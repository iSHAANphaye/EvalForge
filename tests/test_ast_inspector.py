"""Comprehensive unit tests for ASTCodeInspector and AntiCheatVisitor."""

import pytest

from evalforge.grader import AntiCheatVisitor, ASTCodeInspector
from evalforge.models.schemas import ASTAuditReport


@pytest.fixture
def inspector() -> ASTCodeInspector:
    return ASTCodeInspector()


# -----------------------------------------------------------------------------
# 1. Clean Algorithmic Python Code
# -----------------------------------------------------------------------------
def test_clean_quicksort_scores_full_points(inspector: ASTCodeInspector):
    """Verify clean recursive quicksort solution passes with full 20.0 points."""
    code = """
def quicksort(arr):
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quicksort(left) + middle + quicksort(right)
"""
    report = inspector.inspect_python(code)
    assert isinstance(report, ASTAuditReport)
    assert report.passed is True
    assert report.score == 20.0
    assert len(report.violations) == 0
    assert report.cyclomatic_complexity > 0


def test_clean_binary_search_scores_full_points(inspector: ASTCodeInspector):
    """Verify clean binary search with loops passes with full 20.0 points."""
    code = """
def binary_search(arr, target):
    low = 0
    high = len(arr) - 1
    while low <= high:
        mid = (low + high) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            low = mid + 1
        else:
            high = mid - 1
    return -1
"""
    report = inspector.inspect_python(code)
    assert report.passed is True
    assert report.score == 20.0
    assert len(report.violations) == 0


# -----------------------------------------------------------------------------
# 2. Syntax Errors
# -----------------------------------------------------------------------------
def test_syntax_error_returns_zero(inspector: ASTCodeInspector):
    """Verify code with syntax error fails gracefully with 0.0 score."""
    code = "def invalid_func(: pass"
    report = inspector.inspect_python(code)
    assert report.passed is False
    assert report.score == 0.0
    assert any("SyntaxError" in v for v in report.violations)


# -----------------------------------------------------------------------------
# 3. Banned Modules
# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "import_code, expected_banned",
    [
        ("import os", "os"),
        ("import os.path", "os"),
        ("from subprocess import Popen", "subprocess"),
        ("import ctypes", "ctypes"),
        ("import socket", "socket"),
        ("import pty", "pty"),
        ("import shutil", "shutil"),
        ("import urllib.request", "urllib"),
        ("import requests", "requests"),
        ("import aiohttp", "aiohttp"),
        ("import importlib", "importlib"),
        ("import inspect", "inspect"),
        ("import builtins", "builtins"),
        ("from os import environ", "os"),
        ("from urllib import parse", "urllib"),
    ],
)
def test_banned_module_imports(inspector: ASTCodeInspector, import_code: str, expected_banned: str):
    """Verify that importing any banned module immediately drops score to 0.0."""
    code = f"""
{import_code}

def solve(x):
    return x * 2
"""
    report = inspector.inspect_python(code)
    assert report.passed is False
    assert report.score == 0.0
    assert any("Banned module import" in v and expected_banned in v for v in report.violations)


# -----------------------------------------------------------------------------
# 4. Dangerous Builtin Calls
# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "call_expr",
    [
        'eval("1 + 1")',
        'exec("x = 1")',
        'compile("x = 1", "<string>", "exec")',
        "__import__('os')",
        "open('/etc/passwd')",
        "globals()",
        "locals()",
        "breakpoint()",
        "getattr(object, '__class__')",
        "setattr(object, 'attr', 1)",
        "delattr(object, 'attr')",
    ],
)
def test_dangerous_builtin_calls(inspector: ASTCodeInspector, call_expr: str):
    """Verify calls to dangerous builtins fail anti-cheat with score 0.0."""
    code = f"""
def solve(x):
    res = {call_expr}
    return x
"""
    report = inspector.inspect_python(code)
    assert report.passed is False
    assert report.score == 0.0
    assert any("Dangerous builtin call" in v for v in report.violations)


# -----------------------------------------------------------------------------
# 5. Early Process Exit Traps
# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "exit_code",
    [
        "sys.exit(0)",
        "sys.exit(1)",
        "os._exit(0)",
        "exit()",
        "quit()",
        "raise SystemExit(0)",
        "raise SystemExit",
    ],
)
def test_early_exit_traps(inspector: ASTCodeInspector, exit_code: str):
    """Verify early exit attempts are caught and flagged with score 0.0."""
    code = f"""
import sys

def solve(x):
    {exit_code}
    return x
"""
    report = inspector.inspect_python(code)
    assert report.passed is False
    assert report.score == 0.0
    assert any("Early process exit trap" in v or "Banned sys" in v for v in report.violations)


