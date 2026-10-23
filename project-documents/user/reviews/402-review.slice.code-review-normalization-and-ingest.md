---
docType: review
layer: project
reviewType: slice
slice: code-review-normalization-and-ingest
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/402-slice.code-review-normalization-and-ingest.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261022
dateUpdated: 20261022
reviewedSha: ba75abc773a22aac86670d2e4d2550883fa7494e
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 174508
cachedTokens: 88036
cacheWriteTokens: 86466
completionTokens: 2628
durationSeconds: 22.7
costUsd: 0.381691
costBasis: provider
runId: run-20261023-slices-plan-3d287756
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Alignment with architecture principles and scope boundaries"
    location: "project-documents/user/slices/402-slice.code-review-normalization-and-ingest.md#Technical Scope"
  - id: F002
    severity: pass
    category: dependency-direction
    summary: "Dependency direction and boundaries"
    location: "project-documents/user/slices/402-slice.code-review-normalization-and-ingest.md#Component Structure"
  - id: F003
    severity: concern
    category: proportionality
    summary: "Read-side alias table is more mapping than the slice needs"
    location: "project-documents/user/slices/402-slice.code-review-normalization-and-ingest.md#D7 — The read-side alias table"
  - id: F004
    severity: concern
    category: proportionality
    summary: "Several decisions and sections restate or pre-empt other documents"
    location: "project-documents/user/slices/402-slice.code-review-normalization-and-ingest.md#Technical Decisions"
  - id: F005
    severity: concern
    category: proportionality
    summary: "Ingest may carry more branching than the slice needs"
    location: "project-documents/user/slices/402-slice.code-review-normalization-and-ingest.md#Data Flow"
  - id: F006
    severity: concern
    category: integration
    summary: "The findings-addressed screen claim has no stated mechanism"
    location: "project-documents/user/slices/402-slice.code-review-normalization-and-ingest.md#Integration Requirements"
  - id: F007
    severity: concern
    category: error-handling
    summary: "Write-time failure mode for a template flag and prompt mismatch is unspecified"
    location: "project-documents/user/slices/402-slice.code-review-normalization-and-ingest.md#D3 — Normalization is opt-in per template, after the shared parser"
  - id: F008
    severity: note
    category: process
    summary: "Verification step 4 depends on a live review by the Project Manager"
    location: "project-documents/user/slices/402-slice.code-review-normalization-and-ingest.md#Verification Walkthrough"
---

# Review: slice — slice 402

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Alignment with architecture principles and scope boundaries

The design honors the architecture's constraints:
- Normalization applies to `code` reviews only.
- `AuditCategory` and the audit skill are unchanged.
- Severities stay disjoint.
- Records are coarse, one per review file with findings inline.
- It extends the 320 store with an optional sibling payload.
- There is no pipeline hook.
- `uncategorized` is treated as missing, never as a category.
- Read-side mapped records are marked.
- The sync test extends to the third copy of the vocabulary.
Every success criterion in the 402 slice plan entry is covered.

### [PASS] Dependency direction and boundaries

Moving the vocabulary to a `core` leaf module keeps `review` from importing `metrology` at parse time. Re-exports keep existing imports working. The slice depends only on 320 and 323, which matches the plan's note that 402 can run in parallel with 400 and 401.

### [CONCERN] Read-side alias table is more mapping than the slice needs

D7 carries about 45 hand-curated historical strings across 10 categories, plus an explicit `other` list. The architecture notes that mapping free-form strings "would need a lookup table that misses". The slice plan only requires that historical reviews are "mapped read-side and marked as mapped". The design doesn't say how much of the historical corpus the table needs to cover for 403's counts to be useful. It rests on 70 distinct strings across 116 files, and the `other` list is itself a judgment call. Cut the table to the high-frequency strings (error-handling, testing, design, dry, correctness, and a few more) and send the rest to `other` with the raw string kept. The `read_side_mapped` flag already tells reports these are inferred. Because ingest re-derives records on every run, the table can be extended later without migration.

### [CONCERN] Several decisions and sections restate or pre-empt other documents

