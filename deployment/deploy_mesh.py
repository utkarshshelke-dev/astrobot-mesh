# deployment/deploy_mesh.py
"""
Mesh Deployment Script — deploys all Astro.bot agents to Vertex AI Agent Engine
and the webhook to Cloud Run. Updates Agent Card endpoints in Firestore after
each deployment so the Orchestrator A2A handshake can find them.

Usage:
    python deployment/deploy_mesh.py --action deploy --agent all
    python deployment/deploy_mesh.py --action deploy --agent orchestrator
    python deployment/deploy_mesh.py --action deploy --agent data_scientist
    python deployment/deploy_mesh.py --action update  --agent economist --resource-name projects/.../agents/...
    python deployment/deploy_mesh.py --action delete  --agent scheduler  --resource-name projects/.../agents/...
    python deployment/deploy_mesh.py --action deploy-webhook
"""

import argparse
import json
import logging
import os
import subprocess

import vertexai
from vertexai.preview import agent_engines

from shared.utils.config import PROJECT_ID, LOCATION
from shared.firestore.registry import update_agent_endpoint
from shared.a2a.agent_card import ALL_AGENT_CARDS

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("deploy")

STAGING_BUCKET = os.getenv("STAGING_BUCKET", f"gs://{PROJECT_ID}-adk-staging")

AGENT_MODULES = {
    "orchestrator":       "orchestrator.agent",
    "persona_aggregator": "persona_aggregator.agent",
    "economist":          "economist.agent",
    "project_manager":    "project_manager.agent",
    "scheduler":          "scheduler.agent",
}

AGENT_DESCRIPTIONS = {
    "orchestrator":       "Astro.bot Orchestrator — central routing and coordination",
    "persona_aggregator": "Persona Aggregator — Global Definition, Local Execution",
    "economist":          "Economist Agent — macroeconomic context and benchmarking",
    "project_manager":    "Project Manager Agent — tasks, emails, timelines",
    "scheduler":          "Scheduler Agent — recurring automated prompt executions",
}

REQUIREMENTS = [
    "google-cloud-aiplatform[agent_engines,adk]>=1.87.0",
    "google-adk>=1.0.0",
    "google-cloud-bigquery>=3.11.0",
    "google-cloud-firestore>=2.13.0",
    "vertexai>=1.40.0",
    "httpx>=0.27.0",
    "flask>=3.0.0",
]


def _init():
    vertexai.init(project=PROJECT_ID, location=LOCATION, staging_bucket=STAGING_BUCKET)


def deploy_agent(agent_id: str) -> str:
    """Deploys a single agent to Agent Engine. Returns the resource name."""
    _init()
    module_path = AGENT_MODULES[agent_id]
    module      = __import__(module_path, fromlist=["root_agent"])
    root_agent  = module.root_agent

    logger.info("Deploying '%s'…", agent_id)
    remote = agent_engines.create(
        agent_engines.AdkApp(agent=root_agent, enable_tracing=True),
        requirements=REQUIREMENTS,
        extra_packages=["./"],
        display_name=f"astrobot_{agent_id}",
        description=AGENT_DESCRIPTIONS[agent_id],
    )
    resource_name = remote.resource_name
    logger.info("✅ '%s' deployed: %s", agent_id, resource_name)

    # Update Agent Card endpoint in Firestore so Orchestrator can find it
    update_agent_endpoint(agent_id, resource_name)
    ALL_AGENT_CARDS[agent_id].endpoint = resource_name

    return resource_name


def update_agent(agent_id: str, resource_name: str) -> None:
    _init()
    module_path = AGENT_MODULES[agent_id]
    module      = __import__(module_path, fromlist=["root_agent"])
    root_agent  = module.root_agent

    logger.info("Updating '%s': %s", agent_id, resource_name)
    remote = agent_engines.get(resource_name)
    remote.update(
        agent_engines.AdkApp(agent=root_agent, enable_tracing=True),
        requirements=REQUIREMENTS,
        extra_packages=["./"],
    )
    update_agent_endpoint(agent_id, resource_name)
    logger.info("✅ '%s' updated.", agent_id)


def delete_agent(agent_id: str, resource_name: str) -> None:
    _init()
    logger.warning("Deleting '%s': %s", agent_id, resource_name)
    remote = agent_engines.get(resource_name)
    remote.delete(force=True)
    logger.info("✅ '%s' deleted.", agent_id)


def deploy_webhook() -> None:
    """Deploys the Cloud Run webhook handler for Google Chat."""
    logger.info("Deploying Cloud Run webhook…")
    cmd = [
        "gcloud", "run", "deploy", "astrobot-webhook",
        "--source", ".",
        "--region", LOCATION,
        "--project", PROJECT_ID,
        "--allow-unauthenticated",
        "--set-env-vars",
        f"GOOGLE_CLOUD_PROJECT={PROJECT_ID},GOOGLE_CLOUD_LOCATION={LOCATION}",
        "--memory", "512Mi",
        "--timeout", "120",
    ]
    subprocess.run(cmd, check=True)
    logger.info("✅ Cloud Run webhook deployed.")


def deploy_all() -> dict:
    """Deploys all agents in dependency order. Orchestrator last."""
    order = [
        "persona_aggregator",
        "economist",
        "project_manager",
        "scheduler",
        "orchestrator",   # Last — needs other endpoints set first
    ]
    results = {}
    for agent_id in order:
        results[agent_id] = deploy_agent(agent_id)
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Astro.bot mesh deployment")
    parser.add_argument("--action", choices=["deploy", "update", "delete", "deploy-webhook"], required=True)
    parser.add_argument("--agent",  default="all", help="Agent ID or 'all'")
    parser.add_argument("--resource-name", help="Agent Engine resource name")
    args = parser.parse_args()

    if args.action == "deploy":
        if args.agent == "all":
            results = deploy_all()
            print(json.dumps(results, indent=2))
        elif args.agent in AGENT_MODULES:
            name = deploy_agent(args.agent)
            print(json.dumps({args.agent: name}))
        else:
            parser.error(f"Unknown agent '{args.agent}'. Valid: {list(AGENT_MODULES.keys())} or 'all'")

    elif args.action == "update":
        if not args.resource_name:
            parser.error("--resource-name required for update")
        update_agent(args.agent, args.resource_name)

    elif args.action == "delete":
        if not args.resource_name:
            parser.error("--resource-name required for delete")
        delete_agent(args.agent, args.resource_name)

    elif args.action == "deploy-webhook":
        deploy_webhook()
