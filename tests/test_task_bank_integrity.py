"""Integrity and test validation suite for EvalForge benchmark task bank.

Validates that all 30 benchmark tasks (20 Python + 10 C++20):
1. Exist in their designated bank directories.
2. Parse cleanly into TaskSpec models.
3. Conform strictly to rubric, timing, memory, and categorization standards.
4. Execute canonical Python solutions against visible and hidden tests with 100% pass rate.
"""

import asyncio
import re
from pathlib import Path
from typing import Any

import pytest

from evalforge.models.schemas import TaskSpec
from evalforge.tasks.loader import TaskLoader, TaskRegistry

TASK_BANK_DIR = Path(__file__).resolve().parent.parent / "evalforge" / "tasks" / "bank"
PYTHON_BANK_DIR = TASK_BANK_DIR / "python"
CPP_BANK_DIR = TASK_BANK_DIR / "cpp"

EXPECTED_PYTHON_TASK_IDS = [f"EF-PY-{i:03d}" for i in range(1, 21)]
EXPECTED_CPP_TASK_IDS = [f"EF-CPP-{i:03d}" for i in range(1, 11)]
ALL_EXPECTED_TASK_IDS = EXPECTED_PYTHON_TASK_IDS + EXPECTED_CPP_TASK_IDS


def test_task_bank_files_exist():
    """Verify that all 30 task definition YAML files exist in their target directories."""
    assert PYTHON_BANK_DIR.is_dir(), f"Python task bank directory '{PYTHON_BANK_DIR}' missing"
    assert CPP_BANK_DIR.is_dir(), f"C++ task bank directory '{CPP_BANK_DIR}' missing"

    for task_id in EXPECTED_PYTHON_TASK_IDS:
        yaml_file = PYTHON_BANK_DIR / f"{task_id}.yaml"
        assert yaml_file.is_file(), f"Missing Python task YAML file: {yaml_file}"

    for task_id in EXPECTED_CPP_TASK_IDS:
        yaml_file = CPP_BANK_DIR / f"{task_id}.yaml"
        assert yaml_file.is_file(), f"Missing C++ task YAML file: {yaml_file}"


@pytest.mark.parametrize("task_id", ALL_EXPECTED_TASK_IDS)
def test_task_spec_parsing_and_schema(task_id: str):
    """Verify that every task file parses cleanly into TaskSpec with mandatory fields."""
    is_python = task_id.startswith("EF-PY")
    bank_dir = PYTHON_BANK_DIR if is_python else CPP_BANK_DIR
    yaml_file = bank_dir / f"{task_id}.yaml"

    task: TaskSpec = TaskLoader.load_task_from_file(yaml_file)

    assert isinstance(task, TaskSpec)
    assert task.task_id == task_id
    assert task.title.strip()
    assert task.language == ("python" if is_python else "cpp")
    assert task.difficulty in {"easy", "medium", "hard"}
    assert task.category in {"systems", "concurrency", "algorithmic", "data_structures"}
    assert task.time_limit_sec == 2.0
    assert task.memory_limit_mb == 256
    assert isinstance(task.rubric_rules, dict)
    assert "banned_imports" in task.rubric_rules

    # Check non-empty content
    assert len(task.prompt.strip()) > 30, f"[{task_id}] Prompt too short"
    assert len(task.starter_code.strip()) > 10, f"[{task_id}] Starter code too short"
    assert len(task.canonical_solution.strip()) > 20, f"[{task_id}] Canonical solution too short"
    assert len(task.visible_tests.strip()) > 10, f"[{task_id}] Visible tests too short"
    assert len(task.hidden_tests.strip()) > 20, f"[{task_id}] Hidden tests too short"


def test_task_registry_batch_loading():
    """Verify TaskRegistry recursively discovers and registers all 30 bank tasks."""
    registry = TaskRegistry()
    loaded_count = registry.load_tasks_from_directory(TASK_BANK_DIR)
    assert loaded_count >= 30
    assert len(registry) >= 30

    for task_id in ALL_EXPECTED_TASK_IDS:
        assert task_id in registry
        spec = registry.get(task_id)
        assert spec.task_id == task_id

    py_tasks = registry.list_tasks(language="python")
    assert len(py_tasks) >= 20

    cpp_tasks = registry.list_tasks(language="cpp")
    assert len(cpp_tasks) >= 10


@pytest.mark.parametrize("task_id", EXPECTED_CPP_TASK_IDS)
def test_cpp_task_gtest_structure(task_id: str):
    """Verify C++ tasks contain required Google Test cases (>=2 visible, >=6 hidden)."""
    yaml_file = CPP_BANK_DIR / f"{task_id}.yaml"
    task = TaskLoader.load_task_from_file(yaml_file)

    # Count TEST( or TEST_F( macros
    visible_tests = re.findall(r"\bTEST(?:_F)?\s*\(", task.visible_tests)
    hidden_tests = re.findall(r"\bTEST(?:_F)?\s*\(", task.hidden_tests)

    assert len(visible_tests) >= 2, f"[{task_id}] Expected >= 2 visible gtests, found {len(visible_tests)}"
    assert len(hidden_tests) >= 6, f"[{task_id}] Expected >= 6 hidden gtests, found {len(hidden_tests)}"
    assert "<gtest/gtest.h>" in task.visible_tests
    assert "<gtest/gtest.h>" in task.hidden_tests


def _run_python_test_suite(task_id: str, solution_code: str, test_code: str, suite_name: str) -> int:
    """Helper executing Python tests in isolated namespace."""
    ns: dict[str, Any] = {"__name__": "__main__"}
    exec(solution_code, ns)
    exec(test_code, ns)

    test_funcs = [v for k, v in ns.items() if k.startswith("test_") and callable(v)]
    for fn in test_funcs:
        if asyncio.iscoroutinefunction(fn):
            asyncio.run(fn())
        else:
            fn()
    return len(test_funcs)


@pytest.mark.parametrize("task_id", EXPECTED_PYTHON_TASK_IDS)
def test_python_canonical_solution_visible_tests(task_id: str):
    """Verify Python canonical reference solution passes 100% of visible tests."""
    yaml_file = PYTHON_BANK_DIR / f"{task_id}.yaml"
    task = TaskLoader.load_task_from_file(yaml_file)

    count = _run_python_test_suite(task_id, task.canonical_solution, task.visible_tests, "visible_tests")
    assert count >= 2, f"[{task_id}] Expected >= 2 visible tests, found {count}"


@pytest.mark.parametrize("task_id", EXPECTED_PYTHON_TASK_IDS)
def test_python_canonical_solution_hidden_tests(task_id: str):
    """Verify Python canonical reference solution passes 100% of hidden stress tests."""
    yaml_file = PYTHON_BANK_DIR / f"{task_id}.yaml"
    task = TaskLoader.load_task_from_file(yaml_file)

    count = _run_python_test_suite(task_id, task.canonical_solution, task.hidden_tests, "hidden_tests")
    assert count >= 6, f"[{task_id}] Expected >= 6 hidden tests, found {count}"
