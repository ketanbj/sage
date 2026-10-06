# Implementation state and next steps

The target-independent candidate catalog, human scientific-selection gate, generic
run facade, provenance and reporting are implemented. Einsums has independent Rust
and C++20 CPU/Python ports, SymSan campaigns and authenticated public API replay.
Both languages have 144 bounded six-operation Tensor obligations and eligible
public requests route to those methods. See [the proof scope](tensor-six-proof.md).

## Remaining work

1. Prove complete public adapters, including parsing, shape validation and lifetimes.
2. Extend proof coverage to larger shapes and additional dtypes.
3. Connect upstream dispatch and vendor BLAS implementations to explicit contracts.
4. Classify reference disagreements under shared compatibility policies.
5. Complete downstream/Psi4 regressions and native performance comparisons.

The full-library compatibility gate remains `INCOMPLETE_SCOPE`. Potential targets
stay in the catalog without runtime claims. Human scientific approval remains
separate from implementation readiness.

## Development and execution

Unit and ordinary integration tests need no Docker, credentials or paid calls.
Actual campaigns require the pinned Linux/amd64 SymSan environment and never fall
back to bootstrap seeds. Build images and prepare upstreams before offline-provider
campaigns. The [repository workflow](repository-preparation.md) keeps generated
runs and downloaded toolchains outside version control.

No trained Semantically Aligned Model is bundled. The versioned SAM endpoint
contract remains an extension point for future target adapters.
