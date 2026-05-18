"""
One-shot migration: ad_campaign_dataset_config_v3.json → Firestore.

Writes to ds_agent_* prefixed collections (isolated from other agents):

  ds_agent_app_config/dataset_config_v3
    {
      _schema_version, _description, _global_rules, _global_table_types,
      client_ids: [...], last_updated
    }

  ds_agent_datasets/<client_id>
    {client_id, channel_unification, _meta: {table_count, last_updated}}

  ds_agent_datasets/<client_id>/tables/<table_id>
    {table_id, ...all per-table fields...}

Idempotent: re-running updates existing docs (set with merge=True).
Safe to run repeatedly during development.

Usage:
    python deployment/migrate_dataset_config_to_firestore.py
    python deployment/migrate_dataset_config_to_firestore.py --dry-run
    python deployment/migrate_dataset_config_to_firestore.py \\
        --config path/to/some_config.json
"""

from __future__ import annotations
import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Make data_science importable when run from repo root
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from google.cloud import firestore  # noqa: E402

from data_science.utils.firestore_constants import (  # noqa: E402
    DS_AGENT_APP_CONFIG_COLLECTION,
    DS_AGENT_DATASETS_COLLECTION,
    DATASET_CONFIG_DOC_ID,
    TABLES_SUBCOLLECTION,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("migrate")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_config(path: str) -> dict:
    log.info(f"Loading config from {path}")
    with open(path) as f:
        return json.load(f)


def _firestore_client() -> firestore.Client:
    project = os.getenv("GOOGLE_CLOUD_PROJECT", "nc-ai-chatbot")
    database = os.getenv("FIRESTORE_DB", "(default)")
    log.info(f"Firestore client: project={project}, database={database}")
    return firestore.Client(project=project, database=database)


def migrate(config_path: str, dry_run: bool = False) -> dict:
    """
    Returns a dict summarising what was (or would be) written:
        {
          "app_config_doc": 1,
          "client_docs": N,
          "table_docs": M,
        }
    """
    config = _load_config(config_path)

    datasets = config.get("datasets", [])
    if not datasets:
        log.error("Config has no 'datasets' key or it's empty. Aborting.")
        return {"error": "empty"}

    client_ids = [d.get("client_id") for d in datasets if d.get("client_id")]
    log.info(f"Found {len(client_ids)} clients in config: {client_ids}")

    # Build app_config doc payload
    app_config_payload = {
        "_schema_version": config.get("_schema_version"),
        "_description": config.get("_description"),
        "_global_rules": config.get("_global_rules", []),
        "_global_table_types": config.get("_global_table_types", []),
        "client_ids": client_ids,
        "last_updated": _now_iso(),
    }

    # Pre-build all per-client + per-table writes (for accurate dry-run report)
    planned_writes = {
        "app_config": [(DS_AGENT_APP_CONFIG_COLLECTION, DATASET_CONFIG_DOC_ID, app_config_payload)],
        "client_docs": [],
        "table_docs": [],
    }

    for ds in datasets:
        client_id = ds.get("client_id")
        if not client_id:
            log.warning(f"Skipping dataset entry with no client_id: {ds}")
            continue

        tables = ds.get("tables", [])

        client_payload = {
            "client_id": client_id,
            "channel_unification": ds.get("channel_unification", {}),
            "_meta": {
                "table_count": len(tables),
                "last_updated": _now_iso(),
                "migrated_from": "ad_campaign_dataset_config_v3.json",
            },
        }
        planned_writes["client_docs"].append(
            (DS_AGENT_DATASETS_COLLECTION, client_id, client_payload)
        )

        for tbl in tables:
            table_id = tbl.get("table_id")
            if not table_id:
                log.warning(f"Skipping table entry with no table_id (client={client_id}): {tbl}")
                continue
            planned_writes["table_docs"].append(
                (client_id, table_id, tbl)
            )

    log.info(
        f"Planned writes: 1 app_config, "
        f"{len(planned_writes['client_docs'])} client docs, "
        f"{len(planned_writes['table_docs'])} table docs"
    )

    if dry_run:
        log.info("DRY-RUN — no Firestore writes performed.")
        for coll, doc_id, _ in planned_writes["app_config"]:
            log.info(f"  Would write: {coll}/{doc_id}")
        for coll, doc_id, _ in planned_writes["client_docs"]:
            log.info(f"  Would write: {coll}/{doc_id}")
        for cid, tid, _ in planned_writes["table_docs"]:
            log.info(f"  Would write: {DS_AGENT_DATASETS_COLLECTION}/{cid}/{TABLES_SUBCOLLECTION}/{tid}")
        return {
            "dry_run": True,
            "app_config_doc": 1,
            "client_docs": len(planned_writes["client_docs"]),
            "table_docs": len(planned_writes["table_docs"]),
        }

    # ── Real writes ───────────────────────────────────────────────────
    fs = _firestore_client()

    # 1. App config
    for coll, doc_id, payload in planned_writes["app_config"]:
        fs.collection(coll).document(doc_id).set(payload, merge=True)
        log.info(f"  ✓ {coll}/{doc_id}")

    # 2. Client docs
    for coll, doc_id, payload in planned_writes["client_docs"]:
        fs.collection(coll).document(doc_id).set(payload, merge=True)
        log.info(f"  ✓ {coll}/{doc_id}")

    # 3. Table docs (nested under client doc)
    for client_id, table_id, payload in planned_writes["table_docs"]:
        fs.collection(DS_AGENT_DATASETS_COLLECTION).document(client_id) \
          .collection(TABLES_SUBCOLLECTION).document(table_id) \
          .set(payload, merge=True)
        log.info(f"  ✓ {DS_AGENT_DATASETS_COLLECTION}/{client_id}/{TABLES_SUBCOLLECTION}/{table_id}")

    return {
        "dry_run": False,
        "app_config_doc": 1,
        "client_docs": len(planned_writes["client_docs"]),
        "table_docs": len(planned_writes["table_docs"]),
    }


def verify(config_path: str) -> bool:
    """Read back from Firestore + cross-check against the source JSON."""
    config = _load_config(config_path)
    expected_clients = {d["client_id"] for d in config["datasets"] if d.get("client_id")}
    expected_tables = {
        (d["client_id"], t["table_id"])
        for d in config["datasets"]
        for t in d.get("tables", [])
        if d.get("client_id") and t.get("table_id")
    }

    fs = _firestore_client()

    # App config
    app_doc = fs.collection(DS_AGENT_APP_CONFIG_COLLECTION).document(DATASET_CONFIG_DOC_ID).get()
    if not app_doc.exists:
        log.error(f"App config doc MISSING at {DS_AGENT_APP_CONFIG_COLLECTION}/{DATASET_CONFIG_DOC_ID}")
        return False
    log.info(f"  ✓ App config present, client_ids={app_doc.to_dict().get('client_ids')}")

    # Client docs
    actual_clients = set()
    for doc in fs.collection(DS_AGENT_DATASETS_COLLECTION).stream():
        actual_clients.add(doc.id)
    missing = expected_clients - actual_clients
    extra = actual_clients - expected_clients
    if missing:
        log.error(f"Missing client docs: {missing}")
        return False
    if extra:
        log.warning(f"Extra client docs (not in source): {extra}")
    log.info(f"  ✓ Client docs: {sorted(actual_clients)}")

    # Table docs (per client)
    actual_tables = set()
    for cid in actual_clients:
        for tdoc in (
            fs.collection(DS_AGENT_DATASETS_COLLECTION)
              .document(cid)
              .collection(TABLES_SUBCOLLECTION)
              .stream()
        ):
            actual_tables.add((cid, tdoc.id))
    missing_t = expected_tables - actual_tables
    if missing_t:
        log.error(f"Missing table docs: {missing_t}")
        return False
    log.info(f"  ✓ Table docs: {len(actual_tables)} total ({sorted(actual_tables)})")

    log.info("VERIFICATION PASSED")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--config",
        default="ad_campaign_dataset_config_v3.json",
        help="Path to the v3 config JSON to migrate.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be written, do not touch Firestore.",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Skip migration; just verify Firestore matches source.",
    )
    args = parser.parse_args()

    if args.verify_only:
        ok = verify(args.config)
        return 0 if ok else 1

    summary = migrate(args.config, dry_run=args.dry_run)
    log.info(f"Migration summary: {summary}")

    if not args.dry_run:
        log.info("Verifying...")
        ok = verify(args.config)
        return 0 if ok else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
