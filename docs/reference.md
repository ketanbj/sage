# Technical reference

Use this page when you need an exact contract or recorded implementation detail.
For setup, start with [Getting started](getting-started.md); for proof commands,
use [Verification](verification.md).

- [API compatibility](#api-compatibility)
- [Implementation details](#implementation-details)
- [Campaign profiles and input format](#campaign-profiles-and-input-format)
- [Numerical comparison](#numerical-comparison)
- [Source and toolchain pins](#source-and-toolchain-pins)
- [SymSan execution](#symsan-execution)
- [Translation providers](#translation-providers)
- [Proof internals](#proof-internals)
- [Recorded upstream findings](#recorded-upstream-findings)

## API compatibility

Both ports implement the 90 CPU exports of the pinned original Python extension
and its 16 public helpers. The [Rust API inventory](../ports/einsums-rs/api-surface.json)
and [C++ API inventory](../ports/einsums-cpp/api-surface.json) identify that surface.
The scope includes tensors/views, contractions, linear algebra, decomposition,
FFT, storage, HDF5, runtime services and Python packaging. HIP/GPU is excluded.
Export presence does not certify all original calling contracts, C++ overloads,
vendor symbols or binary interfaces.

Python imports are `einsums` and `pyeinsums`. NumPy owns Python buffer storage;
scientific arithmetic uses the selected native library. Install the two packages
in separate environments because their import names coincide. The original
Einsums library is a validation reference, not the candidate's numerical backend.

| Behavior | Port contract or recorded difference |
|---|---|
| Python `syev/heev` | Eigenvectors in rows, matching the pinned Python wrapper; native Rust `eigh` uses columns |
| Python ONE/INFINITY norms | Preserve the pinned transposed-storage convention; native Rust norms use conventional meanings |
| General eigensystems | Eigenvalue order, phases and repeated/defective-root bases can differ |
| Pseudoinverse | Returns `n × m`, with a valid rank threshold and Penrose checks |
| Rectangular QR | Thin factors; the campaign restricts the upstream QR probe to square positive-definite inputs |
| SVD | Useful thin factors for SOME/OVERWRITE and empty factors for NONE; does not reproduce pinned padded outputs or mutate the input |
| Truncated decompositions | Exactly `k` deterministic leading modes; pinned upstream uses `k+5` randomized projected modes |
| Nullspace | Dtype-aware rank threshold; some single-precision rank decisions differ |
| Complex Lyapunov | Implemented; the pinned complex extension throws |
| Views and negation | Stepped views and unary negation extend the pinned Python API; shared tensor replay uses unit-step slices |
| Disk storage | Explicit flush or successful context-manager exit; destructors do not silently write |
| Random factories | Distribution/sign contracts, not identical upstream random samples |
| BadBuffer | Rejects invalid metadata safely instead of constructing unsafe native pointers |

These choices require review when compatibility with upstream behavior is the
acceptance criterion. A mathematical correction is not automatically an approved
compatibility change. Nonunique eigenvectors, SVD completions and nullspace bases
need residual/reconstruction/subspace criteria; literal mismatches remain visible.

HDF5 handles all four dtypes, nested datasets and compressed/endian-converted
reads. Block/tiled storage provides dense conversion. Decompositions include
CP/PARAFAC, weighted CP, Tucker HOSVD/HOOI, reconstruction, unfolding, mode products
and Khatri–Rao products. Runtime initialization/configuration and error services
exist natively and in Python, but their state is separate.

## Implementation details

Rust consumers use `sage_einsums::api::{array,linalg,decomposition,storage,runtime}`
and `api::execute(Request)`. Generic `Tensor<T>`/`View<T>` storage remains available.
Rust locks nalgebra, num-complex, serde and HDF5 dependencies through Cargo.lock.
Its general eigenvectors use triangular Schur solves with SVD fallback.

C++ consumers use `api/api.hpp`, typed DenseTensor/RuntimeTensor storage and
`api::execute()`. `sage_api_request` / `sage_api_free` expose a JSON C interface
that contains errors at the language boundary. The broad backend uses Eigen and
the HDF5 C library; left/right general eigenvectors use SVD nullspaces. Native
views retain owners and check shape/index/read-only contracts.

Both ports use double working precision before conversion to the declared dtype.
Lyapunov uses a Schur triangular solve with quadratic storage instead of an
explicit Kronecker coefficient matrix. FFT is currently a quadratic DFT, and
C++ generic contractions use scalar enumeration. Performance equivalence is
unestablished. Inverse-transform normalization follows the pinned upstream.

Rust builds need Rust 1.84+, a C compiler, CMake and Python 3.11+. C++ builds need
C++20, CMake 3.20+, Eigen 3.4 or 5.x, nlohmann JSON 3.11+ and HDF5 C. Exact commands
and wheel installation are in the [Rust](../ports/einsums-rs/README.md) and
[C++](../ports/einsums-cpp/README.md#build) guides. The C++ wheel builder repairs
macOS HDF5 dependencies; Linux distribution needs its runtime or auditwheel repair.
A dependency-free six-operation C++ build uses `-DSAGE_BUILD_FULL_API=OFF`.

## Campaign profiles and input format

| Configuration | Language | Comparison scope |
|---|---|---|
| `configs/einsums-library.yaml` | Rust, default for Einsums | 23 bounded CPU/Python probes |
| `configs/einsums-cpp-library.yaml` | C++20 | The same 23 probes, with actual Python entrypoints |
| `configs/einsums.yaml` | Rust | Earlier six tensor operations |
| `configs/einsums-cpp.yaml` | C++20 | Earlier six tensor operations |
| `configs/sage.yaml` | No target | Requires an explicit implemented target |

Use `uv run sage run --config <configuration> --provider offline` to select a
profile. The full profiles capture multi-file ports; they do not invoke a model
translator. Their whole-library scope gate remains `INCOMPLETE_SCOPE`.

The binary input is exactly 36 bytes: unsigned operation/M/K/N header bytes,
then two 16-byte signed data buffers. Dimensions are each 1–4; active values are
signed bytes divided by eight. Unused elements are ignored. The six-operation
format is `einsums-tensor-1.0`; the library profile extends the operation IDs.

| IDs | Operations |
|---|---|
| 0–5 | Copy, add, elementwise multiply, transpose, matrix multiply, scale |
| 6–9 | Subtract, divide by abs(B)+1, negate, first-column copy slice |
| 10–16 | Dot, axpy, axpby, gemv, ger, vector norm, RMSD |
| 17–19 | Inverse, symmetric eigenvalues, QR reconstruction on A Aᵀ + I |
| 20–22 | Complex DFT, inverse DFT, frequency coordinates |

For IDs 0–5, A has shape M×K. B has M×K except matrix multiplication, where
B has K×N. Copy/add/multiply/scale output M×K; transpose outputs K×M;
matmul outputs M×N. Scale uses B[0]. Outputs carry JSON shape, strides and values.
The strict decoder rejects wrong lengths or out-of-domain dimensions.

The earlier Rust library runner calls owned tensor Python objects for IDs 0–17
and its campaign C ABI for 18–22. The C++ library runner calls actual public Python
entrypoints for all 23. Each execution records its entrypoint. Neither profile
covers all ranks, dtypes, errors or ownership contracts of the broad API.

## Numerical comparison

Shapes/strides and API dtypes compare exactly where applicable. Campaign value
comparison uses `abs(actual-expected) <= atol + rtol*abs(expected)`, normally
atol 1e-12 and rtol 1e-10 under `einsums-tensor-1.0` or `einsums-library-1.0`.
Nonfinite outputs fail the bounded campaign policy. Signed-zero handling is
recorded in configuration; these tolerances are not universal scientific constants.

The API replay tool uses atol 2e-4 / rtol 5e-4 for float32/complex64 and
atol 1e-8 / rtol 1e-8 for float64/complex128. Complex errors use magnitude;
eigenvalue residuals normalize by matrix scale. Reconstruction, orthogonality,
Penrose identities and eigenpair residuals validate nonunique numerical outputs.
The `k=1` truncation probe resizes generated values deterministically into 8×8
arrays. Proof-domain adapter replay instead uses exact binary64 bit comparisons.

The 31 replay groups are tensor, gemm, gemv, scale, scale_row, scale_column, dot,
true_dot, axpy, axpby, ger, direct_product, norm, vec_norm, sum_square, lu, invert,
gesv, det, syev, heev, geev, svd, svd_dd, svd_nullspace, qr, pseudoinverse,
solve_continuous_lyapunov, truncated_svd, truncated_syev and plan.

Recorded replay disagreement counts are milestone-specific:

| Group | Rust replay | C++ replay |
|---|---:|---:|
| General eigen | 23 | 23 |
| LU | 232 | 232 |
| Pseudoinverse | 512 | 512 |
| Complex Lyapunov | 256 | 256 |
| Nullspace | 43 | 43 |
| Truncated SVD | 512 | 512 |
| Truncated syev | 484 | 478 |
| Total | 2,062 | 2,056 |

An upstream exception or contract difference is `REFERENCE_DISAGREEMENT`, not a
three-way pass or proof of an upstream bug. Candidate failures, process failures
and raw outputs remain separately recorded. Unresolved replay findings return a
nonzero exit.

## Source and toolchain pins

| Component | Recorded baseline |
|---|---|
| Einsums | v1.1.5, `22a115978041e905461b24d9ca2a17bfcce01f32`, MIT |
| SymSan | R-Fuzz/SymSan `ecbe8a7d6a5ceb687df16660d6f3f60f844b5bd4`, Apache-2.0 |
| SymSan environment | Ubuntu 24.04, Linux amd64, Clang/LLVM 18 |
| Z3 | 4.13.3 x64 glibc-2.35 release archive |
| Formal tools | Kani 0.68.0, bundled CBMC 6.11.0, required pinned Rust nightly |
| Docker images | `sage-symsan:ecbe8a7`, `sage-einsums:22a1159`, `sage-einsums-python:22a1159` |

The Z3 archive SHA-256 is
`32c7377026733c9d7b33c21cd77a68f50ba682367207b031a6bfd80140a8722f`.
The macOS arm64 Kani release archive SHA-256 is
`a5d39a5d5e748253a553aa62f295c6c397287927a28e5e32691d7ff2eda0c398`.
The setup script reads the nightly from that verified bundle. Ubuntu's Z3 4.8.12
is too old for this selected SymSan commit; use the checked-in Dockerfile.

Image tags identify intended builds. Runs capture immutable image IDs and execute
those identities; replacing an image under a tag does not reproduce an old run.
Upstream source pins, hashes, licenses, commands and resolved configuration travel
with captured evidence. Docker base/package dependencies remain a residual moving
part until separately locked.

## SymSan execution

Harness builds use the pinned `ko-clang` wrappers, `KO_USE_FASTGEN=1` and
`KO_DONT_OPTIMIZE=1`. The full library profile instruments the C input decoder
at O0 and executes upstream C++ natively. Earlier mixed C++ template/native tracing
hit uninitialized-label failures; decoder-only tracing avoids that problem while
leaving internal library paths unexplored.

The earlier Rust tensor profile retains selected template instrumentation, with
`KO_USE_NATIVE_LIBCXX=1` and an explicit native ABI list derived from undefined
C++/HDF5/OpenMP symbols. Standard-library, out-of-line, BLAS and OpenMP work stays
native. Pointer-bound tracing is disabled because native calls do not preserve
those labels. Unsupported expressions and native boundaries remain recorded.

`trace_only: true` records events without initializing/using a solver and cannot
produce passing campaign evidence. `traces/events.jsonl` records events, solver
outcomes, generated paths, target exits and completion. Malformed cases have
adjacent `.invalid.json` metadata. Instrumented binaries are excluded from any
performance claim.

The full-library configurations currently allow 120 seconds, 2,048 tasks,
2,048 MiB, 10 MiB captured output, 2,048 corpus entries and 48 tasks per seed.
Other profiles have different limits; the resolved config/run metadata is the
authority. A low solver yield never triggers ordinary mutation or seed replay as
a substitute generator. Missing tools, timeout, failed tracing or disabled solving
remain explicit failures.

## Translation providers

A provider receives a versioned source unit, source text/hash and prompt, and
returns code, structured metadata, provider identity and a response hash. It does
not execute code or decide equivalence. Versioned prompts live in `configs/prompts/`;
their content and hashes are captured in each run's `prompts/` directory.

| Provider | Current use |
|---|---|
| `offline` | Default; snapshots a checked-in translation without credentials or model calls |
| `openai` | Explicit option for the earlier single-file Rust tensor profile; needs `OPENAI_API_KEY` and `SAGE_MODEL` |
| `sam` | Version-1 endpoint contract using `SAGE_SAM_ENDPOINT`; no trained model or endpoint is bundled, and current Einsums runtimes reject it |

Full-library Rust and both C++ profiles accept only `offline`. Selecting a network
provider sends its bounded source and prompt to that service. Generic SAM requests
carry languages, unit IDs, source/hash and prompt; responses are limited to 10 MiB
and require code/metadata. The adapter records bounded retries/timeouts and response
provenance, omits credentials and avoids request-echoing exception text. Failure
never silently substitutes an offline fixture or changes numerical policy.

## Proof internals

The six-operation specification independently emits ordered prefix expressions:
0 is positive zero, 2–33 are distinct input leaves, 60 is addition and 61 is
multiplication. Six bits encode each token. A four-term left-associated dot
product needs 17 tokens/102 bits, fitting in 128 bits. Rust carries a length field;
C++ derives length from the leading nonzero token. The prefix grammar is injective
on these trees. The specification does not call the candidate arithmetic operators.

The C++ six-operation lowering materializes scalar types and models span/array
because CBMC cannot parse the full C++20 wrapper. Certificates compare production
and materialized optimized LLVM for 144 binary64 and 144 expression entries, keeping
instructions, attributes and metadata. Only ModuleID/source_filename are removed.
Kani directly imports the unchanged generic production Rust Tensor source.

For the separate scalar profile, the upstream pin and exact `Transpose.cpp` hash
are checked before extracting `macro_kernel_scalar`. Parameters are `double`,
alpha one, beta zero, conjugation disabled and independent buffers with capacity
16. The runner materializes `betaIsZero=true`, `floatType=double`, `conjA=false`
and changes the constant `if constexpr` to `if` for CBMC's C++11 parser. An identity
helper makes the unreachable conjugation branch well-formed. Computational
statements remain verbatim. Clang 18 checks identical optimized LLVM for the
original specialization and compatible source. C++ candidate kernels also get
C++11/C++20 source-binding certificates.

CBMC checks assertions, pointer/array bounds, overflow and complete unwinding.
Kani checks assertions, panic/safety and unwinding; its allocation model assumes
success. Scalar controls inject an incorrect C++ output and Rust transpose metadata
fault; the paired C++ workflow tests upstream/candidate output faults. The six-method
profile has one isolated fault per operation plus native binary64 witness replay.
Missing assertions, unsupported reachable code or failed controls cannot pass.

The memory models, arithmetic interpretation, generic parametricity and compilers
remain trusted. Complete upstream HPTT planning, SIMD, OpenMP, BLAS, public wrappers
and broad Python/FFI semantics are excluded; see the [proof scope](verification.md#prove-the-six-tensor-operations).

## Recorded upstream findings

The initial pinned CPU baseline built 307 targets and passed 206 CTest entries
in an Ubuntu 24.04/Linux arm64 environment. Its best installed Python suite passed
723 cases and skipped 137 GPU cases, with two random-data complex eigen/QR basis
comparisons still failing. This established feasibility for one environment,
not portability or translated-library compatibility.

That baseline needed pybind11 2.13.6 for `pybind11/typing.h`, SciPy 1.16.1 for the
test suite's nullspace API, and both double/single FFTW runtimes. The v1.1.5 pin's
CMake/soname output reports 1.1.3. The upstream build requires C++20, CMake 3.25.2+,
BLAS/LAPACK and HDF5; optional integrations include FFT, HIP and pybind11.
The rectangular upstream QR wrapper passed inconsistent dimensions to `orgqr`
and a recorded probe timed out. The bounded campaign consequently uses square
positive-definite inputs; independent rectangular-port tests are not an upstream
equivalence claim. The container's spdlog/fmt versions must also agree.

Assessment references include Psi4 [Einsums integration](https://github.com/psi4/psi4/pull/3050)
and [Python integration](https://github.com/psi4/psi4/pull/3350), plus recorded Einsums
issues on [layout](https://github.com/Einsums/Einsums/issues/236),
[LAPACK discovery](https://github.com/Einsums/Einsums/issues/251),
[dependencies](https://github.com/Einsums/Einsums/issues/284),
[Windows Python tests](https://github.com/Einsums/Einsums/issues/295) and
[restructuring](https://github.com/Einsums/Einsums/issues/302).
These explain assessment risks at the recorded baseline; they do not establish
current issue status or scientific priority.
