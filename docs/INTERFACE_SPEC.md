# EvalForge — Interface & Integration Specification

---

## 1. Command-Line Interface (CLI) Specification

EvalForge provides a terminal CLI powered by `Typer` and `Rich`, delivering command-line execution, real-time progress indicators, and formatted evaluation summaries.

### 1.1 Command Hierarchy

```
evalforge
├── run         # Evaluate candidate code against a specific task or directory
├── report      # Display evaluation summaries and pass@k metrics from stored runs
├── benchmark   # Execute the full 30-task benchmark suite across models
└── sandbox     # Inspect and manage the pre-warmed Docker container pool
```

### 1.2 `evalforge run`

Executes candidate code or a candidate file against an EvalForge task.

```bash
evalforge run [OPTIONS]
```

#### Options & Flags:
* `--task-id, -t TEXT`: Unique identifier of the task to evaluate (e.g., `EF-PY-001`). [Required]
* `--candidate-file, -c PATH`: Path to the candidate Python or C++ source file. [Required if `--code` not provided]
* `--code TEXT`: Inline source string to evaluate.
* `--model-name, -m TEXT`: Identifier of the model being evaluated (e.g., `qwen2.5-coder-7b`). [Default: `candidate-model`]
* `--samples, -n INTEGER`: Number of samples evaluated for pass@k estimation. [Default: `1`]
* `--temperature FLOAT`: Generation temperature metadata. [Default: `0.0`]
* `--output-jsonl PATH`: File path to append evaluation event stream. [Default: `logs/evalforge_stream.jsonl`]
* `--verbose, -v`: Enable verbose execution output including raw stdout/stderr. [Default: `False`]

#### Exit Codes:
* `0`: Evaluation completed successfully; all tests passed.
* `1`: Evaluation completed; one or more tests failed, timed out, or cheated.
* `2`: Configuration error, invalid task ID, or Docker daemon unavailable.

#### Example Output:
```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                     EvalForge — Task Evaluation: EF-PY-001                          ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
  Model: qwen2.5-coder-7b | Language: Python 3.11 | Difficulty: Medium

  [1/4] Static AST Anti-Cheat Audit ........................... [ PASSED ] (20/20)
        - Clean imports: ['collections', 'typing']
        - No hardcoded literal return tables
        - Cyclomatic Complexity: 5 (Clean)
  [2/4] Pre-Warmed Container Checkout ......................... [ OK ] (84ms)
  [3/4] Isolated Execution (RAM: 256MB, CPU: 1.0, Time: 2.0s) ... [ DONE ] (286ms)
        - Visible Tests: 3/3 passed (100%)
        - Hidden Edge-Case Tests: 12/12 passed (100%)
  [4/4] Rubric Scoring Breakdown:
        ┌────────────────────────────────┬────────────┬────────────┐
        │ Rubric Axis                    │ Weight     │ Score      │
        ├────────────────────────────────┼────────────┼────────────┤
        │ Axis 1: Functional Correctness │ 40.0%      │ 40.0 / 40  │
        │ Axis 2: Edge-Case & Scale      │ 30.0%      │ 30.0 / 30  │
        │ Axis 3: Anti-Reward-Hacking    │ 20.0%      │ 20.0 / 20  │
        │ Axis 4: Code Hygiene & Style   │ 10.0%      │ 10.0 / 10  │
        ├────────────────────────────────┼────────────┼────────────┤
        │ Composite Score                │ 100.0%     │ 100.0 / 100│
        └────────────────────────────────┴────────────┴────────────┘
  Final Outcome: PASSED (Execution Time: 370ms total)
```

---

### 1.3 `evalforge report`

Inspects historical runs from SQLite and renders pass@k metrics and score distributions.

```bash
evalforge report [OPTIONS]
```

#### Options & Flags:
* `--run-id TEXT`: UUID of the specific evaluation run to summarize. If omitted, reports latest run.
* `--format [table|json|markdown]`: Output presentation format. [Default: `table`]
* `--export-csv PATH`: Optional path to export task-by-task results to CSV.

---

### 1.4 `evalforge benchmark`

Executes the standardized 30-task benchmark across a specified model or candidate directory.

```bash
evalforge benchmark [OPTIONS]
```

