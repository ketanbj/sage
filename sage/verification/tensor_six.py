"""Compositional ordered-expression proofs of the six public Tensor operations.

Expression equality is stronger than an algebraic equality: it preserves operand
indices, positive-zero initialization and the exact order of every FP operation.
No associativity, reassociation, sampled inputs or numerical stubs are used.
"""

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

OPERATIONS = ("copy", "add", "multiply", "transpose", "matmul", "scale")
OBLIGATIONS = [
    (op, m, k, n)
    for op in OPERATIONS
    for m in range(1, 5)
    for k in range(1, 5)
    for n in (range(1, 5) if op == "matmul" else [1])
]
RELATION = "ordered expression matches specification"


def name(item: tuple[str, int, int, int]) -> str:
    op, m, k, n = item
    return f"{op}_{m}x{k}" + (f"x{n}" if op == "matmul" else "")


def lower_cpp(source: str, scalar: str) -> str:
    """Materialize one template, preserving all computational method statements."""
    marker = "template<class Scalar> struct NativeArithmetic"
    end = "template<class Scalar, class Arithmetic = NativeArithmetic<Scalar>> class BasicTensor"
    if source.count(marker) != 1 or source.count(end) != 1:
        raise ValueError("public Tensor template binding changed")
    start, stop = source.index(marker), source.index(end)
    source = source[:start] + source[stop:]
    source = source.replace(end, "class BasicTensor")
    source = source.replace("using Tensor = BasicTensor<double>;", "")
    source = source.replace("Scalar", scalar)
    source = source.replace(
        "Arithmetic::",
        ("ExpressionArithmetic::" if scalar == "Code" else "NativeBoundArithmetic::"),
    )
    source = source.replace(f"std::array<{scalar}, 16>", "std::array")
    source = source.replace(f"std::span<const {scalar}>", "std::span")
    source = source.replace(
        "return {data_.data(), size()};", "return std::span(data_.data(), size());"
    )
    source = "\n".join(line for line in source.splitlines() if not line.startswith("#include <"))
    return source.replace("#pragma once", '#pragma once\n#include "compat.hpp"') + "\n"


def cpp_entry(item: tuple[str, int, int, int], *, symbolic: bool, lowered: bool) -> str:
    op, m, k, n = item
    rows, cols = (k, m) if op == "transpose" else (m, n) if op == "matmul" else (m, k)
    br, bc = (k, n) if op == "matmul" else (m, k)
    scalar = "Code" if symbolic else "double"
    cls = (
        "sage_cpp::BasicTensor"
        if lowered
        else (
            "sage_cpp::BasicTensor<Code,ExpressionArithmetic>" if symbolic else "sage_cpp::Tensor"
        )
    )
    span = "std::span" if lowered else f"std::span<const {scalar}>"
    method = {
        "copy": "a.copy()",
        "add": "a.added(b)",
        "multiply": "a.multiplied(b)",
        "transpose": "a.transposed()",
        "matmul": "a.matmul(b)",
        "scale": "a.scaled(bb[0])",
    }[op]
    return f"""
extern "C" void entry_{name(item)}(const {scalar}* aa,const {scalar}* bb,
                                  {scalar}* output,unsigned* shape) {{
 {cls} a={cls}::from_values({m},{k},{span}(aa,{m * k}));
 {cls} b={cls}::from_values({br},{bc},{span}(bb,{br * bc}));
 {cls} out={method};
 shape[0]=out.rows(); shape[1]=out.cols();
 for(unsigned r=0;r<{rows};++r) for(unsigned c=0;c<{cols};++c)
  output[r*{cols}+c]=out.at(r,c);
}}
"""


