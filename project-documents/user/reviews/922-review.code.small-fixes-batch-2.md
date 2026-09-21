---
docType: review
layer: project
reviewType: code
slice: small-fixes-batch-2
project: squadron
verdict: PASS
verdictSource: stated
sourceDocument: project-documents/user/slices/922-slice.small-fixes-batch-2.md
aiModel: moonshotai/kimi-k3
status: complete
dateCreated: 20260921
dateUpdated: 20260921
reviewedSha: dc2e2b636151811853672fcf1a2872bdf1a6d88a
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 25
findings:
  - id: F001
    severity: pass
    category: design
    summary: "sdk_type literals centralized per the one-value-one-source rule"
    location: "src/squadron/core/models.py"
  - id: F002
    severity: pass
    category: error-handling
    summary: "ProcessCwdNotFoundError classification is correct, documented, and tested"
    location: "src/squadron/core/process_runner.py:120-129"
  - id: F003
    severity: note
    category: correctness
    summary: "cf-scope predicate assumes repo-root-relative staged paths"
    location: "src/squadron/events/builtin/frontmatter_gate.py:39-50"
  - id: F004
    severity: note
    category: testing
    summary: "Smoke test hand-parses requirement markers"
    location: "tests/test_smoke.py#_declared_dependency_names"
  - id: F005
    severity: pass
    category: logging
    summary: "Jail exclusion/escape log-level split (D6) is consistent and fully pinned"
    location: "src/squadron/tools/builtin/_shared.py"
  - id: F006
    severity: pass
    category: structure
    summary: "Placeholder module deletions leave no dangling references"
    location: "src/squadron/adk/__init__.py"
---

# Review: code — slice 922

**Verdict:** PASS
**Model:** moonshotai/kimi-k3

## Findings

### [PASS] sdk_type literals centralized per the one-value-one-source rule

`TOOL_USE_TYPE`/`TOOL_RESULT_TYPE` replace scattered `"tool_use"`/`"tool_result"` literals across the writer (`providers/sdk/translation.py`) and all four readers shown in the diff (`audit.py`, `sdk_session.py`, `summary_oneshot.py`, `review_client.py`). This directly implements the project convention that a comparison value be defined once and referenced everywhere. The accompanying comment records why (#108). One caveat I could not verify within scope: whether any literal occurrences survive outside the files in this diff.

### [PASS] ProcessCwdNotFoundError classification is correct, documented, and tested

Classifying `FileNotFoundError` after the fact (rather than pre-statting `cwd`) keeps the success path stat-free and avoids a check-then-use gap; the comment says exactly that. The three-way test coverage is complete: missing cwd → `ProcessCwdNotFoundError` naming the directory, missing executable with valid cwd → `ProcessNotFoundError`, missing executable with `cwd=None` → `ProcessNotFoundError`. The deliberate non-subclassing is the right call — a missing cwd is a configuration error, and `github_cli.py`'s existing `except ProcessNotFoundError` must not translate it into "gh is not on PATH". The explicit catch-and-re-raise in `github_cli.py:491` adds a second WARNING for one event, but that matches the established double-layer logging pattern already used for timeout and not-found in the same function.

### [NOTE] cf-scope predicate assumes repo-root-relative staged paths

`_is_under_cf_document_root` is documented as receiving repo-root-relative paths "as the pre-commit hook passes it", and for that caller the assumption holds (git supplies repo-relative paths, and the `./`-prefixed case is normalized by `PurePosixPath` and pinned by a test). However, `sq events fire` (`cli/commands/events.py:44`) forwards user-supplied path arguments verbatim, so an absolute or `..`-prefixed spelling of an in-scope file would be counted as out of scope — and if cf also checks 0 files, the gate now passes where it previously failed closed. In practice cf receives the same spelling and would likely check (or error on) the file, making `filesChecked: 0` unlikely in that scenario, and the constant carries an upstream removal condition (ecorkran/context-forge#96). Worth keeping in mind if the fire-path ever becomes automated.

### [NOTE] Smoke test hand-parses requirement markers

`_declared_dependency_names` filters extras with the substring check `"extra =="` and extracts names with a hand-rolled regex. This works against installed metadata (backends normalize marker spacing), and a missed filter fails loudly rather than silently, so the risk is low. Using `packaging.requirements.Requirement(req).marker` would parse the semantic content instead of the formatting, per the project's parsing rule — a small robustness improvement if this test ever grows more assertions. The asserted names (`rich`, `mcp`, `anthropic`, `google-adk`) contain no separator characters, so PEP 503 normalization differences cannot cause false results today.

### [PASS] Jail exclusion/escape log-level split (D6) is consistent and fully pinned

The WARNING→DEBUG demotion for policy exclusions is applied at both logging sites (`contained_in_jail` and `jail_violation`), all three docstrings (`resolve_in_jail`'s included) were updated to tell the same story, and the tests pin exactly-one-record at the assigned level for each refusal kind at each site — including "nothing at INFO+" for exclusions. Jail escapes correctly stay at WARNING, preserving the security-relevant signal; the demoted case is deterministic policy working as designed, so the Failure-Mode Enumeration rule's WARNING+ requirement is arguably satisfied by the escape path alone. The recorded rationale (avoiding `-v` review-output flooding) is sound.

### [PASS] Placeholder module deletions leave no dangling references

The deleted `adk`, `mcp`, and `providers/anthropic` placeholder packages are not imported anywhere under `src/` (verified by grep), and the new `test_declared_dependencies_match_what_src_imports` smoke test mechanically guards the corresponding dependency declarations (`anthropic`, `google-adk` out; `rich`, `mcp` in), reading the installed distribution's own metadata rather than hand-parsing `pyproject.toml` — the test asserts against what a real install resolved.

### Run Digest

- Response length: 5815 chars
- Response is newline-free: no
- Tool calls made: 25
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 23845
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6

## Response (20260921)

Both NOTE findings verified against the actual code and confirmed real.

**F003 (cf-scope predicate assumes repo-root-relative staged paths).** Confirmed: `sq events fire` (`cli/commands/events.py:44`) forwards user-supplied paths verbatim into `staged_paths`, with no normalization, so an absolute or `..`-prefixed spelling of a genuinely in-scope path defeats `_is_under_cf_document_root`'s parts comparison — verified directly (`PurePosixPath('/repo/project-documents/user/x.md').parts[:2]` is `('/', 'repo')`, not `('project-documents', 'user')`). Not fixed in this slice, since the only current caller (the pre-commit hook) always passes repo-relative paths and is unaffected. Filed as [squadron#122](https://github.com/ecorkran/squadron/issues/122) as a follow-up.

**F004 (smoke test hand-parses requirement markers).** Fixed. `tests/test_smoke.py::_declared_dependency_names` now parses each requirement string with `packaging.requirements.Requirement` (name + marker) instead of a substring check on `"extra =="` plus a hand-rolled regex — the project's parsing rule prefers parsing semantic content over matching formatting, and this closes that gap even though today's risk was low (`importlib.metadata` happens to normalize marker spacing consistently). `packaging` added to `[dev]` in `pyproject.toml` as an explicit dependency rather than relying on it arriving transitively; `uv.lock` regenerated (no new packages — already resolved). Test still passes; full gate (`ruff format --check`, `ruff check`, `pyright`, `pytest`) clean.
