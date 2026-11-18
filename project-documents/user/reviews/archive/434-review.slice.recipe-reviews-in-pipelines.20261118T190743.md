---
docType: review
layer: project
reviewType: slice
slice: recipe-reviews-in-pipelines
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261118
dateUpdated: 20261118
reviewedSha: 75fe287010856c47cbe4c1f97f3ea05aa7342fb3
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 17
effort: xhigh
turns: 18
promptTokens: 497822
cachedTokens: 400544
cacheWriteTokens: 97264
completionTokens: 51077
durationSeconds: 227.8
costUsd: 0.100876
costBasis: provider
runId: run-20261118-p4-b5566cfd
squadronVersion: 0.24.34
findings:
  - id: F001
    severity: fail
    category: architecture-conformance
    summary: "A recipe review breaks the amended cost-bound rule"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:225-231"
  - id: F002
    severity: concern
    category: scope
    summary: "Production review behavior is outside the architecture's stated scope"
    location: "project-documents/user/architecture/420-arch.model-benchmark.md:28-34"
  - id: F003
    severity: concern
    category: dependency-direction
    summary: "`review/recipe` depends upward on metrology"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:83"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Failure modes for unexpected errors, cancellation, and git failure are not enumerated"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:170-195"
  - id: F005
    severity: concern
    category: correctness
    summary: "The comb reads the mutable working tree, not the reviewed revision"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:162-168"
  - id: F006
    severity: concern
    category: measurement-validity
    summary: "Real-work rows group by recipe hash alone, so config changes merge rows"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:233-247"
  - id: F007
    severity: concern
    category: non-functional
    summary: "Architecture NFRs on record size, record count, and cost are not restated"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:257-258"
  - id: F008
    severity: concern
    category: integration
    summary: "The review-ingest contract is deferred to the task breakdown"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:206-214"
  - id: F009
    severity: concern
    category: scope
    summary: "The plan's MCP criterion is dropped without a stated deferral"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:294"
  - id: F010
    severity: concern
    category: traceability
    summary: "Frontmatter dependencies and interfaces omit slices the design uses"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:6-10"
  - id: F011
    severity: concern
    category: proportionality
    summary: "The design is heavier than the plan's effort and carries cuttable scope"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md"
  - id: F012
    severity: note
    category: architecture-conformance
    summary: "Serial stages depart from the architecture's \"in parallel\" wording"
    location: "project-documents/user/architecture/420-arch.model-benchmark.md:26"
  - id: F013
    severity: note
    category: scope
    summary: "Records keyed by run ID replace \"stored with the run\" in the plan"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:216-223"
  - id: F014
    severity: pass
    category: architecture-conformance
    summary: "No benchmark result is read at run time, and the default is unchanged"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:250-255"
  - id: F015
    severity: pass
    category: security
    summary: "The comb tool set matches the \"no write or shell tool\" claim"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:429-430"
---

# Review: slice — slice 434

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] A recipe review breaks the amended cost-bound rule

The 20261115 amendment says "Every measured run prints its cost bound first and stops at a cap" (420-arch, line 34). This slice says each real recipe review is a measurement (Overview, line 34; D8). D9 prints no bound. It checks the run cap only between steps, so "one review can cross the cap by its own cost." It also counts a stage with no cost as zero toward the cap. `sq review` has no `--max-cost` at all (checked: `cli/commands/review.py` has none), so a CLI recipe review has no cap.

The repo already has the pattern this needs. `benchmark/grade_budget.py:54-60` counts an unpriced review at a per-review figure and checks the cap before each review. That class lives under `benchmark/`, which this slice's own layering rule forbids `review/recipe` to import (line 83), so it must be moved or re-homed.

Fix: state a dollar bound before the first stage, check the cap before each stage, count unpriced stages at a stated figure, and give `sq review` a cap source. If production reviews are not meant to be measured runs, amend the architecture and remove the measurement claim from Value. As written, the slice and the architecture conflict.

### [CONCERN] Production review behavior is outside the architecture's stated scope

