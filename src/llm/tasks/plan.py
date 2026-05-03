from pathlib import Path
from src.agent.state import AgentState
from src.llm.client import BaseLLMClient
from src.llm.prompts.planner import PlannerPrompt
from src.models.schemas import Plan
from src.tools.file_scanner import scan_python_files
from src.logger import get_logger

logger = get_logger(__name__)


def _build_file_list(repo_path: Path, relative_files: list[str]) -> str:
    lines = []
    for f in relative_files:
        size = (repo_path / f).stat().st_size
        lines.append(f"  {f} · {size} bytes")
    return "\n".join(lines)


def _sanitize_plan(plan: Plan, available_files: list[str]) -> Plan:
    """Drop any steps the LLM hallucinated (files not in the repo)."""
    valid = set(available_files)
    seen: set[str] = set()
    clean_steps = []

    for step in plan.steps:
        if step.file not in valid:
            logger.warning("Planner hallucinated file '%s' — skipping", step.file)
            continue
        if step.file in seen:
            logger.warning("Planner duplicated file '%s' — skipping", step.file)
            continue
        seen.add(step.file)
        clean_steps.append(step)

    # files the planner forgot → append as medium priority
    for f in available_files:
        if f not in seen:
            logger.warning("Planner missed file '%s' — appending as medium", f)
            from src.models.schemas import PlanStep
            clean_steps.append(PlanStep(file=f, reason="Not included in plan.", priority="medium"))

    return Plan(reasoning=plan.reasoning, steps=clean_steps)


def create_plan(state: AgentState, client: BaseLLMClient) -> tuple[Plan, list[str]]:
    files = scan_python_files(state["repo_path"])
    available_files = [str(f.relative_to(state["repo_path"])) for f in files]

    if not available_files:
        logger.warning("No Python files found — returning empty plan.")
        return Plan(reasoning="No files to analyze.", steps=[]), available_files

    file_list_str = _build_file_list(state["repo_path"], available_files)
    system, user = PlannerPrompt.build(
        repo_path=state["repo_path"],
        file_list=file_list_str,
    )

    logger.info("Planning analysis for %d files...", len(available_files))
    response = client.complete(user, system=system, json_mode=True)
    data = response.as_json()
    raw_plan = Plan(**data)

    plan = _sanitize_plan(raw_plan, available_files)

    logger.info("Plan ready — %d steps (reasoned in %dms)", len(plan.steps), response.duration_ms)
    for i, step in enumerate(plan.steps, 1):
        logger.debug("  [%d/%d] %-8s %s — %s", i, len(plan.steps), f"[{step.priority}]", step.file, step.reason)

    return plan, available_files