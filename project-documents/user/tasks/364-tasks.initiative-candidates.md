---
docType: tasks
slice: initiative-candidates
project: squadron
lldReference: project-documents/user/slices/364-slice.initiative-candidates.md
parent: project-documents/user/architecture/360-slices.document-intelligence.md
dependencies: [361, 362]
projectState: Slices 361, 362, 363 merged to main. 364 design committed 192cdcf, slice review PASS with five pass-severity findings and nothing to resolve (88e299e). Real v2.8.1 graph present at .understand-anything/, gitCommitHash 1bfbca1, unchanged since 363 — now 56 commits behind HEAD.
dateCreated: 20260823
dateUpdated: 20260823
status: not_started
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

- [ ] **2.1 Author the preconditions** — Effort: 1/5
  - [ ] Precondition 1 — graph present: the 361 preflight, executed unchanged and in full
        (location, validation, staleness, `.gitignore` hygiene). Reference the shared contract; do
        not duplicate it. State that this flow adds no hygiene behavior and skips none.
  - [ ] Precondition 2 — resolvable project name from the cf project registration, never
        `project.name` from the graph.
  - [ ] State explicitly: **the concept document is not a precondition.** Its absence is an
        observation the flow records, not a stop.
  - [ ] State that there is no `/cf:onboard` boundary concern here — this flow writes to
        `analysis/`, which the comprehension flow already writes to.
  - [ ] Success: two preconditions authored; the concept's non-precondition status stated; no
        preflight logic duplicated.

- [ ] **2.2 Verify preconditions against the design** — Effort: 1/5
  - [ ] Check the section against the design's Preconditions: two numbered items, the
        concept-not-a-precondition statement, and the `/cf:onboard` note.
  - [ ] Success: exact correspondence; no third precondition introduced.
  - [ ] Commit: `docs: add candidates flow preconditions`

## Task 3: The candidate derivation model

- [ ] **3.1 Author the two signal classes** — Effort: 3/5
  - [ ] Write the signal table: **layer boundary** (`layers[]` — `name`, `description`, `nodeIds`)
        and **complexity cluster** (file-level `nodes[]` `complexity`, `filePath`, intersected with
        `layers[].nodeIds`). Exactly two classes; no third.
  - [ ] State the one-signal rule: **a candidate names exactly one signal.** Where one layer
        supports both observations, that is two candidates or one — never one candidate citing
        two. Give the reason: a candidate citing both is checkable against neither.
  - [ ] Cite 362's mechanics by reference — file-level definition, `nodeIds | length` counting with
        type breakdown, ordinal `complexity` handling, layer cross-check drift rule. **Do not
        restate them.**
  - [ ] State what this flow does **not** read: no `tour[]`, no `entry-point` tags, no `meta.json`
        coverage read.
  - [ ] Success: two signal classes with source fields; one-signal rule with its reason; 362
        mechanics cited not restated; the not-read list present.

- [ ] **3.2 Author the no-padding rule** — Effort: 2/5
  - [ ] State it plainly: candidates the graph does not support are not proposed. **No target
        count, no minimum, no maximum.**
  - [ ] Give the reason the design records: a padded list is indistinguishable from a real one to a
        reader, and one invented candidate makes every other candidate suspect.
  - [ ] State that **emitting zero candidates is a success, not a failure** — the document is still
        written (on confirmation) and states that the graph supported no candidate, naming what was
        looked for.
  - [ ] Success: rule, reason, and zero-is-success statement all present and unhedged.

- [ ] **3.3 Verify the derivation model** — Effort: 1/5
  - [ ] Check against the design's "The candidate derivation model": signal table matches
        field-for-field; the one-signal rule is stated as a rule, not a preference; no 362
        mechanic has been restated in place of a citation.
  - [ ] Success: correspondence confirmed.
  - [ ] Commit: `docs: add candidate derivation model and no-padding rule`

## Task 4: The optional concept read

- [ ] **4.1 Author what is read** — Effort: 2/5
  - [ ] Name the path: `project-documents/user/project-guides/000-concept.{project}.md`.
  - [ ] **Two sections only** — User-Provided Concept (verbatim engagement answers, Q1 in
        particular) and Problem & Motivation (the engagement half).
  - [ ] State the exclusion and its reason: not Solution Approach, not Initial Technical Direction,
        not Development Approach — those are graph-derived in the concept itself, so reading them
        would launder graph content through a second document and present it as independent
        corroboration.
  - [ ] Success: path, the two sections, and the exclusion-with-reason all present.

