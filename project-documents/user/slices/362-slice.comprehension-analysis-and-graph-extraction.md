---
docType: slice-design
slice: comprehension-analysis-and-graph-extraction
project: squadron
parent: 360-slices.document-intelligence.md
dependencies: [361]
interfaces: [363, 364]
dateCreated: 20260818
dateUpdated: 20260819
status: in_progress
---

# Slice Design: Comprehension Analysis and Graph Extraction

## Overview

Slice 361 proved the graph contract end to end at deliberately shallow depth. This slice turns that
proving stub into the real comprehension document and settles the extraction strategy the
architecture left open: **which graph field feeds which section, in what order, with what fallback
when the field is absent.**

Everything here is markdown edits to the existing `commands/analysis/understand.md`. No Python is
added and no new file is created outside `project-documents/`.

Three corrections to the 361 contract are in scope and are the reason this slice is not merely
additive — two are extraction defects found by probing the real v2.8.1 graph, and the third is a
misleading note corrected against the upstream plugin's source. All three are documented under
**Technical Decisions → Corrections to the 361 contract**.

## Value

Developer value: a usable structural read of an unfamiliar codebase, in squadron's own document
conventions, with no human interview. This is also the first slice in initiative 360 that *consumes*
the 361 contract rather than defining it, so it is the slice that tests whether the contract is
actually reusable — the initiative's stated premise.

Architecturally, the extraction mapping defined here is reused verbatim by slice 363 (concept, whose
extract-then-ask rule needs a per-section field mapping to attempt first) and slice 364 (initiative
candidates, which derives candidates from `layers[]` and complexity clusters).

## Technical Scope

**Included** — all within `commands/analysis/understand.md`:

- A **field-to-section extraction mapping** stated as a table: every section names its source
  fields, its ordering rule, and its fallback when the fields are absent or empty.
- **Corrections** to three claims in the 361 contract: two the real graph contradicts (layer node
  composition; the definition of "file-level") and one whose wording misstates when
  `fingerprints.json` churns.
- **New sections** in the comprehension flow that the corrected reading makes sourceable:
  project identity, entry points, coverage and scope limits. Their grounding against the
  architecture's four-section shape is stated below under **Section count vs the architecture**.
- **Deepened existing sections** — layer architecture, complexity hotspots, reading order,
  dependency observations — each gaining an explicit ordering rule and fallback.
- The **`[INFERRED]` governance decision** and the recorded decision on
  `analyze-codebase-prompt.md` reuse (the parent architecture's open question).
- The three fields 361 explicitly deferred: `config.json`, `.understandignore`, and `meta.json`'s
  `analyzedFiles`.

**Excluded (owned elsewhere):**

- Interview, concept generation — slice 363. This slice asks the PM nothing beyond the staleness
  decision the 361 contract already defines.
- Initiative candidates — slice 364.
- Dispatcher routing, README, plugin-absent install guidance — slice 366. The skill is still
  exercised by invoking the file directly.
- Any change to `src/squadron/`, the installer, manifests, or the preflight contract's
  validation/staleness/hygiene behavior. Preflight is executed unchanged.

## Dependencies

### Prerequisites

- **[361]** — the Preflight Graph Contract, provenance block, gap-marker syntax, and generated
  document conventions, all executed unchanged.
- **External:** the same upstream `understand-anything` output at `$PROJECT_ROOT/.understand-anything/`.

### Interfaces Required

Beyond the 361 contract, this slice consumes graph fields 361 did not read. All were verified
present in the real v2.8.1 graph during this design (see **Verified graph facts**).

| Field | Used for |
|---|---|
| `project.name`, `.description`, `.languages`, `.frameworks` | Project identity section |
| `nodes[].tags` | Entry points, section grouping |
| `nodes[].languageNotes` | Complexity hotspot annotation (partial coverage) |
| `tour[].description` | Reading-order annotation |
| `edges[].weight`, `.direction` | Dependency ordering |
| `meta.json` `analyzedFiles` | Coverage section |
| `config.json`, `.understandignore` | Scope-limits section |

## Verified graph facts

Probed against this repo's real graph (v2.8.1, `gitCommitHash` `1bfbca1`, 925 nodes / 2184 edges /
10 layers / 15 tour steps) while writing this design. These are measurements, not assumptions, and
the design's decisions rest on them.

