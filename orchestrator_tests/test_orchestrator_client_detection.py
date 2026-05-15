"""Test client detection and locking logic."""
import pytest, sys, os
sys.path.insert(0, os.path.expanduser("~/astrobot_mesh"))

def test_detect_client_npi():
    from orchestrator.agent import _detect_client
    assert _detect_client("For NPI show top channels") == "NPI"

def test_detect_client_npi_lowercase():
    from orchestrator.agent import _detect_client
    assert _detect_client("for npi show top channels") == "NPI"

def test_detect_client_nassau():
    from orchestrator.agent import _detect_client
    assert _detect_client("Nassau Paradise Island data") == "NPI"

def test_detect_client_paradise_island():
    from orchestrator.agent import _detect_client
    assert _detect_client("paradise island campaigns") == "NPI"

def test_detect_client_venetian():
    from orchestrator.agent import _detect_client
    assert _detect_client("Venetian OOH performance") == "Venetian"

def test_detect_client_venetian_lowercase():
    from orchestrator.agent import _detect_client
    assert _detect_client("venetian spend last quarter") == "Venetian"

def test_detect_client_winndixie():
    from orchestrator.agent import _detect_client
    assert _detect_client("WinnDixie ViVs last quarter") == "WinnDixie"

def test_detect_client_winn_dixie_space():
    from orchestrator.agent import _detect_client
    assert _detect_client("winn dixie performance") == "WinnDixie"

def test_detect_client_winn_dixie_hyphen():
    from orchestrator.agent import _detect_client
    assert _detect_client("winn-dixie streaming data") == "WinnDixie"

def test_detect_client_seg():
    from orchestrator.agent import _detect_client
    assert _detect_client("SEG streaming performance") == "WinnDixie"

def test_detect_client_none_weather():
    from orchestrator.agent import _detect_client
    assert _detect_client("what is the weather today") is None

def test_detect_client_none_empty():
    from orchestrator.agent import _detect_client
    assert _detect_client("") is None

def test_detect_client_none_generic():
    from orchestrator.agent import _detect_client
    assert _detect_client("show me top channels by spend") is None

def test_detect_client_none_unknown():
    from orchestrator.agent import _detect_client
    assert _detect_client("For Pepsi show top channels") is None

def test_detect_client_none_whitespace():
    from orchestrator.agent import _detect_client
    assert _detect_client("   ") is None
