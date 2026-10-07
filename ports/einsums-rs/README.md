# Einsums Rust CPU APIs

An independent Rust numerical implementation and Python compatibility package for
Einsums v1.1.5 (`22a115978041e905461b24d9ca2a17bfcce01f32`). GPU/HIP is outside this port.

## Install

Build a platform wheel with `uv build --wheel .` or install this directory with
`uv pip install .`. Building requires Rust 1.84+, a C compiler, CMake and Python
3.11+. The wheel includes the Rust shared library; NumPy supplies Python buffer
storage. HDF5 and zlib are built through the locked Cargo dependencies. No original
Einsums library is loaded by the candidate.

```python
import einsums as ein
import numpy as np

a = ein.utils.create_tensor(np.array([[3.0, 1.0], [1.0, 2.0]]))
b = np.array([[1.0], [0.0]])
ein.core.gesv(a, b)  # overwrites a with LU and b with the solution
print(b)
```

`pyeinsums` is also available. `einsums_rs.Library` preserves the earlier campaign
ABI. Use `EINSUMS_RS_LIBRARY` only to select a specific development shared library.

## API

Rust consumers use `sage_einsums::api::{array,linalg,decomposition,storage,runtime}`
or the structured `api::execute(Request)` dispatcher. Python `einsums.core`
implements every CPU export in the pinned compiled extension, including the four
real/complex tensor and view types, buffer mutation, contraction plans, numerical
functions, errors, configuration and profiling. Additional modules expose CPU FFT,
CP/weighted CP, Tucker/HOOI, block/tiled tensors and HDF5 disk storage.

Numerical work runs in Rust. LU, QR, tensor contractions, FFT and CP are independent
implementations; eigensystems/SVD use nalgebra. HDF5 uses the independently linked
HDF5 C library. Python owns its NumPy buffers and runtime services. Single precision
inputs are rounded to their declared dtype; internal numerical working precision
is double precision, with results converted to the requested dtype.

## Compatibility decisions

- `core.syev/heev` writes eigenvectors in rows, as the pinned Python wrapper does.
  Rust `linalg::eigh` returns columns. Python `norm(ONE/INFINITY)` follows the pinned
  transposed-storage convention; Rust norms use conventional row/column meanings.
- General eigenvalues may be reordered; eigenvector phases, repeated-eigenvalue
  bases, SVD completions and nullspace bases can differ. Compare residuals/subspaces.
- Pseudoinverse returns the correct `n × m` shape and satisfies the Penrose identities.
  The pinned implementation has shape and rank-selection defects.
- QR returns thin Q/R for rectangular arrays. SVD `SOME`/`OVERWRITE` returns thin
  factors and `NONE` returns empty factor arrays, without mutating the input.
  These are explicit differences from the pinned wrapper's padded outputs.
- Truncated decompositions return exactly `k` leading modes using deterministic
  factorization. The pinned randomized routines return `k+5` projected modes.
- Complex Lyapunov solves are implemented; the pinned complex backend throws.
- `DiskTensor` flushes explicitly or on successful context-manager exit. It does
  not silently write from a destructor. HDF5 supports all four dtypes, nested
  datasets and compressed/endian-converted input.
- Random factories use independent seeded Rust generation; samples are not identical
  to upstream's RNG. Definite eigenvalues follow the documented Maxwell distribution.
- Safe `BadBuffer` metadata rejection replaces deliberately invalid native pointers.
  C++ templates, vendor BLAS ABI symbols, plugin/build internals and Psi4 integration
  are not binary-compatible interfaces provided by this Rust package.

## Validation

The [six-operation proof](../../docs/verification.md#prove-the-six-tensor-operations) checks 144 bounded
public Tensor obligations. Eligible float64 CPU/Python requests call the same
methods; six deliberate source faults and native replays accompany the proofs.
The current [evidence report](../../artifacts/tensor-six/report.md) distinguishes
formal method results from native adapter checks and broader library validation.

From the SAGE repository root, `make check` runs implementation checks. These are
not counted as SymSan validation evidence. `tools/validate_einsums_api.py --run RUN`
replays authenticated, unique, non-seed SymSan inputs against the original compiled
Python extension and this package, checking both against independent numerical
expectations. It records source/binary hashes, raw outputs and discrepancies. The
operation/dtype sweep does not establish library-internal concolic coverage or
whole-library equivalence. See the [API compatibility contract](../../docs/reference.md#api-compatibility).