| Fact | Value |
|---|---|
| Node types | `function` 476, `class` 211, `file` 201, `pipeline` 20, `config` 17 |
| Nodes carrying `filePath` + `complexity` | all `file`, `config`, `pipeline` — 238 total |
| `meta.json` `analyzedFiles` | **238** — exactly `file` + `config` + `pipeline` |
| Sum of all `layers[].nodeIds` lengths | **238** |
| Type composition of every `layers[].nodeIds` entry | `file` 201, `config` 17, `pipeline` 20 — **zero** function or class |
| File-level nodes in more than one layer | **0** |
| `tags` coverage on file nodes | 201/201; `entry-point` appears on 27 |
| `languageNotes` coverage on file nodes | 81/201 (40%) |
| `tour[].languageLesson` populated | 9/15 |
| `config.json` contents | `{"outputLanguage":"en"}` only |
| `.understandignore` active (uncommented) lines | 17 |
| `complexity` values across all 238 file-level nodes | `simple` 106, `moderate` 89, `complex` 43 |
| Node `id` format | `<type>:<filePath>[:<name>]` — second field equals `filePath` for **all 925** nodes; no `filePath` contains a colon |
| Edges with an endpoint absent from `nodes` | **0** (of 2184) |
| `imports`/`depends_on` edges touching a function/class endpoint | **16** of 610 (2.6%) |

## Technical Decisions

### Corrections to the 361 contract

All three corrections change existing text in `understand.md`. None is an upstream contract change —
in every case the graph and the plugin match what the *architecture* documented, and the 361 skill
text is what diverged, so these are defect fixes inside squadron, not escalations. Corrections 1 and
2 change what the flow extracts; correction 3 changes only a note's wording.

**Correction 1 — `layers[].nodeIds` does not mix function and class nodes.**

The 361 skill states that `nodeIds` mixes file, function, and class nodes and instructs intersecting
with `type == "file"` to get a file count. Measurement shows every one of the 238 `nodeIds` entries
across all 10 layers resolves to a `file`, `config`, or `pipeline` node, and none to a `function` or
`class`. The architecture's own statement — "every file is assigned to exactly one layer" — holds
exactly.

The instruction to intersect with `type == "file"` therefore **undercounts**, because it discards
the `config` and `pipeline` members:

| Layer | 361 reported | Actual |
|---|---|---|
| Packaged Declarative Content | 1 | **34** (config 13, file 1, pipeline 20) |
| Project Configuration | 2 | **6** (config 4, file 2) |

The other eight layers are unaffected because they happen to contain only `file` nodes. The
generated `943` sample carries both wrong counts.

**Fix:** count a layer as `nodeIds | length` directly, and report the type breakdown when a layer
contains anything other than `file`. Retain a cross-check that every `nodeIds` entry resolves to a
node carrying `filePath`; if any entry resolves to a `function` or `class` node, that *is* upstream
drift and is reported as such rather than silently filtered.

**Correction 2 — "file-level" means "carries a `filePath`", not `type == "file"`.**

The architecture defines file-level types as a set of nine (`file`, `config`, `service`, `endpoint`,
`schema`, `table`, `pipeline`, `document`, `resource`); 361's skill text collapsed that to
`select(.type == "file")`. In this graph that silently drops 37 real analyzed files, including every
review template, every pipeline definition, and `pyproject.toml` — content squadron cares about more
than average.

**Fix:** the file-level selector becomes an explicit type allow-list, and the two excluded types
(`function`, `class`) stay excluded by name rather than by omission:

```
select(.type != "function" and .type != "class")
```

Stated as an exclusion rather than an allow-list deliberately: an upstream release that adds a tenth
file-level type is then included automatically rather than silently dropped, while the two node
classes that would blow up context stay out. A node surviving this filter but carrying no `filePath`
is reported as drift.

This also repairs the coverage arithmetic — 238 file-level nodes reconciles exactly with
`meta.json`'s `analyzedFiles`, which is what makes the coverage section below verifiable rather than
decorative.

**Correction 3 — the `fingerprints.json` churn warning is misleading as written.**

The 361 skill's `.gitignore` section says of `fingerprints.json`: "**Expect it to churn** — it
rewrites on every graph refresh and is diff-noisy." That is literally true but reads as a warning
about ordinary use, which it is not. Verified against the upstream plugin's own source:

| Writer | When it runs | Triggered by squadron? |
|---|---|---|
| `/understand` Phase 7 (`build-fingerprints.mjs`) | Full graph build | No |
| Post-commit auto-update hook (LOAD-PATCH-SAVE) | Incremental graph update, **only when `autoUpdate` is enabled** | No |

Both writers modify the graph. **Reading a graph never writes fingerprints.** Squadron's `understand`
skill only ever reads — `jq` selections against `knowledge-graph.json` — so no squadron flow in this
initiative causes churn, at any depth. The auto-update path additionally requires `autoUpdate` in
`config.json`, which this repo's config does not set (it carries only `outputLanguage`).

**Fix:** reword the note so it says what actually causes the rewrite — a deliberate `/understand`
re-run or an enabled auto-update hook — rather than implying that consuming the graph does. The
tracking decision itself is unchanged and correct: `fingerprints.json` costs a large diff only on
the occasions the PM deliberately refreshes the graph, and buys incremental analysis on a fresh
clone.

