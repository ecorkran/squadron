---
docType: review
layer: project
reviewType: code
slice: loop-iteration-versioning-and-review-evidence
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/911-slice.loop-iteration-versioning-and-review-evidence.md
aiModel: minimax/minimax-m3
status: complete
dateCreated: 20260801
dateUpdated: 20260801
findings:
  - id: F001
    severity: concern
    category: parsing
    summary: "Lenient BOM stripping may swallow legitimate BOM-inside-body content"
    location: src/squadron/documents/frontmatter.py:22
  - id: F002
    severity: concern
    category: error-handling
    summary: "Failure-Mode Enumeration: revision_number stamp has unobserved failure modes"
    location: src/squadron/pipeline/executor.py:214-257
  - id: F003
    severity: concern
    category: design
    summary: "`revision_number` semantics conflates two counters"
    location: src/squadron/pipeline/executor.py:217-223
  - id: F004
    severity: concern
    category: error-handling
    summary: "`_expected_artifact_paths` contract is unclear when list is empty"
    location: src/squadron/pipeline/executor.py:233-244
  - id: F005
    severity: pass
    category: testing
    summary: "Frontmatter helper is well-designed with strong test coverage"
    location: src/squadron/documents/frontmatter.py:1-88
  - id: F006
    severity: pass
    category: validation
    summary: "`commit_each_iteration` validation properly prevents double-commit"
    location: src/squadron/pipeline/steps/loop.py:241-265
  - id: F007
    severity: pass
    category: design
    summary: "`ActionContext.iteration` propagation is clean and testable"
    location: src/squadron/pipeline/models.py:60-66
  - id: F008
    severity: pass
    category: design
    summary: "Commit message iteration suffixing is well-scoped"
    location: src/squadron/pipeline/actions/commit.py:79-94
  - id: F009
    severity: pass
    category: testing
    summary: "Dry-run display of `commit_each_iteration` is consistent and tested"
    location: src/squadron/cli/commands/run.py:992-996
  - id: F010
    severity: note
    category: design
    summary: "`_walk_valid_inner_action_types` mutates global registry side-effect"
    location: src/squadron/pipeline/steps/loop.py:185-204
  - id: F011
    severity: note
    category: design
    summary: "`_COMMIT_ACTION_TYPE` constant is defined but `_VERDICT_BEARING_ACTION_TYPES` is not reused for it"
    location: src/squadron/pipeline/steps/loop.py:18
  - id: F012
    severity: note
    category: correctness
    summary: "`revision_number` written by `update_frontmatter` may re-serialize keys in different order"
    location: src/squadron/documents/frontmatter.py:84-86
  - id: F013
    severity: concern
    category: testing
    summary: "`_stamp_revision_number` failure modes lack exception-type tests"
    location: tests/pipeline/test_executor.py:1183-1219
---

# Review: code — slice 911

**Verdict:** CONCERNS
**Model:** minimax/minimax-m3

## Resolution (20260801)

