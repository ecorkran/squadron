---
docType: review
layer: project
reviewType: tasks
slice: metrology-data-layer-sample-capture-keystone
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/320-tasks.metrology-data-layer-sample-capture-keystone.md
aiModel: moonshotai/kimi-k2.7-code
status: complete
dateCreated: 20260718
dateUpdated: 20260718
findings:
  - id: F001
    severity: concern
    category: completeness
    summary: "Configured sample budget is registered but never enforced or tested"
    location: project-documents/user/tasks/320-tasks.metrology-data-layer-sample-capture-keystone.md
  - id: F002
    severity: pass
    category: architecture
    summary: "Package scaffold and typed exceptions map cleanly to the design"
    location: project-documents/user/tasks/320-tasks.metrology-data-layer-sample-capture-keystone.md
  - id: F003
    severity: pass
    category: architecture
    summary: "Identity, result reference, and judge-config identity implementations align with the LLD"
    location: project-documents/user/tasks/320-tasks.metrology-data-layer-sample-capture-keystone.md
  - id: F004
    severity: pass
    category: architecture
    summary: "Store design mirrors StateManager precedent"
    location: project-documents/user/tasks/320-tasks.metrology-data-layer-sample-capture-keystone.md
  - id: F005
    severity: pass
    category: correctness
    summary: "Blind-capture guarantee is implemented and tested at the data layer"
    location: project-documents/user/tasks/320-tasks.metrology-data-layer-sample-capture-keystone.md
  - id: F006
    severity: pass
    category: process
    summary: "Test tasks follow implementation tasks and commit checkpoints are distributed"
    location: project-documents/user/tasks/320-tasks.metrology-data-layer-sample-capture-keystone.md
  - id: F007
    severity: pass
    category: scope-control
    summary: "Deferred scope and judging-path regression are explicitly gated"
    location: project-documents/user/tasks/320-tasks.metrology-data-layer-sample-capture-keystone.md
  - id: F008
    severity: note
    category: traceability
    summary: "Failure-mode coverage spans T3/T5/T15 rather than T15 alone"
    location: project-documents/user/tasks/320-tasks.metrology-data-layer-sample-capture-keystone.md
---

# Review: tasks — slice 320

**Verdict:** CONCERNS
**Model:** moonshotai/kimi-k2.7-code

## Findings

### [CONCERN] Configured sample budget is registered but never enforced or tested

Description:  
T12 adds `metrology.sample_budget` to `CONFIG_KEYS`, and T14 implements the `sq metrology sample` command, but neither T10 (capture core) nor T14 reads `metrology.sample_budget` or refuses/limits captures when the budget is exhausted. The slice design explicitly states that “offered-sample volume respects the configured budget” and that this slice “stores and respects the budget as a ceiling on what the command offers.” Without a budget check and a corresponding test, that success criterion is not covered. Add budget enforcement in `record_sample`/`build_capture_payload` or the CLI surface, and assert it in T11/T15.

---

### [PASS] Package scaffold and typed exceptions map cleanly to the design

Description:  
T1 creates the `squadron.metrology` package and defines `MetrologyIdentityError`, `MetrologyTargetError`, and `MetrologyStoreError` with a shared `MetrologyError` base, matching the Failure Modes table and the “actionable messages” requirement.

---

### [PASS] Identity, result reference, and judge-config identity implementations align with the LLD

Description:  
T2/T4 implement stable project identity (git-remote primary + `.squadron.toml` fallback + explicit failure), content-addressed `JudgeResultRef`, and `JudgeConfigId`. Each has a matching test task (T3/T5), and the project-identity behavior matches the design’s “never a path” rule.

---

### [PASS] Store design mirrors StateManager precedent

Description:  
T8/T9 implement the user-level `~/.config/squadron/metrology/` store with Pydantic records at the file boundary, schema versioning with `SchemaVersionError`, atomic write-then-rename, and cross-project / judge-config filtering. This directly satisfies the store shape and query requirements.

---

### [PASS] Blind-capture guarantee is implemented and tested at the data layer

Description:  
T10 builds the capture payload from artifact + ground truth only and exposes a separate post-commit `reveal` accessor; T11 asserts the payload excludes judge score/verdict/findings. This satisfies the design’s “blindness enforced at the data layer” requirement.

---

### [PASS] Test tasks follow implementation tasks and commit checkpoints are distributed

Description:  
Every implementation task is immediately followed by its test task (T2/T3, T4/T5, T6/T7, T8/T9, T10/T11, T12/T13, T14/T15), and each task carries its own commit checkpoint rather than batching at the end.

---

### [PASS] Deferred scope and judging-path regression are explicitly gated

Description:  
The Coverage Check and T16 correctly leave out agreement/dispersion, version-keying resolution, audit records, MCP tooling, and any 300 write-path changes. T16 also gates the slice with the full test suite, static checks, manual regression, and the verification walkthrough.

---

### [NOTE] Failure-mode coverage spans T3/T5/T15 rather than T15 alone

Description:  
The Coverage Check maps the Failure Modes table to T15, but the git-remote-absent/timeout row is asserted in T3 and the malformed-target row is T5. The table is still fully covered (good), but the cross-reference should be updated to show T3 + T5 + T15 jointly cover it, or T15’s bullet list should include those rows to match its “one assertion per Failure Modes table row” success criterion.
