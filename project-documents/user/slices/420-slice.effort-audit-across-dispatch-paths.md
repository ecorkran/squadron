---
docType: slice-design
slice: effort-audit-across-dispatch-paths
project: squadron
parent: project-documents/user/architecture/420-slices.model-benchmark.md
dependencies: []
interfaces: [421, 422, 424, 425, 426, 427]
dateCreated: 20261104
dateUpdated: 20261105
status: complete
---

# Slice Design: Effort Audit Across Dispatch Paths

## Overview

Effort is configured on `models.toml` aliases (slice 931) and sent by most dispatch paths. The SDK pipeline session sends it since 0.24.19 (#216). Nobody has checked every path together. This slice does that check, fixes the paths that drop or misreport effort, and makes "effort sent" the effort part of a config's identity, so a benchmark row for "sonnet at high" means effort `high` was actually sent.

The audit was done while writing this design. Its result is the inventory below. Four paths need a code change, and the replay and stats readers need a change to how they determine a config's effort.

## Value

- **Benchmark validity.** Slices 421–427 group results by config. If the effort part of a config is wrong, every effort comparison is wrong. After this slice, a config's effort is what went on the wire.
- **Fixes four real defects.** Compaction records "not sent" for a turn that ran at the session's effort. The replay judge and the findings-addressed judge drop the alias's effort. Prompt-only `_dispatch-run` drops it too.
- **Keeps the inventory true.** A test enumerates every `AgentConfig` construction site. A new dispatch path cannot ship without a decision about effort.

## Technical Scope

**Included**
- The dispatch-path inventory (below), kept current by an enumeration test.
- Fixes: compaction records the session's effort; the replay judge sends and records the alias's effort; the findings-addressed judge sends the alias's effort; `_dispatch-run` accepts `--effort` and the prompt-only renderer emits it.
- An action-level `effort_sent` metadata key, written whenever an action reaches a provider, including failure paths. A reader for it that both replay and `sq stats producers` use.
- Replay config identity becomes what went on the wire: model, profile, effort sent, and the alias's `tool_use` and `max_output_tokens`. The alias becomes a display field.
- One test per path for the effort sent, and one test of the "not sent" capability gate in each shared helper.

**Excluded**
- Paths that resolve no squadron alias: the metrology audit (`metrology.audit_model` is passed to the CLI raw), the PR composer (`--model` passed raw), daemon agents (`server/routes/agents.py`), and the auth probe (`providers/auth.py`). These paths have no alias effort to send. Giving them alias resolution would be a feature, not part of this audit.
- Prompt-only SDK steps (`/model <alias>` in the IDE). The harness dispatches those, not squadron, so squadron has nothing to send and writes no record.
- Usage recording for the findings-addressed judge. It writes no `UsageRecord` at all, so its spend is missing. That is a 175 gap, not an effort gap; see Special Considerations.
- New effort levels, or a `--effort` flag on user commands. The alias is still the only selector (931 D1).

## Dependencies

### Prerequisites
- Slice 931 (alias `effort`, `Effort` enum, `applies_effort` capability) and slice 175 (`UsageRecord.effort` = sent, D7). Both complete.
- #216 (SDK session opens at the first SDK step's effort), fixed in 0.24.19.

### Interfaces Required
- `UsageCapture` (`pipeline/usage_capture.py`): `note_effort_sent`, `read_effort_sent`, `effort_for_session`, `effort_sent_by_profile`.
- `ModelResolver.resolve_full` (`pipeline/resolver.py`), which carries `ResolvedModel.effort`.
- `SDKExecutionSession.effort` (`pipeline/sdk_session.py`), fixed for the session's life.
- The shared capture harness `tests/providers/agent_config_sites.py`, and the AST enumeration pattern in `tests/tools/test_effective_tools.py` (SC1a).

## Architecture

### Component Structure

**Dispatch-path inventory.** "Sends" means the alias's effort reaches the provider request. "Records" means the record that path writes carries the effort sent.

| # | Path | Entry | Sends | Records | Action |
|---|------|-------|-------|---------|--------|
| 1 | Pipeline dispatch on SDK session | `DispatchAction` → `session.dispatch` | session effort (#216) | yes, via `effort_for_session` | none |
| 2 | Pipeline summary on SDK session | `summary._execute_summary` → session | session effort | yes | none |
| 3 | Pipeline compact on SDK session | `CompactAction` → `session.compact` → `capture_summary` on the live client | **session effort** | **no: hard-coded `None`** | fix (D2) |
| 4 | Pipeline dispatch, one-shot | `DispatchAction._one_shot` → `one_shot_dispatch_with_telemetry(effort=resolved.effort)` | yes | yes, via `note_effort_sent` | none |
| 5 | Pipeline summary, one-shot | `capture_summary_via_profile_with_telemetry(effort=...)` | yes | yes | none |
| 6 | Pipeline review action | `run_review_with_profile(effort=...)` | yes | yes; failure uses `effort_sent_by_profile` | none |
| 7 | Findings-addressed judge (pipeline gate and `sq review resolve`) | `findings_addressed/judge._resolve_model` → `resolver.resolve` → `run_review_with_profile` | **no: `resolve` drops effort** | no record written (see Excluded) | fix send (D3) |
| 8 | Replay judge (`sq replay judge`) | `replay/judge_dispatch.py` → `one_shot_dispatch_with_telemetry` | **no: effort not passed** | **no: hard-coded `None`** | fix both (D3) |
| 9 | `sq review` CLI | `cli/commands/review.py` → `model_effort(alias)` → `run_review_with_profile` | yes | yes, review frontmatter `effort` | none |
| 10 | Prompt-only `_summary-run` | renderer emits `--effort` | yes | no record (harness-run) | none |
| 11 | Prompt-only `_dispatch-run` | renderer emits `--model <id>` with no effort | **no** | no record (harness-run) | fix send (D4) |
| 12 | Replay producer run | `sq run` subprocess (paths 1–6); `replay/outcome.py` reads effort from the dispatch's `UsageRecord` | per paths 1–6 | **no record when the call returned no telemetry: read as "not sent"** | fix (D5) |
| 13 | Metrology audit | `metrology/audit.py` | no alias | no | out of scope |
| 14 | PR composer | `pr/composer.py` | no alias | no | out of scope |
| 15 | Daemon agents | `server/routes/agents.py` | no alias | no | out of scope |
| 16 | Auth probe | `providers/auth.py` | no LLM work | n/a | out of scope |
| 17 | Prompt-only SDK steps | `/model <alias>` in the IDE | not squadron's dispatch | n/a | out of scope |

**Providers.** All three providers set `applies_effort=True`, and each maps effort onto its wire format: SDK `effort` option, or `thinking: disabled` for `none` (`sdk_effort_options`); Codex per-turn `ReasoningEffort` (`CodexAgent._turn_options`); OpenAI-compatible top-level `reasoning_effort` on every turn. No current provider is a "cannot send" case. The capability-gated recording (`note_effort_sent`, `effort_sent_by_profile`) stays, so a future provider without effort support records "not sent".

**Components changed**
- `pipeline/actions/compact.py`: record the session's effort.
- `replay/judge_dispatch.py`: pass `resolved.effort` and record the effort read back.
- `pipeline/actions/findings_addressed/judge.py`: resolve with `resolve_full` and pass its effort.
- `cli/commands/dispatch_run.py` and `pipeline/prompt_renderer.py`: `--effort`.
- `pipeline/usage_capture.py`: `stamp_effort_sent` and `action_effort_sent` (D5).
- `pipeline/actions/dispatch.py`, `summary.py`, `review.py`, `compact.py`: call `stamp_effort_sent` on success and failure paths.
- `replay/outcome.py`, `stats/producer_units.py`: read the effort with `action_effort_sent`.
- `replay/report.py`: config identity without the alias (D6).
- `replay/config_label.py`: the config identity and label code moved out of `report.py`, which is over its line budget. `replay/pair_tally.py` takes the judgment-to-comparison tally block for the same reason.
- `metrology/replay_models.py`, `cli/commands/replay_common.py`: optional `JudgeRef.effort_sent` (D3); optional `ProducerConfigRef.tool_use` and `max_output_tokens`, filled by `config_ref` (D6).

### Data Flow

```
alias (models.toml effort)
  └─ ModelResolver.resolve_full → ResolvedModel.effort
       ├─ one-shot: AgentConfig.effort → provider wire; note_effort_sent(capability) → effort sent
       └─ SDK session: session.effort (first SDK step) → effort_for_session → effort sent
            (compact's summary turn runs on this session too)
effort sent
  ├─ UsageRecord.effort (spend record, 175 D7; only when telemetry exists)
  └─ ActionResult.metadata["effort_sent"] (identity; always, once a provider was reached)
       └─ action_effort_sent → replay ProducerConfigRef.effort_sent, stats ProducerKey.effort
```

### State Management

There is no new store record type. Run state (`ActionResult.metadata`) gets one key, `effort_sent`. A value is an effort level, and `null` means not sent. An absent key means the run predates this slice, or the action failed before its model was resolved (D5). `ProducerReplay.config.effort_sent` keeps its existing shape. The new optional fields on `JudgeRef` and `ProducerConfigRef` default to `None`, so no migration is needed.

## Technical Decisions

### D1 — "Not sent" is `null`, not a new marker
Status: decided
- Effort sent is recorded as the `Effort` value, or `null` when nothing went on the wire. That covers an alias with no effort, a provider that does not apply effort, and a path with no alias. All three are the same thing on the wire: the backend default.
- This is what 175 D7 and 931 already do, so existing records keep their meaning and no migration is needed. Display text stays `describe_effort` ("backend default").
- Rejected: a separate `"not_sent"` string or a reason field. Identity only needs what was sent. Why nothing was sent is reported once at WARNING where it happens (the existing `effort_for_session` mismatch log), not stored on every record.

### D2 — Compaction records the session's effort
Status: decided
- `SDKExecutionSession.compact` captures the summary with a turn on the live client, which was opened with `session.effort`. The current record says `None`, which is a stand-in. `CompactAction` passes `context.sdk_session.effort` as `effort_sent`.
- The compact model is named by alias, but that alias's own effort cannot apply (the session's is fixed, #216). The record takes the session's value directly. A compact alias that configures an effort different from the session's logs the #216 mismatch warning once (`UsageCapture.note_session_mismatch`, as a summary step does); an alias that sets none has nothing to drop and says nothing. Added after the code review (F006).

### D3 — Both judges send the alias's effort
Status: decided
- Replay judge: `one_shot_judge_dispatcher` already calls `resolve_full`. It passes `effort=resolved.effort` and records `read_effort_sent(usage_metadata)`, as `DispatchAction` does. `JudgeRef` gains an optional `effort_sent` (default `None`, so old judgments load unchanged). The report already builds one table per distinct `JudgeRef`, so judgments at different efforts, including those made before this slice, are never mixed.
- Findings-addressed judge: `_resolve_model` switches from `resolve` to `resolve_full` and returns the `ResolvedModel`. `judge_residue_core` accepts an `effort` and passes it to `run_review_with_profile`. `review/resolution.py` (`sq review resolve`) resolves the same way, so both entry points send it.

### D4 — `_dispatch-run` takes `--effort`
Status: decided
- Same shape as `_summary-run` (931 D11): an optional `--effort` option, typed `Effort`, passed to `one_shot_dispatch`. `_render_dispatch` switches to `resolve_full` and appends `--effort <level>` when the alias sets one. The command carries the resolved model id, not the alias, so effort has to be passed explicitly.

### D5 — Effort sent is stamped on the action, not only on the usage record
Status: decided
- `UsageCapture._build` returns no `UsageRecord` when a call reports no turns, tokens or cost, for example when it fails before any response. Replay and `sq stats producers` read effort from that record, so a failed run is read as "not sent" and lands in a different config row. That is a stand-in.
- `stamp_effort_sent(metadata, effort)` writes `metadata["effort_sent"]` on every action result built after the model is resolved, success or failure, next to the existing `model`/`profile` fields. That includes the `set_model` failure. The `except Exception` branch in `DispatchAction.execute` is not stamped: the effort is local to `_dispatch` there. The value is the one passed to the capture, so the key and `UsageRecord.effort` cannot disagree.
- Some failed runs carry no stamp: the `sq run` subprocess died with no run state, the action was cancelled, or resolution itself failed. Nothing was sent in those runs, and replay already marks each with a failure class (`NO_RUN_STATE`, or "no phase step ran"). They are harness or config failures, counted by that class, not by effort.
- `action_effort_sent(metadata, usage)` is the one reader. If the key is present, it returns that value. If the key is absent, it returns `usage.effort`: under 175 D7 that field already meant "sent", so this rule only reads old records and never substitutes an alias value. With neither, it returns `None`.
- Run state is persisted as JSON, so a stored value is a string. The reader parses it into `Effort`, ignoring case and whitespace, and raises on an unrecognized value rather than reading it as `None`.
- Rejected: building a `UsageRecord` with no spend. That changes 175's priced and unpriced tallies.

### D6 — Config identity is what went on the wire; the alias is display
Status: decided
- `sq stats producers` already keys on `ProducerKey(model, profile, effort, reviewer)` with no alias. Replay does not: `config_label` puts the alias name first, so `opus-high` and `opus-xhigh` aliases that sent the same effort (for example under a session whose effort was fixed by an earlier step) become two rows.
- An alias also sets `tool_use` and `max_output_tokens`, and both change what is sent. `config_ref` copies them onto `ProducerConfigRef` as two optional fields (default `None`, so old records load unchanged), and they are part of the identity.
- A private `config_identity` in `replay/report.py` returns `(model, profile, effort_sent, tool_use, max_output_tokens)`. It is the grouping key for rows and Bradley-Terry contestants. The label shows the identity plus the alias names seen in that group, sorted. `ProducerConfigRef` still stores the alias for provenance.
- This narrows the architecture's "config (alias, model, profile, effort sent)" to what the slice plan's success criterion requires. The architecture's own rule ("two rows only when the effort really differed on the wire") already implies it.
- D6 covers producer configs only. A judge's identity is its `JudgeRef` (D3), alias included: a judge table states which judge produced it, and two judge aliases are never pooled.

### D7 — The inventory is enforced by an enumeration test
Status: decided
- A test parses `src/squadron` for `AgentConfig(` constructions and `open_pipeline_session` calls, and checks each site against a classification table in the test. Each site is either `SENDS_ALIAS_EFFORT` (with the test that proves it) or `NO_ALIAS` (with a one-line reason). An unclassified site fails the test with its file and line. This follows the SC1a guard in `tests/tools/test_effective_tools.py`.
- The table lives in the test, not in runtime code: it is a contract check, not behavior.

### Patterns and Conventions
- Per-path tests reuse `capture_config` (`tests/providers/agent_config_sites.py`) and assert `config.effort`. Recording tests assert `UsageRecord.effort` and `metadata["effort_sent"]`.
- The metadata key is a constant (`EFFORT_SENT_KEY`, already defined in `usage_capture.py` for `usage_metadata`), not a repeated string.

## Integration Points

### Provides to Other Slices
- `action_effort_sent` and `metadata["effort_sent"]`. 424 reads the producer's effort from these, and 425's report groups by them.
- The identity rule: a config is what went on the wire (D6), not the alias name. It supersedes the architecture's "(alias, model, profile, effort sent)" for grouping. Later slices apply the rule to their own record types; this slice ships no shared identity type.
- The guarantee that every alias-resolving dispatch path, including the grading review and the judge, sends and records effort.

### Consumes from Other Slices
- 931's `Effort`, `applies_effort` and the provider wire mappings; 175's `UsageCapture`; #216's session effort. None of them change.

## Success Criteria

### Functional Requirements
- The inventory table in this design matches the code. The enumeration test (D7) fails on an unclassified `AgentConfig` site.
- Compaction on an SDK session opened with effort `high` records `effort: "high"` in its usage record and `effort_sent: "high"` in its action metadata.
- The replay judge sends the judge alias's effort (`AgentConfig.effort`) and records it.
- The findings-addressed judge sends its alias's effort from both the pipeline gate and `sq review resolve`.
- `sq _dispatch-run --effort low` sends `low`. The prompt-only renderer emits `--effort` for a non-SDK dispatch step whose alias sets effort, and omits it otherwise.
- A dispatch that fails before any telemetry still carries `effort_sent` in its action metadata, and replay and `sq stats producers` attribute it to the config that sent that effort.
- Two replays whose aliases differ but which sent the same model, profile, effort, `tool_use` and `max_output_tokens` fall into one report row (D6). Two replays that differ in any of the five are two rows.

### Technical Requirements
- One test per sending path (1–12) asserts the effort sent. The capability gate is tested once in each of `note_effort_sent` and `effort_sent_by_profile`, with a fake provider with `applies_effort=False`, asserting `null`.
- Existing tests that assert compaction's `effort=None` are updated to the session's value.
- `ruff format`, `ruff check`, `pyright` with zero errors, and the full test suite pass.
- CHANGELOG: one bullet covering the user-visible fixes (judge and compaction effort, `_dispatch-run`, replay row merging). It says the findings-addressed gate and `sq review resolve` now run at the judge alias's effort, so their cost and latency can change.

### Integration Requirements
- 421–427 can read a config's effort from `action_effort_sent` and group by the D6 rule, with no further effort work.

### Verification Walkthrough

Run on 2026-11-05 against the slice branch. Commands and results below are what actually happened.

1. **Inventory guard.**
   ```bash
   uv run pytest tests/providers/test_effort_inventory.py -q
   ```
   `8 passed`. Adding a throwaway `AgentConfig(...)` to `src/squadron/pr/body.py` and rerunning failed with `src/squadron/pr/body.py:277 calls AgentConfig(...) but is not in _SITES in test_effort_inventory.py.` The throwaway was removed.

2. **Per-path effort tests.**
   ```bash
   uv run pytest tests/pipeline/test_effort_plumbing.py tests/pipeline/actions/test_compact.py \
     tests/replay/test_judge_dispatch.py tests/pipeline/test_prompt_renderer.py -q
   ```
   `106 passed`. The full suite (`FORCE_COLOR=1 uv run pytest tests -q`) gave `8839 passed, 5 skipped`. `PATH_TESTS` in the inventory test maps paths 1–12 to named tests and checks each exists.

3. **Prompt-only dispatch carries effort.** A one-step pipeline (`dispatch: {model: glm-flash-low, ...}`, an openrouter alias with `effort = "low"`):
   ```bash
   sq run effort-walkthrough.yaml demo --prompt-only
   ```
   The emitted command was `sq _dispatch-run --prompt-file {tmp_path} --model z-ai/glm-5.3-flash --profile openrouter --effort low --param topic=demo ...`. The same pipeline with `gpt54-mini` (no effort) emitted the command with no `--effort`.

4. **Compaction record.** A pipeline of one dispatch then `compact: {}`, with the dispatch on `sonnet-high` (SDK, `effort = "high"`):
   ```bash
   sq run effort-compact.yaml demo
   jq -c '[.. | objects | select(has("effort_sent")) | {effort_sent, usage_effort: .usage.effort}]' \
     ~/.config/squadron/runs/<run-id>.json
   ```
   Result: `[{"effort_sent":"high","usage_effort":"high"},{"effort_sent":"high","usage_effort":"high"}]`, the dispatch and the compaction. Before this slice the compaction's `usage.effort` was `null`. Caveat: the first attempt used `haiku-xhigh`, which failed because the installed Claude Code (2.1.311) does not know `claude-haiku-5-5`. That failure still showed D5: `[{"effort_sent":"xhigh","usage":null}]`, the effort stamped on a result with no usage record.

5. **Replay rows follow what was sent.** Replays of slice 176's task breakdown under `glm-flash` and `glm-flash-low` (same model and profile; the first sends no effort, the second `low`):
   ```bash
   sq replay run --phase tasks --slice 176 --config glm-flash --config glm-flash-low \
     --reviewer glm-flash --max-revisions 1 --yes
   sq replay report
   ```
   The report shows two rows: `glm-flash (z-ai/glm-5.3-flash, openrouter, effort none, max 128000 output tokens)` and `glm-flash-low (z-ai/glm-5.3-flash, openrouter, effort low)`. The `glm-flash` alias also sets `max_output_tokens`, which the identity now includes. Merging two aliases with identical identity into one row is not run live (it needs a second alias defined in the user's alias file); `test_aliases_that_sent_the_same_config_are_one_row_naming_both` covers it. A replay of slice 167 was skipped by `sq replay run` because its start commit declares submodules, which replay does not support.

6. **Judge effort.**
   ```bash
   sq replay judge --phase tasks --slice 176 --judge glm-flash-low --yes
   ```
   `3 pair(s) judged`. The judgment record's judge reads `{"alias":"glm-flash-low",...,"effort_sent":"low"}` and its usage records read `effort: "low"` (previously `null`).

## Implementation Notes

### Development Approach
1. `stamp_effort_sent`, `action_effort_sent` and their tests (D5). Wire them into dispatch, summary, review and compact, on success and failure paths.
2. Compaction fix (D2), with its test updated.
3. Replay judge and findings-addressed judge (D3).
4. `_dispatch-run --effort` and the renderer (D4).
5. Switch replay outcome and producer units to `action_effort_sent`; `config_identity` in the replay report (D6).
6. Enumeration test (D7) with the classification table.

Effort: 2/5.

### Special Considerations
- **Findings-addressed judge spend is unrecorded.** Path 7 writes no `UsageRecord`, so its spend is missing from run totals and from `pipeline.max_cost_usd`. That is a defect in 175's coverage, outside this slice's effort scope. Filed as #294 rather than fixed here.
- **Session effort mismatch stays a warning.** A step whose alias asks for a different effort than the open session still runs at the session's effort (#216). This slice records that truthfully. It does not reopen the session, because that would drop the conversation.
