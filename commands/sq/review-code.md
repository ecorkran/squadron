Run a code review using squadron:

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
