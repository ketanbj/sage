# ADR 0001: Python orchestration

Status: accepted

## Context

The workflow combines YAML configuration, upstream preparation, provider APIs, native builds, binary
corpora, numerical comparison, and report generation. NumPy supplies independent numerical references.

## Decision

Use typed Python 3.11+ with `uv`, Typer, dataclasses, JSON/JSONL, and YAML for orchestration. Native
scientific implementations remain separate executables.

## Consequences

Adapters and scientific references are easy to extend and test offline. Python is not an isolation
boundary, so generated native code must remain out of process. Schema/version discipline is required
because dataclasses alone do not guarantee long-term artifact compatibility.

## Alternatives

Rust would strengthen the orchestrator binary and deployment story but slow provider and NumPy
integration. Shell scripts would be smaller initially but weak for typed records, failure taxonomy,
and portable testing.
