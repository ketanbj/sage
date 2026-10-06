"""Public Python tensor factories and iteration helpers."""

from __future__ import annotations

import functools
import itertools
import random

__all__ = ["random"]

import numpy as np

from . import core


def labeled_section(arg):
    def decorate(func, label):
        @functools.wraps(func)
        def wrapped(*args, **kwargs):
            with core.Section(label):
                return func(*args, **kwargs)

        return wrapped

    if callable(arg):
        return decorate(arg, arg.__name__)
    if isinstance(arg, str):
        return lambda func: decorate(func, f"{func.__name__} {arg}")
    raise TypeError("expected a function or label")


def enumerate_many(*args, start=0):
    for index, values in enumerate(itertools.zip_longest(*args), start=start):
        yield (*values, index)


class TensorIndices:
    def __init__(self, other, reverse=False):
        if isinstance(other, TensorIndices):
            self.shape, self.index, self.reverse = other.shape, other.index, other.reverse
        else:
            self.shape = tuple(other.shape)
            self.reverse = reverse
            self.index = int(np.prod(self.shape)) - 1 if reverse else 0

    def __iter__(self):
        return self

    def __reversed__(self):
        result = TensorIndices(self)
        result.reverse = not self.reverse
        return result

    def __next__(self):
        if not 0 <= self.index < int(np.prod(self.shape)):
            raise StopIteration
        value = np.unravel_index(self.index, self.shape)
        self.index += -1 if self.reverse else 1
        return tuple(int(i) for i in value)


def _suffix(dtype):
    dtype = np.dtype(dtype)
    try:
        return {"float32": "F", "float64": "D", "complex64": "C", "complex128": "Z"}[dtype.name]
    except KeyError as exc:
        raise TypeError("tensor dtype must be real or complex floating point") from exc


def create_tensor(*args, dtype=float):
    return getattr(core, "RuntimeTensor" + _suffix(dtype))(*args)


def tensor_factory(name, dims, dtype=float, method="einsums"):
    if method == "numpy":
        return np.zeros(dims, dtype=dtype)
    if method in ("einsums", "pyeinsums"):
        return create_tensor(name, dims, dtype=dtype)
    raise ValueError("method must be einsums or numpy")


def remove_complex(dtype):
    return np.empty((), dtype=dtype).real.dtype.type


def add_complex(dtype):
    return (
        np.complex64
        if np.dtype(dtype) in (np.dtype("float32"), np.dtype("complex64"))
        else np.complex128
    )


def create_random_tensor(name, dims, dtype=float):
    return getattr(core, "create_random_tensor" + _suffix(dtype))(name, dims)


def create_random_numpy_array(dims, dtype=float):
    return np.asarray(create_random_tensor("random", dims, dtype)).copy()


def random_tensor_factory(name, dims, dtype=float, method="einsums"):
    value = create_random_tensor(name, dims, dtype)
    return _method(value, method)


def _method(value, method):
    if method == "numpy":
        return np.asarray(value).copy()
    if method in ("einsums", "pyeinsums"):
        return value
    raise ValueError("method must be einsums or numpy")


def create_random_definite(name, rows, mean=1.0, dtype=float):
    return getattr(core, "create_random_definite" + _suffix(dtype))(name, rows, mean)


def create_random_definite_numpy_array(rows, mean=1.0, dtype=float):
    return np.asarray(create_random_definite("random", rows, mean, dtype)).copy()


def random_definite_tensor_factory(name, rows, mean=1.0, dtype=float, method="einsums"):
    return _method(create_random_definite(name, rows, mean, dtype), method)


def create_random_semidefinite(name, rows, mean=1.0, force_zeros=1, dtype=float):
    return getattr(core, "create_random_semidefinite" + _suffix(dtype))(
        name, rows, mean, force_zeros
    )


def create_random_semidefinite_numpy_array(rows, mean=1.0, force_zeros=1, dtype=float):
    return np.asarray(create_random_semidefinite("random", rows, mean, force_zeros, dtype)).copy()


def random_semidefinite_tensor_factory(
    name, rows, mean=1.0, force_zeros=1, dtype=float, method="einsums"
):
    return _method(create_random_semidefinite(name, rows, mean, force_zeros, dtype), method)


# Retained because the upstream Python suite and downstream utilities import them.
__singles = [np.float32]
__doubles = [float, np.float64]
__complex_singles = [np.complex64]
__complex_doubles = [complex, np.complex128]

# CPU exports captured from the pinned compiled upstream extension.
__all__ = [
    "TensorIndices",
    "add_complex",
    "create_random_definite",
    "create_random_definite_numpy_array",
    "create_random_numpy_array",
    "create_random_semidefinite",
    "create_random_semidefinite_numpy_array",
    "create_random_tensor",
    "create_tensor",
    "enumerate_many",
    "labeled_section",
    "random_definite_tensor_factory",
    "random_semidefinite_tensor_factory",
    "random_tensor_factory",
    "remove_complex",
    "tensor_factory",
]
