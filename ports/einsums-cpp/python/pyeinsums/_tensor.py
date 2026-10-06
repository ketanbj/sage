"""Python buffers and ownership; every exposed arithmetic operation calls C++20."""

from __future__ import annotations

import operator

import numpy as np

from . import _backend as backend
from . import errors


def _shape(dims):
    shape = tuple(operator.index(x) for x in dims)
    if any(x < 0 for x in shape):
        raise ValueError("dimensions must be nonnegative")
    return shape


class RuntimeTensor(np.ndarray):
    _scalar_dtype = np.dtype("float64")
    _is_view = False

    def __new__(cls, *args):
        name = "(Unnamed)"
        if args and isinstance(args[0], str):
            name, args = args[0], args[1:]
        if not args:
            array = np.zeros((), dtype=cls._scalar_dtype)
        elif len(args) == 1 and isinstance(args[0], (list, tuple)):
            array = np.zeros(_shape(args[0]), dtype=cls._scalar_dtype)
        elif len(args) in (1, 2):
            source = args[0]._checked_array() if hasattr(args[0], "_checked_array") else args[0]
            original = np.asarray(source)
            if cls._is_view:
                if original.dtype != cls._scalar_dtype:
                    raise TypeError("view dtype must match the underlying buffer")
                array = original
            else:
                if not np.issubdtype(cls._scalar_dtype, np.complexfloating) and np.iscomplexobj(
                    original
                ):
                    original = original.real
                array = np.array(original, dtype=cls._scalar_dtype, copy=True, order="C")
            if len(args) == 2:
                reshaped = array.reshape(_shape(args[1]))
                if cls._is_view and array.size and not np.shares_memory(array, reshaped):
                    raise ValueError("reshape would copy a view")
                array = reshaped
        else:
            raise TypeError("expected dimensions, a buffer, or a name and dimensions")
        obj = np.ndarray.view(array, cls)
        obj._name = name
        return obj

    def __array_finalize__(self, obj):
        self._name = getattr(obj, "_name", "(Unnamed)")

    def __repr__(self):
        return f"{type(self).__name__}({self._name!r}, {np.asarray(self)!r})"

    def __str__(self):
        return str(np.asarray(self))

    def rank(self):
        return self.ndim

    def dim(self, axis):
        return self.shape[axis]

    def dims(self):
        return list(self.shape)

    def stride(self, axis):
        return np.asarray(self).strides[axis] // self.itemsize

    def strides(self):
        return [s // self.itemsize for s in np.asarray(self).strides]

    def size(self):
        return np.asarray(self).size

    def __len__(self):
        return self.size()

    def get_name(self):
        return self._name

    def set_name(self, name):
        self._name = str(name)

    name = property(get_name, set_name)

    def zero(self):
        self.set_all(0)

    def set_all(self, value):
        np.asarray(self)[...] = value

    def assign(self, source):
        a = np.asarray(source)
        if a.shape != self.shape:
            raise errors.dimension_error("assignment shapes differ")
        np.copyto(np.asarray(self), a, casting="unsafe")
        return self

    def __iter__(self):
        return _Iterator(self)

    def __reversed__(self):
        return _Iterator(self, True)

    def __getitem__(self, key):
        out = np.asarray(self)[key]
        if isinstance(out, np.ndarray) and out.dtype.name in _VIEWS:
            out = out.view(_VIEWS[out.dtype.name])
            out._name = self._name
        return out

    def __setitem__(self, key, value):
        np.asarray(self)[key] = np.asarray(value) if isinstance(value, RuntimeTensor) else value

    def to_rank_1_view(self):
        a = np.asarray(self)
        if not a.flags.c_contiguous:
            raise ValueError("cannot flatten a noncontiguous view without copying")
        return a.reshape(-1).view(_VIEWS[a.dtype.name])

    def copy(self, order="C"):
        return wrap(backend.result("copy", self), self._name)

    def __copy__(self):
        return self.copy()

    def __deepcopy__(self, memo=None):
        return self.copy()

    deepcopy = copy

    @property
    def T(self):
        if self.ndim != 2:
            raise errors.rank_error("transpose requires a matrix")
        return wrap(backend.result("permute", self, axes=[1, 0]), self._name + " transposed")

    def _binary(self, other, op, reverse=False, inplace=False):
        a = np.asarray(self)
        b = np.asarray(other._checked_array() if hasattr(other, "_checked_array") else other)
        dtype = a.dtype
        if np.iscomplexobj(b) and not np.iscomplexobj(a):
            b = b.real
        a, b = a.astype(dtype, copy=False), b.astype(dtype, copy=False)
        result = backend.result(op, b, a) if reverse else backend.result(op, a, b)
        if inplace:
            np.copyto(np.asarray(self), result, casting="unsafe")
            return self
        return wrap(result)

    def __neg__(self):
        return wrap(backend.result("negate", self))

    def __abs__(self):
        return wrap(backend.result("abs", self))

    def __matmul__(self, other):
        return wrap(backend.result("matmul", self, other))

    def __pow__(self, value):
        return wrap(backend.result("pow", self, alpha=value))


class RuntimeTensorView(RuntimeTensor):
    _is_view = True


class _Iterator:
    def __init__(self, tensor, reverse=False):
        self.tensor = tensor
        self.reverse = reverse
        self.index = tensor.size() - 1 if reverse else 0

    def __iter__(self):
        return self

    def __next__(self):
        if not 0 <= self.index < self.tensor.size():
            raise StopIteration
        out = np.asarray(self.tensor).flat[self.index]
        self.index += -1 if self.reverse else 1
        return out

    def reversed(self):
        out = _Iterator(self.tensor, not self.reverse)
        out.index = self.index
        return out

    __reversed__ = reversed


_TENSORS, _VIEWS = {}, {}
for _suffix, _dtype in zip("FDCZ", ("float32", "float64", "complex64", "complex128"), strict=True):
    for _prefix, _base, _registry in (
        ("RuntimeTensor", RuntimeTensor, _TENSORS),
        ("RuntimeTensorView", RuntimeTensorView, _VIEWS),
    ):
        _cls = type(
            _prefix + _suffix,
            (_base,),
            {"_scalar_dtype": np.dtype(_dtype), "__module__": "pyeinsums.core"},
        )
        globals()[_prefix + _suffix] = _cls
        _registry[_dtype] = _cls
    globals()["PyTensorIterator" + _suffix] = _Iterator


def wrap(array, name="(Unnamed)"):
    out = np.asarray(array).view(_TENSORS[np.asarray(array).dtype.name])
    out._name = name
    return out


def _operator(op, reverse=False, inplace=False):
    def apply(self, other):
        return self._binary(other, op, reverse, inplace)

    return apply


for _py, _cpp20 in (
    ("add", "add"),
    ("sub", "subtract"),
    ("mul", "multiply"),
    ("truediv", "divide"),
):
    setattr(RuntimeTensor, f"__{_py}__", _operator(_cpp20))
    setattr(RuntimeTensor, f"__r{_py}__", _operator(_cpp20, reverse=True))
    setattr(RuntimeTensor, f"__i{_py}__", _operator(_cpp20, inplace=True))
RuntimeTensor.__rdiv__ = RuntimeTensor.__rtruediv__
