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

*(authored in Task 2.1 — graph location and read discipline)*

### Graph location and read discipline

### Validation: absent, unparseable, malformed

### Staleness

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