- **F002 (concern, FIXED)** — Confirmed real: `cf_client` is duck-typed
  (`CfClientProtocol`), and the real implementation
  (`ContextForgeCLI.list_slices/list_tasks/get_project`,
  `context_forge.py:113-154`) raises `ContextForgeError`/
  `ContextForgeNotAvailable` (plain `Exception` subclasses) or `KeyError` on
  malformed CF JSON — none caught by the original `(ValueError, TypeError)`
  tuple. A CF hiccup mid-loop would have propagated uncaught through
  `_execute_step_once`, breaking the documented contract "a failed evidence
  stamp must not fail a converging loop"
  ([executor.py:238-245](src/squadron/pipeline/executor.py#L238-L245)).
  Widened the catch to `Exception` with an inline comment explaining why —
  the function's own contract is unconditional, not scoped to parse/write
  failures. New regression test
  (`test_cf_client_error_logs_warning_and_dispatch_still_succeeds`,
  `tests/pipeline/test_executor.py`) reproduces the real `ContextForgeError`
  path via a two-call `side_effect` (post-condition call succeeds, stamp
  call raises).
- **F003 (concern, ACKNOWLEDGED)** — No action. This is exactly the
  `revision_number` vs. loop-iteration distinction the slice design's Field
  Contract table already deliberated and the PM confirmed as intentional —
  a readability tradeoff, not a defect.
- **F004 (concern, FIXED)** — Confirmed real: the sibling post-condition
  function (`_check_dispatch_artifact_written`) already warns when
  `_expected_artifact_paths` resolves to an empty list
  ([executor.py:146-149](src/squadron/pipeline/executor.py#L146-L149)), but
  `_stamp_revision_number` silently no-opped on the same condition. Added a
  matching WARNING naming the artifact kind and slice index
  ([executor.py:249-254](src/squadron/pipeline/executor.py#L249-L254)). New
  test (`test_no_expected_path_logs_warning_and_does_not_stamp`) forces an
  empty-but-non-raising resolution on the stamp's own call (via
  `side_effect`, distinct from the post-condition's call) and asserts both
  the WARNING and that no `revision_number` key was written.
- **F013 (concern, FIXED)** — Closed by the same fix and test as F002: the
  new `test_cf_client_error_logs_warning_and_dispatch_still_succeeds`
  exercises the previously-untested non-`FrontmatterError` exception path.
- **F001 (concern, ACKNOWLEDGED)** — No action. The review's own prose
  downgrades this to a NOTE ("calling this out as a NOTE rather than a
  bug"); the documented leniency is correct for real slice documents, and
  the existing BOM-prefix test already exercises the production shape.
- **F005-F009 (pass)** — no action.
- **F010, F011, F012 (note)** — no action; none affect behavior or the
  contracts this slice ships.

## Findings

### [CONCERN] Lenient BOM stripping may swallow legitimate BOM-inside-body content

`_split_document` uses `text.lstrip("\ufeff \n")` to strip the BOM and blank lines. This is correct for the prefix but problematic if a BOM or blank lines legitimately appear *after* the body — they are preserved verbatim (which is correct), but the function tolerates the BOM only as a leading prefix. The bigger issue: `lstrip` removes *any combination* of these characters at the start, which means a file beginning with `\n\n\n` followed by `---` works, but a file like ` \n---\nkey: value\n---\nbody` (leading space + newline) has the space stripped silently. This is the intended lenient behavior per the docstring, but the test suite does not cover a leading-space-before-BOM scenario, only the BOM-prefix case via `"\ufeff---\n..."`. Per the project's "lenient parsing" rule, the leading whitespace tolerance is appropriate, but the test `test_read_frontmatter_bom_prefixed` uses `"\ufeff"` directly without a fixture proving the BOM is actually a real BOM in production files. Low severity, but worth flagging because the parser depends on this for real-world slice documents.

The implementation is correct for documented use cases; calling this out as a NOTE rather than a bug.

### [CONCERN] Failure-Mode Enumeration: revision_number stamp has unobserved failure modes

The docstring says "any parse/write failure is logged at WARNING (naming the path and reason) and swallowed" — good. However:

1. `_expected_artifact_paths` can raise exceptions other than `(ValueError, TypeError)` per the explicit catch — if the implementation raises e.g. `KeyError` or `AttributeError` due to malformed `cf_client` state, this would bubble up and fail the dispatch. Per the docstring's contract ("A failed evidence stamp must not fail a converging loop"), the catch should be broader — at minimum `(ValueError, TypeError, KeyError, AttributeError)`, or simply `Exception` with the WARNING log line preserving observability.

2. The test `test_malformed_target_logs_warning_and_dispatch_still_succeeds` covers only the "no frontmatter block" path. The path where `_expected_artifact_paths` raises something other than `(ValueError, TypeError)` is not exercised, and an over-narrow exception tuple silently becomes a bug-in-waiting per the Failure-Mode Enumeration principle.

The current `(ValueError, TypeError)` choice mirrors the explicitly-tested case, but a real-world code reviewer would widen this to `(ValueError, TypeError, KeyError, AttributeError)` or `Exception` with a clear log message. Either is defensible; the current choice is defensible only if `_expected_artifact_paths` is contractually limited to those exceptions. Worth flagging.

### [CONCERN] `revision_number` semantics conflates two counters

The docstring says: *"Value rule: absent or non-int prior value -> 1; present int n -> n + 1. It counts squadron stamps, not the loop iteration."*

This is correct as designed, but the field name `revision_number` is misleading at the *call site* — it's set on every iteration, so a reader of the persisted file sees "revision_number: 5" and naturally assumes "5 iterations." The docstring explicitly disambiguates, but readers downstream may not read the executor's docstring. Consider either:
- Renaming to something like `loop_stamp` or `iteration_evidence_count`, OR
- Adding a comment in the frontmatter (or in the slice design doc) clarifying the semantics.

Not a blocker — the docstring and tests are explicit — but flagging as a readability hazard per the project's "do not duplicate logic" / "centralize magic" rule.

### [CONCERN] `_expected_artifact_paths` contract is unclear when list is empty

The function calls `_expected_artifact_paths(kind, slice_index, cf_client)`. If this returns an empty list, `_stamp_revision_number` silently no-ops. The test `test_not_stamped_when_expected_kind_none` covers `expected_kind is None` (the kind check), but if `expected_kind` is non-None and `_expected_artifact_paths` returns an empty list (perhaps because `cf_client.list_slices` returns nothing), no warning is emitted. Per Failure-Mode Enumeration: "What if this returns empty?" — should be observable. This is a plausible silent-success bug: a loop runs, the artifact doesn't exist anywhere, no stamp is written, and no warning surfaces. Worth a WARNING log when `paths` is empty after the resolve call, or an explicit test confirming the no-op is intentional.

### [PASS] Frontmatter helper is well-designed with strong test coverage

The new `squadron.documents.frontmatter` module is a clean DRY extraction: a single source of truth for read/update with proper `FrontmatterError` typing, leniency semantics documented and tested, byte-preserving body preservation verified against the actual real-world slice document (`911-slice.loop-iteration-versioning-and-review-evidence.md`), and parametrized edge cases (BOM, leading blanks, no block, scalar, unclosed, malformed YAML). The `test_update_frontmatter_byte_preserves_real_document_body` test is exactly the kind of fixture-using-real-input test the project conventions call for. The refactor of `metrology.identity.read_review_frontmatter` to delegate here is a textbook DRY application.

### [PASS] `commit_each_iteration` validation properly prevents double-commit

The `_validate_commit_each_iteration` correctly detects when a body step would also commit (phase-shaped steps commit every iteration), with an explicit inner step that fails its own validate() being skipped via `_walk_valid_inner_action_types`. Tests cover both the happy path (`test_commit_each_iteration_true_with_dispatch_review_body_no_error`) and the failure case (`test_commit_each_iteration_true_with_phase_step_produces_error`). The bool-vs-int subtlety (bool is subclass of int but rejected here) is tested explicitly. Strong design.

### [PASS] `ActionContext.iteration` propagation is clean and testable

Adding `iteration: int = 0` as a default-valued field on `ActionContext` is the right call — backward-compatible, explicit sentinel for "not in a loop," and propagated through `_execute_step_once` to the action's context. The test `test_action_context_carries_loop_iteration_number` confirms both the in-loop (1-based) and out-of-loop (0 sentinel) semantics. Good SRP — the iteration count is the loop's concern, exposed to actions via the context, not duplicated in each action's params.

### [PASS] Commit message iteration suffixing is well-scoped

The iteration suffix is appended only to *composed* messages, never to caller-supplied explicit messages, with the contract documented in the comment (`An explicit `message:` param is a caller contract, not a template`). The `#42 symptom made observable` warning for byte-identical rounds is exactly the Failure-Mode Enumeration principle in action: previously a no-op iteration returned `success=True, committed=False` silently; now it logs at WARNING with all relevant identifiers. Test coverage verifies both the suffix application and the warning emission thresholds.

### [PASS] Dry-run display of `commit_each_iteration` is consistent and tested

The new constant `_DRY_RUN_COMMIT_EACH_ITERATION_SUFFIX` is defined alongside the existing `_DRY_RUN_NO_UNTIL_DISPLAY` constant — single source of truth for the displayed string, both tested positively and negatively. Centralizes the magic string per project conventions.

### [NOTE] `_walk_valid_inner_action_types` mutates global registry side-effect

This helper calls `get_step_type(inner.step_type)` which can lazily register step types as a side effect (depending on registry implementation). During validation, this is normally fine, but if a malformed inner step's validate() fails AND its expand() happens to register a new step type before raising, this could have surprising side effects. Reading the existing `_validate_verdict_count` (which previously did this inline without the helper), the behavior is unchanged — this is just a refactor for DRY. Flagging as NOTE because the function is called twice now where it was inline once before, so any global side-effect is doubled.

### [NOTE] `_COMMIT_ACTION_TYPE` constant is defined but `_VERDICT_BEARING_ACTION_TYPES` is not reused for it

`_COMMIT_ACTION_TYPE = "commit"` is a module-level constant, while `_VERDICT_BEARING_ACTION_TYPES = frozenset({"review", "gate"})` is also module-level. The naming convention is slightly inconsistent (one is a frozenset, one is a plain str). Not a bug — just an observation. Could be unified into a single frozenset for consistency.

### [NOTE] `revision_number` written by `update_frontmatter` may re-serialize keys in different order

`yaml.safe_dump` with `sort_keys=False, default_flow_style=False, allow_unicode=True` — for a dict that preserves insertion order (Python 3.7+), this should preserve key order. The test `test_update_frontmatter_preserves_order_of_untouched_keys` verifies this. PASS-grade for behavior, but worth noting that this depends on `dict` insertion-order semantics — if the implementation ever switched to e.g. `OrderedDict` ordering or `Cython`-accelerated YAML, the behavior could shift. Comment in the docstring already says "Existing key order is preserved" which is correct.

### [CONCERN] `_stamp_revision_number` failure modes lack exception-type tests

`test_malformed_target_logs_warning_and_dispatch_still_succeeds` only covers the `FrontmatterError` path. The contract says "any parse/write failure is logged at WARNING." If a future change widens the catch to include `KeyError` or `AttributeError`, the test wouldn't notice. Per "Test coverage patterns (test-with, not test-after)," the failure-mode enumeration should include a test exercising e.g. a `_expected_artifact_paths` that raises a non-(ValueError, TypeError) exception, OR the test should pin down the exact exception set with a comment. Currently the test only covers the frontmatter-failure path; the cf_client-failure path is implicitly trusted.

---

**Overall:** The PR is well-structured and test-with in spirit. The strongest concerns are around `_stamp_revision_number` failure-mode completeness (both in implementation narrowness and test coverage) and the semantic naming of `revision_number` versus loop iteration. None of these are blockers, but they would benefit from a follow-up clarification or test addition.
