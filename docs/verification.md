# Verification

SAGE uses three kinds of evidence. Keep them separate when interpreting a result:

| Evidence | Purpose | Limit |
|---|---|---|
| Implementation tests | Check known examples, numerical invariants, ownership and packaging | Finite regression checks |
| Generated-input campaigns and replay | Compare upstream, a port and NumPy on concrete inputs | Sampled behavior, with recorded disagreements |
| Bounded formal proofs | Check every allowed case of a fixed specification | Only the stated domain and trusted assumptions |

Read [Current status](status.md) for recorded results. This guide explains what
those results mean and how to produce new evidence.

- [Compare behavior](#compare-behavior): campaigns, reports and API replay.
- [Prove the six Tensor operations](#prove-the-six-tensor-operations): scope, setup and adapter checks.
- [Separate upstream scalar proof](#separate-upstream-scalar-proof): the earlier copy/transpose profile.
- [Retain and publish evidence](#retain-and-publish-evidence): run bundles and tracked summaries.

## Compare behavior

A campaign uses SymSan to generate inputs from execution constraints. Only new,
valid, unique solver outputs enter validation. Fixed seed inputs start exploration;
unchanged seeds, duplicate payloads and malformed inputs never count as evidence.
If generation is empty, disabled, timed out or failed, partial passing cases cannot
make the campaign successful.

Each accepted input runs the original Einsums and the selected port, with NumPy
providing an independent expectation. Shapes and strides compare exactly. The
bounded profiles use absolute tolerance 1e-12 and relative tolerance 1e-10 for
values. Broader API replay has dtype-specific tolerances and numerical invariant
checks, documented in the [reference](reference.md#numerical-comparison).

Follow [Getting started](getting-started.md#3-run-a-comparison-campaign) to prepare
and run the default Rust or C++ library campaign. Full-profile SymSan instrumentation
covers the input decoder, while the library runs natively. It does not explore
library-internal computation paths. The earlier Rust tensor profile instruments
selected template bodies as well; external native calls still remain outside
symbolic exploration.

### Read a run report

The command prints a directory under `runs/`. Begin with its `report.md` or
`report.html`, then inspect `manifest.json` for the source/configuration identities
and generation outcome. `operation-coverage.json` lists all profile operations,
including those with no generated evidence. `library-coverage.json` records partial
or missing scope; a file inventory is not a complete symbol inventory.

| Result | Interpretation |
|---|---|
| `COMPLETED` | The selected campaign's completion checks passed |
| `INCOMPLETE_SCOPE` | The required library compatibility scope remains incomplete, even if current probes agree |
| `NO_TEST_CASES` | Generation completed without new valid inputs |
| `INFRASTRUCTURE_FAILURE` | A required tool, build or execution step failed |
| `TIMEOUT` | Execution or generation exceeded its bound |
| `STRUCTURAL_DIFFERENCE` | Output shape or layout disagrees |
| `NUMERICAL_DIFFERENCE` | Values disagree under the recorded policy |
| `REFERENCE_DISAGREEMENT` | Upstream conflicts with the independent expectation |
| `CRASH` | An implementation did not complete normally |

The first rows are run outcomes; the remaining labels can describe individual
comparisons or execution failures. A candidate agreeing with an incorrect or
unsupported upstream result is insufficient for a three-way pass. A candidate
passing while upstream disagrees also leaves a finding to review.

Re-render the report or reproduce a discrepancy with:

```sh
uv run sage report --run runs/<run-id>
uv run sage reproduce runs/<run-id>/discrepancies/<case-id>
```

Replay uses the recorded image identity and saved binaries. Keep them with the
run. A reproduced mismatch confirms that observation; it is not a theorem about
the entire library.

### Replay through the broader Python APIs

API replay reuses an authenticated generated corpus across more functions and
dtypes. It checks that recorded bytes, generation metadata and original generated
files agree, and rejects empty, duplicate or seed-only corpora. It records source,
replay code, library, corpus and reference-image hashes.

After a library campaign, build the original Python reference image and select
one replay backend:

```sh
make build-einsums-python-container
make validate-einsums-api RUN=runs/<generated-library-run>
make validate-einsums-cpp-api RUN=runs/<generated-library-run>
```

Replace the placeholder with your campaign directory. Each command makes its own
replay bundle. The standard sweep covers 31 API groups and four dtypes. For
example, 128 inputs yield 15,872 API/dtype checks; the sweep generates no new
SymSan inputs or concolic paths. Unresolved disagreements cause a nonzero exit.

## Prove the six Tensor operations

The `tensor-six` profile checks production methods against a common specification
for copy, add, elementwise multiply, transpose, matrix multiplication and scale.
There are 144 obligations per language: 16 shapes for each of five operations,
and 64 dimension combinations for matrix multiplication.

### Domain and public API connection

The proved domain uses owned, contiguous rank-two float64 tensors, dimensions
1–4, independent valid input storage and successful allocation. Input values and
the scale scalar are signed bytes divided by eight. Matrix multiplication uses
matching inner dimensions, normal operands and no accumulated output. Transpose
uses the permutation `[1,0]`.

| Operation | Rust method | C++ method | Python entry |
|---|---|---|---|
| Copy | `Tensor::clone` | `Tensor::copy` | `tensor.copy()` |
| Add | `Tensor::zip` with addition | `Tensor::added` | `a + b` |
| Elementwise multiply | `Tensor::zip` with multiplication | `Tensor::multiplied` | `a * b` |
| Transpose | `Tensor::permute([1,0])` | `Tensor::transposed` | `a.T` |
| Matrix multiply | `Tensor::matmul` | `Tensor::matmul` | `a @ b` |
| Scale | `Tensor::map` with scaling | `Tensor::scaled` | `core.scale(scalar,a)` |

Eligible JSON/FFI/Python requests route to these methods. Other inputs use the
general Array implementation, including larger shapes, other dtypes, broadcasting,
negative zero, nonfinite or non-dyadic values. That fallback is outside the proof.

### What the theorem establishes

The harnesses check exact ordered expressions, output shapes, unchanged inputs,
indexing/safety properties and complete loop unwinding. Rust also checks contiguous
output strides. The generic production algorithms execute over symbolic expression
trees, so the proof preserves every input index, operand order, initial positive
zero and intermediate matrix accumulation. It makes no assumption of associative
floating-point addition.

Interpreting equal expression trees as the same deterministic binary64 operations
gives the conditional numerical result. This compositional argument relies on
arithmetic interpretation, generic-algorithm parametricity, compiler/verifier
semantics and memory models. It is not direct binary64 bit-blasting of every matrix
calculation, a verified-compiler theorem or a proof of IEEE 754 itself.

Kani checks the actual generic Rust Tensor source. CBMC checks the C++ BasicTensor
method bodies with a materialized scalar type and small span/array models. Clang 18
must produce identical optimized LLVM for all 144 production/materialized entries,
for both binary64 and expression arithmetic. Normalization removes only ModuleID
and source filename lines. See [proof internals](reference.md#proof-internals) for
encoding and source-binding details.

Public-adapter replay exercises all 144 combinations with six input patterns:
864 exact-bit Python checks and 864 JSON/FFI checks per language. It checks shape,
storage, ownership, input preservation and representative fallback calls. Those
adapter checks are empirical; parsing, serialization, lifetime and error semantics
are not symbolically proved.

### Setup and run

The checked-in verifier installer currently supports **macOS arm64 only**. It
installs pinned Kani 0.68.0, CBMC 6.11.0 and the required Rust nightly beneath
`.sage/verification`, without changing the default Rust toolchain. Other platforms
need an explicitly pinned, validated setup before using these commands.

With Docker running and the [development prerequisites](development.md#development-setup)
installed:

```sh
make setup-verification
make build-containers
make build-einsums-container
make prepare-einsums
uv run sage prove --target einsums --profile tensor-six --language rust --jobs 4
uv run sage prove --target einsums --profile tensor-six --language cpp20 --jobs 4
```

Each command creates a new proof bundle. Successful bundles report
`BOUNDED_TENSOR_API_PROVED`. All obligations and six deliberate source-fault
controls must pass; each fault also requires native original/mutant replay.
Missing tooling, unknown results, unsupported reachable code, timeouts, incomplete
unwinding or failed controls prevent success. Production sources are never mutated.

`--output runs/<new-proof-name>` chooses a new destination. `--timeout 1800` sets
an obligation timeout, and `--jobs` accepts 1–8. `--reuse-checks <bundle>` is specific
to this profile: it reuses complete method checks only when proof inputs, generated
harnesses and pinned tools match. Source drift is rejected; certificates and
fault-detection/native-replay controls still run again.

### Check the public adapters separately

Build current native libraries before replay; the proof command does not replace
this installation check. A fresh Rust checkout needs `cargo fetch --locked`
before an offline Cargo build:

```sh
cargo fetch --locked --manifest-path ports/einsums-rs/Cargo.toml
cargo build --locked --offline --manifest-path ports/einsums-rs/Cargo.toml
cmake -S ports/einsums-cpp -B .sage/cpp20-build -DCMAKE_BUILD_TYPE=Release
cmake --build .sage/cpp20-build -j 2
uv run python tools/verification/check_tensor_six_apis.py --language rust \
  --library ports/einsums-rs/target/debug/libsage_einsums.dylib \
  --output .sage/api-replay/rust.json
uv run python tools/verification/check_tensor_six_apis.py --language cpp20 \
  --library .sage/cpp20-build/libsage_einsums_cpp.dylib \
  --output .sage/api-replay/cpp20.json
```

These library names are for macOS; Linux uses `.so`. The script sets the backend
loader and imports the checked-in Python package for that language.

## Separate upstream scalar proof

The earlier `scalar` profile covers copy and transpose of the pinned upstream HPTT
scalar kernel. HPTT is the transpose implementation used by Einsums. This workflow
remains available with the same setup:

```sh
uv run sage prove --target einsums --profile scalar --language rust
uv run sage prove --target einsums --profile scalar --language cpp20
```

Rust checks 32 upstream C++ and 32 Rust obligations against the same bit-exact
copy/transpose specification. C++ checks 32 paired obligations including both
upstream scalar code and production kernels. The domain is all 16 shapes with
dimensions 1–4 and symbolic signed-byte values divided by eight. Copy and transpose
preserve exact bits, inputs and valid buffer bounds. Rust checks output metadata;
C++ checks inactive output preservation.

The runner checks the pinned source hash and compiler identity certificates. Both
profiles require fault detection and native counterexample replay. Success reports
`BOUNDED_EQUIVALENCE_PROVED`; an incomplete run is `INCONCLUSIVE` and exits nonzero.
The HPTT planner, SIMD/threading dispatch and full upstream Tensor wrapper are
outside this proof. It does not certify upstream add/multiply/scale/matmul or BLAS.

## Retain and publish evidence

A proof bundle records specification/exclusions, source snapshots and hashes,
tool versions, commands, raw outputs, compiler certificates and controls. A past
proof cannot certify changed code. Current tracked summaries live in
[artifacts/tensor-six](../artifacts/tensor-six/report.md); full raw bundles live in
ignored `runs/` and must be regenerated or distributed separately with licenses.

To collect new six-operation summaries, first save each language's separate
adapter replay as `api-replay.json` inside its new proof bundle. Then run:

```sh
uv run python tools/verification/collect_tensor_six.py \
  --rust runs/<rust-proof> --cpp runs/<cpp-proof> --output artifacts/tensor-six
```

The collector rejects incomplete/stale evidence and checks current source/library
hashes. Published paths are root-relative; original and published manifest hashes
remain recorded. Historical run records retain their original counts and scope.

Next proof work is to establish contracts for complete public adapters and upstream
planning/dispatch/backends, then extend domains and operation families. General
sizes/dtypes, aliasing, allocation failure, arbitrary floating-point patterns, GPU
and whole-library equivalence remain outside the present formal claim.

## Tool documentation

- [Kani installation](https://model-checking.github.io/kani/install-guide.html)
- [Kani verification results](https://model-checking.github.io/kani/verification-results.html)
- [CBMC loop completeness](https://model-checking.github.io/cbmc-training/faq/loop-unwinding.html)
