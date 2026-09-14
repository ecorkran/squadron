---
docType: tasks
slice: review-a-pr
project: squadron
lld: project-documents/user/slices/382-slice.review-a-pr.md
dependencies: [381, 916, 904, 918]
projectState: "File 1 (Parts A-C) lands convention_root, the settings override, and the scratch-worktree lifecycle. This file adds the PR-metadata block and its template input."
dateCreated: 20260913
dateUpdated: 20260913
status: not_started
---

# Tasks: Review a PR (2 of 3)

Continues
[382-tasks.review-a-pr-1.md](project-documents/user/tasks/382-tasks.review-a-pr-1.md),
which holds the Context Summary, verified code anchors, corrections against
the design, and the standing constraints. All of those govern the parts
below; read that file first.

File 1 built the security-critical foundation (convention_root, the settings
override) and the scratch-worktree lifecycle. This file builds the
PR-metadata block that reaches the model as data (D4), and the input plumbing
that carries it. File 3 builds the `pr` subcommand that ties everything
together (D2, D5–D7) plus live evidence and closeout.

## Part D — PR Metadata Reaches the Model as Data

Design D4. The CLI (file 3) will supply raw metadata; this part builds the
renderer and its containment guarantees, independent of the CLI work.

### Task D.1 — `code.yaml`: declare the optional `pr` input

- [ ] In [code.yaml](src/squadron/data/templates/code.yaml), add to
      `inputs.optional`:
      ```yaml
      - name: pr
        description: "Pull request metadata (title, body, linked issues, discussions) rendered as a fenced block"
      ```
- [ ] Do not add a `default`. Absence means no PR context — every non-PR
      caller of the `code` template (including `sq review code`) is
      unaffected.
- [ ] Effort: 1

### Task D.2 — Test: pipeline action tolerates the new input

- [ ] Locate the pipeline `review` action's input validation (search for
      where template `inputs.optional`/`required` are checked against a
      pipeline step's supplied keys — likely in `squadron/pipeline/` or
      wherever `ReviewTemplate.required_inputs`/`optional_inputs` are
      consumed outside the CLI).
- [ ] Add a test: a pipeline step invoking the `code` template with no `pr`
      key supplied still runs — an optional input the pipeline never
      populates must not become a validation failure.
- [ ] Effort: 2

### Task D.3 — `_pr_block`: fence-length and label neutralization

