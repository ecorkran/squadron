---
name: sq-review
description: Runs a squadron review — code, slice design, task plan, architecture, pull request, or a resolve check on whether an earlier review's findings were addressed. Use when the user asks for any of these to be reviewed, or asks whether review findings were handled.
---

# sq review

Run a review using squadron.

## Input parsing

The first word the user typed after `$sq-review` is the subcommand. The remainder is passed to the
CLI unchanged.

Valid subcommands: `code`, `slice`, `tasks`, `arch`, `resolve`, `pr`

If the subcommand is missing or unrecognized, show the usage below and stop.

**Usage:**
```
$sq-review code [NUMBER | FLAGS]     — code review
$sq-review slice [NUMBER | FLAGS]    — slice design review
$sq-review tasks [NUMBER | FLAGS]    — task plan review
$sq-review arch [NUMBER | FLAGS]     — architecture review
$sq-review resolve NUMBER [TYPE]     — were a review's findings addressed?
$sq-review pr [TARGET | FLAGS]       — pull request review
```

---

## Subcommand: code

Run a code review using squadron.

If what the user typed after `$sq-review code` (the leading subcommand word removed) starts with a number (e.g., `191`, `118`), treat it as a **slice number shorthand**. Otherwise, pass the remainder directly to `sq review code`.

### Slice number shorthand

When the remainder is a bare number:

`sq review code {number} -v`

The CLI automatically:
- Resolves the slice context via `cf list slices --json`
- Defaults to `--diff main` when invoked with a number
- Saves the review to `project-documents/user/reviews/{nnn}-review.code.{slice-name}.md` with YAML frontmatter

Additional flags:
- `--json`: output and save as JSON instead of markdown
- `--no-save`: suppress the review file save
- `-v`/`-vv`: verbosity level

Show the review results. If the verdict is FAIL or CONCERNS, highlight the key findings.

### Full flag invocation

When the remainder contains flags (not a bare number), run:

`sq review code {remainder}`

Optional flags:
- `--cwd DIR`: project directory to review
- `--files PATTERN`: glob pattern to scope the review
- `--diff REF`: git ref to diff against (reviews changed files)
- `--rules PATH`: path to additional rules file
- `--rules-dir DIR`: rules directory override
- `--no-rules`: suppress all rule injection
- `--model MODEL`: model override — accepts aliases (e.g., `opus`, `gpt4o`) or full model IDs. Aliases automatically set the correct profile. Run `sq model list` for available aliases.
- `--profile PROFILE`: provider profile (e.g., `openrouter`, `openai`, `local`, `sdk`). Resolved from model alias when omitted, defaults to `sdk`.

For non-SDK providers, file contents and git diffs are automatically injected into the prompt so models can review actual content.
- `-v`/`-vv`: verbosity level
- `--json`, `--no-save`

Example: `sq review code --diff main` or `sq review code --files "src/**/*.py"`

Show the review results. If the verdict is FAIL or CONCERNS, highlight the key findings.

---

## Subcommand: slice

Run a slice design review using squadron.

If what the user typed after `$sq-review slice` (the leading subcommand word removed) starts with a number (e.g., `191`, `118`), treat it as a **slice number shorthand** and perform a holistic review. Otherwise, pass the remainder directly to `sq review slice`.

### Slice number shorthand (holistic review)

When the remainder is a bare number:

`sq review slice {number} -v`

The CLI automatically:
- Resolves the slice design file via `cf list slices --json`
- Resolves the architecture document via `cf get --json`
- Runs a holistic review: slice design vs. architecture doc + slice plan entry
- Saves the review to `project-documents/user/reviews/{nnn}-review.slice.{slice-name}.md` with YAML frontmatter

This is a **holistic review** answering: "does this slice design effectively cover what it's supposed to?" It checks against both the architecture document and the slice plan entry.

Additional flags:
- `--json`: output and save as JSON instead of markdown
- `--no-save`: suppress the review file save
- `-v`/`-vv`: verbosity level

Show the review results. If the verdict is FAIL or CONCERNS, highlight the key findings.

### Full path invocation

When the remainder contains paths (not a bare number), run:

