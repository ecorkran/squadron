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
reviewedSha: 3a628691f4180671a08b990424c9873333835242
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 16
turns: 11
promptTokens: 401851
cachedTokens: 355584
completionTokens: 28505
reasoningTokens: 25519
durationSeconds: 117.8
runId: run-20261007-p4-72e6f5be
squadronVersion: 0.21.0
findings:
  - id: F001
    severity: pass
    category: nfr
    summary: "No NFR is stated for this path in 140, and the carried-forward target is restated explicitly"
    location: "project-documents/user/slices/174-slice.run-liveness-stall-bounds-pruning-and-readable-listings.md:635"
  - id: F002
    severity: pass
    category: architecture-alignment
    summary: "Component boundaries and dependency direction match the 140 architecture"
    location: "project-documents/user/slices/174-slice.run-liveness-stall-bounds-pruning-and-readable-listings.md#component-structure"
  - id: F003
    severity: concern
    category: error-handling
    summary: "Failure modes for the process check (`os.kill`) are only half-enumerated"
    location: "project-documents/user/slices/174-slice.run-liveness-stall-bounds-pruning-and-readable-listings.md:175"
  - id: F004
    severity: concern
    category: scope-and-failure-modes
    summary: "Unowned `running` runs are exempt from prune entirely, leaving the class of rows the slice exists to clear"
    location: "project-documents/user/slices/174-slice.run-liveness-stall-bounds-pruning-and-readable-listings.md#d9-prune-selection"
  - id: F005
    severity: note
    category: under-specification
    summary: "`RunHeartbeat`'s new-vs-resume claim branch is under-specified"
    location: "project-documents/user/slices/174-slice.run-liveness-stall-bounds-pruning-and-readable-listings.md#data-flow"
  - id: F006
    severity: note
    category: error-handling
    summary: "The foreground interrupt relies on an SDK-internal bound it does not wrap"
    location: "project-documents/user/slices/174-slice.run-liveness-stall-bounds-pruning-and-readable-listings.md#d7-foreground-stall"
---

# Review: slice — slice 174

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [PASS] No NFR is stated for this path in 140, and the carried-forward target is restated explicitly

The 140 architecture states no NFR for the listing, prune or run-state path (verified: the only performance-adjacent text is the deferred "SDK Client Warm Pool … reducing per-step latency"). The slice says so in Special Considerations and restates 199's advisory target with its specific value (`sq runs list --all` under 1 s with a few hundred run-state files, measured 0.67 s for 188 runs), plus the delta in cost this slice introduces (one `os.kill` per same-host running run, no new file reads, no extra definition loads). This satisfies the "restate the NFR with a specific target" criterion, since there is no parent NFR to inherit.

### [PASS] Component boundaries and dependency direction match the 140 architecture

New modules land in `pipeline/` (state, liveness, heartbeat, observer, prune) and `cli/`, with no new cross-layer edges: `run_liveness` is pure with injected `process_alive`, and listing/wait/prune all assess liveness through it so "orphaned" has one definition. The one architecture-level change — a second executor notification path (`RunObserver`) beside the 173 events dispatcher — is correctly identified as a divergence from the 140 "Events Dispatcher (173)" extension mechanism and is scheduled as an explicit paragraph addition to the architecture's Component Architecture section (D12, Implementation step 8). That is the right handling of an intentional divergence rather than silent drift. `sq runs prune` also lands inside 140's already-declared scope ("Old run pruning", slice 150), so it is not scope creep.

### [CONCERN] Failure modes for the process check (`os.kill`) are only half-enumerated

The design defines two outcomes for the process probe: `ProcessLookupError` means gone, `PermissionError` means alive. Every other `OSError` from `os.kill(pid, 0)` is unspecified, and an unhandled one propagates out of `process_alive` into `assess_liveness`, which is called on the listing, `wait` and prune paths — i.e. a corrupt or hand-edited `RunState` could turn a routine `sq runs list` into a traceback. The error-handling summary table (line ~147) has no row for "process check raised". Additionally, `pid` is read from a persisted file that nothing validates as positive: `os.kill(0, 0)` targets the caller's own process group and `os.kill(-N, 0)` targets process group N, both of which return "alive" and silently classify the run `LIVE` rather than flagging the file as malformed. Given the slice's own rule that liveness has exactly one definition and one policy, the non-`ProcessLookupError`/`PermissionError` branch and the non-positive-pid case need an explicit, stated outcome (fail loudly, or treat as non-conclusive → `STALE`), not an implicit one.

### [CONCERN] Unowned `running` runs are exempt from prune entirely, leaving the class of rows the slice exists to clear

D9 protects an `UNOWNED` `running` run "the same way" as a `LIVE` one: it is never a candidate, and naming it is refused (stderr line, exit 1). Combined with the Excluded item "Liveness for prompt-only runs … these runs are `UNOWNED`", a prompt-only run whose session died between `--next` and `--step-done` sits at `status: running` forever, matches no prunable category that survives protection (it may match `unavailable` if its pipeline was deleted, but protection drops it silently rather than refusing with a message), and cannot be removed by `sq runs prune` at all. That directly undercuts the slice's stated value ("The runs directory fills with rows nobody can act on"). The design records a follow-up issue for resuming orphaned runs, but none for this class. Either the exclusion needs a named, observable refusal path (not a silent drop) or a follow-up issue should be recorded alongside the resume-orphaned one in Implementation step 8.

### [NOTE] `RunHeartbeat`'s new-vs-resume claim branch is under-specified

D13 splits ownership writing by run kind — new runs get the owner from `init_run(owner=...)`, resumed (and item-resumed) runs get it from `RunHeartbeat`'s enter calling `StateManager.claim(run_id)` — and the component table describes `RunHeartbeat` as "claim on resume + heartbeat". The design never states how the context manager distinguishes the two cases, nor what `claim` does if it is entered for an already-owning new run (idempotent? refused?). Since `_run_pipeline_sdk` is the single call site for new, resumed and item-resumed runs, a `claim` invocation on the new-run path would rewrite a file the process already owns. A one-line statement of the discriminator and `claim`'s idempotence would close the ambiguity; no behavioural gap is visible in the Success Criteria.

### [NOTE] The foreground interrupt relies on an SDK-internal bound it does not wrap

The drain step is explicitly bounded by `INTERRUPT_DRAIN_TIMEOUT_S = 60`, but `await client.interrupt()` itself is left unguarded on the stated grounds that "the SDK bounds the request with its own 60 s timeout (`_internal/query.py:_send_control_request`)". That is a reasonable delegation, but it is the one await on this new I/O path with no bound owned by squadron, and the slice's whole purpose is eliminating unbounded foreground waits. A short note in D7 (or a task in step 4) confirming the SDK bound is observed in the step-1 spike — and adding a squadron-side wrapper if it is not — would remove the dependency on an undocumented internal.

### Run Digest

- Response length: 7050 chars
- Response is newline-free: no
- Tool calls made: 16
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 107932
- Effort: backend default
- Turns: 11
- Tokens — prompt / cached / completion / reasoning: 401851 / 355584 / 28505 / 25519
- Duration: 117.8 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