# -----------------------------------------------------------------------------
# 6. Sys Handling: Safe Standard Attributes vs Banned Members
# -----------------------------------------------------------------------------
def test_safe_sys_attributes_pass(inspector: ASTCodeInspector):
    """Verify standard safe sys attributes (stdin, stdout, stderr, maxsize) pass cleanly."""
    code = """
import sys

def solve():
    data = sys.stdin.read()
    sys.stdout.write(data)
    sys.stderr.write("log")
    max_val = sys.maxsize
    return max_val
"""
    report = inspector.inspect_python(code)
    assert report.passed is True
    assert report.score == 20.0
    assert len(report.violations) == 0


def test_safe_sys_import_from_pass(inspector: ASTCodeInspector):
    """Verify importing safe members directly from sys passes cleanly."""
    code = """
from sys import stdin, stdout, stderr, maxsize

def solve():
    return maxsize
"""
    report = inspector.inspect_python(code)
    assert report.passed is True
    assert report.score == 20.0
    assert len(report.violations) == 0


@pytest.mark.parametrize(
    "sys_abuse",
    [
        "sys.modules",
        "sys._getframe()",
        "sys.setrecursionlimit(5000)",
        "sys.audit('event')",
        "from sys import modules",
        "from sys import _getframe",
        "from sys import setrecursionlimit",
        "from sys import audit",
        "from sys import *",
    ],
)
def test_dangerous_sys_attributes_flagged(inspector: ASTCodeInspector, sys_abuse: str):
    """Verify dangerous sys attributes and functions are rejected."""
    code = f"""
import sys
{sys_abuse}

def solve(x):
    return x
"""
    report = inspector.inspect_python(code)
    assert report.passed is False
    assert report.score == 0.0
    assert any("sys" in v.lower() for v in report.violations)


def test_sys_aliasing_caught(inspector: ASTCodeInspector):
    """Verify that importing sys as an alias still intercepts dangerous calls."""
    code = """
import sys as my_sys

def solve():
    my_sys.exit(0)
"""
    report = inspector.inspect_python(code)
    assert report.passed is False
    assert report.score == 0.0
    assert any("Early process exit trap" in v or "Banned sys" in v for v in report.violations)


# -----------------------------------------------------------------------------
# 7. Test Harness Tampering & Monkeypatching
# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "tampering_code",
    [
        "import pytest",
        "import unittest",
        "from unittest import mock",
        "import monkeypatch",
        "import _pytest",
        "def solve(): return pytest.skip()",
        "def solve(): return unittest.TestCase()",
    ],
)
def test_harness_tampering_references(inspector: ASTCodeInspector, tampering_code: str):
    """Verify references to test harness frameworks are flagged."""
    code = f"""
{tampering_code}
"""
    report = inspector.inspect_python(code)
    assert report.passed is False
    assert report.score == 0.0
    assert any("Test harness tampering" in v for v in report.violations)


def test_assertion_error_catch_tampering(inspector: ASTCodeInspector):
    """Verify catching AssertionError to swallow test failures is flagged."""
    code = """
def solve():
    try:
        assert False
    except AssertionError:
        pass
    return True
"""
    report = inspector.inspect_python(code)
    assert report.passed is False
    assert report.score == 0.0
    assert any("catching AssertionError" in v for v in report.violations)


def test_assertion_error_tuple_catch_tampering(inspector: ASTCodeInspector):
    """Verify catching AssertionError in exception tuple is flagged."""
    code = """
def solve():
    try:
        assert False
    except (ValueError, AssertionError):
        pass
    return True
"""
    report = inspector.inspect_python(code)
    assert report.passed is False
    assert report.score == 0.0
    assert any("catching AssertionError" in v for v in report.violations)


def test_assertion_error_reassignment_tampering(inspector: ASTCodeInspector):
    """Verify redefining or assigning AssertionError is flagged."""
    code = """
AssertionError = Exception

def solve():
    return 1
"""
    report = inspector.inspect_python(code)
    assert report.passed is False
    assert report.score == 0.0
    assert any("modifying AssertionError" in v for v in report.violations)


def test_assertion_error_class_definition_tampering(inspector: ASTCodeInspector):
    """Verify defining class AssertionError is flagged."""
    code = """
class AssertionError(Exception):
    pass
"""
    report = inspector.inspect_python(code)
    assert report.passed is False
    assert report.score == 0.0
    assert any("defining 'AssertionError'" in v for v in report.violations)


