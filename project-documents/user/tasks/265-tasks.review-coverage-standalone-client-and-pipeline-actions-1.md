---
docType: tasks
project: squadron
slice: 265-slice.review-coverage-standalone-client-and-pipeline-actions
lldReference: project-documents/user/slices/265-slice.review-coverage-standalone-client-and-pipeline-actions.md
parent: 260-slices.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md
dependencies: [261, 262, 263]
dateCreated: 20260901
dateUpdated: 20260901
status: not_started
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
callers, so its signature does not change — task 18 adds a sibling function that returns both
text and telemetry.

**Where translation and validation live today, with no changes yet:**
- `providers/sdk/provider.py:56-57` passes `AgentConfig.allowed_tools` straight into
  `ClaudeAgentOptions(**kwargs)` — no translation. This is the edge task 7 changes.
- `providers/openai/agent.py:125-134` is the warn-and-drop loop task 9 tightens to a raise.
- `core/models.py:65-74` — `Message.metadata: dict[str, Any]` already exists and defaults to
  `{}`; no model change needed to carry the new keys.
- `tools/limits.py` is a flat module of bare constants (`MAX_READ_BYTES`, `MAX_OUTPUT_BYTES`,
  `BASH_TIMEOUT_S`); `GREP_TIMEOUT_S` joins it the same way.
- `pipeline/schema.py` has no per-step-type Pydantic schema — `StepSchema.config` is a flat
  `dict[str, object]`. There is nothing to "extend" there; `allowed_tools` for review/summary
  is read the same ad hoc way `dispatch.py` already reads it, via a shared helper (task 13).
- `pipeline/executor.py:95-108`, `_log_action_result`, already renders `verdict=` and `model=`
  from `result.metadata`; task 20 appends one more `extras` block for `tools=N/M calls`.
- `review/models.py`, `ReviewResult` — no `tools_given`/`tool_calls_made` fields today; task 19
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
dependency first (1-2), then the tools themselves with tests (3-6), then the two provider-side
vocabulary changes that make everything else meaningful (7-10), then the injection decision
(11-12) — this file ends here. Part 2 continues with pipeline-action wiring for review and
summary (13-15), observability threading (16-20), template migration (21-22, deliberately late
because it depends on the vocabulary fix actually working), then end-to-end verification and
close-out (23-25). Each task ends with its own commit — see Commit Protocol below.

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

- [ ] **1.1** Add `GREP_TIMEOUT_S = 5.0` to `src/squadron/tools/limits.py`, alongside
  `BASH_TIMEOUT_S`, matching the module's existing bare-constant style and docstring
  - [ ] Value is a starting point for review-time greps over source trees; task 6's timeout
    test will monkeypatch it down regardless, so the exact number is not load-bearing
  - [ ] Effort: 1/5

- [ ] **Task 1 success criteria**
  - [ ] `limits.GREP_TIMEOUT_S` importable and equal to the chosen float
  - [ ] `ruff format` run, then committed: `chore: add GREP_TIMEOUT_S limit`

## Task 2: Add `regex` dependency

- [ ] **2.1** Add `"regex>=2024.0.0"` to the flat `dependencies` list in `pyproject.toml`
  (there is no extras group to gate it behind — it goes directly in the main list, matching
  entries like `"pydantic>=2.0"`)
- [ ] **2.2** `uv sync` (or `uv lock` then `uv sync`, whichever this project's lockfile
  workflow uses) to update the lockfile
  - [ ] Effort: 1/5

- [ ] **Task 2 success criteria**
  - [ ] `uv run python -c "import regex"` succeeds
  - [ ] Lockfile updated and included in the diff
  - [ ] `ruff format` run, then committed: `chore: add regex dependency for bounded grep tool`

## Task 3: `list_files` tool

- [ ] **3.1** Add `LIST_FILES_NAME = "list_files"` to the module-level name constants in
  `tools/builtin.py`, alongside `READ_FILE_NAME` / `WRITE_FILE_NAME` / `BASH_NAME`
- [ ] **3.2** Implement `_list_files_factory(cwd: Path) -> ToolExecutor`, mirroring the
  `_read_file_factory` shape (159-195): async `execute(args)` wrapped in `_guarded`, a nested
  sync function doing the blocking `Path.iterdir`/`Path.rglob` walk run via
  `await asyncio.to_thread(...)`
  - [ ] Parameters: `path` (string, optional, default `"."`), `pattern` (string, optional
    glob, e.g. `"*.py"`), `recursive` (boolean, optional, default `false`)
  - [ ] Resolve `path` via `_resolve_in_jail(cwd, path)`; `None` result returns
    `_jail_violation(LIST_FILES_NAME, path)`
  - [ ] Non-recursive: `Path.glob(pattern or "*")`. Recursive: `Path.rglob(pattern or "*")`
  - [ ] Returns newline-joined paths **relative to the jail root** (`cwd`), directories marked
    with a trailing `/`
  - [ ] Apply the same truncation pattern as `read_file` (`_truncate`, using
    `limits.MAX_OUTPUT_BYTES` read as a module attribute at call time, not imported by value —
    matching the existing comment explaining why)
