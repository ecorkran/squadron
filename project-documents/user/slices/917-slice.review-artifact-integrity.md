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
| B | #28 | Already shipped in `6d296aa` (`_verdict_from_findings`, [parsers.py:122](src/squadron/review/parsers.py#L122)); issue closed 20260730. It derives a missing verdict from finding severities; the plan entry had said to flag the mismatch instead. Derivation accepted (PM, 20260912). | Dropped. |
| C | #84 | The "uncommitted fix on the 266 branch" is fully merged: `finish_reason`, `reasoning_chars`, `_require_final_content`, `TestEmptyFinalTurn` all on main. Prior-artifact overwrite already prevented by `archive_existing_review` (#73). | Narrowed to what remains: neither the CLI nor the pipeline writes an artifact when the provider raises. |

Also: the entry's `_location_path` is the public `location_path`; `_parse_findings` is `_extract_findings`. Effort 5/5 → **4/5**.

## Parts, in execution order

| # | Part | Plan | Issues | Effort |
|---|---|---|---|---|
| 1 | Rename the debug-log field | E | #87 | 1 |
| 2 | Reject invalid verdicts at commit | A | #77 | 2 |
| 3 | Stop parsing finding-shaped text that is not a finding | F | #91, #25 | 2 |
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
- **Deliverables that ship with the gate (slice 173's obligations for a built-in binding):** a row in the built-in bindings table in `docs/EVENTS.md`; a `builtin/review_verdict_gate.py` line in the `events/` listing of `architecture/140-arch.pipeline-foundation.md`; a CHANGELOG entry, since a default-on commit gate is a user-visible behavior change. (`interfaces:` in this frontmatter lists slices, not identifiers; the gate name is documented in `EVENTS.md`.)

**Done when:** `BANANA` and `RESOLVED` are rejected with the value and allowed set in the message; each real member passes; a review with no `verdict:` is rejected; a non-review doc with a bad `verdict:` is ignored; a test pins that the allowed set comes from the enum; the gate passes against the existing review corpus before it is enabled; `EVENTS.md`, the 140 listing, and CHANGELOG carry the gate.

---

## Part 3 — Stop parsing finding-shaped text that is not a finding (#91, #25)

`_extract_findings` runs `_FINDING_RE.finditer` over the entire response ([parsers.py:356](src/squadron/review/parsers.py#L356)). The regex deliberately accepts five shapes to tolerate formatting variance, so anything finding-shaped anywhere in the response parses as a finding — including the template's own specimen `### [PASS|CONCERN|FAIL] Finding title` when the model restates the format before using it. That is where `summary: "Finding title"` citing `src/module.py` came from, and the `concern` under a `PASS`.

**What the evidence says (20260912).** Checked every real captured response on disk (14 artifacts with a raw response; the debug log is polluted by test fixtures and contributed nothing real). Two of ~13 real responses — both slice 267 reviews, 2026-09-08 — are good reviews with 6 well-formed findings each and **no `## Findings` heading at all**; the findings start at line 2. So "no heading → discard" would throw away real reviews, and is rejected. Where the #91 phantoms sit relative to the heading is not recorded anywhere (the 35-finding artifact was never archived) and a live rerun of #91's own command came back clean — it is non-deterministic. The design therefore has to be right regardless of where the echo lands.

**Decision.** Three mechanical changes, each correct independently of the others:

1. **Skip fenced code blocks.** A model restating the format almost always fences it. Finding-shaped text inside ` ``` ` fences is never a finding. This is position-independent and is the change most likely to be the actual #91 fix.
2. **Bound to `## Findings` when the heading exists.** Take the span from the heading to the next `##` heading or end of document. Heading location is lenient (case, whitespace, bold, trailing punctuation). **When the heading is absent, scan the whole response as today** — the 267 reviews stay intact — and record `findings_section_located=False` on `ReviewResult`. That field does not feed `fallback_used` and does not extend the degraded-render computation at [persistence.py:198](src/squadron/review/persistence.py#L198): the slice-267 reviews are good reviews and stay clean artifacts without an embedded raw response. Part 6's digest is what surfaces the missing heading.
3. **Fence the specimen and delimit substituted content (#25).** All six templates (four review, two judge) show the required format as bare text; wrap it so the model is less likely to echo it as output and so change 1 skips it if it does. #25 is folded in whole, at its filed scope: descriptive XML tags around substituted document content in the six `prompt_template`s and in `builders/code.py`, per the issue's proposed fix.

The permissive five-shape matching inside the parsed region is not the bug and stays. Counts — finding-shaped matches in the whole response, inside fences, inside the bounded span, and surviving — are computed here and carried on `ReviewResult` for Part 6. Part 5's `location_verified` is the backstop for any phantom that gets through all three.

**Done when:** finding-shaped text inside a fence yields nothing; text outside `## Findings` yields nothing when the heading exists; the two slice-267 raw responses (real fixtures, headingless) still parse to 6 findings each with `findings_section_located=False` and no degraded rendering; all five shapes still parse inside the region; heading variants are located; all six templates and `builders/code.py` carry the fenced specimen and the #25 delimiters; a synthetic response echoing the specimen then writing real findings yields only the real ones. Existing tests encoding the unbounded scan are examined individually, not bulk-updated.

---

## Part 4 — Persist a failure artifact when the provider fails (#84)

The provider half is done: an empty final turn raises `ProviderError` carrying `finish_reason` and `reasoning_chars` ([agent.py:67](src/squadron/providers/openai/agent.py#L67)). The problem is what happens next, on both entry paths:

- **CLI** — `run_review`'s catch-all ([cli/commands/review.py:627](src/squadron/cli/commands/review.py#L627)) prints `Error: Review failed — {exc}` and exits 1. No artifact, no traceback, no record of `finish_reason`.
- **Pipeline** — `ReviewAction.execute`'s catch-all ([pipeline/actions/review.py:92](src/squadron/pipeline/actions/review.py#L92)) logs the exception and returns `success=False`. Better — the step fails and the traceback is in the log — but still no artifact.

The evidence the provider fix collects is discarded one layer up, on both paths. For a pipeline run, the artifact is the whole durable record.

**Decision.** A provider failure on either path writes a failure artifact. The artifact states that the provider failed (not that the review found nothing), carries the error text including `finish_reason` and `reasoning_chars`, and carries whatever tool telemetry exists — so "given tools, said nothing" is distinguishable from "ran without tools", which slice 265 D5 requires. Exit code / `success=False` are unchanged: this changes what is recorded, not whether the run fails.

**Why overwrite the live slot.** The plan entry's instinct ran the other way ("the prior FAIL artifact was overwritten"). But leaving the prior artifact in place means a pipeline gate reads a stale verdict from a previous run and waves the step through — the silent pass-through 901 exists to prevent. Fail-closed requires the slot to hold the failure. The prior content is preserved by `archive_existing_review` (#73), and a test pins that the failure path goes through it.

**Shape.** One failure-artifact writer shared by both paths, in `persistence.py`, taking the exception and the context the paths already have (template, model, slice info, telemetry). Not a fabricated `ReviewResult` with empty `raw_output` — that is the 487-byte artifact #84 complained about. `ProviderError` gets an explicit handler on each path; the catch-alls remain as process-boundary handlers.

**Frontmatter.** The failure artifact is emitted through the same frontmatter block `format_review_markdown` writes (extracted into a shared helper, not duplicated): `docType: review`, `verdict: UNKNOWN`, `status: complete`, and the slice-265 telemetry keys when tools were offered. `UNKNOWN` is a `Verdict` member, so Part 2's gate passes it by construction, and gates already treat UNKNOWN fail-closed (901). `status` names the document's lifecycle, not the run's outcome; `DocumentStatus` has no failure value and none is added. The distinguishing marker is in the body: a `## Provider Failure` section carrying the error text, in place of `## Summary`/`## Findings`. "Given tools, said nothing" vs "ran without tools" is the existing `toolsGiven`/`toolCallsMade` frontmatter, present or absent. No diagnostic key is added to frontmatter, for Part 6's reason.

**On #92.** Not the same failure. #92 is a full turn, correct telemetry, 3302 characters of prose review, no formatted block — it never reaches `_require_final_content`. It is a parse outcome: its verdict parses UNKNOWN, so the existing degraded path already embeds the raw response, and Part 6's digest adds `## Findings` not located with zero finding-shaped matches. A test here confirms that, and records which half of #92 this slice addresses (the artifact is honest) and which it does not (the content is not recovered).

**Done when:** a `ProviderError` on the CLI path and on the pipeline path each produce an artifact naming the provider failure with `finish_reason` and `reasoning_chars`; the artifact carries `## Provider Failure` and passes Part 2's gate; it is distinguishable from a clean UNKNOWN by that section and from a no-tools run by the telemetry keys; the prior artifact lands in `archive/`; CLI exit code stays 1 and pipeline `success` stays `False`; the #92 shape renders as degraded through the existing UNKNOWN path and its digest shows no `## Findings`.

---

## Part 5 — Bounds-check cited line numbers (#26)

`_check_path_existence` and `_check_diff_membership` already exist, but `location_path()` ([parsers.py:236](src/squadron/review/parsers.py#L236)) stops at the first `:` or `#`, so `:42` / `:42-50` is discarded. A line past the end of the file is the deterministic signature of a hallucinated citation. `_check_path_existence` fired on every #91 phantom and was ignored because it is WARNING-only — this part is what makes that fact survive.

**Decision (from the plan entry, 20260910).** Add `location_verified: bool | None` to `ReviewFinding`. Tri-state, not `bool`: `None` = not checked, `True` = path exists and line in bounds, `False` = checked and failed. A plain `bool` collapses "checked and bad" with "never checked", and the second is the common case — existence runs only with `cwd`, diff membership only with `diff_files`, both skip `UNVERIFIED_LOCATION` and whole-file citations. A gate reading `False` as "hallucinated" would reject most legitimate findings on non-code templates.

- `location_path()` keeps its contract — the findings-addressed gate depends on it. Line extraction is a sibling function.
- `:42` and `:42-50` parse; a location with no line suffix is a whole-file citation and stays `None`, matching the existing checks.
- Line count is read relative to the same `cwd` the existence check uses, through `_path_exists_under`'s resolution so bare-filename citations resolve the same way.
- Diff membership does **not** feed `location_verified`. A code review citing a file outside the diff may be legitimate context; it stays a WARNING.
- **Failure modes of the read.** This is a new I/O path on the parse path, driven by a model-supplied path, once per finding. `False` means exactly one thing: the file resolved and the cited line exceeds its line count. Every case where the check cannot run yields `None` with a WARNING naming the finding and the reason — no fourth state, and no `False` for a real citation whose file merely could not be read:
  - path does not resolve under `cwd` (existing check already warns) → `None`;
  - resolved path is not inside `cwd` after `resolve()` (a `../` citation) → `None`, and the file is never opened;
  - resolved path is a directory, unreadable (`OSError`), or larger than a single module-level byte cap → `None`;
  - lines are counted by streaming newline bytes in binary mode; no decode, so encoding cannot fail.
- **Written, not read.** Nothing consumes the field in this slice; it is not added to `StructuredFinding` or frontmatter, because that would imply a contract this slice is not making. Precedent: `ReviewResult.provenance`, added the same way in slice 300.

**Done when:** `None` everywhere when neither `cwd` nor `diff_files` is supplied; `parsers.py:999999` → `False`; a real in-bounds line → `True`; whole-file and `UNVERIFIED_LOCATION` → `None`; the range form parses; `location_path()` tests pass untouched; the #91 phantoms re-parse with `False`; a directory, an unreadable file, an over-cap file, and a `../` citation each yield `None` with a WARNING, and the file is not opened for the last.

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
- **Part 3 changes what every review parses.** Finding counts on real artifacts will change; that is the intent. Headingless responses keep today's behavior, so no known real review loses findings. Land 3 and 6 in the same branch so the counts are visible from the first run.
- **Part 5's model field** is defaulted and write-only. Low.

## Slice Review Disposition

Slice review (`917-review.slice.review-artifact-integrity.md`, glm-5.3, CONCERNS, 20260912). All four concerns and both notes accepted.

- **F005 (concern) — accepted, Part 4 gains a Frontmatter paragraph.** `verdict: UNKNOWN`, same frontmatter writer as a normal artifact, marker in the body; passing Part 2's gate is a done-when.
- **F006 (concern) — accepted, Part 5 gains a failure-mode list.** `False` means only "resolved and out of bounds"; every could-not-check case is `None` plus WARNING; containment, size cap, binary line count.
- **F007 (concern) — accepted, wording retracted.** "Mark degraded" is now `ReviewResult.findings_section_located`, rendered by Part 6 only. Headingless good reviews stay clean artifacts. Part 4's #92 sentence corrected to match.
- **F008 (concern) — accepted, Part 2 gains deliverables.** `EVENTS.md` row, 140 listing, CHANGELOG. `interfaces:` is a slice list, not an identifier list; unchanged.
- **F009 (note) — accepted.** 265 D5, here and in plan entry 15.
- **F010 (note) — accepted.** #25 folded at its filed scope: six templates plus `builders/code.py`.
- **F001–F004 (pass)** — no action.

## Verification walkthrough

Draft; refined at Phase 6 with commands actually run.

1. **Debug-log field.** Run a review that degrades; `tail -1 ~/.config/squadron/logs/review-debug.jsonl | jq keys` shows `degraded`, not `fallback_used`. `--output json` still shows `fallback_used` on the result.
2. **Verdict gate.** Stage a `docType: review` file with `verdict: BANANA`; commit is rejected naming `BANANA` and the four values. Change to `CONCERNS`; commit proceeds. Repeat with `RESOLVED`; rejected. Stage a slice design with `verdict: BANANA`; not rejected. Remove the probe.
3. **Finding scan.** Re-parse the two slice-267 archived raw responses (headingless); still 6 findings each, artifact flagged degraded. Parse a response with the specimen in a fence followed by real findings; only the real ones survive. Run `sq review slice 916 -vv --model kimi27` several times; no `"Finding title"` / `src/module.py` phantoms and no path-existence warnings on any run.
4. **Failure artifact.** Stub an empty final turn on the CLI path and on a pipeline review step. Each writes an artifact naming the provider failure with `finish_reason`/`reasoning_chars`; the prior artifact is in `reviews/archive/`; CLI exits 1, pipeline step fails.
5. **Line bounds.** Parse a response citing `src/squadron/review/parsers.py:999999` with `cwd`; `location_verified=False`. A real line → `True`. No `cwd` → `None`. Artifact output is unchanged.
6. **Digest.** Open a clean PASS artifact; the digest block is present. Re-run on the #91 fixture; whole-document and bounded counts differ.
