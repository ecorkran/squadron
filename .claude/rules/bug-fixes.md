### Bug Fixes

A bug fix is not a slice. Do not create a slice, design, task file, plan entry, or review artifact for one. The GitHub issue is the spec.

#### Procedure

1. Read the issue. Get the actual error or failing behavior (see Core Principles on debugging evidence).
2. Write a test that fails for the reported reason. Run it and confirm it fails.
3. Fix the code. Run the test and confirm it passes.
4. Before committing: `ruff format`, `ruff check`, `pyright` (zero errors), and the tests for the touched area.
5. Commit directly to the target branch (`cf config get git.integration_branch`, or `main`). One fix, one commit: `fix: {summary}` with `Fixes #{n}` in the body. Several related fixes may land as several commits in a row.
6. Add a CHANGELOG bullet if a user would notice the change. Nothing else is documented.
7. The issue closes from the commit. Do not edit slice plans, task files, or DEVLOG for the fix.

#### Not reviewed by default

No `sq review` runs on a bug fix unless the Project Manager asks for one. The failing-then-passing test is the gate.

#### When it stops being a bug fix

Stop and tell the Project Manager when the fix needs a new user-facing option, a changed file or state format, or a new component. Say what it needs in one line. That, and only that, is a candidate for a slice.

A fix that is large but changes no interface, format, or component is still a bug fix.
