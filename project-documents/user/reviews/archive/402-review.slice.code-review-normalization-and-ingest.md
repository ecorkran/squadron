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
reviewedSha: 420f234f8f922c5419810a5f7c722b7c01081c2b
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
turns: 5
promptTokens: 175368
cachedTokens: 88443
cacheWriteTokens: 86919
completionTokens: 3625
durationSeconds: 34.1
costUsd: 0.393513
costBasis: provider
runId: run-20261023-slices-plan-3d287756
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: concern
    category: architecture-alignment
    summary: "Content-keyed record id can produce more than one record per review file"
    location: "project-documents/user/slices/402-slice.code-review-normalization-and-ingest.md#D5 — One record per review, keyed on the review's semantic content"
  - id: F002
    severity: concern
    category: dependencies
    summary: "Hidden coupling to 401 despite \"no dependency on 401\""
    location: "project-documents/user/slices/402-slice.code-review-normalization-and-ingest.md#Dependencies"
  - id: F003
    severity: concern
    category: proportionality
    summary: "Design is heavier than the slice requires in a few places"
    location: "project-documents/user/slices/402-slice.code-review-normalization-and-ingest.md#Technical Decisions"
  - id: F004
    severity: note
    category: error-handling
    summary: "NFR and failure-mode coverage is adequate for the new I/O paths"
    location: "project-documents/user/slices/402-slice.code-review-normalization-and-ingest.md#Data Flow"
  - id: F005
    severity: pass
    category: architecture-alignment
    summary: "Layering and dependency direction"
    location: "project-documents/user/slices/402-slice.code-review-normalization-and-ingest.md#Component Structure"
  - id: F006
    severity: pass
    category: architecture-alignment
    summary: "Alignment with the architecture's category and measurement principles"
    location: "project-documents/user/slices/402-slice.code-review-normalization-and-ingest.md#Technical Scope"
---

# Review: slice — slice 402

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Content-keyed record id can produce more than one record per review file

The architecture's "Coarse records" principle says "one review record per review file", because the store reads every record file on every query. D5 keys the id on `review_path`, `reviewedSha`, `verdict` and the findings. A re-review that rewrites the same path therefore adds a record and keeps the earlier round's record. The slice states this on purpose, so that 403 can choose between "every round" and "latest per path". The slice has no stated consumer for the every-round option. The architecture says nothing about it, and `Excluded` rules out ingesting earlier rounds from git history.

Record count grows with each re-ingest of a changed file, which is the cost the architecture asks to minimize. 403 also gets a dedup obligation (latest per path) that nothing in the architecture assigns. The fix is one of two things:
- Key the id on project plus `review_path`, so a re-ingest replaces the record. The cost is that a re-review overwrites the earlier round's record.
- Keep content keying, and justify the extra records in the doc against a named requirement. State 403's latest-per-path rule as a contract in "Provides to Other Slices" and note the record-growth trade-off.

### [CONCERN] Hidden coupling to 401 despite "no dependency on 401"

The Dependencies section says "No dependency on 400 or 401", and the frontmatter lists only 320 and 323. The CLI component, however, is "mounted onto `metrology_app`, following the `metrology_snapshot.py` pattern". The envelope field is added "the same way" as `code_snapshot`, and `RECORD_TYPE_CODE_SNAPSHOT` already exists in `models.py`. Both appear to come from the snapshot slice, 401. Both files exist in the tree today, so there is no immediate breakage. But the doc states the independence of 401 and then relies on 401's artifacts: the command-mounting pattern and the envelope-extension pattern. If 401's registration approach changes, this slice is affected. Either list 401 as a soft prerequisite for the mount point, or say that only the established pattern is followed and no 401 code is imported.

### [CONCERN] Design is heavier than the slice requires in a few places

Several parts could be cut or deferred without losing anything the architecture assigns to this slice:
- **`CommitAbsentReason`** is an enum with a single member (`NO_REVIEWED_SHA`), plus a paired validator. The "absent with a reason" rule is satisfied by a nullable commit and the reason enum, but a one-value enum guards nothing yet. Keep it only if 403 or 401 needs a second reason soon. Otherwise a boolean or the existing absence convention is lighter.
- **`IngestSkipReason`, `IngestSummary` and `CategorySource`** are three more closed enums and types for a command whose output is five counted lines.
- **The semantic-hash payload design** (canonical JSON, frontmatter exclusions, a refresh-via-replace story) exists only because of the content keying in the first concern. Path keying would remove most of D5.
- **The 11-row alias table** is built from 116 files and maps 70 strings, with an `other (by design)` row listing a dozen more. Arch 400 accepts read-side mapping, so the table itself is in scope. The compound-string splitting rule adds a second mechanism. Consider mapping only exact lenient-normalized strings and sending compounds to `other`, unless the corpus shows compounds are a large share of the 116 files.

Trim these, or justify each against a named requirement.

### [NOTE] NFR and failure-mode coverage is adequate for the new I/O paths

The ingest failure-mode table covers a missing path, a missing directory, an empty directory, malformed frontmatter, a store write failure, a file changing mid-run and concurrent runs. Each has a log level and an exit code. The tests assert the WARNING with `caplog` and the exit codes. The architecture states no latency or throughput NFR for this path, so nothing needs restating. One gap remains: a single oversized or non-UTF-8 review file. It would probably land under "frontmatter unreadable", but the table doesn't say so.

### [PASS] Layering and dependency direction

The `core/finding_categories.py` leaf module lets `review` import the vocabulary without importing `metrology`. `metrology` imports `review.models` in one direction only, so there are no cycles. Re-exports keep existing `AuditCategory` imports working. The shared parser stays template-agnostic, and normalization sits in the review client's parse closure behind a template flag. Keying on `template.name` is explicitly rejected, which matches the "no labels as logic" rule.

### [PASS] Alignment with the architecture's category and measurement principles

The slice delivers what the architecture assigns to it:
- A closed vocabulary plus `correctness`.
- The raw string kept beside the normalized value.
- `other` as the honest fallback.
- Ingest of one record per file, tied to project, commit and slice where known.
- The extended three-copy sync test.
- `uncategorized` treated as missing, never as `other`.
- Review and audit severity scales kept separate.

Reports, rollups and slice-range records are correctly left to 403. The tech-debt-audit skill is not changed. There is no pipeline hook and no gate.

### Run Digest

- Response length: 6693 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 175368 / 88443 / 86919 / 3625 / not computed
- Duration: 34.1 s
- Cost: $0.39 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
