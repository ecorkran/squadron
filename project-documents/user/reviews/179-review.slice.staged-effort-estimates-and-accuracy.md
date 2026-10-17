---
docType: review
layer: project
reviewType: slice
slice: staged-effort-estimates-and-accuracy
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/179-slice.staged-effort-estimates-and-accuracy.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261016
dateUpdated: 20261016
reviewedSha: 6564618f7c4a10c0b8c315e46e2b2fdc80a137bd
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
turns: 6
promptTokens: 372660
cachedTokens: 276071
cacheWriteTokens: 96579
completionTokens: 4479
durationSeconds: 40.2
costUsd: 0.459397
costBasis: provider
runId: run-20261017-slices-plan-d9bcbe25
squadronVersion: 0.23.0
findings:
  - id: F001
    severity: concern
    category: proportionality
    summary: "Design is heavier than the slice needs"
    location: "project-documents/user/slices/179-slice.staged-effort-estimates-and-accuracy.md#Technical Decisions"
  - id: F002
    severity: concern
    category: documentation-consistency
    summary: "Architecture document change is promised but not scheduled"
    location: "project-documents/user/slices/179-slice.staged-effort-estimates-and-accuracy.md#Special Considerations"
  - id: F003
    severity: concern
    category: layer-boundaries
    summary: "Revise-prompt change puts document-schema knowledge into the dispatch action"
    location: "project-documents/user/slices/179-slice.staged-effort-estimates-and-accuracy.md#D4 — The re-estimate instruction"
  - id: F004
    severity: concern
    category: integration
    summary: "Prompt-only mode silently loses revised-stage estimates"
    location: "project-documents/user/slices/179-slice.staged-effort-estimates-and-accuracy.md#Technical Scope"
  - id: F005
    severity: concern
    category: scope
    summary: "Plan-entry dependency and scope changes are made unilaterally"
    location: "project-documents/user/slices/179-slice.staged-effort-estimates-and-accuracy.md#Dependencies"
  - id: F006
    severity: concern
    category: dependencies
    summary: "Hard dependency on an external repo for the slice's value"
    location: "project-documents/user/slices/179-slice.staged-effort-estimates-and-accuracy.md#Prerequisites"
  - id: F007
    severity: concern
    category: error-handling
    summary: "Failure handling for the new git path leans on 176 without restating the bound"
    location: "project-documents/user/slices/179-slice.staged-effort-estimates-and-accuracy.md#D3 — Reading the history within 176's git bound"
  - id: F008
    severity: note
    category: alignment
    summary: "Architecture alignment otherwise sound"
    location: "project-documents/user/slices/179-slice.staged-effort-estimates-and-accuracy.md#Architecture"
  - id: F009
    severity: pass
    category: error-handling
    summary: "Failure modes enumerated for new I/O paths"
    location: "project-documents/user/slices/179-slice.staged-effort-estimates-and-accuracy.md#D7 — Failure modes"
---

# Review: slice — slice 179

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Design is heavier than the slice needs

The slice plan entry asks for re-estimating at design and after reviews, per-slice history, and an accuracy measure added to 176's report. The design delivers that with two new `stats/` modules, a new `pipeline/reestimate_prompt.py`, a second whole-history git query, ancestry-based stage labelling, and a new rank-correlation table. It also adds JSON fields, a `key_removed` flag, an `estimates_skipped` counter, and an 11-row failure table. It declares the slice 3/5. That looks low for this much machinery.

Cuts to consider:
- **Stage labels.** D2 gives five stages from first-parent ancestry walks, and the doc admits a merge-commit blind spot. The plan wording needs only plan, design and revised. A simple ordered list of `effort` changes, labelled by the review type that precedes each one, would cover it.
- **Accuracy table rows.** The `plan`, `design` and `final` rows and per-measure cells could start with `design` and `final` against one or two measures. The plan row duplicates 176's levels table, as D6 itself says.
- **`key_removed` and `estimates_skipped`.** Both track edge cases that nothing in the current corpus has. Warn and drop would do until a real case appears.
- **Accuracy table timing.** The accuracy table prints only "below floor" until enough designs carry `effort`, and the doc says none do today. The slice may be building a report it cannot show for a long time. Deferring it with the other items sent to #232 is a valid option.

### [CONCERN] Architecture document change is promised but not scheduled

Special Considerations says "Step 6 amends that line" in the architecture document (Non-goals, around line 712) to name effort-estimate reporting. Development Approach step 6 lists wrapper help, README, CHANGELOG, the slice-plan dependency amendment and an issue comment. It does not list the architecture edit.

