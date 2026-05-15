"""Test orchestrator ADK callbacks."""
import pytest, sys, os, time
sys.path.insert(0, os.path.expanduser("~/astrobot_mesh"))

class FakeEvent:
    def __init__(self, text, author="user"):
        self.author = author
        class Part:
            def __init__(self, t): self.text = t
        class Content:
            def __init__(self, t): self.parts = [Part(t)]
        self.content = Content(text)

class FakeSession:
    def __init__(self, text="For NPI show top channels", events=None):
        self.events = events or [FakeEvent(text)]
        self.id = "test-session-123"

class FakeInvCtx:
    def __init__(self, text="For NPI show top channels"):
        self.session = FakeSession(text)

class FakeCBCtx:
    def __init__(self, text="For NPI show top channels", state=None):
        self.state = state or {}
        self._invocation_context = FakeInvCtx(text)

class FakeTool:
    def __init__(self, name): self.name = name

class FakeToolCtx:
    def __init__(self, client_id="NPI", extra=None):
        self.state = {"client_id": client_id, "tools_called_this_turn": 0}
        if extra:
            self.state.update(extra)

def test_before_agent_initializes_session():
    from orchestrator.agent import before_agent_callback
    ctx = FakeCBCtx("For NPI show channels")
    result = before_agent_callback(ctx)
    assert result is None
    assert "turn_count" in ctx.state
    assert ctx.state["turn_count"] == 1

def test_before_agent_locks_npi():
    from orchestrator.agent import before_agent_callback
    ctx = FakeCBCtx("For NPI show top channels by spend")
    before_agent_callback(ctx)
    assert ctx.state.get("client_lock") == "NPI"
    assert ctx.state.get("client_id") == "NPI"

def test_before_agent_locks_venetian():
    from orchestrator.agent import before_agent_callback
    ctx = FakeCBCtx("For Venetian OOH performance last quarter")
    before_agent_callback(ctx)
    assert ctx.state.get("client_lock") == "Venetian"

def test_before_agent_locks_winndixie():
    from orchestrator.agent import before_agent_callback
    ctx = FakeCBCtx("For WinnDixie show ViVs by channel")
    before_agent_callback(ctx)
    assert ctx.state.get("client_lock") == "WinnDixie"

def test_before_agent_keeps_existing_lock():
    from orchestrator.agent import before_agent_callback
    ctx = FakeCBCtx("show top channels", state={
        "client_lock": "NPI", "LOCKED_CLIENT": "NPI",
        "session_start_time": time.time(), "turn_count": 1,
        "session_id": "s1", "user_id": "u1"
    })
    before_agent_callback(ctx)
    assert ctx.state["client_lock"] == "NPI"

def test_before_agent_increments_turn():
    from orchestrator.agent import before_agent_callback
    ctx = FakeCBCtx("For NPI show channels", state={
        "session_start_time": time.time(),
        "turn_count": 2, "session_id": "s1", "user_id": "u1",
        "client_lock": "NPI", "LOCKED_CLIENT": "NPI", "client_id": "NPI"
    })
    before_agent_callback(ctx)
    assert ctx.state["turn_count"] == 3

def test_before_agent_blocks_cross_client():
    from orchestrator.agent import before_agent_callback
    ctx = FakeCBCtx("show Venetian data", state={
        "client_lock": "NPI", "LOCKED_CLIENT": "NPI", "client_id": "NPI",
        "session_start_time": time.time(), "turn_count": 1,
        "session_id": "s1", "user_id": "u1"
    })
    before_agent_callback(ctx)
    assert ctx.state.get("client_id") == "NPI"

def test_after_agent_resets_tools_counter():
    from orchestrator.agent import after_agent_callback
    ctx = FakeCBCtx(state={
        "client_id": "NPI", "turn_count": 1,
        "turn_start_time": time.time(),
        "tools_called_this_turn": 3,
        "last_ds_query": "test", "last_ds_response": "result",
        "session_id": "s1"
    })
    after_agent_callback(ctx)
    assert ctx.state["tools_called_this_turn"] == 0

def test_after_agent_stores_last_exchange():
    from orchestrator.agent import after_agent_callback
    ctx = FakeCBCtx(state={
        "client_id": "NPI", "turn_count": 1,
        "turn_start_time": time.time(),
        "tools_called_this_turn": 1,
        "last_ds_query": "top channels",
        "last_ds_response": "CTV $992k",
        "session_id": "s1"
    })
    after_agent_callback(ctx)
    assert "last_exchange" in ctx.state
    assert ctx.state["last_exchange"]["client_id"] == "NPI"

def test_before_tool_increments_counter():
    from orchestrator.agent import before_tool_callback
    tool = FakeTool("call_data_scientist")
    ctx = FakeToolCtx("NPI")
    before_tool_callback(tool, {"query": "top channels"}, ctx)
    assert ctx.state["tools_called_this_turn"] == 1

