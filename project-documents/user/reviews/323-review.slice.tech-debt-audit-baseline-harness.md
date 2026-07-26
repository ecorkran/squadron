---
docType: review
layer: project
reviewType: slice
slice: tech-debt-audit-baseline-harness
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/323-slice.tech-debt-audit-baseline-harness.md
aiModel: claude-sonnet-5
status: complete
dateCreated: 20260726
dateUpdated: 20260726
resolutionDate: 20260726
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "No failure-mode enumeration for the new agent-execution I/O path"
    location: project-documents/user/slices/323-slice.tech-debt-audit-baseline-harness.md#Execution-path
    resolution: fixed
  - id: F002
    severity: concern
    category: dependency-direction
    summary: "Frontmatter `interfaces: []` omits the downstream consumer this slice's own design says it feeds"
    location: project-documents/user/slices/323-slice.tech-debt-audit-baseline-harness.md:7
    resolution: fixed
  - id: F003
    severity: note
    category: scope-boundary
    summary: "Editing a 340-owned distributable artifact is a real scope expansion, though well-disclosed"
    location: project-documents/user/slices/323-slice.tech-debt-audit-baseline-harness.md#1-Fix-the-fork-do-not-wrap-it
    resolution: fixed
  - id: F004
    severity: pass
    category: alignment
    summary: "Variance-before-baseline-before-intervention is honored precisely"
    location: project-documents/user/slices/323-slice.tech-debt-audit-baseline-harness.md#Technical-Scope
  - id: F005
    severity: pass
    category: alignment
    summary: "Honest small-n statistics and no-borrowed-floor discipline match the architecture's stated constraint"
    location: project-documents/user/slices/323-slice.tech-debt-audit-baseline-harness.md:174-181
  - id: F006
    severity: pass
    category: alignment
    summary: "Non-goals respected: no agreement dimension fabricated, no dispatch write, no new storage engine, no auto-remediation"
    location: project-documents/user/slices/323-slice.tech-debt-audit-baseline-harness.md#Explicitly-excluded
---

# Review: slice — slice 323

**Verdict:** CONCERNS
**Model:** claude-sonnet-5

## Resolution (20260726)

All three actionable findings addressed in the slice design. Verdict left as CONCERNS — this section records disposition only, not a re-review.

- **F001 (failure-mode enumeration)** — Added a *Failure modes of the agent-execution path* section. The finding's premise was verified and proved stronger than stated: `run_review_with_profile` supplies **no** handling to inherit ([review_client.py:134-156](../../../src/squadron/review/review_client.py#L134-L156) is a bare `async for` with only `finally: shutdown()` — no timeout, no exception handling around the stream). The section enumerates eight failure modes with detection, response, and observable signal; establishes that a run persists a complete `AuditRun` or nothing at all (so a failed run can never enter the floor as a low-count sample); adds pre-flight checks before any token spend; and adds `metrology.audit_timeout_s`. Three success criteria and per-mode tests added.
- **F002 (`interfaces: []`)** — Confirmed against sibling frontmatter (320 → `[321, 322, 323, 324]`, 321 → `[322]`) and corrected to `interfaces: [324]`. The diagnosis was exact: carried over from 322, which is `[]` correctly because it is terminal, whereas 324 consumes 323's baseline and floor.
- **F003 (340 boundary)** — Recorded in the parent architecture's Related Work, which had described the 340 relationship as read-only. It now states that 323 makes it read-write, names the MIT-licensed fork as canonical source, notes edits reach every consumer of that fork, and records PM approval.

## Findings

### [CONCERN] No failure-mode enumeration for the new agent-execution I/O path

`run_audit` invokes an LLM agent against another project's `cwd`, potentially triggering Task-subagent fan-out on large repos (Decision 1, `:97` fan-out note) — a genuinely new, long-running, cross-process I/O path for this initiative. The doc enumerates handling for downstream failures (malformed findings block fails loudly at the parse boundary; a variance series with divergent SHAs/hashes is refused; a failed run in a series doesn't discard prior runs), but never addresses failure of the agent invocation itself: what happens if the audit run hangs, times out, the model/API connection drops mid-generation, or a subagent's tool permission is denied mid-run. `review_client.run_review_with_profile` is named as the structural precedent, but the doc doesn't state whether its timeout/error handling is inherited, reused, or needs new logic for a run that targets an arbitrary external `cwd` rather than the current repo. Per the project's failure-mode-enumeration rule, this must be explicit (with an observable signal — log/metric) rather than left to be discovered at implementation time.

### [CONCERN] Frontmatter `interfaces: []` omits the downstream consumer this slice's own design says it feeds

The architecture's Anticipated Slices section lists slice 324 with "Dependencies: [323] (baseline + noise floor must exist first)," and the 320-slices plan doc states 324 "consumes the persisted baseline and noise floor (323)." Sibling slice 320's frontmatter correctly lists `interfaces: [321, 322, 323, 324]` to reflect exactly this kind of downstream consumption. 323's own frontmatter declares `interfaces: []`, which contradicts the dependency edge the architecture and slice-plan both assert (324 → 323). This looks like a copy-paste from 322 (also `interfaces: []`, correctly, since nothing depends on 322 for this data) rather than a deliberate value for 323, and any tooling that reads this field for dependency graphing will silently miss the 323→324 edge.

### [NOTE] Editing a 340-owned distributable artifact is a real scope expansion, though well-disclosed

The architecture's Related Work describes 340 only as the initiative that "ships the analysis pack containing the `tech-debt-audit` skill this component's code-quality oracle runs" — a read/consume relationship. This slice instead makes 320 a canonical-source editor of that skill (Decision 1/1a: edits land in `github:ecorkran/tech-debt-audit` first, then get vendored into squadron, affecting every other consumer of the fork). The slice doc is commendably explicit that this is "a real coupling, not a read-only one" and adds CI enforcement (category-vocabulary sync test) to guard drift — so this isn't a hidden dependency, but it is scope the parent architecture doesn't anticipate for 320's boundary with 340, and it is worth the Project Manager's explicit sign-off given it touches a MIT-licensed external repo outside squadron's own release process.

### [PASS] Variance-before-baseline-before-intervention is honored precisely

The architectural principle *"Variance, then baseline, then intervention"* is implemented literally: noise floor (Decision 6/7) ships alongside the baseline, the pre-emption prompt and delta report are explicitly excluded to 324, and Data Flow states "the down-only discipline 324 must honor starts being true here."

### [PASS] Honest small-n statistics and no-borrowed-floor discipline match the architecture's stated constraint

Architecture: *"Reports must carry their sample sizes and refuse to imply precision they don't have."* The slice's `FloorStat` (min/max/mean/stddev), per-project (not global) floors, and the explicit "no floor measured" sentinel rather than borrowing another project's number directly satisfy this.

### [PASS] Non-goals respected: no agreement dimension fabricated, no dispatch write, no new storage engine, no auto-remediation

Matches architecture Non-Goals and Technical Considerations ("Pre-emption data flows down... never up at runtime," "No hard dependency on 280," store additive only) and Success Criteria includes an explicit test that no report path produces a human-comparison figure.
