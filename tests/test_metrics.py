"""Unit tests for EvalForge metrics calculation, pass@k estimators, and aggregation."""

import math

import pytest

from evalforge.core.constants import ErrorTypeEnum
from evalforge.metrics import (
    MetricsAggregator,
    compute_confidence_interval,
    compute_pass_at_k_metrics,
    estimate_pass_at_k,
)
from evalforge.models.schemas import (
    EvalRunReport,
    ExecutionResult,
    RubricScore,
    TaskEvaluationResult,
)


# -----------------------------------------------------------------------------
# 1. Known Mathematical Reference Values (Codex / Chen et al., 2021)
# -----------------------------------------------------------------------------
def test_estimate_pass_at_k_reference_values():
    """Verify exact mathematical reference values from Codex pass@k formulation."""
    # n=1, c=1, k=1 -> 1.0
    assert estimate_pass_at_k(n=1, c=1, k=1) == 1.0

    # n=1, c=0, k=1 -> 0.0
    assert estimate_pass_at_k(n=1, c=0, k=1) == 0.0

    # n=10, c=5, k=1 -> 0.5
    assert estimate_pass_at_k(n=10, c=5, k=1) == 0.5

    # n=10, c=2, k=5 -> 1 - binom(8, 5) / binom(10, 5) = 1 - 56/252 = 1 - 2/9 ~ 0.7777777777777778
    expected_10_2_5 = 1.0 - (2.0 / 9.0)
    assert estimate_pass_at_k(n=10, c=2, k=5) == pytest.approx(expected_10_2_5, abs=1e-14)
    assert estimate_pass_at_k(n=10, c=2, k=5) == pytest.approx(0.7777777777777778, abs=1e-14)

    # n=10, c=0, k=5 -> 0.0
    assert estimate_pass_at_k(n=10, c=0, k=5) == 0.0

    # n=10, c=10, k=5 -> 1.0
    assert estimate_pass_at_k(n=10, c=10, k=5) == 1.0

    # n=5, c=1, k=5 -> 1.0
    assert estimate_pass_at_k(n=5, c=1, k=5) == 1.0


# -----------------------------------------------------------------------------
# 2. Error Handling & Parameter Validation
# -----------------------------------------------------------------------------
def test_estimate_pass_at_k_n_less_than_k_raises_value_error():
    """Verify that n < k raises ValueError with specified message format."""
    with pytest.raises(ValueError, match=r"Sample count n=0 must be >= k=1"):
        estimate_pass_at_k(n=0, c=0, k=1)

    with pytest.raises(ValueError, match=r"Sample count n=4 must be >= k=5"):
        estimate_pass_at_k(n=4, c=2, k=5)

    with pytest.raises(ValueError, match=r"Sample count n=1 must be >= k=5"):
        estimate_pass_at_k(n=1, c=1, k=5)


def test_estimate_pass_at_k_invalid_parameters():
    """Verify error handling for out-of-bounds k and c parameters."""
    # k < 1
    with pytest.raises(ValueError, match=r"k=0 must be >= 1"):
        estimate_pass_at_k(n=10, c=5, k=0)

    with pytest.raises(ValueError, match=r"k=-2 must be >= 1"):
        estimate_pass_at_k(n=10, c=5, k=-2)

    # c < 0
    with pytest.raises(ValueError, match=r"Correct count c=-1 must be between 0 and n=10"):
        estimate_pass_at_k(n=10, c=-1, k=1)

    # c > n
    with pytest.raises(ValueError, match=r"Correct count c=11 must be between 0 and n=10"):
        estimate_pass_at_k(n=10, c=11, k=1)


# -----------------------------------------------------------------------------
# 3. Numerical Stability with Large n
# -----------------------------------------------------------------------------
def test_estimate_pass_at_k_numerical_stability_large_n():
    """Verify product formulation maintains precision without overflow on large n."""
    n, c, k = 200, 100, 10
    result = estimate_pass_at_k(n=n, c=c, k=k)

    # Compare against exact math.comb calculation
    exact = 1.0 - math.comb(n - c, k) / math.comb(n, k)
    assert result == pytest.approx(exact, abs=1e-12)
    assert 0.0 <= result <= 1.0

    # Even larger sample set where factorials would overflow standard C ints
    n_large, c_large, k_large = 500, 250, 20
    large_result = estimate_pass_at_k(n=n_large, c=c_large, k=k_large)
    exact_large = 1.0 - math.comb(n_large - c_large, k_large) / math.comb(n_large, k_large)
    assert large_result == pytest.approx(exact_large, abs=1e-12)


