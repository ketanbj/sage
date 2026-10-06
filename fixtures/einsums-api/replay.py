"""Replay authenticated SymSan payloads through an installed CPU Python API.

Each payload supplies all matrix values and dimensions. Operation and dtype sweeps
are fixed harness parameters, not additional generated inputs. NumPy computes
independent expectations and residuals; it never substitutes for an API call.
"""

import json
import sys
from pathlib import Path

import einsums as ein
import numpy as np

OPERATIONS = (
    "tensor",
    "gemm",
    "gemv",
    "scale",
    "scale_row",
    "scale_column",
    "dot",
    "true_dot",
    "axpy",
    "axpby",
    "ger",
    "direct_product",
    "norm",
    "vec_norm",
    "sum_square",
    "lu",
    "invert",
    "gesv",
    "det",
    "syev",
    "heev",
    "geev",
    "svd",
    "svd_dd",
    "svd_nullspace",
    "qr",
    "pseudoinverse",
    "solve_continuous_lyapunov",
    "truncated_svd",
    "truncated_syev",
    "plan",
)
DTYPES = ("float32", "float64", "complex64", "complex128")


def encode(value):
    a = np.asarray(value)
    return {
        "shape": list(a.shape),
        "dtype": a.dtype.name,
        "values": [[float(z.real), float(z.imag)] for z in a.ravel()],
    }


