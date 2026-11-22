"""Unit and integration tests for EvalForge SQLite persistence and JSONL streaming logger."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from evalforge.core.exceptions import StorageError
from evalforge.models.schemas import (
    EvalRunReport,
    ExecutionResult,
    RubricScore,
    TaskEvaluationResult,
    TaskSpec,
)
from evalforge.storage.db import (
    get_leaderboard,
    get_run,
    get_task,
    get_task_evaluations,
    init_db,
    insert_run,
    insert_task,
    insert_task_evaluation,
    list_runs,
    list_tasks,
)
from evalforge.storage.jsonl_logger import JSONLEventLogger


@pytest.fixture
async def temp_db(tmp_path: Path) -> Path:
    """Fixture providing an initialized SQLite database in a temporary directory."""
    db_file = tmp_path / "test_evalforge.db"
    await init_db(db_file)
    return db_file


@pytest.mark.asyncio
async def test_init_db_idempotent(tmp_path: Path):
    """Verify init_db can be called repeatedly without error."""
    db_file = tmp_path / "idempotent.db"
    await init_db(db_file)
    await init_db(db_file)
    assert db_file.exists()


@pytest.mark.asyncio
async def test_task_crud_operations(temp_db: Path):
    """Verify task insertion, retrieval, and filtered listing."""
    task1 = TaskSpec(
        task_id="EF-PY-001",
        title="LRU Cache with TTL",
        language="python",
        difficulty="medium",
        category="concurrency",
        tags=["caching", "ttl"],
        prompt="Implement TTL cache",
        starter_code="class TTLCache: pass",
        time_limit_sec=2.0,
        memory_limit_mb=256,
    )
    task2 = TaskSpec(
        task_id="EF-CPP-001",
        title="Lock-Free Ring Buffer",
        language="cpp",
        difficulty="hard",
        category="concurrency",
        tags=["lock-free", "atomics"],
        prompt="Implement SPSC ring buffer",
        starter_code="template <typename T> class RingBuffer {};",
        time_limit_sec=1.5,
        memory_limit_mb=128,
    )

    await insert_task(task1, temp_db)
    await insert_task(task2, temp_db)

    # Retrieval
    t1 = await get_task("EF-PY-001", temp_db)
    assert t1 is not None
    assert t1["task_id"] == "EF-PY-001"
    assert t1["title"] == "LRU Cache with TTL"
    assert t1["language"] == "python"
    assert "caching" in t1["tags"]

    assert await get_task("NON-EXISTENT", temp_db) is None

    # Filtering
    py_tasks = await list_tasks(language="python", db_path=temp_db)
    assert len(py_tasks) == 1
    assert py_tasks[0]["task_id"] == "EF-PY-001"

    hard_tasks = await list_tasks(difficulty="hard", db_path=temp_db)
    assert len(hard_tasks) == 1
    assert hard_tasks[0]["task_id"] == "EF-CPP-001"

    all_tasks = await list_tasks(db_path=temp_db)
    assert len(all_tasks) == 2


@pytest.mark.asyncio
async def test_eval_run_and_evaluations_persistence(temp_db: Path):
    """Verify inserting an EvalRunReport with attached TaskEvaluationResults."""
    eval_result1 = TaskEvaluationResult(
        task_id="EF-PY-001",
        model_name="claude-3-7-sonnet",
        rubric=RubricScore.compute(
            functional_score=40.0,
            edge_scale_score=30.0,
            anti_cheat_score=20.0,
            code_hygiene_score=10.0,
        ),
        execution=ExecutionResult(
            exit_code=0,
            duration_ms=120.5,
            memory_peak_kb=15400,
        ),
        passed=True,
    )
    eval_result2 = TaskEvaluationResult(
        task_id="EF-PY-002",
        model_name="claude-3-7-sonnet",
        rubric=RubricScore.compute(
            functional_score=40.0,
            edge_scale_score=20.0,
            anti_cheat_score=20.0,
            code_hygiene_score=8.0,
        ),
        execution=ExecutionResult(
            exit_code=0,
            duration_ms=180.2,
            memory_peak_kb=16200,
        ),
        passed=True,
    )

    run_report = EvalRunReport(
        run_id="run_test_001",
        model_name="claude-3-7-sonnet",
        tasks_evaluated=2,
        total_samples=2,
        pass_at_1=1.0,
        pass_at_5=1.0,
        mean_score=94.0,
        pass_rate=1.0,
        results=[eval_result1, eval_result2],
    )

    inserted_id = await insert_run(run_report, temp_db)
    assert inserted_id == "run_test_001"

    # Query run
    run_record = await get_run("run_test_001", include_evaluations=True, db_path=temp_db)
    assert run_record is not None
    assert run_record["run_id"] == "run_test_001"
    assert run_record["model_name"] == "claude-3-7-sonnet"
    assert len(run_record["evaluations"]) == 2
    assert run_record["evaluations"][0]["task_id"] == "EF-PY-001"
    assert run_record["evaluations"][0]["passed"] is True
    assert run_record["evaluations"][0]["composite_score"] == 100.0

    # Query evaluations directly
    evals = await get_task_evaluations("run_test_001", temp_db)
    assert len(evals) == 2

    # Query list_runs
    runs = await list_runs(limit=10, db_path=temp_db)
    assert len(runs) >= 1
    assert runs[0]["run_id"] == "run_test_001"


@pytest.mark.asyncio
async def test_leaderboard_aggregation(temp_db: Path):
    """Verify leaderboard computes pass rates, cheat detections, and ranks models correctly."""
    # Model A: 2 passed, 0 cheats
    await insert_run(
        {
            "run_id": "run_model_a",
            "model_name": "model_alpha",
            "tasks_evaluated": 2,
            "total_samples": 2,
            "pass_at_1": 1.0,
            "pass_at_5": 1.0,
            "mean_score": 95.0,
        },
        temp_db,
    )
    await insert_task_evaluation(
        {
            "task_id": "EF-PY-001",
            "model_name": "model_alpha",
            "passed": True,
            "rubric": {"composite_score": 95.0, "cheat_detected": False},
            "execution": {"duration_ms": 100.0},
        },
        run_id="run_model_a",
        sample_index=0,
        db_path=temp_db,
    )
    await insert_task_evaluation(
        {
            "task_id": "EF-PY-002",
            "model_name": "model_alpha",
            "passed": True,
            "rubric": {"composite_score": 90.0, "cheat_detected": False},
            "execution": {"duration_ms": 110.0},
        },
        run_id="run_model_a",
        sample_index=1,
        db_path=temp_db,
    )

    # Model B: 1 passed, 1 cheated
    await insert_run(
        {
            "run_id": "run_model_b",
            "model_name": "model_beta",
            "tasks_evaluated": 2,
            "total_samples": 2,
            "pass_at_1": 0.5,
            "pass_at_5": 0.5,
            "mean_score": 45.0,
        },
        temp_db,
    )
    await insert_task_evaluation(
        {
            "task_id": "EF-PY-001",
            "model_name": "model_beta",
            "passed": True,
            "rubric": {"composite_score": 90.0, "cheat_detected": False},
            "execution": {"duration_ms": 120.0},
        },
        run_id="run_model_b",
        sample_index=0,
        db_path=temp_db,
    )
    await insert_task_evaluation(
        {
            "task_id": "EF-PY-002",
            "model_name": "model_beta",
            "passed": False,
            "rubric": {"composite_score": 0.0, "cheat_detected": True},
            "execution": {"duration_ms": 50.0},
        },
        run_id="run_model_b",
        sample_index=1,
        db_path=temp_db,
    )

    leaderboard = await get_leaderboard(temp_db)
    assert len(leaderboard) == 2

    # Model Alpha should be rank 1
    assert leaderboard[0]["rank"] == 1
    assert leaderboard[0]["model_name"] == "model_alpha"
    assert leaderboard[0]["total_tasks"] == 2
    assert leaderboard[0]["pass_at_1"] == 100.0
    assert leaderboard[0]["mean_composite_score"] == 92.5
    assert leaderboard[0]["cheat_attempts_detected"] == 0

    # Model Beta should be rank 2
    assert leaderboard[1]["rank"] == 2
    assert leaderboard[1]["model_name"] == "model_beta"
    assert leaderboard[1]["pass_at_1"] == 50.0
    assert leaderboard[1]["cheat_attempts_detected"] == 1


@pytest.mark.asyncio
async def test_foreign_key_constraint_enforcement(temp_db: Path):
    """Verify inserting task evaluation with invalid run_id raises StorageError."""
    with pytest.raises(StorageError):
        await insert_task_evaluation(
            {
                "task_id": "EF-PY-001",
                "model_name": "test_model",
                "passed": False,
                "rubric": {"composite_score": 0.0},
                "execution": {},
            },
            run_id="non_existent_run_id",
            db_path=temp_db,
        )


@pytest.mark.asyncio
async def test_jsonl_logger_events_and_filtering(tmp_path: Path):
    """Verify JSONLEventLogger writes, flushes, and filters JSONL lines."""
    log_dir = tmp_path / "logs"
    logger = JSONLEventLogger(log_dir=log_dir, filename="audit_test.jsonl")

    # Log generic event
    await logger.log_event(
        event_type="RUN_STARTED",
        data={"model": "qwen2.5-coder-7b", "total_tasks": 30},
        run_id="run_001",
    )

    # Log task evaluation
    eval_result = TaskEvaluationResult(
        task_id="EF-PY-001",
        model_name="qwen2.5-coder-7b",
        rubric=RubricScore.compute(
            functional_score=40.0,
            edge_scale_score=30.0,
            anti_cheat_score=20.0,
            code_hygiene_score=10.0,
        ),
        execution=ExecutionResult(
            exit_code=0,
            duration_ms=150.0,
            memory_peak_kb=12000,
        ),
        passed=True,
    )
    await logger.log_task_evaluation(eval_result, run_id="run_001", sample_index=0)

    # Log another event for run_002
    await logger.log_event(
        event_type="RUN_STARTED",
        data={"model": "gpt-4o"},
        run_id="run_002",
    )

    # Read events
    all_events = logger.read_events()
    assert len(all_events) == 3

    # Filter by run_id
    run_001_events = logger.read_events(run_id="run_001")
    assert len(run_001_events) == 2

    # Filter by event_type
    eval_events = logger.read_events(event_type="TASK_EVALUATION_COMPLETED")
    assert len(eval_events) == 1
    assert eval_events[0]["task_id"] == "EF-PY-001"
    assert eval_events[0]["rubric_breakdown"]["composite"] == 100.0


@pytest.mark.asyncio
async def test_jsonl_logger_concurrent_writes(tmp_path: Path):
    """Verify concurrent async calls to log_event do not corrupt the JSONL file."""
    log_dir = tmp_path / "concurrent_logs"
    logger = JSONLEventLogger(log_dir=log_dir)

    async def worker(idx: int):
        for i in range(25):
            await logger.log_event(
                event_type="TICK",
                data={"worker": idx, "seq": i},
                run_id=f"run_worker_{idx}",
            )

    tasks = [worker(w) for w in range(4)]
    await asyncio.gather(*tasks)

    events = logger.read_events(event_type="TICK")
    assert len(events) == 100
