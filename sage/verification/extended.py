"""Source-bound proofs of production adapter and additional numerical decisions."""

from __future__ import annotations

import json
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sage.verification.einsums import (
    CBMC_VERSION,
    KANI_VERSION,
    ProofRun,
    cbmc_result,
    digest,
    kani_result,
    normalize_ir,
)

ASSERTIONS = {
    "adapter_guard": "adapter contract matches specification",
    "dyad_sound": "dyadic eligibility matches specification",
    "dyad_complete": "all signed byte dyadics accepted",
    "real_pivot": "pivot order matches finite absolute values",
    "frequency": "frequency bin matches specification",
    **{
        f"layout_{m}x{k}": "transpose preserves all 64 bits"
        for m in range(1, 9)
        for k in range(1, 9)
    },
}
MUTATIONS = {
    "adapter_guard": ("arity ==", "arity !="),
    "dyad_complete": ("return true;", "return false;"),
    "real_pivot": ("> b & MAGNITUDE", ">= b & MAGNITUDE"),
    "frequency": ("n / 2 + n % 2", "n / 2"),
    "layout_2x3": ("c * rows + r", "r * cols + c"),
}
CPP_MUTATIONS = {
    **MUTATIONS,
    "dyad_complete": ("if (bits == 0) return true;", "if (bits == 0) return false;"),
    "real_pivot": (
        "> (b & 0x7fffffffffffffffULL)",
        ">= (b & 0x7fffffffffffffffULL)",
    ),
    "layout_2x3": ("c * rows + r", "r * cols + c"),
}
BINDINGS = [
    "ports/einsums-cpp/api/execute.hpp",
    "ports/einsums-cpp/sage_api.h",
    "ports/einsums-rs/src/lib.rs",
    "ports/einsums-rs/src/api/bounded_tensor.rs",
    "ports/einsums-rs/src/api/mod.rs",
    "ports/einsums-rs/src/api/linalg.rs",
    "ports/einsums-rs/src/fft.rs",
    "ports/einsums-cpp/api/bounded_tensor.hpp",
    "ports/einsums-cpp/api/execute.cpp",
    "ports/einsums-cpp/api/linalg.cpp",
    "ports/einsums-cpp/api/fft.hpp",
]


