---
docType: review
layer: project
reviewType: slice
slice: pr-keyed-review-persistence
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/383-slice.pr-keyed-review-persistence.md
aiModel: z-ai/glm-5.2
status: complete
dateCreated: 20260915
dateUpdated: 20260915
reviewedSha: 963e56125ac84c2f55d622c6848554d270073234
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 19
findings:
  - id: F001
    severity: pass
    category: uncategorized
    summary: "Dependency direction preserved — review/ imports nothing from codehost"
    location: "project-documents/user/slices/383-slice.pr-keyed-review-persistence.md#architecture"
  - id: F002
    severity: pass
    category: uncategorized
    summary: "reviewedSha taken from the PR record, not operator HEAD"
    location: "project-documents/user/slices/383-slice.pr-keyed-review-persistence.md#d3-the-pr-target-its-filename-and-the-key-that-is-not-filesystem-safe"
  - id: F003
    severity: pass
    category: uncategorized
    summary: "Byte-identity acceptance test enforces \"existing flows do not change\""
    location: "project-documents/user/slices/383-slice.pr-keyed-review-persistence.md#d2-frontmatter-splits-into-common-and-target-specific-and-the-migrations-test-is-byte-identity"
  - id: F004
    severity: pass
    category: uncategorized
    summary: "Scope matches the architecture's slice description"
    location: "project-documents/user/slices/383-slice.pr-keyed-review-persistence.md#technical-scope"
  - id: F005
    severity: concern
    category: boundary-responsibility
    summary: "SaveTarget protocol omits \"reviews directory\" from the contract, deviating from the architecture's three-part description"
    location: "project-documents/user/slices/383-slice.pr-keyed-review-persistence.md#d1-the-save-target-contract-is-a-structural-protocol-with-three-questions"
  - id: F006
    severity: concern
    category: error-handling
    summary: "Failure modes for the new external-directory write path not explicitly enumerated"
    location: "project-documents/user/slices/383-slice.pr-keyed-review-persistence.md#d5-where-a-pr-review-lands-in-precedence-order"
  - id: F007
    severity: note
    category: integration-points
    summary: "targetKind classification reads frontmatter, not the filename prefix — a justified correction"
    location: "project-documents/user/slices/383-slice.pr-keyed-review-persistence.md#d4-existing-consumers-are-shown-not-to-match-and-the-review-consumers-learn-target-kind"
  - id: F008
    severity: note
    category: integration-points
    summary: "external_reviews_dir default uses ~/.config/squadron/ rather than the architecture's \"per-user data directory\""
    location: "project-documents/user/slices/383-slice.pr-keyed-review-persistence.md#d5-where-a-pr-review-lands-in-precedence-order"
---

# Review: slice — slice 383

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.2

## Findings

### [PASS] Dependency direction preserved — review/ imports nothing from codehost

The architecture states "the review package imports that type and nothing else from [the adapter], so types flow from adapter to review and calls never flow from review to host" (380-arch, Architectural Principles). The slice honors this precisely: `save_target.py` sits in `review/` and imports nothing from `codehost`; `PrTarget` is built in the CLI layer (`review_pr.py`), which already imports both packages. The slice's stated invariant — "No module under `review/` imports `squadron.codehost`" — with an import-graph test, is the correct enforcement. The Protocol-over-union choice is explicitly motivated by keeping `PrTarget` out of `review/`, which is exactly the boundary the architecture draws.

### [PASS] reviewedSha taken from the PR record, not operator HEAD

The architecture is emphatic: "the reviewed head sha is taken from that record, never resolved from HEAD of the working directory, which on this path is the operator's branch and not the reviewed tree" (380-arch, Persistence shape and location). The slice implements this correctly: `reviewed_sha` comes from the target rather than being resolved inside `save_review_result`; `PrTarget` returns the record's `head_sha`; slice/arch targets resolve from git as before. Verified against the current code — `save_review_result` stamps `resolve_reviewed_sha(".")` (persistence.py:639), which is exactly the bug the architecture warns about on the PR path. The acceptance test deliberately makes operator HEAD and PR head differ, which is the right assertion.

### [PASS] Byte-identity acceptance test enforces "existing flows do not change"

The architecture's constraint is "Existing flows do not change" (380-arch, Constraint). The slice makes this concrete and testable: slice, arch, and pipeline step reviews must produce files byte-identical to pre-migration fixtures captured before the change. This is stronger than "tests still pass" and is the correct mitigation for a three-caller migration that touches frontmatter rendering. The deliberate behavior change on the step path (archive guard now applies) is called out separately with its own test and the non-fatal `try/except` boundary preserved, which is the right separation.

### [PASS] Scope matches the architecture's slice description

The architecture's "PR-keyed review persistence" slice lists: the save-target contract, arch review migration off minimal-`SliceInfo`, PR naming and frontmatter, unplanned-repository location, and rules-source provenance. The slice covers all of these, plus the pipeline step migration (which the architecture's "Persistence takes a target" principle explicitly names: "migrates the arch review and the pipeline action's step-keyed save onto it in the same slice"). Exclusions are correctly drawn: posting (384), PR creation (385), and teaching resolve/metrology to *act* on PR reviews are out of scope. No scope creep.

### [CONCERN] SaveTarget protocol omits "reviews directory" from the contract, deviating from the architecture's three-part description

