---
docType: review
layer: project
reviewType: slice
slice: effort-calibration-and-producer-model-effectiveness
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/176-slice.effort-calibration-and-producer-model-effectiveness.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261015
dateUpdated: 20261015
reviewedSha: 39032f2d4e462cce36ea9b7b932112addc0d16e2
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
turns: 6
promptTokens: 362912
cachedTokens: 267831
cacheWriteTokens: 95071
completionTokens: 4772
durationSeconds: 44.2
costUsd: 0.455471
costBasis: provider
runId: run-20261015-p4-08d36a4f
squadronVersion: 0.22.0
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Layering and dependency direction match the architecture"
    location: "project-documents/user/slices/176-slice.effort-calibration-and-producer-model-effectiveness.md#Architecture"
  - id: F002
    severity: pass
    category: scope
    summary: "Split of #210 is consistent with the slice plan and scope boundaries"
    location: "project-documents/user/slices/176-slice.effort-calibration-and-producer-model-effectiveness.md#D1"
  - id: F003
    severity: concern
    category: architectural-principles
    summary: "Task attribution anchors on commit subject text, against the project rule on user-accessible labels"
    location: "project-documents/user/slices/176-slice.effort-calibration-and-producer-model-effectiveness.md#D5"
  - id: F004
    severity: concern
    category: error-handling
    summary: "The \"one git log pass\" bound contradicts the per-slice git calls D5 and D6 require"
    location: "project-documents/user/slices/176-slice.effort-calibration-and-producer-model-effectiveness.md#D6"
  - id: F005
    severity: concern
    category: integration
    summary: "Phase-step-to-loop-step join in the producer report is under-specified"
    location: "project-documents/user/slices/176-slice.effort-calibration-and-producer-model-effectiveness.md#D8"
  - id: F006
    severity: concern
    category: proportionality
    summary: "Heavier than the slice needs; candidates to cut or defer"
    location: "project-documents/user/slices/176-slice.effort-calibration-and-producer-model-effectiveness.md#Technical-Scope"
  - id: F007
    severity: note
    category: nfr
    summary: "No NFR in the parent architecture applies"
    location: "project-documents/user/architecture/140-arch.pipeline-foundation.md"
---

# Review: slice — slice 176

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Layering and dependency direction match the architecture

The report cores sit in `stats/`, take injected inputs (`StateManager`, `GitHistory`) and import no Typer. `stats/git_history.py` is the only module that runs git. The only persisted-schema change is three defaulted `StepState` fields, and the doc commits to updating the state-file section of `140-arch.pipeline-foundation.md` when it lands. That matches the arch's State Manager responsibility and 175's no-version-bump precedent.

### [PASS] Split of #210 is consistent with the slice plan and scope boundaries

Slice plan entry 32 leaves two questions to the design: whether (b) splits, and whether an eval tool is adopted. D1 answers both. Entry 33 exists and carries the replay and judge scope, and the arch's "cost optimization" exclusion still holds because this slice only reports cost. The slice plan entry already reflects the split and the lowered effort (3/5).

### [CONCERN] Task attribution anchors on commit subject text, against the project rule on user-accessible labels

D5 makes exact commit-subject matches the structural anchors for task groups. Window selection and the `merge: slice {index}…` lookup match message text in the same way. Project guidance says never to use user-accessible labels as logical structure, and to prefer lenient parsing over exact matching. The doc acknowledges the heuristic (Risk Assessment), but it doesn't say why a more robust anchor doesn't work, or whether this is a deliberate exception. A commit message reworded during a rebase turns into `marker not found`. Add an explicit justification and exception to D5. Or key groups on something structural, such as a `Task-Id:` trailer going forward, and use subjects only as a fallback for older slices.

### [CONCERN] The "one git log pass" bound contradicts the per-slice git calls D5 and D6 require

D6 says one report invocation runs one `git log --name-status` pass plus one `git show` per review version. D5, though, needs the following for each slice, and `sq stats slices` runs it across every completed slice:
- a branch lookup
- the commit that added the task file
- a `first-parent` range log
- a merge-commit search
- the commit that first added the review artifact

That is O(slices) git calls, each with its own timeout. The doc never says how many calls this makes. The tested bound ("a test asserts the count") therefore can't be met as written, and D9's "never a partial report" means one hung call on one old slice kills the whole rollup. Restate the bound honestly, for example a fixed number of whole-history passes with the window derived in memory. Alternatively, state the per-slice call count and an overall time or call budget.

### [CONCERN] Phase-step-to-loop-step join in the producer report is under-specified

The unit is "a phase step together with the loop step that follows it in the same run." The architecture defines a phase step as expanding to cf-op → dispatch → review → checkpoint → commit, with the loop declared as step config. The doc doesn't say whether the loop is a separate `StepState` or fields on the phase step. Nor does it say how "follows" is determined across `each` collections or `--from` adoption, or how the reviewer model is taken from "the phase step's review action" when rounds live in `prior_round_results`. This join determines the producer config key and every rate in the report. Specify the exact linkage and add a failure row for a phase step with no resolvable review action or a missing follower.

### [CONCERN] Heavier than the slice needs; candidates to cut or defer

The slice delivers D3 persistence, three parsers, a git reader, four subcommands with `--json`, and a 12-row failure table. That is a lot for 3/5. Named cuts that don't drop plan-assigned scope:
- **`merge` window source.** Local slice branches are never deleted per project rules, so `branch` covers the main case. Drop `merge` and mark that slice `none`.
- **Shallow-clone handling.** This is a warning plus footer for a case this single-developer repo doesn't have.
- **`schema_version` on every JSON report.** The doc itself says the cross-project contract waits until something consumes it.
- **Per-task `Effort` summing (D2).** It is parsed, summed and rendered, but the doc says none of 160–175 carry per-task effort. Keep it only if it is cheap.

Also reconsider the two partial-failure contradictions in D9. A shallow clone yields a report, yet a single missing object on `git show` aborts the entire rollup, while an unreadable frontmatter merely skips a round. Choose one policy, skip with a counted WARNING or fail, for old review versions.

### [NOTE] No NFR in the parent architecture applies

The architecture states no latency or throughput targets for reporting paths, so there is nothing to restate. Given the O(slices) git behavior noted above, the slice may want to set its own target for `sq stats slices` on this repo's history.

### Run Digest

- Response length: 6367 chars
- Response is newline-free: no
- Tool calls made: 5
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 6
- Tokens — prompt / cached / cache write / completion / reasoning: 362912 / 267831 / 95071 / 4772 / not computed
- Duration: 44.2 s
- Cost: $0.46 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
