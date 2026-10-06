# Current six-operation proof evidence

Copy, add, elementwise multiply, transpose, matrix multiplication and scale have
completed bounded production Tensor proofs in **both Rust and C++20**. Eligible
public CPU/Python requests call those methods.

| Evidence | Rust | C++20 |
|---|---:|---:|
| Public-method obligations | 144 /144 | 144 /144 |
| Deliberate source faults detected | 6 /6 | 6 /6 |
| Native original/mutant replays | 6 /6 | 6 /6 |
| Python exact-bit adapter checks | 864 | 864 |
| JSON/FFI exact-bit adapter checks | 864 | 864 |
| Compiler identity entries | Direct Kani source import | 144 binary64 +144 expression |

The proof preserves ordered expressions, including every input index and every
matrix accumulation step. Interpreting those expressions as binary64 establishes
the conditional functional result. The trusted base includes arithmetic semantics,
parametricity, the compilers/verifiers and standard-library memory models. This is
a compositional proof rather than a direct bit-blast of all floating-point matrix
calculations. Native adapter checks are separate empirical evidence.

**Domain:** owned rank-two float64 tensors, dimensions 1–4, independent valid input
storage, signed-byte values divided by eight, and successful allocation. Scale
uses the same scalar domain. The bridges preserve general-library fallbacks.

The refreshed upstream HPTT scalar copy/transpose proofs also pass against the
current code. Add/multiply/matmul/scale prove the ports against the common operation
contract. The external upstream BLAS implementation and complete Einsums public
call chains remain outside the theorem, as do general sizes/dtypes and full
JSON/FFI/Python parsing, lifetime and error behavior.

At this proof milestone, project checks passed **139 tests with 5 backend-specific
skips**. Rust native checks and C++ CTest contracts passed, along with Ruff and mypy.
These historical counts predate the removal of the retired demonstration tests.

See [Rust evidence](rust/manifest.json), [C++ evidence](cpp20/manifest.json) and the
[methodology and rerun instructions](../../docs/tensor-six-proof.md). The manifests
record raw immutable proof-bundle locations and any reused-check provenance.
Published summary paths are repository-relative. The combined summary retains both
original and published manifest hashes. Full raw solver bundles are intentionally
outside Git and must be regenerated or distributed separately.
`verification.json` provides the combined current state. Failed exploratory runs
remain separate audit records under `runs/`.
