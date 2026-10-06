"""Upstream CPU linear-algebra signatures, backed by Rust."""

from enum import IntEnum

import numpy as np

from . import _backend as backend
from . import errors
from ._tensor import wrap


class Norm(IntEnum):
    MAXABS = ord("M")
    ONE = ord("1")
    INFINITY = ord("I")
    FROBENIUS = ord("F")


class Vectors(IntEnum):
    ALL = ord("A")
    SOME = ord("S")
    OVERWRITE = ord("O")
    NONE = ord("N")


MAXABS, ONE, INFINITY, FROBENIUS = tuple(Norm)
ALL, SOME, OVERWRITE, NONE = tuple(Vectors)


def _job(value):
    if not isinstance(value, str) or value.upper() not in ("N", "V"):
        raise ValueError("eigenvector job must be N or V")
    return value.upper()


def _output(value):
    return backend.asarray(value, writable=True)


def _tuple(op, *args, **params):
    return tuple(wrap(backend.decode(a)) for a in backend.call(op, *args, **params)["arrays"])


def sum_square(A):
    return tuple(z[0] for z in backend.call("sum_square", A)["scalars"])


def gemm(transA, transB, alpha, A, B, beta, C):
    _output(C)
    backend.output(
        C, backend.result("gemm", A, B, C, trans_a=transA, trans_b=transB, alpha=alpha, beta=beta)
    )


def gemv(transA, alpha, A, B, beta, C):
    _output(C)
    backend.output(C, backend.result("gemv", A, B, C, trans_a=transA, alpha=alpha, beta=beta))


def syev(jobz, A, W):
    jobz = _job(jobz)
    a, w = _output(A), _output(W)
    if a.ndim != 2 or a.shape[0] != a.shape[1] or w.shape != (a.shape[0],):
        raise errors.dimension_error(
            "eigensystem requires a square matrix and matching eigenvalue vector"
        )
    if w.dtype != np.empty((), dtype=a.dtype).real.dtype:
        raise TypeError("eigenvalue dtype must be the real component dtype")
    values, vectors = _tuple("syev", A)
    backend.output(W, np.asarray(values))
    if jobz == "V":
        backend.output(A, np.asarray(vectors).T.copy())


heev = syev


def geev(jobvl, jobvr, A, W, Vl, Vr):
    jobvl, jobvr = _job(jobvl), _job(jobvr)
    a, w = _output(A), _output(W)
    if a.ndim != 2 or a.shape[0] != a.shape[1] or w.shape != (a.shape[0],):
        raise errors.dimension_error("geev requires square A and matching eigenvalue vector")
    dtype = np.dtype(
        "complex64" if a.dtype in (np.dtype("float32"), np.dtype("complex64")) else "complex128"
    )
    if w.dtype != dtype:
        raise TypeError("geev eigenvalues must have the corresponding complex dtype")
    for job, destination in ((jobvl, Vl), (jobvr, Vr)):
        if job == "V":
            out = _output(destination)
            if out.shape != a.shape or out.dtype != dtype:
                raise errors.dimension_error("eigenvector output has wrong shape/dtype")
    values, left, right = _tuple("geev", A)
    backend.output(W, np.asarray(values))
    if jobvl == "V":
        backend.output(Vl, np.asarray(left))
    if jobvr == "V":
        backend.output(Vr, np.asarray(right))


def gesv(A, B):
    _output(A)
    _output(B)
    a, b = _tuple("gesv", A, B)
    backend.output(A, np.asarray(a))
    backend.output(B, np.asarray(b))


def scale(factor, A):
    _output(A)
    backend.output(A, backend.result("scale", A, alpha=factor))


def scale_row(row, factor, A):
    _output(A)
    backend.output(A, backend.result("scale_row", A, index=row, alpha=factor))


def scale_column(column, factor, A):
    _output(A)
    backend.output(A, backend.result("scale_column", A, index=column, alpha=factor))


def dot(A, B):
    return backend.scalar("dot", A, B)


def true_dot(A, B):
    return backend.scalar("true_dot", A, B)


def axpy(alpha, x, y):
    _output(y)
    backend.output(y, backend.result("axpy", x, y, alpha=alpha))


def axpby(alpha, x, beta, y):
    _output(y)
    backend.output(y, backend.result("axpby", x, y, alpha=alpha, beta=beta))


def ger(alpha, X, Y, A):
    _output(A)
    backend.output(A, backend.result("ger", X, Y, A, alpha=alpha))


def getrf(A):
    _output(A)
    response = backend.call("getrf", A)
    backend.output(A, backend.decode(response["arrays"][0]))
    return response["indices"]


def extract_plu(A, pivot):
    return _tuple("extract_plu", A, pivots=list(pivot))


def getri(A, pivot):
    _output(A)
    backend.output(A, backend.result("getri", A, pivots=list(pivot)))


def invert(A):
    _output(A)
    backend.output(A, backend.result("invert", A))


def norm(type, A):
    kind = Norm(type).name
    # The pinned Python wrapper applies LAPACK to transposed row-major storage.
    kind = {"ONE": "INFINITY", "INFINITY": "ONE"}.get(kind, kind)
    return backend.scalar("norm", A, kind=kind)


def vec_norm(A):
    if np.asarray(A).ndim != 1:
        raise errors.rank_error("vec_norm requires a vector")
    return backend.scalar("vec_norm", A)


def svd(A):
    return _tuple("svd", A, job="ALL")


def svd_dd(A, job=Vectors.ALL):
    job = Vectors(job)
    result = _tuple("svd_dd", A, job=job.name)
    if job == Vectors.NONE:
        return (
            wrap(np.empty((0, 0), dtype=np.asarray(A).dtype)),
            result[1],
            wrap(np.empty((0, 0), dtype=np.asarray(A).dtype)),
        )
    return result


def svd_nullspace(A):
    return wrap(backend.result("svd_nullspace", A))


def truncated_svd(A, k):
    return _tuple("truncated_svd", A, k=k)


def truncated_syev(A, k):
    return _tuple("truncated_syev", A, k=k)


def pseudoinverse(A, tol):
    return wrap(backend.result("pseudoinverse", A, tol=tol))


def solve_continuous_lyapunov(A, Q):
    return wrap(backend.result("solve_continuous_lyapunov", A, Q))


def qr(A):
    return _tuple("qr", A)


def q(qr, tau):
    return wrap(backend.result("q", qr, tau))


def r(qr, tau):
    return wrap(backend.result("r", qr, tau))


def direct_product(alpha, A, B, beta, C):
    _output(C)
    backend.output(C, backend.result("direct_product", A, B, C, alpha=alpha, beta=beta))


def det(A):
    return backend.scalar("det", A)
