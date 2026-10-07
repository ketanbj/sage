# Current status

This page summarizes the recorded state after the October 6, 2026 repository
cleanup. Counts below describe different checks and should not be added together.

## What is implemented

SAGE has independent Rust and C++20 translations of the pinned Einsums CPU/Python
surface. Both implement 90 core exports and 16 utility helpers, with float32,
float64, complex64 and complex128 data. The original source is Einsums v1.1.5;
the exact revision is in the [technical reference](reference.md#source-and-toolchain-pins).

| Area | Available in both ports |
|---|---|
| Arrays | Tensors, views, slicing, ownership and contractions |
| Numerical operations | Matrix/vector operations, factorizations, eigensystems, SVD and related solvers |
| Other scientific modules | FFT, CP and Tucker decompositions |
| Storage and services | Block/tiled tensors, HDF5, configuration, errors and runtime services |
| Delivery | Native libraries and installable Python packages |

The ports implement this export inventory. They do not reproduce every original
C++ overload, binary interface or calling behavior. The
[API compatibility contract](reference.md#api-compatibility) records deliberate
differences. Both ports are checked-in implementations; automatic whole-library
translation by a model remains future work.

## What has been checked

| Evidence | Recorded result | What it establishes |
|---|---|---|
| Maintained project tests | 129 passed, 5 backend-specific skips | Regression checks after cleanup |
| C++ native profile grid | 4,416 cases passed | Selected operation/shape/value combinations |
| C++ Python profile runner | 69 checks passed | Calls through the campaign's Python entrypoints |
| C++ native safety contracts | 2 CTest contracts passed under ASan/UBSan | Tested ownership, runtime and error behavior |
| Fresh C++ campaign | 128 new accepted SymSan inputs across 23 operations, all passing | Sampled agreement with upstream and NumPy |
| Six-operation formal checks | 144 obligations passed per language | The stated bounded production-method specification |
| Public API proof-domain replay | 864 Python and 864 JSON/FFI exact-bit checks per language | Tested routing and adapter behavior |

Both translations have saved-input API replays over 31 API groups and four dtypes.
Each replay uses 128 generated inputs for 15,872 checks. The recorded Rust replay
has 13,810 passes and 2,062 reference disagreements. The separate C++ replay has
13,816 passes and 2,056 reference disagreements. Both candidates passed the replay's
independent numerical expectations, but disagreements with the original remain
unresolved compatibility findings. These are replays, not 15,872 newly generated
inputs. The Rust and C++ results were recorded at different milestones.

Selected upstream suites also exercise the ports. C++ tensor/contraction tests
passed 171 cases. Its linear-algebra/view tests passed 448 and failed 40 literal
eigenvalue-order or nonunique-basis comparisons. Residual and reconstruction checks
pass separately; they do not erase those compatibility differences. These suite
counts overlap other implementation checks and are not campaign evidence.

## What the proofs cover

**Copy, add, elementwise multiply, transpose, matrix multiply and scale** have
production Tensor proofs in both languages. Eligible public calls route to those
methods. The domain is owned, contiguous rank-two float64 data with dimensions
1–4 and signed-byte values divided by eight. Scale uses the same scalar domain.

The theorem preserves ordered arithmetic expressions under explicit compiler,
arithmetic and memory assumptions. The public adapters are tested natively;
parsing, lifetimes and error behavior are not symbolically proved. Upstream scalar
copy/transpose proofs are separate evidence. Full upstream dispatch and vendor
BLAS behavior are outside the six-operation theorem.

Read [Verification](verification.md) for the exact scope and reproduction commands.
The tracked [proof report](../artifacts/tensor-six/report.md) and
[combined summary](../artifacts/tensor-six/verification.json) identify the current
proof records. The [C++ summary](../ports/einsums-cpp/verification.json) records
the broader port milestone, including older project-test counts.

## What remains

The full-library compatibility gate remains **`INCOMPLETE_SCOPE`**. Work needed
before a broader compatibility claim includes:

1. Agree on required calling behavior and classify the recorded reference disagreements.
2. Validate complete interfaces, lifetimes, errors, threading and C++ overload/ABI requirements.
3. Expand generated numerical inputs and explore library computation paths. Current full-profile SymSan instrumentation covers the input decoder only.
4. Extend proofs to public adapters, larger domains and additional operation families, including upstream dispatch/backend contracts.
5. Run downstream Psi4 regressions and an agreed platform matrix, then compare native performance.

HIP/GPU is excluded from the current scope. Scientific pilot selection is a
separate human decision: Einsums remains `UNDER_ASSESSMENT`, while Gau2Grid, DKH
and GDMA are potential targets without executable adapters. See
[target selection](development.md#target-selection) for that workflow.
