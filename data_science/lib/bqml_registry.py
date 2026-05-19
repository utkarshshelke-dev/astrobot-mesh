"""BQML model registry — dynamic discovery + Firestore overrides.

This module is the single source of truth for "what BQML models exist for
client X." It replaces the hardcoded inventory in
data_science/sub_agents/bqml/prompts.py.

Functions:
  discover_client_models(client_id) -> list[ModelInfo]
    Lists all BQML models matching <client_id>_* or arima_<client_id>_*
    naming convention.

  get_model_metadata(model_full_path) -> dict
    Returns model type, creation date, training column, target column.

  evaluate_model_health(model_full_path) -> dict
    Runs ML.EVALUATE, returns metrics + health verdict.

  get_client_models_with_health(client_id) -> list[dict]
    Combines discover + health into one structured response, suitable
    for injection into agent state.
"""
from __future__ import annotations
import logging
import os
import re
from dataclasses import dataclass, asdict
from typing import Optional

from google.cloud import bigquery

logger = logging.getLogger(__name__)

_BQML_PROJECT = "nc-ai-chatbot"
_BQML_DATASET = "astrobot_bqml_models"


@dataclass
class ModelInfo:
    """One BQML model's basic metadata."""
    model_name: str             # e.g. "npi_arima_spend"
    model_full_path: str        # e.g. "nc-ai-chatbot.astrobot_bqml_models.npi_arima_spend"
    model_type: str             # e.g. "ARIMA_PLUS"
    created: str                # ISO datetime string
    client_id: str              # parsed from name


def _matches_client(model_name: str, client_id: str) -> bool:
    """True if model belongs to client_id by naming convention.

    Matches either prefix (npi_arima_spend) or substring (arima_npi_all_conv).
    Case-insensitive. Word-boundary aware to avoid 'npi' matching inside
    'gnpiuoffj_anything'.
    """
    cid_lower = client_id.lower()
    name_lower = model_name.lower()
    # Word-boundary check: client_id surrounded by _ or start/end
    pattern = re.compile(rf"(^|_){re.escape(cid_lower)}(_|$)")
    return bool(pattern.search(name_lower))


def discover_client_models(client_id: str,
                            project: str = None,
                            dataset: str = None) -> list[ModelInfo]:
    """List all BQML models that belong to client_id by naming convention.

    Uses BQ list_models() API (works regardless of INFORMATION_SCHEMA
    availability). Filters by name match against client_id.

    Args:
      client_id: Logical client identifier (NPI, Venetian, WinnDixie).
      project:   BQ project (defaults to BQ_DATA_PROJECT_ID env or nc-ai-chatbot).
      dataset:   BQ dataset containing models (defaults to astrobot_bqml_models).

    Returns:
      List of ModelInfo. Empty list if no models found, dataset missing,
      or BQ error.
    """
    proj = project or os.getenv("BQ_DATA_PROJECT_ID", _BQML_PROJECT)
    ds = dataset or _BQML_DATASET
    
    try:
        bq = bigquery.Client(project=proj)
        models_iter = bq.list_models(f"{proj}.{ds}")
        result = []
        for m in models_iter:
            if _matches_client(m.model_id, client_id):
                full_path = f"{proj}.{ds}.{m.model_id}"
                # m.created is a datetime; convert to ISO
                created_str = m.created.isoformat() if m.created else ""
                model_type = str(m.model_type) if hasattr(m, "model_type") else "UNKNOWN"
                result.append(ModelInfo(
                    model_name=m.model_id,
                    model_full_path=full_path,
                    model_type=model_type,
                    created=created_str,
                    client_id=client_id,
                ))
        # Sort by name for stable output
        result.sort(key=lambda x: x.model_name)
        logger.info(f"discover_client_models({client_id}): found {len(result)} models")
        return result
    except Exception as e:
        logger.warning(f"discover_client_models({client_id}) failed: {e}")
        return []


