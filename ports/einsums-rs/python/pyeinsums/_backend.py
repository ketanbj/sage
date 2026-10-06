"""Storage conversion and the Rust request boundary. No NumPy numerical kernels."""

from __future__ import annotations

import builtins
import ctypes
import json
import math
import os
import sys
from pathlib import Path

import numpy as np

from . import errors

_DTYPES = {"float32", "float64", "complex64", "complex128"}
_library = None


def _load():
    global _library
    if _library is None:
        name = "libsage_einsums.dylib" if sys.platform == "darwin" else "libsage_einsums.so"
        explicit = os.environ.get("EINSUMS_RS_LIBRARY")
        candidates = (
            [Path(explicit)]
            if explicit
            else [
                Path(__file__).parent / "_native" / name,
                Path(__file__).parents[2] / "target/release" / name,
                Path(__file__).parents[2] / "target/debug" / name,
            ]
        )
        for path in candidates:
            if not path.is_file():
                continue
            lib = ctypes.PyDLL(str(path.resolve()))
            if not hasattr(lib, "sage_api_request"):
                continue
            lib.sage_api_request.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
            lib.sage_api_request.restype = ctypes.c_void_p
            lib.sage_api_free.argtypes = [ctypes.c_void_p]
            lib.sage_api_free.restype = None
            _library = lib
            break
        if _library is None:
            raise ImportError(
                "Build the Rust library with cargo build --release, or set EINSUMS_RS_LIBRARY"
            )
    return _library


def asarray(value, dtype=None, writable=False):
    if hasattr(value, "_checked_array"):
        value = value._checked_array()
    a = np.asarray(value, dtype=dtype)
    if a.dtype.name not in _DTYPES:
        raise TypeError("expected float32/64 or complex64/128 buffer")
    if not a.dtype.isnative:
        raise TypeError("expected native-endian buffer")
    if writable and not a.flags.writeable:
        raise ValueError("output buffer is read-only")
    return a


def _number(x):
    x = float(x)
    return (
        x if math.isfinite(x) else "NaN" if math.isnan(x) else "Infinity" if x > 0 else "-Infinity"
    )


def encode(a):
    a = asarray(a)
    return {
        "dtype": a.dtype.name,
        "shape": list(a.shape),
        "values": [[_number(complex(x).real), _number(complex(x).imag)] for x in a.flat],
    }


def decode(a):
    values = [
        complex(float(r), float(i)) if a["dtype"].startswith("complex") else float(r)
        for r, i in a["values"]
    ]
    return np.array(values, dtype=a["dtype"]).reshape(a["shape"])


def call(op, *arrays, **params):
    def clean(v):
        if isinstance(v, (complex, np.complexfloating)):
            return [_number(v.real), _number(v.imag)]
        if isinstance(v, (float, np.floating)):
            return _number(v)
        if isinstance(v, np.generic):
            return v.item()
        if isinstance(v, dict):
            return {k: clean(x) for k, x in v.items()}
        if isinstance(v, (list, tuple)):
            return [clean(x) for x in v]
        return v

    payload = json.dumps(
        {"op": op, "arrays": [encode(a) for a in arrays], "params": clean(params)}, allow_nan=False
    ).encode()
    source = ctypes.create_string_buffer(payload)
    lib = _load()
    pointer = lib.sage_api_request(source, len(payload))
    if not pointer:
        raise RuntimeError("Rust request allocation failed")
    try:
        response = json.loads(ctypes.string_at(pointer))
    finally:
        lib.sage_api_free(pointer)
    if "error" in response:
        e = response["error"]
        cls = getattr(errors, e["kind"], getattr(builtins, e["kind"], RuntimeError))
        raise cls(e["message"])
    return response["ok"]


def result(op, *arrays, **params):
    return decode(call(op, *arrays, **params)["arrays"][0])


def scalar(op, *arrays, **params):
    r, i = call(op, *arrays, **params)["scalars"][0]
    return (
        complex(float(r), float(i))
        if any(np.iscomplexobj(a) for a in arrays) and op in ("sum", "dot", "true_dot", "det")
        else float(r)
    )


def output(destination, source):
    target = asarray(destination, writable=True)
    if target.shape != source.shape:
        raise errors.dimension_error("output shape does not match result")
    if target.dtype != source.dtype:
        raise TypeError("output dtype does not match result")
    np.copyto(target, source, casting="no")
