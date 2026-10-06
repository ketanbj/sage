"""Alias retained for upstream Python users importing einsums."""

from pyeinsums import __version__, core, decomposition, fft, initialize, io, storage, utils

__all__ = ["__version__", "core", "utils", "decomposition", "fft", "io", "storage", "initialize"]

import sys as _sys

for _name in ("core", "utils", "decomposition", "fft", "io", "storage"):
    _sys.modules[__name__ + "." + _name] = globals()[_name]
_sys.modules[__name__ + ".core.errors"] = core.errors
