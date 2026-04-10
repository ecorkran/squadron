---
docType: tasks
slice: pipeline-documentation-and-authoring-guide
project: squadron
lld: user/slices/152-slice.pipeline-documentation-and-authoring-guide.md
dependencies: [140, 141, 142, 143, 144, 145, 146, 147, 148, 149, 150, 151, 153, 155, 156, 157, 158, 161, 162]
projectState: All pipeline infrastructure (slices 140–162) complete; documentation not yet written
dateCreated: 20260410
dateUpdated: 20260410
status: not_started
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

- [ ] Confirm `ActionType` enum members in `src/squadron/pipeline/actions/__init__.py` match the slice design's action catalog
  - [ ] Expected: `dispatch`, `review`, `compact`, `summary`, `checkpoint`, `cf-op`, `commit`, `devlog`
- [ ] Confirm registered step types match design (design, tasks, implement, compact, summary, review, devlog, each)
  - [ ] Search for step type registration in `src/squadron/pipeline/` to enumerate all registered types
- [ ] Confirm built-in pipeline files in `src/squadron/data/pipelines/` match the design's built-in pipeline table
  - [ ] Expected: `slice`, `tasks`, `implement`, `review`, `design-batch`, `P1`, `P2`, `P4`, `P5`, `P6`, `example`
  - [ ] Note any extra files (e.g. `test-pipeline.yaml`, `app.yaml`) — do not document test/dev pipelines
- [ ] Confirm `example.yaml` exists and passes `sq run example --validate`
- [ ] Confirm model resolution implementation in `resolver.py` matches the 5-level cascade in the slice design
  - [ ] Levels: CLI override → action-level → step-level → pipeline-level → config default
- [ ] Document any discrepancies found; do not write documentation that contradicts the code

### T2: Create docs/ directory and PIPELINES.md skeleton

- [ ] Create `docs/` directory at project root if it does not exist
- [ ] Create `docs/PIPELINES.md` with YAML front matter and top-level section headings
  - [ ] Front matter: `docType: guide`, `title`, `dateCreated`, `dateUpdated`
  - [ ] Section headings matching the design: Quick Start, YAML Grammar Reference, Step Type Catalog, Action Type Catalog, Model Resolution, Configuration Surface, Built-in Pipelines, Writing a Custom Pipeline, Prompt-Only Mode
- [ ] Verify file is parseable markdown (no unclosed fences or malformed YAML front matter)

### T3: Write the Quick Start section

- [ ] Add `## Quick Start` section to `docs/PIPELINES.md`
  - [ ] Include three commands: `sq run --list`, `sq run slice 152`, `sq run example 152 --dry-run`
  - [ ] Each command has a one-line explanation of what it does
  - [ ] Section is self-contained — a user can verify the system works before reading further
- [ ] Verify: section is ≤ 15 lines and covers all three commands from the slice design

### T4: Write the YAML Grammar Reference section

- [ ] Add `## YAML Grammar Reference` section with top-level fields table
  - [ ] Table columns: Field, Type, Required, Description
  - [ ] Rows: `name`, `description`, `params`, `model`, `steps` — match design exactly
- [ ] Document parameter placeholder syntax (`{param_name}`)
  - [ ] Include the YAML quoting requirement with a clear example: `model: "{model}"` not `model: {model}`
  - [ ] Explain why: bare braces parse as YAML flow mapping
  - [ ] Explain `required` vs default params
- [ ] Document step syntax (single-key YAML map) with the step example from the design
- [ ] Document scalar step shorthand (`- devlog: auto`) with expansion note
- [ ] Verify: quoting requirement is prominent (not buried in a footnote)

### T5: Write the Step Type Catalog section

- [ ] Add `## Step Type Catalog` section
- [ ] Write entry for phase steps: `design`, `tasks`, `implement`
  - [ ] Purpose, expansion sequence, fields table (`phase`, `model`, `review`, `checkpoint`), minimal YAML example
- [ ] Write entry for `compact`
  - [ ] Purpose, fields table (`template`, `model`, `keep`, `summarize`), note on built-in usage
- [ ] Write entry for `summary`
  - [ ] Purpose, fields table (`template`, `model`, `emit`, `checkpoint`), emit destination options
- [ ] Write entry for `review`
  - [ ] Purpose, fields (`template`, `model`, `checkpoint`)
- [ ] Write entry for `devlog`
  - [ ] Purpose, fields (`mode`), scalar shorthand preferred
- [ ] Write entry for `each`
  - [ ] Purpose, fields (`source`, `as`, `steps`), dotted binding note, source options
- [ ] Verify: all 8 step types (design, tasks, implement, compact, summary, review, devlog, each) have entries; cross-check against registered step types found in T1

### T6: Write the Action Type Catalog section