This matters because the project minimizes graph regenerations deliberately. A note implying that
routine reads dirty the working tree would argue for untracking a file that is, in practice, stable
between refreshes.

**Ignore scope is trash-only, and stays that way.** `.gitignore` ignores
`.understand-anything/.trash-*/` and nothing else; `knowledge-graph.json`, `meta.json`,
`config.json`, `.understandignore`, `fingerprints.json`, and `intermediate/scan-result.json` all
remain tracked as durable project knowledge. Confirmed on `main` at design time via
`git check-ignore` against each path.

### Section count vs the architecture

The architecture names four sections for this document — "the structural findings: layers, complexity
hotspots, entry points, dependency observations" (line 163). This design writes seven. The extra
three are stated and grounded here rather than left for a reader to infer, since a slice that
silently exceeds its architecture's declared shape is indistinguishable from one that drifted.

| Section | Status | Grounding |
|---|---|---|
| Layer architecture, complexity hotspots, entry points, dependency observations | Architecture-declared | Line 163, verbatim |
| Suggested reading order | **Inherited, not new** | Shipped in 361's flow and accepted at that slice's close. The architecture calls tour ordering "an expert judgment about which components matter and in what sequence" (line 104); this slice deepens it rather than introducing it |
| Coverage and scope limits | **Architecture-sanctioned slot** | The output-contract table calls `.understandignore` the field "squadron may reference when explaining coverage gaps" (line 89). This section is that reference, and it closes the three deferrals 361 forwarded here |
| Project identity | **Extension beyond the declared shape** | Justified below |

**Project identity is the one genuine extension, and it is deliberate.** The architecture maps
`project.languages` / `project.frameworks` to the *concept* document's Initial Technical Direction
(line 220), not to this document. Including it here is a scope decision, taken for two reasons:

1. **It is the only document capability (a) produces for a codebase with no concept.** Slice 363
   writes the concept, and 363 depends on this slice. Until 363 lands, a reader of the comprehension
   analysis has no artifact anywhere stating what the project *is* — only how it is shaped. A
   structural read that never names the system reads as anonymous.
2. **The cost of being wrong is one deletable section.** It is four fields, sourced and attributed,
   with no downstream consumer that breaks if it moves. If the PM judges identity to belong solely to
   the concept document, deleting section 1 leaves the other six untouched.

**If that trade is not wanted, drop section 1 and renumber** — nothing else in this design depends
on it, and success criteria 3 and 5 are the only places it is named. The extraction mapping it
provides to 363 stands either way, because 363 reads the mapping table, not this document.

### Extraction mapping

The core deliverable. Seven sections, in document order. Each row is binding: the section is written
from those fields, ordered by that rule, and on absence emits that fallback and nothing else.

| # | Section | Source fields | Ordering rule | Fallback when absent/empty |
|---|---|---|---|---|
| 1 | Project identity | `project.name`, `.description`, `.languages`, `.frameworks` | n/a (single block) | `[GAP: ...]` per missing subfield; `project` itself missing is a preflight rejection |
| 2 | Layer architecture | `layers[]` (`name`, `description`, `nodeIds`) | descending file count | preflight rejects empty `layers` |
| 3 | Entry points | file-level `nodes[]` where `tags` contains `entry-point` | layer, then `filePath` | `[GAP: no node carries the entry-point tag — re-run /understand]` |
| 4 | Complexity hotspots | file-level `nodes[]` (`complexity`, `filePath`, `summary`, `languageNotes`) | top ordinal tier, then layer | `[GAP: ...]` naming `complexity` |
| 5 | Suggested reading order | `tour[]` (`order`, `title`, `description`) | `order` ascending | `[GAP: ...]` naming `tour`; preflight has already warned |
| 6 | Dependency observations | `edges[]` (`type`, `source`, `target`, `weight`) | descending count, ties by `weight` | preflight rejects empty `edges`; an edge whose endpoint will not resolve to a layer is excluded from the tally and reported as drift, with the excluded count carried as a `[GAP: ...]` when non-zero |
| 7 | Coverage and scope limits | `meta.json` `analyzedFiles`; `config.json`; `.understandignore` | n/a | `[GAP: ...]` naming the unreadable file |

**Section ordering is identity → structure → detail → caveats.** A reader who stops after section 1
knows what the project is; a reader who stops after section 2 knows how it is shaped. Coverage
limits go last because they qualify everything above them and are meaningless read first.

**The fallback column has no third option.** Every section resolves to sourced content or a gap
marker. A section is never omitted, never shortened silently, and never filled with prose that is not
traceable to its named fields. This is the 361 governing rule applied per section rather than
globally.

