"""
TDD tests for channel_resolver — the deterministic core.

These tests MUST always pass. Any regression here means the agent will
produce wrong SQL filters.
"""

import pytest
from lib.channel_resolver import (
    load_config_v3,
    get_client,
    get_table,
    list_clients,
    list_tables,
    resolve_channel_reference,
    get_unification_map,
    get_duality_info,
    get_kpi_column,
    get_channel_column,
    get_table_path,
)


# ============================================================
# Config loading
# ============================================================

class TestConfigLoading:
    def test_config_loads(self):
        config = load_config_v3()
        assert "datasets" in config
        assert "_global_rules" in config

    def test_config_has_expected_clients(self):
        clients = list_clients()
        assert "NPI" in clients
        assert "Venetian" in clients
        assert "WinnDixie" in clients

    def test_config_caches(self):
        c1 = load_config_v3()
        c2 = load_config_v3()
        assert c1 is c2

    def test_force_reload_returns_fresh_object(self):
        c1 = load_config_v3()
        c2 = load_config_v3(force_reload=True)
        assert c1 is not c2  # different objects
        assert c1 == c2  # same contents


# ============================================================
# Client / table lookup
# ============================================================

class TestClientLookup:
    def test_get_npi_client(self):
        client = get_client("NPI")
        assert client["client_id"] == "NPI"
        assert "tables" in client

    def test_npi_has_two_tables(self):
        tables = list_tables("NPI")
        assert "performance" in tables
        assert "pacing" in tables

    def test_venetian_has_performance_table(self):
        assert "performance" in list_tables("Venetian")

    def test_winndixie_has_performance_table(self):
        assert "performance" in list_tables("WinnDixie")

    def test_unknown_client_raises(self):
        with pytest.raises(ValueError, match="Unknown client"):
            get_client("DoesNotExist")

    def test_unknown_table_raises(self):
        with pytest.raises(ValueError, match="Unknown table"):
            get_table("NPI", "does_not_exist")


# ============================================================
# Channel reference resolution — CRITICAL deterministic behaviors
# ============================================================

class TestChannelResolution:
    """
    These are the tests that prevent the bugs we saw in production:
    - 'direct' becoming 'DEFAULT'
    - 'awareness' getting only 2 of 9 channels
    - 'organic' picking the wrong filter
    """

    # --- CRITICAL: "direct" must always be 'Direct', never 'DEFAULT' ---

    def test_direct_returns_Direct_not_DEFAULT(self):
        """REGRESSION: agent previously used 'DEFAULT' for direct conversions."""
        result = resolve_channel_reference("NPI", "direct")
        assert result == ["Direct"]
        assert "DEFAULT" not in result

    def test_direct_case_insensitive(self):
        for term in ["direct", "Direct", "DIRECT"]:
            assert resolve_channel_reference("NPI", term) == ["Direct"]

    # --- CRITICAL: "awareness" includes ALL TV/Video/Audio/OOH/Print ---

    def test_awareness_includes_all_tv_channels(self):
        """REGRESSION: agent only counted 2 of 9 awareness channels."""
        result = resolve_channel_reference("NPI", "awareness")
        assert "Linear TV" in result
        assert "CTV" in result
        assert "OTT" in result

    def test_awareness_includes_video_and_audio(self):
        result = resolve_channel_reference("NPI", "awareness")
        assert "Online Audio" in result
        assert "Online Video" in result
        assert "Paid Video" in result
        assert "Video" in result

    def test_awareness_includes_offline(self):
        result = resolve_channel_reference("NPI", "awareness")
        assert "OOH" in result
        assert "Print" in result

    def test_awareness_has_at_least_seven_channels(self):
        result = resolve_channel_reference("NPI", "awareness")
        assert len(result) >= 7

    # --- "organic" semantics ---

    def test_organic_includes_organic_search_social_video(self):
        result = resolve_channel_reference("NPI", "organic")
        assert "Organic Search" in result
        assert "Organic Social" in result
        assert "Organic Video" in result

    def test_organic_includes_direct_and_referral(self):
        result = resolve_channel_reference("NPI", "organic")
        assert "Direct" in result
        assert "Referral" in result
        assert "Email" in result

    def test_organic_excludes_paid_channels(self):
        result = resolve_channel_reference("NPI", "organic")
        assert "Paid Social" not in result
        assert "Paid Search" not in result
        assert "Demand Gen" not in result

    # --- "direct response" / "lower funnel" ---

    def test_direct_response_includes_search_and_email(self):
        result = resolve_channel_reference("NPI", "direct response")
        assert "Paid Search" in result
        assert "Search" in result
        assert "Email" in result

    def test_direct_response_excludes_tv(self):
        result = resolve_channel_reference("NPI", "direct response")
        assert "Linear TV" not in result
        assert "CTV" not in result
        assert "OTT" not in result

    # --- Synonyms map consistently ---

    def test_upper_funnel_equals_awareness(self):
        assert (
            resolve_channel_reference("NPI", "upper funnel")
            == resolve_channel_reference("NPI", "awareness")
        )

    def test_lower_funnel_equals_direct_response(self):
        assert (
            resolve_channel_reference("NPI", "lower funnel")
            == resolve_channel_reference("NPI", "direct response")
        )

    def test_dr_equals_direct_response(self):
        assert (
            resolve_channel_reference("NPI", "dr")
            == resolve_channel_reference("NPI", "direct response")
        )

    def test_television_equals_tv(self):
        assert (
            resolve_channel_reference("NPI", "television")
            == resolve_channel_reference("NPI", "tv")
        )

    # --- Whitespace & casing ---

    def test_handles_extra_whitespace(self):
        result = resolve_channel_reference("NPI", "  awareness  ")
        assert "Linear TV" in result

    def test_handles_mixed_case(self):
        result = resolve_channel_reference("NPI", "AWARENESS")
        assert "Linear TV" in result

    # --- Errors ---

    def test_unknown_term_raises_with_helpful_message(self):
        with pytest.raises(ValueError) as exc:
            resolve_channel_reference("NPI", "gibberish_xyz")
        assert "Unknown channel reference" in str(exc.value)

    def test_unknown_client_raises(self):
        with pytest.raises(ValueError, match="Unknown client"):
            resolve_channel_reference("FakeClient", "organic")

    # --- Multi-client consistency ---

    def test_winndixie_tv_channels(self):
        result = resolve_channel_reference("WinnDixie", "tv")
        assert "OTT" in result
        assert "CTV" in result
        assert "Linear TV" in result

    def test_venetian_awareness_is_ooh(self):
        result = resolve_channel_reference("Venetian", "awareness")
        assert "OOH" in result


