---
name: understand
description: Consumes an existing understand-anything knowledge graph and writes squadron planning documents from it. Reads the graph the plugin already produced — it does not analyze the codebase itself and does not run the plugin. Use when the user asks for a codebase comprehension analysis derived from an existing knowledge graph. Does not auto-invoke.
disable-model-invocation: true
---

# Understand

A Claude Code skill that reads an existing `understand-anything` knowledge graph and writes squadron
planning documents from it.

This skill is a **consumer**. The graph is produced by the upstream `understand-anything` marketplace
plugin's own `/understand` command; this skill never runs, wraps, forks, or installs that plugin. If
no graph exists, this skill stops and says so rather than analyzing the codebase itself.

When invoked via `/understand`, follow the protocol below. Everything from here through the `---`
divider is the protocol Claude executes. The section after the divider is documentation for humans
installing or maintaining this skill.

---

## Preflight: Graph Contract

Run this entire section before writing anything. Every step below either succeeds, stops with a
named reason, or records an explicit skip. No step is allowed to fail quietly.

### Graph location and read discipline

Resolve the graph root:

1. Run `git rev-parse --show-toplevel`. On success, that is the repository root.
2. If `git` is unavailable or the directory is not a repository, use the current working directory
   as the root. This is a location fallback only — it does not suppress any check below.
3. The graph root is `<root>/.understand-anything/`. The graph file is
   `<root>/.understand-anything/knowledge-graph.json`; the metadata file is `meta.json` beside it.

**`jq` is required.** Check it with `command -v jq`. If it is absent, stop and say that this skill
requires `jq` to read the graph safely. **Do not fall back to reading the graph file directly** — the
graph routinely exceeds a megabyte, and loading it whole defeats the purpose of every scoped read
below.

**Every read is a field-scoped `jq` selection.** The graph is never loaded whole into context, never
`cat`-ed, and never read with the Read tool. Only these selections are needed:

| Purpose | Selection |
|---|---|
| Key presence | `jq -r 'keys[]'` |
| Array lengths | `jq -r '"\(.nodes\|length) \(.edges\|length) \(.layers\|length) \(.tour\|length)"'` |
| Graph version | `jq -r '.version'` |
| Project identity | `jq -r '.project \| {name, description, languages, frameworks}'` |
| Layers | `jq -r '.layers[] \| {id, name, description, count: (.nodeIds\|length)}'` |
| Layer membership | `jq -r '.layers[] \| {name, nodeIds}'` |
| File-level nodes | `jq -r '.nodes[] \| select(.type != "function" and .type != "class") \| {id, filePath, summary, complexity, tags, languageNotes}'` |
| Tour steps | `jq -r '.tour[] \| {order, title, description}'` |
| Edge aggregates | `jq -r '[.edges[].type] \| group_by(.) \| map({type: .[0], n: length})'` |
| Edge endpoints | `jq -r '.edges[] \| {type, source, target, weight}'` |

Select **only** the fields named in that table. A node also carries `name` and `lineRange`; neither is
read by this flow.

**Edge endpoints are read as strings, never dereferenced into nodes** — see section 6 of the flow for
the id-prefix parse that makes this possible.

**Function- and class-level nodes are never read.** They are the bulk of the graph and none of the
sections this skill writes derive from them.

**"File-level" means "carries a `filePath`"** — a node that stands for a whole file. It is *not* a
synonym for `type == "file"`. The architecture defines nine file-level types; this graph carries
`file`, `config`, and `pipeline` among them, and a future upstream release may add a tenth.

So the file-level filter is stated as an **exclusion by name**:

```
select(.type != "function" and .type != "class")
```

Not `select(.type == "file")`. The allow-list form silently drops every file-level type it was not
written to know about — on this graph it yields 201 nodes instead of 238, losing all 17 `config` and
20 `pipeline` nodes and quietly disagreeing with `meta.json`'s `analyzedFiles`. The exclusion form
admits a new upstream file-level type automatically, which is the correct default: a file-level node
this skill has never heard of still stands for a real file.

**Drift rule.** A node that survives the exclusion but carries **no `filePath`** is reported as
upstream drift, naming the offending id. It is never silently counted or silently dropped — either
`function`/`class` are no longer the only non-file-level types, or the node is malformed, and both
are findings.

**Also consumed by the comprehension flow**, beyond the selections above — these were deferred by the
361 contract and are read by section 7 (coverage and scope limits):

- `config.json` and `.understandignore` in the graph root — how the upstream plugin was configured
  and what it excluded, which is what lets a generated document state its own coverage limits.
- `meta.json`'s `analyzedFiles` count, reconciled against the file-level node count.

Node `type` values beyond `file`, `function`, and `class` (this graph also carries `pipeline` and
`config`) are **in scope** — see the file-level definition above; they are the reason the filter is an
exclusion rather than an allow-list.

### Validation: absent, unparseable, malformed

Run these three checks in order and stop at the first failure. The three messages must be textually
distinct — a reader must be able to tell which failure occurred without inspecting anything else.

**1. Absent** — `knowledge-graph.json` does not exist at the graph root.

Stop. Report the path that was checked, and say that this skill consumes a knowledge graph produced
by the `understand-anything` plugin's own `/understand` command, which must be run first.

State only that the graph is missing. **Do not speculate about whether the plugin is installed**,
and do not offer to install it — detecting and reporting plugin availability is slice 366's scope,
and a guess here would be wrong as often as right.

**2. Unparseable** — `jq empty <graph>` exits non-zero.

Stop. Name the file and report that it is not valid JSON, quoting `jq`'s own error. Say the graph is
likely truncated or partially written, and that re-running the plugin's `/understand` will rewrite
it. This message must not mention missing keys — the file never parsed, so no key was inspected.

**3. Malformed** — the file parses but its shape is wrong.

Required top-level keys, each with its required type:

| Key | Type | Empty is |
|---|---|---|
| `nodes` | array | **reject** |
| `edges` | array | **reject** |
| `layers` | array | **reject** |
| `tour` | array | warn, proceed |
| `version` | string | reject if missing |
| `project` | object | reject if missing |

Stop if any key is missing, is the wrong type, or — for `nodes`, `edges`, `layers` — is present but
empty. **Name every offending key in one message**, not just the first one found, so a single run
tells the reader everything that is wrong.

Report graph identity alongside the failure: `version` from the graph, and `gitCommitHash` and
`lastAnalyzedAt` from `meta.json` when they are readable. If `meta.json` is unreadable, say so rather
than omitting the line — identity is what lets a reader tell a stale graph from a broken one.

**The `tour` asymmetry.** An empty `tour` degrades exactly one section (suggested reading order), so
it warns and proceeds, and the affected section carries a gap marker. Empty `nodes`, `edges`, or
`layers` means nothing useful can be written, so it rejects. This asymmetry is deliberate: the test
is whether the missing field costs one section or the whole document.

