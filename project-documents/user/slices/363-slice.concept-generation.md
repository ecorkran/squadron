---
docType: slice-design
slice: concept-generation
project: squadron
parent: 360-slices.document-intelligence.md
dependencies: [361, 362]
interfaces: [364, 366]
dateCreated: 20260822
dateUpdated: 20260823
status: complete
review: none
---

# Slice Design: Concept Generation

## Overview

Produce `000-concept.{project}.md` for an existing codebase that has no concept document — the
Phase 0 entry point for pointing squadron at a repo that has never had cf/sq planning artifacts.

This design replaces a rejected predecessor. The rejected design treated the knowledge graph as the
only machine-readable source, so every section the graph could not fill defaulted to interviewing
the human — producing six generic product-discovery questions ("what problem does this solve and for
whom?", "why now?") whose answers, for an existing codebase, either sit in the repo's own README or
do not matter at all. The PM rejected the question set outright.

The operative rule now: **an existing codebase answers questions about its own nature through its
artifacts, or not at all.** Three machine-readable sources are extracted before any human contact:

1. **The graph** — structure: layers, tour, languages, frameworks, entry points. Unchanged from 362.
2. **The repo's own prose** — intent: the root README, cited by file. A repo's README states what it
   is, what problem it addresses, and who reaches it, in its authors' own words.
3. **Filesystem signals** — development practice: a test tree, CI workflows, lint configuration,
   observed directly. The graph's ignore rules routinely exclude these paths from analysis;
   the filesystem cannot hide them.

The human is asked exactly one category of thing: **engagement context** — facts that are about why
squadron is being pointed at this codebase, which no artifact can hold. Two questions, both
skippable, plus one confirm-or-correct on the derived project description before the file is
written. Worst-case total human cost: two short answers and one yes/no.

Everything here is markdown edits to `commands/analysis/understand.md`, adding a sibling flow
section alongside Flow: Comprehension Analysis. No Python is added.

## Value

The highest-leverage output of initiative 360: it turns an unplanned existing codebase into
squadron's Phase 0 entry point, with near-zero interrogation of the operator. The concept document
it writes is the input 364's initiative candidates and every later cf phase consume.

## Technical Scope

**Included** — all within `commands/analysis/understand.md`:

- A **flow selector**: `concept` becomes a recognized argument; everything else non-default stays
  unrecognized.
- The **three-source extraction model** and its per-section mapping.
- The **two engagement questions**, fixed wording, and the single description confirmation.
- The **User-Provided Concept contract**: verbatim write, preservation, loud failure when the
  cross-repo layout has changed.
- **Preconditions** for running against a bare repo: graph present (361 preflight, unchanged),
  ai-project-guide installed, project name resolvable.
- **Re-run semantics** for the one fixed-path output in this initiative.
- Concept-specific **frontmatter and provenance**, and `[INFERRED]` governance for this flow.

**Excluded (owned elsewhere):**

- Initiative candidates — slice 364. Dispatcher routing, README, plugin-absent guidance — slice 366.
- Any change to the Preflight Graph Contract, the comprehension flow, `src/squadron/`, the
  installer, the frontmatter gate, or `guide.ai-project.000-concept.md`.
- Prose mining beyond the root README (docs/ trees, wikis). Deliberately excluded: unbounded cost,
  unpredictable relevance. The README is the one prose artifact a repo reliably aims at a newcomer.

## Preconditions and the /cf:onboard boundary

The target scenario is a repo with **no user-level cf/sq artifacts** — no concept, no initiative
plan. It is not a repo with no setup at all. The flow requires:

1. **The graph** — produced by the upstream plugin's `/understand`. Missing/malformed/stale handling
   is the 361 preflight, executed unchanged.
2. **The ai-project-guide installed** — the concept guide's layout is read from
   `project-documents/ai-project-guide/project-guides/guide.ai-project.000-concept.md` at write
   time. On a raw client repo this means project setup (`cf init` or `/cf:onboard`) has run first.
   If the guide tree is absent, stop and name the setup step — this is a terminal precondition
   failure, not a gap.
3. **A resolvable project name** — from the cf project registration. Never from the graph (see
   Output conventions). If no registration resolves a name, **stop**, naming the setup step —
   deriving a filename from the graph's `project.name` is prohibited, so there is no fallback and
   this failure is terminal, same family as precondition 2.

**Boundary:** `/cf:onboard` owns project setup and the conversational, greenfield concept path — a
human describing what they want to build. This flow owns the artifact-derived, brownfield path — a
machine drafting from what already exists. They compose (onboard sets up the scaffolding this flow
requires) and do not overlap: neither contains the other's interaction model.

## Dependencies

- **[361]** — Preflight Graph Contract, gap-marker syntax, provenance block shape, `model:` rule.
  Executed unchanged.
- **[362]** — the extraction mapping, the corrected file-level selector
  (`type != "function" and type != "class"`), and the coverage facts (`.understandignore` scope,
  `meta.json` `analyzedFiles`) that supply Solution Approach's coverage boundary.
- **Cross-repo:** `guide.ai-project.000-concept.md` — document structure and the **User-Provided
  Concept** section. Verified at write time, not assumed.

## Verified facts

Measured against this repo on 20260822 (graph v2.8.1, `gitCommitHash` `1bfbca1`, 925 nodes /
2184 edges / 10 layers / 15 tour steps).

| Fact | Value |
|---|---|
| `project.name` | **`squadron-ai`** — distribution name, not the project name |
| `project.description` | present; upstream prose, **stale** — describes an earlier, narrower squadron |
| `project.languages` / `.frameworks` | 4 / 10, both non-empty |
| Graph nodes under `tests/` / `.github/` | **0 / 0** — excluded by `.understandignore` |
| Filesystem: `tests/` | **present** — real test tree at repo root |
| Filesystem: `.github/workflows/` | **present** — `ci.yml` |
| Filesystem: lint/test config | **present** — `[tool.ruff]`, `[tool.pytest.ini_options]` in `pyproject.toml` |
| Root `README.md` | **present**; lead states what squadron is, what it does, and how it is reached |
| Existing `000-concept.squadron.md` | absent — `user/project-guides/` holds only the initiative plan |
| Concept guide `## User-Provided Concept` | present, exactly once |

Two of these decide the design directly:

- **The graph/filesystem divergence on tests and CI.** The graph says squadron has no tests and no
  CI; the filesystem says it has both, plus lint and test configuration. Development Approach is
  therefore sourced from **filesystem signals, never the graph** — the prior design's treatment of
  this section (interview-primary because the graph was empty) asked a human for what `ls` answers.
- **The README states intent.** Its opening two paragraphs answer "what is this, what problem does
  it address, who reaches it and how" in the authors' own words. Problem & Motivation and Target
  Users are therefore **prose-extraction sections, never interview sections**.

## Technical Decisions

### Flow selection

Unchanged mechanism from the comprehension flow's argument handling, narrowed:

- No argument, or `comprehension` → Flow: Comprehension Analysis (unchanged).
- `concept` → this flow.
- Anything else → unrecognized; say so and stop. `candidates` remains unrecognized until 364.

Selection is by explicit argument only. The skill never infers a flow from repo state — the absence
of a concept document never auto-triggers this flow.

Preflight runs in full for both flows, unchanged — including its `.gitignore` hygiene write, which
the shared contract performs at the start of every run before any document is written. The concept
flow adds no hygiene behavior of its own and skips none.

### The three-source extraction model

Per section, extraction runs against the sources named in the table below, **in order, before any
human contact**. Each source has a distinct attribution style:

- **Graph fields** — the claim names its field inline, as in the comprehension flow.
- **Repo prose** — the claim cites its file (`README.md`), and quoted material is quoted, not
  paraphrased into squadron's own voice.
- **Filesystem signals** — a fixed checklist, reported as observations with paths: test tree
  (`tests/` or `test/` at root), CI workflows (`.github/workflows/` non-empty, or `.gitlab-ci.yml`),
  lint/format/test configuration (tool tables in `pyproject.toml`, `.pre-commit-config.yaml`,
  `.eslintrc*`/`.prettierrc*`). The checklist is closed — a signal outside it is not probed.
  **Absence of a signal is an observation, not a gap**: "no test tree observed at the repo root" is
  a true, useful statement about development practice, and the source that produced it was fully
  readable.

**README resolution:** the root-level README, case-insensitive, `README.md` preferred over other
extensions when several exist. Nothing below the root is read. A repo with no root README loses the
prose source for this run: affected sections fall back to graph fields where mapped, and to gap
markers where not.

### Per-section mapping

The concept guide's own sections, in its order. Each row is binding.

| # | Section | Sources, in order | Human role |
|---|---|---|---|
| 1 | Overview | graph `project.description`; README lead | single confirm-or-correct before write |
| 2 | User-Provided Concept | engagement answers, verbatim | the two questions |
| 3 | Problem & Motivation | README problem statement (cited); Q1 answer for the engagement half | none beyond Q1 |
| 4 | Target Users | README; graph entry surfaces (`entry-point` nodes, `frameworks`) | none — never asked |
| 5 | Solution Approach | `layers[]` names + descriptions; `tour[]` order; coverage boundary | none |
| 6 | Initial Technical Direction | `project.languages`, `.frameworks`; `config` nodes; `entry-point` nodes | none |
| 7 | Development Approach | filesystem signals checklist; Q2 answer for unwritten constraints | none beyond Q2 |

**Dropped, not gap-marked:** "why now", audience-evolution, and methodology-preference questions
appear nowhere — not asked, not marked absent. For an existing codebase they have no useful answer,
and a generated document is not improved by recording that nobody answered them. A gap marker is
reserved for content a section *needs* whose source is missing; these are topics the document does
not need.

**Solution Approach's coverage boundary** is unchanged from the prior design's one sound
measurement: sourced from 362's coverage facts (`.understandignore` active patterns, `meta.json`
`analyzedFiles` reconciled against the file-level node count), stating which parts of the repo the
graph never saw — on this repo, everything outside `src/` and root config, including the markdown
command surface.

