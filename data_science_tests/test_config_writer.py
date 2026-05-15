"""
test_config_writer.py — TDD coverage for the gated, two-phase config writer.

Layout assumption (matches the existing test scaffolding):
    ~/astrobot_mesh/
      ├── ad_campaign_dataset_config_v3.json
      └── data_science/
          ├── lib/
          ├── utils/config_writer.py
          └── tests/test_config_writer.py   <-- this file

Most tests run with run_tests=False so Gate 2 (the pytest subprocess) is
skipped — that keeps this suite sub-second. Two integration tests exercise
the real Gate 2 subprocess path and are marked accordingly.

Every test operates on a TEMP COPY of the config (via the `sandbox` fixture);
the real ad_campaign_dataset_config_v3.json is never touched.
"""

import hashlib
import json
import os
import shutil
import time
from pathlib import Path

import pytest

from data_science.utils import config_writer as cw


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------

@pytest.fixture
def real_config_path():
    """Locate the real v3 config the same way the module does."""
    return cw._resolve_config_path(None)


@pytest.fixture
def sandbox(tmp_path, real_config_path):
    """
    Copy the real config into an isolated temp dir and yield the temp path.
    All writer operations in a test target this copy, never the real file.
    A minimal test suite is also dropped in so Gate 2 has something to run
    in the integration tests.
    """
    cfg_copy = tmp_path / "ad_campaign_dataset_config_v3.json"
    shutil.copy(real_config_path, cfg_copy)

    # Minimal stand-in test suite for Gate 2 integration tests. It asserts
    # something true of the baseline config so that a benign change passes
    # and a destructive change can be made to fail.
    # IMPORTANT: build it at exactly the path config_writer will look for —
    # derive it from TEST_SUITE_RELPATH so the fixture can never drift from
    # the module's constant.
    test_dir = tmp_path / cw.TEST_SUITE_RELPATH
    test_dir.mkdir(parents=True, exist_ok=True)
    (test_dir / "test_smoke.py").write_text(
        "import json, os\n"
        "def test_config_has_datasets():\n"
        "    cfg = json.load(open(os.environ['DATASET_CONFIG_FILE_V3']))\n"
        "    assert isinstance(cfg.get('datasets'), list) and cfg['datasets']\n"
        "def test_first_client_has_tables():\n"
        "    cfg = json.load(open(os.environ['DATASET_CONFIG_FILE_V3']))\n"
        "    assert cfg['datasets'][0].get('tables')\n"
    )
    return cfg_copy