def get_model_metadata(model_full_path: str) -> dict:
    """Return detailed metadata for one model.

    Includes: type, feature columns, label column, training data table
    if known, creation/modification dates.

    Returns empty dict on failure (caller decides how to handle).
    """
    try:
        bq = bigquery.Client(project=_BQML_PROJECT)
        m = bq.get_model(model_full_path)
        # feature_columns and label_columns are lists of SchemaField
        features = [f.name for f in (m.feature_columns or [])]
        labels = [f.name for f in (m.label_columns or [])]
        return {
            "model_full_path": model_full_path,
            "model_type": str(m.model_type),
            "feature_columns": features,
            "label_columns": labels,
            "created": m.created.isoformat() if m.created else "",
            "modified": m.modified.isoformat() if m.modified else "",
            "description": m.description or "",
        }
    except Exception as e:
        logger.warning(f"get_model_metadata({model_full_path}) failed: {e}")
        return {}


# Metric thresholds for health verdicts. Tuned conservatively — flag anything
# that looks degenerate (zero error, NaN, etc.) without being too strict
# about specific values which depend on the data.
_HEALTH_THRESHOLDS = {
    "ARIMA_PLUS": {
        # AIC and log_likelihood are scale-dependent — can't set absolute bounds.
        # Healthy = ML.EVALUATE returns non-empty result. We trust BQ here.
        "metric_keys": ["AIC", "log_likelihood"],
    },
    "LINEAR_REGRESSION": {
        # r2_score = nan or MAE = 0 → degenerate
        "metric_keys": ["mean_absolute_error", "r2_score", "mean_squared_error"],
        "degenerate_checks": ["zero_error", "nan_r2"],
    },
    "BOOSTED_TREE_REGRESSOR": {
        "metric_keys": ["mean_absolute_error", "r2_score"],
        "degenerate_checks": ["zero_error", "nan_r2"],
    },
    "KMEANS": {
        "metric_keys": ["davies_bouldin_index"],
    },
    "LOGISTIC_REGRESSION": {
        "metric_keys": ["roc_auc", "accuracy"],
    },
}


def _verdict_from_metrics(model_type: str, metrics: dict) -> tuple[str, list[str]]:
    """Return (verdict, reasons).

    verdict ∈ {"healthy", "degenerate", "unknown"}
    reasons: list of human-readable strings explaining the verdict
    """
    if not metrics:
        return ("unknown", ["ML.EVALUATE returned no metrics"])
    
    spec = _HEALTH_THRESHOLDS.get(model_type, {})
    checks = spec.get("degenerate_checks", [])
    reasons = []
    
    import math
    
    if "nan_r2" in checks:
        r2 = metrics.get("r2_score")
        if r2 is not None and isinstance(r2, float) and math.isnan(r2):
            reasons.append("r2_score is NaN (model has no variance to fit)")
    
    if "zero_error" in checks:
        mae = metrics.get("mean_absolute_error")
        mse = metrics.get("mean_squared_error")
        if mae == 0.0 and mse == 0.0:
            reasons.append("MAE=0 AND MSE=0 (overfit or feature leakage)")
    
    if reasons:
        return ("degenerate", reasons)
    return ("healthy", ["all metrics within expected range"])


def evaluate_model_health(model_full_path: str, model_type: str = None) -> dict:
    """Run ML.EVALUATE, return metrics + health verdict.

    Returns:
      {
        "model_full_path": "...",
        "model_type": "...",
        "verdict": "healthy" | "degenerate" | "missing" | "error",
        "metrics": {...},
        "reasons": [...]  # if not healthy
      }
    """
    if not model_type:
        meta = get_model_metadata(model_full_path)
        model_type = meta.get("model_type", "UNKNOWN")
    
    try:
        bq = bigquery.Client(project=_BQML_PROJECT)
        sql = f"SELECT * FROM ML.EVALUATE(MODEL `{model_full_path}`)"
        rows = list(bq.query(sql).result())
        if not rows:
            return {
                "model_full_path": model_full_path,
                "model_type": model_type,
                "verdict": "error",
                "metrics": {},
                "reasons": ["ML.EVALUATE returned no rows"],
            }
        metrics = dict(rows[0])
        # Sanitize for JSON
        clean_metrics = {}
        import math
        for k, v in metrics.items():
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                clean_metrics[k] = str(v)
            else:
                clean_metrics[k] = v
        verdict, reasons = _verdict_from_metrics(model_type, metrics)
        return {
            "model_full_path": model_full_path,
            "model_type": model_type,
            "verdict": verdict,
            "metrics": clean_metrics,
            "reasons": reasons,
        }
    except Exception as e:
        err_msg = str(e)
        if "Not found" in err_msg or "404" in err_msg:
            verdict = "missing"
        else:
            verdict = "error"
        return {
            "model_full_path": model_full_path,
            "model_type": model_type,
            "verdict": verdict,
            "metrics": {},
            "reasons": [f"ML.EVALUATE exception: {err_msg[:200]}"],
        }


