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