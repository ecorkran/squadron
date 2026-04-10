---
docType: tasks
slice: pipeline-run-summary-persistence-and-restore
project: squadron
lld: user/slices/163-slice.pipeline-run-summary-persistence-and-restore.md
dependencies: [161-summary-step-with-emit-destinations, 162-sq-summary-clipboard-summary-for-manual-context-reset]
projectState: Slice 163 design complete and reviewed (PASS). Working tree clean on main.
dateCreated: 20260410
dateUpdated: 20260410
status: complete
---

## Context Summary

- Working on slice 163: Pipeline Run Summary Persistence and Restore
- Closes the "run pipeline in terminal, restore context in VS Code" workflow gap
- Three implementation sites: `emit.py` (default file path), `summary_instructions.py` (--restore), `summary.md` skill (--restore branch)
- One cross-cutting concern: thread `_project` param into `ActionContext` during pipeline init
- One prompt-only alignment: update `run.md` summary handler to write to conventional path via Bash
- Dependencies: slices 161 (emit registry, `_emit_file`) and 162 (`summary_instructions.py`, `summary.md`, `gather_cf_params`)
- Next: Phase 6 implementation

---

## Tasks

### T1: Verify source files and locate insertion points

- [x] Read `src/squadron/pipeline/emit.py` — locate `_emit_file()`, `EmitDestination`, and existing module-level path constants
- [x] Read `src/squadron/pipeline/executor.py` — locate where `ActionContext` is constructed and params are assembled
- [x] Read `src/squadron/cli/commands/run.py` — confirm how `cwd` is available at pipeline init time
- [x] Read `src/squadron/pipeline/summary_render.py` — confirm `gather_cf_params()` signature and return type
- [x] Read `src/squadron/cli/commands/summary_instructions.py` — confirm current function signature and import structure
- [x] Read `commands/sq/summary.md` — confirm current argument parsing section structure
- [x] Read `commands/sq/run.md` — locate the `### summary` action handler section
  - [x] Confirm all seven insertion points are understood before proceeding

### T2: Add summaries directory constant to `emit.py`

- [x] In `src/squadron/pipeline/emit.py`, add module-level constant:
  `_DEFAULT_SUMMARIES_DIR = Path.home() / ".config" / "squadron" / "runs" / "summaries"`
  Place alongside any existing path constants (e.g. near `_DEFAULT_RUNS_DIR` if referenced, or at top of module)
  - [x] Constant uses `pathlib.Path` (no `os.path`)
  - [x] Constant is module-private (underscore prefix)

### T3: Extend `_emit_file()` with default path resolution

- [x] In `_emit_file()`, add conditional before the existing write logic:
  - If `dest.arg is not None`: existing behavior (resolve relative to `ctx.cwd`)
  - If `dest.arg is None`: resolve default path using `ctx.params.get("_project") or "unknown"` and `ctx.pipeline_name or "unknown"`, forming `_DEFAULT_SUMMARIES_DIR / f"{project}-{pipeline}.md"`
- [x] Ensure `_DEFAULT_SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)` is called before write when using default path
  - [x] Explicit path behavior is unchanged
  - [x] Default path is `~/.config/squadron/runs/summaries/{project}-{pipeline}.md`
  - [x] `mkdir` is called only on the summaries dir (not redundantly on the full path)

### T4: Test `_emit_file()` default path behavior

- [x] In the existing emit test file (locate under `tests/pipeline/`), add tests for `_emit_file()` when `dest.arg is None`:
  - [x] Test: `dest.arg=None` with `_project="myproject"` and `pipeline_name="P4"` writes to `<tmp>/.../summaries/myproject-P4.md` (use `tmp_path` fixture, patch `_DEFAULT_SUMMARIES_DIR`)
  - [x] Test: `dest.arg=None` with `_project=None` falls back to `"unknown"` in filename
  - [x] Test: existing explicit-path behavior still works when `dest.arg` is set
  - [x] All new tests pass: `uv run pytest tests/pipeline/test_emit.py -v`

### T5: Thread `_project` param into `ActionContext` during pipeline init

