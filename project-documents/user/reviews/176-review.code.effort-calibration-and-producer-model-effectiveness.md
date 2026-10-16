---
docType: review
layer: project
reviewType: code
slice: effort-calibration-and-producer-model-effectiveness
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/176-slice.effort-calibration-and-producer-model-effectiveness.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261015
dateUpdated: 20261015
reviewedSha: 9f798397488e3f6b8a1274711c7705572e026287
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 0
diffTruncated: false
turns: 1
promptTokens: 116862
cachedTokens: 3232
cacheWriteTokens: 113628
completionTokens: 4633
durationSeconds: 37.0
costUsd: 0.510902
costBasis: provider
squadronVersion: 0.22.0
findings:
  - id: F001
    severity: concern
    category: design
    summary: "Comparison values scattered as bare strings in the effort table"
    location: "src/squadron/cli/stats_effort_views.py#_format_value"
  - id: F002
    severity: concern
    category: performance
    summary: "`_records(unit)` is recomputed several times per unit, and its warnings repeat"
    location: "src/squadron/stats/producer_report.py#_row"
  - id: F003
    severity: concern
    category: error-handling
    summary: "Missing or unparseable slice-design frontmatter silently becomes \"not complete\""
    location: "src/squadron/stats/planning_docs.py#slice_status"
  - id: F004
    severity: concern
    category: maintainability
    summary: "Hard-coded cutoff timestamp with no configuration or provenance check"
    location: "src/squadron/stats/review_rounds.py:COMMIT_EACH_ITERATION_SINCE"
  - id: F005
    severity: concern
    category: design
    summary: "CLI constructs `StateManager` and git runner directly, so tests must monkeypatch internals"
    location: "src/squadron/cli/commands/stats.py#stats_slice"
  - id: F006
    severity: note
    category: style
    summary: "Fragile introspection and positional construction"
    location: "src/squadron/stats/producer_units.py#extract_units"
  - id: F007
    severity: note
    category: testing
    summary: "Test type-checking escapes"
    location: "tests/cli/test_stats_producers.py"
  - id: F008
    severity: note
    category: dry
    summary: "Duplicated slice-match predicate"
    location: "src/squadron/stats/usage_report.py#runs_usage_report"
  - id: F009
    severity: pass
    category: testing
    summary: "Test coverage and failure observability"
    location: "tests/stats"
---

# Review: code — slice 176

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Comparison values scattered as bare strings in the effort table

`_LEVEL_MEASURES` pairs each `Measure` with a bare `"span"`, `"count"` or `"usd"`, and `_format_value` and `_stat_cell` branch on those literals. The project rule is to define a comparison value once (enum or constant) and reference that definition everywhere. A typo in either place would silently fall through to the `case _:` count format. Make the kind a `StrEnum`, or give `Measure` a formatter attribute so the table needs no second lookup.

### [CONCERN] `_records(unit)` is recomputed several times per unit, and its warnings repeat

`_row` calls `_records(unit)` once for the records and again for the action count. `_unpriced` and `producer_report` then call it again, so each unit is walked about three times. `_records` goes through `action_usage_row`, which logs a WARNING for each malformed usage record. A single bad record is therefore logged repeatedly, which makes the footer and log counts misleading. Compute `(records, llm_actions)` once per unit and reuse it.

### [CONCERN] Missing or unparseable slice-design frontmatter silently becomes "not complete"

`read_frontmatter(designs[0]) or {}` turns a design with no frontmatter, or a malformed one, into `status == ""`, so the slice is dropped from the `sq stats slices` rollup with no signal. This conflicts with the "no silent fallback" rule and the Failure-Mode Enumeration rule. Log a WARNING, or count these designs in a footer as the other exclusions are. The function also reads each design twice during a rollup, once for completeness and once for `--since`.

### [CONCERN] Hard-coded cutoff timestamp with no configuration or provenance check

