---
docType: architecture
project: squadron
initiative: 360
dateCreated: 20260817
dateUpdated: 20260822
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

   **Validate shape, not just presence.** The plugin is upstream-maintained and actively developed,
   so the output contract can change under us. Before reading, confirm the required top-level keys
   exist — `project`, `nodes`, `edges`, `layers`, `tour` — and that `nodes`/`edges`/`layers` are
   non-empty arrays. On a missing or mistyped key, stop with an error naming the absent key and the
   graph's version, rather than proceeding with partial data. A renamed field in a future release
   must surface as a loud failure, never as a silently thinner document. Absence and malformation
   are different failures and get different messages.

   **Staleness warns, it does not block.** If `meta.json`'s `gitCommitHash` differs from `HEAD`,
   report the drift — including the commit distance — and let the PM choose to proceed or refresh.
   Blocking would force a full re-analysis after a typo commit, which is disproportionate; a graph a
   few commits behind is usually adequate for concept-level work.

   **The check requires git.** If `git` is unavailable or the directory is not a repository, the
   comparison cannot run. Skip it and say so explicitly, in both the console output and the
   provenance block — never skip silently. A silent skip defeats the check's entire purpose, which
   is to prevent a confidently wrong document built on a stale graph.
2. **Hygiene.** Ensure `.gitignore` ignores the plugin's scratch directories, idempotently — a
   named, announced side effect of the skill, not a silent one (see Working-tree hygiene).
3. **Read structure.** Extract `project`, `layers[]`, `tour[]`, and file-level nodes with their
   `summary`, `filePath`, and `complexity`.
4. **Read repo prose and signals.** The graph is not the only machine-readable source. The repo's
   own prose states intent where it exists — the root README is the canonical instance — and
   filesystem signals (a test tree, CI workflows, lint configuration) show development practice
   directly, even where the graph's ignore rules excluded those paths from analysis. Extract from
   these before asking a human anything.
5. **Interview — engagement context only.** Ask only for what no artifact can hold because it is
   about the engagement rather than the code: what the operator needs to do with this codebase, and
   any constraints or off-limits areas written down nowhere. Two questions, both skippable.
   Questions about the project's own nature — what problem it solves, who uses it, why it exists —
   are never asked: an existing codebase answers those through its artifacts or not at all.
6. **Draft.** Emit the planning artifacts, attributing structural claims to the graph, intent claims
   to the prose source that stated them (cited by file), and engagement claims to the interview.
   Before writing, show the derived project description for a single confirm-or-correct — the one
   extracted value most likely to be stale.

### Outputs

- `project-documents/user/project-guides/000-concept.{project}.md` — `docType: concept`, with the
  interview responses preserved verbatim in the **User-Provided Concept** section, and graph-derived
  structure in Refined Concept's Solution Approach and Initial Technical Direction.
- `project-documents/user/analysis/{index}-analysis.codebase-comprehension.md` — `docType: analysis`,
  the structural findings: layers, complexity hotspots, entry points, dependency observations.
- `project-documents/user/analysis/{index}-analysis.initiative-candidates.md` — `docType: analysis`,
  proposed initiatives for PM review. See below.

**Dependency on the concept document layout.** The skill relies on one structural guarantee from
`guide.ai-project.000-concept.md` (owned by the ai-project-guide, not by squadron): a section titled
**User-Provided Concept**, whose contents are authored by the PM and never rewritten by an AI. The
skill writes interview responses there verbatim and preserves anything already present. This is a
cross-repo dependency: if that guide renames the section or drops it, the skill must fail loudly
rather than write to a section that no longer means what it did. Slice design verifies the section
exists before writing and errors with a pointer to the guide if it does not.

**Initiative candidates are a proposal, not a plan.** They are written to their own `analysis`
document, never into `001-initiative-plan.{project}.md`, because an initiative plan is a commitment
document and a generated one that nobody reviewed is worse than none. Adopting a candidate is a
deliberate PM act of moving it into the real plan.

Each candidate is derived from one signal and states which: a layer boundary from `layers[]`, or a
complexity cluster from file-level `complexity` values within a layer. Each carries a title, the
signal and the node IDs supporting it, a one-paragraph scope statement, and observed dependencies
from `edges[]` between the implicated layers. A candidate the graph does not support is not
proposed — the skill emits fewer candidates rather than padding to a target count. What the PM
confirms is that the document is worth writing at all; they are not approving the candidates
themselves, which remain proposals until moved by hand.

### Provenance block

Every document generated by either capability carries a **Provenance** section, placed immediately
after the title so it cannot be missed, recording how the document was produced:

- Which capability generated it, and when.
- Source artifacts read, with their identity — for (a) the graph's `gitCommitHash` and
  `lastAnalyzedAt`; for (b) the concept and initiative-plan paths.
- **Staleness state**: whether the graph matched `HEAD`, the commit distance if not, or that the
  check was skipped because git was unavailable.
