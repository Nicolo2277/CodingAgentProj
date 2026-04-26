from pathlib import Path
from src.agent.state import AgentState
from src.llm.factory import get_client
from src.llm.tasks.find_bugs import find_bugs
from src.tools.file_scanner import scan_python_files
from src.tools.file_reader import read_python_file
from src.tools.output_writer import save_file_report
from src.logger import get_logger

logger = get_logger(__name__)
client = get_client()


def node_scan_repo(state: AgentState) -> dict:
    """Scan repo and populate the file list"""
    files = scan_python_files(state["repo_path"])
    logger.info("Found %d files to analyze", len(files))
    return {"files_to_analyze": files}


def node_analyze_file(state: AgentState) -> dict:
    """Take the first file from the list and analyze it"""
    files = list(state["files_to_analyze"])
    file_path = files.pop(0)

    logger.info(
        "[%d remaining] Analysis: %s",
        len(files),
        file_path.name,
    )

    try:
        code = read_python_file(file_path)
        report = find_bugs(code, client)
        save_file_report(state["repo_path"], file_path, report)

        updated_reports = {**state.get("reports", {}), str(file_path): report}

        return {
            "files_to_analyze": files,
            "files_analyzed": [file_path],
            "reports": updated_reports,
            "total_bugs": state.get("total_bugs", 0) + len(report.bugs),
        }

    except Exception as e:
        logger.error("Error on %s: %s", file_path.name, e)
        return {
            "files_to_analyze": files,
            "files_failed": [file_path],
        }


def node_save_results(state: AgentState) -> dict:
    """Save final report"""
    from src.tools.output_writer import save_final_report
    save_final_report(state["repo_path"], state.get("reports", {}))
    logger.info(
        "Completed — %d analyzed files, %d bugs found",
        len(state.get("files_analyzed", [])),
        state.get("total_bugs", 0),
    )
    return {}