from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

import yaml


class CandidateState(StrEnum):
    PROPOSED = "PROPOSED"
    UNDER_ASSESSMENT = "UNDER_ASSESSMENT"
    FEASIBLE = "FEASIBLE"
    SELECTED = "SELECTED"
    DEFERRED = "DEFERRED"
    PILOT_COMPLETE = "PILOT_COMPLETE"


ASSESSMENT_FIELDS = (
    "scientific_value",
    "proposed_translation_unit",
    "languages",
    "build_complexity",
    "tests",
    "reference_implementations",
    "numerical_equivalence_requirements",
    "symsan_compatibility",
    "developer_availability",
    "risks",
    "evidence",
    "confidence",
    "open_pi_questions",
)

CANDIDATE_ALIASES = {
    "psi4-module": "einsums",
}


def canonical_candidate_id(candidate_id: str) -> str:
    """Resolve retired candidate placeholders without duplicating catalog records."""
    return CANDIDATE_ALIASES.get(candidate_id, candidate_id)


@dataclass(frozen=True)
class CandidateAssessment:
    scientific_value: str | None
    proposed_translation_unit: str | None
    languages: list[str]
    build_complexity: str | None
    tests: list[str]
    reference_implementations: list[str]
    numerical_equivalence_requirements: list[str]
    symsan_compatibility: str | None
    developer_availability: list[str]
    risks: list[str]
    evidence: list[str]
    confidence: str
    open_pi_questions: list[str]


@dataclass(frozen=True)
class TargetCandidate:
    schema_version: str
    candidate_id: str
    display_name: str
    description: str
    state: CandidateState
    assessment: CandidateAssessment

    def to_dict(self) -> dict[str, Any]:
        result = dataclasses.asdict(self)
        result["state"] = self.state.value
        return result


@dataclass(frozen=True)
class TargetRecommendation:
    """A reviewable proposal, intentionally distinct from candidate and approval records."""

    schema_version: str
    status: str
    recommendation_id: str
    candidate_id: str
    rationale: str
    evidence: list[str]
    authored_by: str


def load_candidate(path: Path) -> TargetCandidate:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_version") != "1.0":
        raise ValueError(f"candidate {path} must use schema_version 1.0")
    assessment = raw.get("assessment")
    if not isinstance(assessment, dict):
        raise ValueError(f"candidate {path} has no assessment")
    missing = [field for field in ASSESSMENT_FIELDS if field not in assessment]
    if missing:
        raise ValueError(f"candidate {path} assessment missing: {', '.join(missing)}")
    return TargetCandidate(
        schema_version="1.0",
        candidate_id=str(raw["candidate_id"]),
        display_name=str(raw["display_name"]),
        description=str(raw["description"]),
        state=CandidateState(str(raw["state"])),
        assessment=CandidateAssessment(**assessment),
    )


class CandidateCatalog:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def list(self, *, include_template: bool = True) -> list[TargetCandidate]:
        candidates = [load_candidate(path) for path in sorted(self.directory.glob("*.yaml"))]
        if not include_template:
            candidates = [item for item in candidates if item.candidate_id != "template"]
        return candidates

    def get(self, candidate_id: str) -> TargetCandidate:
        canonical_id = canonical_candidate_id(candidate_id)
        path = self.directory / f"{canonical_id}.yaml"
        if not path.is_file():
            raise ValueError(f"unknown target candidate {candidate_id!r}")
        return load_candidate(path)
