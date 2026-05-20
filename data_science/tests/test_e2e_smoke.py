"""End-to-end smoke tests against the deployed Astrobot data_science agent.

Hits the deployed Cloud Run agent over HTTP using ADK's standard API server
endpoints. These are SLOW tests — each makes real LLM calls and BQ queries.
Suite runtime: ~3-5 minutes.

Each test creates a fresh session to avoid long-session drift contamination
(Session 10 verified that fresh-session testing is required — contaminated
sessions can hide hallucination bugs).

Auth: uses `gcloud auth print-identity-token` from the test environment.
Run from Cloud Shell or any machine with gcloud configured.

Usage:
    pytest data_science/tests/test_e2e_smoke.py -v
    pytest data_science/tests/test_e2e_smoke.py::test_npi_inventory -v

Configurable via env:
    ASTROBOT_BASE_URL   — default: deployed v4 Cloud Run URL
    ASTROBOT_LLM_TIMEOUT — per-request timeout in seconds, default 90
"""

import os
import re
import subprocess
import time
import uuid

import pytest
import requests

# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────
BASE_URL = os.getenv(
    "ASTROBOT_BASE_URL",
    "https://astrobot-ds-v4-2jfu4lrr2q-uc.a.run.app",
).rstrip("/")
APP_NAME = "data_science"
LLM_TIMEOUT = int(os.getenv("ASTROBOT_LLM_TIMEOUT", "90"))


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def auth_token() -> str:
    """Get gcloud identity token. Cached for the whole module."""
    try:
        token = subprocess.check_output(
            ["gcloud", "auth", "print-identity-token"],
            text=True,
            timeout=10,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as e:
        pytest.skip(f"gcloud auth print-identity-token failed: {e}")
    if not token:
        pytest.skip("gcloud returned empty identity token")
    return token


@pytest.fixture(scope="module")
def headers(auth_token: str) -> dict:
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
    }


def _create_session(headers: dict, client_id: str) -> tuple[str, str]:
    """Create a fresh session with LOCKED_CLIENT preset. Returns (user_id, session_id)."""
    user_id = f"test_{uuid.uuid4().hex[:8]}"
    session_id = f"s_{uuid.uuid4().hex[:12]}"
    url = f"{BASE_URL}/apps/{APP_NAME}/users/{user_id}/sessions/{session_id}"
    # The bqml_before_agent_callback checks client_id, LOCKED_CLIENT, or client_lock.
    # Set all three to be safe — different agents in the mesh may read different keys.
    payload = {
        "state": {
            "LOCKED_CLIENT": client_id,
            "client_id": client_id,
            "client_lock": client_id,
        }
    }
    r = requests.post(url, json=payload, headers=headers, timeout=20)
    assert r.status_code in (200, 201), (
        f"Session creation failed: {r.status_code} {r.text[:300]}"
    )
    return user_id, session_id


def _send(headers: dict, user_id: str, session_id: str, message: str) -> dict:
    """Send a message to the agent. Returns the parsed run response (list of events)."""
    url = f"{BASE_URL}/run"
    payload = {
        "appName": APP_NAME,
        "userId": user_id,
        "sessionId": session_id,
        "newMessage": {"role": "user", "parts": [{"text": message}]},
    }
    r = requests.post(url, json=payload, headers=headers, timeout=LLM_TIMEOUT)
    assert r.status_code == 200, f"/run failed: {r.status_code} {r.text[:500]}"
    return r.json()


def _extract_text(events: list) -> str:
    """Concatenate all model-text parts from the event stream."""
    chunks = []
    for ev in events:
        content = ev.get("content") or {}
        if content.get("role") != "model":
            continue
        for part in content.get("parts") or []:
            txt = part.get("text")
            if txt:
                chunks.append(txt)
    return "\n".join(chunks)


def _extract_tool_calls(events: list) -> list[str]:
    """Return list of tool names called during this run."""
    names = []
    for ev in events:
        for part in (ev.get("content") or {}).get("parts") or []:
            fc = part.get("functionCall") or part.get("function_call")
            if fc and fc.get("name"):
                names.append(fc["name"])
    return names


def _extract_sql_strings(events: list) -> list[str]:
    """Return all SQL-looking strings found anywhere in tool args/responses."""
    sql_blobs = []
    for ev in events:
        for part in (ev.get("content") or {}).get("parts") or []:
            fc = part.get("functionCall") or part.get("function_call") or {}
            args = fc.get("args") or {}
            for v in args.values():
                if isinstance(v, str) and ("SELECT" in v.upper() or "CREATE" in v.upper()):
                    sql_blobs.append(v)
            fr = part.get("functionResponse") or part.get("function_response") or {}
            resp = fr.get("response") or {}
            for v in resp.values() if isinstance(resp, dict) else []:
                if isinstance(v, str) and ("SELECT" in v.upper() or "CREATE" in v.upper()):
                    sql_blobs.append(v)
    return sql_blobs


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────
def test_deployed_endpoint_reachable(headers):
    """Smoke 0: confirm the deployed agent is up and registered."""
    r = requests.get(f"{BASE_URL}/list-apps", headers=headers, timeout=15)
    assert r.status_code == 200, f"/list-apps failed: {r.status_code}"
    assert APP_NAME in r.json(), f"Expected '{APP_NAME}' in apps, got {r.json()}"


