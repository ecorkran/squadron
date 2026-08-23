---
docType: slice-design
slice: initiative-candidates
project: squadron
parent: 360-slices.document-intelligence.md
dependencies: [361, 362]
interfaces: [366]
dateCreated: 20260823
dateUpdated: 20260823
status: not_started
---

# Slice Design: Initiative Candidates

## Overview

Propose initiative-shaped work items from the knowledge graph, written to a standalone
`{index}-analysis.initiative-candidates.md` and never into `001-initiative-plan.{project}.md`.

The slice exists because a graph makes two things visible that a human reading a repo cold does not
see quickly: where layer boundaries fall, and where complexity concentrates inside a layer. Those are
structural facts. They are not, by themselves, proposals — and the central design decision here is
about exactly that gap.

Everything is markdown edits to `commands/analysis/understand.md`, adding a third flow section
alongside Flow: Comprehension Analysis and Flow: Concept Generation. **No Python is added.**

## Value

Developer value — turns structural observations into reviewable proposals without letting a machine
author a commitment document. The output is advisory by construction: it lives in `analysis/`, it is
written only on explicit confirmation, and adopting any candidate into the real initiative plan
remains a deliberate manual act by a human.

## Resolved: does this flow read the concept?

The slice plan entry and 363's design disagreed. The slice plan lists dependencies `[361], [362]`
and derives every candidate from `layers[]`, `complexity`, and `edges[]`. 363's Integration Points
list 364 as consuming Q1's engagement answer via the written concept. **This design settles it:**

> **The flow reads `000-concept.{project}.md` when one exists, and degrades to structure-only when
> it does not.** The concept is an **optional input** — never a precondition and never a dependency
> that gates the run.

### Why

A graph carries structure, not priorities. Against squadron's real graph the mechanical signals
produce ten layers and this distribution of `complex` file-level nodes:

```
Pipeline Orchestration: 14   Metrology Subsystem: 9   CLI Surface: 7   Review Engine: 7
Provider & Agent Abstraction: 3   Packaged Declarative Content: 1
Server & Client Surface: 1   Shared Foundation: 1
```

That is roughly eight defensible candidates and **no ordering principle among them**. "Pipeline
Orchestration holds the most complex files" is true and says nothing about whether working there is
worth doing. Complexity is not debt, a large layer is not a problem, and a layer boundary is not a
seam that anyone wants moved.

The concept's Q1 answer — *what do you need to do with this codebase* — is the only available input
that supplies priority. "Take over maintenance and modernize" and "audit it for a security review"
produce different orderings of the identical candidate set. Reading the concept is therefore what
makes candidates *targeted* rather than merely *structural*.

But 364 must also run where 363 has not: the flows are independent, invocation is by explicit
argument, and no flow ever triggers another. A hard dependency on the concept would make the
graph-only path — the one every repo has on day one — impossible.

**Optional-input-with-degradation** is the same shape 365 uses for its own optional concept read, and
the same shape the extraction mapping already uses per section: sourced content or an explicit
marker, never a third outcome where the skill supplies the missing thing itself.

### Reconciliation of the two documents

Both source documents are edited by this slice's implementation:

| Document | Current text | Correction |
|---|---|---|
| `360-slices.document-intelligence.md`, entry 4 | "Dependencies: [361], [362]"; the two "Open at design time" blocks | Add the resolution: concept is an optional input; record that Phase 4 settled it. Keep hard dependencies at `[361], [362]` — the concept is not a dependency. |
| `363-slice.concept-generation.md`, Integration Points | "[364] — ... consumes Q1's engagement answer (via the written concept) to target its candidates" | Qualify: *when a concept exists*. The claim is correct but unqualified, and unqualified it reads as a hard dependency. |

Neither document was wrong about mechanism; the slice plan omitted the optional read and 363 omitted
the degradation. Frontmatter `dependencies: [361, 362]` is correct as written and does not change.

## Resolved: where candidate quality gets judged

Two distinct claims, and this design separates them permanently:

- **Mechanical correctness** — every candidate names a real signal, cites node IDs that resolve,
  derives dependencies from actual `edges[]`, and the document is never written without
  confirmation. **All verifiable against squadron**, and the Verification Walkthrough below does
  exactly that.
