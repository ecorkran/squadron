---
docType: architecture
project: squadron
initiative: 360
dateCreated: 20260817
dateUpdated: 20260818
status: not_started
archIndex: 360
component: document-intelligence
---

# Architecture: Document Intelligence

## Overview

Initiative 340 made squadron a package manager for skill files. This initiative makes squadron a
**producer and consumer of project documents**. Two capabilities share that shape and nothing else:

1. **Codebase comprehension → planning artifacts.** Consume the knowledge graph produced by the
   `understand-anything` Claude Code marketplace plugin and turn it into squadron planning documents
   (concept, initiative-plan candidates, analysis) for a codebase that was never planned in squadron.
2. **Planning artifacts → client-facing document.** Consume squadron's own concept and initiative
   plan and turn them into a stakeholder-facing markdown document suitable for clients, management,
   and colleagues.

Both are document transforms with squadron's `project-documents/user/` layout and YAML frontmatter
conventions on at least one side. Neither adds runtime machinery to the engine.

**Scope:** Skill-level document transforms. No pipeline actions, no new agent providers, no changes
to the executor.

**Motivation:** Squadron's planning phases assume a greenfield project where a human writes the
concept first. Real engagements start from an existing codebase with no planning artifacts at all —
squadron's own repo is an instance (its initiative plan was retroactively generated and it has no
`000-concept` document). Separately, everything squadron produces today is engineer-facing; there is
no artifact to hand a stakeholder.

## Design Goals

- **Consume, do not re-implement.** The `understand-anything` plugin is upstream-maintained and
  actively developed (v2.8.1). Squadron reads its output; squadron does not fork, vendor, or wrap
  its pipeline.
- **Squadron-native output.** Everything written lands in `project-documents/user/` with correct
  `docType` frontmatter and index conventions, so downstream phases and `cf` introspection consume
  it unchanged.
- **Never fabricate intent.** A knowledge graph describes structure, not purpose. Motivation, target
  users, and business context are elicited from the PM or explicitly marked unknown — never invented
  from file names.
- **Leave the working tree clean.** Consuming a third-party tool must not force the user to
  hand-manage its scratch output.
- **Client document is derived, not authored.** The stakeholder document restates existing approved
  artifacts in stakeholder language. It is not a place where new claims about the project appear.

## Architectural Principles

- **Graph is an input, not a dependency.** Squadron reads `.understand-anything/knowledge-graph.json`
  as data. If the plugin is absent or the graph is missing, squadron reports what to run and stops —
  it never shells into the plugin's engine or reimplements a phase of it.
- **Interview fills only what the graph cannot answer.** The skill reads structure first, then asks a
  short focused set of questions scoped to the genuine gaps. Questions the graph already answers are
  never asked.
- **Ignore the scratch, track the artifacts.** Squadron manages `.gitignore` for the plugin's
  transient output only. The durable graph files remain tracked — they are project knowledge.
- **Separation of audience is a document boundary, not a tone setting.** The client document is a
  distinct artifact, not a rendering mode of an engineering document. It reuses the existing
  `analysis` docType rather than introducing a new one (see Output Conventions).

## Current State

- The `understand-anything` plugin is installed via the Claude Code marketplace
  (`Egonex-AI/Understand-Anything`, upstream — not a squadron fork), user scope, v2.8.1.
- Squadron has no awareness of it: `commands/sq/analysis.md` routes only `tech-debt-audit`, and the
  bundled `analysis` pack contains only `tech-debt-audit.md` (a squadron fork of
  `ksimback/tech-debt-skill`). Slice 344, which would have vendored understand-anything, was
  deprecated in favour of the marketplace plugin.
- No `.gitignore` entry in this repo mentions `understand` or `trash`.
- Squadron has no `000-concept` document and no client-facing artifact of any kind.

## The understand-anything Output Contract

Squadron consumes these paths, all under `$PROJECT_ROOT/.understand-anything/`:

| Path | Role for squadron |
|---|---|
| `knowledge-graph.json` | Primary input: `project`, `nodes[]`, `edges[]`, `layers[]`, `tour[]` |
| `meta.json` | Staleness signal: `lastAnalyzedAt`, `gitCommitHash`, `analyzedFiles` |
| `config.json` | `autoUpdate`, `outputLanguage` — read only, never written by squadron |
| `intermediate/scan-result.json` | Deliberately preserved upstream for incremental runs; squadron does not touch it |
| `.understandignore` | Analysis scope; squadron may reference it when explaining coverage gaps |
| `.trash-<epoch>/` | Transient scratch — the gitignore target |

