"""Integration tests for EvalForge FastAPI REST API."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from evalforge.api.app import create_app
from evalforge.core.config import Settings
from evalforge.models.schemas import TaskSpec
from evalforge.tasks.loader import TaskRegistry


@pytest.fixture
def mock_settings(tmp_path: Path) -> Settings:
    """Fixture providing isolated Settings pointing to temporary database and log paths."""
    db_file = tmp_path / "test_api.db"
    log_dir = tmp_path / "test_logs"
    return Settings(
        db_path=str(db_file),
        audit_log_dir=str(log_dir),
        docker_pool_size=2,
    )


@pytest.fixture
def test_task() -> TaskSpec:
    """Fixture providing a standard test task."""
    return TaskSpec(
        task_id="EF-PY-001",
        title="Thread-Safe LRU Cache with TTL",
        language="python",
        difficulty="medium",
        category="concurrency",
        tags=["caching", "concurrency"],
        prompt="Implement a thread-safe LRU Cache with TTL.",
        starter_code="class TTLCache:\n    def __init__(self, capacity: int): pass\n",
        canonical_solution="class TTLCache:\n    def __init__(self, capacity: int): self.cap = capacity\n",
        visible_tests="def test_basic(): pass\n",
        hidden_tests="def test_hidden(): pass\n",
        rubric_rules={"banned_imports": ["subprocess", "socket"]},
        time_limit_sec=2.0,
        memory_limit_mb=256,
    )


@pytest.fixture
def client(mock_settings: Settings, test_task: TaskSpec) -> TestClient:
    """Fixture providing a configured FastAPI TestClient with initialized state."""
    app = create_app(mock_settings)

    # Initialize task registry with test task
    registry = TaskRegistry()
    registry.register(test_task)
    app.state.task_registry = registry

    # Mock container pool manager so tests don't require live Docker daemon
    mock_pool = MagicMock()
    mock_pool.is_docker_available.return_value = True
    mock_pool.pool_size = 2
    mock_pool.available_count = 2
    mock_pool.active_count = 0

    mock_container = MagicMock()
    mock_container.id = "mock_c_001"

    async def mock_checkout(language="python"):
        return mock_container

    async def mock_checkin(container):
        pass

    async def mock_cleanup():
        pass

    mock_pool.checkout = mock_checkout
    mock_pool.checkin = mock_checkin
    mock_pool.cleanup = mock_cleanup
    app.state.pool_manager = mock_pool


    with TestClient(app) as test_client:
        yield test_client


def test_root_endpoint(client: TestClient):
    """Verify root endpoint returns service info."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "EvalForge"
    assert "/docs" in data["docs"]


def test_health_endpoint(client: TestClient):
    """Verify health endpoint returns pool status."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ("healthy", "degraded")
    assert data["pool_size"] == 2
    assert "timestamp" in data


def test_list_tasks_and_filtering(client: TestClient):
    """Verify task listing and query parameter filtering."""
    response = client.get("/api/v1/tasks")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert data["tasks"][0]["id"] == "EF-PY-001"

    # Filter by language python
    py_resp = client.get("/api/v1/tasks?language=python")
    assert py_resp.status_code == 200
    assert py_resp.json()["total"] >= 1

    # Filter by non-existent language
    empty_resp = client.get("/api/v1/tasks?language=rust")
    assert empty_resp.status_code == 200
    assert empty_resp.json()["total"] == 0


def test_get_task_by_id_sanitizes_hidden_tests(client: TestClient):
    """Verify get task by ID never leaks hidden_tests or canonical_solution."""
    response = client.get("/api/v1/tasks/EF-PY-001")
    assert response.status_code == 200
    data = response.json()
    assert data["task_id"] == "EF-PY-001"
    assert "starter_code" in data
    assert "visible_tests" in data
    assert "hidden_tests" not in data
    assert "canonical_solution" not in data

    # 404 for non-existent task
    not_found = client.get("/api/v1/tasks/EF-NONEXISTENT")
    assert not_found.status_code == 404


def test_submit_valid_evaluation(client: TestClient):
    """Verify submitting a valid solution passes evaluation and persists results."""
    valid_code = (
        "class TTLCache:\n"
        "    def __init__(self, capacity: int):\n"
        "        self.cap = capacity\n"
        "        self.cache = {}\n"
        "    def put(self, k, v):\n"
        "        self.cache[k] = v\n"
        "    def get(self, k):\n"
        "        return self.cache.get(k)\n"
    )
    payload = {
        "task_id": "EF-PY-001",
        "model_name": "qwen2.5-coder-7b",
        "candidate_code": valid_code,
        "sample_index": 0,
    }
    response = client.post("/api/v1/eval/run", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["task_id"] == "EF-PY-001"
    assert data["model_name"] == "qwen2.5-coder-7b"
    assert data["ast_audit"]["cheat_detected"] is False
    assert data["ast_audit"]["syntax_valid"] is True
    assert "run_id" in data
    assert "rubric" in data

    # Query the run by run_id
    run_id = data["run_id"]
    run_resp = client.get(f"/api/v1/eval/runs/{run_id}")
    assert run_resp.status_code == 200
    run_data = run_resp.json()
    assert run_data["run_id"] == run_id
    assert len(run_data["evaluations"]) >= 1


def test_submit_cheat_evaluation_caught(client: TestClient):
    """Verify AST anti-cheat traps banned imports and marks cheat_detected."""
    cheating_code = (
        "import subprocess\n"
        "import sys\n"
        "sys.exit(0)\n"
    )
    payload = {
        "task_id": "EF-PY-001",
        "model_name": "adversarial-agent",
        "candidate_code": cheating_code,
    }
    response = client.post("/api/v1/eval/run", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["ast_audit"]["cheat_detected"] is True
    assert data["rubric"]["composite_score"] <= 30.0
    assert data["rubric"]["is_passed"] is False


def test_submit_evaluation_nonexistent_task(client: TestClient):
    """Verify submitting evaluation for nonexistent task returns 404."""
    payload = {
        "task_id": "EF-UNKNOWN-999",
        "candidate_code": "def solve(): pass",
    }
    response = client.post("/api/v1/eval/run", json=payload)
    assert response.status_code == 404


def test_leaderboard_endpoint(client: TestClient):
    """Verify leaderboard endpoint returns structured model rankings."""
    # First submit an evaluation so database has data
    client.post(
        "/api/v1/eval/run",
        json={
            "task_id": "EF-PY-001",
            "model_name": "claude-3-7-sonnet",
            "candidate_code": "class TTLCache: pass",
        },
    )
    response = client.get("/api/v1/leaderboard")
    assert response.status_code == 200
    data = response.json()
    assert "leaderboard" in data
    assert "updated_at" in data
    assert len(data["leaderboard"]) >= 1
    assert data["leaderboard"][0]["model_name"] == "claude-3-7-sonnet"
