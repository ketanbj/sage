"""Full CPU/Python C++20 candidate with the conservative whole-library gate."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from sage.builders.base import BuildResult
from sage.domain import ExecutionResult, Outcome, sha256_file
from sage.einsums.domain import TensorCase
from sage.einsums.inventory import inventory
from sage.einsums.library_runtime import EinsumsLibraryRun
from sage.einsums.runtime import EinsumsRun
from sage.provenance import write_json
from sage.targets.einsums import EINSUMS_COMMIT, EinsumsTargetAdapter


class EinsumsCppLibraryRun(EinsumsLibraryRun):
    CANDIDATE_NAME = "einsums-cpp20-library"
    CANDIDATE_BUILD_KEY = "cpp_candidate"
    CANDIDATE_LABEL = "cpp20"
    LIMITATIONS = [
        "Independent C++20 CPU/Python implementation; HIP/GPU excluded by user scope.",
        "90 CPU exports and 16 helpers record implementation, not universal equivalence.",
        "The campaign probes 23 operations; broader Python API/dtype replay is separate.",
        "SymSan instruments input decoding only; computation paths execute natively.",
        "Generated inputs count as campaign evidence; bootstrap seeds are excluded.",
        "Public wrappers and new kernels have native tests, not formal proof. Existing "
        "copy/transpose proof remains bounded and applies to the unchanged scalar kernels.",
        "Exact C++ template overload/ABI, upstream dispatch, SIMD, threading, and downstream "
        "compatibility remain unverified. Whole-library completion stays conservative.",
    ]

    def __init__(self, config: Any, root: Path, **kwargs: Any) -> None:
        if (kwargs.get("provider_name") or config.provider.name) != "offline":
            raise ValueError("modern C++ uses the checked-in independent offline translation")
        super().__init__(config, root, **kwargs)

    def translate(self) -> Path:
        destination = self.root / ".sage/upstreams/einsums" / EINSUMS_COMMIT
        EinsumsTargetAdapter().prepare(self.config, destination)
        checkout = destination / "checkout"
        self.source_inventory = inventory(checkout)
        write_json(self.run_dir / "source/inventory.json", self.source_inventory)
        shutil.copytree(
            checkout, self.run_dir / "source/upstream", ignore=shutil.ignore_patterns(".git")
        )
        shutil.copy2(checkout / "LICENSE.txt", self.run_dir / "source/EINSUMS-LICENSE.txt")
        candidate = self.run_dir / "translation/einsums-cpp"
        shutil.copytree(
            self.root / "ports/einsums-cpp",
            candidate,
            ignore=shutil.ignore_patterns("build", "build-*", "dist", "__pycache__", "_native"),
        )
        metadata = {
            "scope": "cpu-python-library",
            "implementation": "independent checked-in C++20 backend; no model call",
            "complete": False,
            "source_commit": EINSUMS_COMMIT,
            "file_hashes": {
                str(p.relative_to(candidate)): sha256_file(p)
                for p in candidate.rglob("*")
                if p.is_file()
            },
            "api_surface": json.loads((candidate / "api-surface.json").read_text()),
        }
        self.manifest.translation_provider = {"name": "offline", "metadata": metadata}
        write_json(self.run_dir / "translation/metadata.json", self.manifest.translation_provider)
        self._save()
        return candidate

    def _build_candidate(self, candidate: Path) -> BuildResult:
        build = self.run_dir / "builds/cpp20"
        build.mkdir(exist_ok=True)
        configure = [
            "cmake",
            "-S",
            str(candidate),
            "-B",
            str(build),
            "-DCMAKE_BUILD_TYPE=Release",
            "-DBUILD_TESTING=OFF",
        ]
        command = ["cmake", "--build", str(build), "-j", "2"]
        log = build / "build.log"
        success = self._command(configure, build / "configure.log") and self._command(command, log)
        binary = build / "einsums-cpp-library-candidate"
        self.python_library = build / (
            "libsage_einsums_cpp.dylib" if sys.platform == "darwin" else "libsage_einsums_cpp.so"
        )
        success = success and binary.is_file() and self.python_library.is_file()
        return BuildResult(
            "einsums-cpp20-library",
            success,
            binary if success else None,
            command,
            log,
            {
                "configure_command": configure,
                "binary_sha256": sha256_file(binary) if success else None,
                "python_library": str(self.python_library),
                "library_sha256": sha256_file(self.python_library) if success else None,
            },
        )

    def _execute(self, case: TensorCase, input_path: Path) -> Any:
        executions, comparison = EinsumsRun._execute(self, case, input_path)
        runner = self.run_dir / "translation/einsums-cpp/python/run_case.py"
        try:
            completed = subprocess.run(
                [sys.executable, str(runner), str(input_path)],
                env={**os.environ, "EINSUMS_CPP_LIBRARY": str(self.python_library)},
                capture_output=True,
                text=True,
                timeout=self.config.execution.timeout_seconds,
                check=False,
            )
            output = json.loads(completed.stdout) if completed.returncode == 0 else None
            result = ExecutionResult(
                "1.0",
                "python-cpp20-api",
                case.case_id,
                completed.returncode,
                0,
                False,
                completed.stdout,
                completed.stderr,
                output,
                {"python_entrypoint": "CPU compatibility package"},
            )
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            result = ExecutionResult(
                "1.0",
                "python-cpp20-api",
                case.case_id,
                70,
                0,
                isinstance(exc, subprocess.TimeoutExpired),
                "",
                str(exc),
                None,
                {},
            )
        executions.append(result)
        if comparison.outcome == Outcome.PASS:
            comparison = self.policy.compare(case, executions[0], result)
        return executions, comparison
