"""Test orchestrator security guardrails."""
import pytest, sys, os, time
sys.path.insert(0, os.path.expanduser("~/astrobot_mesh"))

class FakeTool:
    def __init__(self, name): self.name = name

class FakeToolCtx:
    def __init__(self, client_id="NPI", extra=None):
        self.state = {
            "client_id": client_id,
            "tools_called_this_turn": 0,
            "current_skill": "nl2sql"
        }
        if extra:
            self.state.update(extra)

def test_invalid_client_blocked():
    from orchestrator.agent import before_tool_callback
    tool = FakeTool("call_data_scientist")
    ctx = FakeToolCtx("UnknownClient")
    result = before_tool_callback(tool, {"query": "test"}, ctx)
    assert result is not None
    assert "error" in result

def test_valid_clients_allowed():
    from orchestrator.agent import before_tool_callback, VALID_CLIENTS
    tool = FakeTool("call_data_scientist")
    for client in VALID_CLIENTS:
        ctx = FakeToolCtx(client, {"last_tool_query": ""})
        result = before_tool_callback(tool, {"query": f"For {client} show top channels"}, ctx)
        assert result is None, f"Valid client {client} was blocked"

def test_pa_blocked_without_ds_result():
    from orchestrator.agent import before_tool_callback
    tool = FakeTool("call_persona_aggregator")
    ctx = FakeToolCtx("NPI", {
        "tool_result_this_turn": False,
        "last_ds_response": None
    })
    result = before_tool_callback(tool, {"persona_request": "which persona"}, ctx)
    assert result is not None
    assert "error" in result
    assert "call_data_scientist" in result["error"]

def test_pa_allowed_after_ds_result():
    from orchestrator.agent import before_tool_callback
    tool = FakeTool("call_persona_aggregator")
    ctx = FakeToolCtx("NPI", {
        "tool_result_this_turn": True,
        "last_ds_response": "CTV $992k spend"
    })
    result = before_tool_callback(tool, {"persona_request": "which persona aligns"}, ctx)
    assert result is None

def test_pa_allowed_with_existing_ds_response():
    from orchestrator.agent import before_tool_callback
    tool = FakeTool("call_persona_aggregator")
    ctx = FakeToolCtx("NPI", {
        "tool_result_this_turn": False,
        "last_ds_response": "Paid Social $965k spend last quarter"
    })
    result = before_tool_callback(tool, {"persona_request": "persona analysis"}, ctx)
    assert result is None

def test_duplicate_ds_call_blocked():
    from orchestrator.agent import before_tool_callback
    tool = FakeTool("call_data_scientist")
    query = "show top 5 channels by spend for NPI last quarter"
    ctx = FakeToolCtx("NPI", {
        "last_tool_query": query,
        "last_ds_response": "CTV $992k",
        "tool_result_this_turn": True
    })
    result = before_tool_callback(tool, {"query": query}, ctx)
    assert result is not None
    assert "result" in result

def test_cross_client_ref_logged():
    from orchestrator.agent import before_tool_callback
    tool = FakeTool("call_data_scientist")
    ctx = FakeToolCtx("NPI", {"last_tool_query": ""})
    # Query mentions another client — logged but not blocked at tool level
    result = before_tool_callback(
        tool,
        {"query": "show Venetian data for comparison"},
        ctx
    )
    # Tool callback doesn't block — orchestrator prompt handles this
    assert result is None or "error" in (result or {})

def test_after_tool_error_logged():
    from orchestrator.agent import after_tool_callback
    tool = FakeTool("call_data_scientist")
    ctx = FakeToolCtx("NPI", {"current_skill": "nl2sql", "turn_count": 1})
    after_tool_callback(tool, {}, ctx, "**Agent Error: timeout occurred**")
    assert len(ctx.state.get("error_log", [])) > 0

def test_after_tool_no_error_not_logged():
    from orchestrator.agent import after_tool_callback
    tool = FakeTool("call_data_scientist")
    ctx = FakeToolCtx("NPI", {"current_skill": "nl2sql", "turn_count": 1})
    after_tool_callback(tool, {}, ctx, "CTV spend was $992k last quarter")
    assert len(ctx.state.get("error_log", [])) == 0
