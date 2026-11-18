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
reviewedSha: 58773eb3f871d8442253ec67a41e11185bd69ced
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 35
effort: xhigh
turns: 36
promptTokens: 1095113
cachedTokens: 980435
cacheWriteTokens: 114652
completionTokens: 69706
durationSeconds: 307.0
costUsd: 0.188885
costBasis: provider
runId: run-20261118-p4-b5566cfd
squadronVersion: 0.24.34
findings:
  - id: F001
    severity: fail
    category: correctness
    summary: "Six benchmark recipes shadow model aliases in the production search"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:139-147"
  - id: F002
    severity: concern
    category: architecture-boundary
    summary: "Migration plan leaves a benchmark import in the moved comb code"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:293-300"
  - id: F003
    severity: concern
    category: correctness
    summary: "The comb's changed-files input has no named helper, and both nearby helpers break a stated rule"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:172"
  - id: F004
    severity: concern
    category: proportionality
    summary: "Design is heavier than its plan entry; five items can be cut or deferred"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:42-56"
  - id: F005
    severity: concern
    category: scope
    summary: "Pool recipes are refused in production with no reason given"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:63"
  - id: F006
    severity: concern
    category: error-handling
    summary: "A hung stage is logged only at INFO, below the observability bar"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:213"
  - id: F007
    severity: concern
    category: correctness
    summary: "Partially priced recipes under-report cost to the pipeline cap"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:245-246"
  - id: F008
    severity: concern
    category: error-handling
    summary: "The sink's swallowed write error lacks the exception type and justification the project rule requires"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:239"
  - id: F009
    severity: concern
    category: integration
    summary: "Consumer plan entries do not list the dependency on this slice"
    location: "project-documents/user/architecture/420-slices.model-benchmark.md:178"
  - id: F010
    severity: concern
    category: specification
    summary: "The verification walkthrough uses CLI flags that do not exist"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:411-421"
  - id: F011
    severity: note
    category: specification
    summary: "\"Kept\" has two meanings in the comb design"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:171"
  - id: F012
    severity: note
    category: integration
    summary: "`aiModel` now carries a recipe name for readers that expect a model"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:227"
  - id: F013
    severity: pass
    category: architecture-boundary
    summary: "Layering and dependency direction match the amendment"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:88"
  - id: F014
    severity: pass
    category: alignment
    summary: "Production cost rule matches the 20261118 amendment"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:242-244"
  - id: F015
    severity: pass
    category: error-handling
    summary: "Failure modes are enumerated for reviewer, comb, git, cancellation and unexpected-exception paths"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:187-213"
---

# Review: slice — slice 434

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] Six benchmark recipes shadow model aliases in the production search

D1 moves six single-reviewer benchmark recipes into `project-documents/user/recipes/`, which D1 searches for production. Five of those file stems are also model aliases in `models.toml`: `haiku-xhigh`, `sonnet-high`, `sonnet`, `sol` and `luna`. D2 (line 147) makes a name that is both an alias and a recipe an error. In squadron's checkout, the default `review-model: haiku-xhigh` that D11 keeps would then fail the pre-run check. The success criterion that `haiku-xhigh` "behave[s] as before" cannot hold. A user alias that matches a recipe in a project's `user/recipes/` hits the same error. Fix: keep single-reviewer benchmark recipes out of the production search root, or give them names that cannot collide, and state which names the production search covers.

### [CONCERN] Migration plan leaves a benchmark import in the moved comb code

`render_findings` and `run_comb_stage` move to `recipes/comb_call.py`, but both call `finding_id_at`, which lives in the benchmark recall `review_output` module. The migration table does not move that module or the function. As written, `recipes/` imports `benchmark/`, which the 20261118 amendment forbids and which the import test in Technical Requirements (line 381) would fail. Two consumers are also missing from the table: the hand-run reviews reader, which imports `review_output`, and the hand-run combs reader, which imports the decisions parser. Fix: name `finding_id_at` (or the module) in the move table, and list every consumer from an import search rather than a sample.

### [CONCERN] The comb's changed-files input has no named helper, and both nearby helpers break a stated rule

D4 says `changed_files` is `git diff --name-only` "over the review's resolved diff range" but names no helper. The two existing candidates each conflict with the design. The review package's `extract_diff_paths` returns an empty list on git failure, which is the silent fallback D5 forbids, since D5 requires a WARNING and a failed review. The benchmark stage module's `changed_files` diffs `base HEAD`, the committed range only. D4's own tree-state paragraph says pipeline reviews run before the commit, so that helper would give the comb a file list that omits the uncommitted work it judges. Fix: specify the range (the one the review's diff input uses, against the working tree), name the helper, and state that a git failure raises.

### [CONCERN] Design is heavier than its plan entry; five items can be cut or deferred

The plan entry asks for recipe names to be accepted, kept findings merged, stages recorded, and failures reported. Beyond that, the design adds, in rough order of size:
1. Tree-state hashing and a closing read (D4, second half), with `tree_head`, `tree_dirty` and `tree_changed`, a failure row, and a report column. Neither the plan nor the architecture asks for it. A cheaper option is to record the starting head and dirty flag and state that a mid-run edit can reach a comb.
2. A `report --json --real-work` schema and a schema test fixed for 433. 433 is not built, and its plan entry does not name this contract.
3. Moving the six non-shipped recipe files (D1 and the migration table). No 434 criterion needs the move, and it causes the collision above.
4. Record fields no named consumer reads: `slice_index`, `input_file`, `diff` and `reviewed_sha` (line 330). Keep them only if 431 or 433 needs them.
5. The Value section (lines 42–45), which restates the plan entry almost word for word.

