---
docType: tasks
slice: concept-generation-with-interview
project: squadron
lldReference: project-documents/user/slices/363-slice.concept-generation-with-interview.md
parent: project-documents/user/architecture/360-slices.document-intelligence.md
dependencies: [361, 362]
projectState: Slices 361 and 362 merged to main. Phase 4 design complete and reviewed PASS (z-ai/glm-5.2, 01ed19e). Real v2.8.1 graph present at .understand-anything/, gitCommitHash 1bfbca1, unchanged since design time — same graph both 362 and 363 measured against.
dateCreated: 20260822
dateUpdated: 20260822
status: not_started
---

# Tasks: Concept Generation with Interview

## Context Summary

- Working on slice **363**, the interview-driven half of capability (a): produce
  `000-concept.{project}.md` for a codebase that has no concept document.
- This is initiative 360's only **interactive** flow. Correctness depends on question quality, and
  it is the first slice to consume 362's extraction mapping as a mapping — reading it to decide what
  **not** to ask — rather than as a section list.
- Delivers a new sibling flow section in `commands/analysis/understand.md`, added alongside the
  existing Flow: Comprehension Analysis: flow selection (`concept` argument), the extract-then-ask
  procedure with a per-section decision table, six fixed interview questions asked before any
  extracted content is shown, the User-Provided Concept cross-repo contract (verified at write time,
  terminal failure on mismatch), re-run semantics (the initiative's one non-idempotent output —
  never overwritten), `[INFERRED]` governance for this flow, and concept-specific frontmatter and
  provenance.
- **Everything here is markdown editing.** No Python. No change to `src/squadron/`, the installer,
  the frontmatter gate, or `guide.ai-project.000-concept.md` (read and depended upon, not edited).
- Design review: **PASS**, 6 findings, all pass-severity — no CONCERNS to address before
  implementation (`project-documents/user/reviews/363-review.slice.concept-generation-with-interview.md`).
- Three real-graph measurements drive specific task content: `project.name` is `squadron-ai` (the
  filename must use the squadron project name instead); `project.description` is stale upstream
  prose (Overview is confirm-or-correct, never accept); `.understandignore` leaves zero test/CI
  nodes (Development Approach is interview-primary, not weak-evidence-assisted).
- **Next planned slice:** 364 (initiative candidates), which also reuses 362's extraction mapping
  and extends this slice's flow-selection mechanism for a `candidates` argument.

### Verified anchors (traced 20260822 on `main` at `01ed19e`)

| Anchor | Fact |
|---|---|
| Skill file | `commands/analysis/understand.md` exists, 669 lines, contains Flow: Comprehension Analysis |
| Graph | `.understand-anything/knowledge-graph.json` + `meta.json` present; `gitCommitHash` `1bfbca1` — same graph the design measured |
| Concept guide | `project-documents/ai-project-guide/project-guides/guide.ai-project.000-concept.md` present, contains `## User-Provided Concept` heading |
| Existing concept | `project-documents/user/project-guides/000-concept.squadron.md` **absent** — directory holds only `001-initiative-plan.squadron.md` |
| Analysis indexes | `user/analysis/` holds 940–944; not directly relevant here (concept path is fixed, not indexed) |
| Design review | `project-documents/user/reviews/363-review.slice.concept-generation-with-interview.md`, verdict PASS, `reviewedSha: 01ed19e` |

---

## Task 0: Branch and premise verification

- [ ] **0.1 Create the slice branch** — Effort: 1/5
  - [ ] Confirm working tree is clean and current branch is `main` (integration branch is unset via
        `cf config get git.integration_branch`; target is `main`).
  - [ ] Commit the untracked design-review file if not already committed
        (`project-documents/user/reviews/363-review.slice.concept-generation-with-interview.md`).
  - [ ] `git checkout -b 363-slice.concept-generation-with-interview main`
  - [ ] Success: on the new branch, clean tree, review file tracked.

- [ ] **0.2 Re-measure the design's three graph facts** — Effort: 1/5
  - [ ] Run the checks from Verification Walkthrough step 1 (design lines 471–487): `project.name`,
        `project.description` + `lastAnalyzedAt`, `project.languages`/`.frameworks` non-empty counts,
        and zero-count checks for `tests/` and `.github/` nodes.
  - [ ] Confirm: `project.name` is `squadron-ai`; `languages` and `frameworks` are both non-empty;
        `tests/`-prefixed and `.github/`-prefixed node counts are both **0**.
  - [ ] **STOP condition:** if any of these disagree with the design's Verified graph facts table,
        stop and report to the Project Manager — the per-section decision table (design lines
        201–221) was built on these numbers and needs revisiting before implementation.
  - [ ] Success: all four checks match the design, or work is stopped with a report.

