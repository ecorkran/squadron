---
docType: review
layer: project
reviewType: tasks
slice: codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/129-tasks.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md
aiModel: deepseek/deepseek-v4.1-flash
status: complete
dateCreated: 20261001
dateUpdated: 20261001
reviewedSha: 40ae840b84f1cbc35acb5fe0c99efc7f20b8a449
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 24
turns: 10
promptTokens: 517206
cachedTokens: 355200
completionTokens: 34511
reasoningTokens: 31540
durationSeconds: 183.2
runId: run-20261001-p5-9c2f4175
squadronVersion: 0.17.0
findings:
  - id: F001
    severity: pass
    category: requirements-coverage
    summary: "Success criteria cross-reference"
    location: "project-documents/user/tasks/129-tasks.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md"
  - id: F002
    severity: pass
    category: nfr-coverage
    summary: "No NFR restatement requiring a load test"
    location: "project-documents/user/slices/129-slice.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md"
  - id: F003
    severity: concern
    category: type-checking
    summary: "pyright-strict handling for new SDK-importing modules is under-specified"
    location: "pyproject.toml:95"
  - id: F004
    severity: concern
    category: error-handling
    summary: "`missing_extra_hint()` must catch the resolver's raise, but the task does not say so"
    location: "src/squadron/providers/codex/provider.py"
  - id: F005
    severity: note
    category: sequencing
    summary: "Hint-source audit is scheduled before its targets exist"
    location: "project-documents/user/tasks/129-tasks.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md"
  - id: F006
    severity: note
    category: requirements-coverage
    summary: "Functional success criterion \"artifact records effort and usage\" is only covered indirectly"
    location: "src/squadron/review/review_client.py:262"
  - id: F007
    severity: note
    category: task-sizing
    summary: "Task 7 is large but cohesive"
    location: "project-documents/user/tasks/129-tasks.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md"
---

# Review: tasks — slice 129

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [PASS] Success criteria cross-reference

Every Functional, Technical, and Integration success criterion in the slice design has a corresponding task: extra install + login review smoke (Tasks 3–10, 13; PM manual step), missing-extra error text (Tasks 5, 10, 14, 20–25), browser/device-code login (Tasks 20, 23), status/logout (Tasks 21, 24, 25), unchanged non-interactive behavior (Task 23), effort/usage (Tasks 8, 9), no stale references (Task 11), real-type drift test (Task 12), default-install suite (Tasks 13, 26), doctor + models clean with/without extra (Tasks 16, 17).

### [PASS] No NFR restatement requiring a load test

The slice explicitly sets "No latency target" for runtime startup; D7 timeouts are bounded caps on hangs, not throughput/latency NFRs. No `tests/load/` task is therefore required, and none is expected. Consistent with the existing `tests/load/` suite.

### [CONCERN] pyright-strict handling for new SDK-importing modules is under-specified

`[tool.pyright]` includes all of `src` and excludes only `src/squadron/providers/codex/agent.py`. CI runs `uv run pyright` after `uv sync --dev`, and Task 3 explicitly says *not* to add `openai-codex` to `dev`, so `openai_codex` is absent in CI. The new `login.py` (Task 20: "`openai_codex` imported inside functions") will therefore trip `reportMissingImports` at strict mode. Task 13 only anticipates this for `runtime.py` ("If `pyright` reports missing-import errors in `runtime.py` … fix there") and never names `login.py`, nor does it say to use the existing `# pyright: ignore[reportMissingImports]` pattern (or a stated alternative). As written, Task 20 can be marked complete while `pyright` fails. Add explicit guidance for every new module that names `openai_codex` (login.py, and confirm runtime.py if it imports rather than only `find_spec`).

### [CONCERN] `missing_extra_hint()` must catch the resolver's raise, but the task does not say so

`resolve_codex_runtime()` raises `ProviderError` when the package is missing (Task 5), yet Task 14 specifies `CodexProvider.missing_extra_hint()` as "`None` when `resolve_codex_runtime()` succeeds, otherwise the hint from `runtime.py`". A literal reading leaves an uncaught `ProviderError` propagating out of a method both `sq doctor` (Task 16) and `sq models list` (Task 17) call to compute a *non-fatal* row/marker — the opposite of their stated "must not break the listing" behavior. The task should state that the resolver's `ProviderError` is caught and its message reused as the hint (single hint source), so the two callers stay fail-safe.

### [NOTE] Hint-source audit is scheduled before its targets exist

Task 15 ("no duplicated install string anywhere in `src`") runs before Task 16 (`doctor`) and Task 17 (`models list`) add their hint consumers; its own text hedges with "(later)". The real enforcement already recurs in Task 26 ("Technical Requirements grep from Task 11 still clean"). Consider folding Task 15's assertion into Task 26 or explicitly restating it after Task 17 so the audit runs against the completed surface.

### [NOTE] Functional success criterion "artifact records effort and usage" is only covered indirectly

Task 8 flips `applies_effort=True` and tests that `thread.run` receives `ReasoningEffort`, and Task 9 tests the message metadata keys — but no task asserts the end-to-end review artifact records effort/usage for `codex-agent` (the slice's Functional Requirement). `review_client` records `sent_effort` from `capabilities.applies_effort`, so the behavior follows, but it is left to the PM manual walkthrough (step 6). A targeted test (or an explicit note that slice 931's review_client tests cover it) would make the criterion independently verifiable.

### [NOTE] Task 7 is large but cohesive

Task 7 (Effort 4) bundles timeout, three turn-status branches, four SDK-error wraps, and ~11 tests. It maps 1:1 to the Failure Modes — Codex Turn table, so splitting may fragment the table's test-per-row contract; flagging only so the implementer budgets for it. No change required.

### Run Digest

- Response length: 5413 chars
- Response is newline-free: no
- Tool calls made: 24
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 127596
- Effort: backend default
- Turns: 10
- Tokens — prompt / cached / completion / reasoning: 517206 / 355200 / 34511 / 31540
- Duration: 183.2 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
