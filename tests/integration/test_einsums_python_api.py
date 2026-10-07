"""API implementation checks. These fixtures are not SymSan campaign evidence."""

from __future__ import annotations

import gc
import importlib
import subprocess
import sys
from pathlib import Path

import h5py
import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module", params=["rust", "cpp20"])
def api(request):
    language = request.param
    if language == "rust":
        port = ROOT / "ports/einsums-rs"
        subprocess.run(
            [
                "cargo",
                "build",
                "--locked",
                "--offline",
                "--manifest-path",
                str(port / "Cargo.toml"),
            ],
            check=True,
            capture_output=True,
        )
        directory, stem = port / "target/debug", "libsage_einsums"
    else:
        port = ROOT / "ports/einsums-cpp"
        subprocess.run(
            ["cmake", "-S", str(port), "-B", str(port / "build"), "-DCMAKE_BUILD_TYPE=Release"],
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["cmake", "--build", str(port / "build"), "-j", "2"],
            check=True,
            capture_output=True,
        )
        directory, stem = port / "build", "libsage_einsums_cpp"
    # Both wheels intentionally expose the same import names. Keep each backend
    # isolated so tests cannot accidentally execute the previously loaded port.
    previous = {
        name: module
        for name, module in list(sys.modules.items())
        if name.split(".")[0] in {"einsums", "pyeinsums"}
    }
    for name in previous:
        del sys.modules[name]
    sys.path.insert(0, str(port / "python"))
    try:
        module = importlib.import_module("pyeinsums")
        # Select this exact tested build and verify backend identity.
        import ctypes

        from pyeinsums import _backend

        name = stem + (".dylib" if sys.platform == "darwin" else ".so")
        library = ctypes.PyDLL(str(directory / name))
        library.sage_api_request.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        library.sage_api_request.restype = ctypes.c_void_p
        library.sage_api_free.argtypes = [ctypes.c_void_p]
        library.sage_api_free.restype = None
        _backend._library = library
        assert Path(module.__file__).is_relative_to(port)
        yield module
    finally:
        sys.path.remove(str(port / "python"))
        for name in list(sys.modules):
            if name.split(".")[0] in {"einsums", "pyeinsums"}:
                del sys.modules[name]
        sys.modules.update(previous)


DTYPES = [np.float32, np.float64, np.complex64, np.complex128]


def close(a, b, dtype):
    low = np.dtype(dtype) in (np.dtype("float32"), np.dtype("complex64"))
    np.testing.assert_allclose(
        np.asarray(a), np.asarray(b), atol=2e-5 if low else 1e-10, rtol=2e-4 if low else 1e-9
    )


def matrix(dtype):
    a = np.array([[1, 2, -1], [3, -2, 1], [1, 0, 4]], dtype=dtype)
    if np.issubdtype(dtype, np.complexfloating):
        a += np.array([[0, 1, 2], [2, 0, -1], [-1, 2, 0]], dtype=dtype) * 1j
    return a


@pytest.mark.parametrize("dtype", DTYPES)
def test_views_ownership_buffers_and_casting(api, dtype):
    a = api.utils.create_tensor(np.arange(24).reshape(2, 3, 4), dtype=dtype)
    view = a[1, :, ::2]
    view *= 2
    expected = np.arange(24).reshape(2, 3, 4).astype(dtype)
    expected[1, :, ::2] *= 2
    close(a, expected, dtype)
    shared = np.asarray(view)
    del a
    gc.collect()
    view[0, 0] = 99
    assert shared[0, 0] == 99
    assert memoryview(view).shape == (3, 2)
    snapshot = view.copy()
    view.zero()
    assert snapshot[0, 0] == 99
    assert not np.shares_memory(snapshot, view)
    readonly = np.asarray(snapshot)
    readonly.flags.writeable = False
    with pytest.raises(ValueError, match="read-only"):
        api.core.scale(2, readonly)


