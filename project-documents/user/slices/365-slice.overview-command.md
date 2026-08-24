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

Deliver `/sq:overview` as a first-party command in `commands/sq/`, reading squadron's own planning
artifacts and writing `{index}-analysis.overview.md` for a non-engineering reader.

**One file is added: `commands/sq/overview.md`.** No Python, no installer change, no manifest
change, no CLI registration. `sq install-commands` copies `commands/sq/*.md` wholesale
(`src/squadron/cli/commands/install.py:48-55` — `sorted(sub.glob("*.md"))` per subdirectory into
`~/.claude/commands/{sub}/`), so the file's presence is its registration.

This slice has **no dependency on the knowledge graph, on `understand-anything`, or on slices
361–364**. It is capability (b) in full.

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
statement*, not of logic, and the alternative — a shared fragment installed by both paths — would
require an installer change this initiative has committed to not making, in an initiative whose
plan states plainly that no slice adds Python.

**Drift control:** the two statements must remain identical in substance. The task breakdown carries
an explicit step that diffs this file's convention sections against `commands/analysis/understand.md`
and records any deliberate divergence in the file itself. Two divergences are already known and
intended, listed in D2.

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

### D3 — Inputs, and the two missing-input cases are not the same

| Input | Path | Required? | If absent |
|---|---|---|---|
| Initiative plan | `project-documents/user/project-guides/001-initiative-plan.{project}.md` | **Yes** | Stop with an actionable error. No document is written. |
| Concept | `project-documents/user/project-guides/000-concept.{project}.md` | No | Proceed; concept-sourced fields become gap markers. |

**A missing initiative plan is a stop, not a gap.** Five of the nine fields source from it, and a
document in which the majority of fields are markers is not an overview — it is a report that the
project has not been planned. The error names the expected path and points at Phase 1 of the
process guide as what produces it.

**A missing concept is a first-class path**, not an edge case, and is the path this slice is
verified on (see Verification Walkthrough). Squadron itself has no `000-concept.squadron.md` —
confirmed: `project-documents/user/project-guides/` contains only the initiative plan.

**The plan's caution is carried into this design.** Squadron is a *fixture* for the missing-concept
path, not evidence the path is common, and not a representative instance of it. On a client repo
the absence means Phase 0 has not yet run and running it would resolve the absence; on squadron it
is a bootstrap ordering fact — concept generation (363) postdates the project that built it. This
slice verifies the **mechanics** of degradation. Whether the degraded output is *useful* is judged
on a repo whose concept is genuinely pending, and is recorded here as an explicit non-criterion.

**Project name resolution.** The `{project}` in both paths is resolved from the initiative plan's
own `project:` frontmatter field, which is authoritative because that file is required. Filename
matching is the fallback only when that field is absent, and a mismatch between the field and the
filename is reported rather than silently preferred.

### D4 — Every field is sourced or gapped; there is no third outcome

This is the structural enforcement of "derive, never invent" from the architecture. It is not a
guideline in the command file — it is the shape of the generation loop: the skill walks the nine
fields in order, and for each one either extracts from its named source or emits a marker naming
what is missing and which input would supply it.

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

### D7 — One neutral document; no emphasis parameter

The command takes no audience argument. Client, management, and colleague readings differ in
emphasis, not in fact, and three variants means three artifacts to keep true. Per-audience emphasis
is already recorded as Future Work item (1) in the slice plan, dependent on this slice, to be
pursued only if real use shows one document is insufficient.

The command does accept an optional **topic** argument, because the naming convention already
provides for it: `{index}-analysis.overview.{topic}.md` where a project needs more than one. With
no argument, the plain form is written. This is a filename affordance, not a content variant — the
generation rules are identical either way.

---

## Data Flow