**Graph shape** (from the plugin's own reference):

- `nodes[]` — `{id, type, name, filePath?, summary, tags[], complexity, languageNotes?}`. Node `id`
  is type-prefixed (`file:path`, `function:path:name`, `config:path`).
- `edges[]` — `{source, target, type, direction, weight}`, types including `imports`, `contains`,
  `calls`, `depends_on`, `configures`, `documents`.
- `layers[]` — `{id, name, description, nodeIds[]}`; every file is assigned to exactly one layer.
- `tour[]` — `{order, title, description, nodeIds[]}`, 5–15 pedagogical steps.

**Critical:** `tour[]` is produced by `/understand` Phase 6 (the `tour-builder` agent) and persisted
in the graph. It is *not* produced by `/understand-onboard`, which merely renders it. Squadron
therefore reads the tour as structured data with node IDs and never needs to parse onboard's prose.
The tour ordering is an expert judgment about which components matter and in what sequence — a
strong signal for a concept's Solution Approach section.

**Read discipline:** the graph is large. Grep for the needed section before reading; never load the
whole file into context. File-level node types (`file`, `config`, `service`, `endpoint`, `schema`,
`table`, `pipeline`, `document`, `resource`) are sufficient for planning artifacts; function- and
class-level nodes are not read.

### Relationship to the plugin's own skills

`/understand-onboard` and `/understand-explain` are **descriptive** — they answer "what is this
codebase?" for a new engineer. Onboard renders six fixed sections to `docs/ONBOARDING.md` with no
frontmatter and no notion of squadron. Explain is an interactive per-file deep dive that produces no
artifact.

Squadron's capability is **prescriptive** — "what should we do about this codebase?" — and writes
squadron-native planning documents. Same source data, different consumer, no functional overlap.
Squadron does not replace or wrap either skill.

## Capability 1: Comprehension → Planning Artifacts

### Flow

1. **Preconditions.** Verify the plugin is installed and `knowledge-graph.json` exists. If the graph
   is missing, report the exact command to run (`/understand`) and stop.

   **Staleness warns, it does not block.** If `meta.json`'s `gitCommitHash` differs from `HEAD`,
   report the drift — including the commit distance — and let the PM choose to proceed or refresh.
   Blocking would force a full re-analysis after a typo commit, which is disproportionate; a graph a
   few commits behind is usually adequate for concept-level work. The warning must be prominent and
   must appear in the generated document's provenance, because the genuine failure mode is a
   confidently wrong concept doc built on a stale graph without the reader knowing.
2. **Hygiene.** Ensure `.gitignore` contains an entry for the plugin's scratch directories,
   idempotently (see below).
3. **Read structure.** Extract `project`, `layers[]`, `tour[]`, and file-level nodes with their
   `summary`, `filePath`, and `complexity`.
4. **Interview.** Ask a short focused set of questions covering only what the graph cannot supply:
   problem and motivation, target users, business context, and known constraints. Structural
   questions are never asked — the graph already answered them.
5. **Draft.** Emit the planning artifacts, attributing structural claims to the graph and intent
   claims to the interview.

### Outputs

- `project-documents/user/project-guides/000-concept.{project}.md` — `docType: concept`, with the
  interview responses preserved verbatim in the **User-Provided Concept** section (which is sacred
  per project convention and never rewritten), and graph-derived structure in Refined Concept's
  Solution Approach and Initial Technical Direction.
- `project-documents/user/analysis/{index}-analysis.codebase-comprehension.md` — `docType: analysis`,
  the structural findings: layers, complexity hotspots, entry points, dependency observations.
- **Initiative-plan candidates** — proposed initiatives derived from layer boundaries and complexity
  clustering, offered for PM review. Written only on explicit confirmation, because an initiative
  plan is a commitment document; an unreviewed generated one is worse than none.

### Interview scope

The graph supplies structure; the interview supplies intent. Question set is bounded and derived
from the concept guide's own section list:

| Concept section | Source |
|---|---|
| Problem & Motivation | Interview — graph cannot infer why |
| Target Users | Interview — graph cannot infer who |
| Solution Approach | Graph (layers, tour) + interview confirmation |
| Initial Technical Direction | Graph (languages, frameworks, dependencies) |
| Development Approach | Interview — methodology and constraints |

Anything the PM declines to answer is written as an explicit unknown, per the concept guide's "flag
unknowns explicitly" rule. It is never filled with a plausible guess.

### Working-tree hygiene

The plugin's Phase 7 deliberately `mv`s scratch into `.understand-anything/.trash-<epoch>/` instead
of deleting it, to avoid tripping destructive-action gates on hardened hosts (upstream issue #301).
Phase 0 purges trash older than 7 days. Consequently a repo accumulates trash directories for a week.

Squadron adds a single idempotent `.gitignore` entry scoped to the scratch only:

```
.understand-anything/.trash-*/
```

**Not ignored:** `knowledge-graph.json`, `meta.json`, `config.json`, and `.understandignore` remain
tracked. They are durable project knowledge, and tracking `meta.json` makes graph staleness visible
in review. Squadron does not delete trash directories — the upstream purge owns that lifecycle, and
squadron deleting directories it did not create would reintroduce exactly the destructive-action
problem the upstream design avoids.

## Capability 2: Planning Artifacts → Client-Facing Document

### Inputs

- **Required:** the initiative plan (`001-initiative-plan.{project}.md`).
- **Optional:** the concept (`000-concept.{project}.md`). When absent, the skill degrades gracefully
  and sources purpose from the initiative plan plus interview, rather than failing. This is the
  common case for retroactively planned projects — squadron itself included — so it is the tested
  path, not an edge case.

### Output

`project-documents/user/analysis/{index}-analysis.{name}.md` — markdown, chosen because it converts
cleanly to PDF, slides, or a document without a toolchain commitment. See Output Conventions for
index allocation and the working name of this artifact.

### Document field schema

The document communicates purpose and benefit to a non-engineering reader. Fields, with source:

| Field | Content | Source |
|---|---|---|
| Purpose | What this project is, one paragraph, no jargon | Concept Overview / initiative plan |
| Problem | The situation motivating the work | Concept Problem & Motivation |
| Audience | Who benefits and how | Concept Target Users |
| Approach | How it is being solved, at a level a non-engineer follows | Concept Solution Approach |
| Benefits | Concrete outcomes, phrased as outcomes not features | Derived from initiative descriptions |
| Scope | What is explicitly included and excluded | Initiative plan + non-goals |
| Status | Progress in plain terms, no phase numbers or slice indices | Initiative statuses |
| Roadmap | Sequenced themes with dependency-driven ordering, no indices | Initiative plan + dependencies |
| Risks / Open Questions | Known unknowns stated honestly | Initiative plan notes |

### Translation rules

- **Strip internal vocabulary.** Slice indices, phase numbers, initiative indices, and docType
  frontmatter never appear. "Initiative 140 status draft" becomes "foundational work, in progress."
- **Features become outcomes.** "Weighted review convergence with decay-based finding dismissal"
  becomes "automated review that converges without human babysitting."
- **Derive, never invent.** Every claim traces to an input artifact. If a benefit is not supported by
  the concept or initiative plan, it is not asserted — the skill flags the gap for the PM instead.
- **Status is honest.** Not-started work is described as planned, not implied complete. A client
  document that overstates progress is a liability, not a deliverable.
- **Audience variants share one document.** Client, management, and colleague readings differ in
  emphasis, not in facts. Emphasis is a generation parameter; the factual content is identical.

## Output Conventions

Both capabilities write to the existing `project-documents/user/analysis/` directory with the
existing `docType: analysis`. No new directory, no new docType, and no change to
`file-naming-conventions.md` — which matters because the frontmatter gate validates `docType` and
`status` against a fixed enum, so a new type would require a gate change before anything could be
committed.

**Index range.** The naming convention reserves **940-949** for "codebase analysis, research,
investigation" in `user/analysis/`. Generated documents draw from that range, incrementing per run
like the existing `940`/`941`/`942` tech-debt-audit series, where each run is an independent sample
rather than a revision of the last.

**Known constraint — the range is small.** Ten slots, three already consumed. Comprehension runs and
client documents share the range with tech-debt audits, and a client engagement would spend several
on arrival. The convention does not define an overflow rule (950+ is maintenance/tasks). The first
slice design must therefore establish an allocation rule: which sub-range each artifact type draws
from, and what happens at 949. This is a real ceiling, not a theoretical one.

**Status values.** Generated frontmatter uses only enum members — `complete`, `in_progress`,
`not_started`, `deprecated`, `deferred`. Invented values such as `draft` are rejected by the gate.

**Prior art.** `user/reference/analyze-codebase-prompt.md` is an existing hand-authored three-phase
codebase-analysis prompt built on a different extraction backend (`codebase-probe.py` + Repomix). It
shares this initiative's discipline of separating known facts from inference and flagging gaps
explicitly. It is an input to slice design — its analysis template is a tested structure for the
comprehension output, and its `[INFERRED]` convention is directly applicable to graph-derived claims.

## Delivery

**Capability (a) — `understand`** ships as a skill in the existing bundled `analysis` pack, routed
by the existing dispatcher as `/sq:analysis understand`. The name deliberately matches the upstream
plugin's `/understand`, because the two are the same concept at different stages: the plugin builds
comprehension, squadron consumes it. Dispatcher namespacing keeps the names distinct in use, so
there is no collision. Adding it requires a new pack file plus three edits to
`commands/sq/analysis.md` (valid-skills line, usage block, skill section) — the same shape as the
deprecated slice 344, and no installer, manifest, or CLI change.

**Capability (b)** ships as a first-party command in `commands/sq/`, not as a pack skill. It reads
squadron's own document layout and writes for stakeholders; nothing about it audits a codebase, so
routing it through the analysis dispatcher would make that dispatcher's name inaccurate. It belongs
alongside `sq:review` and `sq:task`.

**Naming is unresolved for (b).** `brief` is the working placeholder, not a decision — it is
serviceable but not liked, and `presentation` was rejected as too long and overstating what the
artifact is. The command name, the document name, and the `{name}` slot in the output path all
depend on settling this. It must be resolved before the capability-(b) slice is designed.

## Non-Goals

- **Forking or vendoring understand-anything.** Settled by slice 344's deprecation. Squadron consumes
  the marketplace plugin's output and nothing more.
- **Squadron installing the marketplace plugin.** Squadron's installer copies markdown; driving
  Claude Code's plugin system is out of scope. The skill detects absence and instructs.
- **Re-implementing graph construction.** Scan, batch, analyze, and assemble belong to the plugin.
- **A pipeline action for either capability.** These are skills. If pipeline integration is wanted
  later, it is a separate initiative built on the action protocol.
- **Non-markdown client output.** PDF, slides, and HTML are downstream conversions of the markdown,
  not squadron's responsibility.
- **Automatic initiative-plan generation.** Candidates are proposed for review; squadron does not
  silently author a commitment document.

## Dependencies

- **[100]** — CLI command registration for any command surface.
- **[340]** — skill pack install mechanism and the `sq:analysis` dispatcher pattern.
- **External:** `understand-anything` marketplace plugin (Capability 1 only). Capability 2 has no
  external dependency.

Independent of 140, 180, 240, 260, 280, 300, and 320 — no pipeline, judging, or agent-provider
machinery is involved.

## Resolved Design Decisions

Settled during architecture review (20260818):

- **Pack placement** — capability (a) joins the existing bundled `analysis` pack as
  `/sq:analysis understand`; capability (b) ships as a first-party `commands/sq/` command. No new
  pack is introduced.
- **Skill name for (a)** — `understand`, matching the upstream plugin rather than inventing a
  synonym. Dispatcher namespacing prevents collision, and a second vocabulary word for one concept
  is a cost with no benefit.
- **Client document audience handling** — one neutral document, not per-audience variants. The three
  readerships (client, management, colleagues) differ in emphasis, not in fact; three variants would
  mean three artifacts to keep true. An emphasis parameter is added only if real use demonstrates
  the need.
- **Output location and docType** — existing `user/analysis/` directory and `docType: analysis`, in
  the 940-949 reserved range. No new convention, no gate change.
- **Graph staleness** — warn and offer, never block; the warning is recorded in the generated
  document's provenance.

## Open Questions for Slice Design

- **Name for capability (b).** `brief` is a working placeholder that has not been accepted.
  Blocks the (b) slice: the command name, document name, and output filename all derive from it.
- **Index allocation within 940-949.** Seven slots remain and three artifact types now compete for
  them. Needs an explicit sub-range rule and an overflow answer for 949.
- **Interview question set for (a).** The concept sections needing PM input are identified; the
  actual wording, ordering, and how much the graph can pre-fill to shorten the interview are not.
- **Reuse of `analyze-codebase-prompt.md`.** How much of its analysis template and `[INFERRED]`
  convention transfers to the graph-backed path, and whether that reference document is superseded,
  retained as the non-graph fallback, or merged.
