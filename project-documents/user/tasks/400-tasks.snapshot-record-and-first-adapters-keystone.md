---
docType: tasks
slice: snapshot-record-and-first-adapters-keystone
project: squadron
lld: user/slices/400-slice.snapshot-record-and-first-adapters-keystone.md
dependencies:
- 100
- 320
projectState: 0.23.8 released; slice 400 design complete (revision 2, review concerns
  resolved)
dateCreated: 20261022
dateUpdated: 20261022
status: in_progress
turns: 30
promptTokens: 2121124
cachedTokens: 2020672
cacheWriteTokens: 100398
completionTokens: 25779
durationSeconds: 232.1
costUsd: 1.723422
usageRounds: 3
pricedRounds: 3
revision_number: 2
---

# Tasks: Snapshot Record and First Adapters (keystone)

## Context Summary
- Slice 400 adds `sq metrology snapshot`: it measures a clean HEAD read-only and writes one `code_snapshot` record per (project, commit) to 320's metrology store. Metrics: file length, function length, lint count, type-error count.
- Two adapters: Python (all four metrics) and TypeScript (length and lint; type errors absent `metric_unsupported`).
- All decisions and contracts live in the slice design (the `lld` above). Each task cites its decision (D1–D10) or section. Read it before starting the task. The module table is under Architecture → Component Structure.
- Prerequisites, all on `main`: 320's `MetrologyStore`, `MetrologyRecord`, `ProjectId`/`derive_project_id`, `MetrologyError` hierarchy; 100's `metrology_app`; `squadron.review.git_utils.run_git`; `squadron.config.manager.get_config` / `get_positive_int_config`.
- Branch: `400-slice.snapshot-record-and-first-adapters-keystone`, forked from the target (`cf config get git.integration_branch`, or `main` if empty).
- Every commit: `.venv/bin/ruff format`, `.venv/bin/ruff check`, `.venv/bin/pyright` (zero errors project-wide), and the tests for the touched area. Don't use `pytest -n`.
- Tests build throwaway git repos and stores under `tmp_path`, never the user store. New modules stay at ~300 lines or less.
- Live tool runs (ruff, pyright, uv, ESLint against squadron and `../context-forge`) are pre-authorized.
- Next slices: 401 (more metrics), 403 (diffs), 404 (adoption baseline). All consume the record shape and adapter contract fixed here.

## Task 1: Branch and parser dependencies — Effort 1
- [x] Create the slice branch from the target
- [x] Add `tree-sitter` and `tree-sitter-typescript` to `[project] dependencies` in `pyproject.toml` with lower bounds at the checked versions (0.26.0 and 0.23.2), then `uv sync`
- [x] Success: `.venv/bin/python -c` parsing a one-line TypeScript function with the `typescript` and `tsx` languages succeeds; `uv.lock` updated
- [x] Commit: `chore: add tree-sitter and tree-sitter-typescript dependencies`