```
/sq:overview [topic]
      │
      ├─ 1. Resolve project name ── initiative plan frontmatter `project:`
      │
      ├─ 2. Read required input ─── 001-initiative-plan.{project}.md
      │        └─ absent ──► STOP, name the path, point at Phase 1. Nothing written.
      │
      ├─ 3. Read optional input ─── 000-concept.{project}.md
      │        └─ absent ──► record in provenance Source line; concept-sourced fields → markers
      │
      ├─ 4. Field loop (nine fields, in schema order)
      │        for each: extract from named source ──► content
      │                  source absent/empty      ──► [GAP: what — which input]
      │        (no third branch)
      │
      ├─ 5. Apply translation rules to assembled content (D5)
      │
      ├─ 6. Select index ── lowest unused 9nn ≥ 940 in user/analysis/
      │
      └─ 7. Write ── frontmatter, H1, ## Provenance, nine field sections
```

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

---

## Success Criteria

1. `commands/sq/overview.md` exists and is the only file added by the slice; `git diff --stat`
   shows no `.py` file touched.
2. Running the command against squadron — used as a **fixture** for the missing-concept path, not
   as a representative instance of it — produces a complete nine-field overview with gap markers
   where concept-sourced content would have gone.
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
8. With the initiative plan absent, the command stops with an error naming the expected path, and
   writes nothing.
9. `sq install-commands` places `overview.md` in `~/.claude/commands/sq/` with no installer change.
10. Output carries `docType: analysis`, `topic: overview`, `status: not_started`, a real `model:`
    id, and a provenance block placed above all content; `cf validate frontmatter` passes.
11. The document contains zero `[INFERRED]` markers — `grep -c 'INFERRED'` returns 0.
12. The convention sections in `overview.md` match `commands/analysis/understand.md` in substance,
    with only the divergences listed in D2, each stated in the file.

**Explicit non-criterion — degraded-output usefulness.** Whether the missing-concept output is
*useful* is not verified by this slice. Squadron's missing concept is a bootstrap ordering fact, not
a representative instance of the client-repo case, so a green walkthrough here is evidence the
mechanics work — not evidence the degraded document is worth handing to a stakeholder. That
judgment belongs on a repo whose concept is genuinely pending.

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

### W2 — Preflight, missing required input

Temporarily point the command at a path with no initiative plan (a scratch tree **outside the repo
working directory** — never by moving squadron's own plan).

Expect: an error naming the expected initiative-plan path and pointing at Phase 1; **nothing
written**; `git status` clean.

### W3 — The real run, missing-concept path

Confirm the starting state first:

```bash
ls project-documents/user/project-guides/
```

Expect only `001-initiative-plan.squadron.md` — no concept. Then run the command.

Expect a new `946-analysis.overview.md` (or the lowest unused index ≥ 940 at execution time) in
`project-documents/user/analysis/`.

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

### W11 — Idempotence and non-destructiveness

Run the command a second time. Expect a **new** index (947), the first document untouched, and
`001-initiative-plan.squadron.md` byte-identical (`shasum` before and after).

### W12 — Guards

```bash
.venv/bin/ruff format --check .
.venv/bin/pytest tests/skills/
```

Expect clean and green. No Python changed, so these confirm the slice broke nothing.

---

## Risks

**Low overall.** One item is worth naming:

**Convention drift between the two files (D1).** Restating conventions in two places means a later
change to gap-marker syntax or provenance-line composition can land in one file and not the other.
Mitigated by W10 and by task-level explicitness, not by machinery — a shared fragment would require
the installer change this initiative has ruled out. If drift recurs in practice, the correct fix is
a Future Work item for a shared-fragment install path, not an ad-hoc reference from a first-party
command to an opt-in pack.

---

## Relative Effort

3/5 — matching the slice plan. One markdown file, but a substantial one: nine field mappings with
per-field fallback semantics, four translation rules in mechanical form, and a full restatement of
the generated-document conventions.

---

## Open Questions for Phase 6

None blocking. Two items to resolve during implementation and record at close-out:

1. **Concept section-name matching.** The field schema names concept sections (*Overview*,
   *Problem & Motivation*, *Target Users*, *Solution Approach*). Whether matching is exact-heading
   or lenient should follow the project's parsing rule (prefer lenient over strict) and be settled
   against the concept guide's actual layout when a concept is first available. Squadron's run
   cannot settle it — there is no concept to match against.
2. **Benefits granularity.** Whether Benefits renders one outcome per initiative or a consolidated
   set of themes. Decide against the real output, where over-enumeration will be visible.
