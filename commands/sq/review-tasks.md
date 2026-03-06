Run a task plan review using squadron:

`sq review tasks $ARGUMENTS`

Required arguments:
- Positional: path to the task breakdown file
- `--against PATH`: parent slice design to review against

Optional: `--cwd DIR`, `--model MODEL`, `--output FORMAT`, `-v`/`-vv` for verbosity.

Example: `sq review tasks tasks/105-tasks.md --against slices/105-slice.md`

Show the review results. If the verdict is FAIL or CONCERNS, highlight the key findings.
