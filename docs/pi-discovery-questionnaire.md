# PI discovery questionnaire

Use this questionnaire before recommending or selecting a scientific pilot. Record answers and
evidence; do not fill gaps by inference.

## Scientific value and scope

- What scientific workflow, decision, or bottleneck should the pilot improve?
- Which repository, revision, module, and smallest meaningful translation unit are in scope?
- Which inputs, outputs, derivatives, symmetries, units, layouts, and failure behaviors are observable?
- What is explicitly outside scope, and what result would make the pilot scientifically useful?

## References and numerical behavior

- Which implementation is the compatibility reference, and which reference is independently derived?
- What existing tests, examples, datasets, or published results may be reused?
- What absolute, relative, component-specific, or invariant criteria are scientifically justified?
- How should NaN, infinity, signed zero, underflow, overflow, nondeterminism, and reference disagreement
  be handled?

## Engineering feasibility

- What are the source and intended target languages, build system, dependencies, platforms, and licenses?
- Can the unit execute deterministically in a bounded subprocess with a canonical input format?
- Which compiler transformations or external calls could prevent SymSan instrumentation?
- What secrets, proprietary data, network services, hardware, or unavailable research assets are needed?

## People and decisions

- Who can explain the scientific contract and review a numerical discrepancy?
- Who can explain and maintain the source build and tests?
- What availability has each person actually confirmed?
- Who has authority to recommend, approve selection, accept results, or stop the pilot?
- What dated decision record and evidence are required before scientific-pilot mode?

## Completion and risk

- What concrete evidence would count as pilot completion, and what would remain unproven?
- Which errors are highest consequence, and which adversarial or robustness cases matter?
- What artifact retention, licensing, privacy, and publication constraints apply?
- What open questions must be answered before assessment state can advance?

## Einsums whole-library questions

- Does “whole library” include documentation tools, examples, benchmarks, Python packaging, and every
  optional GPU path, or only shipped runtime APIs and their tests?
- Which target language and foreign-function interface must replace or coexist with the C++20 API?
- Which Psi4 workflows actually exercise Einsums, and which downstream results form acceptance evidence?
- When upstream behavior conflicts with intended semantics, such as the recorded row/column-major
  linear-algebra issue, is compatibility with the defect required or should SAGE report an intentional fix?
- Which BLAS/LAPACK vendors, HDF5 versions, compilers, operating systems, Python versions, threading
  modes, and accelerator configurations are mandatory?
- Can acceptance be staged by subsystem while retaining the complete library as the final scope?
