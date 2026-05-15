# shared/a2a/agent_card.py
"""
A2A Agent Card Protocol — Astro.bot Mesh §7.2

Each agent publishes an AgentCard at its endpoint describing its capabilities,
expected inputs, and output formats. The Orchestrator performs a handshake
using the target agent's AgentCard rather than calling a hard-coded API shape.

This means individual agents can be iterated on rapidly without requiring
coordinated releases across the entire mesh, as long as the AgentCard contract
is honoured.
"""

from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class AgentCardInput:
    """Describes a single input parameter the agent accepts."""
    name:        str
    type:        str        # "string" | "dict" | "list"
    required:    bool
    description: str


@dataclass
class AgentCardOutput:
    """Describes the output format the agent returns."""
    type:        str        # "string" | "dict" | "markdown"
    description: str
    schema:      dict = field(default_factory=dict)


@dataclass
class AgentCard:
    """
    Machine-readable descriptor published by each agent.
    The Orchestrator uses this to understand how to call each specialist agent.
    """
    agent_id:      str          # unique identifier e.g. "data_scientist"
    display_name:  str
    version:       str          # semver e.g. "1.0.0"
    description:   str
    capabilities:  list[str]    # list of capability tags
    inputs:        list[AgentCardInput]
    output:        AgentCardOutput
    endpoint:      str          # Agent Engine resource name
    requires_client_id: bool = True   # all agents require client scoping

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: dict) -> "AgentCard":
        inputs = [AgentCardInput(**i) for i in data.get("inputs", [])]
        output = AgentCardOutput(**data.get("output", {}))
        return cls(
            agent_id=data["agent_id"],
            display_name=data["display_name"],
            version=data["version"],
            description=data["description"],
            capabilities=data.get("capabilities", []),
            inputs=inputs,
            output=output,
            endpoint=data.get("endpoint", ""),
            requires_client_id=data.get("requires_client_id", True),
        )


# ── Canonical Agent Cards for the Astro.bot mesh ─────────────────────────────


import os as _os

def _endpoint(agent_id: str, local_port: int) -> str:
    env_map = {
        "data_scientist":     "DATA_SCIENTIST_ENDPOINT",
        "persona_aggregator": "PERSONA_AGGREGATOR_ENDPOINT",
        "economist":          "ECONOMIST_ENDPOINT",
        "project_manager":    "PROJECT_MANAGER_ENDPOINT",
        "scheduler":          "SCHEDULER_ENDPOINT",
    }
    val = _os.getenv(env_map.get(agent_id, ""), "").strip()
    return val if val else f"http://localhost:{local_port}"

DATA_SCIENTIST_CARD = AgentCard(
    agent_id="data_scientist",
    display_name="Data Scientist Agent",
    version="1.0.0",
    description=(
        "Quantitative engine for ad campaign analytics. Handles NL2SQL queries, "
        "Python-based analysis and charting, and BigQuery ML forecasting, "
        "anomaly detection, and clustering. Serves NPI, Venetian, WinnDixie."
    ),
    capabilities=[
        "nl2sql", "bigquery", "data_analysis", "charting",
        "bqml_forecast", "bqml_clustering", "bqml_regression",
        "anomaly_detection", "pacing_analysis", "channel_efficiency",
    ],
    inputs=[
        AgentCardInput(
            name="query",
            type="string",
            required=True,
            description="Natural language analytics question or request.",
        ),
        AgentCardInput(
            name="client_id",
            type="string",
            required=True,
            description="One of: NPI, Venetian, WinnDixie.",
        ),
    ],
    output=AgentCardOutput(
        type="markdown",
        description="Result + Explanation + optional Graph in markdown format.",
        schema={
            "result":      "str",
            "explanation": "str",
            "graph":       "str | None",
        },
    ),
    endpoint=_endpoint("data_scientist", 8001),
)

