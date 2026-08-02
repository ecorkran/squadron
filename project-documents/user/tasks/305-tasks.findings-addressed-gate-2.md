---
docType: tasks
slice: findings-addressed-gate
project: squadron
lld: user/slices/305-slice.findings-addressed-gate.md
dependencies: [911, 910, 304]
projectState: >
  Continuation of 305-tasks.findings-addressed-gate-1.md (Parts D–G). Parts A–C
  in file 1 must be complete before Part D begins: A supplies the loop-body
  evidence the policy reads, B unblocks the target loop shape at validation, and
  C establishes the policy enum and per-policy reference-field mapping that
  every task here references.
dateCreated: 20260802
dateUpdated: 20260802
status: in_progress
---

## Context Summary

- This is **file 2 of 2** for slice 305. Read
  `305-tasks.findings-addressed-gate-1.md` first — its Context Summary carries
  the design deltas discovered during breakdown, the facts established by
  inspection, and the out-of-scope list. All of it applies here and is not
  repeated.
- File 1 covers Part A (loop-body evidence plumbing), Part B (policy config
  surface), and Part C (loop validation), tasks T1–T11.
- This file covers Part D (deterministic screens), Part E (judge over the
  residue), Part F (gate evidence artifact), and Part G (integration,
  documentation, close-out), tasks T12–T31. Task numbering continues unbroken
  across both files.

---

## Part D — Deterministic Screens

New module `src/squadron/pipeline/actions/findings_addressed.py`. Watch the
~300-line file guideline: if the module approaches it, split the judge leg
(Part E) into a sibling module rather than letting it sprawl.

- [x] **T12. Module skeleton: status enum, evidence types, finding access** (effort 2)
  - [x] Define `FindingStatus(StrEnum)` with exactly `ADDRESSED`, `UNADDRESSED`,
    `MOVED`, `DISPUTED`. This enum and its parse tokens are defined **once**
    here and referenced everywhere else.
  - [x] Define `SettlingScreen(StrEnum)` naming which layer settled a finding
    (`no_prior_round`, `byte_identical`, `exact_match`, `judge`) — this is the
    audit field the design requires on metadata, and it must not be a free
    string.
  - [x] Define a small frozen dataclass for a per-finding outcome: finding id,
    status, settling screen, optional successor id, optional note.
  - [x] Add a helper that reads the CONCERN+ subset out of an `ActionResult`'s
    `findings` list. Findings arrive as plain dicts (see Context Summary); read
    defensively — a missing key is a malformed finding, log at WARNING with the
    finding's id if present, and treat it as unsettleable residue rather than
    dropping it silently.
  - [x] Success: `pyright` strict passes; module imports cleanly with no
    circular-import error from `actions/gate.py`.

- [x] **T13. Screen 0 — no prior round** (effort 1)
  - [x] When `context.prior_iteration_step_outputs` has no entry for the
    `review_from` step name, the addressed leg is `PASS` with
    `metadata.no_prior_round: True` and an INFO log naming pipeline, step, and
    iteration.
  - [x] Never `UNKNOWN` here (design decision 6): a first round is a known state
    with a known right action.
  - [x] Success: round 1 of the target shape spends zero tokens and the gate's
    verdict equals the fresh review's verdict.

- [x] **T14. Extract a shared `run_git` helper** (refactor only, no new behavior) (effort 1)
  - [x] Add a public `run_git(args: list[str], *, cwd: str)` helper to
    `src/squadron/review/git_utils.py` returning the `CompletedProcess` or
    `None` on `OSError`, matching the existing private runners
    (`git_utils.py:206-220`, `pipeline/actions/commit.py:123-135`).
  - [x] Rewire `commit.py`'s `_git` to delegate to it — a pure delegation, no
    behavior change. Do not touch `git_utils._resolve_rev`.
  - [x] Success: existing commit tests pass **unmodified**; `pyright` strict
    clean. Nothing in this task depends on the new policy module, so it is
    independently revertable.
  - [x] **Commit before continuing.** `ruff format`, then commit from the project
    root — `refactor: extract shared run_git helper into git_utils`. The next
    task builds new logic on this helper; separating the commits keeps a
    regression attributable to one or the other.

