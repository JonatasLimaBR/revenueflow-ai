from pathlib import Path

_PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"


def test_langfuse_pinned_below_v3() -> None:
    # Regression: langfuse 3.x/4.x removed Client.trace() -- LangfuseTracer
    # (observability/tracer.py) uses that v2 API and silently falls back to
    # noop (AttributeError caught + logged) when an unpinned install pulls
    # the latest major version. Found live in production 2026-09-09.
    body = _PYPROJECT.read_text()
    assert '"langfuse>=2.50,<3"' in body
