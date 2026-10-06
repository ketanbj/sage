from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class BuildResult:
    implementation: str
    success: bool
    binary: Path | None
    command: list[str]
    log_path: Path
    metadata: dict[str, Any]


class BuildAdapter(ABC):
    @abstractmethod
    def build(self, source: Path, build_dir: Path) -> BuildResult:
        """Build source in a run-specific directory."""
