from __future__ import annotations
from typing import Annotated
from pathlib import Path
import operator
from src.models.schemas import BugReport
from langgraph.graph import MessagesState
from typing_extensions import TypedDict


class AgentState(TypedDict):
    # input
    repo_path: Path

    # file management
    files_to_analyze: list[Path]          #overwrite
    files_analyzed: Annotated[list[Path], operator.add]   # extend
    files_failed: Annotated[list[Path], operator.add]     # extend

    # risultati
    reports: dict[str, BugReport]         # overwrite with manual merge

    # metadata
    total_bugs: int