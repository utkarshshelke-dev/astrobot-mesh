# Modular Design: Separate Write-Path & Rule Extraction

This design keeps the core `KnowledgeManager` and `channel_resolver.py` strictly **read-only**, ensuring system stability. All write operations, rule extractions, and event handling are moved to new, specialized modules.

---

## 1. New Architecture Components

### **A. Rule Extraction (The Parser)**
**File**: `data_science/utils/rule_extractor.py`
*   **Role**: Converts unstructured input into structured configuration proposals.
*   **Inputs**:
    *   **From Prompt**: A user saying *"From now on, filter NPI data by 'Brand' category for Awareness."*
    *   **From Table**: A JSON payload from a Cloud Function showing a new row with `Channel: 'TikTok'`.
*   **Logic**: Uses a small Gemini call (or regex) to generate a "Proposal Object" matching the `config_writer` schema (`add_rule`, `add_channel`, etc.).

### **B. Configuration Writing (The Committer)**
**File**: `data_science/utils/firestore_manager.py`
*   **Role**: Handles the actual interaction with Firestore.
*   **Actions**:
    *   `propose(proposal_obj)`: Saves a temporary proposal and returns a token.
    *   `commit(token)`: Moves the proposal from "pending" to "active" in the main Firestore config document.
*   **Note**: This file is the only one with `write` permissions to the Firestore configuration.

### **C. Event Ingestion (The Trigger Handler)**
**File**: `data_science/utils/event_handler.py`
*   **Role**: The entry point for the Cloud Function.
*   **Logic**:
    1.  Receives the BQ row payload.
    2.  Queries the **read-only** `KnowledgeManager` to check if the data matches existing taxonomy.
    3.  If a mismatch is found (e.g., new channel), calls the `RuleExtractor` to suggest a fix.
    4.  Sends the suggestion to the Orchestrator for user approval.

---

## 2. Process Flow

| Step | Component | Action |
|---|---|---|
| **1. Detection** | `event_handler.py` | New row 'TikTok' detected in BQ. |
| **2. Analysis** | `rule_extractor.py` | Analyzes the row vs. current config. Suggests: `add_channel: TikTok to category: Paid Social`. |
| **3. Proposal** | `firestore_manager.py` | Saves the suggestion as a **Pending Proposal**; generates a token. |
| **4. Approval** | **Orchestrator** | Pings user: *"New channel TikTok found. Update config? (Token: XYZ)"* |
| **5. Execution** | `firestore_manager.py` | User approves; token is used to commit the change to Firestore. |

---

## 3. Benefits of this Modular Approach

1.  **Read-Only Integrity**: The `KnowledgeManager` never changes, meaning it can be aggressively cached and remains a "Source of Truth" for the current turn.
2.  **Auditability**: Every change to the mesh must pass through the `firestore_manager.py`, creating a clear audit trail of who approved what.
3.  **Separation of Concerns**: The Data Science Agent focuses on *analysis*, while the new utilities focus on *administration*.

---
