# Einsums CPU tensor stage

The executable `einsums` adapter implements a staged Rust translation of bounded tensor operations.
It uses pinned Einsums v1.1.5, commit `22a115978041e905461b24d9ca2a17bfcce01f32`, as its actual C++
reference. The broader CPU/Python library profile is now the default; see [library scope](einsums-library.md).

## Contract

Input format `einsums-tensor-1.0` is exactly 36 bytes: operation, M, K, N (one unsigned byte each),
then two 16-byte signed integer data buffers. Dimensions must each be 1–4. Data convert to binary64
by division by 8; unused buffer elements are ignored. Operation IDs are:

| ID | Operation | A shape | B shape | Output shape |
|---|---|---|---|---|
| 0 | Copy and indexed readback | M × K | M × K | M × K |
| 1 | Elementwise addition | M × K | M × K | M × K |
| 2 | Elementwise multiplication | M × K | M × K | M × K |
| 3 | Transpose (`permute`) | M × K | M × K | K × M |
| 4 | Matrix contraction (`einsum`) | M × K | K × N | M × N |
| 5 | Scalar multiplication (B[0]) | M × K | M × K | M × K |

Outputs are JSON `shape`, `strides`, and `values` matrices. The first two compare exactly; numeric
values compare against independent NumPy operations with the versioned policy `einsums-tensor-1.0`
(default atol 1e-12, rtol 1e-10). Nonfinite outputs fail. A C++/NumPy disagreement is a reference
problem even when Rust matches C++. Process failures and structural differences remain separate.

## Generation and instrumentation

Six fixed bootstrap inputs (one per operation) initialize SymSan. They never become validation cases.
Only new, valid, deduplicated solver-generated payloads are replayed through C++, Rust and NumPy.
Reports include counts for every operation, including zero. No generated inputs means `NO_TEST_CASES`,
not a successful validation; a timeout or failed campaign remains incomplete even if partial cases pass.

The harness and instantiated Einsums template bodies compile with the pinned `ko-clang++`,
`KO_USE_FASTGEN=1`, `KO_USE_NATIVE_LIBCXX=1`, and `KO_DONT_OPTIMIZE=1`. The builder derives an explicit
native ABI list from the ordinary object file's undefined C++, HDF5 and OpenMP symbols. Pointer-bounds tracing is disabled for this mixed native/instrumented stage because native calls
do not preserve pointer-bound labels. Integer branch exploration remains enabled; the binary decoder
strictly enforces dimensions and input length. Instrumented nonzero exits fail the campaign.

Out-of-line
Einsums functions, standard-library calls, BLAS, and OpenMP remain native; their internal branches
are not explored. C I/O and memory operations use SymSan interceptors. The exact ABI list, compiler
commands and environment are saved in each run. Unsupported symbolic expressions are counted in
campaign metadata. None of this establishes full-library branch coverage.

## Reproduction

```console
make build-containers
make build-einsums-container
uv run sage target prepare --target einsums
uv run sage run --target einsums --config configs/einsums.yaml --provider offline
uv run sage report --run runs/<run-id>
uv run sage reproduce runs/<run-id>/discrepancies/<case-id>
```

The image builds the pinned library with Clang 18, OpenBLAS, HDF5 and FFTW. Its spdlog build uses the
same fmt version as Einsums to avoid the distribution spdlog/fmt ABI mismatch. The immutable local
image ID, source hashes and original MIT license are captured. Replay requires the recorded image
and binaries. The Rust offline provider is a checked-in implementation; OpenAI is an explicit
optional translation provider, and no trained SAM model is supplied.

## Exclusions

This stage does not translate all of Einsums. Tensor views, arbitrary rank and dtype, complex
numbers, ownership/binding compatibility, error-path equivalence, decompositions, FFT/I/O, Python,
GPU, threading behavior and Psi4 downstream workflows remain unimplemented. The input encoding
samples a small exactly representable numeric domain and does not explore arbitrary floating-point
bit patterns. Discrepancies are replayed and saved at their original size; automated Einsums case
minimization is not yet implemented.