@pytest.mark.parametrize("dtype", DTYPES)
def test_lu_qr_svd_eigen_residuals(api, dtype):
    a = matrix(dtype)
    packed = a.copy()
    pivots = api.core.getrf(packed)
    p, lower, u = api.core.extract_plu(packed, pivots)
    close(np.asarray(p) @ a, np.asarray(lower) @ np.asarray(u), dtype)
    api.core.getri(packed, pivots)
    close(a @ packed, np.eye(3), dtype)
    assert api.core.det(a) == pytest.approx(np.linalg.det(a), rel=2e-4, abs=1e-9)
    for value in (a, a[:2, :], a[:, :2]):
        packed, tau = api.core.qr(value)
        q, r = api.core.q(packed, tau), api.core.r(packed, tau)
        close(np.asarray(q) @ np.asarray(r), value, dtype)
        close(np.asarray(q).conj().T @ np.asarray(q), np.eye(min(value.shape)), dtype)
        u, s, vh = api.core.svd(value)
        k = min(value.shape)
        close(np.asarray(u)[:, :k] @ np.diag(np.asarray(s)) @ np.asarray(vh)[:k], value, dtype)
        close(np.asarray(u).conj().T @ np.asarray(u), np.eye(value.shape[0]), dtype)
        close(np.asarray(vh) @ np.asarray(vh).conj().T, np.eye(value.shape[1]), dtype)
    hermitian = a @ a.conj().T
    w = np.empty(3, dtype=np.empty((), dtype=dtype).real.dtype)
    v = hermitian.copy()
    api.core.syev("V", v, w)
    close(hermitian @ v.T, v.T * w, dtype)
    close(w, np.linalg.eigvalsh(hermitian), dtype)
    wdtype = (
        np.complex64 if np.dtype(dtype).itemsize in (4,) or dtype == np.complex64 else np.complex128
    )
    w = np.empty(3, dtype=wdtype)
    left = np.empty((3, 3), dtype=wdtype)
    right = np.empty_like(left)
    api.core.geev("V", "V", a.copy(), w, left, right)
    close(a @ right, right * w, dtype)
    close(a.conj().T @ left, left * w.conj(), dtype)


@pytest.mark.parametrize("dtype", DTYPES)
def test_solve_pseudoinverse_nullspace_and_lyapunov(api, dtype):
    a = matrix(dtype)
    b = np.array([[1, 2], [2, 3], [4, 5]], dtype=dtype)
    aa, x = a.copy(), b.copy()
    api.core.gesv(aa, x)
    close(a @ x, b, dtype)
    rank_deficient = a[:2, :]
    pinv = np.asarray(api.core.pseudoinverse(rank_deficient, 1e-6))
    close(rank_deficient @ pinv @ rank_deficient, rank_deficient, dtype)
    close(pinv @ rank_deficient @ pinv, pinv, dtype)
    null = np.asarray(api.core.svd_nullspace(rank_deficient))
    assert null.shape == (3, 1)
    close(rank_deficient @ null, np.zeros((2, 1)), dtype)
    q = a @ a.conj().T + np.eye(3, dtype=dtype)
    x = np.asarray(api.core.solve_continuous_lyapunov(q, a))
    close(q @ x + x @ q.conj().T, a, dtype)
    singular = np.zeros((2, 2), dtype=dtype)
    with pytest.raises(RuntimeError):
        api.core.invert(singular)
    close(singular, np.zeros((2, 2)), dtype)


@pytest.mark.parametrize("dtype", DTYPES)
def test_contraction_and_output_aliases(api, dtype):
    a = api.utils.create_tensor(matrix(dtype), dtype=dtype)
    original = np.asarray(a).copy()
    plan = api.core.compile_plan("ij", "ik", "kj")
    plan.execute(0, a, 1, a, a)
    close(a, original @ original, dtype)
    scalar = np.zeros((), dtype=dtype)
    api.core.compile_plan("", "ii", "").execute(0, scalar, 1, a, np.array(1, dtype=dtype))
    close(scalar, np.trace(np.asarray(a)), dtype)
    output = np.zeros((3, 6), dtype=dtype)
    api.core.gemm("N", "C", 2, original, original, 0, output[:, ::2])
    close(output[:, ::2], 2 * original @ original.conj().T, dtype)
    close(output[:, 1::2], np.zeros((3, 3)), dtype)
    invalid = output.copy()
    with pytest.raises(ValueError):
        api.core.compile_plan("ij", "ik", "kj").execute(0, output, 1, original, original)
    close(output, invalid, dtype)


