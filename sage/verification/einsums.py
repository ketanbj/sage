"""Bounded equivalence of the pinned HPTT scalar kernel and Rust Tensor operations.

Both programs must satisfy the same exact relation. The HPTT planner, SIMD paths,
public C++ Tensor wrapper and Python bindings are deliberately outside this proof.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

UPSTREAM_COMMIT = "22a115978041e905461b24d9ca2a17bfcce01f32"
UPSTREAM_FILE = "libs/Einsums/HPTT/src/Transpose.cpp"
UPSTREAM_SHA256 = "82dea1cf525a664969bc2443ac1e35eb409397b17821868b7de329c45abedb9d"
KANI_VERSION = "0.68.0"
CBMC_VERSION = "6.11.0"
TEMPLATE = "template <bool betaIsZero, typename floatType, bool conjA>\n"
START = TEMPLATE + "static INLINE void macro_kernel_scalar("
END = "\ntemplate <int blockingA,"
SHAPES = [(m, k) for m in range(1, 5) for k in range(1, 5)]
EXPECTED_HARNESSES = {f"{op}_{m}x{k}" for op in ("copy", "transpose") for m, k in SHAPES}
ASSUMPTIONS = [
    "Independent, valid, contiguous input/output buffers with room for 16 doubles.",
    "Rows and columns each range from 1 through 4; every shape is checked separately.",
    "Every input element is an arbitrary signed byte converted to binary64 and divided by 8.",
    "C++ scalar specialization: double, alpha=1, beta=0, conjugation=false; no threading.",
    "Rust allocation succeeds, as in Kani's default --no-malloc-may-fail model.",
    "Trusted toolchain semantics: Clang 18, CBMC/Kani, standard allocation and memcpy models.",
]
EXCLUSIONS = [
    "HPTT plan construction, dispatch, SIMD kernels and OpenMP execution.",
    "The complete public C++ Tensor copy/permute call path and its metadata.",
    "Rust protocol decoding, the newer Array API and Python bindings.",
    "Other dimensions, dtypes, arbitrary floating-point inputs, aliasing and error contracts.",
    "Whole-library equivalence and native performance.",
]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_scalar(source: str) -> str:
    """Extract an unmodified, uniquely identified upstream definition."""
    if source.count(START) != 1:
        raise ValueError("expected exactly one pinned scalar kernel definition")
    start = source.index(START)
    end = source.index(END, start)
    return source[start:end]


def specialize_scalar(block: str) -> str:
    """Materialize fixed template arguments for CBMC's C++11 frontend.

    The computational statements remain verbatim. Replacing if constexpr with
    a constant if is valid here: both branches are well-formed for double, and
    only the beta=0, nonconjugating branch is reachable. A Clang IR identity
    check additionally ties this specialization to the original template.
    """
    if not block.startswith(TEMPLATE) or block.count("if constexpr (betaIsZero)") != 1:
        raise ValueError("unexpected scalar template structure")
    return "#define floatType double\n#define betaIsZero 1\n#define conjA 0\n" + block.removeprefix(
        TEMPLATE
    ).replace("if constexpr (betaIsZero)", "if (betaIsZero)")


PREAMBLE = """#include <stddef.h>
#include <stdint.h>
#include <string.h>
#define INLINE inline
// Unreachable when conjA=false. Included to make the unused branch well-formed.
double conj(double x) { return x; }
uint64_t bits(double x) { uint64_t out; memcpy(&out, &x, sizeof(out)); return out; }
"""
WRAPPER = """extern "C" void sage_scalar(const double *A, size_t lda, int blockingA,
 size_t innerStrideA, double *B, size_t ldb, int blockingB, size_t innerStrideB) {
 CALL(A,lda,blockingA,innerStrideA,B,ldb,blockingB,innerStrideB,1.,0.);
}
"""


def scalar_call(op: str, m: int, k: int) -> str:
    if op == "transpose":
        return f"macro_kernel_scalar(A,{k},{k},1,B,{m},{m},1,1.,0.);"
    if op == "copy":
        return f"macro_kernel_scalar(A,{k},{k},1,B,1,{m},{k},1.,0.);"
    raise ValueError(f"unsupported proof operation: {op}")


def cpp_harness(op: str, m: int, k: int) -> str:
    rows, cols = (k, m) if op == "transpose" else (m, k)
    index = f"c*{k}+r" if op == "transpose" else f"r*{k}+c"
    return f"""
