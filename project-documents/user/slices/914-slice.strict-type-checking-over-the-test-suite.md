---
docType: slice-design
slice: strict-type-checking-over-the-test-suite
project: squadron
parent: project-documents/user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: [913]
interfaces: []
dateCreated: 20260817
dateUpdated: 20260817
status: not_started
---

# Slice Design: Strict Type Checking Over the Test Suite

## Overview

Closes the fourth and final step of
[issue #50](https://github.com/ecorkran/squadron/issues/50). The Python guide
specifies `[tool.pyright] include = ["src", "tests"]` on the rationale that bugs
in tests mask bugs in code. The project currently sets `include = ["src"]`, with
a comment in `pyproject.toml` deferring the widening to issue #50.

This slice widens the include to `["src", "tests"]` under the existing
`typeCheckingMode = "strict"`, resolves every error the widening surfaces, and
leaves the deferral comment deleted.

The slice plan flagged three questions to resolve before task breakdown: one
sweep versus per-directory; whether `MagicMock` noise warrants a narrower rule
set for `tests/`; and whether the mock-heavy pipeline tests want typed fixture
factories or just annotations. The measured baseline below answers all three,
and answers two of them **against** the assumption embedded in the question.

## Value

Test code is the only code in the repo that currently type-checks at zero
strictness. That asymmetry is what the slice removes. The concrete payoff is
the class of drift named in the slice plan — fixtures that stop resembling what
production emits — becoming visible at check time rather than at review time.

Slice 305's F001 (a severity-case mismatch that survived a full slice because
every fixture hand-wrote the finding dict instead of routing through the
production path) is the reference case. Strict typing would not have caught that
specific string-value bug, and this design does not claim it would. It catches
the structural half of that class: a fixture whose *shape* has diverged from the
production type.

## Measured Baseline (measured 20260817)

Measured by setting `include = ["src", "tests"]` and running `uv run pyright
--outputjson` against the tree at `03cdd73`. The configuration change was
reverted after measurement; the working tree is unmodified.

**905 errors across 104 files.** Both numbers differ from the slice plan's
estimate of "868 errors across 234 test files" — the error count drifted up by
37 as slices 909–915 added tests, and the file count is less than half the
estimate. The plan's 234 was the count of test files *analyzed*, not the count
containing errors. The real figure matters: this is a concentrated problem, not
a broad one.

Errors by rule:

| Count | Rule |
|------:|------|
| 175 | `reportArgumentType` |
| 172 | `reportPrivateUsage` |
| 103 | `reportUnknownMemberType` |
| 96 | `reportUnknownArgumentType` |
| 68 | `reportUnknownLambdaType` |
| 57 | `reportUnknownVariableType` |
| 42 | `reportAttributeAccessIssue` |
| 38 | `reportUnknownParameterType` |
| 23 | `reportUnusedFunction` |
| 23 | `reportOperatorIssue` |
| 21 | `reportTypedDictNotRequiredAccess` |
| 21 | `reportMissingTypeArgument` |
| 18 | `reportUnusedImport` |
| 18 | `reportIndexIssue` |
| 17 | `reportMissingParameterType` |
| 14 | (11 rules with ≤4 each) |

Concentration by file — the single most important number in this baseline:

| Scope | Errors | Share |
|------|-------:|------:|
| Top 10 files | 407 | 45% |
| Top 20 files | 592 | 65% |
| Top 30 files | 697 | 77% |
| Top 50 files | 814 | 90% |
| All 104 files | 905 | 100% |

The five heaviest files alone carry 282 errors (31%):
`tests/providers/openai/test_provider.py` (96), `tests/server/test_engine.py`
(81), `tests/cli/test_review_profile.py` (41), `tests/pipeline/test_executor.py`
(36), `tests/pipeline/steps/test_fan_out.py` (28).

By directory: `tests/pipeline` 234 (31 files), `tests/cli` 125 (18),
`tests/providers/openai` 101 (3), `tests/server` 88 (3),
`tests/pipeline/actions` 77 (9), `tests/review` 49 (11), remainder ≤43 each.

Zero errors are reported in `src` — widening the include does not disturb the
existing production baseline.