@pytest.mark.parametrize("dtype", DTYPES)
def test_fft_decompositions_and_storage(api, dtype, tmp_path):
    a = matrix(dtype)
    x = a[0].copy()
    close(api.fft.fft(x), np.fft.fft(x), dtype)
    close(api.fft.ifft(api.fft.fft(x)), x * len(x), dtype)
    real = x.real.copy()
    close(api.fft.irfft(api.fft.rfft(real), n=len(real)), real * len(real), dtype)
    tensor = np.arange(24).reshape(2, 3, 4).astype(dtype)
    core, factors = api.decomposition.tucker(tensor, [2, 3, 4])
    close(api.decomposition.reconstruct_tucker(core, factors), tensor, dtype)
    tiled = api.storage.TiledTensor("tiles", [[1, 2], [2, 1]], dtype=dtype)
    tiled[0, 0] = a[:1, :2]
    tiled[1, 1] = a[1:, 2:]
    expected = np.zeros((3, 3), dtype=dtype)
    expected[:1, :2], expected[1:, 2:] = a[:1, :2], a[1:, 2:]
    close(tiled.to_dense(), expected, dtype)
    block = api.storage.BlockTensor("blocks", [1, 2], dtype=dtype)
    block[0], block[1] = a[:1, :1], a[1:, 1:]
    expected = np.zeros((3, 3), dtype=dtype)
    expected[:1, :1], expected[1:, 1:] = a[:1, :1], a[1:, 1:]
    close(block.to_dense(), expected, dtype)
    path = tmp_path / "tensor.h5"
    api.io.write(path, "array", a)
    with h5py.File(path, "r+") as file:
        close(file["array"][:], a, dtype)
        file.create_dataset("foreign", data=tensor)
    close(api.io.read(path, "foreign"), tensor, dtype)
    with api.io.DiskTensor(path, "array") as disk:
        disk[0, 0] = 7
    with h5py.File(path, "r") as file:
        assert file["array"][0, 0] == 7
    with pytest.raises(OSError):
        api.io.write(path, "array", a)


def test_ieee_roundtrip_and_runtime(api):
    a = api.utils.create_tensor(np.array([np.nan, np.inf, -np.inf, -0.0]))
    copy = np.asarray(a.copy())
    assert np.isnan(copy[0]) and np.isposinf(copy[1]) and np.isneginf(copy[2])
    assert np.signbit(copy[3])
    value = api.utils.create_tensor(np.array([1.0, -1.0, 0.0])) / 0.0
    assert np.isposinf(value[0]) and np.isneginf(value[1]) and np.isnan(value[2])
    config = api.core.GlobalConfigMap.get_singleton()
    config.set_str("test-option", "value")
    assert config.get_str("test-option") == "value"
    with api.core.Section("API test"):
        pass
    assert api.core.Section.records["API test"][1] >= 1
    assert not api.core.gpu_enabled()


