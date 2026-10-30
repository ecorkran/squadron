---
docType: review
layer: project
reviewType: code
slice: slice-ranges-and-rollup-reports
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/403-slice.slice-ranges-and-rollup-reports.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261029
dateUpdated: 20261029
reviewedSha: 0f1274ca59b0e50656d8e436be4fd2cca55c77e1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 0
diffTruncated: false
turns: 1
promptTokens: 124932
cachedTokens: 3232
cacheWriteTokens: 121698
completionTokens: 1751
durationSeconds: 17.1
costUsd: 0.556418
costBasis: provider
squadronVersion: 0.24.9
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "Merge landing assumes a two-parent merge and unvalidated git output"
    location: "src/squadron/metrology/slice_range.py:_merge_landing"
  - id: F002
    severity: concern
    category: correctness
    summary: "Concurrent slice-range writes still have a lost-update window"
    location: "src/squadron/metrology/slice_range.py:_persist_gained"
  - id: F003
    severity: concern
    category: error-handling-observability
    summary: "Silent skip when the live and exported lockfile hashes cannot be compared"
    location: "src/squadron/metrology/snapshot/python_types.py:_lockfile_differs"
  - id: F004
    severity: concern
    category: architectural-decay
    summary: "Duplicated git-call-failure handling and hash-preview constants"
    location: "src/squadron/cli/commands/metrology_quality_support.py:commit_exists"
  - id: F005
    severity: concern
    category: performance-resource
    summary: "`_audit_section` recomputes the full baseline report once per landing"
    location: "src/squadron/metrology/quality_report/slice_report.py:_baseline_for"
  - id: F006
    severity: concern
    category: architectural-decay
    summary: "Report builders and renderers mix several responsibilities and exceed size guidance"
    location: "src/squadron/metrology/quality_report/compare.py:compare_snapshots"
  - id: F007
    severity: concern
    category: type-contract-debt
    summary: "Exceptions swallowed or lost with weak type contracts at the CLI layer"
    location: "src/squadron/cli/commands/metrology_quality.py:_as_json"
  - id: F008
    severity: note
    category: test-debt
    summary: "Test coverage is strong"
    location: "tests/metrology"
---

# Review: code — slice 403

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Merge landing assumes a two-parent merge and unvalidated git output

`_merge, before, tip, *_other_parents = line.split()` raises `ValueError` if the matched merge commit has fewer than two parents. This can happen if the grep pattern matches a non-merge entry. It is unlikely, because `--merges` is passed. The same unpack would also accept octopus merges and silently drop the extra parents. `ValueError` is not caught by `exit_on_failure`, so the CLI would crash with a traceback instead of reporting `GIT_ERROR`. An explicit parent-count check that maps to a reported failure would be safer.

### [CONCERN] Concurrent slice-range writes still have a lost-update window

The re-read followed by a write is not atomic. The docstring admits the remaining window, and a WARNING is logged only when the record changed before the re-read. A race inside the window loses landings silently. Landings are described as durable, so a file lock around the read-merge-write would remove the problem. If concurrent runs are explicitly unsupported, this is acceptable but should be enforced rather than only documented.

### [CONCERN] Silent skip when the live and exported lockfile hashes cannot be compared

`file_content_hash` on `repo_root / LOCKFILE` was already checked as a file by `_check_lock_and_venv`. The live lockfile is also checked as a file, but a read error (`OSError`) would propagate uncaught as a raw traceback rather than an `ENVIRONMENT_UNRESOLVED` absence. This is minor. The more material issue is that `_lockfile_differs` is reached only when the roots differ, and that path depends on `resolve()` comparisons that can misfire with symlinked roots.

### [CONCERN] Duplicated git-call-failure handling and hash-preview constants

The code duplicates three kinds of logic.
- `commit_exists`, `first_parent_history`, `resolve_commit` and `_archive` each rebuild the "run_git returned None → log, echo, exit" pattern.
- `_SHA_PREVIEW_CHARS` is defined in both `metrology_quality_support.py` and `slice_report.py`.
- `_HASH_PREVIEW_CHARS` is defined in both `compare.py` and `slice_report.py`.
Preview lengths of 8 and 12 are also hard-coded in several places, such as `[:12]` in `compare.py` and `_SHA = 8` in `render.py`. This breaks the "define once" rule. A shared constants module would fix it.

