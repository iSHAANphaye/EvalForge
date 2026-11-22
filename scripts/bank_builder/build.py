"""Build and validate all 30 benchmark tasks for EvalForge."""

import asyncio
import sys
from pathlib import Path

import yaml

# Add EvalForge project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from evalforge.models.schemas import TaskSpec
from evalforge.tasks.loader import TaskLoader
from scripts.bank_builder.cpp_01_05 import TASKS as CPP_01_05
from scripts.bank_builder.cpp_06_10 import TASKS as CPP_06_10
from scripts.bank_builder.py_01_05 import TASKS as PY_01_05
from scripts.bank_builder.py_06_10 import TASKS as PY_06_10
from scripts.bank_builder.py_11_15 import TASKS as PY_11_15
from scripts.bank_builder.py_16_20 import TASKS as PY_16_20

ALL_PY_TASKS = PY_01_05 + PY_06_10 + PY_11_15 + PY_16_20
ALL_CPP_TASKS = CPP_01_05 + CPP_06_10
ALL_TASKS = ALL_PY_TASKS + ALL_CPP_TASKS


def write_yaml(task_data: dict, out_path: Path) -> None:
    # Use standard yaml dump with preserve formatting
    content = yaml.dump(task_data, sort_keys=False, width=120, allow_unicode=True)
    out_path.write_text(content, encoding="utf-8")


def run_python_suite(task_id: str, solution_code: str, test_code: str, suite_name: str) -> None:
    # Namespace execution
    ns: dict = {"__name__": "__main__"}
    try:
        exec(solution_code, ns)
    except Exception as exc:
        raise RuntimeError(f"[{task_id}] Failed executing canonical solution: {exc}") from exc

    try:
        exec(test_code, ns)
    except Exception as exc:
        raise RuntimeError(f"[{task_id}] Failed executing {suite_name} definition: {exc}") from exc

    test_funcs = [v for k, v in ns.items() if k.startswith("test_") and callable(v)]
    if not test_funcs:
        raise RuntimeError(f"[{task_id}] No test_* functions found in {suite_name}")

    min_required = 2 if suite_name == "visible_tests" else 6
    if len(test_funcs) < min_required:
        raise RuntimeError(
            f"[{task_id}] {suite_name} has {len(test_funcs)} tests, expected at least {min_required}"
        )

    for fn in test_funcs:
        try:
            if asyncio.iscoroutinefunction(fn):
                asyncio.run(fn())
            else:
                fn()
        except Exception as exc:
            raise AssertionError(f"[{task_id}][{suite_name}][{fn.__name__}] Failed: {exc}") from exc


def main() -> None:
    py_dir = PROJECT_ROOT / "evalforge" / "tasks" / "bank" / "python"
    cpp_dir = PROJECT_ROOT / "evalforge" / "tasks" / "bank" / "cpp"
    py_dir.mkdir(parents=True, exist_ok=True)
    cpp_dir.mkdir(parents=True, exist_ok=True)

    print(f"Total tasks to build: {len(ALL_TASKS)} (Python: {len(ALL_PY_TASKS)}, C++: {len(ALL_CPP_TASKS)})")

    # 1. Write YAML files
    for t in ALL_PY_TASKS:
        file_path = py_dir / f"{t['task_id']}.yaml"
        write_yaml(t, file_path)
        print(f"  [WROTE] {file_path.relative_to(PROJECT_ROOT)}")

    for t in ALL_CPP_TASKS:
        file_path = cpp_dir / f"{t['task_id']}.yaml"
        write_yaml(t, file_path)
        print(f"  [WROTE] {file_path.relative_to(PROJECT_ROOT)}")

    print("\n--- Validating TaskSpec Parsing ---")
    for t in ALL_TASKS:
        tid = t["task_id"]
        lang = t["language"]
        file_path = (py_dir if lang == "python" else cpp_dir) / f"{tid}.yaml"
        spec = TaskLoader.load_task_from_file(file_path)
        assert isinstance(spec, TaskSpec), f"Failed parsing {tid} into TaskSpec"
        assert spec.task_id == tid
        assert spec.prompt.strip()
        assert spec.starter_code.strip()
        assert spec.canonical_solution.strip()
        assert spec.visible_tests.strip()
        assert spec.hidden_tests.strip()
        assert spec.time_limit_sec == 2.0
        assert spec.memory_limit_mb == 256
        assert "banned_imports" in spec.rubric_rules
        print(f"  [SPEC VALID] {tid}: {spec.title} ({spec.difficulty}, {spec.category})")

    print("\n--- Validating Python Task Test Execution ---")
    passed_tests = 0
    for t in ALL_PY_TASKS:
        tid = t["task_id"]
        run_python_suite(tid, t["canonical_solution"], t["visible_tests"], "visible_tests")
        run_python_suite(tid, t["canonical_solution"], t["hidden_tests"], "hidden_tests")
        passed_tests += 1
        print(f"  [PYTHON 100% PASS] {tid}: {t['title']}")

    print(f"\nSuccessfully generated and verified {len(ALL_TASKS)} benchmark tasks!")
    print(f"All {passed_tests} Python tasks passed 100% of visible and hidden tests.")


if __name__ == "__main__":
    main()
