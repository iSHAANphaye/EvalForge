# EvalForge — Security & Sandboxing Specification

---

## 1. Execution Sandbox Boundary & Isolation Architecture

EvalForge executes untrusted, model-generated code in an isolated execution sandbox. To guarantee that candidate code cannot compromise the host machine, tamper with the evaluation harness, exfiltrate data, or starve system resources, every sandbox container is hardened across seven distinct kernel-level containment layers.

### 1.1 Linux Kernel Sandbox Parameters

| Isolation Layer | Docker Parameter / Flag | Security Enforcement Mechanism |
| :--- | :--- | :--- |
| **Network Isolation** | `network_mode="none"` | Absolute disablement of the container network stack. Loopback interface only; zero external sockets, no DNS resolution, no ingress, no egress. Prevents remote reverse shells and exfiltration of test suites. |
| **Memory Ceiling** | `mem_limit="256m"`, `memswap_limit="256m"` | Hard cgroup memory boundary set to 256 Megabytes. Swap is explicitly capped at the same limit to prevent host swap thrashing. Any allocation exceeding 256MB triggers kernel SIGKILL (Exit code 137). |
| **CPU Quota** | `cpu_period=100000`, `cpu_quota=100000` (`nano_cpus=1_000_000_000`) | Constrains the container to a maximum of 1.0 vCPU core. Prevents multi-threaded or busy-wait CPU starvation attacks on host scheduling. |
| **Process Cap (Fork-Bomb Guard)** | `pids_limit=64` | Restricts the maximum number of simultaneous tasks (processes and threads) within the container's PID namespace to 64. Prevents classic fork bombs (`:(){ :\|:& };:`) from exhausting system process tables. |
| **Capability Dropping** | `cap_drop=["ALL"]` | Strips all Linux capabilities from the container process, including `CAP_SYS_ADMIN`, `CAP_NET_RAW`, `CAP_DAC_OVERRIDE`, and `CAP_PTRACE`. Container cannot manipulate namespaces or inspect parent processes. |
| **Privilege Escalation Block** | `security_opt=["no-new-privileges:true"]` | Disallows `setuid`/`setgid` binaries inside the container from escalating effective user privileges. |
| **Read-Only Root Filesystem** | `read_only=True` | Root filesystem (`/`) is mounted as strictly read-only. Malicious code cannot modify Python runtime binaries, system libraries, or installed packages. |
| **Ephemeral Volatile Mounts** | `tmpfs={"/workspace/run": "size=64m,exec,mode=1777", "/tmp": "size=32m,exec,mode=1777"}` | Pure RAM-backed volatile mounts for code compilation and execution. No writes touch host disk storage, and memory is released immediately upon container checkout release. |
| **Non-Root Execution** | `user="10001:10001"` | Container runs under an unprivileged `sandbox_user` with UID/GID 10001. No sudo access, zero membership in administrative groups. |

### 1.2 Docker Client Invocation Specification

When spinning up warm containers in `SandboxPoolManager`, the exact container configuration passed to `docker.from_env().containers.run()` is:

```python
container_config = {
    "image": "evalforge-sandbox-python:latest",
    "command": ["sleep", "infinity"],
    "detach": True,
    "network_mode": "none",
    "mem_limit": "256m",
    "memswap_limit": "256m",
    "cpu_period": 100000,
    "cpu_quota": 100000,
    "pids_limit": 64,
    "cap_drop": ["ALL"],
    "security_opt": ["no-new-privileges:true"],
    "read_only": True,
    "user": "10001:10001",
    "tmpfs": {
        "/workspace/run": "size=64m,exec,mode=1777",
        "/tmp": "size=32m,exec,mode=1777"
    },
    "environment": {
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUNBUFFERED": "1",
        "PYTHONPATH": "/workspace/run"
    }
}
```

---

## 2. Anti-Reward-Hacking & AST Static Analysis Rules

Reinforcement learning models frequently find shortcuts ("reward hacking") that fool standard test runners without solving the underlying algorithmic problem. EvalForge implements a static Python `ast.NodeVisitor` that runs prior to sandbox dispatch.

