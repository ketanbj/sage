# ruff: noqa: F822
# CPU exports below are installed dynamically from dtype/function tables.
"""Einsums CPU Python API implemented over the C++20 backend."""

from __future__ import annotations

import logging
import secrets
import threading
import time

import numpy as np

from . import _backend as backend
from . import _linalg, _tensor, errors
from ._tensor import wrap
from ._testutils import BadBuffer

__all__ = ["BadBuffer", "errors"]

# Explicitly export the upstream tensor types and numerical API, not helper imports.
for _name in ("RuntimeTensor", "RuntimeTensorView"):
    globals()[_name] = getattr(_tensor, _name)
for _suffix in "FDCZ":
    for _prefix in ("RuntimeTensor", "RuntimeTensorView", "PyTensorIterator"):
        globals()[_prefix + _suffix] = getattr(_tensor, _prefix + _suffix)
for _name in (
    "Norm",
    "Vectors",
    "MAXABS",
    "ONE",
    "INFINITY",
    "FROBENIUS",
    "ALL",
    "SOME",
    "OVERWRITE",
    "NONE",
    "sum_square",
    "gemm",
    "gemv",
    "syev",
    "heev",
    "geev",
    "gesv",
    "scale",
    "scale_row",
    "scale_column",
    "dot",
    "true_dot",
    "axpy",
    "axpby",
    "ger",
    "getrf",
    "extract_plu",
    "getri",
    "invert",
    "norm",
    "vec_norm",
    "svd",
    "svd_nullspace",
    "svd_dd",
    "truncated_svd",
    "truncated_syev",
    "pseudoinverse",
    "solve_continuous_lyapunov",
    "qr",
    "q",
    "r",
    "direct_product",
    "det",
):
    globals()[_name] = getattr(_linalg, _name)

_initialized = False
_log = logging.getLogger("pyeinsums")


def gpu_enabled():
    return False


def initialize(argv=None):
    global _initialized
    backend._load()
    _initialized = True
    GlobalConfigMap.get_singleton().set_str("argv", " ".join(argv or []))


def finalize():
    global _initialized
    _initialized = False


def log(level, message):
    levels = [
        logging.DEBUG,
        logging.DEBUG,
        logging.INFO,
        logging.WARNING,
        logging.ERROR,
        logging.CRITICAL,
    ]
    if not 0 <= level < len(levels):
        raise ValueError("log level must be in 0..5")
    _log.log(levels[level], str(message))


def _logger(level):
    return lambda message: log(level, message)


for _level, _name in enumerate(("trace", "debug", "info", "warn", "error", "critical")):
    globals()["log_" + _name] = _logger(_level)


class GlobalConfigMap:
    _singleton = None
    _singleton_lock = threading.RLock()

    def __init__(self):
        self._maps = {kind: {} for kind in ("str", "int", "float", "bool")}
        self._lock = threading.RLock()

    @classmethod
    def get_singleton(cls):
        with cls._singleton_lock:
            if cls._singleton is None:
                cls._singleton = cls()
            return cls._singleton

    def empty(self):
        return self.size() == 0

    def size(self):
        with self._lock:
            return sum(len(m) for m in self._maps.values())

    def max_size(self):
        return np.iinfo(np.intp).max

    def _get(self, kind, key):
        with self._lock:
            return self._maps[kind][key]

    def _set(self, kind, key, value):
        cast = {"str": str, "int": int, "float": float, "bool": bool}[kind]
        with self._lock:
            self._maps[kind][str(key)] = cast(value)


for _kind in ("str", "int", "float", "bool"):

    def _get(self, key, kind=_kind):
        return self._get(kind, key)

    def _set(self, key, value, kind=_kind):
        return self._set(kind, key, value)

    setattr(GlobalConfigMap, "get_" + _kind, _get)
    setattr(GlobalConfigMap, "set_" + _kind, _set)


class Section:
    records = {}
    _lock = threading.RLock()

    def __init__(self, label, *args):
        if len(args) > 2:
            raise TypeError("too many Section arguments")
        self.label = str(label) + (" " + args[0] if args and isinstance(args[0], str) else "")
        self._start = time.perf_counter()
        self._ended = False

    def end(self):
        if not self._ended:
            with self._lock:
                elapsed, count = self.records.get(self.label, (0.0, 0))
                self.records[self.label] = (elapsed + time.perf_counter() - self._start, count + 1)
            self._ended = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.end()

    def __del__(self):
        if hasattr(self, "_ended"):
            self.end()


class EinsumGenericPlan:
    def __init__(self, C_indices, A_indices, B_indices):
        self.indices = (C_indices, A_indices, B_indices)

    def execute(self, C_prefactor, C, AB_prefactor, A, B):
        if isinstance(C, (list, tuple)):
            if len(C) != len(A) or len(C) != len(B):
                raise ValueError("batch lengths must match")
            # Compute the batch before mutating any destination.
            products = [
                self._result(C_prefactor, c, AB_prefactor, a, b)
                for c, a, b in zip(C, A, B, strict=True)
            ]
            for c, product in zip(C, products, strict=True):
                backend.output(c, product)
        else:
            backend.output(C, self._result(C_prefactor, C, AB_prefactor, A, B))

    def _result(self, beta, C, alpha, A, B):
        backend.asarray(C, writable=True)
        ci, ai, bi = self.indices
        destination = np.asarray(C)
        scalar_buffer = not ci and destination.size == 1
        result = backend.result(
            "einsum",
            A,
            B,
            destination.reshape(()) if scalar_buffer else C,
            a_labels=ai,
            b_labels=bi,
            out_labels=ci,
            alpha=alpha,
            beta=beta,
        )
        return result.reshape(destination.shape) if scalar_buffer else result


