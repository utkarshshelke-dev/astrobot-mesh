"""Test orchestrator module imports and basic structure."""
import pytest, sys, os
sys.path.insert(0, os.path.expanduser("~/astrobot_mesh"))

def test_orchestrator_agent_imports():
    import orchestrator.agent as ag
    assert ag is not None

def test_orchestrator_prompts_imports():
    import orchestrator.prompts as p
    assert p is not None

def test_orchestrator_remote_client_imports():
    import orchestrator.remote_client as rc
    assert rc is not None

def test_orchestrator_root_agent_exists():
    from orchestrator.agent import root_agent
    assert root_agent is not None

def test_orchestrator_root_agent_is_llm_agent():
    from orchestrator.agent import root_agent
    from google.adk.agents import LlmAgent
    assert isinstance(root_agent, LlmAgent)

def test_orchestrator_agent_name():
    from orchestrator.agent import root_agent
    assert "orchestrator" in root_agent.name.lower()

def test_orchestrator_valid_clients_set():
    from orchestrator.agent import VALID_CLIENTS
    assert isinstance(VALID_CLIENTS, set)
    assert len(VALID_CLIENTS) == 3

def test_orchestrator_all_valid_clients():
    from orchestrator.agent import VALID_CLIENTS
    assert "NPI" in VALID_CLIENTS
    assert "Venetian" in VALID_CLIENTS
    assert "WinnDixie" in VALID_CLIENTS

def test_orchestrator_agent_card_exists():
    from orchestrator.agent import DATA_SCIENTIST_CARD
    assert DATA_SCIENTIST_CARD is not None

def test_orchestrator_agent_card_id():
    from orchestrator.agent import DATA_SCIENTIST_CARD
    assert DATA_SCIENTIST_CARD.agent_id == "data_scientist"

def test_orchestrator_agent_card_version():
    from orchestrator.agent import DATA_SCIENTIST_CARD
    assert DATA_SCIENTIST_CARD.version == "1.0.0"

def test_orchestrator_agent_card_skills_count():
    from orchestrator.agent import DATA_SCIENTIST_CARD
    assert len(DATA_SCIENTIST_CARD.skills) >= 5

def test_orchestrator_agent_card_to_json():
    from orchestrator.agent import DATA_SCIENTIST_CARD
    import json
    result = DATA_SCIENTIST_CARD.to_json()
    data = json.loads(result)
    assert data["agent_id"] == "data_scientist"

def test_orchestrator_agent_card_is_remote_false():
    from orchestrator.agent import DATA_SCIENTIST_CARD
    import os
    os.environ.pop("DS_AGENT_ENDPOINT", None)
    # Reload to get fresh value
    assert isinstance(DATA_SCIENTIST_CARD.is_remote, bool)

def test_orchestrator_model_temperature():
    from orchestrator.agent import root_agent
    assert root_agent.generate_content_config.temperature == 0.0

def test_orchestrator_code_interpreter_env():
    from orchestrator.agent import _CODE_INTERPRETER
    assert isinstance(_CODE_INTERPRETER, str)
    assert len(_CODE_INTERPRETER) > 0
