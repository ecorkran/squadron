---
docType: slice-design
slice: graph-contract-and-provenance
project: squadron
parent: 360-slices.document-intelligence.md
dependencies: [340]
interfaces: [362, 363, 364, 366]
dateCreated: 20260818
dateUpdated: 20260818
status: not_started
---

# Slice Design: Graph Contract and Provenance

## Overview

Establish the shared machinery every capability-(a) skill depends on: locating and validating the
`understand-anything` knowledge graph, the staleness check, `.gitignore` hygiene for the plugin's
scratch directories, the provenance block format, and the gap-marker syntax. Deliver it inside the
smallest real consumer — a comprehension analysis output producing structural findings only — so the
contract is proven end to end against a real graph, not specified in the abstract.

Everything in this slice is markdown skill content. No Python is added.

## Value

Architectural enablement. Slices 362, 363, and 364 all read the graph through this contract; the
failure modes named in the architecture (missing graph, malformed graph, stale graph, unavailable
git, unwritable `.gitignore`) are implemented once. This slice also front-loads the initiative's
only external risk: the upstream plugin's output shape is observed, not guaranteed, and proving the
contract against a real graph surfaces drift before three skills depend on it.

## Technical Scope

**Included:**
- New skill file `commands/analysis/understand.md` containing:
  - the **Graph Contract** protocol sections (location, validation, staleness, hygiene) that later
    slices execute unchanged;
  - the **document conventions** sections (provenance block format, gap-marker syntax, index
    selection) that later slices reuse;
  - the **comprehension analysis** flow at proving-consumer depth: structural findings only, no
    interview, no concept.
- The generated artifact contract: `{index}-analysis.codebase-comprehension.md` in
  `user/analysis/`, `docType: analysis`, `status: not_started`, provenance block above content.

**Excluded (owned elsewhere):**
- Deep extraction mapping (which graph fields feed which analysis sections, in what order, with
  what fallbacks) — slice 362. The 361 comprehension output is deliberately shallow.
- Concept generation and interview — slice 363. Initiative candidates — slice 364.
- Dispatcher routing (`commands/sq/analysis.md` edits), README, plugin-absent install guidance —
  slice 366. Until 366 lands, the skill is exercised by invoking the file directly.
- Any change to `_install_prefix()`, the installer, manifests, or `src/squadron/`.

## Dependencies

### Prerequisites
- **[340]** — bundled `analysis` pack and `sq skills install analysis` copy-all-`*.md` behavior.
  Adding `understand.md` to `commands/analysis/` is sufficient for installation; no installer
  change.
- **External:** `understand-anything` marketplace plugin output at
  `$PROJECT_ROOT/.understand-anything/`. The skill consumes the output only; the plugin itself is
  never invoked, wrapped, or installed by squadron.

### Interfaces Required
- Upstream output contract per the architecture: `knowledge-graph.json` with top-level `project`,
  `nodes[]`, `edges[]`, `layers[]`, `tour[]`; `meta.json` with `gitCommitHash`, `lastAnalyzedAt`.

## Architecture

### Component Structure

One file, `commands/analysis/understand.md`, organized so the contract is a named, reusable block:

1. **Preflight: Graph Contract** — locate, validate, staleness, hygiene. Written as a
   self-contained protocol section that slices 362-364 execute verbatim at the start of every
   flow. It lives in this file (not a separate fragment file) because `_install_prefix()` installs
   every `*.md` in the pack directory as its own skill — a fragment file would surface as a bogus
   installable skill.
2. **Document Conventions** — provenance block format, gap-marker syntax, index selection. Slice
   365 (overview), which never reads a graph, copies these conventions rather than referencing
   this file, since a first-party `commands/sq/` command cannot assume the analysis pack is
   installed.
3. **Flow: Comprehension Analysis** — the proving consumer. Later slices add sibling flow
   sections (concept, candidates) selected by argument; this slice defines only the one flow and
   treats any argument other than the comprehension default as unrecognized.

### Data Flow

```
.understand-anything/knowledge-graph.json ─┐
.understand-anything/meta.json ────────────┤→ preflight (validate, staleness) ─┐
.gitignore ←── hygiene write ──────────────┘                                   │
                                                                               ▼
                                    selective jq extraction (layers, file-level nodes, tour, edges)
                                                                               ▼
                       user/analysis/{index}-analysis.codebase-comprehension.md
                       (frontmatter → provenance block → structural findings)
```

