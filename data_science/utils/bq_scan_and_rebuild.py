"""
bq_scan_and_rebuild.py — discover new tables in BigQuery and merge into config v3.

MERGE MODE only — preserves existing entries. Never modifies hand-curated rules,
taxonomy, or applicable_questions for tables already in config.

CLI:
    # Audit only (default, no writes)
    python -m data_science.utils.bq_scan_and_rebuild
    
    # Actually write new tables
    python -m data_science.utils.bq_scan_and_rebuild --add-new
    
    # Skip interactive confirmation
    python -m data_science.utils.bq_scan_and_rebuild --add-new --no-confirm
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import logging
import os
import sys
from typing import Optional

logger = logging.getLogger(__name__)


def _list_matching_datasets(project, pattern):
    from google.cloud import bigquery
    bq = bigquery.Client(project=project)
    matching = []
    for ds in bq.list_datasets():
        if fnmatch.fnmatch(ds.dataset_id, pattern):
            matching.append(ds.dataset_id)
    return sorted(matching)


def _list_tables_in_dataset(project, dataset_id):
    from google.cloud import bigquery
    bq = bigquery.Client(project=project)
    tables = []
    try:
        for t in bq.list_tables(f"{project}.{dataset_id}"):
            if t.table_type in ("TABLE", "VIEW", "MATERIALIZED_VIEW", "EXTERNAL"):
                tables.append(t.table_id)
    except Exception as e:
        logger.warning(f"Could not list tables in {dataset_id}: {e}")
    return sorted(tables)


def _infer_client_id(dataset_id, pattern="Astrobot_*"):
    prefix = pattern.split("*")[0].split("?")[0]
    if dataset_id.startswith(prefix):
        return dataset_id[len(prefix):]
    return dataset_id


def _load_existing_config(config_path):
    if not os.path.exists(config_path):
        return {"datasets": []}
    try:
        with open(config_path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Could not parse {config_path}: {e}")
        return {"datasets": []}


def _table_already_in_config(config, client_id, table_full_path):
    for ds in config.get("datasets", []):
        if ds.get("client_id") != client_id:
            continue
        for t in ds.get("tables", []):
            if t.get("table_full_path", "").lower() == table_full_path.lower():
                return t.get("table_id", "")
    return None


def _guess_table_id(table_name):
    name_lower = table_name.lower()
    if "budget" in name_lower or "pacing" in name_lower or "flight" in name_lower:
        return "pacing"
    return "performance"


def scan(project, pattern, config_path):
    config = _load_existing_config(config_path)
    datasets = _list_matching_datasets(project, pattern)
    existing = []
    new_to_add = []
    for dataset_id in datasets:
        client_id = _infer_client_id(dataset_id, pattern)
        tables = _list_tables_in_dataset(project, dataset_id)
        for table_name in tables:
            full_path = f"{project}.{dataset_id}.{table_name}"
            already = _table_already_in_config(config, client_id, full_path)
            if already:
                existing.append({
                    "client_id": client_id,
                    "table_id": already,
                    "table_full_path": full_path,
                })
            else:
                suggested_id = _guess_table_id(table_name)
                client_exists = any(
                    d.get("client_id") == client_id
                    for d in config.get("datasets", [])
                )
                new_to_add.append({
                    "client_id": client_id,
                    "suggested_table_id": suggested_id,
                    "table_full_path": full_path,
                    "table_name": table_name,
                    "reason": f"Not in config (client {client_id!r} {'exists' if client_exists else 'NEW'})",
                })
    return {
        "datasets_in_bq": datasets,
        "existing_in_config": existing,
        "new_to_add": new_to_add,
    }


def print_diff(diff):
    print("=" * 70)
    print("BQ SCAN — DIFF AGAINST CONFIG")
    print("=" * 70)
    print()
    print(f"BQ datasets found:        {len(diff['datasets_in_bq'])}")
    print(f"  {diff['datasets_in_bq']}")
    print()
    print(f"Tables already in config: {len(diff['existing_in_config'])}")
    for e in diff["existing_in_config"]:
        print(f"  [OK] {e['client_id']:12s} / {e['table_id']:14s} -> {e['table_full_path']}")
    print()
    print(f"Tables NEW (would be added):  {len(diff['new_to_add'])}")
    if not diff["new_to_add"]:
        print("  (none — config matches BQ)")
    for n in diff["new_to_add"]:
        print(f"  [NEW] {n['client_id']:12s} / {n['suggested_table_id']:14s} -> {n['table_full_path']}")
        print(f"        reason: {n['reason']}")
    print()
    print("=" * 70)


def apply_new(new_to_add, confirm=True):
    try:
        from data_science.utils.bq_introspector import write_to_config_directly
    except ImportError:
        from utils.bq_introspector import write_to_config_directly

    summary = {"added": [], "skipped": [], "errors": []}

    if confirm:
        print()
        print(f"About to add {len(new_to_add)} table(s) to config.")
        print("A backup will be created before each write.")
        response = input("Proceed? (yes/no): ").strip().lower()
        if response not in ("yes", "y"):
            print("Aborted. No writes performed.")
            return summary

    for entry in new_to_add:
        client_id = entry["client_id"]
        table_full_path = entry["table_full_path"]
        table_id = entry["suggested_table_id"]
        print()
        print(f"Adding {client_id}/{table_id} -> {table_full_path} ...")
        try:
            result = write_to_config_directly(
                table_full_path=table_full_path,
                client_id=client_id,
                table_id=table_id,
                client_description=(
                    f"Auto-onboarded via bq_scan_and_rebuild "
                    f"from dataset {table_full_path.split('.')[1]}"
                ),
            )
            if result["status"] == "added":
                summary["added"].append(entry)
                print(f"  OK: added")
            elif result["status"] == "exists":
                summary["skipped"].append({**entry, "reason": "already exists"})
                print(f"  SKIP: already exists")
            else:
                summary["errors"].append({**entry, "error": result.get("message", "unknown")})
                print(f"  ERROR: {result.get('message', '')[:200]}")
        except Exception as e:
            summary["errors"].append({**entry, "error": str(e)})
            print(f"  ERROR: {e}")

    return summary


def _main():
    parser = argparse.ArgumentParser(description="Scan BQ and merge new tables into config v3")
    parser.add_argument("--project", default=os.getenv("BQ_DATA_PROJECT_ID", "nc-ai-chatbot"))
    parser.add_argument("--pattern", default="Astrobot_*")
    parser.add_argument("--config", default=None)
    parser.add_argument("--add-new", action="store_true",
                        help="Actually write new tables (default: audit only)")
    parser.add_argument("--no-confirm", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

    config_path = args.config
    if not config_path:
        candidates = [
            os.getenv("DATASET_CONFIG_FILE_V3", ""),
            "/app/ad_campaign_dataset_config_v3.json",
            os.path.expanduser("~/astrobot_mesh/ad_campaign_dataset_config_v3.json"),
            "./ad_campaign_dataset_config_v3.json",
        ]
        for c in candidates:
            if c and os.path.exists(c):
                config_path = c
                break
        if not config_path:
            print("ERROR: Could not locate _v3.json")
            sys.exit(1)

    print(f"Scanning project={args.project!r}, pattern={args.pattern!r}")
    print(f"Config: {config_path}")
    print()

    diff = scan(args.project, args.pattern, config_path)
    print_diff(diff)

    if not args.add_new:
        print()
        print("Audit-only mode. To add new tables, re-run with --add-new")
        print(f"Would add {len(diff['new_to_add'])} table(s).")
        return

    if not diff["new_to_add"]:
        print("Nothing to add — config matches BQ.")
        return

    summary = apply_new(diff["new_to_add"], confirm=not args.no_confirm)

    print()
    print("=" * 70)
    print("APPLY SUMMARY")
    print("=" * 70)
    print(f"Added:    {len(summary['added'])}")
    for e in summary["added"]:
        print(f"  [OK]    {e['client_id']:12s} / {e['suggested_table_id']:14s} -> {e['table_full_path']}")
    print(f"Skipped:  {len(summary['skipped'])}")
    for e in summary["skipped"]:
        print(f"  [SKIP]  {e['client_id']:12s} / {e['suggested_table_id']:14s} -> {e.get('reason','')}")
    print(f"Errors:   {len(summary['errors'])}")
    for e in summary["errors"]:
        print(f"  [ERR]   {e['client_id']:12s} / {e['suggested_table_id']:14s}")
        print(f"          {e.get('error', '')[:200]}")
    print()
    print("Review the updated config and refine any auto-generated taxonomy/rules.")


if __name__ == "__main__":
    _main()
