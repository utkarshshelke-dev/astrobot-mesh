"""
TDD tests for question_router.

Routes user questions to the correct table based on applicable_questions keywords.
"""

import pytest
from lib.question_router import route_question_to_table, get_applicable_rules


class TestQuestionRouting:
    """Routes user questions to the right table (performance vs pacing)."""

    # --- Performance table questions ---

    def test_cpa_question_routes_to_performance(self):
        r = route_question_to_table("Which channel has the lowest CPA?", "NPI")
        assert r["table_id"] == "performance"

    def test_channel_ranking_routes_to_performance(self):
        r = route_question_to_table("Rank channels by efficiency", "NPI")
        assert r["table_id"] == "performance"

    def test_organic_efficiency_routes_to_performance(self):
        r = route_question_to_table(
            "What's the organic efficiency for last 12 months?", "NPI"
        )
        assert r["table_id"] == "performance"

    def test_tv_halo_routes_to_performance(self):
        r = route_question_to_table(
            "Does TV halo lift Paid Search conversions?", "NPI"
        )
        assert r["table_id"] == "performance"

    def test_volatility_routes_to_performance(self):
        r = route_question_to_table("Which channel is most volatile?", "NPI")
        assert r["table_id"] == "performance"

    def test_forecast_routes_to_performance(self):
        r = route_question_to_table("Forecast next quarter conversions", "NPI")
        assert r["table_id"] == "performance"

    # --- Pacing table questions ---

    def test_pacing_question_routes_to_pacing(self):
        r = route_question_to_table("Are we pacing well this month?", "NPI")
        assert r["table_id"] == "pacing"

    def test_budget_remaining_routes_to_pacing(self):
        r = route_question_to_table("How much budget is remaining?", "NPI")
        assert r["table_id"] == "pacing"

    def test_underpacing_routes_to_pacing(self):
        r = route_question_to_table(
            "Which flights are underpacing?", "NPI"
        )
        assert r["table_id"] == "pacing"

    def test_will_we_hit_budget_routes_to_pacing(self):
        r = route_question_to_table("Will we hit budget for December?", "NPI")
        assert r["table_id"] == "pacing"

    def test_days_remaining_routes_to_pacing(self):
        r = route_question_to_table("How many days remaining on the flight?", "NPI")
        assert r["table_id"] == "pacing"

    def test_burn_rate_routes_to_pacing(self):
        r = route_question_to_table("What's our current burn rate?", "NPI")
        assert r["table_id"] == "pacing"

    def test_geo_budget_routes_to_pacing(self):
        r = route_question_to_table("Show me geo budget breakdown", "NPI")
        assert r["table_id"] == "pacing"

    # --- Fallback ---

    def test_unmatched_question_defaults_to_performance(self):
        r = route_question_to_table("Hello world unrelated question", "NPI")
        assert r["table_id"] == "performance"
        assert r["confidence"] == "default"
        assert r["matched_keywords"] == []

    # --- Result structure ---

    def test_result_includes_required_fields(self):
        r = route_question_to_table("Lowest CPA channel?", "NPI")
        assert "table_id" in r
        assert "table_full_path" in r
        assert "rules" in r
        assert "channel_column" in r
        assert "matched_keywords" in r
        assert "confidence" in r

    def test_confidence_higher_with_more_matches(self):
        r_high = route_question_to_table(
            "Show CPA, ROAS, and channel ranking for NPI", "NPI"
        )
        r_low = route_question_to_table("CPA?", "NPI")
        # Both should route to performance, but high should have more matches
        assert len(r_high["matched_keywords"]) >= len(r_low["matched_keywords"])

    # --- Multi-client routing ---

    def test_winndixie_routes_to_its_only_table(self):
        r = route_question_to_table("Show ViVs by month", "WinnDixie")
        assert r["table_id"] == "performance"

    def test_venetian_routes_to_its_only_table(self):
        r = route_question_to_table("OOH performance?", "Venetian")
        assert r["table_id"] == "performance"


class TestRulesLookup:
    """Tests that applicable rules are retrieved correctly per table."""

    def test_performance_rules_include_unified_cte(self):
        rules = get_applicable_rules("NPI", "performance")
        rule_ids = [r["rule_id"] for r in rules]
        assert "blended_cpa_use_unified_cte" in rule_ids
        assert "volatility_use_cv_not_stddev" in rule_ids

    def test_pacing_rules_include_pacing_specific(self):
        rules = get_applicable_rules("NPI", "pacing")
        rule_ids = [r["rule_id"] for r in rules]
        assert "pacing_use_days_remaining_for_projections" in rule_ids
        assert "ignore_default_channel_unless_explicit" in rule_ids

    def test_pacing_rules_do_not_include_performance_specific(self):
        rules = get_applicable_rules("NPI", "pacing")
        rule_ids = [r["rule_id"] for r in rules]
        assert "blended_cpa_use_unified_cte" not in rule_ids

    def test_rules_include_global_rules(self):
        rules = get_applicable_rules("NPI", "performance")
        rule_ids = [r["rule_id"] for r in rules]
        assert "always_filter_by_client" in rule_ids
        assert "always_use_date_range_filter" in rule_ids

    def test_rules_have_descriptions(self):
        rules = get_applicable_rules("NPI", "performance")
        for r in rules:
            assert r["description"]
            assert r["description"] != "(no description)"

    def test_no_duplicate_rules(self):
        rules = get_applicable_rules("NPI", "performance")
        ids = [r["rule_id"] for r in rules]
        assert len(ids) == len(set(ids))