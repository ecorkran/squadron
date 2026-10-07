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
reviewedSha: 4e9f2a180945c24cb03869b79bbfd96a991601b2
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 1
turns: 2
promptTokens: 31766
cachedTokens: 9600
completionTokens: 5233
reasoningTokens: 4005
durationSeconds: 21.9
runId: run-20261007-p4-72e6f5be
squadronVersion: 0.21.0
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "`sq pipelines show` file-read failure mode not enumerated"
    location: "project-documents/user/slices/174-slice.run-liveness-stall-bounds-pruning-and-readable-listings.md#error-handling-summary"
  - id: F002
    severity: concern
    category: integration
    summary: "Frontmatter dependencies omit 173, which the body lists as a prerequisite"
    location: "project-documents/user/slices/174-slice.run-liveness-stall-bounds-pruning-and-readable-listings.md#prerequisites"
  - id: F003
    severity: note
    category: architectural-alignment
    summary: "`RunObserver` is a new executor notification path not described in the architecture"
    location: "project-documents/user/slices/174-slice.run-liveness-stall-bounds-pruning-and-readable-listings.md#d12-one-executor-observer-separate-from-events"
  - id: F004
    severity: note
    category: error-handling
    summary: "Heartbeat/progress write failures are enumerated only for `OSError`"
    location: "project-documents/user/slices/174-slice.run-liveness-stall-bounds-pruning-and-readable-listings.md#d6-heartbeat-failure"
  - id: F005
    severity: note
    category: nfr
    summary: "Listing performance target is restated correctly, but no architecture-level NFR exists to inherit"
    location: "project-documents/user/slices/174-slice.run-liveness-stall-bounds-pruning-and-readable-listings.md#special-considerations"
---

# Review: slice — slice 174

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [CONCERN] `sq pipelines show` file-read failure mode not enumerated

`sq pipelines show <name>` resolves the pipeline and then prints the file text "byte for byte" (Implementation Details / API Contracts). This is a new I/O path — a definition-file read — but the "Error handling summary" table enumerates no row for it. The only documented failure is "not found" (loader message, exit 1). A file that exists at resolution time but is unreadable (permissions, deleted between resolve and read, non-UTF-8 content, race with a rebuild) is not covered, so the required explicit-handling-vs-"TBD" rule is not satisfied for this path. The new I/O paths that *are* covered (heartbeat writes, observer progress writes, prune deletes) show the intended standard; show should meet it too.

### [CONCERN] Frontmatter dependencies omit 173, which the body lists as a prerequisite

Frontmatter declares `dependencies: [150, 156, 199, 932]`, but the "Prerequisites" section lists five entries, including "**173 (complete):** the events dispatcher (`squadron.events`, `run_event`)" and explains why the slice does not use it. Either 173 is a real dependency (and belongs in frontmatter) or it is context, not a prerequisite, and should be moved out of "Prerequisites." Integration-point bookkeeping in the slice plan depends on this list being accurate.

### [NOTE] `RunObserver` is a new executor notification path not described in the architecture

D12 replaces `on_step_complete` with a `RunObserver` protocol and adds `step_started`/`item_started` notifications, driven from the executor's step loop and `each` loop. The 140 architecture documents the events dispatcher (173) as the executor's extension mechanism at the action-execution site and does not describe an in-process observer protocol. D12 gives a solid four-point justification for keeping bookkeeping off the event path (manifest dependency, failure coupling, per-fire cost, async/sync mismatch), so this reads as an intentional local choice rather than a boundary violation — but the architecture is silent on it, so the record should note that a second, non-event notification mechanism now sits alongside the documented one.

### [NOTE] Heartbeat/progress write failures are enumerated only for `OSError`

D6 handles an `OSError` from a heartbeat write (WARNING, run continues) and applies the same to `observer.step_started`/`item_started`. A non-`OSError` failure (e.g. a serialization/validation error on the rewritten JSON) is not enumerated. The run would still surface as `STALE` after the stale window, so the outcome is arguably observable, but the error-handling table does not say so for this class of failure; worth one line to close the enumeration.

### [NOTE] Listing performance target is restated correctly, but no architecture-level NFR exists to inherit

The slice restates the "`sq runs list --all` under 1 s … measured at 0.67 s for 188 runs" target and explains how 174 changes listing cost (no new file reads, one `os.kill` per same-host running run, cached pipeline loads). This is the correct handling of the restated-NFR rule. I confirmed the parent architecture document (140-arch.pipeline-foundation.md) states no latency/throughput NFR for the listing or dispatch paths, so there is no architecture-level target being violated or silently dropped here — the inherited target is 199's, and the slice carries it forward accurately.

### Run Digest

- Response length: 4979 chars
- Response is newline-free: no
- Tool calls made: 1
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 17353
- Effort: backend default
- Turns: 2
- Tokens — prompt / cached / completion / reasoning: 31766 / 9600 / 5233 / 4005
- Duration: 21.9 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5
