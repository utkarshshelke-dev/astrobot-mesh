"""
config_writer.py — gated, two-phase, human-approved writer for
ad_campaign_dataset_config_v3.json.

This module is the safety gate that KnowledgeManager deliberately left out.
KnowledgeManager stays strictly read-only; this is a SEPARATE sibling module.
Normal query handling never touches it.

Design (decided):
  - Caller   : the data science orchestrator (an LLM) initiates proposals.
  - Approval : human-in-the-loop, two-phase.

      propose_change(change)              -> WriteResult(status="pending", token=...)
          runs Gate 1 (schema) + Gate 2 (test suite), touches NOTHING.
          The orchestrator shows the user `diff_summary` and asks for approval.

      confirm_change(token, confirmed_by) -> WriteResult(status="committed", ...)
          re-runs Gate 2, then Gate 3 (backup + atomic replace + cache reset).
          The ONLY thing that ever writes the real file.

Nothing here lets the LLM write directly: propose_change physically does not
commit, and confirm_change requires a token that only a gate-passing proposal
produces, plus a named human in `confirmed_by`.

Dependencies: only the standard library + lib.channel_resolver (load_config_v3,
reset_config_cache). No pydantic — the schema check is hand-rolled to keep the
deterministic layer dependency-free.
"""

from __future__ import annotations

import copy
import datetime as _dt
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Literal, Optional, TypedDict

# This is the only project import. lib/ is the tested deterministic layer.
# The test suite's conftest.py inserts the repo root (~/astrobot_mesh/) on
# sys.path, so `data_science.lib...` is the canonical import. The bare
# `lib...` form is kept as a fallback for standalone/alternate layouts.
try:
    from data_science.lib.channel_resolver import (
        load_config_v3,
        reset_config_cache,
    )
except ImportError:  # pragma: no cover - alternate layout fallback
    from lib.channel_resolver import load_config_v3, reset_config_cache


# ----------------------------------------------------------------------
# Constants & configuration
# ----------------------------------------------------------------------

#: How long a pending proposal token stays valid, in seconds.
PROPOSAL_TTL = 60 * 60  # 1 hour

#: How many timestamped backups to keep. Oldest beyond this are pruned.
MAX_BACKUPS = 20

#: Hard timeout for the Gate 2 subprocess (pytest run), in seconds.
TEST_GATE_TIMEOUT = 120

#: Where the deterministic test suite lives, relative to the project root
#: (the directory containing ad_campaign_dataset_config_v3.json, i.e.
#: ~/astrobot_mesh/). The 131 deterministic tests live in data_science_tests/.
TEST_SUITE_RELPATH = "data_science_tests/"

#: Gate 2 runs the deterministic suite but must NOT recursively run this
#: module's OWN test file (test_config_writer.py also lives in
#: data_science_tests/). We exclude it by basename via pytest's --ignore.
TEST_GATE_IGNORE = "test_config_writer.py"

#: Recognized structured-patch operations.
_SUPPORTED_OPS = {"add_channel", "add_rule", "add_client", "add_table"}

#: project.dataset.table — loose but catches obvious malformations.
_TABLE_PATH_RE = re.compile(r"^[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+$")


class WriteResult(TypedDict):
    """Structured result returned by every public entry point."""

    status: Literal["pending", "committed", "rejected", "expired"]
    gate_failed: Optional[Literal["schema", "tests"]]
    errors: list[str]
    token: Optional[str]
    diff_summary: str
    gates_passed: list[str]
    backup_path: Optional[str]


# ----------------------------------------------------------------------
# Path helpers
# ----------------------------------------------------------------------

def _resolve_config_path(config_path: Optional[str]) -> Path:
    """Resolve the real config path, mirroring channel_resolver's lookup order."""
    if config_path:
        return Path(config_path).expanduser().resolve()

    env_path = os.getenv("DATASET_CONFIG_FILE_V3")
    if env_path:
        return Path(env_path).expanduser().resolve()

    candidates = [
        Path("/app/ad_campaign_dataset_config_v3.json"),
        Path("~/astrobot_mesh/ad_campaign_dataset_config_v3.json").expanduser(),
        Path("./ad_campaign_dataset_config_v3.json"),
    ]
    for c in candidates:
        if c.exists():
            return c.resolve()
    raise FileNotFoundError(
        "Could not locate ad_campaign_dataset_config_v3.json. "
        "Pass config_path explicitly or set DATASET_CONFIG_FILE_V3."
    )


