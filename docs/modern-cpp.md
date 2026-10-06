# Modern C++ translation and verification

## Broad CPU/Python translation, October 6, 2026

The independent C++20 port now implements the broad CPU/Python surface: all
90 pinned CPU exports, 16 helpers, four dtypes, arbitrary-rank arrays and
contractions, linear algebra, decompositions, FFT, HDF5/block/tiled storage and
runtime services. The [port README](../ports/einsums-cpp/README.md) describes the
native API, dependency requirements, platform wheel and compatibility choices.
The Python calling interface was reused from the Rust port; its numerical
backend is independent C++20 with Eigen and HDF5, with no Rust/upstream linkage.

Native implementation checks pass 4,416 operation/shape/value-pattern cases for
the 23-operation profile, 69 Python profile calls, four-dtype broad API tests and
ASan/UBSan CTest contracts. Selected upstream tensor/contraction suites pass 171
tests (88 GPU skips, 96 slow cases deselected). Upstream linear-algebra/view
suites pass 448 tests and fail 40 literal eigenvalue-order or nonunique
SVD/nullspace basis comparisons (16 slow cases deselected). Those compatibility
differences remain recorded; passing residual checks does not erase them.

The [C++ API replay](../runs/20261006T151151.290470Z-einsums-api-cpp20/report.md)
uses the saved 128 authenticated SymSan inputs across 31 API groups and four
dtypes: 15,872 checks, 13,816 PASS, 2,056 REFERENCE_DISAGREEMENT and zero candidate
numerical failures. All replay processes exited successfully. The seven
disagreement groups are pseudoinverse 512, truncated SVD 512, truncated syev
478, complex Lyapunov 256, LU 232, nullspace 43 and general eigen 23. New
function/dtype sweeps do not add concolic computation paths.

`configs/einsums-cpp-library.yaml` selects the full CPU/Python candidate and
23-operation campaign, while `configs/einsums-cpp.yaml` retains the old bounded
profile. The whole-library gate remains conservative: infrastructure replacements
are mapped separately from scientific implementations, and exact upstream
C++ overload/ABI and downstream compatibility are not yet established.

The [six-operation proof extension](tensor-six-proof.md) now checks the public
Tensor methods through shared generic arithmetic, with 144 obligations, compiler
identity certificates and six fault-detection/native-replay controls. Eligible
float64 CPU/Python requests call those methods. General Array paths retain native
validation and are outside this formal scope. The scalar-kernel evidence below
is recorded separately.

The [fresh 23-operation campaign](../runs/20261006T152014.013938Z-115b5d8bf7/report.md)
passes all 128 accepted new SymSan cases through native and actual Python entrypoints,
against upstream and NumPy. It rejects 351 malformed solver outputs and retains
INCOMPLETE_SCOPE. The complete project suite passes 134 tests with five backend-specific
skips. Installed native headers/shared-library and the isolated repaired macOS wheel
pass consumer checks. See the [current verification summary](../ports/einsums-cpp/verification.json).

```console
make build-einsums-cpp-wheel
make demo-cpp20-library
make validate-einsums-cpp-api RUN=runs/<generated-library-run>
make test-cpp20-library
```

## Original six-operation profile

The independent C++20 candidate in `ports/einsums-cpp/` implements the same
six-operation tensor profile previously used for Rust. The pinned Einsums
source is already C++20. This work translates selected semantics into an
independent implementation with owned storage and borrowed spans; it is not
merely recompiling the upstream library with a newer standard.

## Completed scope

| Operation | Native comparison | Formal proof |
|---|---|---|
| Copy | Upstream C++ and NumPy | Public method, 16 shapes; upstream scalar evidence |
| Transpose | Upstream C++ and NumPy | Public method, 16 shapes; upstream scalar evidence |
| Add | Upstream C++ and NumPy | Public method, 16 shapes |
| Elementwise multiply | Upstream C++ and NumPy | Public method, 16 shapes |
| Matrix multiply | Upstream C++ and NumPy | Public method, 64 dimension combinations |
| Scale | Upstream C++ and NumPy | Public method, 16 shapes |

