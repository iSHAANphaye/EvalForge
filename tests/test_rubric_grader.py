"""Unit and integration test suite for 4-axis RubricGrader and report parsers."""

import json

from evalforge.core.constants import ErrorTypeEnum
from evalforge.grader.functional import parse_gtest_json_report, parse_pytest_json_report
from evalforge.grader.rubric import RubricGrader
from evalforge.models.schemas import ASTAuditReport, ExecutionResult, TaskSpec


def test_full_score_submission() -> None:
    """Verify that a perfect submission scores 100/100 and is marked is_passed=True."""
    grader = RubricGrader()

    exec_vis = ExecutionResult(
        stdout="==== 10 passed in 0.05s ====",
        exit_code=0,
        error_type=ErrorTypeEnum.NONE,
    )
    exec_hid = ExecutionResult(
        stdout="==== 15 passed in 0.08s ====",
        exit_code=0,
        error_type=ErrorTypeEnum.NONE,
    )
    ast_rep = ASTAuditReport(
        passed=True,
        score=20.0,
        violations=[],
        cyclomatic_complexity=4,
    )

    clean_code = "def solution(x):\n    return x * 2\n"

    score = grader.evaluate(
        execution_vis=exec_vis,
        execution_hid=exec_hid,
        ast_report=ast_rep,
        passed_vis=10,
        total_vis=10,
        passed_hid=15,
        total_hid=15,
        code=clean_code,
    )

    assert score.functional_score == 40.0
    assert score.edge_scale_score == 30.0
    assert score.anti_cheat_score == 20.0
    assert score.code_hygiene_score == 10.0
    assert score.composite_score == 100.0
    assert score.is_passed is True
    assert score.cheat_detected is False
    assert len(score.details["deductions"]) == 0


def test_partial_functional_failure() -> None:
    """Verify partial functional failure (5/10 pass) yields 20/40 and fails pass condition."""
    grader = RubricGrader()

    exec_vis = ExecutionResult(
        stdout="5 passed, 5 failed",
        exit_code=1,
        error_type=ErrorTypeEnum.RUNTIME_EXCEPTION,
    )
    exec_hid = ExecutionResult(
        stdout="10 passed",
        exit_code=0,
        error_type=ErrorTypeEnum.NONE,
    )
    ast_rep = ASTAuditReport(
        passed=True,
        score=20.0,
        violations=[],
        cyclomatic_complexity=3,
    )

    score = grader.evaluate(
        execution_vis=exec_vis,
        execution_hid=exec_hid,
        ast_report=ast_rep,
        passed_vis=5,
        total_vis=10,
        passed_hid=10,
        total_hid=10,
    )

    assert score.functional_score == 20.0
    assert score.edge_scale_score == 30.0
    assert score.anti_cheat_score == 20.0
    assert score.code_hygiene_score == 10.0
    # Composite = 20 + 30 + 20 + 10 = 80.0
    assert score.composite_score == 80.0
    # Even though composite >= 75.0, visible functional score is 20 != 40 -> fails
    assert score.is_passed is False
    assert score.cheat_detected is False


def test_timeout_on_hidden_tests_zeros_edge_score() -> None:
    """Verify execution timeout during hidden tests awards 0/30 edge points."""
    grader = RubricGrader()

    exec_vis = ExecutionResult(
        stdout="10 passed",
        exit_code=0,
        error_type=ErrorTypeEnum.NONE,
    )
    exec_hid = ExecutionResult(
        stdout="",
        exit_code=124,
        timed_out=True,
        error_type=ErrorTypeEnum.TIMEOUT,
        error_message="Execution timed out after 2.0s",
    )
    ast_rep = ASTAuditReport(
        passed=True,
        score=20.0,
        violations=[],
        cyclomatic_complexity=2,
    )

    score = grader.evaluate(
        execution_vis=exec_vis,
        execution_hid=exec_hid,
        ast_report=ast_rep,
        passed_vis=10,
        total_vis=10,
        passed_hid=0,
        total_hid=10,
    )

    assert score.functional_score == 40.0
    assert score.edge_scale_score == 0.0
    assert score.anti_cheat_score == 20.0
    assert score.code_hygiene_score == 10.0
    assert score.composite_score == 70.0
    assert score.is_passed is False