- [ ] **0.3 Verify the cross-repo contract holds today** — Effort: 1/5
  - [ ] `grep -c '^## User-Provided Concept'`
        `project-documents/ai-project-guide/project-guides/guide.ai-project.000-concept.md` returns
        exactly 1.
  - [ ] Confirm no `000-concept.squadron.md` exists yet in `user/project-guides/` (the happy-path
        walkthrough in Task 8 depends on this being a fresh write).
  - [ ] Success: guide section present and correctly titled; no pre-existing concept document.

---

## Task 1: Flow selection

- [ ] **1.1 Add the `concept` flow argument** — Effort: 2/5
  - [ ] In `commands/analysis/understand.md`, locate the sentence "Any argument other than the
        comprehension default is **unrecognized**" (in Flow: Comprehension Analysis) and narrow it
        per design section **Flow selection** (lines 161–175): no argument or `comprehension` →
        existing flow; `concept` → new flow (this task adds the routing, Task 2+ adds the flow
        body); anything else, including `candidates`, remains unrecognized.
  - [ ] State explicitly that flow selection is by argument only — the skill never infers which flow
        to run from repo state (e.g., absence of a concept document never auto-triggers the concept
        flow).
  - [ ] State that Preflight runs in full for both flows, unchanged, and that a concept run against a
        missing/malformed graph fails identically to a comprehension run.
  - [ ] Per the design's Implementation Notes, edit the existing sentence "The concept flow and the
        initiative-candidates flow are slices 363 and 364" (in Flow: Comprehension Analysis) so it
        no longer describes the concept flow as a future slice, since this task makes it exist.
  - [ ] Success: the unrecognized-argument sentence is updated in place; the forward-reference
        sentence no longer describes the concept flow as future work; no duplicate or conflicting
        statement about argument handling exists elsewhere in the file.

- [ ] **1.2 Test: flow selection routes correctly** — Effort: 2/5
  - [ ] By inspection (this is a markdown skill file, not executable code): confirm the updated text
        unambiguously routes all four cases — no argument, `comprehension`, `concept`, and any other
        string (e.g. `candidates`, `foo`) — to the correct outcome, matching Success Criterion 1.
  - [ ] This check is re-verified live in Task 8.1 (walkthrough step 3); no standalone execution
        here.
  - [ ] Success: the four-case routing is unambiguous on read-through.

---

## Task 2: Extract-then-ask procedure and per-section decision table

- [ ] **2.1 Add the extract-then-ask procedure** — Effort: 3/5
  - [ ] Per the design's Implementation Notes: place this and every subsequent new subsection (Tasks
        2–7) as one sibling flow section — "Flow: Concept Generation" — positioned after the
        existing Flow: Comprehension Analysis and before the human-documentation divider. Reference
        the existing Preflight and Document Conventions sections rather than duplicating their text;
        duplication is what makes the two flows drift apart.
  - [ ] Add a new subsection stating the four-step procedure from design section **The
        extract-then-ask procedure** (lines 177–199): attempt, judge sufficiency, confirm-or-ask,
        record.
  - [ ] Include the confirmation-vs-question distinction and the stated tie-break: "when a field is
        present but thin, ask."
  - [ ] State that a correction supersedes the extraction entirely — the original extracted value is
        not retained beside a PM's correction, and provenance records the section as
        extracted-and-corrected rather than extracted-and-confirmed.
  - [ ] Success: the four-step procedure and the tie-break rule are stated as skill text a Claude Code
        session executing this flow would follow.

- [ ] **2.2 Add the per-section decision table** — Effort: 3/5
  - [ ] Transcribe the seven-row table from design section **Per-section decision table** (lines
        201–221) into the skill file: section, extraction attempt, sufficiency test, interaction
        (Ask / Confirm-or-correct) — for Overview, User-Provided Concept, Problem & Motivation,
        Target Users, Solution Approach, Initial Technical Direction, Development Approach.
  - [ ] Preserve the two measured deviations from the architecture's default expectation: Overview is
        **never** sufficient-and-accept (always confirm-or-correct, given stale
        `project.description`); Development Approach is **Ask** (primary), not weak-evidence, because
        the real graph carries zero test/CI nodes — state that the extraction attempt is still coded
        for a differently-configured repo, but its absence is the expected case here.
  - [ ] For the Solution Approach row's "plus coverage boundary" clause: state what the boundary is
        and where it comes from — sourced from 362's coverage facts (`.understandignore` scope,
        `meta.json` `analyzedFiles`), naming which parts of the repo the graph did not see. Do not
        leave this as a bare phrase with no content for the flow to act on.
  - [ ] Success: seven-row table present in the skill file, matching the design table exactly; the
        two stated deviations are called out inline, not silently merged into the generic rule.

