---
docType: review
layer: project
reviewType: slice
slice: slice-ranges-and-rollup-reports
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/403-slice.slice-ranges-and-rollup-reports.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261022
dateUpdated: 20261022
reviewedSha: 2de1e637647c54a12d2f69b2bf8bf213f53b303e
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 98969
cachedTokens: 11266
cacheWriteTokens: 87699
completionTokens: 5936
durationSeconds: 52.7
costUsd: 0.412021
costBasis: provider
runId: run-20261023-slices-plan-3d287756
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Core architectural principles are honored"
    location: "project-documents/user/slices/403-slice.slice-ranges-and-rollup-reports.md#Technical Decisions"
  - id: F002
    severity: note
    category: architecture-alignment
    summary: "D3 refines the architecture's \"fork commit against merge commit\" definition"
    location: "project-documents/user/slices/403-slice.slice-ranges-and-rollup-reports.md:193-197"
  - id: F003
    severity: concern
    category: integration-points
    summary: "AdapterContext contract change isn't carried through to 401's adapters"
    location: "project-documents/user/slices/403-slice.slice-ranges-and-rollup-reports.md:70-73, 205-209, 317-318"
  - id: F004
    severity: concern
    category: architecture-alignment
    summary: "Per-slice records and per-slice store lookups work against the \"coarse records\" principle"
    location: "project-documents/user/slices/403-slice.slice-ranges-and-rollup-reports.md:106-124, 166-171, 199-203"
  - id: F005
    severity: concern
    category: proportionality
    summary: "Design is heavier than the slice needs"
    location: "project-documents/user/slices/403-slice.slice-ranges-and-rollup-reports.md:292, 199-203, 126-140"
  - id: F006
    severity: concern
    category: error-handling
    summary: "Failure modes for new I/O paths leave hangs, concurrent writes and unreportable slices unstated"
    location: "project-documents/user/slices/403-slice.slice-ranges-and-rollup-reports.md:152-164, 166-173"
  - id: F007
    severity: note
    category: dependency-direction
    summary: "metrology depends on review/git_utils"
    location: "project-documents/user/slices/403-slice.slice-ranges-and-rollup-reports.md:76, 87-89"
  - id: F008
    severity: note
    category: scope
    summary: "Live ESLint plugins during export"
    location: "project-documents/user/slices/403-slice.slice-ranges-and-rollup-reports.md:209"
---

# Review: slice — slice 403

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Core architectural principles are honored

The design matches the architecture on each of these points:
- **Measure, never gate:** no pipeline hook, and a test asserts that no serialized report has a key containing `score` (D8).
- **Store:** `slice_range` is an optional sibling payload on `MetrologyRecord`, with no new store and `schema_version` unchanged.
- **Export:** non-HEAD commits are measured via `git archive`, so nothing is written to the measured repo's `.git`.
- **Absent is not zero:** the D6 lockfile gate matches the architecture's rule that the current environment is used only when the lockfile matches.
- **Comparability:** D7 diffs a row only on full identity match, and breaks are named, as the architecture requires.
- **Severity:** severities are never mapped across scales (D8).
- **Attribution:** D9 attributes commits only through the merge convention, which the architecture accepts.

### [NOTE] D3 refines the architecture's "fork commit against merge commit" definition

The architecture defines a slice's before and after as the fork commit against the merge commit. The design uses `M^1` against `M` instead. It justifies this: the fork-to-merge diff would include unrelated work merged into the target in the meantime. It also stores `fork_sha` and `tip_sha`, so 420 can still get `fork..tip`. For fast-forwards the two definitions agree. The deviation is explicit and reasoned. Consider recording it back in the architecture doc so the two don't drift.

### [CONCERN] AdapterContext contract change isn't carried through to 401's adapters

`environment_root` is a required field with no default. Only "both 400 adapters" are updated. 401 is designed but not implemented, and it adds tool-resolving adapters for complexity, duplication and coverage. Those adapters will resolve tools from `repo_root`, and in an export that is a temp tree with no `.venv` or `node_modules`.
- 403 calls 401 "not a prerequisite" and says its metrics "appear with no 403 change". That is false for any 401 adapter that resolves a tool. Such an adapter either breaks at export or reports the tool as absent.
- The gap is a hidden dependency. Neither document says which slice owns the update.
- Fix: state that 401's adapters must resolve tools from `environment_root`, and amend the 401 design or add a verification step for it. Alternatively, define the contract in the slice so a 401 adapter that ignores `environment_root` fails a conformance test.