## Technical Decisions

### Graph location and read discipline

The graph root is `$PROJECT_ROOT/.understand-anything/` where `$PROJECT_ROOT` is the current
working directory's repo root (`git rev-parse --show-toplevel`, falling back to `pwd` outside a
repository). The graph is never loaded whole into context. All reads go through `jq` selections
that return only the requested fields — key presence, array lengths, `layers[]`, file-level nodes
(`.nodes[] | select(.type == "file" or ...)` with `id`, `filePath`, `summary`, `complexity` only),
`tour[]` order/title/nodeIds, and edge aggregates. Function- and class-level nodes are never read.

`jq` is the extraction tool because it is already assumed by squadron's environment tooling and
does exactly this job without adding code. If `jq` is unavailable the skill stops and says so —
it does not fall back to reading the raw file into context.

### Validation: absence vs malformation (two distinct failures)

Checked in order, each with its own message:

1. **Absent.** `.understand-anything/knowledge-graph.json` does not exist → stop with an
   actionable message: the graph has not been generated; run `/understand` (the marketplace
   plugin) first. This message must not speculate about whether the plugin is installed — that
   detection and install guidance is slice 366 scope.
2. **Unparseable.** `jq empty` fails → stop, naming the file and reporting it is not valid JSON.
3. **Malformed.** Any required top-level key (`project`, `nodes`, `edges`, `layers`, `tour`)
   missing or not of the expected type, or any of `nodes`/`edges`/`layers` an empty array → stop
   with an error naming each absent/mistyped/empty key and reporting the graph's version identity
   (`meta.json` `lastAnalyzedAt` and `gitCommitHash` when readable) so upstream drift is
   diagnosable. An empty `tour` is tolerated with a warning (it degrades one signal, not the
   document); empty `nodes`/`edges`/`layers` are rejected because nothing useful can be written
   from them.

A renamed upstream field must surface as failure 3, never as a silently thinner document.

### Staleness: warn with distance, never block

- Read `gitCommitHash` from `meta.json`. If `meta.json` is missing or the field is absent, report
  that the staleness check cannot run for that reason and record the skip in provenance.
- If `git` is unavailable or the directory is not a repository: announce the skip explicitly in
  console output and record it in the provenance block. Never skip silently.
- Otherwise compare against `git rev-parse HEAD`:
  - equal → record "matched HEAD";
  - differing and the hash is a known ancestor → report distance via
    `git rev-list --count {hash}..HEAD` as "N commits behind HEAD";
  - differing and the hash unknown to the repo (rebase, amend, shallow clone) → report drift with
    unknown distance, stating why.
- On any drift, state the finding and ask the PM: proceed on the stale graph, or stop to re-run
  `/understand`. Proceeding is recorded in provenance as a PM choice. The check never blocks on
  its own.

### `.gitignore` hygiene: semantic idempotency via `git check-ignore`

Performed per-run, at the start, before any document is written:

1. Semantic test: `git check-ignore -q .understand-anything/.trash-probe/`. Exit 0 means some
   existing rule (including a broader `.understand-anything/` ignore) already covers trash
   directories — report "already ignored", write nothing.
2. Otherwise append to `.gitignore` (creating it if absent):

   ```
   # understand-anything transient scratch (squadron-managed)
   .understand-anything/.trash-*/
   ```

3. Re-run the check to confirm, and report the addition.
4. Failure (read-only file, permission denied) → report the entry could not be added and why, then
   continue. Outside a git repository, report the hygiene step does not apply. Non-fatal, never
   silent, and never proceed claiming the write succeeded when it did not.

`git check-ignore` is the idempotency test because it evaluates gitignore semantics exactly as git
does — no pattern-grep false negatives against equivalent spellings. The probe path does not need
to exist for the check to work. Squadron never deletes trash directories; the upstream purge owns
that lifecycle.

### Gap-marker syntax (settled here, used by every generated document)

Extends the retained `analyze-codebase-prompt.md` convention (`[INFERRED]`) with a sibling marker
rather than competing with it:

- `[GAP: {what is missing} — {which input would supply it}]` — placed in the body exactly where
  the content would have appeared. Examples:
  `[GAP: tour ordering absent from graph — re-run /understand to regenerate tour]`,
  `[GAP: target users unknown — interview declined]` (slice 363 usage).
- `[INFERRED]` — prefix for a claim derived from indirect evidence rather than a named field.
  Defined here for the family of generated documents; the 361 comprehension output should not
  need it (structural claims all trace to named fields), and 362 governs its use in the deepened
  analysis.

Rules: gap markers appear in the body at the point of absence **and** are listed in the provenance
block; a document with gap markers is a valid output, not a failure; a gap is never filled with
plausible prose.

### Provenance block format

Placed immediately after the H1 title, before all content, as a `## Provenance` section of body
prose (not frontmatter — frontmatter is schema-validated and invisible to a reader; this warning
exists for humans):

```markdown
## Provenance

- **Generated by:** squadron `understand` skill — comprehension analysis
- **Generated:** {YYYYMMDD}
- **Source:** `.understand-anything/knowledge-graph.json` ({n} nodes, {n} edges, {n} layers, {n} tour steps)
- **Graph identity:** `gitCommitHash` {hash-or-gap}, `lastAnalyzedAt` {timestamp-or-gap}
- **Staleness:** {matched HEAD | {N} commits behind HEAD — proceeded on PM choice | check skipped: {reason}}
- **Section sourcing:** {one line per section: section → named graph fields (or interview, for later slices)}
- **Flagged gaps:** {each gap marker in the document, or "none"}
- **Review state:** machine-generated draft; no human review has occurred
```

Every line resolves from real data or carries a gap marker — the format itself obeys the
gap-marker rule (e.g. a missing `meta.json` yields `[GAP: ...]` in Graph identity, matching the
skipped staleness line). Capability (b) (slice 365) uses the same shape with **Source** naming the
concept/initiative-plan paths instead.

### Generated document conventions

- Path: `project-documents/user/analysis/{index}-analysis.codebase-comprehension.md`.
- Index: lowest unused index ≥ 940 in `user/analysis/` (scan existing `9nn-` filenames). Each run
  takes a new index — runs are independent samples, matching the `940/941/942` tech-debt-audit
  series. Overflow past 949 is sanctioned by the architecture.
- Frontmatter, matching the existing generated-analysis shape:

  ```yaml
  ---
  docType: analysis
  project: {project}
  topic: codebase-comprehension
  dateCreated: {YYYYMMDD}
  dateUpdated: {YYYYMMDD}
  status: not_started
  model: {generating model id}
  ---
  ```

  `status: not_started` is deliberate: review state lives in the provenance block, per the
  architecture's resolved decision.

### Comprehension output at proving depth

The 361 document exercises every contract element with minimal extraction — one section per major
graph area, each naming its source field inline:

1. **Layer architecture** — each layer's name, description, and file count, from `layers[]`.
2. **Complexity hotspots** — top file-level nodes by `complexity`, with `filePath` and `summary`.
3. **Suggested reading order** — `tour[]` step titles in order (or a gap marker if `tour` is
   empty).
4. **Dependency observations** — edge-type counts and the strongest inter-layer `imports`/
   `depends_on` connections, from `edges[]`.

