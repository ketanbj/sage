from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from sage.cli import app


@pytest.mark.parametrize(
    "status,exit_code",
    [
        ("COMPLETED", 0),
        ("NO_TEST_CASES", 1),
        ("INFRASTRUCTURE_FAILURE", 1),
        ("TIMEOUT", 1),
        ("COMPLETED_WITH_DISCREPANCIES", 1),
    ],
)
def test_cli_exit_matches_evidence_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, status: str, exit_code: int
) -> None:
    (tmp_path / "manifest.json").write_text(json.dumps({"status": status}))
    monkeypatch.setattr("sage.cli.new_run", lambda *a, **kw: SimpleNamespace(run=lambda: tmp_path))
    result = CliRunner().invoke(app, ["run", "--target", "einsums"])
    assert result.exit_code == exit_code
    assert str(tmp_path) in result.output
