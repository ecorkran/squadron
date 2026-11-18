---
docType: review
layer: project
reviewType: slice
slice: recipe-reviews-in-pipelines
targetKind: slice
rulesSource: project
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
reviewedSha: 2eb39aa549ee0f60d778297903dc23414a26e777
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 29
effort: xhigh
turns: 30
promptTokens: 1927002
cachedTokens: 1779242
cacheWriteTokens: 147726
completionTokens: 68625
durationSeconds: 314.4
costUsd: 0.265343
costBasis: provider
squadronVersion: 0.24.34
findings:
  - id: F001
    severity: fail
    category: error-handling
    summary: "An incomplete recipe can clear the loop's accept threshold on the final round"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:199-205"
  - id: F002
    severity: concern
    category: contract
    summary: "Omitting requestedModel tells existing gates that a recipe was answered as asked"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:228-233"
  - id: F003
    severity: concern
    category: error-handling
    summary: "Mid-recipe edits to the working tree are a known failure mode with no signal"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:176"
  - id: F004
    severity: concern
    category: security
    summary: "The comb's \"no write or shell tool\" guarantee is not shown to hold on sdk and Codex profiles"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:171-177"
  - id: F005
    severity: concern
    category: error-handling
    summary: "Recipe name resolution is inconsistent for same-name recipes and unspecified for bad files"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:134-141"
  - id: F006
    severity: concern
    category: error-handling
    summary: "Sink and file writes lack an ordering and sync/async contract"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:207-214"
  - id: F007
    severity: concern
    category: scope
    summary: "Several record fields and restated figures can be cut"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:339-354"
  - id: F008
    severity: note
    category: dependencies
    summary: "The cost-cap dependency (947) is missing from Dependencies"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:69-83"
  - id: F009
    severity: note
    category: cost
    summary: "An unpriced stage makes the cap count less than the recipe spends"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:251"
  - id: F010
    severity: note
    category: error-handling
    summary: "Two reviewer outcomes are missing from the failure table"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:189-198"
  - id: F011
    severity: pass
    category: architecture
    summary: "Layering matches the 20261118 amendment"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:87-108"
  - id: F012
    severity: pass
    category: architecture
    summary: "Cost rule and record-by-product match the amendment"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:238-254"
  - id: F013
    severity: pass
    category: integration
    summary: "Plan criteria and the 431/433 contracts are covered"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:348-356"
---

# Review: slice — slice 434

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] An incomplete recipe can clear the loop's accept threshold on the final round

D5 says "An incomplete recipe cannot pass," but the rule only turns a PASS into UNKNOWN. The Risk Assessment (line 442) names this hazard. Pipeline templates such as P6 set `until` to `review.pass` and `accept_if` to `review.concerns_or_better`, and `accept_if` is applied when the loop exhausts its rounds. On the last round, a recipe with a failed reviewer and kept CONCERN findings returns CONCERNS, the accept threshold is met, and the step proceeds as accepted. Nothing in the loop reads `complete`, and the design does not say this is intended.

Recommendation: make an incomplete recipe's verdict UNKNOWN, so neither `until` nor `accept_if` passes it and the exhaust behavior applies. Before choosing this, confirm that the reviser's feedback is built from findings and not from the verdict. If the design keeps CONCERNS instead, it must state that a partial review is accepted at exhaustion and how that is surfaced. Either way, add a test at exhaustion.

### [CONCERN] Omitting requestedModel tells existing gates that a recipe was answered as asked

D7 omits `requestedModel` for recipe reviews. In the existing review-file contract, that key appears only when the answering model differs from the one requested, and gates read its absence as "answered as asked." A recipe has no single requested model, and its stages' answering models can differ from their aliases (the stage table in line 234 reports them). The frontmatter therefore makes a claim the design cannot support. The readers list in lines 230-233 also omits this gate.

Specify what a recipe's frontmatter says about substitution, for example a recipe-level marker, and state how gates should read `aiRecipe`.

### [CONCERN] Mid-recipe edits to the working tree are a known failure mode with no signal

D4 says an edit made while the recipe runs can reach a later comb, and that "this is not detected." The review rules require each identified failure mode to be observable at WARNING or above, and silent paths are bugs. Record a content hash of the changed files at each stage start, log a WARNING naming the stage and files when a later stage sees different content, and store the hashes in the stage record. The cost is one hash pass per stage over the changed files.

### [CONCERN] The comb's "no write or shell tool" guarantee is not shown to hold on sdk and Codex profiles

D4 gives the comb `read_file`, `list_files` and `grep` only. Lines 176-177 then say sdk and Codex profiles use their own tool controls, which do not confine reads. The design never says whether the restricted list is enforced on those profiles. Line 465 states "The comb is given no write or shell tool" as a guarantee. Tests inject the review call (line 389), so no test can show the guarantee holds.

Either state how the list maps onto each profile's controls and which check verifies the mapping, or narrow the claim to what is enforced.

### [CONCERN] Recipe name resolution is inconsistent for same-name recipes and unspecified for bad files

A project recipe with the same name as a shipped recipe silently wins, because the first match is used (line 136). But a name that is both an alias and a recipe is an error (line 148), and the design keeps five benchmark recipes out of production search specifically to avoid that kind of collision (line 141). Silent shadowing of a shipped recipe bypasses that rule.

Choose one: error when a name appears in two search directories, or allow the override and log it at WARNING. The design also needs to say what happens when a file found by name is malformed or has an unknown key. Raising with the file path is the consistent choice; skipping to the next directory would be a silent fallback.

