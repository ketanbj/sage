from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class TestGenerator(ABC):
    @abstractmethod
    def generate(self) -> list[Any]:
        """Return cases parsed by the selected target's decoder."""
