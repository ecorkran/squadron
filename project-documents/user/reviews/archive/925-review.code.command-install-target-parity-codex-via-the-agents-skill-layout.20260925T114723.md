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
aiModel: z-ai/glm-5.3-flash
status: complete
dateCreated: 20260922
dateUpdated: 20260922
reviewedSha: 1af995cbb99fc351f793e0a4e92b1aba0962b852
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 31
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Uninstall cannot reach the receipt an overridden `--local` install wrote"
    location: "src/squadron/cli/commands/install.py:206"
  - id: F002
    severity: concern
    category: correctness
    summary: "`--target` mismatch check compares paths lexically, so equivalent spellings are refused"
    location: "src/squadron/cli/commands/install.py:227-238"
  - id: F003
    severity: pass
    category: design
    summary: "Delivery table cleanly separates per-target variance from the install loop"
    location: "src/squadron/skills/targets.py:146-176"
  - id: F004
    severity: pass
    category: correctness
    summary: "Agents-tree ownership is read from the source, closing the #65 reincarnation"
    location: "src/squadron/skills/targets.py#write_skill_dirs"
  - id: F005
    severity: pass
    category: testing
    summary: "Tests assert the real-HOME and real-receipts safety mechanically"
    location: "tests/cli/test_install_commands.py#test_no_test_writes_under_a_real_machine_root"
  - id: F006
    severity: note
    category: design
    summary: "Doctor's pure-check layer now reaches into the CLI command layer"
    location: "src/squadron/cli/commands/doctor_checks.py:155"
  - id: F007
    severity: note
    category: testing
    summary: "No test exercises the bundle-unreadable fallback in `_squadron_skill_names`"
    location: "src/squadron/cli/commands/doctor_checks.py:155-165"
  - id: F008
    severity: note
    category: design
    summary: "Per-target presentation strings remain scattered across five name-keyed tables"
    location: "src/squadron/cli/commands/setup_steps.py:57-64"
  - id: F009
    severity: note
    category: security
    summary: "Receipt `files_written` entries are unlinked without a destination-containment check"
    location: "src/squadron/cli/commands/install.py:243-249"
---

# Review: code — slice 925

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3-flash

## Findings

### [CONCERN] Uninstall cannot reach the receipt an overridden `--local` install wrote

Install resolves the receipt name from the *honored* scope (`pack_name = receipt_name(command_target, local=local_honored)`, install.py:124): `sq install-commands --target X --local` warns "--local ignored", writes to `X`, and records the machine-scope receipt `squadron-commands.toml`. Uninstall resolves the receipt name from the flags *as given* (`receipt_name(command_target, local=local)`, install.py:206), so `sq uninstall-commands --target X --local` — identical flags — reads `squadron-commands-local.toml`, gets `None`, and prints "Nothing to remove — no install receipt found. Re-run 'sq install-commands' to record one…". The receipt exists but is unreachable under the flags the user is actually passing, and the message directs them to re-install, not re-uninstall. The `--local` flag is also silently consumed here: install warns when `--target` overrides it (install.py:122-123), uninstall has no equivalent warning. The D6 fix correctly takes the *destination* from the receipt, but the receipt *lookup* still trusts the flags. Fail-safe (nothing is deleted), but a dead end for the user. Suggested fix: when the flag-derived pack name finds no receipt, also probe the sibling scope name and either use it (verifying destination) or tell the user which receipt file actually exists.

### [CONCERN] `--target` mismatch check compares paths lexically, so equivalent spellings are refused

The new D6 guard (`if requested != destination`) compares `Path(target).expanduser()` against the receipt's recorded destination without resolving either side. An install recorded with `--target ~/x` cannot be uninstalled with `--target /home/user/x`, `--target ~/x/`, a symlinked path, or any path containing `..` — all exit 1 with "Nothing was removed" despite pointing at the same directory. The failure direction is safe (refuses rather than mis-deletes), and the error message does name the recorded destination, so recovery is one retyped command — but the comparison should be canonicalized (`requested.resolve() != destination.resolve()`, with care for the not-yet-existing case) or the check should compare resolved destinations only when both exist. Related pre-existing wrinkle now load-bearing: a *relative* `--target` at install time is recorded verbatim into the receipt (install.py:68), so the recorded destination is cwd-dependent; resolving at write time would make the new guard sound.

### [PASS] Delivery table cleanly separates per-target variance from the install loop

