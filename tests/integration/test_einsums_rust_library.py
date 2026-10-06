from __future__ import annotations

import ctypes
import gc
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from sage.einsums.library_domain import bootstrap_seeds

ROOT = Path(__file__).resolve().parents[2]


def test_rust_crate_and_python_abi(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Implementation integration test; bootstrap inputs are not campaign evidence."""
    subprocess.run(
        [
            "cargo",
            "build",
            "--locked",
            "--offline",
            "--manifest-path",
            str(ROOT / "ports/einsums-rs/Cargo.toml"),
            "--target-dir",
            str(tmp_path),
        ],
        check=True,
        capture_output=True,
    )
    name = "libsage_einsums.dylib" if sys.platform == "darwin" else "libsage_einsums.so"
    library = ctypes.CDLL(str(tmp_path / "debug" / name))
    call = library.sage_einsums_execute
    call.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t]
    call.restype = ctypes.c_ssize_t
    for case in bootstrap_seeds():
        source = ctypes.create_string_buffer(case.payload)
        output = ctypes.create_string_buffer(16384)
        size = call(source, len(case.payload), output, len(output))
        assert size > 0
        observed = json.loads(output.raw[:size])
        expected = case.reference()
        assert observed["shape"] == expected["shape"]
        np.testing.assert_allclose(observed["values"], expected["values"], atol=1e-10, rtol=1e-9)
    assert call(None, 36, output, len(output)) == -1
    assert call(source, 35, output, len(output)) == -1
    assert call(source, 36, output, 1) == -2

    monkeypatch.syspath_prepend(str(ROOT / "ports/einsums-rs/python"))
    from einsums_rs import Library

    api = Library(tmp_path / "debug" / name)
    a = api.tensor([2, 3, 4], range(24))
    np.testing.assert_array_equal(
        np.asarray(a.permute([2, 0, 1])), np.arange(24).reshape(2, 3, 4).transpose(2, 0, 1)
    )
    a[-1, -1, -1] = 100
    assert a[1, 2, 3] == 100
    with pytest.raises(IndexError):
        a[2, 0, 0] = 1
    assert a[1, 2, 3] == 100
    with pytest.raises(ValueError):
        a.reshape([5, 5])
    with pytest.raises(ValueError):
        api.tensor([-1])
    matrix = api.tensor([2, 2], [0, 2, 1, 3])
    rhs = api.tensor([2, 1], [4, 7])
    solution = matrix.solve(rhs)
    del matrix, rhs
    gc.collect()
    np.testing.assert_allclose(np.asarray(solution), [[1], [2]])
    assert api.tensor([], [3])[()] == 3
    assert np.asarray(api.tensor([0, 3])).shape == (0, 3)
    v = api.tensor([2], [2, 3])
    np.testing.assert_allclose(np.asarray(v.einsum("i", v, "j", "ij")), [[4, 6], [6, 9]])
    assert v.dot(v) == 13
    with pytest.raises(ValueError, match="Singular"):
        api.tensor([2, 2]).inverse()
    with pytest.raises(TypeError):
        v + Library(tmp_path / "debug" / name).tensor([2], [1, 1])

    # Exercise the same Python entrypoint used by generated campaigns. These are
    # implementation fixtures only; no manifest counts them as SymSan evidence.
    from run_case import execute

    for case in bootstrap_seeds():
        observed = execute(api, case.payload)
        expected = case.reference()
        assert observed["shape"] == expected["shape"]
        assert observed["strides"] == expected["strides"]
        np.testing.assert_allclose(observed["values"], expected["values"], atol=1e-10, rtol=1e-9)
