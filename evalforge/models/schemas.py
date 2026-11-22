"""Pydantic v2 domain schemas for EvalForge benchmarks, execution, and rubrics."""

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from evalforge.core.constants import (
    DEFAULT_EXEC_TIMEOUT_SEC,
    DEFAULT_RAM_LIMIT_MB,
    MAX_POINTS_ANTI_CHEAT,
    MAX_POINTS_CODE_HYGIENE,
    MAX_POINTS_COMPOSITE,
    MAX_POINTS_EDGE_SCALE,
    MAX_POINTS_FUNCTIONAL,
    ErrorTypeEnum,
)


class TaskSpec(BaseModel):
    """Specification of a benchmark task including prompts and test suites."""

    task_id: str = Field(description="Unique task identifier, e.g. 'EF-PY-001'")
    title: str = Field(description="Human-readable title of the benchmark task")
    language: str = Field(default="python", description="Programming language ('python' or 'cpp')")
    prompt: str = Field(description="Problem formulation and docstring prompt for the model")
    starter_code: str = Field(default="", description="Function or class signatures provided to the model")
    visible_tests: str = Field(default="", description="Visible pytest / test harness code")
    hidden_tests: str = Field(default="", description="Hidden edge-case and scaling test suite")
    time_limit_sec: float = Field(
        default=DEFAULT_EXEC_TIMEOUT_SEC,
        gt=0.0,
        description="Execution timeout per test run in seconds",
    )
    memory_limit_mb: int = Field(
        default=DEFAULT_RAM_LIMIT_MB,
        ge=16,
        description="Container memory ceiling in MB",
    )
    rubric_rules: dict[str, Any] = Field(
        default_factory=dict,
        description="Task-specific constraints (e.g. banned modules, complexity limit)",
    )
    difficulty: str = Field(
        default="medium",
        description="Difficulty tier ('easy', 'medium', 'hard')",
    )
    category: str = Field(
        default="algorithmic",
        description="Task category ('algorithmic', 'systems', 'concurrency', 'data_structures')",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Categorization and topic tags",
    )
    canonical_solution: str = Field(
        default="",
        description="Canonical reference solution",
    )

    def get_public_spec(self) -> dict[str, Any]:
        """Return public task specification omitting hidden tests and canonical solution."""
        data = self.model_dump()
        data.pop("hidden_tests", None)
        data.pop("canonical_solution", None)
        return data


class ExecutionResult(BaseModel):
    """Raw container execution telemetry and exit state."""

    stdout: str = Field(default="", description="Captured standard output stream")
    stderr: str = Field(default="", description="Captured standard error stream")
    exit_code: int = Field(default=0, description="Process return code")
    duration_ms: float = Field(default=0.0, ge=0.0, description="Execution duration in milliseconds")
    memory_peak_kb: int = Field(default=0, ge=0, description="Peak memory consumption in KB")
    oom_killed: bool = Field(default=False, description="Whether process was killed by OOM killer")
    timed_out: bool = Field(default=False, description="Whether execution was terminated due to timeout")
    error_type: ErrorTypeEnum = Field(
        default=ErrorTypeEnum.NONE,
        description="Categorical failure classification",
    )
    error_message: str | None = Field(
        default=None,
        description="Detailed diagnostic or error message",
    )


class ASTAuditReport(BaseModel):
    """Static AST anti-cheat and structural inspection results."""

    passed: bool = Field(default=True, description="Whether the AST audit passed without critical violations")
    score: float = Field(
        default=MAX_POINTS_ANTI_CHEAT,
        ge=0.0,
        le=MAX_POINTS_ANTI_CHEAT,
        description="Anti-cheat score awarded (0 to 20)",
    )
    violations: list[str] = Field(
        default_factory=list,
        description="List of detected rule violations or banned patterns",
    )
    literal_decision_density: float = Field(
        default=0.0,
        ge=0.0,
        description="Ratio of literal return lookups relative to algorithmic control nodes",
    )
    cyclomatic_complexity: int = Field(
        default=0,
        ge=0,
        description="McCabe cyclomatic complexity score",
    )


