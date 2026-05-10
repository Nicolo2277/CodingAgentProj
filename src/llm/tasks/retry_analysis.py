from __future__ import annotations

import json

from src.llm.client import BaseLLMClient
from src.llm.prompts.retry_analysis import RetryAnalysisPrompt
from src.models.schemas import BugReport, VerifiedBugReport
from src.logger import get_logger

logger = get_logger(__name__)


def _build_verification_json(verified: VerifiedBugReport) -> str:
    """Compact, LLM-readable summary of what the verifier found."""
    rows = []
    for v in verified.verifications:
        bug = verified.original_report.bugs[v.bug_index]
        rows.append({
            "bug_index":   v.bug_index,
            "line":        bug.line,
            "description": bug.description,
            "verdict":     v.verdict,
            "explanation": v.explanation,
        })
    return json.dumps(rows, indent=2)


def retry_analysis(
    code: str,
    previous_report: BugReport,
    verified: VerifiedBugReport,
    client: BaseLLMClient,
) -> BugReport:
    """
    Re-run bug analysis using verifier feedback as additional context.
    Returns an improved BugReport (may have fewer, more, or the same bugs).
    """
    previous_bugs_json = json.dumps(
        [{"index": i, **b.model_dump()} for i, b in enumerate(previous_report.bugs)],
        indent=2,
    )
    verification_json = _build_verification_json(verified)

    system, user = RetryAnalysisPrompt.build(
        code=code,
        previous_bugs_json=previous_bugs_json,
        verification_json=verification_json,
    )

    logger.info(
        "Retry analysis — previous: %d bugs (rate %.0f%%) → asking for improved report",
        len(previous_report.bugs),
        verified.confirmation_rate * 100,
    )

    response = client.complete(user, system=system, json_mode=True)
    data     = response.as_json()
    report   = BugReport(**data)

    logger.info(
        "Retry complete — new report: %d bugs (%dms)",
        len(report.bugs), response.duration_ms,
    )
    return report