- Which sections came from source data and which from the interview.
- Any gap the skill flagged rather than filled.

The block is body prose, not frontmatter — frontmatter is validated against a fixed schema and a
reader never sees it, whereas the failure this guards against is a *human* trusting a stale or
partly-invented document. Placement above the content is deliberate for the same reason: a warning
at the bottom of a long document is a warning nobody reads.

The block is also what makes `status: not_started` legible on a generated draft — it states plainly
that a machine produced this and no human has reviewed it.

### Interview scope

The graph and the repo's own prose supply everything they can; the interview covers only
**engagement context** — facts about why squadron is being pointed at this codebase, which no
artifact can hold. Exactly two questions, asked once, both skippable:

1. What the operator needs to do with this codebase (add features, audit, take over maintenance,
   modernize) — the answer that makes generated initiative candidates targetable instead of generic.
2. Constraints or off-limits areas written down nowhere (a dependency that cannot be upgraded, a
   directory not to touch, an API that must stay stable).

Questions about the project's own nature are never asked. What a project is for, who uses it, and
how it is reached are answered by the README and the graph's surface evidence — or gap-marked when
those sources are silent. "Why now" and audience-evolution questions are neither asked nor
gap-marked: for an existing codebase they have no useful answer, and a generated document is not
improved by recording that nobody answered them.

The source model, per concept section:

| Concept section | Sources attempted | Human role |
|---|---|---|
| Overview | graph `project.description`, README lead | single confirm-or-correct before write |
| Problem & Motivation | README's own problem statement (cited); engagement answer | Q1 supplies the engagement half |
| Target Users | README; entry surfaces from graph | none — never asked |
| Solution Approach | `layers[]`, `tour[]` node ordering | none |
| Initial Technical Direction | `project.languages`, `project.frameworks`, `config` nodes | none |
| Development Approach | filesystem signals (test tree, CI workflows, lint config); constraints answer | Q2 supplies unwritten constraints |

**Extraction precedes any human contact**, and extracted content is never re-asked — the derived
project description is shown once for confirm-or-correct, which is cheaper for the PM than authoring
from scratch. Anything the PM declines to answer is written as an explicit unknown, per the concept
guide's "flag unknowns explicitly" rule, and recorded in the provenance block. It is never filled
with a plausible guess.

### Working-tree hygiene

