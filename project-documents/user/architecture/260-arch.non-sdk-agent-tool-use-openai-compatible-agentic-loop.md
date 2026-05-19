---
docType: architecture
archIndex: 260
component: non-sdk-agent-tool-use-openai-compatible-agentic-loop
initiative: non-sdk-agent-tool-use-openai-compatible-agentic-loop
project: squadron
parent: ../project-guides/001-initiative-plan.squadron.md
dependencies: [100, 140, 240]
dateCreated: 20260505
dateUpdated: 20260519
status: not_started
---

# Architecture: Non-SDK Agent Tool Use (OpenAI-Compatible Agentic Loop)

## Overview

Squadron's `OpenAICompatibleAgent` (used for openrouter, openai, local, and gemini providers) is text-in/text-out only. It detects `tool_calls` deltas in the streaming API response and surfaces them as read-only system messages, but it never passes a `tools` parameter to `chat.completions.create()` and never executes returned tool calls. Pipeline actions that depend on file artifacts being written by the model — most visibly the `design` step type, which emits a slice-design markdown file — silently fail when run with a capable non-SDK model: the model emits its tool-call protocol as raw text, no file is created, and downstream steps (e.g. `review`) report "missing input."

This component adds tool-calling capability to non-SDK agents via an agentic loop that lives inside `OpenAICompatibleAgent.handle_message`. The loop passes a tool schema to the model, executes returned tool calls against squadron-side tool implementations, accumulates the assistant/tool-result message history within a single call, and re-invokes the model until it returns a response with no further `tool_calls`. Tool access is gated by an explicit `allowed_tools` allowlist on `AgentConfig` — the project policy is "no tools by default" for non-SDK models.

**Scope.** OpenAI-compatible providers only (openrouter, openai, local, gemini). Initial action coverage is `dispatch`. SDK provider is unchanged — it already has full tool support via the `claude_code` system-prompt preset and `bypassPermissions`. Codex provider is out of scope (it has its own internal agentic handling).

**Motivation.** Pipelines should be able to use cost-effective or capability-specific non-SDK models for tasks that require file I/O (design, codegen, refactoring) without being forced to use Claude. This unlocks the original promise of profile-aware dispatch (slice 240): pick the right model for the step, and the step actually works.

## Design Goals

- **Capability without surrender of control.** Capable non-SDK models gain tool-use, but only via an explicit per-step `allowed_tools` allowlist. There is no "all tools by default" path.
- **Self-contained loop with future-extraction in mind.** The agentic loop lives inside `handle_message` for a clean caller boundary today, but is structured (in a clearly named private method) so it can be lifted to a higher orchestration layer when that layer arrives.
- **Standard protocol.** Use the OpenAI tool-call protocol verbatim — `tools` parameter on the request, `tool_calls` on the response, `role: "tool"` messages with `tool_call_id` on the next turn. No bespoke JSON shapes.
- **Bounded execution.** Every loop has a max-iterations guard. File-tool operations are CWD-restricted (path-escape rejected). Bash, when enabled, runs with `cwd` as working directory; this is the trust boundary at this stage — network access, env manipulation, and process forking are not blocked. Failure modes are observable, not silent.
- **No SDK-path regression.** `ClaudeSDKAgent` and `CodexAgent` paths are unchanged. The new tool registry and `allowed_tools` plumbing must not couple to or alter SDK tool delivery.

## Architectural Principles

