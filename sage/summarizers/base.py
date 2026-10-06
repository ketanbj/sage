from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Summarizer(ABC):
    @abstractmethod
    def summarize(self, artifacts: dict[str, Any]) -> dict[str, Any]:
        """Return advisory text derived only from structured artifacts."""