The plugin's Phase 7 deliberately `mv`s scratch into `.understand-anything/.trash-<epoch>/` instead
of deleting it, to avoid tripping destructive-action gates on hardened hosts (upstream issue #301).
Phase 0 purges trash older than 7 days. Consequently a repo accumulates trash directories for a week.

Squadron adds a single idempotent `.gitignore` entry scoped to the scratch only:

```
.understand-anything/.trash-*/
```

**Who writes it, when, and what if it fails.** The skill itself performs the write, at the start of
every run, and reports what it did. The check is cheap and the entry may have been removed since
last time, so it is verified per-run rather than once. Writing is skipped when the entry is already
present — matched semantically, so an existing broader ignore of `.understand-anything/` satisfies
it and is not duplicated.

Failure is non-fatal and never silent. If `.gitignore` is absent it is created; if it cannot be
written (read-only, permission denied) or the directory is not a git repository, the skill reports
that the entry could not be added, names the reason, and continues to the analysis — hygiene is a
convenience, and failing the whole run over an untracked scratch directory would be
disproportionate. What is never acceptable is proceeding as though the write succeeded.

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

`project-documents/user/analysis/{index}-analysis.overview.md` — markdown, chosen because it converts
cleanly to PDF, slides, or a document without a toolchain commitment.

The artifact is called an **overview**: plain enough that any reader understands it without
explanation, and it claims no particular format (unlike "presentation", which would promise slides
squadron does not produce). Where a project needs more than one, the topic is appended —
`{index}-analysis.overview.{topic}.md`.

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

Every field resolves to exactly one of: content derived from its named source, or a gap marker
naming the missing input. There is no third outcome in which the skill supplies the content itself.
The overview also carries the provenance block described under Capability 1, recording which inputs
were read and which fields were marked as gaps.

### Translation rules

- **Strip internal vocabulary.** Slice indices, phase numbers, initiative indices, and docType
  frontmatter never appear. "Initiative 140 status draft" becomes "foundational work, in progress."
- **Features become outcomes.** "Weighted review convergence with decay-based finding dismissal"
  becomes "automated review that converges without human babysitting."
- **Derive, never invent.** Every claim traces to an input artifact. This is enforced structurally
  rather than by good intentions: the overview is assembled **field by field from named sources**
  (see the schema table), and a field whose source yields nothing is emitted as an explicit gap
  marker naming what is missing and which input would supply it — never as inferred prose. The rule
  applies to every field, not only Benefits: Approach, Scope, Risks, and Roadmap are each either
  sourced or marked. Gap markers appear in the document body, so the PM sees them where the content
  would have been, and are listed in the provenance block so they can be found without reading
  through. A document with gap markers is the expected output for a thin input, not a failure.
- **Status is honest.** Not-started work is described as planned, not implied complete. A client
  document that overstates progress is a liability, not a deliverable.
- **Audience variants share one document.** Client, management, and colleague readings differ in
  emphasis, not in facts. Emphasis is a generation parameter; the factual content is identical.

## Output Conventions

Both capabilities use existing directories and existing docTypes, and require no change to
`file-naming-conventions.md` and no gate change — which matters because the frontmatter gate
validates `docType` and `status` against fixed enums, so a new type could not be committed until the
gate was changed first.

Per-artifact placement:

| Artifact | Path | docType |
|---|---|---|
| Concept draft (a) | `user/project-guides/000-concept.{project}.md` | `concept` |
| Comprehension analysis (a) | `user/analysis/{index}-analysis.codebase-comprehension.md` | `analysis` |
| Initiative candidates (a) | see Capability 1 → Outputs | `analysis` |
| Overview (b) | `user/analysis/{index}-analysis.overview.md` | `analysis` |

Capability (a) therefore writes to **two** directories: the concept lands in `project-guides/`
because that is where the naming convention puts it, and everything else in `analysis/`.

**Index range.** The naming convention reserves **940-949** for "codebase analysis, research,
investigation" in `user/analysis/`. Generated documents draw from that range, incrementing per run
like the existing `940`/`941`/`942` tech-debt-audit series, where each run is an independent sample
rather than a revision of the last.

**Overflow into 950+ is sanctioned.** Ten slots with three already consumed is not enough for
comprehension runs and client documents alongside tech-debt audits, so generated documents take
remaining slots in the 900 band as needed rather than stopping at 949. The 900 band is heavily used
and its subdivision may need to be widened or re-cut later; that is a known future concern for the
naming convention as a whole, not a blocker for this initiative.

**Status values.** Generated frontmatter uses only `DocumentStatus` members — `complete`,
`in_progress`, `not_started`, `deprecated`, `deferred` (`src/squadron/documents/schema.py`).
Invented values such as `draft` are rejected by the gate.

**A generated document is written `not_started`.** The enum has no `needs_review` member, and none
is added here: `complete` would assert a PM review that has not happened, and `in_progress` would
claim an active author. `not_started` reads correctly for a machine-produced draft awaiting human
work — the *work* has not started, notwithstanding that a draft exists. The distinction matters
because a generated concept marked `complete` would be indistinguishable from a human-authored,
reviewed one. Review state is carried by the document's own provenance block, not by `status`.

**Prior art (retained, not superseded).** `user/reference/analyze-codebase-prompt.md` is an
experimental hand-authored three-phase codebase-analysis prompt on a different extraction backend
(`codebase-probe.py` + Repomix). It is a more cursory answer to the same question than
understand-anything gives, but materially lighter on token use. It is not part of any main process
and this initiative does not supersede or absorb it — it stays available as a low-cost alternative
path. Its analysis template and `[INFERRED]` convention are useful references when designing the
comprehension output, since both address separating known facts from inference.

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

**Capability (b) — `overview`** ships as `/sq:overview`, writing
`{index}-analysis.overview.md`. Registration matches capability (a)'s cost: `sq install-commands`
copies `commands/sq/*.md` wholesale (`src/squadron/cli/commands/install.py`), so adding
`commands/sq/overview.md` is sufficient — no installer, manifest, or CLI change, exactly as for the
pack skill. The two capabilities differ in delivery surface, not in registration burden. `brief` was rejected as vague about contents, `presentation` as
naming a format squadron does not produce, and `summary` because `commands/sq/summary.md` already
exists for conversation summaries.

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
- **Name for capability (b)** — `overview`, shipping as `/sq:overview`. Chosen over `brief`
  (vague), `presentation` (names a format squadron does not produce), and `summary` (taken by the
  existing conversation-summary command).
- **Client document audience handling** — one neutral document, not per-audience variants. The three
  readerships (client, management, colleagues) differ in emphasis, not in fact; three variants would
  mean three artifacts to keep true. An emphasis parameter is added only if real use demonstrates
  the need.
- **Output location and docType** — existing `user/analysis/` directory and `docType: analysis`, in
  the 940-949 reserved range. No new convention, no gate change.
- **Graph staleness** — warn and offer, never block; the warning is recorded in the generated
  document's provenance.

## Open Questions for Slice Design

- **Reuse of `analyze-codebase-prompt.md`.** How much of its analysis template and `[INFERRED]`
  convention transfers to the graph-backed path. The document itself is retained regardless.
- **Gap-marker syntax.** A single convention is needed for both capabilities. The retained
  `analyze-codebase-prompt.md` uses `[INFERRED]` for a related purpose and is the obvious candidate
  to extend rather than compete with.
