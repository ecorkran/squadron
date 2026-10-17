---
docType: review
layer: project
reviewType: code
slice: artifact-usage-stamping
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/178-slice.artifact-usage-stamping.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261017
dateUpdated: 20261017
reviewedSha: 4821f231dab48893578910ee2d036ffe0e5f62dd
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 0
diffTruncated: false
turns: 1
promptTokens: 104876
cachedTokens: 0
cacheWriteTokens: 104874
completionTokens: 4292
durationSeconds: 35.1
costUsd: 0.467095
costBasis: provider
squadronVersion: 0.23.0
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Stamp action can still raise on undecodable files, breaking its \"never fails a run\" contract"
    location: "src/squadron/events/builtin/usage_stamp.py:119-123"
  - id: F002
    severity: concern
    category: concurrency
    summary: "Synchronous file and Context Forge I/O runs inside an `async def`"
    location: "src/squadron/events/builtin/usage_stamp.py:104-123"
  - id: F003
    severity: concern
    category: design
    summary: "Param parsing and error messages are still duplicated between `dispatch_artifact` and `artifact_paths`"
    location: "src/squadron/events/builtin/dispatch_artifact.py:113-135"
  - id: F004
    severity: concern
    category: error-handling
    summary: "`UnicodeDecodeError` is handled in the stats reader but not in the stamp reader, and the shared warning text is now misleading"
    location: "src/squadron/review/frontmatter_usage.py:91"
  - id: F005
    severity: note
    category: design
    summary: "Literal strings repeated instead of defined once"
    location: "src/squadron/events/builtin/usage_stamp.py:105"
  - id: F006
    severity: note
    category: style
    summary: "`assert` used for a runtime invariant and exceptions used for control flow"
    location: "src/squadron/events/builtin/usage_stamp.py:49"
  - id: F007
    severity: note
    category: design
    summary: "Type-dispatch in `step_artifact_kind` and a weakly typed parameter"
    location: "src/squadron/pipeline/steps/dispatch.py:108-117"
  - id: F008
    severity: note
    category: correctness
    summary: "Per-stamp rounding accumulates drift"
    location: "src/squadron/review/run_cost.py:78-86"
  - id: F009
    severity: pass
    category: testing
    summary: "Failure modes are observable and tested"
    location: "tests/events/builtin/test_usage_stamp_failures.py"
  - id: F010
    severity: pass
    category: design
    summary: "Refactors keep a single source of truth"
    location: "src/squadron/review/frontmatter_usage.py"
---

# Review: code — slice 178

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Stamp action can still raise on undecodable files, breaking its "never fails a run" contract

The module docstring says every resolution, parse or write failure is logged and the action returns success. `execute` only catches `(FrontmatterError, OSError)` around `_stamp`. `stats/artifacts_report.py:_read_front` shows that `read_frontmatter` can also raise `UnicodeDecodeError`, which is a `ValueError`, not an `OSError`. A planning artifact with bad bytes would propagate out of the post-action and could fail a converging loop, which is what D1/D6 are meant to prevent. The same applies to any YAML or `ValueError` that `update_frontmatter` raises and that `FrontmatterError` does not wrap.

Catch `UnicodeDecodeError` alongside the others, or confirm that `read_frontmatter` and `update_frontmatter` wrap everything into `FrontmatterError`. Add a test with a non-UTF-8 artifact; `test_usage_stamp_failures.py` currently has no such case.

### [CONCERN] Synchronous file and Context Forge I/O runs inside an `async def`

`execute` is `async`, but it calls blocking operations directly:
- `dispatch_artifact_paths`, which goes through `cf_client.list_slices`/`list_tasks`/`get_project`.
- `Path.exists`.
- `read_frontmatter`.
- `update_frontmatter`, a read-modify-write of the artifact.

The project's async rule requires synchronous work inside an awaitable to take under 1 ms in the worst case, and a Context Forge call or disk write can exceed that. The same pre-existing pattern in `dispatch_artifact` may justify this, but the new action adds more of it on every dispatch. Move the resolve and stamp steps into `asyncio.to_thread` or `run_in_executor`, or document why the blocking is acceptable.

The read-modify-write also has no lock. That is fine while stamps run serially, but a comment should say the action assumes no concurrent writers to the same artifact (for example, parallel collection items).

### [CONCERN] Param parsing and error messages are still duplicated between `dispatch_artifact` and `artifact_paths`

