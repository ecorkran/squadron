---
docType: slice-design
slice: scoped-code-review-prompt-logging
project: squadron
parent: 100-slices.orchestration-v2.md
dependencies: [review-context-enrichment]
interfaces: []
dateCreated: 20260325
dateUpdated: 20260325
status: not_started
---

# Slice Design: Scoped Code Review & Prompt Logging

## Overview

When running `sq review code 122`, the diff currently resolves to `--diff main`, which includes *all* changes on main — not just the commits introduced by slice 122. This slice adds automatic commit-range scoping so that `sq review code 122` diffs only the commits that belong to slice 122's branch, producing a focused review.

Additionally, the `-vvv` debug output (system prompt, user prompt, injected rules) currently prints only to stderr and is lost. This slice adds prompt log persistence: at `-vvv`, the full prompt is written to a timestamped file under `~/.config/squadron/logs/`. Optionally, at `-vv+`, the full prompt and raw response can be embedded in the saved review file itself.

## User-Provided Concept

From slice plan: "Enable `sq review code 122` to automatically scope the diff to the commits introduced by slice 122's branch, rather than diffing against main. Resolve commit range from branch name (`122-slice.*`) or merge base. Add prompt log persistence: `-vvv` output written to `~/.config/squadron/logs/review-prompt-{timestamp}.md` alongside stderr. Optionally include full prompt/response in the saved review file at `-vv+`."

PM observation: Running `sq review code 122 -vvv` showed the full prompt sent to the model — a large payload (~4000 tokens of diff + injected file contents). The diff included all changes on main, not just slice 122's work. The `-vvv` output is valuable for debugging but is lost after the terminal scrolls.

---

## Technical Decisions

### 1. Scoped Diff Resolution

**Problem:** `sq review code 122` currently sets `diff = "main"`, which produces `git diff main` — the diff of the entire working tree against main, not the commits specific to slice 122.

**Solution:** Resolve the slice's branch name from the slice number, then compute the appropriate diff range:

1. **Branch discovery:** Given slice number N, find the branch matching `N-slice.*` (e.g., `122-slice.review-context-enrichment`). Use `git branch --list 'N-slice.*'` to find it.

2. **Diff range computation** — two cases:
   - **Branch still exists (not yet merged):** Use `git merge-base main <branch>` to find where the branch diverged, then diff `<merge-base>...<branch>` (three-dot) to get only the branch's commits.
   - **Branch is merged:** Detect the merge commit on main via `git log --merges --oneline --grep='N-slice' main`. Extract the merge commit, then use `<merge-commit>^1..<merge-commit>^2` to diff only the merged branch's changes.

3. **Fallback:** If no branch or merge commit is found, fall back to the current behavior (`--diff main`) with a warning message.

**New helper:** `_resolve_slice_diff_range(slice_number: int, cwd: str) -> str` in `review.py` (or a new `squadron/review/git_utils.py` if cleaner). Returns a git diff range string.

### 2. Prompt Log Persistence

**Problem:** `-vvv` debug output prints to stderr and is lost when the terminal scrolls or when reviewing later.

**Solution:** At verbosity >= 3, write the full prompt payload to a file:

- **Location:** `~/.config/squadron/logs/review-prompt-{timestamp}.md`
- **Format:** Markdown with sections for system prompt, user prompt, injected rules, and metadata (model, profile, template name, timestamp)
- **Timestamp format:** `YYYYMMDD-HHmmss` (e.g., `review-prompt-20260325-143022.md`)
- **Behavior:** Write the file *before* the API call, so the prompt is captured even if the call fails. Print the file path to stderr alongside the existing debug output.

**Implementation location:** `_run_non_sdk_review()` in `review_client.py` — the same function that currently prints to stderr. Add a `_write_prompt_log()` helper.

For the SDK path: the SDK manages its own prompts, so prompt logging only applies to the non-SDK path. This is acceptable since the SDK path is the one where prompt debugging is less transparent.

### 3. Prompt/Response in Saved Review File (verbosity >= 2)

**Problem:** When debugging review quality, having the full prompt and raw response alongside the parsed findings is valuable. Currently this requires re-running with `-vvv` and manually correlating.

**Solution:** At verbosity >= 2, include an appendix in the saved review markdown file:

```markdown
---

## Debug: Prompt & Response

### System Prompt
{system_prompt}

### User Prompt
{user_prompt}

### Rules Injected
{rules_content or "None"}

### Raw Response
{raw_output}
```

**Implementation:**
- Add `system_prompt`, `user_prompt`, and `rules_content` fields to `ReviewResult` (all `str | None`, default `None`). These are populated only when verbosity >= 2 in the non-SDK path.
- `_format_review_markdown()` appends the debug appendix when these fields are present.
- The fields are excluded from `to_dict()` JSON output to keep JSON responses clean.

### 4. Log Directory Management

Reuse the existing `~/.config/squadron/logs/` directory already used by `review-debug.jsonl` (from slice 122). No new directory structure needed.

Ensure the directory is created if it doesn't exist (it should already exist from the debug log, but be defensive).

---

## Architecture

### Component Structure

```
squadron/review/git_utils.py (NEW)
  _find_slice_branch(slice_number, cwd) -> str | None
  _find_merge_commit(slice_number, cwd) -> str | None
  resolve_slice_diff_range(slice_number, cwd) -> str

squadron/cli/commands/review.py (MODIFIED)
  review_code() — use resolve_slice_diff_range() when slice_number is provided
  _format_review_markdown() — append debug appendix when fields present

squadron/review/review_client.py (MODIFIED)
  _run_non_sdk_review() — populate prompt fields on result, write prompt log
  _write_prompt_log() (NEW) — write markdown prompt log file

squadron/review/models.py (MODIFIED)
  ReviewResult — add system_prompt, user_prompt, rules_content_used fields
```

### Data Flow

1. User runs `sq review code 122 -vv`
2. `review_code()` resolves slice 122 → finds branch `122-slice.review-context-enrichment`
3. `resolve_slice_diff_range(122, cwd)` computes `<merge-base>...<branch>` or merge-commit range
4. Diff range passed to `_run_review_command()` as the `diff` input
5. Review executes normally; at verbosity >= 2, prompt fields populated on `ReviewResult`
6. If verbosity >= 3, `_write_prompt_log()` writes `~/.config/squadron/logs/review-prompt-{ts}.md`
7. `_save_review_file()` includes debug appendix in saved review markdown

---

## Implementation Details

### `git_utils.py` — Slice Diff Resolution

```python
def _find_slice_branch(slice_number: int, cwd: str) -> str | None:
    """Find a branch matching '{slice_number}-slice.*'."""
    # git branch --list '122-slice.*' → '  122-slice.review-context-enrichment'

def _find_merge_commit(slice_number: int, cwd: str) -> str | None:
    """Find the merge commit for a slice branch on main."""
    # git log --merges --oneline --grep='{N}-slice' main -1
    # Parse commit hash from output

def resolve_slice_diff_range(slice_number: int, cwd: str) -> str:
    """Resolve the git diff range for a slice's commits.

    Returns a diff range string suitable for `git diff <range>`.
    Falls back to 'main' with a warning if resolution fails.
    """
```

**Branch detection precedence:**
1. Local branch `{N}-slice.*` exists → use merge-base three-dot diff
2. No local branch but merge commit found on main → use merge-commit parent diff
3. Neither found → warn and fall back to `main`

### `review_client.py` — Prompt Log Writer

```python
def _write_prompt_log(
    system_prompt: str,
    user_prompt: str,
    rules_content: str | None,
    model: str,
    profile: str,
    template_name: str,
) -> Path:
    """Write prompt to ~/.config/squadron/logs/review-prompt-{ts}.md."""
```

The log file format:

```markdown
---
template: {template_name}
model: {model}
profile: {profile}
timestamp: {ISO 8601}
---

# Review Prompt Log

## System Prompt
{system_prompt}

## User Prompt
{user_prompt}

## Injected Rules
{rules_content or "None"}
```

### `models.py` — New Fields on ReviewResult

Add three optional fields:

```python
system_prompt: str | None = None
user_prompt: str | None = None
rules_content_used: str | None = None
```

These are populated by `_run_non_sdk_review()` when verbosity >= 2. They are excluded from `to_dict()` to keep JSON output clean. `_format_review_markdown()` uses them for the debug appendix.

### `review.py` — Integration Changes