def _project_root(config_path: Path) -> Path:
    """The directory holding the config file is treated as the project root."""
    return config_path.parent


def _pending_dir(config_path: Path) -> Path:
    d = _project_root(config_path) / "pending_changes"
    d.mkdir(exist_ok=True)
    return d


def _audit_log_path(config_path: Path) -> Path:
    return _project_root(config_path) / "config_changes.log"


# ----------------------------------------------------------------------
# Audit log
# ----------------------------------------------------------------------

def _audit(config_path: Path, entry: dict) -> None:
    """Append one structured, append-only line to config_changes.log."""
    entry = {"timestamp": _dt.datetime.now(_dt.timezone.utc).isoformat(), **entry}
    line = json.dumps(entry, sort_keys=True, default=str)
    with open(_audit_log_path(config_path), "a", encoding="utf-8") as fh:
        fh.write(line + "\n")


# ----------------------------------------------------------------------
# Change application — turn a structured patch into a new config dict
# ----------------------------------------------------------------------

def _find_dataset(config: dict, client_id: str) -> Optional[dict]:
    return next(
        (d for d in config.get("datasets", []) if d.get("client_id") == client_id),
        None,
    )


def _find_table(dataset: dict, table_id: str) -> Optional[dict]:
    return next(
        (t for t in dataset.get("tables", []) if t.get("table_id") == table_id),
        None,
    )


def _apply_change(config: dict, change: dict) -> tuple[dict, str]:
    """
    Apply a structured patch to an in-memory DEEP COPY of `config`.

    Returns (new_config, diff_summary).
    Raises ValueError if the op is unknown or the patch is internally malformed
    (e.g. targets a client/table that does not exist). Schema validity of the
    *result* is Gate 1's job, not this function's.
    """
    op = change.get("op")
    if op not in _SUPPORTED_OPS:
        raise ValueError(
            f"Unknown op {op!r}. Supported: {sorted(_SUPPORTED_OPS)}"
        )

    new = copy.deepcopy(config)

    if op == "add_channel":
        client_id = change["client_id"]
        table_id = change["table_id"]
        category = change["category"]
        channel = change["channel"]

        dataset = _find_dataset(new, client_id)
        if dataset is None:
            raise ValueError(f"add_channel: unknown client_id {client_id!r}")
        table = _find_table(dataset, table_id)
        if table is None:
            raise ValueError(
                f"add_channel: unknown table_id {table_id!r} for client {client_id!r}"
            )
        taxonomy = table.setdefault("channel_taxonomy", {})
        bucket = taxonomy.setdefault(category, [])
        if channel in bucket:
            raise ValueError(
                f"add_channel: {channel!r} already in {client_id}/{table_id}/{category}"
            )
        bucket.append(channel)
        diff = (
            f"add_channel: '{channel}' -> {client_id}/{table_id} "
            f"channel_taxonomy['{category}']"
        )
        return new, diff

    if op == "add_rule":
        rule_id = change["rule_id"]
        description = change["description"]
        attach_to = change.get("attach_to", [])

        global_rules = new.setdefault("_global_rules", {})
        rule_defs = global_rules.setdefault("rule_definitions", {})
        if rule_id in rule_defs:
            raise ValueError(f"add_rule: rule_id {rule_id!r} already defined")
        rule_defs[rule_id] = description

        attached = []
        for target in attach_to:
            client_id = target["client_id"]
            table_id = target["table_id"]
            dataset = _find_dataset(new, client_id)
            if dataset is None:
                raise ValueError(f"add_rule: unknown client_id {client_id!r}")
            table = _find_table(dataset, table_id)
            if table is None:
                raise ValueError(
                    f"add_rule: unknown table_id {table_id!r} for client {client_id!r}"
                )
            rules = table.setdefault("rules", [])
            if rule_id not in rules:
                rules.append(rule_id)
            attached.append(f"{client_id}/{table_id}")

        suffix = f" attached to {', '.join(attached)}" if attached else " (defined only)"
        diff = f"add_rule: '{rule_id}'{suffix}"
        return new, diff

    if op == "add_table":
        client_id = change["client_id"]
        table_block = change["table_block"]
        dataset = _find_dataset(new, client_id)
        if dataset is None:
            raise ValueError(f"add_table: unknown client_id {client_id!r}")
        table_id = table_block.get("table_id")
        if not table_id:
            raise ValueError("add_table: table_block missing 'table_id'")
        if _find_table(dataset, table_id) is not None:
            raise ValueError(
                f"add_table: table_id {table_id!r} already exists for client {client_id!r}"
            )
        dataset.setdefault("tables", []).append(copy.deepcopy(table_block))
        diff = f"add_table: '{table_id}' -> client '{client_id}'"
        return new, diff

    if op == "add_client":
        client_id = change["client_id"]
        dataset_block = change["dataset"]
        if _find_dataset(new, client_id) is not None:
            raise ValueError(f"add_client: client_id {client_id!r} already exists")
        # Ensure the block's own client_id is consistent with the op.
        block = copy.deepcopy(dataset_block)
        block["client_id"] = client_id
        new.setdefault("datasets", []).append(block)
        n_tables = len(block.get("tables", []))
        diff = f"add_client: '{client_id}' with {n_tables} table(s)"
        return new, diff

    # Unreachable — _SUPPORTED_OPS guard above covers all cases.
    raise ValueError(f"Unhandled op {op!r}")  # pragma: no cover


