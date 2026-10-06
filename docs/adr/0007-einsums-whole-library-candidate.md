# ADR 0007: Einsums replaces the unidentified Psi4-module candidate

- Status: Accepted for candidate assessment
- Date: 2026-09-02

## Context

The catalog contained `psi4-module`, a deliberately unidentified bounded placeholder. Research
identified Einsums as the relevant C++20 tensor-algebra library used optionally by Psi4, and the
requesting user directed SAGE to assess the complete library rather than a bounded module.

## Decision

Replace the listed placeholder with canonical candidate `einsums`, set its state to
`UNDER_ASSESSMENT`, and record the complete pinned v1.1.5 library as the proposed translation unit.
Retain `psi4-module` only as a deprecated lookup alias. Do not register an executable adapter, make a
recommendation, create a selection decision, or change the zero-selection default.

Implementation evidence may be produced in subsystem increments, but a whole-library completion
claim requires the combined C++/Python API, build and packaging behavior, required backends, approved
optional features, and downstream Psi4 workflows. Partial results must remain labeled partial.

## Consequences

The candidate is now specific and evidence-backed, and old placeholder lookups remain readable. The
scope exceeds SAGE's demonstrated bounded-kernel workflow and therefore carries high feasibility,
equivalence, dependency, and schedule risk. Target language, backend matrix, defect-compatibility
policy, reviewers, acceptance evidence, and scientific-pilot approval remain human decisions.
