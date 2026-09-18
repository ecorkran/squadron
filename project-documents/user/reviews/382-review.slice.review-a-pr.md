---
docType: review
layer: project
reviewType: slice
slice: review-a-pr
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/382-slice.review-a-pr.md
aiModel: claude-sonnet-5
status: complete
dateCreated: 20260913
dateUpdated: 20260913
reviewedSha: a8c745acac38bb212bc54a6445394973431d076a
findings:
  - id: F001
    severity: pass
    category: alignment
    summary: "Two-root split correctly closes the gap the plan didn't express"
    location: "project-documents/user/slices/382-slice.review-a-pr.md:136-165"
  - id: F002
    severity: pass
    category: security
    summary: "Untrusted-settings risk closes a real gap the architecture didn't foresee, without contradicting it"
    location: "project-documents/user/slices/382-slice.review-a-pr.md:237-274"
  - id: F003
    severity: concern
    category: error-handling
    summary: "Submodule fetch during worktree creation is unbounded network I/O with no named hang/timeout signal"
    location: "project-documents/user/slices/382-slice.review-a-pr.md:174-177"
  - id: F004
    severity: note
    category: documentation
    summary: "Worktree location diverges from the architecture's literal wording without going through the scope-correction mechanism"
    location: "project-documents/user/slices/382-slice.review-a-pr.md:169-170"
---

# Review: slice — slice 382

**Verdict:** CONCERNS
**Model:** claude-sonnet-5

## Findings

### [PASS] Two-root split correctly closes the gap the plan didn't express

D1/D2 give `AgentConfig.convention_root` a precise meaning (jail root vs. convention root) that matches the architecture's "Which tree rules load from" principle (380-arch:243-250) exactly, and D2 backs the "no split needed for the diff range" claim with a design-time probe rather than an assumption, consistent with the project's no-guessing rule.

### [PASS] Untrusted-settings risk closes a real gap the architecture didn't foresee, without contradicting it

D8 extends the architecture's "Isolated checkout for tool-enabled reviews" and "Never surprise the operator" principles (380-arch:73-75, 114-117) to a threat (attacker-planted `.claude/settings.json` hooks) the architecture text never names. The fix is scoped per-invocation rather than as a template edit, correctly preserving `sq review code`'s legitimate use of `[project]` — no boundary violation.

### [CONCERN] Submodule fetch during worktree creation is unbounded network I/O with no named hang/timeout signal

D3 states `git worktree add` is "bounded by the git timeout," but the following sentence about `git submodule update --init --recursive` only says a submodule "that cannot be fetched fails the review naming it" — it never states this call is bounded by the same timeout, and unlike the lock-file and worktree-removal failure modes (which each name an explicit WARNING log line, per lines 182-183 and 191-192), no log level or metric is named for a submodule fetch that hangs rather than cleanly fails. Submodule init is real network I/O against a third-party remote (a private submodule needing credentials the operator's `gh` doesn't provide is called out in Risk Assessment line 384 as a *failure* case, but not as a *hang* case). The parent architecture's own failure-mode principle (380-arch:121-128) requires each new I/O path's hang/timeout/disconnect behavior to be enumerated with an observable signal and a test; the Testing section (382-slice:409-412) lists "create, lock, sweep..., remove on success/failure/timeout" but no test exercises a submodule fetch that hangs. Recommend naming the observable signal (log level) for a submodule-fetch timeout explicitly and adding it to the test list, the same way the lock and removal paths already do.

### [NOTE] Worktree location diverges from the architecture's literal wording without going through the scope-correction mechanism

380-arch:212 says the scratch worktree is "created under squadron's data directory"; this slice places it under `~/.config/squadron/worktrees/` and argues `data_dir()` is "package data and is the wrong home" (382-slice:169-170). The reasoning is sound, but it's a deviation from the architecture's own words that isn't captured in the "Scope corrections against the plan entry" table (which only reconciles against the slice-plan doc, not the architecture doc). Worth a one-line note in that table or elsewhere so a future reader doesn't need to reconcile the two documents themselves.
