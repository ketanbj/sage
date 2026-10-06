from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from sage.builders.base import BuildAdapter, BuildResult
from sage.domain import sha256_file
from sage.provenance import command_version


class RustCandidateBuilder(BuildAdapter):
    def __init__(self, binary_name: str = "sage-rust-candidate") -> None:
        self.binary_name = binary_name

    def build(self, source: Path, build_dir: Path) -> BuildResult:
        build_dir.mkdir(parents=True, exist_ok=True)
        copied = build_dir / "candidate.rs"
        shutil.copy2(source, copied)
        binary = build_dir / self.binary_name
        command = ["rustc", "--edition=2021", "-C", "opt-level=2", str(copied), "-o", str(binary)]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        log = build_dir / "build.log"
        log.write_text(
            f"$ {' '.join(command)}\n{completed.stdout}{completed.stderr}", encoding="utf-8"
        )
        success = completed.returncode == 0
        return BuildResult(
            "translated-rust",
            success,
            binary if success else None,
            command,
            log,
            {
                "compiler": command_version(["rustc", "--version"]),
                "flags": command[1:4],
                "instrumentation": "none",
                "source_sha256": sha256_file(copied),
                "binary_sha256": sha256_file(binary) if success else None,
            },
        )
