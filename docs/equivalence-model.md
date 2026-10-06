# Equivalence model

SAGE distinguishes sampled behavioral agreement from bounded formal proofs. A
campaign compares concrete upstream, translated and independent NumPy results.
Its finite corpus cannot establish universal library equivalence.

The [six-operation proof profile](tensor-six-proof.md) proves copy, add,
elementwise multiply, transpose, matmul and scale in Rust and C++20 against a
common ordered-expression specification. Each language has 144 bounded shape
obligations. The theorem preserves operand indices and arithmetic order under
stated compiler, arithmetic and memory assumptions. Eligible public API requests
use those methods. Public adapters have native checks rather than symbolic proofs.
The separate [upstream scalar proof](formal-verification.md) covers copy/transpose.
Neither theorem proves complete Einsums dispatch or vendor BLAS implementations.

## Observable behavior

Einsums observables include shapes, strides, dtypes, ownership and views, values,
errors, termination and process failures. The bounded six-operation domain is
owned rank-two float64, dimensions 1–4 and signed-byte values/scalar divided by
eight. Full-library policies additionally distinguish reconstruction/residual
contracts from literal basis/order comparisons. Future targets must define their
own observables. Instrumented binaries supply no performance evidence.

## Three-way comparison

Campaigns execute the pinned upstream C++ implementation and selected Rust/C++
candidate, and compute an independent NumPy reference. Candidate/upstream agreement
is insufficient when the oracle disagrees. `REFERENCE_DISAGREEMENT` identifies
upstream/reference conflicts. `STRUCTURAL_DIFFERENCE` covers shape/layout changes,
`NUMERICAL_DIFFERENCE` covers value errors, and process failures remain `CRASH` or
`TIMEOUT`. Build, invalid input, unsupported and infrastructure outcomes are separate.

## Numerical policies and replay

The versioned [API contract](einsums-api.md) defines tolerances, dtype rules,
nonunique numerical outputs and known reference disagreements. Tolerances are
recorded configuration rather than universal scientific constants. Exact-bit
adapter checks for the proof domain remain separate from tolerance-based campaigns.
Each discrepancy retains its input, executions and clean replay. A matching replay
confirms the observed discrepancy, not a whole-library incompatibility theorem.

## Evidence boundaries

Only new valid SymSan outputs count as campaign inputs. Bootstrap seeds initialize
exploration, while authenticated API sweeps are labeled as replay. Missing, failed
or empty generation cannot yield a passing campaign. Coverage, solver satisfiability,
compilation, pairwise matches and model summaries cannot substitute for proof.
General shapes/dtypes, full adapter semantics and upstream BLAS remain outside the
current formal theorem.
