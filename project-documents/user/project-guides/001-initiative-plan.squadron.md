---
docType: initiative-plan
layer: project
project: squadron
source: user/project-guides/001-concept.squadron.md
dateCreated: 20260325
dateUpdated: 20260505
status: in_progress
---

# Initiative Plan: Squadron

## Source
Retroactively generated from existing architecture documents.

## Index Convention
Variable gaps based on initiative scope. Working range 100-799 for feature initiatives, 900+ reserved for cross-cutting maintenance and refactoring.

## Initiatives

1. [x] **(100) Orchestration (Python Reboot)** — Core engine, agent providers, CLI interface, review system, daemon. M1 shipped (v0.2.7). Dependencies: None (foundation). Status: in_progress
2. [x] **(140) Pipeline Foundation** — Action protocol, declarative pipeline definitions (YAML), executor with step sequencing, model resolution cascade, basic and collection loops, state persistence and resume, built-in pipelines (slice-lifecycle, review-only, design-batch). Ships `sq run` as a working replacement for run-slice. Dependencies: [100]. Status: draft
3. [ ] **(180) Pipeline Intelligence** — Weighted review convergence strategies (decay-based finding dismissal), model pools with selection strategies, escalation behaviors (auto-retry with stronger model), conversation persistence across retries, findings ledger with cross-iteration identity matching. Layers sophistication onto 140's foundation. Dependencies: [100, 140]. Status: draft
4. [ ] **(200) Multi-Agent Communication** — Shared message bus, configurable routing topologies, supervisor with health monitoring and restart strategies, multi-provider agent coordination, human-in-the-loop participation. Dependencies: [100]. Status: not_started
5. [ ] **(220) Simulation Runtime** — Persistent agent entities with identity and emergent behavior in shared environments. Future work. Dependencies: [100, 200]. Status: future_work
6. [ ] **(240) Pipeline Auth-Boundary Flexibility** — Decouple pipeline execution from unconditional Claude SDK auth. Two SDK-touching paths (persistent `SDKExecutionSession` for cross-step Claude dispatches; one-shot `ClaudeSDKAgent` spawned by the provider registry for review/dispatch when a Claude profile is resolved) become independently controlled. Per-step auth classification via pre-scan of resolved models, conditional persistent-session creation (connect iff some step actually needs it), profile-aware dispatch routing in pure-CLI executor mode, and clear error semantics when pool resolution mid-run conflicts with the upfront classification. Goal: pipelines composed entirely of non-Claude profiles run end-to-end without Claude auth, login, or account; mixed pipelines pay Claude cost only where actually used; persistent-session lifetime guarantees (compact/rotate-only termination) preserved for SDK-profile dispatch chains. Explicit non-goals: until-loop convergence intelligence, fan-out/fan-in aggregation semantics, intra-loop compaction policy, conversation-vs-override-instruction routing for review findings — all 180-band. One-shot Claude subprocess pooling/reuse documented as known cost, not optimised here. Dependencies: [100, 140]. Status: not_started.
7. [ ] **(260) Non-SDK Agent Tool Use (OpenAI-Compatible Agentic Loop)** — Add tool-calling capability to non-SDK provider agents (openrouter, openai, local, gemini) so dispatch and review actions can use models like Kimi-K2.5, GPT-4-class, etc. for tasks that require file I/O. Today the `OpenAICompatibleAgent` is text-in/text-out only: it detects tool calls in the streaming response but never passes a `tools` parameter to the API and never executes them, so capable models emit raw tool-call XML into the response stream and pipeline steps that depend on file writes (e.g. `design`) silently fail. This initiative implements an agentic loop inside `handle_message`: pass a tool schema to the API, execute returned `tool_calls` via squadron-side tool implementations (file read, file write, bash sandboxed to CWD), accumulate the assistant/tool-result message history within the call, and re-invoke the model until it returns a response with no `tool_calls`. Tool access is controlled by an explicit `allowed_tools` allowlist on `AgentConfig` (empty by default) — the project rejects "all tools by default" for non-SDK models. Implementation is structured for future lift-out: the loop lives in a private `_run_agentic_loop` method so when the higher-level orchestration layer (tentatively planned) needs to observe intermediate tool calls, the boundary is already extracted. Goal: pipelines using capable non-SDK models (Kimi, GPT-4, etc.) for design/dispatch steps actually produce file artifacts; allowed_tools is enforced; max-iteration guard prevents runaway loops. Explicit non-goals: streaming intermediate tool calls to the executor (deferred to orchestration initiative), MCP tool bridging beyond context-forge (separate slice if pursued), changes to the SDK path (which already has full tool support via Claude Code preset), `review`/`summary` action coverage (initial scope is `dispatch` only). Dependencies: [100, 140, 240]. Status: not_started.
8. [x] **(900) Maintenance and Refactoring** — Cross-cutting maintenance, tech debt, refactoring, and operational improvements that span initiative boundaries. Dependencies: None. Status: not_started

## Cross-Initiative Dependencies
- 140 depends on 100: needs stable agent dispatch, review system, model aliases, CF integration layer, and CLI interfaces
- 180 depends on 100, 140: builds on 140's action protocol, pipeline executor, model resolver, and structured review findings
- 200 depends on 100: builds on agent registry, provider protocols, and daemon infrastructure
- 220 depends on 100, 200: requires both core engine and multi-agent communication layer
- 240 depends on 100, 140: builds on agent registry / provider-profile resolution (100), the pipeline executor and model resolver (140), and the persistent `SDKExecutionSession` lifecycle established in 140. Coordinates with 180 at the auth-classification ↔ pool-resolution boundary but does not depend on 180.
- 260 depends on 100, 140, 240: builds on the agent registry and `OpenAICompatibleAgent` (100), the dispatch action and `AgentConfig` interface (140), and the profile-aware dispatch routing established in 240. Independent of 180.
- 900 is independent: maintenance work applies across all initiatives as needed

## Notes
- Indices are tentative and may be reassigned as initiatives are added or reorganized.
- New initiatives discovered during development are added here with the next available base index.
- Check off initiatives as their architecture documents and slice plans are complete.
- Initiative 100 is effectively complete. Slice 123 migrated to 140 (as slice 141). Slice 125 migrated to 160.
- Initiative 140 supersedes the earlier `140-arch.automated-dev-pipeline.md` draft. The new `140-arch.pipeline-foundation.md` has a narrower, more concrete scope with intelligence features split into initiative 180.
- Initiative 180 (Pipeline Intelligence) was split from 140 along the foundation/intelligence boundary. 140 is deterministic machinery; 180 is probabilistic heuristics that require calibration.
- Initiatives 160, 180, 200, and 220 were re-indexed from original 160, 180, 200 on 2026-04-06 to free up number space in the 140 initiative for additional slices.