def test_oom_on_hidden_tests_zeros_edge_score() -> None:
    """Verify OOM killed process during hidden tests awards 0/30 edge points."""
    grader = RubricGrader()

    exec_vis = ExecutionResult(
        stdout="10 passed",
        exit_code=0,
        error_type=ErrorTypeEnum.NONE,
    )
    exec_hid = ExecutionResult(
        stdout="",
        exit_code=137,
        oom_killed=True,
        error_type=ErrorTypeEnum.OOM,
        error_message="Killed by OOM",
    )
    ast_rep = ASTAuditReport(
        passed=True,
        score=20.0,
        violations=[],
        cyclomatic_complexity=3,
    )

    score = grader.evaluate(
        execution_vis=exec_vis,
        execution_hid=exec_hid,
        ast_report=ast_rep,
        passed_vis=10,
        total_vis=10,
        passed_hid=0,
        total_hid=10,
    )

    assert score.functional_score == 40.0
    assert score.edge_scale_score == 0.0
    assert score.composite_score == 70.0
    assert score.is_passed is False


def test_cheat_detected_in_ast_hard_caps_composite() -> None:
    """Verify that cheat detected in AST zeros AST score and hard-caps composite score at 30.0."""
    grader = RubricGrader()

    exec_vis = ExecutionResult(
        stdout="10 passed",
        exit_code=0,
        error_type=ErrorTypeEnum.NONE,
    )
    exec_hid = ExecutionResult(
        stdout="10 passed",
        exit_code=0,
        error_type=ErrorTypeEnum.NONE,
    )
    ast_rep = ASTAuditReport(
        passed=False,
        score=0.0,
        violations=["Banned module import: 'os'", "Dangerous builtin: 'eval'"],
        cyclomatic_complexity=2,
    )

    # Raw would be: 40 (func) + 30 (edge) + 0 (ast) + 10 (hygiene) = 80.0
    score = grader.evaluate(
        execution_vis=exec_vis,
        execution_hid=exec_hid,
        ast_report=ast_rep,
        passed_vis=10,
        total_vis=10,
        passed_hid=10,
        total_hid=10,
    )

    assert score.functional_score == 40.0
    assert score.edge_scale_score == 30.0
    assert score.anti_cheat_score == 0.0
    assert score.code_hygiene_score == 10.0
    assert score.composite_score == 30.0  # Hard capped!
    assert score.cheat_detected is True
    assert score.is_passed is False


def test_cheat_detected_with_lower_raw_total() -> None:
    """Verify that when raw total is below 30.0, capped score preserves the lower total."""
    grader = RubricGrader()

    exec_vis = ExecutionResult(
        stdout="2 passed, 8 failed",
        exit_code=1,
        error_type=ErrorTypeEnum.RUNTIME_EXCEPTION,
    )
    exec_hid = ExecutionResult(
        stdout="0 passed, 10 failed",
        exit_code=1,
        error_type=ErrorTypeEnum.RUNTIME_EXCEPTION,
    )
    ast_rep = ASTAuditReport(
        passed=False,
        score=0.0,
        violations=["Banned module import: 'socket'"],
        cyclomatic_complexity=2,
    )

    # Raw = 8.0 (func) + 0 (edge) + 0 (ast) + 10 (hygiene) = 18.0
    score = grader.evaluate(
        execution_vis=exec_vis,
        execution_hid=exec_hid,
        ast_report=ast_rep,
        passed_vis=2,
        total_vis=10,
        passed_hid=0,
        total_hid=10,
    )

    assert score.functional_score == 8.0
    assert score.edge_scale_score == 0.0
    assert score.anti_cheat_score == 0.0
    assert score.code_hygiene_score == 10.0
    assert score.composite_score == 18.0  # min(18.0, 30.0)
    assert score.cheat_detected is True
    assert score.is_passed is False


