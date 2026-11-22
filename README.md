# EvalForge — AI Coding Benchmark & Rubric Grading Harness

> **The uncompromising, lightning-fast evaluation forge that measures true algorithmic competence and engineering rigor in AI coding models—guaranteed tamper-proof, sub-second, and graded like a staff software engineer.**

---

## Overview

EvalForge is a high-throughput, hardened evaluation harness for benchmarking LLM code generation. Modern coding models easily game legacy benchmarks like HumanEval through training data contamination and unit-test reward hacking (e.g. hardcoding literal returns or monkeypatching `pytest`).

EvalForge replaces binary pass/fail assertions with a **4-axis rubric grading engine** running inside an **ephemeral pre-warmed Docker sandbox pool** with sub-150ms execution dispatch overhead.

```
Candidate Code ──► AST Anti-Cheat ──► Warm Docker Sandbox ──► 4-Axis Rubric ──► pass@k Metric
                      (Static)           (<150ms Overhead)     (40/30/20/10)     (Chen et al.)
```

---

## Key Capabilities

* **Pre-Warmed Docker Container Pool**: Maintains an active pool of 4 warm containers. Executes code via low-overhead `docker exec` into isolated tmpfs RAM mounts, reducing dispatch latency from ~2,000ms cold-start down to **sub-150ms**.
* **Hermetic Kernel Sandbox**:
  - `network_mode="none"`: Absolute zero-network execution (loopback only, zero sockets).
  - Strict resource constraints: 256MB RAM cap, 1.0 vCPU quota, 64 PIDs ceiling (fork-bomb guard).
  - Hardened isolation: Read-only root filesystem (`read_only=True`), dropped kernel capabilities (`cap_drop=["ALL"]`), unprivileged user (`10001:10001`), and 2.0-second execution watchdog.
* **AST Anti-Cheat & Anti-Reward-Hacking**: Static Python AST analyzer detecting hardcoded literal return tables, `sys.exit(0)` evasion, pytest monkeypatching, dangerous builtins (`eval`, `exec`), and banned system modules (`os`, `subprocess`, `socket`).
* **4-Axis Rubric Grading Engine**:
  - **Axis 1: Functional Correctness (40%)**: Baseline visible test validation.
  - **Axis 2: Edge-Case & Scale Robustness (30%)**: Hidden boundary and algorithmic scaling tests ($O(N)$ vs $O(N^2)$).
  - **Axis 3: Anti-Cheat & AST Integrity (20%)**: Static algorithmic integrity audit.
  - **Axis 4: Code Hygiene & Style (10%)**: Cyclomatic complexity ceiling and typing adherence.
* **Unbiased `pass@k` Estimators**: Mathematically unbiased Chen et al. (2021) estimator for $k \in \{1, 5\}$ over $n$ samples.
* **30 Curated Benchmark Tasks**: 20 Python 3.11 and 10 C++20 production-grade challenges (concurrency, data structures, streaming tokenizers, distributed algorithms) with visible and hidden test suites.
* **Dual Interface**: Typer & Rich interactive terminal CLI and high-throughput FastAPI REST API.

---

## Pre-Build Engineering Documentation

EvalForge is built according to rigorous systems engineering specifications:

| Document | Description | Direct File Link |
| :--- | :--- | :--- |
| **Product Requirements Document (PRD)** | Problem statement, user personas, vision, must-have features, user flows, success metrics, and scope ceiling. | [PRD.md](file:///C:/Antigravity%20Dev/EvalForge/docs/PRD.md) |
| **Technical Architecture** | Complete tech stack, repository map, SQLite schema, JSONL telemetry, Pydantic models, container pool lifecycle, and Mermaid diagrams. | [ARCHITECTURE.md](file:///C:/Antigravity%20Dev/EvalForge/docs/ARCHITECTURE.md) |
| **Security & Sandboxing** | Linux kernel isolation boundary, AST visitor rules, error recovery guide, and STRIDE threat model. | [SECURITY.md](file:///C:/Antigravity%20Dev/EvalForge/docs/SECURITY.md) |
| **Interface & Integration Spec** | CLI commands, exit codes, FastAPI OpenAPI endpoints, `task.yaml` schema, and Rich / Web visual design tokens. | [INTERFACE_SPEC.md](file:///C:/Antigravity%20Dev/EvalForge/docs/INTERFACE_SPEC.md) |
| **Feature Build Tickets** | 12 atomic, sequential engineering tickets with exact AI coding prompts and acceptance criteria. | [FEATURE_TICKETS.md](file:///C:/Antigravity%20Dev/EvalForge/docs/FEATURE_TICKETS.md) |

---

## Quickstart Guide

### Prerequisites
* **Python 3.11+**
* **Docker Engine** running locally (Docker Desktop or Docker daemon socket)

### 1. Installation
Clone the repository and install dependencies:
```bash
git clone https://github.com/evalforge/evalforge.git
cd EvalForge
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -e ".[dev]"
```

### 2. Build Sandbox Docker Images
Build the hardened Python 3.11 and C++20 sandbox container images:
```bash
python scripts/build_sandboxes.py
```

### 3. Evaluate a Candidate Solution via CLI
Evaluate a model's solution against task `EF-PY-001` with real-time rubric scorecards:
```bash
evalforge run --task-id EF-PY-001 --candidate-file solutions/lru_cache.py --model-name "qwen2.5-coder-7b"
```

### 4. Run Full Benchmark
Execute the complete 30-task benchmark across 5 samples per task to calculate unbiased pass@1 and pass@5:
```bash
evalforge benchmark --suite all --candidates-dir ./model_outputs/ --samples-per-task 5
```

### 5. Launch FastAPI REST Service
Start the REST API server:
```bash
uvicorn evalforge.api.app:app --host 127.0.0.1 --port 8000 --reload
```
Interactive OpenAPI documentation is available at `http://127.0.0.1:8000/docs`.

---

## Repository Map

```
EvalForge/
├── README.md
├── pyproject.toml
├── Dockerfile.sandbox.python
├── Dockerfile.sandbox.cpp
├── docs/
│   ├── PRD.md                  # Product Requirements Document
│   ├── ARCHITECTURE.md         # Technical Architecture Document
│   ├── SECURITY.md             # Security & Access Document
│   ├── INTERFACE_SPEC.md       # Frontend & Integration Specification
│   └── FEATURE_TICKETS.md      # Feature Build Ticket List
├── evalforge/
│   ├── main.py                 # CLI entrypoint (Typer/Rich)
│   ├── api/                    # FastAPI routes & schemas
│   ├── core/                   # Config, constants & exceptions
│   ├── sandbox/                # Pre-warmed pool manager & runner
│   ├── grader/                 # 4-axis rubric & AST inspector
│   ├── tasks/                  # Task registry & 30 curated YAML tasks
│   └── storage/                # SQLite DB & JSONL streaming logger
└── tests/                      # Pytest suite & integration tests
```

---

## License

Apache-2.0. See `LICENSE` for details.
