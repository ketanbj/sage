# Einsums CPU and Python API implementation

Both the Rust and independent C++20 ports implement all **90 CPU exports** of the pinned compiled Python extension and its
**16 public utility helpers**. The checked-in [Rust API surface](../ports/einsums-rs/api-surface.json)
and [C++ API surface](../ports/einsums-cpp/api-surface.json)
record the upstream commit and original image. This is an export/implementation inventory;
it does not claim exact compatibility for every call, C++ template overload or downstream consumer.

The Python package imports as `einsums` or `pyeinsums`. NumPy owns the Python buffer storage;
scientific arithmetic dispatches to the selected independent Rust or C++20 library. The original C++ Einsums library
is used only as a validation reference. GPU/HIP remains outside the requested scope.

## Implemented surface

| Area | Implementation |
|---|---|
| Tensor and view types | Float32, float64, complex64, complex128; owning copies, mutable aliases, buffer protocol, slicing, iteration, shape/stride metadata and arithmetic |
| Tensor algebra | General two-input Einstein contractions, repeated indices, scalar contractions, batched plans, matrix/vector and outer products |
| Linear algebra | Scaling, reductions/norms, dot/conjugate dot, LU/PLU, solve/inverse/determinant, packed QR and factors, Hermitian/general eigensystems, SVD, nullspace, truncation, pseudoinverse, Lyapunov, Cholesky and matrix powers |
| Decomposition | CP/PARAFAC, weighted CP, Tucker HOSVD/HOOI, reconstruction, unfolding, mode products and Khatri–Rao |
| Storage | Block/tiled tensors and dense conversion; four-dtype HDF5, nested datasets, compressed/endian-converted reads and explicit disk flush |
| FFT | Real and complex forward/inverse transforms and frequency coordinates; inverse normalization follows upstream |
| Services | Initialization/finalization, typed configuration, logging, profiling sections, error classes and tensor factories |
| Packaging | Independent native libraries, source build hooks, platform wheels, both Python import names and submodules |

Rust consumers use the public `api::{array,linalg,decomposition,storage,runtime}` modules and the
structured `api::execute(Request)` dispatcher. Generic Rust storage and borrowed views also remain
available through `Tensor<T>`/`View<T>`. Rust runtime/configuration state and Python runtime services
are separate. Numerical kernels use double working precision before conversion to the declared dtype.

Rust general eigenvectors use triangular Schur solves with SVD fallback for repeated/defective roots.
C++ uses Eigen eigenvalues and SVD nullspaces for left/right eigenvectors.
Lyapunov uses a Schur triangular solve, requiring quadratic storage rather than an explicit
Kronecker coefficient matrix. FFT remains a quadratic DFT; no performance equivalence is claimed.

## Build and install

```console
uv sync --all-extras
make build-einsums-wheel
uv pip install ports/einsums-rs/dist/<platform-wheel>.whl
```

Source builds require Rust 1.84+, a C compiler and CMake. Cargo.lock pins numerical and HDF5
libraries. First-time builds fetch dependencies; cached builds work offline. The wheel contains
the native library and requires NumPy. The built macOS arm64/Python 3.11 wheel was installed into a
clean environment and exercised with a solve, complex SVD and HDF5 read/write.

See the [crate README](../ports/einsums-rs/README.md) for Rust usage. The
[C++ port README](../ports/einsums-cpp/README.md) documents the separate native
backend and wheel. Build it with `make build-einsums-cpp-wheel`, then install the
platform wheel into its own environment because both ports expose the same import
names. C++ uses Eigen and the HDF5 C library rather than Rust numerical crates.

The C++20 translation was verified on October 6 with 15,872 saved-corpus API/dtype
checks: 13,816 three-way PASS, 2,056 reference/contract disagreements and zero
candidate numerical failures. Its 23-operation native grid, Python entrypoints,
four-dtype API tests and native sanitizer checks also pass. See
[modern C++ verification](modern-cpp.md) for full evidence and remaining limits.

## Compatibility decisions

The port preserves the pinned Python row-eigenvector `syev/heev` convention and the transposed-storage
ONE/INFINITY norm convention. It corrects mathematical defects and records differences:

- Pseudoinverse has shape `n × m`, a valid rank threshold and the Penrose identities.
- Complex Lyapunov is available; the pinned extension throws for the complex backend.
- Rectangular QR returns thin factors. SVD job modes return useful thin/empty arrays rather than
  the pinned padded buffers. General eigenvalue order and nonunique bases can differ.
