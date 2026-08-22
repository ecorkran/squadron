---
docType: tasks
slice: concept-generation
project: squadron
lldReference: project-documents/user/slices/363-slice.concept-generation.md
parent: project-documents/user/architecture/360-slices.document-intelligence.md
dependencies: [361, 362]
projectState: Slices 361 and 362 merged to main. 363 redesigned after PM rejection of the interview-heavy predecessor (reset to Phase 4, redesign committed 998ab97, reviewed PASS with notes addressed in dfce803). Real v2.8.1 graph present at .understand-anything/, gitCommitHash 1bfbca1, unchanged since design.
dateCreated: 20260822
dateUpdated: 20260822
status: not_started
---

# Tasks: Concept Generation

## Context Summary

- Working on slice **363**, the third slice in initiative 360: produce
  `000-concept.{project}.md` for an existing codebase with no cf/sq planning artifacts —
  squadron's brownfield Phase 0 entry point.
- Governing rule from the design: **an existing codebase answers questions about its own nature
  through its artifacts, or not at all.** Three machine-readable sources (graph, root README,
  filesystem signals) are extracted before any human contact. The human is asked exactly two
  fixed engagement-context questions plus one confirm-or-correct on the derived description.
- This design replaces a rejected predecessor whose six product-discovery questions the PM
  rejected outright. **An improvised, added, or reworded question is a defect against Success
  Criterion 2, not a judgment call.** Dropped topics (why-now, audience evolution, methodology
  preference) appear nowhere — neither asked nor gap-marked.
- **Everything here is markdown editing.** No Python. The only changed non-document file is
  `commands/analysis/understand.md` (a sibling "Flow: Concept Generation" section), plus one
  cross-reference sentence fix in the comprehension flow's text.
- Design review: PASS, 4 notes, all addressed in the design (`dfce803`).
- **Next planned slice:** 364 (initiative candidates), which extends flow selection and consumes
  Q1's engagement answer via the written concept.

### Verified anchors (traced 20260822 on `main` at `dfce803`)

| Anchor | Fact |
|---|---|
| Skill file | `commands/analysis/understand.md` exists, 669 lines |
| Graph | `.understand-anything/knowledge-graph.json` + `meta.json` present; `gitCommitHash` `1bfbca1` — same graph the design measured |
| Graph `project.name` | `squadron-ai` — diverges from cf project name `squadron` (the divergence the output conventions handle) |
| Filesystem signals | `tests/`, `.github/workflows/ci.yml`, `[tool.ruff]` + `[tool.pytest.ini_options]` in `pyproject.toml` — all present; graph carries 0 nodes under `tests/`/`.github/` |
| Root `README.md` | present; lead states what squadron is, what problem it addresses, how it is reached |
| Concept guide | `guide.ai-project.000-concept.md` contains `## User-Provided Concept` exactly once |
| Existing concept | `user/project-guides/` holds only `001-initiative-plan.squadron.md` — no `000-concept.*` |

### PM interaction notice

Walkthrough Task 8.1 requires the PM live: two engagement answers and one description
confirmation. Before running it, tell the PM what is about to happen and why (which walkthrough
step, what will be asked). Never fire the questions without framing. AskUserQuestion is not used;
ask in plain text.

---

## Task 0: Branch and premise verification

- [ ] **0.1 Create the slice branch** — Effort: 1/5
  - [ ] Confirm working tree is clean and current branch is `main` (integration branch is unset;
        target is `main`).
  - [ ] `git checkout -b 363-slice.concept-generation main`
  - [ ] Success: on the new branch, clean tree.

- [ ] **0.2 Re-verify the design's premises** — Effort: 1/5
  - [ ] Run the checks from Verification Walkthrough step 1 (design lines 384–392):
        `project.name` is `squadron-ai`; `languages`/`frameworks` both non-empty;
        `tests/`, `.github/workflows/`, `README.md` all present; concept guide contains
        `^## User-Provided Concept` exactly once; `user/project-guides/` holds no `000-concept.*`.
  - [ ] Additionally confirm `pyproject.toml` still carries `[tool.ruff]` and
        `[tool.pytest.ini_options]` (the lint/test signals the design measured).
  - [ ] **STOP condition:** if any check diverges from the Verified facts table (design lines
        110–121), stop and report to the Project Manager — the design's source model was measured
        against these facts.
  - [ ] Success: all checks match, or work is stopped.

## Task 1: Flow selection

