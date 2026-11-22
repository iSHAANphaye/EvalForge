"""AST anti-cheat and static code analysis inspector for Python and C++."""

from __future__ import annotations

import ast
import re
from typing import Any

from evalforge.core.constants import MAX_POINTS_ANTI_CHEAT
from evalforge.models.schemas import ASTAuditReport

# -----------------------------------------------------------------------------
# Python Inspection Constants
# -----------------------------------------------------------------------------
BANNED_MODULES: frozenset[str] = frozenset({
    "os",
    "subprocess",
    "ctypes",
    "socket",
    "pty",
    "shutil",
    "urllib",
    "requests",
    "aiohttp",
    "importlib",
    "inspect",
    "builtins",
})

BANNED_SYS_ATTRIBUTES: frozenset[str] = frozenset({
    "exit",
    "modules",
    "_getframe",
    "setrecursionlimit",
    "audit",
})

SAFE_SYS_ATTRIBUTES: frozenset[str] = frozenset({
    "stdin",
    "stdout",
    "stderr",
    "maxsize",
})

DANGEROUS_BUILTINS: frozenset[str] = frozenset({
    "eval",
    "exec",
    "compile",
    "__import__",
    "open",
    "globals",
    "locals",
    "breakpoint",
    "getattr",
    "setattr",
    "delattr",
})

EARLY_EXIT_FUNCTIONS: frozenset[str] = frozenset({
    "exit",
    "quit",
})

EARLY_EXIT_ATTRIBUTES: frozenset[str] = frozenset({
    "exit",
    "_exit",
})

FRAMEWORK_TAMPERING_NAMES: frozenset[str] = frozenset({
    "pytest",
    "unittest",
    "mock",
    "monkeypatch",
    "_pytest",
})

DANGEROUS_DUNDERS: frozenset[str] = frozenset({
    "__globals__",
    "__subclasses__",
    "__code__",
    "__builtins__",
})

# -----------------------------------------------------------------------------
# C++ Inspection Patterns
# -----------------------------------------------------------------------------
CPP_BANNED_HEADERS_RE: re.Pattern[str] = re.compile(
    r'#\s*include\s*[<"](thread|unistd\.h|dlfcn\.h|sys/[^>"]+)[>"]',
    re.IGNORECASE,
)

CPP_SYSCALL_KEYWORDS_RE: re.Pattern[str] = re.compile(
    r"\b(system|popen|fork|clone|execve|socket|kill)\b",
)

CPP_TAMPERING_MACROS_RE: re.Pattern[str] = re.compile(
    r"#\s*define\s+(EXPECT_EQ|ASSERT_TRUE|ASSERT_EQ|EXPECT_TRUE|private\s+public)\b",
)


def _is_constant_val(expr: ast.AST | None) -> bool:
    """Return True if the expression is a static literal constant."""
    if expr is None:
        return True
    if isinstance(expr, ast.Constant):
        return True
    if isinstance(expr, ast.UnaryOp) and isinstance(expr.operand, ast.Constant):
        return True
    if isinstance(expr, (ast.List, ast.Tuple, ast.Set)):
        return all(_is_constant_val(elt) for elt in expr.elts)
    if isinstance(expr, ast.Dict):
        return all(
            _is_constant_val(k) and _is_constant_val(v)
            for k, v in zip(expr.keys, expr.values, strict=False)
        )
    return False


def _is_constant_equality_test(test: ast.AST) -> bool:
    """Check if condition compares an expression against a literal constant."""
    if isinstance(test, ast.Compare):
        for op, comp in zip(test.ops, test.comparators, strict=False):
            if isinstance(op, ast.Eq):
                if _is_constant_val(test.left) or _is_constant_val(comp):
                    return True
            elif isinstance(op, ast.In) and _is_constant_val(comp):
                return True
    return False


def _branch_returns_constant(body: list[ast.stmt]) -> bool:
    """Check if the branch body contains a return statement with a literal constant."""
    for stmt in body:
        if isinstance(stmt, ast.Return):
            return _is_constant_val(stmt.value)
    return False


def _flatten_if_branches(if_node: ast.If) -> list[tuple[ast.AST | None, list[ast.stmt]]]:
    """Flatten an if-elif-else chain into a list of (condition, body) pairs."""
    branches: list[tuple[ast.AST | None, list[ast.stmt]]] = []
    curr: ast.AST = if_node
    while isinstance(curr, ast.If):
        branches.append((curr.test, curr.body))
        if len(curr.orelse) == 1 and isinstance(curr.orelse[0], ast.If):
            curr = curr.orelse[0]
        else:
            if curr.orelse:
                branches.append((None, curr.orelse))
            break
    return branches


