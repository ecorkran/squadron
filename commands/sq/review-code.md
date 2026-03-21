Run a code review using squadron.

## Input handling

If `$ARGUMENTS` starts with a number (e.g., `191`, `118`), treat it as a **slice number shorthand**. Otherwise, pass `$ARGUMENTS` directly to `sq review code` as before.

### Slice number shorthand

When `$ARGUMENTS` is a bare number:

`sq review code {number} -v`

The CLI automatically:
- Resolves the slice context via `cf slice list --json`
- Defaults to `--diff main` when invoked with a number
- Saves the review to `project-documents/user/reviews/{nnn}-review.code.{slice-name}.md` with YAML frontmatter

Additional flags:
- `--json`: output and save as JSON instead of markdown
- `--no-save`: suppress the review file save
- `-v`/`-vv`: verbosity level

Show the review results. If the verdict is FAIL or CONCERNS, highlight the key findings.

### Full flag invocation

When `$ARGUMENTS` contains flags (not a bare number), run:

`sq review code $ARGUMENTS`

Optional flags:
- `--cwd DIR`: project directory to review
- `--files PATTERN`: glob pattern to scope the review
- `--diff REF`: git ref to diff against (reviews changed files)
- `--rules PATH`: path to additional rules file
- `--model MODEL`: model override
- `-v`/`-vv`: verbosity level
- `--json`, `--no-save`

Example: `sq review code --diff main` or `sq review code --files "src/**/*.py"`

Show the review results. If the verdict is FAIL or CONCERNS, highlight the key findings.
