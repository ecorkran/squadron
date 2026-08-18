---
docType: tasks
slice: graph-contract-and-provenance
project: squadron
lldReference: project-documents/user/slices/361-slice.graph-contract-and-provenance.md
parent: project-documents/user/architecture/360-slices.document-intelligence.md
dependencies: [340]
projectState: Phase 4 design complete and reviewed PASS (2904beb). No graph exists in this repo yet.
dateCreated: 20260818
dateUpdated: 20260818
status: complete
---

# Tasks: Graph Contract and Provenance

## Context Summary

- Working on slice **361**, the foundation slice of initiative 360 (Document Intelligence).
- Delivers the shared graph-reading contract every capability-(a) skill depends on — locating and
  validating the `understand-anything` knowledge graph, staleness, `.gitignore` hygiene, the
  provenance block, and the gap-marker syntax — inside the smallest real consumer that proves it
  works (a structural-only comprehension analysis).
- **Everything here is markdown authoring.** No Python is added. No file under `src/squadron/`
  changes. The only new non-document file is `commands/analysis/understand.md`.
- Design reviewed PASS (`361-review.slice.graph-contract-and-provenance.md`, 15 findings: 12 pass,
  3 note). All three notes are dispositioned in Task 1.1 below; none block.
- **Next planned slice:** 362 (Comprehension Analysis and Graph Extraction), which deepens the
  comprehension flow authored here and consumes the same contract sections.

### Verified anchors (traced 20260818 on `2904beb`)

