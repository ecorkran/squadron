Run a task plan review using squadron.

## Input handling

If `$ARGUMENTS` starts with a number (e.g., `191`, `118`), treat it as a **slice number shorthand**. Otherwise, pass `$ARGUMENTS` directly to `sq review tasks` as before.

### Slice number shorthand

When `$ARGUMENTS` is a bare number:

`sq review tasks {number} -v`

The CLI automatically:
- Resolves the task file and slice design via `cf slice list --json` / `cf task list --json`
- Runs the review
- Saves the review to `project-documents/user/reviews/{nnn}-review.tasks.{slice-name}.md` with YAML frontmatter

Additional flags:
- `--json`: output and save as JSON instead of markdown
- `--no-save`: suppress the review file save
- `-v`/`-vv`: verbosity level

Show the review results. If the verdict is FAIL or CONCERNS, highlight the key findings.

### Full path invocation

When `$ARGUMENTS` contains paths (not a bare number), run:

`sq review tasks $ARGUMENTS`

Required arguments:
- Positional: path to the task breakdown file
- `--against PATH`: parent slice design to review against

Optional: `--cwd DIR`, `--model MODEL`, `--profile PROFILE`, `-v`/`-vv` for verbosity, `--json`, `--no-save`.

The `--model` flag accepts aliases (e.g., `opus`, `sonnet`, `gpt4o`) or full model IDs. Aliases automatically set the correct profile. Run `sq model list` to see available aliases. Users can add custom aliases in `~/.config/squadron/models.toml`.

The `--profile` flag routes the review through a specific provider (e.g., `openrouter`, `openai`, `local`, `sdk`). When omitted, the profile is resolved from the model alias or defaults to `sdk`.

Example: `sq review tasks tasks/105-tasks.md --against slices/105-slice.md`

Show the review results. If the verdict is FAIL or CONCERNS, highlight the key findings.
