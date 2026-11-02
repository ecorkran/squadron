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
reviewedSha: 286e7505e795c61270f01b8d5d31b17c2649879f
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
turns: 5
promptTokens: 285252
cachedTokens: 184490
cacheWriteTokens: 100754
completionTokens: 3931
durationSeconds: 38.1
costUsd: 0.461558
costBasis: provider
runId: run-20261101-p4-470d268f
squadronVersion: 0.24.12
findings:
  - id: F001
    severity: concern
    category: architectural-boundary
    summary: "Collapse rewrites target history, which the architecture's git-mutating-step rules prohibit"
    location: "project-documents/user/slices/202-slice.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md#D2 — Mechanism: `commit-tree` plus compare-and-swap `update-ref`"
  - id: F002
    severity: concern
    category: error-handling
    summary: "Proof-check git failures continue the run, against the architecture's \"stop when state can't be verified\" rule"
    location: "project-documents/user/slices/202-slice.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md#D6 — Collapse never changes the loop's status"
  - id: F003
    severity: concern
    category: proportionality
    summary: "Design carries speculative and duplicated scope that can be trimmed"
    location: "project-documents/user/slices/202-slice.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md#Integration Points"
  - id: F004
    severity: note
    category: architecture-alignment
    summary: "Layering and dependency direction are correct"
    location: "project-documents/user/slices/202-slice.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md#Component Structure"
  - id: F005
    severity: pass
    category: error-handling
    summary: "Failure modes and observability are otherwise enumerated"
    location: "project-documents/user/slices/202-slice.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md#D3 — What \"provably ours\" means"
---

# Review: slice — slice 202

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Collapse rewrites target history, which the architecture's git-mutating-step rules prohibit

The architecture's "Git-Mutating Steps" section says these steps "never force, reset, delete a branch, push, or merge beyond one level." It also says commits "stage only what the step produced." Slice 202 moves the target's `HEAD` from the recorded chain to a new commit with a different parent (D2). That is a history rewrite of the integration target. It is functionally a reset, even though it uses `update-ref` and not `git reset`.

The slice's safeguards are real: the D3 proof chain, the compare-and-swap, the backup ref, and the refusal paths. But the slice never acknowledges that it deviates from a stated architectural invariant. It also doesn't say how the deviation is reconciled.

Either amend the architecture's git-mutating rules to name this one sanctioned exception, or state the exception in the slice. The exception is: "a loop may replace only its own recorded, unpublished, tail commits, and never forces or resets in the general sense." Without this, the architecture and the shipped behavior will contradict each other.

### [CONCERN] Proof-check git failures continue the run, against the architecture's "stop when state can't be verified" rule

The architecture says: "When the repository state can't be verified, the run stops rather than letting later work build on it." D6 stops the run only for `GitStateUnknownError`, and the only named source of that error is a timeout on the two `update-ref` calls. A failure or timeout in the read-only D3 checks (`rev-list`, `for-each-ref`, or reading `HEAD`) becomes `git_failed`, and the pipeline continues. No write has happened at that point, so continuing is probably safe. But the slice should say so explicitly, so the difference from the architecture rule is deliberate and not accidental.

Two related gaps in the failure-mode enumeration:
- A timeout in `commit-tree` isn't addressed. It is probably benign, since no ref has moved, but D2 and D6 don't state it.
- A crash between the backup-ref write and the `HEAD` swap leaves an orphan `refs/squadron/pre-collapse/<new>` pointing at a sha that never became `HEAD`. This is harmless, but the slice should say that no handling is needed.

Add one line to D6 covering each of these cases.

### [CONCERN] Design carries speculative and duplicated scope that can be trimmed

The mechanism is heavy for a "tidy the commit log" goal. It adds two new modules, a six-field persisted ledger, a ten-value `CollapseOutcome`, cross-resume carry-forward, and a legacy-state `no_ledger` path. Most of that serves the stated safety goal. These parts can be cut or deferred:
- **Speculative consumers.** "Supervisor and Amoeba can read collapse outcomes" and the `sq _collapse` wrapper for #145 are claims about slices that don't exist yet. The Excluded list already defers #145. Drop both from Integration Points.
- **Overlapping outcomes.** `no_ledger` and `unrecorded_commit` both come from the single `unprovable` flag (D3.1). Likewise `cas_failed` and `head_moved` differ only in when the race is detected. Collapse each pair into one outcome with a reason string, or justify keeping them separate.
- **Walkthrough steps 5 and 6.** They restate behavior that the real-git tests already cover (the published refusal) or that is plain git (cleanup). Keep steps 1–4.
- **Signing branch.** The `-S` handling for `commit.gpgsign` is a branch that nothing in the slice requires. Keep it only if the project signs commits.

### [NOTE] Layering and dependency direction are correct

- The new logic sits in `pipeline/loop_ledger.py` and `pipeline/loop_collapse.py`. It depends on existing 196 modules, `commit_message`, `commit_plan` and `git_utils`, and not the reverse.
- `executor.py` gains only call sites.
- The target comes from `read_integration_target`, so the architecture's strict target read is respected.
- Collapse is scoped by the `CommitSubject` enum, not by labels.
- The slice reuses `compose_message` and doesn't add a second message template.
- Excluding code loops matches the architecture's rule that code lands on the slice branch and merges back with `--no-ff`, so history collapse on that branch is not undertaken.

### [PASS] Failure modes and observability are otherwise enumerated

- Each refusal reason maps to a `CollapseOutcome`.
- Each outcome has a WARNING or INFO line and is recorded in state.
- The compare-and-swap handles races.
- Tests use real git repositories, including the CAS race, a published remote-tracking ref, and index preservation.
- No NFR from the parent architecture applies to this path.

### Run Digest

- Response length: 5641 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 5
- Tokens — prompt / cached / cache write / completion / reasoning: 285252 / 184490 / 100754 / 3931 / not computed
- Duration: 38.1 s
- Cost: $0.46 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5
