# deployment/setup_firestore.py
"""
Firestore Setup Script — creates all required collections and seeds initial data.

Run once before first deployment:
    python deployment/setup_firestore.py

Creates:
  - space_client_registry    (Space ID → Client ID mapping)
  - persona_authorizations   (Client → authorised personas)
  - agent_registry           (agent_id → endpoint)
  - scheduled_jobs           (recurring job configs)
  - agent_memory             (cross-session memory, partitioned by client_id)
  - RLHF tables in BigQuery  (feedback_log)
"""

import logging
import os
from datetime import datetime

from google.cloud import bigquery, firestore
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ID   = os.getenv("GOOGLE_CLOUD_PROJECT", "nc-ai-chatbot")
FIRESTORE_DB = os.getenv("FIRESTORE_DB", "(default)")
BQ_RLHF_DS   = os.getenv("BQ_RLHF_DATASET",  "astrobot_rlhf")
BQ_MEM_DS    = os.getenv("BQ_MEMORY_DATASET", "astrobot_memory")


def setup_firestore():
    fs = firestore.Client(project=PROJECT_ID, database=FIRESTORE_DB)

    # ── 1. Space → Client registry ────────────────────────────────────────────
    # In production: add real Google Chat Space IDs here.
    # Format: spaces/XXXXXXXXX (from Google Chat API)
    logger.info("Seeding space_client_registry…")
    spaces = [
        {
            "id":        "spaces/npi_dev_space",
            "client_id": "NPI",
            "active":    True,
            "note":      "NPI development space — replace with real Space ID",
        },
        {
            "id":        "spaces/venetian_dev_space",
            "client_id": "Venetian",
            "active":    True,
            "note":      "Venetian development space — replace with real Space ID",
        },
        {
            "id":        "spaces/winndixie_dev_space",
            "client_id": "WinnDixie",
            "active":    True,
            "note":      "WinnDixie development space — replace with real Space ID",
        },
    ]
    for space in spaces:
        fs.collection("space_client_registry").document(space["id"]).set({
            "client_id":  space["client_id"],
            "active":     space["active"],
            "note":       space["note"],
            "created_at": datetime.utcnow().isoformat(),
        })
        logger.info("  Space '%s' → Client '%s'", space["id"], space["client_id"])

    # ── 2. Persona authorisations ─────────────────────────────────────────────
    logger.info("Seeding persona_authorizations…")
    persona_auth = {
        "NPI": [
            "budget_conscious_shopper",
            "high_intent_researcher",
        ],
        "Venetian": [
            "high_intent_researcher",
            "brand_loyalist",
            "streaming_viewer",
        ],
        "WinnDixie": [
            "budget_conscious_shopper",
            "local_deal_seeker",
            "streaming_viewer",
            "brand_loyalist",
        ],
    }
    for client_id, personas in persona_auth.items():
        fs.collection("persona_authorizations").document(client_id).set({
            "client_id":           client_id,
            "authorised_personas": personas,
            "updated_at":          datetime.utcnow().isoformat(),
        })
        logger.info("  %s → %s", client_id, personas)

    # ── 3. Agent registry (empty — filled by deploy_mesh.py after deployment) ─
    logger.info("Initialising agent_registry…")
    agents = [
        "orchestrator",
        "data_scientist",
        "persona_aggregator",
        "economist",
        "project_manager",
        "scheduler",
    ]
    for agent_id in agents:
        fs.collection("agent_registry").document(agent_id).set({
            "agent_id":   agent_id,
            "endpoint":   "",           # set by deploy_mesh.py after deployment
            "updated_at": datetime.utcnow().isoformat(),
        }, merge=True)
        logger.info("  Agent '%s' registered (no endpoint yet)", agent_id)

    logger.info("✅ Firestore setup complete.")


def setup_bigquery():
    bq = bigquery.Client(project=PROJECT_ID)

    # ── RLHF feedback log table ───────────────────────────────────────────────
    logger.info("Creating BigQuery RLHF dataset and table…")
    try:
        bq.create_dataset(f"{PROJECT_ID}.{BQ_RLHF_DS}", exists_ok=True)
    except Exception:
        pass

    rlhf_schema = [
        bigquery.SchemaField("client_id",  "STRING",    mode="REQUIRED"),
        bigquery.SchemaField("session_id", "STRING"),
        bigquery.SchemaField("prompt",     "STRING"),
        bigquery.SchemaField("response",   "STRING"),
        bigquery.SchemaField("rating",     "INTEGER"),  # 1=positive, -1=negative
        bigquery.SchemaField("correction", "STRING"),
        bigquery.SchemaField("agent_id",   "STRING"),
        bigquery.SchemaField("timestamp",  "TIMESTAMP"),
    ]

    rlhf_table_ref = f"{PROJECT_ID}.{BQ_RLHF_DS}.feedback_log"
    table = bigquery.Table(rlhf_table_ref, schema=rlhf_schema)
    table.time_partitioning = bigquery.TimePartitioning(field="timestamp")
    table.clustering_fields = ["client_id", "agent_id"]

    try:
        bq.create_table(table)
        logger.info("  Created: %s", rlhf_table_ref)
    except Exception:
        logger.info("  Already exists: %s", rlhf_table_ref)

    # ── Memory summary table ──────────────────────────────────────────────────
    logger.info("Creating BigQuery memory dataset and table…")
    try:
        bq.create_dataset(f"{PROJECT_ID}.{BQ_MEM_DS}", exists_ok=True)
    except Exception:
        pass

    memory_schema = [
        bigquery.SchemaField("client_id",  "STRING",    mode="REQUIRED"),
        bigquery.SchemaField("session_id", "STRING"),
        bigquery.SchemaField("summary",    "STRING"),
        bigquery.SchemaField("metadata",   "JSON"),
        bigquery.SchemaField("timestamp",  "TIMESTAMP"),
    ]
    memory_table_ref = f"{PROJECT_ID}.{BQ_MEM_DS}.session_summaries"
    table = bigquery.Table(memory_table_ref, schema=memory_schema)
    table.time_partitioning = bigquery.TimePartitioning(field="timestamp")
    table.clustering_fields = ["client_id"]

    try:
        bq.create_table(table)
        logger.info("  Created: %s", memory_table_ref)
    except Exception:
        logger.info("  Already exists: %s", memory_table_ref)

    logger.info("✅ BigQuery setup complete.")


def setup_bqml_dataset():
    bq = bigquery.Client(project=PROJECT_ID)
    dataset_id = os.getenv("BQML_DATASET_ID", "astrobot_bqml_models")
    try:
        ds = bigquery.Dataset(f"{PROJECT_ID}.{dataset_id}")
        ds.location = "US"
        bq.create_dataset(ds)
        logger.info("✅ BQML dataset created: %s.%s", PROJECT_ID, dataset_id)
    except Exception:
        logger.info("BQML dataset already exists: %s.%s", PROJECT_ID, dataset_id)


if __name__ == "__main__":
    logger.info("Setting up Astro.bot mesh infrastructure…")
    setup_firestore()
    setup_bigquery()
    setup_bqml_dataset()
    logger.info("\n✅ All infrastructure ready. Run deploy_mesh.py next.")
