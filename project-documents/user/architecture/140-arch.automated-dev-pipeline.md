---
docType: architecture
layer: project
project: squadron
archIndex: 140
component: automated-dev-pipeline
dateCreated: 20260221
dateUpdated: 20260221
status: draft
---

# Architecture: Automated Development Pipeline

## Overview

The Automated Development Pipeline (ADP) is an integration layer that combines Context Forge's context assembly capabilities with Orchestration's agent dispatch and review workflows to automate the ai-project-guide development phases. It executes the phase loop — slice design → review → task breakdown → review → implementation → verification — as a managed pipeline with human checkpoints at critical decision points.

This is not a new product. It is a capability within the orchestration system that consumes Context Forge as a service.

### The Core Insight

During the Context Forge restructure (initiative 140), a pattern emerged: once architecture and slice plans were designed (human + AI collaborative work), the subsequent phases — slice design, task breakdown, and implementation — were consistently completable by AI agents when given properly constructed context. The agent "one-shotted" every implementation task list. The bottleneck was not agent capability but the manual labor of assembling context, dispatching agents, running reviews, and managing phase transitions.

The ADP automates that mechanical labor. It preserves human authority at architectural decision points while eliminating the human-as-context-assembly-bottleneck antipattern.

### Relationship to Other Initiatives

**Orchestration (100-band):** The ADP lives within the orchestration codebase. It uses the agent registry, SDK agent provider, and review workflow templates. The pipeline executor is an orchestration capability.

**Context Forge (140-band):** The ADP consumes Context Forge via its MCP server. It calls `context_build`, `project_update`, `context_summarize`, and other MCP tools to assemble context for each phase. Context Forge is a service dependency, not modified by this initiative.

**ai-project-guide:** The ADP encodes the guide's phase methodology as executable pipeline definitions. The guide remains the source of truth for methodology; the ADP is a runtime implementation of it.

---

## System Architecture

### Component Relationships

```
┌──────────────────────────────────────────────────────────┐
│                    Human (Project Manager)                 │
│         Architecture decisions, checkpoints, overrides     │
└────────────────────────┬─────────────────────────────────┘
                         │ checkpoint interactions
                         ▼
┌──────────────────────────────────────────────────────────┐
│              Pipeline Executor (Orchestration)             │
│                                                           │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │  Pipeline    │  │  Phase       │  │  Checkpoint    │  │
│  │  Definition  │  │  Runner      │  │  Manager       │  │
│  └─────────────┘  └──────┬───────┘  └───────┬────────┘  │
│                          │                    │           │
│  ┌───────────────────────┴────────────────────┘          │
│  │                                                       │
│  │  ┌──────────────┐  ┌──────────────┐                   │
│  │  │  Agent       │  │  Compaction  │                   │
│  │  │  Selector    │  │  Strategy    │                   │
│  │  └──────────────┘  └──────────────┘                   │
│  │                                                       │
└──┼───────────────────────────────────────────────────────┘
   │
   │ consumes (MCP)              dispatches (SDK/API)
   ▼                             ▼
┌─────────────┐           ┌─────────────────┐
│  Context    │           │  Agent Execution │
│  Forge      │           │  (SDK Provider)  │
│  MCP Server │           │                  │
└─────────────┘           └─────────────────┘
```

### Key Components

#### Pipeline Definition

A declarative specification of the phase loop for a unit of work (typically: one slice through the full cycle). Defines phases, their ordering, context requirements, agent configuration, review gates, and checkpoint conditions.

Pipeline definitions are data, not code. They can be stored as YAML files, constructed programmatically by the pipeline executor, or provided at runtime.

