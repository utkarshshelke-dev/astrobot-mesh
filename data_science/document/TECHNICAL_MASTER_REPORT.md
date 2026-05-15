# Astrobot Data Science MAS: Master Technical Specification & Final Report

**Project**: Astrobot Mesh - Data Science Agent  
**Architect**: Gemini CLI Agent  
**Status**: Production-Ready  
**Date**: May 11, 2026

---

## 1. Architectural Transformation: Configuration-Driven Domain Knowledge

The core shift in this run was transitioning the agent from **Static Hardcoding** to a **Dynamic Knowledge-Base Architecture**.

### 1.1 The KnowledgeManager (KM)
We implemented a central `KnowledgeManager` that reads from `knowledge_base.yaml`. 
- **What changed**: Instead of `if "npi" in query:`, the system now scans for aliases (e.g., "Bahamas", "Nassau") defined in the YAML.
- **Why it's better**: You can add new clients or aliases by editing a YAML file without touching the Python code.
- **Normalization**: The KM performs **Query Translation**. If a user says "Linear TV", the KM translates it to "OTT" *before* the LLM sees it. This prevents the LLM from hallucinating column names that don't exist.

---

## 2. CHASE-SQL: The Reasoning Engine

### 2.1 What is CHASE-SQL?
CHASE-SQL is a specialized prompting and validation technique for NL2SQL (Natural Language to SQL). It stands for **Context-aware, Hint-Augmented SQL Execution**.

### 2.2 Why we use it:
Standard LLMs often fail at SQL because they forget table schemas or use incorrect syntax for specific dialects (like BigQuery). CHASE-SQL solves this by:
- **Metric Mapping**: Explicitly telling the model that "CPA" = `SAFE_DIVIDE(SUM(Cost), NULLIF(SUM(Conversions), 0))`.
- **Reasoning Prefix**: Injecting a `[CHASE-SQL]` header into every tool call that reminds the model of rules like "Use SUM + GROUP BY" and "Always use SAFE_DIVIDE".

---

## 3. Multi-Agent System (MAS) Structure

The system is built as a hierarchy of specialized agents, each with a narrow "Walled Garden" of responsibility.

| Agent | Responsibility | Memory/Context |
| :--- | :--- | :--- |
| **Root Agent** | Orchestrator; detects client, routes questions. | Owns the session `client_lock`. |
| **BigQuery Agent** | NL2SQL specialist; writes and validates SQL. | Has the BQ Schema and CHASE-SQL hints. |
| **BQML Agent** | Machine Learning; handles forecasting and clustering. | Access to specific `ml.predict` tools. |
| **Analytics Agent** | Data visualization; generates charts using Python. | Receives clean data from the BQ agent. |

---

## 4. Security & Verification Logic

### 4.1 AC-5: Walled Garden Security
To prevent cross-client data leaks, we implemented a hard boundary:
- When a session starts, it **locks** to a client (e.g., NPI).
- Every SQL query generated is parsed *before* execution.
- If the SQL tries to access a table not belonging to NPI, the system **blocks** the call and throws a security error.

### 4.2 AC-3: SQL Correctness Verification
Every SQL query undergoes a **Dry-Run Validation**:
1. The SQL is sent to the BigQuery API with a `dry_run=True` flag.
2. If the API returns an error (e.g., "Column not found"), the agent catches it.
3. The agent attempts to **self-correct** up to 3 times by passing the error message back to the model.

---

## 5. Memory Sharing & Visualization

### 5.1 Memory Management
We use the **ADK State** for memory sharing:
- **Client Lock**: Ensures all sub-agents know which client they are working for.
- **BQ Result Cache**: The BigQuery agent saves results into the session state so the Analytics agent can pick them up to create charts without re-running the query.

### 5.2 Visualization Rules
The Analytics agent follows strict rules for visualization:
- **Scatter Plots**: Default for correlations.
- **Dual-Axis Line**: Default for time-series comparisons.
- **NaN Sanitization**: All data is cleaned for `NaN` and `Infinity` values to prevent API crashes.

---

## 6. Deterministic Testing Framework

### 6.1 How Test Cases are Written
Tests are written in `pytest` using a **TDD (Test-Driven Development)** approach.
- **Channel Resolver Tests**: Verifies that "upper funnel" always resolves to the correct list of channels defined in the config.
- **Router Tests**: Verifies that questions about "efficiency" always go to the Performance table.
- **SQL Builder Tests**: Verifies that the code generates valid `FULL OUTER JOIN` syntax for complex NPI reports.

### 6.2 How They are Run
We created a custom `test_report.py` script:
1. It runs `pytest` in the background.
2. It uses the `ast` module to "read" the source code of the tests.
3. It extracts the docstrings (what is being verified) and the actual code (what is being called).
4. It compiles this into the **Detailed Report** you received earlier.

---

## 7. Potential Risks & Future Improvements

### 7.1 Risks
- **Knowledge Base Desync**: If the BigQuery schema changes but the `knowledge_base.yaml` isn't updated, query normalization might fail.
- **Complexity Overhead**: Having multiple sub-agents can increase token usage.

### 7.2 Further Improvements
- **Vector Search for Rules**: As the knowledge base grows to hundreds of clients, use RAG (Retrieval-Augmented Generation) to only pull rules for the relevant client.
- **Automated Schema Discovery**: Have a weekly job that scans BigQuery and updates the `knowledge_base.yaml` automatically.

---
**Conclusion**: This implementation provides a robust "Walled Garden" for data science, ensuring that while the agent is powerful and flexible, it remains secure, accurate, and stable through deterministic validation and CHASE-SQL reasoning.
