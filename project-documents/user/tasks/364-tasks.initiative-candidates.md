---
docType: tasks
slice: initiative-candidates
project: squadron
lldReference: project-documents/user/slices/364-slice.initiative-candidates.md
parent: project-documents/user/architecture/360-slices.document-intelligence.md
dependencies: [361, 362]
projectState: Slices 361, 362, 363 merged to main. 364 design committed 192cdcf, slice review PASS with five pass-severity findings and nothing to resolve (88e299e). Real v2.8.1 graph present at .understand-anything/, gitCommitHash 1bfbca1, unchanged since 363 — now 56 commits behind HEAD.
dateCreated: 20260823
dateUpdated: 20260824
status: in_progress
---

# Tasks: Initiative Candidates

## Context Summary

- Working on slice **364**, the fourth slice in initiative 360: propose initiative-shaped work
  items from the knowledge graph into a standalone
  `{index}-analysis.initiative-candidates.md`.
- **Everything here is markdown editing.** No Python. The only changed non-document file is
  `commands/analysis/understand.md` (a third sibling flow section), plus two cross-reference
  sentence fixes in existing flow text.
- Two design decisions govern the whole slice and are not open:
  - **The concept is an optional ordering input.** It affects candidate **order** only — it never
    creates, suppresses, or supplies a candidate the graph does not support. No concept → order by
    signal strength, degradation stated in body and provenance.
  - **Candidate usefulness is an explicit non-criterion.** Mechanical correctness verifies against
    squadron; usefulness does not, because squadron's initiative plan is hand-written. A green
    walkthrough here is evidence of mechanics only.
- **The no-padding rule is the highest-value behavior in the flow.** A padded list is
  indistinguishable from a real one to a reader, and one invented candidate makes every other
  candidate suspect. Zero candidates is a success that still writes a document.
- **362's mechanics are cited, never restated** — file-level definition, `nodeIds | length`
  counting with type breakdown, ordinal `complexity` handling, layer cross-check drift rule, edge
  endpoint string-parse resolution. A restated rule drifts from its original.
- Design review: PASS, five findings all `severity: pass`, nothing to address.

### Verified anchors (traced 20260823 on `main` at `88e299e`)