- [ ] **2.3 Test: verify the decision table against the live graph** — Effort: 2/5
  - [ ] For each of the four graph-backed rows (Overview, Solution Approach, Initial Technical
        Direction, Development Approach), run the `jq` selection the row implies against
        `.understand-anything/knowledge-graph.json` and confirm the sufficiency test's stated outcome
        holds: Overview → description present but flagged for confirmation; Solution Approach →
        `layers[]` non-empty (10 layers); Initial Technical Direction → both `languages` and
        `frameworks` non-empty; Development Approach → zero test/CI config nodes, confirming **Ask**.
  - [ ] Success: all four outcomes match the table's stated interaction column against the real
        graph.

---

## Task 3: Interview question wording and ordering

- [ ] **3.1 Add the six fixed interview questions** — Effort: 2/5
  - [ ] Transcribe the six questions verbatim from design section **Question wording and ordering**
        (lines 223–278) into the skill file, as fixed text — not paraphrased, not summarized.
  - [ ] State the ordering rule: intent questions (all six) are asked first, as one block, before any
        extracted content is shown — with the two stated reasons (anchoring; cheap abandonment on
        decline).
  - [ ] State that answers to questions 1–4 serve two purposes at once: verbatim User-Provided
        Concept content, and the source for the corresponding Refined Concept sections (Problem &
        Motivation from 1–2, Target Users from 3–4) — never asked twice.
  - [ ] State that question 5 supplies Development Approach and question 6 is the deliberate
        open catch-all, asked last.
  - [ ] Success: exactly six questions present, verbatim against the design; the ordering and
        dual-purpose rules are stated as skill text.

- [ ] **3.2 Test: question set matches the per-section table** — Effort: 1/5
  - [ ] Cross-check: every **Ask**-interaction row in the Task 2.2 decision table has at least one
        of the six questions mapped to it (Problem & Motivation ← Q1–2; Target Users ← Q3–4;
        Development Approach ← Q5; User-Provided Concept ← the verbatim capture of all answers), and
        no question maps to a **Confirm-or-correct** row.
  - [ ] Commit: flow selection, extract-then-ask procedure, decision table, and interview questions
        (Tasks 1–3) — `commands/analysis/understand.md` is buildable skill text at this checkpoint.
  - [ ] Success: the six-question set fully covers the Ask rows with no orphaned or misrouted
        question; commit made.

---

## Task 4: User-Provided Concept cross-repo contract

- [ ] **4.1 Add the verify-before-write check** — Effort: 3/5
  - [ ] Add the contract from design section **The User-Provided Concept contract** (lines 280–304):
        before any write, confirm the concept guide is readable and its document-structure block
        contains a section titled exactly `## User-Provided Concept`.
  - [ ] State both terminal failure modes distinctly: guide unreadable/absent → stop naming the path;
        section title absent or renamed → stop naming the guide, the expected title, and that the
        layout appears to have changed upstream. State explicitly that neither failure is a gap
        marker — a gap marker means "this document is missing something," this means "this document
        cannot be correctly written at all."
  - [ ] State the write rule: verbatim, no summarizing/rewording/reordering/grammar-correction — the
        one section where the skill is a transcriptionist, not an author.
  - [ ] State the preservation rule: pre-existing section content survives untouched; new answers are
        appended below under a dated subheading; never rewritten, reordered, or merged with existing
        material.
  - [ ] Success: the check, both failure messages, the write rule, and the preservation rule are all
        present as skill text, matching the design's distinctions.