### Section detail

Only what is not obvious from the mapping table.

**1. Project identity.** `project.description` is upstream-generated prose, so it is quoted as the
plugin's description and attributed — not restated as squadron's own claim. `languages` and
`frameworks` are listed verbatim. This section supplies concept sections in slice 363 (Initial
Technical Direction) and is the reason it is added here rather than there.

**3. Entry points.** The architecture names entry points as a required output of the comprehension
document and 361 did not deliver them. The signal is the `entry-point` tag, not a filename heuristic.
27 nodes carry it in this graph, which is too many to list flat — group by layer and report the count
per layer with the paths. A package `__init__.py` tagged `entry-point` is reported as tagged, not
reinterpreted; the tag is upstream's judgment and this skill does not overrule it.

**4. Complexity hotspots.** `complexity` is an ordinal string (`simple` / `moderate` / `complex`) —
carried forward from 361, where sorting it numerically was found to fail outright. Report the full
tier distribution across all file-level nodes, then list the top tier grouped by layer, which is what
makes concentration visible. Attach `languageNotes` where present (40% coverage) and omit the
annotation silently where absent — this is the one place omission is correct, because
`languageNotes` is a per-node optional annotation rather than a section's source field, and a gap
marker per unannotated node would be noise. A value outside the observed ordinal set is reported as
an unrecognized tier, never bucketed into a known one.

**6. Dependency observations.** Edge-type counts across the whole graph, then inter-layer `imports`
and `depends_on` connections with self-references excluded, ordered by count and broken by `weight`.
Map an edge to a layer through the owning file's layer membership, which is unambiguous — every
file-level node belongs to exactly one layer (verified).

**Endpoint resolution is a string operation on the edge, not a node read.** Node `id` is
type-prefixed as `<type>:<filePath>[:<name>]`. Verified across all 925 nodes in the real graph: the
second colon-delimited field equals `filePath` exactly, for every node of every type, and no
`filePath` contains a colon. The owning file of any edge endpoint is therefore recoverable from the
edge's own `source`/`target` string, and **no function or class node is read to do it** — which is
what keeps this consistent with Success Criterion 9 and the architecture's "function- and
class-level nodes are not read" rule.

This resolves a contradiction present in the first draft of this design, which said function/class
endpoints were "resolved to their owning file's layer" while Success Criterion 9 simultaneously
claimed no such node is read. The id-prefix derivation is what makes both true at once.

**Failure path — an endpoint that does not resolve.** Every step can fail on a graph nobody has
measured, and each failure is reported, never silently dropped:

- The endpoint string does not parse as `<type>:<filePath>[:<name>]` → the edge is excluded from the
  inter-layer tally and **reported as drift**, naming the malformed endpoint id.
- The endpoint parses but its `filePath` matches no file-level node → same: excluded and reported as
  drift, naming the unresolved id. (In the real graph, zero of 2184 edges have an endpoint absent
  from `nodes` — but that is one graph.)
- Excluded edges are counted, and the count appears in the section with a `[GAP: ...]` marker when
  it is non-zero, so a reader knows the tally is partial and by how much.

An unresolvable edge is never quietly skipped. That would make the dependency counts wrong in a way
no reader could detect, which is precisely the failure the fallback covenant exists to prevent.

**Scope note.** Only 16 of 610 `imports`/`depends_on` edges in the real graph touch a function or
class endpoint — 2.6%. Endpoint resolution is therefore a correctness guarantee for a small tail,
not a load-bearing feature. If the id-prefix contract fails to hold on some future graph, restricting
the tally to file-level endpoints and reporting the excluded count is an acceptable fallback that
loses little.

**7. Coverage and scope limits.** Closes all three 361 deferrals in one section:

- `analyzedFiles` from `meta.json`, reconciled against the file-level node count. Equal is the
  expected case and is stated as such. **A mismatch is reported as a discrepancy with both numbers**
  — it means the graph is internally inconsistent, and a reader deciding how much to trust the
  document needs to know that.
- `config.json` — report the settings that are present. In this graph it holds only
  `outputLanguage`; the architecture's table also lists `autoUpdate`, which is **absent**. Report
  only what is there. Do not report an absent optional setting as a gap: `config.json` is upstream's
  own file with upstream's own defaults, and squadron does not know which keys are mandatory.
- `.understandignore` — report the count of active (uncommented, non-blank) patterns and list them.
  This is what lets the document state its own coverage limits: a reader can see what was never
  analyzed. This repo's file measures **17 active lines** at design time. A file whose lines are all
  comments or blank is reported as "defaults only" — that is a real state, not a gap, since the
  upstream plugin ships the file pre-populated with commented suggestions.

### `[INFERRED]` governance

