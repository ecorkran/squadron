Run a review using squadron.

## Input parsing

The first word of `$ARGUMENTS` is the subcommand. The remainder is passed to the CLI unchanged.

Valid subcommands: `code`, `slice`, `tasks`, `arch`

If the subcommand is missing or unrecognized, show the usage below and stop.

**Usage:**
```
/sq:review code [NUMBER | FLAGS]     — code review
/sq:review slice [NUMBER | FLAGS]    — slice design review
/sq:review tasks [NUMBER | FLAGS]    — task plan review
/sq:review arch [NUMBER | FLAGS]     — architecture review
```

---

## Subcommand: code

Run a code review using squadron.

If the remainder of `$ARGUMENTS` (after stripping the leading `code` word) starts with a number (e.g., `191`, `118`), treat it as a **slice number shorthand**. Otherwise, pass the remainder directly to `sq review code`.

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

If the remainder of `$ARGUMENTS` (after stripping the leading `slice` word) starts with a number (e.g., `191`, `118`), treat it as a **slice number shorthand** and perform a holistic review. Otherwise, pass the remainder directly to `sq review slice`.

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

If the remainder of `$ARGUMENTS` (after stripping the leading `tasks` word) starts with a number (e.g., `191`, `118`), treat it as a **slice number shorthand**. Otherwise, pass the remainder directly to `sq review tasks`.

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

If the remainder of `$ARGUMENTS` (after stripping the leading `arch` word) starts with a number (e.g., `140`), treat it as an **initiative index shorthand**. Otherwise, pass the remainder directly to `sq review arch`.

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
