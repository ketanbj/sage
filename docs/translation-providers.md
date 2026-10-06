# Translation providers

`TranslationProvider.translate(request)` accepts a versioned source unit, bounded source text,
versioned prompt, and hashes, then returns target code, structured metadata, provider identity, and a
response hash. Providers do not build or execute their output.

## Offline fixture provider

The default provider copies the checked-in Rust fixture deterministically. It requires no network,
credentials, or model and is the CI acceptance path. Its metadata and content hash still flow through
the same artifact contract as a network response.

Einsums full-library profiles snapshot the checked-in multi-file port rather than emitting a
single source file. `configs/einsums-cpp-library.yaml` selects the independent C++20 port;
the default selects Rust. These profiles accept only the offline provider and record separate
source/build identities. The single-file network providers remain limited to the tensor profile.

## OpenAI provider

The OpenAI adapter is activated only with `--provider openai`. It requires `OPENAI_API_KEY` and
`SAGE_MODEL`; no model name is hardcoded. It uses the official Responses API, strict structured JSON,
bounded SDK retries and timeout, `store=False`, and a maximum output size. It records returned model,
prompt version, request unit, response hash, and a response-ID hash. It omits upstream exception text
because an SDK error may echo source or request data. Secrets are never written to artifacts.

Selecting this provider is the user's explicit authorization to send the captured source unit and
prompt to OpenAI. Offline and SAM selections do not send source to OpenAI.

## SAM-compatible endpoint

`provider: sam` uses `SAGE_SAM_ENDPOINT` and a version-1 JSON request/response contract. The request
contains source language, target language, unit identifiers, source hash, source text, and prompt.
Responses are limited to 10 MiB and must contain `code` and `metadata`. No endpoint or trained SAM is
bundled; selection without configuration fails precisely as unsupported.

## Prompt versioning and failures

Prompts live under `prompts/` and request complete code, API/ABI and layout assumptions, numerical
assumptions, dependencies, unsupported constructs, confidence by component, and function mappings.
The filename/version and SHA-256 are copied into every run. Provider failures stop translation as
infrastructure failures; SAGE never substitutes a fixture silently, retries indefinitely, treats prose
as executable policy, or automatically edits numerical tolerances.