- **Candidate usefulness** — whether a proposal is worth adopting. **Not verifiable against
  squadron**, because squadron already has a hand-written initiative plan covering initiatives 100
  through 900. A proposal that matches existing scoped work cannot be told apart from a restatement
  of it, and a proposal that does not match cannot be told apart from noise.

**Usefulness is explicitly not a success criterion of this slice.** It is deferred to a repo nobody
on this project has planned. Recording it as a non-criterion is the point: it prevents a green
walkthrough on squadron from being read as evidence the suggestions are good.

## Technical Scope

**Included** — all within `commands/analysis/understand.md`:

- **Flow selection**: `candidates` becomes a recognized argument; the "not recognized until 364"
  note is removed.
- **The candidate derivation model** — two signal classes, and the rule that a candidate exists only
  where a signal supports it.
- **The optional concept read** — locate, read the two named sections, apply as ordering; degrade
  loudly when absent.
- **Candidate record shape** — the five required fields, and what each is sourced from.
- **Dependency derivation** from `edges[]` between implicated layers.
- **The write confirmation** — one interaction, on whether the document is worth writing at all.
- **Output conventions** — path, index selection, frontmatter, provenance.
- **Non-modification guarantee** for `001-initiative-plan.{project}.md`.

**Excluded (owned elsewhere):**

- Slice-level proposals — Future Work item 3 in the slice plan, explicitly out of scope.
- Dispatcher routing, README, plugin-absent guidance — slice 366.
- Any change to the Preflight Graph Contract, the comprehension flow, the concept flow, `src/`, the
  installer, or the frontmatter gate.
- Any write to `001-initiative-plan.{project}.md`, under any condition. Not a configurable behavior,
  not a flag — the flow has no code path that opens that file for writing.

## Preconditions

1. **The graph** — the 361 preflight, executed unchanged and in full: location, validation,
   staleness, `.gitignore` hygiene. No addition, no skip.
2. **A resolvable project name** — from the cf project registration, never `project.name` from the
   graph, per the rule already established in Output conventions.

The concept document is **not** a precondition. Its absence is an observation the flow records, not
a stop.

There is no `/cf:onboard` boundary concern here as there was in 363: this flow writes to
`analysis/`, which the comprehension flow already writes to, so it requires nothing of
`project-guides/` beyond what 361 and 362 already require.

## Flow selection

The existing table gains one row, and the exclusion note is removed:

| Argument | Flow |
|---|---|
| none | Flow: Comprehension Analysis |
| `comprehension` | Flow: Comprehension Analysis |
| `concept` | Flow: Concept Generation |
| `candidates` | Flow: Initiative Candidates |
| anything else | **unrecognized** — say so and stop |

Selection remains **by explicit argument only**. The flow is never inferred from repository state:
the absence of an initiative plan never auto-triggers it, and the presence of one never suppresses
it. The presence or absence of a concept document selects nothing — it changes only what this flow
reads once it has been named.

## The candidate derivation model

### Two signal classes, and only two

A candidate is derived from exactly one of:

| Signal | Source fields | What it observes |
|---|---|---|
| **Layer boundary** | `layers[]` (`name`, `description`, `nodeIds`) | A layer whose size or described responsibility marks it as a unit of work |
| **Complexity cluster** | file-level `nodes[]` (`complexity`, `filePath`) intersected with `layers[].nodeIds` | A concentration of `complex` files inside one layer |

**A candidate names exactly one signal.** Not "layers and complexity" — the signal is what a reader
checks the candidate against, and a candidate that cites both is checkable against neither. Where the
same layer supports both a boundary observation and a complexity observation, that is two candidates
or one; it is never one candidate citing two signals.

**Field mechanics are inherited from 362, not re-specified here.** The file-level definition
(`select(.type != "function" and .type != "class")`), the `nodeIds | length` counting rule and its
type breakdown, the ordinal-string handling of `complexity`, and the layer cross-check drift rule all
apply unchanged. This flow reads strictly less of the graph than the comprehension flow: no `tour[]`,
no `entry-point` tags, no `meta.json` coverage read.

### The no-padding rule

**Candidates the graph does not support are not proposed.** There is no target count, no minimum, and
no maximum. A thin graph — few layers, flat complexity — yields few candidates or none, and a run
that yields none says so and writes a document saying so.

