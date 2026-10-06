# Repository preparation

The repository contains the SAGE orchestration package, Einsums Rust/C++20 ports,
source fixtures, target catalogs, tests, configurations, lockfiles, proof harnesses,
curated proof summaries and the maintained PPTX/PDF presentations. Potential
targets have catalog records without executable adapters.

## Local and generated files

`.gitignore` excludes `runs/`, `.sage/`, virtual environments, Python caches,
Cargo/CMake output, packaged wheels, downloaded JavaScript dependencies, private
slide builds, Office lock files and local environment files. Keep `.env.example`,
`uv.lock` and `Cargo.lock` in Git. `.gitattributes` preserves LF line endings in
source and proof harnesses and marks presentation files as binary.

The tracked `artifacts/tensor-six/` files summarize the recorded proof milestone.
Their paths are relative to the repository and their summaries retain original
manifest hashes. Full immutable run bundles, logs, LLVM certificates and native
binaries remain separate local evidence under ignored `runs/`; the summaries are
not standalone solver bundles. Use [the verification instructions](tensor-six-proof.md)
to regenerate them in a clean checkout, or distribute full bundles separately.

The SAGE Python package declares Apache-2.0 and includes the standard root license.
The Einsums ports retain their MIT licenses in their respective directories.
Upstream source and licenses captured by a run must remain together when shared.

## Verify a checkout

Install Python 3.11+, uv, Rust and a C++20 compiler. The C++ port also needs CMake,
Eigen, nlohmann JSON and HDF5 as described in [its README](../ports/einsums-cpp/README.md).

```sh
uv sync --all-extras --locked
uv run ruff check sage tests tools scripts
uv run mypy sage
uv run pytest
cargo test --locked --offline --manifest-path ports/einsums-rs/Cargo.toml
cmake -S ports/einsums-cpp -B .sage/cpp20-build -DCMAKE_BUILD_TYPE=Release
cmake --build .sage/cpp20-build
ctest --test-dir .sage/cpp20-build --output-on-failure
```

A fresh Cargo checkout needs its dependencies fetched before `--offline` can work.
Ordinary tests do not need credentials or Docker. Actual SymSan campaigns and
formal verification require their documented pinned toolchains and images. The
proof runners reject missing tooling or incomplete evidence.

## GitHub repository

The repository is [ketanbj/sage](https://github.com/ketanbj/sage). Its default branch
is `main`. Clone it before following the checkout validation commands above:

```sh
git clone https://github.com/ketanbj/sage.git
cd sage
```

Review the files included in each change before committing and pushing:

```sh
git status --short
git add --dry-run .
git add .
git diff --cached --stat
git commit -m "Describe the change"
git push origin main
```
