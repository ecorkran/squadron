---
docType: guide
title: Pipeline Authoring Guide
dateCreated: 20260410
dateUpdated: 20260410
---

# Pipeline Authoring Guide

Pipelines let you compose multi-step AI workflows and run them with a single command.

```bash
sq run slice 152          # run the built-in slice lifecycle pipeline
sq run example --list     # list all available pipelines
```

---

## Quick Start

Three commands to verify the system works before reading further:

```bash
sq run --list                         # show all available pipelines with descriptions
sq run slice 152                      # run the full slice lifecycle for slice 152
sq run example 152 --dry-run          # show the step plan without executing anything
```

---

## YAML Grammar Reference

Each pipeline is a YAML file with a fixed top-level structure:

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Pipeline name (case-insensitive, used in `sq run <name>`) |
| `description` | string | yes | One-line description shown in `sq run --list` |
| `params` | map | no | Parameter declarations (`name: required` or `name: default-value`) |
| `model` | string | no | Pipeline-level default model alias |
| `steps` | list | yes | Ordered list of step definitions |

### Parameter placeholders

Parameters declared in `params` can be referenced anywhere inside step configs using `{param_name}` syntax.

**Required vs default params:**
- `param: required` — caller must supply the value positionally or with `--param param=value`
- `param: sonnet` — default applied automatically when caller does not override

**YAML quoting — mandatory:**

When a placeholder is the entire field value, it must be quoted:

```yaml
# CORRECT
model: "{model}"

# WRONG — bare braces parse as a YAML flow mapping and cause a load error
model: {model}
```

This applies whenever `{...}` is the full value of a scalar field. If the placeholder is embedded in a longer string (`"Reviewing slice {slice}"`) no quoting is needed.

### Step syntax

Each step is a single-key YAML map. The key is the step type; the value is the step config:

```yaml
steps:
  - design:          # step type: design
      phase: 4       # step config
      model: opus
```

### Scalar shorthand

For steps that accept a single string config, you can use the `key: value` shorthand:

```yaml
steps:
  - devlog: auto     # equivalent to: devlog: {mode: auto}
```

---

## Step Type Catalog

### Phase steps: `design`, `tasks`, `implement`

**Purpose:** Run a Context Forge phase — build context, dispatch to the LLM, optionally review the output, and commit the result.

**Expansion sequence:**
`cf-op(set_phase)` → `cf-op(set_slice)` → `cf-op(build_context)` → `dispatch` → [`review` → `checkpoint`] → `commit`

**Fields:**

| Field | Type | Required | Description |
|---|---|---|---|
| `phase` | int | yes | Context Forge phase number |
| `model` | string | no | Model alias for the dispatch action |
| `review` | string or dict | no | Review template name, or `{template, model}` dict |
| `checkpoint` | string | no | When to pause: `always`, `on-concerns`, `on-fail`, `never` (default: `never`) |

**Example:**

```yaml
- design:
    phase: 4
    model: opus
    review:
      template: slice
      model: minimax
    checkpoint: on-concerns
```

---

### `compact`

**Purpose:** Reduce the current session's context. Dispatches the best available mechanism per environment — no configuration required.

| Environment | Mechanism |
|---|---|
| `sq run` (true CLI) | Session-rotate: capture summary → disconnect → new session → restore |
| IDE / Claude Code CLI (prompt-only) | Dispatches `/compact` via `claude_agent_sdk.query()`, awaits `compact_boundary` |

**Fields:**

| Field | Type | Required | Description |
|---|---|---|---|
| `model` | string | no | Model alias used for summary capture in the true-CLI rotate path |
| `instructions` | string | no | Passed to `/compact` as prompt body (prompt-only) or summary instructions (true CLI) |

**Note:** `compact:` no longer implicitly captures a summary artifact. If you need a summary artifact around a compaction, use the explicit compose pattern:

```yaml
- summary:
    emit: [file]       # capture artifact before compacting

- compact:             # reduce context in place

- summary:
    restore: true      # re-inject the captured summary
```

**Migration:** pipelines that relied on `compact:` producing a summary (via the old `emit: [rotate]` expansion) must add an explicit `summary:` step before `compact:`.

**Example:**