def test_code_hygiene_deductions_high_complexity() -> None:
    """Verify that cyclomatic complexity > 15 deducts 5.0 hygiene points."""
    grader = RubricGrader()

    exec_vis = ExecutionResult(stdout="10 passed", exit_code=0)
    exec_hid = ExecutionResult(stdout="10 passed", exit_code=0)
    ast_rep = ASTAuditReport(
        passed=True,
        score=20.0,
        violations=[],
        cyclomatic_complexity=18,  # > 15 threshold
    )

    score = grader.evaluate(
        execution_vis=exec_vis,
        execution_hid=exec_hid,
        ast_report=ast_rep,
        passed_vis=10,
        total_vis=10,
        passed_hid=10,
        total_hid=10,
    )

    assert score.code_hygiene_score == 5.0
    assert score.composite_score == 95.0
    assert score.is_passed is True
    assert any("cyclomatic complexity" in d.lower() for d in score.details["deductions"])


def test_code_hygiene_deductions_excessive_lines() -> None:
    """Verify that exceeding 200 lines deducts 5.0 hygiene points."""
    grader = RubricGrader()

    exec_vis = ExecutionResult(stdout="10 passed", exit_code=0)
    exec_hid = ExecutionResult(stdout="10 passed", exit_code=0)
    ast_rep = ASTAuditReport(
        passed=True,
        score=20.0,
        violations=[],
        cyclomatic_complexity=5,
    )

    long_code = "\n".join([f"x_{i} = {i}" for i in range(250)])

    score = grader.evaluate(
        execution_vis=exec_vis,
        execution_hid=exec_hid,
        ast_report=ast_rep,
        passed_vis=10,
        total_vis=10,
        passed_hid=10,
        total_hid=10,
        code=long_code,
    )

    assert score.code_hygiene_score == 5.0
    assert score.composite_score == 95.0
    assert score.is_passed is True
    assert any("lines" in d.lower() for d in score.details["deductions"])


def test_code_hygiene_deductions_complexity_and_lines_stack() -> None:
    """Verify that both complexity > 15 and lines > 200 stack to deduct 10.0 points (score 0)."""
    grader = RubricGrader()

    exec_vis = ExecutionResult(stdout="10 passed", exit_code=0)
    exec_hid = ExecutionResult(stdout="10 passed", exit_code=0)
    ast_rep = ASTAuditReport(
        passed=True,
        score=20.0,
        violations=[],
        cyclomatic_complexity=22,
    )

    long_code = "\n".join([f"x_{i} = {i}" for i in range(220)])

    score = grader.evaluate(
        execution_vis=exec_vis,
        execution_hid=exec_hid,
        ast_report=ast_rep,
        passed_vis=10,
        total_vis=10,
        passed_hid=10,
        total_hid=10,
        code=long_code,
    )

    assert score.code_hygiene_score == 0.0
    assert score.composite_score == 90.0
    assert score.is_passed is True
    assert len(score.details["deductions"]) == 2


def test_code_hygiene_lint_warnings_deduction() -> None:
    """Verify that lint warnings deduct 5.0 points from hygiene."""
    grader = RubricGrader()

    exec_vis = ExecutionResult(stdout="10 passed", exit_code=0)
    exec_hid = ExecutionResult(stdout="10 passed", exit_code=0)
    ast_rep = ASTAuditReport(
        passed=True,
        score=20.0,
        violations=[],
        cyclomatic_complexity=4,
    )

    score = grader.evaluate(
        execution_vis=exec_vis,
        execution_hid=exec_hid,
        ast_report=ast_rep,
        passed_vis=10,
        total_vis=10,
        passed_hid=10,
        total_hid=10,
        has_lint_warnings=True,
    )

    assert score.code_hygiene_score == 5.0
    assert score.composite_score == 95.0


def test_pass_condition_exact_75_threshold() -> None:
    """Verify pass condition boundary at exactly 75.0 points."""
    grader = RubricGrader()

    exec_vis = ExecutionResult(stdout="10 passed", exit_code=0)
    exec_hid = ExecutionResult(stdout="5 passed, 5 failed", exit_code=1)
    ast_rep = ASTAuditReport(
        passed=True,
        score=10.0,
        violations=[],
        cyclomatic_complexity=4,
    )

    # 40 (func) + 15 (edge) + 10 (ast) + 10 (hygiene) = 75.0 -> PASS
    score_75 = grader.evaluate(
        execution_vis=exec_vis,
        execution_hid=exec_hid,
        ast_report=ast_rep,
        passed_vis=10,
        total_vis=10,
        passed_hid=5,
        total_hid=10,
    )
    assert score_75.composite_score == 75.0
    assert score_75.is_passed is True

    # 40 (func) + 12 (edge) + 10 (ast) + 10 (hygiene) = 72.0 -> FAIL
    score_72 = grader.evaluate(
        execution_vis=exec_vis,
        execution_hid=exec_hid,
        ast_report=ast_rep,
        passed_vis=10,
        total_vis=10,
        passed_hid=4,
        total_hid=10,
    )
    assert score_72.composite_score == 72.0
    assert score_72.is_passed is False