def test_npi_inventory(headers):
    """Smoke 1: 'what BQML models do you have for NPI?' → expects ≥10 models listed.

    Confirms BEF dynamic discovery (Session 10 win #2) still works.
    """
    user_id, session_id = _create_session(headers, "NPI")
    events = _send(headers, user_id, session_id,
                   "What BQML models do you have for NPI?")
    text = _extract_text(events)

    assert text, "Agent returned no text"
    # Loose check — agent should mention model names from the registry
    # Expect at least one of the known production model names
    known = ["arima", "saturation", "linear", "cluster", "boosted"]
    hits = sum(1 for k in known if k.lower() in text.lower())
    assert hits >= 2, f"Expected ≥2 model-type keywords, got {hits}. Text:\n{text[:800]}"


def test_npi_forecast_no_locked_client_leak(headers):
    """Smoke 2: 'Forecast spend next 14 days' → must NOT contain 'LOCKED_CLIENT'.

    Confirms Fix-T state substitution (Session 10 win #5) still works:
    SQL templates should resolve {state.LOCKED_CLIENT} → 'NPI', not leak the
    literal placeholder string into emitted SQL.
    """
    user_id, session_id = _create_session(headers, "NPI")
    events = _send(headers, user_id, session_id,
                   "For NPI, forecast spend for the next 14 days")
    text = _extract_text(events)
    sqls = _extract_sql_strings(events)

    assert text, "Agent returned no text"
    # Critical: no literal placeholder leak in any SQL we can see
    for sql in sqls:
        assert "LOCKED_CLIENT" not in sql, (
            f"Found literal 'LOCKED_CLIENT' in emitted SQL — Fix-T regression:\n{sql[:500]}"
        )
        assert "{state." not in sql, (
            f"Found unresolved {{state.X}} placeholder in SQL:\n{sql[:500]}"
        )
    # Same check applied to the natural-language response (some agents echo SQL)
    assert "LOCKED_CLIENT" not in text, (
        f"'LOCKED_CLIENT' leaked into response text:\n{text[:500]}"
    )


def test_npi_saturation_calls_tool(headers):
    """Smoke 3: 'saturation analysis by channel' → must call a tool this turn.

    Confirms Phase H anti-hallucination (Session 10 win #4) still works:
    a fresh-session saturation request should trigger tool calls (not be
    answered purely from prompt-example numbers).
    """
    user_id, session_id = _create_session(headers, "NPI")
    events = _send(headers, user_id, session_id,
                   "For NPI, show me saturation analysis by channel")
    text = _extract_text(events)
    tool_calls = _extract_tool_calls(events)

    assert text, "Agent returned no text"
    assert tool_calls, (
        f"Saturation request did not trigger any tool calls — "
        f"possible Phase H regression (agent may be hallucinating numbers).\n"
        f"Response:\n{text[:800]}"
    )
    # Anti-hallucination canary: the Phase H prompt edits removed the worked
    # example numbers $85.50 / $44.94. If those leak into a response, the
    # prompt edits were reverted.
    assert "$85.50" not in text, "Worked-example number $85.50 leaked — Phase H regression"
    assert "$44.94" not in text, "Worked-example number $44.94 leaked — Phase H regression"


def test_winndixie_channel_filter(headers):
    """Smoke 5: WinnDixie 'spend by channel last quarter' → multiple channel rows.

    Confirms WinnDixie filter routing (Session 10 win #1) still works:
    client_filter_value='SEG' is correctly mapped so the SQL filter returns
    real rows instead of an empty result set.
    """
    user_id, session_id = _create_session(headers, "WinnDixie")
    events = _send(headers, user_id, session_id,
                   "For WinnDixie, show total spend by channel for 2025")
    text = _extract_text(events)

    assert text, "Agent returned no text"
    # At least 2 channel keywords should appear (loose check)
    channels = ["search", "social", "ctv", "pmax", "performance max",
                "demand gen", "display", "video"]
    hits = sum(1 for c in channels if c.lower() in text.lower())
    assert hits >= 2, (
        f"WinnDixie 'spend by channel' returned <2 channel mentions ({hits}). "
        f"Possible filter regression (empty result set).\nResponse:\n{text[:800]}"
    )




