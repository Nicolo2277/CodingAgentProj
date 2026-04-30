from pathlib import Path
from src.agent.state import AgentState
from src.models.schemas import RunResult
from src.tools.file_scanner import scan_python_files
from src.tools.file_reader import read_python_file
from src.tools.output_writer import save_file_report
from src.llm.client import BaseLLMClient
from src.llm.tasks.find_bugs import find_bugs
from src.logger import get_logger

import subprocess
import sys

_RUN_TIMEOUT_SEC = 15
_OUTPUT_TRUNCATE  = 2000  # chars — keep prompts lean

logger = get_logger(__name__)


def tool_list_files(state: AgentState) -> tuple[str, dict]:
    files = scan_python_files(state["repo_path"])
    if not files:
        return "No Python files found.", {}
    file_list = [str(f.relative_to(state["repo_path"])) for f in files]
    result = "\n".join(f"{f} ({Path(state['repo_path'] / f).stat().st_size} bytes)" for f in file_list)
    return result, {"available_files": file_list}  # ← store in state


def tool_analyze_file(state: AgentState, file_input: str, client: BaseLLMClient) -> tuple[str, dict]:
    file_path = state["repo_path"] / file_input.strip()

    if file_input in state.get("files_analyzed", []):
        return "File already analyzed, skipping.", {}

    try:
        code = read_python_file(file_path)
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
    except Exception as e:
        logger.error("Error analyzing %s: %s", file_input, e)
        return f"Error: {e}", {"files_failed": [file_input]}
    
    
def tool_run_file(state: AgentState, file_input: str) -> tuple[str, dict]:
    """Execute a Python file and capture its output.
 
    Uses the same interpreter that is running the agent (sys.executable) so no
    venv setup is needed.  stdout/stderr are truncated to keep the result
    readable when fed back into the prompt.
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
            cwd=str(state["repo_path"]),   # run from repo root so relative imports work
        )
        returncode = proc.returncode
        stdout     = proc.stdout
        stderr     = proc.stderr
 
    except subprocess.TimeoutExpired as e:
        timed_out  = True
        returncode = -1
        stdout     = (e.stdout or b"").decode("utf-8", errors="replace") if isinstance(e.stdout, bytes) else (e.stdout or "")
        stderr     = f"[TIMEOUT after {_RUN_TIMEOUT_SEC}s]"
        logger.warning("Timeout running %s", file_input)
 
    except Exception as e:
        logger.error("Unexpected error running %s: %s", file_input, e)
        return f"Error running file: {e}", {"files_failed": [file_input]}
 
    # Truncate to avoid bloating the prompt context
    stdout_t = _truncate(stdout) # type: ignore
    stderr_t = _truncate(stderr)
 
    run_result = RunResult(
        file=file_input,
        returncode=returncode,
        stdout=stdout_t,
        stderr=stderr_t,
        timed_out=timed_out,
    )
 
    updated_run_results = {**state.get("run_results", {}), file_input: run_result}
 
    # Human-readable summary for the action_history
    status = "TIMEOUT" if timed_out else ("OK" if returncode == 0 else f"EXIT {returncode}")
    summary_lines = [f"Run result [{status}]"]
    if stdout_t:
        summary_lines.append(f"stdout:\n{stdout_t}")
    if stderr_t:
        summary_lines.append(f"stderr:\n{stderr_t}")
    result_text = "\n".join(summary_lines)
 
    logger.info(
        "Run finished — %s | exit=%d | timed_out=%s | stdout=%d chars | stderr=%d chars",
        file_input, returncode, timed_out, len(stdout), len(stderr),
    )
 
    return result_text, {
        "files_run":   [file_input],
        "run_results": updated_run_results,
    }
 
 
def _truncate(text: str, limit: int = _OUTPUT_TRUNCATE) -> str:
    if len(text) <= limit:
        return text
    half = limit // 2
    return text[:half] + f"\n... [truncated {len(text) - limit} chars] ...\n" + text[-half:]