| Anchor | Fact |
|---|---|
| Pack install glob | [installer.py:87](src/squadron/skills/installer.py#L87) — `source_path.glob("*.md")`, copies every pack `*.md` as its own skill |
| Existing pack contents | `commands/analysis/` holds only `tech-debt-audit.md` |
| Frontmatter gate | [frontmatter_gate.py:44](src/squadron/events/builtin/frontmatter_gate.py#L44) — delegates to `cf validate frontmatter`; squadron owns no schema |
| `model:` frontmatter field | Accepted — `cf validate frontmatter` passes on `942-analysis.tech-debt-audit.md`, which carries it (review F013 resolved) |
| Existing gitignore state | No `understand` or `trash` entry in `.gitignore` — Task 4.x exercises the create-and-append path, not the already-present path |
| Graph presence | **`.understand-anything/` does not exist in this repo** — Task 0.1 is a hard prerequisite for every walkthrough task |

### Deviation from the design document

The design's Verification Walkthrough opens with "Prerequisite: a real graph — run `/understand`
once if it does not exist." At task-authoring time it **does not** exist. That prerequisite is
promoted to Task 0.1, a blocking first task, because every downstream verification depends on it
and because generating the graph is a PM-gated action (it runs a marketplace plugin over the whole
repo, which costs tokens and writes to the working tree).

---

## Task 0: Prerequisite

- [x] **0.1 Generate the knowledge graph** — Effort: 1/5
  - [x] Confirm the `understand-anything` marketplace plugin is installed and available in this
        Claude Code session.
  - [x] Run the plugin's `/understand` against this repo to produce
        `.understand-anything/knowledge-graph.json`.
  - [x] **This task writes to the working tree and consumes significant tokens.** Confirm with the
        Project Manager before running; do not run it unattended.
  - [x] Success: `.understand-anything/knowledge-graph.json` and `meta.json` exist.
  - [x] Success: record the graph's actual top-level keys and the `meta.json` fields present. If
        the observed shape differs from the architecture's documented contract (`project`,
        `nodes`, `edges`, `layers`, `tour`), **stop and raise to the Project Manager** — that is a
        contract change, not an implementation detail (design Risk Assessment).
  - [x] Do **not** commit `.understand-anything/` contents in this task; Task 4.1 settles what is
        ignored and what is tracked.

- [x] **1.1 Disposition the review notes** — Effort: 1/5
  - [x] **F013 (`model:` frontmatter field) — already resolved, no action.** Verified: `cf validate
        frontmatter` passes on `942-analysis.tech-debt-audit.md`, which carries `model:`. Record
        this in the skill's frontmatter section as a verified fact, not an assumption.
  - [x] **F011 (`config.json`, `.understandignore` unaddressed) — out of scope for 361, forward to
        362.** Disposition only; the "not consumed at this depth" note is **authored in Task 2.1**,
        which owns the read-discipline section. Nothing is written to the skill file here.
  - [x] **F012 (`meta.json` `analyzedFiles` unused) — out of scope for 361, forward to 362.** Same
        treatment and same handoff as F011.
  - [x] Success: this task produces a decision, not skill text. It is complete when all three notes
        are dispositioned — F013 verified resolved, F011 and F012 handed to Task 2.1 for authoring.

---

## Task 1: Skill file skeleton

- [x] **1.2 Create `commands/analysis/understand.md` with its skill header** — Effort: 2/5
  - [x] Create the file with YAML skill frontmatter matching the shape of
        `commands/analysis/tech-debt-audit.md`: `name`, `description`, and
        `disable-model-invocation: true` (this skill writes documents and runs on explicit
        invocation only).
  - [x] `name: understand`. Write a `description` that states it consumes an existing
        `understand-anything` knowledge graph and writes squadron planning documents — it must not
        claim to analyze a codebase itself, which is the plugin's job.
  - [x] Lay out the section skeleton in the order the design's Component Structure specifies:
        **Preflight: Graph Contract** → **Document Conventions** → **Flow: Comprehension
        Analysis**, plus a human-facing maintainer section after a `---` divider (matching
        `tech-debt-audit.md`'s protocol/documentation split).
  - [x] Add a note in the maintainer section stating why the contract lives in **this file** rather
        than a separate fragment: `_install_prefix()` installs every pack `*.md` as its own skill,
        so a fragment file would surface as a bogus installable command.
  - [x] Success: file exists, sections are present and empty-but-titled, and the file's purpose is
        unambiguous to a reader who has not read the design.

- [x] **1.3 Verify the skeleton installs** — Effort: 1/5
  - [x] Run `sq skills install analysis` and read the receipt.
  - [x] Success: the receipt lists both `tech-debt-audit.md` and `understand.md`.
  - [x] Success: no change to `src/squadron/`, manifests, or installer code was required.
  - [x] Run the existing skills test suite (`uv run pytest tests/skills/`) and confirm it is green.
  - [x] **Commit checkpoint:** commit the skeleton before authoring protocol content.
  - [x] Environment note: the `sq` on PATH (`/Users/manta/.local/bin/sq`) is a separate global uv-tool install and reports only 1 file. Use `uv run sq skills install analysis` to exercise the working-tree installer, which correctly reports 2 files.

---

## Task 2: Preflight — graph location and validation

- [x] **2.1 Author graph location and read discipline** — authored in commands/analysis/understand.md. Read-discipline table names each jq selection; function/class nodes excluded via `select(.type == "file")`; missing jq stops the run; F011/F012 deferral note included.
  - [x] Specify graph root resolution: `git rev-parse --show-toplevel`, falling back to the current
        working directory outside a repository; graph root is `<root>/.understand-anything/`.
  - [x] Specify that all reads are field-scoped `jq` selections and the graph is never loaded whole
        into context. Name the specific selections needed: key presence, array lengths, `layers[]`,
        file-level nodes (`id`, `filePath`, `summary`, `complexity` only), `tour[]`
        order/title/nodeIds, edge aggregates.
  - [x] State explicitly that function- and class-level nodes are never read.
  - [x] Specify that a missing `jq` stops the run with a clear message — it must **not** fall back
        to reading the raw file into context.
  - [x] Include the F011/F012 deferral note from Task 1.1.
  - [x] Success: a junior AI following this section reads only named fields and could not
        accidentally load the whole graph.

- [x] **2.2 Author the three-way validation failure** — three distinct messages authored (absent / unparseable / malformed), tour asymmetry specified, governing rule stated.
  - [x] Author the checks in order, each with its own distinct message:
    1. **Absent** — graph file does not exist → stop; message points at running the plugin's
       `/understand` first. This message must **not** speculate about whether the plugin is
       installed (that detection is slice 366 scope).
    2. **Unparseable** — `jq empty` fails → stop; message names the file and reports invalid JSON.
    3. **Malformed** — any required top-level key missing/mistyped, or `nodes`/`edges`/`layers`
       empty → stop; message names **each** offending key and reports graph identity
       (`lastAnalyzedAt`, `gitCommitHash` when readable).
  - [x] Specify the `tour` asymmetry: an empty `tour` **warns and proceeds** (it degrades one
        signal); empty `nodes`/`edges`/`layers` **reject** (nothing useful can be written).
  - [x] State the governing rule in the section: a renamed upstream field must surface as failure 3,
        never as a silently thinner document.
  - [x] Success: the three messages are textually distinct and each names what a reader must do
        next.

- [x] **2.3 Verify validation against real and tampered graphs** — all six cases run in a scratch copy outside the repo. Real graph passed (nodes 925, edges 2184, layers 10, tour 15). `del(.layers)` produced "MALFORMED: missing key(s): layers" plus identity (version 1.0.0, gitCommitHash 1bfbca1, lastAnalyzedAt). `.layers = []` produced "MALFORMED: empty required array(s): layers". `.tour = []` warned and proceeded. Truncated file produced "UNPARSEABLE" with jq's parse error. Absent directory produced the run-/understand-first message. Three failure messages confirmed textually distinct in actual output.
  - [x] Work in a scratch copy outside this repo; never tamper with this repo's real graph.
  - [x] **Happy path:** run preflight against the real graph (Task 0.1) — expect it to pass and
        report node/edge/layer counts.
  - [x] **Missing key:** `jq 'del(.layers)'` on the scratch copy — expect a loud error naming
        `layers` plus graph identity, and no document written.
  - [x] **Empty array:** `jq '.layers = []'` — expect the same rejection.
  - [x] **Empty tour:** `jq '.tour = []'` — expect a **warning** and a completed run.
  - [x] **Unparseable:** truncate the JSON mid-object — expect the invalid-JSON message, distinct
        from the missing-key message.
  - [x] **Absent:** run in a scratch directory with no `.understand-anything/` — expect the
        run-`/understand`-first message, distinct from all of the above.
  - [x] Success: all six runs produce the specified outcome; the three failure messages are
        confirmed distinct in actual output, not just in the source text.

---

## Task 3: Preflight — staleness

- [x] **3.1 Author the staleness check** — authored; three comparison outcomes, explicit skip reasons, never fabricates a distance, PM decision recorded in provenance.
  - [x] Specify reading `gitCommitHash` from `meta.json`; if `meta.json` is missing or the field is
        absent, report that the check cannot run **for that reason** and record the skip in
        provenance.
  - [x] Specify the git-unavailable path: if `git` is absent or the directory is not a repository,
        announce the skip explicitly in console output **and** record it in the provenance block.
        Never skip silently.
  - [x] Specify the three comparison outcomes against `git rev-parse HEAD`:
    1. equal → "matched HEAD";
    2. differing, hash is a known ancestor → distance via `git rev-list --count {hash}..HEAD`,
       reported as "N commits behind HEAD";
    3. differing, hash unknown to the repo (rebase, amend, shallow clone) → drift reported with
       **unknown** distance and the reason. Never fabricate a distance number.
  - [x] Specify that on any drift the skill states the finding and asks the PM to proceed or stop
        and refresh; proceeding is recorded in provenance as a PM choice. The check never blocks on
        its own.
  - [x] Success: every path either produces a distance, an explicit unknown-distance reason, or an
        explicit skip reason — there is no silent outcome.

- [x] **3.2 Verify staleness paths** — all five verified. Matched-HEAD confirmed via scratch meta at current HEAD. "Behind" exercised naturally against real data: graph hash 1bfbca1 vs HEAD abd6a4d gave "1 commits behind HEAD" via git rev-list --count (no throwaway commit needed — the skeleton commit moved HEAD). Unknown hash produced drift with unknown distance and no fabricated number. Non-repo scratch dir produced explicit skip. Missing meta.json and present-but-no-gitCommitHash produced two distinct "cannot run" reasons.
  - [x] **Matched:** run against the fresh graph from Task 0.1 with a clean tree — expect "matched
        HEAD".
  - [x] **Behind:** make one throwaway commit, re-run — expect "1 commit behind HEAD" and a PM
        prompt; confirm proceeding is possible. Reset the throwaway commit afterwards.
  - [x] **Unknown distance:** in the scratch copy, set `gitCommitHash` to a syntactically valid but
        unknown hash — expect drift reported with unknown distance and a stated reason, and **no
        fabricated number**.
  - [x] **No git:** copy graph and skill inputs to a scratch directory that is not a repository —
        expect an explicit skip statement in console output.
  - [x] **No meta.json:** remove it in the scratch copy — expect the distinct "cannot run" reason.
  - [x] Success: all five paths behave as specified; the console output states the outcome in every
        case.
  - [x] **Commit checkpoint:** committed as 7b5a90e.

---

## Task 4: Preflight — `.gitignore` hygiene

- [x] **4.1 Author the hygiene step** — authored; runs before any document write, semantic `git check-ignore -q` test, append with squadron-managed comment, re-confirm, non-fatal failure reporting, what-is-not-ignored rationale.
  - [x] Specify that hygiene runs per-run, at the start, **before any document is written**.
  - [x] Specify the semantic idempotency test:
        `git check-ignore -q .understand-anything/.trash-probe/`. Exit 0 → already covered by some
        rule (including a broader `.understand-anything/` ignore) → report "already ignored" and
        write nothing. Note in the text that the probe path need not exist for the check to work.
  - [x] Specify the append (creating `.gitignore` if absent): a comment line marking it
        squadron-managed, then `.understand-anything/.trash-*/`.
  - [x] Specify re-running the check to confirm, then reporting the addition.
  - [x] Specify failure handling: read-only or permission-denied → report that the entry could not
        be added **and why**, then continue (non-fatal). Outside a git repository → report that
        hygiene does not apply. Never proceed claiming a write succeeded when it did not.
  - [x] State what is **not** ignored and why: `knowledge-graph.json`, `meta.json`, `config.json`,
        and `.understandignore` stay tracked as durable project knowledge. Squadron never deletes
        trash directories — the upstream purge owns that lifecycle.
  - [x] Success: the section specifies a semantic check (not a pattern grep), and every failure
        path is reported rather than swallowed.

- [x] **4.2 Verify hygiene idempotency and failure paths** — all five verified. First run appended the entry and confirmed; real trash dir .trash-1787060004 now matched by .gitignore:177. All four durable files (knowledge-graph.json, meta.json, config.json, .understandignore) confirmed NOT ignored. Second run reported "already ignored", .gitignore md5 unchanged, exactly 1 matching line (no duplicate). Broader `.understand-anything/` rule accepted with no addition. chmod 444 produced a reported non-fatal permission-denied and the run continued. Non-repo dir produced does-not-apply.
  - [x] **First run (this repo has no entry today):** run — expect `.gitignore` to gain the entry
        exactly once, reported.
  - [x] **Second run:** run again — expect "already ignored"; confirm `git diff .gitignore` is
        empty and there is no duplicate line.
  - [x] **Broader ignore accepted:** temporarily replace the entry with `.understand-anything/`,
        run — expect no addition. Restore the original entry afterwards.
  - [x] **Read-only:** `chmod 444 .gitignore`, run — expect a reported non-fatal failure **and a
        completed run**. `chmod 644 .gitignore` to restore.
  - [x] **Not a repository:** run in a non-repo scratch directory — expect the does-not-apply
        report.
  - [x] Success: all five paths behave as specified; no duplicate `.gitignore` line exists after
        repeated runs.
  - [x] **Commit checkpoint:** committed as 6e0363e.

---

## Task 5: Document conventions

- [x] **5.1 Author the gap-marker syntax** — authored in commands/analysis/understand.md. Marker `[GAP: {what is missing} — {which input would supply it}]`, [INFERRED] retained as sibling convention from analyze-codebase-prompt.md, three rules stated (body + provenance placement, valid output, never filled with prose).
  - [x] Specify the marker: `[GAP: {what is missing} — {which input would supply it}]`, placed in
        the body exactly where the content would have appeared.
  - [x] Specify `[INFERRED]` as the retained sibling convention from
        `user/reference/analyze-codebase-prompt.md` — a prefix for claims from indirect evidence.
        State that 361's structural output should not need it (all claims trace to named fields)
        and that its use in the deepened analysis is 362's to govern.
  - [x] Specify the three rules: markers appear in the body at the point of absence **and** are
        listed in the provenance block; a document with gap markers is a valid output, not a
        failure; a gap is never filled with plausible prose.
  - [x] Success: a junior AI can tell from this section alone which marker to use and where both
        copies of it go.

- [x] **5.2 Author the provenance block format** — authored. `## Provenance` immediately after H1 as body prose (not frontmatter) with the reason stated. All nine lines specified. Block obeys its own gap-marker rule. Review-state line always states machine-generated draft with no human review. Slice 365 reuse noted.
  - [x] Specify placement: a `## Provenance` section immediately after the H1 title, before all
        content, as body prose — **not** frontmatter. Include the reason: frontmatter is
        schema-validated and invisible to a reader, and the failure this guards against is a human
        trusting a stale or partly-invented document.
  - [x] Author the line set per the design: generated-by, generated-date, source (with node/edge/
        layer/tour counts), graph identity (`gitCommitHash`, `lastAnalyzedAt`), staleness state,
        section sourcing, flagged gaps, review state.
  - [x] Specify that the block obeys its own gap-marker rule — a missing `meta.json` yields a
        `[GAP: ...]` in the graph-identity line, consistent with the staleness skip line.
  - [x] Specify that the review-state line always states the document is a machine-generated draft
        with no human review. This is what makes `status: not_started` legible on a generated draft.
  - [x] Note that capability (b) (slice 365) reuses this shape with **Source** naming the concept
        and initiative-plan paths instead.
  - [x] Success: every line resolves from real data or carries a gap marker; no line can be silently
        omitted.

- [x] **5.3 Author the generated-document conventions** — authored. Output path, index selection (lowest unused >= 940, new index per run, 949 overflow sanctioned), frontmatter field set, `model:` must hold the real generating model id with an explicit stop-and-say-so instruction if the model cannot determine its own id (no example id in the text, per the hallucination-trap rule), F013 verified fact recorded, `status: not_started` rationale stated.
  - [x] Specify the output path
        `project-documents/user/analysis/{index}-analysis.codebase-comprehension.md`.
  - [x] Specify index selection: lowest unused index ≥ 940, found by scanning existing `9nn-`
        filenames in `user/analysis/`. Each run takes a **new** index — runs are independent
        samples, matching the existing `940`/`941`/`942` series. State that overflow past 949 is
        sanctioned by the architecture.
  - [x] Specify the frontmatter fields: `docType: analysis`, `project`, `topic:
        codebase-comprehension`, `dateCreated`, `dateUpdated`, `status: not_started`, `model`.
  - [x] **`model:` must be populated with the id of the model actually generating the document** —
        never left empty, never a placeholder, never a hardcoded example. `cf validate frontmatter`
        is permissive here and will pass on a placeholder, so the skill text must state the
        requirement rather than relying on the gate to enforce it. Do not put an example model id
        in the skill's instruction text: if the generating model cannot determine its own id, it
        must say so rather than reach for the nearest plausible token.
  - [x] Record the verified fact from Task 1.1: `cf validate frontmatter` accepts `model:` on an
        `analysis` document (confirmed against `942-analysis.tech-debt-audit.md`).
  - [x] State why `status: not_started` is correct rather than a review-pending value: the enum has
        no `needs_review` member, `complete` would assert a review that has not happened, and review
        state is carried by the provenance block.
  - [x] Success: the conventions produce a document that passes `cf validate frontmatter` and does
        not collide with an existing index.

---

## Task 6: Comprehension analysis flow

- [x] **6.1 Author the comprehension flow at proving depth** — authored. Preflight-first, exactly four sections each naming its source field, explicit statement that depth/ordering/additional sections are 362's scope, unrecognized-argument handling.
  - [x] Specify that the flow runs preflight (Tasks 2–4) first, then extracts and writes.
  - [x] Author exactly four sections, each naming its source graph field inline:
    1. **Layer architecture** — each layer's name, description, and file count, from `layers[]`.
    2. **Complexity hotspots** — top file-level nodes by `complexity`, with `filePath` and
       `summary`.
    3. **Suggested reading order** — `tour[]` step titles in order, or a gap marker if `tour` is
       empty.
    4. **Dependency observations** — edge-type counts and the strongest inter-layer
       `imports`/`depends_on` connections, from `edges[]`.
  - [x] State explicitly that section depth, ordering, fallbacks, and any **additional** sections
        are slice 362's scope, and that 361 must not grow this list.
  - [x] Specify that any argument other than the comprehension default is treated as unrecognized
        (the concept and candidates flows are 363/364).
  - [x] Success: the flow exercises every contract element — validation, staleness, hygiene,
        provenance, gap markers, index selection — end to end.
  - [x] Divergence from design: `complexity` is an ordinal STRING (observed values `simple` 83 / `moderate` 76 / `complex` 42 across 201 file nodes), not a numeric sort key. `sort_by(-.complexity)` fails outright on a string. Flow section 2 corrected to select the top tier rather than sort numerically. Field name and presence match the documented contract, so this is a narrowing, not a contract break — no escalation required, recorded for slice 362.

- [x] **6.2 Verify the happy path against this repo** — all sub-bullets. Generated `project-documents/user/analysis/943-analysis.codebase-comprehension.md` at the expected next index (940/941/942 existed). Provenance block confirmed at line 13, directly under the H1 at line 11, above all content. Every structural claim names its graph field. `cf validate frontmatter` = "No inconsistencies found (1 file checked)". `model:` read back as `claude-opus-5[1m]` — a real id, not a placeholder. A second run would select 944, not overwrite. SPOT-CHECKS BOTH HOLD: (1) CLI Surface layer description claims "27 sq sub-commands" — `src/squadron/cli/commands/*.py` contains exactly 27 modules; (2) `src/squadron/pipeline/sdk_session.py` rated `complex` — confirmed a real 288-line module wrapping a long-lived ClaudeSDKClient across dispatch steps, its own docstring matching the graph summary.
  - [x] Run the full flow against this repo using the real graph.
  - [x] Success: a new `user/analysis/{index}-analysis.codebase-comprehension.md` exists at the
        expected next index.
  - [x] Success: the provenance block sits directly under the H1 title, above all content.
  - [x] Success: every structural claim names the graph field it derives from.
  - [x] **Spot-check two claims against the real repo** — pick one layer and one complexity hotspot
        and confirm they are true of the actual codebase. A claim that does not hold is a defect,
        not a cosmetic issue.
  - [x] Success: `cf validate frontmatter` passes on the generated file.
  - [x] Success: `model:` holds a real model id, not a placeholder or empty value. Check this by
        reading the field — the gate is permissive and will not catch it.
  - [x] Success: a second run produces a **new** index rather than overwriting the first.

- [x] **6.3 Verify at least one gap marker is exercised** — all sub-bullets. Real graph supplied everything (no natural gap), so the tampered `.tour = []` scratch copy was used per the task. Preflight warned and proceeded (required arrays OK). Marker demonstrated in BOTH required locations: the body's reading-order section and the provenance block's flagged-gaps line, 2 occurrences confirmed.
  - [x] If the real graph produced a gap marker naturally (e.g. a node lacking `complexity`),
        confirm it appears both in the body and in the provenance block's flagged-gaps line.
  - [x] If the real graph supplied everything, use the tampered `.tour = []` scratch copy from Task
        2.3 to produce the marker, and confirm both placements there.
  - [x] Success: at least one genuine `[GAP: ...]` marker is demonstrated in both required
        locations.
  - [x] **Commit checkpoint:** committed as be2ed5f.

---

## Task 7: Close-out

- [x] **7.1 Full-slice verification pass** — Effort: 2/5
  - [x] Walk the design's Verification Walkthrough steps 1–8 in order and confirm each produces its
        stated outcome. Steps map to tasks: 1→6.2, 2–4→4.2, 5→2.3, 6→2.3, 7→3.2, 8→1.3.
  - [x] Confirm the slice's ten Success Criteria are each satisfied, checking them against actual
        run output rather than the authored text.
  - [x] Confirm no file under `src/squadron/` changed: `git diff --stat main -- src/` is empty.
  - [x] Confirm the only new non-document file is `commands/analysis/understand.md`.
  - [x] Run `uv run ruff format` and `uv run ruff check` (note: bare `ruff` is not on PATH; use
        `uv run`). No Python changed, so these should be no-ops — run them to confirm that.
  - [x] Run the full test suite once and confirm it is green with no new skips.

- [x] **7.2 Mark the slice complete and record the session** — Effort: 1/5
  - [x] Check off entry 1 (361) in `360-slices.document-intelligence.md`.
  - [x] Set `status: complete` in the slice design's frontmatter.
  - [x] Write the DEVLOG entry per `prompt.ai-project.system.md` → Session State Summary. Record any
        observed divergence between the real graph's shape and the architecture's documented
        contract, since that is the initiative's standing risk.
  - [x] **Commit checkpoint:** final commit; merge the slice branch into `main` (no integration
        branch is configured).
