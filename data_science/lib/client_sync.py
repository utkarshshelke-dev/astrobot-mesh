"""
Dynamic client/table sync between BigQuery and Firestore.

Handles:
  - New clients (new Astrobot_* datasets in BQ)
  - New tables (new views in existing client datasets)
  - Renamed tables (old name gone, new name appears)
  - Called on-demand or via Cloud Scheduler

Usage:
    from data_science.lib.client_sync import sync_all_clients
    result = sync_all_clients(dry_run=False)
"""
import logging
import os
import re
from typing import Optional

logger = logging.getLogger(__name__)

_PROJECT = os.getenv("BQ_DATA_PROJECT_ID", "nc-ai-chatbot")
_DATASET_PREFIX = "Astrobot_"

# Map BQ dataset names to logical client IDs when they differ
# e.g. Astrobot_TWDC → WinnDixie (BQ uses TWDC, system uses WinnDixie)
_DATASET_TO_CLIENT = {
    "TWDC": "WinnDixie",
}
_CLIENT_TO_DATASET = {v: k for k, v in _DATASET_TO_CLIENT.items()}


def _get_bq_client():
    from google.cloud import bigquery
    return bigquery.Client(project=_PROJECT)


def _get_firestore_client():
    from google.cloud import firestore
    return firestore.Client(project=_PROJECT)


def _client_id_from_dataset(dataset_id: str) -> str:
    """Astrobot_WinnDixie → WinnDixie, Astrobot_TWDC → WinnDixie"""
    raw = dataset_id.replace(_DATASET_PREFIX, "", 1)
    return _DATASET_TO_CLIENT.get(raw, raw)


def _discover_bq_clients() -> dict:
    """
    Scan BQ for all Astrobot_* datasets and their views.
    Returns {client_id: {table_id: full_path}}
    """
    bq = _get_bq_client()
    result = {}
    try:
        datasets = list(bq.list_datasets(project=_PROJECT))
        for ds in datasets:
            ds_id = ds.dataset_id
            if not ds_id.startswith(_DATASET_PREFIX):
                continue
            client_id = _client_id_from_dataset(ds_id)
            tables = {}
            for t in bq.list_tables(f"{_PROJECT}.{ds_id}"):
                # Map view names to table_ids
                table_id = _guess_table_id(t.table_id)
                if table_id:
                    tables[table_id] = f"{_PROJECT}.{ds_id}.{t.table_id}"
            if tables:
                result[client_id] = tables
    except Exception as e:
        logger.error(f"BQ scan failed: {e}")
    return result


def _guess_table_id(table_name: str) -> Optional[str]:
    """
    Map BQ view name to logical table_id.
    vw_astrobot_npi_nc360_dashboard → performance
    vw_astrobot_wd_nc360_budget → pacing
    sample_* → performance
    """
    name = table_name.lower()
    if "budget" in name or "pacing" in name:
        return "pacing"
    if "dashboard" in name or "performance" in name or "sample" in name:
        return "performance"
    # Unknown — use the view name as table_id
    return table_name


def _get_firestore_clients() -> dict:
    """
    Read all registered clients from Firestore.
    Returns {client_id: {table_id: full_path}}
    """
    fs = _get_firestore_client()
    result = {}
    try:
        for doc in fs.collection("ds_agent_datasets").stream():
            client_id = doc.id
            tables = {}
            for t_doc in doc.reference.collection("tables").stream():
                t_data = t_doc.to_dict() or {}
                path = t_data.get("table_full_path")
                if path:
                    tables[t_doc.id] = path
            result[client_id] = tables
    except Exception as e:
        logger.error(f"Firestore read failed: {e}")
    return result


