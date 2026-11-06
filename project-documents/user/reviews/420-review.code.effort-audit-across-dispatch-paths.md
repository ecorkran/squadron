---
docType: review
layer: project
reviewType: code
slice: effort-audit-across-dispatch-paths
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/420-slice.effort-audit-across-dispatch-paths.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261105
dateUpdated: 20261105
reviewedSha: b9965721c4743a41e3ef1dc6371324608ea61704
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 39
diffTruncated: false
effort: xhigh
turns: 40
promptTokens: 2430467
cachedTokens: 2220103
cacheWriteTokens: 210336
completionTokens: 68624
durationSeconds: 301.3
costUsd: 0.498189
costBasis: provider
squadronVersion: 0.24.22
categoriesNormalized: true
findings:
  - id: F001
    severity: pass
    category: other
    summary: "New effort imports and annotations resolve"
    location: "src/squadron/pipeline/actions/summary.py:8"
  - id: F002
    severity: pass
    category: correctness
    summary: "Compact's summary turn does run at the session's effort"
    location: "src/squadron/pipeline/actions/compact.py:83"
  - id: F003
    severity: pass
    category: correctness
    summary: "Review result effort is gated by the profile's capability"
    location: "src/squadron/review/review_client.py:331"
  - id: F004
    severity: concern
    category: correctness
    summary: "Config label renders \"not sent\" and `Effort.none` identically"
    location: "src/squadron/replay/config_label.py:33"
  - id: F005
    severity: concern
    category: correctness
    summary: "Replay identity records the alias's output budget even where it is not sent"
    location: "src/squadron/cli/commands/replay_common.py:55-56"
  - id: F006
    severity: concern
    category: error-handling-observability
    summary: "Compact silently drops the summary alias's effort"
    location: "src/squadron/pipeline/actions/compact.py:80"
  - id: F007
    severity: concern
    category: test-debt
    summary: "The judge effort test mocks away the code it should check"
    location: "tests/review/test_cli_review_resolve.py::test_the_judge_alias_effort_reaches_the_judge"
  - id: F008
    severity: note
    category: type-contract-debt
    summary: "Defaulted `effort: Effort | None = None` can silently drop effort"
    location: "src/squadron/review/resolution.py:227"
  - id: F009
    severity: note
    category: consistency-rot
    summary: "A failed `set_model` is stamped with an effort that was never sent"
    location: "src/squadron/pipeline/actions/dispatch.py:683"
  - id: F010
    severity: note
    category: consistency-rot
    summary: "A second config label ignores the new identity fields"
    location: "src/squadron/cli/replay_views.py:18"
  - id: F011
    severity: note
    category: other
    summary: "Walrus inside a dict comprehension"
    location: "src/squadron/replay/report.py:75"
  - id: F012
    severity: note
    category: error-handling-observability
    summary: "A malformed stored effort can abort a whole read"
    location: "src/squadron/pipeline/usage_capture.py:76"
  - id: F013
    severity: note
    category: test-debt
    summary: "The effort inventory's classifications and path map are not checked"
    location: "tests/providers/test_effort_inventory.py"
---

# Review: code — slice 420

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [PASS] New effort imports and annotations resolve

`summary.py` imports `Effort`. `compact.py` has `from __future__ import annotations`, so its `SDKExecutionSession` annotation under `TYPE_CHECKING` is safe. `producer_units.py` imports `UsageRecord` (line 13). `dispatch.py` already uses `Effort` in signatures. I found no import-time NameError.

### [PASS] Compact's summary turn does run at the session's effort

`SDKExecutionSession.compact()` calls `capture_summary`, which calls `dispatch` on the live client. That client was built with `session.effort` (sdk_session.py:178, 565). Stamping `session.effort` is accurate.

### [PASS] Review result effort is gated by the profile's capability

`sent_effort = effort if provider.capabilities.applies_effort else None`. The new `stamp_effort_sent(part.metadata, result.effort)` never claims an effort that was not sent.

### [CONCERN] Config label renders "not sent" and `Effort.none` identically

`f"effort {identity.effort_sent or 'none'}"` maps both `None` (nothing sent) and `"none"` (`Effort.none`, a distinct member at core/models.py:52) to `effort none`. The identities differ, so the report keeps two rows with the same text. This happens when one alias is recorded at both values, for example with a session effort that differs between runs, or with pre-slice records. The line predates this slice, but the slice rewrote the function and kept it. Render `None` distinctly, for example `effort not sent`.

### [CONCERN] Replay identity records the alias's output budget even where it is not sent

`max_output_tokens=model_max_output_tokens(alias)` takes the alias value regardless of provider. Dispatch sends the budget only when `capabilities.applies_output_budget` (dispatch.py:272). Only the OpenAI provider sets that to `True` (providers/openai/provider.py:36). Two aliases that differ only in `max_output_tokens` on any other profile send identical requests, yet they split into two rows labelled "max N output tokens". That contradicts `ProducerConfigRef`'s docstring (None means no budget was sent) and report.py's "what went on the wire". Effort is safe because `runner.py:298` overwrites it from the run's gated stamp. The budget is not overwritten. Gate it the same way, or take it from the run's stamp.

### [CONCERN] Compact silently drops the summary alias's effort

