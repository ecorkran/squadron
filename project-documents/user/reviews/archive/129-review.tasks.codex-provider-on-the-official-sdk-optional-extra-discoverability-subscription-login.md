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
reviewedSha: 7b7f3ae3eea336acede77ae93b0e996e16f94cc6
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 38
turns: 20
promptTokens: 1334266
cachedTokens: 1075840
completionTokens: 76349
reasoningTokens: 71449
durationSeconds: 427.9
runId: run-20261001-p5-9c2f4175
squadronVersion: 0.17.0
findings:
  - id: F001
    severity: pass
    category: traceability
    summary: "Every Failure Modes row and D-decision traces to a task"
    location: "project-documents/user/tasks/129-tasks.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md"
  - id: F002
    severity: concern
    category: test-coverage
    summary: "Task 8 names the wrong tests; the test that actually breaks is not in any task"
    location: "tests/review/test_review_client.py:1546"
  - id: F003
    severity: concern
    category: integration
    summary: "New `codex provider` doctor row leaks into `sq setup` with no name-keyed-table entries"
    location: "src/squadron/cli/commands/setup_steps.py:48-140"
  - id: F004
    severity: concern
    category: documentation
    summary: "README is updated but `docs/QUICKSTART.md` still prescribes the npm install this slice removes"
    location: "docs/QUICKSTART.md:139"
  - id: F005
    severity: note
    category: dependency-management
    summary: "`uv.lock` is not regenerated after declaring the extra"
    location: "uv.lock:1032"
  - id: F006
    severity: note
    category: task-scoping
    summary: "Task 9 mixes two subsystems and a cross-module end-to-end test"
    location: "project-documents/user/tasks/129-tasks.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md:194"
  - id: F007
    severity: note
    category: test-coverage
    summary: "Task 2's \"works\" branch duplicates existing coverage"
    location: "tests/providers/codex/test_auth.py:69-75"
  - id: F008
    severity: pass
    category: nfr-coverage
    summary: "No NFR is restated, so no load test or CI gate is owed"
    location: "project-documents/user/slices/129-slice.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md"
---

# Review: tasks — slice 129

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [PASS] Every Failure Modes row and D-decision traces to a task

Cross-referencing the slice design's Failure Modes table against the tasks: package missing (T5/T10/T20/T21/T23/T24/T25), no binary anywhere (T5/T10), initialize failure (T7b), turn hang→timeout (T7a), `account()` hang (T21/T25), `logout()` hang (T21/T24), login `wait()` timeout (T20/T23), turn timeout with `shutdown()` in `finally` (T7a), `TransportClosedError` with state reset (T7b), `ServerBusyError`/`RetryLimitExceededError` (T7b), `CodexRpcError` naming `sq auth login openai-oauth` (T7b), `failed`/`interrupted` (T7a), empty/blank `final_response` (T7a), `usage` absent (T9), teardown error logged-not-raised (T6/T7b). D1→T3, D2→T5/T6/T10, D3→T19/T22, D4→T6, D5→T8, D6→T9, D7→T4, D8→T7a, D9→T14/T15/T16/T18. No criterion is unowned and no task is scope creep.

### [CONCERN] Task 8 names the wrong tests; the test that actually breaks is not in any task

Task 8 says to "Update the existing capabilities test that expects `applies_effort=False` for `openai-oauth` (`tests/providers/test_capabilities.py` / codex provider tests)". That test does not exist where named — I read `tests/providers/test_capabilities.py` and its `TestAppliesEffort` class only asserts the dataclass default and `OpenAICompatibleProvider().capabilities.applies_effort is True`; neither `tests/providers/codex/test_provider.py` nor `test_capabilities.py` mentions `applies_effort` for `openai-oauth`. The assertion that will fail is `TestEffortThreading::test_codex_artifact_has_no_effort_key` in `tests/review/test_review_client.py` (it builds `provider.capabilities = CodexProvider().capabilities`, then asserts `result.effort is None` and `"effort:" not in frontmatter`), plus `DEVLOG.md`-era expectations noted in the slice-931 follow-up. An agent following Task 8 literally will edit a file with nothing to change, then fail "Success: tests pass" in `tests/review/`. Task 8 should name `tests/review/test_review_client.py` (and state that the `TestEffortThreading` Codex case must be inverted, since the artifact now legitimately carries `effort:`).

### [CONCERN] New `codex provider` doctor row leaks into `sq setup` with no name-keyed-table entries

