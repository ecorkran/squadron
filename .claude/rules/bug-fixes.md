### Fixes (squadron specifics)

The general rule is `project-documents/ai-project-guide/project-guides/rules/fixes.md`. In squadron:

- The standing fixes slice is 944: `project-documents/user/tasks/944-tasks.standing-fixes.md`.
- Before committing: `ruff format`, `ruff check`, `pyright` (zero errors), and the tests for the touched area.
- The target is `cf config get git.integration_branch`, or `main` if empty. Never infer it from the current branch.
- Add a CHANGELOG bullet if a user would notice the change.
- Post progress on the GitHub issue as a comment when it helps; the issue is the record.
- Run `sq review` on a fix only when the Project Manager asks.
