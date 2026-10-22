---
docType: slice-design
slice: snapshot-record-and-first-adapters-keystone
project: squadron
parent: ../architecture/400-slices.code-quality-measurement.md
dependencies:
- 100
- 320
interfaces:
- 401
- 403
- 404
dateCreated: 20261022
dateUpdated: 20261022
status: not_started
turns: 85
promptTokens: 5690269
cachedTokens: 5541026
cacheWriteTokens: 149139
completionTokens: 57823
durationSeconds: 588.1
costUsd: 3.458543
usageRounds: 3
pricedRounds: 3
revision_number: 2
---

# Slice Design: Snapshot Record and First Adapters (keystone)

## Overview

Nothing deterministic about squadron's code is measured today. Ruff and pyright run in CI as pass/fail gates, their counts go nowhere, and the project's own size rules (~300-line files, ~50-line functions) are checked by nothing.

This slice adds `sq metrology snapshot`. It measures a clean HEAD, read-only, and writes one `code_snapshot` record per commit to 320's metrology store. The record holds file length, function length, lint counts and type-error counts for every language that has an adapter. Every measurement carries its full identity: metric, language, tool, tool version, and the rule set and environment where they apply. A metric that can't be measured is recorded as absent with a reason, never as zero.

There are two adapters. Python measures all four metrics. TypeScript measures length and lint only, which proves the adapter contract isn't Python-shaped before 401 builds on it.

## Value

- **Architectural enablement.** 401 extends the metric enum and both adapters. 403 diffs snapshots at slice boundaries. 404 takes a snapshot as half of the adoption baseline. All three read the record shape, metric identity and adapter contract fixed here.
- **Developer value.** Squadron's file and function limits are checked for the first time, and lint and type counts become numbers you can compare between commits instead of a pass/fail.
- **Brownfield reach.** The TypeScript adapter measures context-forge, the first non-Python project, using its own ESLint config.

## Technical Scope

