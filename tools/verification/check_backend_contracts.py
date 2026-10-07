"""Record finite dispatcher/BLAS checks across both ports and the pinned upstream."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COMMIT = "22a115978041e905461b24d9ca2a17bfcce01f32"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, choices=range(1, 4), default=3)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    fixture = ROOT / "fixtures/einsums-paths/backend_replay.py"
    shutil.copy2(fixture, output / fixture.name)
    upstream = ROOT / ".sage/upstreams/einsums" / COMMIT / "checkout"
    checkout = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=upstream, text=True
    ).strip()
    if checkout != COMMIT:
        raise ValueError("wrong upstream checkout")
    image = subprocess.check_output(
        ["docker", "image", "inspect", "--format", "{{.Id}}", "sage-einsums-python:22a1159"],
        text=True,
    ).strip()
    records = []
    for attempt in range(args.repetitions):
        for threads in (1, 2):
            for language in ("original", "rust", "cpp20"):
                env = dict(
                    os.environ, OMP_NUM_THREADS=str(threads), OPENBLAS_NUM_THREADS=str(threads)
                )
                if language == "original":
                    command = [
                        "docker",
                        "run",
                        "--rm",
                        "--platform",
                        "linux/amd64",
                        "--network",
                        "none",
                        "--memory",
                        "2g",
                        "--cpus",
                        "2",
                        "-v",
                        f"{output}:/audit:ro",
                        "-e",
                        f"OMP_NUM_THREADS={threads}",
                        "-e",
                        f"OPENBLAS_NUM_THREADS={threads}",
                        "--entrypoint",
                        "python3",
                        image,
                        "/audit/backend_replay.py",
                    ]
                else:
                    port = ROOT / "ports" / ("einsums-rs" if language == "rust" else "einsums-cpp")
                    suffix = ".dylib" if sys.platform == "darwin" else ".so"
                    library = port / (
                        "target/debug/libsage_einsums"
                        if language == "rust"
                        else "build/libsage_einsums_cpp"
                    )
                    library = library.with_suffix(suffix)
                    if not library.is_file():
                        raise ValueError(f"build the {language} native library first")
                    env.update(PYTHONPATH=str(port / "python"))
                    env["EINSUMS_RS_LIBRARY" if language == "rust" else "EINSUMS_CPP_LIBRARY"] = (
                        str(library)
                    )
                    command = [sys.executable, str(fixture)]
                library_sha = (
                    None
                    if language == "original"
                    else hashlib.sha256(library.read_bytes()).hexdigest()
                )
                r = subprocess.run(
                    command, env=env, capture_output=True, text=True, timeout=180, check=False
                )
                if (
                    language != "original"
                    and hashlib.sha256(library.read_bytes()).hexdigest() != library_sha
                ):
                    raise ValueError("native library changed during replay")
                label = f"{language}-{threads}-{attempt}"
                (output / f"{label}.stdout").write_text(r.stdout)
                (output / f"{label}.stderr").write_text(r.stderr)
                payloads = [
                    json.loads(line)
                    for line in r.stdout.splitlines()
                    if line.startswith('{"checks"')
                ]
                checks = payloads[0]["checks"] if len(payloads) == 1 else []
                records.append(
                    {
                        "language": language,
                        "library_sha256": library_sha,
                        "thread_setting": threads,
                        "attempt": attempt,
                        "returncode": r.returncode,
                        "command": command,
                        "checks": len(checks),
                        "passed": len(checks) == 156
                        and r.returncode == 0
                        and all(c["passed"] for c in checks),
                        "failures": [c for c in checks if not c["passed"]],
                        "plan_classes": sorted({c["plan"] for c in checks if c["plan"]}),
                        "output_sha256": hashlib.sha256(r.stdout.encode()).hexdigest(),
                    }
                )
    paths = [
        "libs/EinsumsPy/TensorAlgebra/include/EinsumsPy/TensorAlgebra/PyTensorAlgebra.hpp",
        "libs/Einsums/BLAS/include/Einsums/BLAS.hpp",
        "libs/Einsums/TensorAlgebra/include/Einsums/TensorAlgebra/TensorAlgebra.hpp",
    ]
    failures = collections.Counter()
    for execution in records:
        for finding in execution["failures"]:
            kind = (
                "REFERENCE_BUFFER_LAYOUT_DIFFERENCE"
                if finding["contract"] in ("gemm-T-strided", "gemm-C-strided")
                else "REFERENCE_CONTRACTION_UNRESOLVED"
            )
            if execution["language"] != "original":
                kind = "CANDIDATE_FAILURE"
            failures[kind] += 1
    ports_pass = all(r["passed"] for r in records if r["language"] != "original")
    report = {
        "status": (
            "FINITE_BACKEND_CONTRACTS_PASS"
            if all(r["passed"] for r in records)
            else "REFERENCE_DISAGREEMENTS"
            if ports_pass and all(r["checks"] == 156 for r in records)
            else "FAIL"
        ),
        "finding_classifications": dict(failures),
        "repetitions": args.repetitions,
        "claim": "Finite public dispatch/backend numerical probes; no symbolic backend theorem.",
        "source_commit": COMMIT,
        "reference_image": image,
        "thread_scope": (
            "Environment requests of one/two threads; actual worker counts "
            "are not asserted. Ports do not delegate to BLAS."
        ),
        "source_hashes": {
            p: hashlib.sha256((upstream / p).read_bytes()).hexdigest() for p in paths
        },
        "port_source_hashes": {
            str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
            for directory in (
                ROOT / "ports/einsums-rs/src",
                ROOT / "ports/einsums-cpp/api",
                ROOT / "ports/einsums-rs/python/pyeinsums",
                ROOT / "ports/einsums-cpp/python/pyeinsums",
            )
            for p in directory.rglob("*")
            if p.suffix in (".rs", ".py", ".hpp", ".cpp")
        },
        "library_hashes": {
            lang: hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
            for lang, relative in {
                "rust": "ports/einsums-rs/target/debug/libsage_einsums"
                + (".dylib" if sys.platform == "darwin" else ".so"),
                "cpp20": "ports/einsums-cpp/build/libsage_einsums_cpp"
                + (".dylib" if sys.platform == "darwin" else ".so"),
            }.items()
        },
        "fixture_sha256": hashlib.sha256(fixture.read_bytes()).hexdigest(),
        "checker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "executions": records,
    }
    (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "checks": sum(r["checks"] for r in records)}))
    return 0 if report["status"] == "FINITE_BACKEND_CONTRACTS_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
