# Code Review Report: Data Science Agent and Subagents

## Overview

This report details a comprehensive code review of the `data_science` agent and its associated subagents (`bqml`, `bigquery`, `analytics`, `alloydb`). The overall architecture demonstrates a robust, layered approach to handling complex data science and analytical tasks, leveraging LLMs while enforcing strict control, safety, and deterministic behavior through specialized tools and highly prescriptive prompts.

---

## 1. Main Data Science Agent (`data_science/agent.py`)

**Purpose:** Orchestrates NL2SQL, NL2Py, and BQML tasks. Integrates KnowledgeManager for routing, handles data security (walled-garden), and validates SQL queries (dry-run).

**Key Observations:**

*   **Architecture:** Acts as a central coordinator, delegating specific tasks to subagents and custom tools.
*   **Security & Validation:** Implements crucial pre-execution checks:
    *   **AC-5 Walled Garden:** Prevents cross-client data access and enforces rules like `SELECT *` only with `LIMIT`.
    *   **AC-3 SQL Dry Run:** Validates SQL queries using `google.cloud.bigquery` before execution, with retry logic.
*   **Client Management:** Dynamically detects clients and offers auto-onboarding (local development feature).
*   **Callbacks:** Extensive use of ADK callbacks (`before_agent`, `after_agent`, `before_tool`, `after_tool`, `after_model`) for state management, context injection, and result sanitization (e.g., `_global_nan_fix`).
*   **Subagent Integration:** Clearly defines `bqml_agent` as a sub-agent and other subagent interactions as tools (`call_analytics_agent`, `call_bigquery_agent`).
*   **Configuration:** Uses environment variables for sensitive IDs and `gemini-2.5-flash` as the default model.
*   **Code Quality:** Well-structured with clear responsibilities.

---

## 2. Main Data Science Agent Prompts (`data_science/prompts.py`)

**Purpose:** Defines the overarching system instructions and behavioral guidelines for the main data science agent.

**Key Observations:**

*   **Highly Prescriptive:** This prompt is the "brain" of the agent, dictating an extremely detailed and complex set of rules, workflows, and best practices.
*   **Dynamic Context:** Injects `dynamic_context` from `KnowledgeManager` and `scheduled_jobs_section` to tailor instructions.
*   **Data Quality & Charting:** Strict rules for data filtering, chart spec format, seasonal comparisons, and chart rendering conditions.
*   **Client Lock & Security:** Explicitly explains the client locking mechanism and how to handle cross-client questions. References `state.LOCKED_CLIENT`.
*   **New Table/Client Onboarding:** Provides triggers and instructions for `propose_new_table`.
*   **Table Routing:** Leverages `KnowledgeManager` for table routing, providing specific `state` fields for agent use.
*   **Duality Enforcement:** Detailed instructions on handling duality (Cost and Conversions on separate rows) using `FULL OUTER JOIN` and pre-aggregation.
*   **Saturation & Unification:** Explains that unification maps are handled automatically by tools and how to invoke saturation models.
*   **Strict Rules:** Includes critical directives like "NO Embedded Code," "Try Harder," "Always Show Available Data," and "Use Available Models First."
*   **Auto-Recovery:** Provides specific logic for automatically fixing issues when queries return zero data.
*   **Anti-Sycophancy:** Strong guidelines for correcting user premises and reporting results honestly.
*   **Chain of Verification:** A 3-step process (Draft, Verify, Emit) for ensuring numerical accuracy.
*   **Maintainability:** While extensive, the detailed instructions aim to make the agent's behavior predictable and robust.

---

## 3. Main Data Science Agent Tools (`data_science/tools.py`)

**Purpose:** Provides core utilities, wrappers for subagents, and advanced data visualization capabilities for the main agent.

**Key Observations:**

*   **KnowledgeManager Integration:** Resolves fuzzy channel terms (`resolve_channel_reference_tool`) and integrates with `utils.config_writer` for dynamic configuration updates.
*   **Config-Change Proposal:** `propose_config_change` and `confirm_config_change` enable the agent to propose and apply configuration changes (e.g., adding a channel to taxonomy) with human approval, a powerful extensibility feature.
*   **BigQuery Agent Wrapper (`call_bigquery_agent`):**
    *   Includes a **duplicate call blocking mechanism** to prevent redundant BigQuery queries.
    *   Implements **retry logic** for SQL errors, improving robustness.
*   **Direct BQ Helpers:**
    *   `_compute_correlation_via_bq()`: Executes direct BigQuery correlation queries with a **1-hour caching mechanism**.
    *   `_compute_aggregate_via_bq()`: Runs direct BigQuery aggregate queries.
