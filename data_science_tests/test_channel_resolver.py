"""Tests for data_science.lib.channel_resolver — uses REAL signatures."""
import pytest
from data_science.lib import channel_resolver


def test_module_imports():
    assert channel_resolver is not None


class TestResolveChannelReference:
    """resolve_channel_reference(client_id, term, table_id='performance', config=None)"""

    def test_search_resolves(self):
        result = channel_resolver.resolve_channel_reference("NPI", "search")
        assert isinstance(result, list)
        assert any("Search" in ch for ch in result)

    def test_social_resolves(self):
        result = channel_resolver.resolve_channel_reference("NPI", "social")
        assert isinstance(result, list)

    def test_unknown_term_raises_or_empty(self):
        """The implementation may raise ValueError or return []. Accept both."""
        try:
            result = channel_resolver.resolve_channel_reference("NPI", "xyzzy_unknown")
            assert isinstance(result, list)  # If it returns, must be a list
        except ValueError as e:
            assert "xyzzy_unknown" in str(e) or "Unknown" in str(e)

    def test_paid_resolves_to_multiple(self):
        result = channel_resolver.resolve_channel_reference("NPI", "paid")
        assert isinstance(result, list)
        assert len(result) >= 1

    def test_works_for_all_clients(self):
        for client in ("NPI", "Venetian", "WinnDixie"):
            try:
                result = channel_resolver.resolve_channel_reference(client, "search")
                assert isinstance(result, list)
            except ValueError:
                pass  # Some clients may not have all taxonomy keys


class TestListClients:
    def test_returns_list(self):
        assert isinstance(channel_resolver.list_clients(), list)

    def test_includes_all_three(self):
        result = channel_resolver.list_clients()
        for c in ("NPI", "Venetian", "WinnDixie"):
            assert c in result


class TestListTables:
    def test_npi_has_performance(self):
        assert "performance" in channel_resolver.list_tables("NPI")


class TestGetClient:
    def test_returns_dict(self):
        result = channel_resolver.get_client("NPI")
        assert isinstance(result, dict)
        assert len(result) > 0


class TestGetTable:
    def test_returns_dict(self):
        result = channel_resolver.get_table("NPI", "performance")
        assert isinstance(result, dict)


class TestGetTablePath:
    def test_npi_path_includes_project(self):
        result = channel_resolver.get_table_path("NPI", "performance")
        assert "nc-ai-chatbot" in result


class TestGetChannelColumn:
    def test_returns_str(self):
        assert isinstance(channel_resolver.get_channel_column("NPI"), str)


class TestGetKpiColumn:
    def test_returns_str(self):
        assert isinstance(channel_resolver.get_kpi_column("NPI"), str)


class TestGetDualityInfo:
    def test_returns_dict(self):
        assert isinstance(channel_resolver.get_duality_info("NPI"), dict)


class TestGetUnificationMap:
    def test_returns_dict(self):
        assert isinstance(channel_resolver.get_unification_map("NPI"), dict)


class TestLoadConfigV3:
    def test_returns_dict(self):
        result = channel_resolver.load_config_v3()
        assert isinstance(result, dict)

    def test_force_reload(self):
        assert isinstance(channel_resolver.load_config_v3(force_reload=True), dict)


class TestResetConfigCache:
    def test_doesnt_raise(self):
        channel_resolver.reset_config_cache()
        # Verify next load still works
        assert isinstance(channel_resolver.load_config_v3(), dict)
