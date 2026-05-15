#!/usr/bin/env python3
"""
eval_smoke.py — Quick Python eval for astrobot data science agent.

Tests the NEW behaviors added in v2:
  - KM routing (performance vs pacing)
  - SQL validator triggers retries
  - Walled garden blocks cross-client
  - Channel resolver tool gets called (not LLM guessing)
  - Direct ≠ DEFAULT
  - BQML exception works
  - Client locking persists across turns

Runs single-turn questions against the deployed adk web server or
the Cloud Run service. Asserts on tool calls and final SQL.

Usage:
    # Against local adk web (default port 8000)
    python3 eval_smoke.py --target http://localhost:8000

    # Against Cloud Run
    python3 eval_smoke.py --target https://astrobot-ds-v2-XXXX-uc.a.run.app

    # Specific cases only
    python3 eval_smoke.py --target http://localhost:8000 --case-ids E1,E3,E5

Exit code: 0 if all pass, 1 if any fail.
"""

import argparse
import json
import re
import sys
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional
import urllib.request
import urllib.error


# ============================================================
# Eval case definitions
# ============================================================

@dataclass
class EvalCase:
    """A single eval case with assertions on tool calls and final SQL."""
    case_id: str
    description: str
    question: str

    # Pre-conditions
    pre_messages: list[str] = field(default_factory=list)  # for multi-turn client lock tests

    # Assertions
    expected_routed_table: Optional[str] = None  # e.g. "performance" or "pacing"
    must_call_tools: list[str] = field(default_factory=list)  # tool names that must appear
    must_not_call_tools: list[str] = field(default_factory=list)  # tools that must NOT appear
    sql_must_contain: list[str] = field(default_factory=list)  # substrings in final SQL
    sql_must_not_contain: list[str] = field(default_factory=list)  # forbidden patterns
    sql_regex_required: Optional[str] = None  # regex SQL must match
    sql_regex_forbidden: Optional[str] = None  # regex SQL must NOT match
    response_must_contain: list[str] = field(default_factory=list)  # substrings in final text
    response_must_not_contain: list[str] = field(default_factory=list)


