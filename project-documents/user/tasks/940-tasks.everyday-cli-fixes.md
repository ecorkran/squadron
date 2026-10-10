---
docType: tasks
slice: everyday-cli-fixes
project: squadron
lld: user/slices/940-slice.everyday-cli-fixes.md
dependencies: []
projectState: >
  Slice design 940 complete (20261009). No code written. Seven independent fixes (D1-D7) to
  everyday CLI commands, each committed on its own.
dateCreated: 20261009
dateUpdated: 20261009
status: in_progress
---

## Context Summary

- Working on **940 everyday-cli-fixes**: five small fixes plus a cosmetic list color, grouped on
  purpose (#194). Closes #198 (`sq pipelines copy`), #197 (`sq models init`), #169 (path-run
  names), #177 (Rich swallows bracketed text), #193 (`-v` names the review profile).
- Tasks reference the slice design by decision number (D1-D8). Its D-sections, the D8
  failure-mode table, Success Criteria and Verification Walkthrough are the contract.
- Order follows the design's Implementation Notes, cheapest first: D5, D4, D6, then D3 → D1 → D2,
  then D7. Each part is independent; commit each on its own so it can be reverted alone.
- Tests use a temporary home and project directory and never touch the real
  `~/.config/squadron`. Every D8 row has a test asserting both the exit code and the message or
  log record. Locate existing tests with `grep` before adding new files.
- Every task that changes code ends with `ruff format`, `ruff check`, `pyright` (zero errors),
  its tests, and a commit on the slice branch with a semantic prefix.
