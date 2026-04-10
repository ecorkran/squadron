---
docType: slice-design
project: squadron
initiative: 140-slices.pipeline-foundation
dateCreated: 20260410
dateUpdated: 20260410
status: complete
index: 152
---

# Slice 152: Pipeline Documentation and Authoring Guide

## Overview

This slice produces the user-facing documentation for the pipeline system: a comprehensive authoring guide, a command reference update for `sq run`, and a configuration surface guide. All pipeline infrastructure (140–162) is complete; this slice makes it usable by documenting it.

No code changes. All deliverables are markdown documentation files.

## Deliverables

### 1. `docs/PIPELINES.md` — Pipeline Authoring Guide

New file. Authoritative reference for pipeline authors. Structure:

#### § Quick Start
Three commands: `sq run --list`, `sq run slice 152`, `sq run example 152 --dry-run`. Enough to prove it works before reading further.

#### § YAML Grammar Reference

Top-level fields:

| Field | Type | Required | Description |
|---|---|---|---|
| `name` | string | yes | Pipeline name (case-insensitive, used in `sq run <name>`) |
| `description` | string | yes | One-line description shown in `sq run --list` |
| `params` | map | no | Parameter declarations (name: `required` or default value) |
| `model` | string | no | Pipeline-level default model alias |
| `steps` | list | yes | Ordered list of step definitions |

Parameter placeholders:
- Syntax: `{param_name}` in any string value within a step config
- YAML: must be quoted when the entire value is a placeholder — `model: "{model}"`, not `model: {model}` (bare braces parse as a YAML flow mapping)
- Substitution is eager — unresolved placeholders remain as literal strings (validator catches references to undeclared params at load time)
- `required` params: caller must supply positionally or via `--param`; default params are applied automatically when not overridden

Step syntax — each step is a single-key YAML map where the key is the step type:
```yaml
steps:
  - design:          # step type: design
      phase: 4       # step config fields
      model: opus
```

Scalar step shorthand for devlog:
```yaml
  - devlog: auto     # equivalent to: devlog: {mode: auto}
```

#### § Step Type Catalog

Each entry: purpose, expansion (what action sequence it expands into), YAML fields, and a minimal example.

**Phase steps: `design`, `tasks`, `implement`**
- Purpose: Run a phase via CF context build → model dispatch → optional review → commit
- Expansion: `cf-op(set_phase)` → `cf-op(set_slice)` → `cf-op(build_context)` → `dispatch` → [`review` → `checkpoint`] → `commit`
- Fields:
  - `phase` (int, required): CF phase number
  - `model` (string, optional): model alias for dispatch
  - `review` (string or dict, optional): review template name, or `{template, model}` dict
  - `checkpoint` (string, optional): `always | on-concerns | on-fail | never` — default `never`

**`compact`**
- Purpose: Compress context at a step boundary
- Fields:
  - `template` (string): compaction template name
  - `model` (string): model for compaction
  - `keep` (list of strings, optional): items to preserve in context
  - `summarize` (bool, optional): whether to update CF project summary
- Note: the built-in pipelines use `template` + `model`; `keep` and `summarize` are available for fine-grained control

**`summary`**
- Purpose: Generate a session summary and emit to configured destinations
- Fields:
  - `template` (string): compaction template name
  - `model` (string): model for summary generation  
  - `emit` (list): destinations — `stdout`, `clipboard`, `rotate`, `{file: path}`
  - `checkpoint` (string, optional): same triggers as phase steps

**`review`**
- Purpose: Standalone review step outside a phase build
- Fields: `template` (required), `model` (optional), `checkpoint` (optional)

**`devlog`**
- Purpose: Write a DEVLOG entry capturing pipeline state
- Fields: `mode` (`auto` or `manual`); scalar shorthand `- devlog: auto` is preferred

