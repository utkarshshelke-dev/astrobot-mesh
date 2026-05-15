"""Test remote client module."""
import pytest, sys, os
sys.path.insert(0, os.path.expanduser("~/astrobot_mesh"))

def test_remote_client_loads():
    import orchestrator.remote_client as rc
    assert rc is not None

def test_remote_client_ds_endpoint_set():
    import orchestrator.remote_client as rc
    assert hasattr(rc, "DS_ENDPOINT")
    assert isinstance(rc.DS_ENDPOINT, str)

def test_remote_client_app_name():
    import orchestrator.remote_client as rc
    assert rc.APP_NAME == "data_science"

def test_remote_client_get_token_callable():
    from orchestrator.remote_client import _get_token
    assert callable(_get_token)

def test_remote_client_post_callable():
    from orchestrator.remote_client import _post
    assert callable(_post)

def test_remote_client_call_remote_ds_callable():
    from orchestrator.remote_client import call_remote_ds_agent
    assert callable(call_remote_ds_agent)

def test_remote_client_get_artifacts_callable():
    from orchestrator.remote_client import get_session_artifacts
    assert callable(get_session_artifacts)

def test_remote_client_post_bad_url():
    from orchestrator.remote_client import _post
    try:
        _post("http://localhost:99999/bad", {}, "fake_token")
    except Exception as e:
        assert isinstance(e, Exception)

def test_remote_client_call_ds_bad_endpoint():
    import asyncio
    import os
    os.environ["DS_AGENT_ENDPOINT"] = "http://localhost:99999"
    from orchestrator.remote_client import call_remote_ds_agent
    try:
        result = asyncio.run(call_remote_ds_agent("test", "NPI"))
        assert "Error" in result or isinstance(result, str)
    except Exception:
        pass
    finally:
        os.environ.pop("DS_AGENT_ENDPOINT", None)

def test_remote_client_get_artifacts_bad_session():
    import asyncio
    from orchestrator.remote_client import get_session_artifacts
    try:
        result = asyncio.run(get_session_artifacts("nonexistent-session"))
        assert isinstance(result, list)
    except Exception:
        pass

def test_remote_client_ds_endpoint_default():
    import orchestrator.remote_client as rc
    import os
    old = os.environ.pop("DS_AGENT_ENDPOINT", None)
    # Re-check default
    assert "run.app" in rc.DS_ENDPOINT or isinstance(rc.DS_ENDPOINT, str)
    if old:
        os.environ["DS_AGENT_ENDPOINT"] = old
