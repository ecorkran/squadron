---
docType: tasks
slice: comprehension-analysis-and-graph-extraction
project: squadron
lldReference: project-documents/user/slices/362-slice.comprehension-analysis-and-graph-extraction.md
parent: project-documents/user/architecture/360-slices.document-intelligence.md
dependencies: [361]
projectState: Slice 361 merged to main. Phase 4 design complete, reviewed CONCERNS with all three findings addressed in the design. Real v2.8.1 graph present at .understand-anything/, gitCommitHash 1bfbca1, unchanged since design.
dateCreated: 20260819
dateUpdated: 20260819
status: complete
---

# Tasks: Comprehension Analysis and Graph Extraction

## Context Summary

- Working on slice **362**, the first slice in initiative 360 that *consumes* the 361 graph
  contract rather than defining it.
- Delivers the real comprehension document: a seven-section extraction mapping (project identity,
  layer architecture, entry points, complexity hotspots, reading order, dependency observations,
  coverage/scope limits), each section binding source fields, an ordering rule, and a fallback —
  sourced content or a gap marker, never a third option.
- Includes **three corrections to the shipped 361 contract**: layer counting (`nodeIds | length`,
  not intersect-with-`type=="file"`), the file-level selector (exclude `function`/`class` by name,
  not allow only `file`), and the misleading `fingerprints.json` churn note.
- **Everything here is markdown editing.** No Python. The only changed non-document files are
  `commands/analysis/understand.md` and one cross-reference line in
  `user/reference/analyze-codebase-prompt.md`.
- Design review: CONCERNS, 3 findings, all addressed in the design (endpoint resolution via the
  id-prefix contract; unresolvable-endpoint failure path; section count grounded vs architecture).
- **Next planned slice:** 363 (concept generation), which reuses this slice's extraction mapping.

### Verified anchors (traced 20260819 on `main` at `837ff73`)

| Anchor | Fact |
|---|---|
| Skill file | `commands/analysis/understand.md` exists, 388 lines |
| Graph | `.understand-anything/knowledge-graph.json` + `meta.json` present; `gitCommitHash` `1bfbca1` — same graph the design measured |
| Analysis indexes | `user/analysis/` holds 940–943; next unused index is **944** |
| `.gitignore` | Trash-only scope already in place (`.understand-anything/.trash-*/`, line 184) — correction 3 changes only the skill's note text, not `.gitignore` |
| Reference doc | `user/reference/analyze-codebase-prompt.md` present, unchanged |

### Deviation from the design document

The design's Implementation Notes step 1 says to re-run the comprehension flow immediately after
corrections 1 and 2, before layering new sections. This breakdown instead verifies those
corrections by executing the corrected skill text's own `jq` selections directly (Tasks 1.2, 2.2),
and runs the full flow **once**, at the walkthrough (Task 8.1). Rationale: the corrected
selections are deterministic and prove the same numbers (34, 6, 238) at zero token cost, while a
full flow run is an LLM session that writes a new numbered analysis document — an interim sample
at 944 would displace the walkthrough's expected index and add a document conveying nothing the
`jq` checks don't. If the PM prefers literal fidelity to the design's step 1, run the flow after
Task 2 and expect the walkthrough document at 945 instead.

---

## Task 0: Branch and premise verification

- [x] **0.1 Create the slice branch** — Effort: 1/5
  - [x] Confirm working tree is clean and current branch is `main` (integration branch is unset;
        target is `main`).
  - [x] `git checkout -b 362-slice.comprehension-analysis-and-graph-extraction main`
  - [x] Success: on the new branch, clean tree.

- [x] **0.2 Re-measure the design's premises** — Effort: 1/5
  - [x] Run the three reconciliation checks from Verification Walkthrough step 1 (design lines
        456–469): layer `nodeIds` sum, `meta.json` `analyzedFiles`, and the not-function-not-class
        node count.
  - [x] Confirm all three return **238**, and layer compositions show Packaged Declarative Content
        total=34 (config:13 file:1 pipeline:20) and Project Configuration total=6 (config:4 file:2),
        with every other layer file-only.
  - [x] **STOP condition:** if the three numbers do not agree, stop and report to the Project
        Manager — the coverage section's reconciliation claim is false and the design needs
        revisiting before implementation.
  - [x] Success: all checks match the design's Verified graph facts table, or work is stopped.