- [ ] **1.1 Add the flow selector to the skill** — Effort: 2/5
  - [ ] In `commands/analysis/understand.md`, extend the argument handling: no argument or
        `comprehension` → Flow: Comprehension Analysis (unchanged); `concept` → the new flow;
        anything else → say it is unrecognized and stop. `candidates` remains unrecognized
        until 364.
  - [ ] State explicitly: selection is by explicit argument only — the skill never infers a flow
        from repo state; the absence of a concept document never auto-triggers this flow.
  - [ ] State that preflight runs in full for both flows, unchanged — including the shared
        contract's `.gitignore` hygiene write. The concept flow adds no hygiene behavior and
        skips none.
  - [ ] Add the empty sibling section shell "Flow: Concept Generation" after Flow: Comprehension
        Analysis, before the human-documentation divider (Implementation Notes, design line 443).
  - [ ] Success: selector covers all four argument cases; explicit-only rule and preflight
        statement present; section shell in the stated position.

- [ ] **1.2 Verify selector text** — Effort: 1/5
  - [ ] Check the selector against design lines 137–148: routing table matches case-for-case;
        no additional recognized argument introduced.
  - [ ] Success: exact case coverage confirmed. (Live selection behavior is exercised in
        Task 8.5.)
  - [ ] Commit: `feat: add concept flow selector to understand skill`

## Task 2: Preconditions and the /cf:onboard boundary

- [ ] **2.1 Author the preconditions** — Effort: 2/5
  - [ ] Precondition 1 — graph present: the 361 preflight, executed unchanged. Reference the
        shared contract; do not duplicate it.
  - [ ] Precondition 2 — ai-project-guide installed: the concept guide is read at write time from
        `project-documents/ai-project-guide/project-guides/guide.ai-project.000-concept.md`. If
        the guide tree is absent, **stop** and name the setup step (`cf init` / `/cf:onboard`) —
        a terminal precondition failure, not a gap.
  - [ ] Precondition 3 — resolvable project name from the cf project registration, never from the
        graph. If no registration resolves a name, **stop** naming the setup step — deriving a
        filename from the graph's `project.name` is prohibited, so there is no fallback; terminal,
        same family as precondition 2.
  - [ ] State the boundary: `/cf:onboard` owns project setup and the greenfield conversational
        concept path; this flow owns the artifact-derived brownfield path. They compose and do
        not overlap.
  - [ ] Success: three preconditions with their two terminal-stop behaviors; boundary statement
        present; no fallback language anywhere.

- [ ] **2.2 Verify preconditions against this repo** — Effort: 1/5
  - [ ] Confirm the guide tree path is readable, the cf registration resolves `squadron`
        (`cf get` Name field), and the graph's `project.name` is `squadron-ai` — the divergence
        the output conventions must state.
  - [ ] Success: all three confirmed on this repo.
  - [ ] Commit: `feat: add concept flow preconditions and onboard boundary`

## Task 3: The three-source extraction model

- [ ] **3.1 Author the graph source** — Effort: 2/5
  - [ ] Sources: `project.description`, `.languages`, `.frameworks`; `layers[]` names +
        descriptions; `tour[]` order; file-level nodes tagged `entry-point`; `config` nodes.
        Attribution: each claim names its field inline, as in the comprehension flow.
  - [ ] Read discipline: 362's, unchanged — field-scoped `jq` selections only, whole graph never
        loaded, no `function`/`class` node read. State that this flow reads strictly less of the
        graph than the comprehension flow.
  - [ ] Success: field list, inline attribution rule, and discipline statement present.

- [ ] **3.2 Author the repo-prose source** — Effort: 2/5
  - [ ] README resolution: the root-level README, case-insensitive, `README.md` preferred when
        several exist. Nothing below the root is read — docs/ mining is excluded.
  - [ ] Attribution: claims cite their file (`README.md`); quoted material is quoted, never
        paraphrased into squadron's own voice.
  - [ ] No-README fallback: affected sections fall back to graph fields where mapped, and to gap
        markers where not — the source model degrades explicitly, never silently.
  - [ ] Success: resolution rule, citation/quoting rule, and explicit fallback present.

- [ ] **3.3 Author the filesystem-signals source** — Effort: 2/5
  - [ ] The closed checklist, verbatim in substance from the design (lines 158–164): test tree
        (`tests/` or `test/` at root); CI (`.github/workflows/` non-empty, or `.gitlab-ci.yml`);
        lint/format/test configuration (tool tables in `pyproject.toml`,
        `.pre-commit-config.yaml`, `.eslintrc*`/`.prettierrc*`). A signal outside the checklist
        is not probed.
  - [ ] Reported as observations with paths. **Absence of a signal is an observation, not a
        gap** — state this with the design's example ("no test tree observed at the repo root").
  - [ ] Success: closed checklist matches the design item-for-item; observation-not-gap rule
        stated.

