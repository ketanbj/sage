"""Independent C++20 candidate using the existing bounded comparison protocol."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from sage.builders.base import BuildResult
from sage.builders.cpp_candidate import CppCandidateBuilder
from sage.config import Config
from sage.domain import sha256_file
from sage.einsums.runtime import SOURCE_FILES, EinsumsRun
from sage.provenance import write_json
from sage.targets.einsums import EINSUMS_COMMIT, EinsumsTargetAdapter


class EinsumsCppRun(EinsumsRun):
    CANDIDATE_NAME = "einsums-cpp20"
    CANDIDATE_BUILD_KEY = "cpp_candidate"
    CANDIDATE_LABEL = "cpp20"
    FIXTURE_DIR = "fixtures/einsums-library"
    INSTRUMENTATION = "einsums-symsan-input-harness"
    LIMITATIONS = [
        "Independent C++20 implementation of six bounded rank-two CPU tensor operations.",
        "Contiguous binary64, dimensions 1..4, signed-byte values divided by eight.",
        "SymSan instruments only the input-contract harness; all Einsums kernels execute "
        "natively. These cases do not demonstrate library branch coverage.",
        "Only newly generated SymSan inputs count as campaign evidence; seeds are excluded.",
        "No whole-library/Python/GPU translation, arbitrary ranks/dtypes, views or aliasing.",
        "Sampled comparison is separate from the copy/transpose scalar-kernel proof. "
        "The C++20 wrapper, decoder and remaining operations have no formal proof.",
    ]

    def __init__(self, config: Config, root: Path, **kwargs: Any) -> None:
        if (kwargs.get("provider_name") or config.provider.name) != "offline":
            raise ValueError("modern C++ uses the checked-in independent offline translation")
        super().__init__(config, root, **kwargs)

    def translate(self) -> Path:
        destination = self.root / ".sage/upstreams/einsums" / EINSUMS_COMMIT
        EinsumsTargetAdapter().prepare(self.config, destination)
        checkout = destination / "checkout"
        source = self.run_dir / "source"
        snapshot = source / "upstream"
        shutil.copytree(checkout, snapshot, ignore=shutil.ignore_patterns(".git"))
        shutil.copy2(checkout / "LICENSE.txt", source / "EINSUMS-LICENSE.txt")
        shutil.copy2(self.root / "fixtures/einsums/driver.cpp", source / "driver.cpp")
        write_json(
            source / "hashes.json",
            {
                str(p.relative_to(source)): sha256_file(p)
                for p in snapshot.rglob("*")
                if p.is_file()
            },
        )
        candidate = self.run_dir / "translation/einsums-cpp"
        shutil.copytree(
            self.root / "ports/einsums-cpp",
            candidate,
            ignore=shutil.ignore_patterns("build", "build-*", "dist", "__pycache__", "_native"),
        )
        hashes = {p.name: sha256_file(p) for p in candidate.iterdir() if p.is_file()}
        metadata = {
            "target_language": "cpp20",
            "implementation": "checked-in independent translation; no model call",
            "scope": "bounded-cpu-tensors",
            "operations": list(self.OPERATIONS),
            "source_commit": EINSUMS_COMMIT,
            "source_contract_hashes": {path: sha256_file(snapshot / path) for path in SOURCE_FILES},
            "candidate_hashes": hashes,
            "source_mapping": {
                "copy/indexing": "Tensor.hpp -> tensor.hpp / copy_kernel",
                "add/multiply/scale": "Tensor.hpp operators -> tensor.hpp",
                "transpose": "Permute.hpp / HPTT scalar path -> transpose_kernel",
                "matmul": "TensorAlgebra.hpp einsum -> tensor.hpp::matmul",
            },
        }
        write_json(self.run_dir / "translation/metadata.json", metadata)
        self.manifest.translation_provider = {"name": "offline", "metadata": metadata}
        self._save()
        return candidate / "driver.cpp"

    def _build_reference(self) -> bool:
        shutil.copy2(
            self.root / "fixtures/einsums-cpp/input_harness.c",
            self.run_dir / "builds/input_harness.c",
        )
        return super()._build_reference()

    def _build_candidate(self, candidate: Path) -> BuildResult:
        return CppCandidateBuilder().build(candidate, self.run_dir / "builds/cpp20")
