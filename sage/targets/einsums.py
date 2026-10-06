from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from sage.config import Config
from sage.targets.base import TargetAdapter

EINSUMS_COMMIT = "22a115978041e905461b24d9ca2a17bfcce01f32"


class EinsumsTargetAdapter(TargetAdapter):
    def prepare(self, config: Config, destination: Path) -> dict[str, str]:
        if config.target is None or config.target.name != "einsums":
            raise ValueError("Einsums adapter requires an Einsums configuration")
        if config.target.upstream_commit != EINSUMS_COMMIT:
            raise ValueError("Einsums contract requires the recorded v1.1.5 pin")
        destination.mkdir(parents=True, exist_ok=True)
        checkout = destination / "checkout"
        if not checkout.exists():
            subprocess.run(
                ["git", "clone", "--no-checkout", config.target.upstream_url, str(checkout)],
                check=True,
            )
            subprocess.run(
                ["git", "-C", str(checkout), "checkout", "--detach", EINSUMS_COMMIT], check=True
            )
        actual = subprocess.check_output(
            ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
        ).strip()
        dirty = subprocess.check_output(
            ["git", "-C", str(checkout), "status", "--porcelain"], text=True
        ).strip()
        if actual != EINSUMS_COMMIT or dirty:
            raise ValueError("Einsums checkout must be clean and match the pinned commit")
        shutil.copy2(checkout / "LICENSE.txt", destination / "EINSUMS-LICENSE.txt")
        scope = (
            "cpu-python-library"
            if config.equivalence.policy_version == "einsums-library-1.0"
            else "bounded-cpu-tensors"
        )
        return {"commit": actual, "checkout": str(checkout), "scope": scope}
