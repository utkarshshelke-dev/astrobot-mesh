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




root_agent = Agent(
    model=os.getenv("BQML_AGENT_MODEL", "gemini-2.5-flash"),
    name="bq_ml_agent",
    instruction=return_instructions_bqml(),
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
