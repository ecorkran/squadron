---
docType: slice-design
slice: findings-addressed-gate
project: squadron
parent: project-documents/user/architecture/300-slices.eval-actions-llm-as-judge-scoring.md
dependencies: [911, 910, 304]
interfaces: []
dateCreated: 20260802
dateUpdated: 20260802
status: draft
---

# Slice Design: Findings-Addressed Gate Policy

## Overview

Slice 911 made a loop iteration *legible* — per-round commits, a
`revision_number:` on the artifact, a stated round contract. This slice makes
the round-over-round question *answerable inside the pipeline*: were the prior
round's findings actually addressed?

**Initiative home (20260802).** Originally scoped as slice 912 under the
maintenance initiative (900), whose slice plan entry 10 required a design
conversation before Phase 4. The design review (F001) flagged that 900's
scope explicitly excludes new capabilities, and this slice is one: the first
use of the `VALID_GATE_POLICIES` seam that slice 304 declared. Renumbered to
**305 under initiative 300** (eval-actions / LLM-as-judge) — the initiative
that declared the seam and whose Future Work already tracked the adjacent
gaps. 900's entry 10 remains as a pointer preserving the design-conversation
record. This is a compromise, not a full cleanup: fixed cleanly, other
judge-adjacent maintenance work might also move, but those slices have code,
commits, and closed issues — renumbering is only cheap before implementation
starts, which is true of this slice alone.

The design conversation (20260801–20260802) reframed the problem. The plan
entry's candidate resolution — a second, history-aware reviewer alongside the
clean-eyes review — survives in spirit but not in shape: the
findings-addressed check is not a reviewer. It is a **gate policy**.

### Design principles established in the conversation

These are stated here because they govern this slice and future pipeline
node work; they are the frame, not incidental rationale.

1. **Squadron is not a theory of quality — it is the toolkit for composing
   one.** Loop-until, fan-out, gates, judges are instruments. Choosing among
   them is pipeline design, and squadron's responsibility ends at making each
   node honest about what it is.
2. **Deterministic where measurable, model-backed where not, and the boundary
   explicit at each node.** A pipeline that pays a model for a measurable
   thing is a badly designed pipeline, not a squadron bug — but squadron must
   never *force* that design by failing to run the measurable layer first.
3. **Gate is where, judge is who.** `gate` is the control node — the place a
   decision happens. "Judge" is never a node type: it names the role a model
   plays when rendering scored judgment (the industry sense, LLM-as-a-judge).
   That role is employed from two positions: a judge template scoring a
   document (assessor position — `judge.slice-vs-arch`, unchanged by this
   slice), or a gate consulting a judge on the residue its deterministic
   screens cannot settle (this slice). No new user-facing vocabulary: the
   ontology a newcomer needs is *review = an opinion, gate = the decision*.
4. **Derived, not declared.** Carried over from `enforce_judge` (slice 301):
   a model consulted by a gate emits per-item statuses; the decision is
   computed from those by rule. The model never asserts the conclusion.
5. **Assessors are blind, deciders see.** The clean-eyes review is
   structurally denied prior opinions (anti-anchoring is a typing rule, not
   prompt engineering); the gate is structurally granted them. The
   deterministic layer is how the gate avoids being anchored itself.

## Value

Closes the evidence loop that 910 and 911 opened. 910 feeds findings into the
retry; 911 records each round; nothing yet *checks* the claim that round N+1
addressed round N. Today `until: review.pass` exits on a fresh verdict alone —
a reviewer that simply fails to re-notice a prior concern ends the loop, and
the failure shape of issue #32 (a confident verdict over work nothing
examined) recurs with a different mechanism.

After this slice a loop can require both: fresh eyes are satisfied, *and* the
prior round's CONCERN+ findings are accounted for — with the accounting
mechanical wherever it can be, and model judgment confined to what cannot be
measured.

## Technical Scope

**Included:**

