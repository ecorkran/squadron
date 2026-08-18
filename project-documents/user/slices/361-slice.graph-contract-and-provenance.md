---
docType: slice-design
slice: graph-contract-and-provenance
project: squadron
parent: 360-slices.document-intelligence.md
dependencies: [340]
interfaces: [362, 363, 364, 366]
dateCreated: 20260818
dateUpdated: 20260818
status: complete
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

Run from the squadron repo root. **Verified 20260818** on branch `361-slice.graph-contract-and-provenance`
against a real v2.8.1 graph (925 nodes, 2184 edges, 10 layers, 15 tour steps). Every command and
output below is transcribed from an actual run.

**Prerequisite: a real graph.** `.understand-anything/knowledge-graph.json` did not exist at
implementation time; it was generated by running the marketplace plugin's `/understand` once, in a
separate CLI session (it is token-expensive and writes to the working tree). Confirm with:

```
jq -r 'keys[]' .understand-anything/knowledge-graph.json
# -> edges  layers  nodes  project  tour  version
```

**Scratch setup used by steps 5-7** (never tamper with the repo's real graph):

```
mkdir -p "$S/real/.understand-anything" "$S/absent"
cp .understand-anything/{knowledge-graph.json,meta.json} "$S/real/.understand-anything/"
cd "$S/real/.understand-anything"
jq 'del(.layers)' knowledge-graph.json > kg-missing-key.json
jq '.layers = []'  knowledge-graph.json > kg-empty-layers.json
jq '.tour = []'    knowledge-graph.json > kg-empty-tour.json
head -c 4000       knowledge-graph.json > kg-truncated.json
```

1. **Happy path.** Invoke the skill (pre-366: open `commands/analysis/understand.md` in a Claude
   Code session and instruct "execute this skill's comprehension analysis flow against this repo").

   Preflight reported, in order: `jq: present`, `graph: present`, `parse: OK`, `shape: OK`,
   `counts -> nodes: 925  edges: 2184  layers: 10  tour: 15`, `staleness: 3 commits behind HEAD`,
   `hygiene: already ignored`. Wrote
   `project-documents/user/analysis/943-analysis.codebase-comprehension.md` (940-942 already
   existed).

   Confirmed: `## Provenance` at line 13 sits directly under the H1 at line 11, above all content;
   every section names its graph field inline; `cf validate frontmatter` returns
   `No inconsistencies found (1 file checked)`; `model:` reads back as a real id, not a placeholder.

   **Spot-checks (both hold).** The CLI Surface layer description claims "27 `sq` sub-commands" —
   `ls src/squadron/cli/commands/*.py | wc -l` returns exactly `27`.
   `src/squadron/pipeline/sdk_session.py`, rated `complex`, is a real 288-line module whose own
   docstring ("Manages a single ClaudeSDKClient connection across all dispatch steps in a pipeline
   run") matches the graph summary.

   **Caveat — staleness during implementation.** Each commit in this slice moves HEAD past the
   graph's `gitCommitHash`, so a run late in the slice legitimately reports "N commits behind HEAD".
   That is the check working. Confirm the intervening commits touch no analyzed source before
   proceeding, and record the decision in the provenance block (the 943 sample does exactly this).

2. **Idempotent hygiene and index advance.** Run again.

   ```
   git check-ignore -q .understand-anything/.trash-probe/   # exit 0 -> "already ignored"
   git diff .gitignore                                      # -> empty
   grep -c 'understand-anything/.trash' .gitignore          # -> 1  (no duplicate line)
   ```

   With 943 present, the next run selects **944**; 943 is never overwritten.

3. **Broader ignore accepted.** Replace the entry with `.understand-anything/`, run:
   `git check-ignore -q .understand-anything/.trash-probe/` still exits 0, so no addition is made.
   This is the point of the semantic check — a pattern grep would have appended a redundant entry.
   Restore the original entry afterwards.

4. **Read-only `.gitignore`.** `chmod 444 .gitignore`, run with the entry absent. The append fails
   with `permission denied`, the skill reports
   `could not update .gitignore: permission denied (file is read-only)`, and **the run continues**
   (non-fatal). `chmod 644 .gitignore` to restore.

5. **Malformed graph.** Against the scratch copies:

   ```
   jq -r '["nodes","edges","layers","tour","version","project"] - (keys)
          | if length>0 then "MALFORMED: missing key(s): "+join(", ") else "keys OK" end' kg-missing-key.json
   # -> MALFORMED: missing key(s): layers
   ```

   The message is accompanied by graph identity (`version: 1.0.0`, `gitCommitHash`,
   `lastAnalyzedAt`), and no document is written. `.layers = []` produces the same rejection via the
   empty-array check. `.tour = []` **warns and proceeds**, and the written document carries a
   `[GAP: ...]` marker in **both** the Suggested reading order section and the provenance block's
   flagged-gaps line (2 occurrences).

6. **Absent graph.** In `$S/absent` (no `.understand-anything/`), the run reports the absent-graph
   message naming the checked path and pointing at the plugin's `/understand`. Confirmed textually
   distinct from step 5's malformed message and from the unparseable message
   (`jq empty kg-truncated.json` -> `parse error: Unfinished string at EOF at line 123, column 30`).

7. **No git.** In the non-repo scratch directory, `git rev-parse --show-toplevel` fails, and the run
   reports `SKIP — not a git repository; staleness cannot run` in console output **and** records it
   in the written document's provenance block as
   `**Staleness:** SKIPPED — this directory is not a git repository...`. Hygiene separately reports
   `does not apply — not a git repository`. Two further distinct skip reasons were confirmed:
   `meta.json` absent, and `meta.json` present but carrying no `gitCommitHash`.

8. **Installation.**

   ```
   uv run sq skills install analysis
   # -> Installed pack 'analysis': 2 file(s) -> /Users/<user>/.claude/commands/analysis
   uv run pytest tests/skills/     # -> 62 passed
   ```

   Both `tech-debt-audit.md` and `understand.md` land in the destination, with no installer change.

   **Caveat — use `uv run sq`, not bare `sq`.** A globally installed `sq` (uv tool, e.g.
   `~/.local/bin/sq`) resolves its bundled pack from its own snapshot and will report `1 file(s)`,
   silently ignoring the working tree. `uv run sq` exercises the working-tree installer. This is an
   environment artifact, not a defect: calling `install_pack()` directly from the working-tree module
   writes both files.

**Full-slice checks.** `git diff --stat main -- src/` is empty; the only new non-document file is
`commands/analysis/understand.md` (plus the intended `.gitignore` entry).
`uv run ruff format --check .` reports `446 files already formatted` and `uv run ruff check` reports
`All checks passed!` (no Python changed — these confirm that). Full suite: **3021 passed, 2 skipped**
(the 2 skips are pre-existing).

**Divergence found during verification.** The graph's `complexity` field is an **ordinal string**
(`simple` 83 / `moderate` 76 / `complex` 42 across 201 file-level nodes), not the numeric sort key
this design assumed — `sort_by(-.complexity)` fails outright with
`string ("simple") cannot be negated`. The flow's Complexity hotspots section selects the top tier
instead. The field's name and presence match the architecture's documented contract, so this is a
narrowing rather than a contract change; it did not require escalation, and is recorded for slice 362.
Separately, `layers[].nodeIds` mixes file, function, and class nodes, so a file count requires
intersecting with `type == "file"` rather than taking `nodeIds | length`.

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