- [x] **T15. Round diff and Screen 1 — byte-identical round** (effort 3)
  - [x] Compute the round diff at gate time, via T14's `run_git`, as the
    **working tree against
    `HEAD`** (`git diff HEAD -- <paths>`), scoped to the loop's artifact paths
    when the gate config supplies them, plus `git status --porcelain` to catch
    untracked new files. Per delta 3 above, `HEAD` *is* the prior round's commit
    at this point and round N is uncommitted — do not look for a round-N SHA.
  - [x] Screen 1: an empty diff **and** empty porcelain output means the round
    produced nothing. Every prior CONCERN+ finding is `UNADDRESSED` with settling
    screen `byte_identical`, the addressed leg is `FAIL`, and no judge is
    invoked. Log at WARNING — this is #42's symptom made load-bearing.
  - [x] Git subprocess failure (non-zero exit, `None` return, unresolvable ref):
    addressed leg `UNKNOWN` with a WARNING naming the exact failed command. This
    is the **only** git condition that earns `UNKNOWN` (design decision 8).
  - [x] Record the prior round's commit SHA for the audit trail by resolving
    `git rev-parse HEAD` at gate time — that ref *is* the prior round's commit.
    Do **not** read it out of `prior_iteration_step_outputs`: that field carries
    only verdict-bearing results (T1 populates it via `_last_with_verdict`) and
    `CommitAction` returns no verdict, so the commit result is never in it. No
    screen may depend on the SHA either way.
  - [x] Round N's own SHA is **not recordable** and must not be attempted. The
    evidence artifact is written before the commit that contains it, so it
    cannot carry that commit's identity — the design's "round SHAs" success
    criterion is satisfiable only for the prior round. Record
    `revision_number` alongside the prior SHA; round N's commit is discoverable
    from git as the commit containing this artifact. State this in a comment so
    a later reader does not try to "complete" the pair.
  - [x] Success: an unchanged working tree yields `FAIL` with zero transport
    calls; a git failure yields `UNKNOWN` with the command in the log.

- [x] **T16. Screen 2 — conservative exact matching** (effort 2)
  - [x] A prior CONCERN+ finding whose (`location`, `category`) pair appears in
    the fresh findings set is `UNADDRESSED` with settling screen `exact_match` —
    the reviewer re-found it, no judgment needed.
  - [x] Findings whose `location` is `unverified` (904's normalization token for
    every unknown location) are **excluded from match keys** and routed to the
    judge instead. Add a comment giving the reason: two unrelated findings
    sharing a category would collide on that token and trap the loop until
    exhaustion.
  - [x] Matching is exact only. No fuzzy/line-shift tolerance — 911's clean
    regeneration contract moves line numbers wholesale and a false `addressed`
    fails open (design decision 4).
  - [x] Anything not settled by Screens 0–2 is residue and falls through to the
    judge, never to `ADDRESSED`.
  - [x] Success: a recurring exact-match finding settles without a transport
    call; an `unverified`-located prior finding never settles here.

- [x] **T17. Tests for the deterministic screens** (effort 3)
  - [x] New `tests/pipeline/test_findings_addressed.py` with a transport spy
    fixture that fails the test if the judge transport is called.
  - [x] Screen 0: empty `prior_iteration_step_outputs` → leg `PASS`,
    `no_prior_round` metadata present, INFO log captured, spy uncalled.
  - [x] Screen 1: fake git reporting an empty diff and empty porcelain → leg
    `FAIL`, every prior CONCERN+ finding `UNADDRESSED` with screen
    `byte_identical`, spy uncalled, WARNING captured.
  - [x] Git failure: fake git returning non-zero → leg `UNKNOWN`, WARNING names
    the failed command.
  - [x] Screen 2: prior finding at `src/x.py:12` / `correctness` recurring in the
    fresh set → `UNADDRESSED` via `exact_match`, spy uncalled.
  - [x] Screen 2 exclusion: two prior/fresh findings both located `unverified`
    with the same category → neither settles here; both reach the residue set.
  - [x] Prior findings of severity `NOTE`/`PASS` are not part of the CONCERN+
    set and never appear in the residue.
  - [x] Success: all pass; `pytest tests/pipeline/` green.
  - [x] **Commit Part D.** `ruff format`, then commit from the project root —
    `feat: add findings-addressed deterministic screens`. The screens are
    useful and testable without the judge leg; this is a real revert point.

---

## Part E — Judge Over the Residue

