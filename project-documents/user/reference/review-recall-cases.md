---
docType: reference
project: squadron
dateCreated: 20261112
dateUpdated: 20261112
status: draft
---

# Review Recall Cases

Case records for [review-recall-runbook.md](review-recall-runbook.md). Review diff is `base..head`. Repos are local under `~/source/repos/manta/`.

Status: `verified` means the author confirmed the bugs against real command output. `checked` means each fix diff and the saved review were read by a separate read-only pass (20261112) against the validity rules below; it was not independently re-checked.

## What counts as a bug

A bug counts only if all hold:
1. The fix corrects a defect (wrong behavior, crash, wrong data). A fix that adds a capability, a gate, an option, or follows a later spec or contract change does not count.
2. The defective code was at `head` and was added or changed inside `base..head`.
3. The saved review of that head did not report it. If it did, it is a **control**: a reviewer that cannot find controls is not worth scoring on the rest.

## How these were found

For each `fix:` commit (trading-data and others since 2026-08-01, squadron since 2026-09-15; fixes whose message mentions a review were excluded), `git blame` the parent on the changed lines to find the commit that introduced them. A candidate needs that commit to be an ancestor of a saved code review's `reviewedSha`, within 40 commits of it, with the fix landing after. `base` is the parent of the earliest buggy commit, so a diff can include a few unrelated commits. Then the fix diffs were read against the rules above.

The miner over-reports: of 34 fixes read, 13 were unreported bugs and 3 were bugs the review had already reported. Typical false positives are fixes that add new behavior on reviewed lines, fixes of code that predates `base`, and fixes that follow a later contract change. Mine, then read; never score on mined output alone.

## Cases

### trading-data-307 — verified
- repo `trading-data`, base `dcfb86f1`, head `b5c3d781`.
- B1: the purchase script judged the whole `pass --estimate-only --json` payload as the plan summary; the plan is nested under `phases[purchase].summary`, so the first key lookup raised `KeyError`. `scripts/cutover_304_checks.py` (`judge_estimate`).
- B2: the judge required verdict `allowed`, but `--estimate-only` reports `estimate_only` whenever there is something to buy, so the buy step was unreachable.
- Proof: both fixed in `a7c5e36f`. Reviews: `project-documents/user/reviews/archive/307-review.code.futures-history-acquisition*.md`.

### trading-data-921 — checked (best case: three bugs)
- base `eaf1ab4e5913465369ad916785cce5974eaab08c`, head `9b54f27bdc6b62bca9890bc5006bbac73f2ea6bc` (5 commits, 24 files). Review: 921, CONCERNS, z-ai/glm-5.3. The review praised the per-session judging.
- B1 (`dc391881`): a session with no bar inside it after a long publication delay was always judged partial; the gap row stayed open and was re-requested every walk, burning quota and never converging. `minute_sessions.judge_chunk_by_sessions`, `minute.py _do_minute_symbol`.
- B2 (`b1c7f3b7`): the seed's truncated-day scan started at the 7-day floor, and the seed deletes unknown rows in its window, so truncated sessions older than 7 days were erased instead of fetched. `minute.py run_minute_cycle`.
- B3 (`f94c9e58`): the cutover started the firing with a blocking command, so its "trailing phase complete" stop could never act and the cutover sat for 2 hours. `cutover_common.fire_unit_until`.
- Excluded: `41d66d8e` (the defective predicate predates `base`), `33974743` and `660160ff` (spec change, and code predating `base`).

### trading-data-188 — checked
- base `0c6060f80be38524eb02585c44a481a9b6cdf453`, head `3e29c2afc500d786b26ee925efd0eb9269e18d52` (6 commits, 29 files, ~105k code chars). Review: 188, CONCERNS, claude-sonnet-5.
- B1 (`ec8be864`, moderate): the candle route filtered `end_period_ts` with inclusive bounds, so a whole-day query `start=D&end=D` dropped the day's last candle and gave it to the next day. `serve_timeseries._candle_window`, `windows.resolve_window`. The docs said "inclusive" before the fix, so some would call it a contract change.
- Excluded: `b8e2685b` (trades moved to half-open for consistency; the pre-fix docs said inclusive).

