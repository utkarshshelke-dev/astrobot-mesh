"""Tool wrappers — bigquery agent + matplotlib chart generation + channel resolver."""
import os
import json
import logging
import hashlib
import time
import io
import re


def _normalize_series_to_dict(series):
    """Coerce 'series' field to dict shape.

    LLMs sometimes emit series as a list of dicts:
        [{"name": "A", "values": [1,2,3]}, ...]
    Or as a list of lists:
        [[1,2,3], [4,5,6]]
    Both must be coerced to:
        {"A": [1,2,3], ...}
    """
    if isinstance(series, dict):
        return series
    if not isinstance(series, list):
        return {}
    if not series:
        return {}
    # List of dicts with 'name'/'values' keys
    if isinstance(series[0], dict):
        out = {}
        for i, item in enumerate(series):
            name = item.get("name") or item.get("label") or f"Series {i+1}"
            vals = item.get("values") or item.get("data") or []
            out[name] = vals
        return out
    # List of lists — make up names
    if isinstance(series[0], list):
        return {f"Series {i+1}": vals for i, vals in enumerate(series)}
    return {}


def _filter_empty_chart_data(values_dict):
    """Remove channels/categories where ALL values are 0 (would render blank)."""
    if not isinstance(values_dict, dict):
        return values_dict
    filtered = {}
    for key, vals in values_dict.items():
        if isinstance(vals, list):
            if any(v not in (0, 0.0, None, "0", "0.0", "0%", "0.00%") for v in vals):
                filtered[key] = vals
        else:
            filtered[key] = vals
    return filtered


def _validate_chart_payload(payload):
    """Sanity-check chart payload before sending to analytics agent."""
    issues = []
    cats = payload.get("categories") or payload.get("labels") or []
    if not cats:
        issues.append("No categories/labels")
    vals_data = payload.get("data")
    if isinstance(vals_data, dict):
        vals = vals_data.get("values") or []
    else:
        vals = payload.get("values") or vals_data or []
    if not vals:
        issues.append("No values/data")
    if vals:
        if isinstance(vals[0], (int, float)):
            if all(v == 0 for v in vals):
                issues.append("All values are zero — chart would be blank")
        elif isinstance(vals[0], list):
            if all(all(v == 0 for v in row) for row in vals):
                issues.append("All values are zero — chart would be blank")
    return issues


from google.adk.tools import ToolContext
from google.adk.tools.agent_tool import AgentTool
from google.genai import types

_logger = logging.getLogger(__name__)
_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "nc-ai-chatbot")


# ============================================================
# NEW: KnowledgeManager-backed channel resolver tool
# ============================================================
try:
    from .utils.knowledge_manager import manager as km
    _KM_AVAILABLE = True
except ImportError as e:
    _logger.warning(f"KnowledgeManager not available in tools: {e}")
    km = None
    _KM_AVAILABLE = False


def resolve_channel_reference_tool(term: str, tool_context: ToolContext) -> dict:
    """
    Resolve a fuzzy channel term to an exact channel list + ready-to-use SQL filter.

    Call this BEFORE writing any WHERE clause that filters by channel category.
    Never guess channel lists yourself.

    Args:
        term: User's term (e.g. "awareness", "organic", "direct response", "TV")
        tool_context: ADK tool context (provides access to state)

    Returns:
        dict with:
          - channels: list of exact Channel values to filter on
          - sql_filter: ready-to-paste SQL fragment (e.g. "Channel IN ('Linear TV', ...)")
          - error: None on success, or error message string

    Examples:
        resolve_channel_reference_tool("awareness", tool_context)
          → {
              "channels": ["Linear TV", "CTV", "OTT", "Online Audio", ...],
              "sql_filter": "Channel IN ('Linear TV', 'CTV', 'OTT', ...)",
              "error": None
            }

        resolve_channel_reference_tool("direct", tool_context)
          → {
              "channels": ["Direct"],
              "sql_filter": "Channel IN ('Direct')",
              "error": None
            }
    """
    if not _KM_AVAILABLE or km is None:
        return {
            "channels": [],
            "sql_filter": "",
            "error": "KnowledgeManager unavailable — fall back to manual interpretation.",
        }

    state = getattr(tool_context, "state", {}) or {}
    client_id = state.get("client_lock") or state.get("client_id") or os.getenv("DEFAULT_CLIENT_ID", "NPI")
    table_id = state.get("routed_table_id", "performance")

    try:
        result = km.resolve_term_safe(client_id, term, table_id)
        _logger.info(f"resolve_channel_reference: {term!r} for {client_id}/{table_id} → {result.get('channels')}")
        return result
    except Exception as e:
        _logger.error(f"resolve_channel_reference error: {e}")
        return {"channels": [], "sql_filter": "", "error": str(e)}


# ============================================================
# Config-change proposal tools  (front half of the config_writer pipeline)
# ============================================================
#
# These two tools let the data science agent PROPOSE a change to
# ad_campaign_dataset_config_v3.json and, after a human approves in chat,
# COMMIT it. They are thin wrappers over data_science/utils/config_writer.py
# — all gating, backup, atomic write and audit logging live there.
#
# Flow:
#   1. User explicitly asks for a config change
#      ("add Podcast as an awareness channel for NPI").
#   2. Agent calls propose_config_change(...). Runs Gate 1 (schema) +
#      Gate 2 (full deterministic test suite). NOTHING is written.
#   3. Agent shows the returned diff_summary to the user verbatim, says
#      nothing is saved yet, and asks for explicit approval.
#   4. On an explicit "approve", agent calls confirm_config_change(token).
#      Runs Gate 3 (backup + atomic write). The change is live.
#   5. On anything else, agent does nothing — the token expires
#      harmlessly after 1 hour.
#
# Import matches the relative style used for knowledge_manager above
# (tools.py runs as part of the data_science package).
try:
    from .utils.config_writer import (
        propose_change as _cw_propose_change,
        confirm_change as _cw_confirm_change,
    )
    _CONFIG_WRITER_AVAILABLE = True