for _name in (
    "EinsumDotPlan",
    "EinsumDirectProductPlan",
    "EinsumGerPlan",
    "EinsumGemvPlan",
    "EinsumGemmPlan",
):
    globals()[_name] = type(_name, (EinsumGenericPlan,), {"__module__": __name__})


def compile_plan(C_indices, A_indices, B_indices):
    if any(not isinstance(x, str) for x in (C_indices, A_indices, B_indices)):
        raise TypeError("index expressions must be strings")
    if len(set(C_indices)) != len(C_indices) or any(
        x not in A_indices + B_indices for x in C_indices
    ):
        raise ValueError("invalid output indices")
    if not C_indices:
        cls = globals()["EinsumDotPlan"]
    elif C_indices == A_indices == B_indices:
        cls = globals()["EinsumDirectProductPlan"]
    elif set(A_indices).isdisjoint(B_indices):
        cls = globals()["EinsumGerPlan"]
    elif (
        len(A_indices) == len(B_indices) == len(C_indices) == 2
        and len(set(A_indices) & set(B_indices) - set(C_indices)) == 1
        and len(set(A_indices + B_indices)) == 3
    ):
        cls = globals()["EinsumGemmPlan"]
    elif len(C_indices) == 1 and min(len(A_indices), len(B_indices)) == 1:
        cls = globals()["EinsumGemvPlan"]
    else:
        cls = EinsumGenericPlan
    return cls(C_indices, A_indices, B_indices)


def _random_factory(dtype, operation):
    def create(name, dims, mean=1.0, force_zeros=1):
        parameters = {"dtype": dtype, "seed": secrets.randbits(63)}
        if operation == "random":
            parameters["shape"] = list(dims)
        else:
            parameters.update(n=int(dims), mean=mean, force_zeros=force_zeros)
        return wrap(backend.result(operation, **parameters), name)

    return create


for _suffix, _dtype in zip("FDCZ", ("float32", "float64", "complex64", "complex128"), strict=True):
    for _prefix, _operation in (
        ("create_random_tensor", "random"),
        ("create_random_definite", "random_definite"),
        ("create_random_semidefinite", "random_semidefinite"),
    ):
        globals()[_prefix + _suffix] = _random_factory(_dtype, _operation)

# CPU exports captured from the pinned compiled upstream extension.
__all__ = [
    "ALL",
    "BadBuffer",
    "EinsumDirectProductPlan",
    "EinsumDotPlan",
    "EinsumGemmPlan",
    "EinsumGemvPlan",
    "EinsumGenericPlan",
    "EinsumGerPlan",
    "FROBENIUS",
    "GlobalConfigMap",
    "INFINITY",
    "MAXABS",
    "NONE",
    "Norm",
    "ONE",
    "OVERWRITE",
    "PyTensorIteratorC",
    "PyTensorIteratorD",
    "PyTensorIteratorF",
    "PyTensorIteratorZ",
    "RuntimeTensor",
    "RuntimeTensorC",
    "RuntimeTensorD",
    "RuntimeTensorF",
    "RuntimeTensorView",
    "RuntimeTensorViewC",
    "RuntimeTensorViewD",
    "RuntimeTensorViewF",
    "RuntimeTensorViewZ",
    "RuntimeTensorZ",
    "SOME",
    "Section",
    "Vectors",
    "axpby",
    "axpy",
    "compile_plan",
    "create_random_definiteC",
    "create_random_definiteD",
    "create_random_definiteF",
    "create_random_definiteZ",
    "create_random_semidefiniteC",
    "create_random_semidefiniteD",
    "create_random_semidefiniteF",
    "create_random_semidefiniteZ",
    "create_random_tensorC",
    "create_random_tensorD",
    "create_random_tensorF",
    "create_random_tensorZ",
    "det",
    "direct_product",
    "dot",
    "errors",
    "extract_plu",
    "finalize",
    "geev",
    "gemm",
    "gemv",
    "ger",
    "gesv",
    "getrf",
    "getri",
    "gpu_enabled",
    "heev",
    "initialize",
    "invert",
    "log",
    "log_critical",
    "log_debug",
    "log_error",
    "log_info",
    "log_trace",
    "log_warn",
    "norm",
    "pseudoinverse",
    "q",
    "qr",
    "r",
    "scale",
    "scale_column",
    "scale_row",
    "solve_continuous_lyapunov",
    "sum_square",
    "svd",
    "svd_dd",
    "svd_nullspace",
    "syev",
    "true_dot",
    "truncated_svd",
    "truncated_syev",
    "vec_norm",
]
