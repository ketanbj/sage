"""Generate fresh SymSan constraints inside selected production library decisions.

The existing full-library profile remains input-only. This separate experiment
traces exact integer decisions used by FFT bins and real LU pivot selection.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import struct
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run(args: list[str], output: Path, label: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(args, capture_output=True, text=True, timeout=300, check=False)
    (output / f"{label}.stdout").write_text(result.stdout)
    (output / f"{label}.stderr").write_text(result.stderr)
    if result.returncode:
        raise RuntimeError(f"{label} failed: {result.stderr[-1000:]}")
    return result


def decode(payload: bytes) -> tuple[int, int, int, bool, float, float]:
    if len(payload) != 20:
        raise ValueError("wrong length")
    mode, n, i, real = payload[:4]
    a, b = struct.unpack("<dd", payload[4:])
    if mode > 2 or (mode == 0 and not (1 <= n <= 64 and i < n)):
        raise ValueError("invalid decision request")
    return mode, n, i, bool(real), a, b


def expectation(payload: bytes) -> int:
    import math

    mode, n, i, real, a, b = decode(payload)
    if mode == 0:
        return i if real or i <= (n - 1) // 2 else i - n
    if mode == 1:
        if not math.isfinite(a) or not math.isfinite(b):
            raise ValueError("nonfinite pivot")
        return int(abs(a) > abs(b))
    return int(
        math.isfinite(a)
        and -16 <= a <= 15.875
        and (a * 8).is_integer()
        and (a != 0 or struct.pack("<d", a) == bytes(8))
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-inputs", type=int, default=128)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    image = run(
        ["docker", "image", "inspect", "--format", "{{.Id}}", "sage-einsums:22a1159"],
        output,
        "image",
    ).stdout.strip()
    for src in (
        "fixtures/einsums-paths/driver.cpp",
        "ports/einsums-cpp/api/proof_contract.hpp",
        "containers/symsan/driver.py",
    ):
        shutil.copy2(ROOT / src, output / Path(src).name)
    shutil.copy2(Path(__file__), output / "experiment.py")
    docker = [
        "docker",
        "run",
        "--rm",
        "--platform",
        "linux/amd64",
        "--network",
        "none",
        "--memory",
        "2g",
        "--cpus",
        "1",
        "-v",
        f"{output}:/work",
        "--entrypoint",
    ]
    compile_script = (
        "KO_USE_FASTGEN=1 KO_USE_NATIVE_LIBCXX=1 KO_DONT_OPTIMIZE=1 "
        "/opt/symsan/bin/ko-clang++ -std=c++20 -O0 -g -fno-pie -no-pie "
        "-fno-vectorize -fno-slp-vectorize /work/driver.cpp -o /work/instrumented && "
        "clang++-18 -std=c++20 -O0 -g -fno-pie -no-pie /work/driver.cpp -o /work/native"
    )
    run([*docker, "sh", image, "-c", compile_script], output, "build")
    seeds = output / "seeds"
    seeds.mkdir()
    # Bootstrap paths, never counted as generated evidence.
    patterns = [
        (0.0, 0.0),
        (-0.0, 1.0),
        (1.0, -2.0),
        (15.875, -16.0),
        (0.125, 0.3),
        (1e-300, 1e300),
    ]
    for mode in range(3):
        for j, (a, b) in enumerate(patterns):
            (seeds / f"{mode}-{j}.bin").write_bytes(
                bytes([mode, 5, j % 5, j % 2]) + struct.pack("<dd", a, b)
            )
    seed_files = sorted(seeds.glob("*.bin"))
    result = run(
        [
            *docker,
            "python3",
            image,
            "/work/driver.py",
            "--target",
            "/work/instrumented",
            "--output",
            "/work/generated",
            "--no-bounds",
            "--max-tasks",
            str(args.max_inputs * 8),
            "--max-tasks-per-seed",
            "40",
            "--max-corpus",
            str(args.max_inputs),
            *[f"/work/seeds/{p.name}" for p in seed_files],
        ],
        output,
        "symsan",
    )
    events = [json.loads(line) for line in result.stdout.splitlines() if line.startswith("{")]
    addresses = sorted(
        {e["address"] for e in events if e["event"] == "symbolic_event" and e.get("label", 0)}
    )
    located = run(
        [
            *docker,
            "addr2line",
            image,
            "-f",
            "-C",
            "-e",
            "/work/instrumented",
            *[hex(a) for a in addresses],
        ],
        output,
        "locations",
    ).stdout.splitlines()
    locations = [
        {"address": a, "function": located[2 * j], "source": located[2 * j + 1]}
        for j, a in enumerate(addresses)
    ]
    library = [p for p in locations if "proof_contract.hpp:" in p["source"]]
    bootstrap = {p.read_bytes() for p in seed_files}
    seen: set[bytes] = set()
    accepted = []
    rejected = 0
    for p in sorted((output / "generated").glob("*.bin")):
        payload = p.read_bytes()
        if payload in bootstrap or payload in seen:
            rejected += 1
            continue
        seen.add(payload)
        try:
            expected = expectation(payload)
        except ValueError:
            rejected += 1
            continue
        native = run(
            [*docker, "/work/native", image, f"/work/generated/{p.name}"],
            output,
            f"replay-{p.stem}",
        )
        if int(native.stdout.strip()) != expected:
            raise ValueError("native production decision disagrees")
        accepted.append(
            {
                "file": f"generated/{p.name}",
                "sha256": hashlib.sha256(payload).hexdigest(),
                "mode": payload[0],
                "expected": expected,
            }
        )
    report = {
        "status": "SAMPLED_LIBRARY_DECISIONS_PASS"
        if accepted and library and {c["mode"] for c in accepted} == {0, 1, 2}
        else "INCONCLUSIVE",
        "claim": (
            "Fresh sampled constraints and native replay of selected "
            "production decisions; not a library arithmetic proof."
        ),
        "image": image,
        "accepted": len(accepted),
        "rejected": rejected,
        "instrumentation": (
            "production FFT bin, dyadic eligibility and real-pivot comparison helpers"
        ),
        "floating_point_expression_exploration": False,
        "full_profile_instrumentation": "unchanged: input decoder only",
        "source_hashes": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in output.iterdir()
            if p.suffix in (".py", ".hpp", ".cpp")
        },
        "symbolic_library_locations": library,
        "symbolic_locations": locations,
        "cases": accepted,
        "generation_events_sha256": hashlib.sha256(result.stdout.encode()).hexdigest(),
    }
    (output / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("status", "accepted", "rejected")}))
    return 0 if report["status"] == "SAMPLED_LIBRARY_DECISIONS_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
