---
docType: slice-plan
parent: 140-arch.pipeline-foundation.md
project: squadron
dateCreated: 20260327
dateUpdated: 20260405
status: in_progress
---

# Slice Plan: Pipeline Foundation

## Parent Document
`140-arch.pipeline-foundation.md` — Architecture: Pipeline Foundation

---

## Foundation Work

1. [x] **(140) Command Surface Parity** — Rename slash commands to match CLI subcommand structure: `/sq:review-code` → `/sq:review code`, `/sq:review-slice` → `/sq:review slice`, `/sq:review-tasks` → `/sq:review tasks`, `/sq:auth-status` → `/sq:auth status`. Add `/sq:run` slash command. Add `sq review arch` command and `/sq:review arch` slash command for architecture reviews (template/prompt driven, same pattern as existing review types — `arch.yaml` template in `builtin/`). Retire `/sq:run-slice` (superseded by `sq run`). Dependencies: [100-band complete]. Risk: Low. Effort: 1/5

2. [x] **(141) Configuration Externalization** — Consolidate all shipped data files into `src/squadron/data/`: model aliases (TOML, moved from Python dict in `aliases.py`), review templates (YAML, moved from `review/templates/builtin/`), and pipeline definitions (YAML, new in later slices). Built-in and user override files use identical formats — users can copy blocks between shipped defaults and their `~/.config/squadron/` overrides. Runtime loads from `data/` first, then layers user config on top (existing merge behavior preserved). "All defaults live in `squadron/data/`" becomes the single answer for where to find shipped configuration. Dependencies: [100-band complete]. Risk: Low. Effort: 2/5

3. [x] **(142) Pipeline Core Models and Action Protocol** — Pydantic models for pipeline infrastructure (PipelineDefinition, StepConfig, ActionContext, ActionResult). Action protocol and action registry. StepType protocol and step type registry. Model resolver with cascade chain (5 levels: CLI override, action, step, pipeline, system config). Package scaffolding for `src/squadron/pipeline/` matching the architecture's package structure. Pool prefix (`pool:`) acknowledged in resolver interface but not implemented (160 scope). Dependencies: [100-band complete]. Risk: Low. Effort: 2/5

---

## Migration Work

4. [x] **(143) Structured Review Findings** — Extract structured findings from review output as typed data: id, severity, category, summary, location. Single-file format: structured findings index in YAML frontmatter, full prose descriptions in the markdown body. Absorbs the scope of former 100-band slice 123 (Review Findings Pipeline), refocused for pipeline consumption. Finding schema designed with 160's cross-iteration identity matching in mind (category + location fingerprint). Standalone value before pipelines exist: `sq review` commands gain machine-readable structured output in frontmatter. Dependencies: [142, Review System (105/128)]. Risk: Medium (finding extraction parsing heuristics). Effort: 3/5

---

## Feature Slices

5. [x] **(144) Utility Actions** — Implement three simple actions that validate the action protocol against well-defined operations: cf-op action (set phase, build context, summarize via ContextForgeClient), commit action (git commit at phase boundaries with semantic message conventions), and devlog action (structured DEVLOG entries auto-generated from pipeline state). Dependencies: [142, CF Integration (126)]. Risk: Low. Effort: 2/5

6. [x] **(145) Dispatch Action** — Send assembled context to a model via agent registry, capture output (file artifacts or code changes), record metadata (model used, token counts). Integrates with model resolver for alias resolution through the cascade chain. Handles both SDK and API provider dispatch transparently through the AgentProvider protocol. Dependencies: [142, Agent Registry (102)]. Risk: Low. Effort: 2/5

7. [x] **(146) Review and Checkpoint Actions** — Review action: run a review template against an artifact within a pipeline step, consume structured findings from slice 143, produce verdict and structured finding set, handle review file persistence. Checkpoint action: pause pipeline execution for human decision, serialize pipeline state for resume, present findings and status summary, accept human input (approve, revise, skip, abort, override model/config for subsequent steps). Checkpoint triggers: always, on-concerns, on-fail, never. Dependencies: [143, 145]. Risk: Medium (checkpoint interactive UX). Effort: 3/5

