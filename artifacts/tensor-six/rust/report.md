# Six-operation public Tensor proof (rust)

Status: `BOUNDED_TENSOR_API_PROVED`

All 144 public Tensor obligations preserve the exact ordered expression specified for the six operations, including shape and unchanged inputs. Interpreting those expressions as binary64 establishes bounded functional equivalence under the recorded assumptions. Public JSON/FFI/Python paths route this domain to these methods; the adapters require native replay.

## Assumptions

- Rank-two contiguous owned tensors, each dimension 1..4; successful allocation.
- Each leaf represents an arbitrary independent input, not a sampled value.
- Arithmetic means deterministic binary64 + and *, with +0 initialization.
- For cross-language and upstream claims, inputs/scalar are signed bytes /8.
- Round-to-nearest, no fast-math, reassociation or fused multiply-add.
- Trusted Kani 0.68.0/CBMC 6.11.0, Clang 18 and standard-library memory models.
- Injective base-64 prefix-tree encoding (at most 17 tokens /102 bits).

## Exclusions

- External upstream BLAS, public Einsums planner/dispatch/SIMD/OpenMP.
- General Array fallback, other sizes/ranks/dtypes, aliasing and invalid inputs.
- JSON/FFI/Python parsing and serialization are replay-tested, not model-checked.
- NaN payloads, floating-point environment changes, allocation/lifetime failures.
- The arithmetic interpretation and compiler are trusted, not verified toolchains.

Error: none
