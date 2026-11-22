"""Domain exception hierarchy for EvalForge."""

from typing import Any


class EvalForgeError(Exception):
    """Base exception for all EvalForge errors."""

    def __init__(self, message: str = "An EvalForge error occurred.") -> None:
        super().__init__(message)
        self.message = message


class SandboxError(EvalForgeError):
    """Base exception for Docker sandbox and container management failures."""

    def __init__(self, message: str = "A sandbox error occurred.") -> None:
        super().__init__(message)


class SandboxTimeoutError(SandboxError, TimeoutError):
    """Raised when acquiring a sandbox container from the pool times out."""

    def __init__(
        self,
        message: str = "Timed out waiting for warm sandbox container.",
        timeout_sec: float | None = None,
    ) -> None:
        self.timeout_sec = timeout_sec
        super().__init__(message)


class ExecutionTimeoutError(SandboxError):
    """Raised when container execution exceeds the timeout deadline."""

    def __init__(self, timeout_sec: float, message: str | None = None) -> None:
        self.timeout_sec = timeout_sec
        formatted = message or f"Execution exceeded maximum timeout of {timeout_sec:.2f}s."
        super().__init__(formatted)


class MemoryExhaustionError(SandboxError):
    """Raised when candidate code is terminated due to OOM (Out of Memory)."""

    def __init__(self, limit_mb: int, message: str | None = None) -> None:
        self.limit_mb = limit_mb
        formatted = message or f"Execution terminated by OOM killer (limit: {limit_mb}MB)."
        super().__init__(formatted)


class ForkBombError(SandboxError):
    """Raised when candidate code violates PID limits or triggers fork bomb behavior."""

    def __init__(self, pid_limit: int, message: str | None = None) -> None:
        self.pid_limit = pid_limit
        formatted = message or f"Process exceeded PID limit ceiling ({pid_limit})."
        super().__init__(formatted)


class CheatDetectedError(EvalForgeError):
    """Raised when static AST analysis or runtime checks detect anti-cheat violations."""

    def __init__(
        self,
        message: str,
        rule_violated: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.rule_violated = rule_violated
        self.details = details or {}


class TaskNotFoundError(EvalForgeError, ValueError):
    """Raised when a benchmark task ID cannot be found in the task registry or files are missing/malformed."""

    def __init__(self, task_id: str = "", message: str | None = None) -> None:
        self.task_id = task_id
        if message:
            formatted = message
        elif task_id and not (" " in task_id or "\n" in task_id):
            formatted = f"Task '{task_id}' not found in registry."
        else:
            formatted = task_id or "Task not found."
        super().__init__(formatted)


class PatchApplicationError(EvalForgeError):
    """Raised when candidate solution code cannot be written or applied into the harness."""

    def __init__(self, message: str = "Failed to apply candidate code patch.") -> None:
        super().__init__(message)


class DatabaseError(EvalForgeError):
    """Raised when an operation against the SQLite database fails."""

    def __init__(self, message: str = "A database operation failed.") -> None:
        super().__init__(message)


class StorageError(DatabaseError):
    """Raised when persistence, retrieval, or logging operations fail."""

    def __init__(self, message: str = "A storage operation failed.") -> None:
        super().__init__(message)

