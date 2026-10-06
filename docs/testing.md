# Testing strategy

`make check` runs Ruff formatting/lint, strict mypy, unit tests, native integration and target-specific
orchestration checks. It does not require Docker, credentials or model calls. These implementation
tests are distinct from scientific validation campaigns.

Full C++ integration requires a C++20 compiler, CMake, Eigen, nlohmann JSON and HDF5.
See the [C++ build instructions](../ports/einsums-cpp/README.md). The complete October 6
project suite after repository cleanup passes 129 tests with five backend-specific skips. Both native CTest contracts also
run under ASan/UBSan. The Python API contract suite runs independently against both backends.

Unit coverage includes target selection, compatibility, binary input rejection, exact shape/stride
comparison, rectangular transpose and matrix contraction, numerical/reference error classification,
nonfinite outputs, and generated-corpus import excluding unchanged seeds and duplicates.

Orchestration checks explicitly stub generation traces and Docker responses, verify
failed traces retain an infrastructure-failure outcome, and confirm disabled or
trace-only generation cannot pass. Bootstrap fixtures used in native integration
are implementation regression inputs rather than scientific campaign evidence.

For a real Einsums acceptance campaign:

```console
make build-containers
make build-einsums-container
make prepare-einsums
make demo
```

Inspect the manifest for `COMPLETED`, nonzero `symsan` input counts, no other origins, and concrete
comparisons. `operation-coverage.json` reports the selected profile's operations (six tensor
operations or 23 library probes), including any
with no generated evidence. The manifest records SymSan events, rejected payloads, unsupported
expressions, bounds and native ABI boundaries. Reports never infer full-library coverage.

Mutation checks should alter tensor layout or numeric outputs and verify structural or numerical
failure. A mutated C++ reference must be classified as `REFERENCE_DISAGREEMENT` even when Rust
matches it. Saved discrepancies support `sage reproduce` against the captured image and binaries.

For C++20 use `make demo-cpp20-library`. The native integration grid checks 4,416 combinations
of profile operation, dimensions and value patterns; another 69 checks exercise the actual Python
campaign runner. `make validate-einsums-cpp-api RUN=runs/<generated-library-run>` replays
authenticated inputs over 31 API groups and four dtypes. It is not new solver generation.
Nonunique factorization outputs are checked with reconstruction, orthogonality and eigenpair
residuals. Literal upstream basis/order mismatches remain documented compatibility differences.
