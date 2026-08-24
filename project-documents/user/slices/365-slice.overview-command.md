---
docType: slice-design
project: squadron
slice: 365-slice.overview-command
parent: 360-slices.document-intelligence.md
dateCreated: 20260824
dateUpdated: 20260824
status: not_started
---

# Slice Design: Overview Command

## Parent Documents

- Architecture: `360-arch.document-intelligence.md` — Capability 2 (Planning Artifacts →
  Client-Facing Document)
- Slice Plan: `360-slices.document-intelligence.md`, entry 5

## Scope

Deliver `/sq:overview` as a first-party command in `commands/sq/`, reading a project's planning
artifacts and writing `{index}-analysis.overview.md` for a non-engineering reader.

**One file is added: `commands/sq/overview.md`.** The slice adds no Python source — not because
squadron avoids Python (squadron *is* a Python project and this command runs on it), but because
the installer already copies `commands/sq/*.md` wholesale
(`src/squadron/cli/commands/install.py:48-55` — `sorted(sub.glob("*.md"))` per subdirectory into
`~/.claude/commands/{sub}/`). The file's presence is its registration, so no installer, manifest,
or CLI-registration change is required. A slice in this initiative concluding otherwise is a signal
that scope has drifted, per the slice plan.

The command reads **planning documents only** — the concept and the initiative plan. It has no
dependency on the knowledge graph, on `understand-anything`, or on slices 361–364, and does not
read their outputs even when present (see D8, which also covers how an inherited project reaches a
good overview *through* those slices rather than around them).

---

## Technical Decisions

### D1 — The command file is self-contained; it does not reference the analysis pack

Slices 361–364 built shared conventions (gap markers, provenance block, generated-document
frontmatter, index selection) inside `commands/analysis/understand.md`. Line 344 of that file
already anticipates this slice: *"Slice 365 (capability (b)) reuses this same block shape, with
**Source** naming the concept and initiative-plan paths instead of a graph."*

**Reuse here means reuse of the *shape*, restated in this file — not a cross-file reference.**

The reason is an install-path fact, not a stylistic preference. The two files install to different
places by different commands, and one of them is opt-in:

| File | Installed by | Destination | Opt-in? |
|---|---|---|---|
| `commands/sq/overview.md` | `sq install-commands` | `~/.claude/commands/sq/` | No — ships with squadron |
| `commands/analysis/understand.md` | `sq skills install analysis` | analysis pack prefix | Yes |

A user who has run `sq install-commands` and never installed the analysis pack has `/sq:overview`
and no `understand.md`. A cross-file reference would resolve to nothing for that user, and the
failure would be a silently degraded document rather than a loud error. The architecture's own
delivery section makes the same split for the same reason: capability (b) "belongs alongside
`sq:review` and `sq:task`", not behind the pack.

**Consequence accepted:** the provenance-block line list, the gap-marker syntax, the frontmatter
block, and the index-selection rule appear in two files. This is duplication of a *convention
statement*, not of logic.

**A shared fragment read by both files remains open, deliberately deferred — not rejected.** It may
well be the right structure. It is not done now because this slice adds one file and a shared
fragment changes two install paths, which is a wider blast radius than the slice needs. Whether it
requires installer code is **unverified**: both paths already copy directories of markdown, so a
shared file might ride along with no code change at all. That question should be answered with
evidence — by reading the install paths — at the point someone next touches either file, and not
assumed either way before then. This design does not claim the fragment is costly; it claims only
that this slice is not the place to find out.

**Drift control until then:** the two statements must remain identical in substance. The task
breakdown carries an explicit step that diffs this file's convention sections against
`commands/analysis/understand.md` and records any deliberate divergence in the file itself. The
known, intended divergences are listed in D2.

This is process, not machinery — the weakest form of drift control, and the honest reason to
revisit the shared fragment later. The file itself should say so where a reader will see it, rather
than let them assume the conventions are shared by construction when they are shared by convention.

### D2 — Known, intended divergences from the 361 conventions

