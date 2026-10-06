"""Python access to the Rust campaign ABI; not a drop-in replacement for pyeinsums.

All calculations run in Rust. This adapter validates the Python/native boundary;
full upstream Python API/lifetime compatibility is tracked separately by SAGE.
"""

from __future__ import annotations

import ctypes
import json
from pathlib import Path

from .tensor import Tensor, bind


class Library:
    def __init__(self, path: str | Path) -> None:
        self._library = ctypes.PyDLL(str(Path(path).resolve()))
        self._execute = self._library.sage_einsums_execute
        self._execute.argtypes = [
            ctypes.c_void_p,
            ctypes.c_size_t,
            ctypes.c_void_p,
            ctypes.c_size_t,
        ]
        self._execute.restype = ctypes.c_ssize_t
        bind(self)

    def execute(self, payload: bytes) -> dict:
        if len(payload) != 36:
            raise ValueError("campaign input must contain 36 bytes")
        source = ctypes.create_string_buffer(payload)
        output = ctypes.create_string_buffer(16384)
        written = self._execute(source, len(payload), output, len(output))
        if written < 0:
            raise ValueError(f"Rust rejected input (code {written})")
        return json.loads(output.raw[:written])

    def tensor(self, shape, values=None) -> Tensor:
        return Tensor(self, shape, values)
