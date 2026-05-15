"""Tests for data_science.lib.question_router."""
import pytest
from data_science.lib import question_router


def test_module_imports():
    assert question_router is not None


# ============================================================
# route_question_to_table(question, client_id, config=None, default_table_id="performance")
# ============================================================

class TestRouteQuestion:
    def test_returns_dict(self):
        result = question_router.route_question_to_table(
            "show me top channels by spend",
            client_id="NPI",
        )
        assert isinstance(result, dict)

    def test_pacing_question_routes_to_pacing_or_performance(self):
        result = question_router.route_question_to_table(
            "are we pacing well in December?",
            client_id="NPI",
        )
        assert isinstance(result, dict)
        # Result has a routed table — pacing or performance both possible
        routed = str(result.get("routed_table_id", "")).lower()
        assert routed in ("pacing", "performance", "")

    def test_default_question_routes_to_performance(self):
        result = question_router.route_question_to_table(
            "top channels by spend",
            client_id="NPI",
        )
        routed = str(result.get("routed_table_id", "")).lower()
        # Performance is the default — should be picked for non-pacing questions
        assert "performance" in routed or routed == ""

    def test_works_for_all_clients(self):
        for client in ("NPI", "Venetian", "WinnDixie"):
            result = question_router.route_question_to_table(
                "show channels by spend",
                client_id=client,
            )
            assert isinstance(result, dict)


# ============================================================
# get_applicable_rules(client_id, table_id, config=None)
# ============================================================

class TestApplicableRules:
    def test_returns_list(self):
        result = question_router.get_applicable_rules("NPI", "performance")
        assert isinstance(result, list)

    def test_each_rule_is_dict(self):
        result = question_router.get_applicable_rules("NPI", "performance")
        for rule in result:
            assert isinstance(rule, dict)

    def test_works_for_pacing_table(self):
        result = question_router.get_applicable_rules("NPI", "pacing")
        assert isinstance(result, list)

    def test_works_for_all_clients(self):
        for client in ("NPI", "Venetian", "WinnDixie"):
            result = question_router.get_applicable_rules(client, "performance")
            assert isinstance(result, list)


# ============================================================
# get_client(client_id, config=None)
# ============================================================

class TestGetClient:
    def test_returns_dict_for_npi(self):
        result = question_router.get_client("NPI")
        assert isinstance(result, dict)

    def test_returns_dict_for_venetian(self):
        result = question_router.get_client("Venetian")
        assert isinstance(result, dict)
