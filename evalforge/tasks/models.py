"""Domain models and rubric configuration schemas for EvalForge benchmark tasks."""

from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

from evalforge.models.schemas import TaskSpec


class TaskRubricConfig(BaseModel):
    """Configuration for custom rubric weights, bounds, and AST anti-cheat constraints."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    banned_imports: list[str] = Field(
        default_factory=list,
        description="List of forbidden module or package imports",
    )
    max_cyclomatic_complexity: int = Field(
        default=25,
        ge=1,
        description="Maximum cyclomatic complexity ceiling before penalties",
    )
    max_lines: int = Field(
        default=200,
        ge=1,
        description="Maximum lines of code ceiling",
    )
    timeout_sec: float = Field(
        default=2.0,
        gt=0.0,
        description="Execution timeout in seconds",
    )
    memory_limit_mb: int = Field(
        default=256,
        ge=16,
        description="Container memory ceiling in MB",
    )
    require_algorithmic_control: bool = Field(
        default=True,
        description="Whether algorithmic branching/looping is strictly required",
    )
    disallowed_modules: list[str] = Field(
        default_factory=list,
        description="Alias for banned_imports",
    )

    @model_validator(mode="before")
    @classmethod
    def _sync_rubric_fields(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Sync banned_imports and disallowed_modules
            if "disallowed_modules" in data and "banned_imports" not in data:
                data["banned_imports"] = data["disallowed_modules"]
            elif "banned_imports" in data and "disallowed_modules" not in data:
                data["disallowed_modules"] = data["banned_imports"]
            # Sync timeout aliases
            if "timeout_seconds" in data and "timeout_sec" not in data:
                data["timeout_sec"] = data["timeout_seconds"]
            elif "time_limit_sec" in data and "timeout_sec" not in data:
                data["timeout_sec"] = data["time_limit_sec"]
        return data


# Clean alias for rubric rules
RubricRules = TaskRubricConfig


class TaskMetadata(BaseModel):
    """Descriptive metadata and categorization for benchmark tasks."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    task_id: str = Field(
        validation_alias=AliasChoices("task_id", "id"),
        description="Unique task identifier, e.g. 'EF-PY-001'",
    )
    title: str = Field(description="Human-readable title of the benchmark task")
    language: str = Field(default="python", description="Programming language ('python' or 'cpp')")
    difficulty: str = Field(
        default="medium",
        description="Difficulty tier ('easy', 'medium', 'hard')",
    )
    category: str = Field(
        default="algorithmic",
        description="Category ('algorithmic', 'systems', 'concurrency', 'data_structures')",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Categorization and topic tags",
    )
    slug: str | None = Field(default=None, description="URL-safe task slug")

    @field_validator("language", mode="before")
    @classmethod
    def _validate_language(cls, v: str) -> str:
        lang = str(v).strip().lower()
        if lang in ("c++", "cpp"):
            return "cpp"
        if lang == "python":
            return "python"
        raise ValueError(f"Unsupported language '{v}'. Must be 'python' or 'cpp'.")

    @field_validator("difficulty", mode="before")
    @classmethod
    def _validate_difficulty(cls, v: str) -> str:
        diff = str(v).strip().lower()
        valid = {"easy", "medium", "hard"}
        if diff not in valid:
            raise ValueError(f"Invalid difficulty '{v}'. Must be one of {valid}.")
        return diff

    @field_validator("category", mode="before")
    @classmethod
    def _validate_category(cls, v: str) -> str:
        cat = str(v).strip().lower()
        valid = {"algorithmic", "systems", "concurrency", "data_structures"}
        if cat not in valid:
            raise ValueError(f"Invalid category '{v}'. Must be one of {valid}.")
        return cat


class TestCase(BaseModel):
    """Specification of an individual test case within a benchmark suite."""

    __test__ = False  # Prevent pytest from collecting this model as a test suite

    name: str = Field(default="", description="Test case name or identifier")
    code: str = Field(default="", description="Source code for the test")
    description: str | None = Field(default=None, description="Optional docstring or explanation")


__all__ = [
    "TaskRubricConfig",
    "RubricRules",
    "TaskMetadata",
    "TaskSpec",
    "TestCase",
]