# ----------------------------------------------------------------------
# Gate 1 — schema validation
# ----------------------------------------------------------------------

def _validate_schema(config: dict) -> list[str]:
    """
    Hand-rolled structural validation of a full v3 config dict.

    Returns a list of human-readable error strings. Empty list == valid.
    """
    errors: list[str] = []

    if not isinstance(config, dict):
        return ["config root is not a dict"]

    # --- top-level keys -------------------------------------------------
    datasets = config.get("datasets")
    if not isinstance(datasets, list) or not datasets:
        errors.append("top-level 'datasets' must be a non-empty list")
        datasets = datasets if isinstance(datasets, list) else []

    global_rules = config.get("_global_rules")
    if not isinstance(global_rules, dict):
        errors.append("top-level '_global_rules' must be a dict")
        global_rules = {}
    rule_defs = global_rules.get("rule_definitions", {})
    if not isinstance(rule_defs, dict):
        errors.append("'_global_rules.rule_definitions' must be a dict")
        rule_defs = {}
    defined_rule_ids = set(rule_defs.keys())

    # --- per-dataset / per-table ---------------------------------------
    seen_client_ids: set[str] = set()

    for di, dataset in enumerate(datasets):
        where = f"datasets[{di}]"
        if not isinstance(dataset, dict):
            errors.append(f"{where} is not a dict")
            continue

        client_id = dataset.get("client_id")
        if not client_id or not isinstance(client_id, str):
            errors.append(f"{where} missing non-empty string 'client_id'")
        else:
            if client_id in seen_client_ids:
                errors.append(f"duplicate client_id {client_id!r}")
            seen_client_ids.add(client_id)
            where = f"datasets[{di}]({client_id})"

        if not dataset.get("name") or not isinstance(dataset.get("name"), str):
            errors.append(f"{where} missing non-empty string 'name'")

        tables = dataset.get("tables")
        if not isinstance(tables, list) or not tables:
            errors.append(f"{where} 'tables' must be a non-empty list")
            continue

        seen_table_ids: set[str] = set()
        for ti, table in enumerate(tables):
            twhere = f"{where}.tables[{ti}]"
            if not isinstance(table, dict):
                errors.append(f"{twhere} is not a dict")
                continue

            table_id = table.get("table_id")
            if not table_id or not isinstance(table_id, str):
                errors.append(f"{twhere} missing non-empty string 'table_id'")
            else:
                if table_id in seen_table_ids:
                    errors.append(
                        f"{where} has duplicate table_id {table_id!r}"
                    )
                seen_table_ids.add(table_id)
                twhere = f"{where}.tables[{ti}]({table_id})"

            for required in ("table_full_path", "channel_column", "kpi_column"):
                val = table.get(required)
                if not val or not isinstance(val, str):
                    errors.append(
                        f"{twhere} missing non-empty string '{required}'"
                    )

            tfp = table.get("table_full_path")
            if isinstance(tfp, str) and tfp and not _TABLE_PATH_RE.match(tfp):
                errors.append(
                    f"{twhere} table_full_path {tfp!r} is not project.dataset.table"
                )

            # channel_taxonomy: every value must be a list of non-empty strings
            taxonomy = table.get("channel_taxonomy", {})
            if not isinstance(taxonomy, dict):
                errors.append(f"{twhere} 'channel_taxonomy' must be a dict")
            else:
                for category, members in taxonomy.items():
                    if not isinstance(members, list):
                        errors.append(
                            f"{twhere} channel_taxonomy['{category}'] is not a list"
                        )
                        continue
                    for m in members:
                        if not isinstance(m, str) or not m.strip():
                            errors.append(
                                f"{twhere} channel_taxonomy['{category}'] "
                                f"contains a non-string/empty entry: {m!r}"
                            )

            # rules: every referenced rule_id must be defined globally
            rules = table.get("rules", [])
            if not isinstance(rules, list):
                errors.append(f"{twhere} 'rules' must be a list")
            else:
                for rule_id in rules:
                    if rule_id not in defined_rule_ids:
                        errors.append(
                            f"{twhere} references undefined rule_id {rule_id!r} "
                            f"(not in _global_rules.rule_definitions)"
                        )

    return errors


