---
docType: review
layer: project
reviewType: code
slice: isolated-file-in-file-out-dispatch-steps
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/949-slice.isolated-file-in-file-out-dispatch-steps.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261102
dateUpdated: 20261102
reviewedSha: c80fff203530428c614980d08370cf43424ed3c5
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
diffTruncated: false
turns: 3
promptTokens: 244619
cachedTokens: 120442
cacheWriteTokens: 124173
completionTokens: 4426
durationSeconds: 35.3
costUsd: 0.558716
costBasis: provider
squadronVersion: 0.24.13
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: type-contract-debt
    summary: "Optional `body_steps` is discovered with `getattr` and is not part of the `StepType` protocol"
    location: "src/squadron/pipeline/loader.py#_body_steps"
  - id: F002
    severity: concern
    category: error-handling-observability
    summary: "A non-string `response` silently becomes an empty reply"
    location: "src/squadron/pipeline/actions/dispatch_io.py#apply_reply_contract"
  - id: F003
    severity: concern
    category: correctness
    summary: "A bad `reply_format` is only caught after the model call has been paid for"
    location: "src/squadron/pipeline/actions/dispatch_io.py:_reply_format"
  - id: F004
    severity: concern
    category: correctness
    summary: "Prompt resolution now runs before `set_model` in the session path"
    location: "src/squadron/pipeline/actions/dispatch.py:660-672"
  - id: F005
    severity: note
    category: security-hygiene
    summary: "Path safety is lexical only"
    location: "src/squadron/pipeline/dispatch_keys.py#path_error"
  - id: F006
    severity: note
    category: consistency-rot
    summary: "Prompt-only refusal is handled correctly and tested"
    location: "src/squadron/cli/commands/run.py:792"
  - id: F007
    severity: note
    category: other
    summary: "Tool-isolation guard and routing refactor look behavior-preserving"
    location: "src/squadron/pipeline/actions/dispatch.py#_dispatch"
  - id: F008
    severity: note
    category: test-debt
    summary: "Test coverage is strong across the new surface"
    location: "tests/pipeline/test_dispatch_file_io.py"
---

# Review: code — slice 949

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Optional `body_steps` is discovered with `getattr` and is not part of the `StepType` protocol

`_body_steps(step_impl: object, ...)` finds container bodies with `getattr(step_impl, "body_steps", None)`. `known_keys` was added to the `StepType` Protocol in `steps/protocol.py`, but `body_steps` was not. Only loop, each and fan_out implement it, and a future container that forgets it will be silently skipped. That would leave strict unknown-key checks and the nested `reply_from` rejection quietly missing for it. `getattr` on `object` also yields `Any`, which hurts the strict pyright setup. Declare an optional sub-protocol such as `ContainerStepType` and test it with `isinstance`, or add `body_steps` to the Protocol with a default `[]`. `LoopStepType.body_steps` and `EachStepType.body_steps` also just delegate to `inner_steps`, so the extra method is mostly an alias.

### [CONCERN] A non-string `response` silently becomes an empty reply

`reply = response if isinstance(response, str) else ""` is a silent fallback, which the project rules prohibit. In text mode with `reply_file`, a successful dispatch with no string `response` would write an empty file and report success. Even if that state is unlikely, fail explicitly with an error. `step_reply` already refuses an empty reply, so the writer and the reader disagree.

### [CONCERN] A bad `reply_format` is only caught after the model call has been paid for

`_reply_format` runs inside `apply_reply_contract`, after the model has already responded. A value that only resolves at run time, such as a `{param}` placeholder, reaches this point and wastes the call. `DispatchInputError` is then caught by the outer handler in `execute`, so it does fail cleanly. Validate `reply_format`, and the output paths via `path_error`, before dispatch, for example in `_resolve_prompt` or at the top of `_dispatch`. Output-path problems are currently detected after the model call too, in `_checked_output_path`.

### [CONCERN] Prompt resolution now runs before `set_model` in the session path

Moving `_resolve_prompt` ahead of `set_model` and onto a thread is intentional (D2). It changes the failure ordering for every session dispatch, not only the new file keys. It also moves existing prompt-resolution code, which may call `cf` or git, onto a worker thread. Confirm that `_resolve_prompt` touches no loop-bound or shared mutable context state. If it does, document the publication mechanism, as the concurrency rules require.

### [NOTE] Path safety is lexical only

`path_error` rejects absolute paths and `..` but does not resolve symlinks, so a symlink inside the working directory can read or write outside it. The docstring says this is deliberate because pipelines are trusted author content. However, `{param}` values can come from the CLI, so the "trusted" assumption is weaker for placeholder paths. Also, `PurePath` on POSIX does not treat `C:\x` as absolute. Consider a `resolve()` containment check at run time.

### [NOTE] Prompt-only refusal is handled correctly and tested

`PromptOnlyUnsupportedError` subclasses `ValueError`, and the preceding handler catches `ModelResolutionError`, which is a plain `Exception`, so there is no shadowing. The handler logs at WARNING and exits cleanly, and a test covers it. Other callers of `render_step_instructions` that do not go through `_render_prompt_only_step` would need the same handling, which I did not verify.

### [NOTE] Tool-isolation guard and routing refactor look behavior-preserving

The routing is equivalent to the old branching: no session or a non-SDK alias goes to the agent, otherwise to the session. `_agent_profile_name` is shared by the guard and `_dispatch_via_agent`, so the two cannot disagree on provider. The guard reads the provider capability rather than its name, and the failure is observable (WARNING plus `FailureKind.TOOL_ISOLATION`). Tests cover both routes, the provider that reads no files, and the absent-key case.

### [NOTE] Test coverage is strong across the new surface

Unit tests cover extraction, prompt assembly (fifo, permission and UTF-8 edge cases), write rollback, and strict known-keys for every step type. An end-to-end test with resume completes the coverage. Every built-in pipeline is checked against strict validation, and the warning-log assertions meet the failure-mode rules. No load-tier test was added, but the new code is file I/O off the loop, not a simulation or network path.

### Run Digest

- Response length: 5175 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 3
- Tokens — prompt / cached / cache write / completion / reasoning: 244619 / 120442 / 124173 / 4426 / not computed
- Duration: 35.3 s
- Cost: $0.56 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
