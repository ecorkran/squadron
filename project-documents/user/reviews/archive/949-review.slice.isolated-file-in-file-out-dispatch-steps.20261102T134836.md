---
docType: review
layer: project
reviewType: slice
slice: isolated-file-in-file-out-dispatch-steps
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/949-slice.isolated-file-in-file-out-dispatch-steps.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261102
dateUpdated: 20261102
reviewedSha: d98cb8ba0246928d288340987115c023ca397c65
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
turns: 6
promptTokens: 321875
cachedTokens: 233886
cacheWriteTokens: 87979
completionTokens: 4163
durationSeconds: 42.8
costUsd: 0.417725
costBasis: provider
runId: run-20261102-p4-037d1fcf
squadronVersion: 0.24.13
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "\"Written together\" overclaims atomicity for the two output files"
    location: "project-documents/user/slices/949-slice.isolated-file-in-file-out-dispatch-steps.md#D5 — Output files"
  - id: F002
    severity: concern
    category: scope
    summary: "Prompt-only rejection of `allowed_tools: []` goes past the plan and changes existing behavior"
    location: "project-documents/user/slices/949-slice.isolated-file-in-file-out-dispatch-steps.md#D9 — Prompt-only mode"
  - id: F003
    severity: concern
    category: proportionality
    summary: "Design is heavier than the plan requires in several places"
    location: "project-documents/user/slices/949-slice.isolated-file-in-file-out-dispatch-steps.md#Architecture"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Input and output file I/O failure modes are only partly enumerated"
    location: "project-documents/user/slices/949-slice.isolated-file-in-file-out-dispatch-steps.md#D2 — Prompt assembly"
  - id: F005
    severity: note
    category: dependencies
    summary: "Frontmatter lists no dependencies, but the body consumes slice 945"
    location: "project-documents/user/slices/949-slice.isolated-file-in-file-out-dispatch-steps.md:6"
  - id: F006
    severity: pass
    category: alignment
    summary: "Plan entry items (1)–(5) are all assigned and mapped to decisions"
    location: "project-documents/user/slices/949-slice.isolated-file-in-file-out-dispatch-steps.md#Technical Scope"
  - id: F007
    severity: pass
    category: architecture
    summary: "Layering and dependency direction are sound"
    location: "project-documents/user/slices/949-slice.isolated-file-in-file-out-dispatch-steps.md#Component Structure"
---

# Review: slice — slice 949

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] "Written together" overclaims atomicity for the two output files

D5 writes both temp files first, then replaces each target in order, with `reply_file` last. The failure table says an output write error leaves "targets intact", and criterion 4 says a failed step leaves both files "byte-identical". That holds only when the temp writes fail. If the second replace fails after the first has succeeded, `delivered_prompt_file` is new and `reply_file` is old. The plan requires that a failed step "writes nothing and leaves existing files alone". Either state this residual window as accepted (replace failures after successful temp writes are rare) and narrow the table and criterion wording, or add rollback. The first costs less, and the design should pick one. It should also say what a replace failure logs (level, path), because the step is then reported as failed while one file has changed.

### [CONCERN] Prompt-only rejection of `allowed_tools: []` goes past the plan and changes existing behavior

D9 makes `_render_dispatch` raise for `allowed_tools: []` as well as the five new keys. The plan entry keeps non-strict behavior unchanged and puts the run-time meaning change in `sq run`. This breaks any existing pipeline that sets `allowed_tools: []` and is run with `--prompt-only` or as a slash command. The risk section covers only `sq run`, and the CHANGELOG requirement mentions only SDK and Codex steps. Rejecting the five new keys is reasonable. They cannot work in that mode, and an unknown-key silent drop would be worse. For `allowed_tools: []`, either cut it from D9 and document that prompt-only cannot enforce it, or add this case to the Risk Assessment and CHANGELOG. Given "resist complexity", cutting it is the lighter choice.

### [CONCERN] Design is heavier than the plan requires in several places

Effort is rated 3/5, but several mechanisms go beyond the plan items and could be cut or deferred:
- The `ContainsSteps` protocol plus `walk_steps` yielding `(step, nested)`. This exists partly to flag nested `reply_from` and partly for a future `classification.py` use that the slice says it does not need (D8, last bullet; Provides section). A direct `inner_steps` call in `unknown_key_errors` would meet the requirement.
- `EXECUTOR_STEP_KEYS` as a separate constant merged by the walker. This is fine, but it is one more layer than adding the two keys to each set.
- Symlink-following run-time containment on top of load-time `..` and absolute-path checks. The doc itself says pipelines are trusted author content, "guards against mistakes, not against an attacker". The plan does not ask for containment.
- The `feedback` plus `prompt_files`/`reply_from` validation error, and the nested-`reply_from` rejection. Both handle cases the Amoeba pipeline does not have.
Name which of these stay. The first and third are the best candidates to defer.

### [CONCERN] Input and output file I/O failure modes are only partly enumerated

Missing, outside-cwd and non-UTF-8 files are handled. For the new file reads the design does not say what happens with:
- a path that is a directory, a FIFO or a device (a read can hang or raise `IsADirectoryError`)
- a very large file that produces an oversized prompt
- permission errors
These should map to `DispatchInputError`, since the "reads in `to_thread`" step has no timeout. Name the exceptions caught (`OSError` and `UnicodeDecodeError`), require a regular file, and decide whether a size limit is wanted or explicitly not. The Technical Requirements test list also never asserts that each failure produces its WARNING log or `failure_kind` metadata. The project rule requires at least one test asserting the observable signal. Add that to the test list.

### [NOTE] Frontmatter lists no dependencies, but the body consumes slice 945

`dependencies: []` and "Prerequisites: None" conflict with "Consumes from Other Slices" naming slice 945's `can_read_files` and `runs_squadron_tools`. If 945 is already merged, say so in the Prerequisites section. If it isn't, the claim "None" is wrong.

### [PASS] Plan entry items (1)–(5) are all assigned and mapped to decisions

- File content in the prompt maps to D1/D2.
- The earlier reply hand-off with JSON extraction maps to D3/D4.
- Reply and delivered-prompt files with fail-writes-nothing map to D5.
- The no-tools guard maps to D6.
- `--validate --strict` with a per-type known-keys list shared by `validate` and `expand` maps to D7/D8.

Plain `--validate` and `sq run` stay unchanged, as the plan requires. The decision to limit the guard to dispatch steps is stated in Excluded and carried into the docs and CHANGELOG requirements. This is consistent with the plan and the maintenance architecture's scope.

### [PASS] Layering and dependency direction are sound

The guard tests the provider capability (`can_read_files`), not provider identity. A single helper, `_agent_profile_name`, is shared by the guard and the call path. Key constants are defined once. The new logic sits in `dispatch_io.py`, which keeps the roughly 1000-line `actions/dispatch.py` from growing further. The risk of the behavior change is acknowledged, and Criterion 8 validates every built-in pipeline under `--strict`.

### Run Digest

- Response length: 6544 chars
- Response is newline-free: no
- Tool calls made: 5
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 6
- Tokens — prompt / cached / cache write / completion / reasoning: 321875 / 233886 / 87979 / 4163 / not computed
- Duration: 42.8 s
- Cost: $0.42 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
