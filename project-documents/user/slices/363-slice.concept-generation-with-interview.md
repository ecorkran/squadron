---
docType: slice-design
slice: concept-generation-with-interview
project: squadron
parent: 360-slices.document-intelligence.md
dependencies: [361, 362]
interfaces: [364, 366]
dateCreated: 20260820
dateUpdated: 20260820
status: not_started
---

# Slice Design: Concept Generation with Interview

## Overview

The interview-driven half of capability (a): produce `000-concept.{project}.md` for a codebase that
has no concept document. Slice 362 settled *what the graph can say*; this slice settles **what the
graph cannot say, how the human is asked for it, and what happens when they decline.**

The operative rule is the architecture's **extract-then-ask**: for each concept section, attempt
extraction from its named graph fields first, and ask the human only when the fields are absent or
when what they yield is structure standing in for intent. Extracted content is shown for
confirmation, never re-asked from scratch.

Two things make this slice different in kind from 361 and 362. First, it is the initiative's only
**interactive** flow — correctness depends on question quality, and both failure directions (asking
too much, asking too little) degrade the result. Second, it writes to a document layout squadron does
not own: `guide.ai-project.000-concept.md` lives in the ai-project-guide, so the **User-Provided
Concept** section is a cross-repo contract verified at write time.

Everything here is markdown edits to the existing `commands/analysis/understand.md`, adding a sibling
flow section alongside Flow: Comprehension Analysis. No Python is added.

## Value

User value, and the highest-leverage output of initiative 360: it turns an unplanned codebase into
squadron's Phase 0 entry point. Squadron's own repo is the instance — it has an initiative plan that
was written retroactively and no concept document at all.

This is also the slice where the initiative's central claim is tested. 361 asserted a reusable
contract and 362 demonstrated reuse of the preflight; 363 is the first consumer of 362's **extraction
mapping** as a mapping — reading it to decide what *not* to ask — rather than as a section list.

## Technical Scope

**Included** — all within `commands/analysis/understand.md`:

- A **flow selector**: the skill gains a second flow, chosen by argument. 362 currently treats any
  non-default argument as unrecognized; this slice makes `concept` recognized and leaves everything
  else unrecognized still.
- The **extract-then-ask decision procedure**, stated per concept section: fields attempted, what
  counts as sufficient, and the ask that fires when it is not.
- The **literal question wording and ordering** — the parent architecture's first open question,
  assigned here.
- **Confirmation of extracted content** as a distinct interaction from asking, including how a
  correction is recorded.
- The **decline path**: an unanswered question becomes an explicit unknown in the body and a
  provenance entry, never a plausible guess.
- The **User-Provided Concept contract**: verbatim write, preservation of pre-existing content, and
  a loud failure naming the governing guide when the section is absent.
- **Re-run semantics** for a document that already exists — the one place in this initiative where
  an output is not a fresh independent sample.
- Concept-specific **frontmatter and provenance** shape.
- `[INFERRED]` **governance for the concept flow**, which 362 explicitly deferred here.

**Excluded (owned elsewhere):**

- Initiative candidates — slice 364.
- Dispatcher routing (`commands/sq/analysis.md`), README, plugin-absent guidance — slice 366. The
  flow is exercised by invoking the file directly, as in 361 and 362.
- Any change to the Preflight Graph Contract's validation, staleness, or hygiene behavior — executed
  unchanged. Any change to the comprehension flow or its extraction mapping.
- Any change to `src/squadron/`, the installer, manifests, or the frontmatter gate.
- Any change to `guide.ai-project.000-concept.md`. That guide is read and depended upon; this slice
  does not edit the ai-project-guide.

## Dependencies

### Prerequisites

- **[361]** — Preflight Graph Contract, gap-marker syntax, provenance block, executed unchanged.
- **[362]** — the extraction mapping table. This slice reads it to determine what the graph already
  answers, and inherits its corrected file-level selector (`type != "function" and type != "class"`)
  and its id-prefix endpoint rule.
- **Cross-repo:** `project-documents/ai-project-guide/project-guides/guide.ai-project.000-concept.md`
  — supplies the document structure, the **User-Provided Concept** section, and the "flag unknowns
  explicitly" rule. Verified at write time, not assumed.