- [x] In `src/squadron/pipeline/executor.py` (or `src/squadron/cli/commands/run.py` — confirm in T1), locate where params dict is assembled before `ActionContext` is constructed
- [x] Call `gather_cf_params(cwd)` from `squadron.pipeline.summary_render` and extract `"project"` value
- [x] Set `params["_project"] = project_value or "unknown"` — only if `_project` is not already set (don't override explicit user params)
- [x] Import `gather_cf_params` from `squadron.pipeline.summary_render`
  - [x] `_project` is present in `ActionContext.params` for all pipeline runs
  - [x] If CF is unavailable, `_project` is `"unknown"` (no exception raised)
  - [x] Explicit `_project` in pipeline YAML params is not overwritten

### T6: Test `_project` param threading

- [x] In `tests/pipeline/` or `tests/cli/`, add test(s) for `_project` injection:
  - [x] Test: running a minimal pipeline with a mocked CF project name results in `_project` being set in `ActionContext.params`
  - [x] Test: CF unavailable (mock `gather_cf_params` to return `{}`) results in `_project="unknown"`, no exception
  - [x] All new tests pass

### T7: Commit emit and executor changes

- [x] `ruff format .`
- [x] `git add` changed files in `src/squadron/pipeline/emit.py`, executor/run, and tests
- [x] `git commit -m "feat: add default summaries path to emit and thread _project into ActionContext"`

### T8: Add `--restore` flag to `summary_instructions.py`

- [x] Add `restore: bool = typer.Option(False, "--restore", hidden=True)` to the `summary_instructions()` function signature
- [x] Add early-return branch: `if restore: _handle_restore(cwd); return`
- [x] Implement `_handle_restore(cwd: str) -> None` in the same file:
  - Resolve project name via `gather_cf_params(cwd).get("project")`
  - If no project: print error to stderr, `raise typer.Exit(code=1)`
  - Glob `~/.config/squadron/runs/summaries/{project}-*.md`, sort by `st_mtime` descending
  - If no matches: print error to stderr, `raise typer.Exit(code=1)`
  - If multiple matches: print selection info to stderr (pipeline name + filename for each), print "Using most recent: {name}" to stderr
  - Print contents of `matches[0]` to stdout
- [x] `--restore` is mutually exclusive with template argument and `--suffix` (handled by early return — no explicit validation needed unless both are provided; document in docstring)
  - [x] `--restore` flag added and hidden from `--help`
  - [x] Error path (no project, no files) exits 1 with descriptive stderr message
  - [x] Happy path prints file contents to stdout, exits 0
  - [x] Multiple-match case lists options on stderr, uses most recent

### T9: Test `--restore` flag behavior

- [x] In `tests/cli/commands/test_summary_instructions.py` (or create if absent), add tests:
  - [x] Test: `--restore` with one matching file → file contents on stdout, exit 0
  - [x] Test: `--restore` with multiple matching files → most recent on stdout, list on stderr, exit 0
  - [x] Test: `--restore` with no matching files → error on stderr, exit 1
  - [x] Test: `--restore` with no CF project (mock `gather_cf_params` returning `{}`) → error on stderr, exit 1
  - [x] All new tests pass: `uv run pytest tests/cli/commands/test_summary_instructions.py -v`

### T10: Update `commands/sq/summary.md` with `--restore` branch

- [x] In the Input parsing section of `commands/sq/summary.md`, add detection for `--restore`:
  - If `$ARGUMENTS` is `--restore`: run restore flow (Steps R1–R2), skip normal summary flow
  - Otherwise: existing behavior unchanged
- [x] Add Step R1: run `sq _summary-instructions --restore` via Bash; if non-zero exit, show error and stop
- [x] Add Step R2: output the returned text as a context block; do NOT copy to clipboard; print confirmation `Context restored from {filename} (N chars).`
  - [x] `--restore` branch is clearly separated from normal summary flow
  - [x] No clipboard write in restore path
  - [x] Confirmation line is printed after output

### T11: Update `commands/sq/run.md` summary handler to write to conventional path

- [x] In the `### summary` action handler section of `commands/sq/run.md`, add file-write step after generating the summary text and before or alongside clipboard handling:
  - Resolve project name via `cf status` (CF is already used in the pipeline run, so it is available); extract from its output or use `sq _summary-instructions --restore` to confirm the project name is resolvable
  - Resolve pipeline name from the run context (available in step JSON as pipeline name slug)
  - Write summary to `~/.config/squadron/runs/summaries/{project}-{pipeline}.md` via Bash heredoc
  - Create the directory if needed (`mkdir -p`)
- [x] The file-write step is additive — existing clipboard and stdout handling unchanged
  - [x] File is written to the conventional path after summary generation
  - [x] Existing clipboard emit is unaffected
  - [x] Project name is resolved, not hardcoded

### T12: Commit skill and run.md changes

- [x] `ruff format .` (for any Python touched; markdown files need no formatting)
- [x] `git add` changed files: `commands/sq/summary.md`, `commands/sq/run.md`, `src/squadron/cli/commands/summary_instructions.py`, tests
- [x] `git commit -m "feat: add --restore to /sq:summary and write summary to conventional path in run.md"`

### T13: Verification walkthrough

- [x] Run a pipeline with `emit: [file]` (no explicit path) — confirm file appears at `~/.config/squadron/runs/summaries/{project}-{pipeline}.md`
- [x] Run the same pipeline again — confirm file is overwritten, not appended
- [x] `sq _summary-instructions --restore` — confirm contents of the summary file are printed to stdout
- [x] `sq _summary-instructions --restore` with no files — confirm exit 1 with clear error
- [x] `/sq:summary --restore` in an active Claude Code session — confirm context is seeded and confirmation line is printed, no clipboard write
- [x] Explicit-path `emit: [file: /tmp/test.md]` still writes to `/tmp/test.md` (no regression)
- [x] All tests pass: `uv run pytest tests/ -v`
  - [x] All verification steps pass before marking slice complete

### T14: Update slice plan and DEVLOG

- [x] Mark slice 163 as complete (`[x]`) in `project-documents/user/architecture/140-slices.pipeline-foundation.md`
- [x] Update slice design frontmatter: `status: complete`, `dateUpdated: YYYYMMDD`
- [x] Write DEVLOG entry summarizing implementation decisions and completion
- [x] `git add -A && git commit -m "docs: mark slice 163 complete"`
