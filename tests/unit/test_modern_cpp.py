from __future__ import annotations

import json
import subprocess
from dataclasses import replace
from pathlib import Path

import pytest
from typer.testing import CliRunner

from sage.cli import app
from sage.config import load_config
from sage.einsums.cpp_library_runtime import EinsumsCppLibraryRun
from sage.einsums.cpp_runtime import EinsumsCppRun
from sage.einsums.library_runtime import create_run
from sage.verification.einsums_cpp import ModernCppProofRun

ROOT = Path(__file__).resolve().parents[2]


def test_cpp_dispatch_preserves_rust_default_and_accepts_cpu_library(tmp_path: Path) -> None:
    config = load_config(ROOT / "configs/einsums-cpp.yaml")
    config = replace(config, runs_dir=str(tmp_path))
    assert isinstance(create_run(config, ROOT), EinsumsCppRun)
    assert load_config(ROOT / "configs/einsums.yaml").provider.target_language == "rust"
    assert isinstance(
        create_run(
            replace(
                config,
                equivalence=replace(config.equivalence, policy_version="einsums-library-1.0"),
            ),
            ROOT,
        ),
        EinsumsCppLibraryRun,
    )
    with pytest.raises(ValueError, match="tensor or library policy"):
        create_run(
            replace(config, equivalence=replace(config.equivalence, policy_version="unknown")), ROOT
        )
    with pytest.raises(ValueError, match="unsupported target language"):
        create_run(
            replace(config, provider=replace(config.provider, target_language="invalid")), ROOT
        )
    with pytest.raises(ValueError, match="offline translation"):
        create_run(config, ROOT, provider_name="openai")


def test_cpp_proof_missing_sources_cannot_succeed(tmp_path: Path) -> None:
    output = ModernCppProofRun(tmp_path, tmp_path / "proof").run()
    manifest = json.loads((output / "manifest.json").read_text())
    assert manifest["status"] == "INCONCLUSIVE"
    assert "error" in manifest


def test_cpp_proof_requires_both_relations_and_pairwise_assertion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    run = ModernCppProofRun(tmp_path, tmp_path)
    descriptions = [
        "upstream output bits match specification",
        "candidate output bits match specification",
        "paired output bits match exactly",
    ]

    def response() -> subprocess.CompletedProcess[str]:
        output = [
            {"result": [{"description": d, "status": "SUCCESS"} for d in descriptions]},
            {"cProverStatus": "success"},
        ]
        return subprocess.CompletedProcess([], 0, json.dumps(output), "")

    monkeypatch.setattr(run, "command", lambda *args: response())
    assert run.check(tmp_path / "unused.cpp", "test")["status"] == "PROVED"
    descriptions.pop()
    assert run.check(tmp_path / "unused.cpp", "test")["status"] == "INCONCLUSIVE"
    descriptions[:] = ["paired output bits match exactly"]
    assert run.check(tmp_path / "unused.cpp", "test")["status"] == "INCONCLUSIVE"


def test_cli_rejects_unrecognized_proof_language() -> None:
    result = CliRunner().invoke(app, ["prove", "--language", "fortran"])
    assert result.exit_code != 0
    assert "language must be rust or cpp20" in result.output