A literal datetime decides whether a review's round count is flagged as a lower bound. It is documented and the tests patch it, so it is a reasonable choice. It is still a magic default that is correct only for this repository's history. Derive it from git (the commit that introduced the 941 behaviour), or at least tie it to a named config location.

### [CONCERN] CLI constructs `StateManager` and git runner directly, so tests must monkeypatch internals

Every command calls `StateManager()` itself, and the CLI tests patch `squadron.cli.commands.stats.StateManager`. Under the DIP rule, needing to monkeypatch internals is a sign the dependency is inverted. A small provider function (or Typer context object) that supplies the `StateManager` would remove the patching. `squadron.stats` modules also import `squadron.pipeline.executor` only for `ExecutionStatus`. That pulls a very large module into the reporting layer.

### [NOTE] Fragile introspection and positional construction

`{name: 0 for name in ExcludedCounts.__dataclass_fields__}` followed by `ExcludedCounts(**counts)` relies on a dunder attribute and string-keyed counters (`counts["each_steps"]`). The compiler or pyright cannot check those keys. `effort_rollup.slices_effort_report` also builds the empty `SlicesEffortReport` with eight positional arguments. Use `dataclasses.fields` or a mutable counter dataclass, and keyword arguments for the empty report.

### [NOTE] Test type-checking escapes

Tests rely on many `# type: ignore[...]` comments and one `# noqa: ANN202` (`_row` in `tests/stats/test_producer_report.py`). The Python rules require zero errors under strict pyright, including tests. Typed accessors such as `cast` or a small TypedDict for the JSON payloads would remove most of the ignores.

### [NOTE] Duplicated slice-match predicate

`str(state.params.get("slice")) == str(index)` appears in both `runs_usage_report` and `slice_spend`. Extract a shared helper so the two reports always agree on what "this slice's run" means.

### [PASS] Test coverage and failure observability

The slice adds tests for git history parsing, review rounds, attribution, planning docs, producers, rollups, state round-trip and the CLI commands. The planning-doc parser is tested against verbatim copies of real task files. Git failures, unreadable review rounds and unreadable run files each surface as a WARNING or a footer count, and each has a test asserting that signal. Older files without the new loop-round fields load with defaults, and a test covers that.

### Run Digest

- Response length: 4938 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 116862 / 3232 / 113628 / 4633 / not computed
- Duration: 37.0 s
- Cost: $0.51 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9

## Response (20261015)

- **F001 — accepted.** `_LEVEL_MEASURES` pairs each measure with its formatter function, so there are no kind strings left to match.
- **F002 — accepted.** Each unit's usage is read once into `_UnitUsage` and reused by the row, the action count and the unpriced count, so a malformed record warns once.
- **F003 — accepted.** A design with no readable frontmatter logs a WARNING naming the file. `PlannedSlice` now carries `date_created`, so the rollup reads each design once. New test in `test_planning_docs.py`.
- **F004 — no change.** The cutoff marks when squadron itself started committing every review iteration (slice 941), so it is a fact about the tool, not this repository, and applies to any project's history. It is one named constant with its meaning documented beside it.
- **F005 — no change.** Every CLI command in `cli/commands/` constructs `StateManager()` at the process boundary and its tests patch it the same way; changing that is a CLI-wide refactor, not this slice's. `ExecutionStatus` is defined in `pipeline.executor`; moving it is out of scope.
- **F006 — accepted.** `ExcludedCounts` is a mutable dataclass incremented by attribute, and the empty `SlicesEffortReport` uses keyword arguments. The duplicate `"paused"` literal now uses `ExecutionStatus.PAUSED`.
- **F007 — accepted.** The CLI tests' `_json` helpers return `Any`, removing their ignores, and `_row` has a return type. Two ignores remain on `to_json_dict()` and `pytest.approx` comparisons, where the ignore is the honest type.
- **F008 — accepted.** `run_slice()` in `usage_report` is the single reading of `params["slice"]`, used by the runs report, slice spend and producer units.
