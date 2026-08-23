---
docType: slice-plan
parent: 360-arch.document-intelligence.md
project: squadron
dateCreated: 20260818
dateUpdated: 20260822
status: not_started
---

# Slice Plan: Document Intelligence

## Parent Document
`360-arch.document-intelligence.md` — Architecture: Document Intelligence

## Planning Context

Architecture-level. The parent describes two capabilities that share a shape (document transforms)
and no machinery:

- **(a)** consumes the upstream `understand-anything` knowledge graph and writes squadron planning
  artifacts — concept draft, comprehension analysis, initiative candidates.
- **(b)** consumes squadron's own planning artifacts and writes a stakeholder-facing overview.

They are independent: (b) never reads a graph and has no external dependency, so it can be built and
shipped without (a) existing. Within (a), three outputs share one graph-reading contract — validation,
staleness policy, extraction, provenance — which is the only genuine foundation work in this
initiative.

Nothing here adds Python. Every slice is markdown-authored skill content plus, in one case, three
edits to an existing dispatcher file. `sq install-commands` already copies `commands/sq/*.md`
wholesale and `_install_prefix()` already copies all `*.md` from `commands/analysis/`, so no
installer, manifest, or CLI change is required by any slice.

Slice order is: graph contract (foundation) → the three (a) outputs in increasing dependence on
human input → (b), which is independent and may be built at any point. The two documented open
questions from the parent are absorbed: gap-marker syntax is settled in slice 361 because the first
generated artifact needs it, and the `analyze-codebase-prompt.md` reuse question is answered in 362
where its analysis template is the direct comparable.

---

## Foundation Work

1. [x] **(361) Graph Contract and Provenance** — Establish the shared machinery every capability-(a)
   skill depends on, delivered as a reusable skill fragment plus the smallest real consumer that
   proves it works. Covers: locating `.understand-anything/knowledge-graph.json`; validating the
   required top-level keys (`project`, `nodes`, `edges`, `layers`, `tour`) and erroring loudly on a
   missing or mistyped key rather than proceeding with partial data; the staleness comparison of
   `meta.json`'s `gitCommitHash` against `HEAD`, warning with commit distance but never blocking, and
   announcing an explicit skip when git is unavailable or the directory is not a repository; the
   idempotent `.gitignore` write for `.understand-anything/.trash-*/`, performed per-run by the skill
   itself, non-fatal on failure but never silent, and satisfied without duplication by an existing
   broader ignore; the provenance block format, placed above content, recording source identity,
   staleness state, section sourcing, and flagged gaps; and the gap-marker syntax used by every
   generated document. The proving consumer is the comprehension analysis output (structural
   findings only — no interview, no concept), which exercises the whole contract end to end.
   - **Value:** Architectural enablement — every other capability-(a) slice reads the graph through
     this contract, and the failure modes named in the architecture are implemented once rather than
     three times.
   - **Success Criteria:**
     - A graph missing any required top-level key produces a clear error naming the absent key; a
       graph present but empty in `nodes`/`edges`/`layers` is rejected the same way.
     - An absent graph produces a different, actionable message pointing at `/understand`.
     - Staleness drift is reported with commit distance and does not block; the run proceeds on PM
       choice.
     - With git unavailable or outside a repository, the staleness skip is stated in both console
       output and the provenance block.
     - `.gitignore` gains `.understand-anything/.trash-*/` exactly once across repeated runs; a
       pre-existing broader `.understand-anything/` ignore is accepted without a second entry; a
       read-only `.gitignore` yields a reported non-fatal failure and the run continues.
     - `{index}-analysis.codebase-comprehension.md` is written with `docType: analysis`,
       `status: not_started`, and a provenance block above the content.
     - Gap-marker syntax is documented and used for at least one genuinely absent field.
   - **Dependencies:** [340] (bundled `analysis` pack and its dispatcher exist).
   - **Interfaces:** Provides the graph-read contract, provenance block, and gap-marker syntax
     consumed by 362 and 363. Consumes the upstream plugin's output contract.
   - **Risk:** Medium — the contract is against an actively developed upstream whose output shape is
     observed, not guaranteed.
   - **Relative Effort:** 3/5

---

## Feature Slices