The architecture states the contract as three parts: "a target yields the filename stem, the target-specific frontmatter fields, and the reviews directory" (380-arch, Architectural Principles — "Persistence takes a target, not a slice"). The slice's D1 reduces the protocol to two methods (`filename_stem`, `frontmatter_fields`, `source_document`) and deliberately excludes the reviews directory, arguing it "depends on the invocation (`--reviews-dir`, the project's presence) rather than on the target." The justification is sound — the directory is indeed invocation-dependent — but it is a deliberate deviation from the architecture's literal three-part contract. The `source_document` method is an addition not named by the architecture. The deviation is well-reasoned and arguably an improvement (it prevents every implementation from carrying a directory it does not choose), but because the architecture explicitly names "the reviews directory" as part of what "a target yields," this should be confirmed with the architecture owner or noted as a design-level correction to the parent doc, the same way the slice documents its other corrections in the "Scope corrections" table. It is not listed there.

### [CONCERN] Failure modes for the new external-directory write path not explicitly enumerated

The slice introduces a new I/O path: writing a review to `~/.config/squadron/reviews/<host>/<owner>/<repo>/` (or a `--reviews-dir` override) in an unplanned repository. The architecture's failure-mode principle ("Failure modes are enumerated and observable") applies to each new I/O path. The slice states the handling strategy at a high level — "it either saves or reports a failed write as `UNSAVED`" (D8) — and the existing `OSError` → `_save_and_report` → `False` → `UNSAVED` path covers write failures. However, the specific failure modes for this new path are not enumerated: directory creation failure on the external path (permissions, read-only parent), `--reviews-dir` pointing at a non-writable or non-existent-when-not-created location, and disk-full. The precedence resolver (D5) does not state what happens when the chosen directory cannot be created — e.g., does `--reviews-dir /nonexistent` fail loudly or fall through to the next precedence rule? The slice says rule 2 "requires the directory to already exist" but does not say whether `--reviews-dir` (rule 1) must pre-exist or is created. Given the architecture's requirement that each new I/O path have its failure modes enumerated with explicit handling, the external-directory write path should state its mkdir/write-failure behavior explicitly rather than relying on the inherited OSError path implicitly.

### [NOTE] targetKind classification reads frontmatter, not the filename prefix — a justified correction

The architecture says `*-review.*` consumers "are taught to read the target kind from the prefix" (380-arch, Persistence shape and location). The slice corrects this: classification reads a `targetKind` frontmatter key, never the filename, noting that `capture._read_review_type` already reads frontmatter and that filename parsing is unreliable (a type like `judge.slice-vs-arch` contains dots). Verified: `capture.py:_read_review_type` reads `reviewType` from frontmatter with a filename fallback, and `discover_judge_results` filters on frontmatter `reviewType`. The slice's approach is more robust than the architecture's literal "from the prefix" and is consistent with existing code. The correction is documented in the "Scope corrections" table, which is the right practice.

### [NOTE] external_reviews_dir default uses ~/.config/squadron/ rather than the architecture's "per-user data directory"

The architecture says the default is "a `reviews/<host>/<owner>/<repo>/` tree under squadron's per-user data directory" (380-arch, Persistence shape and location). The slice uses `~/.config/squadron/reviews/...` and explicitly documents that `data_dir()` resolves to the installed package's read-only `squadron/data/`, so the architecture's term is imprecise. Verified: `_worktree_root` in `worktree.py` already uses `Path.home() / ".config" / "squadron"`, and the slice cites 382's D3 for the same correction. This is a legitimate design-time correction of an imprecise architecture term, documented in the "Scope corrections" table.

## Response — 20260915

Design updated at `cba46123`+ (see the follow-up commit). Dispositions:

- **F005 (concern) — reviews directory omitted from the contract: ACCEPTED, recorded.** The
  finding is right on both counts: the protocol deviates from the parent architecture's literal
  three-part contract, and I documented that deviation inside D1's prose instead of the scope
  corrections table, which is exactly the table's purpose. The design reasoning stands unchanged
  — the directory is invocation-dependent (`--reviews-dir`, whether a `project-documents/`
  exists), so a target would carry a value it cannot answer, and `save_review_result` already
  takes `reviews_dir` as a parameter for that reason. Added as a corrections-table row naming it
  a deliberate deviation, alongside `source_document` as an addition the architecture does not
  name. No change to the protocol.

- **F006 (concern) — external-directory failure modes not enumerated: ACCEPTED, fixed.** The
  substantive half of this review. The open question — does `--reviews-dir /nonexistent` fail or
  fall through? — was genuinely unanswerable from the document, and a fall-through would have
  been a silent fallback the project rules forbid. D5 now carries a four-row failure-mode table
  and a stated rule that precedence selects once and never falls through on failure. Resolved
  against existing behavior rather than invented: `mkdir` sits outside the try in
  `save_review_result`, so a creation failure already raises `OSError` → `_save_and_report` →
  `UNSAVED` → non-zero exit. For the create-vs-require question the codebase offered two
  precedents; `--reviews-dir` follows `metrology`'s store dir (create, and raise naming the path)
  rather than `--rules-dir`'s silent degrade-to-`None`. Rule 2 remains the one require-not-create
  case, so squadron never creates `project-documents/` inside a repository that never asked for
  one. A matching success criterion asserts each mode, including that no failure reaches the next
  precedence rule.

- **F007, F008 (notes) — no action.** Both confirm corrections already recorded in the scope
  corrections table (frontmatter-over-prefix classification; `~/.config/squadron/` over the
  architecture's imprecise "per-user data directory").

- **F001–F004 (passes) — no action.**

Neither concern required a design change beyond documentation; the protocol, the precedence
chain, and the migration plan are unchanged.

### Run Digest

- Response length: 9529 chars
- Response is newline-free: no
- Tool calls made: 19
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 11762
- `## Summary` located: no
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