- [x] **0.3 Verify the id-prefix contract** — Effort: 1/5
  - [x] Run the three checks from Verification Walkthrough step 1b (design lines 477–489):
        second colon field equals `filePath` for all 925 nodes; zero `filePath` contains a colon;
        zero edges have an endpoint absent from `nodes`.
  - [x] **STOP condition:** if the first check returns any `ok:false`, stop — endpoint resolution
        must fall back to file-level endpoints only per the design's scope note (Section detail
        item 6), and the PM decides before Task 6.4 is authored against the wrong contract.
  - [x] Success: `ok:true, n:925`; colon count 0; absent-endpoint count 0 (or documented fallback
        decision).

## Task 1: Correction 1 — layer counting

- [x] **1.1 Replace the intersect-with-`type=="file"` layer counting** — Effort: 2/5
  - [x] In `commands/analysis/understand.md`, remove the claim that `layers[].nodeIds` mixes file,
        function, and class nodes, and the instruction to intersect with `type == "file"`.
  - [x] Replace with: layer count is `nodeIds | length` directly; when a layer contains anything
        other than `file` nodes, report its type breakdown (e.g. `34 (config:13 file:1 pipeline:20)`).
  - [x] Retain a cross-check: every `nodeIds` entry must resolve to a node carrying `filePath`; an
        entry resolving to a `function` or `class` node is **reported as upstream drift**, never
        silently filtered.
  - [x] Success: skill text contains no intersect instruction; count rule, breakdown rule, and
        drift cross-check all present.

- [x] **1.2 Verify correction 1 against the real graph** — Effort: 1/5
  - [x] Execute the skill's new layer-count selection exactly as the skill now states it.
  - [x] Success: Packaged Declarative Content reports **34** with type breakdown, Project
        Configuration reports **6**, totals sum to **238**, and the cross-check reports zero drift.
  - [x] Commit: `fix: count layers by nodeIds length with type breakdown (correction 1)`

## Task 2: Correction 2 — file-level selector

- [x] **2.1 Widen the file-level selector to an exclusion** — Effort: 2/5
  - [x] Replace `select(.type == "file")` (wherever the skill uses it as the file-level filter)
        with `select(.type != "function" and .type != "class")`, stated as an exclusion by name so
        a future tenth upstream file-level type is included automatically.
  - [x] State the definition in the skill: "file-level" means "carries a `filePath`", and the
        architecture's nine file-level types are all included.
  - [x] Add the drift rule: a node surviving the filter but carrying no `filePath` is reported as
        drift.
  - [x] Success: no remaining `type == "file"` file-level filter in the skill; exclusion selector,
        definition, and drift rule present.

- [x] **2.2 Verify correction 2 against the real graph** — Effort: 1/5
  - [x] Execute the skill's new file-level selection as written.
  - [x] Success: yields **238** nodes, reconciling exactly with `meta.json`'s `analyzedFiles`;
        zero nodes lack `filePath`.
  - [x] Commit: `fix: widen file-level selector to exclude function/class by name (correction 2)`

## Task 3: Correction 3 — `fingerprints.json` note

- [x] **3.1 Reword the churn note** — Effort: 1/5
  - [x] In the skill's `.gitignore` section, replace the "expect it to churn — it rewrites on
        every graph refresh" wording with text naming what actually rewrites `fingerprints.json`:
        a deliberate `/understand` re-run, or the post-commit auto-update hook **only when
        `autoUpdate` is enabled** in `config.json`.
  - [x] State explicitly: **reading a graph never writes fingerprints**, and squadron's flows only
        read (`jq` selections).
  - [x] Do not change the tracking decision or `.gitignore` itself — ignore scope stays trash-only.
  - [x] Success: note names both writers and their triggers; states reads never write; `git diff`
        touches only `commands/analysis/understand.md`.
  - [x] Commit: `docs: correct fingerprints.json churn note to name actual writers (correction 3)`

