---
docType: review
layer: project
reviewType: slice
slice: configuration-externalization
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/141-slice.configuration-externalization.md
aiModel: z-ai/glm-5
status: complete
dateCreated: 20260329
dateUpdated: 20260329
---

# Review: slice — slice 141

**Verdict:** CONCERNS
**Model:** z-ai/glm-5

## Findings

### [CONCERN] Pipeline directory location conflicts with architecture

The slice design proposes reserving `src/squadron/data/pipelines/` for pipeline definitions (slice 148), stating: "Reserve `src/squadron/data/pipelines/` directory for slice 148 (empty placeholder with `.gitkeep`)". However, the architecture document explicitly shows built-in pipelines in a different location:

```
src/squadron/pipeline/
└── pipelines/
    ├── slice-lifecycle.yaml
    ├── review-only.yaml
    ├── implementation-only.yaml
    └── design-batch.yaml
```

The architecture places pipeline YAML files under `src/squadron/pipeline/pipelines/`, not `src/squadron/data/pipelines/`. The slice's rationale that "all shipped data files" should live in `data/` introduces a new organizational principle that contradicts the architecture's established package structure.

**Resolution needed:** Either the architecture should be updated to reflect the `data/pipelines/` location, or the slice should align with the architecture's `pipeline/pipelines/` location. If slice 148 will address this, the slice design should note the conflict and explain how slice 148 will resolve it.

### [CONCERN] Slice index mismatch with architecture prerequisites

The architecture document's Prerequisites section states:

> "Structured Review Findings (141, formerly 100-band slice 123) — Finding extraction is foundational for the review action."

However, this slice design is numbered 141 and titled "Configuration Externalization" with completely different scope. The slice design quotes a slice plan entry confirming this is the correct assignment for 141.

This is a documentation synchronization issue in the architecture that should be corrected. The prerequisites section needs to be updated to reflect the actual slice numbering, or there may be a missing slice for structured review findings.

### [PASS] Data loading pattern follows established conventions

The `DataLoader` utility's fallback pattern (importlib.resources for wheel installs, `Path(__file__).parent` for editable installs) correctly mirrors the existing `_get_commands_source()` pattern in `install.py`. The dependency direction is appropriate: `aliases.py` and `review/templates/__init__.py` depend on `squadron.data`, not the reverse.

### [PASS] Scope correctly limited to reorganization

The slice correctly scopes itself to moving existing data without behavior changes. Public APIs (`get_all_aliases()`, `load_user_aliases()`, template loading functions) maintain their signatures. User config paths (`~/.config/squadron/`) remain unchanged. The merge semantics (built-ins first, user overrides second) are preserved.

### [PASS] Cross-slice interfaces well documented

The Cross-Slice Interfaces section correctly identifies dependencies on slices 142 and 148, and confirms that existing consumers see no API changes. The reserved `data/pipelines/` directory with `.gitkeep` is an appropriate placeholder pattern.