- [ ] **Truncation-cap mechanism, decided here rather than left open (review
      finding, part 2, F001).** `builders/code.py` today has zero imports
      beyond `from __future__ import annotations` — a pure, config-free
      module that only reads pre-resolved values off the `inputs` dict (the
      existing `diff_exclude_patterns` key is the precedent: the CLI/
      `review_client` layer resolves it via `get_config` and hands the
      builder a plain string, never fetching config itself). `_pr_block`
      follows the same shape: it does **not** call `get_config` and does
      **not** import `squadron.config.manager`. Instead, the caller that
      already resolves `review.max_file_size_bytes` —
      `_inject_file_contents` ([review_client.py:361](src/squadron/review/review_client.py#L361)) —
      resolves it once and the CLI (file 3, Task G.1) threads it into
      `inputs["pr_max_bytes"]` as a stringified int, exactly as
      `diff_exclude_patterns` is threaded today. `_pr_block` reads
      `inputs.get("pr_max_bytes")` and passes it to the shared truncation
      helper (see the bullet below) — no new config/IO dependency enters
      this module.
- [ ] In [builders/code.py](src/squadron/review/builders/code.py), add
      `_pr_block(pr_metadata: str, max_bytes: int) -> str`. Content shape
      (raw metadata the CLI assembles, per D4): title, body, linked issue
      numbers, unresolved discussions (path, line, author, body) — already
      formatted into one string by the CLI; this function only fences,
      labels, and truncates it.
- [ ] Outer fence length: find the longest run of consecutive backticks
      anywhere in `pr_metadata`, use a fence one backtick longer (minimum
      three). A 4-backtick run inside forces a 5-backtick outer fence. This
      is the same defect class as the review parser's closer-length bug
      fixed on 381's review — a fixed-length fence is not containment.
- [ ] Label neutralization: the block's own label (e.g. `### Pull Request`
      or whatever heading text is chosen — pick one and use it consistently)
      must not appear verbatim inside `pr_metadata`'s content; if it does,
      insert a zero-width character or otherwise break the exact string
      match before emission, without altering the visible text a human or
      model reads.
- [ ] Truncate through the existing size discipline: import `_truncate`
      directly from `review_client`
      ([review_client.py:332](src/squadron/review/review_client.py#L332)).
      **Verified no import cycle results**: `review_client.py` never imports
      `builders/code.py` — the builder is loaded at runtime by the dotted
      path `code.yaml` names
      (`squadron.review.builders.code.code_review_prompt`), not by a Python
      `import` statement, so `builders/code.py → review_client` is a new,
      one-directional edge. `_truncate` is private (leading underscore) but
      not module-private in any enforced sense; import it as
      `from squadron.review.review_client import _truncate` and call
      `_truncate(pr_metadata, "pr", max_bytes)`, matching its existing
      signature. State the truncation in the block's own text when it
      occurs (design requirement).
- [ ] `code_review_prompt` calls
      `_pr_block(inputs["pr"], int(inputs["pr_max_bytes"]))` and appends the
      result to the prompt when `inputs.get("pr")` is present; omitted
      entirely when absent. A `pr` key present without `pr_max_bytes` is a
      caller error — raise rather than defaulting to an arbitrary cap (no
      silent fallback values, project rule).
- [ ] Effort: 4

### Task D.4 — Test: fence length, label neutralization, truncation

- [ ] Create `tests/review/test_code_builder_pr_block.py`.
- [ ] 3-backtick content inside the PR body → outer fence is 4 backticks;
      4-backtick content → outer fence is 5 backticks. Assert the rendered
      block, when scanned for the outer fence's exact character sequence,
      finds it only at open and close.
- [ ] PR body containing the literal block label text does not close or
      confuse the block — assert the rendered prompt keeps the block intact
      (the design's own success criterion; use this test to satisfy it).
- [ ] Content exceeding a small test-supplied `max_bytes` is truncated and
      the block states so; content under the cap is untouched.
- [ ] `inputs` with no `pr` key produces a prompt identical to today's (no
      block, no stray heading), and `code_review_prompt` never reads
      `pr_max_bytes` in that case.
- [ ] `inputs["pr"]` present without `inputs["pr_max_bytes"]` raises rather
      than silently picking a default cap.
- [ ] Effort: 3

### Task D.5 — Commit Part D

- [ ] Run `uv run pytest tests/review -q`. All green, including every
      existing `builders/code.py` and `code.yaml` test.
- [ ] `uv run ruff format`, `uv run ruff check`, `uv run pyright`.
- [ ] Commit: `feat(review): render PR metadata as a contained fenced block`
- [ ] Effort: 1

---

## Part E — `--files` Intersection Helper (D7)

Isolated here because it is pure logic with no worktree or CLI dependency,
and file 3's `pr` subcommand needs it ready to call.

### Task E.1 — Intersect a glob with a changed-path set

- [ ] Add a small function (co-locate with `extract_diff_paths` in
      [rules.py](src/squadron/review/rules.py), or a new
      `review/scope.py` if that module is a better fit — check which is more
      consistent with existing organization before choosing) —
      `intersect_files_with_range(files_glob: str, changed_paths: Sequence[str], cwd: str) -> list[str]`.
- [ ] Resolves the glob against `cwd`, intersects with `changed_paths`
      (already known from the `FetchedRange`, no second git call).
- [ ] An empty intersection raises `EmptyScopeError`
      ([git_utils.py:135](src/squadron/review/git_utils.py#L135)) — it
      already carries `case`, matched patterns, and excluded-file-count as
      structured fields for exactly this "nothing to review" situation; add
      whatever `case` value or fields best describe "glob matched nothing in
      range" rather than defining a second error type for the same failure
      shape. Message names both the glob and the range.
- [ ] Effort: 2

### Task E.2 — Test: intersection semantics

- [ ] A glob matching some changed paths and some non-changed paths returns
      only the intersection.
- [ ] A glob matching nothing in the range raises, naming the glob and the
      range in the error.
- [ ] A glob matching everything in the range returns the full changed-path
      list unchanged.
- [ ] Effort: 2

### Task E.3 — Commit Part E

- [ ] `uv run pytest tests/review -q`; ruff; pyright.
- [ ] Commit: `feat(review): intersect --files with the PR range rather than replacing it`
- [ ] Effort: 1

---

## Task Review Disposition

Task review
(`382-review.tasks.review-a-pr.part-2.md`, claude-sonnet-5, CONCERNS,
20260913, sha `78ccf3bb`), reviewing this file. One concern and two notes
actioned; three pass findings, no action.

- **F001 (concern) — accepted, the substantive one.** Task D.3 told the
  implementer to truncate `_pr_block`'s content "through the existing size
  discipline" without saying how the builder — a pure, config-free module
  with zero imports beyond `from __future__ import annotations` — would
  obtain the `max_file_size` integer `_truncate` requires. Verified both
  claims directly: `builders/code.py` has no other imports, and
  `_inject_file_contents` resolves the cap itself via `get_config(...,
  cwd=cwd_for_config)`, a pattern the builder does not follow for any other
  value (`diff_exclude_patterns` arrives pre-resolved as a plain string via
  `inputs`, never fetched by the builder). Also verified the reviewer's
  implicit premise that reusing `_truncate` would create a
  `review_client ↔ builders` cycle: it would not — `review_client.py` never
  imports `builders/code.py` at all; the builder is loaded at runtime by the
  dotted path `code.yaml` names, not a Python `import`. Task D.3 now
  threads a pre-resolved `inputs["pr_max_bytes"]` (the CLI resolves it,
  matching the `diff_exclude_patterns` precedent) and imports `_truncate`
  directly from `review_client` — a new one-directional edge, not a cycle.
  Task D.4 gained a case for the missing-cap error path.
- **F002 (note) — accepted.** File 1's Part B intro said the `pr` input key
  "lands in file 2's Part C"; file 2 has no Part C — it starts at Part D.
  Fixed in file 1.
- **F006 (note) — partially accepted.** Of the two placement decisions this
  finding named, D.3's is now resolved by F001's fix above (no ambiguity
  remains — the mechanism is stated exactly). E.1's module-placement choice
  (`rules.py` vs. a new `review/scope.py`) is left as an implementer
  decision with a stated procedure, since it is a genuinely minor
  organizational call with no security or correctness weight — consistent
  with the reviewer's own assessment that it is "low-risk."
- **F003 (pass)** — D4/D7 scope is tight, no scope creep. No action.
- **F004 (pass)** — code anchors are accurate. No action.
- **F005 (pass)** — test-with pattern and commit checkpoints. No action.

---

**Continues in
[382-tasks.review-a-pr-3.md](project-documents/user/tasks/382-tasks.review-a-pr-3.md)**
— `_warn_not_persistable`'s reason parameter (D6), the `sq review pr`
subcommand tying files 1 and 2's pieces together (D2, D5), full flag parity,
live evidence, and closeout. The Context Summary, verified anchors,
corrections, and standing constraints in file 1 govern this file too.
