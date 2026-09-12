---
docType: slice-design
slice: review-artifact-integrity
project: squadron
parent: 900-slices.maintenance-and-refactoring.md
dependencies: [916]
interfaces: []
dateCreated: 20260912
dateUpdated: 20260912
status: not_started
---

# Slice Design: Review Artifact Integrity

## The problem in one paragraph

A review artifact is what a pipeline gate reads and what a human returns to. Today it can lie in four ways: it can carry a verdict that is not a real verdict and nothing rejects it; it can carry findings that are not findings, because the parser scans the model's whole response for finding-shaped text and the model often echoes the required format back; it can carry a hallucinated line number and nothing records that the file is shorter than that; and when the model produces nothing usable, the failure leaves no artifact at all. When it *does* degrade, the artifact keeps the raw evidence — but a confident PASS keeps nothing, so the artifacts most likely to be wrong are the least auditable. Six changes, all in `review/parsers.py`, `review/models.py`, `review/persistence.py`, plus one new commit-event action.

The live driver is the second one. Two runs of the same review against the same document and sha produced 8 findings and 35; the 35 included `summary: "Finding title"` citing `src/module.py` — the template's own specimen — and a `concern` under a top-line `PASS`. The count tracked how much the model restated the format, not what it found.

## Scope corrections against the plan entry

Plan entry 15 lists seven parts, A–G. Two of its premises were stale at `main` `ca40196`:

| Plan part | Issue | Finding | Disposition |
|---|---|---|---|
| B | #28 | Already shipped in `6d296aa` (`_verdict_from_findings`, [parsers.py:122](src/squadron/review/parsers.py#L122)); issue closed 20260730. What shipped *derives* the verdict from finding severities — the opposite of what the entry prescribes on the #5 precedent. | Dropped. The divergence is a separate decision, not a task here. |
| C | #84 | The "uncommitted fix on the 266 branch" is fully merged: `finish_reason`, `reasoning_chars`, `_require_final_content`, `TestEmptyFinalTurn` all on main. Prior-artifact overwrite already prevented by `archive_existing_review` (#73). | Narrowed to what remains: neither the CLI nor the pipeline writes an artifact when the provider raises. |

Also: the entry's `_location_path` is the public `location_path`; `_parse_findings` is `_extract_findings`. Effort 5/5 → **4/5**.

## Parts, in execution order

| # | Part | Plan | Issues | Effort |
|---|---|---|---|---|
| 1 | Rename the debug-log field | E | #87 | 1 |
| 2 | Reject invalid verdicts at commit | A | #77 | 2 |
| 3 | Bound the finding scan to `## Findings` | F | #91, #25 | 2 |
| 4 | Persist a failure artifact when the provider fails | C | #84 | 2 |
| 5 | Bounds-check cited line numbers | D | #26 | 2 |
| 6 | Run digest on every artifact | G | #93 | 2 |

Why this order: 1 and 2 are self-contained and land first so the shared parser files are quiet. 3 is the live bug and changes what 4–6 reason about. 5 runs on the findings 3 leaves behind. 6 reports counts 3 computes, so it goes last.

## Non-goals

- **No verdict manipulation from findings, beyond what already ships.** Part 5 writes a fact; nothing in this slice reads it to reject, downgrade, or filter a finding. Whoever builds that gate owns the policy.
- **No semantic hallucination detection.** Parts 3 and 5 are mechanical. A finding citing a real line and describing something not there is a problem no deterministic check solves.
- **No `max_tokens` work.** If Part 4 shows the empty turn traces to `finish_reason="length"`, that is follow-up.
- **#27** (fabricated content, unreproducible, seen twice) stays out. Parts 4 and 6 are the instrumentation that would catch a recurrence; re-assess after.
- **#92** (model reasons in prose, never emits the block) is not folded in — see Part 4.

---

## Part 1 — Rename the debug-log field (#87)

