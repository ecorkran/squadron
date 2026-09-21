---
docType: review
layer: project
reviewType: code
slice: slash-command-parity-documentation-and-live-evidence
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/386-slice.slash-command-parity-documentation-and-live-evidence.md
aiModel: moonshotai/kimi-k2.7-code
status: complete
dateCreated: 20260921
dateUpdated: 20260921
reviewedSha: 988bb66de6b528670244318894b68eccef380de8
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Broad `except Exception` catches more than Click parse errors"
    location: "tests/docs/test_pr_doc_examples.py:90-93"
  - id: F002
    severity: concern
    category: parsing
    summary: "Bash-fence regex is stricter than project lenient-parsing convention"
    location: "tests/docs/test_pr_doc_examples.py:22"
  - id: F003
    severity: concern
    category: parsing
    summary: "Flag-token regex excludes valid digits in option names"
    location: "tests/cli/test_command_surface.py:33"
  - id: F004
    severity: note
    category: typing
    summary: "`_resolve_command` uses weak `object` return type"
    location: "tests/docs/test_pr_doc_examples.py:62"
  - id: F005
    severity: pass
    category: testing
    summary: "Drift tests cover CLI surface agreement and include fail-proof test"
    location: "tests/cli/test_command_surface.py:1-142"
  - id: F006
    severity: pass
    category: testing
    summary: "Documentation examples are validated against real Click commands"
    location: "tests/docs/test_pr_doc_examples.py:1-95"
  - id: F007
    severity: pass
    category: testing
    summary: "Install tests updated consistently for new `pr.md` command file"
    location: "tests/cli/test_install_commands.py:15-165"
---

# Review: code — slice 0

**Verdict:** CONCERNS
**Model:** moonshotai/kimi-k2.7-code

## Findings

### [CONCERN] Broad `except Exception` catches more than Click parse errors

`test_every_example_parses_against_the_real_command` catches `Exception` (with `noqa: BLE001`) and re-raises as `AssertionError`. While the exception is not swallowed, the Python Rules require specific exception types or re-raising after logging at ERROR level. Click parsing raises `click.ClickException` and subclasses such as `BadParameter`/`MissingParameter`; the handler should target that family rather than `Exception`, so unexpected test-setup errors are not wrapped into a misleading "example failed to parse" message.

### [CONCERN] Bash-fence regex is stricter than project lenient-parsing convention

`_BASH_FENCE_RE = re.compile(r"```bash\n(.*?)```", re.DOTALL)` requires an exact `bash` info string immediately followed by `\n` and a closing ` ``` ` without trailing spaces or attributes. Per CLAUDE.md, parsers should prefer lenient matching and tolerate common format variations. Consider a pattern such as `r"```bash(?:\s+[^\n]*)?\r?\n(.*?)```"` to tolerate trailing info-string content, CRLF line endings, and trailing spaces on the closing fence.

### [CONCERN] Flag-token regex excludes valid digits in option names

`_FLAG_TOKEN_RE = re.compile(r"--[a-z][a-z-]*")` only matches lowercase letters and hyphens. Click option names can contain digits (e.g., `--sha-256`). If a command file documents such a flag, the drift test would either silently drop it or report it as unsupported, producing a false signal. Prefer a more permissive pattern such as `--[a-z][a-z0-9-]*`.

### [NOTE] `_resolve_command` uses weak `object` return type

The helper returns `tuple[object, list[str]]`. The first element is a Click command, so `click.Command` would make the contract explicit and remove the need for the `type: ignore[attr-defined]` on the subsequent `.make_context()` call.

### [PASS] Drift tests cover CLI surface agreement and include fail-proof test

The module cleanly separates extraction, CLI introspection, and comparison logic. It includes `test_comparison_fails_on_incomplete_section` to prove the assertion can fail, avoiding vacuous green tests. The `_COMMANDS_UNDER_TEST` table makes extending coverage to additional subcommands a single-line change.

### [PASS] Documentation examples are validated against real Click commands

The test mechanically verifies that every `sq review pr` / `sq pr` example in README.md, docs/COMMANDS.md, and docs/QUICKSTART.md parses against the actual registered command, including handling of `$` prompts, line continuations, and trailing comments. The `test_at_least_one_example_collected` guard prevents a silent zero-example pass.

### [PASS] Install tests updated consistently for new `pr.md` command file

The existing install/uninstall suite was updated in one place: `EXPECTED_FILES` and `EXPECTED_COMMANDS` now include `pr.md`, counts moved from 9 to 10, and the expected subcommand reference is `"sq pr"`. The changes are minimal and consistent across all assertions.

## Response

- **F001 (fixed)**: `test_every_example_parses_against_the_real_command` now catches
  `click.ClickException` instead of `Exception`; the `noqa: BLE001` is removed since
  the handler is no longer blind.
- **F002 (fixed)**: `_BASH_FENCE_RE` now tolerates trailing info-string content after
  `bash` and CRLF line endings: `` r"```bash(?:[^\S\r\n]+[^\n]*)?\r?\n(.*?)```" ``.
- **F003 (fixed)**: `_FLAG_TOKEN_RE` now allows digits in flag names:
  `r"--[a-z][a-z0-9-]*"`.
- **F004 (fixed)**: `_resolve_command` now returns `tuple[click.Command, list[str]]`;
  the call sites use `isinstance` narrowing on `click.Group` instead of
  `type: ignore[attr-defined]`, and `command.make_context(...)` no longer needs a
  type-ignore either.

Verification: `tests/docs/test_pr_doc_examples.py` and `tests/cli/test_command_surface.py`
pass (6/6); `ruff format`/`ruff check` clean on both files; pre-existing pyright
errors in `test_command_surface.py` (private-member access on
`_get_commands_source`, Click's partially-typed `Command.params`) are unchanged by
this fix and were confirmed pre-existing via a stash-based baseline diff — out of
scope for this review's findings.

### Run Digest

- Response length: 3523 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 40687
- `## Summary` located: no
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