- **`findings-addressed` gate policy.** Second entry in
  `VALID_GATE_POLICIES` (`actions/gate.py:14`), the first model-capable one.
  `most-severe` is unchanged and remains the degenerate case: a gate whose
  model layer is empty.
- **Policy-dependent gate config.** `most-severe` keeps its
  `judge_from`/`review_from` contract. `findings-addressed` requires
  `review_from` (the clean-eyes review), forbids `judge_from`, and accepts an
  optional `judge:` block (`model:` — the judge consulted for the residue).
  Validation in `steps/gate.py` and the loader's reference checks dispatch on
  policy.
- **Layered decision procedure** (deterministic screens → judge residue →
  derivation rule) implemented in a new module, keeping `gate.py` within the
  file-size guideline.
- **Loop validation refinement.** `_validate_verdict_count`
  (`steps/loop.py:208`) counts *unconsumed* verdict-bearing actions: a gate's
  named legs are consumed and do not count. A body of dispatch + review +
  gate is valid (one unconsumed verdict — the gate's). 910 Part B's
  motivating rejection (two reviews, no gate) still rejects with the same
  message and reasoning.
- **Round-1 semantics, explicit.** First iteration has no prior round; the
  policy renders a decision from the fresh leg alone and says so observably.

**Excluded (deliberately):**

- **Generic judge-over-results node.** A gate whose judge reads arbitrary
  step results is a future instrument; this slice builds the one policy with
  a concrete consumer.
- **Reviewer error rate / review scoring against later ground truth.**
  Acknowledged as eventually necessary (design conversation, 20260801); not
  now.
- **`on_exhaust: skip` fall-through** (910's deferred hole). Unchanged here.
- **Renaming existing judge templates.** `judge.*` template names stay;
  principle 3 makes them consistent, not stale.
- **Fan-out changes.** Fan-out/fan-in remains a peer instrument; nothing
  here privileges loop-until over it.

## Dependencies

| Slice | What it provides |
|---|---|
| 911 | Per-iteration commits (the diff evidence) and `revision_number:` (names the round). Commit SHAs ride in the commit action's outputs. |
| 910 | Accumulated per-iteration `prior_outputs` — the prior round's review `ActionResult` (verdict *and* `findings`) is available in-process; no git archaeology needed for findings. |
| 304 | Gate composition — `reduce_verdicts`, `step_outputs` resolution, checkpoint expansion. Reused unchanged. |
| 301 | Judge enforcement discipline — the derived-not-declared precedent this policy's derivation rule follows. **Precedent-only**, not a mechanical dependency, hence absent from frontmatter `dependencies:` (design review F006). |

## Architecture

### Target loop shape

```yaml
- loop:
    max: 3
    until: review.pass
    commit_each_iteration: true
    steps:
      - dispatch:                       # producer — writes the artifact
      - review:
          name: fresh-review            # assessor — blind to prior rounds
      - gate:
          review_from: fresh-review
          policy: findings-addressed
          judge:
            model: "{review-model}"
          checkpoint: on-concerns
```

Runtime already lands correctly on this shape: the gate step expands to
`gate` + optional `checkpoint` (`steps/gate.py:76-93`), checkpoint bears no
verdict, so `_last_with_verdict` (`executor.py:414`) finds the gate — the
loop is gated by the decision, by construction. Only the loop validator
rejects it today; that is the refinement above.

### Decision procedure (inside `GateAction.execute`, findings-addressed policy)

Evidence in hand before any model call:

- **Fresh findings** — `step_outputs[review_from].findings` (in-process).
- **Prior findings** — most recent prior-iteration review `ActionResult` in
  `context.prior_outputs` (910's accumulation).
- **Round diff** — `git diff <sha_{n-1}> <sha_n>` via the iteration commit
  SHAs in `prior_outputs` (911). Scoped to the loop's artifact paths.

**Screen 0 — no prior round.** First iteration (or no prior review result in
`prior_outputs`): the addressed-leg verdict is `PASS` with
`metadata.no_prior_round: true` and an INFO log. Decision reduces to the
fresh leg alone. Explicit, never silent — and never `UNKNOWN`, which would
fail a legitimate first round closed forever.

**Screen 1 — byte-identical round.** Nothing was addressed by definition:
every prior CONCERN+ finding is `unaddressed`; addressed-leg verdict `FAIL`;
zero judge tokens spent. Detected **without git**: 911's `CommitAction`
already reports `committed: False` on a clean tree, and that output is in
`prior_outputs` — a missing round-N SHA is not an unknown state, it *is* this
screen's signal (the symptom 910 fixed, here made load-bearing).

**Git-path failure disposition** (design review F002 — enumerated, not
implicit):

- `findings-addressed` on a loop without per-round commits (neither
  `commit_each_iteration` nor a committing body): **validation-time
  rejection** with an actionable message. The policy's evidence source is
  absent by configuration; that is knowable at load time and must never
  surface as a runtime verdict.
- Missing round-N commit at runtime: `committed: False` → Screen 1 `FAIL`,
  per above.
- Git subprocess failure (SHA unresolvable after history rewrite, repo in an
  unexpected state on resume): the diff evidence genuinely cannot be
  computed → addressed-leg `UNKNOWN` with a WARNING naming the failed
  command. This is the only git failure that earns `UNKNOWN`.

**Screen 2 — mechanical finding matching, conservative.** A prior finding
recurring in the fresh set at the same `location` + `category` is
`unaddressed` — the reviewer itself re-found it; no judgment needed.
Matching is deliberately narrow: with 911 Part C's clean-regeneration
contract, line numbers shift wholesale between rounds, so fuzzy matching
would manufacture false resolutions. Anything not exactly matched falls
through to the judge, not to `addressed`. **`unverified` locations are
excluded from match keys** (design review F005): 904 normalizes all
unknown locations to that one token, so two unrelated findings sharing a
category would exact-match on it, and a false `unaddressed` traps the loop
until exhaustion. `unverified`-located findings route to the judge instead —
conservatism preserved, trap removed.

**Judge — residue only.** For prior CONCERN+ findings not settled by the
screens, the judge receives: the finding, the round diff, and the fresh
findings list. It emits one status per finding from a closed set:

- `addressed` — the change substantively resolves it
- `unaddressed` — no responsive change
- `moved` — resolved at its location but the issue relocated; **must name
  its successor** (`successor=<fresh-finding-id>`). The gate verifies the
  named finding exists in the fresh set; `moved` with a missing or
  unverifiable successor downgrades to `disputed` with a WARNING (design
  review F004) — an unverifiable relocation claim is an uncertainty, not a
  pass.
- `disputed` — the judge cannot render a status it would defend

**Contradiction check.** A judge status of `addressed` for a finding whose
cited region the deterministic layer shows untouched is downgraded to
`disputed` with a WARNING. The gate flags the contradiction; it does not
accept the verdict.

**Derivation rule** (computed, closed over statuses; the judge's opinion of
the overall outcome, if it offers one, is discarded — `enforce_judge`
precedent):

- All prior CONCERN+ findings `addressed` or `moved`-with-successor-tracked →
  addressed-leg `PASS`
- Any `disputed`, or judge unavailable/unparseable → `UNKNOWN` (fail-closed,
  dominates under `reduce_verdicts`)
- Any `unaddressed` → `FAIL`

**Final verdict:** `reduce_verdicts(addressed_leg, fresh_review_verdict)` —
the existing most-severe arithmetic, unchanged. Gate `metadata` carries the
per-finding statuses, the screen that settled each, both leg verdicts, and
the round SHAs — the audit record the slice title promises.

### Judge invocation mechanics

The judge call happens *inside* gate execution — it is not a step, so loop
verdict accounting is untouched. It reuses the review **transport only**
(`review_client` provider dispatch) with a new bundled template
`judge.findings-addressed`; review-file persistence is disabled for this
call.

An earlier draft encoded statuses as review severities and persisted the
judge's output through the review machinery. The design review (F003) caught
this as a hidden cross-consumer contract — and a live one: metrology's
`discover_judge_results` globs `*-review.*` and keeps anything whose
`reviewType` maps to an `is_judge` template, so findings-addressed evidence
(no score, severities meaning status codes) would be swept into the 320
calibration sample set. Structurally it also violated this design's own
principle 5: decider evidence dressed in assessor vocabulary. Dropped.

Instead the judge emits one status line per prior finding
(`<finding-id>: <status>[ successor=<fresh-finding-id>]`), parsed by a small
dedicated parser over the closed status set — the "no new parser" saving was
~20 lines and not worth the aliasing. The status enum and its parse tokens
are defined once in the new module.

### Gate evidence artifact

The gate persists **one evidence artifact per decision** — this is the
"review evidence" the original slice title promised:

- Filename pattern distinct from reviews (e.g.
  `{index}-gate.{policy}.{name}-r{revision}.md`) — deliberately **never**
  matching the `*-review.*` glob, so every existing and future review-file
  consumer excludes it by construction rather than by filtering.
- `docType: gate-evidence` frontmatter (provenance-distinct, consistent with
  304's `composed` provenance precedent), carrying: per-finding statuses and
  the screen that settled each, both leg verdicts, the round SHAs, revision
  numbers, and judge model/template when consulted.
- Written before the iteration's commit, so it enters the round's commit
  alongside the artifact and the fresh review — the audit trail assembles in
  git for free.

Gate `ActionResult.metadata` carries the same record in-process.

### Files touched

| File | Change |
|---|---|
| `pipeline/actions/gate.py` | Policy registry entry; dispatch to policy module; `most-severe` path unchanged |
| `pipeline/actions/findings_addressed.py` (new) | Status enum + parse tokens, status-line parser, screens, matcher, judge invocation (transport-only), contradiction check, derivation rule, gate-evidence persistence |
| `pipeline/steps/gate.py` | Policy-dependent validation (`judge_from` required/forbidden by policy; `judge:` block shape) |
| `pipeline/loader.py` | `_validate_gate_references` fields resolved per policy; reject `findings-addressed` in a loop with no per-round commit source |
| `pipeline/steps/loop.py` | `_validate_verdict_count` → unconsumed-verdict rule |
| `data/templates/judge-findings-addressed.yaml` (new) | Judge template: one status line per prior finding from the closed set, derived-not-declared instructions |
| `data/pipelines/` | One example pipeline demonstrating the target loop shape |

## Technical Decisions

1. **Gate policy, not a node type.** The extension seam
   (`VALID_GATE_POLICIES`) was declared in 304 and this is its first use.
   Vocabulary count stays flat; a newcomer learns nothing new.
2. **Fail-closed direction.** A prior CONCERN+ finding with no evidence of
   resolution is `unaddressed`, never `addressed`-by-default. `disputed` and
   judge failure map to `UNKNOWN`, which ranks most severe in
   `reduce_verdicts` — a check that could not run must not wave a round
   through (no-silent-pass, consistent with 901's UNKNOWN-fails-closed).
3. **Judge only on residue, iterations ≥ 2.** The plan entry's "doubles
   review cost per iteration" concern is resolved structurally: screens 0–2
   spend no tokens, round 1 never consults a judge, and the judge model
   defaults to the pipeline's `review-model` (cheap tier), not the dispatch
   model.
4. **Conservative matching over clever matching.** Screen 2 matches exact
   `location`+`category` only. The failure mode of fuzzy matching (false
   `addressed`) is worse than its benefit (fewer judge calls), because it
   fails open.
5. **Prior findings from `prior_outputs`, not git.** 910's accumulation
   already carries the prior review result in-process. Git is consulted only
   for the round diff, via SHAs already present in commit-action outputs.
   Resume caveat: a run resumed mid-loop must rehydrate `prior_outputs` with
   findings intact — verified against state persistence during
   implementation (Phase 6 task, not assumed).
6. **Round 1 is `PASS`-with-annotation, not `UNKNOWN`.** `UNKNOWN` would
   fail every first round closed; silence would hide that the check didn't
   run. Explicit metadata + log is the honest middle.
7. **Status set is closed and includes `disputed`.** A judge forced to choose
   between addressed/unaddressed will guess under uncertainty; the explicit
   "I cannot defend a status" token routes uncertainty to `UNKNOWN` →
   checkpoint, instead of laundering it into a confident status
   (same reasoning as 904's `unverified` location token).
8. **`UNKNOWN` discipline.** `UNKNOWN` is reserved for exactly one meaning:
   *the check could not run, and the system stops* (escalates via
   checkpoint; post-901 it fails closed and dominates reduction). It is
   never the disposition for a condition whose right action is knowable —
   config errors resolve at validation time, known runtime states resolve to
   their known verdicts (`committed: False` → Screen 1 `FAIL`, round 1 →
   annotated `PASS`). Mapping a known state to `UNKNOWN` would be doing
   something without knowing the right action and tagging the result; every
   `UNKNOWN` this policy can emit (judge transport failure, unparseable
   judge output, `disputed`, unresolvable SHA) is instead a *refusal to
   proceed* handed to a human.

## Success Criteria

- [ ] `most-severe` gates behave byte-identically to pre-slice (regression
      suite green, no config changes required for existing pipelines).
- [ ] Loop body dispatch + review + findings-addressed gate validates and
      runs; `until:` reads the gate's verdict.
- [ ] Two reviews with no gate still rejected by loop validation (910 Part B
      preserved).
- [ ] Byte-identical round produces addressed-leg `FAIL` with zero judge
      invocations (asserted via transport spy).
- [ ] Round 1 produces `no_prior_round` metadata + INFO log, never `UNKNOWN`.
- [ ] Recurring exact-match finding settles as `unaddressed` without a judge
      call.
- [ ] Judge `addressed` over an untouched region downgrades to `disputed`
      with a WARNING (contradiction check observable).
- [ ] Judge transport failure → addressed-leg `UNKNOWN` → gate `UNKNOWN` →
      `on-concerns` checkpoint fires (fail-closed path end-to-end).
- [ ] `findings-addressed` on a loop with no per-round commit source is
      rejected at validation time, never at runtime.
- [ ] `moved` without a verifiable successor downgrades to `disputed` with a
      WARNING.
- [ ] `unverified`-located prior findings are never settled by Screen 2.
- [ ] Gate-evidence artifact filename never matches `*-review.*`;
      `discover_judge_results` over a reviews dir containing one returns it
      in no sample set.
- [ ] Gate metadata carries per-finding statuses, settling screen, leg
      verdicts, and round SHAs.
- [ ] Example pipeline runs the target loop shape end-to-end.

## Risk Assessment

- **Judge status quality (Medium).** The residue judgment is the
  genuinely unmeasurable part; a weak judge model produces `disputed` churn
  (safe but noisy) or wrong `addressed` (caught only partially by the
  contradiction check). Mitigation: contradiction check + fail-closed
  derivation + checkpoint on UNKNOWN; error-rate measurement is the
  acknowledged future slice.
- **Matching brittleness under clean regeneration (Medium).** Exact matching
  will under-match, pushing volume to the judge — a cost risk, not a
  correctness risk (decision 4 chose this direction deliberately).
- **Resume rehydration (Low–Medium).** Decision 5's caveat; must be verified,
  not assumed.
- **Validator refinement regression (Low).** The unconsumed-verdict rule
  touches 910 Part B's guard; its existing tests pin the reject case.

## Implementation Notes

Effort: 3/5, consistent with the plan's provisional estimate — the evidence
plumbing (910/911) and the compose machinery (304) exist; the new work is one
policy module, one template, and two validation refinements. Sequence:
validator refinement first (it unblocks the target shape and is independently
testable), then the policy module with screens before judge, then the
template and example pipeline.
