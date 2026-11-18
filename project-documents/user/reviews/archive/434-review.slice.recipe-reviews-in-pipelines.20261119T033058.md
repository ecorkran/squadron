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
reviewedSha: f9b98c11ed296af7a1649bde3c80de1fe5a2ab7a
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 16
effort: xhigh
turns: 17
promptTokens: 1039519
cachedTokens: 926385
cacheWriteTokens: 113110
completionTokens: 81117
durationSeconds: 364.7
costUsd: 0.200213
costBasis: provider
runId: run-20261118-p4-b5566cfd
squadronVersion: 0.24.34
findings:
  - id: F001
    severity: fail
    category: architecture
    summary: "`sq review` recipe reviews are not bounded by the cost cap the architecture requires"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:249-254"
  - id: F002
    severity: concern
    category: error-handling
    summary: "The absent-effort case for `effort_sent` is not specified"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:242"
  - id: F003
    severity: concern
    category: architecture
    summary: "The comb's input differs from the one the benchmark measured"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:172"
  - id: F004
    severity: concern
    category: security
    summary: "The comb containment claim does not hold for every profile"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:176"
  - id: F005
    severity: concern
    category: integration
    summary: "`aiModel` now holds a recipe name, and two readers are missing from the design"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:228-233"
  - id: F006
    severity: concern
    category: integration
    summary: "Finding counts in ingest and in the 400 and 431 reports change meaning for recipe reviews"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:235"
  - id: F007
    severity: concern
    category: integration
    summary: "431's read contract leaves recipe rows undefined"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:350-353"
  - id: F008
    severity: concern
    category: architecture
    summary: "Stage identity is built in two places"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:242"
  - id: F009
    severity: concern
    category: proportionality
    summary: "Three pieces the requirements do not need"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:175"
  - id: F010
    severity: note
    category: architecture
    summary: "\"Nothing runs two review calls at once\" is stated too strongly"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:163"
  - id: F011
    severity: note
    category: consistency
    summary: "The plan entry and the design disagree on the merged findings and on scope"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:183"
  - id: F012
    severity: note
    category: consistency
    summary: "The comb prompt is still a draft when production starts using it"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:173"
  - id: F013
    severity: pass
    category: architecture
    summary: "Code boundary and dependency direction hold"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:86-107"
  - id: F014
    severity: pass
    category: error-handling
    summary: "Failure modes are enumerated with observable signals"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:188-214"
  - id: F015
    severity: pass
    category: nfr
    summary: "Parent NFRs are restated with targets"
    location: "project-documents/user/slices/434-slice.recipe-reviews-in-pipelines.md:281-286"
---

# Review: slice — slice 434

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] `sq review` recipe reviews are not bounded by the cost cap the architecture requires

D9 says "a production review, single-model or recipe, is bounded by `pipeline.max_cost_usd` (947), as the 20261118 amendment states." The same entry says `sq review` "has no cap today for any model, and this slice adds none." The 947 cap is enforced by the pipeline executor per invocation, so a `sq review --model <recipe>` run (two reviewers and up to four combs, six calls) is unbounded. The amendment's Cost rule names `sq review` in the production path it changes. Line 254 also misstates 947, which checks the cap after every action, not "between steps." The review is one action, and a split review runs the whole recipe per part inside it (line 165), so the overshoot is the sum over parts.

Fix, decided by the PM: either the `sq review` recipe path reads the cap and stops between stages when the sum exceeds it (state that this is stricter than 947), or the PM amends the 20261118 Cost rule to exempt `sq review`. D9 must not claim compliance in the meantime.

### [CONCERN] The absent-effort case for `effort_sent` is not specified

D8 sets `effort_sent` to the stage result's `effort`, "the effort sent (430 D6)." 430 D6 writes that field only when the provider applies effort (slice 931 D4), so for other providers the key is absent. The design does not say what the record holds then. The architecture's rule is "Effort that was not sent is recorded as not sent, not as the alias's value" (420 arch, Absent is not zero). A `.get("effort", alias_effort)` would violate it. Require `null` for an absent key, a test for that case, and list 420 (effort sent on usage records) as a prerequisite beside 430 (lines 71–73).

### [CONCERN] The comb's input differs from the one the benchmark measured

