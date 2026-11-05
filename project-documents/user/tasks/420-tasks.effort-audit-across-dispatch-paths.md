---
docType: tasks
slice: effort-audit-across-dispatch-paths
project: squadron
lld: user/slices/420-slice.effort-audit-across-dispatch-paths.md
dependencies:
- 931
- 175
- '#216'
projectState: slice 420 design complete; initiative 420 (model benchmark) planning;
  no implementation started
dateCreated: 20261105
dateUpdated: 20261105
status: in_progress
turns: 27
promptTokens: 1786060
cachedTokens: 1685486
cacheWriteTokens: 100524
completionTokens: 33127
durationSeconds: 223.2
costUsd: 0.902333
usageRounds: 3
pricedRounds: 3
usageByModel:
  claude-sonnet-5-5:
    rounds: 3
    costUsd: 0.9023336
    completionTokens: 33127
revision_number: 2
---

# Tasks: Effort Audit Across Dispatch Paths

## Context Summary
- Slice 420 makes a config's effort "what went on the wire". It fixes four dispatch paths that drop or misreport effort (compaction record, replay judge, findings-addressed judge, prompt-only `_dispatch-run`), adds an action-level `effort_sent` metadata key, and changes replay config identity to five fields: model, profile, effort sent, `tool_use`, `max_output_tokens` (D6). Where the design's Success Criteria name only model, profile and effort, D6's five fields govern.
- All decisions live in the slice design (the `lld` above): D1–D7, and the dispatch-path inventory under Architecture → Component Structure. Each task cites its decision. Read the design before starting a task.
- Prerequisites, complete on the target: slice 931 (`Effort`, `applies_effort`), slice 175 (`UsageRecord.effort` = sent), #216 (session effort). `EFFORT_SENT_KEY`, `note_effort_sent`, `effort_sent_by_profile`, `read_effort_sent`, `effort_for_session` already exist in `pipeline/usage_capture.py`.
- Branch: `420-slice.effort-audit-across-dispatch-paths`, forked from the target (`cf config get git.integration_branch`, or `main` if empty).
- Every commit: `ruff format`, `ruff check`, `pyright` (zero errors project-wide), and the tests for the touched area. Don't use `pytest -n`.
- Per-path tests reuse `capture_config` from `tests/providers/agent_config_sites.py` and assert `config.effort`; recording tests assert `UsageRecord.effort` and `metadata["effort_sent"]`.
- Load-test tier (`rules/python.md`): not applicable. The slice passes one value through existing calls and adds no simulation, network, concurrency or environment-layer code, so there is no latency, throughput or resource bound to assert.
- Next slices: 421, 422, 424–427 read effort via `action_effort_sent` and group by the D6 identity rule.

## Task 1: Branch — Effort 1
- [x] Planning documents (this task file, the slice design, `DEVLOG.md`) commit to the target, not the slice branch. Before branching, commit any of them still uncommitted on the target
- [x] Run `git status --short -- . ':!project-documents' ':!DEVLOG.md'`. If it prints anything, write a line starting `BLOCKED:` naming those paths under this task and stop
- [x] Read the target: `cf config get git.integration_branch`, or `main` if empty. Create the slice branch from it
- [x] Success: `git branch --show-current` prints the slice branch name; the status command above printed nothing

## Task 2: `stamp_effort_sent`, `action_effort_sent`, strict `read_effort_sent` (D5) — Effort 2
- [x] In `pipeline/usage_capture.py` add `stamp_effort_sent(metadata, effort)`: writes `metadata[EFFORT_SENT_KEY]` as the `Effort` value string, or `None` when `effort` is `None`. Uses the existing constant
- [x] Add one private parser from a stored value to `Effort | None`: an `Effort` or `None` passes; a string is parsed ignoring case and whitespace; anything else, or an unrecognized string, raises a clear error
- [x] Add `action_effort_sent(metadata, usage)`, the reader for stored action state:
  - [x] key present: the parsed value (`None` stays `None`)
  - [x] key absent: `usage.effort` parsed the same way when `usage` is present, else `None`
