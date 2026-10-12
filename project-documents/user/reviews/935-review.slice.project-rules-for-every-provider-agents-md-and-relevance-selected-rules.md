---
docType: review
layer: project
reviewType: slice
slice: project-rules-for-every-provider-agents-md-and-relevance-selected-rules
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/935-slice.project-rules-for-every-provider-agents-md-and-relevance-selected-rules.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261012
dateUpdated: 20261012
reviewedSha: 73deaab9ae0305acd7ed7427da82ea7518334eed
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
durationSeconds: 28.9
squadronVersion: 0.21.5
findings:
  - id: F001
    severity: concern
    category: scope
    summary: "Slice size and mechanism count exceed a maintenance-initiative slice"
    location: "project-documents/user/slices/935-slice.project-rules-for-every-provider-agents-md-and-relevance-selected-rules.md#Technical Scope"
  - id: F002
    severity: concern
    category: dependency-direction
    summary: "Dependency direction: the shared package needs `review.rules.resolve_rules_dir`"
    location: "project-documents/user/slices/935-slice.project-rules-for-every-provider-agents-md-and-relevance-selected-rules.md#Interfaces Required"
  - id: F003
    severity: concern
    category: under-specification
    summary: "Reviewer capabilities are undefined, so a stated success criterion can't be verified"
    location: "project-documents/user/slices/935-slice.project-rules-for-every-provider-agents-md-and-relevance-selected-rules.md#Data Flow"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Failure modes for new I/O paths are only partly enumerated"
    location: "project-documents/user/slices/935-slice.project-rules-for-every-provider-agents-md-and-relevance-selected-rules.md#Technical Decisions"
  - id: F005
    severity: note
    category: process
    summary: "Fixes-slice routing"
    location: "project-documents/user/slices/935-slice.project-rules-for-every-provider-agents-md-and-relevance-selected-rules.md#Overview"
  - id: F006
    severity: pass
    category: architecture
    summary: "Boundaries, SDK handling and recording are well reasoned"
    location: "project-documents/user/slices/935-slice.project-rules-for-every-provider-agents-md-and-relevance-selected-rules.md#D4"
---

# Review: slice — slice 935

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Slice size and mechanism count exceed a maintenance-initiative slice

The architecture (900) is a container for tech debt, fixes and "small conveniences over existing commands, files and config". It explicitly excludes new feature areas. This slice fixes two issues (#181 and #182), but it adds a new package with four modules and two new rule-frontmatter keys. It also adds a capability model, a per-provider native-loading table, `@` import resolution, a size-budget config key and a new artifact contract (`ConventionsSource`). The design rates its effort 3/5. Several parts are not needed to close the two issues and could be cut or deferred:
- `requires` and the whole capability derivation. This includes the tool-name-to-capability table and the codex sandbox mapping. The only stated consumer is "a `requires: [shell]` rule never reaches a read-only reviewer", and no existing rule uses `requires`. `steps` alone covers the relevance selection.
- The `dispatch` step kind and `RULES_STEP_PARAM` plumbing. They could be limited to the phase steps.
- `@` import resolution with a depth limit and cycle handling. It is only needed once a project has a `CLAUDE.md` that is just `@AGENTS.md`. It could be deferred behind the context-forge#116 work the design already cites.

Pick the lighter option: ship conventions discovery, `steps` filtering and recording first. Defer `requires` and import resolution until a real rule or project needs them.

### [CONCERN] Dependency direction: the shared package needs `review.rules.resolve_rules_dir`

D1 makes `squadron.project_rules` the shared layer, with review and pipeline dispatch both consuming it. But rules-directory resolution (`resolve_rules_dir`) stays in `review/`. `select_project_rules` needs the rules directory. The design never says who resolves it for a dispatch. Either `project_rules` imports from `review` (inverting the layering) or pipeline dispatch imports a review module. Specify where directory resolution lives. The simplest fix is to move it into `project_rules` and leave a re-export in `review.rules`, or to have `RuleContext` carry the resolved directory.

The package also appears to depend on `tools.effective`, `tools/builtin/_shared.py` constants and `StepTypeName`. `RuleStep` is a separate enum from `StepTypeName`, and no mapping between them is defined. State the intended import direction and the mapping.

### [CONCERN] Reviewer capabilities are undefined, so a stated success criterion can't be verified

The Review flow filters language rules by "the reviewer's capabilities" without saying how those are derived. D5 defines capabilities only for non-SDK tools and for the codex sandbox, and codex read-only yields `{read, shell}`. The success criterion "a `requires: [shell]` rule never reaches a read-only reviewer" conflicts with that table, because a read-only codex reviewer has `shell`. Define the review capability source for each reviewer type, or drop `requires` from review (see the proportionality finding).

### [CONCERN] Failure modes for new I/O paths are only partly enumerated

Handled explicitly:
- an unreadable rule file (WARNING plus `dropped`)
- a `git ls-files` failure (raises)
- an unresolved `@` import (WARNING)
- an over-budget conventions file (fails)
- an unknown frontmatter value (raises)

Not addressed:
- An unreadable conventions file (`OSError`, permissions, a broken symlink) in either dispatch or review. Say whether it fails or is recorded.
- Which dispatch or review call sites get a test that asserts the observable signal for each failure. The Technical Requirements cover selection and budget paths, but not the `git ls-files` timeout, the unreadable-rule WARNING or the unresolved-import WARNING.
- Whether one typo'd `steps` value in a single rule file fails every dispatch and review in the project. That may be intended (fail fast), but state it, since it widens the blast radius of a frontmatter edit.

### [NOTE] Fixes-slice routing

The project rules say fixes never get their own slice and larger ones go to slice 944. This slice is justified as feature-like: new frontmatter keys and a new artifact contract. If the PM treats #181 and #182 as fixes, only a reduced version (conventions discovery plus recording) would fit the routing. This relates to the scope concern above.

### [PASS] Boundaries, SDK handling and recording are well reasoned

- The design keeps SDK native loading and gives a concrete reason (`settings.json` and the #155 connect-time prompt).
- It keeps the migration behavior-preserving, with the existing review tests required to pass unchanged.
- It uses enums for comparison values, and it gives each persisted record a concrete schema.
- No NFR from the parent architecture applies to this path.

### Run Digest

- Response length: 5775 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 28.9 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6

## Response (20261012)

- **F001:** accepted. Cut `requires` and the capability model (#204) and `@` import resolution (#205). With AGENTS.md chosen first, the import case the design cited can't occur. The `dispatch` step kind stays: one table entry.
- **F002:** fixed. `RuleContext` carries the resolved `rules_dir`. `project_rules` imports nothing from `review` or `pipeline`. The pipeline-side glue (`StepTypeName` → `RuleStep` map, native-loading table) lives in a new `pipeline/actions/dispatch_rules.py`.
- **F003:** resolved by the F001 cut. No capability filtering remains.
- **F004:** fixed. Unreadable conventions file → error naming the path. A bad `steps` value fails everything that loads the directory, on purpose, and the design now says so. Added a failure-mode table, with one test per row.
- **F005:** no change. The PM routed #181/#182 to a slice.
