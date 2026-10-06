"""Block and tiled tensor containers with C++20 dense conversion."""

import operator

import numpy as np

from . import _backend as backend
from . import errors
from ._tensor import wrap


class TiledTensor:
    def __init__(self, name, partitions, dtype=float):
        self.name = str(name)
        self.partitions = [list(map(operator.index, axis)) for axis in partitions]
        if any(n < 0 for axis in self.partitions for n in axis):
            raise ValueError("tile dimensions must be nonnegative")
        self.dtype = np.dtype(dtype)
        self.tiles = {}

    @property
    def shape(self):
        return tuple(sum(axis) for axis in self.partitions)

    def __setitem__(self, index, value):
        index = tuple(index)
        if len(index) != len(self.partitions):
            raise errors.rank_error("tile index rank mismatch")
        if any(i < 0 or i >= len(axis) for i, axis in zip(index, self.partitions, strict=True)):
            raise IndexError("tile index out of bounds")
        shape = tuple(axis[i] for axis, i in zip(self.partitions, index, strict=True))
        a = backend.asarray(value)
        if a.shape != shape or a.dtype != self.dtype:
            raise errors.dimension_error("tile dimensions/dtype disagree with partition")
        self.tiles[index] = wrap(a.copy())

    def __getitem__(self, index):
        index = tuple(index)
        if index not in self.tiles:
            shape = [axis[i] for axis, i in zip(self.partitions, index, strict=True)]
            self[index] = np.zeros(shape, dtype=self.dtype)
        return self.tiles[index]

    def to_dense(self):
        keys = sorted(self.tiles)
        return wrap(
            backend.result(
                "tile_dense",
                *(self.tiles[key] for key in keys),
                indices=keys,
                partitions=self.partitions,
                dtype=self.dtype.name,
            ),
            self.name,
        )


class BlockTensor:
    def __init__(self, name, blocks, rank=2, dtype=float):
        self.name, self.rank = str(name), operator.index(rank)
        self.dimensions = list(map(operator.index, blocks))
        self.dtype = np.dtype(dtype)
        if self.rank < 1 or any(n < 0 for n in self.dimensions):
            raise ValueError("invalid block shape")
        self.blocks = [wrap(np.zeros([n] * self.rank, dtype=dtype)) for n in self.dimensions]

    @property
    def shape(self):
        return (sum(self.dimensions),) * self.rank

    def __getitem__(self, index):
        return self.blocks[index]

    def __setitem__(self, index, value):
        a = backend.asarray(value)
        if a.shape != (self.dimensions[index],) * self.rank or a.dtype != self.dtype:
            raise errors.dimension_error("block dimensions/dtype disagree with partition")
        self.blocks[index] = wrap(a.copy())

    def to_dense(self):
        return wrap(
            backend.result(
                "block_dense",
                *self.blocks,
                blocks=self.dimensions,
                rank=self.rank,
                dtype=self.dtype.name,
            ),
            self.name,
        )