# ----------------------------------------------------------------------
# Gate 2 — test-suite gate
# ----------------------------------------------------------------------

def _run_test_gate(proposed_config: dict, config_path: Path) -> list[str]:
    """
    Write `proposed_config` to a temp file, point DATASET_CONFIG_FILE_V3 at it,
    and run the full deterministic test suite as a subprocess.

    Returns a list of error strings. Empty list == all tests passed.
    """
    project_root = _project_root(config_path)
    test_dir = project_root / TEST_SUITE_RELPATH
    if not test_dir.exists():
        return [f"test suite not found at {test_dir}"]

    tmp_fd, tmp_name = tempfile.mkstemp(
        suffix=".json", prefix="proposed_config_", dir=str(project_root)
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
            json.dump(proposed_config, fh, indent=2)

        env = dict(os.environ)
        env["DATASET_CONFIG_FILE_V3"] = tmp_name

        try:
            proc = subprocess.run(
                [
                    sys.executable, "-m", "pytest",
                    str(test_dir), "-q", "--tb=no", "--no-header",
                    # Don't recursively run this module's own test file.
                    f"--ignore={test_dir / TEST_GATE_IGNORE}",
                ],
                cwd=str(project_root),
                env=env,
                capture_output=True,
                text=True,
                timeout=TEST_GATE_TIMEOUT,
            )
        except subprocess.TimeoutExpired:
            return [f"test gate timed out after {TEST_GATE_TIMEOUT}s"]

        if proc.returncode == 0:
            return []

        # Extract failing test node ids from pytest output.
        failing = re.findall(r"^(FAILED|ERROR)\s+(\S+)", proc.stdout, re.MULTILINE)
        if failing:
            return [f"{kind}: {nodeid}" for kind, nodeid in failing]
        # Fallback: surface the tail of stdout so the failure isn't opaque.
        tail = proc.stdout.strip().splitlines()[-5:]
        return ["test gate failed:"] + tail
    finally:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:  # pragma: no cover
            pass


# ----------------------------------------------------------------------
# Gate 3 — atomic commit with backup
# ----------------------------------------------------------------------

def _prune_backups(config_path: Path) -> None:
    backups = sorted(
        config_path.parent.glob(config_path.name + ".bak.*"),
        key=lambda p: p.name,
        reverse=True,
    )
    for stale in backups[MAX_BACKUPS:]:
        try:
            stale.unlink()
        except FileNotFoundError:  # pragma: no cover
            pass


def _firestore_commit(proposed_config: dict) -> str:
    """Write proposed_config to Firestore (ds_agent_* collections).

    Inverse of channel_resolver._load_from_firestore. Writes:
      ds_agent_app_config/dataset_config_v3 (globals + client_ids index)
      ds_agent_datasets/<client_id>          (client metadata + channel_unification)
      ds_agent_datasets/<client_id>/tables/<table_id>  (per-table dicts)

    Uses a Firestore batched write for atomicity (single network round-trip,
    all-or-nothing semantics within the batch).

    Resets channel_resolver._CONFIG_CACHE after write so subsequent
    load_config_v3() calls see the new state.

    Returns:
        Short audit message (e.g. "firestore: wrote 1 app_config + 3 clients + 6 tables")
    """
    from datetime import datetime, timezone
    from google.cloud import firestore as _firestore
    from data_science.utils.firestore_constants import (
        DS_AGENT_APP_CONFIG_COLLECTION,
        DS_AGENT_DATASETS_COLLECTION,
        DATASET_CONFIG_DOC_ID,
        TABLES_SUBCOLLECTION,
    )

    project = os.getenv("GOOGLE_CLOUD_PROJECT", "nc-ai-chatbot")
    database = os.getenv("FIRESTORE_DB", "(default)")
    fs = _firestore.Client(project=project, database=database)

    now_iso = datetime.now(timezone.utc).isoformat()

    datasets = proposed_config.get("datasets", [])
    client_ids = [d["client_id"] for d in datasets if d.get("client_id")]

    batch = fs.batch()
    n_app, n_clients, n_tables = 0, 0, 0

    # 1. App config doc — globals + client index
    app_ref = (
        fs.collection(DS_AGENT_APP_CONFIG_COLLECTION)
          .document(DATASET_CONFIG_DOC_ID)
    )
    batch.set(app_ref, {
        "_schema_version": proposed_config.get("_schema_version"),
        "_description": proposed_config.get("_description"),
        "_global_rules": proposed_config.get("_global_rules", []),
        "_global_table_types": proposed_config.get("_global_table_types", []),
        "client_ids": client_ids,
        "last_updated": now_iso,
    }, merge=True)
    n_app = 1

    # 2. Per-client docs + 3. Per-table subcollection docs
    for ds in datasets:
        cid = ds.get("client_id")
        if not cid:
            continue
        tables = ds.get("tables", [])

        # Client doc (strip tables — they go to subcollection)
        client_payload = {
            "client_id": cid,
            "channel_unification": ds.get("channel_unification", {}),
            "_meta": {
                "table_count": len(tables),
                "last_updated": now_iso,
            },
        }
        client_ref = fs.collection(DS_AGENT_DATASETS_COLLECTION).document(cid)
        batch.set(client_ref, client_payload, merge=True)
        n_clients += 1

        # Table docs in subcollection
        for tbl in tables:
            table_id = tbl.get("table_id")
            if not table_id:
                continue
            table_ref = client_ref.collection(TABLES_SUBCOLLECTION).document(table_id)
            batch.set(table_ref, tbl, merge=True)
            n_tables += 1

    # Commit the batch atomically (single network call)
    batch.commit()

    # Reset read-side cache so subsequent load_config_v3() picks up changes
    try:
        from data_science.lib.channel_resolver import reset_config_cache
        reset_config_cache()
    except Exception:
        pass  # never let cache-reset failure break the write

    return f"firestore: wrote {n_app} app_config + {n_clients} clients + {n_tables} tables"


def _atomic_commit(proposed_config: dict, config_path: Path) -> str:
    """
    Backup the current real config, atomically replace it with proposed_config,
    reset the KnowledgeManager cache, prune old backups.

    Returns the backup path.
    """
    stamp = _dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = config_path.parent / f"{config_path.name}.bak.{stamp}"

    # 1. backup current real config
    if config_path.exists():
        backup_path.write_text(
            config_path.read_text(encoding="utf-8"), encoding="utf-8"
        )

    # 2. write proposed config to a temp file in the same directory
    tmp_fd, tmp_name = tempfile.mkstemp(
        suffix=".json", prefix=".commit_", dir=str(config_path.parent)
    )
    with os.fdopen(tmp_fd, "w", encoding="utf-8") as fh:
        json.dump(proposed_config, fh, indent=2)

    # 3. atomic replace (POSIX: os.replace is atomic on the same filesystem)
    os.replace(tmp_name, config_path)

    # 4. reset the read-only layer's cache so the running process sees the change
    try:
        reset_config_cache()
    except Exception:  # pragma: no cover - cache reset is best-effort
        pass

    # 5. prune old backups
    _prune_backups(config_path)

    return str(backup_path)


# ----------------------------------------------------------------------
# Pending-proposal token storage
# ----------------------------------------------------------------------

def _new_token() -> str:
    return f"{uuid.uuid4().hex[:8]}-{secrets.token_hex(4)}"


def _pending_path(config_path: Path, token: str) -> Path:
    return _pending_dir(config_path) / f"{token}.json"


def _store_pending(
    config_path: Path,
    token: str,
    proposed_config: dict,
    change: dict,
    diff_summary: str,
    gates_passed: list[str],
) -> None:
    payload = {
        "token": token,
        "created_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "change": change,
        "diff_summary": diff_summary,
        "gates_passed": gates_passed,
        "proposed_config": proposed_config,
    }
    _pending_path(config_path, token).write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


def _load_pending(config_path: Path, token: str) -> Optional[dict]:
    path = _pending_path(config_path, token)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):  # pragma: no cover
        return None


