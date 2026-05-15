"""Test AgentCard and AgentSkill dataclasses."""
import pytest, sys, os
sys.path.insert(0, os.path.expanduser("~/astrobot_mesh"))

def test_agent_skill_creation():
    from orchestrator.agent import AgentSkill
    skill = AgentSkill(id="test", name="Test", description="A test skill")
    assert skill.id == "test"
    assert skill.name == "Test"

def test_agent_skill_defaults():
    from orchestrator.agent import AgentSkill
    skill = AgentSkill(id="test", name="Test", description="desc")
    assert skill.examples == []
    assert skill.tags == []

def test_agent_skill_with_examples():
    from orchestrator.agent import AgentSkill
    skill = AgentSkill(id="nl2sql", name="NL to SQL",
                       description="desc", examples=["Show top channels"])
    assert "Show top channels" in skill.examples

def test_agent_card_creation():
    from orchestrator.agent import AgentCard, AgentSkill
    card = AgentCard(
        agent_id="test", name="Test", version="1.0",
        description="desc", endpoint="", skills=[]
    )
    assert card.agent_id == "test"
    assert card.is_remote == False

def test_agent_card_is_remote_true():
    from orchestrator.agent import AgentCard
    card = AgentCard(
        agent_id="test", name="Test", version="1.0",
        description="desc",
        endpoint="https://example.run.app",
        skills=[]
    )
    assert card.is_remote == True

def test_agent_card_is_remote_false():
    from orchestrator.agent import AgentCard
    card = AgentCard(
        agent_id="test", name="Test", version="1.0",
        description="desc", endpoint="", skills=[]
    )
    assert card.is_remote == False

def test_data_scientist_card_skills():
    from orchestrator.agent import DATA_SCIENTIST_CARD
    ids = [s.id for s in DATA_SCIENTIST_CARD.skills]
    assert "nl2sql" in ids
    assert "bqml_forecast" in ids
    assert "bqml_cluster" in ids
    assert "anomaly" in ids
    assert "charts" in ids

def test_data_scientist_card_input_schema():
    from orchestrator.agent import DATA_SCIENTIST_CARD
    schema = DATA_SCIENTIST_CARD.input_schema
    assert "request" in schema
    assert "client_id" in schema

def test_data_scientist_card_output_mode():
    from orchestrator.agent import DATA_SCIENTIST_CARD
    assert DATA_SCIENTIST_CARD.output_mode == "markdown"

def test_data_scientist_card_json_roundtrip():
    from orchestrator.agent import DATA_SCIENTIST_CARD
    import json
    j = DATA_SCIENTIST_CARD.to_json()
    data = json.loads(j)
    assert data["version"] == "1.0.0"
    assert len(data["skills"]) >= 5
