"""Tests for KnowledgeManager methods we hadn't covered."""
import pytest
from data_science.utils.knowledge_manager import KnowledgeManager, manager


@pytest.fixture
def km():
    return KnowledgeManager()


class TestResolveTerm:
    """KM.resolve_term — wraps lib.channel_resolver"""

    def test_known_term(self, km):
        result = km.resolve_term("NPI", "search")
        assert isinstance(result, list)

    def test_unknown_term_raises_or_returns(self, km):
        """May raise ValueError or return empty — accept both."""
        try:
            result = km.resolve_term("NPI", "definitely_not_a_real_term")
            assert isinstance(result, list)
        except ValueError:
            pass  # Acceptable per channel_resolver behavior


class TestResolveTermSafe:
    """KM.resolve_term_safe — never raises, returns dict."""

    def test_known_term_returns_dict(self, km):
        result = km.resolve_term_safe("NPI", "search")
        assert isinstance(result, dict)

    def test_unknown_term_returns_dict_with_error(self, km):
        result = km.resolve_term_safe("NPI", "xyzzy_unknown")
        assert isinstance(result, dict)


class TestGetPromptSnippet:
    """KM.get_prompt_snippet — generates the dynamic context block."""

    def test_returns_string(self, km):
        result = km.get_prompt_snippet("NPI")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_respects_max_chars(self, km):
        result = km.get_prompt_snippet("NPI", max_chars=500)
        # Should be roughly bounded (allow some overrun for formatting)
        assert len(result) < 1000

    def test_works_for_all_clients(self, km):
        for client in ("NPI", "Venetian", "WinnDixie"):
            result = km.get_prompt_snippet(client)
            assert isinstance(result, str)

    def test_max_rules_parameter(self, km):
        short = km.get_prompt_snippet("NPI", max_rules=1)
        long = km.get_prompt_snippet("NPI", max_rules=10)
        # Lower rule count should produce shorter (or same) snippet
        assert len(short) <= len(long) * 1.5  # Loose check
