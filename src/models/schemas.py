from typing import Literal
from pydantic import BaseModel


class Bug(BaseModel):
    line: int
    description: str
    severity: Literal["low", "medium", "high"]
    fix: str


class BugReport(BaseModel):
    bugs: list[Bug]
    summary: str


class AgentAction(BaseModel):
    thought:      str
    action:       Literal["list_files", "analyze_file", "finish"]
    action_input: str
    reasoning:    str