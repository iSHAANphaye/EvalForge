"""Unit tests for EvalForge Task Loader, Task Registry, and Pydantic task models."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from evalforge.core.exceptions import TaskNotFoundError
from evalforge.models.schemas import TaskSpec
from evalforge.tasks.loader import (
    TaskLoader,
    TaskRegistry,
    get_global_registry,
    load_task_from_dir,
    reset_global_registry,
)
from evalforge.tasks.models import (
    RubricRules,
    TaskMetadata,
    TaskRubricConfig,
    TestCase,
)


def test_task_rubric_config_defaults_and_aliases():
    """Verify TaskRubricConfig default values, constraints, and field aliases."""
    config = TaskRubricConfig()
    assert config.banned_imports == []
    assert config.max_cyclomatic_complexity == 25
    assert config.max_lines == 200
    assert config.timeout_sec == 2.0
    assert config.memory_limit_mb == 256
    assert config.require_algorithmic_control is True

    # Alias synchronization
    cfg2 = TaskRubricConfig(
        disallowed_modules=["os", "sys"],
        timeout_seconds=5.0,
        extra_weight=10.0,
    )
    assert cfg2.banned_imports == ["os", "sys"]
    assert cfg2.disallowed_modules == ["os", "sys"]
    assert cfg2.timeout_sec == 5.0
    assert getattr(cfg2, "extra_weight") == 10.0

    # RubricRules is alias of TaskRubricConfig
    assert RubricRules is TaskRubricConfig


def test_task_metadata_validation():
    """Verify TaskMetadata strict validation, normalization, and alias handling."""
    meta = TaskMetadata(
        id="EF-PY-001",
        title="Thread-Safe LRU Cache",
        language="c++",
        difficulty="hard",
        category="concurrency",
        tags=["caching", "multithreading"],
    )
    assert meta.task_id == "EF-PY-001"
    assert meta.language == "cpp"
    assert meta.difficulty == "hard"
    assert meta.category == "concurrency"
    assert "caching" in meta.tags

    # Invalid language
    with pytest.raises(ValidationError):
        TaskMetadata(task_id="EF-01", title="Test", language="rust")

    # Invalid difficulty
    with pytest.raises(ValidationError):
        TaskMetadata(task_id="EF-01", title="Test", difficulty="extreme")

    # Invalid category
    with pytest.raises(ValidationError):
        TaskMetadata(task_id="EF-01", title="Test", category="machine_learning")


def test_test_case_model():
    """Verify TestCase Pydantic model creation."""
    tc = TestCase(name="test_1", code="assert True", description="Smoke test")
    assert tc.name == "test_1"
    assert tc.code == "assert True"


def test_load_valid_python_task_directory(tmp_path: Path):
    """Verify loading a valid Python task directory with all standard files."""
    task_dir = tmp_path / "EF-PY-001"
    task_dir.mkdir()

    (task_dir / "task.yaml").write_text(
        """
task_id: "EF-PY-001"
title: "Thread-Safe LRU Cache with TTL"
language: "python"
difficulty: "medium"
category: "concurrency"
tags:
  - "caching"
  - "concurrency"
timeout_sec: 2.5
memory_limit_mb: 512
rubric:
  banned_imports: ["socket", "subprocess"]
  max_cyclomatic_complexity: 15
""",
        encoding="utf-8",
    )
    (task_dir / "prompt.md").write_text(
        "# Implement a thread-safe LRU Cache with TTL.",
        encoding="utf-8",
    )
    (task_dir / "starter.py").write_text(
        "class TTLCache:\n    def __init__(self, capacity: int): pass\n",
        encoding="utf-8",
    )
    (task_dir / "test_visible.py").write_text(
        "def test_put_get():\n    cache = TTLCache(2)\n    assert cache is not None\n",
        encoding="utf-8",
    )
    (task_dir / "test_hidden_stress.py").write_text(
        "def test_stress():\n    pass\n",
        encoding="utf-8",
    )
    (task_dir / "solution.py").write_text(
        "class TTLCache:\n    def __init__(self, capacity: int): self.cap = capacity\n",
        encoding="utf-8",
    )

    task = TaskLoader.load_task_from_dir(task_dir)
    assert isinstance(task, TaskSpec)
    assert task.task_id == "EF-PY-001"
    assert task.title == "Thread-Safe LRU Cache with TTL"
    assert task.language == "python"
    assert task.difficulty == "medium"
    assert task.category == "concurrency"
    assert task.time_limit_sec == 2.5
    assert task.memory_limit_mb == 512
    assert "TTLCache" in task.starter_code
    assert "test_put_get" in task.visible_tests
    assert "test_stress" in task.hidden_tests
    assert "self.cap = capacity" in task.canonical_solution
    assert "socket" in task.rubric_rules.get("banned_imports", [])

    # Test module-level load_task_from_dir helper
    task2 = load_task_from_dir(task_dir)
    assert task2.task_id == task.task_id

    # Test get_public_spec() sanitization
    public_spec = task.get_public_spec()
    assert "hidden_tests" not in public_spec
    assert "canonical_solution" not in public_spec
    assert public_spec["task_id"] == "EF-PY-001"
    assert "visible_tests" in public_spec


def test_load_valid_cpp_task_directory(tmp_path: Path):
    """Verify loading a valid C++ task directory without stress test."""
    task_dir = tmp_path / "EF-CPP-001"
    task_dir.mkdir()

    (task_dir / "task.yaml").write_text(
        """
