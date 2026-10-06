"""Build the independent C++20 backend into a platform wheel."""

import subprocess
import sys
from pathlib import Path

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        if self.target_name != "wheel":
            return
        root = Path(self.root)
        build = root / "build-wheel"
        subprocess.run(
            [
                "cmake",
                "-S",
                str(root),
                "-B",
                str(build),
                "-DCMAKE_BUILD_TYPE=Release",
                "-DBUILD_TESTING=OFF",
            ],
            check=True,
        )
        subprocess.run(["cmake", "--build", str(build), "-j", "2"], check=True)
        filename = "libsage_einsums_cpp" + (".dylib" if sys.platform == "darwin" else ".so")
        build_data["force_include"][str(build / filename)] = "pyeinsums/_native/" + filename
        build_data["pure_python"] = False
        build_data["infer_tag"] = True