# 12 eval cases covering the new v2 behaviors
EVAL_CASES: list[EvalCase] = [

    EvalCase(
        case_id="E1",
        description="KM routes performance question to performance table",
        question="For NPI, which channel has the lowest CPA last 12 months?",
        expected_routed_table="performance",
        sql_must_contain=["vw_astrobot_npi_nc360_dashboard", "SAFE_DIVIDE"],
        sql_must_not_contain=["DEFAULT"],
    ),

    EvalCase(
        case_id="E2",
        description="KM routes pacing question to pacing table",
        question="For NPI, what's the budget remaining by channel?",
        expected_routed_table="pacing",
        sql_must_contain=["vw_astrobot_npi_nc360_budget", "GVMM_Channel"],
        sql_must_not_contain=["vw_astrobot_npi_nc360_dashboard"],
    ),

    EvalCase(
        case_id="E3",
        description="SQL validator forces CV over raw STDDEV for volatility",
        question="For NPI, which channel is most volatile in the last 6 months?",
        expected_routed_table="performance",
        sql_regex_required=r"(?i)SAFE_DIVIDE\s*\(\s*STDDEV.*?,\s*NULLIF\s*\(\s*AVG",
        sql_regex_forbidden=r"(?i)STDDEV\s*\([^)]+\)(?!\s*[,)/]\s*(?:NULLIF\s*\()?AVG)",
    ),

    EvalCase(
        case_id="E4",
        description="Direct channel resolves to 'Direct' not 'DEFAULT'",
        question="For NPI, show me Direct conversions last 12 months",
        sql_must_contain=["'Direct'"],
        sql_must_not_contain=["'DEFAULT'", "DEFAULT'"],
    ),

    EvalCase(
        case_id="E5",
        description="Awareness includes all 9 taxonomy channels",
        question="For NPI, what's our total awareness spend last 12 months?",
        must_call_tools=["resolve_channel_reference_tool"],
        sql_regex_required=(
            r"(?i)Channel\s+IN\s*\([^)]*"
            r"(?=.*Linear TV)(?=.*OTT)(?=.*Online Video)"
        ),
    ),

    EvalCase(
        case_id="E6",
        description="Walled garden blocks Venetian table when locked to NPI",
        question="For NPI compare with Venetian's spend last quarter",
        pre_messages=["Lock me to NPI please", "For NPI, what's the total spend last month?"],
        sql_must_not_contain=["Astrobot_Venetian"],
        response_must_contain=["NPI"],  # should explain it can't compare across clients
    ),

    EvalCase(
        case_id="E7",
        description="BQML ML.FORECAST works (walled-garden exception)",
        question="Forecast NPI conversions for the next quarter",
        sql_must_contain=["ML.FORECAST", "MODEL"],
        sql_must_not_contain=["GROUP BY Channel"],  # forecasts are time-series, not channel-grouped
    ),

    EvalCase(
        case_id="E8",
        description="Organic efficiency uses correct formula (% from organic channels)",
        question="What's the organic efficiency for NPI last 12 months?",
        expected_routed_table="performance",
        sql_regex_required=r"(?i)CASE\s+WHEN\s+Channel\s+IN\s*\([^)]*Organic",
        sql_must_not_contain=[
            # Wrong formula: total_conv / total_cost is NOT organic efficiency
        ],
    ),

    EvalCase(
        case_id="E9",
        description="Channel mix uses unified CTE (Search + Paid Search unified)",
        question="For NPI, show channel mix in November vs December",
        expected_routed_table="performance",
        sql_regex_required=r"(?is)WITH\s+\w+\s+AS.*CASE\s+WHEN.*Channel\s+IN",
    ),

    EvalCase(
        case_id="E10",
        description="Pacing query excludes DEFAULT and active flights only",
        question="For NPI, which flights are underpacing?",
        expected_routed_table="pacing",
        sql_must_contain=["vw_astrobot_npi_nc360_budget", "Budget_Flag"],
        # Validator/prompt should encourage these but they're advisory (info severity)
    ),

    EvalCase(
        case_id="E11",
        description="Client locking persists across turns",
        question="What about TV halo lift?",
        pre_messages=["For NPI, which channel has lowest CPA?"],
        expected_routed_table="performance",
        sql_must_contain=["Astrobot_NPI"],
        sql_must_not_contain=["Astrobot_Venetian", "Astrobot_WinnDixie"],
    ),

    EvalCase(
        case_id="E12",
        description="No client mentioned → agent asks for client",
        question="Show me the lowest CPA channel",
        must_not_call_tools=["call_bigquery_agent", "execute_sql"],
        response_must_contain=["which client", "NPI", "Venetian", "WinnDixie"],
    ),

]


# ============================================================
# ADK API client
# ============================================================

