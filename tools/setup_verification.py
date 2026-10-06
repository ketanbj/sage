"""Install the pinned verification bundle locally without changing the default Rust toolchain."""

from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import tarfile
import urllib.request
from pathlib import Path

VERSION = "0.68.0"
ROOT = Path(__file__).resolve().parents[1]
# Digest of the official GitHub release asset used by this pilot.
SHA256 = "a5d39a5d5e748253a553aa62f295c6c397287927a28e5e32691d7ff2eda0c398"


def main() -> None:
    if (platform.system(), platform.machine()) != ("Darwin", "arm64"):
        raise SystemExit(
            "This setup script currently pins macOS arm64. See docs/formal-verification.md."
        )
    cache = ROOT / ".sage/verification"
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / "kani.tar.gz"
    url = (
        f"https://github.com/model-checking/kani/releases/download/kani-{VERSION}/"
        f"kani-{VERSION}-aarch64-apple-darwin.tar.gz"
    )
    if not archive.exists():
        urllib.request.urlretrieve(url, archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest() != SHA256:
        raise SystemExit("Kani release archive digest mismatch")
    bundle = cache / f"kani-{VERSION}"
    if not bundle.exists():
        with tarfile.open(archive) as source:
            source.extractall(cache, filter="data")
    nightly = (bundle / "rust-toolchain-version").read_text().strip()
    subprocess.run(
        [
            "rustup",
            "toolchain",
            "install",
            nightly,
            "--profile",
            "minimal",
            "--component",
            "rust-src",
            "--component",
            "llvm-tools-preview",
            "--component",
            "rustc-dev",
            "--no-self-update",
        ],
        check=True,
    )
    compiler = subprocess.run(
        ["rustup", "run", nightly, "rustc", "--print", "sysroot"],
        capture_output=True,
        text=True,
        check=True,
    )
    link = bundle / "toolchain"
    if not link.exists():
        link.symlink_to(Path(compiler.stdout.strip()), target_is_directory=True)
    (cache / "installation.json").write_text(
        json.dumps(
            {
                "kani": VERSION,
                "archive_sha256": SHA256,
                "url": url,
                "rust_toolchain": nightly,
            },
            indent=2,
        )
    )
    print(f"Installed pinned proof tools in {bundle}")


if __name__ == "__main__":
    main()
