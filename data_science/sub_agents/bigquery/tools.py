import logging
import os
import time
import re
import json
import functools
from typing import Optional, Dict, List, Any, Tuple
from google.cloud import bigquery
from google.cloud.bigquery import DatasetReference
from google.adk.tools import ToolContext
try:
    from .sql_validator import validate_sql
except ImportError:
    validate_sql = None
import pandas as pd

# Copyright 2025 Google LLC (Apache 2.0)
"""
import logging
import os
import re
BigQuery tools for the Astrobot data science agent.

Schema source: nc-ai-chatbot BQ dashboard tables (all three clients share
the same column structure).

Dimension columns:
  Account, Business_Unit, Sub_Business_Unit, Campaign, Channel, Status,
  Tactic, Geo, Sub_Geo, NC_Paid, Partner, Targeting_Type, Audience_Modifier,
  Active, Campaign_Objective, Ad_Group, Ad_Group_Status, Ad, Ad_Status,
  Ad_Type, Creative, Device, Source_Medium, Network

Metric columns (all NULLABLE):
  Cost (FLOAT), Clicks (INTEGER), Impressions (INTEGER), Conversions (INTEGER),
  Transactions (INTEGER), Revenue (FLOAT), Platform_Revenue (FLOAT),
  Platform_Transactions (INTEGER), Sessions (INTEGER), Engaged_Sessions (INTEGER),
  Users (INTEGER), New_Users (INTEGER), Pageviews (INTEGER),
  Session_Duration (FLOAT), Bounces (INTEGER), Item_Quantity (INTEGER),
  ViVs (INTEGER), eViVs (INTEGER), Partner_Linkouts (INTEGER),
  Video_Views (INTEGER), Video_Views_25Pct (INTEGER), Video_Views_50Pct (INTEGER),
  Video_Views_75Pct (INTEGER), Video_Views_100Pct (INTEGER)

Tools:
  get_database_settings          — schema for LLM instruction context
  bigquery_nl2sql                — NL → SQL (BASELINE method)
  check_campaign_status          — safety gate: no recs on paused campaigns
  get_pacing_sql                 — MTD spend pacing by channel
  get_channel_efficiency_sql     — CPA / ROAS / CTR / CPC / CVR by channel
  get_correlation_sql            — Pearson CORR(channel spend, Transactions) all channels
  get_cpa_monthly_sql            — monthly CPA per channel (L12M), lowest CPA analysis
  get_saturation_sql             — spend vs transactions for diminishing returns
  get_channel_efficiency_rank_sql — transactions per dollar ranked + consistency score
"""

from google.adk.tools import ToolContext


# Module-level cache (was missing — caused NameError when called outside agent context)
_clients_cache = {"data": None, "ts": 0}
_CLIENTS_CACHE_TTL = 600  # 10 minutes

def discover_available_clients(project_id: str = None) -> dict:
    """
    Dynamically discover all clients from BigQuery datasets.
    
    Scans for datasets matching `Astrobot_<ClientName>` pattern,
    then finds the primary table (preferring vw_ views over sample_ tables).
    
    Returns:
        dict mapping client_name -> full_table_path
        e.g. {"NPI": "nc-ai-chatbot.Astrobot_NPI.vw_astrobot_npi_nc360_dashboard"}
    
    Cached for 5 minutes.
    """
    project_id = project_id or os.environ.get("BQ_DATA_PROJECT_ID", "nc-ai-chatbot")
    
    # Check cache
    now = time.time()
    if _clients_cache["data"] and (now - _clients_cache["ts"]) < _CLIENTS_CACHE_TTL:
        return _clients_cache["data"]
    
    try:
        client = _bq_module.Client(project=project_id)
        
        # List all datasets, filter to Astrobot_ prefix
        astrobot_datasets = []
        for ds in client.list_datasets():
            if ds.dataset_id.startswith("Astrobot_"):
                astrobot_datasets.append(ds.dataset_id)
        
        # For each dataset, find primary table
        clients = {}
        for dataset_id in astrobot_datasets:
            client_name = dataset_id.replace("Astrobot_", "")
            
            # List tables in this dataset
            ds_ref = _bq_module.DatasetReference(project_id, dataset_id)
            tables = list(client.list_tables(ds_ref))
            
            # Prefer vw_ view (multi-year data), fall back to sample_ table
            vw_table = None
            sample_table = None
            
            for tbl in tables:
                tid = tbl.table_id.lower()
                if tid.startswith("vw_") and "nc360_dashboard" in tid:
                    vw_table = tbl.table_id
                elif tid.startswith("sample_") and "nc360_dashboard" in tid:
                    sample_table = tbl.table_id
            
            chosen = vw_table or sample_table
            if chosen:
                clients[client_name] = f"{project_id}.{dataset_id}.{chosen}"
        
        # Cache and return
        _clients_cache["data"] = clients
        _clients_cache["ts"] = now
        return clients
    
    except Exception as e:
        print(f"⚠️  Error discovering clients: {e}")
        # Fall back to known clients if discovery fails
        return {
            "NPI": f"{project_id}.Astrobot_NPI.vw_astrobot_npi_nc360_dashboard",
            "Venetian": f"{project_id}.Astrobot_Venetian.sample_astrobot_venetian_nc360_dashboard",
            "WinnDixie": f"{project_id}.Astrobot_WinnDixie.sample_astrobot_wd_nc360_dashboard",
        }


def get_clients_summary_for_prompt(project_id: str = None) -> str:
    """Format the client list for inclusion in prompts."""
    clients = discover_available_clients(project_id)
    if not clients:
        return "⚠️ No clients found. Check BQ access."
    
    lines = [f"🏢 Available clients ({len(clients)}):"]
    for name, table in sorted(clients.items()):
        lines.append(f"  • {name} → {table}")
    return "\n".join(lines)


def is_valid_client(name: str, project_id: str = None) -> bool:
    """Check if a client name exists in the dynamic registry."""
    if not name:
        return False
    clients = discover_available_clients(project_id)
    # Case-insensitive match
    return any(c.lower() == name.lower() for c in clients.keys())


def get_table_for_client(name: str, project_id: str = None) -> str:
    """Get full table path for a client. Returns None if not found."""
    if not name:
        return None
    clients = discover_available_clients(project_id)
    # Case-insensitive lookup
    for c, table in clients.items():
        if c.lower() == name.lower():
            return table
    return None

# ============================================================

logger = logging.getLogger(__name__)

_PROJECT_ID = os.getenv("BQ_DATA_PROJECT_ID", "nc-ai-chatbot")

def _build_client_table_map() -> dict:
    """
    Build the client -> performance-table-path map.
    Prefers config v3 (loaded by KnowledgeManager) so adding clients
    is a config edit, not a code edit. Falls back to the hardcoded
    dict if config load fails for any reason.
    """
    hardcoded_fallback = {
        "NPI":       f"{_PROJECT_ID}.Astrobot_NPI.vw_astrobot_npi_nc360_dashboard",
        "Venetian":  f"{_PROJECT_ID}.Astrobot_Venetian.sample_astrobot_venetian_nc360_dashboard",
        "WinnDixie": f"{_PROJECT_ID}.Astrobot_WinnDixie.sample_astrobot_wd_nc360_dashboard",
    }
    try:
        try:
            from data_science.utils.knowledge_manager import manager as km
        except ImportError:
            from ...utils.knowledge_manager import manager as km
        cfg = getattr(km, "_config", None) or {}
        datasets = cfg.get("datasets", [])
        if not datasets:
            return hardcoded_fallback
        result = {}
        for d in datasets:
            cid = d.get("client_id")
            if not cid:
                continue
            for t in d.get("tables", []):
                if t.get("table_id") == "performance":
                    path = t.get("table_full_path")
                    if path:
                        result[cid] = path
                    break
        return result if result else hardcoded_fallback
    except Exception:
        return hardcoded_fallback


_CLIENT_TABLE_MAP = _build_client_table_map()

# Known Channel values in the dashboard (from NC360 taxonomy).
# Used in pivot CTEs — add/remove as needed per client.
_CHANNELS = [
    "Search",
    "Social",
    "Display",
    "Video",
    "Email",
    "Linear TV",
    "CTV",
    "Audio",
    "Direct Mail",
    "Programmatic",
    "P-Max",
    "Shopping",
    "Demand Gen",
    "OTT",
]



