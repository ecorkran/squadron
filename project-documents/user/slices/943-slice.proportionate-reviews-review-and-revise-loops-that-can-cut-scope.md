---
docType: slice-design
slice: proportionate-reviews-review-and-revise-loops-that-can-cut-scope
project: squadron
parent: project-documents/user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: []
interfaces: []
dateCreated: 20261011
dateUpdated: 20261011
status: not_started
---

# Slice Design: Proportionate Reviews — Review-and-Revise Loops That Can Cut Scope

## Overview

Review-and-revise loops only add weight. The slice, tasks and arch review templates grade what is missing. Over-engineering gets one passing line in slice.yaml and arch.yaml and none in tasks.yaml. The revise prompt says only "Address the following findings". Each round adds material and none removes it.

Recorded evidence comes from trading-ui slice 127, run `run-20261010-p4-e8ba2e27` (model opus, review-model sonnet):

| Commit | Round | Design words |
|---|---|---|
| 253fb35 | initial design | 4,673 |
| c012207 | revise 1 | 6,561 |
| 46dfa1e | revise 2 (run ends, CONCERNS) | 7,735 |
| 0589e8e | in-session Opus cut | 3,135 |

The loop grew the design by 66% and still ended at CONCERNS. The usable design was 40% of what the loop produced. In a pipeline, no in-session model trims the result.

This slice changes prompts only. Reviews get a proportionality criterion that grades an artifact as CONCERN in both directions: too heavy, or cut below what the plan assigns it. Revise is told that cutting or deferring scope the plan does not require resolves a finding, and that each deferral becomes a GitHub issue.

## Value

- P4, P5 and the planning pipelines stop producing designs and task files that grow with every round.
- A reviewer can ask for a cut and revise will act on it, without the opposite failure of deferring everything into future slices.
- The PM no longer hand-trims after every pipeline run. That trim is what blocks moving more phase work into pipelines.

## Technical Scope

Included:

1. **Proportionality criterion** in the `slice`, `tasks` and `arch` review templates (`src/squadron/data/templates/`). It has two sides: an overweight artifact is a CONCERN, and dropping or deferring scope that the parent plan assigns to this artifact is a CONCERN.
2. **Gap findings must name a need.** Slice and tasks reviews raise a missing-item finding only when they can name the requirement the gap leaves unmet. This qualifies the existing omission criteria (failure modes, NFR restatement, load-test tasks), which are the main source of added weight.
3. **Revise instruction** in `DispatchAction._findings_block` (`src/squadron/pipeline/actions/dispatch.py`): use the smallest sufficient change; cutting or deferring scope the plan does not require is a valid resolution; record each deferral as a GitHub issue named in the artifact.

Excluded:

- **Judge templates** (`judge-slice-vs-arch`, `judge-tasks-vs-slice`, `judge-findings-addressed`). Editing a judge's prompt re-keys its calibration identity (`metrology/identity.py`), which lapses existing graduations, and that churn belongs to initiative 320. `judge-findings-addressed` already counts any diff change that "substantively resolves" a finding as `addressed`, and a cut is such a change. If the 127 rerun shows judges working against cuts, that gets its own issue.
- **Code review template (`code.yaml`).** The approved task file already bounds code size. The revise instruction still reaches code revise rounds, so a simplification finding there is now explicitly valid.
- **Context-forge phase prompts.** They set the initial size, not the ratchet, and live in another repo.
- **Loop mechanics and a numeric size gate.** Prompts come first. A gate gets added only if the rerun shows prompts are not enough.

## Dependencies

### Prerequisites

None.

### Interfaces Required

- `ReviewTemplate` YAML schema: unchanged. Only `system_prompt` text changes.
- Review parser: unchanged. Proportionality findings use the existing `### [CONCERN] Title` and `location:` format. In arch reviews they carry `category: antipattern`.

## Architecture

### Component Structure

```
review template (system_prompt) ──► reviewer model ──► findings (incl. proportionality CONCERNs)
                                                              │
revise dispatch ◄── _findings_block ◄─────────────────────────┘
        │  + "smallest sufficient change; cut/defer what the plan
        │     does not require; deferral = GitHub issue"
        ▼
revised artifact ──► next review round
```

No new components: three YAML prompt edits and one string change in `_findings_block`.

### Data Flow

Unchanged. A proportionality finding takes the same path as any other finding: review, then `ActionResult.findings`, then `_findings_block`, then the revise prompt.

### State Management

None.

## Technical Decisions

### Technology Choices

**Criterion text.** Each template gets one criterion bullet, worded for its artifact. The existing over-engineering bullet folds into it. Draft wording (final text is settled in Phase 6):

- `slice.yaml`: *Proportionality: the design's size, mechanism count and effort fit what the slice must deliver. Name scope that can be cut or deferred: sections restating other documents, handling for cases the slice does not have, configuration or abstraction nothing uses yet, the heaviest option where a lighter one meets the requirement. An overweight design is a CONCERN and the finding names what to cut. Dropping or deferring scope the slice plan entry assigns to this slice is also a CONCERN.*
- `tasks.yaml`: *Proportionality: task count, step detail and file count fit the slice. Flag test tasks beyond what the success criteria need, steps dictating implementation detail the slice does not require, and a split into multiple task files the size does not need. An overweight task file is a CONCERN and the finding names what to cut or merge.* The existing "success criterion with no task" check already covers the under-delivery side.
- `arch.yaml`: a short PROPORTIONALITY block after ANTIPATTERNS, with the same two-sided rule, graded CONCERN with `category: antipattern`.

