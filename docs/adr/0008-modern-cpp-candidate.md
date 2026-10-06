# ADR 0008: Independent modern C++ candidate

Status: accepted, 2026-10-05

## Decision

Add C++20 as a target for the bounded Einsums tensor profile, following the user's
request. Retain Rust as the existing default and its broader CPU/Python port.
The original Einsums library already uses C++20, so implement the selected
semantics independently with standard-library ownership and borrowed spans.

## Consequences

The C++20 candidate has a separate build identity, source snapshot and campaign
configuration, while sharing the three-way validation policy. Unsupported scope
or provider choices fail explicitly. Copy/transpose kernels keep syntax accepted
by CBMC without changing their production implementation. The modern wrapper is
checked natively, not represented by a substitute model in the formal proof.
Source-binding certificates connect the proof syntax to C++20 compilation.

This extends ADR 0004's Rust-first decision; it does not imply that C++20 or Rust
guarantees numerical equality, whole-library compatibility or performance.

## CPU/Python extension, 2026-10-06

Extend the independent C++20 candidate to the established CPU/Python scope: 90 pinned core
exports, 16 utility helpers, decompositions, storage, HDF5 and FFT. Provide native headers,
a shared library, and an installable Python package. Eigen supplies independent factorization
kernels; HDF5 supplies file-format support. Owned storage and retained-owner views use standard
C++20 facilities. Python interface code shares its origin with the Rust port but loads only the
C++ backend; numerical work is not delegated to Rust or upstream Einsums.

The full-library campaign and replay have separate evidence identities. Infrastructure replacements
do not reproduce every upstream C++ template overload or vendor ABI. Compatibility disagreements,
downstream validation and performance remain open. The six-operation implementation is preserved
byte-for-byte, so its existing kernel proof is unchanged and does not extend to the broad API.
