"""Metrics calculation and aggregation for EvalForge benchmark evaluations.

Implements unbiased pass@k estimators (Chen et al., 2021), metric aggregation across
multi-task benchmark runs, and confidence interval estimation.
"""

import math
import statistics

from evalforge.models.schemas import EvalRunReport, TaskEvaluationResult


def estimate_pass_at_k(n: int, c: int, k: int) -> float:
    """Computes unbiased estimator for pass@k metric (Chen et al., Codex 2021).

    Mathematical formula:
        pass@k = 1 - binom(n - c, k) / binom(n, k)
               = 1 - prod_{i=1}^k (n - c - i + 1) / (n - i + 1)

    Args:
        n: Total number of generated code samples.
        c: Number of samples that passed all evaluation tests.
        k: Sample subset evaluation budget.

    Returns:
        float: Estimated pass@k probability in [0.0, 1.0].

    Raises:
        ValueError: If n < k, k < 1, or c is not in [0, n].
    """
    if k < 1:
        raise ValueError(f"k={k} must be >= 1")
    if n < k:
        raise ValueError(f"Sample count n={n} must be >= k={k}")
    if not (0 <= c <= n):
        raise ValueError(f"Correct count c={c} must be between 0 and n={n}")
    if c == 0:
        return 0.0
    if n - c < k:
        return 1.0

    prod = 1.0
    for i in range(1, k + 1):
        prod *= (n - c - i + 1) / (n - i + 1)

    return float(max(0.0, min(1.0, 1.0 - prod)))


def compute_pass_at_k_metrics(
    task_results: list[bool] | list[TaskEvaluationResult],
    k_values: list[int] | None = None,
) -> dict[str, float]:
    """Evaluates pass@k metrics for a list of task evaluation samples.

    Args:
        task_results: List of boolean pass/fail indicators or TaskEvaluationResult instances.
        k_values: List of k values to evaluate (defaults to [1, 5]).

    Returns:
        dict[str, float]: Dictionary mapping 'pass@{k}' to estimated pass@k float score.

    Raises:
        ValueError: If sample count n is less than any requested k in k_values.
    """
    if k_values is None:
        k_values = [1, 5]

    n = len(task_results)
    c = 0
    for item in task_results:
        if isinstance(item, bool):
            if item:
                c += 1
        elif isinstance(item, TaskEvaluationResult):
            if item.passed:
                c += 1
        elif hasattr(item, "passed"):
            if item.passed:
                c += 1
        else:
            if bool(item):
                c += 1

    metrics: dict[str, float] = {}
    for k in k_values:
        metrics[f"pass@{k}"] = estimate_pass_at_k(n, c, k)
    return metrics


def compute_confidence_interval(
    scores: list[float],
    confidence: float = 0.95,
) -> tuple[float, float]:
    """Computes standard error and normal confidence intervals for benchmark scores.

    Args:
        scores: List of numerical evaluation scores or metrics.
        confidence: Confidence level in range (0, 1), default 0.95.

    Returns:
        tuple[float, float]: (lower_bound, upper_bound) of the confidence interval.

    Raises:
        ValueError: If confidence is not in the open interval (0, 1).
    """
    if not (0.0 < confidence < 1.0):
        raise ValueError(f"Confidence level must be between 0 and 1, got {confidence}")
    if not scores:
        return (0.0, 0.0)
    n = len(scores)
    if n == 1:
        val = float(scores[0])
        return (val, val)

    mean = statistics.mean(scores)
    stdev = statistics.stdev(scores)
    if stdev == 0.0:
        return (float(mean), float(mean))

    se = stdev / math.sqrt(n)
    z = statistics.NormalDist().inv_cdf((1.0 + confidence) / 2.0)
    margin = z * se
    return (float(mean - margin), float(mean + margin))


class MetricsAggregator:
    """Aggregates benchmark evaluations into comprehensive metrics and reports."""

    @staticmethod
    def aggregate_run(
        run_id: str,
        model_name: str,
        evaluations: list[TaskEvaluationResult],
        k_values: list[int] | None = None,
    ) -> EvalRunReport:
        """Groups evaluations by task_id and aggregates run-level benchmark metrics.

        Args:
            run_id: Unique benchmark run identifier.
            model_name: Identifier of the evaluated model.
            evaluations: List of individual sample evaluation outcomes.
            k_values: k values to estimate (defaults to [1, 5]).

        Returns:
            EvalRunReport: Validated Pydantic summary report for the run.
        """
        if k_values is None:
            k_values = [1, 5]

        total_samples = len(evaluations)
        if total_samples == 0:
            return EvalRunReport(
                run_id=run_id,
                model_name=model_name,
                tasks_evaluated=0,
                pass_at_1=0.0,
                pass_at_5=0.0,
                mean_score=0.0,
                total_samples=0,
                pass_rate=0.0,
                results=[],
            )

        task_groups: dict[str, list[TaskEvaluationResult]] = {}
        for eval_res in evaluations:
            task_groups.setdefault(eval_res.task_id, []).append(eval_res)

        total_passed = sum(1 for e in evaluations if e.passed)
        pass_rate = total_passed / total_samples

        total_score = sum(e.rubric.composite_score for e in evaluations)
        mean_score = total_score / total_samples

        pass_k_means: dict[int, float] = {}
        for k in k_values:
            task_estimates: list[float] = []
            for task_samples in task_groups.values():
                n_task = len(task_samples)
                c_task = sum(1 for e in task_samples if e.passed)
                if n_task >= k:
                    task_estimates.append(estimate_pass_at_k(n_task, c_task, k))
            if task_estimates:
                pass_k_means[k] = sum(task_estimates) / len(task_estimates)
            else:
                pass_k_means[k] = 0.0

        return EvalRunReport(
            run_id=run_id,
            model_name=model_name,
            tasks_evaluated=len(task_groups),
            pass_at_1=pass_k_means.get(1, 0.0),
            pass_at_5=pass_k_means.get(5, 0.0),
            mean_score=round(mean_score, 2),
            total_samples=total_samples,
            pass_rate=pass_rate,
            results=evaluations,
        )

    @staticmethod
    def compute_confidence_interval(
        scores: list[float],
        confidence: float = 0.95,
    ) -> tuple[float, float]:
        """Computes standard error and normal confidence intervals for scores."""
        return compute_confidence_interval(scores, confidence=confidence)