- [ ] **T18. Bundled template `judge-findings-addressed.yaml`** (effort 3)
  - [ ] Create `src/squadron/data/templates/judge-findings-addressed.yaml`, named
    `judge.findings-addressed`. Model its structure on
    `judge-slice-vs-arch.yaml` (system prompt, `inputs`, `prompt_template`,
    `allowed_tools`, `permission_mode`, `model`).
  - [ ] **No `judge:` block.** `ReviewTemplate.is_judge` derives from that block
    (`review/templates/__init__.py:48`), and this template emits statuses, not a
    score — leaving it out is what keeps a stray persisted file out of
    metrology's judge sample set. Add a comment in the YAML stating this.
  - [ ] Required output shape: exactly one line per prior finding,
    `<finding-id>: <status>` with an optional ` successor=<fresh-finding-id>`
    suffix, statuses drawn from the closed set defined in T12. Instruct the model
    explicitly that it must **not** emit a `## Summary` section, a verdict line,
    or an overall conclusion — the outcome is derived, and anything it asserts is
    discarded (same wording discipline as `judge-slice-vs-arch.yaml:22-28`).
  - [ ] Instruct that `moved` **must** name a successor, and that `disputed` is
    the correct answer whenever it cannot defend a status — guessing between
    addressed and unaddressed is the failure mode this token exists to prevent
    (design decision 7).
  - [ ] The prompt receives the residue findings, the round diff, and the fresh
    findings list. Do not include an example status line with a plausible
    finding id next to the fill-in slot — per project rules, a nearby example is
    a hallucination trap when the real value is absent.
  - [ ] Success: `load_all_templates()` registers it; `get_template(
    "judge.findings-addressed").is_judge` is `False`.

- [ ] **T19. Status-line parser** (effort 2)
  - [ ] Parse the judge's `raw_output` into per-finding statuses over the closed
    status set from T12. Parse leniently: tolerate surrounding prose, blank
    lines, varying whitespace, and case-insensitive status tokens; anchor on the
    `<id>: <status>` shape rather than requiring an exact layout.
  - [ ] A finding with no parsable line, or a line naming a status outside the
    closed set, is `DISPUTED` — not dropped, not defaulted to addressed.
  - [ ] An entirely unparseable response (no recognizable lines at all) is
    reported as a parse failure so T22 can map it to `UNKNOWN`.
  - [ ] Success: the parser's tests use the real output shape the template
    instructs, including one messy real-world-style sample with leading prose.

- [ ] **T20. Judge invocation — transport only** (effort 3)
  - [ ] Call `run_review_with_profile` (`review/review_client.py:54`) directly
    with the loaded template. **Do not** route through `ReviewAction` and **do
    not** persist a review file — the design's F003 resolution: metrology's
    `discover_judge_results` would otherwise sweep this evidence into the 320
    calibration sample set.
  - [ ] Model resolution: the `judge:` block's `model:` when supplied, otherwise
    `context.resolver`'s standard cascade. The judge defaults to the pipeline's
    review-tier model, never the dispatch model (design decision 3).
  - [ ] Invoke only when the residue is non-empty. Round 1 and byte-identical
    rounds never reach here.
  - [ ] Transport failure (exception, or a result with no usable output) is
    caught narrowly, logged with `logger.exception`, and surfaced as a judge
    failure for T22 to map to `UNKNOWN` — fail-closed, never fail-open.
  - [ ] Success: a residue of N findings produces exactly one transport call; an
    empty residue produces zero.

- [ ] **T21. Successor verification and contradiction check** (effort 2)
  - [ ] `MOVED` must name a successor that exists in the fresh findings set. A
    missing or unresolvable successor downgrades to `DISPUTED` with a WARNING
    naming the finding and the claimed successor — an unverifiable relocation
    claim is uncertainty, not a pass.
  - [ ] `ADDRESSED` for a finding whose cited region the round diff shows
    untouched downgrades to `DISPUTED` with a WARNING. Match the finding's
    `location` path against the diff's changed paths; a finding located
    `unverified` cannot be contradicted this way and is left as the judge
    reported it.
  - [ ] Both downgrades record the original judge status on the evidence record
    so the audit trail shows what was claimed and what was accepted.
  - [ ] Success: both downgrades observable in logs and in gate metadata.

- [ ] **T22. Derivation rule** (effort 2)
  - [ ] Compute the addressed-leg verdict from the per-finding statuses, closed
    over the enum: all `ADDRESSED` or successor-verified `MOVED` → `PASS`; any
    `DISPUTED`, judge unavailable, or unparseable output → `UNKNOWN`; any
    `UNADDRESSED` → `FAIL`. Evaluate `UNKNOWN` before `FAIL` so a fail-closed
    condition dominates.
  - [ ] Discard any overall verdict the judge stated — it is derived, never
    declared (`enforce_judge` precedent, design principle 4).
  - [ ] Final gate verdict is `reduce_verdicts(addressed_leg,
    fresh_review_verdict)` — the existing function, unchanged.
  - [ ] Success: the derivation is a pure function over statuses with no I/O, so
    it is testable without a transport.

