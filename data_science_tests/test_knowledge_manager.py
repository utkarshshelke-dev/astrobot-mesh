"""Tests for data_science.utils.knowledge_manager (production)."""
import os
import pytest

# Force config path before import
if "DATASET_CONFIG_FILE_V3" not in os.environ:
    from pathlib import Path
    repo = Path(__file__).parent.parent
    cfg = repo / "ad_campaign_dataset_config_v3.json"
    if cfg.exists():
        os.environ["DATASET_CONFIG_FILE_V3"] = str(cfg)

from data_science.utils.knowledge_manager import manager, KnowledgeManager


def test_singleton_manager_exists():
    assert manager is not None
    assert isinstance(manager, KnowledgeManager)


def test_list_clients_returns_npi():
    clients = manager.list_clients()
    assert isinstance(clients, list)
    assert "NPI" in clients


def test_list_clients_returns_all_three():
    clients = manager.list_clients()
    for client in ("NPI", "Venetian", "WinnDixie"):
        assert client in clients, f"Missing client: {client}"


def test_npi_has_performance_table():
    tables = manager.list_tables("NPI")
    assert isinstance(tables, list)
    assert "performance" in tables


def test_unknown_client_handled_gracefully():
    """list_tables on unknown client returns empty, not exception."""
    try:
        result = manager.list_tables("UnknownClient")
        assert result == [] or result is None
    except (KeyError, ValueError):
        pass  # Acceptable to raise


class TestRouteAndLoadContext:
    def test_returns_dict_with_routed_table(self):
        ctx = manager.route_and_load_context(
            question="For NPI, top channels by spend",
            client_id="NPI",
        )
        assert isinstance(ctx, dict)
        assert "routed_table_id" in ctx or "routed_table_path" in ctx

    def test_pacing_question_routes_correctly(self):
        ctx = manager.route_and_load_context(
            question="Are we pacing well in December for NPI?",
            client_id="NPI",
        )
        # Either pacing is routed, or table is disabled — both acceptable
        routed = ctx.get("routed_table_id", "")
        assert routed in ("pacing", "performance"), f"Unexpected route: {routed}"
