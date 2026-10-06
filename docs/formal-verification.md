# Bounded formal equivalence pilot

The [six-operation extension](tensor-six-proof.md) now covers production public
Tensor methods in both ports and connects the bounded domain to their public
JSON/FFI/Python APIs. It adds 144 ordered-expression obligations per language;
the scalar-kernel pilot below remains separate upstream evidence.

The [modern C++ extension](modern-cpp.md) adds `sage prove --target einsums
--language cpp20`. It directly pairs the upstream scalar kernel with the unchanged
production kernels in `ports/einsums-cpp/kernels.hpp`. On 2026-10-05 all 32 paired
obligations, both source-binding certificates, both fault detections and both
native counterexample replays passed. The C++20 wrapper is tested natively and is
outside that proof. The Rust workflow below remains available with `--language rust`.

SAGE now has a separate `sage prove` workflow. It checks the pinned Einsums HPTT
scalar kernel and the actual checked-in Rust `Tensor::clone` and `Tensor::permute`
against the same exact copy/transpose specification. Successful obligations on both
sides establish equivalence for that kernel and domain, conditional on the stated
toolchain and memory assumptions.

This result does not establish equivalence of the complete public Einsums call path.
The ordinary C++ transpose wrapper constructs an HPTT plan and may dispatch SIMD
kernels. The pilot directly checks the scalar kernel with explicit parameters.
Planner correctness, dispatch, SIMD, OpenMP and the public C++ Tensor metadata remain
outside the proof. No existing full-library completion gate changes.

The baseline run on 2026-10-04, `runs/20261004-einsums-bounded-proof-final`,
completed with `BOUNDED_EQUIVALENCE_PROVED`: all 32 C++ and 32 Rust obligations,
the compiler identity check, both fault detections and both native replays passed.
Its source snapshots and hashes identify the exact code certified by that run.

## Scope and specification

The domain contains all 16 matrix shapes with each dimension from 1 to 4. Every
active value is an arbitrary signed byte divided by eight in binary64, matching
the numerical domain of the existing campaign. These are symbolic inputs, not
sampled or replayed cases. Each shape receives one copy and one transpose obligation
on each implementation, for 32 C++ and 32 Rust obligations.

- Copy: output element `(r,c)` has exactly the bits of input element `(r,c)`.
- Transpose: output element `(r,c)` has exactly the bits of input element `(c,r)`.
- Both preserve the input and stay within the declared valid buffers.
- Rust also proves output shape and contiguous row-major strides.
- C++ also proves that inactive output elements remain unchanged.

C++ checks use `double`, alpha one, beta zero, conjugation disabled and nonoverlapping
buffers with capacity for 16 elements. Allocation failure is outside the Rust
domain: Kani's default allocator model assumes successful allocation. Arbitrary
floating-point patterns, larger dimensions, other dtypes, aliasing, failures,
the protocol decoder, the newer Rust Array API and Python bindings remain excluded.

The verified Rust file is an unchanged snapshot of
`ports/einsums-rs/src/tensor.rs`, imported into a standalone harness. No numerical
operation is replaced with a stub. Other Rust methods may have unsupported constructs,
but Kani rejects them if reachable from the selected harnesses.

## Binding the C++ proof to the source

The upstream source is pinned to Einsums commit
`22a115978041e905461b24d9ca2a17bfcce01f32`. The runner requires the exact SHA-256 of
`libs/Einsums/HPTT/src/Transpose.cpp` before extracting `macro_kernel_scalar`.

CBMC's C++11 frontend cannot parse `if constexpr`. The runner mechanically
materializes the template arguments `betaIsZero=true`, `floatType=double` and
`conjA=false`, replacing that one `if constexpr` with a constant `if`. All
computational statements remain verbatim. The unused conjugation branch receives
an identity helper to make it well-formed; the helper is unreachable in this scope.

As an additional source-binding check, Clang 18 compiles both the original template
specialization and the CBMC-compatible source. Their optimized LLVM modules must
be identical after removing only the ModuleID and source_filename lines. The bundle
retains both sources, both LLVM modules and the normalized IR digest. Clang is part
of the trusted toolchain. This compiler identity check is not presented as a
separate verified-compiler theorem.

CBMC checks exact output bits, pointer/array bounds, overflow and loop unwinding
completeness. Kani checks the Rust assertions, panic/safety properties and unwinding
completeness. All obligations must complete successfully. Unknown results, missing
assertions, timeout, unsupported reachable code and missing harnesses fail closed.

## Setup and execution

The checked-in setup script currently supports macOS arm64 and pins Kani 0.68.0,
its CBMC 6.11.0 bundle, the official release archive digest and its required Rust
nightly. It installs under `.sage/verification` and does not change the default
Rust toolchain. Setup downloads dependencies. Verification uses local inputs and
network-disabled compiler containers.

```console
make setup-verification
make build-einsums-container
uv run sage target prepare --target einsums
uv run sage prove --target einsums
```

The cached image `sage-einsums:22a1159` must exist and Docker must be running.
The proof records its immutable image ID and uses that ID for all compiler steps.
The runner records installed verifier versions and rejects unexpected versions.
On other supported Kani platforms, add an explicitly pinned release digest and
validate the setup before extending the setup script.

Optional controls:

```console
uv run sage prove --target einsums --jobs 2 --timeout 1800 --output runs/my-proof
```

The destination must be new. Results live in their own run bundle, separate from
ordinary campaign manifests. A successful run reports `BOUNDED_EQUIVALENCE_PROVED`.
An incomplete run reports `INCONCLUSIVE` and exits nonzero.

Each successful bundle includes the contract and exclusions, immutable source
snapshots and hashes, tool commands and versions, raw verifier output, compiler
source-binding artifacts, and a Markdown report. Rerunning the command recomputes
all obligations against the current Rust file; old proof bundles cannot certify
changed code.

## Negative controls and replay

Each run mutates isolated snapshots, leaving production code unchanged:

1. Add one eighth to the C++ scalar output. CBMC must disprove the exact output
   assertion. The runner reconstructs a solver input and compiles the original
   and mutant kernels for native replay. The original must pass and the mutant
   must produce the mismatch.
2. Leave the Rust strides unpermuted while changing the shape. Kani must detect
   an assertion failure for the 2×3 transpose. Its generated concrete playback
   test must fail during native playback.

Both fault detections and both replays are mandatory for a successful bundle.
Their purpose is to check that the proof harnesses detect actual source faults.
Replay is additional evidence, not the exhaustive proof itself.

## Next proof boundaries

The next extension should verify HPTT planning/dispatch and the public wrapper
for this small domain, or establish a reviewed refinement contract connecting
those paths to the proved scalar relation. Additional operation families need
their own semantics and dependency coverage. Intentional compatibility changes
must use an appropriate relation rather than asserting identical behavior.

## Tool references

- [Kani installation](https://model-checking.github.io/kani/install-guide.html)
- [Kani verification results](https://model-checking.github.io/kani/verification-results.html)
- [CBMC loop completeness](https://model-checking.github.io/cbmc-training/faq/loop-unwinding.html)
- [Pinned Einsums source](https://github.com/Einsums/Einsums/blob/22a115978041e905461b24d9ca2a17bfcce01f32/libs/Einsums/HPTT/src/Transpose.cpp)
