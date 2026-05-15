"""Smoke tests for chase_sql modules — module loading only."""
import pytest


def test_chase_constants_imports():
    from data_science.sub_agents.bigquery.chase_sql import chase_constants
    assert chase_constants is not None


def test_chase_db_tools_imports():
    from data_science.sub_agents.bigquery.chase_sql import chase_db_tools
    assert chase_db_tools is not None


def test_llm_utils_imports():
    from data_science.sub_agents.bigquery.chase_sql import llm_utils
    assert llm_utils is not None


def test_sql_translator_imports():
    from data_science.sub_agents.bigquery.chase_sql.sql_postprocessor import sql_translator
    assert sql_translator is not None
