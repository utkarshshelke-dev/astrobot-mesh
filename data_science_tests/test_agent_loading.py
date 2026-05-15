"""Tests that agents and tool wiring load correctly."""
import pytest


def test_data_science_imports():
    """Root module loads."""
    import data_science
    assert data_science is not None


def test_data_science_tools_imports():
    from data_science import tools
    assert hasattr(tools, "_sanitize_json") or hasattr(tools, "call_analytics_agent")


def test_bigquery_subagent_loads():
    from data_science.sub_agents.bigquery.agent import bigquery_agent
    assert bigquery_agent is not None


def test_bigquery_subagent_has_all_tools():
    from data_science.sub_agents.bigquery.agent import bigquery_agent
    if hasattr(bigquery_agent, "tools"):
        tools_list = bigquery_agent.tools
        assert len(tools_list) >= 8, \
            f"Expected at least 8 tools, got {len(tools_list)}"


def test_analytics_subagent_loads():
    from data_science.sub_agents.analytics.agent import analytics_agent
    assert analytics_agent is not None


def test_root_agent_loads():
    from data_science.agent import root_agent
    assert root_agent is not None
