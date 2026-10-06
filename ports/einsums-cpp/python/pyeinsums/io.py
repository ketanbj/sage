"""HDF5 files through C++20's HDF5 implementation."""

from pathlib import Path

import numpy as np

from . import _backend as backend
from ._tensor import wrap


def write(path, name, tensor, *, overwrite=False):
    backend.call(
        "write_hdf5",
        tensor,
        path=str(Path(path).resolve()),
        name=str(name),
        overwrite=bool(overwrite),
    )


def read(path, name):
    return wrap(
        backend.result("read_hdf5", path=str(Path(path).resolve()), name=str(name)), str(name)
    )


class DiskTensor:
    """Working buffer for an HDF5 dataset; flush is explicit and reports I/O errors."""

    def __init__(self, path, name, tensor=None):
        self.path, self.name = Path(path).resolve(), str(name)
        if tensor is not None:
            write(self.path, self.name, tensor)
        self.tensor = read(self.path, self.name)

    @property
    def shape(self):
        return self.tensor.shape

    def __getitem__(self, key):
        return self.tensor[key]

    def __setitem__(self, key, value):
        self.tensor[key] = value

    def __array__(self, dtype=None, copy=None):
        return np.array(self.tensor, dtype=dtype, copy=copy)

    def flush(self):
        write(self.path, self.name, self.tensor, overwrite=True)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        if exc_type is None:
            self.flush()
