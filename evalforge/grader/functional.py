"""Parsers and helpers for test execution runner reports (pytest and Google Test)."""

import json
import re
from typing import Any

from evalforge.core.constants import ErrorTypeEnum
from evalforge.models.schemas import ExecutionResult


def parse_pytest_json_report(report_data: dict[str, Any] | str | None) -> tuple[int, int, int]:
    """Parse a test report emitted by pytest-json-report.

    Args:
        report_data: Dictionary or JSON string representing pytest-json-report output.

    Returns:
        tuple[int, int, int]: (passed_tests, total_tests, failed_tests).
    """
    if report_data is None:
        return 0, 0, 0

    if isinstance(report_data, str):
        cleaned = report_data.strip()
        if not cleaned:
            return 0, 0, 0
        try:
            data = json.loads(cleaned)
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            return 0, 0, 0
    elif isinstance(report_data, dict):
        data = report_data
    else:
        return 0, 0, 0

    if not isinstance(data, dict):
        return 0, 0, 0

    passed = 0
    failed = 0
    total = 0

    # 1. Inspect summary dictionary if present
    summary = data.get("summary")
    if isinstance(summary, dict) and summary:
        try:
            passed = int(summary.get("passed", 0))
            failed = (
                int(summary.get("failed", 0))
                + int(summary.get("error", 0))
                + int(summary.get("errors", 0))
            )
            raw_total = summary.get("total")
            if raw_total is None:
                raw_total = summary.get("collected")

            if raw_total is not None and int(raw_total) > 0:
                total = int(raw_total)
            else:
                total = passed + failed

            if total < passed + failed:
                total = passed + failed

            return max(0, passed), max(0, total), max(0, failed)
        except (TypeError, ValueError):
            pass

    # 2. Inspect individual tests array if present
    tests = data.get("tests")
    if isinstance(tests, list) and tests:
        for t in tests:
            if isinstance(t, dict):
                outcome = t.get("outcome")
                if outcome == "passed":
                    passed += 1
                elif outcome in ("failed", "error"):
                    failed += 1
        total = max(len(tests), passed + failed)
        return max(0, passed), max(0, total), max(0, failed)

    # 3. Inspect top-level keys fallback
    if "passed" in data or "total" in data or "failed" in data:
        try:
            passed = int(data.get("passed", 0))
            failed = int(data.get("failed", 0))
            total = int(data.get("total", passed + failed))
            total = max(total, passed + failed)
            return max(0, passed), max(0, total), max(0, failed)
        except (TypeError, ValueError):
            pass

    return 0, 0, 0


def parse_gtest_json_report(report_data: dict[str, Any] | str | None) -> tuple[int, int, int]:
    """Parse a Google Test JSON report emitted by --gtest_output=json:<path>.

    Args:
        report_data: Dictionary or JSON string representing Google Test JSON output.

    Returns:
        tuple[int, int, int]: (passed_tests, total_tests, failed_tests).
    """
    if report_data is None:
        return 0, 0, 0

    if isinstance(report_data, str):
        cleaned = report_data.strip()
        if not cleaned:
            return 0, 0, 0
        try:
            data = json.loads(cleaned)
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            return 0, 0, 0
    elif isinstance(report_data, dict):
        data = report_data
    else:
        return 0, 0, 0

    if not isinstance(data, dict):
        return 0, 0, 0

    total_tests = 0
    failed_tests = 0
    suites_found = False

    # 1. Parse 'testsuites' collection
    testsuites = data.get("testsuites")
    if isinstance(testsuites, list) and testsuites:
        suites_found = True
        for suite in testsuites:
            if isinstance(suite, dict):
                suite_total = 0
                suite_failed = 0
                try:
                    suite_total = int(suite.get("tests", 0))
                    suite_failed = int(suite.get("failures", 0)) + int(suite.get("errors", 0))
                except (TypeError, ValueError):
                    pass

                # Fallback to testsuite case entries if tests count not populated
                suite_cases = suite.get("testsuite")
                if isinstance(suite_cases, list) and suite_cases and suite_total == 0:
                    suite_total = len(suite_cases)
                    for case in suite_cases:
                        if isinstance(case, dict) and (
                            case.get("failures") or case.get("status") == "FAIL"
                        ):
                            suite_failed += 1

                total_tests += suite_total
                failed_tests += suite_failed

    # 2. Check top-level 'tests' and 'failures'/'errors' if testsuites was missing or empty
    if not suites_found or total_tests == 0:
        if "tests" in data:
            try:
                total_tests = int(data.get("tests", 0))
                failed_tests = int(data.get("failures", 0)) + int(data.get("errors", 0))
            except (TypeError, ValueError):
                pass

    total_tests = max(0, total_tests)
    failed_tests = max(0, failed_tests)
    if total_tests < failed_tests:
        total_tests = failed_tests

    passed_tests = max(0, total_tests - failed_tests)
    return passed_tests, total_tests, failed_tests


def extract_test_counts_from_execution(
    execution: ExecutionResult,
    language: str = "python",
    fallback_total: int = 0,
) -> tuple[int, int, int]:
    """Extract passed, total, and failed test counts from ExecutionResult.

    Attempts JSON report parsing from stdout, falls back to regex terminal output parsing,
    and finally falls back to exit_code status.

    Args:
        execution: ExecutionResult containing execution outputs and exit code.
        language: Programming language ('python' or 'cpp').
        fallback_total: Optional expected total tests if exit code is 0 but no output found.

    Returns:
        tuple[int, int, int]: (passed_tests, total_tests, failed_tests).
    """
    stdout = execution.stdout or ""
    stderr = execution.stderr or ""
    combined = f"{stdout}\n{stderr}"
    lang = language.lower()

    # 1. Attempt to parse stdout as JSON report
    if stdout.strip().startswith("{") and stdout.strip().endswith("}"):
        if lang in ("cpp", "c++", "cxx"):
            p, t, f = parse_gtest_json_report(stdout)
            if t > 0:
                return p, t, f
        else:
            p, t, f = parse_pytest_json_report(stdout)
            if t > 0:
                return p, t, f

    # 2. Regex fallback for terminal output
    if lang in ("cpp", "c++", "cxx"):
        pass_match = re.search(r"\[\s*PASSED\s*\]\s*(\d+)\s*tests?", combined)
        fail_match = re.search(r"\[\s*FAILED\s*\]\s*(\d+)\s*tests?", combined)
        ran_match = re.search(r"\[==========\]\s*(\d+)\s*tests?", combined)

        passed = int(pass_match.group(1)) if pass_match else 0
        failed = int(fail_match.group(1)) if fail_match else 0
        total = int(ran_match.group(1)) if ran_match else (passed + failed)

        if total > 0:
            return passed, max(total, passed + failed), failed
    else:
        # Pytest summary terminal output: e.g. '5 passed', '3 passed, 2 failed in 0.12s'
        pass_match = re.search(r"(\d+)\s+passed", combined)
        fail_match = re.search(r"(\d+)\s+failed", combined)
        err_match = re.search(r"(\d+)\s+error", combined)

        passed = int(pass_match.group(1)) if pass_match else 0
        failed = (int(fail_match.group(1)) if fail_match else 0) + (
            int(err_match.group(1)) if err_match else 0
        )
        total = passed + failed

        if total > 0:
            return passed, total, failed

    # 3. Status exit code fallback
    if execution.exit_code == 0 and execution.error_type == ErrorTypeEnum.NONE:
        count = max(1, fallback_total)
        return count, count, 0

    return 0, fallback_total, fallback_total
