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

## Validation

The [current status guide](../../docs/status.md) separates implementation checks,
fresh SymSan campaigns, saved-input replay and bounded proofs. The
[port verification summary](verification.json) retains its recorded milestone
counts, including compatibility findings and install checks.

The broad C++ port passed its 4,416-case native grid, 69 Python campaign-entrypoint
checks, four-dtype API checks and two ASan/UBSan native contracts. Its recorded
128-input API replay has 13,816 passes and 2,056 reference disagreements; its
separate fresh campaign passes 128 new cases across all 23 operations. The
full-library gate remains `INCOMPLETE_SCOPE`.

Use [the verification guide](../../docs/verification.md) to reproduce checks and
interpret disagreements. Full raw run bundles are retained separately from Git.

## Compatibility and proof scope

This is a semantic CPU/Python translation. It replaces upstream vendor BLAS,
allocator, preprocessor and similar infrastructure with Eigen and standard C++20
facilities; it does not reproduce every upstream C++ template overload, exported
vendor symbol or binary ABI. GPU/HIP remains outside the established project
scope. The Python numerical/shape differences documented for the Rust port also
apply here: deterministic truncation, rank thresholds, meaningful pseudoinverse
shape, complex Lyapunov, useful thin factors and nonunique basis/order choices.

The [six-operation extension](../../docs/verification.md#prove-the-six-tensor-operations) now proves 144
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
See [current status](../../docs/status.md) for evidence and scope.