except ImportError as _cw_err:
    _logger.warning(f"config_writer not available in tools: {_cw_err}")
    _cw_propose_change = None
    _cw_confirm_change = None
    _CONFIG_WRITER_AVAILABLE = False


def propose_config_change(
    op: str,
    category: str = "",
    channel: str = "",
    rule_id: str = "",
    rule_description: str = "",
    tool_context: ToolContext = None,
) -> dict:
    """
    Propose a change to the dataset config. RUNS VALIDATION ONLY — writes nothing.

    Call this ONLY when the user has EXPLICITLY asked for a config change
    (e.g. "add Podcast as an awareness channel", "that rule is missing,
    add it"). Do NOT call it proactively or to "remember" things the user
    did not ask to persist.

    The change is applied to the CURRENTLY LOCKED CLIENT and its routed
    table — you do not pass client_id/table_id, they come from session state.

    Supported ops:
      - "add_channel"  : add `channel` to channel_taxonomy[`category`]
                         (requires: category, channel)
      - "add_rule"     : define a new rule and attach it to the current
                         table (requires: rule_id, rule_description)

    After calling this you MUST:
      1. Show the user the returned `diff_summary` verbatim.
      2. Tell them NOTHING has been written yet.
      3. Ask for explicit approval ("reply 'approve' to save this").
      4. Only on an explicit affirmative, call confirm_config_change(token).
      5. On anything else, do nothing — the token expires on its own.

    Args:
        op: "add_channel" or "add_rule"
        category: taxonomy category for add_channel (e.g. "awareness", "paid")
        channel: channel name for add_channel (e.g. "Podcast")
        rule_id: identifier for add_rule (e.g. "exclude_test_partners")
        rule_description: human description for add_rule
        tool_context: ADK tool context (provides state access)

    Returns:
        dict with:
          - status: "pending" | "rejected"
          - token: confirmation token (only when status == "pending")
          - diff_summary: human-readable description of the change — SHOW THIS
          - gate_failed: "schema" | "tests" | None
          - errors: list of rejection reasons (when status == "rejected")
          - gates_passed: e.g. ["schema", "tests"]
    """
    if not _CONFIG_WRITER_AVAILABLE or _cw_propose_change is None:
        return {
            "status": "rejected",
            "token": None,
            "diff_summary": "",
            "gate_failed": None,
            "errors": ["config_writer is not available in this deployment."],
            "gates_passed": [],
        }

    state = getattr(tool_context, "state", {}) or {}
    client_id = (
        state.get("client_lock")
        or state.get("client_id")
        or os.getenv("DEFAULT_CLIENT_ID", "NPI")
    )
    table_id = state.get("routed_table_id", "performance")

    # Build the structured change patch from the agent's arguments.
    if op == "add_channel":
        if not category or not channel:
            return {
                "status": "rejected", "token": None, "diff_summary": "",
                "gate_failed": "schema",
                "errors": ["add_channel requires both 'category' and 'channel'."],
                "gates_passed": [],
            }
        change = {
            "op": "add_channel",
            "client_id": client_id,
            "table_id": table_id,
            "category": category,
            "channel": channel,
        }
    elif op == "add_rule":
        if not rule_id or not rule_description:
            return {
                "status": "rejected", "token": None, "diff_summary": "",
                "gate_failed": "schema",
                "errors": ["add_rule requires both 'rule_id' and 'rule_description'."],
                "gates_passed": [],
            }
        change = {
            "op": "add_rule",
            "rule_id": rule_id,
            "description": rule_description,
            "attach_to": [{"client_id": client_id, "table_id": table_id}],
        }
    else:
        return {
            "status": "rejected", "token": None, "diff_summary": "",
            "gate_failed": "schema",
            "errors": [
                f"Unsupported op {op!r}. This tool supports 'add_channel' "
                f"and 'add_rule'. Adding a whole new client/table is an "
                f"operator task, not an in-chat one."
            ],
            "gates_passed": [],
        }

    try:
        result = _cw_propose_change(change)  # runs Gate 1 + Gate 2, writes nothing
    except Exception as e:  # defensive
        _logger.error(f"propose_config_change error: {e}")
        return {
            "status": "rejected", "token": None, "diff_summary": "",
            "gate_failed": None, "errors": [str(e)], "gates_passed": [],
        }

    _logger.info(
        f"propose_config_change: {op} for {client_id}/{table_id} "
        f"→ {result.get('status')} (gates: {result.get('gates_passed')})"
    )

    # Return only the fields the agent needs — drop the in-memory proposed
    # config etc. The token is what links propose → confirm.
    return {
        "status": result.get("status"),
        "token": result.get("token"),
        "diff_summary": result.get("diff_summary", ""),
        "gate_failed": result.get("gate_failed"),
        "errors": result.get("errors", []),
        "gates_passed": result.get("gates_passed", []),
    }