## Task 4: Extraction mapping table

- [x] **4.1 Add the mapping table as the flow's governing reference** — Effort: 2/5
  - [x] Add the seven-row extraction mapping table from the design (Technical Decisions →
        Extraction mapping) to `commands/analysis/understand.md`: section, source fields, ordering
        rule, fallback. Reproduce the design's rows; do not paraphrase field names.
  - [x] State the two governing rules with it: section order is identity → structure → detail →
        caveats, and the fallback column has **no third option** — sourced content or a gap
        marker, never omission, never untraceable prose.
  - [x] Success: table matches the design row-for-row (7 sections, same fields, same ordering
        rules, same fallbacks); both governing rules stated adjacent to it.

- [x] **4.2 Verify table fidelity** — Effort: 1/5
  - [x] Diff-check each row against design lines 241–249; confirm no field renamed, dropped, or
        added.
  - [x] Success: row-for-row match confirmed.
  - [x] Commit: `feat: add field-to-section extraction mapping table to understand skill`

## Task 5: New sections

Each new section is authored in the skill's comprehension flow per its mapping row and the
design's Section detail. One subtask per section, verification paired with each.

- [x] **5.1 Author section 1 — project identity** — Effort: 2/5
  - [x] Source: `project.name`, `.description`, `.languages`, `.frameworks`.
  - [x] `project.description` is quoted and attributed as the plugin's generated prose — never
        restated as squadron's own claim. `languages`/`frameworks` listed verbatim.
  - [x] Fallback: `[GAP: ...]` per missing subfield; `project` itself missing is a preflight
        rejection (already handled by 361 — do not duplicate).
  - [x] Inline attribution per SC1: the generated section body opens with a lead sentence naming
        its source fields (the 943 `From \`...\`.` pattern) — in addition to the Provenance
        sourcing line.
  - [x] Success: instructions cover all four fields, attribution rule, inline lead-in, and
        per-subfield gaps.

- [x] **5.2 Verify section 1 sources** — Effort: 1/5
  - [x] `jq` the four `project.*` fields from the real graph; confirm each is present and the
        skill's selection retrieves them.
  - [x] Success: all four fields returned non-empty on this graph.

- [x] **5.3 Author section 3 — entry points** — Effort: 2/5
  - [x] Source: file-level nodes whose `tags` contains `entry-point`. The tag is the signal — no
        filename heuristics, and upstream's judgment is reported, never overruled (a tagged
        `__init__.py` is reported as tagged).
  - [x] Ordering: group by layer, report per-layer count with paths (27 nodes is too many flat).
  - [x] Fallback: `[GAP: no node carries the entry-point tag — re-run /understand]`.
  - [x] Inline attribution per SC1: section body opens with a lead sentence naming its source
        fields (the 943 `From \`...\`.` pattern).
  - [x] Success: tag-only selection, layer grouping, inline lead-in, exact fallback present.

- [x] **5.4 Verify section 3 sources** — Effort: 1/5
  - [x] `jq` count of file-level nodes tagged `entry-point`; confirm 27 on this graph and that
        each maps to exactly one layer.
  - [x] Success: count matches; layer grouping is total (no orphan).

- [x] **5.5 Author section 7 — coverage and scope limits** — Effort: 2/5
  - [x] `analyzedFiles` from `meta.json`, reconciled against the file-level node count. Equal is
        stated as expected; **a mismatch reports both numbers as a discrepancy** — never silently
        prefer either.
  - [x] `config.json`: report settings present; do not report absent optional keys as gaps
        (upstream owns its defaults — `autoUpdate` absent here is not a gap).
  - [x] `.understandignore`: report count of active (uncommented, non-blank) patterns and list
        them; all-comments/blank file is reported as "defaults only", a real state, not a gap.
  - [x] Fallback: `[GAP: ...]` naming the unreadable file.
  - [x] Inline attribution per SC1: section body opens with a lead sentence naming its source
        fields (the 943 `From \`...\`.` pattern).
  - [x] Success: all three 361 deferrals closed by this section's instructions; inline lead-in
        required; discrepancy and defaults-only paths explicit.