- [ ] **3.3** Construct the `ToolDescriptor` (name, description, parameters schema, factory)
  and call `register(LIST_FILES)` at module level, following the exact `read_file` pattern at
  line 195
  - [ ] Effort: 3/5

- [ ] **Task 3 success criteria**
  - [ ] `list_files` appears in `tools.list_tools()`
  - [ ] Happy path against a small fixture tree returns expected relative paths
  - [ ] A `path` escaping the jail returns `is_error=True` via `_jail_violation`
  - [ ] Output is capped by the shared truncation limit with the same visible marker
  - [ ] `ruff format` run, then committed: `feat: add list_files tool`

## Task 4: Test `list_files`

- [ ] **4.1** Create `tests/tools/test_list_files.py`, mirroring `test_read_file.py`'s
  structure and fixture setup
  - [ ] `test_lists_files_in_default_path` — `path` omitted, defaults to `"."`
  - [ ] `test_pattern_filters_results` — e.g. `pattern="*.py"` excludes non-matching files
  - [ ] `test_recursive_true_descends_subdirectories`
  - [ ] `test_recursive_false_default_stays_shallow`
  - [ ] `test_directories_marked_with_trailing_slash`
  - [ ] `test_path_escaping_jail_returns_error` — mirror the jail-violation test in
    `test_jail.py` for the existing tools
  - [ ] `test_output_truncated_beyond_limit` — monkeypatch `limits.MAX_OUTPUT_BYTES` down,
    assert the visible truncation marker appears
  - [ ] Effort: 2/5

- [ ] **Task 4 success criteria**
  - [ ] `uv run pytest tests/tools/test_list_files.py -q` green
  - [ ] `ruff format` run, then committed: `test: add coverage for list_files tool`

## Task 5: `grep` tool with bounded matching

- [ ] **5.1** Add `GREP_NAME = "grep"` to the module-level name constants
- [ ] **5.2** Implement `_grep_factory(cwd: Path) -> ToolExecutor`, same closure/`_guarded`/
  `asyncio.to_thread` shape as the other tools
  - [ ] Parameters: `pattern` (string, required), `path` (string, optional, default `"."`),
    `glob` (string, optional file filter), `max_results` (integer, optional)
  - [ ] Resolve `path` via `_resolve_in_jail`; jail violation returns `_jail_violation(GREP_NAME, path)`
  - [ ] Compile `pattern` with the `regex` package (not stdlib `re`) — an invalid pattern is
    caught and returned as `ToolResult(is_error=True, content=...)`, **not raised**; the model
    must be able to correct itself
  - [ ] Walk the resolved path (respecting `glob` as a file filter, matching every readable
    file if `path` is a directory), matching `pattern` against each line via
    `compiled.search(line, timeout=limits.GREP_TIMEOUT_S)` — **the budget covers the whole
    walk, not each file**: track elapsed time across the loop, or pass a per-call timeout
    scoped so the sum cannot exceed `limits.GREP_TIMEOUT_S` for the call
  - [ ] On `regex.TimeoutError` (or equivalent from the `regex` package): log at WARNING naming
    the pattern (mirror the bash timeout log at `builtin.py` ~303-317), return
    `ToolResult(is_error=True, content=...)` telling the model its pattern was too expensive
  - [ ] Format matches as `path:line:text`, one per line, paths relative to jail root
  - [ ] Respect `max_results` by stopping the walk early when given
  - [ ] Apply the same output truncation as the other tools
- [ ] **5.3** Construct `ToolDescriptor` and `register(GREP)` at module level
  - [ ] Effort: 4/5

- [ ] **Task 5 success criteria**
  - [ ] `grep` appears in `tools.list_tools()`
  - [ ] Happy path returns `path:line:text` matches against a fixture tree
  - [ ] `glob` filter and `max_results` both work
  - [ ] Invalid regex returns `is_error=True`, not a raise
  - [ ] `ruff format` run, then committed: `feat: add bounded grep tool`

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

## Task 7: Canonical → Claude tool name translation at the SDK edge