2. [x] **(362) Comprehension Analysis and Graph Extraction** — Deepen the structural output from a
   contract-proving stub into the real comprehension document, and settle the extraction strategy the
   architecture leaves open. Defines which graph fields map to which sections of the analysis, in what
   order, with what fallback when a field is absent: `layers[]` for architecture, file-level
   `complexity` for hotspots, `edges[]` for dependency observations, `tour[]` ordering as the signal
   for which components matter most. Applies the read discipline the architecture requires — grep for
   the needed section, never load the whole graph, read only file-level node types and skip
   function/class nodes. Resolves the parent's open question on `analyze-codebase-prompt.md` by
   deciding how much of its analysis template and `[INFERRED]` convention transfers to the
   graph-backed path; that document is retained regardless as the lighter non-graph alternative.
   - **Value:** Developer value — a usable structural read of an unfamiliar codebase, in squadron's
     own document conventions, without any human interview.
   - **Success Criteria:**
     - Each analysis section names the graph fields it derives from; a section whose fields are
       absent emits a gap marker rather than inferred prose.
     - Complexity hotspots, entry points, layer architecture, and dependency observations are all
       present and traceable to node or edge data.
     - The whole graph is never loaded into context; extraction is selective.
     - A decision is recorded on `analyze-codebase-prompt.md` reuse, and that document remains in
       place.
     - Running against squadron itself produces a document a reader can check against the real repo.
   - **Dependencies:** [361].
   - **Interfaces:** Consumes the 361 graph contract. Provides the extraction mapping reused by 363.
   - **Risk:** Low.
   - **Relative Effort:** 3/5

3. [x] **(363) Concept Generation** — Produce `000-concept.{project}.md` for an existing codebase
   that has no concept document. Non-interrogative by design: structure extracts from the graph,
   intent extracts from the repo's own prose (root README, cited by file), and development practice
   from filesystem signals (test tree, CI workflows, lint config) that the graph's ignore rules
   cannot hide. The interview is engagement-context only — two skippable questions (what the
   operator needs to do with the codebase; unwritten constraints) — with answers written verbatim
   into the **User-Provided Concept** section, which is verified present in the concept guide's
   layout before any write, with a loud stop naming the guide if the layout changed upstream. One
   confirm-or-correct on the derived project description before writing. Declined answers become
   explicit unknowns recorded in provenance, never plausible guesses; questions about the project's
   own nature (what problem it solves, who it is for, why now) are never asked.
   - **Value:** User value — the highest-leverage output of this initiative, turning an unplanned
     codebase into squadron's Phase 0 entry point.
   - **Success Criteria:**
     - No question is asked whose answer any repo artifact or graph field supplies; the only
       questions are the two engagement-context questions, and extracted content is shown for
       confirmation rather than re-asked from scratch.
     - A declined answer produces an explicit unknown in the document and an entry in provenance.
     - The **User-Provided Concept** section holds engagement answers verbatim, and pre-existing
       content there survives a re-run untouched.
     - A concept document whose User-Provided Concept section is absent causes a loud failure naming
       the governing guide, not a silent write elsewhere.
     - Output carries `docType: concept`, `status: not_started`, and a provenance block; every
       prose-derived intent claim cites its source file.
     - Running against squadron produces a concept a PM would edit rather than discard.
   - **Dependencies:** [361], [362] (reuses the extraction mapping for Solution Approach and Initial
     Technical Direction).
   - **Interfaces:** Consumes the 361 contract and 362 mapping. Depends on the ai-project-guide's
     concept document layout — a cross-repo dependency, verified at write time.
   - **Risk:** Low — extraction is inherited from 362; the prose-mining rule is bounded to the root
     README, and the two-question interview has no wording risk left to carry.
   - **Relative Effort:** 3/5