# -----------------------------------------------------------------------------
# 4. compute_pass_at_k_metrics
# -----------------------------------------------------------------------------
def test_compute_pass_at_k_metrics_with_bool_list():
    """Verify computing pass@k from a list of boolean sample outcomes."""
    # 10 samples: 5 pass, 5 fail
    samples = [True, False, True, False, True, False, True, False, True, False]
    metrics = compute_pass_at_k_metrics(samples, k_values=[1, 5])

    assert "pass@1" in metrics
    assert "pass@5" in metrics
    assert metrics["pass@1"] == 0.5
    assert metrics["pass@5"] == estimate_pass_at_k(10, 5, 5)


def test_compute_pass_at_k_metrics_with_task_evaluation_results():
    """Verify computing pass@k from TaskEvaluationResult instances."""
    results = []
    for i in range(10):
        passed = i < 7  # 7 passed, 3 failed
        results.append(
            TaskEvaluationResult(
                task_id="EF-PY-001",
                model_name="claude-3-5-sonnet",
                rubric=RubricScore.compute(functional_score=40.0 if passed else 0.0),
                execution=ExecutionResult(exit_code=0 if passed else 1),
                passed=passed,
            )
        )

    metrics = compute_pass_at_k_metrics(results, k_values=[1, 5])
    assert metrics["pass@1"] == pytest.approx(0.7)
    assert metrics["pass@5"] == pytest.approx(estimate_pass_at_k(10, 7, 5))


def test_compute_pass_at_k_metrics_insufficient_samples_raises():
    """Verify ValueError when n < k in compute_pass_at_k_metrics."""
    with pytest.raises(ValueError, match=r"Sample count n=2 must be >= k=5"):
        compute_pass_at_k_metrics([True, False], k_values=[5])


# -----------------------------------------------------------------------------
# 5. Confidence Interval Calculations
# -----------------------------------------------------------------------------
def test_compute_confidence_interval_normal():
    """Verify normal confidence interval calculation around benchmark score mean."""
    scores = [70.0, 80.0, 85.0, 90.0, 95.0]
    lower, upper = compute_confidence_interval(scores, confidence=0.95)

    mean = sum(scores) / len(scores)
    assert lower < mean < upper
    # Verify symmetry
    assert (mean - lower) == pytest.approx(upper - mean, abs=1e-10)

    # 99% CI should be strictly wider than 95% CI
    lower_99, upper_99 = compute_confidence_interval(scores, confidence=0.99)
    assert lower_99 < lower
    assert upper_99 > upper


def test_compute_confidence_interval_edge_cases():
    """Verify boundary and edge conditions for confidence interval calculation."""
    # Empty scores
    assert compute_confidence_interval([]) == (0.0, 0.0)

    # Single score
    assert compute_confidence_interval([88.5]) == (88.5, 88.5)

    # Identical scores (zero standard deviation)
    assert compute_confidence_interval([90.0, 90.0, 90.0]) == (90.0, 90.0)

    # Invalid confidence values
    with pytest.raises(ValueError, match=r"Confidence level must be between 0 and 1"):
        compute_confidence_interval([80.0, 90.0], confidence=0.0)

    with pytest.raises(ValueError, match=r"Confidence level must be between 0 and 1"):
        compute_confidence_interval([80.0, 90.0], confidence=1.0)


