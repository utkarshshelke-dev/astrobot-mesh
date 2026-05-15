# deployment/deploy_all.py
"""
Deploys all Astrobot mesh agents to Vertex AI Agent Engine.
Also deploys the Orchestrator webhook to Cloud Run.

Usage:
    python deployment/deploy_all.py --action deploy_all
    python deployment/deploy_all.py --action deploy --agent orchestrator
    python deployment/deploy_all.py --action deploy --agent persona_aggregator
    python deployment/deploy_all.py --action deploy --agent economist
    python deployment/deploy_all.py --action deploy --agent project_manager
    python deployment/deploy_all.py --action deploy --agent scheduler
    python deployment/deploy_all.py --action list
    python deployment/deploy_all.py --action register_cards

Order matters: deploy data_scientist FIRST (already done),
then deploy mesh agents, then update AGENT_ENDPOINTS, then deploy orchestrator.
"""

from __future__ import annotations
import argparse
import json
import logging
import os
import sys

import vertexai
from vertexai.preview import agent_engines

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("deploy_all")

PROJECT_ID     = os.getenv("GOOGLE_CLOUD_PROJECT", "nc-ai-chatbot")
LOCATION       = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
STAGING_BUCKET = os.getenv("STAGING_BUCKET", f"gs://{PROJECT_ID}-agent-staging")

REQUIREMENTS = [
    "google-cloud-aiplatform[agent_engines,adk]>=1.87.0",
    "google-adk>=1.0.0",
    "google-cloud-bigquery>=3.11.0",
    "google-cloud-firestore>=2.13.0",
    "vertexai>=1.40.0",
    "httpx>=0.27.0",
    "fastapi>=0.110.0",
    "uvicorn>=0.29.0",
]

AGENT_CONFIGS = {
    "persona_aggregator": {
        "module":       "persona_aggregator.agent",
        "agent_var":    "persona_aggregator_agent",
        "display_name": "Astrobot Persona Aggregator Agent",
        "description":  "Manages advertising audience personas with client-scoped execution.",
    },
    "economist": {
        "module":       "economist.agent",
        "agent_var":    "economist_agent",
        "display_name": "Astrobot Economist Agent",
        "description":  "Provides macro-economic context and industry benchmarks per client vertical.",
    },
    "project_manager": {
        "module":       "project_manager.agent",
        "agent_var":    "project_manager_agent",
        "display_name": "Astrobot Project Manager Agent",
        "description":  "Handles client-specific email, tasks, and project timelines.",
    },
    "scheduler": {
        "module":       "scheduler.agent",
        "agent_var":    "scheduler_agent",
        "display_name": "Astrobot Scheduler Agent",
        "description":  "Creates and manages recurring automated prompt executions.",
    },
    "orchestrator": {
        "module":       "orchestrator.agent",
        "agent_var":    "root_agent",
        "display_name": "Astrobot Orchestrator",
        "description":  "Central routing hub for the Astrobot multi-agent mesh.",
    },
}


def init_vertexai():
    vertexai.init(
        project=PROJECT_ID,
        location=LOCATION,
        staging_bucket=STAGING_BUCKET,
    )


def deploy_agent(agent_name: str) -> str:
    """Deploys a single agent to Vertex AI Agent Engine."""
    cfg = AGENT_CONFIGS.get(agent_name)
    if not cfg:
        raise ValueError(f"Unknown agent: {agent_name}. Valid: {list(AGENT_CONFIGS)}")

    init_vertexai()

    # Dynamic import of agent object
    import importlib
    module  = importlib.import_module(cfg["module"])
    agent   = getattr(module, cfg["agent_var"])

    logger.info("Deploying %s...", cfg["display_name"])

    remote = agent_engines.create(
        agent_engines.AdkApp(
            agent=agent,
            enable_tracing=True,
        ),
        requirements=REQUIREMENTS,
        extra_packages=["./"],
        display_name=cfg["display_name"],
        description=cfg["description"],
    )

    resource_name = remote.resource_name
    logger.info("✅ %s deployed: %s", agent_name, resource_name)
    logger.warning(
        "⚠️  Update %s_ENDPOINT in .env: %s",
        agent_name.upper(), resource_name,
    )
    return resource_name


