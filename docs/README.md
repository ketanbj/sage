# Documentation guide

Start with the [project README](../README.md) for a short introduction.
You can read these guides in order, or choose the one that answers your question.

| Your question | Read |
|---|---|
| How do I install it and try it? | [Getting started](getting-started.md) |
| What has been done, and what is left? | [Current status](status.md) |
| What do the tests and proofs establish? | [Verification](verification.md) |
| How does it work, and how do I contribute? | [Development](development.md) |
| What are the exact contracts and tool versions? | [Technical reference](reference.md) |

For a presentation, use the [overview slides](../artifacts/sage-slides/output/SAGE-Project-Overview.pdf)
or the [technical slides](../artifacts/sage-slides/output/SAGE-Einsums-and-Symbolic-Verification.pdf).
For recorded results, use the [six-operation report](../artifacts/tensor-six/report.md)
and [proof-extension report](../artifacts/pending-proofs/report.md).

## Terms used in the guides

| Term | Meaning here |
|---|---|
| Tensor | A multidimensional array. A matrix is a rank-two tensor |
| Upstream | The original Einsums implementation at the recorded source revision |
| Port or candidate implementation | The independent Rust or C++ translation being checked |
| Reference | An independent expected result, usually computed with NumPy |
| Campaign | A run that generates new inputs and compares the implementations |
| Replay | Running previously generated inputs again, possibly through more APIs |
| SymSan | A tool that tracks input-dependent execution and solves constraints to generate test inputs |
| Bounded proof | An exhaustive check of a stated specification within a fixed domain and assumptions |
| API | The functions and types a user calls |
| FFI | The interface used to call the native library from another language |

The guides describe the maintained project. Detailed source-level examples remain
with the [Rust port](../ports/einsums-rs/README.md) and
[C++ port](../ports/einsums-cpp/README.md). Historical run bundles are local evidence,
so links to their paths are not downloads from this repository.
