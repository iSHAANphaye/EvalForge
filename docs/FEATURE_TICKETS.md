# EvalForge — Feature Build Tickets

This document breaks down the entire implementation of **EvalForge** into 12 atomic, sequential, and fully specified engineering tickets. Each ticket is structured as an actionable prompt for an AI coding assistant or software engineer.

---

### TICKET-EF-001: Core Configuration, Typed Exceptions & Logging Infrastructure

* **Priority**: Must-Have
* **Dependencies**: None
* **Target File Paths**:
  - `evalforge/core/config.py`
  - `evalforge/core/constants.py`
  - `evalforge/core/exceptions.py`
  - `evalforge/core/__init__.py`
  - `pyproject.toml`
  - `tests/test_config.py`

#### Task Description (AI Coding Prompt):
> Configure the project root `pyproject.toml` with dependencies: `fastapi`, `uvicorn[standard]`, `pydantic>=2.8`, `pydantic-settings`, `docker>=7.1`, `typer>=0.12`, `rich>=13.7`, `aiosqlite`, `pytest>=8.0`, `pyyaml`.
> Implement `evalforge/core/config.py` using `pydantic_settings.BaseSettings` to parse environment variables defined in `ARCHITECTURE.md` (e.g. `EVALFORGE_DOCKER_POOL_SIZE`, `EVALFORGE_RAM_LIMIT_MB=256`, `EVALFORGE_EXEC_TIMEOUT_SEC=2.0`, `EVALFORGE_DB_PATH`).
> Implement `evalforge/core/constants.py` defining standard rubric weights (40% functional, 30% edge, 20% AST, 10% hygiene) and exit codes.
> Implement `evalforge/core/exceptions.py` defining a clear hierarchy: `EvalForgeError`, `SandboxError`, `ExecutionTimeoutError`, `MemoryExhaustionError`, `CheatDetectedError`, `TaskNotFoundError`, and `PatchApplicationError`.
> Write unit tests in `tests/test_config.py` verifying default settings and custom `.env` overrides.

#### Acceptance Criteria:
- [ ] `pyproject.toml` defines all required runtime and dev dependencies with Python `>=3.11`.
- [ ] `evalforge.core.config.Settings` validates all sandbox, database, and timeout settings with sensible defaults.
- [ ] Typed domain exception hierarchy in `exceptions.py` covers all sandbox and evaluation failure modes.
- [ ] `tests/test_config.py` runs and passes with `pytest tests/test_config.py`.

---

### TICKET-EF-002: Hardened Docker Sandbox Container Images

* **Priority**: Must-Have
* **Dependencies**: TICKET-EF-001
* **Target File Paths**:
  - `Dockerfile.sandbox.python`
  - `Dockerfile.sandbox.cpp`
  - `scripts/build_sandboxes.py`

#### Task Description (AI Coding Prompt):
> Author minimal, hardened Dockerfiles for running Python 3.11 and C++20 code under test.
> `Dockerfile.sandbox.python`: Base image `python:3.11-slim-bookworm`. Create an unprivileged user `sandbox_user` (UID 10001). Install `pytest>=8.0` and `pytest-json-report`. Set working directory `/workspace/run` owned by `sandbox_user`. Provide default entrypoint keeping container running (`sleep infinity`).
> `Dockerfile.sandbox.cpp`: Base image `gcc:13-bookworm` or `debian:bookworm-slim` with `g++`, `cmake`, and `libgtest-dev`. Create `sandbox_user` (UID 10001).
> Create a Python script `scripts/build_sandboxes.py` that utilizes `docker-py` to check for and build both images tagged as `evalforge-sandbox-python:latest` and `evalforge-sandbox-cpp:latest`.

#### Acceptance Criteria:
- [ ] `Dockerfile.sandbox.python` creates non-root user `10001:10001` with no sudo permissions.
- [ ] Python sandbox image includes pre-installed `pytest` and `pytest-json-report`.
- [ ] `Dockerfile.sandbox.cpp` compiles C++20 code with `-std=c++20` and links Google Test.
- [ ] `scripts/build_sandboxes.py` successfully triggers docker build via Docker SDK.

