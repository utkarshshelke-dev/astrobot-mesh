"""Tests for data_science.lib.sql_builder using REAL signatures."""
import pytest
from data_science.lib import sql_builder


def test_module_imports():
    assert sql_builder is not None


class TestUnifiedCte:
    def test_returns_string(self):
        assert isinstance(sql_builder.build_unified_cte(client_id="NPI"), str)

    def test_contains_case_when(self):
        sql = sql_builder.build_unified_cte(client_id="NPI")
        assert "CASE" in sql.upper() or "WHEN" in sql.upper()

    def test_works_for_all_clients(self):
        for client in ("NPI", "Venetian", "WinnDixie"):
            assert isinstance(sql_builder.build_unified_cte(client_id=client), str)


class TestVolatilitySql:
    def test_default_metric_is_conversions(self):
        assert "Conversions" in sql_builder.build_volatility_sql(client_id="NPI")

    def test_uses_cv_pattern(self):
        s = sql_builder.build_volatility_sql(client_id="NPI", metric="Cost").upper()
        assert "STDDEV" in s
        assert "AVG" in s

    def test_orders_desc(self):
        s = sql_builder.build_volatility_sql(client_id="NPI", metric="Cost").upper()
        assert "ORDER BY" in s
        assert "DESC" in s

    def test_min_months_filter(self):
        s = sql_builder.build_volatility_sql(client_id="NPI", min_months=8).upper()
        assert "HAVING" in s or "WHERE" in s

    def test_custom_metric_used(self):
        assert "Clicks" in sql_builder.build_volatility_sql(client_id="NPI", metric="Clicks")

    def test_lookback_in_sql(self):
        assert "DATE" in sql_builder.build_volatility_sql(
            client_id="NPI", lookback_months=6
        ).upper()


class TestBlendedCpaSql:
    def test_returns_string(self):
        assert isinstance(sql_builder.build_blended_cpa_sql(client_id="NPI"), str)

    def test_uses_safe_divide(self):
        assert "SAFE_DIVIDE" in sql_builder.build_blended_cpa_sql(client_id="NPI").upper()


class TestFunnelSpendSql:
    def test_returns_string(self):
        sql = sql_builder.build_funnel_spend_sql(client_id="NPI")
        assert isinstance(sql, str)
        assert len(sql) > 0


class TestOrganicShareSql:
    def test_returns_string(self):
        sql = sql_builder.build_organic_share_sql(client_id="NPI")
        assert isinstance(sql, str)
        assert "organic" in sql.lower()


class TestHelpers:
    def test_get_table(self):
        assert isinstance(sql_builder.get_table(client_id="NPI"), dict)

    def test_get_channel_column(self):
        assert isinstance(sql_builder.get_channel_column(client_id="NPI"), str)

    def test_get_unification_map(self):
        assert isinstance(sql_builder.get_unification_map(client_id="NPI"), dict)

    def test_get_duality_info(self):
        assert isinstance(sql_builder.get_duality_info(client_id="NPI"), dict)


class TestResolveChannelReference:
    """Same accept-raise-or-empty pattern."""

    def test_known_term(self):
        result = sql_builder.resolve_channel_reference("NPI", "search")
        assert isinstance(result, list)

    def test_unknown_term_raises_or_empty(self):
        try:
            result = sql_builder.resolve_channel_reference("NPI", "xyzzy_unknown")
            assert isinstance(result, list)
        except ValueError as e:
            assert "Unknown" in str(e) or "xyzzy_unknown" in str(e)