def compute_ldd_for_statements(
    statements: list[ast.stmt],
) -> tuple[float, int, int]:
    """Calculate Literal Decision Density (LDD), loop count, and hardcoded branch count."""
    loops = 0
    hardcoded_equality_branches = 0
    total_algorithmic_statements = 0

    body = statements
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body = body[1:]

    for stmt in body:
        if isinstance(stmt, ast.Pass):
            continue
        if isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
            loops += 1
            total_algorithmic_statements += 1
        elif isinstance(stmt, ast.If):
            chain = _flatten_if_branches(stmt)
            for test, b_body in chain:
                total_algorithmic_statements += 1
                # Check for nested loops in if branch
                loops += sum(
                    1 for n in b_body if isinstance(n, (ast.For, ast.AsyncFor, ast.While))
                )
                if test is not None and _is_constant_equality_test(test) and _branch_returns_constant(b_body):
                    hardcoded_equality_branches += 1
        elif isinstance(stmt, ast.Match):
            for case in stmt.cases:
                total_algorithmic_statements += 1
                if isinstance(case.pattern, (ast.MatchValue, ast.MatchSingleton)) and _branch_returns_constant(case.body):
                    hardcoded_equality_branches += 1
        else:
            total_algorithmic_statements += 1

    ldd = (
        round(hardcoded_equality_branches / total_algorithmic_statements, 4)
        if total_algorithmic_statements > 0
        else 0.0
    )
    return ldd, loops, hardcoded_equality_branches


def compute_cyclomatic_complexity(tree: ast.AST) -> int:
    """Calculate McCabe cyclomatic complexity: M = 1 + decisions."""
    decisions = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.If, ast.IfExp)):
            decisions += 1
        elif isinstance(node, (ast.While, ast.For, ast.AsyncFor)):
            decisions += 1
        elif isinstance(node, ast.BoolOp):
            decisions += max(0, len(node.values) - 1)
        elif isinstance(node, ast.ExceptHandler):
            decisions += 1
        elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
            for gen in node.generators:
                decisions += 1
                decisions += len(gen.ifs)
        elif isinstance(node, ast.match_case):
            decisions += 1
    return 1 + decisions


def strip_cpp_comments_and_strings(code: str) -> str:
    """Strip C++ comments and string literals to prevent false positives."""
    pattern = r'//.*?$|/\*.*?\*/|\'(?:\\.|[^\\\'])*\'|"(?:\\.|[^\\"])*"'

    def replacer(match: re.Match[str]) -> str:
        s = match.group(0)
        return " " if s.startswith(("//", "/*", '"', "'")) else s

    return re.sub(pattern, replacer, code, flags=re.MULTILINE | re.DOTALL)


def strip_cpp_comments(code: str) -> str:
    """Strip C++ comments preserving preprocessor directives and statements."""
    pattern = r"//.*?$|/\*.*?\*/"
    return re.sub(pattern, " ", code, flags=re.MULTILINE | re.DOTALL)


