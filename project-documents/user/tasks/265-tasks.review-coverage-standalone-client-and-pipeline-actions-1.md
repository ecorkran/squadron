---
docType: tasks
project: squadron
slice: 265-slice.review-coverage-standalone-client-and-pipeline-actions
lldReference: project-documents/user/slices/265-slice.review-coverage-standalone-client-and-pipeline-actions.md
parent: 260-slices.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md
dependencies: [261, 262, 263]
dateCreated: 20260901
dateUpdated: 20260901
status: complete
---

# Tasks: Review Coverage — Standalone Client and Pipeline Actions (1 of 2)

## Context Summary

Reviews were left behind by slices 261-264 on three fronts, all confirmed live in the current
code:

1. **Vocabulary mismatch (issue #68, still open).** All seven shipped templates in
   `src/squadron/data/templates/*.yaml` declare Claude vocabulary (`Read`, `Glob`, `Grep`,
   `Bash`). The non-SDK agent (`providers/openai/agent.py:125-134`) looks those names up in the
   squadron registry, finds nothing, logs a WARNING, and drops them — reviews on non-SDK models
   run tool-less today.
2. **Static injection flag.** `review_client.py:85-86` decides file-body injection on
   `provider.capabilities.can_read_files`, a per-provider constant that cannot see what tools a
   run actually has.
3. **Tool use is invisible.** Nothing in `ActionResult.metadata`, the `-v` log line, or
   persisted run/review state records that tools were offered or called.

**What already exists from slice 263 — do not redo this.** `pipeline/actions/dispatch.py`
already has `_resolve_allowed_tools` (405-420, reads `context.params["allowed_tools"]`,
validates `list[str]`, raises `ValueError` on malformed shape, no registry re-check) and
`one_shot_dispatch` already accepts and threads `allowed_tools` + `cwd` into `AgentConfig`
(41-84). `review.py` and `summary.py` have **no** such plumbing yet — both need it built.

**The metadata-discard point.** `one_shot_dispatch` joins the agent's response stream at
`dispatch.py:96-100`:
```python
response_parts: list[str] = []
async for response in agent.handle_message(message):
    if response.metadata.get("sdk_type") == SDK_RESULT_TYPE:
        continue
    response_parts.append(response.content)
...
return "".join(response_parts)
```
Only `sdk_type` is read from `response.metadata`; everything else, including any future
tool-call count, is discarded here. `one_shot_dispatch` returns a bare `str` and has other
callers, so its signature does not change — task 22 adds a sibling function that returns both
text and telemetry.

**Where translation and validation live today, with no changes yet:**
- `providers/sdk/provider.py:56-57` passes `AgentConfig.allowed_tools` straight into
  `ClaudeAgentOptions(**kwargs)` — no translation. This is the edge task 8 changes.
- `providers/openai/agent.py:125-134` is the warn-and-drop loop task 10 tightens to a raise.
- `core/models.py:65-74` — `Message.metadata: dict[str, Any]` already exists and defaults to
  `{}`; no model change needed to carry the new keys.
- `tools/limits.py` is a flat module of bare constants (`MAX_READ_BYTES`, `MAX_OUTPUT_BYTES`,
  `BASH_TIMEOUT_S`); `GREP_TIMEOUT_S` joins it the same way.
- `pipeline/schema.py` has no per-step-type Pydantic schema — `StepSchema.config` is a flat
  `dict[str, object]`. There is nothing to "extend" there; `allowed_tools` for review/summary
  is read the same ad hoc way `dispatch.py` already reads it, via a shared helper (task 14).
- `pipeline/executor.py:95-108`, `_log_action_result`, already renders `verdict=` and `model=`
  from `result.metadata`; task 25 appends one more `extras` block for `tools=N/M calls`.
- `review/models.py`, `ReviewResult` — no `tools_given`/`tool_calls_made` fields today; task 21
  adds them plus their `to_dict()` keys (verdict/findings/etc. are always included; the
  verbosity-gated fields `system_prompt`/`user_prompt`/`rules_content_used` are excluded from
  `to_dict()` today — the new fields follow the always-included group, not the gated one).

**Registered tools today**: `read_file`, `write_file`, `bash` (`tools/builtin.py:26-28`). No
`tests/tools/test_builtin.py` exists — individual tool tests are one file per tool
(`test_read_file.py`, `test_write_file.py`, `test_bash.py`, `test_jail.py`); the new `grep` tool
gets its own `tests/tools/test_grep.py` following that pattern, not a shared file. `list_files`
similarly gets `tests/tools/test_list_files.py`.

**New runtime dependency.** `regex` is not currently in `pyproject.toml`. It is a flat
`dependencies = [...]` list with no extras groups to gate optional tooling behind — `regex`
goes directly into that list (task 2).

**Sequencing.** Tasks build outward from the leaf pieces: new tools and their timeout
dependency first (1-2), then the tools themselves with tests plus a `tests/load/` timeout load
test (3-7), then the two provider-side vocabulary changes that make everything else meaningful
(8-11), then the injection decision (12-13) — this file ends here. Part 2 continues with
pipeline-action wiring for review and summary, each with its own paired test task (14-18),
observability threading (19-25), template migration (26-27, deliberately late because it
depends on the vocabulary fix actually working), then end-to-end verification and close-out
(28-30). Each task ends with its own commit — see Commit Protocol below.

**Commit protocol — applies to every task below.** Each task leaves the suite green and ends
with a commit rather than batching commits at close-out. For every task:

1. `uv run ruff format .` — immediately before the commit, never skipped
2. `git add` from the project root and commit with a semantic message
   (`feat:`, `test:`, `refactor:`, `chore:`, `docs:` — see CLAUDE.md Git Rules)
3. The relevant scoped test command passes first; a task is not done until it is committed

**Branch.** This is Phase 6 implementation work. `cf config get git.integration_branch` reads
empty (source: default), so the target is `main` and the branch is named
`265-slice.review-coverage-standalone-client-and-pipeline-actions`, forked from `main`. Re-read
the config value before creating the branch — do not assume the value recorded here is still
current.

---

## Task 1: `GREP_TIMEOUT_S` limit

- [x] **1.1** Add `GREP_TIMEOUT_S = 5.0` to `src/squadron/tools/limits.py`, alongside
  `BASH_TIMEOUT_S`, matching the module's existing bare-constant style and docstring
  - [x] Value is a starting point for review-time greps over source trees; task 6's timeout
    test will monkeypatch it down regardless, so the exact number is not load-bearing
  - [x] Effort: 1/5

- [x] **Task 1 success criteria**
  - [x] `limits.GREP_TIMEOUT_S` importable and equal to the chosen float
  - [x] `ruff format` run, then committed: `chore: add GREP_TIMEOUT_S limit`

## Task 2: Add `regex` dependency

- [x] **2.1** Add `"regex>=2024.0.0"` to the flat `dependencies` list in `pyproject.toml`
  (there is no extras group to gate it behind — it goes directly in the main list, matching
  entries like `"pydantic>=2.0"`)
- [x] **2.2** `uv sync` (or `uv lock` then `uv sync`, whichever this project's lockfile
  workflow uses) to update the lockfile
  - [x] Effort: 1/5

- [x] **Task 2 success criteria**
  - [x] `uv run python -c "import regex"` succeeds
  - [x] Lockfile updated and included in the diff
  - [x] `ruff format` run, then committed: `chore: add regex dependency for bounded grep tool`

## Task 3: `list_files` tool

- [x] **3.1** Add `LIST_FILES_NAME = "list_files"` to the module-level name constants in
  `tools/builtin.py`, alongside `READ_FILE_NAME` / `WRITE_FILE_NAME` / `BASH_NAME`
- [x] **3.2** Implement `_list_files_factory(cwd: Path) -> ToolExecutor`, mirroring the
  `_read_file_factory` shape (159-195): async `execute(args)` wrapped in `_guarded`, a nested
  sync function doing the blocking `Path.iterdir`/`Path.rglob` walk run via
  `await asyncio.to_thread(...)`
  - [x] Parameters: `path` (string, optional, default `"."`), `pattern` (string, optional
    glob, e.g. `"*.py"`), `recursive` (boolean, optional, default `false`)
  - [x] Resolve `path` via `_resolve_in_jail(cwd, path)`; `None` result returns
    `_jail_violation(LIST_FILES_NAME, path)`
  - [x] Non-recursive: `Path.glob(pattern or "*")`. Recursive: `Path.rglob(pattern or "*")`
  - [x] Returns newline-joined paths **relative to the jail root** (`cwd`), directories marked
    with a trailing `/`
  - [x] Apply the same truncation pattern as `read_file` (`_truncate`, using
    `limits.MAX_OUTPUT_BYTES` read as a module attribute at call time, not imported by value —
    matching the existing comment explaining why)
- [x] **3.3** Construct the `ToolDescriptor` (name, description, parameters schema, factory)
  and call `register(LIST_FILES)` at module level, following the exact `read_file` pattern at
  line 195
  - [x] Effort: 3/5

- [x] **Task 3 success criteria**
  - [x] `list_files` appears in `tools.list_tools()`
  - [x] Happy path against a small fixture tree returns expected relative paths
  - [x] A `path` escaping the jail returns `is_error=True` via `_jail_violation`
  - [x] Output is capped by the shared truncation limit with the same visible marker
  - [x] `ruff format` run, then committed: `feat: add list_files tool`

## Task 4: Test `list_files`

- [x] **4.1** Create `tests/tools/test_list_files.py`, mirroring `test_read_file.py`'s
  structure and fixture setup
  - [x] `test_lists_files_in_default_path` — `path` omitted, defaults to `"."`
  - [x] `test_pattern_filters_results` — e.g. `pattern="*.py"` excludes non-matching files
  - [x] `test_recursive_true_descends_subdirectories`
  - [x] `test_recursive_false_default_stays_shallow`
  - [x] `test_directories_marked_with_trailing_slash`
  - [x] `test_path_escaping_jail_returns_error` — mirror the jail-violation test in
    `test_jail.py` for the existing tools
  - [x] `test_output_truncated_beyond_limit` — monkeypatch `limits.MAX_OUTPUT_BYTES` down,
    assert the visible truncation marker appears
  - [x] Effort: 2/5

- [x] **Task 4 success criteria**
  - [x] `uv run pytest tests/tools/test_list_files.py -q` green
  - [x] `ruff format` run, then committed: `test: add coverage for list_files tool`

## Task 5: `grep` tool with bounded matching

`tools/builtin.py` is already 345 lines before this task and Task 3 add two more tool
implementations; it will grow past the project's ~300-line guideline. Accepted rather than
split into a separate module — this file has one clear responsibility (built-in tool
implementations sharing the jail/truncation/guard helpers) and the codebase has larger
precedent elsewhere (`pipeline/executor.py` ~1700 lines) — but implement `grep` in this file,
not a new one, so the decision is made once here rather than reconsidered per task. Task 30.2
records this as a deliberate close-out call.

- [x] **5.1** Add `GREP_NAME = "grep"` to the module-level name constants
- [x] **5.2** Implement `_grep_factory(cwd: Path) -> ToolExecutor`, same closure/`_guarded`/
  `asyncio.to_thread` shape as the other tools
  - [x] Parameters: `pattern` (string, required), `path` (string, optional, default `"."`),
    `glob` (string, optional file filter), `max_results` (integer, optional)
  - [x] Resolve `path` via `_resolve_in_jail`; jail violation returns `_jail_violation(GREP_NAME, path)`
  - [x] Compile `pattern` with the `regex` package (not stdlib `re`) — an invalid pattern is
    caught and returned as `ToolResult(is_error=True, content=...)`, **not raised**; the model
    must be able to correct itself
  - [x] Walk the resolved path (respecting `glob` as a file filter, matching every readable
    file if `path` is a directory), matching `pattern` against each line via
    `compiled.search(line, timeout=limits.GREP_TIMEOUT_S)` — **the budget covers the whole
    walk, not each file**: track elapsed time across the loop, or pass a per-call timeout
    scoped so the sum cannot exceed `limits.GREP_TIMEOUT_S` for the call
  - [x] On `regex.TimeoutError` (or equivalent from the `regex` package): log at WARNING naming
    the pattern (mirror the bash timeout log at `builtin.py` ~303-317), return
    `ToolResult(is_error=True, content=...)` telling the model its pattern was too expensive
  - [x] Format matches as `path:line:text`, one per line, paths relative to jail root
  - [x] Respect `max_results` by stopping the walk early when given
  - [x] Apply the same output truncation as the other tools
- [x] **5.3** Construct `ToolDescriptor` and `register(GREP)` at module level
  - [x] Effort: 4/5

- [x] **Task 5 success criteria**
  - [x] `grep` appears in `tools.list_tools()`
  - [x] Happy path returns `path:line:text` matches against a fixture tree
  - [x] `glob` filter and `max_results` both work
  - [x] Invalid regex returns `is_error=True`, not a raise
  - [x] `ruff format` run, then committed: `feat: add bounded grep tool`

## Task 6: Test `grep`, including the timeout bound

- [ ] **6.1** Create `tests/tools/test_grep.py`
  - [ ] `test_matches_pattern_across_files`
  - [ ] `test_glob_filters_files_searched`
  - [ ] `test_max_results_caps_output`
  - [ ] `test_path_escaping_jail_returns_error`
  - [ ] `test_invalid_regex_returns_error_not_raise`
  - [ ] `test_output_truncated_beyond_limit`
- [ ] **6.2** The bounded-timeout test — this is the direct regression test for D9 (rejects the
  Phase 4 review's original `asyncio.wait_for` suggestion, which measured at 72.8s against a
  1.0s timeout for `(a+)+$`)
  - [ ] `test_pathological_pattern_times_out` — monkeypatch `limits.GREP_TIMEOUT_S` down to
    keep the suite fast (e.g. `0.5`), search for a pattern the `regex` engine's optimizer
    cannot fold to instant (the slice design verified `(a|a)*$` against a long non-matching run
    of `a`s bounds at ~1.02s at a 1.0s limit — use the same pattern class, scaled to the
    monkeypatched limit)
  - [ ] Assert the call returns within a small multiple of the monkeypatched timeout (not that
    it hangs), returns `is_error=True`, and a WARNING was logged naming the pattern
  - [ ] Effort: 3/5

- [ ] **Task 6 success criteria**
  - [ ] `uv run pytest tests/tools/test_grep.py -q` green, including the timeout test running
    in well under a second of wall time
  - [ ] `ruff format` run, then committed: `test: add coverage for grep tool including timeout bound`

## Task 7: Load test — `grep` timeout bound under realistic conditions

Required by `.claude/rules/python.md`'s load-test tier: "any code on the simulation, network,
concurrency, or environment-layer paths requires at least one load test exercising a realistic
configuration... CI must gate load tests for slices touching these paths." `grep`'s
`regex.search(..., timeout=...)` runs `asyncio.to_thread`d off the event loop specifically to
bound catastrophic backtracking (D9) — a concurrency-layer path. Task 6.2 is a correctness unit
test with a monkeypatched timeout; it does not assert latency/throughput/resource bounds under a
realistic configuration, which is what this task adds. No `tests/load/` directory exists yet in
this repo — this is the first. No separate CI-wiring task is needed: `pyproject.toml`'s
`testpaths = ["tests"]` picks up any new subdirectory automatically, and `.github/workflows/ci.yml`
runs plain `uv run pytest` with no path or marker filter, so a file under `tests/load/` is
already gated by the existing CI job once it exists.

- [ ] **7.1** Create `tests/load/test_grep_timeout.py`
  - [ ] `test_walk_budget_holds_at_real_timeout` — run `grep` against a realistic-sized fixture
    tree (dozens of files, not the handful used in Task 6's unit tests) with the **real,
    non-monkeypatched** `limits.GREP_TIMEOUT_S` value, containing one file with a pathological
    pattern match candidate; assert the call returns within a bounded multiple of
    `GREP_TIMEOUT_S` (not merely "eventually"), proving the whole-walk budget in Task 5.2 holds
    end to end rather than only for the single-pattern case Task 6.2 isolates
  - [ ] `test_concurrent_grep_calls_do_not_starve_the_event_loop` — issue several concurrent
    `grep` calls (including at least one pathological pattern) via `asyncio.gather`, each
    running under `asyncio.to_thread`; assert total wall time stays bounded (no call waits
    materially longer than `GREP_TIMEOUT_S` for the thread pool to free up) and the event loop
    remains responsive to a concurrently-scheduled no-op coroutine throughout — this is the
    check a unit test cannot make, since unit tests exercise one call at a time
  - [ ] Assert on wall-clock bounds and/or a resource metric (thread count, elapsed time), not
    only on `is_error`/return-value correctness — correctness is Task 6's job, this task's job
    is the bound holding under load
  - [ ] Effort: 3/5

- [ ] **Task 7 success criteria**
  - [ ] `uv run pytest tests/load/test_grep_timeout.py -q` green, using the real
    `GREP_TIMEOUT_S` value (not monkeypatched down)
  - [ ] Both tests assert a quantitative bound (elapsed time or resource count), not just
    pass/fail correctness
  - [ ] `ruff format` run, then committed: `test: add load test for grep timeout bound under realistic conditions`

## Task 8: Canonical → Claude tool name translation at the SDK edge

- [ ] **8.1** Add a module-level mapping (new file `providers/sdk/tool_names.py`, or inline in
  `providers/sdk/provider.py` — pick whichever keeps `provider.py` under its current length;
  prefer the new module if `provider.py` is already near 300 lines) with exactly:
  ```python
  CANONICAL_TO_CLAUDE = {
      "read_file": "Read",
      "list_files": "Glob",
      "grep": "Grep",
      "write_file": "Write",
      "bash": "Bash",
  }
  ```
- [ ] **8.2** At `providers/sdk/provider.py:56-57`, replace the direct passthrough
  (`kwargs["allowed_tools"] = config.allowed_tools`) with a translation step: map each name in
  `config.allowed_tools` through `CANONICAL_TO_CLAUDE`; a name with no entry raises
  `ProviderError` naming the offending tool (mirrors the non-SDK raise in task 10 — both
  directions of "name I don't recognize" become loud, per design D3)
  - [ ] `config.allowed_tools is None` still skips translation entirely (today's behavior for
    "no tools declared")
  - [ ] Effort: 3/5

- [ ] **Task 8 success criteria**
  - [ ] A migrated template's canonical names produce the equivalent Claude names in the built
    `ClaudeAgentOptions.allowed_tools`
  - [ ] An unmapped canonical name raises `ProviderError` at config-build time
  - [ ] `ruff format` run, then committed: `feat: translate canonical tool names at SDK config edge`

## Task 9: Test SDK translation, asserting the built config directly

- [ ] **9.1** Add to `tests/providers/sdk/test_provider.py` (or `test_translation.py` if that
  is where config-build tests for this provider already live — check before choosing)
  - [ ] `test_canonical_names_translate_to_claude_names` — build a config from
    `["read_file", "list_files", "grep"]` and assert the resulting
    `ClaudeAgentOptions.allowed_tools == ["Read", "Glob", "Grep"]` **on the built config
    object**, not inferred from a mock call — this is SC3's literal assertion
  - [ ] `test_unmapped_canonical_name_raises_provider_error`
  - [ ] `test_none_allowed_tools_skips_translation` — regression guard for the pre-migration
    no-tools path
  - [ ] Effort: 2/5

- [ ] **Task 9 success criteria**
  - [ ] `uv run pytest tests/providers/sdk/ -q` green
  - [ ] `ruff format` run, then committed: `test: assert SDK config translation of canonical tool names`

## Task 10: Non-SDK unknown-name policy — raise instead of warn

- [ ] **10.1** In `providers/openai/agent.py`, replace the warn-and-continue block (125-134)
  with a raise: on the first (or accumulated, matching whichever the existing loop shape
  favors — accumulate all unknown names into one `ProviderError` message, do not stop at the
  first) unknown name, raise `ProviderError` naming the offending tool(s) and listing
  `tools.list_tools()`
  - [ ] Remove the `_log.warning(...)` call this replaces — a raised error is loud on its own,
    a preceding warning would be redundant noise before the crash
  - [ ] Effort: 2/5

- [ ] **Task 10 success criteria**
  - [ ] Constructing the agent with an unknown tool name raises `ProviderError` naming it
  - [ ] Constructing with only known names is unaffected
  - [ ] `uv run pytest tests/providers/openai/ -q` green (existing tests that relied on the old
    warn-and-drop behavior are updated to expect the raise — check `test_agent.py` and
    `test_agentic_loop.py` for any such test before editing)
  - [ ] `ruff format` run, then committed: `feat: raise on unknown tool name in non-SDK agent`

## Task 11: Test the non-SDK raise

- [ ] **11.1** Add/update tests in `tests/providers/openai/test_agent.py`
  - [ ] `test_unknown_tool_name_raises_provider_error` — assert the message contains the bad
    name and the registered-tools list
  - [ ] `test_two_unknown_names_both_named_in_error` (if the implementation accumulates rather
    than raising on the first — match task 10's actual choice)
  - [ ] `test_known_tool_names_construct_successfully` — regression guard
  - [ ] Effort: 2/5

- [ ] **Task 11 success criteria**
  - [ ] `uv run pytest tests/providers/openai/ -q` green
  - [ ] `ruff format` run, then committed: `test: cover unknown tool name raise in non-SDK agent`

## Task 12: Effective-tools helper and injection decision

- [ ] **12.1** Add a small helper (in `review/review_client.py` or a new
  `review/tool_support.py` if it grows beyond a few lines) computing the effective tool set for
  a run: the template's `allowed_tools` filtered to names `tools.list_tools()` knows for
  non-SDK profiles, passed through untouched for SDK profiles (which resolve names themselves
  per task 8)
  - [ ] No new field on `ProviderCapabilities` (design D1) — this is computed per-call, not
    stored
- [ ] **12.2** Replace the bare check at `review_client.py:85-86`
  (`if not provider.capabilities.can_read_files:`) with:
  ```python
  inject_file_bodies = not provider.capabilities.can_read_files and not effective_tools_include_a_reader
  ```
  where `effective_tools_include_a_reader` is true iff `"read_file"` is in the effective tool
  set computed in 12.1
  - [ ] `can_read_files` itself is untouched — it keeps its current meaning and current call
    sites elsewhere in the codebase are unaffected
  - [ ] A template with no `allowed_tools` and a provider with `can_read_files=False` must
    inject exactly as it does today — this is the byte-identical regression case SC5 requires
  - [ ] Effort: 3/5

- [ ] **Task 12 success criteria**
  - [ ] Tool-capable provider + template allowing `read_file` → prompt contains the diff, no
    injected file bodies
  - [ ] No allowed tools declared → prompt byte-identical to pre-slice behavior
  - [ ] `ruff format` run, then committed: `feat: compute run-scoped injection decision from effective tool set`

## Task 13: Test the injection decision

- [ ] **13.1** Add to `tests/review/test_review_client.py` (or `test_content_injection.py` if
  injection-specific tests already live there — check before choosing)
  - [ ] `test_tool_capable_review_skips_file_body_injection` — assert diff present, file bodies
    absent
  - [ ] `test_no_tools_review_injects_file_bodies_unchanged` — byte-for-byte comparison against
    the pre-slice prompt construction for a fixture input
  - [ ] `test_sdk_provider_unaffected_by_effective_tools_change` — `can_read_files=True`
    providers keep skipping injection regardless of `allowed_tools`
  - [ ] Effort: 2/5

- [ ] **Task 13 success criteria**
  - [ ] `uv run pytest tests/review/ -k "inject" -q` green
  - [ ] `ruff format` run, then committed: `test: cover run-scoped injection decision`
