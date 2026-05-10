from __future__ import annotations

import json
from pathlib import Path

from src.config import OUTPUT_DIR
from src.logger import get_logger
from src.models.schemas import BugReport, VerifiedBugReport

logger   = get_logger(__name__)
OUT_ROOT = Path(OUTPUT_DIR)


# Per-file helpers

def save_file_report(repo_path: Path, file_path: Path, report: BugReport) -> None:
    relative = file_path.relative_to(repo_path)
    out_path = OUT_ROOT / repo_path.name / "files" / relative.with_suffix(".json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    logger.debug("Saved static report: %s", out_path)


def save_verified_report(
    repo_path: Path,
    file_path: Path,
    verified: VerifiedBugReport,
) -> None:
    relative = file_path.relative_to(repo_path)
    out_path = (
        OUT_ROOT / repo_path.name / "verified" / relative.with_suffix(".json")
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(verified.model_dump_json(indent=2), encoding="utf-8")
    logger.debug("Saved verified report: %s", out_path)


# Final consolidated report 

def _build_file_entry(
    report: BugReport,
    verified: VerifiedBugReport | None,
) -> dict:
    """Merge static analysis + verification into a single, readable structure."""
    bugs = []
    for i, bug in enumerate(report.bugs):
        entry: dict = bug.model_dump()
        if verified is not None:
            v = verified.verdict_for(i)
            entry["verification"] = (
                {
                    "verdict":     v.verdict,
                    "explanation": v.explanation,
                    "test_output": v.test_output,
                }
                if v is not None
                else {"verdict": "not_run", "explanation": "", "test_output": ""}
            )
        bugs.append(entry)

    result: dict = {"summary": report.summary, "bugs": bugs}

    if verified is not None:
        result["verification_stats"] = {
            "confirmed":         verified.confirmed_count,
            "refuted":           verified.refuted_count,
            "inconclusive":      len(verified.verifications)
                                 - verified.confirmed_count
                                 - verified.refuted_count,
            "confirmation_rate": verified.confirmation_rate,
        }

    return result


def save_final_report(
    repo_path: Path,
    reports: dict[str, BugReport],
    verified_reports: dict[str, VerifiedBugReport] | None = None,
) -> None:
    verified_reports = verified_reports or {}

    total_bugs      = sum(len(r.bugs) for r in reports.values())
    total_confirmed = sum(
        v.confirmed_count for v in verified_reports.values()
    )

    summary = {
        "repo":            repo_path.name,
        "total_files":     len(reports),
        "total_bugs":      total_bugs,
        "total_confirmed": total_confirmed,
        "confirmation_rate": (
            round(total_confirmed / total_bugs, 2) if total_bugs else 0.0
        ),
        "files": {
            path: _build_file_entry(report, verified_reports.get(path))
            for path, report in reports.items()
        },
    }

    out_path = OUT_ROOT / repo_path.name / "report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    logger.info(
        "Final report saved — %d files | %d bugs | %d confirmed (%.0f%%)",
        summary["total_files"],
        total_bugs,
        total_confirmed,
        summary["confirmation_rate"] * 100,
    )