---
docType: review
layer: project
reviewType: slice
slice: producer-only-replay-runner
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/424-slice.producer-only-replay-runner.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261104
dateUpdated: 20261104
reviewedSha: ef6d51a92bef416c09d60faee087b218920b0079
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 6
effort: high
turns: 7
promptTokens: 433552
cachedTokens: 330782
cacheWriteTokens: 102760
completionTokens: 12228
durationSeconds: 99.4
costUsd: 0.605113
costBasis: provider
squadronVersion: 0.24.22
findings:
  - id: F001
    severity: concern
    category: cost-bound
    summary: "Stated dollar bound is not an upper bound for Codex and unpriced configs"
    location: "project-documents/user/slices/424-slice.producer-only-replay-runner.md:243-258"
  - id: F002
    severity: concern
    category: architectural-boundary
    summary: "Per-replay sandbox removal and diff-only hand-off depart from the architecture and slice plan"
    location: "project-documents/user/slices/424-slice.producer-only-replay-runner.md#Integration Points (Provides to Other Slices, line 401) and #State Management (line 153)"
  - id: F003
    severity: concern
    category: error-handling
    summary: "Failure modes for the producer subprocess and diff capture are incompletely enumerated"
    location: "project-documents/user/slices/424-slice.producer-only-replay-runner.md:203 and #D10 (lines 266-282)"
  - id: F004
    severity: concern
    category: proportionality
    summary: "Surface beyond what the slice must deliver can be deferred"
    location: "project-documents/user/slices/424-slice.producer-only-replay-runner.md#Technical Scope (lines 32-40) and #Component Structure (lines 73-99)"
  - id: F005
    severity: note
    category: scope
    summary: "D9 changes shared SDK-session behavior for every capped run"
    location: "project-documents/user/slices/424-slice.producer-only-replay-runner.md#D9 (lines 260-264)"
  - id: F006
    severity: pass
    category: architecture-alignment
    summary: "Producer-only mechanism matches the architecture's \"no forked step or prompt\" rule"
    location: "project-documents/user/slices/424-slice.producer-only-replay-runner.md#D1-D3"
  - id: F007
    severity: pass
    category: architecture-alignment
    summary: "Containment, leak scan and absence classes follow the architecture"
    location: "project-documents/user/slices/424-slice.producer-only-replay-runner.md#D6-D7, #D10"
---

# Review: slice — slice 424

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Stated dollar bound is not an upper bound for Codex and unpriced configs

The architecture requires a bound stated before dispatch, with overshoot limited to "one per-pipeline cap". Both the bound and the cap check depend on a replay's cost staying near its per-replay cap.
- A producer-only run is one dispatch, so 947's check after each action cannot stop it partway (D9 says this).
- D9 enforces the cap in-dispatch for the SDK path only.
- For `sol` (`openai-oauth`) the bound output itself says cost is "checked after each dispatch, not inside it". A single Codex dispatch can then cost any amount, so "+ one replay of overshoot $1.50 → at most $41.50" is false for that config.
- For `luna`, which reports no cost, replays are not counted against the cap at all.

The headline "at most $X" therefore claims a bound it cannot give for a config the example itself includes. Either state those configs as outside the bound (a separate "unbounded: sol, luna" line, with the headline figure labelled as covering enforced configs only), or add an enforceable limit for them, such as a turn or wall-clock limit. D9 also leaves open whether the SDK budget is per query or per connection, though it is marked "decided".

### [CONCERN] Per-replay sandbox removal and diff-only hand-off depart from the architecture and slice plan

The architecture says the grade "comes from a separate step that runs after the producer finishes, in the same sandbox". The 425 plan entry repeats this. The slice removes the sandbox after each replay and states that 425 "rebuilds the tree from `start_sha` plus the diff". That is a design decision about 425's execution model, made here, and it is not flagged as a deviation.
- Every grade now needs a fresh environment install, which means network access and a possible lockfile failure.
- The producer's tree is not reproduced exactly (mode bits, files outside the diff).
- It adds a second harness failure path to 425.

The grader-reinstalls-on-dependency-change principle suggests rebuilding may be acceptable. If so, record it as a deliberate amendment to the architecture and plan, with its cost to 425. Otherwise keep the sandbox until grading, or hand off the tree itself.

### [CONCERN] Failure modes for the producer subprocess and diff capture are incompletely enumerated

The slice covers store-write failure, missing run state, an unreadable transcript, and Ctrl-C (through the interrupted status). Other paths on the new I/O are left implicit:
- **Hang:** "Stall bounds end a hang" (line 203) names no bound and says nothing about what a stall-killed replay records. D10 has no row for it, so it presumably falls to `producer_failed`, but the slice does not say so.
- **Subprocess killed by a signal:** the exit is not distinguished from a normal nonzero exit.
- **`git diff` or sidecar write failure after a successful producer run:** this is not in the D10 table, and a committed producer result would be lost or misclassified.
- **Overlapping rows:** `no_commit` includes "refused (for example `fix_report`)" and `producer_failed` is "any other failed run status". A `fix_report` failure is a failed run status, and the slice gives no precedence rule between the two.

