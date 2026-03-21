Run a code review using squadron.

## Input handling

If `$ARGUMENTS` starts with a number (e.g., `191`, `118`), treat it as a **slice number shorthand**. Otherwise, pass `$ARGUMENTS` directly to `sq review code` as before.

### Slice number shorthand

When `$ARGUMENTS` is a bare number:

1. Run `cf slice list --json` and find the entry where `index` matches the number. If no match, report the error and stop — do not guess or fall back.
2. Extract the slice name from the `designFile` path (the part after `nnn-slice.` and before `.md`). If `designFile` is null, use the entry `name` field in kebab-case instead.
3. Run the review against main:

`sq review code --diff main -v`

4. Save the full review output to `project-documents/user/reviews/{nnn}-review.code.{slice-name}.md` with this YAML frontmatter:

```yaml
---
docType: review
reviewType: code
slice: {slice-name}
project: squadron
verdict: {PASS|CONCERNS|FAIL}
dateCreated: YYYYMMDD
dateUpdated: YYYYMMDD
---
```

If this file already exists (re-review), overwrite it. Git handles version history.

5. Show the review results. If the verdict is FAIL or CONCERNS, highlight the key findings.

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

Example: `sq review code --diff main` or `sq review code --files "src/**/*.py"`

Show the review results. If the verdict is FAIL or CONCERNS, highlight the key findings.
