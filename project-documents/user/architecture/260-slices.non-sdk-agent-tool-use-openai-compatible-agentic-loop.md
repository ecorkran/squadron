---
docType: slice-plan
parent: 260-arch.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md
project: squadron
dateCreated: 20260505
dateUpdated: 20260825
status: not_started
---

# Slice Plan: Non-SDK Agent Tool Use (OpenAI-Compatible Agentic Loop)

## Parent Document
`260-arch.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md` — Architecture: Non-SDK Agent Tool Use (OpenAI-Compatible Agentic Loop)

---

## Overview

This initiative adds tool-calling capability to the `OpenAICompatibleAgent` so non-SDK providers (openrouter, openai, local, gemini) can run pipeline actions that require file I/O. Today the agent is text-in/text-out only — capable models like Kimi-K2.5 emit raw tool-call XML into the response stream because no `tools` parameter is sent and no execution loop exists. The work splits along three natural axes:

1. **Tool foundation** (one slice) — descriptor protocol, registry, and core tool implementations (`read_file`, `write_file`, `bash`). Pure data + pure callables; testable in isolation; no agent or executor changes. Establishes the abstraction boundary for everything else.

2. **Agentic loop** (one slice) — `_run_agentic_loop` inside `OpenAICompatibleAgent.handle_message`. Materializes tools from the registry per-dispatch, drives the OpenAI tool-call protocol (multi-turn message history, tool execution, max-iterations guard, token-budget threshold), and surfaces only the final turn through the existing message-yield interface. Self-contained behind the agent interface; the executor sees no change.

3. **Pipeline wiring and end-to-end demo** (one slice) — `dispatch` action threads `allowed_tools` from step YAML to `AgentConfig.allowed_tools`. Pipeline schema validates the field. Demonstrates `test-p4.yaml` running to completion with `model: kimi25` and explicit `allowed_tools`.

4. **Review coverage** (one slice; promoted into initiative scope 20260824) — activates `allowed_tools` on the review path: the standalone review client (`run_review_with_profile`) plus the pipeline `review`/`summary` actions, with a read-only tool subset and injection-skip logic (tools enabled → inject diff only; the model reads files on demand). Closes issue #68 (review `allowed_tools` silently ignored by non-SDK providers). Ships read-only `list_files`/`grep` tools for parity with the SDK reviewer's Read+Glob+Grep, migrates template `allowed_tools` to canonical squadron vocabulary (SDK translates at the config edge), and records tools-enabled + tool-call count in review persistence.

5. **Tool-use configuration** (one slice, small) — per-alias `tool_use` capability field in models.toml (may this model be offered tools at all; default true) and a run-level `--no-tools` flag on `sq review` for baseline-vs-tools comparison runs.

One follow-on slice remains tracked as deferred work:

6. **Context-forge MCP tool bridge** — adapter exposing CF MCP operations through the same descriptor protocol. Composes as an adapter because the descriptor protocol is async-first.

The core slices land independently (each leaves the system in a working state) but build on each other: 261 ships tools that no agent yet uses; 262 wires those tools into the agent but no pipeline yet declares them; 263 closes the loop by exposing the YAML surface and proving the end-to-end flow; 265 extends the same plumbing to reviews and can land before or after 263 (both depend only on 262 — ordering is a scheduling call).

---

## Foundation Work

This initiative has no separate foundation phase — slice 261 is itself the foundation slice (descriptor protocol + registry + core tools). It is listed under Feature Slices to keep the sequencing clear.

---

## Feature Slices (in implementation order)