- [ ] Add `## Action Type Catalog` section with introductory note (authors don't write actions directly; actions appear in `--dry-run` and `--prompt-only` output)
- [ ] Write table with columns: Action, Emitted by, What it does
- [ ] Include all 8 action types confirmed in T1: `cf-op`, `dispatch`, `review`, `checkpoint`, `commit`, `compact`, `summary`, `devlog`
- [ ] Verify: table matches `ActionType` enum exactly — no extra or missing entries

### T7: Write the Model Resolution section

- [ ] Add `## Model Resolution` section
  - [ ] Five-level cascade list (highest to lowest priority) matching T1 verification
  - [ ] Note: if all levels are `None`, run fails with explicit error (no hidden fallback)
  - [ ] Note: model values are aliases, not raw model IDs; resolution at execution time
  - [ ] Note: alias definitions in `src/squadron/data/models.toml` and user overrides in `~/.config/squadron/models.toml`
  - [ ] Include parameter-driven model YAML example with quoting comment
- [ ] Verify: cascade order matches `resolver.py` exactly

### T8: Write the Configuration Surface section

- [ ] Add `## Configuration Surface` section
  - [ ] Subsection: Built-in defaults (`src/squadron/data/`) — list `models.toml`, `pipelines/*.yaml`, `compaction/*.yaml`, `review/templates/builtin/*.yaml`
  - [ ] Subsection: User overrides (`~/.config/squadron/`) — list `models.toml`, `pipelines/*.yaml`, `compaction/*.yaml`, `squadron.toml`
  - [ ] Subsection: Project overrides (`<project-root>/project-documents/user/pipelines/`) — highest priority for pipelines
  - [ ] Pipeline lookup order note: project → user → built-in (first match wins)
  - [ ] Note: built-in and user files use identical formats; copy-to-override pattern
- [ ] Verify: all three override tiers are documented

### T9: Write the Built-in Pipelines section

- [ ] Add `## Built-in Pipelines` section
- [ ] Write table with columns: Name, Description, Key params
  - [ ] Rows for all pipelines confirmed in T1 (exclude test/dev pipelines not intended for users)
  - [ ] Match descriptions and params to actual pipeline YAML files, not just the slice design
- [ ] Add note on `example` pipeline as primary authoring reference and inline-comment density
- [ ] Add note resolving naming discrepancy: architecture used placeholder names; shipped names (`slice`, `review`, `implement`) are canonical
- [ ] Verify: `sq run --list` output matches the table (run command to confirm)

### T10: Write the Writing a Custom Pipeline section

- [ ] Add `## Writing a Custom Pipeline` section
  - [ ] Four-step procedure: create file, use example.yaml as template, validate, dry-run
  - [ ] File location: `<project-root>/project-documents/user/pipelines/<name>.yaml`
  - [ ] Include the minimal custom pipeline example from the slice design
  - [ ] Commands: `sq run <name> --validate` and `sq run <name> <target> --dry-run`
- [ ] Verify: the minimal example in the guide passes `sq run my-test --validate` when written to the project pipelines directory

### T11: Write the Prompt-Only Mode section

- [ ] Add `## Prompt-Only Mode` section
  - [ ] Explain context: inside a Claude Code session, direct LLM dispatch is not possible
  - [ ] Document `--prompt-only` flag and the three commands from the slice design
  - [ ] Note: `/sq:run` slash command wraps this loop automatically
- [ ] Verify: section accurately describes the prompt-only workflow (cross-check with `sq run --help` output)

### T12: Final PIPELINES.md verification

- [ ] Run each verification command from the slice design's Verification Walkthrough:
  - [ ] `cat docs/PIPELINES.md | head -5` — file exists and is readable
  - [ ] `sq run example --validate` — example.yaml passes validation
  - [ ] Create `project-documents/user/pipelines/my-test.yaml` from guide's minimal example
  - [ ] `sq run my-test --validate` — passes
  - [ ] `sq run my-test 152 --dry-run` — shows step plan without executing
  - [ ] `sq run --list` — output matches Built-in Pipelines table in docs
- [ ] Check all 7 success criteria from the slice design (§ Success Criteria)
- [ ] Remove `my-test.yaml` after verification
- [ ] Commit: `docs: add pipeline authoring guide`

### T13: Update README.md

- [ ] Read `README.md` to identify the correct insertion point
  - [ ] If a `## Commands` or `## Usage` section exists, add `sq run` there
  - [ ] If no such section exists, add a new `## sq run` section at an appropriate location
- [ ] Add content per the slice design:
  - [ ] One-line description of the pipeline system
  - [ ] Quick-start example (`sq run slice 152`)
  - [ ] Link to `docs/PIPELINES.md` for full reference
  - [ ] Note on `--prompt-only` mode for IDE use
- [ ] Verify: `grep -n "sq run\|PIPELINES" README.md` returns the added lines
- [ ] Commit: `docs: add sq run section to README`

### T14: Write DEVLOG entry

- [ ] Write DEVLOG entry for this session following `prompt.ai-project.system.md` § Session State Summary
  - [ ] Record: slice 152 complete, deliverables created (`docs/PIPELINES.md`, `README.md` updates)
  - [ ] Record: any discrepancies found between slice design and source during T1 verification
- [ ] Mark slice 152 status as `complete` in `user/slices/152-slice.pipeline-documentation-and-authoring-guide.md`
- [ ] Mark slice 152 as complete in the slice plan (`100-slices.orchestration-v2.md`) if applicable