Cut or defer items 1–4, then recheck the success criteria against what remains.

### [CONCERN] Pool recipes are refused in production with no reason given

The plan's first criterion says a pipeline's `review-model` and a step's `review.model` accept a recipe name, with no exception for shape. The design refuses `pool: true` recipes and says only that they "stay valid for `sq benchmark recall`." The design gives no reason, but one exists: a pool picks one reviewer at random, so the same code could get a different verdict on each revise round. If the PM accepts that, the plan criterion needs amending, and this line should state the reason.

### [CONCERN] A hung stage is logged only at INFO, below the observability bar

The project's review rules require each failure mode to be observable at WARNING or above, or as a metric increment. The hang row records only an INFO start line with no finish line, and nothing marks the stage as overdue. The reason given for no time bound is sound, since a recipe-only bound would differ from the single-model path. It does not address observability. Fix: log a WARNING once a stage passes a named threshold held in config, without killing the call. The cancellation path can stay as written.

### [CONCERN] Partially priced recipes under-report cost to the pipeline cap

D9 sets the step's `cost_usd` to the sum of known stage costs and warns once per unpriced stage. The pipeline cap (947) and `RunSpend` read that figure, and it is the only spend guard on production reviews. A recipe with one unpriced stage is counted below what it cost, so the cap can be passed without a stop. The architecture's "Absent is not zero" principle is written for benchmark grades, but it applies here: an unknown cost should not count as zero. Fix: when any stage is unpriced, set `cost_usd` to `None` and let `RunSpend` warn. Alternatively, state that the cap is a known-cost floor and why that is acceptable.

### [CONCERN] The sink's swallowed write error lacks the exception type and justification the project rule requires

D8 says a failed record write is logged at ERROR and does not fail the review. The project's exception rules allow a swallowed exception only when it names the specific type and comments why swallowing is correct, or when it is a top-level handler. The design does neither. Fix: name the store exception types the sink catches, not `Exception`, and state the justification. The review-file precedent it cites is a valid reason.

### [CONCERN] Consumer plan entries do not list the dependency on this slice

The 434 design depends on 425's `ContentSidecars` (frontmatter, lines 6–8). Its plan entry (line 211) lists only 430. The design says 431 reads `recipe_review` records and 433 reads the `real_work` JSON. The plan's 431 dependencies (line 178) omit 434. Its 433 dependencies (line 198) are 430 and 431, with no mention of 434 or the JSON contract. The plan's Provides line says 431 and 433 read these records, so the reverse dependency is real. A 431 built first would silently omit recipe stage data. Fix: add 425 to 434's plan dependencies, and add 434 to 431's and 433's, each with the contract it reads.

### [CONCERN] The verification walkthrough uses CLI flags that do not exist

Step 5 passes `--revise --max-rounds 1`. The review command has no `--revise` or `--max-rounds` option. The revise loop is `--max N`, and `--revise-model` also exists. The API Contracts row (line 314) names `--revise` too. Step 4 passes `--output-path` with `--output json`, but that option's help text says it applies to `--output file`. A walkthrough that fails on its first flag cannot verify the feature. Fix: use `--max 1`, and state how the JSON document is written.

### [NOTE] "Kept" has two meanings in the comb design

D4 defines a comb's input as findings "that every earlier comb in the chain kept", meaning decided KEEP. D5 (line 181) defines kept as KEEP or UNDECIDED. The success criteria use the D5 meaning. An implementer who reuses "kept" for the comb input could drop undecided findings from the merged set. Use "decided KEEP" for comb input, and "kept" only for the D5 set.

### [NOTE] `aiModel` now carries a recipe name for readers that expect a model

D7 sets `aiModel` to the recipe name, and the design checks only review ingest. The judge-calibration identity reader also reads `aiModel` as a model identity. It reads judge-template reviews only, and D2 refuses recipes on judge templates, so it should not be reached. The design should say so, and any new reader of `aiModel` should check `aiRecipe` first.

### [PASS] Layering and dependency direction match the amendment

`recipes/` sits above `review/` and `metrology/`, and neither imports it. `metrology/` already imports `review/`, and `review/` does not import `metrology/`, so the stated direction adds no cycle. Pipeline, CLI and benchmark code import `recipes/`, as the amendment's code boundary requires. The migration gap noted above is the one exception.

### [PASS] Production cost rule matches the 20261118 amendment

A production recipe review prints no measured bound and is bounded by `pipeline.max_cost_usd`, as the amendment states. The measured-run rule still applies to benchmark commands, and `sq review` gains no cap, which keeps the change to the review path. Because that cap defaults to no cap, a production recipe review is unbounded by default, as every pipeline step is today.

### [PASS] Failure modes are enumerated for reviewer, comb, git, cancellation and unexpected-exception paths

Each row gives an outcome, a log level and an effect, and the success criteria assign a test to each. The hang row is the exception, noted above.

### Run Digest

- Response length: 13978 chars
- Response is newline-free: no
- Tool calls made: 35
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 36
- Tokens — prompt / cached / cache write / completion / reasoning: 1095113 / 980435 / 114652 / 69706 / not computed
- Duration: 307.0 s
- Cost: $0.19 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 15
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 15
- Finding-shaped matches — surviving validation: 15
