from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

OPERATIONS = ("copy", "add", "multiply", "transpose", "matmul", "scale")


@dataclass
class TensorCase:
    case_id: str
    payload: bytes
    provenance: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_binary(cls, payload: bytes, case_id: str) -> TensorCase:
        if len(payload) != 36:
            raise ValueError("Einsums tensor input must contain exactly 36 bytes")
        if payload[0] >= len(OPERATIONS) or any(not 1 <= d <= 4 for d in payload[1:4]):
            raise ValueError("operation must be 0..5 and dimensions must be 1..4")
        return cls(case_id, payload)

    @property
    def operation(self) -> str:
        return OPERATIONS[self.payload[0]]

    def to_binary(self) -> bytes:
        return self.payload

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "einsums-tensor-1.0",
            "case_id": self.case_id,
            "operation": self.operation,
            "dimensions": list(self.payload[1:4]),
            "payload_hex": self.payload.hex(),
            "provenance": self.provenance,
        }

    def reference(self) -> dict[str, list[list[float]]]:
        op, m, k, n = self.payload[:4]
        data = np.frombuffer(self.payload[4:], dtype=np.int8).astype(np.float64) / 8
        a = data[: m * k].reshape(m, k)
        b = data[16 : 16 + (k * n if op == 4 else m * k)].reshape((k, n) if op == 4 else (m, k))
        if op == 0:
            c = a.copy()
        elif op == 1:
            c = a + b
        elif op == 2:
            c = a * b
        elif op == 3:
            c = a.T.copy()
        elif op == 4:
            c = np.einsum("ik,kj->ij", a, b)
        else:
            c = a * data[16]
        return {
            "shape": [[int(c.shape[0]), int(c.shape[1])]],
            "strides": [[int(c.shape[1]), 1]],
            "values": c.tolist(),
        }


def bootstrap_seeds() -> list[TensorCase]:
    """Solver starting inputs only; never returned as validation evidence."""
    data = bytes((i * 7 + 3) % 256 for i in range(32))
    return [
        TensorCase.from_binary(bytes([op, 2, 3, 4]) + data, f"seed-{op}")
        for op in range(len(OPERATIONS))
    ]