- [ ] **4.2 Author what it changes and what it does not** — Effort: 2/5
  - [ ] Write the three-row effect table: **which candidates exist** — none, the concept never
        creates, suppresses, or supplies a candidate the graph does not support; **their order** —
        this is the whole effect; **their scope statements** — may frame work in terms of stated
        intent, provided every factual claim still traces to a graph signal.
  - [ ] State the boundary and why it matters: the concept cannot manufacture a candidate, and this
        is what keeps the no-padding rule enforceable. If engagement context could originate
        candidates, "we're here to modernize" would license proposing anything at all.
  - [ ] State that ordering influence is **declared per candidate**, not applied invisibly — an
        ordered-up candidate says so and names the concept as the reason.
  - [ ] Success: effect table with all three rows; the manufacture boundary with its reason; the
        per-candidate declaration rule.

- [ ] **4.3 Author the degradation path** — Effort: 2/5
  - [ ] No concept, or a concept lacking both named sections: order by **signal strength alone** —
        descending count of `complex` file-level nodes for complexity clusters, descending
        `nodeIds | length` for layer boundaries.
  - [ ] The degradation is stated **in the document body and in provenance**, never silent. Include
        the body line from the design, naming what was missing and what a concept would have
        changed.
  - [ ] **Both-questions-declined is recorded distinctly from no-document.** A declined interview
        and a missing document are different facts; collapsing them would hide that the interview
        happened.
  - [ ] Success: degradation rule, the body line, and the declined-vs-absent distinction all
        present.

- [ ] **4.4 Verify the concept read** — Effort: 1/5
  - [ ] Check against the design's "The optional concept read": two sections read, three-row effect
        table, degradation with the distinct declined case.
  - [ ] Confirm no sentence anywhere in the new flow makes the concept a precondition or a
        dependency.
  - [ ] Success: correspondence confirmed; no precondition language.
  - [ ] Commit: `docs: add optional concept read and degradation path`

## Task 5: Candidate record shape and dependency derivation

- [ ] **5.1 Author the five-part record** — Effort: 3/5
  - [ ] Write the record table in order: **title** (authored — names the work, not the observation;
        include the design's contrasting example), **derivation signal** (one, named, with its
        field), **supporting node IDs** (actual ids; every id must resolve to a node carrying a
        `filePath`; an unresolvable id is drift per 362, and a candidate whose supporting ids are
        all drift is not emitted), **scope statement** (one paragraph; every factual claim traces
        to the signal or a cited node; no effort estimates, timelines, or business value
        judgments), **observed dependencies** (derived, never asserted; an empty result is written
        as "none observed", not omitted).
  - [ ] State the citation rule: **node IDs are cited, not summarized.** A candidate supported by
        fourteen nodes lists them. Give the reason — the document is a working artifact for someone
        deciding whether to adopt, and "several files in Pipeline Orchestration" is not checkable.
  - [ ] State the authored/extracted asymmetry: title and scope are the only authored parts, both
        constrained by the three extracted parts. Prose checkable against cited ids is safe; prose
        standing alone is not.
  - [ ] Success: five parts in order with their rules; citation rule with reason; asymmetry stated.