---

### TICKET-EF-003: Pre-Warmed Docker Container Pool Manager

* **Priority**: Must-Have
* **Dependencies**: TICKET-EF-001, TICKET-EF-002
* **Target File Paths**:
  - `evalforge/sandbox/manager.py`
  - `evalforge/sandbox/cleaner.py`
  - `tests/test_sandbox_pool.py`

#### Task Description (AI Coding Prompt):
> Implement `SandboxPoolManager` in `evalforge/sandbox/manager.py` using `docker` Python SDK.
> The manager must initialize and maintain a pool of `N=4` running containers with strict sandbox limits: `network_mode="none"`, `mem_limit="256m"`, `memswap_limit="256m"`, `cpu_period=100000`, `cpu_quota=100000`, `pids_limit=64`, `cap_drop=["ALL"]`, `security_opt=["no-new-privileges:true"]`, `read_only=True`, `user="10001:10001"`, and tmpfs mounts for `/workspace/run` and `/tmp`.
> Use an `asyncio.Queue` or `queue.Queue` with a semaphore for thread-safe container checkout (`acquire()`) and checkin (`release()`).
> In `evalforge/sandbox/cleaner.py`, implement `sanitize_container()` which executes `pkill -u 10001 -9` and purges `/workspace/run/*`. If container is dead or OOM-killed, destroy it and spawn a fresh replacement container.
> Implement unit tests in `tests/test_sandbox_pool.py` using a mock Docker client verifying acquire, release, OOM replacement, and pool size invariants.

#### Acceptance Criteria:
- [ ] Pre-warmed pool starts 4 containers with specified sandbox constraints.
- [ ] Container checkout latency is sub-150ms.
- [ ] `sanitize_container()` wipes workspace files and terminates child processes.
- [ ] Degraded/OOM containers are automatically purged and replaced asynchronously.
- [ ] Unit tests pass cleanly with 100% assertion coverage on queue state.

---

### TICKET-EF-004: Execution Engine & Subprocess Watchdog

* **Priority**: Must-Have
* **Dependencies**: TICKET-EF-003
* **Target File Paths**:
  - `evalforge/sandbox/runner.py`
  - `evalforge/sandbox/isolation.py`
  - `tests/test_sandbox_runner.py`

#### Task Description (AI Coding Prompt):
> Build `DockerExecutionEngine` in `evalforge/sandbox/runner.py`.
> The runner accepts a checked-out container, candidate source code, and a test harness. It writes the files into the container's tmpfs `/workspace/run/` using `put_archive()` (tar stream).
> It executes `pytest --json-report --json-report-file=/tmp/report.json` via container `exec_run()`.
> Implement an asynchronous watchdog timer enforcing `timeout_seconds=2.0`. If execution exceeds the timeout, terminate the execution process immediately via `kill -9` inside the container and return `ExecutionResult(timed_out=True, error_type=ErrorTypeEnum.TIMEOUT)`.
> Parse container stdout, stderr, exit code, and memory usage. Map exit code 137 to `ErrorTypeEnum.OOM`.
> Write comprehensive unit tests in `tests/test_sandbox_runner.py` covering clean execution, timeout handling, and OOM detection.

#### Acceptance Criteria:
- [ ] Successfully archives and writes candidate files into container tmpfs mount.
- [ ] Correctly runs `pytest` and parses JSON test output.
- [ ] Hard wall-clock timeout of 2.0s triggers SIGKILL and flags `timed_out=True`.
- [ ] Out-of-memory termination returns exit code 137 and flags `oom_killed=True`.
- [ ] All tests in `tests/test_sandbox_runner.py` pass.

---

### TICKET-EF-005: AST Anti-Cheat & Static Code Analysis Inspector

* **Priority**: Must-Have
* **Dependencies**: TICKET-EF-001
* **Target File Paths**:
  - `evalforge/grader/ast_inspector.py`
  - `tests/test_ast_inspector.py`