`sq review slice {remainder}`

Required arguments:
- Positional: path to the document to review
- `--against PATH`: architecture or context document to review against

Optional: `--cwd DIR`, `--model MODEL`, `--profile PROFILE`, `-v`/`-vv` for verbosity, `--json`, `--no-save`.

The `--model` flag accepts aliases (e.g., `opus`, `sonnet`, `gpt4o`) or full model IDs. Aliases automatically set the correct profile. Run `sq model list` to see available aliases. Users can add custom aliases in `~/.config/squadron/models.toml`.

The `--profile` flag routes the review through a specific provider (e.g., `openrouter`, `openai`, `local`, `sdk`). When omitted, the profile is resolved from the model alias or defaults to `sdk`.

Example: `sq review slice slices/105-slice.md --against architecture/100-arch.md`

Show the review results. If the verdict is FAIL or CONCERNS, highlight the key findings.

---

## Subcommand: tasks

Run a task plan review using squadron.

If what the user typed after `$sq-review tasks` (the leading subcommand word removed) starts with a number (e.g., `191`, `118`), treat it as a **slice number shorthand**. Otherwise, pass the remainder directly to `sq review tasks`.

### Slice number shorthand

When the remainder is a bare number:

`sq review tasks {number} -v`

The CLI automatically:
- Resolves the task file and slice design via `cf list slices --json` / `cf list tasks --json`
- Runs the review
- Saves the review to `project-documents/user/reviews/{nnn}-review.tasks.{slice-name}.md` with YAML frontmatter

Additional flags:
- `--json`: output and save as JSON instead of markdown
- `--no-save`: suppress the review file save
- `-v`/`-vv`: verbosity level

Show the review results. If the verdict is FAIL or CONCERNS, highlight the key findings.

### Full path invocation

When the remainder contains paths (not a bare number), run:

`sq review tasks {remainder}`

Required arguments:
- Positional: path to the task breakdown file
- `--against PATH`: parent slice design to review against

Optional: `--cwd DIR`, `--model MODEL`, `--profile PROFILE`, `-v`/`-vv` for verbosity, `--json`, `--no-save`.

The `--model` flag accepts aliases (e.g., `opus`, `sonnet`, `gpt4o`) or full model IDs. Aliases automatically set the correct profile. Run `sq model list` to see available aliases. Users can add custom aliases in `~/.config/squadron/models.toml`.

The `--profile` flag routes the review through a specific provider (e.g., `openrouter`, `openai`, `local`, `sdk`). When omitted, the profile is resolved from the model alias or defaults to `sdk`.

Example: `sq review tasks tasks/105-tasks.md --against slices/105-slice.md`

Show the review results. If the verdict is FAIL or CONCERNS, highlight the key findings.

---

## Subcommand: arch

Run an architecture document review using squadron.

If what the user typed after `$sq-review arch` (the leading subcommand word removed) starts with a number (e.g., `140`), treat it as an **initiative index shorthand**. Otherwise, pass the remainder directly to `sq review arch`.

### Initiative index shorthand

When the remainder is a bare number:

`sq review arch {number} -v`

The CLI resolves the architecture document by initiative index and saves the review to `project-documents/user/reviews/{nnn}-review.arch.{initiative-name}.md` with YAML frontmatter.

Additional flags:
- `--json`: output and save as JSON instead of markdown
- `--no-save`: suppress the review file save
- `-v`/`-vv`: verbosity level

Show the review results. If the verdict is FAIL or CONCERNS, highlight the key findings.

### Full path invocation

When the remainder contains a path (not a bare number), run:

`sq review arch {remainder}`

Required arguments:
- Positional: path to the architecture document to review

Optional flags:
- `--cwd DIR`: working directory override
- `--model MODEL`: model override (e.g., `opus`, `sonnet`) or full model ID
- `--profile PROFILE`: provider profile (e.g., `openrouter`, `openai`, `local`, `sdk`)
- `-v`/`-vv`: verbosity level
- `--json`: output and save as JSON instead of markdown
- `--no-save`: suppress review file save
- `--rules-dir DIR`: rules directory override

Note: `sq review arch` does not support `--against`. The review is self-contained against the architecture document itself.

