"""Build the Rust cdylib into a platform wheel; no development-tree path is embedded."""

import subprocess
import sys
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        if self.target_name != "wheel":
            return
        root = Path(self.root)
        subprocess.run(
            [
                "cargo",
                "build",
                "--release",
                "--locked",
                "--manifest-path",
                str(root / "Cargo.toml"),
            ],
            check=True,
        )
        filename = "libsage_einsums.dylib" if sys.platform == "darwin" else "libsage_einsums.so"
        binary = root / "target/release" / filename
        build_data["force_include"][str(binary)] = "pyeinsums/_native/" + filename
        build_data["pure_python"] = False
        build_data["infer_tag"] = True