4. [ ] **(364) Initiative Candidates** — Propose initiative-shaped work items from the graph, written
   to their own `{index}-analysis.initiative-candidates.md` and never into
   `001-initiative-plan.{project}.md`. Each candidate is derived from one stated signal — a layer
   boundary from `layers[]`, or a complexity cluster from file-level `complexity` within a layer — and
   carries a title, the signal and supporting node IDs, a one-paragraph scope statement, and observed
   dependencies from `edges[]` between implicated layers. Candidates the graph does not support are
   not proposed; the skill emits fewer rather than padding to a count. Written only on explicit PM
   confirmation, and what the PM confirms is that the document is worth writing at all — adopting a
   candidate into the real plan stays a deliberate manual act.

   **Open at design time — does this flow read the concept?** This entry says no: dependencies are
   [361] and [362], and every candidate derives from `layers[]`, `complexity`, and `edges[]`. But
   363's design lists 364 as consuming Q1's engagement answer via the written concept. The two
   disagree, and the answer decides what 364 *is*. A graph carries structure, not priorities — layer
   boundaries and complexity clusters show where code is tangled, never where work is valuable.
   Engagement context is the only available input that would make candidates prioritized rather than
   merely structural, which argues for reading the concept when one exists and degrading to
   structure-only when it does not. **Settle this in Phase 4 and reconcile whichever document is
   wrong.**

   **Open at design time — where candidate quality gets judged.** The mechanical criteria below are
   all verifiable against squadron. Candidate *usefulness* is not: squadron already has an
   initiative plan written by hand, so a proposal here cannot be told apart from a restatement of
   work already scoped. Build and verify the mechanics against squadron; judge whether the
   suggestions are worth having on a repo nobody on this project has planned.
   - **Value:** Developer value — turns structural observations into reviewable proposals without
     letting a machine author a commitment document.
   - **Success Criteria:**
     - Every candidate names its derivation signal and the node IDs supporting it.
     - No candidate is emitted that the graph does not support; a thin graph yields few or none.
     - Output is a standalone `analysis` document; `001-initiative-plan.{project}.md` is never
       modified by the skill.
     - The document is written only after explicit confirmation.
     - Dependencies between candidates are derived from `edges[]`, not asserted.
   - **Dependencies:** [361], [362].
   - **Interfaces:** Consumes the 361 contract and 362 mapping.
   - **Risk:** Low — output is advisory and adoption is manual.
   - **Relative Effort:** 2/5

5. [ ] **(365) Overview Command** — Capability (b), independent of everything above: `/sq:overview`
   as a first-party command in `commands/sq/`, reading the initiative plan (required) and concept
   (optional) and writing `{index}-analysis.overview.md` for a non-engineering reader. Implements the
   nine-field schema — purpose, problem, audience, approach, benefits, scope, status, roadmap, risks —
   with each field resolving to either content derived from its named source or a gap marker naming
   the missing input, and no third outcome in which the skill supplies content itself. Applies the
   translation rules: strip slice/phase/initiative indices and docType frontmatter, render features as
   outcomes rather than mechanisms, describe not-started work as planned rather than implying
   completion. Degrades gracefully when no concept exists — the case a client repo hits whenever the
   overview is wanted before Phase 0 has run, which is why it is a first-class path rather than an
   edge case. One neutral document, not per-audience variants.

   **On testing degradation against squadron.** Squadron has no concept document for a reason no
   other repo will share: concept generation (363) postdates the project that built it. That makes
   squadron a convenient *fixture* for the missing-concept path — it exercises the mechanics — but
   **not evidence that the path is common**, and not a representative instance of it. On a client
   repo the absence means Phase 0 has not run yet and running it would resolve the absence; on
   squadron it is a bootstrap ordering fact. Verify the mechanics here; judge the degraded output's
   usefulness on a repo whose concept is genuinely pending.
   - **Value:** User value — the first artifact squadron produces that can be handed to a client,
     manager, or colleague.
   - **Success Criteria:**
     - Runs against squadron itself — used here as a fixture for the missing-concept path, not as a
       representative instance of it — and produces a complete overview with gap markers where
       concept-sourced content would have gone.
     - No slice index, phase number, initiative index, or frontmatter field appears in the body.
     - Not-started initiatives are described as planned; nothing implies more progress than the
       inputs support.
     - Every field traces to a named source or carries a gap marker; gap markers appear in the body
       and are listed in provenance.
     - `sq install-commands` picks up `commands/sq/overview.md` with no installer change.
     - Output carries `docType: analysis`, `status: not_started`, and a provenance block.
   - **Dependencies:** None within this initiative. [100] for the command surface.
   - **Interfaces:** Consumes `001-initiative-plan.{project}.md` and optionally
     `000-concept.{project}.md`. Reuses the provenance and gap-marker conventions from 361 if built
     after it; defines them itself if built first.
   - **Risk:** Low.
   - **Relative Effort:** 3/5

---

## Integration Work