def cpp_harness(item: tuple[str, int, int, int]) -> str:
    op, m, k, n = item
    rows, cols = (k, m) if op == "transpose" else (m, n) if op == "matmul" else (m, k)
    return (
        '#include "expression.hpp"\n#include "tensor-lowered.hpp"\n'
        + cpp_entry(item, symbolic=True, lowered=True)
        + f'''
int main() {{
 Code a[16],b[16],output[16]; unsigned shape[2];
 for(unsigned i=0;i<16;++i) {{a[i]=leaf(i);b[i]=leaf(i+16);output[i]=0;}}
 entry_{name(item)}(a,b,output,shape);
 __CPROVER_assert(shape[0]=={rows} && shape[1]=={cols},"output shape matches specification");
 for(unsigned r=0;r<{rows};++r) for(unsigned c=0;c<{cols};++c)
  __CPROVER_assert(output[r*{cols}+c]==expected({OPERATIONS.index(op)},{m},{k},{n},r,c),
                   "{RELATION}");
 for(unsigned i=0;i<16;++i) {{
  __CPROVER_assert(a[i]==leaf(i),"first input unchanged");
  __CPROVER_assert(b[i]==leaf(i+16),"second input unchanged");
 }}
}}
'''
    )


def mutate_rust(source: str, op: str) -> str:
    pairs = {
        "copy": (
            "pub fn from_vec(shape: Vec<usize>, data: Vec<T>)",
            "pub fn from_vec(shape: Vec<usize>, mut data: Vec<T>)",
        ),
        "add": (".zip(&b.data)", ".zip(&self.data)"),
        "multiply": (".zip(&b.data)", ".zip(&self.data)"),
        "transpose": (
            "data.push(self.get(&indices)?.clone());",
            "data.push(self.data[self.offset].clone());",
        ),
        "matmul": ("b.data[p * n + j]", "b.data[(p * n + j + 1) % (k * n)]"),
        "scale": (
            "self.data.iter().map(|&x| f(x)).collect()",
            "self.data.iter().map(|_| f(self.data[0])).collect()",
        ),
    }
    old, new = pairs[op]
    if source.count(old) != 1:
        raise ValueError(f"Rust {op} mutation binding changed")
    source = source.replace(old, new)
    if op == "copy":
        old = "let (strides, size) = layout(&shape)?;"
        start = source.index("pub fn from_vec")
        stop = source.index("    fn offset", start)
        section = source[start:stop]
        if section.count(old) != 1:
            raise ValueError("Rust constructor mutation binding changed")
        source = (
            source[:start]
            + section.replace(old, old + "\n        if data.len()>1 {data.swap(0,1);}")
            + source[stop:]
        )
    return source


def mutate_cpp(source: str, op: str) -> str:
    pairs = {
        "copy": ("output[i] = input[i];", "output[i] = input[(i+1)%(rows*cols)];"),
        "transpose": ("input[r * cols + c];", "input[(r * cols + c + 1)%(rows*cols)];"),
        "add": (
            "Arithmetic::add(data_[i], other.data_[i])",
            "Arithmetic::add(data_[i], other.data_[0])",
        ),
        "multiply": (
            "Arithmetic::multiply(data_[i], other.data_[i])",
            "Arithmetic::multiply(data_[i], other.data_[0])",
        ),
        "scale": (
            "Arithmetic::multiply(scalar, data_[i])",
            "Arithmetic::multiply(scalar, data_[0])",
        ),
        "matmul": ("other.at(k, c)", "other.at(k, (c+1)%other.cols_)"),
    }
    old, new = pairs[op]
    if source.count(old) != 1:
        raise ValueError(f"C++ {op} mutation binding changed")
    return source.replace(old, new)


