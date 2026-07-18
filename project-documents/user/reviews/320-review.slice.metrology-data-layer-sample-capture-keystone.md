---
docType: review
layer: project
reviewType: slice
slice: metrology-data-layer-sample-capture-keystone
project: squadron
verdict: UNKNOWN
sourceDocument: project-documents/user/slices/320-slice.metrology-data-layer-sample-capture-keystone.md
aiModel: moonshotai/kimi-k2.7-code
status: complete
dateCreated: 20260718
dateUpdated: 20260718
findings:
  - id: F001
    severity: concern
    category: error-handling / resilience
    summary: "New I/O paths lack enumerated failure modes and explicit handling"
    location: project-documents/user/slices/320-slice.metrology-data-layer-sample-capture-keystone.md#implementation-details
  - id: F002
    severity: pass
    category: scope
    summary: "Keystone scope correctly defers non-keystone work to subsequent slices"
    location: project-documents/user/slices/320-slice.metrology-data-layer-sample-capture-keystone.md#technical-scope
  - id: F003
    severity: pass
    category: architectural-alignment
    summary: "Core architectural commitments are satisfied"
    location: project-documents/user/slices/320-slice.metrology-data-layer-sample-capture-keystone.md#architecture
  - id: F004
    severity: pass
    category: technical-decisions
    summary: "Version-keying tension is captured and deferred appropriately"
    location: project-documents/user/slices/320-slice.metrology-data-layer-sample-capture-keystone.md#technical-decisions
  - id: F005
    severity: note
    category: documentation-consistency
    summary: "Minor CLI syntax inconsistency in the verification walkthrough"
    location: project-documents/user/slices/320-slice.metrology-data-layer-sample-capture-keystone.md#verification-walkthrough
---

# Review: slice — slice 320

**Verdict:** UNKNOWN
**Model:** moonshotai/kimi-k2.7-code

## Findings

### [CONCERN] New I/O paths lack enumerated failure modes and explicit handling

The keystone introduces several new I/O boundaries, but the design only states “typed errors/actionable messages” without enumerating failure modes or recovery strategies. The design document should specify, before implementation:
- **Subprocess git remote call:** how long to wait (timeout), what constitutes failure if `git` is not installed or the remote command hangs, and whether to cache/fallback to the recorded `metrology.project_id` on transient failure.
- **Reading the 300 review result file:** behavior when the file is missing, malformed, or partially written, and how the “no stable id” join fails explicitly.
- **Target resolution ambiguity:** explicit handling when zero or multiple review files match the provided `(slice-index, review-type)` pair.
- **Atomic store write:** failure handling if the write-then-rename fails, or if the store directory is not writable/created.
- **Interactive CLI capture:** behavior for non-TTY environments, SIGINT during prompt, invalid input, and timeout/waiting on human input.

Without this, runtime failure modes remain implicit and operators may see unclear errors.

### [PASS] Keystone scope correctly defers non-keystone work to subsequent slices

The included work is limited to the data layer, stable identity, content-addressed result reference, and blind human-sample capture surface. It explicitly excludes agreement/dispersion reporting (321), version-keying resolution and minimum-evidence floor (322), audit findings/noise-floor harness (323), threshold feedback, and MCP tooling. This matches the architecture’s anticipated slices and non-goals.

### [PASS] Core architectural commitments are satisfied

The design satisfies the architecture’s load-bearing commitments:
- **Store locality:** user-level central store at `~/.config/squadron/metrology/`, aggregating across projects and standing independently of 280.
- **Stable project identity:** derived from normalized git remote URL or recorded `metrology.project_id`, with explicit failure rather than path-based fallback.
- **Read-side-only over 300:** consumes `ReviewResult` and `review/persistence.py`; no modification to the judging path, parser, or result write semantics.
- **Blind capture:** enforced at the data layer by constructing the presented payload from artifact + ground truth only, withholding judge output until after the human verdict is committed.
- **Pull-based, budgeted, non-blocking sampling:** operator-initiated command with configured `metrology.sample_budget`; skips record nothing; no pipeline waits on a human verdict.

### [PASS] Version-keying tension is captured and deferred appropriately

The design records both a `JudgeConfigId` (template+model+template content hash) and the content hash at capture time, while explicitly deferring the decision of which becomes the comparability key to slice 322. It also leaves open the coordinated 300 write-path change as a future option. This aligns with the architecture’s stated tension and preferred/fallback resolution.

### [NOTE] Minor CLI syntax inconsistency in the verification walkthrough

Step 2 of the walkthrough shows `sq metrology sample <n> --type slice`, but the API Contracts section documents the command as `sq metrology sample <target>` with accepted target forms of a file path or a `(slice-index, review-type)` pair. Ensure the walkthrough matches the final CLI option shape or that the `--type` flag is documented in the API Contracts section.
