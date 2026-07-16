---
docType: devlog
project: squadron
dateCreated: 20260218
dateUpdated: 20260715

---

# Development Log

A lightweight, append-only record of development activity. Newest entries first.

---

## 20260715 (9)

### Issue #21: `{keep_section}`/`{summarize_section}` never resolved by `_summary-instructions`

Confirmed the issue's own diagnosis against current source: two independent
render paths existed for compaction templates —
`compaction_templates.render_instructions()`
([src/squadron/pipeline/compaction_templates.py:83-116](src/squadron/pipeline/compaction_templates.py#L83-L116)),
which computes `keep_section`/`summarize_section` from `keep`/`summarize`
args, and `summary_render.resolve_template_instructions()`
([src/squadron/pipeline/summary_render.py:22-41](src/squadron/pipeline/summary_render.py#L22-L41)),
used by the `_summary-instructions` CLI command, which called
`render_with_params()` directly and never computed those two placeholders
at all — they fell through `LenientDict`'s missing-key handling and leaked
into output as literal `{keep_section}` text.

Checked `summary_instructions.py`'s CLI signature: no `--keep`/`--summarize`
flags exist on this entry point, so `keep`/`summarize` can only ever be
their defaults (empty list / `False`) here — ruling out "add CLI flags" as
the fix and confirming the issue's own suggested direction (route through
`render_instructions()`) was correct. Weighed against computing the two
placeholders locally in `summary_render.py`: routing through
`render_instructions()` keeps a single source of truth for which derived
placeholders a compaction template can reference, at the cost of two unused
`keep`/`summarize` parameters at this call site — preferred over
duplicating the placeholder names in two files.

Fix: `resolve_template_instructions()` now calls
`render_instructions(template, pipeline_params=params)` instead of
`render_with_params(template.instructions, params)` directly. Added
`test_keep_section_placeholder_resolved_not_leaked` to
`tests/pipeline/test_summary_render.py`, asserting `minimal-sdk.yaml`'s
`{keep_section}` reference resolves rather than leaking. Verified live via
`sq _summary-instructions minimal-sdk` — no leaked placeholders. Full gate:
2142 tests passed (+1), pyright strict 0 errors, ruff clean. Closes #21.

## 20260715 (8)

### Issue #23: SDKExecutionSession.dispatch had the same no-separator/no-filter join as #22

Same root-cause pattern as #22 (fixed earlier today for `review_client.py`
and `summary_oneshot.py`), found in a third location while fixing #22:
`SDKExecutionSession.dispatch()`
([src/squadron/pipeline/sdk_session.py:143-166](src/squadron/pipeline/sdk_session.py#L143-L166))
accumulated every translated SDK message's content — including
`tool_use` ("Using tool: Bash") and `tool_result` (command stdout) —
via bare list-append + `"".join()`, mixing tool-call narration into the
dispatch response with no separator.

Traced the two real consumers before fixing, resolving the issue's own
open question ("is this cosmetic-only?"): `_dispatch_via_session` in
[src/squadron/pipeline/actions/dispatch.py:191-200](src/squadron/pipeline/actions/dispatch.py#L191-L200)
passes the joined string to `_check_cli_error` (prefix check only, low
risk) and stores it as `outputs={"response": response_text}` — which
persists into `prior_outputs`, read by later steps including the F001
fix from earlier today (`_resolve_prompt_from_prior_review` scans
`prior_outputs` for review findings). A corrupted response string here
can therefore leak tool-call noise into what a later dispatch step's
prompt is built from — not cosmetic.

Fix: filter `sdk_type in (SDK_RESULT_TYPE, "tool_use", "tool_result")`
before appending to `response_parts` (session_id capture still runs for
every translated message, unchanged), and join with `"\n"` instead of
`""`. Mirrors the #22 fix exactly. Added
`test_dispatch_excludes_tool_call_noise` to
`tests/pipeline/test_sdk_session.py`, using `AssistantMessage` with
mixed `TextBlock`/`ToolUseBlock` content plus a top-level
`ToolResultBlock` SDK message to match how `translate_sdk_message`
actually produces these types. Full gate clean: 2141 tests passed,
pyright strict 0 errors, ruff clean. Closes #23.

## 20260715 (7)

### Issue #24: `sq review code` sent its template rules to the model twice

`review_code()` ([src/squadron/cli/commands/review.py:704-711](src/squadron/cli/commands/review.py#L704-L711))
already fully assembles `rules_content` via `load_review_rules("code",
resolved_rules_dir, file_paths=..., manual_rules_content=manual_content)`
— template rules (`review-code.md`) + language auto-detection + any
explicit `--rules` override, one copy of template rules. It then passed
both that assembled `rules_content` *and* `rules_dir=resolved_rules_dir`
into `_run_review_command`, whose own `if rules_dir is not None` guard
([review.py:322-329](src/squadron/cli/commands/review.py#L322-L329))
unconditionally re-ran `load_review_rules`, prepending `review-code.md`
a second time onto content that already had it. `review_slice`/`arch`/
`tasks` never hit this because they don't pre-assemble — they resolve
only `rules_dir` and let `_run_review_command` do the one and only
`load_review_rules` call for those templates.

Fix: `review_code` now passes `rules_dir=None` to `_run_review_command`,
since its `rules_content` is already complete — the existing guard then
correctly skips the redundant call for this caller only. Added
`test_review_code_template_rules_not_duplicated` to
`tests/review/test_cli_review.py`'s `TestRulesWiring` class, asserting
the template rules string appears exactly once in the `rules_content`
actually passed to `run_review_with_profile`. Full gate clean: 2140
tests passed, pyright strict 0 errors, ruff clean. Closes #24.

## 20260715 (6)

### Slice 303 re-review F001: judge-cycle's fix step never saw the judge's findings

Re-verified a finding from an earlier, never-filed comparison-review
artifact (`project-documents/user/analysis/303-review.code.judge-gated-cycle-conventions-sonnet5.md`,
run via `/code-review`) before fixing, per this session's ongoing effort
to eliminate false review findings — confirmed against current source
rather than taken on faith.

`judge-cycle.yaml`'s loop `dispatch` step had a static hardcoded
`prompt:`, and `dispatch.py`'s `_resolve_prompt` only scans
`prior_outputs` for a prompt when no explicit `prompt` param is set —
so that scan never ran, and the fix step repeated the same generic
instruction every iteration regardless of what the judge flagged.
Root cause was actually two-layered: even with the hardcoded prompt
removed, `_resolve_prompt` had no branch at all for a prior `review`
action's output — it only knew how to pull `stdout` from a prior
`cf-op(build_context)` result. Fixed both: removed the YAML's
hardcoded `prompt:` ([judge-cycle.yaml](src/squadron/data/pipelines/judge-cycle.yaml)),
and added `_resolve_prompt_from_prior_review`
([dispatch.py](src/squadron/pipeline/actions/dispatch.py)) — a new
fallback tier that scans `prior_outputs` for the most recent `review`
action, formats its structured findings (severity/summary/location)
into a fix prompt, or falls back to "perform an initial improvement
pass" when the prior review had no findings (e.g. iteration 1, or a
clean PASS). Verified `prior_outputs` does thread across loop
iterations by reference (`executor.py:713-714`, `1013`), so this
actually reaches the fix step on iteration 2+.

Added `TestDispatchPriorReviewFallback` (4 tests) to
`tests/pipeline/test_dispatch.py`: explicit `prompt:` still wins over
a prior review (only steps that omit it fall through), prior-review
findings become the prompt, a findings-less prior review yields the
initial-pass message, and no prompt/build_context/review anywhere
still raises `KeyError`.

### Slice 303 re-review F002: `template.model` fallback invisible to the classification pre-scan

The T7 fix in `ReviewAction._review` (`review.py:120-125`) retries
model resolution against a review template's own `model:` default
when the standard 5-level cascade is empty — but that retry is local
to `_review` and never goes through `ModelResolver.cascade_candidates()`,
which the slice-243 classification pre-scan (`classification.py`)
treats as the single source of truth for what the cascade will
resolve to. A pipeline relying solely on a template's default model
(no CLI/action/step/pipeline/config override) got a false
`ClassificationError` before the pipeline even started, even though
runtime resolution would have succeeded.

Considered making `template.model` a real 6th tier inside
`ModelResolver` itself, but that would require teaching the generic
resolver (shared by dispatch/summary/compact, none of which have
templates) about review templates specifically. Asked Erik, who
confirmed the surgical option: mirror the exact fallback locally in
`classification.py` instead. Added `_review_template_model_fallback()`,
called from both `classify_pipeline`'s top-level action loop and
`_classify_container_inner` (the loop/each/fan_out inner-step path —
the one `judge-cycle.yaml` actually exercises) when the cascade comes
back empty for a `review` action. Loads the template via the same
`get_template()`/`load_all_templates()` used at runtime; confirmed
this doesn't violate the module's documented side-effect-freeness
contract (`test_classification_is_idempotent_and_side_effect_free`
only asserts idempotency and zero `pool.select()` calls, both
preserved by a deterministic template load).

Added 3 tests to `tests/pipeline/test_classification.py`: a top-level
review step with no cascade model falls back to the template's
default, still raises when the template also has no model, and the
loop-container inner-step path specifically (matching
`judge-cycle.yaml`'s actual shape).

### Slice 303 re-review F003: malformed judge threshold silently discarded a completed review

Fixing "judge reviews always persist as UNKNOWN" required moving
judge-verdict computation (`resolve_thresholds`/`enforce_judge`)
before persistence in `ReviewAction._review`, so the derived verdict
could be passed into `verdict_override`. But `resolve_thresholds`
calls unguarded `float()` on `pass_floor`/`concerns_floor` — a
malformed step-level `judge:` override (e.g. a non-numeric
`pass_floor`) now raised *before* persistence's own try/except
(`review.py:230`) was ever reached, discarding a review whose model
call had already succeeded, with no file written at all. Previously
persistence ran first in its own non-fatal try/except, so the
artifact was always saved regardless.

Wrapped the threshold resolution/enforcement in its own narrow
`try/except (TypeError, ValueError)` that logs a WARNING and degrades
to `verdict="UNKNOWN"`/`provenance=judge` — matching the existing
"no score / out-of-range score → UNKNOWN" behavior already inside
`enforce_judge` for a different failure mode. Persistence below still
runs either way.

Added `test_malformed_threshold_override_degrades_to_unknown_and_still_persists`
to `tests/pipeline/actions/test_review_action.py`, asserting
`success=True`, `verdict=UNKNOWN`, a WARNING log, and that
`save_review_file`/`format_review_markdown` were still called.

### Slice 303 re-review F004 (PLAUSIBLE): `as_json` persistence never received `verdict_override`

`save_review_result`'s `as_json=True` branch called `result.to_dict()`
directly, bypassing `verdict_override` entirely — the docstring said
as much ("Ignored for `as_json` output"). A judge review persisted as
JSON would show `UNKNOWN` while the markdown persistence of the
identical run showed the correct threshold-derived verdict. Dormant
today (no live caller passes both `as_json=True` and a judge
template), but real.

Gave `ReviewResult.to_dict()` an optional `verdict_override` parameter
(mirroring `format_review_markdown`'s existing signature) and threaded
it through from `save_review_result`. Added 2 tests to
`tests/review/test_models.py` (`to_dict(verdict_override=...)` in
isolation) and 1 to `tests/cli/test_review_save.py` (the full
`save_review_result(as_json=True, verdict_override=...)` path writing
real JSON to a `tmp_path`).

Full gate (2139 tests, pyright strict, ruff) clean before commit.
None of F001-F004 were filed as GitHub issues — Erik preferred to fix
directly since all four were confirmed against current source.

---

## 20260715 (5)

### Issue #22: Verified Against Real SDK Run; Issue #24 Filed (Rules Sent Twice)

Erik ran the fixed build in a real terminal (`uv run sq run`, local
unpublished build — an earlier attempt using the globally-installed
version predictably still hit the old bug) against `claude-sonnet-5`,
producing `project-documents/user/reviews/303-review.code.judge-gated-cycle-conventions.md`.
Checked the saved review for validity: raw output is clean prose
throughout — no `Using tool:` fragments, no run-on lines, well-formed
`### [SEVERITY]`/`location:`/`category:` structure. All six findings
(4 PASS, 2 NOTE) traced against real source and verified accurate — no
hallucinated paths, lines, or symbols. Confirms the #22 fix (commit
`2032cf0`) holds against actual Claude Agent SDK message shapes, not
just the hand-constructed mocks in `test_review_client.py`/
`test_summary_oneshot.py`. Closed #22.

**New finding surfaced during verification, filed as #24 (not fixed
this session):** the saved review's debug appendix showed the
"Design Principles" / SOLID rules content duplicated — once in the
`### System Prompt` section and again in `### Rules Injected`, and
duplicated *within* the system prompt section itself. Traced to
confirm this is a real double-send to the model, not just a debug
display artifact:

- `review_code` ([cli/commands/review.py:707-711](src/squadron/cli/commands/review.py#L707-L711))
  calls `load_review_rules("code", resolved_rules_dir, file_paths=...,
  manual_rules_content=manual_content)` — correctly assembles template
  rules (`review-code.md`) + auto-detected language rules (`python.md`)
  + any explicit override. One copy of template rules.
- It then calls `_run_review_command` ([lines 721-729](src/squadron/cli/commands/review.py#L721-L729)),
  passing **both** this already-assembled `rules_content` *and*
  `rules_dir=resolved_rules_dir`.
- `_run_review_command` ([lines 322-329](src/squadron/cli/commands/review.py#L322-L329))
  unconditionally re-runs `load_review_rules` whenever `rules_dir is
  not None`, prepending `review-code.md`'s content a **second time**
  onto content that already has it.
- `review_client.py:78-82` bakes the resulting doubled `rules_content`
  into `AgentConfig.instructions` — the actual system prompt sent to
  the model. Confirmed this is real, not cosmetic: every `sq review
  code` run with a rules dir configured (the common case) sends
  `review-code.md`'s content twice, inflating prompt size and token
  cost on every call.
- `slice`/`arch`/`tasks` review commands don't have this bug — they
  never pre-assemble `rules_content` themselves, so `_run_review_
  command`'s single internal `load_review_rules` call is the only one
  that ever runs for those paths. `_run_review_command`'s own comment
  ("Language auto-detection is handled by the caller... `_run_review_
  command` only sees the template [rules]") is stale — `review_code`
  now does its own full `load_review_rules` call including template
  rules, not just auto-detection, so the comment's assumed division of
  labor no longer holds.

Not fixed this session — needs its own change (likely: `review_code`
passes `rules_dir=None` once it has fully assembled `rules_content`
itself, relying on the existing `if rules_dir is not None` guard to
skip the redundant call) plus a regression test asserting `review-
code.md` content appears exactly once in the final system prompt.

Also committed (`477db4f`): the verification review file itself, and
the untracked `303-review.code.judge-gated-cycle-conventions-kimi26.md`
comparison-run artifact from the original #19 size-cap investigation
(previously referenced but never committed).

## 20260715 (4)

### Issue #22: SDK Tool-Call Noise No Longer Corrupts Review/Summary Raw Output

Noticed while investigating #20 (fabricated review findings): the fixed
`sonnet-fail.md` artifact's raw response contained an unreadable run-on
line — `Using tool: BashUsing tool: BashUsing tool: Read...Clean. Now
let's run the relevant test suite...` — prose and tool-call narration mashed
together with no whitespace between them at all.

**Root cause:** `providers/sdk/translation.py` correctly translates each SDK
content block into its own `Message` — a `TextBlock` (the model's actual
prose, `sdk_type: assistant_text`) and each `ToolUseBlock` (a tool
invocation, rendered as `content=f"Using tool: {block.name}"`, `sdk_type:
tool_use`) are distinct, well-formed messages. The bug was downstream, in
how callers reassembled them: both `review_client.py:150`
(`raw_output += response.content`) and `pipeline/summary_oneshot.py:78`
(identical pattern) accumulated every yielded message — prose, tool-use
markers, and tool-result content (command stdout / file contents,
`sdk_type: tool_result`) alike — via bare string concatenation with no
separator and no type filtering. Whenever a model's turn alternated prose
and tool calls (normal for any review or summary that reads files or runs
commands before responding), the result was one run-on line with tool
narration interleaved mid-sentence.

**Why this isn't just cosmetic:** the corrupted text is exactly what
`parse_review_output` parses for `## Summary` / `### [SEVERITY] Title`
structure, and what gets written verbatim into the saved review file body
and the `-vv`/mismatch debug log. A tool-use marker landing between two
lines that were meant to be separate can break the very structural patterns
the parser depends on — plausibly a contributing cause of #20's fabrication
trigger, independent of #20's own (already-fixed) fallback-extraction bug.

**Fix:** both call sites now filter out `sdk_type in ("tool_use",
"tool_result")` messages entirely (alongside the pre-existing
`SDK_RESULT_TYPE` duplicate-content filter) and join the remaining
assistant-text chunks with `"\n"` instead of bare `+=`. Non-SDK providers
never set `sdk_type` and are unaffected — the filter only ever excludes
messages that explicitly opt in to the `tool_use`/`tool_result` marker.
Updated `test_summary_oneshot.py`'s multi-chunk test to expect newline
joining instead of the old bare-concatenation shape; added
`test_capture_summary_filters_tool_messages` and (in
`test_review_client.py`) `test_raw_output_excludes_tool_call_noise`, both
asserting tool-call content never reaches the accumulated output.

**Scope note:** `pipeline/sdk_session.py:166` (the main dispatch path for
design/tasks/implement steps) has the identical pattern
(`"".join(response_parts)`, no tool-message filtering) but was left
untouched — it's a different subsystem (dispatch artifacts are mostly
written by the agent's own file tools, not parsed from the returned string)
that needs its own look at actual downstream impact before applying the
same fix blind. Filed as [#23](https://github.com/ecorkran/squadron/issues/23).

**Not yet verified against a real SDK run** — all coverage above is via
mocked `handle_message` iterators. Real-terminal `sq review code` runs
against `claude-sonnet-5` (or another SDK profile) are still needed to
confirm the fix holds against actual Claude Agent SDK message shapes, not
just the mocked translation this repo's tests construct by hand.

Full gate: `uv run pytest` (2128 passed, 2 skipped), `uv run pyright` (0
errors), `uv run ruff check`/`format` (clean). Committed directly to `main`
(non-slice bugfix, no feature branch). Closes
[#22](https://github.com/ecorkran/squadron/issues/22).

## 20260715 (3)

### Issue #20: Parser No Longer Fabricates Findings From Unstructured Prose

Follow-up from slice 303's comparison code-review testing (same batch as
#19, below). A `sq review code 303 -vv --model claude-sonnet-5` run produced
a persisted review whose frontmatter `findings` were verifiably garbage:
truncated mid-sentence fragments lifted from the model's own tool-use
narration (`"**What's solid:** ruff and pyright are clean..."`) and a
numbered "Gaps found" list item, each dressed up with an invented severity
and a fabricated `F001`/`F002` id. Structurally valid-looking, semantically
meaningless.

**Root cause:** `parsers.py`'s `_extract_findings` correctly requires a real
structural marker (`### [SEVERITY] Title`, `**[SEVERITY]** Title`, or
`- [SEVERITY] Title` — five formats total after slice 122's widening). When
a model's response has a CONCERNS/FAIL verdict but doesn't emit any of those
markers, the parser fell through to `_lenient_extract_findings`, whose
`_LENIENT_RE` regex matched on the bare presence of `NOTE`/`CONCERN`/`FAIL`
*anywhere in a line*, with no structural anchor — the opposite of what
`_extract_findings` requires. Confirmed via the affected review's own raw
output: the model wrote free-form prose, and the keyword-anywhere regex
grabbed sentence fragments after it, truncated to 120 chars, as if they were
independent findings.

**History check (before fixing):** this fallback path is genuinely old
(`c0c697f`, 2026-03-25, slice 122 "Review Context Enrichment") and was
solving a real, documented problem at the time — `minimax` returning a
CONCERNS verdict with the saved review showing "No specific findings" at
all, silently dropping real concerns the model had raised. Slice 122's
design doc (Layer 2/Layer 3 split) conflated two different fixes under one
"fallback" umbrella: Layer 3 (widening `_FINDING_RE` to accept colon
separators, bold brackets, bullets — still requiring a real marker) is
sound and unchanged. Layer 2 (`_lenient_extract_findings` +
`_synthesize_fallback_finding`, no structural anchor) is what actually
fabricates. Confirmed via `git log` that nothing in the review subsystem
changed in the days immediately before this bug was noticed — the parser
gap is ~4 months old; it was model-response variance (this specific
`sonnet5` run's prose shape) that exposed it now, not a regression.

**Fix:** removed `_lenient_extract_findings` and
`_synthesize_fallback_finding` entirely, along with `_LENIENT_RE`. When a
CONCERNS/FAIL verdict has zero structured findings, `parse_review_output`
now logs a WARNING (template, model, verdict) and leaves `findings` empty —
the same "honest empty" shape already used for PASS. Nothing is silently
lost: `ReviewResult.raw_output` (and the saved review file body) always
carries the model's full raw response regardless of findings, so a human
can still read what the model actually said; it's just no longer disguised
as structured findings. `fallback_used` keeps its existing meaning
("verdict/findings mismatch was detected") for telemetry/debug-log
purposes. Updated `tests/review/test_parsers.py`'s `TestFallbackParsing`
class to assert the new empty-findings-plus-warning behavior instead of
the old synthesized-finding shape; added `test_mismatch_preserves_raw_output`
and `test_mismatch_logs_warning`.

Full gate: `uv run pytest` (2126 passed, 2 skipped), `uv run pyright` (0
errors), `uv run ruff check`/`format` (clean). Committed directly to `main`
(non-slice bugfix, no feature branch — `git.integration_branch` unset).
Closes [#20](https://github.com/ecorkran/squadron/issues/20).

## 20260715 (2)

### Issue #19: Review File-Injection Size Caps Are Now Configurable

Also from slice 303's comparison code-review testing: a `kimi26` review run
truncated a 136,191-byte diff because `review_client.py`'s file-injection
limits (`_MAX_FILE_SIZE` = 100KB, `_MAX_TOTAL_INJECTION` = 500KB) were
hardcoded module constants with no way to raise them for a model with a
larger context window.

**Fix:** added two typed config keys, `review.max_file_size_bytes` (default
100,000) and `review.max_total_injection_bytes` (default 500,000), to
`config/keys.py` following the existing `ConfigKey` pattern. Removed the
hardcoded constants from `review_client.py`; `_inject_file_contents` now
resolves both via `get_config(key, cwd=...)` at call time, scoped to the
review's `cwd`, with `isinstance` narrowing and an explicit `TypeError` on
type mismatch (fail-fast per CLAUDE.md, since `_coerce_value` guarantees the
stored type is always `int` — a mismatch here is genuinely exceptional, not
a normal missing-config case). `_truncate` now takes `max_file_size` as an
explicit parameter instead of reading a module constant. No additional
wiring needed for `sq config get/set/unset/list` — those subcommands
already operate generically over `CONFIG_KEYS`, so the new keys were live
immediately; verified with `sq config list` and `sq config get
review.max_file_size_bytes`.

New test `test_max_file_size_config_override` proves a raised config value
actually lets larger content through untruncated. Full gate: `uv run
pytest` (2125 passed, 2 skipped), `uv run pyright` (0 errors, after fixing
a `reportArgumentType` regression from passing untyped `object` to `int()`
— resolved with the same `isinstance` narrowing pattern already used in
`cli/commands/review.py:_resolve_verbosity`), `uv run ruff check`/`format`
(clean). Committed directly to `main` (`71d8524`, non-slice bugfix, no
feature branch). Closes [#19](https://github.com/ecorkran/squadron/issues/19).

**Note:** this fix does not address #20 (above) — the `sonnet5` review
artifact that motivated #20 had a diff well under the size cap; its failure
is 100% attributable to the parser-fabrication bug, unrelated to injection
truncation.

## 20260715 (1)

### Slice 303: Judge-Gated Cycle Conventions — Complete

Phase 6 implementation complete, T0–T8. Delivered `judge-cycle.yaml` (built-in
reference pipeline: fix-first `loop [dispatch, review]`, `max: 3`,
`until: review.pass`, `on_exhaust: checkpoint`, review step templated on
`judge.slice-vs-arch`), a structural test in `test_loader_integration.py`,
three control-flow tests in a new `tests/pipeline/test_judge_cycle.py`
(auto-advance, escalate-at-max, advisory-always-escalates — all driving the
real `ReviewAction`/loop/`enforce_judge` path with only
`run_review_with_profile`/persistence/`resolve_slice_info` mocked), and a
"Judge-Gated Cycles" section plus missing `### loop`/bare-`dispatch` catalog
entries in `docs/PIPELINES.md`.

**Live validation (T7) surfaced two pre-existing bugs, both fixed:**

1. `judge-cycle.yaml` initially left the review step's `model:` unset,
   relying on an implicit fallback — inconsistent with every other built-in
   pipeline's convention (`P4.yaml`, `slice.yaml`: named `model`/
   `review-model` params, referenced via placeholders). Rewrote
   `judge-cycle.yaml` to match: `params: {model: sonnet, review-model:
   minimax}`, both steps reference their param via `"{...}"`.
2. Independent of (1), `ReviewAction`'s model-resolution cascade (CLI →
   action → step → pipeline → config) never consulted a review template's
   own `model:` default — unlike `sq review`'s CLI-side cascade, which
   falls back to `template.model` as its last resort
   (`cli/commands/review.py:_resolve_model`). A pipeline `review:` step with
   no model anywhere always raised `ModelResolutionError`, even for a judge
   template that declares a sensible default (`judge.slice-vs-arch`:
   `opus`). Fixed in `pipeline/actions/review.py`: on `ModelResolutionError`
   from the standard cascade, retry once against `template.model` before
   giving up. New tests in `test_review_action.py` cover both the rescue
   path and the case where no template default exists (error still
   propagates unchanged).
3. Also surfaced live: the persisted review file's `verdict:` field came
   from the raw `ReviewResult.verdict`, always `UNKNOWN` for judge templates
   by design (`judge-slice-vs-arch.yaml`'s prompt explicitly forbids
   emitting a verdict line — the score is the source of truth). A human
   reading the file saw `UNKNOWN` next to a score that clearly passed.
   Fixed: `format_review_markdown`/`save_review_result`
   (`review/persistence.py`) now accept an optional `verdict_override`;
   `ReviewAction._review` computes the `enforce_judge`-derived verdict
   *before* persistence (previously persistence ran first) and supplies it
   for judge templates. New tests in both `test_review_action.py` and
   `test_persistence.py` cover the override and the unchanged
   non-override/non-judge paths.

All three fixes are small, additive parameter/reordering changes to
*existing* functions — no new step type, action, selector, or executor
branch, so FR6 ("no new constructs") holds — but they are a deviation from
the slice's stricter "zero engine code" framing, noted directly in the LLD's
Success Criteria section rather than glossed over.

**T7 final live run** (`sq run judge-cycle 302`, no manual `--model`,
minimax via the new param defaults): judge scored slice 302's design at 98
against its architecture doc, cleared `pass_floor` (82), loop exited on
iteration 1, pipeline reported `completed`/`PASS`. Persisted file
(`302-review.judge.slice-vs-arch.design-phase-judge-templates.md`) now shows
`verdict: PASS` end-to-end. An earlier iteration of this same live run (fix
leg, score below the floor) genuinely improved
`302-slice.design-phase-judge-templates.md`'s anchoring-mitigation
rationale — committed as real design-doc value, not test residue.

**Known gap, not fixed (out of scope):** `LoopStepType.expand()` deliberately
returns `[]` (iteration is owned by the executor's `_execute_loop_body`, not
the flat action-list path) — so `--prompt-only` mode cannot drive any `loop`
step at all, including `judge-cycle`. `sq run` inside a Claude Code session
also refuses direct SDK execution. A `loop`-based pipeline is therefore only
runnable from a standalone terminal today. Not filed as a separate GitHub
issue; noted here and in the slice's Verification Walkthrough for whoever
picks up prompt-only/loop support next.

Full gate: `uv run pytest` (2124 passed, 2 skipped), `uv run pyright` (0
errors), `uv run ruff check` (clean). Slice 303 marked complete in its own
frontmatter and in `300-slices.eval-actions-llm-as-judge-scoring.md`.
Branch `303-slice.judge-gated-cycle-conventions` ready to merge to `main`.

## 20260714 (3)

### Slice 303: Judge-Gated Cycle Conventions — In Progress

Phase 5 (task breakdown) complete: created
`user/tasks/303-tasks.judge-gated-cycle-conventions.md` (T0–T8) from the
approved LLD. The slice is data + docs + tests only — no engine change:
`judge-cycle.yaml` reference pipeline (fix-first `loop [dispatch, judge]`,
`max: 3`, `until: review.pass`, `on_exhaust: checkpoint`), structural test in
`test_loader_integration.py`, three control-flow tests (auto-advance,
escalate-at-max, advisory-always-escalates) in a new
`tests/pipeline/test_judge_cycle.py`, authoring docs in `docs/PIPELINES.md`,
and one live unattended validation run.

Two findings surfaced during breakdown, folded into the tasks:
- `docs/PIPELINES.md` has no `### loop` (or bare-`dispatch`) Step Type
  Catalog entry — the convention section is unfollowable without them; T6
  adds both alongside the judge-gated-cycles section.
- The issue-#18 guard (`4564471`, shipped after the 303 design) makes a
  missing `input`/`against` file a hard error in `ReviewAction._review`, so
  the control-flow tests cannot mock `run_review_with_profile` alone — T3's
  harness must provide real tmp input/against files or patch the slice-input
  resolution seam, while keeping `resolve_thresholds`/`enforce_judge` and the
  loop evaluation real.

Pending: Phase 6 implementation on branch
`303-slice.judge-gated-cycle-conventions` (T0). Resume point: T0/T1.

## 20260714 (2)

### Fixed issue #18: review input/against existence guard

`missing_input_files()` (new, `review/template_inputs.py`) returns the
`input`/`against` keys whose values name no real file — checked against both
the process cwd (how non-SDK content injection resolves paths) and
`inputs["cwd"]` (how SDK review agents resolve them), so a path valid under
either provider semantics is accepted. Both review boundaries now hard-fail
on a non-empty result before any model call: `_run_review_command` (covers
`sq review slice|tasks|arch|code`) exits 1 with `Error: {key} file not
found: {path}`; `ReviewAction._review` raises the same KeyError shape as its
existing required-inputs check, so judge-awareness (verdict=UNKNOWN) and
step-failure routing are preserved. Defense-in-depth: `_inject_file_contents`
now logs a WARNING when it skips a missing `input`/`against` (it previously
skipped silently — the asymmetry with its logged `OSError` branch was the
original #18 observation); other keys still skip silently by design since
they may hold non-path values.

Tests: 11 new (helper unit tests, CLI guard via CliRunner, pipeline action
guard, injection-warning + no-noise cases). 13 existing tests updated —
they passed fabricated paths (`slice.md`, `a.md`, `f.md`) to mocked review
clients and now use real tmp files, which the guard correctly rejected.
Full gate: ruff clean, format clean, pyright 0 errors, pytest 2112 passed /
2 skipped.

**Correction to 20260714 (1) below:** its claim that no `143-tasks.*.md`
existed on disk was a stale snapshot — the file was created minutes later
by a parallel agent working the same repo, and the review it sourced was
genuine (verified via timestamps and finding-ID cross-references). Issue
#18's "observed in the wild" example was retracted on the issue; the code
gap itself was real regardless and is what this entry fixes. Lesson
recorded: filesystem facts from earlier in a session decay — re-verify at
the moment of use, especially before publishing claims.

## 20260714 (1)

### Diagnosed field bug: 909 dispatch-artifact fix never released to PyPI

`sq run p5a <slice>` failed in a client repo (grizcam_mobile_ios) at the
`review template=tasks` step with `missing required input(s): input,
against` — the exact pre-909 symptom, on a repo confirmed to have current
guides and no CF-side formatting issue.

**Investigation ruled out, in order:** (1) `p5a.yaml`/`p4.yaml` custom
pipeline definitions — both correctly use `tasks:`/`design:` phase-step
shorthand, not raw `dispatch:`, so they get the full 909 post-condition
guard; (2) context-forge slice-plan parsing — slice 143's checklist line
(`4. [ ] **(143) ...** — desc`) matches `PLAN_INDEXED_RE` cleanly, confirmed
by testing the actual line against the regex; (3) CF worktree scoping — not
in use in the affected repo; (4) a race between the two `resolve_slice_info`
calls (dispatch's post-condition check and the review step's input
resolution) — ruled out, `cf list tasks --json` does a live filesystem scan
with no caching on either side.

**Root cause:** the installed `sq` was `squadron-ai 0.6.2` via `uv tool
install` — a real PyPI release, not a dev/editable checkout. Confirmed by
grepping the installed wheel's `executor.py` directly: zero references to
`_check_dispatch_artifact_written` / `expected_artifact_kind`. The 909 fix
(commit `49b8522`) merged to `main` on 20260710 but `pyproject.toml`'s
`version` was never bumped past `0.6.2` and no release was cut — so every
consulting client running `squadron-ai` from PyPI has been on pre-909
squadron the entire time, including this session's own local install
(chalked up as "we should release 0.6.2 anyway" rather than investigated
further, since the fix and its tests are confirmed correct on `main`).

Slice 143 itself is legitimately `needs-design`/`not-started` — no
`143-tasks.*.md` exists on disk, consistent with a dispatch agent turn that
ended without writing the file (same failure shape as the original 303
repro that motivated 909). On a release containing 49b8522, this would now
fail loudly at the dispatch step with an accurate message instead of
surfacing one step later at review.

**Action:** prepared a 0.7.0 release (see below) rather than a 0.6.3 patch
— `[Unreleased]` already contained a full minor's worth of shipped-but-
unreleased feature work (judge templates, judge enforcement) alongside the
three bug fixes, so a minor bump is correct per semver even though this
investigation only needed the fix half.

### Prepared release 0.7.0

Bumped `pyproject.toml` version `0.6.2` → `0.7.0`, re-ran `uv lock` to sync
`uv.lock`, converted `CHANGELOG.md`'s `[Unreleased]` section to `## [0.7.0]
- 20260714` (left a fresh empty `[Unreleased]` above it). Verified `uv
build` produces a clean sdist/wheel and that the built wheel actually
contains the 909 fix (`unzip -p ... | grep _check_dispatch_artifact_written`
→ 2 matches). Full test suite green: 2101 passed, 2 skipped, 0 failed — no
regressions since the last recorded baseline. Committed and tagged `v0.7.0`;
`pypi` publish deliberately deferred as a separate, explicit step.

## 20260712 (1)

### Slice 906: Quickstart and Onboarding Documentation — Complete

New `docs/QUICKSTART.md`, plus two additive links from `README.md`. Docs-only
slice; no code changes. Branch `906-slice.quickstart-and-onboarding-documentation`
merges to `main` on completion, `codeReview: none` (no-code slice, gate
bypassed via `cf check --set-review-none 906`).

**Design history — two corrections, both discovered by re-verifying live
state instead of trusting the prior draft:**

1. The original design (20260513) assumed a manual multi-step install
   narrative (npm → `cf init` → pipx → `sq install-commands` → provider auth)
   that slice 908 (`sq setup`) has since superseded. Rebuilt 20260711 to lead
   with `install.sh` → `sq setup` as the canonical path.
2. That rebuild *itself* turned out to misdescribe the current README: it
   assumed README's Install section still needed the `curl | sh` one-liner
   added (908 had already landed it) and that Quickstart needed replacing
   with an install-pointer (Quickstart is actually a different, already-good
   section — SDK auth, review-a-design, review-tasks-then-code — unrelated to
   install steps). Corrected 20260711 after actually reading the live README
   top to bottom rather than reasoning from the stale design.
3. During Phase 6 itself, Task 1's re-verification step (built into the task
   file specifically to catch further drift) found a third error: the design
   claimed `sq run` was undocumented anywhere in README. It is documented —
   a `## Pipelines (sq run)` section already exists. "Your first pipeline
   run" was written as a short bridge/pointer (matching the "Your first
   review" section's treatment), not as net-new content.

**What QUICKSTART actually covers** (the real, narrower gap after all three
corrections): how to read `sq doctor`/`sq setup --check-only` output
(undocumented anywhere before this), the full six-profile provider matrix
(README's existing Quickstart only documents `sdk` auth), and pointers to
README/`docs/PIPELINES.md` for review and pipeline walkthroughs rather than
duplicating them.

**Verification (20260712):** `sq doctor -v`, `sq setup --check-only`,
`sq run --help`, and `BUILT_IN_PROFILES` all captured live and used verbatim
in QUICKSTART rather than reconstructed from memory. `sq run slice 906
--dry-run` confirmed QUICKSTART's example command resolves correctly.
`git diff README.md` confirmed additive-only (two insertions, zero
deletions). Full gate: ruff clean, pyright 0 errors, pytest 2101 passed / 2
skipped / 0 failed — matches pre-slice baseline (docs-only change).

**Takeaway for future doc slices:** a slice design's claims about "what's
currently documented" or "what's currently missing" are load-bearing facts
that decay fast — this slice needed re-verification at three separate
points (initial rebuild, second rebuild, and again inside Phase 6's own
task list) before its scope was actually correct. Building an explicit
"re-verify live state" phase into the task file (rather than trusting the
design as ground truth) is what caught the third error; worth carrying that
pattern into future docs-only slices.

---

## 20260706 (1)

### Slice 303: Judge-Gated Cycle Conventions — Slice Design (Phase 4) Complete

Design document authored at `user/slices/303-slice.judge-gated-cycle-conventions.md`
on branch `300-planning.judge-gated-cycle-conventions`.

**Central finding:** the judge-gated review→fix→re-review cycle is expressible
today with **zero new code** — it is `loop` + a judge `review` step + `dispatch`
+ `checkpoint`, all pre-existing. Verified against the real constructs:
- `LoopCondition.REVIEW_PASS` / `REVIEW_CONCERNS_OR_BETTER` (`executor.py:215`)
  evaluate the last verdict — and a judge's verdict is the score's threshold
  projection (slice 301). So "gate on the score" needs no score-aware loop
  condition.
- `ExhaustBehavior.CHECKPOINT` (`executor.py:257`) → `PAUSED` StepResult is the
  observable escalation path when the bound (`loop.max`) is hit without clearing.
- The `review` step already accepts a step-level `judge:` threshold override
  (`steps/review.py`) — so **advisory-only = `pass_floor > 100`**, a value not a
  flag. No new "always-escalate" field.
- `test-loop.yaml` already ships the exact `loop [dispatch, review] until:
  review.pass` shape with a *standard* review; the delta to a judge cycle is the
  template name and `on_exhaust: checkpoint` — data only.

**Deliverables the slice defines (for Phase 6):**
- `data/pipelines/judge-cycle.yaml` — worked reference pipeline (judge-first
  shape: pre-loop judge, then `loop [fix, judge]`, `until: review.pass`,
  `on_exhaust: checkpoint`), gating on `judge.slice-vs-arch`.
- Structural + three control-flow tests (auto-advance, escalate-at-max,
  advisory-always-escalates) with a mocked judge score to prove the flow
  deterministically; one live unattended run to validate the fix prompt.
- Authoring-guide section covering the bound, exit condition, escalation, the
  two gating modes, and the optional `commit` body step.

**Scope boundaries recorded:** gate composition (judge + review verdict) is
slice 304; multi-sample judging is Future Work 1; new `each` sources are out of
scope (only `cf.unfinished_slices` is registered).

**Branch:** `300-planning.judge-gated-cycle-conventions` (created from `main`).

**Next:** Phase 5 (Task Breakdown) for slice 303, then Phase 6 implementation on
`303-slice.judge-gated-cycle-conventions`.

---

## 20260705 (4)

### Slice 302: Design-Phase Judge Templates — Implementation Complete

All 11 tasks (T1–T11) implemented on branch `300-planning.design-phase-judge-templates`.

**What was built:**
- `data/templates/judge-tasks-vs-slice.yaml` — judge variant of `tasks.yaml`; reuses its evaluation criteria verbatim, swaps the output contract to score+rationale+findings, forbids a verdict summary. `judge: {pass_floor: 78, concerns_floor: 55}`.
- `data/templates/judge-slice-vs-arch.yaml` — judge variant of `slice.yaml`, same pattern. `judge: {pass_floor: 82, concerns_floor: 60}` (higher floor — architecture alignment is more interpretive ground truth than a concrete task list).
- `review/template_inputs.py` — two new `TEMPLATE_INPUTS` entries (`judge.tasks-vs-slice`, `judge.slice-vs-arch`), reusing the existing `_tasks_input`/`_design_file`/`_arch_file` source functions unchanged. No prefix-stripping fallback (rejected in the slice design as reintroducing naming-convention dispatch).

**No engine/parser/action changes** — both templates run through the unmodified `ReviewAction._review()` → `run_review_with_profile()` → parser → `enforce_judge()` path built in slice 301/300.

**Tests:** 8 new/extended tests across `test_templates.py` (load + is_judge + threshold differentiation regression guard), `test_template_inputs.py` (resolution + exact-keyset regression), and `test_review_action.py` (T7: rogue model-emitted verdict discarded — confirms `enforce_judge()` never reads `result.verdict`; T8: `TEMPLATE_INPUTS` resolution failure surfaces as `UNKNOWN`/`provenance=judge` via the existing exception handler, not a silent skip). Both new-to-this-slice failure modes needed no new handling code — only new test coverage confirming slice 301's mechanisms already cover them.

**Live-provider verification (T9/T10):** ran both templates against real in-repo artifact pairs via `run_review_with_profile()` directly (openrouter profile, `anthropic/claude-opus-4.5` — the `sdk` profile can't launch from inside an active Claude Code session). `judge.tasks-vs-slice` scored 91.0 reviewing this slice's own task file against its slice design; `judge.slice-vs-arch` scored 86.0 reviewing this slice's design against its architecture doc. Neither run emitted a `## Summary`/verdict line; both produced well-formed `criteria` maps and findings. No prompt revision needed. The slice-vs-arch score (clears `pass_floor=82`) is consistent with the design's already-fixed review findings — the committed human review's `CONCERNS` verdict predates the `d69ee7e` fixes to failure-mode enumeration.

**Full validation:** 2080 passed / 2 skipped (pre-existing, unrelated), `pyright` 0 errors, `ruff check`/`format` clean, `sq review list` shows all 6 templates, no `template_name.startswith("judge.")`-style dispatch found in non-test code.

**Unblocks:** slice 303 (judge-gated cycle conventions) now has two real judges to compose into a pipeline.

---

## 20260625

### Slice 342: Analysis Pack (Bundled) — Task Breakdown Complete

Authored `342-tasks.analysis-pack-bundled.md` (12 tasks, 122 lines).

Task sequence: branch/prereq check → data package + skills.toml → extend `load_effective()` → tests → commands/analysis/ + commands/sq/analysis.md → commit checkpoint → two CLI smoke tests → integration test → full validation → final commit.

**Pending unblock:** `tech-debt-analyze.md` skill content needed from Project Manager (T5); placeholder acceptable to unblock T6–T12.

---

### Slice 342: Analysis Pack (Bundled) — Design Complete

Authored `342-slice.analysis-pack-bundled.md`.

**Key decisions:**
- Shipped default `skills.toml` at `src/squadron/data/skills.toml` acts as base layer in `load_effective()` — users see the `analysis` pack in `sq skills list` with no manual manifest setup.
- `commands/analysis/` covered automatically by the existing `force-include` wheel rule; no `pyproject.toml` changes needed for commands.
- `src/squadron/data/` package added via `__init__.py` for `importlib.resources` resolution.
- `commands/sq/analysis.md` dispatcher wired into the existing `sq install-commands` path (not `sq skills install`) for `/sq:analysis <skill>` dispatch.
- `tech-debt-analyze.md` content is an external input (existing forked skill); placeholder acceptable to unblock packaging.

**Only code change:** `manifest.py`'s `load_effective()` gains a base-layer step to load the shipped default. Everything else is new files.

**Pending:** Project Manager to supply or confirm `tech-debt-analyze.md` skill content before implementation begins.

---

### Slice 341: Manifest Format and `sq skills install/list` — Implementation Complete

All 14 tasks implemented on branch `341-slice.manifest-format-and-sq-skills-install-list`.

**What was built:**
- `squadron/skills/models.py` — `PackEntry` (Pydantic, validates exactly-one-surface), `InstallResult` (dataclass), `SkillSourceError`
- `squadron/skills/manifest.py` — `load()`, `merge()`, `load_effective()`; `ValidationError` from malformed pack entries is caught and re-raised as `ValueError` with path context
- `squadron/skills/resolver.py` — `resolve_source()`: bundled (importlib.resources), absolute/relative path, `github:` (shallow clone via subprocess+git)
- `squadron/skills/installer.py` — `install_pack()`: copies `.md` files to `commands_dir/<prefix>/` or `commands_dir/sq/<dispatch_file>.md`
- `cli/commands/skills.py` — `skills_app` Typer sub-app with `install` and `list` commands; Rich table for list; catches `SkillSourceError` and `ValueError` at CLI boundary
- `app.py` — wired `skills_app` via `add_typer`

**Tests:** 35 tests in `tests/skills/` (models, manifest, resolver, installer, CLI). All pass. 1 network-gated test (GitHub clone) skipped by default.

**One design correction during implementation:** `_USER_MANIFEST` and `_PROJECT_MANIFEST_NAME` renamed to public `USER_MANIFEST` / `PROJECT_MANIFEST_NAME` (pyright strict rejects cross-module use of private names).

**Commits:** `cdeb3a1` (subpackage foundation) + `b60ecd5` (installer, CLI, wiring).

---

### Slice 341: Manifest Format and `sq skills install/list` — Task Breakdown Complete

Authored `341-tasks.manifest-format-and-sq-skills-install-list.md` (14 tasks, 130 lines).

**Task sequence summary:**
- T1–T2: `skills/models.py` (`PackEntry`, `InstallResult`, `SkillSourceError`) + tests
- T3–T4: `skills/manifest.py` (`load`, `merge`, `load_effective`) + tests
- T5–T6: `skills/resolver.py` (bundled / local / github source resolution) + tests
- T7: Commit checkpoint — subpackage foundation
- T8–T9: `skills/installer.py` (file-copy install for prefix and dispatch_file) + tests
- T10–T11: `cli/commands/skills.py` (Typer `install`/`list` sub-app) + wire into `app.py`
- T12: CLI integration tests via Typer CliRunner
- T13–T14: Full validation pass + final commit

**Pending:** PM approval, then Phase 6 implementation.

### Slice 341: Manifest Format and `sq skills install/list` — Design Complete

Authored `341-slice.manifest-format-and-sq-skills-install-list.md`. Slice plan entry updated with materialized index and doc link.

**Design decisions committed:**

- **Manifest location:** User-level at `~/.config/squadron/skills.toml`; project-level at `<cwd>/.squadron/skills.toml`. Merge rule: additive union — project-level entries extend user-level; same-named pack in project-level wins.
- **Schema:** Each pack entry has `source` (one of `"bundled"`, absolute/relative path, `"github:<org>/<repo>"`) and exactly one of `prefix` or `dispatch_file`. Both or neither is a validation error at load time.
- **Source resolution:** `"bundled"` → `importlib.resources` (same pattern as `_get_commands_source()`); local path → direct; `github:` → shallow `git clone --depth=1` to temp dir, copy `.md` files, discard. No version pinning in v1.
- **Install semantics:** Additive within a pack's prefix directory (no deletion of pre-existing files not from the pack — that is `uninstall`'s job). Idempotent: second install overwrites files, reports success, no error.
- **No manifest auto-creation:** Missing `skills.toml` produces an actionable message; we do not silently create a default file.
- **Component structure:** New `squadron/skills/` subpackage (`manifest.py`, `resolver.py`, `installer.py`, `models.py`) with thin Typer layer at `cli/commands/skills.py`. `skills_app` added to `app.py` via `add_typer`.
- **Pydantic for manifest model**; `tomllib` (stdlib) for parsing; `subprocess` + `git` for GitHub fetch; no new third-party dependencies.

**Pending:** Phase 5 task breakdown, then Phase 6 implementation.

---

## 20260617

### Slice 301: Judge Enforcement Layer — Design Complete

Authored `301-slice.judge-enforcement-layer.md`. No commits (design-only phase).

**Design decisions committed:**
- Judge templates identified by presence of a `judge:` YAML block (not naming convention — project rule forbids string dispatch). Block carries default `pass_floor`/`concerns_floor` thresholds.
- `ReviewTemplate.judge: dict[str, object] | None` + `is_judge` property; `JudgeThresholds` and enforcement logic live in a new `pipeline/actions/judge.py`, keeping the template model a thin data carrier.
- `enforce_judge()` is a pure function (logger injected); independently testable without action context.
- Provenance set for ALL results from this slice forward: `"judge"` for judge templates, `"review"` for standard templates — completing the self-describing guarantee from 300.
- Exception path (provider down, missing inputs) for judge templates returns `verdict="UNKNOWN"` rather than `verdict=None`, so checkpoints fire correctly.
- Conservative defaults: `pass_floor=75`, `concerns_floor=50` (constants in `judge.py`).
- Step-level override via `judge: {pass_floor: N}` in pipeline YAML; passed through from `ReviewStepType.expand()` to action params.

**Pending:** PM review of design before task breakdown (Phase 5).

---

## 20260531

### Initiative 300 scope reduction + Initiative 320 + orchestrator Future Work — Design

Major rethink after a review (GLM-5.1, CONCERNS) and an extended PM/architect design conversation. The 300 arch doc had spiraled toward over-engineering; pulled it back to what's actually needed, and split the rest into a sibling initiative and a far-future Future Work entry.

**The "why" (captured for future context — this is the motivation behind 300/320 and the orchestrator):**
Squadron is an excellent *deterministic workflow engine* running a *non-deterministic process*. High accuracy, decent-but-variable code quality, and an external quality standard now exists to measure against (a forked MIT `tech-debt-audit` Claude skill, adapted for squadron projects, which surfaces plenty of issues). In return for high accuracy it demands human-in-loop at too many gates — rarely at code, sometimes extensively at *design* — heavy enough that simple projects aren't worth the overhead. The automation breaks precisely at the **decision points**, because those are non-deterministic. LLM judgment at those points is the missing piece. (Origin: the CCA training + two interviews surfaced the eval gap; adding it makes squadron feel "complete"/legit — a workflow engine without eval is a car without a speedometer.)

**Determinism/leverage ladder (the framing that resolved where agentic loops belong):**
1. Now — high-accuracy, high-effort workflow engine (human at every gate).
2. 300/320 — judge-at-decision-points; trade some accuracy for far less effort; variability accepted but kept minimal.
3. Future — an orchestrator agent driving CF+squadron, human consulted only on hard calls; another leverage jump.
Organism metaphor: CF structures = stable skeleton; LLM judges/orchestrator = nervous system (joints absorbing variability, making local decisions); human = consulted only where it matters. **Agentic loops belong ONLY at rung 3, above the engine — never inside a pipeline action.** The doc kept spiraling because it tried to put a rung-3 turn-loop inside a rung-2 action (the read-file capability). Removing that dissolved the circularity.

**Initiative 300 — reduced and renamed → "Intrinsic LLM Judging & Scoring".**
Now two reuse-first capabilities only: (1) an optional 0–100 numeric **score** added additively to result models/parser/persistence (keystone slice, done first), verdict *derived from* score by threshold (score = source of truth, verdict = its projection for `--step-done --verdict`), optional `criteria` map reserved from the start; (2) an **intrinsic judge** = the *existing* `review` action with a judge system-prompt emitting score+findings, composing with *existing* `each`/`loop`/`commit` for unattended review→fix→re-review. Ground truth is **in-repo** (parent doc, rules, code, phase criteria) — no external answer key. Prioritize design-phase gates (slice-vs-arch, tasks-vs-slice). **Dropped from 300:** the `eval:judge` action (duplicative of `review`), reference datasets, per-case dataset loop, read-file/turn-loop, fan-in aggregation. Arch doc fully rewritten; `status: not_started` (needs fresh review against reduced scope). Second-review findings re-dispositioned: F001/F002/F006/F007 fixed & carried forward, F003/F004/F005 removed from scope, F008 retained as a slice-design caveat.

**Reference datasets — ruled out (not deferred scope, a different product).** Curated input/expected pairs to grade a model in the abstract. Poor fit here: prompts are complex, outputs non-deterministic (valid solutions vary), and ground-truth strength is a *gradient* — strong for tasks-vs-slice, minimal for arch-concept-vs-initiative-blurb. Squadron's judging needs none of it; its ground truth is the project's own documents.

**Initiative 320 (new) — "Judge Calibration & Quality Metrology".** Answers "how good are the judges themselves?" Ground truth = **the human, sampled**: operator spot-checks a sample of judge verdicts; system reports judge-vs-human agreement + judge-vs-judge dispersion ("does model X overreach while Y rubber-stamps?"). Trust is per-artifact-level (scales with in-repo ground-truth strength) and feeds 300's escalate-vs-auto-gate decision. Includes the **tech-debt-audit code-quality baseline** + a dispatch-side **prompt-chaining pre-emption** prompt (chained because the current one is already complex) as the first measurable customer (audit-findings-per-project should drop). Two oracles, same metrology shape: tech-debt-audit (code), human-sampled agreement (design). Depends on [100, 140, 300]. Overview/rough-concept captured in the initiative-plan entry; full design in coming weeks.

**Orchestrator — Future Work entry.** The rung-3 organism; named to keep its agentic loop from being smuggled back into 300-band components. Promote to a full initiative when pursued.

**Index spacing:** initiatives now spaced by 20 (300, 320). 310 intentionally skipped.

**Delivered:** rewrote `300-arch.eval-actions-llm-as-judge-scoring.md`; updated `001-initiative-plan.squadron.md` (300 entry slimmed, 320 added, Future Work section added, cross-deps + dateUpdated); re-dispositioned `300-review.arch...md`.

**Pending:** fresh review of slimmed 300; `/cf:prompt get add-initiative-overview` already applied to capture 320 as a plan entry — a standalone 320 concept doc was not created (project has no concept-doc convention; the plan entry + this DEVLOG are the durable capture). All planning edits remain uncommitted on branch `908-sq-setup-one-call-install-orchestrator`.

---

## 20260530

### Initiative 300: Eval Actions (LLM-as-Judge & Scoring) — Design Complete

Stood up a new initiative and authored its architecture document. Adds an `eval` action family that gives squadron's deterministic executor a judgment-and-measurement layer.

**Delivered:**
- Initiative 300 entry added to `001-initiative-plan.squadron.md` (index 300, after 280; dependencies [100, 140]); cross-initiative dependency entry and `dateUpdated` refreshed.
- `300-arch.eval-actions-llm-as-judge-scoring.md` created and registered (`cf set arch 300`).

**Component shape.** `eval:judge` is LLM-as-judge: reuses the existing provider-agnostic review engine (`run_review_with_profile`) with a judge system-prompt and reference-dataset inputs, emitting a **0–100 scalar score + verdict + findings**. The verdict drops into the existing `sq run --step-done --verdict` checkpoint machinery with no new plumbing.

**Key decisions:**
- **Initiative, not a single slice** — because numeric scoring is a cross-cutting change to result models every pipeline depends on, reference-dataset eval is new infrastructure, and eval/review gate composition is an open arch question.
- **Keystone slice first:** numeric scoring foundation (add `score` *alongside* verdict, additive/backward-compatible, verdict stays authoritative at summary level). Isolated and done first to de-risk the model migration.
- **Scalar summarizes a latent criterion vector** — scalar consumed now, vector recorded but not surfaced.
- **Read-file-on-request tool** for non-SDK judges is owned by this initiative (the canonical minimal one), but is a **secondary, later slice** — explicitly *not* dependent on 260's full agentic loop (260 may consume it later).

**Grounding (verified against source this session):** action registry is open (`register_action`); `ActionResult` already carries `verdict`/`findings`; verdict enum `PASS|CONCERNS|FAIL|UNKNOWN` is exactly what `--step-done --verdict` consumes; provider/model support comes from the profile registry; the 500KB injection cap is the binding constraint on non-file-reading judge models.

**Pending / open (for slice design):** dataset format & location convention; scalar score range vs. per-criterion schema detail; eval/review gate-composition policy (combined / separate / per-review-type).

**Note:** these are planning-doc edits made on branch `908-sq-setup-one-call-install-orchestrator`; not yet committed.

---

## 20260514

### Initiative 200: Multi-Agent Communication — Architecture Rewrite

Rewrote `200-arch.multi-agent-communication.md` and `200-slices.multi-agent-communication.md` to reflect a fundamentally different model from the original pub/sub message bus design.

**Why:** IDE plugins (Claude Code, Codex) and interactive sessions are reactive — they cannot receive async push. The original bus model assumed agents could be woken up; they can't. The new model is pull-based: a shared SQLite task store owned by the daemon, agents poll for work, claim atomically, complete via daemon socket.

**New model summary:**
- Daemon (`sq serve`) owns `workspace.db` (SQLite, WAL mode), listens on Unix socket
- `sq run` posts tasks via socket, polls DB read-only for results — no more SDK session spawning from CLI
- Claude Code IDE participates via `/sq:work` slash command + MCP tools
- Codex IDE plugin: same poll/claim/complete loop, capability-routed
- Hermes (remote machine): connects to local daemon via SSH tunnel, same socket protocol
- Project isolation via `project_path` column — one daemon, one DB, multiple projects

**Dropped from original 200-series:** Supervisor (OTP restart patterns), Message Bus Core, Multi-Agent Message Routing, Human-in-the-Loop as bus participant, Communication Topologies, ADK Integration, REST+WebSocket, Subprocess Agent Support.

**Retained/adapted:** 203 (Anthropic API Provider, standalone, unchanged), 208→224 (MCP tools, repurposed for poll/claim), 210 (Ensemble Review, unchanged), 212→228 (E2E testing, rescoped).

**New slices:** 221 (Task Store schema), 222 (Daemon Socket Server), 223 (Pipeline Executor Integration), 224 (MCP Tools), 225 (/sq:work slash command), 226 (Capability Routing), 227 (sq work Hermes worker CLI).

**June 15 relevance noted:** Slices 203 + 223 together eliminate the Agent SDK credit dependency for `sq run` pipeline steps. Prioritized in implementation order notes.

## 20260513

### Slice 906: Quickstart and Onboarding Documentation — Phase 4 Slice Design

Authored `user/slices/906-slice.quickstart-and-onboarding-documentation.md`.

Scope: docs-only. Two deliverables — new `docs/QUICKSTART.md` (step-by-step from
zero to working `sq run`) and targeted README edits (Quickstart → pointer, Install →
keep global-install block only).

Key design decisions:
- QUICKSTART is structured as numbered install steps matching the `sq doctor` fix-hint
  contract: every hint emitted by doctor maps to a named QUICKSTART section. This
  mapping is documented in the slice design as a stable interface.
- Provider matrix table derived from `BUILT_IN_PROFILES` — covers sdk, openai,
  openrouter, gemini, local, openai-oauth (experimental), and Anthropic API (planned,
  slice 203).
- README Quickstart section replaced with ~3 lines + link; dev-install block moves
  to QUICKSTART under a contributing subsection.
- No code changes. Effort 1/5.

### Slice 905: `sq doctor` — Phase 6 Implementation Complete

Completed full implementation of `sq doctor` in a single session across 35 tasks.

Two new files: `src/squadron/cli/commands/doctor_checks.py` (~280 lines, pure check
functions + `run_all_checks()`) and `src/squadron/cli/commands/doctor.py` (~120 lines,
Typer command + Rich/JSON rendering). One edit to `cli/app.py` to register the command.

Key implementation decisions:
- Module-level imports for `get_all_profiles`, `providers_toml_path`, `models_toml_path`
  (not lazy inside functions) — required for test patching to work correctly.
- `Console(soft_wrap=True)` for path-heavy detail strings that exceed terminal width.
- `_API_KEY_ONLY_PROFILES` fixture in integration tests because `sdk`, `local`,
  `openai-oauth` profiles return `is_valid()=True` unconditionally — a fresh-system
  env var wipe doesn't actually leave zero valid providers. The fixture simulates
  a minimal env with only API-key-based profiles for the "fresh-system → exit 1" scenario.
- Scenario 3 (broken providers.toml) produces two error signals: `get_all_profiles()` 
  raises before per-profile checks run (process-boundary handler emits WARN), then 
  `check_providers_toml()` independently emits the MISSING row. Both correct; both informative.

Tests: 35 doctor tests added; full suite 1904 passing, 2 skipped (pre-existing). Ruff/pyright clean.

Branch: `905-sq-doctor-environment-diagnostic-command`. Not yet merged.

### Slice 905: `sq doctor` — Phase 5 Task Breakdown

Authored `user/tasks/905-tasks.sq-doctor-environment-diagnostic-command.md`
(35 tasks across four phases: setup/data-model, individual checks,
orchestration/rendering, final integration).

Test-with pattern applied throughout — every implementation task is
immediately followed by its test task (T4→T5, T6→T7, T8→T9, etc.), no
batched test phase. Each check function gets its own implementation +
test pair so failures surface against a small surface area.

Phase A (T1–T3) bootstraps the branch, skeleton files, and the
`CheckResult`/`CheckStatus` data model. Phase B (T4–T23) implements the
10 individual check functions. Phase C (T24–T30) wires orchestration,
Rich + JSON rendering, the Typer command, and 6 CliRunner integration
tests. Phase D (T31–T35) is the gate (pytest/ruff/pyright), manual
scenario verification mirroring 904's recorded-outcomes pattern,
CHANGELOG, commit, and slice closure.

Notable choices:

- Provider profile tests use real `monkeypatch.setenv` against the real
  auth registry — not mocked `resolve_auth_strategy_for_profile`. We're
  testing integration with the actual auth strategies, not a fake.
- TOML config checks distinguish absent (informational OK) from
  malformed (MISSING). Repairing the file is the fix hint.
- Process-boundary catch in `run_all_checks()` wraps each check call;
  one broken check emits a synthetic WARN row instead of aborting.
- Top-level command body raises `typer.Exit(exit_code)`. Exit 1 iff any
  MISSING row exists; WARN never affects exit code.

Status: not_started · 35 tasks · 219 lines.

---

### Slice 905: `sq doctor` Environment Diagnostic — Phase 4 Slice Design

Authored `user/slices/905-slice.sq-doctor-environment-diagnostic-command.md`.
Design covers a read-only `sq doctor` subcommand that orchestrates pure
check functions over existing inspection targets — `get_all_profiles()`,
`resolve_auth_strategy_for_profile()`, `providers_toml_path()`,
`models_toml_path()`, `shutil.which("cf"|"codex")`, Claude Code env-var
presence — and renders a Rich table (default) or JSON (`--json`).

Key decisions:

- Two new files: `cli/commands/doctor.py` (Typer command + rendering) and
  `cli/commands/doctor_checks.py` (pure synchronous check functions
  returning a `CheckResult` dataclass). Separation keeps checks unit-
  testable without Typer.
- "Apparent intent" inference is deferred. Required checks are only those
  that block all Squadron use (the package itself, at-least-one provider
  authenticated, parseability of any user-supplied `providers.toml` /
  `models.toml`). Provider-specific and integration-specific rows are
  WARN. Exit 1 iff any MISSING row.
- WARN rows are hidden by default; surface via `-v`. JSON output always
  includes all rows.
- No network calls. Auth correctness against the wire remains
  `sq auth login`'s job. Doctor reports "authenticated locally" — not
  "will work."
- Failure-mode enumeration is explicit for every I/O point (malformed
  TOML, missing HOME, stale `which` results, unexpected profile shape,
  `PackageNotFoundError` for dev installs). Every catch logs at WARNING
  per project rules.

Pairs with slice 906 (Quickstart docs) — `fix_hint` strings are the
contract 906 will reference verbatim.

Status: not_started · Effort: 2/5 · Risk: Low · Dependencies: none.

---

## 20260507

### Slice 243 follow-up: classify_pipeline missed phase-step dispatches (commit aef3b41)

Discovered while testing slice 246's `--explain` against P4: the classifier
returned a single non-SDK row (the summary step), reporting P4 as
Claude-free even though P4's `design` step dispatches with the default
`model: sonnet` (SDK).

**Root cause:** `_MODEL_DISPATCHING_STEP_TYPES` in `classification.py`
gated on raw step-type names (`dispatch`/`review`/`summary`/`compact`).
Phase step types (`design`/`tasks`/`implement`) expand into those
actions via `StepType.expand()` but their step-type name doesn't match,
so the classifier silently skipped them. The same gap also affected the
embedded review block under a phase step.

**Fix:** Classifier now walks `StepType.expand()` and classifies each
emitted model-dispatching action. Action configs run through
`resolve_placeholders` against pipeline-default params so `{model}`-style
templates resolve to their concrete alias before cascade lookup. Two test
fixtures for standalone review steps were updated to include the required
`template` field.

**Known limitation (out of scope here):** `each`, `loop`, and `fan_out`
step types return `[]` from `expand()` — their inner model dispatches are
still uncovered by classification. These are handled directly by the
executor; a future slice should either teach those step types to surface
their inner dispatches, or extend the classifier to introspect them.

---

## 20260506

### Slice 246: Auth-Classification Diagnostics CLI — Complete (commit ec72fab)

All 9 tasks implemented in a single pass on branch `246-slice.auth-classification-diagnostics-cli`.

**Changes:**
- `src/squadron/cli/commands/run.py` — Added `--explain` flag, `_render_explain`, `_handle_explain`, `_extract_model_override`, `_SHAPE_LABELS` constant, `_STEP_CLASS_COLORS` constant, mutual-exclusivity guards (5 incompatible options), and dispatch branch. All confined to this file; no new modules.
- `tests/cli/commands/test_run.py` — Added `TestExplainMutualExclusivity` (5 tests) and `TestExplainCommand` (8 tests). Total test count: 1863 passing.

**Verification findings:**
- `uv run sq run p6 --explain` and `uv run sq run implement --explain` work correctly.
- `test-compact-compose` has a misconfigured `summary-2` step with no model at any cascade level — `--explain` correctly raises `ClassificationError` for it. Verification walkthrough updated to use `p6` and `implement` instead.
- Pre-existing integration test failures (2 in `test_compact_compose_integration.py`) are unrelated and present on `main` before this branch.

**Quality gates:** ruff format ✓, ruff check ✓, pyright ✓ (3 pre-existing errors), pytest 1863 passed.

---

### Slice 246: Auth-Classification Diagnostics CLI — Task Breakdown Complete

No commits (planning-only phase).

Created `project-documents/user/tasks/246-tasks.auth-classification-diagnostics-cli.md` (173 lines, 9 tasks).

**Task sequence:** Flag declaration (T1) → mutual-exclusivity guard (T2) → guard tests (T3) → `_render_explain` renderer (T4) → `_handle_explain` handler (T5) → wire dispatch branch (T6) → happy-path tests (T7) → error-path tests (T8) → quality gates + commit (T9).

All changes confined to `src/squadron/cli/commands/run.py` and `tests/cli/commands/test_run.py`. No new modules. Dependencies (classify_pipeline, PipelineClassification, all related enums) fully stable.

**Ready for Phase 6 (Implementation).**

---

## 20260505

### Slice 246: Auth-Classification Diagnostics CLI — Design Complete

No commits (design-only phase).

Created `project-documents/user/slices/246-slice.auth-classification-diagnostics-cli.md`. Updated slice plan entry (240-slices) to reference the design document and pin the flag name as `--explain`.

**Decisions:**
- Flag name `--explain` (over `--classify`, `--auth-check`) — most natural for the "explain to me why this needs Claude auth" user intent.
- No new module; all changes land in `cli/commands/run.py`: new `--explain` flag, `_handle_explain`, and `_render_explain`.
- `--explain` accepts `--model`, `--param`, `--strict`, and `--verbose`; rejected alongside execution options (`--resume`, `--dry-run`, `--from`, `--prompt-only`, `--validate`).
- Resolver construction duplicates `_run_pipeline_sdk`'s `_classify_resolver` block intentionally — deferred to a `_build_classification_resolver` helper only when a third call site appears.
- No `--json` output in this slice; trivial to add as a maintenance task later.
- Rich table for per-step output (matches existing CLI conventions); summary panel below.

**Ready for Phase 5 (Task Breakdown) and implementation.**

---

### Initiative 260: Non-SDK Agent Tool Use — Architecture and Slice Plan Complete

Commits `0d94d7b` (arch + slice plan), `0c19515` (arch review).

**Context:** Triggered by observing that `test-p4.yaml` with `model: kimi25` fails silently — the model emits raw tool-call XML into the response stream because `OpenAICompatibleAgent` never passes `tools` to the API and has no execution loop. Confirmed via code audit that `allowed_tools`, `permission_mode`, and all tool-related `AgentConfig` fields are silently ignored by non-SDK providers.

**Architecture (`260-arch.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md`):** Agentic loop inside `OpenAICompatibleAgent._run_agentic_loop` (structured for future lift-out). Tool descriptor protocol: name, description, JSON Schema parameters, `cwd`-injecting factory, async executor returning `ToolResult(content, is_error)`. Process-level tool registry (`register`/`lookup`/`materialize`). Core tools: `read_file`, `write_file` (CWD-scoped), `bash` (CWD working directory; network/env/fork unrestricted at this stage — documented scope). Reuses existing `AgentConfig.allowed_tools` field with non-SDK semantics; empty by default, opt-in per pipeline step. Max-iterations guard + character-count token-budget threshold. Streaming contract: intermediate turns DEBUG-logged only; final turn streams normally. Arch review (GLM-5.1, CONCERNS) addressed in same session: F001 false "no network" claim fixed; F002–F008 covered by new Technical Considerations subsections (descriptor protocol, cwd injection, async-first interface, token budget, streaming contract, content+tool_calls co-occurrence).

**Slice plan (`260-slices.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md`):** 5 slices. Critical path: 261 (tool registry + core tools, Effort 2/5) → 262 (agentic loop, Effort 3/5) → 263 (dispatch wiring + YAML surface, Effort 2/5). Deferred: 264 (CF MCP bridge), 265 (review/summary coverage).

**Decision:** Initiative 260 shelved pending completion of initiative 240 (4 slices remaining: 246–249). Will resume 260 after 240 is closed.

## 20260504

### Slice 245: Pool-Resolution Classification Policy and Mid-Run Session Construction — Complete

Commit `be0138c`. 10 files changed, 947 insertions.

**Delivered:**
- `PoolClassificationPolicy` enum (`LAZY`/`STRICT`) in `classification.py`; `PipelineClassification` stores policy; `needs_persistent_session` evaluates `POOL_UNCERTAIN` against policy — LAZY skips it, STRICT counts it.
- `classify_pipeline()` gains optional `policy=PoolClassificationPolicy.LAZY` param.
- `PipelineDefinition.auth_policy: str | None` and `PipelineSchema.auth_policy` with validator (accepts `"lazy"`, `"strict"`, or `None`).
- `execute_pipeline()` gains `pool_policy` param; mid-run lazy hook connects `SDKExecutionSession` just before the first step whose candidate statically resolves to an SDK alias. `_step_needs_sdk()` and `_connect_lazy_session()` are private helpers.
- `LazySessionConnectError` exception carries step name; caught in `_run_pipeline_sdk` which prints a user-facing red message with `--strict` guidance and raises `typer.Exit(1)`.
- `DispatchAction._dispatch` guard: when `sdk_session is None` and the resolved alias has an explicit `'sdk'` profile (pool selected an SDK alias at runtime), returns FAILED with `--strict` hint. `None` alias_profile (no explicit profile) still routes through the one-shot agent safely.
- `sq run --strict` flag; YAML `auth_policy: strict` support; policy resolution precedence: LAZY → YAML strict → CLI `--strict`.
- `PERSISTENT_SESSION_STEP_TYPES` renamed public (was `_PERSISTENT_SESSION_STEP_TYPES`) to avoid pyright `reportPrivateUsage`.

**Tests:** `tests/cli/commands/test_run_pipeline_lazy.py` (new, 18 tests); expanded `test_classification.py` (+12 tests); `test_schema.py` (+4 tests); `test_dispatch.py` (1 updated). 1836 total passing, 0 new failures. ruff/pyright clean (3 pre-existing pyright errors from slice 244 unchanged).

**Key design decision (implementation):** Dispatch guard uses `alias_profile == ProfileName.SDK` (not `is_sdk_profile(alias_profile)`) because `is_sdk_profile(None)` returns True but `None` profile means "one-shot agent, safe without session". Only an explicit `'sdk'` profile signals that a pool selected a true SDK alias requiring a persistent session.

### Slice 243: Resolution Pre-Scan — Phase 6 Implementation Complete

Commit `e838898`. Changed files: `src/squadron/pipeline/classification.py` (new, 235 lines), `src/squadron/pipeline/resolver.py` (added `cascade_candidates()`; refactored `resolve()` to consume it), `tests/pipeline/test_classification.py` (new, 28 tests).

**`ModelResolver.cascade_candidates(action_model, step_model) -> tuple[str | None, ...]`** — returns the ordered cascade inputs (cli_override, action_model, step_model, pipeline_model, config_default) with no alias resolution and no pool selection. `resolve()` now iterates `cascade_candidates()` internally, making cascade ordering single-source. Existing 11 resolver tests pass unchanged.

**`classification.py`** — `classify_pipeline(definition, resolver, pool_backend) -> PipelineClassification`. Walks `definition.steps`; for each model-dispatching step (`dispatch`, `review`, `summary`, `compact`), calls `resolver.cascade_candidates()`, picks first non-None, then dispatches: non-pool candidate → `resolve_model_alias()` + `is_sdk_profile()` → `SDK_REQUIRED` or `NON_SDK`; pool candidate → walks `pool.models` statically → all-SDK collapses to `SDK_REQUIRED`, all-non-SDK to `NON_SDK`, mixed → `POOL_UNCERTAIN`. Non-model steps skipped; `step_index` preserves original pipeline position. Two failure modes raise `ClassificationError` explicitly: empty cascade and pool candidate without backend. `PipelineClassification` derives `needs_persistent_session` (dispatch/summary/compact SDK or pool-uncertain), `needs_one_shot_claude` (review SDK or pool-uncertain), and `shape` (`claude_required_persistent`, `claude_required_one_shot`, `claude_free`).

**Test coverage (28 tests):** spy-backend verification (T1), cascade ordering and resolve-consumes-candidates patch guard (T3), all 7 property isolation tests (T5), 9 non-pool path tests including step-index and F002 regression guards (T7), 5 pool path tests with zero-select assertions (T9), idempotency/side-effect-freeness regression (T10). ruff/pyright clean; full suite +28 new passing tests.

No executor changes. Pre-existing 2 failures in `test_compact_compose_integration` are unrelated and pre-date this slice.

### Slice 243: Resolution Pre-Scan — Phase 5 Task Breakdown Complete

Created [243-tasks.resolution-pre-scan.md](project-documents/user/tasks/243-tasks.resolution-pre-scan.md) (267 lines, 12 tasks). Task sequence: T1 creates test infrastructure (`SpyPoolBackend`, definition/resolver builders) before any implementation. T2 adds `ModelResolver.cascade_candidates()` and refactors `resolve()` to consume it (single-source cascade, resolves review F001). T3 tests `cascade_candidates` and the resolver refactor. T4 defines the dataclasses (`StepClass`, `PipelineShape`, `ClassificationError`, `StepClassification`, `PipelineClassification`) with the three `@property` methods. T5 tests the properties in isolation — includes direct F002 regression guard (`test_needs_one_shot_claude_false_for_sdk_dispatch_only`). T6–T7 implement and test the non-pool path. T8–T9 implement and test the pool path (pool-collapsing logic + `SpyPoolBackend` zero-select assertions). T10 adds the idempotency/side-effect-freeness regression test. T11 is the quality-gate and commit task. T12 closes the slice. No open questions; design is unambiguous.

### Slice 243: Resolution Pre-Scan — Phase 4 Slice Design Revision (review CONCERNS addressed)

Slice review at [243-review.slice.resolution-pre-scan.md](project-documents/user/reviews/243-review.slice.resolution-pre-scan.md) returned `CONCERNS` with two findings; both addressed in-place in the slice design (frontmatter `reviewIteration: 2`, `dateUpdated: 20260504`). **F001 (cascade duplication):** earlier draft proposed three read-only properties (`cli_override`, `pipeline_model`, `config_default`) on `ModelResolver` and reproduced the cascade ordering inside the classifier — leaving cascade logic in two places with a known divergence risk. Replaced with a single `ModelResolver.cascade_candidates(action_model, step_model) -> tuple[str | None, ...]` method returning the ordered cascade *inputs* (no alias resolution, no pool selection). `resolve()` is refactored in the same change to consume the new method internally so the two paths cannot drift; added `test_cascade_candidates_returns_ordered_inputs` and `test_resolve_consumes_cascade_candidates` regression guards. The "Resolver attribute coupling" risk is dropped (resolved by design). Non-goal updated: "no new *selection-performing* resolver entrypoint" (the side-effect-free accessor is permitted; selection is the prohibition). **F002 (`needs_one_shot_claude` semantics drift):** earlier draft defined the predicate as "any SDK-resolved or pool-uncertain step" — broader than arch §Envisioned State point 2, which scopes it to steps that route through the provider registry's one-shot ClaudeSDKAgent path. Tightened to: SDK-resolved review steps ∪ SDK-resolved dispatch-via-agent steps (the second set is empty in practice post-slice-242, included for arch-correctness). Added two new tests — `test_one_shot_excludes_persistent_session_steps` (dispatch+summary all Claude → `needs_one_shot_claude=False`, the direct F002 regression guard) and `test_one_shot_excludes_non_sdk_review`. Success criterion #4 expanded with explicit mixed-pipeline rows. Test count moved from ~14 to ~16. Five PASS findings (side-effect contract documentation, conservative pool default, failure-mode enumeration, scope discipline, 180-band boundary) acknowledged; no design changes for those.

## 20260503

### Slice 243: Resolution Pre-Scan — Phase 4 Slice Design Complete

Authored design at [243-slice.resolution-pre-scan.md](project-documents/user/slices/243-slice.resolution-pre-scan.md). Slice introduces a new `src/squadron/pipeline/classification.py` module exposing `classify_pipeline(definition, resolver, pool_backend) -> PipelineClassification`. The classifier walks `PipelineDefinition.steps`, reproduces the resolver's five-tier cascade in read-only form (so it can inspect candidates *before* selection commits), and emits a `StepClassification` per model-dispatching step (`dispatch`, `review`, `summary`, `compact`). Non-pool candidates resolve via `resolve_model_alias` (pure dict lookup); pool candidates classify structurally by walking `ModelPool.models` and applying `is_sdk_profile` to each — never invokes `pool_backend.select()`, never advances 180-band selection state. Two pipeline-level booleans derived per arch §Envisioned State point 2: `needs_persistent_session` (union over `dispatch`/`summary`/`compact` SDK-resolved steps, *excluding* reviews — they route through one-shot ClaudeSDKAgent), and `needs_one_shot_claude` (informational, any-step union). Three pipeline shapes surface: claude_required_persistent, claude_required_one_shot, claude_free. Conservative pool-uncertain default hard-coded for this slice; lazy policy is slice 245's job. Adds three read-only properties on `ModelResolver` (`cli_override`, `pipeline_model`, `config_default`) so the classifier reads via clean public surface, not name-mangled attrs. Failure modes: misconfigured step (cascade yields no candidate) raises `ClassificationError` at planning time; pool candidate without backend likewise. Side-effect-freeness contract documented and asserted by a spy-backend test (zero `select()` calls for double classification). Slice ships the classifier and 14 unit tests only — no executor wiring; slice 244 will gate `SDKExecutionSession` construction on `classification.needs_persistent_session`. Slice-plan entry now carries the design pointer; slice plan `status` advanced to `in_progress`. Risk: Low; Effort: 2/5.

### Slice 242: Profile-Aware Dispatch Router (pure CLI) — Phase 6 Implementation Complete

Commit `0dbe41a`. Changed files: `src/squadron/pipeline/actions/dispatch.py`, `tests/pipeline/actions/test_dispatch_routing.py`, `tests/pipeline/actions/test_dispatch_session.py`.

**What changed:**
- `dispatch.py`: Added `is_sdk_profile` import from `squadron.providers.profiles`. Added `_resolve_model(context)` helper that extracts the `action_model / step_model / resolver.resolve(...)` cascade. Rewrote `_dispatch` with three-branch profile-aware routing: no session → agent path; session + non-SDK profile → agent path; session + SDK or None profile → session path. `_dispatch_via_session` and `_dispatch_via_agent` retain their own inline resolve cascade unchanged.
- `test_dispatch_routing.py` (new): Five routing tests (T5a–T5e): session+non-SDK→agent, session+None→session, session+sdk→session, no-session→agent, mixed-pipeline-per-step. All pass.
- `test_dispatch_session.py`: Updated one assertion from `assert_called_once_with` to `assert_any_call` to reflect the documented double-resolve (routing call in `_dispatch`, then branch call in `_dispatch_via_session`).

**T10 verification walkthrough:** Unit tests T5a–T5e verify routing logic in isolation. Live end-to-end steps (Step 1 minimax via pure-CLI, Step 2 default Claude regression, Step 3 mixed pipeline) require a configured minimax alias and Claude auth; these are environment-dependent and were not executed in this session. Steps should be run manually before tagging a release. Step 4 (IDE axis unchanged) is covered by existing slice-170 tests.

**Quality gates:** ruff format clean, ruff check clean, pyright 0 errors. Full suite: 1769 passed (baseline 1764 + 5 new).

### Slice 242: Profile-Aware Dispatch Router (pure CLI) — Phase 5 Task Breakdown Complete

Created [242-tasks.profile-aware-dispatch-router-pure-cli.md](project-documents/user/tasks/242-tasks.profile-aware-dispatch-router-pure-cli.md) (222 lines, 10 tasks). Three implementation tasks: T1 adds the `is_sdk_profile` import, T2 extracts the `_resolve_model` helper, T3 rewrites `_dispatch` with the profile-aware three-branch routing. T4 verifies existing tests stay green. T5 creates a new dedicated `tests/pipeline/actions/test_dispatch_routing.py` with five routing cases (session+non-SDK→agent, session+None-profile→session, session+explicit-sdk→session, no-session→agent, mixed-pipeline per-step); `test_dispatch.py` at 412 lines would be too large for 5 additional tests. T6–T8 are quality gates (targeted test run, ruff+pyright, full suite expecting 1769+ passed). T9 commits; T10 closes out the slice. No open questions; design is unambiguous.

### Slice 242: Profile-Aware Dispatch Router (pure CLI) — Phase 4 Slice Design Complete

Authored design at [242-slice.profile-aware-dispatch-router-pure-cli.md](project-documents/user/slices/242-slice.profile-aware-dispatch-router-pure-cli.md). The slice closes the pure-CLI mirror of slice 170: when `sq run … --param model=<non-sdk>` runs through `_run_pipeline_sdk`, today's `DispatchAction._dispatch` routes purely on `context.sdk_session is not None` and silently misroutes non-SDK aliases to `session.set_model(...)` on a Claude session — the prompt is dispatched to Claude under the non-SDK model id. Design extracts a small `_resolve_model(context)` helper, branches on `is_sdk_profile(alias_profile)` (now imported from `squadron.providers.profiles` per slice 241), and routes non-SDK profiles to `_dispatch_via_agent` even when a persistent session exists. Default Claude path (profile `None` per the slice-241 `None → True` contract) and explicit `sdk` profiles continue through `_dispatch_via_session` unchanged. No session-construction changes — the persistent session still connects at startup; conditional construction is slice 244. Test plan covers five routing cases (session+non-SDK → agent, session+default-None → session, session+explicit-sdk → session, no-session → agent, mixed-pipeline per-step). Risk: Low; Effort: 2/5. Slice-plan entry materialized with the (242) index and design pointer; frontmatter dateUpdated bumped.

### Slice 241: is_sdk_profile Predicate Re-Homing — Phase 6 Implementation Complete

Mechanical refactor landed in commit 393af52: `is_sdk_profile()` now lives in `src/squadron/providers/profiles.py` (alongside `get_profile()`), with `__all__` updated to export it. Two production callers (`pipeline/prompt_renderer.py:23`, `pipeline/actions/summary.py:11`) and one test (`tests/providers/test_profiles.py`) import from the new home; the old definition and its predicate-test are deleted from `pipeline/summary_oneshot.py` and `tests/pipeline/test_summary_oneshot.py`. The 9-case parametric test (None, "sdk", 5 registered non-SDK profiles, "unknown-profile", "") covers the documented contract; `None` → `True` semantics preserved per arch iteration 3 (renderer/summary call sites depend on this; pre-scan layer in slice 243 will operate only on resolved profiles and never pass `None`). All 4 grep sentinels green: zero hits for the old import path, zero residual references in `summary_oneshot.py`, expected hits at the new home. Quality gates: ruff format clean, ruff check clean, pyright zero errors, full suite 1764 passed (one net-new test). Verification walkthrough re-run end-to-end against the landed commit; observed output matches documented expectations across steps 1–5 and 7. Foundation in place for slices 242–248. Note: the slice-plan summary line at `240-slices.pipeline-auth-boundary-flexibility.md:35` still narrates the original `None` → `False` contract; appended a pointer to the arch iteration-3 contract rather than rewriting the plan body.

---

## 20260502

### Slice 241: is_sdk_profile Predicate Re-Homing — Phase 5 Task Breakdown

Task file created at `user/tasks/241-tasks.is-sdk-profile-predicate-re-homing.md` (10 tasks, 158 lines). Sequenced as: T1 add predicate to `providers/profiles.py` → T2 add parametric test at new home → T3 update `prompt_renderer.py` import → T4 update `actions/summary.py` import → T5 remove predicate from `test_summary_oneshot.py` → T6 delete old definition from `summary_oneshot.py` → T7 grep sentinel verification → T8 quality gates → T9 commit → T10 slice closeout. Investigation confirmed `tests/providers/test_profiles.py` already exists (no `is_sdk_profile` tests yet) and `tests/providers/` directory is present — no `__init__.py` creation needed.

---

## 20260501

### Slice 241: is_sdk_profile Predicate Re-Homing — Phase 4 Slice Design

Drafted slice design at [241-slice.is-sdk-profile-predicate-re-homing.md](project-documents/user/slices/241-slice.is-sdk-profile-predicate-re-homing.md). Foundation slice for the 240-band initiative: promotes `is_sdk_profile()` from [pipeline/summary_oneshot.py:19-24](src/squadron/pipeline/summary_oneshot.py#L19-L24) to [providers/profiles.py](src/squadron/providers/profiles.py) with an explicit contract (returns `True` for `None` or `"sdk"`, `False` for every other registered profile and unknown strings; no I/O, no auth probe, pure read of the profile-name enum). Investigation found only **2 production importers** (not 3 as the slice plan estimated) — slice 170 added the predicate to the dispatch *renderer* but not the dispatch *router* (router branch is slice 242's work). 6-file mechanical refactor: new definition + new test file + 2 caller import updates + old definition removal + old test removal. No re-export shim — all callers update in the same PR. Slice plan entry updated with design-complete pointer.

### Initiative 240: Pipeline Auth-Boundary Flexibility — Phase 3 Slice Plan

Drafted slice plan at [240-slices.pipeline-auth-boundary-flexibility.md](project-documents/user/architecture/240-slices.pipeline-auth-boundary-flexibility.md). 8 slices in two groups: 1 foundation (241 predicate re-homing) + 7 features (242 dispatch router pure-CLI fix, 243 resolution pre-scan, 244 conditional persistent session construction, 245 pool-resolution policy + mid-run construction, 246 `sq run --explain` diagnostics CLI, 247 documentation, 248 adversarial test matrix). Each slice maps directly to addressed-CONCERN territory from the iteration-2 arch review: 241 → F006 ownership, 243 → F003/F004/F005 pre-scan correctness, 244 → F001 split classification + F007 resume policy, 245 → F002 mid-run mechanism. Conservative shipping order: 241 → 242 → 243 → 244 → 245 → 246 → 248 → 247. Aggressive parallel order with {242, 243} and {244, 246} as parallelizable groups also documented.

### Slice 170: Profile-Aware Dispatch Model Routing — Phase 6 Implementation Complete

All 15 tasks (T1–T15) implemented and committed. 1763 tests passing, zero ruff/pyright errors.

**What changed:**

- **`_render_dispatch` branches on resolved profile** (`prompt_renderer.py`): SDK/None profiles keep the current in-session path (`model_switch`, no command). Non-SDK profiles emit a `sq _dispatch-run` command with `--prompt-file {tmp_path}`, `--model`, `--profile`, and any non-internal params forwarded as `--param` flags. `model_switch` and `command` are mutually exclusive.
- **`one_shot_dispatch` helper extracted** (`dispatch.py`): Factored the agent-spawn sequence out of `_dispatch_via_agent` into a public module-level async function. `_dispatch_via_agent` becomes a thin caller. Token metadata was not consumed downstream and was dropped in the refactor.
- **`sq _dispatch-run` hidden subcommand added** (`cli/commands/dispatch_run.py`, `app.py`): Reads prompt from `--prompt-file`, resolves profile via `ModelResolver` if `--profile` omitted, calls `one_shot_dispatch`, prints to stdout. Errors always go to stderr before exit 1. Hidden from `sq --help`.
- **`commands/sq/run.md` dispatch section updated**: Branched on `command` field presence — non-SDK path writes temp file, replaces `{tmp_path}`, runs via Bash, cleans up. SDK/in-session path is the else branch (unchanged wording).
- **SDK synthetic-error fix** (`sdk_session.py`): In `SDKExecutionSession.dispatch`, after `translate_sdk_message`, checks `isinstance(sdk_msg, ResultMessage) and sdk_msg.is_error` before appending content. Raises `ProviderAPIError("SDK reported is_error=True: ...")` on the error path. Existing `_CLI_ERROR_PREFIX` text check in `_check_cli_error` preserved as backstop.

**Key decision:** `_one_shot_dispatch` renamed to `one_shot_dispatch` (no leading underscore) because pyright strict mode treats leading-underscore module-level names as private and the function is intentionally cross-module.

**Commits:** `9942161` refactor, `6000c42` feat renderer, `062191e` feat subcommand, `7545a7e` feat run.md, `32bc7f6` fix sdk error

**Issues logged:** None.

**Next:** Initiative 240 slice plan (pipeline auth-boundary flexibility), or Phase 6 on any pending slice.
Format: `## YYYYMMDD` followed by brief notes (1-3 lines per session).  This file differs from
CHANGELOG.md, in that this file is written from implementor perspective where CHANGELOG.md is
written from user perspective.

---

## 20260501

### Slice 170: Profile-Aware Dispatch Model Routing — Phase 5 Task Breakdown

Task file created at `user/tasks/170-tasks.profile-aware-dispatch-model-routing.md` (15 tasks, 360 lines).
Tasks cover: `_one_shot_dispatch` extraction from `_dispatch_via_agent`, `_render_dispatch` profile
branch fix, new hidden `sq _dispatch-run` subcommand, `commands/sq/run.md` dispatch-section update,
SDK `is_error` synthetic-error detection fix, full suite + type-check, verification walkthrough, and
slice closeout. Inline `--prompt` intentionally omitted from `_dispatch-run`; file-only via
`--prompt-file` matching the established convention for multi-KB assembled context.

---

## 20260428

### Initiative 240: Pipeline Auth-Boundary Flexibility — Phase 2 Architecture (review iteration 2)

Reviewed via slice-style review at [240-review.arch.pipeline-auth-boundary-flexibility.md](project-documents/user/reviews/240-review.arch.pipeline-auth-boundary-flexibility.md) (verdict CONCERNS, 6 concerns + 1 note). All addressed in arch doc revision: classification split into two distinct properties (`needs_persistent_session` vs `needs_one_shot_claude`) so review-only-with-SDK-reviews pipelines no longer pay persistent-session connect cost (F001); mid-run lazy-connect mechanism sketched in Envisioned State step 5a after verifying `ActionContext` is constructed per-action in `pipeline/executor.py:785` (F002); pre-scan pool handling clarified as static structural query against pool's alias list with no 180 API dependency (F003); pre-scan resolver instance must match runtime cascade including `--param` overrides (F004); resolver side-effect-freedom verified by inspection of `models/aliases.py:resolve_model_alias` and stated as documented contract (F005); `is_sdk_profile()` ownership promoted to `providers/profiles.py` with explicit contract (F006); resume policy under changed pipeline definitions stated explicitly — current resolution wins (F007).

### Initiative 240: Pipeline Auth-Boundary Flexibility — Phase 2 Architecture

Drafted [240-arch.pipeline-auth-boundary-flexibility.md](project-documents/user/architecture/240-arch.pipeline-auth-boundary-flexibility.md). Promoted from in-flight slice-170 work after recognising the actual scope: today's pipeline executor unconditionally constructs a `ClaudeSDKClient` at startup regardless of pipeline content, and the dispatch router has no profile branch — together these mean (a) any `sq run` from pure CLI requires Claude auth, (b) `sq run … --param model=<non-sdk>` for a dispatch step silently fails. Architecture names two distinct SDK-touching paths (persistent `SDKExecutionSession` vs. registry-spawned one-shot `ClaudeSDKAgent`) and treats them as separate auth surfaces, both intentional. Initiative owns: per-step auth classification via resolution pre-scan, conditional persistent-session construction, profile-aware dispatch routing in pure-CLI mode, pool-resolution classification policy (conservative-vs-lazy), and diagnostic CLI surface. Explicit non-goals: until-loop convergence, fan-out/fan-in aggregation, intra-loop compaction policy, conversation-vs-override-instruction routing for findings — all 180-band. One-shot Claude subprocess pooling documented as known cost, not optimised. Anticipated 6–10 slices. Initiative entry added to [001-initiative-plan.squadron.md](project-documents/user/project-guides/001-initiative-plan.squadron.md) at index 240; cross-initiative dependency line added.

## 20260427

### Slice 170: Profile-Aware Dispatch Model Routing — Phase 4 Design

Drafted slice design at [170-slice.profile-aware-dispatch-model-routing.md](project-documents/user/slices/170-slice.profile-aware-dispatch-model-routing.md). Mirrors slice 164's profile-aware fix on the dispatch axis: `_render_dispatch` will branch on resolved profile and emit a runnable `sq dispatch …` command for non-SDK profiles (currently emits "in-session work" regardless of profile, so `/sq:run … --param model=minimax` from inside Claude Code silently runs the dispatch in the IDE session instead of routing to minimax). New `sq dispatch` CLI surface factored from `_dispatch_via_agent`. Independent in-scope fix: `_dispatch_via_session` will surface SDK `is_error=True` messages as `ProviderAPIError` instead of returning the error JSON as response text. Slice plan entry added to [140-slices.pipeline-foundation.md](project-documents/user/architecture/140-slices.pipeline-foundation.md) at index 170 (Feature Slices, after 166); plan `dateUpdated` bumped.

### Slice 904: Review-Finding Location Required — Complete

Resolves [issue #10](https://github.com/ecorkran/squadron/issues/10): review findings inconsistently cite a `location:` field, especially on PASS findings. The field is the dedup key for upcoming ensemble review (slices 182, 189), so it has to land first.

**Four coordinated changes:**

1. **Template prompts** (`src/squadron/data/templates/{code,slice,arch,tasks}.yaml`). All four review templates now require `location:` on every finding (PASS included), with a per-template precedence ladder (e.g. code: `path:line` → `path:start-end` → `path#symbol` → `path` → `unverified`). The explicit `unverified` token is the "I don't know" escape hatch — the prompt tells the model that hallucinated paths are worse than `unverified`. Commit `88bf32e`.

2. **Soft-fail parser normalization** (`src/squadron/review/parsers.py`). New `_normalize_location()` helper: missing locations and placeholder values (`-`, `global`, `n/a`, `none`, empty) become `"unverified"` with a WARNING that names the finding ID, title, template, and verdict. Tightened `_CATEGORY_RE` and `_LOCATION_RE` to `[ \t]*` (was `\s*`) so an empty value tag cannot bleed onto the next body line. Threaded `verdict` and `template_name` through `_extract_findings`, `_lenient_extract_findings`, and the synthesized fallback for consistent triage signals. Commit `059818a`.

3. **Diff-membership check** (code reviews only). `_check_diff_membership()` runs after extraction; for each finding citing a path, WARN if the path is not in the diff under review. Skips `UNVERIFIED_LOCATION` findings. Wired up in `review_client.py` via a new `_run_git_diff_filenames()` helper that calls `git diff --name-only` with the same exclude-pattern handling as `_run_git_diff()`. Commit `846a8a1`.

4. **Path-existence check** (all template types). `_check_path_existence()` runs after extraction; for each finding citing a path and a `cwd`, WARN if `(cwd / path).exists()` is false. Cheap defense against hallucinated filenames in arch/slice/tasks reviews where there's no diff. Same commit as (3).

**Hallucination defense, three layers, all WARNING-only:** prompt-side `unverified` token (self-documenting in rendered review); path-existence (catches made-up filenames everywhere); diff-membership (stricter check where we have an authoritative file set). Hard-rejection deferred until real-world false-positive data is available.

**Tests:** 11 new soft-fail tests (`TestLocationSoftFail`) + 6 diff/path tests (`TestLocationDiffMembershipAndPathExistence`). One existing test (`test_no_location_returns_none`) renamed/updated — the old `None` behavior is now `"unverified"` by design. Full review suite: 315 passing. Full project: 1742 passing.

**T11/T12 manual verification with `minimax/minimax-m2.7`:**
- T11 code review against the slice 902 diff (commit `a4679b6`): 8 PASS findings, 8/8 had `location:` populated with real `path:line-range` values. Zero `unverified`, zero hallucinations, zero parser WARNINGs. Saved to [902-review.code.pipeline-verbosity-passthrough-v-vv.md](project-documents/user/reviews/902-review.code.pipeline-verbosity-passthrough-v-vv.md).
- T12 arch review against `900-arch.maintenance-and-refactoring.md`: 5 findings (3 CONCERN, 2 NOTE), 5/5 had `location:` populated. **All 5 fired path-existence WARNINGs** because the model emitted bare filenames (`900-arch.maintenance-and-refactoring.md`) without the `project-documents/user/architecture/` prefix. The check did exactly its job — the cited paths really don't exist relative to `cwd`. The arch prompt could be tightened later to require project-relative paths; for slice 904 the WARNING is the correct surfacing.

**Caveat captured:** the code prompt does not require `category:` (only arch.yaml does), so code-review findings still fall back to `category: uncategorized` in structured output. Pre-existing, not a 904 regression. If/when ensemble review needs category-based dedup, that's a follow-up.

## 20260426


**slice: devlog-9**
- cf-op-0: PASS
- cf-op-1: PASS
- cf-op-2: PASS
- dispatch-3: PASS
- review-4: PASS (verdict: PASS)
- checkpoint-5: PASS
- commit-6: PASS
- summary-0: PASS
- compact-0: PASS

### Slice 902: Pipeline Verbosity Passthrough — Complete
- Commits: `69aefbf` fix(pipeline): thread verbosity through render_step_instructions; `4c1c011` fix(sq:run): peel -v/-vv flags from arguments, pass to sq run.
- `_render_review` now accepts `verbosity: int = 0` (keyword-only). Hard-coded `-v` replaced with conditional: nothing at 0, `-v` at 1, `-vv` at ≥2.
- `_build_action_instruction` and `render_step_instructions` forward `verbosity`. Both `_handle_prompt_only_init` and `_handle_prompt_only_next` in `run.py` pass `verbose` count from typer option.
- `/sq:run` slash command updated: three-step peel (scan → capture → remove) for `-v`/`-vv`/`--verbose`; Step 0 template includes `<verbose_flags>`.
- Tests: existing assertion updated (no `-v` at default); 3 new parametrized verbosity tests added. Full gate: 1723 passed, ruff+pyright clean.
- Verification walkthrough updated with actual output and `command: null` gotcha (use `a.get('command') or ''`).

### Slice 902: Pipeline Verbosity Passthrough — Task Breakdown Complete
- Created `902-tasks.pipeline-verbosity-passthrough-v-vv.md` (12 tasks, 105 lines).
- Tasks cover: `_render_review` verbosity param + conditional emit, test update + new parametrized tests, `_build_action_instruction` forwarding, `render_step_instructions` param, two `run.py` call sites, slash command peel in `run.md`, two commits, final gate.

### Slice 902: Pipeline Verbosity Passthrough — Design Complete
- Created slice design for issue #9: pipeline review commands hard-code `-v`, `/sq:run` swallows trailing flags.
- Two changes: thread `verbosity` param through `render_step_instructions` → `_render_review` (replacing hard-coded `-v`), and update `/sq:run` slash command to peel `-v`/`-vv` from `$ARGUMENTS`.
- Default changes from implicit `-v` to silent (0); `-v`/`-vv` opt in explicitly.

## 20260425

### Slice 901: Pipeline Code-Review Diff Injection — Implementation Complete

Shipped three coordinated fixes for issue #11 (pipeline code reviews silently UNKNOWN).

**UNKNOWN fails closed** (`checkpoint.py`): Added `"UNKNOWN"` to `ON_FAIL` and `ON_CONCERNS`
threshold sets. `verdict is None` (no prior review) is unchanged — only the
parsed-but-unparseable case fails closed. 8 new unit tests in `test_checkpoint.py`.

**`slice` forwarded through `expand()`** (`phase.py`, `review.py`): `PhaseStepType.expand()` and
`ReviewStepType.expand()` now include `"slice"` in the emitted review action dict. Phase steps
use `"{slice}"` placeholder; review steps forward `cfg.get("slice")`. 4 new tests.

**Declarative template-input registry** (`src/squadron/review/template_inputs.py`): New module
with `TemplateInputSpec` dataclass and `TEMPLATE_INPUTS` dict covering `slice`, `tasks`, `arch`,
and `code` templates. `code` entry calls `resolve_slice_diff_range` to inject `inputs["diff"]`.
`_resolve_slice_inputs` in `pipeline/actions/review.py` rewritten to delegate entirely to
`resolve_template_inputs`. 9 registry tests + 6 `_resolve_slice_inputs` regression tests + 2
end-to-end integration tests.

Gates: 1719 tests pass, ruff clean, pyright 0 errors.

### Slice 901: Pipeline Code-Review Diff Injection — Task Breakdown Complete

Task file created at `user/tasks/901-tasks.pipeline-code-review-diff-injection.md`
(13 tasks, test-with pattern, 4 commits). Covers three coordinated fixes for
issue #11: UNKNOWN fails closed in checkpoint thresholds; `slice` forwarded
explicitly through `PhaseStepType.expand()` and `ReviewStepType.expand()`; and
the per-template `match` in `_resolve_slice_inputs` replaced by a declarative
`TEMPLATE_INPUTS` registry that auto-injects `inputs["diff"]` for the `code`
template via `resolve_slice_diff_range`.

**P6: devlog-2**
- cf-op-0: PASS
- cf-op-1: PASS
- cf-op-2: PASS
- dispatch-3: PASS
- review-4: PASS (verdict: UNKNOWN)
- checkpoint-5: PASS
- commit-6: PASS
- compact-0: PASS

### Slice 194: Loop Step Type for Multi-Step Bodies — Implementation Complete

Shipped `LoopStepType` in `src/squadron/pipeline/steps/loop.py` with full `validate()` (7 rules, nested-loop ban on both sub-field and step-type forms) and `expand()` returning `[]`. Added `_execute_loop_body` to `executor.py` and wired it as the `StepTypeName.LOOP` dispatch branch (ahead of the existing `loop:` sub-field else branch). Reused all slice-149 machinery unchanged: `_parse_loop_config`, `LoopCondition`, `ExhaustBehavior`, `evaluate_condition`, `_unpack_inner_steps`, `_execute_step_once`. Strategy field parsed but stubbed with same warning as the single-step path — slice 184 will implement convergence strategies for both forms simultaneously. Added 25 new tests across three test files; fixed 11 pre-existing integration-test failures caused by `slice.yaml` having grown from 6 to 10 steps in a prior commit. All 1690 tests pass, pyright zero errors.

## 20260424

### Slice 194: Loop Step Type for Multi-Step Bodies — Phase 4 Slice Design Complete

Added new slice 194 to `180-slices.pipeline-intelligence.md` (Feature Slices) and authored slice design at `project-documents/user/slices/194-slice.loop-step-type-for-multi-step-bodies.md`. Top-level `loop:` step type with a `steps:` body, symmetric with `each:`. Reuses existing `LoopConfig` / `LoopCondition` / `evaluate_condition` / `ExhaustBehavior` from slice 149's executor — no new loop semantics. v1 bans both nested-loop forms (sub-field on inner step, and inner `loop:` step type) at validation time. Existing single-step `loop:` sub-field unchanged; inline `review:` sub-field on phase steps stays as phase-only sugar. Prerequisite for slice 184 to drive realistic dispatch-then-review convergence rather than re-asking the same review against an unchanged artifact. Effort 2/5. Status: not-started, ready for Phase 5 (task design).

### Slice 194: Loop Step Type for Multi-Step Bodies — Phase 5 Task Breakdown Complete

Authored `project-documents/user/tasks/194-tasks.loop-step-type-for-multi-step-bodies.md` (275 lines, 21 tasks). Tasks follow the test-with pattern — each implementation task is paired with its test task before moving on. Sequence: enum addition → test stub → `LoopStepType` (validate + expand) → validation tests → expand/registration tests → `_execute_loop_body` executor branch → dispatch wiring → registration import → six integration tests covering pass-on-iteration-1, retry-to-PASS-on-N, three exhaustion modes, transient inner failure, checkpoint short-circuit, nested-loop ban (both forms) → regression check on existing single-step loop suite → authoring example in `example.yaml` → schema/loader smoke test → final lint/types/test gate → slice completion + DEVLOG entry. Slice review (verdict FAIL from kimi-k2.6) addressed: F001 rejected on slice-182 precedent (same registry-mediated step-type addition pattern, shipped in same 180 plan); F002 accepted via new "Deferred Interactions with 184/185/188" section that punts multi-step convergence/escalation/persistence cross-product to those downstream slices. Status: in-review, ready for Phase 6 implementation.

## 20260422

### Slice 169: Compact Action — SDK Capability Dispatch — Implementation Complete

Implemented `CompactAction` end-to-end as a dedicated pipeline action (separate from `SummaryAction`).
`CompactStepType.expand()` now emits `("compact", ...)` instead of `("summary", emit=[rotate])`.
Two execution branches: when `context.sdk_session is not None`, delegates to existing
`SDKExecutionSession.compact()` rotate flow (unchanged); when None, dispatches `/compact` via
`claude_agent_sdk.query()` and awaits `SystemMessage(subtype="compact_boundary")`, logging
`pre_tokens`/`trigger`/`compacted_at` to `ActionResult.outputs`. Default 120s timeout.
`SummaryAction` gained `restore: true` mode — reads most recent prior `summary` result from
`prior_outputs` and seeds it into the SDK session via `seed_context()`.

**Design simplification during implementation:** T2 (SessionCapabilities), T3 (capability probe),
and T4 (/model investigation) were dropped after PM discussion. The original design called for
reading `slash_commands` from the SDK init message and branching on capability presence. Simplified
to: assume `/compact` is available (SDK v0.0.20+ guarantees it); branch on `sdk_session` presence
instead. `SessionCapabilities` dataclass and `ActionContext.capabilities` field were not added.

**Added:** `src/squadron/pipeline/actions/compact.py` (CompactAction, ~165 lines);
`src/squadron/data/pipelines/test-compact-compose.yaml`; `_render_compact` builder in
`prompt_renderer.py` (emits `trigger: "/compact"` for prompt-only). **Modified:**
`CompactStepType` (new config surface: `model`, `instructions`); `SummaryAction._execute_restore`;
`ActionType` enum (added `COMPACT`); executor imports `actions.compact` to trigger registration;
existing integration test registries gained `"compact": action` entries.

**Tests:** 16 new in `test_compact.py` (action unit); 12 rewritten in `steps/test_compact.py`
(StepType); 3 new in `test_compact_compose_integration.py` (prompt-only + true-CLI compose,
dead-slash-text regression); 6 new restore-mode tests in `test_summary.py`; 1 new registry
integration assertion. **Total: 1665 passing, pyright clean, ruff clean.**

**Docs:** `docs/PIPELINES.md` — compact step section rewritten with environment matrix and
compose pattern; summary section documents `restore: true`; actions table updated.
`CHANGELOG.md` — `[Unreleased]` section describes added capability, restore mode, and
migration note for pipelines that relied on compact's implicit summary. No existing pipeline
YAMLs required migration (audit in T9 found all `compact:` uses were pure context-reduction,
not summary-capture dependencies).

**Commits:** `126a0bf` (CompactAction + step wiring), `e988261` (summary restore mode),
`b5ac797` (compose integration tests + pipeline YAML), `6293ff0` (docs).

---

## 20260415

### Slice 182: Fan-Out / Fan-In Step Type — Implementation Complete

Implemented `fan_out` step type end-to-end. New files: `src/squadron/pipeline/steps/fan_out.py`,
`src/squadron/pipeline/intelligence/fan_in/{__init__,protocol,reducers}.py`. Executor changes:
`_execute_fan_out_step` added to `executor.py`, dispatch branch wired after `each` in
`execute_pipeline`, import triggers added for `fan_out` module and `fan_in.reducers`.
29 new tests (15 step/integration + 14 reducer); 1635 total passing. Pyright and ruff clean.
SDK-session guard wording matches user-facing contract exactly. Slice 189 can register
`merge_findings` reducer at import time with no fan-out infra changes.

**Commits:** `1e138a7` (reducers), `25fff72` (FanOutStepType), `fc60e7b` (executor), `812f2a2` (cleanup)

---

### Slice 182: Fan-Out / Fan-In Step Type — Design + Tasks Complete

Created slice design `user/slices/182-slice.fan-out-fan-in-step-type.md` and task file
`user/tasks/182-tasks.fan-out-fan-in-step-type.md` (14 tasks, 202 lines). Design covers
`FanOutStepType`, `_execute_fan_out_step` in executor, `FanInReducer` protocol, and
`collect`/`first_pass` built-in reducers. Key decisions: reuse `resolver.resolve()` N times
for pool multi-select (no new `PoolBackend` method needed), explicit SDK-session guard (raise
error rather than silently interleave), failure fast-fail before reducer. Unblocks slice 189
(Ensemble Review). Ready for Phase 6 (Implementation).

---

### Slice 168: `sq review code` — Slice Implementation Review — Complete

Added commit-message grep as step 3 in `resolve_slice_diff_range` (`src/squadron/review/git_utils.py`). `sq review code <N>` now resolves a useful diff range for slices merged directly to main with no surviving branch. Single-commit edge case handled via `{sha}^!` syntax. `--fan N` flag added to `sq review code` as a placeholder for slice 182 fan-out; warns and proceeds. 12 new tests (1598 total). All passing, pyright clean.

**Commit:** `b5df568` feat: resolve slice impl diff via commit grep

---

## 20260414

### Slice 181: Pool Resolver Integration and CLI — Implementation Complete

Wired the slice 180 pool infrastructure into the resolver, state, and CLI. Key implementation
decisions: `PoolBackend` protocol and `DefaultPoolBackend` added to new `backend.py` (slice 180
shipped only module-level functions); resolver construction sites are in `run.py` (not
`executor.py`, which accepts a pre-built resolver as a param); `state.py` `_load_raw` uses a
`_SUPPORTED_SCHEMA_VERSIONS = {3, 4}` set to accept both v3 (back-compat) and v4 (new). At
SDK-mode call site, resolver must be built after `init_run` so `run_id` is in scope for the
`on_pool_selection` closure. Pre-existing schema v1 run files produce harmless
"Skipping unreadable state file" log warnings from `list_runs()` — expected, not a bug.
1589 tests passing; 5 commits.

Refactor: consolidated `sq pools show <name>` into `sq pools list [name]` — optional name arg
produces detail view (members + recent selections). Pattern matches `sq models list`. 949 tests
passing; 6 commits. Bump to 0.4.0 — start of significant new functionality (pool-based model
selection).

---

## 20260413

### Slice 180: Model Pool Infrastructure and Strategies — Implementation Complete

Implemented full pool infrastructure in `src/squadron/pipeline/intelligence/pools/`:
5 source files (`models.py`, `protocol.py`, `strategies.py`, `loader.py`, `__init__.py`),
`src/squadron/data/pools.toml` (3 built-in pools), 5 test files (71 new tests, all green).
One bug found during implementation: `tomli_w.dumps()` returns `str` not `bytes` — fixed
with `write_text()` instead of `write_bytes()`. No regressions in the 1478 existing tests.
Patch order for `get_all_aliases` in tests: must patch `squadron.models.aliases.get_all_aliases`
(the source) since loader imports it lazily inside functions.

### Slice 180: Model Pool Infrastructure and Strategies — Design Complete (Phase 5)

Task breakdown complete at `project-documents/user/tasks/180-tasks.model-pool-infrastructure-and-strategies.md`
(28 tasks, 420 lines). Covers: package scaffolding, test infrastructure, data models (`ModelPool`,
`SelectionContext`, `PoolState`), `PoolStrategy` protocol, four built-in strategies (`random`,
`round-robin`, `cheapest`, `weighted-random`), strategy registry, round-robin state persistence,
built-in `pools.toml`, pool loader with alias validation, `select_from_pool` wrapper, and public
API surface. Test-with pattern applied throughout; 5 intermediate commits defined.
Implementation is slice 181's blocker for pool resolver integration.

---

## 20260412

### Slice 191: Dispatch Summary Context Injection — Complete (Phase 6)

Fixed the root cause of empty/hallucinated non-SDK summary output: one-shot
models received only the compaction template instructions with zero pipeline
context. Added `src/squadron/pipeline/summary_context.py` — a pure function
`assemble_dispatch_context` that iterates `prior_outputs` and assembles prior
dispatch responses, review verdicts/findings, and `build_context` stdout into
a delimited context block prepended to non-SDK summary instructions. SDK path
(has session history) is completely unmodified. 13 unit tests, 2 integration
tests, all 623 pipeline tests green, ruff clean. Verified with a live minimax
run: model correctly summarized the dispatch response and accurately reported
it had no slice 191 content (the test pipeline used an unrelated prompt).

Also added `dispatch` as a first-class YAML step type (previously only an
internal `ActionType`). Accepts optional `prompt` and `model`; expands to a
single dispatch action. Required to make Verification Walkthrough scenarios
runnable directly. 8 new tests.

Fixed a `/sq:summary --restore` hallucination bug (v0.3.13): CLI only emitted
the selected filename to stderr in the multi-match case; single-match was
silent, causing the model to use the nearby example value verbatim. Always emit
`Using: {name}` to stderr; slash command now parses it explicitly and errors if
absent. Added "Hallucination traps in prompts" rule to CLAUDE.md.

---

## 20260411

### Slice 166: Compact and Summary Unification — Complete (Phase 6)

Completed the runtime unification of `compact` and `summary`. Deleted
`CompactAction`, `ActionType.COMPACT`, `_render_compact`, and both
compact action test files (~780 lines net deleted). Moved template
helpers (`CompactionTemplate`, `load_compaction_template`,
`render_instructions`, `_parse_template`) from `actions/compact.py`
into a new `src/squadron/pipeline/compaction_templates.py` module;
updated all five consumers to import from the new home.

Rewrote `CompactStepType.expand()` to return `("summary", {...,
"emit": ["rotate"]})` instead of `("compact", ...)`. Rewrote
`StateManager._maybe_record_compact_summaries` gate to fire on
`action_type="summary"` with a successful rotate emit entry in
`emit_results` — the one real risk in the slice. Removed the
`### compact` section from `commands/sq/run.md` and refreshed the
installed copy.

Prompt-only smoke test confirmed: `compact-1` step in P6 now renders
as `action_type="summary"`, `emit=["rotate"]`, no `/compact [` in
any command field. All 1455 tests green, pyright clean, ruff clean.

No surprises. Pipeline YAML files (P6, slice, tasks, app, example)
all validate cleanly — `compact:` keyword still parses.

### Slice 166: Compact and Summary Unification — Task Breakdown Complete (Phase 5)

Broke slice 166 into a single task file at
`project-documents/user/tasks/166-tasks.compact-and-summary-unification.md`
(26 tasks, 6 commit checkpoints, ~510 lines). Kept it as one file after
weighing against the 450-line guideline — splitting added more friction
than it solved for this size.

Task groups follow the migration order from the slice doc's
Implementation Notes: (1) survey call sites, (2) extract template
helpers into a new `compaction_templates.py` module and update every
import before touching runtime code, (3) rewrite
`CompactStepType.expand()` and the `_maybe_record_compact_summaries`
gate with paired tests, (4) delete `_render_compact` and add a
prompt-only renderer smoke test, (5) delete `CompactAction`,
`ActionType.COMPACT`, and compact-specific tests, (6) clean up
`commands/sq/run.md`, (7) pipeline validation + E2E smoke tests in
both prompt-only and SDK modes + grep verification + full quality
gate, (8) arch doc verification and slice/DEVLOG wrapup.

Test-with pairing honored throughout: each rewrite (step expand,
state gate, `_render_compact` removal) has its tests as the immediate
successor task. The state gate test specifically covers the slice's
one real risk — summary action with rotate emit must still populate
`RunState.compact_summaries` for resume-with-reinjection.

Next: Phase 6 implementation.

### Slice 166: Compact and Summary Unification — Review PASS (1 concern addressed)

Review verdict PASS (glm5). Eight findings: seven pass, one note, one concern.

Concern F004 (documentation-sync): `140-arch.pipeline-foundation.md` lists
compact as a distinct action type in two places flagged by the reviewer, plus
two additional locations I found when auditing: action registry table (line
106), detailed compact-action subsection (lines ~246-251), action type diagram
(line 514), and `actions/compact.py` package entry (line ~549). Addressed by
adding a new §"Architecture Document Updates" section to the slice design with
a concrete change checklist and explicit out-of-scope list (compaction as
concept, `compact:` YAML examples, and step-type-layer references all stay).
Arch doc updates land during Phase 6 implementation alongside the code changes,
keeping doc and code in sync rather than drifting during the implementation
window. New success criterion #11 verifies the arch doc is updated.

Review: `project-documents/user/reviews/166-review.slice.compact-and-summary-unification.md`.

### Slice 166: Compact and Summary Unification — Design Complete

Added slice 166 to `140-slices.pipeline-foundation.md` and designed it at
`project-documents/user/slices/166-slice.compact-and-summary-unification.md`.

Finishes the abandoned refactor from slice 161. Today compact and summary are
two half-merged code paths: SDK mode already delegates compact to summary
internally, but prompt-only mode still renders a broken `/compact [...]` slash
command string. This breaks P6 and every pipeline using `compact:`.

Design: rewrite `CompactStepType.expand()` to emit a summary action with
`emit=[rotate]` instead of a compact action. Delete `CompactAction`,
`ActionType.COMPACT`, `_render_compact`, the compact test class, and the compact
section of `commands/sq/run.md`. `compact:` YAML continues to parse — it becomes
a pure two-word alias with no unique code below the step-expansion layer.

One real risk: `state.py::_maybe_record_compact_summaries` is gated on
`ar.action_type == "compact"`. After the refactor no action is compact-typed, so
the gate must switch to "summary action whose emit includes rotate" to preserve
resume-with-reinjection. Called out explicitly in the design with its own
targeted integration test. No schema version bump — field names and shapes
unchanged.

Template helper functions (`load_compaction_template`, `render_instructions`)
must be moved out of `actions/compact.py` before the file can be deleted, since
the summary action imports them.

Priority: implement before continuing 180-band work — P6 is currently broken in
prompt-only mode.

Marked slice plan 140 frontmatter `status: in_progress` (was `complete`). Slice
plan entry numbering updated: 166 added as item 23, Integration Work item 152
bumped from 23 to 24.

---

### Slice 181: Pool Resolver Integration and CLI — Design Complete

Created `project-documents/user/slices/181-slice.pool-resolver-integration-and-cli.md`.

Design extends `ModelResolver` with `pool_backend` and `on_pool_selection` callback params.
`_resolve_pool()` delegates to `PoolBackend.select()` (slice 180), then resolves the returned
alias through the existing alias registry — transparent to all action handlers. `RunState` gains
`pool_selections: list[dict]` with schema version bump to 4 (backwards-compatible). New
`sq pools` CLI (list / show / reset) follows the `sq models` pattern. Executor wires up
`PoolLoader.load()` and the logging callback when building `ModelResolver`.

---

### Slice 160: Interactive Checkpoint Resolution — Implementation Complete

Phase 6 complete. Three files changed:

- `executor.py`: Added `CheckpointResolution(StrEnum)`, `CheckpointDecision` dataclass,
  `_is_interactive()`, `_prompt_checkpoint_interactive()`. Modified `_execute_step_once`
  checkpoint detection block to call the handler; EXIT path returns PAUSED (unchanged),
  Accept/Override inject `override_instructions` into `merged_params` and continue.
- `actions/dispatch.py`: `_resolve_prompt` now reads `override_instructions` from
  `context.params` and prepends a delimited block when present.
- `prompt_renderer.py`: `_render_checkpoint` now describes all three options per trigger
  type. `run_id` injected into `render_params` so the resume command is correct.

All 1477 tests pass. `pyright` clean. No `RunState` schema change (stays v3).

---

### Slice 160: Interactive Checkpoint Resolution — Design Complete

Created `project-documents/user/slices/160-slice.interactive-checkpoint-resolution.md`.

Design confines the change to three files: `executor.py` (interactive handler +
`CheckpointResolution`/`CheckpointDecision` types), `actions/dispatch.py` (pick up
`override_instructions` from params), and `prompt_renderer.py` (enhanced checkpoint
instruction text). The Accept/Override path injects instructions into `merged_params` and
continues in-place; the Exit path is unchanged. No `RunState` schema bump required.
Updated slice plan entry 18 with Design Complete pointer.

---

### CHANGELOG rewrite — user perspective

Rewrote all CHANGELOG entries to answer "what can I do / what bug is fixed"
rather than listing internal class names, module paths, and slice refs.
Net: 338 lines removed, changelog is now readable without source context.

---

## 20260411

### Slice 164 implementation complete: profile-aware summary model routing

**Slice 164 — Phase 6 complete.**

- **What changed:**
  - New module `src/squadron/pipeline/summary_oneshot.py`:
    `is_sdk_profile()` predicate and `capture_summary_via_profile()` —
    near-copy of the ~40 relevant lines from `run_review_with_profile()`,
    review-specific paths stripped.
  - `_execute_summary()` now branches on resolved profile: SDK path
    (profile `None` or `"sdk"`) keeps `sdk_session.capture_summary()`;
    non-SDK path dispatches through the provider registry via
    `capture_summary_via_profile()`.
  - Rotation emit + non-SDK profile fails fast with a descriptive error
    at execution time (resolver not available at schema-validation time).
  - `_render_summary()` in `prompt_renderer.py` emits `model_switch` for
    SDK profiles and `command` (runnable `sq _summary-run …`) for
    non-SDK profiles.
  - New hidden CLI subcommand `sq _summary-run` (registered alongside
    `sq _summary-instructions`) as the CLI surface for prompt-only
    non-SDK summary execution.
  - `CompactAction` inherits the fix for free via the shared
    `_execute_summary()` helper.
  - 1452 tests pass; pyright and ruff clean.

- **OQ1 resolved:** Option A — new hidden `sq _summary-run` subcommand,
  matching the `_summary-instructions` naming convention. The subcommand
  name uses leading underscore (`_summary-run`) per project convention.

- **Surprises:**
  - `compact.py` imports `_execute_summary` inside the method body
    (deferred import), so tests must patch
    `squadron.pipeline.actions.summary._execute_summary`, not
    `squadron.pipeline.actions.compact._execute_summary`.
  - `--validate` in `sq run` only calls schema-level `validate()` — the
    rotate+non-SDK profile check fires at execution time, not validation
    time (resolver is execution-time only). Slice doc updated with
    caveat.

- **Pipelines unblocked:** Any pipeline summary step can now use cheap
  external models (minimax, gemini-flash, local) via their respective
  profiles. The only restriction is `emit: [rotate]`, which remains
  SDK-only.

---

### Slice 164 design + tasks; CI fix; phase pipelines now write summary files

**v0.3.8 release.**

- **Slice 164 (Profile-Aware Summary Model Routing)** — Phase 4 design
  and Phase 5 task breakdown complete via `/sq:run P4 164` and
  `/sq:run P5 164`. Both phases reviewed PASS by minimax-m2.7. Slice
  routes the summary action through the provider registry for non-SDK
  profiles, mirroring `run_review_with_profile()`. New module
  `summary_oneshot.py` houses `capture_summary_via_profile()` and the
  `is_sdk_profile()` predicate. 17 implementation tasks in
  `164-tasks.profile-aware-summary-model-routing.md`. Implementation
  deferred (Phase 6 not yet started).
- **CI fix** — `prompt_renderer.py:270` had a `dict[str, object]`
  narrow that pyright couldn't infer through; added
  `cast(list[object], emit_raw)` after the `isinstance(list)` check.
  Seven consecutive `main` builds had been red on this same error.
- **Phase pipelines now write summary files** — after re-running
  `sq install-commands` to refresh stale `summary.md` and `run.md`
  skills, discovered that all five phase pipelines (P1, P2, P4, P5, P6)
  emit only `[stdout, clipboard]` and never `[file]` — so slice 163's
  default-file-path branch had nothing to write to. Added `file` to
  every P*.yaml emit list. `/sq:summary --restore` now works
  end-to-end after any phase pipeline run.

**Commits:**
- `5d7ab9d` docs: add slice 164 profile-aware summary model routing design
- `32fc9e7` fix: cast emit list to satisfy pyright in _render_summary
- `f8c887a` docs: add slice 164 task breakdown
- (this commit) feat: emit pipeline summaries to file + bump to v0.3.8

## 20260410

### Slice 163: Pipeline Run Summary Persistence and Restore — Complete

**Phase 6 (implementation) complete.**

- Closes the "run pipeline in CLI terminal, restore context in VS Code" workflow gap
- Three implementation sites: `emit.py` (default file path), `executor.py` (_project injection), `summary_instructions.py` (--restore), `commands/sq/summary.md` (--restore branch), `commands/sq/run.md` (file-write step)
- Key decision: bare `"file"` in `emit:` YAML list now produces `EmitDestination(kind=FILE, arg=None)` rather than raising; default path is `~/.config/squadron/runs/summaries/{project}-{pipeline}.md`
- `_project` threaded into `ActionContext.params` via `gather_cf_params()` at pipeline init in `executor.py`; falls back to `"unknown"` when CF unavailable; caller-supplied `_project` not overwritten
- 31 new tests added (28 in test_emit.py, 3 in test_executor.py, 5 in test_summary_instructions.py)

**Commits:**
- `51a3342` feat: add default summaries path to emit and thread _project into ActionContext
- `1d6281f` feat: add --restore to /sq:summary and write summary to conventional path in run.md


**tasks: devlog-4**
- cf-op-0: PASS
- cf-op-1: PASS
- cf-op-2: PASS
- dispatch-3: PASS
- review-4: PASS (verdict: UNKNOWN)
- checkpoint-5: PASS
- commit-6: PASS
- compact-0: PASS

### Slice 152: Pipeline Documentation and Authoring Guide — Complete

**Deliverables created:**
- `docs/PIPELINES.md` — authoritative pipeline authoring guide (Quick Start, YAML Grammar, Step Type Catalog, Action Type Catalog, Model Resolution, Configuration Surface, Built-in Pipelines, Custom Pipeline Walkthrough, Prompt-Only Mode)
- `README.md` — added `## Pipelines (sq run)` section with quick-start and link to guide

**Discrepancies found during T1 verification (documented, not propagated from slice design):**
- `slice` pipeline has 2 params (`slice`, `review-model`); slice design table listed only `slice`
- `tasks`, `P5`, `P6` each have 3 params including `model`; design table showed 2
- `example.yaml` inline comment shows stale project path (`.squadron/pipelines/`); loader uses `project-documents/user/pipelines/` — guide uses loader path
- `app.yaml` is a WIP pipeline (same description as design-batch, has TODO comment) — excluded from docs

**Commits:**
- `4056c7b` docs: add pipeline authoring guide
- `5460177` docs: add sq run section to README

## 20260409

### Slice 162: /sq:summary — Clipboard Summary for Manual Context Reset

**Phase 4 (design) + Phase 5 (task breakdown) + Phase 6 (implementation) complete.**

- Motivated by unreliable `/compact [with instructions]` — user wants deterministic "clear with custom summary" using templates already built for pipeline compaction (slices 157/158)
- Design: slash command `/sq:summary [template]` + hidden `sq _summary-instructions` CLI. Current CC session generates the summary inline; squadron supplies template instructions + clipboard sink.
- Created `pipeline/summary_render.py` with `resolve_template_instructions()` and `gather_cf_params()` — logic salvaged from dead `precompact_hook.py`
- Removed `precompact_hook.py`, `install_settings.py`, and all PreCompact hook install/uninstall logic (dead code since 0.3.3)
- Reuses `compact.template` config key — no new config surface
- Clipboard via shell chain: `pbcopy` → `xclip` → `wl-copy` (Windows deferred)
- All 1400 tests pass, ruff clean, pyright clean
- Post-implementation: removed misleading "do not print to chat" instruction from summary.md — summary appearing in chat is correct and lets user verify before `/clear`; bumped to v0.3.4

## 20260408 (session 2)

**v0.3.3 release — merge, tag, PyPI publish**

- Caught that dispatch fix landed on `test-161-pipeline` instead of `161`; cherry-picked `07881d5` → `210950d`
- Bumped version 0.3.2 → 0.3.3, merged `161-slice.summary-step-with-emit-destinations` → main, tagged `v0.3.3`
- CI: both push and tag runs triggered; `publish` job succeeded; `squadron-ai==0.3.3` live on PyPI
- Verified full pipeline smoke test end-to-end (design → tasks → summary:rotate → design again) on separate branch; discarded test branch
- CHANGELOG restructured: collapsed duplicate `[Unreleased]` sections into proper versioned entries; fixed orphaned `## [Unreleased]` mid-file (was 0.2.7-era content); made entries more concise for human readers
- **Latent bug fixed:** `DispatchAction` — Claude CLI surfaces API errors (e.g. 500) as assistant text with `"API Error:"` prefix; dispatch was returning `success=True`, allowing review/checkpoint to run against a non-existent output file. Added `_check_cli_error()` detection in both session and agent paths.

## 20260408

### Slice 161: Summary Step with Emit Destinations — Complete

**Commits (8 slice commits):**
- `877f1e6` chore: add pyperclip dependency for summary clipboard emit
- `2bbbcb7` feat: add SDKExecutionSession.capture_summary() method
- `1a953ae` feat: add summary= overload to SDKExecutionSession.compact()
- `6f78e1e` feat: add emit destination registry and types
- `76b0e65` feat: add SummaryAction with config validation
- `9b043a7` feat: implement _execute_summary shared helper
- `c613422` feat: wire SummaryAction.execute to shared helper
- `7293394` feat: add SummaryStepType, register summary action+step, validate emit, update test-pipeline

**Delivered:**
- `SDKExecutionSession.capture_summary()` — captures summary without rotating session
- `SDKExecutionSession.compact(summary=...)` — `summary=` overload skips capture phase for reuse
- `emit.py` — `EmitKind` registry with stdout, file, clipboard (pyperclip), rotate destinations
- `actions/summary.py` — `SummaryAction` + `_execute_summary()` shared helper; single capture, multi-destination dispatch; rotate failures fail the action, others log warning
- `CompactAction` SDK path refactored to delegate into `_execute_summary()` with `emit=[rotate]`; `action_type` kept as `"compact"` — state persistence unaffected
- `SummaryStepType` with `emit` validation and `checkpoint:` shorthand (expands to summary + checkpoint action pair)
- `test-pipeline.yaml` updated to use `summary:emit:[rotate]` in place of `compact:`
- 1429 tests passing; pyright clean; ruff clean

**Pending / deferred:**
- T15 manual smoke test (`sq run test-pipeline 154 -vv`) deferred — requires live Claude SDK session; no blockers
- `clear` follow-up (rotate without seeding) not yet filed as a slice; design open question from 161 slice doc

---

## 20260407

**Slices 158, 159: Pipeline plan additions**
Added two new feature slices to `140-slices.pipeline-foundation.md`. Slice 158 (Pipeline Fan-Out / Fan-In Step Type) — general parallel branch infrastructure with pluggable fan-in reducer; ships with identity reducer, consensus reducer is a stub for 160; demonstrates with N>1 reviews against multiple models; foundational for consensus review infrastructure. Slice 159 (Interactive Checkpoint Resolution) — replace pause-and-exit with interactive prompt offering accept/override/exit options; first two avoid the full resume cycle. Both slices need design (Phase 4) before implementation.

**Slice 157: SDK Session Management and Compaction — Design Updated (Phase 4 revision)**
Revised `157-slice.sdk-session-management-and-compaction.md` to address two review concerns: (1) checkpoint resume after compact loses the summary because the previous process's session is gone — fixed by persisting compact summaries in a new keyed `compact_summaries` dict on `RunState` (schema bump v2 → v3); (2) executor-owned re-injection on resume via a new `seed_context()` session method. Keying scheme `{step_index}:{step_name}` is forward-compatible with slice 158 fan-out branches (will extend with `#branch{n}` suffix). Added `CompactSummary` dataclass, `record_compact_summary` state manager method, and `active_compact_summary_for_resume` helper. Re-reviewed task breakdown follows in same session.

**Slice 157: SDK Session Management and Compaction — Task Breakdown Updated (Phase 5 revision)**
Expanded `157-tasks.sdk-session-management-and-compaction.md` from 11 tasks to 18 to cover the design revision: T2/T3 add `CompactSummary` dataclass, schema v3 bump, state manager persistence and lookup helpers; T7 adds `seed_context()` method; T11 wires the compact summary persistence via the executor's `on_step_complete` callback (action stays free of state-manager coupling); T12 implements executor resume injection; T14 adds an automated integration test for the full session rotate flow; T15 adds an automated test specifically for resume-after-compact. T13 (PreCompact hook) retains its investigation-first note. Test-with pattern throughout; 452 lines.

## 20260406

**Slice 157: SDK Session Management and Compaction — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/157-tasks.sdk-session-management-and-compaction.md`. 11 tasks (T1–T11): capture `session_id` from `ResultMessage` in translation (T1); add `session_id` and `options` fields to `SDKExecutionSession` (T2); pass options into session from `_run_pipeline_sdk` (T3); implement `compact()` session rotate method (T4); remove `configure_compaction()` stub (T5); add `model` field to compact step YAML (T6); wire compact action to call `session.compact()` (T7); register `PreCompact` hook for interactive instruction injection (T8); end-to-end smoke test via test-pipeline (T9); lint/type-check/full suite (T10); closeout (T11). Test-with pattern throughout; commits after each implementation+test pair. Note: T8 includes verification-before-implement note for the `PreCompact` hook return format as that API detail needs confirmation.

**Slice 157: SDK Session Management and Compaction — Design Complete (Phase 4)**
Created `project-documents/user/slices/157-slice.sdk-session-management-and-compaction.md`. Core approach: session rotate compaction at pipeline step boundaries. When compact step executes, switch model to cheap summarizer (e.g. haiku) in the *current* session, query with compact template instructions, capture summary, disconnect, start fresh session seeded with summary. Key insight: summarize in the live session (model has full context) rather than resuming in a new process (loads entire context just to read it). Also wires `PreCompact` hook for interactive `/compact` instruction injection. Adds optional `model` field to compact YAML. Removes unconnected `configure_compaction()` stub from slice 155. Agent SDK investigation confirmed: no `context_management`, no `compaction_control`, no threshold control — session rotate is the only deterministic compaction path. Dependencies: [155, 156]. Effort: 3/5.

## 20260405

**Fix: validate pipeline before execution, not just `--validate`**
`_run_pipeline` now calls `validate_pipeline()` before `execute_pipeline()`, so invalid action parameters (e.g. `checkpoint: concerns` instead of `on-concerns`) are caught with a clear error before execution begins. Previously validation only ran for `--validate` and `--dry-run`. Also added defense-in-depth in `CheckpointAction.execute()` — invalid trigger values now return `ActionResult(success=False)` instead of an unhandled `ValueError`. 1253 tests pass.

**Slice 154: Prompt-Only Loops — Design Complete (Phase 4)**
Created `project-documents/user/slices/154-slice.prompt-only-loops.md`. Slice extends slice 153's prompt-only mode to transparently support `each`/collection loops. Core design: `EachLoopState` dataclass tracks iteration context (current item index, inner step name, cached source query results) persisted in `RunState`; `render_each_step_instructions()` resolves CF source queries on first entry; placeholder resolution enhanced to support `{param.field}` dot-path syntax for item binding; `StateManager` methods `first_unfinished_step()` and `advance_iteration()` handle navigation within/across iterations. To the caller, loops are transparent — each `--next` returns the next instruction in flattened execution order, whether it's a new step or next iteration. Model switching is informational only (slash command handles manually). Technical decisions documented: transparent iteration, params-based item binding, single-depth loops (nesting deferred to 160), convergence strategies stubbed (160 scope). Data flows, state persistence format, and integration points detailed. Ready for Phase 5 (task breakdown) and Phase 6 (implementation). Effort: 2/5, risk: low.

**Slice 156: Pipeline Executor Hardening — Implementation Complete (Phase 6)**
Implemented all 14 tasks. `ExecutionMode` StrEnum added to `state.py`; `RunState` schema bumped to v2 with `execution_mode` field (default `SDK` for forward-compat with v1 files); `init_run` gains `execution_mode` param and `pipeline_name.lower()` normalisation. `_run_pipeline` gains `run_id` param (skips `init_run` when provided); `_run_pipeline_sdk` gains `run_id` param and forwards with `execution_mode=SDK`. Both `--resume` and implicit resume paths rewritten to dispatch via `match state.execution_mode:` — no string literals. `_handle_prompt_only_init` records `PROMPT_ONLY`. `load_pipeline` and `discover_pipelines` normalise names to lowercase; CLI `run()` normalises at `--validate`, `--dry-run`, `--prompt-only`, and standard execution entry points. `--status` output includes `Mode:` line. 1251 tests pass; pyright zero errors; ruff clean. Branch: `156-slice.pipeline-executor-hardening`.

## 20260404

**Slice 156: Pipeline Executor Hardening — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/156-tasks.pipeline-executor-hardening.md`. 14 tasks (T1–T14): `ExecutionMode` StrEnum in state.py (T1); schema v2 with `execution_mode` field on `RunState` (T2); `init_run` gains `execution_mode` param and lowercase normalisation (T3); `_run_pipeline` gains `run_id` and `execution_mode` params (T4); `_run_pipeline_sdk` gains `run_id` param (T5); fix `--resume` dispatch via `match state.execution_mode` (T6); fix implicit resume dispatch (T7); `_handle_prompt_only_init` records `PROMPT_ONLY` (T8); lowercase normalisation in `load_pipeline` (T9) and `discover_pipelines` (T10); CLI input normalisation (T11); display `execution_mode` in `--status` (T12); lint/type-check/full suite (T13); closeout (T14). Test-with pattern throughout; 6 commit checkpoints.

**Slice 156: Pipeline Executor Hardening — Design Complete (Phase 4)**
Diagnosed resume failure: both `--resume` and implicit resume paths bypass `_run_pipeline_sdk`, so `sdk_session` is `None` on resume; compact action falls through to `cf compact --instructions ...` which does not exist. Fix scope: (1) `ExecutionMode` StrEnum added to `state.py`; (2) `RunState.execution_mode` field (schema v2); (3) both resume paths dispatch by enum match to the correct runner; (4) `_run_pipeline_sdk` accepts `run_id` for resume-in-place; (5) pipeline name normalised to lowercase at load and CLI input boundary. Design created at `project-documents/user/slices/156-slice.pipeline-executor-hardening.md`.

**Slice 154: Prompt-Only Loops — Design Complete (Phase 4)**
Created `project-documents/user/slices/154-slice.prompt-only-loops.md` and `project-documents/user/tasks/154-tasks.prompt-only-loops.md`. Slice extends prompt-only mode to transparently support `each`/collection loops — executor expands loops internally, returns successive iteration instructions via `--next` calls. To the caller, a loop appears as a sequence of steps. Enables design-batch pipelines (multi-slice batch operations) in interactive prompt-only mode. Architecture: loop state tracking (iteration count, bound item) in StateManager; placeholder resolution (`{slice.index}` → actual value from item); query source executor for CF `cf.unfinished_slices(plan)` integration; loop expansion in executor's `next_step()` / advancement in `step_done()`. Convergence loop syntax acknowledged in YAML but stubbed (strategies are 155/160 scope). 20 implementation tasks; test-with pattern throughout. No design blockers; ready for implementation.

**Slice 155: SDK Pipeline Executor — Implementation Complete (Phase 6)**
Implemented all 20 tasks (T1–T20). Created `src/squadron/pipeline/sdk_session.py`: `SDKExecutionSession` dataclass wrapping `ClaudeSDKClient` with `set_model()` (skips if unchanged), `dispatch()` (rate-limit retry, error translation), `configure_compaction()` (stores config), `connect()`/`disconnect()` lifecycle. Extended `ActionContext` with `sdk_session: SDKExecutionSession | None = None`. Dispatch action gains `_dispatch_via_session()` path; routing checks `context.sdk_session`. Compact action gains SDK path that calls `session.configure_compaction()` instead of CF. Environment detection via `_resolve_execution_mode()` raises `typer.Exit(1)` for `CLAUDECODE` env var. CLI wiring: `_run_pipeline_sdk()` async helper creates session, connects, calls `_run_pipeline()`, disconnects in `finally`. Executor propagates `sdk_session` through all `_execute_step_once()`/loop/each call chains. 38 new tests across 5 test files. Full suite: 1228 tests pass, zero regressions. Slice 155 marked complete.

**Slice 155: SDK Pipeline Executor — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/155-tasks.sdk-pipeline-executor.md`. 20 tasks (T1–T20): SDKExecutionSession module with persistent client lifecycle and set_model()/dispatch()/configure_compaction() methods (T1-T3), ActionContext extension with sdk_session field (T4), dispatch action session path with model switching (T5-T7), compact action SDK compaction path via context_management API (T8-T10), environment detection for CLAUDECODE rejection (T11-T13), CLI wiring and executor propagation (T14-T17), integration test with full pipeline cycle (T18-T19), lint/verify/closeout (T20). Test-with pattern throughout; 7 commit checkpoints.

**Slice 155: SDK Pipeline Executor — Design Complete (Phase 4)**
Created `project-documents/user/slices/155-slice.sdk-pipeline-executor.md`. Full pipeline automation via `ClaudeSDKClient` with persistent session, per-step model switching via `set_model()`, and server-side compaction via `context_management` API (`compact_20260112` beta). Slice review (glm-5) raised FAIL on persistent session violating 140's "stateless steps" principle. Resolved by updating `140-arch.pipeline-foundation.md` to distinguish SDK session persistence (runtime optimization, 140 scope) from conversation persistence (semantic dependency, 160 scope). Architecture updated: "Interaction with Conversations" section clarified, dependency notes updated.

**Slice 153: Verification and Pipeline Testing**
Ran prompt-only pipeline end-to-end in IDE extension, Claude Code CLI, and straight CLI. Findings: (1) reviews blocked inside Claude Code sessions ("no nested Claude Code") regardless of model — review dispatch goes through SDK subprocess; (2) `/model` and `/compact` slash commands cannot be automated — only user can issue slash commands; (3) checkpoint `always` trigger required stronger prompt language to enforce. Fixed: review command now uses model alias (not resolved ID) to preserve profile resolution; removed invalid `--template` flag; strengthened checkpoint/compact instructions in `/sq:run`. Added `test-pipeline.yaml` for low-cost pipeline testing. Added slice 155 to slice plan, updated slice 154 scope (loops only, model switching informational).

**Slice 153: Prompt-Only Pipeline Executor — Implementation Complete (Phase 6)**
Implemented all 17 tasks (T1–T17). Created `src/squadron/pipeline/prompt_renderer.py`: `StepInstructions`, `ActionInstruction`, `CompletionResult` dataclasses, per-action-type builders (cf-op, dispatch, review, checkpoint, commit, compact, devlog), `render_step_instructions()` entry point. Added `StateManager.record_step_done()` public method. CLI: `--prompt-only`, `--next`, `--step-done`, `--verdict` flags on `sq run`. `/sq:run` slash command rewritten to consume prompt-only output. 30 unit tests, 4 integration tests, 12 CLI tests. Full verification walkthrough passed: all 6 slice pipeline steps cycle correctly, model aliases resolve, compact params resolve `{slice}` → target. 1193 total tests pass, zero regressions. Slice 153 complete.

## 20260403

**Slice 153: Prompt-Only Pipeline Executor — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/153-tasks.prompt-only-pipeline-executor.md`. 17 tasks (T1–T17): data models (`StepInstructions`, `ActionInstruction`, `CompletionResult`), per-action-type instruction builders (cf-op, dispatch, review, checkpoint, commit, compact, devlog), `render_step_instructions()` entry point, `StateManager.record_step_done()` public method, CLI flags (`--prompt-only`, `--next`, `--step-done`), integration test (full prompt-only cycle), `/sq:run` slash command rewrite to consume executor output, lint/verify, closeout. Test-with pattern throughout; 7 commit checkpoints. No blockers.

**Slice 153: Prompt-Only Pipeline Executor — Design Complete (Phase 4)**
Created `project-documents/user/slices/153-slice.prompt-only-pipeline-executor.md`. Adds `--prompt-only --next` mode to `sq run` that outputs one step's structured instructions (JSON) at a time without dispatching to LLMs. Each call advances state via existing `StateManager`. `--step-done <run-id> [--verdict V]` feeds back completion/verdict for checkpoint evaluation. New `prompt_renderer.py` module: pure function that expands step types via existing `expand()`, resolves models via `ModelResolver`, renders compact templates with pipeline params — produces `StepInstructions` dataclass. `/sq:run` slash command rewritten to consume executor output instead of hardcoding workflow. Added slice overview to `140-slices.pipeline-foundation.md` (item 13). Added future work item for external model dispatch to non-Claude-Code LLMs. Dependencies: [151].

**Slice 151: CLI Integration and End-to-End Validation — Implementation Complete (Phase 6)**
Implemented all tasks T1–T21. Created `src/squadron/cli/commands/run.py` (~300 lines): `run()` Typer command with positional `pipeline`/`target` args, `--model`, `--param key=value`, `--from`, `--resume`, `--dry-run`, `--validate`, `--list`, `--status`. `_resolve_target()` maps positional target to pipeline's first required param at runtime. `_assemble_params()` combines target, `--param`, and model. `_check_cf()` pre-flight verifies CF availability. `_run_pipeline()` async helper: load → validate → init_run → execute → finalize. `--resume` loads state, finds next step, re-executes. Implicit resume detection via `find_matching_run()` + `typer.confirm()`. Keyboard interrupt handling saves state and prints resume instructions. Rich output: Table for `--list`, Panel for `--status`, colored summary for execution results. Registered in `app.py`. 38 unit tests (`tests/cli/commands/test_run.py`), 5 integration tests (`tests/pipeline/test_cli_integration.py`). pyright 0 errors; ruff clean. Slice 151 marked complete — completes Pipeline Foundation initiative (140).

**Slice 151: CLI Integration and End-to-End Validation — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/151-tasks.cli-integration-and-end-to-end-validation.md`. 21 tasks (T1–T21): command skeleton + registration, Typer argument signatures, mutual exclusivity validation, `--list`, `--validate`, `--status` (with `"latest"` sentinel), `--dry-run`, parameter assembly helper, CF pre-flight check, core execution flow (`_run_pipeline` async helper + `asyncio.run` bridge), `--resume` flow, implicit resume detection (`find_matching_run` + `typer.confirm`), `--from` mid-process adoption, keyboard interrupt handling, 4 integration tests (full run, resume, from-step, dry-run no state file), exports/lint/pyright, verification and closeout. Test-with pattern throughout; 5 commit checkpoints. No blockers.

**Slice 151: CLI Integration and End-to-End Validation — Design Complete (Phase 4)**
Created `project-documents/user/slices/151-slice.cli-integration-and-end-to-end-validation.md`. Typer `sq run` command surface wiring executor, state manager, and pipeline loader into the CLI presentation layer. Options: `--slice`, `--model`, `--from`, `--resume`, `--dry-run`, `--validate`, `--list`, `--status`. Implicit resume detection when paused run matches pipeline+params. Rich terminal output for all display modes. Integration tests with mock action registries. Async executor bridged via `asyncio.run()`. Pre-flight CF check to avoid orphan state files. Dependencies: [148, 149, 150]. Completes the Pipeline Foundation initiative (140).

**Slice 150: Pipeline State and Resume — Implementation Complete (Phase 6)**
Implemented all tasks T1–T26. Created `src/squadron/pipeline/state.py` (~280 lines): Pydantic models (`RunState`, `StepState`, `CheckpointState`), `SchemaVersionError`, and `StateManager` with full public interface (10 methods). Atomic write via `.tmp` sibling + rename; `init_run` generates `run-{YYYYMMDD}-{slug}-{hash8}` IDs and auto-prunes; `make_step_callback` returns executor-ready closure; `_append_step` extracts verdict (last non-None) and outputs (last action); paused steps set `status="paused"` + `checkpoint` field; `finalize` writes terminal status; `load` validates schema version; `load_prior_outputs` reconstructs `dict[str, ActionResult]` defensively; `first_unfinished_step` scans definition in order; `list_runs` globs+filters+sorts; `find_matching_run` exact params match; `prune` skips paused runs. 43 unit tests + 2 integration tests (full run + resume) all pass. pyright 0 errors; ruff clean. Slice 150 marked complete.

**Slice 150: Pipeline State and Resume — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/150-tasks.pipeline-state-and-resume.md`. 26 tasks (T1–T26): test infrastructure (conftest fixtures), Pydantic models (`RunState`/`StepState`/`CheckpointState`/`SchemaVersionError`), `StateManager.__init__` + atomic write helper, `init_run`, `make_step_callback` + `_append_step`, `finalize`, `load` + `SchemaVersionError` check, `load_prior_outputs`, `first_unfinished_step`, `list_runs`, `find_matching_run`, `prune`, integration tests (full run + resume), exports/lint, closeout. Test-with pattern throughout; 3 commit checkpoints. No blockers.

**Slice 150: Pipeline State and Resume — Design Complete (Phase 4)**
Created `project-documents/user/slices/150-slice.pipeline-state-and-resume.md`. `StateManager` persists `RunState` JSON to `~/.config/squadron/runs/` after every completed step via `on_step_complete` callback. Pydantic models: `RunState`, `StepState`, `CheckpointState`. Atomic write pattern for corruption safety. `load_prior_outputs` reconstructs `dict[str, ActionResult]` from stored `action_results`. `find_matching_run` enables implicit resume detection. `prune(keep=10)` per-pipeline auto-prune on `init_run`. `SchemaVersionError` for forward-compatibility. Provides `StateManager` interface to slice 151 (CLI). Dependencies: [149]. Status: not_started.

**Slice 149: Pipeline Executor and Loops — Implementation Complete (Phase 6)**
Implemented all tasks T1–T10. Created `src/squadron/pipeline/executor.py` (~570 lines): `ExecutionStatus`/`StepResult`/`PipelineResult` result types; `resolve_placeholders` with dotted-path traversal; `LoopCondition`/`evaluate_condition` with closed 3-value enum; `ExhaustBehavior`/`LoopConfig`; `_cf_unfinished_slices` source fn + `_SOURCE_REGISTRY`; `_parse_source` with regex validation; `execute_pipeline` async core with sequential steps, `start_from` skip, checkpoint and failure propagation, `each` branch via `_execute_each_step`, and loop wrapping via `_execute_loop_step`. Replaced `steps/collection.py` stub with `EachStepType` (structural validation, empty `expand()`). Added `collection` import to `validate_pipeline` in `loader.py`. 52 unit tests in `test_executor.py`, 6 integration tests in `test_executor_integration.py`. 296 total pipeline tests pass; pyright 0 errors; ruff clean. Slice 149 marked complete.

**Slice 149: Pipeline Executor and Loops — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/149-tasks.pipeline-executor-and-loops.md`. 10 tasks (T1–T10): test infrastructure, result types (`ExecutionStatus`, `StepResult`, `PipelineResult`), placeholder resolution, loop condition grammar (`LoopCondition` enum + `evaluate_condition`), core sequential executor with checkpoint/failure handling, retry loop execution (`LoopConfig`, `ExhaustBehavior`), `EachStepType` implementation, source registry + `each` execution branch, integration tests, verification and closeout. Test-with pattern throughout; 3 commit checkpoints. No blockers.

**Slice 149: Pipeline Executor and Loops — Design Complete (Phase 4)**
Created `project-documents/user/slices/149-slice.pipeline-executor-and-loops.md`. Async executor engine takes validated `PipelineDefinition`, expands step types into action sequences, resolves `{param}` placeholders, and executes actions sequentially. Retry loops (`loop: {max, until, on_exhaust}`) with closed condition grammar (`review.pass`, `review.concerns_or_better`, `action.success`). `each` collection loop step type with source query dispatch (`cf.unfinished_slices`) and dot-path item binding (`{slice.index}`). Convergence loop strategy field acknowledged but stubbed (160 scope). Checkpoint pausing and action failure propagation. `on_step_complete` callback for state manager/CLI integration. Dependencies: [147, 148]. Unblocks slices 150 (State/Resume) and 151 (CLI).

## 20260402

**Slice 148: Pipeline Definitions and Loader — Implementation Complete (Phase 6)**
Implemented all 13 tasks (T1–T13). Created `schema.py` with `PipelineSchema` and `StepSchema` Pydantic v2 models — `@model_validator(mode="before")` unpacks YAML step grammar, scalar shorthand expansion (`devlog: auto` → `{"mode": "auto"}`), `to_definition()` converts to existing dataclasses. Created `loader.py` with `load_pipeline()` (path or name with project→user→built-in search), `discover_pipelines()` (scan+merge with source attribution), and `validate_pipeline()` (step type registry, model alias resolution, review template existence, param placeholder declaration checks). Four built-in pipeline YAMLs: slice-lifecycle (5 steps), review-only (1), implementation-only (2), design-batch (1 `each`). 43 new tests (12 schema + 11 loader + 9 validation + 11 integration), 995 total pass, pyright 0 errors, ruff clean. Slice 148 marked complete.

**Slice 148: Pipeline Definitions and Loader — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/148-tasks.pipeline-definitions-and-loader.md`. 13 tasks (T1–T13): Pydantic schema models + tests, four built-in pipeline YAML files, pipeline loader with 3-source discovery + tests, `discover_pipelines` + tests, semantic validation (`validate_pipeline`) + tests, integration tests for all built-ins, two commit checkpoints, closeout. Test-with pattern throughout. No blockers.

**Slice 148: Pipeline Definitions and Loader — Design Complete (Phase 4)**
Created `project-documents/user/slices/148-slice.pipeline-definitions-and-loader.md`. YAML pipeline grammar with Pydantic v2 schema validation (`schema.py`), loader with 3-source discovery (built-in → user → project), four built-in pipelines (slice-lifecycle, review-only, implementation-only, design-batch), and semantic validation (step types, model aliases, review templates, param references). Pydantic validates at boundary, converts to existing `PipelineDefinition`/`StepConfig` dataclasses. Dependencies: [147]. Unblocks slice 149 (Executor) and 151 (CLI).

**Slice 147: Compact Action and Step Types — Implementation Complete (Phase 6)**
Implemented all 13 tasks (T1–T13). Created compaction instruction template (`data/compaction/default.yaml`) with loader supporting user overrides from `~/.config/squadron/compaction/`. Implemented `CompactAction` with template-based CF instructions, `keep`/`summarize` params, and optional CF summarize call. Implemented four step types: `PhaseStepType` (3 registrations, 6-action expansion with optional review/checkpoint), `CompactStepType` (single compact action passthrough), `ReviewStepType` (review + optional checkpoint), `DevlogStepType` (single devlog with auto/explicit mode). 76 new tests (17 compact action + 17 phase + 7 compact step + 8 review step + 9 devlog step + 17 registry integration + 1 init), 952 total pass, pyright 0 errors, ruff clean. Slice 147 marked complete.

**Slice 147: Compact Action and Step Types — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/147-tasks.compact-action-and-step-types.md`. 13 tasks (T1–T13): compaction instruction template + loader, CompactAction implementation + tests, PhaseStepType (3-phase registration) + tests, CompactStepType + tests, ReviewStepType + tests, DevlogStepType + tests, registry integration tests, verification and closeout. Test-with pattern throughout. No blockers.

**Slice 147: Compact Action and Step Types — Design Complete (Phase 4)**
Created `project-documents/user/slices/147-slice.compact-action-and-step-types.md`. Compact action issues parameterized compaction instructions to CF with configurable `keep`/`summarize` params. Four step types: phase (cf-op→dispatch→review→checkpoint→commit), compact (single compact action), review (review + optional checkpoint), devlog (single devlog action). Step types are pure data transformers — `expand()` returns `(action_type, action_config)` tuples for the executor. Dependencies: [144, 145, 146]. Unblocks slice 148 (Pipeline Definitions) and 149 (Executor).

**Slice 146: Review and Checkpoint Actions — Implementation Complete (Phase 6)**
Implemented all 8 tasks (T1–T8). Extracted review persistence to shared `review/persistence.py` (`format_review_markdown`, `save_review_file`, `yaml_escape`, `SliceInfo`). Implemented `CheckpointAction` with `CheckpointTrigger` enum and trigger×verdict evaluation matrix. Implemented `ReviewAction` delegating to `run_review_with_profile()` with model/profile resolution, template input passthrough, review file persistence (non-fatal), and verdict/findings mapping. 57 new tests (13 persistence + 21 checkpoint + 21 review + 2 registry), 884 total pass, pyright 0 errors, ruff clean. Slice 146 marked complete.

---

## 20260331

**Slice 146: Review and Checkpoint Actions — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/146-tasks.review-and-checkpoint-actions.md`. 8 tasks (T1–T8): review persistence extraction + tests, CheckpointAction implementation + tests, ReviewAction implementation + tests, registry integration verification, full verification and closeout. Test-with pattern throughout. No blockers.

**Slice 146: Review and Checkpoint Actions — Design Complete (Phase 4)**
Created `project-documents/user/slices/146-slice.review-and-checkpoint-actions.md`. Two actions: ReviewAction delegates to `run_review_with_profile()`, populates `ActionResult.verdict` and `ActionResult.findings` from structured findings (slice 143), persists review files. CheckpointAction evaluates trigger (always, on-concerns, on-fail, never) against prior review verdict, returns paused/skipped result for executor interpretation. Includes persistence extraction from CLI to shared `review/persistence.py`. Dependencies: [143, 145]. Unblocks slices 147, 149, 150.

**Slice 145: Dispatch Action — Implementation Complete (Phase 6)**
Implemented all 6 tasks (T1–T6). Extracted `_ensure_provider_loaded` from `review_client.py` to shared `providers/loader.py`. Implemented `DispatchAction` with 5-level model resolution, profile resolution (explicit override > alias > SDK default), one-shot agent lifecycle, SDK response deduplication, token metadata passthrough, and comprehensive error handling (never raises). 26 new tests (17 dispatch + 9 loader), 827 total pass, pyright 0 errors, ruff clean. Slice 145 marked complete.

**Slice 145: Dispatch Action — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/145-tasks.dispatch-action.md`. 6 tasks (T1–T6): provider loader extraction + tests, DispatchAction implementation + tests, registry integration verification, full verification and closeout. Test-with pattern throughout. No blockers.

**Slice 145: Dispatch Action — Design Complete (Phase 4)**
Created `project-documents/user/slices/145-slice.dispatch-action.md`. Dispatch action resolves model alias via 5-level cascade (`ModelResolver`), creates one-shot agent through provider registry, sends prompt via `handle_message()`, captures response and token metadata. Follows review system's proven dispatch pattern. Includes provider loader extraction from `review_client.py` to shared location. Dependencies: [142, 102]. Unblocks slices 146, 147.

**Slice 144: Utility Actions — Implementation Complete (Phase 6)**
Implemented all 8 tasks (T1–T8). `CfOpAction` delegates to `cf_client._run()` with `pyright: ignore[reportPrivateUsage]` per project convention. `CommitAction` uses `subprocess.run()` with real `git init` test repos via `tmp_path`. `DevlogAction` handles DEVLOG insertion with date header deduplication and auto-generation from `prior_outputs`. All three actions satisfy `Action` protocol and auto-register at import time. 39 new tests, 800 total pass, pyright 0 errors, ruff clean. Slice 144 marked complete.

**Slice 144: Utility Actions — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/144-tasks.utility-actions.md`. 8 tasks (T1–T8): CfOpAction implementation + tests, CommitAction implementation + tests, DevlogAction implementation + tests, registry integration verification, full verification and closeout. Test-with pattern throughout. No blockers.

**Slice 144: Utility Actions — Design Complete (Phase 4)**
Created `project-documents/user/slices/144-slice.utility-actions.md`. Three action implementations: CfOpAction (set_phase, build_context, summarize via ContextForgeClient), CommitAction (git commit with semantic messages, no-op on clean tree), DevlogAction (structured DEVLOG entries auto-generated from pipeline state or explicit content). Each action auto-registers at import time. Mock I/O boundaries for testing. Unblocks slice 147 (step types).

---

## 20260330

**Slice 143: Structured Review Findings — Implementation Complete (Phase 6)**
Implemented all 10 tasks (T1–T10). Added `StructuredFinding` dataclass and `NOTE` severity to `review/models.py`. Extended parser with NOTE support, `category:` and `location:` tag extraction from finding blocks. Extended frontmatter formatter to emit `findings:` YAML array with structured entries. Extended `to_dict()` with `structured_findings` and `category`/`location` on findings. Injected structured output instructions into all review template system prompts via `review_client.py`. 761 tests pass (0 pre-existing failures), pyright 0 errors, ruff clean. Slice 143 marked complete.

**Slice 143: Structured Review Findings — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/143-tasks.structured-review-findings.md`. 10 tasks (T1–T10): models (StructuredFinding + NOTE severity), parser extensions (category/location extraction), frontmatter formatter, JSON serialization, prompt enhancement, full verification. Test-with pattern throughout. No blockers.

**Slice 143: Structured Review Findings — Design Complete (Phase 4)**
Created `project-documents/user/slices/143-slice.structured-review-findings.md`. Extends review output with machine-readable structured findings in YAML frontmatter. Adds `StructuredFinding` dataclass (id, severity, category, summary, location), `NOTE` severity level, parser extensions for category extraction, and prompt enhancement for all review templates. Single-file format: frontmatter is the programmatic index, prose body unchanged. Absorbs former slice 123 scope. Designed for slice 160 cross-iteration identity matching via (category, location) fingerprint.

**Slice 142: Pipeline Core Models and Action Protocol — Implementation Complete (Phase 6)**
Implemented full `src/squadron/pipeline/` package: 5 dataclasses in `models.py`, `Action` protocol + `ActionType` StrEnum + action registry, `StepType` protocol + `StepTypeName` StrEnum + step-type registry, `ModelResolver` (5-level cascade, pool: stub), stub modules for 7 actions and 5 step types, public `__init__` surface. 26 new tests across 3 test files — all pass. Pyright: 0 errors. Full repo: 707 passed, 8 pre-existing failures (unrelated). Slice 142 marked complete.

**Slice 142: Pipeline Core Models and Action Protocol — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/142-tasks.pipeline-core-models-and-action-protocol.md`. 14 tasks (T1–T14): package skeleton + stubs, data models, Action protocol + registry, StepType protocol + registry, ModelResolver (5-level cascade, pool: stub), pipeline `__init__` public surface, full test/pyright pass, verification walkthrough and closeout. Tests interleaved after each implementation group. No blockers.

**Slice 142: Pipeline Core Models and Action Protocol — Design Complete (Phase 4)**
Created `project-documents/user/slices/142-slice.pipeline-core-models-and-action-protocol.md`. Defines `ActionContext`, `ActionResult`, `PipelineDefinition`, `StepConfig`, `ValidationError` dataclasses; `Action` and `StepType` protocols; action/step-type registries; `ModelResolver` with 5-level cascade chain and `pool:` prefix error stub. Full `src/squadron/pipeline/` package layout with stub modules for all future action and step type files. No blockers — all design decisions resolved by architecture.

---

## 20260329

**Slice 141: Configuration Externalization — Implementation Complete (Phase 6)**
Created `src/squadron/data/` package with `data_dir()` two-path fallback. Transcribed 18 built-in model aliases to `data/models.toml`. Moved review templates to `data/templates/`. Refactored `aliases.py` (extracted `_load_aliases_from_file`, removed `BUILT_IN_ALIASES`). Updated `review/templates/__init__.py` to use `data_dir()`. Updated `pyproject.toml` force-include. Deleted `review/templates/builtin/`. Updated all tests referencing old paths. 681 tests pass (8 pre-existing failures unrelated to this slice). Slice 141 marked complete.

---

## 20260328

### Slice 141: Configuration Externalization — Task Breakdown Complete (Phase 5)
- Task file created: `project-documents/user/tasks/141-tasks.configuration-externalization.md`
- 11 tasks (T1–T11): create data/ package, copy templates, transcribe models.toml, refactor aliases.py, update template loader, update pyproject.toml, delete builtin/, verify, commit
- Test tasks interleaved after each implementation task (T5 after T4, T7 after T6)
- No blockers — straightforward reorganization, all design decisions resolved

### Slice 141: Configuration Externalization — Design Complete (Phase 4)
- Slice design created: `project-documents/user/slices/141-slice.configuration-externalization.md`
- Scope: move `BUILT_IN_ALIASES` Python dict → `src/squadron/data/models.toml`; move `review/templates/builtin/*.yaml` → `src/squadron/data/templates/`; add `DataLoader.data_dir()` utility; reserve `data/pipelines/` for slice 148
- Key decision: `data_dir()` uses same two-path fallback pattern as `install.py`'s `_get_commands_source()`
- Public APIs unchanged; merge precedence (built-ins → user overrides) preserved
- Slice plan entry already had (141) index materialized — no update needed

### Slice 140: Command Surface Parity — Task Breakdown (Phase 5) [revised]
- 11 tasks: create review.md (4 subcommands), create auth.md, delete 4 old files, handle run-slice, fix installer stale removal, smoke-test, close
- install.py gets stale-file cleanup (source-authoritative deletion, same pattern as CF daec117)
- Revised after design correction: consolidated dispatch pattern replaces per-subcommand files

### Slice 140: Command Surface Parity — Slice Design (Phase 4)
- Designed slash command parity: add `/sq:review arch`, deprecate `/sq:run-slice`
- Naming convention formalized: `commands/sq/{parent}-{child}.md` maps to `sq {parent} {child}`
- Existing names already follow convention — primary work is adding `review-arch.md` and deprecation banner
- Effort: 1/5 — markdown files and settings only, no Python changes

## 20260327

### Slice 128: Review Transport Unification — Implementation Complete (Phase 6)
- Reviews unified through `Agent.handle_message()` via provider registry — one code path for all profiles
- `runner.py` deleted (net -700 lines), `AsyncOpenAI` removed from review module
- `ProviderCapabilities` on all providers; file injection conditional on `can_read_files`
- `ProviderType`, `ProfileName`, `AuthType` enums — all identifiers defined once
- `OAuthFileStrategy` + `CodexProvider`/`CodexAgent` via MCP transport
- Profile renamed `codex` → `openai-oauth`; auth type `codex` → `oauth`
- `SDKAgent` → `ClaudeSDKAgent`; auth dispatch via `from_config` factory
- 687 tests pass; ruff/pyright clean

## 20260326

### Slice 124: Codex Agent Integration — Rewound
- Implementation completed but discovered fundamental architecture gap: review system bypasses Agent/AgentProvider Protocols entirely, tightly coupled to AsyncOpenAI and ClaudeSDKClient
- Codex subscription auth (OAuth token from `~/.codex/auth.json`) can't call Chat Completions API directly — must route through Codex runtime. But review system can't use non-OpenAI transports
- String-based dispatch (`if profile == "sdk"`, `if auth_type == "codex"`) throughout codebase
- Branch rewound to main. Slice superseded by 128

### Slice 128: Review Transport Unification — Slice Design Complete (Phase 4)
- Reviews use `Agent.handle_message()` via provider registry instead of bespoke transport implementations
- `ProviderCapabilities` dataclass: `can_read_files`, `supports_system_prompt`, `supports_streaming`
- Auth strategy dispatch via registry (eliminate if/elif chains), `"codex"` auth type → `"oauth"`
- `SDKAgent` → `ClaudeSDKAgent`, `runner.py` deleted (absorbed into agent)
- Enables Codex subscription reviews and future Anthropic API without review system changes

### Slice 128: Review Transport Unification — Task Breakdown Complete (Phase 5)
- 19 tasks: capabilities, auth refactor, OAuth strategy, SDK rename, Codex provider, runner.py migration, review_client unification, CLI auth cleanup, model aliases, validation, docs
- Test-with pattern throughout; 9 commit checkpoints
- Key sequence: capabilities first → auth cleanup → providers → review client unification → CLI cleanup

## 20260325

### Initiative Plan & 900-Band Maintenance Initiative
- Created `001-initiative-plan.squadron.md` retroactively documenting all initiatives (100, 140, 160, 200, 900)
- Created `900-arch.maintenance-and-refactoring.md` and `900-slices.maintenance-and-refactoring.md` as cross-cutting maintenance home

### Slice 124: Codex Agent Integration — Task Breakdown Complete (Phase 5)
- 12 tasks: transport evaluation, CodexAuthStrategy + tests, CodexAgent + tests, CodexProvider + tests, registration/profile + tests, model aliases, validation, documentation
- Test-with pattern throughout; 7 commit checkpoints
- Key design: Codex models already work for reviews via `openai` profile (Chat Completions API) — no review system changes; agentic provider is for spawn/task workflows only

### Slice 124: Codex Agent Integration — Slice Design Complete (Phase 4)
- Codex integration via MCP server path (`codex mcp-server`), not TypeScript SDK
- `CodexProvider`/`CodexAgent` implementing existing Protocols via MCP stdio client
- `CodexAuthStrategy` checks `~/.codex/auth.json` or `OPENAI_API_KEY`
- Review system gets third path: `_run_codex_review()` alongside SDK and non-SDK paths
- Lazy subprocess start, read-only sandbox for reviews

### Slice 127: Scoped Code Review & Prompt Logging — Implementation Complete (Phase 6)

- `git_utils.py`: `_find_slice_branch()`, `_find_merge_commit()`, `resolve_slice_diff_range()` — three-tier resolution (branch → merge commit → fallback to main)
- Prompt log: `_write_prompt_log()` writes `review-prompt-{ts}.md` at `-vvv`; prompt fields on `ReviewResult` populated at `-vv`
- `review_code()` uses `resolve_slice_diff_range()` instead of `diff = "main"` when slice number provided; `--diff` flag overrides
- Debug appendix `## Debug: Prompt & Response` appended to saved review markdown when prompt fields present
- 637 tests pass; 6 semantic commits on branch `127-slice.scoped-code-review-prompt-logging`

### Slice 127: Scoped Code Review & Prompt Logging — Task Breakdown Complete (Phase 5)

- 16 tasks: git_utils.py (branch/merge resolution + tests), ReviewResult prompt fields + tests, prompt log writer + tests, scoped diff wiring + tests, debug appendix + tests, validation pass, documentation
- Test-with pattern throughout; 6 commit checkpoints

### Slice 127: Scoped Code Review & Prompt Logging — Slice Design Complete (Phase 4)

- Scoped diff resolution: `sq review code 122` auto-resolves to slice branch's commits via merge-base or merge-commit detection, falls back to `--diff main`
- Prompt log persistence: `-vvv` writes full prompt to `~/.config/squadron/logs/review-prompt-{ts}.md`; `-vv` embeds debug appendix in saved review file
- New `git_utils.py` module; optional fields on `ReviewResult` for prompt/response capture

### Slice 122: Review Context Enrichment — Implementation Complete (Phase 6)

- Expanded `_FINDING_RE` to 5 formats; lenient fallback + synthesized finding when verdict/findings mismatch; `fallback_used` flag on `ReviewResult`; debug log at `~/.config/squadron/logs/review-debug.jsonl`
- CRITICAL consistency block added to all three builtin templates; `rules.py` module: `resolve_rules_dir()`, language detection, glob matching, template rules injection
- `review code` auto-detects language rules from diff paths; `--rules-dir`/`--no-rules` flags on review commands; template rules prepended from `rules/review.md` + `rules/review-{template}.md`
- Review file YAML aligned: `layer`, `sourceDocument`, `aiModel` (resolved ID), `status: complete`; `-vvv` debug output shows system/user prompt + injected rules
- 609 tests pass; 4 semantic commits on branch `122-slice.review-context-enrichment`

### Slice 122: Review Context Enrichment — Task Breakdown Complete (Phase 5)

- 19 tasks across: parser hardening (lenient parsing + fallback + debug log), template prompt hardening, `rules.py` auto-detection module, review CLI wiring (`--rules-dir`, `--no-rules`), review file YAML alignment, prompt debug output (`-vvv`)
- Slice design updated: added Section 5 (YAML alignment), Section 6 (prompt debug), prompt hardening renames to Section 7
- v0.2.6 tagged and published (slice 126 complete — `ContextForgeClient`)

---

## 20260324

### Slice 126: Context Forge Integration Layer — Implementation Complete

- `ContextForgeClient` implemented in `src/squadron/integrations/context_forge.py` with typed methods: `list_slices()`, `list_tasks()`, `get_project()`, `is_available()`
- `review.py` migrated: `_run_cf()` removed, `_resolve_slice_number()` uses `ContextForgeClient`
- Custom exceptions (`ContextForgeNotAvailable`, `ContextForgeError`) replace inline `typer.Exit`
- 16 unit tests for client, 3 new CLI error path tests, 7 existing resolve tests updated
- Markdown command files updated to CF's new command surface (`cf list slices`, `cf list tasks`)
- All 556 tests pass, pyright 0 errors, ruff clean

### Slice 126: Context Forge Integration Layer — Task Breakdown Complete

Task file at `project-documents/user/tasks/126-tasks.context-forge-integration-layer.md` (14 tasks: T1-T14). Three workstreams: client implementation with typed dataclasses (T1-T9), review.py migration (T10-T11), markdown command file updates and validation (T12-T14). Test-with pattern throughout.

### Slice 126: Context Forge Integration Layer — Design Complete

- Created `project-documents/user/slices/126-slice.context-forge-integration-layer.md`
- `ContextForgeClient` class in `src/squadron/integrations/context_forge.py` — typed methods replacing scattered `subprocess.run(["cf", ...])` calls
- Typed return dataclasses: `SliceEntry`, `TaskEntry`, `ProjectInfo`
- Custom exceptions (`ContextForgeNotAvailable`, `ContextForgeError`) separated from CLI layer
- Adapts to CF's new command surface (`cf list slices --json` replacing `cf slice list --json`)
- Markdown command files updated to reference new CF command names
- Scope limited to abstraction and migration — MCP transport, command aliasing deferred

### Slice 122: Review Context Enrichment — Design Complete

- Created `project-documents/user/slices/122-slice.review-context-enrichment.md`
- Two-pronged scope: (1) fix verdict/findings inconsistency (issue #5) via prompt hardening + parser post-processing guard, (2) auto-detect and inject language-specific rules for code reviews
- Language detection from diff file paths or glob matches, matched against rules files' `paths` frontmatter globs
- Rules directory resolution: `--rules-dir` flag > config `rules_dir` > `{cwd}/rules/` > `{cwd}/.claude/rules/`
- Slice/task reviews inject `rules/general.md` if present
- `--no-rules` flag to suppress all rule injection
- Legacy P0-P3 priorities extracted as optional copyable rules file, not baked into templates

## 20260323

### .env support for API keys

Added `python-dotenv` dependency. `load_dotenv()` runs at CLI startup (`cli/app.py`), so API keys (ANTHROPIC_API_KEY, OPENAI_API_KEY, OPENROUTER_API_KEY, etc.) can be set in a `.env` file instead of exported in the shell. `.env` already gitignored.

### Slice 121: Model Alias Metadata — Implementation Complete

- All 12 tasks (T1-T12) complete. 537 tests pass, pyright/ruff/format clean.
- `ModelPricing` TypedDict (input, output, cache_read, cache_write — USD per 1M tokens)
- `ModelAlias` extended with `private`, `cost_tier`, `notes`, `pricing` — all optional via inheritance pattern (`_ModelAliasRequired` base + `total=False`)
- All 12 `BUILT_IN_ALIASES` populated with curated metadata and pricing
- `load_user_aliases()` extracts metadata and pricing from TOML (inline and sub-table formats)
- `estimate_cost()` utility: alias name + token counts → USD float or None
- `sq models` compact by default; `sq models -v` shows Private, Cost, In $/1M, Out $/1M, Notes columns
- 21 new tests across T4 (3), T6 (6), T8 (6), T10 (6)

## 20260322

### Slice 121: Model Alias Metadata — Task Breakdown Complete

Task file at `project-documents/user/tasks/121-tasks.model-alias-metadata.md` (12 tasks: T1-T12). Three workstreams: type extensions with built-in metadata (T1-T4), TOML parsing and cost estimation (T5-T8), display updates and validation (T9-T12). Test-with pattern: each implementation task followed immediately by its test task.

### Slice 121: Model Alias Metadata — Design Complete

- Created `project-documents/user/slices/121-slice.model-alias-metadata.md`
- Extends `ModelAlias` TypedDict with optional `private` (bool), `cost_tier` (str), `notes` (str), `pricing` (ModelPricing) fields
- `ModelPricing` TypedDict: `input`, `output`, `cache_read`, `cache_write` (USD per 1M tokens)
- `total=False` on TypedDict for backward-compatible optional fields
- `cost_tier` values: free, cheap, moderate, expensive, subscription (new — for Max sub models)
- `estimate_cost()` utility: pure function, alias name + token counts → USD or None
- `sq models` gains Private, Cost, In $/1M, Out $/1M, Notes columns with compact mode
- Curated metadata and pricing for all 12 built-in aliases
- Also in this session: slice plan refactored (100-series trimmed, 160-series created for multi-agent), reindexing (161-172, 121-125), test fixes, template clarification, architecture docs updated to squadron naming

## 20260321

### Slice 120: Model Alias Registry — Implementation Complete

- All 22 tasks (T1-T22) complete. 514 tests pass, pyright/ruff clean.
- `review arch` renamed to `review slice` with backward-compat hidden alias + deprecation notice
- `src/squadron/models/aliases.py`: `resolve_model_alias()` with built-in defaults (opus, sonnet, haiku, gpt4o, o3, o1) and user `~/.config/squadron/models.toml` override
- `_infer_profile_from_model()` removed — alias registry handles all model→profile inference
- `_inject_file_contents()` in `review_client.py`: reads file contents and appends to prompt for non-SDK reviews; handles git diff and glob patterns for code reviews; size limits (100KB/file, 500KB total)
- `sq model list` command showing built-in + user aliases in a rich table
- 5 commits on branch `120-model-alias-registry`
- Post-impl live tests remain for PM (alias resolution, content injection, diff injection)

### Slice 120: Model Alias Registry — Task Breakdown Complete

Task file at `project-documents/user/tasks/120-tasks.model-alias-registry.md` (22 tasks: T1-T22). Three workstreams: rename review arch→slice (T1-T5), model alias registry with wiring (T6-T10), content injection for non-SDK reviews including code review diff/files (T11-T16), plus model list CLI (T17-T19) and slash command updates (T20-T22). Post-impl: live tests with OpenRouter, alias customization, diff injection.

### Slice 120: Model Alias Registry — Design Complete

- Slice design at `project-documents/user/slices/120-slice.model-alias-registry.md`
- Two problems addressed: (1) hardcoded model inference replaced by data-driven alias registry in `models.toml`, (2) non-SDK reviews fail because prompts contain file paths but models can't read files — content injection adds file contents to prompt for non-SDK path
- Ships built-in aliases (opus, sonnet, gpt4o, etc.) + user `~/.config/squadron/models.toml`
- Content injection: auto-reads files from `inputs` dict, appends to prompt; handles git diff for code reviews; 100KB/file, 500KB total limits
- New `sq model list` command

### Slice 119: Review Provider & Model Selection — Implementation Complete

- All 20 implementation tasks (T1-T20) complete. 491 tests pass.
- New `review_client.py` with `run_review_with_profile()` — SDK delegation or OpenAI-compatible API path
- `--profile` flag on all `sq review` commands (arch, tasks, code)
- `_resolve_profile()`: CLI flag → model inference → template → config → sdk fallback
- `_infer_profile_from_model()`: opus→sdk, gpt-4o→openai, slash→openrouter
- `load_all_templates()` loads from built-in + `~/.config/squadron/templates/` (user override by name)
- `default_review_profile` config key added
- Slash commands updated with `--profile` documentation
- Slice 120 (Model Alias Registry) added to slice plan as next priority
- Post-impl live tests remain for PM

### Slice 119: Review Provider & Model Selection — Task Breakdown Complete

Task file created at `project-documents/user/tasks/119-tasks.review-provider-model-selection.md` (20 tasks: T1-T20). Key task groups: template profile field (T1-T2), config key + profile resolution (T3-T7), review client with provider routing (T9-T10), CLI `--profile` flag (T12-T13), user template loading (T15-T16), slash command updates (T18), validation (T19-T20). Post-impl: live tests with OpenRouter, OpenAI, user templates, config defaults.

### Slice 119: Review Provider & Model Selection — Design Complete

- Slice design created at `project-documents/user/slices/119-slice.review-provider-model-selection.md`
- Scope: decouple review execution from hardcoded Claude SDK. Add `--profile` flag, `profile` field in templates, user-customizable templates from `~/.config/squadron/templates/`, config default `default_review_profile`, model-to-profile inference
- Key decision: SDK path preserved exactly (delegation), non-SDK path uses `AsyncOpenAI` directly via existing profile/auth infrastructure
- Known limitation: non-SDK reviews have no tool access (prompt-only)
- Slice plan updated: new slice 119 inserted, old 119 (Conversation Persistence) re-indexed to 134

---

## 20260320

### Slice 118: Claude Code Commands — Composed Workflows — In Progress

- Implementation complete (T1-T9 checked off). Remaining items are PM manual tests.
- Commits:
  - `a2058c9` feat: add /sq:run-slice command, update review commands with number shorthand
  - `f31cd44` test: update install tests for 9 command files
- What works: all 448 tests pass, ruff/pyright clean, wheel bundles `run-slice.md`, install produces 9 commands
- Scope expanded from original design:
  - Updated `review-tasks.md`, `review-code.md`, `review-arch.md` with bare number shorthand (e.g., `/sq:review-tasks 191`)
  - Path resolution via `cf slice list --json` / `cf task list --json` — worktree-aware, CF owns conventions
  - `review-arch` performs holistic check: slice design vs. architecture doc + slice plan entry
  - Review file persistence to `project-documents/user/reviews/` with YAML frontmatter
  - DEVLOG entry step added to `run-slice` pipeline (Step 5)
- Pending: PM live tests (`/sq:run-slice` on real slice, `/sq:review-tasks {nnn}` shorthand), prompt iteration

---

## 20260317

### Slice 118: Claude Code Commands — Composed Workflows — Task Breakdown Complete

Task file created at `project-documents/user/tasks/118-tasks.claude-code-commands-composed-workflows.md` (6 tasks: T1-T6). T1 create `run-slice.md` command file with full pipeline prompt. T2 update install tests (8→9 expected files). T3 commit. T4 validation pass. T5 commit. T6 verify wheel bundling. Post-impl: live test on a real slice, iterate on prompt.

### Slice 118: Claude Code Commands — Composed Workflows — Design Complete

Slice design created at `project-documents/user/slices/118-slice.claude-code-commands-composed-workflows.md`.

Scope: Single `/sq:run-slice` command that automates the full slice lifecycle — phase 4 (design) → phase 5 (task breakdown + review) → compact → phase 6 (implementation + code review). Chains `cf set/build` with `sq review tasks/code` and `/compact`. Review gates: PASS proceeds, FAIL stops for human input. Smart resume (skip completed phases) documented as future enhancement. Lives in existing `sq/` namespace — no new directories or Python code.

---

## 20260307

### Slice 117: PyPI Publishing & Global Install — Task Breakdown Complete

Task file created at `project-documents/user/tasks/117-tasks.pypi.md` (13 tasks: T1-T13). T1-T2 version flag + test, T3 commit. T4-T5 metadata polish + wheel verification, T6 commit. T7-T8 GitHub Actions CI (test + publish jobs), T9 commit. T10 README install section, T11 commit. T12-T13 validation pass + commit. Post-implementation section documents manual PM steps (PyPI account, first publish, smoke test).

---

## 20260306

### Slice 117: PyPI Publishing & Global Install — Design Complete

Slice design created at `project-documents/user/slices/117-slice.pypi.md`.

Scope: Publish `squadron` to PyPI for global install via `pipx install squadron` / `uv tool install squadron`. SemVer versioning (start at 0.1.0, single-sourced in pyproject.toml). `sq --version` via `importlib.metadata`. pyproject.toml metadata polish (classifiers, license, project-urls). GitHub Actions CI workflow (lint+test on push, publish to TestPyPI+PyPI on version tag). README install instructions.

Key decisions: SemVer over CalVer, tag-driven manual releases, `pypa/gh-action-pypi-publish` with OIDC trusted publisher preferred, TestPyPI dry-run before real publish, `astral-sh/setup-uv` for CI.

### Slice 116: Claude Code Commands — Implementation Complete

All 15 tasks complete. Eight command files in `commands/sq/` (`spawn.md`, `task.md`, `list.md`, `shutdown.md`, `review-arch.md`, `review-tasks.md`, `review-code.md`, `auth-status.md`). `pyproject.toml` updated with `force-include` for wheel bundling. `install.py` with `install_commands`/`uninstall_commands` wired into Typer app. 11 tests (8 install/uninstall + 3 source verification). 446 total tests pass, pyright clean, ruff clean.

---

## 20260305

### Slice 116: Claude Code Commands — sq Wrappers — Design Complete

Slice design created at `project-documents/user/slices/116-slice.sq-slash-command.md`.

Scope: Eight Claude Code slash command files (`/sq:spawn`, `/sq:task`, `/sq:list`, `/sq:shutdown`, `/sq:review-arch`, `/sq:review-tasks`, `/sq:review-code`, `/sq:auth-status`) in `commands/sq/`. Install/uninstall CLI commands (`sq install-commands`, `sq uninstall-commands`). Command files bundled in package wheel via `pyproject.toml`. Commands are thin prompts that instruct Claude to execute the corresponding `sq` CLI command via Bash.

### Slice 116: Claude Code Commands — Task Breakdown Complete

Task file created at `project-documents/user/tasks/116-tasks.sq-slash-command.md` (15 tasks). T1 directory setup, T2-T9 command file authoring (one per command), T10 package bundling, T11-T12 install/uninstall CLI, T13-T14 tests, T15 validation.

---

### Slice 115: Project Rename — orchestration → squadron — Complete

- Renamed `src/orchestration/` → `src/squadron/`, updated pyproject.toml (name, dual entry points: `sq` + `squadron`)
- Updated all imports across 127 .py files (61 src + 66 tests)
- Config paths: `~/.config/squadron/`, `.squadron.toml`, `~/.squadron/` for daemon
- Added config migration logic in `config/manager.py` — copies old config dir on first run, writes `MIGRATED.txt`
- Renamed `OrchestrationEngine` → `SquadronEngine`
- Updated README.md, docs/COMMANDS.md, docs/TEMPLATES.md
- 435 tests pass, `sq --help` and `squadron --help` both work

---

## 20260301

### Slice 114: Auth Strategy & Credential Management — Implementation Complete

Implemented all 18 tasks for slice 114. Added `AuthStrategy` protocol and `ApiKeyStrategy` in `providers/auth.py` — direct extraction of existing credential resolution from `OpenAICompatibleProvider`, same behavior. Added `resolve_auth_strategy()` factory and `AUTH_STRATEGIES` registry. Extended `ProviderProfile` with `auth_type` field (default `"api_key"`). Refactored `OpenAICompatibleProvider.create_agent()` to delegate to the strategy. Added `orchestration auth login <profile>` and `orchestration auth status` CLI commands. 435 tests pass; pyright and ruff clean.

New files: `src/orchestration/providers/auth.py`, `src/orchestration/cli/commands/auth.py`, `tests/providers/test_auth.py`, `tests/providers/test_auth_resolution.py`, `tests/cli/test_auth.py`.

---

### Slice 114: Auth Strategy & Credential Management — Design Complete

Research into OpenAI OAuth revealed the API has no general OAuth2 flow — authentication is purely key-based (project-scoped, service account). OAuth exists only for Codex subscription access (browser-based, ChatGPT Plus/Pro/Teams). This finding reshaped slice 114 from "implement OAuth" to "formalize auth strategy abstraction with API key as concrete implementation."

Documents created:
- `project-documents/user/slices/114-slice.oauth-advanced-auth.md` — slice design
- Updated `100-slices.orchestration-v2.md` — revised slice 114 entry, new slice 116 (Codex Agent Integration)

Key decisions:
- `AuthStrategy` protocol with `get_credentials()`, `refresh_if_needed()`, `is_valid()`
- `ApiKeyStrategy` as direct extraction of existing provider credential resolution
- `auth_type` field on `ProviderProfile` for strategy dispatch
- CLI `auth login`/`auth status` commands for credential validation
- Codex agent integration (OAuth) deferred to new slice 116

Scope: `AuthStrategy` protocol, `ApiKeyStrategy`, `ProviderProfile.auth_type`, CLI auth commands, provider refactor

| Hash | Description |
|------|-------------|
| `156d78f` | docs: add slice 114 design (auth strategy) and slice 116 entry (codex) |

---

### Slice 113: Provider Variants & Registry — Post-Merge Fix

Live testing with OpenRouter/Kimi revealed `credentials` dropped at daemon boundary. `SpawnRequest` was missing the field; fixed in `server/models.py` and `routes/agents.py`. Verified working end-to-end with OpenRouter profile.

| Hash | Description |
|------|-------------|
| `146ed4b` | fix: pass credentials through SpawnRequest to AgentConfig |

---

## 20260228

### Slice 113: Provider Variants & Registry — Complete

All 15 tasks implemented across 4 groups. 408 tests passing (31 new). Zero pyright/ruff errors on src/.

**Key commits:**
| Hash | Description |
|------|-------------|
| `b1831c0` | feat: add provider profile model and TOML loading |
| `7eb9eff` | feat: enhance credential resolution and default headers support |
| `45ec6b8` | feat: add --profile flag to spawn and models command |

**What works:**
- `ProviderProfile` frozen dataclass with 4 built-ins: `openai`, `openrouter`, `local`, `gemini`
- TOML loading from `~/.config/orchestration/providers.toml`; user profiles override built-ins
- Credential resolution chain: `config.api_key` → profile env var → `OPENAI_API_KEY` → localhost placeholder
- OpenRouter `default_headers` via `AsyncOpenAI(default_headers=...)` constructor
- `orchestration spawn --profile openrouter --model x` fully functional
- `orchestration models --profile local` for model discovery (direct HTTP, no daemon)

**Key decisions:**
- Profiles are data (frozen dataclass), not subclasses — all three variants reuse `OpenAICompatibleProvider`
- Localhost placeholder: `"not-needed"` when no API key and `base_url` starts with `http://localhost` or `http://127.0.0.1`
- `models` command calls `/v1/models` directly via `httpx`, bypassing daemon

**Next:** Slice 114 (OAuth & Advanced Auth)

---

### Slice 113: Provider Variants & Registry — Phase 4 Design Complete

Slice design created at `project-documents/user/slices/113-slice.provider-variants.md`.

Key design decisions:
- **Profiles, not subclasses**: All three variants (OpenRouter, local, Gemini) are configurations of `OpenAICompatibleProvider`, bundled as named `ProviderProfile` entries.
- **Separate `providers.toml`**: Structured profile data lives in its own file (`~/.config/orchestration/providers.toml`), not in the flat `config.toml`.
- **`--profile` CLI flag**: New flag on spawn command, separate from `--provider`. Profile provides defaults; CLI flags override.
- **Localhost auth bypass**: Local model servers get a placeholder API key (`"not-needed"`) instead of raising `ProviderAuthError`.
- **`models` command**: Direct HTTP query to `/v1/models` for model discovery, bypasses daemon.

| Hash | Description |
|------|-------------|
| `e399e5f` | docs: add slice 113 design |

### Slice 112: Local Server & CLI Client — Phase 7 Implementation Complete

All 27 tasks (T1-T27) implemented. 35 new tests (377 total project tests passing). Zero pyright/ruff errors on src/.

**Key commits:**
| Hash | Description |
|------|-------------|
| `e8350b2` | chore: add httpx dependency |
| `46c4380` | feat: add test infrastructure for server and client (T2) |
| `ae55e8b` | feat: implement OrchestrationEngine (T3) |
| `5301aa5` | test: add OrchestrationEngine tests (T4) |
| `d0591f6` | feat: add server models and health route (T5) |
| `73acbd8` | feat: add agent CRUD and messaging routes (T6) |
| `4a0dccb` | feat: add app factory and route tests (T7, T8) |
| `51b6f3d` | feat: add daemon module with PID management (T9) |
| `f6c74af` | feat: server core checkpoint (T11) |
| `48a5068` | feat: add DaemonClient (T12-T14) |
| `1733974` | feat: add serve command (T15-T16) |
| `c908121` | refactor: CLI commands use DaemonClient (T17-T20) |
| `2079bfd` | feat: add message and history commands (T21-T23) |
| `1de8866` | feat: validation pass and format fixes (T25) |
| `ca8b1f5` | test: add daemon integration test (T26-T27) |

**New modules:**
- `src/orchestration/server/engine.py` — OrchestrationEngine with agent lifecycle and conversation history
- `src/orchestration/server/models.py` — Pydantic request/response schemas
- `src/orchestration/server/routes/` — FastAPI agent CRUD, messaging, and health routes
- `src/orchestration/server/app.py` — Application factory
- `src/orchestration/server/daemon.py` — PID management, signal handling, dual-transport server
- `src/orchestration/client/http.py` — DaemonClient with Unix socket / HTTP transport
- `src/orchestration/cli/commands/serve.py` — `orchestration serve` with --status/--stop
- `src/orchestration/cli/commands/message.py` — `orchestration message`
- `src/orchestration/cli/commands/history.py` — `orchestration history` with --limit

**Refactored modules:**
- `spawn.py`, `list.py`, `task.py`, `shutdown.py` — all use DaemonClient instead of direct registry

**Next:** Slice 113 (Provider Variants & Registry).

---

### Slice 112: Local Server & CLI Client — Slice Design Complete

**Documents created:**
- `user/slices/112-slice.local-daemon.md` — slice design
- `user/slices/112-slice.local-daemon-agent-brief.md` — technical brief from PM

**Scope:** Persistent daemon process (`orchestration serve`) holding agent registry, agent instances, and conversation history in memory. CLI commands become thin clients communicating with daemon via Unix domain socket (primary) or localhost HTTP (secondary). New `OrchestrationEngine` composes existing `AgentRegistry` and adds conversation history tracking. FastAPI app serves both transports. New commands: `serve`, `message`, `history`. Existing commands (`spawn`, `list`, `task`, `shutdown`) refactored to use `DaemonClient`.

**Key design decisions:**
- `OrchestrationEngine` composes `AgentRegistry` (not subclass/replace) — registry manages lifecycle, engine adds history and coordination
- Dual transport: Unix socket (`~/.orchestration/daemon.sock`) for CLI, HTTP (`127.0.0.1:7862`) for external consumers — same FastAPI app serves both via two uvicorn instances
- `httpx.AsyncHTTPTransport(uds=path)` for CLI→daemon Unix socket communication
- Explicit `orchestration serve` — no auto-start magic, predictable daemon lifecycle
- All agent commands route through daemon — one execution path, enables future observability
- Conversation history at engine level (not just agent-internal) — provider-agnostic, supports `history` command
- Agent lifecycle categories: ephemeral (task) and session (spawn+message) — behavioral patterns, not formal types
- PID file + socket file in `~/.orchestration/` — stale file detection on startup
- `review` and `config` commands left unchanged for now (review uses SDK directly, config is stateless)

**Commit:** `dcab7a9` docs: add slice 112 design for local daemon & CLI client

**Next:** Phase 5 (Task Breakdown) on slice 112.

---

## 20260226

### Slice 111: OpenAI-Compatible Provider Core — Phase 7 Implementation Complete

All 17 tasks (T1-T17) implemented. 41 new tests (342 total project tests passing). Zero pyright/ruff errors on src/.

**Key commits:**
| Hash | Description |
|------|-------------|
| `3965380` | chore: add openai>=1.0.0 dependency |
| `b4d1da9` | feat: add OpenAI provider translation module with tests |
| `c53c64c` | feat: add OpenAICompatibleProvider with tests |
| `fba88e6` | feat: implement OpenAICompatibleAgent with tests |
| `ab12531` | feat: add OpenAI-compatible provider |
| `4c547c7` | feat: add provider auto-loader and --base-url to spawn command |

**What was added:**
- `providers/openai/` package: `translation.py`, `provider.py`, `agent.py`, `__init__.py`
- `OpenAICompatibleProvider`: API key resolution (config → env → ProviderAuthError), `AsyncOpenAI` client construction, `base_url` pass-through, explicit `ProviderError` on missing model
- `OpenAICompatibleAgent`: conversation history, streaming accumulation, tool call reconstruction by chunk index, full error mapping (AuthenticationError→ProviderAuthError, RateLimitError→ProviderAPIError(429), APIStatusError→ProviderAPIError(status_code), APIConnectionError→ProviderError, APITimeoutError→ProviderTimeoutError)
- `translation.py`: `build_text_message`, `build_tool_call_message`, `build_messages` — pure functions, independently testable
- Auto-registration: `get_provider("openai")` available after import
- `_load_provider(name)` auto-loader in `spawn.py` — lazy `importlib.import_module` triggers provider registration; silent `ImportError` catch; benefits all providers retroactively
- `--base-url` flag on `spawn` command — passed through to `AgentConfig.base_url`

**Architecture note:** Per-agent `AsyncOpenAI` client (not per-provider) — credentials and `base_url` are per-agent concerns. Accumulate full stream then yield complete `Message` objects to preserve `AsyncIterator[Message]` Protocol contract. Validated that `AgentProvider` Protocol generalizes beyond Anthropic with zero core engine changes.

**Issues logged:** None.

**Next:** Slice 112 (Provider Variants & Registry — OpenRouter, local, Gemini configs + model alias profiles).

### Slice 111: OpenAI-Compatible Provider Core — Slice Design Complete

**Documents created:**
- `user/slices/111-slice.openai-provider-core.md` — slice design (410 lines)

**Scope:** `OpenAICompatibleProvider` and `OpenAICompatibleAgent` using the `openai` Python SDK's `AsyncOpenAI` client with `base_url` override. Single implementation covers OpenAI, OpenRouter, Ollama/vLLM, and Gemini-compatible endpoints. Validates that `AgentProvider` Protocol generalizes beyond Anthropic with no core engine changes. Also fixes provider auto-loader gap in `spawn.py` and adds `--base-url` CLI flag.

**Key design decisions:**
- Per-agent `AsyncOpenAI` client (not per-provider) — credentials and `base_url` are per-agent concerns
- Accumulate full stream response before yielding `Message` objects — preserves `AsyncIterator[Message]` Protocol contract; streaming-through deferred as future evolution
- No silent model default — `ProviderError` if `config.model` is None (billing concern)
- Tool calls surfaced as `system` Messages with metadata; no execution (needs message bus + executor, future slice)
- `_load_provider(name)` auto-loader via `importlib.import_module` in `spawn.py` — silent `ImportError` catch; benefits all current and future providers retroactively
- Model alias / provider profile registry (`codex_53` → openai + model + base_url) deferred to slice 112

**Commit:** `864ed9c` docs: add slice design for 111-openai-provider-core

### Slice 111: OpenAI-Compatible Provider Core — Task Breakdown Complete

Task file created at `project-documents/user/tasks/111-tasks.openai-provider-core.md` (169 lines, 17 tasks). Test-with pattern applied; two commit checkpoints (T11 after providers/openai, T17 after CLI changes).

**Tasks overview:** T1 add dependency → T2 test infra → T3-T4 translation.py → T5-T6 provider.py → T7-T8 agent.py → T9-T10 `__init__.py` registration → T11 commit → T12-T13 auto-loader → T14-T15 `--base-url` flag → T16 full validation → T17 commit.

**Commit:** `5f4a7be` docs: add task breakdown for 111-openai-provider-core

---

## 20260223

### Model selection support (Issue #2)

Added `--model` flag to all review commands and spawn. Model threads through the full pipeline: config key (`default_model`) → ReviewTemplate YAML field → runner → `ClaudeAgentOptions`. Precedence: CLI flag → config → template default → None (SDK default). Template defaults: `opus` for arch/tasks, `sonnet` for code. Model shown in review output panel header at all verbosity levels. 17 new tests (298 total).

**Commit:** `9eae0f7` feat: add model selection support to review and spawn commands

### Rate limit handling fix (Issue #1)

Replaced the retry-entire-session loop (3 retries, 10s delay each) with a `receive_response()` restart on the same session. The SDK's `MessageParseError` (not publicly exported) fires on `rate_limit_event` messages the CLI emits while handling API rate limits internally. Fix catches `ClaudeSDKError` (public parent) with string match, restarts the async generator on the same connected session (anyio channel survives generator death), circuit breaker at 10 retries. Eliminates ~10-20s unnecessary delay. 3 new tests (301 total).

### Post-implementation: code review findings and fixes

Ran `orchestration review code` against its own codebase. Addressed three findings from the review:

1. **`_coerce_value` guard** — added explicit `str` check and `ValueError` for unsupported types (was silently falling through)
2. **Unknown config key warnings** — `load_config` now logs warnings for unrecognized keys in TOML files (catches typos)
3. **Double template loading** — `_execute_review` now accepts `ReviewTemplate` directly instead of re-loading by name
4. **CLAUDE.md exception** — documented that public-facing docs (`docs/`, root `README.md`) are exempt from YAML frontmatter rule

Also added rate-limit retry (3 attempts, 10s delay) in runner and friendlier CLI error message.

**Deferred findings** (logged for future work):
- Duplicated `cli_runner` fixture across 6 test files → promote to root `conftest.py`
- `_resolve_verbosity` can't override config back to 0 from CLI → consider `--quiet` flag

---

## 20260222

### Slice 106: M1 Polish & Publish — Phase 7 Implementation Complete

All 22 tasks (T1-T22) implemented. 49 new tests (28 config + 12 verbosity + 6 rules + 3 cwd), 281 total project tests passing. Zero pyright/ruff errors on src/.

**Key commits:**
| Hash | Description |
|------|-------------|
| `9034843` | feat: add persistent config system with TOML storage |
| `196f03f` | feat: add config CLI commands (set, get, list, path) |
| `b002801` | feat: add verbosity levels and improve text colors |
| `b945fb4` | feat: add --rules flag, config-based cwd, and rules injection |
| `85c953e` | chore: format and fix pyright issues in slice 106 code |
| `eb44cef` | docs: add README, COMMANDS, and TEMPLATES documentation |

**What was added:**
- `config/` package: typed key definitions, TOML load/merge/persist manager, user + project config with precedence
- Config CLI: `config set/get/list/path` commands
- Verbosity levels (0/1/2) with `-v`/`-vv` flags on all review commands
- Text color improvements: bright severity badges, white headings, default foreground body text
- `--rules` flag on `review code` with config-based `default_rules`
- Config-based `--cwd` resolution across all review commands
- Documentation: `docs/README.md`, `docs/COMMANDS.md`, `docs/TEMPLATES.md`

**Architecture note:** `config.py` restructured to `config/__init__.py` package (same pattern as templates in slice 105) to coexist with `keys.py` and `manager.py`. TOML reading via stdlib `tomllib`, writing via `tomli-w`.

### Slice 106: M1 Polish & Publish — Phase 5 Task Breakdown Complete

Task file created at `project-documents/user/tasks/106-tasks.m1-polish-and-publish.md` (219 lines, 22 tasks).

**Commit:** `09a69cd` docs: add slice 106 task breakdown (m1-polish-and-publish)

### Slice 105: Review Workflow Templates — Phase 7 Implementation Complete

All 22 tasks (T1-T22) implemented. 76 review-specific tests, 226 total project tests passing. Zero pyright/ruff errors. Build succeeds.

**Key commits:**
| Hash | Description |
|------|-------------|
| `29c53e2` | feat: add pyyaml dependency |
| `dc8a4a4` | feat: add review result models |
| `fad9109` | feat: add ReviewTemplate, YAML loader, and registry |
| `1d29679` | refactor: restructure templates as package with builtin directory |
| `ea5839d` | feat: add built-in review templates (arch, tasks, code) |
| `a430358` | feat: add review result parser |
| `bff53a0` | feat: add review runner |
| `2feca18` | feat: add review CLI subcommand |
| `74eca88` | chore: review slice 105 final validation pass |

**Architecture note:** `templates.py` moved to `templates/__init__.py` package to coexist with `templates/builtin/` YAML directory. SDK literal types handled via `type: ignore` comments since template values are dynamic from YAML.

### Slice 105: Review Workflow Templates — Phase 5 Task Breakdown Complete

Task file created at `project-documents/user/tasks/105-tasks.review-workflow-templates.md` (210 lines, 22 tasks). Covers result models, YAML loader/registry, three built-in templates (arch, tasks, code), result parser, review runner, and CLI subcommand. Test-with ordering applied throughout; commit checkpoints after each stable milestone. Merge conflict in slice frontmatter resolved by PM prior to task creation.

---

## 20260220

### Slice 103: CLI Foundation & SDK Agent Tasks — Implementation Complete

**Commits:**
| Hash | Description |
|------|-------------|
| `8e76a6d` | feat: add Typer app scaffolding and pyproject.toml entry point |
| `4a4a478` | feat: implement CLI commands (spawn, list, task, shutdown) and test infra |
| `faaa5cc` | feat: refactor CLI commands to plain functions + add command tests |
| `b58d539` | feat: add integration smoke test + fix lint/type issues |

**What works:**
- 150 tests passing (22 new + 128 existing), ruff clean, pyright zero errors on src/ and tests/cli/
- `orchestration spawn --name NAME [--type sdk] [--provider P] [--cwd PATH] [--system-prompt TEXT] [--permission-mode MODE]`
- `orchestration list [--state STATE] [--provider P]` — rich table with color-coded state
- `orchestration task AGENT PROMPT` — `handle_message` async bridge, displays text and tool-use summaries
- `orchestration shutdown AGENT` / `orchestration shutdown --all` — individual and bulk with `ShutdownReport`
- `pyproject.toml` entry point registered; `orchestration --help` works
- All commands use `asyncio.run()` bridge pattern (sync Typer → async registry/agent)
- Unit tests: mocked registry via `patch_registry` fixture; integration smoke test: real registry + mock provider

**Key decisions:**
- Commands registered as plain functions via `app.command("name")(fn)` — not sub-typers. Sub-typers created nested groups (`spawn spawn --name`) rather than flat commands (`spawn --name`).
- `task` command uses `agent.handle_message(message)` (the actual Agent Protocol method), not a hypothetical `query()` method referenced in the task design
- `asyncio.run()` per command invocation — no persistent event loop, clean for CLI use
- Integration test patches the provider registry (not the agent registry) to use a mock SDK provider

**Issues logged:** None.

**Next:** Slice 5 (SDK Client Warm Pool).

---

## 20260219

### Slice 103: CLI Foundation & SDK Agent Tasks — Design and Task Breakdown Complete

**Documents created:**
- `user/slices/103-slice.cli-foundation.md` — slice design
- `user/tasks/103-tasks.cli-foundation.md` — 11 tasks, test-with pattern

**Scope:** Typer CLI with four commands (`spawn`, `list`, `task`, `shutdown`) wiring the full path from terminal through Agent Registry and SDK Agent Provider to Claude execution. Async bridge via `asyncio.run()`. Rich output formatting (tables for `list`, styled text for responses). User-friendly error handling for all known failure modes. `pyproject.toml` script entry point. Integration smoke test (spawn → list → task → shutdown). **Completes Milestone 1.**

**Next:** Phase 7 (Implementation) on slice 103.

---

### Slice 102: Agent Registry & Lifecycle — Implementation Complete

**Commits:**
| Hash | Description |
|------|-------------|
| `23747c4` | feat: add AgentRegistry core with models, errors, spawn, and lookup |
| `9a40ff3` | feat: add list_agents filtering and individual shutdown to AgentRegistry |
| `26f61b4` | feat: add bulk shutdown and singleton accessor to AgentRegistry |
| `16d2a8a` | chore: fix linting, formatting, and type errors for agent registry |
| `a045636` | docs: mark slice 102 (Agent Registry & Lifecycle) as complete |

**What works:**
- 127 tests passing (26 new + 101 existing), ruff clean, pyright zero errors on src/ and new test file
- `AgentInfo` and `ShutdownReport` Pydantic models in `core/models.py`
- `AgentRegistryError`, `AgentNotFoundError`, `AgentAlreadyExistsError` error hierarchy
- `AgentRegistry.spawn()`: resolves provider, creates agent, tracks by unique name
- `AgentRegistry.get()`, `has()`: lookup by name with proper error raising
- `AgentRegistry.list_agents()`: returns `AgentInfo` summaries with optional state/provider filtering
- `AgentRegistry.shutdown_agent()`: always-remove semantics (agent removed even if shutdown raises)
- `AgentRegistry.shutdown_all()`: best-effort bulk shutdown returning `ShutdownReport`
- `get_registry()` / `reset_registry()` singleton accessor

**Key decisions:**
- Imports moved above error class definitions (ruff E402) — error classes placed after imports, not before
- `AgentInfo.provider` sourced from stored `AgentConfig`, not from the agent object (registry owns this mapping)
- `shutdown_agent()` uses try/finally to guarantee removal regardless of shutdown errors
- `shutdown_all()` collects errors per-agent without aborting — returns structured `ShutdownReport`
- MockAgent uses `set_state()` method instead of direct `_state` access to satisfy pyright's `reportPrivateUsage`

**Issues logged:** None.

**Next:** Slice 4 (CLI Foundation & SDK Agent Tasks).

---

### Slice 102: Agent Registry & Lifecycle — Design and Task Breakdown Complete

**Documents created:**
- `user/slices/102-slice.agent-registry.md` — slice design
- `user/tasks/102-tasks.agent-registry.md` — 14 tasks, test-with pattern

**Scope:** `AgentRegistry` class in `core/agent_registry.py` — spawn, get, has, list_agents (with state/provider filtering), shutdown_agent, shutdown_all. Registry errors (`AgentRegistryError`, `AgentNotFoundError`, `AgentAlreadyExistsError`). `AgentInfo` and `ShutdownReport` models added to `core/models.py`. Module-level `get_registry()` singleton. All tests use mock providers.

**Next:** Phase 7 (Implementation) on slice 102.

---

### Slice 101: SDK Agent Provider — Complete

**Objective:** Implement the first concrete provider — `SDKAgentProvider` and `SDKAgent` wrapping `claude-agent-sdk` for one-shot and multi-turn agent execution.

**Commits:**
| Hash | Description |
|------|-------------|
| `b44914a` | feat: implement SDK message translation module with tests |
| `f7d15e0` | feat: implement SDKAgentProvider with options mapping and tests |
| `3055fcf` | feat: implement SDKAgent with query and client modes |
| `83611a5` | feat: auto-register SDK provider and add integration tests |
| `8743255` | chore: fix linting, formatting, and type errors |

**What works:**
- 96 tests passing (51 new + 45 foundation), ruff clean, pyright strict zero errors
- `translation.py`: Converts SDK message types (AssistantMessage, ToolUseBlock, ToolResultBlock, ResultMessage) to orchestration Messages
- `SDKAgentProvider`: Maps `AgentConfig` to `ClaudeAgentOptions`, defaults `permission_mode` to `"acceptEdits"`, reads mode from `credentials` dict
- `SDKAgent` query mode: One-shot via `sdk_query()`, translates and yields response messages
- `SDKAgent` client mode: Multi-turn via `ClaudeSDKClient` (create once, reuse), `shutdown()` disconnects
- Error mapping: All 5 SDK exception types → orchestration `ProviderError` hierarchy
- Auto-registration: Importing `orchestration.providers.sdk` registers `"sdk"` in the provider registry
- `validate_credentials()` returns bool without throwing

**Key decisions:**
- `translate_sdk_message` returns `list[Message]` (not `Message | None`) — `AssistantMessage` with multiple blocks produces multiple Messages, empty list for unknown types
- Deferred import of `SDKAgent` in `provider.py` to avoid stub-state issues at module load
- ruff requires `query as sdk_query` alias in a separate import block from other `claude_agent_sdk` imports (isort rule)
- Used `__import__("claude_agent_sdk")` in `validate_credentials` to satisfy pyright's `reportUnusedImport`
- Real SDK dataclasses used for test fixtures (no MagicMock — `TextBlock`, `AssistantMessage`, etc. are simple dataclasses)

**Issues logged:** None.

**Next:** Slice 3 (Agent Registry & Lifecycle) or slice 4 (CLI Foundation).

---

### Slice 100: Foundation Migration — Complete

**Objective:** Migrate foundation from v1 (LLMProvider-based) to v2 (dual-provider Agent/AgentProvider architecture) per `100-arch.orchestration-v2.md`.

**Commits:**
| Hash | Description |
|------|-------------|
| `7200b4e` | feat: add claude-agent-sdk dependency |
| `b6e1264` | feat: add SDK and Anthropic provider subdirectories with stubs |
| `6a389a5` | feat: add shared provider error hierarchy |
| `9700bed` | refactor: rename Agent to AgentConfig, remove ProviderConfig |
| `5ebf6cb` | test: update model tests for AgentConfig migration |
| `2433494` | refactor: replace LLMProvider with Agent and AgentProvider Protocols |
| `0b4302e` | refactor: retype provider registry for AgentProvider instances |
| `90dd38b` | test: update provider tests for AgentProvider instances and error hierarchy |
| `cb1d56c` | refactor: update Settings for dual-provider architecture |
| `0d3da45` | test: update config tests for new Settings fields |
| `f944f02` | docs: update .env.example for dual-provider architecture |
| `fd45a0d` | docs: update stub docstrings with correct slice numbers |
| `f189dc2` | fix: type checking — zero pyright errors |
| `5aaf718` | docs: mark foundation migration tasks and slice complete |

**What works:**
- 45 tests passing, ruff check clean, ruff format clean, pyright strict zero errors
- `AgentConfig` model with SDK-specific fields (cwd, setting_sources, allowed_tools, permission_mode) and API fields (model, api_key, auth_token, base_url)
- `Agent` and `AgentProvider` Protocols (runtime_checkable, structural typing)
- Provider registry maps type names to `AgentProvider` instances
- Shared error hierarchy: `ProviderError` → `ProviderAuthError`, `ProviderAPIError`, `ProviderTimeoutError`
- Settings with `default_provider="sdk"`, `default_agent_type="sdk"`, auth token and base URL support
- Provider subdirectories: `providers/sdk/` and `providers/anthropic/` with stubs
- All stub docstrings updated to correct slice numbers per v2 plan

**Key decisions:**
- `handle_message` in Agent Protocol is a sync method signature (not `async def`) — implementations are async generators, callers use `async for` directly without `await`
- `ProviderTimeoutError` chosen over `ProviderConfigError` — config errors caught at Pydantic validation time; timeout is the real operational concern
- `sdk_default_cwd` kept off Settings (per-agent config via AgentConfig, not global)
- `claude-agent-sdk` imports as `claude_agent_sdk` (module name differs from package name)

**Issues logged:** None.

**Next:** Slice 2 (SDK Agent Provider) or slice 101 (Anthropic Provider) — both can proceed in parallel as they only depend on foundation.

---

## 20260218

### Slice 101: Anthropic Provider — Design Complete

**Documents created:**
- `user/slices/101-slice.anthropic-provider.md` — slice design

**Key design decisions:**
- **API key auth only**: The official Anthropic Python SDK supports `api_key` / `ANTHROPIC_API_KEY` exclusively. No native `auth_token` parameter exists. Claude Max / OAuth bearer token usage requires external gateways (e.g., LiteLLM) — out of scope for this slice but extensible via `ProviderConfig.extra["base_url"]` in future.
- **Async-only client**: `AsyncAnthropic` exclusively — no sync path needed given async framework.
- **SDK streaming helper**: Uses `client.messages.stream()` context manager (not raw `stream=True`) for typed text_stream iterator and automatic cleanup.
- **Minimal error hierarchy**: `ProviderError` → `ProviderAuthError`, `ProviderAPIError`. SDK exceptions mapped to provider-level errors at boundaries.
- **No custom retry**: SDK built-in retry (2 retries, exponential backoff) is sufficient.
- **Default max_tokens=4096**: Required by Anthropic API, configurable via `ProviderConfig.extra`.

**Scope summary:**
- `AnthropicProvider` class satisfying `LLMProvider` Protocol (send_message, stream_message, validate)
- Message conversion: `orchestration.Message` → Anthropic dict format (role mapping, system extraction, consecutive role merging)
- API key resolution: `ProviderConfig.api_key` → `Settings.anthropic_api_key` → explicit error
- Auto-registration in provider registry via `providers/__init__.py`
- Full mock-based test suite (no real API calls)

**Commits:**
- `3c418e0` docs: add slice 101 design (Anthropic Provider)

**Next:** Phase 5 (Task Breakdown) on slice 101, then Phase 7 (Implementation).

### Slice 100: Foundation — Design and Task Creation Complete

**Documents created:**
- `user/slices/100-slice.foundation.md` — slice design (project setup, package structure, core Pydantic models, config, logging, provider protocol, test infrastructure)
- `user/tasks/100-tasks.foundation.md` — 19 granular tasks, sequentially ordered

**Key design decisions:**
- **Test-with ordering**: Tasks are structured so each implementation unit (models, providers, config, logging) is immediately followed by its tests, catching contract issues early rather than batching tests at the end
- **All dependencies installed up front**: `pyproject.toml` includes all project dependencies (anthropic, typer, fastapi, google-adk, mcp, etc.) so later slices just import and use
- **Protocol over ABC**: `LLMProvider` defined as a `Protocol` for structural typing, better ADK compatibility later
- **Stdlib logging only**: No third-party logging library; JSON formatter on stdlib `logging` keeps dependencies minimal

**Scope summary:**
- Project init with `uv`, `src/orchestration/` package layout matching HLD 4-layer architecture
- Pydantic models: Agent, Message, ProviderConfig, TopologyConfig (with StrEnum types)
- Pydantic Settings for env-based config (`ORCH_` prefix), `.env.example`
- LLMProvider Protocol + dict-based provider registry
- Structured logging (JSON + text formats)
- Full test infrastructure and validation pass

**Commits:**
- `007b02f` planning: slice 100 foundation — design and task breakdown complete

**Next:** Phase 6 (Task Expansion) on `100-tasks.foundation.md`, or proceed directly to Phase 7 (implementation) if PM approves skipping expansion for this low-complexity slice.