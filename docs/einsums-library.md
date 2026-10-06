# Einsums CPU/Python library port

The requested scope is the full pinned Einsums CPU and Python library, excluding HIP/GPU. The
implementation currently covers part of that scope. `INCOMPLETE_SCOPE` and a nonzero CLI exit are
expected even when all current probes pass. This status must not be presented as library equivalence.

## Run and inspect

```console
uv run sage target prepare --target einsums
make build-containers
make build-einsums-container
uv run sage run --target einsums --provider offline
uv run sage report --run runs/<run-id>
```

The default target configuration is `configs/einsums-library.yaml`; the earlier six-operation
profile is retained at `configs/einsums.yaml`. The full profile uses a multi-file checked-in Rust
crate, without an API/model call. The old single-file translation provider cannot generate this crate.

Each run captures the complete clean upstream tree, its MIT license, every tracked file's hash,
module inventory, candidate source hashes, Rust binary/shared-library hashes, immutable Docker image
identity, all build commands, and input-generation metadata. `source/inventory.json` is a file
inventory, not a complete public-symbol inventory. `library-coverage.json` reports partial and missing
modules. Unknown upstream modules cannot disappear from that report.

## Independent C++20 library profile

`configs/einsums-cpp-library.yaml` selects the independent C++20 CPU/Python port.
It implements the same 90 core exports, 16 public helpers, four dtypes and broad modules
as the Rust port, using Eigen and HDF5 with separate build/source identities. Native headers
and a platform Python wheel are available. The original six-operation C++ profile remains
at `configs/einsums-cpp.yaml`. Neither port reproduces every upstream C++ overload or ABI.

The C++ library profile uses the same 23-operation bounded input protocol, but its Python
runner exercises actual public Python calls for every profile operation. Its October 6
campaign passes 128 newly generated cases across all 23 operations; its separate 31-group,
four-dtype saved-corpus replay has 13,816 PASS and 2,056 REFERENCE_DISAGREEMENT, with zero
candidate numerical failures. The full-library gate remains INCOMPLETE_SCOPE. See
[C++ scope and evidence](modern-cpp.md) and [API compatibility choices](einsums-api.md).

```console
make build-einsums-cpp-wheel
make demo-cpp20-library
make validate-einsums-cpp-api RUN=runs/<generated-library-run>
```

## Implemented Rust and Python surface

The API has expanded beyond this campaign's original 23 probes. See
[the current API implementation and compatibility contract](einsums-api.md) and
[the crate installation guide](../ports/einsums-rs/README.md). All four real/complex dtypes,
CPU Python exports, numerical factorizations, decomposition, HDF5 and storage APIs now have
implementations. nalgebra, num-complex, serde and HDF5 are locked dependencies; an initial
`cargo fetch --locked` is required before offline builds on a fresh machine.

This profile preserves its original 36-byte protocol and legacy Python replay for reproducibility.
Use the separate API replay command to exercise the new `einsums` / `pyeinsums` package against
the compiled original Python extension. Old passing reports do not validate newly added APIs.

## SymSan-only comparison contract

The 36-byte protocol retains the operation/M/K/N header and two 16-byte signed-value buffers.
Dimensions are 1–4, and input values are signed bytes divided by eight. The operation IDs are:

| IDs | Operations |
|---|---|
| 0–5 | copy, add, elementwise multiply, transpose, matmul, scale |
| 6–9 | subtract, divide by abs(B)+1, negate, first-column copy slice |
| 10–16 | dot, axpy, axpby, gemv, ger, vector norm, RMSD |
| 17–19 | inverse, symmetric eigenvalues, QR reconstruction on A Aᵀ + I |
| 20–22 | complex DFT, inverse DFT, frequency coordinates |

All accepted inputs are new SymSan solver outputs. The 23 bootstrap seeds initialize traces only;
unchanged seeds, duplicate bytes, and invalid encodings never become validation evidence. Ordinary
Rust/Python unit and integration fixtures remain implementation checks, not campaign evidence.

Each generated input compares real upstream C++, the Rust executable, and NumPy. Python replays
operations 0–17 through owned tensor objects, and 18–22 through the Rust campaign C ABI. The Python
entrypoint is recorded per execution. Shapes/strides compare exactly; the numeric tolerance is
atol 1e-12 and rtol 1e-10. This does not validate all ranks, numeric domains, dtypes, exceptions,
ownership contracts, or algorithmic stability of the broader Rust API.

SymSan instruments `input_harness.c` at O0, including active-region decoding loop bounds. The native
C++ `einsums_kernel` executes during each trace and during concrete reference replay. The native
boundary is explicit in the ABI list and build metadata. Mixed instrumented C++ template/native calls
produced uninitialized label failures, retained in earlier run artifacts. Input-only instrumentation
avoids those failures but **does not explore library-internal branches**. Pointer-bound tracing is
disabled. Per-seed task limits distribute the global solver budget; no ordinary mutation generator
or seed replay is substituted when yield is low.

The pinned upstream rectangular `linear_algebra::q` wrapper uses inconsistent dimensions when
calling `orgqr`; a rectangular probe timed out during native execution. The current QR probe is
restricted to square positive-definite matrices. Rectangular Rust QR has independent residual and
orthogonality tests, but no passing upstream equivalence claim. Input-harness coverage cannot
establish complete QR behavior or resolve the upstream issue.

## Completion and compatibility

The gate remains conservative. The implementation now covers the CPU Python export surface and
scientific operation families; its documented behavior differs from the pinned source in several
places. Exact C++ symbol/overload compatibility, complete aliasing/threading/error behavior,
downstream Psi4 integration and full generated validation remain unestablished. HDF5, decomposition,
empty-array and buffer-lifetime checks are implementation tests, not SymSan campaign evidence.

GPU modules remain excluded. Passing the bounded probes never marks an entire upstream module
complete. The API replay records source disagreements and candidate disagreements separately.