def _delete_pending(config_path: Path, token: str) -> None:
    try:
        _pending_path(config_path, token).unlink()
    except FileNotFoundError:
        pass


def _is_expired(payload: dict) -> bool:
    created = _dt.datetime.fromisoformat(payload["created_at"])
    age = (_dt.datetime.now(_dt.timezone.utc) - created).total_seconds()
    return age > PROPOSAL_TTL


def _sweep_expired(config_path: Path) -> None:
    """Best-effort cleanup of expired pending proposals."""
    for path in _pending_dir(config_path).glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if _is_expired(payload):
                path.unlink()
        except (json.JSONDecodeError, OSError, KeyError, ValueError):  # pragma: no cover
            pass


# ----------------------------------------------------------------------
# Result helpers
# ----------------------------------------------------------------------

def _rejected(
    gate_failed: Optional[Literal["schema", "tests"]],
    errors: list[str],
    diff_summary: str = "",
    gates_passed: Optional[list[str]] = None,
) -> WriteResult:
    return WriteResult(
        status="rejected",
        gate_failed=gate_failed,
        errors=errors,
        token=None,
        diff_summary=diff_summary,
        gates_passed=gates_passed or [],
        backup_path=None,
    )


# ----------------------------------------------------------------------
# Phase 1 — propose_change (read-only; touches nothing)
# ----------------------------------------------------------------------