def deploy_all_agents() -> dict:
    """
    Deploys agents in the correct order:
    1. persona_aggregator, economist, project_manager, scheduler (no dependencies)
    2. orchestrator (depends on all above)
    Data scientist is already deployed — skip.
    """
    results = {}
    # Deploy leaf agents first
    for name in ["persona_aggregator", "economist", "project_manager", "scheduler"]:
        try:
            results[name] = deploy_agent(name)
        except Exception as e:
            logger.error("Failed to deploy %s: %s", name, e)
            results[name] = f"ERROR: {e}"

    logger.info("\n%s\nUpdate .env with all endpoints above, then deploy orchestrator.\n%s",
                "="*60, "="*60)
    logger.info("Run: python deployment/deploy_all.py --action deploy --agent orchestrator")
    return results


def register_agent_cards(endpoints: dict) -> None:
    """
    Registers Agent Cards in Firestore after deployment.
    Call this after updating AGENT_ENDPOINTS.
    """
    init_vertexai()
    from shared.a2a.agent_card import (
        AgentCardRegistry,
        get_data_scientist_card,
        get_persona_aggregator_card,
        get_economist_card,
        get_project_manager_card,
        get_scheduler_card,
    )

    registry = AgentCardRegistry(PROJECT_ID)
    cards = {
        "data_scientist":    get_data_scientist_card(endpoints.get("data_scientist", "")),
        "persona_aggregator": get_persona_aggregator_card(endpoints.get("persona_aggregator", "")),
        "economist":         get_economist_card(endpoints.get("economist", "")),
        "project_manager":   get_project_manager_card(endpoints.get("project_manager", "")),
        "scheduler":         get_scheduler_card(endpoints.get("scheduler", "")),
    }
    for agent_id, card in cards.items():
        registry.publish(card)
        logger.info("Registered agent card: %s", agent_id)


def list_deployed_agents() -> None:
    """Lists all deployed agents in Agent Engine."""
    init_vertexai()
    agents = agent_engines.list()
    for a in agents:
        print(f"  {a.display_name}: {a.resource_name}")


def deploy_webhook_cloud_run() -> None:
    """Deploys the Chat webhook to Cloud Run."""
    import subprocess
    logger.info("Deploying Astrobot webhook to Cloud Run...")
    cmd = [
        "gcloud", "run", "deploy", "astrobot-webhook",
        f"--project={PROJECT_ID}",
        f"--region={LOCATION}",
        "--source=.",
        "--command=uvicorn",
        "--args=orchestrator.webhook:app,--host,0.0.0.0,--port,8080",
        "--allow-unauthenticated",
        "--memory=512Mi",
        "--cpu=1",
        "--min-instances=1",
        "--set-env-vars",
        f"GOOGLE_CLOUD_PROJECT={PROJECT_ID},GOOGLE_CLOUD_LOCATION={LOCATION}",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        logger.info("✅ Webhook deployed to Cloud Run.")
        logger.info(result.stdout)
    else:
        logger.error("Cloud Run deployment failed:\n%s", result.stderr)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Astrobot mesh deployment tool")
    parser.add_argument(
        "--action",
        choices=["deploy", "deploy_all", "list", "register_cards", "deploy_webhook"],
        required=True,
    )
    parser.add_argument("--agent", help="Agent name for --action deploy")
    args = parser.parse_args()

    if args.action == "deploy":
        if not args.agent:
            parser.error("--agent is required for --action deploy")
        name = deploy_agent(args.agent)
        print(json.dumps({"resource_name": name}))

    elif args.action == "deploy_all":
        results = deploy_all_agents()
        print(json.dumps(results, indent=2))

    elif args.action == "list":
        list_deployed_agents()

    elif args.action == "register_cards":
        from shared.config import AGENT_ENDPOINTS
        register_agent_cards(AGENT_ENDPOINTS)

    elif args.action == "deploy_webhook":
        deploy_webhook_cloud_run()
