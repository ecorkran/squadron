---
docType: review
layer: project
reviewType: slice
slice: sq-validate-docs-mechanical-frontmatter-enforcement
project: squadron
verdict: PASS
sourceDocument: project-documents/user/slices/172-slice.sq-validate-docs-mechanical-frontmatter-enforcement.md
aiModel: minimax/minimax-m3
status: complete
dateCreated: 20260803
dateUpdated: 20260803
findings:
  - id: F001
    severity: pass
    category: uncategorized
    summary: "Slice correctly positions itself relative to deferred slice 171"
    location: project-documents/user/slices/172-slice.sq-validate-docs-mechanical-frontmatter-enforcement.md#cross-slice-dependencies-and-interfaces
  - id: F002
    severity: note
    category: uncategorized
    summary: "File structure deviates from architecture's planned `documents/` package"
    location: project-documents/user/slices/172-slice.sq-validate-docs-mechanical-frontmatter-enforcement.md#components
  - id: F003
    severity: note
    category: uncategorized
    summary: "CI integration is technically out-of-scope per the architecture"
    location: project-documents/user/slices/172-slice.sq-validate-docs-mechanical-frontmatter-enforcement.md#d7
  - id: F004
    severity: note
    category: uncategorized
    summary: "Cross-package edit to `review/persistence.py`"
    location: project-documents/user/slices/172-slice.sq-validate-docs-mechanical-frontmatter-enforcement.md#d9
  - id: F005
    severity: note
    category: uncategorized
    summary: "Architecture's example of structured review findings shows the bug being fixed"
    location: project-documents/user/architecture/140-arch.pipeline-foundation.md#review-output-structured-findings
  - id: F006
    severity: note
    category: uncategorized
    summary: "No architecture NFRs apply to document validation; no restatement needed"
    location: project-documents/user/architecture/140-arch.pipeline-foundation.md
  - id: F007
    severity: note
    category: uncategorized
    summary: "Failure modes are largely enumerated but a few edge cases are implicit"
    location: project-documents/user/slices/172-slice.sq-validate-docs-mechanical-frontmatter-enforcement.md#d5
---

# Review: slice — slice 172

**Verdict:** PASS
**Model:** minimax/minimax-m3

## Findings

### [PASS] Slice correctly positions itself relative to deferred slice 171

The relationship to slice 171 is explicitly addressed: "171 generalizes two hardcoded executor post-action checks and revives only when a consumer must run *inside* a pipeline and *block* it. This slice does not create one — a commit gate is deliberately outside the pipeline." This is a correct read of the architecture's status note ("171 — DEFERRED, not built") and a defensible architectural decision. The slice does not pretend to implement 171's mechanism while doing something else.

### [NOTE] File structure deviates from architecture's planned `documents/` package

The architecture's Component Architecture section shows `src/squadron/documents/status.py` (DocumentStatus canonical enum, deferred to 171) and `src/squadron/documents/paths.py` (USER_DOCS_ROOT, deferred to 171) as the planned files. The slice creates `schema.py` (DocumentStatus + DocType + machine-artifact types + aliases) instead of `status.py`, and does not create `paths.py` (uses a config key `validate.docs_root` instead). The `schema.py` contents are broader than what 171 was scoped for. When 171 is eventually implemented, it will need to either adopt `schema.py` as canonical or move its `DocumentStatus` into a new `status.py`. This is a coordination concern but not a current violation, since slice 172 is not claiming to be 171.

### [NOTE] CI integration is technically out-of-scope per the architecture

The architecture's Scope Boundaries section explicitly lists "CI/CD integration" under "Out of Scope (future, unscheduled)." The slice adds `uv run sq validate docs` as a step in the existing `test` job (D7, criterion 16). The architecture's exclusion appears aimed at pipeline CI/CD (running pipelines in CI systems), whereas this slice uses existing CI infrastructure to run a document validator — a different category. The slice does acknowledge this is a "CI backstop." Worth flagging because the architecture does not bless CI integration in any form.

### [NOTE] Cross-package edit to `review/persistence.py`

The slice edits `src/squadron/review/persistence.py` directly to quote the `location` field. This is outside the `documents/` package boundary that the architecture treats as the shared primitives package. The edit is well-justified (closes the observed corruption that breaks `metrology/identity.py` and `review/resolution_evidence.py`) and the slice explicitly acknowledges that the larger correct fix (rendering the whole block through `render_frontmatter_block`) is recorded as Future Work due to test coupling. Acceptable, but the architecture's view of the documents/review boundary is being exercised in a way the architecture doesn't model.

### [NOTE] Architecture's example of structured review findings shows the bug being fixed

The architecture's example YAML for structured findings shows `location` unquoted:
```

```
while `summary` is quoted. This is exactly the asymmetry the slice's D9 fix addresses (model-authored free text rendered unquoted in one field, quoted in another). The example happens to be valid YAML because the path contains no `: `, but it sets the wrong precedent for implementation. The slice's fix aligns the implementation with what the architecture clearly intends (parseable YAML) but the architecture's own example reinforces the very pattern the slice is correcting.

### [NOTE] No architecture NFRs apply to document validation; no restatement needed

The architecture's performance-sensitive concerns are scoped to the pipeline executor (`asyncio.to_thread` for subprocess calls, per-step latency for the SDK warm pool). The slice does not touch these paths. The slice makes no unsupported latency/throughput claims about the validator itself (the design is structurally simple — split + `yaml.safe_load` + enum membership tests — so the absence of explicit NFRs is reasonable).

### [NOTE] Failure modes are largely enumerated but a few edge cases are implicit

The slice explicitly addresses: clean/violations/usage-error exit codes, hook behavior when `sq` cannot be launched, YAML error positions, and drift-test behavior when the `ai-project-guide` submodule is absent. The design says exit code 2 covers "unreadable path, root does not exist" but does not enumerate what other conditions trip usage error vs. violations (e.g., a path argument that is not under the root is silently skipped, but a binary file under the root is not addressed). Acceptable for a 1/5 slice, but worth surfacing for the implementation to enumerate during development.
