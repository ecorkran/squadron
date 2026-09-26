---
docType: slice-design
slice: review-artifacts-state-what-happened-diff-truncation-and-the-model-that-answered
project: squadron
parent: user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: []
interfaces: []
dateCreated: 20260926
dateUpdated: 20260926
status: complete
---

# Slice Design: Review Artifacts State What Happened — Diff Truncation and the Model That Answered

## Overview

A saved review must record facts about the run, not the request. Two facts are missing today.

**The diff the model saw.** `_inject_file_contents` in [review_client.py](../../../src/squadron/review/review_client.py) passes the diff through `_truncate`, which cuts it at `review.max_file_size_bytes` and reports the cut only to `_logger.warning`. Amoeba's slice 103 review came back PASS after the tail of a ~275KB diff was dropped and the model made zero tool calls, so it approved code it never saw ([#135](https://github.com/ecorkran/squadron/issues/135)). There is a second, worse path nobody filed: once `review.max_total_injection_bytes` is reached, `_add_injection` skips the diff *entirely*, again with only a log line.

**The model that answered.** `aiModel:` in the frontmatter is `resolved_model`, the id squadron asked for. Nothing reads back what answered ([#134](https://github.com/ecorkran/squadron/issues/134)). It is accurate today only because the SDK path fails loudly on an unknown id.

This slice records both facts in the artifact, the findings header, and `--output json`, on both the CLI and pipeline paths. It also stops a truncated, unread diff from coming back as a clean PASS.

## Value

- **Gates can trust a PASS on a code review.** context-forge gates and Amoeba read the artifact, not squadron's logs. After this slice a PASS on a truncated diff means the model made at least one successful tool call, and the artifact says so (`diffTruncated: true` plus a Run Digest line). A truncated diff with no tool use comes back CONCERNS with a finding that says why.
- **The artifact names the model that did the work.** A silent fallback (a configured fallback model, an OpenRouter route remapping an id) shows up as `requestedModel:` next to `aiModel:` with a WARNING, instead of an artifact naming a model that never ran.
- **Metrology calibrates the right judge.** `metrology/identity.py` keys judge identity on `aiModel`. Recording the answering model means a substituted judge's scores are no longer pooled under the model that was requested.

## Technical Scope

**Included**

- **Part A — record diff truncation.** Measure the diff produced against the diff injected. Carry it on `ReviewResult`, render `diffTruncated` in frontmatter, a `**Diff:**` line in the findings header when truncated, and three keys in `to_dict()`.
- **Part B — cap a truncated, unread PASS.** A truncated diff with no successful tool call turns a stated PASS into CONCERNS, adds a synthetic CONCERN finding, and marks `verdictSource: imposed`.
- **Part C — record the answering model.** The SDK and OpenAI-compatible providers stamp the model ids they observed. `ReviewResult.model` and `aiModel` carry the answering model. A substitution adds `requestedModel` and logs WARNING. A provider that reports nothing (Codex) keeps the requested id, and the Run Digest says so.
- Terminal display (`sq review` header) and pipeline `ActionResult.metadata["model"]` follow the answering model.

**Excluded**

- Changing `max_file_size_bytes` / `max_total_injection_bytes` defaults (slice plan).
- [#114](https://github.com/ecorkran/squadron/issues/114) (findings recording what they were checked against) (slice plan).
- Diff ordering and `--stat` injection → [#137](https://github.com/ecorkran/squadron/issues/137) (D7).
- Truncation of injected file bodies, glob files, and `CLAUDE.md` → [#138](https://github.com/ecorkran/squadron/issues/138). Same silent class, but not the one that approved unseen code.
- `judge-findings-addressed`'s `round_diff`. It is rendered into the prompt by its builder, not injected through the `diff` key, and never passes through `_truncate`.
- Provider-failure artifacts (`format_provider_failure_markdown`). Nothing answered, so there is no answering model to record. They keep writing the requested id (D13).

## Dependencies

### Prerequisites

- None. Builds on shipped work: slice 265/266 tool telemetry (`toolsGiven`/`toolCallsMade`), slice 918's metadata-stamping pattern and Run Digest, slice 919's `VerdictSource`, and slice 920's `claude-agent-sdk` 0.2.152 pin (`AssistantMessage.model` and `parent_tool_use_id` exist there; verified 20260926).

### Interfaces Required

- `claude_agent_sdk.AssistantMessage.model: str` and `.parent_tool_use_id: str | None`.
- `openai.types.chat.ChatCompletionChunk.model: str`. A required field on every streamed chunk.
- `TurnCapture` / `collect_turn` ([turn_capture.py](../../../src/squadron/review/turn_capture.py)). Its metadata-folding loop is where the new stamp is read.

## Architecture

### Component Structure

| Component | Change |
|---|---|
| `review/models.py` | New frozen `DiffInjection` dataclass. New `ReviewResult` fields `diff_injection`, `requested_model`, `answering_models`. New `model_substituted` property. `VerdictSource.IMPOSED`, with the class docstring rewritten: it no longer answers only "did the model say this?" but "where did this verdict come from?" (stated, derived, imposed), still a closed vocabulary. `to_dict()` keys. |
| `review/review_client.py` | `_inject_file_contents` returns the prompt plus the `DiffInjection`. `run_review_with_profile` stamps the diff and model facts on the result and calls the coverage cap. `_truncate` keeps its signature, because `builders/code.py` imports it for PR metadata. |
| `review/coverage.py` (new) | `impose_diff_coverage(result)`: the Part B rule, pure and unit-testable. |
| `models/snapshot.py` (new) | `answers_as_requested(requested, answered) -> bool`: the D9 equivalence rule. It lives next to `models/aliases.py` because it is about model ids, not reviews. |
| `review/turn_capture.py` | `TurnCapture.answering_models`, folded from the `answering_models` metadata key. |
| `providers/sdk/agent.py` | Collect distinct `AssistantMessage.model` values per `handle_message`, top-level only, skipping `<synthetic>`. Stamp them on the `ResultMessage` translation next to `stop_reason`. |
| `providers/openai/agent.py` | `TurnResult.model` from the last non-empty `chunk.model`. Accumulate distinct values across the agentic loop. Stamp in `_stamp_tool_telemetry` before its tools early-return. |
| `review/persistence.py` | Frontmatter `diffTruncated`, `requestedModel`. Header `**Diff:**` line and `**Model:** X (requested Y)`. Run Digest answering-model and diff-coverage lines. |
| `cli/commands/review.py` | Terminal header shows the substitution. |
| `pipeline/actions/review.py` | `metadata["model"]` = `result.model`. Adds `metadata["requested_model"]`. |

### Data Flow

```
git diff ──► _inject_file_contents ──► (prompt, DiffInjection)
                                              │
provider stream ──► agent stamps metadata["answering_models"] on final Message
                                              │
              collect_turn ──► TurnCapture.answering_models
                                              │
run_review_with_profile:
  result = parse(...)                        # model = requested, as today
  result.diff_injection    = DiffInjection
  result.requested_model   = resolved_model
  result.answering_models  = capture.answering_models
  result.model             = last answering model, else requested (D11)
  WARNING if model_substituted, or if >1 distinct answering model (D12)
  impose_diff_coverage(result)               # Part B, after tool telemetry is set
                                              │
      ┌───────────────────────┬───────────────┴──────────────┐
format_review_markdown   ReviewResult.to_dict()     _display_terminal / ActionResult
(CLI + pipeline, same fn) (--output json / file)
```

Both `sq review` and the pipeline `review` action call `run_review_with_profile` and then `save_review_result` → `format_review_markdown`. Every fact rides `ReviewResult`, so parity is structural. No second code path to keep in sync.

### State Management

No persisted state beyond the artifact. `TurnCapture` accumulates across the #92 recovery turn: answering models append in order, deduplicated. The SDK and OpenAI agents reset their per-message model list at the top of `handle_message`, like `_tool_calls_made`.

## Technical Decisions

### D1 — Measure characters; frontmatter carries only `diffTruncated`

`DiffInjection(total_chars: int, injected_chars: int)` with a `truncated` property (`injected_chars < total_chars`). Characters, because that is what `_truncate` compares: `len(content)` on a `str`, despite the config keys being named `*_bytes` (noted on #138). Naming the fields `diffBytes` would record a unit the code never measured.

A gate needs one fact to decide: did the model see all of it. So frontmatter gets the boolean. The two counts go to the findings header (for humans) and JSON (for programs). A threshold gate ("truncated by under 5%") is speculative. If one is ever built, the counts are already in JSON.

`injected_chars` counts diff content only, never the `[truncated at …]` marker `_truncate` appends. So `injected_chars == min(total_chars, max_file_size)` when the diff was added, and `0` when it was skipped (D3).

### D2 — `diffTruncated` is present exactly when the review had a diff

`diff_injection` is `None` when `inputs` has no `diff` key (slice, arch, and tasks reviews), and the key is absent. When a diff was part of the review, the key is always written, `true` or `false`. An empty diff (wrong ref, nothing changed, so `_inject_file_contents` injects nothing) records `DiffInjection(0, 0)` and writes `diffTruncated: false`: the model saw all zero characters. That gives a gate three distinguishable states: absent (no diff, or pre-927 artifact), `false` (saw it all), and `true`. It is the same tri-state the codebase already uses for `location_verified`. Writing it only when `true` would make a clean code review indistinguishable from an artifact written before this slice.

Cost: every code-review artifact gains one line. The `clean_pass_artifact.md` snapshot uses a hand-built result with no diff, so it stays byte-identical.

### D3 — A diff dropped by the total-injection limit is a truncation to zero

When `_add_injection` returns `False` for the diff, record `DiffInjection(total_chars=len(diff), injected_chars=0)`. The model saw none of it, which is the worst case of the same fact, not a different fact. `_add_injection` already reports whether it added the content, so this needs no new branch in the budget logic.

### D4 — Truncated and unread: cap PASS to CONCERNS, don't fail the run

Rule, in `impose_diff_coverage`:

- **Applies when:** `diff_injection.truncated` **and** no successful tool call, where successful = `(tool_calls_made or 0) - (failed_tool_calls or 0)`, **and** `verdict is PASS`.
- **Effect:** `verdict = CONCERNS`, `verdict_source = IMPOSED`, and one synthetic finding is prepended (below).
- **Otherwise:** nothing. A CONCERNS, FAIL, or UNKNOWN verdict is already not a clean pass, and `diffTruncated: true` records the rest. A run where the model made a successful tool call keeps its verdict, as the slice plan requires.

**The exemption is wider than "read the missing files", on purpose.** Any successful call counts, including a `Glob` or a `Read` of `CLAUDE.md`. No tool can rebuild the diff itself (`review_client.py`, issue #81), and telemetry records counts, not per-call tool names, so narrowing the rule to reads of `diff_files` would need new telemetry this slice doesn't add. Instead the exemption is made visible: when a truncated diff keeps a PASS because of tool calls, the Run Digest adds `- Diff coverage: truncated; PASS kept because the model made N successful tool call(s)`. A gate that wants stricter behavior already has `diffTruncated: true` to key on.

`tool_calls_made is None` (no tools offered) counts as zero. A tool-less model with a truncated diff could not have read the rest, which is the same problem with fewer options. Failed calls don't count, because a model whose every read failed read nothing.

**Why not fail the run:** the model's review of the part it saw is real work. Failing throws it away and turns a coverage gap into a hard pipeline step failure. CONCERNS is already what `CheckpointTrigger.ON_CONCERNS` pauses on, so a pipeline stops for a human either way, and the gate sees a non-PASS in the one place it looks. This does not break the #5 precedent (no verdict changes derived from finding severities). The input here is a fact squadron measured about the run, not a severity. It also only ever moves PASS down.

Synthetic finding:

```markdown
### [CONCERN] Diff truncated; the omitted part was never read
category: review-coverage

The diff was 275431 characters; the first 256000 reached the model
(review.max_file_size_bytes). The model made no successful tool calls,
so the remaining 19431 characters were not reviewed. The model's own
verdict was PASS. Raise review.max_file_size_bytes, narrow the diff,
or use a tool-enabled model.
```

It has no `location` because it cites no file. `location_verified` stays `None`.

### D5 — `VerdictSource.IMPOSED`

`verdictSource: stated` would claim the model said CONCERNS. `derived` means derived from findings. Neither is true. A third member, `IMPOSED = "imposed"`, means squadron set the verdict from a measured fact about the run. The vocabulary stays closed (the docstring's concern was open reason strings, not member count). Nothing outside squadron reads `verdictSource`: grep of context-forge on 20260926 found no reader. The parser never produces it. Only `impose_diff_coverage` sets it.

### D6 — The cap cannot hide a degraded parse; no render change

`format_review_markdown` picks exactly one of: the findings list, the `fallback_used` not-parsed notice, or the UNKNOWN notice. The first branch wins whenever `findings` is non-empty. That would hide the notice if a PASS with unparsed findings got the synthetic finding, but no such PASS exists. The parser sets `fallback_used` in two branches (`parsers.py`): the mismatch branch (CONCERNS/FAIL with no findings, never PASS) and the derived-verdict branch (verdict computed *from* parsed findings, so findings are non-empty). A stated PASS with no findings is a clean review, not a degraded one. So the cap, which only moves PASS, only ever meets a clean PASS or a derived PASS whose findings did parse.

Rendering the notice whenever `fallback_used` is set would be wrong. It would stamp "Findings Not Parsed" on every derived-verdict review, whose findings parsed fine. The render conditions stay as they are, and a test pins the invariant (derived PASS + cap → synthetic finding, parsed findings, no not-parsed notice).

### D7 — Diff ordering and `--stat` deferred to #137

Ordering "source before docs and tests" needs a policy for what counts as source, likely per template. That is a decision, not plumbing. `--stat` is small, but it only helps a tool-enabled model, and D4's rule doesn't depend on it. Neither is needed for the correctness gap. Filed as [#137](https://github.com/ecorkran/squadron/issues/137).

### D8 — Where each provider reads the answering model

- **SDK:** `AssistantMessage.model`, only when `parent_tool_use_id is None`. Messages from a subagent spawned through the Task tool can legitimately run another model and did not write the review. The Claude Code CLI emits placeholder assistant messages with model `<synthetic>`. That string is skipped as not-a-model, and it is defined once as a module constant. Not `ResultMessage.model_usage`: it aggregates every model the CLI used for the session, including background work, so it answers a different question.
- **OpenAI-compatible:** `chunk.model` on each streamed chunk. The last non-empty value per turn goes on `TurnResult.model`. It is read from every chunk, including choice-less ones, because the usage chunk carries it too.
- **Codex (`openai-oauth`):** the agent returns `final_response` text only and reports no model. Unchanged. It surfaces as "not reported" (D11).

Stamped as `metadata["answering_models"]: list[str]` (distinct, first-seen order) on the same final Message that already carries `stop_reason`. The existing OpenAI text-message `metadata["model"]` holds the *requested* id and is left alone. A new key avoids repurposing an existing one.

### D9 — What counts as "the model that was requested"

`answers_as_requested(requested, answered)` is true iff:

- `answered == requested`, or
- `answered == requested + "-" + snapshot`, where `snapshot` is `\d{8}` or `\d{4}-\d{2}-\d{2}` (Anthropic `claude-…-20251001`, OpenAI `gpt-…-2025-08-07`, and OpenRouter's dated forms under the same `vendor/` prefix).

Everything else is a substitution. That includes `gpt-5` → `gpt-5-mini`, which a plain prefix rule would wrongly accept. When unsure, the rule reports a substitution. A false report costs one extra frontmatter key and a WARNING. A missed substitution is the bug this slice exists to fix.

The rule is deliberately exact rather than guessed wider. Phase 6 captures the real `answering_models` from one review per configured profile (sdk, openai, openrouter, local). Any profile whose default alias produces a false substitution gets its observed form added to the rule, with a test built from the captured id. No speculative forms go in beforehand.

When `requested` is `None` (the SDK run on its default model), nothing was requested, so nothing can be substituted.

### D10 — `aiModel` is the answering model; `requestedModel` appears only on substitution

- `aiModel:` = the answering model id, verbatim, including a dated snapshot.
- `requestedModel:` present **iff** `model_substituted`. So its presence alone tells a gate "not the model you asked for", with no need to reimplement D9. A snapshot resolution writes the dated id to `aiModel` and no `requestedModel`. The requested id is its prefix.
- Header: `**Model:** gpt-4.1 (requested gpt-5)` on substitution. JSON always carries `requested_model`, `answering_models`, and `model_substituted`, `null`/`false` when they don't apply, following JSON's always-present convention.
- WARNING on substitution: `"%s review requested model %s but %s answered"`.

Consequence: OpenAI-direct judges whose API returns dated snapshots will change metrology identity once, from `gpt-5` to `gpt-5-2025-08-07`. That is the correct calibration identity (a new snapshot *is* a different judge), and it takes effect from this slice forward. SDK runs are unchanged: the CLI answers with the id it was given (verified in #134).

### D11 — Not reported: keep the requested id, say so in the artifact

When `answering_models` is empty (Codex, or any provider that stamps nothing), `result.model` keeps the requested id, and the Run Digest adds `- Answering model: not reported by provider (aiModel is the requested id)`. This is not a silent fallback: the artifact states it. It is not `aiModel: unknown` either, which would collapse every Codex judge into a single metrology identity. It is not a WARNING, because Codex never reports and a warning on every Codex review is noise. The signal lives in the artifact, where a reader looks.

`answering_models` is `None` on hand-built results, meaning not produced by `review_client`, the convention `finding_scan` uses. The digest line keys on `== []`, not on falsiness, so hand-built results and the snapshot fixture render unchanged.

### D12 — More than one model answered in one run

Possible across agentic-loop turns or the #92 recovery turn. `aiModel` is the **last** model reported, the one that wrote the review. The substitution check runs against it. The Run Digest lists all of them (`- Answering models: a, b`), and a WARNING names them. The frontmatter describes the review. The digest describes the run.

### D13 — Provider-failure artifacts are unchanged

`save_provider_failure` has no `ReviewResult` and no answer. Its `aiModel` is the requested id, and its verdict and body already say the provider failed. Adding `requestedModel` there would break D10's rule that its presence means substitution.

### Patterns and Conventions

- Optional frontmatter keys are emitted only when they apply, so a clean non-diff review stays byte-for-byte unchanged (slice 265/266/919 convention).
- JSON keys are always present, `null` when they don't apply (slice 918 convention).
- `None` means "not reported" and is never replaced by a plausible value. `is None` checks, never `or 0`, for counts.
- Metadata keys are string literals, matching the existing `stop_reason`/`tools_given` stamps. `<synthetic>` and the snapshot regex are module constants.

## Implementation Details

### Artifact Contract

Frontmatter, truncated and capped (tools offered, none used):

```yaml
verdict: CONCERNS
verdictSource: imposed
sourceDocument: …
aiModel: claude-sonnet-5
…
toolsGiven: [Read, Grep, Glob]
toolCallsMade: 0
diffTruncated: true
findings:
  - id: F001
    severity: concern
    category: review-coverage
    summary: "Diff truncated; the omitted part was never read"
```

`diffTruncated` goes after the tool telemetry pair. `requestedModel` goes directly after `aiModel`:

```yaml
aiModel: openai/gpt-4.1
requestedModel: openai/gpt-5
```

Findings header (lines added only when they apply):

```markdown
**Verdict:** CONCERNS
**Model:** openai/gpt-4.1 (requested openai/gpt-5)
**Diff:** truncated: 256000 of 275431 characters reached the model
```

`to_dict()` additions, always present:

```json
"diff_chars": 275431,
"diff_chars_injected": 256000,
"diff_truncated": true,
"requested_model": "openai/gpt-5",
"answering_models": ["openai/gpt-4.1"],
"model_substituted": true
```

`verdictSource` in JSON already mirrors frontmatter and picks up `"imposed"` for free.

## Integration Points

### Provides to Other Slices

- **context-forge / Amoeba gates:** `diffTruncated` (tri-state by presence), `verdictSource: imposed`, `requestedModel` (presence = substitution). All additive. No existing key changes meaning except `aiModel`, which now names the answering model. That is the meaning its consumers assumed all along.
- **Metrology:** `aiModel` becomes the answering model (D10 consequence).
- **Future #138:** `DiffInjection` is the shape to generalize to every injection.

### Consumes from Other Slices

- Slice 918 metadata-stamping path and Run Digest. If a provider stamps nothing, the result degrades to "not reported" (D11), never a fabricated id.
- Slice 917's COMMIT verdict validator checks `verdict:` against `Verdict`. `CONCERNS` is valid. `verdictSource` is not validated there, so `imposed` needs no gate change.

## Success Criteria

### Functional Requirements

1. A code review whose diff exceeds `review.max_file_size_bytes` writes `diffTruncated: true`, the `**Diff:**` header line, and `diff_chars`/`diff_chars_injected`/`diff_truncated` in JSON, with the correct counts. Same on the pipeline `review` action.
2. A diff skipped by `review.max_total_injection_bytes` records `diff_chars_injected: 0` and `diffTruncated: true`.
3. A code review with an untruncated diff writes `diffTruncated: false` and no `**Diff:**` line. So does a code review whose diff came back empty (D2). A slice/arch/tasks review writes no `diffTruncated` key.
4. Truncated diff + PASS + zero successful tool calls → `verdict: CONCERNS`, `verdictSource: imposed`, the synthetic `review-coverage` finding first, and exit code / checkpoint behavior of CONCERNS. Holds for `tool_calls_made` None, 0, and `== failed_tool_calls`.
5. Truncated diff + at least one successful tool call → verdict unchanged, no synthetic finding, `diffTruncated: true`. On a kept PASS, the Run Digest carries the `Diff coverage:` exemption line (D4).
6. Truncated diff + CONCERNS/FAIL/UNKNOWN → verdict and findings unchanged.
7. A derived PASS (`fallback_used=True`, findings parsed) that gets capped renders the synthetic finding and its parsed findings, with no "Findings Not Parsed" notice (D6).
8. The SDK provider stamps `answering_models` from top-level `AssistantMessage.model`, excluding `<synthetic>` and subagent messages. The OpenAI provider stamps it from `chunk.model` across all loop turns.
9. A stubbed provider whose reported model differs from the request (not a snapshot) produces `aiModel: <answered>`, `requestedModel: <requested>`, the header suffix, `model_substituted: true` in JSON, and a WARNING. This is #134's stated test.
10. A dated-snapshot answer (`gpt-5` → `gpt-5-2025-08-07`) produces `aiModel: gpt-5-2025-08-07` with no `requestedModel` and no WARNING. `gpt-5` → `gpt-5-mini` is a substitution.
11. A provider that stamps nothing keeps `aiModel` = requested and adds the "not reported" digest line. Two distinct answering models list both in the digest and log a WARNING.
12. Pipeline `ActionResult.metadata["model"]` is the answering model. `metadata["requested_model"]` is the request.

### Technical Requirements

- `clean_pass_artifact.md` snapshot stays byte-identical (no fixture regeneration).
- Unit tests: `impose_diff_coverage` (parametrized over verdict × tool-call states), `answers_as_requested` (parametrized, including the captured real ids from D9), `DiffInjection` accounting in `_inject_file_contents` (under limit, over file limit, over total limit), `collect_turn` folding across the recovery turn, SDK and OpenAI stamping with stubbed streams, frontmatter/header/JSON rendering for each case.
- `ruff format`, `ruff check`, and `pyright` clean. Full suite green.
- CHANGELOG: short user-facing bullets. DEVLOG: technical detail.

### Integration Requirements

- The same `ReviewResult` produces agreeing frontmatter, header, and JSON (single source, like slice 919's SC6).
- `sq review code` and `sq run review` produce the same new keys for the same inputs.

### Verification Walkthrough

Run in this repo on the slice branch. The diff for slice 927 itself is the test subject.
All commands below were run for real on 20260926 against commit e560c6e3 (before the
ff39680b DRY fix, which does not touch rendering). Use `uv run sq ...` rather than a
globally-installed `sq`, so the local dev tree's code is what actually runs.

1. **Force truncation, no tools (Part A + B, CLI).**
   ```bash
   uv run sq config set review.max_file_size_bytes 20000 --project
   uv run sq review code 927 --model sonnet --no-tools -v
   ```
   **Actual:** terminal verdict `CONCERNS`. In the saved artifact: `diffTruncated: true`,
   header line `**Diff:** truncated: 20000 of 83324 characters reached the model`. The
   verdict came back `verdictSource: stated`, not `imposed` — the model itself found real
   findings and stated CONCERNS on the visible 20000 characters, so the D4 cap (which only
   ever moves a stated *PASS*) correctly never fired. This is expected, not a defect: it
   confirms the cap is scoped to PASS as designed rather than blindly appending a finding to
   every truncated CONCERNS run.

2. **Same, JSON.**
   ```bash
   uv run sq review code 927 --model sonnet --no-tools --output json --no-save
   ```
   **Actual:** `diff_chars: 84077`, `diff_chars_injected: 20000`, `diff_truncated: true`,
   `verdict: "CONCERNS"`. Caveat: the CLI prints a `Truncated Git Diff (N bytes)` WARNING
   line to stdout before the JSON payload; pipe stdout and stderr separately (don't merge
   with `2>&1` before `jq`) or the warning line breaks JSON parsing. This run also exercised
   the #92 recovery turn (`recovery_turn_used: true`) — the first turn ended without a
   parseable review and a follow-up turn produced one — unrelated to this slice, pre-existing
   behavior.

3. **Truncated, tools on (Part B does not fire when the model reads).**
   ```bash
   uv run sq review code 927 --model sonnet -v
   ```
   **Actual:** the model made 28 successful tool calls. Verdict stayed the model's own
   (`CONCERNS`, `verdictSource: stated`, real findings — no `review-coverage` synthetic
   finding), and `diffTruncated: true` was still present. No `Diff coverage:` exemption
   line, because that line only renders on a *kept PASS* (D4) and this run's stated verdict
   was CONCERNS, not PASS.

4. **Pipeline parity (Part A).**
   ```bash
   uv run sq run review 927
   ```
   **Could not run live**: `sq run review` refuses SDK pipeline execution inside a Claude
   Code session (`Error: SDK pipeline execution cannot run inside a Claude Code session.
   Use --prompt-only mode or run from a standard terminal.`). `--prompt-only` only prints
   the planned actions without executing them, so it does not exercise the render path.
   Verified structurally instead: `pipeline/actions/review.py` calls the same
   `run_review_with_profile` → `save_review_result` → `format_review_markdown` chain the CLI
   uses (confirmed by reading the file), so `diffTruncated`/the `**Diff:**` line/the D4 cap
   apply identically with no second render path to drift, matching the design's data-flow
   diagram. The metadata half of this parity (`ActionResult.metadata["model"]` /
   `requested_model`) is covered directly by `tests/pipeline/actions/test_review_action.py`.
   An agent running this walkthrough from a standard terminal (not inside a Claude Code
   session) should complete this step live.

5. **Untruncated.**
   ```bash
   uv run sq config unset review.max_file_size_bytes --project
   uv run sq review code 927 --model sonnet -v
   ```
   **Actual:** `diffTruncated: false`, no `**Diff:**` line, and the model returned a clean
   `PASS` after reading the entire diff — end-to-end confirmation that the untruncated path
   renders correctly and that the earlier truncated runs' findings were genuinely a function
   of the missing tail, not an unrelated issue with the diff itself. `git status` confirmed
   no leftover project config change after the `unset`.

6. **Answering model (Part C), one per configured profile.** For each profile with credentials
   (sdk, openai, openrouter, local), run a small review on that profile's default model (no
   `--model`), since those defaults are the ids D9 has to handle:
   ```bash
   uv run sq review slice 927 --profile <profile> -v --output json --no-save
   ```
   **Actual, captured 20260926:**
   - `sdk` with `--model sonnet` (see caveat below): `requested_model: "claude-sonnet-5"`,
     `answering_models: ["claude-sonnet-5"]`, `model_substituted: false`.
   - `openrouter` on its default alias: `requested_model: "minimax/minimax-m3"`,
     `answering_models: ["minimax/minimax-m3"]`, `model_substituted: false`.
   - `openai`: skipped — a key is configured but returned `insufficient_quota` /
     `credit_balance_exhausted` even against a real model id (`gpt-5`).
   - `local`: skipped — the configured default model id 404'd (`model 'minimax/minimax-m3'
     not found`); no local server in this environment serves that id.

   No D9 false positive on either profile that actually ran, so `answers_as_requested`
   needed no widening from this walkthrough.

   **Caveat found:** running `--profile sdk` with *no* explicit `--model` in this environment
   resolved through the user's `default_model = "minimax"` config setting, and the review
   actually executed via the `minimax` alias's own declared profile (`openrouter`) rather than
   the true SDK/Claude Code path — visible from `stop_reason: "stop_sequence"`, an
   OpenAI-compatible value the SDK path never produces. Passing `--model sonnet` alongside
   `--profile sdk` forced the genuine SDK path (`Review via sdk (provider=sdk,
   model=claude-sonnet-5)` on stderr). This looks like a profile/alias resolution precedence
   quirk specific to a `default_model` pointing at a non-SDK alias; it is not something this
   slice's scope covers, and D9's rule was validated correctly once the real SDK path ran.

## Risk Assessment

### Technical Risks

- **D9 false positives on a live router.** OpenRouter or a local server may return an id form the rule doesn't know, such as a dropped `vendor/` prefix or a `:free` suffix, and every run on that profile would report a substitution.

### Mitigation Strategies

- Walkthrough step 6 captures each profile's real ids before merge. Any false positive is fixed with an explicit, tested form, not a looser rule.

## Implementation Notes

### Development Approach

1. **Models first.** `DiffInjection`, the new `ReviewResult` fields, `model_substituted`, `VerdictSource.IMPOSED`, and `to_dict()`. `models/snapshot.py` with its parametrized tests.
2. **Part A.** `_inject_file_contents` returns `(prompt, DiffInjection | None)`. Update its two `review_client` call sites and the direct callers in `test_content_injection.py`, `test_convention_root.py`, `test_injection_decision.py`, and `test_review_client.py`. Then persistence rendering and JSON.
3. **Part B.** `review/coverage.py`, the D6 invariant test, and the call in `run_review_with_profile` after telemetry assignment.
4. **Part C.** OpenAI `TurnResult.model` and stamping, SDK collection and stamping, `TurnCapture` folding, and the `run_review_with_profile` assignment and warnings. Then persistence, terminal, and pipeline metadata.
5. Walkthrough, capture D9 ids, DEVLOG, CHANGELOG.

Parts A and C are independent after step 1. B depends on A. Commit each part separately, so A+B and C can each be reverted on its own.

### Special Considerations

- `review_client.py` is already 588 lines. The cap goes in its own module, and the model assignment stays a few lines. Extracting injection into its own module is tempting but not this slice's job.
- `impose_diff_coverage` must run **after** `tool_calls_made`/`failed_tool_calls` are assigned, and after the #92 recovery turn. Otherwise it reads the first turn's counts only.
