# Proposed Integration: KnowledgeManager & Domain Knowledge

This document outlines the surgical changes required to integrate the `KnowledgeManager` (and `knowledge_base.yaml`) into the `astrobot_mesh/data_science` agent. These changes transition the agent from hardcoded rules to a dynamic, configuration-driven architecture.

---

## 1. Agent Logic (`agent.py`)

### Goal: Query Normalization
Use the `KnowledgeManager` to translate vague user terms (e.g., "Linear TV") into deterministic data terms (e.g., "OTT") before the model processes the request.

```python
# Location: astrobot_mesh/data_science/agent.py
from .utils.knowledge_manager import manager as km

# Inside your LlmAgent class
def before_agent_callback(self, context: CallbackContext, message: types.Content):
    """
    Runs before the LLM is called. 
    Intercepts the user message to normalize terms.
    """
    if not message.parts or not message.parts[0].text:
        return

    original_text = message.parts[0].text
    
    # 1. Translate vague terms (e.g. "Streaming" -> "OTT")
    translated_text = km.translate_query(original_text)
    
    # 2. (Optional) Auto-detect Client ID if missing in state
    # This ensures rules are loaded correctly for NPI, Venetian, etc.
    client_id = context.state.get("client_id")
    if not client_id:
        # Simple heuristic to find client in text
        for cid, cfg in km.data.get("clients", {}).items():
            if any(alias in translated_text.lower() for alias in cfg.get("aliases", [])):
                context.state["client_id"] = cid
                client_id = cid
                break

    # 3. Update the message text for the LLM
    message.parts[0].text = translated_text
```

---

## 2. Dynamic Prompts (`prompts.py`)

### Goal: Inject relevant rules only
Instead of a massive static prompt, inject only the rules relevant to the current client and the global channel mappings.

```python
# Location: astrobot_mesh/data_science/prompts.py
from .utils.knowledge_manager import manager as km

def return_instructions_root(client_id: str = None) -> str:
    """
    Returns the system instruction, now including dynamic domain rules.
    """
    # Generate the compact rule snippet from knowledge_base.yaml
    domain_snippet = km.get_prompt_snippet(client_id)

    return f"""
    # ASTROBOT DATA SCIENCE AGENT
    
    ... (Core Agent Logic) ...

    {domain_snippet}

    ## Operational Constraints:
    - Never include triple quotes in function arguments.
    - Max table size is 10 rows.
    """
```

---

## 3. SQL Tooling (`tools.py` or SQL Builder)

### Goal: Eliminate Hardcoded CASE statements
Use the central `unified_groups` definition to build the "Unified Channel" logic used in reports.

```python
# Location: astrobot_mesh/data_science/tools.py
from .utils.knowledge_manager import manager as km

def call_bigquery_agent(query: str, client_id: str = None):
    """
    Wrapper for BQ agent. Can be enhanced to inject 
    unified channel logic automatically.
    """
    # If the user asks for 'channel mix', the system knows to use:
    unified_logic = km.get_unified_channel_logic()
    
    # Example: Replacing a placeholder in a pre-defined template
    # query = query.replace("{unified_channel_logic}", unified_logic)
    
    # ... call the sub-agent ...
```

---

## 4. Verification Plan

1.  **Unit Test KnowledgeManager**: Ensure `translate_query` handles mixed case and multiple terms.
2.  **Verify Prompt Size**: Ensure `get_prompt_snippet` doesn't exceed token limits for small models.
3.  **Regression Test**: Run the 94 deterministic tests (`pytest astrobot_mesh/_tests`) to ensure term normalization doesn't break existing routing or SQL building.

---
**Status**: Ready for implementation. Use `KnowledgeManager` as a singleton to avoid repeated disk reads of `knowledge_base.yaml`.
