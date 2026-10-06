from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


class Outcome(StrEnum):
    PASS = "PASS"
    NUMERICAL_DIFFERENCE = "NUMERICAL_DIFFERENCE"
    STRUCTURAL_DIFFERENCE = "STRUCTURAL_DIFFERENCE"
    REFERENCE_DISAGREEMENT = "REFERENCE_DISAGREEMENT"
    CRASH = "CRASH"
    TIMEOUT = "TIMEOUT"
    BUILD_FAILURE = "BUILD_FAILURE"
    UNSUPPORTED = "UNSUPPORTED"
    INVALID_INPUT = "INVALID_INPUT"
    INFRASTRUCTURE_FAILURE = "INFRASTRUCTURE_FAILURE"
    NO_TEST_CASES = "NO_TEST_CASES"


@dataclass(frozen=True)
class ProjectTarget:
    schema_version: str
    name: str
    upstream_url: str
    upstream_commit: str
    source_language: str = "c"
    target_language: str = "rust"


@dataclass(frozen=True)
class TranslationUnit:
    schema_version: str
    unit_id: str
    source_path: str
    source_sha256: str
    symbols: list[str]


@dataclass(frozen=True)
class TranslationRequest:
    schema_version: str
    unit: TranslationUnit
    source_code: str
    prompt: str
    prompt_version: str


@dataclass(frozen=True)
class TranslationResult:
    schema_version: str
    provider: str
    code: str
    metadata: dict[str, Any]
    response_sha256: str


@dataclass(frozen=True)
class ExecutionResult:
    schema_version: str
    implementation: str
    case_id: str
    exit_code: int | None
    elapsed_seconds: float
    timed_out: bool
    stdout: str
    stderr: str
    outputs: dict[str, list[list[float]]] | None
    resource_use: dict[str, Any]


@dataclass(frozen=True)
class ComparisonResult:
    schema_version: str
    case_id: str
    outcome: Outcome
    pair_results: dict[str, bool]
    metrics: dict[str, Any]
    invariant_results: dict[str, bool]
    message: str = ""


@dataclass(frozen=True)
class Discrepancy:
    schema_version: str
    case_id: str
    outcome: Outcome
    comparison: ComparisonResult
    replay_confirmed: bool
    reproducer_path: str


@dataclass
class RunManifest:
    schema_version: str
    run_id: str
    started_at: str
    completed_at: str | None
    status: str
    commits: dict[str, str]
    config_sha256: str
    prompt_hashes: dict[str, str]
    translation_provider: dict[str, Any]
    tool_versions: dict[str, str]
    container_images: dict[str, str]
    random_seeds: list[int]
    equivalence_policy_version: str
    test_counts_by_origin: dict[str, int] = field(default_factory=dict)
    outcome_counts: dict[str, int] = field(default_factory=dict)
    known_limitations: list[str] = field(default_factory=list)
    concolic_outcome: dict[str, Any] = field(default_factory=dict)
    build_records: dict[str, Any] = field(default_factory=dict)
    target_candidate: str | None = None
    run_mode: str = "platform-demo"
    selection_decision: dict[str, Any] | None = None


@dataclass(frozen=True)
class ProvenanceRecord:
    schema_version: str
    timestamp: str
    event: str
    attributes: dict[str, Any]


def jsonable(value: Any) -> Any:
    if dataclasses.is_dataclass(value):
        return {
            field.name: jsonable(getattr(value, field.name)) for field in dataclasses.fields(value)
        }
    if isinstance(value, StrEnum):
        return value.value
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(jsonable(value), sort_keys=True, separators=(",", ":"), allow_nan=False)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
