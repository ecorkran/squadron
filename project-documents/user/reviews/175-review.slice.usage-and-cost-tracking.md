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
reviewedSha: 8e310f5db337ab9676d8dd7683a79fe4205ad049
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 6
durationSeconds: 33.1
runId: run-20261015-p4-733c0a5c
squadronVersion: 0.21.9
findings:
  - id: F001
    severity: concern
    category: scope-alignment
    summary: "Plan-assigned MCP parity is dropped, and the architecture still lists cost tracking as out of scope"
    location: "project-documents/user/slices/175-slice.usage-and-cost-tracking.md#Technical Scope"
  - id: F002
    severity: concern
    category: proportionality
    summary: "The design is heavy for one slice and has cuttable scope"
    location: "project-documents/user/slices/175-slice.usage-and-cost-tracking.md#Technical Scope"
  - id: F003
    severity: concern
    category: error-handling
    summary: "Failure modes for the new `sq stats` read paths are not enumerated"
    location: "project-documents/user/slices/175-slice.usage-and-cost-tracking.md#Technical Requirements"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Failure and interrupt paths for step duration and session telemetry are underspecified"
    location: "project-documents/user/slices/175-slice.usage-and-cost-tracking.md#D6"
  - id: F005
    severity: pass
    category: architecture-alignment
    summary: "Layering and dependency direction match the architecture"
    location: "project-documents/user/slices/175-slice.usage-and-cost-tracking.md#Component Structure"
  - id: F006
    severity: note
    category: nfr
    summary: "No architecture NFR applies to these paths"
    location: "project-documents/user/slices/175-slice.usage-and-cost-tracking.md"
---

# Review: slice — slice 175

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Plan-assigned MCP parity is dropped, and the architecture still lists cost tracking as out of scope

The slice plan entry (item 31) tells the design to settle "a reporting surface (`sq stats` or similar, CLI, slash command, and MCP identical)". The design excludes the MCP tool and defers it to an issue "logged when this design is approved". It gives a reason (no MCP server exists). Even so, dropping plan-assigned scope is a CONCERN. The plan entry or the PM should record the deferral, so the plan and the design don't disagree.

The architecture (`140-arch`, "Out of Scope (future, unscheduled)") lists "Cost tracking and optimization across providers". The architecture's `dispatch` row only owns "token tracking". This slice adds cost computation, pricing precedence, and a stats command group. The plan entry authorizes this, but the architecture document was not updated, and the design never acknowledges the conflict. Add one line to the slice, or amend the architecture, saying that cost reporting is now in scope and that cross-provider cost *optimization* (pool ranking) remains out.

### [CONCERN] The design is heavy for one slice and has cuttable scope

The slice bundles 12 items across every provider seam, the executor, run state, review artifacts, metrology, three CLI subcommands, a slash command, a skill, two live-probe/measurement walkthroughs, and a README/CHANGELOG pass. The plan itself rates it Risk Med and Effort 4/5, and D12 already split off the payoff reports.

Candidates to cut or defer:
- `sq stats runs` filter set (`--pipeline`, `--status`, `--since`, `--slice`) plus `reviews --dir`. Nothing downstream consumes these yet, and one filter or two would meet the stated value.
- The separate slash command and agents skill. Both only wrap `sq stats $ARGUMENTS`, and the MCP parity they stand in for is already deferred.
- `AuditRun.usage` (item 7). Its only consumer is the D10 #34 walkthrough, which is an operator measurement and not a task gate. It could ride with the #34 follow-up.
- The #173 gemini probe (D11). It is conditional on an API key and has no dependency on the capture layer.
- `StepState.duration_seconds` alongside `UsageRecord.duration_seconds` (D6). Two durations are kept "because they answer different questions", but the step-level one serves only the deferred #210 report.

### [CONCERN] Failure modes for the new `sq stats` read paths are not enumerated

The failure table covers usage parsing, pricing, and one malformed `metadata.usage`. It does not cover the new I/O paths the slice adds:
- `sq stats run <run_id>` with an unknown id, or a state file that is not valid JSON or is truncated.
- Reading a state file while a live run is writing it (the architecture's run-state storage is a plain JSON file per run).
- `sq stats reviews` hitting an artifact with unparseable frontmatter, or a `--dir` that does not exist.
- A run state file that is unreadable in `runs`, where it needs to be skipped with a signal and not abort the whole listing.

The "must be observable and tested" rule needs a row for each. The same applies to D11's live probe (timeout and 429/503 are mentioned, but the signal and the test are not).

### [CONCERN] Failure and interrupt paths for step duration and session telemetry are underspecified

Success criterion 4 sets `duration_seconds` only for "every completed step". D6 does not say what happens for a step that fails, is checkpointed or paused, or is interrupted by the 174 stall handling. D5 says failed actions record spend, and run totals include failed attempts. The step-level timing needs to follow the same rule, or the stats rows for failed loop iterations will show tokens with no time. Likewise, "a drain yields no `ResultMessage`" is called "not a failure" with no observable signal, so spend can be lost silently. Add at least a DEBUG or WARNING line and a test for it.

### [PASS] Layering and dependency direction match the architecture

`core/usage.py` stays a stdlib-only leaf. Providers report raw telemetry through shared metadata constants, and only `pipeline/usage_capture.py` attributes it to a model alias. Providers never build the alias-aware record. Capture rides the existing `ActionResult.metadata` and `asdict` persistence, and it reuses the `Action` protocol and the `ResolvedModel` resolver without changing them. The stats core is Typer-free and sits behind a thin CLI. Totals are computed at read time, so there is one source of truth. None of this violates the architecture's action, resolver, or state boundaries, and the events and `RunObserver` paths are untouched.

### [NOTE] No architecture NFR applies to these paths

`140-arch` states no latency or throughput targets for the dispatch, review, or state paths this slice touches, so nothing needs restating. If `sq stats runs` is expected to scan many files in `~/.config/squadron/runs`, a rough size or time expectation would help the cutting decision above. It is not required.

### Run Digest

- Response length: 5700 chars
- Response is newline-free: no
- Tool calls made: 6
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 33.1 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
