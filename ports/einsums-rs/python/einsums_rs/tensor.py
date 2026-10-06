"""Owned, arbitrary-rank f64 tensors. Arithmetic executes in Rust.

This is the port's API, not yet import/API compatible with pyeinsums. Array
exports and permutations are copies; zero-copy Python views are not implemented.
"""

from __future__ import annotations

import ctypes as ct
import math
import operator
import weakref


def bind(library):
    def function(name, args, result):
        call = getattr(library._library, name)
        call.argtypes = args
        call.restype = result
        return call

    pointer, size = ct.c_void_p, ct.c_size_t
    library._new = function("sage_tensor_new", [pointer, size, pointer, size], pointer)
    library._free = function("sage_tensor_free", [pointer], None)
    library._shape = function("sage_tensor_shape", [pointer, pointer, size], ct.c_ssize_t)
    library._values = function("sage_tensor_values", [pointer, pointer, size], ct.c_ssize_t)
    library._apply = function(
        "sage_tensor_apply", [ct.c_uint32, pointer, pointer, ct.c_double, pointer, size], pointer
    )
    library._einsum = function(
        "sage_tensor_einsum",
        [pointer, pointer, pointer, size, pointer, size, pointer, size],
        pointer,
    )
    library._set = function("sage_tensor_set", [pointer, pointer, size, ct.c_double], ct.c_int)
    library._error = function("sage_tensor_last_error", [], ct.c_char_p)


def sizes(values):
    values = tuple(operator.index(x) for x in values)
    if any(x < 0 or x > ct.c_size_t(-1).value for x in values):
        raise ValueError("dimensions and indices must be nonnegative and fit size_t")
    return (ct.c_size_t * len(values))(*values)


class Tensor:
    def __init__(self, library, shape, values=None):
        dims = sizes(shape)
        count = math.prod(dims)
        values = [0.0] * count if values is None else list(values)
        if len(values) != count:
            raise ValueError("tensor shape does not match value count")
        data = (ct.c_double * count)(*values)
        self._initialize(library, library._new(dims, len(dims), data, count))

    def _initialize(self, library, handle):
        if not handle:
            raise ValueError(library._error().decode())
        self._library = library
        self._handle = handle
        self._finalizer = weakref.finalize(self, library._free, handle)

    @classmethod
    def _owned(cls, library, handle):
        obj = cls.__new__(cls)
        obj._initialize(library, handle)
        return obj

    @property
    def shape(self):
        rank = self._library._shape(self._handle, None, 0)
        out = (ct.c_size_t * rank)()
        self._library._shape(self._handle, out, rank)
        return tuple(out)

    @property
    def strides(self):
        shape = self.shape
        return tuple(math.prod(shape[i + 1 :]) for i in range(len(shape)))

    @property
    def values(self):
        count = self._library._values(self._handle, None, 0)
        out = (ct.c_double * count)()
        self._library._values(self._handle, out, count)
        return list(out)

    def __array__(self, dtype=None, copy=None):
        import numpy as np

        if copy is False:
            raise ValueError("Rust tensors currently require a copy for NumPy export")
        return np.array(self.values, dtype=dtype or np.float64).reshape(self.shape)

    def _other(self, b):
        if not isinstance(b, Tensor) or self._library is not b._library:
            raise TypeError("operands must be tensors from the same Library")
        return b._handle

    def _op(self, op, b=None, scalar=0.0, params=()):
        b_handle = None if b is None else self._other(b)
        params = sizes(params)
        handle = self._library._apply(op, self._handle, b_handle, scalar, params, len(params))
        return self._owned(self._library, handle)

    def copy(self):
        return self._op(0)

    def __neg__(self):
        return self._op(1)

    def __add__(self, b):
        return self._op(6, b) if isinstance(b, Tensor) else self._op(19, scalar=float(b))

    def __sub__(self, b):
        return self._op(7, b) if isinstance(b, Tensor) else self._op(19, scalar=-float(b))

    def __mul__(self, b):
        return self._op(8, b) if isinstance(b, Tensor) else self._op(2, scalar=float(b))

    __rmul__ = __mul__

    def __truediv__(self, b):
        return self._op(9, b) if isinstance(b, Tensor) else self._op(2, scalar=1.0 / float(b))

    def __matmul__(self, b):
        return self._op(10, b)

    def __pow__(self, power):
        return self._op(15, scalar=float(power))

    def exp(self):
        return self._op(16)

    def log(self):
        return self._op(17)

    def __abs__(self):
        return self._op(18)

    def slice(self, ranges):
        ranges = tuple(ranges)
        if len(ranges) != len(self.shape):
            raise ValueError("one (start, stop) range per dimension is required")
        return self._op(20, params=[r[0] for r in ranges] + [r[1] for r in ranges])

    def permute(self, axes):
        return self._op(4, params=axes)

    @property
    def T(self):
        return self.permute(reversed(range(len(self.shape))))

    def reshape(self, shape):
        return self._op(5, params=shape)

    def inverse(self):
        return self._op(3)

    def solve(self, rhs):
        return self._op(11, rhs)

    def sum(self):
        return self._op(12).values[0]

    def norm(self):
        return self._op(13).values[0]

    def dot(self, b):
        return self._op(14, b).values[0]

    def einsum(self, a_labels, b, b_labels, output_labels):
        labels = [label.encode("ascii") for label in (a_labels, b_labels, output_labels)]
        buffers = [ct.create_string_buffer(label) for label in labels]
        handle = self._library._einsum(
            self._handle,
            self._other(b),
            buffers[0],
            len(labels[0]),
            buffers[1],
            len(labels[1]),
            buffers[2],
            len(labels[2]),
        )
        return self._owned(self._library, handle)

    def _indices(self, key):
        indices = key if isinstance(key, tuple) else (key,)
        if len(indices) != len(self.shape):
            raise IndexError("one integer index per tensor dimension is required")
        result = []
        for value, dim in zip(indices, self.shape, strict=True):
            value = operator.index(value)
            if value < 0:
                value += dim
            if not 0 <= value < dim:
                raise IndexError("tensor index out of range")
            result.append(value)
        return sizes(result)

    def __getitem__(self, key):
        indices = self._indices(key)
        offset = sum(i * s for i, s in zip(indices, self.strides, strict=True))
        return self.values[offset]

    def __setitem__(self, key, value):
        indices = self._indices(key)
        if self._library._set(self._handle, indices, len(indices), float(value)) != 0:
            raise IndexError(self._library._error().decode())
