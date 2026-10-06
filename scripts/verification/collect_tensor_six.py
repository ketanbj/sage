"""Collect current six-operation evidence, rejecting incomplete or stale inputs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from sage.verification.einsums import digest  # noqa: E402


def portable(value: Any) -> Any:
    """Publish root-relative paths while retaining the immutable raw run separately."""
    if isinstance(value, str):
        return value.replace(str(ROOT) + "/", "")
    if isinstance(value, list):
        return [portable(item) for item in value]
    if isinstance(value, dict):
        return {key: portable(item) for key, item in value.items()}
    return value


def collect(rust: Path, cpp: Path, output: Path) -> None:
    results = {}
    for language, bundle in (("rust", rust), ("cpp20", cpp)):
        manifest = json.loads((bundle / "manifest.json").read_text())
        replay = json.loads((bundle / "api-replay.json").read_text())
        assert manifest["status"] == "BOUNDED_TENSOR_API_PROVED"
        assert len(manifest["obligations"]) == 144
        assert len(manifest["negative_controls"]) == 6
        assert all(v["detected"] for v in manifest["negative_controls"].values())
        assert manifest["native_fault_replay"]["status"] == "PASS"
        assert replay["status"] == "PASS" and replay["python_checks"] == 864
        assert replay["json_ffi_checks"] == 864
        assert digest(Path(replay["library"]).read_bytes()) == replay["library_sha256"]
        for filename, sha in manifest["public_api_bindings"].items():
            assert digest((ROOT / filename).read_bytes()) == sha, filename
        candidate = (
            "ports/einsums-rs/src/tensor.rs"
            if language == "rust"
            else "ports/einsums-cpp/tensor.hpp"
        )
        key = "tensor_source.rs" if language == "rust" else "tensor.hpp"
        assert digest((ROOT / candidate).read_bytes()) == manifest["source_hashes"][key]
        if language == "cpp20":
            for key in ("public_method_certificate", "expression_lowering_certificate"):
                assert manifest[key]["identical_optimized_ir"] and manifest[key]["entries"] == 144
            assert (
                digest((ROOT / "ports/einsums-cpp/kernels.hpp").read_bytes())
                == manifest["source_hashes"]["kernels.hpp"]
            )
        output.mkdir(parents=True, exist_ok=True)
        destination = output / language
        destination.mkdir(exist_ok=True)
        for filename in (
            "manifest.json",
            "report.md",
            "api-replay.json",
            "native-fault-replay.json",
        ):
            source = (bundle / filename).read_text()
            published = (
                json.dumps(portable(json.loads(source)), indent=2) + "\n"
                if filename.endswith(".json")
                else portable(source)
            )
            (destination / filename).write_text(published)
        results[language] = {
            "status": manifest["status"],
            "proof_bundle": portable(str(bundle.resolve())),
            "manifest_sha256": digest((bundle / "manifest.json").read_bytes()),
            "published_manifest_sha256": digest((destination / "manifest.json").read_bytes()),
            "method_obligations": 144,
            "fault_controls": 6,
            "native_fault_replays": 6,
            "python_exact_bit_checks": 864,
            "json_ffi_exact_bit_checks": 864,
        }
    summary = {
        "status": "BOUNDED_SIX_OPERATIONS_PROVED_AND_CONNECTED",
        "publication": "Root-relative summary paths; raw manifests remain unchanged under runs/",
        "languages": results,
        "operations": ["copy", "add", "multiply", "transpose", "matmul", "scale"],
        "domain": "Owned rank-two float64, dimensions 1..4, signed-byte values/scalar /8",
        "proof_kind": "Ordered expressions with trusted compiler, arithmetic and memory models",
        "api_connection": "Production routing with native replay; adapters outside model checking",
        "exclusions": [
            "General sizes/dtypes/Array fallback",
            "Upstream BLAS and full public dispatch",
            "JSON/FFI/Python lifetime and error semantics",
            "Whole-library equivalence",
        ],
    }
    (output / "verification.json").write_text(json.dumps(summary, indent=2))
    (output / "report.md").write_text("""# Current six-operation proof evidence

Copy, add, elementwise multiply, transpose, matrix multiplication and scale have
completed bounded production Tensor proofs in **both Rust and C++20**. Eligible
public CPU/Python requests call those methods.

| Evidence | Rust | C++20 |
|---|---:|---:|
| Public-method obligations | 144 /144 | 144 /144 |
| Deliberate source faults detected | 6 /6 | 6 /6 |
| Native original/mutant replays | 6 /6 | 6 /6 |
| Python exact-bit adapter checks | 864 | 864 |
| JSON/FFI exact-bit adapter checks | 864 | 864 |
| Compiler identity entries | Direct Kani source import | 144 binary64 +144 expression |

The proof preserves ordered expressions, including every input index and every
matrix accumulation step. Interpreting those expressions as binary64 establishes
the conditional functional result. The trusted base includes arithmetic semantics,
parametricity, the compilers/verifiers and standard-library memory models. This is
a compositional proof rather than a direct bit-blast of all floating-point matrix
calculations. Native adapter checks are separate empirical evidence.

**Domain:** owned rank-two float64 tensors, dimensions 1–4, independent valid input
storage, signed-byte values divided by eight, and successful allocation. Scale
uses the same scalar domain. The bridges preserve general-library fallbacks.

The refreshed upstream HPTT scalar copy/transpose proofs also pass against the
current code. Add/multiply/matmul/scale prove the ports against the common operation
contract. The external upstream BLAS implementation and complete Einsums public
call chains remain outside the theorem, as do general sizes/dtypes and full
JSON/FFI/Python parsing, lifetime and error behavior.

At this proof milestone, project checks passed **139 tests with 5 backend-specific
skips**. Rust native checks and C++ CTest contracts passed, along with Ruff and mypy.
These historical counts predate the removal of the retired demonstration tests.

See [Rust evidence](rust/manifest.json), [C++ evidence](cpp20/manifest.json) and the
[methodology and rerun instructions](../../docs/tensor-six-proof.md). The manifests
record raw immutable proof-bundle locations and any reused-check provenance.
Published summary paths are repository-relative. The combined summary retains both
original and published manifest hashes. Full raw solver bundles are intentionally
outside Git and must be regenerated or distributed separately.
`verification.json` provides the combined current state. Failed exploratory runs
remain separate audit records under `runs/`.
""")
    print(output.resolve())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rust", required=True, type=Path)
    parser.add_argument("--cpp", required=True, type=Path)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/tensor-six")
    args = parser.parse_args()
    collect(args.rust, args.cpp, args.output)