### [CONCERN] `_audit_section` recomputes the full baseline report once per landing

`_baseline_for` calls `baseline_report(store, ...)` on every landing, and `_audit_section` also calls `list_audit_runs` on every landing. Both do a full store scan. With many landings, or with `report slice` run over a large store, the repeated scans are wasted work. Computing both once in `build_slice_report` and passing them in would avoid it.

### [CONCERN] Report builders and renderers mix several responsibilities and exceed size guidance

`compare_snapshots` runs well over 50 lines and mixes row iteration, break accumulation and delta computation. `_identity_breaks` also repeats near-identical tool, rule-set and environment text formatting. `metrology_quality.py` builds the commands and also holds rendering and JSON shaping for `slice-ranges`, while `render.py` has a parallel renderer module. Extracting small helpers would bring these within the project guidance.

### [CONCERN] Exceptions swallowed or lost with weak type contracts at the CLI layer

`_as_json` returns `dict[str, object]` hand-built for `slice-ranges`, while the `report` commands emit Pydantic models. This produces two ways of doing the same thing and an untyped output contract. A `BaseModel` for the `slice-ranges` output would be consistent. Separately, `take_commit_for` is public but used only inside the module.

### [NOTE] Test coverage is strong

The slice adds extensive tests. They cover the resolver against real throwaway repos, the export safety filter, comparability breaks, the `GIT_ERROR` observable signal, the no-score guard on the models and CLI exit codes. Failure modes are asserted through log output as the rules require. No gap was found beyond the paths noted above.

### Run Digest

- Response length: 4865 chars
- Response is newline-free: no
- Tool calls made: 0
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 1
- Tokens — prompt / cached / cache write / completion / reasoning: 124932 / 3232 / 121698 / 1751 / not computed
- Duration: 17.1 s
- Cost: $0.56 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8

## Response (20261029)

I checked each finding against the code. Three are fixed in `a8408e10`, one is partly fixed, and three are declined. The reviewer made no tool calls, so several claims were never checked against the code.

- **F001: declined.** `git log --merges` only returns commits with two or more parents, so the unpack cannot see a non-merge. Slice branches are merged one at a time, so an octopus landing does not arise.
- **F002: declined.** Concurrent runs are unsupported by design (the docstring says so), and the re-read already merges both runs' landings and logs a WARNING when the record changed. The store has no locking for any other record type, so adding one here would be a new mechanism for one record.
- **F003: declined.** `_check_lock_and_venv` has already confirmed both lockfiles are files, so a read error is a filesystem fault, not an environment state. The symlink worry is the wrong way round: `resolve()` follows links, so two roots that are the same directory compare equal, and two that differ go on to the byte comparison, which is what decides.
- **F004: accepted in part.** The preview widths now live in `metrology/preview.py` (`SHA_PREVIEW_CHARS`, `COMPACT_PREVIEW_CHARS`, `abbrev`). Six files used them, including the report renderer's own copy. In the CLI support module, `commit_exists` and `first_parent_history` now share one git-failure exit. Declined for `resolve_commit` and `_archive`: they raise `SnapshotExportError` with different messages, which is not the same handling.
- **F005: accepted.** `build_slice_report` reads audit runs and the baseline report once, and passes them to each landing. A slice with several landings no longer rescans the store per landing.
- **F006: declined.** `compare_snapshots` is 45 lines, under the 50-line guide. `metrology_quality.py` is 187 lines. The rendering helpers in it are for `slice-ranges` alone; moving them next to the report renderer would split one command's output across two modules.
- **F007: accepted.** `slice-ranges --json` now builds Pydantic models (the output shape is unchanged), as the `report` commands do. `take_commit_for` is private. The heading's "exceptions swallowed" has nothing behind it: no exception is caught in this path.
- **F008:** note, no action.
