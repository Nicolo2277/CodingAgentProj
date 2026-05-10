from __future__ import annotations
import operator
from typing import Annotated
from pathlib import Path
import operator
from src.models.schemas import BugReport, RunResult, Plan, VerifiedBugReport, FilePerformance
from typing_extensions import TypedDict, NotRequired

class ActionRecord(TypedDict):
    thought: str
    action: str
    action_input: str
    result: str
    
class AgentState(TypedDict):
    # input
    repo_path: Path

    # file management
    available_files: list[str]
    files_analyzed: Annotated[list[str], operator.add]   # extend
    files_failed: Annotated[list[str], operator.add]     # extend
    files_run: Annotated[list[str], operator.add]
    files_verified: Annotated[list[str], operator.add]
    # ReAct
    action_history: Annotated[list[ActionRecord], operator.add]
    current_step:   int
    max_steps:      int
    finished:       bool
    
    # Planner
    plan: NotRequired[Plan]

    # results
    reports: dict[str, BugReport]         # overwrite with manual merge
    run_results: dict[str, RunResult]
    verified_reports: dict[str, VerifiedBugReport]

    performance: dict[str, FilePerformance]
    
    # metadata
    total_bugs: int
    summary: str
    confirmed_bugs: int
    
