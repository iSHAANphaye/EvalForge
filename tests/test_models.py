"""Unit tests for EvalForge Pydantic v2 domain models and schema validation."""

import pytest
from pydantic import ValidationError

from evalforge.core.constants import ErrorTypeEnum
from evalforge.models.schemas import (
    ASTAuditReport,
    EvalRunReport,
    ExecutionResult,
    RubricScore,
    TaskEvaluationResult,
    TaskSpec,
)


def test_task_spec_defaults_and_validation():
    """Verify TaskSpec creation and validation."""
    task = TaskSpec(
        task_id="EF-PY-001",
        title="LRU Cache with TTL",
        language="python",
        prompt="Implement an LRU Cache with TTL support.",
        starter_code="class LRUCache:\n    pass\n",
        visible_tests="def test_basic(): pass",
        hidden_tests="def test_scale(): pass",
    )
    assert task.task_id == "EF-PY-001"
    assert task.title == "LRU Cache with TTL"
    assert task.time_limit_sec == 2.0
    assert task.memory_limit_mb == 256
    assert task.rubric_rules == {}

    # Required fields missing
    with pytest.raises(ValidationError):
        TaskSpec(task_id="EF-PY-001")


def test_execution_result_defaults_and_serialization():
    """Verify ExecutionResult defaults and JSON serialization roundtrip."""
    result = ExecutionResult(
        stdout="All tests passed",
        stderr="",
        exit_code=0,
        duration_ms=124.5,
        memory_peak_kb=32768,
        oom_killed=False,
        timed_out=False,
        error_type=ErrorTypeEnum.NONE,
    )
    assert result.exit_code == 0
    assert result.error_type == ErrorTypeEnum.NONE

    # Serialization roundtrip
    dumped = result.model_dump()
    assert dumped["exit_code"] == 0
    assert dumped["error_type"] == "NONE"

    json_str = result.model_dump_json()
    restored = ExecutionResult.model_validate_json(json_str)
    assert restored.duration_ms == 124.5
    assert restored.error_type == ErrorTypeEnum.NONE


def test_ast_audit_report():
    """Verify ASTAuditReport default values and properties."""
    report = ASTAuditReport(
        passed=True,
        score=20.0,
        violations=[],
        literal_decision_density=0.05,
        cyclomatic_complexity=4,
    )
    assert report.passed is True
    assert report.score == 20.0
    assert len(report.violations) == 0

    with pytest.raises(ValidationError):
        ASTAuditReport(score=25.0)  # Max allowed is 20.0


def test_rubric_score_bounds_and_composite_calculation():
    """Verify 4-axis bounds and composite calculation."""
    # Valid instance
    rubric = RubricScore(
        functional_score=35.0,
        edge_scale_score=25.0,
        anti_cheat_score=20.0,
        code_hygiene_score=8.5,
    )
    composite = rubric.calculate_composite()
    assert composite == 88.5
    assert rubric.composite_score == 88.5

    # Bounds validation
    with pytest.raises(ValidationError):
        RubricScore(functional_score=45.0)  # Max 40.0

    with pytest.raises(ValidationError):
        RubricScore(edge_scale_score=35.0)  # Max 30.0

    with pytest.raises(ValidationError):
        RubricScore(anti_cheat_score=25.0)  # Max 20.0

    with pytest.raises(ValidationError):
        RubricScore(code_hygiene_score=15.0)  # Max 10.0


def test_rubric_score_cheat_detected_zeros_composite():
    """Verify that cheat detection forces composite score to 0.0."""
    rubric = RubricScore.compute(
        functional_score=40.0,
        edge_scale_score=30.0,
        anti_cheat_score=0.0,
        code_hygiene_score=10.0,
        cheat_detected=True,
    )
    assert rubric.composite_score == 0.0
    assert rubric.cheat_detected is True


def test_task_evaluation_result_and_eval_run_report():
    """Verify nested aggregation in TaskEvaluationResult and EvalRunReport."""
    rubric = RubricScore.compute(
        functional_score=40.0,
        edge_scale_score=30.0,
        anti_cheat_score=20.0,
        code_hygiene_score=10.0,
    )
    execution = ExecutionResult(
        stdout="PASS",
        exit_code=0,
        duration_ms=50.0,
    )
    task_eval = TaskEvaluationResult(
        task_id="EF-PY-001",
        model_name="test-model",
        rubric=rubric,
        execution=execution,
        passed=True,
    )
    assert task_eval.passed is True
    assert task_eval.rubric.composite_score == 100.0

    report = EvalRunReport(
        run_id="run-1234",
        model_name="test-model",
        tasks_evaluated=1,
        pass_at_1=1.0,
        pass_at_5=1.0,
        mean_score=100.0,
        results=[task_eval],
    )
    assert report.tasks_evaluated == 1
    assert len(report.results) == 1

    # Roundtrip JSON serialization
    json_data = report.model_dump_json()
    loaded = EvalRunReport.model_validate_json(json_data)
    assert loaded.run_id == "run-1234"
    assert loaded.results[0].task_id == "EF-PY-001"
