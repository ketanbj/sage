from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from sage.config import load_config
from sage.domain import sha256_file
from sage.einsums.inventory import coverage, inventory
from sage.einsums.library_domain import OPERATIONS, LibraryCase, bootstrap_seeds
from sage.einsums.library_runtime import EinsumsLibraryRun, create_run
from sage.einsums.runtime import EinsumsRun
from sage.orchestrator import rerender_report
from sage.targets.einsums import EINSUMS_COMMIT

ROOT = Path(__file__).resolve().parents[2]


def test_dispatch_preserves_existing_tensor_profile(tmp_path: Path) -> None:
    for profile, cls in [("einsums.yaml", EinsumsRun), ("einsums-library.yaml", EinsumsLibraryRun)]:
        cfg = replace(load_config(ROOT / "configs" / profile), runs_dir=str(tmp_path))
        assert type(create_run(cfg, ROOT)) is cls


def test_library_protocol_handles_all_operations_and_rejects_bad_inputs() -> None:
    seeds = bootstrap_seeds()
    assert len(seeds) == len(OPERATIONS) == 23
    for seed in seeds:
        assert seed.to_dict()["operation"] in OPERATIONS
        output = seed.reference()
        assert len(output["values"]) == output["shape"][0][0]
        assert len(output["values"][0]) == output["shape"][0][1]
    with pytest.raises(ValueError):
        LibraryCase.from_binary(bytes([23, 1, 1, 1]) + bytes(32), "bad")


def test_inventory_includes_unknown_modules_and_hashes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    files = [
        "libs/Einsums/NewModule/include/New.hpp",
        "libs/Einsums/GPUMemory/src/Device.hip",
        "pyeinsums/__init__.py",
        "CMakeLists.txt",
    ]
    for name in files:
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("// test\n")

    def git(args, **kwargs):
        if "rev-parse" in args:
            return EINSUMS_COMMIT + "\n"
        if "status" in args:
            return ""
        return ("\0".join(files) + "\0").encode()

    monkeypatch.setattr("sage.einsums.inventory.subprocess.check_output", git)
    result = inventory(tmp_path)
    assert len(result["files"]) == len(files)
    assert "Einsums/NewModule" in result["modules"]
    assert result["files"][0]["sha256"] == sha256_file(tmp_path / result["files"][0]["path"])
    report = coverage(result, {}, {"PASS": 100})
    assert report["whole_library_complete"] is False
    assert report["modules"]["Einsums/GPUMemory"]["translation_status"] == "EXCLUDED_GPU"
    assert report["modules"]["Einsums/NewModule"]["translation_status"] == "NOT_IMPLEMENTED"


def test_full_scope_cannot_pass_with_only_api_probes(tmp_path: Path) -> None:
    cfg = replace(load_config(ROOT / "configs/einsums-library.yaml"), runs_dir=str(tmp_path))
    run = EinsumsLibraryRun(cfg, ROOT)
    run.source_inventory = {
        "modules": {
            "Einsums/Tensor": {"runtime_files": 1, "probe_operations": ["copy"]},
            "Python/package": {"runtime_files": 1, "probe_operations": []},
        }
    }
    run.manifest.status = "COMPLETED"
    run.manifest.outcome_counts = {"PASS": 10}
    run.manifest.concolic_outcome = {"operations": {"copy": 10}}
    path = run._finish([])
    assert json.loads((path / "manifest.json").read_text())["status"] == "INCOMPLETE_SCOPE"
    markdown, _ = rerender_report(path)
    assert "CPU/Python library scope" in markdown.read_text()
    assert "Python/package" in markdown.read_text()


def test_cpp_coverage_uses_cpp_paths_and_keeps_conservative_gate():
    source = {
        "modules": {
            "Einsums/LinearAlgebra": {"runtime_files": 1, "probe_operations": ["inverse"]},
            "Einsums/BLASVendor": {"runtime_files": 1, "probe_operations": []},
            "Einsums/NewModule": {"runtime_files": 1, "probe_operations": []},
        }
    }
    report = coverage(source, {"inverse": 5}, {"PASS": 5}, target_language="cpp20")
    assert "api/linalg.cpp" in report["modules"]["Einsums/LinearAlgebra"]["implementation"]
    assert report["modules"]["Einsums/BLASVendor"]["translation_status"].startswith("REPLACED_")
    assert report["modules"]["Einsums/NewModule"]["translation_status"] == "NOT_IMPLEMENTED"
    assert report["scope_status"] == "INCOMPLETE_SCOPE"
    assert report["whole_library_complete"] is False
