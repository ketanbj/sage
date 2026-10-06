"""Replay generated inputs through Python tensor APIs (0..17) or campaign ABI (18..22)."""

import json
import math
import sys
from pathlib import Path

from einsums_rs import Library


def execute(library, raw):
    if len(raw) != 36 or raw[0] > 22 or any(d < 1 or d > 4 for d in raw[1:4]):
        raise ValueError("invalid campaign input")
    op, m, k, n = raw[:4]
    if op >= 18:
        return library.execute(raw)
    values = [(x if x < 128 else x - 256) / 8.0 for x in raw[4:]]
    a = library.tensor([m, k], values[: m * k])
    b_shape = [k, n] if op == 4 else [m, k]
    b = library.tensor(b_shape, values[16 : 16 + math.prod(b_shape)])
    if op == 0:
        c = a.copy()
    elif op == 1:
        c = a + b
    elif op == 2:
        c = a * b
    elif op == 3:
        c = a.T
    elif op == 4:
        c = a @ b
    elif op == 5:
        c = a * values[16]
    elif op == 6:
        c = a - b
    elif op == 7:
        c = a / (abs(b) + 1.0)
    elif op == 8:
        c = -a
    elif op == 9:
        c = a.slice([(0, m), (0, 1)])
    elif op == 10:
        c = library.tensor([1, 1], [a.dot(b)])
    elif op == 11:
        c = a * 2 + b
    elif op == 12:
        c = a * 2 - b * 0.5
    elif op == 13:
        c = a @ library.tensor([k, 1], values[16 : 16 + k])
    elif op == 14:
        x = library.tensor([m], values[:m])
        y = library.tensor([k], values[16 : 16 + k])
        c = a + x.einsum("i", y, "j", "ij") * 2
    elif op == 15:
        c = library.tensor([1, 1], [a.norm()])
    elif op == 16:
        c = library.tensor([1, 1], [(a - b).norm() / math.sqrt(m * k)])
    elif op == 17:
        identity = library.tensor([m, m], [float(i == j) for i in range(m) for j in range(m)])
        c = (a @ a.T + identity).inverse()
    data = c.values
    return {
        "shape": [list(c.shape)],
        "strides": [list(c.strides)],
        "values": [data[i : i + c.shape[1]] for i in range(0, len(data), c.shape[1])],
    }


if __name__ == "__main__":
    print(json.dumps(execute(Library(sys.argv[1]), Path(sys.argv[2]).read_bytes())))
