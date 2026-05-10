from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, computed_field


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
    
    
class TestCase(BaseModel):
    bug_index:   int
    description: str
    test_code:   str  # standalone runnable Python script
 
 
class VerificationResult(BaseModel):
    bug_index:   int
    verdict:     Literal["confirmed", "refuted", "inconclusive", "generation_error"]
    test_output: str
    explanation: str
 
 
class VerifiedBugReport(BaseModel):
    original_report: BugReport
    test_cases:      list[TestCase]
    verifications:   list[VerificationResult]
 
    @computed_field  # type: ignore[misc]
    @property
    def confirmed_count(self) -> int:
        return sum(1 for v in self.verifications if v.verdict == "confirmed")
 
    @computed_field  # type: ignore[misc]
    @property
    def refuted_count(self) -> int:
        return sum(1 for v in self.verifications if v.verdict == "refuted")
 
    @computed_field  # type: ignore[misc]
    @property
    def confirmation_rate(self) -> float:
        total = len(self.verifications)
        return round(self.confirmed_count / total, 2) if total else 0.0
 
    def verdict_for(self, bug_index: int) -> VerificationResult | None:
        """Look up the verification result for a specific bug index."""
        return next((v for v in self.verifications if v.bug_index == bug_index), None)
