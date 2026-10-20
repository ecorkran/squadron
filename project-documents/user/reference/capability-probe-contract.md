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
field names. Agreed with the CF session on 20261020. The probe itself is not built yet.

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
  "surfaces": ["claude-code"],
  "analysis_skill": {"installed": true, "entry": "/sq:analysis understand"},
  "understand_plugin": {"installed": true},
  "graph": {"present": true, "path": "string or null", "commit": "string or null", "commits_behind": 0},
  "baseline": {"available": false}
}
```

| Field | Type | Meaning |
|---|---|---|
| `probe_version` | int | Version of this contract. |
| `sq_version` | string | Installed squadron version. |
| `surfaces` | list of string | Agent surfaces where squadron's brownfield path runs. CF takes its own path on any surface not listed. |
| `analysis_skill.installed` | bool | The analysis skill pack, including the understand skill, is installed. |
| `analysis_skill.entry` | string | The command an agent runs to start squadron's path. |
| `understand_plugin.installed` | bool | The `understand-anything` plugin is installed. |
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
| `claude-code` | Claude Code. The analysis skills install as Claude Code commands, and `understand-anything` is a Claude Code plugin. |

This list is closed. CF compares against it as a constant.

## Versioning

- Adding a new `surfaces` value or a new optional field is additive. It keeps `probe_version` and is
  recorded in this document before it ships.
- Renaming or removing a field, changing a field's type or meaning, or changing exit-code semantics
  bumps `probe_version`.
- If staleness ever means something other than "behind HEAD", it gets its own field. `commits_behind`
  does not change meaning.

## Not in the probe

- Presence of planning artifacts such as a concept: CF's detection owns that.
- Whether running `/understand` needs the PM's go: open with CF's PM. Nothing here depends on it.
