---
docType: review
layer: project
reviewType: slice
slice: everyday-cli-fixes
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/940-slice.everyday-cli-fixes.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261009
dateUpdated: 20261009
reviewedSha: c000f9ec4b22620288dde6b7352956bd0435e274
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
durationSeconds: 22.3
squadronVersion: 0.21.2
findings:
  - id: F001
    severity: concern
    category: scope
    summary: "New features (copy, models init, list color) fall outside the architecture's stated scope"
    location: "project-documents/user/slices/940-slice.everyday-cli-fixes.md#Technical Scope"
  - id: F002
    severity: concern
    category: scope
    summary: "The slice bundles five independent items, against the \"small and focused\" guideline"
    location: "project-documents/user/slices/940-slice.everyday-cli-fixes.md#Overview"
  - id: F003
    severity: concern
    category: error-handling
    summary: "Failure-mode table (D8) is incomplete for the new I/O paths and for the escape change"
    location: "project-documents/user/slices/940-slice.everyday-cli-fixes.md#D8: Failure modes"
  - id: F004
    severity: concern
    category: nfr
    summary: "No NFRs or performance targets are restated"
    location: "project-documents/user/slices/940-slice.everyday-cli-fixes.md#Success Criteria"
  - id: F005
    severity: concern
    category: over-engineering
    summary: "The D5 guard test is a regex-style lint that may be brittle"
    location: "project-documents/user/slices/940-slice.everyday-cli-fixes.md#D5: Escaping CLI output"
  - id: F006
    severity: concern
    category: integration
    summary: "D6 leaves a layering decision open and places logic in the wrong layer"
    location: "project-documents/user/slices/940-slice.everyday-cli-fixes.md#D6: The review profile is visible"
  - id: F007
    severity: concern
    category: integration
    summary: "D4 introduces a state schema change without a stated migration or versioning approach"
    location: "project-documents/user/slices/940-slice.everyday-cli-fixes.md#D4: Run names and source paths"
  - id: F008
    severity: concern
    category: documentation
    summary: "Frontmatter `parent` and `interfaces` use unusual values"
    location: "project-documents/user/slices/940-slice.everyday-cli-fixes.md:5"
  - id: F009
    severity: pass
    category: architecture
    summary: "Dependency directions and module boundaries are sound"
    location: "project-documents/user/slices/940-slice.everyday-cli-fixes.md#Dependencies"
  - id: F010
    severity: pass
    category: error-handling
    summary: "Explicit failure over silent fallback in resume"
    location: "project-documents/user/slices/940-slice.everyday-cli-fixes.md#D4: Run names and source paths"
---

# Review: slice — slice 940

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] New features (copy, models init, list color) fall outside the architecture's stated scope

The architecture says new features or capabilities belong in a feature initiative, not in 900. Three of the five items add new capabilities: `sq pipelines copy` (D1), `sq models init` (D2), and colored `pipelines list` with a `shadows <source>` marker (D7). The `aiProfile` artifact field (D6) is a smaller addition of the same kind. Only #169 (D4) and #177 (D5) are clearly bug fixes, and #193 (D6) is a borderline observability fix. The slice does not justify why these belong in the maintenance initiative. Either state that they count as the "developer experience / operational improvements" the architecture permits, or move them to the appropriate feature initiative.

### [CONCERN] The slice bundles five independent items, against the "small and focused" guideline