**Governing rule.** If the upstream plugin renames or restructures a field, that must surface here as
failure 3 — a loud, named rejection. It must **never** produce a document that is silently thinner
because a selection returned nothing. A section that cannot be sourced is either a gap marker or a
stopped run, never a quiet omission.

### Staleness

The graph is a snapshot. This check reports how far the codebase has moved since it was taken. It
**warns; it never blocks** — a stale graph still produces a useful document, provided the reader is
told it is stale.

Read `gitCommitHash` from `meta.json`.

- If `meta.json` is missing, or does not carry `gitCommitHash`, report **that specific reason** —
  "meta.json is absent" and "meta.json has no gitCommitHash" are different findings — and record the
  skip in the provenance block. Then continue.
- If `git` is not on PATH, or the graph root is not inside a repository, announce the skip in console
  output **and** record it in the provenance block, naming which of the two applies. Then continue.

**Never skip silently.** A reader who is not told the check was skipped will assume it passed.

With a hash in hand, compare against `git rev-parse HEAD`. There are exactly three outcomes:

1. **Equal** — report "graph matches HEAD".
2. **Different, and the hash is a known ancestor** — confirm with `git merge-base --is-ancestor
   <hash> HEAD`, then get the distance with `git rev-list --count <hash>..HEAD`. Report "N commits
   behind HEAD".
3. **Different, and the hash is unknown to this repository** — the commit was rebased away, amended,
   or is absent from a shallow clone. Report drift with an **unknown** distance and say which of
   those the evidence supports.

**Never fabricate a distance.** If `git rev-list --count` cannot run or the hash is not an ancestor,
the honest answer is "unknown distance", with the reason. A made-up number is worse than no number,
because it reads as measured.

On any drift (outcomes 2 and 3), state the finding and ask the Project Manager whether to proceed
with the stale graph or stop and refresh it by re-running the plugin's `/understand`. If they choose
to proceed, record that in the provenance block as a PM decision — not as an incidental detail.

Every path through this check ends in one of: a distance, an explicit unknown-distance reason, or an
explicit skip reason. There is no silent outcome.

### `.gitignore` hygiene

The upstream plugin writes timestamped trash directories (`.understand-anything/.trash-<epoch>/`)
when it re-analyzes. These are churn, not project knowledge, and must not reach a commit.

Run this **at the start of every run, before any document is written**. A run that writes a document
and then fails hygiene has already left the repository in the state hygiene exists to prevent.

**1. Test whether it is already covered.** Run:

```
git check-ignore -q .understand-anything/.trash-probe/
```

Exit 0 means some existing rule already covers the path — this skill's own entry, a broader
`.understand-anything/`, or anything else equivalent. Report "already ignored" and write nothing.

This is a **semantic** test, not a pattern grep. Grepping `.gitignore` for a literal string would
miss a broader rule that already does the job and would append a redundant entry. **The probe path
does not need to exist** — `git check-ignore` answers about the path, not about the file.

**2. Append if not covered.** Create `.gitignore` if it is absent. Append:

```
# squadron: understand-anything trash directories
.understand-anything/.trash-*/
```

**3. Confirm.** Re-run the check from step 1. Report the addition only after it passes. Never report
a write you did not confirm.

**Failure handling.** Every failure is reported and non-fatal — hygiene never stops a run:

- `.gitignore` is read-only or the write is permission-denied → report that the entry could not be
  added **and why**, then continue.
- The graph root is not inside a git repository → report that hygiene does not apply here, then
  continue.

**Never claim a write succeeded when it did not.** "Could not update .gitignore: permission denied"
is a good outcome. Silence is not.

**What is not ignored, and why.** Everything in the graph root except the trash directories stays
**tracked**:

- `knowledge-graph.json`, `meta.json`, `config.json`, `.understandignore` — durable project
  knowledge. The graph is the input every document in this initiative derives from, and a tracked
  graph is what makes a generated document auditable after the fact.
- `fingerprints.json` — the plugin's incremental-analysis cache: a `contentHash` plus structural
  summary per analyzed file. Tracking it means a fresh clone's first re-analysis is incremental
  rather than a full rescan. It is regenerable, so it is tracked for the speed, not because it is
  authoritative.

  **Exactly two things rewrite it**, and neither is a side effect of using this skill:

  1. A deliberate re-run of the upstream plugin's own `/understand` command.
  2. The plugin's post-commit auto-update hook — but **only when `autoUpdate` is `true` in
     `.understand-anything/config.json`**. The hook is gated on that key and the plugin's default
     is `autoUpdate: false`, so on a project that has never enabled it the hook never fires.

  **Reading a graph never writes fingerprints.** Every squadron flow that touches the graph — this
  skill included — only reads, via the field-scoped `jq` selections above. No number of runs of this
  skill will produce a `fingerprints.json` diff. Expect churn when you refresh the graph on purpose,
  not when you consume it.
- `intermediate/` — the raw pre-analysis scan (file inventory, language and framework detection,
  import map) that feeds graph construction.

`fingerprints.json` and `intermediate/` were not contemplated by the slice 361 design; they were
observed in a real v2.8.1 graph and are recorded here so a later author does not have to rediscover
what they are.

Squadron never deletes trash directories. The upstream plugin owns that lifecycle; this skill only
keeps them out of git.

## Document Conventions

### Gap markers

When the graph does not supply something a section needs, **say so in place**. Do not omit the
section, and do not fill it with plausible prose.

The marker is:

```
[GAP: {what is missing} — {which input would supply it}]
```

Both halves are required. "What is missing" alone tells a reader something is wrong; naming the input
that would supply it tells them what to do about it. Example shape: a marker for an empty tour names
the tour field and says that re-running the plugin's `/understand` would populate it.

**Three rules:**

1. A marker appears **twice** — in the body, exactly where the content would have appeared, and in
   the provenance block's flagged-gaps line. The body placement tells a reader mid-document; the
   provenance placement lets them see every gap without reading the whole thing.
2. A document containing gap markers is a **valid output**, not a failed run. Gaps are information.
3. A gap is **never** filled with plausible prose. Inventing content that reads as sourced is the
   specific failure this whole contract exists to prevent.

**`[INFERRED]` is a retained sibling convention**, not a replacement. It comes from
`project-documents/user/reference/analyze-codebase-prompt.md` and prefixes a claim drawn from
indirect evidence. The two differ: `[GAP: ...]` marks something absent, `[INFERRED]` marks something
present but derived.

**This flow does not use `[INFERRED]`, and its appearance in a comprehension document is a defect.**

Every claim in the comprehension document traces to a named field via the extraction mapping table
below, so nothing is left for `[INFERRED]` to mark. Where inference would go, the correct output is a
**gap marker** — the field is absent, and saying so is more useful than reasoning around it.