- [x] Make the existing `read_effort_sent` (in-process `usage_metadata`) use the same parser, so a present value that is neither `Effort` nor `None` raises instead of reading as `None`. Key absent still returns `None`
- [x] Tests in `tests/pipeline/test_effort_plumbing.py` (or a new `test_effort_stamp.py` beside it if that file would pass ~300 lines):
  - [x] stamp then read returns the same `Effort`; stamping `None` reads `None`
  - [x] JSON round trip of the metadata reads back as `Effort`; uppercase and padded input accepted
  - [x] key absent falls back to `usage.effort`; absent with no usage is `None`; present wins over a differing `usage.effort`
  - [x] unrecognized string raises from both readers; `read_effort_sent` raises on a non-`Effort`, non-`None` value
  - [x] gate tests: with a fake provider with `applies_effort=False`, `note_effort_sent` writes `None` and `effort_sent_by_profile` returns `None`
- [x] Success: tests pass; ruff and pyright clean; existing callers unaffected

**Commit**: `feat: add effort_sent action stamp and strict readers`

## Task 3: Stamp effort in dispatch results (D5) — Effort 3
- [ ] In `pipeline/actions/dispatch.py`, call `stamp_effort_sent` with the value passed to the usage capture (`effort_sent`) at each result built after the effort is known:
  - [ ] SDK-session path: the success metadata (beside `"profile": "sdk-session"`), the `_check_cli_error` result, and the `ProviderError` result from `session.dispatch`
  - [ ] one-shot path: the success metadata (beside `"profile": profile_name`), the `_check_cli_error` result, and the `ProviderError` result
  - [ ] the `set_model` failure result: move the `effort_sent = capture.effort_for_session(...)` line above `session.set_model`, so the effort is known when it fails
  - [ ] `_provider_failure` stays unchanged. Its callers at the sites above stamp the returned `result.metadata`, because only they hold the effort
- [ ] Not stamped: failures before resolution; the outer `except ProviderError` and `except Exception` handlers in `execute`, where the effort is a local of `_dispatch` and out of reach. Add a comment at the outer handlers saying so. D5 in the slice design already states this limit
- [ ] Tests in `tests/pipeline/actions/test_dispatch_usage.py`:
  - [ ] SDK-session dispatch: `metadata["effort_sent"]` equals the session effort (extend the existing mismatch and match tests)
  - [ ] one-shot dispatch: equals the alias effort; `None` when the alias sets none
  - [ ] one-shot and session `ProviderError` with no telemetry: `effort_sent` present, no `UsageRecord`
  - [ ] `_check_cli_error` result carries it
  - [ ] `set_model` failure: `effort_sent` present
  - [ ] failure before resolution: no `effort_sent` key
- [ ] Success: tests pass; ruff and pyright clean

## Task 4: Stamp effort in summary results (D5) — Effort 2
- [ ] In `pipeline/actions/summary.py`, call `stamp_effort_sent` at each result-metadata site that already calls `stamp` (SDK-session success, one-shot success, failure paths), with the value given to the capture
- [ ] Tests in `tests/pipeline/actions/test_summary.py` (existing effort tests live in `tests/pipeline/test_effort_plumbing.py`; reuse their setup): session summary stamp equals the session effort; one-shot equals the alias effort; failed summary with no telemetry still carries the stamp
- [ ] Success: tests pass; ruff and pyright clean

## Task 5: Stamp effort in review results (D5) — Effort 2
- [ ] In `pipeline/actions/review.py`, call `stamp_effort_sent` where the part metadata (`stamp(part.metadata, ...)`) and the final result metadata (`"profile": settings.profile_name` block) are built. The value is `result.effort` on success and `effort_sent_by_profile` on failure
- [ ] Tests in `tests/pipeline/actions/test_review_action.py` (or `test_review_outputs.py`): successful review stamp equals the alias effort; failed review stamp equals `effort_sent_by_profile`
- [ ] Success: tests pass; ruff and pyright clean

