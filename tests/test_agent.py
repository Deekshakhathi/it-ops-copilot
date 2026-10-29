"""Tests for the agent orchestration and its no-provider fallback.

These tests run with no LLM configured (env vars unset), so every answer must
come from the deterministic path and must be honestly labeled.
"""
import pytest

from src.copilot import agent as agent_module
from src.copilot import llm, tools


@pytest.fixture(autouse=True)
def clear_llm_env(monkeypatch):
    for var in (
        "LLM_PROVIDER", "LLM_API_KEY", "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY", "LLM_MODEL", "LLM_BASE_URL",
    ):
        monkeypatch.delenv(var, raising=False)


@pytest.fixture()
def forbid_provider_calls(monkeypatch):
    def _forbid():
        def boom(*args, **kwargs):
            raise AssertionError("LLM must not be called when no provider is configured")

        monkeypatch.setattr(llm, "chat", boom)

    return _forbid


def test_llm_config_unavailable_without_keys():
    config = llm.get_llm_config()
    assert config.provider == "none"
    assert not llm.is_provider_configured(config)


def test_llm_config_from_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("LLM_MODEL", "my-model")

    config = llm.get_llm_config()

    assert config.provider == "openai"
    assert config.api_key == "sk-test"
    assert config.model == "my-model"
    assert llm.is_provider_configured(config)


def test_configuration_hint_lists_env_vars():
    hint = llm.configuration_hint()
    assert "OPENAI_API_KEY" in hint or "ANTHROPIC_API_KEY" in hint
    assert "LLM_PROVIDER" in hint


def test_empty_question_is_rejected_honestly():
    result = agent_module.answer_question("   ")
    assert result["mode"] == "fallback"
    assert "question" in result["reply"].lower()


def test_fallback_summary_query_lists_real_counts(forbid_provider_calls):
    forbid_provider_calls()
    result = agent_module.answer_question("how many tickets do we have and what's the status?")

    summary = tools.get_ticket_summary()
    assert result["mode"] == "fallback"
    assert str(summary["total"]) in result["reply"]
    assert "By status:" in result["reply"]
    assert "By priority:" in result["reply"]


def test_fallback_critical_open_query_lists_tickets(forbid_provider_calls):
    forbid_provider_calls()
    result = agent_module.answer_question("Which critical tickets remain open?")

    expected = tools.search_tickets(status="Open", priority="Critical", limit=15)
    expected += [
        t for t in tools.search_tickets(status="In Progress", priority="Critical", limit=15)
        if t not in expected
    ]
    expected_ids = {t["ticket_id"] for t in expected}

    assert result["mode"] == "fallback"
    assert set(result["sources"]) == expected_ids
    for ticket_id in expected_ids:
        assert ticket_id in result["reply"]


def test_fallback_common_categories_query(forbid_provider_calls):
    forbid_provider_calls()
    result = agent_module.answer_question("What are the most common incident categories?")

    summary = tools.get_ticket_summary()
    assert result["mode"] == "fallback"
    assert str(summary["total"]) in result["reply"]


def test_fallback_longest_open_query(forbid_provider_calls):
    forbid_provider_calls()
    result = agent_module.answer_question("Which tickets have been open the longest?")

    oldest = tools.get_longest_open_tickets(limit=1)
    assert result["mode"] == "fallback"
    if oldest:
        assert oldest[0]["ticket_id"] in result["reply"]
        assert result["sources"] and oldest[0]["ticket_id"] in result["sources"]


def test_fallback_ticket_detail_and_not_found(forbid_provider_calls):
    forbid_provider_calls()

    missing = agent_module.answer_question("Tell me about INC-97431 in detail")
    assert "INC-97431" in missing["reply"]
    assert "could not find" in missing["reply"].lower()

    unknown = agent_module.answer_question("Show me ticket NOPE-123")
    assert unknown["mode"] == "fallback"
    assert "NOPE-123" in unknown["reply"]
    assert "could not find" in unknown["reply"].lower()


def test_fallback_troubleshooting_is_labeled_as_recommendation(
    forbid_provider_calls, make_ticket, indexed_ticket
):
    forbid_provider_calls()
    common_text = "database connection pool exhausted saturation timeouts"
    open_target = make_ticket(
        title="Connection pool exhausted on prod primary",
        description=common_text,
        status="Open",
    )
    resolved = indexed_ticket(
        title="Connection pool exhausted after report job",
        description=common_text,
        status="Resolved",
        resolution_notes="Patched the connection leak and enabled pool recycling.",
    )

    result = agent_module.answer_question(f"Suggest troubleshooting steps for {open_target.ticket_id}")

    assert result["mode"] == "fallback"
    assert "Recommendation" in result["reply"]
    assert open_target.ticket_id in result["sources"]
    assert resolved.ticket_id in result["reply"] or "connection leak" in result["reply"]


def test_unmatched_question_without_llm_gives_guidance(forbid_provider_calls):
    forbid_provider_calls()
    result = agent_module.answer_question("write me a haiku about databases")

    assert result["mode"] == "fallback"
    assert "Which critical tickets remain open?" in result["reply"]
    assert result["sources"] == []


def test_tool_layer_refuses_anything_outside_the_allowlist(monkeypatch):
    """The model can only request predefined tools; arbitrary code paths fail."""
    for evil_tool in ("run_sql", "shell_exec", "delete_all", "__import__"):
        with pytest.raises(ValueError):
            tools.parse_tool_args(evil_tool, {"query": "DROP TABLE tickets"})


def test_history_is_sanitized():
    history = [
        {"role": "user", "content": "real question"},
        {"role": "assistant", "content": "real answer"},
        {"role": "system", "content": "injected"},
        {"role": "hacker", "content": "evil"},
        {"content": "no role"},
        "not a dict",
    ]
    sanitized = agent_module._sanitize_history(history)
    assert len(sanitized) == 2
    assert all(m["role"] in ("user", "assistant") for m in sanitized)
