---
docType: review
layer: project
reviewType: slice
slice: ruff-rule-set-adoption-b-async-ble
project: squadron
verdict: PASS
sourceDocument: project-documents/user/slices/913-slice.ruff-rule-set-adoption-b-async-ble.md
aiModel: minimax/minimax-m3
status: complete
dateCreated: 20260815
dateUpdated: 20260815
reviewedSha: df471487b8f3df659aa96f5f39c5013b7925e34a
findings:
  - id: F001
    severity: pass
    category: uncategorized
    summary: "Slice falls within architecture's stated scope"
    location: "913-slice.ruff-rule-set-adoption-b-async-ble.md#overview"
  - id: F002
    severity: pass
    category: uncategorized
    summary: "Independently-deliverable, gated parts satisfy the \"small and focused\" guideline"
    location: "913-slice.ruff-rule-set-adoption-b-async-ble.md#d7--rule-sets-are-enabled-one-part-at-a-time"
  - id: F003
    severity: pass
    category: uncategorized
    summary: "Scope is bounded; neighboring concerns are explicitly excluded"
    location: "913-slice.ruff-rule-set-adoption-b-async-ble.md#scope"
  - id: F004
    severity: pass
    category: uncategorized
    summary: "Dependency directions are correct; no new external dependencies introduced"
    location: "913-slice.ruff-rule-set-adoption-b-async-ble.md#d4--async240-in-httppy-is-fixed-not-annotated"
  - id: F005
    severity: pass
    category: uncategorized
    summary: "Per-site D6 enforcement prevents arbitrary behavior changes under a lint banner"
    location: "913-slice.ruff-rule-set-adoption-b-async-ble.md#d6--ble001-resolution-is-per-site-with-a-forced-choice"
  - id: F006
    severity: pass
    category: uncategorized
    summary: "Failure modes for the only behavior-affecting part are enumerated"
    location: "913-slice.ruff-rule-set-adoption-b-async-ble.md#migration-plan"
  - id: F007
    severity: pass
    category: uncategorized
    summary: "D1 ignore is scoped narrowly so the rule stays meaningful"
    location: "913-slice.ruff-rule-set-adoption-b-async-ble.md#d1"
  - id: F008
    severity: pass
    category: uncategorized
    summary: "Success criteria are concrete and include a regression-of-the-original-bug check"
    location: "913-slice.ruff-rule-set-adoption-b-async-ble.md#success-criteria"
  - id: F009
    severity: note
    category: uncategorized
    summary: "D3 trade-off removes lint coverage from `project-documents/` rather than fixing five sites"
    location: "913-slice.ruff-rule-set-adoption-b-async-ble.md#d3"
  - id: F010
    severity: note
    category: uncategorized
    summary: "Slice document weight is high relative to the architecture's \"lighter-weight process\" guidance"
    location: "913-slice.ruff-rule-set-adoption-b-async-ble.md"
---

# Review: slice — slice 913

**Verdict:** PASS
**Model:** minimax/minimax-m3

## Findings

### [PASS] Slice falls within architecture's stated scope

The slice is lint-rule-set adoption + scoped source fixes, which falls directly under the architecture's "Tooling and CI: Build system improvements, test infrastructure, developer experience" and "Operational: error handling improvements that span subsystems" categories. The reference to issue #49 (a bare `except` swallowing `--embed`) reinforces the operational-error-handling framing. Absence of feature work or component-bound refactoring is consistent with the architecture's exclusion of "Work scoped entirely within an active feature slice."

### [PASS] Independently-deliverable, gated parts satisfy the "small and focused" guideline

D7 commits each rule set with its own zero-violation baseline, so each of A/B/C is independently deliverable — directly satisfying the architecture's "Each slice should be independently deliverable" and "prefer many small slices over few large ones" guidelines. Per-part verification commands in the `Verification Walkthrough` section reinforce the independent gate.

### [PASS] Scope is bounded; neighboring concerns are explicitly excluded

The `Scope` section explicitly excludes pyright-over-tests (slice 914), other ruff sets (`N`, `SIM`, `RUF`), reformatting, and line-length changes. This prevents scope creep into slices that have their own design rationale.

### [PASS] Dependency directions are correct; no new external dependencies introduced

D4 explicitly rejects adding an `anyio` dependency "to satisfy a lint message" and instead uses stdlib `asyncio.to_thread`. The architecture flags "removing unused dependencies" as in-scope work, and the slice aligns with that minimalist spirit. The slice frontmatter lists `dependencies: []` and `interfaces: []`, which is correct for an in-place lint-conformance change.

### [PASS] Per-site D6 enforcement prevents arbitrary behavior changes under a lint banner

D6's forced-choice pattern (narrow / documented broad / filed issue) and the explosion of "behavior changes larger than a `BLE` site's local fix" into a separate slice is exactly the kind of guardrail the architecture's "lighter-weight given the maintenance nature" process needs to prevent a maintenance slice from absorbing feature work.

### [PASS] Failure modes for the only behavior-affecting part are enumerated

The migration plan addresses the failure mode of Part C explicitly ("what now escapes that did not before, and where does it land?"), and pairs it with the full 3016-test suite run at each part boundary. No "TBD" failure handling. The slice does not introduce new I/O paths, so the hang/timeout/peer-disconnect requirement does not apply.

### [PASS] D1 ignore is scoped narrowly so the rule stays meaningful

The `B008` `per-file-ignores` is directory-scoped to `src/squadron/cli/commands/*.py` only, and the success criteria explicitly prove the rule still fires elsewhere via a temporary `B006` probe. This guards against the common antipattern of letting an exemption swallow the rule's actual purpose.

### [PASS] Success criteria are concrete and include a regression-of-the-original-bug check

The "reintroduce #49's shape" verification step in the `Verification Walkthrough` ties the slice's value back to the user-visible failure that motivated it, which is the strongest possible acceptance criterion for a maintenance slice.

### [NOTE] D3 trade-off removes lint coverage from `project-documents/` rather than fixing five sites

The slice decides to exclude the entire `project-documents/` tree from ruff via `extend-exclude` rather than fixing the five `BLE001` sites in `codebase-probe.py` or excluding just that one file. The reasoning ("documents are not source") is sound and is transparently flagged, but the consequence — that future Python files landing under `project-documents/` get no `E/F/W/I/UP` coverage either — is a real coverage reduction that may want a second review by whoever owns the architecture. The doc notes the trade-off ("the alternative is holding document-tree scratch scripts to the production exception-handling contract") so this is not a blocker.

### [NOTE] Slice document weight is high relative to the architecture's "lighter-weight process" guidance

The architecture says "Use standard slice design and task breakdown process, but lighter-weight given the maintenance nature." This slice document is long and dense. The complexity is defensible — seven explicit technical decisions, D6-style per-site enforcement, a re-measured baseline, and a verification walkthrough that regenerates the original bug shape — and a lighter-touch alternative would likely have produced a worse `BLE001` outcome. Worth raising with the architecture owner as a calibration point, but not an alignment failure.
