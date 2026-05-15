# shared/security/iam_impersonation.py
"""
IAM Service Account Impersonation — Layer 3 of the 4-layer isolation model.

Rather than giving agents a single broad BigQuery credential, this module
provides dynamic short-lived IAM tokens bound exclusively to the active
Client ID. The token carries only BigQuery Data Viewer role scoped to
that client's views.

If an LLM hallucination produces a query targeting an unauthorised table,
GCP infrastructure rejects it with 403 Access Denied — regardless of what
the model generated.

Spec reference: Section 2.3 — Infrastructure-Level Enforcement
"""

from __future__ import annotations
import logging
import os
from typing import Optional

import google.auth
import google.auth.transport.requests
from google.oauth2 import service_account
from google.auth import impersonated_credentials

logger = logging.getLogger(__name__)

# Service account naming pattern: one SA per client
# e.g. astrobot-npi@nc-ai-chatbot.iam.gserviceaccount.com
SA_PATTERN = os.getenv(
    "CLIENT_SA_PATTERN",
    "astrobot-{client_id_lower}@{project_id}.iam.gserviceaccount.com"
)

# Scopes: BigQuery read-only
BQ_READONLY_SCOPES = [
    "https://www.googleapis.com/auth/bigquery.readonly",
    "https://www.googleapis.com/auth/cloud-platform.read-only",
]


def get_client_credentials(
    client_id: str,
    project_id: str,
    lifetime_seconds: int = 3600,
) -> impersonated_credentials.Credentials:
    """
    Returns short-lived impersonated credentials scoped to a single client.

    The returned credentials can only access BigQuery views belonging to
    the specified client. Any attempt to access another client's data will
    be rejected by GCP IAM with a 403 error.

    Args:
        client_id:        Authorised client (e.g. 'NPI').
        project_id:       GCP project ID.
        lifetime_seconds: Token lifetime (default 1 hour).

    Returns:
        Impersonated credentials object.
    """
    target_sa = SA_PATTERN.format(
        client_id_lower=client_id.lower(),
        project_id=project_id,
    )

    source_credentials, _ = google.auth.default()

    creds = impersonated_credentials.Credentials(
        source_credentials=source_credentials,
        target_principal=target_sa,
        target_scopes=BQ_READONLY_SCOPES,
        lifetime=lifetime_seconds,
    )

    logger.info(
        "Impersonating SA %s for client %s (TTL: %ds)",
        target_sa, client_id, lifetime_seconds
    )
    return creds


def validate_table_access(
    table_ref: str,
    client_id: str,
    project_id: str,
) -> bool:
    """
    Validates that a BigQuery table reference belongs to the authorised client.
    This is a pre-execution check before sending to BQ — defence in depth.

    Args:
        table_ref: Fully-qualified BQ table (e.g. 'nc-ai-chatbot.Astrobot_NPI.sample_...')
        client_id: The active client ID.
        project_id: GCP project.

    Returns:
        True if authorised, False if the table belongs to another client.
    """
    from shared.config import CLIENT_BQ_TABLE_MAP

    authorised_datasets = {
        cfg["dataset"]
        for cid, cfg in CLIENT_BQ_TABLE_MAP.items()
        if cid == client_id
    }

    # Extract dataset from table_ref
    parts = table_ref.replace("`", "").split(".")
    if len(parts) < 3:
        logger.warning("Malformed table reference: %s", table_ref)
        return False

    table_dataset = parts[1]
    if table_dataset not in authorised_datasets:
        logger.error(
            "SECURITY VIOLATION: Client %s attempted to access dataset %s "
            "(authorised: %s)",
            client_id, table_dataset, authorised_datasets
        )
        return False

    return True


def log_rlhf_feedback(
    client_id: str,
    session_id: str,
    prompt: str,
    response: str,
    rating: int,          # 1 = positive, -1 = negative
    correction: str = "",
    project_id: str = "",
) -> None:
    """
    Logs RLHF feedback to BigQuery, partitioned by Client ID.
    All entries carry client_id to enforce memory partitioning.

    Spec reference: Section 8.1 — Feedback Loop / RLHF Training Logs
    """
    from google.cloud import bigquery
    from shared.config import RLHF_LOGS_TABLE

    bq = bigquery.Client(project=project_id or os.getenv("GOOGLE_CLOUD_PROJECT"))
    rows = [{
        "client_id":  client_id,
        "session_id": session_id,
        "prompt":     prompt[:4096],
        "response":   response[:8192],
        "rating":     rating,
        "correction": correction[:2048],
        "timestamp":  "AUTO",
    }]
    errors = bq.insert_rows_json(RLHF_LOGS_TABLE, rows)
    if errors:
        logger.error("RLHF log insert failed: %s", errors)