```yaml
# Example: Standard slice pipeline
name: standard-slice-pipeline
description: Full lifecycle for a single slice from design through implementation

input:
  required:
    - arch_doc        # Path to architecture document
    - slice_plan      # Path to slice plan
    - slice_name      # Name of the slice to process
  optional:
    - additional_context  # Extra files to include
    - model_overrides     # Per-phase model overrides

phases:
  - name: slice-design
    instruction_type: slice-design
    context_files:
      - "{arch_doc}"
      - "{slice_plan}"
    agent:
      default_model: claude-opus-4-6
      thinking: extended
      max_turns: null         # let agent work until done
    output:
      type: file
      pattern: "{slice_index}-slice.{slice_name}.md"
    review:
      template: arch
      against: "{arch_doc}"
    checkpoint:
      trigger: on-concerns    # PASS=proceed, CONCERNS=pause, FAIL=pause
      
  - name: task-breakdown
    instruction_type: task-breakdown
    context_files:
      - "{output.slice-design}"  # output of prior phase
      - "{slice_plan}"           # for broader context
    agent:
      default_model: claude-opus-4-6
      thinking: standard
    output:
      type: file
      pattern: "{slice_index}-tasks.{slice_name}.md"
    review:
      template: tasks
      against: "{output.slice-design}"
    checkpoint:
      trigger: on-fail         # lighter review, only pause on FAIL

  - name: implementation
    instruction_type: implementation
    context_files:
      - "{output.task-breakdown}"
      - "{output.slice-design}"
    agent:
      default_model: claude-sonnet-4-5  # default to Sonnet for implementation
      thinking: standard
      cwd: "{project_root}"
    output:
      type: code
      verification: tests-pass
    review:
      template: code
      diff_ref: "HEAD~1"       # review changes since last commit
    checkpoint:
      trigger: on-fail
```

#### Agent Selector

The "sometimes decisions" problem. Agent selection is currently a human judgment call based on task complexity, phase type, and prior experience. The ADP formalizes this as a selection strategy with defaults and overrides.

**Phase-based defaults** (the common case):
| Phase | Default Model | Thinking | Rationale |
|-------|--------------|----------|-----------|
| Architecture | Opus 4.6 | Extended | Highest complexity, cross-cutting concerns |
| Slice Design | Opus 4.6 | Extended | Complex design decisions, many dependencies |
| Review (any) | Opus 4.6 | Standard | Needs judgment but working within defined criteria |
| Task Breakdown | Opus 4.6 | Standard | Structured decomposition, moderate complexity |
| Implementation | Sonnet 4.6 | Standard | Well-defined tasks, strong execution capability |
| Simple/Mechanical | Haiku 4.5 | Standard | Formatting, simple transforms, boilerplate |

**Complexity-based escalation:**
When a phase produces output that the review flags as insufficient (CONCERNS or FAIL), the pipeline can escalate to a more capable model before pausing for human review. This is a single retry — not an infinite escalation loop.

```
Sonnet produces implementation → code review returns CONCERNS
  → retry with Opus (same context) → re-review
  → if still CONCERNS → checkpoint (human reviews)
```

**Human override:**
At any checkpoint, the human can specify model overrides for subsequent phases. This handles the "sometimes" cases — a slice that looks straightforward but turns out to need Opus for implementation.

**Future: Multi-provider selection:**
The AgentProvider Protocol in orchestration already supports multiple providers. When additional providers are integrated (OpenAI, Gemini, local), the selector extends to cross-provider decisions. Initial implementation is Claude-only since that's what's available now via SDK.

Multi-provider model map (future):
| Provider | Models | Auth | Notes |
|----------|--------|------|-------|
| Claude (SDK) | Opus 4.6, Sonnet 4.6, Haiku 4.5 | Max subscription | Primary, no API cost |
| Claude (API) | Same models | API key | Fallback, metered |
| OpenAI | GPT-5.3-Codex, etc. | API key (team account) | Via Codex CLI or API |
| Gemini | Gemini 3.0 Pro | API key | Via API |
| Local | Various | None/local | Ollama, vLLM compatible |

The selector would consider: cost (SDK free vs API metered), capability (model strengths per task type), availability (API limits, local GPU availability), and explicit user preferences.

#### Phase Runner

Executes a single phase within the pipeline:

1. **Context assembly:** Calls Context Forge MCP tools to build the prompt. Updates project state (`project_update` to set current slice, phase, instruction type), then calls `context_build` with any additional instructions.

2. **Agent dispatch:** Creates an agent via the orchestration agent registry with the selected model and configuration. Sends the assembled context as the task. Streams output.

3. **Output capture:** Collects the agent's output. For file outputs (slice designs, task files), verifies the file was created. For code outputs, verifies the working tree is in a reasonable state. Commits at phase boundaries per the ai-project-guide convention.