## Technical Decisions

### D1 — `MagicMock` noise is not the problem; no narrower rule set for `tests/`

The slice plan asked whether `reportUnknownMemberType` noise on `MagicMock`
warrants a narrower rule set for `tests/` rather than full strict. **Measured
answer: no, because the premise is false.**

Of the 362 `reportUnknown*` errors, exactly **2** mention `Mock` in their
message. The unknown-type errors are not mock noise. They are ordinary missing
annotations: untyped lambda parameters (68), unannotated local variables (57),
unannotated helper parameters (38 + 17). `tests/cli/test_doctor.py` is
representative — `lambda name: "/usr/local/bin/cf"` passed to
`monkeypatch.setattr`, where the lambda's parameter and return are both
inferred as unknown.

`unittest.mock` ships with type stubs good enough that `MagicMock` attribute
access does not trip strict mode at the volume assumed. Adding a per-directory
rule relaxation for `tests/` would therefore suppress real missing annotations
while solving a problem that does not exist.

**Decision:** `tests/` runs the same `typeCheckingMode = "strict"` as `src`,
with no `[tool.pyright]` rule overrides, no per-directory `executionEnvironments`
block, and no relaxed ruleset. The suppression inventory at the end of this
slice must be empty of rule-level relaxations.

### D2 — Landing is per-directory with a shrinking `exclude`, not one sweep

The slice plan asked one sweep versus per-directory. **Per-directory**, driven
by the concentration data rather than by preference.

One sweep means a single commit touching 104 files with ~905 individual edits,
reviewable only in aggregate. Per-directory with a shrinking `exclude` list
means each commit is a self-contained, independently verifiable unit, and — the
decisive property — pyright passes at *every* commit in the history rather than
only at the last one. This is the same principle as 913's D7 (no commit has a
rule live and failing), applied to a config key instead of a rule set.

Mechanically, `include` is widened to `["src", "tests"]` in the **first**
commit, with `exclude` simultaneously listing every test directory that still
has errors. Each subsequent commit fixes one directory and deletes its line from
`exclude`. The final commit deletes the last entry, leaving `exclude` holding
only its pre-existing production entry.

**Ordering runs highest-value-first.** `exclude` accepts file paths, not only
directories, so the heaviest files can be their own part regardless of where
they live:

| Part | Target | Errors | Files |
|------|--------|-------:|------:|
| A | infra: `include` widened, `exclude` seeded, shared helpers added (see D5) | — | — |
| B | the 10 heaviest files (spans 6 directories) | 407 | 10 |
| C | `tests/pipeline` remainder + subdirectories | 292 | 42 |
| D | `tests/cli`, `tests/cli/commands` remainder | 104 | 22 |
| E | `tests/providers` remainder, `tests/server`, `tests/review`, `tests/events`, `tests/client`, `tests/metrology`, `tests/integrations`, `tests/core`, `tests/documents` | 102 | 30 |

Part B clears 45% of all errors in the first working commit. Its cost is
cohesion — a 10-file commit spanning six directories reviews less cleanly than a
directory-scoped one — and it places four `tests/pipeline` files, where the
judgment calls concentrate, before the rest of that directory. Part A mitigates
this by landing the shared helpers before any fixing begins.

**Rejected alternative:** cheapest-signal-first (small self-contained
directories, then the heavy ones). It reviews more cleanly per commit but
defers the bulk of the work behind commits that move 5–10% each, and gives no
early read on whether the hard files hold surprises.

### D3 — `reportPrivateUsage` is fixed by renaming the symbol public

172 errors across **67 distinct symbols** — the second-largest rule — are tests
using underscore-prefixed symbols from production modules: `_execute_summary`
(16 sites), `_write_atomic` (11), `_run_pipeline_sdk` (10), `_REGISTRY` (9),
`_codex` (7), and 62 more.

Three resolutions exist, and two are rejected:

**Rejected — 172 inline suppressions.** `# pyright: ignore[reportPrivateUsage]`
on 172 lines is a blanket disable wearing a costume. It leaves the rule nominally
enabled while removing all of its signal.

