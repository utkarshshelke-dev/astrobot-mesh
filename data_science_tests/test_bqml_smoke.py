"""Smoke tests for BQML sub-agent — module loading only."""
import pytest


def test_bqml_agent_imports():
    from data_science.sub_agents.bqml.agent import root_agent as bqml_agent
    assert bqml_agent is not None


def test_bqml_tools_imports():
    from data_science.sub_agents.bqml import tools as bqml_tools
    # Just verify it imports without crashing
    assert bqml_tools is not None


def test_bqml_prompts_imports():
    from data_science.sub_agents.bqml import prompts as bqml_prompts
    # Function name might differ — just verify module loads
    assert bqml_prompts is not None


def test_bqml_agent_has_tools():
    from data_science.sub_agents.bqml.agent import root_agent as bqml_agent
    assert hasattr(bqml_agent, 'tools')
    assert len(bqml_agent.tools) > 0
