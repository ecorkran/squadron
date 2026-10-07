---
docType: review
layer: project
reviewType: slice
slice: pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/199-slice.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261006
dateUpdated: 20261006
reviewedSha: d50272e5a201fe494179ad84cff612529f3dace0
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 7
durationSeconds: 42.8
runId: run-20261007-p4-08b6c078
squadronVersion: 0.20.1
findings:
  - id: F001
    severity: concern
    category: integration
    summary: "D3 \"listing and resume cannot disagree\" is overstated for item resume"
    location: "project-documents/user/slices/199-slice.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md#D3"
  - id: F002
    severity: concern
    category: error-handling
    summary: "Failure-mode table omits cases for the new filesystem read paths"
    location: "project-documents/user/slices/199-slice.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md#D7"
  - id: F003
    severity: concern
    category: design
    summary: "Free-text `resume_problem` and display markers carry logical meaning"
    location: "project-documents/user/slices/199-slice.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md#API Contracts"
  - id: F004
    severity: concern
    category: dependencies
    summary: "Under-specified shared location and command-to-command dependency"
    location: "project-documents/user/slices/199-slice.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md#Component Structure"
  - id: F005
    severity: note
    category: nfr
    summary: "No stated performance target for the listing"
    location: "project-documents/user/slices/199-slice.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md#Special Considerations"
  - id: F006
    severity: note
    category: scope
    summary: "Capability is not reflected in the parent architecture"
    location: "project-documents/user/architecture/180-arch.pipeline-intelligence.md"
  - id: F007
    severity: pass
    category: architecture
    summary: "Layering, dependency direction and read-only design"
    location: "project-documents/user/slices/199-slice.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md#Architecture"
---

# Review: slice — slice 199

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] D3 "listing and resume cannot disagree" is overstated for item resume

D3 and the Technical Requirements say the listing and the resume path "cannot disagree". Only `RESUMABLE_OUTCOMES` is shared. Item resume (slice 197, `item_resume._validate`) also rejects a run in these cases:
- Its pipeline doesn't have exactly one `each` step (`_single_each_step`).
- `--decision accept` is used on a record whose `flagKind` isn't `review_unresolved` (`_check_record`).

The listing counts any `flagged` or `not_run` record in any `<run_id>.*.report.json`. A completed run could therefore show as "N items" and then be rejected by `--item`. Several reports in one run (more than one `each` step) would also be summed, yet `ResumePoint` carries a single `step_name`. The hint line always advertises `retry|accept`. The doc should do one of two things:
- Share the eligibility check with `item_resume`, including the `each`-step rule.
- Narrow the claim and say how a multi-report run is shown.

### [CONCERN] Failure-mode table omits cases for the new filesystem read paths

The table covers corrupt state, a missing pipeline, and an unreadable report. It leaves out these cases:
- **Concurrent writer:** a running pipeline (per-checkout run lock, slice 197) writes state or a report while `sq runs list` reads. A torn read would surface as a skipped row or `<report unreadable>`. The doc should say whether this is accepted as transient and logged, or handled.
- **Paused or failed run with no unfinished step:** `first_unfinished_step_of` returns `None` when the pipeline was edited after the run. D7 doesn't say whether such a run gets `resume=None` and is dropped from the default view or gets a marker. Silently hiding a paused run contradicts the "no silent fallback" principle.
- **Exceptions that make a definition "invalid":** `load_pipeline` can raise several types. The doc should name them. The Exception Handling rule needs narrow catches.
- **Orphaned `running` runs:** a crashed run is neither listed by default nor resumable by `_RESUMABLE_STATUSES`. The doc should say that is intended.
- **Test coverage:** the Technical Requirements require unit tests for the first two D7 rows, but none asserts the WARNING itself (log or metric). The architecture review criteria require at least one such test.

### [CONCERN] Free-text `resume_problem` and display markers carry logical meaning

`RunSummary.resume_problem: str | None` holds the D7 marker text (`<pipeline unavailable>`, `<report unreadable>`). Those strings are user-visible labels. The project rule says never use user-accessible labels as logical structure, and the doc applies that discipline to `ResumeKind` but not here. A `ResumeProblem` enum, rendered to text only in the CLI, is the consistent design. `status: str` should likewise be an `ExecutionStatus`, or the doc should justify the string. The "resumable even with a marker" logic in D7 also depends on this field.

### [CONCERN] Under-specified shared location and command-to-command dependency

`_STATUS_COLORS` moves from `run.py` to "a shared location" that the doc doesn't name. `run.py` also imports `render_pipeline_listing()` from `commands/pipelines.py`, which makes one command module depend on another. Name the shared module, and consider putting the rendering helpers in a CLI-level module that both command files import.

### [NOTE] No stated performance target for the listing

The parent architecture states no NFR for listing paths, so nothing is violated. The slice adds one pipeline load per paused or failed run and one report glob per completed run. It sets no latency target and no bound on unbounded filesystem I/O. "Acceptable at current run counts" is implicit. Consider giving a rough target (for example, under 1s at a few hundred runs). Also consider memoizing pipeline definitions per name within one call, which is cheap and needs no cross-call cache.

### [NOTE] Capability is not reflected in the parent architecture

The architecture documents 197's `sq run --resume --item` as the Amoeba or human interface. It has no listing surface for finding runs that need a decision, and its CLI scope names only `sq pools`. The slice's value (finding resumable batch runs) follows from 197. Still, add a one-line mention in the architecture's 197 bullet so that `sq pipelines list`, `sq runs list` and `run_listing` don't count as scope creep. The "Provides to Other Slices" claim that Amoeba can use `list_run_summaries` "without parsing CLI output" also sits oddly beside the exclusion of `--json` because "no consumer needs JSON yet". An out-of-process orchestrator can only use the Python API by importing it.

### [PASS] Layering, dependency direction and read-only design

- Pure listing logic sits in `pipeline/run_listing.py`, and rendering stays in the CLI.
- `StateManager` is injected for testability.
- The slice consolidates `RESUMABLE_OUTCOMES`, `first_unfinished_step_of` and `report_json_paths` rather than duplicating them.
- It reuses 197's `BatchReportLoadError` instead of treating a bad report as "no open items".
- The parent field points at the slice plan (`180-slices.pipeline-intelligence.md`), which exists.

### Run Digest

- Response length: 6493 chars
- Response is newline-free: no
- Tool calls made: 7
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 42.8 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