def confirm_config_change(token: str, tool_context: ToolContext = None) -> dict:
    """
    Commit a previously-proposed config change. THIS WRITES THE CONFIG FILE.

    Call this ONLY after:
      1. You called propose_config_change and got status="pending" + a token.
      2. You showed the user the diff_summary.
      3. The user EXPLICITLY approved (a clear "approve" / "yes, save it").

    Never call this without an explicit human approval in the conversation.
    Never call it with a token the user did not approve.

    It re-runs the test suite once more, then takes a timestamped backup and
    atomically writes the new config. The token is single-use.

    Args:
        token: the confirmation token from propose_config_change
        tool_context: ADK tool context

    Returns:
        dict with:
          - status: "committed" | "rejected" | "expired"
          - backup_path: path to the pre-change backup (on success)
          - diff_summary: what was committed
          - gate_failed: "tests" | None
          - errors: list of reasons (on rejection/expiry)
    """
    if not _CONFIG_WRITER_AVAILABLE or _cw_confirm_change is None:
        return {
            "status": "rejected", "backup_path": None, "diff_summary": "",
            "gate_failed": None,
            "errors": ["config_writer is not available in this deployment."],
        }

    if not token or not str(token).strip():
        return {
            "status": "rejected", "backup_path": None, "diff_summary": "",
            "gate_failed": None,
            "errors": ["No token provided. Call propose_config_change first."],
        }

    # confirmed_by: prefer a real user identity if it is in session state.
    # The orchestrator webhook puts user_email into orchestrator state; on
    # the LOCAL AgentTool path that state is shared with this agent, so
    # user_email may be present. On the REMOTE DS path it is not, and we
    # fall back to a generic marker (the config_writer audit log still
    # records the timestamp). agent.py currently sets only client_lock /
    # client_id / LOCKED_CLIENT — no user identity — so the fallback is
    # the common case until a user field is added upstream.
    state = getattr(tool_context, "state", {}) or {}
    confirmed_by = (
        state.get("user_email")
        or state.get("user_id")
        or "chat-approval"
    )

    try:
        result = _cw_confirm_change(token, confirmed_by=confirmed_by)
    except ValueError as e:
        # config_writer raises ValueError on an empty confirmed_by — should
        # not happen given the fallback above, but surface it cleanly.
        return {
            "status": "rejected", "backup_path": None, "diff_summary": "",
            "gate_failed": None, "errors": [str(e)],
        }
    except Exception as e:  # defensive
        _logger.error(f"confirm_config_change error: {e}")
        return {
            "status": "rejected", "backup_path": None, "diff_summary": "",
            "gate_failed": None, "errors": [str(e)],
        }

    _logger.info(
        f"confirm_config_change: token={token} confirmed_by={confirmed_by} "
        f"→ {result.get('status')}"
    )

    return {
        "status": result.get("status"),
        "backup_path": result.get("backup_path"),
        "diff_summary": result.get("diff_summary", ""),
        "gate_failed": result.get("gate_failed"),
        "errors": result.get("errors", []),
    }


# ============================================================
# Correlation/aggregate caches
# ============================================================
_corr_cache = {}
_corr_cache_ttl = 3600


def _cache_get(key: str):
    entry = _corr_cache.get(key)
    if entry:
        ts, val = entry
        if time.time() - ts < _corr_cache_ttl:
            _logger.info(f"CACHE_HIT: {key}")
            return val
        else:
            del _corr_cache[key]
    return None


def _cache_set(key: str, val):
    _corr_cache[key] = (time.time(), val)
    _logger.info(f"CACHE_SET: {key}")


# ============================================================
# BQ agent wrapper
# ============================================================
async def call_bigquery_agent(query: str, tool_context: ToolContext) -> str:
    """Calls the BigQuery sub-agent with retry on SQL errors."""
    q_hash = hashlib.md5(query.encode()).hexdigest()[:8]
    last_hash = tool_context.state.get("_last_bq_hash", "")
    steps_done = tool_context.state.get("_chart_steps_done", 0)
    if q_hash == last_hash and steps_done == 0:
        _logger.warning("Duplicate BQ call blocked")
        return tool_context.state.get("last_bq_result", "Already retrieved.")
    tool_context.state["_last_bq_hash"] = q_hash

    from .sub_agents.bigquery.agent import bigquery_agent
    agent_tool = AgentTool(agent=bigquery_agent)

    max_retries = 2
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            tool_context.state["_retry_count"] = attempt

            actual_query = query
            if attempt > 0 and last_error:
                actual_query = (
                    f"{query}\n\nNOTE: Previous attempt failed with: {last_error[:200]}. "
                    "Please simplify the SQL — use fewer columns, add WHERE filters for NULL values, "
                    "and avoid complex joins."
                )
                _logger.warning(f"BQ RETRY attempt {attempt} for query: {query[:100]}")

            result = await agent_tool.run_async(
                args={"request": actual_query},
                tool_context=tool_context,
            )

            result_str = str(result).lower()
            error_indicators = [
                "syntax error", "unrecognized name", "table not found",
                "does not exist", "invalid query", "sql error",
            ]
            if any(ind in result_str for ind in error_indicators):
                last_error = str(result)[:500]
                _logger.warning(f"BQ ERROR detected (attempt {attempt}): {last_error[:150]}")
                if attempt < max_retries:
                    continue

            tool_context.state["last_bq_result"] = result
            tool_context.state["_retry_count"] = 0
            return result

        except Exception as e:
            last_error = str(e)[:500]
            _logger.error(f"BQ EXCEPTION attempt {attempt}: {last_error[:150]}")
            if attempt >= max_retries:
                tool_context.state["_retry_count"] = 0
                return f"Query failed after {max_retries + 1} attempts: {last_error}"

    return tool_context.state.get("last_bq_result", "Query failed")


# ============================================================
# Direct BQ correlation/aggregate helpers (kept from original)
# ============================================================
def _get_table_for_client(client_id: str) -> str:
    """Return fully-qualified table path. Prefer KnowledgeManager when available."""
    if _KM_AVAILABLE and km is not None:
        try:
            return km.data.get("datasets") and \
                next(
                    (t["table_full_path"] for d in km.data["datasets"] if d["client_id"] == client_id
                     for t in d.get("tables", []) if t["table_id"] == "performance"),
                    None
                )
        except Exception:
            pass
    # Fallback to hardcoded
    project = os.getenv("GOOGLE_CLOUD_PROJECT", "nc-ai-chatbot")
    table_map = {
        "NPI": f"`{project}.Astrobot_NPI.vw_astrobot_npi_nc360_dashboard`",
        "Venetian": f"`{project}.Astrobot_Venetian.sample_astrobot_venetian_nc360_dashboard`",
        "WinnDixie": f"`{project}.Astrobot_WinnDixie.sample_astrobot_wd_nc360_dashboard`",
    }
    return table_map.get(client_id, table_map["NPI"])