**`each`**
- Purpose: Iterate inner steps over a collection
- Fields:
  - `source` (string): collection source — currently `cf.unfinished_slices("{plan}")` or `cf.slices("{plan}")`
  - `as` (string): loop variable name
  - `steps` (list): inner step definitions using `{as.field}` placeholders
- Item fields accessible as `{variable.index}`, `{variable.title}`, etc. (dotted binding, sourced from CF query — binding semantics established in slice 149)

#### § Action Type Catalog

Actions are the internal execution units that step types expand into. Authors don't write actions directly, but understanding them clarifies what pipelines do and what shows up in `--dry-run` and `--prompt-only` output.

| Action | Emitted by | What it does |
|---|---|---|
| `cf-op` | phase steps | Runs a Context Forge CLI operation (`set_phase`, `set_slice`, `build_context`) |
| `dispatch` | phase steps | Sends assembled context to an LLM; performs the phase work |
| `review` | phase steps, standalone review step | Runs `sq review <template>` and captures verdict + findings |
| `checkpoint` | phase steps (when `checkpoint:` is set) | Pauses pipeline; user decides to continue or abort |
| `commit` | phase steps | Runs `git add -A && git commit -m '<prefix>: ...'` |
| `compact` | compact step | Issues compaction instruction (session rotate) |
| `summary` | summary step | Generates summary text and routes to emit destinations |
| `devlog` | devlog step | Writes a DEVLOG entry |

#### § Model Resolution

Five-level cascade, highest priority first:

1. **CLI override** — `sq run slice 152 --model haiku`
2. **Action-level model** — set inside a step's `review.model` field
3. **Step-level model** — `model:` field on a phase/summary/etc. step
4. **Pipeline-level model** — top-level `model:` on the pipeline definition
5. **Config default** — `sq config get model.default`

If all levels are `None`, the run fails with an explicit error. There is no hidden global fallback.

Model values are **aliases** (e.g. `opus`, `sonnet`, `minimax`, `glm5`, `haiku`), not raw model IDs. Alias → model-id resolution happens at execution time. Aliases are defined in `src/squadron/data/models.toml` and user overrides in `~/.config/squadron/models.toml`.

**Parameter-driven model example:**
```yaml
params:
  model: opus          # default; caller can override with --param model=sonnet

steps:
  - design:
      phase: 4
      model: "{model}"  # NOTE: quotes required — bare {model} parses as YAML flow map
```

#### § Configuration Surface

**Built-in defaults** live in `src/squadron/data/` (installed with the package):
- `models.toml` — model alias definitions
- `pipelines/*.yaml` — built-in pipeline definitions
- `compaction/*.yaml` — compaction templates (used by `compact` and `summary` steps)
- `review/templates/builtin/*.yaml` — review templates

**User overrides** live in `~/.config/squadron/`:
- `models.toml` — additional/overriding model aliases
- `pipelines/*.yaml` — additional/overriding pipeline definitions
- `compaction/*.yaml` — additional/overriding compaction templates
- `squadron.toml` — general config (`model.default`, `compact.template`, etc.)

**Project overrides** live in `<project-root>/project-documents/user/pipelines/`:
- `*.yaml` — project-local pipeline definitions (highest priority for pipelines)

Pipeline lookup order (first match wins): project → user → built-in.

Built-in and user override files use **identical formats** — copy a block from a built-in file to your user config directory to override or extend it.

#### § Built-in Pipelines

| Name | Description | Key params |
|---|---|---|
| `slice` | Full lifecycle: design → tasks → compact → implement → compact → devlog | `slice` |
| `tasks` | Tasks + implementation only | `slice`, `review-model` |
| `implement` | Implementation only (design + tasks already exist) | `slice`, `model` |
| `review` | Standalone review | `slice`, `template`, `model` |
| `design-batch` | Phase 4 for every unfinished slice in a plan | `plan`, `model` |
| `P1` | Phase 1 (project vision) with arch review and checkpoint | `slice` |
| `P2` | Phase 2 (architecture) with arch review | `slice` |
| `P4` | Phase 4 (slice design) with slice review | `slice`, `model`, `review-model` |
| `P5` | Phase 5 (tasks) with tasks review | `slice`, `review-model` |
| `P6` | Phase 6 (implement) with code review | `slice`, `review-model` |
| `example` | Annotated reference — all available options | `slice` |