```yaml
- compact:
    model: minimax
    instructions: Keep the most recent branch results verbatim; drop tool-use details.
```

---

### `summary`

**Purpose:** Generate a session summary and route it to one or more destinations; or re-inject a previously captured summary (`restore: true`).

**Fields:**

| Field | Type | Required | Description |
|---|---|---|---|
| `template` | string | no | Compaction template name (default: `default`) |
| `model` | string | no | Model alias for summary generation |
| `emit` | list | no | Destination list — see options below |
| `restore` | bool | no | If `true`, re-inject the most recent prior summary instead of generating a new one |
| `checkpoint` | string | no | Same triggers as phase steps |

**Restore mode:** `restore: true` reads the most recent `summary` result from prior steps and seeds it back into the session via `sdk_session.seed_context()`. Use after `compact:` to preserve a summary artifact across context reduction.

```yaml
- summary:
    restore: true
```

**Emit destinations:**

| Destination | Effect |
|---|---|
| `stdout` | Print to terminal |
| `clipboard` | Copy to system clipboard |
| `rotate` | Inject as compacted context and rotate the session |
| `{file: path}` | Write to file (relative to project root) |

**Example:**

```yaml
- summary:
    template: minimal-sdk
    model: minimax
    emit: [stdout, clipboard]
```

---

### `review`

**Purpose:** Standalone review outside a phase build.

**Fields:**

| Field | Type | Required | Description |
|---|---|---|---|
| `template` | string | yes | Review template name (`arch`, `slice`, `tasks`, `code`) |
| `model` | string | no | Model alias for the review |
| `checkpoint` | string | no | Same triggers as phase steps |

**Example:**

```yaml
- review:
    template: code
    model: minimax
```

---

### `devlog`

**Purpose:** Write a DEVLOG entry capturing pipeline state.

**Fields:**

| Field | Type | Description |
|---|---|---|
| `mode` | string | `auto` — generate entry automatically |

Prefer scalar shorthand:

```yaml
- devlog: auto
```

---

### `each`

**Purpose:** Iterate inner steps over a collection, running them once per item.

**Fields:**

| Field | Type | Required | Description |
|---|---|---|---|
| `source` | string | yes | Collection source expression |
| `as` | string | yes | Loop variable name |
| `steps` | list | yes | Inner step definitions using `{variable.field}` placeholders |

**Source options:**

| Expression | Returns |
|---|---|
| `cf.unfinished_slices("{plan}")` | All unfinished slices in a Context Forge plan |
| `cf.slices("{plan}")` | All slices in a plan |

Item fields are accessed as dotted references: `{slice.index}`, `{slice.title}`, etc.

**Example:**

```yaml
- each:
    source: cf.unfinished_slices("{plan}")
    as: slice
    steps:
      - design:
          phase: 4
          slice: "{slice.index}"
          model: opus
```

---

## Action Type Catalog

Actions are the internal execution units that step types expand into. Pipeline authors don't write actions directly — they appear in `--dry-run` and `--prompt-only` output.

| Action | Emitted by | What it does |
|---|---|---|
| `cf-op` | phase steps | Runs a Context Forge CLI operation (`set_phase`, `set_slice`, `build_context`) |
| `dispatch` | phase steps | Sends assembled context to an LLM; performs the phase work |
| `review` | phase steps, standalone review step | Runs `sq review <template>` and captures verdict and findings |
| `checkpoint` | phase steps (when `checkpoint:` is set) | Pauses pipeline; user decides to continue or abort |
| `commit` | phase steps | Runs `git add -A && git commit` |
| `compact` | compact step | Reduces context (session-rotate in true CLI; `/compact` dispatch in prompt-only) |
| `summary` | summary step | Generates summary text and routes to emit destinations |
| `devlog` | devlog step | Writes a DEVLOG entry |

---

## Model Resolution

Squadron resolves the active model for each action through a 5-level cascade, highest priority first:

1. **CLI override** — `sq run slice 152 --model haiku`
2. **Action-level model** — `review.model` inside a phase step's review config
3. **Step-level model** — `model:` on a phase, compact, summary, or review step
4. **Pipeline-level model** — top-level `model:` in the pipeline definition
5. **Config default** — `sq config get model.default`

If all levels are `None`, the run fails with an explicit error. There is no hidden global fallback.

