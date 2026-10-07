from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from sage.verification.extended import ASSERTIONS, ExtendedProofRun

ROOT = Path(__file__).resolve().parents[2]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / f"tools/verification/{name}.py")
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_extended_obligations_include_complete_larger_layout_grid():
    assert len(ASSERTIONS) == 69
    assert {name for name in ASSERTIONS if name.startswith("layout_")} == {
        f"layout_{m}x{k}" for m in range(1, 9) for k in range(1, 9)
    }


def test_extended_missing_sources_fail_closed(tmp_path):
    destination = tmp_path / "proof"
    ExtendedProofRun(tmp_path, destination, language="rust").run()
    assert json.loads((destination / "manifest.json").read_text())["status"] == "INCONCLUSIVE"
    with pytest.raises(FileExistsError):
        ExtendedProofRun(tmp_path, destination, language="rust").run()


def test_residual_disagreements_are_not_classified_as_benign_basis_changes():
    classifier = module("classify_disagreements")
    record = {
        "outcome": "REFERENCE_DISAGREEMENT",
        "operation": "geev",
        "original": {"passed": False, "message": "output 1 numerical disagreement"},
        "rust_python": {"passed": True},
    }
    assert classifier.classify(record) == "NUMERICAL_RESIDUAL_UNRESOLVED"
    record["operation"] = "new_operation"
    assert classifier.classify(record) == "UNCLASSIFIED"
    record["rust_python"]["passed"] = False
    with pytest.raises(ValueError):
        classifier.classify(record)


def test_path_decoder_rejects_invalid_inputs_and_nonfinite_pivots():
    import struct

    experiment = module("explore_library_paths")
    for payload in (
        b"",
        bytes(20),
        bytes([0, 64, 64, 0]) + bytes(16),
        bytes([1, 0, 0, 0]) + struct.pack("<dd", float("nan"), 1),
    ):
        with pytest.raises(ValueError):
            experiment.expectation(payload)
    assert experiment.expectation(bytes([1, 0, 0, 0]) + struct.pack("<dd", -3, 2)) == 1
    assert experiment.expectation(bytes([2, 0, 0, 0]) + struct.pack("<dd", -0.0, 0)) == 0
    assert experiment.expectation(bytes([0, 5, 3, 0]) + bytes(16)) == -2