The architecture's Scope (line 28) lists the case record, replay runner, grader, recall harness, metrology record types, and reports. The Anticipated Slices (lines 137-147) and the amendment (lines 32-36) name 430 through 433 and nothing that changes production behavior. This slice changes `ReviewAction` verdicts and the review gate, the review file format, the pre-run check and loader, `sq review` exit behavior, step cost stamping, and review ingest.

The plan adds 434 (420-slices item 15, dated 20261118), but the architecture (dated 20261115) has no entry for it. Amend the architecture, as the 20261115 amendment did, to name the production surface, the cost rule that applies to it, and the boundary between benchmark and production code.

### [CONCERN] `review/recipe` depends upward on metrology

Line 83 says `review/recipe` imports "review/, models/ and metrology payloads." But the `RecipeReview` payload is in `metrology/recipe_review_models.py` (line 219), and `recipe_record.py` holds "the metrology-store implementation" (line 94), which needs the store. The runner that builds the outcome therefore depends on metrology. Metrology already imports `squadron.review` in about a dozen modules (for example `metrology/review_ingest.py:26` and `metrology/review_models.py:17`), so the two packages now depend on each other.

Fix: the runner returns a neutral `RecipeOutcome`. Mapping it to `RecipeReview` and writing to the store belong in metrology or in the pipeline/CLI wiring that already injects the sink (D8). Correct line 83 to match.

### [CONCERN] Failure modes for unexpected errors, cancellation, and git failure are not enumerated

D5 handles `ProviderError` and two config outcomes. It does not say what happens to:
- a non-`ProviderError` exception from a stage (a parse bug, an error in verdict computation);
- pipeline cancellation or Ctrl-C mid-recipe: spend from completed stages is never stamped (D9 stamps only reviews that complete), and no record is written, so `RunSpend` undercounts;
- `git diff --name-only` failing (bad range, not a repo), which decides whether the comb runs at all (D4);
- a stage call that hangs: D5 says timeouts arrive as `ProviderError` but gives no bound for a stage call;
- `unknown_ids` and `duplicate_decisions` from a comb (fields at line 313, no rule).

The review rules require each of these to be explicit and observable (a WARNING or higher, or a metric), with a test. Add a row for each.

### [CONCERN] The comb reads the mutable working tree, not the reviewed revision

The reviewer sees the diff range (`reviewed_sha`, line 306). D4 sets the comb's cwd to the review's cwd, the user's working tree, with `read_file`, `list_files` and `grep` (`COMB_ALLOWED_TOOLS`, `benchmark/recall/stage_command.py:28`). If the tree has uncommitted edits or sits on another revision, the comb makes KEEP/DROP decisions against code the reviewer did not see, and the record cannot show which.

This also breaks the architecture's comparability rule for real-work rows (line 46). Fix: read files at `reviewed_sha` through git, or record the tree state (head SHA and dirty flag) on each comb stage and flag dirty rows in the real-work table.

### [CONCERN] Real-work rows group by recipe hash alone, so config changes merge rows

D10 keys rows on recipe name and recipe hash. The hash covers the recipe file, which names aliases but not what they resolve to. Changing `haiku-xhigh`'s effort in `models.toml` leaves the recipe hash unchanged, so reviews from before and after the change merge into one row. The stage template hashes (lines 303-304) are also missing from the key.

The architecture requires a report to compare only matching results and flag the rest. The config includes model, profile, effort sent, `tool_use`, and `max_output_tokens`, plus grader and prompt identity (line 46). Add each stage's effort sent and config identity, and the template and comb-prompt hashes, to the key, and show a separate row or a flag when they differ.

### [CONCERN] Architecture NFRs on record size, record count, and cost are not restated

The architecture states NFRs this slice touches: records stay coarse and small because the store reads every file on every query (line 71; "Record size and count," line 135). The slice's only Non-functional item (line 258) covers thread handling and says there is no new concurrency. This slice writes one record per review in every project, not per benchmark run, so record count grows with ordinary use, and no size or count target is given.

Restate the rule with targets: a per-record size ceiling (inline findings bounded, raw output in sidecars), expected record volume per project, and how `iter_records` cost stays acceptable.

### [CONCERN] The review-ingest contract is deferred to the task breakdown