The one apparent exception is the closing observation a section may carry — a sentence that reads a
pattern out of the data it just presented. Those are **summaries of presented data, not new claims**,
and the test is mechanical:

> If the closing sentence is not derivable from the data presented directly above it, it does not
> belong in the document.

`[INFERRED]` is not a license to add one. **A conforming comprehension document contains zero
`[INFERRED]` markers** — `grep -c 'INFERRED'` returns 0.

The marker stays documented in these shared conventions because Flow: Concept Generation genuinely
needs it: a concept's Solution Approach derived from tour ordering *is* an inference from indirect
evidence. Governance for that use is **`[INFERRED]` governance for this flow**, in that flow's
section below.

### Provenance block

Place a `## Provenance` section **immediately after the H1 title, above all content**, as body prose.

**Not frontmatter.** Frontmatter is schema-validated and invisible to a reader scanning the document.
The failure this guards against is a human reading a generated document and trusting it without
knowing it was machine-written, derived from a stale snapshot, or missing sections. That warning has
to be where they will actually see it.

The block carries these lines:

- **Generated by** — this skill, and the model id that produced the document.
- **Generated on** — the date of this run.
- **Source** — the graph path, with its `nodes` / `edges` / `layers` / `tour` counts.
- **Graph identity** — `gitCommitHash` and `lastAnalyzedAt` from `meta.json`.
- **Staleness** — the outcome from the staleness check: matched HEAD, N commits behind, drift with
  unknown distance and its reason, or an explicit skip and its reason. If the PM chose to proceed
  with a stale graph, record that decision here.
- **Section sourcing** — each section of the document and the graph field it derives from.
- **Flagged gaps** — every `[GAP: ...]` marker in the document, or an explicit statement that there
  are none.
- **Review state** — always states the document is a machine-generated draft that has had no human
  review.

**The block obeys its own gap-marker rule.** If `meta.json` is unreadable, the graph-identity line
carries a `[GAP: ...]` rather than being dropped — consistent with how the staleness line records a
skip. **No line is ever silently omitted**: every one resolves from real data or carries a marker.

The review-state line is what makes `status: not_started` legible on a generated draft — it tells a
reader the status field means "not yet reviewed by a human", not "not yet written".

Slice 365 (capability (b)) reuses this same block shape, with **Source** naming the concept and
initiative-plan paths instead of a graph.

### Generated document conventions

**Output path:**

```
project-documents/user/analysis/{index}-analysis.codebase-comprehension.md
```

**Index selection.** Scan existing `9nn-` filenames in `project-documents/user/analysis/` and take
the **lowest unused index ≥ 940**. Each run takes a **new** index — runs are independent samples, not
revisions of each other, matching the existing `940`/`941`/`942` series. Never overwrite an existing
document. Overflow past `949` is sanctioned by the architecture; keep counting.

**Frontmatter:**

```yaml
---
docType: analysis
project: {project name}
topic: codebase-comprehension
dateCreated: {YYYYMMDD}
dateUpdated: {YYYYMMDD}
status: not_started
model: {id of the model generating this document}
---
```

**`model:` must hold the id of the model actually generating the document.** Never empty, never a
placeholder, never copied from another document. `cf validate frontmatter` is permissive here and
will pass on a placeholder, so this requirement rests on the skill text, not on the gate.

If you cannot determine your own model id, **say so explicitly and stop** rather than writing a
plausible-looking value. A wrong id is worse than a reported inability, because it silently
misattributes the document.

`model:` on an `analysis` document is accepted by `cf validate frontmatter` — verified against
`942-analysis.tech-debt-audit.md`, which carries it.

**Why `status: not_started`** rather than a review-pending value: the status enum has no
`needs_review` member; `complete` would assert a review that has not happened. Review state is
carried by the provenance block, and `not_started` correctly reflects that no human has reviewed it.

## Flow selection

This skill implements two flows. The invocation argument selects between them:

| Argument | Flow |
|---|---|
| none | Flow: Comprehension Analysis |
| `comprehension` | Flow: Comprehension Analysis |
| `concept` | Flow: Concept Generation |
| `candidates` | Flow: Initiative Candidates |
| anything else | **unrecognized** — say so and stop |

Any unrecognized argument stops the same way — say the argument is unrecognized and stop; do not
guess at intent.

**Selection is by explicit argument only.** The skill never infers a flow from repository state. The
absence of a concept document never auto-triggers Flow: Concept Generation, and the presence of one
never suppresses it. A flow runs because it was named. The presence or absence of a concept document
selects nothing here either — it changes only what Flow: Initiative Candidates reads once it has
been named.

**Preflight runs in full for both flows, unchanged** — location, validation, staleness, and the
`.gitignore` hygiene write, which the shared contract performs at the start of every run before any
document is written. Flow: Concept Generation adds no hygiene behavior of its own and skips none.

## Flow: Comprehension Analysis

This is the default flow. Run **Preflight: Graph Contract** in full first — location, validation,
staleness, hygiene — then extract and write.

### Extraction mapping

This table governs the flow. Seven sections, in document order. **Each row is binding**: the section
is written from those fields, ordered by that rule, and on absence emits that fallback and nothing
else.

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
knows what the project is; a reader who stops after section 2 knows how it is shaped. Coverage limits
go last because they qualify everything above them and are meaningless read first.

**The fallback column has no third option.** Every section resolves to sourced content or a gap
marker. A section is never omitted, never shortened silently, and never filled with prose that is not
traceable to its named fields. This is the governing rule of the graph contract applied per section
rather than globally.

Write exactly these seven sections, in this order. Each names its source graph field **inline, in the
body**, so a reader can trace any claim without consulting this skill — the section-sourcing lines in
the provenance block are in addition to that, not a substitute for it.

**Inline attribution is required in every section.** Each section body **opens with a lead sentence
naming the fields it was written from** — the established pattern is a short `From \`<field>\`.`
sentence, optionally carrying the one caveat a reader needs to read the numbers correctly:

```
From `layers[]`. Counts are `nodeIds | length`; layers holding non-`file` types carry a breakdown.
From `tour[]`, in `order`.
```

This is what makes a claim traceable at the point of reading. The provenance block's section-sourcing
lines serve a reader scanning the top of the document; they do not discharge this requirement.

**1. Project identity** — from `project`.

`project.name`, `project.description`, `project.languages`, `project.frameworks` — a single block, no
internal ordering.

**`project.description` is upstream-generated prose.** Quote it and attribute it to the plugin. Never
restate it as squadron's own claim about the project: it is the graph's description of the codebase,
and a reader must be able to tell that apart from anything squadron asserts. `languages` and
`frameworks` are listed verbatim, not summarized or reordered.

