"""Portal authentication (ADR-073): Google Sign-In verification, email
allowlist (reused from ADR-065's dashboard_viewer_emails), and a signed
session cookie. No dependency on the `mcp` package; `google-auth` is imported
lazily inside `verify_google_token` so importing this module never requires
the optional `portal` extra — same pattern as `mcp/auth.py`.
"""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass

COOKIE_NAME = "revenueflow_portal_session"
_SESSION_TTL_S = 12 * 3600  # SHOULD S1: session expires, not eternal


@dataclass(frozen=True)
class Session:
    email: str
    issued_at: int


def verify_google_token(id_token: str, *, client_id: str) -> str | None:
    """Returns the verified email, or None if the token is invalid/expired."""
    if client_id == "":
        return None
    from google.auth.transport import requests as google_requests
    from google.oauth2 import id_token as google_id_token

    try:
        claims = google_id_token.verify_oauth2_token(  # type: ignore[no-untyped-call]
            id_token, google_requests.Request(), client_id
        )
    except Exception:
        return None
    email = claims.get("email")
    return email if claims.get("email_verified") and email else None


def is_allowed(email: str, *, allowed_emails: str) -> bool:
    allowed = {e.strip().lower() for e in allowed_emails.split(",") if e.strip()}
    return email.lower() in allowed


def sign_session(email: str, *, secret: str) -> str:
    issued_at = int(time.time())
    payload = f"{email}:{issued_at}"
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}:{signature}"


def verify_session(cookie_value: str, *, secret: str) -> Session | None:
    parts = cookie_value.split(":")
    if len(parts) != 3:
        return None
    email, issued_at_str, signature = parts
    payload = f"{email}:{issued_at_str}"
    expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    if not issued_at_str.isdigit():
        return None
    issued_at = int(issued_at_str)
    if time.time() - issued_at > _SESSION_TTL_S:
        return None
    return Session(email=email, issued_at=issued_at)
