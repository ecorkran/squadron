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
reviewedSha: 00b531cc4493e5e1b8d8716aa019edb21eade294
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
turns: 5
promptTokens: 247324
cachedTokens: 161296
cacheWriteTokens: 86020
completionTokens: 3384
durationSeconds: 32.9
costUsd: 0.394832
costBasis: provider
runId: run-20261102-p4-037d1fcf
squadronVersion: 0.24.13
findings:
  - id: F001
    severity: concern
    category: scope-alignment
    summary: "Failed step can still change `delivered_prompt_file`, contradicting the plan entry"
    location: "project-documents/user/slices/949-slice.isolated-file-in-file-out-dispatch-steps.md#D5 — Output files"
  - id: F002
    severity: concern
    category: proportionality
    summary: "`replace_files_together` adds a two-phase mechanism that does not deliver the guarantee"
    location: "project-documents/user/slices/949-slice.isolated-file-in-file-out-dispatch-steps.md#D5 — Output files"
  - id: F003
    severity: concern
    category: scope-alignment
    summary: "`reply_from` narrowed to top-level steps without the plan entry reflecting it"
    location: "project-documents/user/slices/949-slice.isolated-file-in-file-out-dispatch-steps.md#D3 — Reply hand-off scope and lookup"
  - id: F004
    severity: concern
    category: dependencies
    summary: "Declared dependency differs from the plan entry"
    location: "project-documents/user/slices/949-slice.isolated-file-in-file-out-dispatch-steps.md:7-8"
  - id: F005
    severity: concern
    category: proportionality
    summary: "Scope breadth: several mechanisms beyond the five plan items"
    location: "project-documents/user/slices/949-slice.isolated-file-in-file-out-dispatch-steps.md#Component Structure"
  - id: F006
    severity: pass
    category: error-handling
    summary: "Failure modes enumerated for each new I/O path"
    location: "project-documents/user/slices/949-slice.isolated-file-in-file-out-dispatch-steps.md#API Contracts"
  - id: F007
    severity: pass
    category: architecture
    summary: "Layering and dependency direction"
    location: "project-documents/user/slices/949-slice.isolated-file-in-file-out-dispatch-steps.md#Component Structure"
---

# Review: slice — slice 949

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Failed step can still change `delivered_prompt_file`, contradicting the plan entry

Plan item (3) says "a failed step writes nothing and leaves existing files alone". D5 accepts a window in which `os.replace` of `reply_file` fails after `delivered_prompt_file` was already replaced. Success criterion 4 carves out the same exception. This drops part of the scope the plan assigns to this slice. Amoeba is the stated consumer, and it may read the prompt file as evidence of what the failed step sent. The design says "no rollback" because the failure is rare, but it does not say what the consumer sees when it happens. Either close the window or get the plan entry amended. Closing it could mean keeping the old prompt-file bytes in memory and restoring them on failure. Amending it could mean narrowing plan item (3) to match D5.

### [CONCERN] `replace_files_together` adds a two-phase mechanism that does not deliver the guarantee

The temp-all-then-replace-in-order helper is new shared API in `core/file_write.py`. It still leaves the partial-failure window described above. Calling the existing single-file `_replace_file` twice, with `reply_file` last, would give nearly the same guarantee. The only difference is that a temp-write failure on the second file would leave the first file already replaced. Either make the helper actually atomic, or drop it and reuse the existing function. Right now the extra mechanism costs more than it buys.

### [CONCERN] `reply_from` narrowed to top-level steps without the plan entry reflecting it

Plan item (2) says a step "names an earlier step in the same run". D3 supports only a top-level step naming an earlier top-level dispatch, and does not check nested use at load time. The reason is sound: loop, each and fan-out bodies use three different key schemes. It is still a deferral of plan scope. Nested use is documented as unsupported, but nothing validates it. A nested `reply_from` therefore fails only at run time, with a lookup error that does not say why. Add a load-time rejection for `reply_from` inside `ContainsSteps` bodies. The slice already walks `inner_steps` for strict mode, so this is cheap. Also update the plan entry to record the narrowing.

### [CONCERN] Declared dependency differs from the plan entry

Frontmatter lists 945 as a dependency, and the Dependencies section justifies it (`runs_squadron_tools`, `can_read_files`). The plan entry says "Dependencies: none". Reconcile the two. 945 is complete, so this is bookkeeping and does not block anything.

### [CONCERN] Scope breadth: several mechanisms beyond the five plan items

The plan names five capabilities. The design adds these on top:
- a new `ContainsSteps` protocol
- `EXECUTOR_STEP_KEYS`
- `results_for_step` in `models.py`
- two new `FailureKind` values
- `contained_path_error`
- the D9 prompt-only rejection

Some are justified. `known_keys` is required by the plan, and D9 prevents a silent mode divergence. Others can be trimmed or merged:
- `ContainsSteps` can be dropped if strict validation reuses the existing `inner_steps` check, since the three container types already implement it.
- Fold `contained_path_error` into the dispatch validation module rather than `utils.py`, because only dispatch uses it.
- Consider reusing an existing `FailureKind` for the `reply_format` failure.

Effort 3/5 looks optimistic for this surface area. The four-step development order does help, because it ships the `--strict` probe first.

### [PASS] Failure modes enumerated for each new I/O path

The failure table covers every new I/O path:
- prompt-file reads: non-regular files, so a FIFO cannot hang the read, plus `OSError` and invalid UTF-8
- a missing or failed upstream reply
- JSON extraction, run off the event loop
- temp-write and replace errors

Each has an explicit handling strategy and an observable signal (WARNING or ERROR log, or `failure_kind`). The Technical Requirements assert these signals in tests, which satisfies the failure-mode rule.

### [PASS] Layering and dependency direction

File and reply logic goes in a new `dispatch_io` module, which keeps the ~1000-line `actions/dispatch.py` from growing. Guard logic tests `ProviderCapabilities.can_read_files` rather than provider identity. Key lists are defined once and shared by validate and expand. `--strict` is opt-in, so existing `sq run` and `--validate` behavior is unchanged.

### Run Digest

- Response length: 5705 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 5
- Tokens — prompt / cached / cache write / completion / reasoning: 247324 / 161296 / 86020 / 3384 / not computed
- Duration: 32.9 s
- Cost: $0.39 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
