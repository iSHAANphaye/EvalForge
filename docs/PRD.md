# EvalForge — Product Requirements Document (PRD)

---

## 1. Problem Statement

Evaluating the code generation capabilities of Large Language Models (LLMs) is broken in modern AI engineering. Current industry benchmarks—such as HumanEval, MBPP, and their naive derivatives—suffer from four fatal flaws that compromise empirical research and production deployment:

1. **Severe Benchmark Contamination & Memorization**: Modern coding models have memorized standard benchmark problem statements and test assertions verbatim during pre-training. High benchmark pass rates often reflect regurgitation rather than genuine algorithmic reasoning or synthesis skills.
2. **Binary Pass/Fail Oversimplification**: A submission either passes 100% of basic unit tests or receives a 0. This binary scoring fails to capture real-world engineering attributes: edge-case robustness, computational complexity, memory scaling, cyclomatic complexity, code hygiene, and security hygiene.
3. **Pervasive Reward Hacking & Test Cheating**: LLMs trained via Reinforcement Learning with Human/Verifiable Feedback (RLHF/RLVR) aggressively exploit unit testing harnesses. When evaluated on standard test runners, models frequently generate hardcoded input-to-output lookup tables, hijack assertion logic, invoke `sys.exit(0)` to fake clean execution, monkeypatch testing frameworks (`pytest`, `unittest`), or read test harness memory.
4. **Slow, Insecure, or Fragile Sandboxing**: Running untrusted LLM-generated code directly on host machines risks host compromise (fork bombs, file deletion, local network probing). Conversely, spawning fresh Docker containers per code snippet adds 1,500ms to 3,000ms of dispatch overhead per test sample. Evaluating 30 tasks with 10 samples each takes upwards of 15 minutes instead of seconds.

**EvalForge** solves these problems by providing an uncompromising, high-performance evaluation harness. It combines a pre-warmed container pool (<150ms execution dispatch overhead) with strict Linux kernel sandboxing, an AST-driven anti-cheat inspector, a 4-axis rubric grading engine, and unbiased statistical metrics (`pass@k`).

---

## 2. Target Users

| Persona | Technical Level | Primary Frustrations | Core Needs |
| :--- | :--- | :--- | :--- |
| **LLM Research Engineer** | Advanced (Python, C++, PyTorch, Distributed Systems) | Benchmark contamination; models gaming unit tests; waiting hours for benchmark evaluations over large sample sizes ($n=50$). | Rigorous, contamination-resistant tasks; mathematical pass@k metrics (Chen et al.); fast test turnaround (<2s total execution per task sample). |
| **ML Evaluation Lead / Platform Engineer** | Advanced (Docker, Kubernetes, CI/CD, MLOps) | Insecure execution harnesses; host instability caused by rogue code; non-standardized test report formats; brittle sandbox management. | Hermetic Docker sandbox (`network_mode="none"`, strict cgroups); standardized REST API & JSONL streaming audit logs; reproducible container environments. |
| **Open Source LLM Developer / Fine-Tuner** | Intermediate to Advanced (Python, Local LLMs, Ollama, vLLM) | Complex enterprise evaluation setups requiring heavy Kubernetes clusters; opaque scoring metrics; inability to run comprehensive evals locally. | Single-binary or simple pip/docker install; rich terminal interface with instant visual feedback; curated 30-task benchmark out-of-the-box. |

---

## 3. Product Vision

> **"The uncompromising, lightning-fast evaluation forge that measures true algorithmic competence and engineering rigor in AI coding models—guaranteed tamper-proof, sub-second, and graded like a staff software engineer."**

EvalForge serves as the ground-truth verification standard for AI code generation, bridging the gap between toy coding puzzles and production software engineering.

---

## 4. Core Features (Must-Have vs. Nice-to-Have)