The architecture prefers many small slices and says each should be independently deliverable. The slice acknowledges that the fixes are independent (Implementation Notes) and groups them to save process overhead (#194). That is a deliberate tradeoff, but it conflicts with the guideline. The slice doesn't say how partial delivery works if one item stalls, for example whether each item commits separately and can merge on its own. The note to commit each fix separately partly covers this.

### [CONCERN] Failure-mode table (D8) is incomplete for the new I/O paths and for the escape change

D8 covers file-exists, write errors, an unknown name and a missing resume path. It leaves out several cases:
- copy: the source file is unreadable or disappears between resolve and read.
- copy: a partial write leaves a truncated target. `write_new_file` has no atomic write (temp file plus rename) and no cleanup.
- init: `data/models.toml` can't be read from the installed package.
- D4: the stored `pipeline_path` exists but fails to parse or load.
- D4: `pipeline_path` is set but `load_pipeline` raises a different error.
- Concurrent creation (a race between the existence check and the create). Opening with exclusive-create mode (`x`) would make the refusal atomic.
The project's review rules also require each failure mode to be observable and covered by at least one test asserting the signal. The slice never says that the D8 rows have such tests. The "target exists" row also shows only a CLI message, with no log at WARNING or above.

### [CONCERN] No NFRs or performance targets are restated

The architecture document defines no NFRs, so this is not a violation. The D5 guard test and the run-state change also touch run-state loading, so the slice should state a backward-compatibility NFR explicitly: old state files load unchanged. D4 mentions it in passing but does not make it a success criterion or a test requirement.

### [CONCERN] The D5 guard test is a regex-style lint that may be brittle

The test scans source for `print(f"...{exc}...")` patterns with variable names `exc`/`e`/`err`/`error`. That is name-based heuristic matching, and it will miss other variable names, multi-line prints and non-f-string formatting. It could also fail on legitimate non-markup prints, since the slice offers no suppression mechanism. A central escaping helper, or a linter rule, would be sturdier. The slice itself says "a helper alone can't" prevent regression, but it doesn't weigh an AST-based check or a wrapper for the console. State the known limits of the heuristic.

### [CONCERN] D6 leaves a layering decision open and places logic in the wrong layer

The verbose line is moved from the executor into the review action, which keeps the layers consistent. But the statement "Implementation confirms that success and failure artifacts share that writer. If they don't, both get the field" defers a design question to implementation. It is a minor under-specification. The `aiProfile` frontmatter change also alters the artifact schema, and the slice doesn't say whether any consumer of review artifacts (a parser, or resume logic) needs to accept the new field.

### [CONCERN] D4 introduces a state schema change without a stated migration or versioning approach

The new optional `pipeline_path` field is backward compatible for old files. The slice doesn't address forward compatibility, where an older binary reads a state file with the new field, nor what happens to existing runs already recorded under a lowercased path as the name. Those runs stay unfindable by name, and the slice doesn't say whether that is accepted. Absolute paths in state also break if a project is moved. The fail-explicit behavior covers this, but the slice should say so.

### [CONCERN] Frontmatter `parent` and `interfaces` use unusual values

The `parent` points to `user/architecture/900-slices.maintenance-and-refactoring.md`. The instructions say `parent` refers to the slice plan, so this is acceptable and not flagged. The header says "Five small, independent fixes" but the Technical Scope lists seven numbered items, D1–D7 (D3 is a helper and D7 a sixth change). The count in the overview doesn't match the scope.

### [PASS] Dependency directions and module boundaries are sound

The slice uses only existing modules (loader, aliases, profile resolution, state) and adds no new inter-slice interfaces. It routes directory paths through the loader instead of recomputing them. A single `write_new_file` helper follows DRY, and the single-source field reference for `models.toml` avoids duplicated documentation. The doctor row stays at OK status, which avoids nagging.

### [PASS] Explicit failure over silent fallback in resume

A missing recorded `pipeline_path` fails with an error naming the path instead of silently falling back to a same-named pipeline. This matches the project principle against silent fallbacks.

### Run Digest

- Response length: 6955 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 22.3 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10

## Response

- **F001 (fixed):** the Overview now places the items under 900's "developer experience" and "configuration improvements" scope. The two new commands are thin conveniences over files squadron already owns.
- **F002 (fixed):** the grouping is deliberate (#194). The Overview now says each fix commits and reverts on its own.
- **F003 (fixed):** D3 uses exclusive-create mode, writes through a temp file and replace under `--force`, and removes a partial file when a write fails. D8 gains rows for an unreadable source, an unreadable built-in models.toml, a failed write, and a recorded path that fails to load. Each row is required to have a test that asserts its signal. A CLI message plus exit code is the observable signal for "target exists". That is a user error, not a fault, so it gets no WARNING log.
- **F004 (fixed):** loading old state files is now a success criterion with a test.
- **F005 (fixed):** the guard is now an AST check keyed on names bound by `except ... as`, not on variable names. Its limit (user text that never passed through an exception) is stated.
- **F006 (fixed):** settled. Both artifact kinds use `_review_frontmatter_lines`, and `cf validate frontmatter` accepts `aiProfile`.
- **F007 (fixed):** D4 states that `schema_version` is unchanged, that older binaries ignore the field, and that runs already recorded under a path are not migrated.
- **F008 (fixed):** the `parent` value is correct. The count mismatch is resolved: five fixes plus the cosmetic D7. D3 is a helper, not a fix.