def native_cpp(item: tuple[str, int, int, int]) -> str:
    op, m, k, n = item
    rows, cols = (k, m) if op == "transpose" else (m, n) if op == "matmul" else (m, k)
    expression = {
        "copy": f"a[r*{k}+c]",
        "transpose": f"a[c*{k}+r]",
        "add": f"a[r*{k}+c]+b[r*{k}+c]",
        "multiply": f"a[r*{k}+c]*b[r*{k}+c]",
        "scale": f"b[0]*a[r*{k}+c]",
        "matmul": "0.",
    }[op]
    reduction = f"for(unsigned p=0;p<{k};++p) e+=a[r*{k}+p]*b[p*{n}+c];" if op == "matmul" else ""
    return (
        '#include "tensor.hpp"\n#include <bit>\n'
        + cpp_entry(item, symbolic=False, lowered=False)
        + f"""
int main() {{
 double a[16],b[16],out[16]={{}}; unsigned shape[2];
 for(unsigned i=0;i<16;++i){{a[i]=(i+1)/8.;b[i]=(i+17)/8.;}}
 entry_{name(item)}(a,b,out,shape);
 if(shape[0]!={rows} || shape[1]!={cols}) return 3;
 for(unsigned r=0;r<{rows};++r) for(unsigned c=0;c<{cols};++c) {{
  double e={expression}; {reduction}
  if(std::bit_cast<unsigned long long>(out[r*{cols}+c])!=
     std::bit_cast<unsigned long long>(e)) return 3;
 }}
 return 0;
}}
"""
    )


def native_rust(item: tuple[str, int, int, int]) -> str:
    op, m, k, n = item
    rows, cols = (k, m) if op == "transpose" else (m, n) if op == "matmul" else (m, k)
    br, bc = (k, n) if op == "matmul" else (m, k)
    method = {
        "copy": "a.clone()",
        "add": "a.zip(&b,|x,y|x+y).unwrap()",
        "multiply": "a.zip(&b,|x,y|x*y).unwrap()",
        "transpose": "a.permute(&[1,0]).unwrap()",
        "matmul": "a.matmul(&b).unwrap()",
        "scale": "a.map(|x|bv[0]*x)",
    }[op]
    expression = {
        "copy": f"av[r*{k}+c]",
        "transpose": f"av[c*{k}+r]",
        "add": f"av[r*{k}+c]+bv[r*{k}+c]",
        "multiply": f"av[r*{k}+c]*bv[r*{k}+c]",
        "scale": f"bv[0]*av[r*{k}+c]",
        "matmul": "0.0f64",
    }[op]
    reduction = f"for p in 0..{k} {{e+=av[r*{k}+p]*bv[p*{n}+c];}}" if op == "matmul" else ""
    return f"""
#![allow(dead_code,unused_mut)]
#[path="tensor_source.rs"] mod tensor;
fn main() {{
 let av:Vec<f64>=(0..{m * k}).map(|i|(i+1) as f64/8.).collect();
 let bv:Vec<f64>=(0..{br * bc}).map(|i|(i+17) as f64/8.).collect();
 let a=tensor::Tensor::from_vec(vec![{m},{k}],av.clone()).unwrap();
 let b=tensor::Tensor::from_vec(vec![{br},{bc}],bv.clone()).unwrap();
 let out={method};
 if out.shape()!=&[{rows},{cols}] || out.strides()!=&[{cols},1] {{std::process::exit(3);}}
 for r in 0..{rows} {{for c in 0..{cols} {{
  let mut e={expression}; {reduction}
  if out.get(&[r,c]).unwrap().to_bits()!=e.to_bits() {{std::process::exit(3);}}
 }}}}
}}
"""


