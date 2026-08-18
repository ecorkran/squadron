---
docType: review
layer: project
reviewType: slice
slice: graph-contract-and-provenance
project: squadron
verdict: PASS
sourceDocument: project-documents/user/slices/361-slice.graph-contract-and-provenance.md
aiModel: minimax/minimax-m3
status: complete
dateCreated: 20260818
dateUpdated: 20260818
reviewedSha: 2904bebf6750aa40e0f4b12649aeca29cd0dafd5
findings:
  - id: F001
    severity: pass
    category: uncategorized
    summary: "Failure modes enumerated with distinct, specific handling"
    location: "361-slice.graph-contract-and-provenance.md#validation-absence-vs-malformation-two-distinct-failures"
  - id: F002
    severity: pass
    category: uncategorized
    summary: "Staleness handling matches architectural intent"
    location: "361-slice.graph-contract-and-provenance.md#staleness-warn-with-distance-never-block"
  - id: F003
    severity: pass
    category: uncategorized
    summary: "Hygiene idempotency via semantic `git check-ignore`"
    location: "361-slice.graph-contract-and-provenance.md#gitignore-hygiene-semantic-idempotency-via-git-check-ignore"
  - id: F004
    severity: pass
    category: uncategorized
    summary: "Provenance block placement and format align with architecture"
    location: "361-slice.graph-contract-and-provenance.md#provenance-block-format"
  - id: F005
    severity: pass
    category: uncategorized
    summary: "Gap-marker syntax resolved consistent with architectural open question"
    location: "361-slice.graph-contract-and-provenance.md#gap-marker-syntax-settled-here-used-by-every-generated-document"
  - id: F006
    severity: pass
    category: uncategorized
    summary: "Scope correctly bounded — proves contract via minimal consumer"
    location: "361-slice.graph-contract-and-provenance.md#technical-scope"
  - id: F007
    severity: pass
    category: uncategorized
    summary: "Read discipline enforced via scoped `jq` selections"
    location: "361-slice.graph-contract-and-provenance.md#graph-location-and-read-discipline"
  - id: F008
    severity: pass
    category: uncategorized
    summary: "Output path, docType, index range, and status match architecture"
    location: "361-slice.graph-contract-and-provenance.md#generated-document-conventions"
  - id: F009
    severity: pass
    category: uncategorized
    summary: "Delivery surface matches architecture"
    location: "361-slice.graph-contract-and-provenance.md#dependencies"
  - id: F010
    severity: pass
    category: uncategorized
    summary: "Verification walkthrough exercises each failure mode end to end"
    location: "361-slice.graph-contract-and-provenance.md#verification-walkthrough"
  - id: F011
    severity: note
    category: uncategorized
    summary: "`config.json` and `.understandignore` not addressed"
    location: "361-slice.graph-contract-and-provenance.md#interfaces-required"
  - id: F012
    severity: note
    category: uncategorized
    summary: "`analyzedFiles` field from `meta.json` unused"
    location: "361-slice.graph-contract-and-provenance.md#staleness-warn-with-distance-never-block"
  - id: F013
    severity: note
    category: uncategorized
    summary: "Frontmatter `model` field is novel and may need schema validation"
    location: "361-slice.graph-contract-and-provenance.md#generated-document-conventions"
  - id: F014
    severity: pass
    category: uncategorized
    summary: "`[INFERRED]` convention preserved rather than replaced"
    location: "361-slice.graph-contract-and-provenance.md#gap-marker-syntax-settled-here-used-by-every-generated-document"
  - id: F015
    severity: pass
    category: uncategorized
    summary: "Architectural risk (upstream contract drift) addressed in slice Risk Assessment"
    location: "361-slice.graph-contract-and-provenance.md#risk-assessment"
---

# Review: slice — slice 361

**Verdict:** PASS
**Model:** minimax/minimax-m3

## Findings

### [PASS] Failure modes enumerated with distinct, specific handling

The slice distinguishes three graph failures (absent, unparseable, malformed) with distinct messages, an explicit empty-tour tolerance, and clear handling for git-unavailable. This matches the architecture's "Absence and malformation are different failures and get different messages" and "never skip silently" requirements.

### [PASS] Staleness handling matches architectural intent

The slice implements the architecture's "warn, never block" rule with three sub-cases (matched, behind, unknown-distance), records the skip reason in provenance when git is unavailable, and surfaces the PM choice in provenance. The architecture only specified two cases; the slice's third case (unknown-distance for rebase/amend/shallow clone) is a reasonable extension that prevents fabricated distance numbers.

### [PASS] Hygiene idempotency via semantic `git check-ignore`

