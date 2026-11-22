"""JSONL streaming event logger for EvalForge evaluation runs and telemetry."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from evalforge.core.config import get_settings
from evalforge.core.exceptions import StorageError
from evalforge.core.logging import get_logger
from evalforge.models.schemas import TaskEvaluationResult

logger = get_logger("storage.jsonl_logger")


class JSONLEventLogger:
    """Thread-safe and async-safe append-only streaming JSONL audit logger."""

    def __init__(self, log_dir: str | Path | None = None, filename: str = "evalforge_events.jsonl") -> None:
        if log_dir is not None:
            self.log_dir = Path(log_dir)
        else:
            self.log_dir = Path(get_settings().audit_log_dir)

        self.filename = filename
        self.log_path = self.log_dir / self.filename
        self._lock = asyncio.Lock()
        self._ensure_dir()

    def _ensure_dir(self) -> None:
        """Ensure the target log directory exists."""
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
        except Exception as exc:
            logger.error(f"Failed to create audit log directory '{self.log_dir}': {exc}")

    async def log_event(
        self,
        event_type: str,
        data: dict[str, Any] | None = None,
        run_id: str | None = None,
        task_id: str | None = None,
        model_name: str | None = None,
    ) -> dict[str, Any]:
        """Record an arbitrary telemetry event to the JSONL log stream."""
        event: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event_type": event_type,
        }
        if run_id is not None:
            event["run_id"] = run_id
        if task_id is not None:
            event["task_id"] = task_id
        if model_name is not None:
            event["model_name"] = model_name

        if data:
            for k, v in data.items():
                if k not in event:
                    event[k] = v

        serialized = json.dumps(event, default=str)
        async with self._lock:
            try:
                # Run file write in executor or direct async append
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(serialized + "\n")
                    f.flush()
            except Exception as exc:
                raise StorageError(message=f"Failed to write event to JSONL '{self.log_path}': {exc}") from exc

        return event

    async def log_task_evaluation(
        self,
        evaluation: TaskEvaluationResult | dict[str, Any],
        run_id: str,
        sample_index: int = 0,
    ) -> dict[str, Any]:
        """Record a completed TASK_EVALUATION_COMPLETED audit event conforming to ARCHITECTURE.md §3.2."""
        if isinstance(evaluation, TaskEvaluationResult):
            task_id = evaluation.task_id
            model_name = evaluation.model_name
            ast_data = {
                "passed": evaluation.rubric.anti_cheat_score >= 10.0 and not evaluation.rubric.cheat_detected,
                "score": evaluation.rubric.anti_cheat_score,
                "cheat_detected": evaluation.rubric.cheat_detected,
                "violations": evaluation.rubric.details.get("violations", []),
                "cyclomatic_complexity": evaluation.rubric.details.get("cyclomatic_complexity", 0),
            }
            exec_data = {
                "exit_code": evaluation.execution.exit_code,
                "duration_ms": evaluation.execution.duration_ms,
                "memory_peak_kb": evaluation.execution.memory_peak_kb,
                "timed_out": evaluation.execution.timed_out,
                "oom_killed": evaluation.execution.oom_killed,
                "error_type": str(evaluation.execution.error_type),
                "error_message": evaluation.execution.error_message,
            }
            rubric_breakdown = {
                "functional": evaluation.rubric.functional_score,
                "edge_cases": evaluation.rubric.edge_scale_score,
                "anti_cheat": evaluation.rubric.anti_cheat_score,
                "hygiene": evaluation.rubric.code_hygiene_score,
                "composite": evaluation.rubric.composite_score,
                "passed": evaluation.passed,
                "cheat_detected": evaluation.rubric.cheat_detected,
            }
        else:
            task_id = evaluation.get("task_id", "")
            model_name = evaluation.get("model_name", "")
            sample_index = evaluation.get("sample_index", sample_index)
            ast_data = evaluation.get("ast_audit", {})
            exec_data = evaluation.get("execution", {})
            rubric_breakdown = evaluation.get("rubric", evaluation.get("rubric_breakdown", {}))

        event: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event_type": "TASK_EVALUATION_COMPLETED",
            "run_id": run_id,
            "task_id": task_id,
            "model_name": model_name,
            "sample_index": sample_index,
            "ast_audit": ast_data,
            "execution": exec_data,
            "rubric_breakdown": rubric_breakdown,
        }

        serialized = json.dumps(event, default=str)
        async with self._lock:
            try:
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(serialized + "\n")
                    f.flush()
            except Exception as exc:
                raise StorageError(message=f"Failed to stream task evaluation to '{self.log_path}': {exc}") from exc

        return event

    def read_events(
        self,
        run_id: str | None = None,
        event_type: str | None = None,
        task_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Synchronously read and filter events from the JSONL log file."""
        if not self.log_path.exists():
            return []

        results: list[dict[str, Any]] = []
        try:
            with open(self.log_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                        if run_id and record.get("run_id") != run_id:
                            continue
                        if event_type and record.get("event_type") != event_type:
                            continue
                        if task_id and record.get("task_id") != task_id:
                            continue
                        results.append(record)
                    except json.JSONDecodeError:
                        continue
        except Exception as exc:
            raise StorageError(message=f"Failed to read JSONL events from '{self.log_path}': {exc}") from exc

        return results


__all__ = ["JSONLEventLogger"]
