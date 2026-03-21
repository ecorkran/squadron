Run an architectural review using squadron.

## Input handling

If `$ARGUMENTS` starts with a number (e.g., `191`, `118`), treat it as a **slice number shorthand** and perform a holistic review. Otherwise, pass `$ARGUMENTS` directly to `sq review arch` as before.

### Slice number shorthand (holistic review)

When `$ARGUMENTS` is a bare number:

`sq review arch {number} -v`

The CLI automatically:
- Resolves the slice design file via `cf slice list --json`
- Resolves the architecture document via `cf get --json`
- Runs a holistic review: slice design vs. architecture doc + slice plan entry
- Saves the review to `project-documents/user/reviews/{nnn}-review.arch.{slice-name}.md` with YAML frontmatter

This is a **holistic review** answering: "does this slice design effectively cover what it's supposed to?" It checks against both the architecture document and the slice plan entry.

Additional flags:
- `--json`: output and save as JSON instead of markdown
- `--no-save`: suppress the review file save
- `-v`/`-vv`: verbosity level

Show the review results. If the verdict is FAIL or CONCERNS, highlight the key findings.

### Full path invocation

When `$ARGUMENTS` contains paths (not a bare number), run:

`sq review arch $ARGUMENTS`

Required arguments:
- Positional: path to the document to review
- `--against PATH`: architecture or context document to review against

Optional: `--cwd DIR`, `--model MODEL`, `-v`/`-vv` for verbosity, `--json`, `--no-save`.

Example: `sq review arch slices/105-slice.md --against architecture/100-arch.md`

Show the review results. If the verdict is FAIL or CONCERNS, highlight the key findings.
