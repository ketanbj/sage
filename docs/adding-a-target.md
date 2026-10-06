# Adding a target

## 1. Propose before implementing

Copy `candidates/template.yaml` to `candidates/<id>.yaml`. Fill every assessment field with sourced
facts, null, or an empty list. Candidate creation does not recommend or select the target. Run
`sage target show`, `assess`, and `compare` to check the record.

## 2. Define the scientific contract

Document the bounded translation unit, source/target languages, canonical inputs, observable outputs,
ordering/layout, references, invariants, tolerance source, invalid inputs, and blind spots. Pin upstream
revisions and preserve license attribution. Identify an independent reference when practical.

## 3. Implement the adapter-owned behavior

Target-specific code must own:

- upstream preparation and source capture;
- translation-unit and prompt selection;
- native build adapters and instrumentation flags;
- canonical input serialization, validation, and allocation bounds;
- bootstrap seeds and a SymSan generator with a target-specific decoder;
- compatibility and independent reference runners;
- numerical/structural equivalence policy;
- discrepancy replay/minimization and target-specific limitations.

Do not add these assumptions to `sage.core`. Register adapter and runtime module paths in
`targets/registry.py` only after implementation. Dynamic loading prevents the generic core from
importing target packages.

## 4. Add configuration and tests

Create an explicit `configs/<id>.yaml` platform-demo profile; do not change `configs/sage.yaml` from
`target: null`. Add schema/bounds tests, deterministic generator tests, native integration against all
references, mutation cases for likely semantic errors, and the smallest offline end-to-end run.

```console
uv run sage run --target <id> --mode platform-demo --provider offline --seed 12345
```

The offline translation provider must require no key or paid call. SymSan-only validation requires
Docker and prepared images; seed inputs must never be used as fallback validation cases. Unsupported adapters should fail clearly without falling back to a different target.

## 5. Keep approval separate

Technical feasibility can move a candidate to `FEASIBLE`; it does not select a pilot. After discovery,
any recommendation remains its own authored artifact. Scientific-pilot execution requires an actual
human-approved `SelectionDecision` supplied with `--selection` and matching the target.