- [ ] **T23. Tests for the judge leg** (effort 3)
  - [ ] Parser: well-formed lines; lines with `successor=`; case variants;
    leading prose; an unknown status token → `DISPUTED`; a missing line →
    `DISPUTED`; a wholly unparseable response → parse failure.
  - [ ] Invocation: residue of 2 → exactly one transport call, and the prompt
    carries both residue findings and the round diff; empty residue → zero calls.
  - [ ] Transport raising → leg `UNKNOWN`, `logger.exception` recorded.
  - [ ] `MOVED` with a successor present in the fresh set stays `MOVED`; with an
    absent successor → `DISPUTED` + WARNING.
  - [ ] `ADDRESSED` over a path absent from the diff → `DISPUTED` + WARNING;
    `ADDRESSED` over a path present in the diff is accepted.
  - [ ] Derivation table, parametrized over every status combination that
    changes the outcome, including `UNKNOWN` dominating `FAIL`.
  - [ ] Success: all pass; no test reaches a real provider.
  - [ ] **Commit Part E.** `ruff format`, then commit from the project root —
    `feat: add judge residue leg and derivation rule to findings-addressed`.

---

## Part F — Gate Evidence Artifact

- [ ] **T24. Write the gate-evidence artifact** (effort 3)
  - [ ] Persist one artifact per gate decision under the reviews directory
    (`project-documents/user/reviews`, the constant already defined at
    `review/persistence.py:17`). Filename pattern
    `{index}-gate.{policy}.{name}-r{revision}.md` — it must **never** match the
    `*-review.*` glob, so every existing and future review-file consumer excludes
    it by construction rather than by filtering. Define the pattern once as a
    module constant.
  - [ ] Frontmatter carries `docType: gate-evidence` plus: per-finding statuses
    with the settling screen for each, both leg verdicts, the reduced verdict,
    the prior round SHA when known, `revision_number`, and the judge model and
    template when one was consulted.
  - [ ] Write it **before** the iteration's commit so it enters the round's
    commit alongside the artifact and the fresh review. The gate already runs
    ahead of `commit_each_iteration` (`executor.py:1417-1440`), so this needs no
    ordering change — state that in a comment.
  - [ ] Persistence failure is non-fatal and logged at WARNING, mirroring the
    review action's treatment (`actions/review.py:281-285`). The gate's verdict
    does not depend on the file being written.
  - [ ] Success: the artifact is written on every decision, including Screens 0
    and 1 where no judge ran.

- [ ] **T25. Gate metadata parity** (effort 1)
  - [ ] The returned `ActionResult.metadata` carries the same record in-process:
    per-finding statuses, settling screens, both leg verdicts, the prior round
    SHA, and `revision_number` — the same pair T15 establishes, not a round-N
    SHA. Keep `policy` on metadata as `most-severe` already does
    (`actions/gate.py:143-151`).
  - [ ] Success: metadata and the persisted artifact are built from one source
    object — no second assembly of the same facts.

- [ ] **T26. Tests for the evidence artifact** (effort 2)
  - [ ] The written filename does not match `*-review.*` (assert with the same
    glob `discover_judge_results` uses).
  - [ ] `discover_judge_results` run over a reviews directory containing a
    gate-evidence artifact returns it in no sample set
    (`tests/metrology/`, alongside the existing discovery tests).
  - [ ] Frontmatter round-trips: `docType: gate-evidence`, statuses, settling
    screens, leg verdicts, revision number.
  - [ ] An unwritable reviews directory produces a WARNING and does not change
    the gate's verdict.
  - [ ] Success: all pass.
  - [ ] **Commit Part F.** `ruff format`, then commit from the project root —
    `feat: persist gate-evidence artifact for findings-addressed decisions`.

---

## Part G — Integration, Documentation, Close-Out

- [ ] **T27. Example pipeline** (effort 2)
  - [ ] Add one pipeline under `src/squadron/data/pipelines/` demonstrating the
    target loop shape from the design (`dispatch` → named `review` →
    `findings-addressed` gate with `checkpoint: on-concerns`,
    `commit_each_iteration: true`, `until: review.pass`).
  - [ ] Give each model role its own `params` entry, per the convention stated at
    `docs/PIPELINES.md:308`.
  - [ ] Success: the pipeline loads and validates clean; `--dry-run` shows the
    expanded action sequence with the gate last.