8. [x] **(147) Compact Action and Step Types** — Compact action: issue parameterized compaction instructions via CF with configurable context preservation rules. Step type implementations: phase step (expands to cf-op → dispatch → review → checkpoint → commit action sequence), compact step, standalone review step, devlog step. Each step type is a named expansion into an action sequence, bridging the terse YAML grammar and the action layer. Dependencies: [144, 145, 146]. Risk: Low. Effort: 3/5

9. [x] **(148) Pipeline Definitions and Loader** — YAML pipeline definition grammar with params, model defaults, and step configurations. Definition loader with schema validation. Built-in pipeline definitions: slice-lifecycle (full design → tasks → implementation), review-only (quality gates on existing artifacts), implementation-only (when design and tasks exist), design-batch (phase 4 across unfinished slices). Custom pipeline discovery from project directory and user config directory. `sq run --validate` for pre-execution validation that calls each action's `validate()` method. Dependencies: [147]. Risk: Low. Effort: 2/5

10. [x] **(149) Pipeline Executor and Loops** — Step sequencer that expands step types into action sequences and executes them in order. Basic loops: fixed iteration with max count and until condition evaluated against step output. Collection loops: `each` construct that iterates over items from a typed query source (initially CF queries for unfinished slices, extensible). Convergence loop syntax: `loop.strategy` field parsed and acknowledged, but execution falls back to basic max-iteration behavior (convergence strategies are 160 scope). **Design decisions required:** (1) collection loop item binding semantics — how `{slice.index}` resolves inside an `each` block (item type/schema from CF query, field traversal syntax, missing field behavior, read-only binding); (2) loop condition grammar — what `until: review.pass` means (field path into ActionResult? named property? formal expression syntax?), how the validator checks conditions, and how the executor evaluates them. See OQ5 and loop condition finding in `140-arch.pipeline-foundation.md`. Dependencies: [147, 148]. Risk: Medium (loop semantics, collection variable binding). Effort: 3/5

11. [x] **(150) Pipeline State and Resume** — State file persistence as JSON in `~/.config/squadron/runs/`. State captures completed steps with outputs, current step, checkpoint reason, review verdicts, and pipeline params. Resume from checkpoint or interruption via `sq run --resume <run-id>`. Mid-process adoption via `--from <step>` for starting at a specific step. Implicit resume detection when an existing run matches the same pipeline and params. Old run pruning. Dependencies: [149]. Risk: Low. Effort: 2/5

12. [x] **(151) CLI Integration and End-to-End Validation** — `sq run` Typer command surface: run a pipeline by name or path, `--resume`, `--status`, `--list`, `--validate`, `--dry-run`, `--slice`, `--model`, `--from`. Wire executor, state manager, and pipeline loader into the CLI presentation layer. Integration testing of built-in pipelines against a real CF project structure. Completes the initiative: `sq run slice-lifecycle --slice 191` is a working replacement for the markdown-based `/sq:run-slice`. Dependencies: [148, 149, 150]. Risk: Low. Effort: 2/5

13. [x] **(153) Prompt-Only Pipeline Executor** — Add `--prompt-only --next` mode to `sq run` CLI that outputs one step's instructions at a time without dispatching to an LLM. Each call returns the next step's structured instructions (CF commands, model to switch to, review command with template/model from YAML, compact instructions with resolved params, checkpoint decisions). Pipeline executor tracks state across calls. Update `/sq:run` slash command to consume executor output instead of reimplementing YAML interpretation — slash command becomes a thin loop: call `sq run --prompt-only --next`, execute instructions, repeat. Sequential steps only. Dependencies: [151]. Risk: Low. Effort: 3/5

