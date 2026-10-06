"""Run the 23-operation comparison profile through the C++20 Python API."""

import json
import sys
from pathlib import Path

import numpy as np
import pyeinsums as ein


def execute(payload):
    if len(payload) != 36:
        raise ValueError("expected 36 bytes")
    op, m, k, n = payload[:4]
    if op >= 23 or any(d < 1 or d > 4 for d in (m, k, n)):
        raise ValueError("invalid profile input")
    values = np.frombuffer(payload[4:], dtype=np.int8).astype(np.float64) / 8
    a = ein.utils.create_tensor(values[: m * k].reshape(m, k))
    b = ein.utils.create_tensor(
        values[16 : 16 + (k * n if op == 4 else m * k)].reshape((k, n) if op == 4 else (m, k))
    )
    c = ein.core
    if op == 0:
        out = a.copy()
    elif op == 1:
        out = a + b
    elif op == 2:
        out = a * b
    elif op == 3:
        out = a.T
    elif op == 4:
        out = np.zeros((m, n))
        c.gemm("N", "N", 1, a, b, 0, out)
    elif op == 5:
        out = a.copy()
        c.scale(values[16], out)
    elif op == 6:
        out = a - b
    elif op == 7:
        out = a / (abs(b) + 1)
    elif op == 8:
        out = -a
    elif op == 9:
        out = a[:, :1].copy()
    elif op == 10:
        out = np.array([[c.dot(a, b)]])
    elif op in (11, 12):
        out = b.copy()
        c.axpby(2, a, 1 if op == 11 else -0.5, out)
    elif op == 13:
        out = np.zeros(m)
        c.gemv("N", 1, a, values[16 : 16 + k], 0, out)
        out = out.reshape(m, 1)
    elif op == 14:
        out = a.copy()
        c.ger(2, values[:m], values[16 : 16 + k], out)
    elif op == 15:
        from pyeinsums import _backend

        out = np.array([[_backend.scalar("vec_norm", a)]])
    elif op == 16:
        from pyeinsums import _backend

        out = np.array([[_backend.scalar("rmsd", a, b)]])
    elif op in (17, 18, 19):
        out = np.zeros((m, m))
        c.gemm("N", "T", 1, a, a, 0, out)
        for i in range(m):
            out[i, i] += 1
        if op == 17:
            c.invert(out)
        elif op == 18:
            w = np.empty(m)
            c.syev("N", out, w)
            out = w.reshape(1, m)
        else:
            packed, tau = c.qr(out)
            result = np.empty_like(out)
            c.gemm("N", "N", 1, c.q(packed, tau), c.r(packed, tau), 0, result)
            out = result
    elif op in (20, 21):
        result = np.asarray(
            (ein.fft.fft if op == 20 else ein.fft.ifft)(values[:k] + 1j * values[16 : 16 + k])
        )
        out = np.column_stack((result.real, result.imag))
    else:
        out = np.asarray(ein.fft.fftfreq(k)).reshape(1, k)
    out = np.asarray(out)
    return {"shape": [list(out.shape)], "strides": [[out.shape[1], 1]], "values": out.tolist()}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(64)
    try:
        print(json.dumps(execute(Path(sys.argv[1]).read_bytes())))
    except Exception as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(65) from error
