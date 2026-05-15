# Copyright 2025 NetConversion / Evonence
"""Central configuration for the Astro.bot Multi-Agent Mesh."""

from __future__ import annotations
import os

PROJECT_ID   = os.getenv("GOOGLE_CLOUD_PROJECT",  "nc-ai-chatbot")
LOCATION     = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
GEMINI_MODEL = os.getenv("ORCHESTRATOR_MODEL",    "gemini-2.5-flash")

FIRESTORE_DB               = os.getenv("FIRESTORE_DB", "(default)")
CLIENT_REGISTRY_COLLECTION = "client_registry"
PERSONA_AUTH_COLLECTION    = "persona_authorisation"
AGENT_REGISTRY_COLLECTION  = "agent_registry"

BQ_DATA_PROJECT    = os.getenv("BQ_DATA_PROJECT_ID",    PROJECT_ID)
BQ_COMPUTE_PROJECT = os.getenv("BQ_COMPUTE_PROJECT_ID", PROJECT_ID)
RLHF_DATASET       = os.getenv("RLHF_DATASET", "astrobot_rlhf")
RLHF_TABLE         = "feedback_log"

AGENT_ENDPOINTS: dict = {
    "data_scientist":     os.getenv("DATA_SCIENTIST_ENDPOINT",     "local"),
    "persona_aggregator": os.getenv("PERSONA_AGGREGATOR_ENDPOINT", "local"),
    "economist":          os.getenv("ECONOMIST_ENDPOINT",          "local"),
    "project_manager":    os.getenv("PROJECT_MANAGER_ENDPOINT",    "local"),
    "scheduler":          os.getenv("SCHEDULER_ENDPOINT",          "local"),
}

CLIENT_BQ_MAP: dict = {
    "NPI":       {"dataset": "Astrobot_NPI",       "table": "sample_astrobot_npi_nc360_dashboard",       "kpi_col": "Conversions", "channels": ["Search","Performance Max","Social"]},
    "Venetian":  {"dataset": "Astrobot_Venetian",  "table": "sample_astrobot_venetian_nc360_dashboard",  "kpi_col": "KPI",         "channels": ["OOH"]},
    "WinnDixie": {"dataset": "Astrobot_WinnDixie", "table": "sample_astrobot_wd_nc360_dashboard",        "kpi_col": "KPI",         "channels": ["OTT"]},
}

VERTICAL_ECONOMIC_SOURCES: dict = {
    "healthcare":   ["CPI Medical","AHA hospital spending","Rx market trends"],
    "hospitality":  ["STR hotel occupancy","Travel demand index","Leisure spend"],
    "grocery":      ["CPG market data","Consumer staples index","Grocery CPI"],
    "entertainment":["Box office index","Streaming subscription data","Events spend"],
    "default":      ["US GDP","CPI","Consumer confidence index","Ad spend index"],
}

CLIENT_VERTICALS: dict = {
    "NPI":       "healthcare",
    "Venetian":  "hospitality",
    "WinnDixie": "grocery",
}

SCHEDULER_DATASET  = os.getenv("SCHEDULER_DATASET", "astrobot_scheduler")
SCHEDULER_TABLE    = "scheduled_jobs"
VALID_FREQUENCIES  = ["daily","weekly","monthly","hourly"]
VALID_CHANNELS     = ["email","google_chat","google_sheets"]
