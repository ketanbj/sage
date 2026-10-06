# ADR 0002: Dockerized SymSan

Status: accepted

## Context

SymSan depends on a specific Linux, LLVM, DFSan, and solver combination that differs from common macOS
and developer host environments.

## Decision

Build the pinned SymSan revision in an Ubuntu 24.04 Linux/amd64 Docker image with LLVM 18 and a pinned,
checksummed compatible Z3 release. Invoke it only through a bounded adapter.

## Consequences

The specialized toolchain is reproducible and does not contaminate the host. Apple Silicon incurs
emulation cost. Docker reduces accidental impact but is not a security boundary for hostile binaries.
Image IDs and instrumentation are recorded, and instrumented binaries are excluded from performance.

## Alternatives

A host install is faster on native amd64 but hard to reproduce. A full VM is a stronger boundary but
heavier for the MVP. Omitting SymSan loses constraint-driven cases but remains supported offline.