- **Allowlist, not denylist.** The default `AgentConfig.allowed_tools` for a non-SDK agent is empty (or `None`, equivalent to empty for non-SDK). A pipeline opts in by listing tool names. An unknown or unlisted tool name in a model's response is a tool-execution error surfaced back to the model, not a silent skip. The `allowed_tools` field is shared with the SDK path; semantics are provider-specific (SDK consumes the list as Claude Code tool names; non-SDK consumes it as squadron tool-registry names).
- **Tool implementations are pure side-effects with explicit IO surfaces.** Each tool is a small, isolated function that takes parsed arguments and returns a structured result (text or JSON). Tools own their failure messages. No tool reaches into agent or executor internals.
- **CWD as the trust boundary.** File operations resolve paths relative to the agent's `cwd` and reject anything that escapes it (no `..`, no absolute paths outside the tree). Bash runs with `cwd` as working directory and no network. Path-escape is the canonical sandbox check.
- **Loop visibility via logging, not interface change.** Each tool call and result is logged at DEBUG (and at INFO for tool-call summaries under `-vv`). The executor sees a single dispatch result, unchanged. Future orchestration can observe by intercepting the loop, not by re-shaping the agent interface.
- **Tool registry parallels action registry.** Tools are registered by name into a process-level registry, mirroring how actions and step types are registered. Provider-agnostic registration; `OpenAICompatibleAgent` consults the registry to materialize schemas and execute calls. This keeps the design open to MCP-bridged tools (e.g. context-forge) being registered uniformly.

## Current State

- `OpenAICompatibleAgent._call_api()` issues `chat.completions.create(model=..., messages=..., stream=True, extra_body=...)` — no `tools` parameter, ever.
- The streaming consumer (`_consume_stream`) collects `delta.tool_calls` into `tool_calls_state` and emits them as `MessageType.system` records via `translation.build_tool_call_message`. These messages are visible to the pipeline as text but are never re-injected into the model's next turn — there is no next turn.
- `AgentConfig` has fields `allowed_tools`, `permission_mode`, `setting_sources`, `cwd` — all consumed by the SDK provider, all silently ignored by `OpenAICompatibleProvider`.
- `dispatch` action's `_dispatch_via_agent` constructs an `AgentConfig` without populating `allowed_tools`. Pipeline YAML has no syntax for declaring tool access on a step.
- Result: a YAML pipeline configured to run `design` with `model: kimi25` produces a "successful" dispatch (the API call returns) whose `outputs.response` contains the model's raw tool-call XML. The next step fails because no file exists.

## Envisioned State

When this component is complete:

- A pipeline step can declare `allowed_tools: [read_file, write_file, bash]` (or a subset) in its YAML config. The dispatch action threads this into `AgentConfig.allowed_tools`.
- For non-SDK providers, `OpenAICompatibleAgent.handle_message` runs an agentic loop:
    1. Materialize tool schemas from the registry for the names in `AgentConfig.allowed_tools`. Pass them as the `tools` parameter on the API call.
    2. Stream the response. If `tool_calls` are present in the assistant message, do not return yet. The assistant message (including any `content` field, even when `tool_calls` are also present) is appended verbatim to the in-memory message history per OpenAI protocol.
    3. For each tool call: look up the tool in the registry, validate arguments against the tool's schema, execute, and capture the result.
    4. Append a `role: "tool"` message per call to the message history (with matching `tool_call_id`).
    5. Re-invoke the API with the extended history and the same tools. Loop.
    6. When the assistant message has no `tool_calls`, yield the final content as the response and exit.
- **Streaming contract during the loop:** Intermediate iterations (turns that return `tool_calls`) are consumed internally; their content is logged at DEBUG but not surfaced to the caller. Only the final turn's content is streamed normally through the agent's existing message-yield interface. Pipeline progress observability for intermediate tool calls is via logs (`-v`/`-vv`), not via the agent interface. This is a deliberate scope choice for this stage; future orchestration can lift the loop boundary to expose intermediate turns.
- A max-iterations guard (configurable, conservative default) terminates runaway loops with a structured error returned via the agent's normal failure path.
- Tool implementations (`read_file`, `write_file`, `bash`) live in `core/tools/` (or analogous) and are registered at module import time. File tools enforce CWD scope (path-escape rejected). Bash runs with CWD as working directory; network/env/fork are not restricted at this stage.
- `dispatch` action wiring reads `allowed_tools` from the resolved step config and passes it to `AgentConfig`. Other actions (`review`, `summary`) are unchanged in this initiative — extension is a future slice.
- A pipeline like `test-p4.yaml` with `model: kimi25` and `allowed_tools: [read_file, write_file]` on the design step actually produces the slice-design file; the subsequent review step finds its input.