class RubricScore(BaseModel):
    """Four-axis rubric score breakdown totaling up to 100 points."""

    functional_score: float = Field(
        default=0.0,
        ge=0.0,
        le=MAX_POINTS_FUNCTIONAL,
        description="Axis 1: Functional Correctness (0 to 40)",
    )
    edge_scale_score: float = Field(
        default=0.0,
        ge=0.0,
        le=MAX_POINTS_EDGE_SCALE,
        description="Axis 2: Edge-Case & Scale Robustness (0 to 30)",
    )
    anti_cheat_score: float = Field(
        default=0.0,
        ge=0.0,
        le=MAX_POINTS_ANTI_CHEAT,
        description="Axis 3: Anti-Cheat & AST Integrity (0 to 20)",
    )
    code_hygiene_score: float = Field(
        default=0.0,
        ge=0.0,
        le=MAX_POINTS_CODE_HYGIENE,
        description="Axis 4: Code Hygiene & Style (0 to 10)",
    )
    composite_score: float = Field(
        default=0.0,
        ge=0.0,
        le=MAX_POINTS_COMPOSITE,
        description="Total composite score (0 to 100)",
    )
    cheat_detected: bool = Field(
        default=False,
        description="Flag indicating whether cheating or test tampering was detected",
    )
    is_passed: bool = Field(
        default=False,
        description="Whether solution met passing criteria (composite >= 75, func == 40, no cheat)",
    )
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Granular evaluation breakdowns and axis telemetry",
    )

    @property
    def edge_score(self) -> float:
        """Alias for edge_scale_score."""
        return self.edge_scale_score

    @property
    def ast_score(self) -> float:
        """Alias for anti_cheat_score."""
        return self.anti_cheat_score

    @property
    def hygiene_score(self) -> float:
        """Alias for code_hygiene_score."""
        return self.code_hygiene_score

    def calculate_composite(self) -> float:
        """Calculate and update composite_score from individual axis scores."""
        if self.cheat_detected:
            self.composite_score = 0.0
        else:
            total = (
                self.functional_score
                + self.edge_scale_score
                + self.anti_cheat_score
                + self.code_hygiene_score
            )
            self.composite_score = round(min(max(total, 0.0), MAX_POINTS_COMPOSITE), 2)
        self.is_passed = (
            self.composite_score >= 75.0
            and self.functional_score == MAX_POINTS_FUNCTIONAL
            and not self.cheat_detected
        )
        return self.composite_score

    @classmethod
    def compute(
        cls,
        functional_score: float = 0.0,
        edge_scale_score: float = 0.0,
        anti_cheat_score: float = 0.0,
        code_hygiene_score: float = 0.0,
        cheat_detected: bool = False,
        details: dict[str, Any] | None = None,
        is_passed: bool | None = None,
    ) -> "RubricScore":
        """Factory method that calculates composite_score automatically."""
        instance = cls(
            functional_score=functional_score,
            edge_scale_score=edge_scale_score,
            anti_cheat_score=anti_cheat_score,
            code_hygiene_score=code_hygiene_score,
            composite_score=0.0,
            cheat_detected=cheat_detected,
            details=details or {},
        )
        instance.calculate_composite()
        if is_passed is not None:
            instance.is_passed = is_passed
        return instance


class TaskEvaluationResult(BaseModel):
    """Complete evaluation outcome for a single candidate sample on a task."""

    task_id: str = Field(description="Task evaluated")
    model_name: str = Field(description="Identifier of model under evaluation")
    rubric: RubricScore = Field(description="Evaluated 4-axis rubric scores")
    execution: ExecutionResult = Field(description="Container execution details")
    passed: bool = Field(default=False, description="Whether solution met passing criteria")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Timestamp of evaluation record",
    )


class EvalRunReport(BaseModel):
    """High-level summary report for an evaluation benchmark run."""

    run_id: str = Field(description="UUID of the benchmark run")
    model_name: str = Field(description="Model evaluated")
    tasks_evaluated: int = Field(default=0, ge=0, description="Total tasks evaluated in this run")
    pass_at_1: float = Field(default=0.0, ge=0.0, le=1.0, description="Unbiased pass@1 estimate")
    pass_at_5: float = Field(default=0.0, ge=0.0, le=1.0, description="Unbiased pass@5 estimate")
    mean_score: float = Field(default=0.0, ge=0.0, le=100.0, description="Mean composite rubric score")
    total_samples: int = Field(
        default=0,
        ge=0,
        description="Total evaluation samples across all tasks in this run",
    )
    pass_rate: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall pass rate across all evaluated samples",
    )
    results: list[TaskEvaluationResult] = Field(
        default_factory=list,
        description="Per-task evaluation outcomes",
    )