**Included**
- The `code_snapshot` record type: a sibling payload on `MetrologyRecord`, with store write and read methods.
- Closed enums: `SnapshotMetric`, `SourceLanguage`, `AbsenceReason`.
- Identity models for tool, rule set and environment, plus the cross-field validation that enforces them.
- The `LanguageAdapter` protocol, an adapter registry, and an injectable `ToolRunner`.
- File-set resolution from `git ls-files`, with one effective exclusion set applied through git pathspecs.
- Project-declared length limits and exclusions, read from config.
- Python adapter: file and function length from stdlib `ast`, lint from ruff, type errors from pyright (only when the project's uv environment is resolved and in sync with `uv.lock`).
- TypeScript adapter: file and function length from tree-sitter, lint from the project's own ESLint. Type errors are recorded as absent (`metric_unsupported`).
- Preflight: must be a git repo with a HEAD and a clean tree. Integrity check: the repo must be unchanged after measuring.
- `sq metrology snapshot [--cwd PATH] [--json]`.
- Squadron's own `.squadron.toml` values: limits 300/50 and the vendored exclusions.

**Excluded**
- Measuring a commit other than HEAD, including `git archive` export (403).
- Complexity, duplication and coverage (401).
- Reports, diffs and slice ranges (403). The baseline command (404).
- Installing dependencies, running tests, or a fixed reference rule set (Future Work in the slice plan).
- An MCP or slash-command surface. Metrology is CLI-only today (`src/squadron/server` exposes none of it), so there's no parity surface to update.
- JavaScript, shell and the other detected languages. They're recorded as present with `no_adapter`.

## Dependencies

### Prerequisites
- **320 (complete):** `MetrologyStore`, the `MetrologyRecord` envelope, `ProjectId` and `derive_project_id`, and the `MetrologyError` hierarchy.
- **100 (complete):** Typer CLI registration under `metrology_app`.
- **New runtime dependencies:** `tree-sitter` and `tree-sitter-typescript`, which ship prebuilt wheels. Checked on 20261022: tree-sitter 0.26.0 with tree-sitter-typescript 0.23.2 parses TypeScript in-process with no Node.
- **Tools at measurement time, resolved from the measured project and never installed:** `ruff`, `pyright`, `uv` for Python; `node_modules/.bin/eslint` for TypeScript. A missing tool means that metric is absent with `tool_missing`. It doesn't fail the snapshot.

### Interfaces Required
- `squadron.review.git_utils.run_git` (bounded timeout, UTF-8 pinned). It's reused for every git call, with no new git helper.
- `squadron.config.manager.get_config` and `CONFIG_KEYS` for the new keys.
- `derive_project_id(cwd)`. Its `MetrologyIdentityError` propagates unchanged, with its own fix text.

## Architecture

### Component Structure

New code lives in `src/squadron/metrology/`. The record models sit in a sibling module, the same way `replay_models.py` does, so the envelope can import them without a cycle.

| Module | Responsibility |
|---|---|
| `snapshot_models.py` | Enums, identity models, `Measurement`, `LanguageSnapshot`, `CodeSnapshot`, validators |
| `snapshot/contract.py` | `LanguageAdapter` protocol, `AdapterContext`, `ToolRunner` protocol and `ToolResult`, the `SourceLanguage` → extensions map and the `AdapterRegistry` type (a mapping from language to adapter, holding no adapters itself) |
| `snapshot/registry.py` | `default_registry()`: builds the registry holding the Python and TypeScript adapters. The only non-test module that imports concrete adapters |
| `snapshot/files.py` | Exclusion set and file-set resolution (git pathspecs), grouping files by language. `resolve_files(repo_root, exclusions)` is public so 404's scope report can run without a snapshot |
| `snapshot/preflight.py` | Repo, HEAD, clean tree, config validation, and the post-measurement integrity check |
| `snapshot/runner.py` | Default subprocess `ToolRunner` (timeout, no shell), tool resolution and version probe |
| `snapshot/lengths.py` | Shared non-blank line counting and the distribution reduction |
| `snapshot/python_adapter.py` | Python adapter: ast, ruff, pyright, uv environment |
| `snapshot/typescript_adapter.py` | TypeScript adapter: tree-sitter, ESLint |
| `snapshot/take.py` | Orchestrator `take_snapshot(repo_root, registry, runner, store) -> CodeSnapshot`. Fills absent measurements and writes the record |
| `cli/commands/metrology_snapshot.py` | `snapshot` command, registered onto `metrology_app` |

`take.py` depends only on the contract module, never on a concrete adapter. It receives the registry and the `ToolRunner` as arguments: the CLI and 404 pass `default_registry()` and the subprocess runner, and tests pass fakes. Adding a language means writing an adapter and adding it in `registry.py`. Adding a metric means adding an enum member and implementing it in the adapters that support it. The orchestrator doesn't change either way.

### Data Flow

```
sq metrology snapshot --cwd P
  └─ preflight(P): git repo? HEAD sha? `git status --porcelain` empty (an untracked .squadron.toml exempt)? limits valid?
       ├─ fail → SnapshotPreflightError (exit 1, nothing written)
       └─ derive_project_id(P)
  └─ exclusions = project patterns ∪ adapters' convention patterns
  └─ files = `git ls-files -z -- . ':(exclude,glob)<p>'…`  → grouped by SourceLanguage
  └─ for each language present:
       adapter = registry.get(lang)
         none → every SnapshotMetric absent(no_adapter)
         else → adapter.measure(ctx, files) → list[Measurement]
                orchestrator adds absent(metric_unsupported) for metrics the adapter doesn't declare
  └─ after = `git status --porcelain` (same check as preflight); non-empty → SnapshotIntegrityError (nothing written)
  └─ CodeSnapshot(...) validated → store.write_snapshot() (deterministic id, overwrite in place, INFO line naming the commit if a record was replaced)
  └─ print summary (or --json)
```

**Failure modes not covered by the tool rules in D7 and D8:**

| Failure | Handling | Signal |
|---|---|---|
| Store write fails (disk full, permissions) | `_write_atomic` already writes a `.tmp` sibling and atomically replaces, so no partial record is published. `MetrologyStoreError` propagates and the CLI exits 1. | ERROR log and the path on stderr |
| Two snapshots of one commit at once | Not supported. `_write_atomic` is unchanged, and running two at once is outside this slice. | None |
| A git call (`ls-files`, or the post-measurement `status`) returns `None` or non-zero | Raises `SnapshotIntegrityError` naming the call. It's never treated as an empty file set or an unchanged tree. Nothing is written. | ERROR log and the message on stderr |
| A tool's `--version` probe hangs, exits non-zero or prints no parseable version | The metric is absent with `tool_failed` ("version probe failed: …"). The tool isn't run, because a count without a version has no identity. | WARNING |
| `ast` or tree-sitter fails on a file (deep nesting gives `RecursionError` or `MemoryError`; an undecodable file gives `UnicodeDecodeError`) | The file goes into `unparsed_files`, and the snapshot continues. | WARNING per file |
| In-process parse is slow | Not time-bounded. Both parsers are linear in file size and only tracked source files reach them. A wall-clock bound would mean moving parsing into a subprocess. | One INFO line per language before its adapter starts, so a stall can be traced to its language |

### State Management

The only state is the store record. Its id is `snapshot-{sha256(project_id.value)[:12]}-{commit_sha[:12]}`. A second snapshot of the same commit replaces the first (see D3). The command holds nothing in memory between runs.

## Technical Decisions

### D1 — Record shape: one coarse record per commit
Status: decided
- One `CodeSnapshot` per (project, commit) holds a `LanguageSnapshot` for every language present. Each one holds exactly one `Measurement` per `SnapshotMetric` member, present or absent. A reader never has to infer a missing metric.
- Values are stored per file, plus a `Distribution` (count, total, min, p50, p90, max) over files, or over functions for function length.
  - File length: `per_file` covers every measured file in the language.
  - Lint and type: `per_file` lists only files with a non-zero count. The measured file set is the file-length key set (for ESLint, less `tool_ignored_files`, see D4).
  - Function length: no `per_file`. It keeps `over_limit` rows (path, qualified name, start line, length) only for functions over the declared limit.
- Rejected: one record per language or per metric. The store reads every file on every query (320), so record count is the cost that matters.

### D2 — Metric identity is enforced by the model, not by convention
Status: decided
- `Measurement` fields: `metric`, `language`, `tool: ToolIdentity` (name, version, `counting`: how the adapter counts), `rule_set: RuleSetIdentity | None` (config source path and content hash), `environment: EnvironmentIdentity | None` (lockfile path, its SHA-256, and the interpreter version), `absent: AbsenceReason | None`, `absent_detail: str | None`, plus the values from D1.
- A model validator rejects any record that breaks these rules. This is fail-fast at the record boundary, so a malformed snapshot can't be written:
  - A present lint or type measurement must have a `rule_set`.
  - A present type measurement must have an `environment`. This is the arch's rule, and ESLint lint carries none in 400. ESLint results also depend on the plugins in `node_modules`, so recording that environment is deferred to #250.
  - An absent measurement carries no values, and `absent_detail` is required.
- In-process counters are tools too: `squadron-python-ast` and `squadron-tree-sitter-ts`. Their version is the squadron version plus the parser version (the Python version, or the tree-sitter and grammar versions). A change to the counting code then shows up as a tool change, never as a quiet shift in the numbers.
- When a tool has no config file, the rule set is `source="tool-defaults"` with `content_hash=None`, and the tool version stands in for it. This is an explicit value, not a missing one.

### D3 — Same commit re-snapshot overwrites in place
Status: decided
- The record id is deterministic per (project, commit), so a re-snapshot replaces the old record. This matches the "one record per commit" criterion, and it means re-measuring a commit after a tool upgrade leaves one consistent record rather than two that contradict each other.
- An overwrite can replace a record taken under different settings, for example from another checkout with other local limits. `write_snapshot` logs an INFO line naming the commit when it replaces a record. The replaced record isn't kept, and no diff is computed. Comparisons between commits stay honest because each record carries its own identity, and 403 compares limits, exclusions and tool identities before it diffs.
- Determinism is checked by comparing `--json` output from two runs, ignoring `measured_at`. The verification walkthrough does this.

### D4 — One effective exclusion set, applied by git, and tool-level include/exclude ignored
Status: decided
- The file set is `git ls-files` at a clean HEAD, which matches the commit exactly. Untracked `node_modules/` and `.venv/` never enter.
- Exclusions are passed as `:(exclude,glob)` pathspecs, so git does the matching and squadron needs no glob library. The effective set is the sorted union of:
  - project patterns from `metrology.snapshot_exclude`
  - each adapter's convention patterns: Python `**/*_pb2.py`, `**/*_pb2_grpc.py`; TypeScript `**/*.d.ts`, `**/node_modules/**`, `**/dist/**`.
- It's recorded once on `CodeSnapshot.exclusions` as a sorted list of patterns.
- Every tool gets the explicit file list, chunked to stay under argv limits. Chunking doesn't change any result: ruff, ESLint and pyright diagnostics are per file. Tool-level `include`/`exclude` settings are therefore not applied. Rule selection, per-file ignores and strictness still are. Ruff and pyright analyze every file they're given.
- ESLint is the exception. A flat config's `ignores` entries still apply to files passed explicitly, so ESLint skips them. The adapter doesn't override that, because `ignores` is part of the project's rule set. Files ESLint skips are dropped from the lint measurement and listed in `tool_ignored_files`, so the lint file set is the length file set minus that list, and the difference is recorded rather than hidden. They never add to the lint count. How ESLint reports a skipped file is taken from output captured from context-forge (a fixture with an ignored file), not assumed.
- Consequence: on squadron, pyright counts `tests/` (its config `include` is `["src"]`). That's deliberate, because every metric covers the same files. It's stated in the adapter's `counting` field.
- Rejected: letting each tool apply its own excludes. That would measure four different file sets under one snapshot.

### D5 — Second language is TypeScript, with tree-sitter for length
Status: decided
- TypeScript because context-forge is the sibling TypeScript project that 440 adopts, and the ai-project-guide ships TypeScript ESLint rules. The adapter covers `.ts`, `.tsx`, `.mts` and `.cts`. JavaScript is a separate `SourceLanguage` member and stays `no_adapter` here.
- Function length comes from tree-sitter, in-process: it's deterministic, needs no Node, and works on a project that has no `node_modules`. Lint comes from `node_modules/.bin/eslint --format json` with the project's own config. It's never fetched with `npx`, which can download and write.
- Rejected:
  - The TypeScript compiler API through a Node script. Length would then depend on a working Node environment.
  - ESLint `max-lines-per-function` with `max: 0` and its messages parsed. That reads lengths out of human-readable text and needs the project's parser plugins to load.

### D6 — Counting definitions
Status: decided
- File length is the number of non-blank physical lines, matching the "excluding whitespace" wording of the project's rule.
- Function length is the number of non-blank lines from the first decorator, or the def line, through the end of the body.
  - Python counts `def` and `async def` at any depth, with names qualified like `__qualname__` (`Cls.method`, `outer.<locals>.inner`). Lambdas are excluded.
  - TypeScript counts function declarations (generators included), methods (constructors and accessors included), function expressions, and arrow functions with block bodies. Expression-bodied arrows are excluded, to match the lambda exclusion. A name comes from the node, or from the enclosing variable declarator or property, or else is `<anonymous>`.
  - A nested function counts on its own, and its lines are also inside the outer function's span.
- A file that fails to parse (Python `SyntaxError` under squadron's interpreter, or a tree-sitter tree with an error root) is listed in the measurement's `unparsed_files`. It still counts for file length, but contributes no functions.

### D7 — Python environment resolution (type counts)
Status: decided
- The environment counts as resolved only when all three of these hold. Otherwise type errors are absent with `environment_unresolved`, and the detail names the failing condition, for example `lockfile type not supported: poetry.lock`.
  1. `uv.lock` exists.
  2. `.venv/` exists.
  3. `uv sync --check --locked --offline` exits 0. Checked on 20261022 on squadron: it reports "Would make no changes" and doesn't touch the venv or the lockfile.
- The check's outcomes: exit 0 means type errors are measured. Exit 1 ("The environment is outdated") is `environment_unresolved` (venv out of sync with `uv.lock`). Anything else follows D8: `uv` not found is `tool_missing`; a timeout, any other exit code (a uv error, with the stderr head) or unparseable output is `tool_failed`. Each non-success is logged at WARNING. Condition 2 is needed because, with no `.venv`, the check exits 0 ("Would create project environment"). Exit codes were checked on 20261022 with uv 0.11.2 against scratch projects.
- The environment identity is `uv.lock` plus its SHA-256. Pyright runs with `--outputjson --pythonpath .venv/bin/python`. Only `severity == "error"` diagnostics count.
- Only uv is supported. Other lockfile types are honestly absent, and adding them is new adapter code, not a contract change.

### D8 — Tool resolution, version and rule-set sources
Status: decided
- Tools are looked up in the project first (`.venv/bin/{ruff,pyright}`, `node_modules/.bin/eslint`), then on `PATH` for ruff and pyright. The version comes from `--version`. A tool that isn't found gives `tool_missing`. A tool that exits non-zero for a reason other than findings, times out, or emits unparseable JSON gives `tool_failed`. Each of these is logged at WARNING with the tool, the command and the stderr head.
- Rule-set sources:
  - ruff: `ruff.toml`, then `.ruff.toml`, then pyproject `[tool.ruff]`.
  - pyright: `pyrightconfig.json`, then pyproject `[tool.pyright]`.
  - ESLint: `eslint.config.{js,mjs,cjs}`. Other config forms are added when a real project needs them. With none present, ESLint isn't run and lint is absent with `tool_failed` ("no eslint.config.{js,mjs,cjs} found").
- A pyproject table is hashed as canonical JSON (sorted keys). This is kept rather than hashing the whole file, because squadron bumps `version` in `pyproject.toml` on every release, and 403 would otherwise flag every release's lint and type counts as a rule-set change. Config files are hashed by content. Configs inherited through `extend` aren't followed; the rule set names the config file actually read.
- Every tool runs read-only: `ruff check --no-cache --exit-zero --output-format json`, pyright with no cache flag, ESLint without `--cache`. All tool commands go through `ToolRunner`. The timeout `metrology.snapshot_tool_timeout_s` applies to each subprocess call: every version probe, the uv check, and every chunk. There's no separate bound on total runtime; it's at most the number of calls times the timeout, and the per-language INFO lines show where the time goes.

### D9 — Read-only: prevented by construction, tracked and untracked checked
Status: decided
- Prevention is the guarantee. Every tool runs with its read-only flags (D8), and squadron never imports or executes the measured project's Python, so no `__pycache__` is created.
- The check reruns the preflight's `git status --porcelain` after measuring, applying the same `.squadron.toml` exemption. Any output raises `SnapshotIntegrityError` naming the paths, and nothing is written. This catches modified tracked files and new untracked files. Ignored paths (tool caches, `.venv/`, `node_modules/`) aren't checked, and rely on prevention alone.
- Dirty-tree refusal covers any `--porcelain` output, untracked files included. An untracked tool config such as `ruff.toml` would change the counts without the commit showing it. The single exemption is an untracked `.squadron.toml` at the repo root (D10). Squadron reads it, no measured tool does, and its values are recorded on the snapshot. This is a deliberate departure from the arch's "a dirty tree is refused" wording: two checkouts of one commit can produce different records when their `.squadron.toml` values differ. Each record carries those values, and D3's INFO line records that one replaced the other. This is otherwise stricter than the audit's preflight, which exempts its own output file: the snapshot writes nothing into the repo, so it needs no such exemption.

### D10 — Config keys
Status: decided
- New keys in `CONFIG_KEYS`, all project-level via `.squadron.toml`:
  - `metrology.max_file_lines` (int, default None)
  - `metrology.max_function_lines` (int, default None)
  - `metrology.snapshot_exclude` (str, default None)
  - `metrology.snapshot_tool_timeout_s` (int, default 600). The default is defined only in `CONFIG_KEYS` and read with `get_positive_int_config`, which raises on a non-positive value. No adapter or runner repeats it. `ToolRunner.run` takes `timeout_s` as a required argument with no default, so a caller can't omit it.
- Resolution: every key is read with `get_config(key, cwd=<measured repo root>)`, so the project layer is the measured repo's own `.squadron.toml`, resolved from `--cwd` and never from the process cwd. The user layer (`~/.config/squadron/config.toml`) still applies underneath.
- Declaring limits doesn't break preflight or edit the project. An untracked `.squadron.toml` is exempt from the dirty-tree check (D9), so a brownfield project gets limits and exclusions without committing anything.
- `snapshot_exclude` is a comma-separated string, which is what `sq config set` writes. Whitespace around each pattern is stripped, and empty entries are skipped.
- A limit of zero or less, or one that isn't a number, raises `SnapshotPreflightError`. Each unset limit is recorded as `None` on `CodeSnapshot.limits`, and `limits_declared=False` when both are unset, so the record itself says no limits were set. `over_limit` stays empty, and the distributions still appear in full.

### Technology Choices
- Stdlib `ast` for Python length: no dependency, exact spans through `end_lineno`.
- `tree-sitter` and `tree-sitter-typescript` for TypeScript length (D5).
- ruff, pyright, ESLint and uv are invoked as external CLIs and never imported, so their versions are recorded and not pinned by squadron.

### Patterns and Conventions
- Errors: `SnapshotPreflightError` and `SnapshotIntegrityError` subclass `MetrologyError`, and each message names the fix. A metric-level failure is data (`absent`), not an exception. Only a failure that makes the whole record untrustworthy raises.
- Enums own every compared value: metric, language and absence reason. Tool names and rule-set source names are constants in the adapter module that owns them.
- Store methods follow the existing pattern: `write_snapshot(snapshot) -> record_id`, `list_snapshots(project_id, commit_sha=None)` newest first, and the shared `_iter_records` that tolerates bad records.

## Implementation Details

### API Contracts

**CLI**

```
sq metrology snapshot [--cwd PATH] [--json]
```

- Exit 0 writes the record and prints a line per language with each metric's summary or `absent: <reason> (<detail>)`, then the limits line, the exclusion count and the record path.
- `--json` prints the `CodeSnapshot` as JSON instead.
- Exit 1 on `SnapshotPreflightError`, `SnapshotIntegrityError` or `MetrologyIdentityError`, with the message on stderr and nothing written.

**Adapter contract** (`snapshot/contract.py`)

```python
class LanguageAdapter(Protocol):
    language: SourceLanguage
    metrics: frozenset[SnapshotMetric]          # what this adapter measures
    convention_exclusions: tuple[str, ...]      # glob pathspecs
    def measure(self, ctx: AdapterContext, files: Sequence[str]) -> list[Measurement]: ...

@dataclass(frozen=True)
class AdapterContext:
    repo_root: Path
    limits: LengthLimits
    runner: ToolRunner
    tool_timeout_s: int
```

The contract has four rules:
- An adapter returns exactly one `Measurement` per member of its `metrics` set.
- The orchestrator raises if an adapter returns a measurement for a metric it didn't declare, or omits one it did.
- `files` are repo-relative POSIX paths.
- An adapter never writes inside `repo_root`.

### Database / Storage Schema

`MetrologyRecord` gains `code_snapshot: CodeSnapshot | None = None` and `RECORD_TYPE_CODE_SNAPSHOT = "code_snapshot"`. `schema_version` stays 1, and there's no migration: existing records have no such field and still validate.

```
CodeSnapshot
  snapshot_id, project_id: ProjectId, commit_sha, measured_at, squadron_version
  limits: LengthLimits(max_file_lines, max_function_lines, limits_declared)
  exclusions: list[str]   (sorted glob pathspecs)
  languages: list[LanguageSnapshot(language, file_count, adapter: str|None, measurements)]
Measurement   (see D1, D2)
  metric, language, tool, rule_set?, environment?, absent?, absent_detail?
  per_file: dict[str,int], distribution?, limit?,
  over_limit: list[FunctionOverLimit], unparsed_files: list[str],
  tool_ignored_files: list[str]
```

Dicts and lists are sorted before serialization so the JSON is byte-stable across runs.

## Integration Points

### Provides to Other Slices
- **401:** `SnapshotMetric` (adds complexity, duplication, coverage), `AbsenceReason` (adds reasons such as tests failed or coverage not configured), and the `LanguageAdapter` contract. Both adapters gain metrics without any envelope or contract change.
- **403:** `store.list_snapshots` and the full identity per measurement for comparability checks. In 400, `take_snapshot(repo_root, registry, runner, store)` measures a clean HEAD only. 403 extends it for exported commits, including the rule that type counts at an export need its lockfile to match the current environment. Before diffing two snapshots, 403 must compare `limits` and `exclusions` as well as tool identities, because a gitignored `.squadron.toml` makes limits checkout-local (D9).
- **404:** `take_snapshot` with `default_registry()`, and `files.resolve_files`, which gives the post-exclusion file set for the scope report without running any tool.

### Consumes from Other Slices
- **320's store, envelope and `ProjectId`.** Identity failure propagates unchanged.
- **git_utils `run_git`.** A `None` (git couldn't answer) is a preflight failure, never treated as a clean tree.

## Success Criteria

### Functional Requirements
1. On a clean HEAD, `sq metrology snapshot` writes exactly one `code_snapshot` record keyed on `ProjectId` and commit SHA. A second run on the same commit leaves one record.
2. A dirty tree, including untracked files, is refused with `SnapshotPreflightError` naming the offending paths, and no record is written.
3. Every present measurement carries metric, language, tool name, tool version and counting definition. Present lint and type measurements also carry a rule set, and present type measurements also carry an environment with the lockfile hash. The model rejects a record that violates any of this.
4. Two snapshots of the same commit with the same tools and environment produce identical JSON apart from `measured_at`.
5. With limits declared, file length reports the files over the limit and function length has an `over_limit` row for each function over it, and only those. With no limits declared, `limits_declared` is false, `over_limit` is empty, and the distributions are present.
6. Each unmeasurable metric is absent with a reason and detail:
   - `no_adapter` for a detected language with no adapter (shell on squadron)
   - `metric_unsupported` for TypeScript type errors
   - `tool_missing` when the tool isn't found
   - `tool_failed` on a timeout or bad output
   - `environment_unresolved` when there's no `uv.lock` or `.venv`, or the venv is out of sync
7. `CodeSnapshot.exclusions` records one effective set. On squadron it includes `commands/analysis/**`, and no file under it appears in any measurement. Files ESLint skips through its own `ignores` are listed in `tool_ignored_files` and add nothing to the lint count.
8. `git status --porcelain` is still empty after measuring. A modified tracked file or a new untracked file causes `SnapshotIntegrityError`, and nothing is recorded. Ignored paths aren't checked (D9).
9. An untracked `.squadron.toml` doesn't fail preflight. Re-snapshotting a commit logs an INFO line saying the earlier record was replaced.
10. Every existing metrology record type still loads, and `sq metrology list`, `report baseline` and `audit delta` behave as before.

### Technical Requirements
- ruff format, ruff check and pyright (zero errors) are clean, and the full test suite passes.
- New modules stay at ~300 lines or less.
- Parser tests use real tool output, per the project's parsing rule: ruff and pyright JSON captured from squadron, and ESLint 10 JSON captured from context-forge (including a run where a file is skipped by `ignores`), stored as fixtures.
- Each failure mode has a test asserting both its log signal and its outcome:
  - for a tool or version probe: timeout, missing tool, bad JSON, non-zero exit
  - for a parse: `SyntaxError`, `RecursionError`, an undecodable file (`unparsed_files`)
  - for a git call: `None` or non-zero (`SnapshotIntegrityError`)
- Tests build throwaway git repos under `tmp_path` and use a store dir under `tmp_path`. They never use the user store.

### Integration Requirements
- 401 can add a metric enum member with no change to `MetrologyRecord`, `CodeSnapshot` or `LanguageAdapter`. A test asserts that every `SnapshotMetric` member appears for every language, so a new member automatically shows up as `metric_unsupported` in adapters that haven't implemented it yet.
- `docs/COMMANDS.md` documents `sq metrology snapshot`, and CHANGELOG has a user-facing bullet.

### Verification Walkthrough

None of these commands exist yet. Expected outputs describe structure, not exact numbers.

1. **Squadron config.** Add to squadron's `.squadron.toml` (gitignored, so local to this checkout):
   ```toml
   "metrology.max_file_lines" = 300
   "metrology.max_function_lines" = 50
   "metrology.snapshot_exclude" = "commands/analysis/**, project-documents/ai-project-guide/**"
   ```
2. **Snapshot squadron.** With a clean tree, run `sq metrology snapshot`. Expect:
   - a `python` section with file length, function length (N over 50), lint count (ruff with its version and `pyproject.toml [tool.ruff]`) and type errors (pyright with `uv.lock` and its hash)
   - a `shell` section, every metric `absent: no_adapter`
   - `limits: file 300, function 50`
   - the exclusion count, and the record path under `~/.config/squadron/metrology/`
3. **Exclusion holds.** Run `sq metrology snapshot --json | jq '[.languages[].measurements[].per_file | keys[]] | map(select(startswith("commands/analysis/")))'`. Expect `[]`.
4. **Determinism.** Run `sq metrology snapshot --json > a.json`, then the same command into `b.json`. Then `diff <(jq 'del(.measured_at)' a.json) <(jq 'del(.measured_at)' b.json)` gives no output, and `ls ~/.config/squadron/metrology/snapshot-*` still shows one file for this commit.
5. **Dirty tree refused.** `touch scratch.txt && sq metrology snapshot` exits 1 naming `scratch.txt`, and no record is written. Then `rm scratch.txt`.
6. **No limits.** Remove the two limit keys and re-run. The output says no limits are declared, `over_limit` is empty in `--json`, and the distributions are still there. Restore the keys.
7. **Environment unresolved.** In a scratch clone of squadron with no `.venv`, `sq metrology snapshot --cwd <clone>` shows type errors as `absent: environment_unresolved (.venv not found)`, while lint and length are still present.
8. **TypeScript.** Run `sq metrology snapshot --cwd ../context-forge`. Expect:
   - a `typescript` section: file and function length from `squadron-tree-sitter-ts`, lint from `eslint 10.x` with `eslint.config.mjs` and its hash, type errors `absent: metric_unsupported`
   - a `javascript` section for the `.mjs` files, every metric `absent: no_adapter`
   - `limits: none declared`
   - `git -C ../context-forge status --porcelain` still empty
9. **Tool missing.** On a scratch TypeScript repo with no `node_modules`, lint shows `absent: tool_missing (node_modules/.bin/eslint not found)` and length is still measured.
10. **Old records load.** `sq metrology list` and `sq metrology report baseline` print as before the slice.

## Risk Assessment

### Technical Risks
- **Contract shape is inherited by every later slice.** A field missing from `Measurement` now becomes a migration later.
- **pyright determinism.** Its results can depend on the interpreter and installed stubs as well as the lockfile.

### Mitigation Strategies
- The pyright environment identity is the lockfile hash plus the `--pythonpath` interpreter version (in `EnvironmentIdentity.interpreter`). Walkthrough step 4 checks run-to-run stability on squadron.

## Implementation Notes

### Development Approach
1. Models, enums and validators, the envelope field, and the store methods. Back-compat load test.
2. Config keys and preflight: dirty tree, limits, identity. Integrity check.
3. File-set resolution with pathspec exclusions and grouping by language. The registry type goes in the contract.
4. Contract, `ToolRunner`, and the orchestrator with absent-filling.
5. Python adapter: ast length, then ruff, then uv environment check and pyright.
6. TypeScript adapter: tree-sitter length, then ESLint.
7. `default_registry()`, the CLI command, docs and CHANGELOG, and the squadron `.squadron.toml` values. Then the walkthrough.

### Special Considerations
- **Squadron's limits live in a gitignored file.** `.squadron.toml` is gitignored in squadron, so limits and exclusions belong to the checkout. Because the record carries both, a snapshot taken under different settings is identifiable rather than silently comparable. Overwriting one is logged (D3).
- **Security.** Tools run with argv lists, never a shell. Only binaries inside the measured project or on `PATH` run: no `npx`, no install, no network (`uv --offline`). Snapshotting an untrusted repo still runs that repo's `node_modules/.bin/eslint` and its JavaScript config, which executes the repo's code. The command's help text states this.
- **Performance.** Pyright on a large repo is the slowest step, and it's bounded by `metrology.snapshot_tool_timeout_s`. A timeout gives `tool_failed`, never a partial count.