# ============================================================
# Per-table config helpers
# ============================================================

class TestTableMetadata:
    def test_npi_performance_kpi_column(self):
        assert get_kpi_column("NPI", "performance") == "Conversions"

    def test_winndixie_kpi_column(self):
        assert get_kpi_column("WinnDixie") == "KPI"

    def test_npi_performance_channel_column(self):
        assert get_channel_column("NPI", "performance") == "Channel"

    def test_npi_pacing_channel_column(self):
        """Pacing table uses GVMM_Channel, NOT Channel."""
        assert get_channel_column("NPI", "pacing") == "GVMM_Channel"

    def test_npi_performance_table_path(self):
        path = get_table_path("NPI", "performance")
        assert "vw_astrobot_npi_nc360_dashboard" in path
        assert "Astrobot_NPI" in path

    def test_npi_has_duality_on_performance(self):
        d = get_duality_info("NPI", "performance")
        assert d["has_duality"] is True
        assert d["spend_rows_filter"] == "Cost > 0"
        assert d["conv_rows_filter"] == "Conversions > 0"

    def test_npi_pacing_has_no_duality(self):
        d = get_duality_info("NPI", "pacing")
        assert d["has_duality"] is False

    def test_npi_unification_map(self):
        m = get_unification_map("NPI", "performance")
        assert "Paid Search" in m
        assert set(m["Paid Search"]) == {"Search", "Paid Search"}
        assert "Demand Gen + P-Max" in m
        assert "Demand Gen" in m["Demand Gen + P-Max"]
        assert "Performance Max" in m["Demand Gen + P-Max"]


# ============================================================
# Pacing table specifics
# ============================================================

class TestPacingTable:
    """The new pacing table has different rules than performance."""

    def test_pacing_table_exists(self):
        table = get_table("NPI", "pacing")
        assert table["table_id"] == "pacing"

    def test_pacing_uses_GVMM_channel(self):
        assert get_channel_column("NPI", "pacing") == "GVMM_Channel"

    def test_pacing_has_flag_definitions(self):
        table = get_table("NPI", "pacing")
        flags = table.get("flag_definitions", {})
        assert "No spend" in flags
        assert "Pacing" in flags
        assert "Underpacing" in flags
        assert "Overpacing" in flags

    def test_pacing_has_ignore_default_rule(self):
        table = get_table("NPI", "pacing")
        assert "ignore_default_channel_unless_explicit" in table["rules"]