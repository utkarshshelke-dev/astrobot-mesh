# Copyright 2025 NetConversion / Evonence
"""
shared/utils/rlhf.py
RLHF feedback logging to BigQuery — partitioned by Client ID.
Spec reference: Section 8.1 — Feedback Loop / RLHF Training Logs
"""

from __future__ import annotations
import logging
from datetime import datetime, timezone
from typing import Optional

from google.cloud import bigquery

from shared.config import BQ_COMPUTE_PROJECT, RLHF_DATASET, RLHF_TABLE

logger = logging.getLogger(__name__)
_bq: Optional[bigquery.Client] = None


def _get_bq() -> bigquery.Client:
    global _bq
    if _bq is None:
        _bq = bigquery.Client(project=BQ_COMPUTE_PROJECT)
    return _bq


def log_feedback(
    client_id:       str,
    space_id:        str,
    session_id:      str,
    prompt:          str,
    response:        str,
    rating:          int,           # 1 = thumbs up, -1 = thumbs down
    agent_name:      str,
    correction_note: str = "",
    routing_path:    list[str] = None,
) -> bool:
    """
    Logs user feedback to BigQuery RLHF table.
    All rows are partitioned by client_id — cross-client RLHF contamination
    is prevented at the query level.

    Args:
        client_id:       The active client (NPI / Venetian / WinnDixie).
        space_id:        Google Chat Space ID.
        session_id:      Agent Engine session ID.
        prompt:          Original user prompt.
        response:        Agent response text.
        rating:          1 (positive) or -1 (negative).
        agent_name:      Which agent produced the response.
        correction_note: Optional correction from the user on negative rating.
        routing_path:    List of agents invoked e.g. ["orchestrator","data_scientist"].

    Returns:
        True if logged successfully.
    """
    table_ref = f"{BQ_COMPUTE_PROJECT}.{RLHF_DATASET}.{RLHF_TABLE}"
    row = {
        "client_id":       client_id,
        "space_id":        space_id,
        "session_id":      session_id,
        "prompt":          prompt[:4096],
        "response":        response[:8192],
        "rating":          rating,
        "agent_name":      agent_name,
        "correction_note": correction_note[:2048],
        "routing_path":    ",".join(routing_path or []),
        "logged_at":       datetime.now(timezone.utc).isoformat(),
    }
    try:
        errors = _get_bq().insert_rows_json(table_ref, [row])
        if errors:
            logger.error("RLHF log insert errors: %s", errors)
            return False
        return True
    except Exception as e:
        logger.error("RLHF logging failed: %s", e)
        return False
