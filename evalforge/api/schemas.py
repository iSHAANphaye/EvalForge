"""Pydantic schemas for EvalForge REST API requests and responses."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SubmissionRequest(BaseModel):
    """Payload for submitting candidate code for evaluation against a benchmark task."""

    model_config = ConfigDict(extra="ignore")

    task_id: str = Field(..., description="Unique task identifier, e.g. 'EF-PY-001'")
    model_name: str = Field(default="candidate-model", description="Identifier of the model being evaluated")
    candidate_code: str = Field(..., description="Candidate source code string")
    sample_index: int = Field(default=0, ge=0, description="Sample index for pass@k evaluations")
    temperature: float = Field(default=0.0, ge=0.0, le=2.0, description="Sampling temperature metadata")


class EvaluationSubmissionResponse(BaseModel):
    """Response returned upon completing task evaluation."""

    run_id: str = Field(..., description="UUID or identifier of the evaluation run")
    task_id: str = Field(..., description="Task identifier evaluated")
    sample_index: int = Field(default=0, description="Sample index")
    model_name: str = Field(..., description="Evaluated model name")
    ast_audit: dict[str, Any] = Field(default_factory=dict, description="AST static analysis audit breakdown")
    execution: dict[str, Any] = Field(default_factory=dict, description="Raw container execution telemetry")
    rubric: dict[str, Any] = Field(default_factory=dict, description="4-axis rubric scoring breakdown")
    created_at: str = Field(..., description="ISO 8601 UTC timestamp")


class TaskSummary(BaseModel):
    """Public summary representation of a benchmark task."""

    id: str = Field(..., description="Task identifier")
    slug: str | None = Field(default=None, description="Task slug")
    language: str = Field(..., description="Programming language ('python' or 'cpp')")
    title: str = Field(..., description="Human-readable title")
    difficulty: str = Field(..., description="Difficulty tier")
    category: str = Field(default="algorithmic", description="Task category")
    time_limit_ms: int = Field(default=2000, description="Timeout in milliseconds")
    memory_limit_mb: int = Field(default=256, description="Memory limit in megabytes")
    tags: list[str] = Field(default_factory=list, description="Categorization tags")


class TaskListResponse(BaseModel):
    """Response containing list of available benchmark tasks."""

    total: int = Field(..., description="Total tasks matching filter")
    tasks: list[dict[str, Any]] = Field(default_factory=list, description="Task records")


class LeaderboardEntry(BaseModel):
    """Leaderboard entry for an evaluated model."""

    rank: int = Field(..., description="Leaderboard position")
    model_name: str = Field(..., description="Model identifier")
    total_tasks: int = Field(..., description="Distinct benchmark tasks evaluated")
    pass_at_1: float = Field(..., description="pass@1 accuracy percentage (0-100)")
    pass_at_5: float = Field(..., description="pass@5 accuracy percentage (0-100)")
    mean_composite_score: float = Field(..., description="Mean composite rubric score (0-100)")
    cheat_attempts_detected: int = Field(..., description="Total detected cheat attempts")


class LeaderboardResponse(BaseModel):
    """Response containing aggregate model benchmark leaderboard."""

    updated_at: str = Field(..., description="ISO 8601 UTC timestamp of report")
    leaderboard: list[LeaderboardEntry] = Field(default_factory=list, description="Ranked model leaderboard")


class HealthResponse(BaseModel):
    """Health check and pre-warmed sandbox pool status."""

    status: str = Field(..., description="Overall service status ('healthy', 'degraded', 'offline')")
    pool_size: int = Field(default=0, description="Target pre-warmed pool capacity")
    warmed_containers: int = Field(default=0, description="Number of currently warmed containers ready")
    active_containers: int = Field(default=0, description="Number of leased containers currently executing")
    docker_available: bool = Field(default=False, description="Whether Docker daemon connection is operational")
    timestamp: str = Field(..., description="ISO 8601 UTC timestamp")


__all__ = [
    "SubmissionRequest",
    "EvaluationSubmissionResponse",
    "TaskSummary",
    "TaskListResponse",
    "LeaderboardEntry",
    "LeaderboardResponse",
    "HealthResponse",
]
