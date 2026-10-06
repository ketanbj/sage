# Product requirements

## Problem

Scientific source translation can preserve syntax while subtly changing layouts, derivatives,
floating-point behavior, or failure modes. Reviewers need concrete, replayable evidence tied to a
specific source revision, generated candidate, input domain, and numerical policy. A model's claim
that code is equivalent is not adequate evidence.

## Users and use cases

- Scientific software maintainers evaluate a translation before review or adoption.
- Research engineers compare translation providers and test generators reproducibly.
- Numerical analysts inspect errors per component and isolate reference disagreements.
- CI systems rerun a deterministic, network-free regression campaign.

Primary use cases are assessing target candidates, recording human selection decisions, translating
one bounded unit, generating diverse tests, three-way execution, confirming and minimizing
discrepancies, and exporting an auditable run bundle.

## Functional requirements

SAGE must represent candidates, recommendations, and approved selections separately; permit zero
selected targets; require human approval for scientific-pilot mode; prepare pinned upstream source;
invoke an explicitly selected provider; build target implementations in isolated run directories;
generate target-owned test inputs; run implementations in bounded subprocesses; evaluate independent
references; compare under a versioned target policy; replay every discrepancy; and write JSON/JSONL
plus Markdown/HTML reports with full provenance.

The CLI must expose diagnostics, target preparation, translation, test generation, validation,
report rendering, reproduction, cleanup, target assessment/selection, and one end-to-end command.
Offline operation is
the default. Network translation must require an explicit provider choice.

## Nonfunctional requirements

- Reproducible: pins, hashes, tool versions, seeds, commands, and resolved configuration are stored.
- Safe by default: no network in execution sandboxes; time, memory, process, and output bounds apply.
- Extensible: target-specific science does not leak into generic provider or runner contracts.
- Observable: failures, crashes and timeouts must not be collapsed into numerical differences.
- Portable: offline development works on Linux and macOS; SymSan is Linux/amd64 Docker.
- Honest: reports describe sampled behavioral evidence, never proof or universal equivalence.

## MVP scope

New validation campaigns use only SymSan-generated cases; no generated cases means no passing evidence.
The Einsums CPU tensor stage adds bounded Rust translation with an independent NumPy reference.

The implementation includes a target-independent candidate and selection core,
adapter registry, run modes, providers, provenance and failure taxonomy. Einsums
has independent Rust and C++20 CPU/Python ports and six bounded Tensor proofs.
Potential targets remain catalog records until their adapters are implemented.
Implementation coverage does not imply scientific selection or exact upstream
compatibility. HIP/GPU remains outside the current scope.

## Out of scope

Whole-library formal verification, synthesis of a SAM model, automatic scientific target recommendation or
approval, invented stakeholder commitments, production sandbox guarantees against hostile native
code, automatic tolerance changes, and unsupported target implementations are outside this MVP.

## Success criteria

1. A clean offline setup builds and passes unit, integration, and orchestration tests with a stubbed solver without
   Docker, credentials, or paid calls. Actual validation campaigns require SymSan.
2. No target is selected by default, and scientific-pilot mode rejects missing or invalid approval.
3. Einsums remains executable in both languages with target-specific validation and proof profiles.
4. One run directory is sufficient to understand configuration, lineage, builds, cases, executions,
   comparisons, limitations, and confirmed discrepancies.
5. A new candidate can be recorded without code, and an implemented target can be added without
   importing its scientific details into the generic core.

Scientific selection remains a human decision. For Einsums, the PI must confirm the
wider compatibility surface and supported backends. Bounded-kernel proofs and broad
CPU/Python implementation do not establish complete library equivalence.