class ExtendedProofRun(ProofRun):
    def __init__(
        self,
        root: Path,
        output: Path,
        *,
        language: str,
        reuse_checks: Path | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(root, output, **kwargs)
        if language not in ("rust", "cpp20"):
            raise ValueError("language must be rust or cpp20")
        self.language = language
        self.reuse_checks = reuse_checks.resolve() if reuse_checks else None
        self.manifest.update(
            profile="extended",
            target_language=language,
            scope=(
                "Production metadata guards, exact dyadic eligibility, real "
                "pivot order, FFT bins, and copy/transpose"
            ),
            obligations=list(ASSERTIONS),
            operations=[
                "adapter eligibility",
                "real LU pivot comparison",
                "fftfreq bins",
                "copy",
                "transpose",
            ],
            shapes=[[m, k] for m in range(1, 9) for k in range(1, 9)],
            assumptions=[
                "Metadata fields and input bit patterns are symbolic, including invalid metadata.",
                (
                    "Copy/transpose: independent valid buffers, every 1..8 "
                    "rank-two shape, arbitrary u64 elements."
                ),
                (
                    "The u64 layout theorem interprets elementwise copies as "
                    "preservation of arbitrary binary64 bits."
                ),
                (
                    "Rust allocation succeeds; compiler, standard-library and "
                    "verifier semantics are trusted."
                ),
                "Pivot comparison: two finite binary64 operands; first row wins ties.",
                "FFT bins: 0<n<=INT64_MAX, i<n; all such integer inputs, not just n<=64.",
            ],
            exclusions=[
                (
                    "JSON/Python parsing, serialization, FFI pointer validity and "
                    "lifetime/thread scheduling."
                ),
                (
                    "Whole LU arithmetic, FFT arithmetic, BLAS/LAPACK, upstream "
                    "dispatcher/planner/SIMD/OpenMP."
                ),
                (
                    "Larger C++ layout proofs concern kernels; public BasicTensor "
                    "remains limited to dimensions 1..4."
                ),
                (
                    "No claim that larger-shape public Array fallbacks execute "
                    "the proved layout methods."
                ),
                "GPU, allocation failure and complete upstream C++ overload/ABI compatibility.",
            ],
            claim="No proof result yet.",
        )

    def prepare_extended(self) -> None:
        sources = {
            "contract.rs": "ports/einsums-rs/src/proof_contract.rs",
            "proof_contract.hpp": "ports/einsums-cpp/api/proof_contract.hpp",
            "tensor_source.rs": "ports/einsums-rs/src/tensor.rs",
            "kernels.hpp": "ports/einsums-cpp/kernels.hpp",
            "contracts.rs": "verification/einsums/extended/contracts.rs",
            "contracts.cpp": "verification/einsums/extended/contracts.cpp",
        }
        for filename, src in sources.items():
            shutil.copy2(self.root / src, self.output / filename)
        p = self.output / "contracts.rs"
        s = p.read_text()
        for old, new in (
            (
                '#[path = "../../../ports/einsums-rs/src/proof_contract.rs"]',
                '#[path = "contract.rs"]',
            ),
            ('#[path = "../../../ports/einsums-rs/src/tensor.rs"]', '#[path = "tensor_source.rs"]'),
        ):
            if s.count(old) != 1:
                raise ValueError("production source binding changed")
            s = s.replace(old, new)
        p.write_text(s)
        shutil.copy2(Path(__file__), self.output / "proof_runner.py")
        shutil.copy2(Path(__file__).with_name("einsums.py"), self.output / "proof_support.py")
        self.manifest["public_api_bindings"] = {}
        for path in BINDINGS:
            dest = self.output / "bindings" / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.root / path, dest)
            self.manifest["public_api_bindings"][path] = digest(dest.read_bytes())
        self.manifest["source_hashes"] = {
            p.name: digest(p.read_bytes()) for p in self.output.iterdir() if p.is_file()
        }
        for tool, version in (("kani-driver", KANI_VERSION), ("cbmc", CBMC_VERSION)):
            r = self.command([str(self.bin / tool), "--version"], f"{tool}-version")
            if r.returncode or version not in r.stdout:
                raise ValueError(f"wrong {tool} version")
        self.manifest["tools"] = {"kani": KANI_VERSION, "cbmc": CBMC_VERSION}

    def cpp_check(self, folder: Path, harness: str, label: str) -> dict[str, Any]:
        r = self.command(
            [
                str(self.bin / "cbmc"),
                str(folder / "contracts.cpp"),
                "--cpp11",
                "--function",
                harness,
                "--unwind",
                "66",
                "--unwinding-assertions",
                "--bounds-check",
                "--pointer-check",
                "--signed-overflow-check",
                "--unsigned-overflow-check",
                "--trace",
                "--json-ui",
            ],
            label,
        )
        return {"obligation": harness, **cbmc_result(r.stdout, r.returncode, ASSERTIONS[harness])}

    def controls(self) -> None:
        controls = {}
        mutations = MUTATIONS if self.language == "rust" else CPP_MUTATIONS
        for harness, (old, new) in mutations.items():
            folder = self.output / f"negative-{harness}"
            folder.mkdir()
            for p in self.output.iterdir():
                if p.suffix in (".rs", ".hpp", ".cpp"):
                    shutil.copy2(p, folder / p.name)
            filename = "contract.rs" if self.language == "rust" else "proof_contract.hpp"
            if harness.startswith("layout"):
                filename = "tensor_source.rs" if self.language == "rust" else "kernels.hpp"
                if self.language == "rust":
                    old, new = (
                        "data.push(self.get(&indices)?.clone());",
                        "data.push(self.data[self.offset].clone());",
                    )
            p = folder / filename
            s = p.read_text()
            if s.count(old) != 1:
                raise ValueError(f"mutation binding changed: {harness}")
            p.write_text(s.replace(old, new))
            if self.language == "cpp20":
                r = self.cpp_check(folder, harness, f"negative-{harness}")
                detected = r["status"] == "DISPROVED" and any(
                    ASSERTIONS[harness] in f["description"] for f in r["failures"]
                )
            else:
                result = self.command(
                    [
                        str(self.bin / "kani-driver"),
                        str(folder / "contracts.rs"),
                        "--harness",
                        harness,
                        "--output-format",
                        "regular",
                    ],
                    f"negative-{harness}",
                )
                detected = (
                    result.returncode != 0
                    and ASSERTIONS[harness] in result.stdout
                    and ("0 successfully verified harnesses, 1 failures, 1 total" in result.stdout)
                )
            controls[harness] = {"detected": detected}
        self.manifest["negative_controls"] = controls

    def production_certificate(self) -> None:
        source = '#include "proof_contract.hpp"\n#include "kernels.hpp"\n'
        source += (
            'extern "C" bool dyad(uint64_t b){return '
            'sage_cpp::contract::dyad_bits(b);}\nextern "C" bool '
            "pivot(uint64_t a,uint64_t b){return "
            'sage_cpp::contract::greater_magnitude(a,b);}\nextern "C" bool '
            "guard(unsigned op,size_t arity,sage_cpp::contract::Metadata "
            "a,sage_cpp::contract::Metadata b,bool s){return "
            'sage_cpp::contract::route(op,arity,a,b,s);}\nextern "C" '
            "int64_t freq(size_t n,size_t i,bool real){return "
            'sage_cpp::contract::frequency_bin(n,i,real);}\nextern "C" '
            "void copy(const uint64_t* a,uint64_t* b,unsigned m,unsigned "
            'n){sage_cpp::copy_kernel(a,b,m,n);}\nextern "C" void '
            "transpose(const uint64_t* a,uint64_t* b,unsigned m,unsigned "
            "n){sage_cpp::transpose_kernel(a,b,m,n);}\n"
        )
        (self.output / "binding.cpp").write_text(source)
        r = self.command(["docker", "image", "inspect", "--format", "{{.Id}}", self.image], "image")
        if r.returncode or not r.stdout.strip().startswith("sha256:"):
            raise ValueError("pinned compiler image unavailable")
        self.image = r.stdout.strip()
        self.manifest["compiler_image"] = self.image
        flags = (
            "-O2 -ffp-contract=off -fno-autolink -fno-vectorize -fno-slp-vectorize -S -emit-llvm"
        )
        r = self.docker(
            f"clang++-18 -std=c++20 {flags} /work/binding.cpp -o /work/binding20.ll && "
            f"clang++-18 -std=c++11 {flags} /work/binding.cpp -o /work/binding11.ll",
            "certificate",
        )
        if r.returncode:
            raise ValueError("compiler certificate failed")
        modern = normalize_ir((self.output / "binding20.ll").read_text())
        legacy = normalize_ir((self.output / "binding11.ll").read_text())
        self.manifest["compiler_certificate"] = {
            "identical_optimized_ir": modern == legacy,
            "normalization": "Remove only ModuleID and source_filename lines.",
            "modern_sha256": digest(modern.encode()),
            "legacy_sha256": digest(legacy.encode()),
        }
        if modern != legacy:
            raise ValueError("C++11/C++20 helper and kernel identities differ")

    def native_controls(self) -> None:
        rust_cases = {
            "adapter_guard": (
                "let "
                "a=contract::Metadata{f64:true,rank:2,rows:1,cols:1,values:1,"
                "dyadic:true}; contract::route(0,1,a,a,true)"
            ),
            "dyad_complete": "contract::dyad_bits(0)",
            "real_pivot": "!contract::greater_magnitude(0x3ff0000000000000,0x3ff0000000000000)",
            "frequency": "contract::frequency_bin(3,1,false)==1",
            "layout_2x3": (
                "let "
                "a=tensor::Tensor::from_vec(vec![2,3],vec![1u64,2,3,4,5,6]).u"
                "nwrap(); a.permute(&[1,0]).unwrap().as_slice()==[1,4,2,5,3,6]"
            ),
        }
        cpp_cases = {
            "adapter_guard": (
                "sage_cpp::contract::Metadata a={true,2,1,1,1,true}; return "
                "sage_cpp::contract::route(0,1,a,a,true);"
            ),
            "dyad_complete": "return sage_cpp::contract::dyad_bits(0);",
            "real_pivot": (
                "return "
                "!sage_cpp::contract::greater_magnitude(0x3ff0000000000000ULL"
                ",0x3ff0000000000000ULL);"
            ),
            "frequency": "return sage_cpp::contract::frequency_bin(3,1,false)==1;",
            "layout_2x3": (
                "uint64_t a[]={1,2,3,4,5,6},b[6],e[]={1,4,2,5,3,6}; "
                "sage_cpp::transpose_kernel<uint64_t>(a,b,2,3); for(unsigned "
                "i=0;i<6;++i)if(b[i]!=e[i])return false; return true;"
            ),
        }
        outcomes = {}
        for harness in MUTATIONS:
            statuses = []
            for folder in (self.output, self.output / f"negative-{harness}"):
                if self.language == "rust":
                    source = folder / "witness.rs"
                    source.write_text(
                        '#![allow(dead_code)]\n#[path="contract.rs"]mod contract;\n'
                        '#[path="tensor_source.rs"]mod tensor;\nfn main(){let ok={'
                        + rust_cases[harness]
                        + "};std::process::exit(if ok{0}else{3});}\n"
                    )
                    command = [
                        "rustc",
                        "--edition=2021",
                        "-O",
                        str(source),
                        "-o",
                        str(folder / "witness"),
                    ]
                else:
                    source = folder / "witness.cpp"
                    source.write_text(
                        '#include "proof_contract.hpp"\n#include "kernels.hpp"\n'
                        "bool check(){"
                        + cpp_cases[harness]
                        + "}\nint main(){return check()?0:3;}\n"
                    )
                    command = [
                        "c++",
                        "-std=c++20",
                        "-O2",
                        str(source),
                        "-o",
                        str(folder / "witness"),
                    ]
                suffix = "original" if folder == self.output else "mutant"
                build = self.command(command, f"native-build-{harness}-{suffix}")
                if build.returncode:
                    raise ValueError(f"native witness failed to compile: {harness}")
                statuses.append(
                    self.command([str(folder / "witness")], f"native-{harness}-{suffix}").returncode
                )
            outcomes[harness] = {
                "baseline_passed": statuses[0] == 0,
                "mutant_failed": statuses[1] == 3,
            }
        self.manifest["native_fault_replay"] = outcomes
        if not all(r["baseline_passed"] and r["mutant_failed"] for r in outcomes.values()):
            raise ValueError("native mutation witness failed")

    def reuse_rust(self) -> bool:
        if not self.reuse_checks:
            return False
        if self.language != "rust":
            raise ValueError("extended proof reuse currently supports Rust only")
        previous = json.loads((self.reuse_checks / "manifest.json").read_text())
        if (
            previous.get("target_language") != "rust"
            or previous.get("profile") != "extended"
            or previous.get("tools") != self.manifest["tools"]
        ):
            raise ValueError("reused proof language/profile/tools differ")
        for filename in ("contract.rs", "tensor_source.rs", "contracts.rs"):
            expected = digest((self.output / filename).read_bytes())
            if (
                digest((self.reuse_checks / filename).read_bytes()) != expected
                or previous["source_hashes"].get(filename) != expected
            ):
                raise ValueError(f"reused proof input differs: {filename}")
        commands = [
            c
            for c in previous["commands"]
            if Path(c["args"][0]).name == "kani-driver"
            and "--harness" not in c["args"]
            and "--output-format" in c["args"]
        ]
        if len(commands) != 1:
            raise ValueError("reused verification command is ambiguous")
        log = (self.reuse_checks / "rust-extended.stdout").read_text()
        result = kani_result(log, commands[0]["returncode"], set(ASSERTIONS))
        if result["status"] != "PROVED":
            raise ValueError("reused Rust proof is incomplete")
        self.manifest["checks"] = result
        self.manifest["reused_checks"] = {
            "bundle": str(self.reuse_checks),
            "manifest_sha256": digest((self.reuse_checks / "manifest.json").read_bytes()),
            "raw_log_sha256": digest(log.encode()),
        }
        for filename in ("rust-extended.stdout", "rust-extended.stderr"):
            shutil.copy2(self.reuse_checks / filename, self.output / filename)
        return True

    def run(self) -> Path:
        self.output.mkdir(parents=True, exist_ok=False)
        try:
            self.prepare_extended()
            if self.language == "cpp20":
                self.production_certificate()
            if self.reuse_rust():
                good = True
            elif self.language == "rust":
                r = self.command(
                    [
                        str(self.bin / "kani-driver"),
                        str(self.output / "contracts.rs"),
                        "-j",
                        str(self.jobs),
                        "--output-format",
                        "terse",
                    ],
                    "rust-extended",
                )
                self.manifest["checks"] = kani_result(r.stdout, r.returncode, set(ASSERTIONS))
                good = self.manifest["checks"]["status"] == "PROVED"
            else:
                with ThreadPoolExecutor(max_workers=self.jobs) as pool:
                    self.manifest["checks"] = list(
                        pool.map(lambda h: self.cpp_check(self.output, h, h), ASSERTIONS)
                    )
                good = all(r["status"] == "PROVED" for r in self.manifest["checks"])
            self.controls()
            self.native_controls()
            if good and all(c["detected"] for c in self.manifest["negative_controls"].values()):
                self.manifest.update(
                    status="BOUNDED_CONTRACTS_PROVED",
                    claim=(
                        "All 69 source-bound obligations and five mutation controls passed. "
                        "Production decisions satisfy the adapter, pivot and FFT specifications. "
                        "Copy/transpose preserve arbitrary 64-bit elements in all 64 shapes 1..8. "
                        "Public adapters and upstream backends remain outside this theorem."
                    ),
                )
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
            self.manifest["error"] = str(exc)
        self.manifest["commands"] = self.commands
        self.manifest["finished_at"] = datetime.now(UTC).isoformat()
        (self.output / "manifest.json").write_text(json.dumps(self.manifest, indent=2) + "\n")
        (self.output / "report.md").write_text(
            f"# Extended production contracts ({self.language})\n\n"
            f"Status: `{self.manifest['status']}`\n\n"
            + self.manifest["claim"]
            + "\n\nAssumptions:\n\n"
            + "\n".join(f"- {s}" for s in self.manifest["assumptions"])
            + "\n\nExclusions:\n\n"
            + "\n".join(f"- {s}" for s in self.manifest["exclusions"])
            + f"\n\nError: {self.manifest.get('error', 'none')}\n"
        )
        return self.output
