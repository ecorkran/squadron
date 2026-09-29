---
docType: review
layer: project
reviewType: slice
slice: pipeline-sdk-session-control-seeding-without-a-turn-dispatch-that-waits-for-background-work-and-explicit-prompt-and-settings
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/932-slice.pipeline-sdk-session-control-seeding-without-a-turn-dispatch-that-waits-for-background-work-and-explicit-prompt-and-settings.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20260928
dateUpdated: 20260928
reviewedSha: 5807aea95fa66a49e512b0e65b91464837f43849
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
squadronVersion: 0.15.1
findings:
  - id: F001
    severity: concern
    category: scope
    summary: "Slice size and independence conflict with the architecture's \"small and focused\" guideline"
    location: "project-documents/user/slices/932-slice.pipeline-sdk-session-control-seeding-without-a-turn-dispatch-that-waits-for-background-work-and-explicit-prompt-and-settings.md#Technical Scope"
  - id: F002
    severity: concern
    category: scope
    summary: "Part D is a visible behavior and policy change, not maintenance"
    location: "project-documents/user/slices/932-slice.pipeline-sdk-session-control-seeding-without-a-turn-dispatch-that-waits-for-background-work-and-explicit-prompt-and-settings.md#D10 — Settings policy per path"
  - id: F003
    severity: concern
    category: error-handling
    summary: "Failure handling for `stop_task` itself is not enumerated"
    location: "project-documents/user/slices/932-slice.pipeline-sdk-session-control-seeding-without-a-turn-dispatch-that-waits-for-background-work-and-explicit-prompt-and-settings.md#D5 — Wait for background agents, not shells"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Foreground dispatch remains unbounded and is only implicitly justified"
    location: "project-documents/user/slices/932-slice.pipeline-sdk-session-control-seeding-without-a-turn-dispatch-that-waits-for-background-work-and-explicit-prompt-and-settings.md:158"
  - id: F005
    severity: note
    category: nfr
    summary: "No NFRs in the parent architecture apply"
    location: "project-documents/user/architecture/900-arch.maintenance-and-refactoring.md"
  - id: F006
    severity: note
    category: dependencies
    summary: "Soft dependency on slice 931 is documented but not in frontmatter"
    location: "project-documents/user/slices/932-slice.pipeline-sdk-session-control-seeding-without-a-turn-dispatch-that-waits-for-background-work-and-explicit-prompt-and-settings.md:6"
  - id: F007
    severity: pass
    category: architecture
    summary: "Layering and dependency direction"
    location: "project-documents/user/slices/932-slice.pipeline-sdk-session-control-seeding-without-a-turn-dispatch-that-waits-for-background-work-and-explicit-prompt-and-settings.md#Component Structure"
  - id: F008
    severity: pass
    category: error-handling
    summary: "Failure modes for the new I/O paths are largely explicit"
    location: "project-documents/user/slices/932-slice.pipeline-sdk-session-control-seeding-without-a-turn-dispatch-that-waits-for-background-work-and-explicit-prompt-and-settings.md#D13 — Failure modes"
---

# Review: slice — slice 932

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Slice size and independence conflict with the architecture's "small and focused" guideline