### The engagement interview

Exactly two questions. Fixed wording — not improvised, not extended. Asked once, as one block,
after extraction and before drafting, so the answers can inform Problem & Motivation and Development
Approach in a single drafting pass.

```
1. What do you need to do with this codebase — add features, audit it, take over
   maintenance, modernize it, something else?

2. Are there constraints or off-limits areas that aren't written down anywhere — a
   dependency that can't be upgraded, a directory not to touch, an API that must stay
   stable?
```

Both are skippable without argument or follow-up. A declined question produces a gap marker at the
point of absence (naming the interview as the input) and an entry in the provenance block's
declined-questions line — never a plausible guess, never a silent omission.

**Why these two and no others:** they are the only questions whose answers no artifact can hold,
because they are facts about the engagement rather than the code. Q1 is also what makes 364's
initiative candidates targetable — "we are here to modernize" and "we are here to audit" produce
different candidate sets from the same graph.

**Answers land verbatim in User-Provided Concept.** The operator's words about the engagement are
the user-provided concept for a brownfield run. They are additionally the source for Problem &
Motivation's engagement half (Q1) and Development Approach's constraints (Q2) — used twice, asked
once.

### The single confirmation

After drafting and before the file write, show the derived project description — the Overview
paragraph assembled from `project.description` and the README lead — together with the graph's
`lastAnalyzedAt`, and ask the operator to confirm or correct it. One interaction, about content
already extracted; never a request to author from nothing.

