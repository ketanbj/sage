# SAGE design documentation

Current execution workflow: [Einsums CPU/Python library scope](einsums-library.md), using only
SymSan-generated validation cases. [The six-operation tensor profile](einsums-tensors.md) remains
available with an explicit configuration.

- [Product requirements](product-requirements.md) defines users, scope, requirements, and success.
- [Architecture](architecture.md) describes components, flow, trust boundaries, and extension points.
- [Target selection](target-selection.md) separates candidates, recommendations, and approvals.
- [Stakeholders and user stories](stakeholders-and-user-stories.md) records provisional users without
  inventing assignments.
- [PI discovery questionnaire](pi-discovery-questionnaire.md) lists evidence needed before selection.
- [Adding a target](adding-a-target.md) defines the candidate and adapter workflow.
- [Einsums candidate assessment](einsums-candidate.md) defines the proposed whole-library scope,
  evidence, equivalence dimensions, and feasibility gates.
- [Equivalence model](equivalence-model.md) defines what SAGE can and cannot conclude.
- [SymSan integration](symsan-integration.md) documents the pinned concolic toolchain and bounds.
- [Translation providers](translation-providers.md) covers offline, OpenAI, and future SAM adapters.
- [Testing](testing.md) describes the verification layers and reproducibility strategy.
- [Modern C++ translation](modern-cpp.md) records the full CPU/Python port, empirical checks and compatibility gaps.
- [Bounded formal verification](formal-verification.md) defines the scalar proof pilot and its limits.
- [Six-operation proofs](tensor-six-proof.md) covers both languages and public API connections.
- [Repository preparation](repository-preparation.md) documents tracked files and local exclusions.
- [Operations](operations.md) provides setup, execution, replay, cleanup, and troubleshooting.
- [Security and safety](security-and-safety.md) records the generated-code threat model and controls.
- [Upstream pins](upstreams.md) records immutable third-party revisions and build findings.
- [Implementation plan](implementation-plan.md) captures the MVP build sequence and research gap.
- [Architecture decisions](adr/) records the major technical choices.
