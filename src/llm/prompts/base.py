from __future__ import annotations
from abc import ABC, abstractmethod


class BasePrompt(ABC):
    SYSTEM: str = ""
    USER_TEMPLATE: str = ""

    @classmethod
    def build(cls, **kwargs) -> tuple[str, str]:
        return cls.SYSTEM, cls.USER_TEMPLATE.format(**kwargs)