**Decision: `[INFERRED]` is defined but not used by this flow, and its use is a defect here.**

361 deferred this. The rule: every claim in the comprehension document traces to a named graph field
per the mapping table above, so there is nothing left for `[INFERRED]` to mark. If a section cannot
be written without inference, the correct output is a gap marker, not an inferred claim.

The one apparent exception is the closing observation each section carries — the sentence that reads
a pattern out of the data ("complexity concentrates in the seams where squadron meets an external
SDK"). These are **summaries of the presented data, not new claims**, and the test is mechanical: if
the sentence is not derivable from the table directly above it, it does not belong in the document.
`[INFERRED]` is not a license to add one, and a document written per this design contains zero
`[INFERRED]` markers.

The marker stays documented in the shared conventions because slice 363's interview path genuinely
needs it — a concept's Solution Approach derived from tour ordering *is* an inference from indirect
evidence. Governance for that use belongs to 363.

### `analyze-codebase-prompt.md` reuse

**Decision: adopt two conventions, adopt no structure, retain the document unchanged.**

This closes the parent architecture's open question.

**Adopted:** (1) the fact/inference separation discipline, already realized as the
`[GAP: ...]` / `[INFERRED]` pair settled in 361; (2) the rule that a section lacking data says so
explicitly and names what would be needed — which is exactly the fallback column above.

**Not adopted:** its analysis template. Its ten-part structure (identity, architecture, build/test/
deploy, code quality, security, performance, operations, and so on) is built for a different backend
— `codebase-probe.py` plus Repomix, which supply CI configs, dependency versions, static-analysis
output, and the source text itself. The knowledge graph supplies none of that. Adopting its template
would produce a document that is mostly gap markers, which is technically correct behavior and a bad
document. The seven sections above are the sections this backend can actually source.

Where the two overlap — identity/stack, architecture, dependency layering — the graph-backed path
sources them from named fields rather than from inference over source text, which is strictly
stronger and is why the shapes differ.

**Retained:** the document stays in `user/reference/` unchanged, as the architecture requires. It is
the lighter, cheaper, non-graph alternative and this initiative does not supersede it. A one-line
note is added to it pointing at the graph-backed path so a future reader knows both exist; nothing
else about it changes.

### Read discipline, unchanged

The 361 discipline is executed as written and this slice does not relax it: `jq` is required, every
read is a field-scoped selection, and the graph is never loaded whole, `cat`-ed, or opened with the
Read tool. This slice **adds** selections (project identity, tags, coverage files) and **widens** the
node filter from `type == "file"` to "not function and not class" — a widening from 201 to 238 nodes,
where the excluded 687 function and class nodes remain excluded and are the reason the discipline
exists.

The one new read that is not a `jq` selection against the graph is `.understandignore`, which is a
small line-oriented text file read directly. That is consistent with the discipline, whose subject is
the graph's size, not the graph root generally.

## Integration Points

### Provides to Other Slices

- **363:** the extraction mapping table — the "attempt extraction first" half of the extract-then-ask
  rule needs exactly this per-section field mapping. Project identity (section 1) feeds the concept's
  Initial Technical Direction; layers and tour feed Solution Approach.
- **364:** the corrected layer composition and the file-level definition. Initiative candidates derive
  from layer boundaries and complexity clusters within a layer, both of which would have been wrong
  under the 361 undercount.
- **365:** nothing directly — capability (b) reads no graph. It continues to copy the 361 provenance
  and gap-marker conventions, which this slice does not change.

### Consumes from Other Slices

- **361:** preflight (location, validation, staleness, hygiene), provenance block, gap markers, index
  selection, and generated-document frontmatter — all executed unchanged.

## Success Criteria

1. Every section of the generated document names the graph fields it derives from, inline in the
   body, matching the extraction mapping table.
2. A section whose source fields are absent or empty emits a gap marker naming the field and the
   input that would supply it — never inferred prose, never a silent omission.
3. Project identity, layer architecture, entry points, complexity hotspots, reading order, dependency
   observations, and coverage/scope limits are all present, in that order, and every claim traces to
   node, edge, layer, tour, or metadata.
4. Layer file counts equal `nodeIds | length`; a layer containing `config` or `pipeline` nodes reports
   its type breakdown. Against this repo's graph, Packaged Declarative Content reports **34** and
   Project Configuration reports **6**.
5. The file-level selector excludes `function` and `class` by name and includes everything else;
   against this repo's graph it yields **238** nodes, reconciling with `meta.json`'s `analyzedFiles`.
6. The coverage section states the analyzed-file count, the `config.json` settings present, and the
   count of active `.understandignore` patterns — closing all three 361 deferrals.
7. The `fingerprints.json` note names what actually rewrites it — a deliberate `/understand` re-run
   or an enabled `autoUpdate` hook — and states that reading a graph never does. The ignore scope
   remains trash-only, with every other `.understand-anything/` artifact tracked.
8. A decision on `analyze-codebase-prompt.md` reuse is recorded in this design and reflected in the
   skill; the document itself remains in `user/reference/` and gains only a cross-reference line.
9. The generated document contains zero `[INFERRED]` markers, and the skill states why.
10. The whole graph is never loaded into context; every graph read is a field-scoped `jq` selection
    and no function- or class-level node is read. Dependency-endpoint resolution satisfies this by
    parsing the edge's own `source`/`target` id string, never by reading the node it names.
11. An edge whose endpoint cannot be resolved to a layer is excluded from the dependency tally and
    reported as drift naming the endpoint id; the excluded count appears as a `[GAP: ...]` when
    non-zero. It is never silently dropped.
12. Running against squadron itself produces a document whose claims a reader can check against the
    real repo — at least three spot-checks confirmed in the walkthrough.
13. No file under `src/squadron/` changes. The only changed non-document files are
    `commands/analysis/understand.md` and the cross-reference line in
    `user/reference/analyze-codebase-prompt.md`.

## Verification Walkthrough

Run from the squadron repo root, on branch `362-slice.comprehension-analysis-and-graph-extraction`.
Pre-366, the skill is exercised by opening `commands/analysis/understand.md` in a Claude Code session
and instructing "execute this skill's comprehension analysis flow against this repo".

**1. Corrections are real — confirm before implementing.** These are the measurements the design
rests on; re-run them, because the graph may have been refreshed:

```
# Layer nodeIds contain zero function/class nodes, and sum to analyzedFiles
jq -r '([.nodes[]|{name:.id,value:.type}]|from_entries) as $T
  | .layers[] | "\(.name)  total=\(.nodeIds|length)  " +
    (.nodeIds|map($T[.]//"UNRESOLVED")|group_by(.)|map("\(.[0]):\(length)")|join(" "))' \
  .understand-anything/knowledge-graph.json
# -> Packaged Declarative Content total=34 config:13 file:1 pipeline:20
# -> Project Configuration total=6 config:4 file:2   (all others file-only)

jq -r '[.layers[].nodeIds|length]|add' .understand-anything/knowledge-graph.json   # -> 238
jq -r '.analyzedFiles' .understand-anything/meta.json                              # -> 238
jq -r '[.nodes[]|select(.type!="function" and .type!="class")]|length' \
  .understand-anything/knowledge-graph.json                                        # -> 238
```

If these three numbers do not agree, **stop and report** — the coverage section's reconciliation
claim is false and the design needs revisiting before implementation.

**1b. The id-prefix contract, which endpoint resolution depends on.** Confirm that a node's owning
file is recoverable from its id alone, so no function/class node is ever read:

```
# every node's second colon field must equal its filePath -> expect only ok:true, n:925
jq -r '[.nodes[]|{ok: ((.id|split(":")[1]) == .filePath)}]
       | group_by(.ok)|map({ok:.[0].ok,n:length})' .understand-anything/knowledge-graph.json

# no filePath may contain a colon (it would break the split) -> expect 0
jq -r '[.nodes[]|select(.filePath and (.filePath|test(":")))]|length' \
  .understand-anything/knowledge-graph.json

# edges whose endpoints are absent from nodes -> expect 0 here, but the code path must exist anyway
jq -r '([.nodes[].id]|map({name:.,value:true})|from_entries) as $N
  | [.edges[]|select(($N[.source]|not) or ($N[.target]|not))]|length' \
  .understand-anything/knowledge-graph.json
```

If the first check returns any `ok:false`, **stop** — endpoint resolution must fall back to
file-level endpoints only, per the scope note in Section detail item 6.

**2. Happy path.** Run the flow. Preflight reports as in 361 (unchanged). The document is written to
the next unused index ≥ 940 in `user/analysis/` — 943 exists, so expect **944**; 943 is not
overwritten.

Confirm in the written document:
- seven sections, in the mapping table's order;
- `## Provenance` immediately under the H1, above all content, with a section-sourcing line per
  section;
- Packaged Declarative Content reports 34 files with its type breakdown, not 1;
- coverage section states 238 analyzed files, `outputLanguage: en` from `config.json`, and the active
  `.understandignore` pattern count;
- zero occurrences of `[INFERRED]`: `grep -c 'INFERRED' <doc>` returns 0.

**3. Frontmatter gate.** `cf validate frontmatter` on the new document returns no inconsistencies;
`model:` reads back as a real model id, not a placeholder.

**4. Spot-checks against the real repo** (at least three). **Executed 20260819 — four run, all
resolved:**

```
find src/squadron -name '*.yaml' -path '*pipeline*' | wc -l          # 20 == 20 pipeline nodes  PASS
find src/squadron -name '*.yaml' | grep -i templ | wc -l             # 7 templates             PASS
grep -vE '^\s*(#|$)' .understand-anything/.understandignore | wc -l  # 17 == 17 reported       PASS
grep -cE '^\s*app\.(command|add_typer)' src/squadron/cli/app.py      # 23 vs prose "27"        REPORTED
```

**Caveat found and recorded in the generated document, not reconciled.** The CLI Surface layer's
`description` says "27 `sq` sub-commands"; `app.py` registers 23 top-level entries (15 commands + 8
sub-groups) and `cli/commands/` holds 26 non-`__init__` modules. Layer descriptions are
upstream-generated prose and are quoted verbatim, so the mismatch is reported as a caveat in section
7 of the generated document. The layer's **node count (29) is computed from `nodeIds` and is
unaffected** — numbers embedded in upstream prose carry upstream's authority, not the document's.

Both paths in this step's original draft are correct: all 20 pipeline YAML files live in
`src/squadron/data/pipelines/` and all 7 templates in `src/squadron/data/templates/`, so the `ls`
form yields the same counts as the `find` form above. The 13 `config`-type nodes in the Packaged
Declarative Content layer decompose exactly as 7 templates + 3 compaction policies + 3 `.toml`
registries.

**5. Gap-marker path.** Against a scratch copy (never tamper with the repo's real graph), following
the 361 scratch pattern:

```
mkdir -p "$S/real/.understand-anything"
cp .understand-anything/{knowledge-graph.json,meta.json} "$S/real/.understand-anything/"
cd "$S/real/.understand-anything"
jq '.tour = []' knowledge-graph.json > kg-empty-tour.json
jq '[.nodes[] | if .tags then .tags -= ["entry-point"] else . end] as $n | .nodes = $n' \
  knowledge-graph.json > kg-no-entrypoints.json
```

- Empty `tour` → reading-order section carries a gap marker, and the same marker appears in the
  provenance flagged-gaps line (2 occurrences), and the run still completes.
- No `entry-point` tag anywhere → entry-points section carries a gap marker naming the tag; the run
  still completes and every other section is unaffected.
- Remove `meta.json` → coverage section's analyzed-file line carries a gap marker; staleness
  separately records its skip per the 361 contract.

**5b. Unresolvable edge endpoint.** The real graph has none, so it must be induced:

```
# point one edge at a node id that does not exist
jq '.edges[0].target = "file:does/not/exist.py"' knowledge-graph.json > kg-dangling-edge.json
# and one at a string that does not parse as <type>:<filePath>[:<name>]
jq '.edges[1].source = "malformed-endpoint-id"'  knowledge-graph.json > kg-malformed-edge.json
```

Each run must exclude the offending edge from the inter-layer tally, **report it as drift naming the
endpoint id**, and carry the excluded count as a `[GAP: ...]` in the dependency section. A run that
completes with an unchanged-looking tally and no mention of the excluded edge is a **failure of this
step**, not a pass — silent exclusion is the specific behavior this path exists to prevent.

**Executed 20260819 — both variants PASS.** Detection is a single selection resolving each endpoint
by id-prefix parse and classifying it `MALFORMED` (no colon) or `UNRESOLVED` (parses, but the
`filePath` matches no file-level node):

```
excluded_edges=1  DRIFT: target=file:does/not/exist.py [UNRESOLVED]      # dangling
excluded_edges=1  DRIFT: source=malformed-endpoint-id [MALFORMED]        # malformed
excluded_edges=0                                                          # control: real graph
```

The control run on the unmodified graph returns 0, which is what makes the two positives meaningful —
the check distinguishes induced breakage from the healthy case rather than always firing.

**6. Coverage discrepancy path.** Make `analyzedFiles` disagree with the node count:

```
jq '.analyzedFiles = 999' meta.json > meta-wrong.json
```

The coverage section reports **both** numbers and names the discrepancy. It does not silently prefer
either.

**7. Read discipline.** Confirm no whole-graph read occurred: the session used only `jq` selections,
and no `cat`, `head`, or Read tool call targeted `knowledge-graph.json`. Confirm no
function/class-level node data appears in any section.

**Executed 20260819 — PASS.** Every graph access in the implementing session was a field-scoped `jq`
selection; no `cat`, `head`, or Read tool call targeted `knowledge-graph.json`, and no function- or
class-level node data reached any section of the generated document. `git status` on
`.understand-anything/` reports no modification — including `fingerprints.json`, which empirically
confirms correction 3's claim that **reading a graph never writes fingerprints**.

## Walkthrough outcome (20260819)

All steps executed on branch `362-slice.comprehension-analysis-and-graph-extraction`. Generated
document: `project-documents/user/analysis/944-analysis.codebase-comprehension.md` (943 not
overwritten).

| Step | Result |
|---|---|
| 1. Corrections are real | PASS — 238/238/238 reconcile; layer compositions match (PDC 34 `config:13 file:1 pipeline:20`, Project Configuration 6 `config:4 file:2`) |
| 1b. Id-prefix contract | PASS — `ok:true, n:925`; 0 filePaths contain a colon; 0 edges have an absent endpoint |
| 2. Happy path | PASS — 944 written; 7 sections in mapping order; Provenance under H1; 7 inline `From ...` lead sentences; `grep -c INFERRED` = 0 |
| 3. Frontmatter gate | PASS — no inconsistencies; `model: claude-fable-5` (real id) |
| 4. Spot-checks | 3 PASS, 1 REPORTED (upstream prose "27 sub-commands" vs 23 registrations — recorded as a caveat, not reconciled) |
| 5. Gap-marker paths | PASS — all three degrade exactly one section and complete |
| 5b. Unresolvable endpoints | PASS — both variants excluded and named; control returns 0 |
| 6. Coverage discrepancy | PASS — both numbers reported (999 vs 238), neither preferred |
| 7. Read discipline | PASS — `jq`-only; graph and `fingerprints.json` unmodified |
| 8. Full-slice checks | PASS — no `src/` diff; 446 files formatted; 62 skills tests pass |

**Numbers that changed from the design's measurements, both as a direct result of correction 2** (the
widened file-level selector), not as premise failures:

- **Entry points: 28, not 27.** The design counted `type == "file"` only. The corrected selector adds
  `pyproject.toml`, a `config`-type node that genuinely carries the `entry-point` tag and declares the
  `sq` console script. The narrow selector was silently dropping a real entry point.
- **Complexity distribution: `complex` 43 / `moderate` 89 / `simple` 106** across 238 file-level
  nodes, where sample 943 reported 42/76/83 across 201. Same reason — 943 was generated under the
  pre-correction selector. Both totals are internally consistent with their own selector.

Sample 943 deliberately retains the pre-correction numbers as the historical record; 944 is the first
sample generated under the corrected contract.

**8. Full-slice checks.**

```
git diff --stat main -- src/     # -> empty
uv run ruff format --check .     # no Python changed; confirms nothing drifted
uv run pytest tests/skills/      # pack install path undisturbed
```

The only changed non-document files are `commands/analysis/understand.md` and the cross-reference
line in `user/reference/analyze-codebase-prompt.md`.

## Risk Assessment

**The extraction corrections rest on one graph.** Corrections 1 and 2 are measured against this
repo's single v2.8.1 graph. (Correction 3 is not exposed to this risk — it was verified against the
plugin's source, not against graph data.) If a layer in some other project's graph does contain
function or class
nodes, correction 1's simplification (`nodeIds | length`) would overcount. This is why the design
keeps the cross-check rather than dropping it: every `nodeIds` entry must resolve to a node carrying
`filePath`, and an entry that resolves to a `function` or `class` is reported as upstream drift
rather than silently filtered. The cross-check is cheap and makes the correction safe on graphs that
were never measured.

**Upstream contract drift** remains the initiative's standing medium risk and is handled by the
unchanged 361 preflight. Note one already-observed instance: the architecture documents `config.json`
as carrying `autoUpdate` and `outputLanguage`, and the real file carries only `outputLanguage`. That
is why section 7 reports what is present rather than checking for expected keys.

## Implementation Notes

Suggested order:

1. Apply the two extraction corrections (1 and 2) to the existing 361 sections first, in isolation,
   and re-run the flow — this alone changes two layer counts and the file-level selector, and
   confirms the corrections before any new section is layered on top.
2. Apply correction 3 — reword the `fingerprints.json` churn note in the `.gitignore` section. Pure
   text edit, no flow impact; doing it early keeps it from being forgotten behind the larger work.
3. Add the extraction mapping table to the skill as the flow's governing reference.
4. Add sections 1, 3, and 7 (project identity, entry points, coverage) — the genuinely new ones.
5. Deepen sections 2, 4, 5, 6 with their ordering rules and fallbacks.
6. Record the `[INFERRED]` and `analyze-codebase-prompt.md` decisions in the skill; add the
   cross-reference line to the reference document.
7. Walkthrough runs 1-8, fixing as found.

The 943 document generated during slice 361 carries the two wrong layer counts. **Leave it in place
and do not edit it** — generated analysis documents are independent samples, not revisions, per the
document conventions, and 944 will be the corrected sample. The divergence between the two is itself
useful evidence that the correction landed.

Testing is the walkthrough. This slice adds no Python and therefore no unit tests; run the existing
skills suite once to confirm the pack install path is undisturbed.
