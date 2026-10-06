from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from sage.cli import app
from sage.verification.einsums import cbmc_result, kani_result
from sage.verification.tensor_six import (
    OBLIGATIONS,
    OPERATIONS,
    RELATION,
    TensorSixProofRun,
    lower_cpp,
    mutate_cpp,
    mutate_rust,
    name,
)

ROOT = Path(__file__).resolve().parents[2]


def test_six_scope_has_every_matrix_dimension_combination() -> None:
    assert len(OBLIGATIONS) == 144 and len({name(x) for x in OBLIGATIONS}) == 144
    for op in OPERATIONS:
        expected = {
            (m, k, n)
            for m in range(1, 5)
            for k in range(1, 5)
            for n in (range(1, 5) if op == "matmul" else [1])
        }
        assert {(m, k, n) for candidate, m, k, n in OBLIGATIONS if candidate == op} == expected


def test_expression_completion_rejects_missing_duplicate_or_failed_obligations() -> None:
    expected = {name(x) for x in OBLIGATIONS}
    log = "\n".join(f"Checking harness {x}...\nVERIFICATION:- SUCCESSFUL" for x in sorted(expected))
    log += "\nComplete - 144 successfully verified harnesses, 0 failures, 144 total."
    assert kani_result(log, 0, expected)["status"] == "PROVED"
    for changed in (
        log.replace("matmul_4x4x4", "wrong_name"),
        log + "\nChecking harness copy_1x1...",
        log.replace("144 total", "143 total"),
        log.replace("VERIFICATION:- SUCCESSFUL", "VERIFICATION:- FAILED", 1),
    ):
        assert kani_result(changed, 0, expected)["status"] == "INCONCLUSIVE"
    assert kani_result(log, 124, expected)["status"] == "INCONCLUSIVE"
    data = [
        {"result": [{"status": "SUCCESS", "description": RELATION}]},
        {"cProverStatus": "success"},
    ]
    assert cbmc_result(json.dumps(data), 0, RELATION)["status"] == "PROVED"
    data[0]["result"][0]["description"] = "bounds only"
    assert cbmc_result(json.dumps(data), 0, RELATION)["status"] == "INCONCLUSIVE"


def test_materialization_and_fault_controls_reject_source_drift() -> None:
    cpp = (ROOT / "ports/einsums-cpp/tensor.hpp").read_text()
    lowered = lower_cpp(cpp, "Code")
    assert "ExpressionArithmetic::multiply(at(r, k), other.at(k, c))" in lowered
    assert "ExpressionArithmetic::add(out.at(r, c)" in lowered
    assert "Scalar" not in lowered and "std::span<const" not in lowered
    with pytest.raises(ValueError):
        lower_cpp(cpp.replace("template<class Scalar> struct NativeArithmetic", "changed"), "Code")
    rust = (ROOT / "ports/einsums-rs/src/tensor.rs").read_text()
    kernel = (ROOT / "ports/einsums-cpp/kernels.hpp").read_text()
    for op in OPERATIONS:
        assert mutate_rust(rust, op) != rust
        source = kernel if op in ("copy", "transpose") else cpp
        assert mutate_cpp(source, op) != source
        with pytest.raises(ValueError):
            mutate_cpp("unrelated source", op)
        with pytest.raises(ValueError):
            mutate_rust("unrelated source", op)


def test_six_proof_is_fail_closed_when_setup_is_missing(tmp_path: Path) -> None:
    dest = tmp_path / "proof"
    TensorSixProofRun(tmp_path, dest, language="rust").run()
    assert json.loads((dest / "manifest.json").read_text())["status"] == "INCONCLUSIVE"
    with pytest.raises(FileExistsError):
        TensorSixProofRun(tmp_path, dest, language="rust").run()
    result = CliRunner().invoke(app, ["prove", "--profile", "wrong"])
    assert result.exit_code != 0 and "scalar or tensor-six" in result.output


def test_reuse_requires_identical_sources_and_complete_raw_results(tmp_path: Path) -> None:
    previous = tmp_path / "previous"
    destination = tmp_path / "new"
    previous.mkdir()
    destination.mkdir()
    hashes = {}
    from sage.verification.einsums import digest

    for filename in ("tensor_source.rs", "tensor.rs", "expression.rs"):
        content = f"exact input {filename}".encode()
        (previous / filename).write_bytes(content)
        (destination / filename).write_bytes(content)
        hashes[filename] = digest(content)
    log = "\n".join(
        f"Checking harness {name(x)}...\nVERIFICATION:- SUCCESSFUL" for x in OBLIGATIONS
    )
    log += "\nComplete - 144 successfully verified harnesses, 0 failures, 144 total."
    (previous / "rust-six.stdout").write_text(log)
    (previous / "rust-six.stderr").write_text("")
    manifest = {
        "target_language": "rust",
        "profile": "tensor-six",
        "tools": {"pinned": True},
        "source_hashes": hashes,
        "commands": [
            {"args": ["kani-driver", "tensor.rs", "--output-format", "terse"], "returncode": 0}
        ],
    }
    (previous / "manifest.json").write_text(json.dumps(manifest))
    runner = TensorSixProofRun(tmp_path, destination, language="rust", reuse_checks=previous)
    runner.manifest["tools"] = manifest["tools"]
    runner.reuse_method_checks()
    assert runner.manifest["rust_checks"]["status"] == "PROVED"
    (destination / "expression.rs").write_text("changed interpretation")
    with pytest.raises(ValueError, match="input differs"):
        runner.reuse_method_checks()
    (destination / "expression.rs").write_bytes((previous / "expression.rs").read_bytes())
    (previous / "rust-six.stdout").write_text(log.replace("matmul_4x4x4", "missing"))
    with pytest.raises(ValueError, match="incomplete"):
        runner.reuse_method_checks()
