"""Finite CPU dispatcher/backend contract checks; also runs in the pinned reference image."""

from __future__ import annotations
import json
import numpy as np
from einsums import core as c


def main():
    rng = np.random.default_rng(80417)
    results = []
    for dtype in (np.float32, np.float64, np.complex64, np.complex128):
        low = dtype in (np.float32, np.complex64)
        for m, k, n in ((2, 3, 4), (8, 5, 7), (9, 9, 9)):
            a = rng.uniform(-1, 1, (m, k)).astype(dtype)
            b = rng.uniform(-1, 1, (k, n)).astype(dtype)
            if np.issubdtype(dtype, np.complexfloating):
                a += 0.5j * a
                b -= 0.25j * b

            def check(name, actual, expected, plan=None):
                actual, expected = np.asarray(actual), np.asarray(expected)
                passed = actual.shape == expected.shape and np.allclose(
                    actual, expected, atol=2e-4 if low else 1e-10, rtol=5e-4 if low else 1e-9
                )
                results.append(
                    {
                        "contract": name,
                        "dtype": np.dtype(dtype).name,
                        "shape": [m, k, n],
                        "passed": bool(passed),
                        "max_abs_error": float(np.max(np.abs(actual - expected), initial=0)),
                        "plan": plan,
                    }
                )

            for mode in ("N", "T", "C"):
                right = b if mode == "N" else b.T if mode == "T" else b.conj().T
                for layout in ("contiguous", "strided"):
                    operand = (
                        np.array(right, order="C", copy=True) if layout == "contiguous" else right
                    )
                    out = np.ones((m, n), dtype=dtype)
                    c.gemm("N", mode, 0.5, a, operand, -0.25, out)
                    check("gemm-" + mode + "-" + layout, out, 0.5 * a @ b - 0.25)
            x = b[:, 0].copy()
            out = np.ones(m, dtype=dtype)
            c.gemv("N", 0.5, a, x, -0.25, out)
            check("gemv", out, 0.5 * a @ x - 0.25)
            for name, ol, al, bl, left, right, expected in (
                ("plan-gemm", "ij", "ik", "kj", a, b, a @ b),
                ("plan-gemv", "i", "ij", "j", a, x, a @ x),
                (
                    "plan-ger",
                    "ij",
                    "i",
                    "j",
                    a[:, 0].copy(),
                    b[0, :].copy(),
                    np.outer(a[:, 0], b[0, :]),
                ),
                ("plan-direct", "ij", "ij", "ij", a, a, a * a),
                ("plan-dot", "", "ij", "ij", a, a, np.asarray([np.sum(a * a)], dtype=dtype)),
            ):
                expected = np.asarray(expected)
                out = np.zeros(expected.shape, dtype=dtype)
                plan = c.compile_plan(ol, al, bl)
                plan.execute(0.0, out, 0.5, left, right)
                check(name, out, 0.5 * expected, type(plan).__name__)
            volume = rng.uniform(-1, 1, (m, k, n)).astype(dtype)
            vector = rng.uniform(-1, 1, k).astype(dtype)
            out = np.zeros((m, n), dtype=dtype)
            plan = c.compile_plan("ik", "ijk", "j")
            plan.execute(0.0, out, 0.5, volume, vector)
            check(
                "plan-generic",
                out,
                0.5 * np.einsum("ijk,j->ik", volume, vector),
                type(plan).__name__,
            )
    print(json.dumps({"checks": results, "passed": all(r["passed"] for r in results)}))
    return 0 if all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