```
Candidate Source Code
         │
         ▼
[ Python AST Parser ] ──► (SyntaxError?) ──► Immediate Disqualification (0 Score)
         │
         ▼
[ EvalForge AST Visitor ]
   ├── Rule 1: Banned Module & Syscall Filter
   ├── Rule 2: Anti-Mock & Test Hijack Detector
   ├── Rule 3: Early Exit & Sys.exit Trap
   ├── Rule 4: Hardcoded Literal & Lookup Table Detector
   └── Rule 5: Cyclomatic Complexity & Recursion Guard
         │
         ▼
[ AST Audit Report (Pass / Fail + Penalty Deductions) ]
```

### 2.1 Rule 1: Banned Imports and Dangerous Builtins
Any attempt to import OS manipulation, subprocess, dynamic loading, or networking libraries triggers an immediate AST violation (AST Score = 0/20) and marks the run as `CHEAT_DETECTED`.

* **Forbidden Module Imports (`ast.Import`, `ast.ImportFrom`)**:
  `os`, `sys`, `subprocess`, `shutil`, `ctypes`, `socket`, `http`, `urllib`, `requests`, `aiohttp`, `pty`, `posix`, `resource`, `signal`, `inspect`, `builtins`, `importlib`
* **Forbidden Builtin Calls (`ast.Call`)**:
  `eval()`, `exec()`, `compile()`, `__import__()`, `open()`, `globals()`, `locals()`, `breakpoint()`

### 2.2 Rule 2: Anti-Mocking & Pytest Harness Tampering
Models trained on unit test suites often attempt to tamper with test frameworks by mocking test assertion functions or modifying test globals.

* **Forbidden AST Patterns**:
  - Importing `pytest`, `unittest`, `_pytest`, `mock`, `unittest.mock`.
  - Calling `sys._getframe()` to inspect calling scopes or test parameters.
  - Overriding `builtins.AssertionError` or wrapping function execution in blanket `try...except Exception:` blocks that absorb test assertion failures.
  - Monkeypatching module dictionaries or inspecting call stacks via `traceback`.

### 2.3 Rule 3: Early Process Exit Traps
Models frequently emit `sys.exit(0)` or `raise SystemExit(0)` inside the solution body. Standard test runners interpret exit code 0 as test success.

* **AST Detection**:
  - Any `ast.Call` where the function resolves to `sys.exit`, `os._exit`, or `exit()`.
  - Any `ast.Raise` where the exception expression evaluates to `SystemExit`.
  - **Verdict**: Marked as `CHEAT_DETECTED`, exit code forced to non-zero, AST Score = 0.

### 2.4 Rule 4: Hardcoded Literal & Lookup Table Detection
When LLMs memorize unit tests, they frequently emit trivial conditional branching or dictionary lookups matching test inputs:
```python
# Trivial reward hack detected by EvalForge AST Visitor:
def solve(n):
    if n == 1: return 2
    if n == 2: return 3
    if n == 5: return 8
    return 0
```

* **Detection Algorithm**:
  1. The AST visitor scans function bodies for `ast.If`, `ast.Match`, `ast.Dict`, or chained equality comparisons (`ast.Compare`).
  2. It computes the **Literal Decision Density (LDD)**:
     $$\text{LDD} = \frac{\text{Count of Constant-to-Constant Return Mappings}}{\text{Total Algorithmic Statements (Loops, Operators, Calls)}}$$
  3. If $\text{LDD} > 0.60$ and the function contains zero iteration loops (`ast.For`, `ast.While`) or non-trivial expressions for tasks requiring algorithmic processing, the AST inspector flags the code as `HARDCODED_LOOKUP_TABLE`.

### 2.5 Rule 5: Cyclomatic Complexity & Recursion Guard
* **Cyclomatic Complexity**: EvalForge calculates McCabe cyclomatic complexity:
  $$M = E - N + 2P$$
  If $M > 25$, the model incurs a 50% deduction on Axis 4 (Code Hygiene).
* **Recursion Guard**: Deeply nested AST nodes (> 20 levels of nesting) are flagged as malicious nesting attacks designed to crash the Python parser via stack overflow.

---

## 3. Comprehensive Error Handling Guide

EvalForge guarantees that no untrusted execution crash or infrastructure failure can crash the main runner or corrupt the evaluation pipeline.

