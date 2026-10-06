from __future__ import annotations

import itertools
import json
import subprocess
from pathlib import Path

import pytest

from sage.builders.cpp_candidate import CppCandidateBuilder
from sage.einsums.domain import TensorCase

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="module")
def cpp_candidate(tmp_path_factory: pytest.TempPathFactory) -> Path:
    build = tmp_path_factory.mktemp("cpp20")
    result = CppCandidateBuilder().build(ROOT / "ports/einsums-cpp/driver.cpp", build)
    assert result.success, result.log_path.read_text()
    assert result.binary is not None
    return result.binary


def test_all_bounded_shapes_and_operations(cpp_candidate: Path, tmp_path: Path) -> None:
    """Native implementation checks, separate from generated campaign evidence."""
    patterns = [
        bytes(32),
        bytes([128, 255, 0, 1, 127, 8, 248, 64] * 4),
        bytes((i * 73 + 19) % 256 for i in range(32)),
    ]
    path = tmp_path / "input.bin"
    for op, m, k, n, data in itertools.product(
        range(6), range(1, 5), range(1, 5), range(1, 5), patterns
    ):
        payload = bytes([op, m, k, n]) + data
        case = TensorCase.from_binary(payload, "native-contract-test")
        path.write_bytes(payload)
        result = subprocess.run([str(cpp_candidate), str(path)], capture_output=True, check=True)
        # In this dyadic domain all six operations are exactly representable.
        assert json.loads(result.stdout) == case.reference(), payload.hex()


def test_decoder_rejects_invalid_input(cpp_candidate: Path, tmp_path: Path) -> None:
    path = tmp_path / "invalid.bin"
    for payload in (
        b"",
        bytes(35),
        bytes(37),
        bytes(36),
        bytes([6, 1, 1, 1]) + bytes(32),
        bytes([0, 1, 1, 5]) + bytes(32),
    ):
        path.write_bytes(payload)
        result = subprocess.run([str(cpp_candidate), str(path)], capture_output=True)
        assert result.returncode == 65
        assert not result.stdout
    assert subprocess.run([str(cpp_candidate)], capture_output=True).returncode == 64
    assert (
        subprocess.run([str(cpp_candidate), str(path / "missing")], capture_output=True).returncode
        == 65
    )


def test_public_tensor_contract_under_sanitizers(tmp_path: Path) -> None:
    binary = tmp_path / "tensor-tests"
    subprocess.run(
        [
            "clang++",
            "-std=c++20",
            "-O1",
            "-g",
            "-Wall",
            "-Wextra",
            "-Werror",
            "-ffp-contract=off",
            "-fsanitize=address,undefined",
            "-fno-omit-frame-pointer",
            str(ROOT / "ports/einsums-cpp/tests.cpp"),
            "-o",
            str(binary),
        ],
        capture_output=True,
        check=True,
    )
    subprocess.run([str(binary)], capture_output=True, check=True)