def get_client_models_with_health(client_id: str, validate: bool = True) -> list[dict]:
    """Discover client's models + optionally run health checks.

    This is the primary entry point used by the bqml agent's callback.
    Output is suitable for serializing into agent state.

    Args:
      client_id: Client identifier
      validate:  If True, run ML.EVALUATE on each. If False, return just
                 discovery (faster, no health verdict).

    Returns:
      List of dicts, each:
        {
          "model_name": "npi_arima_spend",
          "model_full_path": "nc-ai-chatbot.astrobot_bqml_models.npi_arima_spend",
          "model_type": "ARIMA_PLUS",
          "created": "2026-05-15T18:08:34+00:00",
          "verdict": "healthy" | "degenerate" | "missing" | "error" | "unvalidated"
          "metrics": {...},   # only if validate=True
          "reasons": [...],   # only if validate=True and not healthy
        }
    """
    models = discover_client_models(client_id)
    result = []
    for mi in models:
        entry = asdict(mi)
        if validate:
            health = evaluate_model_health(mi.model_full_path, mi.model_type)
            entry["verdict"] = health["verdict"]
            entry["metrics"] = health["metrics"]
            entry["reasons"] = health["reasons"]
        else:
            entry["verdict"] = "unvalidated"
        result.append(entry)
    return result


# ──────────────────────────────────────────────────────────────────
# LLM-readable formatting — turns discovery + health into a text block
# suitable for injecting into a prompt via state placeholder
# ──────────────────────────────────────────────────────────────────

def format_inventory_for_prompt(client_id: str,
                                  models_with_health: list[dict],
                                  table_paths: dict = None) -> str:
    """Format the per-client BQML inventory as an LLM-readable text block.

    The output replaces what was hardcoded in bqml/prompts.py lines 269-450.

    Args:
      client_id: The locked client (NPI, Venetian, WinnDixie, ...)
      models_with_health: List of dicts from get_client_models_with_health()
      table_paths: Optional {table_id: full_path} for the client. Pulled from
                   Firestore if not provided.

    Returns:
      Formatted text block. Empty-but-clean message if no models found.
    """
    if not models_with_health:
        return (
            f"📋 NO BQML MODELS FOUND FOR CLIENT {client_id!r}\n"
            f"\n"
            f"This client has zero models in {_BQML_DATASET}. To train initial\n"
            f"models, the agent will need to use the training tools. The system\n"
            f"can auto-train standard models (ARIMA spend, ARIMA conversions,\n"
            f"saturation curves) when first requested.\n"
        )

    # Group models by type
    by_type = {}
    for m in models_with_health:
        t = m.get("model_type", "UNKNOWN")
        by_type.setdefault(t, []).append(m)

    lines = []
    lines.append(f"📋 {client_id.upper()} BQML MODELS REGISTRY (dynamically discovered)")
    lines.append("")
    lines.append(f"Location: `{_BQML_PROJECT}.{_BQML_DATASET}.<model_name>`")
    lines.append("")

    # Order by useful type categories
    type_order = ["ARIMA_PLUS", "LINEAR_REGRESSION", "BOOSTED_TREE_REGRESSOR",
                  "KMEANS", "LOGISTIC_REGRESSION"]
    type_labels = {
        "ARIMA_PLUS": "🔮 FORECASTING (ARIMA_PLUS)",
        "LINEAR_REGRESSION": "📈 REGRESSION (LINEAR_REGRESSION)",
        "BOOSTED_TREE_REGRESSOR": "🌲 BOOSTED REGRESSION",
        "KMEANS": "🎯 CLUSTERING (KMEANS)",
        "LOGISTIC_REGRESSION": "✅ CLASSIFICATION (LOGISTIC_REGRESSION)",
    }

    for t in type_order:
        if t not in by_type:
            continue
        lines.append(type_labels.get(t, t))
        for m in sorted(by_type[t], key=lambda x: x["model_name"]):
            health_flag = ""
            verdict = m.get("verdict", "unvalidated")
            if verdict == "degenerate":
                reasons = m.get("reasons", [])
                reason_str = "; ".join(reasons[:2]) if reasons else "broken metrics"
                health_flag = f"  ❌ DEGENERATE — DO NOT USE ({reason_str})"
            elif verdict == "error":
                health_flag = "  ⚠️ VALIDATION ERROR"
            elif verdict == "missing":
                health_flag = "  ❌ MISSING"
            elif verdict == "healthy":
                health_flag = "  ✅"
            lines.append(f"  - {m['model_name']}{health_flag}")
        lines.append("")

    # Handle any unrecognized types at the bottom
    remaining_types = [t for t in by_type if t not in type_order]
    for t in remaining_types:
        lines.append(f"{t}:")
        for m in by_type[t]:
            lines.append(f"  - {m['model_name']}")
        lines.append("")

    # Table paths for the client
    if table_paths:
        lines.append("CLIENT DATA TABLES:")
        for tid, path in sorted(table_paths.items()):
            lines.append(f"  {tid}: `{path}`")
        lines.append("")

    # Quick health summary
    healthy_count = sum(1 for m in models_with_health if m.get("verdict") == "healthy")
    degen_count = sum(1 for m in models_with_health if m.get("verdict") == "degenerate")
    lines.append(f"SUMMARY: {len(models_with_health)} models total — "
                 f"{healthy_count} healthy, {degen_count} degenerate")

    return "\n".join(lines)