**Commit**: `fix: stamp effort sent on dispatch, summary and review results`

## Task 6: Compaction records the session's effort (D2) — Effort 2
- [ ] In `pipeline/actions/compact.py`, `execute` already tests `context.sdk_session is not None`. Pass that narrowed session into `_execute_sdk_rotate` as a typed parameter (`SDKExecutionSession`) and use it instead of `context.sdk_session` there, which needs `# type: ignore[union-attr]` today; remove those ignores
- [ ] Pass `session.effort` as `effort_sent` to `record_from_telemetry` (replacing `None`) and call `stamp_effort_sent` with the same value on the success metadata and on the `except Exception` failure result (the session effort is known before the call)
- [ ] Update the "Effort is never sent (D7)" comment: the summary turn runs on the session's effort
- [ ] Do not route through `effort_for_session` (it would warn for every compaction whose alias differs)
- [ ] Tests in `tests/pipeline/actions/test_compact.py`:
  - [ ] update every existing assertion of `effort=None` to the session's value
  - [ ] session effort `high` gives `usage.effort == "high"` and `metadata["effort_sent"] == "high"`
  - [ ] a compact alias with a different effort logs no mismatch warning
  - [ ] a `compact()` that raises returns a failed result with `effort_sent` equal to the session effort
- [ ] Success: tests pass; ruff and pyright clean

**Commit**: `fix: record session effort on compaction`

## Task 7: Replay judge sends and records effort (D3) — Effort 3
- [ ] In `metrology/replay_models.py` add optional `effort_sent: str | None = None` to `JudgeRef`
- [ ] In `replay/judge_dispatch.py`: pass `effort=resolved.effort` to `one_shot_dispatch_with_telemetry`; record `read_effort_sent(usage_metadata)` as `effort_sent` in the usage record (replacing `None`)
- [ ] Wherever `JudgeRef` is built for a judgment (grep `JudgeRef(`), fill `effort_sent` from the same value
- [ ] Tests: create `tests/replay/test_judge_dispatch.py`: captured `AgentConfig.effort` equals the judge alias's effort (`capture_config`); usage record `effort` equals it, `None` when the alias sets none; a `JudgeRef` JSON without `effort_sent` loads with `None`. In `tests/replay/test_report.py`: judgments with different `JudgeRef.effort_sent` produce separate tables
- [ ] Success: tests pass; ruff and pyright clean

## Task 8: Findings-addressed judge sends effort (D3) — Effort 3
- [ ] In `pipeline/actions/findings_addressed/judge.py` switch `_resolve_model` to `resolver.resolve_full`, returning the `ResolvedModel`; keep the `template_model` fallback and the profile override
- [ ] `judge_residue_core` (`review/addressed/judge.py`) accepts `effort: Effort | None` and passes it to `run_review_with_profile`. Update every caller of both functions
- [ ] In `review/resolution.py` (`sq review resolve`) resolve with `resolve_full` and pass the effort the same way
- [ ] Tests: pipeline gate (nearest existing findings-addressed judge test; grep `_resolve_model` under `tests`): `run_review_with_profile` receives the judge alias's effort, none when the alias sets none; the `judge:` block alias and the `template_model` fallback each send their own alias's effort. `tests/review/test_cli_review_resolve.py` or `test_resolution.py`: `sq review resolve` sends it. Update existing `_resolve_model` tests for the new return type
- [ ] Success: tests pass; ruff and pyright clean

**Commit**: `fix: send alias effort from the replay and findings-addressed judges`