@pytest.mark.parametrize("dtype", DTYPES)
def test_decomposition_truncation_empty_and_compressed_io(api, dtype, tmp_path):
    from pyeinsums import _backend

    factors = [
        np.array([[1], [2], [3]], dtype=dtype),
        np.array([[1], [-2]], dtype=dtype),
        np.array([[2], [1]], dtype=dtype),
    ]
    if np.issubdtype(dtype, np.complexfloating):
        factors[0] *= 1 + 0.5j
    a = np.einsum("ir,jr,kr->ijk", *factors)
    cp = api.decomposition.parafac(a, 1)
    close(api.decomposition.parafac_reconstruct(cp), a, dtype)
    weights = np.array([1, 0, 2], dtype=dtype)
    weighted = api.decomposition.weight_tensor(a, weights)
    close(weighted, a * weights[:, None, None], dtype)
    cp = api.decomposition.weighted_parafac(a, weights, 1)
    close(
        api.decomposition.weight_tensor(api.decomposition.reconstruct_cp(cp), weights),
        weighted,
        dtype,
    )
    core, basis = api.decomposition.tucker_ho_oi(a, [1, 1, 1])
    close(api.decomposition.tucker_reconstruct(core, basis), a, dtype)
    for shape in ((0, 3), (3, 0)):
        u, s, vh = api.core.svd(np.empty(shape, dtype=dtype))
        close(np.asarray(u).conj().T @ np.asarray(u), np.eye(shape[0]), dtype)
        close(np.asarray(vh) @ np.asarray(vh).conj().T, np.eye(shape[1]), dtype)
        assert np.asarray(s).shape == (0,)
    h = matrix(dtype)
    h = h @ h.conj().T
    v, w = api.core.truncated_syev(h, 1)
    close(h @ np.asarray(v), np.asarray(v) * np.asarray(w), dtype)
    u, s, vh = api.core.truncated_svd(h, 1)
    close(h @ np.asarray(vh).conj().T, np.asarray(u) * np.asarray(s), dtype)
    with pytest.raises(ValueError):
        api.decomposition.hooi(a, [1, 1, 1], tolerance=-1)
    with pytest.raises(ValueError):
        _backend.call("svd_nullspace", h, tol=-1)
    definite = api.utils.create_random_definite("negative", 5, mean=-2, dtype=dtype)
    assert np.linalg.eigvalsh(np.asarray(definite)).max() < 0
    semidefinite = api.utils.create_random_semidefinite("semi", 5, force_zeros=2, dtype=dtype)
    values = np.linalg.eigvalsh(np.asarray(semidefinite))
    close(values[:2], np.zeros(2), dtype)
    path = tmp_path / "compressed.h5"
    bigendian = np.dtype(dtype).newbyteorder(">")
    with h5py.File(path, "w") as f:
        f.create_dataset("nested/tensor", data=a.astype(bigendian), compression="gzip")
    close(api.io.read(path, "nested/tensor"), a, dtype)
    import einsums.core.errors
    import einsums.decomposition

    assert einsums.core.errors is api.core.errors


def test_pinned_export_surface_and_star_imports(api):
    import json

    surface = json.loads((ROOT / "ports/einsums-rs/api-surface.json").read_text())
    for module, names in surface["cpu_python_exports"].items():
        namespace = {}
        exec(f"from einsums.{module} import *", namespace)
        assert set(names) <= namespace.keys()
        assert all(hasattr(getattr(api, module), name) for name in names)


def test_cpp_numpy_comparison_interop(api):
    if "einsums-cpp" not in str(api.__file__):
        pytest.skip("C++ NumPy interoperability regression")
    value = api.utils.create_tensor(np.array([[1.0, 2.0], [3.0, 4.0]]))
    np.testing.assert_allclose(value, np.array([[1.0, 2.0], [3.0, 4.0]]))
    mask = np.isclose(value, value)
    assert np.asarray(mask).dtype == np.bool_
    assert bool(mask[()].all())


