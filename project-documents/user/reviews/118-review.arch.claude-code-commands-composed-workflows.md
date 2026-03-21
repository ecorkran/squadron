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

### [CONCERN] Significant scope divergence from slice plan entry

The slice plan (100-slices.orchestration-v2.md, line 65) describes slice 118 as delivering:
- A **`commands/workflow/`** namespace (not `commands/sq/`)
- **`/workflow:next-step`** — runs `cf status + cf next`, interprets project state
- **`/workflow:design-review`** — runs `cf build` then `sq review arch`
- **`/workflow:ensemble-review`** — runs the same review across multiple providers and synthesizes results

The actual slice design delivers:
- Commands in the **`commands/sq/`** namespace (staying in existing namespace)
- **`/sq:run-slice`** — a full phase 4→5→6 lifecycle automation command
- **Updates to existing review commands** with number shorthand and review file persistence
- **CLI number shorthand** for `sq review` commands

None of the three originally planned commands (`next-step`, `design-review`, `ensemble-review`) appear in the design. The design acknowledges the namespace decision explicitly (section "Namespace: `/sq:run-slice`") and gives reasonable justification ("one command doesn't justify a new namespace"), but the slice plan entry should be updated to reflect the actual scope — especially since the slice plan shows `[x]` (complete) for this item.

The `ensemble-review` command from the plan (which maps conceptually to slice 130 — Ensemble Review & Cross-Model Analysis) being dropped is particularly notable. The plan said this was "a lightweight ensemble pattern that works before the message bus exists" — a deliberate pre-M2 capability. The design's "Excluded" section doesn't mention it, so the rationale for dropping it is undocumented.

### [CONCERN] Review file persistence scope pull-forward

Slice 105 (Review Workflow Templates) explicitly lists "Review Result Persistence" as a Tracked Enhancement:

> *"Save ReviewResult to a conventional location (e.g., reviews/ directory) after each review. Enables tracking review history..."*

The 118 design now implements this enhancement — review files saved to `project-documents/user/reviews/` with YAML frontmatter, overwrite semantics, and commit-at-gate behavior. This is reasonable and well-designed, but it's scope that was explicitly deferred from 105 and is now absorbed into 118 without noting that it fulfills that tracked enhancement. The design should acknowledge this provenance so the tracked enhancement in 105 can be marked as addressed.

Additionally, the review file format in 118 (YAML frontmatter + markdown body) diverges slightly from what 105's `ReviewResult.to_dict()` would produce (JSON). The `--json` flag on the CLI (line 175) addresses this for programmatic consumers, but there's a subtle format gap: the slash commands produce YAML-frontmatter markdown files, while `ReviewResult.to_dict()` produces JSON. The parity principle ("CLI, slash commands, and MCP must produce identical artifacts" — per both the design and the project memory) should clarify which format is canonical and ensure both paths produce the same output.

### [PASS] Correct architectural layer placement

The design operates entirely within the Interface Layer (CLI commands + Claude Code markdown command files). It does not modify the Core Engine, Agent Provider Layer, or any architectural boundaries. The `run-slice` command orchestrates existing CLI tools (`sq`, `cf`) via Claude Code's reasoning — this is appropriate for the Interface Layer's role as defined in the architecture.

### [PASS] Dependency directions are correct

- Depends on slice 116 (sq Wrappers) for `commands/sq/` infrastructure → correct, 116 is complete
- Depends on slice 105 (Review Workflow Templates) for `sq review` commands → correct, 105 is complete
- Depends on Context-Forge CLI (external) → documented in architecture as a future integration point (line 265: "Context Forge (future) — Context assembly for agent instructions")
- No reverse dependencies or circular references

### [PASS] Integration points are well-defined and minimal

The design correctly identifies what it provides (automation pattern for future composed commands) and what it consumes (sq wrappers, review workflow templates, context-forge). The `run-slice` command composes existing capabilities rather than introducing new abstractions, which is appropriate for a composed workflow command.

### [PASS] CLI/slash command parity principle

The design explicitly addresses the parity principle from project memory (`feedback_interface_parity.md`). The CLI number shorthand (`sq review tasks 221`) mirrors the slash command shorthand (`/sq:review-tasks 221`), and both produce the same review file artifacts. The `_resolve_slice_number()` helper is shared logic. This is well-considered.

### [PASS] No hidden dependencies on unbuilt components

The command relies only on completed slices (105, 116, 117) and the external Context-Forge CLI. It does not depend on the message bus (M2), daemon (already complete), or any future slice. The `run-slice` pipeline is self-contained within existing capabilities.

### [CONCERN] Duplicate line in Excluded section

Line 39 and line 40 are identical: "Automated resolution of review findings (TODOs in design for future iteration)". Minor copy-paste error.

### [PASS] Appropriate use of Claude Code reasoning

The design correctly leverages Claude Code's reasoning capability for review gate decisions (PASS → proceed, CONCERNS → assess severity, FAIL → stop) rather than building complex decision logic in code. This is appropriate for a markdown command file — the "logic" is in the prompt, not in Python code. The TODOs acknowledging that smarter loop/signal logic is future work show healthy scope awareness.