Compact records the session's effort, which is accurate. It never resolves the compact alias's own effort, and it logs nothing when the two differ. `summary.py:309` routes the same mismatch through `effort_for_session`, which logs once at WARNING (#216). The test `tests/pipeline/actions/test_compact.py::test_compact_alias_effort_mismatch_logs_no_warning` pins the silence. Slice decision D2 documents the choice. A configured effort dropped with no signal is the failure class this audit exists to catch. Resolve the compact alias and call `effort_for_session`, as summary does, and change that test to expect the warning.

### [CONCERN] The judge effort test mocks away the code it should check

The test patches `squadron.cli.commands.review.model_effort` to return `Effort.high` for any argument. It then checks only that the transport received `Effort.high`. It never checks what `model_effort` was called with. That argument is the one thing `_resolve_judge_model` (review.py:1463-1479) adds: it reads the alias name before expansion. If that code passed the expanded id instead, this test would still pass. Assert the call argument, or use a real alias configured with an effort.

### [NOTE] Defaulted `effort: Effort | None = None` can silently drop effort

The same default appears in `resolve_review` (resolution.py:321) and `judge_residue_core` (src/squadron/review/addressed/judge.py:80). Every current caller passes effort explicitly (resolution.py:160, 346; review.py:1549; findings_addressed/judge.py:89), so nothing is dropped today. But a forgotten argument would now send no effort without any sign, which is the bug this slice audits. `_run_judge_leg` (resolution.py:126) already takes it without a default. Do the same here.

### [NOTE] A failed `set_model` is stamped with an effort that was never sent

The session path stamps the intended effort when `set_model` fails before any request goes out. A one-shot that fails before `note_effort_sent` (dispatch.py:255) stamps `None`. `action_effort_sent`'s docstring says "the effort an action sent". Pick one meaning and state it in one place. The set_model choice is pinned by `test_set_model_failure_stamps`.

### [NOTE] A second config label ignores the new identity fields

`_config_label` prints `alias (model, profile)` for the plan and omits effort, tool use and budget. `replay/config_label.py` is now the identity label, so one `ProducerConfigRef` has two labels. Use `config_label` here, or document that the plan deliberately shows less.

### [NOTE] Walrus inside a dict comprehension

`record_id: config_label(identity := _config_identity(replay.config), sorted(aliases[identity]))` binds `identity` in the enclosing scope and relies on argument evaluation order. The project asks for walrus only where it removes duplication. A plain loop would be clearer. The line is 103 characters, within the project's `line-length = 104`, so it passes format.

### [NOTE] A malformed stored effort can abort a whole read

`_parse_effort` raises `ValueError` on an unknown stored value. Raising is correct, since the alternative files the run as "not sent". The error propagates through `effort_sent_value` (src/squadron/stats/producer_units.py:161) into `extract_units` and `read_outcome`. One bad record could therefore stop a stats or replay report for the whole project. I did not trace whether those callers catch it. Decide whether one bad record should fail the report or be reported and skipped.

### [NOTE] The effort inventory's classifications and path map are not checked

The test enforces that every construction site is listed and that the counts match. It does not verify the `NO_ALIAS` reasons, such as "`--model` is passed raw". `PATH_TESTS` checks only that each named test exists, not that it asserts effort, so a renamed or gutted test would still pass. The inventory is a manual register. Say so in the module docstring, or check that each named test references effort.

### Run Digest

- Response length: 11563 chars
- Response is newline-free: no
- Tool calls made: 39
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 40
- Tokens — prompt / cached / cache write / completion / reasoning: 2430467 / 2220103 / 210336 / 68624 / not computed
- Duration: 301.3 s
- Cost: $0.50 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 13
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 13
- Finding-shaped matches — surviving validation: 13

## Responses

- [pass] F001, F002, F003: no change.
- [concern] F004 "not sent" and `Effort.none` render alike: fixed. `config_label` now prints `effort not sent` when no effort was sent, and `effort none` only for the real level. A report test pins the two as different.
- [concern] F005 output budget recorded where it is not sent: fixed. `config_ref` now takes the budget through `output_budget_sent_by_profile`, which applies the same `applies_output_budget` gate dispatch uses, so aliases that differ only in budget on a provider that ignores it share a row. Tests cover a provider that sends it and one that does not.
- [concern] F006 compact silently drops the alias's effort: fixed. A compact alias that configures an effort different from the session's now logs the #216 warning once, through the new `UsageCapture.note_session_mismatch` (which `effort_for_session` also uses). An alias that sets none stays silent, since it has nothing to drop; that keeps D2's reason (no warning on every compaction) while closing the gap. D2 is updated and the pinned test is replaced by a warns-once test and a no-effort-no-warning test.
- [concern] F007 judge effort test mocks away the code it checks: fixed. The test now also asserts `model_effort` was called with the alias name as typed.
- [note] F008 defaulted `effort`: fixed. `resolve_review`, `settle_findings` and `judge_residue_core` take `effort` with no default, as `_run_judge_leg` does. Every test call site passes it.
- [note] F009 what "sent" means: fixed in `stamp_effort_sent`'s docstring: it is the effort the action attempted to send, known once its model is resolved. A refused `set_model` keeps its stamp on purpose (the failure counts against the config that tried); a one-shot that fails before its capability gate stamps none.
- [note] F010 plan label: no code change. `_config_label` carries a comment saying the plan shows alias, model and profile only, because the effort sent is known after the run.
- [note] F011 walrus in a comprehension: fixed with a plain loop in `_labels`.
- [note] F012 malformed stored effort aborts a read: declined. An unrecognized stored value means corrupted or hand-edited state; reading it as "not sent" would file the run under the wrong config, which is the error this slice removes. The error names the value, and the callers do not catch it by design.
- [note] F013 inventory is a manual register: fixed in part. Each named proving test must now mention effort in its source, so a renamed or emptied test fails. The module docstring says the `NO_ALIAS` reasons are a manual register.