Fallback: a `[GAP: ...]` marker **per missing subfield**, naming that subfield. A missing `project`
object as a whole is a preflight rejection (**Validation** step 3 above) and never reaches this
section — do not re-implement that check here.

This section supplies the concept document's Initial Technical Direction in **Flow: Concept
Generation**, which is why identity is captured here rather than left to that flow.

**2. Layer architecture** — from `layers[]`.

For each layer: `name`, `description`, and its node count.

**Ordering: descending file count** — the largest layer first, so the shape of the system is legible
from the top of the section.

**Fallback: none beyond preflight.** An empty `layers` array is a preflight rejection (**Validation**
step 3), so this section is never reached without data and invents no marker of its own.

**The count is `nodeIds | length`, directly.** `layers[].nodeIds` holds only file-level nodes — no
function or class node appears in any layer. Intersecting with `type == "file"` undercounts every
layer that carries a non-`file` file-level type, and does so silently: on this repo's graph it
reports Packaged Declarative Content as 1 instead of 34, and Project Configuration as 2 instead of 6.

**Report the type breakdown when a layer holds anything other than `file` nodes**, so the count is
auditable rather than a bare number:

```
Packaged Declarative Content — 34 (config:13 file:1 pipeline:20)
Project Configuration — 6 (config:4 file:2)
```

A layer that is entirely `file` nodes reports its count alone; the breakdown would add nothing.

**Cross-check, and its drift rule.** Every `nodeIds` entry must resolve to a node carrying a
`filePath`. An entry that resolves to a `function` or `class` node — or to no node at all — is
**reported as upstream drift**, naming the offending id. It is never silently filtered out of the
count: filtering is what produced the wrong numbers this rule replaces.

```
jq -r '([.nodes[]|{name:.id,value:.type}]|from_entries) as $T
  | .layers[] | "\(.name)  total=\(.nodeIds|length)  " +
    (.nodeIds|map($T[.]//"UNRESOLVED")|group_by(.)|map("\(.[0]):\(length)")|join(" "))' \
  .understand-anything/knowledge-graph.json
```

Any `function`, `class`, or `UNRESOLVED` entry in that breakdown is drift; report it.

**3. Entry points** — from file-level `nodes[]` whose `tags` contains `entry-point`.

**The tag is the only signal.** No filename heuristics — do not infer an entry point from `main.py`,
`__main__`, `app.py`, or any other naming pattern, and do not suppress one because its name looks
unlikely. A package `__init__.py` carrying the tag is reported **as tagged**. The tag is upstream's
judgment; this skill reports it and does not overrule it in either direction.

Selection — note the file-level exclusion, not `type == "file"`:

```
jq -r '.nodes[] | select(.type != "function" and .type != "class")
       | select(.tags and (.tags | index("entry-point"))) | "\(.type)  \(.filePath)"' \
  .understand-anything/knowledge-graph.json
```

Ordering: **group by layer**, report the count per layer with the paths beneath it. A flat list is
the wrong shape here — this graph tags 28 file-level nodes, and grouping is what makes the
distribution legible.

Function-level nodes also carry this tag (24 of them here) and are **not** read: they are not
file-level, and the section reports files.

Fallback, verbatim: `[GAP: no node carries the entry-point tag — re-run /understand]`.

**4. Complexity hotspots** — from file-level `nodes[]`.

Fields: `complexity`, `filePath`, `summary`, `languageNotes`. File-level only
(`select(.type != "function" and .type != "class")` — see the file-level definition in the read
discipline above).

`complexity` is an **ordinal string**, not a number — observed values are `simple`, `moderate`, and
`complex`. Do not sort it numerically; `sort_by(-.complexity)` fails outright on a string, which is
the correct loud failure.

**Report the full tier distribution first, then the top tier grouped by layer.** The distribution
gives the reader a denominator; the grouping is what makes concentration visible. Ordering within the
section is top ordinal tier first, then by layer.

```
# distribution across all file-level nodes
jq -r '[.nodes[]|select(.type!="function" and .type!="class")|.complexity]
       | group_by(.) | map("\(.[0]):\(length)") | join(" ")' \
  .understand-anything/knowledge-graph.json
```

**`languageNotes` is attached where present and omitted silently where absent.** This is the one
sanctioned omission in the whole flow, and the reason is specific: `languageNotes` is a **per-node
optional annotation**, not a source field of the section. It is present on 97 of 238 file-level nodes
in this graph, and emitting a gap marker for each of the other 141 would bury the section in noise
that tells a reader nothing. Every other absence in this document still gets a marker.

**A `complexity` value outside the observed ordinal set is reported as an unrecognized tier**, named
explicitly, and never bucketed into a known one. Bucketing would silently move a file into a tier
upstream did not assign it.

Fallback: `[GAP: ...]` naming `complexity`.

**5. Suggested reading order** — from `tour[]`.

Fields: `order`, `title`, `description`. **Ordering: `order` ascending** — the tour is a sequence and
reporting it out of sequence destroys the only thing it carries.

`description` annotates each step; it is not optional decoration, it is what tells a reader why the
step comes where it does.

Fallback: `[GAP: ...]` naming `tour` and the input that would supply it. Preflight has already warned
on an empty `tour` (the tour asymmetry above), but **this section still emits its own marker** — the
warning went to the console, and the document has to stand on its own.

**6. Dependency observations** — from `edges[]`.

Fields: `type`, `source`, `target`, `weight`. Two parts, in this order:

1. **Edge-type counts across the whole graph** — a `group_by` over `.edges[].type`.
2. **Inter-layer `imports` / `depends_on` connections**, self-references excluded (a layer importing
   itself is not an observation), **ordered by descending count with ties broken by `weight`**.

**Endpoint resolution is a string parse of the edge's own `source` / `target` id — not a node read.**
Node ids are type-prefixed as `<type>:<filePath>[:<name>]`, so the **second colon-delimited field is
the owning file's path**, and that path's file-level node gives the layer. Verified across all 925
nodes of this graph: the second field equals `filePath` exactly for every node of every type, and no
`filePath` contains a colon.

**No node — and specifically no `function` or `class` node — is read to resolve an endpoint.** This
is what keeps the dependency section consistent with the read discipline above while still counting
the edges whose endpoints are function-level.

**Failure path — an endpoint that does not resolve.** Both variants are excluded from the tally and
**reported as drift naming the endpoint id**:

- The endpoint string **does not parse** as `<type>:<filePath>[:<name>]` → excluded, reported as
  drift naming the malformed endpoint id.
- The endpoint parses but its `filePath` **matches no file-level node** → excluded, reported as drift
  naming the unresolved id.

**Excluded edges are counted, and when that count is non-zero the section carries a `[GAP: ...]`
marker** stating how many edges were excluded, so a reader knows the tally is partial and by how
much. An unresolvable edge is **never silently skipped** — that would make the counts wrong in a way
no reader could detect. In this graph, zero of 2184 edges have an endpoint absent from `nodes`, but
the code path exists regardless, because that is one graph.

