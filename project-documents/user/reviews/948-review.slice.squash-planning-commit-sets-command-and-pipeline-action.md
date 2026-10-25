---
docType: review
layer: project
reviewType: slice
slice: squash-planning-commit-sets-command-and-pipeline-action
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/948-slice.squash-planning-commit-sets-command-and-pipeline-action.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261025
dateUpdated: 20261025
reviewedSha: acf189623c17736c51aefe7ff32d7a70c15e539a
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
turns: 5
promptTokens: 154330
cachedTokens: 77579
cacheWriteTokens: 76745
completionTokens: 3688
durationSeconds: 46.4
costUsd: 0.352363
costBasis: provider
squadronVersion: 0.24.1
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Fits the 900 maintenance charter and the slice plan entry"
    location: "project-documents/user/slices/948-slice.squash-planning-commit-sets-command-and-pipeline-action.md#Technical Scope"
  - id: F002
    severity: pass
    category: architecture-alignment
    summary: "Dependency direction and layering are sound"
    location: "project-documents/user/slices/948-slice.squash-planning-commit-sets-command-and-pipeline-action.md#Component Structure"
  - id: F003
    severity: concern
    category: error-handling
    summary: "Post-rewrite tree check contradicts \"nothing is rewritten\""
    location: "project-documents/user/slices/948-slice.squash-planning-commit-sets-command-and-pipeline-action.md#D3 Refusals are explicit failures"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Failure modes miss the commit step and observability"
    location: "project-documents/user/slices/948-slice.squash-planning-commit-sets-command-and-pipeline-action.md#Failure Modes"
  - id: F005
    severity: concern
    category: under-specification
    summary: "Pipeline integration is under-specified and the doc contradicts itself"
    location: "project-documents/user/slices/948-slice.squash-planning-commit-sets-command-and-pipeline-action.md#D6 Pipeline placement"
  - id: F006
    severity: concern
    category: correctness
    summary: "DEVLOG.md in the path set can absorb unrelated commits"
    location: "project-documents/user/slices/948-slice.squash-planning-commit-sets-command-and-pipeline-action.md#Dependencies"
  - id: F007
    severity: concern
    category: proportionality
    summary: "Proportionality and descriptive inconsistencies"
    location: "project-documents/user/slices/948-slice.squash-planning-commit-sets-command-and-pipeline-action.md#Complexity"
  - id: F008
    severity: note
    category: under-specification
    summary: "The `--dry-run` output is not defined"
    location: "project-documents/user/slices/948-slice.squash-planning-commit-sets-command-and-pipeline-action.md#Technical Scope"
---

# Review: slice — slice 948

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Fits the 900 maintenance charter and the slice plan entry

The slice covers what plan entry 42 assigns. That is the `sq squash` command, the `squash` pipeline action, refusal on a dirty tree, off the target, on a pushed commit and on a tree change, the backup tag, the out-of-scope list, and `sq metr` as Part B. It adds a small convenience over existing git and planning-file workflows, which the 900 architecture's scope section allows. The 900 architecture sets no ordering requirement. The "Sequencing relative to the 400s" section is consistent with that.

### [PASS] Dependency direction and layering are sound

The CLI command and the pipeline action both depend on one shared `pipeline/squash.py`. `plan_squash` and `apply_squash` take the target and cwd as arguments, so they do not read config themselves. Extracting the path-set function from `commit_plan.py` for both callers removes the drift risk. Using real temporary git repositories in the tests follows the project's failure-mode and testing rules.

### [CONCERN] Post-rewrite tree check contradicts "nothing is rewritten"

D3 says every listed refusal stops with "nothing … rewritten". The tree-id check compares the tree before and after the rewrite, so it can only trip after `reset --soft` and `commit`. At that point history has already changed. The design then says "the tag is the way back". Either the command restores the old HEAD itself when the check trips, or it leaves the rewrite in place, and D3 and the Failure Modes section must say which. The user also needs to know what state the tree is left in.

### [CONCERN] Failure modes miss the commit step and observability

The section covers git returning `None` and a kill between reset and commit. It does not cover `git commit -C` failing for another reason, such as a pre-commit hook, a signing requirement or an empty commit. That leaves the index staged on the run's parent, which is the same state as the killed-process case but reached through an ordinary error. The project rule requires each failure mode to be observable, meaning a WARNING-level log or a metric. It also requires at least one test that asserts the signal. The design only says "exits non-zero" or "fails the step". It does not name logging, and the Tests list asserts outcomes without asserting a logged signal. The rule also needs the same observable-failure handling for the case where the run reaches the root commit and there is no parent to reset to.

### [CONCERN] Pipeline integration is under-specified and the doc contradicts itself

Slice plan entry 42 assigns "the planning pipelines" to this slice. D6 defers the question of which pipelines need the step ("Design check for tasks: which shipped pipelines inline P4's or P5's loop"). Sequencing then says "two pipeline YAMLs". The design also never says how the action obtains `subject` and the slice index. It could take them from step params, the cf slice, or the `each` item. The case where an `each` step runs the planning loop over many slices, so several runs are squashed in sequence, is also not described. Resolve the pipeline list and the parameter source here, because they decide the action's interface.

### [CONCERN] DEVLOG.md in the path set can absorb unrelated commits

`DEVLOG.md` is in every artifact's set, and detection is by file alone (D2). A DEVLOG-only commit from other work, or a commit made for a different artifact that touched only DEVLOG, would be treated as part of this artifact's run. It would then be folded into the squash, or it would become the "first commit" whose message and author survive. D5 and the test list ("DEVLOG-only touches stay in the set") assume this is acceptable. The design should state the rule that prevents it, for example requiring that the run's first commit touches an artifact file. Otherwise it should state that the absorption is accepted.

### [CONCERN] Proportionality and descriptive inconsistencies

The Complexity section says "about five new modules". The Component Structure section lists three new modules plus one extraction. The count should be reconciled. The design does not say Part B (`sq metr`) lands as its own commit. The 900 guidelines allow grouped slices only when "each item commits separately and can be reverted without touching the others". Add that statement. Backup tags are never deleted by the command (D4), so they accumulate on every squash and every pipeline run. A line on cleanup, or on an explicit decision to leave them, would stop this from being a hidden cost. Nothing else here looks cuttable.

### [NOTE] The `--dry-run` output is not defined

The scope lists `--dry-run`, but the design never says what it prints. A natural output is the commits in the run and the surviving message. The pipeline action also has no dry-run mapping, even though pipelines already have a `--dry-run` mode. This is minor and can be settled in the task breakdown.

### Run Digest

- Response length: 6198 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 5
- Tokens — prompt / cached / cache write / completion / reasoning: 154330 / 77579 / 76745 / 3688 / not computed
- Duration: 46.4 s
- Cost: $0.35 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