Architecture 900 says to prefer many small slices, and that each slice should be independently deliverable. This slice bundles four issues (#162, #163, #155, #156). It touches about 14 components across `pipeline/`, `providers/`, `review/`, `config/`, `core/`, `events/` and `data/templates`. It also adds a new module and two new config keys. The "Why one slice" paragraph records that bundling was a PM decision, and I'm not challenging it. The A → B → D → C ordering with separately revertable commits reduces the risk. But Part D is coupled to Part C. The recording half of #156 lands in the C + recording step, and `AgentConfig.auto_memory` overlaps with slice 931's files. Part A also depends on Part D's constants only loosely. If effort or review pressure grows, splitting at the A/B vs D/C boundary would match the architecture better, and A alone is the urgent safety fix. Treat that split as a pre-agreed fallback.

### [CONCERN] Part D is a visible behavior and policy change, not maintenance

The architecture excludes "new features or capabilities" from this initiative. Part D introduces the `pipeline.auto_memory` switch, a policy layer (`PIPELINE_SETTING_SOURCES`, `REVIEW_SETTING_SOURCES`), and a change to which user settings reach automated runs. D10 records PM ratification and a CHANGELOG line, which covers the decision. Even so, the new config key and operator-visible behavior change sit at the edge of "operational: configuration improvements". The slice should say explicitly why this counts as maintenance (closing an unintended default, #156) rather than a feature. It should also keep the config surface minimal. Consider whether the `auto_memory` switch is needed now or is a candidate for a deferred issue.

### [CONCERN] Failure handling for `stop_task` itself is not enumerated

D13 covers the idle timeout, an early stream end, and reconnect failure well. It does not say what happens if `client.stop_task(task_id)` raises or hangs during the timeout path. The steps say the ledger is cleared locally and the WARNING is logged, but not whether a `stop_task` error is logged at ERROR and swallowed or re-raised. Project rules require an explicit strategy for every try/except. The failure-mode table and the failure-mode tests should add this row. Also state that the reconnect-failed `unusable_reason` path is inspected before the idle-timeout path, so the two don't interact.

### [CONCERN] Foreground dispatch remains unbounded and is only implicitly justified

The slice states that foreground turns keep today's behavior with no timer, and that it bounds only the new wait it adds. That is acceptable scope discipline. But the new stream-read loop now runs across multiple `receive_response()` turns, and a peer that stalls before the own result is seen (the ledger is empty, or the own result hasn't arrived) is not covered by any signal. Add one line to D13 saying this is an accepted, unchanged failure mode, and link a tracking issue per the "issues over Future Work" convention. Otherwise a reader can't tell whether the gap is deliberate.

### [NOTE] No NFRs in the parent architecture apply

Architecture 900 defines no latency, throughput, or other NFR targets, so nothing needs restating in the slice. The only quantitative bound the slice introduces is `pipeline.background_idle_timeout_s` (default 1800), which is stated where it is used.

### [NOTE] Soft dependency on slice 931 is documented but not in frontmatter

`dependencies: []` is consistent with the "no hard prerequisite" statement. The rebase overlap with 931 (`review/models.py`, `persistence.py`, `core/models.py`) is described in the Dependencies section. No action is needed unless the project tracks soft ordering elsewhere.

### [PASS] Layering and dependency direction

The settings policy lives in a small `providers/sdk/settings.py` that both the provider and the pipeline session builder consume. `describe_system_prompt` sits next to the existing prompt table in `core/models.py`, so the recorded mode and the mode sent come from one rule. `open_pipeline_session` replaces duplicated option literals, which is a DRY consolidation. `AgentConfig.auto_memory` replaces an inferred `setting_sources == []` check. Dependency directions look correct: pipeline and review depend on the provider and core layers, not the reverse.

### [PASS] Failure modes for the new I/O paths are largely explicit

The D13 table covers reconnect failure, an early stream end, an idle timeout with lost terminal signals, a killed or failed agent, a leftover injected turn, an invalid step prompt on the session path, and a missing template setting. Each row has an observable signal (a WARNING, `logger.exception`, a `ProviderError`, or step metadata). The Technical Requirements list tests asserting those signals. This meets the failure-mode enumeration criterion apart from the two gaps noted above.

### Run Digest

- Response length: 6669 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- Reasoning characters: 0
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8

## Response (20260928)

- **F001, no change to scope.** Bundling is the PM's decision. Technical Scope now records the fallback the review suggests: if the slice needs splitting, split between A/B and D/C.
- **F002, clarified.** D10 now says why Part D is maintenance. The SDK's handling of `setting_sources=None` changed underneath squadron: slice 101 records "no project context", while 0.2.160 lets the CLI load user settings (D9). Part D closes that unintended default. Its only new config key is `pipeline.auto_memory`, which the PM asked for explicitly, so it stays. Settings sources remain code constants, not config.
- **F003, fixed.**
  - `stop_task` is already bounded by the SDK (a 60s control-request timeout). It raises a bare `Exception` on both timeout and error response. The design names a single-call `except Exception` (`noqa: BLE001`, with a comment citing the SDK) that logs through `logger.exception` and continues with the next id. This is best-effort cleanup, and any follow-up turn falls to D6.
  - A D13 row and a test were added.
  - The `unusable_reason` check is the first statement of each session method, so it cannot meet the wait logic.
- **F004, fixed.** D13 now has a row stating that a stalled foreground turn is an accepted, unchanged failure mode, tracked in [#165](https://github.com/ecorkran/squadron/issues/165). D5 links it too.
- **F005, no action.**
- **F006, no action.** The soft ordering is recorded in Dependencies, and the frontmatter stays `[]` because 932 has no hard prerequisite.