**Scope note — the fallback if the id-prefix contract ever fails.** Only 16 of 610
`imports`/`depends_on` edges here touch a function or class endpoint (2.6%), so endpoint resolution
is a correctness guarantee for a small tail, not a load-bearing feature. If a future graph breaks the
id-prefix contract, restrict the tally to file-level endpoints and **report the excluded count** —
that loses little and stays honest.

**7. Coverage and scope limits** — from `meta.json`, `config.json`, and `.understandignore`.

Last section, because it qualifies everything above it. Three inputs, each with its own rule:

**`analyzedFiles` from `meta.json`, reconciled against the file-level node count.** Equality is the
expected case and is stated as such ("238 analyzed files, matching 238 file-level nodes"). **A
mismatch is reported as a discrepancy carrying both numbers** — never silently prefer either, and
never reconcile them by hand. A mismatch means the graph is internally inconsistent, which is exactly
what a reader deciding how far to trust the document needs to be told.

```
jq -r '.analyzedFiles' .understand-anything/meta.json
jq -r '[.nodes[]|select(.type!="function" and .type!="class")]|length' \
  .understand-anything/knowledge-graph.json
```

**`config.json` — report the settings that are present.** Nothing more. **An absent optional key is
not a gap**: this is upstream's own file with upstream's own defaults, and squadron does not know
which keys are mandatory. This graph's file holds only `outputLanguage`; `autoUpdate` is absent, and
that absence is reported as nothing at all, not as a missing setting.

**`.understandignore` — report the count of active patterns and list them.** Active means uncommented
and non-blank (`grep -vE '^\s*(#|$)'`). This is what lets the document state its own coverage limits:
a reader can see what was never analyzed. A file whose lines are **all** comments or blank is
reported as **"defaults only"** — a real state, not a gap, because the upstream plugin ships this
file pre-populated with commented suggestions.

Fallback: `[GAP: ...]` naming the specific file that could not be read.

**Do not add sections beyond these seven.** The mapping table is the full scope of this flow. Concept
generation is **Flow: Concept Generation** below and initiative candidates are **Flow: Initiative
Candidates** below; neither is written here.

## Flow: Concept Generation

Writes `000-concept.{project}.md` for an existing codebase that has no concept document — the Phase 0
entry point for a repo that has never had cf/sq planning artifacts.

The governing rule of this flow: **an existing codebase answers questions about its own nature
through its artifacts, or not at all.** Three machine-readable sources are extracted **before any
human contact**. The human is asked exactly one category of thing — engagement context, the facts no
artifact can hold — as two fixed questions, plus one confirm-or-correct on the derived description.

Run **Preflight: Graph Contract** in full first, then check the preconditions below, then extract,
then interview, then draft, then confirm, then write.

### Preconditions

The target scenario is a repo with **no user-level cf/sq artifacts** — no concept, no initiative
plan. It is not a repo with no setup at all. Three preconditions, checked before extraction:

**1. The graph is present.** This is the shared **Preflight: Graph Contract** above, executed
unchanged — location, validation, staleness, hygiene. Missing, malformed, and stale handling all
belong to that contract; do not re-implement any part of it here.

**2. The ai-project-guide is installed.** The concept guide's layout is read at write time from:

```
project-documents/ai-project-guide/project-guides/guide.ai-project.000-concept.md
```

If the guide tree is absent, **stop** and name the setup step (`cf init` or `/cf:onboard`) that
installs it. This is a **terminal precondition failure, not a gap** — the document cannot be
correctly written at all, so no document is written.

**3. The project name resolves** from the cf project registration. **Never from the graph** — see
**Output conventions** below. If no registration resolves a name, **stop**, naming the setup step.
Deriving a filename from the graph's `project.name` is prohibited, so there is no fallback; this
failure is terminal, the same family as precondition 2.

**Boundary with `/cf:onboard`.** `/cf:onboard` owns project setup and the conversational, greenfield
concept path — a human describing what they intend to build. This flow owns the artifact-derived,
brownfield path — a machine drafting from what already exists. They **compose** (onboard installs the
scaffolding these preconditions require) and **do not overlap**: neither contains the other's
interaction model.

### The three-source extraction model

Extraction runs against three sources, **in the order below, before any human contact**. Each source
has a distinct attribution style, and the style is what makes a claim traceable at the point of
reading.

**Source 1 — the graph (structure).**

Fields read: `project.description`, `project.languages`, `project.frameworks`; `layers[]` names and
descriptions; `tour[]` order; file-level nodes tagged `entry-point`; `config` nodes.

*Attribution:* each claim **names its field inline**, exactly as the comprehension flow does.

*Read discipline:* 362's discipline, unchanged — field-scoped `jq` selections only, the whole graph
never loaded, no `function` or `class` node read. **This flow reads strictly less of the graph than
the comprehension flow does**: no edges, no complexity tiers, no per-node summaries.

**Source 2 — the repo's own prose (intent).**

A repo's README states what it is, what problem it addresses, and who reaches it, in its authors'
own words. That is the intent no graph field carries.

**Where the README and `project.description` disagree, the README wins.** `project.description` is
upstream-generated prose describing the repo as it stood when the graph was built; the README is
maintained by the project's own authors and travels with the code. A graph that is many commits
behind HEAD routinely carries a description of an earlier, narrower version of the project.

**Do not blend the two into a single averaged paragraph.** When they describe the project
differently — not merely in different words, but as a different kind of thing — that disagreement is
itself a finding: it usually means the project's scope moved and the graph did not follow. Surface it
at the confirmation step (below) rather than resolving it silently.

*Resolution:* the **root-level README, case-insensitive**, with `README.md` preferred when several
extensions exist. **Nothing below the root is read** — `docs/` trees and wikis are out of scope for
this flow by design: unbounded cost, unpredictable relevance.

*Attribution:* a claim **cites its file** (`README.md`). **Quoted material is quoted, never
paraphrased into squadron's own voice** — the distinction between what the repo says about itself and
what squadron asserts must survive into the document.

*When there is no root README:* the run loses the prose source. Affected sections **fall back to
graph fields where the mapping table maps them, and to gap markers where it does not**. The source
model degrades **explicitly, never silently**.

**Source 3 — filesystem signals (development practice).**

The graph's ignore rules routinely exclude test trees and CI configuration from analysis; the
filesystem cannot hide them. This source is a **closed checklist**:

| Signal | Probed at |
|---|---|
| Test tree | `tests/` or `test/` at the repo root |
| CI | `.github/workflows/` non-empty, or `.gitlab-ci.yml` |
| Lint/format/test configuration | tool tables in `pyproject.toml`, `.pre-commit-config.yaml`, `.eslintrc*`/`.prettierrc*` |