def _compute_correlation_via_bq(labels: list) -> dict:
    """Run BQ CORR() query directly to get accurate correlations (cached 1h)."""
    client_id = os.getenv("DEFAULT_CLIENT_ID", "NPI")
    cache_key = f"corr:{client_id}:{','.join(sorted(labels))}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    try:
        from google.cloud import bigquery
        project = os.getenv("GOOGLE_CLOUD_PROJECT", "nc-ai-chatbot")
        table = _get_table_for_client(client_id)
        if not table.startswith("`"):
            table = f"`{table}`"

        corr_parts = []
        for i, c1 in enumerate(labels):
            for j, c2 in enumerate(labels):
                if i < j:
                    corr_parts.append(f"ROUND(CORR({c1}, {c2}), 4) AS {c1.lower()}_{c2.lower()}_corr")
        if not corr_parts:
            return {}

        null_filter = " AND ".join([f"{c} IS NOT NULL" for c in labels])
        sql = f"SELECT {', '.join(corr_parts)} FROM {table} WHERE {null_filter}"
        _logger.info(f"BRUTE_FORCE CORR query: {sql}")

        client = bigquery.Client(project=project)
        results = client.query(sql).result()
        row = next(iter(results), None)

        if row:
            corr_dict = {}
            for i, c1 in enumerate(labels):
                for j, c2 in enumerate(labels):
                    if i < j:
                        key = f"{c1.lower()}_{c2.lower()}_corr"
                        if hasattr(row, key):
                            corr_dict[(c1, c2)] = float(getattr(row, key))
            _logger.info(f"BRUTE_FORCE CORR results: {corr_dict}")
            _cache_set(cache_key, corr_dict)
            return corr_dict
    except Exception as e:
        _logger.error(f"BRUTE_FORCE CORR failed: {e}")
    return {}


def _compute_aggregate_via_bq(metric: str, dimension: str, agg_func: str = "SUM") -> dict:
    """Run BQ aggregate query directly."""
    try:
        from google.cloud import bigquery
        project = os.getenv("GOOGLE_CLOUD_PROJECT", "nc-ai-chatbot")
        client_id = os.getenv("DEFAULT_CLIENT_ID", "NPI")
        table = _get_table_for_client(client_id)
        if not table.startswith("`"):
            table = f"`{table}`"

        agg_func = agg_func.upper()
        if agg_func not in ("SUM", "AVG", "COUNT", "MIN", "MAX"):
            agg_func = "SUM"

        sql = f"""
        SELECT {dimension} AS dim, ROUND({agg_func}({metric}), 2) AS val
        FROM {table}
        WHERE {metric} IS NOT NULL AND {dimension} IS NOT NULL
        GROUP BY {dimension}
        ORDER BY val DESC
        """
        _logger.info(f"BRUTE_FORCE AGG: {sql.strip()}")

        client = bigquery.Client(project=project)
        results = client.query(sql).result()
        return {row.dim: float(row.val) for row in results if row.val is not None}
    except Exception as e:
        _logger.error(f"BRUTE_FORCE AGG failed: {e}")
    return {}


def _validate_chart_data(chart_type: str, data: dict) -> tuple:
    """Validate chart data, return (is_valid, reason)."""
    if chart_type in ("bar", "pie"):
        cats = data.get("categories", [])
        vals = data.get("values", [])
        if not cats or not vals:
            return False, "missing categories or values"
        if len(cats) != len(vals):
            return False, "category/value count mismatch"
        if all(v == 0 for v in vals):
            return False, "all values are zero"
        if len(cats) < 2:
            return False, "need at least 2 categories"
    elif chart_type == "stacked_bar":
        cats = data.get("categories", []) or data.get("labels", [])
        series = _normalize_series_to_dict(data.get("series", {}))
        if not cats:
            return False, "stacked_bar missing categories/labels"
        if not series:
            return False, "stacked_bar missing series (or series is malformed list)"
        non_empty = {k: v for k, v in series.items()
                     if isinstance(v, list) and any(float(x or 0) != 0 for x in v[:len(cats)])}
        if not non_empty:
            return False, "stacked_bar has no non-empty series after filtering"
        if len(non_empty) < 1:
            return False, "stacked_bar needs at least one non-empty series"
    elif chart_type in ("scatter", "line"):
        x = data.get("x", []) or data.get("categories", [])
        y = data.get("y", []) or data.get("values", [])
        if len(x) < 2 or len(y) < 2:
            return False, "need at least 2 points"
    return True, "ok"


# ============================================================
# Chart rendering (kept from original — unchanged below)
# ============================================================
def _filter_empty_series(series: dict) -> dict:
    """Remove series where all values are zero or None."""
    if not isinstance(series, dict):
        return series
    return {k: v for k, v in series.items()
            if isinstance(v, list) and any(x not in (0, None, 0.0) for x in v)}


