---
docType: slice-design
slice: pipeline-run-summary-persistence-and-restore
project: squadron
parent: 140-slices.pipeline-foundation.md
dependencies: [161-summary-step-with-emit-destinations, 162-sq-summary-clipboard-summary-for-manual-context-reset]
interfaces: []
dateCreated: 20260410
dateUpdated: 20260410
status: draft
---

# Slice Design: Pipeline Run Summary Persistence and Restore

## Overview

Close the "run a pipeline in CLI terminal, restore context in VS Code"
workflow gap. When a pipeline's `summary` step uses `emit: [file]`
without an explicit path, the summary is written to a conventional
location keyed by project and pipeline name. A new `--restore` mode on
`/sq:summary` reads the most recent summary for the current project
and seeds it into the active conversation — no run-id lookup required.

Three changes, all small:

1. **Default file path for `emit: [file]`** — when the `file` emit
   destination has no explicit path argument, write to
   `~/.config/squadron/runs/summaries/{project}-{pipeline}.md`.
   Overwrites on each run (latest-only snapshot).

2. **`/sq:summary --restore`** — reads the latest summary file for the
   current project from the conventional location and outputs it as a
   context-seeding block. No run-id needed.

3. **Prompt-only `run.md` alignment** — the summary action handler in
   `run.md` writes to the same conventional path via Bash, so
   prompt-only pipelines produce the same persistent artifact as SDK
   pipelines.

## Motivation

Today, a user who runs a multi-phase pipeline in the terminal (CLI or
SDK mode) ends up with a summary that lives only on the clipboard or
in stdout. If they switch to VS Code, open a new conversation, or
simply use the clipboard for something else, the summary is gone. The
pipeline's run state JSON contains summary text buried in
`action_results`, but it's keyed by run-id — which users don't
remember and shouldn't need to.

The desired workflow:

1. Run `sq run P4 163` in the terminal (produces summary at end).
2. Open VS Code, start a new conversation.
3. Type `/sq:summary --restore` — context is seeded from the pipeline's
   last summary. No clipboard gymnastics, no run-id lookup.

## Non-Goals

- **No run-id-based restore.** The whole point is that users shouldn't
  need run-ids. The conventional `{project}-{pipeline}.md` path gives
  "latest run" semantics for free.
- **No history / multiple versions.** Each run overwrites the previous
  summary file. The run state JSON is the historical record if needed.
- **No new emit destination type.** This extends the existing `file`
  emit behavior with a default path, not a new `EmitKind`.
- **No aggregation across pipeline steps.** The summary file contains
  whatever the pipeline's `summary` step produced. If the pipeline has
  multiple summary steps, the last one wins (overwrite semantics).
- **No changes to the `RunState` model or schema.**

## Architecture

### Default file path resolution

The `file` emit destination in `emit.py` currently requires an
explicit path argument (`file: /path/to/output.md`). When the path
argument is `None` (i.e., the pipeline YAML says `emit: [file]` with
no path), the emit function will resolve a default path using:

- **Project name** — from `ActionContext`. The pipeline executor
  already has access to context params; the project name needs to be
  threaded through. Resolved from CF via CWD at pipeline init time
  (same `gather_cf_params` from `summary_render.py`).
- **Pipeline name** — from `ActionContext.pipeline_name` (already
  available).

Convention: `~/.config/squadron/runs/summaries/{project}-{pipeline}.md`

```
~/.config/squadron/runs/
  summaries/
    squadron-P4.md          ← latest P4 run for project "squadron"
    squadron-P5.md          ← latest P5 run
    squadron-slice.md       ← latest slice lifecycle run
    other-project-P4.md     ← different project
```

The `summaries/` subdirectory keeps these files separate from the
run state JSON files in the parent `runs/` directory.

### Component flow: SDK pipeline writes summary to file