Each needs an explicit outcome, with its absence class and an observable log or record, as the review rules require. Add the matching test cases to the D10 per-outcome test list.

### [CONCERN] Surface beyond what the slice must deliver can be deferred

The slice is large (11 new modules, 3 CLI subcommands with slash-command mirrors, effort 4/5). Items the 424 plan entry or the 425/426 hand-offs do not need yet:
- **`sq benchmark status` and `--json`:** the plan entry names only the run command, and records plus `replay-show` already make each replay inspectable. Defer `status` until 425's report exists. 425 will then own the cross-config view.
- **`CaseKindRunner` protocol:** it has one implementation. The 426 interface can be a plain function seam until a second kind exists. Keeping the protocol is defensible if the PM wants the "426 registers without editing `bench_runner.py`" criterion, but nothing uses it today.
- **Record fields no consumer reads yet:** `interrupted_at: tuple[datetime, ...]` and `seed_files`. `unpriced_replays` and the per-replay `cap_overshoot_usd` are partly covered by the bound output.

Cutting these narrows the slice without dropping anything the plan assigns to it.

### [NOTE] D9 changes shared SDK-session behavior for every capped run

In-dispatch `max_budget_usd` is not assigned to this slice by the plan, and it alters 947 cap semantics for all capped `sq run` use. It is justified here because a single-dispatch producer run is otherwise unbounded on the SDK path, and the slice acknowledges the blast radius and adds a CHANGELOG bullet. If it grows past a small change to `sdk_session.py`, it could be split out as a fix.

### [PASS] Producer-only mechanism matches the architecture's "no forked step or prompt" rule

Producer-only is a definition transform. The review key is stripped by each step type through `ProducerStep`, and a test compares the stripped step's actions with the full step's. The flag name and stop reporting are settled, which closes the slice plan's open item. `--from`, `--item` and `--flagged` are refused, and the reserved param keeps `--resume` producer-only. It consumes 423's `fix-context → dispatch → commit` step as stated there.

### [PASS] Containment, leak scan and absence classes follow the architecture

- The scan covers the paths the architecture lists: user checkout, installed site-packages, package-manager cache, the store, and `git`/`gh` against other repos. It adds the own-package rule for the network route 421 recorded.
- Verdicts are `leaked`, `no_leak_detected` or `scan_unavailable`, never "not leaked". An empty transcript is never read as clean.
- A leaked or unscannable run becomes a harness absence that drops the case from every config. Config-caused absences stay with the config.
- Transcripts come from the runtime's own files in the redirected home. Profiles with no transcript are refused at planning, and the transcript spike runs first as a `BLOCKED:` gate.
- Diffs are content-addressed sidecars verified by hash, and the replay record is small.
- Resume, interruption and orphan sweep match the plan.
- Both caps are required, and the bound is printed before any dispatch.

### Run Digest

- Response length: 7808 chars
- Response is newline-free: no
- Tool calls made: 6
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: high
- Turns: 7
- Tokens — prompt / cached / cache write / completion / reasoning: 433552 / 330782 / 102760 / 12228 / not computed
- Duration: 99.4 s
- Cost: $0.61 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7

## Responses

- **F001 (fixed):** The bound's headline now covers only configs capped inside the dispatch, and every other config (checked only after the dispatch, or unpriced) is listed under `not bounded`. D9 now sets the SDK budget once when the session opens; a replay is one dispatch, so per-query and per-connection give the same limit.
- **F002 (fixed):** Integration Points now records the rebuild as a deliberate departure from the architecture's "same sandbox" wording, with the reason and its cost to 425, which 425 D1 already accepts (`environment_changed`). The architecture text itself is outside this slice and is flagged for the PM.
- **F003 (fixed):** D5 names the existing hang bounds (SDK stall, `codex.turn_timeout_s`), D10 now has first-match-wins ordering, a signal-killed run maps to `no_run_state`, and a `git diff` or sidecar failure is a store write failure that stops the benchmark. The test list covers each.
- **F004 (fixed):** Cut `sq benchmark status`, `interrupted_at`, `seed_files` and `cap_overshoot_usd`. Kept `CaseKindRunner` because the integration requirement that 426 registers without editing `bench_runner.py` needs it, and `unpriced_replays` because the summary reports it.
- **F005 (noted):** The change stays to one option in `open_pipeline_session` plus the result mapping; if it grows it will be split out as a fix.
