"""Einsums CPU Python API with numerical operations implemented in Rust."""

import atexit
import sys

from . import core, decomposition, fft, io, storage, utils

__version__ = "0.2.0"
__all__ = ["core", "utils", "decomposition", "fft", "io", "storage", "initialize"]


def initialize():
    import sys

    args = [sys.argv[0]]
    arguments = iter(sys.argv[1:])
    for arg in arguments:
        if arg == "--einsums":
            try:
                args.append(next(arguments))
            except StopIteration as exc:
                raise ValueError("--einsums requires an argument") from exc
    core.initialize(args)


initialize()
atexit.register(core.finalize)

sys.modules[__name__ + ".core.errors"] = core.errors
