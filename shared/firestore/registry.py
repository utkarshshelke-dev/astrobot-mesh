# shared/firestore/registry.py
"""
Firestore Registry — client config, persona authorisations, agent endpoints.
"""

from __future__ import annotations
import logging
from typing import Optional

from google.cloud import firestore

from shared.utils.config import (
    PROJECT_ID,
    FIRESTORE_DB,
    PERSONA_AUTH_COLLECTION,
    AGENT_REGISTRY_COLLECTION,
    SCHEDULER_COLLECTION,
)

logger = logging.getLogger(__name__)

_fs: Optional[firestore.Client] = None


def _get_fs() -> firestore.Client:
    global _fs
    if _fs is None:
        _fs = firestore.Client(project=PROJECT_ID, database=FIRESTORE_DB)
    return _fs


def get_authorised_personas(client_id: str) -> list[str]:
    """
    Returns the list of persona IDs the client is authorised to use.
    Requests for personas outside this list are rejected before the LLM is invoked.
    """
    doc = (
        _get_fs()
        .collection(PERSONA_AUTH_COLLECTION)
        .document(client_id)
        .get()
    )
    if not doc.exists:
        logger.warning("No persona authorisations found for client '%s'", client_id)
        return []
    return doc.to_dict().get("authorised_personas", [])


def is_persona_authorised(client_id: str, persona_id: str) -> bool:
    """Checks if a specific persona is authorised for this client."""
    return persona_id in get_authorised_personas(client_id)


def get_agent_endpoint(agent_id: str) -> str:
    """Retrieves the current Agent Engine endpoint for a given agent."""
    doc = (
        _get_fs()
        .collection(AGENT_REGISTRY_COLLECTION)
        .document(agent_id)
        .get()
    )
    if not doc.exists:
        return ""
    return doc.to_dict().get("endpoint", "")


def update_agent_endpoint(agent_id: str, endpoint: str) -> None:
    """Updates the agent endpoint in the registry after deployment."""
    _get_fs().collection(AGENT_REGISTRY_COLLECTION).document(agent_id).set(
        {"agent_id": agent_id, "endpoint": endpoint},
        merge=True,
    )
    logger.info("Agent registry updated: '%s' → '%s'", agent_id, endpoint)


def get_scheduled_jobs(client_id: str) -> list[dict]:
    """Returns all scheduled jobs for a given client."""
    docs = (
        _get_fs()
        .collection(SCHEDULER_COLLECTION)
        .where("client_id", "==", client_id)
        .where("active", "==", True)
        .stream()
    )
    return [d.to_dict() for d in docs]


def save_scheduled_job(job: dict) -> str:
    """Saves a new scheduled job and returns the job ID."""
    ref = _get_fs().collection(SCHEDULER_COLLECTION).add(job)
    return ref[1].id
