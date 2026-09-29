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
reviewedSha: 0a93b6a785d1502252dbdcf9424398891abc68e1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
squadronVersion: 0.15.1
findings:
  - id: F001
    severity: concern
    category: scope
    summary: "Slice bundles four issues and exceeds the \"small and focused\" guideline"
    location: "project-documents/user/slices/932-slice.pipeline-sdk-session-control-seeding-without-a-turn-dispatch-that-waits-for-background-work-and-explicit-prompt-and-settings.md#Technical Scope"
  - id: F002
    severity: concern
    category: scope
    summary: "Part D changes operator-visible defaults, which sits close to the \"not a feature\" boundary"
    location: "project-documents/user/slices/932-slice.pipeline-sdk-session-control-seeding-without-a-turn-dispatch-that-waits-for-background-work-and-explicit-prompt-and-settings.md#D10 — Settings policy per path"
  - id: F003
    severity: concern
    category: error-handling
    summary: "Failure modes for the new reconnect and background-wait paths are incomplete"
    location: "project-documents/user/slices/932-slice.pipeline-sdk-session-control-seeding-without-a-turn-dispatch-that-waits-for-background-work-and-explicit-prompt-and-settings.md#D13 — Failure modes"
  - id: F004
    severity: concern
    category: correctness
    summary: "The D6 race can misattribute work between steps"
    location: "project-documents/user/slices/932-slice.pipeline-sdk-session-control-seeding-without-a-turn-dispatch-that-waits-for-background-work-and-explicit-prompt-and-settings.md#D6 — Only the dispatch's own result can end it"
  - id: F005
    severity: note
    category: dependencies
    summary: "The dependency declaration understates the overlap with slice 931"
    location: "project-documents/user/slices/932-slice.pipeline-sdk-session-control-seeding-without-a-turn-dispatch-that-waits-for-background-work-and-explicit-prompt-and-settings.md:6"
  - id: F006
    severity: pass
    category: architecture
    summary: "Layering and dependency direction"
    location: "project-documents/user/slices/932-slice.pipeline-sdk-session-control-seeding-without-a-turn-dispatch-that-waits-for-background-work-and-explicit-prompt-and-settings#Component Structure"
  - id: F007
    severity: pass
    category: scope
    summary: "Scope boundaries are explicit and justified"
    location: "project-documents/user/slices/932-slice.pipeline-sdk-session-control-seeding-without-a-turn-dispatch-that-waits-for-background-work-and-explicit-prompt-and-settings#Technical Scope"
  - id: F008
    severity: pass
    category: testing
    summary: "Verification and test plan match the change"
    location: "project-documents/user/slices/932-slice.pipeline-sdk-session-control-seeding-without-a-turn-dispatch-that-waits-for-background-work-and-explicit-prompt-and-settings#Technical Requirements"
---

# Review: slice — slice 932

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Slice bundles four issues and exceeds the "small and focused" guideline

The architecture asks for "many small slices over few large ones" that are each independently deliverable. This slice combines four parts (A–D) across the following areas:
- the session builder
- dispatch-loop semantics
- a new `providers/sdk/settings.py` module
- a new `SystemPromptMode` enum
- template loader changes
- review model, digest, and JSON output changes
- step metadata

The Development Approach already splits the work into four commits, and A, B, and D are largely independent of one another. Part A is the safety fix and is the urgent one. Splitting off B, and the D-plus-recording work, would fit the guideline better. If the PM wants to keep it together, the slice should say why.

### [CONCERN] Part D changes operator-visible defaults, which sits close to the "not a feature" boundary

D10 and D11 do more than fix bugs. Pipeline sessions, dispatch, and the `slice`/`tasks`/`judge-*` reviews stop loading the operator's user CLAUDE.md, and auto-memory is turned off on several paths. That is a behavior-policy change. The slice concedes it is "a single constant change if the PM prefers" the other option, so the decision is still open. Because the maintenance architecture excludes new capabilities, the slice should mark D10 as a PM-ratified decision before implementation. The change could also break workflows that quietly rely on user-level CLAUDE.md, and the slice has no migration or release-note item for it.

### [CONCERN] Failure modes for the new reconnect and background-wait paths are incomplete

D13 covers the main cases, but three gaps remain on paths the slice adds:

- **Reconnect leaves no live client.** Rotation disconnects the old client before connecting the new one. If the new connect fails, the session has no live client. D13 says only that "the exception propagates". It does not say what state the session is left in, or whether a later step can retry safely or must abort the run.
- **CLI process dies while the ledger is non-empty.** The stream may end with no terminal task message and no own result. D13 does not say whether that is an error, an empty return, or a hang. Today's dispatch handles stream end. The new loop needs an explicit rule.
- **A lost terminal signal hangs dispatch.** If a terminal task message is never delivered, the ledger never empties. D5 accepts "no wait ceiling" and offers only an INFO log. The architecture states no NFR, so this is acceptable in principle. Still, an unbounded wait on an unattended batch run is an explicit failure mode that the slice should either accept knowingly, with the log line as the signal, or bound.

Tests are specified for the scripted message sequences. There is no test for the stream-ended-early case, and none asserting the observable signal on reconnect failure.

### [CONCERN] The D6 race can misattribute work between steps

D6 admits a known SDK race. An injected follow-up turn can land at the start of the next dispatch's stream, so its text belongs to the previous step. The mitigation is a WARNING. In the meantime, the previous step's post-condition (the artifact check) has already run and may have flagged it. The consumed text is also joined into the next step's response, so the D7 tail and the next step's post-condition see the wrong step's words. The slice should say whether that text is discarded from the response or kept, and it should acknowledge that the previous step's flag reason can be misleading.

### [NOTE] The dependency declaration understates the overlap with slice 931

Frontmatter says `dependencies: []`, and Prerequisites says "None". The slice also says 931 adds Run Digest lines and `AgentConfig` fields in neighboring code, and that "whichever merges second rebases". This is manageable. Still, `ReviewResult` and the digest renderer are shared surfaces. Record it as a soft ordering constraint, since the rebase risk sits mainly in `review/models.py` and `review/persistence.py`.

### [PASS] Layering and dependency direction

The new `providers/sdk/settings.py` is a leaf module used by both the provider and the session builder. Prompt-mode derivation lives in `core/models.py` next to the existing prompt table, and there is one shared session builder. This removes duplicated option literals (DRY) and keeps pipeline, provider, and review dependencies pointing at core and provider primitives. No cross-layer violations found.

### [PASS] Scope boundaries are explicit and justified

The out-of-scope list is specific and each item has a reason: `capture_summary`, query-mode dispatch, background shells, `sq serve`, and the auth probe. The rejected `system_prompt_mode: replace` escape hatch is backed by a check of shipped and user pipelines. All four parts fit the architecture's categories of bug fixes and operational improvements that span subsystems. The slice carries no feature scope beyond the settings-policy question raised above.

### [PASS] Verification and test plan match the change

Tests assert on the client options and on the absence of a `query`, which is the right check for part A. Scripted message sequences cover the dispatch-wait cases, including terminal-only-by-update, shells, and injected-first. Parametrized tests cover the modes and the per-path settings. The CLI default behavior in D9 was probed rather than assumed.

### Run Digest

- Response length: 7184 chars
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

- **F001, no change to scope.** The slice plan entry bundles the four issues, and that was a PM decision. Technical Scope now has a "Why one slice" paragraph: one shared theme and two shared surfaces. The parts still land separately in the order A → B → D → C. Each passes the suite on its own and can be reverted alone. The safety fix (A) goes first.
- **F002, fixed.** D10 is marked PM-ratified 20260928. The PM kept `[project]` and changed only auto-memory, which is now the `pipeline.auto_memory` config key (D11). Implementation Notes add a one-line CHANGELOG item telling operators that user CLAUDE.md and user settings no longer load.
- **F003, fixed.**
  - A failed reconnect sets `unusable_reason`, and every later call raises `ProviderError` naming it.
  - A stream that ends before the dispatch's own result raises `ProviderError`.
  - The background wait is now bounded by `pipeline.background_idle_timeout_s` (default 1800). On timeout, dispatch stops the tracked tasks, clears the ledger, logs a WARNING, and records `background_tasks_stopped`.
  - D13, Data Flow, Success Criteria, and Technical Requirements are updated, and a test asserts the signal for each mode.
- **F004, fixed.** Leftover text from an injected turn that arrives before the dispatch's own result is dropped from the response and logged at WARNING with its tail. The current step's response, D7 tail, and post-condition therefore see only that step's words. D6 now says plainly that the previous step's flag can be misleading if the leftover turn wrote its artifact late. This is accepted: the WARNING is the evidence, and a resume finds the artifact.
- **F005, fixed.** Prerequisites records a soft ordering with 931. The overlap is in `review/models.py`, `review/persistence.py`, and `core/models.py`, and Part C (plus Part D's one `AgentConfig` line) rebases if 931 lands first. Frontmatter `dependencies` stays `[]`, because the two slices share no logic.