### [CONCERN] Per-slice records and per-slice store lookups work against the "coarse records" principle

The architecture says the store reads every record file on every query, so record count is the cost that matters.
- **Record count:** D1 writes one `slice_range` record per slice. Squadron has hundreds of slices, so that adds hundreds of files, each scanned by every later query.
- **Query count:** the resolution flow calls `store.get_slice_range(project_id, index)` for each slice. With `slice-ranges` and no arguments, that loops over every slice, and each call is a full store scan.
- Fix: say that the no-argument path reads once via `list_slice_ranges` and resolves from memory. Alternatively, store one record per project holding all slices' landings. If per-slice records are kept for the append-only merge semantics, record that reasoning against the architecture's principle.

### [CONCERN] Design is heavier than the slice needs

The design has 10 decisions, 4 commands, a comparability module, a tar-extract-plus-diff-tree export verifier, and 3 report assemblers. These can be cut or deferred if the slice plan doesn't assign them:
- **History bucketing:** `report history` adds first-parent ordering with an off-line fallback by commit date, audit totals per commit, and review findings bucketed by calendar month. Month bucketing is the part to defer. `history` could list snapshots in first-parent order with break markers and leave the rest to a later slice.
- **No-argument discovery:** `slice-ranges` with no arguments combines local branch indices with merge-message grepping to find every slice (D4). The explicit `INDEX...` form meets the durability requirement, and `report slice` already persists on use.
- **Pathspec cross-checks:** the export runs both `git archive` and a separate `git diff-tree` file list, then compares them to detect `export-ignore`. A single check on the extracted tree against `git ls-files`-equivalent output would be lighter. Alternatively, drop the check and document the `export-ignore` difference.
- **Prose duplication:** the Technology Choices and Risk sections restate decisions already made in D5 and D6.

### [CONCERN] Failure modes for new I/O paths leave hangs, concurrent writes and unreportable slices unstated

The failure table is thorough on non-zero exits and bad inputs. These gaps remain:
- **Hangs:** `git archive`, tar extraction and `git diff-tree` have no stated timeout. The table bounds only tool hangs, via `snapshot_tool_timeout_s`. A "returns `None`" row presumes `run_git` enforces a timeout, which the document doesn't state. A very large repository could hang the export.
- **Disk and symlink:** a full disk during extraction and a failure creating the `node_modules` symlink have no row.
- **Concurrent writers:** `record_slice_range` merges the stored record and writes it back. Two concurrent runs, such as `slice-ranges` and `report slice` on the same slice, can lose a landing. This matters because landings are described as append-only and durable.
- **Stored landing whose commit is gone:** after a rebase or force-push, `ensure_snapshot` raises. The slice is then unreportable, including its source-document reviews, and the only remedy is deleting the record by hand. The rest of `report slice` could degrade to the unresolved path (D9) instead.
- **Observability:** the review rules call for an observable signal per failure mode. The success criteria list no test that asserts one for the resolver's INFO signal.

### [NOTE] metrology depends on review/git_utils

The metrology package imports the git helpers from `review/git_utils.py`, whose slice helpers are now renamed public. The dependency direction is acceptable, since it reuses the code the architecture names and avoids duplication. If more git primitives start to accumulate there, consider moving the shared ones to a neutral module later.

### [NOTE] Live ESLint plugins during export

The `node_modules` symlink means an exported commit's ESLint results use the live plugins. This is acknowledged as the existing #250 gap and excluded from scope. The architecture says an exported commit's config should be read, and it is. The plugin versions are the unrecorded part.

### Run Digest

- Response length: 8226 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 3
- Tokens — prompt / cached / cache write / completion / reasoning: 98969 / 11266 / 87699 / 5936 / not computed
- Duration: 52.7 s
- Cost: $0.41 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
