# SymSan integration

## Pinned toolchain and image

SAGE pins R-Fuzz/SymSan commit `ecbe8a7d6a5ceb687df16660d6f3f60f844b5bd4` in image
`sage-symsan:ecbe8a7`. The image targets Ubuntu 24.04, Linux amd64, Clang/LLVM 18, and Z3 4.13.3.
Ubuntu 24.04's Z3 4.8.12 is older than the selected SymSan commit permits, so the Dockerfile installs
the official Z3 4.13.3 x64 release by a recorded SHA-256 before configuring SymSan. Exact revision
rationale is in [upstreams.md](upstreams.md). Boost.Container and gperftools development/runtime
packages match the selected commit's parser build requirements. The runtime stage also retains the
unversioned Clang 18 command names, static libc++/libc++abi and zlib development archives, and Python
development runtime required by the pinned compiler wrapper and Python extension.

```console
docker build --platform linux/amd64 -t sage-symsan:ecbe8a7 containers/symsan
uv run sage doctor
```

Apple Silicon uses amd64 emulation. The image is a reproducibility boundary: do not replace it with a
host build and claim the same environment.

## Instrumentation and execution

Einsums profiles build the target-specific input harness with `ko-clang` using
`KO_USE_FASTGEN=1`, `KO_DONT_OPTIMIZE=1` and bounded optimization settings. Builds
and execution mount run-specific directories with networking disabled. Instrumented
binaries are never performance-eligible. The container Python binding launches them
out of process, reads symbolic records and requests Z3 solutions.

Each target must supply its own decoder. Einsums validates fixed-size tensor or
library-profile bytes before concrete upstream, candidate and NumPy replay. The
shared generator has no fallback scientific input format.

## SymSan-only validation

Only new, valid SymSan outputs enter validation. Bootstrap examples and boundaries seed the solver
but never count as evidence. Empty corpora report `NO_TEST_CASES`; disabled, failed and timed-out
campaigns cannot pass. The driver records unsupported expressions and continues bounded exploration.
Einsums uses its own binary decoder and C++ instrumentation; see [the tensor stage](einsums-tensors.md).

## Modes, traces, and bounds

`trace_only: true` initializes no solver and records events without calling parse or solve APIs.
Normal mode records symbolic events, solver status, generated paths, target exit status, and campaign
completion in `traces/events.jsonl`; driver stderr and a structured summary are stored alongside it.

The default campaign is limited to 30 seconds, 128 tasks, 2048 MiB, one CPU, 128 processes, 10 MiB of
captured output, 128 generated inputs, and a derived event cap. Configuration can tighten these limits.
A failed solve, timeout, malformed input, missing image, driver failure, or unsupported operation is an
explicit outcome and adds no passing evidence.

## Troubleshooting

- `docker daemon / SymSan: UNAVAILABLE`: start Docker Desktop or the Linux daemon.
- `SymSan image: MISSING`: run the platform-specific build command above.
- `exec format error`: include `--platform linux/amd64` and enable Docker's amd64 emulation.
- Z3 version rejection: rebuild the checked-in Dockerfile; do not use Ubuntu's 4.8.12 headers.
- `ko-clang` failure: inspect the target-specific build log and confirm LLVM 18 in `sage doctor`.
- Campaign timeout: inspect partial JSONL and reduce seeds/tasks; do not relabel timeout as a pass.
- Invalid generated cases: inspect adjacent `.invalid.json`; malformed data is intentionally quarantined.

The adapter boundary allows future i2s, Jigsaw, alternate Z3 configurations, and solver-free tracing
without changing the differential runner.

## Einsums library profile

The CPU/Python library profile instruments a C input harness and treats all C++ library code as a
native boundary. It does not explore Einsums-internal branches. Its per-seed task cap is recorded
along with global task/corpus/time limits. The earlier tensor profile retains template instrumentation.
See [the library contract](einsums-library.md) for the boundary rationale and completion limitations.