def propose_change(
    change: dict,
    *,
    config_path: Optional[str] = None,
    run_tests: bool = True,
) -> WriteResult:
    """
    Phase 1. Validate a structured patch without writing anything.

    Runs Gate 1 (schema) and Gate 2 (test suite, unless run_tests=False) against
    an in-memory copy of the config with the change applied. On success, stores
    a pending proposal and returns status="pending" with a single-use token and
    a human-readable diff_summary for the orchestrator to show the user.

    The real config file is NEVER modified by this function.
    """
    cfg_path = _resolve_config_path(config_path)
    _sweep_expired(cfg_path)

    current = load_config_v3(str(cfg_path))

    # Apply the structured patch to an in-memory deep copy.
    try:
        proposed, diff_summary = _apply_change(current, change)
    except (ValueError, KeyError) as exc:
        result = _rejected("schema", [f"invalid change patch: {exc}"])
        _audit(cfg_path, {
            "phase": "propose", "change": change, "result": "rejected",
            "gate_failed": "schema", "errors": result["errors"],
        })
        return result

    # Gate 1 — schema validation
    schema_errors = _validate_schema(proposed)
    if schema_errors:
        result = _rejected("schema", schema_errors, diff_summary)
        _audit(cfg_path, {
            "phase": "propose", "change": change, "diff_summary": diff_summary,
            "result": "rejected", "gate_failed": "schema", "errors": schema_errors,
        })
        return result

    gates_passed = ["schema"]

    # Gate 2 — test-suite gate
    if run_tests:
        test_errors = _run_test_gate(proposed, cfg_path)
        if test_errors:
            result = _rejected("tests", test_errors, diff_summary, gates_passed)
            _audit(cfg_path, {
                "phase": "propose", "change": change,
                "diff_summary": diff_summary, "result": "rejected",
                "gate_failed": "tests", "errors": test_errors,
            })
            return result
        gates_passed.append("tests")

    # Both read-only gates passed — issue a pending token. Nothing written yet.
    token = _new_token()
    _store_pending(cfg_path, token, proposed, change, diff_summary, gates_passed)
    _audit(cfg_path, {
        "phase": "propose", "change": change, "diff_summary": diff_summary,
        "result": "pending", "token": token, "gates_passed": gates_passed,
    })

    return WriteResult(
        status="pending",
        gate_failed=None,
        errors=[],
        token=token,
        diff_summary=diff_summary,
        gates_passed=gates_passed,
        backup_path=None,
    )


