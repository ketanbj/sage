# Current SAGE slides

This is the single maintained presentation folder. Update the same files in `output/`
for future revisions. Folder names and delivered filenames do not include dates or
version suffixes.

- `output/SAGE-Project-Overview.pptx` and `.pdf`: seven slides for a broad audience.
- `output/SAGE-Einsums-and-Symbolic-Verification.pptx` and `.pdf`: sixteen technical slides.

Updated October 6, 2026. Both independent Rust and C++20 ports now implement the
established CPU/Python semantic surface: 90 core exports, 16 helpers, four dtypes,
linear algebra, FFT, decompositions, storage, HDF5 and runtime services.
Implementation coverage does not establish exact upstream compatibility or C++ ABI
and overload parity. HIP/GPU remains excluded.

All six original tensor operations now have bounded production-method proofs in
both languages: copy, add, elementwise multiply, transpose, matmul and scale.

- Rust: 144 Kani obligations pass against the actual generic production methods.
- C++20: 144 CBMC obligations pass, with 144 binary64 and 144 expression compiler
  identity entries connecting the verifier model to the production method bodies.
- Both detect six deliberate source faults and replay each failure natively.
- Eligible public APIs route to these methods. Each language passes 864 exact-bit
  Python checks and 864 JSON/FFI checks across every bounded shape combination.

The domain is owned rank-two float64 tensors with dimensions 1–4 and signed-byte
values divided by eight, including the scale scalar. The proofs preserve exact
ordered expressions and rely on trusted arithmetic, compiler, parametricity and
memory models. Public adapters have native replay evidence rather than symbolic
proofs. General sizes/dtypes, upstream vendor BLAS and complete public call chains
remain outside the theorem. The refreshed upstream scalar copy/transpose proofs
also pass. SymSan supplies comparison inputs, while CBMC and Kani supply proof
evidence. Broad library implementation does not expand the formal domain.

The Rust replay chart retains its historical September 8 values: 128 inputs,
15,872 comparisons and 2,062 reference disagreements. The separate October 6 C++
API replay has 15,872 checks, 13,816 three-way passes and 2,056 reference disagreements,
with no candidate numerical failures against the replay expectations. These are
saved-input replays. The new C++ 23-operation campaign passes all 128 fresh SymSan
cases through native and actual Python entrypoints, with upstream and NumPy agreement.
The decoder-only instrumentation does not establish internal computation-path coverage.

The complete project suite passes 129 tests with five backend-specific skips. C++
checks include 4,416 native profile cases, 69 Python runner cases, ASan/UBSan native
contracts and isolated native/Python installs. The upstream tensor/contraction subset
passes 171 tests. Linalg/views pass 448 and fail 40 literal order/basis comparisons;
independent reconstruction and eigenpair-residual checks pass. Counts overlap and
should not be added to solver counts. The whole-library gate remains INCOMPLETE_SCOPE.

Next steps are common contract review, complete calling-contract and C++ overload/ABI
validation, larger proof domains and symbolic adapter proofs, varied numerical payloads and computation-path
exploration, downstream/Psi4 regression and native performance benchmarks. Automatic
full-library model translation also remains pending for both checked-in ports.

Current consolidated evidence: [six-operation report](../tensor-six/report.md).
Scope and rerun instructions: [six-operation methodology](../../docs/tensor-six-proof.md), [formal verification](../../docs/formal-verification.md),
[modern C++](../../docs/modern-cpp.md) and the [C++ verification summary](../../ports/einsums-cpp/verification.json).
Immutable proof/campaign/replay evidence remains under `runs/`. The latest C++ campaign
is `runs/20261006T152014.013938Z-115b5d8bf7/` and API replay is
`runs/20261006T151151.290470Z-einsums-api-cpp20/`. Presentation build sources, original
decks, previews and validation records live privately in `.build/`.
