# Security and safety

## Threat model

Upstream source, model-generated code, compiler diagnostics, source comments, endpoint responses, and
concolic inputs can be malicious or malformed. SAGE protects a normal research workstation from
accidental failures and limits exposure; it is not a hardened malware-analysis sandbox.

## Generated-code execution

C++ and Rust candidates never load into the orchestrator. They compile in run-specific directories and
execute as subprocesses with time and address-space limits, captured output, deterministic inputs, and
no shell interpolation of generated text. SymSan builds and execution use a container with networking
disabled, CPU/memory/process limits, and only the required run directory mounted. Docker shares a host
kernel and is not sufficient for hostile code; use an ephemeral VM or isolated worker for that case.

## Inputs, network, and secrets

Canonical parsers validate magic, version, representation, counts, total lengths, and conservative
bounds before allocation. Invalid generated cases are quarantined and never executed as scientific
evidence. Offline execution has no network need. Container runs specify `--network none`; target
preparation and an explicitly selected network provider are the intended network exceptions.

Only the OpenAI client receives `OPENAI_API_KEY`; manifests store neither credentials nor raw exception
messages that could echo requests. Examples use placeholders. `SAGE_MODEL` and endpoint URLs are
configuration metadata, not secrets, but should still be reviewed before publication.

## Supply chain, prompts, and provenance

Einsums, SymSan, and Z3 are pinned to immutable revisions or checksummed artifacts. Docker base and
package repositories remain a residual moving dependency unless locked to digests/snapshots; image IDs
are recorded per run. Upstream licenses and captured source attribution must travel with redistributed
artifacts.

Source comments may contain prompt-injection instructions. Providers receive source as data under a
versioned translation instruction; their response is untrusted code and metadata. No response can
change numerical policy, mark a case passing, suppress a discrepancy, or instruct the solver outside
the adapter contract.

## Artifact retention

Runs may contain proprietary source, prompts, generated code, inputs, paths, and provider metadata.
Store and share them according to source licensing and organizational policy. `sage clean` deletes one
validated run tree, but backups, Docker layers, provider-side telemetry, and external caches require
their own retention controls.
