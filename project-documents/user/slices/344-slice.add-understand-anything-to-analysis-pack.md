---
docType: slice-design
slice: add-understand-anything-to-analysis-pack
project: squadron
parent: 340-slices.skill-pack-infrastructure.md
initiative: 340
index: 344
dependencies: [342]
interfaces: []
dateCreated: 20260628
dateUpdated: 20260717
status: deprecated
deprecationReason: >
  Superseded by Claude Code's native understand-anything marketplace plugin
  (/plugin install understand-anything). Hosting a vendored copy in the analysis
  pack added a 33 MB Node-engine dependency, a competing command surface, and a
  3rd-party file to maintain for no bundling benefit. Branch deleted, not merged;
  tech-debt-audit remains the sole analysis-pack skill. See slice plan
  340-slices.skill-pack-infrastructure.md item (344) for full rationale.
---

# Slice Design: Add `understand-anything` to Analysis Pack

## Overview

Adds the `understand-anything` skill to the bundled analysis pack as `commands/analysis/understand-anything.md` and updates the `sq:analysis` dispatcher to route it. The skill is forked from `github:Egonex-AI/Understand-Anything` (MIT). No Python code changes are required — the installer already copies all `*.md` files from `commands/analysis/`.

## Value

Extends the analysis pack with a 7-phase deep codebase comprehension skill: scan → batch → analyze → assemble → architecture → tour → save. It produces a persistent knowledge graph (`.understand-anything/knowledge-graph.json`) and supports incremental updates via git diff fingerprinting. Together with `tech-debt-audit`, the pack covers both structural understanding and debt discovery in one `sq skills install analysis`.

## Technical Scope

### In scope
- Fork `github:Egonex-AI/Understand-Anything` to `ecorkran/understand-anything` (user action on GitHub, not a squadron code change)
- Extract `understand-anything-plugin/skills/understand/SKILL.md` from the fork
- Prepend attribution comment
- Audit SKILL.md for self-references to `/understand` command invocations and patch them to `/analysis:understand-anything`
- Add the adapted file as `commands/analysis/understand-anything.md`
- Update `commands/sq/analysis.md` dispatcher: valid skills list, usage block, new skill section

### Out of scope
- Installer, manifest, model, or CLI code changes — not required; `_install_prefix()` already copies all `*.md` from `commands/analysis/`
- `sq doctor` changes — the Skill Packs section (from slice 343) reports analysis pack presence; no per-file reporting is needed

## Dependencies

- [342] — `commands/analysis/` directory and installer `_install_prefix()` copy-all-md behavior both exist
- [343] — `sq skills uninstall analysis` and `sq doctor` Skill Packs section are used in verification, but not required for the slice to function

## Architecture

### File addition: `commands/analysis/understand-anything.md`

The skill file is sourced from `github:Egonex-AI/Understand-Anything` at path
`understand-anything-plugin/skills/understand/SKILL.md`, forked to `ecorkran/understand-anything`.

It is adapted (attribution + self-reference patching, described below) and placed at
`commands/analysis/understand-anything.md` in the squadron repo. The installer's
`_install_prefix()` uses `source_path.glob("*.md")` — adding this file to `commands/analysis/`
is sufficient for it to be picked up by `sq skills install analysis`. No installer changes required.

**Attribution comment** (prepended before YAML frontmatter, matching `tech-debt-audit.md`):
```
<!-- Forked from github:ecorkran/understand-anything (MIT). Original: github:Egonex-AI/Understand-Anything, Copyright 2026 Yuxiang Lin and Infinite Universe Inc. -->
```

**Filename:** `understand-anything.md` — the filename determines the installed command name under the
prefix, so the skill becomes `/analysis:understand-anything` when installed. This must match the
dispatcher's delegation target and the patched self-references in the skill body.

### Self-reference audit and patching

SKILL.md instructs Claude to invoke the skill as `/understand [flags]` in several places — for
example, mid-pipeline instructions to re-invoke for incremental updates. Under the analysis pack
the skill lives at `/analysis:understand-anything`, so any instructional invocation must be updated.

