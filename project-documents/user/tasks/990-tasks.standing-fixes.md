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