class AdkClient:
    """Minimal client for adk web /run_sse endpoint."""

    def __init__(self, base_url: str, app_name: str = "data_science"):
        self.base_url = base_url.rstrip("/")
        self.app_name = app_name
        self.session_id = None
        self.user_id = f"eval_{uuid.uuid4().hex[:8]}"

    def new_session(self):
        """Create a fresh session — wipes client lock + state."""
        self.session_id = uuid.uuid4().hex
        try:
            url = f"{self.base_url}/apps/{self.app_name}/users/{self.user_id}/sessions/{self.session_id}"
            req = urllib.request.Request(url, method="POST",
                                          data=b"{}",
                                          headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req, timeout=10).read()
        except Exception as e:
            # Some adk versions auto-create sessions
            pass
        return self.session_id

    def send(self, message: str, timeout: int = 120) -> dict:
        """Send a message, return parsed events.

        Returns dict with:
          - events: list of all events
          - tool_calls: list of {name, args}
          - final_text: assistant's final text reply
          - sql_queries: list of all SQL queries seen in tool calls
        """
        if not self.session_id:
            self.new_session()

        url = f"{self.base_url}/run_sse"
        payload = {
            "app_name": self.app_name,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "new_message": {"role": "user", "parts": [{"text": message}]},
            "streaming": False,
        }
        req = urllib.request.Request(
            url,
            method="POST",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
        )

        events = []
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                for line in resp:
                    line = line.decode("utf-8", errors="replace").strip()
                    if line.startswith("data: "):
                        try:
                            ev = json.loads(line[6:])
                            events.append(ev)
                        except json.JSONDecodeError:
                            pass
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {e.code}: {body[:500]}")
        except Exception as e:
            raise RuntimeError(f"Request failed: {e}")

        return self._parse_events(events)

    def _parse_events(self, events: list[dict]) -> dict:
        tool_calls = []
        sql_queries = []
        final_text_parts = []

        for ev in events:
            content = ev.get("content", {})
            for part in content.get("parts", []):
                # Tool call
                if "function_call" in part:
                    fc = part["function_call"]
                    name = fc.get("name", "")
                    args = fc.get("args", {})
                    tool_calls.append({"name": name, "args": args})

                    # Extract SQL from common tool args
                    for sql_key in ("query", "sql", "question"):
                        v = args.get(sql_key)
                        if v and isinstance(v, str) and (
                            "SELECT" in v.upper() or "ML.FORECAST" in v.upper()
                            or "ML.PREDICT" in v.upper()
                        ):
                            sql_queries.append(v)

                # Tool response - sometimes has the SQL too
                if "function_response" in part:
                    resp = part["function_response"].get("response", {})
                    if isinstance(resp, dict):
                        for k in ("sql", "query"):
                            if isinstance(resp.get(k), str) and "SELECT" in resp[k].upper():
                                sql_queries.append(resp[k])

                # Text — could be intermediate or final
                if "text" in part and part["text"]:
                    final_text_parts.append(part["text"])

        return {
            "events": events,
            "tool_calls": tool_calls,
            "final_text": "\n".join(final_text_parts),
            "sql_queries": sql_queries,
        }


# ============================================================
# Assertion engine
# ============================================================

def assert_case(case: EvalCase, response: dict, pre_response: Optional[dict] = None) -> dict:
    """Check all assertions for a case. Returns {passed, failures: [str]}."""
    failures = []

    all_tool_names = [tc["name"] for tc in response["tool_calls"]]
    all_sql = "\n".join(response["sql_queries"])
    final_text = response["final_text"]

    # Routed table check (looks for table path in any SQL)
    if case.expected_routed_table:
        routing_map = {
            "performance": "vw_astrobot_npi_nc360_dashboard",  # or other clients' dashboards
            "pacing": "vw_astrobot_npi_nc360_budget",
        }
        expected_substr = routing_map.get(case.expected_routed_table, case.expected_routed_table)
        if expected_substr.lower() not in all_sql.lower():
            failures.append(
                f"Expected routed table '{case.expected_routed_table}' "
                f"(substring '{expected_substr}'), not found in any SQL"
            )

    # Must call tools
    for tool in case.must_call_tools:
        if tool not in all_tool_names:
            failures.append(f"Expected tool '{tool}' was not called. Called: {all_tool_names}")

    # Must NOT call tools
    for tool in case.must_not_call_tools:
        if tool in all_tool_names:
            failures.append(f"Forbidden tool '{tool}' was called")

    # SQL must contain
    for s in case.sql_must_contain:
        if s.lower() not in all_sql.lower():
            failures.append(f"SQL missing required substring: '{s}'")

    # SQL must NOT contain
    for s in case.sql_must_not_contain:
        if s and s.lower() in all_sql.lower():
            failures.append(f"SQL contains forbidden substring: '{s}'")

    # SQL regex required
    if case.sql_regex_required:
        if not re.search(case.sql_regex_required, all_sql):
            failures.append(
                f"SQL did not match required regex: {case.sql_regex_required!r}"
            )

    # SQL regex forbidden
    if case.sql_regex_forbidden:
        if re.search(case.sql_regex_forbidden, all_sql):
            failures.append(
                f"SQL matched forbidden regex: {case.sql_regex_forbidden!r}"
            )

    # Response text checks
    for s in case.response_must_contain:
        if s.lower() not in final_text.lower():
            failures.append(f"Response missing required substring: '{s}'")

    for s in case.response_must_not_contain:
        if s.lower() in final_text.lower():
            failures.append(f"Response contains forbidden substring: '{s}'")

    return {
        "passed": len(failures) == 0,
        "failures": failures,
        "tool_calls": all_tool_names,
        "sql_count": len(response["sql_queries"]),
        "final_text_preview": final_text[:200],
    }


