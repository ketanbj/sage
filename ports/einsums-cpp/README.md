# Independent modern C++ CPU/Python translation

The C++20 port now implements the same broad CPU/Python surface as the Rust port:
all **90 pinned CPU exports**, **16 public utility helpers**, and the tensor
decomposition, storage and FFT modules. Scientific operations execute in an
independent C++ backend. It does not link upstream Einsums or delegate to Rust,
NumPy or SciPy numerical kernels. NumPy supplies Python buffer storage and test
oracles. The Python calling-interface code is shared in origin with the Rust
port; its native loader exclusively selects the C++ library.

| Area | C++ implementation |
|---|---|
| Arrays and tensors | Arbitrary rank, four real/complex dtypes, owned copies, contractions, matrix products, checked shapes and strides |
| Native typed storage/views | DenseTensor<T> / four RuntimeTensor aliases; deep owning copies, retained-owner strided views, reverse slices, read-only checks |
| Python tensors/views | Buffer protocol, slicing, iteration, mutable aliases, owner lifetime, metadata and arithmetic |
| Linear algebra | LU/PLU, solve, inverse, determinant, packed QR, Hermitian/general eigenpairs, full/thin SVD, nullspace, truncation, pseudoinverse, Lyapunov, native Cholesky/matrix powers |
| Decomposition | CP/PARAFAC, weighted CP, Tucker HOSVD/HOOI, reconstruction, unfolding, mode products and Khatri–Rao |
| Storage | Block/tiled tensors, dense conversion, four-dtype HDF5, nested/compressed/endian-converted reads, explicit disk flush |
| FFT | Forward/inverse real and complex transforms, frequency coordinates; unnormalized inverse as in Einsums |
| Services | Initialization, typed configuration, logging, profiling sections, errors and factories |
| Packaging | Native shared library, C++ headers, platform Python wheel, einsums and pyeinsums imports |

The checked-in [API manifest](api-surface.json) maps the pinned export inventory.
`api/api.hpp` is the native umbrella header; `api::execute()` is the structured
dispatcher. `sage_api_request` / `sage_api_free` provide a JSON C ABI with errors
contained across the boundary. Native runtime state and Python runtime services
are separate, as in the Rust port. Factoring uses Eigen, with double working
precision before dtype conversion. HDF5 uses its independent C library. The DFT
is quadratic and generic contractions use scalar enumeration; performance
equivalence is not claimed.

## Build

Requirements: C++20 compiler, CMake 3.20+, Eigen 3.4 or 5.x, nlohmann JSON 3.11+,
HDF5 C library and Python 3.11+. On macOS use
`brew install eigen nlohmann-json hdf5`; on Debian/Ubuntu use `libeigen3-dev`,
`nlohmann-json3-dev` and `libhdf5-dev`.

```console
cmake -S ports/einsums-cpp -B ports/einsums-cpp/build -DCMAKE_BUILD_TYPE=Release
cmake --build ports/einsums-cpp/build -j 2
ctest --test-dir ports/einsums-cpp/build --output-on-failure
make build-einsums-cpp-wheel
uv pip install ports/einsums-cpp/dist/repaired/<platform-wheel>.whl
```

The wheel builder bundles macOS HDF5 dependencies with delocate. Linux wheels
need the HDF5 runtime, or auditwheel repair for redistribution. Use separate
environments for the Rust and C++ wheels because both offer the same upstream
Python import names. Source development can use
`PYTHONPATH=ports/einsums-cpp/python` and
`EINSUMS_CPP_LIBRARY=/absolute/path/to/libsage_einsums_cpp.dylib` (`.so` on Linux).
The native CMake install supplies `lib/` and `include/sage-einsums/api/`.

## Validation recorded October 6, 2026

- The complete project suite passes **134 tests**, with **five backend-specific skips**.
- Broad API checks pass across float32, float64, complex64 and complex128,
  including numerical residuals, ownership, aliases, decompositions and HDF5.
- The new 23-operation native grid passes **4,416** operation/shape/value-pattern
  cases. Python campaign entrypoints pass **69** separate profile checks.
- Both native CTest contracts pass under ASan/UBSan, including typed view
  ownership, runtime state, JSON errors, Cholesky and matrix powers.
- The selected upstream tensor/contraction suites pass **171** tests, with
  **88 GPU skips** and **96 slow cases deselected**.
- Upstream linear-algebra and view suites pass **448** tests and fail **40**
  literal eigenvalue-order or nonunique SVD/nullspace basis comparisons;
  **16 slow cases are deselected**. Residual/reconstruction checks are separate
  and pass. These failures remain visible compatibility differences.
- Saved-corpus replay:
  `runs/20261006T151151.290470Z-einsums-api-cpp20/` records **15,872** checks over
  128 authenticated SymSan inputs, 31 API groups and four dtypes. The candidate
  passes every numerical expectation: **13,816** three-way PASS and **2,056**
  REFERENCE_DISAGREEMENT. This is a replay, not new symbolic path discovery.
- The full-library campaign additionally generates **128 new cases across all
  23 operations**, with upstream, C++ native, C++ Python and NumPy agreement.
  See the [recorded campaign report](../../runs/20261006T152014.013938Z-115b5d8bf7/report.md).
  Its completion gate remains INCOMPLETE_SCOPE because finite probes cannot
  establish the whole library contract.
- A repaired macOS arm64/Python 3.11 wheel installs in a clean environment and
  passes solve, complex SVD and HDF5 operations through its bundled native library.

## Compatibility and proof scope

This is a semantic CPU/Python translation. It replaces upstream vendor BLAS,
allocator, preprocessor and similar infrastructure with Eigen and standard C++20
facilities; it does not reproduce every upstream C++ template overload, exported
vendor symbol or binary ABI. GPU/HIP remains outside the established project
scope. The Python numerical/shape differences documented for the Rust port also
apply here: deterministic truncation, rank thresholds, meaningful pseudoinverse
shape, complex Lyapunov, useful thin factors and nonunique basis/order choices.

The [six-operation extension](../../docs/tensor-six-proof.md) now proves 144
public Tensor method obligations through generic arithmetic and compiler-bound
expression semantics. The bounded float64 public CPU/Python domain calls those
methods, with exact-bit adapter checks and six source-fault/native replay controls.
The earlier upstream scalar copy/transpose proof remains separate evidence.
General Array paths and the full upstream call chain remain outside the proof. The standalone
six-operation binary can still be built without third-party dependencies using
`-DSAGE_BUILD_FULL_API=OFF`.

```console
make demo-cpp20-library
make validate-einsums-cpp-api RUN=runs/<generated-library-run>
make test-cpp20-library
uv run sage prove --target einsums --language cpp20
uv run sage prove --target einsums --language cpp20 --profile tensor-six --jobs 4
```

Next verification work is contract review of the 2,056 replay disagreements,
broader payload/computation-path exploration, formal proofs for more kernels
and public calls, downstream/Psi4 integration and native performance benchmarks.
See [modern-cpp.md](../../docs/modern-cpp.md) for evidence and scope.