*   **Chart Rendering (`call_analytics_agent`):**
    *   **Dynamic Routing to Code Interpreter:** Automatically routes requests to the `VertexAiCodeExecutor` if advanced keywords are detected in the `analysis_request` and the interpreter is available, showcasing intelligent tool selection.
    *   **Matplotlib Rendering:** If not using the code interpreter, it parses JSON chart specifications and uses `_render_chart_to_bytes` (a comprehensive `matplotlib` rendering engine) to generate PNG images.
    *   **Artifact Saving:** Saves generated PNG artifacts.
    *   **Extensive Charting:** `_render_chart_to_bytes` supports numerous chart types with helper functions for data normalization and validation.
*   **Code Quality:** Robust error handling, caching, and dynamic routing logic.

---

## 4. BQML Subagent (`data_science/sub_agents/bqml/`)

**Purpose:** Specializes in BigQuery ML tasks (forecasting, clustering, regression, anomaly detection).

### 4.1. `bqml/agent.py`

*   **Specialization:** Dedicated to BQML tasks.
*   **Callbacks:** `bqml_after_model_callback()` prevents duplicate text responses using a hashing mechanism.
*   **Tools:** A specialized set of tools: `bq_execute_sql`, `check_bq_models`, `rag_response`, and SQL generators for specific BQML models (ARIMA, anomaly detection).
*   **Delegation:** Delegates general SQL execution to the `bigquery_agent` (`call_db_agent`) and chart rendering to the `analytics_agent` (`call_analytics_for_visualization`).
*   **Data Cleaning:** Includes `_clean_floats` for sanitizing NaN/Infinity in JSON.

### 4.2. `bqml/prompts.py`

*   **Comprehensive BQML Playbook:** An extremely detailed prompt guiding the agent through various ML workflows.
*   **Forecast Handling:** Specific steps for model selection, execution, and evaluation of ARIMA forecasts, emphasizing reporting *actual numbers* and offering user-approved retraining. Mandates **weekly aggregation** for chart output.
*   **Stop Retraining Loop:** Strict rule (max 2 attempts) to prevent endless ML retraining, defaulting to non-ML (SQL) approaches after failures.
*   **Mandatory Data Diagnostic:** If models fail, the agent is instructed to *automatically* run specific SQL queries to diagnose data issues (e.g., spend/conversion duality, aggregation needs) and report findings proactively to the user.
*   **Model Validation:** Criteria for detecting "broken models" and templates for proposing retraining, with SQL examples.
*   **Model Registry:** Provides a precise list of known BQML models and strict rules against hallucinating model names.
*   **Auto-Train Fallback:** Workflow for when a requested model doesn't exist, including user consultation and SQL templates for new model training.
*   **Concurrency-Safe Training:** Instructions to use `CREATE MODEL IF NOT EXISTS` by default.
*   **Full Pipeline:** Emphasizes that the agent must *always* predict, plot, and explain results, not just train models.
*   **Specific SQL & Plotting Instructions:** Detailed SQL examples for KMEANS, ARIMA, Linear Regression, and Anomaly Detection, along with specific plotting instructions (e.g., mandatory scatter plot after clustering).

### 4.3. `bqml/tools.py`

*   **BQML Utilities:** Direct `google.cloud.bigquery` client for model listing.
*   `check_bq_models()`: Lists models in a dataset, useful for validation.
*   `rag_response()`: Uses `vertexai.rag.retrieval_query` to fetch contextually relevant information, enhancing knowledge retrieval.
*   **SQL Generators:** Functions that generate BQML-specific SQL for training, forecasting, and anomaly detection. These are designed to return SQL for *user approval* before execution.
    *   `get_arima_train_sql()`, `get_arima_forecast_sql()`, `get_anomaly_detect_sql()`, `get_eom_variance_sql()`.
    *   Uses environment variables for configurability and `_CLIENT_TABLE_MAP` for correct data targeting.

---

## 5. BigQuery Subagent (`data_science/sub_agents/bigquery/`)

**Purpose:** Primary interface for NL2SQL translation and execution against BigQuery.

### 5.1. `bigquery/agent.py`

