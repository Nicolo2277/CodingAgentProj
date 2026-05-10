from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from src.agent.state import AgentState
from src.llm.client import BaseLLMClient
from src.llm.tasks.find_bugs import find_bugs
from src.llm.tasks.verify_bugs import verify_bugs
from src.models.schemas import RunResult, VerifiedBugReport
from src.tools.file_reader import read_python_file
from src.tools.file_scanner import scan_python_files
from src.tools.output_writer import save_file_report, save_verified_report
from src.logger import get_logger
from src.config import _RUN_TIMEOUT_SEC, _OUTPUT_TRUNCATE

logger = get_logger(__name__)

#  list_files 

def tool_list_files(state: AgentState) -> tuple[str, dict]:
    files = scan_python_files(state["repo_path"])
    if not files:
        return "No Python files found.", {}
    file_list = [str(f.relative_to(state["repo_path"])) for f in files]
    result = "\n".join(
        f"{f} ({(state['repo_path'] / f).stat().st_size} bytes)"
        for f in file_list
    )
    return result, {"available_files": file_list}


# analyze_file

def tool_analyze_file(
    state: AgentState,
    file_input: str,
    client: BaseLLMClient,
) -> tuple[str, dict]:
    file_input = file_input.strip()
    file_path  = state["repo_path"] / file_input

    if file_input in state.get("files_analyzed", []):
        return "File already analyzed, skipping.", {}

    try:
        code   = read_python_file(file_path)
        report = find_bugs(code, client)
        save_file_report(state["repo_path"], file_path, report)

        updated_reports = {**state.get("reports", {}), file_input: report}
        result = f"Found {len(report.bugs)} bugs: {report.summary}"

        return result, {
            "files_analyzed": [file_input],
            "reports":        updated_reports,
            "total_bugs":     state.get("total_bugs", 0) + len(report.bugs),
        }

    except FileNotFoundError:
        return f"File not found: {file_input}", {"files_failed": [file_input]}
    except Exception as exc:  # noqa: BLE001
        logger.error("Error analyzing %s: %s", file_input, exc)
        return f"Error: {exc}", {"files_failed": [file_input]}


# run_file

def tool_run_file(
    state: AgentState,
    file_input: str,
) -> tuple[str, dict]:
    """
    Health-check execution: confirms the file is importable and runnable in its
    natural environment.  Bug *verification* (targeted test generation) is handled
    automatically by the verifier after this call completes — do not use this tool
    to draw conclusions about individual bug findings.
    """
    file_input = file_input.strip()
    file_path  = state["repo_path"] / file_input

    if file_input in state.get("files_run", []):
        return "File already run, skipping.", {}

    if not file_path.exists():
        return f"File not found: {file_input}", {"files_failed": [file_input]}

    logger.info("Running %s (timeout=%ds)", file_path, _RUN_TIMEOUT_SEC)

    timed_out  = False
    try:
        proc = subprocess.run(
            [sys.executable, str(file_path)],
            capture_output=True,
            text=True,
            timeout=_RUN_TIMEOUT_SEC,
            cwd=str(state["repo_path"]),
        )
        returncode = proc.returncode
        stdout     = proc.stdout
        stderr     = proc.stderr

    except subprocess.TimeoutExpired as exc:
        timed_out  = True
        returncode = -1
        raw    = exc.stdout or b""
        stdout = raw.decode("utf-8", errors="replace") if isinstance(raw, (bytes, bytearray)) else str(raw)
        stderr = f"[TIMEOUT after {_RUN_TIMEOUT_SEC}s]"
        logger.warning("Timeout running %s", file_input)

    except Exception as exc:  # noqa: BLE001
        logger.error("Unexpected error running %s: %s", file_input, exc)
        return f"Error running file: {exc}", {"files_failed": [file_input]}

    stdout_t = _truncate(stdout)
    stderr_t = _truncate(stderr)

    run_result = RunResult(
        file=file_input,
        returncode=returncode,
        stdout=stdout_t,
        stderr=stderr_t,
        timed_out=timed_out,
    )
    updated_run_results = {**state.get("run_results", {}), file_input: run_result}

    status = "TIMEOUT" if timed_out else ("OK" if returncode == 0 else f"EXIT {returncode}")
    summary_lines = [f"Run result [{status}]"]
    if stdout_t:
        summary_lines.append(f"stdout:\n{stdout_t}")
    if stderr_t:
        summary_lines.append(f"stderr:\n{stderr_t}")

    logger.info(
        "Run finished — %s | exit=%d | timed_out=%s | stdout=%d chars | stderr=%d chars",
        file_input, returncode, timed_out, len(stdout), len(stderr),
    )

    return "\n".join(summary_lines), {
        "files_run":   [file_input],
        "run_results": updated_run_results,
    }


# verify_file

def tool_verify_file(
    state: AgentState,
    file_input: str,
    client: BaseLLMClient,
) -> tuple[str, dict]:
    """
    Triggered automatically after run_file when a bug report exists for the file.
    Generates targeted test cases for each bug, executes them, and produces a
    VerifiedBugReport with per-bug verdicts.
    """
    file_input = file_input.strip()
    file_path  = state["repo_path"] / file_input

    report = state.get("reports", {}).get(file_input)
    if report is None:
        logger.warning("No bug report for %s — cannot verify.", file_input)
        return "Verification skipped: no bug report available.", {}

    if file_input in state.get("files_verified", []):
        return "File already verified, skipping.", {}

    try:
        code            = read_python_file(file_path)
        verified_report = verify_bugs(code, report, file_path, state["repo_path"], client)
        save_verified_report(state["repo_path"], file_path, verified_report)

        updated_verified = {
            **state.get("verified_reports", {}),
            file_input: verified_report,
        }

        result = (
            f"Verification complete — "
            f"{verified_report.confirmed_count} confirmed, "
            f"{verified_report.refuted_count} refuted, "
            f"{len(verified_report.verifications) - verified_report.confirmed_count - verified_report.refuted_count} inconclusive "
            f"(rate {verified_report.confirmation_rate:.0%})"
        )

        return result, {
            "files_verified":  [file_input],
            "verified_reports": updated_verified,
            "confirmed_bugs":  state.get("confirmed_bugs", 0) + verified_report.confirmed_count,
        }

    except Exception as exc:  # noqa: BLE001
        logger.error("Verification error for %s: %s", file_input, exc)
        return f"Verification error: {exc}", {}


# Internal helpers

def _truncate(text: str, limit: int = _OUTPUT_TRUNCATE) -> str:
    if len(text) <= limit:
        return text
    half = limit // 2
    return text[:half] + f"\n... [truncated {len(text) - limit} chars] ...\n" + text[-half:]