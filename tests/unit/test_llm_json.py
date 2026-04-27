"""Tests for `src.api.llm_json` — the pure JSON-handling helpers."""

from __future__ import annotations

import pytest

from src.api.llm_json import (
    CHART_EDITOR_ALLOWED_OPERATORS,
    extract_chart_type,
    extract_json_object,
    normalise_corrections,
    normalise_derived_series,
    sanitize_llm_json,
)


# ----------------------------------------------------------------------
# extract_json_object
# ----------------------------------------------------------------------
class TestExtractJsonObject:
    def test_strict_object(self):
        assert extract_json_object('{"a": 1}') == {"a": 1}

    def test_strips_json_fence(self):
        raw = '```json\n{"a": 1}\n```'
        assert extract_json_object(raw) == {"a": 1}

    def test_strips_bare_fence(self):
        raw = '```\n{"a": 1}\n```'
        assert extract_json_object(raw) == {"a": 1}

    def test_trims_to_outer_braces(self):
        raw = 'sure! {"a": 1}  trailing junk'
        assert extract_json_object(raw) == {"a": 1}

    def test_recovers_from_trailing_comma(self):
        raw = '{"a": 1, "b": [1, 2,],}'
        assert extract_json_object(raw) == {"a": 1, "b": [1, 2]}

    def test_recovers_from_js_function_formatter(self):
        raw = '{"formatter": function(value) { return value + "K"; }}'
        result = extract_json_object(raw)
        assert isinstance(result, dict) and "formatter" in result

    def test_returns_none_on_garbage(self):
        assert extract_json_object("definitely not json") is None

    def test_returns_none_on_empty(self):
        assert extract_json_object("") is None
        assert extract_json_object(None) is None  # type: ignore[arg-type]


# ----------------------------------------------------------------------
# sanitize_llm_json
# ----------------------------------------------------------------------
class TestSanitizeLlmJson:
    def test_drops_line_comments(self):
        assert "//" not in sanitize_llm_json('{"a": 1} // trailing')

    def test_drops_block_comments(self):
        assert "/*" not in sanitize_llm_json('{"a": /* x */ 1}')

    def test_drops_trailing_commas(self):
        assert sanitize_llm_json("[1, 2, 3,]") == "[1, 2, 3]"


# ----------------------------------------------------------------------
# normalise_corrections
# ----------------------------------------------------------------------
class TestNormaliseCorrections:
    def test_canonical_shape(self):
        out = normalise_corrections([{"wrong": "prooduct", "right": "product"}])
        assert out == [{"wrong": "prooduct", "right": "product"}]

    def test_legacy_from_to(self):
        out = normalise_corrections([{"from": "salez", "to": "sales"}])
        assert out == [{"wrong": "salez", "right": "sales"}]

    def test_single_pair_dict(self):
        out = normalise_corrections([{"prooduct": "product"}])
        assert out == [{"wrong": "prooduct", "right": "product"}]

    def test_arrow_string(self):
        out = normalise_corrections(["prooduct -> product"])
        assert out == [{"wrong": "prooduct", "right": "product"}]

    def test_unicode_arrow(self):
        out = normalise_corrections(["prooduct → product"])
        assert out == [{"wrong": "prooduct", "right": "product"}]

    def test_drops_self_equal(self):
        assert normalise_corrections([{"wrong": "ok", "right": "OK"}]) == []

    def test_drops_duplicates(self):
        out = normalise_corrections(
            [
                {"wrong": "a", "right": "b"},
                {"wrong": "a", "right": "b"},
            ]
        )
        assert len(out) == 1

    def test_caps_at_four(self):
        items = [{"wrong": f"w{i}", "right": f"r{i}"} for i in range(10)]
        assert len(normalise_corrections(items)) == 4

    def test_non_list_input(self):
        assert normalise_corrections("not a list") == []  # type: ignore[arg-type]
        assert normalise_corrections(None) == []  # type: ignore[arg-type]


# ----------------------------------------------------------------------
# normalise_derived_series
# ----------------------------------------------------------------------
class TestNormaliseDerivedSeries:
    def test_valid_moving_avg(self):
        out = normalise_derived_series(
            [
                {
                    "operator": "moving_avg",
                    "source_column": "Sales",
                    "params": {"window": 3},
                    "label": "MA(3)",
                }
            ],
            allowed_columns=["sales", "month"],
        )
        # source_column should be canonicalised to the matching column case.
        assert out == [
            {
                "operator": "moving_avg",
                "source_column": "sales",
                "params": {"window": 3},
                "label": "MA(3)",
            }
        ]

    def test_drops_unknown_operator(self):
        out = normalise_derived_series(
            [{"operator": "bogus_op", "source_column": "sales"}],
            allowed_columns=["sales"],
        )
        assert out == []

    def test_drops_unknown_column(self):
        out = normalise_derived_series(
            [{"operator": "moving_avg", "source_column": "nope"}],
            allowed_columns=["sales"],
        )
        assert out == []

    def test_clamps_window_to_positive_int(self):
        out = normalise_derived_series(
            [
                {
                    "operator": "moving_avg",
                    "source_column": "sales",
                    "params": {"window": 0},
                }
            ],
            allowed_columns=["sales"],
        )
        assert out[0]["params"]["window"] == 1

    def test_synthesises_label_when_missing(self):
        out = normalise_derived_series(
            [{"operator": "linear_trend", "source_column": "sales"}],
            allowed_columns=["sales"],
        )
        assert out[0]["label"] == "linear_trend (sales)"

    def test_caps_at_four(self):
        items = [
            {"operator": "moving_avg", "source_column": "sales"} for _ in range(10)
        ]
        out = normalise_derived_series(items, allowed_columns=["sales"])
        assert len(out) == 4

    def test_non_list_input(self):
        assert normalise_derived_series(None, []) == []  # type: ignore[arg-type]

    def test_allowlist_is_authoritative(self):
        # Sanity: every operator name we exercise above is in the allowlist.
        assert "moving_avg" in CHART_EDITOR_ALLOWED_OPERATORS
        assert "linear_trend" in CHART_EDITOR_ALLOWED_OPERATORS


# ----------------------------------------------------------------------
# extract_chart_type
# ----------------------------------------------------------------------
class TestExtractChartType:
    def test_reads_first_series_type(self):
        assert extract_chart_type({"series": [{"type": "line"}, {"type": "bar"}]}) == "line"

    def test_defaults_to_bar_when_missing(self):
        assert extract_chart_type({}) == "bar"
        assert extract_chart_type({"series": []}) == "bar"
        assert extract_chart_type({"series": [{}]}) == "bar"

    @pytest.mark.parametrize("bad", [None, 0, "string", []])
    def test_safe_against_non_dict(self, bad):
        assert extract_chart_type(bad) == "bar"  # type: ignore[arg-type]
