---
docType: review
layer: project
reviewType: slice
slice: review-scope-correctness
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/916-slice.review-scope-correctness.md
aiModel: moonshotai/kimi-k3
status: complete
dateCreated: 20260913
dateUpdated: 20260913
reviewedSha: 45e7b0024bb797c6b131eb43580c9591bf8c0625
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 19
findings:
  - id: F001
    severity: pass
    category: alignment
    summary: "Slice is maintenance-shaped and plan-authorized"
    location: "project-documents/user/slices/916-slice.review-scope-correctness.md"
  - id: F002
    severity: pass
    category: integration
    summary: "Integration claims verify against source"
    location: "project-documents/user/slices/916-slice.review-scope-correctness.md"
  - id: F003
    severity: pass
    category: error-handling
    summary: "Failure modes on the new I/O path are enumerated and closed"
    location: "project-documents/user/slices/916-slice.review-scope-correctness.md"
  - id: F004
    severity: pass
    category: scope
    summary: "Documented surface preserved as a first-class invariant"
    location: "project-documents/user/slices/916-slice.review-scope-correctness.md#part-c--save-gating-70"
  - id: F005
    severity: concern
    category: documentation
    summary: "Embedded \"verified on implementation\" evidence invites design-vs-reality drift"
    location: "project-documents/user/slices/916-slice.review-scope-correctness.md"
  - id: F006
    severity: note
    category: testing
    summary: "\"No message-text assertions\" sits awkwardly beside the differentiation requirement"
    location: "project-documents/user/slices/916-slice.review-scope-correctness"
---

# Review: slice — slice 916

**Verdict:** CONCERNS
**Model:** moonshotai/kimi-k3

## Findings

### [PASS] Slice is maintenance-shaped and plan-authorized

- The five bundled defects are bug fixes on the `sq review` entry path — squarely within 900-arch's "bug fixes … that don't belong to an active feature slice" scope. The bundle-vs-split question was raised at slice review (F004) and answered by plan authorization plus a load-bearing D→A→C→B→E sequence; each part lands independently committable. That is the correct home for this work.
- The parent-field pointing at the slice plan (`900-slices.maintenance-and-refactoring.md`) matches the documented convention and is not an error.

### [PASS] Integration claims verify against source

- Part B's no-new-Verdict-member decision rests on an enumerated consumer set; the cited gate shapes check out — `CheckpointTrigger.ON_CONCERNS` allowlist (`{CONCERNS, FAIL, UNKNOWN}`) at `checkpoint.py:22`, `LoopCondition.REVIEW_CONCERNS_OR_BETTER` (`{PASS, CONCERNS}`) at `executor.py:231/247`. The "no artifact, no gate" argument is sound.
- B3's escape hatch (omit `review:` key → no review action, no checkpoint) verified at `phase.py:76` and `:163`.
- E1's mechanism confirmed: the SDK provider now sets both `tools` and `allowed_tools` (`provider.py:64-75`), and the pinned dependency is `claude-agent-sdk>=0.1.38` (`pyproject.toml:30`).
- The prompt-builder interpolation (`builders/code.py:31/36`) confirms A1's single-normalized-string requirement is meaningful — the model's own `git diff` instruction and the path list derive from the same value.

### [PASS] Failure modes on the new I/O path are enumerated and closed

- Part A5 names the hang/timeout/no-repo family explicitly, routes the new git call through the shared `run_git` helper, and distinguishes "not a git repository" from "ref not found" via typed errors. Verified in `git_utils.py` — `GIT_COMMAND_TIMEOUT_SECONDS = 30` is applied, with a WARNING rather than a silent None on timeout. The residual gap (unvalidated endpoints inside explicit `a..b`/`a...b` shapes) is recorded as a deliberate decision with rationale, not an oversight. That is the level of rigor the criterion requires.

### [PASS] Documented surface preserved as a first-class invariant

- C3's revision (warn-and-exit-on-verdict for slice-less `--diff`, exit 1 only for attempted-and-failed saves) treats the 10 README/COMMANDS.md examples and slice 118's compatibility guarantee as the constraint they are. The recovery is more important than the original mistake: the design now preserves the tool's most-advertised invocation while still closing #70's actual harm (silent non-persistence). Success criteria 7 and the walkthrough pin this down concretely (stderr, not stdout, so `--output json` pipelines stay parseable).

### [CONCERN] Embedded "verified on implementation" evidence invites design-vs-reality drift

- At design time this document asserted things it could not yet have observed ("run_git passes no timeout", step-by-step mock probes, live SDK kwargs). The implementation did close those gaps, but the document itself marks the pattern: a future reader cannot tell which claims were pre-implementation hypotheses and which are post-implementation facts, because the doc carries both with identical authority. Much of it has been corrected inline, but the residual risk is recurrence — a design doc that absorbs implementation-time narrative without distinguishing it invites quiet staleness on the next edit. Worth recording as guidance, not as a defect of this slice. All concrete claims spot-checked here (`git_utils.py` timeout, provider kwargs, README example counts, phase.py review-key gate) did resolve correctly — so the concern is about the *practice*, not the *outcome*.

### [NOTE] "No message-text assertions" sits awkwardly beside the differentiation requirement

- The technical criteria forbid asserting on user-facing message text, yet B2/A4/C4's correctness *is* message differentiation (all-excluded vs no-changes, not-a-repo vs ref-not-found, warning-names-the-remedy). Typed fields on exceptions (e.g. `EmptyScopeCase`, `DiffSpecError.ref`) make this testable on structure rather than text — so the two requirements are compatible — but the criterion as written is one edit away from being read as "test exit codes only," which would defeat the differentiation the design insists on. A one-line clarification ("assert on the exception's structured fields, not its rendered message") would remove the ambiguity.

### Run Digest

- Response length: 5860 chars
- Response is newline-free: no
- Tool calls made: 19
- Tool calls failed: 1
- Stop reason: stop
- Reasoning characters: 0
- `## Summary` located: no
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
