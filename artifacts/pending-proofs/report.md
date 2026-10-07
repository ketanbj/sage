# Proof extensions

Branch: `prending-proofs`. Contract: **corrected-cpu-semantics-1**, selected by
the project owner. Both ports preserve their documented mathematical corrections.
Original behavior remains a comparison target; disagreement is recorded rather
than silently waived. Whole-library compatibility remains `INCOMPLETE_SCOPE`.

| Requested area | Added evidence | Remaining boundary |
|---|---|---|
| Calling behavior and reference findings | Explicit contract, strict arity for nine normalized operations, classification of all 4,118 recorded disagreements | 351 numerical residual findings per historical language replay remain unresolved |
| Interfaces, lifetimes, errors, threading and ABI | Malformed/UTF-8/overflow requests, independent FFI allocations, eight concurrent callers, borrowed-view lifetime rejection, installed C and C++ consumers | Finite checks; complete parser/lifetime/scheduler proofs and upstream C++ overload/ABI compatibility remain open |
| Numerical inputs and computation paths | Larger/empty/scaled/rank-deficient numerical tests; a separate SymSan experiment in production FFT indexing, real pivot comparison and dyadic guards; public replay in both languages | Full-library profile remains decoder-only; floating arithmetic, complete LU and FFT paths are not explored by this experiment |
| Public adapters, domains and operation families | Source-bound symbolic guard, dyadic, pivot and FFT-bin obligations; larger copy/transpose layouts; upstream dispatcher/backend probes | Surrounding adapters, remaining arithmetic families and upstream backends do not have complete formal proofs |

Read [Verification](../../docs/verification.md#extended-contract-proofs) for setup
and commands. Machine-readable [extension evidence](verification.json) and
[historical disagreement classification](disagreements.json) preserve source and
run hashes. Raw logs and source snapshots are in ignored `runs/` bundles and can
be regenerated with the checked-in commands.

The current project check has **172 Python unit/integration passes**, five
backend-specific skips, seven Rust tests and one compile-fail lifetime check.
The path experiment accepts **35 fresh unique solver inputs** (nine frequency,
six pivot, twenty dyadic cases); **68 public JSON/FFI replays** pass across the
two languages. One real-frequency case per language has an index outside the
public half-spectrum and is kept only in the native decision evidence.

The backend matrix records 2,808 checks. Each port passes all 936 of its checks;
reference failures retain their individual records and classifications. Counts
are separate evidence categories and are not added into a formal proof count.

## Exact new theorem

Each language has 69 obligations: five production decision obligations and
64 layout obligations, one for every rank-two shape with dimensions 1–8.
Five deliberate faults must be detected, and each must also fail a native witness
while the unmodified program passes.

- Metadata routing considers arbitrary representable dimensions, ranks, lengths,
  dtypes, arities and predicate flags, including invalid inputs. It proves the
  pure production guard; conversion of parsed arrays into this metadata remains
  outside the theorem.
- Dyadic eligibility is sound over all binary64 bit patterns and complete for
  the 256 signed-byte/8 values. Negative zero, nonfinite and non-dyadic values
  cannot enter the six-operation proof path.
- Real LU comparison has the same strict order as absolute value for **all finite
  binary64 pairs**, including subnormals and extreme magnitudes. The first row
  wins a tie. This does not prove elimination or complex pivot arithmetic.
- FFT bin indexing agrees with the signed-bin specification for all integer
  `0 < n <= INT64_MAX`, `i < n`. Floating scaling, transforms and allocation are
  outside this theorem.
- Copy/transpose preserve arbitrary opaque 64-bit elements in all 64 shapes.
  Rust checks production Tensor methods and output shape/strides; C++ checks the
  production kernels, input preservation and inactive output buffers. C++
  `BasicTensor` still accepts only dimensions 1–4. Larger public Array fallbacks
  are replay-tested and are not connected to this layout theorem.

The C++ helper/kernel bodies are unmodified C++11-compatible production source.
Clang 18 must emit identical optimized LLVM in C++11 and C++20 modes, after
removing only ModuleID/source filename lines. Kani/CBMC, compilers, binary64 and
memory semantics remain trusted. Allocation success is assumed for Rust layouts.
Opaque-element layout proofs do not certify public JSON preservation of NaN
payloads or prove numerical floating-point arithmetic.

The original six-operation proofs remain separate: 144 obligations, six detected
faults and native witnesses, plus 864 Python and 864 JSON/FFI exact-bit checks per
language. Their source bindings now include the new guard implementations and C
ABI declarations. Those method results are reused only with byte-identical proof
inputs and pinned tools; certificates and controls run again.

## Required calling behavior

The Python API accepts the documented four native-endian dtypes. Shapes and output
dtypes must match each operation. Writable outputs are required for mutation;
checked failures leave output buffers unchanged. Views retain Python/C++ owners;
Rust borrowed views cannot outlive the Tensor. Owning copies are independent.
Overlapping user mutations and mutation/free of an in-use native handle require
caller synchronization.

The normalized JSON operations `copy`, `permute`, `scale`, `negate` require one
array; `add`, `subtract`, `multiply`, `divide`, `matmul` require two. Missing or
extra arrays produce `ValueError`. BLAS operations retain their separate output,
alpha/beta and transpose contracts. Known Python orientation conventions remain
as documented in [API compatibility](../../docs/reference.md#api-compatibility).

Both libraries export the [same C request ABI](../../ports/einsums-cpp/sage_api.h).
Input bytes are borrowed during a call. Each returned UTF-8 JSON allocation must
be freed once with its originating library's `sage_api_free`; null free is allowed.
Malformed requests produce error envelopes. Null input, an impossible length, or
failure to produce a response returns null. No invalid native pointer can be
validated without the caller's memory contract. Error message text is diagnostic;
error classes, ownership and output atomicity are the required behavior.

The installed C++ consumer checks const/mutable span and reference overloads,
copy/move ownership, four typed Tensor aliases, retained views and `noexcept`
request declarations. A C11 consumer links against each language's shared library.
This establishes the tested **SAGE** interfaces on this platform. Einsums C++
headers, namespace, symbol layout and its full overload set are not drop-in
compatible. Read-only C++ views must be read through a const view/reference;
nonconst `at` requires writable storage.

## Findings are retained

Historical replay classification distinguishes reference shape defects,
unsupported wrapper/backend behavior, rank-policy and approximation-contract
differences, and unresolved numerical residuals. LU and geev residual failures
are not classified as benign nonunique bases. Numerical pseudoinverse findings
remain unresolved. Classification preserves every original campaign outcome.

The separate upstream matrix exercises six public plan classes, GEMM N/T/C,
GEMV, four dtypes, three shapes up to 9×9, contiguous and transposed buffers,
one/two-thread environment settings, and three repetitions. Both ports pass their
finite checks. The reference has transposed-buffer GEMM disagreements and
intermittent generic contraction residual failures observed with the two-thread
setting. These observations do not identify a proven root cause or establish
actual backend worker counts. Their per-execution records remain in the evidence.

Next work is to resolve these findings, prove surrounding parser/serialization
and lifetime/error paths, expand numerical operation proofs, and connect upstream
planning, threading and vendor backends under explicit contracts. Downstream Psi4,
other compilers/platforms and native performance remain separate acceptance work.