**Gap qualifier** (slice and tasks), placed directly under the omission criteria: *Raise a missing-item finding only when you can name the requirement the gap leaves unmet. Absence of an item this artifact does not need is not a finding.*

**Revise instruction.** `_findings_block` appends this paragraph after the findings list, only when findings exist:

> Resolve each finding with the smallest change that satisfies it. Removing or simplifying is as valid as adding. Defer only scope the artifact's plan does not require, and record each deferral as a GitHub issue named in the artifact. Do not add material no finding asks for.

The no-findings branch is unchanged.

**Why `_findings_block` and not a per-template field:** the sentence holds for every review type, so a schema field would be weight with no use. If guidance ever needs to diverge per review type, a `revise_guidance` template field is the extension point.

### Patterns and Conventions

- Prompt text contains no example values next to fill-in slots (the hallucination-trap rule in CLAUDE.md).

## Integration Points

### Provides to Other Slices

`_findings_block` serves both revise paths: `feedback: review` steps (P4, P5, P45, P456, P56, P6, implement, implement-plan, slices-plan, tasks-plan, findings-addressed-cycle, judge-cycle) and the fallback fix-from-prior-review path (`_resolve_prompt_from_prior_review`). Neither path needs a config change.

### Consumes from Other Slices

None. No judge template changes, so slice 320 calibration identities are untouched.

## Success Criteria

### Functional Requirements

1. `slice.yaml`, `tasks.yaml` and `arch.yaml` each state a proportionality criterion that grades an overweight artifact as CONCERN and requires the finding to name what to cut. `slice.yaml` and `arch.yaml` also grade cutting plan-assigned scope as CONCERN.
2. `slice.yaml` and `tasks.yaml` qualify their omission criteria: a gap finding names the unmet requirement.
3. The revise prompt built by `_findings_block` contains the paragraph above whenever findings exist.

### Technical Requirements

- A test in `tests/pipeline/actions/test_dispatch.py` asserts the paragraph is present when findings exist and absent in the no-findings branch.
- Existing template-load and review-parse tests stay green.
- ruff format, ruff check and pyright are clean.
- CHANGELOG Unreleased gets a bullet saying review loops can now cut scope.

### Integration Requirements

The trading-ui slice 127 rerun (walkthrough below) produces a final design no larger than its first-round design that still covers 127's slice plan entry.

### Verification Walkthrough

1. **Unit check.**
   ```bash
   cd /Users/manta/source/repos/manta/squadron
   pytest tests/pipeline/actions/test_dispatch.py tests/review -q
   ```

2. **Rerun slice 127 from its original input.** Use a throwaway trading-ui worktree at `2c5e9d4`, the commit before the recorded design was added, and the recorded run's models. The installed `sq` must be the 943 build.
   Run it from a standard terminal: `sq run` refuses SDK pipeline execution inside a Claude Code session. Confirm the 943 build with `which sq` (expect the squadron checkout's `.venv/bin/sq`, an editable install).
   ```bash
   cd /Users/manta/source/repos/manta/trading-ui
   git worktree add /tmp/tui-943 2c5e9d4 -b verify-943
   cd /tmp/tui-943
   sq run P4 127 --model opus -p review-model=sonnet
   ```

3. **Measure each round.** P4 commits every loop iteration:
   ```bash
   F=project-documents/user/slices/127-slice.pan-to-load-range-fetching.md
   git log --format=%h -- $F | while read c; do echo "$c $(git show $c:$F | wc -w)"; done
   ```
   Weight passes when no revise round grows the design materially and the final word count is no larger than the initial design. The baseline was 4,673 → 6,561 → 7,735.

4. **Check coverage.** Compare the final design against 127's slice plan entry and against the approved cut (`0589e8e`). Every behavior the approved cut delivers must still be in scope, or be deferred with a named GitHub issue. Read the review files too: any CONCERN the baseline run raised about a real gap (a missing failure mode on a new I/O path, a missing NFR target) should still be raised, or the design should already handle it.

5. **Record and clean up.** Put per-round word counts, verdicts and the coverage result in the DEVLOG and on the 943 slice plan entry. Then:
   ```bash
   cd /Users/manta/source/repos/manta/trading-ui
   git worktree remove /tmp/tui-943 && git branch -D verify-943
   ```

A single model run is noisy. If the rerun fails, read the review findings before changing anything. There are three possible causes, each with a different fix: the reviewer did not raise proportionality (criterion wording), revise ignored the instruction (revise wording), or the gap qualifier silenced a real gap (qualifier wording).

## Implementation Notes

### Development Approach

1. Revise paragraph in `_findings_block`, with its test. Commit.
2. Slice, tasks and arch template edits. Commit.
3. CHANGELOG bullet.
4. Run the slice 127 rerun walkthrough and record the result.

### Special Considerations

- No tests check template wording. Prompt-text tests are brittle and prove nothing about model behavior; the 127 rerun is the real test.
- Effort: 2/5.
