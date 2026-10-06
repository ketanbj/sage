from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from sage.builders.base import BuildAdapter, BuildResult
from sage.domain import sha256_file
from sage.provenance import command_version


class CppCandidateBuilder(BuildAdapter):
    def build(self, source: Path, build_dir: Path) -> BuildResult:
        build_dir.mkdir(parents=True, exist_ok=True)
        files = ("driver.cpp", "tensor.hpp", "kernels.hpp")
        for filename in files:
            shutil.copy2(source.parent / filename, build_dir / filename)
        binary = build_dir / "einsums-cpp-candidate"
        flags = ["-std=c++20", "-O2", "-ffp-contract=off", "-Wall", "-Wextra", "-Werror"]
        command = ["clang++", *flags, str(build_dir / "driver.cpp"), "-o", str(binary)]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        log = build_dir / "build.log"
        log.write_text(f"$ {' '.join(command)}\n{completed.stdout}{completed.stderr}")
        success = completed.returncode == 0
        return BuildResult(
            "translated-cpp20",
            success,
            binary if success else None,
            command,
            log,
            {
                "compiler": command_version(["clang++", "--version"]),
                "flags": flags,
                "instrumentation": "none",
                "source_hashes": {name: sha256_file(build_dir / name) for name in files},
                "binary_sha256": sha256_file(binary) if success else None,
            },
        )