1. [ ] **(261) Tool Registry, Descriptor Protocol, and Core Tool Implementations** — Establish the tool abstraction boundary for the rest of the initiative. Define the `ToolDescriptor` protocol (name, description, JSON Schema `parameters` matching OpenAI's `tools[].function.parameters` shape, factory callable). Define `ToolResult(content: str, is_error: bool)`. Implement the process-level tool registry with `register(descriptor)`, `lookup(name) -> ToolDescriptor | None`, and `materialize(names: list[str], cwd: str) -> dict[name, async_executor]` (the materialize call invokes each descriptor's factory with `cwd` once per dispatch and returns the closure-bound async executors). Ship three core tools registered at module import time: `read_file`, `write_file` (both CWD-scoped, path-escape rejected via `pathlib.Path.resolve(strict=False).is_relative_to(cwd_resolved)`), and `bash` (runs with `cwd` as working directory; network/env/fork unrestricted at this stage — documented scope). Each tool's executor is `async def execute(args: dict[str, object]) -> ToolResult`; sync work wraps in `asyncio.to_thread` where needed. No `OpenAICompatibleAgent` or `AgentConfig` changes; nothing in the executor changes. Tests assert: descriptors register correctly, registry lookups return `None` for unknown names, materialized executors enforce CWD scope (path-escape attempts return `is_error=True` with a clear message), each tool's happy path produces the expected content. Dependencies: [100, 140]. Risk: Low. Effort: 2/5. Design: `261-slice.tool-registry-descriptor-protocol-and-core-tool-implementations.md`