id: "EF-CPP-001"
title: "Lock-Free Ring Buffer"
language: "cpp"
difficulty: "hard"
category: "systems"
prompt: "Implement a lock-free SPSC queue in C++20."
""",
        encoding="utf-8",
    )
    (task_dir / "starter.cpp").write_text(
        "#include <atomic>\ntemplate<typename T> class RingBuffer {};",
        encoding="utf-8",
    )
    (task_dir / "test_visible.cpp").write_text(
        "#include <cassert>\nint main() { return 0; }",
        encoding="utf-8",
    )

    task = TaskLoader.load_task_from_dir(task_dir)
    assert task.task_id == "EF-CPP-001"
    assert task.language == "cpp"
    assert task.difficulty == "hard"
    assert task.category == "systems"
    assert "RingBuffer" in task.starter_code
    assert "main" in task.visible_tests
    assert task.hidden_tests == ""


def test_missing_mandatory_files_raise_task_not_found(tmp_path: Path):
    """Verify missing mandatory files raise TaskNotFoundError (or ValueError)."""
    # 1. Nonexistent directory
    with pytest.raises((TaskNotFoundError, ValueError)):
        TaskLoader.load_task_from_dir(tmp_path / "nonexistent")

    # 2. Directory missing task.yaml / metadata.yaml
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    with pytest.raises((TaskNotFoundError, ValueError)):
        TaskLoader.load_task_from_dir(empty_dir)

    # 3. Missing prompt
    no_prompt = tmp_path / "no_prompt"
    no_prompt.mkdir()
    (no_prompt / "task.yaml").write_text("task_id: 'EF-01'\nlanguage: 'python'\n", encoding="utf-8")
    (no_prompt / "starter.py").write_text("pass", encoding="utf-8")
    (no_prompt / "test_visible.py").write_text("pass", encoding="utf-8")
    with pytest.raises((TaskNotFoundError, ValueError)):
        TaskLoader.load_task_from_dir(no_prompt)

    # 4. Missing starter code
    no_starter = tmp_path / "no_starter"
    no_starter.mkdir()
    (no_starter / "task.yaml").write_text("task_id: 'EF-02'\nprompt: 'Do x'\n", encoding="utf-8")
    (no_starter / "test_visible.py").write_text("pass", encoding="utf-8")
    with pytest.raises((TaskNotFoundError, ValueError)):
        TaskLoader.load_task_from_dir(no_starter)

    # 5. Missing visible tests
    no_tests = tmp_path / "no_tests"
    no_tests.mkdir()
    (no_tests / "task.yaml").write_text("task_id: 'EF-03'\nprompt: 'Do x'\n", encoding="utf-8")
    (no_tests / "starter.py").write_text("pass", encoding="utf-8")
    with pytest.raises((TaskNotFoundError, ValueError)):
        TaskLoader.load_task_from_dir(no_tests)


def test_malformed_yaml_handling(tmp_path: Path):
    """Verify syntax errors and malformed roots in task YAML raise TaskNotFoundError / ValueError."""
    # Syntax error in task.yaml
    bad_syntax = tmp_path / "bad_syntax"
    bad_syntax.mkdir()
    (bad_syntax / "task.yaml").write_text("invalid: [unclosed_bracket", encoding="utf-8")
    with pytest.raises((TaskNotFoundError, ValueError)):
        TaskLoader.load_task_from_dir(bad_syntax)

    # Non-dictionary root
    bad_root = tmp_path / "bad_root"
    bad_root.mkdir()
    (bad_root / "task.yaml").write_text("- item1\n- item2\n", encoding="utf-8")
    with pytest.raises((TaskNotFoundError, ValueError)):
        TaskLoader.load_task_from_dir(bad_root)

    # Bad auxiliary rubric.yaml
    bad_rubric = tmp_path / "bad_rubric"
    bad_rubric.mkdir()
    (bad_rubric / "task.yaml").write_text(
        "task_id: 'EF-04'\nprompt: 'Prompt'\n",
        encoding="utf-8",
    )
    (bad_rubric / "starter.py").write_text("pass", encoding="utf-8")
    (bad_rubric / "test_visible.py").write_text("pass", encoding="utf-8")
    (bad_rubric / "rubric.yaml").write_text("rubric: [unclosed", encoding="utf-8")
    with pytest.raises((TaskNotFoundError, ValueError)):
        TaskLoader.load_task_from_dir(bad_rubric)


def test_metadata_yaml_and_rubric_yaml_override(tmp_path: Path):
    """Verify loading from metadata.yaml and external rubric.yaml merge."""
    task_dir = tmp_path / "alt_meta"
    task_dir.mkdir()

    (task_dir / "metadata.yaml").write_text(
        """