def _sanitize_json(obj):
    """Replace NaN/Infinity with None for JSON compatibility."""
    import math
    if isinstance(obj, dict):
        return {k: _sanitize_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_sanitize_json(item) for item in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    return obj


def _get_table(client_id: str, tool_context=None) -> str | None:
    """
    Resolve the BigQuery table path for a query.

    Priority:
      1. state.routed_table_path  (per-question routing from KnowledgeManager)
      2. _CLIENT_TABLE_MAP[client_id]  (client default = performance table)

    Callers should pass tool_context whenever available. The no-arg form
    is kept for legacy callers like get_database_settings (startup load).
    """
    if tool_context is not None:
        try:
            routed = tool_context.state.get("routed_table_path")
            if routed:
                return routed
        except Exception:
            pass
    return _CLIENT_TABLE_MAP.get(client_id)


def _unknown_client(client_id: str) -> dict:
    return {
        "error": (
            f"Unknown client '{client_id}'. "
            f"Must be one of: NPI, Venetian, WinnDixie."
        )
    }


def _channel_pivot_spend(channels: list[str]) -> str:
    """Build UNION ALL lines for channel spend pivot."""
    lines = []
    for ch in channels:
        safe = ch.replace("'", "\\'")
        col  = ch.replace(" ", "_").replace("-", "_")
        lines.append(
            f"  SUM(IF(Channel = '{safe}', Cost, 0))         AS {col}_Spend"
        )
    return ",\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# SCHEMA / SETTINGS
# ══════════════════════════════════════════════════════════════════════════════



def propose_new_table(
    table_full_path: str,
    client_id: str,
    table_id: str = "performance",
    client_description: str = "",
) -> dict:
    """
    Introspect a BigQuery table and add it to the config.

    Use when the user explicitly asks to add a new table or client,
    e.g. "add table nc-ai-chatbot.Astrobot_Acme.dashboard for Acme",
    or when KnowledgeManager doesn't recognize a table reference.

    Args:
      table_full_path: Fully-qualified BQ table path (project.dataset.table)
      client_id: Client identifier (NPI / Venetian / Acme / ...)
      table_id: Logical table id (performance / pacing / ...). Default: performance
      client_description: Optional description for new clients

    Returns:
      {
        "status": "added" | "exists" | "error",
        "message": "<human-readable summary>",
        "table_block": {...},   # the config block that was added/proposed
        "backup_path": "..."     # location of backup before this write
      }

    Notes:
      - This auto-populates structural fields AND semantic fields (taxonomy,
        unification, rules, applicable_questions) using heuristics.
      - Human is expected to review ad_campaign_dataset_config_v3.json after
        this runs and refine the taxonomy/rules where the heuristics missed.
      - Local-only feature: in Cloud Run deployment writes do not persist
        across container restarts.
    """
    try:
        from data_science.utils.bq_introspector import write_to_config_directly
    except ImportError:
        from utils.bq_introspector import write_to_config_directly

    return write_to_config_directly(
        table_full_path=table_full_path,
        client_id=client_id,
        table_id=table_id,
        client_description=client_description,
    )


def get_database_settings() -> dict:
    """
    Load schema and 3 sample rows from BigQuery for LLM instruction context.
    Called once at agent startup via before_agent_callback.
    """
    client = bigquery.Client(project=_PROJECT_ID)
    schema_parts = []

    for client_id, table in _CLIENT_TABLE_MAP.items():
        try:
            bq_table   = client.get_table(table)
            schema_str = "\n".join(
                f"  {f.name} ({f.field_type}, {f.mode})"
                for f in bq_table.schema
            )
            schema_parts.append(f"-- {client_id} ({table})\n{schema_str}")
        except Exception as e:
            logger.warning("Could not load schema for %s: %s", client_id, e)

    return {"schema": "\n\n".join(schema_parts)}


# ══════════════════════════════════════════════════════════════════════════════
# NL2SQL (BASELINE)
# ══════════════════════════════════════════════════════════════════════════════



def list_available_models(client_id: str = "NPI") -> dict:
    """
    Dynamically list all BQML models available for a client.
    Uses Dataset API instead of INFORMATION_SCHEMA (which has region limits).
    Cached for 5 minutes.
    """
    import time
    
    cache_key = f"_models_cache_{client_id}"
    cache_ttl = 300
    
    if not hasattr(list_available_models, "_cache"):
        list_available_models._cache = {}
    
    cache = list_available_models._cache
    if cache_key in cache:
        ts, val = cache[cache_key]
        if time.time() - ts < cache_ttl:
            return val
    
    try:
        from google.cloud import bigquery
        project = os.getenv("GOOGLE_CLOUD_PROJECT", "nc-ai-chatbot")
        bqml_dataset = "astrobot_bqml_models"
        
        bq = bigquery.Client(project=project)
        dataset_ref = bigquery.DatasetReference(project, bqml_dataset)
        
        # Use list_models API — works regardless of region
        models = {}
        prefix = client_id.lower()
        
        for model in bq.list_models(dataset_ref):
            name = model.model_id
            # Filter to client-relevant models
            if not (name.startswith(prefix) or prefix in name.lower()):
                continue
            
            models[name] = {
                "name": name,
                "type": model.model_type or "UNKNOWN",
                "created": str(model.created),
                "full_path": f"`{project}.{bqml_dataset}.{name}`",
            }
        
        result = {"client_id": client_id, "models": models, "count": len(models)}
        cache[cache_key] = (time.time(), result)
        logger.info(f"Found {len(models)} models for {client_id}")
        return result
        
    except Exception as e:
        logger.error(f"Could not list models: {e}")
        return {"client_id": client_id, "models": {}, "count": 0, "error": str(e)}


def get_models_summary_for_prompt(client_id: str = "NPI") -> str:
    """Format model list for LLM consumption in prompt."""
    result = list_available_models(client_id)
    
    if result.get("error") or result["count"] == 0:
        return f"No models available for {client_id}. (Check astrobot_bqml_models dataset)"
    
    models = result["models"]
    
    # Group by type
    by_type = {}
    for name, info in models.items():
        t = info["type"]
        by_type.setdefault(t, []).append(name)
    
    lines = [f"📋 Available models for {client_id} ({result['count']} total):"]
    lines.append("Location: `nc-ai-chatbot.astrobot_bqml_models.<model_name>`")
    lines.append("")
    
    type_emoji = {
        "ARIMA_PLUS": "🔮 FORECASTING",
        "LINEAR_REGRESSION": "📈 LINEAR PREDICTION",
        "BOOSTED_TREE_REGRESSOR": "🌳 BOOSTED TREE",
        "BOOSTED_TREE_CLASSIFIER": "🌳 BOOSTED CLASSIFIER",
        "LOGISTIC_REGRESSION": "🎯 CLASSIFICATION",
        "KMEANS": "🔵 CLUSTERING",
        "DNN_REGRESSOR": "🧠 DEEP LEARNING",
    }
    
    for model_type, names in sorted(by_type.items()):
        emoji_label = type_emoji.get(model_type, f"📊 {model_type}")
        lines.append(f"{emoji_label} ({model_type}):")
        for name in sorted(names):
            lines.append(f"  • {name}")
        lines.append("")
    
    lines.append("USAGE: Use EXACT names above. If a needed model is missing,")
    lines.append("offer to train a new one with CREATE OR REPLACE MODEL syntax.")
    
    return "\n".join(lines)



def bigquery_nl2sql(question: str, tool_context: ToolContext) -> dict:
    """
    Translate a natural language analytics question into a BigQuery SQL query
    and return context for the agent to call execute_sql.

    Exact column names (use these — no others):
      Dimensions : Account, Business_Unit, Sub_Business_Unit, Campaign, Channel,
                   Status, Tactic, Geo, Sub_Geo, NC_Paid, Partner, Targeting_Type,
                   Audience_Modifier, Active, Campaign_Objective, Ad_Group,
                   Ad_Group_Status, Ad, Ad_Status, Ad_Type, Creative, Device,
                   Source_Medium, Network
      Metrics    : Cost, Clicks, Impressions, Conversions, Transactions, Revenue,
                   Platform_Revenue, Platform_Transactions, Sessions,
                   Engaged_Sessions, Users, New_Users, Pageviews, Session_Duration,
                   Bounces, Item_Quantity, ViVs, eViVs, Partner_Linkouts,
                   Video_Views, Video_Views_25Pct, Video_Views_50Pct,
                   Video_Views_75Pct, Video_Views_100Pct

    SQL rules:
      - Always SUM() metrics and GROUP BY dimensions
      - Always SAFE_DIVIDE(numerator, NULLIF(denominator, 0)) for ratios
      - Always IFNULL(metric_expression, 0) to prevent NaN in output
      - Date column is named Date (DATE type) — use DATE_TRUNC / DATE_SUB
      - Never SELECT * without LIMIT
      - Filter by Channel using WHERE Channel = '...' or GROUP BY Channel
    """
    client_id = tool_context.state.get("client_id", "NPI")
    table     = _get_table(client_id, tool_context)
    if not table:
        return _unknown_client(client_id)

    db_settings = tool_context.state.get("database_settings", {})

    return {
        "table":       table,
        "client_id":   client_id,
        "schema":      db_settings.get("schema", "Schema not loaded."),
        "question":    question,
        "instruction": (
            f"Generate BigQuery SQL for: {question}\n"
            f"Table: `{table}`\n"
            f"Rules: SUM+GROUP BY | SAFE_DIVIDE(x,NULLIF(y,0)) for ratios | "
            f"IFNULL(...,0) on every metric | CORR() must use IFNULL(CORR(...),0) | "
            f"Date column = Date (DATE type)"
        ),
    }


# ══════════════════════════════════════════════════════════════════════════════
# SAFETY GATE
# ══════════════════════════════════════════════════════════════════════════════

def check_campaign_status(campaign_name: str, tool_context: ToolContext) -> dict:
    """
    Safety gate — check if a campaign is active before making recommendations.
    Uses the Status column (STRING) from the schema.
    Never make budget or bid recommendations for paused or ended campaigns.

    Args:
        campaign_name: Full or partial campaign name to look up.
    """
    client_id = tool_context.state.get("client_id", "NPI")
    table     = _get_table(client_id, tool_context)
    if not table:
        return _unknown_client(client_id)

    sql = f"""
SELECT
  Campaign,
  Status,
  Channel,
  Active,
  SUM(Cost)         AS Total_Spend,
  MAX(Date)         AS Last_Active_Date
FROM `{table}`
WHERE LOWER(Campaign) LIKE LOWER('%{campaign_name}%')
GROUP BY Campaign, Status, Channel, Active
ORDER BY Last_Active_Date DESC
LIMIT 20
"""
    try:
        bq   = bigquery.Client(project=_PROJECT_ID)
        rows = [dict(r) for r in bq.query(sql).result()]
        if not rows:
            return {"status": "not_found", "campaign": campaign_name}
        return {"campaigns": rows}
    except Exception as e:
        return {"error": str(e), "sql": sql}


# ══════════════════════════════════════════════════════════════════════════════
# PRE-BUILT SQL TOOLS
# All return {"sql": "...", "client_id": "..."}
# The agent passes the sql value to execute_sql via the BigQuery toolset.
# ══════════════════════════════════════════════════════════════════════════════

def get_pacing_sql(tool_context: ToolContext) -> dict:
    """
    Returns pre-built SQL for MTD spend pacing by Channel.
    No Budget column in schema — compares MTD spend to prior month same period.

    Use when user asks:
    - Are we on pace this month?
    - How is spend pacing vs last month?
    - MTD spend by channel.
    """
    client_id = tool_context.state.get("client_id", "NPI")
    table     = _get_table(client_id, tool_context)
    if not table:
        return _unknown_client(client_id)

    sql = f"""
WITH mtd AS (
  SELECT
    Channel,
    SUM(Cost)           AS MTD_Spend,
    SUM(Clicks)         AS MTD_Clicks,
    SUM(Impressions)    AS MTD_Impressions,
    SUM(Conversions)    AS MTD_Conversions,
    SUM(Transactions)   AS MTD_Transactions,
    SUM(Revenue)        AS MTD_Revenue
  FROM `{table}`
  WHERE DATE_TRUNC(Date, MONTH) = DATE_TRUNC(CURRENT_DATE(), MONTH)
  GROUP BY Channel
),
prior_full AS (
  SELECT
    Channel,
    SUM(Cost)           AS Prior_Month_Total_Spend
  FROM `{table}`
  WHERE DATE_TRUNC(Date, MONTH) = DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 MONTH), MONTH)
  GROUP BY Channel
),
prior_same_period AS (
  SELECT
    Channel,
    SUM(Cost)           AS Prior_Same_Period_Spend
  FROM `{table}`
  WHERE Date >= DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 MONTH), MONTH)
    AND Date <  DATE_ADD(
                  DATE_TRUNC(DATE_SUB(CURRENT_DATE(), INTERVAL 1 MONTH), MONTH),
                  INTERVAL EXTRACT(DAY FROM CURRENT_DATE()) - 1 DAY
                )
  GROUP BY Channel
)
SELECT
  m.Channel,
  IFNULL(m.MTD_Spend, 0)                                                         AS MTD_Spend,
  IFNULL(p.Prior_Same_Period_Spend, 0)                                            AS Prior_Same_Period_Spend,
  IFNULL(pf.Prior_Month_Total_Spend, 0)                                           AS Prior_Month_Total_Spend,
  IFNULL(SAFE_DIVIDE(m.MTD_Spend, NULLIF(p.Prior_Same_Period_Spend, 0)), 0)       AS Spend_Index_vs_Prior,
  IFNULL(SAFE_DIVIDE(
    m.MTD_Spend,
    NULLIF(pf.Prior_Month_Total_Spend, 0)
  ) * 100, 0)                                                                     AS Pct_Of_Prior_Month_Total,
  IFNULL(m.MTD_Transactions, 0)                                                   AS MTD_Transactions,
  IFNULL(m.MTD_Revenue, 0)                                                        AS MTD_Revenue,
  IFNULL(SAFE_DIVIDE(m.MTD_Revenue, NULLIF(m.MTD_Spend, 0)), 0)                  AS MTD_ROAS
FROM mtd m
LEFT JOIN prior_full pf          USING (Channel)
LEFT JOIN prior_same_period p    USING (Channel)
ORDER BY MTD_Spend DESC
"""
    return {"sql": sql.strip(), "client_id": client_id}


def get_channel_efficiency_sql(tool_context: ToolContext) -> dict:
    """
    Returns pre-built SQL for channel efficiency over the last 30 days.
    Computes: Spend, Transactions, Revenue, ROAS, CPA, CTR, CPC, CVR,
              ViVs, Engaged_Sessions, Bounce_Rate.

    Use when user asks:
    - Which channel performs best / worst?
    - CPA or ROAS by channel.
    - Channel efficiency audit.
    - How are channels performing?
    """
    client_id = tool_context.state.get("client_id", "NPI")
    table     = _get_table(client_id, tool_context)
    if not table:
        return _unknown_client(client_id)

    sql = f"""
SELECT
  Channel,
  IFNULL(SUM(Cost), 0)                                                                  AS Total_Spend,
  IFNULL(SUM(Clicks), 0)                                                                AS Total_Clicks,
  IFNULL(SUM(Impressions), 0)                                                           AS Total_Impressions,
  IFNULL(SUM(Conversions), 0)                                                           AS Total_Conversions,
  IFNULL(SUM(Transactions), 0)                                                          AS Total_Transactions,
  IFNULL(SUM(Revenue), 0)                                                               AS Total_Revenue,
  IFNULL(SUM(Sessions), 0)                                                              AS Total_Sessions,
  IFNULL(SUM(ViVs), 0)                                                                  AS Total_ViVs,
  IFNULL(SUM(Engaged_Sessions), 0)                                                      AS Total_Engaged_Sessions,
  IFNULL(SUM(Bounces), 0)                                                               AS Total_Bounces,
  -- Ratios
  IFNULL(SAFE_DIVIDE(SUM(Cost),        NULLIF(SUM(Transactions), 0)), 0)               AS CPA,
  IFNULL(SAFE_DIVIDE(SUM(Revenue),     NULLIF(SUM(Cost),         0)), 0)               AS ROAS,
  IFNULL(SAFE_DIVIDE(SUM(Clicks),      NULLIF(SUM(Impressions),  0)), 0)               AS CTR,
  IFNULL(SAFE_DIVIDE(SUM(Cost),        NULLIF(SUM(Clicks),       0)), 0)               AS CPC,
  IFNULL(SAFE_DIVIDE(SUM(Transactions),NULLIF(SUM(Clicks),       0)), 0)               AS CVR,
  IFNULL(SAFE_DIVIDE(SUM(Bounces),     NULLIF(SUM(Sessions),     0)), 0)               AS Bounce_Rate,
  IFNULL(SAFE_DIVIDE(SUM(Engaged_Sessions), NULLIF(SUM(Sessions), 0)), 0)              AS Engagement_Rate
FROM `{table}`
WHERE Date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
GROUP BY Channel
ORDER BY CPA ASC
"""
    return {"sql": sql.strip(), "client_id": client_id}


def get_correlation_sql(tool_context: ToolContext) -> dict:
    """
    Returns pre-built SQL computing Pearson correlation between each channel's
    monthly spend and total Transactions across all channels.

    Uses a monthly pivot CTE so CORR() runs on monthly aggregates
    (more statistically meaningful than raw daily rows).
    IFNULL(CORR(...), 0) prevents NaN in the JSON payload.

    Use when user asks:
    - Which channel has the highest statistical correlation with Transactions?
    - Which channel is the lead driver of conversions / revenue?
    - Correlation analysis between spend and outcomes.
    """
    client_id = tool_context.state.get("client_id", "NPI")
    table     = _get_table(client_id, tool_context)
    if not table:
        return _unknown_client(client_id)

    # Build pivot columns for all known channels
    pivot_cols = "\n".join([
        f"    SUM(IF(Channel = '{ch}', Cost, 0))  AS {ch.replace(' ','_').replace('-','_')}_Spend,"
        for ch in _CHANNELS
    ])

    # Build UNION ALL rows for correlation output
    union_rows = "\nUNION ALL\n".join([
        f"SELECT '{ch}' AS Channel, "
        f"IFNULL(CORR({ch.replace(' ','_').replace('-','_')}_Spend, Total_Transactions), 0) "
        f"AS Correlation_With_Transactions FROM pivoted"
        for ch in _CHANNELS
    ])

    sql = f"""
WITH monthly AS (
  SELECT
    DATE_TRUNC(Date, MONTH)    AS Month,
    Channel,
    SUM(Cost)                  AS Channel_Monthly_Spend,
    SUM(Transactions)          AS Channel_Monthly_Transactions
  FROM `{table}`
  GROUP BY Month, Channel
),
pivoted AS (
  SELECT
    Month,
    SUM(Channel_Monthly_Transactions)                  AS Total_Transactions,
{pivot_cols.rstrip(',')}
  FROM monthly
  GROUP BY Month
)
{union_rows}
ORDER BY Correlation_With_Transactions DESC
"""
    return {"sql": sql.strip(), "client_id": client_id}


def get_cpa_monthly_sql(tool_context: ToolContext) -> dict:
    """
    Returns pre-built SQL for monthly CPA per channel over the last 12 months.
    Includes avg / min / max / stddev CPA and months active.

    Use when user asks:
    - Which channel has the lowest Cost Per Acquisition on a monthly basis?
    - Monthly CPA breakdown.
    - Most cost-efficient channel for conversions.
    """
    client_id = tool_context.state.get("client_id", "NPI")
    table     = _get_table(client_id, tool_context)
    if not table:
        return _unknown_client(client_id)

    sql = f"""
WITH monthly_channel AS (
  SELECT
    DATE_TRUNC(Date, MONTH)                                                  AS Month,
    Channel,
    SUM(Cost)                                                                AS Spend,
    SUM(Transactions)                                                        AS Transactions,
    SUM(Conversions)                                                         AS Conversions,
    SUM(Revenue)                                                             AS Revenue,
    IFNULL(SAFE_DIVIDE(SUM(Cost), NULLIF(SUM(Transactions), 0)), 0)         AS CPA,
    IFNULL(SAFE_DIVIDE(SUM(Revenue), NULLIF(SUM(Cost), 0)), 0)              AS ROAS
  FROM `{table}`
  WHERE Date >= DATE_SUB(CURRENT_DATE(), INTERVAL 12 MONTH)
    AND Cost > 0
  GROUP BY Month, Channel
)
SELECT
  Channel,
  ROUND(AVG(CPA), 2)                                              AS Avg_CPA,
  ROUND(MIN(CPA), 2)                                              AS Min_CPA,
  ROUND(MAX(CPA), 2)                                              AS Max_CPA,
  ROUND(STDDEV(CPA), 2)                                           AS StdDev_CPA,
  ROUND(AVG(ROAS), 2)                                             AS Avg_ROAS,
  SUM(Spend)                                                      AS Total_Spend,
  SUM(Transactions)                                               AS Total_Transactions,
  COUNT(DISTINCT Month)                                           AS Months_Active
FROM monthly_channel
WHERE Transactions > 0
GROUP BY Channel
ORDER BY Avg_CPA ASC
"""
    return {"sql": sql.strip(), "client_id": client_id}


def get_saturation_sql(channel: str, tool_context: ToolContext) -> dict:
    """
    Returns pre-built SQL showing monthly spend vs Transactions for a single
    channel — used to identify diminishing returns / saturation point.

    Plot Monthly_Spend (x) vs Transactions_Per_Dollar (y) to see where the
    curve flattens.

    Use when user asks:
    - At what spend level does [channel] stop producing incremental transactions?
    - Saturation point for Search / Social / Display.
    - Diminishing returns analysis.

    Args:
        channel: Exact Channel value e.g. 'Search', 'Social', 'Display'
    """
    client_id = tool_context.state.get("client_id", "NPI")
    table     = _get_table(client_id, tool_context)
    if not table:
        return _unknown_client(client_id)

    sql = f"""
SELECT
  DATE_TRUNC(Date, MONTH)                                                  AS Month,
  Channel,
  SUM(Cost)                                                                AS Monthly_Spend,
  SUM(Transactions)                                                        AS Monthly_Transactions,
  SUM(Conversions)                                                         AS Monthly_Conversions,
  SUM(Clicks)                                                              AS Monthly_Clicks,
  SUM(Sessions)                                                            AS Monthly_Sessions,
  IFNULL(SAFE_DIVIDE(SUM(Transactions), NULLIF(SUM(Cost), 0)), 0)         AS Transactions_Per_Dollar,
  IFNULL(SAFE_DIVIDE(SUM(Cost), NULLIF(SUM(Transactions), 0)), 0)         AS CPA,
  IFNULL(SAFE_DIVIDE(SUM(Revenue), NULLIF(SUM(Cost), 0)), 0)              AS ROAS
FROM `{table}`
WHERE Channel = '{channel}'
  AND Cost > 0
  AND Date >= DATE_SUB(CURRENT_DATE(), INTERVAL 24 MONTH)
GROUP BY Month, Channel
ORDER BY Monthly_Spend ASC
"""
    return {
        "sql":       sql.strip(),
        "client_id": client_id,
        "channel":   channel,
        "note": (
            "Sort by Monthly_Spend ascending and plot vs Transactions_Per_Dollar. "
            "The point where Transactions_Per_Dollar stops increasing (flattens or "
            "declines) as Monthly_Spend rises is the saturation point."
        ),
    }


def get_channel_efficiency_rank_sql(tool_context: ToolContext) -> dict:
    """
    Returns pre-built SQL ranking all channels by Transactions per Dollar Spent
    over the last 12 months, with a monthly consistency score showing how often
    each channel sits in the bottom quartile.

    Use when user asks:
    - Which 3 channels sit at the bottom by transactions per dollar?
    - Efficiency ranking across all channels.
    - Where should we reallocate budget?
    - Which channels produce the fewest transactions per dollar?
    - Budget reallocation recommendation.
    """
    client_id = tool_context.state.get("client_id", "NPI")
    table     = _get_table(client_id, tool_context)
    if not table:
        return _unknown_client(client_id)

    sql = f"""
WITH monthly AS (
  SELECT
    DATE_TRUNC(Date, MONTH)                                               AS Month,
    Channel,
    SUM(Cost)                                                             AS Spend,
    SUM(Transactions)                                                     AS Transactions,
    SUM(Revenue)                                                          AS Revenue,
    IFNULL(SAFE_DIVIDE(SUM(Transactions), NULLIF(SUM(Cost), 0)), 0)      AS Txn_Per_Dollar,
    IFNULL(SAFE_DIVIDE(SUM(Cost), NULLIF(SUM(Transactions), 0)), 0)      AS CPA,
    IFNULL(SAFE_DIVIDE(SUM(Revenue), NULLIF(SUM(Cost), 0)), 0)           AS ROAS
  FROM `{table}`
  WHERE Date >= DATE_SUB(CURRENT_DATE(), INTERVAL 12 MONTH)
    AND Cost > 0
  GROUP BY Month, Channel
),
ranked AS (
  SELECT
    *,
    NTILE(4) OVER (PARTITION BY Month ORDER BY Txn_Per_Dollar ASC) AS Efficiency_Quartile
    -- Quartile 1 = bottom (worst), Quartile 4 = top (best)
  FROM monthly
),
summary AS (
  SELECT
    Channel,
    ROUND(AVG(Txn_Per_Dollar), 6)                                        AS Avg_Txn_Per_Dollar,
    ROUND(AVG(CPA), 2)                                                   AS Avg_CPA,
    ROUND(AVG(ROAS), 2)                                                  AS Avg_ROAS,
    SUM(Spend)                                                           AS Total_Spend,
    SUM(Transactions)                                                    AS Total_Transactions,
    COUNT(DISTINCT Month)                                                AS Months_Active,
    COUNTIF(Efficiency_Quartile = 1)                                     AS Months_In_Bottom_Quartile,
    COUNTIF(Efficiency_Quartile = 4)                                     AS Months_In_Top_Quartile
  FROM ranked
  GROUP BY Channel
)
SELECT
  Channel,
  Avg_Txn_Per_Dollar,
  Avg_CPA,
  Avg_ROAS,
  Total_Spend,
  Total_Transactions,
  Months_Active,
  Months_In_Bottom_Quartile,
  Months_In_Top_Quartile,
  ROUND(SAFE_DIVIDE(Months_In_Bottom_Quartile, Months_Active), 2)       AS Bottom_Quartile_Rate
FROM summary
ORDER BY Avg_Txn_Per_Dollar ASC   -- lowest efficiency first
"""
    return {"sql": sql.strip(), "client_id": client_id}

def compute_channel_volatility(
    client_id: str,
    table_name: Optional[str] = None,
    metric: str = "Conversions",
    lookback_months: int = 12,
    min_months: Optional[int] = None,
) -> dict:
    """
    Compute coefficient of variation (CV) for each channel's monthly metric values.
    Returns top 10 channels by CV, filtered to those with sufficient observations.
    
    This is a DETERMINISTIC computation - no LLM interpretation involved.
    Use this for "most volatile" / "most unpredictable" / "stability" questions.
    
    Args:
        client_id: Client name (NPI, Venetian, WinnDixie)
        table_name: Full table reference (e.g. nc-ai-chatbot.Astrobot_NPI.vw_...)
        metric: Column name to compute volatility on (Cost, Clicks, Impressions, Conversions, Revenue)
        lookback_months: How far back to look (default 12)
        min_months: Minimum months of data required for stable CV (default 8)
    
    Returns:
        dict with status, channels (list of channel/cv dicts sorted by cv desc), error.
    """
    try:
        from google.cloud import bigquery
    except ImportError:
        return {"status": "ERROR", "error": "google-cloud-bigquery not installed",
                "channels": []}

    # Resolve table_name from KnowledgeManager if not provided
    if table_name is None:
        try:
            table_name = _sat_resolve_performance_table(client_id)
        except Exception as e:
            return {"status": "ERROR",
                    "error": f"Could not resolve table for {client_id!r}: {e}",
                    "channels": []}
        if not table_name:
            return {"status": "ERROR",
                    "error": f"No performance table configured for client {client_id!r}",
                    "channels": []}
    
    if metric not in ("Cost", "Clicks", "Impressions", "Conversions", "Revenue", "ViVs", "Sessions"):
        return {"status": "ERROR",
                "error": f"Invalid metric: {metric}. Must be Cost, Clicks, Impressions, Conversions, Revenue, ViVs, or Sessions",
                "channels": []}

    # Auto-scale min_months to lookback_months if not provided.
    # Rule: need at least 80% of the lookback window to compute reliable CV.
    # Floor at 3 (need at least 3 points for variance), cap at lookback_months.
    if min_months is None:
        min_months = max(3, min(lookback_months, int(lookback_months * 0.8)))
    
    sql = (
        f"WITH monthly AS ("
        f"  SELECT FORMAT_DATE('%Y-%m', Date) AS month, Channel, "
        f"         SUM({metric}) AS value "
        f"  FROM `{table_name}` "
        f"  WHERE Date >= DATE_SUB(CURRENT_DATE(), INTERVAL {lookback_months} MONTH) "
        f"    AND Client = '{client_id}' "
        f"    AND {metric} > 0 "
        f"  GROUP BY month, Channel "
        f") "
        f"SELECT Channel, "
        f"  COUNT(*) AS months, "
        f"  ROUND(AVG(value), 2) AS avg_value, "
        f"  ROUND(STDDEV(value), 2) AS stddev_value, "
        f"  ROUND(STDDEV(value) / NULLIF(AVG(value), 0), 3) AS cv "
        f"FROM monthly "
        f"WHERE TRUE "
        f"GROUP BY Channel "
        f"HAVING months >= {min_months} AND avg_value > 0 "
        f"ORDER BY cv DESC "
        f"LIMIT 10"
    )
    
    try:
        client = bigquery.Client(project='nc-ai-chatbot')
        rows = client.query(sql).result()
        results = []
        for row in rows:
            results.append({
                "Channel": row.Channel,
                "months_observed": row.months,
                "avg_value": float(row.avg_value) if row.avg_value else 0,
                "stddev_value": float(row.stddev_value) if row.stddev_value else 0,
                "cv": float(row.cv) if row.cv else 0,
            })
        return {"status": "SUCCESS", "channels": results}
    except Exception as e:
        return {"status": "ERROR",
                "error": f"{type(e).__name__}: {e}",
                "channels": []}


def get_channel_volatility_summary(
    client_id: str,
    table_name: Optional[str] = None,
    lookback_months: int = 12,
) -> dict:
    """
    Get volatility ranking across ALL key metrics (Cost, Conversions, Clicks, Impressions).

    Use this when the user wants a CROSS-METRIC SUMMARY, e.g.:
      - "Which channels are most volatile overall?"
      - "Volatility overview across metrics"
      - "Give me a stability snapshot"

    For a SPECIFIC metric, use compute_channel_volatility instead.

    Args:
        client_id: Client name (NPI, Venetian, WinnDixie)
        table_name: Full table reference. If None, auto-resolved from KnowledgeManager.
        lookback_months: How far back to look (default 12).

    Returns:
        Dict with status, by_metric (Cost/Conversions/Clicks/Impressions, each with
        most_volatile_channel + cv + top_5), error.
    """
    metrics = ["Cost", "Conversions", "Clicks", "Impressions"]
    summary = {"status": "SUCCESS", "by_metric": {}}

    for metric in metrics:
        try:
            result = compute_channel_volatility(
                client_id=client_id,
                table_name=table_name,
                metric=metric,
                lookback_months=lookback_months,
            )
            # New dict-based format: {"status", "channels", "error"}
            if result.get("status") == "SUCCESS" and result.get("channels"):
                top = result["channels"][0]
                cv_value = top.get("cv") or top.get("coefficient_of_variation", 0)
                channel_name = top.get("Channel") or top.get("channel", "?")
                summary["by_metric"][metric] = {
                    "most_volatile_channel": channel_name,
                    "cv": round(float(cv_value), 3),
                    "top_5": result["channels"][:5],
                }
            else:
                summary["by_metric"][metric] = {
                    "error": result.get("error", "no data returned"),
                }
        except Exception as e:
            summary["by_metric"][metric] = {
                "error": f"{type(e).__name__}: {str(e)[:200]}",
            }

    # Overall status: SUCCESS only if at least one metric returned data
    successful_metrics = [m for m, v in summary["by_metric"].items() if "error" not in v]
    if not successful_metrics:
        summary["status"] = "ERROR"
        summary["error"] = "All 4 metric queries failed"

    return summary



"""
compute_saturation_curve — deterministic saturation modeling tool.

Handles Cost/Conversion duality automatically via unified CTE + FULL OUTER JOIN.
Fits a Hill saturation curve (the standard MMM functional form) per channel
on daily aggregated data, returns predicted conversions at each spend level.
"""

import logging
import math
import os
from typing import Optional

_logger = logging.getLogger(__name__)

_DEFAULT_SPEND_LEVELS = [
    10_000, 25_000, 50_000, 75_000,
    100_000, 150_000, 200_000, 300_000,
]


# ============================================================
# compute_saturation_curve — config-driven, duality-aware
# ============================================================

import math as _sat_math

_DEFAULT_SATURATION_SPEND_LEVELS = [
    10_000, 25_000, 50_000, 75_000,
    100_000, 150_000, 200_000, 300_000,
]


def compute_saturation_curve(
    client_id: str,
    budget_to_allocate: Optional[float] = None,
    lookback_months: int = 12,
    spend_levels: Optional[List[float]] = None,
    min_data_points: int = 30,
) -> dict:
    """
    Build saturation curves per channel — fully config-driven.

    Reads channel_unification from KnowledgeManager (config v3) to merge
    inconsistent channel names before fitting. NO channel names hardcoded.
    If the unification map is wrong, fix the config — don't edit this code.

    Use for: "saturation", "budget allocation", "next $X investment",
             "diminishing returns", "where should I spend"
    """
    try:
        from google.cloud import bigquery
    except ImportError:
        return {"status": "ERROR", "error": "google.cloud.bigquery not available"}

    table_path = _sat_resolve_performance_table(client_id)
    if not table_path:
        return {"status": "ERROR", "error": f"No performance table for {client_id!r}"}

    unification_map = _sat_load_unification_map(client_id)
    case_when_sql = _sat_build_case_when(unification_map)

    project_id = os.getenv("BQ_DATA_PROJECT_ID", "nc-ai-chatbot")
    bq = bigquery.Client(project=project_id)
    spend_levels = sorted(spend_levels or _DEFAULT_SATURATION_SPEND_LEVELS)

    aggregation_sql = f"""
    WITH normalized AS (
      SELECT
        Date,
        {case_when_sql} AS unified_channel,
        Cost,
        Conversions
      FROM `{table_path}`
      WHERE Client = '{client_id}'
        AND Date >= DATE_SUB(CURRENT_DATE(), INTERVAL {lookback_months} MONTH)
        AND Channel IS NOT NULL
    ),
    spend_rows AS (
      SELECT Date, unified_channel, SUM(Cost) AS daily_cost
      FROM normalized
      WHERE Cost > 0 AND unified_channel != 'DEFAULT'
      GROUP BY Date, unified_channel
    ),
    conv_rows AS (
      SELECT Date, unified_channel, SUM(Conversions) AS daily_conversions
      FROM normalized
      WHERE Conversions > 0 AND unified_channel != 'DEFAULT'
      GROUP BY Date, unified_channel
    )
    SELECT
      COALESCE(s.Date, c.Date) AS date,
      COALESCE(s.unified_channel, c.unified_channel) AS channel,
      COALESCE(s.daily_cost, 0.0) AS daily_spend,
      COALESCE(c.daily_conversions, 0.0) AS daily_conv
    FROM spend_rows s
    FULL OUTER JOIN conv_rows c
      ON s.Date = c.Date AND s.unified_channel = c.unified_channel
    WHERE COALESCE(s.daily_cost, 0) > 0
       OR COALESCE(c.daily_conversions, 0) > 0
    ORDER BY date, channel
    """

    _logger.info(
        f"compute_saturation_curve: aggregating for {client_id}, "
        f"{len(unification_map)} unification rules, lookback={lookback_months}mo"
    )

    try:
        df_rows = list(bq.query(aggregation_sql).result())
    except Exception as e:
        _logger.error(f"Aggregation query failed: {e}")
        return {"status": "ERROR", "error": f"Aggregation query failed: {str(e)[:300]}"}

    if not df_rows:
        return {"status": "ERROR", "error": f"No data for {client_id} in last {lookback_months} months"}

    by_channel = {}
    for r in df_rows:
        ch = r.channel
        if ch not in by_channel:
            by_channel[ch] = {"spends": [], "convs": [], "total_spend": 0.0, "total_conv": 0.0}
        s = float(r.daily_spend or 0.0)
        c = float(r.daily_conv or 0.0)
        by_channel[ch]["spends"].append(s)
        by_channel[ch]["convs"].append(c)
        by_channel[ch]["total_spend"] += s
        by_channel[ch]["total_conv"] += c

    channels_modeled = {}
    excluded = {
        "spend_only": [],
        "conv_only": [],
        "insufficient_data": [],
        "fit_failed": [],
    }

    for channel, data in by_channel.items():
        has_spend = data["total_spend"] > 0
        has_conv = data["total_conv"] > 0

        if has_spend and not has_conv:
            excluded["spend_only"].append({
                "channel": channel,
                "total_spend": round(data["total_spend"], 0),
                "note": "Spend with no conversions — likely awareness or naming mismatch",
            })
            continue
        if has_conv and not has_spend:
            excluded["conv_only"].append({
                "channel": channel,
                "total_conv": round(data["total_conv"], 0),
                "note": "Conversions with no spend — likely organic or attribution-only",
            })
            continue

        n = len(data["spends"])
        if n < min_data_points:
            excluded["insufficient_data"].append({"channel": channel, "data_points": n})
            continue

        paired = [(s, c) for s, c in zip(data["spends"], data["convs"]) if s > 0 and c > 0]
        if len(paired) < 5:
            excluded["insufficient_data"].append({"channel": channel, "paired_days": len(paired)})
            continue

        try:
            alpha, kappa, r2 = _sat_fit_log_log(paired)
        except Exception as e:
            excluded["fit_failed"].append({"channel": channel, "error": str(e)[:200]})
            continue

        # ── QUALITY GATES (Option 1) ──
        # Reject fits that are statistically unreliable or economically implausible.
        # These channels are moved to excluded["low_quality_fit"] with reasons.
        quality_issues = []
        if r2 < 0.5:
            quality_issues.append(
                f"R² too low ({r2:.3f}); need ≥0.5 for reliable saturation curve"
            )
        if alpha <= 0:
            quality_issues.append(
                f"alpha={alpha:.3f} ≤0; negative slope means more spend → fewer "
                f"conversions, which is uninterpretable"
            )
        elif alpha >= 1.0:
            quality_issues.append(
                f"alpha={alpha:.3f} ≥1; suggests increasing returns to scale, "
                f"economically implausible for advertising. Model likely misspecified."
            )
        if len(paired) < 30:
            quality_issues.append(
                f"only {len(paired)} paired days; need ≥30 for robust fit"
            )

        if quality_issues:
            excluded.setdefault("low_quality_fit", []).append({
                "channel": channel,
                "fit_quality_r2": round(r2, 3),
                "saturation_alpha": round(alpha, 4),
                "saturation_kappa": round(kappa, 4),
                "n_paired_observations": len(paired),
                "reasons": quality_issues,
                "note": (
                    "Fit completed but failed quality gates. Math is unreliable for "
                    "budget allocation. Investigate data quality or use a different "
                    "functional form (e.g., Adstock + Hill)."
                ),
            })
            continue

        avg_spend = sum(data["spends"]) / n
        avg_conv = sum(data["convs"]) / n
        cpd = sum(data["convs"]) / sum(data["spends"]) if sum(data["spends"]) > 0 else 0.0

        days = 30
        predictions = {}
        prev_conv = 0.0
        prev_spend = 0.0
        for level in spend_levels:
            ds = level / days
            pdc = kappa * (ds ** alpha) if ds > 0 else 0.0
            inc_c = pdc - prev_conv
            inc_s = ds - prev_spend
            incr_per = inc_c / inc_s if inc_s > 0 else 0.0
            predictions[str(level)] = {
                "monthly_spend": level,
                "predicted_daily_conv": round(pdc, 2),
                "predicted_monthly_conv": round(pdc * days, 0),
                "incremental_conv_per_dollar": round(incr_per, 6),
            }
            prev_conv = pdc
            prev_spend = ds

        channels_modeled[channel] = {
            "current_avg_daily_spend": round(avg_spend, 2),
            "current_avg_daily_conv": round(avg_conv, 4),
            "current_conv_per_dollar": round(cpd, 6),
            "saturation_alpha": round(alpha, 4),
            "saturation_kappa": round(kappa, 4),
            "fit_quality_r2": round(r2, 3),
            "n_paired_observations": len(paired),
            "predictions": predictions,
        }

    recommended = (
        _sat_greedy_allocate(channels_modeled, budget_to_allocate)
        if budget_to_allocate and channels_modeled else None
    )

    return {
        "status": "SUCCESS",
        "duality_handled": True,
        "unification_applied": bool(unification_map),
        "unification_map_used": unification_map,
        "client_id": client_id,
        "lookback_months": lookback_months,
        "channels": channels_modeled,
        "recommended_allocation": recommended,
        "excluded": excluded,
        "diagnostic": {
            "channels_fitted": list(channels_modeled.keys()),
            "n_unification_rules": len(unification_map),
        },
    }


def _sat_resolve_performance_table(client_id: str):
    try:
        try:
            from data_science.utils.knowledge_manager import manager as km
        except ImportError:
            from ...utils.knowledge_manager import manager as km
        for d in km.data.get("datasets", []):
            if d["client_id"] == client_id:
                for t in d.get("tables", []):
                    if t["table_id"] == "performance":
                        return t["table_full_path"]
    except Exception as e:
        _logger.warning(f"KM lookup failed for {client_id}: {e}")
    project_id = os.getenv("BQ_DATA_PROJECT_ID", "nc-ai-chatbot")
    fallback = {
        "NPI":       f"{project_id}.Astrobot_NPI.vw_astrobot_npi_nc360_dashboard",
        "Venetian":  f"{project_id}.Astrobot_Venetian.sample_astrobot_venetian_nc360_dashboard",
        "WinnDixie": f"{project_id}.Astrobot_WinnDixie.sample_astrobot_wd_nc360_dashboard",
    }
    return fallback.get(client_id)


def _sat_load_unification_map(client_id: str, table_id: str = "performance") -> dict:
    """Read channel_unification map from config v3."""
    try:
        try:
            from data_science.utils.knowledge_manager import manager as km
        except ImportError:
            from ...utils.knowledge_manager import manager as km
        for d in km.data.get("datasets", []):
            if d["client_id"] == client_id:
                for t in d.get("tables", []):
                    if t["table_id"] == table_id:
                        return dict(t.get("channel_unification", {}))
    except Exception as e:
        _logger.warning(f"Failed to load unification map: {e}")
    return {}


def _sat_build_case_when(unification_map: dict) -> str:
    """Build SQL CASE WHEN from {target: [aliases]}. Empty map -> pass-through."""
    if not unification_map:
        return "Channel"
    when_clauses = []
    for target, aliases in unification_map.items():
        if not aliases:
            continue
        quoted = ", ".join(f"'{a.replace(chr(39), chr(39)+chr(39))}'" for a in aliases)
        target_escaped = target.replace("'", "''")
        when_clauses.append(f"WHEN Channel IN ({quoted}) THEN '{target_escaped}'")
    if not when_clauses:
        return "Channel"
    return "CASE\n      " + "\n      ".join(when_clauses) + "\n      ELSE Channel\n    END"


def _sat_fit_log_log(paired):
    """Fit conv = kappa * spend^alpha. Returns (alpha, kappa, r2)."""
    if not paired or len(paired) < 2:
        return None
    if not paired or len(paired) < 2:
        return None
    log_s = [_sat_math.log(s) for s, _ in paired]
    log_c = [_sat_math.log(c) for _, c in paired]
    n = len(paired)
    mx = sum(log_s) / n
    my = sum(log_c) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(log_s, log_c))
    sxx = sum((x - mx) ** 2 for x in log_s)
    if sxx < 1e-10:
        raise ValueError("No variance in log(spend) — can't fit slope")
    alpha = sxy / sxx
    log_kappa = my - alpha * mx
    kappa = _sat_math.exp(log_kappa)
    ss_tot = sum((y - my) ** 2 for y in log_c)
    ss_res = sum((y - (log_kappa + alpha * x)) ** 2 for x, y in zip(log_s, log_c))
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
    return alpha, kappa, r2


