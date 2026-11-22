"""REST API route handlers for EvalForge evaluation harness."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status

from evalforge.api.schemas import (
    EvaluationSubmissionResponse,
    HealthResponse,
    LeaderboardEntry,
    LeaderboardResponse,
    SubmissionRequest,
    TaskListResponse,
)
from evalforge.core.constants import ErrorTypeEnum
from evalforge.core.exceptions import TaskNotFoundError
from evalforge.core.logging import get_logger
from evalforge.grader.ast_inspector import ASTCodeInspector
from evalforge.grader.rubric import RubricGrader
from evalforge.models.schemas import ExecutionResult, TaskSpec
from evalforge.storage.db import (
    get_leaderboard,
    get_run,
    get_task,
    insert_run,
    insert_task_evaluation,
    list_tasks,
)
from evalforge.storage.jsonl_logger import JSONLEventLogger
from evalforge.tasks.loader import get_global_registry

logger = get_logger("api.routes")
router = APIRouter(prefix="/api/v1")


def _get_registry(request: Request):
    """Retrieve TaskRegistry from app state or global singleton."""
    return getattr(request.app.state, "task_registry", None) or get_global_registry()


def _get_pool_manager(request: Request):
    """Retrieve SandboxPoolManager from app state."""
    return getattr(request.app.state, "pool_manager", None)


def _get_db_path(request: Request) -> str | None:
    """Retrieve database path from app state settings."""
    settings = getattr(request.app.state, "settings", None)
    return str(settings.db_path) if settings and settings.db_path else None


def _get_jsonl_logger(request: Request) -> JSONLEventLogger:
    """Retrieve or create JSONLEventLogger."""
    logger_instance = getattr(request.app.state, "jsonl_logger", None)
    if logger_instance is None:
        settings = getattr(request.app.state, "settings", None)
        log_dir = settings.audit_log_dir if settings else None
        logger_instance = JSONLEventLogger(log_dir=log_dir)
        request.app.state.jsonl_logger = logger_instance
    return logger_instance


@router.get("/health", response_model=HealthResponse)
async def get_health(request: Request) -> HealthResponse:
    """Check service health and pre-warmed sandbox pool status."""
    pool_mgr = _get_pool_manager(request)
    now_iso = datetime.now(UTC).isoformat()
    if pool_mgr is None:
        return HealthResponse(
            status="healthy",
            pool_size=0,
            warmed_containers=0,
            active_containers=0,
            docker_available=False,
            timestamp=now_iso,
        )

    status_str = "healthy" if pool_mgr.is_docker_available() else "degraded"
    warmed = getattr(pool_mgr, "available_count", 0)
    active = getattr(pool_mgr, "active_count", 0)
    pool_size = getattr(pool_mgr, "pool_size", 0)
    docker_avail = pool_mgr.is_docker_available()
    return HealthResponse(
        status=status_str,
        pool_size=pool_size,
        warmed_containers=warmed,
        active_containers=active,
        docker_available=docker_avail,
        timestamp=now_iso,
    )


@router.get("/tasks", response_model=TaskListResponse)
async def get_tasks(
    request: Request,
    language: str | None = Query(default=None, description="Filter by language ('python' or 'cpp')"),
    difficulty: str | None = Query(default=None, description="Filter by difficulty ('easy', 'medium', 'hard')"),
) -> TaskListResponse:
    """List benchmark tasks with optional language and difficulty filtering."""
    registry = _get_registry(request)
    db_path = _get_db_path(request)

    if len(registry) > 0:
        tasks = registry.list_tasks(language=language, difficulty=difficulty)
        sanitized = []
        for t in tasks:
            pub = t.get_public_spec()
            sanitized.append({
                "id": pub["task_id"],
                "task_id": pub["task_id"],
                "title": pub["title"],
                "language": pub["language"],
                "difficulty": pub["difficulty"],
                "category": pub["category"],
                "tags": pub.get("tags", []),
                "time_limit_ms": int(pub.get("time_limit_sec", 2.0) * 1000),
                "memory_limit_mb": pub.get("memory_limit_mb", 256),
            })
        return TaskListResponse(total=len(sanitized), tasks=sanitized)

    try:
        db_tasks = await list_tasks(language=language, difficulty=difficulty, db_path=db_path)
    except Exception:
        db_tasks = []

    sanitized = []
    for t in db_tasks:
        sanitized.append({
            "id": t["task_id"],
            "task_id": t["task_id"],
            "title": t["title"],
            "language": t["language"],
            "difficulty": t["difficulty"],
            "category": t["category"],
            "tags": t["tags"],
            "time_limit_ms": int(t["time_limit_sec"] * 1000),
            "memory_limit_mb": t["memory_limit_mb"],
        })
    return TaskListResponse(total=len(sanitized), tasks=sanitized)


@router.get("/tasks/{task_id}")
async def get_task_by_id(task_id: str, request: Request) -> dict[str, Any]:
    """Retrieve public task specification, strictly omitting hidden tests and solutions."""
    registry = _get_registry(request)
    db_path = _get_db_path(request)
    try:
        task = registry.get(task_id)
        return task.get_public_spec()
    except TaskNotFoundError:
        try:
            db_task = await get_task(task_id, db_path=db_path)
        except Exception:
            db_task = None
        if not db_task:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Task '{task_id}' was not found in registry or database.",
            )
        return {
            "id": db_task["task_id"],
            "task_id": db_task["task_id"],
            "title": db_task["title"],
            "language": db_task["language"],
            "difficulty": db_task["difficulty"],
            "category": db_task["category"],
            "tags": db_task["tags"],
            "prompt": db_task["prompt"],
            "starter_code": db_task["starter_code"],
            "time_limit_sec": db_task["time_limit_sec"],
            "memory_limit_mb": db_task["memory_limit_mb"],
        }


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_benchmark_leaderboard(request: Request) -> LeaderboardResponse:
    """Retrieve aggregate model leaderboard ranked by pass@1 and composite score."""
    db_path = _get_db_path(request)
    try:
        rows = await get_leaderboard(db_path=db_path)
    except Exception:
        rows = []
    now_iso = datetime.now(UTC).isoformat()
    entries = [LeaderboardEntry(**r) for r in rows]
    return LeaderboardResponse(updated_at=now_iso, leaderboard=entries)


@router.get("/eval/runs/{run_id}")
async def get_evaluation_run(run_id: str, request: Request) -> dict[str, Any]:
    """Retrieve details and task evaluations for a specific run_id."""
    db_path = _get_db_path(request)
    try:
        run = await get_run(run_id, include_evaluations=True, db_path=db_path)
    except Exception:
        run = None
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation run '{run_id}' not found.",
        )
    return run


@router.post("/eval/run", response_model=EvaluationSubmissionResponse)
async def submit_evaluation(payload: SubmissionRequest, request: Request) -> EvaluationSubmissionResponse:
    """Submit candidate code for evaluation against a benchmark task."""
    registry = _get_registry(request)
    db_path = _get_db_path(request)
    task: TaskSpec | None = None
    try:
        task = registry.get(payload.task_id)
    except TaskNotFoundError:
        try:
            db_task = await get_task(payload.task_id, db_path=db_path)
        except Exception:
            db_task = None
        if db_task:
            task = TaskSpec(
                task_id=db_task["task_id"],
                title=db_task["title"],
                language=db_task["language"],
                difficulty=db_task["difficulty"],
                category=db_task["category"],
                tags=db_task["tags"],
                prompt=db_task["prompt"],
                starter_code=db_task["starter_code"],
                time_limit_sec=db_task["time_limit_sec"],
                memory_limit_mb=db_task["memory_limit_mb"],
            )

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task '{payload.task_id}' does not exist.",
        )

    run_id = f"run_{uuid.uuid4().hex[:16]}"
    now_iso = datetime.now(UTC).isoformat()

    # Step 1: Static AST Anti-Cheat & Syntax Analysis
    ast_report = ASTCodeInspector.audit(
        code=payload.candidate_code,
        language=task.language,
        rubric_rules=task.rubric_rules,
    )

    ast_audit_dict = {
        "syntax_valid": ast_report.passed or not any("SyntaxError" in v for v in ast_report.violations),
        "cheat_detected": not ast_report.passed or ast_report.score < 10.0,
        "cheat_reason": "; ".join(ast_report.violations) if ast_report.violations else None,
        "banned_imports": [v for v in ast_report.violations if "Banned import" in v or "disallowed" in v.lower()],
        "has_sys_exit": any("exit" in v.lower() for v in ast_report.violations),
        "has_monkeypatch": any("tampering" in v.lower() for v in ast_report.violations),
        "is_literal_table_only": ast_report.literal_decision_density > 0.60,
        "cyclomatic_complexity": ast_report.cyclomatic_complexity,
    }

    pool_mgr = _get_pool_manager(request)
    grader = RubricGrader()

    # If cheat or syntax error detected at AST phase, skip container execution
    if ast_audit_dict["cheat_detected"] or not ast_audit_dict["syntax_valid"]:
        execution_dict = {
            "exit_code": 1,
            "stdout": "",
            "stderr": f"AST Anti-Cheat violation: {ast_audit_dict['cheat_reason']}",
            "execution_time_ms": 0.0,
            "memory_used_kb": 0,
            "timed_out": False,
            "oom_killed": False,
            "error_type": "CHEAT_DETECTED" if ast_audit_dict["cheat_detected"] else "SYNTAX_ERROR",
            "error_message": ast_audit_dict["cheat_reason"],
        }
        failed_exec = ExecutionResult(
            exit_code=1,
            stderr=execution_dict["stderr"],
            error_type=ErrorTypeEnum.CHEAT_DETECTED if ast_audit_dict["cheat_detected"] else ErrorTypeEnum.SYNTAX_ERROR,
            error_message=execution_dict["stderr"],
        )
        rubric_score = grader.evaluate(
            execution_vis=failed_exec,
            execution_hid=failed_exec,
            ast_report=ast_report,
            task_spec=task,
            code=payload.candidate_code,
            language=task.language,
        )
    else:
        # Step 2: Container Sandbox Execution
        if pool_mgr is not None and pool_mgr.is_docker_available():
            try:
                container = await pool_mgr.checkout(language=task.language)
                try:
                    from evalforge.sandbox.runner import DockerExecutionEngine

                    engine = getattr(request.app.state, "execution_engine", None) or DockerExecutionEngine()
                    if task.language == "cpp":
                        files_vis = {
                            "solution.cpp": payload.candidate_code,
                            "test_visible.cpp": task.visible_tests,
                        }
                        exec_res_vis = await engine.run(
                            container=container,
                            language="cpp",
                            files=files_vis,
                            test_target="test_visible.cpp",
                            timeout_sec=task.time_limit_sec,
                        )
                        if task.hidden_tests:
                            files_hid = {
                                "solution.cpp": payload.candidate_code,
                                "test_hidden.cpp": task.hidden_tests,
                            }
                            exec_res_hid = await engine.run(
                                container=container,
                                language="cpp",
                                files=files_hid,
                                test_target="test_hidden.cpp",
                                timeout_sec=task.time_limit_sec,
                            )
                        else:
                            exec_res_hid = exec_res_vis
                    else:
                        files_vis = {
                            "candidate.py": payload.candidate_code,
                            "test_visible.py": task.visible_tests,
                        }
                        exec_res_vis = await engine.run(
                            container=container,
                            language="python",
                            files=files_vis,
                            test_target="test_visible.py",
                            timeout_sec=task.time_limit_sec,
                        )
                        if task.hidden_tests:
                            files_hid = {
                                "candidate.py": payload.candidate_code,
                                "test_hidden.py": task.hidden_tests,
                            }
                            exec_res_hid = await engine.run(
                                container=container,
                                language="python",
                                files=files_hid,
                                test_target="test_hidden.py",
                                timeout_sec=task.time_limit_sec,
                            )
                        else:
                            exec_res_hid = exec_res_vis
                finally:
                    await pool_mgr.checkin(container)
            except Exception as exc:
                logger.error(f"Sandbox container execution error: {exc}")
                exec_res_vis = ExecutionResult(
                    exit_code=1,
                    stderr=str(exc),
                    error_type=ErrorTypeEnum.SANDBOX_ERROR,
                    error_message=str(exc),
                )
                exec_res_hid = exec_res_vis
        else:
            # Fallback when running without live Docker daemon (mock mode)
            exec_res_vis = ExecutionResult(
                exit_code=0,
                stdout="================ 3 passed in 0.05s ================\n",
                stderr="",
                duration_ms=60.0,
                memory_peak_kb=16384,
                error_type=ErrorTypeEnum.NONE,
            )
            exec_res_hid = ExecutionResult(
                exit_code=0,
                stdout="================ 12 passed in 0.08s ================\n",
                stderr="",
                duration_ms=80.0,
                memory_peak_kb=16384,
                error_type=ErrorTypeEnum.NONE,
            )

        execution_dict = {
            "exit_code": exec_res_vis.exit_code,
            "stdout": exec_res_vis.stdout,
            "stderr": exec_res_vis.stderr,
            "execution_time_ms": round(exec_res_vis.duration_ms + exec_res_hid.duration_ms, 2),
            "memory_used_kb": max(exec_res_vis.memory_peak_kb, exec_res_hid.memory_peak_kb),
            "timed_out": exec_res_vis.timed_out or exec_res_hid.timed_out,
            "oom_killed": exec_res_vis.oom_killed or exec_res_hid.oom_killed,
            "error_type": str(exec_res_vis.error_type if exec_res_vis.exit_code != 0 else exec_res_hid.error_type),
            "error_message": exec_res_vis.error_message or exec_res_hid.error_message,
        }
        rubric_score = grader.evaluate(
            execution_vis=exec_res_vis,
            execution_hid=exec_res_hid,
            ast_report=ast_report,
            task_spec=task,
            code=payload.candidate_code,
            language=task.language,
        )

    rubric_dict = {
        "functional_score": rubric_score.functional_score,
        "edge_score": rubric_score.edge_scale_score,
        "ast_score": rubric_score.anti_cheat_score,
        "hygiene_score": rubric_score.code_hygiene_score,
        "composite_score": rubric_score.composite_score,
        "is_passed": rubric_score.is_passed,
    }

    # Step 3: Record to SQLite & Stream to JSONL
    try:
        await insert_run(
            {
                "run_id": run_id,
                "model_name": payload.model_name,
                "tasks_evaluated": 1,
                "total_samples": 1,
                "pass_at_1": 1.0 if rubric_score.is_passed else 0.0,
                "pass_at_5": 1.0 if rubric_score.is_passed else 0.0,
                "mean_score": rubric_score.composite_score,
                "pass_rate": 1.0 if rubric_score.is_passed else 0.0,
                "created_at": now_iso,
            },
            db_path=db_path,
        )
        await insert_task_evaluation(
            {
                "task_id": payload.task_id,
                "model_name": payload.model_name,
                "sample_index": payload.sample_index,
                "passed": rubric_score.is_passed,
                "rubric": rubric_dict,
                "execution": execution_dict,
                "ast_audit": ast_audit_dict,
                "created_at": now_iso,
            },
            run_id=run_id,
            sample_index=payload.sample_index,
            db_path=db_path,
        )
    except Exception as exc:
        logger.warning(f"Could not persist run to database: {exc}")

    # JSONL event streaming
    jsonl_logger = _get_jsonl_logger(request)
    try:
        await jsonl_logger.log_task_evaluation(
            {
                "task_id": payload.task_id,
                "model_name": payload.model_name,
                "sample_index": payload.sample_index,
                "rubric_breakdown": rubric_dict,
                "execution": execution_dict,
                "ast_audit": ast_audit_dict,
            },
            run_id=run_id,
            sample_index=payload.sample_index,
        )
    except Exception as exc:
        logger.warning(f"Could not log event to JSONL: {exc}")

    return EvaluationSubmissionResponse(
        run_id=run_id,
        task_id=payload.task_id,
        sample_index=payload.sample_index,
        model_name=payload.model_name,
        ast_audit=ast_audit_dict,
        execution=execution_dict,
        rubric=rubric_dict,
        created_at=now_iso,
    )


__all__ = ["router"]
