"""Paired bounded proof of upstream and independent production C++ kernels."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sage.verification.einsums import (
    CBMC_VERSION,
    EXPECTED_HARNESSES,
    PREAMBLE,
    SHAPES,
    UPSTREAM_COMMIT,
    UPSTREAM_FILE,
    UPSTREAM_SHA256,
    ProofRun,
    cbmc_result,
    digest,
    extract_scalar,
    normalize_ir,
    scalar_call,
    specialize_scalar,
)


def paired_harness(op: str, m: int, k: int) -> str:
    rows, cols = (k, m) if op == "transpose" else (m, k)
    index = f"c*{k}+r" if op == "transpose" else f"r*{k}+c"
    return f"""
#include "kernels.hpp"
unsigned char nondet_byte();
int main() {{
 double A[16], original[16], B[16], candidate[16];
 for(unsigned i=0;i<16;i++) {{
  unsigned char byte=nondet_byte();
  int value=byte<128 ? (int)byte : (int)byte-256;
  A[i]=(double)value/8.; original[i]=A[i]; B[i]=0.; candidate[i]=0.;
 }}
 {scalar_call(op, m, k)}
 sage_cpp::{op}_kernel<double>(A,candidate,{m},{k});
 for(unsigned r=0;r<{rows};r++) for(unsigned c=0;c<{cols};c++) {{
  __CPROVER_assert(bits(B[r*{cols}+c])==bits(original[{index}]),
    "upstream output bits match specification");
  __CPROVER_assert(bits(candidate[r*{cols}+c])==bits(original[{index}]),
    "candidate output bits match specification");
  __CPROVER_assert(bits(candidate[r*{cols}+c])==bits(B[r*{cols}+c]),
    "paired output bits match exactly");
 }}
 for(unsigned i=0;i<16;i++)
  __CPROVER_assert(bits(A[i])==bits(original[i]), "input remains unchanged");
 for(unsigned i={m * k};i<16;i++) {{
  __CPROVER_assert(bits(B[i])==bits(0.), "upstream inactive output unchanged");
  __CPROVER_assert(bits(candidate[i])==bits(0.), "candidate inactive output unchanged");
 }}
}}
"""


class ModernCppProofRun(ProofRun):
    def __init__(self, root: Path, output: Path, **kwargs: Any) -> None:
        super().__init__(root, output, **kwargs)
        self.manifest.update(
            target_language="cpp20",
            scope="HPTT scalar kernel versus independent production C++ kernels",
            assumptions=[
                "Independent contiguous buffers, each with capacity for 16 doubles.",
                "All 16 input values arbitrary signed bytes converted to binary64 / 8.",
                "Rows and columns 1..4, with all 16 shapes proved for each operation.",
                "Upstream double, alpha=1, beta=0, conjugation=false scalar specialization.",
                "Trusted CBMC 6.11.0, Clang 18 and memcpy/IEEE binary64 models.",
            ],
            exclusions=[
                "C++20 Tensor/span/array wrapper, allocation/lifetime and input decoder.",
                "Add, elementwise multiply, matmul and scale (native validation only).",
                "Upstream public Tensor/planner/dispatch/SIMD/OpenMP and metadata paths.",
                "Other sizes/dtypes, arbitrary floats, aliasing, error behavior and performance.",
                "Whole-library, Python and GPU equivalence.",
            ],
        )

    def prepare(self) -> str:
        upstream = (
            self.root / ".sage/upstreams/einsums" / UPSTREAM_COMMIT / "checkout" / UPSTREAM_FILE
        )
        raw = upstream.read_bytes()
        if digest(raw) != UPSTREAM_SHA256:
            raise ValueError("upstream source differs from the pinned proof source")
        (self.output / "Transpose.cpp").write_bytes(raw)
        for name in ("kernels.hpp", "tensor.hpp", "driver.cpp"):
            shutil.copy2(self.root / "ports/einsums-cpp" / name, self.output / name)
        self.manifest["source_hashes"] = {
            "upstream": digest(raw),
            **{
                name: digest((self.output / name).read_bytes())
                for name in ("kernels.hpp", "tensor.hpp", "driver.cpp")
            },
        }
        for name, source in (
            ("proof_runner.py", Path(__file__)),
            ("proof_support.py", Path(__file__).with_name("einsums.py")),
        ):
            shutil.copy2(source, self.output / name)
            self.manifest["source_hashes"][name] = digest(source.read_bytes())
        cbmc = self.command([str(self.bin / "cbmc"), "--version"], "cbmc-version")
        if cbmc.returncode or cbmc.stdout.split()[0] != CBMC_VERSION:
            raise ValueError("incorrect CBMC version")
        image = self.command(
            ["docker", "image", "inspect", "--format", "{{.Id}}", self.image], "image"
        )
        if image.returncode or not image.stdout.startswith("sha256:"):
            raise ValueError("compiler image unavailable")
        self.image = image.stdout.strip()
        self.manifest["tools"] = {"cbmc": cbmc.stdout.strip(), "compiler_image": self.image}
        return extract_scalar(raw.decode())

    def candidate_certificate(self) -> bool:
        (self.output / "candidate-binding.cpp").write_text(
            '#include "kernels.hpp"\n'
            'extern "C" void sage_copy(const double* a,double* b,unsigned r,unsigned c) '
            "{ sage_cpp::copy_kernel(a,b,r,c); }\n"
            'extern "C" void sage_transpose(const double* a,double* b,unsigned r,unsigned c) '
            "{ sage_cpp::transpose_kernel(a,b,r,c); }\n"
        )
        result = self.docker(
            "clang++-18 -std=c++20 -fno-autolink -O2 -ffp-contract=off "
            "-fno-vectorize -fno-slp-vectorize "
            "-S -emit-llvm /work/candidate-binding.cpp -o /work/candidate20.ll && "
            "clang++-18 -std=c++11 -fno-autolink -O2 -ffp-contract=off "
            "-fno-vectorize -fno-slp-vectorize "
            "-S -emit-llvm /work/candidate-binding.cpp -o /work/candidate11.ll",
            "candidate-certificate",
        )
        if result.returncode:
            return False
        modern = normalize_ir((self.output / "candidate20.ll").read_text())
        legacy = normalize_ir((self.output / "candidate11.ll").read_text())
        equal = modern == legacy
        self.manifest["candidate_certificate"] = {
            "identical_optimized_ir": equal,
            "normalized_ir_sha256": digest(modern.encode()),
            "normalization": "Remove only ModuleID and source_filename lines.",
            "source": "Unmodified production kernels.hpp in both language modes.",
        }
        return equal

    def check(self, source: Path, name: str) -> dict[str, Any]:
        result = self.command(
            [
                str(self.bin / "cbmc"),
                str(source),
                "--cpp11",
                "--object-bits",
                "12",
                "--unwind",
                "18",
                "--unwinding-assertions",
                "--bounds-check",
                "--pointer-check",
                "--signed-overflow-check",
                "--unsigned-overflow-check",
                "--trace",
                "--json-ui",
            ],
            name,
        )
        parsed = cbmc_result(result.stdout, result.returncode)
        # Require all three relation assertions, not merely one successful output property.
        if parsed["status"] == "PROVED":
            descriptions = [
                p["description"] for e in json.loads(result.stdout) for p in e.get("result", [])
            ]
            if not all(
                any(required in d for d in descriptions)
                for required in (
                    "upstream output bits match",
                    "candidate output bits match",
                    "paired output bits match",
                )
            ):
                parsed["status"] = "INCONCLUSIVE"
        return parsed

    def paired_checks(self, block: str) -> list[dict[str, Any]]:
        def obligation(item: tuple[str, int, int]) -> dict[str, Any]:
            op, m, k = item
            name = f"paired-{op}-{m}x{k}"
            source = self.output / f"{name}.cpp"
            source.write_text(PREAMBLE + specialize_scalar(block) + paired_harness(op, m, k))
            return {"operation": op, "shape": [m, k], **self.check(source, name)}

        with ThreadPoolExecutor(max_workers=self.jobs) as pool:
            return list(
                pool.map(
                    obligation, [(op, m, k) for op in ("copy", "transpose") for m, k in SHAPES]
                )
            )

    def controls(self, block: str) -> dict[str, bool]:
        outcomes = {}
        for side in ("candidate", "upstream"):
            folder = self.output / f"negative-{side}"
            folder.mkdir()
            kernel = (self.output / "kernels.hpp").read_text()
            specialized = specialize_scalar(block)
            if side == "candidate":
                old = "output[c * rows + r] = input[r * cols + c];"
                if kernel.count(old) != 1:
                    raise ValueError("negative-control mutation site changed")
                kernel = kernel.replace(old, old.replace(";", " + 0.125;"))
            else:
                old = "alpha * A[(i * lda) + (j * innerStrideA)];"
                if specialized.count(old) != 1:
                    raise ValueError("upstream mutation site changed")
                specialized = specialized.replace(old, old.replace(";", " + 0.125;"))
            (folder / "kernels.hpp").write_text(kernel)
            source = folder / "mutant.cpp"
            source.write_text(PREAMBLE + specialized + paired_harness("transpose", 2, 3))
            name = f"negative-{side}"
            result = self.check(source, name)
            failed_relation = any(
                "output bits match" in p.get("description", "") for p in result["failures"]
            )
            outcomes[f"{side}_fault_detected"] = result["status"] == "DISPROVED" and failed_relation
            values: dict[int, int] = {}
            for failure in result["failures"]:
                for step in failure.get("trace", []):
                    match = re.fullmatch(r"A\[(\d+)l?\]", step.get("lhs", ""))
                    if match:
                        values[int(match[1])] = round(float(step["value"]["data"]) * 8)
            if set(values) != set(range(16)):
                outcomes[f"{side}_witness_replayed"] = False
                continue
            witness = [values[i] for i in range(16)]
            (folder / "counterexample.json").write_text(json.dumps({"values": witness}))
            native_prefix = (
                "#define __CPROVER_assert(condition, message) if (!(condition)) return 10\n"
                "unsigned char witness[16]={" + ",".join(str(v % 256) for v in witness) + "};\n"
                "unsigned cursor=0;\n"
                "unsigned char nondet_byte(){return witness[cursor++];}\n"
            )
            for variant, upstream in (
                ("original", specialize_scalar(block)),
                ("mutant", specialized),
            ):
                target = folder / variant
                target.mkdir()
                target_kernel = (
                    kernel if variant == "mutant" else (self.output / "kernels.hpp").read_text()
                )
                (target / "kernels.hpp").write_text(target_kernel)
                (target / "replay.cpp").write_text(
                    native_prefix + PREAMBLE + upstream + paired_harness("transpose", 2, 3)
                )
            replay = self.docker(
                f"set -e; for variant in original mutant; do clang++-18 -std=c++20 "
                f"-O2 -ffp-contract=off /work/{name}/$variant/replay.cpp "
                f"-o /work/{name}/$variant/replay; done; "
                f"set +e; /work/{name}/original/replay; original=$?; "
                f"/work/{name}/mutant/replay; mutant=$?; "
                'echo "original=$original mutant=$mutant"; '
                '[ "$original" -eq 0 ] && [ "$mutant" -eq 10 ]',
                f"{name}-replay",
            )
            outcomes[f"{side}_witness_replayed"] = replay.returncode == 0
        return outcomes

    def run(self) -> Path:
        self.output.mkdir(parents=True, exist_ok=False)
        try:
            block = self.prepare()
            if not self.certificate(block) or not self.candidate_certificate():
                raise ValueError("source-binding compiler certificate failed")
            checks = self.paired_checks(block)
            self.manifest["paired_checks"] = checks
            controls = self.controls(block)
            self.manifest["negative_controls"] = controls
            names = {f"{c['operation']}_{c['shape'][0]}x{c['shape'][1]}" for c in checks}
            if (
                len(checks) == 32
                and names == EXPECTED_HARNESSES
                and all(c["status"] == "PROVED" for c in checks)
                and len(controls) == 4
                and all(controls.values())
            ):
                self.manifest["status"] = "BOUNDED_EQUIVALENCE_PROVED"
                self.manifest["claim"] = (
                    "The pinned upstream HPTT scalar kernel and independent production C++ "
                    "copy/transpose kernels produce identical binary64 output for every "
                    "declared input and shape, preserve input and inactive output, and "
                    "satisfy the checked memory/overflow/unwinding properties. "
                    "The modern C++ wrapper is outside this kernel proof."
                )
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
            self.manifest["error"] = str(exc)
        self.manifest["commands"] = self.commands
        self.manifest["finished_at"] = datetime.now(UTC).isoformat()
        (self.output / "manifest.json").write_text(json.dumps(self.manifest, indent=2))
        proved = sum(c["status"] == "PROVED" for c in self.manifest.get("paired_checks", []))
        report = (
            f"# Modern C++ bounded equivalence\n\nStatus: `{self.manifest['status']}`\n\n"
            f"{self.manifest['claim']}\n\nPaired obligations proved: {proved}/32.\n\n"
            "## Assumptions\n\n"
            + "\n".join(f"- {s}" for s in self.manifest["assumptions"])
            + "\n\n## Exclusions\n\n"
            + "\n".join(f"- {s}" for s in self.manifest["exclusions"])
            + "\n\n## Fault detection and native witness replay\n\n"
            + "\n".join(
                f"- {name}: {'PASS' if passed else 'FAIL'}"
                for name, passed in self.manifest.get("negative_controls", {}).items()
            )
            + "\n\nSource snapshots, hashes, tool outputs, LLVM certificates and solver "
            "counterexamples are retained in this bundle.\n"
        )
        if "error" in self.manifest:
            report += f"\nError: {self.manifest['error']}\n"
        (self.output / "report.md").write_text(report)
        return self.output
