from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Annotated, Any

import typer
import yaml

from sage.config import Config, load_config
from sage.core.orchestrator import SageRun
from sage.orchestrator import rerender_report
from sage.targets.catalog import CandidateCatalog
from sage.targets.registry import demo_config_path, load_target_adapter
from sage.targets.selection import (
    load_selection_decision,
    read_selection_status,
    record_selection,
)

app = typer.Typer(
    help="SAGE — Semantically Aligned Generation and Equivalence", no_args_is_help=True
)
target_app = typer.Typer(help="Scientific target candidates and selection", no_args_is_help=True)
app.add_typer(target_app, name="target")


@app.command()
def prove(
    target: Annotated[str, typer.Option("--target")] = "einsums",
    language: Annotated[str, typer.Option("--language")] = "rust",
    profile: Annotated[str, typer.Option("--profile")] = "scalar",
    reuse_checks: Annotated[Path | None, typer.Option("--reuse-checks")] = None,
    output: Annotated[Path | None, typer.Option("--output")] = None,
    jobs: Annotated[int, typer.Option("--jobs", min=1, max=8)] = 2,
    timeout: Annotated[int, typer.Option("--timeout", min=1)] = 1800,
) -> None:
    """Prove bounded scalar-kernel equivalence separately from validation campaigns."""
    from datetime import UTC, datetime

    from sage.verification.einsums import ProofRun

    if target != "einsums":
        raise typer.BadParameter("the current proof pilot supports only einsums")
    if language not in ("rust", "cpp20"):
        raise typer.BadParameter("language must be rust or cpp20")
    if profile not in ("scalar", "tensor-six"):
        raise typer.BadParameter("profile must be scalar or tensor-six")
    if reuse_checks and profile != "tensor-six":
        raise typer.BadParameter("--reuse-checks requires --profile tensor-six")
    destination = output or (
        project_root()
        / "runs"
        / (datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ") + f"-einsums-{language}-proof")
    )
    typer.echo(
        "Checking 144 public Tensor obligations and six fault controls."
        if profile == "tensor-six"
        else (
            "Checking 32 paired C++ obligations, then fault detection and replay."
            if language == "cpp20"
            else "Checking 32 C++ and 32 Rust obligations, then fault detection and replay."
        )
    )
    typer.echo(f"Proof bundle: {destination.resolve()}")
    try:
        runner: type[ProofRun] = ProofRun
        if language == "cpp20":
            from sage.verification.einsums_cpp import ModernCppProofRun

            runner = ModernCppProofRun
        if profile == "tensor-six":
            from sage.verification.tensor_six import TensorSixProofRun

            path = TensorSixProofRun(
                project_root(),
                destination,
                language=language,
                reuse_checks=reuse_checks,
                jobs=jobs,
                timeout=timeout,
            ).run()
        else:
            path = runner(project_root(), destination, jobs=jobs, timeout=timeout).run()
    except (OSError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    typer.echo(str(path))
    status = json.loads((path / "manifest.json").read_text())["status"]
    typer.echo(f"proof status: {status}")
    expected_status = (
        "BOUNDED_TENSOR_API_PROVED" if profile == "tensor-six" else "BOUNDED_EQUIVALENCE_PROVED"
    )
    if status != expected_status:
        raise typer.Exit(1)


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def catalog() -> CandidateCatalog:
    return CandidateCatalog(project_root() / "candidates")


def selection_state_path() -> Path:
    return project_root() / ".sage" / "selection.json"


def config_option(path: Path) -> Config:
    return load_config(path.resolve())


def available(command: str) -> tuple[bool, str]:
    executable = shutil.which(command)
    if not executable:
        return False, "not found"
    result = subprocess.run([executable, "--version"], capture_output=True, text=True, check=False)
    lines = (result.stdout or result.stderr).strip().splitlines()
    return True, lines[0] if lines else executable


def resolve_run_config(
    config_path: Path,
    target_name: str | None,
    *,
    mode: str | None = None,
    selection_path: Path | None = None,
) -> tuple[Config, str]:
    config = config_option(config_path)
    configured_target = config.target.name if config.target is not None else None
    resolved_target = target_name or configured_target
    if resolved_target is None:
        raise ValueError("no target selected; pass --target <candidate>")
    catalog().get(resolved_target)
    if mode == "scientific-pilot":
        if selection_path is None:
            raise ValueError(
                "scientific-pilot mode requires --selection with an approved human decision"
            )
        load_selection_decision(selection_path.resolve(), expected_target=resolved_target)
    if config.target is None:
        config = load_config(demo_config_path(project_root(), resolved_target))
    elif configured_target != resolved_target:
        raise ValueError(
            f"configuration targets {configured_target!r}, not requested {resolved_target!r}"
        )
    return config, resolved_target


def new_run(
    config: Path,
    target_name: str | None,
    mode: str,
    selection: Path | None,
    provider: str | None,
    seed: int | None,
    symsan: bool,
) -> SageRun:
    cfg, resolved_target = resolve_run_config(
        config, target_name, mode=mode, selection_path=selection
    )
    if symsan:
        cfg = replace(cfg, symsan=replace(cfg.symsan, enabled=True))
    return SageRun(
        cfg,
        project_root(),
        target_name=resolved_target,
        mode=mode,
        selection_path=selection,
        provider_name=provider,
        seed=seed,
    )


def render_json(value: Any) -> None:
    typer.echo(json.dumps(value, indent=2, sort_keys=True))


def print_run_result(path: Path) -> None:
    typer.echo(str(path))
    status = json.loads((path / "manifest.json").read_text())["status"]
    if status != "COMPLETED":
        typer.echo(f"validation status: {status}; inspect {path / 'report.md'}", err=True)
        raise typer.Exit(1)


@app.command()
def doctor(
    config: Annotated[Path, typer.Option("--config")] = Path("configs/sage.yaml"),
) -> None:
    """Check core tools and the required SymSan validation environment."""
    cfg = config_option(config)
    typer.echo(
        f"Python: {'OK' if sys.version_info >= (3, 11) else 'MISSING'} {platform.python_version()}"
    )
    core_ok = sys.version_info >= (3, 11)
    for command in ("uv", "git", "cc", "rustc"):
        ok, detail = available(command)
        core_ok = core_ok and ok
        typer.echo(f"{command}: {'OK' if ok else 'MISSING'} {detail}")
    docker_ok, docker_detail = available("docker")
    typer.echo(f"docker client: {'OK' if docker_ok else 'MISSING'} {docker_detail}")
    daemon = (
        subprocess.run(
            ["docker", "version", "--format", "{{json .Server}}"],
            capture_output=True,
            text=True,
            check=False,
        )
        if docker_ok
        else None
    )
    if daemon and daemon.returncode == 0 and daemon.stdout.strip() not in ("", "null"):
        server = json.loads(daemon.stdout)
        typer.echo(f"docker daemon: OK architecture={server.get('Arch', 'unknown')}")
        image = subprocess.run(
            ["docker", "image", "inspect", cfg.symsan.image], capture_output=True, check=False
        )
        typer.echo(
            f"SymSan image: {'OK' if image.returncode == 0 else 'MISSING'} {cfg.symsan.image}"
        )
        core_ok = core_ok and image.returncode == 0
    else:
        typer.echo("docker daemon / SymSan: UNAVAILABLE")
        core_ok = False
    typer.echo(f"SymSan pin: {cfg.symsan.upstream_commit}")
    selected_target = read_selection_status(selection_state_path())["selected_target"]
    typer.echo(f"scientific target selection: {selected_target}")
    if not core_ok:
        raise typer.Exit(1)


@target_app.command("list")
def target_list() -> None:
    """List candidates; catalog state is not an approval decision."""
    typer.echo("TARGET\tSTATE\tCONFIDENCE\tDESCRIPTION")
    for candidate in catalog().list():
        typer.echo(
            f"{candidate.candidate_id}\t{candidate.state.value}\t"
            f"{candidate.assessment.confidence}\t{candidate.description}"
        )


@target_app.command("show")
def target_show(target: str) -> None:
    render_json(catalog().get(target).to_dict())


@target_app.command("assess")
def target_assess(target: str) -> None:
    candidate = catalog().get(target)
    data = candidate.to_dict()
    assessment = data["assessment"]
    unresolved = [
        key
        for key, value in assessment.items()
        if value is None or value == [] or value == "NOT_ASSESSED"
    ]
    render_json(
        {
            "record_kind": "candidate-assessment",
            "candidate": candidate.candidate_id,
            "state": candidate.state.value,
            "assessment": assessment,
            "unresolved_fields": unresolved,
            "selection_effect": "NONE",
        }
    )


@target_app.command("compare")
def target_compare(targets: Annotated[list[str], typer.Argument()]) -> None:
    """Show recorded fields side by side without ranking or recommending candidates."""
    if not targets:
        raise typer.BadParameter("provide at least one target candidate")
    typer.echo("TARGET\tSTATE\tCONFIDENCE\tTRANSLATION UNIT\tBUILD\tSYMSAN")
    for target in targets:
        candidate = catalog().get(target)
        assessment = candidate.assessment
        typer.echo(
            "\t".join(
                [
                    candidate.candidate_id,
                    candidate.state.value,
                    assessment.confidence,
                    assessment.proposed_translation_unit or "UNKNOWN",
                    assessment.build_complexity or "UNKNOWN",
                    assessment.symsan_compatibility or "UNKNOWN",
                ]
            )
        )
    typer.echo("No ranking or recommendation is implied; unknown fields require stakeholder input.")


@target_app.command("selection-status")
def target_selection_status() -> None:
    render_json(read_selection_status(selection_state_path()))


@target_app.command("select")
def target_select(
    target: str,
    decision: Annotated[Path, typer.Option("--decision")],
) -> None:
    try:
        approved = record_selection(decision.resolve(), selection_state_path(), catalog(), target)
    except (OSError, ValueError, yaml.YAMLError) as exc:
        typer.echo(f"selection rejected: {exc}", err=True)
        raise typer.Exit(2) from exc
    render_json(
        {
            "status": "SELECTED",
            "target": target,
            "decision_id": approved.decision_id,
            "decision_sha256": approved.sha256,
        }
    )


@target_app.command("prepare")
def target_prepare(
    config: Annotated[Path, typer.Option("--config")] = Path("configs/sage.yaml"),
    target: Annotated[str | None, typer.Option("--target")] = None,
) -> None:
    try:
        cfg, resolved_target = resolve_run_config(config, target)
        assert cfg.target is not None
        destination = (
            project_root() / ".sage" / "upstreams" / resolved_target / cfg.target.upstream_commit
        )
        result = load_target_adapter(resolved_target).prepare(cfg, destination)
    except (OSError, subprocess.SubprocessError, RuntimeError, ValueError) as exc:
        typer.echo(f"prepare failed: {exc}", err=True)
        raise typer.Exit(1) from exc
    render_json(result)


@app.command()
def translate(
    config: Annotated[Path, typer.Option("--config")] = Path("configs/sage.yaml"),
    target: Annotated[str | None, typer.Option("--target")] = None,
    provider: Annotated[str | None, typer.Option("--provider")] = None,
) -> None:
    try:
        output = new_run(config, target, "platform-demo", None, provider, None, False).translate()
    except ValueError as exc:
        typer.echo(f"translation rejected: {exc}", err=True)
        raise typer.Exit(2) from exc
    typer.echo(str(output))


@app.command("generate-tests")
def generate_tests(
    config: Annotated[Path, typer.Option("--config")] = Path("configs/sage.yaml"),
    target: Annotated[str | None, typer.Option("--target")] = None,
    seed: Annotated[int | None, typer.Option("--seed")] = None,
    symsan: Annotated[bool, typer.Option("--symsan")] = False,
) -> None:
    try:
        run = new_run(config, target, "platform-demo", None, "offline", seed, symsan)
    except ValueError as exc:
        typer.echo(f"test generation rejected: {exc}", err=True)
        raise typer.Exit(2) from exc
    cases, adapter = run.generate_tests()
    render_json({"run": str(run.run_dir), "cases": len(cases), "symsan": adapter.outcome})
    if not cases or adapter.outcome.get("status") != "COMPLETED":
        raise typer.Exit(1)


@app.command()
def validate(
    config: Annotated[Path, typer.Option("--config")] = Path("configs/sage.yaml"),
    target: Annotated[str | None, typer.Option("--target")] = None,
    provider: Annotated[str | None, typer.Option("--provider")] = None,
    seed: Annotated[int | None, typer.Option("--seed")] = None,
) -> None:
    try:
        result = new_run(config, target, "platform-demo", None, provider, seed, False).run()
    except ValueError as exc:
        typer.echo(f"validation rejected: {exc}", err=True)
        raise typer.Exit(2) from exc
    print_run_result(result)


@app.command("run")
def run_command(
    config: Annotated[Path, typer.Option("--config")] = Path("configs/sage.yaml"),
    target: Annotated[str | None, typer.Option("--target")] = None,
    mode: Annotated[str, typer.Option("--mode")] = "platform-demo",
    selection: Annotated[Path | None, typer.Option("--selection")] = None,
    provider: Annotated[str | None, typer.Option("--provider")] = None,
    seed: Annotated[int | None, typer.Option("--seed")] = None,
    symsan: Annotated[bool, typer.Option("--symsan")] = False,
) -> None:
    try:
        result = new_run(config, target, mode, selection, provider, seed, symsan).run()
    except (OSError, ValueError, yaml.YAMLError) as exc:
        typer.echo(f"run rejected: {exc}", err=True)
        raise typer.Exit(2) from exc
    print_run_result(result)


@app.command()
def report(run: Annotated[Path, typer.Option("--run")]) -> None:
    md_path, html_path = rerender_report(run.resolve())
    typer.echo(f"{md_path}\n{html_path}")


@app.command()
def reproduce(discrepancy: Path) -> None:
    """Replay a saved target discrepancy."""
    discrepancy = discrepancy.resolve()
    run_dir = discrepancy.parent.parent
    cfg = load_config(run_dir / "config.resolved.yaml")
    if cfg.target is not None and cfg.target.name == "einsums":
        from sage.einsums.runtime import reproduce as reproduce_einsums

        render_json(reproduce_einsums(discrepancy))
        return
    typer.echo("reproduce supports only implemented Einsums targets", err=True)
    raise typer.Exit(2)


@app.command()
def clean(run: Annotated[str, typer.Option("--run")]) -> None:
    """Delete exactly one run directory after strict containment checks."""
    runs_root = (project_root() / "runs").resolve()
    target = Path(run)
    if not target.is_absolute() and len(target.parts) == 1:
        target = runs_root / target
    target = target.resolve()
    if target.parent != runs_root or not (target / "manifest.json").is_file():
        typer.echo("refusing to clean: target is not exactly one SAGE run", err=True)
        raise typer.Exit(2)
    shutil.rmtree(target)
    typer.echo(f"removed {target} (not recoverable by SAGE)")


if __name__ == "__main__":
    app()
