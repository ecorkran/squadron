---
docType: review
layer: project
reviewType: slice
slice: pipeline-executor-hardening
project: squadron
verdict: PASS
sourceDocument: project-documents/user/slices/156-slice.pipeline-executor-hardening.md
aiModel: z-ai/glm-5
status: complete
dateCreated: 20260404
dateUpdated: 20260404
findings:
  - id: F001
    severity: pass
    category: state-management
    summary: "Execution mode tracking aligns with architecture"
  - id: F002
    severity: pass
    category: schema-design
    summary: "Schema version evolution is appropriate"
  - id: F003
    severity: note
    category: error-handling
    summary: "Schema migration strategy is implicit"
  - id: F004
    severity: pass
    category: portability
    summary: "Pipeline name normalization addresses cross-platform consistency"
  - id: F005
    severity: pass
    category: architecture-boundaries
    summary: "Changes stay within defined package structure"
  - id: F006
    severity: pass
    category: execution-flow
    summary: "Resume dispatch logic correctly implements architecture intent"
  - id: F007
    severity: pass
    category: scope-alignment
    summary: "Slice scope matches stated hardening purpose"
---

# Review: slice — slice 156

**Verdict:** PASS
**Model:** z-ai/glm-5

## Findings

### [PASS] Execution mode tracking aligns with architecture

The architecture describes two execution modes under "Interaction with Conversations": SDK execution mode (slice 155) and prompt-only mode (slices 153-154). The slice correctly identifies that resume must dispatch to the appropriate runner based on the original execution mode. The proposed `ExecutionMode` enum and `RunState.execution_mode` field provide the persistence mechanism needed to make this dispatch reliable.

### [PASS] Schema version evolution is appropriate

The architecture shows `schema_version: 1` in the state file example. The slice bumps this to version 2 for the new `execution_mode` field. The reasoning is sound: v1 state files from prompt-only runs cannot exist (prompt-only mode never calls `_run_pipeline` in a way that creates a state file), so breaking v1 compatibility affects only SDK runs that could be migrated. The default `ExecutionMode.SDK` provides forward compatibility for the new field.

### [NOTE] Schema migration strategy is implicit

The slice proposes raising `SchemaVersionError` for v1 files with the message guiding users to "abandon the stale run." The architecture does not define a schema migration policy. This is a reasonable design decision, but consider whether a migration utility (v1 → v2 with assumed SDK mode) would reduce user friction for in-progress runs during upgrade.

### [PASS] Pipeline name normalization addresses cross-platform consistency

The architecture defines pipeline identification by short name for built-in pipelines and path/name for custom pipelines. Case sensitivity is not specified. The slice's normalization to lowercase at discovery, load, and CLI boundaries correctly addresses the platform-dependent behavior (HFS+ case-insensitive, Linux case-sensitive) without requiring changes to YAML definitions or user-facing names.

### [PASS] Changes stay within defined package structure

The slice modifies `src/squadron/pipeline/state.py`, `src/squadron/pipeline/loader.py`, and `src/squadron/cli/commands/run.py` — all within the architecture's defined package structure. No new files or modules are created. The changes respect the separation between state management, pipeline loading, and CLI command layers.

### [PASS] Resume dispatch logic correctly implements architecture intent

The architecture defines `--resume <run-id>` to "continue from the checkpoint or last completed step." The slice's dispatch logic (matching `ExecutionMode` enum values to call `_run_pipeline_sdk` or `_run_pipeline`) ensures that resume uses the correct execution path. The `run_id` parameter propagation allows reuse of the existing state file rather than creating a new run.

### [PASS] Slice scope matches stated hardening purpose

The slice correctly identifies what is out of scope: the compact action's non-SDK CF path, multiple paused runs, collection loop resume (slice 154), and convergence loops (160 scope). The fixes are focused on the two identified bugs without feature creep.
