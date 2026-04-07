---
docType: architecture
layer: project
project: squadron
archIndex: 220
component: simulation-runtime-future-work
dateCreated: 20260322
dateUpdated: 20260406
status: future_work
---

# Architecture: Simulation Runtime (Future Work)

## Status
This is a draft document. It is not refined for compliance with Architectural Document (Phase 2) guidelines. This is required before creating a slice plan from this document.

## Future Work: Simulation Runtime
The orchestration system's original motivation — experimenting with agent interaction patterns — naturally extends to a simulation runtime where agents are persistent entities with identity, personality, and emergent behavior rather than task-completion nodes in a workflow.

### Vision
Multi-model simulations where each agent is a distinct entity: different LLM provider, different system instructions (personality, backstory, motivation, knowledge), different tool access, different interaction patterns. Agents interact with each other and with human participants in a shared environment governed by topology and turn management rules.

### First Form Factor: Interactive Text Adventure
A text adventure where NPCs are LLM agents. Requires:

- **Environment agent** (narrator/world state manager, strongest available model)
- **Character agents** (mixed models, system prompts as personality/backstory/motivation)
- **Human participant** (the player, via CLI or future UI)
- **Spatial topology** (who can hear whom — characters in the same "room" share a message context)
- **Turn management** (conversational rhythm — which character speaks next, preventing dominant models from monopolizing, creating natural pacing)

### Why This Is Different From Existing Agent Runtimes
Existing frameworks (CrewAI, AutoGen, OpenClaw, NanoClaw, etc.) optimize for task completion workflows — agent A researches, agent B writes, agent C reviews. They are pipelines with agent-shaped nodes. The simulation runtime treats agents as persistent entities whose interactions are the point, not a means to a task output.

Closest prior art: Stanford's Generative Agents paper (2023), but that was an academic prototype, not a reusable tool.

### Architectural Alignment
The orchestration system's existing design decisions support this directly:

- **Unified Agent Protocol** → mixing models is native (a character can be GPT-4o, Claude, Gemini, or local)
- **Message bus with configurable topologies** → environment/spatial rules for who hears what
- **Human-in-the-loop** → player participation
- **Provider-agnostic design** → different "thinking" qualities map to personality differences
- **Persistent agents (daemon, slice 112)** → agents that maintain identity and conversation history
- **Agent identity files** (future: agent.md, soul.md) → declarative personality/role/knowledge definitions

### Prerequisite Slices
- 112: Local Server & CLI Client (persistent agents)
- Slice 6: Message Bus Core (agent-to-agent communication)
- Slice 8: Multi-Agent Message Routing (topology-aware delivery)
- Slice 9: Human-in-the-Loop (player participation)
- Slice 10: Communication Topologies (spatial/environmental rules)

### Open Research Questions
- **Turn management in free-form multi-agent conversation**: How to create natural conversational rhythm? Which character speaks next? How to prevent one model from dominating?
- **World state consistency**: How does the environment agent maintain coherent state as multiple characters act?
- **Agent memory and continuity**: How do characters "remember" past interactions across sessions?
- **Evaluation**: How do you measure whether a simulation is producing interesting/coherent behavior?
