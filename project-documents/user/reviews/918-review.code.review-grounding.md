---
docType: review
layer: project
reviewType: code
slice: review-grounding
project: squadron
verdict: PASS
sourceDocument: project-documents/user/slices/918-slice.review-grounding.md
aiModel: minimax/minimax-m3
status: complete
dateCreated: 20260913
dateUpdated: 20260913
reviewedSha: e71988e67988ccc05252fe5904d43b2da70deaa1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 32
findings:
  - id: F001
    severity: note
    category: uncategorized
    summary: "Dead `JailSpec.rooted_at` classmethod"
    location: "src/squadron/tools/models.py:54-59"
  - id: F002
    severity: note
    category: uncategorized
    summary: "Loose type on `_render_optional`"
    location: "src/squadron/review/persistence.py:228"
  - id: F003
    severity: note
    category: uncategorized
    summary: "Test name overstates what is verified"
    location: "tests/cli/test_install_commands.py:380-391"
  - id: F004
    severity: pass
    category: uncategorized
    summary: "Receipt-based install/uninstall fixes issue #65"
    location: "src/squadron/cli/commands/install.py:46-120"
  - id: F005
    severity: pass
    category: uncategorized
    summary: "Stop-reason evidence on every completion path"
    location: "src/squadron/providers/openai/agent.py:531-560"
  - id: F006
    severity: pass
    category: uncategorized
    summary: "`_render_optional` preserves the None-vs-zero distinction"
    location: "src/squadron/review/persistence.py:228-238"
  - id: F007
    severity: pass
    category: uncategorized
    summary: "Tool jail exclusion refactor"
    location: "src/squadron/tools/builtin/_shared.py:26-99"
  - id: F008
    severity: pass
    category: uncategorized
    summary: "Two exclusion lists kept separate by design and test"
    location: "src/squadron/review/templates/__init__.py:40-47,151-155"
  - id: F009
    severity: pass
    category: uncategorized
    summary: "End-to-end exclusion test mirrors #94"
    location: "tests/tools/test_jail_exclusions.py:99-178"
  - id: F010
    severity: pass
    category: uncategorized
    summary: "Receipt write omits `surface` when None"
    location: "src/squadron/skills/receipts.py:29-37"
  - id: F011
    severity: pass
    category: uncategorized
    summary: "No new bare-except or silent fallback paths"
    location: "unverified"
---

# Review: code — slice 918

**Verdict:** PASS
**Model:** minimax/minimax-m3

## Findings

### [NOTE] Dead `JailSpec.rooted_at` classmethod

The `rooted_at` constructor is defined with a docstring describing it as "the plain-jail convenience" but is never invoked anywhere — `materialize` builds its spec directly with `JailSpec(root=root, excluded=...)` in src/squadron/tools/registry.py:88. Either route callers through it or drop it; keeping an unused convenience constructor is dead code and slightly undermines the docstring's claim about callers wanting plain-jail behavior.

### [NOTE] Loose type on `_render_optional`

The signature is `value: object | None` but every actual caller (lines 184, 208–210) passes either an `int | None` or `str | None`. Tightening to `int | str | None` would let a future caller passing an unintended value fail at the type boundary rather than reaching `str(value)` and rendering `repr`-style output. Minor.

### [NOTE] Test name overstates what is verified

`test_no_test_touches_the_real_receipts_directory` only checks that the `_receipts_dir` helper returns a non-default path for a hardcoded input, not that any test invocation actually avoids the real receipts directory. The name and docstring imply a stronger guarantee. The test still functions as a regression guard against modifying the helper, but a stronger version would monkeypatch `DEFAULT_RECEIPTS_DIR` and assert no path passed to any tool during a real install resolves into it.

### [PASS] Receipt-based install/uninstall fixes issue #65

The rewrite correctly scopes deletion to what the previous receipt names and the current bundle no longer ships — `previously_written - set(installed)` — instead of "everything in the directory we did not write". Test coverage (tests/cli/test_install_commands.py:189-388) pins both the user-file-survives-install and the pre-receipt-upgrade-deletes-nothing shapes, which is what would have caught the original bug.

### [PASS] Stop-reason evidence on every completion path

`_stamp_tool_telemetry` writes `stop_reason`, `reasoning_chars`, and `failed_tool_calls` unconditionally before the `_tools_given` early return, so the tool-less path and the truncated-completion path both carry the evidence. Tests in tests/providers/openai/test_agentic_loop.py:738-869 pin the "normal", "length", "all-tools-failed", and "tool-less" shapes, and tests/providers/sdk/test_translation.py:259-289 pins the SDK absence. The "no fabrication" guarantee at design D12 is what keeps the digest honest.

### [PASS] `_render_optional` preserves the None-vs-zero distinction

`value is None` rather than `value or "not computed"` is exactly the fix named in the diff comments, and it is mirrored at src/squadron/review/persistence.py:291 (`0 if tool_calls_made is None else tool_calls_made`). The test at tests/review/test_persistence.py:1147-1154 makes the Amoeba retry predicate (``made == failed > 0``) explicit, which is the consumer this guard exists for.

### [PASS] Tool jail exclusion refactor

The split of `_excluding` from `resolve_in_jail` keeps the predicate and the wording/logging in two places, which is what the tests at tests/tools/test_jail.py:158-260 pin: the predicate logs nothing (`test_resolve_in_jail_does_not_log_its_own_refusals`) and `jail_violation` produces exactly one WARNING per refusal. The `is_relative_to` choice for exclusion matching is exercised by `test_sibling_sharing_a_prefix_with_an_excluded_directory_is_not_excluded`, the same trap that motivated the original jail rule.

### [PASS] Two exclusion lists kept separate by design and test

The docstring names the distinction (`diff_exclude_patterns` narrows text handed to the model; `tool_exclude_patterns` narrows paths the model may read), and `test_tool_and_diff_exclusions_do_not_bleed_into_each_other` (tests/review/test_templates.py:154-175) pins that a template declaring one must leave the other `None` in both directions. The boundary check at tests/review/test_tool_exclusions.py is what turns the constant `REVIEWS_DIR` into the single source of truth for the exclusion value.

### [PASS] End-to-end exclusion test mirrors #94

The three document-review tools (read_file, list_files, grep) are exercised against a real fixture tree containing live and archived review artifacts with a unique stale phrase. The tests assert the phrase and the filenames never reach the model content, which is the shape of the #94 bug. The "indistinguishable from a nonexistent path" check (`test_a_refusal_is_indistinguishable_from_a_nonexistent_path`) pins design D6.

### [PASS] Receipt write omits `surface` when None

The conditional inclusion (`if receipt.surface is not None`) is the right fix for TOML's missing null. The model change to `surface: SurfaceType | None = None` keeps pack receipts valid (they always set it) and command receipts valid (they always leave it None), and the `read_receipt` validation through `InstallReceipt.model_validate` accepts both shapes.

### [PASS] No new bare-except or silent fallback paths

The two `except Exception:` sites that exist are both pre-existing and annotated (`# noqa: BLE001` at src/squadron/providers/openai/agent.py:381) with the documented "executor contract says never raise" rationale. The new code uses specific `except ValueError` at install.py:65 and uninstall.py:132 with `raise typer.Exit(code=1) from None`, which is the explicit-failure pattern the project rules require.

### Run Digest

- Response length: 5921 chars
- Response is newline-free: no
- Tool calls made: 32
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 35454
- `## Summary` located: no
- `## Findings` located: yes
- Finding-shaped matches — whole response: 11
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 11
- Finding-shaped matches — surviving validation: 11
