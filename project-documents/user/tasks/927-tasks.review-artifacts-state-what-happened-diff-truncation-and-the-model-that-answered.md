---
docType: tasks
slice: review-artifacts-state-what-happened-diff-truncation-and-the-model-that-answered
project: squadron
lld: user/slices/927-slice.review-artifacts-state-what-happened-diff-truncation-and-the-model-that-answered.md
parent: user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: []
projectState: Implementation complete (73adc7c5, b33b736b, e560c6e3, ff39680b). Walkthrough steps 1-3, 5-6 run live; step 4 blocked by SDK-in-session restriction, verified structurally.
dateCreated: 20260926
dateUpdated: 20260926
status: complete
---

# Tasks: Review Artifacts State What Happened — Diff Truncation and the Model That Answered

## Context Summary

Fixes [#135](https://github.com/ecorkran/squadron/issues/135) and [#134](https://github.com/ecorkran/squadron/issues/134). A saved review must record facts about the run, not the request. Three parts:

- **Part A**: record whether the injected diff was truncated (`diffTruncated`, header line, JSON counts).
- **Part B**: a truncated diff + PASS + no successful tool call becomes CONCERNS with a synthetic finding and `verdictSource: imposed`.
- **Part C**: `aiModel` records the model that answered. `requestedModel` appears only on substitution.

Read the design before starting. Every task cites the decision (D1–D13) it implements. Those sections are the spec; this file does not repeat them.

Key constraints:
- Both `sq review` and the pipeline `review` action go through `run_review_with_profile` → `save_review_result` → `format_review_markdown`. Put every fact on `ReviewResult`. Never add a second rendering path.
- `tests/review/fixtures/clean_pass_artifact.md` must stay byte-identical. Do **not** regenerate it. If `test_clean_pass_artifact_is_byte_identical_to_the_pre_change_snapshot` fails, the new rendering is wrong.
- `None` means "not reported". Use `is None` checks, never `or 0`, for counts.
- `_truncate`'s signature does not change: `review/builders/code.py` imports it.
- Before every commit: `uv run ruff format`, `uv run ruff check`, `uv run pyright` (zero errors), plus the tests the task names.

Effort for the slice: 3/5. Commit A+B and C separately so either can be reverted alone.

**Next planned slice:** 928 (Codex parity for skill packs and provider access).

---

## Setup

- [x] **S.1 — Create the slice branch**
  - [x] Run `cf config get git.integration_branch`. Its value is the **target**; if it is empty, the target is `main`.
  - [x] `git checkout -b 927-slice.review-artifacts-state-what-happened-diff-truncation-and-the-model-that-answered <target>`, using the target from the previous step. Never hardcode `main`.
  - [x] `uv run pytest -q` passes on the fresh branch (baseline). Record the pass count for the DEVLOG.

## Part M — Shared model changes

- [x] **M.1 — Add `DiffInjection` and new `ReviewResult` fields** in `src/squadron/review/models.py` (Effort 1/5)
  - [x] Frozen dataclass `DiffInjection(total_chars: int, injected_chars: int)` with a `truncated` property (`injected_chars < total_chars`). Docstring says the unit is characters and why (D1).
  - [x] `ReviewResult` gains `diff_injection: DiffInjection | None = None`, `requested_model: str | None = None`, `answering_models: list[str] | None = None`. Comment each with its None meaning: `diff_injection` None = no diff input (D2); `answering_models` None = not produced by review_client, `[]` = provider reported none (D11).
  - [x] `VerdictSource.IMPOSED = "imposed"`. Rewrite the class docstring per the design's component table: it answers "where did this verdict come from?" (stated, derived, imposed), still a closed vocabulary. The parser never produces IMPOSED.
  - [x] Success: `uv run pyright` clean. Existing `tests/review/test_models.py` passes unchanged.

- [x] **M.2 — Add `answers_as_requested`** in a new `src/squadron/models/snapshot.py` (Effort 1/5)
  - [x] Signature `answers_as_requested(requested: str, answered: str) -> bool`, implementing D9 exactly: equal, or `answered == requested + "-" + snapshot` where snapshot is `\d{8}` or `\d{4}-\d{2}-\d{2}`. Compile the snapshot regex once as a module constant. Escape `requested`.
  - [x] No other equivalence forms. Wider forms are added only from ids captured in W.2.

- [x] **M.3 — Test `answers_as_requested`** in a new `tests/models/test_snapshot.py` (Effort 1/5)
  - [x] Parametrized cases, true: exact match; `claude-x` → `claude-x-20251001`; `gpt-5` → `gpt-5-2025-08-07`; `anthropic/claude-x` → `anthropic/claude-x-20260101`.
  - [x] Parametrized cases, false: `gpt-5` → `gpt-5-mini`; `gpt-5` → `gpt-4.1`; `claude-x` → `claude-x-2025` (partial date); regex metacharacters in `requested` (e.g. `a.b` vs `axb`) do not match.
  - [x] Success: `uv run pytest tests/models/test_snapshot.py` passes.

- [x] **M.4 — Add `model_substituted` and the `to_dict()` keys** in `src/squadron/review/models.py` (Effort 1/5)
  - [x] Property `model_substituted -> bool`: True only when `requested_model` is not None, `answering_models` is non-empty, and `answers_as_requested(requested_model, answering_models[-1])` is False (D10, D12: the last model is the one checked).
  - [x] `to_dict()` adds, always present: `diff_chars`, `diff_chars_injected`, `diff_truncated` (all `None` when `diff_injection` is None), `requested_model`, `answering_models`, `model_substituted`. See the design's "Artifact Contract" JSON block.

- [x] **M.5 — Test M.1 and M.4** in `tests/review/test_models.py` (Effort 1/5)
  - [x] `DiffInjection.truncated` for (100, 100), (100, 40), (100, 0), and (0, 0), which is not truncated (D2 empty diff).
  - [x] `model_substituted`: False with `requested_model` None; False with `answering_models` None or `[]`; False on a snapshot answer; True on `gpt-5` → `gpt-4.1`; with `["gpt-4.1", "gpt-5"]` and request `gpt-5`, False (last wins).
  - [x] `to_dict()` contains all six new keys, with `None`/`False` values on a default-constructed result.
  - [x] Success: `uv run pytest tests/review/test_models.py tests/models` passes. Commit: `feat: add diff injection and answering-model fields to ReviewResult`.

## Part A — Record diff truncation

- [x] **A.1 — Return the `DiffInjection` from `_inject_file_contents`** in `src/squadron/review/review_client.py` (Effort 2/5)
  - [x] Change the return to a two-field `NamedTuple` (e.g. `InjectedPrompt(prompt: str, diff: DiffInjection | None)`) defined in the same module.
  - [x] `diff` is None when `inputs` has no `diff` key. When the key is present:
    1. diff text came back and was added → `DiffInjection(len(diff), min(len(diff), max_file_size))`. Measure before `_truncate`. Never count the `[truncated at …]` marker (D1).
    2. `_add_injection` returned False (total limit) → `DiffInjection(len(diff), 0)` (D3).
    3. `_run_git_diff` returned None or empty → `DiffInjection(0, 0)` (D2).
  - [x] `_truncate` is unchanged.
  - [x] Update the call in `run_review_with_profile` to unpack the tuple. Hold the `DiffInjection` for A.3.

- [x] **A.2 — Update existing callers and test the accounting** (Effort 2/5)
  - [x] Update direct callers of `_inject_file_contents` in `tests/review/test_content_injection.py`, `tests/review/test_convention_root.py`, `tests/review/test_injection_decision.py`, and `tests/review/test_review_client.py` to read `.prompt`. Assertions otherwise unchanged.
  - [x] New tests in `test_content_injection.py`, patching `review.max_file_size_bytes` / `review.max_total_injection_bytes` the way the existing tests do: diff under the limit → not truncated, counts equal; diff over the file limit → `injected_chars == max_file_size`; diff skipped by the total limit → `injected_chars == 0`; empty diff → `(0, 0)`; no `diff` key → `None`.
  - [x] Success: `uv run pytest tests/review` passes.

- [x] **A.3 — Stamp `diff_injection` on the result** in `run_review_with_profile` (Effort 1/5)
  - [x] Assign `result.diff_injection` next to the existing telemetry assignments (after the recovery turn).
  - [x] Test in `tests/review/test_review_client.py`: a stubbed provider run with a `diff` input whose diff exceeds the patched limit yields `result.diff_injection.truncated is True`. A run without `diff` yields `None`.

- [x] **A.4 — Render truncation in the artifact** in `src/squadron/review/persistence.py` (Effort 2/5)
  - [x] `_review_frontmatter_lines` gains a `diff_truncated: bool | None` parameter. Emit `diffTruncated: true|false` after the tool telemetry lines when not None (D2). Pass `None` from `format_provider_failure_markdown`.
  - [x] `format_review_markdown`: when `diff_injection` is truncated, add a header line after `**Model:**`: `**Diff:** truncated: {injected} of {total} characters reached the model`. No line otherwise.
  - [x] Success: the clean-pass snapshot test still passes unchanged.

- [x] **A.5 — Test A.4** in `tests/review/test_persistence.py` (Effort 1/5)
  - [x] Truncated → `diffTruncated: true` in frontmatter and the `**Diff:**` line with the right numbers.
  - [x] Not truncated → `diffTruncated: false`, no `**Diff:**` line.
  - [x] `diff_injection` None → no `diffTruncated` key at all.
  - [x] Parse the frontmatter with the project's frontmatter reader and assert `diffTruncated` is a YAML boolean, not a string.
  - [x] JSON: `save_review_result(..., as_json=True)` output contains the three diff keys with matching values (frontmatter/JSON agreement).
  - [x] Success: `uv run pytest tests/review` passes.

## Part B — Cap a truncated, unread PASS

- [x] **B.1 — Implement `impose_diff_coverage`** in a new `src/squadron/review/coverage.py` (Effort 2/5)
  - [x] `impose_diff_coverage(result: ReviewResult) -> None`, mutating in place. Rule per D4: applies when `diff_injection` is truncated, successful calls `(tool_calls_made or 0) - (failed_tool_calls or 0) <= 0`, and `verdict is Verdict.PASS`. The `or 0` is deliberate and an exception to the `is None` rule above: D4 says no tools offered counts as zero calls. Add a one-line code comment citing D4 so nobody "fixes" it.
  - [x] Effect: `verdict = CONCERNS`, `verdict_source = VerdictSource.IMPOSED`, and prepend a `ReviewFinding(severity=CONCERN, category="review-coverage", ...)` with title `Diff truncated; the omitted part was never read`. The description uses the D4 text with real numbers: the model's stated verdict, the counts, the remedy. `location` None.
  - [x] Define the category string and title as module constants.
  - [x] Otherwise, no change.

- [x] **B.2 — Test `impose_diff_coverage`** in a new `tests/review/test_coverage.py` (Effort 2/5)
  - [x] Parametrize verdict {PASS, CONCERNS, FAIL, UNKNOWN} × tool state {`tool_calls_made` None; 0; 3 with 3 failed; 2 with 0 failed} × truncated {yes, no}.
  - [x] Only PASS + truncated + no successful call changes anything. In that case: verdict CONCERNS, `verdict_source` IMPOSED, findings[0] is the synthetic finding, and existing findings follow in order.
  - [x] The description contains the total, injected, and omitted counts, and the words "verdict was PASS".
  - [x] Success: `uv run pytest tests/review/test_coverage.py` passes.

- [x] **B.3 — Call the cap and add the exemption digest line** (Effort 1/5)
  - [x] In `run_review_with_profile`, call `impose_diff_coverage(result)` after `diff_injection`, `tool_calls_made`, and `failed_tool_calls` are all assigned (design, Special Considerations).
  - [x] In `persistence._run_digest_lines`: when `diff_injection` is truncated and `verdict is PASS` (a kept PASS), append `- Diff coverage: truncated; PASS kept because the model made N successful tool call(s)` (D4). Emit it only in that case.
  - [x] Test in `test_review_client.py`: stubbed run, truncated diff, zero tool calls, model says PASS → result verdict CONCERNS. Test in `tests/cli/test_cli_review.py` (or the existing CLI exit-code test module): the same stubbed imposed-CONCERNS run exits `sq review code` with the code `_exit_on` in `cli/commands/review.py` assigns to CONCERNS. Read `_exit_on` for the expected value; don't hardcode a guess (SC4). Test in `test_persistence.py`: a truncated PASS with 2 successful calls renders the exemption line; an untruncated PASS does not.

- [x] **B.4 — Pin that the cap never meets an unparsed-findings review** (D6) (Effort 1/5)
  - [x] No render change to `format_review_markdown` or `_display_terminal`: the not-parsed notice keeps its current `elif` condition.
  - [x] Test in `test_coverage.py`: a derived PASS (`fallback_used=True`, `verdict_source=DERIVED`, non-empty findings, truncated diff, zero tool calls) run through `impose_diff_coverage` then `format_review_markdown` shows the synthetic finding plus the parsed findings and no `## Findings Not Parsed`.
  - [x] Success: `uv run pytest tests/review tests/cli` passes, ruff and pyright clean. Commit: `feat: record diff truncation and cap unread truncated PASS reviews`.

## Part C — Record the model that answered

- [x] **C.1 — OpenAI provider: capture `chunk.model`** in `src/squadron/providers/openai/agent.py` (Effort 2/5)
  - [x] `TurnResult` gains `model: str | None = None`. In `_stream_turn`, read `chunk.model` from **every** chunk, before the `if not chunk.choices: continue`, and keep the last non-empty value (D8).
  - [x] The agent keeps a per-`handle_message` ordered, distinct `list[str]` of turn models, reset at the top of `handle_message` like the tool counters. Append in both the no-tools branch and every `_run_agentic_loop` turn.
  - [x] `_stamp_tool_telemetry` stamps `metadata["answering_models"]` with that list, next to `stop_reason`, **before** the tools early return. Leave the existing `metadata["model"]` (requested id) untouched.

- [x] **C.2 — Test C.1** in `tests/providers/openai/test_agent.py` and `test_agentic_loop.py` (Effort 2/5)
  - [x] The stream stub's chunks carry `model="gpt-5-2025-08-07"`. The final Message's `answering_models == ["gpt-5-2025-08-07"]` on the no-tools path.
  - [x] A choice-less final chunk carrying the model still counts.
  - [x] Agentic loop with two turns reporting different models → both listed, in order. The same model twice → listed once.
  - [x] A second `handle_message` on the same agent does not carry the first call's models.
  - [x] Success: `uv run pytest tests/providers/openai` passes.

- [x] **C.3 — SDK provider: collect `AssistantMessage.model`** in `src/squadron/providers/sdk/agent.py` (Effort 2/5)
  - [x] In `_translate_and_track`, for an `AssistantMessage` with `parent_tool_use_id is None` and `model` not equal to the `<synthetic>` constant, add `model` to an ordered distinct list. Define `_SYNTHETIC_MODEL = "<synthetic>"` once as a module constant.
  - [x] Reset the list in `handle_message` with the other counters.
  - [x] Stamp `final.metadata["answering_models"]` in the `ResultMessage` block, next to `stop_reason`.
  - [x] Do not read `ResultMessage.model_usage` (D8).

- [x] **C.4 — Test C.3** in `tests/providers/sdk/test_agent.py` (Effort 2/5)
  - [x] Build real `AssistantMessage`/`ResultMessage` instances, as existing tests do. A top-level message with model `claude-sonnet-5` → stamped `["claude-sonnet-5"]`.
  - [x] A subagent message (`parent_tool_use_id="toolu_1"`) with another model is excluded. A `<synthetic>` message is excluded.
  - [x] Counters reset between `handle_message` calls.
  - [x] Success: `uv run pytest tests/providers/sdk` passes.

- [x] **C.5 — Fold `answering_models` in `collect_turn`** in `src/squadron/review/turn_capture.py` (Effort 1/5)
  - [x] `TurnCapture.answering_models: list[str] = field(default_factory=list[str])`. In `collect_turn`, when a response's metadata has `answering_models`, append each id not already present, preserving order. This accumulates across the #92 recovery turn.
  - [x] New `tests/review/test_turn_capture.py`: a fake agent yielding stamped messages across two `collect_turn` calls → combined distinct list. A turn with no stamp leaves the list unchanged.

- [x] **C.6 — Assign model facts and warn** in `run_review_with_profile` (Effort 2/5)
  - [x] After the turns: `result.requested_model = resolved_model`, `result.answering_models = list(capture.answering_models)`. If the list is non-empty, `result.model = answering_models[-1]`. Otherwise leave `result.model` as the parser set it (the requested id, D11).
  - [x] WARNING when `result.model_substituted`: `"%s review requested model %s but %s answered"` (D10).
  - [x] WARNING when more than one distinct answering model: name them all (D12).
  - [x] No log when the list is empty (D11: Codex never reports; the artifact carries the signal).

- [x] **C.7 — Test C.6** in `tests/review/test_review_client.py` (Effort 2/5)
  - [x] Stub provider stamping `answering_models=["gpt-4.1"]` for request `gpt-5` → `result.model == "gpt-4.1"`, `model_substituted`, WARNING captured via `caplog` (this is #134's required test).
  - [x] Snapshot answer → `result.model` is the dated id, no WARNING.
  - [x] No stamp → `result.model` is the requested id, `answering_models == []`, no WARNING.
  - [x] Two models → the last is `result.model`, and one WARNING names both.

- [x] **C.8 — Render the model facts** in `src/squadron/review/persistence.py` (Effort 2/5)
  - [x] `_review_frontmatter_lines` gains `requested_model: str | None`. Emit `requestedModel:` directly after `aiModel:` when not None. `format_review_markdown` passes `result.requested_model` only when `result.model_substituted`. The failure artifact passes None (D13).
  - [x] Header: `**Model:** {model} (requested {requested})` on substitution only.
  - [x] Run Digest: when `answering_models == []`, append `- Answering model: not reported by provider (aiModel is the requested id)`. When it has 2 or more entries, append `- Answering models: a, b`. Nothing when None or exactly one (D11, D12).
  - [x] Tests in `test_persistence.py`: substitution renders both keys and the header suffix. A snapshot answer renders the dated `aiModel` with no `requestedModel`. `[]` renders the not-reported digest line. `None` renders nothing new. The clean-pass snapshot is unchanged. Frontmatter and JSON agree on `model_substituted`.

- [x] **C.9 — Terminal and pipeline follow the answering model** (Effort 1/5)
  - [x] `cli/commands/review.py` `_display_terminal`: on `model_substituted`, append ` (requested {requested_model})` after the model in the header.
  - [x] `pipeline/actions/review.py`: `metadata["model"] = result.model` and add `metadata["requested_model"] = model_id`.
  - [x] Tests: extend `tests/pipeline/actions/test_review_action.py` so a stubbed result with a substituted model puts the answering id in `metadata["model"]` and the request in `requested_model`. Add a terminal header test in `tests/cli/test_review_format.py`, where `_display_terminal` is already tested.
  - [x] Success: full suite `uv run pytest -q` passes, ruff and pyright clean. Commit: `feat: record the model that answered a review`.

## Walkthrough and close

- [x] **W.1 — Run design walkthrough steps 1–5** (Parts A and B) (Effort 2/5)
  - [x] Run each command in the design's Verification Walkthrough, steps 1–5, exactly. Record the observed verdict, `diffTruncated`, `verdictSource`, header line, and JSON values.
  - [x] Step 3: record whether the model made tool calls, and whether the exemption digest line appeared.
  - [x] Step 5 **must** run (`sq config unset ... --project`), so the project config is left clean. Confirm `git status` shows no config change.

- [x] **W.2 — Capture real answering-model ids per profile** (walkthrough step 6, D9) (Effort 2/5)
  - [x] For each profile with working credentials (sdk, openai, openrouter, local), run `sq review slice 927 --profile <profile> -v --output json --no-save` and record `requested_model` and `answering_models`. List any profile skipped for missing credentials by name.
  - [x] If any profile reports `model_substituted: true` for its own default model, that is a D9 false positive. Add the observed form to `answers_as_requested` with a test case built from the captured ids, then rerun that profile. Do not widen the rule beyond the observed form.
  - [x] Success: no profile's default model reports a substitution.
  - [x] If this task changed `snapshot.py`: run `uv run ruff format`, `uv run ruff check`, `uv run pyright`, and `uv run pytest tests/models tests/review`, then commit on its own as `fix: accept <profile> answering-model form in answers_as_requested`. Never fold that change into W.3's docs commit.

- [x] **W.3 — Documentation and close-out** (Effort 1/5)
  - [x] CHANGELOG: short user-facing bullets under Unreleased. Truncated diffs are recorded and an unread truncated PASS becomes CONCERNS. `aiModel` names the model that answered, and `requestedModel` flags a substitution.
  - [x] DEVLOG entry: what shipped, deviations from the design, the W.2 captured ids, and the suite pass count.
  - [x] Mark the tasks file and slice design `status: complete`, and mark slice plan entry 25 `[x]`.
  - [x] Commit: `docs: complete slice 927`. Merge the branch into the target per CLAUDE.md (re-read `git.integration_branch` first).