4. **Review execution:** If the phase defines a review, dispatches a review agent using the review workflow template system (orchestration slice 105). Collects the review verdict (PASS/CONCERNS/FAIL).

5. **Checkpoint evaluation:** Based on the review verdict and the phase's checkpoint trigger, decides: proceed to next phase, escalate (retry with stronger model), or pause for human.

6. **Compaction:** After phase completion, optionally compact project context. Calls `context_summarize` to update the project's recent events field with a summary of what this phase produced. This prevents context bloat across phases.

#### Checkpoint Manager

Manages the human interaction points in the pipeline.

**Checkpoint triggers:**
- `always` — pause after every execution of this phase (architecture work)
- `on-concerns` — pause when review returns CONCERNS or FAIL
- `on-fail` — pause only on FAIL (lighter touch for well-defined phases)
- `never` — fully automated (use with caution)

**When a checkpoint fires:**
1. Pipeline pauses execution
2. Presents the human with: phase output, review findings (if any), and suggested next action
3. Human can: approve and proceed, request revision (re-run phase with adjusted instructions), skip phase, abort pipeline, or override model/config for subsequent phases
4. Pipeline resumes based on human decision

**Implementation considerations:**
- CLI-first: checkpoints present as interactive prompts in the terminal
- State persistence: pipeline state is saved so checkpoints survive session interruptions
- DEVLOG integration: checkpoint decisions are logged for continuity

**The "slice doesn't make sense anymore" problem:**
This is the critical case you identified — where architectural assumptions shift during implementation and an agent wouldn't know to stop. This manifests as:
- A review that returns FAIL with structural concerns (not just quality issues)
- Implementation that reveals the slice's premise is wrong
- Dependencies that changed while the pipeline was running

The checkpoint system handles this through **mandatory human review at phase boundaries that involve architectural judgment** — specifically, the slice-design phase should always trigger a checkpoint on CONCERNS. The human reviews the design, confirms it still makes sense given current project state, and either approves or redirects.

For implementation phases, a "structural FAIL" (review finds the approach is wrong, not just buggy) should escalate to a human checkpoint even if the trigger is `on-fail`.

#### Compaction Strategy