class AntiCheatVisitor(ast.NodeVisitor):
    """AST NodeVisitor that inspects Python source code for security violations and cheats."""

    def __init__(self) -> None:
        self.violations: list[str] = []
        self.cheat_detected: bool = False
        self.sys_aliases: set[str] = {"sys"}

    def add_violation(self, message: str, is_cheat: bool = True) -> None:
        """Register a violation and optionally flag cheat_detected."""
        if is_cheat:
            self.cheat_detected = True
        if message not in self.violations:
            self.violations.append(message)

    def visit_Import(self, node: ast.Import) -> None:
        """Flag banned module imports and track sys aliases."""
        for alias in node.names:
            root = alias.name.split(".")[0]
            if root == "sys":
                if alias.asname:
                    self.sys_aliases.add(alias.asname)
                else:
                    self.sys_aliases.add("sys")
            elif root in BANNED_MODULES:
                self.add_violation(f"Banned module import: '{alias.name}'")
            elif root in FRAMEWORK_TAMPERING_NAMES:
                self.add_violation(f"Test harness tampering: import of '{alias.name}'")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Flag banned from-imports, dangerous sys imports, and test harness imports."""
        module = node.module or ""
        root = module.split(".")[0] if module else ""
        if root in BANNED_MODULES:
            self.add_violation(f"Banned module import: '{module}'")
        elif root in FRAMEWORK_TAMPERING_NAMES:
            self.add_violation(f"Test harness tampering: import from '{module}'")
        elif root == "sys":
            for alias in node.names:
                if alias.name in BANNED_SYS_ATTRIBUTES:
                    self.add_violation(f"Banned sys member imported: 'sys.{alias.name}'")
                elif alias.name == "*":
                    self.add_violation("Wildcard import from sys is forbidden")

        for alias in node.names:
            if alias.name in FRAMEWORK_TAMPERING_NAMES:
                self.add_violation(f"Test harness tampering: import '{alias.name}'")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Flag dangerous builtin calls and early exit routines."""
        if isinstance(node.func, ast.Name):
            func_id = node.func.id
            if func_id in DANGEROUS_BUILTINS:
                self.add_violation(f"Dangerous builtin call: '{func_id}()'")
            elif func_id in EARLY_EXIT_FUNCTIONS:
                self.add_violation(f"Early process exit trap: call to '{func_id}()'")
        elif isinstance(node.func, ast.Attribute):
            attr_name = node.func.attr
            if attr_name in DANGEROUS_BUILTINS:
                self.add_violation(f"Dangerous builtin call: '{attr_name}()'")
            if isinstance(node.func.value, ast.Name):
                val_id = node.func.value.id
                if val_id in self.sys_aliases and attr_name in BANNED_SYS_ATTRIBUTES:
                    self.add_violation(f"Banned sys call: 'sys.{attr_name}()'")
                elif (val_id in self.sys_aliases or val_id == "os") and attr_name in EARLY_EXIT_ATTRIBUTES:
                    self.add_violation(f"Early process exit trap: call to '{val_id}.{attr_name}()'")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """Inspect attribute accesses for dangerous dunders, tampering, and sys abuse."""
        if node.attr in DANGEROUS_DUNDERS:
            self.add_violation(f"Dangerous dunder attribute access: '{node.attr}'")
        elif node.attr in FRAMEWORK_TAMPERING_NAMES:
            self.add_violation(f"Test harness tampering reference: '{node.attr}'")
        elif isinstance(node.value, ast.Name) and node.value.id in self.sys_aliases:
            if node.attr in BANNED_SYS_ATTRIBUTES:
                self.add_violation(f"Banned sys attribute accessed: 'sys.{node.attr}'")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        """Flag identifier references to test harnesses."""
        if node.id in FRAMEWORK_TAMPERING_NAMES:
            self.add_violation(f"Test harness tampering reference: '{node.id}'")
        self.generic_visit(node)

    def visit_Raise(self, node: ast.Raise) -> None:
        """Detect early exit traps via raise SystemExit."""
        if node.exc is not None:
            is_system_exit = False
            if isinstance(node.exc, ast.Name) and node.exc.id == "SystemExit":
                is_system_exit = True
            elif isinstance(node.exc, ast.Call):
                if isinstance(node.exc.func, ast.Name) and node.exc.func.id == "SystemExit":
                    is_system_exit = True
                elif isinstance(node.exc.func, ast.Attribute) and node.exc.func.attr == "SystemExit":
                    is_system_exit = True
            elif isinstance(node.exc, ast.Attribute) and node.exc.attr == "SystemExit":
                is_system_exit = True

            if is_system_exit:
                self.add_violation("Early process exit trap: 'raise SystemExit'")
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        """Detect attempts to swallow AssertionError."""
        if node.type is not None:
            caught: list[str] = []
            if isinstance(node.type, ast.Name):
                caught.append(node.type.id)
            elif isinstance(node.type, ast.Tuple):
                caught.extend(
                    elt.id for elt in node.type.elts if isinstance(elt, ast.Name)
                )
            if "AssertionError" in caught:
                self.add_violation("Test harness tampering: catching AssertionError")
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        """Flag reassignments to AssertionError."""
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "AssertionError":
                self.add_violation("Test harness tampering: modifying AssertionError")
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        """Flag annotated assignments to AssertionError."""
        if isinstance(node.target, ast.Name) and node.target.id == "AssertionError":
            self.add_violation("Test harness tampering: modifying AssertionError")
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Flag classes redefining AssertionError."""
        if node.name == "AssertionError":
            self.add_violation("Test harness tampering: defining 'AssertionError'")
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Flag functions redefining AssertionError."""
        if node.name == "AssertionError":
            self.add_violation("Test harness tampering: defining 'AssertionError'")
        self.generic_visit(node)