The architecture line 715 also lists "Automated complexity estimation for model selection" as out of scope. The slice's own routing exclusion keeps it clear of that line. Even so, agents now set the estimate and an accuracy table ranks the estimates, so the slice should say explicitly why it is not that out-of-scope item. Add the architecture edit to the task list, and state that boundary in the amended text.

### [CONCERN] Revise-prompt change puts document-schema knowledge into the dispatch action

The architecture keeps `dispatch` responsible for model resolution, agent lifecycle and output capture. This slice makes `_resolve_feedback_prompt` call a function that resolves the slice design path through `cf_client`. It then injects an instruction to edit a frontmatter key, which is a new side-effect policy in the dispatch action. The doc keeps the function outside the Action protocol, which is reasonable.

It does not say how `sq review --max` reaches the same code path, although Integration Requirements claim it does. It also does not say how this fits the architecture's closed event and action boundaries: 173's `revision-stamp` and `frontmatter-gate` already operate on design files at commit. State which component owns "who may edit design frontmatter during a revise round". Also confirm that the 173 frontmatter gate and the `revision-stamp` post-action do not conflict with an agent-edited `effort` line.

### [CONCERN] Prompt-only mode silently loses revised-stage estimates

The architecture treats prompt-only mode (153-154) as a first-class runtime in which "the human is the runtime". The slice excludes it because `prompt_renderer` does not render `feedback: review` prompts. That is accurate today, but it means every prompt-only slice has design-stage estimates and never revised ones. The accuracy table's `final` and `design` rows then diverge only for pipeline-run slices, which biases the measure. Name this bias in the report footer or the doc. At minimum, add an acceptance note that the exclusion is revisited when `prompt_renderer` gains feedback prompts.

### [CONCERN] Plan-entry dependency and scope changes are made unilaterally

The plan entry assigns this slice "extend 176's planned-vs-actual report with per-stage estimates and an accuracy measure" and dependencies [176, 178]. The design drops 178 and moves `--stage` grouping, the rollup drift line and the `artifact_spend` measure to #232. The rationale is sound, but dropping or deferring assigned scope is a flaggable change. The design handles it with an amendment step in the task list. Make the plan entry edit and the #232 issue creation prerequisites that are visible before implementation starts, not trailing items in step 6.

### [CONCERN] Hard dependency on an external repo for the slice's value

Without ai-project-guide#43, P4 designers write no `effort`, so every report shows "design not estimated". The design acknowledges this and makes Phase 7 integration wait on it. That puts the slice's merge on an open issue in another repository that this project does not control. Either confirm the issue is scheduled ahead of this slice's integration, or add a squadron-side fallback. One fallback is a design-prompt instruction in the P4 dispatch. That would raise scope, so a stated owner and ordering for #43 is the lighter choice.

### [CONCERN] Failure handling for the new git path leans on 176 without restating the bound

D7 covers failures well. The new `git log --all -G` call scans all history for a regex, and `git show` runs once per candidate (E). Neither the doc nor D7 states a timeout or a bound on E. Failure of the whole-history call aborts the entire report with exit 1. That includes `sq stats slice` for an unrelated purpose, such as the existing planned-vs-actual view, which now cannot be produced when the estimate query fails. Consider degrading to "estimates unavailable" for the slice view instead of failing the whole command, or state why 176 D9 requires a hard failure here. Restate the timeout value inherited from 176 and the expected E for a typical slice.

### [NOTE] Architecture alignment otherwise sound

- **Dependency direction.** `stats/` stays read-only, `git_history.py` stays the only module that runs git, and `stats/` cores contain no Typer code. This fits the layering 176 established.
- **Constants and enums.** Stages, rows and the key name are enums or constants, consistent with the project's no-scattered-values rule.
- **Prompt text.** It contains no example value, so it avoids the hallucination trap.
- **Persisted state.** No new state is added, which suits the architecture's state-file model.
- **Scale.** The estimate reuses the plan's 1–5 scale and is stored once, with git as the history.

### [PASS] Failure modes enumerated for new I/O paths

Each new git call, parse step and prompt-resolution path has a stated behavior and an observable signal (WARNING, counter or footer). The Technical Requirements require a test per row. This meets the failure-mode enumeration rule.

### Run Digest

- Response length: 8211 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 372660 / 276071 / 96579 / 4479 / not computed
- Duration: 40.2 s
- Cost: $0.46 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