def _sat_greedy_allocate(channels: dict, total_budget: float) -> dict:
    """Greedy: $1k at a time to channel with highest marginal return."""
    if not channels or not total_budget:
        return None
    increment = 1_000.0
    allocation = {ch: 0.0 for ch in channels}
    steps = int(total_budget / increment)
    for _ in range(steps):
        best = None
        best_marginal = -1.0
        for ch, info in channels.items():
            a = info["saturation_alpha"]
            k = info["saturation_kappa"]
            cm = allocation[ch]
            nm = cm + increment
            cd = cm / 30
            nd = nm / 30
            if nd > 0:
                conv_n = k * (nd ** a)
                conv_c = k * (cd ** a) if cd > 0 else 0
                m = (conv_n - conv_c) / increment
            else:
                m = 0
            if m > best_marginal:
                best_marginal = m
                best = ch
        if best is None:
            break
        allocation[best] += increment
    total = 0.0
    for ch, mn in allocation.items():
        if mn == 0:
            continue
        a = channels[ch]["saturation_alpha"]
        k = channels[ch]["saturation_kappa"]
        d = mn / 30
        total += k * (d ** a) * 30
    return {
        "total_budget": total_budget,
        "by_channel": {ch: round(amt, 0) for ch, amt in allocation.items() if amt > 0},
        "expected_monthly_conversions": round(total, 0),
    }


