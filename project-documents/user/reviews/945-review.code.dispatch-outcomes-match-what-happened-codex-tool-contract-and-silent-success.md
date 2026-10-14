---
docType: review
layer: project
reviewType: code
slice: dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/945-slice.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success.md
aiModel: deepseek/deepseek-v4.1-flash
aiProfile: openrouter
status: complete
dateCreated: 20261014
dateUpdated: 20261014
reviewedSha: af81699f793a5715a871e14672d557499f2127e7
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 42
diffTruncated: false
turns: 20
promptTokens: 2214863
cachedTokens: 1880064
completionTokens: 90663
reasoningTokens: 86354
durationSeconds: 553.6
squadronVersion: 0.21.7
findings:
  - id: F001
    severity: pass
    category: design
    summary: "Telemetry keys centralized in one module"
    location: "src/squadron/providers/base.py:14-17"
  - id: F002
    severity: concern
    category: observability
    summary: "Codex sandbox is silently escalated to `workspace-write` with no log"
    location: "src/squadron/providers/codex/agent.py:257"
  - id: F003
    severity: concern
    category: security
    summary: "The implicit write-tool default grants unjailed `bash`"
    location: "src/squadron/tools/builtin/_shared.py:29"
  - id: F004
    severity: concern
    category: design
    summary: "Write-tool default keys on provider identity instead of a capability"
    location: "src/squadron/pipeline/actions/dispatch.py:150"
  - id: F005
    severity: concern
    category: documentation
    summary: "Docstrings in `dispatch_artifact.py` still claim every branch logs at WARNING"
    location: "src/squadron/events/builtin/dispatch_artifact.py#_resolve_paths"
  - id: F006
    severity: note
    category: error-handling
    summary: "A malformed telemetry count becomes an unexpected-traceback failure"
    location: "src/squadron/pipeline/actions/dispatch_outcome.py:31-34"
  - id: F007
    severity: note
    category: observability
    summary: "Failed steps do not render their tool counts"
    location: "src/squadron/pipeline/executor.py:144-155"
  - id: F008
    severity: note
    category: testing
    summary: "Two near-identically named new test modules"
    location: "tests/pipeline/actions/test_dispatch_outcomes.py"
---

# Review: code — slice 945

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [PASS] Telemetry keys centralized in one module

The four metadata keys (`tools_given`, `tool_calls_made`, `failed_tool_calls`, `first_tool_error`) are now defined once and referenced by every producer and consumer (`dispatch.py`, `review.py`, `review_fold.py`, `executor.py`, `turn_capture.py`, `summary_oneshot.py`, `sdk/agent.py`, `openai/agent.py`). This directly satisfies the project rule "never scatter comparison values across code" and removes the previous `_TOOL_CALLS_MADE` private duplicate in `review_fold.py`. The `dispatch_outcome.py` pure-function split (a D3 decision table isolated from the I/O-heavy dispatch action) is also the right SRP shape, and its unit tests exercise every row plus the no-telemetry case.

### [CONCERN] Codex sandbox is silently escalated to `workspace-write` with no log

`_resolve_sandbox` returns `Sandbox.workspace_write` whenever `requires_writes` is true and the profile sets no sandbox. Because `_check_sandbox_allows_writes` then sees a non-read-only sandbox, it returns early — so the *only* path that grants write access produces neither a WARNING nor an INFO record. An operator running a stock Codex profile gets a phase step that now writes into the checkout where the previous behavior was read-only, with nothing in the log saying the sandbox changed. The project convention is explicit here: "Never use silent fallback values." The `read_only` + bare-dispatch case logs a warning; the escalation case, which is the larger behavior change, logs nothing. A one-line `_log.warning`/`_log.info` naming the escalation (and the credential that would pin it) would make this observable without changing the decision the slice design already made.

### [CONCERN] The implicit write-tool default grants unjailed `bash`

`DEFAULT_WRITE_STEP_TOOLS` is `(read_file, write_file, list_files, grep, bash)` and is applied automatically to any OpenAI-compatible phase/revise step that declared no `allowed_tools` (`dispatch.py:150-151`). The module comment next to it states plainly that "`bash` runs in the working directory but is not jailed: the jail covers only the file tools." So a user who declared nothing now silently gets shell execution as part of the default grant. The stated requirement — a step that "must write files" — is satisfied by `write_file` alone. Including `bash` widens the trust boundary beyond the requirement and beyond what the operator asked for, on the one tool that the `_shared.py` comment says is not sandboxed. The `CHANGELOG` mentions a README warning, but the default itself is the thing granting the capability; `write_file` (+ the read tools) would meet D1's contract with a strictly smaller grant.

