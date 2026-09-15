---
docType: review
layer: project
reviewType: code
slice: review-a-pr
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/382-slice.review-a-pr.md
aiModel: z-ai/glm-5.2
status: complete
dateCreated: 20260915
dateUpdated: 20260915
reviewedSha: f72420b0e5a24039a2f3495094cdb4ea90229605
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 35
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "`assemble_pr_metadata` network call not covered by CodeHostError handler"
    location: "src/squadron/cli/commands/review_pr.py:96-97"
  - id: F002
    severity: concern
    category: concurrency
    summary: "Race window between worktree creation and lock write in concurrent sweeps"
    location: "src/squadron/codehost/worktree.py:215-223"
  - id: F003
    severity: concern
    category: design
    summary: "`--no-tools` path unconditionally disables SDK project settings even against trusted checkout"
    location: "src/squadron/cli/commands/review_pr.py:178-196"
  - id: F004
    severity: note
    category: style
    summary: "Zero-width space defined as invisible literal character"
    location: "src/squadron/review/builders/code.py:14"
  - id: F005
    severity: note
    category: design
    summary: "Private function imports from `review.py` create tight coupling"
    location: "src/squadron/cli/commands/review_pr.py:24-30"
---

# Review: code — slice 382

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.2

## Findings

### [CONCERN] `assemble_pr_metadata` network call not covered by CodeHostError handler

In `review_pr`, the `CodeHostError` try/except only wraps `resolve_and_fetch_pull_request` (lines 93-95). Immediately after, `assemble_pr_metadata(resolved, host)` is called (line 97), which internally calls `host.list_unresolved_discussions(record)` — a network call that can raise `CodeHostError` on transport/auth failure. This exception is not caught, so an adapter failure during discussion fetch produces an unhandled traceback rather than the clean `render_code_host_error` + `typer.Exit(code=1)` path used for all other adapter failures in this command. The fix is to move the `assemble_pr_metadata` call inside the existing try block, or add a second try/except around it that calls `render_code_host_error` and exits.

### [CONCERN] Race window between worktree creation and lock write in concurrent sweeps

`ScratchWorktree.__enter__` creates the worktree via `git worktree add` (line 218) and then writes the lock file (line 222-223). Between these two steps, the worktree directory exists on disk with no `lock.json`. A concurrent `sweep_orphans` call (from another `ScratchWorktree.__enter__` running simultaneously) will call `_read_lock` on this directory, get `None` (no lock file), and `_is_orphan` returns `True` for `lock is None` — so it removes the just-created worktree. The comment in `_read_lock` says "missing" is treated as orphan, which is correct for crashed prior runs, but it also makes a live-but-not-yet-locked worktree indistinguishable from an orphan. The load test `test_concurrent_worktree_creation_succeeds_with_non_colliding_paths` exercises 8 concurrent threads but may pass due to timing — the race window is narrow but real. Consider writing a sentinel file before `git worktree add` completes, or having `sweep_orphans` skip directories whose `git worktree add` is still in progress (e.g., a creation marker written atomically before the worktree add call).

### [CONCERN] `--no-tools` path unconditionally disables SDK project settings even against trusted checkout

In `_run`, `setting_sources_override=[]` is always passed regardless of whether the `--no-tools` branch (no worktree, single root = the trusted checkout) or the worktree branch is taken. The comment says "D8: setting_sources_override=[] regardless of --no-tools." While this is intentional, it means `sq review pr 83 --no-tools --cwd <trusted-checkout>` runs the SDK with `setting_sources=[]` and `CLAUDE_CODE_DISABLE_AUTO_MEMORY=1`, disabling all project-level settings even though the cwd IS the trusted checkout with no untrusted worktree involved. Users running `--no-tools` reviews against their own checkout lose their project settings (hooks, `.claude/settings.json`) unexpectedly. Consider only applying the override on the worktree (tools-enabled) path, where the cwd is genuinely untrusted.

### [NOTE] Zero-width space defined as invisible literal character

`_ZERO_WIDTH_SPACE = "​"` uses a literal zero-width space (U+200B) character in the source. While commented, an invisible literal is fragile in source code — it cannot be visually distinguished from an empty string and may be accidentally modified or removed by editors. Prefer the explicit escape: `_ZERO_WIDTH_SPACE = "\u200b"` for clarity and robustness.

### [NOTE] Private function imports from `review.py` create tight coupling

`review_pr.py` imports four underscore-prefixed private functions (`_exit_on`, `_resolve_save_outcome`, `_resolve_verbosity`, `_run_review_command`) from `review.py` with `pyright: ignore[reportPrivateUsage]`. This makes `review_pr.py` tightly coupled to `review.py`'s internal implementation — any refactor of those functions' signatures or names breaks `review_pr` with no compiler warning. The `pyright: ignore` suppresses the only automated signal. Consider promoting these to a shared non-private module (e.g., `review_common.py`) or making them public API if they are shared across CLI commands.

### Run Digest

- Response length: 4857 chars
- Response is newline-free: no
- Tool calls made: 35
- Tool calls failed: 1
- Stop reason: stop
- Reasoning characters: 9728
- `## Summary` located: no
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5
