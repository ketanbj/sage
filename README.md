# SAGE

**Semantically Aligned Generation and Equivalence**

SAGE helps answer a practical question: **does translated scientific code still
produce the expected results?** It runs the original code, a translated version
and NumPy, an independent numerical library, on the same inputs, then saves the results
so differences can be investigated and reproduced.

The current project translates **Einsums**, a library for multidimensional arrays
and scientific calculations, into **Rust** and **C++20**. Both translations include
Python packages.

## Where the project stands

| Area | Current state |
|---|---|
| Translation | Rust and C++20 implementations cover the chosen CPU library and Python functions |
| Behavioral checks | Generated and saved test inputs compare each translation with the original and NumPy |
| Formal verification | Six array operations have proofs for a small, defined input domain in both languages |
| Still open | Compatibility differences, broader proofs, downstream integration and performance comparisons |

The complete library is **not yet certified equivalent**. Passing tests and the
six proofs cover specific behavior. GPU support is outside this project's
current scope. See [current results and limits](docs/status.md).

The `prending-proofs` branch adds adapter guard and larger-layout proofs, selected
library-path exploration and interface/ABI checks. See the
[extension report](artifacts/pending-proofs/report.md) for exact scope and open
reference findings.

## Start here

For a quick look at the project, open the
[overview slides](artifacts/sage-slides/output/SAGE-Project-Overview.pdf).

### Prerequisites

Use a macOS or Linux shell. You need access to the private GitHub repository,
Git, Python 3.11+ and [uv](https://docs.astral.sh/uv/), plus `make` for the Makefile
shortcuts. Install the additional tools for the workflow you want:

| Workflow | Additional prerequisites |
|---|---|
| Explore the CLI or run Python unit tests | None; `uv sync` installs the Python dependencies |
| Try the Rust-backed Python library | Rust 1.84+ with Cargo, a C compiler and CMake |
| Try the C++-backed Python library | C/C++20 compiler, CMake 3.20+, Eigen 3.4+, nlohmann JSON 3.11+ and HDF5 C development files |
| Run comparison campaigns | The selected port's build tools, `make`, Docker running with Linux amd64 support, built images and prepared upstream source |
| Run formal proofs | Rust/rustup, C/C++20 build tools, Docker, the pinned verifier bundle and compiler image; the installer currently supports macOS arm64 only |

First-time package, source and image downloads require internet access. Apple
Silicon uses Docker's amd64 emulation for campaigns. See
[setup details](docs/getting-started.md#prerequisites-and-settings) for dependency
checks and the complete preparation commands.

### Required settings

The standard workflow uses the checked-in `offline` translation provider and needs
**no API key, model setting or `.env` file**. Select Einsums with `--target einsums`;
Rust is the default. Select C++ with `--config configs/einsums-cpp-library.yaml`.
The supplied configurations already contain source pins, limits and tolerances.

For the optional earlier Rust model-translation profile, set `OPENAI_API_KEY` and
`SAGE_MODEL`. SAGE does not automatically read `.env`; the
[environment-settings guide](docs/getting-started.md#optional-environment-settings)
shows how to load it explicitly. Installed Python packages locate their native
libraries automatically.

### First commands

After cloning the repository, run these commands from its root:

```sh
uv sync --all-extras --locked
uv run sage --help
uv run sage target list
```

This installs the Python tooling and lists the available targets. It does not run
a translation or validation campaign. Follow [Getting started](docs/getting-started.md)
to try a translated Python package or run a comparison.

## Documentation

- [Getting started](docs/getting-started.md): setup, a small example and your first comparison.
- [Current status](docs/status.md): what is implemented, checked and still pending.
- [Verification](docs/verification.md): what the evidence means and how to reproduce it.
- [Development](docs/development.md): architecture, tests and adding a target.
- [Technical reference](docs/reference.md): API differences, input formats and toolchain pins.

The [documentation guide](docs/README.md) includes a suggested reading order and
short definitions of the project's terminology.

## Repository map

Start with `docs/` to understand the project or `artifacts/` to review results.
For the translated implementations, open `ports/`. The other folders support
running, testing or extending the project.

| Folder | What it contains |
|---|---|
| [docs/](docs/) | The six guides: setup, status, verification, development and technical reference, plus the reading guide |
| [artifacts/](artifacts/) | Presentation files in `sage-slides/output/`; maintained proof evidence in `tensor-six/` and `pending-proofs/` |
| [ports/](ports/) | Independent implementations and Python packages: `einsums-rs/` for Rust, `einsums-cpp/` for C++20 |
| [sage/](sage/) | Python code that prepares builds, generates inputs, compares results and writes reports |
| [configs/](configs/) | YAML run settings and versioned translation instructions in `prompts/` |
| [targets/](targets/) | The target catalog in `candidates/` and optional pilot-planning templates in `templates/` |
| [tests/](tests/) | Unit and native integration tests |
| [tools/](tools/) | Setup and wheel builds; `verification/` contains proof collection, API replay and library-path/backend experiments |
| [verification/](verification/) | Formal proof specifications and harness source code used by the verifiers |
| [fixtures/](fixtures/) | Comparison drivers, input decoders and reference/translation fixtures used by campaigns |
| [containers/](containers/) | Docker build definitions for the pinned generation and upstream-reference environments |

`targets/` collects the former candidate, decision and recommendation folders.
Its templates are only needed when proposing a target or approving a scientific
pilot; the normal demonstration workflow is in [Getting started](docs/getting-started.md).

After running the tools, `runs/` holds detailed local evidence, `.sage/` holds
downloaded tools and workspace state, and `.venv/` holds Python dependencies.
These generated folders, caches and native build outputs are excluded from Git.
At the root, `Makefile` collects common commands, while `pyproject.toml` and
`uv.lock` define the Python package and its dependencies.

## Licenses

SAGE uses [Apache-2.0](LICENSE). The
[Rust](ports/einsums-rs/LICENSE.txt) and [C++](ports/einsums-cpp/LICENSE.txt)
ports retain their MIT licenses.
