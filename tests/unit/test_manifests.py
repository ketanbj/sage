from __future__ import annotations

import json
from pathlib import Path

import yaml

from sage.config import load_config
from sage.manifests import load_manifest

ROOT = Path(__file__).resolve().parents[2]


def test_default_configuration_has_no_target() -> None:
    config = load_config(ROOT / "configs" / "sage.yaml")
    assert config.schema_version == "1.1"
    assert config.target is None


def test_schema_10_records_get_target_and_mode_defaults(tmp_path: Path) -> None:
    raw = yaml.safe_load((ROOT / "configs/einsums.yaml").read_text())
    raw["schema_version"] = "1.0"
    raw["target"].update(angular_momenta=[], derivatives=[], representations=[], cartesian_order="")
    config_path = tmp_path / "config.resolved.yaml"
    config_path.write_text(yaml.safe_dump(raw))
    assert load_config(config_path).target == load_config(ROOT / "configs/einsums.yaml").target
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "commits": {"sage": "recorded-commit", "einsums": "pin"},
            }
        ),
        encoding="utf-8",
    )
    manifest = load_manifest(path)
    assert manifest["commits"]["sage"] == "recorded-commit"
    assert manifest["target_candidate"] == "einsums"
    assert manifest["run_mode"] == "platform-demo"
    assert manifest["selection_decision"] is None


def test_einsums_manifest_can_be_rerendered(tmp_path: Path) -> None:
    from dataclasses import replace

    from sage.einsums.runtime import EinsumsRun
    from sage.orchestrator import rerender_report

    config = load_config(ROOT / "configs/einsums.yaml")
    config = replace(config, runs_dir=str(tmp_path), symsan=replace(config.symsan, enabled=False))
    run = EinsumsRun(config, ROOT).run()
    markdown, html = rerender_report(run)
    assert "Target: `einsums`" in markdown.read_text()
    assert "Status: `UNSUPPORTED`" in markdown.read_text()
    assert html.is_file()