#### Task Description (AI Coding Prompt):
> Implement `ASTCodeInspector` in `evalforge/grader/ast_inspector.py` using Python's standard `ast` library.
> The visitor class `AntiCheatVisitor(ast.NodeVisitor)` must inspect candidate code for:
> 1. Syntax errors: parsed via `ast.parse()`, catches `SyntaxError`.
> 2. Banned imports: `os`, `sys`, `subprocess`, `ctypes`, `socket`, `urllib`, `requests`, `importlib`.
> 3. Dangerous builtins: calls to `eval()`, `exec()`, `compile()`, `__import__()`, `open()`.
> 4. Early exits: calls to `sys.exit()`, `os._exit()`, or `raise SystemExit`.
> 5. Framework hijacking: references to `pytest`, `unittest`, `mock`, `monkeypatch`, or `sys._getframe()`.
> 6. Hardcoded literal return tables: functions that only contain static equality lookups matching inputs to outputs without algorithmic logic (computing Literal Decision Density > 0.60).
> 7. Cyclomatic complexity: calculate McCabe complexity.
> Returns a validated `ASTAuditReport` Pydantic model.
> Write exhaustive tests in `tests/test_ast_inspector.py` verifying all 7 detection rules with synthetic cheating code samples.

#### Acceptance Criteria:
- [ ] Accurately flags any banned import or dangerous builtin.
- [ ] Catches `sys.exit(0)` and `SystemExit` attempts.
- [ ] Detects pytest monkeypatching and stack inspection.
- [ ] Flags hardcoded input/output return tables.
- [ ] Calculates cyclomatic complexity correctly.
- [ ] `tests/test_ast_inspector.py` achieves 100% cheat detection on test fixtures.

---

### TICKET-EF-006: 4-Axis Rubric Grading Engine

* **Priority**: Must-Have
* **Dependencies**: TICKET-EF-004, TICKET-EF-005
* **Target File Paths**:
  - `evalforge/grader/rubric.py`
  - `evalforge/grader/functional.py`
  - `tests/test_rubric_grader.py`

#### Task Description (AI Coding Prompt):
> Implement the multi-axis evaluation formula in `evalforge/grader/rubric.py`:
> $$\text{Composite Score} = S_{\text{func}} (40\%) + S_{\text{edge}} (30\%) + S_{\text{ast}} (20\%) + S_{\text{hygiene}} (10\%)$$
> - **Axis 1: Functional Correctness (40%)**: Pass ratio of visible baseline unit tests ($40 \times \frac{P_{\text{vis}}}{N_{\text{vis}}}$).
> - **Axis 2: Edge-Case & Scale Robustness (30%)**: Pass ratio of hidden edge-case and scale tests ($30 \times \frac{P_{\text{hid}}}{N_{\text{hid}}}$). 0 if timed out or OOM.
> - **Axis 3: Anti-Cheat & AST Integrity (20%)**: 20 points if AST audit passes with no cheats; 0 points if cheat/banned import detected. If cheat detected, composite score is capped at 30.0.
> - **Axis 4: Code Hygiene & Style (10%)**: Deducts points for McCabe complexity > 15, unhandled exceptions, or excessive lines.
> - Task is marked `is_passed=True` only if `composite_score >= 75.0` AND `functional_score == 40.0`.
> Write unit tests in `tests/test_rubric_grader.py` testing boundary conditions, cheat penalties, and score weighting.

#### Acceptance Criteria:
- [ ] Computes exact weights: 40/30/20/10 summing to 100 max.
- [ ] Caps total score at 30.0 whenever a reward-hacking cheat is flagged.
- [ ] Zero edge-case score awarded for timeouts or OOMs.
- [ ] Output conforms to `RubricScore` Pydantic model.
- [ ] All tests in `tests/test_rubric_grader.py` pass.

---

### TICKET-EF-007: Unbiased Chen et al. pass@k Metrics Calculator

* **Priority**: Must-Have
* **Dependencies**: TICKET-EF-006
* **Target File Paths**:
  - `evalforge/grader/metrics.py`
  - `tests/test_pass_at_k.py`