6. [ ] **(366) Dispatcher Routing and Documentation** — Wire capability (a) into the advertised
   command surface and document both capabilities. Three edits to `commands/sq/analysis.md` — the
   valid-skills line, the usage block, and a new skill section — so `/sq:analysis understand` routes
   correctly, matching the shape the deprecated slice 344 established. Add the skill file to
   `commands/analysis/` so `sq skills install analysis` picks it up via existing copy-all-md
   behavior. Document both capabilities in the README and note the `understand-anything` marketplace
   plugin as a prerequisite for (a), including how to install it, since squadron does not and will
   not install it.
   - **Value:** User value — the capabilities become discoverable and installable through the paths
     users already know.
   - **Success Criteria:**
     - `/sq:analysis understand` routes to the skill and passes arguments through intact.
     - `sq skills install analysis` installs both `tech-debt-audit.md` and the new skill; the receipt
       lists both.
     - An unrecognized skill name still produces the dispatcher's usage message.
     - With the marketplace plugin absent, the skill reports how to install it rather than failing
       obscurely.
     - README documents `/sq:analysis understand` and `/sq:overview`, and states the plugin
       prerequisite.
     - Existing skills tests remain green.
   - **Dependencies:** [361], [365]. Fullest value after [362], [363], [364].
   - **Interfaces:** Consumes the 340 dispatcher and installer conventions.
   - **Risk:** Low.
   - **Relative Effort:** 1/5

---

## Implementation Order

361 → 362 → 363 → 364 → 366, with 365 insertable at any point.

The ordering is dependency-driven with one deliberate risk choice: 361 comes first because it owns
the upstream contract, which is the only place this initiative can be broken by someone else's
release. Proving it early against a real graph surfaces that risk before three skills depend on it.

362 precedes 363 and 364 because both reuse its extraction mapping, and because a structural document
with no human input is the cheapest way to verify extraction quality before adding interview
complexity on top.

365 has no dependency on the graph path at all. It is placed last in the numbering for coherence, not
sequence — it can be built first if a client-facing artifact is wanted sooner, and it is the natural
choice when the marketplace plugin is unavailable.

366 is last because it advertises capabilities that should exist before they are announced, though
its dispatcher edits could land earlier without harm.

---

## Future Work

Items out of scope for this plan but worth tracking.

1. [ ] **(1) Overview Emphasis Parameter** — Per-audience emphasis (client / management / colleague)
   for `/sq:overview`, if real use shows one neutral document is insufficient. Deliberately deferred:
   the three readerships differ in emphasis, not fact, and three variants means three artifacts to
   keep true. Dependencies: [365]. Effort: 2/5.
2. [ ] **(2) 900-Band Index Re-cut** — The 900 band carries ad-hoc reviews, analyses, maintenance
   tasks, and now generated documents in 100 slots, with 940-949 already overflowing by design. A
   widening or re-subdivision affects `file-naming-conventions.md` and therefore every project on the
   guide, so it belongs in 900-band maintenance rather than here. Dependencies: None. Effort: 2/5.
3. [ ] **(3) Graph-Backed Slice Proposals** — Extend candidate generation from initiative-level to
   slice-level for an adopted initiative. Only worth pursuing once candidate quality at the
   initiative level is proven in real use. Dependencies: [364]. Effort: 3/5.
4. [ ] **(4) Non-Graph Comprehension Path** — Promote `analyze-codebase-prompt.md` from experimental
   reference to a supported lower-token alternative when the marketplace plugin is unavailable or its
   cost is not justified. Dependencies: [362]. Effort: 2/5.

---

## Notes

**Key decisions inherited from the parent architecture:**
- Squadron consumes the marketplace plugin's output and never forks, vendors, wraps, or installs it.
- Generated documents are written `status: not_started`; review state lives in the provenance block,
  because the enum has no `needs_review` member and adding one would change every project on the
  guide.
- Capability (a) writes to two directories — the concept to `project-guides/`, everything else to
  `analysis/`.
- Generated documents take 900-band slots past 949 as needed.

**Absorbed open questions:** the parent's two documented open questions are assigned rather than left
floating — interview wording to 363, `analyze-codebase-prompt.md` reuse to 362. Gap-marker syntax,
raised during architecture review, is settled in 361 because the first generated artifact requires it.

**No Python is added by any slice.** If a slice design concludes otherwise, that is a signal the
scope has drifted from the parent architecture and should be raised before proceeding.