def check_operation(op, a, b):
    c = ein.core
    m, n = a.shape
    k = min(m, n)
    real = a.real.dtype
    eye = np.eye(m, dtype=a.dtype)
    h = a @ a.conj().T + eye
    x = a[:, 0].copy()
    y = b[0].copy()
    result, expected = [], []

    def add(value, oracle):
        result.append(encode(value))
        expected.append(encode(oracle))

    if op == "tensor":
        t = ein.utils.create_tensor(a, dtype=a.dtype)
        u = ein.utils.create_tensor(b, dtype=b.dtype)
        for value, oracle in (
            (t + u, a + b),
            (t - u, a - b),
            (t * u, a * b),
            (t / (u * 0 + 2), a / 2),
        ):
            add(value, oracle)
        view = t[:, : max(1, n // 2)]
        view *= 2
        modified = a.copy()
        modified[:, : max(1, n // 2)] *= 2
        add(t, modified)
    elif op == "gemm":
        out = eye.copy()
        c.gemm("N", "C", 0.5, a, b, -0.25, out)
        add(out, 0.5 * a @ b.conj().T - 0.25 * eye)
    elif op == "gemv":
        out = x.copy()
        c.gemv("N", 0.5, a, y, -0.25, out)
        add(out, 0.5 * a @ y - 0.25 * x)
    elif op in ("scale", "scale_row", "scale_column"):
        out, oracle = a.copy(), a.copy()
        if op == "scale":
            c.scale(0.5, out)
            oracle *= 0.5
        elif op == "scale_row":
            c.scale_row(m - 1, 0.5, out)
            oracle[-1, :] *= 0.5
        else:
            c.scale_column(n - 1, 0.5, out)
            oracle[:, -1] *= 0.5
        add(out, oracle)
    elif op in ("dot", "true_dot"):
        add(
            np.asarray(getattr(c, op)(a, b), dtype=a.dtype),
            np.sum((a.conj() if op == "true_dot" else a) * b, dtype=a.dtype),
        )
    elif op in ("axpy", "axpby"):
        out = b.copy()
        if op == "axpy":
            c.axpy(0.5, a, out)
            beta = 1
        else:
            c.axpby(0.5, a, -0.25, out)
            beta = -0.25
        add(out, 0.5 * a + beta * b)
    elif op == "ger":
        out = a.copy()
        c.ger(0.5, x, y, out)
        add(out, a + 0.5 * np.outer(x, y))
    elif op == "direct_product":
        out = a.copy()
        c.direct_product(0.5, a, b, -0.25, out)
        add(out, 0.5 * a * b - 0.25 * a)
    elif op == "norm":
        for kind, oracle in (
            (c.MAXABS, np.abs(a).max()),
            (c.ONE, np.linalg.norm(a, np.inf)),
            (c.INFINITY, np.linalg.norm(a, 1)),
            (c.FROBENIUS, np.linalg.norm(a)),
        ):
            add(np.asarray(c.norm(kind, a), dtype=real), np.asarray(oracle, dtype=real))
    elif op == "vec_norm":
        add(np.asarray(c.vec_norm(x), dtype=real), np.asarray(np.linalg.norm(x), dtype=real))
    elif op == "sum_square":
        sums, scale = c.sum_square(x)
        add(
            np.asarray(sums * scale * scale, dtype=real), np.asarray(np.vdot(x, x).real, dtype=real)
        )
    elif op == "lu":
        packed = h.copy()
        piv = c.getrf(packed)
        p, lower, upper = (np.asarray(v) for v in c.extract_plu(packed, piv))
        add(p @ h - lower @ upper, np.zeros_like(h))
        c.getri(packed, piv)
        add(packed, np.linalg.inv(h))
    elif op == "invert":
        out = h.copy()
        c.invert(out)
        add(out, np.linalg.inv(h))
    elif op == "gesv":
        out = b.copy()
        c.gesv(h.copy(), out)
        add(out, np.linalg.solve(h, b))
    elif op == "det":
        add(np.asarray(c.det(h), dtype=a.dtype), np.linalg.det(h))
    elif op in ("syev", "heev"):
        v, w = h.copy(), np.empty(m, dtype=real)
        getattr(c, op)("V", v, w)
        add(w, np.linalg.eigvalsh(h))
        add((h @ v.T - v.T * w) / np.linalg.norm(h), np.zeros_like(h))
        add(v.conj() @ v.T, eye)
    elif op == "geev":
        original = a[:, : min(m, n)]
        original = np.resize(original, (m, m)).copy()
        dtype = np.complex64 if real == np.dtype("float32") else np.complex128
        w = np.empty(m, dtype=dtype)
        left, right = np.empty((m, m), dtype=dtype), np.empty((m, m), dtype=dtype)
        c.geev("V", "V", original.copy(), w, left, right)
        oracle = np.linalg.eigvals(original).astype(dtype)
        # Pair by minimum distance, since conjugate pairs can have nearly equal real parts.
        remaining = list(oracle)
        aligned = []
        for z in w:
            j = min(range(len(remaining)), key=lambda i: abs(z - remaining[i]))
            aligned.append(remaining.pop(j))
        scale = max(1, np.linalg.norm(original))
        add(w / scale, np.array(aligned, dtype=dtype) / scale)
        add((original @ right - right * w) / scale, np.zeros_like(right))
        add((original.conj().T @ left - left * w.conj()) / scale, np.zeros_like(left))
        add(np.linalg.norm(right, axis=0), np.ones(m, dtype=real))
        add(np.linalg.norm(left, axis=0), np.ones(m, dtype=real))
    elif op in ("svd", "svd_dd", "truncated_svd"):
        source = a
        if op == "truncated_svd":
            source = np.resize(a, (8, 8)).copy() + np.eye(8, dtype=a.dtype)
            u, s, vh = (np.asarray(v) for v in c.truncated_svd(source, 1))
            add(s[:1], np.linalg.svd(source, compute_uv=False)[:1])
            add(
                (source @ vh[:1].conj().T - u[:, :1] * s[:1]) / np.linalg.norm(source),
                np.zeros((8, 1), dtype=a.dtype),
            )
        else:
            jobs = (c.ALL, c.SOME, c.NONE) if op == "svd_dd" else (None,)
            for job in jobs:
                u, s, vh = (
                    np.asarray(v) for v in (c.svd(source) if job is None else c.svd_dd(source, job))
                )
                add(s, np.linalg.svd(source, compute_uv=False))
                if job != c.NONE:
                    add(
                        (u[:, :k] @ np.diag(s) @ vh[:k] - source) / max(1, np.linalg.norm(source)),
                        np.zeros_like(source),
                    )
                    active_u = u if job is None or job == c.ALL else u[:, :k]
                    active_vh = vh if job is None or job == c.ALL else vh[:k]
                    add(active_u.conj().T @ active_u, np.eye(active_u.shape[1], dtype=a.dtype))
                    add(active_vh @ active_vh.conj().T, np.eye(active_vh.shape[0], dtype=a.dtype))
    elif op == "svd_nullspace":
        null = np.asarray(c.svd_nullspace(a))
        rank = np.linalg.matrix_rank(a)
        add(null.conj().T @ null, np.eye(n - rank, dtype=a.dtype))
        add(a @ null, np.zeros((m, n - rank), dtype=a.dtype))
    elif op == "qr":
        packed, tau = c.qr(a)
        q, r = np.asarray(c.q(packed, tau)), np.asarray(c.r(packed, tau))
        # Upstream wide q includes untouched packed columns beyond the thin Q.
        q, r = q[:, :k], r[:k, :]
        add(q @ r, a)
        add(q.conj().T @ q, np.eye(k, dtype=a.dtype))
    elif op == "pseudoinverse":
        tol = 1e-5 if real == np.dtype("float32") else 1e-10
        out = np.asarray(c.pseudoinverse(a, tol))
        u, s, vh = np.linalg.svd(a, full_matrices=False)
        inverse = np.zeros_like(s)
        np.divide(1, s, out=inverse, where=s > tol)
        add(out, (vh.conj().T * inverse) @ u.conj().T)
    elif op == "solve_continuous_lyapunov":
        q = b @ b.conj().T
        out = np.asarray(c.solve_continuous_lyapunov(h, q))
        add((h @ out + out @ h.conj().T) / max(1, np.linalg.norm(q)), q / max(1, np.linalg.norm(q)))
    elif op == "truncated_syev":
        source = np.resize(a, (8, 8)).copy()
        source = source @ source.conj().T + np.eye(8, dtype=a.dtype)
        v, w = (np.asarray(z) for z in c.truncated_syev(source, 1))
        order = np.argsort(np.abs(w))[::-1]
        w, v = w[order], v[:, order]
        add(w[:1], np.linalg.eigvalsh(source)[-1:])
        add(
            (source @ v[:, :1] - v[:, :1] * w[:1]) / np.linalg.norm(source),
            np.zeros((8, 1), dtype=a.dtype),
        )
    elif op == "plan":
        out = np.zeros_like(a)
        c.compile_plan("ij", "ij", "ij").execute(0, out, 0.5, a, b)
        add(out, 0.5 * a * b)
        out = np.zeros(1, dtype=a.dtype)
        c.compile_plan("", "ij", "ij").execute(0, out, 0.5, a, b)
        add(out, np.asarray([0.5 * np.sum(a * b)], dtype=a.dtype))
    else:
        raise ValueError(op)
    return result, expected


def main():
    corpus, operation = Path(sys.argv[1]), sys.argv[2]
    for case in json.loads(corpus.read_text()):
        raw = bytes.fromhex(case["hex"])
        m, n = raw[1], raw[3]
        av = np.frombuffer(raw[4:20], dtype=np.int8).astype(float) / 8
        bv = np.frombuffer(raw[20:36], dtype=np.int8).astype(float) / 8
        for dtype in DTYPES:
            a = av[: m * n].astype(dtype)
            b = bv[: m * n].astype(dtype)
            if "complex" in dtype:
                a += 1j * bv[: m * n]
                b -= 1j * av[: m * n]
            record = {"case_id": case["case_id"], "operation": operation, "dtype": dtype}
            try:
                actual, expected = check_operation(operation, a.reshape(m, n), b.reshape(m, n))
                record.update(actual=actual, expected=expected)
            except Exception as exc:
                record["error"] = f"{type(exc).__name__}: {exc}"
            print(json.dumps(record), flush=True)


if __name__ == "__main__":
    main()