**The checklist is closed — a signal outside it is not probed.** Do not extend it opportunistically;
an open-ended filesystem hunt is what this bounded list exists to prevent.

*Attribution:* reported as **observations with paths** ("`tests/` present at repo root";
"`.github/workflows/ci.yml`").

**Absence of a signal is an observation, not a gap.** "No test tree observed at the repo root" is a
true and useful statement about development practice, and the source that produced it was fully
readable. A gap marker would wrongly imply something failed to be read.

### Per-section mapping

The concept guide's own sections, in its order. **Each row is binding**: the section is written from
those sources, in that order, with that human role and no other.

| # | Section | Sources, in order | Human role |
|---|---|---|---|
| 1 | Overview | README lead; graph `project.description`; `layers[]` descriptions | single confirm-or-correct before write |
| 2 | User-Provided Concept | engagement answers, verbatim | the two questions |
| 3 | Problem & Motivation | README problem statement (cited); Q1 answer for the engagement half | none beyond Q1 |
| 4 | Target Users | README; graph entry surfaces (`entry-point` nodes, `frameworks`) | none — never asked |
| 5 | Solution Approach | `layers[]` names + descriptions; `tour[]` order; coverage boundary | none |
| 6 | Initial Technical Direction | `project.languages`, `.frameworks`; `config` nodes; `entry-point` nodes | none |
| 7 | Development Approach | filesystem signals checklist; Q2 answer for unwritten constraints | none beyond Q2 |

**The Overview reads `layers[]` descriptions, not only the two top-level summaries.**
`project.description` and the README lead are both *summaries*, and a summary drops the specific
systems a project integrates with. Layer descriptions name them — an integration that appears in two
layer descriptions and its own module is a fact about what this project **is**, not merely how it is
built, and an Overview that omits it is thinner than its own sources.

> Before confirming the description, check it against `layers[]`: if a system named in two or more
> layer descriptions appears nowhere in the Overview, it belongs there.

This costs no extra read — `layers[]` is already loaded for Solution Approach.

**Dropped, not gap-marked.** "Why now", audience-evolution, and methodology-preference questions
appear **nowhere** — not asked, and not marked absent. For an existing codebase they have no useful
answer, and a generated document is not improved by recording that nobody answered them.

> A gap marker is reserved for content a section **needs** whose source is missing. These are topics
> the document does not need.

**Solution Approach's coverage boundary** is sourced from the coverage facts the comprehension flow
already establishes (section 7): `.understandignore` active patterns, and `meta.json`'s
`analyzedFiles` reconciled against the file-level node count. It states **which parts of the repo the
graph never saw** — on squadron, everything outside `src/` and root configuration, including the
markdown command surface. A concept that claims to describe the whole system while resting on a
partial graph is the failure this boundary prevents.

### The engagement interview

**Exactly two questions.** Fixed wording — not improvised, not extended, not reworded. Asked **once,
as one block, after extraction and before drafting**, so the answers inform Problem & Motivation and
Development Approach in a single drafting pass.

Ask these, verbatim:

```
1. What do you need to do with this codebase — add features, audit it, take over
   maintenance, modernize it, something else?

2. Are there constraints or off-limits areas that aren't written down anywhere — a
   dependency that can't be upgraded, a directory not to touch, an API that must stay
   stable?
```

**An improvised, added, or reworded question is a defect against Success Criterion 2, not a judgment
call.** No third question. No follow-up prompt on an answer. No clarifying round.

**Why these two and no others:** they are the only questions whose answers no artifact can hold,
because they are facts about the **engagement** rather than about the code. Everything else a
discovery interview would ask, an existing codebase already answers through its README, its graph,
and its filesystem.

**Both are skippable**, without argument or follow-up. A declined question produces:

- a **gap marker at the point of absence**, naming the interview as the input that would supply it,
  and
- an entry in the provenance block's **declined-questions** line.

Never a plausible guess. Never a silent omission.

**Answers land verbatim in User-Provided Concept.** The operator's words about the engagement *are*
the user-provided concept for a brownfield run. They are additionally the source for **Problem &
Motivation's engagement half** (Q1) and **Development Approach's constraints** (Q2) — used twice,
asked once.

### The single confirmation

After drafting and **before the file write**, show the operator:

- the **derived project description** — the Overview paragraph, README-led per the precedence rule
  above;
- the graph's **`lastAnalyzedAt`** and its distance behind HEAD, so a stale description is
  recognizable as stale; and
- **the disagreement, when there is one** — where `project.description` and the README describe the
  project as different kinds of thing, say so in one line and name both framings. This is the single
  most likely thing for the operator to correct, and showing it is what turns a vague "looks about
  right" into a real answer.

Then ask them to **confirm or correct** it, and add one prompt with it:

> Anything the codebase can't tell me — a surface being moved out, a component being replaced,
> a direction already decided but not yet built?

**This is part of the confirmation, not a third interview question.** It is bounded to the
description being confirmed, it is skippable in the same breath as the confirmation itself, and a
skipped answer adds nothing to the document — no gap marker.

Its purpose is narrow, and narrower than it may look: **a decision made but not yet built** is
invisible to all three sources, because the artifacts show what is, never what was decided last
week. A component moving to another system, a surface being deprecated in favor of a replacement
elsewhere — no graph field, README line, or filesystem signal can reach those.

**This prompt is not a substitute for reading the sources properly.** A fact already present in
`layers[]`, the README, or a module name is an extraction failure when the operator has to supply
it, not a fact the codebase could not hold. Do not lean on this prompt to cover a thin draft.

Corrections from this prompt land in the body with the rest of the description and are recorded as
`extracted-and-corrected`.

One interaction, about content already extracted — never a request to author from nothing. Three
outcomes:

| Outcome | Body | Provenance records |
|---|---|---|
| Confirmed | the derived description stands | extracted-and-confirmed |
| Corrected | **the correction** lands in the body; the original is **not** retained beside it | extracted-and-corrected |
| Refused or unavailable | the draft proceeds, description attributed to its sources | extracted-unconfirmed |

**The flow never stalls on a confirmation.** No answer is a valid outcome with its own provenance
record, not a reason to wait.

**This is the only confirmation in the flow.** Graph-derived structure — layers, languages,
frameworks, tour order — is **attributed, not confirmed section-by-section**. The operator edits the
draft afterward if it is wrong; that is cheaper than a per-section confirm-or-correct cycle, and it
is why this flow has one confirmation instead of seven.

### The User-Provided Concept contract

The concept guide is a **cross-repo dependency**: it lives in `ai-project-guide`, which updates
independently of squadron. Its layout is therefore **verified at write time, never assumed**.

**Before any write**, run both checks:

**Check 1 — the guide is readable** at:

```
project-documents/ai-project-guide/project-guides/guide.ai-project.000-concept.md
```

