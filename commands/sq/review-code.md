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
- `--model MODEL`: model override — accepts aliases (e.g., `opus`, `gpt4o`) or full model IDs. Aliases automatically set the correct profile. Run `sq model list` for available aliases.
- `--profile PROFILE`: provider profile (e.g., `openrouter`, `openai`, `local`, `sdk`). Resolved from model alias when omitted, defaults to `sdk`.

For non-SDK providers, file contents and git diffs are automatically injected into the prompt so models can review actual content.
- `-v`/`-vv`: verbosity level
- `--json`, `--no-save`

Example: `sq review code --diff main` or `sq review code --files "src/**/*.py"`

Show the review results. If the verdict is FAIL or CONCERNS, highlight the key findings.
