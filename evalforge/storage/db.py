"""SQLite persistence layer for EvalForge using aiosqlite."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite

from evalforge.core.config import get_settings
from evalforge.core.exceptions import StorageError
from evalforge.core.logging import get_logger
from evalforge.models.schemas import EvalRunReport, TaskEvaluationResult, TaskSpec

logger = get_logger("storage.db")

DDL_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS tasks (
        task_id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        language TEXT NOT NULL,
        difficulty TEXT NOT NULL,
        category TEXT NOT NULL,
        tags TEXT NOT NULL DEFAULT '[]',
        prompt TEXT NOT NULL DEFAULT '',
        starter_code TEXT NOT NULL DEFAULT '',
        time_limit_sec REAL NOT NULL DEFAULT 2.0,
        memory_limit_mb INTEGER NOT NULL DEFAULT 256,
        created_at TEXT NOT NULL
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS eval_runs (
        run_id TEXT PRIMARY KEY,
        model_name TEXT NOT NULL,
        tasks_evaluated INTEGER NOT NULL DEFAULT 0,
        total_samples INTEGER NOT NULL DEFAULT 0,
        pass_at_1 REAL NOT NULL DEFAULT 0.0,
        pass_at_5 REAL DEFAULT 0.0,
        mean_score REAL NOT NULL DEFAULT 0.0,
        pass_rate REAL NOT NULL DEFAULT 0.0,
        created_at TEXT NOT NULL,
        metadata TEXT NOT NULL DEFAULT '{}'
    );
    """,
    """
    CREATE TABLE IF NOT EXISTS task_evaluations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL,
        task_id TEXT NOT NULL,
        sample_index INTEGER NOT NULL DEFAULT 0,
        model_name TEXT NOT NULL,
        passed INTEGER NOT NULL DEFAULT 0,
        composite_score REAL NOT NULL DEFAULT 0.0,
        functional_score REAL NOT NULL DEFAULT 0.0,
        edge_scale_score REAL NOT NULL DEFAULT 0.0,
        anti_cheat_score REAL NOT NULL DEFAULT 0.0,
        code_hygiene_score REAL NOT NULL DEFAULT 0.0,
        cheat_detected INTEGER NOT NULL DEFAULT 0,
        duration_ms REAL NOT NULL DEFAULT 0.0,
        memory_peak_kb INTEGER NOT NULL DEFAULT 0,
        exit_code INTEGER NOT NULL DEFAULT 0,
        error_type TEXT NOT NULL DEFAULT 'NONE',
        error_message TEXT,
        stdout TEXT NOT NULL DEFAULT '',
        stderr TEXT NOT NULL DEFAULT '',
        violations TEXT NOT NULL DEFAULT '[]',
        cyclomatic_complexity INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY (run_id) REFERENCES eval_runs(run_id) ON DELETE CASCADE
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_task_evals_run_id ON task_evaluations(run_id);",
    "CREATE INDEX IF NOT EXISTS idx_task_evals_model_name ON task_evaluations(model_name);",
    "CREATE INDEX IF NOT EXISTS idx_task_evals_task_id ON task_evaluations(task_id);",
    "CREATE INDEX IF NOT EXISTS idx_eval_runs_model_name ON eval_runs(model_name);",
    "CREATE INDEX IF NOT EXISTS idx_tasks_lang_diff ON tasks(language, difficulty);",
]


def resolve_db_path(db_path: str | Path | None = None) -> Path:
    """Resolve database path from argument or application settings."""
    if db_path is not None:
        p = Path(db_path)
    else:
        p = Path(get_settings().db_path)
    if p.parent and not p.parent.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
    return p


async def init_db(db_path: str | Path | None = None) -> None:
    """Initialize database tables and indexes with WAL mode enabled."""
    path = resolve_db_path(db_path)
    try:
        async with aiosqlite.connect(path) as db:
            await db.execute("PRAGMA journal_mode=WAL;")
            await db.execute("PRAGMA foreign_keys=ON;")
            for statement in DDL_STATEMENTS:
                await db.execute(statement)
            await db.commit()
            logger.info(f"Initialized database schema at {path}")
    except Exception as exc:
        raise StorageError(message=f"Failed to initialize database at {path}: {exc}") from exc


async def insert_task(task: TaskSpec | dict[str, Any], db_path: str | Path | None = None) -> None:
    """Insert or update a task specification in the tasks table."""
    path = resolve_db_path(db_path)
    if isinstance(task, TaskSpec):
        t_id = task.task_id
        title = task.title
        lang = task.language
        diff = task.difficulty
        cat = task.category
        tags = json.dumps(task.tags)
        prompt = task.prompt
        starter = task.starter_code
        time_lim = task.time_limit_sec
        mem_lim = task.memory_limit_mb
    else:
        t_id = task.get("task_id", task.get("id", ""))
        title = task.get("title", "")
        lang = task.get("language", "python")
        diff = task.get("difficulty", "medium")
        cat = task.get("category", "algorithmic")
        tags = json.dumps(task.get("tags", []))
        prompt = task.get("prompt", "")
        starter = task.get("starter_code", "")
        time_lim = float(task.get("time_limit_sec", task.get("timeout_sec", 2.0)))
        mem_lim = int(task.get("memory_limit_mb", 256))

    now_iso = datetime.now(UTC).isoformat()
    try:
        async with aiosqlite.connect(path) as db:
            await db.execute("PRAGMA foreign_keys=ON;")
            await db.execute(
                """
                INSERT INTO tasks (
                    task_id, title, language, difficulty, category, tags,
                    prompt, starter_code, time_limit_sec, memory_limit_mb, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    title=excluded.title,
                    language=excluded.language,
                    difficulty=excluded.difficulty,
                    category=excluded.category,
                    tags=excluded.tags,
                    prompt=excluded.prompt,
                    starter_code=excluded.starter_code,
                    time_limit_sec=excluded.time_limit_sec,
                    memory_limit_mb=excluded.memory_limit_mb;
                """,
                (t_id, title, lang, diff, cat, tags, prompt, starter, time_lim, mem_lim, now_iso),
            )
            await db.commit()
    except Exception as exc:
        raise StorageError(message=f"Failed to insert task '{t_id}': {exc}") from exc


async def get_task(task_id: str, db_path: str | Path | None = None) -> dict[str, Any] | None:
    """Retrieve a task record by task_id."""
    path = resolve_db_path(db_path)
    try:
        async with aiosqlite.connect(path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            data = dict(row)
            data["tags"] = json.loads(data["tags"])
            return data
    except Exception as exc:
        raise StorageError(message=f"Failed to query task '{task_id}': {exc}") from exc


async def list_tasks(
    language: str | None = None,
    difficulty: str | None = None,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """List tasks matching optional filters."""
    path = resolve_db_path(db_path)
    query = "SELECT * FROM tasks WHERE 1=1"
    params: list[Any] = []
    if language:
        query += " AND language = ?"
        params.append(language.lower())
    if difficulty:
        query += " AND difficulty = ?"
        params.append(difficulty.lower())
    query += " ORDER BY task_id ASC"

    try:
        async with aiosqlite.connect(path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, tuple(params))
            rows = await cursor.fetchall()
            results = []
            for row in rows:
                d = dict(row)
                d["tags"] = json.loads(d["tags"])
                results.append(d)
            return results
    except Exception as exc:
        raise StorageError(message=f"Failed to list tasks: {exc}") from exc


async def insert_run(run: EvalRunReport | dict[str, Any], db_path: str | Path | None = None) -> str:
    """Insert an evaluation run report and all associated task evaluations."""
    path = resolve_db_path(db_path)
    if isinstance(run, EvalRunReport):
        run_id = run.run_id
        model_name = run.model_name
        tasks_evaluated = run.tasks_evaluated
        total_samples = run.total_samples
        p_1 = run.pass_at_1
        p_5 = run.pass_at_5
        mean_score = run.mean_score
        pass_rate = run.pass_rate
        metadata = "{}"
        created_at = datetime.now(UTC).isoformat()
        results = run.results
    else:
        run_id = run["run_id"]
        model_name = run["model_name"]
        tasks_evaluated = int(run.get("tasks_evaluated", 0))
        total_samples = int(run.get("total_samples", 0))
        p_1 = float(run.get("pass_at_1", 0.0))
        p_5 = float(run.get("pass_at_5", 0.0))
        mean_score = float(run.get("mean_score", 0.0))
        pass_rate = float(run.get("pass_rate", 0.0))
        meta_val = run.get("metadata", {})
        metadata = json.dumps(meta_val) if isinstance(meta_val, dict) else str(meta_val)
        created_at = run.get("created_at", datetime.now(UTC).isoformat())
        results = run.get("results", run.get("evaluations", []))

    try:
        async with aiosqlite.connect(path) as db:
            await db.execute("PRAGMA foreign_keys=ON;")
            await db.execute(
                """
                INSERT INTO eval_runs (
                    run_id, model_name, tasks_evaluated, total_samples,
                    pass_at_1, pass_at_5, mean_score, pass_rate, created_at, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    tasks_evaluated=excluded.tasks_evaluated,
                    total_samples=excluded.total_samples,
                    pass_at_1=excluded.pass_at_1,
                    pass_at_5=excluded.pass_at_5,
                    mean_score=excluded.mean_score,
                    pass_rate=excluded.pass_rate,
                    metadata=excluded.metadata;
                """,
                (
                    run_id,
                    model_name,
                    tasks_evaluated,
                    total_samples,
                    p_1,
                    p_5,
                    mean_score,
                    pass_rate,
                    created_at,
                    metadata,
                ),
            )
            await db.commit()

        # Insert per-task evaluations if present
        for idx, evaluation in enumerate(results):
            await insert_task_evaluation(
                evaluation=evaluation,
                run_id=run_id,
                sample_index=idx,
                db_path=path,
            )
        return run_id
    except Exception as exc:
        raise StorageError(message=f"Failed to insert run '{run_id}': {exc}") from exc


async def insert_task_evaluation(
    evaluation: TaskEvaluationResult | dict[str, Any],
    run_id: str,
    sample_index: int = 0,
    db_path: str | Path | None = None,
) -> int:
    """Insert a single task evaluation result linked to run_id."""
    path = resolve_db_path(db_path)

    if isinstance(evaluation, TaskEvaluationResult):
        t_id = evaluation.task_id
        model_name = evaluation.model_name
        passed = 1 if evaluation.passed else 0
        composite_score = evaluation.rubric.composite_score
        func_score = evaluation.rubric.functional_score
        edge_score = evaluation.rubric.edge_scale_score
        anti_cheat = evaluation.rubric.anti_cheat_score
        hygiene = evaluation.rubric.code_hygiene_score
        cheat_detected = 1 if evaluation.rubric.cheat_detected else 0
        duration_ms = evaluation.execution.duration_ms
        mem_peak = evaluation.execution.memory_peak_kb
        exit_code = evaluation.execution.exit_code
        err_type = str(evaluation.execution.error_type)
        err_msg = evaluation.execution.error_message
        stdout = evaluation.execution.stdout
        stderr = evaluation.execution.stderr
        violations = json.dumps(evaluation.rubric.details.get("violations", []))
        cyclomatic = int(evaluation.rubric.details.get("cyclomatic_complexity", 0))
        created_at = evaluation.created_at.isoformat()
    else:
        t_id = evaluation.get("task_id", "")
        model_name = evaluation.get("model_name", "")
        sample_index = evaluation.get("sample_index", sample_index)
        passed = 1 if evaluation.get("passed", False) else 0

        rubric = evaluation.get("rubric", evaluation.get("rubric_breakdown", {}))
        composite_score = float(rubric.get("composite_score", rubric.get("composite", 0.0)))
        func_score = float(rubric.get("functional_score", rubric.get("functional", 0.0)))
        edge_score = float(rubric.get("edge_scale_score", rubric.get("edge_cases", rubric.get("edge_score", 0.0))))
        anti_cheat = float(rubric.get("anti_cheat_score", rubric.get("anti_cheat", rubric.get("ast_score", 0.0))))
        hygiene = float(rubric.get("code_hygiene_score", rubric.get("hygiene", rubric.get("hygiene_score", 0.0))))
        cheat_detected = 1 if rubric.get("cheat_detected", False) else 0

        execution = evaluation.get("execution", {})
        duration_ms = float(execution.get("duration_ms", execution.get("execution_time_ms", 0.0)))
        mem_peak = int(execution.get("memory_peak_kb", execution.get("memory_used_kb", 0)))
        exit_code = int(execution.get("exit_code", 0))
        err_type = str(execution.get("error_type", "NONE"))
        err_msg = execution.get("error_message")
        stdout = str(execution.get("stdout", ""))
        stderr = str(execution.get("stderr", ""))

        ast_audit = evaluation.get("ast_audit", {})
        violations = json.dumps(ast_audit.get("violations", []))
        cyclomatic = int(ast_audit.get("cyclomatic_complexity", 0))
        created_at = evaluation.get("created_at", datetime.now(UTC).isoformat())

    try:
        async with aiosqlite.connect(path) as db:
            await db.execute("PRAGMA foreign_keys=ON;")
            cursor = await db.execute(
                """
                INSERT INTO task_evaluations (
                    run_id, task_id, sample_index, model_name, passed,
                    composite_score, functional_score, edge_scale_score,
                    anti_cheat_score, code_hygiene_score, cheat_detected,
                    duration_ms, memory_peak_kb, exit_code, error_type,
                    error_message, stdout, stderr, violations,
                    cyclomatic_complexity, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    t_id,
                    sample_index,
                    model_name,
                    passed,
                    composite_score,
                    func_score,
                    edge_score,
                    anti_cheat,
                    hygiene,
                    cheat_detected,
                    duration_ms,
                    mem_peak,
                    exit_code,
                    err_type,
                    err_msg,
                    stdout,
                    stderr,
                    violations,
                    cyclomatic,
                    created_at,
                ),
            )
            await db.commit()
            return cursor.lastrowid or 0
    except Exception as exc:
        raise StorageError(message=f"Failed to insert task evaluation for '{t_id}': {exc}") from exc


async def get_run(
    run_id: str,
    include_evaluations: bool = True,
    db_path: str | Path | None = None,
) -> dict[str, Any] | None:
    """Retrieve an evaluation run by run_id, optionally including task evaluations."""
    path = resolve_db_path(db_path)
    try:
        async with aiosqlite.connect(path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM eval_runs WHERE run_id = ?", (run_id,))
            row = await cursor.fetchone()
            if not row:
                return None
            data = dict(row)
            data["metadata"] = json.loads(data["metadata"])

            if include_evaluations:
                eval_cursor = await db.execute(
                    "SELECT * FROM task_evaluations WHERE run_id = ? ORDER BY id ASC",
                    (run_id,),
                )
                eval_rows = await eval_cursor.fetchall()
                evaluations = []
                for erow in eval_rows:
                    edata = dict(erow)
                    edata["passed"] = bool(edata["passed"])
                    edata["cheat_detected"] = bool(edata["cheat_detected"])
                    edata["violations"] = json.loads(edata["violations"])
                    evaluations.append(edata)
                data["evaluations"] = evaluations
            return data
    except Exception as exc:
        raise StorageError(message=f"Failed to query run '{run_id}': {exc}") from exc


async def list_runs(
    limit: int = 50,
    offset: int = 0,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    """List recent evaluation runs sorted by creation time descending."""
    path = resolve_db_path(db_path)
    try:
        async with aiosqlite.connect(path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM eval_runs ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
            rows = await cursor.fetchall()
            results = []
            for row in rows:
                d = dict(row)
                d["metadata"] = json.loads(d["metadata"])
                results.append(d)
            return results
    except Exception as exc:
        raise StorageError(message=f"Failed to list runs: {exc}") from exc


async def get_task_evaluations(run_id: str, db_path: str | Path | None = None) -> list[dict[str, Any]]:
    """Retrieve all task evaluations for a specific run_id."""
    path = resolve_db_path(db_path)
    try:
        async with aiosqlite.connect(path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM task_evaluations WHERE run_id = ? ORDER BY sample_index ASC, id ASC",
                (run_id,),
            )
            rows = await cursor.fetchall()
            results = []
            for row in rows:
                d = dict(row)
                d["passed"] = bool(d["passed"])
                d["cheat_detected"] = bool(d["cheat_detected"])
                d["violations"] = json.loads(d["violations"])
                results.append(d)
            return results
    except Exception as exc:
        raise StorageError(message=f"Failed to query evaluations for run '{run_id}': {exc}") from exc


async def get_leaderboard(db_path: str | Path | None = None) -> list[dict[str, Any]]:
    """Compute and retrieve aggregate leaderboard across all models.

    Computes:
    - rank: 1-based ordering
    - model_name: string identifier
    - total_tasks: distinct tasks evaluated
    - pass_at_1: percentage (0.0 to 100.0)
    - pass_at_5: estimated pass@5 percentage (if multiple samples exist) or average
    - mean_composite_score: average composite rubric score (0.0 to 100.0)
    - cheat_attempts_detected: total number of evaluations where cheat was detected
    """
    path = resolve_db_path(db_path)
    query = """
    SELECT
        model_name,
        COUNT(DISTINCT task_id) as total_tasks,
        COUNT(id) as total_evaluations,
        ROUND(AVG(passed) * 100.0, 2) as pass_at_1,
        ROUND(AVG(composite_score), 2) as mean_composite_score,
        SUM(cheat_detected) as cheat_attempts_detected
    FROM task_evaluations
    GROUP BY model_name
    ORDER BY pass_at_1 DESC, mean_composite_score DESC;
    """
    try:
        async with aiosqlite.connect(path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query)
            rows = await cursor.fetchall()

            # Also check if eval_runs has pass_at_5 reported per model
            runs_cursor = await db.execute(
                "SELECT model_name, AVG(pass_at_5) * 100.0 as avg_pass_5 FROM eval_runs GROUP BY model_name;"
            )
            pass5_rows = await runs_cursor.fetchall()
            pass5_map = {r["model_name"]: round(r["avg_pass_5"] or 0.0, 2) for r in pass5_rows}

            leaderboard = []
            for rank, row in enumerate(rows, start=1):
                m_name = row["model_name"]
                pass_5 = pass5_map.get(m_name, row["pass_at_1"])
                leaderboard.append({
                    "rank": rank,
                    "model_name": m_name,
                    "total_tasks": row["total_tasks"],
                    "pass_at_1": float(row["pass_at_1"] or 0.0),
                    "pass_at_5": float(pass_5 if pass_5 is not None else row["pass_at_1"]),
                    "mean_composite_score": float(row["mean_composite_score"] or 0.0),
                    "cheat_attempts_detected": int(row["cheat_attempts_detected"] or 0),
                })
            return leaderboard
    except Exception as exc:
        raise StorageError(message=f"Failed to query leaderboard: {exc}") from exc


__all__ = [
    "DDL_STATEMENTS",
    "resolve_db_path",
    "init_db",
    "insert_task",
    "get_task",
    "list_tasks",
    "insert_run",
    "insert_task_evaluation",
    "get_run",
    "list_runs",
    "get_task_evaluations",
    "get_leaderboard",
]
