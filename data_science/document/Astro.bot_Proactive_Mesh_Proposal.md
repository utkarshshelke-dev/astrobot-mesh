# Technical Proposal: Proactive & Event-Driven Configuration Mesh

## 1. Executive Summary
The current Astro.bot system relies on a static, local JSON configuration (`ad_campaign_dataset_config_v3.json`). While secure, this creates a bottleneck for scaling and requires manual developer intervention for every new client, table, or taxonomy change.

**The Proposed Solution** transforms the mesh into a **dynamic, event-driven architecture**. By migrating configuration to **Firestore** and enabling automated ingestion from **GCS (Excel)** and **BigQuery Events**, we enable the system to "self-heal" and adapt proactively under human oversight.

---

## 2. Architecture: The Modular Write-Path
To maintain the high security standards of the NetConversion platform, we are separating the "Reasoning" (Read) from the "Administration" (Write).

### A. The Read Path (Unchanged & Stable)
*   **KnowledgeManager**: Stays **Read-Only**. It caches the current Firestore configuration for the duration of a session. This ensures that the agent's logic doesn't "shift" mid-conversation.
*   **channel_resolver.py**: Continues to provide deterministic channel lookups based on the "frozen" state in the KnowledgeManager.

### B. The Write Path (New & Gated)
*   **`firestore_manager.py`**: The only module with write permissions. It implements a **Gated Proposal Workflow**. No change is ever committed without a human typing an approval token in Google Chat.
*   **`rule_extractor.py`**: A specialized Gemini-powered utility that translates unstructured requests or data into structured config JSON.

---

## 3. Data Schema (Firestore)
The configuration will be moved from a flat file to a structured Firestore collection.

**Collection: `astrobot_configs`**
*   **Document: `v3_master`** (The Active Configuration)
    *   `datasets`: Array of Client objects.
    *   `global_rules`: Dictionary of universal logic.
*   **Collection: `proposals`** (Pending Changes)
    ```json
    {
      "token": "XY-7721",
      "status": "pending",
      "proposed_by": "event_handler/rule_extractor",
      "change": {
        "op": "add_channel",
        "client_id": "NPI",
        "channel": "TikTok",
        "category": "Paid Social"
      },
      "expires_at": "2026-05-15T12:00:00Z"
    }
    ```

---

## 4. Operational Workflows & Examples

### Scenario 1: Proactive Taxonomy Discovery (Cloud Function)
**The Trigger**: A new row is added to the NPI BigQuery table with `Channel: 'TikTok_Global'`.

1.  **Detection**: Your Cloud Function triggers the `event_handler.py`.
2.  **Validation**: `event_handler` checks the KnowledgeManager: *"Is 'TikTok_Global' in our Paid taxonomy?"* → Result: **No**.
3.  **Extraction**: `rule_extractor.py` analyzes the row and identifies it as a likely Social channel.
4.  **Proposal**: `firestore_manager` saves a proposal and generates a token (`TK-99`).
5.  **User Interaction (Google Chat)**:
    > **Astro.bot**: "I noticed new data appearing for 'TikTok_Global'. This channel is not yet in your taxonomy. Should I add it to **Paid Social** for NPI? Reply 'Approve TK-99' to confirm."
6.  **Commit**: User approves. The Firestore config updates. The KnowledgeManager refreshes.

### Scenario 2: Dynamic Rule Writing (Conversational)
**The Trigger**: A user says: *"Astro, from now on, all 'Awareness' queries for Venetian should exclude 'OOH' data."*

1.  **Detection**: The Data Science Agent recognizes this is a configuration request, not a data query.
2.  **Extraction**: The Agent calls `rule_extractor.py`.
3.  **Result**:
    ```json
    {
      "op": "update_taxonomy",
      "client_id": "Venetian",
      "category": "awareness",
      "remove": "OOH"
    }
    ```
4.  **Approval**: The Orchestrator presents the "Diff" to the user for final confirmation before committing to Firestore.

### Scenario 3: Client Self-Service (GCS + Excel)
**The Trigger**: The client uploads `tables.xlsx` to their GCS bucket to add a new "Pacing" table.

1.  **Ingestion**: `excel_ingestor.py` reads the file.
2.  **Mapping**: It detects the table path, the date column, and the KPI column.
3.  **Workflow**: It creates a "New Table" proposal.
4.  **Benefit**: Clients can manage their own data mappings without touching a single line of Python code.

---

## 5. Implementation Roadmap: Detailed Timeline & Effort

This phase transitions the system from a static prototype to a production-grade, event-driven mesh. The estimated effort is **10-12 business days**.

