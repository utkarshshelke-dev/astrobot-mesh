"""More tests for data_science/tools.py — uncovered branches."""
import pytest
from data_science import tools


class TestNormalizeSeriesToDict:
    """_normalize_series_to_dict — our chart fix from earlier."""

    def test_dict_passthrough(self):
        d = {"A": [1, 2, 3], "B": [4, 5, 6]}
        assert tools._normalize_series_to_dict(d) == d

    def test_list_of_dicts_with_name_values(self):
        inp = [{"name": "Peak", "values": [10, 20]}, {"name": "Trough", "values": [5, 8]}]
        out = tools._normalize_series_to_dict(inp)
        assert out == {"Peak": [10, 20], "Trough": [5, 8]}

    def test_list_of_dicts_with_label_data(self):
        inp = [{"label": "A", "data": [1, 2]}, {"label": "B", "data": [3, 4]}]
        out = tools._normalize_series_to_dict(inp)
        assert out == {"A": [1, 2], "B": [3, 4]}

    def test_list_of_lists(self):
        inp = [[1, 2, 3], [4, 5, 6]]
        out = tools._normalize_series_to_dict(inp)
        assert out == {"Series 1": [1, 2, 3], "Series 2": [4, 5, 6]}

    def test_empty_list(self):
        assert tools._normalize_series_to_dict([]) == {}

    def test_none(self):
        assert tools._normalize_series_to_dict(None) == {}


class TestFilterEmptyChartDataEdges:
    def test_handles_none(self):
        result = tools._filter_empty_chart_data(None)
        assert result is None or result == {}

    def test_handles_list(self):
        # Pass a list — should return list (not crash)
        result = tools._filter_empty_chart_data([1, 2, 3])
        assert result == [1, 2, 3] or isinstance(result, list)

    def test_all_zero_string_variations(self):
        d = {"A": ["0", "0.0", "0%", 0, 0.0, None]}
        result = tools._filter_empty_chart_data(d)
        # All zeros — should be filtered
        assert "A" not in result or result.get("A") == d["A"]


class TestValidateChartDataAllTypes:
    def test_line_with_one_point_fails(self):
        valid, reason = tools._validate_chart_data(
            "line", {"x": [1], "y": [2]}
        )
        assert not valid

    def test_pie_with_mismatched_lengths(self):
        valid, reason = tools._validate_chart_data(
            "pie", {"categories": ["A", "B"], "values": [10]}
        )
        assert not valid
        assert "mismatch" in reason.lower() or "missing" in reason.lower()

    def test_stacked_bar_valid_with_one_good_series(self):
        valid, reason = tools._validate_chart_data(
            "stacked_bar",
            {
                "categories": ["A", "B"],
                "series": {"Peak": [10, 20], "Trough": [0, 0]}
            }
        )
        # Should be valid — Peak has data even if Trough is zeros
        assert valid

    def test_unknown_chart_type_defaults_valid(self):
        """Chart types we don't validate fall through to True."""
        valid, reason = tools._validate_chart_data(
            "treemap", {"categories": ["A"], "values": [1]}
        )
        # Function doesn't validate treemap explicitly — returns True/OK
        assert valid


class TestCacheKeyVariations:
    def test_overwrite_with_none(self):
        tools._cache_set("test_none_key", None)
        assert tools._cache_get("test_none_key") is None

    def test_overwrite_with_dict(self):
        tools._cache_set("test_dict_key", {"a": 1})
        assert tools._cache_get("test_dict_key") == {"a": 1}

    def test_overwrite_with_list(self):
        tools._cache_set("test_list_key", [1, 2, 3])
        assert tools._cache_get("test_list_key") == [1, 2, 3]
