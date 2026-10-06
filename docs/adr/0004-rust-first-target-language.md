# ADR 0004: Rust as the first target language

Status: accepted

## Context

The first translation should demonstrate movement from generated scientific C to a modern systems
language while preserving a stable callable contract and floating-point behavior.

## Decision

Use stable Rust for the bounded tensor candidate. Keep the fixture dependency-free and
compile an uninstrumented optimized binary for validation.

## Consequences

Rust provides explicit ownership and a strong type system without requiring a large runtime. ABI,
layout, indexing, and floating-point evaluation order still require tests; memory safety does not imply
numerical equivalence. Additional build adapters can introduce other target languages.

## Alternatives

Modern C++ would ease mechanical translation and is the documented fallback if Rust becomes
technically infeasible. Translating to Python would not exercise a systems-language migration and
would confound NumPy as the independent reference.
