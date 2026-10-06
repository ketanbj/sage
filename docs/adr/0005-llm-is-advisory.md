# ADR 0005: LLM output is advisory

Status: accepted

## Context

Models can translate and explain code but can also invent executions, miss numerical defects, follow
instructions hidden in source comments, or overstate equivalence.

## Decision

Treat provider code as untrusted and model-generated summaries as visibly advisory. Only structured,
concrete executions and policy evaluations determine outcomes. A model cannot suppress discrepancies,
alter tolerances, or supply authoritative solver semantics.

## Consequences

Reports remain auditable even when model output is wrong or unavailable. Explanations can accelerate
diagnosis but cannot close a finding. Network source disclosure requires explicit provider selection.

## Alternatives

Allowing the model to judge equivalence is faster but non-reproducible and circular. Excluding models
entirely would lose useful translation and triage assistance without improving the concrete oracle.
