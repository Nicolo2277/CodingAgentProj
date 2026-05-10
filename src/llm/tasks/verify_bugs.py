from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from src.llm.client import BaseLLMClient
from src.llm.prompts.generate_tests import GenerateTestsPrompt
from src.llm.prompts.interpret_results import InterpretResultsPrompt
from src.models.schemas import (
    BugReport,
    TestCase,
    VerificationResult,
    VerifiedBugReport,
)
from src.logger import get_logger
from src.config import _TEST_TIMEOUT_SEC, _OUTPUT_TRUNCATE

logger = get_logger(__name__)


def _module_import_path(file_path: Path, repo_path: Path) -> str:
    """Convert  src/tools/file_reader.py  →  src.tools.file_reader"""
    relative = file_path.relative_to(repo_path)
    return str(relative.with_suffix("")).replace("\\", "/").replace("/", ".")


def _validate_syntax(code: str) -> tuple[bool, str]:
    """Return (is_valid, error_message)."""
    try:
        ast.parse(code)
        return True, ""
    except SyntaxError as e:
        return False, f"SyntaxError at line {e.lineno}: {e.msg}"


def _run_script(test_code: str, repo_path: Path) -> tuple[str, int]:
    """
    Write *test_code* to a temp file, execute it, return (combined_output, returncode).
    The temp file is always cleaned up, even on error.
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as fh:
        fh.write(test_code)
        tmp_path = Path(fh.name)

    try:
        proc = subprocess.run(
            [sys.executable, str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=_TEST_TIMEOUT_SEC,
            cwd=str(repo_path),
        )
        combined = (proc.stdout + proc.stderr).strip()
        return combined[:_OUTPUT_TRUNCATE], proc.returncode

    except subprocess.TimeoutExpired as exc:
        partial = (
            (exc.stdout or b"").decode("utf-8", errors="replace")
            if isinstance(exc.stdout, bytes)
            else (exc.stdout or "")
        )
        return f"[TIMEOUT after {_TEST_TIMEOUT_SEC}s]\n{partial}"[:_OUTPUT_TRUNCATE], -1

    except Exception as exc:  # noqa: BLE001
        return f"[RUNNER ERROR: {exc}]", -1

    finally:
        tmp_path.unlink(missing_ok=True)


def _generate_test_cases(
    code: str,
    report: BugReport,
    file_path: Path,
    repo_path: Path,
    client: BaseLLMClient,
) -> list[TestCase]:
    module_path   = str(file_path.relative_to(repo_path))
    module_import = _module_import_path(file_path, repo_path)
    bugs_json     = json.dumps(
        [{"index": i, **bug.model_dump()} for i, bug in enumerate(report.bugs)],
        indent=2,
    )

    system, user = GenerateTestsPrompt.build(
        module_path=module_path,
        module_import=module_import,
        code=code,
        bugs_json=bugs_json,
    )

    logger.debug("Requesting test generation for %d bugs…", len(report.bugs))
    response   = client.complete(user, system=system, json_mode=True)
    raw_cases  = response.as_json().get("test_cases", [])

    test_cases = [
        TestCase(
            bug_index=tc["bug_index"],
            description=tc["description"],
            test_code=tc["test_code"],
        )
        for tc in raw_cases
    ]

    logger.info(
        "Generated %d/%d test cases in %dms",
        len(test_cases), len(report.bugs), response.duration_ms,
    )
    return test_cases


def _interpret_result(
    bug_index: int,
    report: BugReport,
    test_case: TestCase,
    test_output: str,
    returncode: int,
    client: BaseLLMClient,
) -> VerificationResult:
    bug = report.bugs[bug_index]

    system, user = InterpretResultsPrompt.build(
        bug_index=bug_index,
        bug_description=bug.description,
        severity=bug.severity,
        fix=bug.fix,
        test_code=test_case.test_code,
        test_output=test_output or "(no output)",
        returncode=returncode,
    )

    response = client.complete(user, system=system, json_mode=True)
    data     = response.as_json()

    return VerificationResult(
        bug_index=bug_index,
        verdict=data["verdict"],
        test_output=test_output,
        explanation=data["explanation"],
    )


def verify_bugs(
    code: str,
    report: BugReport,
    file_path: Path,
    repo_path: Path,
    client: BaseLLMClient,
) -> VerifiedBugReport:
    """
    Full verification pipeline:
      1. Generate one test case per bug via LLM
      2. Validate syntax; skip malformed tests
      3. Execute each test in a subprocess
      4. Interpret each result via LLM → confirmed / refuted / inconclusive
    """
    logger.info(
        "Verification started — %s (%d bugs)",
        file_path.name, len(report.bugs),
    )

    # Fast-path: nothing to verify
    if not report.bugs:
        logger.info("No bugs to verify — skipping.")
        return VerifiedBugReport(
            original_report=report,
            test_cases=[],
            verifications=[],
        )

    # Step 1: generate
    try:
        test_cases = _generate_test_cases(code, report, file_path, repo_path, client)
    except Exception as exc:  # noqa: BLE001
        logger.error("Test generation failed entirely: %s", exc)
        return VerifiedBugReport(
            original_report=report,
            test_cases=[],
            verifications=[
                VerificationResult(
                    bug_index=i,
                    verdict="generation_error",
                    test_output="",
                    explanation=f"Test generation failed: {exc}",
                )
                for i in range(len(report.bugs))
            ],
        )

    # Steps 2–4: validate → run → interpret
    verifications: list[VerificationResult] = []
    tested_indices: set[int] = set()

    for tc in test_cases:
        tested_indices.add(tc.bug_index)

        # Syntax gate
        valid, syntax_err = _validate_syntax(tc.test_code)
        if not valid:
            logger.warning("Bug #%d — generated test has syntax error: %s", tc.bug_index, syntax_err)
            verifications.append(VerificationResult(
                bug_index=tc.bug_index,
                verdict="generation_error",
                test_output="",
                explanation=f"Generated test has a syntax error: {syntax_err}",
            ))
            continue

        # Execute
        logger.debug("Running test for bug #%d: %s", tc.bug_index, tc.description)
        output, returncode = _run_script(tc.test_code, repo_path)
        logger.debug("Bug #%d exit=%d | output: %s", tc.bug_index, returncode, output[:120])

        # Interpret
        try:
            result = _interpret_result(tc.bug_index, report, tc, output, returncode, client)
        except Exception as exc:  # noqa: BLE001
            logger.error("Interpretation failed for bug #%d: %s", tc.bug_index, exc)
            result = VerificationResult(
                bug_index=tc.bug_index,
                verdict="inconclusive",
                test_output=output,
                explanation=f"Interpretation error: {exc}",
            )

        verifications.append(result)
        logger.info(
            "Bug #%d [%-12s] — %s",
            tc.bug_index, result.verdict, result.explanation,
        )

    # Fill gaps: bugs for which no test case was generated
    for i in range(len(report.bugs)):
        if i not in tested_indices:
            logger.warning("Bug #%d had no test case generated — marking inconclusive", i)
            verifications.append(VerificationResult(
                bug_index=i,
                verdict="inconclusive",
                test_output="",
                explanation="No test case was generated for this bug.",
            ))

    # Sort by bug_index for deterministic output
    verifications.sort(key=lambda v: v.bug_index)

    verified = VerifiedBugReport(
        original_report=report,
        test_cases=test_cases,
        verifications=verifications,
    )
    logger.info(
        "Verification complete — confirmed=%d refuted=%d inconclusive=%d rate=%.0f%%",
        verified.confirmed_count,
        verified.refuted_count,
        sum(1 for v in verifications if v.verdict == "inconclusive"),
        verified.confirmation_rate * 100,
    )
    return verified