```
Pipeline step: summary
  emit: [clipboard, file]       ← no explicit path on file
         │
         ▼
  _emit_file(text, dest, ctx)   ← dest.arg is None
         │
         ▼
  resolve default path:
    project = ctx.params.get("_project") or "unknown"
    pipeline = ctx.pipeline_name or "unknown"
    path = ~/.config/squadron/runs/summaries/{project}-{pipeline}.md
         │
         ▼
  write file (existing atomic write logic)
```

### Component flow: prompt-only pipeline writes summary to file

```
run.md summary handler
  │
  ▼
  Generate summary text (in-session, per resolved_instructions)
  │
  ▼
  Write to conventional path via Bash:
    SUMM_DIR=~/.config/squadron/runs/summaries
    mkdir -p "$SUMM_DIR"
    cat << '__SQ_END__' > "$SUMM_DIR/{project}-{pipeline}.md"
    SUMMARY_TEXT
    __SQ_END__
  │
  ▼
  Also copy to clipboard (per existing clipboard handling)
```

The prompt-only handler needs the project name and pipeline name. The
`run_id` is available (it's tracked throughout the run), and the
pipeline name can be extracted from it. The project name is resolvable
via a one-shot `cf status` call or passed as a pipeline param.

### Component flow: restore

```
User types /sq:summary --restore
         │
         ▼
commands/sq/summary.md
  detects --restore in $ARGUMENTS
  branches to restore flow:
         │
         ▼
  Bash: sq _summary-instructions --restore [--cwd .]
         │
         ▼
  _summary-instructions CLI:
    --restore mode:
    1. Resolve project name via gather_cf_params(cwd)
    2. List ~/.config/squadron/runs/summaries/{project}-*.md
    3. If exactly one: print its contents to stdout
    4. If multiple: print a selection list to stderr,
       print the most recently modified file's contents to stdout
    5. If none: print error to stderr, exit 1
         │
         ▼
  summary.md skill:
    Outputs the summary text as context for the conversation
    (does NOT copy to clipboard — this is a restore, not a generate)
    Prints confirmation: "Context restored from {filename} (N chars)."
```

### Code changes

**Modified: `src/squadron/pipeline/emit.py`**

In `_emit_file()`, when `dest.arg` is `None`, resolve the default
path:

```python
async def _emit_file(
    text: str, dest: EmitDestination, ctx: ActionContext
) -> EmitResult:
    if dest.arg is not None:
        path = Path(dest.arg)
        if not path.is_absolute():
            path = Path(ctx.cwd) / path
    else:
        # Default: conventional summary location
        project = ctx.params.get("_project") or "unknown"
        pipeline = ctx.pipeline_name or "unknown"
        summaries_dir = _DEFAULT_SUMMARIES_DIR  # ~/.config/squadron/runs/summaries
        path = summaries_dir / f"{project}-{pipeline}.md"
    # ... existing write logic unchanged
```

New module-level constant:

```python
_DEFAULT_SUMMARIES_DIR = Path.home() / ".config" / "squadron" / "runs" / "summaries"
```

**Modified: `src/squadron/pipeline/executor.py`** (or pipeline init)

Thread the project name into `ActionContext.params` as `_project`
during pipeline initialization. The underscore prefix signals it's
an internal/system param, not user-supplied. Resolved via
`gather_cf_params(cwd)` — same helper used by `summary_render.py`.
If CF is unavailable, falls back to the git repo name or `"unknown"`.

**Modified: `src/squadron/cli/commands/summary_instructions.py`**

Add `--restore` flag:

```python
def summary_instructions(
    template: str = typer.Argument(None, ...),
    cwd: str = typer.Option(".", "--cwd", hidden=True),
    suffix: bool = typer.Option(False, "--suffix", hidden=True),
    restore: bool = typer.Option(False, "--restore", hidden=True),
) -> None:
    if restore:
        _handle_restore(cwd)
        return
    # ... existing template logic unchanged
```

New helper in the same file:

```python
def _handle_restore(cwd: str) -> None:
    """Find and print the latest summary file for the current project."""
    params = gather_cf_params(cwd)
    project = params.get("project")
    if not project:
        print("Error: cannot resolve project name from CWD.", file=sys.stderr)
        raise typer.Exit(code=1)

    summaries_dir = Path.home() / ".config" / "squadron" / "runs" / "summaries"
    matches = sorted(
        summaries_dir.glob(f"{project}-*.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    if not matches:
        print(f"Error: no summary files found for project '{project}'.", file=sys.stderr)
        raise typer.Exit(code=1)

    if len(matches) > 1:
        print(f"Found {len(matches)} summaries for '{project}':", file=sys.stderr)
        for m in matches:
            pipeline = m.stem.removeprefix(f"{project}-")
            print(f"  {pipeline}  ({m.name})", file=sys.stderr)
        print(f"Using most recent: {matches[0].name}", file=sys.stderr)

    print(matches[0].read_text(encoding="utf-8"))
```

**Modified: `commands/sq/summary.md`**

Add `--restore` branch to the argument parsing section:

```markdown
## Input parsing

If `$ARGUMENTS` starts with `--restore`:
  - Run restore flow (Step R1-R2 below)
  - Skip the normal summary generation flow entirely

Otherwise: existing behavior (template name parsing, Steps 1-4).

## Step R1: Get restore content

Run via Bash:
    sq _summary-instructions --restore

If non-zero exit, show error and stop.

## Step R2: Seed context

Output the returned summary text directly as a context block.
Do NOT copy to clipboard. Print confirmation:
    Context restored from {filename} (N chars).
```

**Modified: `commands/sq/run.md`**

Extend the `summary` action handler to write the summary to the
conventional file path via Bash, in addition to the existing clipboard
handling. The project name and pipeline name can be resolved from the
run context (the run_id contains the pipeline name slug, and the
project name is resolvable via `cf status --json` or similar).

## Data Flow

### Happy path: SDK pipeline writes summary, user restores in VS Code

1. User runs `sq run P4 163` in terminal.
2. Pipeline reaches `summary` step with `emit: [clipboard, file]`.
3. SDK executor runs `SummaryAction.execute()`.
4. `_emit_file()` sees `dest.arg is None`, resolves to
   `~/.config/squadron/runs/summaries/squadron-P4.md`.
5. Summary written to file and copied to clipboard.
6. User opens VS Code, new conversation.
7. User types `/sq:summary --restore`.
8. Skill runs `sq _summary-instructions --restore`.
9. CLI resolves project = "squadron", finds
   `~/.config/squadron/runs/summaries/squadron-P4.md`.
10. Summary text output as context. Confirmation printed.

### Happy path: prompt-only pipeline

Same as above but step 4 happens via Bash in the `run.md` handler
instead of `_emit_file()`. The file ends up at the same path.

### Multiple pipelines for same project

User has run P4, P5, and slice pipelines. Summaries directory:

```
squadron-P4.md
squadron-P5.md
squadron-slice.md
```

`/sq:summary --restore` lists all three on stderr, uses the most
recently modified. User sees which pipeline it came from.

### No CF project (edge case)

`gather_cf_params` returns empty project. CLI prints
`Error: cannot resolve project name from CWD.` and exits 1.
Skill surfaces the error. User knows they need to be in a CF
project directory.

### No summary files (edge case)

User hasn't run any pipeline with `emit: [file]`. CLI prints
`Error: no summary files found for project 'squadron'.` and exits 1.

## Interfaces

### `sq _summary-instructions --restore` (CLI extension)

```
sq _summary-instructions --restore [--cwd PATH]
```

- `--restore` — read and print the latest summary file for the
  current project. Mutually exclusive with `--suffix` and
  template argument.
- `--cwd PATH` — project root for CF resolution. Defaults to `.`.

**Output:** summary file contents to stdout. If multiple matches,
selection info on stderr.

**Exit codes:**
- `0` — success. One summary found and printed.
- `1` — no project resolved, or no summary files found.

### `/sq:summary --restore` (skill extension)

```
/sq:summary --restore
```

Seeds the current conversation with the latest pipeline summary for
this project. No clipboard write. Prints a one-line confirmation.

### Default file emit path (internal)

When `emit: [file]` is specified without an explicit path, the file
emit destination writes to:

```
~/.config/squadron/runs/summaries/{project}-{pipeline}.md
```

Pipeline authors who want a custom path can still use
`emit: [file: path/to/output.md]` — the existing explicit-path
behavior is unchanged.

## Success Criteria

1. A pipeline with `emit: [clipboard, file]` (no explicit path) writes
   the summary to `~/.config/squadron/runs/summaries/{project}-{pipeline}.md`.
2. Running the same pipeline again overwrites the previous summary file.
3. `sq _summary-instructions --restore` in a CF project directory
   prints the latest summary file contents to stdout.
4. `sq _summary-instructions --restore` with no summary files exits 1
   with a clear error.
5. `sq _summary-instructions --restore` with multiple pipelines lists
   options on stderr and outputs the most recent.
6. `/sq:summary --restore` in VS Code seeds the conversation with the
   summary content and prints a confirmation line.
7. `/sq:summary --restore` does NOT copy to clipboard (it's a context
   seed, not a clipboard operation).
8. The existing explicit-path `emit: [file: /path/to/x.md]` behavior
   is unchanged.
9. Prompt-only pipelines (via `run.md`) write to the same conventional
   path as SDK pipelines.

## Verification Walkthrough

1. **Run a pipeline with file emit.**
   ```bash
   sq run P4 163
   ```
   Confirm `~/.config/squadron/runs/summaries/squadron-P4.md` exists
   and contains the pipeline's summary.

2. **Run the same pipeline again.**
   Confirm the file is overwritten (not appended).

3. **Direct CLI restore.**
   ```bash
   sq _summary-instructions --restore
   ```
   Confirm it prints the contents of the most recent summary file.

4. **CLI restore with no files.**
   ```bash
   rm ~/.config/squadron/runs/summaries/squadron-*.md
   sq _summary-instructions --restore
   ```
   Confirm exit code 1 and clear error message.

5. **Slash command restore in VS Code.**
   ```
   /sq:summary --restore
   ```
   Confirm conversation is seeded with summary content. No clipboard
   write. One-line confirmation printed.

6. **Prompt-only pipeline.**
   ```
   /sq:run P4 163
   ```
   After pipeline completes, confirm summary file exists at the
   conventional path.

## Cross-Slice Dependencies

- **Slice 161 (Summary Step with Emit Destinations)** — owns the
  emit registry and `_emit_file()` function. This slice modifies
  `_emit_file()` to add default path resolution.
- **Slice 162 (/sq:summary)** — owns `summary_instructions.py` and
  `commands/sq/summary.md`. This slice extends both with `--restore`.
- **`summary_render.py`** — owns `gather_cf_params()`. Reused for
  project name resolution; no changes needed.

## Implementation Notes

- The `_project` param should be set early in pipeline initialization
  (in `executor.py` or the CLI `run` command) so it's available to all
  actions, not just summary. Other actions may benefit from it later.
- The `summaries/` subdirectory is created on first write via
  `mkdir(parents=True, exist_ok=True)` — no separate initialization
  step needed.
- The pipeline name used in the filename is the raw pipeline name (e.g.
  `P4`, `slice`, `tasks`), not the run-id slug. This keeps filenames
  predictable and human-readable.

## Risks

**Low overall.** All components are small extensions of existing
machinery.

1. **Project name resolution failure.** If CF is not available or the
   user is outside a project directory, `_emit_file()` falls back to
   `"unknown"` for the project name. Files end up at
   `unknown-P4.md` — functional but not useful for restore. The
   `--restore` command requires a project name and fails clearly if
   one isn't available.

## Effort Estimate

**1/5** — three small modifications to existing files, one new
conditional branch in the skill, and a few lines in `run.md`.
