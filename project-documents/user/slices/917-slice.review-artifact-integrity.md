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

# Slice Design: Review Artifact Integrity — Verdict Validity and Legible Degradation

## Overview

Where 916 asked whether a review examined the right thing, this slice asks whether the **persisted artifact can be trusted, and whether its failures are legible**. Every part touches `review/parsers.py`, `review/models.py`, or `review/persistence.py`, which is why they are bundled rather than split: they contend for the same three files, and the same reason 916 and 917 were sequenced apart applies within 917 itself.

The slice's center of gravity is Part F. Live reviews of slice 916 produced an artifact carrying 35 findings, several of them phantom — `summary: "Finding title"` citing `src/module.py`, the template's own format specimen parsed as a real finding — including one at `severity: concern` under a top-line verdict of `PASS`. Two runs of the identical command against the same document and sha produced 8 findings and 35 respectively. The count tracks how much the model echoes the required format, not what it found. Review artifacts are currently being used to gate this project's own work; this slice is what makes them worth reading.

### Plan-entry corrections

The slice plan entry (entry 15, written 20260910–11) describes seven parts A–G. Two of its premises did not survive verification against `main` at `ca40196`, and this design supersedes the entry on both. The plan entry should be updated to match.

**Part B (#28) is already fixed and is dropped from scope.** `_verdict_from_findings` ([parsers.py:122](src/squadron/review/parsers.py#L122)) derives a lost verdict most-severe-wins — any FAIL yields FAIL, any CONCERN yields CONCERNS, otherwise PASS — and both UNKNOWN branches now log at WARNING. Shipped in `6d296aa`; issue #28 closed 20260730 as COMPLETED. Note that what shipped is the *opposite* of the approach the plan entry prescribes ("the fix does **not** upgrade or downgrade verdicts from finding severities; it makes the disagreement explicit"). That divergence is recorded here deliberately rather than silently reconciled — if the #5 precedent is to be honored, re-opening it is a separate decision on its own evidence, not a task inside this slice.

**Part C (#84) is narrowed to its artifact half.** The plan entry directs the implementer to "recover and verify" an uncommitted fix on the `266-slice.tool-use-configuration-and-limits` branch. That branch has zero commits ahead of `main` and is fully merged; the provider half already landed. `TurnResult.finish_reason` and `.reasoning_chars` ([agent.py:102-107](src/squadron/providers/openai/agent.py#L102-L107)), `_require_final_content` raising `ProviderError` on both loop exits ([agent.py:67](src/squadron/providers/openai/agent.py#L67), called at lines 222 and 432), and `TestEmptyFinalTurn` ([test_agentic_loop.py:627](tests/providers/openai/test_agentic_loop.py#L627)) are all present. Separately, the prior-artifact overwrite the entry worries about is already prevented by `archive_existing_review` (the #73 fix). What remains is the CLI side, described in Part C below.

With B dropped and C narrowed, effort drops from 5/5 to **4/5**. Sequence becomes **E → A → F → C → D → G**.

## Goals

- A review artifact carrying an invalid `verdict:` cannot be committed (A).
- The finding parser cannot extract findings from text outside the `## Findings` section (F).
- A review that produces no usable output says why, in a persisted artifact, rather than vanishing into a one-line CLI error (C).
- A hallucinated line-number citation is detected and recorded as a fact on the finding (D).
- Every artifact — including a confident PASS — carries enough of a run digest to diagnose the next #91 (G).
- `review-debug.jsonl`'s `fallback_used` stops meaning something different from `ReviewResult.fallback_used` (E).

## Non-Goals

- **No verdict manipulation from finding severities beyond what already ships.** The #5 precedent stands. Part D writes `location_verified` but nothing reads it; no gate in this slice rejects, downgrades, or filters a finding.
- **No semantic hallucination detection.** Parts D and F are *mechanical*: a citation that names a real file at a real line, describing something that is not there, remains a problem no deterministic filter solves. Bounding that claim is part of the deliverable, not a caveat on it.
- **No `max_tokens` sizing work.** If Part C's investigation shows the empty turn traces to `finish_reason="length"` against a reasoning model, that is follow-up, not this slice.
- **Issue #27** (fabricated review content, unreproducible, seen twice) is not scoped. It has no root cause and no reproduction. Parts C and G are the instrumentation that would catch a recurrence; re-assess #27 after this slice rather than scoping it blind.

---

## Part E — `fallback_used` names two different things (#87)

**Effort 1/5. First because it is contained and touches a field the later parts log through.**

`parse_review_output`'s genuinely-unknown branch calls `_write_debug_log(fallback_used=True, ...)` ([parsers.py:516](src/squadron/review/parsers.py#L516)) while deliberately leaving `ReviewResult.fallback_used` at `False` for the same event — and the existing comment at that site says so explicitly. The two names mean different things: the debug-log field means "a degraded parse of some kind occurred", the result field means "findings were un-derivable from a *known* verdict".

**Decision:** rename the debug-log field to `degraded`. `ReviewResult.fallback_used` is unchanged — it is a public serialized field (`to_dict`) with downstream consumers, and its meaning is correct for what it names.

**Compat.** `review-debug.jsonl` is an on-disk append-only format with existing entries. Old entries keep `fallback_used`; new entries write `degraded`. No migration of existing lines and no dual-write: the file is a diagnostic log read by humans and ad-hoc `jq`, not a parsed interface with a schema contract. The decision to break rather than dual-write is recorded here because it is a decision, not an oversight — a dual-written field would preserve exactly the ambiguity the rename exists to remove.

**Success criteria**
- `_write_debug_log` takes `degraded: bool`; no call site passes `fallback_used`.
- All three call sites in `parse_review_output` pass `degraded=True` (unchanged behavior — all three already do).
- A test asserts the emitted JSONL line carries `degraded` and not `fallback_used`.
- `ReviewResult.fallback_used` and its `to_dict` key are untouched.

---

## Part A — verdict frontmatter is unvalidated against the enum (#77)

**Effort 2/5.**

Nothing checks a review artifact's `verdict:` frontmatter key against `Verdict` ([models.py:10-16](src/squadron/review/models.py#L10-L16): PASS, CONCERNS, FAIL, UNKNOWN). Hit for real on slice 266, where both artifacts committed with the invented value `RESOLVED` and the pre-commit frontmatter gate accepted them (corrected in `f07a01c`). A `verdict: BANANA` artifact passes `cf validate frontmatter` today — the file *is* checked, the verdict value simply is not among what is checked.

This matters because an invalid verdict does not fail loudly; it degrades to UNKNOWN downstream, and `CheckpointTrigger.ON_CONCERNS`'s set is `{CONCERNS, FAIL, UNKNOWN}` — so an invalid verdict silently *trips a checkpoint*, indistinguishable from a genuine UNKNOWN.

**Decision: squadron-side validator as its own COMMIT event action** (issue #77's option 2, which the issue itself recommends). The alternative — teaching `cf validate frontmatter` a per-docType enumerated check — requires a cross-repo change and a verdict list living in context-forge that would drift from `Verdict` the first time a member is added. A squadron-side action reads the enum directly: single source of truth, no cross-repo coupling, no parallel literal list.

The insertion point is clean and already precedented. `src/squadron/events/builtin/` holds four actions; `FrontmatterGateAction` ([frontmatter_gate.py](src/squadron/events/builtin/frontmatter_gate.py)) is the shape to follow — a `name`, an `events = frozenset({EventType.COMMIT})`, a no-op `validate`, and an async `execute` returning `ActionResult`. The new action is simpler than that one: it reads staged files directly rather than shelling out.

**Design**

- New action `squadron.review-verdict-gate` in `src/squadron/events/builtin/review_verdict_gate.py`.
- Scope: staged `.md` files under the reviews directory. Non-review markdown is ignored — the gate must not fire on a slice design that happens to contain the word `verdict`. Selection keys on `docType: review` in the file's own frontmatter, not on path or filename: per the project rule, user-facing labels and paths are not logical structure, and `REVIEWS_DIR` placement is a convention while `docType` is the document's own declaration.
- A file with `docType: review` and no `verdict:` key is a violation (a review artifact must state a verdict). A file whose `verdict:` value is not a `Verdict` member is a violation.
- Failure is explicit: the message names the offending file, the offending value, and the allowed set, derived from `Verdict` at runtime. **No silent coercion** — not to UNKNOWN, not to anything.
- Registration alongside the existing builtins, enabled by default on COMMIT like the frontmatter gate. A project's `events.yaml` can disable it.

**Failure modes** (per the project's failure-mode enumeration rule): a staged file that cannot be read, and a staged file whose frontmatter does not parse. Both must be *observable* — the gate logs at WARNING and does not pass the commit on an unreadable file it was asked to check, matching the 172 D6 posture the frontmatter gate already holds ("a gate that cannot determine validity must not pass"). A file with no frontmatter at all is not a review artifact and is skipped silently.

**Success criteria**
- A staged review with `verdict: BANANA` fails the commit, and the error names `BANANA` and lists the four allowed values.
- A staged review with `verdict: RESOLVED` — the real slice-266 case — fails.
- Each of PASS, CONCERNS, FAIL, UNKNOWN passes.
- A staged review artifact with no `verdict:` key fails.
- A staged non-review markdown file with an invalid `verdict:` value in its frontmatter passes (not this gate's business).
- Adding a member to `Verdict` requires no edit to the gate; a test pins this by asserting the gate's allowed set is derived from the enum.
- The action appears in `sq events` listings and can be disabled via `events.yaml`.

---

## Part F — the parser scans the whole response for findings (#91)

**Effort 2/5. The live correctness bug; moved early because bounding the scan changes what C, D, and G reason about.**

`_extract_findings` runs `_FINDING_RE.finditer(text)` over the **entire** model response ([parsers.py:356](src/squadron/review/parsers.py#L356)) with no bounding to the `## Findings` section, while `_FINDING_RE` deliberately accepts five permissive shapes to tolerate formatting variance. Any finding-shaped text anywhere parses as a real finding: a model restating the required format, or the template's own specimen — `### [PASS|CONCERN|FAIL] Finding title`, present at the same relative position in all four templates ([code.yaml:49](src/squadron/data/templates/code.yaml#L49), [slice.yaml:52](src/squadron/data/templates/slice.yaml#L52), [arch.yaml:105](src/squadron/data/templates/arch.yaml#L105), [tasks.yaml:52](src/squadron/data/templates/tasks.yaml#L52)) — echoed back by the model.

**Decision: bound the scan to the `## Findings` section.** This removes the incidental-match surface structurally while preserving the permissive shape matching inside the section, which exists for good reason and is not the defect. All four templates already instruct `## Findings` at a consistent position, so the bounding contract is uniform across template types.

**Design**

- A section-extraction step runs before `_FINDING_RE`: locate the `## Findings` heading, take text from there to the next `##`-level heading or end of document, and run the existing finding regex over only that span.
- **Lenient location of the heading**, per the project's parsing rule: case-insensitive, tolerant of leading whitespace and of a bolded or trailing-punctuation variant. What is bounded is *where* findings may be found, not *how strictly the heading is spelled* — a strict heading match would recreate the #28 shape (strict outer parse, lenient inner parse) one level up.
- **No `## Findings` section found → parse nothing, and say so.** This is the consequential sub-decision. The alternative — falling back to scanning the whole document — reintroduces the bug on exactly the malformed responses where it does most damage. A model that emitted no `## Findings` section did not follow the format, which is a degraded parse and must present as one: WARNING log, debug-log entry, and the existing `_findings_not_parsed_section` rendering in the artifact. This is precedented; the parser already refuses to fabricate findings from unstructured prose rather than guessing.
- **Counts are retained for Part G**: how many finding-shaped matches the whole document contains versus how many survive the bounding. That difference is the #91 signature, and G reports it.

**Fold in #25 (delimit substituted document content).** The plan entry supersedes #25's exclusion — it was excluded as unsymptomatic prompt hardening and now has a symptom. Once the parser is bounded, the complementary prompt-side change is to delimit substituted document content in the review templates with XML tags, so content under review cannot be confused with the model's own output. Parser-side bounding is the load-bearing fix and lands first; #25 is the defense in depth, not a substitute for it.

**Success criteria**
- A response whose prose *outside* `## Findings` contains `### [CONCERN] Something` yields zero findings from that text.
- The exact #91 reproduction — a response echoing the template specimen `### [PASS|CONCERN|FAIL] Finding title` — yields no phantom finding. A regression test uses a real captured response, not a synthesized one (project rule: the fixture must include the format the parser consumes in production).
- All five permissive finding shapes still parse when they appear inside `## Findings`.
- A response with findings but no `## Findings` heading parses zero findings, logs a WARNING, writes a debug-log entry, and renders the "findings not parsed" section rather than "No specific findings."
- A heading variant (`##  findings`, `## Findings:`, `## **Findings**`) is still located.
- The two 916 review runs that produced 8 and 35 findings, re-parsed from captured raw output, produce consistent counts.
- Review templates delimit substituted document content with XML tags (#25).

---

## Part C — a review that produces no usable output must still leave an artifact (#84)

**Effort 2/5. Narrowed from the plan entry — see "Plan-entry corrections" above.**

The provider half has landed: an empty final turn now raises `ProviderError` carrying `finish_reason` and `reasoning_chars`, rather than returning nothing. That converts a silent 487-byte UNKNOWN artifact into a raised error — strictly better, and it is where the remaining problem now lives.

The CLI has no handler for it. `run_review`'s catch-all ([review.py:627](src/squadron/cli/commands/review.py#L627)) turns *any* exception into `Error: Review failed — {exc}` and `typer.Exit(1)`. So today an empty final turn produces: no artifact, no telemetry, no persisted record of `finish_reason` or `reasoning_chars`, and one red line in a terminal that may not be attached. The evidence the provider fix went to the trouble of collecting is discarded one layer up. For a review run inside a pipeline, that is the whole record.

**Decision: a review that fails to produce output leaves a persisted artifact recording why.** The artifact is the durable interface — it is what a pipeline gate reads, what a human returns to, and what made #91 and #92 diagnosable at all. A failure that exists only as terminal output is not observable in the sense the project's failure-mode rule requires.

**Design**

- `ProviderError` (and its subclasses) get an explicit handler in the CLI review path, distinct from the catch-all. The catch-all stays as the process-boundary handler it is.
- The failure artifact carries: verdict UNKNOWN, an explicit statement that the *provider* failed rather than that the review found nothing, the error text including `finish_reason` and `reasoning_chars`, and whatever tool telemetry is available. This is the distinction slice 266's D5 requires: "the model was given tools and said nothing" must not read identically to "the review ran without tools."
- Exit code stays 1. This part changes what is *recorded*, not whether the command fails.
- The prior artifact is not destroyed: `archive_existing_review` already handles this (#73), and a test pins that the failure path goes through it rather than around it.

**On #92.** The plan entry notes #92 — a model that completed its analysis in prose and never emitted the formatted block, landing as UNKNOWN with zero findings — and says to fold it into C if the cause proves shared. It is **not** shared: #92 is a full turn with correct telemetry and 3302 characters of substantive review, so it never reaches `_require_final_content` and never raises. It is a parse-side outcome, and Part F's "no `## Findings` section found" path is what makes it present legibly. #92 stays out of C's scope; verifying that F's degraded rendering covers it is a success criterion here, and if it does not, #92 remains open for a follow-up.

**Success criteria**
- A review whose provider raises `ProviderError` writes an artifact rather than only printing to the terminal.
- That artifact states the provider failed, and contains the `finish_reason` and `reasoning_chars` from the error.
- The artifact is distinguishable from both a clean UNKNOWN and a review that ran without tools.
- A pre-existing artifact at the same path is archived, not overwritten in place.
- Exit code remains 1.
- The #92 shape — a full prose response with no formatted block — renders as a degraded parse under Part F, and a test captures which of #92's two halves (legible artifact vs. recovering the content) this slice does and does not address.

---

## Part D — line-number citations are never validated (#26)

**Effort 2/5. F's safety net: `_check_path_existence` fired correctly on every #91 phantom and was ignored because it is WARNING-only.**

`_check_path_existence` ([parsers.py:305](src/squadron/review/parsers.py#L305)) and `_check_diff_membership` ([parsers.py:256](src/squadron/review/parsers.py#L256)) already exist, but `location_path()` ([parsers.py:236](src/squadron/review/parsers.py#L236)) stops at the first `:` or `#`, so the `:42` / `:42-50` suffix is parsed off and discarded. Extend to bounds-check the cited line against the file's actual length — the deterministic signature of a hallucinated citation.

*(Note: the plan entry cites these as `_location_path` at parsers.py:260 and `_check_diff_membership` at :231. The function is public and named `location_path`, and line numbers have shifted. The plan entry's `_parse_findings` is likewise `_extract_findings`.)*

**Decision (carried from the plan entry, 20260910): add `location_verified: bool | None` to `ReviewFinding` — tri-state, not `bool`.** Issue #26 proposed a plain `bool`; that collapses "checked, and the citation is bad" together with "never checked" into a single `False`, and the second case is the common one. `_check_diff_membership` runs only for code templates with `diff_files` supplied, `_check_path_existence` only when `cwd` is supplied, and both skip `UNVERIFIED_LOCATION` and whole-file locations — so a gate reading `False` as "hallucinated" would reject most legitimate findings on non-code templates. `None` means not checked, `True` means the path exists and the cited line is in bounds, `False` means checked and failed. That is the only shape a downstream gate can act on safely.

**The field is written but not read in this slice.** 917 populates it; nothing consumes it. Deliberate, and precedented by `ReviewResult.provenance` ([models.py:72](src/squadron/review/models.py#L72)), added the same way in slice 300. Whoever builds the gate owns the policy; this slice's job is to stop discarding the fact. The existing WARNING logs stay as they are.

**Design**

- `location_path()` keeps its current contract (consumers outside the module depend on it — the findings-addressed gate). Line extraction is a **sibling** function, not a change to it.
- Parse `:42` and `:42-50` forms. A location with no line suffix is a whole-file citation and is skipped, matching the existing checks' posture.
- Bounds check reads the file's line count relative to the same `cwd` the existing existence check uses, and reuses `_path_exists_under`'s resolution so a bare-filename citation resolves the same way it does today.
- Set `location_verified` on the finding: `None` when no check ran, `True` when path exists and line is in bounds, `False` when either failed.
- The field is not added to `StructuredFinding` or to frontmatter in this slice — nothing reads it yet, and putting it in the artifact's machine-readable block implies a contract this slice is explicitly not making.

**Explicitly bounded.** Existence and bounds are *mechanical* hallucination detection only. A finding citing a real, in-bounds line that describes something not there remains a semantic problem no deterministic filter solves.

**Success criteria**
- `location_verified` is `None` on every finding when neither `cwd` nor `diff_files` is supplied.
- A finding citing `src/squadron/review/parsers.py:999999` gets `location_verified=False`.
- A finding citing a real in-bounds line gets `True`.
- A whole-file citation and an `UNVERIFIED_LOCATION` finding both get `None`.
- `:42-50` range form parses; the check applies to the range's bounds.
- `location_path()`'s existing behavior and public contract are unchanged; its existing tests pass untouched.
- The #91 phantom findings, re-parsed, carry `location_verified=False`.

---

## Part G — only degraded reviews persist raw output (#93)

**Effort 2/5. Last, because it reports the validation counts F introduces.**

`format_review_markdown` appends `### Raw Response` only when the review degraded ([persistence.py:310](src/squadron/review/persistence.py#L310)), so a confident PASS is the least auditable artifact on disk while artifacts that announce their own unreliability keep full evidence. Both #91 and #92 were diagnosable *only* because those runs degraded. The 8-vs-35 finding discrepancy on identical inputs is invisible in either persisted artifact.

**Decision: a small always-on run digest, not unconditional full raw text.** Persisting every response in full is a large, mostly-unread cost on the common case; the digest is cheap enough to be unconditional and would have made #91 visible in the artifact itself. Existing raw-response behavior on degraded runs and the `-vv` appendix are both unchanged — the digest is additive.

**Digest contents**

- Response length in characters.
- Tool-call count (already available as `tool_calls_made`).
- Whether a `## Summary` block was present.
- Whether a `## Findings` section was located (Part F).
- Finding-shaped matches in the whole document vs. matches inside the bounded section vs. findings surviving validation.

That third group is the #91 signature made visible: a document with 35 whole-document matches and 3 bounded ones is self-evidently the failure mode, in the artifact, without needing the raw text.

**Design**

- The counts originate in the parser (Part F computes them) and travel on `ReviewResult` to the formatter. The formatter does not re-parse — a second parse in the persistence layer would drift from the first, which is the DRY failure this project's rules name directly.
- Rendered as a compact block in the artifact body. Frontmatter placement is rejected: frontmatter is a consumed contract (`cf` scans it, Part A now gates it), and adding diagnostic fields there invites downstream coupling this slice does not intend.
- Emitted for every review including a clean PASS. That is the entire point.

**Success criteria**
- A PASS review's artifact carries the digest.
- The digest reports whole-document vs. bounded vs. surviving finding counts, and they differ on a #91-shaped response.
- The digest is present regardless of verbosity.
- Existing degraded-path `### Raw Response` behavior and the `-vv` appendix are unchanged.
- The counts come from the parser, not a re-parse in `persistence.py`.

---

## Cross-Part Interactions

- **F → G.** G reports counts F computes. G cannot land first, and the counts must travel on `ReviewResult` rather than being recomputed.
- **F → D.** D is F's safety net. Both are mechanical checks on the same findings list; D runs after F's bounding, on the surviving findings only.
- **F → C.** F's "no `## Findings` section" path is what makes #92 legible. C verifies it and does not duplicate it.
- **A ↔ E.** Independent; both contained; sequenced first to keep the shared files quiet while F lands.
- **D → `ReviewFinding`.** The only model change in the slice. `location_verified` defaults to `None`, so every existing construction site stays valid.

## Risks

- **Part A adds a commit-path gate.** A gate that misfires blocks commits repo-wide. Mitigated by scoping on `docType: review` (not path), by skipping files without frontmatter silently, and by `--no-verify` remaining available. The gate must be tested against the project's own existing review corpus before it is enabled by default.
- **Part F changes what every review parses.** Finding counts will change on real artifacts — that is the intent, but it means existing tests encoding the unbounded behavior will fail and must be examined individually rather than updated in bulk. A test that breaks here is evidence, not noise.
- **Part D adds a `ReviewFinding` field.** Low: defaulted, written-not-read, precedented by `provenance`.

## Verification Walkthrough

Draft — to be refined at Phase 6 completion with commands actually run and output actually observed.

**Part E**
1. Run any review that degrades (e.g. against a document that produces no summary), then `tail -1 ~/.config/squadron/logs/review-debug.jsonl | jq 'keys'`.
2. Confirm `degraded` is present and `fallback_used` is absent.
3. Confirm `sq review ... --output json` still emits `fallback_used` on the result.

**Part A**
1. Create `project-documents/user/reviews/999-review.tasks.verdict-probe.md` with `docType: review` and `verdict: BANANA`.
2. `git add` it and attempt a commit. Confirm the commit is rejected, and that the message names `BANANA` and lists PASS/CONCERNS/FAIL/UNKNOWN.
3. Change to `verdict: CONCERNS`; confirm the commit proceeds.
4. Repeat with `verdict: RESOLVED` (the real slice-266 value); confirm rejection.
5. Stage a slice-design document containing `verdict: BANANA` in its frontmatter; confirm it is *not* rejected.
6. Delete the probe file.

**Part F**
1. Take the captured 916 review response that produced 35 findings. Re-parse it and confirm the phantom findings — `"Finding title"`, `"Title"` citing `src/module.py` — are gone.
2. Re-parse the response that produced 8 findings; confirm the two counts now agree.
3. Run a live review (`env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT uv run sq review code --diff main -vv --no-save`) twice against the same sha; confirm finding counts are stable.
4. Confirm a response with no `## Findings` heading renders the "findings not parsed" section, not "No specific findings."

**Part C**
1. Induce a `ProviderError` from the review path (a stubbed empty final turn is sufficient; the live reasoning-model case is opportunistic).
2. Confirm an artifact is written, and that it names the provider failure and carries `finish_reason` and `reasoning_chars`.
3. Confirm a pre-existing artifact at that path landed in `reviews/archive/`.
4. Confirm exit code 1.

**Part D**
1. Hand-write a review response citing `src/squadron/review/parsers.py:999999`; parse with `cwd` supplied; confirm `location_verified=False`.
2. Cite a real in-bounds line; confirm `True`.
3. Parse with no `cwd` and no `diff_files`; confirm `None` throughout.
4. Confirm no artifact output changed — the field is written, not rendered.

**Part G**
1. Run a review that passes cleanly. Open the artifact.
2. Confirm the digest block is present, with response length, tool-call count, summary/findings presence, and the three finding counts.
3. Re-run against the #91 response; confirm whole-document and bounded counts differ visibly in the artifact.

## Effort

**4/5** (reduced from the plan entry's 5/5 with Part B dropped and Part C narrowed). Six parts, all in three files plus one new events action.