#### Task Description (AI Coding Prompt):
> Implement the unbiased estimator for $\text{pass}@k$ introduced by Chen et al. (2021) in *Evaluating Large Language Models Trained on Code*:
> $$\text{pass}@k = \mathbb{E}\left[ 1 - \frac{\binom{n - c}{k}}{\binom{n}{k}} \right]$$
> Where $n$ is total samples per task, $c$ is the number of samples passing the rubric ($c \le n$), and $k \in \{1, 5\}$.
> Handle numerical stability: when $n - c < k$, return $1.0$. Use `math.comb` or logarithmic combinations to avoid integer overflow.
> Implement functions `estimate_pass_at_k(n: int, c: int, k: int) -> float` and `calculate_benchmark_metrics(runs: List[TaskEvaluationResult], k_list: List[int] = [1, 5]) -> Dict[str, float]`.
> Write tests in `tests/test_pass_at_k.py` validating against known theoretical distributions and edge cases ($c=0$, $c=n$, $n < k$).

#### Acceptance Criteria:
- [ ] Implements exact Chen et al. combinatorial formula without sample bias.
- [ ] Correctly handles edge cases ($c=0 \implies 0.0$, $c=n \implies 1.0$, $n-c < k \implies 1.0$).
- [ ] Calculates pass@1 and pass@5 across aggregate benchmark runs.
- [ ] All tests in `tests/test_pass_at_k.py` pass.

---

### TICKET-EF-008: Task Registry, YAML Spec Loader & Pydantic Data Models

* **Priority**: Must-Have
* **Dependencies**: TICKET-EF-001
* **Target File Paths**:
  - `evalforge/tasks/models.py`
  - `evalforge/tasks/loader.py`
  - `tests/test_task_loader.py`

#### Task Description (AI Coding Prompt):
> In `evalforge/tasks/models.py`, implement Pydantic models for `TaskSpec`, `TestCase`, and `RubricRules` matching the specification in `ARCHITECTURE.md` and `INTERFACE_SPEC.md`.
> In `evalforge/tasks/loader.py`, implement `TaskBankLoader` which:
> 1. Discovers and parses all `.yaml` task files in `evalforge/tasks/bank/`.
> 2. Validates each task against `TaskSpec`.
> 3. Indexes tasks by `id` (e.g. `EF-PY-001`) and `slug`.
> 4. Provides methods `get_task(task_id: str) -> TaskSpec`, `list_tasks(language: Optional[str], difficulty: Optional[str]) -> List[TaskSpec]`, and `get_public_spec(task_id: str) -> Dict` (which strips `hidden_tests` and `canonical_solution`).
> Write unit tests in `tests/test_task_loader.py` validating file loading, error handling for malformed YAML, and public spec sanitization.

#### Acceptance Criteria:
- [ ] Pydantic models validate all task YAML fields with strict types.
- [ ] `TaskBankLoader` successfully discovers and caches tasks.
- [ ] `get_public_spec()` completely omits hidden test cases and canonical solutions.
- [ ] Malformed YAML raises descriptive `EvalForgeError`.
- [ ] Unit tests pass.

---

### TICKET-EF-009: 30 Curated Benchmark Tasks Dataset (20 Python, 10 C++20)

* **Priority**: Must-Have
* **Dependencies**: TICKET-EF-008
* **Target File Paths**:
  - `evalforge/tasks/bank/python/EF-PY-001.yaml` through `EF-PY-020.yaml`
  - `evalforge/tasks/bank/cpp/EF-CPP-001.yaml` through `EF-CPP-010.yaml`
  - `tests/test_task_bank_integrity.py`

