---
docType: review
layer: project
reviewType: arch
slice: document-intelligence
project: squadron
verdict: PASS
sourceDocument: project-documents/user/architecture/360-arch.document-intelligence.md
aiModel: minimax/minimax-m3
status: complete
dateCreated: 20260818
dateUpdated: 20260818
reviewedSha: e7300471d9d2baa742dedd32a797a211328b8a21
findings:
  - id: F001
    severity: concern
    category: consistency
    summary: "Output directory claim in Output Conventions contradicts Capability 1"
    location: "360-arch.document-intelligence.md#Output-Conventions"
  - id: F002
    severity: concern
    category: completeness
    summary: "Provenance location is mandated but undefined in the schema"
    location: "360-arch.document-intelligence.md#Capability-1:-Comprehension-→-Planning-Artifacts"
  - id: F003
    severity: concern
    category: completeness
    summary: "Initiative plan candidate generation has no defined heuristic or output shape"
    location: "360-arch.document-intelligence.md#Capability-1:-Comprehension-→-Planning-Artifacts"
  - id: F004
    severity: concern
    category: completeness
    summary: "\"Structural vs. intent\" interview boundary is undefined"
    location: "360-arch.document-intelligence.md#Interview-scope"
  - id: F005
    severity: concern
    category: completeness
    summary: "Status value for a freshly generated document is unspecified"
    location: "360-arch.document-intelligence.md#Status-values"
  - id: F006
    severity: concern
    category: completeness
    summary: ".gitignore write is unattributed and its failure mode is unchecked"
    location: "360-arch.document-intelligence.md#Working-tree-hygiene"
  - id: F007
    severity: concern
    category: feasibility
    summary: "No format-version detection for understand-anything output"
    location: "360-arch.document-intelligence.md#The-understand-anything-Output-Contract"
  - id: F008
    severity: concern
    category: dependencies
    summary: "\"Sacred\" User-Provided Concept section is an unstated cross-initiative dependency"
    location: "360-arch.document-intelligence.md#Outputs"
  - id: F009
    severity: concern
    category: completeness
    summary: "Capability (b) command-registration impact is not described"
    location: "360-arch.document-intelligence.md#Delivery"
  - id: F010
    severity: concern
    category: antipatterns
    summary: "Translation principles are stated but not enforced by design"
    location: "360-arch.document-intelligence.md#Translation-rules"
  - id: F011
    severity: note
    category: feasibility
    summary: "Staleness check implicitly requires git"
    location: "360-arch.document-intelligence.md#Flow"
  - id: F012
    severity: note
    category: completeness
    summary: "Token-efficient graph reading is a hint, not an extraction strategy"
    location: "360-arch.document-intelligence.md#Read-discipline"
---

# Review: arch — slice 360

**Verdict:** PASS
**Model:** minimax/minimax-m3

## Findings

### [CONCERN] Output directory claim in Output Conventions contradicts Capability 1

The Output Conventions section states: "Both capabilities write to the existing `project-documents/user/analysis/` directory with the existing `docType: analysis`." This is directly contradicted by the Capability 1 → Outputs section, which writes `project-documents/user/project-guides/000-concept.{project}.md` — a different directory. Capability 1 writes to two different directories (`project-guides/` for the concept, `analysis/` for the structural findings); the "both" generalization is false. The "No new directory" follow-on claim is also questionable for the concept path. Tighten to something like "Both capabilities use existing docType conventions and require no gate change; Capability 1 writes to both `project-guides/` and `analysis/` per existing convention."

### [CONCERN] Provenance location is mandated but undefined in the schema

The staleness policy states: "the warning must be prominent and must appear in the generated document's provenance, because the genuine failure mode is a confidently wrong concept doc built on a stale graph without the reader knowing." But the document field schema (Capability 2) and the Capability 1 output descriptions do not include a `provenance` field. The Capability 1 outputs only specify that interview responses go "verbatim in the **User-Provided Concept** section." Where does the staleness warning live — body prose, a dedicated section, a frontmatter field? This is a load-bearing decision (the warning's purpose is reader awareness; if it's in an unread place it fails its purpose) left implicit.

### [CONCERN] Initiative plan candidate generation has no defined heuristic or output shape

The document says initiative-plan candidates are "proposed initiatives derived from layer boundaries and complexity clustering, offered for PM review." The signals (layer boundaries, complexity hotspots) are stated, but the design does not specify: (a) the heuristic for translating those signals into initiative-shaped proposals, (b) the candidate artifact's structure (title? scope statement? rationale? linked layers?), (c) where candidates are written (project-guides? a proposals directory? a transient file?), (d) the docType/filename, or (e) what the PM actually confirms when they confirm. The "Written only on explicit confirmation" clause controls *when* but not *what*. This is the "step 3: magic happens" antipattern applied to a deliverable that is described as significant enough to merit a separate paragraph in the architecture.

### [CONCERN] "Structural vs. intent" interview boundary is undefined

The document says "Structural questions are never asked — the graph already answered them" and "Question set is bounded and derived from the concept guide's own section list." But "structural" is never defined as a property the skill can recognize. The interview-scope table maps each concept section to a source ("Graph", "Interview", "Graph + interview confirmation") but does not state the per-section rule for *how the skill decides* what to ask. The architecture should state the principle (e.g., "for each section, attempt to extract from the named graph fields; ask the human only on absence or low confidence") even if the detailed mapping is slice design. As written, the core correctness criterion of Capability 1 — ask too few and the concept is fabricated, ask too many and the user is annoyed — is left entirely to implementation judgment.

