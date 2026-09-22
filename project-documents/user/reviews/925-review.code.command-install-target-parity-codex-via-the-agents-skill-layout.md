---
docType: review
layer: project
reviewType: code
slice: command-install-target-parity-codex-via-the-agents-skill-layout
targetKind: slice
rulesSource: project
project: squadron
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/slices/925-slice.command-install-target-parity-codex-via-the-agents-skill-layout.md
aiModel: z-ai/glm-5.3-flash
status: complete
dateCreated: 20260922
dateUpdated: 20260922
reviewedSha: 0129e0828119236946215b1be6d4612490821b6d
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 34
findings:
  - id: F001
    severity: fail
    category: correctness
    summary: "write_skill_dirs records pre-existing destination files as squadron-owned, so uninstall later deletes user files"
    location: "src/squadron/skills/targets.py:96-98"
  - id: F002
    severity: concern
    category: error-handling
    summary: "`except SystemExit` cannot catch `typer.Exit`, so setup's in-process install error path aborts the whole setup run"
    location: "src/squadron/cli/commands/setup_install.py:176-183"
  - id: F003
    severity: concern
    category: correctness
    summary: "Agents doctor check counts any `SKILL.md` directory, reporting a false OK when the user has third-party skills"
    location: "src/squadron/cli/commands/doctor_checks.py:164"
  - id: F004
    severity: note
    category: design
    summary: "The Claude check's `/sq` root suffix is target-specific knowledge living outside `TargetDelivery`"
    location: "src/squadron/cli/commands/doctor_checks.py:178-181"
  - id: F005
    severity: note
    category: design
    summary: "Per-target presentation strings live in five parallel name-keyed tables"
    location: "src/squadron/cli/commands/setup_steps.py:57-67"
  - id: F006
    severity: note
    category: correctness
    summary: "Install's stale-removal ignores the previous receipt's recorded destination"
    location: "src/squadron/cli/commands/install.py:148-156"
  - id: F007
    severity: pass
    category: design
    summary: "Delivery-table design and test discipline are strong"
    location: "src/squadron/skills/targets.py:105-152"
---

# Review: code — slice 0

**Verdict:** FAIL
**Model:** z-ai/glm-5.3-flash

## Findings

### [FAIL] write_skill_dirs records pre-existing destination files as squadron-owned, so uninstall later deletes user files

`write_skill_dirs` copies the skill tree with `shutil.copytree(..., dirs_exist_ok=True)` (merging into an existing directory), then records ownership by walking the **destination**: `for copied in sorted(dest_dir.rglob("*"))` (src/squadron/skills/targets.py:96-98). Any file already sitting in an installed skill directory that squadron did not write is claimed by the receipt.

Reachable sequence with stock code:
1. `sq install-commands --ide codex` writes `~/.agents/skills/sq-review/SKILL.md`; receipt records it.
2. User adds their own `sq-review/notes.md` — a scenario the slice itself treats as real (`test_a_directory_holding_a_user_file_is_not_pruned`, tests/cli/test_install_commands.py).
3. User re-runs the install. `rglob` picks up `notes.md`; the receipt now names `sq-review/notes.md`, and the install output even lists it as "Installed".
4. `sq uninstall-commands --ide codex` deletes both files — the user's `notes.md` is destroyed.

This is the same ownership-confusion bug issue #65 fixed for the Claude tree, reintroduced through a different route; the module's own docstring ("Recording the directory alone would leave uninstall unable to tell squadron's files from the user's") states the invariant the implementation then violates. The Claude writer (`write_flat_markdown`, src/squadron/skills/targets.py:72-78) is correct because it globs the **source**; the agents writer must do the same — walk `skill_dir.rglob("*")` and map each source file to its destination-relative path. The test suite misses it because `test_a_directory_holding_a_user_file_is_not_pruned` adds the user file after install, never reinstall-then-uninstall.

### [CONCERN] `except SystemExit` cannot catch `typer.Exit`, so setup's in-process install error path aborts the whole setup run

`_install_sq_commands` wraps `install_for_target` in `except SystemExit` with the comment "Typer raises SystemExit/Exit on its own error paths." In this dependency set, `typer.Exit` **is** `click.exceptions.Exit`, which subclasses `RuntimeError`, not `SystemExit` (.venv/lib/python3.13/site-packages/click/exceptions.py:298; typer/__init__.py:9). `install_for_target` raises `typer.Exit(code=1)` on two realistic paths — bundle source not found (src/squadron/cli/commands/install.py:47) and a malformed install receipt (src/squadron/cli/commands/install.py:134) — so the handler never fires: the exception propagates out of `run_install`, out of the un-guarded `outcome = run_install(step.check_name)` in `_run_interactive` (src/squadron/cli/commands/setup.py), and is swallowed by Typer's top-level `Exit` handling, ending `sq setup` mid-flow with no `InstallOutcome` message. This contradicts the module's stated contract ("Never raises: a failed install must leave setup able to fall back to telling the user the command").

