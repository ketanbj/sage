# ADR 0003: Three-way differential validation

Status: accepted

## Context

A translated implementation can agree with a defect in its source, while an independent mathematical
reference can have ordering or domain mistakes. Pairwise comparison cannot distinguish these cases.

## Decision

Execute generated C, translated Rust, and NumPy for every valid case. Check structure and ordering,
then use a versioned numerical policy. Classify C/NumPy disagreement separately and replay every
non-pass result.

## Consequences

Evidence is clearer and common-mode translation errors are less likely to pass unnoticed. The NumPy
reference and ordering contract require independent maintenance. Three executions cost more but are
small for the bounded pilot.

## Alternatives

C-versus-Rust alone is simpler but cannot validate the source oracle. Property invariants alone are
too weak. Formal verification would be stronger but is outside the MVP and available toolchain.
