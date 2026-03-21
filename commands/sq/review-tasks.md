Run a task plan review using squadron.

## Input handling

If `$ARGUMENTS` starts with a number (e.g., `191`, `118`), treat it as a **slice number shorthand**. Otherwise, pass `$ARGUMENTS` directly to `sq review tasks` as before.

### Slice number shorthand

When `$ARGUMENTS` is a bare number:

1. Run `cf slice list --json` and find the entry where `index` matches the number. If no match, report the error and stop — do not guess or fall back.
2. Extract the `designFile` from the matching entry. If `designFile` is null, report that no slice design file exists for this slice and stop.
3. Extract the slice name from the design file path (the part after `nnn-slice.` and before `.md`).
4. Run `cf task list --json` and find the entry where `index` matches the number. Extract the task file path. If no task file exists, report the error and stop.
5. Run the review:

`sq review tasks {task-file-path} --against {design-file-path} -v`

6. Save the full review output to `project-documents/user/reviews/{nnn}-review.tasks.{slice-name}.md` with this YAML frontmatter:

```yaml
---
docType: review
reviewType: tasks
slice: {slice-name}
project: squadron
verdict: {PASS|CONCERNS|FAIL}
dateCreated: YYYYMMDD
dateUpdated: YYYYMMDD
---
```

If this file already exists (re-review), overwrite it. Git handles version history.

7. Show the review results. If the verdict is FAIL or CONCERNS, highlight the key findings.

### Full path invocation

When `$ARGUMENTS` contains paths (not a bare number), run:

`sq review tasks $ARGUMENTS`

Required arguments:
- Positional: path to the task breakdown file
- `--against PATH`: parent slice design to review against

Optional: `--cwd DIR`, `--model MODEL`, `--output FORMAT`, `-v`/`-vv` for verbosity.

Example: `sq review tasks tasks/105-tasks.md --against slices/105-slice.md`

Save the review output to `project-documents/user/reviews/` following the same naming convention if a slice number can be extracted from the task file name. Otherwise, just show the results.

Show the review results. If the verdict is FAIL or CONCERNS, highlight the key findings.
