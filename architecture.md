# Architecture

## Components

- `WorkflowCore`: routes a task by its declared `kind`, invokes one registered handler, and sends the result to verification.
- `ToolRegistry`: explicit mapping from task kind to handler. Duplicate registrations are rejected.
- `GovernancePolicy`: preserves mandatory execution checks and configures task-specific structural evidence schemas.
- `SemanticValidatorRegistry`: optional registry of application-supplied, task-kind-specific validators.
- `ResultVerifier`: computes a final status from execution, structural, and any configured semantic check results.
- `LoopDetector`: bounded run-scoped detector for repeated calls/outcomes, short oscillations, and consecutive failure cascades; a detected pattern latches `WorkflowCore` into `BLOCKED` until a trusted progress event is supplied.
- `InProcessRunner`: compatibility backend that invokes a handler in the current process.
- `SubprocessHandlerRunner`: optional child-process backend with JSON IPC, a wall-clock timeout, and POSIX resource limits.
- `DockerSandboxRunner`: optional digest-pinned Docker backend with disabled networking, no host mounts, a read-only root filesystem, dropped capabilities, a non-root identity, and container resource limits.
- `WorkflowReport`: returns route, tool result, check results, and a compact audit record.

## Execution path

1. Validate task identity and kind.
2. Resolve a handler. An absent handler produces `BLOCKED`.
3. Run the handler. Exceptions and malformed handler returns become explicit failure results.
4. Feed each routed task attempt, arguments, outcome, and unique per-instance event ID to the bounded loop detector, including missing-handler and execution-backend-blocked outcomes. A finding marks the report `BLOCKED` and latches the core so subsequent handler calls do not execute until a progress event is supplied.
5. Evaluate mandatory execution checks and structural evidence completeness.
6. If semantic mode is enabled by injecting a `SemanticValidatorRegistry`, require a validator for every task kind and run it only after structural completeness passes. Missing validators yield `UNKNOWN`.
7. Determine the overall status from all check results, including the loop guard.
8. Return the report; no external side effects or persistence are implied.

## Loop-guard limits

The detector sees only events observed by this `WorkflowCore` instance and uses deterministic signatures over JSON-compatible arguments/results. The call that crosses the detection threshold has already run; only later calls are blocked. A progress event resets the detector only when the caller supplies `progress=True` and an event ID, so the host must independently establish that the milestone is real. This library-level integration does not intercept ChatGPT runtime calls or external plugins. If an observation cannot be fingerprinted, the loop check is `UNKNOWN`, not `PASS`.

## Evidence levels

Structural completeness and semantic validation are separate checks. A structural schema establishes that required fields are present, not that the fields are true. A semantic validator is supplied by the application and can enforce only its implemented domain rules. A validator's `PASS` is not source authentication or independent proof unless those mechanisms are actually implemented and their evidence is checked. Validator exceptions and invalid return types produce `UNKNOWN`; they do not produce `PASS`.

Semantic validation is opt-in for compatibility. Without a registry, the workflow retains structural-only behavior and must not be described as semantically verified. With a registry, missing task-specific validators fail closed to `UNKNOWN`. Applications requiring semantic verification must register validators for the relevant task kinds and test their domain-specific assumptions, adversarial inputs, and source dependencies.

## Boundaries

The default runner is in-process. The optional subprocess runner adds process separation and resource limits but is not a security sandbox: it uses the same OS identity and does not isolate filesystem or network access. The optional Docker runner provides a stronger container boundary only when the target Docker daemon, host, and digest-pinned image are trusted and correctly configured. It accepts only importable top-level handlers and JSON-serializable task data/results; the handler module must be present in the image. Unit tests mock Docker CLI execution, so a real deployment still needs target-environment and adversarial integration tests. The project does not implement plugin discovery, authentication, or distributed scheduling.


## Pre-inference Memory Gate (experimental)

The `MemoryGate` module is a fail-closed policy primitive for an application that
must retrieve user-scoped memory before model inference.

- The trusted host adapter supplies a `GateRequest` bound to the exact outbound
  request digest and a `MemorySnapshot` containing scoped content, source IDs,
  retrieval time, and provider version.
- The gate checks subject scope, memory age/future timestamp, context size, and
  request/snapshot provenance. It issues a short-lived HMAC-SHA256 token bound
  to the request digest, policy version, memory snapshot digest, and hashed
  subject/request/source identifiers.
