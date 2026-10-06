"""Build the native platform wheel and bundle macOS HDF5 dependencies."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORT = ROOT / "ports/einsums-cpp"


def main():
    subprocess.run(["uv", "build", "--wheel", str(PORT)], check=True)
    wheel = max((PORT / "dist").glob("*.whl"), key=lambda p: p.stat().st_mtime)
    if sys.platform == "darwin":
        subprocess.run(
            [
                "uv",
                "tool",
                "run",
                "--from",
                "delocate",
                "delocate-wheel",
                "--require-archs",
                "arm64" if "arm64" in wheel.name else "x86_64",
                "-w",
                str(PORT / "dist/repaired"),
                str(wheel),
            ],
            check=True,
        )
        wheel = PORT / "dist/repaired" / wheel.name
    print(wheel)


if __name__ == "__main__":
    main()
