---
docType: review
layer: project
reviewType: slice
slice: effort-audit-across-dispatch-paths
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/420-slice.effort-audit-across-dispatch-paths.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261104
dateUpdated: 20261104
reviewedSha: ef6d51a92bef416c09d60faee087b218920b0079
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 9
effort: high
turns: 10
promptTokens: 516964
cachedTokens: 415241
cacheWriteTokens: 101712
completionTokens: 8638
durationSeconds: 70.4
costUsd: 0.581897
costBasis: provider
squadronVersion: 0.24.22
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Failure paths that return no ActionResult still read as \"not sent\""
    location: "project-documents/user/slices/420-slice.effort-audit-across-dispatch-paths.md#D5 — Effort sent is stamped on the action, not only on the usage record"
  - id: F002
    severity: concern
    category: architecture
    summary: "The judge starts sending effort without changing judge identity"
    location: "project-documents/user/slices/420-slice.effort-audit-across-dispatch-paths.md#D3 — Both judges send the alias's effort"
  - id: F003
    severity: concern
    category: integration
    summary: "`config_identity` is typed to the producer replay record but is promised to slices that don't use it"
    location: "project-documents/user/slices/420-slice.effort-audit-across-dispatch-paths.md#D6 and #Provides to Other Slices"
  - id: F004
    severity: concern
    category: architecture
    summary: "D6 narrows the architecture's config identity, but only the slice doc records it"
    location: "project-documents/user/slices/420-slice.effort-audit-across-dispatch-paths.md#D6 — Config identity is (model, profile, effort sent); the alias is display"
  - id: F005
    severity: concern
    category: scope
    summary: "Proportionality: the null-path tests and enumeration test cover a case the slice doesn't have"
    location: "project-documents/user/slices/420-slice.effort-audit-across-dispatch-paths.md#Technical Requirements and #D7 — The inventory is enforced by an enumeration test"
  - id: F006
    severity: note
    category: error-handling
    summary: "Persisted `effort_sent` round-trips as a plain string"
    location: "project-documents/user/slices/420-slice.effort-audit-across-dispatch-paths.md#D5 — Effort sent is stamped on the action, not only on the usage record"
  - id: F007
    severity: note
    category: scope
    summary: "The findings-addressed judge's effort change alters a production gate"
    location: "project-documents/user/slices/420-slice.effort-audit-across-dispatch-paths.md#D3"
  - id: F008
    severity: pass
    category: architecture
    summary: "Boundaries, dependency direction and plan alignment"
    location: "project-documents/user/slices/420-slice.effort-audit-across-dispatch-paths.md#Dependencies"
---

# Review: slice — slice 420

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Failure paths that return no ActionResult still read as "not sent"

D5 exists to stop a failed dispatch from landing in the wrong config row. It guarantees `effort_sent` only on "every action result that reached a provider, success or failure". Some failures produce no result to stamp:
- A cancelled action propagates unchanged. `UsageCapture` already documents this.
- A provider hang or timeout can kill the `sq run` subprocess.
- The `except Exception` branch in `DispatchAction` returns a generic failure result.

In those cases the key is absent. `action_effort_sent` then falls back to `usage.effort`, which is also absent, and returns `None`. D1 defines `None` as "nothing went on the wire". That conflates "not sent" with "unknown", which is the same stand-in D5 sets out to remove.

The same ambiguity shows up in the doc. Under State Management, an absent key means "predates this slice", but a crashed run on new code has an absent key too.

The slice needs a failure-mode table for the new stamp, covering:
- Success.
- A provider error that returns a result.
- The generic exception branch.
- Cancellation.
- Subprocess death before any result is written.

For each row it should say what the stamp and the reader yield. The reader also needs a distinct "unattributed" outcome, which replay and `sq stats producers` report as a harness-side absence. The architecture's "Absent is not zero" principle requires this. One observable signal, such as a WARNING when the reader hits that case, should be tested.

### [CONCERN] The judge starts sending effort without changing judge identity

D3 makes the replay judge send `resolved.effort`, where it sent none before. It also states that `JudgeRef` (alias, model, prompt_hash) gains no effort field because "the judge is fixed per report". After this slice, the same judge alias produces different behavior before and after the change, and again whenever the alias's effort is edited. The architecture says results must stay comparable over time and name the grader identity. Judgments made before and after this slice carry an identical `JudgeRef`, so a Bradley-Terry report can mix them without any flag.

The slice doesn't say that the report enforces "fixed per report". Either add effort sent to `JudgeRef` (an optional field, so no migration is needed), or specify that the report rejects or flags mixed judge efforts. Choose one explicitly. The usage-record effort alone doesn't protect the aggregation.

### [CONCERN] `config_identity` is typed to the producer replay record but is promised to slices that don't use it

D6 defines `config_identity(ProducerConfigRef)`. `ProducerConfigRef` is a 177 replay type in `metrology/replay_models.py`. The Provides section offers it to 425, 426 and 427's "reviewer configs".

- 424/425 write new record types, so they need a config shape that isn't `ProducerReplay`'s.
- 427 depends only on 421 and is deliberately independent of 424–426. Reviewer configs are not producer configs.
- `ProducerKey` in `stats/producer_units.py` is a third shape that already holds `(model, profile, effort, reviewer)`.

