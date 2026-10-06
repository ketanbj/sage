from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from sage.config import Config


class TargetAdapter(ABC):
    @abstractmethod
    def prepare(self, config: Config, destination: Path) -> dict[str, str]:
        """Prepare pinned source without modifying its checkout in place."""
