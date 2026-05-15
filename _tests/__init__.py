"""
Deterministic library for Astrobot.

All functions here are pure / side-effect free. TDD-tested.
The LLM calls these functions instead of guessing channel filters,
SQL patterns, or which table to query.
"""

from .channel_resolver import (
    load_config_v3,
    reset_config_cache,
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

from .question_router import (
    route_question_to_table,
    get_applicable_rules,
)

from .sql_builder import (
    build_unified_cte,
    build_blended_cpa_sql,
    build_organic_share_sql,
    build_funnel_spend_sql,
    build_volatility_sql,
)

__all__ = [
    # config
    "load_config_v3",
    "reset_config_cache",
    "get_client",
    "get_table",
    "list_clients",
    "list_tables",
    # resolution
    "resolve_channel_reference",
    "get_unification_map",
    "get_duality_info",
    "get_kpi_column",
    "get_channel_column",
    "get_table_path",
    # routing
    "route_question_to_table",
    "get_applicable_rules",
    # SQL
    "build_unified_cte",
    "build_blended_cpa_sql",
    "build_organic_share_sql",
    "build_funnel_spend_sql",
    "build_volatility_sql",
]