- [ ] **7.1** Add a module-level mapping (new file `providers/sdk/tool_names.py`, or inline in
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
- [ ] **7.2** At `providers/sdk/provider.py:56-57`, replace the direct passthrough
  (`kwargs["allowed_tools"] = config.allowed_tools`) with a translation step: map each name in
  `config.allowed_tools` through `CANONICAL_TO_CLAUDE`; a name with no entry raises
  `ProviderError` naming the offending tool (mirrors the non-SDK raise in task 8 — both
  directions of "name I don't recognize" become loud, per design D3)
  - [ ] `config.allowed_tools is None` still skips translation entirely (today's behavior for
    "no tools declared")
  - [ ] Effort: 3/5

- [ ] **Task 7 success criteria**
  - [ ] A migrated template's canonical names produce the equivalent Claude names in the built
    `ClaudeAgentOptions.allowed_tools`
  - [ ] An unmapped canonical name raises `ProviderError` at config-build time
  - [ ] `ruff format` run, then committed: `feat: translate canonical tool names at SDK config edge`

## Task 8: Test SDK translation, asserting the built config directly

- [ ] **8.1** Add to `tests/providers/sdk/test_provider.py` (or `test_translation.py` if that
  is where config-build tests for this provider already live — check before choosing)
  - [ ] `test_canonical_names_translate_to_claude_names` — build a config from
    `["read_file", "list_files", "grep"]` and assert the resulting
    `ClaudeAgentOptions.allowed_tools == ["Read", "Glob", "Grep"]` **on the built config
    object**, not inferred from a mock call — this is SC3's literal assertion
  - [ ] `test_unmapped_canonical_name_raises_provider_error`
  - [ ] `test_none_allowed_tools_skips_translation` — regression guard for the pre-migration
    no-tools path
  - [ ] Effort: 2/5

- [ ] **Task 8 success criteria**
  - [ ] `uv run pytest tests/providers/sdk/ -q` green
  - [ ] `ruff format` run, then committed: `test: assert SDK config translation of canonical tool names`

## Task 9: Non-SDK unknown-name policy — raise instead of warn

- [ ] **9.1** In `providers/openai/agent.py`, replace the warn-and-continue block (125-134)
  with a raise: on the first (or accumulated, matching whichever the existing loop shape
  favors — accumulate all unknown names into one `ProviderError` message, do not stop at the
  first) unknown name, raise `ProviderError` naming the offending tool(s) and listing
  `tools.list_tools()`
  - [ ] Remove the `_log.warning(...)` call this replaces — a raised error is loud on its own,
    a preceding warning would be redundant noise before the crash
  - [ ] Effort: 2/5

- [ ] **Task 9 success criteria**
  - [ ] Constructing the agent with an unknown tool name raises `ProviderError` naming it
  - [ ] Constructing with only known names is unaffected
  - [ ] `uv run pytest tests/providers/openai/ -q` green (existing tests that relied on the old
    warn-and-drop behavior are updated to expect the raise — check `test_agent.py` and
    `test_agentic_loop.py` for any such test before editing)
  - [ ] `ruff format` run, then committed: `feat: raise on unknown tool name in non-SDK agent`

## Task 10: Test the non-SDK raise

- [ ] **10.1** Add/update tests in `tests/providers/openai/test_agent.py`
  - [ ] `test_unknown_tool_name_raises_provider_error` — assert the message contains the bad
    name and the registered-tools list
  - [ ] `test_two_unknown_names_both_named_in_error` (if the implementation accumulates rather
    than raising on the first — match task 9's actual choice)
  - [ ] `test_known_tool_names_construct_successfully` — regression guard
  - [ ] Effort: 2/5

- [ ] **Task 10 success criteria**
  - [ ] `uv run pytest tests/providers/openai/ -q` green
  - [ ] `ruff format` run, then committed: `test: cover unknown tool name raise in non-SDK agent`

## Task 11: Effective-tools helper and injection decision

- [ ] **11.1** Add a small helper (in `review/review_client.py` or a new
  `review/tool_support.py` if it grows beyond a few lines) computing the effective tool set for
  a run: the template's `allowed_tools` filtered to names `tools.list_tools()` knows for
  non-SDK profiles, passed through untouched for SDK profiles (which resolve names themselves
  per task 7)
  - [ ] No new field on `ProviderCapabilities` (design D1) — this is computed per-call, not
    stored
- [ ] **11.2** Replace the bare check at `review_client.py:85-86`
  (`if not provider.capabilities.can_read_files:`) with:
  ```python
  inject_file_bodies = not provider.capabilities.can_read_files and not effective_tools_include_a_reader
  ```
  where `effective_tools_include_a_reader` is true iff `"read_file"` is in the effective tool
  set computed in 11.1
  - [ ] `can_read_files` itself is untouched — it keeps its current meaning and current call
    sites elsewhere in the codebase are unaffected
  - [ ] A template with no `allowed_tools` and a provider with `can_read_files=False` must
    inject exactly as it does today — this is the byte-identical regression case SC5 requires
  - [ ] Effort: 3/5

- [ ] **Task 11 success criteria**
  - [ ] Tool-capable provider + template allowing `read_file` → prompt contains the diff, no
    injected file bodies
  - [ ] No allowed tools declared → prompt byte-identical to pre-slice behavior
  - [ ] `ruff format` run, then committed: `feat: compute run-scoped injection decision from effective tool set`

## Task 12: Test the injection decision

- [ ] **12.1** Add to `tests/review/test_review_client.py` (or `test_content_injection.py` if
  injection-specific tests already live there — check before choosing)
  - [ ] `test_tool_capable_review_skips_file_body_injection` — assert diff present, file bodies
    absent
  - [ ] `test_no_tools_review_injects_file_bodies_unchanged` — byte-for-byte comparison against
    the pre-slice prompt construction for a fixture input
  - [ ] `test_sdk_provider_unaffected_by_effective_tools_change` — `can_read_files=True`
    providers keep skipping injection regardless of `allowed_tools`
  - [ ] Effort: 2/5

- [ ] **Task 12 success criteria**
  - [ ] `uv run pytest tests/review/ -k "inject" -q` green
  - [ ] `ruff format` run, then committed: `test: cover run-scoped injection decision`
