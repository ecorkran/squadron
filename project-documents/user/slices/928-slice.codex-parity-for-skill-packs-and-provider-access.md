---
docType: slice-design
slice: codex-parity-for-skill-packs-and-provider-access
project: squadron
parent: user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: [925]
interfaces: []
dateCreated: 20260927
dateUpdated: 20260927
status: not_started
---

# Slice Design: Codex Parity for Skill Packs and Provider Access

## Overview

Slice 925 made `sq install-commands` target-aware. Two Codex gaps were left behind:

- **#125** — `sq skills install` still writes to `~/.claude/commands` ([skills.py:24](../../../src/squadron/cli/commands/skills.py#L24)). A Codex user gets files Codex never reads, and no error. `skills list` and doctor's `check_skill_packs` ([doctor_checks.py:428](../../../src/squadron/cli/commands/doctor_checks.py#L428)) hardcode the same root, so both report status for Claude only.
- **#127** — the first `$sq-review` under Codex fails on Codex's sandbox approval. The Codex model reports it as "the provider connection failed", which sends the user to their provider config. README carries a partial fix (a rule for `sq review` only, appended to `default.rules`); QUICKSTART carries nothing.

Part A threads `CommandTarget` through the skills sub-app and settles how a single-source pack declares its Codex content. Part B documents the approval rule for every `sq` command that needs it, and puts a hint at the point of failure.

Found while probing (fixed here, one line each): `commands/sq/review.md` and `commands/agents/sq-review/SKILL.md` tell the model to run `sq model list`, which does not exist — the command is `sq models list`.

## Value

- A Codex user can install, list, and uninstall skill packs, and a pack that has no Codex content fails loudly instead of installing somewhere inert.
- Pack authors get one documented format for shipping Claude and Codex content side by side. Squadron's own `analysis` pack becomes the reference example.
- Codex users hit the sandbox wall once, get told exactly what it is, and add one rule file that covers every `sq` command that reaches the network.
- `sq doctor` and `sq skills list` report skill-pack status for the target the user actually runs.

## Technical Scope

**Included**

- `sq skills install | uninstall | list` gain `--ide {claude|agents|codex|openai}` (default `claude`) and `--local`. `--commands-dir` stays as the explicit override that beats both.
- The pack-format rule for agents content, its validation, and the move of the bundled `analysis` pack's agents skills to match it.
- Per-target skill-pack receipts that still read every receipt written today.
- A per-target pack layout table shared by install, `skills list`, and `check_skill_packs`.
- Receipt-driven file removal extracted from `uninstall_commands` so `skills uninstall` handles nested skill directories the same way.
- Doctor skill-pack rows per target.
- The Codex approval rule in README and QUICKSTART, the command enumeration behind it, and a failure hint in the `sq-review`, `sq-run`, and `sq-pr` agent skills.
- `sq model list` → `sq models list` in both command trees.

**Excluded**