14. [x] **(154) Prompt-Only Loops** — Extend prompt-only mode with `each`/collection loop support (executor returns successive iteration instructions via `--next`, caller doesn't need to know it's a loop). Enables design-batch pipelines in prompt-only mode. Model switching is informational only in prompt-only mode — `/model` commands cannot be automated from within Claude Code sessions (IDE or CLI). The `model_switch` field remains in step instructions for user reference. Automated model switching requires the SDK executor (slice 155). Dependencies: [153]. Risk: Low. Effort: 2/5. **✓ Design Complete: [154-slice.prompt-only-loops.md](user/slices/154-slice.prompt-only-loops.md)**

15. [x] **(155) SDK Pipeline Executor** — Full pipeline automation via `ClaudeSDKClient`. Dispatch steps spawn a persistent SDK session that executes work autonomously with tool use (file I/O, commands, web search). Per-step model switching via `client.set_model(model)`. Server-side context compaction via the `context_management` API (`compact_20260112` beta) with pipeline-defined `instructions` from compact templates and configurable `trigger` thresholds. Reviews execute normally (SDK can spawn subprocesses). Checkpoints pause and optionally notify. Runs outside Claude Code sessions only (`sq run slice 154` from straight CLI). This is the fully automated path — prompt-only mode (slices 153-154) remains the interactive bridge for IDE and Claude Code CLI sessions. Dependencies: [154]. Risk: Medium (SDK API stability, compaction beta). Effort: 3/5

16. [x] **(156) Pipeline Executor Hardening** — Fix resume-with-correct-mode: add `execution_mode` enum field to `RunState` (schema v2) so resume always uses the same runner as the original run — no hardcoded mode-name strings, dispatch via enum match. Fix implicit resume and `--resume` paths to both honour the stored mode. Normalize pipeline names to lowercase at load time and CLI input boundary (case-insensitive lookup and state matching). Dependencies: [155]. Risk: Low. Effort: 2/5

17. [ ] **(157) SDK Session Management and Compaction** — Controlled context compaction at pipeline step boundaries via session rotate: disconnect SDK session after compact step, construct summary prompt from compact template instructions and accumulated pipeline state/step outputs, reconnect with fresh context. Replaces the unconnected `configure_compaction()` stub from slice 155. Wire the Agent SDK `PreCompact` hook for best-effort instruction injection during auto-compaction within long individual steps. Add optional `model` field to compact step YAML for cheaper summarization. The Agent SDK (`ClaudeSDKClient`) does not expose `context_management` or `compaction_control` — session rotate is the only path to deterministic, step-boundary compaction. Dependencies: [155, 156]. Risk: Medium (session lifecycle edge cases, state continuity across reconnects, summary quality). Effort: 3/5

---

## Integration Work

16. [ ] **(152) Pipeline Documentation and Authoring Guide** — Pipeline authoring documentation: YAML grammar reference, action type catalog, step type catalog, model resolution rules and cascade precedence, built-in pipeline descriptions with annotated examples. Configuration surface guide: where built-in defaults live (shipped TOML and YAML), where user overrides live, how layering works. Example custom pipeline definition. README updates for `sq run`. Dependencies: [all prior slices]. Risk: Low. Effort: 1/5

---

## Implementation Order

```
Foundation:
  140. Command Surface Parity                          (can start immediately)
  141. Configuration Externalization                    (can start immediately, parallel with 140)
  142. Pipeline Core Models & Action Protocol           (can start immediately, parallel with 140-141)

Migration:
  143. Structured Review Findings                      (after 142)

Feature Slices:
  144. Utility Actions                                 (after 142, parallel with 143)
  145. Dispatch Action                                 (after 142, parallel with 143-144)
  146. Review and Checkpoint Actions                    (after 143, 145)
  147. Compact Action and Step Types                    (after 144, 145, 146)
  148. Pipeline Definitions and Loader                  (after 147)
  149. Pipeline Executor and Loops                      (after 147, 148)
  150. Pipeline State and Resume                        (after 149)
  151. CLI Integration and End-to-End Validation        (after 148, 149, 150)

Feature:
  153. Prompt-Only Pipeline Executor                     (after 151)
  154. Prompt-Only Loops                                  (after 153)
  155. SDK Pipeline Executor                              (after 154) ✓ complete
  156. Pipeline Executor Hardening                        (after 155) ✓ complete
  157. SDK Session Management and Compaction              (after 155, 156)

Integration:
  152. Pipeline Documentation and Authoring Guide       (after all prior)
```