unsigned char nondet_byte();
int main() {{
 double A[16], original[16], B[16];
 for(unsigned i=0;i<16;i++) {{
  unsigned char byte=nondet_byte();
  A[i]=(double)(signed char)byte/8.; original[i]=A[i]; B[i]=0.;
 }}
 {scalar_call(op, m, k)}
 for(unsigned r=0;r<{rows};r++) for(unsigned c=0;c<{cols};c++)
  __CPROVER_assert(bits(B[r*{cols}+c])==bits(original[{index}]),
    "output bits match specification");
 for(unsigned i=0;i<16;i++)
  __CPROVER_assert(bits(A[i])==bits(original[i]), "input remains unchanged");
 for(unsigned i={m * k};i<16;i++)
  __CPROVER_assert(bits(B[i])==bits(0.), "inactive output remains unchanged");
}}
"""


def normalize_ir(text: str) -> str:
    return "\n".join(
        line for line in text.splitlines() if not line.startswith(("; ModuleID", "source_filename"))
    )


def cbmc_result(
    text: str, returncode: int, required_assertion: str = "output bits match"
) -> dict[str, Any]:
    """A successful exit alone is insufficient: properties must be present."""
    try:
        events = json.loads(text)
        if not isinstance(events, list) or not all(isinstance(e, dict) for e in events):
            raise ValueError("invalid verifier event stream")
        properties = [p for e in events for p in e.get("result", [])]
        if not all(isinstance(p, dict) for p in properties):
            raise ValueError("invalid verifier properties")
        statuses = [e["cProverStatus"] for e in events if "cProverStatus" in e]
        if not properties or not any(required_assertion in p["description"] for p in properties):
            raise ValueError("missing equivalence assertion")
        failed = [p for p in properties if p["status"] == "FAILURE"]
        if (
            returncode == 0
            and statuses == ["success"]
            and all(p["status"] == "SUCCESS" for p in properties)
        ):
            status = "PROVED"
        elif returncode == 10 and statuses == ["failure"] and failed:
            status = "DISPROVED"
        else:
            status = "INCONCLUSIVE"
        return {"status": status, "property_count": len(properties), "failures": failed}
    except (ValueError, TypeError, KeyError):
        return {"status": "INCONCLUSIVE", "property_count": 0, "failures": []}


def kani_result(text: str, returncode: int, expected: set[str] | None = None) -> dict[str, Any]:
    expected = EXPECTED_HARNESSES if expected is None else expected
    names = set(re.findall(r"Checking harness ([A-Za-z0-9_]+)\.\.\.", text))
    summary = re.search(
        r"Complete - (\d+) successfully verified harnesses, (\d+) failures, (\d+) total", text
    )
    valid = (
        returncode == 0
        and names == expected
        and len(re.findall(r"Checking harness ([A-Za-z0-9_]+)\.\.\.", text)) == len(expected)
        and summary is not None
        and tuple(map(int, summary.groups())) == (len(expected), 0, len(expected))
        and text.count("VERIFICATION:- SUCCESSFUL") == len(expected)
    )
    return {"status": "PROVED" if valid else "INCONCLUSIVE", "harnesses": sorted(names)}


class ProofRun:
    def __init__(
        self,
        root: Path,
        output: Path,
        *,
        jobs: int = 2,
        timeout: int = 1800,
        image: str = "sage-einsums:22a1159",
    ) -> None:
        self.root, self.output = root.resolve(), output.resolve()
        self.jobs, self.timeout, self.image = jobs, timeout, image
        if not 1 <= jobs <= 8 or timeout < 1:
            raise ValueError("jobs must be 1..8 and timeout must be positive")
        self.bin = self.root / ".sage/verification" / f"kani-{KANI_VERSION}" / "bin"
        self.env = {**os.environ, "PATH": str(self.bin) + os.pathsep + os.environ.get("PATH", "")}
        self.commands: list[dict[str, Any]] = []
        self.manifest: dict[str, Any] = {
            "schema_version": "sage-bounded-proof-1.0",
            "target": "einsums",
            "status": "INCONCLUSIVE",
            "scope": "HPTT scalar kernel versus Rust Tensor",
            "operations": ["copy", "transpose"],
            "shapes": SHAPES,
            "assumptions": ASSUMPTIONS,
            "exclusions": EXCLUSIONS,
            "source_commit": UPSTREAM_COMMIT,
            "claim": "No proof result yet.",
        }

    def command(self, args: list[str], name: str) -> subprocess.CompletedProcess[str]:
        start = datetime.now(UTC).isoformat()
        process = subprocess.Popen(
            args,
            cwd=self.output,
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        try:
            stdout, stderr = process.communicate(timeout=self.timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            stdout, stderr = process.communicate()
            (self.output / f"{name}.stdout").write_text(stdout)
            (self.output / f"{name}.stderr").write_text(stderr)
            self.commands.append({"args": args, "started_at": start, "returncode": 124})
            if args[:2] == ["docker", "run"]:
                cid_path = self.output / f"{name}.cid"
                if cid_path.exists():
                    subprocess.run(
                        ["docker", "rm", "-f", cid_path.read_text().strip()],
                        capture_output=True,
                        check=False,
                        timeout=30,
                    )
            raise RuntimeError(f"verification command timed out: {name}") from None
        result = subprocess.CompletedProcess(args, process.returncode, stdout, stderr)
        (self.output / f"{name}.stdout").write_text(result.stdout)
        (self.output / f"{name}.stderr").write_text(result.stderr)
        self.commands.append({"args": args, "started_at": start, "returncode": result.returncode})
        return result

    def docker(self, script: str, name: str) -> subprocess.CompletedProcess[str]:
        return self.command(
            [
                "docker",
                "run",
                "--rm",
                "--platform",
                "linux/amd64",
                "--network",
                "none",
                "--cidfile",
                str(self.output / f"{name}.cid"),
                "--memory",
                "2g",
                "--cpus",
                "2",
                "-v",
                f"{self.output}:/work",
                self.image,
                "sh",
                "-c",
                script,
            ],
            name,
        )

    def prepare(self) -> str:
        upstream = (
            self.root / ".sage/upstreams/einsums" / UPSTREAM_COMMIT / "checkout" / UPSTREAM_FILE
        )
        raw = upstream.read_bytes()
        if digest(raw) != UPSTREAM_SHA256:
            raise ValueError("upstream scalar source differs from the pinned proof source")
        (self.output / "Transpose.cpp").write_bytes(raw)
        rust = self.root / "ports/einsums-rs/src/tensor.rs"
        shutil.copy2(rust, self.output / "tensor_source.rs")
        harness = (self.root / "verification/einsums/tensor.rs").read_text()
        expected_path = '#[path = "../../ports/einsums-rs/src/tensor.rs"]'
        if harness.count(expected_path) != 1:
            raise ValueError("Rust proof harness source binding has changed")
        (self.output / "tensor.rs").write_text(
            harness.replace(expected_path, '#[path = "tensor_source.rs"]')
        )
        self.manifest["source_hashes"] = {
            "upstream": digest(raw),
            "rust_tensor": digest(rust.read_bytes()),
            "rust_harness": digest(harness.encode()),
        }
        runner = Path(__file__)
        shutil.copy2(runner, self.output / "proof_runner.py")
        self.manifest["source_hashes"]["proof_runner"] = digest(runner.read_bytes())
        kani = self.command([str(self.bin / "kani-driver"), "--version"], "kani-version")
        cbmc = self.command([str(self.bin / "cbmc"), "--version"], "cbmc-version")
        if kani.returncode or KANI_VERSION not in kani.stdout:
            raise ValueError("incorrect Kani version")
        if cbmc.returncode or cbmc.stdout.split()[0] != CBMC_VERSION:
            raise ValueError("incorrect CBMC version")
        self.manifest["tools"] = {"kani": kani.stdout.strip(), "cbmc": cbmc.stdout.strip()}
        image = self.command(
            ["docker", "image", "inspect", "--format", "{{.Id}}", self.image], "image"
        )
        if image.returncode or not image.stdout.startswith("sha256:"):
            raise ValueError("pinned compiler image unavailable")
        self.image = image.stdout.strip()
        self.manifest["tools"]["compiler_image"] = self.image
        return extract_scalar(raw.decode())

    def certificate(self, block: str) -> bool:
        (self.output / "original.cpp").write_text(
            PREAMBLE + block + WRAPPER.replace("CALL", "macro_kernel_scalar<true,double,false>")
        )
        (self.output / "lowered.cpp").write_text(
            PREAMBLE + specialize_scalar(block) + WRAPPER.replace("CALL", "macro_kernel_scalar")
        )
        result = self.docker(
            "clang++-18 --version && "
            "clang++-18 -std=c++20 -O2 -fno-vectorize -fno-slp-vectorize -S -emit-llvm "
            "/work/original.cpp -o /work/original.ll && "
            "clang++-18 -std=c++20 -O2 -fno-vectorize -fno-slp-vectorize -S -emit-llvm "
            "/work/lowered.cpp -o /work/lowered.ll",
            "compiler-certificate",
        )
        if result.returncode:
            return False
        original = normalize_ir((self.output / "original.ll").read_text())
        lowered = normalize_ir((self.output / "lowered.ll").read_text())
        equal = original == lowered
        self.manifest["specialization_certificate"] = {
            "identical_optimized_ir": equal,
            "normalized_ir_sha256": digest(original.encode()),
            "normalization": "Remove only ModuleID and source_filename lines.",
        }
        return equal

    def cpp_checks(self, block: str) -> list[dict[str, Any]]:
        checks = []
        for op in ("copy", "transpose"):
            for m, k in SHAPES:
                name = f"cpp-{op}-{m}x{k}"
                source = self.output / f"{name}.cpp"
                source.write_text(PREAMBLE + specialize_scalar(block) + cpp_harness(op, m, k))
                result = self.command(
                    [
                        str(self.bin / "cbmc"),
                        str(source),
                        "--cpp11",
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
                checks.append(
                    {
                        "operation": op,
                        "shape": [m, k],
                        **cbmc_result(result.stdout, result.returncode),
                    }
                )
        return checks

    def rust_checks(self) -> dict[str, Any]:
        result = self.command(
            [
                str(self.bin / "kani-driver"),
                str(self.output / "tensor.rs"),
                "--output-format",
                "terse",
                "--jobs",
                str(self.jobs),
                "-Z",
                "unstable-options",
                "--harness-timeout",
                "180s",
            ],
            "rust-proofs",
        )
        return kani_result(result.stdout, result.returncode)

    def negative_controls(self, block: str) -> dict[str, Any]:
        # Mutate isolated source snapshots only; never touch production code.
        original = "alpha * A[(i * lda) + (j * innerStrideA)];"
        if block.count(original) != 1:
            raise ValueError("unexpected scalar mutation site")
        mutant = block.replace(original, original[:-1] + " + 0.125;")
        cpp = self.output / "mutant.cpp"
        cpp.write_text(PREAMBLE + specialize_scalar(mutant) + cpp_harness("transpose", 2, 3))
        result = self.command(
            [
                str(self.bin / "cbmc"),
                str(cpp),
                "--cpp11",
                "--unwind",
                "18",
                "--unwinding-assertions",
                "--bounds-check",
                "--pointer-check",
                "--trace",
                "--json-ui",
            ],
            "cpp-negative-control",
        )
        checked = cbmc_result(result.stdout, result.returncode)
        cpp_detected = checked["status"] == "DISPROVED" and any(
            "output bits match" in p["description"] for p in checked["failures"]
        )
        # Reconstruct a solver witness, then replay against the original and mutant
        # scalar code in native execution. This is an evidence check, not the proof.
        witness: list[int] | None = None
        for failure in checked["failures"]:
            values: dict[int, int] = {}
            for step in failure.get("trace", []):
                match = re.fullmatch(r"A\[(\d+)l?\]", step.get("lhs", ""))
                if match:
                    values[int(match[1])] = round(float(step["value"]["data"]) * 8)
            if len(values) == 16:
                witness = [values[i] for i in range(16)]
                break
        replay = False
        if witness is not None:
            (self.output / "counterexample.json").write_text(
                json.dumps(
                    {
                        "operation": "transpose",
                        "shape": [2, 3],
                        "signed_bytes": witness,
                    },
                    indent=2,
                )
            )
            values_literal = ",".join(str(x) for x in witness)
            native = f"""