def sync_all_clients(dry_run: bool = True) -> dict:
    """
    Compare BQ vs Firestore and sync differences.

    Args:
        dry_run: If True, only report what would change. If False, apply changes.

    Returns:
        {
          "new_clients": [client_id, ...],
          "new_tables": {client_id: [table_id, ...]},
          "renamed_tables": {client_id: {old: new}},
          "missing_tables": {client_id: [table_id, ...]},
          "errors": [...],
          "applied": bool
        }
    """
    bq_clients = _discover_bq_clients()
    fs_clients = _get_firestore_clients()

    new_clients = []
    new_tables = {}
    missing_tables = {}
    renamed_tables = {}
    errors = []

    # Check each BQ client
    for client_id, bq_tables in bq_clients.items():
        fs_tables = fs_clients.get(client_id, {})

        if not fs_tables:
            new_clients.append(client_id)
            new_tables[client_id] = list(bq_tables.keys())
            continue

        # Check for new tables
        added = {k: v for k, v in bq_tables.items() if k not in fs_tables}
        if added:
            new_tables[client_id] = list(added.keys())

        # Check for missing tables (in Firestore but not BQ)
        removed = [k for k in fs_tables if k not in bq_tables]

        # Check for renames — same table_id but different path
        renamed = {}
        for tid, fs_path in fs_tables.items():
            bq_path = bq_tables.get(tid)
            if bq_path and bq_path != fs_path:
                renamed[tid] = {"old": fs_path, "new": bq_path}

        if removed:
            missing_tables[client_id] = removed
        if renamed:
            renamed_tables[client_id] = renamed

    # Check for clients in Firestore but not in BQ
    for client_id in fs_clients:
        if client_id not in bq_clients:
            missing_tables.setdefault(client_id, []).append("(entire client missing from BQ)")

    report = {
        "new_clients": new_clients,
        "new_tables": new_tables,
        "renamed_tables": renamed_tables,
        "missing_tables": missing_tables,
        "errors": errors,
        "applied": False,
    }

    if dry_run:
        logger.info(f"sync_all_clients dry_run: {report}")
        return report

    # Apply changes
    try:
        from data_science.utils.bq_introspector import introspect_table
        from google.cloud import firestore as _fs
        _db = _fs.Client(project=_PROJECT)

        def _register_table(client_id, table_id, full_path):
            """Introspect BQ table and write config to Firestore directly."""
            try:
                result = introspect_table(full_path, client_id, table_id)
                block = result.get("table_block", {})
                if not block:
                    raise ValueError("introspect_table returned empty block")
                _db.collection("ds_agent_datasets").document(client_id)                   .collection("tables").document(table_id).set(block, merge=True)
                # Ensure root doc exists with name
                _db.collection("ds_agent_datasets").document(client_id).set({
                    "client_id": client_id,
                    "name": client_id,
                    "client_filter_value": block.get("client_filter_value", client_id),
                }, merge=True)
                logger.info(f"Registered {client_id}/{table_id}: kpi={block.get('kpi_column')}, channels={len(block.get('channel_taxonomy', {}).get('paid', []))}")
                return "added"
            except Exception as e:
                errors.append(f"Failed to register {client_id}/{table_id}: {e}")
                logger.error(f"Failed to register {client_id}/{table_id}: {e}")
                return "error"

        # Register new clients
        for client_id in new_clients:
            bq_tables = bq_clients[client_id]
            for table_id, full_path in bq_tables.items():
                _register_table(client_id, table_id, full_path)

        # Register new tables for existing clients
        for client_id, table_ids in new_tables.items():
            if client_id in new_clients:
                continue
            for table_id in table_ids:
                full_path = bq_clients[client_id][table_id]
                _register_table(client_id, table_id, full_path)

        # Fix renamed tables — update path in Firestore directly
        fs = _get_firestore_client()
        for client_id, renames in renamed_tables.items():
            for table_id, paths in renames.items():
                try:
                    doc_ref = (fs.collection("ds_agent_datasets")
                                 .document(client_id)
                                 .collection("tables")
                                 .document(table_id))
                    doc_ref.update({"table_full_path": paths["new"]})
                    logger.info(f"Updated renamed table path: {client_id}/{table_id}: {paths['old']} → {paths['new']}")
                except Exception as e:
                    errors.append(f"Failed to rename {client_id}/{table_id}: {e}")

        report["applied"] = True
        report["errors"] = errors

    except Exception as e:
        errors.append(f"Sync apply failed: {e}")
        report["errors"] = errors

    return report
