# Code Review: astrobot_mesh Data Science Agent

**Reviewer:** Gemini CLI
**Date:** May 12, 2026
**Scope:** `agent.py`, `tools.py`, `prompts.py`, `KnowledgeManager`

---

## 1. Architectural Overview
The `data_science` agent follows a configuration-driven design, utilizing the `ad_campaign_dataset_config_v3.json` as the source of truth for clients, tables, and business rules. It is built on the Google ADK (Agent Development Kit) framework, leveraging callbacks for security, validation, and observability.

## 2. Security & Isolation (AC-5)
- **Walled Garden:** The `_ac5_walled_garden_check` in `agent.py` is robust. It validates that all generated SQL queries reference only the locked client's tables and datasets.
- **SQL Hardening:** Blocks `SELECT *` without `LIMIT` to prevent massive data exfiltration or cost overruns.
- **Client Locking:** Strict logic in `before_agent_callback` ensures a session remains locked to one client (NPI, Venetian, or WinnDixie), preventing cross-pollination.

## 3. Reliability & Stability
- **JSON Sanitization:** The global patch for `NaN` and `Infinity` floats in `agent.py` effectively prevents the Gemini API from crashing on invalid JSON types often returned by BigQuery aggregates (e.g., `CORR`).
- **Dry-Run Validation (AC-3):** Every SQL query is dry-run through BigQuery before execution to check syntax and cost.
- **Retry Mechanisms:** `call_bigquery_agent` includes a retry loop that feeds error messages back to the LLM for self-correction.
- **Argument Guarding:** `_enforce_arg_size` prevents tool-calling crashes by truncating overly large arguments.

## 4. Technical Quality (lib/ & utils/)
- **Channel Resolution:** Centralized in `lib/channel_resolver.py` and backed by the v3 config, ensuring deterministic translation of vague marketing terms.
- **Question Routing:** Uses a keyword-based approach in `lib/question_router.py` to route users to the correct table (Performance vs. Pacing).
- **SQL Builder:** Implements complex patterns like "Duality" (Spend vs. Conversions on separate rows) using a standard `FULL OUTER JOIN` template.

## 5. Strengths
- **Decoupling:** Business rules (SQL anti-patterns) are kept in JSON, not Python code.
- **Brute-Force Tools:** Inclusion of direct BQ helpers for correlation and aggregation in `tools.py` improves speed and reliability.
- **Detailed Prompting:** The `prompts.py` is highly prescriptive about data quality, chart selection, and error recovery.

## 6. Recommendations
- **Dynamic Terminology:** Move hardcoded client aliases (e.g., "Nassau" -> "NPI") from `agent.py` into the `ad_campaign_dataset_config_v3.json`.
- **Proactive Truncation:** Instead of silent truncation in `_enforce_arg_size`, return an error to the LLM suggesting it summarize the results using Python.
- **Schema Validation:** Consider an automated script to verify that the BigQuery table schemas actually match the dimensions/metrics listed in the v3 config.

---

**Final Status:** Production-Ready.
The agent demonstrates a high level of engineering rigor and adheres to the security and reliability standards expected for enterprise-grade analytics.