# -----------------------------------------------------------------------------
# 8. Dangerous Dunders vs Safe Dunders
# -----------------------------------------------------------------------------
@pytest.mark.parametrize(
    "dunder_attr",
    [
        "fn.__globals__",
        "cls.__subclasses__()",
        "obj.__code__",
        "mod.__builtins__",
    ],
)
def test_dangerous_dunders_flagged(inspector: ASTCodeInspector, dunder_attr: str):
    """Verify dangerous introspective dunder attributes are flagged."""
    code = f"""
def solve(fn, cls, obj, mod):
    return {dunder_attr}
"""
    report = inspector.inspect_python(code)
    assert report.passed is False
    assert report.score == 0.0
    assert any("Dangerous dunder attribute access" in v for v in report.violations)


def test_safe_dunders_do_not_false_positive(inspector: ASTCodeInspector):
    """Verify legitimate dunders (e.g. self.__class__.__name__, __init__, __len__) pass."""
    code = """
class Solution:
    def __init__(self, val):
        self.val = val

    def __str__(self):
        return f"{self.__class__.__name__}({self.val})"

    def __repr__(self):
        return self.__str__()

    def __len__(self):
        return len(str(self.val))

    def __getitem__(self, idx):
        return self.val[idx]

    def __iter__(self):
        return iter([self.val])

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False
"""
    report = inspector.inspect_python(code)
    assert report.passed is True
    assert report.score == 20.0
    assert len(report.violations) == 0


# -----------------------------------------------------------------------------
# 9. Literal Decision Density (LDD) Calculation
# -----------------------------------------------------------------------------
def test_hardcoded_lookup_table_detected(inspector: ASTCodeInspector):
    """Verify function with hardcoded input-to-output equality table is caught."""
    code = """
def solve(x):
    if x == 1:
        return 10
    elif x == 2:
        return 20
    elif x == 3:
        return 30
    elif x == 4:
        return 40
    return 0
"""
    report = inspector.inspect_python(code)
    assert report.passed is False
    assert report.score == 0.0
    assert report.literal_decision_density > 0.60
    assert any("HARDCODED_LOOKUP_TABLE" in v for v in report.violations)


def test_hardcoded_lookup_separate_ifs_detected(inspector: ASTCodeInspector):
    """Verify separate if statements returning constants are flagged."""
    code = """
def solve(x):
    if x == "cat": return "feline"
    if x == "dog": return "canine"
    if x == "cow": return "bovine"
    if x == "pig": return "porcine"
    return "unknown"
"""
    report = inspector.inspect_python(code)
    assert report.passed is False
    assert report.score == 0.0
    assert report.literal_decision_density > 0.60
    assert any("HARDCODED_LOOKUP_TABLE" in v for v in report.violations)


def test_recursive_base_cases_not_flagged_as_lookup_table(inspector: ASTCodeInspector):
    """Verify recursive algorithms with 1-2 base case equality branches are NOT flagged."""
    code = """
def factorial(n):
    if n == 0:
        return 1
    if n == 1:
        return 1
    return n * factorial(n - 1)
"""
    report = inspector.inspect_python(code)
    assert report.passed is True
    assert report.score == 20.0
    assert not any("HARDCODED_LOOKUP_TABLE" in v for v in report.violations)


def test_loop_prevents_hardcoded_lookup_false_positive(inspector: ASTCodeInspector):
    """Verify algorithms containing loops are not flagged as hardcoded lookup tables."""
    code = """
def count_matches(arr):
    res = 0
    for x in arr:
        if x == 1:
            res += 10
    return res
"""
    report = inspector.inspect_python(code)
    assert report.passed is True
    assert report.score == 20.0
    assert not any("HARDCODED_LOOKUP_TABLE" in v for v in report.violations)


# -----------------------------------------------------------------------------
# 10. Cyclomatic Complexity Calculation
# -----------------------------------------------------------------------------
def test_normal_cyclomatic_complexity(inspector: ASTCodeInspector):
    """Verify normal algorithm has low cyclomatic complexity."""
    code = """
def add(a, b):
    return a + b
"""
    report = inspector.inspect_python(code)
    assert report.passed is True
    assert report.score == 20.0
    assert report.cyclomatic_complexity == 1


def test_excessive_cyclomatic_complexity_penalized(inspector: ASTCodeInspector):
    """Verify cyclomatic complexity > 25 deducts 10 points without cheat failure."""
    # Generate 26 if statements with non-trivial loop logic
    conditions = "\n".join(
        f"    if x > {i} and arr:\n        total += arr[0]"
        for i in range(26)
    )
    code = f"""
def complex_fn(x, arr):
    total = 0
    for _ in range(1):
        pass
{conditions}
    return total
"""
    report = inspector.inspect_python(code)
    assert report.passed is True
    assert report.score == 10.0  # 20.0 - 10.0 penalty
    assert report.cyclomatic_complexity > 25
    assert any("EXCESSIVE_CYCLOMATIC_COMPLEXITY" in v for v in report.violations)


