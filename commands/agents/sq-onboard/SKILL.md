---
name: sq-onboard
description: Adopts an existing codebase into squadron and Context Forge one step at a time, driven by `sq onboard`. Use when the user asks to onboard, adopt or bring an existing (brownfield) project under squadron and Context Forge.
---

# sq onboard

Adopt an existing codebase into squadron and Context Forge, one step at a time.

## Input parsing

The text the user typed after `$sq-onboard` is the project directory. If there is none, use the
current directory. Call it `<dir>`.

## The loop

1. Run `sq onboard --path <dir> --json`. If it exits non-zero, show its stderr line and stop.
2. Read `next.step` from the JSON and do exactly that step below.
3. Go back to 1.

`sq onboard` decides the step. Never choose a step yourself, and never run a step the JSON does not
name.

## The steps

### Step: handoff

Print the `notices` from the JSON exactly as given. Then print the command that `next.handoff`
names: `cf-onboard` means run `/cf:onboard`, and `cf-next` means run `cf next`. Stop.

### Step: ask-adopt

The project has existing code that Context Forge does not know about. Ask the user whether to adopt
it into Context Forge.

- Yes: run `sq onboard register --path <dir> --ide agents`. The `--ide agents` option makes cf set
  up Codex rather than its default, Claude. If it exits 1, show its output, tell the user to fix the
  cause and re-run `sq onboard register --path <dir> --ide agents`, and stop.
- No: run `sq onboard decline --path <dir>`, show its output, and stop.

### Step: build-graph

The comprehension analysis reads an `understand-anything` knowledge graph, and the graph is absent,
behind HEAD, or of unknown staleness. Tell the user which: absent, how many commits behind
(`graph.commits_behind`), or that staleness is unknown. Ask whether to build it.

- First check `surfaces` → `codex` → `understand_plugin_installed`. If it is not true, tell the user
  to install the `understand-anything` plugin for Codex and stop. Never install it yourself.
- Yes: first make sure `<dir>/.understand-anything/.understandignore` excludes the tooling `cf init`
  installed, so the graph describes the project's code and not the guide: create the file if it is
  absent and append only the missing lines among `project-documents/ai-project-guide/`, `.claude/` and
  `.context-forge/`. Then run the plugin's `$understand` skill.
- No, and the graph is absent: stop. The comprehension step needs a graph.
- No, and the graph is present: go straight to the `comprehension` step without running
  `sq onboard` again.

### Step: comprehension

First check `surfaces` → `codex` → `analysis_skill_installed`. If it is not true, tell the user to
run `sq skills install analysis` and stop.

Run `$analysis-understand comprehension`.

### Step: concept

First check `surfaces` → `codex` → `analysis_skill_installed`. If it is not true, tell the user to
run `sq skills install analysis` and stop.

Run `$analysis-understand concept`. That flow asks the user its own questions and never overwrites a
concept without them.

### Step: adopt

Run `sq onboard prompt --path <dir>`. If it exits non-zero, show its stderr line and stop.
Otherwise follow the prompt it printed.

## No-progress stop

Remember which step you just did. If `sq onboard` then reports that same step again, stop. Also stop
if you just did `comprehension` and it now reports `build-graph` (the user kept a stale graph and no
comprehension doc was written). Tell the user what you did and what `sq onboard` reported, and wait
for them. Do not repeat a step to try again. This covers an `adopt` that leaves cf at
`adoption-incomplete`, a concept the user declined, and a comprehension run that wrote no document.