This is the single most important behavioral rule in the flow, because the failure mode it prevents
is the one that destroys the output's value: a padded list is indistinguishable from a real one to a
reader, and one invented candidate makes every other candidate in the document suspect.

**Emitting zero candidates is a success, not a failure.** The document is still written (on
confirmation), and it states that the graph supported no candidate, naming what it looked for.

## The optional concept read

### What is read

When `project-documents/user/project-guides/000-concept.{project}.md` exists, read **two sections
only**:

- **User-Provided Concept** — the verbatim engagement answers, Q1 in particular.
- **Problem & Motivation** — the engagement half, which 363 sources from Q1.

Nothing else. Not Solution Approach, not Initial Technical Direction, not Development Approach —
those are graph-derived in the concept itself, so reading them here would launder graph content
through a second document and present it as independent corroboration.

### What it changes, and what it does not

| Aspect | Effect of the concept |
|---|---|
| **Which candidates exist** | **None.** Candidates are derived from graph signals only. The concept never creates a candidate, never suppresses one, and never supplies one the graph does not support. |
| **Their order** | **This is the whole effect.** Candidates whose implicated layers align with the stated engagement intent are ordered first. |
| **Their scope statements** | The scope paragraph may frame the work in terms of the stated intent, provided every factual claim in it still traces to a graph signal. |

**The concept cannot manufacture a candidate.** This boundary is what keeps the no-padding rule
enforceable — if engagement context could originate candidates, "we're here to modernize" would
license proposing anything at all.

**Ordering influence is stated per candidate**, not applied invisibly: a candidate ordered up by the
engagement read says so, and names the concept as the reason.

### Degradation when absent

No concept, or a concept lacking both named sections: **candidates are ordered by signal strength
alone** — descending count of `complex` file-level nodes for complexity clusters, descending
`nodeIds | length` for layer boundaries.

The degradation is **stated in the document body and recorded in provenance**, never silent. The
body line names what was missing and what a concept would have changed:

```
Ordered by signal strength alone — no concept document was found at
project-documents/user/project-guides/000-concept.{project}.md. With one present, candidates
would additionally be ordered against the engagement intent it records.
```

A concept that exists but whose User-Provided Concept section records **both questions declined** is
treated as absent for ordering purposes, and the provenance says which of the two cases occurred.
A declined interview and a missing document are different facts, and collapsing them would hide that
the interview happened.

## Candidate record shape

Each candidate carries exactly five parts, in this order:

| # | Part | Sourced from | Rule |
|---|---|---|---|
| 1 | **Title** | authored | Names the work, not the observation. "Extract pipeline step classification" — never "Pipeline Orchestration is complex". |
| 2 | **Derivation signal** | `layers[]` or `complexity` | One signal, named explicitly, with the field it came from. |
| 3 | **Supporting node IDs** | `layers[].nodeIds`, file-level `nodes[]` | The actual ids. Every id must resolve to a node carrying a `filePath`; an unresolvable id is drift, reported per the 362 rule, and a candidate whose supporting ids are all drift is not emitted. |
| 4 | **Scope statement** | authored, constrained | **One paragraph.** Every factual claim traces to the signal or to a cited node. Effort estimates, timelines, and value judgments about the business are out of scope. |
| 5 | **Observed dependencies** | `edges[]` | Derived, never asserted — see below. An empty result is written as "none observed", not omitted. |

**Node IDs are cited, not summarized.** A candidate supported by fourteen nodes lists them; the
document is a working artifact for someone deciding whether to adopt the proposal, and "several files
in Pipeline Orchestration" is not checkable. Where a list is long, it is still written out — the
alternative is an unfalsifiable claim.

**The title is authored and the scope statement is authored.** These are the only two authored parts
of the record, and both are constrained by parts 2, 3, and 5, which are all extracted. That asymmetry
is intentional: prose that a reader can check against cited ids is safe; prose that stands alone is
not.

## Dependency derivation

Dependencies between candidates come from `edges[]` between the layers each candidate implicates —
**observed, never asserted**.

Mechanics are 362's, unchanged: endpoint resolution is a **string parse of the edge's own
`source`/`target` id** (the second colon-delimited field is the owning file's path, which resolves to
a layer), `imports` and `depends_on` edge types, self-references excluded. **No node is read to
resolve an endpoint**, and specifically no `function` or `class` node.