## Task 9: `_dispatch-run --effort` and prompt-only render (D4) — Effort 2
- [ ] In `cli/commands/dispatch_run.py` add an optional `--effort` option typed `Effort`, same shape and help text as `summary_run.py`, and pass `effort=effort` to `one_shot_dispatch`
- [ ] In `pipeline/prompt_renderer.py` `_render_dispatch`: switch `resolver.resolve(action_model)` to `resolve_full`; append `--effort <level>` to the non-SDK command when `resolved.effort` is not `None`, omit it otherwise. Model it on `_render_summary` (near line 450)
- [ ] Tests: the existing `_dispatch-run` CLI test (grep `dispatch_run` under `tests/cli`): `--effort low` passes `Effort.LOW` to `one_shot_dispatch`, no flag passes `None`. `tests/pipeline/test_prompt_renderer.py`: non-SDK alias with effort emits `--effort low`; without effort omits it; SDK-profile alias still emits no command
- [ ] Success: tests pass; ruff and pyright clean

**Commit**: `fix: carry alias effort through _dispatch-run and prompt-only render`

## Task 10: Replay outcome and stats read `action_effort_sent` (D5) — Effort 2
- [ ] `replay/outcome.py` (around line 192): compute `effort_sent` with `action_effort_sent(metadata, usage)` from the dispatch step's action metadata, replacing `None if usage is None else usage.effort`
- [ ] `stats/producer_units.py` (around line 121): same replacement for `ProducerKey.effort`
- [ ] Tests: in `tests/replay/test_outcome.py` and `tests/stats/test_producer_units.py`, a failed dispatch with no `UsageRecord` but `effort_sent: "high"` metadata reads `"high"` (and lands in the matching `ProducerKey.effort` row); an old record with usage only still reads `usage.effort`
- [ ] Success: no remaining read of `usage.effort` for producer identity in either module; tests pass; ruff and pyright clean

**Commit**: `fix: attribute failed producer runs to the effort sent`

## Task 11: Config identity fields on `ProducerConfigRef` (D6) — Effort 2
- [ ] In `metrology/replay_models.py` add `tool_use: bool | None = None` and `max_output_tokens: int | None = None` to `ProducerConfigRef`. `None` means only "record predates this slice" for `tool_use`; for `max_output_tokens` it also means "no budget sent"
- [ ] In `cli/commands/replay_common.py` `config_ref` fill them through the alias readers, never by testing the raw field: `model_allows_tools(alias)` (absence means allow, so an alias with no `tool_use` records `True`, not `None`) and `model_max_output_tokens(alias)` (`None` = no budget)
- [ ] Tests in `tests/cli/test_replay_run.py` (or a new `test_replay_config_ref.py`): alias with `tool_use = false` gives `False`; alias with no `tool_use` gives `True`; `max_output_tokens` set and unset; old `ProducerConfigRef` JSON without the fields loads with `None`
- [ ] Success: tests pass; ruff and pyright clean