### **Task 1: Firestore Migration (3-4 Days)**
*   **Objective**: Move the source of truth from a local JSON file to a high-availability Firestore collection.
*   **Sub-tasks**:
    *   **Schema Design**: Model the `datasets`, `tables`, and `rules` into Firestore collections and documents.
    *   **Resolver Refactor**: Update `lib/channel_resolver.py` to use `google-cloud-firestore`. Implement a connection-pooling mechanism and a local memory cache (LRU) to minimize Firestore read costs.
    *   **Writer Refactor**: Update `utils/config_writer.py` to handle atomic document updates, ensuring that concurrent client changes do not cause data corruption.
*   **Deliverable**: A fully cloud-native configuration system that syncs across all Agent instances.

### **Task 2: Rule Extractor — "The Intelligence Layer" (2-3 Days)**
*   **Objective**: Build the logic that "understands" what configuration changes are needed.
*   **Sub-tasks**:
    *   **Gemini Prompt Engineering**: Develop specialized system instructions for the Rule Extractor to identify taxonomy gaps (e.g., "I found a channel called 'Snapchat', it should go in Social").
    *   **Structural Validation**: Ensure the output of the extractor matches the required JSON schema for the Firestore `proposals` collection.
    *   **Testing**: Run simulations against 50+ diverse marketing row samples to ensure extraction accuracy.
*   **Deliverable**: A module that converts raw data observations into actionable "Proposals."

### **Task 3: Real-Time Event Handler (2 Days)**
*   **Objective**: Connect Cloud Functions to the Astro.bot reasoning engine.
*   **Sub-tasks**:
    *   **Endpoint Creation**: Build a secure `/webhook/event` endpoint in the Orchestrator using FastAPI.
    *   **Deduplication Logic**: Implement an "Event Registry" in Firestore to ensure the same BigQuery row isn't analyzed multiple times if a Cloud Function retries.
    *   **Notification Pipeline**: Design the "Proactive Ping" logic that notifies the user in Google Chat when a gap is detected.
*   **Deliverable**: An end-to-end event pipeline from BigQuery → Cloud Function → Astro.bot.

### **Task 4: Excel Self-Service Ingestor (2 Days)**
*   **Objective**: Allow clients to manage their own table mappings via GCS.
*   **Sub-tasks**:
    *   **GCS Integration**: Use `google-cloud-storage` to monitor for new uploads in client-specific buckets.
    *   **Header Mapping**: Implement a fuzzy-matching logic to identify `Spend`, `Date`, and `KPI` columns regardless of their name in the Excel file.
    *   **Automation**: Automatically trigger a "New Table" proposal upon successful Excel parsing.
*   **Deliverable**: A zero-code interface for clients to add or update their campaign data.

---

## 6. Analysis: Orchestrator Hallucination & Mitigation

During the initial review, we identified that the Orchestrator can "hallucinate" (invent numbers or personas) during a **new session**. We have diagnosed the root causes and developed a mitigation strategy.

### **Technical Root Causes**
1.  **Premature Client Defaulting**: The system currently defaults to the "NPI" client if no intent is detected. This causes the agent to load NPI-specific instructions into its short-term memory before the user has even asked a question.
2.  **Context Leakage**: The system prompt is ~22k characters long and contains hardcoded examples for all three clients (NPI, Venetian, WinnDixie). In a fresh session with no data, the model "fills the silence" by using these examples as if they were real, current facts.
3.  **Lack of "Null State" Guardrails**: The agent is instructed to be "helpful and proactive," which sometimes overrides its instruction to only report what the tools return.

### **Mitigation Strategy (The "Grounding" Fix)**
*   **Session Hardening**: We will modify `before_agent_callback` to detect a `NEW_SESSION` flag. In this state, the agent will be **forbidden** from calling any data tools until the user confirms their client (NPI, Venetian, or WinnDixie).
*   **Dynamic Prompt Injection**: We will remove hardcoded persona names and client examples from the master prompt. These will instead be **injected dynamically** from Firestore only *after* a client is locked. This eliminates "Attention Leakage" from other clients.
*   **"Truth-Only" Enforcement**: We will add a hard constraint to the final response formatter: 
    > *"If the Agent Response is empty or contains an error, you MUST respond with: 'I am ready to help, but I don't see any data yet for this client. What would you like to analyze?'"*

---
## 7. Conclusion
By implementing these four remaining tasks and hardening the Orchestrator against hallucinations, Astro.bot will transition from a "Passive Tool" into an **Active Marketing Consultant** that grows alongside the client's data.

---
**Prepared for**: NetConversion Analytics Team
**Status**: Final Technical Roadmap (V1.1)