@pytest.mark.parametrize("width", [10, 50])
@pytest.mark.parametrize("dtype", [np.float64, np.complex128])
def test_cpp_larger_nonunique_factorization_residuals(api, width, dtype):
    if "einsums-cpp" not in str(api.__file__):
        pytest.skip("C++ factorization regression")
    rng = np.random.default_rng(771)
    a = rng.normal(size=(width, width)).astype(dtype)
    if dtype == np.complex128:
        a += 1j * rng.normal(size=a.shape)
    values = np.empty(width, dtype=np.complex128)
    left, right = np.empty_like(a, dtype=np.complex128), np.empty_like(a, dtype=np.complex128)
    api.core.geev("V", "V", a.copy(), values, left, right)
    scale = max(np.linalg.norm(a), 1)
    assert np.linalg.norm(a @ right - right * values) / scale < 1e-10
    assert np.linalg.norm(a.conj().T @ left - left * values.conj()) / scale < 1e-10
    rectangular = a[:-2, :]
    u, s, vh = map(np.asarray, api.core.svd(rectangular))
    k = len(s)
    close(u[:, :k] @ np.diag(s) @ vh[:k], rectangular, dtype)
    close(u.conj().T @ u, np.eye(u.shape[1]), dtype)
    close(vh @ vh.conj().T, np.eye(vh.shape[0]), dtype)
    null = np.asarray(api.core.svd_nullspace(rectangular))
    assert np.linalg.norm(rectangular @ null) / scale < 1e-10
    close(null.conj().T @ null, np.eye(2), dtype)


@pytest.mark.parametrize("dtype", DTYPES)
def test_nonhermitian_lyapunov_and_repeated_eigenvalues(api, dtype):
    a = matrix(dtype) + np.eye(3, dtype=dtype) * 10
    q = matrix(dtype).T.copy()
    x = np.asarray(api.core.solve_continuous_lyapunov(a, q))
    close(a @ x + x @ a.conj().T, q, dtype)
    repeated = np.eye(3, dtype=dtype) * 2
    cdtype = api.utils.add_complex(dtype)
    w, left, right = (
        np.empty(3, dtype=cdtype),
        np.empty((3, 3), dtype=cdtype),
        np.empty((3, 3), dtype=cdtype),
    )
    api.core.geev("V", "V", repeated, w, left, right)
    close(w, [2, 2, 2], dtype)
    close(right.conj().T @ right, np.eye(3), dtype)
    close(left.conj().T @ left, np.eye(3), dtype)


@pytest.mark.parametrize("dtype", DTYPES)
def test_expanded_numerical_domains(api, dtype):
    """Deterministically generated larger/empty, scaled and rank-deficient inputs."""
    from pyeinsums import _backend

    rng = np.random.default_rng(77101)
    for m, k, n in [(1, 8, 3), (8, 5, 7), (0, 3, 2), (9, 9, 9)]:
        for exponent in (-12, 0, 12):
            a = np.ldexp(rng.uniform(-1, 1, (m, k)), exponent).astype(dtype)
            b = np.ldexp(rng.uniform(-1, 1, (k, n)), -exponent).astype(dtype)
            if np.issubdtype(dtype, np.complexfloating):
                a += 0.25j * a
                b -= 0.5j * b
            before_a, before_b = a.copy(), b.copy()
            close(_backend.result("matmul", a, b), a @ b, dtype)
            close(_backend.result("subtract", a, a), np.zeros_like(a), dtype)
            close(_backend.result("negate", a), -a, dtype)
            np.testing.assert_array_equal(a, before_a)
            np.testing.assert_array_equal(b, before_b)
    # Exact diagonal singular values avoid asserting nonunique bases.
    s = np.array([1, 0.125, 2**-10, 2**-20, 0, 0], dtype=np.empty((), dtype=dtype).real.dtype)
    source = np.diag(s).astype(dtype)
    u, actual, vh = api.core.svd(source)
    close(actual, s, dtype)
    close(np.asarray(u) @ np.diag(np.asarray(actual)) @ np.asarray(vh), source, dtype)
    for n in (1, 2, 3, 8, 31, 64):
        for d in (0.125, -2.0, 2**-20):
            close(_backend.result("fftfreq", n=n, d=d), np.fft.fftfreq(n, d), np.float64)
            close(_backend.result("rfftfreq", n=n, d=d), np.fft.rfftfreq(n, d), np.float64)