- **Confirmed** → provenance records the Overview as extracted-and-confirmed.
- **Corrected** → the correction is what lands in the body; the original is not retained beside it;
  provenance records extracted-and-corrected.
- **Refused/unavailable** → the draft proceeds with the description attributed to its sources and
  provenance records extracted-unconfirmed. The flow never stalls on a confirmation.

This is the only confirmation in the flow. Graph-derived structure (layers, languages, frameworks)
is not confirmed section-by-section — it is attributed, and the PM edits the draft afterward if it
is wrong. The rejected design's per-section confirm-or-correct cycle is gone.

### The User-Provided Concept contract

Unchanged in substance from the prior design — it was sound. Before any write:

1. Confirm `guide.ai-project.000-concept.md` is readable at its expected path. Unreadable or absent
   → **stop**, naming the path. If the whole ai-project-guide tree is absent, name the setup step
   (`cf init` / `/cf:onboard`) instead of just the file.
2. Confirm its document-structure block contains a section titled exactly
   `## User-Provided Concept`. Absent or renamed → **stop**, naming the guide, the expected title,
   and that the layout appears changed upstream.

Neither failure is a gap marker: a gap marker means "this document is missing something"; these mean
"this document cannot be correctly written at all."

**Write verbatim** — the operator's answers as given, not summarized, reworded, or
grammar-corrected. **Preserve what is there** — pre-existing section content survives untouched; new
answers append below under a dated subheading.

### Re-run semantics

Unchanged from the prior design — the concept's path is fixed, so a re-run meets an existing
document:

- No existing document → write it.
- Existing document → never overwrite. Report it; offer augment or stop; **stop is the default**.
- Augment appends to User-Provided Concept per the preservation rule and fills only Refined Concept
  sections that are empty or hold exactly a `[GAP: ...]` marker — the mechanical refillability test.
  A section with real content is left alone.
