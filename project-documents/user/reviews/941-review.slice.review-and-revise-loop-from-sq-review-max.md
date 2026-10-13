---
docType: review
layer: project
reviewType: slice
slice: review-and-revise-loop-from-sq-review-max
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/941-slice.review-and-revise-loop-from-sq-review-max.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261012
dateUpdated: 20261012
reviewedSha: d550827276e811f47a96be7b263c18666824babb
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
durationSeconds: 25.4
runId: run-20261013-p4-55015267
squadronVersion: 0.21.6
findings:
  - id: F001
    severity: concern
    category: scope
    summary: "MCP parity assigned by the slice plan is dropped"
    location: "project-documents/user/slices/941-slice.review-and-revise-loop-from-sq-review-max.md#Technical Scope"
  - id: F002
    severity: concern
    category: error-handling
    summary: "Failure modes of the new execution path are only partly enumerated"
    location: "project-documents/user/slices/941-slice.review-and-revise-loop-from-sq-review-max.md#D5 — Exit codes match `sq review`"
  - id: F003
    severity: concern
    category: dependencies
    summary: "Import cycle and private-symbol coupling between `review.py` and the new CLI module"
    location: "project-documents/user/slices/941-slice.review-and-revise-loop-from-sq-review-max.md#Interfaces Required"
  - id: F004
    severity: concern
    category: proportionality
    summary: "Some surface area looks speculative or heavier than needed"
    location: "project-documents/user/slices/941-slice.review-and-revise-loop-from-sq-review-max.md#Provides to Other Slices"
  - id: F005
    severity: note
    category: architecture
    summary: "Alignment with the 900 architecture is otherwise good"
    location: "project-documents/user/architecture/900-arch.maintenance-and-refactoring.md"
---

# Review: slice — slice 941

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] MCP parity assigned by the slice plan is dropped

The plan entry for 941 says "The `/sq:review` slash command and MCP get the same option (interface parity)". The slice excludes MCP because Squadron has no MCP review tool, only an MCP client (`tools/mcp_bridge.py`, `tools/cf_tools.py`). The reasoning is sound, but the exclusion contradicts the plan entry and is not recorded there. Update the 900 slice plan entry to drop the MCP item, or record the deferral. The slice also has to say what happens if an MCP review tool is added later. Without that, the plan and the design disagree.

### [CONCERN] Failure modes of the new execution path are only partly enumerated

D5 maps three outcomes to exit codes (PASS or accepted, FAIL or exhausted, dispatch or save failure). The design runs multi-round model calls and git commits, but it does not say what happens in these cases:
- A reviewer or reviser call hangs or times out mid-round. The design does not say whether the pipeline's own timeouts apply, which exit code results, or what is logged.
- The user interrupts the run (Ctrl-C) during a revise. The artifact may be edited but uncommitted. "Special Considerations" covers rerunning, but not how to treat leftover uncommitted edits.
- A git commit fails after a successful revise, for example on a hook failure or a dirty tree. The design does not say whether this exits 1.
- The working tree already has unrelated uncommitted changes when `commit_each_iteration` runs. The design does not say whether they get swept into the revision commit or the run is refused.

The project's failure-mode rule wants each of these observable (WARNING-level log or equivalent) and covered by at least one test asserting the signal. Add a short failure-mode table, or state which cases are inherited unchanged from `execute_pipeline`. The Technical Requirements tests should assert the observable signal for at least one of them.

### [CONCERN] Import cycle and private-symbol coupling between `review.py` and the new CLI module

`cli/commands/review.py` branches into `cli/commands/review_revise.py`. The slice's own interface table also has `review_revise.py` consuming `_resolve_model`, a private function in `review.py`. That is a circular dependency and a reach into another module's internals. Pass the resolved reviewer into `run_review_revise` (the `reviewer` parameter already exists), or move `_resolve_model` into a shared module. The design should pick one, so the new module does not import from `review.py`.

### [CONCERN] Some surface area looks speculative or heavier than needed

- "Provides to Other Slices" advertises `build_review_revise_definition` for a hypothetical future pipeline step. No consumer exists, so cut this paragraph.
- D6 refuses a long list of named options (about 14) by hand. A single table-driven check against the options that `--max` does support (`--model`, `--revise-model`, `-v`, `--cwd`) would remove the per-option enumeration. It would also stay correct as new options are added.
- Two new modules, a kind-to-pipeline table and a composed-definition builder are reasonable for the stated reuse of the loops. The extra weight is in the speculative provides and the option enumeration above.

### [NOTE] Alignment with the 900 architecture is otherwise good

The 900 architecture says small conveniences over existing commands belong in this initiative, and this slice fits that. It adds no new feature area and changes no pipeline files. Dependencies run from the CLI to the pipeline package. The slice relies on `load_pipeline` for the loop definitions and does not duplicate them, which meets the DRY and "pipeline knowledge stays in the pipeline package" principles. The 900 architecture states no NFRs, so there are none to restate. The options for `arch` and for kinds with no loop are handled explicitly, as the plan requires.

### Run Digest

- Response length: 4589 chars
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
- Duration: 25.4 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5
