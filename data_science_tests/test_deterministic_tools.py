"""Tests for data_science.sub_agents.bigquery.tools deterministic functions.

These tests verify SIGNATURES and BASIC SHAPE — they do NOT make live BQ calls.
For live testing, use the eval harness with credentials.
"""
import inspect
import pytest
from data_science.sub_agents.bigquery import tools as bq_tools


# ============================================================
# Signature checks — ensure ADK can build JSON schemas
# ============================================================

class TestSignatures:
    """Confirm function signatures are well-annotated for ADK function-calling."""

    def test_compute_channel_volatility_annotated(self):
        sig = inspect.signature(bq_tools.compute_channel_volatility)
        for name, param in sig.parameters.items():
            if name == "self":
                continue
            assert param.annotation is not inspect.Parameter.empty, \
                f"Parameter '{name}' missing type annotation"

    def test_compute_saturation_curve_annotated(self):
        sig = inspect.signature(bq_tools.compute_saturation_curve)
        for name, param in sig.parameters.items():
            if name == "self":
                continue
            assert param.annotation is not inspect.Parameter.empty, \
                f"Parameter '{name}' missing type annotation"

    def test_get_channel_volatility_summary_annotated(self):
        sig = inspect.signature(bq_tools.get_channel_volatility_summary)
        for name, param in sig.parameters.items():
            if name == "self":
                continue
            assert param.annotation is not inspect.Parameter.empty


class TestDefaults:
    """Optional parameters have defaults so LLM doesn't need to know them."""

    def test_volatility_table_name_optional(self):
        sig = inspect.signature(bq_tools.compute_channel_volatility)
        assert sig.parameters["table_name"].default is None

    def test_volatility_metric_defaults_to_conversions(self):
        sig = inspect.signature(bq_tools.compute_channel_volatility)
        assert sig.parameters["metric"].default == "Conversions"

    def test_volatility_min_months_auto_scales(self):
        """min_months default should be None (auto-scale) after our patch."""
        sig = inspect.signature(bq_tools.compute_channel_volatility)
        assert sig.parameters["min_months"].default is None, \
            "min_months should auto-scale based on lookback_months"

    def test_saturation_spend_levels_optional(self):
        sig = inspect.signature(bq_tools.compute_saturation_curve)
        assert sig.parameters["spend_levels"].default is None


class TestErrorHandling:
    """Functions return error dicts, not raise, for handle-able failures."""

    def test_volatility_invalid_metric_returns_error_dict(self):
        result = bq_tools.compute_channel_volatility(
            client_id="NPI",
            table_name="x.y.z",  # bypass KM lookup
            metric="NotARealMetric",
        )
        assert isinstance(result, dict)
        assert result.get("status") == "ERROR"
        assert "error" in result
        assert "NotARealMetric" in result["error"]

    def test_volatility_returns_dict_structure(self):
        """Even on validation error, return shape stays consistent."""
        result = bq_tools.compute_channel_volatility(
            client_id="NPI",
            table_name="x.y.z",
            metric="BadMetric",
        )
        assert "status" in result
        assert "channels" in result
        assert isinstance(result["channels"], list)


class TestAdkFunctionToolWrapping:
    """ADK should be able to wrap our functions as FunctionTools."""

    def test_volatility_wrappable_by_adk(self):
        """Catches the INVALID_ARGUMENT issue from earlier."""
        try:
            from google.adk.tools import FunctionTool
        except ImportError:
            pytest.skip("google.adk not installed")
        # Should not raise
        tool = FunctionTool(bq_tools.compute_channel_volatility)
        assert tool is not None

    def test_saturation_wrappable_by_adk(self):
        try:
            from google.adk.tools import FunctionTool
        except ImportError:
            pytest.skip("google.adk not installed")
        tool = FunctionTool(bq_tools.compute_saturation_curve)
        assert tool is not None

    def test_summary_wrappable_by_adk(self):
        try:
            from google.adk.tools import FunctionTool
        except ImportError:
            pytest.skip("google.adk not installed")
        tool = FunctionTool(bq_tools.get_channel_volatility_summary)
        assert tool is not None