- A human-edited concept is never rewritten from a graph.

### `[INFERRED]` governance

The shared Gap markers section already reserves `[INFERRED]` for this flow. The checkable rule:

> A sentence carries `[INFERRED]` when it is derived from a named graph field but asserts something
> the field does not literally state. A sentence that restates a field carries no marker. A sentence
> with no source behind it does not belong in the document.

Prose sources interact with the rule by **citation, not inference**: a claim the README states is
cited to `README.md` and carries no marker — the source literally says it. The marker's home remains
graph-structural inference, e.g. a tour-order-implies-importance claim in Solution Approach. A
PM-confirmed inference stays marked; confirmation changes the provenance entry, not the body.

`[INFERRED]` sentences are listed in provenance alongside gap markers.

### Output conventions

**Path:** `project-documents/user/project-guides/000-concept.{project}.md`, `{project}` resolved
from the cf project registration — **never `project.name` from the graph** (measured: the graph
carries the distribution name `squadron-ai`). Where the two differ, the difference is stated in the
Overview and the graph's value recorded in provenance.

**Frontmatter** — the concept guide's schema with squadron's generated-document rules:

```yaml
---
docType: concept
layer: project
phase: 0
phaseName: concept
project: {project}
audience: [human, ai]
description: Concept for {project}
dependsOn: []
dateCreated: {YYYYMMDD}
dateUpdated: {YYYYMMDD}
status: not_started
model: {id of the model generating this document}
---
```

`model:` follows 361's rule unchanged: the real generating model id or an explicit stop, never a
placeholder.

**Provenance block** — 361's shape with concept-specific content:

- **Generated by** names this flow.
- **Source** names the graph (with identity), the README when read, the filesystem signals checked,
  and the concept guide path with a statement that its User-Provided Concept section was verified
  present.
- **Section sourcing** records one outcome per section from: extracted-from-graph,
  extracted-from-prose (with file cite), observed-signals, interview, extracted-and-confirmed,
  extracted-and-corrected, extracted-unconfirmed, declined, gap.
- **Engagement questions** — both questions with answered/declined per question.
- **Inferred claims** — every `[INFERRED]` sentence, or none.
- **Flagged gaps**, **staleness**, **review state** — as in 361.

### Read discipline

362's discipline, unchanged, for the graph: field-scoped `jq` selections only, whole graph never
loaded, no `function`/`class` node read. This flow reads strictly less of the graph than the
comprehension flow. The README and filesystem checks are ordinary file reads outside the graph and
carry no special discipline beyond the bounded lists above.

## Integration Points

- **[364]** — extends the flow-selection mechanism for `candidates`; **when a concept exists**,
  consumes Q1's engagement answer (via the written concept) to order its candidates. Settled in
  364's design: the concept is an optional input there, affecting ordering only, and 364 runs
  correctly on a repo where this flow has never been invoked.
- **[366]** — adds `/sq:analysis understand concept` routing; this slice is exercised by invoking
  the skill file directly, as 361/362 were.
- **`/cf:onboard`** — provides the setup this flow's preconditions require; owns the greenfield
  conversational path. See Preconditions.

## Success Criteria

1. `concept` is recognized; no argument and `comprehension` route to the comprehension flow;
   anything else stops as unrecognized.
2. The only questions ever asked are the two fixed engagement questions, verbatim, asked once —
   plus the single description confirmation. No question about the project's own nature is asked,
   and extraction demonstrably precedes all interaction.
3. Every intent claim cites its prose source by file; every structural claim names its graph field;
   Development Approach derives from the filesystem checklist with absences reported as
   observations, not gaps.
4. Dropped topics (why-now, audience evolution, methodology preference) appear nowhere in the
   document — neither as content nor as gap markers.
5. A declined question produces a gap marker in the body and a declined entry in provenance; no
   declined answer is filled with prose.
6. User-Provided Concept holds the engagement answers verbatim; pre-existing content survives
   re-runs untouched, with new content appended under a dated subheading.
7. With the concept guide absent, unreadable, or missing the expected section title, the flow stops
   loudly naming the guide (or the missing setup step) and the expected title; it never writes to a
   substitute or remembered layout.
8. An existing `000-concept.{project}.md` is never overwritten: report, augment-or-stop, default
   stop, mechanical refillability for augment.
