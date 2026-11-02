---
docType: review
layer: project
reviewType: slice
slice: one-commit-per-planning-document-loops-collapse-their-own-round-commits
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/202-slice.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261101
dateUpdated: 20261101
reviewedSha: e50b3cc9da5f724bca1c8ec0ebc9135d035e074f
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 7
turns: 8
promptTokens: 588175
cachedTokens: 475239
cacheWriteTokens: 112920
completionTokens: 7300
durationSeconds: 64.4
costUsd: 0.573002
costBasis: provider
runId: run-20261101-p4-470d268f
squadronVersion: 0.24.12
findings:
  - id: F001
    severity: pass
    category: architectural-alignment
    summary: "Rewrite exception matches 180-arch's recorded carve-out"
    location: "project-documents/user/slices/202-slice.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md#D2 — `commit-tree` plus compare-and-swap `update-ref`"
  - id: F002
    severity: pass
    category: error-handling
    summary: "Failure modes are enumerated per git operation"
    location: "project-documents/user/slices/202-slice.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md#D6 — Collapse never changes the loop's status"
  - id: F003
    severity: concern
    category: error-handling
    summary: "No test is required to assert the observable signal"
    location: "project-documents/user/slices/202-slice.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md#Technical Requirements"
  - id: F004
    severity: concern
    category: integration
    summary: "Claim that `reviewedSha` stamps \"keep resolving\" is narrower than it reads"
    location: "project-documents/user/slices/202-slice.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md#Integration Requirements"
  - id: F005
    severity: note
    category: architectural-alignment
    summary: "\"Unpublished\" is defined as absent from remote-tracking refs only"
    location: "project-documents/user/slices/202-slice.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md#D3 — What \"provably ours\" means"
  - id: F006
    severity: note
    category: dependencies
    summary: "Declared dependencies understate what the design uses"
    location: "project-documents/user/slices/202-slice.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md:7"
  - id: F007
    severity: note
    category: proportionality
    summary: "Proportionality is acceptable; small cuts are available"
    location: "project-documents/user/slices/202-slice.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md#Technical Scope"
---

# Review: slice — slice 202

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Rewrite exception matches 180-arch's recorded carve-out

180-arch's Git-Mutating Steps section already records the slice 202 exception to "never force, reset". The conditions it lists are the target only, an unpublished recorded tail, an identical tree, a compare-and-swap on `HEAD`, and a backup ref. D2, D3 and D5 implement each one. D3.2 refuses on any non-target branch, which keeps the "never a slice branch" boundary. D7 and the Excluded list keep code loops out. The slice plan's items are all covered: loop-recorded shas, the phase commit, the refusal conditions, mechanism, message, resume reconstruction and a signal per refusal.

### [PASS] Failure modes are enumerated per git operation

D6 covers each step separately:
- A read-only check failure or timeout gives `git_failed`, with no write made.
- A `commit-tree` failure leaves at most an unreferenced object.
- A crash between the backup-ref write and the `HEAD` swap leaves a harmless ref.
- A `HEAD` swap timeout raises `GitStateUnknownError`, which stops the run.

This squares with the architecture's "when the repository state can't be verified, the run stops". The run stops only when a ref write may have happened. A CAS race is covered by the `refused` outcome.

### [CONCERN] No test is required to assert the observable signal

Success Criteria require one WARNING per refusal and one INFO on success. Project rules require each identified failure mode to be observable, with at least one test asserting the signal. The Technical Requirements say tests "branch on the enum and on git state, never on log text". They list a test for every `CollapseOutcome` but none that checks a log record. As written, the WARNING and INFO lines could go missing and every listed test would still pass. Fix: add at least one `caplog`-style assertion on the level and the reason (the shas involved) for a refusal and for a `git_failed`. Keep the enum-based assertions for logic.

### [CONCERN] Claim that `reviewedSha` stamps "keep resolving" is narrower than it reads

D5 and the Integration Requirements say the backup ref keeps `reviewedSha` stamps resolving, and only `sq review resolve` is tested. The backup ref keeps the objects alive. It does not make them reachable from `HEAD`. After collapse the round shas are no longer in `base..HEAD`. `src/squadron/pr/inputs.py:143-160` selects reviews by membership in `base..head`, and it skips an out-of-range sha with no warning. For planning reviews this probably doesn't matter, since design review files are committed on the target before a slice branch forks. But the design doesn't say so, and it tells slice 183 it has "no collapse-related work". Fix: add one line stating that range-membership consumers (`sq pr create`) are out of scope for planning documents, and that 183 must diff by sha rather than by `<sha>..HEAD`. Alternatively, add a check of those consumers to the integration criteria.

### [NOTE] "Unpublished" is defined as absent from remote-tracking refs only

D3.5 checks `refs/remotes` only. A local branch that contains a ledger commit, such as a slice branch forked during a pause, won't block collapse. That branch would then hold the old commits, and a later merge would bring them in alongside the collapsed one. The run lock and the pause-then-fork window make this unlikely. Widening the check to `git for-each-ref --contains <commits[0]>` over `refs/heads` and `refs/remotes`, excluding the target itself, is one more argument if you want it closed.

### [NOTE] Declared dependencies understate what the design uses

Frontmatter lists only 196. The design also relies on the 197 run lock (Risk mitigation), `resume_item` (D3 and the item-rerun criteria), and 176/915 resume (Prerequisites). All of these are complete, so there is no sequencing problem. The frontmatter and the slice plan's "Dependencies: none" are just inconsistent with the Prerequisites section.

### [NOTE] Proportionality is acceptable; small cuts are available

Each mechanism traces to a plan requirement or a rejected-alternative argument: the ledger, persistence for resume, the backup ref and CAS. The design could drop two things without losing a requirement:
- The long item-rerun narrative in Data Flow step 2 could shrink to "a rerun opens a fresh ledger".
- The Verification Walkthrough partly restates the Success Criteria.

Neither needs to block progress.

### Run Digest

- Response length: 6033 chars
- Response is newline-free: no
- Tool calls made: 7
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 8
- Tokens — prompt / cached / cache write / completion / reasoning: 588175 / 475239 / 112920 / 7300 / not computed
- Duration: 64.4 s
- Cost: $0.57 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
