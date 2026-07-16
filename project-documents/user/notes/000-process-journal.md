---
docType: notes
layer: project
project: squadron
audience: [human, ai]
description: Append-only log of process decisions and design reasoning that has no home in other document types
dateCreated: 20260716
dateUpdated: 20260716
status: in_progress
---

# Overview

Each entry is an h2 heading `## YYYYMMDD — Title`, newest first, followed by
**Context** (what prompted it), **Decision** (what was settled), **Rationale**
(why), and optionally **Follow-ups** (issues/slices/docs affected). Entries are
written in timeless decision language — no session transcripts, no line numbers
that drift. When the file exceeds the standard size limit, split per
file-naming-conventions (`-1`, `-2`, …).

# Entries

## 20260716 — Three result-reduction mechanisms are converging but nothing links them: gate (304), fan-in (182/189), multi-sample judging (300 FW1)

**Context:** Slice 304 (gate composition) was designed to reduce a *judge* verdict and a *standard review* verdict into one checkpoint gate via an upstream most-severe-wins reduction. During PM review it was observed that squadron already has — or plans — two other mechanisms that also "reduce a set of results to one verdict," and that they look similar enough to be confused yet reduce along genuinely different axes. Critically, **no single document connects the three.** Each lives in its own slice/initiative, and a reader landing on any one of them two months from now would have no pointer to the other two — the overlap would be re-derived (or, worse, one would be reimplemented as if the others didn't exist). This entry is the connective tissue that has no home in any one slice.

The three mechanisms:

1. **Gate composition (304, this initiative — 300).** Reduces **2 heterogeneous** judgments of *one* artifact: a judge's score-derived verdict *and* an independent review's model-produced verdict. Answers "do a judge **and** a review agree this gate should open?" Mechanism: a purpose-built `gate` action, most-severe-wins over two named steps. Ships as its own small action.
2. **Fan-out / fan-in convergence (182 shipped; 189 planned).** Reduces **N homogeneous** branch results from a `fan_out`: the *same* review/judge run across several models or prompts. Answers "does the **consensus/median/unanimity** of N samples clear the gate?" Mechanism: the `FanInReducer` protocol + `_REDUCER_REGISTRY` (`src/squadron/pipeline/intelligence/fan_in/reducers.py`) — `collect` and `first_pass` today, `merge_findings` and `unanimous` planned in 189.
3. **Multi-sample judging (300 Future Work item 1).** Run *one* judge N times and reduce by median to bound run-to-run score variance. This is **not** a gate concern and **not** its own new mechanism — it is a *fan-in* job: it belongs to the `fan_out`/`FanInReducer` machinery (#2), reducing N judge samples by a median reducer. It is filed under 300 only because 300 is where the *need* was identified, not because 300 owns the *mechanism*.

**Decision:** Keep all three **separate and unblended for now** — no unification is scheduled — but record the relationship explicitly so the convergence is a known, deliberate future direction rather than a rediscovery. Specifically:

- The gate (304) does **not** grow a sample count and is **not** routed through the fan-out branch model. It reduces exactly two heterogeneous named sources.
- Multi-sample judging (300 FW1), when built, is implemented as a **fan-in reducer** (a median `FanInReducer` over a `fan_out` of N judge runs), **not** as new judge-specific looping and **not** as a gate feature.
- The likely eventual unification — the gate's most-severe rule expressed as a two-input `FanInReducer`, so "judge-plus-review" becomes a fan-out of two heterogeneous branches reduced by a most-severe reducer — is flagged as **unscheduled direction**, to be undertaken only when a caller needs it, and only knowingly (treating the gate reduction as one reducer among several).

**Rationale:** All three are instances of "reduce a set of `ActionResult`s to one verdict," which is exactly why they will keep drifting toward each other and exactly why they are easy to confuse or accidentally duplicate. But they reduce along different axes (heterogeneous-kind vs. homogeneous-sample vs. repeated-sample-of-one), have different callers, and have different config surfaces. Forcing them into one abstraction now would add real complexity — heterogeneous fan-out branches, per-branch template config on the gate path — to buy an abstraction nothing currently needs, violating the project's "resist complexity until truly necessary" rule. The correct move is to let each ship in its purpose-built form *and leave a durable pointer* so the next person to touch any of them sees the whole triangle. The failure mode this entry prevents is not a code bug; it is institutional forgetting — the design overlap was noticed once, and without a home outside the individual slices it would be lost. (The gate's own slice-design doc carries the 304↔182/189 comparison table; this journal entry is the wider three-way link, including 300 FW1, that no single slice is the right home for.)

**Follow-ups:** Slice 304 design (`project-documents/user/slices/304-slice.gate-composition.md`) — "Relationship to fan-out/fan-in convergence" subsection and the fan-in comparison table. Slice 182 (`182-slice.fan-out-fan-in-step-type.md`) and slice 189 (the `merge_findings`/`unanimous` reducers) — the fan-in mechanism. Slice plan `300-slices.eval-actions-llm-as-judge-scoring.md` Future Work item 1 (multi-sample judging). No new issue filed — this is a design-relationship record, not a defect; when a unification slice is eventually scoped, it should cite this entry as the origin of the decision to defer.

## 20260716 — A fix for one silent-fallback bug shipped with a second, undetected one already inside it

**Context:** Issue #14 (fixed and closed earlier this same day, commit `17f3ab1`). The diff-range resolver's unsafe last-resort fallback (unscoped commit-message grep, matching bare slice-number tokens in unrelated commits) was removed and replaced with a loud `DiffRangeUnresolvedError` when neither of the two remaining structural paths — local branch, or merge commit on main — resolves. This was verified at the time with 2133 passing tests and a live check against an intentionally-unresolvable slice number. Later the same day, running `sq review code` against slice 303 — work from the *immediately preceding* session — hit that same "no local branch and no merge commit found" error, even though the branch exists locally and a real merge commit is on `main`.

**Decision:** No process change to the fix itself is needed once the actual defect was found: `_find_merge_commit`'s `--grep` pattern searched for the branch-naming word order (`{slice}-slice`), but this project's real merge commit messages use the reversed prose order ("Merge slice {slice}: ..."), so path 2 could never match a real merge commit and silently failed shut. Fixed the pattern to match both orders with explicit non-digit boundary anchors (POSIX ERE has no `\b`), and — critically — added a test that runs the real `grep -E` pattern against literal commit-message strings rather than mocking `subprocess.run` and asserting only on stdout-parsing.

**Rationale:** The existing `TestFindMergeCommit` tests were shaped exactly like the anti-pattern this project's own parsing-rules guidance warns about: they supplied `mock_result.stdout` by hand and asserted the *parsing* of that string was correct, which can never catch a grep *pattern* that never matches real input — the test fixture never contained the actual format the code would consume in production. The deeper process failure: the #14 fix was reviewed and verified the same day it shipped, with a full green test run and a live manual check, and still missed that the fallback path it was leaving in place (path 2, merge-commit detection) was already broken and had likely been dead code for a while. "All tests pass" was treated as sufficient verification for a fix whose entire premise was removing a fallback and trusting the remaining paths — but neither remaining path had ever been exercised against a real, once-merged, currently-existing branch in this repo. The fix needed for #14 was correct in isolation; the verification was not comprehensive enough to notice a neighboring path was silently non-functional. Going forward, when a fix's safety argument rests on "path X remains as a working fallback," that path must be positively demonstrated against real repository state, not just left standing because it existed before.

**Follow-ups:** No issue number filed (a same-day continuation of #14, not a new bug in an unrelated feature); fix applied directly in `src/squadron/review/git_utils.py` (`_find_merge_commit` grep pattern) with new tests in `tests/review/test_git_utils.py::TestFindMergeCommit::test_grep_pattern_against_real_git`. Verified live against slices 301, 906, 909 (now resolve) and 300 (still correctly unresolved — genuinely has no merge-commit-into-main, only main-into-branch merges, since it was squash-merged with no true two-parent commit).