Context management across the phase loop. Each phase gets a fresh agent (agents don't carry context between phases), but project state accumulates knowledge.

**Between phases:**
- Call `context_summarize` with instructions about what was just completed
- Update project state: current phase, last completed phase, output file paths
- The next phase's context assembly starts fresh from project state — not from the prior agent's conversation

**Between slices:**
- Heavier compaction: summarize the entire slice's journey (design → implementation)
- Archive detailed DEVLOG entries
- Update slice plan with completion status
- Reset phase-specific state

This mirrors the `/compact [with instructions]` pattern that's been working well manually. The automation just makes it consistent.

#### DEVLOG Integration

The DEVLOG has been invaluable for maintaining continuity. The pipeline automates DEVLOG entries:

- **Phase start:** Log which phase is beginning, which model is being used, input files
- **Phase completion:** Log output file, review verdict, any escalations
- **Checkpoint decisions:** Log human decisions and rationale
- **Errors/retries:** Log failures and recovery actions
- **Slice completion:** Summary entry covering the full slice lifecycle

---

## Pipeline Variants

### Standard Slice Pipeline (described above)
Full lifecycle: design → review → tasks → review → implementation → review → verification

### Design-Only Pipeline
For architectural exploration: design → review → checkpoint. Human takes output and decides what's next. Useful for complex slices that need multiple design iterations.

### Implementation-Only Pipeline  
When design and tasks already exist (human-written or from a prior run): implementation → review → verification. The most common "inner loop" during active development.

### Multi-Slice Pipeline
Wraps the standard pipeline in an outer loop over a slice plan:
```
for each slice in slice_plan:
  if slice.status == 'not started':
    run standard_slice_pipeline(slice)
    update slice_plan status
```
This is the "almost one-shot the whole product" scenario. Human checkpoints at each slice design gate.

### Review-Only Pipeline
Just run reviews: load existing artifacts, dispatch review agents, collect findings. No implementation. Useful for quality gates on human-written work.

---

## Prerequisites and Dependencies

### From Context Forge (must be complete)
- **Slice 7: MCP Server — Context Tools** (context_build, template_preview, prompt_list, prompt_get)
- **Slice 8: MCP Server — State Update Tools** (context_summarize, project_update)
- **Future Work #1: Project Schema Standardization** (nice-to-have — fileArch, fileHLD fields make context assembly more flexible)
- **Future Work #2: Command Grammar** (nice-to-have — `/forge:build` is cleaner than raw MCP tool calls in logs/DEVLOG, but not functionally required)

### From Orchestration (must be complete)
- **Slice 105: Review Workflow Templates** (arch, tasks, code review templates)
- **Slices 101-104: Foundation through CLI** (agent registry, SDK provider, CLI)

### Not Required (but beneficial when available)
- **Orchestration: Additional LLM Providers** — multi-provider selection becomes real
- **Context Forge: Streamable HTTP Transport** — enables persistent MCP server that survives across pipeline phases without stdio restart overhead
- **Orchestration: SDK Client Warm Pool / Session Cache** — reduces cold-start latency per phase

---

## Scope Boundaries

### In Scope (this initiative)
- Pipeline definition schema (YAML-based, declarative)
- Pipeline executor with phase sequencing
- Agent model selector with phase defaults and escalation
- Checkpoint manager (CLI-first interactive)
- Compaction between phases via Context Forge MCP
- DEVLOG automation
- Standard pipeline variants (single slice, multi-slice, design-only, implementation-only)
- Pipeline state persistence (survive session interruptions)
- CLI commands: `orchestration pipeline run`, `orchestration pipeline resume`, `orchestration pipeline status`

### Out of Scope (future work)
- GUI/web interface for pipeline monitoring
- Parallel phase execution (phases are sequential within a slice)
- Cross-slice parallelism (run multiple slices simultaneously) — architecturally possible but complex
- Automated complexity estimation for model selection — start with defaults + human override
- Cost tracking and optimization across providers
- Pipeline definition marketplace/sharing
- Integration with CI/CD systems

---

## Open Questions

1. **Pipeline definition storage:** Where do pipeline definitions live? Options: in the orchestration config directory, in the project's user/architecture/ directory, or as built-in presets with user overrides. Likely answer: built-in presets (standard-slice, design-only, etc.) with project-level overrides in a conventional location.

2. **Context Forge connection model:** Does the pipeline executor start a Context Forge MCP server per run, or expect one to be already running? For stdio transport, each MCP tool call spawns a process. For Streamable HTTP (future), a persistent server is more efficient. Initial implementation: stdio (simple, no server management). Migrate to HTTP when available.

3. **Review agent reuse:** Should review agents persist across multiple reviews in a pipeline run, or be fresh per review? Fresh is simpler and avoids context contamination. Persistent is faster (warm pool territory). Start fresh, optimize later.

4. **Checkpoint UX:** Interactive CLI prompts are the obvious first implementation, but what about long-running pipelines where the human isn't at the terminal? Options: write checkpoint state to a file and poll, send a notification (email, webhook), or integrate with a messaging system. CLI-first, notification as enhancement.

5. **Error recovery granularity:** If implementation fails mid-task-list (task 12 of 20 fails), does the pipeline retry the entire implementation phase or attempt to resume from task 12? The ai-project-guide's commit-per-task convention suggests resume is possible. Implementation: start with full-phase retry, add task-level resume as enhancement.

---

## Notes

- **Numbering:** This initiative claims the 160-band. Orchestration v2 uses 100-band (overflow to ~117), Context Forge restructure uses 140-band (overflow to ~151). The 160-band gives clear separation.
- **Project ownership:** The pipeline executor is orchestration code. Context Forge is consumed as a service. No changes to Context Forge are required (though schema standardization and command grammar are nice-to-haves that improve the integration).
- **Incremental value:** Each pipeline variant is independently useful. Even without the full multi-slice loop, the single-phase "dispatch agent with proper context and review" automation removes significant friction.
- **The "almost one-shot" qualifier:** The multi-slice pipeline cannot fully replace human architectural judgment. The checkpoint system is not a limitation to be minimized — it is the mechanism that preserves the human-as-architect role that makes the whole system work. The goal is not zero human involvement. The goal is human involvement only at decision points that require human judgment.