- [ ] **4.2 Test: contract holds and fails correctly** — Effort: 3/5
  - [ ] Positive case: `grep -c '^## User-Provided Concept'` against the real guide returns 1 (already
        confirmed in Task 0.3; re-confirm here as the unit under test for this task's skill text).
  - [ ] Negative case, on a **scratch copy only**: copy
        `guide.ai-project.000-concept.md` to a scratch path (e.g. under the session scratchpad),
        rename the section heading in the copy, and — following the skill text added in 4.1 as a
        manual walkthrough — confirm the described check would stop with an error naming the guide
        path and the expected title. Confirm no file would be written to `user/project-guides/`.
        Delete the scratch copy.
  - [ ] **Never modify the real guide file** during this test.
  - [ ] Success: positive case passes; negative case's failure message and non-write behavior are
        confirmed against the skill text; scratch copy deleted.

---

## Task 5: Re-run semantics and existing-document handling

- [ ] **5.1 Add re-run semantics** — Effort: 2/5
  - [ ] Add the rules from design section **Re-run semantics** (lines 306–322): no existing document
        → write it; existing document → do not overwrite, report it, offer augment-or-stop, default
        to stop when the PM does not choose.
  - [ ] State the augment rule precisely: appends to User-Provided Concept per the Task 4
        preservation rule; fills only Refined Concept sections that are **empty or hold a gap
        marker**; a section with real content is left alone.
  - [ ] State the mechanical test for "empty or hold a gap marker": a section whose body is exactly
        a `[GAP: ...]` marker is machine-written and refillable; anything else is not.
  - [ ] State explicitly: a human-authored concept is never rewritten from a graph, because the
        concept is the input to every later phase and regenerating one over a PM's work would
        destroy the most expensive artifact in the tree.
  - [ ] Success: re-run rules, the augment scope, and the mechanical refillability test are present
        as skill text.

- [ ] **5.2 Test: re-run behavior on a scratch fixture** — Effort: 2/5
  - [ ] Using a scratch copy of the tree (or a scratch concept file outside `user/project-guides/`,
        clearly named to avoid confusion with a real output), construct a minimal concept document
        with one populated Refined Concept section and one section holding only a `[GAP: ...]`
        marker.
  - [ ] Walk through the skill text against this fixture: confirm the populated section would be left
        untouched and the gap-marker section would be identified as refillable.
  - [ ] Commit: User-Provided Concept cross-repo contract and re-run semantics (Tasks 4–5).
  - [ ] Success: the fixture demonstrates the mechanical distinction correctly; no changes made to
        any file under `user/project-guides/` during this test; commit made.

---

## Task 6: `[INFERRED]` governance and declines

- [ ] **6.1 Add `[INFERRED]` governance for the concept flow** — Effort: 2/5
  - [ ] In the existing Gap markers section (shared Document Conventions), update the pointer
        sentence that currently defers `[INFERRED]` governance to slice 363 — replace it with the
        rule from design section **`[INFERRED]` governance for the concept flow** (lines 324–354).
  - [ ] State the checkable rule verbatim: marker when a sentence is derived from a named field but
        asserts something the field does not literally state; no marker when it restates the field;
        the sentence does not belong in the document when no field is behind it.
  - [ ] Include the three worked examples from the design (layers restated with no marker; tour-order
        importance claim marked; unsupported intent claim omitted entirely) as skill guidance.
  - [ ] State that a PM-confirmed inference stays marked — the marker describes provenance, not
        confidence — and that confirmation changes the provenance entry, not the body.
  - [ ] Success: the shared Gap markers section's forward-pointer is resolved with the concept flow's
        actual rule; the three examples are present.

- [ ] **6.2 Add the decline path** — Effort: 2/5
  - [ ] Add the rules from design section **Declines** (lines 356–368): an unanswered question
        produces a gap marker in the body (using the existing `[GAP: ...]` syntax, naming the
        interview as the input) and an entry in the provenance block's declined-questions line.
  - [ ] State that a decline is never filled with a plausible guess and never silently omitted, and
        that a fully-declined run still yields a valid document — structure from the graph, unknowns
        elsewhere, with provenance stating exactly that.
  - [ ] Success: decline handling is present as skill text and distinguishes body placement from
        provenance placement, matching the existing gap-marker two-placement rule from 361.

- [ ] **6.3 Test: `[INFERRED]` rule is mechanically checkable** — Effort: 1/5
  - [ ] Using the three worked examples in the skill text (6.1), confirm each maps to its stated
        outcome (no marker / marker / omitted) by applying the rule verbatim — this is a read-through
        check of the skill text's own examples, not a live document.
  - [ ] Success: all three examples resolve correctly under the rule as written.

---

## Task 7: Output conventions — path, frontmatter, provenance

- [ ] **7.1 Add output path and the project-name distinction** — Effort: 2/5
  - [ ] Add the path rule from design section **Output conventions** (lines 370–410):
        `project-documents/user/project-guides/000-concept.{project}.md`, where `{project}` is
        resolved as the squadron project name — **never** `project.name` from the graph.
  - [ ] State the reconciliation rule: where the graph's `project.name` differs from the squadron
        project name, the difference is stated in the Overview section of the generated document and
        the graph's value appears in provenance.
  - [ ] Success: the filename rule and the divergence-handling rule are both present and
        unambiguous.

- [ ] **7.2 Add concept frontmatter** — Effort: 2/5
  - [ ] Add the frontmatter block from the design (lines 385–401), sourced from the concept guide's
        own schema: `docType: concept`, `layer: project`, `phase: 0`, `phaseName: concept`,
        `project`, `audience: [human, ai]`, `description`, `dependsOn: []`, `dateCreated`,
        `dateUpdated`, `status: not_started`, `model:`.
  - [ ] Carry forward the 361 `model:` rule unchanged: the real generating model id or an explicit
        stop, never a placeholder.
  - [ ] Success: frontmatter block present in the skill file, matching the concept guide's schema
        with squadron's generated-document additions (`status`, `model`).

- [ ] **7.3 Add concept-specific provenance shape** — Effort: 2/5
  - [ ] Extend the shared provenance block (361's shape) with the three concept-specific
        additions from the design: **Generated by** names the concept flow; **Section sourcing**
        distinguishes four outcomes per section (extracted-and-confirmed, extracted-and-corrected,
        interview, declined) instead of two; two new lines, **Declined questions** and **Inferred
        claims**.
  - [ ] State that **Source** additionally names the concept guide path and states that the
        User-Provided Concept section was verified present.
  - [ ] Success: the concept flow's provenance shape is fully specified as skill text, distinct from
        but clearly derived from the shared 361 block.

- [ ] **7.4 Test: frontmatter passes the gate** — Effort: 2/5
  - [ ] Hand-construct a minimal scratch document (outside `user/project-guides/`) using the exact
        frontmatter block from 7.2 with placeholder-but-valid values (e.g. a real model id, a real
        date), and run `cf validate frontmatter` against it.
  - [ ] Confirm it passes cleanly, matching Success Criterion 8. Delete the scratch document
        afterward.
  - [ ] By inspection: confirm 7.1's filename/divergence rule and 7.3's four-outcome provenance
        enumeration are present in the skill text and match the design, closing the loop on those
        two additions before the live walkthrough exercises them in Task 8.
  - [ ] Commit: output conventions — path, frontmatter, provenance (Task 7). All skill-text edits
        for the concept flow (Tasks 1–7) are now complete in `commands/analysis/understand.md`.
  - [ ] Success: gate passes on the constructed frontmatter; scratch file removed; commit made.

---

## Task 8: Verification walkthrough

- [ ] **8.1 Flow-selection routing, live** — Effort: 1/5
  - [ ] Execute Verification Walkthrough step 3 (design line 491): in a Claude Code session with the
        updated skill file, confirm all four cases route correctly — no argument and `comprehension`
        run the comprehension flow; `concept` runs this flow; `candidates` is unrecognized and stops.
  - [ ] This is the live confirmation Task 1.2 deferred to here; 1.2 was read-through inspection only.
  - [ ] Success: all four cases confirmed live, closing out Success Criterion 1 alongside Task 1.2.

- [ ] **8.2 Happy path — full interview** — Effort: 4/5
  - [ ] Execute Verification Walkthrough step 4 (design lines 501–517): open
        `commands/analysis/understand.md` in a Claude Code session, instruct it to run the concept
        flow against this repo with argument `concept`, and answer all six questions.
  - [ ] Confirm every point in the design's step 4 checklist: filename uses `squadron` (not
        `squadron-ai`) with the difference stated in Overview; six questions asked before any
        extracted content shown; User-Provided Concept holds answers verbatim (diff against what was
        given); Solution Approach names layers and tour-derived ordering and states its coverage
        boundary; Initial Technical Direction lists the measured languages/frameworks; Development
        Approach sourced from interview with no gap marker misclaiming a missing field; provenance
        distinguishes all four sourcing outcomes and carries both new lines, including the graph's
        `project.name` value on the Source line per Task 7.1; `grep -c 'INFERRED'` returns non-zero
        with every marked sentence satisfying the rule; `cf validate frontmatter` passes on the
        written file.
  - [ ] Success: `000-concept.squadron.md` written; every checklist point confirmed, including the
        judgment call that the result is a concept a PM would edit rather than discard (Success
        Criterion 14 — final acceptance still rests with PM review in Task 9.3); file committed at
        the next checkpoint (Task 8.6).

- [ ] **8.3 Decline path** — Effort: 3/5
  - [ ] Execute Verification Walkthrough step 5 (design lines 519–522) in a scratch copy of the tree:
        run the flow again, decline every question.
  - [ ] Confirm: document still written; Problem & Motivation, Target Users, and Development Approach
        each carry a gap marker naming the interview; provenance lists all six questions as declined;
        no section holds unsourced prose.
  - [ ] Success: decline path produces a valid document per design; no file under the real
        `user/project-guides/` is affected by this scratch run.

- [ ] **8.4 Correction path** — Effort: 2/5
  - [ ] Execute Verification Walkthrough step 6 (design lines 524–527) in a **fresh scratch copy of
        the tree containing no existing concept document** (do not reuse 8.2's real
        `000-concept.squadron.md` — per Task 5.1's re-run semantics, a run against an existing
        document would report it and stop rather than reach the Overview confirm-or-correct
        interaction this task must exercise): run the flow and correct the extracted Overview
        description.
  - [ ] Confirm: the correction lands in the body (not the original upstream description); provenance
        records the section as extracted-and-corrected, not extracted-and-confirmed.
  - [ ] Success: correction semantics confirmed live, matching design section **The extract-then-ask
        procedure**.

- [ ] **8.5 Re-run against an existing document** — Effort: 3/5
  - [ ] Execute Verification Walkthrough step 7 (design lines 529–532), using the real
        `000-concept.squadron.md` written in 8.2: run the flow again.
  - [ ] Confirm: flow does not overwrite; reports the existing document; defaults to stop; when told
        to augment, appends to User-Provided Concept under a dated subheading while leaving
        already-populated Refined Concept sections byte-identical — verify with `git diff`.
  - [ ] Success: non-destructive re-run confirmed with `git diff` evidence.

- [ ] **8.6 Read discipline, scope, and checkpoint commit** — Effort: 2/5
  - [ ] Execute Verification Walkthrough steps 8–9 (design lines 534–547): confirm no command read
        the graph without a `jq` field selection and no `function`/`class` node was read during any
        of the above runs; confirm `git status` on `.understand-anything/` shows no modification
        (including `fingerprints.json`).
  - [ ] Confirm `git diff --name-only` against the branch point lists only
        `commands/analysis/understand.md`, the generated concept document, this slice's own task and
        design documents, and the DEVLOG — nothing under `src/squadron/` or
        `project-documents/ai-project-guide/`.
  - [ ] Commit the walkthrough's real-tree artifact (`000-concept.squadron.md` from 8.2) and any
        skill-file fixes surfaced during the walkthrough.
  - [ ] Success: both checks pass, matching Success Criteria 13 and 15; commit made, tree clean apart
        from remaining close-out work.

---

## Task 9: Close the slice

- [ ] **9.1 Update task and slice status** — Effort: 1/5
  - [ ] All checkboxes above verified against walkthrough evidence; any dropped/skipped items marked
        `[x]` with a note per project convention.
  - [ ] Set this file's `status: complete`, refresh `dateUpdated`; set the slice design's `status`
        per its frontmatter contract. If this completes all of initiative 360's slice-plan items
        through 363, update the slice plan entry's checkbox
        (`project-documents/user/architecture/360-slices.document-intelligence.md`, item 3) to `[x]`
        — do not mark items 4–6 (364–366), which are unstarted.
  - [ ] Success: statuses consistent across task file, slice design, and slice plan.

- [ ] **9.2 DEVLOG entry** — Effort: 1/5
  - [ ] Write the slice-completion DEVLOG entry per `prompt.ai-project.system.md` → Session State
        Summary: flow shipped, walkthrough outcomes (happy/decline/correction/re-run paths), the
        `000-concept.squadron.md` artifact produced, any deviations from the design.
  - [ ] Success: entry present, dated, concise.

- [ ] **9.3 Final commit and hand-off** — Effort: 1/5
  - [ ] `uv run ruff format .` before committing (project rule), commit the close-out changes from
        Task 9 (status updates, DEVLOG) — this is a checkpoint on top of the commits already made at
        Tasks 3.2, 5.2, and 8.6, not a single end-of-slice commit. Confirm clean tree.
  - [ ] Report to the Project Manager for review and merge authorization. **Do not merge** — merging
        the slice branch is PM-gated.
  - [ ] Success: branch complete and clean; PM notified; no merge performed.
