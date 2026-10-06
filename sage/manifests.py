from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_manifest(path: Path) -> dict[str, Any]:
    """Read supported run manifests and supply target/mode defaults."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_version") not in {"1.0", "1.1"}:
        raise ValueError("unsupported run manifest schema")
    commits = raw.setdefault("commits", {})
    if "target_candidate" not in raw:
        raw["target_candidate"] = "einsums" if "einsums" in commits else None
    raw.setdefault("run_mode", "platform-demo")
    raw.setdefault("selection_decision", None)
    return raw
