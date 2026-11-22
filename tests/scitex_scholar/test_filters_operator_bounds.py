"""Numeric parsed-operator bounds preserve explicit zero and form fallbacks."""

import pytest

from scitex_scholar.filters import apply_filters

# field, form key, operator key, form bound, paper values, operator-zero result,
# form-fallback result. Each row checks the same precedence contract.
_BOUND_CASES = [
    ("year", "year_from", "year_min", 2020, [0, 2024], [0, 2024], [2024]),
    ("year", "year_to", "year_max", 2020, [0, 1], [0], [0, 1]),
    ("citations", "min_citations", "citations_min", 5, [0, 10], [0, 10], [10]),
    ("citations", "max_citations", "citations_max", 5, [0, 1], [0], [0, 1]),
    (
        "impact_factor",
        "min_impact_factor",
        "impact_factor_min",
        2.0,
        [0.0, 3.0],
        [0.0, 3.0],
        [3.0],
    ),
    (
        "impact_factor",
        "max_impact_factor",
        "impact_factor_max",
        2.0,
        [0.0, 1.0],
        [0.0],
        [0.0, 1.0],
    ),
]


@pytest.mark.parametrize("case", _BOUND_CASES, ids=[c[2] for c in _BOUND_CASES])
def test_zero_operator_bound_overrides_form_filter(case):
    # Arrange
    field, form, operator, fallback, values, expected, _ = case
    papers = [{field: value} for value in values]
    # Act
    result = apply_filters(papers, {form: fallback}, {operator: 0})
    # Assert
    assert [paper[field] for paper in result] == expected


@pytest.mark.parametrize("case", _BOUND_CASES, ids=[c[2] for c in _BOUND_CASES])
def test_none_operator_bound_retains_form_filter(case):
    # Arrange
    field, form, operator, fallback, values, _, expected = case
    papers = [{field: value} for value in values]
    # Act
    result = apply_filters(papers, {form: fallback}, {operator: None})
    # Assert
    assert [paper[field] for paper in result] == expected


@pytest.mark.parametrize("case", _BOUND_CASES, ids=[c[2] for c in _BOUND_CASES])
def test_missing_operator_bound_retains_form_filter(case):
    # Arrange
    field, form, _, fallback, values, _, expected = case
    papers = [{field: value} for value in values]
    # Act
    result = apply_filters(papers, {form: fallback}, {"title_includes": []})
    # Assert
    assert [paper[field] for paper in result] == expected