**Rejected — rewriting the tests to reach the symbol through a public path.**
This is correct in principle but is test-behavior work, not type work, across
172 sites. It would balloon well past this slice and risks changing what the
tests actually assert.

**Decision: rename the symbol to drop the underscore and update all call
sites.** The test then calls public API, with no suppression and no test-logic
change.

An explicitly rejected justification, recorded because it is tempting and
wrong: *"the test suite calls it, therefore it is de-facto public."* That
reasoning is circular — it derives the contract from the violation, and would
launder any encapsulation breach into API. Call-site counting cannot answer
whether a symbol belongs in a module's contract. The judgment is made on the
symbol itself: a stable signature that means something to a caller who is not
the test.

**Measured blast radius:** 922 lines touched — **261 in `src`**, 661 in tests.
The heaviest by production footprint are `_REGISTRY` (28 `src` occurrences),
`_client` (23), `_run` (18), `_write_atomic` (11), `_run_review_command` (8),
`_state_path` (8).

**Known exceptions, to be resolved during implementation, not assumed away.**
Some flagged symbols are module-level internals whose names only read correctly
as private — `_run`, `_client`, `_codex`, `_REGISTRY`, `_thread`, `_HEADER`,
`_FOOTER` are the clear candidates. Promoting `_run` to `run` creates public API
the project then has to live with, which is a real cost and not obviously better
than the alternative. Implementation renames every symbol where a public name
reads correctly, and for each symbol where it does not, records the symbol and
the reason in the slice's completion notes and resolves it with a justified
single-line suppression. The count of such exceptions is reported, not
predicted — this design does not claim to know it in advance.

**This is the part of the slice that touches `src`.** The slice plan records
"test-only; no production code changes" as its risk basis; that is stale. These
are signature-only edits with no behavior change, covered by the existing suite,
but they are production edits. Risk is corrected from Low to **Low-Medium** and
the plan entry updated to say so.

### D4 — `reportUnusedFunction` on fixtures is a real conflict, suppressed at source

23 errors, of which **11** sit directly under a `@pytest.fixture` decorator —
`autouse=True` fixtures like `_clear_registry` and `_sdk_base_patches` that are
never called by name because pytest invokes them by collection.

This is a genuine pyright/pytest idiom conflict, not dead code. The remaining 12
must be inspected individually: an unused `_invoke` or `_boom` helper that is
*not* a fixture is real dead code and gets deleted.

**Decision:** fixture-decorated functions get `# pyright: ignore[reportUnusedFunction]`
on the `def` line. Non-fixture unused functions are deleted, not suppressed —
if a test helper is genuinely unreferenced, removing it is the fix. Each of the
23 is classified explicitly in the task breakdown; none is resolved by
guessing.

### D5 — Two shared typed helpers, added up front; no broad fixture-factory rewrite

The slice plan asked whether mock-heavy pipeline tests want typed fixture
factories or just annotations. **Measured answer: two specific shared helpers
that pay for themselves, and annotations for everything else.** A general
fixture-factory rewrite is out of scope — it is a refactor wearing a
type-checking slice as a disguise.

The two helpers are identified by the error data, not by taste:

**Helper 1 — a typed CLI invoke.** 42 `reportAttributeAccessIssue` errors are
all the same shape: `Cannot access attribute "exit_code"/"output" for class
"object"`. The cause is self-inflicted. `tests/cli/commands/test_dispatch_run.py:17`
declares:

```python
def _invoke(*args: str) -> object:
    return _runner.invoke(app, ["_dispatch-run", *args])
```

`typer.testing.CliRunner.invoke` returns a properly typed `Result`; annotating
the helper as `-> object` throws that away, and every downstream
`result.exit_code` then fails. 12 test modules define a `_invoke` helper and 32
construct a `CliRunner`. Correcting the return annotation to `Result` erases the
whole 42-error rule in a mechanical edit.

**Helper 2 — typed `monkeypatch.setattr` lambdas.** The 68
`reportUnknownLambdaType` errors are lambdas passed to `monkeypatch.setattr`
whose parameters pyright cannot infer. These are fixed by replacing the lambda
with an annotated `def`, or by annotating the lambda's binding. No new
abstraction is required; this is annotation work with a consistent shape, which
is why it belongs in Part A's vocabulary rather than being re-invented per
directory.

