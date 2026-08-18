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
status: not_started
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

- [ ] **0.1 Generate the knowledge graph** — Effort: 1/5
  - [ ] Confirm the `understand-anything` marketplace plugin is installed and available in this
        Claude Code session.
  - [ ] Run the plugin's `/understand` against this repo to produce
        `.understand-anything/knowledge-graph.json`.
  - [ ] **This task writes to the working tree and consumes significant tokens.** Confirm with the
        Project Manager before running; do not run it unattended.
  - [ ] Success: `.understand-anything/knowledge-graph.json` and `meta.json` exist.
  - [ ] Success: record the graph's actual top-level keys and the `meta.json` fields present. If
        the observed shape differs from the architecture's documented contract (`project`,
        `nodes`, `edges`, `layers`, `tour`), **stop and raise to the Project Manager** — that is a
        contract change, not an implementation detail (design Risk Assessment).
  - [ ] Do **not** commit `.understand-anything/` contents in this task; Task 4.1 settles what is
        ignored and what is tracked.

- [ ] **1.1 Disposition the review notes** — Effort: 1/5
  - [ ] **F013 (`model:` frontmatter field) — already resolved, no action.** Verified: `cf validate
        frontmatter` passes on `942-analysis.tech-debt-audit.md`, which carries `model:`. Record
        this in the skill's frontmatter section as a verified fact, not an assumption.
  - [ ] **F011 (`config.json`, `.understandignore` unaddressed) — out of scope for 361, forward to
        362.** Disposition only; the "not consumed at this depth" note is **authored in Task 2.1**,
        which owns the read-discipline section. Nothing is written to the skill file here.
  - [ ] **F012 (`meta.json` `analyzedFiles` unused) — out of scope for 361, forward to 362.** Same
        treatment and same handoff as F011.
  - [ ] Success: this task produces a decision, not skill text. It is complete when all three notes
        are dispositioned — F013 verified resolved, F011 and F012 handed to Task 2.1 for authoring.

---

## Task 1: Skill file skeleton

