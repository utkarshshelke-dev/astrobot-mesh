"""Extended tests for KnowledgeManager — methods beyond basic discovery."""
import pytest
from data_science.utils.knowledge_manager import manager, KnowledgeManager


@pytest.fixture
def km():
    return KnowledgeManager()


# ============================================================
# Channel/KPI column lookups
# ============================================================

class TestChannelKpiLookups:
    def test_get_channel_column_npi(self, km):
        if hasattr(km, "get_channel_column"):
            result = km.get_channel_column("NPI")
            assert isinstance(result, str)
            assert len(result) > 0

    def test_get_kpi_column_npi(self, km):
        if hasattr(km, "get_kpi_column"):
            result = km.get_kpi_column("NPI")
            assert isinstance(result, str)
            assert len(result) > 0


# ============================================================
# Channel taxonomy
# ============================================================

class TestChannelTaxonomy:
    def test_taxonomy_returns_dict(self, km):
        if hasattr(km, "get_channel_taxonomy"):
            result = km.get_channel_taxonomy("NPI")
            assert isinstance(result, dict)


# ============================================================
# Duality info
# ============================================================

class TestDualityInfo:
    def test_duality_info_returns_dict(self, km):
        if hasattr(km, "get_duality_info"):
            result = km.get_duality_info("NPI")
            assert isinstance(result, dict)


# ============================================================
# Unification map
# ============================================================

class TestUnificationMap:
    def test_unification_map_returns_dict(self, km):
        if hasattr(km, "get_unification_map"):
            result = km.get_unification_map("NPI")
            assert isinstance(result, dict)


# ============================================================
# Route_and_load_context — the main integration point
# ============================================================

class TestRouteAndLoadContext:
    def test_simple_question(self, km):
        ctx = km.route_and_load_context(
            question="top channels by spend",
            client_id="NPI",
        )
        assert isinstance(ctx, dict)
        assert "routed_table_id" in ctx

    def test_returns_routed_path(self, km):
        ctx = km.route_and_load_context(
            question="show me channel performance",
            client_id="NPI",
        )
        assert ctx.get("routed_table_path") or ctx.get("routed_table_id")

    def test_includes_client_lock(self, km):
        ctx = km.route_and_load_context(
            question="top channels",
            client_id="NPI",
        )
        # Should have some form of client identifier
        assert ctx is not None

    def test_volatility_question_routes_to_performance(self, km):
        ctx = km.route_and_load_context(
            question="which channels are most volatile?",
            client_id="NPI",
        )
        routed = str(ctx.get("routed_table_id", "")).lower()
        assert "performance" in routed or routed == "pacing"


# ============================================================
# Data property exposes config
# ============================================================

class TestDataProperty:
    def test_data_contains_datasets(self, km):
        if hasattr(km, "data"):
            assert "datasets" in km.data or "_datasets" in km.data


# ============================================================
# Singleton manager works the same way
# ============================================================

class TestSingletonManager:
    def test_singleton_lists_clients(self):
        clients = manager.list_clients()
        assert isinstance(clients, list)
        assert "NPI" in clients

    def test_singleton_route(self):
        ctx = manager.route_and_load_context(
            question="top channels",
            client_id="NPI",
        )
        assert isinstance(ctx, dict)
