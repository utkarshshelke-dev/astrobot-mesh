"""Test config + custom markers for live BQ / live agent tests."""
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

# Env defaults
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "nc-ai-chatbot")
os.environ.setdefault("BQ_DATA_PROJECT_ID", "nc-ai-chatbot")
if not os.environ.get("DATASET_CONFIG_FILE_V3"):
    cfg = REPO_ROOT / "ad_campaign_dataset_config_v3.json"
    if cfg.exists():
        os.environ["DATASET_CONFIG_FILE_V3"] = str(cfg)

# Silence noisy agent.py imports during tests
import logging
logging.getLogger("data_science.agent").setLevel(logging.ERROR)


# ============================================================
# pytest markers
# ============================================================
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "live_bq: requires real BigQuery credentials + network"
    )
    config.addinivalue_line(
        "markers", "live_agent: requires LLM API access + ADK runner"
    )


def pytest_addoption(parser):
    parser.addoption(
        "--live",
        action="store_true",
        default=False,
        help="Run live BQ and live agent tests (costs ~$1-2 per full run)",
    )


def pytest_collection_modifyitems(config, items):
    """Skip live tests unless --live flag is passed."""
    if config.getoption("--live"):
        return
    skip_live = __import__("pytest").mark.skip(
        reason="Live test — pass --live to run (costs $$)"
    )
    for item in items:
        if "live_bq" in item.keywords or "live_agent" in item.keywords:
            item.add_marker(skip_live)
