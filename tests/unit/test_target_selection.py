from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from sage.cli import app
from sage.targets.catalog import ASSESSMENT_FIELDS, CandidateCatalog, CandidateState
from sage.targets.selection import load_selection_decision, read_selection_status

ROOT = Path(__file__).resolve().parents[2]


def test_catalog_contains_candidates_with_complete_assessment_shape() -> None:
    candidates = CandidateCatalog(ROOT / "candidates").list()
    by_id = {candidate.candidate_id: candidate for candidate in candidates}
    assert {"gau2grid", "dkh", "gdma", "einsums", "template"} <= by_id.keys()
    assert "psi4-module" not in by_id
    assert by_id["gau2grid"].state == CandidateState.PROPOSED
    assert by_id["dkh"].state == CandidateState.PROPOSED
    assert by_id["einsums"].state == CandidateState.UNDER_ASSESSMENT
    for candidate in candidates:
        assert set(candidate.to_dict()["assessment"]) == set(ASSESSMENT_FIELDS)


def test_retired_psi4_placeholder_resolves_to_einsums() -> None:
    candidate = CandidateCatalog(ROOT / "candidates").get("psi4-module")
    assert candidate.candidate_id == "einsums"
    assert "complete pinned Einsums" in (candidate.assessment.proposed_translation_unit or "")


def test_no_target_is_selected_by_default(tmp_path: Path) -> None:
    assert read_selection_status(tmp_path / "missing.json") == {
        "schema_version": "1.0",
        "selected_target": None,
        "status": "NO_SELECTION",
    }


def test_draft_selection_is_not_approval() -> None:
    with pytest.raises(ValueError, match="APPROVED"):
        load_selection_decision(ROOT / "decisions" / "selection-template.yaml")


def test_approved_selection_is_target_bound(tmp_path: Path) -> None:
    decision = tmp_path / "approved.yaml"
    decision.write_text(
        """schema_version: '1.0'
decision_kind: target-selection
decision_id: test-human-decision
target: dkh
status: APPROVED
approved_by: Test Approver
approved_at: '2026-09-02T00:00:00Z'
rationale: Test-only approval fixture.
evidence: [test-fixture]
""",
        encoding="utf-8",
    )
    loaded = load_selection_decision(decision, expected_target="dkh")
    assert loaded.target == "dkh"
    with pytest.raises(ValueError, match="not 'gdma'"):
        load_selection_decision(decision, expected_target="gdma")


@pytest.mark.parametrize("target", ["dkh", "einsums"])
def test_scientific_pilot_rejects_missing_approval(target: str) -> None:
    result = CliRunner().invoke(
        app,
        ["run", "--target", target, "--mode", "scientific-pilot", "--provider", "offline"],
    )
    assert result.exit_code == 2
    assert "requires --selection" in result.output


@pytest.mark.parametrize(
    "command", [["run", "--target", "gau2grid"], ["target", "prepare", "--target", "gau2grid"]]
)
def test_potential_target_has_no_executable_profile(command: list[str]) -> None:
    result = CliRunner().invoke(app, command)
    assert result.exit_code != 0
    assert "no platform-demo configuration" in result.output
    assert CandidateCatalog(ROOT / "candidates").get("gau2grid").state == CandidateState.PROPOSED