`TargetDelivery` centralizes roots, bundle subdirs, check name, fix hint, receipt base, layout writer, and check subdir; `install.py`, `doctor_checks.py`, `setup_steps.py`, and `setup_install.py` all consume the table (verified: `DELIVERIES[...]` referenced at doctor_checks.py:629, setup_steps.py:57-64, setup_install.py:213-218). The import-time `assert set(DELIVERIES) == set(CommandTarget)` plus `test_deliveries_covers_every_member` make a missing delivery fail loudly. Adding a third target requires no edits to the install loop itself.

### [PASS] Agents-tree ownership is read from the source, closing the #65 reincarnation

`write_skill_dirs` walks the *source* tree to build the receipt, never the merged destination, so a user file dropped into an installed skill directory is never captured on reinstall and never deleted by uninstall. This is asserted at three levels: the unit test (`test_reinstall_does_not_claim_a_user_file_in_a_skill_directory`), the CLI-level reinstall sequence (`test_reinstall_then_uninstall_spares_a_user_file_in_a_skill_dir`), and the empty-dir pruning loop guards `destination in directory.parents` before climbing (install.py:254-261). The nested-directory pruning is deepest-first and verified by `test_agents_uninstall_prunes_nested_skill_directories`.

### [PASS] Tests assert the real-HOME and real-receipts safety mechanically

The new default destination `~/.agents/skills` is a path the slice introduced, and the suite guards it: `test_no_test_writes_under_a_real_machine_root` (parametrized over both targets) asserts a patched `HOME` redirects resolution away from the real home, and `test_no_test_touches_the_real_receipts_directory` pins the receipts helper. The drift guards verify they have teeth against a copied bundle, never the real one, and `test_agents_check_counts_only_squadron_skills_among_foreign_ones` asserts non-vacuously against the real bundle.

### [NOTE] Doctor's pure-check layer now reaches into the CLI command layer

`_squadron_skill_names` (doctor_checks.py:155-165) imports `get_commands_source` from `squadron.cli.commands.install` and catches `typer.Exit` — the pure check module (docstring: "no network, no subprocesses") now depends on the Typer app surface to answer a filesystem question. The fallback is correctly handled (logged at ERROR via `logger.exception`, degrades to WARN, comment justifies the swallow) and no import cycle exists, but the coupling is a smell: `bundled_skill_names` needs a *source path*, and the source-resolution logic living in `install.py` is what forces the CLI import (and the `import typer` now at doctor_checks.py:13). Moving the bundle-locating helper (e.g. into `squadron.skills`) would let the check layer depend on a non-CLI module.

### [NOTE] No test exercises the bundle-unreadable fallback in `_squadron_skill_names`

The `except (OSError, typer.Exit)` path — unreadable bundle → empty set → WARN instead of false OK — is exactly the failure-mode-observable pattern the review rules ask to be tested ("at least one test should assert the failure mode produces the expected observable signal"). The surrounding false-OK scenarios are well covered (`test_agents_check_ignores_third_party_skills`, `test_agents_check_counts_only_squadron_skills_among_foreign_ones`), but no test patches `get_commands_source` to raise and asserts the row stays WARN. Low risk since the fallback is two lines, but it is the one new I/O failure path in this slice with no direct test.

### [NOTE] Per-target presentation strings remain scattered across five name-keyed tables

`_RECHECK_MAP`, `DOCS_ANCHOR`, `_EXPLANATION`, `_human_title`'s `_TITLE_MAP`, and `_INSTALLERS` all gain entries keyed by `DELIVERIES[...].check_name`. The check name itself is defined once (good), but titles ("Install Codex skills"), explanations, and anchors are per-target data living outside `TargetDelivery`, so a new target means six table edits. The dedicated guard test (`test_both_command_check_names_are_registered_in_every_name_keyed_table`) makes omissions fail loudly rather than silently, which is an acceptable mitigation; a future slice could move these into `TargetDelivery` fields so adding a target is one table edit.

### [NOTE] Receipt `files_written` entries are unlinked without a destination-containment check

Uninstall unlinks `destination / relative` for every receipt entry without verifying the result stays inside `destination`, while the rmdir loop directly below *does* guard `destination in directory.parents`. A hand-edited or corrupted receipt (TOML shape is validated; path contents are not) could name paths outside the destination. The receipt file is user-owned and same-trust-level as the files, so this is defense-in-depth rather than an exploitable boundary — noting the asymmetry since the sibling loop already models the guard.

### Run Digest

- Response length: 8900 chars
- Response is newline-free: no
- Tool calls made: 31
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 42710
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