`_write_debug_log(fallback_used=True, ...)` at [parsers.py:516](src/squadron/review/parsers.py#L516) is called from the genuinely-unknown branch while `ReviewResult.fallback_used` is deliberately left `False` for the same event. The log field means "some degraded parse happened"; the result field means "findings were un-derivable from a known verdict". Same name, two meanings.

**Decision.** Rename the log field to `degraded`. `ReviewResult.fallback_used` is a serialized public field with consumers; it is correct for what it names and does not change.

**Compat.** `review-debug.jsonl` is append-only with existing entries. Old lines keep `fallback_used`, new lines write `degraded`, no dual-write. It is a diagnostic log read by humans and ad-hoc `jq`, not a schema contract, and dual-writing would preserve exactly the ambiguity being removed.

**Done when:** `_write_debug_log` takes `degraded`; a test asserts the emitted line has `degraded` and not `fallback_used`; `ReviewResult.fallback_used` and its `to_dict` key are untouched.

---

## Part 2 — Reject invalid verdicts at commit (#77)

Nothing checks an artifact's `verdict:` frontmatter against `Verdict` ([models.py:10](src/squadron/review/models.py#L10)). Slice 266 committed two artifacts with `verdict: RESOLVED` and the pre-commit gate accepted them. A `verdict: BANANA` passes `cf validate frontmatter` today. Downstream it degrades to UNKNOWN, and `CheckpointTrigger.ON_CONCERNS` includes UNKNOWN, so an invalid verdict trips a checkpoint indistinguishably from a real one.

**Decision.** A squadron-side COMMIT event action, `squadron.review-verdict-gate`, in `src/squadron/events/builtin/review_verdict_gate.py`, following the shape of `FrontmatterGateAction`. It reads `Verdict` directly — no literal list, no context-forge change (issue #77's own recommendation, for the reason it gives: a list in `cf` would drift the first time a member is added).

- Applies to staged `.md` files whose own frontmatter says `docType: review`. Not keyed on path: the reviews directory is a convention, the docType is the document's declaration. Confirmed on a real artifact: `docType: review` and `verdict:` are both top-level frontmatter keys.
- Violations: `docType: review` with no `verdict:` key; `verdict:` value not a `Verdict` member. Message names the file, the value, and the allowed set derived from the enum at runtime. No coercion.
- Unreadable or unparseable frontmatter on a file it was asked to check: WARNING and do not pass — the same "a gate that cannot determine validity must not pass" posture the frontmatter gate holds. A file with no frontmatter is not a review and is skipped.
- Enabled by default like the frontmatter gate; disableable in `events.yaml`.

**Done when:** `BANANA` and `RESOLVED` are rejected with the value and allowed set in the message; each real member passes; a review with no `verdict:` is rejected; a non-review doc with a bad `verdict:` is ignored; a test pins that the allowed set comes from the enum; the gate passes against the existing review corpus before it is enabled.

---

## Part 3 — Bound the finding scan to `## Findings` (#91, #25)

`_extract_findings` runs `_FINDING_RE.finditer` over the entire response ([parsers.py:356](src/squadron/review/parsers.py#L356)). The regex deliberately accepts five shapes to tolerate formatting variance, so any finding-shaped text anywhere — a restated format, the template specimen `### [PASS|CONCERN|FAIL] Finding title` echoed back — parses as a real finding. All four templates place the specimen under a `## Findings` heading at the same relative position ([code.yaml:47](src/squadron/data/templates/code.yaml#L47), [slice.yaml:50](src/squadron/data/templates/slice.yaml#L50), [arch.yaml:103](src/squadron/data/templates/arch.yaml#L103), [tasks.yaml:50](src/squadron/data/templates/tasks.yaml#L50)), so the bounding contract is uniform.

**Decision.** Locate the `## Findings` heading, take the span to the next `##` heading or end of document, and run the existing regex over that span only. The permissive shape matching inside the span is not the bug and stays.

- Heading location is lenient: case-insensitive, leading whitespace, bold, trailing punctuation. Bounding *where* findings live must not become a strict-outer/lenient-inner parse — that is the #28 shape one level up.
- **No `## Findings` heading → zero findings, rendered as degraded.** This is the consequential choice. Falling back to a whole-document scan would reintroduce the bug on exactly the responses least likely to be well-formed. A model that omitted the section did not follow the format; that is a degraded parse and presents as one (WARNING, debug-log entry, the existing "findings not parsed" section instead of "No specific findings"). Precedent: the parser already refuses to fabricate findings from prose.
- **This trades recall for precision**, deliberately. A weaker model that writes `### [CONCERN]` blocks without the heading loses them. What makes that acceptable is Part 6: the digest records how many finding-shaped matches the whole document had versus how many were inside the section, so the discard is visible in the artifact rather than silent. Parts 3 and 6 are one change in two files.
- The whole-document count and the bounded count are computed here and carried on `ReviewResult` for Part 6.
- **#25 folded in** as the prompt-side complement: delimit substituted document content in the templates with XML tags so reviewed content cannot be mistaken for the model's own output. Parser bounding is the fix; this is defense in depth.

**Done when:** finding-shaped text outside `## Findings` yields nothing; the captured #91 response (real fixture, not synthesized) yields no phantoms; all five shapes still parse inside the section; the 8-and-35 responses re-parse to consistent counts; a response with no heading renders as degraded; heading variants are located; templates carry the #25 delimiters. Existing tests encoding the unbounded scan will break — each is examined individually, not bulk-updated, because a break here is evidence.

---

## Part 4 — Persist a failure artifact when the provider fails (#84)

The provider half is done: an empty final turn raises `ProviderError` carrying `finish_reason` and `reasoning_chars` ([agent.py:67](src/squadron/providers/openai/agent.py#L67)). The problem is what happens next, on both entry paths:

- **CLI** — `run_review`'s catch-all ([cli/commands/review.py:627](src/squadron/cli/commands/review.py#L627)) prints `Error: Review failed — {exc}` and exits 1. No artifact, no traceback, no record of `finish_reason`.
- **Pipeline** — `ReviewAction.execute`'s catch-all ([pipeline/actions/review.py:92](src/squadron/pipeline/actions/review.py#L92)) logs the exception and returns `success=False`. Better — the step fails and the traceback is in the log — but still no artifact.

The evidence the provider fix collects is discarded one layer up, on both paths. For a pipeline run, the artifact is the whole durable record.

**Decision.** A provider failure on either path writes a failure artifact. The artifact states that the provider failed (not that the review found nothing), carries the error text including `finish_reason` and `reasoning_chars`, and carries whatever tool telemetry exists — so "given tools, said nothing" is distinguishable from "ran without tools", which slice 266 D5 requires. Exit code / `success=False` are unchanged: this changes what is recorded, not whether the run fails.

**Why overwrite the live slot.** The plan entry's instinct ran the other way ("the prior FAIL artifact was overwritten"). But leaving the prior artifact in place means a pipeline gate reads a stale verdict from a previous run and waves the step through — the silent pass-through 901 exists to prevent. Fail-closed requires the slot to hold the failure. The prior content is preserved by `archive_existing_review` (#73), and a test pins that the failure path goes through it.

**Shape.** One failure-artifact writer shared by both paths, in `persistence.py`, taking the exception and the context the paths already have (template, model, slice info, telemetry). Not a fabricated `ReviewResult` with empty `raw_output` — that is the 487-byte artifact #84 complained about. `ProviderError` gets an explicit handler on each path; the catch-alls remain as process-boundary handlers.

**On #92.** Not the same failure. #92 is a full turn, correct telemetry, 3302 characters of prose review, no formatted block — it never reaches `_require_final_content`. It is a parse outcome, and Part 3's no-heading path is what renders it legibly. A test here confirms that, and records which half of #92 this slice addresses (the artifact is honest) and which it does not (the content is not recovered).

**Done when:** a `ProviderError` on the CLI path and on the pipeline path each produce an artifact naming the provider failure with `finish_reason` and `reasoning_chars`; the artifact is distinguishable from a clean UNKNOWN and from a no-tools run; the prior artifact lands in `archive/`; CLI exit code stays 1 and pipeline `success` stays `False`; the #92 shape renders as degraded via Part 3.

---

## Part 5 — Bounds-check cited line numbers (#26)

`_check_path_existence` and `_check_diff_membership` already exist, but `location_path()` ([parsers.py:236](src/squadron/review/parsers.py#L236)) stops at the first `:` or `#`, so `:42` / `:42-50` is discarded. A line past the end of the file is the deterministic signature of a hallucinated citation. `_check_path_existence` fired on every #91 phantom and was ignored because it is WARNING-only — this part is what makes that fact survive.

**Decision (from the plan entry, 20260910).** Add `location_verified: bool | None` to `ReviewFinding`. Tri-state, not `bool`: `None` = not checked, `True` = path exists and line in bounds, `False` = checked and failed. A plain `bool` collapses "checked and bad" with "never checked", and the second is the common case — existence runs only with `cwd`, diff membership only with `diff_files`, both skip `UNVERIFIED_LOCATION` and whole-file citations. A gate reading `False` as "hallucinated" would reject most legitimate findings on non-code templates.

- `location_path()` keeps its contract — the findings-addressed gate depends on it. Line extraction is a sibling function.
- `:42` and `:42-50` parse; a location with no line suffix is a whole-file citation and stays `None`, matching the existing checks.
- Line count is read relative to the same `cwd` the existence check uses, through `_path_exists_under`'s resolution so bare-filename citations resolve the same way.
- Diff membership does **not** feed `location_verified`. A code review citing a file outside the diff may be legitimate context; it stays a WARNING.
- **Written, not read.** Nothing consumes the field in this slice; it is not added to `StructuredFinding` or frontmatter, because that would imply a contract this slice is not making. Precedent: `ReviewResult.provenance`, added the same way in slice 300.

**Done when:** `None` everywhere when neither `cwd` nor `diff_files` is supplied; `parsers.py:999999` → `False`; a real in-bounds line → `True`; whole-file and `UNVERIFIED_LOCATION` → `None`; the range form parses; `location_path()` tests pass untouched; the #91 phantoms re-parse with `False`.

---

## Part 6 — Run digest on every artifact (#93)

`format_review_markdown` appends `### Raw Response` only when the review degraded ([persistence.py:310](src/squadron/review/persistence.py#L310)). A confident PASS is the least auditable artifact on disk. #91 and #92 were diagnosable only because those runs happened to degrade; the 8-vs-35 discrepancy is invisible in either artifact.

**Decision.** A small always-on digest in the artifact body, not full raw text (large, mostly unread) and not frontmatter (a consumed contract — `cf` scans it and Part 2 now gates it; diagnostic fields there invite coupling).

Contents: response length; tool-call count; whether `## Summary` was present; whether `## Findings` was located; finding-shaped matches in the whole document / inside the bounded section / surviving validation. The last group is the #91 signature made visible: 35 whole-document, 3 bounded, in the artifact, with no raw text needed.

The counts come from the parser via `ReviewResult` (Part 3 computes them). The formatter does not re-parse — a second parse would drift from the first. Degraded-path raw response and the `-vv` appendix are unchanged.

**Done when:** a PASS artifact carries the digest; the three counts differ visibly on the #91 fixture; present regardless of verbosity; existing raw-response behavior unchanged; counts originate in the parser.

---

## Risks

- **Part 2 is a commit-path gate.** A misfire blocks commits repo-wide. Mitigated by keying on `docType`, skipping frontmatter-less files, `--no-verify` remaining available, and running against the existing corpus before enabling.
- **Part 3 changes what every review parses.** Finding counts on real artifacts will change. That is the intent, but the recall loss on models that skip the heading is real, and Part 6 is what makes it observable rather than silent. Land 3 and 6 in the same branch.
- **Part 5's model field** is defaulted and write-only. Low.

## Verification walkthrough

Draft; refined at Phase 6 with commands actually run.

1. **Debug-log field.** Run a review that degrades; `tail -1 ~/.config/squadron/logs/review-debug.jsonl | jq keys` shows `degraded`, not `fallback_used`. `--output json` still shows `fallback_used` on the result.
2. **Verdict gate.** Stage a `docType: review` file with `verdict: BANANA`; commit is rejected naming `BANANA` and the four values. Change to `CONCERNS`; commit proceeds. Repeat with `RESOLVED`; rejected. Stage a slice design with `verdict: BANANA`; not rejected. Remove the probe.
3. **Bounded scan.** Re-parse the captured 35-finding response; the `"Finding title"` / `src/module.py` phantoms are gone and the count agrees with the 8-finding run. Run a live review twice against the same sha (`env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT uv run sq review code --diff main -vv --no-save`); counts are stable. A response with no `## Findings` heading renders the "findings not parsed" section.
4. **Failure artifact.** Stub an empty final turn on the CLI path and on a pipeline review step. Each writes an artifact naming the provider failure with `finish_reason`/`reasoning_chars`; the prior artifact is in `reviews/archive/`; CLI exits 1, pipeline step fails.
5. **Line bounds.** Parse a response citing `src/squadron/review/parsers.py:999999` with `cwd`; `location_verified=False`. A real line → `True`. No `cwd` → `None`. Artifact output is unchanged.
6. **Digest.** Open a clean PASS artifact; the digest block is present. Re-run on the #91 fixture; whole-document and bounded counts differ.