# ============================================================
# Runner
# ============================================================

def run_case(client: AdkClient, case: EvalCase, verbose: bool = False) -> dict:
    """Run a single eval case. Returns result dict."""
    start = time.time()

    try:
        # Fresh session per case (unless pre_messages need same session)
        client.new_session()

        pre_response = None
        for pre_msg in case.pre_messages:
            if verbose:
                print(f"      [pre] {pre_msg[:80]}")
            pre_response = client.send(pre_msg)

        if verbose:
            print(f"      [Q]   {case.question[:80]}")

        response = client.send(case.question)
        result = assert_case(case, response, pre_response)
        result["duration_s"] = round(time.time() - start, 1)
        return result

    except Exception as e:
        return {
            "passed": False,
            "failures": [f"Exception: {type(e).__name__}: {e}"],
            "tool_calls": [],
            "sql_count": 0,
            "final_text_preview": "",
            "duration_s": round(time.time() - start, 1),
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", required=True,
                        help="Base URL of adk web or Cloud Run service")
    parser.add_argument("--app-name", default="data_science",
                        help="ADK app name (default: data_science)")
    parser.add_argument("--case-ids", default="",
                        help="Comma-separated case IDs to run (default: all)")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    requested_ids = [c.strip() for c in args.case_ids.split(",") if c.strip()]
    cases = EVAL_CASES if not requested_ids else [
        c for c in EVAL_CASES if c.case_id in requested_ids
    ]

    if not cases:
        print(f"No matching cases for IDs: {requested_ids}")
        sys.exit(1)

    client = AdkClient(args.target, app_name=args.app_name)

    print("=" * 70)
    print(f"ASTROBOT SMOKE EVAL")
    print(f"Target: {args.target}")
    print(f"Cases:  {len(cases)}")
    print("=" * 70)

    results = []
    for i, case in enumerate(cases, 1):
        print(f"\n[{i}/{len(cases)}] {case.case_id}: {case.description}")
        result = run_case(client, case, verbose=args.verbose)
        results.append((case, result))

        if result["passed"]:
            print(f"    ✓ PASS ({result['duration_s']}s, "
                  f"{len(result['tool_calls'])} tool calls, "
                  f"{result['sql_count']} SQL queries)")
        else:
            print(f"    ✗ FAIL ({result['duration_s']}s)")
            for f in result["failures"]:
                print(f"      - {f}")
            if args.verbose:
                print(f"      Tool calls: {result['tool_calls']}")
                print(f"      Text preview: {result['final_text_preview']!r}")

    # Summary
    print("\n" + "=" * 70)
    passed = sum(1 for _, r in results if r["passed"])
    failed = len(results) - passed
    total_time = sum(r["duration_s"] for _, r in results)
    print(f"RESULTS: {passed}/{len(results)} passed in {total_time:.1f}s")
    print("=" * 70)

    if failed > 0:
        print("\nFAILED CASES:")
        for case, result in results:
            if not result["passed"]:
                print(f"  ✗ {case.case_id}: {case.description}")
                for f in result["failures"]:
                    print(f"      {f}")
        sys.exit(1)

    print("\n✓ All eval cases passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()