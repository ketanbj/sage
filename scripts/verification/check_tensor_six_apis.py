"""Native/public Python replay of the proof domain; deliberately not called a proof."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from sage.verification.tensor_six import OBLIGATIONS  # noqa: E402


def reference(op: str, a: np.ndarray, b: np.ndarray) -> np.ndarray:
    if op == "copy":
        return a.copy()
    if op == "transpose":
        return a.T.copy()
    if op == "add":
        return a + b
    if op == "multiply":
        return a * b
    if op == "scale":
        return b.flat[0] * a
    out = np.zeros((a.shape[0], b.shape[1]), dtype=np.float64)
    for r in range(out.shape[0]):
        for c in range(out.shape[1]):
            for k in range(a.shape[1]):
                out[r, c] = float(out[r, c]) + float(a[r, k]) * float(b[k, c])
    return out


def run(language: str, library: Path, output: Path) -> dict:
    port = ROOT / ("ports/einsums-rs" if language == "rust" else "ports/einsums-cpp")
    os.environ["EINSUMS_RS_LIBRARY" if language == "rust" else "EINSUMS_CPP_LIBRARY"] = str(
        library.resolve()
    )
    sys.path.insert(0, str(port / "python"))
    api = importlib.import_module("pyeinsums")
    backend = importlib.import_module("pyeinsums._backend")
    assert Path(api.__file__).is_relative_to(port)
    patterns = [
        (np.arange(32, dtype=np.int16) * 7 - 110).astype(np.int8),
        np.zeros(32, dtype=np.int8),
        np.full(32, -128, dtype=np.int8),
        np.full(32, 127, dtype=np.int8),
        np.resize(np.array([-128, 127, 0, -1, 1, 8, -8], dtype=np.int8), 32),
        np.random.default_rng(20261006).integers(-128, 128, 32, dtype=np.int16).astype(np.int8),
    ]
    checks = []
    for op, m, k, n in OBLIGATIONS:
        for pattern in patterns:
            values = pattern.astype(np.float64) / 8.0
            a = values[: m * k].reshape(m, k).copy()
            br, bc = (k, n) if op == "matmul" else (m, k)
            b = values[16 : 16 + br * bc].reshape(br, bc).copy()
            ta = api.utils.create_tensor(a, dtype=np.float64)
            tb = api.utils.create_tensor(b, dtype=np.float64)
            before = np.asarray(ta).copy()
            if op == "copy":
                actual = ta.copy()
            elif op == "add":
                actual = ta + tb
            elif op == "multiply":
                actual = ta * tb
            elif op == "transpose":
                actual = ta.T
            elif op == "matmul":
                actual = ta @ tb
            else:
                actual = ta.copy()
                api.core.scale(float(b.flat[0]), actual)
            expected = reference(op, a, b)
            result = np.asarray(actual)
            np.testing.assert_array_equal(result.view(np.uint64), expected.view(np.uint64))
            assert result.shape == expected.shape and result.flags.c_contiguous
            np.testing.assert_array_equal(np.asarray(ta).view(np.uint64), before.view(np.uint64))
            assert not np.shares_memory(result, np.asarray(ta))
            # Also exercise the native JSON/FFI endpoint independently of Python operators.
            params = (
                {"axes": [1, 0]}
                if op == "transpose"
                else ({"alpha": float(b.flat[0])} if op == "scale" else {})
            )
            args = [a, b] if op in ("add", "multiply", "matmul") else [a]
            decoded = backend.result("permute" if op == "transpose" else op, *args, **params)
            np.testing.assert_array_equal(decoded.view(np.uint64), expected.view(np.uint64))
            checks.append({"operation": op, "shape": [m, k, n], "passed": True})
    # Explicit guards: these requests must retain valid general-library behavior.
    for data in (
        np.arange(25.0, dtype=np.float64).reshape(5, 5),
        np.array([[0.1, -0.0], [np.inf, np.nan]], dtype=np.float64),
        np.arange(6.0, dtype=np.float32).reshape(2, 3),
        np.arange(6.0, dtype=np.complex128).reshape(2, 3) + 1j,
    ):
        t = api.utils.create_tensor(data, dtype=data.dtype)
        np.testing.assert_array_equal(np.asarray(t.copy()), data)
        np.testing.assert_array_equal(np.asarray(t.T), data.T)
    report = {
        "status": "PASS",
        "kind": "native replay, not model checking",
        "language": language,
        "operation_shape_combinations": len(OBLIGATIONS),
        "patterns_per_combination": len(patterns),
        "python_checks": len(checks),
        "json_ffi_checks": len(checks),
        "library": str(library.resolve()),
        "library_sha256": hashlib.sha256(library.read_bytes()).hexdigest(),
        "checks": checks,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2))
    print(f"{language}: {len(checks)} Python and {len(checks)} JSON/FFI checks passed")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--language", required=True, choices=["rust", "cpp20"])
    parser.add_argument("--library", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    run(args.language, args.library, args.output)