- Out of scope: `sq review <file>` inference (#142), `each`/`loop` dry-run previews (#149, #145),
  `--<param>` flags (#56), `sq review --max` (slice 941).
- Effort: 3/5.

---

## Task 1 — Create the slice branch

- [x] Run `cf config get git.integration_branch`; call its value the target (`main` if empty). Confirm `git status` is clean and the current branch is the target
- [x] `git checkout -b 940-slice.everyday-cli-fixes {target}`
  - [x] Success: `git branch --show-current` prints `940-slice.everyday-cli-fixes`

---

## Part A — D5 (#177): escape Rich markup in CLI output

## Task 2 — Guard test with a shrinking allowlist (D5)

- [x] Create `tests/cli/test_rich_escape_guard.py`: parse every `.py` under `src/squadron/cli` with `ast`
- [x] Find each f-string passed to `rprint`, `console.print`, or a `Console(...).print` call, including multi-line calls
- [x] For each, collect names bound by an enclosing `except ... as <name>`; flag any interpolated expression that references such a name and is not wrapped in `escape(...)`
  - [x] The variable's name does not matter (`exc`, `e`, `err`, anything)
  - [x] `typer.echo` calls are ignored
- [x] A failure message names the file and line of each unescaped site
- [x] Add a module-level `_UNSWEPT` set holding the repo-relative path of every file that currently has a flagged site (run the checker once to build it). Flags in an `_UNSWEPT` file are tolerated; flags anywhere else fail the test
  - [x] A second test fails if an `_UNSWEPT` file has no flagged sites, with a message to remove it from the set. This keeps the set shrinking as Tasks 3-8 proceed
- [x] Add a self-test in the same file: feed the checker small source snippets (unescaped site, escaped site, differently named variable, multi-line call) and assert it flags exactly the unescaped ones
  - [x] Success: all three tests pass on the current tree
- [x] Commit: `test: add Rich escape guard with unswept-file allowlist`

## Task 3 — Sweep metrology modules (D5)

- [x] Files: `cli/commands/metrology.py`, `cli/commands/metrology_preemption.py`
- [x] Run `grep -n "rprint\|console.print" <file>` and inspect every site that interpolates exception text or user-supplied text (paths, names, values from args or files) into Rich markup. Wrap each such interpolated expression in `rich.markup.escape(...)`, adding `from rich.markup import escape` where missing
  - [x] Do not rewrite message wording; `typer.echo` sites stay as they are
- [x] Remove each of these files from `_UNSWEPT` if it is listed (a file with no flagged site was never listed; the second guard test enforces the rest)
  - [x] Success: the guard tests pass; `pytest tests/cli` passes
- [x] Commit: `fix: escape exception and user text in metrology CLI output`

## Task 4 — Sweep run modules (D5)

- [x] Files: `cli/commands/run.py`, `run_item.py`, `run_dry_run.py`, `cli/run_views.py`
- [x] Same procedure as Task 3
- [x] Add one behavior test: an error path in one of these modules that interpolates an exception message containing `[codex]` prints it intact (use `CliRunner`; reuse the setup of an existing error-path test)
- [x] Remove each swept file from `_UNSWEPT` if it is listed
  - [x] Success: guard tests pass; the `[codex]` test passes; `pytest tests/cli` passes
- [x] Commit: `fix: escape exception and user text in run CLI output`

## Task 5 — Sweep review and PR modules (D5)

- [x] Files: `cli/commands/review.py`, `review_pr.py`, `pr.py`
- [x] Same procedure as Task 3; remove each swept file from `_UNSWEPT` if it is listed
  - [x] Success: guard tests pass; `pytest tests/cli` passes
- [x] Commit: `fix: escape exception and user text in review and PR CLI output`

## Task 6 — Sweep setup and install modules (D5)

- [x] Files: `cli/commands/setup.py`, `install.py`, `install_options.py`, `doctor.py`, `skills.py`, `config.py`
- [x] Same procedure as Task 3; remove each swept file from `_UNSWEPT` if it is listed
  - [x] Success: guard tests pass; `pytest tests/cli` passes
- [x] Commit: `fix: escape exception and user text in setup and install CLI output`

## Task 7 — Sweep event, pool, shutdown, models and auth modules (D5)

- [x] Files: `cli/commands/events.py`, `pools.py`, `shutdown.py`, `models.py`, `auth.py`
- [x] Same procedure as Task 3; remove each swept file from `_UNSWEPT` if it is listed
  - [x] Success: guard tests pass; `pytest tests/cli` passes
- [x] Commit: `fix: escape exception and user text in event, pool, models and auth CLI output`

## Task 8 — Sweep remaining modules and retire the allowlist (D5)

- [x] Files: `serve.py`, `spawn.py`, `task.py`, `message.py`, `list.py`, `history.py`, plus any other file under `src/squadron/cli` that `grep -rnE "rprint|console\.print" src/squadron/cli` lists and Tasks 3-7 did not cover
- [x] Same procedure as Task 3
- [x] Delete `_UNSWEPT` and its second test, so the guard now applies to the whole tree
  - [x] Success: the guard test passes with no allowlist; adding an unescaped `except ... as e` f-string print to any CLI file makes it fail (check once by hand, then revert); `pytest tests/cli` passes
- [x] Commit: `fix: escape remaining CLI output and retire guard allowlist`

---

## Part B — D4 (#169): run names and source paths

## Task 9 — `RunState.pipeline_path` and `init_run` (D4)

- [ ] In `pipeline/state.py`, add optional `pipeline_path: str | None = None` to `RunState`; leave `_SCHEMA_VERSION` at 5
- [ ] Add a keyword parameter to `StateManager.init_run` for the path and store it on the new state; the name continues to be lowercased inside `init_run`
- [ ] Tests (`tests/pipeline/test_state.py`):
  - [ ] A state with `pipeline_path` round-trips through write and read
  - [ ] A state file written without the field (use an existing fixture or literal JSON from a v5 file) loads with `pipeline_path` of `None` and resumes unchanged
  - [ ] A state file containing an unknown extra field still loads (older-reader behavior)
  - [ ] Success: tests pass
- [ ] Commit: `feat: record optional pipeline_path in run state`

## Task 10 — Record identity and path at run start (D4)

- [ ] In `cli/commands/run.py`, at both `init_run` call sites (around lines 239 and 672), pass `pipeline_identity(<loaded file path>)` as the name instead of the CLI argument
- [ ] When the CLI argument was a file path, also pass its absolute path as `pipeline_path`. Find how `load_pipeline` decides that an argument is a path and reuse that decision; do not add a second path-detection rule
- [ ] Tests (`tests/cli/commands/test_run_pipeline.py` or the nearest existing run test): `sq run ./x/Foo.yaml` records pipeline `foo` and the absolute path; a named run (`sq run slices-plan`) records no `pipeline_path`; `sq runs list` filtered by `foo` finds the path run
  - [ ] Success: tests pass
- [ ] Commit: `fix: record pipeline identity, not the path argument, as the run name`

## Task 11 — Resume, `--status` and item resume use the recorded path (D4)

- [ ] Add one small helper next to the other run helpers that returns the load target for a state: `state.pipeline_path` when set, otherwise `state.pipeline`. The path is never lowercased
- [ ] Replace `load_pipeline(state.pipeline)` at the resume, `--status` and item-resume sites (around `run.py` lines 718, 865, 1188) with `load_pipeline(<helper>)`
- [ ] Check `cli/commands/runs.py` (`load_definition=load_pipeline`, line 141): confirm whether prune loads by `run.pipeline`; if it does, route it through the same helper so a path run is not reported as an unavailable pipeline
- [ ] When the recorded path is set but the file is gone, fail with an error naming the path and exit 1; never fall back to a same-named pipeline
  - [ ] A path that exists but fails to load or validate surfaces `load_pipeline`'s existing error, naming the path, exit 1
- [ ] Tests, one per D8 resume row plus the happy path:
  - [ ] Resume of a path run reloads the same file (edit the file's description between start and resume and assert the loaded definition is that file)
  - [ ] Missing recorded path: exit 1, message names the path, and a same-named built-in is not loaded
  - [ ] Recorded path that fails validation: exit 1, error names the path
  - [ ] A pre-slice state (no `pipeline_path`) resumes by name unchanged
  - [ ] A pre-slice path run (state `pipeline` is the lowercased path, no `pipeline_path`) is not migrated: it keeps that name in `sq runs list`, and resume still loads through the path in `pipeline`, as it does today
  - [ ] `--status` and item resume use the helper (one case each)
  - [ ] Success: tests pass
- [ ] Commit: `fix: resume path runs from the recorded source path`

---

## Part C — D6 (#193): the review profile is visible

## Task 12 — Review action logs its resolved profile (D6)

- [ ] In `pipeline/actions/review.py`, immediately after `resolve_review_profile` returns (around line 200), log at INFO: `review: step <step> profile=<profile> model=<model>`; leave the executor's pre-action label unchanged
- [ ] Tests (`tests/pipeline/`, next to the existing review action tests): with `caplog` at INFO, a review step logs the line with the resolved profile and model; the profile shown matches an alias profile, a template profile, and the sdk default in one case each
  - [ ] Success: tests pass
- [ ] Verify the line reaches the terminal under `-v`: confirm `run.py` sets the pipeline logger to INFO under `-v` (around line 1050) and add one `CliRunner` test asserting `-v` output contains `profile=`
- [ ] Commit: `feat: log resolved review profile in pipeline review action`

## Task 13 — `aiProfile` in review artifacts (D6)

- [ ] In `review/persistence.py`, add optional keyword `profile: str | None = None` to `_review_frontmatter_lines` (like `requested_model` and `run_id`, which are also optional) and emit `aiProfile: <profile>` next to `aiModel` only when it is not `None`. No placeholder value is ever written
- [ ] Thread `profile` through both writers that call it (the success writer near line 573 and the provider-failure writer near line 967) as an optional parameter
- [ ] Find every caller of those two writers with `grep -rn` and pass the profile that caller has already resolved: the pipeline review action (Task 12) and `sq review` / `sq review pr`, which resolve a profile through `resolve_review_profile`. A caller that genuinely has none at that point (for example a failure raised before resolution) passes nothing and the key is omitted
  - [ ] List in the commit body which callers pass a profile and which do not
- [ ] Tests (`tests/review/`): success artifact and failure artifact each contain `aiProfile` when a profile is passed and contain no `aiProfile` line when it is not; the pipeline review action's artifact carries the resolved profile; existing frontmatter readers (metrology, findings parsing) parse an artifact that has the extra key and one that lacks it
  - [ ] Success: tests pass; existing persistence tests pass unchanged except where they assert exact frontmatter text
- [ ] Run `cf validate frontmatter` on a generated review artifact (from a test's temporary directory)
  - [ ] Success: it accepts the extra key
- [ ] Commit: `feat: record aiProfile in review artifact frontmatter`

---

## Part D — D3, D1, D2, D7: copy, init, list color

## Task 14 — `write_new_file` helper (D3)

- [ ] Create the helper in a small shared module under `src/squadron/` (choose the location by checking where other file-writing utilities live; one module, no new package): `write_new_file(path, content, *, force) -> Path`
- [ ] Without `force`: create parent directories, then open in exclusive-create mode (`x`). If the path exists, raise `FileExistsError` naming the path. If the write fails after the create, unlink the partial file and re-raise
- [ ] With `force`: create parent directories, write to a temporary file in the same directory, then `os.replace` onto the target. A failed write leaves the existing target untouched and removes the temporary file
- [ ] Accepts `bytes` or `str` content as the callers need (copy writes bytes, init writes text); pick one signature and keep it. Do not widen it speculatively
- [ ] Tests (`tmp_path`):
  - [ ] Creates missing parent directories and returns the path
  - [ ] Existing target without `force` raises `FileExistsError` naming the path; content unchanged
  - [ ] `force` replaces the content
  - [ ] Write failure after create without `force` leaves no partial file (monkeypatch the write to raise `OSError`)
  - [ ] Write failure with `force` leaves the original content intact and no temp file
  - [ ] Race: two calls on the same path without `force`; exactly one succeeds
  - [ ] Success: tests pass
- [ ] Commit: `feat: add write_new_file exclusive-create helper`

## Task 15 — Loader exposes the copy target directories (D1)

- [ ] In `pipeline/loader.py`, add one public function returning the target directory for a scope (user or project), built from `_user_dir()` and `_PROJECT_PIPELINES_REL`. The project directory is `<project root>/project-documents/user/pipelines/`; find how `_search_dirs` obtains the project root and reuse that, do not recompute it
  - [ ] Use an enum for the scope (user, project); no string comparison
- [ ] Tests (`tests/pipeline/test_loader.py`): with a temporary home and cwd, each scope returns the same directory `_search_dirs` searches for that source
  - [ ] Success: tests pass
- [ ] Commit: `refactor: expose pipeline target directories from the loader`

## Task 16 — `sq pipelines copy` (D1)

- [ ] In `cli/commands/pipelines.py`, add `copy` with arguments `name`, optional `new_name`, and options `--project`, `--force`
- [ ] Resolve the source with `resolve_pipeline(name)`; an unknown name surfaces its existing error, exit 1 (as `show` does)
- [ ] Read the source as raw bytes (`OSError` → ERROR log with the path, one-line `Error:` message, exit 1; same handling as `show`)
- [ ] Target is `<scope directory>/<new_name or name>.yaml`. Refuse when the source path equals the target path (one-line error, exit 1)
- [ ] Write with `write_new_file(..., force=force)`. `FileExistsError` → one-line message naming the path, exit 1. `OSError` → ERROR log with the path, one-line message, exit 1
- [ ] Output: the written path on stdout. When no `new_name` was given, a notice to stderr that the copy now shadows the original's source
- [ ] Tests (`tests/cli/test_pipelines_command.py`, temporary home and project dirs):
  - [ ] Copy of a built-in writes identical bytes to the user directory; stdout is exactly the path; stderr has the shadow notice; `# source:` / `# path:` header lines are absent
  - [ ] `<new_name>` copy writes `<new_name>.yaml` and prints no shadow notice
  - [ ] `--project` writes under `project-documents/user/pipelines/`, and the built-in still resolves for the original name
  - [ ] Second copy without `--force` exits 1 and leaves the file unchanged; with `--force` it replaces it
  - [ ] Copying a user pipeline onto its own file is refused
  - [ ] Unknown name: exit 1 with `resolve_pipeline`'s message
  - [ ] Unreadable source and source removed between resolve and read: exit 1, ERROR log record with the path
  - [ ] Write `OSError`: exit 1, ERROR log record with the path; partial file absent
  - [ ] After a same-name copy, `load_pipeline(name)` loads the copy
  - [ ] Success: tests pass
- [ ] Commit: `feat: add sq pipelines copy`

## Task 17 — `list` marks shadowing pipelines (D1)

- [ ] In `discover_pipelines` / its result type, carry what a row needs to say it shadows another source: for each winning pipeline, the source it shadows, if any. Add the field to the existing listing type rather than a parallel structure
- [ ] In `render_pipeline_listing` (`cli/run_views.py`), print `shadows <source>` on a shadowing row
- [ ] Tests (`tests/pipeline/test_loader.py`, `tests/cli/test_pipelines_command.py`): a user copy of a built-in is listed once under user with `shadows built-in`; a non-shadowing pipeline has no marker; a project pipeline shadowing a user pipeline names `user`
  - [ ] Success: tests pass; existing listing tests pass unchanged except where they assert exact text
- [ ] Commit: `feat: mark shadowing pipelines in sq pipelines list`

## Task 18 — Starter text builder for `models init` (D2)

- [ ] Add one module-level function in `cli/commands/models.py` (or a small sibling module if that file would pass ~300 lines) that takes the built-in `data/models.toml` text and returns the starter text
  - [ ] Reference block: the file's leading comment block, meaning the lines from line 1 up to the first line that does not start with `#` (a blank line ends it). No edit to `data/models.toml`; D2 defines the reference this way
  - [ ] Starter = a short header, the reference block, then one commented-out example alias and one commented-out `effort` variant, using placeholder names `my-alias` and `provider/model-id`. Every line is a comment, so the file defines nothing
  - [ ] An empty reference block raises an error naming the built-in file; no starter is built without the reference
- [ ] Tests (`tests/cli/test_models.py`):
  - [ ] The starter parses with `tomllib` and defines no aliases
  - [ ] The real built-in file yields a non-empty reference block that contains every field name the alias loader accepts (derive the field list from the loader's accepted keys, not a second literal list). This is the D2 guard against a reworded or split header silently producing a truncated starter
  - [ ] Text that starts with a blank line or with a non-comment line raises the empty-block error
  - [ ] Success: tests pass
- [ ] Commit: `feat: build commented models.toml starter from the built-in reference`

## Task 19 — `sq models init` command (D2)

- [ ] In `cli/commands/models.py`, add `init` with option `--force`. It reads the built-in `data/models.toml` at write time, builds the starter with Task 18's function, and writes it to `models_toml_path()` with `write_new_file(..., force=force)`. Print the written path
  - [ ] Unreadable built-in file → ERROR log with the path, one-line message, exit 1
  - [ ] `FileExistsError` and `OSError` handling is the same as Task 16
- [ ] Tests (`tests/cli/test_models.py`, temporary home):
  - [ ] `sq models init` writes the starter at the temporary home's `models_toml_path()`; the file parses as TOML and defines no aliases
  - [ ] Second run without `--force` exits 1 with the path in the message; `--force` rewrites
  - [ ] Unreadable built-in file: exit 1, ERROR log record with the path
  - [ ] Write `OSError`: exit 1, ERROR log record, no partial file
  - [ ] Success: tests pass
- [ ] Commit: `feat: add sq models init`

## Task 20 — Doctor and setup point to `models init` (D2)

- [ ] In `cli/commands/doctor_checks.py` `check_models_toml`, change only the missing-file detail to `using defaults (no file at <path>); sq models init writes a commented starter`. Status stays OK
- [ ] Check `cli/commands/setup*.py` for a `models.toml` row or its own wording; if it renders `check_models_toml`'s detail, nothing more to change; if it has separate text, apply the same wording
- [ ] Tests (`tests/cli/test_doctor_checks.py`, and the setup test if setup has its own text): missing file → status OK with the new detail; existing-file and malformed cases unchanged
  - [ ] Success: tests pass
- [ ] Commit: `feat: point doctor models.toml row at sq models init`

## Task 21 — Colored `sq pipelines list` (D7)

- [ ] In `render_pipeline_listing`, print names bold, descriptions dim, and the `shadows <source>` marker yellow, using Rich markup through the existing rendering (not a table). Group headers keep their current style
  - [ ] Escape every interpolated name, description and source with `escape` (Part A rule; the guard test covers exception text only, so check these by hand)
- [ ] Tests: render to a recording `Console(force_terminal=True)` or capture styled output and assert the bold, dim and yellow spans appear on a shadowing row; plain-text output of existing listing tests is unchanged
  - [ ] Success: tests pass
- [ ] Commit: `style: color sq pipelines list`

---

## Part E — Validation and close-out

## Task 22 — Full validation and walkthrough

- [ ] Create the baseline first, before any test or walkthrough command: `marker=$(mktemp)` and `ls -la ~/.config/squadron > "$marker.before" 2>&1` (the directory may not exist; that output is the baseline). Use the same shell session for every later step in this task
- [ ] Run `ruff format`, `ruff check`, `pyright`, and the full test suite once each
  - [ ] Success: all clean; zero pyright errors; full suite passes
- [ ] Run the design's Verification Walkthrough in a scratch project with `HOME` pointed at a temporary directory, and record the outcome of each line
  - [ ] Success: path printed with shadow notice on stderr; list marks the shadowing copy; second copy refused; `models init` output parses as TOML; `sq doctor` models.toml row reads `loaded from <path>`
- [ ] After the suite and the walkthrough, confirm the real `~/.config/squadron` was not modified: `find ~/.config/squadron -newer "$marker" 2>/dev/null` prints nothing, and `ls -la ~/.config/squadron` matches `"$marker.before"`
  - [ ] Success: both checks show no change; if either shows one, find the test or step that wrote there and fix it before committing
- [ ] Commit any fixes found: `fix: <summary>` (skip if none)

## Task 23 — Close-out

- [ ] Delegate checking off this task file to the `task-checker` agent; mark any dropped item `[x]` with a note before closing
- [ ] Mark slice 940 complete in the slice design (`status`) and in the slice plan entry if one exists
- [ ] Write the DEVLOG entry at repo-root `DEVLOG.md` (newest first), following Session State Summary in `prompt.ai-project.system.md`
- [ ] Commit: `docs: complete slice 940 tasks and devlog`
  - [ ] Success: `git status` clean; branch holds all commits; no merge performed
