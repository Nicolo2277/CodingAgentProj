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
    action:       Literal["list_files", "analyze_file", "run_file", "finish"]
    action_input: str
    reasoning:    str
    

class RunResult(BaseModel):
    file: str
    returncode: int
    stdout: str
    stderr: str
    timed_out: bool = False
    
    
class PlanStep(BaseModel):
    file:     str
    reason:   str
    priority: Literal["high", "medium", "low"]


class Plan(BaseModel):
    reasoning: str
    steps:     list[PlanStep]

    @property
    def ordered_files(self) -> list[str]:
        """Files in execution order (high → medium → low)."""
        rank = {"high": 0, "medium": 1, "low": 2}
        return [s.file for s in sorted(self.steps, key=lambda s: rank[s.priority])]