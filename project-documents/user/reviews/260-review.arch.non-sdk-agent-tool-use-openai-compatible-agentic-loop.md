---
docType: review
layer: project
reviewType: arch
slice: non-sdk-agent-tool-use-openai-compatible-agentic-loop
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/architecture/260-arch.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md
aiModel: z-ai/glm-5.1
status: complete
dateCreated: 20260505
dateUpdated: 20260505
findings:
  - id: F001
    severity: fail
    category: consistency
    summary: "Design goal promises \"no network from bash\" but implementation explicitly will not deliver it"
    location: 260-arch.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md#Design Goals
  - id: F002
    severity: concern
    category: completeness
    summary: "No context-window or token-budget management strategy for the agentic loop"
    location: 260-arch.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md#Envisioned State
  - id: F003
    severity: concern
    category: abstraction
    summary: "`cwd` injection into tool implementations is an unaddressed implicit dependency"
    location: 260-arch.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md#Architectural Principles
  - id: F004
    severity: concern
    category: completeness
    summary: "Tool descriptor protocol is entirely undefined"
    location: 260-arch.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md#Anticipated Slices
  - id: F005
    severity: concern
    category: extension-points
    summary: "MCP extension point may not compose with a synchronous-only registry"
    location: 260-arch.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md#Technical Considerations
  - id: F006
    severity: concern
    category: consistency
    summary: "Inconsistent naming: `allowed_tools` vs `config.tools` vs `AgentConfig.tools`"
    location: 260-arch.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md#Envisioned State
  - id: F007
    severity: concern
    category: completeness
    summary: "Streaming contract during the agentic loop is unspecified"
    location: 260-arch.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md#Envisioned State
  - id: F008
    severity: concern
    category: completeness
    summary: "Content + tool_calls co-occurrence in a single response is unhandled"
    location: 260-arch.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md#Envisioned State
  - id: F009
    severity: note
    category: technology
    summary: "`pathlib.Path.is_relative_to` requires Python ≥ 3.9"
    location: 260-arch.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md#Technical Considerations
---

# Review: arch — slice 260

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.1

## Findings

### [FAIL] Design goal promises "no network from bash" but implementation explicitly will not deliver it

The Design Goals section states: *"Every tool execution has scope limits (CWD-restricted file/bash operations, **no network from bash**)."* This is a security guarantee. Yet the Technical Considerations section explicitly walks it back: *"'CWD-restricted' is necessary but **does not prevent network access**, environment manipulation, or process forking. The initial implementation accepts this scope (CWD restriction only)."* A design goal that makes a security claim the implementation knowingly won't satisfy is worse than no claim — it creates a false trust boundary. Either remove "no network from bash" from the design goal and replace it with the honest scope, or don't ship `bash` in the initial tool set until the sandbox can enforce the stated constraint.

### [CONCERN] No context-window or token-budget management strategy for the agentic loop

The agentic loop accumulates assistant messages and `role: "tool"` results on each iteration. The motivation explicitly targets "cost-effective" non-SDK models, which tend to have smaller context windows. The document sets a `max_iterations` guard (~20) but never addresses what happens when the accumulated message history exceeds the model's context window before hitting that iteration limit. There is no strategy for truncation, summarization of prior tool results, or graceful failure. This is the primary operational failure mode for long-running tool-use sessions and it is entirely absent.

### [CONCERN] `cwd` injection into tool implementations is an unaddressed implicit dependency

The document states tools are *"pure side-effects with explicit IO surfaces"* that *"take parsed arguments."* But `cwd` — the trust boundary for `read_file`, `write_file`, and `bash` — is infrastructure context, not a model-provided argument. The document never specifies how `cwd` flows from the agent into tool execution. If `cwd` is passed as an implicit parameter through a closure or context object, the tool is no longer "pure" and testable in isolation (slice 261's claim). If it's injected into the tool's argument schema, the model could override it. This is a load-bearing design decision left implicit.

### [CONCERN] Tool descriptor protocol is entirely undefined

Slice 261 ships the tool registry and core tool implementations as the foundation for everything else, yet the document never defines the tool descriptor protocol: what fields a tool descriptor has, how JSON Schema is declared for the OpenAI `tools` parameter, how execution is dispatched from the registry, how `(content, is_error)` results are structured, or how the registry API works (`register`, `lookup`, `list`). This is the central abstraction of the entire initiative. Without it, slice 261's boundary is ambiguous and slices 262–264 may not compose.

### [CONCERN] MCP extension point may not compose with a synchronous-only registry

The document says the registry *"keeps the design open to MCP-bridged tools (e.g. context-forge) being registered uniformly"* (slice 264). But MCP tool calls are inherently async and have different lifecycle semantics (session management, capability negotiation, different schema formats). If the tool registry and descriptor protocol in slice 261 are designed around synchronous callables returning `(content, is_error)`, MCP bridging won't be an adapter — it will require rearchitecting the execution path. The document should specify whether the tool execution interface is async-compatible from day one.

### [CONCERN] Inconsistent naming: `allowed_tools` vs `config.tools` vs `AgentConfig.tools`

The Architectural Principles say *"The default `AgentConfig.tools` for a non-SDK agent is empty."* The Envisioned State step 1 says *"Materialize tool schemas from the registry for the names in `config.tools`."* The YAML surface and Current State section use `allowed_tools`. These refer to the same field but with three different names. The Envisioned State even uses both `allowed_tools` (in the YAML example) and `config.tools` (in the loop description) in the same section. This must be resolved before implementation to avoid aliasing bugs.

### [CONCERN] Streaming contract during the agentic loop is unspecified

The current `OpenAICompatibleAgent` streams responses to the caller. The agentic loop makes multiple API round-trips internally. The document never specifies what the caller sees during the loop: are intermediate streaming chunks from tool-call turns surfaced? Is the final response the only streamed output? Does the caller receive a single stream that spans all loop iterations, or does the loop consume entire responses silently and only stream the final turn? This changes the `handle_message` interface contract and affects pipeline progress observability.

### [CONCERN] Content + tool_calls co-occurrence in a single response is unhandled

OpenAI-compatible models can return both `content` (text) and `tool_calls` in the same assistant message. The envisioned loop (step 2: "If `tool_calls` are present… do not return yet") doesn't specify what happens to the content portion. Is it discarded? Appended to the message history? Included in the final response? The OpenAI protocol requires the assistant message with both fields to be included in the next turn's history — if content is dropped, the model loses context; if it's kept but never shown to the user, it's invisible reasoning. This ambiguity affects both correctness and observability.

### [NOTE] `pathlib.Path.is_relative_to` requires Python ≥ 3.9

The document prescribes `pathlib.Path.resolve(strict=False).is_relative_to(cwd_resolved)` as the canonical path-escape check. `is_relative_to` was introduced in Python 3.9. If the project targets 3.8, this won't work. Even if 3.9+ is the target, this should be noted as a minimum-version dependency for the tool implementations.