In `review_code()`:
- When `slice_number` is provided, replace the current `diff = "main"` with `diff = resolve_slice_diff_range(int(slice_number), resolved_cwd)`

In `_format_review_markdown()`:
- After the findings section, if `result.system_prompt` is not None, append the debug appendix

In `_execute_review()` / `_run_review_command()`:
- Thread `verbosity` through to `_run_non_sdk_review()` (already done in slice 122)

---

## Success Criteria

### Functional Requirements

1. `sq review code 122` scopes the diff to only slice 122's commits, not the entire diff against main
2. When the slice branch still exists locally, the diff uses the merge-base three-dot range
3. When the branch is already merged, the diff is derived from the merge commit
4. If neither branch nor merge commit is found, falls back to `--diff main` with a warning
5. `sq review code 122 -vvv` writes prompt log to `~/.config/squadron/logs/review-prompt-{ts}.md`
6. Prompt log file path is printed to stderr at verbosity >= 3
7. `sq review code 122 -vv` (with auto-save) includes a debug appendix in the saved review markdown
8. `sq review code 122 -v` does NOT include debug appendix (verbosity too low)
9. The `--diff` flag continues to work as an explicit override (takes precedence over auto-resolution)
10. JSON output (`--output json`) does NOT include prompt/response debug fields

### Technical Requirements

1. New `git_utils.py` module with unit tests for all three resolution paths (branch exists, merged, fallback)
2. Prompt log writer has unit tests
3. Debug appendix in review markdown has unit tests
4. All existing tests continue to pass
5. Ruff + pyright clean

### Verification Walkthrough

**1. Scoped diff — branch exists:**
```bash
# Slice 122 branch still exists locally
sq review code 122 -vvv --no-save
# Expected: -vvv output shows git diff range like '<hash>...122-slice.review-context-enrichment'
# Expected: diff content is limited to slice 122's changes, not all of main
```

**2. Scoped diff — branch merged:**
```bash
# If branch is deleted after merge, should find merge commit
git branch -d 122-slice.review-context-enrichment
sq review code 122 -vvv --no-save
# Expected: finds merge commit, diffs only the merged changes
# Expected: warning if neither branch nor merge found
```

**3. Explicit --diff override:**
```bash
sq review code 122 --diff HEAD~3 --no-save
# Expected: uses HEAD~3 as the diff ref, ignoring auto-resolution
```

**4. Prompt log persistence:**
```bash
sq review code 122 -vvv --no-save
# Expected: stderr includes line like "Prompt log: ~/.config/squadron/logs/review-prompt-20260325-143022.md"
ls ~/.config/squadron/logs/review-prompt-*.md
# Expected: at least one prompt log file exists
cat ~/.config/squadron/logs/review-prompt-*.md | head -20
# Expected: markdown with system prompt, user prompt, rules sections
```

**5. Debug appendix in saved review:**
```bash
sq review code 122 -vv
# Expected: saved review file contains "## Debug: Prompt & Response" appendix
cat project-documents/user/reviews/122-review.code.*.md | grep -c "Debug: Prompt"
# Expected: 1
```

**6. No debug appendix at -v:**
```bash
sq review code 122 -v
# Expected: saved review file does NOT contain "## Debug: Prompt & Response"
```

---

## Implementation Notes

### Development Approach

Suggested implementation order:
1. `git_utils.py` with branch/merge resolution + tests
2. `ReviewResult` model changes (new optional fields)
3. `_write_prompt_log()` in `review_client.py` + tests
4. Wire scoped diff into `review_code()` + tests
5. Debug appendix in `_format_review_markdown()` + tests
6. Integration test: end-to-end with mocked git commands

### Special Considerations

- **Git subprocess calls:** All git commands should use `check=False` and handle failures gracefully. The scoped diff is a convenience — failure should fall back to `--diff main`, not crash.
- **Merged branch detection:** The `--grep` pattern needs to be specific enough to avoid false positives. Use `'{N}-slice'` (with the numeric prefix) to match merge commit messages.
- **Prompt log size:** Prompt logs can be large (the user observed ~4000 tokens in one review). This is acceptable for debug logs. Consider adding a note about cleanup in documentation.
- **SDK path:** Prompt logging is not implemented for the SDK path since the SDK manages its own prompts internally. This is a known limitation, not a bug.
