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

## #288 sq run: skip the Context Forge pre-flight for pipelines whose steps don't use CF

- [x] Every step type declares `needs_context_forge(step)` (protocol member): `dispatch` answers from its `artifact` key, `compact` is False, containers (`loop`, `fan_out`) answer for their body, every other step type is True
- [x] `_run_pipeline_sdk` runs `_check_cf` only when some step needs Context Forge
- [x] Verified by running a dispatch-only pipeline of Amoeba's shape (`prompt_files`, `reply_from`, `reply_file`) from a directory with no CF registration: both steps completed, nothing else on the path called cf
- [x] Tests: dispatch-only pipeline runs with a failing pre-flight; `artifact` and `branch` pipelines still fail it; containers answer for their body; every registered step type declares an answer
- [x] CHANGELOG bullet
- **Commit**: `fix: skip the Context Forge pre-flight for pipelines whose steps do not use it (#288)`

## #229 sq stats producers counts replay runs as observed runs

- [x] `RunState.replay` (default False) marks a replay run; `sq replay` starts its runs with a hidden `--replay` flag that sets it (a structured marker, not the run id)
- [x] `extract_units` leaves replay runs out and counts them (`ExcludedCounts.replay_runs`); the `sq stats producers` footer reports the count
- [x] Tests: flag recorded on the run state and hidden; replay runner passes `--replay`; replay run excluded from units and counted in the footer
- [x] CHANGELOG bullet
- **Commit**: `fix: leave replay runs out of sq stats producers (#229)`

## #240 Refuse to start an implement step while the slice design has pending-pm decisions

- [x] New `cf-op` operation `check_decisions` runs `cf validate design --json <design file>` and reads only the `pending` list (squadron does not parse decision status; missing sections are ignored)
- [x] The implement phase expands with `check_decisions` right after `set_slice`; design and tasks phases and initiative-scoped steps do not
- [x] Pending decisions pause the run (`awaits_human`) naming each decision and the `sq run --resume` command, before any dispatch; a slice with no design file, or a cf report with no `pending` list, fails explicitly
- [x] Tests: action passes/pauses/ignores missing/no design file/old cf/error envelope; expand puts the check after `set_slice` for implement only
- [x] CHANGELOG bullet
- **Commit**: `feat: pause an implement step while the slice design has pending PM decisions (#240)`

## #196 Review line citations are model-counted

- [x] A cited range that starts in the file and ends exactly one line past it is not marked `location_verified: false` (the issue's "Secondary" item)
- [x] Tests: `3-11` and `10-11` verified on a 10-line file; `3-12`, `11-12` and single `11` still unverified; `location_span` extraction
- [x] CHANGELOG bullet
- [x] Numbered `read_file` / injected bodies for review runs: dropped (PM decision). Measured 12 of 967 checkable citations (1.2%) unverified; issue closed
- **Commit**: `fix: treat a citation range ending one past EOF as sloppy, not phantom (#196)`

## #180 Three metrology audit CLI tests sleep through the real run cooldown

- [x] `tests/metrology/test_audit_cli.py` sets `metrology.audit_run_cooldown_s` to 0 for every test (autouse user-config fixture); the cooldown between runs is already tested with a fake sleep in `test_audit_series.py`
- [x] The three variance tests drop from ~120 s each to under a second; the file runs in about 2 s

## #283 sq pipelines list hides a shadowed built-in

- [x] `PipelineInfo.hidden` keeps every pipeline a winner hides, nearest first; `shadows` is derived from it
- [x] The listing shows each hidden pipeline in its own group, marked `shadowed by <winner source>`, counted in the group; the winner keeps `shadows <source>`
- [x] Tests: loader keeps both hidden levels; listing keeps the built-in in the Built-in group and count; a user pipeline hidden by a project one is listed under User
- [x] CHANGELOG bullet

## #299 allowed_tools: [] on an SDK (Claude) model runs tool-less

- [x] Live probe (Agent SDK 0.2.162, `sonnet`): with `tools=[]`, `setting_sources=[]`, empty system prompt, the init message lists `tools: []`, the model reports no tools, planted `CLAUDE.md` text does not appear (it does with `setting_sources=["project"]`), and `can_use_tool` is never called because there is nothing to call
- [x] Layer 1: `tools=[]` (already built by the SDK provider) plus an isolated config for a declared `allowed_tools: []` on the SDK: `setting_sources=[]`, no auto-memory, no project rules, `use_default_system_prompt=False`. No `disallowed_tools` list: the probe shows `tools=[]` leaves no built-in tool, and a denylist drifts when the CLI adds tools
- [x] Layer 2: `permission_mode="default"` with a deny-everything `can_use_tool` that logs at ERROR, for `allowed_tools == []` only
- [x] Layer 3: the agent reports `tool_calls_made` for a declared empty list, and dispatch fails the step with `tool_isolation` (reply discarded) when it is above 0
- [x] Routing: a no-tools step never uses the persistent session, and the "explicit sdk profile needs a session" guard does not apply to it; fresh agent per dispatch (one-shot)
- [x] `ProviderCapabilities.honors_empty_tools` replaces the `can_read_files` check in `tool_isolation_error`; the error names the missing property; Codex still refused
- [x] `--validate --strict` reports a no-tools step whose literal model cannot be isolated
- [x] Layer 4: live probe kept as `tests/providers/sdk/test_tool_less_live.py` (`SQ_LIVE_SDK=1`), rerun on every Agent SDK bump
- [x] Tests, docs/PIPELINES.md and CHANGELOG bullet
- **Commit**: `fix: run allowed_tools: [] dispatch steps tool-less on SDK models (#299)`
