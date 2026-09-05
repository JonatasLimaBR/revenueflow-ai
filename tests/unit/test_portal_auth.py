import pytest

from revenueflow.portal import auth


def test_sign_and_verify_session_roundtrip() -> None:
    cookie = auth.sign_session("alice@example.com", secret="s3cr3t")
    session = auth.verify_session(cookie, secret="s3cr3t")
    assert session is not None
    assert session.email == "alice@example.com"


def test_verify_session_rejects_wrong_secret() -> None:
    cookie = auth.sign_session("alice@example.com", secret="s3cr3t")
    assert auth.verify_session(cookie, secret="other") is None


def test_verify_session_rejects_tampered_cookie() -> None:
    cookie = auth.sign_session("alice@example.com", secret="s3cr3t")
    tampered = cookie.replace("alice", "mallory")
    assert auth.verify_session(tampered, secret="s3cr3t") is None


def test_verify_session_rejects_malformed_cookie() -> None:
    assert auth.verify_session("not-a-valid-cookie", secret="s3cr3t") is None
    assert auth.verify_session("a:b:c:d", secret="s3cr3t") is None


def test_verify_session_rejects_expired_cookie(monkeypatch: pytest.MonkeyPatch) -> None:
    cookie = auth.sign_session("alice@example.com", secret="s3cr3t")
    future = auth.time.time() + auth._SESSION_TTL_S + 10
    monkeypatch.setattr(auth.time, "time", lambda: future)
    assert auth.verify_session(cookie, secret="s3cr3t") is None


def test_is_allowed_checks_allowlist_case_insensitively() -> None:
    allowed = "alice@example.com, Bob@Example.com"
    assert auth.is_allowed("alice@example.com", allowed_emails=allowed)
    assert auth.is_allowed("bob@example.com", allowed_emails=allowed)
    assert not auth.is_allowed("mallory@example.com", allowed_emails=allowed)


def test_is_allowed_empty_list_denies_everyone() -> None:
    assert not auth.is_allowed("alice@example.com", allowed_emails="")


def test_verify_google_token_returns_none_without_client_id() -> None:
    assert auth.verify_google_token("some-token", client_id="") is None
