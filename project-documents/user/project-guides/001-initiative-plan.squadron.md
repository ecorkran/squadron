---
docType: initiative-plan
layer: project
project: squadron
source: user/project-guides/001-concept.squadron.md
dateCreated: 20260325
dateUpdated: 20260325
status: in_progress
---

# Initiative Plan: Squadron

## Source
Retroactively generated from existing architecture documents.

## Index Convention
Variable gaps based on initiative scope. Working range 100-799 for feature initiatives, 900+ reserved for cross-cutting maintenance and refactoring.

## Initiatives

1. [x] **(100) Orchestration (Python Reboot)** — Core engine, agent providers, CLI interface, review system, daemon. M1 shipped (v0.2.7). Dependencies: None (foundation). Status: in_progress
2. [ ] **(140) Automated Development Pipeline** — Integration layer combining Context Forge context assembly with agent dispatch and review workflows to automate ai-project-guide development phases. Dependencies: [100]. Status: draft
3. [ ] **(160) Multi-Agent Communication** — Shared message bus, configurable routing topologies, multi-provider agent coordination. Dependencies: [100]. Status: not_started
4. [ ] **(200) Simulation Runtime** — Persistent agent entities with identity and emergent behavior in shared environments. Future work. Dependencies: [100, 160]. Status: future_work
5. [ ] **(900) Maintenance and Refactoring** — Cross-cutting maintenance, tech debt, refactoring, and operational improvements that span initiative boundaries. Dependencies: None. Status: not_started

## Cross-Initiative Dependencies
- 140 depends on 100: needs stable agent dispatch, review system, and CLI interfaces
- 160 depends on 100: builds on agent registry, provider protocols, and daemon infrastructure
- 200 depends on 100, 160: requires both core engine and multi-agent communication layer
- 900 is independent: maintenance work applies across all initiatives as needed

## Notes
- Indices are tentative and may be reassigned as initiatives are added or reorganized.
- New initiatives discovered during development are added here with the next available base index.
- Check off initiatives as their architecture documents and slice plans are complete.
- Initiative 100 is checked off at the architecture/slice-plan level (M1 complete), though remaining slices (123-125) are still in progress.
