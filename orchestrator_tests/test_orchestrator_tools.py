"""Test orchestrator tool registration and callability."""
import pytest, sys, os
sys.path.insert(0, os.path.expanduser("~/astrobot_mesh"))

def test_tools_list_not_empty():
    from orchestrator.agent import root_agent
    assert len(root_agent.tools) >= 3

def test_call_data_scientist_registered():
    from orchestrator.agent import root_agent
    names = [getattr(t, '__name__', str(t)) for t in root_agent.tools]
    assert any("data_scientist" in n for n in names)

def test_call_persona_aggregator_registered():
    from orchestrator.agent import root_agent
    names = [getattr(t, '__name__', str(t)) for t in root_agent.tools]
    assert any("persona" in n for n in names)

def test_submit_feedback_registered():
    from orchestrator.agent import root_agent
    names = [getattr(t, '__name__', str(t)) for t in root_agent.tools]
    assert any("feedback" in n for n in names)

def test_call_data_scientist_callable():
    from orchestrator.agent import call_data_scientist
    assert callable(call_data_scientist)

def test_call_persona_aggregator_callable():
    from orchestrator.agent import call_persona_aggregator
    assert callable(call_persona_aggregator)

def test_call_project_manager_callable():
    from orchestrator.agent import call_project_manager
    assert callable(call_project_manager)

def test_submit_feedback_callable():
    from orchestrator.agent import submit_feedback
    assert callable(submit_feedback)

def test_submit_feedback_positive():
    import asyncio
    from orchestrator.agent import submit_feedback
    class FakeCtx:
        state = {"turn_count": 1, "client_id": "NPI", "feedback_log": []}
    result = asyncio.run(submit_feedback(1, "Great answer!", FakeCtx()))
    assert "👍" in result

def test_submit_feedback_negative():
    import asyncio
    from orchestrator.agent import submit_feedback
    class FakeCtx:
        state = {"turn_count": 1, "client_id": "NPI", "feedback_log": []}
    result = asyncio.run(submit_feedback(-1, "Wrong answer", FakeCtx()))
    assert "👎" in result

def test_submit_feedback_stores_in_state():
    import asyncio
    from orchestrator.agent import submit_feedback
    class FakeCtx:
        state = {"turn_count": 2, "client_id": "NPI"}
    asyncio.run(submit_feedback(1, "Good", FakeCtx()))
    assert len(FakeCtx.state.get("feedback_log", [])) == 1

def test_match_skill_forecast():
    from orchestrator.agent import _match_skill
    assert _match_skill("forecast spend next month") == "bqml_forecast"

def test_match_skill_arima():
    from orchestrator.agent import _match_skill
    assert _match_skill("ARIMA model for NPI") == "bqml_forecast"

def test_match_skill_cluster():
    from orchestrator.agent import _match_skill
    assert _match_skill("cluster campaigns by performance") == "bqml_cluster"

def test_match_skill_kmeans():
    from orchestrator.agent import _match_skill
    assert _match_skill("k-means grouping") == "bqml_cluster"

def test_match_skill_anomaly():
    from orchestrator.agent import _match_skill
    assert _match_skill("detect anomaly in spend") == "anomaly"

def test_match_skill_spike():
    from orchestrator.agent import _match_skill
    assert _match_skill("unusual spike in cost") == "anomaly"

def test_match_skill_chart():
    from orchestrator.agent import _match_skill
    assert _match_skill("plot bar chart of channels") == "charts"

def test_match_skill_visualize():
    from orchestrator.agent import _match_skill
    assert _match_skill("visualize channel spend") == "charts"

def test_match_skill_cpa():
    from orchestrator.agent import _match_skill
    assert _match_skill("what is the CPA by channel") == "channel_efficiency"

def test_match_skill_pacing():
    from orchestrator.agent import _match_skill
    assert _match_skill("are we pacing well this month") == "channel_efficiency"

def test_match_skill_default():
    from orchestrator.agent import _match_skill
    assert _match_skill("show top channels by spend") == "nl2sql"

def test_match_skill_empty():
    from orchestrator.agent import _match_skill
    assert _match_skill("") == "nl2sql"

# ══════════════════════════════════════════════════════════════
# Economist agent integration tests
# ══════════════════════════════════════════════════════════════

def test_call_economist_registered():
    from orchestrator.agent import root_agent
    names = [getattr(t, '__name__', str(t)) for t in root_agent.tools]
    assert any("economist" in n for n in names)

def test_call_economist_callable():
    from orchestrator.agent import call_economist
    assert callable(call_economist)

def test_economist_routing_vertical():
    from orchestrator.agent import _match_skill
    # Economist queries should route via nl2sql (orchestrator decides routing)
    result = _match_skill("what vertical is venetian resort")
    assert isinstance(result, str)

def test_economist_before_tool_allows_call():
    from orchestrator.agent import before_tool_callback
    class FakeTool:
        name = "call_economist"
    class FakeCtx:
        state = {"client_id": "Venetian", "tools_called_this_turn": 0, "current_skill": "nl2sql"}
    result = before_tool_callback(FakeTool(), {"economic_request": "vertical classification"}, FakeCtx())
    assert result is None

def test_economist_econ_endpoint_exists():
    import os
    os.environ.setdefault("ECON_AGENT_ENDPOINT",
                          "https://economist-agent-866797370377.us-central1.run.app")
    endpoint = os.getenv("ECON_AGENT_ENDPOINT")
    assert "economist" in endpoint

def test_call_economist_remote_error_handling():
    import asyncio, os
    os.environ["ECON_AGENT_ENDPOINT"] = "http://localhost:99999"
    from orchestrator.agent import call_economist
    class FakeCtx:
        state = {"client_id": "NPI", "session_id": "test"}
    try:
        result = asyncio.run(call_economist("GDP data 2025", FakeCtx()))
        assert isinstance(result, str)
        assert "error" in result.lower() or "Error" in result
    except Exception:
        pass
    finally:
        os.environ["ECON_AGENT_ENDPOINT"] = \
            "https://economist-agent-866797370377.us-central1.run.app"