The `example` pipeline (`src/squadron/data/pipelines/example.yaml`) is the primary authoring reference. It includes inline comments explaining every field and option. Read it before writing a custom pipeline.

> **Note on naming:** The architecture document used placeholder names (`slice-lifecycle`, `review-only`, `implementation-only`). The shipped pipeline names (`slice`, `review`, `implement`) are the canonical user-facing names. The `P1`–`P6` shortcuts are an addition beyond the minimum specified in the architecture.

#### § Writing a Custom Pipeline

1. Create `<project-root>/project-documents/user/pipelines/<name>.yaml`
2. Use `example.yaml` as a template
3. Validate: `sq run <name> --validate`
4. Dry-run: `sq run <name> <target> --dry-run`

Minimal custom pipeline:
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

#### § Prompt-Only Mode

When running inside a Claude Code session (IDE or terminal), `sq run` cannot execute LLM dispatch directly. Use `--prompt-only` to get step-by-step instructions:

```bash
sq run P4 152 --prompt-only        # returns first step as JSON
sq run --prompt-only --next --resume <run-id>  # subsequent steps
sq run --step-done <run-id>        # mark current step complete
```

The `/sq:run` slash command wraps this loop automatically.

---

### 2. README.md updates

Add or update the `## sq run` section in `README.md` to include:
- One-line description of the pipeline system
- Quick-start example (`sq run slice 152`)
- Link to `docs/PIPELINES.md` for full reference
- Note on `--prompt-only` mode for IDE use

The existing README likely has no `sq run` section. If a `## Commands` or `## Usage` section exists, add `sq run` there.

---

## Success Criteria

1. A user unfamiliar with the pipeline system can read `docs/PIPELINES.md` and author a working custom pipeline without reading source code
2. The YAML grammar section correctly documents the quoting requirement for parameter placeholders
3. The model resolution table matches the actual 5-level cascade in `resolver.py`
4. The step type catalog matches all registered step types (design, tasks, implement, compact, summary, review, devlog, each)
5. The action type catalog matches all action types in `ActionType` enum
6. All built-in pipelines are listed with correct descriptions and params
7. README.md includes `sq run` with a link to the guide

## Verification Walkthrough

```bash
# 1. Confirm docs/PIPELINES.md exists and is accessible
cat docs/PIPELINES.md | head -5

# 2. Confirm README references sq run and links to PIPELINES.md
grep -n "sq run\|PIPELINES" README.md

# 3. Confirm example.yaml referenced in guide actually exists
sq run example --validate

# 4. Follow the custom pipeline example from the guide
mkdir -p project-documents/user/pipelines
cat > project-documents/user/pipelines/my-test.yaml <<'EOF'
name: my-test
description: Test pipeline from authoring guide

params:
  slice: required

steps:
  - design:
      phase: 4
      model: haiku
EOF

sq run my-test --validate        # should pass
sq run my-test 152 --dry-run     # should show step plan without executing

# 5. Confirm built-in pipeline list matches documentation
sq run --list
```

## Cross-Slice Dependencies

- All slices 140–162 must be complete (they are)
- No code changes required; documentation-only slice

## Notes

- `example.yaml` is intentionally dense with comments — the guide should point users there rather than duplicate the inline documentation
- The YAML quoting requirement for parameter placeholders is a non-obvious footgun discovered during P4 pipeline testing; it must be prominent in the grammar reference
- The `pool:` prefix is mentioned in resolver.py but not yet implemented (slice 160 scope) — do not document it as an available feature
