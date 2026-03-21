---
docType: review
reviewType: arch
slice: claude-code-commands-composed-workflows
project: squadron
verdict: CONCERNS
dateCreated: 20260321
dateUpdated: 20260321
---

# Review: arch — slice 118

**Verdict:** CONCERNS
**Model:** opus

## Findings

### [PASS] Layer boundaries respected

The slice operates entirely in the Interface Layer (CLI + Claude Code commands). It does not touch the Core Engine, Agent Provider Layer, or any protocol definitions. The `run-slice.md` command file delegates all orchestration work to existing CLI commands (`sq review tasks`, `sq review code`) and external tooling (`cf`). No new Python business logic leaks into the command layer.

### [PASS] Dependency directions are correct

The slice correctly depends downward:
- **Slice 116 (sq Wrappers)**: provides the `commands/sq/` directory, install mechanism, and wheel bundling — all consumed, not modified.
- **Slice 105 (Review Workflow Templates)**: provides `sq review tasks`, `sq review code`, `sq review arch` — invoked by the composed workflow.
- **Context-Forge CLI**: external dependency consumed via shell commands.

No upward or circular dependencies exist.

### [PASS] Integration points match consuming/providing slices

The slice correctly identifies what it consumes from slices 105 and 116. The review commands it invokes (`sq review tasks`, `sq review code`, `sq review arch`) exist and are documented in slice 105. The `commands/sq/` install mechanism from slice 116 requires no changes — the new file is picked up automatically.

### [CONCERN] Significant scope divergence from slice plan entry

The slice plan entry (item 15, slice 118) describes three composed workflow commands in a `workflow/` namespace:
- `/workflow:next-step` — interprets project state and recommends next action
- `/workflow:design-review` — assembles context then runs arch review
- `/workflow:ensemble-review` — runs reviews across multiple providers and synthesizes results

The actual slice design delivers something substantially different:
- One new command (`/sq:run-slice`) in the `sq/` namespace (not `workflow/`)
- Updates to three existing review commands for number shorthand and review persistence
- CLI number shorthand for `sq review` commands
- Review file persistence with YAML frontmatter

