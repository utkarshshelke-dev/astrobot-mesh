"""
bq_introspector.py — auto-build config blocks for new BigQuery tables.

Workflow:
  1. Query BigQuery for the table's schema (Dataset API — region-safe)
  2. Heuristically classify columns into roles (date/client/channel/kpi/spend)
  3. Sample distinct channels from the table
  4. Map channels to taxonomy categories via dictionary + substring rules
  5. Build a config block compatible with config_writer.propose_change

What this DOES populate:
  - table_id, table_full_path
  - kpi_column, channel_column, date_column, spend_column, client_column
  - schema.dimensions, schema.metrics
  - channel_taxonomy (best-effort from rules; unmatched go to _unmapped)
  - duality.has_duality = False (caller verifies)

What this does NOT populate (humans add later):
  - applicable_questions
  - channel_unification
  - rules
  - bqml_models
  - flag_definitions

CLI usage:
  python -m data_science.utils.bq_introspector <table_full_path> <client_id> [<table_id>]
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from typing import Optional

logger = logging.getLogger(__name__)


# ============================================================
# Channel taxonomy classification rules
# ============================================================

_CHANNEL_DICTIONARY: dict[str, list[str]] = {
    "Paid Search":     ["paid", "direct_response", "search"],
    "Search":          ["paid", "direct_response", "search"],
    "Paid Social":     ["paid", "mid_funnel", "social"],
    "Demand Gen":      ["paid", "mid_funnel"],
    "Performance Max": ["paid", "mid_funnel"],
    "Cross-network":   ["paid", "mid_funnel"],
    "Display":         ["paid"],
    "Shopping":        ["paid", "direct_response"],
    "Linear TV":       ["paid", "awareness", "tv"],
    "CTV":             ["paid", "awareness", "tv"],
    "OTT":             ["paid", "awareness", "tv"],
    "Online Video":    ["paid", "awareness"],
    "Paid Video":      ["paid", "awareness"],
    "Video":           ["paid", "awareness"],
    "OOH":             ["paid", "awareness"],
    "Print":           ["paid", "awareness"],
    "Online Audio":    ["paid", "awareness"],
    "Organic Search":  ["organic", "search"],
    "Organic Social":  ["organic", "social"],
    "Organic Video":   ["organic"],
    "Direct":          ["organic"],
    "Referral":        ["organic"],
    "Email":           ["organic", "direct_response"],
}

_SUBSTRING_RULES: list[tuple[re.Pattern, list[str]]] = [
    (re.compile(r"branded.*search|paid.*search",  re.I), ["paid", "direct_response", "search"]),
    (re.compile(r"organic.*search",                re.I), ["organic", "search"]),
    (re.compile(r"organic.*social",                re.I), ["organic", "social"]),
    (re.compile(r"organic.*video",                 re.I), ["organic"]),
    (re.compile(r"organic.*shopping",              re.I), ["organic", "direct_response"]),
    (re.compile(r"^organic$",                      re.I), ["organic"]),
    (re.compile(r"paid.*social|^social$",          re.I), ["paid", "mid_funnel", "social"]),
    (re.compile(r"\bsearch\b",                     re.I), ["paid", "direct_response", "search"]),
    (re.compile(r"linear.*tv|connected.*tv|^ctv$|^ott$", re.I), ["paid", "awareness", "tv"]),
    (re.compile(r"\btv\b|video|audio",             re.I), ["paid", "awareness"]),
    (re.compile(r"\booh\b|print|billboard",        re.I), ["paid", "awareness"]),
    (re.compile(r"performance.*max|pmax",          re.I), ["paid", "mid_funnel"]),
    (re.compile(r"demand.*gen|dgen",               re.I), ["paid", "mid_funnel"]),
    (re.compile(r"display|banner",                 re.I), ["paid"]),
    (re.compile(r"shopping",                       re.I), ["paid", "direct_response"]),
    (re.compile(r"email",                          re.I), ["organic", "direct_response"]),
    (re.compile(r"direct|referral",                re.I), ["organic"]),
    (re.compile(r"paid",                           re.I), ["paid"]),
]

_SENTINEL_CHANNELS = frozenset({
    "(Other)", "Other", "NA", "N/A", "Unassigned", "VAST Only",
    "Lead Generation", "", "null", "NULL", "None", "(not set)",
})

_COLUMN_ROLE_HINTS: dict[str, list[str]] = {
    "date_column":    ["date", "day", "report_date"],
    "client_column":  ["client"],
    "channel_column": ["gvmm_channel", "channel"],
    "kpi_column":     ["conversions", "kpi", "vivs", "transactions", "revenue"],
    "spend_column":   ["cost", "spend", "budget_to_date", "media_cost"],
    "partner_column": ["gvmm_partner", "partner", "vendor"],
    "geo_column":     ["budget_level1", "geo", "region", "market"],
}


def _parse_table_path(table_full_path: str) -> tuple[str, str, str]:
    parts = table_full_path.split(".")
    if len(parts) != 3:
        raise ValueError(
            f"table_full_path must be 'project.dataset.table', got: {table_full_path!r}"
        )
    return parts[0], parts[1], parts[2]


def _get_table_schema(table_full_path: str) -> list[dict]:
    from google.cloud import bigquery
    project, _, _ = _parse_table_path(table_full_path)
    compute_project = os.getenv("BQ_DATA_PROJECT_ID", project)
    bq = bigquery.Client(project=compute_project)
    table_obj = bq.get_table(table_full_path)
    return [
        {"name": f.name, "type": f.field_type, "mode": f.mode or "NULLABLE"}
        for f in table_obj.schema
    ]


def _get_distinct_channels(table_full_path: str, channel_column: str, limit: int = 200) -> list[str]:
    from google.cloud import bigquery
    project, _, _ = _parse_table_path(table_full_path)
    compute_project = os.getenv("BQ_DATA_PROJECT_ID", project)
    bq = bigquery.Client(project=compute_project)
    sql = f"""
    SELECT DISTINCT `{channel_column}` AS channel
    FROM `{table_full_path}`
    WHERE `{channel_column}` IS NOT NULL
      AND TRIM(CAST(`{channel_column}` AS STRING)) != ''
    LIMIT {limit}
    """
    try:
        rows = bq.query(sql).result()
        channels = [str(r.channel).strip() for r in rows if r.channel]
        channels = [c for c in channels if c not in _SENTINEL_CHANNELS]
        return sorted(set(channels))
    except Exception as e:
        logger.warning(f"Could not sample channels from {table_full_path}: {e}")
        return []


_METRIC_TYPES = frozenset({"INTEGER", "INT64", "FLOAT", "FLOAT64", "NUMERIC", "BIGNUMERIC"})


def _classify_columns_by_role(schema: list[dict]) -> dict[str, Optional[str]]:
    by_name = {col["name"]: col for col in schema}
    lower_names = {col["name"].lower(): col["name"] for col in schema}
    roles: dict[str, Optional[str]] = {}
    for role, hints in _COLUMN_ROLE_HINTS.items():
        match = None
        for hint in hints:
            for col_name in by_name:
                if col_name.lower() == hint.lower():
                    match = col_name
                    break
            if match:
                break
        if not match:
            for hint in hints:
                for lower, original in lower_names.items():
                    if hint.lower() in lower:
                        match = original
                        break
                if match:
                    break
        roles[role] = match
    return roles


def _split_schema_dims_metrics(schema: list[dict]) -> tuple[list[str], list[str]]:
    dimensions = []
    metrics = []
    for col in schema:
        if col["type"].upper() in _METRIC_TYPES:
            metrics.append(col["name"])
        else:
            dimensions.append(col["name"])
    return dimensions, metrics


def _classify_channel(channel: str) -> Optional[list[str]]:
    if channel in _CHANNEL_DICTIONARY:
        return list(_CHANNEL_DICTIONARY[channel])
    for pattern, categories in _SUBSTRING_RULES:
        if pattern.search(channel):
            return list(categories)
    return None


def _build_taxonomy(channels: list[str]) -> tuple[dict, list[str]]:
    taxonomy: dict[str, list[str]] = {
        "organic": [], "paid": [], "awareness": [], "direct_response": [],
        "mid_funnel": [], "tv": [], "social": [], "search": [],
    }
    unmapped: list[str] = []
    for channel in channels:
        categories = _classify_channel(channel)
        if categories is None:
            unmapped.append(channel)
            continue
        for cat in categories:
            if cat in taxonomy and channel not in taxonomy[cat]:
                taxonomy[cat].append(channel)
    for cat in taxonomy:
        taxonomy[cat].sort()
    unmapped.sort()
    return taxonomy, unmapped


# ============================================================
# Auto-generators for applicable_questions, channel_unification,
# rules, and duality detection
# ============================================================

def _detect_pacing_table(metric_columns):
    pacing_signals = {"Budget_Total", "Forecast_Total", "Days_Remaining",
                      "Budget_To_Date", "Budget_Remaining", "Budget_Flag"}
    return any(c in metric_columns for c in pacing_signals)


def _detect_campaign_table(dim_columns):
    return any(c in dim_columns for c in ("Campaign", "Campaign_ID", "Campaign_Name"))


def _detect_duality(table_full_path, spend_col, kpi_col):
    from google.cloud import bigquery
    project, _, _ = _parse_table_path(table_full_path)
    compute_project = os.getenv("BQ_DATA_PROJECT_ID", project)
    bq = bigquery.Client(project=compute_project)
    sql = f"""
    WITH sample AS (
      SELECT `{spend_col}` AS spend, `{kpi_col}` AS kpi
      FROM `{table_full_path}`
      WHERE `{spend_col}` IS NOT NULL OR `{kpi_col}` IS NOT NULL
      LIMIT 10000
    )
    SELECT
      COUNTIF(spend > 0 AND (kpi IS NULL OR kpi = 0)) AS spend_only_rows,
      COUNTIF(kpi > 0 AND (spend IS NULL OR spend = 0)) AS kpi_only_rows,
      COUNTIF(spend > 0 AND kpi > 0) AS both_rows,
      COUNT(*) AS total_rows
    FROM sample
    """
    try:
        row = next(iter(bq.query(sql).result()))
        spend_only = row.spend_only_rows or 0
        kpi_only = row.kpi_only_rows or 0
        both = row.both_rows or 0
        total = row.total_rows or 1
        threshold = 0.05
        # Detect duality two ways:
        # (a) Both spend_only and kpi_only above threshold (canonical)
        # (b) Perfect mutual exclusion: both=0 with real spend AND kpi rows
        canonical = (
            spend_only / total > threshold and
            kpi_only / total > threshold and
            spend_only + kpi_only > both
        )
        mutual_exclusion = (
            both == 0 and spend_only > 100 and kpi_only > 100
        )
        has_duality = canonical or mutual_exclusion
        return {
            "has_duality": bool(has_duality),
            "spend_rows_filter": f"{spend_col} > 0" if has_duality else None,
            "conv_rows_filter": f"{kpi_col} > 0" if has_duality else None,
            "note": (
                f"Auto-detected. Sample: spend_only={spend_only}, "
                f"kpi_only={kpi_only}, both={both}, total={total}. "
                f"{'Duality present.' if has_duality else 'No duality.'}"
            ),
            "_auto_generated": True,
        }
    except Exception as e:
        logger.warning(f"Could not detect duality for {table_full_path}: {e}")
        return {
            "has_duality": False,
            "note": f"Duality detection failed: {e}. Defaulted to False.",
            "_auto_generated": True,
        }


def _generate_applicable_questions(schema, roles, is_pacing, is_campaign):
    questions = []
    col_names_lower = {col["name"].lower() for col in schema}
    has_channel = bool(roles.get("channel_column"))
    has_cost = bool(roles.get("spend_column"))
    has_kpi = bool(roles.get("kpi_column"))
    has_date = bool(roles.get("date_column"))
    has_clicks = "clicks" in col_names_lower

    if is_pacing:
        questions.extend([
            "pacing", "budget", "budget_total", "forecast_total",
            "budget remaining", "burn rate", "underpacing", "overpacing",
            "on pace", "days remaining", "month-end forecast",
            "geo budget", "partner budget", "budget flag",
            "projected spend", "will we hit budget",
        ])
        return questions

    if has_channel:
        questions.extend(["channel performance", "channel ranking", "top channels",
                          "channel mix", "spend by channel"])
    if has_cost and has_kpi:
        questions.extend(["cpa", "roas", "channel efficiency", "cost per conversion"])
    if has_kpi and has_channel:
        questions.append("conversions")
    if has_date and (has_kpi or has_cost):
        questions.extend(["forecast", "monthly trend", "weekly trend", "time series"])
    if has_date and has_channel and has_kpi:
        questions.extend(["correlation", "volatility", "channel synergy"])
    if has_channel:
        questions.append("organic vs paid")
    if has_clicks and has_cost:
        questions.append("ctr")
    if is_campaign:
        questions.extend(["campaign performance", "top campaigns", "campaign ranking"])

    seen = set()
    out = []
    for q in questions:
        if q not in seen:
            seen.add(q)
            out.append(q)
    return out


def _generate_rules(schema, roles, is_pacing, has_duality, channel_taxonomy):
    rules = [
        "always_filter_by_client",
        "always_use_date_range_filter",
        "never_select_star_without_limit",
        "use_safe_divide_for_ratios",
    ]
    if has_duality:
        rules.extend([
            "blended_cpa_use_unified_cte",
            "ranking_use_unified_cte",
            "channel_mix_use_unified_cte",
        ])
    if roles.get("channel_column") and roles.get("kpi_column"):
        rules.append("volatility_use_cv_not_stddev")
    if any(channel_taxonomy.get(c) for c in ("organic", "paid", "awareness", "tv", "social")):
        rules.append("always_resolve_channel_terms_via_taxonomy")
    if channel_taxonomy.get("organic"):
        rules.append("organic_efficiency_use_organic_filter")
    if channel_taxonomy.get("tv") and (channel_taxonomy.get("search") or channel_taxonomy.get("direct_response")):
        rules.append("tv_halo_use_correlation")
    if roles.get("date_column"):
        rules.append("forecast_aggregate_to_weekly_for_chart")
    if is_pacing:
        rules.extend([
            "pacing_use_days_remaining_for_projections",
            "flag_status_check_first",
            "ignore_default_channel_unless_explicit",
            "use_GVMM_Channel_not_Budget_Channel_for_grouping",
            "active_flights_only_unless_specified",
            "use_forecast_total_for_projections",
        ])
    seen = set()
    out = []
    for r in rules:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def _generate_channel_unification(channels):
    unification = {}
    channel_set = set(channels)
    for ch in channels:
        if ch.startswith("Paid ") and ch[len("Paid "):] in channel_set:
            base = ch[len("Paid "):]
            unification.setdefault(ch, []).extend([base, ch])
    pmax_group = ["Cross-network", "Demand Gen", "Performance Max"]
    if all(c in channel_set for c in pmax_group):
        unification["Demand Gen + P-Max"] = pmax_group
    video_group = ["Linear TV", "CTV", "OTT", "Online Video", "Paid Video", "Video"]
    video_present = [c for c in video_group if c in channel_set]
    if len(video_present) >= 3:
        unification["Video/CTV/OTT/TV"] = video_present
    if "Branded Paid Search" in channel_set or "Generic Paid Search" in channel_set:
        search_variants = [
            c for c in ("Branded Paid Search", "Generic Paid Search",
                        "Paid Search", "Search")
            if c in channel_set
        ]
        if len(search_variants) >= 2:
            unification["Paid Search"] = search_variants
    for key in unification:
        unification[key] = sorted(set(unification[key]))
    return unification


def _build_table_block(table_full_path, table_id, schema, roles, taxonomy, unmapped, distinct_channel_count, channels=None):
    dimensions, metrics = _split_schema_dims_metrics(schema)
    is_pacing = _detect_pacing_table(metrics)
    is_campaign = _detect_campaign_table(dimensions)

    spend_col = roles.get("spend_column") or "Cost"
    kpi_col = roles.get("kpi_column") or "Conversions"
    schema_names = [c["name"] for c in schema]
    if spend_col in schema_names and kpi_col in schema_names and not is_pacing:
        duality = _detect_duality(table_full_path, spend_col, kpi_col)
    else:
        duality = {
            "has_duality": False,
            "note": "Skipped (pacing table or missing spend/kpi cols).",
            "_auto_generated": True,
        }

    applicable_questions = _generate_applicable_questions(schema, roles, is_pacing, is_campaign)
    rules = _generate_rules(schema, roles, is_pacing, duality["has_duality"], taxonomy)
    unification = _generate_channel_unification(channels or [])

    block = {
        "table_id": table_id,
        "_purpose": f"Auto-introspected from {table_full_path}",
        "table_full_path": table_full_path,
        "primary_metric": roles.get("kpi_column") or "Conversions",
        "kpi_column": roles.get("kpi_column") or "Conversions",
        "channel_column": roles.get("channel_column") or "Channel",
        "client_column": roles.get("client_column") or "Client",
        "date_column": roles.get("date_column") or "Date",
        "spend_column": roles.get("spend_column") or "Cost",
        "schema": {
            "_note": "Auto-extracted via bq_introspector. Verify and edit as needed.",
            "dimensions": dimensions,
            "metrics": metrics,
        },
        "channel_taxonomy": taxonomy,
        "channel_unification": unification,
        "duality": duality,
        "rules": rules,
        "applicable_questions": applicable_questions,
        "_introspection_notes": {
            "table_type_detected": "pacing" if is_pacing else "performance",
            "has_campaign_dimension": is_campaign,
            "auto_classified_channels": sum(len(v) for v in taxonomy.values() if v),
            "unmapped_channels": unmapped,
            "distinct_channels_sampled": distinct_channel_count,
            "auto_generated_fields": [
                "applicable_questions", "channel_unification",
                "rules", "duality", "channel_taxonomy",
            ],
            "_help": (
                "All fields auto-generated. Review before deploying. "
                "Add domain-specific applicable_questions, refine channel_unification, "
                "add specialized rules from _global_rules.rule_definitions, "
                "verify duality detection, add bqml_models if applicable."
            ),
        },
    }
    if roles.get("partner_column"):
        block["partner_column"] = roles["partner_column"]
    if roles.get("geo_column"):
        block["geo_column"] = roles["geo_column"]
    return block


def introspect_table(table_full_path: str, client_id: str, table_id: str = "performance") -> dict:
    schema = _get_table_schema(table_full_path)
    roles = _classify_columns_by_role(schema)
    channel_col = roles.get("channel_column")
    if channel_col:
        channels = _get_distinct_channels(table_full_path, channel_col)
    else:
        channels = []
        logger.warning(f"No channel column detected in {table_full_path}")
    taxonomy, unmapped = _build_taxonomy(channels)
    block = _build_table_block(
        table_full_path, table_id, schema, roles, taxonomy, unmapped,
        len(channels), channels=channels,
    )
    return {
        "client_id": client_id,
        "table_block": block,
        "summary": {
            "columns_seen": len(schema),
            "channels_classified": sum(len(v) for v in taxonomy.values() if v),
            "channels_unmapped": len(unmapped),
            "unmapped_list": unmapped,
            "detected_roles": roles,
        },
    }


def introspect_and_propose(table_full_path, client_id, table_id="performance", client_description=""):
    try:
        from data_science.utils.config_writer import propose_change
        from data_science.lib.channel_resolver import load_config_v3
    except ImportError:
        from utils.config_writer import propose_change
        from lib.channel_resolver import load_config_v3
    result = introspect_table(table_full_path, client_id, table_id)
    block = result["table_block"]
    config = load_config_v3()
    existing_client = next(
        (d for d in config.get("datasets", []) if d.get("client_id") == client_id),
        None,
    )
    if existing_client is not None:
        change = {"op": "add_table", "client_id": client_id, "table_block": block}
    else:
        change = {
            "op": "add_client",
            "client_id": client_id,
            "dataset": {
                "client_id": client_id,
                "name": f"Astrobot_{client_id}",
                "description": client_description or f"Auto-introspected client {client_id}",
                "default_metric": block["kpi_column"],
                "default_lookback_months": 12,
                "tables": [block],
            },
        }
    return propose_change(change), result["summary"]




def write_to_config_directly(
    table_full_path: str,
    client_id: str,
    table_id: str = "performance",
    client_description: str = "",
    config_path: str = None,
) -> dict:
    """
    Introspect a table and route the write through config_writer.propose_change
    + confirm_change. This means the write goes through whichever backend
    config_writer is configured for — JSON file (local dev) or Firestore
    (when USE_FIRESTORE_CONFIG=true, e.g. Cloud Run production).

    Returns:
      {
        "status": "added" | "exists" | "error",
        "message": "<human-readable>",
        "table_block": {...},      # what was added/would be added
        "backup_path": "..."        # commit identifier from the backend
      }

    Safe for both local dev (writes JSON) and Cloud Run (writes Firestore).
    Idempotent: refuses to add if client+table already exist.
    """
    # 1. Introspect the table
    try:
        result = introspect_table(table_full_path, client_id, table_id)
        block = result["table_block"]
    except Exception as e:
        return {"status": "error",
                "message": f"Introspection failed: {e}"}

    # 2. Detect client_filter_value if BQ data uses a different Client value
    client_column = block.get("client_column") or "Client"
    detected_filter = _detect_client_filter_value(
        table_full_path, client_column, client_id
    )

    # 3. Load current config (via the same backend reads use)
    try:
        from data_science.lib.channel_resolver import load_config_v3
    except ImportError:
        from lib.channel_resolver import load_config_v3
    try:
        config = load_config_v3(force_reload=True)
    except Exception as e:
        return {"status": "error",
                "message": f"Could not load current config: {e}"}

    # 4. Check if client exists
    existing_ds = next(
        (d for d in config.get("datasets", []) if d.get("client_id") == client_id),
        None,
    )

    # 5. Idempotency: if table already exists, no-op
    if existing_ds is not None:
        if any(t.get("table_id") == table_id for t in existing_ds.get("tables", [])):
            return {
                "status": "exists",
                "message": (
                    f"Table {table_id!r} already exists for client {client_id!r}. "
                    f"No write performed."
                ),
                "table_block": block,
            }

    # 6. Build the change dict for propose_change
    try:
        from data_science.utils.config_writer import propose_change, confirm_change
    except ImportError:
        from utils.config_writer import propose_change, confirm_change

    if existing_ds is not None:
        # Client exists -> add a new table to it
        change = {
            "op": "add_table",
            "client_id": client_id,
            "table_block": block,
        }
        action = f"Added table {table_id!r} to existing client {client_id!r}"
    else:
        # New client -> add the client with its first table
        dataset_block = {
            "client_id": client_id,
            "name": f"Astrobot_{client_id}",
            "description": client_description or f"Auto-introspected client {client_id}",
            "default_metric": block.get("kpi_column", "Conversions"),
            "default_lookback_months": 12,
            "tables": [block],
        }
        # Inject client_filter_value if a mismatch was detected
        if detected_filter:
            dataset_block["client_filter_value"] = detected_filter
        change = {
            "op": "add_client",
            "client_id": client_id,
            "dataset": dataset_block,
        }
        action = f"Added new client {client_id!r} with table {table_id!r}"
        if detected_filter:
            action += f" (auto-detected client_filter_value={detected_filter!r})"

    # 7. Propose -> Confirm
    propose_result = propose_change(change)
    if propose_result.get("status") != "pending":
        return {
            "status": "error",
            "message": (
                f"propose_change rejected: gate={propose_result.get('gate_failed')}, "
                f"errors={propose_result.get('errors')}"
            ),
            "table_block": block,
        }
    token = propose_result.get("token")
    if not token:
        return {
            "status": "error",
            "message": "propose_change returned no token",
            "table_block": block,
        }

    confirm_result = confirm_change(token, confirmed_by="write_to_config_directly")
    if confirm_result.get("status") != "committed":
        return {
            "status": "error",
            "message": (
                f"confirm_change failed: gate={confirm_result.get('gate_failed')}, "
                f"errors={confirm_result.get('errors')}"
            ),
            "table_block": block,
        }

    notes = block.get("_introspection_notes", {})
    return {
        "status": "added",
        "message": (
            f"{action}. Config updated via config_writer.\n"
            f"Auto-classified channels: {notes.get('auto_classified_channels', 0)}.\n"
            f"Unmapped channels: {len(notes.get('unmapped_channels', []))}.\n"
            f"Rules attached: {len(block.get('rules', []))}.\n"
            f"Backup/commit ref: {confirm_result.get('backup_path', 'n/a')}"
        ),
        "table_block": block,
        "backup_path": confirm_result.get("backup_path"),
    }


def _detect_client_filter_value(table_full_path: str, client_column: str, client_id: str):
    """Query BQ to see if the actual Client column value differs from client_id.

    Returns the filter value string if it should be set (i.e., exactly 1 distinct
    value AND that value != client_id). Returns None if values match, multiple
    distinct values exist, or the query fails.

    Used during auto-onboarding to handle clients like WinnDixie where the BQ
    data has Client='SEG' but the logical client_id is 'WinnDixie'.
    """
    try:
        from google.cloud import bigquery
        project = os.getenv("BQ_DATA_PROJECT_ID", "nc-ai-chatbot")
        bq = bigquery.Client(project=project)
        sql = (
            f"SELECT DISTINCT `{client_column}` AS v "
            f"FROM `{table_full_path}` "
            f"WHERE `{client_column}` IS NOT NULL "
            f"LIMIT 5"
        )
        rows = list(bq.query(sql).result())
        if len(rows) == 1:
            actual = rows[0]["v"]
            if actual is not None and str(actual) != client_id:
                return str(actual)
    except Exception as e:
        logger.warning(
            f"client_filter_value auto-detect failed for {table_full_path}: {e}"
        )
    return None


def _dataset_exists(project: str, dataset_id: str) -> bool:
    """Check if a BQ dataset exists. Fast — uses Dataset API, no query."""
    from google.cloud import bigquery
    from google.api_core.exceptions import NotFound
    try:
        bq = bigquery.Client(project=project)
        bq.get_dataset(f"{project}.{dataset_id}")
        return True
    except NotFound:
        return False
    except Exception as e:
        logger.warning(f"Could not check dataset {dataset_id}: {e}")
        return False


def _list_tables_in_dataset_raw(project: str, dataset_id: str) -> list[str]:
    """List table/view names in a dataset. Excludes models."""
    from google.cloud import bigquery
    try:
        bq = bigquery.Client(project=project)
        tables = []
        for t in bq.list_tables(f"{project}.{dataset_id}"):
            if t.table_type in ("TABLE", "VIEW", "MATERIALIZED_VIEW", "EXTERNAL"):
                tables.append(t.table_id)
        return sorted(tables)
    except Exception as e:
        logger.warning(f"Could not list tables in {dataset_id}: {e}")
        return []


def _guess_table_id_from_name(table_name: str) -> str:
    """Infer table_id (performance/pacing) from BQ table name."""
    name_lower = table_name.lower()
    if "budget" in name_lower or "pacing" in name_lower or "flight" in name_lower:
        return "pacing"
    return "performance"


def auto_onboard_client(
    client_id: str,
    project: str = None,
    dataset_pattern: str = "Astrobot_{client_id}",
) -> dict:
    """
    Auto-discover and onboard a new client by convention.

    Convention: client "Acme" -> dataset "Astrobot_Acme" in the configured project.
    If the dataset exists, introspect all its tables and add to config.

    Args:
      client_id: The client name as inferred from user text (e.g., "Acme")
      project: GCP project (defaults to BQ_DATA_PROJECT_ID env var)
      dataset_pattern: Template for dataset name. {client_id} gets substituted.

    Returns:
      {
        "status": "added" | "not_found" | "error" | "exists",
        "message": "<human-readable>",
        "client_id": "Acme",
        "dataset_id": "Astrobot_Acme",
        "tables_added": [{"table_id": "performance", ...}, ...],
        "errors": [...]
      }

    NOT safe for Cloud Run (filesystem ephemeral). Local dev / demo only.
    """
    project = project or os.getenv("BQ_DATA_PROJECT_ID", "nc-ai-chatbot")
    dataset_id = dataset_pattern.format(client_id=client_id)

    # Step 1: Does dataset exist?
    if not _dataset_exists(project, dataset_id):
        return {
            "status": "not_found",
            "message": f"No BigQuery dataset {project}.{dataset_id} found.",
            "client_id": client_id,
            "dataset_id": dataset_id,
            "tables_added": [],
        }

    # Step 2: List tables
    tables = _list_tables_in_dataset_raw(project, dataset_id)
    if not tables:
        return {
            "status": "not_found",
            "message": f"Dataset {dataset_id} exists but has no tables/views.",
            "client_id": client_id,
            "dataset_id": dataset_id,
            "tables_added": [],
        }

    # Step 3: For each table, introspect and add
    tables_added = []
    errors = []
    for table_name in tables:
        table_full_path = f"{project}.{dataset_id}.{table_name}"
        table_id = _guess_table_id_from_name(table_name)
        try:
            result = write_to_config_directly(
                table_full_path=table_full_path,
                client_id=client_id,
                table_id=table_id,
                client_description=f"Auto-onboarded for {client_id} on first reference",
            )
            if result["status"] == "added":
                tables_added.append({
                    "table_id": table_id,
                    "table_full_path": table_full_path,
                })
            elif result["status"] == "exists":
                # Already in config — skip silently (idempotent)
                pass
            else:
                errors.append(f"{table_full_path}: {result.get('message', 'unknown')}")
        except Exception as e:
            errors.append(f"{table_full_path}: {e}")

    if not tables_added and not errors:
        return {
            "status": "exists",
            "message": f"All tables for {client_id} already in config.",
            "client_id": client_id,
            "dataset_id": dataset_id,
            "tables_added": [],
        }

    return {
        "status": "added" if tables_added else "error",
        "message": (
            f"Onboarded {len(tables_added)} table(s) for client {client_id!r}: "
            f"{[t['table_id'] for t in tables_added]}"
            + (f". Errors: {errors}" if errors else "")
        ),
        "client_id": client_id,
        "dataset_id": dataset_id,
        "tables_added": tables_added,
        "errors": errors,
    }

def _print_cli_output(write_result, summary):
    print()
    print("=" * 70)
    print("BQ INTROSPECTION RESULT")
    print("=" * 70)
    print(f"Columns seen:            {summary['columns_seen']}")
    print(f"Channels classified:     {summary['channels_classified']}")
    print(f"Channels unmapped:       {summary['channels_unmapped']}")
    if summary["unmapped_list"]:
        print(f"  Unmapped:              {', '.join(summary['unmapped_list'])}")
    print()
    print("Detected column roles:")
    for role, col in summary["detected_roles"].items():
        marker = "OK" if col else "?? "
        print(f"  [{marker}] {role:18s} -> {col or '(not detected)'}")
    print()
    print(f"Write status:            {write_result['status']}")
    print(f"Diff summary:            {write_result['diff_summary']}")
    print(f"Gates passed:            {', '.join(write_result.get('gates_passed', []))}")
    if write_result["status"] == "pending":
        print()
        print("To commit, run:")
        print(f"  python -c \"from data_science.utils.config_writer import confirm_change; "
              f"print(confirm_change('{write_result['token']}', confirmed_by='YOUR_NAME'))\"")
    elif write_result.get("errors"):
        print()
        print("Errors:")
        for err in write_result["errors"]:
            print(f"  - {err}")
    print("=" * 70)


def _main():
    if len(sys.argv) < 3:
        print("Usage: python -m data_science.utils.bq_introspector "
              "<table_full_path> <client_id> [<table_id>] [<client_description>]")
        sys.exit(1)
    table_full_path = sys.argv[1]
    client_id = sys.argv[2]
    table_id = sys.argv[3] if len(sys.argv) > 3 else "performance"
    client_description = sys.argv[4] if len(sys.argv) > 4 else ""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    write_result, summary = introspect_and_propose(
        table_full_path, client_id, table_id, client_description
    )
    _print_cli_output(write_result, summary)
    inspect_path = f"/tmp/introspected_{client_id}_{table_id}.json"
    full_block = introspect_table(table_full_path, client_id, table_id)
    with open(inspect_path, "w") as f:
        json.dump(full_block, f, indent=2)
    print(f"\nProposed block saved to: {inspect_path}")


if __name__ == "__main__":
    _main()
