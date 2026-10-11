---
docType: tasks
slice: proportionate-reviews-review-and-revise-loops-that-can-cut-scope
project: squadron
lld: user/slices/943-slice.proportionate-reviews-review-and-revise-loops-that-can-cut-scope.md
dependencies: []
projectState: >
  Slice design 943 complete after one review round (20261011); the judge template edits were cut.
  No code written. Prompt-only change: a two-sided proportionality criterion in the slice, tasks
  and arch review templates, plus a smallest-sufficient-change paragraph in the revise prompt.
dateCreated: 20261011
dateUpdated: 20261011
status: not_started
---

## Context Summary

- Working on **943 proportionate-reviews**. Review loops only add weight. Trading-ui slice 127 grew from 4,673 to 7,735 words over two revise rounds. This slice teaches reviews to flag overweight artifacts and teaches revise that cutting is a valid fix.
- The design's "Technology Choices" section holds the draft wording for every edit. Tasks reference it and do not repeat it. Final wording may be tightened, but each element listed in a task must be present.
- Files touched: `src/squadron/data/templates/slice.yaml`, `tasks.yaml`, `arch.yaml`, and `src/squadron/pipeline/actions/dispatch.py` (`_findings_block`), plus tests.
- Do not edit any `judge-*.yaml` template. Editing a judge prompt re-keys its calibration identity (design, "Excluded").
- Every code task ends with `ruff format`, `ruff check`, `pyright` (zero errors), the touched tests, and a commit on the slice branch.
- Effort: 2/5.

## Tasks

- [ ] **Task 1: Branch**
  - [ ] Read the target: `cf config get git.integration_branch` (empty means `main`)
  - [ ] Create `943-slice.proportionate-reviews-review-and-revise-loops-that-can-cut-scope` from the target
  - **Success:** on the slice branch, working tree clean

- [ ] **Task 2: Revise paragraph in `_findings_block`**
  - [ ] Append the revise paragraph from the design ("Revise instruction") after the findings list in `DispatchAction._findings_block`. Keep it as a module-level constant next to the method.
  - [ ] Leave the no-findings branch ("Perform an initial improvement pass") unchanged
  - **Success:** with findings, the prompt contains the paragraph after the last finding line; with none, the prompt is unchanged

- [ ] **Task 3: Test the revise paragraph**
  - [ ] Update the exact-match expectation in `test_single_file_prompt_is_unchanged` (`tests/pipeline/actions/test_dispatch.py`) to include the paragraph, and check other exact-match prompt tests in the file and in `tests/review` for the same
  - [ ] Add a test that the paragraph appears through the fallback path (`_resolve_prompt_from_prior_review`, no `feedback` param)
  - [ ] Add a test that a review with no findings yields the initial-improvement text without the paragraph
  - [ ] Run `pytest tests/pipeline tests/review -q`, then ruff and pyright
  - [ ] Commit: `feat: let revise resolve findings by cutting or deferring scope`
  - **Success:** tests pass, zero pyright errors

- [ ] **Task 4: Slice review template (`slice.yaml`)**
  - [ ] Remove "over-engineering" from the "Common antipatterns" bullet (keep under-specification and hidden dependencies) and add the proportionality bullet from the design. It must state all three: overweight is a CONCERN, the finding names what to cut, and cutting or deferring scope the slice plan entry assigns is a CONCERN.
  - [ ] Add the gap qualifier directly under the failure-mode and NFR bullets
  - **Success:** the template-load tests in `tests/review` pass, and the system prompt contains both additions

- [ ] **Task 5: Tasks review template (`tasks.yaml`)**
  - [ ] Add the proportionality bullet from the design: task count, step detail and file count fit the slice; an overweight task file is a CONCERN naming what to cut or merge
  - [ ] Add the gap qualifier directly under the NFR load-test and CI-wiring bullets
  - **Success:** the template loads and the system prompt contains both additions

- [ ] **Task 6: Arch review template (`arch.yaml`)**
  - [ ] Fold the "Over-engineering" antipattern line into a new PROPORTIONALITY block after ANTIPATTERNS. It must state the same two sides as `slice.yaml` and grade a finding CONCERN with `category: antipattern`.
  - **Success:** the template loads and the system prompt contains the block

- [ ] **Task 7: Verify templates and commit**
  - [ ] Run `pytest tests/review -q` (template loading, tool exclusions, parse tests)
  - [ ] `git diff --stat` shows no `judge-*.yaml` changes
  - [ ] Commit: `feat: add proportionality criterion to slice, tasks and arch reviews`
  - **Success:** tests pass and the diff touches only the three templates

- [ ] **Task 8: CHANGELOG**
  - [ ] Add an Unreleased bullet: reviews now flag overweight designs, task files and architectures, and revise can resolve a finding by cutting or deferring scope
  - [ ] Commit: `docs: add proportionate reviews to CHANGELOG`

- [ ] **Task 9: Rerun slice 127 (design Verification Walkthrough steps 2–5)**
  - [ ] Install the branch build of `sq` and confirm `sq --version` runs from this checkout
  - [ ] Create the trading-ui worktree at `2c5e9d4` and run `sq run P4 --slice 127 --model opus --review-model sonnet`
  - [ ] Record per-round word counts against the baseline (4,673 → 6,561 → 7,735)
  - [ ] Check coverage against 127's slice plan entry and the approved cut `0589e8e`, and list any deferrals with their GitHub issue numbers
  - [ ] Read the rerun's review files: every real-gap CONCERN the baseline run raised (failure mode on a new I/O path, NFR target) is still raised, or the design already handles it
  - [ ] If the rerun fails either check, stop and report the review findings to the PM along with the matching cause from the design (criterion wording, revise wording, or gap qualifier). Do not iterate on wording without PM direction.
  - [ ] Remove the worktree and its branch
  - [ ] Record results in the design's Verification Walkthrough, the DEVLOG and the 943 slice plan entry; commit `docs: record slice 943 verification results`
  - **Success:** final design words ≤ initial design words, and coverage holds; or a stop report naming the cause
