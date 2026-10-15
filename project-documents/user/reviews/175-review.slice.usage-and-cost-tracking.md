---
docType: review
layer: project
reviewType: slice
slice: usage-and-cost-tracking
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/175-slice.usage-and-cost-tracking.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261014
dateUpdated: 20261014
reviewedSha: 1c51a68b8305c30d1be14cbad64fc03a30ba4afb
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
durationSeconds: 36.4
runId: run-20261015-p4-733c0a5c
squadronVersion: 0.21.9
findings:
  - id: F001
    severity: concern
    category: proportionality
    summary: "Design is heavier than the slice requires; several mechanisms can be cut or deferred"
    location: "project-documents/user/slices/175-slice.usage-and-cost-tracking.md#Technical Decisions"
  - id: F002
    severity: concern
    category: scope
    summary: "Architecture doc still lists cost tracking as out of scope; the slice relies on the plan entry alone"
    location: "project-documents/user/slices/175-slice.usage-and-cost-tracking.md#Technical Scope"
  - id: F003
    severity: concern
    category: nfr
    summary: "Hot-path NFR is asserted but not stated as a target"
    location: "project-documents/user/slices/175-slice.usage-and-cost-tracking.md#Data Flow"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Failure table rows lack a defined observation hook for some signals"
    location: "project-documents/user/slices/175-slice.usage-and-cost-tracking.md#Technical Requirements"
  - id: F005
    severity: note
    category: architecture
    summary: "Layering and dependency direction are sound"
    location: "project-documents/user/slices/175-slice.usage-and-cost-tracking.md#Architecture"
  - id: F006
    severity: note
    category: integration
    summary: "Integration with 174 and prior slices matches what they provide"
    location: "project-documents/user/slices/175-slice.usage-and-cost-tracking.md#Dependencies"
---

# Review: slice — slice 175

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Design is heavier than the slice requires; several mechanisms can be cut or deferred

The slice plan entry asks for a neutral record, capture at provider seams, persistence, and a reporting surface. This design adds all of that plus these items:
- **`model_usage` fallback (D2).** The design says per-model split "has no consumer yet" and then specifies a summing fallback for results with no top-level `usage`. Nothing says the SDK emits such a result. Cut the fallback. A missing top-level `usage` already produces `None` plus a WARNING.
- **Per-step effort WARNING (D7).** `effort=None` already records the gap truthfully, and #216 tracks the fix. A per-step warning on a known, deferred limitation adds a mechanism and a test row. Log it once per process at DEBUG, or drop it.
- **Pipeline-artifact exclusion and footer in `sq stats reviews` (D8).** The `runId` exclusion exists to avoid double counting between two views. Neither view totals across the other. List the artifacts and let `runId` show as a column, or defer the dedupe with `sq stats runs` (#214).
- **Bundled items.** #151 (`max_output_tokens`) is a dispatch and summary parameter change that does not depend on usage capture. It could be a standing fix (slice 944), as the design already does for #173. #154 is only a field on a record this slice already builds, so keep that one.
- **Unconsumed provisions.** "Provides to Other Slices" lists `price_usage` for pool ranking and an MCP-ready core. Both are speculative; the deferred MCP tool is the only stated consumer.
- **Failure table.** It has 13 rows, each with a mandated test. Several are speculative (non-int usage value, inconsistent counts). Keep the rows for new I/O paths and collapse the rest.

### [CONCERN] Architecture doc still lists cost tracking as out of scope; the slice relies on the plan entry alone

`140-arch` lists "Cost tracking and optimization across providers" under "Out of Scope (future, unscheduled)". The slice acknowledges this and cites the slice plan entry (line 116 of `140-slices.pipeline-foundation.md`). The plan entry does bring cost reporting in. The architecture doc is the parent for this review, and it still says the opposite. Its `dispatch` row already "owns" token tracking, so that part is covered.

Either update the arch scope boundary to say that cost reporting is in scope and cost optimization is out, or add an explicit amendment note to the slice. The follow-on #214/#210 slice will otherwise hit the same contradiction.

### [CONCERN] Hot-path NFR is asserted but not stated as a target

The slice touches every `dispatch`, `summary`, `compact`, and `review` execution and the `_append_step` state write, which are the executor's hot path. It states "Capture adds no I/O" and "no extra state save", which is a qualitative claim.

The state write is atomic-replace, so it grows with each persisted record. The `sq stats reviews` cost is described only as "one frontmatter parse per artifact". The arch doc states no numeric NFR for these paths, so this is not a violation. The slice should still give a concrete bound that tests can check. For example: capture adds zero extra state saves per action, and `sq stats reviews` parses frontmatter only, with no body reads. A test should assert the first of those.

### [CONCERN] Failure table rows lack a defined observation hook for some signals

The failure table is thorough, but three rows are underspecified:
- **"WARNING once per alias per process" (D3).** Process-level state makes the "once" behavior hard to test in isolation. The design does not say how the dedupe set is scoped or reset, and a module-level global would break test independence.
- **D5 interrupt drain with no `ResultMessage`.** The record keeps "turns and tokens that completed" but gets no marker that it is partial. `sq stats` would show it as a complete figure. A partial flag, or at minimum a note in the report, is needed to meet D9's honest-totals goal.
- **D6 end time on every exit path.** `usage_capture` must handle `asyncio.CancelledError` and resume, but the table has no cancellation row.

Specify the dedupe scope, add a partial-record indicator, and add a cancellation row.

### [NOTE] Layering and dependency direction are sound

- Providers emit raw telemetry on `Message.metadata`, and only `pipeline/usage_capture.py` attributes it to an alias and step (D4).
- `stats/` has no Typer dependency, and the CLI, slash command, and skill wrap it.
- No schema bump is needed because the data lives in `ActionResult.metadata`, which already round-trips through `asdict`.
- The slice does not touch the `Action` protocol, the `ActionContext` shape, or the events dispatcher, which matches the arch doc's boundaries.
- The executor-owned `RunObserver` and events paths are not used for usage, which is correct. Capture happens in the action that has the data.

### [NOTE] Integration with 174 and prior slices matches what they provide

The slice consumes 174's interrupt and drain behavior in `SDKExecutionSession`, 931's `RunCost` and `core/usage.py`, and `StateManager` atomic writes. It reuses `cli/columns.py`. The deferral of `AuditRun` persistence, step duration, and `sq stats runs` is documented with issue links, and none of it is silently dropped. The MCP deferral (#217) is recorded in the plan entry, so it does not count as dropped assigned scope.

### Run Digest

- Response length: 6523 chars
- Response is newline-free: no
- Tool calls made: 5
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 36.4 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6

## Response (20261015)

- **F001 (proportionality):** partly accepted. Cut the `model_usage` fallback (D2) and downgraded the per-step effort WARNING to a once-per-process DEBUG (D7). Kept the `sq stats reviews` pipeline-artifact exclusion, #151, and the failure-table rows: each is small and tested, and moving #151 would touch six sections of the design for no risk reduction.
- **F002 (arch scope):** fixed. `140-arch` out-of-scope line now says cost optimization is out and cost reporting is in as of 175.
- **F003 (NFR):** fixed. Two testable bounds added to the hot-path paragraph (zero extra state saves per action; `sq stats reviews` reads frontmatter only).
- **F004 (observation hooks):** fixed. Dedupe set is owned by the capture helper and passed to `price_usage`; `UsageRecord.partial` marks an interrupted turn and `sq stats` shows `*`; cancellation row added (propagates, no record written).
