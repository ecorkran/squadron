---
name: understand
description: Consumes an existing understand-anything knowledge graph and writes squadron planning documents from it. Reads the graph the plugin already produced — it does not analyze the codebase itself and does not run the plugin. Use when the user asks for a codebase comprehension analysis derived from an existing knowledge graph. Does not auto-invoke.
disable-model-invocation: true
---

# Understand

A Claude Code skill that reads an existing `understand-anything` knowledge graph and writes squadron
planning documents from it.

This skill is a **consumer**. The graph is produced by the upstream `understand-anything` marketplace
plugin's own `/understand` command; this skill never runs, wraps, forks, or installs that plugin. If
no graph exists, this skill stops and says so rather than analyzing the codebase itself.

When invoked via `/understand`, follow the protocol below. Everything from here through the `---`
divider is the protocol Claude executes. The section after the divider is documentation for humans
installing or maintaining this skill.

---

## Preflight: Graph Contract

Run this entire section before writing anything. Every step below either succeeds, stops with a
named reason, or records an explicit skip. No step is allowed to fail quietly.

### Graph location and read discipline

Resolve the graph root:

1. Run `git rev-parse --show-toplevel`. On success, that is the repository root.
2. If `git` is unavailable or the directory is not a repository, use the current working directory
   as the root. This is a location fallback only — it does not suppress any check below.
3. The graph root is `<root>/.understand-anything/`. The graph file is
   `<root>/.understand-anything/knowledge-graph.json`; the metadata file is `meta.json` beside it.

**`jq` is required.** Check it with `command -v jq`. If it is absent, stop and say that this skill
requires `jq` to read the graph safely. **Do not fall back to reading the graph file directly** — the
graph routinely exceeds a megabyte, and loading it whole defeats the purpose of every scoped read
below.

**Every read is a field-scoped `jq` selection.** The graph is never loaded whole into context, never
`cat`-ed, and never read with the Read tool. Only these selections are needed:

| Purpose | Selection |
|---|---|
| Key presence | `jq -r 'keys[]'` |
| Array lengths | `jq -r '"\(.nodes\|length) \(.edges\|length) \(.layers\|length) \(.tour\|length)"'` |
| Graph version | `jq -r '.version'` |
| Layers | `jq -r '.layers[] \| {id, name, description, count: (.nodeIds\|length)}'` |
| File-level nodes | `jq -r '.nodes[] \| select(.type == "file") \| {id, filePath, summary, complexity}'` |
| Tour steps | `jq -r '.tour[] \| {order, title, nodeIds}'` |
| Edge aggregates | `jq -r '[.edges[].type] \| group_by(.) \| map({type: .[0], n: length})'` |

Select **only** the fields named in that table. A node carries `name`, `tags`, `lineRange`, and
`languageNotes` as well; none of them are read at this depth.

**Function- and class-level nodes are never read.** Filter with `select(.type == "file")` — never
read a node whose `type` is `function` or `class`. They are the bulk of the graph and none of the
sections this skill writes derive from them.

**Not consumed at this depth** (deferred to slice 362, recorded here so the next author sees the
deferral rather than rediscovering it):

- `config.json` and `.understandignore` in the graph root — they describe how the upstream plugin was
  configured and what it excluded. Reading them would let a generated document state its own
  coverage limits, which is a real improvement and out of scope here.
- `meta.json`'s `analyzedFiles` count — a coverage signal, same reasoning.
- Node `type` values beyond `file`, `function`, and `class` (this graph also carries `pipeline` and
  `config` nodes).

### Validation: absent, unparseable, malformed

Run these three checks in order and stop at the first failure. The three messages must be textually
distinct — a reader must be able to tell which failure occurred without inspecting anything else.

**1. Absent** — `knowledge-graph.json` does not exist at the graph root.

Stop. Report the path that was checked, and say that this skill consumes a knowledge graph produced
by the `understand-anything` plugin's own `/understand` command, which must be run first.

State only that the graph is missing. **Do not speculate about whether the plugin is installed**,
and do not offer to install it — detecting and reporting plugin availability is slice 366's scope,
and a guess here would be wrong as often as right.

**2. Unparseable** — `jq empty <graph>` exits non-zero.