- [x] **5.6 Verify section 7 sources** — Effort: 1/5
  - [x] Confirm against the real inputs: `analyzedFiles` = 238 = file-level count;
        `config.json` holds only `outputLanguage: en`; active `.understandignore` pattern count
        matches `grep -vE '^\s*(#|$)' | wc -l` (17 at design time — re-measure, report actual).
  - [x] Success: skill instructions produce these values as written.
  - [x] Commit: `feat: add project identity, entry points, and coverage sections to flow`

## Task 6: Deepen existing sections

One subtask per section; each gains its explicit ordering rule and fallback per the mapping table.

- [x] **6.1 Deepen section 2 — layer architecture** — Effort: 1/5
  - [x] Ordering: descending file count. Source: `layers[]` `name`, `description`, `nodeIds`.
  - [x] Counts per correction 1 (Task 1) — `nodeIds | length` with type breakdown where mixed.
  - [x] Fallback: none needed beyond preflight (empty `layers` is a 361 preflight rejection);
        state that.
  - [x] Inline attribution per SC1: section body opens with a lead sentence naming its source
        fields (the 943 `From \`...\`.` pattern).
  - [x] Success: ordering rule, count rule, and inline lead-in explicit; no new fallback invented.

- [x] **6.2 Deepen section 4 — complexity hotspots** — Effort: 2/5
  - [x] `complexity` is an ordinal string (`simple`/`moderate`/`complex`) — never sort numerically.
  - [x] Report full tier distribution across all file-level nodes, then list the top tier grouped
        by layer.
  - [x] Attach `languageNotes` where present; **omit silently where absent** — the one sanctioned
        omission, because it is a per-node optional annotation, not a section source field. State
        this exception in the skill.
  - [x] A value outside the observed ordinal set is reported as an unrecognized tier, never
        bucketed.
  - [x] Fallback: `[GAP: ...]` naming `complexity`.
  - [x] Inline attribution per SC1: section body opens with a lead sentence naming its source
        fields (the 943 `From \`...\`.` pattern).
  - [x] Success: distribution + top-tier-by-layer rules, languageNotes exception, unrecognized-tier
        rule, inline lead-in, and fallback all present.

- [x] **6.3 Deepen section 5 — suggested reading order** — Effort: 1/5
  - [x] Source: `tour[]` (`order`, `title`, `description`), ordered by `order` ascending;
        `description` annotates each step.
  - [x] Fallback: `[GAP: ...]` naming `tour` (preflight has already warned; the section still
        emits its own marker).
  - [x] Inline attribution per SC1: section body opens with a lead sentence naming its source
        fields (the 943 `From \`...\`.` pattern).
  - [x] Success: ordering rule, inline lead-in, and fallback explicit.

