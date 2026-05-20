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
_CONFIG_BACKEND_USED = None  # 'file' or 'firestore'


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
    """Load v3 config. Cached unless force_reload=True.

    Backend selected by env var USE_FIRESTORE_CONFIG:
      true  -> read from ds_agent_* Firestore collections
      unset/false -> read from JSON file (existing behavior)

    Both backends return the same dict shape, so all downstream callers
    work unchanged. Cache is keyed by (backend, path).
    """
    global _CONFIG_CACHE, _CONFIG_PATH_USED, _CONFIG_BACKEND_USED

    use_firestore = os.getenv("USE_FIRESTORE_CONFIG", "").lower() == "true"
    backend = "firestore" if use_firestore else "file"

    # Cache hit: same backend, and (for file) same path
    if not force_reload and _CONFIG_CACHE is not None and _CONFIG_BACKEND_USED == backend:
        if backend == "file":
            resolved = _resolve_config_path(path)
            if _CONFIG_PATH_USED == resolved:
                return _CONFIG_CACHE
        else:
            return _CONFIG_CACHE

    if use_firestore:
        _CONFIG_CACHE = _load_from_firestore()
        _CONFIG_PATH_USED = None
    else:
        _CONFIG_CACHE = _load_from_file(path)
    _CONFIG_BACKEND_USED = backend
    return _CONFIG_CACHE


def _load_from_file(path: Optional[str] = None) -> dict:
    """Read v3 config from JSON file. Existing behavior, unchanged."""
    global _CONFIG_PATH_USED
    resolved = _resolve_config_path(path)
    with open(resolved) as f:
        data = json.load(f)
    _CONFIG_PATH_USED = resolved
    return data


def reset_config_cache():
    """Clear cached config. Useful for tests + after config writes."""
    global _CONFIG_CACHE, _CONFIG_PATH_USED, _CONFIG_BACKEND_USED
    _CONFIG_CACHE = None
    _CONFIG_PATH_USED = None
    _CONFIG_BACKEND_USED = None


def _load_from_firestore() -> dict:
    """Read v3 config from Firestore (ds_agent_* collections).

    Layout:
      ds_agent_app_config/dataset_config_v3
         -> _schema_version, _description, _global_rules, _global_table_types, client_ids
      ds_agent_datasets/<client_id>
         -> client_id, channel_unification, _meta (internal, stripped)
      ds_agent_datasets/<client_id>/tables/<table_id>
         -> full per-table dict

    Returns the same shape as _load_from_file().
    """
    # Lazy imports - only when firestore backend is active
    from google.cloud import firestore as _firestore
    from data_science.utils.firestore_constants import (
        DS_AGENT_APP_CONFIG_COLLECTION,
        DS_AGENT_DATASETS_COLLECTION,
        DATASET_CONFIG_DOC_ID,
        TABLES_SUBCOLLECTION,
    )

    project = os.getenv("GOOGLE_CLOUD_PROJECT", "nc-ai-chatbot")
    database = os.getenv("FIRESTORE_DB", "(default)")
    fs = _firestore.Client(project=project, database=database)

    app_doc = (
        fs.collection(DS_AGENT_APP_CONFIG_COLLECTION)
          .document(DATASET_CONFIG_DOC_ID)
          .get()
    )
    if not app_doc.exists:
        raise RuntimeError(
            "Firestore config missing at "
            + DS_AGENT_APP_CONFIG_COLLECTION + "/" + DATASET_CONFIG_DOC_ID
            + ". Run: python deployment/migrate_dataset_config_to_firestore.py"
        )
    app_data = app_doc.to_dict()
    client_ids = app_data.get("client_ids", [])

    datasets = []
    for cid in client_ids:
        client_ref = fs.collection(DS_AGENT_DATASETS_COLLECTION).document(cid)
        client_doc = client_ref.get()
        if not client_doc.exists:
            continue  # index out of sync; skip this client
        client_data = client_doc.to_dict()
        client_data.pop("_meta", None)  # strip internal tracking

        tables = []
        for tdoc in client_ref.collection(TABLES_SUBCOLLECTION).stream():
            tables.append(tdoc.to_dict())
        client_data["tables"] = tables
        datasets.append(client_data)

    return {
        "_schema_version": app_data.get("_schema_version"),
        "_description": app_data.get("_description"),
        "_global_rules": app_data.get("_global_rules", []),
        "_global_table_types": app_data.get("_global_table_types", []),
        "datasets": datasets,
    }


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


def get_client_filter_value(client_id: str, config = None) -> str:
    """Return the value to put in SQL WHERE Client = '...' for this client_id.

    Some clients have BQ data where the Client column value differs from
    their logical client_id. Example: WinnDixie's BQ data uses Client='SEG'.
    This helper reads `client_filter_value` from the client config (Firestore
    field on the client doc) and falls back to client_id when unset.

    This is the ONE place that decides "what value goes in the SQL WHERE
    clause" — so adding a new mismatched client requires only setting one
    field in Firestore, no code changes.

    Args:
      client_id: Logical client identifier (NPI, Venetian, WinnDixie, ...).
      config:    Optional pre-loaded config dict (else load_config_v3 is called).

    Returns:
      The string to use in SQL: e.g. "SEG" for WinnDixie, "NPI" for NPI.
    """
    client = get_client(client_id, config)
    return client.get("client_filter_value", client_id)


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