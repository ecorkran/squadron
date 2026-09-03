---
docType: review
layer: project
reviewType: code
slice: review-coverage-standalone-client-and-pipeline-actions
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/265-slice.review-coverage-standalone-client-and-pipeline-actions.md
aiModel: moonshotai/kimi-k3
status: complete
dateCreated: 20260902
dateUpdated: 20260902
reviewedSha: eb0fc753f7f8efda73a51e05b7cf849fb139f878
findings:
  - id: F001
    severity: concern
    category: security
    summary: "grep reads candidate files without re-verifying jail containment (symlink escape)"
    location: "src/squadron/tools/builtin.py#_grep_candidates"
  - id: F002
    severity: concern
    category: error-handling
    summary: "list_files materializes and sorts the entire recursive walk with no budget"
    location: "src/squadron/tools/builtin.py#_list_files_factory"
  - id: F003
    severity: concern
    category: project-conventions
    summary: "builtin.py is now ~2x the project's ~300-line file-size convention"
    location: "src/squadron/tools/builtin.py"
  - id: F004
    severity: note
    category: design-principles
    summary: "Telemetry-extraction snippet duplicated verbatim across three call sites"
    location: "src/squadron/pipeline/actions/dispatch.py#one_shot_dispatch_with_telemetry"
  - id: F005
    severity: note
    category: style
    summary: "Verify the `cast` import in dispatch.py is still used after extracting `_resolve_allowed_tools`"
    location: "src/squadron/pipeline/actions/dispatch.py"
  - id: F006
    severity: note
    category: style
    summary: "New code lines exceed the 88-character limit"
    location: "src/squadron/review/review_client.py#run_review_with_profile"
---

# Review: code — slice 265

**Verdict:** CONCERNS
**Model:** moonshotai/kimi-k3

## Findings

### [CONCERN] grep reads candidate files without re-verifying jail containment (symlink escape)

`_resolve_in_jail` is applied only to the initial `path` argument. Every candidate discovered by `_grep_candidates` is then opened via `candidate.open("rb")` with no per-file containment check. A symlink inside the jail pointing at a file outside it satisfies `entry.is_file()` (which follows the link) and its contents are read and returned to the model — a read that the `read_file` tool's jail check would refuse for the same target. On Python ≤3.12 the exposure is wider: `Path.rglob` recurses into symlinked *directories* (`recurse_symlinks=False` only became the default in 3.13), so a symlinked directory lets the walk leave the jail entirely.

The module docstring explicitly promises "the file tools treat that directory as a jail," and `read_file` honors it per-access; `grep` should match that discipline — e.g. `candidate.resolve()` and skip (or error) when the result is not `is_relative_to` the resolved jail root — or the docstring should state the jail is advisory for traversal-discovered files. The same applies, at lower severity (names only, no contents), to `list_files`. No test in `tests/tools/test_grep.py` covers a symlinked candidate, so the gap is currently invisible to the suite.

### [CONCERN] list_files materializes and sorts the entire recursive walk with no budget

`lines = sorted(_format_entry(entry, cwd) for entry in matches)` walks, materializes, and sorts the full tree before `_truncate` is applied. This is precisely the pattern the new grep code's own comment rejects — "a sorted list would walk and materialize the entire tree before the caller's first deadline check" — yet `list_files` has no deadline at all. A model that passes `recursive=True` against a tree containing `node_modules` or a build directory produces an unbounded walk and an in-memory list of every entry; output truncation caps bytes *returned*, not work *performed*. It runs in a worker thread so the event loop is safe, but per the failure-mode-enumeration rule the "what if the tree is huge" question deserves an explicit answer here: stream + cap entry count (like `grep`'s `max_results`), or at minimum document why the asymmetry with `grep` is intentional.

### [CONCERN] builtin.py is now ~2x the project's ~300-line file-size convention

The file grows from ~348 to ~614 lines with five tool implementations plus shared helpers. CLAUDE.md's "keep source files to ~300 lines where practical" was already marginally exceeded; this slice doubles it. The new tools are self-contained (own parameter schemas, own argument-narrowing helpers, own timeout path), so a split is cheap — e.g. `builtin/file_tools.py` (`read_file`, `write_file`, `list_files`) and `builtin/search_tools.py` (`grep`) re-registered from `builtin/__init__.py`, or simply moving `list_files`/`grep` into a sibling module. The registry pattern makes this a pure move with no behavior change; doing it now is cheaper than after the next tool lands.

### [NOTE] Telemetry-extraction snippet duplicated verbatim across three call sites

The block reading `tools_given`/`tool_calls_made` off `response.metadata` before the `sdk_type` filter is byte-for-byte identical in `one_shot_dispatch_with_telemetry` and `capture_summary_via_profile_with_telemetry`, and near-identical (locals instead of a dict) in `run_review_with_profile`. All three also repeat the "read before the filter" comment. Since the stamp is produced in exactly one place (`OpenAICompatibleAgent._stamp_tool_telemetry`), a single consumer-side helper (e.g. `extract_tool_telemetry(metadata, telemetry_dict)` next to the stamping contract) would keep the read contract and the write contract from drifting — the same drift-avoidance rationale this slice applies to `resolve_allowed_tools` in `tool_support.py`.

### [NOTE] Verify the `cast` import in dispatch.py is still used after extracting `_resolve_allowed_tools`

The removed `_resolve_allowed_tools` static method contained `cast(list[str], raw)`; the moved copy now lives in `tool_support.py`. If that was the only use of `cast` in `dispatch.py`, the leftover `from typing import cast` trips ruff F401 (the required lint set selects `F`). Relatedly, the deletion of the comment explaining `cwd=None if profile.provider == ProviderType.SDK else cwd` removes the "why" for a non-obvious gate (the SDK forwards cwd into `ClaudeAgentOptions`; the non-SDK agent needs it as the tool jail root) — the code stayed but the rationale didn't.

### [NOTE] New code lines exceed the 88-character limit

`resolved_allowed_tools = allowed_tools if allowed_tools is not None else template.allowed_tools` measures ~99 characters — a splittable code line `ruff format` would wrap automatically, suggesting the formatter wasn't run on this hunk. The `raise ValueError(f"{action_type}: 'allowed_tools' must be...")` line in the new `tool_support.py` is similarly long (~100+ with indent), though that one is inherited verbatim from the dispatch original. If the project's ruff config enforces E501 these fail CI; either way, running `ruff format` over the touched files would bring them in line with the 88-character rule.
