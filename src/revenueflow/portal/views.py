"""Operational portal routes (ADR-073).

Reads go straight through repositories.analytics/audit/portal (same pool as
the API — no new connection path). Actions (approve/reject/resolve) reuse
mcp.tools's already-tested functions, which call the existing internal HTTP
routes via httpx (revenueflow.mcp.tools has no dependency on the `mcp`
package, ADR-064) — the portal never writes to approval/handoff/quote tables
directly (ADR-037).
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from revenueflow.config import get_settings
from revenueflow.mcp import tools as mcp_tools
from revenueflow.observability import live
from revenueflow.observability.masking import mask
from revenueflow.portal import auth
from revenueflow.repositories import analytics as analytics_repo
from revenueflow.repositories import portal as portal_repo
from revenueflow.repositories import session as session_repo
from revenueflow.repositories.db import read_connection
from revenueflow.services.audit import reconstruct

router = APIRouter(prefix="/portal")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


def get_session(request: Request) -> auth.Session:
    settings = get_settings()
    cookie = request.cookies.get(auth.COOKIE_NAME)
    if cookie is None:
        raise HTTPException(status_code=303, headers={"Location": "/portal/login"})
    session = auth.verify_session(cookie, secret=settings.portal_session_secret)
    if session is None:
        raise HTTPException(status_code=303, headers={"Location": "/portal/login"})
    return session


SessionDep = Annotated[auth.Session, Depends(get_session)]


def _internal_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=get_settings().revenueflow_api_base_url, timeout=10.0)


@router.get("/login")
async def login_page(request: Request) -> Any:
    return templates.TemplateResponse(
        request, "login.html", {"google_client_id": get_settings().portal_google_client_id}
    )


@router.post("/login")
async def login_submit(id_token: Annotated[str, Form()]) -> RedirectResponse:
    settings = get_settings()
    email = auth.verify_google_token(id_token, client_id=settings.portal_google_client_id)
    if email is None or not auth.is_allowed(email, allowed_emails=settings.portal_viewer_emails):
        raise HTTPException(status_code=403, detail="not allowed")
    cookie_value = auth.sign_session(email, secret=settings.portal_session_secret)
    response = RedirectResponse(url="/portal/", status_code=303)
    response.set_cookie(auth.COOKIE_NAME, cookie_value, httponly=True, samesite="lax")
    return response


@router.post("/logout")
async def logout() -> RedirectResponse:
    response = RedirectResponse(url="/portal/login", status_code=303)
    response.delete_cookie(auth.COOKIE_NAME)
    return response


@router.get("/")
async def home(request: Request, session: SessionDep) -> Any:
    async with read_connection() as conn:
        revenue_rows = await analytics_repo.conversation_revenue(conn)
        cost_rows = await analytics_repo.cost_per_outcome(conn)
        handoff_row = (await analytics_repo.handoff_rate(conn))[0]
    total_revenue = sum(r["revenue"] for r in revenue_rows)
    total_ai_cost = sum(r["ai_cost_usd"] for r in revenue_rows)
    total_turns = handoff_row["total_turns"] or 0
    handoff_turns = handoff_row["handoff_turns"] or 0
    return templates.TemplateResponse(
        request,
        "home.html",
        {
            "session": session,
            "total_revenue": total_revenue,
            "total_ai_cost": total_ai_cost,
            "conversation_count": len(revenue_rows),
            "handoff_rate": (handoff_turns / total_turns) if total_turns else 0.0,
            "cost_rows": cost_rows,
        },
    )


@router.get("/conversations")
async def conversations(request: Request, session: SessionDep) -> Any:
    async with read_connection() as conn:
        rows = await portal_repo.recent_conversations(conn)
    for row in rows:
        row["phone"] = mask(row["phone"])
    return templates.TemplateResponse(
        request, "conversations.html", {"session": session, "conversations": rows}
    )


@router.get("/conversations/{conversation_id}")
async def conversation_detail(request: Request, session: SessionDep, conversation_id: str) -> Any:
    async with read_connection() as conn:
        phone = await session_repo.phone_for(conn, conversation_id)
    turns = await reconstruct(conversation_id)
    return templates.TemplateResponse(
        request,
        "conversation_detail.html",
        {
            "session": session,
            "conversation_id": conversation_id,
            "phone": mask(phone) if phone else None,
            "turns": turns,
        },
    )


@router.get("/conversations/{conversation_id}/audit.json")
async def conversation_audit_export(
    session: SessionDep, conversation_id: str
) -> list[dict[str, Any]]:
    return await reconstruct(conversation_id)


@router.get("/transactions")
async def transactions(request: Request, session: SessionDep) -> Any:
    async with read_connection() as conn:
        rows = await portal_repo.recent_transactions(conn)
    return templates.TemplateResponse(
        request, "transactions.html", {"session": session, "transactions": rows}
    )


@router.get("/customers")
async def customers(request: Request, session: SessionDep) -> Any:
    async with read_connection() as conn:
        rows = await analytics_repo.customer_360_all(conn)
    return templates.TemplateResponse(
        request, "customers.html", {"session": session, "customers": rows}
    )


@router.get("/funnel")
async def funnel(request: Request, session: SessionDep) -> Any:
    async with read_connection() as conn:
        leads = await analytics_repo.lead_funnel(conn)
        opportunities = await analytics_repo.opportunity_summary(conn)
    return templates.TemplateResponse(
        request, "funnel.html", {"session": session, "leads": leads, "opportunities": opportunities}
    )


@router.get("/approvals")
async def approvals(request: Request, session: SessionDep) -> Any:
    settings = get_settings()
    async with _internal_client() as client:
        pending = await mcp_tools.list_pending_approvals(client, settings.approval_api_token)
    return templates.TemplateResponse(
        request, "approvals.html", {"session": session, "approvals": pending}
    )


@router.post("/approvals/{approval_id}")
async def decide_approval(
    session: SessionDep,
    approval_id: str,
    decision: Annotated[str, Form()],
    discount_pct: Annotated[str | None, Form()] = None,
) -> RedirectResponse:
    settings = get_settings()
    async with _internal_client() as client:
        await mcp_tools.decide_approval(
            client, settings.approval_api_token, approval_id, decision, discount_pct or None
        )
    return RedirectResponse(url="/portal/approvals", status_code=303)


@router.get("/handoffs")
async def handoffs(request: Request, session: SessionDep) -> Any:
    settings = get_settings()
    async with _internal_client() as client:
        pending = await mcp_tools.list_pending_handoffs(client, settings.handoff_api_token)
    return templates.TemplateResponse(
        request, "handoffs.html", {"session": session, "handoffs": pending}
    )


@router.post("/handoffs/{handoff_id}")
async def resolve_handoff(session: SessionDep, handoff_id: str) -> RedirectResponse:
    settings = get_settings()
    async with _internal_client() as client:
        await mcp_tools.resolve_handoff(client, settings.handoff_api_token, handoff_id)
    return RedirectResponse(url="/portal/handoffs", status_code=303)


@router.get("/live")
async def live_view(request: Request, session: SessionDep) -> Any:
    return templates.TemplateResponse(request, "live.html", {"session": session})


@router.get("/live/stream")
async def live_stream(session: SessionDep) -> StreamingResponse:
    async def _events() -> Any:
        async for payload in live.listen():
            yield f"data: {payload}\n\n"

    return StreamingResponse(_events(), media_type="text/event-stream")
