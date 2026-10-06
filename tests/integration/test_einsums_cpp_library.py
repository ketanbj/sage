"""Independent CPU-library checks; these fixtures are not campaign evidence."""

from __future__ import annotations

import itertools
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from sage.einsums.library_domain import LibraryCase

ROOT = Path(__file__).resolve().parents[2]
PORT = ROOT / "ports/einsums-cpp"


@pytest.fixture(scope="module")
def library_binary() -> Path:
    build = PORT / "build"
    subprocess.run(
        ["cmake", "-S", str(PORT), "-B", str(build), "-DCMAKE_BUILD_TYPE=Release"],
        capture_output=True,
        check=True,
    )
    subprocess.run(["cmake", "--build", str(build), "-j", "2"], capture_output=True, check=True)
    return build / "einsums-cpp-library-candidate"


def check(actual, expected):
    assert actual["shape"] == expected["shape"]
    assert actual["strides"] == expected["strides"]
    np.testing.assert_allclose(actual["values"], expected["values"], atol=1e-10, rtol=1e-9)


def test_library_operations_against_numpy(library_binary, tmp_path):
    patterns = [
        bytes(32),
        bytes([128, 255, 0, 1, 127, 8, 248, 64] * 4),
        bytes((i * 73 + 19) % 256 for i in range(32)),
    ]
    path = tmp_path / "input.bin"
    for op, m, k, n, data in itertools.product(
        range(23), range(1, 5), range(1, 5), range(1, 5), patterns
    ):
        payload = bytes([op, m, k, n]) + data
        case = LibraryCase.from_binary(payload, "native-cpp20-library")
        path.write_bytes(payload)
        result = subprocess.run([str(library_binary), str(path)], capture_output=True, check=True)
        check(json.loads(result.stdout), case.reference())


def test_python_campaign_entrypoints_use_cpp(library_binary, tmp_path):
    suffix = ".dylib" if sys.platform == "darwin" else ".so"
    env = {
        **os.environ,
        "EINSUMS_CPP_LIBRARY": str(library_binary.parent / ("libsage_einsums_cpp" + suffix)),
    }
    path = tmp_path / "input.bin"
    for op, shape in itertools.product(range(23), [(1, 1, 1), (2, 3, 4), (4, 2, 3)]):
        payload = bytes([op, *shape]) + bytes((i * 73 + 19) % 256 for i in range(32))
        path.write_bytes(payload)
        result = subprocess.run(
            [sys.executable, str(PORT / "python/run_case.py"), str(path)],
            env=env,
            capture_output=True,
            check=True,
        )
        check(
            json.loads(result.stdout),
            LibraryCase.from_binary(payload, "native-python-cpp20").reference(),
        )


def test_library_decoder_errors(library_binary, tmp_path):
    path = tmp_path / "bad.bin"
    for payload in [b"", bytes(35), bytes(37), bytes([23, 1, 1, 1]) + bytes(32), bytes(36)]:
        path.write_bytes(payload)
        result = subprocess.run([str(library_binary), str(path)], capture_output=True)
        assert result.returncode == 65
        assert not result.stdout


def test_full_native_api_under_sanitizers(tmp_path):
    build = tmp_path / "sanitized"
    flags = "-fsanitize=address,undefined -fno-omit-frame-pointer"
    subprocess.run(
        [
            "cmake",
            "-S",
            str(PORT),
            "-B",
            str(build),
            "-DCMAKE_BUILD_TYPE=RelWithDebInfo",
            f"-DCMAKE_CXX_FLAGS={flags}",
            f"-DCMAKE_EXE_LINKER_FLAGS={flags}",
            f"-DCMAKE_SHARED_LINKER_FLAGS={flags}",
        ],
        capture_output=True,
        check=True,
    )
    subprocess.run(["cmake", "--build", str(build), "-j", "2"], capture_output=True, check=True)
    subprocess.run(
        ["ctest", "--test-dir", str(build), "--output-on-failure"], capture_output=True, check=True
    )
