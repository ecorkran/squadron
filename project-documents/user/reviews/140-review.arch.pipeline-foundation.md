---
docType: review
layer: project
reviewType: arch
slice: pipeline-foundation
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/architecture/140-arch.pipeline-foundation.md
aiModel: minimax/minimax-m2.7
status: complete
dateCreated: 20260327
dateUpdated: 20260327
---

# Review: arch — slice 140

**Verdict:** CONCERNS
**Model:** minimax/minimax-m2.7

## Findings

### [CONCERN] Underspecified `until` condition grammar

category: completeness
The document describes loop conditions as `until: review.pass` but never defines:
- What conditions are valid (only review verdicts, or arbitrary expressions?)
- The syntax for compound conditions (AND/OR?)
- Whether conditions are field references or expressions

Example shows `review.pass` but this could mean "the review action's `pass` field" or "review verdict equals PASS" or something else. A user writing `until: model.timeout` or `until: dispatch.tokens > 1000` would have no guidance.

**Reference:** "check the `until` condition against the step's output"

### [CONCERN] Slice 123 (Review Findings Pipeline) is listed as prerequisite but unclear if complete

category: dependencies
The prerequisites section states "Review Findings Pipeline (123) → moves to 140. Structured finding extraction is foundational for the review action." But the document provides no confirmation that slice 123 is complete or even started.

The convergence loop design (160 preview) explicitly depends on structured findings with identity matching by `(category, location)`. If finding extraction doesn't produce this structure, 160's convergence strategy cannot work as described.

**Reference:** Prerequisites section, "Review Findings Pipeline (123)"

### [CONCERN] ActionContext risks becoming a god object

category: antipattern
The document states ActionContext "carries: pipeline state, resolved parameters, model resolution chain, CF client reference, and output from prior steps." This is five distinct categories of data:

1. Pipeline state (mutable execution context)
2. Resolved parameters (configuration)
3. Model resolution chain (helper/capability)
4. CF client reference (service client)
5. Output from prior steps (artifact storage)

A single object aggregating pipeline state, service clients, configuration, and accumulated artifacts suggests the boundary may be too broad. Consider whether these should be separate injection points: `PipelineState`, `CFClient`, `ModelResolver`, with step outputs accessed via a separate `ArtifactStore` or similar.

**Reference:** "ActionContext carries: pipeline state, resolved parameters, model resolution chain, CF client reference, and output from prior steps"

### [CONCERN] Collection loop CF query result handling unspecified

category: feasibility
The `design-batch` pipeline example queries `cf.unfinished_slices("{plan}")` with no consideration for:
- What happens when the result set is large (100+ unfinished slices)?
- Whether results are streamed or loaded entirely into memory
- Whether pagination exists in the CF query interface

If CF's `unfinished_slices` returns all unfinished slices in one call, and there are many, this could cause memory issues or long delays before iteration begins.

**Reference:** "source: cf.unfinished_slices("{plan}")"

### [CONCERN] Model resolver protocol doesn't specify how provider reaches the dispatch action

category: consistency
The document states the model resolver returns `(provider, model_id)` and "dispatch action...captures output." But the model resolver interface is described as resolving an alias to a concrete model. It doesn't specify what protocol the dispatch action uses to actually invoke the agent.

Does the dispatch action receive `(provider, model_id)` and then call the agent provider registry? Does it receive an already-constructed agent handle? The protocol boundary between model resolver and dispatch action is ambiguous.

**Reference:** "It takes a string (alias or pool: reference) and returns a resolved (provider, model_id) tuple"

### [CONCERN] Findings format decision is deferred but relied upon by validation

category: completeness
The document lists "Review templates exist" as a validation check and states the review action produces "structured findings." But the open question #2 explicitly defers the findings format decision (JSON companion vs. embedded YAML frontmatter vs. structured section).

The validator must check that review templates exist, but if the output format is unknown, the validator cannot verify that the step's template reference will produce parseable structured output. This creates a chicken-and-egg problem: validation depends on output format, output format depends on implementation decisions.

**Reference:** Open Question #2, "Structured findings format"; Validation section

### [CONCERN] No concurrency model defined for future expansion

category: completeness
The document explicitly states "Pipeline executor with sequential step execution" as in-scope and "Cross-slice parallelism (run multiple slices simultaneously)" as out-of-scope. However, the architecture makes no provisions for eventual concurrent execution:

- ActionContext has no thread-safety or async-safety guarantees documented
- State file format has no locking mechanism
- No mention of whether the executor is single-threaded or can run async actions concurrently

If 160 or a future initiative wants parallelism, significant re-architecting may be needed.

**Reference:** "Sequential step execution" in scope; "Cross-slice parallelism" out of scope

### [CONCERN] State file format has no versioning

category: completeness
The state file JSON structure is defined but has no `version` field. If the state file schema evolves (and it will — new fields like `conversation_id` for 160's persistence), there is no migration path. Old state files from interrupted runs would be unparseable or misinterpreted by newer executor versions.

Compare to how the document properly scopes model pools to 160 with syntax acknowledged in 140 — the state file needs the same treatment.

**Reference:** State File JSON example, "run_id", "status", "current_step"...

### [CONCERN] `compact` action responsibility boundary unclear

category: abstraction
The step types section shows `compact` step expands to `compact(instructions from params)` and the action table shows the compact action "owns instruction templates, context preservation rules." But:

- The YAML grammar shows `keep: [design, tasks]` and `summarize: true` as compact step parameters
- It's unclear whether `keep` is evaluated by the step type (which knows the compact semantics) or passed raw to the compact action
- If passed to the compact action, the compact action needs to understand CF structure to know what "design" and "tasks" refer to

This boundary ambiguity could cause tight coupling between compact step type and CF internals.

**Reference:** Step Types section, "compact step type"; YAML grammar example with `keep: [design, tasks]`

### [CONCERN] Step-level vs action-level model specification deferred without criteria

category: completeness
Open question #4 defers YAML grammar choice between nested (`review.model`) and map (`models: { dispatch: opus }`) forms. This affects every pipeline author and every custom pipeline. The document says "choose during grammar finalization with real examples" but provides no criteria for the decision.

This is the most visible user-facing grammar element. Deferring it without explicit acceptance criteria for the choice risks reworking all built-in pipelines after implementation.

**Reference:** Open Question #4; Model Resolution section grammar examples

### [CONCERN] Custom step type error handling not addressed

category: completeness
The document describes custom step types as "following the same pattern: a step type is a named expansion into an action sequence." But error handling for custom step types is never discussed:

- If a custom step type raises an exception, what happens?
- Can custom step types define their own checkpoint triggers?
- What validation does a custom step type go through?

Users writing custom step types need this guidance.

**Reference:** "Custom step types can be registered, following the same pattern"; "Custom pipelines"

### [CONCERN] Dry-run scope unclear

category: completeness
`sq run --dry-run` is listed in command surface and `--dry-run — show what would execute without running` is in the options list. But:
- Does dry-run validate the pipeline definition?
- Does dry-run call CF to resolve structure-derived paths?
- Does dry-run resolve model aliases?
- Does dry-run expand step types to show the action sequence?

Without this clarity, users won't know what to expect from `--dry-run`.

**Reference:** Command Surface section, "Common options"

### [CONCERN] Devlog action vs devlog step distinction needs clarification

category: abstraction
The `devlog` step type expands to `devlog(auto-generate from pipeline state)` but the action table shows the devlog action "owns entry templates, phase/slice metadata." The relationship between "auto-generate" and "entry templates" is unclear:

- Does the step type decide what to log, and the action handles formatting?
- Or does the action decide what to log based on templates?
- Can a user provide explicit log content vs. auto-generate?

The "auto" keyword in the YAML suggests a mode, but the boundary between step type policy and action implementation isn't defined.

**Reference:** Step Types section; Action table for devlog; YAML grammar example `devlog: auto`

### [CONCERN] CF connection model deferred but affects action design

category: feasibility
Open question #3 defers the CF connection model (CLI vs MCP client). The document states "Start with CLI, migrate when HTTP transport is available in CF." But this affects:

- Whether CF operations are synchronous (CLI subprocess) or async
- Whether the ActionContext's CF client reference is a sync or async interface
- Error handling differences between CLI (exit codes) and HTTP (status codes)

If the CLI interface is synchronous but the executor is async (as suggested by `async def execute` in the Action protocol), there may be blocking issues. The async Action protocol with sync CLI calls needs explicit treatment.

**Reference:** Open Question #3; Action protocol `async def execute`; CF connection model
