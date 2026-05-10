from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from src.agent.state import AgentState
from src.config import MAX_RETRIES, VERIFIER_MIN_SCORE, _RUN_TIMEOUT_SEC, _OUTPUT_TRUNCATE
from src.llm.client import BaseLLMClient
from src.llm.tasks.find_bugs import find_bugs
from src.llm.tasks.retry_analysis import retry_analysis
from src.llm.tasks.verify_bugs import verify_bugs
from src.models.schemas import (
    AnalysisAttempt,
    BugReport,
    FilePerformance,
    RunResult,
    VerifiedBugReport,
)
from src.tools.file_reader import read_python_file
from src.tools.file_scanner import scan_python_files
from src.tools.output_writer import save_file_report, save_verified_report
from src.logger import get_logger

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

def tool_run_file(state: AgentState, file_input: str) -> tuple[str, dict]:
    """
    Health-check execution: confirms the file is importable and runnable.
    Individual bug verification is handled automatically after this call.
    """
    file_input = file_input.strip()
    file_path  = state["repo_path"] / file_input

    if file_input in state.get("files_run", []):
        return "File already run, skipping.", {}

    if not file_path.exists():
        return f"File not found: {file_input}", {"files_failed": [file_input]}

    logger.info("Running %s (timeout=%ds)", file_path, _RUN_TIMEOUT_SEC)

    timed_out = False
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
        raw        = exc.stdout or b""
        stdout     = raw.decode("utf-8", errors="replace") if isinstance(raw, (bytes, bytearray)) else str(raw)
        stderr     = f"[TIMEOUT after {_RUN_TIMEOUT_SEC}s]"
        logger.warning("Timeout running %s", file_input)

    except Exception as exc:  # noqa: BLE001
        logger.error("Unexpected error running %s: %s", file_input, exc)
        return f"Error running file: {exc}", {"files_failed": [file_input]}

    stdout_t = _truncate(stdout)
    stderr_t = _truncate(stderr)

    run_result = RunResult(
        file=file_input, returncode=returncode,
        stdout=stdout_t, stderr=stderr_t, timed_out=timed_out,
    )
    updated_run_results = {**state.get("run_results", {}), file_input: run_result}

    status = "TIMEOUT" if timed_out else ("OK" if returncode == 0 else f"EXIT {returncode}")
    lines  = [f"Run result [{status}]"]
    if stdout_t:
        lines.append(f"stdout:\n{stdout_t}")
    if stderr_t:
        lines.append(f"stderr:\n{stderr_t}")

    logger.info(
        "Run finished — %s | exit=%d | timed_out=%s",
        file_input, returncode, timed_out,
    )
    return "\n".join(lines), {"files_run": [file_input], "run_results": updated_run_results}


# verify_file (+ self-improving retry loop)

