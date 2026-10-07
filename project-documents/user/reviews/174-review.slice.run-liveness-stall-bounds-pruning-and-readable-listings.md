---
docType: review
layer: project
reviewType: slice
slice: run-liveness-stall-bounds-pruning-and-readable-listings
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/174-slice.run-liveness-stall-bounds-pruning-and-readable-listings.md
aiModel: deepseek/deepseek-v4.1-flash
status: complete
dateCreated: 20261007
dateUpdated: 20261007
reviewedSha: 327d88a9713675d6bd9167814012946358ce07e6
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 34
turns: 20
promptTokens: 1033944
cachedTokens: 855680
completionTokens: 61435
reasoningTokens: 57057
durationSeconds: 252.9
runId: run-20261007-p4-72e6f5be
squadronVersion: 0.21.0
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Crash window between `init_run` and `claim` still leaves a permanently-`running` run"
    location: "project-documents/user/slices/174-slice.run-liveness-stall-bounds-pruning-and-readable-listings.md:220"
  - id: F002
    severity: concern
    category: error-handling
    summary: "`sq runs wait` trusts `HEARTBEAT_STALE` as terminal while prune explicitly does not"
    location: "project-documents/user/slices/174-slice.run-liveness-stall-bounds-pruning-and-readable-listings.md:273"
  - id: F003
    severity: note
    category: over-engineering
    summary: "A third executor observer hook is added without relating it to the events dispatcher"
    location: "project-documents/user/slices/174-slice.run-liveness-stall-bounds-pruning-and-readable-listings.md:139"
  - id: F004
    severity: note
    category: over-engineering
    summary: "The listing path's stated performance target is not restated although 174 changes its cost"
    location: "project-documents/user/slices/174-slice.run-liveness-stall-bounds-pruning-and-readable-listings.md#success-criteria"
  - id: F005
    severity: pass
    category: error-handling
    summary: "Failure modes for every new I/O path are enumerated with explicit handling"
    location: "project-documents/user/slices/174-slice.run-liveness-stall-bounds-pruning-and-readable-listings.md:316"
  - id: F006
    severity: pass
    category: other
    summary: "Boundaries and dependency direction are preserved, and scope matches the plan entry"
    location: "project-documents/user/slices/174-slice.run-liveness-stall-bounds-pruning-and-readable-listings.md#component-structure"
---

# Review: slice — slice 174

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [CONCERN] Crash window between `init_run` and `claim` still leaves a permanently-`running` run

D3 classifies a `running` run with `owner is None` as `UNOWNED`, and the design states UNOWNED runs "keep today's behaviour everywhere: listed as `running`, waited on, never pruned as orphaned." But `owner` is written by `StateManager.claim()` inside `RunHeartbeat`, not by `init_run` — `state.py`'s `init_run` writes `status=RUNNING_STATUS` with no owner. A process that dies (or is killed) in the window between `init_run` and `claim` therefore produces a v5 file that reads `UNOWNED`, i.e. exactly the symptom issue #190 exists to remove: `sq runs wait` never returns, `sq runs list` shows `running`, and `sq runs prune` can never select it. The Success Criteria explicitly preserve the v4 behaviour ("A v4 `running` file lists as `running` (`UNOWNED`), and `wait` keeps waiting on it"), so the residual hole is deliberate for old files but is not distinguished from a new v5 file whose owner was never written. This is the slice's primary stated value ("A crashed run shows as `orphaned` instead of `running`") failing for a window that the design itself creates. Either `claim` belongs in `init_run` for the SDK path, or the v5-with-no-owner case needs a distinct, handled outcome rather than inheriting the v4 exemption.

### [CONCERN] `sq runs wait` trusts `HEARTBEAT_STALE` as terminal while prune explicitly does not

The prune selection rule deliberately excludes `HEARTBEAT_STALE` orphans from the default set, and the Risk Assessment justifies that with "a synchronous call that blocks the loop for longer than 10 heartbeat intervals (300 s by default) makes a live run read as orphaned." D8, by contrast, has `wait_for_run` end the wait with `WaitOutcome.ORPHANED` and exit 8 on "`ORPHANED`" without distinguishing the reason — the same verdict the design judged too unreliable to act on destructively. The consequence is on the consumer the slice names as its audience: "an agent that started a run in the background can tell 'still working' from 'dead' with one command and an exit code" would be told a live (merely blocked) run is dead. The two readers need one trust policy, or `wait` needs to distinguish `PROCESS_GONE` from `HEARTBEAT_STALE` the way prune does. The error-handling table also does not carry a row for this divergence, so it is not visible as a decision.

### [NOTE] A third executor observer hook is added without relating it to the events dispatcher

`execute_pipeline` gains `on_progress` beside `on_step_complete`, while `140-arch` describes the events dispatcher (173) as a third registry firing at "the executor's single action-execution site." `on_progress` is internal and liveness-specific, and the design is clear that events are separate machinery, so this is defensible — but with three parallel hooks at the executor, it is worth stating in the slice that `on_progress` is not an event binding and will not grow a fourth sibling.

### [NOTE] The listing path's stated performance target is not restated although 174 changes its cost

`140-arch` sets no NFR for this path, so nothing is being omitted from the parent document. 199, however, documents an advisory target ("under 1 s for `sq runs list --all` with a few hundred run-state files") plus a call-count bound test, and 174 adds per-running-run liveness assessment, moves running rows into the default view, and changes `list_run_summaries` to return `RunListing`. 174's Success Criteria contain no performance criterion and no equivalent call-count bound for the added work. Restating or explicitly deferring the target would keep the invariant auditable.

### [PASS] Failure modes for every new I/O path are enumerated with explicit handling

Heartbeat write `OSError` (WARNING, run continues, later observed as `HEARTBEAT_STALE`), fatal `claim`, process death, blocked event loop, foreground silence, interrupt/drain failure (ERROR + `unusable_reason`, later calls fail fast via `_require_usable`), prune delete `OSError` (log, continue, exit 1), live/unowned refusal, and the unavailable-pipeline summary line all have a named outcome and observable signal — no "TBD". D7 additionally covers the peer-side cases the criterion calls for: drain timeout and stream-end mid-turn both set `unusable_reason` and produce a failed `ActionResult` rather than a hang, and the drain bound (`INTERRUPT_DRAIN_TIMEOUT_S = 60`) is defined once and matched to the SDK's own control-request bound.

### [PASS] Boundaries and dependency direction are preserved, and scope matches the plan entry

The new modules sit where the architecture places them: `run_liveness`, `run_heartbeat`, `run_prune` in `pipeline/`, `cli/columns` as a CLI-layer renderer, `runs`/`pipelines` under `cli/commands`. `cli/commands/*` → `cli/run_views` → `cli/columns` and `pipeline/*` is unchanged from 199. `run_liveness` is pure apart from the injected `process_alive`, and listing, wait and prune all read the single `assess_liveness` definition, so "orphaned" has one source. `dispatch` continues to own provider-error mapping. The added surface (`prune`, `pipelines show`, listing rework) is exactly items (c)–(f) of 140-slices #174, with the deferrals (#192 `--json`, #191 status enum, resuming orphaned runs) recorded as Excluded and filed as issues.

### Run Digest

- Response length: 6776 chars
- Response is newline-free: no
- Tool calls made: 34
- Tool calls failed: 2
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 240092
- Effort: backend default
- Turns: 20
- Tokens — prompt / cached / completion / reasoning: 1033944 / 855680 / 61435 / 57057
- Duration: 252.9 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