*   **Core Function:** NL2SQL translation and query execution.
*   **NL2SQL Method:** Configurable via `NL2SQL_METHOD` (CHASE or BASELINE).
*   **Security (Write Mode):** **`BigQueryToolConfig(write_mode=WriteMode.BLOCKED)`** is a critical safety feature, ensuring the agent only performs read operations.
*   **Callbacks:** `store_results_in_context()` sanitizes query results and stores them in `tool_context.state`.
*   **Tools:** Combines `chase_db_tools.initial_bq_nl2sql` (or `tools.bigquery_nl2sql`) with a `BigQueryToolset` (for `execute_sql`). Includes numerous specialized SQL generation and analytical tools.
*   **Deterministic Response:** `temperature=0.01` ensures consistent SQL generation.

### 5.2. `bigquery/prompts.py`

*   **Strict Security:** **"PROJECT ID PINNING"** explicitly mandates `nc-ai-chatbot` as the *only* valid `project_id` and `state.routed_table_path` for table references, preventing malicious or erroneous queries.
*   **Deterministic Tool Routing:** Prioritizes pre-built tools over NL2SQL for specific, complex, or sensitive questions (e.g., volatility, saturation, seasonal comparison, chart type selection). It clearly explains *why* these tools are mandatory.
*   **Mandatory Tool Rules:**
    *   `compute_channel_volatility` for volatility questions.
    *   `compute_saturation_curve` for saturation questions (explaining it handles duality/unification).
    *   A **specific SQL template** for "peak vs trough" seasonal comparisons.
    *   `select_chart_type` for ambiguous chart requests.
*   **CHASE-SQL Context:** Provides extensive `state` fields (`LOCKED_CLIENT`, `routed_table_path`, `duality`, `channel_taxonomy`, etc.) to guide the NL2SQL process.
*   **Table Selection:** Rules for `performance` vs. `pacing` tables.
*   **Duality Enforcement:** Reiterates the `FULL OUTER JOIN` CTE pattern for handling duality.
*   **Channel Category Filters:** Uses `state.channel_taxonomy` for channel filtering.
*   **Safe SQL Patterns:** Emphasizes `SAFE_DIVIDE` and `NULLIF` for ratios.
*   **Date Filtering Defaults:** Provides default date ranges for common requests.
*   **Result Size Limits:** Mandates `LIMIT` clauses and warns against `SELECT *`.
*   **Strict "NEVER DO" List:** A final set of prohibitions reinforcing security and accuracy rules.

### 5.3. `bigquery/tools.py`

*   **Schema & Client Discovery:** Dynamic discovery of clients and tables, with caching. `_build_client_table_map()` integrates with `KnowledgeManager`.
*   **NL2SQL (`bigquery_nl2sql`):** Translates NL to SQL by crafting a prompt that includes schema and rules for an LLM.
*   **Config Introspection (`propose_new_table`):** Introspects BigQuery tables and proposes adding them to the config (local-only feature). This tool appears twice in the file, which should be consolidated.
*   **Safety Gate (`check_campaign_status`):** Prevents recommendations on inactive campaigns.
*   **Pre-built SQL Tools:** A rich set of functions generating validated SQL for common analytical patterns:
    *   `get_pacing_sql()`, `get_channel_efficiency_sql()`, `get_correlation_sql()`, `get_cpa_monthly_sql()`, `get_saturation_sql()`, `get_channel_efficiency_rank_sql()`.
*   **Deterministic Analytical Tools:**
    *   `compute_channel_volatility()`: Calculates Coefficient of Variation (CV) with data quality checks.
    *   `get_channel_volatility_summary()`: Provides cross-metric volatility overview.
    *   `compute_saturation_curve()`: Highly sophisticated tool for fitting Hill saturation curves per channel. Handles duality, unification, and includes **robust quality gates** for fit reliability. Implements `_sat_greedy_allocate()` for budget recommendations.
    *   `train_arima_model_bqml()`: Trains `ARIMA_PLUS` models with pre-flight checks and dynamic naming.
    *   `train_saturation_model_bqml()`: **[DEPRECATED]** explicitly warns against its use due to a known architectural flaw ("shared-slope bug") and directs users to `compute_saturation_curve`. This is an excellent example of self-documentation and quality control.
*   **Chart Type Selection (`select_chart_type`):** A deterministic, rule-based tool that recommends the best chart type based on data shape and user intent, with explicit user overrides and a confidence score.

---

## 6. Analytics Subagent (`data_science/sub_agents/analytics/`)

**Purpose:** Specializes in data visualization, operating in two modes: JSON spec generation or code interpretation for advanced charts.

### 6.1. `analytics/agent.py`

