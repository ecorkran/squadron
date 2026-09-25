---
docType: review
layer: project
reviewType: code
slice: command-install-target-parity-codex-via-the-agents-skill-layout
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/925-slice.command-install-target-parity-codex-via-the-agents-skill-layout.md
aiModel: z-ai/glm-5.3
status: complete
dateCreated: 20260922
dateUpdated: 20260922
reviewedSha: 0d41590ed59860f11c7dce896624aa2da6fe2049
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 38
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "Install's stale-removal ignores the receipt's recorded destination — it misreports removals and can delete user files across destinations"
    location: "src/squadron/cli/commands/install.py:151-161"
  - id: F002
    severity: concern
    category: security
    summary: "Receipt entries are unlinked with no path-containment check"
    location: "src/squadron/cli/commands/install.py#uninstall_commands"
  - id: F003
    severity: concern
    category: testing
    summary: "The doctor check's designed failure mode — unreadable bundle — has no test"
    location: "src/squadron/cli/commands/doctor_checks.py:155-165"
  - id: F004
    severity: note
    category: duplication
    summary: "`--ide` parsing is duplicated between install.py and setup.py"
    location: "src/squadron/cli/commands/setup.py#setup"
  - id: F005
    severity: note
    category: duplication
    summary: "`_DEFAULT_COMMANDS_DIR` now duplicates the delivery table's Claude root"
    location: "src/squadron/cli/commands/doctor_checks.py:31-32"
  - id: F006
    severity: note
    category: correctness
    summary: "The AGENTS `local_root` is an assertion without the citation its sibling has"
    location: "src/squadron/skills/targets.py:163-175"
  - id: F007
    severity: note
    category: design
    summary: "`check_root(local=...)` is never exercised, so `--local` installs always read as \"not installed\""
    location: "src/squadron/skills/targets.py:134-137"
  - id: F008
    severity: note
    category: test-quality
    summary: "Test helpers typed as `object` propagate `# type: ignore[attr-defined]` across the new tests"
    location: "tests/cli/test_install_commands.py"
  - id: F009
    severity: pass
    category: design
    summary: "Delivery-table design and bijection drift-guard are well-executed"
    location: "src/squadron/skills/targets.py"
---

# Review: code — slice 925

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3

## Findings

### [CONCERN] Install's stale-removal ignores the receipt's recorded destination — it misreports removals and can delete user files across destinations

`install_for_target` reads the previous receipt (line ~137) but uses only `previous.files_written`, discarding `previous.destination`, and then resolves every stale entry against the *current* `target_dir` (line 155). Two consequences when the receipt's destination differs from the current one (any two `--target` values sharing a pack name):

1. **False reporting.** Every previously-written file is "stale" at the new destination, doesn't exist there, yet `removed.append(stale)` (line 161) runs unconditionally — the user sees "Removed 10 stale command(s)" listing files that were never touched, while they sit untouched at the old destination. The comment justifying the unconditional append ("the desired end state is absent, and it already holds") is only valid for the *same* destination.
2. **Cross-destination deletion of user files.** If the new bundle dropped a file the old receipt names (e.g. `sq/retired.md`) and the user has their own file of that name at the new destination, `stale_path.unlink()` deletes the user's file — issue #65's ownership confusion arriving via a destination switch.
3. **Orphaning.** After the receipt is overwritten with the new destination, the files at the old destination are unreferenced forever; no uninstall can remove them.

This is the mirror image of the D6 bug the same slice fixed on the uninstall side (`uninstall_commands` now guards `requested != destination.resolve()`). The fix is symmetric and cheap: skip stale-removal (or rebase it on the old destination) unless `previous.destination` matches `target_dir`. No test covers a destination switch; every install test reuses one target.

### [CONCERN] Receipt entries are unlinked with no path-containment check

Both deletion paths trust `receipt.files_written` absolutely: `path = destination / relative; path.unlink()` in `uninstall_commands`, and `stale_path = target_dir / stale; stale_path.unlink()` at install.py:155-159. `InstallReceipt` (pydantic, `src/squadron/skills/models.py`) validates *types*, not path shape — an entry like `"../../.ssh/known_hosts"` (a corrupted, hand-edited, or partially-written receipt) resolves and unlinks outside the install root. The directory-pruning loop *does* have a containment guard (`destination in directory.parents`), which makes its absence on the unlink loop look accidental rather than deliberate. Given this project's history is precisely about uninstall deleting things it doesn't own, a cheap `destination in path.resolve().parents` (or `path.relative_to(destination)`) check on both unlink sites would close the gap and cost nothing in the happy path.

### [CONCERN] The doctor check's designed failure mode — unreadable bundle — has no test

