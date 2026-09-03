---
docType: review
layer: project
reviewType: code
slice: review-coverage-standalone-client-and-pipeline-actions
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/265-slice.review-coverage-standalone-client-and-pipeline-actions.md
aiModel: moonshotai/kimi-k2.7-code
status: complete
dateCreated: 20260903
dateUpdated: 20260903
reviewedSha: 9b04cc477ed6ebb90991ef65e39e0a04767f919d
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "`grep` silently truncates large files without warning"
    location: "src/squadron/tools/builtin.py#_search"
  - id: F002
    severity: concern
    category: security
    summary: "Recursive `list_files` and `grep` follow symlinks without per-entry jail check"
    location: "src/squadron/tools/builtin.py#_list_files_factory and src/squadron/tools/builtin.py#_grep_factory"
  - id: F003
    severity: concern
    category: design
    summary: "One-shot SDK dispatch still rejects `allowed_tools` instead of translating them"
    location: "src/squadron/pipeline/actions/dispatch.py#one_shot_dispatch_with_telemetry"
  - id: F004
    severity: pass
    category: design
    summary: "Built-in tool implementations use worker threads and explicit timeouts"
    location: "src/squadron/tools/builtin.py"
  - id: F005
    severity: pass
    category: design
    summary: "`allowed_tools` resolution is centralized and fail-fast"
    location: "src/squadron/pipeline/actions/tool_support.py#resolve_allowed_tools"
  - id: F006
    severity: pass
    category: error-handling
    summary: "SDK/non-SDK tool-name translation and unknown-name errors are explicit"
    location: "src/squadron/providers/sdk/tool_names.py#translate_tool_names and src/squadron/providers/openai/agent.py#__init__"
  - id: F007
    severity: pass
    category: observability
    summary: "Tool-use telemetry is stamped only on final messages and propagated through results"
    location: "src/squadron/providers/openai/agent.py#_stamp_tool_telemetry"
  - id: F008
    severity: pass
    category: compatibility
    summary: "MCP bridge handles 1.x/2.x protocol error class differences"
    location: "src/squadron/tools/mcp_bridge.py:25-30"
  - id: F009
    severity: pass
    category: design
    summary: "Review and summary actions thread `allowed_tools` through to provider agents"
    location: "src/squadron/pipeline/actions/review.py#ReviewAction._review and src/squadron/pipeline/actions/summary.py#_execute_summary"
  - id: F010
    severity: note
    category: process
    summary: "Review performed without executing the requested `git diff`"
    location: "unverified"
  - id: F011
    severity: concern
    category: error-handling
    summary: "list_files materializes and sorts the entire recursive walk with no budget"
    location: "src/squadron/tools/builtin.py#_list_files_factory"
  - id: F012
    severity: concern
    category: project-conventions
    summary: "builtin.py is now ~2x the project's ~300-line file-size convention"
    location: "src/squadron/tools/builtin.py"
---

# Review: code — slice 265

**Verdict:** CONCERNS
**Model:** moonshotai/kimi-k2.7-code

## Findings

### [CONCERN] `grep` silently truncates large files without warning

`_grep_factory`'s `_search` reads each candidate with `handle.read(limits.MAX_READ_BYTES)` and searches only that chunk. If a file is larger than `MAX_READ_BYTES`, any match beyond the first chunk is silently ignored; the user gets no truncation marker or warning. This violates the project's "no silent fallback" rule and the failure-mode enumeration rule. Either stream/read line-by-line with a bounded buffer, or emit a visible warning/sentinel when a file is truncated.

### [CONCERN] Recursive `list_files` and `grep` follow symlinks without per-entry jail check

`_resolve_in_jail` checks the user-supplied starting path, including symlink resolution, but `Path.glob`/`rglob` follow symlinks while iterating. A symlink inside the working directory that points outside it can cause traversal outside the jail and may trigger an unhandled `ValueError` from `relative_to(cwd)` (or, for `grep`, an unexpected failure). The tool should either skip symlinks or re-check each candidate with `is_relative_to(cwd)` before reading.

### [CONCERN] One-shot SDK dispatch still rejects `allowed_tools` instead of translating them