def _checksum(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _first_client_and_table(cfg_path: Path):
    cfg = json.loads(Path(cfg_path).read_text())
    ds = cfg["datasets"][0]
    table = ds["tables"][0]
    return ds["client_id"], table["table_id"], table


# ----------------------------------------------------------------------
# Phase 1 — propose_change
# ----------------------------------------------------------------------

class TestProposePhase:

    def test_valid_add_channel_returns_pending(self, sandbox):
        client_id, table_id, _ = _first_client_and_table(sandbox)
        change = {
            "op": "add_channel",
            "client_id": client_id,
            "table_id": table_id,
            "category": "paid",
            "channel": "BrandNewChannelXYZ",
        }
        result = cw.propose_change(change, config_path=str(sandbox), run_tests=False)

        assert result["status"] == "pending"
        assert result["token"]
        assert result["gate_failed"] is None
        assert "schema" in result["gates_passed"]
        assert "BrandNewChannelXYZ" in result["diff_summary"]

    def test_propose_does_not_write_real_file(self, sandbox):
        client_id, table_id, _ = _first_client_and_table(sandbox)
        before = _checksum(sandbox)

        cw.propose_change(
            {
                "op": "add_channel",
                "client_id": client_id,
                "table_id": table_id,
                "category": "paid",
                "channel": "AnotherChannel",
            },
            config_path=str(sandbox),
            run_tests=False,
        )

        # Proposal must touch nothing — the live config is byte-identical.
        assert _checksum(sandbox) == before

    def test_schema_violation_rejected(self, sandbox):
        # add_client with a client_id that already exists -> duplicate -> Gate 1 fail.
        existing_client, _, _ = _first_client_and_table(sandbox)
        change = {
            "op": "add_client",
            "client_id": existing_client,
            "dataset": {
                "client_id": existing_client,
                "name": "Dup",
                "tables": [{
                    "table_id": "performance",
                    "table_full_path": "proj.dataset.table",
                    "channel_column": "Channel",
                    "kpi_column": "Conversions",
                }],
            },
        }
        result = cw.propose_change(change, config_path=str(sandbox), run_tests=False)

        assert result["status"] == "rejected"
        # add_client raises on the duplicate before schema validation —
        # either way it's surfaced as a schema-stage rejection.
        assert result["gate_failed"] == "schema"
        assert result["token"] is None

    def test_rule_reference_to_undefined_rule_rejected(self, sandbox):
        # Hand-craft a change that produces a table.rules entry with no
        # matching _global_rules.rule_definitions key. add_rule normally keeps
        # these in sync, so we go through a raw add_client with a bad rules list.
        change = {
            "op": "add_client",
            "client_id": "ClientWithBadRule",
            "dataset": {
                "client_id": "ClientWithBadRule",
                "name": "Bad Rule Co",
                "tables": [{
                    "table_id": "performance",
                    "table_full_path": "proj.dataset.table",
                    "channel_column": "Channel",
                    "kpi_column": "Conversions",
                    "rules": ["this_rule_is_not_defined_anywhere"],
                }],
            },
        }
        result = cw.propose_change(change, config_path=str(sandbox), run_tests=False)

        assert result["status"] == "rejected"
        assert result["gate_failed"] == "schema"
        assert any("undefined rule_id" in e for e in result["errors"])

    def test_unknown_op_rejected(self, sandbox):
        result = cw.propose_change(
            {"op": "delete_everything"}, config_path=str(sandbox), run_tests=False
        )
        assert result["status"] == "rejected"
        assert result["gate_failed"] == "schema"
        assert any("Unknown op" in e for e in result["errors"])

    def test_add_channel_to_unknown_client_rejected(self, sandbox):
        result = cw.propose_change(
            {
                "op": "add_channel",
                "client_id": "NoSuchClient",
                "table_id": "performance",
                "category": "paid",
                "channel": "X",
            },
            config_path=str(sandbox),
            run_tests=False,
        )
        assert result["status"] == "rejected"
        assert result["gate_failed"] == "schema"

    def test_diff_summary_is_human_readable(self, sandbox):
        client_id, table_id, _ = _first_client_and_table(sandbox)
        result = cw.propose_change(
            {
                "op": "add_channel",
                "client_id": client_id,
                "table_id": table_id,
                "category": "awareness",
                "channel": "Podcast",
            },
            config_path=str(sandbox),
            run_tests=False,
        )
        # The orchestrator shows this verbatim to the user — it must name
        # the client, table, category and value.
        for token in (client_id, table_id, "awareness", "Podcast"):
            assert token in result["diff_summary"]

    def test_add_rule_keeps_definitions_in_sync(self, sandbox):
        client_id, table_id, _ = _first_client_and_table(sandbox)
        change = {
            "op": "add_rule",
            "rule_id": "brand_new_rule_id",
            "description": "A freshly proposed rule.",
            "attach_to": [{"client_id": client_id, "table_id": table_id}],
        }
        # add_rule defines the rule AND attaches it, so Gate 1 (which checks
        # every table.rules entry is defined) must still pass.
        result = cw.propose_change(change, config_path=str(sandbox), run_tests=False)
        assert result["status"] == "pending"


# ----------------------------------------------------------------------
# Phase 2 — confirm_change
# ----------------------------------------------------------------------

class TestConfirmPhase:

    def _make_pending(self, sandbox, run_tests=False):
        client_id, table_id, _ = _first_client_and_table(sandbox)
        result = cw.propose_change(
            {
                "op": "add_channel",
                "client_id": client_id,
                "table_id": table_id,
                "category": "paid",
                "channel": "ConfirmTestChannel",
            },
            config_path=str(sandbox),
            run_tests=run_tests,
        )
        assert result["status"] == "pending"
        return result["token"]

    def test_confirm_commits_and_creates_backup(self, sandbox):
        token = self._make_pending(sandbox)
        result = cw.confirm_change(
            token, confirmed_by="utkarsh", config_path=str(sandbox)
        )

        assert result["status"] == "committed"
        assert result["backup_path"]
        assert Path(result["backup_path"]).exists()

        # The change is actually in the live file now.
        cfg = json.loads(sandbox.read_text())
        all_channels = [
            ch
            for ds in cfg["datasets"]
            for t in ds["tables"]
            for members in t.get("channel_taxonomy", {}).values()
            for ch in members
        ]
        assert "ConfirmTestChannel" in all_channels

    def test_confirm_requires_confirmed_by(self, sandbox):
        token = self._make_pending(sandbox)
        with pytest.raises(ValueError, match="confirmed_by"):
            cw.confirm_change(token, confirmed_by="", config_path=str(sandbox))

    def test_confirm_with_bad_token_rejected(self, sandbox):
        before = _checksum(sandbox)
        result = cw.confirm_change(
            "nonexistent-token", confirmed_by="utkarsh", config_path=str(sandbox)
        )
        assert result["status"] == "rejected"
        assert _checksum(sandbox) == before  # real file untouched

    def test_token_is_single_use(self, sandbox):
        token = self._make_pending(sandbox)
        first = cw.confirm_change(
            token, confirmed_by="utkarsh", config_path=str(sandbox)
        )
        assert first["status"] == "committed"

        # Second confirm with the same token must fail — token is consumed.
        second = cw.confirm_change(
            token, confirmed_by="utkarsh", config_path=str(sandbox)
        )
        assert second["status"] == "rejected"

    def test_confirm_with_expired_token_rejected(self, sandbox, monkeypatch):
        token = self._make_pending(sandbox)
        # Force expiry by shrinking the TTL to a negative window.
        monkeypatch.setattr(cw, "PROPOSAL_TTL", -1)
        result = cw.confirm_change(
            token, confirmed_by="utkarsh", config_path=str(sandbox)
        )
        assert result["status"] == "expired"

    def test_propose_does_not_write_then_confirm_does(self, sandbox):
        before = _checksum(sandbox)
        token = self._make_pending(sandbox)
        # Still untouched after propose.
        assert _checksum(sandbox) == before
        cw.confirm_change(token, confirmed_by="utkarsh", config_path=str(sandbox))
        # Now it has changed.
        assert _checksum(sandbox) != before


# ----------------------------------------------------------------------
# Gate 2 — real subprocess integration tests
# ----------------------------------------------------------------------

class TestGate2Integration:
    """These actually run pytest as a subprocess — slower, but exercise the
    real test-gate path end to end."""

    def test_benign_change_passes_test_gate(self, sandbox):
        client_id, table_id, _ = _first_client_and_table(sandbox)
        result = cw.propose_change(
            {
                "op": "add_channel",
                "client_id": client_id,
                "table_id": table_id,
                "category": "paid",
                "channel": "GateTestChannel",
            },
            config_path=str(sandbox),
            run_tests=True,
        )
        # Adding a channel doesn't break the smoke suite -> Gate 2 passes.
        assert result["status"] == "pending"
        assert "tests" in result["gates_passed"]

    def test_destructive_change_fails_test_gate(self, sandbox):
        # Replace the smoke suite with one that requires a channel we are
        # about to NOT have — then a change that empties datasets fails it.
        test_dir = sandbox.parent / cw.TEST_SUITE_RELPATH
        (test_dir / "test_smoke.py").write_text(
            "import json, os\n"
            "def test_requires_many_datasets():\n"
            "    cfg = json.load(open(os.environ['DATASET_CONFIG_FILE_V3']))\n"
            "    assert len(cfg['datasets']) >= 9999  # deliberately impossible\n"
        )
        client_id, table_id, _ = _first_client_and_table(sandbox)
        result = cw.propose_change(
            {
                "op": "add_channel",
                "client_id": client_id,
                "table_id": table_id,
                "category": "paid",
                "channel": "DoesntMatter",
            },
            config_path=str(sandbox),
            run_tests=True,
        )
        assert result["status"] == "rejected"
        assert result["gate_failed"] == "tests"
        assert result["errors"]

    def test_confirm_revalidates_gate_2(self, sandbox):
        # Propose with tests passing...
        client_id, table_id, _ = _first_client_and_table(sandbox)
        proposal = cw.propose_change(
            {
                "op": "add_channel",
                "client_id": client_id,
                "table_id": table_id,
                "category": "paid",
                "channel": "RevalidateChannel",
            },
            config_path=str(sandbox),
            run_tests=True,
        )
        assert proposal["status"] == "pending"
        token = proposal["token"]

        # ...then the test suite changes underneath us before confirm.
        test_dir = sandbox.parent / cw.TEST_SUITE_RELPATH
        (test_dir / "test_smoke.py").write_text(
            "def test_now_always_fails():\n"
            "    assert False\n"
        )
        result = cw.confirm_change(
            token, confirmed_by="utkarsh", config_path=str(sandbox)
        )
        # confirm re-runs Gate 2 and catches the newly-broken suite.
        assert result["status"] == "rejected"
        assert result["gate_failed"] == "tests"


# ----------------------------------------------------------------------
# Rollback
# ----------------------------------------------------------------------

class TestRollback:

    def test_rollback_restores_previous_config(self, sandbox):
        # Capture the original config as DATA, not bytes. _atomic_commit
        # rewrites the file via json.dump(indent=2), so whitespace/key order
        # may differ from the source file even when the data is identical —
        # compare parsed content, not checksums.
        original_data = json.loads(sandbox.read_text())
        client_id, table_id, _ = _first_client_and_table(sandbox)

        # Commit a change so we have a backup of the original.
        token = cw.propose_change(
            {
                "op": "add_channel",
                "client_id": client_id,
                "table_id": table_id,
                "category": "paid",
                "channel": "WillBeRolledBack",
            },
            config_path=str(sandbox),
            run_tests=False,
        )["token"]
        commit = cw.confirm_change(
            token, confirmed_by="utkarsh", config_path=str(sandbox)
        )
        assert json.loads(sandbox.read_text()) != original_data  # changed
        backup = commit["backup_path"]

        # Roll back to the original.
        result = cw.rollback(
            backup, confirmed_by="utkarsh", config_path=str(sandbox)
        )
        assert result["status"] == "committed"
        # Data must match the original; "WillBeRolledBack" must be gone.
        assert json.loads(sandbox.read_text()) == original_data

    def test_rollback_requires_confirmed_by(self, sandbox):
        with pytest.raises(ValueError, match="confirmed_by"):
            cw.rollback("/tmp/whatever.bak", confirmed_by="",
                        config_path=str(sandbox))

    def test_rollback_missing_backup_rejected(self, sandbox):
        result = cw.rollback(
            str(sandbox) + ".bak.does_not_exist",
            confirmed_by="utkarsh",
            config_path=str(sandbox),
        )
        assert result["status"] == "rejected"

    def test_rollback_rejects_schema_corrupt_backup(self, sandbox, tmp_path):
        # A backup file that is valid JSON but structurally corrupt.
        bad_backup = sandbox.parent / (sandbox.name + ".bak.99999999_999999")
        bad_backup.write_text(json.dumps({"datasets": "not a list"}))
        result = cw.rollback(
            str(bad_backup), confirmed_by="utkarsh", config_path=str(sandbox)
        )
        assert result["status"] == "rejected"
        assert result["gate_failed"] == "schema"


# ----------------------------------------------------------------------
# Listing & audit log
# ----------------------------------------------------------------------

class TestListingAndAudit:

    def test_list_pending_reflects_open_proposals(self, sandbox):
        client_id, table_id, _ = _first_client_and_table(sandbox)
        assert cw.list_pending(config_path=str(sandbox)) == []

        cw.propose_change(
            {
                "op": "add_channel",
                "client_id": client_id,
                "table_id": table_id,
                "category": "paid",
                "channel": "PendingOne",
            },
            config_path=str(sandbox),
            run_tests=False,
        )
        pending = cw.list_pending(config_path=str(sandbox))
        assert len(pending) == 1
        assert pending[0]["status"] == "pending"

    def test_list_backups_newest_first(self, sandbox):
        client_id, table_id, _ = _first_client_and_table(sandbox)
        for i in range(2):
            token = cw.propose_change(
                {
                    "op": "add_channel",
                    "client_id": client_id,
                    "table_id": table_id,
                    "category": "paid",
                    "channel": f"BackupChan{i}",
                },
                config_path=str(sandbox),
                run_tests=False,
            )["token"]
            cw.confirm_change(
                token, confirmed_by="utkarsh", config_path=str(sandbox)
            )
            time.sleep(1.1)  # ensure distinct second-resolution timestamps

        backups = cw.list_backups(config_path=str(sandbox))
        assert len(backups) >= 2
        assert backups == sorted(backups, reverse=True)

    def test_audit_log_records_propose_and_confirm(self, sandbox):
        client_id, table_id, _ = _first_client_and_table(sandbox)
        token = cw.propose_change(
            {
                "op": "add_channel",
                "client_id": client_id,
                "table_id": table_id,
                "category": "paid",
                "channel": "AuditChan",
            },
            config_path=str(sandbox),
            run_tests=False,
        )["token"]
        cw.confirm_change(token, confirmed_by="utkarsh", config_path=str(sandbox))

        log_path = sandbox.parent / "config_changes.log"
        assert log_path.exists()
        entries = [json.loads(line) for line in log_path.read_text().splitlines()]
        phases = [e["phase"] for e in entries]
        assert "propose" in phases
        assert "confirm" in phases

        confirm_entry = next(e for e in entries if e["phase"] == "confirm")
        assert confirm_entry["confirmed_by"] == "utkarsh"
        assert confirm_entry["result"] == "committed"
        assert "timestamp" in confirm_entry

    def test_rejected_proposal_is_audit_logged(self, sandbox):
        cw.propose_change(
            {"op": "bogus_op"}, config_path=str(sandbox), run_tests=False
        )
        log_path = sandbox.parent / "config_changes.log"
        entries = [json.loads(line) for line in log_path.read_text().splitlines()]
        assert any(
            e["phase"] == "propose" and e["result"] == "rejected" for e in entries
        )


# ----------------------------------------------------------------------
# Schema validator — direct unit tests
# ----------------------------------------------------------------------

class TestSchemaValidator:

    def test_valid_config_passes(self, real_config_path):
        cfg = json.loads(Path(real_config_path).read_text())
        assert cw._validate_schema(cfg) == []

    def test_missing_datasets_flagged(self):
        errors = cw._validate_schema({"_global_rules": {"rule_definitions": {}}})
        assert any("datasets" in e for e in errors)

    def test_duplicate_client_id_flagged(self):
        cfg = {
            "_global_rules": {"rule_definitions": {}},
            "datasets": [
                {"client_id": "X", "name": "X", "tables": [
                    {"table_id": "performance", "table_full_path": "a.b.c",
                     "channel_column": "Channel", "kpi_column": "Conversions"}]},
                {"client_id": "X", "name": "X2", "tables": [
                    {"table_id": "performance", "table_full_path": "a.b.c",
                     "channel_column": "Channel", "kpi_column": "Conversions"}]},
            ],
        }
        errors = cw._validate_schema(cfg)
        assert any("duplicate client_id" in e for e in errors)

    def test_bad_table_path_flagged(self):
        cfg = {
            "_global_rules": {"rule_definitions": {}},
            "datasets": [
                {"client_id": "X", "name": "X", "tables": [
                    {"table_id": "performance",
                     "table_full_path": "not-a-valid-path",
                     "channel_column": "Channel", "kpi_column": "Conversions"}]},
            ],
        }
        errors = cw._validate_schema(cfg)
        assert any("project.dataset.table" in e for e in errors)

    def test_empty_taxonomy_member_flagged(self):
        cfg = {
            "_global_rules": {"rule_definitions": {}},
            "datasets": [
                {"client_id": "X", "name": "X", "tables": [
                    {"table_id": "performance", "table_full_path": "a.b.c",
                     "channel_column": "Channel", "kpi_column": "Conversions",
                     "channel_taxonomy": {"paid": ["Valid", ""]}}]},
            ],
        }
        errors = cw._validate_schema(cfg)
        assert any("non-string/empty" in e for e in errors)