#### Task Description (AI Coding Prompt):
> Author 30 high-quality, production-grade algorithmic and systems tasks conforming strictly to `task.yaml` format.
> - **20 Python Tasks (`EF-PY-001` .. `EF-PY-020`)**:
>   * Concurrency & Caching: Thread-safe TTL cache, Async token-bucket rate limiter, Work-stealing threadpool simulator.
>   * Data Structures & Algorithms: B-Tree index node splitter, Trie with wildcard prefix search, Disjoint Set with path compression, SkipList.
>   * Parsing & Compilers: JSON streaming tokenizer, SQL WHERE clause boolean evaluator, Regex NFA state machine engine.
>   * Systems & Networking: Consistent hashing ring with virtual nodes, Raft log compaction buffer, Sliding-window packet reassembly buffer.
>   * Graph & Optimization: Bellman-Ford negative cycle detector, A* pathfinder with dynamic obstacles, Maximum flow (Edmonds-Karp).
> - **10 C++20 Tasks (`EF-CPP-001` .. `EF-CPP-010`)**:
>   * Lock-free ring buffer (SPSC), Arena memory allocator, SIMD vector dot product wrapper, Thread-safe connection pool, Bit-sliced Bloom filter, C++20 coroutine generator wrapper.
> Each task must contain: prompt, starter code, canonical solution, at least 2 visible unit tests, at least 6 hidden edge-case/scale tests, and rubric rules.
> Write an automated integrity test `tests/test_task_bank_integrity.py` that verifies canonical solutions against their own visible and hidden test suites.

#### Acceptance Criteria:
- [ ] All 30 YAML files are present and pass `TaskSpec` Pydantic validation.
- [ ] Every task includes prompt, starter skeleton, canonical solution, visible tests, and hidden tests.
- [ ] Canonical solutions pass 100% of their test suites in `tests/test_task_bank_integrity.py`.
- [ ] Tasks include both Python 3.11 and C++20 implementations.

---

### TICKET-EF-010: SQLite Relational Persistence & JSONL Event Streaming Logger

* **Priority**: Must-Have
* **Dependencies**: TICKET-EF-001, TICKET-EF-006, TICKET-EF-007
* **Target File Paths**:
  - `evalforge/storage/db.py`
  - `evalforge/storage/jsonl_logger.py`
  - `tests/test_storage.py`

#### Task Description (AI Coding Prompt):
> Implement the SQLite persistence layer in `evalforge/storage/db.py` using `aiosqlite`.
> Implement functions to initialize tables (`init_db()`), record evaluation runs (`insert_run()`), persist per-task sample evaluations (`insert_task_evaluation()`), query historical runs, and query the aggregate model leaderboard.
> In `evalforge/storage/jsonl_logger.py`, implement `JSONLEventLogger` for append-only streaming telemetry. Each line written must conform to the JSON schema defined in `ARCHITECTURE.md`. Support asynchronous, thread-safe writes.
> Write integration tests in `tests/test_storage.py` verifying database CRUD, relational foreign key constraints, leaderboard aggregation calculations, and JSONL log writing.

#### Acceptance Criteria:
- [ ] Database tables match DDL in `ARCHITECTURE.md`.
- [ ] Thread-safe and asynchronous database reads/writes without connection locking.
- [ ] JSONL logs write valid newline-delimited JSON objects with full audit events.
- [ ] Leaderboard query accurately sorts by pass@1 and mean composite score.
- [ ] Unit and integration tests pass.

---

### TICKET-EF-011: FastAPI REST Server, Router & Endpoints

* **Priority**: Must-Have
* **Dependencies**: TICKET-EF-004, TICKET-EF-006, TICKET-EF-008, TICKET-EF-009, TICKET-EF-010
* **Target File Paths**:
  - `evalforge/api/app.py`
  - `evalforge/api/routes.py`
  - `evalforge/api/schemas.py`
  - `tests/test_api.py`