def format_keyword_routing(models_with_health: list[dict]) -> str:
    """Generate keyword→model routing hints from discovered models.

    Heuristic: parse model names for keywords and emit suggested mappings.
    Skips degenerate models (won't suggest broken ones).

    Returns a text block for prompt injection.
    """
    if not models_with_health:
        return "(no models — train one to enable routing)"

    # Filter out degenerate/error/missing
    usable = [m for m in models_with_health 
              if m.get("verdict") in ("healthy", "unvalidated")]

    if not usable:
        return "(no usable models — all are degraded)"

    lines = ["KEYWORD → MODEL ROUTING (auto-generated from healthy inventory):"]
    
    # ARIMA forecasting routes
    arima_models = [m for m in usable if m.get("model_type") == "ARIMA_PLUS"]
    for m in arima_models:
        name = m["model_name"].lower()
        if "spend" in name or "cost" in name:
            lines.append(f"  \"forecast spend\"        → {m['model_name']}")
        elif "conversion" in name and ("all" in name or "total" in name):
            lines.append(f"  \"forecast conversions\"  → {m['model_name']}")
        elif "search" in name and "conversion" in name:
            lines.append(f"  \"forecast search conv\"  → {m['model_name']}")
        elif "social" in name and "conversion" in name:
            lines.append(f"  \"forecast social conv\"  → {m['model_name']}")
    
    # Linear regression routes
    linear_models = [m for m in usable if m.get("model_type") == "LINEAR_REGRESSION"]
    for m in linear_models:
        name = m["model_name"].lower()
        if "saturation" in name and "v2" not in name:
            lines.append(f"  \"saturation curve\"      → {m['model_name']}")
        elif name.endswith("_cost") or "predict_cost" in name:
            lines.append(f"  \"predict cost\"          → {m['model_name']}")
    
    # KMEANS for clustering
    kmeans = [m for m in usable if m.get("model_type") == "KMEANS"]
    for m in kmeans:
        lines.append(f"  \"cluster campaigns\"     → {m['model_name']}")
    
    # Boosted tree (usually preferred for prediction accuracy)
    boosted = [m for m in usable if m.get("model_type") == "BOOSTED_TREE_REGRESSOR"]
    for m in boosted:
        lines.append(f"  \"best conversions model\" → {m['model_name']}")
    
    if len(lines) == 1:
        lines.append("  (no recognized name patterns — models exist but routing not auto-generated)")
    
    return "\n".join(lines)