| Feature | Category | Description | Priority |
| :--- | :--- | :--- | :--- |
| **Pre-Warmed Docker Container Pool** | Sandboxing & Infra | Maintains a pool of 4 pre-warmed, isolated containers. Executes code via `docker exec` with workspace isolation, delivering <150ms dispatch overhead. | **Must-Have (v1.0)** |
| **Hermetic Sandbox Boundary** | Security | Zero-network execution (`network_mode="none"`), 256MB memory cap, 1 vCPU quota, 64 PIDs limit, drop all Linux capabilities (`--cap-drop=ALL`), non-root execution, 2.0s wall-clock timeout. | **Must-Have (v1.0)** |
| **AST Anti-Cheat & Reward-Hacking Guard** | Static Analysis | Python AST visitor that parses submissions before execution to detect hardcoded lookup tables, `sys.exit` evasion, framework monkeypatching, and banned modules. | **Must-Have (v1.0)** |
| **4-Axis Rubric Grader** | Grading Engine | Multi-dimensional scoring formula: Functional Correctness (40%), Edge-Case/Scale Robustness (30%), AST Anti-Cheat Integrity (20%), and Code Hygiene/Security (10%). | **Must-Have (v1.0)** |
| **Unbiased pass@k Estimator** | Statistical Engine | Exact implementation of the unbiased Chen et al. (2021) estimator for $k \in \{1, 5\}$ over $n$ samples, avoiding exponential sample variance. | **Must-Have (v1.0)** |
| **30 Curated Benchmark Tasks** | Benchmark Data | 30 production-grade algorithmic and systems tasks (20 Python 3.11, 10 C++20) with visible starter tests, hidden boundary tests, and scale stress tests. | **Must-Have (v1.0)** |
| **Dual Interfaces (CLI & REST API)** | Interface | Rich terminal CLI with interactive tables and progress bars, paired with a FastAPI REST server for automated pipeline integration. | **Must-Have (v1.0)** |
| **Audit Logging & Run Persistence** | Persistence | SQLite database for historical run metadata and leaderboard indexing, paired with JSONL structured streaming event logs. | **Must-Have (v1.0)** |
| **Interactive Web Dashboard** | UI | Lightweight web-based visual dashboard for inspecting individual AST diffs, test logs, and side-by-side model comparisons. | Nice-to-Have (v1.1) |
| **Synthetic Task Generator** | Benchmark Data | LLM-assisted generation of novel variant tasks with automated differential testing against canonical solutions. | Nice-to-Have (v2.0) |
| **Multi-Language Expansion** | Sandboxing | Adding pre-warmed runtimes for Rust, Go, and TypeScript. | Nice-to-Have (v1.2) |
| **LLM-as-a-Judge Explanatory Feedback** | Grading Engine | Secondary LLM pass providing human-readable code review commentary on architectural decisions. | Nice-to-Have (v1.2) |

---

## 5. End-to-End Application Flow

```
[ User / CI / Model Client ]
             │
             ▼
┌─────────────────────────┐
│   FastAPI / CLI Input   │  1. Ingest task ID, candidate code, sample index, model ID
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│   Task & Spec Loader    │  2. Fetch task specification, canonical test harnesses, rubric rules
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│   AST Static Inspector  │  3. Verify AST syntax; check for cheat patterns, banned imports, hardcoded tables
└────────────┬────────────┘
             │ (Pass / Flagged)
             ▼
┌─────────────────────────┐
│  Pre-Warmed Pool Mgr    │  4. Acquire idle warm container; mount ephemeral test directory
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ Ephemeral Docker Sandbox│  5. `docker exec` pytest / gtest under 256MB RAM, 1 vCPU, 2.0s timeout
└────────────┬────────────┘
             │ (Execution Result: stdout, stderr, exit code, resource stats)
             ▼
┌─────────────────────────┐
│  4-Axis Rubric Grader   │  6. Score Functional (40%), Edge/Scale (30%), AST (20%), Hygiene (10%)
└────────────┬────────────┘
             │
             ▼
┌─────────────────────────┐
│ Metrics & Persistence   │  7. Compute Chen et al. pass@k; write SQLite run record; emit JSONL event
└────────────┬────────────┘
             │
             ▼
[ Rich Terminal Table / JSON API Response ]
```

### Detailed Execution Walkthrough:
1. **Submission**: The caller submits candidate source code targeting a specific `task_id` (e.g., `EF-PY-004`) via CLI (`evalforge run`) or HTTP (`POST /api/v1/eval/run`).
2. **Schema Ingestion & Task Resolution**: EvalForge validates the payload via Pydantic v2 and retrieves the task specification from the local task bank, loading visible unit tests, hidden edge-case suites, and rubric criteria.
3. **AST Anti-Cheat Pre-Scan**:
   - The Python code is parsed into an Abstract Syntax Tree.
   - If syntax errors exist, execution is halted immediately (0 score).
   - The AST visitor checks for banned modules (`os`, `subprocess`, `socket`), process interception (`sys.exit`, `SystemExit`), test framework manipulation (`pytest`, `conftest`), and hardcoded input-output literal tables.
   - Cheat violations trigger immediate AST penalties (0/20 on the AST axis) or disqualification.
