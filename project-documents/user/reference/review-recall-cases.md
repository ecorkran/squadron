---
docType: reference
project: squadron
dateCreated: 20261112
dateUpdated: 20261112
status: draft
---

# Review Recall Cases

Case records for [review-recall-runbook.md](review-recall-runbook.md). The first section is `manta-digital/trading-data` (local `~/source/repos/manta/trading-data`); later sections name their repo. Review diff is `base..head`.

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

## Cases from other repos (mined 20261112, same method, since 2026-08-01)

Local repos under `~/source/repos/manta/`. `controls` are bugs the saved review did report; a reviewer that finds them shows it can find the easy ones.

### amoeba-122 — candidate
- repo `amoeba`, base `f8097604697cfefb5fb7313d29648a1c6c22b221`, head `e07f13739a5c7cd88c04fe2dffcc57b2a1eb5793` (15 commits, 173,979 code chars: over the PASS floor). Saved review: 122, CONCERNS, deepseek/deepseek-v4.1-flash.
- B1: the runner passed `-p slice=N` to `sq run`, which squadron rejects ("requires a 'slice' argument"); the slice is the positional target (`a62043f`, "found by the slice 125 live walkthrough"). Introduced in `90841a0` (detached launch and launch tracker). This is a producer/consumer shape mismatch, the same kind as trading-data-307.
- B2 (check first): a review the store refuses failed the whole ingest and repeated every tick (`5d0ea2e`); only part of the buggy code (`1da826e`) is in this range.
- Controls (reported by the review): a malformed `issued_at` aborting the whole tick (`0514c62`); an unexpected fault on a node blocked on a non-human kind recorded nowhere (`66ee3c4`).
- Not reported: B1.

### trading-ui-103 — candidate
- repo `trading-ui`, base `a4f9b6cf446929d056689df48082a701467d74e7`, head `d56c493f769d429a40f9e8052eba04ad6254e8c2` (7 commits, 92,642 code chars). Saved review: 103, CONCERNS, deepseek/deepseek-v4-flash-0731.
- B1: the visible range was not applied when the first series landed (`f0ebfb4`); a second range-seam fix followed (`eb74ef8`). Introduced in `0050c49`, `d20d3ce`.
- Control: the hook never re-mounting when the container ref resolves late (`e4632c1`); the review reported it.
- B1 is a UI timing bug; a diff-only review may not reach it. Keep the case anyway as a measure of that limit.

### trading-ui-301 — candidate
- repo `trading-ui`, base `e6aa7676af5c4f110dde58cdc94a22f6bc1dcf86`, head `f02809dbd640f98416ec2bf8ebb18af6abe58a0d` (4 commits, 69,960 code chars). Saved review: 301, CONCERNS, claude-sonnet-5-5.
- B1: Kalshi candles were selected into windows by something other than their open time (`42a2752`, 50 lines changed in code introduced by `c436a1a`). Same boundary-semantics family as trading-data-188 (`ec8be864`).
- Review reported: a 135-line function, a misleading error name, a schema `.and()` use. None about window selection.

### Cases from squadron (mined 20261112, fixes since 2026-09-15)

Fixes whose message or body mentions a review, concern or finding were excluded (they answer a review). Squadron diffs are large; only 913 is small. All code sizes below are in characters.

### squadron-913 — candidate (smallest case in the set)
- base `a90d5e01b12aad98a6c726e30e85bcad4acb57b8`, head `245b3aa349a23b238d2520abb75062abdcb09ea5` (1 commit, 33,295). Saved review: 913 (ruff rule set adoption), PASS, minimax. All findings were `pass`.
- B1: resuming a run did not restore earlier step results (`cc34d3de`, 2026-10-17).
- A PASS review followed by a real resume bug, in one commit. Best first run for checking the harness.

### squadron-932 — candidate
- base `262d0ba064dcc6fa09efb5908eecc1447fd0582b`, head `d89cc060d2fe3033ed479d7e4eb69aadc779bd97` (27 commits, 143,088). Saved review: 932 (pipeline SDK session), PASS, sonnet-5-5.
- B1: an unusable SDK session was not replaced and provider errors logged a traceback (`4df2035f`). The review's note "a failed disconnect in `_reconnect` does not mark the session unusable" may be a hit; read both before scoring.
- B2: SDK session dispatches did not end on the CLI idle state (`5e384226`, #239). The review's note "idle timeout can also catch an unrelated TimeoutError" is adjacent.

### squadron-175 — candidate
- base `3812c815b377eadfd7741ab1734c350c73789e2b`, head `1cbd6be4317f37498b07a31cd9cb64562fdb9d0a` (16 commits, 222,088). Saved review: 175 (usage and cost tracking), CONCERNS, sonnet-5-5.
- B1: SDK cost was charged as the session's running total instead of the delta (`0a850c0a`, 2026-10-15). Not reported.
- B2: the alias effort was not applied when opening the pipeline SDK session (`29850399`); B3: session effort not recorded on compaction (`fed05c66`).
- Review reported error-path logging, stats JSON output, pricing-warning dedupe, a broad exception tuple.

### squadron-197 — candidate
- base `e0dc580dc806b526ab6fa57ccc2d381ca9b7eece`, head `90a40dbf40289fd46b99e999c957a6e9295545be` (23 commits, 181,789). Saved review: a 197 (implementation batch) code review of this head, CONCERNS, sonnet-5-5 (a second 197 review of a different head, `19d83bf`, also exists).
- Six fixes landed after the review: item resume trusts git for merged slices and batch selection treats merged slices as complete (`366250ba`, `af50b937`, #188); refuse a slice merge with unchecked task items (`e602d4e5`); pause the run when the merge finds unfinished tasks (`6ffa6fab`); retry every flagged batch item with `sq run --resume --flagged` (`610f0bfa`); commit an interrupted batch edit before an item resume (`593483ef`).
- Many bugs in one case; decide which count after reading the review's findings against each diff.

### Checked and dropped
- **trading-engine-105:** the first review reported `as_real` rounding large integers, so `6078e2b` answered it; nothing was missed. Only a positive control.
- **trading-engine-102:** the only mined fix (`ccae5e3`) is "harden market validation and share type guards", likely a review answer; not read.

## Leads, not yet cases

- **303 (statistics and open-interest roll rule)**: `8b2e11af` cut futures read cost at manifest scale. A scale problem, found by a load test; likely out of reach for a diff review. Include only as a control for "performance defects".
- **226 (proof on existing data)**: `63d2fc51` surfaces tick-loop failures in the contention run, and the review already reported "thread-boundary and sampler error handling is partly silent". Use as a precision/overlap check: the review may count as a hit.
- **223 (tick archive adoption)**: several fixes (`e0b66b39`, `a32c3841`, `19a89be3`) but `a32c3841` also added the saved review, so it is unclear which bugs the review had already named. Read the review before using.
- **Squadron's own history** has not been mined. Run the same method on this repo once trading-data has been scored; squadron's review files carry `reviewedSha` too.

## Not yet done

- Reading each candidate's fix diff to confirm the one-line bug and the location.
- Checked 20261112: every file a fix changed appears in its case's `base..head` diff. That shows the files were in the review, not that the buggy lines were; blame placed the lines inside the range.
- Code diff size (`.py`, `.sh`, `.sql`, characters): 188 = 105,235; 227 = 102,377; 921 = 71,826; 225 = 58,403; 307 = 97,780. Cases above `review.large_diff_chars` (default 100,000) are subject to the PASS floor; the others are not.