- [ ] **T28. Resume behavior — pin it, do not design for it** (effort 1)
  - [ ] Design decision 5's caveat was **resolved during breakdown**, not left
    open. Two facts, both verified: findings survive state persistence
    (`dataclasses.asdict` at `pipeline/state.py:291` keeps the `findings` field
    and `load_prior_outputs` reconstructs it, `:417-434`), and **squadron has no
    mid-loop resume** — a loop step that pauses is appended to
    `completed_steps` (`state.py:304-309`), so `first_unfinished_step`
    (`state.py:439-446`) skips past it and the loop is never re-entered.
  - [ ] Therefore: build **no** resume special case into the policy. There is no
    execution path where the gate runs against a resumed round with the prior
    round missing. Do not add a Screen 0 fallback for it.
  - [ ] Add one test pinning the second fact — a paused loop step is recorded
    completed and resume continues past it — so a future change to resume
    granularity fails here loudly instead of silently reintroducing the case.
  - [ ] Whether a checkpoint-paused loop *should* be re-enterable on resume is a
    real question and **not this slice's**. Do not change resume granularity
    here; if it is worth pursuing, it is a pipeline-foundation item.
  - [ ] Success: the test pins current behavior; the policy contains no
    resume-specific branch.

- [ ] **T29. End-to-end and regression pass** (effort 3)
  - [ ] Integration test over the example pipeline with a stubbed transport:
    round 1 → Screen 0 `PASS`-annotated; round 2 with an unaddressed recurring
    finding → gate `FAIL` and the loop continues; round 3 with everything
    addressed → gate `PASS` and the loop exits.
  - [ ] Fail-closed path end-to-end: judge transport failure → addressed leg
    `UNKNOWN` → gate `UNKNOWN` → the `on-concerns` checkpoint fires. Note that
    the checkpoint firing inside the loop body will pause the run and, per
    issue #48, mark the loop step complete — assert the pause, not that the
    loop resumes.
  - [ ] Regression: `compose-gate-example.yaml` and every existing `most-severe`
    gate test produce byte-identical results; no existing pipeline YAML needs a
    config change.
  - [ ] Run `ruff format`, `ruff check`, `pyright` strict, and the full test
    suite. Zero errors is the merge bar.
  - [ ] Success: all green; the design's Success Criteria list is walked
    item-by-item and each one is checked against a real test or run. The "round
    SHAs" criterion reads as prior-SHA + `revision_number` — the design text was
    reconciled to match during breakdown, so this is a literal check, not a
    judgment call.
  - [ ] **Commit Part G's integration work.** `ruff format`, then commit from
    the project root — `test: add findings-addressed end-to-end coverage`.

- [ ] **T30. Documentation** (effort 2)
  - [ ] `docs/PIPELINES.md`: update the `gate` step table (`:245-265`) — `policy`
    is no longer "only `most-severe` exists today"; document
    `findings-addressed`, its per-policy field rules, and the optional `judge:`
    block.
  - [ ] Add a short section covering the target loop shape, the layered decision
    procedure, and the `UNKNOWN`-means-stop contract. Cross-link it from the
    judge-gated-cycle section (`:367`) and correct the standing claim at `:403`
    that a judge-gated cycle's body is `[dispatch, review]` only.
  - [ ] Note the gate-evidence artifact: where it lands, what it carries, and
    that it is deliberately outside the `*-review.*` namespace.
  - [ ] Success: a reader who has never seen this slice can author the target
    shape from the docs alone.

- [ ] **T31. Close-out** (effort 1)
  - [ ] CHANGELOG: one short user-facing bullet — a loop can now require that
    the prior round's findings were actually addressed, not just that a fresh
    review passed.
  - [ ] DEVLOG entry per `prompt.ai-project.system.md`, Session State Summary,
    including the Part A design deltas and T28's resume finding.
  - [ ] Mark slice 305 complete in the slice design frontmatter and in
    `300-slices.eval-actions-llm-as-judge-scoring.md` entry 6.
  - [ ] Check off `900-slices` entry 10's pointer if it still reads as open.
  - [ ] `ruff format` immediately before the commit; commit from the project
    root; merge the slice branch into the target per the project git rules.
  - [ ] Success: `cf list slices` shows 305 complete.
