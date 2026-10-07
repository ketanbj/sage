"""Replay accepted path-experiment inputs through both production JSON/FFI APIs."""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import importlib.util
import json
import math
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def request(lib, payload):
    source = ctypes.create_string_buffer(json.dumps(payload, allow_nan=False).encode())
    pointer = lib.sage_api_request(source, len(source.value))
    if not pointer:
        raise ValueError("native response allocation failed")
    try:
        response = json.loads(ctypes.string_at(pointer))
    finally:
        lib.sage_api_free(pointer)
    if "error" in response:
        raise ValueError(response["error"])
    return response["ok"]


def number(x):
    return (
        x if math.isfinite(x) else "NaN" if math.isnan(x) else "Infinity" if x > 0 else "-Infinity"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads((args.run / "manifest.json").read_text())
    if manifest["status"] != "SAMPLED_LIBRARY_DECISIONS_PASS" or not manifest["cases"]:
        raise ValueError("incomplete source experiment")
    spec = importlib.util.spec_from_file_location(
        "experiment", ROOT / "tools/verification/explore_library_paths.py"
    )
    experiment = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(experiment)
    suffix = ".dylib" if sys.platform == "darwin" else ".so"
    libraries = {
        "rust": ROOT / ("ports/einsums-rs/target/debug/libsage_einsums" + suffix),
        "cpp20": ROOT / ("ports/einsums-cpp/build/libsage_einsums_cpp" + suffix),
    }
    records = []
    for language, path in libraries.items():
        lib = ctypes.CDLL(str(path))
        lib.sage_api_request.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        lib.sage_api_request.restype = ctypes.c_void_p
        lib.sage_api_free.argtypes = [ctypes.c_void_p]
        lib.sage_api_free.restype = None
        for case in manifest["cases"]:
            payload = (args.run / case["file"]).read_bytes()
            if hashlib.sha256(payload).hexdigest() != case["sha256"]:
                raise ValueError("generated input drift")
            mode, n, i, real, a, b = experiment.decode(payload)
            expected = experiment.expectation(payload)
            if expected != case["expected"]:
                raise ValueError("saved expectation drift")
            if mode == 0:
                result = request(
                    lib, {"op": "rfftfreq" if real else "fftfreq", "params": {"n": n, "d": 1}}
                )
                # Real FFT exposes only the nonnegative half.
                if real and i >= n // 2 + 1:
                    continue
                actual = float(result["arrays"][0]["values"][i][0])
                passed = actual == expected / n
            elif mode == 1:
                result = request(
                    lib,
                    {
                        "op": "getrf",
                        "arrays": [
                            {"dtype": "float64", "shape": [2, 1], "values": [[a, 0], [b, 0]]}
                        ],
                    },
                )
                passed = result["indices"][0] == (1 if abs(a) >= abs(b) else 2)
            else:
                # Copy checks value preservation; branch selection is a separate proof.
                result = request(
                    lib,
                    {
                        "op": "copy",
                        "arrays": [
                            {"dtype": "float64", "shape": [1, 1], "values": [[number(a), 0]]}
                        ],
                    },
                )
                actual = float(result["arrays"][0]["values"][0][0])
                passed = (
                    math.isnan(actual)
                    if math.isnan(a)
                    else struct.pack("<d", actual) == struct.pack("<d", a)
                )
            records.append(
                {"language": language, "file": case["file"], "mode": mode, "passed": bool(passed)}
            )
    report = {
        "status": "PASS" if records and all(r["passed"] for r in records) else "FAIL",
        "claim": "Finite public JSON/FFI replay; guard branch selection is proved separately.",
        "source_manifest_sha256": hashlib.sha256(
            (args.run / "manifest.json").read_bytes()
        ).hexdigest(),
        "checker_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "library_hashes": {
            lang: hashlib.sha256(path.read_bytes()).hexdigest() for lang, path in libraries.items()
        },
        "checks": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "checks": len(records)}))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
