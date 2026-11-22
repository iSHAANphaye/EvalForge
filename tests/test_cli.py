"""Integration and unit tests for EvalForge Typer & Rich CLI."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from evalforge.main import app
from evalforge.models.schemas import TaskSpec
from evalforge.tasks.loader import get_global_registry

runner = CliRunner()


@pytest.fixture(autouse=True)
def setup_test_registry():
    """Register sample task into global registry for CLI test runs."""
    registry = get_global_registry()
    task = TaskSpec(
        task_id="EF-PY-001",
        title="Thread-Safe LRU Cache with TTL",
        language="python",
        difficulty="medium",
        category="concurrency",
        tags=["caching"],
        prompt="Implement TTL cache",
        starter_code="class TTLCache: pass",
        canonical_solution="class TTLCache: pass",
        visible_tests="def test_basic(): pass",
        hidden_tests="def test_hidden(): pass",
        rubric_rules={"banned_imports": ["subprocess", "socket"]},
    )
    registry.register(task)
    yield
    registry.clear()


def test_cli_help():
    """Verify evalforge root CLI lists subcommands."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "run" in result.stdout
    assert "report" in result.stdout
    assert "benchmark" in result.stdout
    assert "sandbox" in result.stdout


def test_cli_run_missing_code_and_file():
    """Verify run without code or file exits with code 2."""
    result = runner.invoke(app, ["run", "--task-id", "EF-PY-001"])
    assert result.exit_code == 2
    assert "Either --candidate-file (-c) or --code must be specified" in result.stdout


def test_cli_run_nonexistent_task():
    """Verify run with unknown task exits with code 2."""
    result = runner.invoke(app, ["run", "--task-id", "EF-UNKNOWN-999", "--code", "x = 1"])
    assert result.exit_code == 2
    assert "not found" in result.stdout


def test_cli_run_valid_code_success(tmp_path: Path):
    """Verify run with valid candidate code prints scorecard and passes."""
    code = (
        "class TTLCache:\n"
        "    def __init__(self, capacity: int):\n"
        "        self.cap = capacity\n"
    )
    out_jsonl = tmp_path / "stream.jsonl"
    result = runner.invoke(
        app,
        [
            "run",
            "-t",
            "EF-PY-001",
            "--code",
            code,
            "-m",
            "test-coder",
            "--output-jsonl",
            str(out_jsonl),
        ],
    )
    assert result.exit_code == 0
    assert "EvalForge — Task Evaluation: EF-PY-001" in result.stdout
    assert "Rubric Scoring Breakdown" in result.stdout
    assert "Final Outcome: PASSED" in result.stdout


def test_cli_run_cheat_detected(tmp_path: Path):
    """Verify run with cheat code exits with code 1 and flags violation."""
    code = (
        "import subprocess\n"
        "import sys\n"
        "sys.exit(0)\n"
    )
    out_jsonl = tmp_path / "stream.jsonl"
    result = runner.invoke(
        app,
        [
            "run",
            "-t",
            "EF-PY-001",
            "--code",
            code,
            "--output-jsonl",
            str(out_jsonl),
        ],
    )
    assert result.exit_code == 1
    assert "CHEAT" in result.stdout or "Banned import" in result.stdout or "Exit" in result.stdout
    assert "Final Outcome: FAILED" in result.stdout


def test_cli_run_with_candidate_file(tmp_path: Path):
    """Verify run loading code from a candidate file on disk."""
    sol_file = tmp_path / "solution.py"
    sol_file.write_text("class TTLCache:\n    pass\n", encoding="utf-8")

    result = runner.invoke(
        app,
        ["run", "-t", "EF-PY-001", "-c", str(sol_file)],
    )
    assert result.exit_code == 0
    assert "PASSED" in result.stdout


def test_cli_report_formats(tmp_path: Path):
    """Verify report command outputs table, json, and markdown formats."""
    # First submit an evaluation so database has entries
    runner.invoke(app, ["run", "-t", "EF-PY-001", "--code", "class TTLCache: pass"])

    # Table format
    res_table = runner.invoke(app, ["report", "--format", "table"])
    assert res_table.exit_code == 0
    assert "Evaluation Run:" in res_table.stdout

    # JSON format
    res_json = runner.invoke(app, ["report", "--format", "json"])
    assert res_json.exit_code == 0
    assert '"run_id":' in res_json.stdout

    # Markdown format
    res_md = runner.invoke(app, ["report", "--format", "markdown"])
    assert res_md.exit_code == 0
    assert "# EvalForge Run Report:" in res_md.stdout

    # CSV export
    csv_file = tmp_path / "export.csv"
    res_csv = runner.invoke(app, ["report", "--export-csv", str(csv_file)])
    assert res_csv.exit_code == 0
    assert csv_file.exists()


def test_cli_benchmark_command():
    """Verify benchmark runs tasks, updates progress, and renders leaderboard."""
    result = runner.invoke(
        app,
        ["benchmark", "-m", "claude-3-7-sonnet", "--samples-per-task", "1"],
    )
    assert result.exit_code == 0
    assert "Starting Benchmark" in result.stdout
    assert "EVALFORGE BENCHMARK LEADERBOARD" in result.stdout
    assert "claude-3-7-sonnet" in result.stdout


def test_cli_sandbox_status():
    """Verify sandbox status command outputs container pool information."""
    result = runner.invoke(app, ["sandbox", "status"])
    assert result.exit_code == 0
    assert "Docker Daemon Status:" in result.stdout
    assert "Target Pool Size:" in result.stdout
