---
docType: reference
project: squadron
dateCreated: 20261112
dateUpdated: 20261112
status: draft
---

# Review Recall Cases

Case records for [review-recall-runbook.md](review-recall-runbook.md). Repo for all cases below: `manta-digital/trading-data` (local `~/source/repos/manta/trading-data`). Review diff is `base..head`.

Status: `verified` means the bug description was confirmed by reading the fix diff. `candidate` means found by mining (see "How these were found") and checked only against the fix commit message and the saved review's finding titles. Verify a candidate by reading its fix diff before its first run.

## How these were found

For each `fix:` commit since 2026-09-01 (excluding "address review" commits), `git blame` the parent on the lines the fix changed to find the commit that introduced them. A case needs: that commit is an ancestor of a saved code review's `reviewedSha` and within 40 commits of it, and the fix landed after the review. `base` is the parent of the earliest buggy commit, so a diff can include a few unrelated commits. The saved review's findings were then compared by title with the fix. The script is a throwaway; the method is the runbook's "Finding more cases".

## Cases

### trading-data-307 — verified
- base `dcfb86f1`, head `b5c3d781`
- B1: the purchase script judged the whole `pass --estimate-only --json` payload as the plan summary; the plan is nested under `phases[purchase].summary`, so the first key lookup raised `KeyError`. `scripts/cutover_304_checks.py` (`judge_estimate`).
- B2: the judge required verdict `allowed`, but `--estimate-only` reports `estimate_only` whenever there is something to buy, so the buy step was unreachable.
- Proof: both fixed in `a7c5e36f`. Archived reviews: `project-documents/user/reviews/archive/307-review.code.futures-history-acquisition*.md`.

### trading-data-188 — candidate
- base `0c6060f80be38524eb02585c44a481a9b6cdf453`, head `3e29c2afc500d786b26ee925efd0eb9269e18d52` (6 commits). Saved review: 188, CONCERNS, claude-sonnet-5.
- B1: Kalshi candle windows were not half-open on period opens (`ec8be864`, refs #61 point 4). `api_server/routes/windows.py`, `kalshi_timeseries.py`.
- B2: Kalshi trade windows had the same boundary problem (`b8e2685b`, #68).
- Review reported: positional row indices, duplicated helpers, a name, a type. Nothing about window boundaries.

### trading-data-921 — candidate
- base `eaf1ab4e5913465369ad916785cce5974eaab08c`, head `9b54f27bdc6b62bca9890bc5006bbac73f2ea6bc` (5 commits). Saved review: 921, CONCERNS, z-ai/glm-5.3.
- B1: an empty session after the provider's publication lag was treated as truncated and re-asked forever instead of recorded as `PROVIDER_HOLE` (`dc391881`, #22). `data/acquisition/daemon/minute.py`, `minute_sessions.py`.
- B2: both truncation predicates required a bar inside the session, so a session whose only bar was the prior day's after-hours bar was invisible; 59,276 symbol-days affected (`41d66d8e`, #22). `data/gaps/repair_921.py`.
- B3: firing time and the measured 16 h publication lag (`33974743`, #22).
- Review reported: "trailing phase complete" logged when aborted, cutover log omits acceptance numbers, journal format coupling, a crashed pass exits 0. None of B1-B3. Highest-value case: three real bugs, each found in operation.

### trading-data-225 — candidate
- base `09106ab48bda1b7397cfefa0145928a82e3056ac`, head `f328230d409b21ef1c9d8f8d96db21a478169076` (9 commits). Saved review: 225, CONCERNS, deepseek/deepseek-v4.1-flash.
- B1: `caught_up()` judged every session in scope, including sessions another tier's units touch outside the wanted range, so status could never read caught up (`8a9c47ec`). `data/tick/tick_status_build.py`.
- B2: tick coverage raw counts included other products' instruments (`459ac7bd`). `data/tick/status_reads.py`.
- Review reported a nearby item: "a calendar that simply lacks coverage is reported as a storage outage". Count that as adjacent, not a hit, unless the diff shows it is B1.

### trading-data-227 — candidate
- base `11168d5b2ae7805e15a63888eb85ca26b1fdc811`, head `85fee397cbbe12ca5b74bb38fb77cf1165b5ba1c` (7 commits). Saved review: 227, CONCERNS, claude-opus-5-5 (and a sonnet re-run in the archive).
- B1: the 59-minute kill on the hourly WAL push restarted the archive scan, so a catch-up could never finish (`ef2213b7`). `deploy/cron.d/manta-trading-backup`, `deploy/lib/render_cron.sh`.
- B2: `archive_command` was not persisted on a cluster that never archived (`d14f8a60`).
- B3: rclone stderr leaked into the B2 lifecycle rule parse (`0ccf9b00`).
- Review reported six concerns (provisioning drops the 226 database, reconcile after a skipped run, silent production URL, ...). None of B1-B3.

## Leads, not yet cases

- **303 (statistics and open-interest roll rule)**: `8b2e11af` cut futures read cost at manifest scale. A scale problem, found by a load test; likely out of reach for a diff review. Include only as a control for "performance defects".
- **226 (proof on existing data)**: `63d2fc51` surfaces tick-loop failures in the contention run, and the review already reported "thread-boundary and sampler error handling is partly silent". Use as a precision/overlap check: the review may count as a hit.
- **223 (tick archive adoption)**: several fixes (`e0b66b39`, `a32c3841`, `19a89be3`) but `a32c3841` also added the saved review, so it is unclear which bugs the review had already named. Read the review before using.
- **Squadron's own history** has not been mined. Run the same method on this repo once trading-data has been scored; squadron's review files carry `reviewedSha` too.

## Not yet done

- Reading each candidate's fix diff to confirm the one-line bug and the location.
- Checked 20261112: every file a fix changed appears in its case's `base..head` diff. That shows the files were in the review, not that the buggy lines were; blame placed the lines inside the range.
- Code diff size (`.py`, `.sh`, `.sql`, characters): 188 = 105,235; 227 = 102,377; 921 = 71,826; 225 = 58,403; 307 = 97,780. Cases above `review.large_diff_chars` (default 100,000) are subject to the PASS floor; the others are not.