D7 says `review_ingest.py` reads `aiRecipe` so a recipe review is not stored as a model review, and that "the `CodeReviewRecord` field that holds it is settled in the task breakdown." `CodeReviewRecord` (`metrology/review_models.py:33`) is the shared record that 400's quality reports read. Whether a recipe review is skipped, stored under a recipe label, or stored as a model changes what 400 and 431 see. That is an integration decision and belongs in the design. State it, and state what happens to existing reviews whose `aiModel` is a recipe name.

### [CONCERN] The plan's MCP criterion is dropped without a stated deferral

Plan item 15 requires "the same result shape from CLI, slash command and MCP." Line 294 says "Squadron has no MCP review tool today; a future one calls the same runner." I checked: `tools/` has an MCP bridge and no review tool, so the claim is accurate. But the criterion is not in the Excluded list (lines 54-62), is not moved to a named slice, and is not reflected in the plan. Add it to Excluded with the reason and update the plan entry, or name the slice that owns it.

### [CONCERN] Frontmatter dependencies and interfaces omit slices the design uses

`dependencies` lists only 430. The design uses `ContentSidecars` and its REVIEWS kind, which 425's slice doc introduced (425, around line 289). Line 68 attributes that kind to 421, which is wrong. `interfaces` lists 431 and 433 but not 432, which the Provides list (line 322) says imports `review/recipe`. The 432 plan entry names only 430 as its dependency, so that expectation is not in 432's spec. Correct the list, fix the attribution, and align with the 432 entry.

### [CONCERN] The design is heavier than the plan's effort and carries cuttable scope

The plan rates this slice 3/5 effort, medium risk. The doc has eleven decisions, eight new modules, a 14-field record with a per-stage list, a frontmatter stage list, a body table, an `ActionResult` summary, a `--output json` recipe object, and a new report. Cut or defer:
- `aiRecipeStages` in frontmatter (D7) repeats the body table and the record. Keep `aiRecipe` and `recipeComplete`.
- The `~/.config/squadron/recipes/` search directory (D1). No recipe in the slice or plan lives there. Add it when a user needs it.
- Per-stage detail in `ActionResult.metadata["recipe"]` and the `--output json` recipe object (D8, API contracts). Keep the name, `complete`, and record ID unless 431 is shown to need stage counts.
- The restated 430 types in Prerequisites and Interfaces Required (lines 66-77). Cite 430 instead.

Keep the migration plan and the verification walkthrough.

### [NOTE] Serial stages depart from the architecture's "in parallel" wording

The architecture describes reviewer setups as "several in parallel" (line 26), and plan 430 defines recipe reviewers as running in parallel. Both 430 and this slice run calls serially (D3, #372). The serial choice is sound and tracked, but real-work duration rows measure serial runs. When 434 lands, update the architecture and plan wording so the duration numbers have the right basis.

### [NOTE] Records keyed by run ID replace "stored with the run" in the plan

Plan item 15 says per-stage data is "stored with the run." D8 stores it in a `recipe_review` record in the metrology store and keeps only a summary in run metadata. The reason holds: `sq review` and prompt-only pipelines have no run state. Update the plan wording so 431 and 433 read the right store.

### [PASS] No benchmark result is read at run time, and the default is unchanged

D2 requires an explicit name, D11 keeps shipped defaults on `haiku-xhigh`, and the runner reads no 430 or 431 output. This matches "Measure, never gate" and "No automatic model selection" (architecture lines 77 and 155).

### [PASS] The comb tool set matches the "no write or shell tool" claim

The comb is given `read_file`, `list_files` and `grep` (`benchmark/recall/stage_command.py:28`), which matches "no write or shell tool." Once the comb reads the working tree (see the comb-evidence finding), this tool set is the only containment, so it should be restated where that finding is fixed.

### Run Digest

- Response length: 12659 chars
- Response is newline-free: no
- Tool calls made: 17
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 18
- Tokens — prompt / cached / cache write / completion / reasoning: 497822 / 400544 / 97264 / 51077 / not computed
- Duration: 227.8 s
- Cost: $0.10 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 15
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 15
- Finding-shaped matches — surviving validation: 15