*   **Dual Mode:** Supports `json` (default, in-process matplotlib rendering via root agent's tools) and `code_interpreter` (sandboxed `VertexAiCodeExecutor` for advanced plots).
*   **Conditional Code Interpreter:** `_build_analytics_code_executor()` safely initializes `VertexAiCodeExecutor` only if configured via environment variables, with robust fallback to `json` mode.
*   **Instructions:** Uses different instruction sets (`return_instructions_analytics()` vs. `return_instructions_code_interpreter()`) for each mode.
*   **Deterministic Output:** `temperature=0.0` ensures precise chart specifications or code generation.
*   **No Direct Tools:** Its "tools" are either external (root agent's `_render_chart_to_bytes`) or intrinsic capabilities of the code interpreter.

### 6.2. `analytics/prompts.py`

*   **`return_instructions_analytics()` (JSON Mode):**
    *   **Role:** Strictly a "chart specification generator," outputs *only* JSON.
    *   **Supported Chart Types:** Comprehensive list, with explicit instruction to *never* say "could not be generated."
    *   **Strict Selection Rules:** Prioritizes explicit user chart types, then infers from data shape keywords. Includes "Critical Rules" for specific scenarios (e.g., stacked bar for comparisons).
    *   **Precise Output Format:** Detailed JSON schema with examples for various chart types.
    *   **Data Integrity:** Emphasizes extracting *real data values*, *never* placeholders.
    *   **Specific Guidance:** Includes rules for Correlation Heatmap (using BQ `CORR()`), Funnel validation (checking descending values and adding warnings if not), and Pie chart zero handling.
    *   **Final Output:** "OUTPUT THE JSON ONLY. No prose. No code blocks. No backticks. Just raw JSON."
*   **`return_instructions_code_interpreter()` (Code Interpreter Mode):**
    *   **Role:** "Data visualization expert" with sandboxed Python access.
    *   **Mandatory Code Pattern:** Enforces a strict Python boilerplate for every chart, including `matplotlib.use('Agg')`, timestamped file saving, and `CHART_DONE` signal for output capture.
    *   **Advanced Examples:** Provides code snippets for advanced charts (heatmaps, multi-axis, annotations).
    *   **Rules:** Reinforces real data usage, `Agg` backend, and professional styling.

---

## 7. AlloyDB Subagent (`data_science/sub_agents/alloydb/`)

**Purpose:** Provides NL2SQL translation and execution capabilities specifically for AlloyDB databases.

### 7.1. `alloydb/agent.py`

*   **Specialization:** Dedicated NL2SQL agent for AlloyDB.
*   **Output Key:** Uses `output_key="alloydb_agent_output"` for result storage.
*   **Tools:** Explicitly uses `tools.alloydb_nl2sql` (for SQL generation) and `tools.run_alloydb_query` (for execution).
*   **Callbacks:** `setup_before_agent_call` is commented out, suggesting schema loading might be handled differently or is less critical in its current state.
*   **Deterministic Response:** `temperature=0.01` for consistent SQL generation.

### 7.2. `alloydb/prompts.py`

*   **Clear Role & Workflow:** Defines the agent's role and a straightforward 4-step workflow for NL2SQL and execution, including error correction.
*   **Explicit Tool Usage:** Clearly names and describes `alloydb_nl2sql` and `run_alloydb_query`.
*   **Anti-Hallucination:** Strong directive: "ALWAYS USE THE TOOLS... not make up SQL WITHOUT CALLING TOOLS."
*   **Response Format:** Specifies a JSON output with `sql`, `sql_results`, and `nl_results`.

### 7.3. `alloydb/tools.py`

*   **Toolbox Integration:** Heavy reliance on "MCP Toolbox for Databases" (`toolbox_core`) for AlloyDB connectivity and interaction, a key architectural difference from the BigQuery agent.
*   **Environment Variables:** Extensive use of environment variables for configuration.
*   **Toolbox Client Management:** `get_toolbox_client()` and `get_toolbox_toolset()` manage cached connections and tool loading from the Toolbox.
*   **Database Settings & Schema:** `get_database_settings()` and `update_database_settings()` fetch schema dynamically using a `list_tables` tool from the Toolbox.
*   **`alloydb_nl2sql()`:**
    *   Translates NL to PostgreSQL queries.
    *   Uses a detailed prompt template to guide the LLM, including specific SQL guidelines (double quotes for tables, joins, aggregations, aliases) and incorporates the `SCHEMA`.
    *   Uses `llm_client.models.generate_content` for SQL generation.
*   **`run_alloydb_query()`:**
    *   Executes SQL against AlloyDB.
    *   `cleanup_sql()`: Preprocesses SQL string (removes escapes, newlines). The commented-out `LIMIT` addition is a potential area for improvement.
    *   **Security (DML/DDL Restriction):** **Critical regex-based check** to prevent execution of DML/DDL statements, ensuring read-only operations.
    *   Uses an `execute_sql` tool from the Toolbox for actual query execution.

---

## General Observations and Recommendations

1.  **Strong Emphasis on Safety and Control:** Across all agents, there's a clear and consistent pattern of implementing robust safety measures. This includes:
    *   Explicit `WriteMode.BLOCKED` for BigQuery.
    *   Regex-based DML/DDL restriction for AlloyDB.
    *   Project ID pinning for BigQuery.
    *   Mandatory tool routing to prevent LLM hallucinations for critical tasks.
    *   SQL dry runs and pre-flight checks.
    *   Strict output formatting and anti-sycophancy rules.
    *   Conditional and safe initialization of code interpreters.
    *   **Recommendation:** Continue to prioritize and enhance these safety mechanisms. Regularly review the regex patterns for DML/DDL and consider a more robust parsing approach if edge cases emerge.

2.  **Highly Prescriptive Prompts:** The use of extremely detailed and explicit prompts is a key factor in guiding LLM behavior. This is particularly evident in the BigQuery and BQML agents, where complex analytical workflows and data integrity rules are encoded directly into the system instructions.
    *   **Recommendation:** While effective, overly long prompts can sometimes be challenging to maintain and debug. Consider if any portions of prompt logic could be better encapsulated within tools or external configuration, reducing prompt size while maintaining control.

3.  **Deterministic Tooling:** The strategy of using specialized, deterministic tools for complex or sensitive computations (e.g., volatility, saturation, chart type selection) significantly enhances reliability and accuracy compared to relying solely on LLM-generated code or SQL.
    *   **Recommendation:** Continue this pattern. For any new complex analytical feature, prioritize building a dedicated tool.

4.  **Dynamic Configurability and KnowledgeManager Integration:** The integration with `KnowledgeManager` for dynamic client/table mapping, channel unification, and config updates provides a powerful mechanism for extensibility without requiring code changes for every new client or data aspect.
    *   **Recommendation:** Ensure the `KnowledgeManager` and its configuration schema (`ad_campaign_dataset_config_v3.json`) are well-documented and version-controlled.

5.  **Layered Architecture and Delegation:** The system exhibits a clear hierarchy and delegation of tasks from the main agent to specialized subagents. For instance, the BQML agent delegates general SQL execution to the BigQuery agent, and both delegate charting to the Analytics agent.
    *   **Recommendation:** Maintain clear boundaries between agent responsibilities to avoid overlapping logic and simplify debugging.

6.  **Self-Correction and Transparency:** The explicit `[DEPRECATED]` warning in `train_saturation_model_bqml` and the funnel validation logic in the Analytics prompt (reporting non-descending data with warnings) demonstrate a commitment to self-correction and transparency to the user.
    *   **Recommendation:** Foster this culture of clear deprecation and transparent communication about data limitations or model issues.

7.  **Code Duplication:** The `propose_new_table` function appears twice in `data_science/sub_agents/bigquery/tools.py`.
    *   **Recommendation:** Consolidate these duplicate functions into a single definition to improve maintainability.

8.  **Commented-Out Code:** The `before_agent_callback` in `alloydb/agent.py` and the `LIMIT` addition in `run_alloydb_query`'s `cleanup_sql` are commented out.
    *   **Recommendation:** Either remove commented-out code that is no longer relevant or add comments explaining *why* it's commented out and what the long-term plan is (e.g., "disabled until X is implemented"). For the `LIMIT` clause, re-evaluate if adding a default limit is a desirable safety feature for AlloyDB queries.

9.  **Error Handling and Logging:** Robust use of `try-except` blocks and `logging` is evident throughout.
    *   **Recommendation:** Ensure consistent logging levels and message formats for easier debugging and monitoring across all agents.

10. **Test Coverage:** While not explicitly reviewed, the complexity and critical nature of these agents (especially data interaction and ML) suggest that comprehensive test coverage (unit, integration, and end-to-end scenarios) would be paramount.
    *   **Recommendation:** Verify that adequate test suites are in place to cover all agent behaviors, tool functionalities, and prompt interpretations, particularly for the safety and deterministic rules.

This concludes the detailed code review. The overall design exhibits high quality, thoughtfulness in handling LLM capabilities, and a strong focus on data integrity and user safety within a complex domain.