Model values are **aliases** (e.g. `opus`, `sonnet`, `minimax`, `glm5`, `haiku`), not raw model IDs. Alias resolution happens at execution time. Aliases are defined in `src/squadron/data/models.toml` (built-in) and can be extended or overridden in `~/.config/squadron/models.toml`.

**Parameter-driven model example:**

```yaml
params:
  model: opus          # default; caller can override with --param model=sonnet

steps:
  - design:
      phase: 4
      model: "{model}"  # quotes required — bare {model} is a YAML parse error
```

---

## Configuration Surface

### Built-in defaults

Installed with the package at `src/squadron/data/`:

- `models.toml` — built-in model alias definitions
- `pipelines/*.yaml` — built-in pipeline definitions
- `compaction/*.yaml` — compaction templates (used by `compact` and `summary` steps)
- `review/templates/builtin/*.yaml` — review templates

### User overrides

`~/.config/squadron/`:

- `models.toml` — additional or overriding model aliases
- `pipelines/*.yaml` — additional or overriding pipeline definitions
- `compaction/*.yaml` — additional or overriding compaction templates
- `squadron.toml` — general config (`model.default`, `compact.template`, etc.)

### Project overrides

`<project-root>/project-documents/user/pipelines/`:

- `*.yaml` — project-local pipeline definitions (highest priority)

**Pipeline lookup order (first match wins):** project → user → built-in.

Built-in and user files use **identical formats** — copy any built-in file to the corresponding user or project directory to override or extend it.

---

## Built-in Pipelines

```bash
sq run --list    # shows all available pipelines with descriptions
```

| Name | Description | Key params |
|---|---|---|
| `slice` | Full lifecycle: design → tasks → compact → implement → compact → devlog | `slice`, `review-model` |
| `tasks` | Task breakdown through implementation | `slice`, `model`, `review-model` |
| `implement` | Implementation only (design and tasks already exist) | `slice`, `model` |
| `review` | Standalone review against existing artifacts | `slice`, `template`, `model` |
| `design-batch` | Phase 4 for every unfinished slice in a plan | `plan`, `model` |
| `P1` | Phase 1 (project vision) with arch review and checkpoint | `slice` |
| `P2` | Phase 2 (architecture) with arch review and checkpoint | `slice` |
| `P4` | Phase 4 (slice design) with slice review and checkpoint | `slice`, `model`, `review-model` |
| `P5` | Phase 5 (tasks) with tasks review | `slice`, `model`, `review-model` |
| `P6` | Phase 6 (implement) with code review | `slice`, `model`, `review-model` |
| `example` | Annotated reference — all available options | `slice` |

The `example` pipeline (`src/squadron/data/pipelines/example.yaml`) is the primary authoring reference. It includes inline comments explaining every field and option. Read it before writing a custom pipeline.

> **Note on naming:** The architecture document used placeholder names (`slice-lifecycle`, `review-only`, `implementation-only`). The shipped names (`slice`, `review`, `implement`) are the canonical user-facing names.

---

## Writing a Custom Pipeline

1. Create `<project-root>/project-documents/user/pipelines/<name>.yaml`
2. Use `example.yaml` as a template (`sq run example --validate` to see the reference pipeline, then copy `src/squadron/data/pipelines/example.yaml`)
3. Validate: `sq run <name> --validate`
4. Dry-run: `sq run <name> <target> --dry-run`

**Minimal custom pipeline:**

```yaml
name: my-review-loop
description: Design a slice, review it, and pause for human decision

params:
  slice: required
  model: sonnet

steps:
  - design:
      phase: 4
      model: "{model}"
      review:
        template: slice
        model: minimax
      checkpoint: on-concerns

  - devlog: auto
```

---

## Prompt-Only Mode

When running inside a Claude Code session (VS Code extension or terminal), `sq run` cannot execute LLM dispatch directly. Use `--prompt-only` to get step-by-step instructions instead:

```bash
sq run P4 152 --prompt-only                           # returns first step as JSON
sq run --prompt-only --next --resume <run-id>          # subsequent steps
sq run --step-done <run-id>                            # mark current step complete
```

The `/sq:run` slash command (installed via `sq install-commands`) wraps this loop automatically — you don't need to manage run IDs manually.