The derivation:

1. For each candidate, collect the set of layers its supporting nodes belong to.
2. For each ordered pair of candidates, count inter-layer `imports`/`depends_on` edges from the
   first's layers to the second's.
3. A non-zero count is a stated dependency, **carrying the count**.

**A stated dependency is a directional edge count, not a claim about sequencing.** The document says
"Candidate 3's layers hold 27 imports into Candidate 1's layers" — it does not say Candidate 1 must
be done first. That inference belongs to the human adopting the candidates, and asserting it here
would be exactly the kind of unsupported claim this flow is built to avoid.

Unresolvable endpoints are excluded from the count and reported as drift, per 362. Where two
candidates implicate the same layer, that overlap is stated rather than expressed as a dependency —
a layer does not depend on itself.

## The write confirmation

**One interaction, after derivation and before any file write.** Show the operator:

- the **count** of candidates derived;
- each candidate's **title and derivation signal** — one line apiece, enough to judge whether the
  set is worth having;
- the **ordering basis** — engagement-informed (naming the concept) or signal-strength-only (naming
  the concept's absence).

Then ask whether to write the document.

**What is being confirmed is that the document is worth writing at all** — not the correctness of
individual candidates, not their adoption. This is the distinction that makes the interaction cheap:
the operator is answering "is this set worth a file?", which is answerable from titles and signals,
not "is candidate 4 correct?", which is not.

| Outcome | Effect | Provenance |
|---|---|---|
| Confirmed | document written | `confirmed` |
| Declined | **nothing is written**; the derived set is shown in the console and discarded | n/a — no document exists |
| No answer / unavailable | **nothing is written** | n/a — no document exists |

**This flow's confirmation defaults to not writing.** This is deliberately the opposite of 363's
confirmation, which never stalls and proceeds on no answer, and the reason is the artifact class:
363 writes the Phase 0 entry point a repo has no other way to obtain, while this flow writes an
advisory list that costs nothing to regenerate. Where 363's failure mode is a lost interview, this
flow's is an unwanted file in `analysis/`.

**Zero candidates still asks.** A run that derives nothing shows "0 candidates, derived from N
layers and M complex file-level nodes" and asks whether to write the document recording that. The
negative result is a real finding — it says the graph does not support proposals — and suppressing
the question would make an empty result indistinguishable from a failed run.

## Output conventions

**Path:**

```
project-documents/user/analysis/{index}-analysis.initiative-candidates.md
```

**Index selection** — the shared rule in Generated document conventions, unchanged: lowest unused
index ≥ 940 in `project-documents/user/analysis/`, a **new index per run**, never overwriting. Runs
are independent samples; two runs against different graph states are two documents.

**Frontmatter:**

```yaml
---
docType: analysis
project: {project}
topic: initiative-candidates
dateCreated: {YYYYMMDD}
dateUpdated: {YYYYMMDD}
status: not_started
model: {id of the model generating this document}
---
```

`{project}` resolves from the cf project registration, never `project.name` from the graph. `model:`
follows the shared rule unchanged — the real generating model id, or an explicit stop. Never a
placeholder.

**Provenance block** — the shared shape, with flow-specific content:

- **Generated by** — this flow, and the model id.
- **Generated on** — the date of this run.
- **Source** — the graph and its identity (`gitCommitHash`, `lastAnalyzedAt`); the concept document
  path **when one was read**, or an explicit statement that none was found.
- **Ordering basis** — `engagement-informed` (citing the concept) or `signal-strength-only` (citing
  the concept's absence, or both-questions-declined).
- **Candidate count**, and the signal counts it was derived from.
- **Drift** — unresolvable node ids and edge endpoints, per 362.
- **Flagged gaps**, **staleness**, **review state** — as in the shared block.

**The non-modification statement is written into the document body**, not only into this design: the
document states that it is advisory, that adoption is manual, and that
`001-initiative-plan.{project}.md` was not read for writing and not modified.

## Gap markers and `[INFERRED]`

**Gap markers** use the shared 361 syntax. This flow's genuine absences are: no concept document,
a concept with no usable engagement content, and zero candidates derived. Each gets a marker naming
the input that would have supplied it.

**`[INFERRED]` is not used in this flow**, and the reason is structural rather than stylistic. The
comprehension and concept flows use it for sentences that go beyond their fields; here, a claim not
traceable to a cited signal or node id has no place in the document at all — the candidate record's
whole design is that its authored parts are checkable against its extracted parts. A sentence that
would need `[INFERRED]` is a sentence to delete.

This is stated explicitly in the skill text so its absence reads as a decision rather than an
oversight.

## Read discipline

362's discipline, unchanged: field-scoped `jq` selections only, the whole graph never loaded, no
`function` or `class` node read. Fields read by this flow: `layers[]`, file-level `nodes[]`
(`complexity`, `filePath`), and `edges[]` (`type`, `source`, `target`). Nothing else.

The concept read is an ordinary bounded file read of two named sections — not a full-document load,
and not a read of any other document in `project-guides/`.

## Integration Points

### Consumes from other slices

- **[361]** — preflight (location, validation, staleness, hygiene), provenance block, gap-marker
  syntax, index selection, generated-document frontmatter. All executed unchanged.
- **[362]** — the corrected layer composition, the file-level definition, the `nodeIds | length`
  counting rule with type breakdown, the ordinal handling of `complexity`, the layer cross-check
  drift rule, and the edge endpoint string-parse resolution. All inherited, none re-specified.
- **[363]** — the concept document's structure, read optionally. This is a read of an artifact, not
  a dependency on the slice: the flow runs correctly where 363 has never been invoked.

### Provides to other slices

- **[366]** — a third routable skill name, `candidates`, for `/sq:analysis understand candidates`.
- **Future Work [3]** (graph-backed slice proposals) — the candidate record shape and the
  no-padding rule are what that item would extend from initiative level to slice level.

### Documents corrected by this slice

- `360-slices.document-intelligence.md` entry 4 — both "Open at design time" blocks resolved.
- `363-slice.concept-generation.md` Integration Points — the 364 line qualified with *when a concept
  exists*.

## Success Criteria

1. `candidates` is recognized by the flow selector and routes to Flow: Initiative Candidates; the
   other three selector rows are unchanged in behavior.
2. Every emitted candidate names exactly one derivation signal and cites supporting node IDs that
   resolve to nodes carrying a `filePath`.
3. No candidate is emitted that the graph does not support. A graph with few layers and flat
   complexity yields few candidates or none, and a zero-candidate run writes a document recording
   that rather than padding.
4. Dependencies between candidates are derived from counted `edges[]` between implicated layers, are
   stated with their counts, and assert no sequencing.
5. `project-documents/user/analysis/{index}-analysis.initiative-candidates.md` is written only after
   explicit confirmation; a declined or unanswered confirmation writes nothing at all.
6. `001-initiative-plan.{project}.md` is never modified, and the output document states so.
7. With a concept present, ordering is engagement-informed and each affected candidate says so; with
   no concept, ordering is signal-strength-only and the degradation is stated in the body and in
   provenance. Both-questions-declined is recorded distinctly from no-document.
8. Output carries `docType: analysis`, `status: not_started`, a real `model:` id, and a provenance
   block; `cf validate frontmatter` passes.
9. The whole graph is never loaded; no `function` or `class` node is read.
10. `ruff format --check` and `pytest tests/skills/` remain green (the slice adds no Python; this is
    a regression guard on the skill-file tests).

**Explicitly not a success criterion:** that the candidates are *useful*. See "Resolved: where
candidate quality gets judged" — usefulness is deferred to a repo with no hand-written initiative
plan, and a green walkthrough here is evidence of mechanical correctness only.

## Verification Walkthrough

Draft. Refined at Phase 6 completion.

### 1. Flow selection

```bash
# each of the four selector cases, by direct skill invocation
/sq:analysis understand candidates      # → Flow: Initiative Candidates
/sq:analysis understand                 # → Flow: Comprehension Analysis (unchanged)
/sq:analysis understand concept         # → Flow: Concept Generation (unchanged)
/sq:analysis understand nonsense        # → unrecognized, stops
```

Confirms SC1: the new row routes and the existing three are untouched.

### 2. Derivation against squadron's real graph

Run `candidates`. At the confirmation prompt, **decline**. Expected: the derived set is shown in the
console, **no file is written**, `git status` is clean. Confirms SC5's decline path.

The shown set is checkable against the graph directly:

```bash
# layer sizes
jq -r '.layers[] | "\(.name) | \(.nodeIds|length)"' .understand-anything/knowledge-graph.json

# complex file-level nodes per layer
jq -r '([.layers[] | .name as $L | .nodeIds[] | {key:., value:$L}] | from_entries) as $M
 | [.nodes[]|select(.type!="function" and .type!="class")|select(.complexity=="complex")
   |($M[.id]//"UNMAPPED")]
 | group_by(.)|sort_by(-length)|map("\(.[0]): \(length)")|.[]' \
 .understand-anything/knowledge-graph.json
```

Every complexity-cluster candidate must correspond to a layer in that second output, and its cited
node ids must be a subset of that layer's complex nodes. Confirms SC2 and SC3.

### 3. Full run with confirmation

Re-run and **confirm**. Then, on the written document:

```bash
cf validate frontmatter project-documents/user/analysis/9??-analysis.initiative-candidates.md
```

Check by hand:
- every candidate has all five record parts, in order;
- each cites exactly one signal;
- dependency lines carry counts and assert no ordering;
- the body states the non-modification guarantee.

Confirms SC2, SC4, SC6, SC8.

### 4. Node ID resolution

For each cited node id, confirm it resolves to a node with a `filePath`:

```bash
jq -r --arg id "<cited-id>" '.nodes[]|select(.id==$id)|"\(.type)  \(.filePath)"' \
  .understand-anything/knowledge-graph.json
```

An id producing no output, or output with a null `filePath`, is a defect against SC2.

### 5. Dependency counts

Spot-check one stated dependency by recounting its edges independently — inter-layer
`imports`/`depends_on` between the two candidates' layer sets, endpoints resolved by the second
colon-delimited field. The recount must match the stated number. Confirms SC4.

### 6. Initiative plan untouched

```bash
shasum project-documents/user/project-guides/001-initiative-plan.squadron.md   # before and after
git status --short project-documents/user/project-guides/
```

Identical shasum, no modification. Confirms SC6.

### 7. Ordering with and without a concept

Squadron has no concept document (the archived one is `docType: notes` in `archive/` and is not at
the concept path), so the **degraded path runs by default** — verify the body line and provenance
name the absence, and that ordering is by signal strength.

For the engagement-informed path, use a scratch copy of the tree with the archived concept restored
to `project-guides/000-concept.squadron.md`. Its Q1 answer records a maintenance-takeover and
modernization engagement. Expected: ordering shifts, and each affected candidate names the concept
as the reason. **Never restore that file into the real tree** — it was archived deliberately.

Third case: a scratch concept whose User-Provided Concept section records both questions declined.
Expected: signal-strength ordering, and provenance distinguishing this from no-document. Confirms
SC7.

### 8. Zero-candidate path

On a scratch fixture graph with one layer and no `complex` nodes: expected a confirmation prompt
stating 0 candidates, and on confirm a written document recording the negative result with a gap
marker naming what was looked for. Confirms SC3's no-padding rule and the zero-candidate write.

### 9. Guards

```bash
ruff format --check .
pytest tests/skills/
```

Confirms SC10.

## Risks

**Low overall** — output is advisory, adoption is manual, and no Python changes.

The one risk worth naming: **candidates that restate work already in squadron's initiative plan will
look like successful output during the walkthrough.** That is the verification gap this design
records rather than closes. The mitigation is the explicit non-criterion above — mechanical checks
are what the walkthrough proves, and usefulness is judged elsewhere.

## Implementation Notes

- The flow is a sibling section in `commands/analysis/understand.md`, after Flow: Concept Generation,
  before the human-documentation divider. Shared conventions are referenced, not duplicated.
- The Flow selection table gains one row; the "`candidates` is **not** recognized" paragraph is
  removed, not amended.
- 362's extraction mechanics are **cited, never restated**. A restated rule is a rule that will drift
  from its original.
- The two slice-plan "Open at design time" blocks are replaced by the resolutions recorded here, and
  363's Integration Points line for 364 is qualified. Both edits belong to this slice's
  implementation, not to a later cleanup.
- Relative effort: **2/5**, unchanged from the slice plan.