def tool_verify_file(
    state: AgentState,
    file_input: str,
    client: BaseLLMClient,
) -> tuple[str, dict]:
    """
    Full verification + self-improvement pipeline for one file:

      1. verify_bugs  → VerifiedBugReport
      2. If confirmation_rate < VERIFIER_MIN_SCORE and retries remain:
           retry_analysis (guided by verifier feedback) → new BugReport
           verify_bugs again → new VerifiedBugReport
         Repeat up to MAX_RETRIES times, keeping the best result.
      3. Record full attempt history in FilePerformance.
    """
    file_input = file_input.strip()
    file_path  = state["repo_path"] / file_input

    if file_input in state.get("files_verified", []):
        return "File already verified, skipping.", {}

    report = state.get("reports", {}).get(file_input)
    if report is None:
        logger.warning("No bug report for %s — cannot verify.", file_input)
        return "Verification skipped: no bug report available.", {}

    try:
        code = read_python_file(file_path)
    except Exception as exc:  # noqa: BLE001
        logger.error("Cannot read %s for verification: %s", file_input, exc)
        return f"Verification error (read failed): {exc}", {}

    attempts:  list[AnalysisAttempt] = []
    current_report    = report
    current_verified: VerifiedBugReport | None = None
    best_verified:    VerifiedBugReport | None = None
    best_report:      BugReport                = report

    for attempt_num in range(1, MAX_RETRIES + 2):  # 1 initial + MAX_RETRIES
        is_retry = attempt_num > 1

        if is_retry:
            logger.info(
                "Retry %d/%d for %s (previous rate: %.0f%%)",
                attempt_num - 1, MAX_RETRIES,
                file_input,
                current_verified.confirmation_rate * 100 if current_verified else 0,
            )
            try:
                current_report = retry_analysis(
                    code, current_report, current_verified, client  # type: ignore[arg-type]
                )
            except Exception as exc:  # noqa: BLE001
                logger.error("Retry analysis failed: %s", exc)
                break

        # Verify current report
        try:
            current_verified = verify_bugs(
                code, current_report, file_path, state["repo_path"], client
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Verification failed on attempt %d: %s", attempt_num, exc)
            break

        # Record this attempt
        inconclusive = sum(
            1 for v in current_verified.verifications
            if v.verdict in ("inconclusive", "generation_error")
        )
        attempts.append(AnalysisAttempt(
            attempt_number=attempt_num,
            bug_count=len(current_report.bugs),
            confirmed_count=current_verified.confirmed_count,
            refuted_count=current_verified.refuted_count,
            inconclusive_count=inconclusive,
            confirmation_rate=current_verified.confirmation_rate,
        ))

        # Track best result (highest confirmation rate)
        if best_verified is None or current_verified.confirmation_rate >= best_verified.confirmation_rate:
            best_verified = current_verified
            best_report   = current_report

        logger.info(
            "Attempt %d — %d bugs | confirmed=%d | rate=%.0f%%",
            attempt_num,
            len(current_report.bugs),
            current_verified.confirmed_count,
            current_verified.confirmation_rate * 100,
        )

        # Stop if score is satisfactory or no bugs to improve on
        if current_verified.confirmation_rate >= VERIFIER_MIN_SCORE:
            logger.info("Score threshold met — stopping retries.")
            break
        if not current_report.bugs:
            logger.info("No bugs remaining — stopping retries.")
            break
        if attempt_num == MAX_RETRIES + 1:
            logger.info("Max retries reached.")

    # Save best result 
    assert best_verified is not None  # at least one attempt always runs
    save_verified_report(state["repo_path"], file_path, best_verified)

    improved = len(attempts) > 1 and attempts[-1].confirmation_rate > attempts[0].confirmation_rate
    perf = FilePerformance(
        file=file_input,
        total_attempts=len(attempts),
        attempts=attempts,
        improved=improved,
        initial_confirmation_rate=attempts[0].confirmation_rate,
        final_confirmation_rate=attempts[-1].confirmation_rate,
    )

    # Update state: replace report with best version if it changed
    updated_reports   = {**state.get("reports", {}), file_input: best_report}
    updated_verified  = {**state.get("verified_reports", {}), file_input: best_verified}
    updated_perf      = {**state.get("performance", {}), file_input: perf}

    # confirmed_bugs delta: best minus what was previously counted for this file
    # (total_bugs was set when analyze_file ran; keep it consistent with best_report)
    old_bug_count = len(report.bugs)
    new_bug_count = len(best_report.bugs)
    bug_delta     = new_bug_count - old_bug_count

    retry_info = (
        f" ({len(attempts) - 1} retr{'y' if len(attempts) == 2 else 'ies'},"
        f" Δrate={perf.improvement_delta:+.0%})"
        if len(attempts) > 1 else ""
    )
    result = (
        f"Verification complete{retry_info} — "
        f"{best_verified.confirmed_count} confirmed, "
        f"{best_verified.refuted_count} refuted, "
        f"{len(best_verified.verifications) - best_verified.confirmed_count - best_verified.refuted_count} inconclusive "
        f"(rate {best_verified.confirmation_rate:.0%})"
    )

    return result, {
        "files_verified":  [file_input],
        "verified_reports": updated_verified,
        "reports":          updated_reports,
        "performance":      updated_perf,
        "confirmed_bugs":   state.get("confirmed_bugs", 0) + best_verified.confirmed_count,
        "total_bugs":       state.get("total_bugs", 0) + bug_delta,
    }


# Internal helpers

def _truncate(text: str, limit: int = _OUTPUT_TRUNCATE) -> str:
    if len(text) <= limit:
        return text
    half = limit // 2
    return text[:half] + f"\n... [truncated {len(text) - limit} chars] ...\n" + text[-half:]
