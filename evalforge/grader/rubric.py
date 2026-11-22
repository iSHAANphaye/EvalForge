"""Four-axis rubric evaluation engine for EvalForge benchmarks.

Implements the multi-axis formula:
Composite Score = S_func (40%) + S_edge (30%) + S_ast (20%) + S_hygiene (10%)
"""

import math
from typing import Any

from evalforge.core.constants import (
    MAX_POINTS_ANTI_CHEAT,
    MAX_POINTS_CODE_HYGIENE,
    MAX_POINTS_COMPOSITE,
    MAX_POINTS_EDGE_SCALE,
    MAX_POINTS_FUNCTIONAL,
    WEIGHT_ANTI_CHEAT,
    WEIGHT_CODE_HYGIENE,
    WEIGHT_EDGE_SCALE,
    WEIGHT_FUNCTIONAL,
    ErrorTypeEnum,
)
from evalforge.grader.functional import (
    extract_test_counts_from_execution,
    parse_gtest_json_report,
    parse_pytest_json_report,
)
from evalforge.models.schemas import ASTAuditReport, ExecutionResult, RubricScore, TaskSpec


class RubricGrader:
    """Four-axis rubric evaluation engine for grading benchmark candidate code."""

    def __init__(
        self,
        weight_func: float = WEIGHT_FUNCTIONAL,
        weight_edge: float = WEIGHT_EDGE_SCALE,
        weight_ast: float = WEIGHT_ANTI_CHEAT,
        weight_hygiene: float = WEIGHT_CODE_HYGIENE,
        max_func: float = MAX_POINTS_FUNCTIONAL,
        max_edge: float = MAX_POINTS_EDGE_SCALE,
        max_ast: float = MAX_POINTS_ANTI_CHEAT,
        max_hygiene: float = MAX_POINTS_CODE_HYGIENE,
        passing_composite_threshold: float = 75.0,
        cheat_hard_cap: float = 30.0,
    ) -> None:
        """Initialize rubric grader weights and thresholds.

        Args:
            weight_func: Functional correctness weight (default 0.40).
            weight_edge: Edge-case & scale robustness weight (default 0.30).
            weight_ast: Anti-cheat & AST integrity weight (default 0.20).
            weight_hygiene: Code hygiene & style weight (default 0.10).
            max_func: Maximum functional points (default 40.0).
            max_edge: Maximum edge-case points (default 30.0).
            max_ast: Maximum anti-cheat points (default 20.0).
            max_hygiene: Maximum code hygiene points (default 10.0).
            passing_composite_threshold: Minimum composite score for pass (default 75.0).
            cheat_hard_cap: Maximum composite score if cheat is detected (default 30.0).
        """
        self.weight_func = weight_func
        self.weight_edge = weight_edge
        self.weight_ast = weight_ast
        self.weight_hygiene = weight_hygiene

        self.max_func = max_func
        self.max_edge = max_edge
        self.max_ast = max_ast
        self.max_hygiene = max_hygiene

        self.passing_composite_threshold = passing_composite_threshold
        self.cheat_hard_cap = cheat_hard_cap

    def _resolve_counts(
        self,
        execution: ExecutionResult,
        passed_val: Any,
        total_val: Any,
        report_val: Any,
        language: str = "python",
        fallback_total: int = 0,
    ) -> tuple[int, int]:
        """Resolve passed and total test counts from explicit args, reports, or execution output."""
        if passed_val is not None and total_val is not None:
            return max(0, int(passed_val)), max(0, int(total_val))

        if report_val is not None:
            if language.lower() in ("cpp", "c++", "cxx"):
                p, t, _ = parse_gtest_json_report(report_val)
            else:
                p, t, _ = parse_pytest_json_report(report_val)
            if t > 0:
                return p, t

        p, t, _ = extract_test_counts_from_execution(
            execution, language=language, fallback_total=fallback_total
        )
        return p, t

    def evaluate(
        self,
        execution_vis: ExecutionResult,
        execution_hid: ExecutionResult,
        ast_report: ASTAuditReport,
        **kwargs: Any,
    ) -> RubricScore:
        """Evaluate candidate execution and AST inspection across four rubric axes.

        Formula:
            Composite Score = S_func (40%) + S_edge (30%) + S_ast (20%) + S_hygiene (10%)

        Axes:
            1. Functional Correctness (40%): S_func = 40.0 * (P_vis / N_vis)
               (0 if N_vis == 0 or execution error).
            2. Edge-Case & Scale Robustness (30%): S_edge = 30.0 * (P_hid / N_hid)
               (0 if timed out, OOM, runtime exception, or N_hid == 0).
            3. Anti-Cheat & AST Integrity (20%): ASTAuditReport.score (0 to 20).
               If ASTAuditReport.passed is False (cheat detected or banned import),
               S_ast = 0.0 and Composite Score is hard-capped at 30.0 max with cheat_detected=True.
            4. Code Hygiene & Style (10%): Base 10.0 points.
               Deduct 5.0 points if cyclomatic complexity > 15.
               Deduct 5.0 points if code exceeds 200 lines without justification or contains syntax/lint warnings.
               Minimum 0.0 points.

        Pass Condition:
            is_passed is True iff composite_score >= 75.0 AND functional_score == 40.0 AND cheat_detected is False.

        Args:
            execution_vis: Container execution result for visible test suite.
            execution_hid: Container execution result for hidden test suite.
            ast_report: Static AST anti-cheat audit report.
            **kwargs: Optional parameters:
                - passed_vis / p_vis: int
                - total_vis / n_vis: int
                - passed_hid / p_hid: int
                - total_hid / n_hid: int
                - report_vis / vis_report: dict | str
                - report_hid / hid_report: dict | str
                - code / source_code: str
                - line_count: int
                - cyclomatic_complexity: int
                - max_cyclomatic_complexity: int (default 15)
                - max_lines: int (default 200)
                - has_lint_warnings / lint_warnings: bool
                - language: str ('python' or 'cpp')
                - task_spec: TaskSpec

        Returns:
            RubricScore: Calculated 4-axis scores, composite score, and pass status.
        """
        language = kwargs.get("language", "python")
        task_spec: TaskSpec | None = kwargs.get("task_spec")
        if task_spec is not None and not kwargs.get("language"):
            language = task_spec.language

        # ---------------------------------------------------------------------
        # Axis 1: Functional Correctness (40%)
        # ---------------------------------------------------------------------
        passed_vis_arg = kwargs.get("passed_vis", kwargs.get("p_vis", kwargs.get("vis_passed")))
        total_vis_arg = kwargs.get("total_vis", kwargs.get("n_vis", kwargs.get("vis_total")))
        report_vis_arg = kwargs.get("report_vis", kwargs.get("vis_report"))

        p_vis, n_vis = self._resolve_counts(
            execution=execution_vis,
            passed_val=passed_vis_arg,
            total_val=total_vis_arg,
            report_val=report_vis_arg,
            language=language,
        )

        vis_exec_error = (
            execution_vis.timed_out
            or execution_vis.oom_killed
            or execution_vis.error_type
            in (
                ErrorTypeEnum.TIMEOUT,
                ErrorTypeEnum.OOM,
                ErrorTypeEnum.SYNTAX_ERROR,
                ErrorTypeEnum.SANDBOX_ERROR,
                ErrorTypeEnum.PATCH_APPLICATION_ERROR,
            )
            or (
                execution_vis.error_type == ErrorTypeEnum.RUNTIME_EXCEPTION
                and p_vis == 0
                and execution_vis.exit_code != 0
            )
        )

        if vis_exec_error or n_vis == 0:
            functional_score = 0.0
        else:
            ratio = min(max(p_vis / n_vis, 0.0), 1.0)
            functional_score = round(self.max_func * ratio, 2)

        # ---------------------------------------------------------------------
        # Axis 2: Edge-Case & Scale Robustness (30%)
        # ---------------------------------------------------------------------
        passed_hid_arg = kwargs.get("passed_hid", kwargs.get("p_hid", kwargs.get("hid_passed")))
        total_hid_arg = kwargs.get("total_hid", kwargs.get("n_hid", kwargs.get("hid_total")))
        report_hid_arg = kwargs.get("report_hid", kwargs.get("hid_report"))

        p_hid, n_hid = self._resolve_counts(
            execution=execution_hid,
            passed_val=passed_hid_arg,
            total_val=total_hid_arg,
            report_val=report_hid_arg,
            language=language,
        )

        hid_zero_condition = (
            execution_hid.timed_out
            or execution_hid.oom_killed
            or execution_hid.error_type in (ErrorTypeEnum.TIMEOUT, ErrorTypeEnum.OOM)
            or execution_hid.error_type
            in (
                ErrorTypeEnum.SYNTAX_ERROR,
                ErrorTypeEnum.SANDBOX_ERROR,
                ErrorTypeEnum.PATCH_APPLICATION_ERROR,
            )
            or (
                execution_hid.error_type == ErrorTypeEnum.RUNTIME_EXCEPTION
                and (p_hid == 0 or kwargs.get("runtime_exception", False))
            )
            or n_hid == 0
        )

        if hid_zero_condition:
            edge_scale_score = 0.0
        else:
            ratio = min(max(p_hid / n_hid, 0.0), 1.0)
            edge_scale_score = round(self.max_edge * ratio, 2)

        # ---------------------------------------------------------------------
        # Axis 3: Anti-Cheat & AST Integrity (20%)
        # ---------------------------------------------------------------------
        cheat_detected = (not ast_report.passed) or bool(kwargs.get("cheat_detected", False))
        if cheat_detected:
            anti_cheat_score = 0.0
        else:
            anti_cheat_score = round(min(max(float(ast_report.score), 0.0), self.max_ast), 2)

        # ---------------------------------------------------------------------
        # Axis 4: Code Hygiene & Style (10%)
        # ---------------------------------------------------------------------
        base_hygiene = self.max_hygiene
        deductions: list[str] = []

        complexity = kwargs.get("cyclomatic_complexity", ast_report.cyclomatic_complexity)
        max_complexity = kwargs.get("max_cyclomatic_complexity", 15)
        if complexity > max_complexity:
            deductions.append(f"High cyclomatic complexity ({complexity} > {max_complexity}): -5.0")
            base_hygiene -= 5.0

        code = kwargs.get("code") or kwargs.get("source_code")
        if code is not None:
            line_count = len(code.strip().splitlines())
        else:
            line_count = int(kwargs.get("line_count", 0))

        max_lines = kwargs.get("max_lines", 200)
        has_lint_warnings = bool(
            kwargs.get("has_lint_warnings")
            or kwargs.get("lint_warnings")
            or kwargs.get("syntax_warnings")
            or kwargs.get("warnings")
        )

        if line_count > max_lines or has_lint_warnings:
            reason_parts: list[str] = []
            if line_count > max_lines:
                reason_parts.append(f"lines ({line_count} > {max_lines})")
            if has_lint_warnings:
                reason_parts.append("syntax/lint warnings detected")
            deductions.append(f"Excessive {' and '.join(reason_parts)}: -5.0")
            base_hygiene -= 5.0

        code_hygiene_score = round(max(0.0, min(self.max_hygiene, base_hygiene)), 2)

        # ---------------------------------------------------------------------
        # Composite Score Calculation & Anti-Cheat Hard Cap
        # ---------------------------------------------------------------------
        raw_composite = functional_score + edge_scale_score + anti_cheat_score + code_hygiene_score

        if cheat_detected:
            composite_score = round(min(raw_composite, self.cheat_hard_cap), 2)
        else:
            composite_score = round(min(max(raw_composite, 0.0), MAX_POINTS_COMPOSITE), 2)

        # ---------------------------------------------------------------------
        # Pass Condition: composite >= 75.0 AND func == 40.0 AND not cheat
        # ---------------------------------------------------------------------
        is_passed = (
            composite_score >= self.passing_composite_threshold
            and math.isclose(functional_score, self.max_func, abs_tol=1e-5)
            and not cheat_detected
        )

        details: dict[str, Any] = {
            "passed_vis": p_vis,
            "total_vis": n_vis,
            "passed_hid": p_hid,
            "total_hid": n_hid,
            "functional_score": functional_score,
            "edge_scale_score": edge_scale_score,
            "anti_cheat_score": anti_cheat_score,
            "code_hygiene_score": code_hygiene_score,
            "composite_score": composite_score,
            "cheat_detected": cheat_detected,
            "is_passed": is_passed,
            "cyclomatic_complexity": complexity,
            "line_count": line_count,
            "deductions": deductions,
            "violations": list(ast_report.violations),
        }

        return RubricScore(
            functional_score=functional_score,
            edge_scale_score=edge_scale_score,
            anti_cheat_score=anti_cheat_score,
            code_hygiene_score=code_hygiene_score,
            composite_score=composite_score,
            cheat_detected=cheat_detected,
            is_passed=is_passed,
            details=details,
        )

    def evaluate_task(
        self,
        task_spec: TaskSpec,
        execution_vis: ExecutionResult,
        execution_hid: ExecutionResult,
        ast_report: ASTAuditReport,
        **kwargs: Any,
    ) -> RubricScore:
        """Evaluate submission against a specific TaskSpec.

        Extracts task-specific rubric rules (e.g. max_cyclomatic_complexity,
        language) and evaluates rubric.

        Args:
            task_spec: Task specification containing rubric rules and requirements.
            execution_vis: Execution result of visible tests.
            execution_hid: Execution result of hidden tests.
            ast_report: AST inspection audit report.
            **kwargs: Extra overrides for evaluation.

        Returns:
            RubricScore: Calculated 4-axis scores, composite score, and pass status.
        """
        rules = task_spec.rubric_rules or {}
        task_kwargs = dict(kwargs)
        if "max_cyclomatic_complexity" not in task_kwargs and "max_cyclomatic_complexity" in rules:
            task_kwargs["max_cyclomatic_complexity"] = rules["max_cyclomatic_complexity"]
        if "max_lines" not in task_kwargs and "max_lines" in rules:
            task_kwargs["max_lines"] = rules["max_lines"]
        if "language" not in task_kwargs:
            task_kwargs["language"] = task_spec.language

        return self.evaluate(
            execution_vis=execution_vis,
            execution_hid=execution_hid,
            ast_report=ast_report,
            task_spec=task_spec,
            **task_kwargs,
        )
