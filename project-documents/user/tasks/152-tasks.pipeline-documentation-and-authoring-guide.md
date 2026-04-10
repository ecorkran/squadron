---
docType: tasks
slice: pipeline-documentation-and-authoring-guide
project: squadron
lld: user/slices/152-slice.pipeline-documentation-and-authoring-guide.md
dependencies: [140, 141, 142, 143, 144, 145, 146, 147, 148, 149, 150, 151, 153, 155, 156, 157, 158, 161, 162]
projectState: All pipeline infrastructure (slices 140–162) complete; documentation not yet written
dateCreated: 20260410
dateUpdated: 20260410
status: complete
---

## Context Summary

- Writing user-facing documentation for the squadron pipeline system
- All pipeline infrastructure is complete; this slice makes it usable via documentation
- Deliverables: `docs/PIPELINES.md` (authoritative authoring guide) and `README.md` updates
- No code changes — documentation only
- Verification is done by cross-checking docs against source artifacts and running the slice design walkthrough commands
- Next: no immediate successor (152 is the final documentation slice for the pipeline foundation initiative)

---

## Tasks

### T1: Verify source artifacts before writing

- [x] Confirm `ActionType` enum members in `src/squadron/pipeline/actions/__init__.py` match the slice design's action catalog
  - [x] Expected: `dispatch`, `review`, `compact`, `summary`, `checkpoint`, `cf-op`, `commit`, `devlog`
- [x] Confirm registered step types match design (design, tasks, implement, compact, summary, review, devlog, each)
  - [x] Search for step type registration in `src/squadron/pipeline/` to enumerate all registered types
- [x] Confirm built-in pipeline files in `src/squadron/data/pipelines/` match the design's built-in pipeline table
  - [x] Expected: `slice`, `tasks`, `implement`, `review`, `design-batch`, `P1`, `P2`, `P4`, `P5`, `P6`, `example`
  - [x] Note any extra files (e.g. `test-pipeline.yaml`, `app.yaml`) — do not document test/dev pipelines
- [x] Confirm `example.yaml` exists and passes `sq run example --validate`
- [x] Confirm model resolution implementation in `resolver.py` matches the 5-level cascade in the slice design
  - [x] Levels: CLI override → action-level → step-level → pipeline-level → config default
- [x] Document any discrepancies found; do not write documentation that contradicts the code

### T2: Create docs/ directory and PIPELINES.md skeleton

- [x] Create `docs/` directory at project root if it does not exist
- [x] Create `docs/PIPELINES.md` with YAML front matter and top-level section headings
  - [x] Front matter: `docType: guide`, `title`, `dateCreated`, `dateUpdated`
  - [x] Section headings matching the design: Quick Start, YAML Grammar Reference, Step Type Catalog, Action Type Catalog, Model Resolution, Configuration Surface, Built-in Pipelines, Writing a Custom Pipeline, Prompt-Only Mode
- [x] Verify file is parseable markdown (no unclosed fences or malformed YAML front matter)

### T3: Write the Quick Start section

- [x] Add `## Quick Start` section to `docs/PIPELINES.md`
  - [x] Include three commands: `sq run --list`, `sq run slice 152`, `sq run example 152 --dry-run`
  - [x] Each command has a one-line explanation of what it does
  - [x] Section is self-contained — a user can verify the system works before reading further
- [x] Verify: section is ≤ 15 lines and covers all three commands from the slice design

### T4: Write the YAML Grammar Reference section

- [x] Add `## YAML Grammar Reference` section with top-level fields table
  - [x] Table columns: Field, Type, Required, Description
  - [x] Rows: `name`, `description`, `params`, `model`, `steps` — match design exactly
- [x] Document parameter placeholder syntax (`{param_name}`)
  - [x] Include the YAML quoting requirement with a clear example: `model: "{model}"` not `model: {model}`
  - [x] Explain why: bare braces parse as YAML flow mapping
  - [x] Explain `required` vs default params
- [x] Document step syntax (single-key YAML map) with the step example from the design
- [x] Document scalar step shorthand (`- devlog: auto`) with expansion note
- [x] Verify: quoting requirement is prominent (not buried in a footnote)

### T5: Write the Step Type Catalog section

- [x] Add `## Step Type Catalog` section
- [x] Write entry for phase steps: `design`, `tasks`, `implement`
  - [x] Purpose, expansion sequence, fields table (`phase`, `model`, `review`, `checkpoint`), minimal YAML example
- [x] Write entry for `compact`
  - [x] Purpose, fields table (`template`, `model`, `keep`, `summarize`), note on built-in usage
- [x] Write entry for `summary`
  - [x] Purpose, fields table (`template`, `model`, `emit`, `checkpoint`), emit destination options
- [x] Write entry for `review`
  - [x] Purpose, fields (`template`, `model`, `checkpoint`)
- [x] Write entry for `devlog`
  - [x] Purpose, fields (`mode`), scalar shorthand preferred
- [x] Write entry for `each`
  - [x] Purpose, fields (`source`, `as`, `steps`), dotted binding note, source options
- [x] Verify: all 8 step types (design, tasks, implement, compact, summary, review, devlog, each) have entries; cross-check against registered step types found in T1

### T6: Write the Action Type Catalog section

