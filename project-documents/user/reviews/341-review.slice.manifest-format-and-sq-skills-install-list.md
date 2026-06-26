---
docType: review
layer: project
reviewType: slice
slice: manifest-format-and-sq-skills-install-list
project: squadron
verdict: PASS
sourceDocument: project-documents/user/slices/341-slice.manifest-format-and-sq-skills-install-list.md
aiModel: minimax/minimax-m2.7
status: complete
dateCreated: 20260625
dateUpdated: 20260625
findings:
  - id: F001
    severity: pass
    category: uncategorized
    summary: "Correctly implements dispatch model from spike 340"
    location: 341-slice.manifest-format-and-sq-skills-install-list.md#schema
  - id: F002
    severity: pass
    category: uncategorized
    summary: "Merge semantics decision is appropriate and documented"
    location: 341-slice.manifest-format-and-sq-skills-install-list.md#manifest-location-and-merge-semantics
  - id: F003
    severity: pass
    category: uncategorized
    summary: "Error handling covers all stated failure modes"
    location: 341-slice.manifest-format-and-sq-skills-install-list.md#success-criteria
  - id: F004
    severity: pass
    category: uncategorized
    summary: "Git dependency documented and handled explicitly"
    location: 341-slice.manifest-format-and-sq-skills-install-list.md#technical-decisions
  - id: F005
    severity: pass
    category: uncategorized
    summary: "Idempotent install semantics correctly specified"
    location: 341-slice.manifest-format-and-sq-skills-install-list.md#file-copy-semantics
  - id: F006
    severity: pass
    category: uncategorized
    summary: "Integration points match consuming/providing slices"
    location: 341-slice.manifest-format-and-sq-skills-install-list.md#integration-points
  - id: F007
    severity: pass
    category: uncategorized
    summary: "Out-of-scope items appropriately deferred"
    location: 341-slice.manifest-format-and-sq-skills-install-list.md#out-of-scope
  - id: F008
    severity: pass
    category: uncategorized
    summary: "Component structure respects architectural boundaries"
    location: 341-slice.manifest-format-and-sq-skills-install-list.md#component-structure
  - id: F009
    severity: note
    category: uncategorized
    summary: "No NFRs from parent architecture to restate"
    location: 341-slice.manifest-format-and-sq-skills-install-list.md
---

# Review: slice — slice 341

**Verdict:** PASS
**Model:** minimax/minimax-m2.7

## Findings

### [PASS] Correctly implements dispatch model from spike 340

The slice correctly adopts the dispatch model decision from the spike, supporting both `prefix` and `dispatch_file` as mutually exclusive options in the manifest. This aligns with the architecture's principle: "The dispatch model (`/sq:analysis <skill>`) is adopted; the manifest format (slice 341) will support a `dispatch_file` option alongside `prefix`."

### [PASS] Merge semantics decision is appropriate and documented

The architecture flagged "Per-project vs. user-level manifest — a project-local `skills.toml` enables project-specific pack sets. Merge semantics need a decision at slice design time." The slice makes a clear, well-reasoned decision: additive union with project-level override. Rationale is provided. This closes an open question that the architecture left for slice design time.

### [PASS] Error handling covers all stated failure modes

The slice enumerates failure modes with explicit handling strategies: missing pack (clear error with available pack names), invalid source type (`SkillSourceError` with actionable message), unreachable GitHub source (clear message identifying pack and URL), missing manifest (actionable "no manifest found" message), and git not on PATH (explicit requirement + message). No "TBD" or implicit handling found.

### [PASS] Git dependency documented and handled explicitly

The document states: "git must be on PATH; if not, fail with a clear message: 'git is required to install packs from GitHub sources. Install git and retry.'" This matches the architecture's guidance of "shallow clone or single-file download" while making failure handling explicit. Verification step 8 validates this behavior.

### [PASS] Idempotent install semantics correctly specified

Install is additive within a pack's prefix directory, overwrites existing files silently, and provides a summary indicating (re)installed. This matches the architecture's "File copy is the delivery primitive" principle without introducing destructive behavior that would complicate rollback scenarios.

### [PASS] Integration points match consuming/providing slices

Provides `install_pack()`, `load()`, and the `bundled` source type to slice 342. Consumes `_get_commands_source()` pattern from slice 100. Correctly identifies that `manifest.py` is usable by slice 343 for `sq doctor` checks. App.py change is scoped to a single line.

### [PASS] Out-of-scope items appropriately deferred

Version pinning/lock files, `sq skills update`, registry/community pack index, `sq skills uninstall`, and `sq doctor` integration are all correctly listed as out of scope. This aligns with the architecture's "Minimal mechanism" goal and the anticipated slice ordering.

### [PASS] Component structure respects architectural boundaries

The `skills/` subpackage has no dependency on CLI concerns; `cli/commands/skills.py` is the thin Typer layer. This correctly enforces the architecture's separation between mechanism (file copy + manifest) and CLI surface.

### [NOTE] No NFRs from parent architecture to restate

The parent architecture document does not contain stated NFRs (latency, throughput, etc.) that would require restatement in the slice. This is not a concern — the slice operates on user-interactive timescales where explicit NFRs are not applicable.
