# Target selection

## Current status

SAGE starts with zero selected scientific targets. Gau2Grid, DKH and GDMA are
`PROPOSED` potential targets without executable adapters or bundled demonstrations.
Einsums is `UNDER_ASSESSMENT` for scientific selection and has implemented Rust and
C++20 CPU/Python runtimes plus bounded six-operation proofs. Technical implementation
does not itself authorize a scientific pilot.
Unknown assessment fields are intentionally null or empty pending discovery.

## Three distinct concepts

1. A **candidate** is a versioned description and assessment of a possible target. Its lifecycle
   state records assessment progress, not authorization.
2. A **recommendation** is a separately authored proposal that cites candidates and evidence. SAGE
   does not create or infer a recommendation from comparison output.
3. An **approved selection** is a human decision record. It alone authorizes scientific-pilot mode.

The supported candidate states are `PROPOSED`, `UNDER_ASSESSMENT`, `FEASIBLE`, `SELECTED`,
`DEFERRED`, and `PILOT_COMPLETE`. A candidate YAML marked `SELECTED` still cannot replace the
decision record; state and approval remain separate controls.

## Assessment content

Every candidate record captures scientific value, proposed translation unit, languages, build
complexity, tests, reference implementations, numerical-equivalence requirements, SymSan
compatibility, developer availability, risks, evidence, confidence, and open PI questions. Use null
or an empty list when evidence is absent. Do not infer developer availability or scientific priority.

```console
uv run sage target list
uv run sage target show <target>
uv run sage target assess <target>
uv run sage target compare gau2grid dkh gdma einsums
```

`compare` displays recorded fields without weights, scores, ranking, or recommendation.

The retired `psi4-module` placeholder resolves to `einsums` as a compatibility alias for earlier
commands and draft records. It is not listed as a second candidate and does not imply selection.

## Approval workflow

1. Copy `candidates/template.yaml` and fill only sourced facts.
2. Conduct PI and developer discovery; add evidence references and leave unresolved fields explicit.
3. If requested, author a separate recommendation outside the candidate record.
4. A human decision-maker copies `decisions/selection-template.yaml` and records an actual decision.
5. Validate and record it locally:

```console
uv run sage target select <target> --decision decisions/<target>.yaml
uv run sage target selection-status
```

An approved selection requires schema `1.0`, kind `target-selection`, matching target, status
`APPROVED`, decision ID, nonempty human approver and approval time, rationale, and evidence list.
`target select` stores the decision and its hash in `.sage/selection.json`; it does not edit the
candidate YAML.

## Run modes

Platform demonstrations prove that SAGE mechanics work; they do not assert that a target is the
right scientific investment:

```console
uv run sage run --target einsums --mode platform-demo --provider offline --seed 12345
```

Scientific pilots require the approved record again at execution time, binding the evidence bundle
to its authorization:

```console
uv run sage run \
  --target <target> \
  --mode scientific-pilot \
  --selection decisions/<approved-decision>.yaml
```

Missing, draft, malformed, or wrong-target decisions fail before a run directory or target runtime
is created. Approval does not make an unimplemented adapter executable; selection and implementation
readiness are separate.
