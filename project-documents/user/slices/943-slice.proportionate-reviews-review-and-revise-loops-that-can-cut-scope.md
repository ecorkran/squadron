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

Recorded evidence, trading-ui slice 127, run `run-20261010-p4-e8ba2e27` (model opus, review-model sonnet):

| Commit | Round | Design words |
|---|---|---|
| 253fb35 | initial design | 4,673 |
| c012207 | revise 1 | 6,561 |
| 46dfa1e | revise 2 (run ends, CONCERNS) | 7,735 |
| 0589e8e | in-session Opus cut | 3,135 |

The loop grew the design by 66% and the run still ended at CONCERNS. The usable design was 40% of what the loop produced. In a pipeline, no in-session model trims the result.

This slice changes prompts and templates only. Reviews get a proportionality criterion that grades an overweight artifact as CONCERN. Revise is told that cutting or deferring scope resolves a finding.

## Value

- P4, P5 and the planning pipelines stop producing designs and task files that get heavier with every round.
- A reviewer can now ask for a cut, and revise will act on that request.
- The PM no longer has to trim by hand after every pipeline run. That trim is the step that blocks moving more phase work into pipelines.

## Technical Scope

Included:

1. **Proportionality criterion** in the `slice`, `tasks` and `arch` review templates (`src/squadron/data/templates/`).
2. **Gap findings must name a need.** Slice and tasks reviews may raise a missing-item finding only when they can name the requirement the gap leaves unmet. This qualifies the existing omission criteria (failure modes, NFR restatement, load-test tasks), which are the main source of added weight.
3. **Revise instruction** in `DispatchAction._findings_block` (`src/squadron/pipeline/actions/dispatch.py`), stating that the smallest sufficient change wins and that cutting or deferring scope is a valid resolution.
4. **Findings-addressed judge** (`judge-findings-addressed.yaml`) counts a removal or deferral of the scope a finding was about as `addressed`. Without this, the findings-addressed gate would treat a cut as `unaddressed`.
5. **Mirrored judge templates** `judge-slice-vs-arch` and `judge-tasks-vs-slice` get the same criterion. They copy the review criteria word for word, and leaving them behind would score designs against a standard the reviews no longer use.

Excluded:

- **Code review template (`code.yaml`).** The approved task file already bounds the size of code, and code revise rounds do not show the ratchet. The revise instruction in item 3 applies to code revise anyway, so a code finding that asks for a simplification is now explicitly valid.
- **Context-forge phase prompts** (the P4/P5 creation prompts). That is the initial size, not the ratchet, and it lives in another repo.
- **Loop mechanics** (round counts, accept thresholds, an automatic size gate). Prompts first. A numeric size gate gets added only if the rerun shows that prompts are not enough.

## Dependencies

### Prerequisites

None.

### Interfaces Required

- `ReviewTemplate` YAML schema: unchanged. Only `system_prompt` text changes.
- Review parser: unchanged. Proportionality findings use the existing `### [CONCERN] Title` and `location:` format. In arch reviews they use `category: antipattern`, so no new category tag is added.

## Architecture

### Component Structure

```
review template (system_prompt) ──► reviewer model ──► findings (incl. proportionality CONCERNs)
                                                              │
dispatch revise (feedback: review) ◄── _findings_block ◄──────┘
        │  + "smallest sufficient change; cutting/deferring resolves"
        ▼
revised artifact ──► next review round ──► (findings-addressed gate: judge counts cuts as addressed)
```

No new components. Four YAML prompt edits and one string change in `_findings_block`.

### Data Flow

Unchanged. A proportionality finding goes through the same path as any other finding: review → `ActionResult.findings` → `_findings_block` → revise prompt.

### State Management

None.

## Technical Decisions

### Technology Choices

**Criterion text.** Each template gets one criterion bullet, worded for the artifact it reviews, under its existing criteria list. Draft wording (final text is set in Phase 6):

- `slice.yaml` and `judge-slice-vs-arch.yaml`: *Proportionality: the design's size, mechanism count and effort fit what the slice must deliver. Name scope that can be cut or deferred. Examples of such scope: sections that restate other documents, handling for cases the slice does not have, configuration or abstraction nothing uses yet, and the heaviest option where a lighter one meets the requirement. An overweight design is a CONCERN, and the finding names what to cut.* The existing over-engineering bullet folds into this one.
- `tasks.yaml` and `judge-tasks-vs-slice.yaml`: *Proportionality: task count, step detail and file count fit the slice. Flag test tasks beyond what the success criteria need, steps that dictate implementation detail the slice does not require, and a split into multiple task files that the size does not need. An overweight task file is a CONCERN, and the finding names what to cut or merge.*
- `arch.yaml`: a short PROPORTIONALITY block after ANTIPATTERNS. It asks the reviewer to grade an overweight architecture as CONCERN with `category: antipattern` and to name the cuttable scope.

**Gap qualifier** (slice, tasks and both judges): *Raise a missing-item finding only when you can name the requirement the gap leaves unmet. Absence of an item this artifact does not need is not a finding.* It sits directly under the omission criteria it qualifies.

**Revise instruction.** `_findings_block` appends one paragraph after the findings list, and only when findings exist:

> Resolve each finding with the smallest change that satisfies it. Removing, simplifying or deferring scope is as valid as adding to the artifact. Do not add material no finding asks for. Name any deferred scope in the artifact.

The no-findings branch ("Perform an initial improvement pass") is left unchanged.

**Why the instruction goes in `_findings_block` and not in a per-template revise field:** one sentence that is true for every review type does not justify a schema field. If a review type later needs different revise guidance, adding a `revise_guidance` template field is the extension point.

**Judge `addressed` definition** gains: *A change that removes or defers the scope a finding was about addresses it.*

### Patterns and Conventions

- The prompt text contains no example values next to fill-in slots, per the hallucination-trap rule in CLAUDE.md.
- Templates that mirror each other (`slice`/`judge-slice-vs-arch`, `tasks`/`judge-tasks-vs-slice`) get identical criterion text.

## Integration Points

### Provides to Other Slices

Every pipeline with a `feedback: review` revise step picks this up without config changes: P4, P5, P45, P456, P56, P6, implement, implement-plan, slices-plan, tasks-plan, findings-addressed-cycle and judge-cycle.

### Consumes from Other Slices

- Slice 320 judge calibration. Judge scores recorded before this change are not comparable on the proportionality criterion. The criterion is new, so old scores simply lack it and no migration is needed.

## Success Criteria

### Functional Requirements

1. `slice.yaml`, `tasks.yaml` and `arch.yaml` each state a proportionality criterion that grades an overweight artifact as CONCERN and requires the finding to name what to cut or defer.
2. `slice.yaml` and `tasks.yaml` qualify their omission criteria: a gap finding names the unmet requirement.
3. `judge-slice-vs-arch.yaml` and `judge-tasks-vs-slice.yaml` carry the same criterion and qualifier text as their review counterparts.
4. The revise prompt built by `_findings_block` contains the smallest-sufficient-change paragraph whenever findings exist.
5. `judge-findings-addressed.yaml` counts removal or deferral of a finding's scope as `addressed`.

### Technical Requirements

- A test in `tests/pipeline/actions/test_dispatch.py` asserts the paragraph is present when findings exist and absent in the no-findings branch.
- Existing template-load and review-parse tests stay green.
- ruff format, ruff check and pyright are clean.
- CHANGELOG Unreleased gets a bullet saying review loops can now cut scope.

### Integration Requirements

The trading-ui slice 127 rerun (walkthrough below) produces a final design no larger than its first-round design, and well below the recorded 7,735 words.

### Verification Walkthrough

1. **Unit check.**
   ```bash
   cd /Users/manta/source/repos/manta/squadron
   pytest tests/pipeline/actions/test_dispatch.py tests/review -q
   ```

2. **See the revise prompt.** Render a P4 run without executing it and confirm that the revise step's prompt ends with the new paragraph:
   ```bash
   sq run P4 --slice 943 --dry-run
   ```
   If the dry run does not render the feedback prompt (it needs a live review result), check the paragraph through the unit test in step 1 instead.

3. **Rerun slice 127 from its original input.** Use a throwaway trading-ui worktree at `2c5e9d4`, the commit before the recorded design was added:
   ```bash
   cd /Users/manta/source/repos/manta/trading-ui
   git worktree add /tmp/tui-943 2c5e9d4 -b verify-943
   cd /tmp/tui-943
   sq run P4 --slice 127 --model opus --review-model sonnet
   ```
   These are the recorded run's models. The installed `sq` must be the 943 build (`uv tool install -e` from the squadron checkout, or the project's equivalent).

4. **Measure each round.** P4 commits every loop iteration (`commit_each_iteration: true`):
   ```bash
   git log --format=%h -- project-documents/user/slices/127-slice.pan-to-load-range-fetching.md \
     | while read c; do echo "$c $(git show $c:project-documents/user/slices/127-slice.pan-to-load-range-fetching.md | wc -w)"; done
   ```
   Pass: no revise round grows the design over the round before it by more than a small margin, and the final word count is no larger than the initial design. Compare against the baseline 4,673 → 6,561 → 7,735. Also read the review files: at least one finding should ask for a cut, or the review should PASS outright.

5. **Record and clean up.** Put the per-round word counts and final verdict in the DEVLOG and on the 943 entry in the slice plan, then remove the worktree:
   ```bash
   cd /Users/manta/source/repos/manta/trading-ui
   git worktree remove /tmp/tui-943 && git branch -D verify-943
   ```

A single model run is noisy. If the rerun fails the pass condition, read its review findings before changing anything. Either the reviewer did not raise proportionality (a criterion wording problem) or revise ignored the instruction (a revise prompt problem). The fix differs between the two.

## Implementation Notes

### Development Approach

1. Revise paragraph in `_findings_block`, with its test. Commit.
2. Slice, tasks and arch review template edits plus the judge mirrors. Commit.
3. Findings-addressed judge wording. Commit.
4. CHANGELOG bullet.
5. Run the slice 127 rerun walkthrough and record the result.

### Special Considerations

- Tests do not check the template wording itself. Prompt text tests are brittle and prove nothing about model behavior. The slice 127 rerun is the real test.
- Effort: 2/5.
