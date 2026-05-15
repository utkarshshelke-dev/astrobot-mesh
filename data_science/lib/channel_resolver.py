"""
Deterministic channel reference resolver.

Resolves user terminology ("awareness", "direct", "organic") to exact
channel filter lists based on per-client, per-table config.

This is the deterministic layer that replaces LLM guesswork on channel
filters. All functions here are pure (same input → same output).
"""

import json
import os
from pathlib import Path
from typing import Optional


# -------- Config loading --------

_CONFIG_CACHE = None
_CONFIG_PATH_USED = None


def _resolve_config_path(path: Optional[str] = None) -> str:
    """Resolve config path with sensible defaults."""
    if path:
        return str(Path(path).expanduser())

    env_path = os.getenv("DATASET_CONFIG_FILE_V3")
    if env_path:
        return str(Path(env_path).expanduser())

    # Try common locations
    candidates = [
        "/app/ad_campaign_dataset_config_v3.json",
        "~/astrobot_mesh/ad_campaign_dataset_config_v3.json",
        "./ad_campaign_dataset_config_v3.json",
    ]
    for c in candidates:
        p = Path(c).expanduser()
        if p.exists():
            return str(p)

    raise FileNotFoundError(
        f"Could not find config v3. Tried: {candidates}. "
        "Set DATASET_CONFIG_FILE_V3 env var or pass path explicitly."
    )


def load_config_v3(path: Optional[str] = None, force_reload: bool = False) -> dict:
    """Load v3 config. Cached unless force_reload=True."""
    global _CONFIG_CACHE, _CONFIG_PATH_USED
    resolved = _resolve_config_path(path)

    if not force_reload and _CONFIG_CACHE is not None and _CONFIG_PATH_USED == resolved:
        return _CONFIG_CACHE

    with open(resolved) as f:
        _CONFIG_CACHE = json.load(f)
    _CONFIG_PATH_USED = resolved
    return _CONFIG_CACHE


def reset_config_cache():
    """Clear cached config. Useful for tests."""
    global _CONFIG_CACHE, _CONFIG_PATH_USED
    _CONFIG_CACHE = None
    _CONFIG_PATH_USED = None


# -------- Client and table lookup --------

def get_client(client_id: str, config: Optional[dict] = None) -> dict:
    """Return client config dict. Raises ValueError if client unknown."""
    config = config or load_config_v3()
    client = next(
        (d for d in config["datasets"] if d["client_id"] == client_id),
        None,
    )
    if not client:
        known = [d["client_id"] for d in config["datasets"]]
        raise ValueError(f"Unknown client: {client_id!r}. Known: {known}")
    return client


def get_table(client_id: str, table_id: str = "performance", config: Optional[dict] = None) -> dict:
    """Return table config for a given client+table_id."""
    client = get_client(client_id, config)
    table = next(
        (t for t in client["tables"] if t["table_id"] == table_id),
        None,
    )
    if not table:
        known = [t["table_id"] for t in client["tables"]]
        raise ValueError(
            f"Unknown table: {table_id!r} for client {client_id!r}. Known tables: {known}"
        )
    return table


def list_clients(config: Optional[dict] = None) -> list[str]:
    """Return list of all client_ids in config."""
    config = config or load_config_v3()
    return [d["client_id"] for d in config["datasets"]]


def list_tables(client_id: str, config: Optional[dict] = None) -> list[str]:
    """Return list of table_ids for a client."""
    client = get_client(client_id, config)
    return [t["table_id"] for t in client["tables"]]


# -------- Channel taxonomy resolution --------

# Synonyms that map to taxonomy keys
_SYNONYMS = {
    # awareness/upper funnel
    "awareness": "awareness",
    "upper funnel": "awareness",
    "upper-funnel": "awareness",
    "brand": "awareness",

    # direct response
    "direct response": "direct_response",
    "direct-response": "direct_response",
    "dr": "direct_response",
    "lower funnel": "direct_response",
    "lower-funnel": "direct_response",

    # mid-funnel
    "mid funnel": "mid_funnel",
    "mid-funnel": "mid_funnel",
    "consideration": "mid_funnel",

    # organic
    "organic": "organic",
    "non-paid": "organic",
    "non paid": "organic",

    # paid
    "paid": "paid",
    "paid media": "paid",

    # tv
    "tv": "tv",
    "television": "tv",
    "video tv": "tv",

    # social
    "social": "social",

    # search
    "search": "search",
}


def resolve_channel_reference(
    client_id: str,
    term: str,
    table_id: str = "performance",
    config: Optional[dict] = None,
) -> list[str]:
    """
    Resolve a user term like "awareness" or "direct" to the actual list
    of Channel filter values from the config.

    Special cases:
    - "direct" (singular) -> ["Direct"] (the actual Channel value), NOT 'DEFAULT'

    Raises:
        ValueError: if term cannot be resolved for the given client/table
    """
    table = get_table(client_id, table_id, config)
    taxonomy = table.get("channel_taxonomy", {})
    term_norm = term.strip().lower()

    # Special-case: literal "Direct" channel reference
    if term_norm == "direct":
        # On performance table, Direct is a channel value
        return ["Direct"]

    # Synonym lookup
    if term_norm in _SYNONYMS:
        key = _SYNONYMS[term_norm]
        result = taxonomy.get(key, [])
        if not result:
            raise ValueError(
                f"Term {term!r} resolves to taxonomy key {key!r}, "
                f"but it is empty for client {client_id!r}, table {table_id!r}"
            )
        return list(result)

    # Direct match against taxonomy keys
    if term_norm in taxonomy:
        result = taxonomy[term_norm]
        if isinstance(result, list):
            return list(result)

    # Maybe the user typed a literal channel value
    all_channels = set()
    for v in taxonomy.values():
        if isinstance(v, list):
            all_channels.update(v)
    if term in all_channels:
        return [term]

    raise ValueError(
        f"Unknown channel reference: {term!r} for client {client_id!r}, "
        f"table {table_id!r}. Known taxonomy keys: {list(taxonomy.keys())}"
    )


def get_unification_map(client_id: str, table_id: str = "performance", config: Optional[dict] = None) -> dict:
    """Return the channel unification map for SQL CASE WHEN clauses."""
    table = get_table(client_id, table_id, config)
    return dict(table.get("channel_unification", {}))


def get_duality_info(client_id: str, table_id: str = "performance", config: Optional[dict] = None) -> dict:
    """Return duality config (has_duality, spend_rows_filter, conv_rows_filter)."""
    table = get_table(client_id, table_id, config)
    return dict(table.get("duality", {"has_duality": False}))


def get_kpi_column(client_id: str, table_id: str = "performance", config: Optional[dict] = None) -> str:
    """Return the KPI column name for this client+table."""
    return get_table(client_id, table_id, config).get("kpi_column", "Conversions")


def get_channel_column(client_id: str, table_id: str = "performance", config: Optional[dict] = None) -> str:
    """Return the channel column name (e.g. 'Channel' or 'GVMM_Channel')."""
    return get_table(client_id, table_id, config).get("channel_column", "Channel")


def get_table_path(client_id: str, table_id: str = "performance", config: Optional[dict] = None) -> str:
    """Return fully-qualified table path."""
    return get_table(client_id, table_id, config)["table_full_path"]