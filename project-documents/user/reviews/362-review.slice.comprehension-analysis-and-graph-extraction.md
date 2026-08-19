---
docType: review
layer: project
reviewType: slice
slice: comprehension-analysis-and-graph-extraction
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/362-slice.comprehension-analysis-and-graph-extraction.md
aiModel: deepseek/deepseek-v4-flash-0731
status: complete
dateCreated: 20260819
dateUpdated: 20260819
reviewedSha: f434a1a63742ad00574386ef116f366300b37a5e
findings:
  - id: F001
    severity: concern
    category: architectural-boundary
    summary: "Function/class edge-endpoint resolution conflicts with the architecture's \"not read\" rule"
    location: "project-documents/user/slices/362-slice.comprehension-analysis-and-graph-extraction.md#section-detail"
  - id: F002
    severity: concern
    category: error-handling
    summary: "Dependency section lacks an explicit failure path for unresolvable edge endpoints"
    location: "project-documents/user/slices/362-slice.comprehension-analysis-and-graph-extraction.md#section-detail"
  - id: F003
    severity: concern
    category: scope
    summary: "New sections extend the architecture's four-part comprehension-document shape without a stated rationale"
    location: "project-spec/user/slices/362-slice.comprehension-analysis-and-graph-extraction.md#technical-scope"
  - id: F004
    severity: pass
    category: alignment
    summary: "The `analyze-codebase-prompt.md` reuse decision correctly closes the architecture's open question"
    location: "project-documents/user/slices/362-slice.comprehension-analysis-and-graph-extraction.md#technical-decisions"
  - id: F005
    severity: pass
    category: alignment
    summary: "The two corrections to the 361 contract are properly scoped as a defect fix rather than an escalation"
    location: "project-documents/user/slices/362-slice.comprehension-analysis-and-graph-extraction.md#corrections-to-the-361-contract"
  - id: F006
    severity: pass
    category: error-handling
    summary: "The fallback column and failure-handling coverage are consistent for almost all new input paths"
    location: "project-mark/user/slices/362-slice.comprehension-analysis-and-graph-extraction.md#extraction-mapping"
  - id: F007
    severity: pass
    category: dependency-direction
    summary: "Integration points respect the dependency graph and slice boundaries"
    location: "project-documents/user/slices/362-slice.comprehension-analysis-and-graph-extraction.md#integration-points"
---

# Review: slice — slice 362

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4-flash-0731

## Findings

### [CONCERN] Function/class edge-endpoint resolution conflicts with the architecture's "not read" rule

The architecture is explicit: "file-level node types ... are sufficient for planning artifacts; function- and class-level nodes are not read." The slice restates this even more strongly in "Read discipline" and Success Criterion 9 ("no function- or class-level node is read").

But "Section detail", item 6, says:

> Function- and class-level edge endpoints are resolved to their owning file's layer rather than dropped, so a `calls` edge between two functions in different layers still counts as an inter-layer signal.

Resolving a `function:*`/`class:*` edge endpoint to its owning file's layer requires at least a lookup of function/class nodes (id/type/file association) — which reads those nodes, even if only briefly, and logic assumes the graph is large precisely so these 687 nodes can be excluded. The design needs to do one of the following:

- explicitly define that such lookups are allowed for the exclusion filter only in a metadata-only, field-scoped form and that the huge summary/complexity payload of those nodes is never materialized; or
- limit inter-layer dependency edges to file-level endpoints only; or
- state clearly what a "resolved" function/class node is in jq — e.g., by id-prefix mapping — and stop claiming in Success criterion 9 that no function/class node is ever read in any form.

As written, the two statements contradict each other, and a capture team will pick the wrong one.

### [CONCERN] Dependency section lacks an explicit failure path for unresolvable edge endpoints

The slice carefully enumerates failure modes for most inputs: empty `tour`, missing `entry point`, missing `meta.json`, `analyzedFiles` mismatch, `config.json` unreadable, `.understandignore` missing, any `nodeIds` entry resolving to a function/class node ("upstream drift"). The dependency-observations transformation — new in this slice — has no such path.