### trading-data-225 — checked
- base `09106ab48bda1b7397cfefa0145928a82e3056ac`, head `f328230d409b21ef1c9d8f8d96db21a478169076` (9 commits, 25 files). Review: 225, CONCERNS, deepseek/deepseek-v4.1-flash.
- B1 (`459ac7bd`): `raw_counts` counted `tick_trade` rows for all products over overlapping session windows with no filter on the product's instruments, inflating coverage counts when several products are loaded. `status_reads.raw_counts`.
- Excluded: `8a9c47ec` (head matched the slice's own spec; the fix followed a later spec).

### trading-data-227 — checked
- base `11168d5b2ae7805e15a63888eb85ca26b1fdc811`, head `85fee397cbbe12ca5b74bb38fb77cf1165b5ba1c` (7 commits, 18 files, ~102k code chars). Review: the copy under `reviews/archive/` (the one whose `reviewedSha` equals head), CONCERNS, claude-opus-5-5.
- B1 (`0ccf9b00`): `rclone backend lifecycle ... 2>&1` merged stderr into the JSON, so under sudo rclone's "config file not found" notice broke the `jq` parse and failed cutover step 2. `deploy/lib/b2_lifecycle.sh`. Specific to the sudo environment.
- Excluded: `ef2213b7` and `d14f8a60` (both present in `base`).

### amoeba-122 — checked
- repo `amoeba`, base `f8097604697cfefb5fb7313d29648a1c6c22b221`, head `e07f13739a5c7cd88c04fe2dffcc57b2a1eb5793` (51 files, ~174k code chars). Review: 122, CONCERNS, deepseek/deepseek-v4.1-flash.
- B1 (`a62043f`): `build_argv` emitted `sq run P4 --run-id X -p slice=N`; squadron rejects it ("requires a 'slice' argument"), so every dispatched run failed. `runner/launch.py build_argv`. Same shape-mismatch kind as 307.
- B2 (`43ba517`): the tick's unexpected-fault path returned `(COMPLETE, True)`, reporting work, so the host loop skipped its idle wait and a persistent fault spun at full speed. `runner/tenant.py RunnerTenant._tick_project`.
- Controls (reported by the review): malformed `issued_at` aborting the whole tick (`0514c62`, F003); fault on a node blocked on a non-human kind dropped (`66ee3c4`, F002).
- Excluded: `5d0ea2e` (code predates `base`).

### trading-ui-103 — checked (low confidence)
- repo `trading-ui`, base `a4f9b6cf446929d056689df48082a701467d74e7`, head `d56c493f769d429a40f9e8052eba04ad6254e8c2` (22 files). Review: 103, CONCERNS, deepseek/deepseek-v4-flash-0731.
- B1 (`f0ebfb4`, latent): the range effect gates on `seriesCountRef.current === 0` but its dependencies are `[mount.ready, chart, range]`, so a series added after the range settles never triggers `setVisibleRange`. `src/chart/use-chart-provider.ts`. Slice 103 never adds series, so the wrong behavior showed only after later work; a strict "observable at head" reading would exclude it.
- Control: the hook never re-mounting when the container ref resolves late (`e4632c1`, F001).
- Excluded: `eb74ef8` (fixes a flaw in `f0ebfb4`, code not in range).

### squadron-932 — checked (a PASS review)
- repo `squadron`, base `262d0ba064dcc6fa09efb5908eecc1447fd0582b`, head `d89cc060d2fe3033ed479d7e4eb69aadc779bd97` (27 commits, 62 files, ~143k code chars). Review: 932 (pipeline SDK session), PASS, sonnet-5-5.
- B1 (`5e384226`, #239): the dispatch ended once the result was in and the background-agent ledger was empty, but a completion notice arriving mid-turn cleared the agent from the ledger before the follow-up turn it triggers, so the dispatch returned early and lost a design artifact. `sdk_session.py SDKExecutionSession._collect_turns`, `sdk_turns.py BackgroundLedger`.
- The review's notes about an unrelated `TimeoutError` and a failed `disconnect()` are not hits.
- Excluded: `4df2035f` (new recovery capability).

### squadron-175 — checked
- base `3812c815b377eadfd7741ab1734c350c73789e2b`, head `1cbd6be4317f37498b07a31cd9cb64562fdb9d0a` (16 commits, 93 files, ~222k code chars). Review: 175 (usage and cost tracking), CONCERNS, sonnet-5-5.
- B1 (`0a850c0a`): `ResultMessage.total_cost_usd` is the CLI session's running total but was recorded as the step's cost, so later steps included earlier spend (one summary showed $5.35 instead of about $0.61). `sdk_turns.py DispatchTurns.fold_result`, `providers/sdk/agent.py _fold_result`, `usage.py`.
- Excluded: `29850399` and `fed05c66` (the reviewed code said it sent no effort; the fixes add that).

### squadron-197 — checked (borderline)
- base `e0dc580dc806b526ab6fa57ccc2d381ca9b7eece`, head `90a40dbf40289fd46b99e999c957a6e9295545be` (23 commits, 50 files, ~182k code chars). Review: the copy under `reviews/archive/` with that `reviewedSha`, CONCERNS, sonnet-5-5.
- B1 (`af50b937` and `366250ba`, #188; count as one bug): a slice merged into the target with unchecked task boxes still read as open in cf, so batch selection reselected it and item resume flagged its dependents; both read cf status only. `sources.py _cf_slices_ready_to_implement`, `item_resume.py _open_dependencies`, `_select_item`. Borderline: it could also be read as a new "trust git" behavior.
- Excluded: `e602d4e5`, `6ffa6fab`, `610f0bfa`, `593483ef` (new gates and options).

### Batch 2 (20261113): context-forge and trading-engine

Mined with `review-recall-results/miner/mine.py`; 27 leads tied to a saved review were read by three read-only agents against the rules above (`miner/batch*-checked.json`): 1 missed bug, 6 bugs the saved review had reported, 20 rejected (new capability, message-only, later spec, or code older than base). For scoring other reviewers, a bug the original review reported is still a real bug at head, so all seven count; the original review's result is kept per case so recall can be split by it.

- **context-forge-e984cea3** (reported by the saved review): base `2e9355acd2^`, head `3d1268e86a`, 4 commits, 15 files. documentHeadingKeys flips inFence on any line starting with ``` and ignores ~~~, indented and longer fences, so a required heading that appears only inside an example block counts as present. `packages/core/src/schema/sliceDesignValidator.ts documentHeadingKeys`. Fix `e984cea3cf`.
- **context-forge-afd8f74a** (reported by the saved review): base `1d4ccbf97f^`, head `ec7f752e96`, 12 commits, 31 files. A throw or timeout from checkoutReadiness during apply aborts the whole cf check --fix run and discards the per-view results, so commits already made in other checkouts are never reported. `packages/core/src/introspection/routedFixes.ts gateByReadiness (called from applyFixPlan)`. Fix `afd8f74a31`.
- **context-forge-e9597a5e** (missed by the saved review): base `a7286db992^`, head `1976437730`, 4 commits, 13 files. `cf validate frontmatter` run from a registered worktree validated the project root instead of the worktree, so explicit paths failed containment, were silently dropped, and the command reported a clean pass having checked nothing. `packages/cli/src/commands/validate.ts validateFrontmatterAction (`const { id } = await resolveProjectWorktree(...)`; `validateFrontmatterFiles(project.projectPath, ...)`)`. Fix `e9597a5eb2`.
- **trading-engine-6078e2bc** (reported by the saved review): base `7dd4748d05^`, head `6211cf1c16`, 13 commits, 20 files. as_real converted any Integral to float without an exactness check, so distinct REAL parameters above 2**53 (e.g. 2**53 and 2**53+1) bound to the same value and shared a run key. `src/manta_trading_engine/core_model/value_checks.py as_real`. Fix `6078e2bc58`.
- **context-forge-5e840ccb** (reported by the saved review): base `4d64f150f7^`, head `f8657488c9`, 5 commits, 25 files. createAdoptionResolver persisted adoption.state=in_progress before gathering the adoption facts, so a facts probe failure (e.g. non-ENOENT error from presentPaths/recognizeCi) left in_progress written for a build that produced no brownfield prompt. `packages/core/src/adoption/adoptionResolver.ts createAdoptionResolver (persistInProgress called before renderFacts)`. Fix `5e840ccb8b`.
- **context-forge-9006d54c** (reported by the saved review): base `527d3ba78c^`, head `291dabe401`, 12 commits, 58 files. dryRunInstall removed the sandbox with an unguarded fs.rmSync in finally, so a failed removal threw and replaced the install's own error. `packages/cli/src/ideInstall/dryRun.ts dryRunInstall (finally block)`. Fix `9006d54c5f`.
- **trading-engine-ccae5e35** (reported by the saved review): base `45472f7e1d^`, head `1b665d05e3`, 7 commits, 16 files. Market construction with a non-iterable session_calendars, unhashable adjustment_bases or unhashable source_bar_stamping raised a raw TypeError instead of InvalidMarketError. `src/manta_trading_engine/core_model/markets.py Market.__post_init__, _normalize_calendars, _normalize_bases`. Fix `ccae5e3527`.

## Dropped

- **squadron-913:** the fix (`cc34d3de`, #219) added new resume behavior; the reviewed commit was a lint change.
- **trading-ui-301:** the code matched the server contract at head; the fix (`42a2752`) followed a later contract change.
- **trading-engine-105, trading-engine-102:** the review had already reported the bug (105), or the fix answered a review (102).
- **trading-data-303 (scale cost, `8b2e11af`), 226, 223:** not read; see leads.

## Leads, not yet cases

- **trading-data-303**: `8b2e11af` cut futures read cost at manifest scale, found by a load test; likely out of reach for a diff review.
- **trading-data-226**: `63d2fc51` surfaces tick-loop failures; the review reported "thread-boundary and sampler error handling is partly silent", so it may be a control.
- **trading-data-223**: fixes `e0b66b39`, `a32c3841`, `19a89be3`; `a32c3841` also added the saved review, so what the review already reported is unclear.
- More of squadron's own history (the miner kept 117 non-review fixes; 9 were read).

## Totals

10 cases, 14 bugs (307: 2, 921: 3, 188: 1, 225: 1, 227: 1, amoeba-122: 2, trading-ui-103: 1, squadron-932: 1, squadron-175: 1, squadron-197: 1), 3 controls. Batch 2 adds 7 cases with one bug each (5 context-forge TypeScript, 2 trading-engine Python): 17 cases, 21 bugs. Batch 2 is not yet in any grid. The runbook asks for at least 8-12 cases before ranking configs.

Diff sizes matter for the PASS floor (`review.large_diff_chars`, default 100,000): 188, 227, amoeba-122, squadron-175, 197 and 932 are above it; 921, 225, trading-ui-103 are below; 307 is 97,780.