## Task 12: Replay report groups by identity (D6) — Effort 3
- [ ] `replay/report.py` is 311 lines already. First move `config_label` (and any further cohesive block needed) to a new sibling module, `replay/config_label.py` (listed in the slice design's Components changed), so the file has room. Update importers
- [ ] Add private `config_identity(config)` in `replay/report.py`, as D6 specifies, returning `(model, profile, effort_sent, tool_use, max_output_tokens)`. The moved label function takes the identity and the sorted alias names of the group
- [ ] Comment on `config_identity`: records written before this slice have `tool_use=None` and so group apart from new ones, by design; re-running the replay merges them
- [ ] Use the identity as the grouping key for report rows and Bradley-Terry contestants
- [ ] Update the `report.py` module docstring (line 4) from "alias, model, profile, effort" to the D6 rule
- [ ] Success: `report.py` ends at about 300 lines or fewer, measured with `wc -l`, with `config_identity` still in it; the new module is about 300 or fewer
- [ ] Tests in `tests/replay/test_report.py`:
  - [ ] two aliases agreeing on all five identity fields: one row listing both alias names, sorted
  - [ ] same aliases with different `effort_sent`: two rows
  - [ ] differing `tool_use` or `max_output_tokens`: two rows
  - [ ] records with `tool_use`/`max_output_tokens` absent load and group together, and group apart from a record with `tool_use` set
  - [ ] Bradley-Terry contestants follow the same grouping
  - [ ] update existing tests that assume alias-keyed rows
- [ ] Success: tests pass; ruff and pyright clean

**Commit**: `fix: record config tool_use and token budget, group replay rows by identity`

## Task 13: Enumeration test and path coverage (D7) — Effort 3
- [ ] Create `tests/providers/test_effort_inventory.py`, modelled on the AST guard in `tests/tools/test_effective_tools.py`
- [ ] Find sites by walking `ast.Call` nodes whose `func` is the name `AgentConfig` or `open_pipeline_session` (a `Name` or an `Attribute` ending in it). Do not match text: `class AgentConfig(BaseModel)` in `core/models.py`, imports, comments and docstrings must not count
- [ ] Classification table in the test: each site is `SENDS_ALIAS_EFFORT` (naming its proving test), `SENDS_SESSION_EFFORT` (naming its proving test) or `NO_ALIAS` (one-line reason). Sites at design time: `summary_oneshot.py`, `pipeline/actions/dispatch.py`, `review/review_client.py` send; `metrology/audit.py`, `providers/auth.py`, `server/routes/agents.py` (two), `pr/composer.py` have no alias; `open_pipeline_session` callers (`run_session.py`, `executor.py`) are `SENDS_SESSION_EFFORT`. Re-run the AST walk to confirm the list before writing the table
- [ ] An unclassified site fails naming file and line; a table entry with no matching site also fails
- [ ] Path coverage: for each inventory path 1–12, find the test that asserts its effort (grep first: `tests/pipeline/test_effort_plumbing.py`, `tests/pipeline/actions/test_dispatch_usage.py` and the tests added in Tasks 3–10 already cover many). List path → test name in a comment block at the top of the test file. Known already: path 12 the Task 10 tests in `tests/replay/test_outcome.py` and `tests/stats/test_producer_units.py`; path 9 `tests/cli/test_review_profile.py::test_alias_effort_reaches_the_review`; path 10 `tests/pipeline/test_effort_plumbing.py::test_summary_run_cli_passes_effort`. Add a test only for a path with none
- [ ] Success: passes; a throwaway `AgentConfig(...)` added in another module fails naming file and line (check once, then remove it); every sending path 1–12 maps to a named passing test

**Commit**: `test: enforce the effort dispatch-path inventory`

## Task 14: Full validation — Effort 2
- [ ] `ruff format`, `ruff check`, `pyright` (zero errors), full test suite
- [ ] Run the tests of every file touched in Tasks 2–13 (the design's walkthrough step 2 lists only some of them), plus `tests/providers/test_effort_inventory.py`; run walkthrough steps 3–6 where a live run is possible (pre-authorized) and record the result under the task
- [ ] Success: all pass; any remaining failure is named with its cause

## Task 15: CHANGELOG and issue — Effort 1
- [ ] Add one CHANGELOG bullet covering judge and compaction effort, `_dispatch-run --effort`, and replay row merging. State that the findings-addressed gate and `sq review resolve` now run at the judge alias's effort, so cost and latency can change, and that replays recorded before this release report as separate rows until re-run. Keep it short and user-facing
- [ ] File a GitHub issue for the findings-addressed judge's missing `UsageRecord` (design, Special Considerations). Add the number GitHub returns beside that note in the slice design. If the issue cannot be created, write `issue not filed` there instead
- [ ] Success: bullet present; issue number (or `issue not filed`) recorded in the slice design

**Commit**: `docs: add effort audit changelog entry`
