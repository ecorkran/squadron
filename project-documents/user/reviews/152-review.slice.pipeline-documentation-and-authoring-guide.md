---
docType: review
layer: project
reviewType: slice
slice: pipeline-documentation-and-authoring-guide
project: squadron
verdict: PASS
sourceDocument: project-documents/user/slices/152-slice.pipeline-documentation-and-authoring-guide.md
aiModel: minimax/minimax-m2.7
status: complete
dateCreated: 20260410
dateUpdated: 20260410
findings:
  - id: F001
    severity: note
    category: naming-convention
    summary: "Built-in pipeline names differ from architecture naming convention"
    location: § Built-in Pipelines section
  - id: F002
    severity: note
    category: documentation-completeness
    summary: "`summary` action appears in action catalog but has no corresponding step type entry"
    location: Action Type Catalog vs Step Type Catalog
  - id: F003
    severity: concern
    category: documentation-accuracy
    summary: "`compact` step type described as alias; architecture defines it as standalone with different fields"
    location: § Step Type Catalog → `compact`
  - id: F004
    severity: note
    category: documentation-scope
    summary: "Collection loop binding syntax is deferred to 149 but documented as final"
    location: § `each` step type → Item fields accessible as `{variable.index}`
---

# Review: slice — slice 152

**Verdict:** PASS
**Model:** minimax/minimax-m2.7

## Findings

### [NOTE] Built-in pipeline names differ from architecture naming convention

The architecture defines four built-in pipelines with specific names:
- `slice-lifecycle`
- `review-only`
- `implementation-only`
- `design-batch`

The slice documentation uses shortened/more ergonomic names:
- `slice` (for `slice-lifecycle`)
- `tasks` (for the tasks + implementation segment)
- `implement` (for `implementation-only`)
- `review` (for `review-only`)

Additionally, the documentation includes `P1`, `P2`, `P4`, `P5`, `P6` pipelines that are not mentioned in the architecture. This appears to be an intentional extension of the built-in pipeline set beyond the minimum defined in the architecture, with the `example` pipeline serving as the primary authoring reference.

This is not an error — user-facing names can differ from internal identifiers — but the documentation should clarify the relationship (e.g., "The built-in pipeline `slice` is defined as `slice-lifecycle` internally").

---

### [NOTE] `summary` action appears in action catalog but has no corresponding step type entry

The Action Type Catalog lists `summary` as an action emitted by the `summary` step type, but the Step Type Catalog section only documents `compact` — not `summary` — as a step type with a standalone entry. The `summary` step type is described inline within the `compact` section as:

> **Purpose:** Generate a session summary and emit to configured destinations

This is present but easy to miss since there's no dedicated `summary` heading in the Step Type Catalog. The documentation is complete; the finding is informational only.

---

### [CONCERN] `compact` step type described as alias; architecture defines it as standalone with different fields

The documentation states:

> **`compact`**
> Purpose: Compress context at a step boundary (shorthand for `summary` with `emit: [rotate]`)

The architecture defines `compact` as a standalone step type with distinct fields:

```yaml
steps:
  - compact:
      keep: [design, tasks]      # what to preserve
      summarize: true            # update CF project summary
```

These are different parameters (`keep`, `summarize` vs `template`, `model`, `emit`, `checkpoint`). The "shorthand for summary with emit: [rotate]" description appears to conflate the `compact` step type with its relationship to the `compact` action, which IS invoked by both `compact` and `summary` steps.

If the implementation uses `keep:` and `summarize:` fields, the documentation is incorrect. If the implementation uses `template`, `model`, `emit`, then the architecture document may be outdated and this slice's documentation is correct for the implemented behavior.

The Notes section correctly avoids documenting `pool:` as an available feature, which is appropriate given the 160 scope boundary.

---

### [NOTE] Collection loop binding syntax is deferred to 149 but documented as final

The architecture states in Open Questions:

> **[DEFERRED → 149] Collection loop item binding:** How does `{slice.index}` resolve inside an `each` block? Simple string interpolation? Template engine? Full semantics (item type/schema, field traversal, missing field behavior, read-only binding) are a 149 design decision.

The slice documentation documents `{variable.index}`, `{variable.title}` as the item field access pattern. This is reasonable illustrative syntax and consistent with the architecture's illustrative example (`{slice.index}`), but the precise binding mechanism is not yet finalized in the architecture.

Since this slice only produces documentation and no code changes, documenting the binding syntax as the user-facing convention is appropriate. The guide should ideally note "syntax matches the architecture example; see future release notes for binding semantics" to set correct expectations.

---
