---
docType: reference
project: squadron
dateCreated: 20261020
dateUpdated: 20261020
status: not_started
dependsOn: [001-initiative-plan.squadron.md]
---

# Capability Probe Contract (`sq probe --json`)

A cross-repo contract between squadron initiative 440 and context-forge initiative 260. Context Forge
runs the probe during brownfield onboarding to decide whether to take squadron's path, and tests these
field names. Agreed with the CF session on 20261020. The probe is built in slice 366.

Changing a field name, a field's meaning, or a `surfaces` value without following the versioning
rules below breaks Context Forge.

## Command

`sq probe --json` prints one JSON object on stdout.

- Exit 0 whenever the probe can report, including when everything reports absent.
- Non-zero only when the probe itself breaks. CF treats non-zero, unreadable output, or an unknown
  `probe_version` as "squadron unavailable" and says so to the user.

## Shape (probe_version 1)

```json
{
  "probe_version": 1,
  "sq_version": "string",
  "surfaces": {
    "claude-code": {"analysis_skill_installed": true, "entry": "/sq:analysis understand", "concept": "/sq:analysis understand concept", "understand_plugin_installed": true, "graph_build": "/understand"},
    "codex": {"analysis_skill_installed": true, "entry": "analysis-understand", "concept": "analysis-understand concept", "understand_plugin_installed": false, "graph_build": "understand"}
  },
  "graph": {"present": true, "path": "string or null", "commit": "string or null", "commits_behind": 0},
  "baseline": {"available": false}
}
```

| Field | Type | Meaning |
|---|---|---|
| `probe_version` | int | Version of this contract. |
| `sq_version` | string | Installed squadron version. |
| `surfaces` | object | One entry per agent surface where squadron's brownfield path can run, keyed by the values below. Every supported surface is always present. The agent finds its own surface; on a surface not listed, CF takes its own path. |
| `surfaces.<s>.analysis_skill_installed` | bool | Squadron's analysis pack, including the understand skill, is installed for that surface. |
| `surfaces.<s>.entry` | string | How an agent on that surface starts squadron's path: a slash command on `claude-code`, the skill name on `codex`. |
| `surfaces.<s>.concept` | string | How an agent on that surface runs squadron's concept step (slice 363), which writes `000-concept.{project}.md`. It is the same skill as `entry` with the `concept` flow argument; `entry` alone runs only the comprehension analysis and never writes a concept. |
| `surfaces.<s>.understand_plugin_installed` | bool | The `understand-anything` plugin is installed for that surface: its plugin on `claude-code`, its `understand` skill in `~/.agents/skills/` on `codex`. |
| `surfaces.<s>.graph_build` | string | How an agent on that surface builds or refreshes the graph with `understand-anything`: `/understand` on `claude-code`, the skill name `understand` on `codex`. `entry` never builds the graph; it only reads one, so a missing or stale graph is built with this first. |
| `graph.present` | bool | `.understand-anything/knowledge-graph.json` exists in the project. |
| `graph.path` | string or null | Path to the graph file. |
| `graph.commit` | string or null | The commit the graph was built from. |
| `graph.commits_behind` | int or null | Commits between `graph.commit` and HEAD. 0 means current. |
| `baseline.available` | bool | 400's adoption baseline can run. False until 400 ships. |

**Null means unknown.** A field is null when the probe cannot determine it, for example
`commits_behind` outside a git repository. It never carries an invented value.

## `surfaces` values

| Value | Meaning |
|---|---|
| `claude-code` | Claude Code. Squadron's analysis pack installs as commands under `~/.claude/commands/` (`--ide claude`); `understand-anything` installs from its Claude Code plugin marketplace. Run end to end on squadron (analyses 943–945). |
| `codex` | Codex and other runtimes that read `~/.agents/skills/` (`--ide agents`, aliases `codex`, `openai`). Squadron's analysis pack installs there as `analysis-understand`; `understand-anything` documents Codex support (`install.sh codex`, same directory). Not yet run end to end. |

Not supported: Copilot and Cursor, because squadron has no install target for them (`CommandTarget` omits both), even though `understand-anything` supports them. There is no plain CLI path; the analysis skills run inside an agent.

CF tests field names, not surface values. A new surface is additive (see Versioning).

## Versioning

**Revision note.** v1 was revised before any probe existed (998d8944: `surfaces` became an
object and absorbed `analysis_skill` and `understand_plugin`; then `graph_build` and `concept`
were added). No
output in the earlier shapes was ever produced, so v1 means the shape in this document.

- Adding a new `surfaces` value or a new optional field is additive. It keeps `probe_version` and is
  recorded in this document before it ships.
- Renaming or removing a field, changing a field's type or meaning, or changing exit-code semantics
  bumps `probe_version`.
- If staleness ever means something other than "behind HEAD", it gets its own field. `commits_behind`
  does not change meaning.

## Shipping order

The `claude-code` values route through `/sq:analysis`, which reaches the understand skill only once
slice 366 lands; today the installed command is `/analysis:understand`. The probe ships in slice
366 together with that routing (folded in 20261020), so it never reports an entry that does not
route.

## Not in the probe

- Presence of planning artifacts such as a concept: CF's detection owns that.
- Whether running `/understand` needs the PM's go: open with CF's PM. Nothing here depends on it.
