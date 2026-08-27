---
docType: review
layer: project
reviewType: code
slice: tool-registry-descriptor-protocol-and-core-tool-implementations
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/261-slice.tool-registry-descriptor-protocol-and-core-tool-implementations.md
aiModel: claude-sonnet-5
status: complete
dateCreated: 20260827
dateUpdated: 20260827
reviewedSha: a64b7413f9e547e79c2698e99b2bc1f1ca4c5047
findings:
  - id: F001
    severity: concern
    category: async-correctness
    summary: "Blocking filesystem syscalls run directly on the event loop"
    location: "src/squadron/tools/builtin.py:44"
  - id: F002
    severity: concern
    category: failure-mode-enumeration
    summary: "read_file / write_file have no hang protection, unlike bash"
    location: "src/squadron/tools/builtin.py#_read_file_factory"
  - id: F003
    severity: note
    category: simplification
    summary: "Redundant jail check on `target.parent` in write_file"
    location: "src/squadron/tools/builtin.py:195"
  - id: F004
    severity: pass
    category: uncategorized
    summary: "Jail traversal, symlink, and prefix-confusion cases are well covered"
    location: "tests/tools/test_jail.py"
  - id: F005
    severity: pass
    category: uncategorized
    summary: "Exception handling matches project error-handling rules"
    location: "src/squadron/tools/builtin.py:74-97"
---

# Review: code — slice 261

**Verdict:** CONCERNS
**Model:** claude-sonnet-5

## Findings

### [CONCERN] Blocking filesystem syscalls run directly on the event loop

`_resolve_in_jail` (builtin.py:44) calls `Path.resolve(strict=False)`, which performs `stat`/`lstat` syscalls to walk and de-symlink every existing path component. It is invoked synchronously, un-awaited, straight from inside the `async def run()` closures in both `_read_file_factory` (builtin.py:143) and `_write_file_factory` (builtin.py:190, and again at :195 for the parent check). `_write_file_factory` additionally calls `target.is_dir()` (builtin.py:197) and `target.exists()` (builtin.py:200) synchronously before the `asyncio.to_thread`-wrapped `_write()` even starts.

The project's async rule ("Any async def function that calls synchronous code must guarantee that the synchronous code runs in <1ms in the worst case… Reviewers MUST verify this") is not met here: `read_bytes`/`write_bytes` were correctly pushed into `asyncio.to_thread`, but the resolve/stat calls that gate them were not. On a slow disk, a network/FUSE mount, or a jail root with many symlinked components, these calls can block well past 1ms and stall the whole event loop — including any other concurrent tool call or `bash` timeout bookkeeping happening in the same process. Fix: wrap the `_resolve_in_jail` call (and the `is_dir()`/`exists()` checks) in `asyncio.to_thread` alongside the read/write, or resolve everything in one `to_thread` call per executor.

### [CONCERN] read_file / write_file have no hang protection, unlike bash

The additional review rules require, for every new I/O path, an explicit answer to "what if this hangs?" with an observable signal and a test. `bash` (builtin.py:253-298) answers this: `BASH_TIMEOUT_S` plus `_kill_process_group` produce a WARNING log and an error result, and `test_timeout_kills_the_command_and_reports`/`test_timeout_logs_at_warning` in tests/tools/test_bash.py assert it.

`read_file` and `write_file` have no equivalent. `target.read_bytes()` (builtin.py:147, run via `asyncio.to_thread`) and `target.write_bytes(payload)` (builtin.py:205) have no timeout. If the resolved-in-jail path is a FIFO, a device node, or a stalled network mount, the thread-pool call blocks indefinitely with no way to cancel it (unlike the subprocess case, which can be killed). There is no test in tests/tools/test_read_file.py or tests/tools/test_write_file.py exercising this path, and no code path produces an observable signal for it. Given the jail explicitly allows any path under the working directory, a FIFO/special file inside that directory is a realistic input, not a hypothetical.

### [NOTE] Redundant jail check on `target.parent` in write_file

`_write_file_factory` re-runs `_resolve_in_jail(cwd, str(target.parent))` after already confirming `target` itself is `is_relative_to(cwd)` (builtin.py:190-192). Since `Path.resolve()` fully de-symlinks every *existing* path component before appending any non-existent trailing ones, `target` passing the jail check already guarantees `target.parent` is inside the jail too (verified empirically: for `a/b/c.txt`, `sub/../c.txt`, `./x/y.txt`, the parent of an accepted `target` is always accepted). The comment ("before any directory is created") suggests a TOCTOU intent, but the check is synchronous and re-derives a value already implied by the first check — it doesn't add coverage, just an extra stat syscall. Not blocking, but worth removing or replacing with a comment explaining what real case it's meant to catch, since `tests/tools/test_jail.py::test_path_whose_parent_resolves_outside_the_jail_is_rejected` is actually satisfied by the *first* `_resolve_in_jail` call, not this second one.

### [PASS] Jail traversal, symlink, and prefix-confusion cases are well covered

`_resolve_in_jail` is tested in isolation for relative/absolute acceptance, `..` traversal, symlink escape, and the `startswith` prefix trap (`jail` vs `jail_evil`), matching the Fail-Fast and Law-of-Demeter-adjacent "resolve, don't string-compare" approach documented in the code. Good test-with-implementation discipline.

### [PASS] Exception handling matches project error-handling rules

`_guarded` catches specific expected exceptions and converts each to an observable `ToolResult` with an appropriate log level (WARNING for jail violations, INFO for routine errors), and the single catch-all `except Exception` is a documented, justified process-boundary handler (`# noqa: BLE001` with rationale in the docstring) rather than a silent swallow — satisfying rule (c) in both the global and Python-specific exception-handling rules.