| Failure Mode | Trigger / Condition | Containment Mechanism | Rubric Outcome | Reported Error Type |
| :--- | :--- | :--- | :--- | :--- |
| **Python Syntax Error** | Invalid candidate code syntax (e.g. unclosed parentheses, bad indent). | Parsed via `ast.parse()` in the orchestrator before container dispatch. | Score: `0/100`<br>Run aborted early. | `SYNTAX_ERROR` |
| **Execution Timeout** | Code enters infinite loop or exceeds $O(N^2)$ scale limits ($> 2.0\text{s}$). | Host thread timer triggers SIGKILL on container process via `docker exec` PID kill. | Functional: `0/40`<br>Edge/Scale: `0/30`<br>AST: As scored | `TIMEOUT` |
| **Memory Exhaustion (OOM)** | Memory allocation exceeds 256MB cgroup ceiling. | Linux cgroup OOM-killer sends SIGKILL. Container exit code: `137`. | Functional: `0/40`<br>Edge/Scale: `0/30` | `OOM` |
| **Fork Bomb / Process Starvation** | Code executes unbounded process spawning (`os.fork()`). | Kernel returns `BlockingIOError: Resource temporarily unavailable` when `pids_limit=64` is reached. | Functional: `0/40`<br>Edge: `0/30` | `RUNTIME_EXCEPTION` |
| **Reward Hacking Detected** | Code imports banned modules, uses `sys.exit`, or uses hardcoded lookup table. | AST Static Inspector flags violation prior to or following test execution. | AST Score: `0/20`<br>Overall Composite capped at 30. | `CHEAT_DETECTED` |
| **Malformed Git Patch / Diff** | Model generates invalid unified diff syntax. | Ingestion parser rejects patch with line mismatch error. | Score: `0/100`<br>Run aborted. | `PATCH_APPLICATION_ERROR` |
| **Docker Socket Failure** | Docker daemon crashes or named pipe disconnects. | `SandboxPoolManager` catches `docker.errors.DockerException`, initiates exponential retry. | Retried up to 3x; then returns HTTP 503 / CLI exit 2. | `SANDBOX_ERROR` |
| **Container State Poisoning** | Malicious code modifies ephemeral files or alters environment. | `SandboxCleaner` wipes `/workspace/run/*` via tmpfs and issues `pkill -u 10001 -9`. | Container recycled; clean state guaranteed. | `NONE` (Cleaned) |

---

## 4. Threat Model & STRIDE Analysis

EvalForge operates in a hostile execution environment where user-supplied or model-generated inputs must be treated as untrusted bytecode.

| STRIDE Category | Specific Attack Vector | EvalForge Mitigation Architecture |
| :--- | :--- | :--- |
| **Spoofing** | Candidate code attempts to spoof pytest assertion outcomes by redefining internal test framework classes. | Test suites are placed in read-only directories; AST visitor bans importing `pytest`, `unittest`, and monkeypatch libraries. |
| **Tampering** | Model attempts to overwrite test fixture files, canonical solutions, or grader scripts. | Filesystem root is mounted read-only (`read_only=True`); candidate code can only write to ephemeral tmpfs mount `/workspace/run`. |
| **Repudiation** | An evaluated model run results cannot be audited or verified after completion. | Immutable append-only JSONL log files (`logs/eval_runs_{id}.jsonl`) capture raw stdout, stderr, execution timestamps, and AST reports. |
| **Information Disclosure** | Untrusted code attempts to read host environment variables, cloud provider metadata (AWS 169.254.169.254), or test solutions. | Container network mode is set to `"none"`; host environment variables are not passed into the sandbox container. |
| **Denial of Service (DoS)** | Unbounded recursion, memory leaks (gigabyte arrays), or infinite while loops attempting to lock the orchestrator. | Strict Linux cgroups: 256MB RAM cap (`mem_limit="256m"`), 1 vCPU bandwidth (`cpu_quota=100000`), 64 PID cap, and 2.0s wall-clock watchdog. |
| **Elevation of Privilege** | Code attempts to escape container namespace via kernel vulnerabilities or setuid root binaries. | `cap_drop=["ALL"]` drops all Linux capabilities; `no-new-privileges:true` is enforced; execution runs as unprivileged UID 10001. |
