"""Complex and real transforms. Inverse transforms are unnormalized, as in Einsums."""

from . import _backend as backend
from ._tensor import wrap


def _transform(op, a, n):
    return wrap(backend.result(op, a, **({} if n is None else {"n": n})))


def fft(a, n=None):
    return _transform("fft", a, n)


def ifft(a, n=None):
    return _transform("ifft", a, n)


def rfft(a, n=None):
    return _transform("rfft", a, n)


def irfft(a, n=None):
    return _transform("irfft", a, n)


def fftfreq(n, d=1.0):
    return wrap(backend.result("fftfreq", n=n, d=d))


def rfftfreq(n, d=1.0):
    return wrap(backend.result("rfftfreq", n=n, d=d))