def test_visible_execution_error_zeros_functional_score() -> None:
    """Verify syntax errors or crashes on visible tests result in 0 functional score."""
    grader = RubricGrader()

    exec_vis = ExecutionResult(
        stderr="SyntaxError: invalid syntax",
        exit_code=1,
        error_type=ErrorTypeEnum.SYNTAX_ERROR,
    )
    exec_hid = ExecutionResult(stdout="10 passed", exit_code=0)
    ast_rep = ASTAuditReport(passed=True, score=20.0, cyclomatic_complexity=2)

    score = grader.evaluate(
        execution_vis=exec_vis,
        execution_hid=exec_hid,
        ast_report=ast_rep,
        passed_vis=0,
        total_vis=5,
        passed_hid=10,
        total_hid=10,
    )
    assert score.functional_score == 0.0
    assert score.is_passed is False


def test_empty_test_suites_zero_axes() -> None:
    """Verify that zero visible tests or zero hidden tests award 0 points on respective axes."""
    grader = RubricGrader()

    exec_vis = ExecutionResult(exit_code=0)
    exec_hid = ExecutionResult(exit_code=0)
    ast_rep = ASTAuditReport(passed=True, score=20.0, cyclomatic_complexity=2)

    score = grader.evaluate(
        execution_vis=exec_vis,
        execution_hid=exec_hid,
        ast_report=ast_rep,
        passed_vis=0,
        total_vis=0,
        passed_hid=0,
        total_hid=0,
    )
    assert score.functional_score == 0.0
    assert score.edge_scale_score == 0.0


def test_parse_pytest_json_report_valid_dict() -> None:
    """Verify parsing a valid pytest-json-report summary dict."""
    report = {
        "summary": {"passed": 8, "failed": 2, "total": 10},
        "tests": [],
    }
    p, t, f = parse_pytest_json_report(report)
    assert p == 8
    assert t == 10
    assert f == 2


def test_parse_pytest_json_report_valid_json_string() -> None:
    """Verify parsing a valid pytest-json-report serialized string."""
    report_str = json.dumps({"summary": {"passed": 6, "failed": 0, "total": 6}})
    p, t, f = parse_pytest_json_report(report_str)
    assert p == 6
    assert t == 6
    assert f == 0


def test_parse_pytest_json_report_with_errors() -> None:
    """Verify pytest errors are counted into failed_tests."""
    report = {
        "summary": {"passed": 3, "failed": 1, "error": 1, "total": 5},
    }
    p, t, f = parse_pytest_json_report(report)
    assert p == 3
    assert t == 5
    assert f == 2


def test_parse_pytest_json_report_tests_array_fallback() -> None:
    """Verify fallback to counting test outcomes when summary dict is omitted."""
    report = {
        "tests": [
            {"nodeid": "t1", "outcome": "passed"},
            {"nodeid": "t2", "outcome": "passed"},
            {"nodeid": "t3", "outcome": "failed"},
            {"nodeid": "t4", "outcome": "error"},
        ]
    }
    p, t, f = parse_pytest_json_report(report)
    assert p == 2
    assert t == 4
    assert f == 2


def test_parse_pytest_json_report_malformed() -> None:
    """Verify graceful zero handling on malformed reports."""
    assert parse_pytest_json_report(None) == (0, 0, 0)
    assert parse_pytest_json_report("") == (0, 0, 0)
    assert parse_pytest_json_report("  ") == (0, 0, 0)
    assert parse_pytest_json_report("{invalid json") == (0, 0, 0)
    assert parse_pytest_json_report({}) == (0, 0, 0)
    assert parse_pytest_json_report("[]") == (0, 0, 0)


