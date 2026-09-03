import pytest

from revenueflow.config import get_settings


@pytest.fixture(autouse=True)
def _clear_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_defaults() -> None:
    s = get_settings()
    assert s.llm_call_timeout_s == 6.0
    assert s.db_statement_timeout_ms == 3000
    assert s.turn_budget_s == 15.0


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LLM_CALL_TIMEOUT_S", "4.5")
    monkeypatch.setenv("DB_STATEMENT_TIMEOUT_MS", "1500")
    monkeypatch.setenv("TURN_BUDGET_S", "0.1")
    get_settings.cache_clear()

    s = get_settings()
    assert s.llm_call_timeout_s == 4.5
    assert s.db_statement_timeout_ms == 1500
    assert s.turn_budget_s == 0.1