D4 gives the production comb the file list from `assert_reviewable_scope` for the review's diff spec, and drops 430's `git diff --name-only <base> HEAD` list. 430 D6 (lines 274–275) uses the latter, and runs its comb as a `_stage` subprocess, where D4 runs it in process. Both use the same template hash, so their rows share a prompt identity while the comb sees different inputs. The architecture requires a benchmark to measure "the prompt and step a real run uses" (420 arch, Replays run the production pipelines). The 430 plan says the winning recipe becomes the production review configuration, so that choice rests on a comb that production does not run. Either both paths compute the file list the same way (and 430's stored results are re-run or flagged), or the input rule goes into the comb's prompt identity and 430's report states the difference.

### [CONCERN] The comb containment claim does not hold for every profile

D4 says "the comb's read-only jailed tools are its only containment," and line 464 says the comb reads "with the jailed builtins only." 430 D6 (line 270) records that the jailed read tools refuse paths outside the working directory only for OpenAI-compatible profiles, and that "review tools under the `sdk` and Codex profiles are not confined to the working directory." The design does not say which tool implementation a comb gets for its profile. The 430 plan's first recipe uses an opus-high comb, and the architecture says Claude SDK sessions use Claude Code's own tool controls (420 arch, Containment). State the comb's tool binding per profile, and either refuse comb aliases whose read tools are not jailed or say that such combs read outside the tree.

### [CONCERN] `aiModel` now holds a recipe name, and two readers are missing from the design

D7 writes the recipe name into `aiModel` and lists two readers. Two other stats report readers (the reviews report and the review-rounds report) read `aiModel` into a model field and do not check `aiRecipe`. They would show a recipe review as a model named `haiku-solr-luna-opus`. That is misattribution, not a failure, and the design's list is not backed by a search. Options: (a) leave `aiModel` absent for recipes and carry the name in `aiRecipe: <name>`, so unaware readers show "no model" rather than a wrong one; or (b) enumerate every reader and the change each needs. I recommend (a). The rule "any new reader checks `aiRecipe` first" cannot be enforced as written.

### [CONCERN] Finding counts in ingest and in the 400 and 431 reports change meaning for recipe reviews

D7 says review ingest is unchanged and "400's reports see one review with the kept findings." A single-model review's findings are the reviewer's full set, while a recipe review's are the post-comb set (D5 keeps dropped findings out of the file). Finding counts from ingest, 400's reports and 431's per-model finding counts would mix the two without a flag. The architecture requires that results be compared only when they match, and that the rest be flagged (420 arch, Results stay comparable over time). Either the recipe is marked where those counts are read, or the design states that recipe counts are post-comb and that those reports must split on `aiRecipe`.

### [CONCERN] 431's read contract leaves recipe rows undefined

431's plan gives each row a model and an effort sent. A recipe has no single model or effort; each stage has its own (D10). The design does not say what 431 puts in those columns or whether recipe reviews form a separate table. The key `run_id`, `step_name`, `iteration` is also not unique. A review that fails and is rerun on resume (line 199–200) writes a second record under the same key, and both attempts cost money. The design must state how 431 handles recipe rows and whether retries are counted as reviews, or count only the latest record per key.

### [CONCERN] Stage identity is built in two places

D8 fills `StageConfig` in the runner "from what each stage call was resolved with," and keeps `live_stage_config` in benchmark because it depends on the auth check. That gives two functions building the same five-field identity, which `config_key` hashes. The architecture puts code that both production and the benchmark use in `recipes/` (420 arch, Amendment 20261118), and the project forbids duplicated logic. Move the pure part (alias settings to `StageConfig`) into `recipes/`, and keep only the auth dependency in benchmark. Otherwise the two can diverge, and D10's row key stops matching 430's rows.

### [CONCERN] Three pieces the requirements do not need

- **`tree_head` and `tree_dirty`** (line 175, schema line 337, failure row line 211): no reader in the design uses them. 431 and 433 read run keys and recipe names, and D10 uses the recipe hash and stage identities. They cost a git read, a failure path, a test and two schema fields. Keep them only with a named reader.
- **Shipping the three recipes as package data** (line 139, Migration line 306): the architecture and plan ask only that a recipe name be accepted. Shipping changes the package before 430's live run has validated the comb prompt. The lighter option is to search the project recipe directory and keep the files in the repo's reference folder, which covers squadron's own walkthrough. This is a PM decision.
- **The JSON `recipe` object** (line 324): a new output field the plan does not require. The name, `complete` and record id are already in the pipeline metadata and the record. Cut it unless a consumer is named.

### [NOTE] "Nothing runs two review calls at once" is stated too strongly

D3 says nothing in squadron runs two review calls at once in one process. 947 (D5, line 170) says a `fan_out` step runs its branches concurrently with `asyncio.gather`, and nothing in the design stops a review step from sitting inside one. The per-stage state is local, so this is probably harmless. Narrow the claim to the recipe runner's own stages, or verify it.

### [NOTE] The plan entry and the design disagree on the merged findings and on scope

Plan entry 434 (420-slices, line 207) says the step's findings "are the recipe's kept findings." D5 (line 183) and the criterion at line 369 also add the uncombed NOTE and PASS findings. The plan's wording should change to match. The plan entry also omits the real-work report (D10), which plan entry 433 names as 434's, and the refusals in D2 (lines 148–153). Update the parent so the slice's scope is written down there.

### [NOTE] The comb prompt is still a draft when production starts using it

430's plan calls the comb prompt "a first draft," and #369 waits for "the first recipe's live run holds up" before a recipe becomes a default. D4 makes that draft the production comb for every user who opts in. D11 keeps the default, so the exposure is limited to opt-in users. Say so in D4.

### [PASS] Code boundary and dependency direction hold

`recipes/` imports `review/` and `metrology/`, and `pipeline/`, `cli/` and `benchmark/` import it. The design states that `review/` and `metrology/` never import it (line 88) and tests it (line 389). `SCORED_SEVERITIES` moves down to `review/` so 430 imports rather than the reverse. This matches the 20261118 code boundary.

### [PASS] Failure modes are enumerated with observable signals

D5's two tables cover provider errors, malformed or missing comb decisions, duplicate and unknown ids, an uncomputable diff range, a failed head read, an unexpected exception, cancellation and a slow or hung stage. Each row has a log level and an effect. D8 (line 244) covers a failed record or sidecar write. The success criteria name a test per row (lines 374–382).

### [PASS] Parent NFRs are restated with targets

The design restates the serial-stage rule (line 283), the record-size rule with inline findings and sidecar raw output (line 284), and the coarse-record count (line 285). Cost is restated through 947 (lines 249–254), subject to the FAIL above. It also keeps "measure, never gate" and produces no composite score (D10, D11).

### Run Digest

- Response length: 11961 chars
- Response is newline-free: no
- Tool calls made: 16
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 17
- Tokens — prompt / cached / cache write / completion / reasoning: 1039519 / 926385 / 113110 / 81117 / not computed
- Duration: 364.7 s
- Cost: $0.20 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 15
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 15
- Finding-shaped matches — surviving validation: 15

## Response (20261118, PM session)

- F001: fixed in the architecture. The 20261118 Cost rule now says a standalone `sq review` is uncapped, as for a single model; D9 says the same and corrects the cap check to "after each action".
- F002: fixed. `effort_sent` is `null` when the provider applied no effort, with a test; 420 added as a prerequisite.
- F003: dropped. For a committed diff the two file lists differ only by exclude patterns; not worth a re-run of 430's data.
- F004: fixed. D4 states the comb's tool controls per profile, which are no wider than the reviewer's.
- F005: dropped. A report row named after the recipe is correct attribution; D2 forbids a recipe sharing an alias's name.
- F006: dropped. Reports that group by `aiModel` already separate recipe reviews by name.
- F007: dropped. 431 is not designed yet; its design decides how it reads recipe rows and retries.
- F008: fixed. The pure part of `live_stage_config` moves to `recipes/stage_config.py`.
- F009: `tree_head`/`tree_dirty` and the JSON `recipe` object cut. Shipped recipes kept: a recipe name must work in other repos, which have no copy of squadron's reference folder.
- F010: fixed (claim narrowed to the recipe runner).
- F011: plan entry now includes the uncombed NOTE/PASS findings.
- F012: dropped. D11 keeps the default, so only opt-in users get the draft comb.