Example: `sq review arch project-documents/user/architecture/140-slices.pipeline-foundation.md`

Show the review results. If the verdict is FAIL or CONCERNS, highlight the key findings.

---

## Subcommand: resolve

Record whether a prior review's findings were addressed by the work done since.

Pass what the user typed after `$sq-review resolve` (the leading subcommand word removed) directly to:

`sq review resolve {remainder}`

Required arguments:
- Positional: the slice number whose review to resolve (e.g. `305`)

Optional arguments:
- Positional: the review type (`code`, `slice`, `tasks`, `arch`). Omit it when the index has exactly one review; when several exist the CLI errors and lists them rather than guessing.

Optional flags:
- `--cwd DIR`: project directory override
- `--model MODEL`: judge model override — accepts aliases (e.g. `opus`) or full model IDs
- `--profile PROFILE`: provider profile (e.g. `openrouter`, `openai`, `local`, `sdk`)
- `--no-judge`: run the deterministic screens only and never consult the judge
- `--since REF`: git ref to measure from, overriding the review's `reviewedSha`
- `-v`/`-vv`: verbosity level

The CLI:
- Locates `project-documents/user/reviews/{nnn}-review.{type}.{slice-name}.md`
- Measures what changed since the review was authored
- Writes `project-documents/user/reviews/{nnn}-resolution.{type}.{slice-name}-r{n}.md`, incrementing `{n}` — a resolution is never overwritten
- **Never edits the review file.** The resolution is evidence about the review, not an amendment to its `verdict:`

Exit codes: `0` for `ADDRESSED`, `1` for `UNADDRESSED` or `UNKNOWN`.

Example: `sq review resolve 305 code -v`

Show the resolution value, the per-finding table, and the artifact path. If the resolution is `UNADDRESSED` or `UNKNOWN`, highlight which findings are unsettled and why.

---

## Subcommand: pr

Review a pull request's code over its fetched merge-base range.

Pass what the user typed after `$sq-review pr` (the leading subcommand word removed) directly to:

`sq review pr {remainder}`

Unlike `code`/`slice`/`tasks`/`arch`, there is **no number shorthand and nothing is appended**.
A bare number is already a complete pull-request target (`sq review pr 116`), so there is no
shorthand to expand — and appending a flag such as `-v` would be a difference between this
transport and the CLI itself. An absent remainder is valid and passes through as absent:
`sq review pr` with no target reviews the current branch's pull request.

Optional arguments:
- Positional: pull request to review — a number, `owner/repo#number`, `repo#number`, a
  pull-request URL, or a branch. Omit to use the current branch.

Optional flags:
- `--cwd TEXT`: repository to resolve against
- `--rules PATH`: path to additional rules file
- `--rules-dir DIR`: rules directory override
- `--no-rules`: suppress all rule injection
- `--model TEXT`: model override (e.g. `opus`, `sonnet`)
- `--no-tools`: run this review without tools, even if the template declares them
- `--profile TEXT`: provider profile (e.g. `openrouter`, `openai`, `local`, `sdk`)
- `--verbose`/`-v`/`-vv`: verbosity level
- `--output TEXT`: output format — `terminal`, `json`, `file` (default: `terminal`)
- `--output-path TEXT`: file path for `--output file` (a JSON dump, not the review artifact)
- `--reviews-dir DIR`: directory for the saved review artifact. Overrides the project's reviews
  directory and `review.external_reviews_dir`. Distinct from `--output-path`. The CLI prints the
  chosen location and its source.
- `--json`: output and save as JSON instead of markdown
- `--no-save`: suppress review file save
- `--post`: post the review to the pull request as one comment
- `--dry-run`: print the comment that `--post` would write, without writing it (requires
  `--post`)

`--post` writes to the host. Rules for running it from a session:
- **Pass `--post` only when the operator typed it.** Never suggest adding it after a review, and
  never re-run a finished review with it.
- **On a non-zero exit from `--post`, show the output and stop.** No retry.

Example: `sq review pr 116 --model glm-5.3 --post`

Show the review results. If the verdict is FAIL or CONCERNS, highlight the key findings.