`_squadron_skill_names` is the only swallow-and-fallback path in the new code: it catches `(OSError, typer.Exit)`, logs at ERROR via `logger.exception`, and returns an empty set so the check WARNs instead of claiming a false OK. The design principle the project states is that each identified failure mode must be *observable* and that at least one test asserts the observable signal. No test exercises this path — nothing monkeypatches `get_commands_source` to raise (e.g. `typer.Exit(code=1)`) and asserts the check still returns WARN with the codex fix hint rather than OK. `test_agents_check_ignores_third_party_skills` covers the empty-set *consequence* but not the *fallback trigger*, so a refactor that catches the wrong exception type (or drops the `typer.Exit` arm, which is easy to do since `typer.Exit` is a `RuntimeError`, not a `SystemExit`) would pass the suite silently.

### [NOTE] `--ide` parsing is duplicated between install.py and setup.py

`setup()` inlines the exact `normalize_target` → `typer.BadParameter` translation that install.py's `_parse_target` (install.py:50-55) already implements. Both must exit 2 naming the accepted spellings; today both tests (`test_setup_rejects_an_unknown_ide`, `test_unknown_ide_exits_two_naming_the_accepted_values`) pin that, but the message-formatting logic exists twice. Moving `_parse_target` into `squadron/skills/targets.py` (or a small shared CLI helper) would let both surfaces share one definition, per CLAUDE.md's one-place-per-value rule.

### [NOTE] `_DEFAULT_COMMANDS_DIR` now duplicates the delivery table's Claude root

`_DEFAULT_COMMANDS_DIR = Path.home() / ".claude" / "commands"` carries a comment saying it's defined locally "to keep the pure check layer free of CLI coupling." That justification predates this slice: `DELIVERIES[CommandTarget.CLAUDE].machine_root` (`.claude/commands`) now lives in `squadron/skills/targets.py`, a pure data module with no CLI coupling that `doctor_checks` already imports. The same physical root is now defined in two places, so moving Claude's commands directory would require editing both. Consolidating `check_skill_packs`'s default onto the delivery table would close it.

### [NOTE] The AGENTS `local_root` is an assertion without the citation its sibling has

The machine root carries a source citation ("`~/.codex/skills` is marked deprecated in Codex's own source; the documented user root is `~/.agents/skills` (D2)"), but `local_root=Path(".agents/skills")` — i.e. `<cwd>/.agents/skills` — carries no equivalent evidence. If agent-skill runtimes do not read project-local skills from that path, `sq install-commands --ide codex --local` writes to a location nothing reads while reporting success. I could not verify Codex's project-local skill discovery from this repository; confirming that behavior (or documenting the assumption the way D2 does) would prevent a silently dead install path.

### [NOTE] `check_root(local=...)` is never exercised, so `--local` installs always read as "not installed"

`check_root` accepts a `local` flag, but no caller passes `local=True` — `check_commands_installed` (doctor_checks.py:195) always uses the machine-scope default. Net effect: a user who ran `sq install-commands --local` gets a WARN row ("not installed at ~/.claude/commands/sq") from `sq doctor` and from setup's recheck loop, with a fix hint telling them to run the machine install they deliberately avoided. That's inherited behavior for Claude, but the parameter's existence suggests an intent that never landed. Either wire it (e.g. check the machine root, fall back to the local root) or drop the parameter until a caller needs it.

### [NOTE] Test helpers typed as `object` propagate `# type: ignore[attr-defined]` across the new tests

The new helpers (`_install_with(...) -> object`, and the `result.output`/`result.exit_code` accesses) copy the file's pre-existing `-> object` + `# type: ignore[attr-defined]` pattern, adding roughly forty more suppression comments in this diff alone. Annotating the helpers as returning `typer.testing.Result` would delete all of them and let the assertions be checked rather than ignored. This matters more once pyright's `include` widens to `tests/` (tracked in issue #50 per the pyproject comment).

### [PASS] Delivery-table design and bijection drift-guard are well-executed

The `TargetDelivery`/`DELIVERIES` design is a textbook fix for the OCP problem this slice faced: adding a third runtime means one enum member plus one table entry, with `assert set(DELIVERIES) == set(CommandTarget)` failing fast at import and `test_deliveries_covers_every_member` pinning it. The check-name-keyed tables in `setup_steps.py`/`setup_install.py` all derive their keys from `DELIVERIES[...]` expressions rather than re-typing strings, so a rename propagates from one definition — and `test_both_command_check_names_are_registered_in_every_name_keyed_table` mechanically verifies every table resolves both names, which addresses CLAUDE.md's "never use user-accessible labels as logical structure" concern. The drift-guard tests are verified consistent with the committed bundle (12 ↔ 12 bijection, `openai.yaml` exactly mirroring `disable-model-invocation`, no argument-substitution tokens), and the receipt-naming scheme preserves the pre-#65 `squadron-commands` machine name, as `test_claude_machine_receipt_name_is_unchanged` pins.

### Run Digest

- Response length: 9646 chars
- Response is newline-free: no
- Tool calls made: 38
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 70532
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
