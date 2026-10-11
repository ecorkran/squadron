### Bug Fixes

A bug fix is not a slice. Do not create a slice, design, task file, plan entry, or review artifact for one. The GitHub issue is the spec.

#### Procedure

1. Read the issue. Get the actual error or failing behavior (see Core Principles on debugging evidence).
2. Write a test that fails for the reported reason. Run it and confirm it fails.
3. Fix the code. Run the test and confirm it passes.
4. Before committing: `ruff format`, `ruff check`, `pyright` (zero errors), and the tests for the touched area.
5. Commit to the target: read `cf config get git.integration_branch`; its value, or `main` if empty. Never infer it from the current branch. One fix, one commit: `fix: {summary}` with `Fixes #{n}` in the body.
6. Add a CHANGELOG bullet if a user would notice the change. Nothing else is documented.
7. The issue closes from the commit. Do not edit slice plans, task files, or DEVLOG for the fix.

The hard rule on merging to `main` when `integration_branch` is set applies unchanged: never.

#### Large fixes

Size does not turn a bug fix into a slice. A large fix is the same procedure in more commits:

- Land it as a series of commits, each leaving the tests green, each with its own test. Do not batch it into one commit.
- If it will take more than a few commits, work on `fix-{n}` forked from the target and merge it into the target when the full suite passes. This is the only branch a bug fix gets.
- Run the full test suite once before that merge.
- Keep any plan in the issue as a comment, not a file in the repo.

#### Not reviewed by default

No `sq review` runs on a bug fix unless the Project Manager asks for one. The failing-then-passing test is the gate.

#### When it stops being a bug fix

Stop and tell the Project Manager when the fix needs a new user-facing option, a changed file or state format, or a new component. Say what it needs in one line. That, and only that, is a candidate for a slice. Size alone never is.
