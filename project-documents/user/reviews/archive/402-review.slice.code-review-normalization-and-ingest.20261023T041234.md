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
reviewedSha: af04af985c64922448f1ac96afd34e24eb7d51a1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 178056
cachedTokens: 88316
cacheWriteTokens: 89734
completionTokens: 6906
durationSeconds: 57.7
costUsd: 0.437571
costBasis: provider
runId: run-20261023-slices-plan-3d287756
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Scope and boundaries match the architecture"
    location: "project-documents/user/slices/402-slice.code-review-normalization-and-ingest.md#Technical Scope"
  - id: F002
    severity: pass
    category: dependency-direction
    summary: "Dependency direction and the leaf-module decision are sound"
    location: "project-documents/user/slices/402-slice.code-review-normalization-and-ingest.md#Component Structure"
  - id: F003
    severity: concern
    category: data-integrity
    summary: "Content-hash record key can duplicate a review whose file is touched after it is written"
    location: "project-documents/user/slices/402-slice.code-review-normalization-and-ingest.md#D5 — One record per review file, keyed on content"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Failure modes for the ingest I/O paths are only partly enumerated, and the fixture doesn't exercise them"
    location: "project-documents/user/slices/402-slice.code-review-normalization-and-ingest.md#Data Flow"
  - id: F005
    severity: concern
    category: proportionality
    summary: "The design is heavier than this slice needs"
    location: "project-documents/user/slices/402-slice.code-review-normalization-and-ingest.md#Technical Scope"
  - id: F006
    severity: note
    category: dependencies
    summary: "Frontmatter dependencies omit 323"
    location: "project-documents/user/slices/402-slice.code-review-normalization-and-ingest.md:7-8"
  - id: F007
    severity: note
    category: coupling
    summary: "Slice attribution parses a filename convention"
    location: "project-documents/user/slices/402-slice.code-review-normalization-and-ingest.md#D6 — Ingest skips what it can't count honestly"
---

# Review: slice — slice 402

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Scope and boundaries match the architecture

Each architecture requirement for this capability is covered:
- Write-time categories come from the audit vocabulary plus review-only `correctness`.
- The raw string is kept next to the normalized one.
- `other` is the fallback, and `uncategorized` is treated as missing.
- The sync test is extended to the third copy of the vocabulary.
- Ingest writes one record per review file with findings inline, which fits the "coarse records" principle.
- Historical reviews are mapped read-side and labeled `read_side_mapped`.

The exclusions also match the Non-Goals:
- Arch, slice and tasks reviews are untouched.
- The audit skill is unchanged.
- There is no pipeline hook.
- Severities are never mapped (D1, the Technical Requirements, and the disjoint-severity test left unchanged).
- Reports and `other`-share reporting are left to 403.

The record is an optional sibling payload on `MetrologyRecord` with no schema bump, as the "extend the store" principle requires.

### [PASS] Dependency direction and the leaf-module decision are sound

The vocabulary moves to `core/finding_categories.py`. Both `review` (write time) and `metrology` (ingest) import it, and `metrology.models` already imports `review.models`. The review client never imports the metrology package, and `AuditCategory` re-exports keep every existing import and serialized value unchanged. The design also gives a reason for rejecting a template-name check (a label used as logic).

### [CONCERN] Content-hash record key can duplicate a review whose file is touched after it is written

The record id hashes the whole file's bytes. D5 intends a new id only for a genuine re-review. The same hash also changes for any metadata, whitespace or line-ending change. Many existing code-review files carry `dateUpdated`, cost or token frontmatter. A grep found those keys in 131 of the review files, which suggests tooling stamps or edits them. If a review is touched after the first ingest, the next ingest writes a second record for the same review and findings.

403 can pick the latest round per path, but a count across "every round" would double-count. The architecture's "coarse records" principle is meant to keep record count and double-counting under control.

Recommended fix: key the id on the semantic payload (verdict, `reviewedSha`, and the normalized findings list) rather than the raw bytes. Alternatively, state explicitly that metadata-only edits produce a new record and that 403 must dedupe by `review_path`. The design needs to commit to one of these.

A smaller related gap: records are immutable and there is no refresh path. A fix to the D7 alias table cannot reach already-ingested read-side-mapped records. `raw_category` is stored, so a later re-derivation is possible, but the design should say whether that is the intended path.

### [CONCERN] Failure modes for the ingest I/O paths are only partly enumerated, and the fixture doesn't exercise them

Unreadable frontmatter and a missing `reviewType` or `verdict` are handled and logged at WARNING. These ingest paths are not specified:
- **Store write fails mid-run.** The doc says `MetrologyStoreError` fails the command with exit 1. It doesn't say whether the run aborts or continues with the remaining files, or whether the summary of what was written is still printed. Re-running is safe because ingest is idempotent, but the doc should say so.
- **Nonexistent path.** It doesn't say what happens when a `PATHS` argument doesn't exist, or when the default reviews directory is missing or empty.
- **Read race.** It doesn't say whether the content hash and the parsed frontmatter come from the same single read of the file.
- **Concurrent runs.** It doesn't say whether two runs writing the same id are safe (atomic write) or one fails.

The project's failure-mode rule requires each failure mode to be observable and at least one test to assert the signal. The fixture list in Technical Requirements has no malformed-frontmatter file and no `UNKNOWN`-verdict file. The `failed` listing, exit 1, and the WARNING log are therefore untested. Add those fixtures. State the abort-or-continue policy and the nonexistent-path behavior.

### [CONCERN] The design is heavier than this slice needs

Several pieces can be cut or deferred, since nothing in this slice consumes them:
- The `--json` ingest output and the `IngestSummary` `{path, record_id | reason}` lists. A counted human summary plus the WARNING log covers the requirement.
- The `sq review code -v` raw-category line, and the "all interfaces, for parity" requirement. The frontmatter `rawCategory` and the JSON field are enough to keep the raw string.
- Record fields no consumer in this slice or the architecture names: `model`, `revision_number`, and the `list_code_reviews(slice_index=)` filter. Add them when 403 or 420 asks.
- The "Side benefit" subsection, the long six-step walkthrough, and the Special Considerations notes. They restate other documents or describe existing behavior, and they inflate the slice.

The single-member `CommitAbsentReason` enum is fine because the architecture requires "absent with reason". The alias table is assigned by the architecture and should stay. The overall mechanism count (nine new modules and five enums) is high for a slice whose output feeds one downstream report. Trim the items above.

### [NOTE] Frontmatter dependencies omit 323

The body lists 323 as a prerequisite and consumes `AuditCategory`, its sync test and the disjoint-severity test. The frontmatter `dependencies` lists only 320. Add 323 so the dependency is not hidden from tooling.

### [NOTE] Slice attribution parses a filename convention

D6 derives `slice_index` from the `sourceDocument` basename pattern (`{n}-slice.`, `{n}-tasks.`). This is the project's document-naming convention, and the architecture rejects commit-message inference, so it is acceptable. It is still a dependency on a naming scheme. Keep the pattern defined once in a single constant and covered by the test on `0-review.code.review-1.md`, so a naming change fails loudly rather than producing `None` slices silently.

### Run Digest

- Response length: 7607 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 178056 / 88316 / 89734 / 6906 / not computed
- Duration: 57.7 s
- Cost: $0.44 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