Some content can be cut or shortened without losing scope:
- D9 (command placement) records a naming choice and lists a rejected nesting alternative.
- D1 and D2 have long "Rejected" lists.
- The Overview, Value and Technical Scope sections repeat the architecture's rationale.
- Two failure-mode rows describe non-issues: "File changes between discovery and read" is "harmless", and the concurrent-run row notes that `_write_atomic` already makes the last write win.
The slice stays within scope. The cost is review and maintenance surface, so trim these to one line each.

### [CONCERN] Ingest may carry more branching than the slice needs

Ingest has four skip or fail paths (`not-code-review`, `unknown-verdict`, unreadable frontmatter, missing `reviewType`/`verdict`) and a multi-part summary. It also has the `unnormalized_count` severity path and `--cwd` handling for PATHS that can be files or directories. The `UNKNOWN`-verdict skip is justified by the "absent is not zero" principle. The summary breakdowns (`without reviewed commit`, `without slice`, `write-time` versus `read-side mapped`) duplicate information 403 will compute from the records. Keep the verdict skip and the failure handling. Cut the extra summary counters to the ingested, skipped and failed totals.

### [CONCERN] The findings-addressed screen claim has no stated mechanism

The Integration Requirements say the findings-addressed screen "still settles prior findings correctly when round 1 was written before this slice and round 2 after", with mismatches falling through to the judge. The Technical Scope and Component Structure don't touch that screen. There is no check in the Success Criteria or test list that a mixed-vocabulary pair doesn't break it, and the design doesn't explain how category matching in that screen works. Either add one test covering a round 1 with a free-form category and a round 2 with a normalized category, or drop the claim and note the screen as unaffected.

### [CONCERN] Write-time failure mode for a template flag and prompt mismatch is unspecified

The ingest I/O paths have a failure-mode table. The write-time path does not. The case worth covering is a model response with no `category:` tags on any finding. D4 maps a missing category to `uncategorized` (never `other`). The design doesn't say whether a review where every finding is uncategorized is flagged, logged or counted. That is the observable signal that the prompt change failed, which Risk Assessment names as the main technical risk. Add one line: log a WARNING when `categories_normalized` is true and the share of `None` categories is 100% (or above a stated threshold), and add a test for it.

### [NOTE] Verification step 4 depends on a live review by the Project Manager

Step 4 and the final implementation note ask the Project Manager to run `sq review code`. Live runs are pre-authorized and spend is capped, so this is not a blocking gate. It reads as a manual step, though, and the implementer can run it directly once the slice is implemented.

### Run Digest

- Response length: 6349 chars
- Response is newline-free: no
- Tool calls made: 3
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 4
- Tokens — prompt / cached / cache write / completion / reasoning: 174508 / 88036 / 86466 / 2628 / not computed
- Duration: 22.7 s
- Cost: $0.38 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8

## Response

Applied to the design on 20261023.

- **Findings-addressed screen (CONCERN): mechanism stated, test added.** `screens.py` matches on exact `(location, category)`, and a mismatch leaves the finding as residue for the judge. Integration Requirements now say so and require a mixed-vocabulary test (free-form round 1, normalized round 2).
- **Write-time failure mode (CONCERN): fixed.** The review client logs a WARNING when the template normalizes, findings exist and none carries a `category:` tag. The review is still written, and a `caplog` test is required.
- **Alias table (CONCERN): cut.** D7 keeps the 16 strings with four or more findings in the corpus. Everything else is `other` with the raw string kept, and the table can grow later without migration.
- **Ingest branching (CONCERN): partly applied.** The extra summary counters are gone (ingested, skipped, failed remain). The verdict skip and failure handling stay, as the review says.
- **Restated sections (CONCERN): partly applied.** D9's rejected alternative and D1's second rejection are cut. The "harmless" file-change row and the concurrent-run row are removed from the failure-mode table. Overview, Value and Scope are left.
- **Live review step (NOTE): done.** The walkthrough and the implementation notes no longer assign step 4 to the Project Manager.