- [ ] **3.4 Verify the sources against this repo** — Effort: 1/5
  - [ ] Execute the graph selections as the skill states them (fields return non-empty on this
        graph); confirm the README lead answers what-is-this/what-problem/who-reaches-it; run the
        signals checklist and confirm it reports `tests/`, `.github/workflows/ci.yml`, and the
        ruff/pytest tables with paths.
  - [ ] Success: all three sources produce the design's Verified-facts values as written.
  - [ ] Commit: `feat: add three-source extraction model to concept flow`

## Task 4: Per-section mapping

- [ ] **4.1 Add the per-section mapping table** — Effort: 2/5
  - [ ] Reproduce the design's seven-row table (lines 175–183): section, sources in order, human
        role. Rows are binding; do not paraphrase source names. Order is the concept guide's own
        section order.
  - [ ] State the dropped-topics rule with it: why-now, audience-evolution, and
        methodology-preference appear nowhere — not asked, not marked absent. A gap marker is
        reserved for content a section *needs* whose source is missing.
  - [ ] State Solution Approach's coverage boundary: sourced from 362's coverage facts
        (`.understandignore` active patterns, `meta.json` `analyzedFiles` reconciled against the
        file-level node count), stating which parts of the repo the graph never saw.
  - [ ] Success: table matches the design row-for-row; dropped-topics rule and coverage-boundary
        sourcing adjacent to it.

- [ ] **4.2 Verify table fidelity** — Effort: 1/5
  - [ ] Diff-check each row against the design; confirm no source renamed, dropped, or added, and
        that Target Users' human role reads "none — never asked".
  - [ ] Success: row-for-row match confirmed.
  - [ ] Commit: `feat: add per-section source mapping to concept flow`

## Task 5: Engagement interview and the single confirmation

- [ ] **5.1 Author the engagement interview** — Effort: 2/5
  - [ ] Exactly two questions, fixed text copied verbatim from the design (lines 204–210), asked
        once, as one block, after extraction and before drafting.
  - [ ] Both skippable without argument or follow-up. A declined question produces a gap marker
        at the point of absence (naming the interview as the input) and an entry in the
        provenance declined-questions line — never a plausible guess, never a silent omission.
  - [ ] Answers land verbatim in User-Provided Concept; used twice, asked once — Q1 also feeds
        Problem & Motivation's engagement half, Q2 feeds Development Approach's constraints.
  - [ ] State in the skill: an improvised or added question is a defect against Success
        Criterion 2, not a judgment call.
  - [ ] Success: both questions verbatim; once-as-one-block timing, skip semantics, verbatim
        landing, dual use, and the defect rule all present.

- [ ] **5.2 Author the single confirmation** — Effort: 2/5
  - [ ] After drafting, before the file write: show the derived project description (assembled
        from `project.description` and the README lead) together with the graph's
        `lastAnalyzedAt`; ask confirm-or-correct.
  - [ ] Three outcomes with their provenance records: confirmed → extracted-and-confirmed;
        corrected → the correction lands in the body, the original is not retained beside it,
        extracted-and-corrected; refused/unavailable → draft proceeds with sources attributed,
        extracted-unconfirmed. The flow never stalls on a confirmation.
  - [ ] State: this is the only confirmation in the flow; graph-derived structure is attributed,
        not confirmed section-by-section.
  - [ ] Success: trigger point, all three outcomes, never-stalls rule, and only-confirmation
        statement present.

- [ ] **5.3 Verify interview fidelity** — Effort: 1/5
  - [ ] Diff the skill's question block against the design's — byte-identical wording.
        Confirm no third question, no follow-up prompt, and no confirmation besides 5.2's exists
        anywhere in the flow text.
  - [ ] Success: byte-identical questions; interaction inventory is exactly two questions plus
        one confirmation.
  - [ ] Commit: `feat: add engagement interview and single confirmation to concept flow`

## Task 6: User-Provided Concept contract and re-run semantics