# ============================================================
# train_saturation_model_bqml — persisted BQML saturation model
# ============================================================

def train_arima_model_bqml(
    client_id: str,
    metric: str,
    model_name: str = None,
    lookback_months: int = 24,
    horizon_days: int = 90,
    overwrite: bool = True,
) -> dict:
    """
    Train (or retrain) an ARIMA_PLUS forecasting model for a client's daily metric.

    Use when:
      - User asks "retrain the spend forecast model"
      - User notices stale forecasts ("forecasts say 2025 dates")
      - You need to refresh a model before calling ML.FORECAST

    Args:
        client_id: NPI / Venetian / WinnDixie
        metric: Which column to forecast. Must be a numeric column in the
                client's performance table. Common values:
                - "Cost" / "spend"        -> npi_arima_spend (default name)
                - "Conversions"           -> npi_arima_conversions
                - "Clicks"                -> npi_arima_clicks
                - "Impressions"           -> npi_arima_impressions
        model_name: Optional override. Default: {client_lower}_arima_{metric_slug}.
        lookback_months: Training window. Default 24 months.
        horizon_days: How many future days the model should be able to forecast.
                      Default 90.
        overwrite: CREATE OR REPLACE MODEL. Default True.

    Returns:
        {
          "status": "SUCCESS" | "ERROR",
          "model_path": "nc-ai-chatbot.astrobot_bqml_models.npi_arima_spend",
          "metric_forecasted": "Cost",
          "training_rows": 720,
          "training_query": "CREATE OR REPLACE MODEL ..."  # for audit
        }

    Notes:
      - Uses auto_arima=TRUE — BQML picks ARIMA order automatically.
      - Aggregates the metric daily (SUM by Date).
      - Skips rows where the metric is NULL.
      - Models live in nc-ai-chatbot.astrobot_bqml_models (the shared BQML dataset),
        NOT in the per-client Astrobot_X dataset.
      - After training, query via:
          SELECT * FROM ML.FORECAST(MODEL `...`, STRUCT({horizon} AS horizon))

    Common error: column does not exist
      If `metric` references a column the source view doesn't have (e.g., "Revenue"
      when the view only has Cost/Conversions/Clicks/Sessions), training fails.
      Check the source schema first via _list_columns().
    """
    try:
        from google.cloud import bigquery
    except ImportError:
        return {"status": "ERROR", "error": "google.cloud.bigquery not available"}

    # 1. Resolve the source table (performance table for this client)
    table_path = _sat_resolve_performance_table(client_id)
    if not table_path:
        return {"status": "ERROR", "error": f"No performance table for {client_id!r}"}

    # 2. Map metric aliases to actual column names
    metric_aliases = {
        "spend": "Cost",
        "cost": "Cost",
        "revenue": "Revenue",  # may not exist — caller's responsibility
        "conversions": "Conversions",
        "clicks": "Clicks",
        "impressions": "Impressions",
        "sessions": "Sessions",
    }
    actual_column = metric_aliases.get(metric.lower(), metric)

    # 3. Derive model name. Models live in shared astrobot_bqml_models dataset.
    project_id = os.getenv("BQ_DATA_PROJECT_ID", "nc-ai-chatbot")
    bqml_dataset = "astrobot_bqml_models"
    metric_slug = actual_column.lower().replace(" ", "_")
    default_name = f"{client_id.lower()}_arima_{metric_slug}"
    model_name = (model_name or default_name).replace("`", "")
    model_path = f"{project_id}.{bqml_dataset}.{model_name}"

    bq = bigquery.Client(project=project_id)
    create_keyword = "CREATE OR REPLACE MODEL" if overwrite else "CREATE MODEL IF NOT EXISTS"

    # 4. Pre-flight: confirm the column exists in source table
    check_sql = f"""
    SELECT column_name
    FROM `{table_path.split('.')[0]}.{table_path.split('.')[1]}`.INFORMATION_SCHEMA.COLUMNS
    WHERE table_name = '{table_path.split('.')[2]}'
      AND column_name = '{actual_column}'
    LIMIT 1
    """
    try:
        rows = list(bq.query(check_sql).result())
        if not rows:
            return {
                "status": "ERROR",
                "error": (
                    f"Column {actual_column!r} not found in {table_path}. "
                    f"Cannot train ARIMA model for a non-existent column. "
                    f"Check the source view schema first."
                ),
                "table_path": table_path,
                "requested_metric": metric,
                "resolved_column": actual_column,
            }
    except Exception as e:
        return {"status": "ERROR", "error": f"Pre-flight column check failed: {str(e)[:300]}"}

    # 5. Pre-flight: row count for the training window
    count_sql = f"""
    SELECT COUNT(*) AS n
    FROM `{table_path}`
    WHERE Client = '{client_id}'
      AND Date >= DATE_SUB(CURRENT_DATE(), INTERVAL {lookback_months} MONTH)
      AND `{actual_column}` IS NOT NULL
    """
    try:
        n_rows = next(iter(bq.query(count_sql).result())).n
    except Exception as e:
        return {"status": "ERROR", "error": f"Row count query failed: {str(e)[:300]}"}

    if n_rows < 30:
        return {
            "status": "ERROR",
            "error": (
                f"Insufficient data: only {n_rows} rows in last {lookback_months} months "
                f"for {client_id}.{actual_column}. ARIMA needs at least ~30 days "
                f"of data to train. Try a longer lookback_months or a different metric."
            ),
        }

    # 6. Build training query
    training_sql = f"""
    {create_keyword} `{model_path}`
    OPTIONS(
      model_type='ARIMA_PLUS',
      time_series_timestamp_col='Date',
      time_series_data_col='daily_value',
      auto_arima=TRUE,
      holiday_region='US',
      horizon={horizon_days}
    ) AS
    SELECT
      Date,
      SUM(`{actual_column}`) AS daily_value
    FROM `{table_path}`
    WHERE Client = '{client_id}'
      AND Date >= DATE_SUB(CURRENT_DATE(), INTERVAL {lookback_months} MONTH)
      AND `{actual_column}` IS NOT NULL
    GROUP BY Date
    ORDER BY Date
    """

    _logger.info(
        f"train_arima_model_bqml: training {model_path} for {client_id}, "
        f"metric={actual_column}, lookback={lookback_months}mo, rows={n_rows}"
    )

    # 7. Execute training
    try:
        job = bq.query(training_sql)
        job.result()
    except Exception as e:
        _logger.error(f"ARIMA training failed: {e}")
        return {
            "status": "ERROR",
            "error": f"ARIMA training failed: {str(e)[:300]}",
            "training_query": training_sql,
        }

    # 8. Sanity check: forecast 3 days and confirm dates are in the future
    forecast_check_sql = f"""
    SELECT FORMAT_TIMESTAMP('%Y-%m-%d', forecast_timestamp) AS d,
           ROUND(forecast_value, 2) AS v
    FROM ML.FORECAST(MODEL `{model_path}`, STRUCT(3 AS horizon))
    """
    try:
        forecast_preview = [
            {"date": str(r.d), "value": float(r.v) if r.v is not None else None}
            for r in bq.query(forecast_check_sql).result()
        ]
    except Exception as e:
        forecast_preview = []
        _logger.warning(f"Forecast sanity check failed: {e}")

    return {
        "status": "SUCCESS",
        "model_path": model_path,
        "metric_forecasted": actual_column,
        "training_rows": int(n_rows),
        "forecast_preview": forecast_preview,
        "training_query": training_sql,
    }


