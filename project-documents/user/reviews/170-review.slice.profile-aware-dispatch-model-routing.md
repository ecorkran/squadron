---
docType: review
layer: project
reviewType: slice
slice: profile-aware-dispatch-model-routing
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/170-slice.profile-aware-dispatch-model-routing.md
aiModel: z-ai/glm-5.1
status: complete
dateCreated: 20260428
dateUpdated: 20260428
findings:
  - id: F001
    severity: concern
    category: scope-creep
    summary: "`sq dispatch` introduces CLI surface not defined in architecture's Command Surface"
    location: 170-slice.profile-aware-dispatch-model-routing.md#Design
  - id: F002
    severity: concern
    category: error-handling
    summary: "Missing failure-mode enumeration for new I/O paths"
    location: 170-slice.profile-aware-dispatch-model-routing.md#Design
  - id: F003
    severity: concern
    category: nfr-compliance
    summary: "NFR targets not restated for dispatch latency path"
    location: 170-slice.profile-aware-dispatch-model-routing.md#Overview
  - id: F004
    severity: note
    category: package-structure
    summary: "Package structure alignment — new file location is architecturally consistent"
    location: 170-slice.profile-aware-dispatch-model-routing.md#Design
  - id: F005
    severity: pass
    category: model-resolution
    summary: "Model resolution cascade alignment is correct"
    location: 170-slice.profile-aware-dispatch-model-routing.md#Design
  - id: F006
    severity: pass
    category: action-protocol
    summary: "Action protocol and data model alignment is correct"
    location: 170-slice.profile-aware-dispatch-model-routing.md#Design
  - id: F007
    severity: pass
    category: scope-boundaries
    summary: "Scope boundaries respected — no 160-band incursion"
    location: 170-slice.profile-aware-dispatch-model-routing.md#Non-Goals
---

# Review: slice — slice 170

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.1

## Findings

### [CONCERN] `sq dispatch` introduces CLI surface not defined in architecture's Command Surface

The architecture document explicitly defines the CLI command surface under "Command Surface": `sq run`, `sq run --resume`, `sq run --status`, `sq run --list`, `sq run --validate`. There is no `sq dispatch` command. The slice introduces a new top-level CLI subcommand (`sq dispatch`) that constitutes a public, stable interface the slice itself flags as a risk ("any future change to its arg shape is a breaking change"). While the one-shot agent mode is architecturally acknowledged (architecture: "One-shot agent mode: Each dispatch creates a fresh agent. Used for non-SDK providers"), the CLI surface to invoke it is not specified. This is a meaningful expansion of the command surface that should be reflected in the architecture document, or at minimum acknowledged as an intentional extension. The architecture's "sq phase" TBD entry shows the pattern for adding commands — they're discussed at the architecture level first.

### [CONCERN] Missing failure-mode enumeration for new I/O paths

The slice introduces three new I/O paths without enumerating failure modes or explicit handling strategies:

1. **`sq dispatch` subprocess invocation by slash handler** — The slash handler runs a Bash command and captures stdout. Failure modes not enumerated: subprocess hang (no timeout specified), subprocess crash mid-output, slash handler disconnect before stdout capture completes, temp-file write failure before command invocation. The design says "Capture stdout as the dispatch response" but does not specify timeout, retry, or fallback behavior.

2. **Temp-file staging by slash handler** — The renderer emits `--prompt-file {tmp_path}` and the slash handler replaces it after writing the file. Failure modes: temp directory not writable, temp file collision, slash handler crash after write but before invocation (orphan temp files), encoding issues with multi-KB prompt content. No cleanup strategy is mentioned.

3. **`_one_shot_dispatch` helper via agent registry** — Spawns a one-shot agent, sends a message, collects response, shuts down. Failure modes: agent spawn failure, timeout during response collection, partial response on agent crash, registry not returning a provider for the resolved profile. The design says "Print the response on stdout. Errors print to stderr with non-zero exit" but does not specify what happens on partial responses or hangs.

The architecture requires that failure modes for each new I/O path be enumerated with explicit handling strategy, not "TBD" or implicit.

### [CONCERN] NFR targets not restated for dispatch latency path

The architecture document defines the dispatch action as owning "Model resolution, agent lifecycle, output capture, token tracking." The slice introduces a materially different dispatch path (subprocess invocation via `sq dispatch` → one-shot agent) that adds subprocess spawn latency, temp-file I/O, and inter-process communication overhead compared to the existing in-session `_dispatch_via_session` path. If the architecture has any NFR targets for dispatch latency or throughput (the architecture references "reducing per-step latency" in the context of the deferred SDK Client Warm Pool), the slice should restate the specific NFR target for the new path and confirm the added overhead is acceptable. The slice does not address performance implications of the subprocess-based dispatch path at all.

### [NOTE] Package structure alignment — new file location is architecturally consistent

The new file `src/squadron/cli/commands/dispatch.py` is not shown in the architecture's package structure (which lists `src/squadron/pipeline/actions/dispatch.py` for the action), but the architecture does show `src/squadron/data/` as a sibling directory and the CLI framework (slice 103) is a prerequisite. The CLI commands directory is a reasonable extension consistent with the existing pattern (`src/squadron/cli/app.py` is referenced). This is acceptable but the architecture's package structure diagram should be updated to reflect CLI command files if this pattern is established.

### [PASS] Model resolution cascade alignment is correct

The slice correctly uses `ModelResolver` with the architecture's defined cascade pattern. The renderer resolves the alias via `resolver.resolve(alias)`, then branches on `is_sdk_profile(profile)`. This aligns with the architecture's model resolution chain and the one-shot agent mode ("Each dispatch creates a fresh agent. Used for non-SDK providers"). The `--model` and `--profile` flags on `sq dispatch` correctly reflect the cascade: model is resolved, profile can be explicit or derived from alias resolution.

### [PASS] Action protocol and data model alignment is correct

The slice correctly uses the existing `ActionInstruction` dataclass (which already has a `command` field) and does not modify the `Action` protocol or `ActionResult` structure. The `ProviderAPIError` propagation through the existing exception-handling path in `execute()` correctly follows the architecture's action protocol pattern: action returns `ActionResult(success=False, error=…)`, pipeline executor flow control halts. No new action types or protocol changes are introduced.

### [PASS] Scope boundaries respected — no 160-band incursion

The slice explicitly excludes retry/backoff redesign, transport-protocol abstraction, and any ReviewTransport-style refactor, correctly deferring these to the in-flight review-decoupling work. The non-goals section properly fences the work within 140-band scope. No convergence loops, model pools, escalation behaviors, or conversation persistence features are introduced.