## Technical Considerations

- **Tool descriptor protocol.** A tool descriptor is the unit of registration in the tool registry. Each descriptor carries: a `name` (string, registry key), a `description` (string, surfaced to the model), a JSON Schema `parameters` definition (compatible with OpenAI's `tools[].function.parameters` shape), and a `factory` callable. The factory is invoked once per dispatch with the agent's `cwd` (and any other infrastructure context) and returns an `async` execute callable. Execute callables take parsed-and-validated arguments (a `dict[str, object]`) and return a `ToolResult` value carrying `content: str` and `is_error: bool`. Registry API: `register(descriptor)`, `lookup(name) -> descriptor | None`, `materialize(names: list[str], cwd: str) -> dict[name, executor]`. Materializing per-dispatch (rather than per-process) keeps `cwd` explicit and out of the descriptor itself, so descriptors stay pure data and tools remain testable in isolation by invoking the factory with a test `cwd`.
- **`cwd` injection.** `cwd` is infrastructure context, not a model-provided argument. It must not appear in the tool's JSON Schema (the model could override it). The factory pattern above keeps `cwd` an explicit closure-bound input known only to the factory and its returned executor.
- **Async-first execution interface.** The execute callable returned by the factory is `async def execute(args: dict) -> ToolResult`. Synchronous tools (e.g. `read_file`) wrap their work in `asyncio.to_thread` or run inline since the body is fast. The async surface is non-negotiable: it ensures MCP-bridged tools (slice 264) compose as adapters rather than requiring a re-architecture.
- **Token-budget and message-history growth.** The agentic loop accumulates assistant + tool-result messages on each iteration. Non-SDK models often have smaller context windows. Strategy: (a) the `max_iterations` guard remains the primary termination control; (b) the loop tracks a rough message-history character count and, on exceeding a configurable threshold, returns a budget-exceeded error to the model as the next tool result so the model can finalize; (c) no automatic truncation/summarization in the initial implementation — that complexity is deferred. Practically, the typical design-step loop completes in 2–5 turns, well under any reasonable budget. Document the threshold and surface it via DEBUG logging.
- **Streaming + tool-calls + multi-turn semantics.** OpenAI's streaming API yields tool-call deltas across multiple chunks; a complete tool call requires aggregating across them (id, function name, arguments string). The current `_consume_stream` already aggregates into `tool_calls_state` — that work is reusable. The novel piece is treating the assembled tool-call set as a control-flow signal (loop) rather than a metadata event.
- **Message history shape.** The OpenAI tool-call protocol requires the assistant message in the next turn to include the original `tool_calls` array, and each tool result to be a separate message with `role: "tool"` and matching `tool_call_id`. The agent must construct these messages itself, not rely on the SDK doing it. Keeping this construction in one place (`translation.py` is a candidate) avoids drift.
- **Tool argument validation.** Models can return malformed JSON for the `arguments` string. The agent must catch parse errors per-tool-call and return a structured error to the model rather than crashing the loop. Same for argument-schema mismatches.
- **Path-escape detection.** `read_file` and `write_file` must reject path traversal. The check must be done after resolving symlinks and normalizing — naive `..` rejection is not enough. `pathlib.Path.resolve(strict=False).is_relative_to(cwd_resolved)` is the canonical pattern. (`is_relative_to` is Python 3.9+; squadron targets 3.12+ per project rules, so this is in-spec.)
- **Bash scope at this stage.** Bash, when listed in `allowed_tools`, runs with `cwd` as working directory. Network access, environment manipulation, and process forking are NOT restricted at this stage — `cwd` is the only enforced boundary. This is a deliberate scope choice: harder sandboxing (subprocess env scrubbing, pid-namespace isolation, network deny) is deferred and tracked as future work. The per-pipeline allowlist provides opt-out: pipelines that don't include `bash` in `allowed_tools` cannot invoke it.
- **Loop iteration cost.** Each loop turn is a full API round-trip. The `max_iterations` default needs to balance "complex enough to finish a design step" against "runaway protection." A starting value of ~20 is reasonable; the slice that implements the loop should make it a tunable.
- **Provider-side tool-call support varies.** Not every OpenAI-compatible endpoint implements `tools` consistently — some local servers ignore it, some return tool calls but in non-standard formats. The agent must handle "tools requested but model returned plain text" gracefully (treat as final response). It does not need to coerce non-conforming responses; the user's selected model is their responsibility.
- **Registry vs. inline tools.** Tools could be inlined into the agent or extracted into a registry. A registry is preferred: it enables MCP-bridged tools (context-forge), enables review/summary actions to share the same tool implementations later without duplication, and matches squadron's existing registry pattern (actions, step types).
- **Interaction with slice 240's profile-aware routing.** The agentic-loop changes are entirely inside the agent provider, downstream of the dispatch routing decision. No changes needed to classification, session construction, or the lazy/strict policy.

## Anticipated Slices

- **(261) Tool registry, descriptor protocol, and core tool implementations.** Define the tool descriptor protocol (name, description, JSON Schema parameters, factory returning an async executor), the process-level tool registry (`register`, `lookup`, `materialize`), and ship `read_file` / `write_file` / `bash` with CWD-scope enforcement on file tools. No agent changes; tools are testable in isolation by calling the factory with a test `cwd`. Foundation for everything below.
- **(262) `OpenAICompatibleAgent` agentic loop.** Reuse the existing `AgentConfig.allowed_tools` field for non-SDK semantics. Materialize schemas from the registry for the names in `allowed_tools`, implement `_run_agentic_loop` inside `handle_message` (max-iterations guard, multi-turn message accumulation, tool execution, error surfacing, token-budget threshold). Self-contained behind the existing agent interface; intermediate turns logged at DEBUG, only final turn streams to caller.
- **(263) `dispatch` action wiring and pipeline YAML surface.** Thread `allowed_tools` from step config through `_dispatch_via_agent` into `AgentConfig.allowed_tools`. Pipeline schema validates the field (list of registered tool names). End-to-end: `test-p4.yaml` runs to completion with `model: kimi25` and explicit `allowed_tools`.
- **(264) Context-forge MCP tool bridge** *(optional, separate slice).* A registry adapter that exposes selected context-forge MCP operations as agentic-loop tools via the same descriptor protocol. The async-first execute interface from slice 261 makes this an adapter, not a re-architecture.
- **(265) Review/summary action coverage** *(deferred extension).* Apply the same `allowed_tools` plumbing to `review` and `summary` actions. Out of initial scope; tracked here for completeness.

## Related Work

- Initiative 240 (`240-arch.pipeline-auth-boundary-flexibility.md`): established profile-aware dispatch routing and the lazy/strict pool-resolution policy. This initiative depends on 240's `_dispatch_via_agent` path being in place.
- Initiative 140 (`140-arch.pipeline-foundation.md`): established the `Action` protocol, `AgentConfig`, and the agent registry that this initiative extends.
- `src/squadron/providers/openai/agent.py`: current text-only `OpenAICompatibleAgent`.
- `src/squadron/providers/sdk/agent.py`: SDK agent for reference on how tool-use is delivered on the Claude path (different mechanism — `claude_code` preset — but informative for shape of `allowed_tools` semantics).
- `src/squadron/core/models.py`: `AgentConfig` definition.
- Future orchestration initiative (tentatively planned): will eventually need to observe intermediate tool calls. The `_run_agentic_loop` extraction in slice 262 is the seam for that future lift.
