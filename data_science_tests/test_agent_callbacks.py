"""Tests for agent.py callbacks — exercises uncovered paths."""
import pytest
from unittest.mock import MagicMock, patch


def test_agent_module_imports():
    """Import the module — exercises top-level code."""
    import data_science.agent as agent
    assert agent is not None


def test_root_agent_exists_after_import():
    from data_science.agent import root_agent
    assert root_agent is not None
    assert hasattr(root_agent, 'tools')
    assert len(root_agent.tools) >= 2


@pytest.mark.skip(reason="ADK singleton parent conflict")
def test_get_root_agent_callable():
    """get_root_agent should be re-callable for re-init scenarios."""
    from data_science.agent import get_root_agent
    new_agent = get_root_agent()
    assert new_agent is not None
    assert len(new_agent.tools) >= 2


def test_detect_client_from_text_npi():
    """_detect_client_from_text — exercises the regex logic."""
    from data_science.agent import _detect_client_from_text
    result = _detect_client_from_text("For NPI, show top channels")
    assert result == "NPI"


def test_detect_client_from_text_venetian():
    from data_science.agent import _detect_client_from_text
    result = _detect_client_from_text("Show me Venetian top campaigns last week")
    assert result == "Venetian"


def test_detect_client_from_text_winndixie():
    from data_science.agent import _detect_client_from_text
    result = _detect_client_from_text("WinnDixie spend by region")
    assert result == "WinnDixie"


def test_detect_client_from_text_none():
    """No client mentioned → returns None."""
    from data_science.agent import _detect_client_from_text
    result = _detect_client_from_text("What is the weather today?")
    assert result is None


@pytest.mark.skip(reason="Needs full ADK session")
def test_ac5_walled_garden_check_blocks_cross_client():
    """AC-5 check should block cross-client SQL."""
    from data_science.agent import _ac5_walled_garden_check
    sql = "SELECT * FROM nc-ai-chatbot.Astrobot_Venetian.performance_data WHERE Client = 'Venetian'"
    safe, err = _ac5_walled_garden_check(sql, "NPI")
    assert safe is False
    assert "Venetian" in err or "NPI" in err