- Truncation returns exactly `k` deterministic leading modes. Upstream returns `k+5` randomized
  projected modes, so strict truncation checks intentionally expose a contract difference.
- Nullspace uses a dtype-aware threshold. Some single-precision rank decisions differ upstream.
- Stepped views and unary negation extend the pinned Python tensor API. The common tensor replay
  uses unit-step slices, while separate implementation tests check the extensions.
- Disk flush errors are explicit; destructors do not silently write. Random samples differ from
  upstream even when distribution/sign behavior agrees. BadBuffer validates unsafe metadata safely.

C++ compiler templates, vendor BLAS symbols and plugin/build internals are not a binary ABI offered
by these semantic ports. Exact overload compatibility and downstream Psi4 integration remain unverified.
The existing full-library completion gate stays conservative instead of equating API presence with
whole-library equivalence.

## SymSan-only evidence

Generate a corpus with the existing 23-operation campaign, then replay it through the new APIs:

```console
make build-einsums-container
make build-einsums-python-container
uv run sage run --target einsums --provider offline
make validate-einsums-api RUN=runs/<source-run-id>
```

The source campaign's `INCOMPLETE_SCOPE` exit does not discard its generated corpus. API replay
accepts only nonempty, unique, valid SymSan cases whose metadata, accepted bytes and original generated
file agree. Bootstrap seeds are explicitly rejected. It snapshots candidate sources, the native
library, replay code, corpus hashes, source-manifest hash and immutable reference image.

Every saved payload drives all 31 API groups and all four dtypes: **128 generated inputs yield
15,872 API/dtype checks**, not 15,872 new solver-generated cases. Both the original compiled C++ Python
extension and the Rust-backed package execute the inputs. Independent NumPy expectations check values,
dtypes, shapes, normalized reconstruction/eigen residuals and orthogonality. Complex comparisons use
complex magnitude; eigenvalues are normalized by matrix scale. Nonunique bases are not compared
entry by entry. The `k=1` truncation probe deterministically resizes generated values into 8×8 arrays.

Original and candidate results remain separate, including exceptions, crashes/timeouts and raw
outputs. A candidate passing while the original fails is `REFERENCE_DISAGREEMENT`, not a passing
comparison or proof of an upstream bug. Randomized truncation and deliberate calling-contract changes
must be interpreted separately from numerical defects. The replay command exits nonzero on any
unresolved disagreement.

SymSan instruments only the original input decoder. Replaying new API/dtype combinations does not
add concolic paths or establish library-internal branch coverage. HDF5, decomposition, runtime,
empty-array and ownership checks are ordinary implementation tests, never campaign evidence.

## Implementation checks

`make check` runs formatting, lint, strict typing, Python unit/integration/end-to-end tests and Rust
tests. The API checks include all four dtypes, strided aliases and owner lifetime, read-only and error
atomicity, LU/QR/SVD/eigen residuals, Penrose identities, repeated eigenspaces, non-Hermitian Lyapunov,
CP/HOOI reconstruction, compression/endian interoperability, special floats and installed exports.

The selected upstream tensor suite passed 83 tests and contraction-plan suite passed 88 CPU tests
(88 GPU skips). The earlier selected linear-algebra suite passed 160 tests and failed 20 comparisons
of specific eigenvector/SVD/nullspace bases; those literal basis comparisons are not treated as
mathematical equivalence requirements. Upstream fixtures and these counts are implementation checks,
not SymSan-generated evidence. Finite successful checks do not prove universal equivalence.

## Recorded verification

The final [saved replay](../runs/20260908T184451.753740Z-einsums-api/report.md) used 128 authenticated
SymSan-generated inputs. Of 15,872 API/dtype checks, 13,810 passed for both implementations and
2,062 were `REFERENCE_DISAGREEMENT`. The candidate passed all numerical checks; all replay processes exited successfully.
API exceptions from the original remain recorded as disagreements. These disagreements include deliberate truncation/threshold changes and original API
defects or unsupported cases. The full raw outputs and source snapshots are retained.

| Original/contract disagreement group | Checks |
|---|---:|
| geev | 23 |
| lu | 232 |
| pseudoinverse | 512 |
| solve_continuous_lyapunov | 256 |
| svd_nullspace | 43 |
| truncated_svd | 512 |
| truncated_syev | 484 |

`make check` passed 79 Python tests and 5 Rust tests, plus formatting, lint and strict typing. The
final wheel was installed and tested in a clean virtual environment. These implementation/install
checks remain separate from the generated-corpus results.