Using `git check-ignore -q` to verify coverage semantically (not pattern-grep) directly implements the architecture's "matched semantically, so an existing broader ignore of `.understand-anything/` satisfies it and is not duplicated." The non-fatal, never-silent failure handling and "What is never acceptable is proceeding as though the write succeeded" are preserved verbatim in spirit.

### [PASS] Provenance block placement and format align with architecture

Body prose (not frontmatter), placed immediately after H1, content matches the architecture's bullet list (source identity, staleness state, sourcing per section, gaps), and "review state" line solves the architecture's "makes `status: not_started` legible on a generated draft" requirement explicitly. Format obeys its own gap-marker rule (missing meta.json yields `[GAP: ...]` in Graph identity line).

### [PASS] Gap-marker syntax resolved consistent with architectural open question

The slice settles the architecture's open question with `[GAP: {what} — {which input}]` as a sibling (not competitor) to the retained `[INFERRED]` convention, with both body placement and provenance-block listing. Body placement matches the architecture's "Gap markers appear in the document body, so the PM sees them where the content would have been."

### [PASS] Scope correctly bounded — proves contract via minimal consumer

The slice explicitly excludes concept generation (363), interview (363), initiative candidates (364), deep extraction mapping (362), and dispatcher/install changes (366). The shallow comprehension output is the documented "proving-consumer depth" that exercises every contract element. This is the architectural enablement pattern called out in the slice's Value section.

### [PASS] Read discipline enforced via scoped `jq` selections

The slice's read discipline (never load whole graph, scope all reads to named fields, never read function/class-level nodes) directly implements the architecture's "Grep for the needed section before reading; never load the whole file into context" and "function- and class-level nodes are not read."

### [PASS] Output path, docType, index range, and status match architecture

The slice uses `user/analysis/{index}-analysis.codebase-comprehension.md`, `docType: analysis`, the 940-949 reserved range with sanctioned overflow past 949, and `status: not_started` — all matching the architecture's Output Conventions exactly.

### [PASS] Delivery surface matches architecture

Adding `commands/analysis/understand.md` for the existing `analysis` pack is consistent with the architecture's "Capability (a) — `understand` ships as a skill in the existing bundled `analysis` pack" and with the slice 340 install behavior cited as the only prerequisite. No `src/squadron/` changes are needed, matching the architecture's "no installer, manifest, or CLI change."

### [PASS] Verification walkthrough exercises each failure mode end to end

The walkthrough covers all eight scenarios (happy path, idempotent hygiene, broader-ignore accepted, read-only gitignore, malformed graph with three variants, absent graph, no git, installation). Each scenario maps to a success criterion and an architectural failure mode. This is appropriate given the slice adds no Python and therefore no unit tests.

### [NOTE] `config.json` and `.understandignore` not addressed

The architecture documents that `config.json` (with `autoUpdate`, `outputLanguage`) is "read only, never written by squadron" and that `.understandignore` "may reference it when explaining coverage gaps." The slice's Interfaces Required section lists only `knowledge-graph.json` and `meta.json`. This is acceptable for 361's proving depth but should be acknowledged by 362 if it plans to consume `config.json` settings or cite `.understandignore` in coverage gap explanations.

### [NOTE] `analyzedFiles` field from `meta.json` unused

The architecture lists `analyzedFiles` as a `meta.json` field, but the slice uses only `gitCommitHash` and `lastAnalyzedAt`. Not a violation — the slice has no use for analyzedFiles count at proving depth — but 362 may want to surface it in the Source line of the provenance block for the deepened analysis.

### [NOTE] Frontmatter `model` field is novel and may need schema validation

The architecture states frontmatter is schema-validated against a fixed schema. The slice adds `model: {generating model id}` to the frontmatter template; this field is not enumerated in the architecture or visibly required by any prior generated document. Worth confirming the schema in `src/squadron/documents/schema.py` permits it before relying on it as part of the contract.

### [PASS] `[INFERRED]` convention preserved rather than replaced

The slice explicitly preserves the `[INFERRED]` convention from `analyze-codebase-prompt.md` as a sibling marker with `[GAP: ...]`, matching the architecture's "useful references when designing the comprehension output" framing and its "retained, not superseded" prior-art disposition. The slice defers [INFERRED] use to 362, consistent with the architecture's open-question resolution strategy.

### [PASS] Architectural risk (upstream contract drift) addressed in slice Risk Assessment

The slice's Risk Assessment names upstream contract drift as the initiative's stated medium risk, explains the validation strategy that mitigates it, and adds a stop-and-escalate rule ("If the walkthrough's real graph does not match the architecture's documented shape, stop and raise to the PM before proceeding"). This directly addresses the architecture's "A renamed field in a future release must surface as a loud failure, never as a silently thinner document."
