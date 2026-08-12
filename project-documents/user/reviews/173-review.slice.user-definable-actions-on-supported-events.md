---
docType: review
layer: project
reviewType: slice
slice: user-definable-actions-on-supported-events
project: squadron
verdict: PASS
sourceDocument: project-documents/user/slices/173-slice.user-definable-actions-on-supported-events.md
aiModel: minimax/minimax-m3
status: complete
dateCreated: 20260811
dateUpdated: 20260811
reviewedSha: 8a67d6b3bcab2a73f53a6e030bd5bd33d31977b1
findings:
  - id: F001
    severity: pass
    category: uncategorized
    summary: "Event mechanism sits below the pipeline action layer"
    location: 173-slice.user-definable-actions-on-supported-events.md#d1-event-scoped-contexts-the-pipeline-actionactioncontext-are-untouched
  - id: F002
    severity: pass
    category: uncategorized
    summary: "Built-in migration matches 171/909/911 contract"
    location: 173-slice.user-definable-actions-on-supported-events.md#architecture
  - id: F003
    severity: pass
    category: uncategorized
    summary: "No arbitrary shell / subprocess plugins"
    location: 173-slice.user-definable-actions-on-supported-events.md#explicitly-excluded
  - id: F004
    severity: pass
    category: uncategorized
    summary: "Failure modes enumerated for every new I/O path"
    location: 173-slice.user-definable-actions-on-supported-events.md#d5-failure-modes-coarse-attributed-never-silent-carried-from-171-contract-e
  - id: F005
    severity: pass
    category: uncategorized
    summary: "Discovery is declared, not scanned; safe by design"
    location: 173-slice.user-definable-actions-on-supported-events.md#d7-discovery-declared-imports-not-scanning
  - id: F006
    severity: pass
    category: uncategorized
    summary: "Hook re-pointing preserves 172's hard-fail semantics"
    location: 173-slice.user-definable-actions-on-supported-events.md#d8-process-entry-point-sq-events-fire
  - id: F007
    severity: pass
    category: uncategorized
    summary: "Prompt-only parity preserves prompt-only execution mode"
    location: 173-slice.user-definable-actions-on-supported-events.md#d9-prompt-only-parity-at---step-done-carried-from-171-unchanged
  - id: F008
    severity: pass
    category: uncategorized
    summary: "NFRs not stated in parent are not falsely claimed"
    location: 173-slice.user-definable-actions-on-supported-events.md
  - id: F009
    severity: note
    category: uncategorized
    summary: "Architecture package-structure update is correctly flagged as a slice deliverable"
    location: 173-slice.user-definable-actions-on-supported-events.md#provides-to-other-slices
---

# Review: slice — slice 173

**Verdict:** PASS
**Model:** minimax/minimax-m3

## Findings

### [PASS] Event mechanism sits below the pipeline action layer

The slice explicitly keeps `Action`/`ActionContext`/pipeline action registry untouched and creates a separate `EventContext` hierarchy. This is consistent with the architecture's "Action protocol is SOLID foundation — each action has one home" principle and avoids the speculative concern of adding a third thing to the pipeline action registry. Decision D1 is well-reasoned and aligns with the architecture's "no scope creep" boundary.

### [PASS] Built-in migration matches 171/909/911 contract

The architecture reserves a `hooks/` package and a "Post-Action Hook Registry" with the spec "observe | warn | fail the action" and severity clamping. The slice's authority model (D4: observe / fail / mutate) preserves the substance: a hook may not otherwise mutate the action result, may not read outputs, failure handling matches the 909-before-911 ordering that existed. The 911 revision-stamp's "must never fail" requirement is enforced by the stamp's own contract (always success=True, logs at WARNING), not a runner clamp — this is a small divergence in mechanism but not in observable behavior, and is explicitly justified (no severity axis designed now).

### [PASS] No arbitrary shell / subprocess plugins

The architecture explicitly excluded shell hooks from 171 ("Shell is the security surface... it can be added later and cannot be removed later"). The slice carries this forward identically, and even restricts plugin code to in-process Python callables. Direct alignment.

### [PASS] Failure modes enumerated for every new I/O path

The slice enumerates four explicit failure modes (plugin import raise, action raise, timeout, unknown action name) each with a handling strategy: attributed log at the named level, treated as Fail or as manifest error, with no skip-and-continue path. The "no silent path" rule is explicit. The timeout is bounded by `events.timeout_seconds` (default 30) via `asyncio.wait_for`, with the timeout-exceeded case handled identically to a raise. Exit codes (0/1/2) are explicit for the COMMIT path; POST_ACTION stops on failure and propagates the error onto the pipeline `ActionResult`.

### [PASS] Discovery is declared, not scanned; safe by design

Plugins are imported only by module path explicitly listed in the manifest, with `cwd` prepended to `sys.path` for the import step and removed after. No directory scanning, no entry-points, no `pkgutil` walking. This matches the architecture's preference for explicit declaration over implicit discovery (compare to action registry: "Actions are well-defined operations regardless of how pipelines compose them" — not "things found in directories"). Sandboxing is correctly excluded per the PM's threat model statement, and the rationale is recorded.

### [PASS] Hook re-pointing preserves 172's hard-fail semantics

The hook change re-adds a `uv`/squadron dependency at commit time (noted as a known trade-off in Risk Assessment) but preserves the "missing tool = hard fail" contract from slice 172. Exit codes (0/1/2) match the existing 172 gate semantics, so existing expectations and tests are not broken. The byte-identity test on `PRE_COMMIT_HOOK` is preserved as a success criterion.

### [PASS] Prompt-only parity preserves prompt-only execution mode

The slice correctly handles the prompt-only mode (no in-process executor): POST_ACTION bindings are invoked at `_handle_step_done` by synthesizing an `ActionResult(success=True, outputs={})` per expanded action. The "no read of result.outputs" rule is what makes this safe. The `--step-done` exit-code change is explicitly flagged as a CHANGELOG break with a `disable:` escape hatch, matching the architecture's posture on explicit breaking changes.

### [PASS] NFRs not stated in parent are not falsely claimed

The parent architecture document does not state any latency/throughput NFRs for the executor's post-action site or the git-hook entry point. The slice does not invent NFRs; it introduces a single timeout config (`events.timeout_seconds`, default 30) as the only temporal bound, with explicit handling for timeout-exceeded as Fail. No false NFR claims.

### [NOTE] Architecture package-structure update is correctly flagged as a slice deliverable

The slice notes that the parent architecture's Component Architecture / Package Structure sections and authority model will be updated as part of this slice. This is good discipline — closing the loop rather than letting the architecture drift — but it does mean reviewers should expect a follow-up to `140-arch.pipeline-foundation.md` once this slice lands. No issue; worth tracking.