- `execute` invokes the supplied model callback only after memory validation,
  token verification, and a successful pre-invocation audit write. If the
  pre-invocation audit sink fails, the model callback is not invoked. If the
  post-invocation audit write fails, the result is `UNKNOWN`, not `PASS`.
- Audit events contain digests and hashed identifiers, not raw memory content
  or raw subject IDs.

### Enforcement boundary and limitations

This module is not an HTTP proxy, Notion client, OpenAI client, or authentication
provider. The host must retrieve memory from an authenticated user-scoped source,
supply a durable audit sink, and keep provider credentials inaccessible to
callers. Every model invocation must be routed through the controlled executor;
otherwise a caller can bypass the library and invoke the provider directly.

The signed token is short-lived but this initial module does not maintain a
distributed single-use nonce/replay store. The nonce is an integrity-bound
identifier, not proof of one-time use. The module does not authenticate the
memory provider or prove that memory content is factually correct.

Accordingly, this library alone is **not** `ENFORCED_BY_HOST`. That status
requires a deployed host boundary, credential isolation, real Notion and model
adapters, and independent tests proving direct calls cannot bypass the gate.

**Current scope:** library primitive and local regression tests only. No external
credentials, Notion integration, HTTP service, or production deployment are
included in this change.


### Notion memory source adapter (experimental)

`NotionMemoryProvider` uses a separate server-side Notion integration token
(`NOTION_API_KEY`) and a configured authenticated subject
(`MEMORY_GATE_SUBJECT_ID`). It reads the current workspace's Memories,
Memory Archive, Memory Projects, Memory Relations, and Memory Sources data
sources, plus the About and Operating Rules pages. It uses Notion API version
`2026-03-11`, data-source query pagination, recursive block-child retrieval,
a conservative request interval, and bounded 429 retries.

The provider returns a `MemorySnapshot` with the fetched page/data-source IDs,
a version digest derived from page edit timestamps, and a retrieval timestamp.
It fails closed on subject mismatch, missing configuration, API/network errors,
malformed pages, missing required pages, or context-size overflow. It excludes
email and phone-number properties from extracted page metadata. It performs no
Notion writes and does not fall back to cached memory when Notion is unavailable.

The integration must have read-content capability and explicit access to every
configured data source and page. The ChatGPT Notion connector's session/token is
not inherited by this server; the server requires its own Notion integration
credential, stored only in the host's secret environment.

**Verification scope:** mocked HTTP tests cover endpoint/version headers,
pagination, nested blocks, 429 retry, unauthorized response sanitization,
subject scoping, bounded context, and environment configuration. No live Notion
API credential has been supplied, so live authentication and retrieval remain
untested. The provider currently loads all rows from the small configured memory
data sources; relevance ranking and caching are intentionally deferred.


### Gated OpenAI Responses API adapter (experimental)

`OpenAIResponsesClient` is a text-only adapter for `POST /v1/responses`.
It requires `OPENAI_API_KEY`, an explicitly configured `OPENAI_MODEL`, and
a gate-token verifier. Before sending any request it recomputes the exact
outbound payload digest and verifies the signed gate token against the
`GateRequest`; payload substitution or an invalid/expired token is rejected
before network access.

The adapter accepts only two plain user messages (the actual request and a
JSON-encoded memory context), fixed server instructions, a bounded
`max_output_tokens`, and `store=false`. It rejects tools, streaming,
conversation chaining, arbitrary extra fields, and client-selected models.
It never retries a model POST. A network timeout or 5xx response is
`UNKNOWN` because the request may already have been processed; known 4xx
errors are recorded as `FAIL`.

`store=false` disables Responses API application-state storage for the
request, but it does **not** by itself guarantee zero data retention: default
abuse-monitoring logs may still contain customer content and be retained for
up to 30 days. Zero Data Retention or Modified Abuse Monitoring requires
separate OpenAI approval. ChatGPT subscription billing and API billing are
separate; API usage requires its own billing configuration.

**Verification scope:** mocked HTTP tests cover payload binding, gate-token
verification, policy rejection, response parsing, key redaction, no-retry
behavior, and ambiguous outcome classification. No live OpenAI API key or
model has been configured, so live inference, model availability, and actual
billing remain untested.