### Parallelization Notes

- **Slices 140, 141, and 142 are fully independent** and can proceed in parallel. 140 and 141 touch existing code (commands, aliases); 142 is greenfield pipeline scaffolding.
- **Slices 143, 144, and 145 can proceed in parallel** after 142 is complete. All three depend only on the pipeline core models.
- **Slice 146 (Review and Checkpoint) is the convergence point** — it needs structured findings (143) and dispatch (145) before it can integrate.
- **Slices 148-150 are sequential** — each builds on the prior. No useful parallelization within this chain.

---

## Future Work

1. [FUTURE] **`sq run phase` Subcommand** — Single-phase pipeline execution: `sq run phase implement --slice 191 --model sonnet`. Resolves the earlier `sq phase` convenience command question — it becomes a subcommand of `sq run` rather than a top-level command. Absorbed CF commands (`sq run phase`) also route here. Dependencies: [151]. Effort: 1/5

2. [FUTURE] **Pipeline Notifications** — Notify human when a long-running pipeline hits a checkpoint (email, webhook, desktop notification). CLI-first checkpoints assume the human is at the terminal. Dependencies: [150]. Effort: 2/5

3. [FUTURE] **Multiple Positional Target Arguments** — Support additional positional args or `key=value` positional syntax for pipelines with multiple required params (e.g. `sq run review-only 123 template=arch` or `sq run review-only 123 arch`). Currently only the first required param is bound to the positional target; additional required params need `--param key=value`. Dependencies: [151]. Effort: 1/5

4. [FUTURE] **Context Forge as Agent Tools** — Expose CF commands as tools available to non-SDK agents during dispatch. Migrated from 100-band future work. Dependencies: [144, 180-series MCP Server]. Effort: 2/5

5. [FUTURE] **Run State Lifecycle Management** — Prune unreadable/schema-obsolete state files that the current `prune()` skips (schema version mismatches, corrupt JSON); expose as `sq run --gc` or automatic cleanup on `init_run`. Add global TTL (e.g. 30-day max age) and optional total-file cap across all pipeline names to prevent unbounded growth when many distinct pipelines have been run. Dependencies: [150, 156]. Effort: 1/5

---

## Notes

- **Slice 123 (Review Findings Pipeline) absorbed into slice 143.** The original 100-band scope (automated triage, auto-fix routing, design decision surfacing) is narrowed to structured finding extraction — the foundational piece. Automated routing/triage is deferred as it depends on the pipeline executor being operational.
- **Slice 125 (Conversation Persistence) belongs in initiative 160 (Pipeline Intelligence)**, not here. The 140 architecture explicitly states pipeline steps are stateless in this initiative. Conversation persistence across retries is a 160 capability.
- **Convergence loop strategies are 160 scope.** Slice 149 parses the `loop.strategy` YAML field and applies basic max-iteration fallback. Strategy registration and weighted-decay execution are 160 deliverables that plug into 149's extension point.
- **Model pools are 160 scope.** The model resolver in slice 142 recognizes the `pool:` prefix but raises a clear error ("model pools require Pipeline Intelligence initiative"). Pool resolution logic is a 160 deliverable.
- **This initiative supersedes `/sq:run-slice` (slice 118).** The markdown command is retired in slice 140; `sq run slice-lifecycle` is the primary path forward.
- **CF command absorption planned as `sq run phase`.** Some Context Forge commands will be absorbed as squadron subcommands. These route through `sq run` rather than adding top-level commands, keeping the command surface compact. Details deferred to the relevant slice design.
- **All shipped defaults centralized in `src/squadron/data/`.** TOML for model aliases, YAML for review templates and pipeline definitions. User overrides at `~/.config/squadron/` use identical formats. Users can copy blocks between shipped defaults and their overrides directly.
