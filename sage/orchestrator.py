"""Target-independent report loading and rendering."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sage.manifests import load_manifest
from sage.reporting.html import write_html
from sage.reporting.markdown import render_markdown
from sage.summarizers.offline import OfflineSummarizer


def load_comparisons(run_dir: Path) -> list[dict[str, Any]]:
    path = run_dir / "comparisons.jsonl"
    return (
        [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
        if path.exists()
        else []
    )


def rerender_report(run_dir: Path) -> tuple[Path, Path]:
    manifest = load_manifest(run_dir / "manifest.json")
    comparisons = load_comparisons(run_dir)
    advisory_path = run_dir / "advisory-summary.json"
    advisory = (
        json.loads(advisory_path.read_text(encoding="utf-8"))
        if advisory_path.exists()
        else OfflineSummarizer().summarize({"outcomes": manifest.get("outcome_counts", {})})
    )
    markdown = render_markdown(manifest, comparisons, advisory)
    md_path = run_dir / "report.md"
    html_path = run_dir / "report.html"
    md_path.write_text(markdown, encoding="utf-8")
    write_html(html_path, markdown)
    return md_path, html_path
