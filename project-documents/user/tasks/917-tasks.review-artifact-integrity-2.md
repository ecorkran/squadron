---
docType: tasks
slice: review-artifact-integrity
project: squadron
lldReference: project-documents/user/slices/917-slice.review-artifact-integrity.md
parent: project-documents/user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: [916]
interfaces: []
status: not_started
dateCreated: 20260912
dateUpdated: 20260912
---

# Tasks: Review Artifact Integrity (2 of 2)

## Context Summary

Parts 4–6 of six. Context, verified code anchors, standing constraints, and
Parts 1–3 are in `917-tasks.review-artifact-integrity-1.md`; read its anchor
table and constraints before starting here. Part 3 must be complete and
committed first: Parts 5 and 6 consume the fields it adds to `ReviewResult`.

---

## Part 4 — Persist a failure artifact when the provider fails (#84)

### Task 4.1 — Carry tool telemetry on the provider error

- [ ] Add `tool_calls_made: int | None = None` to `ProviderError`
      ([errors.py:6](src/squadron/providers/errors.py#L6)) as a keyword-only
      constructor argument, defaulted so every existing raise is unchanged.
- [ ] `_require_final_content` ([agent.py:67](src/squadron/providers/openai/agent.py#L67))
      takes `tool_calls_made` and passes it into the error; update both call
      sites ([:222](src/squadron/providers/openai/agent.py#L222) passes `0`,
      [:432](src/squadron/providers/openai/agent.py#L432) passes the loop's
      counter).
- [ ] Test in `tests/providers/openai/test_agentic_loop.py::TestEmptyFinalTurn`:
      the raised error's `tool_calls_made` equals the number of tool calls the
      fake loop made.
- [ ] Effort: 1

### Task 4.2 — Extract the frontmatter block and add the failure writer

- [ ] Extract [persistence.py:210-238](src/squadron/review/persistence.py#L210-L238)
      into `_review_frontmatter_lines(...)` taking the already-resolved values
      (verdict, model, review_type, slice fields, source_doc, today, reviewed_sha,
      revision_number, tools_given, tool_calls_made). `format_review_markdown`
      calls it; the snapshot test at
      [test_persistence.py:824](tests/review/test_persistence.py#L824) must pass
      byte-for-byte.
- [ ] Add `format_provider_failure_markdown(exc: ProviderError, review_type,
      slice_info, *, model, source_document, tools_given, reviewed_sha)`:
      frontmatter via the helper with `verdict=Verdict.UNKNOWN.value` and
      `status: complete`; telemetry keys only when `tools_given is not None`,
      with `toolCallsMade` from `exc.tool_calls_made` (`0` when `None`); body is
      `# Review: {review_type} — slice {index}`, `**Verdict:** UNKNOWN`,
      `**Model:** ...`, then `## Provider Failure` with one sentence stating the
      provider raised before any response was delivered and `str(exc)` verbatim
      (it carries `finish_reason` and `reasoning_chars`). No `## Findings`.
- [ ] Add `save_provider_failure(...)` that formats and writes through
      `save_review_file` (so `archive_existing_review` runs). Returns the path or
      `None`; a `None` is logged at WARNING by `save_review_file` already.
- [ ] Effort: 2

### Task 4.3 — Test: the failure artifact

- [ ] In `tests/review/test_persistence.py`: the formatted failure artifact has
      `docType: review`, `verdict: UNKNOWN`, `status: complete`, a
      `## Provider Failure` section containing the error text, and no
      `## Findings`; with `tools_given=["read_file"]` and
      `exc.tool_calls_made=2` it carries `toolsGiven` and `toolCallsMade: 2`;
      with `tools_given=None` neither key appears.
- [ ] `save_provider_failure` over a pre-seeded live artifact moves the old
      content into `reviews/archive/` and the live slot holds the failure.
- [ ] `ReviewVerdictGateAction` run on the saved failure artifact returns
      `success=True`.
- [ ] Effort: 1

### Task 4.4 — CLI path

- [ ] Add `failure_target: SliceInfo | None = None`, `review_type: str`, and
      `no_save: bool` parameters to `_run_review_command`
      ([:548](src/squadron/cli/commands/review.py#L548)); it owns the catch-all.
- [ ] Before the `except Exception` catch-all
      ([:627](src/squadron/cli/commands/review.py#L627)) add
      `except ProviderError as exc`: print the error; when `failure_target` is
      set and `no_save` is false, call `save_provider_failure` with the resolved
      model, the template's tool list (or `None` when tools were withheld) and
      `resolve_reviewed_sha(cwd)`, print the saved path; `raise typer.Exit(code=1) from exc`.
- [ ] Pass `failure_target=slice_info`, `review_type`, and `no_save` from
      `review_slice`, `review_tasks`, and `review_code`. In `review_arch`, build
      `arch_slice_info` ([:800](src/squadron/cli/commands/review.py#L800))
      **before** the run so it can be passed too.
- [ ] Effort: 2

### Task 4.5 — Test: CLI path

- [ ] In `tests/review/test_cli_review.py`: patch `_execute_review` to raise
      `ProviderError("Model returned an empty final turn (finish_reason='length', reasoning_chars=1200)", tool_calls_made=0)`;
      invoke `review slice N` with a temp reviews dir and a resolvable slice.
      Assert exit code 1, the artifact exists with `verdict: UNKNOWN` and the
      `## Provider Failure` section, and a pre-seeded prior artifact is in
      `archive/`.
- [ ] Same with `--no-save`: exit 1, no artifact written.
- [ ] Same for `review arch` with an initiative index: artifact written.
- [ ] Effort: 2

### Task 4.6 — Pipeline path

- [ ] In `_review` ([actions/review.py:238](src/squadron/pipeline/actions/review.py#L238))
      wrap the `run_review_with_profile` call: `except ProviderError as exc` →
      call `save_provider_failure` using `slice_info` when present, else the
      step-name/index naming the existing save branch uses
      ([:283-300](src/squadron/pipeline/actions/review.py#L283-L300)); log at
      WARNING with the saved path; **re-raise**. The `execute` catch-all then
      produces the existing `success=False` result via `_exception_result`.
- [ ] Effort: 2

### Task 4.7 — Test: pipeline path and #92 boundary

- [ ] In `tests/review/test_review_action.py`: patch `run_review_with_profile`
      to raise `ProviderError(...)`; `execute` returns `success=False`; the
      failure artifact exists in the temp reviews dir; a pre-seeded prior
      artifact is archived.
- [ ] #92 boundary test in `test_parsers.py` + `test_persistence.py`: a
      3,000-character prose-only response (no `## Summary`, no findings block)
      parses to `verdict=UNKNOWN`, 0 findings, `findings_section_located False`,
      and its artifact carries `### Raw Response` through the **existing**
      degraded path — no `ProviderError` involved. Name the test after #92.
- [ ] Effort: 1

### Task 4.8 — Verify and commit Part 4

- [ ] `uv run pytest tests/review tests/providers tests/events -q` green;
      format, check, pyright clean.
- [ ] CHANGELOG `### Fixed`: a review whose model returns nothing now leaves an
      artifact naming the provider failure and why the model stopped, instead
      of no artifact (#84).
- [ ] Commit: `feat(review): persist a failure artifact when the provider fails`
- [ ] Effort: 1

---

## Part 5 — Bounds-check cited line numbers (#26)

### Task 5.1 — Model field and line extraction

- [ ] Add `location_verified: bool | None = None` to `ReviewFinding`
      ([models.py:46](src/squadron/review/models.py#L46)) with a comment giving
      the tri-state meaning. Not added to `StructuredFinding`, `to_dict`, or
      frontmatter.
- [ ] In `parsers.py` add `location_line(location: str) -> int | None` beside
      `location_path`: `path:42` → 42; `path:42-50` → 50 (the last cited line
      is the one that must exist); `path#symbol`, bare `path`, and
      `UNVERIFIED_LOCATION` → `None`. `location_path` is not modified.
- [ ] Test in `test_parsers.py`: the five cases above; every existing
      `location_path` test passes untouched.
- [ ] Effort: 1

### Task 5.2 — Resolution and bounded line count

- [ ] Refactor `_path_exists_under` ([parsers.py:287](src/squadron/review/parsers.py#L287))
      to delegate to a new `_resolve_under(root, path) -> Path | None` that
      returns the resolved path (direct join, or the single basename hit) and
      `None` when nothing resolves. Behavior of `_path_exists_under` unchanged.
- [ ] Add module constant `_MAX_LINE_CHECK_BYTES` (one place; pick 4 MiB) and
      `_count_lines(root, resolved) -> int | None`: return `None` with a WARNING
      when `resolved.resolve()` is not relative to `root.resolve()` (never open
      it), when it is a directory, when `stat().st_size` exceeds the cap, or on
      `OSError`. Otherwise open in binary mode and count `b"\n"` in streamed
      chunks; a final unterminated line counts.
- [ ] Effort: 2

### Task 5.3 — Wire the check

- [ ] Add `_check_line_bounds(findings, cwd, *, template_name)` called from the
      same place `_check_path_existence` is (only when `cwd` is supplied). For
      each finding: `location_line` is `None` → leave `None`; path does not
      resolve → `False` (the existing WARNING already fires; the file is
      verifiably absent); `_count_lines` returns `None` → leave `None`
      (WARNING already logged there); line > count → `False` with a WARNING
      naming finding, path, cited line, and actual count; otherwise `True`.
- [ ] Effort: 1

### Task 5.4 — Test: line bounds

- [ ] In `test_parsers.py`, all through `parse_review_output` with a `tmp_path`
      cwd holding a 10-line file: no `cwd` → every finding `None`;
      `file.py:999999` → `False`; `file.py:7` → `True`; `file.py:3-10` → `True`;
      `file.py:3-11` → `False`; `file.py` and `UNVERIFIED_LOCATION` → `None`;
      a nonexistent `ghost.py:3` → `False`.
- [ ] `None` with a WARNING (caplog) for: a directory citation `pkg:1`; an
      over-cap file (monkeypatch `_MAX_LINE_CHECK_BYTES` to 10); an unreadable
      file (chmod 000, skip when running as root); a `../outside.py:1` citation
      — for this one also assert the file was never opened (monkeypatch
      `Path.open` to raise).
- [ ] Synthetic #91 phantom `src/module.py:12` → `False`.
- [ ] Effort: 2

### Task 5.5 — Verify and commit Part 5

- [ ] `uv run pytest tests/review -q` green; format, check, pyright clean.
- [ ] Manual: `uv run sq review slice 916 -v --model kimi27 --no-save`; artifact
      output unchanged (field is write-only); no new WARNINGs on legitimate
      citations.
- [ ] Commit: `feat(review): record line-bounds verification on findings`
- [ ] Effort: 1

---

## Part 6 — Run digest on every artifact (#93)

### Task 6.1 — Render the digest

- [ ] In `persistence.py` add `_run_digest_lines(result) -> list[str]` producing
      a `### Run Digest` section: response length (chars); tool calls made
      (`not offered` when `tools_given is None`); `## Summary` located;
      `## Findings` located; finding-shaped matches — whole response / in
      fences / in section / surviving. When `finding_scan` is `None` (a result
      not produced by the parser) the count lines say `not computed`; the
      section is still emitted.
- [ ] Append it in `format_review_markdown` after the findings body and before
      the degraded `### Raw Response` and the `-vv` appendix, unconditionally.
      The formatter reads `result.finding_scan` only; it does not call the
      parser.
- [ ] Update `tests/review/fixtures/clean_pass_artifact.md` to the new output
      (this is the one intended snapshot change; review the diff by eye).
- [ ] Effort: 2

### Task 6.2 — Test: the digest

- [ ] In `test_persistence.py`: a PASS result carries `### Run Digest`; a result
      built with `finding_scan=FindingScanCounts(total=35, in_fences=30,
      in_section=5, surviving=5)` renders those four numbers (proves no
      re-parse); present at verbosity 0 and with `system_prompt` set; the
      degraded `### Raw Response` behavior is unchanged (existing tests).
- [ ] End-to-end in `test_parsers.py` + `test_persistence.py`: the synthetic
      echo-then-real response from Task 3.5 parsed then formatted shows a
      whole-response count greater than the surviving count.
- [ ] Effort: 1

### Task 6.3 — Close out the slice

- [ ] CHANGELOG `### Fixed`: review artifacts no longer report the template's own
      example as findings (#91); `### Added`: every review artifact carries a run
      digest (#93).
- [ ] DEVLOG entry for the slice under today's date: what shipped per part, the
      corpus dry-run result, the kimi27 rerun observations.
- [ ] Full suite `uv run pytest -q` green; format, check, pyright clean.
- [ ] Commit: `feat(review): add run digest to every review artifact`
- [ ] Merge `917-slice.review-artifact-integrity` into `main`; set this file and
      the slice design `status: complete`; update plan entry 15's status.
- [ ] Effort: 1
