# Architecture Test Report & System Hardening Roadmap

This document summarizes the results of the complete architecture test suite run on May 14, 2026, and provides a detailed analysis of the Orchestrator's hallucination issues with a roadmap for resolution.

---

## 1. Architecture Test Results

**Test Suite Summary:**
*   **Total Tests**: 49
*   **Passed**: 45
*   **Failed**: 2
*   **Skipped**: 2

### 1.1 Technical Failures & Analysis

#### **Failure A: A2A Handshake Protocol Mismatch**
*   **Test**: `test_handshake_enforces_client_id_from_context`
*   **Error**: `AttributeError: 'A2AHandshakeClient' object has no attribute '_local_fallback'`
*   **Cause**: The test suite is attempting to call a private method `_local_fallback` which does not exist in the current implementation of `shared/a2a/handshake.py`.
*   **Impact**: Low risk, but indicates that the test code and the source code have diverged. The actual A2A logic is functioning, but this specific security regression test is broken.

#### **Failure B: Persona Aggregator Import Error**
*   **Test**: `test_global_persona_definitions_have_no_client_data`
*   **Error**: `ImportError: cannot import name 'GLOBAL_PERSONA_DEFINITIONS' from 'persona_aggregator.agent'`
*   **Cause**: The persona definitions were refactored into individual functions (e.g., `_npi_hnw_prompt()`) to enable dynamic search integration, but the test still expects a static dictionary.
*   **Impact**: Critical validation gap. We are no longer programmatically verifying that global persona definitions are free of client-specific data.

### 1.2 Architectural Health
The remaining 45 tests passed, confirming that:
*   **Ingestion Gate**: Space ID → Client ID mapping is working correctly.
*   **Schema Blindfold**: Agents are correctly restricted to their own BigQuery tables.
*   **Isolation**: Project Manager and Economist agents are successfully partitioning data by Client ID.

---

## 2. Hallucination Analysis (Orchestrator Agent)

We identified that the Orchestrator frequently "hallucinates" numbers or personas in new sessions.

### **Root Causes**
1.  **Premature Client Defaulting**: The `before_agent_callback` defaults to `NPI` if no client is detected in the first message. If a user says "Hi," the agent is immediately locked to NPI and starts applying NPI-specific instructions.
2.  **Instruction Overload (22k Characters)**: The system prompt contains highly detailed persona names (e.g., "HNW Luxury Seeker") and examples for all three clients. In a new session with no "Ground Truth" from a tool, the model uses these instruction examples as factual data.
3.  **Aggressive Routing**: The agent is told to "Call call_data_scientist IMMEDIATELY." This prevents it from engaging in a proper discovery phase where it should ask the user to identify themselves first.

---

## 3. Implementation Roadmap & Estimates

The following tasks are required to move to a production-grade, event-driven mesh and solve the hallucination issues.

| Task | Description | Est. Effort |
| :--- | :--- | :--- |
| **Hallucination Hardening** | Implement "Greeting Mode" in Orchestrator; move persona details from prompt to Firestore dynamic injection. | 2 Days |
| **Firestore Migration** | Move `v3` config to Firestore; refactor `KnowledgeManager` and `config_writer`. | 3-4 Days |
| **Rule Extractor** | Build Gemini-powered extraction logic for unstructured data patches. | 3 Days |
| **Event Handler** | Bridge Cloud Function payloads to the rule extractor; implement deduplication. | 2 Days |
| **Excel Ingestor** | Build GCS/Excel ingestion utility with header fuzzy-matching. | 2 Days |
| **Final Integration** | End-to-end testing of the "Self-Healing" loop. | 1 Day |
| **Total** | | **~13-14 Days** |

---

## 4. Recommended Changes

### **Immediate Fixes (Hallucination)**
1.  **Orchestrator Callback**: Update `before_agent_callback` to flag `is_new_session`. If true and no client is detected, return a `types.Content` that forces a "Welcome" message instead of calling a tool.
2.  **Dynamic Context**: In `orchestrator/agent.py`, update `before_model_callback` to fetch personas from the `KnowledgeManager` ONLY for the locked client. Remove all persona names from the `prompts.py` file.

### **Infrastructure Fixes (Architecture)**
1.  **Fix A2A Handshake Test**: Refactor `tests/test_mesh.py` to test the public `call_agent` method using a mock HTTP server instead of trying to access non-existent private methods.
2.  **Restore Persona Validation**: Create a utility in `persona_aggregator/agent.py` that aggregates all prompt strings into a single object so that the `test_global_persona_definitions_have_no_client_data` can be restored.

---
**Status**: Architecture Audit Complete
**Prepared by**: Gemini CLI Agent
