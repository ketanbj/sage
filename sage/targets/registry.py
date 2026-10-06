from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sage.targets.catalog import canonical_candidate_id


@dataclass(frozen=True)
class TargetPlugin:
    candidate_id: str
    adapter_class: str | None
    run_class: str | None
    demo_config: str | None


PLUGINS: dict[str, TargetPlugin] = {
    "gau2grid": TargetPlugin("gau2grid", None, None, None),
    "dkh": TargetPlugin("dkh", None, None, None),
    "gdma": TargetPlugin("gdma", None, None, None),
    "einsums": TargetPlugin(
        "einsums",
        "sage.targets.einsums:EinsumsTargetAdapter",
        "sage.einsums.library_runtime:create_run",
        "configs/einsums-library.yaml",
    ),
}


def get_plugin(candidate_id: str) -> TargetPlugin:
    canonical_id = canonical_candidate_id(candidate_id)
    try:
        return PLUGINS[canonical_id]
    except KeyError as exc:
        raise ValueError(f"target {candidate_id!r} has no registered SAGE plugin") from exc


def _load_symbol(reference: str) -> Any:
    module_name, symbol_name = reference.split(":", 1)
    return getattr(importlib.import_module(module_name), symbol_name)


def load_target_adapter(candidate_id: str) -> Any:
    plugin = get_plugin(candidate_id)
    if plugin.adapter_class is None:
        raise ValueError(f"target {candidate_id!r} has no implemented adapter")
    return _load_symbol(plugin.adapter_class)()


def load_run_class(candidate_id: str) -> Any:
    plugin = get_plugin(candidate_id)
    if plugin.run_class is None:
        raise ValueError(f"target {candidate_id!r} has no implemented runtime")
    return _load_symbol(plugin.run_class)


def demo_config_path(root: Path, candidate_id: str) -> Path:
    plugin = get_plugin(candidate_id)
    if plugin.demo_config is None:
        raise ValueError(f"target {candidate_id!r} has no platform-demo configuration")
    return root / plugin.demo_config