# -----------------------------------------------------------------------------
# 11. C++ Inspection Security Rules
# -----------------------------------------------------------------------------
def test_clean_cpp_code_passes(inspector: ASTCodeInspector):
    """Verify standard C++ algorithm passes inspection."""
    code = """
#include <iostream>
#include <vector>
#include <algorithm>

int binary_search(const std::vector<int>& arr, int target) {
    int low = 0;
    int high = arr.size() - 1;
    while (low <= high) {
        int mid = low + (high - low) / 2;
        if (arr[mid] == target) return mid;
        if (arr[mid] < target) low = mid + 1;
        else high = mid - 1;
    }
    return -1;
}
"""
    report = inspector.inspect_cpp(code)
    assert report.passed is True
    assert report.score == 20.0
    assert len(report.violations) == 0


@pytest.mark.parametrize(
    "header",
    [
        "#include <thread>",
        "#include <sys/socket.h>",
        "#include <sys/types.h>",
        "#include <unistd.h>",
        "#include <dlfcn.h>",
        '#include "unistd.h"',
    ],
)
def test_cpp_banned_headers(inspector: ASTCodeInspector, header: str):
    """Verify banned C++ system headers are detected."""
    code = f"""
{header}
#include <iostream>

int main() {{ return 0; }}
"""
    report = inspector.inspect_cpp(code)
    assert report.passed is False
    assert report.score == 0.0
    assert any("Banned C++ header" in v for v in report.violations)


@pytest.mark.parametrize(
    "syscall",
    [
        'system("rm -rf /")',
        'popen("ls", "r")',
        "fork()",
        "clone()",
        "execve(path, argv, envp)",
        "socket(AF_INET, SOCK_STREAM, 0)",
        "kill(pid, SIGKILL)",
    ],
)
def test_cpp_dangerous_syscalls(inspector: ASTCodeInspector, syscall: str):
    """Verify dangerous syscall keywords are flagged in C++ code."""
    code = f"""
#include <iostream>

void dangerous() {{
    {syscall};
}}
"""
    report = inspector.inspect_cpp(code)
    assert report.passed is False
    assert report.score == 0.0
    assert any("Dangerous C++ syscall keyword" in v for v in report.violations)


@pytest.mark.parametrize(
    "macro",
    [
        "#define EXPECT_EQ(a, b) (true)",
        "#define ASSERT_TRUE(x) (true)",
        "#define private public",
    ],
)
def test_cpp_tampering_macros(inspector: ASTCodeInspector, macro: str):
    """Verify macros attempting to override testing framework or encapsulation are flagged."""
    code = f"""
{macro}
#include <iostream>

int main() {{ return 0; }}
"""
    report = inspector.inspect_cpp(code)
    assert report.passed is False
    assert report.score == 0.0
    assert any("Test framework tampering macro" in v for v in report.violations)


def test_cpp_comments_do_not_trigger_false_positives(inspector: ASTCodeInspector):
    """Verify C++ comments containing keywords do not false-positive."""
    code = """
#include <iostream>

// We do not fork here
/* We never use system() or kill() */
int compute(int x) {
    // #include <thread>
    return x * 2;
}
"""
    report = inspector.inspect_cpp(code)
    assert report.passed is True
    assert report.score == 20.0
    assert len(report.violations) == 0


# -----------------------------------------------------------------------------
# 12. Unified Dispatch Method
# -----------------------------------------------------------------------------
def test_inspect_dispatch_python(inspector: ASTCodeInspector):
    """Verify inspect dispatch for Python."""
    report = inspector.inspect("def f(): return 1", language="python")
    assert report.passed is True
    assert report.score == 20.0

    report_py = inspector.inspect("def f(): return 1", language="py")
    assert report_py.passed is True


def test_inspect_dispatch_cpp(inspector: ASTCodeInspector):
    """Verify inspect dispatch for C++."""
    report = inspector.inspect("int main() { return 0; }", language="cpp")
    assert report.passed is True
    assert report.score == 20.0

    report_cxx = inspector.inspect("int main() { return 0; }", language="c++")
    assert report_cxx.passed is True


def test_inspect_dispatch_unsupported_language(inspector: ASTCodeInspector):
    """Verify inspect raises ValueError for unsupported languages."""
    with pytest.raises(ValueError, match="Unsupported language"):
        inspector.inspect("fn main() {}", language="rust")


# -----------------------------------------------------------------------------
# 13. Re-export Verification
# -----------------------------------------------------------------------------
def test_reexports():
    """Verify ASTCodeInspector and AntiCheatVisitor are exposed from evalforge.grader."""
    from evalforge.grader import AntiCheatVisitor as ImportedVisitor
    from evalforge.grader import ASTCodeInspector as ImportedInspector

    assert ImportedInspector is ASTCodeInspector
    assert ImportedVisitor is AntiCheatVisitor