#### Task Description (AI Coding Prompt):
> Build the FastAPI REST application adhering to `INTERFACE_SPEC.md`.
> In `evalforge/api/routes.py`, implement endpoints:
> - `POST /api/v1/eval/run`: Validate payload with `SubmissionRequest`, run AST check, acquire warm sandbox, execute tests, grade rubric, persist results, and return `TaskEvaluationResult`.
> - `GET /api/v1/eval/runs/{run_id}`: Retrieve run status, metrics, and task evaluations.
> - `GET /api/v1/tasks`: Return list of available tasks with filtering by language and difficulty.
> - `GET /api/v1/tasks/{task_id}`: Return sanitized public task details.
> - `GET /api/v1/leaderboard`: Return current model leaderboard.
> - `GET /api/v1/health`: Return pool health and active container status.
> In `evalforge/api/app.py`, configure lifespan event to warm up the container pool on startup and shut it down gracefully.
> Write integration tests in `tests/test_api.py` using FastAPI's `TestClient`.

#### Acceptance Criteria:
- [ ] All endpoints return defined JSON status codes and response bodies.
- [ ] `POST /api/v1/eval/run` executes evaluation and returns rubric breakdown in sub-second time.
- [ ] Lifespan hooks properly initialize and tear down Docker pool.
- [ ] `GET /api/v1/tasks/{id}` never leaks hidden tests.
- [ ] All tests in `tests/test_api.py` pass.

---

### TICKET-EF-012: Typer & Rich Terminal CLI Commands

* **Priority**: Must-Have
* **Dependencies**: TICKET-EF-006, TICKET-EF-007, TICKET-EF-008, TICKET-EF-009, TICKET-EF-010
* **Target File Paths**:
  - `evalforge/main.py`
  - `tests/test_cli.py`

#### Task Description (AI Coding Prompt):
> Implement the command-line interface in `evalforge/main.py` using `typer` and `rich`.
> Implement commands specified in `INTERFACE_SPEC.md`:
> 1. `evalforge run`: Accept `--task-id`, `--candidate-file` or `--code`, `--model-name`, and execute evaluation with real-time Rich spinner and formatted rubric table scorecard. Return exit code 0 on pass, 1 on fail/cheat.
> 2. `evalforge report`: Render formatted Rich ASCII tables displaying pass@1, pass@5, and score distribution for past runs.
> 3. `evalforge benchmark`: Run candidate solutions across all 30 benchmark tasks with a progress bar, computing aggregate metrics and displaying the final leaderboard.
> 4. `evalforge sandbox status`: Inspect active pre-warmed containers and memory footprint.
> Write CLI tests in `tests/test_cli.py` using Typer's `CliRunner`.

#### Acceptance Criteria:
- [ ] `evalforge run` renders colored scorecards and returns correct exit codes.
- [ ] `evalforge benchmark` executes tasks with progress tracking and aggregates pass@k.
- [ ] `evalforge report` displays Rich tables matching visual spec.
- [ ] `evalforge sandbox status` outputs container pool status.
- [ ] All tests in `tests/test_cli.py` pass.


---

### TICKET-EF-013: End-to-End Evaluation Pipeline Integration Test Suite
* **Priority**: Must-Have
* **Dependencies**: TICKET-EF-011, TICKET-EF-012
* **Target Files**:
  - `tests/test_e2e_pipeline.py`
  - `tests/fixtures/synthetic_patches.py`
* **Task Description (AI Coding Prompt)**:
  > Implement the complete end-to-end integration test suite in `tests/test_e2e_pipeline.py`. Spin up the ephemeral Docker sandbox pool, trigger evaluations of synthetic tasks (both valid algorithmic solutions and adversarial reward-hacked patches), and verify that:
  > 1. Valid solutions score 100/100 and pass functional and scale tests.
  > 2. Reward-hacked solutions (e.g. `sys.exit(0)`, mock assertions, hardcoded lookups) are detected with 100% precision.
  > 3. Execution metrics (latency, memory peak via cgroup v2) are accurately stored in SQLite and streamed to JSONL.
  > 4. Single-use container destruction successfully cleans up 100% of temporary containers without leaking Docker processes.
* **Acceptance Criteria**:
  - [ ] `pytest tests/test_e2e_pipeline.py` executes cleanly and passes all integration assertions.
  - [ ] Proves zero container leakage: Docker daemon container count returns to exactly $K=4$ warm containers after test run.
  - [ ] Confirms sub-150ms task dispatch overhead from warm pool.
