# shared/utils/config.py
"""Central configuration for the Astro.bot multi-agent mesh."""

import os

# ── GCP ───────────────────────────────────────────────────────────────────────
PROJECT_ID   = os.getenv("GOOGLE_CLOUD_PROJECT", "nc-ai-chatbot")
LOCATION     = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

# ── Firestore ─────────────────────────────────────────────────────────────────
FIRESTORE_DB              = os.getenv("FIRESTORE_DB", "(default)")
SPACE_REGISTRY_COLLECTION = "space_client_registry"      # Space ID → Client ID
PERSONA_AUTH_COLLECTION   = "persona_authorizations"     # Client → allowed personas
AGENT_REGISTRY_COLLECTION = "agent_registry"             # Agent Card endpoints
SCHEDULER_COLLECTION      = "scheduled_jobs"             # Recurring job configs
MEMORY_COLLECTION         = "agent_memory"               # Cross-session summaries

# ── Agent Engine endpoints (set after deployment) ─────────────────────────────
AGENT_ENDPOINTS = {
    "orchestrator":       os.getenv("ORCHESTRATOR_ENDPOINT",       ""),
    "data_scientist":     os.getenv("DATA_SCIENTIST_ENDPOINT",     ""),
    "persona_aggregator": os.getenv("PERSONA_AGGREGATOR_ENDPOINT", ""),
    "economist":          os.getenv("ECONOMIST_ENDPOINT",          ""),
    "project_manager":    os.getenv("PROJECT_MANAGER_ENDPOINT",    ""),
    "scheduler":          os.getenv("SCHEDULER_ENDPOINT",          ""),
}

# ── BigQuery ──────────────────────────────────────────────────────────────────
BQ_RLHF_DATASET   = os.getenv("BQ_RLHF_DATASET",   "astrobot_rlhf")
BQ_RLHF_TABLE     = os.getenv("BQ_RLHF_TABLE",      "feedback_log")
BQ_MEMORY_DATASET = os.getenv("BQ_MEMORY_DATASET",  "astrobot_memory")

# ── Models ────────────────────────────────────────────────────────────────────
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# ── Client table map ─────────────────────────────────────────────────────────
CLIENT_TABLE_MAP = {
    "NPI": {
        "dataset": "Astrobot_NPI",
        "table":   "sample_astrobot_npi_nc360_dashboard",
        "vertical": ["healthcare", "medical"],
    },
    "Venetian": {
        "dataset": "Astrobot_Venetian",
        "table":   "sample_astrobot_venetian_nc360_dashboard",
        "vertical": ["hospitality", "entertainment"],
    },
    "WinnDixie": {
        "dataset": "Astrobot_WinnDixie",
        "table":   "sample_astrobot_wd_nc360_dashboard",
        "vertical": ["grocery", "retail", "cpg"],
    },
}

# ── Paused campaign statuses (never recommend budget changes) ─────────────────
PAUSED_STATUSES = {"Paused", "Removed", "Ended", "Other"}