2. [ ] **(262) OpenAICompatibleAgent Agentic Loop** — Reuse the existing `AgentConfig.allowed_tools` field with non-SDK semantics (the SDK path already consumes it; non-SDK currently ignores it — this slice activates the non-SDK consumer). Inside `OpenAICompatibleAgent.handle_message`, replace the single API round-trip with `_run_agentic_loop`: materialize tool executors from the registry for the names in `config.allowed_tools`; on each iteration call `chat.completions.create(model=..., messages=history, tools=schemas, stream=True)`; aggregate streaming `tool_calls` deltas via the existing `_consume_stream` mechanism; if the assembled assistant message has `tool_calls`, append it verbatim to history (per OpenAI protocol — `content` and `tool_calls` co-occur), execute each call (parse JSON args, lookup, validate, dispatch to async executor, build `role: "tool"` message with matching `tool_call_id`), append all tool results to history, and re-invoke. Terminate when the assistant message has no `tool_calls` (yield final `content` as the response) OR when `max_iterations` is reached (default ~20; configurable; raises a structured error surfaced through the agent's normal failure path) OR when accumulated history exceeds the configured character-count threshold (return a budget-exceeded `role: "tool"` message back to the model so it can finalize). Streaming contract: intermediate turns logged at DEBUG only (caller does not see them); only the final turn streams through the existing message-yield interface. Tool-call argument parse failures and unknown-tool responses surface as `is_error=True` tool-result messages back to the model, not loop crashes. History is append-only across iterations — earlier entries are never mutated (no injected timestamps, no re-rendered content) so each request stays a strict prefix-extension of the previous one and provider-side automatic prefix caching keeps discounting the repeated prefix (see arch §Cache-friendly history). Tests: tool-call detection drives loop continuation; absent tool-calls terminate; max-iterations guard fires with a structured error; unknown-tool name returns error to model; malformed JSON args return error to model; multi-tool single-turn dispatches all tools and appends all results in order; final turn's content is yielded; intermediate turns are NOT yielded. Dependencies: [261]. Risk: Medium (multi-turn streaming + tool-call protocol fidelity, message-history shape, error surface). Effort: 3/5

3. [ ] **(263) Dispatch Action Wiring and Pipeline YAML Surface** — Thread `allowed_tools` from step YAML through to `AgentConfig.allowed_tools`. Pipeline schema (`pipeline/schema.py`) gains a per-step optional `allowed_tools: list[str] | None` field validated against the tool registry (unknown names raise `pydantic.ValidationError` at load time, matching the slice 245 `auth_policy` pattern). `DispatchAction._dispatch_via_agent` reads the field from `context.params` (or `step.config`, whichever is the established pipeline-config path for this kind of metadata — confirm during slice design) and populates `AgentConfig.allowed_tools` when constructing the agent config. SDK path is unaffected (the field there continues to mean Claude Code tool names; non-SDK semantics are squadron-registry tool names). End-to-end demo: update `src/squadron/data/pipelines/test-p4.yaml` to declare `allowed_tools: [read_file, write_file]` on its design step; run `sq run test-p4 <slice>` with a non-SDK pipeline model (e.g. `kimi25`) and confirm the slice-design file is actually written and the subsequent review step finds its input. Tests: schema accepts a valid tool list, rejects an unknown tool name, defaults to no tools when absent; dispatch passes `allowed_tools` into `AgentConfig`; integration test runs a small pipeline against a mocked OpenAI-compatible endpoint that returns a tool call and verifies the file is written and the final response captures the model's confirmation. Dependencies: [262]. Risk: Low. Effort: 2/5

4. [ ] **(264) Context-Forge MCP Tool Bridge** *(separate slice; tracked here for sequencing)* — Adapter that exposes selected context-forge MCP operations (e.g. `set_phase`, `set_slice`, `build_context`, `prompt_get`) through the slice-261 descriptor protocol. Each MCP operation is wrapped in a descriptor whose factory creates an async executor that calls the MCP client. The async-first execute interface from slice 261 makes this an adapter rather than a re-architecture. Pipelines can then declare `allowed_tools: [read_file, write_file, cf_set_phase, cf_build_context]` and capable non-SDK models can drive context-forge state directly. Out of scope: dynamic discovery of CF MCP tools (initial implementation registers a curated subset by name); other MCP servers (the bridge pattern can extend, but only CF in this slice). Dependencies: [261, 262]. Risk: Low. Effort: 2/5

5. [ ] **(265) Review Coverage — Standalone Client and Pipeline Actions** *(promoted into initiative scope 20260824)* — Activate `allowed_tools` on the review path. The standalone review client (`run_review_with_profile`) already passes `template.allowed_tools` into `AgentConfig`; slice 262's loop makes non-SDK providers honor it, closing issue #68 (silently ignored today). This slice adds the injection decision: when the provider supports tool use and the template allows tools, skip full-file injection (`_inject_file_contents`) while still injecting the diff — the diff anchors the review and supplies the paths the model may then read on demand; with no tools allowed, injection behavior is unchanged. Requires a capability signal (e.g. `supports_tool_use` on `ProviderCapabilities`, or `can_read_files` made config-dependent — decided in slice design; the flag must not encode provider identity). Applies the same `allowed_tools` plumbing to the pipeline `review` and `summary` actions. Reviews use a read-only tool subset: `read_file`, `list_files`, `grep` — no `write_file`, no `bash`. The read-only search tools ship in this slice (registered via 261's registry; 261's scope is unchanged) — resolved 20260825: `read_file` alone limits the reviewer to paths the diff names, a parity disadvantage against the SDK reviewer's Read+Glob+Grep. Two further work items: (a) migrate shipped template `allowed_tools` declarations from Claude Code vocabulary (`[Read, Glob, Grep, Bash]`) to canonical squadron names, with a single mapping table translating canonical → Claude names at the SDK config-build edge (SDK agent internals unchanged; unknown canonical names are a load-time validation error, never a silent skip); (b) review persistence records tools-enabled and tool-call count, so later baseline-vs-tools comparison runs are distinguishable in stored results. Tests assert: a review with `allowed_tools: [read_file]` against a mocked endpoint reads a referenced file mid-review and the parsed result is unchanged in shape; a tool-enabled review's prompt omits injected file bodies but retains the diff; a no-tools review injects files exactly as today. Dependencies: [262] (263 not required — the standalone client path does not route through pipeline YAML; pipeline review/summary wiring within this slice follows 263's established pattern). Risk: Low. Effort: 2/5

