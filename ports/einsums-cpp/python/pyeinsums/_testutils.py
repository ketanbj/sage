"""Safe buffer-metadata fault injection used by the upstream API tests.

Malformed descriptors are rejected before exposing memory to native code.
"""

import numpy as np


class BadBuffer:
    def __init__(self, source=None):
        if isinstance(source, BadBuffer):
            source = source._checked_array()
        self._data = None if source is None else np.array(source, copy=True, order="C")
        self._ptr = None if self._data is None else self._data.ctypes.data
        self._dims = [] if self._data is None else list(self._data.shape)
        self._strides = [] if self._data is None else list(self._data.strides)
        self._ndim = len(self._dims)
        self._itemsize = 0 if self._data is None else self._data.itemsize
        self._format = "" if self._data is None else memoryview(self._data).format

    def _checked_array(self):
        if self._ptr is None or self._data is None:
            raise ValueError("null buffer")
        if self._ndim != len(self._dims) or self._ndim != len(self._strides):
            raise ValueError("buffer rank/metadata mismatch")
        if self._itemsize != self._data.itemsize or self._format != memoryview(self._data).format:
            raise ValueError("invalid buffer element descriptor")
        if any(n < 0 for n in self._dims) or any(s < 0 for s in self._strides):
            raise ValueError("invalid buffer dimensions or strides")
        span = (
            sum((d - 1) * s for d, s in zip(self._dims, self._strides, strict=True))
            + self._itemsize
        )
        if np.prod(self._dims) and span > self._data.nbytes:
            raise ValueError("buffer descriptor exceeds allocation")
        return np.lib.stride_tricks.as_strided(self._data, shape=self._dims, strides=self._strides)

    def __array__(self, dtype=None, copy=None):
        return np.array(self._checked_array(), dtype=dtype, copy=copy)

    def get_ptr(self):
        return self._ptr or 0

    def clear_ptr(self):
        self._ptr = None

    def get_ndim(self):
        return self._ndim

    def set_ndim(self, value):
        self._ndim = int(value)
        self.change_dims_size(value)
        self.change_strides_size(value)

    def set_ndim_noresize(self, value):
        self._ndim = int(value)

    def get_itemsize(self):
        return self._itemsize

    def set_itemsize(self, value):
        self._itemsize = int(value)

    def get_format(self):
        return self._format

    def set_format(self, value):
        self._format = str(value)

    def get_dims(self):
        return list(self._dims)

    def set_dims(self, value):
        self._dims = list(value)

    def set_dim(self, index, value):
        self._dims[index] = int(value)

    def get_strides(self):
        return list(self._strides)

    def set_strides(self, value):
        self._strides = list(value)

    def set_stride(self, index, value):
        self._strides[index] = int(value)

    def change_dims_size(self, value):
        self._dims = (self._dims + [0] * int(value))[: int(value)]

    def change_strides_size(self, value):
        self._strides = (self._strides + [0] * int(value))[: int(value)]