## Task 2: Snapshot test scaffolding — Effort 2
- [x] Create `tests/metrology/snapshot/` (with `__init__.py` and `conftest.py`)
- [x] Fixture `snapshot_git_repo`: a factory that builds a git repo under `tmp_path` from a `{relative_path: content}` mapping, commits it, and returns the path. Model it on `_init_repo` in `tests/metrology/conftest.py` and `temp_git_repo` in `tests/conftest.py` (local user name/email, no reliance on the developer's git config or default branch)
- [x] Fixture `snapshot_store`: a `MetrologyStore` rooted under `tmp_path`
- [x] Success: a smoke test uses both fixtures and passes

## Task 3: Snapshot enums and identity models (D2) — Effort 2
- [x] Create `src/squadron/metrology/snapshot_models.py`
- [x] Enums (`StrEnum`), each the only definition of its values:
  - [x] `SnapshotMetric`: file length, function length, lint count, type errors
  - [x] `SourceLanguage`: `python`, `typescript`, `javascript`, `shell` (javascript and shell are the `no_adapter` languages in walkthrough steps 2 and 8)
  - [x] `AbsenceReason`: `no_adapter`, `metric_unsupported`, `tool_missing`, `tool_failed`, `environment_unresolved`
- [x] Pydantic models: `ToolIdentity` (name, version, counting), `RuleSetIdentity` (source, content_hash: `str | None`), `EnvironmentIdentity` (lockfile path, lockfile SHA-256, interpreter version), `LengthLimits` (max_file_lines, max_function_lines, limits_declared), `Distribution` (count, total, min, p50, p90, max), `FunctionOverLimit` (path, qualified name, start line, length)
- [x] Define the `tool-defaults` rule-set source as a module constant (D2 last bullet)
- [x] Success: module imports cleanly; pyright clean

## Task 4: Measurement, LanguageSnapshot, CodeSnapshot and validators (D1, D2) — Effort 3
- [x] In `snapshot_models.py`, add `Measurement` with the fields listed under Database / Storage Schema
- [x] Model validator on `Measurement` enforcing D2:
  - [x] present lint or type measurement requires `rule_set`
  - [x] present type measurement requires `environment`
  - [x] absent measurement requires `absent_detail` and carries no values (empty `per_file`, `over_limit`, `unparsed_files`, `tool_ignored_files`; no `distribution`, `limit`)
  - [x] present measurement requires `tool`
- [x] Add `LanguageSnapshot` (language, file_count, adapter: `str | None`, measurements) and `CodeSnapshot` (fields per Database / Storage Schema)
- [x] `LanguageSnapshot` validator: exactly one `Measurement` per `SnapshotMetric` member, each with matching `language`
- [x] Deterministic serialization: `per_file` keys, `over_limit`, `unparsed_files`, `tool_ignored_files`, `exclusions`, `languages` and `measurements` are sorted before serialization (D1, Database / Storage Schema)
- [x] Success: file stays under ~300 lines; if it would exceed, move the identity models into a second sibling module and note it in the module table of the slice design

## Task 5: Model tests — Effort 2
- [x] `tests/metrology/snapshot/test_snapshot_models.py`:
  - [x] each D2 validator rule rejects a violating `Measurement` and accepts a valid one
  - [x] `tool-defaults` rule set with `content_hash=None` is accepted
  - [x] `LanguageSnapshot` rejects a missing metric, a duplicate metric, and a measurement whose language doesn't match
  - [x] two `CodeSnapshot`s built from the same data in different insertion orders serialize to identical JSON
  - [x] round trip `model_dump_json` → `model_validate_json` is lossless
- [x] Success: tests pass; ruff and pyright clean
- [x] Commit: `feat(metrology): add code snapshot models and validators`

## Task 6: Envelope field and store methods (Database / Storage Schema, D3) — Effort 2
- [x] In `src/squadron/metrology/models.py`: add `RECORD_TYPE_CODE_SNAPSHOT = "code_snapshot"` beside the other record-type constants and `code_snapshot: CodeSnapshot | None = None` on `MetrologyRecord`. `schema_version` stays 1
- [x] In `src/squadron/metrology/store.py`:
  - [x] `write_snapshot(snapshot) -> record_id`. Id is `snapshot-{sha256(project_id.value)[:12]}-{commit_sha[:12]}` (State Management), built in one helper. Uses `_write_atomic`
  - [x] When a record with that id already exists, log INFO naming the commit and that the earlier record was replaced (D3)
  - [x] `list_snapshots(project_id, commit_sha=None)`, newest first, via `_iter_records`
- [x] Success: existing store tests still pass

## Task 7: Store and back-compat tests — Effort 2
- [x] `tests/metrology/snapshot/test_snapshot_store.py`, using `snapshot_store`:
  - [x] write then list returns the snapshot; filter by `commit_sha` works; order is newest first
  - [x] a second write for the same (project, commit) leaves one record and logs the INFO line (`caplog`)
  - [x] different commits produce different ids
  - [x] a store holding one record of every existing record type plus a snapshot loads all of them unchanged (Success Criterion 10)
- [x] Success: these tests and all of `tests/metrology/` pass; ruff and pyright clean
- [x] Commit: `feat(metrology): add code_snapshot envelope field and store methods`

## Task 8: Config keys (D10) — Effort 1
- [x] Add to `CONFIG_KEYS` in `src/squadron/config/keys.py`, following the existing `metrology.*` entries: `metrology.max_file_lines` (int, None), `metrology.max_function_lines` (int, None), `metrology.snapshot_exclude` (str, None), `metrology.snapshot_tool_timeout_s` (int, 600)
- [x] The 600 default appears only in `CONFIG_KEYS`
- [x] Success: `sq config set metrology.max_file_lines 300` in a scratch repo writes `.squadron.toml`; existing config tests pass

## Task 9: Snapshot errors and preflight (D9, D10) — Effort 3
- [x] In `src/squadron/metrology/errors.py`: `SnapshotPreflightError` and `SnapshotIntegrityError`, subclassing `MetrologyError`. Every raise site's message names the fix
- [x] Create `src/squadron/metrology/snapshot/__init__.py` and `snapshot/preflight.py`. All git calls go through `run_git`
- [x] `preflight(repo_root)` returns the HEAD SHA, `LengthLimits`, project exclusion patterns and tool timeout:
  - [x] not a git repo, or no HEAD → `SnapshotPreflightError`
  - [x] `git status --porcelain` output non-empty → `SnapshotPreflightError` naming the paths. The one exemption is an untracked `.squadron.toml` at the repo root (D9)
  - [x] `run_git` returning `None` or non-zero → log ERROR naming the call, then raise; never a clean tree (Consumes from Other Slices)
  - [x] limits read with `get_config(key, cwd=str(repo_root))`; a non-integer or ≤0 limit → `SnapshotPreflightError`; unset limits recorded as `None`; `limits_declared` false when both unset
  - [x] `snapshot_exclude` split on commas, whitespace stripped, empty entries skipped
  - [x] timeout read with `get_positive_int_config`
- [x] `check_integrity(repo_root)`: reruns the same porcelain check (shared helper, not a copy) and raises `SnapshotIntegrityError` naming the paths, or, after logging ERROR, naming the git call when it returns `None` / non-zero
- [x] Success: `derive_project_id` is not wrapped; its `MetrologyIdentityError` propagates unchanged

## Task 10: Config and preflight tests — Effort 2
- [x] `tests/metrology/snapshot/test_preflight.py`, using `snapshot_git_repo`:
  - [x] clean repo passes and returns the HEAD SHA
  - [x] non-repo dir, and a repo with no commits, each raise `SnapshotPreflightError`
  - [x] modified tracked file and untracked file each raise, naming the path
  - [x] untracked `.squadron.toml` passes; an untracked `ruff.toml` fails
  - [x] limits: valid values recorded; `0`, `-1` and a non-number raise; none set gives `limits_declared=False`
  - [x] `snapshot_exclude` with spaces and an empty entry (`"a/**, ,b/**"`) parses to two patterns
  - [x] config is read from the measured repo's `.squadron.toml`, not the process cwd (run with `monkeypatch.chdir` elsewhere)
  - [x] `check_integrity` raises after a tracked file is modified and after a new untracked file appears; passes on an ignored path
  - [x] `run_git` patched to return `None` raises in both preflight and integrity, and logs ERROR
  - [x] the four new `CONFIG_KEYS` entries have the Task 8 types and defaults
- [x] Success: tests pass; ruff and pyright clean
- [x] Commit: `feat(metrology): add snapshot config keys, preflight and integrity check`

## Task 11: Adapter contract (Implementation Details → Adapter contract) — Effort 2
- [x] Create `snapshot/contract.py` with:
  - [x] `ToolResult` (exit code, stdout, stderr, timed_out) and `ToolRunner` protocol: `run(argv, *, cwd, timeout_s)`, `timeout_s` required with no default (D10)
  - [x] `LanguageAdapter` protocol and frozen `AdapterContext`, as in the design
  - [x] the `SourceLanguage` → file-extension map (TypeScript: `.ts`, `.tsx`, `.mts`, `.cts`; JavaScript includes `.js`, `.mjs`, `.cjs`; shell `.sh`)
  - [x] `AdapterRegistry` type: a mapping from `SourceLanguage` to adapter, holding no adapters
- [x] Add a `FakeToolRunner` to `tests/metrology/snapshot/conftest.py`: returns scripted `ToolResult`s keyed by argv prefix and records the calls
- [x] Success: `contract.py` imports nothing from any adapter module; pyright clean

## Task 12: File-set resolution (D4) — Effort 2
- [x] Create `snapshot/files.py`
- [x] `effective_exclusions(project_patterns, adapters)`: sorted union of project patterns and each adapter's `convention_exclusions`
- [x] `resolve_files(repo_root, exclusions)` (public, for 404): `git ls-files -z -- . ':(exclude,glob)<p>'…` via `run_git`; `None` or non-zero logs ERROR and raises `SnapshotIntegrityError` naming the call
- [x] `group_by_language(files)`: uses the contract's extension map; files with no mapped extension are not grouped
- [x] Success: no glob library imported; git does all matching

## Task 13: File-set tests — Effort 2
- [x] `tests/metrology/snapshot/test_files.py`:
  - [x] untracked files never appear
  - [x] `commands/analysis/**` exclusion removes every file under it, at any depth
  - [x] `**/*.d.ts` and `**/node_modules/**` conventions remove tracked matches
  - [x] effective set is sorted and de-duplicated
  - [x] grouping maps `.ts`/`.tsx`/`.mts`/`.cts` to TypeScript, `.mjs` to JavaScript, `.sh` to shell
  - [x] a path with a space and a non-ASCII name survive the `-z` split
  - [x] `run_git` returning `None` raises `SnapshotIntegrityError` and logs ERROR (`caplog`)
- [x] Success: tests pass; ruff and pyright clean
- [x] Commit: `feat(metrology): add adapter contract and file-set resolution`

## Task 14: Shared length counting (D1, D6) — Effort 2
- [x] Create `snapshot/lengths.py`:
  - [x] non-blank physical line count for a text, and for a line span (start, end inclusive)
  - [x] `distribution(values)` → `Distribution` (count, total, min, p50, p90, max); define the percentile method once and state it in the docstring
  - [x] file-length measurement builder: `per_file` for every file, distribution, and `limit`. Files over the limit are not a stored field: they are the `per_file` entries above `limit` (Success Criterion 5). Add a `files_over_limit()` helper here that derives them, for the CLI summary
  - [x] function-length measurement builder: distribution over functions, `over_limit` rows only for functions above a declared limit; empty when no limit
- [x] Tests in `tests/metrology/snapshot/test_lengths.py`: blank and whitespace-only lines excluded; distribution on 1, 2 and 10 values; `files_over_limit()` returns exactly the files above the limit and nothing with no limit; function `over_limit` rows appear only above the limit; no limit gives empty `over_limit` with distribution present
- [x] Success: both adapters can build length measurements from this module alone (no duplication); tests pass
- [x] Commit: `feat(metrology): add shared length counting`

## Task 15: Capture real tool output fixtures (Technical Requirements) — Effort 2
- [x] Pre-check: `../context-forge/node_modules/.bin/eslint` exists and `git -C ../context-forge ls-files` lists a file matched by its `eslint.config.mjs` `ignores`. If either fails, write a `BLOCKED:` line under this task and stop; never install into `../context-forge`. Tasks 26 and 27 need none of these fixtures and may proceed first
- [x] Store under `tests/metrology/fixtures/snapshot/`, with a `README.md` recording, per file, the exact command, exit code, tool version and source repo
- [x] ruff: `ruff check --no-cache --exit-zero --output-format json` on squadron, plus a run on a scratch file with known violations so the fixture holds non-empty findings. Trim large output only by dropping list entries, never by editing their fields
- [x] pyright: `--outputjson` on squadron, plus a scratch file with one error and one warning, so both severities appear (exit code recorded), plus a scratch project with an invalid `pyrightconfig.json` for the fatal-exit case
- [x] uv: stdout/stderr and exit code of `uv sync --check --locked --offline` for in-sync (squadron) and out-of-sync (scratch project) cases
- [x] ESLint: `node_modules/.bin/eslint --format json` in `../context-forge` on a few `src` files plus one file matched by its `ignores` (for example a tracked `vitest.config.ts`). Record in the README exactly how ESLint 10 reports the skipped file; Task 28 parses that, not an assumed shape. Also capture a fatal exit by running the same binary with `--config` pointing at a scratch config that fails to load (a file outside `../context-forge`)
- [x] Exit-code table in the README, taken from the captures: for pyright and ESLint, which exit codes accompany a parseable JSON findings report (a normal result) and which mean the tool failed. Tasks 24 and 28 implement exactly this table
- [x] Version outputs: `--version` text for ruff, pyright, uv, ESLint
- [x] Success: `git -C ../context-forge status --porcelain` empty after capture; squadron tree clean apart from the new fixtures
- [x] Commit: `test(metrology): add real tool-output fixtures for snapshot adapters`

## Task 16: Default subprocess ToolRunner and tool resolution (D8) — Effort 3
- [x] Create `snapshot/runner.py`:
  - [x] `SubprocessToolRunner`: argv list, never a shell; enforces `timeout_s`; returns `timed_out=True` on timeout rather than raising; UTF-8 decoding with replacement
  - [x] `resolve_tool(repo_root, name, project_dirs, use_path)`: project location first (`.venv/bin/…`, `node_modules/.bin/…`), then `PATH` only where D8 allows (ruff, pyright)
  - [x] `probe_version(runner, tool_path, timeout_s)`: runs `--version`, parses a version; a hang, non-zero exit or unparseable output returns a failure with detail ("version probe failed: …") and logs WARNING with the tool, command and stderr head
  - [x] argv chunking helper that splits a file list to stay under argv limits
- [x] Success: module has no adapter-specific logic

## Task 17: Runner tests — Effort 2
- [x] `tests/metrology/snapshot/test_runner.py`:
  - [x] real subprocess: a command that exceeds a 1 s timeout returns `timed_out=True`
  - [x] resolution prefers the project binary over `PATH`; ESLint is never resolved from `PATH`; missing tool returns not-found
  - [x] version probe parses each Task 15 `--version` capture (ruff, pyright, uv, ESLint)
  - [x] version probe: timeout, non-zero exit and unparseable output each return a failure and log WARNING (`caplog`)
  - [x] chunking covers every file exactly once
- [x] Success: tests pass; ruff and pyright clean
- [x] Commit: `feat(metrology): add subprocess tool runner and version probe`

## Task 18: Orchestrator `take_snapshot` (Data Flow, D3) — Effort 3
- [x] Create `snapshot/take.py` with `take_snapshot(repo_root, registry, runner, store) -> CodeSnapshot`, importing only the contract, never an adapter
- [x] Flow per Data Flow: preflight → `derive_project_id` → effective exclusions → `resolve_files` → group → per language:
  - [x] log one INFO line per language before measuring
  - [x] no adapter → every `SnapshotMetric` absent `no_adapter`
  - [x] adapter → `measure`; raise if it returns an undeclared metric or omits a declared one
  - [x] fill `metric_unsupported` for metrics the adapter doesn't declare
- [x] After measuring, `check_integrity`; on failure nothing is written
- [x] Build `CodeSnapshot` (squadron version, `measured_at`, limits, exclusions), then `store.write_snapshot`
- [x] Success: under ~300 lines; no adapter import

## Task 19: Orchestrator tests — Effort 3
- [x] `tests/metrology/snapshot/test_take.py` with fake adapters and `FakeToolRunner`:
  - [x] a language with no adapter gets every metric absent `no_adapter`
  - [x] an adapter declaring a subset gets `metric_unsupported` for the rest
  - [x] every `SnapshotMetric` member appears for every language present (Integration Requirements, guards 401)
  - [x] adapter returning an undeclared metric, or omitting a declared one, raises
  - [x] a fake adapter that writes a file into the repo causes `SnapshotIntegrityError` and no record is written
  - [x] a dirty tree is refused before any adapter runs and nothing is written
  - [x] two runs on one commit leave one record and identical JSON apart from `measured_at`
  - [x] the per-language INFO lines are logged
- [x] Success: tests pass; ruff and pyright clean
- [x] Commit: `feat(metrology): add snapshot orchestrator`

## Task 20: Python adapter — ast length (D6) — Effort 3
- [x] Create `snapshot/python_adapter.py` with the adapter class: `language` Python, `metrics` file length and function length only (Task 22 adds lint, Task 24 adds type errors; never stub placeholder measurements), `convention_exclusions` `**/*_pb2.py`, `**/*_pb2_grpc.py`. The `squadron-python-ast` tool name constant lives here; the `ruff` and `pyright` names live in the modules that run them (Tasks 22 and 24)
- [x] File length via `lengths.py` for every file
- [x] Function length: walk `ast` for `def`/`async def` at any depth, qualified like `__qualname__` (`Cls.method`, `outer.<locals>.inner`); span from first decorator (or def line) to `end_lineno`; lambdas excluded
- [x] `SyntaxError`, `RecursionError`, `MemoryError`, `UnicodeDecodeError` → file in `unparsed_files`, WARNING per file, still counted for file length
- [x] Tool identity: version is squadron version plus Python version; `counting` states the D6 definition
- [x] Success: the measured project's code is never imported or executed

## Task 21: Python length tests — Effort 2
- [x] `tests/metrology/snapshot/test_python_length.py`: decorated function span; nested and method qualnames; lambda excluded; nested function counted on its own and inside its parent; over-limit rows; each of the four parse failures lands in `unparsed_files` with a WARNING (`RecursionError` from deeply nested source, undecodable bytes)
- [x] Success: tests pass; ruff and pyright clean
- [x] Commit: `feat(metrology): add Python adapter with ast length`

## Task 22: Python adapter — ruff lint (D4, D8) — Effort 2
- [x] Create `snapshot/config_hash.py` (canonical-JSON hash of a pyproject table, content hash of a config file; shared by ruff, pyright and ESLint) and `snapshot/python_lint.py` (ruff runner and rule-set resolution). `python_adapter.py` only delegates. The slice design's module table already lists them
- [x] Add lint count to the adapter's `metrics`
- [x] Resolve ruff, probe version; missing → `tool_missing`; probe failure → `tool_failed` without running ruff
- [x] Rule set: `ruff.toml`, then `.ruff.toml`, then pyproject `[tool.ruff]` hashed as canonical JSON (sorted keys); none → `tool-defaults`. Use the `config_hash.py` helper for the pyproject table
- [x] Run `ruff check --no-cache --exit-zero --output-format json` over chunked file lists; count findings per file into `per_file` (non-zero only)
- [x] Non-zero exit, timeout or unparseable JSON → `tool_failed` with WARNING (tool, command, stderr head); never a partial count
- [x] Success: parser reads the Task 15 ruff fixture shape

## Task 23: Ruff lint tests — Effort 2
- [x] `tests/metrology/snapshot/test_python_lint.py` with `FakeToolRunner` returning the Task 15 fixtures: counts match the fixture; each rule-set source is chosen in order; editing `[project] version` in pyproject doesn't change the hash, editing `[tool.ruff]` does; missing tool, version-probe failure, timeout, bad JSON and non-zero exit each give the right absence and a WARNING
- [x] Success: tests pass; ruff and pyright clean
- [x] Commit: `feat(metrology): add ruff lint to the Python adapter`

## Task 24: Python adapter — uv environment and pyright (D7, D8) — Effort 3
- [x] Create `snapshot/python_types.py` holding the uv environment check and the pyright runner. `python_adapter.py` only delegates
- [x] Add type errors to the adapter's `metrics`
- [x] Environment check in order: `uv.lock` exists; `.venv/` exists; `uv sync --check --locked --offline` exits 0. Each failure → type errors absent `environment_unresolved` with detail naming the condition (`.venv not found`, `lockfile type not supported: poetry.lock` when another lockfile is present)
- [x] uv outcomes per D7: exit 1 → `environment_unresolved`; uv not found → `tool_missing`; timeout, other exit or unparseable output → `tool_failed`; each non-success at WARNING
- [x] `EnvironmentIdentity`: `uv.lock` path, its SHA-256, interpreter version of `.venv/bin/python`
- [x] Pyright rule set: `pyrightconfig.json`, then pyproject `[tool.pyright]`, else `tool-defaults`
- [x] Run pyright `--outputjson --pythonpath .venv/bin/python` on chunked files; count only `severity == "error"`. Exit codes follow the Task 15 table: exit 1 with parseable JSON is a normal result (errors were found), never `tool_failed`. Any other exit code, a timeout or unparseable JSON → `tool_failed` with WARNING (tool, command, stderr head), never a partial count. Missing → `tool_missing`; version-probe failure → `tool_failed` without running pyright
- [x] `counting` states that every snapshot file is analyzed regardless of pyright `include` (D4)
- [x] Success: `python_adapter.py`, `python_lint.py` and `python_types.py` each stay under ~300 lines

## Task 25: Environment and pyright tests — Effort 2
- [x] `tests/metrology/snapshot/test_python_types.py`, using Task 15 fixtures: no `uv.lock`; `poetry.lock` only; no `.venv`; uv exit 1; uv missing; uv timeout; uv unexpected exit — each gives the specified absence, detail and WARNING. In-sync case counts only errors from the pyright fixture and carries the environment identity. Pyright failure modes: exit 1 with errors is counted, not failed; missing tool, version-probe failure, timeout, bad JSON and a fatal exit (the Task 15 invalid-config capture) each give the specified absence and a WARNING
- [x] Success: tests pass; ruff and pyright clean
- [x] Commit: `feat(metrology): add Python type-error measurement with uv environment check`

## Task 26: TypeScript adapter — tree-sitter length (D5, D6) — Effort 3
- [x] Create `snapshot/typescript_length.py` (tree-sitter parsing and function walk) and `snapshot/typescript_adapter.py` (the adapter class, delegating): `language` TypeScript, `metrics` file length and function length (Task 28 adds lint); `convention_exclusions` `**/*.d.ts`, `**/node_modules/**`, `**/dist/**`. The `squadron-tree-sitter-ts` tool name constant lives in `typescript_length.py`; the `eslint` name lives in `typescript_lint.py` (Task 28)
- [x] Parse `.tsx` with the TSX grammar and the rest with the TypeScript grammar
- [x] Count function declarations (generators included), methods (constructors, accessors), function expressions, block-bodied arrows; skip expression-bodied arrows. Name from the node, else the enclosing variable declarator or property, else `<anonymous>`
- [x] Tree with an error root, or undecodable file → `unparsed_files` with WARNING; still counted for file length
- [x] Tool version: squadron version plus tree-sitter and grammar versions
- [x] Success: no Node process runs for length

## Task 27: TypeScript length tests — Effort 2
- [x] `tests/metrology/snapshot/test_typescript_length.py`: each counted node kind; expression-bodied arrow skipped; naming from declarator and property; `<anonymous>`; `.tsx` with JSX parses; a syntax-error file and an undecodable-bytes file each land in `unparsed_files` with WARNING
- [x] Success: tests pass; ruff and pyright clean
- [x] Commit: `feat(metrology): add TypeScript adapter with tree-sitter length`

## Task 28: TypeScript adapter — ESLint lint (D4, D5, D8) — Effort 3
- [x] Create `snapshot/typescript_lint.py` (ESLint runner and rule-set resolution, using `config_hash.py`); `typescript_adapter.py` only delegates. Add lint count to the adapter's `metrics`
- [x] Resolve only `node_modules/.bin/eslint`; missing → `tool_missing` (detail `node_modules/.bin/eslint not found`); never `npx`
- [x] Rule set: `eslint.config.{js,mjs,cjs}` hashed by content; none → lint absent `tool_failed` ("no eslint.config.{js,mjs,cjs} found") without running ESLint
- [x] Run `--format json` without `--cache` on chunked files; count messages per file
- [x] Files ESLint skipped (identified as recorded in the Task 15 README) go to `tool_ignored_files` and add nothing to the count
- [x] Exit codes follow the Task 15 table: exit 1 with parseable JSON is a normal result (errors were found), never `tool_failed`. Any other exit code (for example a config load error), a timeout or unparseable JSON → `tool_failed` with WARNING (tool, command, stderr head), never a partial count. Version-probe failure → `tool_failed` without running ESLint. No `environment` on ESLint lint (D2)
- [x] Success: TypeScript type errors come out `metric_unsupported` from the orchestrator, not from the adapter; every TypeScript module stays under ~300 lines

## Task 29: ESLint tests — Effort 2
- [x] `tests/metrology/snapshot/test_typescript_lint.py` with the Task 15 ESLint fixtures: counts match; the ignored file is in `tool_ignored_files` and not counted; no config gives `tool_failed`; missing binary gives `tool_missing`; exit 1 with findings is counted, not failed; version-probe failure, timeout, bad JSON and a fatal exit (the Task 15 config-load capture) give `tool_failed` with WARNING
- [x] Success: tests pass; ruff and pyright clean
- [x] Commit: `feat(metrology): add ESLint lint to the TypeScript adapter`

## Task 30: Default registry and CLI command (API Contracts) — Effort 2
- [x] `snapshot/registry.py`: `default_registry()` returning the Python and TypeScript adapters; the only non-test module importing concrete adapters
- [x] `src/squadron/cli/commands/metrology_snapshot.py`: `snapshot [--cwd PATH] [--json]`, registered on `metrology_app`
  - [x] passes `default_registry()` and `SubprocessToolRunner` to `take_snapshot`
  - [x] human output: one line per language with each metric summary or `absent: <reason> (<detail>)`, then the limits line (`none declared` when unset), exclusion count and record path
  - [x] `--json` prints the `CodeSnapshot` JSON
  - [x] `SnapshotPreflightError`, `SnapshotIntegrityError`, `MetrologyIdentityError`, `MetrologyStoreError` → message on stderr, exit 1. The command logs `MetrologyStoreError` at ERROR with the store path before exiting (failure-mode table)
  - [x] help text states that snapshotting a repo runs its `node_modules/.bin/eslint` and its JavaScript config (Special Considerations → Security)
- [x] Success: `sq metrology snapshot --help` shows both options

## Task 31: CLI tests — Effort 2
- [x] `tests/metrology/snapshot/test_snapshot_cli.py` with `CliRunner`, a `snapshot_git_repo` repo and an isolated store: clean run exits 0 and writes one record; `--json` parses as `CodeSnapshot`; dirty tree exits 1 with the path on stderr and no record; `--cwd` measures the given repo, not the process cwd; `sq metrology list`, `report baseline` and `audit delta` give the same output with and without a snapshot record in the store (Success Criterion 10); a store dir that can't be written (a regular file in its place) exits 1 with the path on stderr, logs ERROR, and leaves no record
- [x] Success: tests pass; full `tests/metrology/` passes; ruff and pyright clean
- [x] Commit: `feat(metrology): add sq metrology snapshot command`

## Task 32: Docs, CHANGELOG and squadron config — Effort 1
- [x] `docs/COMMANDS.md`: document `sq metrology snapshot`, and add the four new keys to the metrology config table
- [x] CHANGELOG: one user-facing bullet under Unreleased
- [x] Add the walkthrough step 1 values to squadron's local `.squadron.toml` (gitignored; not committed)
- [x] Commit: `docs: document sq metrology snapshot`

## Task 33: Verification walkthrough — Effort 3
- [x] Run walkthrough steps 2–10 from the slice design against squadron and `../context-forge`. Record each step's actual output summary in the slice design under a "Walkthrough Results" heading
- [x] Any step that fails is a bug in this slice: fix it, add a regression test, rerun the step
- [x] Success: all ten steps match their expected structure; `git -C ../context-forge status --porcelain` empty afterwards; scratch clones removed
- [x] Commit: `docs: record slice 400 walkthrough results`

## Task 34: Final validation — Effort 1
- [ ] `.venv/bin/ruff format`, `.venv/bin/ruff check`, `.venv/bin/pyright` (zero errors), and the full test suite pass
- [ ] Every new module is at ~300 lines or less (`wc -l src/squadron/metrology/snapshot*.py src/squadron/metrology/snapshot/*.py`)
- [ ] Every Success Criterion (Functional 1–10, Technical, Integration) in the slice design maps to a passing test or a recorded walkthrough step
- [ ] Commit any remaining changes on the slice branch