def train_saturation_model_bqml(
    client_id: str,
    model_name: str = None,
    lookback_months: int = 12,
    overwrite: bool = True,
) -> dict:
    """
    [DEPRECATED — use compute_saturation_curve instead]

    This function trains a single BQML linear regression model with channel as a
    categorical feature, which forces the SAME saturation slope (alpha) across all
    channels. That is architecturally wrong for marketing saturation analysis —
    different channels saturate at different rates.

    The model is written to {client_id}_saturation_v2, which the orchestrator
    routing does NOT reference. So this function trains a model that nothing
    in the agent actually reads.

    Use compute_saturation_curve instead — it fits each channel independently
    in-memory using the same SQL + unification logic, then returns per-channel
    alpha/kappa/r-squared.

    Kept for backward compatibility and for legacy callers that may explicitly
    reference this function name. New callers: use compute_saturation_curve.

    Train and PERSIST a BQML linear regression saturation model.

    Uses the SAME duality + unification logic as compute_saturation_curve,
    but instead of fitting in-memory, this CREATEs a BQML model in BigQuery
    that can be queried later via ML.PREDICT.

    The model fits log(conversions) = beta_0 + beta_1 * log(cost), per channel.
    alpha (saturation exponent) = beta_1
    kappa (efficiency constant) = exp(beta_0)

    Args:
        client_id: NPI / Venetian / WinnDixie
        model_name: Optional custom name (default: {client_id}_saturation_v2)
        lookback_months: Training window (default 12)
        overwrite: If True, uses CREATE OR REPLACE MODEL (default True)

    Returns:
        {
          "status": "SUCCESS" | "ERROR",
          "model_path": "nc-ai-chatbot.Astrobot_NPI.npi_saturation_v2",
          "training_rows": 1234,
          "channels_in_training": ["Paid Search", "Paid Social", "Demand Gen + P-Max"],
          "unification_map_used": {...},
          "training_query": "CREATE OR REPLACE MODEL ..."  # for audit
        }

    Use for: "train a saturation model", "create saturation model",
             "build the model", "refresh the model"
    """
    import warnings
    warnings.warn(
        "train_saturation_model_bqml is deprecated due to a shared-slope bug "
        "(same alpha across all channels). Use compute_saturation_curve for "
        "per-channel saturation fits.",
        DeprecationWarning,
        stacklevel=2,
    )
    _logger.warning(
        "[DEPRECATED] train_saturation_model_bqml called. "
        "Prefer compute_saturation_curve for per-channel fits."
    )
    try:
        from google.cloud import bigquery
    except ImportError:
        return {"status": "ERROR", "error": "google.cloud.bigquery not available"}

    # 1. Resolve table path and unification map (same as compute_saturation_curve)
    table_path = _sat_resolve_performance_table(client_id)
    if not table_path:
        return {"status": "ERROR", "error": f"No performance table for {client_id!r}"}

    unification_map = _sat_load_unification_map(client_id)
    case_when_sql = _sat_build_case_when(unification_map)

    # 2. Derive model path — same dataset as source table
    # table_path = "project.dataset.table" → model goes in "project.dataset.model_name"
    parts = table_path.split(".")
    if len(parts) < 3:
        return {"status": "ERROR", "error": f"Cannot parse table path {table_path!r}"}
    model_dataset = ".".join(parts[:2])  # "project.dataset"

    model_name = model_name or f"{client_id.lower()}_saturation_v2"
    # Strip backticks if present
    model_name = model_name.replace("`", "")
    model_path = f"{model_dataset}.{model_name}"

    project_id = os.getenv("BQ_DATA_PROJECT_ID", "nc-ai-chatbot")
    bq = bigquery.Client(project=project_id)

    create_keyword = "CREATE OR REPLACE MODEL" if overwrite else "CREATE MODEL IF NOT EXISTS"

    # 3. Training query — log-log linear regression with channel as categorical feature
    training_sql = f"""
    {create_keyword} `{model_path}`
    OPTIONS(
      model_type='LINEAR_REG',
      input_label_cols=['log_conversions'],
      data_split_method='AUTO_SPLIT',
      enable_global_explain=TRUE
    ) AS
    WITH normalized AS (
      SELECT
        Date,
        {case_when_sql} AS unified_channel,
        Cost,
        Conversions
      FROM `{table_path}`
      WHERE Client = '{client_id}'
        AND Date >= DATE_SUB(CURRENT_DATE(), INTERVAL {lookback_months} MONTH)
        AND Channel IS NOT NULL
    ),
    spend_rows AS (
      SELECT Date, unified_channel, SUM(Cost) AS daily_cost
      FROM normalized
      WHERE Cost > 0 AND unified_channel != 'DEFAULT'
      GROUP BY Date, unified_channel
    ),
    conv_rows AS (
      SELECT Date, unified_channel, SUM(Conversions) AS daily_conversions
      FROM normalized
      WHERE Conversions > 0 AND unified_channel != 'DEFAULT'
      GROUP BY Date, unified_channel
    ),
    paired AS (
      SELECT
        s.Date AS date,
        s.unified_channel AS channel,
        s.daily_cost AS cost,
        c.daily_conversions AS conversions
      FROM spend_rows s
      INNER JOIN conv_rows c
        ON s.Date = c.Date AND s.unified_channel = c.unified_channel
      WHERE s.daily_cost > 0 AND c.daily_conversions > 0
    )
    SELECT
      channel,
      LN(cost) AS log_cost,
      LN(conversions) AS log_conversions
    FROM paired
    """

    _logger.info(
        f"train_saturation_model_bqml: training {model_path} for {client_id}, "
        f"{len(unification_map)} unification rules, lookback={lookback_months}mo"
    )

    # 4. Pre-flight: check there's enough training data
    count_sql = f"""
    WITH normalized AS (
      SELECT
        Date,
        {case_when_sql} AS unified_channel,
        Cost,
        Conversions
      FROM `{table_path}`
      WHERE Client = '{client_id}'
        AND Date >= DATE_SUB(CURRENT_DATE(), INTERVAL {lookback_months} MONTH)
        AND Channel IS NOT NULL
    ),
    spend_rows AS (
      SELECT Date, unified_channel, SUM(Cost) AS daily_cost
      FROM normalized
      WHERE Cost > 0 AND unified_channel != 'DEFAULT'
      GROUP BY Date, unified_channel
    ),
    conv_rows AS (
      SELECT Date, unified_channel, SUM(Conversions) AS daily_conversions
      FROM normalized
      WHERE Conversions > 0 AND unified_channel != 'DEFAULT'
      GROUP BY Date, unified_channel
    )
    SELECT
      s.unified_channel AS channel,
      COUNT(*) AS paired_days
    FROM spend_rows s
    INNER JOIN conv_rows c
      ON s.Date = c.Date AND s.unified_channel = c.unified_channel
    WHERE s.daily_cost > 0 AND c.daily_conversions > 0
    GROUP BY s.unified_channel
    HAVING paired_days >= 5
    """
    try:
        channel_counts = {row.channel: int(row.paired_days) for row in bq.query(count_sql).result()}
    except Exception as e:
        return {"status": "ERROR", "error": f"Pre-flight query failed: {str(e)[:300]}"}

    if not channel_counts:
        return {
            "status": "ERROR",
            "error": (
                f"Insufficient paired data for any channel in last {lookback_months} months "
                f"for {client_id}. Need ≥5 days with both spend AND conversions per channel. "
                f"Check channel_unification map in config v3."
            ),
            "unification_map_used": unification_map,
        }

    total_rows = sum(channel_counts.values())

    # 5. Execute training (this is the long-running step, ~30-60 sec)
    _logger.info(f"BQML training started: {total_rows} rows across {len(channel_counts)} channels")
    try:
        job = bq.query(training_sql)
        job.result()  # blocks until complete
    except Exception as e:
        _logger.error(f"BQML training failed: {e}")
        return {
            "status": "ERROR",
            "error": f"BQML training failed: {str(e)[:300]}",
            "training_query": training_sql,
        }

    # 6. Fetch training metrics
    metrics = {}
    try:
        metrics_sql = f"SELECT * FROM ML.TRAINING_INFO(MODEL `{model_path}`)"
        for row in bq.query(metrics_sql).result():
            metrics = {
                "training_run": int(row.training_run) if hasattr(row, 'training_run') else 0,
                "iteration": int(row.iteration) if hasattr(row, 'iteration') else 0,
                "loss": float(row.loss) if hasattr(row, 'loss') and row.loss is not None else None,
                "eval_loss": float(row.eval_loss) if hasattr(row, 'eval_loss') and row.eval_loss is not None else None,
                "duration_ms": int(row.duration_ms) if hasattr(row, 'duration_ms') else 0,
            }
            break  # just the first iteration's summary
    except Exception as e:
        _logger.warning(f"Could not fetch training metrics: {e}")

    # 7. Fetch evaluation metrics (R², MAE, etc.)
    eval_metrics = {}
    try:
        eval_sql = f"SELECT * FROM ML.EVALUATE(MODEL `{model_path}`)"
        for row in bq.query(eval_sql).result():
            eval_metrics = {
                "mean_absolute_error": float(row.mean_absolute_error) if hasattr(row, 'mean_absolute_error') and row.mean_absolute_error is not None else None,
                "mean_squared_error": float(row.mean_squared_error) if hasattr(row, 'mean_squared_error') and row.mean_squared_error is not None else None,
                "r2_score": float(row.r2_score) if hasattr(row, 'r2_score') and row.r2_score is not None else None,
            }
            break
    except Exception as e:
        _logger.warning(f"Could not fetch eval metrics: {e}")

    return {
        "status": "SUCCESS",
        "model_path": model_path,
        "model_name": model_name,
        "client_id": client_id,
        "lookback_months": lookback_months,
        "training_rows": total_rows,
        "channels_in_training": channel_counts,
        "unification_applied": bool(unification_map),
        "unification_map_used": unification_map,
        "training_metrics": metrics,
        "evaluation_metrics": eval_metrics,
        "next_steps": (
            f"To predict, query: SELECT * FROM ML.PREDICT(MODEL `{model_path}`, "
            f"(SELECT 'Paid Search' AS channel, LN(5000) AS log_cost))"
        ),
    }