### [CONCERN] Status value for a freshly generated document is unspecified

The document specifies the status enum (`complete`, `in_progress`, `not_started`, `deprecated`, `deferred`) and that generated frontmatter uses only enum members. It does not state which enum value a freshly generated concept, analysis, or overview document receives. A machine-generated concept is not `not_started` (work has been done), not cleanly `in_progress` (no one is working on it), and not safely `complete` (it has not been PM-reviewed). The architecture elsewhere emphasizes that "an unreviewed generated [artifact] is worse than none" for the initiative plan, but the same caution applies to the concept — yet the status enum has no `needs_review` or equivalent. This is a load-bearing decision left implicit. The `not_started` value in this document's own frontmatter is the *initiative* status, not the generated-artifact status, and the distinction should be made explicit.

### [CONCERN] .gitignore write is unattributed and its failure mode is unchecked

The "Hygiene" step says "Ensure `.gitignore` contains an entry for the plugin's scratch directories, idempotently." It does not say which component performs the write (the skill itself? a one-time setup command?), when (every skill run? only on first detection?), or what happens if the write fails (file is read-only, `.gitignore` doesn't exist, permission denied, repo is not a git repo). The skill's contract should be explicit: a side effect this visible to the user's working tree should be named in the skill's documented behavior, not just in an "Architecture" sub-section. The current placement under "Working-tree hygiene" reads as a passive description, not a behavioral commitment.

### [CONCERN] No format-version detection for understand-anything output

The document pins the plugin at v2.8.1 and notes it is "upstream-maintained and actively developed." It defines an output contract (a table of paths and their roles) but provides no mechanism for detecting when that contract changes. A v2.9.0 that renames `tour[]` to `walkthrough[]` or changes the `id` prefix scheme would silently produce wrong output from a skill that reads expected fields. At minimum, the skill should validate that the required top-level fields exist (`project`, `nodes`, `edges`, `layers`, `tour`) and report a clear error if not. The current "if the graph is missing, report and stop" only covers *absence*, not *malformation*, and a major version bump is more likely to be a malformation than a complete absence.

### [CONCERN] "Sacred" User-Provided Concept section is an unstated cross-initiative dependency

The skill writes interview responses "verbatim in the **User-Provided Concept** section (which is sacred per project convention and never rewritten)." The convention is referenced but not documented in this architecture — there is no link to the concept guide, no statement of the minimum structural requirement the skill relies on, and no indication of which initiative owns the convention. If a future initiative changes the concept document layout (renames the section, makes it optional, removes it), this skill silently breaks or, worse, writes to a section that no longer means what it used to. The architecture should either link to the governing convention or restate the minimum requirement (a section the skill preserves verbatim, identified by a name) explicitly.

### [CONCERN] Capability (b) command-registration impact is not described

For Capability (a), the document is explicit: "no installer, manifest, or CLI change." For Capability (b), the document says it "ships as a first-party command in `commands/sq/`" without the analogous disclaimer. First-party commands have a registration mechanism somewhere (manifest, installer, auto-discovery, hard-coded dispatcher). The reader has to assume the same constraints apply. State them — or state the differences. The asymmetry is more confusing than illuminating.

### [CONCERN] Translation principles are stated but not enforced by design

The translation rules state "Status is honest. Not-started work is described as planned, not implied complete" and "Derive, never invent. Every claim traces to an input artifact. If a benefit is not supported by the concept or initiative plan, it is not asserted — the skill flags the gap for the PM instead." These are *principles*, not design. The architecture does not say: (a) how the skill detects a claim that cannot be traced to a source, (b) what the skill does on detection (regenerate, fail loudly, flag and proceed), (c) whether the gap-flag is in the output document or a separate report, or (d) how "honest" is verified post-generation. "The skill flags the gap" is mentioned once for the Benefits field but is not generalized to Approach, Scope, or Risks. Without an enforcement story, a generation step that overstates progress or fabricates a benefit looks identical to a correct one.

### [NOTE] Staleness check implicitly requires git

The staleness check compares `meta.json`'s `gitCommitHash` to `HEAD`, which requires `git` to be installed and the working directory to be a git repo. Neither is stated as a precondition. The error path when `git` is unavailable or the directory is not a repo is undefined. The skill should either skip the check (and record that it skipped) or fail with a clear message; silent skip is a footgun because the "genuine failure mode" the staleness check exists to prevent is a confidently wrong document.

### [NOTE] Token-efficient graph reading is a hint, not an extraction strategy

The Read Discipline paragraph says "Grep for the needed section before reading; never load the whole file into context" and identifies file-level node types as "sufficient for planning artifacts." This is sound operational guidance, but the *strategy* — which graph fields map to which planning-artifact sections, in what order, with what fallback when a field is absent — is the heart of Capability 1 and is not specified. The interview-scope table covers the human-input side; it does not cover the graph-extraction side. The Open Questions for Slice Design section does not list this either, despite the section being as load-bearing as the interview question set.