def test_parse_gtest_json_report_top_level() -> None:
    """Verify parsing GTest output with top-level tests and failures fields."""
    report = {
        "tests": 12,
        "failures": 2,
        "errors": 1,
        "disabled": 0,
    }
    p, t, f = parse_gtest_json_report(report)
    assert t == 12
    assert f == 3
    assert p == 9


def test_parse_gtest_json_report_testsuites_hierarchy() -> None:
    """Verify parsing GTest output aggregating across multiple testsuites."""
    report = {
        "testsuites": [
            {"name": "SuiteA", "tests": 4, "failures": 1},
            {"name": "SuiteB", "tests": 6, "failures": 0},
        ]
    }
    p, t, f = parse_gtest_json_report(report)
    assert t == 10
    assert f == 1
    assert p == 9


def test_parse_gtest_json_report_valid_json_string() -> None:
    """Verify parsing a serialized GTest JSON report string."""
    report_str = json.dumps({"testsuites": [{"tests": 5, "failures": 0}]})
    p, t, f = parse_gtest_json_report(report_str)
    assert p == 5
    assert t == 5
    assert f == 0


def test_parse_gtest_json_report_malformed() -> None:
    """Verify graceful zero handling on malformed GTest reports."""
    assert parse_gtest_json_report(None) == (0, 0, 0)
    assert parse_gtest_json_report("") == (0, 0, 0)
    assert parse_gtest_json_report("{corrupt: gtest") == (0, 0, 0)
    assert parse_gtest_json_report({}) == (0, 0, 0)
    assert parse_gtest_json_report(123) == (0, 0, 0)


def test_evaluate_task_with_task_spec_python() -> None:
    """Verify evaluate_task using TaskSpec and report dictionaries."""
    task = TaskSpec(
        task_id="EF-PY-002",
        title="Merge K Sorted Lists",
        language="python",
        prompt="Merge k sorted linked lists.",
        rubric_rules={"max_cyclomatic_complexity": 10},
    )

    report_vis = {"summary": {"passed": 4, "failed": 0, "total": 4}}
    report_hid = {"summary": {"passed": 12, "failed": 0, "total": 12}}

    exec_vis = ExecutionResult(exit_code=0)
    exec_hid = ExecutionResult(exit_code=0)
    ast_rep = ASTAuditReport(passed=True, score=20.0, cyclomatic_complexity=8)

    grader = RubricGrader()
    score = grader.evaluate_task(
        task_spec=task,
        execution_vis=exec_vis,
        execution_hid=exec_hid,
        ast_report=ast_rep,
        report_vis=report_vis,
        report_hid=report_hid,
    )

    assert score.functional_score == 40.0
    assert score.edge_scale_score == 30.0
    assert score.anti_cheat_score == 20.0
    assert score.code_hygiene_score == 10.0
    assert score.composite_score == 100.0
    assert score.is_passed is True


def test_evaluate_task_custom_complexity_override() -> None:
    """Verify that task rubric_rules custom max_cyclomatic_complexity is respected."""
    task = TaskSpec(
        task_id="EF-PY-003",
        title="Parser with Higher Complexity Allowance",
        language="python",
        prompt="Parse expression tree.",
        rubric_rules={"max_cyclomatic_complexity": 25},
    )

    exec_vis = ExecutionResult(stdout="5 passed", exit_code=0)
    exec_hid = ExecutionResult(stdout="5 passed", exit_code=0)
    # Complexity 20 exceeds default 15, but is under custom task limit 25
    ast_rep = ASTAuditReport(passed=True, score=20.0, cyclomatic_complexity=20)

    grader = RubricGrader()
    score = grader.evaluate_task(
        task_spec=task,
        execution_vis=exec_vis,
        execution_hid=exec_hid,
        ast_report=ast_rep,
        passed_vis=5,
        total_vis=5,
        passed_hid=5,
        total_hid=5,
    )

    assert score.code_hygiene_score == 10.0
    assert score.composite_score == 100.0
    assert score.is_passed is True
    assert len(score.details["deductions"]) == 0
