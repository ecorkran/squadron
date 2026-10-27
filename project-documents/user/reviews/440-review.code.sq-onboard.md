---
docType: review
layer: project
reviewType: code
slice: sq-onboard
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/440-slice.sq-onboard.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261027
dateUpdated: 20261027
reviewedSha: 598fcb1fbddd135ef07f919923a184f5de4b0739
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 0
diffTruncated: false
turns: 1
promptTokens: 84662
cachedTokens: 3232
cacheWriteTokens: 81428
completionTokens: 2917
durationSeconds: 25.4
costUsd: 0.361611
costBasis: provider
squadronVersion: 0.24.5
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Unvalidated cf JSON shapes can surface as raw tracebacks"
    location: "src/squadron/integrations/cf_adoption.py#parse_init_report"
  - id: F002
    severity: concern
    category: design
    summary: "Duplicated graph-file location in the staleness check"
    location: "src/squadron/onboard/__init__.py#_doc_older_than_graph"
  - id: F003
    severity: concern
    category: design
    summary: "Public wrappers that only forward to private methods"
    location: "src/squadron/integrations/context_forge.py#ContextForgeClient.run"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Every SET_SLICE now depends on a second cf call and on cf ≥ 0.19.18"
    location: "src/squadron/pipeline/actions/cf_op.py:122-128"
  - id: F005
    severity: concern
    category: naming
    summary: "Leftover \"probe\" naming and one unverified claim in user output"
    location: "src/squadron/cli/commands/onboard.py:150"
  - id: F006
    severity: note
    category: compatibility
    summary: "Removal of `sq probe` is a breaking CLI change"
    location: "src/squadron/cli/app.py:76"
  - id: F007
    severity: pass
    category: error-handling
    summary: "Timeout and failure-mode handling for the cf CLI"
    location: "src/squadron/integrations/context_forge.py#ContextForgeClient._exec"
---

# Review: code — slice 440

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Unvalidated cf JSON shapes can surface as raw tracebacks

`parse_init_report` casts `steps_raw` to `list[dict]` and calls `raw.get(...)` on each element. `is_registered` does the same with `entry.get("projectPath")`. The code already checks that `steps` and the project-list output are lists. If an element is not an object, though, it raises `AttributeError` instead of `ContextForgeError`. `cf_errors()` catches only the cf exception types, so the user would get a traceback instead of the one-line stderr message that the rest of the module promises. Check `isinstance(raw, dict)` per element and raise `ContextForgeError` otherwise. Add a test for each parser.

### [CONCERN] Duplicated graph-file location in the staleness check

`_doc_older_than_graph` rebuilds `root / GRAPH_DIR_NAME / GRAPH_FILE_NAME` even though `probe_graph` has already produced `graph["path"]`. Two places now decide where the graph lives, which breaks the DRY and "one source" rules. It also does a second `stat` that can race with file changes. Derive the graph file from the `GraphReport` that was already built. `to_json` and `render` call `relative_to(root)` on paths that are assumed to sit under `root`. Make sure that holds, or fail with a clear error if it doesn't.

### [CONCERN] Public wrappers that only forward to private methods

`run` and `run_json` only delegate to `_run` and `_run_json`. `cf_op.py` still reaches into `cf_client._run` with a `# pyright: ignore[reportPrivateUsage]`. The same operation is therefore exposed two ways, and the private-access suppression remains. Either make the underlying methods public and update the callers, or leave the privates alone and keep the new surface minimal.

### [CONCERN] Every SET_SLICE now depends on a second cf call and on cf ≥ 0.19.18

`_refuse_retroactive` calls `list_slices()` before every `set_slice`. That adds a subprocess call. With an older cf that lacks the `retroactive` field, it also turns every SET_SLICE into a hard failure, because `_slice_entry` raises when the field is missing. The error message does name the required cf version, and the failure follows the project's no-silent-fallback rule. This is a compatibility break for existing pipelines, so call it out in the CHANGELOG. If a cheaper retroactive check exists, consider using it.

### [CONCERN] Leftover "probe" naming and one unverified claim in user output

`probe_graph` and the "probe" wording survive in the `onboard` package even though `sq probe` was removed. Rename `probe_graph` to something like `read_graph_state`. The `decline` output asserts "/cf:onboard now treats it as new" without checking that cf actually recorded the opt-out. Either soften the message or confirm the state, for example by re-running detect.

### [NOTE] Removal of `sq probe` is a breaking CLI change

`sq probe` and its contract tests are deleted and replaced by `sq onboard`. `test_probe_removed.py` guards the removal. Make sure the CHANGELOG records it, since a user would notice.

### [PASS] Timeout and failure-mode handling for the cf CLI

Timeouts, missing cf, non-zero exits, bad JSON and non-object JSON each raise a distinct `ContextForgeError` that names the command. Tests cover each case, including a real slow-process timeout. `run_report` handles cf's exit-1 error envelope correctly, and `reportVersion` is checked before the envelope. The `AdoptionClient` Protocol and `FakeAdoptionClient` keep the CLI tests independent of a real cf.

### Run Digest

- Response length: 4089 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 84662 / 3232 / 81428 / 2917 / not computed
- Duration: 25.4 s
- Cost: $0.36 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
