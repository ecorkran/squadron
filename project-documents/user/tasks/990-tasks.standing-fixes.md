---
docType: tasks
slice: standing-fixes
project: squadron
lldReference: project-documents/user/slices/990-slice.standing-fixes.md
parent: project-documents/user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: []
projectState: Standing container for multi-step fixes. Add a task group per issue.
status: complete
dateCreated: 20261011
dateUpdated: 20261021
---

# Tasks: Standing Fixes

## #189 Pipelines merge slices with unchecked task boxes

- [x] Merge refuses unchecked task items; close-out dispatch added to the implement body (e602d4e5)
- [x] Guide wording (ai-project-guide v0.20.8)

## #200 Failed dispatch in a revise loop still merges

- [x] A failed dispatch ends the loop with the loop's `on_exhaust` status (451644ac)
- [x] `ProviderError` prints as one line, not a traceback
- [x] An unusable SDK session is replaced with a fresh one, and the replacement is logged
- [x] The run's final status says which steps succeeded (including the merge) when a later step fails

## #199 Dispatch ends while a background shell runs

- [x] Pipeline SDK sessions deny `run_in_background` Bash calls via a PreToolUse hook; the agent reruns in the foreground (verified against the real SDK)

## #230 + #248 Pipeline failure recovery

- [x] #230: `set_model` rejection retries a bounded number of times (each retry logged at WARNING), then fails the step with one line naming the step, model alias and ID, and the API message; traceback only at -vv
- [x] #248: Check whether the SDK reports session/usage limits as a structured field (not only `is_error` result text); the quota pause below uses it, and does not match error strings unless the SDK offers nothing else
  - [x] Yes (SDK 0.2.162): `RateLimitEvent.rate_limit_info` carries `status` (`rejected`), `rate_limit_type` (`five_hour`, `seven_day*`, `overage`) and `resets_at`; also `AssistantMessage.error == "rate_limit"` and `ResultMessage.api_error_status`. Today a rejected event is retried with 2–60 s backoff, pointless against a limit that resets in hours
- [x] #248: A quota or session-limit failure pauses the whole run at the failed step instead of flagging the item and continuing; a plain `sq run --resume <id>` restarts at that step
- [x] #248: `sq run --resume <id> --flagged` retries every flagged and not_run item in order, stopping on the first rejection
- [x] #248: The end-of-run summary prints the exact recovery command(s) for a paused run or flagged items
- [x] #248: Item resume commits uncommitted leftovers on the target when every dirty path belongs to an item of the batch (widened from "the item being retried": the reported case was item 130's file blocking item 128); any other dirty path still rejects
- [x] #248: PIPELINES.md gives one recovery path per failure kind; rerun / resume / item-resume guidance is consistent

## #271 sq squash: squash a run buried under later commits

- [x] Find the newest run for the artifact anywhere in unpushed first-parent history, not only at HEAD; commits already on a remote are never part of a run
- [x] Rewrite without touching the working tree: build the squashed commit, recreate every later commit (merges included) with its original tree, author, committer and message, then move the branch with one compare-and-swap ref update
- [x] `--dry-run` and the command's result report how many later commits are rewritten
- [x] Tests: run buried under foreign commits, under a merged slice branch, and under another artifact's run; rerun is a no-op; content and merge topology above the run are unchanged
- [x] PIPELINES.md and CHANGELOG describe the new behavior

## #276 sq squash almost never finds a run

- [x] `_find_run` keeps walking past a stretch that is under two commits after trimming; the run is the newest stretch with at least two
- [x] A "nothing to squash" result carries a reason: the newest stretch found (or none), and the commit that ended it with the files outside the path set; `sq squash` prints it
- [x] Mixed bookkeeping commits stay outside the path set (widening it would sweep status-flip commits into the wrong run); the refusal text names them instead
- [x] A user or project pipeline that shadows a built-in and lacks a step type the built-in has logs a WARNING naming the missing step types when it loads
- [x] Regression tests from the slice 440 shape: old run then a one-commit artifact stretch near HEAD; a mixed bookkeeping commit above the run; the no-op reason text; the shadow warning
- [x] CHANGELOG bullet; PIPELINES.md note on the shadow warning

## #275 sq onboard: exclude cf-installed tooling from the knowledge graph build

- [x] The build-graph step adds the cf-installed tooling directories to `.understand-anything/.understandignore` before `/understand` scans
- [x] Test, CHANGELOG bullet

## #279 Code review can PASS with zero tool calls

- [x] Code review prompt requires reading the files behind any finding, and the surrounding code for any claim about behavior outside the hunk, before a PASS
- [x] A code review that was offered tools, made no successful call, and returned PASS logs a WARNING naming the review and the condition; no verdict cap, no hard gate
- [x] The review artifact carries a `**Coverage:**` line stating tool calls made (failed-only calls count as zero successful); a run with no tools offered is unchanged
- [x] Tests: tools offered + PASS + zero successful calls warns and records coverage; at least one successful call does not warn; no tools offered unchanged; failed-only calls count as zero
- [x] CHANGELOG bullet
- **Commit**: `fix: require file reads and report tool coverage in code reviews (#279)`

## #278 Code review diff cap applies to the whole diff

- [x] `review.max_file_size_bytes` is applied per file: the diff is split by file and each file's section capped, not the concatenation; order and total-cap handling stay as they are
- [x] Per-file `total_chars` / `injected_chars` recorded; the review artifact (frontmatter and body) lists cut and omitted files beside the `**Diff:**` line
- [x] When any file is cut or omitted the prompt names them and says they can be read with `read_file`; the truncation marker no longer says "file too large for API review" to a tool-enabled run
- [x] `impose_diff_coverage` uses the per-file record, so a PASS is capped when an omitted file was never read
- [x] Tests: many small files over the cap in total, none truncated; one oversized file among small ones, only it cut; artifact lists cut and omitted files and the prompt names them; PASS with an omitted unread file capped to CONCERNS naming it
- [x] CHANGELOG bullet
- **Commit**: `fix: apply the review diff cap per file and report dropped files (#278)`

## #286 sq review: accept -p/--param review-model=X as an alias for --model

- [x] The review commands accept `-p`/`--param`, parsed by the same key=value (comma-separated) parser `sq run` uses
- [x] `review-model` is the only accepted key and resolves as `--model` does; any other key errors naming `review-model`; `--model` and `-p review-model=` with different values error, equal values are accepted
- [x] Tests: `-p review-model=sonnet` resolves the same model as `--model sonnet`; unknown key; both given different; both given equal
- [x] CHANGELOG bullet
- **Commit**: `feat: accept -p review-model=X on sq review as an alias for --model (#286)`
