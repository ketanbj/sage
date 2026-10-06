from __future__ import annotations

from typing import Any

import numpy as np

from sage.einsums.domain import OPERATIONS as TENSOR_OPERATIONS
from sage.einsums.domain import TensorCase

OPERATIONS = (
    *TENSOR_OPERATIONS,
    "subtract",
    "divide",
    "negate",
    "slice",
    "dot",
    "axpy",
    "axpby",
    "gemv",
    "ger",
    "norm",
    "rmsd",
    "inverse",
    "syev_values",
    "qr_reconstruct",
    "fft",
    "ifft",
    "fftfreq",
)


class LibraryCase(TensorCase):
    @classmethod
    def from_binary(cls, payload: bytes, case_id: str) -> LibraryCase:
        if len(payload) != 36 or payload[0] >= len(OPERATIONS):
            raise ValueError("invalid Einsums library operation or payload length")
        if any(not 1 <= d <= 4 for d in payload[1:4]):
            raise ValueError("campaign dimensions must be 1..4")
        return cls(case_id, payload)

    @property
    def operation(self) -> str:
        return OPERATIONS[self.payload[0]]

    def to_dict(self) -> dict[str, Any]:
        return {**super().to_dict(), "schema_version": "einsums-library-1.0"}

    def reference(self) -> dict[str, list[list[float]]]:
        op, m, k, _n = self.payload[:4]
        if op < 6:
            return super().reference()
        data = np.frombuffer(self.payload[4:], dtype=np.int8).astype(float) / 8
        c: Any
        a, b = data[: m * k].reshape(m, k), data[16 : 16 + m * k].reshape(m, k)
        if op == 6:
            c = a - b
        elif op == 7:
            c = a / (np.abs(b) + 1)
        elif op == 8:
            c = -a
        elif op == 9:
            c = a[:, :1]
        elif op == 10:
            c = np.array([[np.sum(a * b)]])
        elif op == 11:
            c = 2 * a + b
        elif op == 12:
            c = 2 * a - 0.5 * b
        elif op == 13:
            c = a @ data[16 : 16 + k].reshape(k, 1)
        elif op == 14:
            c = a + 2 * np.outer(data[:m], data[16 : 16 + k])
        elif op == 15:
            c = np.array([[np.linalg.norm(a)]])
        elif op == 16:
            c = np.array([[np.sqrt(np.mean((a - b) ** 2))]])
        elif op == 17:
            c = np.linalg.inv(a @ a.T + np.eye(m))
        elif op == 18:
            c = np.linalg.eigvalsh(a @ a.T + np.eye(m)).reshape(1, m)
        elif op == 19:
            q, r = np.linalg.qr(a @ a.T + np.eye(m))
            c = q @ r
        elif op in (20, 21):
            z = data[:k] + 1j * data[16 : 16 + k]
            transformed = np.fft.fft(z) if op == 20 else np.fft.ifft(z) * k
            c = np.column_stack((transformed.real, transformed.imag))
        else:
            c = np.fft.fftfreq(k).reshape(1, k)
        return {
            "shape": [[int(c.shape[0]), int(c.shape[1])]],
            "strides": [[int(c.shape[1]), 1]],
            "values": c.tolist(),
        }


def bootstrap_seeds() -> list[LibraryCase]:
    data = bytes((i * 7 + 3) % 256 for i in range(32))
    return [
        LibraryCase.from_binary(bytes([op, 2, 3, 4]) + data, f"seed-{op:02d}")
        for op in range(len(OPERATIONS))
    ]