id: "EF-PY-042"
title: "Prefix Tree Trie"
language: "python"
""",
        encoding="utf-8",
    )
    (task_dir / "prompt.md").write_text("Implement Trie", encoding="utf-8")
    (task_dir / "starter.py").write_text("class Trie: pass", encoding="utf-8")
    (task_dir / "test_visible.py").write_text("def test_trie(): pass", encoding="utf-8")
    (task_dir / "rubric.yaml").write_text(
        """
max_cyclomatic_complexity: 12
banned_imports: ["re"]
timeout_sec: 1.5
""",
        encoding="utf-8",
    )

    task = TaskLoader.load_task_from_dir(task_dir)
    assert task.task_id == "EF-PY-042"
    assert task.time_limit_sec == 1.5
    assert task.rubric_rules["max_cyclomatic_complexity"] == 12
    assert "re" in task.rubric_rules["banned_imports"]


def test_task_registry_operations():
    """Verify TaskRegistry registration, retrieval by ID, and language/category filtering."""
    registry = TaskRegistry()

    t1 = TaskSpec(
        task_id="EF-PY-001",
        title="Python Task 1",
        language="python",
        prompt="Solve in Python",
        starter_code="def solve(): pass",
        visible_tests="def test_solve(): pass",
        difficulty="easy",
        category="algorithmic",
    )
    t2 = TaskSpec(
        task_id="EF-CPP-001",
        title="CPP Task 1",
        language="cpp",
        prompt="Solve in C++",
        starter_code="void solve() {}",
        visible_tests="int main() { return 0; }",
        difficulty="hard",
        category="systems",
    )

    registry.register(t1)
    registry.register(t2)

    # Retrieval
    assert registry.get("EF-PY-001").task_id == "EF-PY-001"
    assert registry.get_task("EF-CPP-001").task_id == "EF-CPP-001"
    assert "EF-PY-001" in registry
    assert len(registry) == 2

    # Missing task
    with pytest.raises(TaskNotFoundError):
        registry.get("EF-NONEXISTENT")

    # Filtering by language
    py_tasks = registry.list_tasks(language="python")
    assert len(py_tasks) == 1
    assert py_tasks[0].task_id == "EF-PY-001"

    cpp_tasks = registry.list_tasks(language="cpp")
    assert len(cpp_tasks) == 1
    assert cpp_tasks[0].task_id == "EF-CPP-001"

    # Filtering by category
    algo_tasks = registry.list_tasks(category="algorithmic")
    assert len(algo_tasks) == 1
    assert algo_tasks[0].task_id == "EF-PY-001"

    sys_tasks = registry.list_tasks(category="systems")
    assert len(sys_tasks) == 1
    assert sys_tasks[0].task_id == "EF-CPP-001"

    # Public spec
    public = registry.get_public_spec("EF-PY-001")
    assert public["task_id"] == "EF-PY-001"
    assert "hidden_tests" not in public

    # Clear
    registry.clear()
    assert len(registry) == 0


def test_task_registry_load_tasks_from_directory(tmp_path: Path):
    """Verify recursive directory discovery and task registration in TaskRegistry."""
    registry = TaskRegistry()

    # Valid Python task dir
    p_dir = tmp_path / "task_py"
    p_dir.mkdir()
    (p_dir / "task.yaml").write_text("task_id: 'EF-PY-010'\nlanguage: 'python'\n", encoding="utf-8")
    (p_dir / "prompt.md").write_text("Prompt 1", encoding="utf-8")
    (p_dir / "starter.py").write_text("pass", encoding="utf-8")
    (p_dir / "test_visible.py").write_text("pass", encoding="utf-8")

    # Valid C++ task dir
    c_dir = tmp_path / "task_cpp"
    c_dir.mkdir()
    (c_dir / "task.yaml").write_text("task_id: 'EF-CPP-010'\nlanguage: 'cpp'\n", encoding="utf-8")
    (c_dir / "prompt.md").write_text("Prompt 2", encoding="utf-8")
    (c_dir / "starter.cpp").write_text("int main(){}", encoding="utf-8")
    (c_dir / "test_visible.cpp").write_text("int main(){}", encoding="utf-8")

    # Invalid task dir (missing prompt and starter)
    bad_dir = tmp_path / "bad_task"
    bad_dir.mkdir()
    (bad_dir / "task.yaml").write_text("invalid", encoding="utf-8")

    loaded_count = registry.load_tasks_from_directory(tmp_path)
    assert loaded_count == 2
    assert "EF-PY-010" in registry
    assert "EF-CPP-010" in registry


def test_global_registry_singleton():
    """Verify get_global_registry returns singleton instance and reset_global_registry cleans it."""
    reset_global_registry()
    r1 = get_global_registry()
    r2 = get_global_registry()
    assert r1 is r2

    t = TaskSpec(
        task_id="EF-GLOBAL-01",
        title="Global Test",
        prompt="Test",
        starter_code="pass",
        visible_tests="pass",
    )
    r1.register(t)
    assert "EF-GLOBAL-01" in r2

    reset_global_registry()
    r3 = get_global_registry()
    assert r3 is not r1
    assert "EF-GLOBAL-01" not in r3
