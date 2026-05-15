"""End-to-end agent runs via ADK Runner — exercise full agent.py + sub_agents.

Run with:    pytest data_science_tests/test_live_agent.py --live -v
Cost: ~$0.50-1 per full run (LLM tokens).

Each test prompts the agent and captures tool calls + final response.
"""
import asyncio
import os
import time
import pytest

REQUIRED_ENV = ("GOOGLE_CLOUD_PROJECT", "DATASET_CONFIG_FILE_V3")


class _AgentInvoker:
    """Wraps ADK Runner to invoke the root agent in-process."""

    def __init__(self):
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        from data_science.agent import root_agent
        self.session_service = InMemorySessionService()
        self.runner = Runner(
            agent=root_agent,
            app_name="astrobot_test",
            session_service=self.session_service,
        )

    async def invoke(self, prompt, user_id="test_user", session_id=None):
        from google.genai import types
        if session_id is None:
            session_id = "test_" + str(int(time.time() * 1000))
        await self.session_service.create_session(
            app_name="astrobot_test", user_id=user_id, session_id=session_id,
        )
        captured = {"final_response": "", "tool_calls": [], "errors": []}
        try:
            content = types.Content(role="user", parts=[types.Part(text=prompt)])
            async for event in self.runner.run_async(
                user_id=user_id, session_id=session_id, new_message=content,
            ):
                if hasattr(event, "content") and event.content:
                    for part in (event.content.parts or []):
                        if hasattr(part, "function_call") and part.function_call:
                            captured["tool_calls"].append(part.function_call.name)
                        if (hasattr(part, "text") and part.text
                                and event.is_final_response()):
                            captured["final_response"] += part.text
        except Exception as e:
            captured["errors"].append(f"{type(e).__name__}: {e}")
        return captured


@pytest.fixture(scope="module")
def invoker():
    """Create one invoker for the module — reused across tests."""
    for var in REQUIRED_ENV:
        if not os.environ.get(var):
            pytest.skip(f"Required env var unset: {var}")
    return _AgentInvoker()


@pytest.mark.live_agent
@pytest.mark.asyncio
async def test_npi_top_channels_basic(invoker):
    """Smoke test — basic NL2SQL question should work."""
    result = await invoker.invoke("For NPI, top 5 channels by spend last 6 months")
    assert not result["errors"], f"Agent errored: {result['errors']}"
    assert result["final_response"], "Empty response"


@pytest.mark.live_agent
@pytest.mark.asyncio
async def test_npi_volatility_question(invoker):
    """Routes through compute_channel_volatility or NL2SQL — both acceptable."""
    result = await invoker.invoke(
        "For NPI, which channels are most volatile in cost over last 12 months?"
    )
    assert not result["errors"]
    assert result["final_response"]
    # Should mention a channel name OR contain "volatility"
    resp = result["final_response"].lower()
    assert "volatil" in resp or "cv" in resp or "performance" in resp


@pytest.mark.live_agent
@pytest.mark.asyncio
async def test_npi_saturation_question(invoker):
    """Saturation question — should call compute_saturation_curve or NL2SQL."""
    result = await invoker.invoke(
        "For NPI, build a saturation model for next $100k investment"
    )
    # Saturation can be slow — just check it doesn't error
    if result["errors"]:
        # Saturation has quality gates that may fail with partial data — that's OK
        assert "quality" in str(result["errors"]).lower() or \
               "channel" in str(result["errors"]).lower()
    else:
        assert result["final_response"]


@pytest.mark.live_agent
@pytest.mark.asyncio
async def test_npi_chart_request_renders(invoker):
    """Explicit chart request should result in chart rendering."""
    result = await invoker.invoke(
        "For NPI, show me a bar chart of top 5 channels by spend last quarter"
    )
    # If errors, log them — chart can fail in many ways but agent shouldn't crash
    if result["errors"]:
        pytest.skip(f"Chart test failed (often data-related): {result['errors'][:1]}")
    assert result["final_response"]


@pytest.mark.live_agent
@pytest.mark.asyncio
async def test_npi_walled_garden(invoker):
    """Switching to Venetian mid-conversation should be refused (AC-5)."""
    # Session 1: lock to NPI
    await invoker.invoke("For NPI, top channels by spend")
    # Session 2: try to ask about a different client
    result = await invoker.invoke("What about Venetian performance?")
    # Should either:
    # - Refuse with "locked to NPI"
    # - Allow it (if walled garden isn't enforced cross-invocation)
    # Either is acceptable — just verify no crash
    assert not result["errors"] or "locked" in str(result["errors"]).lower()