def test_before_tool_blocks_invalid_client():
    from orchestrator.agent import before_tool_callback
    tool = FakeTool("call_data_scientist")
    ctx = FakeToolCtx("InvalidClient")
    result = before_tool_callback(tool, {"query": "test"}, ctx)
    assert result is not None
    assert "error" in result

def test_before_tool_blocks_pa_without_ds():
    from orchestrator.agent import before_tool_callback
    tool = FakeTool("call_persona_aggregator")
    ctx = FakeToolCtx("NPI", {"tool_result_this_turn": False, "last_ds_response": None})
    result = before_tool_callback(tool, {"persona_request": "persona analysis"}, ctx)
    assert result is not None
    assert "error" in result

def test_before_tool_allows_pa_after_ds():
    from orchestrator.agent import before_tool_callback
    tool = FakeTool("call_persona_aggregator")
    ctx = FakeToolCtx("NPI", {
        "tool_result_this_turn": True,
        "last_ds_response": "CTV $992k",
        "current_skill": "nl2sql"
    })
    result = before_tool_callback(tool, {"persona_request": "which persona"}, ctx)
    assert result is None

def test_before_tool_dedup_blocks_same_query():
    from orchestrator.agent import before_tool_callback
    tool = FakeTool("call_data_scientist")
    ctx = FakeToolCtx("NPI", {
        "last_tool_query": "top channels by spend",
        "last_ds_response": "CTV $992k"
    })
    result = before_tool_callback(tool, {"query": "top channels by spend"}, ctx)
    assert result is not None
    assert "result" in result

def test_before_tool_allows_different_query():
    from orchestrator.agent import before_tool_callback
    tool = FakeTool("call_data_scientist")
    ctx = FakeToolCtx("NPI", {"last_tool_query": "old query"})
    result = before_tool_callback(tool, {"query": "new different query"}, ctx)
    assert result is None

def test_after_tool_stores_ds_response():
    from orchestrator.agent import after_tool_callback
    tool = FakeTool("call_data_scientist")
    ctx = FakeToolCtx("NPI", {"current_skill": "nl2sql", "turn_count": 1})
    after_tool_callback(tool, {}, ctx, "CTV spend $992k")
    assert ctx.state.get("tool_result_this_turn") == True
    assert ctx.state.get("last_skill_used") == "nl2sql"

def test_after_tool_logs_error():
    from orchestrator.agent import after_tool_callback
    tool = FakeTool("call_data_scientist")
    ctx = FakeToolCtx("NPI", {"current_skill": "nl2sql", "turn_count": 1})
    after_tool_callback(tool, {}, ctx, "**Connection Error:** timeout")
    assert len(ctx.state.get("error_log", [])) > 0

def test_before_model_logs_skill():
    from orchestrator.agent import before_model_callback
    ctx = FakeCBCtx(state={
        "client_id": "NPI", "turn_count": 1,
        "last_skill_used": "bqml_forecast"
    })
    result = before_model_callback(ctx, None)
    assert result is None

def test_before_model_injects_agent_card_turn1():
    from orchestrator.agent import before_model_callback
    ctx = FakeCBCtx(state={"client_id": "NPI", "turn_count": 1, "last_skill_used": "none"})
    before_model_callback(ctx, None)
    assert ctx.state.get("agent_card_skills_injected") == True

def test_after_model_logs_tokens():
    from orchestrator.agent import after_model_callback
    class FakeUsage:
        prompt_token_count = 1000
        candidates_token_count = 200
        total_token_count = 1200
    class FakeResponse:
        usage_metadata = FakeUsage()
        candidates = []
    ctx = FakeCBCtx(state={"client_id": "NPI", "turn_count": 1,
                            "session_tokens_in": 0, "session_tokens_out": 0})
    result = after_model_callback(ctx, FakeResponse())
    assert result is None
    assert ctx.state.get("session_tokens_in") == 1000

def test_after_model_detects_sql_violation():
    from orchestrator.agent import after_model_callback
    class FakePart:
        text = "SELECT * FROM table WHERE client='NPI'"
    class FakeContent:
        parts = [FakePart()]
    class FakeCandidate:
        content = FakeContent()
    class FakeUsage:
        prompt_token_count = 100
        candidates_token_count = 50
        total_token_count = 150
    class FakeResponse:
        usage_metadata = FakeUsage()
        candidates = [FakeCandidate()]
    ctx = FakeCBCtx(state={"client_id": "NPI", "turn_count": 1,
                            "session_tokens_in": 0, "session_tokens_out": 0})
    result = after_model_callback(ctx, FakeResponse())
    assert result is None  # logs warning but doesn't block