- **External:** the same upstream `understand-anything` output.

### Interfaces Required

| Field | Concept section it feeds |
|---|---|
| `project.name`, `.description` | Overview |
| `project.languages`, `.frameworks` | Initial Technical Direction |
| `layers[]` (`name`, `description`) | Solution Approach — named capability areas |
| `tour[]` (`order`, `title`, `description`) | Solution Approach — what matters and in what order |
| file-level `nodes[]` with `entry-point` tag | Initial Technical Direction — surfaces |
| `config` nodes | Initial Technical Direction — dependency and tooling evidence |

All were measured in 362 and re-measured for this design (see **Verified graph facts**).

## Verified graph facts

Probed against this repo's real graph while writing this design (v2.8.1, `gitCommitHash` `1bfbca1`,
925 nodes / 2184 edges / 10 layers / 15 tour steps). These are measurements, and three of them change
this design's decisions.

| Fact | Value |
|---|---|
| `project` keys present | `name`, `description`, `languages`, `frameworks`, `analyzedAt`, `gitCommitHash` |
| `project.name` | **`squadron-ai`** — the distribution name, not the project name |
| `project.languages` | `json`, `python`, `toml`, `yaml` |
| `project.frameworks` | Anthropic SDK, Claude Agent SDK, FastAPI, Google ADK, MCP, OpenAI SDK, Pydantic, Pytest, Typer, Uvicorn |
| `project.description` | Upstream-generated prose; **narrower than the current project** — describes squadron as a code review framework |
| Layers | 10, all named and described |
| Tour steps | 15, all titled and described |
| `entry-point`-tagged file-level nodes | 28 (matches 362's corrected count, including `pyproject.toml`) |
| `config` nodes | 17 |
| Nodes under `tests/` | **0** |
| Nodes under `.github/` | **0** |
| `.understandignore` location | `.understand-anything/.understandignore` (graph root, **not** repo root) |
| `.understandignore` active patterns | 17, including `/tests/`, `.github/`, `/commands/`, `project-documents/`, `*.md` |
| Existing `000-concept.squadron.md` | **absent** — `user/project-guides/` holds only the initiative plan |
| `concept` in `DocType` enum | present (`src/squadron/documents/schema.py:40`) |

### Three facts that shaped this design

**1. `project.name` is the distribution name.** The graph reports `squadron-ai`; the project name in
every squadron document convention is `squadron`, and the output filename is
`000-concept.{project}.md`. Deriving the filename from `project.name` would write
`000-concept.squadron-ai.md`, which no `cf` introspection would find. **The filename's `{project}` is
the squadron project name, never `project.name`** — resolved from the working context, with the
graph's value reported in provenance as the source's own identity. Where the two differ, the
difference is stated in the Overview rather than silently reconciled.

**2. `project.description` is stale and narrower than the project.** The graph, generated at
`1bfbca1`, describes squadron as "a template-driven code review framework". That was accurate for an
earlier squadron and is no longer the whole system. This is the exact failure the extract-then-ask
rule exists for: a field is *present* but what it yields is a description of part of the structure
standing in for the project's intent. **Overview therefore extracts-and-confirms rather than
extracts-and-accepts**, and the confirmation prompt shows the PM the description together with its
`lastAnalyzedAt` date so staleness is visible at the moment of judgment.

**3. The graph sees `src/` and root config only.** `.understandignore` excludes `/tests/`,
`.github/`, `/commands/`, `project-documents/`, and all `*.md`. Two consequences:

- The architecture's mapping of "test/CI `config` nodes as weak evidence" for **Development
  Approach** does not hold on this graph — there are zero test nodes and zero CI nodes. Development
  Approach is **interview-primary with no extraction attempt worth making**, and the skill says so
  rather than reporting a gap in a field it should not have expected. The attempt is still *coded* —
  a differently-configured repo may include tests — but its absence is the expected case, and the
  question fires without apology.
- A concept derived from this graph would describe the Python package and never mention squadron's
  markdown command surface. **Solution Approach must state its own coverage boundary**, sourced from
  the coverage facts 362 already extracts, so a reader knows what the structural half did not see.

## Technical Decisions

### Flow selection

362 states: "Any argument other than the comprehension default is **unrecognized**. Say so and stop."
This slice narrows that sentence rather than replacing the mechanism:

- No argument, or `comprehension` → Flow: Comprehension Analysis (unchanged).
- `concept` → Flow: Concept Generation (this slice).
- Anything else → unrecognized; say so and stop. `candidates` remains unrecognized until 364.

Flow selection is by **explicit argument only**. The skill never infers which flow the user wanted
from the state of the repo — writing a concept because none exists would be a side effect nobody
asked for.

Preflight runs in full for both flows, unchanged. A concept run against a missing or malformed graph
fails identically to a comprehension run, because the failure is in the shared contract.

### The extract-then-ask procedure

Per section, the skill executes four steps in order. The procedure is uniform; only the per-section
parameters differ.

1. **Attempt.** Run the section's extraction from its named fields.
2. **Judge sufficiency** against the section's stated test (below). This is the only judgment call in
   the flow, and it is bounded per section rather than left to taste.
3. **Confirm or ask.** Sufficient → show the extracted content and ask the PM to confirm or correct
   it. Insufficient → ask the section's question.
4. **Record.** Confirmed extraction, correction, answer, or decline — each is recorded distinctly in
   provenance. These four outcomes are not interchangeable and the provenance must distinguish them.

**Confirmation is not a question.** The distinction is load-bearing: a confirmation shows the PM
something and asks whether it is right, which is cheap; a question asks them to produce content from
nothing, which is expensive. The architecture's asymmetry applies — asking too much wastes the PM's
time, asking too little fabricates a concept — so the tie-break is stated once and applied
throughout: **when a field is present but thin, ask.**

**A correction supersedes the extraction entirely.** When a PM corrects extracted content, the
correction is what lands in the document; the original extraction is not retained beside it as an
alternative, and not merged with it. Provenance records that the section was extracted and corrected,
so the fact of the correction survives without cluttering the body.

### Per-section decision table

The core deliverable. Six sections in the concept guide's own order. Each row is binding.

| # | Section | Extraction attempt | Sufficiency test | Interaction |
|---|---|---|---|---|
| 1 | Overview | `project.description`, `project.name` | Never sufficient alone — upstream prose, possibly stale | **Confirm-or-correct**, showing `lastAnalyzedAt` |
| 2 | User-Provided Concept | none | n/a | **Ask** — verbatim capture; see contract below |
| 3 | Problem & Motivation | none — no graph field states why | n/a | **Ask** (primary) |
| 4 | Target Users | none — no graph field states who | n/a | **Ask** (primary) |
| 5 | Solution Approach | `layers[]` names + descriptions; `tour[]` order and titles | Sufficient when `layers[]` is non-empty — preflight guarantees it | **Confirm-or-correct** the derived summary, plus coverage boundary |
| 6 | Initial Technical Direction | `project.languages`, `.frameworks`; `config` nodes; `entry-point` nodes | Sufficient when `languages` **and** `frameworks` are both non-empty | **Confirm-or-correct**; ask for direction the code cannot show |
| 7 | Development Approach | test/CI `config` nodes | Sufficient only when such nodes exist — zero on this graph | **Ask** (primary) |

Rows 2 and 3–4 are the architecture's "graph holds no statement of why/who" rows, restated as
procedure. Rows 5–6 are the architecture's confirm rows. Row 7 is the row this design changes from
the architecture's expectation, on measurement — see **Verified graph facts** fact 3.

**Section 2 is not a section of the Refined Concept.** It sits above it in the guide's layout and
holds the PM's own words. It is listed in this table because the flow must produce it, not because it
is derived from anything.

### Question wording and ordering

The parent architecture's first open question, settled here. Wording is fixed text in the skill, not
improvised per run, because a question's phrasing determines the answer's shape and an improvised
question set is unauditable.

**Ordering: intent before structure.** The questions the graph cannot answer are asked **first**, in
one block, before any extracted content is shown. Two reasons:

1. **Anchoring.** A PM shown a machine's description of their project answers "what problem does it
   solve?" in the machine's vocabulary. Asking first gets their framing, not a paraphrase of the
   graph's.
2. **Cheap abandonment.** Intent questions are the ones a PM may decline. If they decline everything,
   the run has spent nothing on confirmations for a document that will be mostly unknowns.

The confirmations follow, in document order, so the PM sees the structural half assembled after their
own framing is already recorded.

**The question set, verbatim:**

```
1. In one or two sentences: what problem does this project solve, and for whom is that
   problem currently painful?

2. Why now? Is there something that makes this the right time to build it, or a cost to
   not building it?

3. Who uses this, and how do they reach it — a CLI, a service, a library, something else?
   If there is more than one kind of user, name them.

4. Is the audience expected to change — for example, an internal tool intended to become
   a product, or the reverse?

5. Are there methodology preferences or constraints on how this work is done — testing
   discipline, review requirements, quality-versus-speed tradeoffs, deployment
   constraints?

6. Is there anything the code cannot show that a reader of this concept must know — a
   decision already made, a constraint from outside the project, a direction deliberately
   not taken?
```

**Six questions, and the count is a decision.** Questions 1–2 supply Problem & Motivation, 3–4
supply Target Users, 5 supplies Development Approach, and 6 is the open catch that stops the fixed
set from silently bounding what the PM can contribute. Nothing structural is asked — the graph
answers structure, and asking about it would violate the architecture's rule directly.

**Question 6 is deliberately last and deliberately open.** A fixed question set is auditable but
lossy; the catch-all restores what the fixed set would drop, and placing it last means it collects
what the earlier questions surfaced but did not have a home for.

**Answers to 1–4 are also the verbatim User-Provided Concept content.** They are not asked twice.
The PM's own words serve both as the sacred section's content and as the source for the corresponding
Refined Concept sections, which is exactly the guide's own model: "the PM's original vision is
preserved in the User-Provided Concept section; the AI adds structured analysis as the Refined
Concept."

### The User-Provided Concept contract

The cross-repo dependency, and the one place this slice can be broken by another repository.

**Verify before writing.** Before any write, confirm that
`project-documents/ai-project-guide/project-guides/guide.ai-project.000-concept.md` is readable and
that its document-structure block contains a section titled exactly **User-Provided Concept**.

- Guide unreadable or absent → **stop**, naming the path. Do not fall back to a remembered layout;
  a concept written to a structure nobody verified is the failure this check exists to prevent.
- Guide readable but the section title absent or renamed → **stop**, naming the guide, the expected
  title, and the fact that the layout appears to have changed upstream. Never write the PM's words
  to a section that no longer means what it did, and never invent a substitute section.

Both failures are loud and terminal for the flow. Neither is a gap marker: a gap marker means "this
document is missing something", whereas this means "this document cannot be correctly written at
all".

**Write verbatim.** The PM's answers land in the section as given — not summarized, not reworded,
not reordered, not grammar-corrected. The section is the one place in the document where the machine
is a transcriptionist.

**Preserve what is there.** If the section already holds content, that content survives untouched.
New answers are appended below it under a dated subheading, so authorship over time stays legible.
Pre-existing content is never rewritten, reordered, or merged with new material.

### Re-run semantics

Every other output in initiative 360 takes a fresh index per run, because runs are independent
samples. **The concept is the exception**: its path is fixed at `000-concept.{project}.md`, so a
re-run necessarily meets an existing document.

- **No existing document** → write it.
- **Existing document** → do not overwrite. Report that it exists, and offer exactly two paths:
  augment or stop. Augmenting appends to User-Provided Concept per the preservation rule and fills
  only Refined Concept sections that are **empty or hold a gap marker**; a Refined Concept section
  with real content is left alone. Stopping is the default when the PM does not choose.
- **Never** rewrite a human-authored concept from a graph. A concept document is the input to every
  later phase, and regenerating one over a PM's work would destroy the most expensive artifact in
  the tree.

The distinction between filling a gap marker and rewriting content is mechanical: a section whose
body is exactly a `[GAP: ...]` marker is machine-written and refillable; anything else is not.

### `[INFERRED]` governance for the concept flow

362 deferred this here, and its reasoning is inherited: `[GAP: ...]` marks something absent,
`[INFERRED]` marks something present but derived from indirect evidence.

**The concept flow does use `[INFERRED]`, unlike the comprehension flow**, and exactly one class of
content earns it: **a claim derived from graph structure that asserts intent.** The architecture
names the case — a Solution Approach derived from tour ordering is an inference, because the tour is
an expert judgment about what matters, not a statement of what the project is for.

The rule, stated so it is checkable:

> A sentence carries `[INFERRED]` when it is derived from a named graph field but asserts something
> the field does not literally state. A sentence carries no marker when it restates the field. A
> sentence with no field behind it does not belong in the document.

Applied:

- "The system is organized into ten layers, including Pipeline Orchestration and Review Engine" —
  restates `layers[]`. No marker.
- "`[INFERRED]` The pipeline execution engine appears central, appearing early in the reading order
  and carrying the largest layer" — derived from `tour[]` and `layers[]`, asserts importance. Marker.
- "The project aims to replace manual code review" — no field behind it. **Does not belong**; this is
  what the interview is for.

**A PM-confirmed inference stays marked.** Confirmation records that a human agreed with a derived
claim; it does not convert the claim's derivation into a field that states it. The marker describes
provenance, not confidence. What confirmation changes is the provenance entry, not the body.

`[INFERRED]` markers are listed in provenance alongside gap markers, for the same reason: a reader
should be able to find every non-literal claim without reading the whole document.

### Declines

An unanswered question produces an explicit unknown, per the concept guide's own "flag unknowns
explicitly" rule:

- **In the body**, at the point of absence, as a gap marker naming the interview as the input that
  would supply it — the 361 syntax, unchanged, with the interview in place of a graph field.
- **In provenance**, under a declined-questions line naming which questions went unanswered.

A decline is never filled with a plausible guess, and never quietly omitted so the section reads as
if it were never expected. Declining every question yields a valid document: structure from the
graph, unknowns everywhere else, and a provenance block that says exactly that. That document is
still worth more than none, because the structural half is real.

### Output conventions

**Path:** `project-documents/user/project-guides/000-concept.{project}.md`, where `{project}` is the
squadron project name — never `project.name` from the graph (see **Verified graph facts** fact 1).
This is capability (a)'s second output directory, as the architecture specifies.

**Frontmatter**, from the concept guide's own schema, with squadron's generated-document rules
applied:

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

`docType: concept` is in the gate's enum (`src/squadron/documents/schema.py:40`). `status:
not_started` carries the same meaning 361 established — no human has reviewed it — and is reinforced
by the provenance block's review-state line. `model:` follows 361's rule unchanged: the real model id
or an explicit stop, never a placeholder.

**Provenance block**, the 361 shape with three concept-specific additions:

- **Generated by** names the concept flow rather than the comprehension flow.
- **Section sourcing** distinguishes four outcomes per section, not two: extracted-and-confirmed,
  extracted-and-corrected, interview, or declined.
- Two extra lines: **Declined questions** (which were unanswered, or none) and **Inferred claims**
  (every `[INFERRED]` sentence, or none).

**Source** additionally names the concept guide path and states that its User-Provided Concept
section was verified present — the check happened, and the document says so.

### Read discipline, unchanged

362's discipline applies verbatim: every graph read is a field-scoped `jq` selection, the whole graph
is never loaded into context, and no `function` or `class` node is read. The concept flow reads
strictly less than the comprehension flow — `project`, `layers[]`, `tour[]`, and two tag-filtered
file-level node selections — and adds no new read pattern.

## Integration Points

### Provides to Other Slices

- **[364]** — the flow-selection mechanism, extended for `candidates` by the same narrowing.
- **[366]** — `/sq:analysis understand concept` as a routed invocation; 366 adds routing only.
- **Downstream phases** — a `000-concept.{project}.md` that `cf` introspection and Phase 1 consume
  unchanged, because it is the guide's own layout with the guide's own frontmatter.

### Consumes from Other Slices

- **[361]** — preflight, gap markers, provenance shape, `model:` rule.
- **[362]** — the extraction mapping, the corrected file-level selector, and the coverage facts that
  supply Solution Approach's coverage boundary.

## Success Criteria

1. `concept` is a recognized flow argument; no argument and `comprehension` still route to the
   comprehension flow; `candidates` and any other argument are still unrecognized and stop.
2. Questions are asked only for sections the per-section decision table marks **Ask**. No structural
   question is asked. Extracted content is shown for confirmation, never re-asked from scratch.
3. The six interview questions are the fixed wording in this design, asked before any extracted
   content is shown.
4. A declined answer produces a gap marker in the body at the point of absence **and** an entry in
   the provenance block's declined-questions line. No declined answer is filled with prose.
5. The **User-Provided Concept** section holds the PM's answers verbatim — not summarized or
   reworded — and pre-existing content in that section survives a re-run untouched, with new content
   appended below it under a dated subheading.
6. With the concept guide absent, unreadable, or missing the **User-Provided Concept** title, the
   flow stops with an error naming the guide path and the expected section title. It never writes to
   a substitute section and never proceeds on a remembered layout.
7. An existing `000-concept.{project}.md` is never overwritten. The flow reports it, offers augment
   or stop, defaults to stop, and when augmenting fills only sections that are empty or hold a gap
   marker.
8. Output carries `docType: concept`, `status: not_started`, a real `model:` id, and the concept
   guide's frontmatter fields; `cf validate frontmatter` passes.
9. The provenance block distinguishes extracted-and-confirmed, extracted-and-corrected, interview,
   and declined per section, and carries declined-questions and inferred-claims lines.
10. Every `[INFERRED]` marker in the body satisfies the stated rule — derived from a named field,
    asserting something the field does not literally state — and each is listed in provenance. A
    sentence with no field behind it appears nowhere in the document.
11. The output filename uses the squadron project name, not `project.name` from the graph; where the
    two differ the difference is stated in the Overview and the graph value appears in provenance.
12. Solution Approach states its coverage boundary, so a reader knows which parts of the repo the
    graph did not see.
13. The whole graph is never loaded into context; no `function` or `class` node is read.
14. Running against squadron produces a concept a PM would edit rather than discard.
15. No file under `src/squadron/` changes, and `guide.ai-project.000-concept.md` is not modified. The
    only changed non-document file is `commands/analysis/understand.md`.

## Verification Walkthrough

Run from the squadron repo root, on branch `363-slice.concept-generation-with-interview`. Pre-366 the
flow is exercised by opening `commands/analysis/understand.md` in a Claude Code session and
instructing "execute this skill's concept flow against this repo".

**1. Re-measure the three facts this design rests on.** The graph may have been refreshed since
design time; if these disagree with the design, stop and revisit before implementing.

```
# project.name is the distribution name, not the project name
jq -r '.project.name' .understand-anything/knowledge-graph.json

# description present, and its age
jq -r '.project.description' .understand-anything/knowledge-graph.json | head -c 200; echo
jq -r '.lastAnalyzedAt' .understand-anything/meta.json

# languages and frameworks both non-empty -> Initial Technical Direction is confirm, not ask
jq -r '.project | "langs=\(.languages|length) frameworks=\(.frameworks|length)"' \
  .understand-anything/knowledge-graph.json

# zero test and CI nodes -> Development Approach is ask, not weak-evidence
jq -r '[.nodes[]|select(.filePath != null)|select(.filePath|startswith("tests/"))]|length' \
  .understand-anything/knowledge-graph.json
jq -r '[.nodes[]|select(.filePath != null)|select(.filePath|test("^\\.github/"))]|length' \
  .understand-anything/knowledge-graph.json
```

**2. Cross-repo contract, both directions.** The check must pass on the real guide and fail loudly
on a broken one.

```
# passes: the section title is present
grep -c '^## User-Provided Concept' \
  project-documents/ai-project-guide/project-guides/guide.ai-project.000-concept.md
```

Then induce the failure on a **copy**, never the real guide: copy the guide to a scratch path, rename
the section heading in the copy, point the flow at it, and confirm it stops with an error naming the
guide path and the expected title. Confirm no file is written to `user/project-guides/`. Delete the
copy.

**3. Flow selection.** Confirm all four cases: no argument and `comprehension` run the comprehension
flow; `concept` runs this flow; `candidates` is unrecognized and stops.

**4. Happy path — full interview.** Run the concept flow and answer all six questions.

Confirm in the written `000-concept.squadron.md`:
- filename uses `squadron`, not `squadron-ai`, and the Overview states the difference;
- the six questions were asked before any extracted content was shown;
- User-Provided Concept holds the answers verbatim — diff the answers as given against the section;
- Solution Approach names layers and tour-derived ordering and states the coverage boundary;
- Initial Technical Direction lists the four languages and ten frameworks;
- Development Approach comes from the interview, with no gap marker claiming a missing field;
- provenance distinguishes all four sourcing outcomes and carries both new lines;
- `grep -c 'INFERRED'` returns a non-zero count, and every marked sentence satisfies the rule;
- frontmatter passes: `cf validate frontmatter` (or the project's gate invocation) on the file.

**5. Decline path.** Re-run in a scratch copy of the tree and decline every question. Confirm the
document is still written; Problem & Motivation, Target Users, and Development Approach each carry a
gap marker naming the interview; provenance lists all six as declined; and no section holds prose
that was not extracted from a field.

**6. Correction path.** Re-run and correct the extracted Overview description. Confirm the correction
is what lands in the body, the original upstream description is not retained beside it, and provenance
records the section as extracted-and-corrected rather than extracted-and-confirmed.

**7. Re-run against an existing document.** With `000-concept.squadron.md` now present, run the flow
again. Confirm it does not overwrite, reports the existing document, defaults to stop, and — when
told to augment — appends to User-Provided Concept under a dated subheading while leaving
already-populated Refined Concept sections byte-identical. Verify with `git diff`.

**8. Read discipline.** During a run, confirm no command reads the graph without a `jq` field
selection and no `function` or `class` node is selected. Afterwards, `git status` on
`.understand-anything/` shows no modification — including `fingerprints.json`, per 362's correction 3.

**9. Scope.** `git diff --name-only` against the branch point lists only
`commands/analysis/understand.md`, the generated concept, and this slice's own documents. Nothing
under `src/squadron/` or `project-documents/ai-project-guide/`.

## Risk Assessment

| Risk | Impact | Mitigation |
|---|---|---|
| Interview quality — asking too much or too little | The stated correctness criterion for this slice | Fixed question wording, fixed count, per-section sufficiency tests, and the stated tie-break: when a field is present but thin, ask |
| Upstream guide renames or drops **User-Provided Concept** | The flow cannot write correctly | Verified at write time; loud terminal failure naming the guide. This is the risk the check exists for, not a residual one |
| A generated concept read as authored | Every later phase built on unreviewed content | `status: not_started`, provenance review-state line, `[INFERRED]` markers on derived claims |
| Stale `project.description` accepted as current | Concept opens with an out-of-date framing | Overview is confirm-or-correct, never accept, with `lastAnalyzedAt` shown at the moment of judgment |
| Graph coverage narrower than the repo | Concept describes only what the graph saw | Solution Approach states its coverage boundary from 362's coverage facts |

Relative effort: **4/5** — the interview design and the cross-repo contract are the cost; the
extraction is inherited from 362.

## Implementation Notes

- The flow is a sibling section in `commands/analysis/understand.md`, placed after Flow:
  Comprehension Analysis and before the human-documentation divider. Shared conventions are not
  duplicated into it — it references the existing Preflight and Document Conventions sections, since
  duplication is what makes two flows drift apart.
- The six questions are fixed text in the skill file. If a run improvises a question, that is a
  defect against Success Criterion 3, not a judgment call.
- `[INFERRED]` governance is added to the existing Gap markers section, which already reserves the
  marker for this slice and points here for governance. Update that pointer.
- 362's sentence "The concept flow and the initiative-candidates flow are slices 363 and 364" is
  edited to reflect that the concept flow now exists.