| Convention | In `understand.md` (a) | In `overview.md` (b) | Why |
|---|---|---|---|
| **Source** line | graph path with node/edge/layer/tour counts | initiative-plan path (always) and concept path (or an explicit "not present") | No graph is read |
| Graph identity / Staleness lines | `gitCommitHash`, `lastAnalyzedAt`, commit distance | **Omitted entirely** | There is no snapshot to be stale against; the inputs are live repo files |
| `topic:` frontmatter | `codebase-comprehension` | `overview` | Per-artifact |
| `[INFERRED]` | documented, used only by concept flow | **never used**, and its appearance is a defect | Every field is sourced-or-gapped (D4); nothing is left to infer |

Omitting the staleness line is the one place this file *removes* a provenance line rather than
restating it. The 361 rule "no line is ever silently omitted" is about lines whose data source
failed to read — it does not require carrying a line for a concept that does not apply. The
provenance block states, in the Source line, that the inputs are live repo files read at generation
time, which is the equivalent honest statement.

### D3 — Inputs degrade per field, across a range of incompleteness

| Input | Path | Required? |
|---|---|---|
| Initiative plan | `project-documents/user/project-guides/001-initiative-plan.{project}.md` | **Yes** |
| Concept | `project-documents/user/project-guides/000-concept.{project}.md` | No |

**The governing rule: produce as much useful output as the inputs actually support, and state
plainly what could not be produced and why.** Incompleteness is the normal condition of a real
project, not an error state. A document carrying accurate gap markers is a successful run.

**Degradation is per field, not per document.** A whole input being absent is only the coarsest
case. Real projects present a wide range, and each of these degrades the fields it feeds while
leaving every other field intact:

| Input condition | Effect |
|---|---|
| Concept absent entirely | Concept-sourced fields become markers; Purpose falls back (D4) |
| Concept present, headings differ or are missing | The affected fields become markers naming the section they expected |
| Concept present but a section is empty | Treated the same as absent — a marker, never an empty field and never filler |
| Plan states no dependencies | Roadmap orders by plan order and says so |
| Plan states no non-goals | Scope carries included work; excluded work is a marker |
| Plan entries are one-line stubs | Benefits and Scope carry what is there; thinness is visible, not padded |
| Plan has no status values or checkboxes | Status becomes a marker rather than an assumed state |

**A section that exists but is empty behaves exactly as an absent one.** This is the rule that
keeps thin inputs honest: the failure to guard against is a field that renders blank or gets filled
with plausible prose because *something* was technically read.

**Two hard stops, both about the required input:**

1. **The initiative plan is missing or unreadable.** It is the only required input; with it gone
   there is nothing to derive from. The error names the expected path and points at Phase 1 of the
   process guide as what produces it.
2. **The initiative plan is present but yields no parseable initiatives.** Five of the nine fields
   source from it, and a document where the majority of fields are markers is not an overview — it
   is a report that the project has not been planned. Saying that directly is more useful than
   emitting a hollow document. The error states what was found and what was expected.

Everything short of those two produces a document.

**On using squadron for verification.** Squadron is available because we are working inside it, and
it is a legitimate sample — it genuinely has no concept. It is **not** the baseline. Its particular
shape of incompleteness (concept absent, plan rich and complete) is one point in the range above,
and designing to it would leave the other conditions unverified. Squadron's own missing concept is
also a bootstrap ordering fact — concept generation postdates the project that built it — rather
than the client-repo case where Phase 0 simply has not run yet.

Verification therefore runs against **constructed fixtures spanning the range**, with squadron as
one real-world sample among them (see Verification Walkthrough). This is what makes the "useful
output or a clear statement of what is missing" claim testable here rather than deferred to a
hypothetical future repo.

**Project name resolution.** The `{project}` in both paths is resolved from the initiative plan's
own `project:` frontmatter field, which is authoritative because that file is required. Filename
matching is the fallback only when that field is absent, and a mismatch between the field and the
filename is reported rather than silently preferred.

### D4 — Every field is sourced or gapped; there is no third outcome

This is the structural enforcement of "derive, never invent" from the architecture. It is not a
guideline in the command file — it is the shape of the generation loop: the skill walks the nine
fields in order, and for each one either extracts from its named source or emits a marker naming
what is missing and which input would supply it.

**"Absent source" means absent, unmatched, or empty** — per D3, a section that exists but yields no
content takes the same branch as one that is not there. The marker names what was expected, so a
reader can tell an unwritten section from a mis-titled one.