@pytest.mark.parametrize("dtype", DTYPES)
def test_real_pivot_ties_and_precision_extremes(api, dtype):
    real = np.empty((), dtype=dtype).real.dtype
    tiny = np.nextafter(real.type(0), real.type(1))
    huge = np.finfo(real).max
    for x, y in [(1, -1), (0, -0.0), (tiny, 0), (huge, huge / 2), (tiny, tiny * 2)]:
        source = np.array([[x], [y]], dtype=dtype)
        pivots = api.core.getrf(source)
        assert int(np.asarray(pivots)[0]) == (2 if abs(y) > abs(x) else 1)


def test_concurrent_native_json_ownership_and_errors(api):
    """CDLL releases the GIL, so requests actually overlap inside the native ports."""
    import ctypes
    import json
    from concurrent.futures import ThreadPoolExecutor

    from pyeinsums import _backend

    library = ctypes.CDLL(_backend._load()._name)
    library.sage_api_request.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    library.sage_api_request.restype = ctypes.c_void_p
    library.sage_api_free.argtypes = [ctypes.c_void_p]
    library.sage_api_free.restype = None
    assert library.sage_api_request(None, 1) is None
    library.sage_api_free(None)

    def request(payload):
        source = ctypes.create_string_buffer(payload)
        pointer = library.sage_api_request(source, len(payload))
        assert pointer
        # The returned allocation must survive destruction and reuse of input storage.
        del source
        gc.collect()
        try:
            return json.loads(ctypes.string_at(pointer))
        finally:
            library.sage_api_free(pointer)

    malformed = [
        b"",
        b"\xff",
        b"{}",
        b"null",
        b"{",
        b'{"op":"unknown"}',
        b'{"op":"copy","params":[]}',
        b'{"op":"zeros","params":{"shape":[-1]}}',
        b'{"op":"zeros","params":{"shape":[9223372036854775807,3]}}',
    ]
    for payload in malformed:
        assert "error" in request(payload)

    def worker(index):
        for attempt in range(24):
            a = np.eye(8) * (index + attempt + 1)
            payload = json.dumps(
                {"op": "matmul", "arrays": [_backend.encode(a), _backend.encode(a)]}
            ).encode()
            response = request(payload)
            result = _backend.decode(response["ok"]["arrays"][0])
            np.testing.assert_array_equal(result, a @ a)
            assert "error" in request(b'{"op":"matmul","arrays":[]}')
        return index

    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sorted(pool.map(worker, range(8))) == list(range(8))


def test_shared_c_abi_consumer_against_each_backend(api, tmp_path):
    import ctypes
    import shutil

    from pyeinsums import _backend

    include = tmp_path / "include/sage-einsums"
    include.mkdir(parents=True)
    shutil.copy2(ROOT / "ports/einsums-cpp/sage_api.h", include / "sage_api.h")
    library = Path(_backend._load()._name)
    executable = tmp_path / "c-consumer"
    subprocess.run(
        [
            "cc",
            "-std=c11",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-UNDEBUG",
            "-I",
            str(include.parent),
            str(ROOT / "ports/einsums-cpp/c_consumer_tests.c"),
            str(library),
            f"-Wl,-rpath,{library.parent}",
            "-o",
            str(executable),
        ],
        capture_output=True,
        check=True,
    )
    subprocess.run([str(executable)], capture_output=True, check=True)
    # Verify the selected backend remains callable after a separate consumer process.
    assert ctypes.CDLL(str(library)).sage_api_request


@pytest.mark.parametrize(
    "operation,arity",
    [
        ("copy", 1),
        ("permute", 1),
        ("scale", 1),
        ("negate", 1),
        ("add", 2),
        ("subtract", 2),
        ("multiply", 2),
        ("divide", 2),
        ("matmul", 2),
    ],
)
def test_normalized_adapter_arity(api, operation, arity):
    from pyeinsums import _backend

    value = np.ones((2, 2))
    for n in (arity - 1, arity + 1):
        with pytest.raises(ValueError, match="wrong number"):
            _backend.call(operation, *[value] * n)