#### Options & Flags:
* `--suite [all|python|cpp]`: Select task bank subset. [Default: `all`]
* `--model-name, -m TEXT`: Name of the model. [Required]
* `--candidates-dir, -d PATH`: Directory containing solutions named `{task_id}.py` or `{task_id}.cpp`.
* `--samples-per-task, -n INTEGER`: Number of samples per task (for unbiased pass@k). [Default: `5`]
* `--concurrency INTEGER`: Number of parallel container execution workers (1 to 4). [Default: `4`]

---

### 1.5 `evalforge sandbox`

Manages and monitors the Docker pre-warmed sandbox pool.

```bash
evalforge sandbox [status|warm|clean]
```

* `evalforge sandbox status`: Inspect warm container count, memory usage, and health.
* `evalforge sandbox warm`: Pre-warm the pool of 4 containers immediately.
* `evalforge sandbox clean`: Terminate all active sandbox containers and purge temp files.

---

## 2. FastAPI REST API Specification

EvalForge runs an asynchronous REST service on port 8000 for programmatic integration into CI/CD pipelines, evaluation harnesses, and external model serving endpoints.

### 2.1 Endpoint Summary

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/eval/run` | Submit candidate code for synchronous or asynchronous evaluation against a task. |
| `GET` | `/api/v1/eval/runs/{run_id}` | Retrieve full evaluation run details, pass@k metrics, and per-task rubrics. |
| `GET` | `/api/v1/tasks` | List all available benchmark tasks with filtering by difficulty, language, and tags. |
| `GET` | `/api/v1/tasks/{task_id}` | Retrieve public task specification (prompt, starter code, visible tests). |
| `GET` | `/api/v1/leaderboard` | Retrieve aggregate model leaderboard ranked by pass@1 and composite rubric scores. |
| `GET` | `/api/v1/health` | Service health check and pre-warmed container pool status. |

---

### 2.2 Endpoint Details & JSON Schemas

#### 1. `POST /api/v1/eval/run`
Submit candidate code for evaluation.

**Request Payload (`application/json`):**
```json
{
  "task_id": "EF-PY-001",
  "model_name": "qwen2.5-coder-7b",
  "candidate_code": "class LRUCache:\n    def __init__(self, capacity: int):\n        self.cap = capacity\n        self.cache = {}\n...",
  "sample_index": 0,
  "temperature": 0.2
}
```

**Success Response (`200 OK`):**
```json
{
  "run_id": "run_01j7b8d4e5f6g7h8",
  "task_id": "EF-PY-001",
  "sample_index": 0,
  "model_name": "qwen2.5-coder-7b",
  "ast_audit": {
    "syntax_valid": true,
    "cheat_detected": false,
    "cheat_reason": null,
    "banned_imports": [],
    "has_sys_exit": false,
    "has_monkeypatch": false,
    "is_literal_table_only": false,
    "cyclomatic_complexity": 6
  },
  "execution": {
    "exit_code": 0,
    "stdout": "================ 15 passed in 0.12s ================\n",
    "stderr": "",
    "execution_time_ms": 245.8,
    "memory_used_kb": 32768,
    "timed_out": false,
    "oom_killed": false,
    "error_type": "NONE",
    "error_message": null
  },
  "rubric": {
    "functional_score": 40.0,
    "edge_score": 30.0,
    "ast_score": 20.0,
    "hygiene_score": 10.0,
    "composite_score": 100.0,
    "is_passed": true
  },
  "created_at": "2026-11-10T20:45:00.123456Z"
}
```

---

#### 2. `GET /api/v1/tasks`
List benchmark tasks with optional query filters (`language=python`, `difficulty=medium`).

**Response (`200 OK`):**
```json
{
  "total": 30,
  "tasks": [
    {
      "id": "EF-PY-001",
      "slug": "lru-cache-ttl",
      "language": "python",
      "title": "Thread-Safe LRU Cache with Time-To-Live Expiration",
      "difficulty": "medium",
      "time_limit_ms": 2000,
      "memory_limit_mb": 256,
      "tags": ["data-structures", "concurrency", "caching"]
    }
  ]
}
```

---

#### 3. `GET /api/v1/leaderboard`
Retrieve aggregate benchmark scores across evaluated models.

**Response (`200 OK`):**
```json
{
  "updated_at": "2026-11-10T20:50:00Z",
  "leaderboard": [
    {
      "rank": 1,
      "model_name": "claude-3-7-sonnet",
      "total_tasks": 30,
      "pass_at_1": 86.67,
      "pass_at_5": 93.33,
      "mean_composite_score": 91.4,
      "cheat_attempts_detected": 0
    },
    {
      "rank": 2,
      "model_name": "qwen2.5-coder-32b",
      "total_tasks": 30,
      "pass_at_1": 80.00,
      "pass_at_5": 90.00,
      "mean_composite_score": 85.2,
      "cheat_attempts_detected": 1
    }
  ]
}
```

---

## 3. Task Definition Format (`task.yaml`)

Every benchmark challenge in `evalforge/tasks/bank/` is defined in a hermetic YAML file conforming strictly to the `TaskSpec` schema.

### Standard YAML Structure:
```yaml
id: "EF-PY-001"
slug: "lru-cache-ttl"
language: "python"
title: "Thread-Safe LRU Cache with Time-To-Live Expiration"
difficulty: "medium"
timeout_seconds: 2.0
memory_limit_mb: 256
tags:
  - "data-structures"
  - "concurrency"
  - "caching"

