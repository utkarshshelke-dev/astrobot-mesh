# Strategic Architectural Suggestions: Orchestrator & Data Science Agents

This document outlines high-impact architectural improvements for the Astrobot Multi-Agent Mesh, focusing on reliability, security, and automated scalability.

---

## 1. Orchestrator Agent: The "Gatekeeper" Enhancements

The Orchestrator’s primary goal is to ensure 100% security isolation and 0% hallucination during routing.

### **1.1 Strict Client Discovery Mode**
*   **Problem**: defaulting to a specific client (e.g., NPI) in new sessions causes the agent to "hallucinate" insights based on that client's instructions even before data is fetched.
*   **Suggestion**: Implement a `NEW_SESSION` state in the `before_agent_callback`. 
*   **Action**: Force the agent to present only the "Capabilities Greeting" and block all data tool calls until a client is explicitly identified (e.g., "I'm looking at Venetian data").

### **1.2 Dynamic Context Injection (DCI)**
*   **Problem**: The 22k-character system prompt contains persona definitions and examples for all clients, leading to "Attention Leakage" where the model confuses one client's personas with another's.
*   **Suggestion**: Strip all client-specific personas, table paths, and examples from the static prompt file (`prompts.py`).
*   **Action**: Update the `before_model_callback` to fetch the specific personas and rules for the **locked client only** from Firestore. This reduces the prompt size by 60% and ensures perfect isolation.

### **1.3 Post-Synthesis "Truth-Check"**
*   **Suggestion**: Implement a lightweight validator that runs after the agent generates its final response.
*   **Action**: Compare the numbers/metrics in the final text against the raw `tool_context.state['last_ds_response']`. If the final text contains numbers not present in the tool output, flag it for hallucination or regenerate.

---

## 2. Data Science Agent: The "Brain" Enhancements

The Data Science agent must transition from a reactive tool to a proactive analyst.

### **2.1 Proactive Rule-Writing Engine (The "Self-Healer")**
*   **Problem**: Configuration updates (taxonomy, tables) are manual and reactive.
*   **Suggestion**: Transform execution errors into configuration proposals.
*   **Action**: When the agent encounters a `Table Not Found` or a `Channel Mismatch` error, it should automatically trigger the `rule_extractor.py` to analyze the error and user prompt. It then calls `propose_change` to update the config with a "Self-Healing" rule.

### **2.2 Intelligent Retry Logic (Adaptive SQL)**
*   **Problem**: Current retries simply ask the agent to "simplify the SQL," which is often ignored.
*   **Suggestion**: Implement algorithmic SQL adaptation in the `call_bigquery_agent` wrapper.
*   **Action**: If an "Out of Memory" or "Large Scan" error is detected, the wrapper should **programmatically** inject a `LIMIT 100` or a narrower `Date` filter into the query string before the next retry attempt, rather than relying on the LLM to do it.

### **2.3 BigQuery "Dry-Run" Cost Guardrails**
*   **Suggestion**: Implement mandatory AC-3 (Dry Run) checks for all SQL.
*   **Action**: Use the BigQuery Python SDK's `dry_run` flag. If the estimated bytes processed exceeds a client-specific budget (e.g., 10GB for Venetian), the agent must pause and ask the user: *"This query will scan 15GB. Should I proceed or should I narrow the date range to save costs?"*

---

## 3. Combating Sycophancy & Hallucination (Gemini 2.5 Flash Optimization)

Sycophancy (the tendency to agree with the user) is a major cause of hallucinations. We must force the agent to prioritize "Deterministic Truth" over "User Satisfaction."

### **3.1 The "Hard Anchor" Strategy (Configuration Rules)**
*   **Core Idea**: Adding explicit **Anti-Sycophancy Rules** to the Firestore config for every table.
*   **Action**: Inject the following rules into the agent's system instructions dynamically:
    1.  *"Always verify the user's premise. If a user asks 'Why did spend spike?' but data shows it was flat, you MUST correct the user."*
    2.  *"Zero is a valid result. Do not invent data to explain a null set from BigQuery."*
    3.  *"Never use industry averages unless explicitly asked for benchmarks. Only report values present in the tool response."*
*   **Impact**: Shifting the agent's loyalty from "The User's Mood" to "The Client's Rules."

### **3.2 Chain of Verification (CoV) Prompting**
*   **Suggestion**: Update the Orchestrator and DS response templates to force a two-step internal check.
*   **Logic**: 
    1.  **Draft**: Extract raw numbers from the tool output.
    2.  **Verify**: Compare the draft numbers against the raw tool output.
    3.  **Final**: Output only the verified summary.
*   **Impact**: Reduces "Silence Filling" hallucinations where the model invents data to appear helpful.

---

## 4. Implementation Priority

| Priority | Task | Target Agent | Benefit |
| :--- | :--- | :--- | :--- |
| **P0** | Firestore Config Migration | Both | Enables all other features and fixes concurrent write bugs. |
| **P0** | Strict Discovery Mode | Orchestrator | Eliminates session-start hallucinations. |
| **P0** | Anti-Sycophancy Rules | Config | Forces the agent to be objective and data-driven. |
| **P1** | Dynamic Context Injection | Orchestrator | Improves accuracy and reduces token costs. |
| **P1** | Proactive Rule Writing | Data Science | Reduces developer maintenance effort by 70%. |
| **P2** | Adaptive Retry Logic | Data Science | Increases query success rate for complex data. |

---
**Status**: Architecture Recommendations Documented (V1.2)
**Prepared for**: NetConversion Analytics Lead
