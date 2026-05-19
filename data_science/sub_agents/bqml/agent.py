# data_science/sub_agents/bqml/agent.py
"""BQML sub-agent — forecasting, clustering, regression, anomaly detection."""

import os
import hashlib
import logging
from typing import Any, Optional
from google.adk.agents.callback_context import CallbackContext

_logger = logging.getLogger(__name__)



def _clean_floats(obj):
    """Replace NaN/Infinity with None recursively."""
    import math
    if isinstance(obj, dict):
        return {k: _clean_floats(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean_floats(v) for v in obj]
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
    return obj


def bqml_after_model_callback(
    callback_context: CallbackContext,
    llm_response: Any,
) -> Optional[Any]:
    """Block duplicate text responses from bqml agent."""
    try:
        state = callback_context.state
        if llm_response.candidates:
            for cand in llm_response.candidates:
                if cand.content and cand.content.parts:
                    for part in cand.content.parts:
                        if (hasattr(part, "text") and part.text
                                and len(part.text) > 50):
                            import re
                            normalized = re.sub(r'\d{8}_\d{6}', '', part.text)
                            normalized = re.sub(r'\s+', ' ', normalized).strip()
                            h = hashlib.md5(normalized[:300].encode()).hexdigest()[:8]
                            seen = state.get("_bqml_seen_hashes", [])
                            if h in seen:
                                _logger.warning("BQML duplicate blocked: %s", h)
                                return None
                            state["_bqml_seen_hashes"] = (seen + [h])[-10:]
                            break
    except Exception as e:
        _logger.debug("BQML dedup error: %s", e)
    return None
from google.adk.agents import Agent
from google.adk.tools.agent_tool import AgentTool
from google.adk.tools.bigquery import BigQueryToolset
from google.adk.tools.bigquery.config import BigQueryToolConfig, WriteMode

from .prompts import return_instructions_bqml
from .tools import (
    rag_response,
    check_bq_models,
    get_arima_train_sql,
    get_arima_forecast_sql,
    get_anomaly_detect_sql,
    get_eom_variance_sql,
)


bq_execute_sql = BigQueryToolset(
    tool_filter=["execute_sql"],
    bigquery_tool_config=BigQueryToolConfig(
        write_mode=WriteMode.ALLOWED,
    ),
)


async def call_db_agent(query: str, tool_context) -> str:
    """Calls bigquery agent to run SQL queries."""
    from ..bigquery.agent import bigquery_agent
    agent_tool = AgentTool(agent=bigquery_agent)
    return await agent_tool.run_async(
        args={"request": query},
        tool_context=tool_context,
    )


async def call_analytics_for_visualization(
    data_and_instructions: str, tool_context
) -> str:
    """
    Routes ML results to chart rendering via JSON+matplotlib pipeline.
    """
    try:
        from ..analytics.agent import analytics_agent
        from ...tools import _render_chart_to_bytes
        import json, re, hashlib, time, logging
        from google.adk.tools.agent_tool import AgentTool
        from google.genai import types

        _log = logging.getLogger(__name__)

        # Truncate if too long
        if len(data_and_instructions) > 8000:
            data_and_instructions = data_and_instructions[:8000]

        agent_tool = AgentTool(agent=analytics_agent)
        result = await agent_tool.run_async(
            args={"request": data_and_instructions},
            tool_context=tool_context,
        )

        # Parse JSON spec
        text = str(result).replace("```json", "").replace("```", "")
        match = re.search(r"\{[\s\S]*\}", text)
        if not match:
            return "Chart spec parsing failed"
        spec = json.loads(match.group(0))

        if "chart_type" not in spec:
            return "Invalid chart spec"

        # Render chart with matplotlib
        png_bytes = _render_chart_to_bytes(spec)
        _log.info("BQML chart rendered: %s (%d bytes)",
                  spec.get("title"), len(png_bytes))

        # Save artifact in parent session
        fname = f"chart_{int(time.time())}_{hashlib.md5(str(spec).encode()).hexdigest()[:6]}.png"
        artifact = types.Part.from_bytes(data=png_bytes, mime_type="image/png")
        version = await tool_context.save_artifact(fname, artifact)
        _log.info("BQML chart saved: %s v%s", fname, version)

        return f"Generated {spec.get('chart_type')} chart: {spec.get('title')}"
    except Exception as e:
        import logging
        logging.getLogger(__name__).error("BQML viz failed: %s", e)
        return f"Chart generation error: {str(e)[:200]}"





def bqml_before_agent_callback(callback_context: CallbackContext) -> None:
    """Populate state[\'client_models_inventory\'] for prompt injection.

    Runs before the bqml LLM is called. Discovers BQML models for the
    currently-locked client, validates the 5 high-traffic production models,
    and formats the result as an LLM-readable text block. The block replaces
    what was hardcoded in prompts.py lines 269-450 — the agent now sees
    current reality (no stale model names, degenerate models flagged).

    State keys populated:
      - client_models_inventory: formatted text block for {state.X} substitution

    If no client is locked, falls back to a neutral placeholder so the prompt
    template still resolves cleanly.
    """
    state = callback_context.state
    client_id = state.get("client_id") or state.get("LOCKED_CLIENT") or state.get("client_lock")

    if not client_id:
        # No client locked — neutral placeholder so prompt still resolves
        state["client_models_inventory"] = (
            "(No client locked yet. Once the user identifies a client, the "
            "BQML inventory will populate here dynamically.)"
        )
        return

    try:
        from data_science.lib.bqml_registry import (
            discover_client_models, evaluate_model_health,
            format_inventory_for_prompt,
        )
        from data_science.lib.channel_resolver import load_config_v3

        models_raw = discover_client_models(client_id)

        # Validate the 5 high-traffic production models for NPI; for others,
        # we have nothing tagged as production yet so skip validation to keep
        # callback fast. Phase D will extend this.
        PROD_NAMES = {
            "npi_arima_spend", "arima_npi_all_conversions",
            "npi_conversions_saturation", "npi_linear_cost",
            "npi_campaign_clusters",
        }

        models_with_health = []
        for m in models_raw:
            entry = {
                "model_name": m.model_name,
                "model_full_path": m.model_full_path,
                "model_type": m.model_type,
                "created": m.created,
            }
            if m.model_name in PROD_NAMES:
                h = evaluate_model_health(m.model_full_path, m.model_type)
                entry["verdict"] = h["verdict"]
                entry["reasons"] = h["reasons"]
            else:
                entry["verdict"] = "unvalidated"
                entry["reasons"] = []
            models_with_health.append(entry)

        # Pull table paths for this client from Firestore config
        table_paths = {}
        try:
            cfg = load_config_v3()
            for d in cfg.get("datasets", []):
                if d.get("client_id") == client_id:
                    for t in d.get("tables", []):
                        tid = t.get("table_id")
                        tfp = t.get("table_full_path")
                        if tid and tfp:
                            table_paths[tid] = tfp
                    break
        except Exception as e:
            _logger.debug(f"Could not load table_paths for {client_id}: {e}")

        inventory_text = format_inventory_for_prompt(
            client_id, models_with_health, table_paths
        )
        state["client_models_inventory"] = inventory_text
        _logger.info(
            f"bqml_before_agent_callback: populated inventory for {client_id} "
            f"({len(models_with_health)} models)"
        )
    except Exception as e:
        _logger.warning(f"bqml_before_agent_callback failed for {client_id}: {e}")
        # Failure mode: clean placeholder so prompt still resolves
        state["client_models_inventory"] = (
            f"(BQML inventory unavailable for {client_id} — registry error: "
            f"{str(e)[:120]})"
        )


root_agent = Agent(
    model=os.getenv("BQML_AGENT_MODEL", "gemini-2.5-flash"),
    name="bq_ml_agent",
    instruction=return_instructions_bqml(),
    before_agent_callback=bqml_before_agent_callback,
    after_model_callback=bqml_after_model_callback,
    tools=[
        bq_execute_sql,
        check_bq_models,
        call_db_agent,
        rag_response,
        get_arima_train_sql,
        get_arima_forecast_sql,
        get_anomaly_detect_sql,
        get_eom_variance_sql,
        call_analytics_for_visualization,
    ],
)