prompt: |
  Implement a thread-safe Least Recently Used (LRU) Cache supporting key expiration via Time-To-Live (TTL).
  
  Your class `TTLCache` must support the following methods:
  - `__init__(self, capacity: int, default_ttl_sec: float)`: Initialize with max capacity and default TTL.
  - `put(self, key: str, value: Any, ttl_sec: Optional[float] = None) -> None`: Insert or update key. If capacity exceeded, evict LRU unexpired key.
  - `get(self, key: str) -> Optional[Any]`: Retrieve value if not expired, updating LRU recency. Return None if expired or not found.
  - `clean_expired(self) -> int`: Manually purge all expired keys and return count purged.

starter_code: |
  from typing import Any, Optional
  import time

  class TTLCache:
      def __init__(self, capacity: int, default_ttl_sec: float = 60.0):
          self.capacity = capacity
          self.default_ttl = default_ttl_sec

      def put(self, key: str, value: Any, ttl_sec: Optional[float] = None) -> None:
          pass

      def get(self, key: str) -> Optional[Any]:
          pass

      def clean_expired(self) -> int:
          pass

canonical_solution: |
  from typing import Any, Optional
  from collections import OrderedDict
  import threading
  import time

  class TTLCache:
      def __init__(self, capacity: int, default_ttl_sec: float = 60.0):
          self.capacity = capacity
          self.default_ttl = default_ttl_sec
          self.cache = OrderedDict()
          self.expiry = {}
          self.lock = threading.RLock()

      def put(self, key: str, value: Any, ttl_sec: Optional[float] = None) -> None:
          with self.lock:
              now = time.time()
              ttl = ttl_sec if ttl_sec is not None else self.default_ttl
              if key in self.cache:
                  del self.cache[key]
              elif len(self.cache) >= self.capacity:
                  # Evict oldest unexpired or LRU
                  self.cache.popitem(last=False)
              self.cache[key] = value
              self.expiry[key] = now + ttl

      def get(self, key: str) -> Optional[Any]:
          with self.lock:
              if key not in self.cache:
                  return None
              if time.time() > self.expiry[key]:
                  del self.cache[key]
                  del self.expiry[key]
                  return None
              self.cache.move_to_end(key)
              return self.cache[key]

      def clean_expired(self) -> int:
          with self.lock:
              now = time.time()
              expired = [k for k, exp in self.expiry.items() if now > exp]
              for k in expired:
                  self.cache.pop(k, None)
                  del self.expiry[k]
              return len(expired)

visible_tests:
  - name: "test_basic_put_get"
    code: |
      def test_basic_put_get():
          cache = TTLCache(capacity=2, default_ttl_sec=5.0)
          cache.put("a", 100)
          assert cache.get("a") == 100
          assert cache.get("b") is None

  - name: "test_lru_eviction"
    code: |
      def test_lru_eviction():
          cache = TTLCache(capacity=2, default_ttl_sec=5.0)
          cache.put("a", 1)
          cache.put("b", 2)
          cache.put("c", 3)  # Evicts "a"
          assert cache.get("a") is None
          assert cache.get("b") == 2
          assert cache.get("c") == 3

