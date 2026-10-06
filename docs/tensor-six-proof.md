# Six-operation proofs and public API connection

The Rust and C++ ports now prove **copy, add, elementwise multiply, transpose,
matrix multiplication and scale** against one ordered-expression specification.
There are 144 operation/shape obligations per language: 16 shapes for each of five
operations, plus all 64 `(m,k,n)` combinations for matrix multiplication. Every
dimension ranges from one through four.

The current evidence is collected in [the proof report](../artifacts/tensor-six/report.md).
This extends the earlier copy/transpose scalar-kernel pilot. It does **not** claim
that an arbitrary upstream BLAS implementation or the whole Einsums library has
been formally verified.

## What is proved

The harnesses call production Tensor constructors and methods. Rust additionally
checks contiguous output strides. Both check output shape, exact expression
contents, indexing/safety obligations and unchanged input buffers. Unwinding
assertions require every bounded loop to finish; missing harnesses, unknown
results, timeouts and reachable unsupported code cannot pass the completion gate.

| Operation | Rust public method | C++ public method | Public Python entry |
|---|---|---|---|
| Copy | `Tensor::clone` | `Tensor::copy` | `tensor.copy()` |
| Add | `Tensor::zip` with `x+y` | `Tensor::added` | `a + b` |
| Elementwise multiply | `Tensor::zip` with `x*y` | `Tensor::multiplied` | `a * b` |
| Transpose | `Tensor::permute([1,0])` | `Tensor::transposed` | `a.T` |
| Matrix multiply | `Tensor::matmul` | `Tensor::matmul` | `a @ b` |
| Scale | `Tensor::map` with `scalar*x` | `Tensor::scaled` | `core.scale(scalar,a)` |

## Why the arithmetic proof is compositional

Direct binary64 bit-blasting made the larger matrix obligations impractical in
the installed verifier. The production algorithms were made generic over their
scalar arithmetic, preserving the binary64 public interfaces. The same production
methods can therefore run over expression trees in the proof harness.

Each input is a distinct symbolic leaf, not a sampled numeric value. Operations
construct injectively encoded **ordered** prefix trees: tokens `0` for positive
zero, `2..33` for inputs, `60` for addition, and `61` for multiplication. Six bits
encode each token. The largest expression is a four-term left-associated dot
product: 17 tokens, or 102 bits, fitting in 128 bits. A length field accompanies
the Rust encoding; C++ obtains the length from the leading nonzero token. The
prefix grammar makes the encoding injective on these trees.

The independent specification emits the required prefix stream directly. It does
not call the candidate arithmetic operators. Equality therefore preserves each
operand index, multiplication operand order, positive-zero initialization and
each intermediate addition. It assumes neither associativity nor reassociation.
Substituting the input values and interpreting every node as the corresponding
deterministic binary64 operation gives identical results under the stated
compiler and floating-point assumptions.

Rust uses the actual generic production `Tensor` through Kani. C++ uses the actual
`BasicTensor` method bodies through CBMC, with a mechanically materialized scalar
type and a small `span`/`array` model because CBMC does not parse the C++20 wrapper.
Clang 18 must compile the production and materialized wrappers to identical LLVM
for all 144 entry points, for both binary64 and expression arithmetic. Only the
ModuleID and source filename lines are normalized; instructions, attributes and
metadata remain part of the comparison. The bundles retain the sources, compiler
flags, LLVM modules, hashes and raw verifier outputs.

This is a conditional compositional theorem, with the compiler, arithmetic
interpretation, parametricity of the generic algorithm and memory models in the
trusted base. It is not a verified-compiler theorem or a new proof of IEEE 754.

## Connection to the public library

Both native JSON/FFI dispatchers now route eligible public requests to the proved
Tensor methods. The C++ library campaign driver uses the same bridge for its six
original operations. The existing Rust byte-protocol driver already calls those
methods. The C++ installation includes the Tensor and kernel headers required by
the bridge.

The bridge is restricted to owned, contiguous rank-two `float64` tensors with
dimensions one through four and values equal to signed bytes divided by eight.
Scale uses a scalar from that same domain. Matrix multiplication requires matching
inner dimensions, normal (`N/N`) operands and two operands without an accumulated
output. Transpose is the permutation `[1,0]`. Other requests use the general Array
implementation, including larger shapes, other dtypes, broadcasting and invalid
requests. Negative zero input, nonfinite input and non-dyadic input take that
general path.

The public-adapter check executes all 144 combinations with six input patterns,
including zero, both signed-byte extremes and mixed signs: **864 exact-bit Python
checks and 864 JSON/FFI checks per language**. It also checks output shape, contiguous
storage, ownership and preservation of inputs, plus representative fallback
requests. These are native regression checks, not symbolic proofs of parsing,
serialization or Python/FFI lifetimes.

Each operation has an isolated deliberate source fault. The verifier must reject
it at the expression assertion; native binary64 replay must pass the original
source and fail the mutant on a retained signed-byte fixture. Production files
are never mutated by these controls.

## Reproduce

```sh
uv run sage prove --target einsums --profile tensor-six --language rust --jobs 4
uv run sage prove --target einsums --profile tensor-six --language cpp20 --jobs 4
```

The existing pinned verifier setup and offline compiler image described in
[formal-verification.md](formal-verification.md) are required. Successful bundles
report `BOUNDED_TENSOR_API_PROVED`. Public-adapter replay is run separately:

```sh
uv run python scripts/verification/check_tensor_six_apis.py \
  --language rust --library ports/einsums-rs/target/debug/libsage_einsums.dylib \
  --output /tmp/rust-api-replay.json
```

Use the C++ library and `--language cpp20` for that backend; Linux builds use `.so`.
`--reuse-checks BUNDLE` can reuse complete method obligations only when the proof
inputs, generated harnesses and pinned tools match. Source drift is rejected.
Certificates and fault detection/replay always run again, and provenance of the
reused raw logs is recorded. This allows a repaired control runner to retain
expensive, already successful method proofs without weakening the completion gate.

## Remaining boundaries

The preserved upstream HPTT scalar copy/transpose proofs remain separate evidence.
Add, multiply, scale and matmul now have proofs of the translated methods against
the common operation contract. The full original upstream public call paths,
including BLAS and dispatch, still require their own refinement proofs or explicit
backend contracts. General sizes, other dtypes, arbitrary-rank operations, GPU
paths, allocation failures and full JSON/Python semantics also remain outside the
formal claim.