| Anchor | Fact |
|---|---|
| Skill file | `commands/analysis/understand.md` exists, 1064 lines |
| Graph | `.understand-anything/knowledge-graph.json` + `meta.json` present; `gitCommitHash` `1bfbca1` — same graph 362 and 363 measured |
| Staleness | Graph is **56 commits behind HEAD** (was 45 at 363's walkthrough). Preflight warns and proceeds; this is an expected observation, not a blocker |
| Graph `project.name` | `squadron-ai` — diverges from cf project name `squadron` |
| Layers | 10 layers; `nodeIds` counts 56/34/32/29/20/20/17/12/12/6 |
| Complexity | file-level distribution `complex:43 moderate:89 simple:106` |
| Complex-per-layer | Pipeline Orchestration 14, Metrology Subsystem 9, CLI Surface 7, Review Engine 7, Provider & Agent Abstraction 3, Packaged Declarative Content 1, Server & Client Surface 1, Shared Foundation 1 |
| `candidates` references | Two in the skill: line 399 (flow selection, "not recognized") and line 649 (comprehension flow cross-reference). **Both** need updating |
| Existing concept | `user/project-guides/` holds only `001-initiative-plan.squadron.md` — no `000-concept.*`. The degraded path is the default on this repo |
| Archived concept | `user/archive/000-concept.squadron.md` present, `docType: notes`, `status: deprecated` — the fixture for the engagement-informed walkthrough. **Scratch copies only** |
| Next analysis index | `user/analysis/` holds `940`–`944`; next free is **945** |
| Skills tests | `tests/skills/` — 7 files; regression guard only, this slice adds no test |

### PM interaction notice

Walkthrough Tasks 8.2 and 8.3 require the PM live: the write confirmation is answered once as
decline and once as confirm. Before running either, tell the PM what is about to happen and why —
which walkthrough step, what will be asked. Never fire the prompt without framing. AskUserQuestion
is not used; ask in plain text.

---

## Task 0: Branch and premise verification

- [x] **0.1 Create the slice branch** — Effort: 1/5
  - [x] Confirm working tree is clean and current branch is `main` (integration branch is unset;
        target is `main`).
  - [x] `git checkout -b 364-slice.initiative-candidates main`
  - [x] Success: on the new branch, clean tree.

- [x] **0.2 Re-verify the design's premises** — Effort: 1/5
  - [x] Confirm the graph identity is unchanged: `gitCommitHash` is `1bfbca1`.
  - [x] Re-run the two derivation queries from the design's Verification Walkthrough step 2
        (layer sizes; complex file-level nodes per layer) and compare against the Verified anchors
        table above.
  - [x] Confirm `user/project-guides/` still holds no `000-concept.*`, and
        `user/archive/000-concept.squadron.md` is still present.
  - [x] Confirm both `candidates` references are still at the recorded locations (search the skill
        file; line numbers may have shifted).
  - [x] **STOP condition:** if the layer or complexity figures diverge from the anchors table, stop
        and report to the Project Manager — the design's reasoning about candidate count and
        ordering was measured against these figures.
  - [x] Success: all checks match, or work is stopped.

## Task 1: Flow selection

- [x] **1.1 Add `candidates` to the flow selector** — Effort: 2/5
  - [x] In `commands/analysis/understand.md`, add the `candidates` row to the flow-selection
        table, routing to Flow: Initiative Candidates.
  - [x] **Remove** the paragraph beginning "`candidates` is **not** recognized" (skill line ~399).
        Remove, do not amend — an amended exclusion note reads as a live exclusion.
  - [x] Preserve the "anything else → unrecognized, stop" case and the explicit-argument-only rule
        unchanged. Add one sentence: the presence or absence of a concept document selects nothing
        — it changes only what this flow reads once named.
  - [x] Add the empty sibling section shell "Flow: Initiative Candidates" after Flow: Concept
        Generation, before the human-documentation divider.
  - [x] Success: selector covers all five argument cases; exclusion paragraph gone; concept-selects-
        nothing sentence present; section shell in the stated position.

- [x] **1.2 Fix the comprehension flow's cross-reference** — Effort: 1/5
  - [x] At skill line ~649, the comprehension flow says "initiative candidates are slice 364".
        Edit to reflect that the flow now exists, matching how 363 fixed the equivalent sentence
        for the concept flow.
  - [x] Success: no remaining sentence in the skill describes this flow as future work. Verify by
        searching the file for `364` and confirming every hit is a live reference.
  - [x] Commit: `feat: add candidates flow selector to understand skill`

## Task 2: Preconditions

- [x] **2.1 Author the preconditions** — Effort: 1/5
  - [x] Precondition 1 — graph present: the 361 preflight, executed unchanged and in full
        (location, validation, staleness, `.gitignore` hygiene). Reference the shared contract; do
        not duplicate it. State that this flow adds no hygiene behavior and skips none.
  - [x] Precondition 2 — resolvable project name from the cf project registration, never
        `project.name` from the graph.
  - [x] State explicitly: **the concept document is not a precondition.** Its absence is an
        observation the flow records, not a stop.
  - [x] State that there is no `/cf:onboard` boundary concern here — this flow writes to
        `analysis/`, which the comprehension flow already writes to.
  - [x] Success: two preconditions authored; the concept's non-precondition status stated; no
        preflight logic duplicated.

- [x] **2.2 Verify preconditions against the design** — Effort: 1/5
  - [x] Check the section against the design's Preconditions: two numbered items, the
        concept-not-a-precondition statement, and the `/cf:onboard` note.
  - [x] Success: exact correspondence; no third precondition introduced.
  - [x] Commit: `docs: add candidates flow preconditions`

## Task 3: The candidate derivation model

- [x] **3.1 Author the two signal classes** — Effort: 3/5
  - [x] Write the signal table: **layer boundary** (`layers[]` — `name`, `description`, `nodeIds`)
        and **complexity cluster** (file-level `nodes[]` `complexity`, `filePath`, intersected with
        `layers[].nodeIds`). Exactly two classes; no third.
  - [x] State the one-signal rule: **a candidate names exactly one signal.** Where one layer
        supports both observations, that is two candidates or one — never one candidate citing
        two. Give the reason: a candidate citing both is checkable against neither.
  - [x] Cite 362's mechanics by reference — file-level definition, `nodeIds | length` counting with
        type breakdown, ordinal `complexity` handling, layer cross-check drift rule. **Do not
        restate them.**
  - [x] State what this flow does **not** read: no `tour[]`, no `entry-point` tags, no `meta.json`
        coverage read.
  - [x] Success: two signal classes with source fields; one-signal rule with its reason; 362
        mechanics cited not restated; the not-read list present.

- [x] **3.2 Author the no-padding rule** — Effort: 2/5
  - [x] State it plainly: candidates the graph does not support are not proposed. **No target
        count, no minimum, no maximum.**
  - [x] Give the reason the design records: a padded list is indistinguishable from a real one to a
        reader, and one invented candidate makes every other candidate suspect.
  - [x] State that **emitting zero candidates is a success, not a failure** — the document is still
        written (on confirmation) and states that the graph supported no candidate, naming what was
        looked for.
  - [x] Success: rule, reason, and zero-is-success statement all present and unhedged.

- [x] **3.3 Verify the derivation model** — Effort: 1/5
  - [x] Check against the design's "The candidate derivation model": signal table matches
        field-for-field; the one-signal rule is stated as a rule, not a preference; no 362
        mechanic has been restated in place of a citation.
  - [x] Success: correspondence confirmed.
  - [x] Commit: `docs: add candidate derivation model and no-padding rule`

## Task 4: The optional concept read

- [x] **4.1 Author what is read** — Effort: 2/5
  - [x] Name the path: `project-documents/user/project-guides/000-concept.{project}.md`.
  - [x] **Two sections only** — User-Provided Concept (verbatim engagement answers, Q1 in
        particular) and Problem & Motivation (the engagement half).
  - [x] State the exclusion and its reason: not Solution Approach, not Initial Technical Direction,
        not Development Approach — those are graph-derived in the concept itself, so reading them
        would launder graph content through a second document and present it as independent
        corroboration.
  - [x] Success: path, the two sections, and the exclusion-with-reason all present.

- [x] **4.2 Author what it changes and what it does not** — Effort: 2/5
  - [x] Write the three-row effect table: **which candidates exist** — none, the concept never
        creates, suppresses, or supplies a candidate the graph does not support; **their order** —
        this is the whole effect; **their scope statements** — may frame work in terms of stated
        intent, provided every factual claim still traces to a graph signal.
  - [x] State the boundary and why it matters: the concept cannot manufacture a candidate, and this
        is what keeps the no-padding rule enforceable. If engagement context could originate
        candidates, "we're here to modernize" would license proposing anything at all.
  - [x] State that ordering influence is **declared per candidate**, not applied invisibly — an
        ordered-up candidate says so and names the concept as the reason.
  - [x] Success: effect table with all three rows; the manufacture boundary with its reason; the
        per-candidate declaration rule.

- [x] **4.3 Author the degradation path** — Effort: 2/5
  - [x] No concept, or a concept lacking both named sections: order by **signal strength alone** —
        descending count of `complex` file-level nodes for complexity clusters, descending
        `nodeIds | length` for layer boundaries.
  - [x] The degradation is stated **in the document body and in provenance**, never silent. Include
        the body line from the design, naming what was missing and what a concept would have
        changed.
  - [x] **Both-questions-declined is recorded distinctly from no-document.** A declined interview
        and a missing document are different facts; collapsing them would hide that the interview
        happened.
  - [x] Success: degradation rule, the body line, and the declined-vs-absent distinction all
        present.

- [x] **4.4 Verify the concept read** — Effort: 1/5
  - [x] Check against the design's "The optional concept read": two sections read, three-row effect
        table, degradation with the distinct declined case.
  - [x] Confirm no sentence anywhere in the new flow makes the concept a precondition or a
        dependency.
  - [x] Success: correspondence confirmed; no precondition language.
  - [x] Commit: `docs: add optional concept read and degradation path`

## Task 5: Candidate record shape and dependency derivation

- [x] **5.1 Author the five-part record** — Effort: 3/5
  - [x] Write the record table in order: **title** (authored — names the work, not the observation;
        include the design's contrasting example), **derivation signal** (one, named, with its
        field), **supporting node IDs** (actual ids; every id must resolve to a node carrying a
        `filePath`; an unresolvable id is drift per 362, and a candidate whose supporting ids are
        all drift is not emitted), **scope statement** (one paragraph; every factual claim traces
        to the signal or a cited node; no effort estimates, timelines, or business value
        judgments), **observed dependencies** (derived, never asserted; an empty result is written
        as "none observed", not omitted).
  - [x] State the citation rule: **node IDs are cited, not summarized.** A candidate supported by
        fourteen nodes lists them. Give the reason — the document is a working artifact for someone
        deciding whether to adopt, and "several files in Pipeline Orchestration" is not checkable.
  - [x] State the authored/extracted asymmetry: title and scope are the only authored parts, both
        constrained by the three extracted parts. Prose checkable against cited ids is safe; prose
        standing alone is not.
  - [x] Success: five parts in order with their rules; citation rule with reason; asymmetry stated.

- [x] **5.2 Author dependency derivation** — Effort: 3/5
  - [x] Cite 362's endpoint mechanics by reference: string parse of the edge's own `source`/`target`
        id (second colon-delimited field is the owning file's path, which resolves to a layer),
        `imports` and `depends_on` types, self-references excluded, **no node read to resolve an
        endpoint** and specifically no `function` or `class` node.
  - [x] Write the three-step derivation: collect each candidate's implicated layer set; for each
        ordered pair count inter-layer edges; a non-zero count is a stated dependency **carrying
        the count**.
  - [x] State the non-sequencing rule prominently: a stated dependency is a **directional edge
        count, not a claim about ordering**. The document says "Candidate 3's layers hold 27
        imports into Candidate 1's layers"; it does not say Candidate 1 must be done first. That
        inference belongs to the human adopting the candidates.
  - [x] State the two edge cases: unresolvable endpoints excluded and reported as drift per 362;
        two candidates implicating the same layer have that overlap **stated**, not expressed as a
        dependency — a layer does not depend on itself.
  - [x] Success: mechanics cited not restated; three-step derivation; non-sequencing rule; both
        edge cases.

- [x] **5.3 Verify record and dependency sections** — Effort: 1/5
  - [x] Check against the design's "Candidate record shape" and "Dependency derivation": five parts
        in the design's order; the non-sequencing rule present and unhedged.
  - [x] Confirm no dependency language implies sequencing anywhere in the new flow text.
  - [x] Success: correspondence confirmed.
  - [x] Commit: `docs: add candidate record shape and dependency derivation`

## Task 6: The write confirmation

- [x] **6.1 Author the confirmation** — Effort: 2/5
  - [x] One interaction, **after derivation and before any file write.** Show: the candidate
        **count**; each candidate's **title and derivation signal**, one line apiece; the
        **ordering basis** — engagement-informed (naming the concept) or signal-strength-only
        (naming the concept's absence).
  - [x] State what is being confirmed: **that the document is worth writing at all** — not the
        correctness of individual candidates, not their adoption. Give the reason this makes the
        interaction cheap: the operator answers "is this set worth a file?", answerable from titles
        and signals, not "is candidate 4 correct?", which is not.
  - [x] Write the three-outcome table: confirmed → written, provenance `confirmed`; declined →
        **nothing written**, set shown in console and discarded; no answer → **nothing written**.
  - [x] Success: the three shown items; the scope-of-confirmation statement with its reason; the
        outcome table.

- [x] **6.2 Author the default-to-not-writing rule and its contrast** — Effort: 2/5
  - [x] State plainly: **this flow's confirmation defaults to not writing.**
  - [x] State the contrast with 363 and the reason, from the design: 363's confirmation never
        stalls and proceeds on no answer because it writes a Phase 0 entry point a repo has no
        other way to obtain; this writes an advisory list that costs nothing to regenerate. 363's
        failure mode is a lost interview; this flow's is an unwanted file in `analysis/`.
  - [x] State the zero-candidate case: a run deriving nothing **still asks** — showing "0
        candidates, derived from N layers and M complex file-level nodes" — and on confirm writes
        the document recording the negative result. Give the reason: the negative result is a real
        finding, and suppressing the question would make an empty result indistinguishable from a
        failed run.
  - [x] Success: default stated; contrast with 363 including both failure modes; zero-candidate
        case with its reason.

- [x] **6.3 Verify the confirmation section** — Effort: 1/5
  - [x] Check against the design's "The write confirmation": outcome table matches row-for-row;
        the default-to-not-writing rule is explicit, not implied by the table alone.
  - [x] Confirm the zero-candidate path asks and writes rather than exiting silently.
  - [x] Success: correspondence confirmed.
  - [x] Commit: `docs: add candidates write confirmation`

## Task 7: Output conventions, gap markers, read discipline

- [x] **7.1 Author output conventions** — Effort: 2/5
  - [x] Path: `project-documents/user/analysis/{index}-analysis.initiative-candidates.md`.
  - [x] Index selection: cite the shared Generated document conventions rule — lowest unused index
        ≥ 940, **new index per run**, never overwriting. Do not restate the rule's mechanics.
  - [x] Frontmatter block: `docType: analysis`, `project`, `topic: initiative-candidates`,
        `dateCreated`, `dateUpdated`, `status: not_started`, `model`.
  - [x] State that `{project}` resolves from the cf project registration, never `project.name` from
        the graph, and that `model:` follows the shared rule unchanged — the real generating model
        id or an explicit stop, never a placeholder.
  - [x] Success: path, cited index rule, frontmatter block, both resolution rules.

- [x] **7.2 Author the provenance block** — Effort: 2/5
  - [x] Flow-specific content: **generated by** (flow + model id); **generated on**; **source**
        (graph identity — `gitCommitHash`, `lastAnalyzedAt`; the concept path when read, or an
        explicit statement that none was found); **ordering basis** (`engagement-informed` or
        `signal-strength-only`, citing the concept's absence or both-declined); **candidate count**
        and the signal counts it derived from; **drift** per 362; **flagged gaps**, **staleness**,
        **review state** as in the shared block.
  - [x] Author the **non-modification statement in the document body** — not only in provenance:
        the document states it is advisory, that adoption is manual, and that
        `001-initiative-plan.{project}.md` was not read for writing and not modified.
  - [x] Success: every provenance line present; the body-level non-modification statement authored.

- [x] **7.3 Author gap markers, `[INFERRED]` exclusion, and read discipline** — Effort: 2/5
  - [x] Gap markers use the shared 361 syntax. This flow's genuine absences: no concept document, a
        concept with no usable engagement content, zero candidates derived. Each gets a marker
        naming the input that would have supplied it.
  - [x] State that **`[INFERRED]` is not used in this flow**, with the structural reason: a claim
        not traceable to a cited signal or node id has no place in the document at all — the record
        shape's whole design is that authored parts are checkable against extracted parts. A
        sentence needing `[INFERRED]` is a sentence to delete.
  - [x] State this explicitly in the skill text so the absence reads as a decision, not an
        oversight. Update the shared Gap markers section's pointer if it enumerates per-flow
        `[INFERRED]` governance.
  - [x] Read discipline: cite 362's unchanged. Name the fields this flow reads — `layers[]`,
        file-level `nodes[]` (`complexity`, `filePath`), `edges[]` (`type`, `source`, `target`) —
        and nothing else. The concept read is a bounded read of two named sections.
  - [x] Success: gap-marker cases; `[INFERRED]` exclusion with reason and explicit statement; read
        discipline citing 362 with the field list.

- [x] **7.4 Verify conventions sections** — Effort: 1/5
  - [x] Check against the design's "Output conventions", "Gap markers and `[INFERRED]`", and "Read
        discipline".
  - [x] Confirm the flow reads no field outside the named list.
  - [x] Success: correspondence confirmed.
  - [x] Commit: `docs: add candidates output conventions and read discipline`

## Task 8: Verification walkthrough

The design's Verification Walkthrough, executed. **Tasks 8.2 and 8.3 involve the PM live** — see
the PM interaction notice above.

- [x] **8.1 Flow selection** — Effort: 1/5
  - [x] Exercise all five selector cases by direct skill invocation: `candidates` → the new flow;
        no argument → comprehension; `comprehension` → comprehension; `concept` → concept;
        nonsense → unrecognized, stops.
  - [x] Success (SC1): the new row routes and the existing cases are unchanged in behavior.

- [x] **8.2 Derivation with the confirmation declined** — Effort: 2/5
  - [x] Frame for the PM first, then run `candidates` and **decline** at the confirmation.
  - [x] Confirm: the derived set is shown in the console, **no file is written**, `git status` is
        clean.
  - [x] Check the shown set against the graph using the two design queries (layer sizes; complex
        file-level nodes per layer). Every complexity-cluster candidate corresponds to a layer in
        that output, and its cited ids are a subset of that layer's complex nodes.
  - [x] Success (SC2, SC3, SC5-decline): nothing written; every candidate traceable.

- [x] **8.3 Full run with confirmation** — Effort: 2/5
  - [x] Frame for the PM, re-run, and **confirm**.
  - [x] `cf validate frontmatter` on the written document.
  - [x] Check by hand: five record parts in order per candidate; exactly one signal each;
        dependency lines carry counts and assert no ordering; the body states the non-modification
        guarantee.
  - [x] **The document is kept and committed.** This step writes into the real tree (unlike 8.7 and
        8.8, which use scratch copies), taking index **945**. It is the slice's proof artifact —
        the thing a reader checks the walkthrough's claims against — so it is committed here, on
        its own, rather than riding along in a later commit.
  - [x] Commit: `docs: add generated initiative candidates from walkthrough`
  - [x] Success (SC2, SC4, SC6, SC8): validation passes, all four hand checks hold, and the written
        document is committed.

- [x] **8.4 Node ID resolution** — Effort: 1/5
  - [x] For each cited node id, confirm it resolves to a node carrying a `filePath` (design query).
  - [x] An id producing no output, or a null `filePath`, is a defect against SC2 — report it rather
        than editing the document to hide it.
  - [x] Success (SC2): every cited id resolves.

- [x] **8.5 Dependency recount** — Effort: 2/5
  - [x] Spot-check one stated dependency by recounting independently: inter-layer
        `imports`/`depends_on` between the two candidates' layer sets, endpoints resolved by the
        second colon-delimited field.
  - [x] The recount must match the stated number exactly.
  - [x] Success (SC4): counts match.

- [x] **8.6 Initiative plan untouched** — Effort: 1/5
  - [x] `shasum project-documents/user/project-guides/001-initiative-plan.squadron.md` before and
        after the run; `git status --short project-documents/user/project-guides/`.
  - [x] Success (SC6): identical shasum, no modification.

- [x] **8.7 Ordering — all three concept states** — Effort: 3/5
  - [x] **Degraded (default on this repo):** squadron has no concept at the concept path, so this
        runs by default. Verify the body line and provenance name the absence and that ordering is
        by signal strength.
  - [x] **Engagement-informed:** on a **scratch copy of the tree**, restore
        `user/archive/000-concept.squadron.md` to `project-guides/000-concept.squadron.md`. Its Q1
        answer records a maintenance-takeover and modernization engagement. Verify ordering shifts
        and each affected candidate names the concept as the reason.
  - [x] **Both-declined:** on a scratch copy, a concept whose User-Provided Concept section records
        both questions declined. Verify signal-strength ordering and provenance distinguishing this
        from no-document.
  - [x] **Never restore the archived concept into the real tree** — it is `docType: notes` /
        `status: deprecated` and was archived deliberately. Scratch copies only.
  - [x] Success (SC7): all three states behave as designed and are distinguishable in provenance.

- [x] **8.8 Zero-candidate path** — Effort: 2/5
  - [x] Build a scratch fixture graph with one layer and no `complex` nodes.
  - [x] Expect: a confirmation prompt stating 0 candidates; on confirm, a written document
        recording the negative result with a gap marker naming what was looked for.
  - [x] Success (SC3, zero-candidate write): prompt appears and the document records the negative
        result rather than being skipped.

- [x] **8.9 Read discipline and guards** — Effort: 1/5
  - [x] Confirm no step of the run loaded the whole graph and no `function`/`class` node was read
        (SC9).
  - [x] `.venv/bin/ruff format --check .` and `pytest tests/skills/` — regression guards; this
        slice adds no Python and no test (SC10).
  - [x] Success (SC9, SC10): discipline held; both guards green.

## Task 9: Close-out

- [x] **9.1 Reconcile the walkthrough into the design** — Effort: 2/5
  - [x] Update the design's Verification Walkthrough from draft to the steps as actually executed,
        including any divergence found in Task 8.
  - [x] Record the four Phase-6 decisions the design deferred: the layer-boundary candidacy
        threshold; the per-candidate ordering-influence phrasing; scope-statement length
        discipline; node-ID list rendering.
  - [x] Success: the walkthrough reflects reality and the four deferred decisions are recorded with
        what was chosen.
  - [x] Commit: `docs: reconcile 364 walkthrough and record deferred decisions`

- [x] **9.2 Mark the slice complete** — Effort: 1/5
  - [x] Set `status: complete` on the slice design and this task file.
  - [x] Check slice-plan entry 4 in `360-slices.document-intelligence.md`.
  - [x] State in the close-out that the slice is **mechanically verified, usefulness unjudged** —
        pending a repo with no hand-written initiative plan. Do not let a green walkthrough be
        recorded as evidence the candidates are good.
  - [x] Success: statuses set, entry checked, the usefulness caveat recorded.
  - [x] Commit: `docs: mark slice 364 complete`

- [x] **9.3 DEVLOG and merge** — Effort: 1/5
  - [x] Write the DEVLOG entry per the Session State Summary guidance.
  - [x] `.venv/bin/ruff format --check .` before the final commit.
  - [x] Commit: `docs: record slice 364 in DEVLOG`
  - [x] Confirm the tree is clean before merging — 8.3, 9.1, and 9.2 each committed their own work,
        so nothing from the close-out should remain uncommitted at this point.
  - [x] Merge `364-slice.initiative-candidates` into `main`. **Do not delete the branch** — project
        rules require explicit instruction.
  - [x] Success: DEVLOG written, format clean, merged to `main`.

---

# Reopened 20260824 — Adoption

The slice shipped half a workflow: derivation writes a candidates document whose only route into the
initiative plan was hand-editing. Tasks 10–12 are the reopened scope. Everything above is done and
merged; none of it is being redone.

**Design reference:** "Flow: Candidate Adoption" in `364-slice.initiative-candidates.md`, success
criteria 11–21, walkthrough steps 10–17.

**Branch:** work continues on `364-slice.initiative-candidates` (preserved after the first merge, per
project rules). Re-fork from `main` if it has moved.

## Task 10: The adoption flow

- [ ] **10.1 Flow selection** — Effort: 1/5
  - [ ] Add the `candidates adopt` row to the flow-selection table in `commands/analysis/understand.md`.
  - [ ] State that adoption is a separate invocation, never chained onto a derivation run.
  - [ ] Success: six selector cases documented; the five pre-existing ones unchanged.

- [ ] **10.2 Preconditions and stops** — Effort: 1/5
  - [ ] Locate the highest-indexed `{index}-analysis.initiative-candidates.md` in
        `project-documents/user/analysis/`. Absent → stop, naming `candidates` as the flow that
        produces one. Never derive implicitly.
  - [ ] Initiative plan absent or read-only → stop **before** the triage interaction, naming the path.
  - [ ] State that this flow runs no graph preflight and reads no graph.
  - [ ] Success: both stops fire before any operator interaction.

- [ ] **10.3 The triage interaction** — Effort: 2/5
  - [ ] Parse candidate records: number, title, derivation signal, and any existing decision line.
  - [ ] Present only undecided candidates — number, title, signal, one line apiece. Report
        already-decided ones as a count, not re-presented.
  - [ ] All-decided → report counts and stop; no empty interaction.
  - [ ] Batch subset selection. Selection is the only per-candidate input.
  - [ ] Outcome table: some selected → adopt those, decline the rest; none selected → decline all,
        write nothing to the plan; abandoned → write nothing anywhere.
  - [ ] Success: the three outcomes behave as specified, and declining is recorded as a decision.

- [ ] **10.4 Rendering into the initiative plan** — Effort: 2/5
  - [ ] One entry per adopted candidate, in the plan's existing format: numbered checklist item,
        base index, title, description, dependencies, status.
  - [ ] `status: not_started`, unchecked box, description reworded from the scope statement to plan
        voice — not pasted.
  - [ ] Index assignment per the plan's stated convention: next available base index in the working
        range, respecting existing gaps.
  - [ ] Append without reordering; never modify an existing entry.
  - [ ] **Never convert an observed edge count into a stated dependency.** Dependencies are the
        operator's or `None`. Cite the candidates document by filename for the observed counts.
  - [ ] All adopted candidates written in one pass.
  - [ ] Success: entries render correctly, existing entries byte-identical, no fabricated dependency.

- [ ] **10.5 Recording decisions** — Effort: 2/5
  - [ ] Append a decision line per presented candidate: `adopted as initiative {index} on {date}` or
        `declined on {date}`. Absent line = undecided; existing documents need no migration.
  - [ ] Never modify signal, node IDs, scope statement, or dependencies. Never remove a candidate.
  - [ ] Update `dateUpdated` and add a provenance adoption line: date, adopted candidates with
        assigned indices, declined candidates.
  - [ ] Document the deliberate break from 361's sampling rule — adoption amends, derivation still
        writes a new document each run.
  - [ ] Success: decisions recorded, records otherwise untouched, the break stated in the file.

- [ ] **10.6 Failure modes** — Effort: 1/5
  - [ ] Malformed or unparseable candidates document → stop naming the file and what failed to parse.
        Never partially adopt.
  - [ ] Plan write succeeds, candidates-document write fails → report loudly, naming which candidates
        were adopted and that their decision lines are unrecorded. Plan left intact.
  - [ ] State that the two writes are not atomic and why the plan is the one left intact.
  - [ ] Success: every failure mode in the design's table is implemented and observable.
  - [ ] Commit: `feat: add candidate adoption flow to understand skill`

## Task 11: Verification walkthrough — adoption

Execute walkthrough steps 10–17 against squadron. **PM interaction required** at the triage steps —
frame each as a real decision, not a simulation.

**Squadron's plan is hand-written and already contains this work.** Adopted entries are verification
artifacts, reverted in 11.7 unless the PM decides otherwise. Say so before writing anything to the plan.

- [ ] **11.1 Flow selection and preconditions** — Effort: 1/5
  - [ ] Trace all six selector cases (step 10). Confirms SC11.
  - [ ] Both stops in a scratch tree / with a read-only plan (step 11). Confirms SC19.

- [ ] **11.2 Triage and abandon** — Effort: 1/5
  - [ ] All 8 candidates in `945-analysis.initiative-candidates.md` present as undecided (step 12).
        Confirms SC12.
  - [ ] Abandon without answering; `git status` clean (step 13). Confirms SC16.

- [ ] **11.3 Adopt a subset** — Effort: 2/5 — **PM decision**
  - [ ] Copy the plan and candidates document before writing, for the diff and the revert.
  - [ ] Select 2 of 8. Verify: two entries appended with next available indices, `not_started`,
        unchecked; other entries byte-identical and unreordered; no fabricated dependencies.
        Confirms SC13, SC14.
  - [ ] Verify all 8 gain decision lines — 2 adopted with indices, 6 declined, dated — with records
        otherwise unmodified. Confirms SC15.

- [ ] **11.4 Re-run and derivation** — Effort: 1/5
  - [ ] Re-run adoption: reports counts, stops, no empty interaction (step 15). Confirms SC17.
  - [ ] Run derivation: new document at a new index, `945` byte-identical including decision lines
        (step 16). Confirms SC18.

- [ ] **11.5 Gate and partial-write** — Effort: 1/5
  - [ ] `cf validate frontmatter` on both documents. Confirms SC21.
  - [ ] Trace the partial-write path; confirm the report names adopted candidates and unrecorded
        decision lines. Simulating is acceptable — record which was done. Confirms SC20.

- [ ] **11.6 Guards** — Effort: 1/5
  - [ ] `.venv/bin/ruff format --check .` and `.venv/bin/pytest tests/skills/`.

- [ ] **11.7 Revert verification artifacts** — Effort: 1/5 — **PM decision**
  - [ ] Ask whether any adopted entry should stay in squadron's plan.
  - [ ] Revert the plan and candidates document to their pre-walkthrough state otherwise.
  - [ ] Delete the derivation document written in 11.4 unless the PM wants it kept.
  - [ ] Confirm with `git status`.
  - [ ] Commit: `docs: record 364 adoption walkthrough`

## Task 12: Close-out

- [ ] **12.1 Reconcile the walkthrough** — Effort: 1/5
  - [ ] Rewrite walkthrough steps 10–17 as-executed, with real results.
  - [ ] Record any correction discovered during execution.

- [ ] **12.2 Mark the slice complete** — Effort: 1/5
  - [ ] Set `status: complete` on the slice design and this task file.
  - [ ] Check slice-plan entry 4 in `360-slices.document-intelligence.md`.
  - [ ] Replace the "Reopened" close-out section with the as-executed record, keeping the first
        close-out's derivation record intact.
  - [ ] State plainly what squadron's run does and does not establish: mechanics verified, candidate
        usefulness still unjudged, adoption exercised on a plan that already contained the work.

- [ ] **12.3 DEVLOG and merge** — Effort: 1/5
  - [ ] DEVLOG entry per the Session State Summary guidance — including why the slice was reopened.
  - [ ] `.venv/bin/ruff format --check .` before the final commit.
  - [ ] Confirm the tree is clean, then merge into `main`. **Do not delete the branch.**
