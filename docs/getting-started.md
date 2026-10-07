# Getting started

Choose how far you want to go. You can read results without installing anything,
try a translated library without Docker, or run a full comparison campaign.
Commands below assume a macOS or Linux shell and start in the repository root.

## Prerequisites and settings

Start with Git, Python 3.11+ and [uv](https://docs.astral.sh/uv/). Cloning this
private repository requires GitHub access and Git authentication. The `make`
shortcuts also require `make` on your command path.

| What you want to try | Install or prepare |
|---|---|
| CLI and unit tests | Base tools above; `uv sync --all-extras --locked` installs the Python packages |
| Rust Python package | Rust 1.84+ and Cargo, a C compiler, CMake; the source build fetches locked numerical/HDF5 dependencies |
| C++ Python package | C and C++20 compiler, CMake 3.20+, Eigen 3.4+, nlohmann JSON 3.11+, HDF5 C headers/libraries |
| Rust campaign | Rust build tools plus running Docker, prepared source/images and fetched Cargo dependencies |
| C++ campaign | C++ build tools plus running Docker and prepared source/images |
| Formal proofs | Rust/rustup, C/C++20 build tools, Docker and pinned Kani/CBMC setup; current installer supports macOS arm64 only |

To check tools before a native build:

```sh
git --version
python3 --version
uv --version
```

For Rust, also check `rustc --version`, `cargo --version`, `cc --version` and
`cmake --version`. For C++, check `c++ --version` and `cmake --version`, and install
the [C++ development dependencies](../ports/einsums-cpp/README.md#build).
`uv sync` installs Python packages; native compilers and system libraries are
separate prerequisites.

Docker must be running and able to mount the repository directory. Campaign
images use Linux amd64; Apple Silicon needs Docker emulation. Package installation,
Cargo fetching, source preparation and initial image builds need network access.
The prepared validation containers run with networking disabled.

For the standard examples, the supplied settings are sufficient:

| Setting | Use for your first run |
|---|---|
| Target | `--target einsums` |
| Translation provider | `--provider offline`, using the checked-in code |
| Language/profile | Default Rust library profile, or `--config configs/einsums-cpp-library.yaml` |
| Run mode | `platform-demo`, the default; scientific-pilot mode requires a separate human decision |
| API credentials or model | No settings required for the standard workflow |
| Native library paths | Installed packages find their bundled library automatically |

Source revisions, generation bounds and tolerances are already in `configs/`.
`uv run` uses the project's Python environment, so its commands need no manual
virtual-environment activation.

## 1. Explore the project

Install Git, Python 3.11+ and [uv](https://docs.astral.sh/uv/), then:

```sh
git clone https://github.com/ketanbj/sage.git
cd sage
uv sync --all-extras --locked
uv run sage --help
uv run sage target list
```

The repository is private, so cloning requires access to `ketanbj/sage`.
Einsums is the implemented target. The other catalog entries are potential future
targets. No scientific pilot is selected by default.

For an overview of the results, read [Current status](status.md). For a lightweight
development check, run `make test`, which runs the Python unit tests without Docker
or API credentials.

## 2. Try the translated Python library

The Rust and C++ packages use the same import names, `einsums` and `pyeinsums`.
Install them into separate environments. This example uses the Rust package and
requires Rust 1.84+, a C compiler and CMake in addition to the tools above:

```sh
uv venv .sage/venvs/rust
uv pip install --python .sage/venvs/rust/bin/python ports/einsums-rs
.sage/venvs/rust/bin/python
```

At the Python prompt, multiply two matrices:

```python
import einsums as ein
import numpy as np

a = ein.utils.create_tensor(np.array([[1.0, 2.0], [3.0, 4.0]]))
b = ein.utils.create_tensor(np.eye(2))
print(np.asarray(a @ b))
# [[1. 2.]
#  [3. 4.]]
```

The calculation runs in the translated native library. NumPy supplies the Python
array storage. This example is a usage check, not a validation campaign.

For C++ installation, native headers and its additional Eigen/JSON/HDF5 dependencies,
follow the [C++ build guide](../ports/einsums-cpp/README.md#build). Once those
dependencies are installed, try the same example in a separate C++ environment:

```sh
uv venv .sage/venvs/cpp20
uv pip install --python .sage/venvs/cpp20/bin/python ports/einsums-cpp
.sage/venvs/cpp20/bin/python
```

Paste the Python example above at that prompt. The
[Rust port guide](../ports/einsums-rs/README.md) has more API examples.

## 3. Run a comparison campaign

A campaign generates inputs and compares the original Einsums, the selected port
and NumPy. It requires Docker running, Rust, a C/C++ compiler and the package setup
above. C++ campaigns also need the full C++ dependencies from its build guide.

Build the reproducible environments and fetch the pinned source:

```sh
make build-containers
make build-einsums-container
make prepare-einsums
cargo fetch --locked --manifest-path ports/einsums-rs/Cargo.toml
uv run sage doctor --config configs/einsums-library.yaml
```

The Rust campaign compiles with `--offline`; the fetch step populates Cargo's
cache before that build. A prior successful source installation also fetches these
dependencies. `sage doctor` checks common tools, including Rust, and the selected
image/daemon. It does not check every C++ dependency; the C++ build guide's CMake
configure step checks Eigen, JSON and HDF5 discovery.

Builds and source downloads need network access. The images use Linux amd64;
Apple Silicon runs them through Docker emulation. Once prepared, the `offline`
provider uses the checked-in translation without a model call. Docker is still
needed to generate validation inputs.

Run one language at a time:

```sh
# Rust CPU/Python profile
uv run sage run --target einsums --mode platform-demo --provider offline

# Independent C++20 CPU/Python profile
make demo-cpp20-library
```

The command prints its `runs/<run-id>` directory. Open `report.md` or `report.html`
there. The report separates generation, comparison results and the scope gate.
**`INCOMPLETE_SCOPE` and a nonzero exit are expected for the full-library profile:**
current probes do not establish the whole compatibility contract. Check the report
to distinguish that scope limit from a build, generation or comparison failure.

## Optional environment settings

The standard installed-package examples and offline campaigns need no environment
variables. Use the following only for optional translation services or native
source development:

| Variable | When to set it |
|---|---|
| `OPENAI_API_KEY` | Only when explicitly using `--provider openai` for the earlier Rust tensor profile |
| `SAGE_MODEL` | With that provider; set a model ID your API account can use |
| `SAGE_SAM_ENDPOINT` | Future adapter development; no SAM service is bundled and current Einsums profiles reject this provider |
| `EINSUMS_RS_LIBRARY` | Optional Rust development override: absolute path to the native `.dylib` on macOS or `.so` on Linux |
| `EINSUMS_CPP_LIBRARY` | The corresponding optional C++ native-library override |

For optional OpenAI translation, copy the template and fill in the key/model:

```sh
cp .env.example .env
# Edit .env and fill OPENAI_API_KEY and SAGE_MODEL, then:
uv run --env-file .env sage run --target einsums \
  --config configs/einsums.yaml --provider openai
```

Run the campaign preparation steps first. This provider sends the bounded source
unit and prompt to the API; it applies only to the earlier single-file Rust tensor
profile. Full-library and C++ profiles use `offline`. SAGE reads process environment
variables, not `.env` automatically; `uv run --env-file .env` loads the file
explicitly. `.env` is excluded from Git. Leave native-library overrides unset for
normal package use so the bundled backend can load.

For formal verification, follow [the pinned proof setup](verification.md#setup-and-run)
after installing the prerequisites above. The installer records the required Rust
nightly and verifier versions; do not substitute arbitrary tool versions for a
reproducibility claim.

## Inspect or reproduce a result

Replace `<run-id>` and `<case-id>` below with names from your own run:

```sh
uv run sage report --run runs/<run-id>
uv run sage reproduce runs/<run-id>/discrepancies/<case-id>
```

Keep the run directory and its recorded Docker image for replay. Raw run bundles
are excluded from Git; they are not included in a fresh clone.

## Common setup problems

| Symptom | Next step |
|---|---|
| Docker unavailable | Start the Docker daemon, then rerun `sage doctor` |
| SymSan image missing | Build the containers above |
| `exec format error` | Check that Docker supports Linux amd64 emulation |
| Native build failed | Read the run's `builds/` logs and check the port's dependencies |
| No accepted generated inputs | Read `traces/symsan-outcome.json` and `traces/events.jsonl` |
| Results disagree | Read all implementations' outputs and the saved discrepancy replay |

Continue with [Verification](verification.md) to interpret results, replay a corpus
through more APIs, or run the formal proof profiles.
