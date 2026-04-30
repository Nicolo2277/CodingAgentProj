from __future__ import annotations
from typing import Annotated
from pathlib import Path
import operator
from src.models.schemas import BugReport, RunResult
from langgraph.graph import MessagesState
from typing_extensions import TypedDict

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
    files_analyzed: Annotated[list[Path], operator.add]   # extend
    files_failed: Annotated[list[Path], operator.add]     # extend
    files_run: Annotated[list[str], operator.add]
    
    # ReAct
    action_history: Annotated[list[ActionRecord], operator.add]
    current_step:   int
    max_steps:      int
    finished:       bool

    # results
    reports: dict[str, BugReport]         # overwrite with manual merge
    run_results: dict[str, RunResult]

    # metadata
    total_bugs: int
    summary: str
    
    _pending_action: dict  # transient, used to pass action between think→act