The rationale for the namespace decision is documented and sound (one command doesn't justify a new namespace). The pivot from three theoretical commands to one validated-by-use command is explicitly acknowledged ("deferred until real usage validates need"). However, the `/workflow:ensemble-review` concept (cross-provider review synthesis) is architecturally interesting and maps to slice 130 (Ensemble Review) — its deferral is reasonable but should be noted in the slice plan.

**Impact**: The slice plan entry should be updated to reflect reality. Anyone reading the plan would expect `workflow/` namespace commands that don't exist.

### [CONCERN] CLI Python changes are under-specified for a "markdown command file" slice

The slice declares "No Python changes expected" in technical requirements and "This is a markdown command file" under external packages. However, the Implementation Notes section describes meaningful Python work:
- `_resolve_slice_number()` helper in `review.py`
- Number detection and path resolution in `review_arch`, `review_tasks`, `review_code`
- Optional positional arg addition to `review_code`
- Review file auto-save with `--json` and `--no-save` flags
- Unit tests for resolver and number detection

This is legitimate scope for the slice's goals (CLI/slash-command parity, review persistence), but it contradicts the "no Python changes" assertion. The technical requirements section should be reconciled with the implementation notes.

### [PASS] Parity principle aligns with project memory

The slice explicitly states: "CLI (`sq review tasks 118`), slash commands (`/sq:review-tasks 118`), and eventually MCP should produce identical artifacts." This directly aligns with the project memory note (`feedback_interface_parity.md`): "CLI, slash commands, and MCP must produce identical results and artifacts." The design delivers on this principle by ensuring both CLI and slash commands save the same review files with identical frontmatter.

### [PASS] Context-Forge integration is appropriately bounded

The design delegates path resolution to CF (`cf slice list --json`, `cf task list --json`, `cf get`) rather than hardcoding file patterns. This respects CF's ownership of naming conventions and avoids hidden dependencies on directory structure. The design explicitly notes it "does not mutate CF state" during resolution — only `run-slice` uses `cf set` to advance phases, which is the intended CF workflow.

### [PASS] Review gate design is pragmatic and non-over-engineered

The review gate logic (PASS → proceed, CONCERNS → assess severity, FAIL → stop) is a simple heuristic with explicit TODOs acknowledging that smarter loop/signal logic is future work. This avoids over-engineering while being honest about limitations. The single-retry-then-stop pattern prevents infinite loops — a common antipattern in automated review pipelines.

### [PASS] Future work is properly deferred

Smart resume, automated finding resolution, and additional composed commands are all explicitly listed as excluded/deferred. The slice plan's slice 129 (Review Findings Pipeline) is the correct home for automated finding triage. The design doesn't attempt to pull that forward.

### [CONCERN] Review file persistence introduces a cross-cutting convention without architecture-level documentation

The `project-documents/user/reviews/` directory structure and YAML frontmatter schema (`docType: review`, `reviewType`, `verdict`, etc.) are new conventions that will be consumed by future slices (129 — Findings Pipeline, 130 — Ensemble Review). These conventions are well-designed but exist only in this slice document. If this becomes a stable interface, it should be documented at the architecture or slice-plan level so downstream slices can depend on it explicitly rather than reverse-engineering from slice 118's design.

## Raw Output

Let me check the referenced parent slice plan and dependencies.Now I have all the context needed. Let me also check the parity memory note since it's referenced in the project memory.That's just a test review file. I have all the information needed. Here is my architectural review:

---

## Summary
**CONCERNS**

Slice 118 is largely well-aligned with the architecture and slice plan. It stays within its defined scope (CLI interface layer, markdown command files), respects dependency directions, and correctly builds on the completed slice 116 infrastructure. However, there are a few areas where the design diverges from what the slice plan describes, and one area where scope has grown beyond the plan entry in a way that warrants acknowledgment.

## Findings

### [PASS] Layer boundaries respected
The slice operates entirely in the Interface Layer (CLI + Claude Code commands). It does not touch the Core Engine, Agent Provider Layer, or any protocol definitions. The `run-slice.md` command file delegates all orchestration work to existing CLI commands (`sq review tasks`, `sq review code`) and external tooling (`cf`). No new Python business logic leaks into the command layer.

### [PASS] Dependency directions are correct
The slice correctly depends downward:
- **Slice 116 (sq Wrappers)**: provides the `commands/sq/` directory, install mechanism, and wheel bundling — all consumed, not modified.
- **Slice 105 (Review Workflow Templates)**: provides `sq review tasks`, `sq review code`, `sq review arch` — invoked by the composed workflow.
- **Context-Forge CLI**: external dependency consumed via shell commands.

No upward or circular dependencies exist.

### [PASS] Integration points match consuming/providing slices
The slice correctly identifies what it consumes from slices 105 and 116. The review commands it invokes (`sq review tasks`, `sq review code`, `sq review arch`) exist and are documented in slice 105. The `commands/sq/` install mechanism from slice 116 requires no changes — the new file is picked up automatically.

### [CONCERN] Significant scope divergence from slice plan entry
The slice plan entry (item 15, slice 118) describes three composed workflow commands in a `workflow/` namespace:
- `/workflow:next-step` — interprets project state and recommends next action
- `/workflow:design-review` — assembles context then runs arch review
- `/workflow:ensemble-review` — runs reviews across multiple providers and synthesizes results

The actual slice design delivers something substantially different:
- One new command (`/sq:run-slice`) in the `sq/` namespace (not `workflow/`)
- Updates to three existing review commands for number shorthand and review persistence
- CLI number shorthand for `sq review` commands
- Review file persistence with YAML frontmatter

The rationale for the namespace decision is documented and sound (one command doesn't justify a new namespace). The pivot from three theoretical commands to one validated-by-use command is explicitly acknowledged ("deferred until real usage validates need"). However, the `/workflow:ensemble-review` concept (cross-provider review synthesis) is architecturally interesting and maps to slice 130 (Ensemble Review) — its deferral is reasonable but should be noted in the slice plan.

**Impact**: The slice plan entry should be updated to reflect reality. Anyone reading the plan would expect `workflow/` namespace commands that don't exist.

### [CONCERN] CLI Python changes are under-specified for a "markdown command file" slice
The slice declares "No Python changes expected" in technical requirements and "This is a markdown command file" under external packages. However, the Implementation Notes section describes meaningful Python work:
- `_resolve_slice_number()` helper in `review.py`
- Number detection and path resolution in `review_arch`, `review_tasks`, `review_code`
- Optional positional arg addition to `review_code`
- Review file auto-save with `--json` and `--no-save` flags
- Unit tests for resolver and number detection

This is legitimate scope for the slice's goals (CLI/slash-command parity, review persistence), but it contradicts the "no Python changes" assertion. The technical requirements section should be reconciled with the implementation notes.

### [PASS] Parity principle aligns with project memory
The slice explicitly states: "CLI (`sq review tasks 118`), slash commands (`/sq:review-tasks 118`), and eventually MCP should produce identical artifacts." This directly aligns with the project memory note (`feedback_interface_parity.md`): "CLI, slash commands, and MCP must produce identical results and artifacts." The design delivers on this principle by ensuring both CLI and slash commands save the same review files with identical frontmatter.

### [PASS] Context-Forge integration is appropriately bounded
The design delegates path resolution to CF (`cf slice list --json`, `cf task list --json`, `cf get`) rather than hardcoding file patterns. This respects CF's ownership of naming conventions and avoids hidden dependencies on directory structure. The design explicitly notes it "does not mutate CF state" during resolution — only `run-slice` uses `cf set` to advance phases, which is the intended CF workflow.

### [PASS] Review gate design is pragmatic and non-over-engineered
The review gate logic (PASS → proceed, CONCERNS → assess severity, FAIL → stop) is a simple heuristic with explicit TODOs acknowledging that smarter loop/signal logic is future work. This avoids over-engineering while being honest about limitations. The single-retry-then-stop pattern prevents infinite loops — a common antipattern in automated review pipelines.

### [PASS] Future work is properly deferred
Smart resume, automated finding resolution, and additional composed commands are all explicitly listed as excluded/deferred. The slice plan's slice 129 (Review Findings Pipeline) is the correct home for automated finding triage. The design doesn't attempt to pull that forward.

### [CONCERN] Review file persistence introduces a cross-cutting convention without architecture-level documentation
The `project-documents/user/reviews/` directory structure and YAML frontmatter schema (`docType: review`, `reviewType`, `verdict`, etc.) are new conventions that will be consumed by future slices (129 — Findings Pipeline, 130 — Ensemble Review). These conventions are well-designed but exist only in this slice document. If this becomes a stable interface, it should be documented at the architecture or slice-plan level so downstream slices can depend on it explicitly rather than reverse-engineering from slice 118's design.