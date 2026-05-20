# Copyright 2025 Google LLC (Apache 2.0)
"""
Data Scientist Agent — NL2SQL + NL2Py + BQML.

- Integrates KnowledgeManager (Option A) for routing + channel resolution
- Keeps CHASE-SQL in charge of NL→SQL translation (no query rewriting)
- AC-5 walled-garden check to prevent cross-client data access
- AC-3 dry-run validation for syntax/cost checks
- 6 ADK callbacks for full observability
"""

import base64
import hashlib
import json
import logging
import math
import os
import re
from datetime import date
from typing import Any, Optional

from google.adk.agents import LlmAgent
from google.adk.code_executors import VertexAiCodeExecutor
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools import BaseTool, ToolContext
from google.genai import types

from .prompts import return_instructions_root
from .sub_agents import bqml_agent
from .sub_agents.bigquery.tools import (
    get_database_settings as get_bq_database_settings,
)
from .tools import call_analytics_agent, call_bigquery_agent

# ── KnowledgeManager (Option A — facade over v3 config + lib/) ───────────────
try:
    from .utils.knowledge_manager import manager as km
    _KM_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"KnowledgeManager not available: {e}")
    km = None
    _KM_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
_logger = logging.getLogger(__name__)


# ── Global NaN/Infinity JSON sanitization ────────────────────────────────────
def _global_nan_fix():
    """Patch JSON serialization to never emit NaN/Infinity, preventing 400 errors."""
    _original_dumps = json.dumps
    _original_dump = json.dump

    def _replace_nan(obj):
        if isinstance(obj, dict):
            return {k: _replace_nan(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_replace_nan(v) for v in obj]
        if isinstance(obj, tuple):
            return tuple(_replace_nan(v) for v in obj)
        if isinstance(obj, float):
            if math.isnan(obj) or math.isinf(obj):
                return None
        return obj

    def safe_dumps(obj, *args, **kwargs):
        kwargs["allow_nan"] = False
        return _original_dumps(_replace_nan(obj), *args, **kwargs)

    def safe_dump(obj, fp, *args, **kwargs):
        kwargs["allow_nan"] = False
        return _original_dump(_replace_nan(obj), fp, *args, **kwargs)

    json.dumps = safe_dumps
    json.dump = safe_dump
    _logger.info("✅ Global NaN/Infinity JSON sanitizer installed")


_global_nan_fix()


# ── Argument Size Guard ──────────────────────────────────────────────────────
_MAX_FUNCTION_ARG_SIZE = 6000


def _enforce_arg_size(arg_str):
    """Truncates large function arguments to prevent MALFORMED_FUNCTION_CALL crashes."""
    if not arg_str or not isinstance(arg_str, str) or len(arg_str) <= _MAX_FUNCTION_ARG_SIZE:
        return arg_str
    _logger.warning(f"[ARG GUARD] Truncating large argument ({len(arg_str)} chars)")
    return arg_str[:_MAX_FUNCTION_ARG_SIZE] + " ... [TRUNCATED]"


# ── Config & Constants ───────────────────────────────────────────────────────
_PROJECT_ID = os.getenv("BQ_DATA_PROJECT_ID", "nc-ai-chatbot")
_MAX_SQL_RETRIES = 3

# Fallback table map if KM unavailable — loaded dynamically from config
def _build_client_table_map() -> dict:
    """Build fallback table map from Firestore/JSON config at runtime."""
    try:
        from data_science.lib.channel_resolver import load_config_v3
        cfg = load_config_v3()
        result = {}
        for d in cfg.get("datasets", []):
            cid = d.get("client_id")
            for t in d.get("tables", []):
                if t.get("table_id") == "performance":
                    path = t.get("table_full_path")
                    if cid and path:
                        result[cid] = path
        return result
    except Exception as e:
        _logger.warning(f"Could not build client table map from config: {e}")
        return {}
_CLIENT_TABLE_MAP = _build_client_table_map()

# Metric hints for the BQ sub-agent
_CHASE_SQL_METRIC_MAP = {
    "spend":       "SUM(Cost)",
    "cost":        "SUM(Cost)",
    "cpa":         "SAFE_DIVIDE(SUM(Cost), NULLIF(SUM(Conversions), 0))",
    "ctr":         "SAFE_DIVIDE(SUM(Clicks), NULLIF(SUM(Impressions), 0))",
    "conversions": "SUM(Conversions)",
    "roas":        "SAFE_DIVIDE(SUM(Revenue), NULLIF(SUM(Cost), 0))",
}

# Allowed BQML / metadata operations that don't reference client tables directly
_ALLOWED_NON_TABLE_PATTERNS = [
    "ml.predict", "ml.evaluate", "ml.forecast", "ml.feature_info",
    "ml.training_info", "information_schema",
]

_dataset_config = {}
_database_settings = {}


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _get_table_for_client(client_id: str, table_id: str = "performance") -> str:
    """Get fully-qualified table path. Prefers KM v3 config, falls back to hardcoded map."""
    if _KM_AVAILABLE and km is not None:
        try:
            for d in km.data.get("datasets", []):
                if d["client_id"] == client_id:
                    for t in d.get("tables", []):
                        if t["table_id"] == table_id:
                            return t["table_full_path"]
        except Exception as e:
            _logger.warning(f"KM table lookup failed for {client_id}: {e}")
    return _CLIENT_TABLE_MAP.get(client_id, "")


def _get_all_client_tables() -> dict:
    """Return {client_id: [table_paths]} for all clients across all tables."""
    if _KM_AVAILABLE and km is not None:
        try:
            result = {}
            for d in km.data.get("datasets", []):
                cid = d["client_id"]
                result[cid] = [t["table_full_path"].lower() for t in d.get("tables", [])]
            return result
        except Exception as e:
            _logger.warning(f"KM all-tables lookup failed: {e}")
    return {cid: [path.lower()] for cid, path in _CLIENT_TABLE_MAP.items()}


def _detect_client_from_text(text: str) -> Optional[str]:
    """Detect client mention in user text using KM client list when available."""
    if not text:
        return None
    text_low = text.lower()

    if _KM_AVAILABLE and km is not None:
        for client_id in km.list_clients():
            if client_id.lower() in text_low:
                return client_id

    # Fallback: try config-loaded client list when KM unavailable
    try:
        from data_science.lib.channel_resolver import load_config_v3 as _lcv3
        for d in _lcv3().get("datasets", []):
            cid = d.get("client_id", "")
            if cid and cid.lower() in text_low:
                return cid
            # Check aliases from client config if present
            for alias in d.get("aliases", []):
                if alias.lower() in text_low:
                    return cid
    except Exception:
        pass
    return None


# ══════════════════════════════════════════════════════════════════════════════
# AC-5: WALLED GARDEN
# ══════════════════════════════════════════════════════════════════════════════

def _ac5_walled_garden_check(sql: str, client_id: str) -> tuple[bool, str]:
    """Validates that SQL only queries the correct client's tables."""
    if not client_id:
        return False, "No client_id locked in session — cannot validate SQL."

    sql_lower = sql.lower()
    is_allowed_non_table_op = any(p in sql_lower for p in _ALLOWED_NON_TABLE_PATTERNS)

    if not is_allowed_non_table_op:
        if "select *" in sql_lower and "limit" not in sql_lower:
            return False, "Use explicit column names or add LIMIT — SELECT * without LIMIT is blocked."

    all_client_tables = _get_all_client_tables()
    correct_tables = all_client_tables.get(client_id, [])

    for other_cid, other_tables in all_client_tables.items():
        if other_cid == client_id:
            continue
        for other_table in other_tables:
            dataset_part = other_table.split(".")[-2] if "." in other_table else other_table
            if dataset_part and dataset_part in sql_lower:
                return False, (
                    f"Cross-client violation: SQL references {other_cid}'s "
                    f"dataset ({dataset_part}) while session is locked to {client_id}."
                )

    if not is_allowed_non_table_op:
        touches_correct_table = False
        for correct_table in correct_tables:
            table_short = ".".join(correct_table.split(".")[-2:])
            if table_short.lower() in sql_lower or correct_table in sql_lower:
                touches_correct_table = True
                break
        if not touches_correct_table:
            return False, (
                f"SQL must reference {client_id}'s table. "
                f"Expected one of: {correct_tables}"
            )

    return True, ""


# ══════════════════════════════════════════════════════════════════════════════
# AC-3: DRY-RUN SQL VALIDATION
# ══════════════════════════════════════════════════════════════════════════════

def _ac3_dry_run(sql: str) -> tuple[bool, str]:
    """Submit SQL to BigQuery dry-run API. Returns (is_valid, error_message)."""
    try:
        from google.cloud import bigquery
        bq = bigquery.Client(project=_PROJECT_ID)
        job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
        bq.query(sql, job_config=job_config)
        return True, ""
    except Exception as e:
        return False, str(e)


# ══════════════════════════════════════════════════════════════════════════════
# CALLBACKS
# ══════════════════════════════════════════════════════════════════════════════



# ── Auto-onboarding helpers (local-only; Cloud Run filesystem is ephemeral) ──

_AUTO_ONBOARD_NOISE_WORDS = frozenset({
    "Date", "Channel", "Cost", "Conversions", "Click", "Clicks", "Impression",
    "Impressions", "Revenue", "Spend", "Budget", "Total", "December", "November",
    "October", "September", "August", "July", "June", "May", "April", "March",
    "February", "January", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
    "Saturday", "Sunday", "Q1", "Q2", "Q3", "Q4", "YTD", "MTD", "WTD", "Yesterday",
    "Today", "Tomorrow", "Search", "Social", "Video", "Display", "Email", "Linear",
    "CTV", "OTT", "OOH", "TV", "I", "ID", "URL", "API", "SQL", "BigQuery",
    "Google", "Facebook", "Meta", "Bing", "Yahoo",
})

_AUTO_ONBOARD_INTENT_WORDS = frozenset({
    "show", "pull", "get", "for", "about", "fetch", "display", "list",
    "report", "analyze", "compare", "rank", "top", "data",
})


def _looks_like_client_name(word: str) -> bool:
    """Conservative check: is this word a plausible client identifier?"""
    if len(word) < 3:
        return False
    if word in _AUTO_ONBOARD_NOISE_WORDS:
        return False
    if not word[0].isupper():
        return False
    if not word.isalnum() and "-" not in word and "_" not in word:
        return False
    return True


def _user_text_has_intent(text: str) -> bool:
    """Did the user say something that suggests fetching/showing data?"""
    text_lower = text.lower()
    return any(w in text_lower.split() for w in _AUTO_ONBOARD_INTENT_WORDS)


def _attempt_auto_onboard(user_text: str, state: dict) -> Optional[str]:
    """
    Try to auto-onboard an unknown client name from user text.
    Returns the new client_id if successful, None otherwise.

    Local-only — Cloud Run filesystem doesn't persist these writes.
    Skipped silently in production. Used for dev demos.
    """
    if not _user_text_has_intent(user_text):
        return None

    # Pull capitalized words that aren't noise
    candidates = []
    for raw_word in user_text.split():
        # Strip common punctuation
        word = raw_word.strip(".,;:!?'\"()")
        if _looks_like_client_name(word):
            candidates.append(word)
    if not candidates:
        return None

    # Cache previously-failed lookups for this session
    failed = state.setdefault("_auto_onboard_failed", [])

    for candidate in candidates:
        if candidate in failed:
            continue
        try:
            from .utils.bq_introspector import auto_onboard_client
        except ImportError:
            return None

        try:
            result = auto_onboard_client(candidate)
        except Exception as e:
            _logger.warning(f"Auto-onboard error for {candidate!r}: {e}")
            failed.append(candidate)
            continue

        if result["status"] in ("added", "exists"):
            _logger.info(
                f"🆕 AUTO-ONBOARD: client {candidate!r} discovered "
                f"({len(result.get('tables_added', []))} tables added)"
            )
            # Refresh KM cache so the new client is visible
            if _KM_AVAILABLE and km is not None:
                try:
                    km.refresh_config()
                except Exception as e:
                    _logger.warning(f"KM refresh failed: {e}")
            return candidate
        else:
            failed.append(candidate)

    return None


def before_agent_callback(
    callback_context: CallbackContext,
) -> Optional[types.Content]:
    """Initialize session state, lock client, inject KnowledgeManager context."""
    state = callback_context.state

    # ── 1. Initialize state on first request ──
    if "database_settings" not in state:
        state["database_settings"] = _database_settings
        state["client_lock"] = None
        state["client_id"] = None
        state["LOCKED_CLIENT_FILTER"] = None
        state["client_filter_value"] = None
        state["_sql_retry_count"] = 0
        state["_seen_hashes"] = []
        _logger.info("Session initialized — awaiting client selection")

    # Reset per-request state
    state["_chart_steps_done"] = 0
    state["_multi_step_mode"] = False
    state["_sql_retry_count"] = 0

    # ── 2. Extract user text from session events ──
    user_text = ""
    try:
        session = callback_context._invocation_context.session
        for event in reversed(session.events):
            if event.author == "user" and event.content:
                parts = event.content.parts or []
                for p in parts:
                    if getattr(p, "text", None):
                        user_text = p.text
                        break
                if user_text:
                    break
    except Exception as e:
        _logger.warning(f"Could not extract user text from session: {e}")

    state["_last_user_question"] = user_text

    # ── 3. Client detection & locking ──
    detected_cid = _detect_client_from_text(user_text)

    # If no client detected and user seems to want data, try auto-onboarding (local-only)
    if not detected_cid and user_text and not state.get("client_lock"):
        try:
            onboarded = _attempt_auto_onboard(user_text, state)
            if onboarded:
                detected_cid = onboarded
                state["_auto_onboarded_this_request"] = onboarded
        except Exception as e:
            _logger.warning(f"Auto-onboard attempt failed: {e}")

    # AC-5 STATE LOCK CHECK — use callback_context.state directly (not ctx)
    locked_cid = state.get("client_lock") or state.get("LOCKED_CLIENT")
    if locked_cid and user_text:
        try:
            from data_science.lib.channel_resolver import load_config_v3 as _lcv3
            all_clients = [d.get("client_id") for d in _lcv3().get("datasets", []) if d.get("client_id")]
        except Exception:
            all_clients = list(_CLIENT_TABLE_MAP.keys())
        question_lower = user_text.lower()
        for other in all_clients:
            if other.lower() == locked_cid.lower():
                continue
            if other.lower() in question_lower:
                refusal_msg = (
                    f"This session is locked to {locked_cid}. I cannot show data "
                    f"for {other}. To switch clients, please start a new session."
                )
                state["_walled_garden_refused"] = True
                state["_disabled_table_message"] = refusal_msg
                _logger.warning(
                    f"AC-5 WALLED-GARDEN: refused cross-client question. "
                    f"locked={locked_cid}, requested={other}"
                )
                # Return a hard block — returning Content stops the agent from running
                return types.Content(
                    role="model",
                    parts=[types.Part(text=refusal_msg)]
                )

    locked_cid = state.get("client_lock")

    if not locked_cid and detected_cid:
        state["client_lock"] = detected_cid
        state["client_id"] = detected_cid
        # Also resolve and store the SQL filter value (e.g. "SEG" for WinnDixie)
        try:
            from .lib.channel_resolver import get_client_filter_value
            _filter_val = get_client_filter_value(detected_cid)
        except Exception:
            _filter_val = detected_cid
        state["client_filter_value"] = _filter_val
        state["LOCKED_CLIENT_FILTER"] = _filter_val
        state["LOCKED_CLIENT"] = detected_cid
        locked_cid = detected_cid
        _logger.info(f"🔒 Session LOCKED to client: {detected_cid}")
    elif locked_cid and detected_cid and detected_cid != locked_cid:
        state["_cross_client_blocked"] = detected_cid
        _logger.warning(
            f"🚫 Cross-client attempt: {detected_cid} while locked to {locked_cid}"
        )
    elif not locked_cid and not detected_cid:
        state["_must_ask_client"] = True
        _logger.info("⚠️ No client detected — agent will ask user")
    else:
        state["_must_ask_client"] = False
        if state.get("_cross_client_blocked"):
            state["_cross_client_blocked"] = None

    if locked_cid:
        state["LOCKED_CLIENT"] = locked_cid
        state["client_id"] = locked_cid
        # Also resolve and store the SQL filter value (e.g. "SEG" for WinnDixie)
        try:
            from .lib.channel_resolver import get_client_filter_value
            _filter_val = get_client_filter_value(locked_cid)
        except Exception:
            _filter_val = locked_cid
        state["client_filter_value"] = _filter_val
        state["LOCKED_CLIENT_FILTER"] = _filter_val

    # ── 4. KnowledgeManager context injection ──
    if _KM_AVAILABLE and km is not None and locked_cid and user_text:
        try:
            ctx = km.route_and_load_context(user_text, locked_cid)
            for k, v in ctx.items():
                state[k] = v
            _logger.info(
                f"📍 KM routed '{user_text[:50]}...' → "
                f"table={ctx['routed_table_id']} (confidence={ctx['routing_confidence']})"
            )
        except Exception as e:
            _logger.warning(f"KM routing error: {e}")
            state["routing_error"] = str(e)

    # ── 5. Inject models list ──
    if locked_cid and state.get("_models_listed_for") != locked_cid:
        try:
            from .sub_agents.bigquery.tools import get_models_summary_for_prompt
            models_summary = get_models_summary_for_prompt(locked_cid)
            state["available_models_summary"] = models_summary
            state["_models_listed_for"] = locked_cid
            _logger.info(f"📋 Models listed for {locked_cid}: {len(models_summary)} chars")
        except Exception as e:
            _logger.warning(f"Could not list models for {locked_cid}: {e}")

    return None


def after_agent_callback(callback_context: CallbackContext) -> Optional[types.Content]:
    """Cleanup at end of agent turn."""
    state = callback_context.state
    state["_sql_retry_count"] = 0
    state["_seen_hashes"] = []
    state["_chart_steps_done"] = 0
    state["_last_bq_hash"] = ""
    return None


def before_tool_callback(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
) -> Optional[dict]:
    """Inject hints, validate SQL, guard argument sizes."""
    state = tool_context.state
    client_id = state.get("client_id") or state.get("client_lock") or state.get("LOCKED_CLIENT")
    tool_name = getattr(tool, "name", None) or getattr(tool, "__name__", str(tool))

    # ── Inject hints for call_bigquery_agent ──
    if tool_name == "call_bigquery_agent":
        q = args.get("question", "") or args.get("query", "")
        if q:
            hints = [
                f"{metric} → {expr}"
                for metric, expr in _CHASE_SQL_METRIC_MAP.items()
                if metric in q.lower()
            ]
            prefix_parts = [f"[CHASE-SQL][Client: {client_id}]"]
            routed_table = state.get("routed_table_path") or _get_table_for_client(client_id)
            if routed_table:
                prefix_parts.append(f"[Table: {routed_table}]")
            channel_col = state.get("channel_column", "Channel")
            kpi_col = state.get("kpi_column", "Conversions")
            prefix_parts.append(f"[Channel col: {channel_col}, KPI col: {kpi_col}]")
            if hints:
                prefix_parts.append(f"[Metric expr hints: {', '.join(hints)}]")
            prefix = "\n".join(prefix_parts) + "\n\n"
            if "question" in args:
                args["question"] = _enforce_arg_size(prefix + q)
            elif "query" in args:
                args["query"] = _enforce_arg_size(prefix + q)
        return None

    # ── execute_sql: AC-5 + AC-3 ──
    if tool_name == "execute_sql":
        sql = args.get("query", "") or args.get("sql", "")
        if not sql:
            return None

        safe, walled_err = _ac5_walled_garden_check(sql, client_id)
        if not safe:
            _logger.error(f"AC-5 BLOCKED: {walled_err}")
            return {
                "status": "SECURITY_VIOLATION",
                "error": walled_err,
                "instruction": (
                    f"Security check blocked this SQL: {walled_err} "
                    f"Regenerate the SQL using only {client_id}'s table."
                ),
            }

        valid, dry_run_err = _ac3_dry_run(sql)
        if not valid:
            retry = state.get("_sql_retry_count", 0) + 1
            state["_sql_retry_count"] = retry
            if retry > _MAX_SQL_RETRIES:
                _logger.error(f"SQL failed dry-run after {_MAX_SQL_RETRIES} retries.")
                return {
                    "status": "ERROR",
                    "error": f"SQL failed after {_MAX_SQL_RETRIES} attempts. Last error: {dry_run_err[:300]}",
                }
            _logger.warning(f"SQL dry-run failed (retry {retry}): {dry_run_err[:150]}")
            return {
                "status": "DRY_RUN_FAILED",
                "dry_run_error": dry_run_err,
                "instruction": (
                    f"The SQL failed BigQuery dry-run validation. Error: {dry_run_err[:300]}. "
                    "Regenerate the SQL with the fix."
                ),
            }
        state["_sql_retry_count"] = 0

    # ── Argument size guard ──
    for k, v in list(args.items()):
        if isinstance(v, str):
            args[k] = _enforce_arg_size(v)

    return None


def after_tool_callback(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
    tool_response: Any,
) -> Any:
    """Capture results in state; sanitize NaN values; capture SQL for narration."""
    tool_name = getattr(tool, "name", None) or getattr(tool, "__name__", str(tool))

    if tool_name == "call_bigquery_agent":
        tool_context.state["bigquery_query_result"] = tool_response
    elif tool_name == "execute_sql":
        # Item 9: mirror SQL capture at root layer (defense in depth — the
        # sub-agent callback also writes this; root layer write makes the
        # field reliably readable from the root prompt's state substitution).
        sql_arg = args.get("query") or args.get("sql") or ""
        if sql_arg:
            tool_context.state["last_executed_sql"] = sql_arg

        if isinstance(tool_response, dict) and tool_response.get("status") == "SUCCESS":
            rows = tool_response.get("rows")
            if rows:
                try:
                    sanitized = json.loads(json.dumps(rows))
                    tool_context.state["bigquery_query_result"] = sanitized
                    tool_response["rows"] = sanitized
                except Exception:
                    tool_context.state["bigquery_query_result"] = rows

    return None


# Item 1: Steps narration SQL replacement.
# Matches a "Steps:" / "**Steps:**" header followed by a "Generated SQL:" line
# followed by a fenced code block (```sql ... ``` or ``` ... ```).
# Captures the fenced SQL so we can swap it with state["last_executed_sql"].
_STEPS_SQL_RE = re.compile(
    r"(?P<prefix>(?:\*\*Steps:?\*\*|Steps:).*?(?:Generated SQL|generated SQL)[:\s]*\n+)"
    r"```(?:sql)?\s*\n"
    r"(?P<sql>.*?)\n"
    r"```",
    re.DOTALL | re.IGNORECASE,
)


def _replace_fabricated_sql_in_text(text: str, real_sql: str) -> tuple[str, int]:
    """Swap any SQL block inside a Steps section with the real SQL from state.

    Args:
        text: LLM response text
        real_sql: state["last_executed_sql"] value (must be non-empty)
    Returns:
        (modified_text, n_replacements)
    """
    n = 0
    def _repl(m: re.Match) -> str:
        nonlocal n
        llm_sql = m.group("sql").strip()
        real = real_sql.strip()
        # Only replace if they actually differ (post-strip).
        if llm_sql == real:
            return m.group(0)
        n += 1
        prefix = m.group("prefix")
        return f"{prefix}```sql\n{real}\n```"
    new_text = _STEPS_SQL_RE.sub(_repl, text)
    return new_text, n


def after_model_callback(
    callback_context: CallbackContext,
    llm_response: Any,
) -> Optional[Any]:
    """Log tokens; replace fabricated SQL in Steps blocks; block duplicate responses."""
    state = callback_context.state

    # Log tokens
    try:
        usage = llm_response.usage_metadata
        if usage:
            _logger.info(
                f"Tokens: In={usage.prompt_token_count}, "
                f"Out={usage.candidates_token_count}"
            )
    except Exception:
        pass

    # ── Item 1: Steps narration SQL replacement ──
    # Only runs if state has a real SQL to inject. State-empty case = rule (α),
    # leave the LLM block alone (first-turn safety).
    real_sql = state.get("last_executed_sql", "")
    if real_sql and isinstance(real_sql, str) and real_sql.strip():
        try:
            # LlmResponse (ADK wrapper) has .content directly, not .candidates
            content = getattr(llm_response, "content", None)
            if content and getattr(content, "parts", None):
                for part in content.parts:
                    if hasattr(part, "text") and part.text:
                        new_text, n_repl = _replace_fabricated_sql_in_text(
                            part.text, real_sql
                        )
                        if n_repl > 0:
                            _logger.info(
                                f"Steps SQL replacement: swapped {n_repl} "
                                f"fabricated SQL block(s) with real SQL "
                                f"({len(real_sql)} chars)"
                            )
                            part.text = new_text
        except Exception as e:
            _logger.warning(f"Steps SQL replacement failed (response untouched): {e}")

    # ── Duplicate response suppression ──
    # If the agent emits the same text twice in one turn (once before chart,
    # once after), suppress the second occurrence.
    try:
        if llm_response.candidates:
            for cand in llm_response.candidates:
                if cand.content and cand.content.parts:
                    for part in cand.content.parts:
                        if hasattr(part, "text") and part.text and len(part.text) > 100:
                            # Normalize: strip timestamps/filenames that change each run
                            normalized = re.sub(r'\d{8,}', '', part.text)
                            normalized = re.sub(r'\s+', ' ', normalized).strip()
                            h = hashlib.md5(normalized[:400].encode()).hexdigest()[:8]
                            seen = state.get("_seen_hashes", [])
                            if h in seen:
                                _logger.warning("Duplicate response blocked: %s", h)
                                # Return empty content to suppress duplicate
                                return types.GenerateContentResponse(candidates=[])
                            state["_seen_hashes"] = (seen + [h])[-5:]
                            break
    except Exception as e:
        _logger.debug(f"Dedup check error: {e}")

    return None


# ══════════════════════════════════════════════════════════════════════════════
# BOOTSTRAP & FACTORY
# ══════════════════════════════════════════════════════════════════════════════

def load_dataset_config():
    """Load v1 dataset config (used for schema definitions in prompt)."""
    path = os.getenv("DATASET_CONFIG_FILE", "")
    if not path:
        _logger.warning("DATASET_CONFIG_FILE not set")
        return {"datasets": []}
    if not os.path.exists(path):
        _logger.warning(f"DATASET_CONFIG_FILE not found at {path}")
        return {"datasets": []}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def init_database_settings(cfg: dict) -> dict:
    """Initialize per-dataset-type settings (currently BigQuery only)."""
    settings = {}
    for dataset in cfg.get("datasets", []):
        if dataset.get("type") == "bigquery":
            try:
                settings["bigquery"] = get_bq_database_settings()
            except Exception as e:
                _logger.warning(f"Could not load BQ database settings: {e}")
                settings["bigquery"] = {"schema": "Schema not loaded."}
    return settings


def _get_dataset_definitions() -> str:
    """Format dataset descriptions and schema for the system prompt."""
    definitions = "\n<DATASETS>\n"
    for dataset in _dataset_config.get("datasets", []):
        dtype = dataset.get("type", "bigquery").upper()
        desc = dataset.get("description", "")
        schema_block = _database_settings.get(dtype.lower(), {}).get("schema", "")
        definitions += f"\n<{dtype}>\n<DESCRIPTION>\n{desc}\n</DESCRIPTION>\n"
        if schema_block:
            definitions += f"<SCHEMA>\n{schema_block}\n</SCHEMA>\n"
        definitions += f"</{dtype}>\n"
    definitions += "\n</DATASETS>\n"
    return definitions


def _build_code_executor():
    """Build VertexAiCodeExecutor only if CODE_INTERPRETER_EXTENSION_NAME is set."""
    ext_name = os.getenv("CODE_INTERPRETER_EXTENSION_NAME", "").strip()
    if not ext_name:
        _logger.info(
            "CODE_INTERPRETER_EXTENSION_NAME not set — running without "
            "VertexAiCodeExecutor. Python analytics will still work via "
            "call_analytics_agent (data interpreter tools)."
        )
        return None
    try:
        return VertexAiCodeExecutor(
            resource_name=ext_name,
            optimize_data_file=True,
            stateful=True,
        )
    except Exception as e:
        _logger.warning(
            f"Could not initialize VertexAiCodeExecutor with "
            f"resource_name={ext_name!r}: {e}. Continuing without it."
        )
        return None


def list_tables_for_client(client_id: str) -> dict:
    """List all tables configured for a given client.

    Use this when the user asks what tables exist for a client (e.g.
    "what tables does NPI have", "list tables for Venetian"). This reads
    from KnowledgeManager directly — does NOT query BigQuery — so it
    returns the agent's actual routing table set, not just whatever
    BQ INFORMATION_SCHEMA happens to have.

    Args:
      client_id: The client identifier (e.g. "NPI", "Venetian", "WinnDixie").

    Returns:
      {
        "status": "ok" | "error",
        "client_id": str,
        "tables": list[dict],   # [{table_id, table_full_path, enabled, _purpose}, ...]
        "table_count": int,
        "message": str,
      }
    """
    if not _KM_AVAILABLE:
        return {
            "status": "error",
            "client_id": client_id,
            "tables": [],
            "table_count": 0,
            "message": "KnowledgeManager unavailable.",
        }
    try:
        table_ids = km.list_tables(client_id)
    except Exception as e:
        return {
            "status": "error",
            "client_id": client_id,
            "tables": [],
            "table_count": 0,
            "message": f"Failed to list tables for {client_id}: {e}",
        }

    # Get full details for each table from the config
    tables_detail = []
    for tid in table_ids:
        try:
            t = km.get_table(client_id, tid) or {}
            tables_detail.append({
                "table_id": t.get("table_id", tid),
                "table_full_path": t.get("table_full_path"),
                "enabled": t.get("enabled", True),  # default True if not set
                "_purpose": t.get("_purpose", ""),
            })
        except Exception:
            tables_detail.append({"table_id": tid, "table_full_path": None,
                                  "enabled": None, "_purpose": ""})

    return {
        "status": "ok",
        "client_id": client_id,
        "tables": tables_detail,
        "table_count": len(tables_detail),
        "message": f"{client_id} has {len(tables_detail)} table(s).",
    }


def get_root_agent() -> LlmAgent:
    """Construct the root LlmAgent with all callbacks wired in."""
    kwargs = dict(
        model=os.getenv("ROOT_AGENT_MODEL", "gemini-2.5-flash"),
        name="data_science_root_agent",
        instruction=return_instructions_root() + _get_dataset_definitions(),
        global_instruction=(
            f"You are a Data Science and Analytics Multi Agent System.\n"
            f"Today's date: {date.today()}"
        ),
        sub_agents=[bqml_agent],
        tools=[call_analytics_agent, call_bigquery_agent, list_tables_for_client],
        before_agent_callback=before_agent_callback,
        after_agent_callback=after_agent_callback,
        before_tool_callback=before_tool_callback,
        after_tool_callback=after_tool_callback,
        after_model_callback=after_model_callback,
        generate_content_config=types.GenerateContentConfig(temperature=0.01),
    )
    code_executor = _build_code_executor()
    if code_executor is not None:
        kwargs["code_executor"] = code_executor
    return LlmAgent(**kwargs)


# Boot sequence
_dataset_config = load_dataset_config()
_database_settings = init_database_settings(_dataset_config)
root_agent = get_root_agent()