Unreadable or absent → **stop**, naming the path. If the **whole ai-project-guide tree** is absent,
name the setup step (`cf init` / `/cf:onboard`) instead of just the file — the operator's problem is
that setup has not run, and naming a single missing file would send them looking for the wrong thing.

**Check 2 — the section title is exactly right.** The guide's document-structure block must contain a
section titled exactly:

```
## User-Provided Concept
```

Absent or renamed → **stop**, naming the guide, the expected title, and that **the layout appears to
have changed upstream**. Never write to a substitute section, and never write to a remembered layout.

**Neither failure is a gap marker.** A gap marker means "this document is missing something"; these
two mean **"this document cannot be correctly written at all"**. Nothing is written on either path.

**Write rules for the section:**

- **Verbatim** — the operator's answers exactly as given. Never summarized, never reworded, never
  grammar-corrected. Their words are the artifact.
- **Preserve what is there** — pre-existing section content survives untouched; new answers **append
  below, under a dated subheading** (`### {YYYYMMDD}`).

### Re-run semantics

This flow's output path is fixed, so a re-run meets an existing document.

- **No existing document** → write it.
- **Existing document** → **never overwrite.** Report that it exists, offer **augment or stop**, and
  **stop is the default** — an unattended or ambiguous answer stops.

**Augment** does two things and nothing else:

1. **Appends to User-Provided Concept** per the preservation rule above (dated subheading, verbatim).
2. **Refills only the Refined Concept sections that are empty or hold exactly a `[GAP: ...]`
   marker** — the **mechanical refillability test**. A section holding real content is left alone,
   byte-identical.

**The augment interaction:** an augment run performs the flow's **normal interview** — the two fixed
questions, once — and those answers are what the append carries. A stopped run asks nothing at all.
There is no separate augment-only question set; the flow has no other source for appended
User-Provided Concept content.

**A human-edited concept is never rewritten from a graph.** The refillability test is mechanical
precisely so that this rule needs no judgment: content means keep, empty-or-gap means refill.

### `[INFERRED]` governance for this flow

The shared **Gap markers** section reserves `[INFERRED]` for this flow. Unlike the comprehension
flow — where every claim traces to a named field and any `[INFERRED]` marker is a defect — a
concept's Solution Approach genuinely infers from indirect evidence: tour ordering implying
importance is a claim the `tour[]` field does not literally make.

The checkable rule:

> A sentence carries `[INFERRED]` when it is derived from a named graph field but **asserts something
> the field does not literally state**. A sentence that **restates** a field carries no marker. A
> sentence with **no source** behind it does not belong in the document.

**Prose sources interact with this rule by citation, not inference.** A claim the README states is
**cited to `README.md` and carries no marker** — the source literally says it. Inferring from prose
and marking the result `[INFERRED]` misreads the rule: the marker's home is **graph-structural
inference**, not "anything squadron concluded".

**A PM-confirmed inference stays marked.** Confirmation changes the **provenance entry**, not the
body. An inference that a human agreed with is still an inference, and a reader six months later
needs to see that.

**Every `[INFERRED]` sentence is listed in the provenance block**, alongside gap markers.

### Output conventions

**Path:**

```
project-documents/user/project-guides/000-concept.{project}.md
```

`{project}` is resolved **from the cf project registration** — **never `project.name` from the
graph**. The graph carries a distribution name, which is not the project name: on squadron the graph
says `squadron-ai` while the project is `squadron`.

**Where the two differ**, the difference is **stated in the Overview** and the graph's value is
**recorded in provenance**. A reader who sees only one of the two names cannot tell which artifact
they are holding.

**Frontmatter:**

```yaml
---
docType: concept
layer: project
phase: 0
phaseName: concept
project: {project}
audience: [human, ai]
description: Concept for {project}
dependsOn: []
dateCreated: {YYYYMMDD}
dateUpdated: {YYYYMMDD}
status: not_started
model: {id of the model generating this document}
---
```

**`model:` follows the rule in Generated document conventions above, unchanged**: the real generating
model id, or an explicit stop. Never a placeholder, never copied from another document.

**Provenance block** — the shape from **Document Conventions** above, with concept-specific content:

- **Generated by** — this flow, and the model id that produced the document.
- **Generated on** — the date of this run.
- **Source** — the graph (with its identity), the README when one was read, the filesystem signals
  checked, and the concept guide path **with a statement that its User-Provided Concept section was
  verified present**.
- **Section sourcing** — one outcome per section, drawn from this set and no other:
  `extracted-from-graph`, `extracted-from-prose` (with the file cite), `observed-signals`,
  `interview`, `extracted-and-confirmed`, `extracted-and-corrected`, `extracted-unconfirmed`,
  `declined`, `gap`.
- **Engagement questions** — both questions, each marked answered or declined.
- **Inferred claims** — every `[INFERRED]` sentence, or an explicit statement that there are none.
- **Flagged gaps**, **staleness**, **review state** — as in the shared block.

## Flow: Initiative Candidates

Proposes initiative-shaped work items from the knowledge graph, written to a standalone
`{index}-analysis.initiative-candidates.md` and never into `001-initiative-plan.{project}.md`.

Run **Preflight: Graph Contract** in full first, then check the preconditions below, then derive,
then confirm, then write.

### Preconditions

**1. The graph is present.** This is the shared **Preflight: Graph Contract** above, executed
unchanged — location, validation, staleness, hygiene. This flow adds no hygiene behavior of its own
and skips none; do not re-implement any part of the contract here.

**2. The project name resolves** from the cf project registration. **Never from the graph** — see
**Output conventions** above. If no registration resolves a name, **stop**, naming the setup step.

**The concept document is not a precondition.** Its absence is an observation this flow records, not
a stop — see "The optional concept read" below.

**No `/cf:onboard` boundary concern applies here**, unlike Flow: Concept Generation above. This flow
writes to `analysis/`, which Flow: Comprehension Analysis already writes to, so it requires nothing of
`project-guides/` beyond what the two preconditions above already require.

### The candidate derivation model

A candidate is derived from exactly one of two signal classes:

| Signal | Source fields | What it observes |
|---|---|---|
| **Layer boundary** | `layers[]` (`name`, `description`, `nodeIds`) | A layer whose size or described responsibility marks it as a unit of work |
| **Complexity cluster** | file-level `nodes[]` (`complexity`, `filePath`) intersected with `layers[].nodeIds` | A concentration of `complex` files inside one layer |

**A candidate names exactly one signal.** Where the same layer supports both a boundary observation
and a complexity observation, that is two candidates or one — never one candidate citing two signals.
A candidate citing both is checkable against neither.

