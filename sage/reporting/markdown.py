from __future__ import annotations

from pathlib import Path
from typing import Any


def render_markdown(
    manifest: dict[str, Any], comparisons: list[dict[str, Any]], advisory: dict[str, Any]
) -> str:
    origins = manifest.get("test_counts_by_origin", {})
    outcomes = manifest.get("outcome_counts", {})
    build_records = manifest.get("build_records", {})
    c_implementation = build_records.get("c_reference", {}).get("implementation", "unknown")
    candidate = build_records.get("cpp_candidate", build_records.get("rust_candidate", {}))
    candidate_implementation = candidate.get("implementation", "unknown")
    candidate_language = "C++20" if "cpp_candidate" in build_records else "Rust"
    discrepancies = [item for item in comparisons if item["outcome"] != "PASS"]
    lines = [
        "# SAGE behavioral validation report",
        "",
        f"Run: `{manifest['run_id']}`  ",
        f"Status: `{manifest['status']}`  ",
        f"Target: `{manifest.get('target_candidate', 'legacy-unknown')}`  ",
        f"Mode: `{manifest.get('run_mode', 'platform-demo')}`  ",
        "Selection decision: "
        f"`{(manifest.get('selection_decision') or {}).get('decision_id', 'none')}`  ",
        f"Policy: `{manifest['equivalence_policy_version']}`",
        "",
        "> This report is structured evidence over the recorded domain. It is not formal",
        "> verification and does not establish universal program equivalence.",
        "",
        "## Evidence summary",
        "",
        "| Outcome | Count |",
        "|---|---:|",
    ]
    lines.extend(f"| {name} | {count} |" for name, count in sorted(outcomes.items()))
    lines.extend(["", "## Test-domain origins", "", "| Origin | Count |", "|---|---:|"])
    lines.extend(f"| {name} | {count} |" for name, count in sorted(origins.items()))
    concolic = manifest.get("concolic_outcome", {})
    lines.extend(
        [
            "",
            "Input origins above describe the recorded evidence. In SymSan-only campaigns,",
            "bootstrap seeds are not validation cases; zero generated cases means no evidence.",
            "",
            "## SymSan-assisted exploration",
            "",
            f"Status: `{concolic.get('status', 'not-recorded')}`  ",
            f"Generated valid cases: `{concolic.get('generated', 0)}`  ",
            f"Invalid generated payloads: `{concolic.get('invalid_generated', 0)}`  ",
            f"Reason: {concolic.get('reason') or 'none'}",
            "",
            "## Confirmed discrepancies",
            "",
        ]
    )
    if discrepancies:
        lines.extend(
            f"- `{item['case_id']}`: **{item['outcome']}** — replay artifact recorded"
            for item in discrepancies
        )
    else:
        lines.append(
            "No discrepancies were observed in the recorded cases."
            if comparisons
            else "No validation cases were executed; there is no behavioral evidence."
        )
    if concolic.get("operations"):
        lines.extend(
            ["", "## Executed tensor operations", "", "| Operation | Cases |", "|---|---:|"]
        )
        lines.extend(f"| {name} | {count} |" for name, count in concolic["operations"].items())
    lines.extend(["", "## Advisory interpretation", "", f"**Advisory:** {advisory['text']}"])
    lines.extend(["", "## Provenance", ""])
    for project, commit in sorted(manifest["commits"].items()):
        lines.append(f"- {project}: `{commit}`")
    lines.extend(
        [
            f"- Configuration SHA-256: `{manifest['config_sha256']}`",
            f"- Provider: `{manifest['translation_provider'].get('name', 'unknown')}`",
            f"- Random seeds: `{manifest['random_seeds']}`",
            f"- C/C++ reference build: `{c_implementation}`",
            f"- {candidate_language} candidate build: `{candidate_implementation}`",
            "",
            "## Untested and unsupported behavior",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in manifest.get("known_limitations", []))
    lines.extend(
        [
            "",
            "Raw machine-readable evidence is in `manifest.json`, `environment.json`,",
            "`comparisons.jsonl`, `executions/`, and `discrepancies/`.",
            "",
        ]
    )
    scope = concolic.get("library_coverage")
    if scope:
        lines.extend(
            [
                "## CPU/Python library scope",
                "",
                f"Status: `{scope['scope_status']}`. HIP/GPU backends are excluded.",
                "",
                "| Module | Translation status | Runtime files |",
                "|---|---|---:|",
            ]
        )
        for name, entry in scope["modules"].items():
            lines.append(f"| {name} | {entry['translation_status']} | {entry['runtime_files']} |")
        lines.extend(["", "Missing contracts:", ""])
        lines.extend(f"- {item}" for item in scope["missing_contracts"])
        lines.append("")
    return "\n".join(lines)


def write_markdown(
    path: Path,
    manifest: dict[str, Any],
    comparisons: list[dict[str, Any]],
    advisory: dict[str, Any],
) -> None:
    path.write_text(render_markdown(manifest, comparisons, advisory), encoding="utf-8")