PERSONA_AGGREGATOR_CARD = AgentCard(
    agent_id="persona_aggregator",
    display_name="Persona Aggregator Agent",
    version="1.0.0",
    description=(
        "Retrieves and applies generic advertising audience persona definitions "
        "to client-specific campaign analysis. Uses Global Definition, "
        "Local Execution model — persona definitions are shared; execution "
        "context is always client-scoped."
    ),
    capabilities=[
        "persona_retrieval", "persona_analysis",
        "audience_segmentation", "persona_authorisation_check",
    ],
    inputs=[
        AgentCardInput(
            name="persona_request",
            type="string",
            required=True,
            description="Description of the persona or audience segment needed.",
        ),
        AgentCardInput(
            name="client_id",
            type="string",
            required=True,
            description="One of: NPI, Venetian, WinnDixie.",
        ),
        AgentCardInput(
            name="campaign_context",
            type="dict",
            required=False,
            description="Optional campaign data to contextualise persona analysis.",
        ),
    ],
    output=AgentCardOutput(
        type="markdown",
        description="Persona definition + client-specific application analysis.",
    ),
    endpoint=_endpoint("persona_aggregator", 8002),
)

ECONOMIST_CARD = AgentCard(
    agent_id="economist",
    display_name="Economist Agent",
    version="1.0.0",
    description=(
        "Contextualises client performance data against macroeconomic and market "
        "conditions. Draws on published economic indicators, sector-level market "
        "data, and industry benchmarks filtered by client vertical."
    ),
    capabilities=[
        "economic_context", "market_benchmarking",
        "vertical_analysis", "industry_indicators",
    ],
    inputs=[
        AgentCardInput(
            name="analysis_request",
            type="string",
            required=True,
            description="Economic context question or benchmark request.",
        ),
        AgentCardInput(
            name="client_id",
            type="string",
            required=True,
            description="One of: NPI, Venetian, WinnDixie.",
        ),
        AgentCardInput(
            name="performance_data",
            type="dict",
            required=False,
            description="Optional campaign performance data to contextualise.",
        ),
    ],
    output=AgentCardOutput(
        type="markdown",
        description="Economic context analysis with vertical-specific indicators.",
    ),
    endpoint=_endpoint("economist", 8003),
)

PROJECT_MANAGER_CARD = AgentCard(
    agent_id="project_manager",
    display_name="Project Manager Agent",
    version="1.0.0",
    description=(
        "Handles client-specific project management: email communications, "
        "task management, project timelines, and team correspondence. "
        "Subject to strictest client isolation — no cross-client data sharing."
    ),
    capabilities=[
        "task_management", "email_management",
        "project_tracking", "timeline_management",
    ],
    inputs=[
        AgentCardInput(
            name="pm_request",
            type="string",
            required=True,
            description="Project management task or query.",
        ),
        AgentCardInput(
            name="client_id",
            type="string",
            required=True,
            description="One of: NPI, Venetian, WinnDixie.",
        ),
    ],
    output=AgentCardOutput(
        type="markdown",
        description="Task status, email draft, or project timeline response.",
    ),
    endpoint=_endpoint("project_manager", 8004),
)

SCHEDULER_CARD = AgentCard(
    agent_id="scheduler",
    display_name="Scheduler Agent",
    version="1.0.0",
    description=(
        "Manages recurring automated prompt executions. Sits at the control "
        "plane — behaves as an automated user sending requests to the Orchestrator "
        "rather than as a peer agent. Supports delivery via Google Chat, email, "
        "and Google Sheets."
    ),
    capabilities=[
        "schedule_create", "schedule_update", "schedule_delete",
        "schedule_list", "delivery_chat", "delivery_email", "delivery_sheets",
    ],
    inputs=[
        AgentCardInput(
            name="schedule_request",
            type="string",
            required=True,
            description="Natural language scheduling instruction.",
        ),
        AgentCardInput(
            name="client_id",
            type="string",
            required=True,
            description="One of: NPI, Venetian, WinnDixie.",
        ),
        AgentCardInput(
            name="original_prompt",
            type="string",
            required=False,
            description="The analytical prompt to be scheduled.",
        ),
        AgentCardInput(
            name="delivery_config",
            type="dict",
            required=False,
            description="Delivery channel config: chat_webhook, email, sheets_folder_id.",
        ),
    ],
    output=AgentCardOutput(
        type="markdown",
        description="Confirmation of scheduled job creation or job listing.",
    ),
    endpoint=_endpoint("scheduler", 8005),
)

# Registry of all cards
ALL_AGENT_CARDS: dict[str, AgentCard] = {
    "data_scientist":     DATA_SCIENTIST_CARD,
    "persona_aggregator": PERSONA_AGGREGATOR_CARD,
    "economist":          ECONOMIST_CARD,
    "project_manager":    PROJECT_MANAGER_CARD,
    "scheduler":          SCHEDULER_CARD,
}