6. [ ] **(266) Tool-Use Configuration** — Two orthogonal knobs, added after review coverage proves the loop. **models.toml capability field:** aliases gain optional `tool_use = true|false` (default true) meaning "may this model be offered tools at all" — a model property guarding models with broken tool-calling; parsed alongside the existing alias fields (profile, model, cost_tier, pricing). **Run-level override:** `sq review` gains `--no-tools`, emptying the effective tool set for one run. Effective tools = `template.allowed_tools` ∩ model capability, emptied by `--no-tools`. The flag — not a second models.toml alias — is the comparison mechanism, because persistence records the resolved model and two aliases of the same model would be indistinguishable in stored results. Comparison workflow this enables: run N reviews with `--no-tools` (baseline), re-run with tools, compare via the recorded tools-enabled field from 265. Tests: alias with `tool_use = false` never receives schemas even when the template allows tools; `--no-tools` yields an empty effective set and the run is recorded as tools-disabled; default path (field absent, no flag) passes template tools through unchanged. Dependencies: [265]. Risk: Low. Effort: 1/5

---

## Slice Sequencing Notes

- **261 → 262 → 263** is the critical path. Each slice leaves the system in a working state: after 261, tools exist but no agent uses them (no behavior change in the running system); after 262, the agent uses tools when given them but no pipeline declares them (still no behavior change in default pipelines); after 263, pipelines can declare `allowed_tools` and the end-to-end demo works.
- **264 (CF MCP)** can land any time after 261. It does not block 262 or 263 and is independently valuable. Whether it ships in the initial push or after 263 is a scheduling call.
- **265 (review coverage)** is in scope, not optional (promoted 20260824 — reviewer file-access is a primary motivation for the initiative, alongside dispatch). It depends only on 262; whether it lands before or after 263 is a scheduling call.
- **266 (tool-use configuration)** follows 265 — it configures behavior 265 makes real, and its comparison workflow needs 265's tools-enabled persistence field.
- Slice 261 is small enough that a foundation/feature split would add overhead without value — it is listed in Feature Slices.

---

## Cross-Initiative Coordination

- **240 (Pipeline Auth-Boundary Flexibility):** No coordination needed at runtime. The agentic-loop changes are downstream of the dispatch routing decision in 240 (`_dispatch_via_agent` is called only after the profile-aware router has decided not to use the SDK session). 240's lazy/strict policy and pre-scan are unaffected. The 240 dependency is scoped to slice 263 (dispatch wiring); slices 261, 262, and 265 do not require 240 — the standalone review client already resolves profiles without it.
- **140 (Pipeline Foundation):** This initiative extends `AgentConfig` (semantic activation of `allowed_tools` for non-SDK) and the dispatch action wiring. No changes to the action protocol, executor, or step-type registry.
- **180 (Pipeline Intelligence):** No coordination — orthogonal concern.
- **Future orchestration initiative (tentatively planned):** The `_run_agentic_loop` extraction in slice 262 is the seam for future lift to a higher orchestration layer. No cross-initiative dependency yet, but the structure is intentional.

---

## Out of Scope

- **Sandboxing depth for `bash`** beyond CWD restriction (env scrubbing, network deny, pid-namespace isolation). Tracked as future work; documented in arch §Bash scope.
- **Automatic message-history truncation/summarization** when the token budget is approached. The initial implementation returns a budget-exceeded error to the model so it can finalize; truncation is deferred.
- **Streaming intermediate tool-call turns to the executor.** Final turn only at this stage; future orchestration may lift the loop boundary.
- **Tool-use for the SDK path.** The Claude SDK already has full tool support via `claude_code` preset and `bypassPermissions` — that path is not modified.
- **Codex provider tool support.** Codex has its own internal agentic handling; out of scope here.
- **Provider-side coercion of non-conforming tool-call responses.** If a chosen model emits malformed tool-call protocol, the agent handles the case gracefully (treats absent tool_calls as final response) but does not coerce or correct the model's output. Model selection is the user's responsibility.