9. Output frontmatter passes `cf validate frontmatter` with `docType: concept`,
   `status: not_started`, and a real `model:` id; the filename uses the cf project name, never the
   graph's `project.name`, with any divergence stated in the Overview and recorded in provenance.
10. Provenance carries per-section sourcing over the full outcome set, the engagement-questions
    line, and the inferred-claims line; every `[INFERRED]` sentence satisfies the checkable rule.
11. The whole graph is never loaded; no `function`/`class` node is read; the only changed non-
    document file is `commands/analysis/understand.md`.
12. Running against squadron produces a concept a PM would edit rather than discard.

## Verification Walkthrough

Draft — refined during Phase 6. Run from the repo root on branch `363-slice.concept-generation`.
Pre-366, the flow is exercised by opening `commands/analysis/understand.md` in a Claude Code session
and instructing it to run the concept flow.

**1. Re-verify the source facts.**

```
jq -r '.project.name' .understand-anything/knowledge-graph.json          # squadron-ai
jq -r '.project | "langs=\(.languages|length) fw=\(.frameworks|length)"' \
  .understand-anything/knowledge-graph.json                              # both non-zero
ls tests/ .github/workflows/ README.md                                    # all present
grep -c '^## User-Provided Concept' \
  project-documents/ai-project-guide/project-guides/guide.ai-project.000-concept.md   # 1
ls project-documents/user/project-guides/                                 # no 000-concept.*
```

**2. Flow selection.** No argument and `comprehension` run the comprehension flow; `concept` runs
this flow; `candidates` stops as unrecognized.

**3. Happy path.** Run the concept flow against squadron. Answer both engagement questions with real
answers; when shown the derived description, correct it (the graph's is measurably stale — this
exercises the correction outcome in the same run). Confirm in the written `000-concept.squadron.md`:

- filename uses `squadron`; the Overview states the `squadron-ai` divergence;
- both questions were asked once, after extraction, before drafting; nothing else was asked;
- User-Provided Concept holds the answers verbatim (diff against answers as given);
- Problem & Motivation and Target Users cite `README.md`; no interview content beyond Q1's half;
- Development Approach reports the observed signals (`tests/`, `ci.yml`, ruff/pytest config) with
  paths, plus Q2's constraints;
- Solution Approach names layers, tour ordering, and its coverage boundary;
- the corrected description is in the body; provenance records extracted-and-corrected;
- provenance carries the engagement-questions and inferred-claims lines and the graph's
  `project.name`;
- `cf validate frontmatter` passes on the file.

**4. Decline path** (scratch copy of the tree): decline both questions. Document still written;
gap markers where Q1/Q2 content would land; provenance lists both as declined; no section holds
prose without a source.

**5. Contract failure** (scratch copy of the guide only — never the real one): rename the section
heading in the copy, point the check at it, confirm the loud stop naming guide and expected title,
and that nothing is written.

**6. Re-run** against the real document from step 3: reports the existing document, defaults to
stop; when told to augment, appends to User-Provided Concept under a dated subheading and leaves
populated sections byte-identical (`git diff`).

**7. Discipline and scope.** No graph read without a `jq` field selection; no `function`/`class`
node read; `git status` on `.understand-anything/` clean; `git diff --name-only` shows only the
skill file, the generated concept, this slice's documents, and the DEVLOG.

## Risk Assessment

| Risk | Mitigation |
|---|---|
| README absent or uninformative on a target repo | Prose sections fall back to graph fields or gap markers; the source model degrades explicitly, never silently |
| Upstream guide renames User-Provided Concept | Write-time verification with loud terminal failure — the check this contract exists for |
| Generated concept read as authored | `status: not_started`, provenance review-state line, citations and `[INFERRED]` markers |
| Stale `project.description` accepted | The single confirmation targets exactly this value, showing `lastAnalyzedAt` |

Relative effort: **3/5** — extraction is inherited from 362; the prose/signal sources are bounded
lists; the interview carries no wording risk.

## Implementation Notes

- The flow is a sibling section in `commands/analysis/understand.md`, after Flow: Comprehension
  Analysis, before the human-documentation divider. Shared conventions are referenced, not
  duplicated.
- The two questions are fixed text in the skill file. An improvised or added question is a defect
  against Success Criterion 2, not a judgment call.
- The shared Gap markers section's pointer to this flow's `[INFERRED]` governance is updated to
  point at the actual subsection.
- 362's sentence "The concept flow and the initiative-candidates flow are slices 363 and 364" is
  edited to reflect that the concept flow exists.