- [x] Add `## Action Type Catalog` section with introductory note (authors don't write actions directly; actions appear in `--dry-run` and `--prompt-only` output)
- [x] Write table with columns: Action, Emitted by, What it does
- [x] Include all 8 action types confirmed in T1: `cf-op`, `dispatch`, `review`, `checkpoint`, `commit`, `compact`, `summary`, `devlog`
- [x] Verify: table matches `ActionType` enum exactly — no extra or missing entries

### T7: Write the Model Resolution section

- [x] Add `## Model Resolution` section
  - [x] Five-level cascade list (highest to lowest priority) matching T1 verification
  - [x] Note: if all levels are `None`, run fails with explicit error (no hidden fallback)
  - [x] Note: model values are aliases, not raw model IDs; resolution at execution time
  - [x] Note: alias definitions in `src/squadron/data/models.toml` and user overrides in `~/.config/squadron/models.toml`
  - [x] Include parameter-driven model YAML example with quoting comment
- [x] Verify: cascade order matches `resolver.py` exactly

### T8: Write the Configuration Surface section

- [x] Add `## Configuration Surface` section
  - [x] Subsection: Built-in defaults (`src/squadron/data/`) — list `models.toml`, `pipelines/*.yaml`, `compaction/*.yaml`, `review/templates/builtin/*.yaml`
  - [x] Subsection: User overrides (`~/.config/squadron/`) — list `models.toml`, `pipelines/*.yaml`, `compaction/*.yaml`, `squadron.toml`
  - [x] Subsection: Project overrides (`<project-root>/project-documents/user/pipelines/`) — highest priority for pipelines
  - [x] Pipeline lookup order note: project → user → built-in (first match wins)
  - [x] Note: built-in and user files use identical formats; copy-to-override pattern
- [x] Verify: all three override tiers are documented

### T9: Write the Built-in Pipelines section

- [x] Add `## Built-in Pipelines` section
- [x] Write table with columns: Name, Description, Key params
  - [x] Rows for all pipelines confirmed in T1 (exclude test/dev pipelines not intended for users)
  - [x] Match descriptions and params to actual pipeline YAML files, not just the slice design
- [x] Add note on `example` pipeline as primary authoring reference and inline-comment density
- [x] Add note resolving naming discrepancy: architecture used placeholder names; shipped names (`slice`, `review`, `implement`) are canonical
- [x] Verify: `sq run --list` output matches the table (run command to confirm)

### T10: Write the Writing a Custom Pipeline section

- [x] Add `## Writing a Custom Pipeline` section
  - [x] Four-step procedure: create file, use example.yaml as template, validate, dry-run
  - [x] File location: `<project-root>/project-documents/user/pipelines/<name>.yaml`
  - [x] Include the minimal custom pipeline example from the slice design
  - [x] Commands: `sq run <name> --validate` and `sq run <name> <target> --dry-run`
- [x] Verify: the minimal example in the guide passes `sq run my-test --validate` when written to the project pipelines directory

### T11: Write the Prompt-Only Mode section

- [x] Add `## Prompt-Only Mode` section
  - [x] Explain context: inside a Claude Code session, direct LLM dispatch is not possible
  - [x] Document `--prompt-only` flag and the three commands from the slice design
  - [x] Note: `/sq:run` slash command wraps this loop automatically
- [x] Verify: section accurately describes the prompt-only workflow (cross-check with `sq run --help` output)

### T12: Final PIPELINES.md verification

- [x] Run each verification command from the slice design's Verification Walkthrough:
  - [x] `cat docs/PIPELINES.md | head -5` — file exists and is readable
  - [x] `sq run example --validate` — example.yaml passes validation
  - [x] Create `project-documents/user/pipelines/my-test.yaml` from guide's minimal example
  - [x] `sq run my-test --validate` — passes
  - [x] `sq run my-test 152 --dry-run` — shows step plan without executing
  - [x] `sq run --list` — output matches Built-in Pipelines table in docs
- [x] Check all 7 success criteria from the slice design (§ Success Criteria)
- [x] Remove `my-test.yaml` after verification
- [x] Commit: `docs: add pipeline authoring guide`

### T13: Update README.md

- [x] Read `README.md` to identify the correct insertion point
  - [x] If a `## Commands` or `## Usage` section exists, add `sq run` there
  - [x] If no such section exists, add a new `## sq run` section at an appropriate location
- [x] Add content per the slice design:
  - [x] One-line description of the pipeline system
  - [x] Quick-start example (`sq run slice 152`)
  - [x] Link to `docs/PIPELINES.md` for full reference
  - [x] Note on `--prompt-only` mode for IDE use
- [x] Verify: `grep -n "sq run\|PIPELINES" README.md` returns the added lines
- [x] Commit: `docs: add sq run section to README`

### T14: Write DEVLOG entry

- [x] Write DEVLOG entry for this session following `prompt.ai-project.system.md` § Session State Summary
  - [x] Record: slice 152 complete, deliverables created (`docs/PIPELINES.md`, `README.md` updates)
  - [x] Record: any discrepancies found between slice design and source during T1 verification
- [x] Mark slice 152 status as `complete` in `user/slices/152-slice.pipeline-documentation-and-authoring-guide.md`
- [x] Mark slice 152 as complete in the slice plan (`100-slices.orchestration-v2.md`) if applicable
