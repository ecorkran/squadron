---
docType: review
layer: project
reviewType: slice
slice: pr-review-artifact-naming-drop-the-host-owner-repo-prefix
targetKind: slice
rulesSource: project
project: squadron
verdict: PASS
verdictSource: stated
sourceDocument: project-documents/user/slices/926-slice.pr-review-artifact-naming-drop-the-host-owner-repo-prefix.md
aiModel: z-ai/glm-5.3-flash
status: complete
dateCreated: 20260925
dateUpdated: 20260925
reviewedSha: 34653d4b687ece6c94b36ca92adb986c4807cd8a
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 38
findings:
  - id: F001
    severity: pass
    category: scope
    summary: "Scope and process alignment with the maintenance architecture"
    location: "project-documents/user/slices/926-slice.pr-review-artifact-naming-drop-the-host-owner-repo-prefix.md#overview"
  - id: F002
    severity: pass
    category: design-decision
    summary: "Qualification keyed to the reviews-directory rule resolves the plan's open question without a guessable branch"
    location: "project-documents/user/slices/926-slice.pr-review-artifact-naming-drop-the-host-owner-repo-prefix.md#technical-decisions"
  - id: F003
    severity: pass
    category: error-handling
    summary: "The accepted collision edge is real, and the stated mitigation exists in code"
    location: "project-documents/user/slices/926-slice.pr-review-artifact-naming-drop-the-host-owner-repo-prefix.md#technical-decisions"
  - id: F004
    severity: pass
    category: single-definition
    summary: "The `path_key` split is the deliberate decision the plan required, recorded against reversion"
    location: "project-documents/user/slices/926-slice.pr-review-artifact-naming-drop-the-host-owner-repo-prefix.md#technical-decisions"
  - id: F005
    severity: pass
    category: verification
    summary: "The slice plan's glob premise was wrong, and the design corrects it with verification plus a regression pin"
    location: "project-documents/user/slices/926-slice.pr-review-artifact-naming-drop-the-host-owner-repo-prefix.md#technical-decisions"
  - id: F006
    severity: pass
    category: layering
    summary: "Layer boundaries and dependency directions are preserved"
    location: "project-documents/user/slices/926-slice.pr-review-artifact-naming-drop-the-host-owner-repo-prefix.md#component-structure"
  - id: F007
    severity: pass
    category: error-handling
    summary: "No new I/O paths; the one reordering is verified side-effect-free and its harmless-on-`--no-save` case is stated"
    location: "project-documents/user/slices/926-slice.pr-review-artifact-naming-drop-the-host-owner-repo-prefix.md#data-flow"
  - id: F008
    severity: pass
    category: extensibility
    summary: "The exhaustiveness guard makes future rules fail loudly instead of defaulting"
    location: "project-documents/user/slices/926-slice.pr-review-artifact-naming-drop-the-host-owner-repo-prefix.md#technical-requirements"
  - id: F009
    severity: note
    category: under-specification
    summary: "Old-name PR test fixtures are not enumerated in the migration plan"
    location: "project-documents/user/slices/926-slice.pr-review-artifact-naming-drop-the-host-owner-repo-prefix.md#implementation-details"
  - id: F010
    severity: note
    category: documentation
    summary: "The installed conventions document will contradict the shipped naming until the upstream guide edit is pulled in"
    location: "project-documents/user/slices/926-slice.pr-review-artifact-naming-drop-the-host-owner-repo-prefix.md#integration-requirements"
---

# Review: slice — slice 926

**Verdict:** PASS
**Model:** z-ai/glm-5.3-flash

## Findings

### [PASS] Scope and process alignment with the maintenance architecture

The slice is a bounded artifact-naming correction (the 900 architecture's "bug fixes / operational" scope, not a new capability), independently deliverable with no prerequisites, and it resolves the plan's open questions rather than deferring them — consistent with the 900 plan's established pattern (910, 915, 919) of settling deferred questions in the slice design. Exclusions (#90, old-artifact migration, PR-number metrology addressing) are explicit and each is justified rather than silent.

### [PASS] Qualification keyed to the reviews-directory rule resolves the plan's open question without a guessable branch

D1 answers the plan's "how is same-repo determined, and what when it cannot be determined" by not asking the question: the directory rule (`ReviewsDirRule`: FLAG/PROJECT/CONFIG/DEFAULT, verified at `reviews_dir.py:36`) already is the explicit, printed decision. The rejection of the origin-remote comparison is well-reasoned and cites exactly the project rule against keying logic on user-accessible labels (remote *name*), plus the fork-layout and no-origin cases D1 never needs to answer. Verified the rule table against `resolve_reviews_dir`'s actual branches — each row matches.

### [PASS] The accepted collision edge is real, and the stated mitigation exists in code

D1's "accepted edge" (fork checkout: PR #83 on the fork and on upstream both land as `pr-83-review.code.md` in the project directory) is a genuine consequence of `select_remote`'s semantics — I verified `_select_explicit`/`_select_bare` in `remotes.py` permit reviewing multiple repositories' PRs from one checkout, so the PROJECT rule's directory does not strictly belong to one repository. The design names the edge, quantifies it (identical numbers only), and points at real mitigations that exist: `archive_existing_review` preserves the prior file before overwrite, and the `pr:` frontmatter mapping remains the identity consumers actually read. Documented acceptance with working mitigation, not an overlooked hazard.

### [PASS] The `path_key` split is the deliberate decision the plan required, recorded against reversion

Plan Part A demanded the single-definition question be decided "deliberately and recorded; do not let the two drift silently." D3 does: the worktree keeps `path_key` (verified sole remaining consumers are `worktree.py:320` and the removed `PrTarget.filename_stem`; `pr_comment.marker_for` uses `key`), the artifact moves off it, and the D3 docstring correction explicitly names slice 926 so a future reader cannot "fix" the divergence back. The walkthrough's step 3 pins the worktree name as unchanged, so no consumer of the worktree name is affected.

### [PASS] The slice plan's glob premise was wrong, and the design corrects it with verification plus a regression pin

Plan Part B claimed `pr/inputs.py`'s `*-review.*.md` glob would miss `pr-83-review.code.md`. D5 re-verified with `fnmatch` — correct: the `*` absorbs `code`, and both new forms match (confirmed against `pr/inputs.py:147`, which then classifies by frontmatter, never filename). The added pinning test converts an accident into a guarded property. The other Part B site (`metrology/capture.py`'s `isdigit()` guard) is resolved by D4 as the plan prescribed: decision, not accident, with the refusal message made true. The `{index}-review.*` index-glob family (`locate_review`, `capture.py:97`) still cannot match either new form by construction — the non-numeric `pr-` prefix preserves the load-bearing property.

