---
docType: slice-design
slice: everyday-cli-fixes
project: squadron
parent: user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: []
interfaces: []
dateCreated: 20261009
dateUpdated: 20261009
status: not_started
---

# Slice Design: Everyday CLI Fixes

## Overview

Five small, independent fixes to commands users run every day. They are grouped on purpose: each is too small to justify its own design, review and task cycle (see #194).

These fall under the 900 initiative's "developer experience" and "configuration improvements" scope. Two of them are new commands (`sq pipelines copy` and `sq models init`), but each is a thin convenience over files and paths squadron already owns. Neither is a feature area. Each fix is committed on its own and can be reverted on its own, so if one stalls the others still ship. The list color (D7) is a sixth, cosmetic change that rides along with D1.

1. **`sq pipelines copy`** ([#198](https://github.com/ecorkran/squadron/issues/198)). To customize a pipeline today, you run `show`, paste the output into a new file, and find the right directory by hand.
2. **Starter `models.toml`** ([#197](https://github.com/ecorkran/squadron/issues/197)). The only format reference for model aliases is the built-in `data/models.toml`, which sits inside the installed package at a path that depends on platform and install method.
3. **Path runs record the path as the name** ([#169](https://github.com/ecorkran/squadron/issues/169)). `sq run path/to/foo.yaml` stores the lowercased path as the run's pipeline name ([run.py:239](../../../src/squadron/cli/commands/run.py#L239), [run.py:672](../../../src/squadron/cli/commands/run.py#L672)). Listing or resuming by name doesn't find the run, and lowercasing corrupts case-sensitive paths.
4. **Rich swallows bracketed error text** ([#177](https://github.com/ecorkran/squadron/issues/177)). 77 CLI print sites interpolate exception text into Rich markup without escaping it, so `[...]` in a message silently disappears.
5. **`-v` doesn't name the review profile** ([#193](https://github.com/ecorkran/squadron/issues/193)). A pipeline review step's verbose line shows template and model but not the profile. The profile is resolved inside the review action ([review.py:200](../../../src/squadron/pipeline/actions/review.py#L200)), after the executor has written that line. Review artifacts don't record the profile either.

## Value

- Customizing a built-in pipeline takes one command.
- New users get a commented `models.toml` that documents every field, in a known location.
- Runs started from a file can be listed and resumed by name.
- Error messages print in full.
- `sq run -v` and the review artifact show exactly which profile a review ran on.

## Technical Scope

**Included**
- `sq pipelines copy <name> [<new-name>] [--project] [--force]` (D1).
- `sq models init [--force]`, plus a pointer to it in the doctor/setup `models.toml` row (D2).
- One shared create-file helper used by both commands (D3).
- Run state records the pipeline name and, for path runs, the source path. Resume reloads from that path (D4).
- Escape exception and user-supplied text at every CLI print site, plus a guard test (D5).
- The review action logs its resolved profile, and review artifacts gain `aiProfile` (D6).
- Color in `sq pipelines list` (D7).

**Excluded**
- `sq review <file>` inferring slice and name from the file name (#142). It's useful, but used less often.
- Previewing `each`/`loop` steps in `--dry-run` and `--prompt-only` (#149, #145). These are larger and get their own slice.
- `--<param>` flags on `sq run` (#56). `-p key=value` already covers it.
- `sq review --max` (slice 941).

## Dependencies

### Prerequisites
None. The slice uses existing modules: `pipeline/loader.py` (`resolve_pipeline`, `_user_dir`, `_PROJECT_PIPELINES_REL`), `models/aliases.py` (`models_toml_path`), `review/profile_resolution.py`, and `pipeline/state.py`.

### Interfaces Required
None new.

## Technical Decisions

### D1: `sq pipelines copy`

- **Source:** the file `resolve_pipeline(<name>)` returns, the same one `show` prints. The copy is the raw file bytes. `show`'s `# source:` and `# path:` header lines are not written.
- **Target:** the user pipelines directory (`loader._user_dir()`) by default, or `<project>/project-documents/user/pipelines/` with `--project`. The file is named `<new-name or name>.yaml`. The loader owns both directory paths, and copy uses them rather than recomputing them.
- **Same-name copies:** if no `<new-name>` is given, the copy shadows the original. User and project pipelines both win over built-ins today, through `load_pipeline`'s search order. The command prints a line saying the copy now shadows the original's source.
- **Refusals:** copying a pipeline onto its own file (source path equals target path) is refused. A target that already exists is refused unless `--force` is passed (D3).
- **Output:** the written path on stdout, so `$EDITOR "$(sq pipelines copy slices-plan)"` works. The shadow notice goes to stderr.
- **`list`:** shows only the pipeline that wins for each name. When a user or project pipeline shadows another, its row is marked `shadows <source>`. Without that mark, the built-in silently drops out of the listing.

### D2: `sq models init`

- Writes `models_toml_path()`. It refuses if the file exists, unless `--force` is passed (D3).
- **Content:** a short header, then the field reference, then one example alias and one `effort` variant. Every line is commented out, so the file defines nothing.
- **One source for the field reference:** the reference is the leading comment block of the built-in `data/models.toml`. `init` reads that block at write time, so the reference lives in one place. A test asserts the block is non-empty and contains each field name the alias loader accepts. That way a reworded header can't silently produce an empty starter.
- **Example values:** the example alias uses names that are obviously placeholders (`my-alias`, `provider/model-id`). The starter is read by people, not filled in by a model, so the hallucination-trap rule doesn't apply. Placeholder names still keep anyone from mistaking the example for a real alias.
- **Doctor and setup:** `check_models_toml` keeps its status. A missing file is still OK, since the built-in defaults work. When the file is missing, the detail becomes `using defaults (no file at <path>); sq models init writes a commented starter`. A WARN would nag every user who never wants custom aliases.

### D3: One create-file helper

`write_new_file(path, content, *, force) -> Path` creates parent directories, then opens the target in exclusive-create mode (`x`). Because the existence check and the create are a single operation, two concurrent runs can't both win. With `force`, it writes to a temporary file in the same directory and replaces the target, so a failed write never leaves a truncated file. Without `force`, a write that fails after the create unlinks the partial file before re-raising. It raises `FileExistsError` naming the path. Both commands catch that error and turn it into a one-line message and exit code 1. They also catch `OSError` on write, log it at ERROR with the path, and exit 1.

### D4: Run names and source paths

- `init_run` receives `pipeline_identity(<loaded file path>)` (the file stem, lowercased, matching what lookup uses), not the CLI argument.
- When the argument was a file path, run state also stores the absolute `pipeline_path`. This is a new optional field. Old state files without it load unchanged.
- Resume, `--status` and item resume call `load_pipeline(state.pipeline_path or state.pipeline)`. The path is never lowercased.
- `pipeline_path` is optional, so `schema_version` stays 5. Old state files load unchanged. `RunState` ignores unknown fields (pydantic's default), so an older squadron reading a new state file ignores the path and loads by name. Runs already recorded under a lowercased path keep that name. They are not migrated: they still resume through the path itself, as they do today.
- A recorded path that no longer exists fails with an error naming the path, rather than falling back to a same-named pipeline. A silent fallback could run a different file.

### D5: Escaping CLI output

- Every CLI print that interpolates exception text or user-supplied text into Rich markup passes it through `rich.markup.escape`. The issue's grep finds 77 sites. Five modules already import `escape`.
- **Guard test:** an AST check over `src/squadron/cli`. It finds every f-string passed to a Rich print (`rprint`, `console.print`, `Console(...).print`) and flags any interpolated expression that refers to a name bound by an enclosing `except ... as <name>` and isn't wrapped in `escape(...)`. The variable's name doesn't matter, and multi-line calls are handled. Its limit: it can't tell user-supplied text that never passed through an exception. Those sites get escaped as part of the sweep, but the guard won't catch a future one. A failure names the file and line.
- `typer.echo` doesn't parse markup and is left alone.

### D6: The review profile is visible

- After `resolve_review_profile` returns, the review action logs at INFO `review: step <step> profile=<profile> model=<model>`. `-v` sets the pipeline logger to INFO ([run.py:1050](../../../src/squadron/cli/commands/run.py#L1050)), so the line appears under `-v`. The executor's pre-action label is unchanged. The action is where the profile is actually known.
- Review artifact frontmatter gains `aiProfile: <profile>`, written next to `aiModel` ([persistence.py:443](../../../src/squadron/review/persistence.py#L443)). Success and failure artifacts both build their frontmatter in `_review_frontmatter_lines` ([persistence.py:373](../../../src/squadron/review/persistence.py#L373)), so one change covers both. Squadron's readers of review frontmatter (metrology, findings parsing) look up the keys they need. `cf validate frontmatter` accepts the extra key (checked 20261009 against a probe review).

### D7: Colored `pipelines list`

Pipeline names are printed bold, descriptions dim, and the D1 `shadows <source>` marker yellow. Group headers keep their current style. Formatting goes through the existing Rich rendering in `render_pipeline_listing`. It is not a table.

### D8: Failure modes

| Path | Failure | Observable signal |
|---|---|---|
| copy / init write | target exists | one-line error naming the path, exit 1 |
| copy / init write | permission or disk error | ERROR log with path, one-line error, exit 1 |
| copy | unknown pipeline name | `resolve_pipeline`'s existing error, exit 1 |
| copy | source unreadable, or gone between resolve and read | ERROR log with path, one-line error, exit 1 (the same handling `show` has) |
| copy / init | write fails after create | partial file removed, ERROR log, exit 1 |
| init | built-in `data/models.toml` unreadable | ERROR log with path, one-line error, exit 1 |
| init | built-in reference block empty | test failure (D2) |
| resume | recorded `pipeline_path` missing | error naming the path, exit 1 |
| resume | recorded `pipeline_path` exists but fails to load or validate | `load_pipeline`'s existing error, naming the path, exit 1 |

Each row has a test that asserts its signal: the exit code, plus the message or log record.

## Success Criteria

### Functional Requirements
- `sq pipelines copy slices-plan` writes `~/.config/squadron/pipelines/slices-plan.yaml` with the same bytes as the built-in. It prints the path and a shadow notice, and `sq run slices-plan` then loads the copy.
- `sq pipelines copy slices-plan mine --project` writes `project-documents/user/pipelines/mine.yaml`, and `slices-plan` still resolves to the built-in.
- A second copy without `--force` fails and leaves the file unchanged.
- `sq pipelines list` marks a shadowing copy.
- `sq models init` writes a file that parses as TOML, defines no aliases, and documents every field. A second run without `--force` fails.
- `sq run ./x/Foo.yaml` records pipeline `foo` plus the absolute path, and `--resume` reloads the same file.
- An exception message containing `[codex]` prints intact on the CLI.
- `sq run -v` on a review step prints the profile. The review artifact has `aiProfile`.

### Technical Requirements
- ruff format, ruff check and pyright are clean. The full suite passes.
- The D5 guard test passes, and fails if an unescaped site is added.
- A state file written before this slice (no `pipeline_path`) loads and resumes unchanged (test).
- Tests use a temporary home and project directory and never touch the real `~/.config/squadron`.

## Verification Walkthrough

Run in a scratch project with `HOME` pointed at a temporary directory:

```bash
sq pipelines copy slices-plan            # path printed, shadow notice on stderr
sq pipelines list                        # slices-plan under user, marked as shadowing built-in
sq pipelines copy slices-plan            # refused: exists
sq models init && python -c "import tomllib,sys;tomllib.load(open(sys.argv[1],'rb'))" ~/.config/squadron/models.toml
sq doctor                                # models.toml row: loaded from <path>
```

## Implementation Notes

The fixes are independent. Suggested order is cheapest first: D5, D4, D6, then D3 → D1 → D2, then D7. Commit each one separately with its own semantic commit.
