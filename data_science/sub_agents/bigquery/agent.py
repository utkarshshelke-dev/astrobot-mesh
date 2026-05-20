# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Database Agent: get data from database (BigQuery) using NL2SQL."""

import logging
import os
from typing import Any

from google.adk.agents import LlmAgent
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools import BaseTool, ToolContext
from google.adk.tools.bigquery import BigQueryToolset
from google.adk.tools.bigquery.config import BigQueryToolConfig, WriteMode
from google.genai import types

from ...utils.utils import USER_AGENT
from . import tools
from .chase_sql import chase_db_tools
from .prompts import return_instructions_bigquery

logger = logging.getLogger(__name__)

NL2SQL_METHOD = os.getenv("NL2SQL_METHOD", "BASELINE")

# BigQuery built-in tools in ADK
# https://google.github.io/adk-docs/tools/built-in-tools/#bigquery
ADK_BUILTIN_BQ_EXECUTE_SQL_TOOL = "execute_sql"


def setup_before_agent_call(callback_context: CallbackContext) -> None:
    """Setup the agent."""

    if "database_settings" not in callback_context.state:
        callback_context.state["database_settings"] = (
            tools.get_database_settings()
        )


def store_results_in_context(
    tool: BaseTool,
    args: dict[str, Any],
    tool_context: ToolContext,
    tool_response: dict,
) -> dict | None:
    # We are setting a state for the data science agent to be able to use the
    # sql query results as context
    if tool.name == ADK_BUILTIN_BQ_EXECUTE_SQL_TOOL:
        # Item 9: capture the actual SQL passed to execute_sql so the root
        # agent's "Steps:" narration shows real SQL instead of LLM-paraphrased
        # table names. Previously the LLM had to recall SQL from its own
        # context window, which led to fabricated paths.
        sql_arg = args.get("query") or args.get("sql") or ""
        if sql_arg:
            tool_context.state["last_executed_sql"] = sql_arg

        if tool_response["status"] == "SUCCESS":
            # Sanitize NaN/Infinity values for JSON compatibility
            sanitized_rows = tools._sanitize_json(tool_response["rows"])
            tool_context.state["bigquery_query_result"] = sanitized_rows
            tool_response["rows"] = sanitized_rows

    return None


bigquery_tool_filter = [ADK_BUILTIN_BQ_EXECUTE_SQL_TOOL]
bigquery_tool_config = BigQueryToolConfig(
    write_mode=WriteMode.BLOCKED, application_name=USER_AGENT
)
bigquery_toolset = BigQueryToolset(
    tool_filter=bigquery_tool_filter, bigquery_tool_config=bigquery_tool_config
)

bigquery_agent = LlmAgent(
    model=os.getenv("BIGQUERY_AGENT_MODEL", ""),
    name="bigquery_agent",
    instruction=return_instructions_bigquery(),
    tools=[
        (
            chase_db_tools.initial_bq_nl2sql
            if NL2SQL_METHOD == "CHASE"
            else tools.bigquery_nl2sql
        ),
        bigquery_toolset,
        # ── Astrobot ad-campaign tools ──────────────────────────────────────
        # check_campaign_status: safety gate — no recs on paused campaigns
        # get_pacing_sql:        pre-built performance LEFT JOIN budget SQL
        # get_channel_efficiency_sql: CPA vs Spend audit SQL
        tools.check_campaign_status,
        tools.compute_channel_volatility,
        tools.get_channel_volatility_summary,
        tools.compute_saturation_curve,
        tools.train_arima_model_bqml,
        tools.train_saturation_model_bqml,
        tools.propose_new_table,
        tools.select_chart_type,
        tools.get_pacing_sql,
        tools.get_channel_efficiency_sql,
    ],
    before_agent_callback=setup_before_agent_call,
    after_tool_callback=store_results_in_context,
    generate_content_config=types.GenerateContentConfig(temperature=0.01),
)