The 21 `reportTypedDictNotRequiredAccess` errors (concentrated in
`tests/cli/test_model_list.py`, accessing optional `ModelAlias` keys like
`private`, `cost_tier`, `notes`, `pricing`) are **not** helper material. Each is
a test reaching for a `NotRequired` key without checking presence. Each gets a
real presence check or an explicit narrowing — which is precisely the
fixture-drift signal this slice exists to surface, and suppressing it would
defeat the point.

### D6 — `reportArgumentType` is resolved per site, not by a pattern

175 errors, the largest single rule, and the one with no shortcut. Only 9 have
the `monkeypatch.setattr`/`__call__` overload shape; the other 166 are genuine
type mismatches between what a test passes and what the production signature
declares.

These are the errors most likely to be **real findings** rather than annotation
debt. `Argument of type "object" cannot be assigned to parameter "obj" of type
"Sized"` is a test that has lost track of what it is holding.

**Decision:** no blanket treatment. Each site is read and fixed at the call, and
any site where the *production* signature turns out to be wrong is recorded as a
finding in the slice's completion notes rather than silently accommodated in the
test. If the count of such findings is zero, the slice records zero — the value
claim in this design is falsifiable, and pretending otherwise would be worse
than a null result.

### D7 — The gate runs at every part boundary

Same discipline as 913. At the close of each part: `uv run ruff format`, `uv run
ruff check`, `uv run pyright` (0 errors), `uv run pytest`. The pytest count must
not drop below the 3021-passed / 2-skipped baseline established at `03cdd73`; a
drop means an annotation changed behavior, which is a bug in the change.

## Scope

**In scope:** `[tool.pyright] include`/`exclude` in `pyproject.toml`; type
annotations and typed helpers across all 104 erroring test files; deletion of
genuinely dead test helpers; renaming private production symbols public and
updating their call sites; deletion of the stale deferral comment in
`pyproject.toml`.

**Out of scope:** any production behavior change; a general typed-fixture-factory
framework for pipeline tests (D5); adding new tests for uncovered code;
`typeCheckingMode` changes; relaxing any rule for any directory (D1);
`src/squadron/providers/codex/agent.py`, which stays in `exclude` for its
pre-existing reason.

## Migration Plan

**Source state:** `include = ["src"]`, 0 errors. Tests unchecked.
**Destination state:** `include = ["src", "tests"]`, 0 errors, `exclude`
containing only the pre-existing `agent.py` entry.

**Consumer updates:** the only consumers of the pyright config are CI and the
local gate; both invoke `uv run pyright` with no path arguments and pick up the
config change automatically. No CI workflow edit is required — confirm this in
Part A rather than assuming it.

**Behavior verification:** annotations are erased at runtime, so the pytest
count is the behavior check. The two edits in this slice that *can* change
behavior are D3's symbol renames and D4's dead-helper deletions; both are
covered by the existing suite and gated per part.

## Success Criteria

1. `uv run pyright` reports 0 errors with `include = ["src", "tests"]`.
2. `[tool.pyright] exclude` contains exactly one entry —
   `src/squadron/providers/codex/agent.py` — and no test directory.
3. No `[tool.pyright]` rule is relaxed, and no `executionEnvironments` block
   exists (D1).
4. `typeCheckingMode = "strict"` is unchanged.
5. The deferral comment above `include` in `pyproject.toml` is deleted.
6. `uv run pytest` passes at ≥3021 passed / 2 skipped.
7. `uv run ruff check` and `uv run ruff format --check` pass.
8. Every retained `# pyright: ignore` carries a justifying comment, and the
   audit task has read each one individually.
9. Every `reportPrivateUsage` site is resolved by renaming the symbol public,
   or — where a public name reads wrong — by a justified single-line
   suppression recorded in the completion summary. None by bulk suppression.
10. Any production signature found to be wrong during D6 is recorded in the
    completion summary.
11. The Completion Summary section is filled in: errors remaining (must be 0),
    one-sentence actions, renames, kept-private exceptions.

## Verification Walkthrough

Run from the repo root on the merged branch.