### [PASS] Layer boundaries and dependency directions are preserved

`repository_scoped` lives on `ReviewsDirRule` in `review/`, which must never import `codehost` (per the module's own docstring and the enforced boundary test) — a property on the enum needs no new imports. The qualification boolean is computed in the CLI layer (which already imports both packages) and crosses into `PrTarget` as a plain `qualify: bool`, so `review/` never learns the rule. `SaveTargetProtocol.filename_stem`'s signature is unchanged (verified `persistence.py:77`); only the stem's content changes. No new contract with Context Forge: the old name already lacked a leading digit, so cf behavior is identical.

### [PASS] No new I/O paths; the one reordering is verified side-effect-free and its harmless-on-`--no-save` case is stated

The slice introduces no new I/O or message type, so per-path failure-mode enumeration is not triggered. The single behavioral reordering — resolving the reviews directory before building `PrTarget` — touches a function I verified only reads config and checks `is_dir()` with no side effects, and the design states the `--no-save` implication explicitly. The existing `OSError` handling (no fall-through to the next precedence rule, path and rule named either way) is preserved with the pre-resolved directory threaded through. The parent architecture states no NFRs, so there is nothing to restate here.

### [PASS] The exhaustiveness guard makes future rules fail loudly instead of defaulting

Requiring a test that every `ReviewsDirRule` member carries an explicit `repository_scoped` value means adding a rule without deciding its qualification fails CI rather than silently inheriting a default — the same fail-explicit posture the project rules demand, and cheap insurance for the one seam this slice adds.

### [NOTE] Old-name PR test fixtures are not enumerated in the migration plan

The "Consumers updated" list names only `tests/cli/test_review_pr_persistence.py`, but three other test files embed the old filename form as fixture data: `tests/review/test_review_consumers_ignore_pr.py` (`_PR_NAME`, with a docstring asserting "a stem beginning `github.com-` cannot satisfy either"), `tests/documents/test_pr_review_frontmatter.py:170`, and `tests/review/test_pr_artifact_is_target_agnostic.py`. Under D6 these remain valid — old-name artifacts stay on disk and must keep working, so old-name fixtures now exercise exactly the legacy path D6 promises to preserve. But the design should say so (one line in the unchanged-consumers list), or an implementer "helpfully" rewriting those fixtures to new names would silently drop the only coverage of the old-artifact compatibility guarantee D6 relies on.

### [NOTE] The installed conventions document will contradict the shipped naming until the upstream guide edit is pulled in

D7 correctly puts the edit in the `ai-project-guide` repo and forbids hand-editing the installed copy, but the slice does not state the ordering expectation between the squadron change and the next guide update. In the interim, the installed `file-naming-conventions.md` (Pull-Request Reviews section) documents `{host}-{owner}-{repository}-{number}-review.{type}.md` as the form while squadron writes the new one. The `pr-` prefix keeps the load-bearing non-numeric property so nothing breaks, and doc lag on a cross-repo change is normal — but stating "guide edit lands first, or the mismatch is accepted until the next pull" would close the loop the slice otherwise handles carefully.

## Response (20260925)

Both notes verified and accepted; the design has been revised.

- **F009: accepted.** Confirmed that all three files build `github.com-…` fixtures (`test_review_consumers_ignore_pr.py:79` `_PR_NAME`, docstring at line 9). The Migration Plan now lists them as deliberately unchanged, because they are D6's only old-artifact coverage. `test_review_consumers_ignore_pr.py` gets an added `pr-` case, and its docstring is widened to cover any non-numeric stem.
- **F010: accepted.** D7 now states the ordering. The upstream edit lands within the slice, and the installed copy's lag until the next guide update is accepted because no consumer reads the conventions document to find artifacts.

### Run Digest

- Response length: 9381 chars
- Response is newline-free: no
- Tool calls made: 38
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 53148
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