The excise text says "Map an edge to a layer through the node's layer membership, which is now unambiguous — every file-level node belongs to one layer". But what happens when an edge's `source` or `target` does not resolve to *any* node, or resolves to a node with no file-level owner (orphaned ID), or the type-prefix no longer matches? In a different graph — the design correctly notes the correction measures only the v2.8.1 graph — that path would otherwise silently skip the unresolved edge or break the section. The fallback table (row 6) only covers the case "preflight rejects empty edges", not "an edge has unresolvable endpoints". Add one line to the mapping/ semantics: an edge whose endpoint cannot be resolved to a layer is not silently dropped — it is either reported as drift or closed with `[GAP: ...]` naming the unresolved edge id. This keeps the "no third option" covenant in the fallback column complete.

### [CONCERN] New sections extend the architecture's four-part comprehension-document shape without a stated rationale

The architecture defines the comprehension analysis as "the structural findings: layers, complexity hotspots, entry points, dependency observations" — four sections. The slice adds three more: **Project identity**, **Suggested reading order**, and **Coverage and scope limits**. Reading order is plausibly within the spirit of the architecture (the pre-graph `tour[]` contract is not a strong planning signal). The coverage section makes sense given the architecture's `.understandignore` is described as something squadron "may reference when explaining coverage gaps". But the projection is not explicitly grounded in the architecture; the concept doc's `Initial Technical Direction` — not the analysis doc — is where the architecture expects `project.languages/frameworks`/config nodes to feed. The mapping table is a core deliverable, but the slice says at the start "No new file is stored outside ..." while adding two sections beyond the architecture's declared shape — this is a mild scope-overshoot. Either the section should be explicitly justified as "an architecture-defined slot" (e.g., "coverage" is the gap-marker counterpart the architecture envisions, and "project identity" is a pre-analysis block from `project` which the architecture uses in flow step 3), or the `technical scope` should say "adds beyond the architecture's documented four, for reasons X and Y." As it stands, the reviewer cannot tell whether the new sections were sanctioned.

### [PASS] The `analyze-codebase-prompt.md` reuse decision correctly closes the architecture's open question

The architecture's open question ("Reuse of `analyze-codebase-prompt.md` — how much of its template and `[INFERRED]` convention choices transfer") is settled well: the slice adopts only the fact/inference discipline, adopts no report structure, and retains the document "unchanged", except for a one-line cross-reference. This is also consistent with the design goal "Consume, do not re-implement" (the graph-backed path never should be forced into a template built for `codebase-probe.py` + Repomix), and the "[INFERRED] defined but not used" decision is a precise answer to the architecture's gap-marker question (it defers the marker's use to slice 363, where real inference occurs). This is the most clearly aligned part of the slice.

### [PASS] The two corrections to the 361 contract are properly scoped as a defect fix rather than an escalation

The slice correctly notes that in both corrections the real graph matches the architecture's documented contract — "every file is the only layer" and file-level node types — while the 361 skill text diverged. So the fixes are internal corrections to the skill, not changes to the upstream contract, and therefore don't violate the architecture's "the graph is an input, not a dependency" principle. The retained cross-check (if `nodeIds` ever resolves to a function/class node, report upstream drift rather than filtering it) also aligns with the architecture's "never proceed on partial data silently".

### [PASS] The fallback column and failure-handling coverage are consistent for almost all new input paths

The slice's mapping table — source fields, ordering, and fallback — is the strongest part of the design. It ensures a "document with gap markers is the expected output for a thin input, not a failure" (architecture) and makes "no third outcome" binding. The walkthrough concretely exercises the new failure modes: empty `tour`, missing `entry-point` tag, negative `meta.json`, `analyzedFiles` mismatch, `.understandignore` unreadable, and replay of `config.json`. This sets a strong precedent for the detailed paths (the dependency-edge endpoint gap in the previous finding aside).

### [PASS] Integration points respect the dependency graph and slice boundaries

The slice's declared dependency direction is correct: it consumes 361's preflight/provenance/gap-marker conventions unchanged and provides material to 363 (extraction mapping, project identity) and 364 (corrected layer composition/file-level definition); 365 and 366 are explicitly delegated elsewhere. The frontmatter `parent` field is to the slice plan, not the architecture (not an issue). The boundary laid out in "Excluded", e.g. dispatcher/ `communicating" being 366's scope, keeps the slice appropriately narrow even though the architecture eventually wants the skill correctly routed — that's precisely what the slice sequencing is for.