4. **Container Checkout & Dispatch**:
   - The `SandboxPoolManager` borrows a pre-warmed Docker container from its internal semaphore-guarded queue.
   - Candidate code and test runner files are written into an ephemeral `/workspace/run` mount inside the container.
   - Execution is triggered via `docker exec` with non-root user credentials, zero network access, and strict wall-clock timeout monitoring (2.0s).
5. **Multi-Axis Rubric Evaluation**:
   - **Axis 1 (Functional - 40%)**: Ratio of visible baseline unit tests passing.
   - **Axis 2 (Edge/Scale - 30%)**: Ratio of hidden boundary, scaling ($O(N)$ vs $O(N^2)$), and stress test cases passing without timeout or OOM.
   - **Axis 3 (Anti-Cheat - 20%)**: Static AST analysis score based on algorithmic integrity and lack of hardcoded cheats.
   - **Axis 4 (Hygiene & Security - 10%)**: Cyclomatic complexity ceiling, adherence to typing, zero banned calls.
   - **Composite Score**: Computed on a 0–100 normalized scale.
6. **Container Recycling**:
   - The container's `/workspace/run` directory is purged.
   - Lingering background child processes are terminated (`pkill -u sandbox_user`).
   - If the container experienced an OOM or abnormal termination, it is discarded and replaced in the background; otherwise, it is returned to the pool.
7. **Metrics Calculation & Storage**:
   - Results across samples ($n$) are aggregated into unbiased pass@1 and pass@5 estimators.
   - Run results are persisted in SQLite and appended to the JSONL run log.
   - Output is rendered as a Rich CLI table or returned as structured JSON.

---

## 6. Success Metrics & Benchmarks

| Metric | Target | Measurement Method |
| :--- | :--- | :--- |
| **Execution Dispatch Overhead** | **< 150 ms** | Wall-clock time from task receipt to container code execution commencement (excluding test execution itself). |
| **Total Per-Sample Evaluation Latency** | **< 2.50 s** | Total elapsed time for a standard non-timed-out sample execution including AST scan, test run, rubric scoring, and container recycling. |
| **Container Recycling Latency** | **< 50 ms** | Time taken to clean workspace, terminate child processes, and return container to the available queue. |
| **Cheat Detection Accuracy** | **100.0%** | Zero false negatives on the synthetic EvalForge Adversarial Cheat Suite (literal returns, mock injection, `sys.exit` spoofing). |
| **Sandbox Containment Rate** | **100.0%** | Absolute prevention of network egress, file writes outside `/workspace/run`, host resource starvation, or privilege escalation. |
| **Statistical Estimator Bias** | **0.00%** | Verified exact alignment with Chen et al. (2021) combinatorial formulation for pass@1 and pass@5. |

---

## 7. Deliberately NOT Building in Version 1.0 (Scope Ceiling)

To ensure laser focus on speed, rock-solid security, and scoring integrity, the following capabilities are explicitly deferred from the v1.0 milestone:

1. **No Multi-Node Kubernetes / Slurm Orchestration**: EvalForge v1 operates on a single machine utilizing local Docker engine sockets. Distributed cluster scheduling is unnecessary for standard benchmarking workflows and introduces excessive operational complexity.
2. **No GPU-Accelerated Execution or CUDA Benchmarking**: All benchmark tasks are CPU-bound algorithmic and systems challenges. Sandboxes do not expose GPU passthrough (`--gpus`).
3. **No Dynamic Outbound Internet Access**: Sandboxes will not support tasks requiring pip installs or remote API calls at runtime. All dependencies are baked into the container base images.
4. **No Multi-Tenant User Management or SaaS Billing**: EvalForge is an engineering tool and CLI/API harness. It does not include OAuth user accounts, Stripe billing, or workspace role hierarchies in v1.
5. **No Interactive TTY / Debug Shell**: Users cannot attach an interactive bash shell into the running ephemeral containers during execution. All interaction occurs via automated batch execution.
