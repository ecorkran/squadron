---
docType: architecture
project: squadron
initiative: 340
dateCreated: 20260625
dateUpdated: 20260625
status: in_progress
archIndex: 340
component: skill-pack-infrastructure
---

# Architecture: Skill Pack Infrastructure

## Overview

Squadron's first-party slash commands are bundled in the wheel and installed via `sq install-commands`. This works well for commands owned by squadron, but the ecosystem of useful Claude Code skills is larger and growing — particularly for analysis of existing codebases. There is no mechanism today for users to install external skill sets alongside squadron's commands without manual file management.

**Scope:** A thin, opt-in extension layer that treats external Claude Code skills as installable packs. A pack is a named collection of slash command markdown files with a declared source (local path or git ref). Squadron becomes the package manager for those files; Claude Code's existing slash command system handles invocation unchanged.

**Motivation:** Squadron is used increasingly for analysis of non-greenfield codebases. Skills like `tech-debt-analyze` and `understand-anything` provide value first-party commands don't cover. Without a pack mechanism, users manage these manually, they drift out of sync, and there is no shared vocabulary for "the analysis toolkit." The analysis pack is the first customer; the mechanism is general.

## Design Goals

- **Opt-in, zero default bloat** — nothing extra ships with squadron; users pull packs when they need them.
- **Minimal mechanism** — file copy + a TOML manifest. No dynamic discovery, no registry server, no plugin API.
- **External source support** — manifest entries accept local paths or git refs so forked and community packs work without a squadron-owned registry.
- **First-party parity** — installed pack commands are indistinguishable to Claude Code from first-party `sq` commands; same markdown file format, same invocation model.
- **Discoverable command surface** — pack commands do not pollute the `/sq:*` namespace; each pack gets a distinct prefix so `sq` autocomplete stays clean.

## Architectural Principles

- **File copy is the delivery primitive** — `sq skills install` writes markdown files to `~/.claude/commands/<prefix>/`. No runtime indirection; no loader; no daemon involvement. The installed file IS the capability.
- **Manifest is declarative, not executable** — `skills.toml` names packs and their sources. It does not describe installation logic. Squadron resolves and copies; the manifest does not run.
- **Prefix per pack, not per skill** — each pack owns a command prefix (e.g. `analysis`), installing skills as `/analysis:tech-debt`, `/analysis:understand`. This keeps `/sq:*` first-party only and makes pack membership visible at the command surface without a routing layer.
- **Dispatch model adopted** — spike (slice 340) confirmed that `/sq:analysis <skill>` dispatch via a single router file is reliable: arguments pass through intact, routing is correct, and UX is equivalent to direct invocation. The manifest format (slice 341) will support a `dispatch_file` option alongside `prefix`, allowing packs to choose either surface.
- **Squadron owns the analysis pack** — the bundled `analysis` pack lives in the squadron repo (like `commands/sq/`), sourced from the same wheel. Third-party packs are supported by the manifest format but the analysis pack is the reference implementation.

## Current State

- `sq install-commands` copies `commands/sq/*.md` from the wheel into `~/.claude/commands/sq/`. This is the only install path.
- No manifest format exists for external skill sources.
- No `sq skills` subcommand exists.
- The forked `tech-debt-analyze` skill is used manually, outside squadron's install lifecycle.
- All installed commands share the `/sq:*` prefix; the namespace is flat and will become cluttered as external skills are added.

## Envisioned State

A `skills.toml` file (user-level at `~/.config/squadron/skills.toml`, optionally overridden per-project) declares named packs:

```toml
[packs.analysis]
source = "bundled"          # ships with squadron wheel
prefix = "analysis"

[packs.my-team-skills]
source = "github:org/repo"  # fetched on install
prefix = "team"
```

`sq skills install analysis` resolves the source, copies markdown files to `~/.claude/commands/analysis/`, and reports what was installed. `sq skills list` shows all known packs with installed/available status. The `/analysis:*` commands are immediately available to Claude Code after install.

The analysis pack (bundled) includes the forked `tech-debt-analyze` skill and any other analysis-oriented skills added over time. Installing it is a one-command on-ramp for existing-codebase work.

## Technical Considerations

- **Command surface: dispatch model adopted** — spike (slice 340) verified that a markdown dispatcher passes arguments reliably through Claude Code. The dispatch model (`/sq:analysis tech-debt`) is adopted; the manifest format will support `dispatch_file` as an alternative to `prefix`. Both models remain available; pack authors choose at manifest time.
- **Git source fetch scope** — supporting `github:org/repo` sources requires fetching remote content at install time. Scope should be minimal: shallow clone or single-file download, no version pinning in v1. Pin/update semantics deferred.
- **Bundled pack delivery** — the analysis pack ships as `commands/analysis/` in the wheel, parallel to `commands/sq/`. `importlib.resources` already handles this path; no new packaging mechanism needed.
- **Per-project vs. user-level manifest** — a project-local `skills.toml` enables project-specific pack sets (e.g. a security pack only for security-audit projects). User-level is the default; project-level overrides or extends. Merge semantics need a decision at slice design time.

## Anticipated Slices

- **Spike: dispatch vs. prefix** — 20-minute prototype of `/sq:analysis <skill>` dispatch to determine reliability. Closes the open command-surface question before manifest design commits.
- **Manifest format + `sq skills install/list`** — TOML schema, resolver (bundled / local path / git ref), file-copy installer, list command with status output.
- **Analysis pack (bundled)** — package `tech-debt-analyze` and initial analysis skills into `commands/analysis/`; wire into wheel; document the pack.
- **`sq skills` CLI surface** — `install`, `list`, `uninstall` subcommands; integration with `sq doctor` to report installed packs.

## Related Work

- `sq install-commands` / `sq uninstall-commands` — existing file-copy install mechanism this initiative extends (`src/squadron/cli/commands/install.py`)
- Initiative 320 (Judge Calibration & Quality Metrology) — primary consumer of the analysis pack; tech-debt-audit skill is 320's code-quality oracle
- Initiative 100 (Orchestration) — CLI command registration and `importlib.resources` bundling patterns to follow