Task 15 registers `check_codex_provider` in `run_all_checks`, and `run_all_checks` is exactly what `sq setup` drives (`src/squadron/cli/commands/setup.py` via `build_steps`; `tests/cli/test_setup.py` patches it). `build_steps` renders a step for every result, so the new row will appear in `sq setup`/`sq setup --check-only` as a bare `codex provider` title (the `_TITLE_MAP` fallback is `result.name`), with no `DOCS_ANCHOR` link and no `_EXPLANATION` text — the four maps at `setup_steps.py:56`, `:106`, `:126`, and `:198` are all name-keyed and untouched by any task. `tests/cli/test_setup.py::test_both_command_check_names_are_registered_in_every_name_keyed_table` is deliberately scoped to the two command names, so this will not fail a gate — it will ship as a degraded setup step. Either add the entries as part of Task 15 or explicitly declare `sq setup` out of scope for this row.

### [CONCERN] README is updated but `docs/QUICKSTART.md` still prescribes the npm install this slice removes

Task 17 covers only `README.md` §"Using Codex (experimental)". But `docs/QUICKSTART.md` is the document `sq setup`'s remediation links point at (`docs/QUICKSTART.md#configure-a-provider`, asserted resolvable by `tests/cli/test_setup.py`), and it still tells users, verbatim: `npm i -g @openai/codex` followed by `codex auth login` as the way to configure `openai-oauth` (line 139), with the same command repeated in the `sq doctor` sample output (line 86). The slice's stated value is "then `sq review … --model codex-agent` works on a ChatGPT login with no API key and no npm" — a user routed through QUICKSTART by our own setup output lands on the removed path. The `codex CLI` row's `npm i -g @openai/codex` fix hint is a separate, legitimate surface (the `codex skills` gate) and should stay, so the task needs to distinguish the two rather than blanket-replace.

### [NOTE] `uv.lock` is not regenerated after declaring the extra

Task 3 changes `[project.optional-dependencies]` but no task mentions re-locking. `uv.lock` is committed and carries the `squadron-ai` package entry (line 1032). CI runs `uv sync --dev` (not `--frozen`/`--locked`), which re-locks rather than failing, so this will not break the build — but it leaves a checked-in lockfile that disagrees with `pyproject.toml` until someone runs `uv sync`, and a future `--locked` invocation would fail. Worth one line in Task 3.

### [NOTE] Task 9 mixes two subsystems and a cross-module end-to-end test

Task 9 bundles (a) the four-field `TurnResult.usage.last` mapping inside `agent.py`, (b) the `metadata["usage"]`/`["turns"]` stamping convention shared with `src/squadron/providers/openai/agent.py:689-690`, and (c) an integration test that drives `review/review_client.py` (`sent_effort`, `capture.usage`) through `CodexProvider` and asserts lines persisted by `review/persistence.py` (`format_review_markdown` emits `effort: <value>` and `RunCost` digest lines, per `persistence.py:260-261,449-453`). The implementation half is a few lines; the test half spans three modules and depends on Task 8's capability flag. It is completable as written, but splitting the integration/artifact test into its own task would give each half a success criterion the agent can evaluate without holding both in flight.

### [NOTE] Task 2's "works" branch duplicates existing coverage

Task 2's `works` path asks for "a test pinning `active_source == "OPENAI_API_KEY"` for a key-only environment (existing source label is already `OPENAI_API_KEY`)" — `TestActiveSource::test_api_key_source` in `tests/providers/codex/test_auth.py` already asserts exactly that. The task acknowledges it parenthetically; the checklist item would be sharper as "confirm the existing pin still holds" rather than implying a new test.

### [PASS] No NFR is restated, so no load test or CI gate is owed

The slice design explicitly declines a latency target ("No latency target is set: the cost is dominated by the agentic turn itself") and declines a benchmark task ("Startup duration is logged at DEBUG so a slow start is diagnosable without a benchmark task"), so there is no NFR requiring a `tests/load/` task and consequently no CI-gating task to add. The three timeouts in D7 are correctness bounds, and each has a unit test (T4, T7a, T20, T21). The remaining integration requirement ("`sq doctor` and `sq models list` run cleanly with and without the extra") is covered by T15/T16 and re-run in T26.

### Run Digest

- Response length: 8119 chars
- Response is newline-free: no
- Tool calls made: 38
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 280835
- Effort: backend default
- Turns: 20
- Tokens — prompt / cached / completion / reasoning: 1334266 / 1075840 / 76349 / 71449
- Duration: 427.9 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
