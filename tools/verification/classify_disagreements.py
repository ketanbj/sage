"""Classify recorded observations without changing campaign outcomes or waiving failures."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path


def classify(record: dict) -> str:
    if record.get("outcome") != "REFERENCE_DISAGREEMENT":
        raise ValueError("only reference disagreements can be classified")
    original = record.get("original", {})
    candidates = [v for k, v in record.items() if k.endswith("_python")]
    if (
        original.get("passed") is not False
        or len(candidates) != 1
        or candidates[0].get("passed") is not True
    ):
        raise ValueError("reference-disagreement evidence is inconsistent")
    op, message = record["operation"], original.get("message", "")
    if op == "pseudoinverse" and message.startswith("output 0 shape/dtype:"):
        return "REFERENCE_SHAPE_DEFECT"
    if op == "solve_continuous_lyapunov":
        if "ctrsyl not implemented" in message:
            return "REFERENCE_BACKEND_UNSUPPORTED"
        if "Can not create RuntimeTensorView" in message:
            return "REFERENCE_WRAPPER_UNSUPPORTED"
    if op == "svd_nullspace" and message.startswith("output 0 shape/dtype:"):
        return "RANK_POLICY_DIFFERENCE"
    if op in ("truncated_svd", "truncated_syev") and "numerical disagreement" in message:
        return "APPROXIMATION_CONTRACT_DIFFERENCE"
    if op in ("lu", "geev", "pseudoinverse") and "numerical disagreement" in message:
        return "NUMERICAL_RESIDUAL_UNRESOLVED"
    return "UNCLASSIFIED"


def summarize(run: Path) -> dict:
    source = run / "comparisons.jsonl"
    manifest = run / "manifest.json"
    records = [json.loads(line) for line in source.read_text().splitlines()]
    if not records:
        raise ValueError("empty replay")
    identities = [(r["case_id"], r["operation"], r["dtype"]) for r in records]
    if len(set(identities)) != len(identities):
        raise ValueError("duplicate comparison identities")
    disagreements = [r for r in records if r["outcome"] == "REFERENCE_DISAGREEMENT"]
    groups = collections.Counter((r["operation"], classify(r)) for r in disagreements)
    expected = json.loads(manifest.read_text())["outcomes"]
    observed = dict(collections.Counter(r["outcome"] for r in records))
    if expected != observed:
        raise ValueError("manifest and comparison counts differ")
    return {
        "run": run.name,
        "comparisons_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "original_outcomes": observed,
        "classified": len(disagreements),
        "unclassified": sum(n for (_, c), n in groups.items() if c == "UNCLASSIFIED"),
        "unresolved_numerical": sum(
            n for (_, c), n in groups.items() if c == "NUMERICAL_RESIDUAL_UNRESOLVED"
        ),
        "groups": [
            {"operation": op, "classification": c, "count": n}
            for (op, c), n in sorted(groups.items())
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = {
        "contract": "corrected-cpu-semantics-1",
        "status": "CLASSIFIED_WITH_UNRESOLVED_FINDINGS",
        "claim": (
            "Observation classification only; no new proof, outcome "
            "rewriting or compatibility waiver."
        ),
        "classifier_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "runs": [summarize(r) for r in args.run],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    return 1 if any(r["unclassified"] for r in report["runs"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