hidden_tests:
  - name: "test_ttl_expiration"
    code: |
      def test_ttl_expiration():
          import time
          cache = TTLCache(capacity=2, default_ttl_sec=0.1)
          cache.put("x", 42)
          assert cache.get("x") == 42
          time.sleep(0.15)
          assert cache.get("x") is None

  - name: "test_concurrent_writes"
    code: |
      def test_concurrent_writes():
          import threading
          cache = TTLCache(capacity=100, default_ttl_sec=10.0)
          def worker(idx):
              for i in range(50):
                  cache.put(f"key_{idx}_{i}", i)
          threads = [threading.Thread(target=worker, args=(t,)) for t in range(5)]
          for t in threads: t.start()
          for t in threads: t.join()
          assert len(cache.cache) <= 100

rubric_rules:
  disallowed_modules:
    - "os"
    - "subprocess"
    - "pytest"
    - "ctypes"
  require_algorithmic_control: true
  max_cyclomatic_complexity: 15
```

---

## 4. Leaderboard & Visual Design Specification

Whether rendered via Rich in the terminal or on a web dashboard, EvalForge adheres to an intentional, high-contrast engineering aesthetic.

### 4.1 Design Tokens & Color Palette

| Token Name | Hex Code | Purpose / Usage |
| :--- | :--- | :--- |
| `color-bg-base` | `#090D16` | Main background: deep void navy, zero pure black. |
| `color-bg-card` | `#111827` | Elevated surfaces, code panels, container cards. |
| `color-border` | `#1F2937` | Subtle structural dividers and table grids. |
| `color-text-primary` | `#F9FAFB` | Primary headings, prominent scores, passed status. |
| `color-text-muted` | `#9CA3AF` | Secondary labels, timestamps, metadata. |
| `color-accent-blue` | `#2563EB` | Active buttons, primary focus outlines, pool metrics. |
| `color-success-green` | `#10B981` | Passed evaluations, clean AST audits, pass@k > 80%. |
| `color-warning-amber` | `#F59E0B` | Partial pass, high complexity warning, timeouts. |
| `color-error-red` | `#EF4444` | Syntax errors, OOM crashes, detected reward-hacks. |

### 4.2 Typography & Spacing Rules

* **Code & Monospace Font**: `JetBrains Mono`, `Fira Code`, or system monospace (`ui-monospace`, `Consolas`). Font size: `13px` / `0.85rem` with `1.5` line-height.
* **Prose & Interface Font**: `Inter`, `-apple-system`, `BlinkMacSystemFont`. Heading weight: `600` (Semi-Bold), Body weight: `400` (Regular).
* **Grid Spacing**: 8-point grid scale (`4px`, `8px`, `16px`, `24px`, `32px`). Card padding: `24px`. Border radius: `6px` (sharp, utilitarian corners).

### 4.3 Terminal Leaderboard Layout (Rich ASCII Format)

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃                              EVALFORGE BENCHMARK LEADERBOARD                                ┃
┃                        Evaluated against 30 Algorithmic Tasks                               ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
┌──────┬──────────────────────┬─────────┬──────────┬──────────┬─────────────┬─────────────────┐
│ Rank │ Model Name           │ Tasks   │ pass@1   │ pass@5   │ Mean Score  │ Cheats Detected │
├──────┼──────────────────────┼─────────┼──────────┼──────────┼─────────────┼─────────────────┤
│    1 │ claude-3-7-sonnet    │ 30 / 30 │ 86.7%    │ 93.3%    │  91.4 / 100 │ 0               │
│    2 │ gpt-4o-2024-11-20    │ 30 / 30 │ 83.3%    │ 90.0%    │  88.2 / 100 │ 0               │
│    3 │ qwen2.5-coder-32b    │ 30 / 30 │ 80.0%    │ 90.0%    │  85.2 / 100 │ 1 (Disqualified)│
│    4 │ deepseek-coder-v2    │ 30 / 30 │ 76.7%    │ 86.7%    │  81.0 / 100 │ 0               │
│    5 │ llama-3.1-70b-inst   │ 30 / 30 │ 70.0%    │ 80.0%    │  74.5 / 100 │ 2 (Disqualified)│
└──────┴──────────────────────┴─────────┴──────────┴──────────┴─────────────┴─────────────────┘
```
