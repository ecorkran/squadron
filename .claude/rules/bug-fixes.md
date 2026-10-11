### Fixes

A fix and a bug fix are the same thing: any work that would be committed as `fix:`. Fixes do not get their own slice. Slice 944 (Standing Fixes) is the permanent, review-exempt container for them. Its slice design says so, and unrelated fixes belong together in it.

#### Small fix: just make it

If it needs no tasks, make it:

1. Read the GitHub issue (it is the spec). Get the actual error or failing behavior.
2. Write a test that fails for the reported reason, then fix the code.
3. `ruff format`, `ruff check`, `pyright` (zero errors), and the tests for the touched area.
4. Commit to the target (`cf config get git.integration_branch`, or `main` if empty; never infer it from the current branch) as `fix: {summary}` with `Fixes #{n}`. Add a CHANGELOG bullet if a user would notice.

No task file entry, no review, no branch.

#### Bigger fix: tasks in slice 944

If the fix needs several steps, add a task group titled with its issue number to `project-documents/user/tasks/944-tasks.standing-fixes.md` and work it there, one commit per task on the target. Check the boxes as tasks finish. Reopen slice 944 or its tasks whenever needed; nothing about a closed item stops a new one. Post progress on the issue as a comment when it helps.

#### When it is not a fix

A change that needs a new user-facing option, a changed file or state format, or a new component is a feature. Say so in one line and it gets its own slice. Size alone never makes something a feature.

#### Reviews

None by default (slice 944 is `review: none`). Run `sq review` on a fix only when the Project Manager asks.