class TensorSixProofRun(ProofRun):
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
            schema_version="sage-tensor-expression-proof-1.0",
            target_language=language,
            profile="tensor-six",
            operations=list(OPERATIONS),
            scope="Public Tensor constructor, six methods, shape, strides/indexing and ownership",
            obligations=[name(x) for x in OBLIGATIONS],
            assumptions=[
                "Rank-two contiguous owned tensors, each dimension 1..4; successful allocation.",
                "Each leaf represents an arbitrary independent input, not a sampled value.",
                "Arithmetic means deterministic binary64 + and *, with +0 initialization.",
                "For cross-language and upstream claims, inputs/scalar are signed bytes /8.",
                "Round-to-nearest, no fast-math, reassociation or fused multiply-add.",
                "Trusted Kani 0.68.0/CBMC 6.11.0, Clang 18 and standard-library memory models.",
                "Injective base-64 prefix-tree encoding (at most 17 tokens /102 bits).",
            ],
            exclusions=[
                "External upstream BLAS, public Einsums planner/dispatch/SIMD/OpenMP.",
                "General Array fallback, other sizes/ranks/dtypes, aliasing and invalid inputs.",
                "JSON/FFI/Python parsing and serialization are replay-tested, not model-checked.",
                "NaN payloads, floating-point environment changes, allocation/lifetime failures.",
                "The arithmetic interpretation and compiler are trusted, not verified toolchains.",
            ],
            claim="No proof result yet.",
        )

    def prepare_six(self) -> None:
        source = self.root / "verification/einsums/six"
        for filename in ("expression.rs", "expression.hpp", "compat.hpp", "tensor.rs"):
            shutil.copy2(source / filename, self.output / filename)
        shutil.copy2(self.root / "ports/einsums-rs/src/tensor.rs", self.output / "tensor_source.rs")
        harness = (self.output / "tensor.rs").read_text()
        old = '#[path = "../../../ports/einsums-rs/src/tensor.rs"]'
        if harness.count(old) != 1:
            raise ValueError("six-operation Rust source binding changed")
        (self.output / "tensor.rs").write_text(harness.replace(old, '#[path = "tensor_source.rs"]'))
        for filename in ("tensor.hpp", "kernels.hpp"):
            shutil.copy2(self.root / "ports/einsums-cpp" / filename, self.output / filename)
        shutil.copy2(Path(__file__), self.output / "proof_runner.py")
        shutil.copy2(Path(__file__).with_name("einsums.py"), self.output / "proof_support.py")
        bindings = [
            "ports/einsums-rs/src/api/bounded_tensor.rs",
            "ports/einsums-rs/src/api/mod.rs",
            "ports/einsums-rs/src/protocol.rs",
            "ports/einsums-cpp/api/bounded_tensor.hpp",
            "ports/einsums-cpp/api/execute.cpp",
            "ports/einsums-cpp/driver.cpp",
            "ports/einsums-cpp/library_driver.cpp",
        ]
        self.manifest["public_api_bindings"] = {}
        for path in bindings:
            dest = self.output / "bindings" / path
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.root / path, dest)
            self.manifest["public_api_bindings"][path] = digest(dest.read_bytes())
        self.manifest["source_hashes"] = {
            p.name: digest(p.read_bytes()) for p in self.output.iterdir() if p.is_file()
        }
        for tool, version in (("kani-driver", KANI_VERSION), ("cbmc", CBMC_VERSION)):
            check = self.command([str(self.bin / tool), "--version"], f"{tool}-version")
            if check.returncode or version not in check.stdout:
                raise ValueError(f"wrong {tool} version")
        check = self.command(
            ["docker", "image", "inspect", "--format", "{{.Id}}", self.image], "image"
        )
        if check.returncode or not check.stdout.strip().startswith("sha256:"):
            raise ValueError("compiler image unavailable")
        self.image = check.stdout.strip()
        self.manifest["tools"] = {
            "kani": KANI_VERSION,
            "cbmc": CBMC_VERSION,
            "compiler_image": self.image,
        }

    def lower_in(self, folder: Path, scalar: str = "Code") -> None:
        (folder / "tensor-lowered.hpp").write_text(
            lower_cpp((folder / "tensor.hpp").read_text(), scalar)
        )
        (folder / "compat.hpp").write_text(
            (self.root / "verification/einsums/six/compat.hpp")
            .read_text()
            .replace("SCALAR", scalar)
        )
        head = ""
        if scalar == "double":
            head = (
                "struct NativeBoundArithmetic {static double add(double a,double b){return a+b;}"
                "static double multiply(double a,double b){return a*b;}};\n" + head
            )
        path = folder / "tensor-lowered.hpp"
        path.write_text(head + path.read_text())

    def public_certificate(self) -> bool:
        folder = self.output / "certificate"
        folder.mkdir()
        for p in ("tensor.hpp", "kernels.hpp", "expression.hpp"):
            shutil.copy2(self.output / p, folder / p)
        self.lower_in(folder, "double")
        for lowered in (False, True):
            entry = '#include "tensor-lowered.hpp"\n' if lowered else '#include "tensor.hpp"\n'
            entry += "\n".join(cpp_entry(x, symbolic=False, lowered=lowered) for x in OBLIGATIONS)
            (folder / ("lowered.cpp" if lowered else "modern.cpp")).write_text(entry)
        flags = (
            "-fno-autolink -O2 -fno-strict-aliasing -mllvm -inline-threshold=100000 "
            "-mllvm -enable-noalias-to-md-conversion=false "
            "-ffp-contract=off -fno-vectorize -fno-slp-vectorize -S -emit-llvm"
        )
        result = self.docker(
            f"clang++-18 -std=c++20 {flags} /work/certificate/modern.cpp "
            "-o /work/certificate/modern.ll && "
            f"clang++-18 -std=c++11 {flags} /work/certificate/lowered.cpp "
            "-o /work/certificate/lowered.ll",
            "public-method-certificate",
        )
        if result.returncode:
            return False
        a = normalize_ir((folder / "modern.ll").read_text())
        b = normalize_ir((folder / "lowered.ll").read_text())
        self.manifest["public_method_certificate"] = {
            "identical_optimized_ir": a == b,
            "entries": len(OBLIGATIONS),
            "normalization": "Remove only ModuleID and source_filename lines.",
            "modern_ir_sha256": digest(a.encode()),
            "lowered_ir_sha256": digest(b.encode()),
            "flags": flags,
        }
        if a != b:
            return False
        symbolic = self.output / "expression-certificate"
        symbolic.mkdir()
        for filename in ("tensor.hpp", "kernels.hpp", "expression.hpp"):
            shutil.copy2(self.output / filename, symbolic / filename)
        self.lower_in(symbolic)
        for lowered in (False, True):
            entry = '#define __CPROVER_assert(p,d) ((void)0)\n#include "expression.hpp"\n'
            entry += '#include "tensor-lowered.hpp"\n' if lowered else '#include "tensor.hpp"\n'
            entry += "\n".join(cpp_entry(x, symbolic=True, lowered=lowered) for x in OBLIGATIONS)
            (symbolic / ("lowered.cpp" if lowered else "modern.cpp")).write_text(entry)
        result = self.docker(
            f"clang++-18 -std=c++20 {flags} /work/expression-certificate/modern.cpp "
            "-o /work/expression-certificate/modern.ll && "
            f"clang++-18 -std=c++11 {flags} /work/expression-certificate/lowered.cpp "
            "-o /work/expression-certificate/lowered.ll",
            "expression-certificate",
        )
        if result.returncode:
            return False
        a = normalize_ir((symbolic / "modern.ll").read_text())
        b = normalize_ir((symbolic / "lowered.ll").read_text())
        self.manifest["expression_lowering_certificate"] = {
            "identical_optimized_ir": a == b,
            "entries": len(OBLIGATIONS),
            "modern_ir_sha256": digest(a.encode()),
            "lowered_ir_sha256": digest(b.encode()),
            "normalization": "Remove only ModuleID and source_filename lines.",
            "flags": flags,
        }
        return a == b

    def check_cpp(
        self, folder: Path, item: tuple[str, int, int, int], label: str
    ) -> dict[str, Any]:
        source = folder / f"{name(item)}.cpp"
        source.write_text(cpp_harness(item))
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
            label,
        )
        parsed = cbmc_result(result.stdout, result.returncode, RELATION)
        if parsed["status"] == "PROVED":
            descriptions = [
                p["description"] for e in json.loads(result.stdout) for p in e.get("result", [])
            ]
            if not all(
                any(x in d for d in descriptions)
                for x in (
                    RELATION,
                    "output shape matches",
                    "first input unchanged",
                    "second input unchanged",
                )
            ):
                parsed["status"] = "INCONCLUSIVE"
        return {"obligation": name(item), **parsed}

    def method_checks(self) -> None:
        if self.reuse_checks:
            if self.language == "cpp20":
                self.lower_in(self.output)
            self.reuse_method_checks()
            return
        if self.language == "rust":
            result = self.command(
                [
                    str(self.bin / "kani-driver"),
                    str(self.output / "tensor.rs"),
                    "-j",
                    str(self.jobs),
                    "--output-format",
                    "terse",
                ],
                "rust-six",
            )
            self.manifest["rust_checks"] = kani_result(
                result.stdout, result.returncode, {name(x) for x in OBLIGATIONS}
            )
        else:
            self.lower_in(self.output)
            with ThreadPoolExecutor(max_workers=self.jobs) as pool:
                self.manifest["cpp_checks"] = list(
                    pool.map(lambda x: self.check_cpp(self.output, x, name(x)), OBLIGATIONS)
                )

    def reuse_method_checks(self) -> None:
        """Reuse only complete successes with identical proof inputs and pinned tools."""
        assert self.reuse_checks is not None
        source = self.reuse_checks
        previous = json.loads((source / "manifest.json").read_text())
        if (
            previous.get("target_language") != self.language
            or previous.get("profile") != "tensor-six"
            or previous.get("tools") != self.manifest["tools"]
        ):
            raise ValueError("reused proof language/profile/toolchain differs")
        files = (
            ("tensor_source.rs", "tensor.rs", "expression.rs")
            if self.language == "rust"
            else ("tensor.hpp", "kernels.hpp", "expression.hpp")
        )
        hashes = {}
        for f in files:
            expected = digest((self.output / f).read_bytes())
            if (
                digest((source / f).read_bytes()) != expected
                or previous["source_hashes"][f] != expected
            ):
                raise ValueError(f"reused proof input differs: {f}")
            hashes[f] = expected
        if self.language == "cpp20":
            if (
                previous["source_hashes"]["compat.hpp"]
                != self.manifest["source_hashes"]["compat.hpp"]
            ):
                raise ValueError("reused standard-library model differs")
            for f in ("tensor-lowered.hpp", "compat.hpp"):
                expected = digest((self.output / f).read_bytes())
                if digest((source / f).read_bytes()) != expected:
                    raise ValueError(f"reused materialized proof input differs: {f}")
                hashes[f] = expected
        logs = {}
        if self.language == "rust":
            log = (source / "rust-six.stdout").read_text()
            matches = [
                c
                for c in previous["commands"]
                if Path(c["args"][0]).name == "kani-driver"
                and "--harness" not in c["args"]
                and "--output-format" in c["args"]
            ]
            if len(matches) != 1:
                raise ValueError("reused Rust verification command is ambiguous")
            result = kani_result(log, matches[0]["returncode"], {name(x) for x in OBLIGATIONS})
            if result["status"] != "PROVED":
                raise ValueError("reused Rust method obligations are incomplete")
            self.manifest["rust_checks"] = result
            shutil.copy2(source / "rust-six.stdout", self.output / "rust-six.stdout")
            shutil.copy2(source / "rust-six.stderr", self.output / "rust-six.stderr")
            logs["rust-six.stdout"] = digest(log.encode())
        else:
            checks = []
            for item in OBLIGATIONS:
                label = name(item)
                harness = cpp_harness(item)
                if (source / f"{label}.cpp").read_text() != harness:
                    raise ValueError(f"reused C++ harness differs: {label}")
                hashes[f"{label}.cpp"] = digest(harness.encode())
                log = (source / f"{label}.stdout").read_text()
                matches = [
                    c
                    for c in previous["commands"]
                    if Path(c["args"][0]).name == "cbmc"
                    and Path(c["args"][1]) == source / f"{label}.cpp"
                ]
                if len(matches) != 1:
                    raise ValueError(f"reused C++ verification command missing: {label}")
                result = cbmc_result(log, matches[0]["returncode"], RELATION)
                if result["status"] != "PROVED":
                    raise ValueError(f"reused C++ obligation is incomplete: {label}")
                checks.append({"obligation": label, **result})
                logs[f"{label}.stdout"] = digest(log.encode())
                shutil.copy2(source / f"{label}.stdout", self.output / f"{label}.stdout")
            self.manifest["cpp_checks"] = checks
        self.manifest["reused_method_checks"] = {
            "bundle": str(source),
            "manifest_sha256": digest((source / "manifest.json").read_bytes()),
            "identical_proof_input_hashes": hashes,
            "raw_log_hashes": logs,
            "reason": "Successful methods reused; certificates and fault controls rerun.",
        }

    def fault_controls(self) -> None:
        results = {}
        for op in OPERATIONS:
            folder = self.output / f"negative-{op}"
            folder.mkdir()
            for f in (
                "tensor.hpp",
                "kernels.hpp",
                "expression.hpp",
                "tensor.rs",
                "expression.rs",
                "tensor_source.rs",
            ):
                shutil.copy2(self.output / f, folder / f)
            item = (op, 2, 3, 4 if op == "matmul" else 1)
            if self.language == "cpp20":
                file = folder / ("kernels.hpp" if op in ("copy", "transpose") else "tensor.hpp")
                file.write_text(mutate_cpp(file.read_text(), op))
                self.lower_in(folder)
                check = self.check_cpp(folder, item, f"negative-{op}")
                detected = check["status"] == "DISPROVED" and any(
                    RELATION in f["description"] for f in check["failures"]
                )
            else:
                file = folder / "tensor_source.rs"
                file.write_text(mutate_rust(file.read_text(), op))
                harness = folder / "tensor.rs"
                lines = harness.read_text().splitlines()
                harness.write_text(
                    "\n".join(
                        line
                        for line in lines
                        if not line.startswith("proof!(")
                        or line.startswith(f"proof!({name(item)},")
                    )
                    + "\n"
                )
                result = self.command(
                    [
                        str(self.bin / "kani-driver"),
                        str(folder / "tensor.rs"),
                        "--harness",
                        name(item),
                        "--output-format",
                        "regular",
                    ],
                    f"negative-{op}",
                )
                detected = (
                    result.returncode != 0
                    and RELATION in result.stdout
                    and "VERIFICATION:- FAILED" in result.stdout
                    and "0 successfully verified harnesses, 1 failures, 1 total" in result.stdout
                )
            results[op] = {"detected": detected}
        self.manifest["negative_controls"] = results

    def native_controls(self) -> dict[str, Any]:
        """Reproduce every source mutation in real binary64, not just the expression model."""
        outcomes = {}
        for op in OPERATIONS:
            item = (op, 2, 3, 4 if op == "matmul" else 1)
            folder = self.output / f"negative-{op}"
            extension = "cpp" if self.language == "cpp20" else "rs"
            content = native_cpp(item) if self.language == "cpp20" else native_rust(item)
            baseline = self.output / f"native-{op}.{extension}"
            mutant = folder / f"native-{op}.{extension}"
            baseline.write_text(content)
            mutant.write_text(content)
            if self.language == "cpp20":
                build = self.docker(
                    f"clang++-18 -std=c++20 -O2 -ffp-contract=off /work/native-{op}.cpp "
                    f"-o /work/native-{op} && "
                    f"clang++-18 -std=c++20 -O2 -ffp-contract=off "
                    f"/work/negative-{op}/native-{op}.cpp -o /work/negative-{op}/native-{op}",
                    f"native-build-{op}",
                )
                if build.returncode:
                    raise ValueError(f"native replay compilation failed for {op}")
                original = self.docker(f"/work/native-{op}", f"native-baseline-{op}")
                modified = self.docker(f"/work/negative-{op}/native-{op}", f"native-mutant-{op}")
            else:
                for source in (baseline, mutant):
                    result = self.command(
                        [
                            "rustc",
                            "--edition=2021",
                            "-C",
                            "opt-level=2",
                            "-C",
                            "target-feature=-fma",
                            str(source),
                            "-o",
                            str(source.with_suffix("")),
                        ],
                        f"native-build-{op}-{'mutant' if source == mutant else 'baseline'}",
                    )
                    if result.returncode:
                        raise ValueError(f"native replay compilation failed for {op}")
                original = self.command([str(baseline.with_suffix(""))], f"native-baseline-{op}")
                modified = self.command([str(mutant.with_suffix(""))], f"native-mutant-{op}")
            outcomes[op] = {
                "baseline_passed": original.returncode == 0,
                "mutant_failed_exact_output": modified.returncode == 3,
                "shape": [item[1], item[2], item[3]],
                "a_values": [(i + 1) / 8 for i in range(16)],
                "b_values": [(i + 17) / 8 for i in range(16)],
            }
        report = {
            "status": "PASS"
            if all(
                v["baseline_passed"] and v["mutant_failed_exact_output"] for v in outcomes.values()
            )
            else "FAIL",
            "controls": outcomes,
            "checker_source_sha256": digest(Path(__file__).read_bytes()),
        }
        (self.output / "native-fault-replay.json").write_text(json.dumps(report, indent=2))
        self.manifest["native_fault_replay"] = report
        return report

    def run(self) -> Path:
        self.output.mkdir(parents=True, exist_ok=False)
        try:
            self.prepare_six()
            if self.language == "cpp20" and not self.public_certificate():
                raise ValueError("C++ public-method compiler identity certificate failed")
            self.method_checks()
            self.fault_controls()
            replay = self.native_controls()
            good = (
                self.manifest.get("rust_checks", {}).get("status") == "PROVED"
                if self.language == "rust"
                else len(self.manifest.get("cpp_checks", [])) == len(OBLIGATIONS)
                and all(c["status"] == "PROVED" for c in self.manifest["cpp_checks"])
            )
            if (
                good
                and replay["status"] == "PASS"
                and all(c["detected"] for c in self.manifest["negative_controls"].values())
            ):
                self.manifest["status"] = "BOUNDED_TENSOR_API_PROVED"
                self.manifest["claim"] = (
                    "All 144 public Tensor obligations preserve the exact ordered expression "
                    "specified for the six operations, including shape and unchanged inputs. "
                    "Interpreting those expressions as binary64 establishes bounded functional "
                    "equivalence under the recorded assumptions. Public JSON/FFI/Python paths "
                    "route this domain to these methods; the adapters require native replay."
                )
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
            self.manifest["error"] = str(exc)
        self.manifest["commands"] = self.commands
        self.manifest["finished_at"] = datetime.now(UTC).isoformat()
        (self.output / "manifest.json").write_text(json.dumps(self.manifest, indent=2))
        (self.output / "report.md").write_text(
            f"# Six-operation public Tensor proof ({self.language})\n\n"
            f"Status: `{self.manifest['status']}`\n\n{self.manifest['claim']}\n\n"
            "## Assumptions\n\n"
            + "\n".join(f"- {s}" for s in self.manifest["assumptions"])
            + "\n\n## Exclusions\n\n"
            + "\n".join(f"- {s}" for s in self.manifest["exclusions"])
            + f"\n\nError: {self.manifest.get('error', 'none')}\n"
        )
        return self.output
