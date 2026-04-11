---
docType: initiative-plan
layer: project
project: squadron
source: user/project-guides/001-concept.squadron.md
dateCreated: 20260325
dateUpdated: 20260327
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
5. [ ] **(900) Maintenance and Refactoring** — Cross-cutting maintenance, tech debt, refactoring, and operational improvements that span initiative boundaries. Dependencies: None. Status: not_started

## Cross-Initiative Dependencies
- 140 depends on 100: needs stable agent dispatch, review system, model aliases, CF integration layer, and CLI interfaces
- 180 depends on 100, 140: builds on 140's action protocol, pipeline executor, model resolver, and structured review findings
- 200 depends on 100: builds on agent registry, provider protocols, and daemon infrastructure
- 220 depends on 100, 200: requires both core engine and multi-agent communication layer
- 900 is independent: maintenance work applies across all initiatives as needed

## Notes
- Indices are tentative and may be reassigned as initiatives are added or reorganized.
- New initiatives discovered during development are added here with the next available base index.
- Check off initiatives as their architecture documents and slice plans are complete.
- Initiative 100 is effectively complete. Slice 123 migrated to 140 (as slice 141). Slice 125 migrated to 160.
- Initiative 140 supersedes the earlier `140-arch.automated-dev-pipeline.md` draft. The new `140-arch.pipeline-foundation.md` has a narrower, more concrete scope with intelligence features split into initiative 180.
- Initiative 180 (Pipeline Intelligence) was split from 140 along the foundation/intelligence boundary. 140 is deterministic machinery; 180 is probabilistic heuristics that require calibration.
- Initiatives 160, 180, 200, and 220 were re-indexed from original 160, 180, 200 on 2026-04-06 to free up number space in the 140 initiative for additional slices.