Field mechanics are **362's, cited and not restated**: the file-level definition, the `nodeIds |
length` counting rule with its type breakdown, the ordinal handling of `complexity`, and the layer
cross-check drift rule all apply unchanged. This flow reads strictly less of the graph than Flow:
Comprehension Analysis: no `tour[]`, no `entry-point` tags, no `meta.json` coverage read.

**The no-padding rule.** Candidates the graph does not support are not proposed. There is no target
count, no minimum, and no maximum. A padded list is indistinguishable from a real one to a reader, and
one invented candidate makes every other candidate in the document suspect.

**Emitting zero candidates is a success, not a failure.** The document is still written (on
confirmation), and it states that the graph supported no candidate, naming what it looked for.

### The optional concept read

When `project-documents/user/project-guides/000-concept.{project}.md` exists, read **two sections
only**: **User-Provided Concept** (the verbatim engagement answers, Q1 in particular) and **Problem &
Motivation** (the engagement half). Nothing else — not Solution Approach, not Initial Technical
Direction, not Development Approach. Those are graph-derived in the concept itself, so reading them
here would launder graph content through a second document and present it as independent
corroboration.

**What it changes, and what it does not:**

| Aspect | Effect of the concept |
|---|---|
| **Which candidates exist** | **None.** Candidates are derived from graph signals only. The concept never creates a candidate, never suppresses one, and never supplies one the graph does not support. |
| **Their order** | **This is the whole effect.** Candidates whose implicated layers align with the stated engagement intent are ordered first. |
| **Their scope statements** | The scope paragraph may frame the work in terms of the stated intent, provided every factual claim in it still traces to a graph signal. |

**The concept cannot manufacture a candidate.** This boundary is what keeps the no-padding rule
enforceable — if engagement context could originate candidates, "we're here to modernize" would
license proposing anything at all.

**Ordering influence is stated per candidate**, not applied invisibly: a candidate ordered up by the
engagement read says so, and names the concept as the reason.

**Degradation when absent.** No concept, or a concept lacking both named sections: candidates are
ordered by **signal strength alone** — descending count of `complex` file-level nodes for complexity
clusters, descending `nodeIds | length` for layer boundaries.

The degradation is **stated in the document body and recorded in provenance**, never silent:

```
Ordered by signal strength alone — no concept document was found at
project-documents/user/project-guides/000-concept.{project}.md. With one present, candidates
would additionally be ordered against the engagement intent it records.
```

A concept that exists but whose User-Provided Concept section records **both questions declined** is
treated as absent for ordering purposes, and the provenance says which of the two cases occurred. A
declined interview and a missing document are different facts, and collapsing them would hide that the
interview happened.

### Candidate record shape

Each candidate carries exactly five parts, in this order:

| # | Part | Sourced from | Rule |
|---|---|---|---|
| 1 | **Title** | authored | Names the work, not the observation. "Extract pipeline step classification" — never "Pipeline Orchestration is complex". |
| 2 | **Derivation signal** | `layers[]` or `complexity` | One signal, named explicitly, with the field it came from. |
| 3 | **Supporting node IDs** | `layers[].nodeIds`, file-level `nodes[]` | The actual ids. Every id must resolve to a node carrying a `filePath`; an unresolvable id is drift, reported per the 362 rule, and a candidate whose supporting ids are all drift is not emitted. |
| 4 | **Scope statement** | authored, constrained | **One paragraph.** Every factual claim traces to the signal or to a cited node. Effort estimates, timelines, and value judgments about the business are out of scope. |
| 5 | **Observed dependencies** | `edges[]` | Derived, never asserted — see below. An empty result is written as "none observed", not omitted. |

**Node IDs are cited, not summarized.** A candidate supported by fourteen nodes lists them; the
document is a working artifact for someone deciding whether to adopt the proposal, and "several files
in Pipeline Orchestration" is not checkable. Where a list is long, it is still written out — the
alternative is an unfalsifiable claim.

**The title and the scope statement are the only two authored parts** of the record, and both are
constrained by parts 2, 3, and 5, which are all extracted. That asymmetry is intentional: prose that a
reader can check against cited ids is safe; prose that stands alone is not.

### Dependency derivation

Dependencies between candidates come from `edges[]` between the layers each candidate implicates —
**observed, never asserted**.

Mechanics are **362's, unchanged**: endpoint resolution is a string parse of the edge's own
`source`/`target` id (the second colon-delimited field is the owning file's path, which resolves to a
layer), `imports` and `depends_on` edge types, self-references excluded. **No node is read to resolve
an endpoint**, and specifically no `function` or `class` node.

The derivation:

1. For each candidate, collect the set of layers its supporting nodes belong to.
2. For each ordered pair of candidates, count inter-layer `imports`/`depends_on` edges from the
   first's layers to the second's.
3. A non-zero count is a stated dependency, **carrying the count**.

**A stated dependency is a directional edge count, not a claim about sequencing.** The document says
"Candidate 3's layers hold 27 imports into Candidate 1's layers" — it does not say Candidate 1 must be
done first. That inference belongs to the human adopting the candidates.

Unresolvable endpoints are excluded from the count and reported as drift, per 362. Where two
candidates implicate the same layer, that overlap is stated rather than expressed as a dependency — a
layer does not depend on itself.

---

# Project documentation

## Why the graph contract lives in this file

The contract sections above (**Preflight: Graph Contract** and **Document Conventions**) are shared
by every capability-(a) flow in initiative 360 — slices 362, 363, and 364 extend *this file* rather
than importing a fragment.

They are **not** factored into a separate fragment file, and this is deliberate. The pack installer's
`_install_prefix()` ([installer.py:87](../../src/squadron/skills/installer.py#L87)) globs every `*.md`
in the pack directory and installs each one as its own skill. A `graph-contract.md` fragment would
therefore surface to users as a bogus installable command that does nothing on its own.

Slice 365 (`commands/sq/`) copies these conventions rather than referencing them: a first-party
squadron command cannot assume the analysis pack is installed.

## Relationship to `analyze-codebase-prompt.md`

`project-documents/user/reference/analyze-codebase-prompt.md` is squadron's pre-existing codebase
analysis prompt. It is **retained unchanged** as a reference document, and this skill adopted
**two of its conventions and none of its structure**:

**Adopted:**

- **Fact/inference discipline** — the explicit separation between what a source states and what a
  reader concludes from it. This skill's `[GAP: ...]` rule and its `[INFERRED]` governance above are
  that discipline applied to a graph-backed flow.
- **A data-lacking section says so and names what would supply it** — which is precisely the
  two-halves requirement on the gap marker.

**Not adopted:** its ten-part document template. That template was written for a probe-plus-Repomix
backend that reads source files directly; a knowledge graph cannot feed most of its parts, and
adopting the shape would have produced sections this flow can only fill with gap markers. The
extraction mapping table's seven sections are derived from what the graph actually carries.

Both paths exist on purpose: the reference prompt for a source-reading analysis, this skill for a
graph-backed one.