def _render_chart_to_bytes(spec: dict) -> bytes:
    """Render chart from JSON spec using matplotlib, return PNG bytes."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    chart_type = spec.get("chart_type", "bar")
    if chart_type == "heatmap":
        _logger.info(f"HEATMAP_DEBUG spec: {spec}")
    title = spec.get("title", "")
    x_label = spec.get("x_label", "")
    y_label = spec.get("y_label", "")
    data = spec.get("data", {})

    fig, ax = plt.subplots(figsize=(10, 6))

    if chart_type == "bar":
        cats = data.get("categories", [])
        vals = data.get("values", [])
        bars = ax.bar(cats, vals, color="steelblue", edgecolor="white")
        ax.bar_label(bars, fmt="$%.2f", padding=3, fontsize=8)
        plt.xticks(rotation=45, ha="right")
    elif chart_type == "line":
        cats = data.get("categories", [])
        vals = data.get("values", [])
        ax.plot(cats, vals, marker="o", linewidth=2, color="steelblue")
        plt.xticks(rotation=45, ha="right")
    elif chart_type == "scatter":
        x = data.get("x", [])
        y = data.get("y", [])
        ax.scatter(x, y, alpha=0.7, color="steelblue", s=60)
        if x and y:
            mn = min(min(x), min(y))
            mx = max(max(x), max(y))
            ax.plot([mn, mx], [mn, mx], "r--", lw=2, label="Perfect prediction")
            ax.legend()
    elif chart_type == "pie":
        import numpy as np
        cats = data.get("categories", [])
        vals = data.get("values", [])
        if cats and vals and len(cats) == len(vals):
            filtered = [(c, v) for c, v in zip(cats, vals) if v > 0]
            if filtered:
                cats_f = [c for c, v in filtered]
                vals_f = [v for c, v in filtered]
                colors = plt.cm.Set3(np.linspace(0, 1, len(cats_f)))
                wedges, texts, autotexts = ax.pie(
                    vals_f, labels=cats_f, autopct="%1.1f%%",
                    colors=colors, startangle=90,
                    pctdistance=0.80, labeldistance=1.08,
                    textprops={"fontsize": 10},
                )
                for autotext in autotexts:
                    autotext.set_color("white")
                    autotext.set_fontweight("bold")
                    autotext.set_fontsize(11)
                excluded = [c for c, v in zip(cats, vals) if v == 0]
                if excluded:
                    ax.text(0.02, -0.05, f"Excluded (zero spend): {', '.join(excluded)}",
                            transform=ax.transAxes, fontsize=8, color="gray", ha="left", va="top")
                ax.axis("equal")
            else:
                ax.text(0.5, 0.5, "All values are zero", ha="center", va="center", transform=ax.transAxes)
        else:
            ax.text(0.5, 0.5, "Invalid pie chart data", ha="center", va="center", transform=ax.transAxes)
    elif chart_type == "heatmap":
        import numpy as np
        import re as _re
        matrix = data.get("matrix", [])
        labels = data.get("labels", [])
        series = _normalize_series_to_dict(data.get("series", {}))
        arr = None

        if series and not matrix:
            corr_keys = [k for k in series.keys() if "_corr" in k.lower() or "_correlation" in k.lower()]
            single_value = all(isinstance(v, list) and len(v) == 1 for v in series.values())
            if corr_keys and single_value:
                corr_dict = {}
                all_vars = []
                for key, vals in series.items():
                    clean = _re.sub(r"_corr(elation)?$", "", key, flags=_re.IGNORECASE)
                    parts = clean.split("_")
                    if len(parts) >= 2:
                        var1 = parts[0].title()
                        var2 = "_".join(parts[1:]).title()
                        try:
                            corr_dict[(var1, var2)] = float(vals[0])
                            if var1 not in all_vars:
                                all_vars.append(var1)
                            if var2 not in all_vars:
                                all_vars.append(var2)
                        except (ValueError, TypeError):
                            pass
                if all_vars and corr_dict:
                    labels = all_vars
                    n = len(labels)
                    arr = np.eye(n)
                    for (v1, v2), val in corr_dict.items():
                        if v1 in labels and v2 in labels:
                            i = labels.index(v1)
                            j = labels.index(v2)
                            arr[i, j] = val
                            arr[j, i] = val

        if arr is None and matrix and labels:
            arr = np.array(matrix)

        if arr is None and series:
            valid = {k: v for k, v in series.items() if isinstance(v, list) and len(v) > 1}
            if len(valid) >= 2:
                labels_p3 = list(valid.keys())
                arrays = list(valid.values())
                min_len = min(len(a) for a in arrays)
                arrays = [np.array(a[:min_len], dtype=float) for a in arrays]
                non_zero_pct = [float(np.sum(a != 0) / len(a)) for a in arrays]
                stds = [float(np.std(a)) for a in arrays]
                _logger.info(f"HEATMAP data quality: rows={min_len}, non_zero_pct={non_zero_pct}, stds={stds}")
                if min_len < 100 or any(p < 0.5 for p in non_zero_pct):
                    _logger.warning(f"HEATMAP: sparse data, running direct BQ CORR for {labels_p3}")
                    bq_corr = _compute_correlation_via_bq(labels_p3)
                    if bq_corr:
                        labels = labels_p3
                        n = len(labels)
                        arr = np.eye(n)
                        for (v1, v2), val in bq_corr.items():
                            if v1 in labels and v2 in labels:
                                i = labels.index(v1)
                                j = labels.index(v2)
                                arr[i, j] = val
                                arr[j, i] = val
                    else:
                        labels = labels_p3
                        arr = np.corrcoef(arrays)
                else:
                    labels = labels_p3
                    arr = np.corrcoef(arrays)

        if arr is None:
            potential_series = {
                k: v for k, v in data.items()
                if isinstance(v, list) and len(v) > 1 and all(isinstance(x, (int, float)) for x in v)
            }
            if len(potential_series) >= 2:
                labels = list(potential_series.keys())
                arrays = list(potential_series.values())
                min_len = min(len(a) for a in arrays)
                arrays = [a[:min_len] for a in arrays]
                arr = np.corrcoef(arrays)

        if arr is None:
            arr = np.array([[1.0]])
            labels = labels or ["data"]

        im = ax.imshow(arr, cmap="RdBu_r", aspect="auto", vmin=-1, vmax=1)
        ax.set_xticks(range(len(labels)))
        ax.set_yticks(range(len(labels)))
        ax.set_xticklabels(labels, rotation=45, ha="right")
        ax.set_yticklabels(labels)
        for i in range(len(labels)):
            for j in range(len(labels)):
                val = arr[i, j] if arr.ndim == 2 else 1.0
                ax.text(j, i, f"{val:.2f}",
                        ha="center", va="center",
                        color="white" if abs(val) > 0.5 else "black",
                        fontsize=10)
        plt.colorbar(im, ax=ax, label="Correlation")
    elif chart_type == "cluster_scatter":
        x = data.get("x", [])
        y = data.get("y", [])
        clusters = data.get("clusters", [])
        colors = ["steelblue", "red", "green", "orange", "purple"]
        for cid in sorted(set(clusters)):
            xi = [x[i] for i, c in enumerate(clusters) if c == cid]
            yi = [y[i] for i, c in enumerate(clusters) if c == cid]
            ax.scatter(xi, yi, label=f"Cluster {cid}",
                       color=colors[(cid - 1) % len(colors)],
                       s=60, alpha=0.7)
        ax.legend()

    elif chart_type == "stacked_bar":
        import numpy as np
        import matplotlib.cm as cm
        categories = data.get("categories", []) or data.get("labels", [])
        series = _normalize_series_to_dict(data.get("series", {}))

        # Filter out empty / all-zero series before plotting (avoids matplotlib shape errors)
        non_empty_series = {}
        for name, vals in series.items():
            if vals is None or not isinstance(vals, list):
                continue
            cleaned = [float(v or 0) for v in vals[:len(categories)]]
            while len(cleaned) < len(categories):
                cleaned.append(0.0)
            if any(v != 0 for v in cleaned):
                non_empty_series[name] = cleaned

        if not categories or not non_empty_series:
            ax.text(0.5, 0.5, "Invalid stacked_bar data: empty after filtering zero series",
                    ha="center", va="center", transform=ax.transAxes)
        else:
            bottom = [0.0] * len(categories)
            colors = cm.tab10(np.linspace(0, 1, max(1, len(non_empty_series))))
            for (name, vals), color in zip(non_empty_series.items(), colors):
                ax.bar(categories, vals, bottom=bottom, label=name, color=color, edgecolor="white")
                bottom = [b + v for b, v in zip(bottom, vals)]
            ax.legend(loc="upper right", fontsize=8)
            plt.xticks(rotation=45, ha="right")

    elif chart_type == "waterfall":
        stages = data.get("categories", []) or data.get("labels", [])
        values = data.get("values", [])
        if not stages or not values or len(stages) != len(values):
            ax.text(0.5, 0.5, "Invalid waterfall data",
                    ha="center", va="center", transform=ax.transAxes)
        else:
            cumulative = 0.0
            bottoms = []
            heights = []
            colors_list = []
            for v in values:
                v = float(v or 0)
                if v >= 0:
                    colors_list.append("#2ca02c")
                    bottoms.append(cumulative)
                    heights.append(v)
                else:
                    colors_list.append("#d62728")
                    bottoms.append(cumulative + v)
                    heights.append(-v)
                cumulative += v
            ax.bar(stages, heights, bottom=bottoms, color=colors_list, edgecolor="white")
            ax.axhline(y=0, color="black", linewidth=0.8)
            max_h = max(heights) if heights else 1
            for i, (h, b, v) in enumerate(zip(heights, bottoms, values)):
                v = float(v or 0)
                ax.text(i, b + h + max_h * 0.02, f"{v:+,.0f}",
                        ha="center", fontsize=8)
            plt.xticks(rotation=30, ha="right")

    elif chart_type == "funnel":
        import matplotlib.cm as cm
        stages = data.get("categories", []) or data.get("labels", [])
        values = data.get("values", [])
        if not stages or not values or len(stages) != len(values):
            ax.text(0.5, 0.5, "Invalid funnel data",
                    ha="center", va="center", transform=ax.transAxes)
        else:
            values = [float(v or 0) for v in values]
            max_val = max(values) if values else 1.0
            if max_val == 0:
                max_val = 1.0
            cmap = cm.Blues
            for i, (stage, val) in enumerate(zip(stages, values)):
                width = val / max_val
                left = (1.0 - width) / 2.0
                color = cmap(0.4 + 0.5 * (i / max(1, len(stages) - 1)))
                ax.barh(i, width, left=left, color=color, height=0.7)
                drop_text = ""
                if i > 0 and values[i-1] > 0:
                    drop_pct = (values[i-1] - val) / values[i-1] * 100
                    drop_text = f"  drop {drop_pct:.1f}%"
                pct_of_top = 100 * val / max_val
                ax.text(0.5, i, f"{stage}: {val:,.0f} ({pct_of_top:.1f}%){drop_text}",
                        ha="center", va="center", fontsize=10, fontweight="bold")
            ax.set_xlim(0, 1)
            ax.set_ylim(-0.5, len(stages) - 0.5)
            ax.invert_yaxis()
            ax.set_xticks([])
            ax.set_yticks([])
            for spine in ["top", "right", "bottom", "left"]:
                ax.spines[spine].set_visible(False)

    elif chart_type == "sankey":
        import numpy as np
        import matplotlib.patches as mpatches
        import matplotlib.cm as cm
        flows = data.get("flows", [])
        if not flows:
            ax.text(0.5, 0.5, "Sankey requires flows",
                    ha="center", va="center", transform=ax.transAxes)
        else:
            sources = []
            targets = []
            for f in flows:
                if f.get("from") not in sources:
                    sources.append(f.get("from"))
                if f.get("to") not in targets:
                    targets.append(f.get("to"))
            source_totals = {s: sum(float(f.get("value", 0)) for f in flows if f.get("from") == s) for s in sources}
            target_totals = {t: sum(float(f.get("value", 0)) for f in flows if f.get("to") == t) for t in targets}
            total_value = sum(source_totals.values()) or 1.0
            src_y = {}
            cur = 0.0
            for s in sources:
                h = source_totals[s] / total_value
                src_y[s] = (cur, cur + h)
                cur += h + 0.02
            tgt_y = {}
            cur = 0.0
            for t in targets:
                h = target_totals[t] / total_value
                tgt_y[t] = (cur, cur + h)
                cur += h + 0.02
            src_used = {s: src_y[s][0] for s in sources}
            tgt_used = {t: tgt_y[t][0] for t in targets}
            colors_list = cm.Set2(np.linspace(0, 1, max(1, len(sources))))
            for s, color in zip(sources, colors_list):
                y0, y1 = src_y[s]
                ax.add_patch(mpatches.Rectangle((0.05, y0), 0.05, y1 - y0, color=color))
                ax.text(0.03, (y0 + y1) / 2, str(s), ha="right", va="center", fontsize=9)
            for t in targets:
                y0, y1 = tgt_y[t]
                ax.add_patch(mpatches.Rectangle((0.90, y0), 0.05, y1 - y0, color="lightgray"))
                ax.text(0.97, (y0 + y1) / 2, str(t), ha="left", va="center", fontsize=9)
            for f in flows:
                src = f.get("from")
                tgt = f.get("to")
                val = float(f.get("value", 0)) / total_value
                if src not in sources or tgt not in targets:
                    continue
                color_idx = sources.index(src)
                src_top = src_used[src]
                src_bot = src_top + val
                tgt_top = tgt_used[tgt]
                tgt_bot = tgt_top + val
                src_used[src] = src_bot
                tgt_used[tgt] = tgt_bot
                xs = np.linspace(0.10, 0.90, 50)
                top_curve = src_top + (tgt_top - src_top) * (1 - np.cos(np.pi * (xs - 0.10) / 0.80)) / 2
                bot_curve = src_bot + (tgt_bot - src_bot) * (1 - np.cos(np.pi * (xs - 0.10) / 0.80)) / 2
                ax.fill_between(xs, top_curve, bot_curve, color=colors_list[color_idx], alpha=0.4)
            all_ys = list(src_used.values()) + list(tgt_used.values())
            ax.set_xlim(0, 1)
            ax.set_ylim(-0.05, (max(all_ys) if all_ys else 1) + 0.05)
            ax.invert_yaxis()
            ax.axis("off")

    elif chart_type == "treemap":
        import numpy as np
        import matplotlib.patches as mpatches
        import matplotlib.cm as cm
        categories = data.get("categories", []) or data.get("labels", [])
        values = data.get("values", [])
        if not categories or not values or len(categories) != len(values):
            ax.text(0.5, 0.5, "Invalid treemap data",
                    ha="center", va="center", transform=ax.transAxes)
        else:
            pairs = sorted(zip(categories, [float(v or 0) for v in values]), key=lambda x: -x[1])
            total = sum(v for _, v in pairs)
            if total <= 0:
                ax.text(0.5, 0.5, "All values are zero",
                        ha="center", va="center", transform=ax.transAxes)
            else:
                rects = []
                def slice_rec(items, x, y, w, h, horizontal):
                    if not items:
                        return
                    if len(items) == 1:
                        rects.append((items[0][0], items[0][1], x, y, w, h))
                        return
                    half_value = sum(v for _, v in items) / 2.0
                    cum = 0
                    split = 1
                    for i, (_, v) in enumerate(items):
                        cum += v
                        if cum >= half_value:
                            split = i + 1
                            break
                    first = items[:split]
                    second = items[split:]
                    if not second:
                        rects.append((first[0][0], first[0][1], x, y, w, h))
                        return
                    first_share = sum(v for _, v in first) / sum(v for _, v in items)
                    if horizontal:
                        slice_rec(first, x, y, w * first_share, h, not horizontal)
                        slice_rec(second, x + w * first_share, y, w * (1 - first_share), h, not horizontal)
                    else:
                        slice_rec(first, x, y, w, h * first_share, not horizontal)
                        slice_rec(second, x, y + h * first_share, w, h * (1 - first_share), not horizontal)
                slice_rec(pairs, 0, 0, 1, 1, True)
                colors_list = cm.tab20(np.linspace(0, 1, max(1, len(rects))))
                for (cat, val, x, y, w, h), color in zip(rects, colors_list):
                    ax.add_patch(mpatches.Rectangle((x, y), w, h, facecolor=color, edgecolor="white", linewidth=2))
                    if w * h > 0.005:
                        share_pct = val / total * 100
                        label = str(cat) + " " + "{:.1f}%".format(share_pct)
                        ax.text(x + w/2, y + h/2, label,
                                ha="center", va="center", fontsize=9, fontweight="bold")
                ax.set_xlim(0, 1)
                ax.set_ylim(0, 1)
                ax.axis("off")

    elif chart_type == "gantt":
        from datetime import datetime
        tasks = data.get("tasks", [])
        if not tasks:
            ax.text(0.5, 0.5, "Gantt requires tasks list",
                    ha="center", va="center", transform=ax.transAxes)
        else:
            def parse_date(s):
                for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y"):
                    try:
                        return datetime.strptime(str(s), fmt)
                    except (ValueError, TypeError):
                        continue
                return None
            parsed = []
            for t in tasks:
                start = parse_date(t.get("start"))
                end = parse_date(t.get("end"))
                if not start or not end:
                    continue
                parsed.append({
                    "name": t.get("name", "Unnamed"),
                    "start": start,
                    "end": end,
                    "status": t.get("status", "active"),
                })
            if not parsed:
                ax.text(0.5, 0.5, "No valid task dates parsed",
                        ha="center", va="center", transform=ax.transAxes)
            else:
                min_d = min(p["start"] for p in parsed)
                status_colors = {
                    "active": "#2ca02c", "paused": "#ff7f0e",
                    "completed": "#1f77b4", "planned": "#bcbd22",
                }
                for i, p in enumerate(parsed):
                    start_days = (p["start"] - min_d).days
                    duration = max(1, (p["end"] - p["start"]).days)
                    color = status_colors.get(p["status"], "#7f7f7f")
                    ax.broken_barh([(start_days, duration)], (i - 0.4, 0.8), facecolors=color)
                ax.set_yticks(range(len(parsed)))
                ax.set_yticklabels([p["name"] for p in parsed])
                ax.set_xlabel("Days since " + min_d.strftime("%Y-%m-%d"))
                ax.invert_yaxis()
                ax.grid(axis="x", alpha=0.3)

    elif chart_type == "bullet":
        actual = float(data.get("actual", 0) or 0)
        target = float(data.get("target", 0) or 0)
        bands = data.get("bands", [])
        if bands:
            sorted_bands = sorted(bands, key=lambda b: float(b.get("max", 0) or 0))
            cmap_colors = ["#fee2e2", "#fed7aa", "#bbf7d0", "#a7f3d0"]
            for i, band in enumerate(sorted_bands):
                width = float(band.get("max", 0) or 0)
                color = cmap_colors[min(i, len(cmap_colors)-1)]
                ax.barh(0, width, color=color, edgecolor="white", height=0.6)
        ax.barh(0, actual, color="#1f77b4", height=0.3, label="Actual: {:,.0f}".format(actual))
        if target > 0:
            ax.axvline(x=target, color="black", linewidth=3, ymin=0.2, ymax=0.8,
                       label="Target: {:,.0f}".format(target))
        ax.set_yticks([])
        ax.legend(loc="upper right", fontsize=9)
        max_x = max([actual, target] + [float(b.get("max", 0) or 0) for b in bands])
        if max_x > 0:
            ax.set_xlim(0, max_x * 1.1)

    ax.set_title(title)
    ax.set_xlabel(x_label)
    ax.set_ylabel(y_label)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    buf.seek(0)
    plt.close(fig)
    return buf.read()


async def call_analytics_agent(analysis_request: str, tool_context: ToolContext) -> str:
    """Calls analytics sub-agent based on ANALYTICS_MODE."""
    from .sub_agents.analytics.agent import analytics_agent
    import glob as _glob

    def _needs_code_interpreter(request: str) -> bool:
        # Honest about runtime capabilities — if CodeInterpreter
        # isn't configured, JSON mode is the only working path.
        # Otherwise the LLM writes Python that nothing can execute.
        if not os.getenv("CODE_INTERPRETER_EXTENSION_NAME"):
            return False

        advanced_keywords = [
            "subplot", "subplots", "small multiple", "facet",
            "treemap", "sunburst",
            "radar", "polar", "candlestick", "ohlc", "violin",
            "regression line", "trendline", "rolling average",
            "moving average", "custom", "multi-axis", "dual axis",
        ]
        return any(kw in request.lower() for kw in advanced_keywords)

    mode = os.getenv("ANALYTICS_MODE", "json").lower()
    if _needs_code_interpreter(analysis_request):
        original_mode = mode
        mode = "code_interpreter"
        if original_mode != mode:
            _logger.info("Auto-routing to code_interpreter for advanced chart")

    artifacts_base = os.path.expanduser("~/astrobot_mesh/.adk/artifacts")
    if not os.path.exists(artifacts_base):
        artifacts_base = "/tmp/.adk/artifacts"
    before = set()
    if mode == "code_interpreter":
        before = set(_glob.glob(os.path.join(artifacts_base, "**", "*.png"), recursive=True))

    call_time = time.time() - 5
    agent_tool = AgentTool(agent=analytics_agent)
    result = await agent_tool.run_async(
        args={"request": analysis_request},
        tool_context=tool_context,
    )

    if mode == "code_interpreter":
        after = set(_glob.glob(os.path.join(artifacts_base, "**", "*.png"), recursive=True))
        new_pngs = [
            f for f in (after - before)
            if os.path.getmtime(f) >= call_time and os.path.getsize(f) > 1000
        ]
        if new_pngs:
            latest = max(new_pngs, key=os.path.getmtime)
            try:
                with open(latest, "rb") as f:
                    img_bytes = f.read()
                fname = f"chart_{int(time.time())}_{hashlib.md5(latest.encode()).hexdigest()[:6]}.png"
                artifact = types.Part.from_bytes(data=img_bytes, mime_type="image/png")
                version = await tool_context.save_artifact(fname, artifact)
                _logger.info("Code Interpreter chart saved: %s v%s (%d bytes)", fname, version, len(img_bytes))
                return f"Generated chart via Code Interpreter ({len(img_bytes)} bytes)"
            except Exception as e:
                _logger.warning("CI artifact save failed: %s", e)
        return "Code Interpreter completed but no chart PNG found"

    # JSON MODE
    spec = None
    try:
        text = str(result).replace("```json", "").replace("```", "")
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            spec = json.loads(match.group(0))
    except Exception as e:
        _logger.warning("Could not parse chart spec: %s", e)
        return f"Chart generation failed — could not parse spec: {e}"

    if not spec or "chart_type" not in spec:
        _logger.warning("Invalid spec: %s", str(spec)[:200])
        return "Chart generation failed — invalid spec returned"

    try:
        png_bytes = _render_chart_to_bytes(spec)
        _logger.info("Chart rendered: %s (%d bytes)", spec.get("title", "untitled"), len(png_bytes))
    except Exception as e:
        _logger.error("Chart rendering failed: %s", e)
        return f"Chart rendering failed: {e}"

    fname = f"chart_{int(time.time())}_{hashlib.md5(str(spec).encode()).hexdigest()[:6]}.png"
    artifact = types.Part.from_bytes(data=png_bytes, mime_type="image/png")
    try:
        version = await tool_context.save_artifact(fname, artifact)
        _logger.info("Saved chart: %s v%s", fname, version)
    except Exception as e:
        _logger.warning("Save failed: %s", e)

    chart_title = spec.get("title", "chart")
    return f"Generated {spec.get('chart_type')} chart: {chart_title}"