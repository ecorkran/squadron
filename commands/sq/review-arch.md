Run an architectural review using squadron:

`sq review arch $ARGUMENTS`

Required arguments:
- Positional: path to the document to review
- `--against PATH`: architecture or context document to review against

Optional: `--cwd DIR`, `--model MODEL`, `--output FORMAT`, `-v`/`-vv` for verbosity.

Example: `sq review arch slices/105-slice.md --against architecture/100-arch.md`

Show the review results. If the verdict is FAIL or CONCERNS, highlight the key findings.