# ----------------------------------------------------------------------
# Phase 2 — confirm_change (the only writer)
# ----------------------------------------------------------------------

def confirm_change(
    token: str,
    *,
    confirmed_by: str,
    config_path: Optional[str] = None,
) -> WriteResult:
    """
    Phase 2. Commit a previously-proposed change.

    Requires a valid, unexpired token from propose_change and a non-empty
    `confirmed_by` (the human approver — recorded in the audit log; there is
    no anonymous commit).

    Re-runs Gate 2 against the pending config (the real config or the test
    suite could have changed since propose_change), then runs Gate 3:
    timestamped backup, atomic replace, cache reset, backup pruning.

    A token is single-use: it is deleted whether the commit succeeds or fails.
    """
    if not confirmed_by or not str(confirmed_by).strip():
        raise ValueError(
            "confirm_change requires a non-empty 'confirmed_by' — "
            "no anonymous commits."
        )

    cfg_path = _resolve_config_path(config_path)

    # NB: load the token's payload BEFORE sweeping. The sweep deletes expired
    # pending files, but confirm_change needs to distinguish "unknown token"
    # (rejected) from "known but expired token" (expired) — so the explicit
    # expiry check below must see the payload first.
    payload = _load_pending(cfg_path, token)
    if payload is None:
        result = _rejected("schema", [f"unknown or already-used token {token!r}"])
        _audit(cfg_path, {
            "phase": "confirm", "token": token, "confirmed_by": confirmed_by,
            "result": "rejected", "errors": result["errors"],
        })
        return result

    if _is_expired(payload):
        _delete_pending(cfg_path, token)
        _audit(cfg_path, {
            "phase": "confirm", "token": token, "confirmed_by": confirmed_by,
            "result": "expired",
        })
        return WriteResult(
            status="expired",
            gate_failed=None,
            errors=[f"token {token!r} expired (TTL {PROPOSAL_TTL}s)"],
            token=None,
            diff_summary=payload.get("diff_summary", ""),
            gates_passed=[],
            backup_path=None,
        )

    proposed = payload["proposed_config"]
    diff_summary = payload.get("diff_summary", "")

    # Token is single-use: consume it now, regardless of what happens next.
    _delete_pending(cfg_path, token)

    # Re-run Gate 2 — the propose -> confirm gap could have changed things.
    test_errors = _run_test_gate(proposed, cfg_path)
    if test_errors:
        result = _rejected("tests", test_errors, diff_summary, ["schema"])
        _audit(cfg_path, {
            "phase": "confirm", "token": token, "confirmed_by": confirmed_by,
            "diff_summary": diff_summary, "result": "rejected",
            "gate_failed": "tests", "errors": test_errors,
        })
        return result

    # Gate 3 — atomic commit. Backend selected by USE_FIRESTORE_CONFIG.
    if os.getenv("USE_FIRESTORE_CONFIG", "").lower() == "true":
        backup_path = _firestore_commit(proposed)
    else:
        backup_path = _atomic_commit(proposed, cfg_path)
    _audit(cfg_path, {
        "phase": "confirm", "token": token, "confirmed_by": confirmed_by,
        "diff_summary": diff_summary, "result": "committed",
        "gate_failed": None, "gates_passed": ["schema", "tests"],
        "backup_path": backup_path,
    })

    return WriteResult(
        status="committed",
        gate_failed=None,
        errors=[],
        token=None,
        diff_summary=diff_summary,
        gates_passed=["schema", "tests"],
        backup_path=backup_path,
    )


