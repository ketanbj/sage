# Pinned upstreams

Inspected 2026-09-02.

| Project | Repository | Commit | License | Confirmed build facts |
|---|---|---|---|---|
| Einsums | `https://github.com/Einsums/Einsums` | `22a115978041e905461b24d9ca2a17bfcce01f32` (`v1.1.5`) | MIT | C++20 and CMake 3.25.2+; requires BLAS/LAPACK and HDF5; can fetch fmt, Catch2, h5cpp, argparse, and spdlog; FFT, HIP, cpptrace, LibreTT, and pybind11 integrations are optional |
| SymSan | `https://github.com/R-Fuzz/symsan` | `ecbe8a7d6a5ceb687df16660d6f3f60f844b5bd4` | Apache-2.0 | Linux amd64, tested Ubuntu 24.04, LLVM/Clang 18.1.18, CMake, libc++/libc++abi; Python binding can trace without solving; `ko-clang` is the documented wrapper |

The SymSan image also pins the official `z3-4.13.3-x64-glibc-2.35.zip` release artifact
with SHA-256 `32c7377026733c9d7b33c21cd77a68f50ba682367207b031a6bfd80140a8722f`.
Ubuntu 24.04 supplies Z3 4.8.12, but this SymSan commit checks for Z3 4.8.15 or newer.

Upstream may move; the full hashes above, not branch names, define this prototype.
