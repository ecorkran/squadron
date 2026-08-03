---
docType: slice-design
slice: review-resolution-recording-that-findings-were-addressed
project: squadron
parent: project-documents/user/architecture/300-slices.eval-actions-llm-as-judge-scoring.md
dependencies: [305]
interfaces: []
dateCreated: 20260802
dateUpdated: 20260802
status: not_started
---

# Slice Design: Review Resolution — Recording That Findings Were Addressed

## Overview

A FAIL (or CONCERNS) review's findings get addressed, the fix lands, and the
review artifact still reads `verdict: FAIL`. Downstream gating (`cf next`
reports `Blocked: review verdict does not clear threshold`) stays closed on a
verdict that is no longer true of the code, and there is no mechanism to say
so. Issue [#51](https://github.com/ecorkran/squadron/issues/51). Observed live
on slice 305 itself: nine findings fixed across eight commits, full suite
green, `cf status` still `review-failed` until the Project Manager hand-edited
the frontmatter.

The constraint that shapes everything here: **agents were barred from editing
`verdict:`, and that bar stands.** They changed it too readily, and invented
status values when they did. A verdict is a fact about a review run at a
moment; mutating it destroys the evidence and makes the artifact
unfalsifiable. The missing thing is not a writable verdict — it is a *second
assertion*, "these findings have been addressed," which is a different claim
from "this review passed" and currently has nowhere to live. Any design where
one word an agent can write unprompted unblocks a gate has rebuilt the
original problem under a new name.

Slice 305 already built the decision procedure: per-finding dispositions
(`addressed` / `unaddressed` / `moved`+successor / `disputed`) derived from a
diff plus a judge over the residue, persisted as a `gate-evidence` artifact.
But it is reachable only from inside a pipeline loop. This slice makes the
same derivation invocable interactively — `sq review resolve` — and persists
its output as a **resolution artifact** that sits beside the review, never in
it.

### Design principles carried forward from 305

1. **Derived, not declared.** The command exposes no flag that asserts
   "addressed." Every status comes from the deterministic screens or from a
   verified judge claim. An agent may *invoke* the command; it cannot
   *fabricate* its output.
2. **The review artifact is immutable evidence.** Resolution is a second
   artifact. Nothing in this slice writes to a review file except the new
   `reviewedSha` stamp at *authoring* time (Part A), which is squadron writing
   its own generated file.
3. **UNKNOWN means the check could not run.** A residue finding no judge
   settled is `disputed` → resolution `UNKNOWN`, never a quiet pass.

## Value

- **Unblocks the interactive fix cycle.** Today the only honest options after
  addressing a FAIL are a full re-review (which silently overwrites the
  artifact — see Part D) or a PM verdict edit justified by prose. This slice
  gives that edit machine-checkable evidence, and gives future cf-side gating
  something to consume.
- **One derivation, two entry points.** The loop path (305) and the
  interactive path now share screens, judge, verification, and rendering —
  no second implementation to drift.
- **Closes a data-loss hazard** discovered during scoping: re-running
  `sq review code <N>` destroys hand-written content in the review file with
  no warning (Part D).

## Technical Scope

**In scope:**

- Part A — stamp `reviewedSha` into review frontmatter at authoring time.
- Part B — `sq review resolve <index>` command deriving per-finding
  dispositions via 305's screens + judge, writing a
  `{index}-resolution.{reviewType}.{name}-r{n}.md` artifact. Includes the
  small refactor that decouples 305's judge transport from `ActionContext`.
- Part C — the consumer contract: documented frontmatter schema for the
  resolution artifact, the interim PM procedure, and the coordination note to
  Context Forge. No cf code changes (review-gating lives in cf, not squadron;
  the seam is the frontmatter contract).
- Part D — overwrite guard in `save_review_file`: WARNING plus archived copy
  when an existing review file would be replaced.
- Slash-command parity: `/sq:review resolve` in `commands/sq/review.md`
  (interface-parity is a standing project rule).

**Explicitly excluded:**

- Any edit to `verdict:` by squadron. The PM procedure stays manual.
- cf-side gating changes (reading the resolution artifact). Tracked as the
  coordination item in Part C.
- Running a fresh review from inside `resolve`. The full
  fix→review→gate cycle is the pipeline's job (`findings-addressed-cycle`);
  this command is its lightweight interactive complement, not a replacement.
- Resolution for `slice`/`arch`/`tasks` reviews beyond what falls out for
  free. The screens are code-diff-based; `--type code` is the target. Other
  types are accepted but their diff evidence is weaker — the judge leg
  carries them. No type-specific screen work in this slice.

## Dependencies

### Prerequisites
- Slice 305 complete (screens, parsing, judge, verification, evidence
  rendering — all shipped in `pipeline/actions/findings_addressed/`).

### Interfaces Required
- `review/persistence.py` (`format_review_markdown`, `save_review_file`) for
  Parts A and D.
- `review/git_utils.run_git` for diff computation (public since 305 T14).
- `run_review_with_profile` transport for the judge leg.
- Review frontmatter findings (`id`, `severity` lowercase, `category`,
  `summary`, `location`) as written by `format_review_markdown` — the parse
  in Part B must consume exactly this shape (the production shape, per the
  F002 lesson: no hand-rolled fixture formats).

## Architecture

### Component Structure

```
review/
  addressed/             NEW package — the context-free core, RELOCATED
    models.py             FindingRecord/FindingStatus vocabulary,
                           read_findings, records_from_frontmatter (new)
    parsing.py             judge status-line parsing (moved verbatim)
    verification.py        verify_outcomes, derivation rule (moved verbatim)
    judge.py               context-free transport core (extracted + moved)
  resolution.py          NEW — orchestration: load review, compute diff,
                          screen, judge residue, derive, persist
  persistence.py         Part A: reviewedSha stamp; Part D: overwrite guard
cli/commands/review.py   NEW subcommand: review resolve
pipeline/actions/findings_addressed/
  screens.py, evidence.py, policy.py   stay — loop-specific machinery
  judge.py               becomes a thin ActionContext wrapper over
                          review/addressed/judge.py
commands/sq/review.md    add `resolve` subcommand
```

**Dependency direction (review F002).** The established direction is
pipeline (140) consumes the review subsystem — and every module in
`findings_addressed/` already imports `squadron.review.*`. Having
`review/resolution.py` import `pipeline/actions/` internals would invert
that and create a review ↔ pipeline package-level cycle. So the
context-free core *moves* into `review/addressed/` rather than being
imported across the boundary: models, parsing, verification, and the
extracted judge transport are review-domain logic (they reason about
findings and judge output, not about pipeline execution). What stays in
`pipeline/actions/findings_addressed/` is exactly what is loop-specific:
the screens that need a fresh review, the gate-evidence artifact, and the
policy that plugs into the gate registry — each importing the moved core
in the already-established direction. The moves are mechanical
(import-path updates; 305's tests must pass unchanged), and the gate
policy's behavior is untouched.

### Data Flow

```
sq review resolve 305 [TYPE] [--model X] [--no-judge] [--since REF]
  │
  ├─ locate review artifact  project-documents/user/reviews/305-review.{type}.{name}.md
  │    TYPE omitted → glob 305-review.*.md; exactly one match → inferred,
  │    several → error listing them (never guess)
  ├─ parse frontmatter → verdict, findings[] → FindingRecord[] (severity
  │    normalized at the boundary, per 305 F001)
  ├─ CONCERN+ subset = what resolution is accountable for
  │    empty AND review verdict PASS        → ADDRESSED, annotated, no judge
  │    empty BUT review verdict FAIL/CONCERNS → UNKNOWN + WARNING naming the
  │      mismatch — the parser is known to drop findings (#28 lineage), and
  │      inconsistent evidence is a check that could not run, not a pass
  ├─ diff base = frontmatter reviewedSha
  │    │  absent (legacy review) → last commit touching the review file
  │    │    (`git log -1 --format=%H -- <file>`), WARNING naming the fallback
  │    └  --since REF overrides both
  ├─ round diff = compute_round_diff-equivalent over base..HEAD + working tree
  │    git failure → resolution UNKNOWN, WARNING names the exact command
  ├─ Screen: empty diff → every CONCERN+ finding unaddressed (nothing changed
  │    since the review; nothing can have been addressed) → FAIL leg, no judge
  ├─ Judge over all remaining findings (there is no fresh review, so 305's
  │    exact-match screen cannot run — see Decision 3)
  │    --no-judge → residue stays disputed → UNKNOWN
  │    judge transport failure, timeout, or unreadable response → UNKNOWN
  │      + WARNING (305's semantics, restated here, not left to inference)
  │    diff over the injection cap (--since can reach arbitrarily far back)
  │      → UNKNOWN + WARNING naming the cap and the base used — the
  │      architecture's cap constraint applies to this path unchanged
  ├─ verify_outcomes: ADDRESSED over an untouched path → disputed (reused
  │    verbatim); MOVED always downgraded (no fresh findings to verify a
  │    successor against — documented, not special-cased)
  ├─ derive: any disputed → UNKNOWN; any unaddressed → UNADDRESSED;
  │    else ADDRESSED   (UNKNOWN evaluated before failure, 305 rule)
  └─ write {index}-resolution.{type}.{slice-name}-r{n}.md
       docType: review-resolution; never touches the review file
```

## Technical Decisions

**Decision 1 — `reviewedSha` is stamped at authoring time (Part A).**
"What changed since the review" needs an anchor. The review file's own git
history is a usable fallback but decays: the PM's verdict edit today moved
the file's last-touched commit past the code the review actually assessed.
So `format_review_markdown` gains `reviewedSha: {HEAD at authoring}`,
written by both persistence paths (CLI and pipeline action — interface
parity). Absent key on legacy reviews → fallback + WARNING; `--since`
overrides. The stamp is squadron writing its own generated artifact, which
does not violate the immutability principle (that principle governs
post-hoc mutation).

**Decision 2 — resolution is a separate artifact, `-r{n}` versioned.**
Filename `{index}-resolution.{reviewType}.{slice-name}-r{n}.md`, first
attempt `r1`, subsequent attempts increment — never overwrite, matching
305's evidence pattern. The name contains no `-review.` segment, so
metrology's `*-review.*` glob (non-recursive, verified) never sweeps it.
`docType: review-resolution`. A field *on the review* was rejected: the
review is immutable evidence, and Part D exists precisely because writes to
that file are destructive today.

**Decision 3 — no fresh review means no exact-match screen; the judge
carries more weight here than in the loop.** 305's Screen 2 keys on the
fresh review's findings, which do not exist on this path. Consequences,
accepted rather than hidden: (a) the judge is consulted for *all* CONCERN+
findings whenever the diff is non-empty — the interactive path pays one
model call where the loop often pays none; (b) `MOVED` is always downgraded
to `disputed` (no fresh findings to verify a successor against). Both are
stated in the artifact's rendering so a reader knows which machinery ran.
Running a fresh review inside `resolve` to restore Screen 2 was rejected:
it duplicates `sq review code` and reintroduces the overwrite hazard.

**Decision 4 — the judge transport is extracted, not duplicated, and the
context-free core relocates to `review/addressed/`.** `judge_residue` is
coupled to `ActionContext` (resolver, params, cwd). Part B extracts a
context-free core — `judge_residue_core(residue, fresh_findings, diff, *,
model_id, profile, cwd)` — and moves it, together with the models, parsing,
and verification modules it depends on, into `review/addressed/` (see
Dependency direction above). The existing `judge_residue(context, …)`
becomes a thin wrapper in `pipeline/actions/findings_addressed/` that
resolves model/profile from the context and delegates. No behavior change;
the existing 305 test suite must pass unchanged against the wrapper. CLI
model resolution follows the review commands' existing cascade (`--model`
flag → config defaults → template default).

**Decision 5 — derivation vocabulary is reused, with a distinct top-level
field.** Per-finding statuses are 305's `FindingStatus` enum, unchanged.
The artifact's summary field is `resolution: ADDRESSED | UNADDRESSED |
UNKNOWN` — deliberately *not* `verdict:`, so no tool that greps review
frontmatter for `verdict:` can mistake a resolution artifact for a review,
and no human reads it as a review outcome.

**Decision 6 — squadron writes the record; cf owns the gate (Part C).**
Review-gating lives in Context Forge; the seam is the frontmatter contract.
This slice ships the contract (schema below) and the interim procedure:
*the PM may update a review's `verdict:` when a resolution artifact with
`resolution: ADDRESSED` exists for it, citing the artifact in the commit
message* — exactly today's practice, now evidence-backed. Whether cf's
`workflow_check`/`cf next` learn to read resolution artifacts directly is
cf's decision, raised as a coordination item, not assumed here.

**Decision 7 — overwrite guard archives, not refuses (Part D).**
`save_review_file`, before replacing an existing file: WARNING naming the
file, and a copy preserved under `project-documents/user/reviews/archive/`
with its original name. Refusing outright would break every legitimate
re-review; a `--force` dance punishes the common case. The archive
directory is invisible to metrology's non-recursive glob; **verification
item:** confirm cf's artifact scanning also ignores `archive/` before
landing — if it recurses, mangle the archived name (e.g. strip the
`-review.` segment) instead.

### Resolution artifact schema (Part C contract)

```yaml
---
docType: review-resolution
reviewFile: 305-review.code.findings-addressed-gate.md
reviewType: code
slice: findings-addressed-gate
project: squadron
reviewVerdict: FAIL          # as the review stated it — never edited
resolution: ADDRESSED        # ADDRESSED | UNADDRESSED | UNKNOWN, derived
reviewedSha: <sha>           # what the review assessed (or fallback, noted)
resolvedSha: <sha>           # HEAD when resolution ran
shaSource: frontmatter       # frontmatter | file-history | --since
judgeModel: <model or null>
dateCreated: YYYYMMDD
findingStatuses:
  - id: F001
    status: addressed        # 305 FindingStatus values
    screen: judge            # which layer settled it
    note: ...
---
```

Serialized via the shared `yaml.safe_dump` helper extracted from
`evidence.py` (305 F005 applies identically here: notes embed arbitrary
model text).

## Implementation Details

**Part A — `reviewedSha` stamp.** `format_review_markdown` gains an optional
`reviewed_sha` parameter emitted into frontmatter when present; both callers
(`review/persistence.save_review_result`, `pipeline/actions/review.py`)
resolve HEAD via `run_git(["rev-parse", "HEAD"])` and pass it. Git
unavailable → key omitted, WARNING (never a placeholder value). Effort 1/5.

**Part B — `review/resolution.py` + `sq review resolve`.** New
`records_from_frontmatter()` in `findings_addressed/models.py` (severity
normalized via the existing `_as_severity`; malformed entries kept as
residue, 305 rule). Judge-core extraction per Decision 4. Diff computation
reuses `run_git` with base..HEAD `--name-only` plus `status --porcelain`
(the working tree counts — an uncommitted fix is still a fix). CLI shape:
`sq review resolve INDEX [TYPE]` — the type is a positional word like the
rest of the review family (`sq review code 305`), not a `--type` flag.
Omitted, it is inferred from `{index}-review.*.md`: exactly one match →
that type; several → error listing the matches (never guess). Flags:
`--model`, `--profile`, `--no-judge`, `--since`, `--cwd`, `-v`. Exit code 0
on ADDRESSED, 1 on UNADDRESSED/UNKNOWN, so the command composes in shell.
Effort 3/5.

**Part C — contract + docs.** Schema above lands in `docs/COMMANDS.md`
(`review resolve` section) and the PM procedure in the same section.
Coordination item filed against context-forge referencing the schema.
Effort 1/5.

**Part D — overwrite guard, fail-closed.** In `save_review_file`: target
exists → copy to `archive/`, **verify the copy** (read back, compare
size/content), then overwrite. If the archive copy cannot be made or
verified — permissions, missing directory, disk full — the overwrite is
**aborted**: the review content is still printed to the terminal, the save
returns None with an ERROR naming both paths, and the original file is
untouched. A guard that fails open would destroy exactly the content it
exists to protect. Two tests: (1) re-save over an edited review preserves
the edited content in `archive/` byte-for-byte; (2) an unwritable
`archive/` (a file where the directory should be, the existing test idiom)
aborts the overwrite and leaves the original intact. Effort 1/5.

## Cross-Slice Dependencies

- **Consumes 305:** screens vocabulary, `FindingStatus`, `verify_outcomes`,
  judge template `judge.findings-addressed`, evidence rendering helpers.
  The gate policy itself is untouched; its tests must pass unchanged.
- **Coordinates with cf (external):** resolution-artifact schema is offered
  as the seam; no squadron behavior depends on cf adopting it.
- **Issue #51** closes on merge. The slice-plan entry's verified-facts block
  (what 305 writes, cf's config surface, the overwrite hazard) is this
  design's factual base.

## Success Criteria

- [ ] A review authored after this slice carries `reviewedSha:` in
      frontmatter, from both the CLI and the pipeline persistence paths.
- [ ] `sq review resolve 305` against a review whose findings were fixed
      produces a `305-resolution.code.*-r1.md` with per-finding statuses and
      `resolution:` derived — and the review file is byte-identical before
      and after.
- [ ] An empty diff since `reviewedSha` yields `resolution: UNADDRESSED`
      with every CONCERN+ finding `unaddressed`, zero judge calls.
- [ ] `--no-judge` with a non-empty diff yields `resolution: UNKNOWN`
      (residue disputed), never ADDRESSED.
- [ ] A judge claim of `addressed` over a path the diff never touched is
      downgraded to `disputed` (existing `verify_outcomes`, exercised via
      the new path).
- [ ] Legacy review without `reviewedSha` resolves via file-history fallback
      with a WARNING naming the fallback; `--since` overrides both.
- [ ] Re-running `sq review code <N>` over an edited review file archives
      the prior content and warns; nothing is silently destroyed.
- [ ] A review whose frontmatter verdict is FAIL/CONCERNS but whose parsed
      findings contain zero CONCERN+ entries resolves to UNKNOWN with a
      WARNING naming the mismatch — never ADDRESSED (F001; #28 lineage).
- [ ] Judge transport failure and an unreadable judge response on the
      resolve path yield UNKNOWN with a WARNING; a diff exceeding the
      injection cap yields UNKNOWN naming the cap and the base used (F004).
- [ ] A failed or unverifiable archive copy aborts the overwrite: the
      original review file is byte-identical afterward and the save errors
      loudly (F003).
- [ ] Metrology `discover_judge_results` and review discovery return no
      resolution artifacts (test against the real glob).
- [ ] 305's full test suite passes unchanged — including after the
      `review/addressed/` relocation (F002).
- [ ] Second `resolve` run writes `-r2`, not over `-r1`.

**Phase 5 note (review F005):** the cf `archive/`-scanning verification in
Decision 7 must appear as its own checklist task in the breakdown, sequenced
before Part D lands — it is a go/no-go on the archive filename scheme.

## Verification Walkthrough (draft — refine at Phase 6)

```bash
# 1. Author a review with the new stamp
sq review code 305 -v
grep reviewedSha project-documents/user/reviews/305-review.code.*.md

# 2. Fix the findings, commit
#    ... edits ...
git commit -am "fix: address review findings"

# 3. Derive resolution (type inferred — only one 305 review exists;
#    `sq review resolve 305 code` to be explicit)
sq review resolve 305 -v
# → per-finding table, resolution: ADDRESSED, artifact path printed
cat project-documents/user/reviews/305-resolution.code.*-r1.md

# 4. Prove the review file was not touched
git status --porcelain project-documents/user/reviews/305-review.code.*.md
# → empty

# 5. Negative case: resolve with nothing changed
sq review resolve 305        # immediately again, no new commits
# → r2 artifact; findings judged against the same diff (statuses persist)

# 6. Screens-only path
sq review resolve 305 --no-judge
# → resolution: UNKNOWN, exit code 1

# 7. Overwrite guard
echo "## Hand note" >> project-documents/user/reviews/305-review.code.*.md
sq review code 305
# → WARNING + archive/ copy containing the hand note

# 8. PM procedure (manual, unchanged in mechanism)
#    verdict edit in review frontmatter, commit message citing the r1 artifact
```

## Relative Effort

3/5 overall (A:1, B:3, C:1, D:1 — B dominates).
