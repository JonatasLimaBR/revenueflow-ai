import pytest

from revenueflow.config import get_settings


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_langfuse_credentials_strip_trailing_crlf(monkeypatch: pytest.MonkeyPatch) -> None:
    # Found live (2026-09-11): "Langfuse ainda sem dados" traced down to
    # `Illegal header value b'pk-lf-...\r\n'` -- the secret was stored with a
    # trailing CRLF (almost certainly `echo` without `-n` when it was
    # populated into Secret Manager). http.client refuses to send a header
    # value containing CR/LF, so every request failed before it left the
    # process, with no structured status code -- always surfacing as the
    # SDK's generic "Unexpected error occurred", never anything actionable.
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-test\r\n")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-test\r\n")
    monkeypatch.setenv("LANGFUSE_HOST", "https://langfuse.example.com\r\n")
    get_settings.cache_clear()

    s = get_settings()
    assert s.langfuse_public_key == "pk-lf-test"
    assert s.langfuse_secret_key == "sk-lf-test"
    assert s.langfuse_host == "https://langfuse.example.com"