int main() {{
 int input[16]={{{values_literal}}}; double A[16], B[16]={{0}};
 for(int i=0;i<16;i++) A[i]=(double)input[i]/8.;
 {scalar_call("transpose", 2, 3)}
 for(int r=0;r<3;r++) for(int c=0;c<2;c++)
  if(bits(B[r*2+c])!=bits(A[c*3+r])) return 10;
 return 0;
}}
"""
            (self.output / "replay-original.cpp").write_text(
                PREAMBLE + specialize_scalar(block) + native
            )
            (self.output / "replay-mutant.cpp").write_text(
                PREAMBLE + specialize_scalar(mutant) + native
            )
            replay_result = self.docker(
                "set -e; "
                "clang++-18 -std=c++20 -O2 /work/replay-original.cpp -o /work/replay-original; "
                "clang++-18 -std=c++20 -O2 /work/replay-mutant.cpp -o /work/replay-mutant; "
                "set +e; /work/replay-original; original_status=$?; "
                "/work/replay-mutant; mutant_status=$?; "
                'test "$original_status" = 0 && test "$mutant_status" = 10',
                "native-counterexample-replay",
            )
            replay = replay_result.returncode == 0
        rust_source = (self.output / "tensor_source.rs").read_text()
        site = "self.strides = axes.iter().map(|&i| self.strides[i]).collect();"
        if rust_source.count(site) != 1:
            raise ValueError("unexpected Rust mutation site")
        (self.output / "tensor_mutant.rs").write_text(
            rust_source.replace(site, "self.strides = self.strides.clone();")
        )
        harness = (self.output / "tensor.rs").read_text().split("\nmacro_rules! proofs", 1)[0]
        harness = harness.replace("tensor_source.rs", "tensor_mutant.rs") + (
            "\n#[kani::proof]\n#[kani::unwind(18)]\nfn transpose_2x3() { check::<2, 3>(true); }\n"
        )
        (self.output / "mutant.rs").write_text(harness)
        rust = self.command(
            [
                str(self.bin / "kani-driver"),
                str(self.output / "mutant.rs"),
                "--harness",
                "transpose_2x3",
                "--concrete-playback",
                "inplace",
                "-Z",
                "concrete-playback",
            ],
            "rust-negative-control",
        )
        rust_detected = (
            rust.returncode != 0
            and "VERIFICATION:- FAILED" in rust.stdout
            and "assertion failed" in rust.stdout
            and "Status: FAILURE" in rust.stdout
        )
        playback = self.command(
            [
                str(self.bin / "kani-driver"),
                "playback",
                str(self.output / "mutant.rs"),
                "--",
                "kani_concrete_playback",
                "--nocapture",
            ],
            "rust-counterexample-replay",
        )
        rust_replayed = playback.returncode != 0 and "test result: FAILED" in playback.stdout
        return {
            "cpp_fault_detected": cpp_detected,
            "cpp_witness_replayed": replay,
            "rust_fault_detected": rust_detected,
            "rust_witness_replayed": rust_replayed,
        }

    def run(self) -> Path:
        self.output.mkdir(parents=True, exist_ok=False)
        try:
            block = self.prepare()
            certificate = self.certificate(block)
            if not certificate:
                raise ValueError("scalar specialization failed its compiler identity check")
            with ThreadPoolExecutor(max_workers=2) as pool:
                rust_future = pool.submit(self.rust_checks)
                cpp = self.cpp_checks(block)
                rust = rust_future.result()
            self.manifest["cpp_checks"] = cpp
            self.manifest["rust_checks"] = rust
            controls = self.negative_controls(block)
            self.manifest["negative_controls"] = controls
            if (
                all(c["status"] == "PROVED" for c in cpp)
                and rust["status"] == "PROVED"
                and all(controls.values())
            ):
                self.manifest["status"] = "BOUNDED_EQUIVALENCE_PROVED"
                self.manifest["claim"] = (
                    "The pinned HPTT scalar kernel and checked-in Rust Tensor clone/permute "
                    "produce identical binary64 output elements for every declared input "
                    "and shape. Rust output shape/strides are also proved. "
                    "This is a kernel-level result, not a proof of the public library call path."
                )
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
            if not self.output.exists():
                # An existing destination is not ours to modify.
                raise
            self.manifest["error"] = str(exc)
        self.manifest["commands"] = self.commands
        self.manifest["finished_at"] = datetime.now(UTC).isoformat()
        (self.output / "manifest.json").write_text(json.dumps(self.manifest, indent=2))
        proved = sum(c["status"] == "PROVED" for c in self.manifest.get("cpp_checks", []))
        report = (
            f"# Einsums bounded scalar-kernel proof\n\nStatus: `{self.manifest['status']}`\n\n"
            f"{self.manifest['claim']}\n\nC++ obligations proved: {proved}/32.\n"
            "Rust obligations: "
            f"{self.manifest.get('rust_checks', {}).get('status', 'NOT_RUN')}.\n\n"
            "## Assumptions\n\n"
            + "\n".join(f"- {s}" for s in ASSUMPTIONS)
            + "\n\n## Exclusions\n\n"
            + "\n".join(f"- {s}" for s in EXCLUSIONS)
            + "\n\n## Fault detection and native replay\n\n"
            + "\n".join(
                f"- {name}: {'PASS' if passed else 'FAIL'}"
                for name, passed in self.manifest.get("negative_controls", {}).items()
            )
            + "\n\nRaw tool outputs, source snapshots, compiler IR, negative controls and "
            "counterexample replay artifacts are retained alongside this report.\n"
        )
        if "error" in self.manifest:
            report += f"\nError: {self.manifest['error']}\n"
        (self.output / "report.md").write_text(report)
        return self.output