Additionally, if the clause ever did catch, `exc.code` is the wrong attribute for click's `Exit` (it exposes `exit_code`), so the branch would `AttributeError`. Fix: `except typer.Exit as exc:` and read `exc.exit_code`; add a test driving `install_for_target` to raise `typer.Exit` and asserting a failed `InstallOutcome` (the current tests only cover `OSError` and the mocked happy path). Note this is pre-existing logic, but the slice made the in-process call real (previously `install_commands()` was mocked out entirely) and rewrote these exact lines, so the now-live path should be corrected here.

### [CONCERN] Agents doctor check counts any `SKILL.md` directory, reporting a false OK when the user has third-party skills

`_count_installed` for `CommandTarget.AGENTS` counts every directory under `~/.agents/skills` containing a `SKILL.md`. That root is shared with every other agent-skill source (the slice's own targets.py docstring calls it "the documented user root"), so a Codex user with five unrelated skills and zero squadron skills gets `"5 command(s)"` and an OK row — a false positive for the very condition the check exists to report. The Claude check avoids this by scoping to the `sq` pack subdirectory (src/squadron/cli/commands/doctor_checks.py:178-181); the agents check has no equivalent scoping to squadron's own skill names. Suggested fix: count only directories matching the bundle's skill names (available from `_get_commands_source()/agents` or a `bundle_subdirs`-like listing on `TargetDelivery`), and add a test with a foreign skill directory asserting the row stays WARN.

### [NOTE] The Claude check's `/sq` root suffix is target-specific knowledge living outside `TargetDelivery`

`targets.py`'s module docstring promises "Everything that differs between the two lives in `DELIVERIES`", but `check_commands_installed` special-cases Claude's check root (`root = root / "sq"`) inside doctor_checks. The comment justifies keeping today's behavior, but a third target added to `DELIVERIES` would silently reuse whichever counting/root convention the author remembers. A `check_root_suffix: Path | None` (or similar) field on `TargetDelivery` would move this into the table the slice built for exactly this purpose.

### [NOTE] Per-target presentation strings live in five parallel name-keyed tables

Adding a `CommandTarget` requires edits in `_RECHECK_MAP`, `DOCS_ANCHOR`, `_EXPLANATION`, `_human_title`'s local `_TITLE_MAP`, and `setup_install._INSTALLERS` (src/squadron/cli/commands/setup_install.py). The slice mitigates this with `test_both_command_check_names_are_registered_in_every_name_keyed_table` (tests/cli/test_setup.py), which turns silent omission into a loud failure — a reasonable trade-off, but folding title/explanation/anchor into `TargetDelivery` would remove the parallel-registration requirement entirely.

### [NOTE] Install's stale-removal ignores the previous receipt's recorded destination

The slice fixed the uninstall side of destination drift (D6) but install's stale-removal still computes `stale_path = target_dir / stale` against the *new* destination while `previously_written` was recorded at the previous one. Reinstalling to a different `--target` with the same receipt name orphans the old install's files (the overwritten receipt no longer records them, so no uninstall can reach them). Low impact because same-scope/same-target receipts imply the same destination, but worth a guard or a mismatch warning mirroring the uninstall behavior at src/squadron/cli/commands/install.py:228-238.

### [PASS] Delivery-table design and test discipline are strong

The `TargetDelivery` frozen dataclass plus the `assert set(DELIVERIES) == set(CommandTarget)` invariant is a clean Open/Closed structure: adding a target means adding one table entry plus its tests, not editing installer/check branches. The tests were authored with the implementation and cover the right things: receipt-name stability (`test_claude_machine_receipt_name_is_unchanged`), alias equivalence, drift guards verified to have teeth against a copied bundle (`test_drift_guard_fails_on_a_command_with_no_twin`), mechanical `HOME`-redirection guards (`test_no_test_writes_under_a_real_machine_root`), and the Typer-OptionInfo trap that motivated `install_for_target`. `ruff`/`pyright` config in pyproject.toml carries the required rule set, with the tests-outside-pyright deviation explicitly tracked under issue #50.

### Run Digest

- Response length: 8536 chars
- Response is newline-free: no
- Tool calls made: 34
- Tool calls failed: 3
- Stop reason: stop
- Reasoning characters: 65961
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
