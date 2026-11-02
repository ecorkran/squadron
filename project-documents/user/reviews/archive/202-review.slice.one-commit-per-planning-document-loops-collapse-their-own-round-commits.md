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
reviewedSha: 0ec9c7fe1d9a466cf17668c7a84d0e0c2ab4e9c8
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 107874
cachedTokens: 11162
cacheWriteTokens: 96708
completionTokens: 3705
durationSeconds: 33.2
costUsd: 0.425773
costBasis: provider
runId: run-20261101-p4-470d268f
squadronVersion: 0.24.12
findings:
  - id: F001
    severity: concern
    category: architectural-boundary
    summary: "Overrides an architecture rule without amending the architecture"
    location: "project-documents/user/slices/202-slice.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md#D2 — Mechanism: `commit-tree` plus compare-and-swap `update-ref`"
  - id: F002
    severity: concern
    category: integration
    summary: "Item-resume path from 197 is not specified"
    location: "project-documents/user/slices/202-slice.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md#Data Flow"
  - id: F003
    severity: concern
    category: proportionality
    summary: "Proportionality: more mechanism than the requirement needs"
    location: "project-documents/user/slices/202-slice.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md#Technical Scope"
  - id: F004
    severity: note
    category: scope
    summary: "Scope is not listed in the architecture's in-scope list"
    location: "project-documents/user/slices/202-slice.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md#Overview"
  - id: F005
    severity: note
    category: risk
    summary: "Concurrency mitigation can cite the architecture's run lock"
    location: "project-documents/user/slices/202-slice.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md#Risk Assessment"
  - id: F006
    severity: pass
    category: error-handling
    summary: "Failure modes enumerated for the new git I/O paths"
    location: "project-documents/user/slices/202-slice.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md#D6 — Collapse never changes the loop's status"
  - id: F007
    severity: pass
    category: architecture-alignment
    summary: "Dependency direction and layering are correct"
    location: "project-documents/user/slices/202-slice.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md#Component Structure"
---

# Review: slice — slice 202

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Overrides an architecture rule without amending the architecture

180-arch (Git-Mutating Steps) says these steps "never force, reset, delete a branch, push, or merge beyond one level." D2 acknowledges that moving the target's HEAD to a differently-parented commit is a reset in effect. It declares itself "the one sanctioned exception." A slice document can't grant an exception to a rule the architecture owns. Nothing in the slice plan or the architecture records the sanction. The architecture's "Git-Mutating Steps" section should gain the carve-out (a loop may replace only its own recorded, unpublished, same-tree tail through a compare-and-swap). Otherwise 202 contradicts its parent, and later slices will read the unqualified rule. The carve-out should also say it applies to the target only. D6 correctly keeps the "run stops when state can't be verified" rule, so that part is fine.

### [CONCERN] Item-resume path from 197 is not specified

The architecture says 197 adds `sq run --resume <run_id> --item N --decision retry|accept`, which reruns one flagged item of a finished batch. It also says a failed item can leave the checkout on the item's slice branch until the next `branch enter` returns it to the target. The slice's resume story (Data Flow step 2, State Management) covers only `start_from` and `--decision accept` on a paused loop. It does not say whether the ledger is carried through an `--item N` resume. That matters for `tasks-plan` and `slices-plan` batches, where items run inside `each`. It also doesn't say what the `off_target` check does if the checkout is still on a slice branch. The `off_target` refusal would be safe, but the design should state the outcome so the 197 interface stays predictable. Add one sentence on `--item` resume, plus an explicit test case.

### [CONCERN] Proportionality: more mechanism than the requirement needs

The requirement is one commit per planning document. The design adds:
- A persisted ledger with six fields and an eight-value outcome enum.
- Two new modules.
- A five-step proof chain.
- A backup ref for every collapse.
- A resume carry-forward with an `unprovable` legacy-state path.
- Message recomposition from a diff (D4).

Several of these overlap, and some could be cut or deferred:
- D3.4 re-derives the exact commit chain with `rev-list`. That makes the ledger's recorded shas a second proof of the same fact. Either the ledger or the chain check should be the proof, not both. A lighter option is to drop persistence, treat a resumed loop as `unprovable`, and collapse only within a single uninterrupted execution. That loses the paused-then-accepted case, which the success criteria require. If that case matters, keep the ledger and drop the `rev-list` equality check down to `HEAD == commits[-1]` plus the merge check.
- The `StepResult` and `StepState` ledger field is added mainly to record outcomes. The log line already gives an observable signal, so recording `outcome` in state could be deferred.
- Recomposing the message (D4) needs `git diff --name-status` plus review-verdict parsing. The simpler option is to reuse the final round commit's message, which already carries the latest verdict, and rewrite only the verb when the phase commit is included. The slice rejects the "first commit's message" option but doesn't consider the "last commit's message" option.
- The `unprovable` reason split (legacy state versus unreadable sha) and the fine-grained refusal enum are speculative. `git_failed` and a single `not_provable` reason would serve the one WARNING line.

### [NOTE] Scope is not listed in the architecture's in-scope list

The architecture's Scope Boundaries and the 194–197 batch-pipeline list don't mention planning-commit history collapse. The slice does fit under "Git-Mutating Steps" and the "Commits stage only what the step produced" principle. When the finding above is addressed, add this slice to the architecture's list of engine-level slices so the rationale for a 180-band slice is traceable.

### [NOTE] Concurrency mitigation can cite the architecture's run lock

The risk section frames concurrent commits to the same branch as the main hazard. The architecture's per-checkout run lock (197) already allows only one git- or cf-mutating run at a time. The compare-and-swap remains the right defense against an operator's manual commit. The mitigation text should state that the run lock covers the squadron-versus-squadron case. That keeps the stated risk accurate.

### [PASS] Failure modes enumerated for the new git I/O paths

Each new git call is classified:
- Read-only checks and `commit-tree` failures or timeouts become `git_failed`, which is logged at WARNING, with no ref moved.
- A crash between the backup-ref write and the HEAD swap leaves a harmless ref.
- A timeout on either `update-ref` raises `GitStateUnknownError`, which stops the run. This matches the architecture's "stop when state can't be verified."
- A refused compare-and-swap is `head_moved`.

Each outcome has an observable signal and a required test, which satisfies the failure-mode enumeration rule.

### [PASS] Dependency direction and layering are correct

The executor gains call sites only. The new modules depend downward on the 196 message composer, the commit-plan helpers and `run_git`. Nothing depends on the new modules, so the slice provides no interfaces to others. The target is read strictly through `read_integration_target`, as the architecture requires. Code loops are excluded, which preserves "code lands on the slice branch and merges back with `--no-ff`."

### Run Digest

- Response length: 7194 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 3
- Tokens — prompt / cached / cache write / completion / reasoning: 107874 / 11162 / 96708 / 3705 / not computed
- Duration: 33.2 s
- Cost: $0.43 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
