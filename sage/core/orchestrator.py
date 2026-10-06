from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from sage.config import Config
from sage.targets.registry import load_run_class
from sage.targets.selection import SelectionDecision, load_selection_decision

RUN_MODES = {"platform-demo", "scientific-pilot"}


class SageRun:
    """Target-independent facade that dispatches to a registered target runtime."""

    def __init__(
        self,
        config: Config,
        root: Path,
        *,
        target_name: str | None = None,
        mode: str = "platform-demo",
        selection_path: Path | None = None,
        provider_name: str | None = None,
        seed: int | None = None,
    ) -> None:
        if mode not in RUN_MODES:
            raise ValueError(f"unknown run mode {mode!r}; expected one of {sorted(RUN_MODES)}")
        configured_target = config.target.name if config.target is not None else None
        self.target_name = target_name or configured_target
        if self.target_name is None:
            raise ValueError("no target selected for this run; pass --target <candidate>")
        if configured_target is not None and configured_target != self.target_name:
            raise ValueError(
                f"configuration targets {configured_target!r}, not {self.target_name!r}"
            )
        self.mode = mode
        self.selection: SelectionDecision | None = None
        if mode == "scientific-pilot":
            if selection_path is None:
                raise ValueError(
                    "scientific-pilot mode requires --selection with an approved human decision"
                )
            self.selection = load_selection_decision(
                selection_path.resolve(), expected_target=self.target_name
            )
        run_class = load_run_class(self.target_name)
        self._delegate: Any = run_class(
            config,
            root,
            provider_name=provider_name,
            seed=seed,
            run_mode=mode,
            selection=self.selection,
        )

    @property
    def run_dir(self) -> Path:
        return cast(Path, self._delegate.run_dir)

    def translate(self) -> Path:
        return cast(Path, self._delegate.translate())

    def generate_tests(self, symsan_binary: Path | None = None) -> Any:
        return self._delegate.generate_tests(symsan_binary)

    def run(self) -> Path:
        return cast(Path, self._delegate.run())

    def __getattr__(self, name: str) -> Any:
        return getattr(self._delegate, name)