def test_npi_forecast_uses_registry_model_name(headers):
    """Session 12 Item 2: forecast conversions → SQL must use registry model name verbatim.

    Confirms USE_DISCOVERED_MODELS rule + model_name param in get_arima_forecast_sql.
    The SQL emitted must reference arima_npi_all_conversions (the healthy registry
    model), not a fabricated name constructed from client_lower patterns.
    """
    user_id, session_id = _create_session(headers, "NPI")
    events = _send(headers, user_id, session_id,
                   "For NPI, forecast conversions for the next 14 days")
    text = _extract_text(events)
    sqls = _extract_sql_strings(events)

    assert text, "Agent returned no text"
    # Must find the registry model name in at least one SQL string
    registry_name = "arima_npi_all_conversions"
    found = any(registry_name in sql for sql in sqls)
    # Also check response text — agent sometimes echoes the model name
    found_in_text = registry_name in text
    sql_preview = [s[:200] for s in sqls]
    assert found or found_in_text, (
        "Registry model name arima_npi_all_conversions not found in SQL or response. "
        "Agent may be fabricating model names (Item 2 regression). "
        f"SQLs: {sql_preview} Response: {text[:300]}"
    )
    # Also assert no obviously fabricated names
    fabricated = ["arima_npi_all_spend", "npi_arima_all_conversions",
                  "arima_npi_conversions_all"]
    for name in fabricated:
        assert name not in str(sqls), (
            f"Fabricated model name '{name}' found in SQL — Item 2 regression"
        )


def test_npi_saturation_multi_channel(headers):
    """Session 12 Item 4: saturation analysis → must return results for >1 channel.

    Confirms Firestore fix: saturation bqml_models ref updated from degenerate
    npi_conversions_saturation to healthy npi_conversions_saturation_agg.
    A degenerate model returns 1 empty row; healthy model returns multi-channel output.
    """
    user_id, session_id = _create_session(headers, "NPI")
    events = _send(headers, user_id, session_id,
                   "For NPI, show me saturation analysis by channel")
    text = _extract_text(events)
    tool_calls = _extract_tool_calls(events)

    assert text, "Agent returned no text"
    assert tool_calls, "Saturation request triggered no tool calls"

    # Must mention at least 2 distinct channels in the response
    channels = ["paid search", "paid social", "search", "social",
                "demand gen", "video", "ctv", "performance max", "pmax"]
    hits = sum(1 for c in channels if c.lower() in text.lower())
    assert hits >= 2, (
        f"Saturation response mentions <2 channels ({hits}) -- "
        f"possible degenerate model regression (Item 4). Response: {text[:800]}"
    )
    # R2 values should appear -- degenerate model produces NaN
    assert any(x in text.lower() for x in ["r²", "r2", "fit quality", "0.867", "alpha", "kappa"]), (
        f"No R2/fit quality mention -- possible degenerate model output. Response: {text[:500]}"
    )


def test_npi_forecast_chart_no_malformed_call(headers):
    """Session 12 Item 3: forecast → chart call must not produce MALFORMED_FUNCTION_CALL.

    Confirms FORECAST CHART INSTRUCTIONS prompt fix. Before the fix, the agent
    wrapped the chart tool call in print(default_api.call_analytics_for_visualization(...))
    which caused a MALFORMED_FUNCTION_CALL error in the event stream.
    """
    user_id, session_id = _create_session(headers, "NPI")
    events = _send(headers, user_id, session_id,
                   "For NPI, forecast conversions for the next 14 days and show a chart")
    text = _extract_text(events)

    assert text, "Agent returned no text"

    # Check no MALFORMED_FUNCTION_CALL in any event
    for ev in events:
        error = ev.get("error") or ev.get("errorCode") or ""
        assert "MALFORMED_FUNCTION_CALL" not in str(error), (
            f"MALFORMED_FUNCTION_CALL detected — Item 3 regression. "
            f"Event: {ev}"
        )
        # Also check inside content parts for error objects
        for part in (ev.get("content") or {}).get("parts") or []:
            part_str = str(part)
            assert "MALFORMED_FUNCTION_CALL" not in part_str, (
                f"MALFORMED_FUNCTION_CALL in content part — Item 3 regression. "
                f"Part: {part_str[:300]}"
            )

    # Forecast data must still be present despite chart attempt
    assert any(d in text for d in ["2026", "forecast", "conversion", "predicted"]), (
        f"Forecast content missing from response. Response: {text[:500]}"
    )

# ─────────────────────────────────────────────────────────────────────────────
# Runtime budget guard — keep suite under ~5 min so CI doesn't time out
# ─────────────────────────────────────────────────────────────────────────────
@pytest.fixture(autouse=True)
def _per_test_timer(request):
    """Log wall-clock duration of each test to make slow tests visible."""
    start = time.monotonic()
    yield
    elapsed = time.monotonic() - start
    if elapsed > LLM_TIMEOUT * 0.9:
        request.node.warn(pytest.PytestWarning(
            f"{request.node.name} took {elapsed:.1f}s (near {LLM_TIMEOUT}s timeout)"
        ))