Domain: contiguous rank-two binary64, dimensions 1..4, with input values decoded
from signed bytes and divided by eight. The public `Tensor` uses `std::array`
for ownership, `std::span<const double>` for borrowed views, checked shapes and
indices, and value copies. It has no dependency on upstream Einsums or Rust.
The offline provider snapshots the checked-in implementation and records the
upstream pin, source mapping and hashes. No model translation call is claimed.

## Recorded verification on 2026-10-05

The fresh campaign `runs/20261006T031310.185203Z-2ca461ec1a/` completed with
**37 PASS, zero discrepancies**. The timestamp is UTC; this run occurred on
October 5 in the workspace's America/New_York time zone.

| Operation | Newly generated cases |
|---|---:|
| Copy | 5 |
| Add | 6 |
| Elementwise multiply | 6 |
| Transpose | 5 |
| Matrix multiply | 11 |
| Scale | 4 |

SymSan instruments the C input-contract harness, while the pinned upstream
library executes natively. These cases do not establish internal library branch
coverage. Bootstrap seeds, duplicates and malformed solver payloads are excluded
from validation evidence (85 malformed payloads were rejected). Every retained
case runs upstream Einsums, the independent C++20 binary and NumPy. Reports keep
the C++20 candidate's comparison keys and build identity distinct from Rust.

The formal bundle `runs/20261005-einsums-cpp20-bounded-proof/` has status
**BOUNDED_EQUIVALENCE_PROVED**, with **32/32 paired obligations** and four passing
fault-detection/native-replay controls. Each obligation directly includes both
the specialized pinned HPTT scalar implementation and the unchanged production
`kernels.hpp`. It proves exact output bits against the specification and against
the other implementation, input preservation, inactive output preservation,
bounds/pointer safety, arithmetic overflow checks and complete loop unwinding.
All 16 input elements are symbolic signed-byte values / 8, rather than samples.

CBMC 6.11.0 uses C++11-compatible syntax in the actual production kernels;
the candidate itself compiles as C++20. Clang 18 compiler certificates require
identical optimized LLVM IR for the original/specialized upstream kernel and
for the candidate kernels under C++11/C++20. Candidate compilation disables
automatic linker hints with `-fno-autolink` in both modes. IR normalization
removes only ModuleID and source_filename. This relies on trusted compiler and
verifier semantics; it does not prove the compiler correct.

Both isolated negative controls add 0.125 to an output write. CBMC finds the
incorrect output, records an input witness, and native C++20 replay returns
success for the unchanged source and detects the mutation. Production files are
never mutated. An earlier attempt exceeded CBMC's default addressed-object
limit; the final run explicitly uses `--object-bits 12` and records every command.
Missing tools, incomplete properties, timeouts or failed controls leave the result
inconclusive. Existing proof bundles cannot be overwritten by the CLI.

Separate native integration tests exercise 1,152 operation/shape/value-pattern
cases against NumPy, invalid protocol inputs, and ownership/shape/index behavior
under ASan and UBSan. These are implementation tests, not generated campaign cases.

## Rerun

Prerequisites: Python/uv, a C++20-capable `clang++`, CMake, Docker, the pinned
`sage-einsums:22a1159` image, prepared Einsums source and the existing CBMC bundle.
`tools/setup_verification.py` installs the proof tool bundle on macOS arm64.

```console
make setup-verification
make prepare-einsums
make build-einsums-container
uv run sage run --config configs/einsums-cpp.yaml --provider offline
uv run sage prove --target einsums --language cpp20 --jobs 2
uv run pytest tests/unit/test_modern_cpp.py tests/integration/test_einsums_cpp.py
```

The Rust configuration and proof remain the defaults. `provider.target_language:
cpp20` selects the C++20 runtime with either the tensor or library policy. Model
providers remain rejected: this is a checked-in independent offline translation.

## Pending

Formal proof of general-library operations outside the six-operation domain;
JSON/FFI decoding, lifetimes and error behavior; upstream BLAS, planner/dispatch,
SIMD and threading paths; other dimensions/dtypes, arbitrary floating values,
views/aliasing in formal proof; exact compatibility of the broader CPU/Python API;
and GPU support (excluded from scope). Performance has not been compared. This
result does not change the conservative whole-library gate.
