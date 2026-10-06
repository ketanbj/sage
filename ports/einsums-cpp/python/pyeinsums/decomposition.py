"""C++20 tensor decomposition and reconstruction entrypoints."""

from . import _backend as backend
from ._tensor import wrap


def _results(op, *arrays, **params):
    return tuple(wrap(backend.decode(a)) for a in backend.call(op, *arrays, **params)["arrays"])


def tucker(A, ranks):
    output = _results("tucker", A, ranks=list(ranks))
    return output[0], output[1:]


def hooi(A, ranks, iterations=100, tolerance=1e-8):
    output = _results("hooi", A, ranks=list(ranks), iterations=iterations, tol=tolerance)
    return output[0], output[1:]


def cp(A, rank, iterations=100, tolerance=1e-8):
    return _results("cp", A, rank=rank, iterations=iterations, tol=tolerance)


def reconstruct_tucker(core, factors):
    return wrap(backend.result("reconstruct_tucker", core, *factors))


def reconstruct_cp(factors):
    return wrap(backend.result("reconstruct_cp", *factors))


def unfold(A, mode):
    return wrap(backend.result("unfold", A, mode=mode))


def khatri_rao(A, B):
    return wrap(backend.result("khatri_rao", A, B))


def mode_product(A, B, mode):
    return wrap(backend.result("mode_product", A, B, mode=mode))


def weight_tensor(A, weights):
    return wrap(backend.result("weight_tensor", A, weights))


def parafac(A, rank, n_iter_max=100, tolerance=1e-8):
    return cp(A, rank, n_iter_max, tolerance)


def weighted_parafac(A, weights, rank, n_iter_max=100, tolerance=1e-8):
    return _results("weighted_parafac", A, weights, rank=rank, iterations=n_iter_max, tol=tolerance)


def tucker_ho_svd(A, ranks):
    return tucker(A, ranks)


def tucker_ho_oi(A, ranks, n_iter_max=100, tolerance=1e-8):
    return hooi(A, ranks, n_iter_max, tolerance)


parafac_reconstruct = reconstruct_cp
tucker_reconstruct = reconstruct_tucker
