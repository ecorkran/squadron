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

# Tasks: Review Artifact Integrity (1 of 2)

## Context Summary

Parts 1–3 of six; Parts 4–6 are in `917-tasks.review-artifact-integrity-2.md`.
Six changes that stop a review artifact from lying: an invalid verdict is
rejected at commit; finding-shaped text that is not a finding is not parsed;
a cited line past the end of its file is recorded as such; a provider failure
leaves an artifact instead of nothing; every artifact carries a run digest; and
the debug log's misnamed field is renamed. Issues
[#87](https://github.com/ecorkran/squadron/issues/87),
[#77](https://github.com/ecorkran/squadron/issues/77),
[#91](https://github.com/ecorkran/squadron/issues/91),
[#25](https://github.com/ecorkran/squadron/issues/25),
[#84](https://github.com/ecorkran/squadron/issues/84),
[#26](https://github.com/ecorkran/squadron/issues/26),
[#93](https://github.com/ecorkran/squadron/issues/93).

Sequenced **1 → 2 → 3 → 4 → 5 → 6** per the design. Parts 1 and 2 are
self-contained; 3 is the live bug and changes what 4–6 reason about; 5 runs on
the findings 3 leaves; 6 renders the counts 3 computes. Parts 3 and 6 land in
the same branch. Each part is independently committable.

Branch: `917-slice.review-artifact-integrity` from `main` (no integration
branch configured). Merge to `main` when Part 6 is verified.

### Verified code anchors (traced on `e6e7a86`, 20260912)

| Anchor | Location |
|---|---|
| `_write_debug_log` — `fallback_used` param and JSON key | [parsers.py:416-434](src/squadron/review/parsers.py#L416-L434) |
| `_write_debug_log` call sites (three) | [:493](src/squadron/review/parsers.py#L493), [:518](src/squadron/review/parsers.py#L518), [:540](src/squadron/review/parsers.py#L540) |
| `_FINDING_RE.finditer` over the whole text | [parsers.py:356](src/squadron/review/parsers.py#L356) |
| `_SUMMARY_RE` | [parsers.py:68](src/squadron/review/parsers.py#L68) |
| `location_path` / `_LOCATION_PATH_RE` | [parsers.py:238](src/squadron/review/parsers.py#L238), [:38](src/squadron/review/parsers.py#L38) |
| `_path_exists_under` (returns bool, not the path) | [parsers.py:287](src/squadron/review/parsers.py#L287) |
| `_check_path_existence` (runs only with `cwd`) | [parsers.py:310](src/squadron/review/parsers.py#L310) |
| `parse_review_output(..., diff_files, cwd)` | [parsers.py:443](src/squadron/review/parsers.py#L443) |
| `ReviewFinding`, `ReviewResult` (`provenance` precedent) | [models.py:46](src/squadron/review/models.py#L46), [:55](src/squadron/review/models.py#L55) |
| `format_review_markdown` frontmatter block | [persistence.py:210-238](src/squadron/review/persistence.py#L210-L238) |
| `degraded` computation | [persistence.py:198](src/squadron/review/persistence.py#L198) |
| `### Raw Response` (degraded only) | [persistence.py:314](src/squadron/review/persistence.py#L314) |
| `save_review_file` → `archive_existing_review` | [persistence.py:412](src/squadron/review/persistence.py#L412), [:354](src/squadron/review/persistence.py#L354) |
| `FrontmatterGateAction` — shape to copy | [frontmatter_gate.py:31](src/squadron/events/builtin/frontmatter_gate.py#L31) |
| Built-in import list | [events/__init__.py:99-102](src/squadron/events/__init__.py#L99-L102) |
| `read_frontmatter` (returns `None` when absent; raises `FrontmatterError`) | [frontmatter.py:60](src/squadron/documents/frontmatter.py#L60) |
| CLI catch-all in `_run_review_command` | [cli/commands/review.py:627](src/squadron/cli/commands/review.py#L627) |
| `slice_info` in scope in `review_slice` before the run | [cli/commands/review.py:690](src/squadron/cli/commands/review.py#L690) |
| `review_arch` builds `arch_slice_info` after the run | [cli/commands/review.py:800](src/squadron/cli/commands/review.py#L800) |
| Pipeline catch-all in `execute` | [actions/review.py:92](src/squadron/pipeline/actions/review.py#L92) |
| Pipeline model call, `slice_info` in scope | [actions/review.py:238](src/squadron/pipeline/actions/review.py#L238), [:169](src/squadron/pipeline/actions/review.py#L169) |
| `_require_final_content` raises `ProviderError` | [agent.py:67](src/squadron/providers/openai/agent.py#L67) |
| `tool_calls_made` in scope at the raise site | [agent.py:393](src/squadron/providers/openai/agent.py#L393), [:432](src/squadron/providers/openai/agent.py#L432) |
| Specimen `### [PASS\|CONCERN\|FAIL] Finding title` (six templates) | `code.yaml:49`, `slice.yaml:52`, `tasks.yaml:52`, `arch.yaml:105`, `judge-slice-vs-arch.yaml:44`, `judge-tasks-vs-slice.yaml:43` |
| `{input}` / `{against}` substitution lines | `slice.yaml:75-76`, `tasks.yaml:75-76`, `arch.yaml:127`, `judge-slice-vs-arch.yaml:86-87`, `judge-tasks-vs-slice.yaml:86-87` |
| `code_review_prompt` builder | [builders/code.py:6](src/squadron/review/builders/code.py#L6) |
| Headingless real responses (fixtures already in tree) | `tests/review/fixtures/267-review.code.*T125359.md`, `267-review.tasks.*T194649.md` |
| Snapshot test for a clean artifact | [test_persistence.py:824](tests/review/test_persistence.py#L824) |
| Built-in bindings table | [docs/EVENTS.md:196-202](docs/EVENTS.md#L196-L202) |
| `events/builtin/` listing | [140-arch.pipeline-foundation.md:589](project-documents/user/architecture/140-arch.pipeline-foundation.md#L589) |

### Standing constraints

- No new `Verdict` member. No new `DocumentStatus` value.
- `ReviewResult.fallback_used`, `location_path()`, and the frontmatter key set
  of a normal artifact do not change.
- Every new failure path logs at WARNING or above. `None` on
  `location_verified` is always accompanied by a WARNING naming the finding
  and the reason.
- Message text is never asserted as logical structure; tests assert on
  `ActionResult.success`, exit codes, enum values, and field values.
- Tests never write to the real `review-debug.jsonl` (conftest already
  monkeypatches `_DEBUG_LOG_PATH`).
- Before each commit: `uv run ruff format`, `uv run ruff check`,
  `uv run pyright` — zero errors.

---

## Part 1 — Rename the debug-log field (#87)

### Task 1.1 — Rename the parameter and JSON key

- [ ] In `_write_debug_log` ([parsers.py:416](src/squadron/review/parsers.py#L416))
      rename the `fallback_used` keyword parameter to `degraded` and the emitted
      JSON key `"fallback_used"` to `"degraded"`.
- [ ] Update the three call sites ([:493](src/squadron/review/parsers.py#L493),
      [:518](src/squadron/review/parsers.py#L518),
      [:540](src/squadron/review/parsers.py#L540)) to pass `degraded=True`.
- [ ] Do not touch `ReviewResult.fallback_used`, its `to_dict` key, or the local
      `fallback_used` variable in `parse_review_output`.
- [ ] Success: `grep -n "fallback_used" src/squadron/review/parsers.py` shows only
      the `parse_review_output` local and the `ReviewResult(...)` constructor arg.
- [ ] Effort: 1

### Task 1.2 — Test: the emitted line carries `degraded`

- [ ] In `tests/review/test_parsers.py`, add a test that parses a response with
      no `## Summary` and no findings (the genuinely-unknown branch), reads the
      last line of the monkeypatched debug log as JSON, and asserts the key
      `degraded` is present and `True` and the key `fallback_used` is absent.
- [ ] Assert the returned `ReviewResult.fallback_used` is `False` for that same
      parse (the existing semantics), and `to_dict()` still carries
      `"fallback_used"`.
- [ ] Effort: 1

### Task 1.3 — Verify and commit Part 1

- [ ] `uv run pytest tests/review -q` green; format, check, pyright clean.
- [ ] Commit: `refactor(review): rename debug-log fallback_used field to degraded`
- [ ] Effort: 1

---

## Part 2 — Reject invalid verdicts at commit (#77)

### Task 2.1 — Create the gate action

- [ ] Read `FrontmatterGateAction` ([frontmatter_gate.py](src/squadron/events/builtin/frontmatter_gate.py))
      and `read_frontmatter` ([frontmatter.py:60](src/squadron/documents/frontmatter.py#L60))
      for the return/raise contract before writing code.
- [ ] Create `src/squadron/events/builtin/review_verdict_gate.py` with class
      `ReviewVerdictGateAction`: `name = "squadron.review-verdict-gate"`,
      `events = frozenset({EventType.COMMIT})`, `validate` returns `[]`.
- [ ] `execute` iterates `context.staged_paths` ending in `.md`, resolved under
      `context.cwd`. For each: `read_frontmatter` returns `None` → skip;
      `docType` != `DocType.REVIEW` → skip; `FrontmatterError` (or any read
      failure) → violation "could not read frontmatter"; no `verdict` key →
      violation; `verdict` value not in `{v.value for v in Verdict}` → violation
      naming the file, the value, and the allowed set computed from the enum.
- [ ] One `ActionResult`: `success=True` when no violations; otherwise
      `success=False`, `error` joining all violations, and one `_logger.warning`
      per violation. Message templates are module-level constants.
- [ ] No literal list of verdict strings anywhere in the module.
- [ ] Register with `register_event_action(ReviewVerdictGateAction())` at module
      bottom, as the frontmatter gate does.
- [ ] Effort: 2

### Task 2.2 — Wire the built-in import

- [ ] Add the import and the `_ = (...)` reference in
      [events/__init__.py:99-102](src/squadron/events/__init__.py#L99-L102)
      next to `_b_frontmatter_gate`.
- [ ] Success: `uv run sq events list` (or the registry's list function) shows
      `squadron.review-verdict-gate` bound to `commit`.
- [ ] Effort: 1

### Task 2.3 — Test: the gate

- [ ] Create `tests/events/builtin/test_review_verdict_gate.py` mirroring
      `test_frontmatter_gate.py`'s `_commit_context` helper; write probe files
      under `tmp_path`.
- [ ] Cases: identity (name, events); `verdict: BANANA` → `success=False` and
      `error` contains `BANANA` and every `Verdict` member (iterate the enum in
      the assertion; do not spell the four values); `verdict: RESOLVED` →
      rejected; each `Verdict` member → `success=True`; `docType: review` with no
      `verdict` → rejected; `docType: slice-design` with `verdict: BANANA` →
      `success=True`; a `.md` with no frontmatter → `success=True`; a file with
      unparseable frontmatter → rejected; a non-`.md` staged path → ignored.
- [ ] One test with two staged files, one bad, asserts the result names the bad
      file and not the good one.
- [ ] Effort: 2

### Task 2.4 — Corpus dry run

- [ ] Run the gate over every `project-documents/user/reviews/**/*.md` (a
      throwaway script or a one-off test invocation, not committed). Expected:
      exactly two violations, both hand-edited historical artifacts already known
      — `reviews/343-review.tasks.sq-skills-uninstall-and-sq-doctor-integration.md`
      and `reviews/archive/266-review.tasks.tool-use-configuration-and-limits.md`,
      both `verdict: RESOLVED`. Leave them; the gate runs on staged files only and
      history is not rewritten.
- [ ] Any *other* violation is a finding: record it in DEVLOG and fix the artifact
      only if this slice produced it.
- [ ] Effort: 1

### Task 2.5 — Documentation deliverables

- [ ] Add a `commit` / `squadron.review-verdict-gate` row to the built-in
      bindings table in [docs/EVENTS.md:198](docs/EVENTS.md#L198).
- [ ] Add `review_verdict_gate.py  # COMMIT — rejects a review whose verdict is
      not a Verdict member` to the `builtin/` listing in
      [140-arch.pipeline-foundation.md:589](project-documents/user/architecture/140-arch.pipeline-foundation.md#L589).
- [ ] Add a CHANGELOG `### Added` bullet under `[Unreleased]`: committing a
      review artifact whose `verdict:` is missing or not one of the review
      verdicts is now rejected; disable with `squadron.review-verdict-gate` in
      `events.yaml` (#77).
- [ ] Effort: 1

### Task 2.6 — Verify and commit Part 2

- [ ] `uv run pytest tests/events -q` green; format, check, pyright clean.
- [ ] Manual: stage a `docType: review` probe with `verdict: BANANA`; commit is
      rejected naming `BANANA`; change to `CONCERNS`, commit proceeds; remove the
      probe commit (`git reset --soft HEAD~1`, unstage, delete the probe).
- [ ] Commit: `feat(events): add review-verdict-gate commit action`
- [ ] Effort: 1

---

## Part 3 — Stop parsing finding-shaped text that is not a finding (#91, #25)

### Task 3.1 — Carry the scan facts on `ReviewResult`

- [ ] In [models.py](src/squadron/review/models.py) add a frozen dataclass
      `FindingScanCounts` with `total: int` (matches in the whole response),
      `in_fences: int`, `in_section: int`, `surviving: int`.
- [ ] Add to `ReviewResult`, defaulted, after `provenance`:
      `summary_section_located: bool | None = None`,
      `findings_section_located: bool | None = None`,
      `finding_scan: FindingScanCounts | None = None`. `None` means "not produced
      by the parser" (e.g. a hand-built result), same convention as `provenance`.
- [ ] `to_dict()` unchanged. A comment on the fields says they feed the Part 6
      digest and nothing else.
- [ ] Effort: 1

### Task 3.2 — Mask fenced code blocks

- [ ] In `parsers.py` add `_mask_fences(text) -> str` that replaces the contents
      of every fenced block (``` or ~~~ opener at line start, optional info
      string, lenient leading whitespace, closed by a matching fence or EOF) with
      spaces, preserving every newline so character offsets and line numbers of
      unfenced text are unchanged.
- [ ] Add `_count_finding_matches(text) -> int` = `len(list(_FINDING_RE.finditer(text)))`.
      `in_fences` = count on raw text minus count on masked text.
- [ ] Effort: 2

### Task 3.3 — Locate the findings section

- [ ] Add `_locate_findings_section(masked_text) -> tuple[int, int] | None`.
      Heading match is lenient: any `#`-level heading whose text, after
      stripping `*`, `_`, backticks, trailing `:`/`.`, and whitespace, equals
      `findings` case-insensitively. Span runs from the end of the heading line
      to the next heading of the same or higher level (fewer or equal `#`), or
      EOF. `###` finding headings inside the section must not terminate it.
- [ ] Add `_locate_summary_section(masked_text) -> bool` using the same heading
      rule for `summary`; feeds `summary_section_located`.
- [ ] Effort: 2

### Task 3.4 — Wire the bounded scan into the parser

- [ ] Change `_extract_findings` to scan the masked text bounded to the section
      when one is located, and the whole masked text otherwise. Return the
      findings **and** a `FindingScanCounts`, with `in_section` equal to the
      matches in the bounded region (equal to the masked-whole count when no
      section exists) and `surviving` equal to `len(findings)`.
- [ ] In `parse_review_output` set `finding_scan`, `findings_section_located`,
      and `summary_section_located` on the returned `ReviewResult`. Log one
      WARNING when the section is not located, naming template and model.
- [ ] `findings_section_located=False` does **not** change `fallback_used` and
      does not touch the `degraded` computation at
      [persistence.py:198](src/squadron/review/persistence.py#L198).
- [ ] Success: `_FINDING_RE.finditer` appears in exactly one place
      (`_count_finding_matches`) plus the bounded scan.
- [ ] Effort: 2

### Task 3.5 — Test: the bounded scan

- [ ] In `tests/review/test_parsers.py` add a helper that returns the text after
      `### Raw Response` from a fixture file, and use it on the two headingless
      fixtures `267-review.code.*T125359.md` and `267-review.tasks.*T194649.md`:
      each parses to 6 findings, `findings_section_located is False`,
      `fallback_used is False`, and `format_review_markdown` of the result does
      not contain `### Raw Response`.
- [ ] Fenced specimen (the six-line block from `code.yaml:44-51` inside ```)
      followed by nothing → 0 findings, `in_fences == total`.
- [ ] Specimen echoed **unfenced** before a `## Findings` heading, then two real
      findings → 2 findings, `total == 3`, `in_section == 2`.
- [ ] Text after a `## Next Steps` heading that follows `## Findings` is not
      parsed; text under `### Sub` inside `## Findings` is.
- [ ] Heading variants each located: `## Findings`, `## **Findings**`,
      `### findings:`, `## Findings.`, `##   Findings   `.
- [ ] All five finding shapes still parse inside the section (extend the existing
      five-shape test, do not duplicate it).
- [ ] `~~~` fences are masked; an unclosed fence masks to EOF.
- [ ] Go through every existing `test_parsers.py` test that feeds finding-shaped
      text with no `## Findings` heading and confirm each still passes for the
      right reason (whole-text fallback). Do not bulk-edit fixtures.
- [ ] Effort: 2

### Task 3.6 — Fence the specimen and delimit substituted content (#25)

- [ ] In each of the six templates, wrap the specimen block (`## Summary` line
      through the `Description ...` line) in a ``` fence inside `system_prompt`.
      Precede it with one sentence: "Use exactly this structure; do not repeat
      this block in your response."
- [ ] Wrap substituted content in descriptive XML tags in each `prompt_template`:
      `slice.yaml` `<slice_document>`/`<architecture_document>`; `tasks.yaml`
      `<task_file>`/`<slice_design>`; `arch.yaml` `<architecture_document>`;
      `judge-slice-vs-arch.yaml` and `judge-tasks-vs-slice.yaml` the same tags
      as their review counterparts. Keep the bold label line above each tag.
- [ ] In `code_review_prompt` ([builders/code.py:6](src/squadron/review/builders/code.py#L6))
      wrap the scoping paragraph in `<scope>` and the reporting directive in
      `<output_format>`.
- [ ] Effort: 2

### Task 3.7 — Test: templates

- [ ] In `tests/review/test_templates.py` add one parametrized test over the six
      templates: `_extract_findings` on the loaded `system_prompt` yields zero
      findings (the specimen no longer parses as a finding).
- [ ] In `tests/review/test_template_inputs.py` (or the builder's test) assert
      the rendered user prompt for `slice`, `tasks`, `arch`, and `code` contains
      the opening and closing tag around the substituted content, and that the
      substituted text sits between them.
- [ ] Effort: 1

### Task 3.8 — Verify and commit Part 3

- [ ] `uv run pytest tests/review -q` green; format, check, pyright clean.
- [ ] Manual: `uv run sq review slice 916 -vv --model kimi27 --no-save` three
      times; no `Finding title` / `src/module.py` phantom and no path-existence
      WARNING on any run.
- [ ] Commit: `fix(review): bound finding parse to the findings section and skip fences`
- [ ] Effort: 1
