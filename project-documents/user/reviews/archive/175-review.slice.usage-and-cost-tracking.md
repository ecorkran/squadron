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
reviewedSha: 8155373526c47ff6169111e7625e0518bd598c98
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
durationSeconds: 32.1
runId: run-20261015-p4-733c0a5c
squadronVersion: 0.21.9
findings:
  - id: F001
    severity: pass
    category: architecture
    summary: "Layering and dependency directions follow 140-arch"
    location: "project-documents/user/slices/175-slice.usage-and-cost-tracking.md#Architecture"
  - id: F002
    severity: pass
    category: scope
    summary: "Scope boundary against \"Cost tracking and optimization across providers\" is stated explicitly"
    location: "project-documents/user/slices/175-slice.usage-and-cost-tracking.md#Technical Scope"
  - id: F003
    severity: concern
    category: proportionality
    summary: "Design is heavy for what the slice must deliver; several items can be cut or deferred"
    location: "project-documents/user/slices/175-slice.usage-and-cost-tracking.md#Technical Scope"
  - id: F004
    severity: concern
    category: integration
    summary: "Slash command and skill parity is assigned to this slice but the failure and ownership story for the wrappers is thin"
    location: "project-documents/user/slices/175-slice.usage-and-cost-tracking.md#Technical Scope"
  - id: F005
    severity: concern
    category: nfr
    summary: "Duration NFR and timing semantics are defined, but no overhead or write-path constraint is restated for the hot path"
    location: "project-documents/user/slices/175-slice.usage-and-cost-tracking.md#D6"
  - id: F006
    severity: concern
    category: error-handling
    summary: "Failure handling for the new `sq stats reviews` directory scan is specified, but the aggregate \"not recorded\" count is under-specified for pipeline reviews"
    location: "project-documents/user/slices/175-slice.usage-and-cost-tracking.md#D8"
  - id: F007
    severity: note
    category: dependencies
    summary: "Hidden dependency on `AuditRun` persistence is acknowledged and correctly bounded"
    location: "project-documents/user/slices/175-slice.usage-and-cost-tracking.md#Excluded"
  - id: F008
    severity: note
    category: error-handling
    summary: "Failure modes are enumerated well for the new I/O paths"
    location: "project-documents/user/slices/175-slice.usage-and-cost-tracking.md#Technical Requirements"
---

# Review: slice — slice 175

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Layering and dependency directions follow 140-arch

Providers report raw telemetry, and `pipeline/usage_capture.py` is the only place a `UsageRecord` is built. That is the right boundary: the Model Resolver owns alias, effort and budget, and the `dispatch` action owns "token tracking" (140-arch Core Action Types). `core/usage.py` stays a stdlib-only leaf. Persistence reuses the existing `ActionResult.metadata` → `asdict` path, so there is no new state schema and no change to the `Action` protocol. Capture is wired into the actions and does not add to `RunObserver` or the events dispatcher, which respects the "two notification paths" boundary.

### [PASS] Scope boundary against "Cost tracking and optimization across providers" is stated explicitly

140-arch lists cost tracking as future and unscheduled. The slice acknowledges this, points to the slice plan entry that brought cost *reporting* in, and keeps optimization out (pool ranking, budgets). The MCP deferral (#217) and the #214/#210 split (D12) match the slice plan entry's own notes.

### [CONCERN] Design is heavy for what the slice must deliver; several items can be cut or deferred

The slice has twelve decisions and ten included items. Four are tracking or closure work that the capture layer does not need:
- **#173 Gemini probe (item 10, D11).** It is a manual curl and a one-line flag flip with no shared code path. It is a separate chore and does not belong in a design that "touches every provider seam". Cut it from Included, or move it to a standalone fix under slice 944.
- **D10 (#34 investigation).** It is a decision section that only says "do it later, elsewhere". Fold it into the Excluded bullet that already covers #34.
- **#158 closure (item 7)** is a code-less issue close plus an always-`None` `cache_write` on the OpenAI reader. Fold it into the CHANGELOG/issue-closing step. It does not need an Included item.
- **Per-run `runs` and `reviews` subcommands plus `--slice` and `--json` on all three.** `run` and `reviews` cover the stated payoffs (#36, #172, #34 diagnosis). `runs` with `--slice` is the aggregation that #214 consumes, and #214 is deferred. Consider deferring `runs` to the follow-on slice, or justify it by naming a requirement it meets in this slice.

The slice also restates material from other documents: the full 931 D10 frontmatter table reference, the SDK `ResultMessage` field list and the `ModelUsage` fields. Link to those instead.

### [CONCERN] Slash command and skill parity is assigned to this slice but the failure and ownership story for the wrappers is thin

Item 9 adds `commands/sq/stats.md` and `commands/agents/sq-stats/SKILL.md`. Success criterion 10 requires "output identical to the CLI". The doc defines no test or mechanism that could check this, since the wrappers just run `sq stats $ARGUMENTS`. The failure table also has no row for a wrapper invoked when `sq` is not installed or is the wrong version. Either drop criterion 10 as untestable and rely on the existing install-commands convention, or state how identity is verified.

### [CONCERN] Duration NFR and timing semantics are defined, but no overhead or write-path constraint is restated for the hot path

The slice adds a record to every action. It also adds a read-and-parse of every run file for `sq stats runs`, which loads every run in `~/.config/squadron/runs`. 140-arch states no latency target for either path, and 174 (already a prerequisite) set listing and rendering behavior for run files. The slice should say that `sq stats runs` reuses `scan_runs` and 174's listing bounds (or name a limit), so a large run history does not make the command unbounded. Without that, the new read path has no stated cost bound.

### [CONCERN] Failure handling for the new `sq stats reviews` directory scan is specified, but the aggregate "not recorded" count is under-specified for pipeline reviews

D8 says pipeline reviews appear in `sq stats reviews` and also under their run, so the two views are never summed together. That makes `sq stats reviews` totals and `sq stats runs` totals overlap by design. No de-duplication or marker lets a reader tell a pipeline-originated artifact from a standalone one. The doc does not say what `reviews` total means to a user who ran both. Either add a column or a flag to separate them, or restrict `reviews` to standalone `sq review` runs. The doc already describes it as covering "standalone `sq review` runs".

### [NOTE] Hidden dependency on `AuditRun` persistence is acknowledged and correctly bounded

The deferral to #33 and #34 is explicit. The SDK agent stamps audit usage on the message, so the later change is small. This is a clean boundary, not an under-specification.

### [NOTE] Failure modes are enumerated well for the new I/O paths

The failure table covers missing or malformed usage, partial pricing, an unknown run id, torn reads (via atomic replace), a missing review directory and unreadable frontmatter. Each row has a signal and a stated test requirement. The interrupt-drain case (D5) ties into 174's behavior with a named WARNING. This meets the Failure-Mode Enumeration rule.

### Run Digest

- Response length: 6379 chars
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
- Duration: 32.1 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