- [ ] **1.2 Create `commands/analysis/understand.md` with its skill header** — Effort: 2/5
  - [ ] Create the file with YAML skill frontmatter matching the shape of
        `commands/analysis/tech-debt-audit.md`: `name`, `description`, and
        `disable-model-invocation: true` (this skill writes documents and runs on explicit
        invocation only).
  - [ ] `name: understand`. Write a `description` that states it consumes an existing
        `understand-anything` knowledge graph and writes squadron planning documents — it must not
        claim to analyze a codebase itself, which is the plugin's job.
  - [ ] Lay out the section skeleton in the order the design's Component Structure specifies:
        **Preflight: Graph Contract** → **Document Conventions** → **Flow: Comprehension
        Analysis**, plus a human-facing maintainer section after a `---` divider (matching
        `tech-debt-audit.md`'s protocol/documentation split).
  - [ ] Add a note in the maintainer section stating why the contract lives in **this file** rather
        than a separate fragment: `_install_prefix()` installs every pack `*.md` as its own skill,
        so a fragment file would surface as a bogus installable command.
  - [ ] Success: file exists, sections are present and empty-but-titled, and the file's purpose is
        unambiguous to a reader who has not read the design.

- [ ] **1.3 Verify the skeleton installs** — Effort: 1/5
  - [ ] Run `sq skills install analysis` and read the receipt.
  - [ ] Success: the receipt lists both `tech-debt-audit.md` and `understand.md`.
  - [ ] Success: no change to `src/squadron/`, manifests, or installer code was required.
  - [ ] Run the existing skills test suite (`uv run pytest tests/skills/`) and confirm it is green.
  - [ ] **Commit checkpoint:** commit the skeleton before authoring protocol content.

---

## Task 2: Preflight — graph location and validation

- [ ] **2.1 Author graph location and read discipline** — Effort: 2/5
  - [ ] Specify graph root resolution: `git rev-parse --show-toplevel`, falling back to the current
        working directory outside a repository; graph root is `<root>/.understand-anything/`.
  - [ ] Specify that all reads are field-scoped `jq` selections and the graph is never loaded whole
        into context. Name the specific selections needed: key presence, array lengths, `layers[]`,
        file-level nodes (`id`, `filePath`, `summary`, `complexity` only), `tour[]`
        order/title/nodeIds, edge aggregates.
  - [ ] State explicitly that function- and class-level nodes are never read.
  - [ ] Specify that a missing `jq` stops the run with a clear message — it must **not** fall back
        to reading the raw file into context.
  - [ ] Include the F011/F012 deferral note from Task 1.1.
  - [ ] Success: a junior AI following this section reads only named fields and could not
        accidentally load the whole graph.

- [ ] **2.2 Author the three-way validation failure** — Effort: 3/5
  - [ ] Author the checks in order, each with its own distinct message:
    1. **Absent** — graph file does not exist → stop; message points at running the plugin's
       `/understand` first. This message must **not** speculate about whether the plugin is
       installed (that detection is slice 366 scope).
    2. **Unparseable** — `jq empty` fails → stop; message names the file and reports invalid JSON.
    3. **Malformed** — any required top-level key missing/mistyped, or `nodes`/`edges`/`layers`
       empty → stop; message names **each** offending key and reports graph identity
       (`lastAnalyzedAt`, `gitCommitHash` when readable).
  - [ ] Specify the `tour` asymmetry: an empty `tour` **warns and proceeds** (it degrades one
        signal); empty `nodes`/`edges`/`layers` **reject** (nothing useful can be written).
  - [ ] State the governing rule in the section: a renamed upstream field must surface as failure 3,
        never as a silently thinner document.
  - [ ] Success: the three messages are textually distinct and each names what a reader must do
        next.

- [ ] **2.3 Verify validation against real and tampered graphs** — Effort: 3/5
  - [ ] Work in a scratch copy outside this repo; never tamper with this repo's real graph.
  - [ ] **Happy path:** run preflight against the real graph (Task 0.1) — expect it to pass and
        report node/edge/layer counts.
  - [ ] **Missing key:** `jq 'del(.layers)'` on the scratch copy — expect a loud error naming
        `layers` plus graph identity, and no document written.
  - [ ] **Empty array:** `jq '.layers = []'` — expect the same rejection.
  - [ ] **Empty tour:** `jq '.tour = []'` — expect a **warning** and a completed run.
  - [ ] **Unparseable:** truncate the JSON mid-object — expect the invalid-JSON message, distinct
        from the missing-key message.
  - [ ] **Absent:** run in a scratch directory with no `.understand-anything/` — expect the
        run-`/understand`-first message, distinct from all of the above.
  - [ ] Success: all six runs produce the specified outcome; the three failure messages are
        confirmed distinct in actual output, not just in the source text.

---

## Task 3: Preflight — staleness

- [ ] **3.1 Author the staleness check** — Effort: 2/5
  - [ ] Specify reading `gitCommitHash` from `meta.json`; if `meta.json` is missing or the field is
        absent, report that the check cannot run **for that reason** and record the skip in
        provenance.
  - [ ] Specify the git-unavailable path: if `git` is absent or the directory is not a repository,
        announce the skip explicitly in console output **and** record it in the provenance block.
        Never skip silently.
  - [ ] Specify the three comparison outcomes against `git rev-parse HEAD`:
    1. equal → "matched HEAD";
    2. differing, hash is a known ancestor → distance via `git rev-list --count {hash}..HEAD`,
       reported as "N commits behind HEAD";
    3. differing, hash unknown to the repo (rebase, amend, shallow clone) → drift reported with
       **unknown** distance and the reason. Never fabricate a distance number.
  - [ ] Specify that on any drift the skill states the finding and asks the PM to proceed or stop
        and refresh; proceeding is recorded in provenance as a PM choice. The check never blocks on
        its own.
  - [ ] Success: every path either produces a distance, an explicit unknown-distance reason, or an
        explicit skip reason — there is no silent outcome.

- [ ] **3.2 Verify staleness paths** — Effort: 2/5
  - [ ] **Matched:** run against the fresh graph from Task 0.1 with a clean tree — expect "matched
        HEAD".
  - [ ] **Behind:** make one throwaway commit, re-run — expect "1 commit behind HEAD" and a PM
        prompt; confirm proceeding is possible. Reset the throwaway commit afterwards.
  - [ ] **Unknown distance:** in the scratch copy, set `gitCommitHash` to a syntactically valid but
        unknown hash — expect drift reported with unknown distance and a stated reason, and **no
        fabricated number**.
  - [ ] **No git:** copy graph and skill inputs to a scratch directory that is not a repository —
        expect an explicit skip statement in console output.
  - [ ] **No meta.json:** remove it in the scratch copy — expect the distinct "cannot run" reason.
  - [ ] Success: all five paths behave as specified; the console output states the outcome in every
        case.
  - [ ] **Commit checkpoint:** commit the preflight sections (2.1–3.1) once verified.

---

## Task 4: Preflight — `.gitignore` hygiene

- [ ] **4.1 Author the hygiene step** — Effort: 2/5
  - [ ] Specify that hygiene runs per-run, at the start, **before any document is written**.
  - [ ] Specify the semantic idempotency test:
        `git check-ignore -q .understand-anything/.trash-probe/`. Exit 0 → already covered by some
        rule (including a broader `.understand-anything/` ignore) → report "already ignored" and
        write nothing. Note in the text that the probe path need not exist for the check to work.
  - [ ] Specify the append (creating `.gitignore` if absent): a comment line marking it
        squadron-managed, then `.understand-anything/.trash-*/`.
  - [ ] Specify re-running the check to confirm, then reporting the addition.
  - [ ] Specify failure handling: read-only or permission-denied → report that the entry could not
        be added **and why**, then continue (non-fatal). Outside a git repository → report that
        hygiene does not apply. Never proceed claiming a write succeeded when it did not.
  - [ ] State what is **not** ignored and why: `knowledge-graph.json`, `meta.json`, `config.json`,
        and `.understandignore` stay tracked as durable project knowledge. Squadron never deletes
        trash directories — the upstream purge owns that lifecycle.
  - [ ] Success: the section specifies a semantic check (not a pattern grep), and every failure
        path is reported rather than swallowed.

- [ ] **4.2 Verify hygiene idempotency and failure paths** — Effort: 2/5
  - [ ] **First run (this repo has no entry today):** run — expect `.gitignore` to gain the entry
        exactly once, reported.
  - [ ] **Second run:** run again — expect "already ignored"; confirm `git diff .gitignore` is
        empty and there is no duplicate line.
  - [ ] **Broader ignore accepted:** temporarily replace the entry with `.understand-anything/`,
        run — expect no addition. Restore the original entry afterwards.
  - [ ] **Read-only:** `chmod 444 .gitignore`, run — expect a reported non-fatal failure **and a
        completed run**. `chmod 644 .gitignore` to restore.
  - [ ] **Not a repository:** run in a non-repo scratch directory — expect the does-not-apply
        report.
  - [ ] Success: all five paths behave as specified; no duplicate `.gitignore` line exists after
        repeated runs.
  - [ ] **Commit checkpoint:** commit the hygiene section and the resulting `.gitignore` entry.

---

## Task 5: Document conventions

- [ ] **5.1 Author the gap-marker syntax** — Effort: 2/5
  - [ ] Specify the marker: `[GAP: {what is missing} — {which input would supply it}]`, placed in
        the body exactly where the content would have appeared.
  - [ ] Specify `[INFERRED]` as the retained sibling convention from
        `user/reference/analyze-codebase-prompt.md` — a prefix for claims from indirect evidence.
        State that 361's structural output should not need it (all claims trace to named fields)
        and that its use in the deepened analysis is 362's to govern.
  - [ ] Specify the three rules: markers appear in the body at the point of absence **and** are
        listed in the provenance block; a document with gap markers is a valid output, not a
        failure; a gap is never filled with plausible prose.
  - [ ] Success: a junior AI can tell from this section alone which marker to use and where both
        copies of it go.

- [ ] **5.2 Author the provenance block format** — Effort: 3/5
  - [ ] Specify placement: a `## Provenance` section immediately after the H1 title, before all
        content, as body prose — **not** frontmatter. Include the reason: frontmatter is
        schema-validated and invisible to a reader, and the failure this guards against is a human
        trusting a stale or partly-invented document.
  - [ ] Author the line set per the design: generated-by, generated-date, source (with node/edge/
        layer/tour counts), graph identity (`gitCommitHash`, `lastAnalyzedAt`), staleness state,
        section sourcing, flagged gaps, review state.
  - [ ] Specify that the block obeys its own gap-marker rule — a missing `meta.json` yields a
        `[GAP: ...]` in the graph-identity line, consistent with the staleness skip line.
  - [ ] Specify that the review-state line always states the document is a machine-generated draft
        with no human review. This is what makes `status: not_started` legible on a generated draft.
  - [ ] Note that capability (b) (slice 365) reuses this shape with **Source** naming the concept
        and initiative-plan paths instead.
  - [ ] Success: every line resolves from real data or carries a gap marker; no line can be silently
        omitted.

- [ ] **5.3 Author the generated-document conventions** — Effort: 2/5
  - [ ] Specify the output path
        `project-documents/user/analysis/{index}-analysis.codebase-comprehension.md`.
  - [ ] Specify index selection: lowest unused index ≥ 940, found by scanning existing `9nn-`
        filenames in `user/analysis/`. Each run takes a **new** index — runs are independent
        samples, matching the existing `940`/`941`/`942` series. State that overflow past 949 is
        sanctioned by the architecture.
  - [ ] Specify the frontmatter fields: `docType: analysis`, `project`, `topic:
        codebase-comprehension`, `dateCreated`, `dateUpdated`, `status: not_started`, `model`.
  - [ ] **`model:` must be populated with the id of the model actually generating the document** —
        never left empty, never a placeholder, never a hardcoded example. `cf validate frontmatter`
        is permissive here and will pass on a placeholder, so the skill text must state the
        requirement rather than relying on the gate to enforce it. Do not put an example model id
        in the skill's instruction text: if the generating model cannot determine its own id, it
        must say so rather than reach for the nearest plausible token.
  - [ ] Record the verified fact from Task 1.1: `cf validate frontmatter` accepts `model:` on an
        `analysis` document (confirmed against `942-analysis.tech-debt-audit.md`).
  - [ ] State why `status: not_started` is correct rather than a review-pending value: the enum has
        no `needs_review` member, `complete` would assert a review that has not happened, and review
        state is carried by the provenance block.
  - [ ] Success: the conventions produce a document that passes `cf validate frontmatter` and does
        not collide with an existing index.

---

## Task 6: Comprehension analysis flow

- [ ] **6.1 Author the comprehension flow at proving depth** — Effort: 3/5
  - [ ] Specify that the flow runs preflight (Tasks 2–4) first, then extracts and writes.
  - [ ] Author exactly four sections, each naming its source graph field inline:
    1. **Layer architecture** — each layer's name, description, and file count, from `layers[]`.
    2. **Complexity hotspots** — top file-level nodes by `complexity`, with `filePath` and
       `summary`.
    3. **Suggested reading order** — `tour[]` step titles in order, or a gap marker if `tour` is
       empty.
    4. **Dependency observations** — edge-type counts and the strongest inter-layer
       `imports`/`depends_on` connections, from `edges[]`.
  - [ ] State explicitly that section depth, ordering, fallbacks, and any **additional** sections
        are slice 362's scope, and that 361 must not grow this list.
  - [ ] Specify that any argument other than the comprehension default is treated as unrecognized
        (the concept and candidates flows are 363/364).
  - [ ] Success: the flow exercises every contract element — validation, staleness, hygiene,
        provenance, gap markers, index selection — end to end.

- [ ] **6.2 Verify the happy path against this repo** — Effort: 3/5
  - [ ] Run the full flow against this repo using the real graph.
  - [ ] Success: a new `user/analysis/{index}-analysis.codebase-comprehension.md` exists at the
        expected next index.
  - [ ] Success: the provenance block sits directly under the H1 title, above all content.
  - [ ] Success: every structural claim names the graph field it derives from.
  - [ ] **Spot-check two claims against the real repo** — pick one layer and one complexity hotspot
        and confirm they are true of the actual codebase. A claim that does not hold is a defect,
        not a cosmetic issue.
  - [ ] Success: `cf validate frontmatter` passes on the generated file.
  - [ ] Success: `model:` holds a real model id, not a placeholder or empty value. Check this by
        reading the field — the gate is permissive and will not catch it.
  - [ ] Success: a second run produces a **new** index rather than overwriting the first.

- [ ] **6.3 Verify at least one gap marker is exercised** — Effort: 1/5
  - [ ] If the real graph produced a gap marker naturally (e.g. a node lacking `complexity`),
        confirm it appears both in the body and in the provenance block's flagged-gaps line.
  - [ ] If the real graph supplied everything, use the tampered `.tour = []` scratch copy from Task
        2.3 to produce the marker, and confirm both placements there.
  - [ ] Success: at least one genuine `[GAP: ...]` marker is demonstrated in both required
        locations.
  - [ ] **Commit checkpoint:** commit the conventions and flow sections plus the generated sample
        document once verified.

---

## Task 7: Close-out

- [ ] **7.1 Full-slice verification pass** — Effort: 2/5
  - [ ] Walk the design's Verification Walkthrough steps 1–8 in order and confirm each produces its
        stated outcome. Steps map to tasks: 1→6.2, 2–4→4.2, 5→2.3, 6→2.3, 7→3.2, 8→1.3.
  - [ ] Confirm the slice's ten Success Criteria are each satisfied, checking them against actual
        run output rather than the authored text.
  - [ ] Confirm no file under `src/squadron/` changed: `git diff --stat main -- src/` is empty.
  - [ ] Confirm the only new non-document file is `commands/analysis/understand.md`.
  - [ ] Run `uv run ruff format` and `uv run ruff check` (note: bare `ruff` is not on PATH; use
        `uv run`). No Python changed, so these should be no-ops — run them to confirm that.
  - [ ] Run the full test suite once and confirm it is green with no new skips.

- [ ] **7.2 Mark the slice complete and record the session** — Effort: 1/5
  - [ ] Check off entry 1 (361) in `360-slices.document-intelligence.md`.
  - [ ] Set `status: complete` in the slice design's frontmatter.
  - [ ] Write the DEVLOG entry per `prompt.ai-project.system.md` → Session State Summary. Record any
        observed divergence between the real graph's shape and the architecture's documented
        contract, since that is the initiative's standing risk.
  - [ ] **Commit checkpoint:** final commit; merge the slice branch into `main` (no integration
        branch is configured).
