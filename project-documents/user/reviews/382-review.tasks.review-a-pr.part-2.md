---
docType: review
layer: project
reviewType: tasks
slice: review-a-pr
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/382-tasks.review-a-pr-2.md
aiModel: claude-sonnet-5
status: complete
dateCreated: 20260913
dateUpdated: 20260913
reviewedSha: 78ccf3bbd63bc132645e568041235162c4600f33
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "`_pr_block` truncation cap has no defined source"
    location: "src/squadron/review/builders/code.py"
  - id: F002
    severity: note
    category: consistency
    summary: "Cross-file part label is wrong"
    location: "project-documents/user/tasks/382-tasks.review-a-pr-1.md:229"
  - id: F003
    severity: pass
    category: uncategorized
    summary: "D4/D7 scope is tight, no scope creep"
    location: "project-documents/user/tasks/382-tasks.review-a-pr-2.md"
  - id: F004
    severity: pass
    category: uncategorized
    summary: "Code anchors are accurate"
    location: "src/squadron/review/review_client.py:332"
  - id: F005
    severity: pass
    category: uncategorized
    summary: "Test-with pattern and commit checkpoints"
    location: "project-documents/user/tasks/382-tasks.review-a-pr-2.md"
  - id: F006
    severity: note
    category: uncategorized
    summary: "Two tasks leave a design-placement decision to the implementer"
    location: "project-documents/user/tasks/382-tasks.review-a-pr-2.md"
---

# Review: tasks — slice 382

**Verdict:** CONCERNS
**Model:** claude-sonnet-5

## Findings

### [CONCERN] `_pr_block` truncation cap has no defined source

Task D.3 tells the implementer to truncate the PR block "through the existing size discipline" by calling the same helper `_inject_file_contents` uses (`_truncate` at `review_client.py:332`), and cites `review.max_file_size_bytes` only indirectly. It never says how `_pr_block` (or `code_review_prompt`) obtains the `max_file_size` integer that `_truncate` requires as its third argument.

I checked the actual call site: `_inject_file_contents` resolves this value itself via `get_config("review.max_file_size_bytes", cwd=cwd_for_config)` (`review_client.py:361-362`), and `builders/code.py` today has zero imports beyond `from __future__ import annotations` — it is a pure, config-free function that only reads keys off the `inputs` dict (confirmed: `diff_exclude_patterns` is pre-resolved by the CLI/review_client layer and handed to the builder as a plain string, never fetched by the builder itself). D.3 breaks that established pattern without saying so: either the builder must newly import `squadron.config.manager.get_config` (introducing a config/IO dependency to a previously pure module, and requiring a `cwd` value the builder doesn't currently receive), or the cap must be pre-resolved by the CLI/`run_review_with_profile` and threaded into `inputs` as a new key — but no task in any of the three files (checked file 3's `G.1`/`G.3` too) does this. Left as-is, a junior AI implementing D.3 is likely to either hardcode a byte constant (violating the project's "no magic defaults" rule) or bolt config access onto the builder inconsistently with every other builder in the package.

### [NOTE] Cross-file part label is wrong

File 1's Part B intro says the `pr` input key "does not exist yet (that lands in file 2's Part C)". It actually lands in file 2's **Part D** (Task D.1); file 2's Part C doesn't exist — file 2 starts at Part D. Low practical impact since the reader can find it via file 2's table of contents, but it's a broken cross-reference in a doc set that otherwise cites anchors precisely.

### [PASS] D4/D7 scope is tight, no scope creep

Every task in this file traces to a named design decision (D4 → Part D, D7 → Part E) and nothing else. No tasks reach into D1–D3/D5/D6/D8 territory, which file 1 and file 3 correctly own instead.

### [PASS] Code anchors are accurate

Spot-checked several citations used to ground these tasks — `_truncate` at `review_client.py:332`, `EmptyScopeError` at `git_utils.py:135`, `extract_diff_paths` at `rules.py:191`, and `code.yaml`'s existing `inputs.optional` shape — all match the current source exactly. No hallucinated anchors found.

### [PASS] Test-with pattern and commit checkpoints

Each implementation task is immediately followed by its test task (D.1/D.2, D.3/D.4, E.1/E.2), and each Part closes with its own commit task (D.5, E.3) rather than batching commits to the end of the file.

### [NOTE] Two tasks leave a design-placement decision to the implementer

Task D.3's truncation-helper reuse ("check whether it is already importable... if private, factor into a shared location") and Task E.1's module placement ("co-locate in rules.py, or a new review/scope.py — check which is more consistent") both push a real design choice onto the implementing agent instead of resolving it at task-writing time. Neither is blocking — both give a clear decision procedure — but combined with the D.3 finding above, D.3 in particular is carrying more ambiguity than its siblings for its Effort-4 rating.