**Field schema** (from the architecture's table, with the source resolved to a concrete section):

| # | Field | Source | On absent source |
|---|---|---|---|
| 1 | Purpose | Concept *Overview* section; falls back to the initiative plan's project-level framing | `[GAP: ...]` naming the concept |
| 2 | Problem | Concept *Problem & Motivation* | `[GAP: ...]` naming the concept |
| 3 | Audience | Concept *Target Users* | `[GAP: ...]` naming the concept |
| 4 | Approach | Concept *Solution Approach* | `[GAP: ...]` naming the concept |
| 5 | Benefits | Derived from initiative descriptions, phrased as outcomes | `[GAP: ...]` naming the initiative plan |
| 6 | Scope | Initiative plan entries plus their stated non-goals | `[GAP: ...]` — included work sourced, excluded work marked if no non-goals are stated |
| 7 | Status | Initiative `Status:` values and checkbox state | `[GAP: ...]` naming the initiative plan |
| 8 | Roadmap | Initiative plan plus its Cross-Initiative Dependencies section | `[GAP: ...]` if dependencies are unstated; ordering then falls back to plan order, and says so |
| 9 | Risks / Open Questions | Initiative plan Notes and per-initiative open questions | `[GAP: ...]` if the plan states none |

**Purpose has a two-source rule and needs stating precisely.** With no concept, Purpose is *not*
automatically a gap: the initiative plan carries project-level framing, and the architecture's own
table lists the source as "Concept Overview / initiative plan". The rule is: derive Purpose from
the concept when one exists; with none, derive it from the initiative plan and **state in the field
that it is initiative-plan-derived**; emit a gap only when neither yields project-level framing.
This is the one field where the fallback is a different real source rather than a marker, and
naming the fallback in place is what keeps it honest.

Fields 2, 3, and 4 have no such fallback. With no concept they are markers, because the initiative
plan describes *what is being built*, not *whose problem it solves* — and inferring the latter from
the former is exactly the invention this rule forbids.

### D5 — Translation rules are stated as mechanical checks, not aspirations

The architecture states four translation rules. Each is written into the command file with a check
the skill can actually apply, and each is separately verifiable:

| Rule | Mechanical form |
|---|---|
| Strip internal vocabulary | No slice index, phase number, initiative index, docType, or frontmatter field name appears in the body. Verifiable by grep. |
| Features become outcomes | Each Benefits entry states what a reader can *do* or what *changes for them*, not what was built. A benefit that names a mechanism is rewritten. |
| Derive, never invent | Every field carries either sourced content or a marker (D4). No sentence asserts a fact absent from both inputs. |
| Status is honest | Not-started work is described as planned. `not_started` never renders as language implying progress; `in_progress` never renders as complete. |

**"Strip internal vocabulary" needs one boundary made explicit**, because it is the rule most likely
to be over-applied: it strips squadron's *process* vocabulary, not the project's *domain* vocabulary.
An overview of squadron may say "pipeline", "review", "agent" — those are what the product is. It
may not say "slice 365", "Phase 4", "initiative 360", or "docType". Named initiatives are rendered
as themes by their title with the index dropped: "Pipeline Foundation", not "initiative 140".

### D6 — Output conventions

**Path:** `project-documents/user/analysis/{index}-analysis.overview.md`

**Index selection:** scan existing `9nn-` filenames in `project-documents/user/analysis/` and take
the lowest unused index ≥ 940. Each run takes a new index; never overwrite. Overflow past 949 is
sanctioned. (Identical rule to 361. At design time 940–945 are used, so the first run of this
command takes **946**.)

**Frontmatter:**

```yaml
---
docType: analysis
project: {project name}
topic: overview
dateCreated: {YYYYMMDD}
dateUpdated: {YYYYMMDD}
status: not_started
model: {id of the model generating this document}
---
```

`model:` holds the id of the model actually generating the document — never a placeholder, never
copied. If the model cannot determine its own id, it says so and stops rather than writing a
plausible value. (`model:` on an `analysis` document is accepted by `cf validate frontmatter`,
verified against `942-analysis.tech-debt-audit.md`.)

`status: not_started` for the same reason as every generated document in this initiative: the enum
has no `needs_review` member, `complete` would assert a review that has not happened, and review
state is carried by the provenance block.

**Provenance block** — `## Provenance` immediately after the H1, above all content, as body prose,
carrying: Generated by (skill + model id), Generated on, Source (initiative-plan path, and concept
path or an explicit statement that none is present), Section sourcing (each of the nine fields and
its resolved source), Flagged gaps (every `[GAP: ...]` in the body, or an explicit statement there
are none), Review state (always: machine-generated draft, no human review).

**Gap marker syntax** — `[GAP: {what is missing} — {which input would supply it}]`, both halves
required, appearing twice (body at the point of absence, and in the provenance flagged-gaps line).
A document containing markers is a valid output, not a failed run.

### D7 — One neutral document; the command takes no arguments

The command takes no audience argument. Client, management, and colleague readings differ in
emphasis, not in fact, and three variants means three artifacts to keep true. Per-audience emphasis
is already recorded as Future Work item (1) in the slice plan, dependent on this slice, to be
pursued only if real use shows one document is insufficient.

**No topic argument either.** The naming convention provides for `{index}-analysis.overview.{topic}.md`
where a project needs more than one, but nothing asks for it yet and an unused argument is an
untested path. The convention still permits it, so a later slice can add the affordance when a real
need appears. The command writes the plain form.

### D8 — Graph-derived artifacts are not read, and how an inherited project still works

**Direct consumption: no.** The command reads planning documents only — the concept and the
initiative plan. Even when `.understand-anything/knowledge-graph.json`, a comprehension analysis, or
an initiative-candidates document is present in the repo, none is read.

The reason differs per artifact:

- **The graph and comprehension analysis** describe *code structure*. An overview that mixed
  structural observations into purpose, audience, or benefit would be asserting things about intent
  that no planning document ever claimed.
- **The initiative-candidates document** is the sharper case. It is explicitly advisory — proposals
  nobody has adopted, written to a standalone analysis file precisely so they never reach the
  initiative plan by machine. Rendering it into a stakeholder overview would present unadopted
  machine suggestions as the project's roadmap, which is exactly the overstates-progress failure the
  translation rules exist to prevent.

This exclusion is stated in the command file, not merely here, because the next reasonable-sounding
question a maintainer asks is "we already have a comprehension analysis — why not use it?" The
answer should be written down rather than rediscovered.

**Indirect consumption: yes, and it is the inherited-project path.** Excluding those artifacts does
not cut an inherited project off from a good overview. The chain runs through a human:

```
understand the codebase (upstream plugin)
   └─► generate concept draft + initiative candidates (slices 363, 364)
          └─► HUMAN reviews, edits, adopts into a real concept and initiative plan
                 └─► /sq:overview reads those planning documents normally
```

The overview never touches the graph at any point in that chain. The generated artifacts arrive as
*reviewed planning documents*, which is the input this command was designed for. The human adoption
step is load-bearing and deliberate: candidates are advisory by design and adoption is a manual act.

**A known dependency on unproven quality.** Whether the generated concept and candidates are good
enough to adopt is genuinely open — slice 364 recorded candidate usefulness as an explicit
non-criterion, to be judged on a repo nobody here has planned. So the inherited-project path is
architecturally sound and its output quality is unverified. This slice does not resolve that and
should not claim to.

**One useful consequence:** run on an inherited project, the overview doubles as an end-to-end read
on the whole initiative. A thin or gap-riddled overview there has two possible causes — weak
generated planning documents, or a defect in this command — and the walkthrough must be able to tell
them apart. The provenance block's section-sourcing lines are what make that possible: they name
what each field resolved from, so a gap traceable to a thin concept section is distinguishable from
one traceable to a failed read.

---

## Data Flow

```
/sq:overview
      │
      ├─ 1. Resolve project name ── initiative plan frontmatter `project:`
      │
      ├─ 2. Read required input ─── 001-initiative-plan.{project}.md
      │        ├─ absent/unreadable ──► STOP, name the path, point at Phase 1. Nothing written.
      │        └─ no parseable initiatives ──► STOP, state found vs expected. Nothing written.
      │
      ├─ 3. Read optional input ─── 000-concept.{project}.md
      │        └─ absent ──► record in provenance Source line; concept-sourced fields → markers
      │
      ├─ 4. Field loop (nine fields, in schema order)
      │        for each: extract from named source        ──► content
      │                  source absent, unmatched, empty  ──► [GAP: what — which input]
      │        (no third branch — never blank, never filler)
      │
      ├─ 5. Apply translation rules to assembled content (D5)
      │
      ├─ 6. Select index ── lowest unused 9nn ≥ 940 in user/analysis/
      │
      └─ 7. Write ── frontmatter, H1, ## Provenance, nine field sections
```

Graph-derived artifacts are absent from this flow by design, whether or not they exist in the repo
(D8).

There is no confirmation gate. This differs deliberately from slice 364, where the PM confirms
whether the document is worth writing at all: 364 proposes work items whose adoption is a
commitment, whereas an overview is a rendering of artifacts that already exist and asserts no new
plan. Nothing is overwritten (D6 index rule), and the initiative plan and concept are read-only —
so an unwanted run costs one file the PM can delete.

---

## Component Interactions

| Component | Interaction | Change required |
|---|---|---|
| `sq install-commands` | Copies `commands/sq/*.md` to `~/.claude/commands/sq/` | **None** — `sorted(sub.glob("*.md"))` picks up the new file |
| `commands/sq/analysis.md` | Unrelated dispatcher; `/sq:overview` is not routed through it | **None** — slice 366 owns dispatcher edits, and only for capability (a) |
| `commands/analysis/understand.md` | Shares convention *shape*, not a reference (D1) | **None** — not edited by this slice |
| `cf validate frontmatter` | Validates the generated document's `docType`/`status` | **None** — both are existing enum members |
| README | Documents `/sq:overview` | **None in this slice** — slice 366 owns the README pass for both capabilities |

---

## Cross-Slice Dependencies

**Depends on:** nothing in this initiative. [100] for the command surface (`install-commands`
exists and copies `commands/sq/`).

**Depended on by:** [366], which documents `/sq:overview` in the README alongside
`/sq:analysis understand`, and whose success criteria require both in one pass. This is the reason
the slice plan's implementation order runs 365 → 366.

**Not depended on by:** 361, 362, 363, 364 — none reads or references this command.

**Interface provided:** `{index}-analysis.overview.md` with the nine-field schema. Future Work
item (1) (emphasis parameter) extends the command's argument surface; nothing else consumes it.

**Relationship to 361–364, restated:** no build-time or run-time dependency in either direction. The
connection is the human-mediated chain in D8 — those slices can produce planning documents a human
adopts, and this command reads adopted planning documents. Neither half needs the other to exist.

---

## Success Criteria

1. `commands/sq/overview.md` exists and is the only file added by the slice; `git diff --stat`
   shows no `.py` file touched.
2. Across the fixture range in D3 — concept absent, concept present with unmatched headings,
   concept section empty, plan without dependencies, plan without non-goals, plan of one-line
   stubs, plan without statuses — every run either produces a nine-field document whose gap markers
   accurately name what was missing, or hits one of the two defined stops. No run produces a blank
   field, filler prose, or an unexplained omission.
2a. Squadron is included as one real-world sample of that range (concept absent, plan complete),
    not as the baseline the design is fitted to.
3. No slice index, phase number, initiative index, or frontmatter field name appears in the
   document body. `grep -nE 'docType|Phase [0-9]|initiative [0-9]|slice [0-9]' body` returns
   nothing.
4. Not-started initiatives are described as planned; no sentence implies more progress than the
   inputs support.
5. Every one of the nine fields traces to a named source or carries a `[GAP: ...]` marker; every
   marker in the body also appears in the provenance flagged-gaps line, and the counts match.
6. A `[GAP: ...]` marker names both what is missing and which input would supply it.
7. Purpose with no concept is derived from the initiative plan and says so in place — it is not a
   gap (D4).
8. Both stops behave correctly and write nothing: a missing or unreadable initiative plan produces
   an error naming the expected path, and a plan with no parseable initiatives produces an error
   stating what was found versus expected.
8a. Graph-derived artifacts present in the repo are not read. With a knowledge graph, comprehension
    analysis, and candidates document all present, the provenance section-sourcing lines name only
    the concept and initiative plan.
9. `sq install-commands` places `overview.md` in `~/.claude/commands/sq/` with no installer change.
10. Output carries `docType: analysis`, `topic: overview`, `status: not_started`, a real `model:`
    id, and a provenance block placed above all content; `cf validate frontmatter` passes.
11. The document contains zero `[INFERRED]` markers — `grep -c 'INFERRED'` returns 0.
12. The convention sections in `overview.md` match `commands/analysis/understand.md` in substance,
    with only the divergences listed in D2, each stated in the file.

**What the fixtures do and do not establish.** Running the range in criterion 2 establishes that
degradation is *accurate and complete* — every missing input is named, nothing is invented, nothing
renders blank. That is verifiable here and is a real claim.

**Explicit non-criterion — stakeholder usefulness of a degraded document.** Whether a heavily
gap-marked overview is worth handing to a stakeholder is a judgment about content quality on a real
project, not a property the fixtures can show. A green walkthrough is evidence the mechanics are
sound, not evidence the output reads well to a manager. That judgment needs a real project with a
real reader.

**Explicit non-criterion — quality of generated planning documents.** Where an inherited project's
concept and initiative plan came from the generation chain in D8, this slice does not assess whether
those documents were good enough to adopt. That question belongs to the slices that produce them,
which deferred it themselves.

---

## Verification Walkthrough (draft)

To be executed and rewritten as-executed at Phase 6 close-out.

**Invocation note.** `/sq:overview` is a first-party command; it is not routed through
`/sq:analysis` and needs no dispatcher change. Confirm the actual invocation form against the
command file's own frontmatter before executing, and record any correction here.

### W1 — Registration

```bash
sq install-commands
ls ~/.claude/commands/sq/overview.md
```

Expect the file present, with no installer change in the diff.

### W2 — The degradation range, against constructed fixtures

This is the core verification step, and it replaces a single missing-input check. Build each fixture
as a minimal `project-documents/user/project-guides/` tree in a scratch directory **outside the repo
working tree**, and run the command against each. Squadron's own documents are never moved or
modified to create a fixture.

| # | Fixture | Expected outcome |
|---|---|---|
| a | No initiative plan | **Stop.** Error names the expected path and points at Phase 1. Nothing written. |
| b | Plan present, no parseable initiatives | **Stop.** Error states what was found versus expected. Nothing written. |
| c | Plan complete, no concept | Document written. Problem, Audience, Approach are markers; Purpose falls back to the plan and says so. |
| d | Concept present, headings differ from expected | Document written. Affected fields are markers naming the section that was expected — not silently empty. |
| e | Concept present, a section exists but is empty | Same as (d): a marker, never a blank field, never filler. |
| f | Plan states no dependencies | Roadmap orders by plan order and states that fallback in place. |
| g | Plan states no non-goals | Scope carries included work; excluded work is a marker. |
| h | Plan entries are one-line stubs | Benefits and Scope carry only what is there. Thinness is visible; nothing is padded to look fuller. |
| i | Plan has no statuses or checkboxes | Status is a marker, not an assumed state. |

For every fixture that produces a document, confirm the same three properties: **no blank field, no
invented content, and every gap marker names something genuinely absent.** A marker naming the wrong
missing input is as much a failure as no marker at all.

The most informative failures here are (d), (e), and (h) — the cases where something was technically
read. Those are where a field renders blank or gets quietly filled.

### W3 — Squadron as one real-world sample

Confirm the starting state first:

```bash
ls project-documents/user/project-guides/
```

Expect only `001-initiative-plan.squadron.md` — no concept. This matches fixture (c), and squadron
is run here as a real instance of that shape, not as the reference case the design was fitted to.

Expect a new `946-analysis.overview.md` (or the lowest unused index ≥ 940 at execution time) in
`project-documents/user/analysis/`.

The value of this run over fixture (c) is scale: squadron's plan carries thirteen initiatives with
real prose, so it exercises the translation rules (D5) against content a synthetic fixture cannot
reproduce.

### W4 — Field completeness and the sourced-or-gapped rule

For each of the nine fields, confirm it is present and resolves to exactly one of: sourced content
naming its source in the provenance section-sourcing line, or a `[GAP: ...]` marker.

Expect markers on **Problem**, **Audience**, and **Approach** (concept-sourced, no concept
present), and expect **Purpose** to be present as initiative-plan-derived content stating that
fallback in place — not a marker (D4, criterion 7).

### W5 — Gap-marker double placement

```bash
grep -c 'GAP:' project-documents/user/analysis/946-analysis.overview.md
```

Count body markers and provenance flagged-gaps entries separately and confirm every body marker
appears in the provenance list. Confirm each marker names both halves.

### W6 — Internal vocabulary stripped

```bash
grep -nE 'docType|Phase [0-9]|[Ii]nitiative [0-9]{3}|[Ss]lice [0-9]{3}|not_started|in_progress' \
  project-documents/user/analysis/946-analysis.overview.md
```

Hits are expected in the frontmatter and provenance block only. Any hit in the nine field sections
is a failure. Confirm initiatives are rendered by title with the index dropped, and confirm domain
vocabulary (pipeline, review, agent) was **not** stripped (D5).

### W7 — Status honesty

Cross-check each initiative's rendered status against its `Status:` value and checkbox in
`001-initiative-plan.squadron.md`. Every `not_started` initiative must read as planned. Spot-check
at least the three unambiguous cases: a complete one, an in-progress one, and a not-started one.

### W8 — Traceability spot-check

Pick three sourced claims — one from Benefits, one from Scope, one from Roadmap — and locate the
supporting text in the initiative plan. A claim that cannot be located is an invention and fails
criterion 5.

### W9 — Frontmatter gate and no-invention checks

```bash
cf validate frontmatter project-documents/user/analysis/946-analysis.overview.md
grep -c 'INFERRED' project-documents/user/analysis/946-analysis.overview.md
```

Expect a clean pass and a count of 0.

### W10 — Convention parity

Diff this file's convention sections against `commands/analysis/understand.md`'s Document
Conventions. Expect only the D2 divergences, each stated in `overview.md`.

### W11 — Graph-derived artifacts are not read

Squadron's repo already carries `.understand-anything/knowledge-graph.json`, two comprehension
analyses, and an initiative-candidates document — so the W3 run is already this test. Confirm the
provenance section-sourcing lines name **only** the concept and initiative plan, and that no field's
content traces to any of those artifacts (criterion 8a).

Confirm the command file states the exclusion and the reason (D8), so a future maintainer finds the
answer rather than re-deriving it.

### W12 — Idempotence and non-destructiveness

Run the command a second time. Expect a **new** index (947), the first document untouched, and
`001-initiative-plan.squadron.md` byte-identical (`shasum` before and after).

### W13 — Guards

```bash
.venv/bin/ruff format --check .
.venv/bin/pytest tests/skills/
```

Expect clean and green. No Python source changed, so these confirm the slice broke nothing.

---

## Risks

**Low overall.** One item is worth naming:

**Convention drift between the two files (D1).** Restating conventions in two places means a later
change to gap-marker syntax or provenance-line composition can land in one file and not the other.
Mitigated by W10 and by task-level explicitness — process, not machinery, which is the honest
weakness. A shared fragment read by both files stays open as the structural fix, deferred rather
than rejected, with its actual installer cost unverified (D1). Whoever next touches either file is
the right person to answer that with evidence.

---

## Relative Effort

3/5 — matching the slice plan. One markdown file, but a substantial one: nine field mappings with
per-field fallback semantics, four translation rules in mechanical form, and a full restatement of
the generated-document conventions.

---

## Open Questions for Phase 6

None blocking. Two items to resolve during implementation and record at close-out:

1. **Concept section-name matching.** The field schema names concept sections (*Overview*,
   *Problem & Motivation*, *Target Users*, *Solution Approach*). Matching should be lenient per the
   project's parsing rule, and the concept guide's actual layout is the authority on the expected
   headings — read it during implementation rather than matching the names in this design.
   Fixtures (d) and (e) in W2 make the behavior testable without waiting for a real concept: the
   requirement is that an unmatched or empty section yields a marker naming what was expected, so
   a reader can tell a mis-titled section from an unwritten one.
2. **Benefits granularity.** Whether Benefits renders one outcome per initiative or a consolidated
   set of themes. Decide against the real output in W3, where squadron's thirteen initiatives make
   over-enumeration visible; fixture (h) covers the thin-input end of the same question.
