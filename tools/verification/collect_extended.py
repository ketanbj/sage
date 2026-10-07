"""Publish compact source-bound extension evidence; reject stale or incomplete proofs."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def portable(value):
    if isinstance(value, str):
        return value.replace(str(ROOT) + "/", "")
    if isinstance(value, list):
        return [portable(item) for item in value]
    if isinstance(value, dict):
        return {key: portable(item) for key, item in value.items()}
    return value


def require(condition, message):
    if not condition:
        raise ValueError(message)


def proof(bundle, language):
    manifest = json.loads((bundle / "manifest.json").read_text())
    require(manifest["status"] == "BOUNDED_CONTRACTS_PROVED", "incomplete proof")
    require(manifest["target_language"] == language, "wrong language")
    require(len(set(manifest["obligations"])) == 69, "missing/duplicate obligations")
    require(
        len(manifest["negative_controls"]) == 5
        and all(c["detected"] for c in manifest["negative_controls"].values()),
        "failed mutation controls",
    )
    require(
        len(manifest["native_fault_replay"]) == 5
        and all(
            c["baseline_passed"] and c["mutant_failed"]
            for c in manifest["native_fault_replay"].values()
        ),
        "failed native witnesses",
    )
    for name, expected in manifest["public_api_bindings"].items():
        require(sha(ROOT / name) == expected, f"stale public binding: {name}")
    paths = (
        {
            "contract.rs": "ports/einsums-rs/src/proof_contract.rs",
            "tensor_source.rs": "ports/einsums-rs/src/tensor.rs",
        }
        if language == "rust"
        else {
            "proof_contract.hpp": "ports/einsums-cpp/api/proof_contract.hpp",
            "kernels.hpp": "ports/einsums-cpp/kernels.hpp",
        }
    )
    for name, source in paths.items():
        require(
            sha(ROOT / source) == manifest["source_hashes"][name] == sha(bundle / name),
            "stale production source",
        )
    require(
        sha(bundle / "proof_runner.py") == sha(ROOT / "sage/verification/extended.py"),
        "stale proof runner",
    )
    if language == "rust":
        require(
            manifest["checks"]["status"] == "PROVED" and len(manifest["checks"]["harnesses"]) == 69,
            "incomplete Kani result",
        )
    else:
        require(
            len(manifest["checks"]) == 69
            and all(c["status"] == "PROVED" for c in manifest["checks"]),
            "incomplete CBMC result",
        )
        require(
            manifest["compiler_certificate"]["identical_optimized_ir"],
            "failed compiler certificate",
        )
    return {
        "status": manifest["status"],
        "manifest_sha256": sha(bundle / "manifest.json"),
        "obligations": 69,
        "mutation_controls": manifest["negative_controls"],
        "native_mutation_witnesses": manifest["native_fault_replay"],
        "source_hashes": manifest["source_hashes"],
        "public_api_bindings": manifest["public_api_bindings"],
        "tools": manifest["tools"],
        "compiler_certificate": manifest.get("compiler_certificate"),
        "assumptions": manifest["assumptions"],
        "exclusions": manifest["exclusions"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rust", type=Path, required=True)
    parser.add_argument("--cpp", type=Path, required=True)
    parser.add_argument("--paths", type=Path, required=True)
    parser.add_argument("--backends", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts/pending-proofs")
    args = parser.parse_args()
    languages = {"rust": proof(args.rust, "rust"), "cpp20": proof(args.cpp, "cpp20")}
    paths = json.loads((args.paths / "manifest.json").read_text())
    replay = json.loads((args.paths / "api-replay.json").read_text())
    require(
        paths["status"] == "SAMPLED_LIBRARY_DECISIONS_PASS" and replay["status"] == "PASS",
        "incomplete path experiment",
    )
    require(
        paths["source_hashes"]["proof_contract.hpp"]
        == sha(ROOT / "ports/einsums-cpp/api/proof_contract.hpp"),
        "stale instrumented decisions",
    )
    require(
        paths["source_hashes"]["experiment.py"]
        == sha(ROOT / "tools/verification/explore_library_paths.py"),
        "stale path experiment",
    )
    require(
        replay["checker_sha256"] == sha(ROOT / "tools/verification/replay_library_paths.py"),
        "stale public path replay",
    )
    backends = json.loads((args.backends / "manifest.json").read_text())
    for source, expected in backends["port_source_hashes"].items():
        require(sha(ROOT / source) == expected, "stale backend port source")
    for language, relative in {
        "rust": "ports/einsums-rs/target/debug/libsage_einsums",
        "cpp20": "ports/einsums-cpp/build/libsage_einsums_cpp",
    }.items():
        import sys

        library = ROOT / (relative + (".dylib" if sys.platform == "darwin" else ".so"))
        require(
            sha(library)
            == replay["library_hashes"][language]
            == backends["library_hashes"][language],
            "stale native replay",
        )
    result = {
        "status": "BOUNDED_EXTENSIONS_WITH_OPEN_COMPATIBILITY_FINDINGS",
        "contract": "corrected-cpu-semantics-1",
        "languages": languages,
        "path_generation": paths,
        "path_api_replay": replay,
        "backend_contracts": backends,
        "backend_manifest_sha256": sha(args.backends / "manifest.json"),
        "whole_library_equivalence": False,
    }
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "verification.json").write_text(json.dumps(portable(result), indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
