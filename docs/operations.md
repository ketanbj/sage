# Operations

## Setup

Install Python 3.11+, `uv`, Git, a C compiler, Rust, and Docker. Linux amd64 containers provide the
pinned SymSan/Einsums environment; Apple Silicon uses emulation.

```console
uv sync --all-extras
make check
make build-containers
make build-einsums-container
uv run sage target prepare --target einsums
make demo
```

Image builds and upstream preparation require network access. Subsequent offline-provider campaigns
make no API calls, but Docker is required: all validation inputs now come from SymSan. Bootstrap
inputs seed exploration only. Missing generation never falls back to examples or random validation.

## Translation providers

`--provider offline` selects the checked-in Rust translation. Explicit `--provider openai` requires
`OPENAI_API_KEY` and `SAGE_MODEL`, and sends the bounded source for translation. The SAM endpoint
contract is available for future adapters; Einsums rejects unsupported providers.

## Runs and reports

```console
uv run sage run --target einsums --mode platform-demo --provider offline
uv run sage report --run runs/<run-id>
uv run sage reproduce runs/<run-id>/discrepancies/<case-id>
```

The Einsums stage is documented in [einsums-tensors.md](einsums-tensors.md). Each isolated run captures
source and license, configuration, translations, build commands, immutable image ID, generation traces,
accepted cases, per-operation counts, executions and comparisons. Failures retain reports and logs.
The CLI returns nonzero for a failed, empty, incomplete or discrepant campaign.

`NO_TEST_CASES` means SymSan completed but generated no new valid inputs. `TIMEOUT` and
`INFRASTRUCTURE_FAILURE` never become successful runs when partial cases pass. Shape and stride
errors, numerical differences and C++/NumPy reference disagreements remain distinct.

Einsums replay uses the recorded image ID and saved native candidate binaries. Keep the
corresponding run directory and image when saving evidence.

Scientific-pilot mode additionally requires a human-approved target-bound decision via `--selection`.
Platform-demo execution creates no scientific selection.

## Troubleshooting

- Docker unavailable: start the daemon; SymSan-only validation cannot proceed without it.
- Missing image: build the SymSan base, then the Einsums image.
- Build failure: inspect `builds/cpp-*.log`, `builds/rust/build.log`.
- Empty corpus: inspect `traces/symsan-outcome.json` and `traces/events.jsonl`; never substitute seeds.
- Unsupported symbolic expressions: inspect the recorded count and native ABI boundaries.
- C++/NumPy mismatch: investigate the reference; matching Rust/C++ output alone cannot pass.
- Discrepancy: inspect all three executions and the clean replay before drawing conclusions.

`uv run sage clean --run <run-id>` removes exactly one direct child of `runs/` containing a manifest.
It does not remove upstream caches or Docker images.
