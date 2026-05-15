"""Test orchestrator prompt content and structure."""
import pytest, sys, os
sys.path.insert(0, os.path.expanduser("~/astrobot_mesh"))

def test_prompt_returns_string():
    from orchestrator.prompts import return_instructions_orchestrator
    result = return_instructions_orchestrator()
    assert isinstance(result, str)

def test_prompt_length():
    from orchestrator.prompts import return_instructions_orchestrator
    result = return_instructions_orchestrator()
    assert len(result) > 2000

def test_prompt_has_npi():
    from orchestrator.prompts import return_instructions_orchestrator
    assert "NPI" in return_instructions_orchestrator()

def test_prompt_has_venetian():
    from orchestrator.prompts import return_instructions_orchestrator
    assert "Venetian" in return_instructions_orchestrator()

def test_prompt_has_winndixie():
    from orchestrator.prompts import return_instructions_orchestrator
    assert "WinnDixie" in return_instructions_orchestrator()

def test_prompt_has_call_data_scientist():
    from orchestrator.prompts import return_instructions_orchestrator
    assert "call_data_scientist" in return_instructions_orchestrator()

def test_prompt_has_call_persona_aggregator():
    from orchestrator.prompts import return_instructions_orchestrator
    assert "call_persona_aggregator" in return_instructions_orchestrator()

def test_prompt_has_submit_feedback():
    from orchestrator.prompts import return_instructions_orchestrator
    assert "submit_feedback" in return_instructions_orchestrator()

def test_prompt_has_security_rules():
    from orchestrator.prompts import return_instructions_orchestrator
    result = return_instructions_orchestrator()
    assert "SECURITY" in result or "NEVER" in result

def test_prompt_has_routing_rules():
    from orchestrator.prompts import return_instructions_orchestrator
    result = return_instructions_orchestrator()
    assert "ROUTING" in result

def test_prompt_has_pipeline_rule():
    from orchestrator.prompts import return_instructions_orchestrator
    result = return_instructions_orchestrator()
    assert "MANDATORY" in result or "pipeline" in result.lower()

def test_prompt_has_duplicate_prevention():
    from orchestrator.prompts import return_instructions_orchestrator
    result = return_instructions_orchestrator()
    assert "DUPLICATE" in result or "duplicate" in result.lower()

def test_prompt_has_visualization_rules():
    from orchestrator.prompts import return_instructions_orchestrator
    result = return_instructions_orchestrator()
    assert "chart" in result.lower() or "VISUALIZATION" in result

def test_prompt_has_ml_rules():
    from orchestrator.prompts import return_instructions_orchestrator
    result = return_instructions_orchestrator()
    assert "ARIMA" in result or "forecast" in result.lower()

def test_prompt_has_today_date():
    from orchestrator.prompts import return_instructions_orchestrator
    from datetime import date
    result = return_instructions_orchestrator()
    assert str(date.today()) in result

def test_prompt_has_netconversion():
    from orchestrator.prompts import return_instructions_orchestrator
    result = return_instructions_orchestrator()
    assert "NetConversion" in result or "netconversion" in result.lower()

def test_prompt_has_persona_examples():
    from orchestrator.prompts import return_instructions_orchestrator
    result = return_instructions_orchestrator()
    assert "HNW" in result or "Luxury Seeker" in result or "DINK" in result

def test_prompt_has_client_isolation():
    from orchestrator.prompts import return_instructions_orchestrator
    result = return_instructions_orchestrator()
    assert "CLIENT ISOLATION" in result or "client_id" in result

def test_prompt_has_response_format():
    from orchestrator.prompts import return_instructions_orchestrator
    result = return_instructions_orchestrator()
    assert "Result" in result or "Explanation" in result

def test_prompt_has_compound_query_handling():
    from orchestrator.prompts import return_instructions_orchestrator
    result = return_instructions_orchestrator()
    assert "COMPOUND" in result or "Step 1" in result