- Automatic conversion of Claude-authored packs to skill directories (D2).
- A doctor check for the Codex rule (D11).
- Writing the rule file for the user (`sq setup` prints and guides; it does not edit another tool's config).
- #126 (Codex polling long commands), `copilot`/`cursor` targets, `sq setup` installing skill packs (it does not today).
- Pack-name collisions with squadron's own receipt names or skill names — pre-existing on the Claude path and unchanged here.

## Dependencies

### Prerequisites

- Slice 925 (complete): `squadron.skills.targets` — `CommandTarget`, `normalize_target`, `DELIVERIES`, `receipt_name`, `write_skill_dirs`, `bundled_skill_names`; doctor's `_command_targets_to_check`.
- Codex CLI ≥ 0.146 on the verification machine, for `codex sandbox` and `codex execpolicy check`.

### Interfaces Required

- Codex execpolicy rules: every `*.rules` file under `$CODEX_HOME/rules/` (default `~/.codex/rules/`) is loaded; project layers load `<project>/.codex/rules/`. `prefix_rule(pattern, decision, justification, match, not_match)` — list elements in `pattern` are alternatives; `match`/`not_match` are validated at load time. A matching `allow` rule runs the command **outside the sandbox without a prompt**. Commands using redirection, env-var prefixes, or globs are never evaluated against rules. (Source: `codex-rs/execpolicy/README.md`, `codex-rs/core/src/exec_policy.rs`, the `on_request` approval-policy prompt.)
- Codex skill requirements from 925 D2–D4: `SKILL.md` with non-empty `name` and `description`, `name` equal to its directory, lowercase `a-z0-9-`.

## Architecture

### Component Structure

| Component | Change |
|---|---|
| `skills/targets.py` | `TargetDelivery.receipt_base` → `receipt_suffix` (`""` / `"-agents"`); `receipt_name(base, target, *, local)` becomes generic; AGENTS `bundle_subdirs` gains `analysis/agents`; `bundled_skill_names` reads every AGENTS bundle subdir. |
| `skills/pack_layouts.py` (new) | `PackLayout` and `PACK_LAYOUTS: dict[CommandTarget, PackLayout]`, exhaustive by assertion like `DELIVERIES`. Holds the per-target install writer, the agents validation, and `installed_path(entry, root)`. |
| `skills/installer.py` | `install_pack(..., target)` resolves the source as today, then dispatches to `PACK_LAYOUTS[target].install`. The Claude prefix/dispatch writers move into the Claude layout unchanged. |
| `skills/receipts.py` | Gains `remove_receipt_files(receipt) -> int`, extracted from `uninstall_commands` (containment check, deepest-first empty-dir removal, never removes the destination itself). |
| `cli/commands/install.py` | `uninstall_commands` calls `remove_receipt_files`; passes `"squadron-commands"` to `receipt_name`. No behavior change. |
| `cli/commands/skills.py` | `--ide`/`--local` on all three commands; root from `DELIVERIES[target].resolve_root(local=)`; status from `installed_path`; uninstall via `remove_receipt_files`. |
| `cli/commands/doctor_checks.py` | `check_skill_packs` loops `_command_targets_to_check(None)` and uses `installed_path`. |
| `commands/analysis/agents/` | `analysis-understand/`, `analysis-tech-debt-audit/` moved here from `commands/agents/`. |
| `commands/agents/sq-{review,run,pr}/SKILL.md` | Sandbox-rejection hint (D12). |
| `README.md`, `docs/QUICKSTART.md` | Approval rule (D9, D10). |

### Data Flow

**Install, agents target**

```
sq skills install mypack --ide codex [--local]
  normalize_target("codex") → AGENTS
  root = DELIVERIES[AGENTS].resolve_root(local)            ~/.agents/skills | ./.agents/skills
  (--commands-dir overrides root; --local then ignored, with the same warning install-commands prints)
  source = resolve_source(entry) | clone_github(entry)      unchanged
  PACK_LAYOUTS[AGENTS].install(pack, entry, source, root)
    agents_dir = source / "agents"        missing → SkillSourceError, nothing written
    validate every skill dir (D3)         any violation → SkillSourceError listing all, nothing written
    write_skill_dirs(agents_dir, root)    → files_written, relative to root
  write receipt  receipt_name("mypack", AGENTS, local) = "mypack-agents[-local]"
```

**Install, Claude target** — identical to today, including the receipt name `mypack` (machine) and the destination `~/.claude/commands/<prefix>` or `.../sq`.

**Uninstall** — receipt looked up by the same `receipt_name`; `remove_receipt_files(receipt)` deletes exactly the recorded files and prunes skill directories left empty; for a Claude prefix pack the now-empty prefix directory is still removed, as today.

**Status (`skills list`, doctor)** — `PACK_LAYOUTS[target].installed_path(entry, root)` returns the path that proves an install, or `None`:

| Surface | Claude | Agents |
|---|---|---|
| `prefix = "p"` | `root/p/` non-empty | first `root/p-*/SKILL.md` |
| `dispatch_file = "d"` | `root/sq/d.md` | `root/sq-d/SKILL.md` |

### State Management

The only persisted state is install receipts under `~/.config/squadron/receipts/`. Schema unchanged; only the file name varies by target and scope (D5).

## Technical Decisions

### Technology Choices

**D1 — Same flags, same meaning as `install-commands`.** `--ide` goes through `normalize_target`, so `codex`/`openai`/`agents` are one target and `copilot` fails with the accepted-spellings message. `--local` uses `TargetDelivery.resolve_root`. `--commands-dir` keeps its name (renaming it to `--target` would break existing scripts for no user gain) and plays `--target`'s role: it wins over `--local`, which is reported as ignored. With no flags, every path, receipt name, and message is unchanged.

**D2 — Codex content is declared, never converted.** A pack supports the agents target by shipping an `agents/` directory in its source root, holding one skill directory per skill — the layout squadron's own bundle already uses. An agents install of a pack without it exits 1: `Pack 'mypack' has no agents/ directory at <source>; it ships no Codex content. Install it for Claude with --ide claude.` Rejected: scanning for `$ARGUMENTS` and auto-converting packs that lack it. Conversion means squadron owns a frontmatter rewriter (`name` must become the directory name, `disable-model-invocation` must become `agents/openai.yaml`, per 925 D7) for content it did not write, and a clean scan proves nothing — a Claude command can depend on argument substitution without spelling `$ARGUMENTS` (925 D3 found the dependency is in the prose). A pack author who has not written Codex content has not tested it under Codex either.

**D3 — Validate names and frontmatter before writing anything.** The agents root is shared with every other skill source, so a skill's directory name is the only thing that ties it to its pack for `list`, doctor, and collision reasoning. Rules:

- `prefix` pack: every directory under `agents/` is named `<prefix>-<something>`, matching `^[a-z0-9-]+$`.
- `dispatch_file` pack: `agents/` holds exactly `sq-<dispatch_file>/` (the Codex counterpart of `/sq:<dispatch_file>`).
- Each `SKILL.md` has YAML frontmatter with `name` equal to its directory and a non-empty `description`.
- `agents/` with no skill directories is an error, not an empty install.

All violations are collected and reported together; nothing is written unless all pass.

**D4 — The bundled `analysis` pack follows the same rule; no bundled special case.** Its agents skills move from `commands/agents/analysis-*` to `commands/analysis/agents/analysis-*`, so `resolve_source` for `bundled` returns `commands/analysis` and D2 applies unchanged. For `install-commands`, the AGENTS delivery's `bundle_subdirs` becomes `("agents", "analysis/agents")`; `write_skill_dirs` writes skill directories at the root either way, so installed paths and existing receipts are identical. `bundled_skill_names` iterates the AGENTS `bundle_subdirs` instead of hardcoding `agents`. Nothing else reads `commands/analysis/` recursively: the Claude writers and `metrology/audit.py` glob `*.md` at the top level, so the new subdirectory is invisible to them. Rejected: a resolver branch that points bundled packs at `commands/agents/` and filters by prefix — it would need prefix filtering there and strict validation everywhere else, two behaviors for one rule.

**D5 — Receipt names: base + target suffix + scope suffix.** `receipt_name(base, target, *, local) = base + DELIVERIES[target].receipt_suffix + ("-local" if local else "")`, with suffixes `""` (Claude) and `"-agents"`. `install-commands` passes `"squadron-commands"`, producing exactly today's four names. A skill pack passes its pack name, so a Claude machine install is still `<pack>.toml` and every receipt written today still reads. No schema change.

**D6 — `PACK_LAYOUTS` is the one place that knows where a pack lands.** `skills list` and `check_skill_packs` each re-derive install paths today (duplicated logic); both call `installed_path` instead. A new target is a new `PackLayout` entry, not a new branch in three callers.

**D7 — One removal routine.** The receipt-driven loop in `uninstall_commands` (containment check against the destination, deepest-first pruning of emptied directories, never `rmtree`) moves to `skills/receipts.py` as `remove_receipt_files`. `skills uninstall` needs exactly that for nested skill directories; its current flat `unlink` loop would leave empty `mypack-x/agents/` directories behind.

**D8 — Doctor reports skill packs per target, like commands.** `check_skill_packs` iterates `_command_targets_to_check(None)`: Claude rows always, agents rows only where the Codex CLI is on PATH. Claude row names and hints are unchanged. Agents rows are named `<pack> (codex)` with hint `sq skills install <pack> --ide codex`, matching the `codex skills` row's wording. A pack with no agents content reports `WARN — pack ships no Codex content`, not "not installed", and no install hint, since the hint would fail. Skill-pack rows are not keys in any setup table, so the name format is free to choose.

**D9 — The rule lives in its own file, `~/.codex/rules/squadron.rules`.** Codex loads every `*.rules` file in that directory and appends its own "always allow" approvals to `default.rules` (the live machine's `default.rules` is full of them). A squadron-owned file keeps the rule findable, replaceable on upgrade, and out of a file Codex rewrites. The documented rule is a single `prefix_rule` with alternatives, a `justification`, and `match` examples — Codex validates `match` at load time, so a typo fails loudly instead of silently never matching:

```starlark
prefix_rule(
    pattern = ["sq", [<subcommands from D10>]],
    decision = "allow",
    justification = "squadron commands that call a model provider or GitHub",
    match = [<one example per subcommand>],
)
```

The docs state plainly what it authorizes: matching commands run **outside Codex's sandbox with no prompt** — network and unrestricted filesystem, not just network. They name `decision = "prompt"` as the ask-every-time alternative, `<project>/.codex/rules/` for a per-project rule, and that a command with a redirect or `VAR=` prefix never matches a rule. README's existing `default.rules` snippet is replaced, not duplicated.

**D10 — The subcommand list comes from a sandbox probe, not from reading code.** Each top-level `sq` command is run under `codex sandbox -- sq <cmd> …` from a terminal and classified by whether it fails on network or filesystem denial. Evidence gathered during design:

| Command | Sandboxed result | Rule |
|---|---|---|
| `sq --version`, `sq models list`, `sq auth status` | ran | no |
| `sq pr show 1` | `HostUnreachableError: … api.github.com` | yes |
| `sq review …`, `sq run …`, `sq metrology …` | reach a provider by construction | yes — confirm by probe |
| `sq skills install` (github source) | runs `git clone` | yes — confirm by probe |
| `sq spawn`, `task`, `message`, `list`, `history`, `shutdown` | talk to the daemon over a Unix socket; `sq list` reported "Daemon is not running" | probe with `sq serve` running in a terminal |
| `sq auth login` | unprobed | probe |

The probe results table goes into the DEVLOG entry for the implementation; the rule's alternatives are exactly the "yes" rows. If the daemon-client commands need the rule, README's "`$sq-spawn` … fine to invoke directly" sentence is corrected in the same edit.

**D11 — No `sq doctor` check for the rule.** A missing squadron rule is not a broken environment: the user may approve per call, run Codex with approvals off or full access, put the rule in a project `.codex/rules/`, or have it in a system or managed-requirements layer doctor cannot see. A check reading `~/.codex/rules` would WARN on correct setups. Evaluating the rule properly means parsing Starlark or shelling out to `codex execpolicy check`, which Codex marks preview ("may have breaking changes"). The cost is coupling to another tool's config; the benefit is covered better by D12.

**D12 — Put the hint where the failure happens.** The misleading message is the Codex model's paraphrase of a sandbox rejection. `commands/agents/sq-review`, `sq-run`, and `sq-pr` each gain a short section: if Codex rejects or blocks the `sq` command for sandbox or approval reasons, say that it is Codex's sandbox, not the provider or squadron config, and point at the README section by heading. Agents tree only — the Claude files never see this failure.

### Patterns and Conventions

- Target-keyed tables with an exhaustiveness assertion (`DELIVERIES`, now `PACK_LAYOUTS`); no `if target == …` branches in callers.
- Failures are `SkillSourceError` → exit 1 with the path and the fix in the message; the Claude path's messages are untouched.
- Receipts remain the only authority for what squadron owns in a shared directory (#65).

## Implementation Details

### Migration Plan

- **Moved:** `commands/agents/analysis-understand/` and `commands/agents/analysis-tech-debt-audit/` → `commands/analysis/agents/` (`git mv`). Consumers: `DELIVERIES[AGENTS].bundle_subdirs`, `bundled_skill_names`, and the fixtures in `tests/cli/test_install_commands.py` and `tests/skills/test_targets.py`. Installed destinations do not change, so no user-side migration.
- **Receipts:** no migration. Existing `<pack>.toml` and `squadron-commands*.toml` names are exactly what D5 produces for the same inputs.
- **Behavior preserved:** for no-flag invocations of `skills install/uninstall/list`, `install-commands`, and `uninstall-commands`, the files written, receipt contents, and printed output are unchanged. Existing tests for those commands pass without edits other than the moved fixture paths.

### API Contracts

```
sq skills install   PACK [--ide T] [--local] [--commands-dir DIR] [--receipts-dir DIR]
sq skills uninstall PACK [--ide T] [--local] [--receipts-dir DIR] [--commands-dir DIR]
sq skills list           [--ide T] [--local] [--commands-dir DIR]
```

`uninstall` takes the destination from the receipt, as `uninstall-commands` does (925 D6); `--commands-dir` there is a check that must match the receipt's destination or the command exits 1 having removed nothing.

Pack source layout (documented in the skills section of README):

```
<pack source>/
  *.md                       Claude commands (prefix packs) or <dispatch_file>.md
  agents/                    optional; required for --ide codex
    <prefix>-<name>/SKILL.md     prefix packs
    sq-<dispatch_file>/SKILL.md  dispatch_file packs
```

## Integration Points

### Provides to Other Slices

- The pack-format rule for Codex content, which any future pack source follows.
- `PACK_LAYOUTS` and `remove_receipt_files` for any future target or installer.

### Consumes from Other Slices

- 925's target vocabulary, deliveries, `write_skill_dirs`, and doctor target selection, unchanged in meaning.

## Success Criteria

### Functional Requirements

1. `sq skills install analysis --ide codex` writes `~/.agents/skills/analysis-understand/` and `analysis-tech-debt-audit/` and a receipt `analysis-agents.toml`; `--local` writes under `./.agents/skills/` with `analysis-agents-local.toml`.
2. `sq skills uninstall analysis --ide codex` removes exactly those files and the emptied skill directories, never `~/.agents/skills` itself or anything not in the receipt.
3. An agents install of a pack with no `agents/` directory, or with a misnamed skill directory or bad frontmatter, exits 1 with every problem listed and writes nothing.
4. `sq skills list --ide codex` shows installed status for agents; `sq skills list` is unchanged.
5. With the Codex CLI on PATH, `sq doctor` shows `<pack> (codex)` rows; without it, the Skill Packs section is unchanged.
6. No-flag `sq skills *`, `sq install-commands`, and `sq uninstall-commands` behave exactly as before; a pre-existing `analysis.toml` receipt still uninstalls.
7. `sq install-commands --ide codex` installs the same skill set to the same paths as before the move.
8. README and QUICKSTART Codex sections carry the D9 rule with the D10 subcommand list and state what it authorizes; `codex execpolicy check --rules <file> sq <cmd> …` returns `allow` for each listed subcommand and no decision for `sq models list`.
9. `sq-review`, `sq-run`, `sq-pr` agent skills carry the sandbox-rejection hint; both `review` command files say `sq models list`.

### Technical Requirements

- Tests: D3 validation (each rule, all-violations-reported, nothing written on failure); receipt-name table for both bases × targets × scopes; `installed_path` table (surface × target); `remove_receipt_files` shared behavior (existing uninstall-commands tests cover it by moving with it); doctor rows with and without Codex; old-receipt read.
- All tests run against a patched `HOME` (#47); none touch the real `~/.agents` or `~/.codex`.
- `ruff format`, `ruff check`, `pyright` clean.

### Verification Walkthrough

Run from the squadron repo root with a disposable home so nothing real is touched:

```bash
export HOME=$(mktemp -d); cd /path/to/squadron

# 1. Codex install of the bundled pack
sq skills install analysis --ide codex
ls ~/.agents/skills                    # analysis-tech-debt-audit  analysis-understand
ls ~/.config/squadron/receipts         # analysis-agents.toml
sq skills list --ide codex             # analysis … Installed

# 2. Claude path unchanged
sq skills install analysis
ls ~/.claude/commands/analysis         # tech-debt-audit.md  understand.md
ls ~/.config/squadron/receipts         # analysis.toml  analysis-agents.toml

# 3. A pack with no Codex content refuses loudly
mkdir -p /tmp/p928 && printf -- '---\ndescription: x\n---\nuse $ARGUMENTS\n' > /tmp/p928/hello.md
mkdir -p ~/.config/squadron && printf '[packs.demo]\nsource = "/tmp/p928"\nprefix = "demo"\n' > ~/.config/squadron/skills.toml
sq skills install demo --ide codex     # exit 1: "Pack 'demo' has no agents/ directory at /tmp/p928 …"
ls ~/.agents/skills | grep demo        # nothing

# 4. Misnamed skill is rejected, all problems listed
mkdir -p /tmp/p928/agents/hello && printf -- '---\nname: hello\ndescription: x\n---\n' > /tmp/p928/agents/hello/SKILL.md
sq skills install demo --ide codex     # exit 1: "agents/hello must be named demo-<name>"
mv /tmp/p928/agents/hello /tmp/p928/agents/demo-hello
sed -i '' 's/name: hello/name: demo-hello/' /tmp/p928/agents/demo-hello/SKILL.md
sq skills install demo --ide codex     # installs ~/.agents/skills/demo-hello/SKILL.md

# 5. Uninstall removes only what was written
touch ~/.agents/skills/mine.txt
sq skills uninstall demo --ide codex
sq skills uninstall analysis --ide codex
ls ~/.agents/skills                    # mine.txt only

# 6. install-commands unaffected by the move
sq install-commands --ide codex && ls ~/.agents/skills | grep analysis   # both analysis-* present

# 7. Doctor rows (Codex CLI on PATH)
sq doctor                              # Skill Packs: analysis, analysis (codex), demo, demo (codex) — all four rows present
rm -rf /tmp/p928/agents && sq doctor   # demo (codex): WARN "pack ships no Codex content", no install hint
```

Codex rule, on a real machine:

```bash
# 8. Before the rule: sandboxed provider call fails
codex sandbox -- sq pr show 1          # HostUnreachableError

# 9. Add the rule exactly as README shows, into ~/.codex/rules/squadron.rules, then:
codex execpolicy check --rules ~/.codex/rules/squadron.rules sq review code 928   # "decision":"allow"
codex execpolicy check --rules ~/.codex/rules/squadron.rules sq models list       # no matchedRules

# 10. In a Codex session: $sq-review code 928 --model <alias>
#     runs without an approval prompt and writes the review file.
# 11. Remove the rule, repeat 10: Codex blocks it, and the skill's reply names
#     Codex's sandbox and the README section rather than the provider.
```

## Implementation Notes

### Development Approach

1. D5 receipt generalization and D7 removal extraction — pure refactor; existing tests stay green.
2. D4 move plus `bundle_subdirs` / `bundled_skill_names`; confirm criterion 7.
3. `PACK_LAYOUTS` with the Claude layout lifted from `installer.py`; then the agents layout and D3 validation.
4. CLI flags on the skills sub-app; then `list` and doctor via `installed_path`.
5. D10 probe from a terminal (start `sq serve` first for the daemon rows); record results.
6. Docs (D9), skill hints (D12), `sq models list` fix.
7. Live Codex check: walkthrough steps 8–11.

Effort: 3/5 (up from the plan's 2/5 — the per-target pack layout and shared removal are more than plumbing).

### Special Considerations

- The rule grants unsandboxed execution. The docs must say so in the same paragraph as the snippet, not in a footnote.
- `codex sandbox` needs to run from a real terminal, not from inside a Codex session, or the probe measures the outer sandbox.