# ============================================================
# select_chart_type — deterministic chart-type selector
# ============================================================

def select_chart_type(data_summary: dict, user_question: str = "") -> dict:
    """
    Recommend the best chart type given data shape + user intent.

    Call this AFTER fetching data and BEFORE call_analytics_agent when
    the user wants a visualization but didn't specify a chart type.

    Args:
        data_summary: {
          "n_rows": int,
          "numeric_columns": list[str],
          "category_columns": list[str],
          "has_time_column": bool,
        }
        user_question: original natural-language question

    Returns:
        {
          "chart_type": "bar" | "line" | "pie" | "scatter" | "heatmap" |
                        "heatmap_correlation" | "heatmap_values" |
                        "multi_line" | "dual_axis_line" | "grouped_bar" |
                        "stacked_bar" | "histogram" | "none",
          "reason": str,
          "confidence": "user_specified" | "high" | "medium" | "low",
          "config": dict (optional chart-specific options like cmap),
        }

    The LLM should pass chart_type into call_analytics_agent's spec.
    If chart_type == "none", present data as a table instead.
    """
    q = (user_question or "").lower()
    n = data_summary.get("n_rows", 0)
    nums = data_summary.get("numeric_columns", []) or []
    cats = data_summary.get("category_columns", []) or []
    has_time = data_summary.get("has_time_column", False)

    # Rule 1: Explicit user override — always wins
    explicit_types = {
        "bar chart": "bar", "bar graph": "bar",
        "line chart": "line", "line graph": "line",
        "pie chart": "pie", "pie graph": "pie",
        "scatter plot": "scatter", "scatter chart": "scatter",
        "heatmap": "heatmap", "heat map": "heatmap",
        "histogram": "histogram",
        "stacked bar": "stacked_bar",
        "stacked area": "stacked_area",
        "box plot": "box", "boxplot": "box",
        "dual axis": "dual_axis_line", "dual-axis": "dual_axis_line",
    }
    for phrase, ct in explicit_types.items():
        if phrase in q:
            return {
                "chart_type": ct,
                "reason": f"User explicitly requested {ct.replace('_', ' ')} chart",
                "confidence": "user_specified",
            }

    # Rule 2: Single scalar — no chart, present as text
    if n <= 1 and len(nums) <= 1 and len(cats) == 0:
        return {
            "chart_type": "none",
            "reason": "Single scalar value — present as text",
            "confidence": "high",
        }

    # Rule 3: Correlation matrix — explicit phrase
    if any(kw in q for kw in ["correlation matrix", "corr matrix",
                                "pairwise correlation", "correlation between multiple"]):
        return {
            "chart_type": "heatmap_correlation",
            "reason": "Correlation matrix — heatmap with [-1,1] scale",
            "confidence": "high",
            "config": {"cmap": "RdYlGn", "vmin": -1, "vmax": 1, "annot": True},
        }

    # Rule 4: Correlation between TWO things → scatter
    if any(kw in q for kw in ["correlation", "halo", "lift", "predicts", " vs.", " vs "]):
        if len(nums) >= 2:
            return {
                "chart_type": "scatter",
                "reason": "Question implies relationship between two numeric variables",
                "confidence": "high",
                "x_axis": nums[0],
                "y_axis": nums[1],
            }

    # Rule 5: Two categorical dimensions + 1 metric → values heatmap
    if len(cats) == 2 and len(nums) == 1:
        return {
            "chart_type": "heatmap_values",
            "reason": "Two categorical dimensions + 1 metric — heatmap of values",
            "confidence": "high",
            "config": {"cmap": "YlOrRd", "annot": True, "fmt": "comma"},
        }

    # Rule 6: Time series
    if has_time and len(nums) >= 1:
        if len(nums) == 1:
            return {
                "chart_type": "line" if n >= 12 else "bar",
                "reason": f"Time-series with 1 metric, {n} points — "
                          f"{'line' if n >= 12 else 'bar'} chart",
                "confidence": "high",
            }
        elif len(nums) == 2:
            if "dual" in q or any(kw in q for kw in ["spend and cpa", "cost and conversions",
                                                       "revenue and"]):
                return {
                    "chart_type": "dual_axis_line",
                    "reason": "Time-series with 2 metrics likely on different scales",
                    "confidence": "medium",
                }
            return {
                "chart_type": "multi_line",
                "reason": f"Time-series with {len(nums)} metrics — multi-line",
                "confidence": "high",
            }
        elif len(nums) <= 5:
            return {
                "chart_type": "multi_line",
                "reason": f"Time-series with {len(nums)} metrics",
                "confidence": "high",
            }
        else:
            return {
                "chart_type": "multi_line",
                "reason": f"Time-series with {len(nums)} metrics — consider filtering to top 5",
                "confidence": "low",
            }

    # Rule 6.5: Specialty chart types
    if any(kw in q for kw in ["waterfall", "build-up", "build up", "incremental change",
                                "stage contribution", "step-by-step contribution"]):
        return {"chart_type": "waterfall", "reason": "Waterfall for incremental contribution", "confidence": "high"}

    if any(kw in q for kw in ["funnel", "conversion funnel", "stages", "drop-off",
                                "drop off", "impression to conversion"]):
        return {"chart_type": "funnel", "reason": "Funnel for conversion stages", "confidence": "high"}

    if any(kw in q for kw in ["sankey", "flow between", " flow ", "from to",
                                "attribution flow", "where does"]):
        return {"chart_type": "sankey", "reason": "Sankey for flows between categories", "confidence": "high"}

    if any(kw in q for kw in ["treemap", "tree map", "share of share",
                                "nested breakdown", "hierarchy"]):
        return {"chart_type": "treemap", "reason": "Treemap for hierarchical share", "confidence": "high"}

    if any(kw in q for kw in ["gantt", "timeline", "campaign schedule",
                                "campaign flights", "flight duration"]):
        return {"chart_type": "gantt", "reason": "Gantt for campaign flights over time", "confidence": "high"}

    if any(kw in q for kw in ["bullet", "vs target", "vs benchmark",
                                "actual vs goal", "performance vs target"]):
        return {"chart_type": "bullet", "reason": "Bullet for KPI vs target", "confidence": "high"}

    # Rule 7: Composition / share
    if any(kw in q for kw in ["share", "mix", "split", "breakdown", "composition",
                                "percent of total", "% of", "portion"]):
        if len(cats) == 1 and len(nums) == 1:
            if n <= 8:
                return {
                    "chart_type": "pie",
                    "reason": "Composition question with ≤8 categories — pie shows share",
                    "confidence": "medium",
                }
            return {
                "chart_type": "bar",
                "reason": "Composition with >8 categories — bar is clearer than pie",
                "confidence": "high",
            }

    # Rule 8: Ranking / comparison
    if any(kw in q for kw in ["top ", "best", "worst", "ranking", "rank",
                                "highest", "lowest", "compare"]):
        if len(cats) == 1 and len(nums) >= 1:
            return {
                "chart_type": "bar",
                "reason": "Ranking/comparison question — bar chart",
                "confidence": "high",
                "sorted": True,
            }

    # Rule 9: Distribution
    if any(kw in q for kw in ["distribution", "spread", "histogram",
                                "frequency", "outliers"]):
        if len(nums) >= 1:
            return {
                "chart_type": "histogram",
                "reason": "Distribution question — histogram",
                "confidence": "high",
            }

    # Rule 10: Shape-based defaults
    if len(cats) == 1 and len(nums) == 1:
        return {
            "chart_type": "bar",
            "reason": "1 category + 1 metric → bar chart (default)",
            "confidence": "medium",
        }
    if len(cats) == 1 and len(nums) >= 2:
        return {
            "chart_type": "grouped_bar",
            "reason": f"1 category + {len(nums)} metrics → grouped bar",
            "confidence": "medium",
        }
    if len(nums) >= 2 and len(cats) == 0:
        return {
            "chart_type": "scatter",
            "reason": "2+ numeric columns, no categories → scatter",
            "confidence": "low",
        }

    # Rule 11: Fallback
    return {
        "chart_type": "none",
        "reason": "No clear chart type from data shape — present as table",
        "confidence": "low",
    }
