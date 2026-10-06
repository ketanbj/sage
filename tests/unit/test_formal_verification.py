from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from sage.cli import app
from sage.verification.einsums import (
    EXPECTED_HARNESSES,
    ProofRun,
    cbmc_result,
    extract_scalar,
    kani_result,
    normalize_ir,
    specialize_scalar,
)


def cbmc_output(status: str = "SUCCESS") -> str:
    return json.dumps(
        [
            {
                "result": [
                    {
                        "property": "main.assertion.1",
                        "status": status,
                        "description": "output bits match specification",
                    }
                ]
            },
            {"cProverStatus": "success" if status == "SUCCESS" else "failure"},
        ]
    )


def test_cbmc_proof_requires_assertions_and_solver_completion() -> None:
    assert cbmc_result(cbmc_output(), 0)["status"] == "PROVED"
    assert cbmc_result("[]", 0)["status"] == "INCONCLUSIVE"
    assert cbmc_result("not JSON", 0)["status"] == "INCONCLUSIVE"
    for malformed in ("{}", "[0]", '[{"result": [0]}]', '[{"result": null}]'):
        assert cbmc_result(malformed, 0)["status"] == "INCONCLUSIVE"
    assert cbmc_result(cbmc_output(), 124)["status"] == "INCONCLUSIVE"
    assert cbmc_result(cbmc_output("UNKNOWN"), 0)["status"] == "INCONCLUSIVE"
    assert cbmc_result(cbmc_output("FAILURE"), 10)["status"] == "DISPROVED"
    assert cbmc_result(cbmc_output("FAILURE"), 1)["status"] == "INCONCLUSIVE"


def test_kani_requires_the_complete_expected_scope() -> None:
    text = (
        "\n".join(
            f"Checking harness {name}...\nVERIFICATION:- SUCCESSFUL"
            for name in sorted(EXPECTED_HARNESSES)
        )
        + "\nComplete - 32 successfully verified harnesses, 0 failures, 32 total."
    )
    assert kani_result(text, 0)["status"] == "PROVED"
    assert kani_result(text, 1)["status"] == "INCONCLUSIVE"
    assert (
        kani_result(text.replace("transpose_4x4", "wrong_harness"), 0)["status"] == "INCONCLUSIVE"
    )
    assert kani_result(text.replace("32 total", "31 total"), 0)["status"] == "INCONCLUSIVE"
    assert (
        kani_result(text.replace("VERIFICATION:- SUCCESSFUL", "", 1), 0)["status"] == "INCONCLUSIVE"
    )


def test_compiler_identity_retains_semantic_differences() -> None:
    original = '; ModuleID = "a"\nsource_filename = "a"\ndefine @kernel { ret i32 0 }'
    renamed = '; ModuleID = "b"\nsource_filename = "b"\ndefine @kernel { ret i32 0 }'
    assert normalize_ir(original) == normalize_ir(renamed)
    assert normalize_ir(original) != normalize_ir(renamed.replace("i32 0", "i32 1"))


def test_extraction_rejects_ambiguous_source() -> None:
    block = (
        "template <bool betaIsZero, typename floatType, bool conjA>\n"
        "static INLINE void macro_kernel_scalar() { if constexpr (betaIsZero) {} }\n"
    )
    source = block + "\ntemplate <int blockingA, int blockingB>"
    assert extract_scalar(source) == block
    with pytest.raises(ValueError):
        extract_scalar(source + source)
    with pytest.raises(ValueError):
        specialize_scalar(block.replace("if constexpr", "if"))


def test_existing_proof_bundle_is_preserved(tmp_path: Path) -> None:
    destination = tmp_path / "existing"
    destination.mkdir()
    sentinel = destination / "manifest.json"
    sentinel.write_text("original")
    with pytest.raises(FileExistsError):
        ProofRun(tmp_path, destination).run()
    assert sentinel.read_text() == "original"


def test_missing_tools_leave_an_inconclusive_bundle(tmp_path: Path) -> None:
    output = tmp_path / "proof"
    assert ProofRun(tmp_path, output).run() == output
    report = json.loads((output / "manifest.json").read_text())
    assert report["status"] == "INCONCLUSIVE"
    assert "error" in report
    assert "No proof result yet" in (output / "report.md").read_text()


def test_cli_rejects_unknown_proof_targets() -> None:
    result = CliRunner().invoke(app, ["prove", "--target", "dkh"])
    assert result.exit_code != 0
    assert "supports only einsums" in result.output
