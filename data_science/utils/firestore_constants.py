"""
Firestore collection + doc constants for the data_science agent.

Isolated under 'ds_agent_*' prefix to avoid colliding with other developers'
Firestore work (e.g. agent_registry, persona_authorizations, space_client_registry).
Do NOT add unrelated constants here.
"""

# Top-level collections owned by the data_science agent.
DS_AGENT_APP_CONFIG_COLLECTION = "ds_agent_app_config"
DS_AGENT_DATASETS_COLLECTION = "ds_agent_datasets"

# Document IDs.
DATASET_CONFIG_DOC_ID = "dataset_config_v3"

# Subcollection name (nested under DS_AGENT_DATASETS_COLLECTION/<client_id>).
TABLES_SUBCOLLECTION = "tables"