### [CONCERN] Sink and file writes lack an ordering and sync/async contract

Three points are underspecified:
- The cancellation row says the aborted record is written "synchronously" (line 213). The Non-functional section (line 283) says file work in the runner goes through `asyncio.to_thread`. `RecipeRecordSink.write` (line 243) has no stated signature, so it is unclear which path blocks the event loop.
- The table does not say what happens when the review-file save fails after the recipe completes: whether the record is written with `review_file: null` or the review fails first.
- The design does not say what happens if the sink write raises on the cancellation path.

Specify the sink as async, run it via `to_thread` on normal paths, and state the cancellation-path behavior and the save-failure ordering.

### [CONCERN] Several record fields and restated figures can be cut

- `kept` (line 340) can be derived from each comb stage's decisions. Drop it.
- `effort_configured` (line 344) has no reader in the design. D10 keys on `effort_sent`, and the architecture says configured effort must not stand in for sent effort. Drop it, or name the reader.
- `chain` (line 344) can be derived from the ordered stage list and each stage's `reviewer`. Drop it unless 431 or 433 needs it, which the plan does not say.
- The 1,176-call statistic (line 281) and the record sizes (line 284) restate 430's measurements. Keep one sentence each with a pointer.
- The 435/436 paragraph (line 354) describes reviewer shapes this slice does not build. Move it to a note or drop it, since the plan already carries those slices.

### [NOTE] The cost-cap dependency (947) is missing from Dependencies

D9 bounds production reviews by `pipeline.max_cost_usd` (line 249), which slice 947 delivers, and the architecture's Current State lists it as existing. Add it to the prerequisites.

### [NOTE] An unpriced stage makes the cap count less than the recipe spends

D9 stamps the priced sum, so an unpriced stage adds nothing to the cap. The design states this, names the stage in a WARNING, and matches how an unpriced single model is counted today. It still sits against the architecture's "Absent is not zero" principle, and the cap is the only production bound on recipe spend. Consider failing the step, or stopping before the next stage, when a stage is unpriced and a cap is set. Otherwise say in the design that the cap is a floor for recipes with unpriced stages.

### [NOTE] Two reviewer outcomes are missing from the failure table

The table covers a reviewer that raises `ProviderError` and a reviewer that returns UNKNOWN with no findings. It does not cover a reviewer that returns UNKNOWN with findings, or output the parser cannot read without raising. State whether each counts as `config_failure` (the recipe is incomplete) or as ok findings.

### [PASS] Layering matches the 20261118 amendment

`recipes/` sits above `review/` and `metrology/`, is imported by `pipeline/`, `cli/` and `benchmark/`, and never imports `benchmark/`. Shared recipe code is moved rather than copied, so benchmark and production use one loader. The design also requires an import test that keeps `review/` and `metrology/` from importing `recipes/` (line 390).

### [PASS] Cost rule and record-by-product match the amendment

Production recipe reviews print no bound. They are capped by `pipeline.max_cost_usd` in a pipeline and are uncapped as a standalone `sq review`. Each review writes one record as a by-product, and a failed write does not fail the review (line 244). Stages run serially. This matches the amendment's cost, record and serial-stage bullets.

### [PASS] Plan criteria and the 431/433 contracts are covered

The plan's 434 criteria are present: pool refusal, a name that is neither alias nor recipe failing before the run, failed stages reported, records keyed by run id, and CLI and slash-command parity. The `run_id`, `step_name`, `aiRecipe` and record id that 431 reads, and the `recipe_review` records that 433 reads, match the plan's 431 and 433 entries.

### Run Digest

- Response length: 9796 chars
- Response is newline-free: no
- Tool calls made: 29
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 30
- Tokens — prompt / cached / cache write / completion / reasoning: 1927002 / 1779242 / 147726 / 68625 / not computed
- Duration: 314.4 s
- Cost: $0.27 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 13
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 13
- Finding-shaped matches — surviving validation: 13

## Response (20261118, PM session)

- F001: fixed. An incomplete recipe with kept findings now gives FAIL, so it keeps the loop revising and is never accepted at exhaustion; a test covers exhaustion. The reviser's feedback is built from findings, not the verdict.
- F002: dropped. The only reader of `requestedModel` is `frontmatter_usage.py`, which fills a usage record; no gate reads its absence. Per-stage substitutions are in the stage table and the record.
- F003: dropped. A single-model review reads the same live tree with the same exposure; in a pipeline nothing else writes during the review step.
- F004: fixed by narrowing. The comb asks for read tools through the same `allowed_tools` path a single-model review uses, and the design claims no restriction beyond that review's.
- F005: fixed. A shadowed recipe logs a WARNING naming both files; a file that fails to load raises with its path and the search never moves on.
- F006: fixed. `write` is synchronous, called through `to_thread` normally and directly on cancellation (an error there is logged at ERROR and cancellation propagates); the review file saves first, and a failed save leaves `review_file: null` in the record.
- F007: `kept`, `chain` and `effort_configured` cut. The restated figures stay (one line each). The 435/436 paragraph stays: the PM asked for it so the runner is built to take those stage kinds.
- F008: fixed (947 added to prerequisites).
- F009: no change. D9 already says the stamped cost is a floor with an unpriced stage, names it in a WARNING, and counts it in the real-work table.
- F010: fixed. A reviewer returning UNKNOWN, with or without findings, is `config_failure` and its findings are not used, as in 430.
