"""
TDD tests for sql_builder.

Verifies that generated SQL contains the required patterns and excludes
the patterns that previously caused wrong answers.
"""

import pytest
from lib.sql_builder import (
    build_unified_cte,
    build_blended_cpa_sql,
    build_organic_share_sql,
    build_funnel_spend_sql,
    build_volatility_sql,
)


class TestUnifiedCte:
    """The CASE WHEN unification clause."""

    def test_npi_unification_includes_paid_search_grouping(self):
        sql = build_unified_cte("NPI", "performance")
        assert "Paid Search" in sql
        assert "Search" in sql

    def test_npi_unification_includes_demand_gen_pmax(self):
        sql = build_unified_cte("NPI", "performance")
        assert "Demand Gen + P-Max" in sql
        assert "Demand Gen" in sql
        assert "Performance Max" in sql

    def test_unification_is_case_statement(self):
        sql = build_unified_cte("NPI", "performance")
        assert "CASE" in sql
        assert "WHEN" in sql
        assert "THEN" in sql
        assert "ELSE" in sql
        assert "END" in sql


class TestBlendedCpaSql:
    """Blended CPA query with unified CTE and FULL OUTER JOIN."""

    def test_uses_full_outer_join(self):
        """REGRESSION: agent previously joined wrong direction, losing channels."""
        sql = build_blended_cpa_sql("NPI")
        assert "FULL OUTER JOIN" in sql

    def test_filters_by_client(self):
        """Critical: must always filter by Client."""
        sql = build_blended_cpa_sql("NPI")
        assert "Client = 'NPI'" in sql

    def test_uses_date_range_filter(self):
        sql = build_blended_cpa_sql("NPI", lookback_months=12)
        assert "INTERVAL 12 MONTH" in sql

    def test_handles_duality_with_separate_ctes(self):
        sql = build_blended_cpa_sql("NPI")
        assert "WITH unified AS" in sql
        assert "spend AS" in sql
        assert "conv AS" in sql

    def test_uses_safe_divide(self):
        sql = build_blended_cpa_sql("NPI")
        assert "SAFE_DIVIDE" in sql

    def test_no_duality_path_is_simpler(self):
        """Venetian has no duality - SQL should be simpler."""
        sql = build_blended_cpa_sql("Venetian")
        # Venetian's config has has_duality=false
        assert "FULL OUTER JOIN" not in sql
        assert "Client = 'Venetian'" in sql

    def test_npi_table_path_in_sql(self):
        sql = build_blended_cpa_sql("NPI")
        assert "vw_astrobot_npi_nc360_dashboard" in sql


class TestOrganicShareSql:
    """Organic % share query."""

    def test_includes_organic_channels_in_filter(self):
        sql = build_organic_share_sql("NPI")
        assert "Organic Search" in sql
        assert "Organic Social" in sql
        assert "Direct" in sql

    def test_excludes_paid_channels_from_filter(self):
        """REGRESSION: agent previously included Paid channels in 'organic'."""
        sql = build_organic_share_sql("NPI")
        # Organic CASE shouldn't include Paid Social
        case_block_end = sql.find("THEN Conversions ELSE 0")
        case_block = sql[:case_block_end]
        assert "'Paid Social'" not in case_block
        assert "'Paid Search'" not in case_block

    def test_groups_by_month(self):
        sql = build_organic_share_sql("NPI")
        assert "FORMAT_DATE('%Y-%m'" in sql
        assert "GROUP BY month" in sql

    def test_uses_pct_calculation(self):
        sql = build_organic_share_sql("NPI")
        assert "pct_organic" in sql
        assert "100.0 *" in sql

    def test_filters_by_client(self):
        sql = build_organic_share_sql("NPI")
        assert "Client = 'NPI'" in sql


class TestFunnelSpendSql:
    """Spend by funnel category (awareness/DR/mid-funnel)."""

    def test_awareness_includes_all_awareness_channels(self):
        """REGRESSION: agent only counted 2 of 9 awareness channels."""
        sql = build_funnel_spend_sql("NPI")
        # All these MUST be in the SQL's awareness CASE
        for ch in ["Linear TV", "CTV", "OTT", "Online Audio",
                   "Online Video", "Paid Video", "Video", "OOH", "Print"]:
            assert f"'{ch}'" in sql, f"Missing {ch} from awareness funnel SQL"

    def test_dr_includes_search_email_shopping(self):
        sql = build_funnel_spend_sql("NPI")
        for ch in ["Search", "Paid Search", "Email", "Shopping"]:
            assert f"'{ch}'" in sql, f"Missing {ch} from DR funnel SQL"

    def test_midfunnel_includes_social_demand_gen_pmax(self):
        sql = build_funnel_spend_sql("NPI")
        for ch in ["Paid Social", "Demand Gen", "Performance Max"]:
            assert f"'{ch}'" in sql

    def test_computes_awareness_dr_ratio(self):
        sql = build_funnel_spend_sql("NPI")
        assert "awareness_dr_ratio" in sql

    def test_uses_safe_divide_for_ratio(self):
        sql = build_funnel_spend_sql("NPI")
        assert "SAFE_DIVIDE" in sql

    def test_returns_all_three_categories(self):
        sql = build_funnel_spend_sql("NPI")
        assert "awareness_spend" in sql
        assert "dr_spend" in sql
        assert "midfunnel_spend" in sql
        assert "total_spend" in sql


class TestVolatilitySql:
    """Coefficient-of-variation volatility query."""

    def test_uses_stddev_div_avg_not_raw_stddev(self):
        """REGRESSION: agent first used raw STDDEV instead of CV."""
        sql = build_volatility_sql("NPI")
        assert "STDDEV" in sql
        assert "AVG" in sql
        # Must be doing CV = STDDEV / AVG
        assert "SAFE_DIVIDE(STDDEV" in sql

    def test_orders_by_cv_desc(self):
        sql = build_volatility_sql("NPI")
        assert "ORDER BY cv DESC" in sql

    def test_filters_low_sample_channels(self):
        sql = build_volatility_sql("NPI", min_months=8)
        assert "months >= 8" in sql

    def test_default_metric_is_conversions(self):
        sql = build_volatility_sql("NPI")
        assert "SUM(Conversions)" in sql

    def test_custom_metric_used(self):
        sql = build_volatility_sql("NPI", metric="Cost")
        assert "SUM(Cost)" in sql

    def test_unified_channel_used_in_grouping(self):
        sql = build_volatility_sql("NPI")
        # Should group by unified channel name, not raw Channel column
        assert "CASE" in sql
        assert "GROUP BY month, channel" in sql