- [ ] **6.1 Author the write-time contract** — Effort: 2/5
  - [ ] Check 1: `guide.ai-project.000-concept.md` readable at its expected path. Unreadable or
        absent → **stop**, naming the path; whole guide tree absent → name the setup step
        (`cf init` / `/cf:onboard`) instead of just the file.
  - [ ] Check 2: the guide's document-structure block contains a section titled exactly
        `## User-Provided Concept`. Absent or renamed → **stop**, naming the guide, the expected
        title, and that the layout appears changed upstream.
  - [ ] State: neither failure is a gap marker — these mean the document cannot be correctly
        written at all.
  - [ ] Write rules: verbatim (never summarized, reworded, or grammar-corrected); pre-existing
        section content survives untouched; new answers append below under a dated subheading.
  - [ ] Success: both checks with their distinct stop messages, the not-a-gap statement, and
        both write rules present.

- [ ] **6.2 Author re-run semantics** — Effort: 2/5
  - [ ] No existing document → write it. Existing document → never overwrite: report it, offer
        augment or stop, **stop is the default**.
  - [ ] Augment appends to User-Provided Concept per the preservation rule and fills only
        Refined Concept sections that are empty or hold exactly a `[GAP: ...]` marker — the
        mechanical refillability test. A section with real content is left alone.
  - [ ] State: a human-edited concept is never rewritten from a graph.
  - [ ] Success: default-stop rule, mechanical refillability test, and never-rewritten rule
        present.

- [ ] **6.3 Verify the contract checks run** — Effort: 1/5
  - [ ] Execute both checks against the real guide: path readable;
        `grep -c '^## User-Provided Concept'` returns 1.
  - [ ] Success: both pass on this repo. (The failure path is exercised in Task 8.3 against a
        scratch copy — never the real guide.)
  - [ ] Commit: `feat: add user-provided-concept contract and re-run semantics`

## Task 7: Governance, output conventions, provenance

- [ ] **7.1 Record `[INFERRED]` governance for this flow** — Effort: 1/5
  - [ ] The checkable rule, in substance from the design (lines 278–280): a sentence carries
        `[INFERRED]` when derived from a named graph field but asserting something the field does
        not literally state; a restating sentence carries no marker; a sentence with no source
        does not belong.
  - [ ] Prose interacts by citation, not inference: a claim the README states is cited and
        unmarked. A PM-confirmed inference stays marked; confirmation changes the provenance
        entry, not the body. `[INFERRED]` sentences are listed in provenance.
  - [ ] Update the shared Gap markers section's pointer to this flow's `[INFERRED]` governance to
        point at the actual subsection (Implementation Notes, design line 448).
  - [ ] Success: rule, citation-not-inference statement, confirmed-stays-marked rule, provenance
        listing, and updated pointer all present.

