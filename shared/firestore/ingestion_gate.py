# shared/firestore/ingestion_gate.py
"""
Ingestion Gate — Layer 1 of the 4-layer isolation model.

Every request passes through this gate BEFORE the LLM is invoked.
The Google Chat Space ID is cryptographically signed by Google and
cannot be fabricated. This gate maps it to an immutable Client ID.

Spec reference: Section 2.1 — Ingestion Gate and Deterministic Routing
"""

from __future__ import annotations
import logging
from functools import lru_cache
from typing import Optional

from google.cloud import firestore

logger = logging.getLogger(__name__)

_fs_client: Optional[firestore.Client] = None


def _get_firestore(project_id: str) -> firestore.Client:
    global _fs_client
    if _fs_client is None:
        _fs_client = firestore.Client(project=project_id)
    return _fs_client


def resolve_client_id(space_id: str, project_id: str) -> Optional[str]:
    """
    Maps a Google Chat Space ID to an authorised Client ID.

    The Space ID is issued and controlled by Google infrastructure —
    it cannot be altered by the end user. From the moment this lookup
    succeeds, the Client ID is immutably locked into the session context.

    Returns None if the Space ID is not registered (unauthorised).

    Args:
        space_id:   Google Chat Space ID from webhook payload.
        project_id: GCP project ID.

    Returns:
        Client ID string (e.g. 'NPI') or None if not found.
    """
    fs  = _get_firestore(project_id)
    doc = fs.collection("space_client_registry").document(space_id).get()

    if not doc.exists:
        logger.warning("Unregistered Space ID: %s — request rejected.", space_id)
        return None

    data      = doc.to_dict()
    client_id = data.get("client_id")
    if not data.get("active", True):
        logger.warning("Space ID %s is deactivated.", space_id)
        return None

    logger.info("Space %s resolved to client: %s", space_id, client_id)
    return client_id


def get_client_schema_context(client_id: str, project_id: str) -> str:
    """
    Returns the DDL schema context for a specific client.

    Only the active client's schemas are injected into the agent context.
    All other clients' schemas are never included — this is the Schema
    Blindfold (Layer 2 of the isolation model).

    Spec reference: Section 2.2 — Contextual Isolation / Schema Blindfold

    Args:
        client_id:  Authorised client (e.g. 'NPI').
        project_id: GCP project ID.

    Returns:
        Formatted DDL string for the client's authorised datasets.
    """
    fs   = _get_firestore(project_id)
    docs = (
        fs.collection("client_schema_registry")
        .where("client_id", "==", client_id)
        .stream()
    )

    schemas = []
    for doc in docs:
        data = doc.to_dict()
        schemas.append(
            f"-- Table: {data.get('bq_table', 'unknown')}\n"
            f"-- Description: {data.get('description', '')}\n"
            f"{data.get('ddl', '')}\n"
        )

    if not schemas:
        logger.warning("No schema docs for client %s — using inline fallback.", client_id)
        return _inline_schema_fallback(client_id, project_id)

    return (
        f"-- AUTHORISED SCHEMA CONTEXT FOR CLIENT: {client_id}\n"
        f"-- DO NOT query any table not listed below.\n\n"
        + "\n\n".join(schemas)
    )


def get_authorised_personas(client_id: str, project_id: str) -> list[str]:
    """
    Returns the list of persona IDs the client is authorised to use.

    Spec reference: Section 3.2 — Client-Level Persona Authorisation
    """
    fs  = _get_firestore(project_id)
    doc = fs.collection("client_persona_map").document(client_id).get()
    if not doc.exists:
        return []
    return doc.to_dict().get("authorised_personas", [])


def register_space(
    space_id: str,
    client_id: str,
    project_id: str,
    display_name: str = "",
) -> None:
    """
    Registers a Google Chat Space in the client registry.
    Called once per new client Space setup by the operations team.
    """
    fs = _get_firestore(project_id)
    fs.collection("space_client_registry").document(space_id).set({
        "client_id":    client_id,
        "display_name": display_name,
        "active":       True,
        "space_id":     space_id,
    })
    logger.info("Registered Space %s → Client %s", space_id, client_id)


def _inline_schema_fallback(client_id: str, project_id: str) -> str:
    """Inline schema fallback when Firestore document is missing."""
    from shared.config import CLIENT_BQ_TABLE_MAP
    cfg = CLIENT_BQ_TABLE_MAP.get(client_id, {})
    if not cfg:
        return f"-- No schema available for client: {client_id}"

    table = f"`{project_id}.{cfg['dataset']}.{cfg['sample_table']}`"
    return f"""
-- Client: {client_id}
-- Primary table: {table}
-- KPI column: {cfg['kpi_column']}
-- Key metrics: Cost, Clicks, Impressions, ViVs, Sessions, Conversions
-- Key dimensions: Date, Campaign, Channel, Device, Geo, Status, Tactic
-- Always use this table directly — never use vw_ views (cross-project blocked)
"""
