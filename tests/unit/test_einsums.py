from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from sage.config import load_config
from sage.domain import ExecutionResult, Outcome
from sage.einsums.domain import TensorCase, bootstrap_seeds
from sage.einsums.library_runtime import create_run
from sage.einsums.policy import TensorPolicy
from sage.einsums.runtime import EinsumsRun
from sage.generators.symsan import SymSanGenerator
from sage.targets.registry import load_run_class

ROOT = Path(__file__).resolve().parents[2]


def test_einsums_dispatch_and_config_are_target_specific() -> None:
    config = load_config(ROOT / "configs/einsums.yaml")
    assert config.target is not None and config.target.name == "einsums"
    assert load_run_class("einsums") is create_run
    assert config.symsan.enabled and not config.symsan.trace_only


@pytest.mark.parametrize(
    "payload",
    [b"", bytes(36), bytes(37), bytes([6, 1, 1, 1]) + bytes(32), bytes([0, 5, 1, 1]) + bytes(32)],
)
def test_invalid_tensor_inputs_are_rejected(payload: bytes) -> None:
    with pytest.raises(ValueError):
        TensorCase.from_binary(payload, "bad")


def test_rectangular_transpose_and_contraction() -> None:
    values = bytes([8, 16, 24, 32, 40, 48] + [0] * 10 + [8, 16, 24, 32, 40, 48] + [0] * 10)
    case = TensorCase.from_binary(bytes([3, 2, 3, 2]) + values, "transpose")
    assert case.reference() == {
        "shape": [[3, 2]],
        "strides": [[2, 1]],
        "values": [[1.0, 4.0], [2.0, 5.0], [3.0, 6.0]],
    }
    case.payload = bytes([4, 2, 3, 2]) + values
    assert case.reference()["values"] == [[22.0, 28.0], [49.0, 64.0]]


def execution(output: dict) -> ExecutionResult:
    return ExecutionResult("1.0", "test", "case", 0, 0, False, "", "", output, {})


def test_policy_catches_layout_numeric_and_reference_errors() -> None:
    case = bootstrap_seeds()[3]
    expected = case.reference()
    policy = TensorPolicy(1e-12, 1e-10)
    assert policy.compare(case, execution(expected), execution(expected)).outcome == Outcome.PASS
    bad = {**expected, "strides": [[1, 3]]}
    assert (
        policy.compare(case, execution(expected), execution(bad)).outcome
        == Outcome.STRUCTURAL_DIFFERENCE
    )
    bad = {**expected, "values": [[x + 1 for x in row] for row in expected["values"]]}
    assert (
        policy.compare(case, execution(expected), execution(bad)).outcome
        == Outcome.NUMERICAL_DIFFERENCE
    )
    assert (
        policy.compare(case, execution(bad), execution(bad)).outcome
        == Outcome.REFERENCE_DISAGREEMENT
    )
    bad = {**expected, "values": [[float("nan") for x in row] for row in expected["values"]]}
    assert policy.compare(case, execution(expected), execution(bad)).outcome != Outcome.PASS


def test_symsan_import_excludes_seeds_duplicates_and_invalid_bytes(tmp_path: Path) -> None:
    config = load_config(ROOT / "configs/einsums.yaml")
    generated = tmp_path / "corpus/generated"
    generated.mkdir(parents=True)
    seed = tmp_path / "seed.bin"
    seed.write_bytes(bootstrap_seeds()[0].payload)
    new = bytearray(seed.read_bytes())
    new[1] = 3
    for name, payload in [
        ("seed", seed.read_bytes()),
        ("new", new),
        ("duplicate", new),
        ("bad", b"bad"),
    ]:
        (generated / f"symsan-{name}.bin").write_bytes(payload)
    generator = SymSanGenerator(
        config.symsan, tmp_path / "traces", [seed], run_dir=tmp_path, decoder=TensorCase.from_binary
    )
    cases, invalid = generator._import_generated()
    assert len(cases) == 1 and invalid == 1
    assert cases[0].to_binary() == new
    assert cases[0].provenance["origin"] == "symsan"


@pytest.mark.parametrize("enabled,trace_only", [(False, False), (True, True)])
def test_einsums_refuses_non_generating_campaign_without_docker(
    tmp_path: Path,
    enabled: bool,
    trace_only: bool,
) -> None:
    config = load_config(ROOT / "configs/einsums.yaml")
    config = replace(
        config,
        runs_dir=str(tmp_path),
        symsan=replace(config.symsan, enabled=enabled, trace_only=trace_only),
    )
    run = EinsumsRun(config, ROOT)
    manifest = json.loads((run.run() / "manifest.json").read_text())
    assert manifest["status"] == "UNSUPPORTED"
    assert manifest["test_counts_by_origin"] == {"symsan": 0}
    assert manifest["outcome_counts"] == {}


@pytest.mark.parametrize(
    "exit_status,expected", [(0, "COMPLETED"), (256, "INFRASTRUCTURE_FAILURE")]
)
def test_failed_instrumented_trace_never_reports_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    exit_status: int,
    expected: str,
) -> None:
    import subprocess

    config = load_config(ROOT / "configs/einsums.yaml")
    (tmp_path / "corpus/generated").mkdir(parents=True)
    seed = tmp_path / "seed.bin"
    seed.write_bytes(bootstrap_seeds()[0].payload)
    changed = bytearray(seed.read_bytes())
    changed[1] = 3
    (tmp_path / "corpus/generated/symsan-output.bin").write_bytes(changed)
    binary = tmp_path / "instrumented"
    binary.touch()
    monkeypatch.setattr(
        "sage.generators.symsan.subprocess.run",
        lambda *a, **kw: subprocess.CompletedProcess(a, 0),
    )
    events = json.dumps(
        {"event": "trace_complete", "seed": 0, "exit_status": exit_status, "killed": False}
    ).encode()
    monkeypatch.setattr(SymSanGenerator, "_invoke", lambda *a: ("COMPLETED", "", events))
    generator = SymSanGenerator(
        config.symsan, tmp_path / "traces", [seed], binary, tmp_path, decoder=TensorCase.from_binary
    )
    assert len(generator.generate()) == 1
    assert generator.outcome["status"] == expected
    assert generator.outcome["trace_bounds"] is False


def test_reference_timeout_removes_daemon_owned_container(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import subprocess

    config = replace(load_config(ROOT / "configs/einsums.yaml"), runs_dir=str(tmp_path))
    run = EinsumsRun(config, ROOT)
    run.rust_binary = tmp_path / "unused-rust"
    case = bootstrap_seeds()[0]
    calls = []

    def invoke(command, **kwargs):
        calls.append(command)
        if command[:2] == ["docker", "run"]:
            raise subprocess.TimeoutExpired(command, 1)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr("sage.einsums.runtime.subprocess.run", invoke)
    monkeypatch.setattr(
        "sage.einsums.runtime.SandboxedRunner.execute",
        lambda *args: execution(case.reference()),
    )
    observed, _ = run._execute(case, run.run_dir / "corpus/generated/input.bin")
    assert observed[0].timed_out
    assert calls[1][:3] == ["docker", "rm", "-f"]
    assert calls[1][3] == calls[0][calls[0].index("--name") + 1]
