# Full Architecture & Agent Test Report

## 1. Test Execution Summary (May 14, 2026)

| Category | Total | Passed | Failed | Skipped |
| :--- | :--- | :--- | :--- | :--- |
| **All Tests** | 825 | 785 | 18 | 22 |
| **Orchestrator** | ~50 | ~48 | 2 | 0 |
| **Data Science** | ~775 | ~737 | 16 | 22 |

### 1.1 Critical Failures

#### **A. Configuration Writer Integrity (Data Science)**
*   **Failures**: 15 tests in `data_science_tests/test_config_writer.py`.
*   **Issue**: Proposals are being `rejected` instead of remaining `pending`.
*   **Root Cause**: The schema validation is failing because of a placeholder table name `<budget_pacing_table_name>` in the default config. This causes the `Gate 1` check to reject all proposals.
*   **Impact**: Prevents dynamic rule writing and configuration updates.

#### **B. Project ID Mismatch (Orchestrator)**
*   **Failure**: `test_webhook_project_id`.
*   **Issue**: Expected `nc-ai-chatbot`, found `cloudshell-gca`.
*   **Root Cause**: The environment variable `GOOGLE_CLOUD_PROJECT` is being set by the Cloud Shell environment, overriding the project's hardcoded expectations.

#### **C. Permission Denied (Logging)**
*   **Failure**: `test_main_module_loads`.
*   **Issue**: `403 Permission 'logging.logEntries.create' denied`.
*   **Root Cause**: The current IAM role for the service account in this environment does not have permissions to write to Cloud Logging.

---

## 2. LLM Judge Hallucination Analysis

The "LLM as Judge" (implemented in `data_science/eval_results/_llm_judge.py`) is reporting false hallucinations or incorrect verdicts due to several architectural flaws:

### **2.1 Stale Hardcoded Ground Truth (Primary Cause)**
The judge's system prompt contains **hardcoded data** for the NPI client:
*   *Example*: It expects CTV spend to be exactly `$992k`.
*   *Conflict*: If the actual BigQuery data is refreshed or the user query specifies a different time range, the agent returns correct, live data. The judge, however, compares this to its stale hardcoded numbers and issues a "Hallucination" FAIL verdict.

### **2.2 Brittle Response Extraction**
The `extract_agent_response` function attempts to "scrape" the agent's response from a text-based table in the log file using character offsets.
*   *Issue*: If the log table wraps or aligns differently due to terminal width, the judge receives truncated or garbled text.
*   *Result*: The judge perceives the response as "low quality" or "hallucinated" because it's literally reading corrupted data.

### **2.3 No Chain-of-Thought (CoT)**
The prompt forces the LLM to output **only JSON**.
*   *Issue*: This prevents the model from reasoning through the data before assigning a score. Complex marketing comparisons often require a few steps of logic that are skipped in "JSON-only" mode, leading to erratic scoring.

---

## 3. Suggested Architectural Changes

### **3.1 Immediate Configuration Fixes**
*   **Fix Table Placeholders**: Replace `<budget_pacing_table_name>` in `ad_campaign_dataset_config_v3.json` with a valid table path or a generic but schema-compliant string.
*   **Environment Agnostic Project ID**: Update `orchestrator/webhook.py` to accept the environment's `GOOGLE_CLOUD_PROJECT` dynamically instead of asserting a specific hardcoded ID.

### **3.2 LLM Judge Refactoring**
*   **Dynamic Ground Truth**: Instead of hardcoding numbers in the judge's prompt, the evaluation suite should first query BigQuery to get the "Actual Truth" and then pass that data to the judge.
*   **Structure Log Parsing**: Modify the evaluation runner to output results in a structured format (JSON per line) instead of a pretty-printed table. This will ensure the judge reads 100% accurate agent responses.
*   **CoT Prompting**: Update the judge prompt to allow for a `"thought"` or `"reasoning"` field *before* the JSON verdict, improving judgment quality.

### **3.3 Implementation of Modular Write-Path**
*   **Proceed with Firestore Migration**: Move the configuration to Firestore (as outlined in the `migration_plan_firestore_gcs.md`) to resolve the concurrent write issues and allow for better schema validation in a cloud-native environment.

---
**Status**: Full Audit Complete
**Prepared by**: Gemini CLI Agent
