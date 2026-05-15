# Proposed Solution: Modular Excel/GCS & Firestore Architecture

This document defines the final proposed architecture for migrating the Astrobot configuration to a cloud-native, event-driven system. It prioritizes **Read-Only Stability** for core reasoning and **Modular Administration** for dynamic updates.

---

## 1. Core Mandate: Read-Only Integrity
The existing `KnowledgeManager` and `channel_resolver.py` remain **strictly read-only**. They serve as the "Source of Truth" for the agents during a conversation. Any change to the configuration must occur through the specialized modules below.

---

## 2. Configuration Management (Firestore)

### **A. Storage: Firestore**
*   **Primary Config**: Stored in a Firestore collection (`configs`).
*   **Audit Log**: Every committed change is logged with a timestamp and the ID of the human who approved it.

### **B. Module: data_science/utils/firestore_manager.py (The Committer)**
*   **Role**: The exclusive write-path for configuration.
*   **Workflow**: Implements a gated, two-phase commit:
    1.  `propose_change`: Validates the new rule against the schema and saves it as "Pending".
    2.  `confirm_change`: Requires a human-provided token to move the rule from "Pending" to "Active".

---

## 3. Table & Rule Ingestion (GCS + Cloud Functions)

### **A. Module: data_science/utils/excel_ingestor.py**
*   **Role**: Ingests new table definitions from client-uploaded Excel files in GCS (`gs://{bucket}/{client_id}/tables.xlsx`).
*   **Action**: Maps Excel headers to the Firestore schema and initiates a proposal via the `firestore_manager`.

### **B. Module: data_science/utils/event_handler.py**
*   **Role**: Handles real-time triggers from Cloud Functions when new rows are added to BigQuery.
*   **Logic**:
    1.  Receives the new row data.
    2.  Checks the row against the **Read-Only KnowledgeManager**.
    3.  If a new channel or anomaly is detected, it triggers the **Rule Extractor**.

---

## 4. Dynamic Rule Extraction

### **Module: data_science/utils/rule_extractor.py (The Brain)**
*   **Role**: Distills unstructured information into structured config updates.
*   **Scenarios**:
    *   **Conversational**: Extracting a rule from a user prompt (e.g., *"Treat TikTok as Paid Social"*).
    *   **Data-Driven**: Identifying a missing taxonomy entry from a new BigQuery row.
*   **Output**: A validated JSON payload ready for `firestore_manager.propose_change`.

---

## 5. Summary of Process Flow

1.  **Event**: A new row is added to BQ or a client uploads a new Excel file.
2.  **Detection**: `event_handler.py` or `excel_ingestor.py` identifies a change or a gap.
3.  **Extraction**: `rule_extractor.py` generates a proposed update.
4.  **Proposal**: `firestore_manager.py` saves a "Pending" proposal in Firestore.
5.  **Human Approval**: The **Orchestrator** notifies the user in Google Chat.
6.  **Commit**: Upon approval, the rule becomes active in the **KnowledgeManager** for all future queries.

---