**Audit target:** Every occurrence of `/understand` that is an instruction to Claude to invoke the
skill by its slash-command name (e.g., "Run `/understand --auto-update`", "invoke `/understand`
again"). These are the references that would break if left unchanged.

**Do not patch:** Occurrences that are purely descriptive — section headings, output directory paths
(`.understand-anything/`), attribute names, or prose explaining what the skill does. The string
`understand-anything` (with a hyphen, not a slash prefix) does not need patching.

**Patch rule:** Replace instructional `/understand` with `/analysis:understand-anything`. When flags
appear (e.g., `/understand --full`, `/understand --auto-update`), preserve the flags verbatim after
the new command name.

### Dispatcher update: `commands/sq/analysis.md`

Three targeted changes to the existing file:

1. **Valid skills line** — add `understand-anything` to the enumerated skill names:
   ```
   Valid skills: `tech-debt-audit`, `understand-anything`
   ```

2. **Usage block** — add the `understand-anything` invocation pattern:
   ```
   /sq:analysis tech-debt-audit [target]
   /sq:analysis understand-anything [path] [--full|--auto-update|--no-auto-update|--review|--language <lang>]
   ```

3. **New skill section** — append after the `tech-debt-audit` section:

   ```markdown
   ## Skill: understand-anything

   Delegate to the understand-anything skill.

   Invoke `/analysis:understand-anything` passing any `[path]` and flags from `$ARGUMENTS`
   as the arguments.

   The skill builds a knowledge graph of the codebase (or `[path]` if specified) through a
   7-phase pipeline: scan → batch → analyze → assemble → architecture → tour → save. It
   produces `.understand-anything/knowledge-graph.json` at the repository root, supports
   incremental updates via git diff fingerprinting, and runs up to 5 concurrent
   file-analyzer subagents.

   If the skill is not installed, inform the user:
   \`\`\`
   The analysis pack is not installed. Run `sq skills install analysis` to install it.
   \`\`\`
   ```

## Integration Points

### Receives from slice 342
- `commands/analysis/` directory structure and installer copy-all-md behavior
- `sq skills install analysis` installs the expanded pack (both skills) without any change to installer logic

### Provides to nothing
No downstream slices depend on this. `sq doctor` Skill Packs section (from 343) reports analysis
pack presence automatically; no new doctor code is needed.

## Success Criteria

1. `commands/analysis/understand-anything.md` is present in the repo with the attribution comment
   prepended and no broken `/understand` invocation references in the skill body.
2. `sq skills install analysis` installs both `tech-debt-audit.md` and `understand-anything.md`
   to `~/.claude/commands/analysis/`.
3. After install, the receipt at `~/.config/squadron/receipts/analysis.toml` lists both files
   in `files_written`.
4. `/analysis:understand-anything` invokes the skill correctly in a Claude Code session.
5. `/sq:analysis understand-anything` routes to `/analysis:understand-anything` via the dispatcher.
6. `sq skills uninstall analysis` removes both skill files cleanly (receipt lists both).
7. Existing test suite remains green with no changes to `test_cli_skills.py`.
8. User has run a full knowledge-graph build on a real repo before merge (see Verification Walkthrough step 7).

## Verification Walkthrough

**Prereq:** squadron dev install (`uv pip install -e .`); analysis pack not currently installed.

**1. Install the expanded analysis pack**
```bash
sq skills install analysis
# Installed pack 'analysis': 2 file(s) → /Users/<you>/.claude/commands/analysis
ls ~/.claude/commands/analysis/
# tech-debt-audit.md  understand-anything.md
```

**2. Receipt lists both files**
```bash
cat ~/.config/squadron/receipts/analysis.toml
```
Expected (both files in `files_written`):
```toml
pack_name = "analysis"
surface = "prefix"
destination = "/Users/<you>/.claude/commands/analysis"
files_written = [
    "tech-debt-audit.md",
    "understand-anything.md",
]
```

**3. Doctor shows pack installed**
```bash
sq doctor -v
```
Expected in "Skill Packs" section:
```
Skill Packs
  ✓ analysis    installed at ~/.claude/commands/analysis
```

**4. Dispatcher routes `understand-anything`**

Open a Claude Code session in any git repo. Run:
```
/sq:analysis understand-anything
```
Expected: Claude delegates to `/analysis:understand-anything` and begins the scan phase (prompts
about parameters or starts the 7-phase pipeline immediately).

**5. Direct invocation also works**
```
/analysis:understand-anything
```
Expected: same skill entry point, same behavior as step 4.

**6. Uninstall removes both files**
```bash
sq skills uninstall analysis
# Uninstalled pack 'analysis': 2 file(s) removed from /Users/<you>/.claude/commands/analysis
ls ~/.claude/commands/analysis/ 2>&1
# ls: .../analysis: No such file or directory   ← prefix dir removed (empty after uninstall)
ls ~/.config/squadron/receipts/
# (analysis.toml absent)
```

**7. User verifies skill on a real repo (required before merge)**

In a Claude Code session open on a small-to-medium git repo:
```
/sq:analysis understand-anything
```
Observe: skill scans repo, batches files, produces `.understand-anything/knowledge-graph.json`.
Verify output file exists and contains a valid JSON structure.

Incremental test: make a small code change, then:
```
/sq:analysis understand-anything --auto-update
```
Observe: only changed files are re-analyzed (not a full re-scan).

## Implementation Notes

### Development Order
1. Fork `github:Egonex-AI/Understand-Anything` to `ecorkran/understand-anything` on GitHub
2. Extract `understand-anything-plugin/skills/understand/SKILL.md` from the fork
3. Prepend attribution comment; audit and patch all instructional `/understand` references
4. Save as `commands/analysis/understand-anything.md`
5. Update `commands/sq/analysis.md` (valid skills line, usage block, new skill section)
6. Run `sq skills install analysis` locally; verify receipt shows both files
7. Test both `/sq:analysis understand-anything` and `/analysis:understand-anything` in a live Claude Code session
8. Run knowledge-graph build on a real repo; confirm `.understand-anything/knowledge-graph.json` is produced
9. Run existing test suite (`pytest tests/skills/`) to confirm nothing is broken

### Testing
No new tests are required for this slice — the installer test fixtures use local source directories
and test the copy-all-md behavior independent of which specific files exist in `commands/analysis/`.
Existing tests remain green when a second `*.md` file is added to the bundled pack.

Optional: add an assertion to the bundled-install integration test that
`commands_dir / "analysis" / "understand-anything.md"` exists after install — a small regression
guard that confirms the new file is included in the wheel.