As written, 427 either imports a replay-producer type or re-derives the identity, which is the duplication D6 was meant to remove. State where `config_identity` lives and what type it accepts. A small shared `(model, profile, effort_sent)` value, with adapters from `ProducerConfigRef` and `ProducerKey`, would let all three consumers use it without a replay dependency.

### [CONCERN] D6 narrows the architecture's config identity, but only the slice doc records it

The architecture states config identity as "(alias, model, profile, effort sent)" in Design Goals and in the Envisioned State. D6 drops the alias from grouping. The slice plan's criterion ("differ only in the alias's effort label but sent the same effort count as one config") supports the narrowing, and D6 acknowledges it. The architecture text is unchanged, though, so 424, 425 and 427 will read the wider definition when they design their records and reports.

Update the architecture sentence, or note in the Provides section that the architecture's identity is superseded for grouping.

D6 also assumes `(model, profile, effort)` fully determines behavior. State what else an alias can set, such as other per-alias options, and confirm that none of it changes what is sent.

### [CONCERN] Proportionality: the null-path tests and enumeration test cover a case the slice doesn't have

The Providers paragraph says every provider sets `applies_effort=True`, so "no current provider is a 'cannot send' case". The Technical Requirements still call for a null-effort test per alias-bearing path, using a fake `applies_effort=False` provider. That's roughly a dozen tests for a case no path can reach.

The gating lives in two shared helpers: `note_effort_sent` and `effort_sent_by_profile`. Test the capability gate once per helper, and keep the per-path tests to what is sent and recorded. The slice plan's "a path that cannot send effort records 'not sent', and a test checks that too" is met by the helper tests.

The D7 AST enumeration test and its classification table go beyond the plan's inventory and per-path tests, and they are a maintenance cost. Keep it only if it stays small. Otherwise move it out of the slice, since the inventory table plus per-path tests already meet the plan's success criteria.

### [NOTE] Persisted `effort_sent` round-trips as a plain string

`read_effort_sent` uses `isinstance(value, Effort)`, which is right for in-memory metadata. Replay and stats read `ActionResult.metadata` from persisted run JSON, where the value is a `str`. Say in D5 that `action_effort_sent` parses persisted strings leniently into `Effort`, and that an unrecognized value raises explicitly rather than reading as `None`. This follows the project's no-silent-fallback rule.

### [NOTE] The findings-addressed judge's effort change alters a production gate

After D3, the gate and `sq review resolve` run at the alias's effort, so their cost and latency change. That follows 931, so it isn't a defect. The CHANGELOG bullet should say it, because a user will notice the change. Its unrecorded spend is correctly deferred to a separate issue.

### [PASS] Boundaries, dependency direction and plan alignment

- Prerequisites (931, 175, #216) are complete and the slice has no upstream dependency in this initiative, matching the slice plan.
- The surface it provides (`action_effort_sent`, the metadata key, `config_identity`) matches the plan's Interfaces line.
- The out-of-scope paths (metrology audit, PR composer, daemon agents, auth probe, IDE `/model`) are correctly excluded, because they resolve no alias.
- It reuses `EFFORT_SENT_KEY` and the existing capability-gated helpers rather than adding a new marker (D1), and it requires no store migration.
- The inventory, compaction fix, both judge fixes, `_dispatch-run --effort` and replay row merging cover the plan's scope, and none of it is dropped.

### Run Digest

- Response length: 8484 chars
- Response is newline-free: no
- Tool calls made: 9
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: high
- Turns: 10
- Tokens — prompt / cached / cache write / completion / reasoning: 516964 / 415241 / 101712 / 8638 / not computed
- Duration: 70.4 s
- Cost: $0.58 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8

## Responses

- **F001 (fixed):** D5 now stamps every result built after resolution, including the `except Exception` branch. It names the runs that carry no stamp (no run state, cancelled, failed resolution): nothing was sent in them, and replay already marks each with a failure class that decides how it counts. No new "unattributed" outcome or failure-mode table; the existing failure class already carries that.
- **F002 (fixed):** `JudgeRef` gains an optional `effort_sent`. The report already builds one table per distinct `JudgeRef` (`replay/report.py`), so mixed judge efforts are never aggregated together.
- **F003 (fixed):** Cut the promise. `config_identity` is private to `replay/report.py`, and Provides now states the identity rule rather than a shared type for 425–427.
- **F004 (fixed):** Provides now says the D6 rule supersedes the architecture's identity for grouping. The check of other alias fields found `tool_use` and `max_output_tokens`, which also change what is sent, so both are recorded on `ProducerConfigRef` as optional fields and join the identity.
- **F005 (fixed in part):** Null-effort tests are cut to one per shared helper. D7 stays: it covers 11 sites and reuses the existing SC1a pattern, so it is small.
- **F006 (fixed):** D5 says the reader parses persisted strings into `Effort` leniently and raises on an unrecognized value.
- **F007 (fixed):** The CHANGELOG requirement now says the findings-addressed gate and `sq review resolve` run at the alias's effort, so their cost and latency can change.
