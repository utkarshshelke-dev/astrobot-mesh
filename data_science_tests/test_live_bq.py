"""Live BigQuery tests — exercise the deterministic tools end-to-end.

Run with:    pytest data_science_tests/test_live_bq.py --live -v
Skipped by default — pass --live to enable.

Cost: ~$0.05-0.20 per full run.
"""
import os
import pytest

from data_science.sub_agents.bigquery.tools import (
    compute_channel_volatility,
    get_channel_volatility_summary,
    compute_saturation_curve,
)


@pytest.fixture(autouse=True)
def env_set():
    """Ensure env vars are set."""
    assert os.environ.get("GOOGLE_CLOUD_PROJECT") == "nc-ai-chatbot"
    yield


@pytest.mark.live_bq
class TestComputeChannelVolatility:
    def test_npi_cost_12mo_returns_data(self):
        r = compute_channel_volatility(client_id="NPI", metric="Cost", lookback_months=12)
        assert r["status"] == "SUCCESS"
        assert len(r["channels"]) > 0

    def test_npi_cost_6mo_returns_data(self):
        """Auto-scaled min_months should make 6-month lookback work."""
        r = compute_channel_volatility(client_id="NPI", metric="Cost", lookback_months=6)
        assert r["status"] == "SUCCESS"
        assert len(r["channels"]) > 0

    def test_invalid_metric_returns_error(self):
        r = compute_channel_volatility(
            client_id="NPI", metric="NotAMetric", lookback_months=6,
        )
        assert r["status"] == "ERROR"
        assert "metric" in r["error"].lower()

    def test_conversions_metric_works(self):
        r = compute_channel_volatility(
            client_id="NPI", metric="Conversions", lookback_months=12,
        )
        assert r["status"] == "SUCCESS"

    def test_returns_dict_with_channels_list(self):
        r = compute_channel_volatility(client_id="NPI", metric="Cost", lookback_months=12)
        assert isinstance(r, dict)
        assert isinstance(r.get("channels"), list)


@pytest.mark.live_bq
class TestGetChannelVolatilitySummary:
    def test_returns_all_four_metrics(self):
        r = get_channel_volatility_summary(client_id="NPI", lookback_months=12)
        assert r["status"] == "SUCCESS"
        by_metric = r.get("by_metric", {})
        for m in ("Cost", "Conversions", "Clicks", "Impressions"):
            assert m in by_metric, f"Missing metric: {m}"


@pytest.mark.live_bq
class TestComputeSaturationCurve:
    def test_npi_100k_allocation(self):
        r = compute_saturation_curve(client_id="NPI", budget_to_allocate=100000)
        # Either SUCCESS with allocation, or PARTIAL with at least one fitted channel
        assert r.get("status") in ("SUCCESS", "PARTIAL")

    def test_returns_dict(self):
        r = compute_saturation_curve(client_id="NPI", budget_to_allocate=50000)
        assert isinstance(r, dict)
        assert "status" in r
