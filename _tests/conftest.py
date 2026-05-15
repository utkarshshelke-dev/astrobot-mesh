"""
Shared pytest fixtures for the Astrobot test suite.

Adjusts sys.path so that the `lib/` directory at the project root
is importable in tests.
"""

import os
import sys
import pytest
from pathlib import Path

# Project root = the dir containing tests/, lib/, and the config json
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope="session", autouse=True)
def set_config_path():
    """Point all tests at the v3 config at the project root."""
    config_path = PROJECT_ROOT / "ad_campaign_dataset_config_v3.json"
    if not config_path.exists():
        pytest.skip(f"Config v3 not found at {config_path}")
    os.environ["DATASET_CONFIG_FILE_V3"] = str(config_path)
    yield


@pytest.fixture(autouse=True)
def reset_cache():
    """Reset config cache between tests for isolation."""
    from lib.channel_resolver import reset_config_cache
    reset_config_cache()
    yield
    reset_config_cache()


@pytest.fixture
def npi_client_id():
    return "NPI"


@pytest.fixture
def all_client_ids():
    return ["NPI", "Venetian", "WinnDixie"]