- [x] **6.4 Deepen section 6 — dependency observations** — Effort: 3/5
  - [x] Edge-type counts across the whole graph; then inter-layer `imports`/`depends_on`
        connections, self-references excluded, ordered by descending count with ties broken by
        `weight`.
  - [x] **Endpoint resolution is a string parse of the edge's own `source`/`target` id**
        (`<type>:<filePath>[:<name>]` → second colon field is the owning file's path → that
        file's layer). No node — and specifically no function/class node — is read to resolve an
        endpoint.
  - [x] Failure path, verbatim from the design: an endpoint that does not parse, or whose
        `filePath` matches no file-level node, is excluded from the tally and **reported as drift
        naming the endpoint id**; the excluded count appears as a `[GAP: ...]` in the section when
        non-zero. Never silently skipped.
  - [x] Include the design's scope note: if the id-prefix contract fails on a future graph,
        restrict the tally to file-level endpoints and report the excluded count.
  - [x] Inline attribution per SC1: section body opens with a lead sentence naming its source
        fields (the 943 `From \`...\`.` pattern).
  - [x] Success: string-parse rule, both drift variants, non-zero-count gap marker, inline
        lead-in, and the fallback scope note all present.

- [x] **6.5 Verify deepened sections** — Effort: 1/5
  - [x] Review each of 6.1–6.4 against the mapping table and the design's Section detail —
        every ordering rule and fallback matches its row exactly.
  - [x] Execute the section 6 edge selections against the real graph: expect 0 unresolvable
        endpoints of 2184, and inter-layer tallies computable without reading any node.
  - [x] Success: no divergence from mapping table; edge checks pass.
  - [x] Commit: `feat: add ordering rules and fallbacks to layer, complexity, tour, dependency sections`

## Task 7: Recorded decisions and cross-reference

- [x] **7.1 Record `[INFERRED]` governance in the skill** — Effort: 1/5
  - [x] State: this flow does not use `[INFERRED]`; every claim traces to a named field, so its
        appearance in a comprehension document is a defect — the correct output where inference
        would go is a gap marker.
  - [x] Include the closing-observation test: a section's closing sentence must be derivable from
        the data presented directly above it, or it does not belong. Zero `[INFERRED]` markers in
        a conforming document.
  - [x] Note the marker remains documented in shared conventions for 363's interview path.
  - [x] Success: rule, mechanical test, and 363 note present in the skill.

- [x] **7.2 Record the `analyze-codebase-prompt.md` decision in the skill** — Effort: 1/5
  - [x] State the decision: two conventions adopted (fact/inference discipline; a data-lacking
        section says so and names what would supply it), no structure adopted (its ten-part
        template serves a probe+Repomix backend the graph cannot feed), document retained
        unchanged in `user/reference/`.
  - [x] Success: decision recorded; matches the design's wording in substance.

- [x] **7.3 Add the cross-reference line to the reference document** — Effort: 1/5
  - [x] Add exactly one line to `user/reference/analyze-codebase-prompt.md` pointing at the
        graph-backed path (`commands/analysis/understand.md`), noting both alternatives exist.
        Nothing else in the file changes; frontmatter `dateUpdated` may be refreshed.
  - [x] Success: `git diff` for this file shows the one content line (plus frontmatter date at
        most).
  - [x] Commit: `docs: record INFERRED and analyze-codebase-prompt decisions; add cross-reference`

## Task 8: Verification walkthrough

Runs from the repo root on the slice branch. The flow is exercised by opening
`commands/analysis/understand.md` in a Claude Code session and instructing "execute this skill's
comprehension analysis flow against this repo" (dispatcher routing is slice 366).

- [x] **8.1 Happy path** — Effort: 3/5
  - [x] Run the flow. Preflight reports as in 361, unchanged. Document written to the next unused
        index — expect **944** (943 is not overwritten).
  - [x] Confirm in the document: seven sections in mapping-table order; `## Provenance`
        immediately under the H1 with a section-sourcing line per section; every section body
        opens with an inline lead sentence naming its source fields (SC1, the 943 `From \`...\`.`
        pattern); Packaged Declarative Content reports 34 with type breakdown; coverage states
        238 analyzed files, `outputLanguage: en`, and the active pattern count;
        `grep -c 'INFERRED'` returns 0.
  - [x] Success: all listed checks pass on the written document.

- [x] **8.2 Frontmatter gate** — Effort: 1/5
  - [x] `cf validate frontmatter` on the new document: no inconsistencies; `model:` is a real
        model id, not a placeholder.
  - [x] Success: gate passes.

- [x] **8.3 Spot-checks against the real repo** — Effort: 1/5
  - [x] At least three, recorded here when done. Candidates from the design: pipeline YAML count
        vs reported pipeline nodes; template YAML count vs config nodes under `templates/`;
        active `.understandignore` pattern count vs reported.
  - [x] Spot-checks executed: pipeline YAML 20 == 20 pipeline nodes; 7 review templates at
        src/squadron/data/templates/; 17 active .understandignore patterns == 17 reported. One
        caveat recorded: upstream prose reports "27 sub-commands" but 23 registrations found; not
        reconciled per scope.
  - [x] Success: each reported number matches, or the mismatch is reported (never reconciled by
        hand).

- [x] **8.4 Gap-marker paths (scratch graph copies)** — Effort: 2/5
  - [x] Build scratch copies per design walkthrough step 5 — never modify the repo's real graph.
  - [x] Empty `tour` → reading-order section gap marker, same marker in provenance flagged-gaps
        line (2 occurrences), run completes.
  - [x] No `entry-point` tag anywhere → entry-points gap marker naming the tag; other sections
        unaffected; run completes.
  - [x] `meta.json` removed → coverage analyzed-file line carries a gap marker; staleness records
        its skip per the 361 contract.
  - [x] Success: all three variants produce the specified markers and complete.

- [x] **8.5 Unresolvable edge endpoints (induced)** — Effort: 2/5
  - [x] Per design step 5b: one scratch graph with a dangling `target`
        (`file:does/not/exist.py`), one with a malformed source (`malformed-endpoint-id`).
  - [x] Each run must exclude the edge from the inter-layer tally, report it as drift **naming
        the endpoint id**, and carry the excluded count as a `[GAP: ...]` in the dependency
        section.
  - [x] **A run with an unchanged-looking tally and no mention of the excluded edge is a failure
        of this task, not a pass.**
  - [x] Success: both variants produce the drift report and gap marker.

- [x] **8.6 Coverage discrepancy** — Effort: 1/5
  - [x] Scratch `meta.json` with `analyzedFiles = 999`: coverage section reports **both** numbers
        and names the discrepancy, preferring neither.
  - [x] Success: both numbers present in output.

- [x] **8.7 Read discipline** — Effort: 1/5
  - [x] Confirm from the 8.1 session: only `jq` field-scoped selections touched
        `knowledge-graph.json` — no `cat`, `head`, or Read tool call against it; no
        function/class node data in any section.
  - [x] Success: no whole-graph read occurred.

- [x] **8.8 Full-slice checks** — Effort: 1/5
  - [x] `git diff --stat main -- src/` is empty; `uv run ruff format --check .` passes;
        `uv run pytest tests/skills/` passes (pack install path undisturbed).
  - [x] Only changed non-document files: `commands/analysis/understand.md` and the
        cross-reference line in `user/reference/analyze-codebase-prompt.md`.
  - [x] Success: all three commands clean; changed-file set as stated.
  - [x] Commit: `feat: add generated 944 comprehension analysis and walkthrough fixes`
        (include any fixes found during 8.x; commit fixes with the evidence that found them)

## Task 9: Close the slice

- [x] **9.1 Update task and slice status** — Effort: 1/5
  - [x] All checkboxes above verified against the walkthrough evidence; dropped/skipped items (if
        any) marked `[x]` with a note per project convention.
  - [x] Set this file's `status: complete`, refresh `dateUpdated`; set the slice design's
        `status` per its frontmatter contract.
  - [x] Success: statuses consistent across task file and slice design.

- [x] **9.2 DEVLOG entry** — Effort: 1/5
  - [x] Write the slice-completion DEVLOG entry per `prompt.ai-project.system.md` → Session State
        Summary: corrections landed (with the 34/6/238 confirmations), 944 generated, walkthrough
        outcomes, any deviations.
  - [x] Success: entry present, dated, concise.

- [x] **9.3 Final commit and hand-off** — Effort: 1/5
  - [x] `uv run ruff format .` before committing (project rule), commit remaining changes, confirm
        clean tree.
  - [x] Report to the Project Manager for review and merge authorization. **Do not merge** —
        merging the slice branch is PM-gated.
  - [x] Success: branch complete and clean; PM notified; no merge performed.