The refactor extracted `dispatch_artifact_paths`, but `_dispatch_artifact_post_condition_error` still does its own slice-versus-plan branching and `int(str(param))` parse with a bespoke "not a numeric index" message. It then calls `dispatch_artifact_paths`, which repeats the branching and the parse in `_numeric_index`. The "no 'slice' param in scope" message also exists in both places. This is the duplication the new helper was meant to remove, and the two copies can drift.

Let the post-condition rely on the helper's `ValueError` and derive `scope` from it, or have the helper return the scope label along with the paths.

### [CONCERN] `UnicodeDecodeError` is handled in the stats reader but not in the stamp reader, and the shared warning text is now misleading

`_warn` still says "review artifact … frontmatter … is malformed". The module is now shared with the planning-artifact stamp and report paths, where the same helper warns about design, tasks and architecture docs. Operators will see "review artifact" for non-review files. Generalize the wording, for example "artifact".

### [NOTE] Literal strings repeated instead of defined once

These values appear as bare literals:
- `"dispatch"`, the action type.
- `"slice"` and `"plan"`, the param names, also duplicated in `artifact_paths.py` and `dispatch_artifact.py`.

The project rules ask for a single definition of values used in conditionals. Where the codebase already has constants for the action type, use them.

### [NOTE] `assert` used for a runtime invariant and exceptions used for control flow

- `assert kind is not None` is stripped under `-O`. Since `execute` already checks the same condition, pass `kind` into `_stamp_target` as a parameter instead.
- `_usage_record` raises a `ValueError` only to catch it a few lines later. A plain early return with the warning would be simpler.

### [NOTE] Type-dispatch in `step_artifact_kind` and a weakly typed parameter

`step_artifact_kind(step_type_impl: object, ...)` branches on concrete types with `isinstance`, so each new step type that declares an artifact means another branch (OCP). A protocol method such as `artifact_kind(step)` on step types would remove both the branching and the `object` typing. This is acceptable for two types but worth watching.

### [NOTE] Per-stamp rounding accumulates drift

`durationSeconds` is rounded to 0.1 and `costUsd` to 6 decimals at every write. Because each stamp reads the prior rounded total and adds to it, error accumulates over many revision rounds. The effect is small and the spend line is labelled "(floor)", so this is only informational.

### [PASS] Failure modes are observable and tested

Each identified failure mode logs at WARNING and has a test asserting the signal:
- Context Forge error.
- Missing architecture doc.
- Non-numeric param.
- Unreadable frontmatter.
- Write failure.
- Ambiguous candidates.
- Missing prior keys.
- Malformed prior total.

The tests also assert that the file is left untouched. The new `usage_stamp_helpers.py` uses real-format frontmatter fixtures, as the parsing rules require. The `_row` and `read_artifact_usage` split in `artifacts_report.py` avoids duplicate warnings.

### [PASS] Refactors keep a single source of truth

- The frontmatter key names (`KEY_*`) and the parsing of cost keys are now defined once and shared by the review and artifact readers.
- `RunCost.frontmatter_lines` is derived from `frontmatter_fields`.
- The `revise` dispatch composition drops `artifact:` explicitly, and a test covers it.

### Disposition (6092476f)

- **F001 fixed.** `UnicodeDecodeError` is caught with the other stamp failures; a non-UTF-8 artifact test asserts the WARNING and an untouched file.
- **F002 fixed.** The eligible stamp runs in `asyncio.to_thread`; `_stamp_dispatch` documents the no-concurrent-writer assumption.
- **F003 fixed.** `artifact_paths.dispatch_scope` owns the slice/plan branching and index parse; the post-condition takes its scope label from it. Messages are unchanged.
- **F004 fixed.** The warning now reads "artifact … frontmatter … is malformed".
- **F005 fixed.** `ActionType.DISPATCH`, `SLICE_PARAM` and `PLAN_PARAM` replace the literals in both actions.
- **F006 fixed.** `kind` is passed to `_stamp_target`; the non-mapping record returns early instead of raising.
- **F007 kept.** Two step types; a protocol method is not worth it yet.
- **F008 kept.** Drift is at most one rounding unit per round, and the line is a floor.

### Run Digest

- Response length: 6381 chars
- Response is newline-free: no
- Tool calls made: 0
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 1
- Tokens — prompt / cached / cache write / completion / reasoning: 104876 / 0 / 104874 / 4292 / not computed
- Duration: 35.1 s
- Cost: $0.47 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