Section depth, ordering, fallbacks, and any additional sections are 362 scope; 361 must not grow
this list. At least one genuinely absent field encountered during the proving run is emitted as a
gap marker (an empty `tour` or a node lacking `complexity` are the likely candidates; if the real
graph supplies everything, the walkthrough's tampered-graph run demonstrates the marker instead).

## Integration Points

### Provides to Other Slices
- **362, 363, 364:** the Preflight Graph Contract and Document Conventions sections of
  `understand.md`, executed verbatim; the comprehension flow 362 deepens in place.
- **365:** the provenance block shape and gap-marker syntax as conventions to copy (no runtime
  dependency in either direction).
- **366:** a working skill file whose argument surface (`understand`, comprehension default) the
  dispatcher edits will route to.

### Consumes from Other Slices
- **340:** pack directory and install behavior, unchanged.
- Upstream plugin output. Failure handling for absent/malformed/stale input is this slice's core
  content, specified above.

## Success Criteria

1. A graph missing any required top-level key produces an error naming the absent key(s) and the
   graph's version identity; empty `nodes`/`edges`/`layers` are rejected the same way; empty
   `tour` warns but proceeds.
2. An absent graph produces a different, actionable message pointing at `/understand`.
3. An unparseable graph file produces a third distinct message naming the file.
4. Staleness drift is reported with commit distance (or explicit unknown-distance reason) and does
   not block; proceeding is a recorded PM choice.
5. With git unavailable or outside a repository, the staleness skip is stated in both console
   output and the provenance block.
6. `.gitignore` gains `.understand-anything/.trash-*/` exactly once across repeated runs; a
   pre-existing broader `.understand-anything/` ignore is accepted without a second entry
   (verified via `git check-ignore` semantics); a read-only `.gitignore` yields a reported
   non-fatal failure and the run continues.
7. `{index}-analysis.codebase-comprehension.md` is written with `docType: analysis`,
   `status: not_started`, the frontmatter shape above, and a provenance block immediately after
   the title.
8. Gap-marker syntax is documented in the skill and at least one genuinely absent field appears as
   a `[GAP: ...]` marker across the walkthrough runs.
9. The whole graph is never read into context; every extraction is a field-scoped `jq` selection.
10. No file under `src/squadron/` changes; the only new file outside `project-documents/` is
    `commands/analysis/understand.md`.

## Verification Walkthrough

Run from the squadron repo root. Prerequisite: a real graph — run the marketplace plugin's
`/understand` once if `.understand-anything/knowledge-graph.json` does not exist.

1. **Happy path.** Invoke the skill (pre-366: open `commands/analysis/understand.md` in a Claude
   Code session and instruct "execute this skill's comprehension analysis flow against this
   repo"). Expect, in order: a hygiene report (entry added, or already ignored), a staleness
   report naming HEAD state, and a new `user/analysis/{index}-analysis.codebase-comprehension.md`.
   Confirm the provenance block sits directly under the title and every structural claim names its
   graph field; spot-check two claims (a layer, a hotspot) against the real repo.
2. **Idempotent hygiene.** Run again. Expect "already ignored" and no second `.gitignore` line;
   `git diff .gitignore` is empty. The new document takes the next index.
3. **Broader ignore accepted.** Temporarily replace the entry with `.understand-anything/` in
   `.gitignore`, run, expect no addition; restore afterwards.
4. **Read-only `.gitignore`.** `chmod 444 .gitignore`, run, expect a reported non-fatal failure
   and a completed document; `chmod 644 .gitignore` to restore.
5. **Malformed graph.** Copy the repo to scratch, `jq 'del(.layers)'` the copy's graph in place,
   run there; expect a loud error naming `layers` and the graph identity, and no document written.
   Repeat with `.layers = []` — same rejection; with `.tour = []` — warning plus a completed
   document containing a `[GAP: ...]` marker in Suggested reading order.
6. **Absent graph.** In a scratch directory with no `.understand-anything/`, run; expect the
   run-`/understand`-first message, distinct from case 5's.
7. **No git.** Copy graph + skill inputs to a scratch directory that is not a repository, run;
   expect an explicit staleness-skip statement in console output and in the written document's
   provenance block, and a hygiene does-not-apply report.
8. **Installation.** `sq skills install analysis`; receipt lists both `tech-debt-audit.md` and
   `understand.md` with no installer change. Existing skills tests remain green.

## Risk Assessment

**Upstream contract drift** (the initiative's stated medium risk): the plugin is actively
developed and its output shape is observed, not guaranteed. Mitigated by validating shape before
every read, failing loudly with the graph's version identity on any missing/mistyped key, and
proving the contract against a real v2.8.1 graph in the walkthrough. If the walkthrough's real
graph does not match the architecture's documented shape, stop and raise to the PM before
proceeding — that is a contract change, not an implementation detail.

## Implementation Notes

Suggested order: skill preflight sections (validation → staleness → hygiene) → document
conventions (gap marker, provenance, index selection) → comprehension flow → walkthrough runs 1-8,
fixing as found. Testing is the walkthrough itself; this slice adds no Python and therefore no
unit tests, but run the existing skills test suite once to confirm the pack install path is
undisturbed.