**1. The include is actually widened, and nothing is hidden behind `exclude`:**

```bash
sed -n '/\[tool.pyright\]/,/^\[/p' pyproject.toml
```

Confirm by eye: `include = ["src", "tests"]`; `exclude` lists only
`src/squadron/providers/codex/agent.py`; `typeCheckingMode = "strict"`; no
`reportX = false` lines; no deferral comment.

**2. The check passes over both trees:**

```bash
uv run pyright
```

Expect `0 errors`. Confirm the file count in pyright's summary covers the test
tree — a config typo that silently matches nothing would also report 0 errors,
so the analyzed-file count is the real signal, not the error count.

```bash
uv run pyright --outputjson | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['summary'])"
```

`filesAnalyzed` should be ~444, not ~210. A number near 210 means `tests` is not
being analyzed and the slice has not done its job.

**3. The suite still passes, and nothing was silently disabled:**

```bash
uv run pytest -q | tail -3
uv run ruff check && uv run ruff format --check .
```

**4. Acceptance test — the check actually fails on a real type error.** Plant a
type error in any test file:

```bash
# in any tests/**/test_*.py, add a function that returns the wrong type:
#   def _probe() -> int: return "not an int"
uv run pyright
```

`reportReturnType` must fire on the probe. If pyright reports 0 errors, the test
tree is not being checked and criteria 1–2 are not met despite appearing so.
Revert the probe and confirm `git status` is clean.

**5. Suppression inventory — confirm no bulk escape hatch was used:**

```bash
grep -rn "pyright: ignore" tests/ | wc -l
grep -rn "pyright: ignore" tests/
```

Read the full list. Each line must sit on a `@pytest.fixture`-decorated `def`
(D4) or carry a justifying comment (D3). A `# type: ignore` anywhere in `tests/`
is a finding — this project uses pyright, and a mypy-style blanket ignore is not
the agreed suppression form.

```bash
grep -rn "basic\|reportUnknown.*false\|executionEnvironments" pyproject.toml
```

Must return nothing.

## Completion Summary (required output)

The slice is not done until this table is filled in and committed with it. One
line per action; if an action needs a paragraph to describe, it was the wrong
unit of work and should be split.

**Errors remaining:** must be 0. If not 0, the slice is not complete — record
the count and the reason rather than closing.

**Actions taken** — one sentence each:

| # | Action | Files | Errors cleared |
|---|--------|------:|---------------:|
| 1 | _e.g. "Annotated the `CliRunner.invoke` wrapper `-> Result` in 12 modules."_ | | |

**Renames that promoted a private symbol to public** — one line each, since
these are the slice's only production edits:

| Symbol | New name | `src` sites | Why it belongs in the contract |
|--------|----------|------------:|--------------------------------|

**Symbols kept private** (suppression instead of rename), with the one-line
reason each:

| Symbol | Why a public name reads wrong |
|--------|-------------------------------|

**Production signatures found to be wrong** (from D6) — record zero if zero.

## Effort

**4/5.** Raised from the plan's 3/5. The volume is as advertised and most
individual edits are easy, but the private-symbol renames (67 symbols, 922 lines,
261 of them in `src`) and the 166 genuine argument-type mismatches are not the
mechanical annotation work 3/5 assumed. Two mechanical fixes collapse 110 of the
905 errors, but not far enough to hold 3/5.

## Risks

**The plan's "test-only; no production code changes" basis is stale.** The
private-symbol renames touch 261 `src` lines. These are signature-only and
covered by the suite, but the slice is not test-only; risk is corrected to
Low-Medium.

**Renaming creates public API the project must live with.** Promoting a symbol
is not free — `run`, `client`, `REGISTRY` are permanent surface once exposed.
Mitigated by the kept-private exception path and by recording every rename in
the completion summary for review.

**Churn hiding a behavior change.** Dead-helper deletions and symbol renames can
alter behavior. Mitigated by the per-part gate and the pytest floor of 3021 —
but the floor only catches what the suite covers.

**Baseline drift.** The 905/104 figures are measured at `03cdd73`. Any slice
merged before 914 starts will move them. Part A re-measures before seeding
`exclude` rather than trusting this document's numbers.
