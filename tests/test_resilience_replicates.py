import pytest

from scripts.summarize_resilience_replicates import stats


def test_stats_constant_runs():
    result = stats(
        [1.0, 1.0, 1.0, 1.0, 1.0]
    )

    assert result["n"] == 5
    assert result["mean"] == 1.0
    assert result["sd"] == 0.0

    assert result["ci95_low"] == 1.0
    assert result["ci95_high"] == 1.0

    assert (
        result["ci95_unbounded_low"]
        == 1.0
    )

    assert (
        result["ci95_unbounded_high"]
        == 1.0
    )


def test_stats_variable_runs():
    result = stats(
        [0.4, 0.5, 0.5, 0.6, 0.5]
    )

    assert result["n"] == 5
    assert result["mean"] == pytest.approx(0.5)
    assert result["sd"] > 0

    assert result["ci95_low"] < 0.5
    assert result["ci95_high"] > 0.5


def test_probability_ci_is_bounded():
    result = stats(
        [1.0, 1.0, 1.0, 1.0, 0.75]
    )

    assert result["mean"] == pytest.approx(0.95)

    assert (
        result["ci95_unbounded_high"]
        > 1.0
    )

    assert result["ci95_high"] == 1.0

    assert (
        result["ci95_low"] >= 0.0
    )


def test_one_run_has_no_ci():
    result = stats([0.75])

    assert result["mean"] == 0.75
    assert result["sd"] is None

    assert result["ci95_low"] is None
    assert result["ci95_high"] is None

    assert (
        result["ci95_unbounded_low"]
        is None
    )

    assert (
        result["ci95_unbounded_high"]
        is None
    )
