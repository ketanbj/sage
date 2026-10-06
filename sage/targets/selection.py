from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from sage.domain import canonical_json, sha256_bytes
from sage.targets.catalog import CandidateCatalog


@dataclass(frozen=True)
class SelectionDecision:
    schema_version: str
    decision_kind: str
    decision_id: str
    target: str
    status: str
    approved_by: str
    approved_at: str
    rationale: str
    evidence: list[str]

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @property
    def sha256(self) -> str:
        return sha256_bytes(canonical_json(self.to_dict()).encode())


def load_selection_decision(path: Path, *, expected_target: str | None = None) -> SelectionDecision:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("selection decision must be a YAML object")
    required = {
        "schema_version",
        "decision_kind",
        "decision_id",
        "target",
        "status",
        "approved_by",
        "approved_at",
        "rationale",
        "evidence",
    }
    missing = sorted(required - raw.keys())
    if missing:
        raise ValueError(f"selection decision missing: {', '.join(missing)}")
    decision = SelectionDecision(**{key: raw[key] for key in required})
    if decision.schema_version != "1.0" or decision.decision_kind != "target-selection":
        raise ValueError("selection decision must use target-selection schema 1.0")
    if decision.status != "APPROVED":
        raise ValueError("scientific-pilot selection decision status must be APPROVED")
    if not decision.approved_by.strip() or not decision.approved_at.strip():
        raise ValueError("selection decision requires recorded human approver and approval time")
    if expected_target is not None and decision.target != expected_target:
        raise ValueError(f"selection decision targets {decision.target!r}, not {expected_target!r}")
    return decision


def record_selection(
    decision_path: Path, state_path: Path, catalog: CandidateCatalog, target: str
) -> SelectionDecision:
    catalog.get(target)
    decision = load_selection_decision(decision_path, expected_target=target)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "schema_version": "1.0",
        "selected_target": target,
        "decision_path": str(decision_path.resolve()),
        "decision_sha256": decision.sha256,
        "decision": decision.to_dict(),
    }
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return decision


def read_selection_status(state_path: Path) -> dict[str, Any]:
    if not state_path.is_file():
        return {"schema_version": "1.0", "selected_target": None, "status": "NO_SELECTION"}
    raw = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_version") != "1.0":
        raise ValueError("stored selection state is incompatible")
    return raw