# -----------------------------------------------------------------------------
# 6. MetricsAggregator Run Aggregation
# -----------------------------------------------------------------------------
def _make_eval(task_id: str, passed: bool, score: float) -> TaskEvaluationResult:
    return TaskEvaluationResult(
        task_id=task_id,
        model_name="gpt-4o",
        rubric=RubricScore.compute(functional_score=score * 0.4, edge_scale_score=score * 0.3),
        execution=ExecutionResult(
            stdout="PASS" if passed else "FAIL",
            exit_code=0 if passed else 1,
            error_type=ErrorTypeEnum.NONE if passed else ErrorTypeEnum.RUNTIME_EXCEPTION,
        ),
        passed=passed,
    )


def test_metrics_aggregator_aggregate_run_multi_task():
    """Verify aggregation across multiple tasks and samples into EvalRunReport."""
    evaluations: list[TaskEvaluationResult] = []

    # Task A: 10 samples, 8 passed, composite scores 80.0
    for i in range(10):
        evaluations.append(_make_eval("TASK-A", passed=(i < 8), score=80.0))

    # Task B: 10 samples, 5 passed, composite scores 60.0
    for i in range(10):
        evaluations.append(_make_eval("TASK-B", passed=(i < 5), score=60.0))

    # Task C: 10 samples, 10 passed, composite scores 100.0
    for i in range(10):
        evaluations.append(_make_eval("TASK-C", passed=True, score=100.0))

    report = MetricsAggregator.aggregate_run(
        run_id="RUN-EF-TEST-001",
        model_name="gpt-4o",
        evaluations=evaluations,
        k_values=[1, 5],
    )

    assert isinstance(report, EvalRunReport)
    assert report.run_id == "RUN-EF-TEST-001"
    assert report.model_name == "gpt-4o"
    assert report.tasks_evaluated == 3
    assert report.total_samples == 30
    assert report.pass_rate == pytest.approx((8 + 5 + 10) / 30)

    # Task pass@1: A=0.8, B=0.5, C=1.0 -> Mean = (0.8 + 0.5 + 1.0) / 3 = 0.7666...
    expected_pass_1 = (0.8 + 0.5 + 1.0) / 3.0
    assert report.pass_at_1 == pytest.approx(expected_pass_1)

    # Task pass@5:
    pass_5_a = estimate_pass_at_k(10, 8, 5)
    pass_5_b = estimate_pass_at_k(10, 5, 5)
    pass_5_c = estimate_pass_at_k(10, 10, 5)  # 1.0
    expected_pass_5 = (pass_5_a + pass_5_b + pass_5_c) / 3.0
    assert report.pass_at_5 == pytest.approx(expected_pass_5)

    assert len(report.results) == 30

    # JSON roundtrip serialization
    json_bytes = report.model_dump_json()
    reloaded = EvalRunReport.model_validate_json(json_bytes)
    assert reloaded.run_id == report.run_id
    assert reloaded.pass_at_1 == report.pass_at_1
    assert reloaded.total_samples == 30


def test_metrics_aggregator_empty_evaluations():
    """Verify aggregate_run gracefully handles empty evaluation lists."""
    report = MetricsAggregator.aggregate_run(
        run_id="RUN-EMPTY",
        model_name="dummy-model",
        evaluations=[],
    )
    assert report.tasks_evaluated == 0
    assert report.total_samples == 0
    assert report.pass_rate == 0.0
    assert report.pass_at_1 == 0.0
    assert report.pass_at_5 == 0.0
    assert report.mean_score == 0.0
    assert len(report.results) == 0


def test_metrics_aggregator_single_sample_per_task():
    """Verify aggregate_run with n=1 sample per task computes pass@1 and zeros pass@5."""
    evaluations = [
        _make_eval("TASK-1", passed=True, score=90.0),
        _make_eval("TASK-2", passed=True, score=85.0),
        _make_eval("TASK-3", passed=False, score=20.0),
        _make_eval("TASK-4", passed=True, score=95.0),
    ]

    report = MetricsAggregator.aggregate_run(
        run_id="RUN-SINGLE-SAMPLE",
        model_name="claude-3-5-haiku",
        evaluations=evaluations,
    )

    assert report.tasks_evaluated == 4
    assert report.total_samples == 4
    assert report.pass_rate == 0.75
    assert report.pass_at_1 == 0.75
    assert report.pass_at_5 == 0.0  # Sample count n=1 < 5 for all tasks
