# Einsums whole-library candidate

## Decision status

Einsums replaces the former unidentified `psi4-module` placeholder. Its canonical candidate ID is
`einsums`; `psi4-module` remains a deprecated lookup alias. The candidate is `UNDER_ASSESSMENT`.
It is not scientifically selected, and SAGE still starts with zero selected scientific targets.
An executable [CPU tensor stage](einsums-tensors.md) now translates bounded tensor operations to Rust
and validates only SymSan-generated inputs. This staged implementation does not complete the
whole-library candidate described below.

The longer-term candidate scope is the complete pinned Einsums v1.1.5 library.
Recording that scope does not claim that a one-shot translation is technically sound. Evidence may be
developed subsystem by subsystem while the completion claim remains whole-library.

## Why Einsums

[Einsums](https://github.com/Einsums/Einsums) is an MIT-licensed C++20 scientific-computing library
for multidimensional tensors, contractions, permutations, linear algebra, decompositions, FFTs, I/O,
CPU and optional accelerator backends, and Python bindings. Psi4 added it as an optional dependency in
[PR 3050](https://github.com/psi4/psi4/pull/3050) and later added build and test integration for
`pyeinsums` in [PR 3350](https://github.com/psi4/psi4/pull/3350).

The upstream record supplies concrete assessment targets:

- [Issue 236](https://github.com/Einsums/Einsums/issues/236) records row/column-major behavior affecting
  `syev`, `heev`, `geev`, and `gesv`.
- [Issue 251](https://github.com/Einsums/Einsums/issues/251) records LAPACK discovery and Psi4 vendor/include-order friction.
- [Issue 284](https://github.com/Einsums/Einsums/issues/284) records restrictions around newer HDF5,
  fmt, and spdlog dependencies.
- [Issue 295](https://github.com/Einsums/Einsums/issues/295) records that Python tests are not enabled on Windows.
- [Issue 302](https://github.com/Einsums/Einsums/issues/302) records technical debt, downstream compile-time
  concerns, Python compatibility difficulty, and a proposed version-2 restructuring.

These are evidence of meaningful risk and useful test hypotheses. They are not evidence that a full
translation is feasible or scientifically preferred.

## Pinned assessment baseline

The assessment baseline is tag `v1.1.5`, commit
`22a115978041e905461b24d9ca2a17bfcce01f32`. The upstream README requires C++20, BLAS/LAPACK, and
HDF5. Its CMake project requires CMake 3.25.2. Several C++ dependencies can be fetched when absent;
FFT, HIP, cpptrace, LibreTT, and pybind11 integrations are optional.

The source pin establishes a reproducible baseline. Before implementation, SAGE must decide whether
critical fixes are applied as explicit patches, compared as a second upstream revision, or treated as
known reference limitations. Moving silently to the evolving version-2 trunk would invalidate the pin.

## Baseline experiment: 2026-09-03

The pinned commit was configured and built in clean Ubuntu 24.04 containers on an Apple Silicon host.
The successful baseline used Linux arm64, GCC 13.3, CMake 3.28.3, Python 3.12.3, OpenBLAS LP64,
HDF5 1.10.10, FFTW 3.3.10, NumPy 1.26.4, pybind11 2.13.6, and SciPy 1.16.1. GPU support,
backtraces, performance benchmarks, Valgrind, and the external-consumer build test were not enabled.

The result is partial but substantive:

- all 307 configured build targets, including the C++ libraries, examples, test executables, and
  Python extension, built successfully;
- all 206 registered CTest tests passed: 158 compile-only header tests, 43 unit tests, and five
  examples;
- the installed Python suite's best run passed 723 cases and skipped 137 CPU-inapplicable GPU cases;
- two random-data Python cases still failed: complex `geev` and complex `qr` on tensor views. The
  assertions compare eigenvectors up to real sign only and compare QR factors elementwise. Complex
  eigenvectors and QR factors are phase-nonunique, and repeated runs produced different failing
  cases. These checks need fixed seeds plus residual, orthogonality, reconstruction, and subspace
  criteria before they can be used as equivalence gates.

The experiment also found reproducibility and packaging gaps:

- Ubuntu 24.04's `pybind11-dev` does not provide `pybind11/typing.h`; compilation stopped at
  `EinsumsPy/LinearAlgebra/src/eigen.cpp` until pybind11 2.13.6 was supplied;
- SciPy is used by the Python tests but is not part of CMake configuration. SciPy 1.11.4 lacks the
  `null_space(..., lapack_driver=...)` API used by 16 parametrized cases; SciPy 1.16.1 supplies it;
- the installed extension requires both `libfftw3.so.3` and `libfftw3f.so.3` at runtime;
- tag `v1.1.5` at the pinned commit configures and installs libraries with version `1.1.3` in their
  CMake output and sonames.

The successful build and broad test execution establish CPU build feasibility for one environment.
They do not establish portability, accelerator feasibility, Psi4 integration, translation
feasibility, or scientific equivalence, so the candidate remains `UNDER_ASSESSMENT`.

## Whole-library contract

The final claim must cover every included public runtime subsystem and binding at the pin:

1. tensor types, views, slicing, strides, allocation, and ownership;
2. tensor contractions, permutations, element operations, and tiled/block behavior;
3. BLAS/LAPACK-backed linear algebra and decompositions;
4. HDF5 I/O and optional FFT behavior;
5. runtime configuration, error handling, threading, and supported backend dispatch;
6. Python import, lifetime, dtype, shape, exception, and result behavior;
7. build, install, package discovery, and downstream consumption by Psi4.

Optional accelerator support must be explicitly included or excluded by the human decision record.
If excluded, reports must say “CPU/Python compatibility,” not “whole Einsums equivalence.”

## Equivalence model

One global tolerance is inadequate. Each operation family needs a versioned policy covering dtype,
shape, layout, condition number, scale, backend, and algorithm. Exact comparison is appropriate for
metadata, shapes, index maps, serialized structure, and deterministic error categories. Numerical
comparison should combine absolute and relative error with invariants such as residuals,
orthogonality, reconstruction error, conservation relationships, and agreement with an independent
oracle.

Eigenvectors require sign or complex-phase normalization; degenerate eigenspaces require subspace
comparison rather than vector-by-vector equality. Nondeterministic reductions need repeated-run and
distribution bounds. Known upstream defects must be labeled as compatibility observations rather than
quietly promoted to the desired scientific contract.

Behavioral validation remains sampled evidence. Even complete passage of the recorded suites would
not formally prove equivalence for every tensor size, index pattern, compiler, dependency, or device.

## Delivery gates

1. **Baseline:** stabilize the two non-invariant Python checks, then reproduce the pinned CPU and
   Python tests in a second recorded environment.
2. **Inventory:** enumerate public APIs, modules, optional features, dependency calls, and unsupported paths.
3. **Harness:** define canonical cases and independent oracles per operation family.
4. **Translation:** translate and build the full source tree in the approved target language.
5. **Subsystem validation:** validate tensors, algebra, linear algebra, I/O/FFT, runtime, and Python separately.
6. **Platform matrix:** execute the approved compiler, BLAS/LAPACK, OS, Python, threading, and device matrix.
7. **Downstream validation:** build and test approved Psi4 workflows against both implementations.
8. **Whole-library report:** aggregate coverage and disclose every exclusion, waiver, reference defect, and discrepancy.

The candidate can move to `FEASIBLE` only after stakeholders define the target language and required
surface and the baseline, adapter, representative translations, and equivalence campaigns demonstrate
that the full scope is tractable. Only a separate human-approved decision can authorize a scientific pilot.