Stop. Name the file and report that it is not valid JSON, quoting `jq`'s own error. Say the graph is
likely truncated or partially written, and that re-running the plugin's `/understand` will rewrite
it. This message must not mention missing keys — the file never parsed, so no key was inspected.

**3. Malformed** — the file parses but its shape is wrong.

Required top-level keys, each with its required type:

| Key | Type | Empty is |
|---|---|---|
| `nodes` | array | **reject** |
| `edges` | array | **reject** |
| `layers` | array | **reject** |
| `tour` | array | warn, proceed |
| `version` | string | reject if missing |
| `project` | object | reject if missing |

Stop if any key is missing, is the wrong type, or — for `nodes`, `edges`, `layers` — is present but
empty. **Name every offending key in one message**, not just the first one found, so a single run
tells the reader everything that is wrong.

Report graph identity alongside the failure: `version` from the graph, and `gitCommitHash` and
`lastAnalyzedAt` from `meta.json` when they are readable. If `meta.json` is unreadable, say so rather
than omitting the line — identity is what lets a reader tell a stale graph from a broken one.

**The `tour` asymmetry.** An empty `tour` degrades exactly one section (suggested reading order), so
it warns and proceeds, and the affected section carries a gap marker. Empty `nodes`, `edges`, or
`layers` means nothing useful can be written, so it rejects. This asymmetry is deliberate: the test
is whether the missing field costs one section or the whole document.

**Governing rule.** If the upstream plugin renames or restructures a field, that must surface here as
failure 3 — a loud, named rejection. It must **never** produce a document that is silently thinner
because a selection returned nothing. A section that cannot be sourced is either a gap marker or a
stopped run, never a quiet omission.

### Staleness

The graph is a snapshot. This check reports how far the codebase has moved since it was taken. It
**warns; it never blocks** — a stale graph still produces a useful document, provided the reader is
told it is stale.

Read `gitCommitHash` from `meta.json`.

- If `meta.json` is missing, or does not carry `gitCommitHash`, report **that specific reason** —
  "meta.json is absent" and "meta.json has no gitCommitHash" are different findings — and record the
  skip in the provenance block. Then continue.
- If `git` is not on PATH, or the graph root is not inside a repository, announce the skip in console
  output **and** record it in the provenance block, naming which of the two applies. Then continue.

**Never skip silently.** A reader who is not told the check was skipped will assume it passed.

With a hash in hand, compare against `git rev-parse HEAD`. There are exactly three outcomes:

1. **Equal** — report "graph matches HEAD".
2. **Different, and the hash is a known ancestor** — confirm with `git merge-base --is-ancestor
   <hash> HEAD`, then get the distance with `git rev-list --count <hash>..HEAD`. Report "N commits
   behind HEAD".
3. **Different, and the hash is unknown to this repository** — the commit was rebased away, amended,
   or is absent from a shallow clone. Report drift with an **unknown** distance and say which of
   those the evidence supports.

**Never fabricate a distance.** If `git rev-list --count` cannot run or the hash is not an ancestor,
the honest answer is "unknown distance", with the reason. A made-up number is worse than no number,
because it reads as measured.

On any drift (outcomes 2 and 3), state the finding and ask the Project Manager whether to proceed
with the stale graph or stop and refresh it by re-running the plugin's `/understand`. If they choose
to proceed, record that in the provenance block as a PM decision — not as an incidental detail.

Every path through this check ends in one of: a distance, an explicit unknown-distance reason, or an
explicit skip reason. There is no silent outcome.

### `.gitignore` hygiene

## Document Conventions

### Gap markers

### Provenance block

### Generated document conventions

## Flow: Comprehension Analysis

---

# Project documentation

## Why the graph contract lives in this file

The contract sections above (**Preflight: Graph Contract** and **Document Conventions**) are shared
by every capability-(a) flow in initiative 360 — slices 362, 363, and 364 extend *this file* rather
than importing a fragment.

They are **not** factored into a separate fragment file, and this is deliberate. The pack installer's
`_install_prefix()` ([installer.py:87](../../src/squadron/skills/installer.py#L87)) globs every `*.md`
in the pack directory and installs each one as its own skill. A `graph-contract.md` fragment would
therefore surface to users as a bogus installable command that does nothing on its own.

Slice 365 (`commands/sq/`) copies these conventions rather than referencing them: a first-party
squadron command cannot assume the analysis pack is installed.
