from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from sage.domain import canonical_json, sha256_bytes

CONFIG_SCHEMA_VERSIONS = {"1.0", "1.1"}


@dataclass(frozen=True)
class TargetConfig:
    name: str
    upstream_url: str
    upstream_commit: str


@dataclass(frozen=True)
class SymSanConfig:
    upstream_url: str
    upstream_commit: str
    image: str
    enabled: bool
    trace_only: bool
    timeout_seconds: int
    max_tasks: int
    max_memory_mb: int
    max_output_bytes: int
    max_corpus: int
    trace_bounds: bool = True
    max_tasks_per_seed: int = 0


@dataclass(frozen=True)
class TestsConfig:
    seed: int
    random_cases: int
    max_points: int
    max_primitives: int
    max_abs_coordinate: float


@dataclass(frozen=True)
class EquivalenceConfig:
    policy_version: str
    atol: float
    rtol: float
    signed_zero_equal: bool


@dataclass(frozen=True)
class ExecutionConfig:
    timeout_seconds: int
    max_memory_mb: int


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    prompt_version: str
    timeout_seconds: int
    max_retries: int
    target_language: str = "rust"


@dataclass(frozen=True)
class Config:
    schema_version: str
    target: TargetConfig | None
    symsan: SymSanConfig
    tests: TestsConfig
    equivalence: EquivalenceConfig
    execution: ExecutionConfig
    provider: ProviderConfig
    runs_dir: str

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    @property
    def sha256(self) -> str:
        return sha256_bytes(canonical_json(self.to_dict()).encode())


def load_config(path: Path) -> Config:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_version") not in CONFIG_SCHEMA_VERSIONS:
        raise ValueError(f"config must use schema_version in {sorted(CONFIG_SCHEMA_VERSIONS)}")
    target_raw = raw.get("target")
    if target_raw is not None and not isinstance(target_raw, dict):
        raise ValueError("config target must be an object or null")
    if isinstance(target_raw, dict):
        target_raw = dict(target_raw)
        # Older resolved Einsums records included unused empty domain fields.
        for field_name in ("angular_momenta", "derivatives", "representations", "cartesian_order"):
            if target_raw.pop(field_name, None) not in (None, [], ""):
                raise ValueError("target configuration contains unsupported legacy domain fields")
    config = Config(
        schema_version=raw["schema_version"],
        target=TargetConfig(**target_raw) if target_raw is not None else None,
        symsan=SymSanConfig(**raw["symsan"]),
        tests=TestsConfig(**raw["tests"]),
        equivalence=EquivalenceConfig(**raw["equivalence"]),
        execution=ExecutionConfig(**raw["execution"]),
        provider=ProviderConfig(**raw["provider"]),
        runs_dir=raw["runs_dir"],
    )
    if config.provider.target_language not in ("rust", "cpp20"):
        raise ValueError("provider.target_language must be rust or cpp20")
    if config.provider.target_language == "cpp20" and (
        config.target is None or config.target.name != "einsums"
    ):
        raise ValueError("modern C++ currently requires the Einsums target")
    if not 1 <= config.tests.max_points <= 64 or not 1 <= config.tests.max_primitives <= 8:
        raise ValueError("MVP native-runner bounds are max_points<=64 and max_primitives<=8")
    if not 0 < config.tests.max_abs_coordinate <= 100.0:
        raise ValueError("MVP max_abs_coordinate must be in (0, 100]")
    return config


def dump_config(config: Config, path: Path) -> None:
    path.write_text(yaml.safe_dump(config.to_dict(), sort_keys=True), encoding="utf-8")
