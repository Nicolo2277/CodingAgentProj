from pathlib import Path
from src.agent.state import AgentState
from src.tools.file_scanner import scan_python_files
from src.tools.file_reader import read_python_file
from src.tools.output_writer import save_file_report
from src.llm.client import BaseLLMClient
from src.llm.tasks.find_bugs import find_bugs
from src.logger import get_logger

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