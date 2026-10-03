---
docType: review
layer: project
reviewType: code
slice: codex-parity-for-skill-packs-and-provider-access
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/928-slice.codex-parity-for-skill-packs-and-provider-access.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261003
dateUpdated: 20261003
reviewedSha: c1d8a230d072d18679dd8e21ad2e81b664221980
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 0
diffTruncated: false
durationSeconds: 30.7
squadronVersion: 0.18.2
findings:
  - id: F001
    severity: concern
    category: design
    summary: "Library module `receipts.py` now prints to the console"
    location: "src/squadron/skills/receipts.py:61-102"
  - id: F002
    severity: concern
    category: correctness
    summary: "Machine-wide Codex rules are removed by any non-local agents uninstall, including `--target`"
    location: "src/squadron/cli/commands/install.py:303-308"
  - id: F003
    severity: concern
    category: error-handling
    summary: "Install can fail after the work is done when the rules file is unwritable"
    location: "src/squadron/cli/commands/install.py:208-222"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Malformed YAML is reported as \"no YAML frontmatter\""
    location: "src/squadron/skills/pack_layouts.py:127-137"
  - id: F005
    severity: concern
    category: correctness
    summary: "Agents `installed_path` and receipt names can collide across packs"
    location: "src/squadron/skills/pack_layouts.py:213-217"
  - id: F006
    severity: note
    category: behavior-change
    summary: "Doctor skill-pack rows are no longer sorted by name"
    location: "src/squadron/cli/commands/doctor_checks.py:560-564"
  - id: F007
    severity: note
    category: design
    summary: "Cross-command import and `str(None)` coercion"
    location: "src/squadron/cli/commands/skills.py:13"
  - id: F008
    severity: pass
    category: design
    summary: "Layout table and receipt refactor"
    location: "src/squadron/skills/pack_layouts.py:219-240"
---

# Review: code — slice 928

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Library module `receipts.py` now prints to the console

`remove_receipt_files` is a data-layer function. It now imports `rich.print` and emits the "Skipping receipt entry outside…" warning itself. This couples the skills package to the CLI presentation layer, and the pure check layer imports from it indirectly. The function should return the skipped entries, or log through `logging.warning`, and let the CLI print them. The test has to capture stdout to assert the warning, which points to the same inversion.

### [CONCERN] Machine-wide Codex rules are removed by any non-local agents uninstall, including `--target`

`local_honored` is False whenever `--target` is given. Uninstalling from a custom `--target` therefore deletes the machine-wide `squadron.rules`, even though a machine install elsewhere may still need it. The rules file is shared state with no reference counting. The comment only covers `--local`. Either skip rule removal when `target` is set, or only remove the file when no other agents receipt remains.

### [CONCERN] Install can fail after the work is done when the rules file is unwritable

`_ensure_codex_rules` runs after skills and the receipt are written. `write_sq_rules` can raise `OSError`, for example when `CODEX_HOME` is read-only or `rules/` is a file. That surfaces as a traceback with a nonzero exit after a successful install. The missing-home case is handled explicitly, but this failure mode is not. Catch `OSError`, warn with the path, and add a test that the warning appears.

### [CONCERN] Malformed YAML is reported as "no YAML frontmatter"

`_skill_frontmatter` swallows `yaml.YAMLError` and returns `None`. It does the same for a non-dict result. The caller then tells the pack author the frontmatter is missing, which is misleading when the fence is present but the YAML is broken. The project rule is that a swallowed exception needs a justification and should be observable. Return the parse error, or distinguish "absent" from "invalid", so the install error names the real cause.

### [CONCERN] Agents `installed_path` and receipt names can collide across packs

For prefix packs, `root.glob(f"{entry.prefix}-*/SKILL.md")` reports a pack installed if any skill shares the prefix. That includes skills from another pack or source, such as a pack named `analysis-extra`, and doctor and `list` would show a false "installed". The prefix is also interpolated into a glob unescaped. Separately, `receipt_name(pack, AGENTS)` yields `<pack>-agents`, which can equal the Claude receipt of a pack literally named `<pack>-agents`. Prefer checking against the receipt or the known skill names, or at least validate pack names.

### [NOTE] Doctor skill-pack rows are no longer sorted by name

The old `results.sort(key=lambda r: r.name)` was dropped, so row order now follows manifest order. A Claude-only machine therefore does not necessarily see the same order as before. The code comment claims the rows are unchanged. Restore the sort, or say that the order changed.

### [NOTE] Cross-command import and `str(None)` coercion

`skills.py` imports `parse_ide_option` from `install.py`, which couples two command modules. It belongs in a shared CLI helper. Separately, `pack_layouts.py` uses `str(entry.dispatch_file)` in `_naming_problems` and `_agents_installed_path`. That would turn `None` into the string `"None"` if the entry invariant were ever broken. An explicit assertion or guard is safer.

### [PASS] Layout table and receipt refactor

Moving install, installed-path and content detection into a per-target `PackLayout` table removes the duplicated path derivation across install, `list` and doctor. Validation runs before any write, so a failed install writes nothing. The uninstall path now has containment checks, and the tests cover validation errors, mismatched `--commands-dir`, legacy receipts and the doctor no-clone guarantee.

## Response (20261003)

All eight findings were checked against the code. Fixes are in `4a011aa8`.

- **F001: accepted.** `remove_receipt_files` returns a `RemovalResult` (`removed`, `skipped_outside`) and prints nothing. The CLI reports skipped entries through `report_skipped_entries` in the new `cli/commands/install_options.py`. The test asserts on the returned list instead of capturing stdout.
- **F002: accepted.** The rules file is removed only by an uninstall of the default machine install. `--local` and `--target` uninstalls leave it. New test: `test_target_codex_uninstall_keeps_the_machine_wide_rules`.
- **F003: accepted.** An `OSError` writing the rules file is caught and reported with the path and the fix, and the install still exits 0. New test: `test_unwritable_rules_warn_without_failing_the_install`.
- **F004: accepted.** `_skill_frontmatter` raises `_FrontmatterProblem`, which separates a missing block, invalid YAML (with the parser's message), and non-mapping frontmatter. New tests cover the latter two.
- **F005: accepted in part.** The receipt-name collision is fixed: `skills.toml` rejects pack names ending in `-agents` or `-local` (`reserved_receipt_suffixes()` in `targets.py`), and the prefix is `glob.escape`d. Not changed: a pack whose prefix extends another pack's (`analysis` and `analysis-extra`) can make the shorter pack's Codex status read "installed". This affects status display only, because uninstall removes exactly what the receipt lists. Rejecting nested prefixes would break Claude setups that are valid today, where `analysis/` and `analysis-extra/` don't collide.
- **F006: accepted.** Rows are sorted by name again. New test: `test_skill_pack_rows_are_sorted_by_name`.
- **F007: accepted.** `parse_ide_option` moved to `cli/commands/install_options.py`, shared by `install.py` and `skills.py`. `str(entry.dispatch_file)` is replaced by `_dispatch_file(entry)`, which raises if the PackEntry invariant is ever broken.
- **F008: pass.** No action.

### Run Digest

- Response length: 4535 chars
- Response is newline-free: no
- Tool calls made: 0
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 30.7 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