# ----------------------------------------------------------------------
# Support — listing & rollback
# ----------------------------------------------------------------------

def list_pending(config_path: Optional[str] = None) -> list[WriteResult]:
    """Return all currently-pending (unexpired, unconfirmed) proposals."""
    cfg_path = _resolve_config_path(config_path)
    _sweep_expired(cfg_path)

    out: list[WriteResult] = []
    for path in sorted(_pending_dir(cfg_path).glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):  # pragma: no cover
            continue
        if _is_expired(payload):
            continue
        out.append(WriteResult(
            status="pending",
            gate_failed=None,
            errors=[],
            token=payload["token"],
            diff_summary=payload.get("diff_summary", ""),
            gates_passed=payload.get("gates_passed", []),
            backup_path=None,
        ))
    return out


def list_backups(config_path: Optional[str] = None) -> list[str]:
    """Return timestamped backup paths, newest first."""
    cfg_path = _resolve_config_path(config_path)
    backups = sorted(
        cfg_path.parent.glob(cfg_path.name + ".bak.*"),
        key=lambda p: p.name,
        reverse=True,
    )
    return [str(p) for p in backups]


def rollback(
    backup_path: str,
    *,
    confirmed_by: str,
    config_path: Optional[str] = None,
) -> WriteResult:
    """
    Restore a previous backup over the live config.

    Still runs Gate 2 against the backup before committing — a backup that no
    longer passes the current test suite is NOT silently restored. Requires
    `confirmed_by` and is audit-logged like confirm_change.
    """
    if not confirmed_by or not str(confirmed_by).strip():
        raise ValueError("rollback requires a non-empty 'confirmed_by'.")

    cfg_path = _resolve_config_path(config_path)
    bpath = Path(backup_path).expanduser().resolve()

    if not bpath.exists():
        result = _rejected("schema", [f"backup not found: {backup_path}"])
        _audit(cfg_path, {
            "phase": "rollback", "backup_path": backup_path,
            "confirmed_by": confirmed_by, "result": "rejected",
            "errors": result["errors"],
        })
        return result

    try:
        backup_config = json.loads(bpath.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        result = _rejected("schema", [f"backup is not valid JSON: {exc}"])
        _audit(cfg_path, {
            "phase": "rollback", "backup_path": backup_path,
            "confirmed_by": confirmed_by, "result": "rejected",
            "errors": result["errors"],
        })
        return result

    # Gate 1 on the backup — defends against restoring something already corrupt.
    schema_errors = _validate_schema(backup_config)
    if schema_errors:
        result = _rejected("schema", schema_errors)
        _audit(cfg_path, {
            "phase": "rollback", "backup_path": backup_path,
            "confirmed_by": confirmed_by, "result": "rejected",
            "gate_failed": "schema", "errors": schema_errors,
        })
        return result

    # Gate 2 on the backup — don't restore something that fails current tests.
    test_errors = _run_test_gate(backup_config, cfg_path)
    if test_errors:
        result = _rejected("tests", test_errors, gates_passed=["schema"])
        _audit(cfg_path, {
            "phase": "rollback", "backup_path": backup_path,
            "confirmed_by": confirmed_by, "result": "rejected",
            "gate_failed": "tests", "errors": test_errors,
        })
        return result

    # Backend selected by USE_FIRESTORE_CONFIG (rollback path).
    if os.getenv("USE_FIRESTORE_CONFIG", "").lower() == "true":
        new_backup = _firestore_commit(backup_config)
    else:
        new_backup = _atomic_commit(backup_config, cfg_path)
    _audit(cfg_path, {
        "phase": "rollback", "backup_path": backup_path,
        "confirmed_by": confirmed_by, "result": "committed",
        "restored_from": backup_path, "pre_rollback_backup": new_backup,
        "gates_passed": ["schema", "tests"],
    })

    return WriteResult(
        status="committed",
        gate_failed=None,
        errors=[],
        token=None,
        diff_summary=f"rollback: restored {bpath.name}",
        gates_passed=["schema", "tests"],
        backup_path=new_backup,
    )