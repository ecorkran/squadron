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
| Layers | `jq -r '.layers[] \| {id, name, description, count: (.nodeIds\|length)}'` |
| File-level nodes | `jq -r '.nodes[] \| select(.type != "function" and .type != "class") \| {id, filePath, summary, complexity}'` |
| Tour steps | `jq -r '.tour[] \| {order, title, nodeIds}'` |
| Edge aggregates | `jq -r '[.edges[].type] \| group_by(.) \| map({type: .[0], n: length})'` |

Select **only** the fields named in that table. A node carries `name`, `tags`, `lineRange`, and
`languageNotes` as well; none of them are read at this depth.

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

**Not consumed at this depth** (deferred to slice 362, recorded here so the next author sees the
deferral rather than rediscovering it):

- `config.json` and `.understandignore` in the graph root — they describe how the upstream plugin was
  configured and what it excluded. Reading them would let a generated document state its own
  coverage limits, which is a real improvement and out of scope here.
- `meta.json`'s `analyzedFiles` count — a coverage signal, same reasoning.
- Node `type` values beyond `file`, `function`, and `class` (this graph also carries `pipeline` and
  `config` nodes).

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

At this slice's depth `[INFERRED]` should not be needed — every claim traces to a named graph field.
If a section cannot be written without inference, that is a signal the section is out of scope here.
Governing its use in deeper analysis belongs to slice 362.

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

## Flow: Comprehension Analysis

This is the default flow and the only one this skill implements. Run **Preflight: Graph Contract** in
full first — location, validation, staleness, hygiene — then extract and write.

Any argument other than the comprehension default is **unrecognized**. Say so and stop; do not guess
at intent. The concept flow and the initiative-candidates flow are slices 363 and 364.

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

**1. Layer architecture** — from `layers[]`.

For each layer: `name`, `description`, and its node count.

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

**2. Complexity hotspots** — from file-level `nodes[]`.

Nodes in the highest `complexity` tier, each with its `filePath` and `summary`. File-level only
(`select(.type != "function" and .type != "class")` — see the file-level definition in the read
discipline above).

`complexity` is an **ordinal string**, not a number — observed values are `simple`, `moderate`, and
`complex`. Do not sort it numerically; `sort_by(-.complexity)` fails outright on a string, which is
the correct loud failure. Select the top tier by value. If the upstream plugin ever emits a value
outside the observed set, report it rather than bucketing it into a known tier.

**3. Suggested reading order** — from `tour[]`.

Step titles in `order`. If `tour` is empty, this section is a `[GAP: ...]` marker naming the tour
field and the input that would supply it — preflight has already warned in this case.

**4. Dependency observations** — from `edges[]`.

Edge-type counts, and the strongest inter-layer `imports` / `depends_on` connections.

**Do not add sections.** Section depth, ordering, fallback behavior, and any additional sections are
slice 362's scope. This slice proves the contract works end to end at the shallowest depth that
exercises every element of it; growing the list here would move that boundary.

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