The function raises `ValueError` when `allowed_tools` is declared for an SDK profile, forcing users to remove the declaration or use a non-SDK model. The inline comment correctly notes this is out-of-scope for the slice, but it leaves a feature gap that conflicts with the rest of the slice’s goal of threading `allowed_tools` through review and summary. Track as follow-up and translate canonical names at this edge the same way `ClaudeSDKProvider.create_agent` does.

### [PASS] Built-in tool implementations use worker threads and explicit timeouts

`read_file`, `write_file`, `bash`, `list_files`, and `grep` all run blocking work in `asyncio.to_thread`, enforce path jail checks via `_resolve_in_jail`, and use explicit timeouts for `bash` and `grep`. Error results are logged and returned rather than swallowed.

### [PASS] `allowed_tools` resolution is centralized and fail-fast

`resolve_allowed_tools` is the single runtime helper used by dispatch, review, and summary. It raises on malformed values instead of silently dropping tools, and defers registry validation to the existing load-time validator.

### [PASS] SDK/non-SDK tool-name translation and unknown-name errors are explicit

Canonical squadron tool names are translated to Claude names only at the SDK `AgentConfig` edge, and unmapped names raise with the full known list. The non-SDK `OpenAICompatibleAgent` also raises on unknown tool names at construction, preventing silent no-op reviews.

### [PASS] Tool-use telemetry is stamped only on final messages and propagated through results

Telemetry is stamped only on the final surfaced message, carried through `ReviewResult`/`ActionResult` metadata, rendered in the executor's verbose log line, and persisted into `RunState`. The keys remain absent when no tools were offered, preserving the distinction between "offered but unused" and "never offered".

### [PASS] MCP bridge handles 1.x/2.x protocol error class differences

The bridge imports `McpError` or `MCPError` depending on the installed `mcp` version, classifies grouped exceptions via `_leaves`, and returns all failures as `ToolResult(is_error=True)` per the slice-261 contract.

### [PASS] Review and summary actions thread `allowed_tools` through to provider agents

Both actions call `resolve_allowed_tools`, pass the result into the provider dispatch path, and surface any returned tool-use telemetry in `ActionResult.metadata`. The summary action correctly rejects `rotate` emit for non-SDK profiles.

### [NOTE] Review performed without executing the requested `git diff`

The environment did not provide a shell execution tool, so the exact changed-file set could not be produced by `git diff`. The files reviewed were inferred from the branch reflog and commit messages, and the assessment is based on the current contents of those files in the branch.

### [CONCERN] list_files materializes and sorts the entire recursive walk with no budget

`lines = sorted(_format_entry(entry, cwd) for entry in matches)` walks, materializes, and sorts the full tree before `_truncate` is applied. This is the pattern the grep code's own comment rejects — "a sorted list would walk and materialize the entire tree before the caller's first deadline check" — yet `list_files` has no deadline at all. A model passing `recursive=True` against a tree containing `node_modules` or a build directory produces an unbounded walk and an in-memory list of every entry; output truncation caps bytes *returned*, not work *performed*. It runs in a worker thread so the event loop is safe, but the "what if the tree is huge" question deserves an explicit answer: stream + cap entry count (like `grep`'s `max_results`), or document why the asymmetry with `grep` is intentional.

### [CONCERN] builtin.py is now ~2x the project's ~300-line file-size convention

The file grows from ~348 to ~614 lines with five tool implementations plus shared helpers. CLAUDE.md's "keep source files to ~300 lines where practical" was already marginally exceeded; this slice doubles it. The new tools are self-contained, so a split is cheap — e.g. `builtin/file_tools.py` (`read_file`, `write_file`, `list_files`) and `builtin/search_tools.py` (`grep`) re-registered from `builtin/__init__.py`. The registry pattern makes this a pure move with no behavior change; doing it now is cheaper than after the next tool lands.

---

## Provenance

F001–F010 are from the `moonshotai/kimi-k2.7-code` run against `eb0fc75` (tool-enabled, 2026-09-03). F011–F012 are carried forward from an earlier `moonshotai/kimi-k3` run against the same SHA, whose artifact this one replaced; both findings remain unaddressed and are tracked in slice 266's scope. The k3 run's three other findings are not carried forward: its telemetry-duplication, unused-`cast`, and line-length findings were addressed in `eb0fc75`. The prior artifact is retained under `archive/`.