class ASTCodeInspector:
    """Static AST anti-cheat and security inspector for Python and C++ benchmark submissions."""

    def inspect_python(self, code: str) -> ASTAuditReport:
        """Inspect Python candidate code using AST parsing and visitor analysis."""
        try:
            tree = ast.parse(code)
        except SyntaxError as exc:
            return ASTAuditReport(
                passed=False,
                score=0.0,
                violations=[f"SyntaxError: {exc}"],
                literal_decision_density=0.0,
                cyclomatic_complexity=0,
            )

        visitor = AntiCheatVisitor()
        visitor.visit(tree)

        # ---------------------------------------------------------------------
        # Literal Decision Density (LDD) Analysis
        # ---------------------------------------------------------------------
        max_ldd = 0.0
        func_found = False

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_found = True
                ldd, loops, hardcoded_branches = compute_ldd_for_statements(node.body)
                if ldd > max_ldd:
                    max_ldd = ldd

                if ldd > 0.60 and loops == 0 and hardcoded_branches > 3:
                    visitor.add_violation(
                        f"HARDCODED_LOOKUP_TABLE: Function '{node.name}' has Literal Decision "
                        f"Density {ldd:.2f} > 0.60 with 0 loops and {hardcoded_branches} "
                        "hardcoded equality branches."
                    )

        if not func_found:
            # Check module-level statements if no functions defined
            ldd, loops, hardcoded_branches = compute_ldd_for_statements(tree.body)
            max_ldd = ldd
            if ldd > 0.60 and loops == 0 and hardcoded_branches > 3:
                visitor.add_violation(
                    f"HARDCODED_LOOKUP_TABLE: Module statements have Literal Decision "
                    f"Density {ldd:.2f} > 0.60 with 0 loops and {hardcoded_branches} "
                    "hardcoded equality branches."
                )

        # ---------------------------------------------------------------------
        # Cyclomatic Complexity Analysis
        # ---------------------------------------------------------------------
        complexity = compute_cyclomatic_complexity(tree)
        complexity_warning = False
        if complexity > 25:
            complexity_warning = True
            visitor.add_violation(
                f"EXCESSIVE_CYCLOMATIC_COMPLEXITY: McCabe complexity {complexity} "
                "exceeds maximum threshold of 25",
                is_cheat=False,
            )

        # ---------------------------------------------------------------------
        # Scoring Calculation (0.0 to 20.0)
        # ---------------------------------------------------------------------
        if visitor.cheat_detected:
            passed = False
            score = 0.0
        else:
            passed = True
            if complexity_warning:
                score = max(0.0, MAX_POINTS_ANTI_CHEAT - 10.0)
            else:
                score = MAX_POINTS_ANTI_CHEAT

        return ASTAuditReport(
            passed=passed,
            score=round(score, 2),
            violations=visitor.violations,
            literal_decision_density=round(max_ldd, 2),
            cyclomatic_complexity=complexity,
        )

    def inspect_cpp(self, code: str) -> ASTAuditReport:
        """Inspect C++ candidate code using lexical and regular expression analysis."""
        violations: list[str] = []

        clean_code_comments = strip_cpp_comments(code)
        clean_code_tokens = strip_cpp_comments_and_strings(code)

        # 1. Banned headers
        for match in CPP_BANNED_HEADERS_RE.finditer(clean_code_comments):
            violations.append(f"Banned C++ header: '{match.group(0).strip()}'")

        # 2. Dangerous syscall keywords with word boundaries
        for match in CPP_SYSCALL_KEYWORDS_RE.finditer(clean_code_tokens):
            violations.append(f"Dangerous C++ syscall keyword: '{match.group(1)}'")

        # 3. Macro attempts to override test framework
        for match in CPP_TAMPERING_MACROS_RE.finditer(clean_code_comments):
            violations.append(f"Test framework tampering macro: '{match.group(0).strip()}'")

        passed = len(violations) == 0
        score = MAX_POINTS_ANTI_CHEAT if passed else 0.0

        return ASTAuditReport(
            passed=passed,
            score=round(score, 2),
            violations=violations,
            literal_decision_density=0.0,
            cyclomatic_complexity=0,
        )

    def inspect(self, code: str, language: str = "python") -> ASTAuditReport:
        """Unified dispatch method for code inspection across languages."""
        lang = language.strip().lower()
        if lang in ("python", "py"):
            return self.inspect_python(code)
        if lang in ("cpp", "c++", "cxx"):
            return self.inspect_cpp(code)
        raise ValueError(f"Unsupported language for AST inspection: '{language}'")

    @classmethod
    def audit(
        cls,
        code: str,
        language: str = "python",
        rubric_rules: dict[str, Any] | None = None,
    ) -> ASTAuditReport:
        """Convenience classmethod for running AST inspection."""
        inspector = cls()
        return inspector.inspect(code, language=language)