### [CONCERN] Write-tool default keys on provider identity instead of a capability

`if allowed_tools is None and requires_writes and profile.provider == ProviderType.OPENAI:` is a type-checking dispatch on the concrete provider. The codebase already has the abstraction for this — `ProviderCapabilities` (with `can_read_files`, `applies_output_budget`, `applies_effort`) and `review/review_client.py` consults it through `provider.capabilities`. A fourth OpenAI-compatible provider type would have to edit this conditional, and none of the copy-pasted guard messages get a compiler-visible reminder. This is the OCP case the review rules call out ("adding a new variant requires editing a switch/case or if-else chain"). A capability flag (e.g. `uses_squadron_tools`) or a provider-side decision would keep the policy with the provider, as the slice design's own "provider-specific knowledge stays in the provider" argument for D2 asserts.

### [CONCERN] Docstrings in `dispatch_artifact.py` still claim every branch logs at WARNING

`_resolve_paths` is documented as "the paths, or a failure message (logged at WARNING)", and `_dispatch_artifact_post_condition_error` as "Every branch fails closed and is logged at WARNING (see docstrings on the helpers it calls)". The new `except ContextForgeError` branch in `_resolve_paths` logs at ERROR, and so does the new `except ContextForgeError` in `DispatchAction.execute` (`dispatch.py:407-411`). Since the log level is the operator-facing contract here — and an operator filtering at ERROR would see a cf failure while one filtering at WARNING would see the neighbouring ValueError case — the docs and the code now disagree. Both docstrings should be updated to say "WARNING, or ERROR for a named cf failure."

### [NOTE] A malformed telemetry count becomes an unexpected-traceback failure

`_count` raises `TypeError` for a non-int count. That raise propagates out of `assess_tool_outcome` into `DispatchAction.execute`, where the only matching handler is the trailing `except Exception`, so a provider that stamps a string count produces a logged traceback rather than the one-line named failure the rest of the D3 path was built to give. Failing fast is defensible, and a test asserts the raise, but the surrounding code (`_TOOLS_SUPPRESSED_MESSAGE`, `ProviderError` handlers) has deliberately moved toward "message names the fix, no traceback" — a `fail_reason` naming the malformed key would fit that contract better than an unhandled type error.

### [NOTE] Failed steps do not render their tool counts

The `tools=N, calls=M` segment is computed inside `if result.success:` in `_log_action_result`. A step failed by D3 row 2 now returns `success=False` carrying `failed_tool_calls` and `first_tool_error` in `metadata`, but the operator's `-v` line prints only `-> FAILED: every tool call failed: …`. The metadata reaches run state, so the evidence is not lost — but the counts that make "every call failed out of three" legible at a glance are exactly the ones suppressed on the failure path, which is where they matter most.

### [NOTE] Two near-identically named new test modules

`test_dispatch_outcome.py` (the pure-function row tests) and `test_dispatch_outcomes.py` (the dispatch wiring and `requires_writes` contract tests) differ by one character. Both are new in this slice. A future reader looking for the D3 tests has a 50% chance of opening the wrong one, and a rename or move touches a name that reads as a typo of the other. `test_dispatch_outcome_rules.py` / `test_dispatch_outcome_wiring.py` would keep the module-under-test prefix that the guide's naming convention asks for while removing the collision.

### Run Digest

- Response length: 7023 chars
- Response is newline-free: no
- Tool calls made: 42
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 342910
- Effort: backend default
- Turns: 20
- Tokens — prompt / cached / completion / reasoning: 2214863 / 1880064 / 90663 / 86354
- Duration: 553.6 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8

## Response

Addressed in 92accd76 unless noted.

- **F002** fixed: `_resolve_sandbox` logs at INFO when a write step on an unpinned Codex profile gets `workspace-write`, naming the pin that refuses instead. Test asserts the record.
- **F003** kept by PM decision: `bash` stays in the default set (implement and code revises need it to run tests; the SDK producer already has Bash). The README carries a warning and the file-tools-only `allowed_tools` list; OS-level containment is #213.
- **F004** fixed: new `ProviderCapabilities.runs_squadron_tools`, set by the OpenAI-compatible provider; dispatch reads the capability, not the provider type. Wiring tests load the real providers.
- **F005** fixed: both docstrings now say WARNING, or ERROR for a Context Forge error.
- **F006** no change: a non-int count is a provider contract violation, and a traceback is the right signal for a bug in squadron itself, not a user-fixable condition.
- **F007** fixed: the failure line renders `(tools=N, calls=M, failed=F)`; success lines gain `failed=F` when nonzero.
- **F008** fixed: renamed to `test_dispatch_outcome_rules.py` and `test_dispatch_outcome_wiring.py`.
