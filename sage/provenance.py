from __future__ import annotations

import json
import os
import platform
import subprocess
import sys
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from sage.domain import ProvenanceRecord, canonical_json, jsonable


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def command_version(command: list[str]) -> str:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=5, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"unavailable: {type(exc).__name__}"
    output = (result.stdout or result.stderr).strip().splitlines()
    return output[0] if output else f"exit {result.returncode}"


def environment_record() -> dict[str, Any]:
    dependencies = {}
    for package in ("sage-equivalence", "numpy", "PyYAML", "typer"):
        try:
            dependencies[package] = version(package)
        except PackageNotFoundError:
            dependencies[package] = "unavailable"
    return {
        "schema_version": "1.0",
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "locale": os.environ.get("LC_ALL") or os.environ.get("LANG", "unknown"),
        "dependencies": dependencies,
        "tools": {
            "cc": command_version(["cc", "--version"]),
            "rustc": command_version(["rustc", "--version"]),
            "cargo": command_version(["cargo", "--version"]),
            "docker": command_version(["docker", "--version"]),
        },
    }


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jsonable(value), indent=2, sort_keys=True) + "\n", encoding="utf-8")


def append_jsonl(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(canonical_json(value) + "\n")


def record_event(path: Path, event: str, attributes: dict[str, Any]) -> None:
    append_jsonl(path, ProvenanceRecord("1.0", utc_now(), event, attributes))
