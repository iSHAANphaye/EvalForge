"""Benchmark task loader and in-memory task registry for EvalForge."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from evalforge.core.exceptions import TaskNotFoundError
from evalforge.core.logging import get_logger
from evalforge.models.schemas import TaskSpec

logger = get_logger("tasks.loader")


class TaskLoader:
    """Loader for benchmark tasks from task directories or hermetic YAML files."""

    @classmethod
    def load_task_from_dir(cls, task_dir: Path | str) -> TaskSpec:
        """Parse a task directory and construct a fully validated TaskSpec.

        Expects the directory to contain:
          - task.yaml (or metadata.yaml / rubric.yaml)
          - prompt.md (or prompt in task.yaml)
          - starter.py or starter.cpp (or starter_code in task.yaml)
          - test_visible.py or test_visible.cpp (or visible_tests in task.yaml)
          - optional test_hidden_stress.py / test_hidden_stress.cpp
          - optional solution.py / solution.cpp (canonical solution)

        Raises TaskNotFoundError (which inherits from ValueError) if files
        are missing or malformed.
        """
        path = Path(task_dir).resolve()
        if not path.exists():
            raise TaskNotFoundError(task_id=str(task_dir), message=f"Task directory '{task_dir}' does not exist.")

        if path.is_file():
            return cls.load_task_from_file(path)

        # 1. Discover task configuration YAML
        yaml_path: Path | None = None
        for candidate_name in ("task.yaml", "metadata.yaml"):
            candidate = path / candidate_name
            if candidate.is_file():
                yaml_path = candidate
                break

        if yaml_path is None:
            raise TaskNotFoundError(
                task_id=path.name,
                message=f"Missing metadata or task YAML file (task.yaml or metadata.yaml) in '{path}'.",
            )

        # 2. Parse main YAML file
        try:
            content = yaml_path.read_text(encoding="utf-8")
            data = yaml.safe_load(content)
        except yaml.YAMLError as exc:
            raise TaskNotFoundError(
                task_id=path.name,
                message=f"Malformed YAML in '{yaml_path}': {exc}",
            ) from exc
        except Exception as exc:
            raise TaskNotFoundError(
                task_id=path.name,
                message=f"Failed to read '{yaml_path}': {exc}",
            ) from exc

        if not isinstance(data, dict):
            raise TaskNotFoundError(
                task_id=path.name,
                message=f"Malformed YAML in '{yaml_path}': expected dictionary root.",
            )

        # 3. Check for auxiliary rubric.yaml if present
        rubric_file = path / "rubric.yaml"
        rubric_data: dict[str, Any] = {}
        if rubric_file.is_file():
            try:
                r_content = rubric_file.read_text(encoding="utf-8")
                parsed_r = yaml.safe_load(r_content)
                if isinstance(parsed_r, dict):
                    rubric_data = parsed_r
            except yaml.YAMLError as exc:
                raise TaskNotFoundError(
                    task_id=path.name,
                    message=f"Malformed YAML in '{rubric_file}': {exc}",
                ) from exc

        # 4. Extract metadata fields
        task_id = data.get("task_id") or data.get("id") or path.name
        if not task_id or not str(task_id).strip():
            raise TaskNotFoundError(
                task_id=path.name,
                message=f"Missing task identifier ('task_id' or 'id') in '{yaml_path}'.",
            )
        task_id = str(task_id).strip()
        title = str(data.get("title") or task_id).strip()

        # Determine language
        raw_lang = data.get("language")
        if raw_lang:
            norm_lang = str(raw_lang).strip().lower()
            language = "cpp" if norm_lang in ("c++", "cpp") else norm_lang
        else:
            # Auto-detect from file presence
            if (path / "starter.cpp").is_file() or (path / "test_visible.cpp").is_file():
                language = "cpp"
            else:
                language = "python"

        if language not in ("python", "cpp"):
            raise TaskNotFoundError(
                task_id=task_id,
                message=f"Unsupported language '{language}' in '{yaml_path}'. Must be 'python' or 'cpp'.",
            )

        ext = "cpp" if language == "cpp" else "py"

        # 5. Extract prompt
        prompt_file = path / "prompt.md"
        if prompt_file.is_file():
            prompt = prompt_file.read_text(encoding="utf-8").strip()
        elif "prompt" in data and str(data["prompt"]).strip():
            prompt = str(data["prompt"]).strip()
        else:
            raise TaskNotFoundError(
                task_id=task_id,
                message=f"Missing mandatory prompt: 'prompt.md' not found in '{path}' and 'prompt' not in YAML.",
            )

        # 6. Extract starter code
        starter_file = path / f"starter.{ext}"
        if not starter_file.is_file():
            for alt_ext in ("py", "cpp"):
                alt_candidate = path / f"starter.{alt_ext}"
                if alt_candidate.is_file():
                    starter_file = alt_candidate
                    break

        if starter_file.is_file():
            starter_code = starter_file.read_text(encoding="utf-8")
        elif "starter_code" in data and data["starter_code"] is not None:
            starter_code = str(data["starter_code"])
        else:
            raise TaskNotFoundError(
                task_id=task_id,
                message=(
                    f"Missing mandatory starter code: 'starter.{ext}' not found in '{path}' "
                    "and 'starter_code' not in YAML."
                ),
            )

        # 7. Extract visible tests
        visible_file = path / f"test_visible.{ext}"
        if not visible_file.is_file():
            for alt_ext in ("py", "cpp"):
                alt_candidate = path / f"test_visible.{alt_ext}"
                if alt_candidate.is_file():
                    visible_file = alt_candidate
                    break

        if visible_file.is_file():
            visible_tests = visible_file.read_text(encoding="utf-8")
        elif "visible_tests" in data and data["visible_tests"] is not None:
            raw_vt = data["visible_tests"]
            if isinstance(raw_vt, list):
                visible_tests = "\n\n".join(t.get("code", "") for t in raw_vt if isinstance(t, dict))
            else:
                visible_tests = str(raw_vt)
        else:
            raise TaskNotFoundError(
                task_id=task_id,
                message=(
                    f"Missing mandatory visible tests: 'test_visible.{ext}' not found in '{path}' "
                    "and 'visible_tests' not in YAML."
                ),
            )

        # 8. Extract hidden stress tests (optional)
        hidden_file = path / f"test_hidden_stress.{ext}"
        if not hidden_file.is_file():
            hidden_file = path / f"test_hidden.{ext}"
        if not hidden_file.is_file():
            for alt_ext in ("py", "cpp"):
                c1 = path / f"test_hidden_stress.{alt_ext}"
                c2 = path / f"test_hidden.{alt_ext}"
                if c1.is_file():
                    hidden_file = c1
                    break
                if c2.is_file():
                    hidden_file = c2
                    break

        if hidden_file.is_file():
            hidden_tests = hidden_file.read_text(encoding="utf-8")
        elif "hidden_tests" in data and data["hidden_tests"] is not None:
            raw_ht = data["hidden_tests"]
            if isinstance(raw_ht, list):
                hidden_tests = "\n\n".join(t.get("code", "") for t in raw_ht if isinstance(t, dict))
            else:
                hidden_tests = str(raw_ht)
        else:
            hidden_tests = ""

        # 9. Extract canonical reference solution (optional)
        solution_file = path / f"solution.{ext}"
        if not solution_file.is_file():
            solution_file = path / f"canonical_solution.{ext}"
        if not solution_file.is_file():
            for alt_ext in ("py", "cpp"):
                c1 = path / f"solution.{alt_ext}"
                c2 = path / f"canonical_solution.{alt_ext}"
                if c1.is_file():
                    solution_file = c1
                    break
                if c2.is_file():
                    solution_file = c2
                    break

        if solution_file.is_file():
            canonical_solution = solution_file.read_text(encoding="utf-8")
        elif "canonical_solution" in data and data["canonical_solution"] is not None:
            canonical_solution = str(data["canonical_solution"])
        elif "solution" in data and data["solution"] is not None:
            canonical_solution = str(data["solution"])
        else:
            canonical_solution = ""

        # 10. Rubric rules & limits
        rubric_rules: dict[str, Any] = {}
        if isinstance(data.get("rubric_rules"), dict):
            rubric_rules.update(data["rubric_rules"])
        elif isinstance(data.get("rubric"), dict):
            rubric_rules.update(data["rubric"])
        if rubric_data:
            rubric_rules.update(rubric_data)

        time_limit_sec = float(
            data.get("time_limit_sec")
            or data.get("timeout_sec")
            or data.get("timeout_seconds")
            or rubric_rules.get("timeout_sec")
            or 2.0
        )
        memory_limit_mb = int(
            data.get("memory_limit_mb")
            or rubric_rules.get("memory_limit_mb")
            or 256
        )
        difficulty = str(data.get("difficulty", "medium"))
        category = str(data.get("category", "algorithmic"))
        raw_tags = data.get("tags") or []
        tags = [str(t) for t in raw_tags] if isinstance(raw_tags, list) else [str(raw_tags)]

        # 11. Construct validated TaskSpec
        try:
            return TaskSpec(
                task_id=task_id,
                title=title,
                language=language,
                prompt=prompt,
                starter_code=starter_code,
                visible_tests=visible_tests,
                hidden_tests=hidden_tests,
                time_limit_sec=time_limit_sec,
                memory_limit_mb=memory_limit_mb,
                rubric_rules=rubric_rules,
                difficulty=difficulty,
                category=category,
                tags=tags,
                canonical_solution=canonical_solution,
            )
        except Exception as exc:
            raise TaskNotFoundError(
                task_id=task_id,
                message=f"Invalid task specification in '{path}': {exc}",
            ) from exc

    @classmethod
    def load_task_from_file(cls, yaml_path: Path | str) -> TaskSpec:
        """Parse a standalone hermetic YAML file into a TaskSpec."""
        path = Path(yaml_path).resolve()
        if not path.is_file():
            raise TaskNotFoundError(task_id=str(yaml_path), message=f"Task file '{yaml_path}' not found.")

        try:
            content = path.read_text(encoding="utf-8")
            data = yaml.safe_load(content)
        except yaml.YAMLError as exc:
            raise TaskNotFoundError(task_id=path.stem, message=f"Malformed YAML in '{path}': {exc}") from exc
        except Exception as exc:
            raise TaskNotFoundError(task_id=path.stem, message=f"Failed to read '{path}': {exc}") from exc

        if not isinstance(data, dict):
            raise TaskNotFoundError(task_id=path.stem, message=f"Malformed YAML in '{path}': expected mapping root.")

        task_id = str(data.get("task_id") or data.get("id") or path.stem).strip()
        title = str(data.get("title") or task_id).strip()

        raw_lang = data.get("language", "python")
        norm_lang = str(raw_lang).strip().lower()
        language = "cpp" if norm_lang in ("c++", "cpp") else norm_lang

        prompt = str(data.get("prompt", "")).strip()
        if not prompt:
            raise TaskNotFoundError(task_id=task_id, message=f"Missing prompt in '{path}'.")

        starter_code = str(data.get("starter_code", ""))

        visible_tests = data.get("visible_tests", "")
        if isinstance(visible_tests, list):
            visible_tests = "\n\n".join(t.get("code", "") for t in visible_tests if isinstance(t, dict))
        else:
            visible_tests = str(visible_tests)

        hidden_tests = data.get("hidden_tests", "")
        if isinstance(hidden_tests, list):
            hidden_tests = "\n\n".join(t.get("code", "") for t in hidden_tests if isinstance(t, dict))
        else:
            hidden_tests = str(hidden_tests)

        canonical_solution = str(data.get("canonical_solution") or data.get("solution") or "")
        rubric_rules = data.get("rubric_rules") or data.get("rubric") or {}

        time_limit_sec = float(
            data.get("time_limit_sec")
            or data.get("timeout_sec")
            or data.get("timeout_seconds")
            or 2.0
        )
        memory_limit_mb = int(data.get("memory_limit_mb", 256))
        difficulty = str(data.get("difficulty", "medium"))
        category = str(data.get("category", "algorithmic"))
        raw_tags = data.get("tags") or []
        tags = [str(t) for t in raw_tags] if isinstance(raw_tags, list) else [str(raw_tags)]

        try:
            return TaskSpec(
                task_id=task_id,
                title=title,
                language=language,
                prompt=prompt,
                starter_code=starter_code,
                visible_tests=visible_tests,
                hidden_tests=hidden_tests,
                time_limit_sec=time_limit_sec,
                memory_limit_mb=memory_limit_mb,
                rubric_rules=rubric_rules,
                difficulty=difficulty,
                category=category,
                tags=tags,
                canonical_solution=canonical_solution,
            )
        except Exception as exc:
            raise TaskNotFoundError(
                task_id=task_id,
                message=f"Invalid task specification in '{path}': {exc}",
            ) from exc


def load_task_from_dir(task_dir: Path | str) -> TaskSpec:
    """Convenience functional wrapper for TaskLoader.load_task_from_dir."""
    return TaskLoader.load_task_from_dir(task_dir)


class TaskRegistry:
    """In-memory benchmark task registry."""

    def __init__(self, loader: TaskLoader | None = None) -> None:
        self.loader = loader or TaskLoader()
        self._tasks: dict[str, TaskSpec] = {}

    def register(self, task: TaskSpec) -> None:
        """Register or override a task in the registry."""
        self._tasks[task.task_id] = task

    def get(self, task_id: str) -> TaskSpec:
        """Retrieve a task by ID, raising TaskNotFoundError if missing."""
        if task_id not in self._tasks:
            raise TaskNotFoundError(task_id=task_id)
        return self._tasks[task_id]

    def get_task(self, task_id: str) -> TaskSpec:
        """Alias for get(task_id)."""
        return self.get(task_id)

    def list_tasks(
        self,
        language: str | None = None,
        category: str | None = None,
        difficulty: str | None = None,
    ) -> list[TaskSpec]:
        """List registered tasks with optional filtering."""
        tasks = list(self._tasks.values())
        if language is not None:
            norm_lang = "cpp" if language.strip().lower() in ("c++", "cpp") else language.strip().lower()
            tasks = [t for t in tasks if t.language.lower() == norm_lang]
        if category is not None:
            norm_cat = category.strip().lower()
            tasks = [t for t in tasks if getattr(t, "category", "").lower() == norm_cat]
        if difficulty is not None:
            norm_diff = difficulty.strip().lower()
            tasks = [t for t in tasks if getattr(t, "difficulty", "").lower() == norm_diff]
        return tasks

    def get_public_spec(self, task_id: str) -> dict[str, Any]:
        """Retrieve public specification for a task omitting hidden tests and solution."""
        return self.get(task_id).get_public_spec()

    def clear(self) -> None:
        """Clear all registered tasks."""
        self._tasks.clear()

    def __len__(self) -> int:
        return len(self._tasks)

    def __contains__(self, task_id: str) -> bool:
        return task_id in self._tasks

    def load_tasks_from_directory(self, root_dir: Path | str) -> int:
        """Recursively discover and register all valid task directories under root_dir."""
        root_path = Path(root_dir).resolve()
        if not root_path.exists():
            raise TaskNotFoundError(task_id=str(root_dir), message=f"Task root directory '{root_dir}' does not exist.")

        initial_count = len(self._tasks)

        if root_path.is_file():
            try:
                task = (
                    self.loader.load_task_from_dir(root_path.parent)
                    if root_path.name in ("task.yaml", "metadata.yaml")
                    else self.loader.load_task_from_file(root_path)
                )
                self.register(task)
                return 1
            except Exception as exc:
                logger.warning(f"Failed to load task from '{root_path}': {exc}")
                return 0

        # Discover directories containing task.yaml or metadata.yaml
        candidate_dirs: list[Path] = []
        if (root_path / "task.yaml").is_file() or (root_path / "metadata.yaml").is_file():
            candidate_dirs.append(root_path)

        for yaml_path in sorted(root_path.glob("**/task.yaml")):
            if yaml_path.parent not in candidate_dirs:
                candidate_dirs.append(yaml_path.parent)

        for yaml_path in sorted(root_path.glob("**/metadata.yaml")):
            if yaml_path.parent not in candidate_dirs:
                candidate_dirs.append(yaml_path.parent)

        for task_dir in candidate_dirs:
            try:
                task = self.loader.load_task_from_dir(task_dir)
                self.register(task)
            except Exception as exc:
                logger.warning(f"Failed to load task from directory '{task_dir}': {exc}")

        # Also search for standalone *.yaml task files
        for standalone_yaml in sorted(root_path.glob("**/*.yaml")):
            if standalone_yaml.name in ("task.yaml", "metadata.yaml", "rubric.yaml"):
                continue
            if standalone_yaml.parent in candidate_dirs:
                continue
            try:
                task = self.loader.load_task_from_file(standalone_yaml)
                self.register(task)
            except Exception as exc:
                logger.debug(f"Skipping non-task YAML '{standalone_yaml}': {exc}")

        return len(self._tasks) - initial_count


_GLOBAL_REGISTRY: TaskRegistry | None = None


def get_global_registry() -> TaskRegistry:
    """Return the global singleton TaskRegistry instance."""
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is None:
        _GLOBAL_REGISTRY = TaskRegistry()
    return _GLOBAL_REGISTRY


def reset_global_registry() -> None:
    """Reset the global singleton TaskRegistry instance."""
    global _GLOBAL_REGISTRY
    if _GLOBAL_REGISTRY is not None:
        _GLOBAL_REGISTRY.clear()
    _GLOBAL_REGISTRY = None


__all__ = [
    "TaskLoader",
    "TaskRegistry",
    "load_task_from_dir",
    "get_global_registry",
    "reset_global_registry",
]