- [ ] **5.2 Author dependency derivation** — Effort: 3/5
  - [ ] Cite 362's endpoint mechanics by reference: string parse of the edge's own `source`/`target`
        id (second colon-delimited field is the owning file's path, which resolves to a layer),
        `imports` and `depends_on` types, self-references excluded, **no node read to resolve an
        endpoint** and specifically no `function` or `class` node.
  - [ ] Write the three-step derivation: collect each candidate's implicated layer set; for each
        ordered pair count inter-layer edges; a non-zero count is a stated dependency **carrying
        the count**.
  - [ ] State the non-sequencing rule prominently: a stated dependency is a **directional edge
        count, not a claim about ordering**. The document says "Candidate 3's layers hold 27
        imports into Candidate 1's layers"; it does not say Candidate 1 must be done first. That
        inference belongs to the human adopting the candidates.
  - [ ] State the two edge cases: unresolvable endpoints excluded and reported as drift per 362;
        two candidates implicating the same layer have that overlap **stated**, not expressed as a
        dependency — a layer does not depend on itself.
  - [ ] Success: mechanics cited not restated; three-step derivation; non-sequencing rule; both
        edge cases.

- [ ] **5.3 Verify record and dependency sections** — Effort: 1/5
  - [ ] Check against the design's "Candidate record shape" and "Dependency derivation": five parts
        in the design's order; the non-sequencing rule present and unhedged.
  - [ ] Confirm no dependency language implies sequencing anywhere in the new flow text.
  - [ ] Success: correspondence confirmed.
  - [ ] Commit: `docs: add candidate record shape and dependency derivation`

## Task 6: The write confirmation

- [ ] **6.1 Author the confirmation** — Effort: 2/5
  - [ ] One interaction, **after derivation and before any file write.** Show: the candidate
        **count**; each candidate's **title and derivation signal**, one line apiece; the
        **ordering basis** — engagement-informed (naming the concept) or signal-strength-only
        (naming the concept's absence).
  - [ ] State what is being confirmed: **that the document is worth writing at all** — not the
        correctness of individual candidates, not their adoption. Give the reason this makes the
        interaction cheap: the operator answers "is this set worth a file?", answerable from titles
        and signals, not "is candidate 4 correct?", which is not.
  - [ ] Write the three-outcome table: confirmed → written, provenance `confirmed`; declined →
        **nothing written**, set shown in console and discarded; no answer → **nothing written**.
  - [ ] Success: the three shown items; the scope-of-confirmation statement with its reason; the
        outcome table.

- [ ] **6.2 Author the default-to-not-writing rule and its contrast** — Effort: 2/5
  - [ ] State plainly: **this flow's confirmation defaults to not writing.**
  - [ ] State the contrast with 363 and the reason, from the design: 363's confirmation never
        stalls and proceeds on no answer because it writes a Phase 0 entry point a repo has no
        other way to obtain; this writes an advisory list that costs nothing to regenerate. 363's
        failure mode is a lost interview; this flow's is an unwanted file in `analysis/`.
  - [ ] State the zero-candidate case: a run deriving nothing **still asks** — showing "0
        candidates, derived from N layers and M complex file-level nodes" — and on confirm writes
        the document recording the negative result. Give the reason: the negative result is a real
        finding, and suppressing the question would make an empty result indistinguishable from a
        failed run.
  - [ ] Success: default stated; contrast with 363 including both failure modes; zero-candidate
        case with its reason.

- [ ] **6.3 Verify the confirmation section** — Effort: 1/5
  - [ ] Check against the design's "The write confirmation": outcome table matches row-for-row;
        the default-to-not-writing rule is explicit, not implied by the table alone.
  - [ ] Confirm the zero-candidate path asks and writes rather than exiting silently.
  - [ ] Success: correspondence confirmed.
  - [ ] Commit: `docs: add candidates write confirmation`

## Task 7: Output conventions, gap markers, read discipline

- [ ] **7.1 Author output conventions** — Effort: 2/5
  - [ ] Path: `project-documents/user/analysis/{index}-analysis.initiative-candidates.md`.
  - [ ] Index selection: cite the shared Generated document conventions rule — lowest unused index
        ≥ 940, **new index per run**, never overwriting. Do not restate the rule's mechanics.
  - [ ] Frontmatter block: `docType: analysis`, `project`, `topic: initiative-candidates`,
        `dateCreated`, `dateUpdated`, `status: not_started`, `model`.
  - [ ] State that `{project}` resolves from the cf project registration, never `project.name` from
        the graph, and that `model:` follows the shared rule unchanged — the real generating model
        id or an explicit stop, never a placeholder.
  - [ ] Success: path, cited index rule, frontmatter block, both resolution rules.

- [ ] **7.2 Author the provenance block** — Effort: 2/5
  - [ ] Flow-specific content: **generated by** (flow + model id); **generated on**; **source**
        (graph identity — `gitCommitHash`, `lastAnalyzedAt`; the concept path when read, or an
        explicit statement that none was found); **ordering basis** (`engagement-informed` or
        `signal-strength-only`, citing the concept's absence or both-declined); **candidate count**
        and the signal counts it derived from; **drift** per 362; **flagged gaps**, **staleness**,
        **review state** as in the shared block.
  - [ ] Author the **non-modification statement in the document body** — not only in provenance:
        the document states it is advisory, that adoption is manual, and that
        `001-initiative-plan.{project}.md` was not read for writing and not modified.
  - [ ] Success: every provenance line present; the body-level non-modification statement authored.

- [ ] **7.3 Author gap markers, `[INFERRED]` exclusion, and read discipline** — Effort: 2/5
  - [ ] Gap markers use the shared 361 syntax. This flow's genuine absences: no concept document, a
        concept with no usable engagement content, zero candidates derived. Each gets a marker
        naming the input that would have supplied it.
  - [ ] State that **`[INFERRED]` is not used in this flow**, with the structural reason: a claim
        not traceable to a cited signal or node id has no place in the document at all — the record
        shape's whole design is that authored parts are checkable against extracted parts. A
        sentence needing `[INFERRED]` is a sentence to delete.
  - [ ] State this explicitly in the skill text so the absence reads as a decision, not an
        oversight. Update the shared Gap markers section's pointer if it enumerates per-flow
        `[INFERRED]` governance.
  - [ ] Read discipline: cite 362's unchanged. Name the fields this flow reads — `layers[]`,
        file-level `nodes[]` (`complexity`, `filePath`), `edges[]` (`type`, `source`, `target`) —
        and nothing else. The concept read is a bounded read of two named sections.
  - [ ] Success: gap-marker cases; `[INFERRED]` exclusion with reason and explicit statement; read
        discipline citing 362 with the field list.

- [ ] **7.4 Verify conventions sections** — Effort: 1/5
  - [ ] Check against the design's "Output conventions", "Gap markers and `[INFERRED]`", and "Read
        discipline".
  - [ ] Confirm the flow reads no field outside the named list.
  - [ ] Success: correspondence confirmed.
  - [ ] Commit: `docs: add candidates output conventions and read discipline`

## Task 8: Verification walkthrough

The design's Verification Walkthrough, executed. **Tasks 8.2 and 8.3 involve the PM live** — see
the PM interaction notice above.

- [ ] **8.1 Flow selection** — Effort: 1/5
  - [ ] Exercise all five selector cases by direct skill invocation: `candidates` → the new flow;
        no argument → comprehension; `comprehension` → comprehension; `concept` → concept;
        nonsense → unrecognized, stops.
  - [ ] Success (SC1): the new row routes and the existing cases are unchanged in behavior.

- [ ] **8.2 Derivation with the confirmation declined** — Effort: 2/5
  - [ ] Frame for the PM first, then run `candidates` and **decline** at the confirmation.
  - [ ] Confirm: the derived set is shown in the console, **no file is written**, `git status` is
        clean.
  - [ ] Check the shown set against the graph using the two design queries (layer sizes; complex
        file-level nodes per layer). Every complexity-cluster candidate corresponds to a layer in
        that output, and its cited ids are a subset of that layer's complex nodes.
  - [ ] Success (SC2, SC3, SC5-decline): nothing written; every candidate traceable.

- [ ] **8.3 Full run with confirmation** — Effort: 2/5
  - [ ] Frame for the PM, re-run, and **confirm**.
  - [ ] `cf validate frontmatter` on the written document.
  - [ ] Check by hand: five record parts in order per candidate; exactly one signal each;
        dependency lines carry counts and assert no ordering; the body states the non-modification
        guarantee.
  - [ ] **The document is kept and committed.** This step writes into the real tree (unlike 8.7 and
        8.8, which use scratch copies), taking index **945**. It is the slice's proof artifact —
        the thing a reader checks the walkthrough's claims against — so it is committed here, on
        its own, rather than riding along in a later commit.
  - [ ] Commit: `docs: add generated initiative candidates from walkthrough`
  - [ ] Success (SC2, SC4, SC6, SC8): validation passes, all four hand checks hold, and the written
        document is committed.

- [ ] **8.4 Node ID resolution** — Effort: 1/5
  - [ ] For each cited node id, confirm it resolves to a node carrying a `filePath` (design query).
  - [ ] An id producing no output, or a null `filePath`, is a defect against SC2 — report it rather
        than editing the document to hide it.
  - [ ] Success (SC2): every cited id resolves.

- [ ] **8.5 Dependency recount** — Effort: 2/5
  - [ ] Spot-check one stated dependency by recounting independently: inter-layer
        `imports`/`depends_on` between the two candidates' layer sets, endpoints resolved by the
        second colon-delimited field.
  - [ ] The recount must match the stated number exactly.
  - [ ] Success (SC4): counts match.

- [ ] **8.6 Initiative plan untouched** — Effort: 1/5
  - [ ] `shasum project-documents/user/project-guides/001-initiative-plan.squadron.md` before and
        after the run; `git status --short project-documents/user/project-guides/`.
  - [ ] Success (SC6): identical shasum, no modification.

- [ ] **8.7 Ordering — all three concept states** — Effort: 3/5
  - [ ] **Degraded (default on this repo):** squadron has no concept at the concept path, so this
        runs by default. Verify the body line and provenance name the absence and that ordering is
        by signal strength.
  - [ ] **Engagement-informed:** on a **scratch copy of the tree**, restore
        `user/archive/000-concept.squadron.md` to `project-guides/000-concept.squadron.md`. Its Q1
        answer records a maintenance-takeover and modernization engagement. Verify ordering shifts
        and each affected candidate names the concept as the reason.
  - [ ] **Both-declined:** on a scratch copy, a concept whose User-Provided Concept section records
        both questions declined. Verify signal-strength ordering and provenance distinguishing this
        from no-document.
  - [ ] **Never restore the archived concept into the real tree** — it is `docType: notes` /
        `status: deprecated` and was archived deliberately. Scratch copies only.
  - [ ] Success (SC7): all three states behave as designed and are distinguishable in provenance.

- [ ] **8.8 Zero-candidate path** — Effort: 2/5
  - [ ] Build a scratch fixture graph with one layer and no `complex` nodes.
  - [ ] Expect: a confirmation prompt stating 0 candidates; on confirm, a written document
        recording the negative result with a gap marker naming what was looked for.
  - [ ] Success (SC3, zero-candidate write): prompt appears and the document records the negative
        result rather than being skipped.

- [ ] **8.9 Read discipline and guards** — Effort: 1/5
  - [ ] Confirm no step of the run loaded the whole graph and no `function`/`class` node was read
        (SC9).
  - [ ] `.venv/bin/ruff format --check .` and `pytest tests/skills/` — regression guards; this
        slice adds no Python and no test (SC10).
  - [ ] Success (SC9, SC10): discipline held; both guards green.

## Task 9: Close-out

- [ ] **9.1 Reconcile the walkthrough into the design** — Effort: 2/5
  - [ ] Update the design's Verification Walkthrough from draft to the steps as actually executed,
        including any divergence found in Task 8.
  - [ ] Record the four Phase-6 decisions the design deferred: the layer-boundary candidacy
        threshold; the per-candidate ordering-influence phrasing; scope-statement length
        discipline; node-ID list rendering.
  - [ ] Success: the walkthrough reflects reality and the four deferred decisions are recorded with
        what was chosen.
  - [ ] Commit: `docs: reconcile 364 walkthrough and record deferred decisions`

- [ ] **9.2 Mark the slice complete** — Effort: 1/5
  - [ ] Set `status: complete` on the slice design and this task file.
  - [ ] Check slice-plan entry 4 in `360-slices.document-intelligence.md`.
  - [ ] State in the close-out that the slice is **mechanically verified, usefulness unjudged** —
        pending a repo with no hand-written initiative plan. Do not let a green walkthrough be
        recorded as evidence the candidates are good.
  - [ ] Success: statuses set, entry checked, the usefulness caveat recorded.
  - [ ] Commit: `docs: mark slice 364 complete`

- [ ] **9.3 DEVLOG and merge** — Effort: 1/5
  - [ ] Write the DEVLOG entry per the Session State Summary guidance.
  - [ ] `.venv/bin/ruff format --check .` before the final commit.
  - [ ] Commit: `docs: record slice 364 in DEVLOG`
  - [ ] Confirm the tree is clean before merging — 8.3, 9.1, and 9.2 each committed their own work,
        so nothing from the close-out should remain uncommitted at this point.
  - [ ] Merge `364-slice.initiative-candidates` into `main`. **Do not delete the branch** — project
        rules require explicit instruction.
  - [ ] Success: DEVLOG written, format clean, merged to `main`.
