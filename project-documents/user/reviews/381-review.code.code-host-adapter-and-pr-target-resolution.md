---
docType: review
layer: project
reviewType: code
slice: code-host-adapter-and-pr-target-resolution
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/381-slice.code-host-adapter-and-pr-target-resolution.md
aiModel: claude-sonnet-5
status: complete
resolutionBranch: 381-slice.review-fixes
dateCreated: 20260913
dateUpdated: 20260913
reviewedSha: cdee551852ecc823902efbc02770c6bf495ef81b
findings:
  - id: F001
    resolution: fixed
    severity: concern
    category: correctness
    summary: "Current-branch resolution ignores the resolved repo cwd"
    location: "src/squadron/codehost/github_cli.py#_branch_for"
  - id: F002
    resolution: fixed
    severity: concern
    category: correctness
    summary: "PR title/head/base interpolated into `-f`/`-F` argv, which gh treats specially when the value starts with `@`"
    location: "src/squadron/codehost/github_cli.py#open_pull_request"
  - id: F003
    resolution: fixed
    severity: note
    category: correctness
    summary: "Fence-closing regex doesn't enforce \"at least as long as the opener\" despite the comment claiming it does"
    location: "src/squadron/review/parsers.py#_FENCE_RE"
---

# Review: code — slice 381

**Verdict:** CONCERNS — all three findings fixed on `381-slice.review-fixes`
**Model:** claude-sonnet-5

## Findings

### [CONCERN] Current-branch resolution ignores the resolved repo cwd

`sq pr show` (no target given) resolves to `TargetForm.CURRENT_BRANCH`, and `GitHubCli._branch_for` determines the branch by running:

```python
result = self._runner.run(
    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
    cwd=None,
    timeout=HOST_COMMAND_TIMEOUT_SECONDS,
)
```

`cwd=None` means this git call runs against the process's actual working directory, not the `repo_cwd` that `cli/commands/pr.py::show` computed via `resolve_repo_cwd(cwd)`. Every other call on this path (`list_remotes(runner, repo_cwd)`, `fetch_pull_request_refs(..., cwd=repo_cwd)`) is deliberately anchored at the resolved repo root — the whole point of `cwd_resolution.py`, whose own docstring explains "an agent's cwd is its tool jail root, so a config cwd pointing at a subdirectory of the repo makes every repo-relative path unreadable." `CodeHost.resolve_pull_request(locator, target)` has no `cwd` parameter at all (see `protocol.py`), so there is no way for `_branch_for` to honor `--cwd`/config `cwd` even if it wanted to.

Concretely: if `sq pr show` is invoked from a directory other than the resolved repo root (e.g. an agent whose jail root is a subdirectory, or via `--cwd /other/repo`), the "current branch" is read from whatever git repo (if any) happens to be at the *process's* actual cwd — not the repo the command is targeting. If that directory isn't a git worktree, this misfires as `TargetUnresolvableError("HEAD is detached...")`, which is the wrong diagnosis (there's no detached HEAD; there's simply no repo at the literal cwd). If it happens to be a *different* git repo, the wrong PR could silently be resolved.

This is untested: `FakeProcessRunner` matches only on argv prefix and ignores the `cwd` field it records, so `test_all_six_forms_resolve_to_the_same_record[current-branch]` passes regardless of what `cwd` was passed to this specific call, masking the gap.

### [CONCERN] PR title/head/base interpolated into `-f`/`-F` argv, which gh treats specially when the value starts with `@`

```python
args = [
    "api", "-X", "POST", path,
    "-f", f"title={title}",
    "-f", f"head={head}",
    "-f", f"base={base}",
    "-f", "body=@-",
]
```

`gh api`'s `-f`/`--raw-field` (and `-F`/`--field`, used elsewhere for GraphQL variables such as `branch` in `_number_for_branch`) treats a value beginning with `@` as "read this field's value from a file" rather than as literal text — the same convention deliberately relied on here for `body=@-` (read from stdin). `title` is free-form operator text with no validation against a leading `@` (e.g. a title like `"@here: fix the flaky test"`), so `open_pull_request` would send `-f title=@here: fix the flaky test`, which `gh` will try to resolve as a filename rather than the literal title — producing a file-not-found failure or, worse, silently substituting file contents if a matching file happens to exist in the invocation directory. The module's own docstring for this class notes bodies are kept off argv specifically because of `gh`'s special handling, but that reasoning wasn't extended to `title`/`head`/`base`, which go through argv unguarded. No test exercises an `@`-prefixed title.

### [NOTE] Fence-closing regex doesn't enforce "at least as long as the opener" despite the comment claiming it does

The comment above `_FENCE_RE` says: "The closing fence must be *at least* as long as the opener, per CommonMark — not exactly as long... the closer is matched by character and length instead." The actual pattern only requires `(?P=char){3,}` for the closer — i.e. "the same character, 3+ repeats" — without ever comparing against the *opener's* captured length. A response using a 4-backtick fence (to safely contain a nested 3-backtick example) would have its outer fence closed early by the inner 3-backtick line, unmasking the remainder of the outer block as if it were live text. This is a narrow edge case (long fences are uncommon in review responses) but is a real gap relative to what the comment documents, and it works against the "never drop a real finding" posture the rest of this section is built around by doing the opposite failure (masking too little instead of too much).
