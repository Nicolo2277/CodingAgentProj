import json
from pathlib import Path
from src.models.schemas import BugReport
from src.logger import get_logger
from src.config import OUTPUT_DIR
logger = get_logger(__name__)

OUTPUT_PATH = Path(OUTPUT_DIR)

def save_file_report(repo_path: Path, file_path: Path, report: BugReport) -> None:
    relative = file_path.relative_to(repo_path)
    out_path = OUTPUT_PATH / repo_path.name / "files" / relative.with_suffix(".json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    logger.debug("Saved: %s", out_path)


def save_final_report(repo_path: Path, reports: dict[str, BugReport]) -> None:
    summary = {
        "repo": repo_path.name,
        "total_files": len(reports),
        "total_bugs": sum(len(r.bugs) for r in reports.values()),
        "files": {
            path: json.loads(report.model_dump_json())
            for path, report in reports.items()
        }
    }
    out_path = OUTPUT_PATH / repo_path.name / "report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    logger.info("Final repo saved — %d files, %d bugs ", summary["total_files"], summary["total_bugs"])