- [ ] **7.2 Author output conventions** — Effort: 2/5
  - [ ] Path: `project-documents/user/project-guides/000-concept.{project}.md`, `{project}` from
        the cf project registration — never the graph's `project.name`. Where the two differ, the
        difference is stated in the Overview and the graph's value recorded in provenance.
  - [ ] Frontmatter: the design's block (lines 297–312) — `docType: concept`, `status:
        not_started`, and `model:` per 361's rule unchanged (real generating model id or an
        explicit stop, never a placeholder).
  - [ ] Success: path rule with divergence handling; frontmatter block matches the design;
        `model:` rule referenced, not restated.

- [ ] **7.3 Author the provenance block** — Effort: 2/5
  - [ ] 361's shape with concept-specific content (design lines 317–328): Generated by; Source
        (graph with identity, README when read, signals checked, concept guide path with
        section-verified statement); Section sourcing with one outcome per section over the full
        outcome set (extracted-from-graph, extracted-from-prose with file cite, observed-signals,
        interview, extracted-and-confirmed, extracted-and-corrected, extracted-unconfirmed,
        declined, gap); Engagement questions (answered/declined per question); Inferred claims;
        Flagged gaps, staleness, review state as in 361.
  - [ ] Success: all block lines present; outcome set complete, none invented.

- [ ] **7.4 Fix the 362 cross-reference sentence** — Effort: 1/5
  - [ ] Edit the comprehension flow's sentence "The concept flow and the initiative-candidates
        flow are slices 363 and 364" to reflect that the concept flow now exists (364 remains
        future).
  - [ ] Success: sentence accurate; no other comprehension-flow text changed.
  - [ ] Commit: `feat: add inferred governance, output conventions, and provenance to concept flow`

## Task 8: Verification walkthrough

Run from the repo root on branch `363-slice.concept-generation`. Pre-366, the flow is exercised
by opening `commands/analysis/understand.md` in a Claude Code session and instructing it to run
the concept flow. **Before 8.1, give the PM the framing described in the PM interaction notice.**

- [ ] **8.1 Happy path (PM live)** — Effort: 3/5
  - [ ] Run the concept flow against squadron. PM answers both engagement questions; when shown
        the derived description, the PM corrects it (the graph's is measurably stale — this
        exercises the correction outcome).
  - [ ] Confirm in the written `000-concept.squadron.md`, per design step 3 (lines 397–411):
        filename uses `squadron` and the Overview states the `squadron-ai` divergence; both
        questions asked once, after extraction, before drafting, nothing else asked;
        User-Provided Concept holds the answers verbatim (diff against answers as given);
        Problem & Motivation and Target Users cite `README.md`; Development Approach reports the
        observed signals with paths plus Q2's constraints; Solution Approach names layers, tour
        ordering, and the coverage boundary; the corrected description is in the body with
        provenance extracted-and-corrected; provenance carries the engagement-questions and
        inferred-claims lines and the graph's `project.name`.
  - [ ] `cf validate frontmatter` passes on the file; `model:` is a real model id.
  - [ ] Success: every listed check passes on the written document.

- [ ] **8.2 Decline path (scratch copy of the tree)** — Effort: 2/5
  - [ ] On a scratch copy, decline both questions. Document still written; gap markers where
        Q1/Q2 content would land; provenance lists both as declined; no section holds prose
        without a source.
  - [ ] Success: all decline-path checks pass; the real tree is untouched.

- [ ] **8.3 Contract failure (scratch copy of the guide only)** — Effort: 1/5
  - [ ] Copy the concept guide to scratch, rename the section heading in the copy, point the
        check at it. Confirm the loud stop names the guide and the expected title, and that
        nothing is written. Never modify the real guide.
  - [ ] Success: loud stop with both names; no file written.

- [ ] **8.4 Re-run against the real document** — Effort: 2/5
  - [ ] Re-run the flow against the step-8.1 document: reports the existing document, defaults
        to stop. When told to augment: appends to User-Provided Concept under a dated subheading;
        populated sections stay byte-identical (`git diff`).
  - [ ] Success: default stop observed; augment behavior matches; byte-identity confirmed.

- [ ] **8.5 Flow selection live** — Effort: 1/5
  - [ ] No argument and `comprehension` route to the comprehension flow (unchanged behavior);
        `candidates` stops as unrecognized.
  - [ ] Success: all three routes behave as authored.

- [ ] **8.6 Discipline and scope checks** — Effort: 1/5
  - [ ] From the 8.1 session: no graph read without a `jq` field selection; no `function`/`class`
        node read. `git status` on `.understand-anything/` clean.
  - [ ] `git diff --name-only main` shows only `commands/analysis/understand.md`, the generated
        concept, this slice's documents, and the DEVLOG. `git diff --stat main -- src/` is empty.
  - [ ] `uv run ruff format --check .` passes; `uv run pytest tests/skills/` passes (pack install
        path undisturbed).
  - [ ] Success: all checks clean; changed-file set as stated.
  - [ ] Commit: `feat: add generated concept document and walkthrough fixes`
        (include any fixes found during 8.x; commit fixes with the evidence that found them)

## Task 9: Close the slice

- [ ] **9.1 Update task and slice status** — Effort: 1/5
  - [ ] All checkboxes above verified against walkthrough evidence; dropped/skipped items (if
        any) marked `[x]` with a note per project convention.
  - [ ] Set this file's `status: complete`, refresh `dateUpdated`; set the slice design's
        `status` per its frontmatter contract; check off slice-plan entry 3 in
        `360-slices.document-intelligence.md`.
  - [ ] Success: statuses consistent across task file, slice design, and slice plan.

- [ ] **9.2 DEVLOG entry** — Effort: 1/5
  - [ ] Write the slice-completion entry per `prompt.ai-project.system.md` → Session State
        Summary: what landed, walkthrough outcomes (including the correction and decline paths),
        any deviations.
  - [ ] Success: entry present, dated, concise.

- [ ] **9.3 Final commit and hand-off** — Effort: 1/5
  - [ ] `uv run ruff format .` before committing (project rule), commit remaining changes,
        confirm clean tree.
  - [ ] Report to the Project Manager for review and merge authorization. **Do not merge** —
        merging the slice branch is PM-gated.
  - [ ] Success: branch complete and clean; PM notified; no merge performed.
