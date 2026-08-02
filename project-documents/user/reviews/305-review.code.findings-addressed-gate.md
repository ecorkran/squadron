---
docType: review
layer: project
reviewType: code
slice: findings-addressed-gate
project: squadron
verdict: FAIL
sourceDocument: project-documents/user/slices/305-slice.findings-addressed-gate.md
aiModel: claude-opus-5
status: complete
dateCreated: 20260802
dateUpdated: 20260802
findings:
  - id: F001
    severity: fail
    category: correctness
    summary: "`concern_plus` never matches a real finding — the gate always fails open"
    location: src/squadron/pipeline/actions/findings_addressed/models.py:20
  - id: F002
    severity: concern
    category: test-coverage
    summary: "Test fixtures use a finding shape the production path never emits"
    location: tests/pipeline/test_findings_addressed_e2e.py:55
  - id: F003
    severity: concern
    category: correctness
    summary: "Screen 0 conflates \"first round\" with \"prior round produced no verdict\", and fails open"
    location: src/squadron/pipeline/actions/findings_addressed/policy.py:127-136
  - id: F004
    severity: concern
    category: correctness
    summary: "The fresh review leg reads run-wide `step_outputs`, which is never cleared between iterations"
    location: src/squadron/pipeline/executor.py:1425
  - id: F005
    severity: concern
    category: correctness
    summary: "Gate evidence frontmatter emits unescaped arbitrary strings"
    location: src/squadron/pipeline/actions/findings_addressed/evidence.py:89-95
  - id: F006
    severity: concern
    category: correctness
    summary: "Consumed-name exclusion opens an ordering hole for `most-severe` gates in loop bodies"
    location: src/squadron/pipeline/steps/loop.py:318-326
  - id: F007
    severity: note
    category: correctness
    summary: "Status-line regex is last-wins and one-match-per-line"
    location: src/squadron/pipeline/actions/findings_addressed/parsing.py:27-30
  - id: F008
    severity: note
    category: simplification
    summary: "`_location_path` is duplicated from `review/parsers.py`"
    location: src/squadron/pipeline/actions/findings_addressed/verification.py:24-26
  - id: F009
    severity: note
    category: project-conventions
    summary: "Project lint/type config omits the rule sets that would enforce this guide"
    location: pyproject.toml:70-85
  - id: F010
    severity: pass
    category: design
    summary: "Layering, fail-closed derivation, and contract-driven validation"
    location: src/squadron/pipeline/actions/findings_addressed/
---

# Review: code — slice 305

**Verdict:** FAIL
**Model:** claude-opus-5

## Resolution (20260802)

Eight commits on `305-slice.findings-addressed-gate`. Full suite 2832 passed /
2 skipped, `ruff check` clean, `pyright` strict clean.

- **F001 (fail, FIXED)** — Confirmed exactly as reported: `Severity` is
  uppercase, `ReviewResult.structured_findings` emits
  `f.severity.value.lower()`, and the membership test could never match.
  Normalized at the boundary in `read_findings` via a new `_as_severity`
  helper ([models.py:80-96](src/squadron/pipeline/actions/findings_addressed/models.py#L80-L96)),
  so `CONCERN_PLUS_SEVERITIES` stays tied to the enum rather than being
  lowercased to match one producer's current casing.
- **F002 (concern, FIXED)** — The e2e fixtures now build review findings by
  constructing a `ReviewResult` and taking `.structured_findings`, which is
  the only shape production emits; the `F00n` ids come from that property
  rather than being hand-written. A new unit test
  (`test_concern_plus_reads_the_shape_the_review_action_actually_emits`)
  pins F001 directly, and the e2e round-2 assertions
  (`decidingScreen: null`, `status: unaddressed`) now depend on the fix,
  so the bug cannot return silently.
- **F003 (concern, FIXED)** — `screen_no_prior_round` takes `review_from`
  and branches on the iteration: iteration ≤ 1 is the legitimate first round
  (annotated PASS); a later iteration with no prior result is an evidence
  gap and returns UNKNOWN with `deciding_screen` unset, following the
  git-failure path's precedent that nothing was settled there. The WARNING
  names the missing step.
- **F004 (concern, FIXED)** — Each loop iteration now resolves step names
  against its own view: a copy of the pre-loop `step_outputs` plus this
  round's body steps. Inner results are no longer written into the run-wide
  dict, which closes all three effects — a failed review can no longer leave
  the prior round's result standing as this round's evidence, inner names
  cannot overwrite a top-level step, and they stop resolving once the loop
  exits. Two regression tests in `test_executor_loop_body.py`.
- **F005 (concern, FIXED)** — Frontmatter is built as a mapping and
  serialized with `yaml.safe_dump` (`gate_evidence_frontmatter`), with enum
  members coerced first since SafeDumper dispatches on exact type. A test
  round-trips a note containing a colon-space, a leading `#`, a leading `-`
  and embedded newlines, plus a hostile step name.
- **F006 (concern, FIXED)** — The ordering rule is now policy-agnostic:
  `_validate_gate_ordering` rejects any gate in a body that names a body
  step at or after its own position, for every policy. A name matching no
  body step is left to the findings-addressed rule, which requires the
  reference to be in the body at all — so a `most-severe` gate may still
  name a pre-loop step, which consumes nothing and opens no hole.
- **F007 (note, FIXED)** — `finditer` per line with first-wins accumulation.
  Multiple statuses on one line are all read; later prose naming a finding
  again cannot overwrite the answer already given. Matching stays within a
  line, so a bare `F001:` cannot absorb the next line's first word.
- **F008 (note, FIXED)** — `review/parsers._location_path` is promoted to
  public `location_path` and imported by `verification`; the local copy is
  gone. `screens._match_key` is left alone: it matches on the full
  `location` string deliberately (911's clean-regeneration contract), so it
  is a different rule rather than a third copy of this one.
- **F009 (note, PARTIALLY ADOPTED)** — `W` is enabled (zero violations).
  `B` (70), `BLE` (23) and `ASYNC` (6) violations, and 868 pyright-strict
  errors under `tests`, are all pre-existing across unrelated modules;
  `BLE` and `ASYNC` in particular require narrowing exception types and
  moving blocking calls off the event loop, which are behavior changes.
  The gap and its counts are recorded in `pyproject.toml` next to the
  config, and adoption is tracked as issue #50 rather than folded into a
  review-fix branch.
- **F010 (pass)** — no action.

## Findings

### [FAIL] `concern_plus` never matches a real finding — the gate always fails open

`CONCERN_PLUS_SEVERITIES` is built from `Severity.CONCERN`/`Severity.FAIL`, whose values are `"CONCERN"`/`"FAIL"` (uppercase). But `ActionResult.findings` is populated in `actions/review.py:297` as `[sf.__dict__ for sf in result.structured_findings]`, and `ReviewResult.structured_findings` (`review/models.py:127`) sets `severity=f.severity.value.lower()` — **lowercase**.

So the membership test at `models.py:156` is always `False`. Verified against the live code:

```
gate expects: frozenset({'FAIL', 'CONCERN'})
records:      [FindingRecord(severity='concern', ..., malformed=False)]
concern_plus: []
```

Consequence: `_run_screens` hands `prior_findings=[]` to `run_deterministic_screens`, which returns `Verdict.PASS` with the log line "prior round raised no CONCERN+ findings". Screens 1 and 2 never run, the judge is never consulted, and the entire policy reduces to the fresh review's verdict. The one thing slice 305 exists to prevent — a round that addressed nothing sailing through — is exactly what happens, silently, on the happy path.

Note the same latent mismatch exists for the `malformed` path: `location` on `StructuredFinding` is `str | None`, so a finding whose location falls through to `None` is flagged malformed. That direction fails closed, so it is secondary, but it shows the same root cause: this module was written against an assumed shape rather than the one `structured_findings` produces.

Fix by normalizing at the boundary in `read_findings` (e.g. `severity.upper()`) rather than by lowercasing the constant — the constant should stay tied to the `Severity` enum so it cannot drift.

### [CONCERN] Test fixtures use a finding shape the production path never emits

`_finding()` builds `{"severity": "CONCERN", ...}` by hand, and `test_findings_addressed.py:85-88` does the same with `"NOTE"`/`"PASS"`/`"CONCERN"`/`"FAIL"`. No test in this slice routes a finding through `ReviewResult.structured_findings`, which is the only way findings reach a real `ActionResult`. That is precisely the gap CLAUDE.md names: *"the test fixture must include the actual format that parser will consume in production. A test that only passes on a format the real data never uses only provides false confidence."*

The e2e test already imports `ReviewResult` (line 25) for the judge leg, so the machinery is present — the prior/fresh review results should be built the same way. At minimum, add one test that constructs a `ReviewResult` with `ReviewFinding(severity=Severity.CONCERN, ...)`, takes `.structured_findings`, and asserts `concern_plus(read_findings(...))` is non-empty. That single test fails today and pins the bug above permanently.

### [CONCERN] Screen 0 conflates "first round" with "prior round produced no verdict", and fails open

`_run_screens` selects `screen_no_prior_round` on `prior_result is None`. In the executor, `prior_iteration_step_outputs` is populated only from `_last_with_verdict(inner_result.action_results)` (`executor.py:1422-1423`), which returns `None` whenever the prior iteration's review step failed, was skipped, or emitted no verdict-bearing action.

So a round-5 gate whose round-4 review crashed takes the round-1 path and returns an annotated `PASS`. `screen_no_prior_round` is documented as "a legitimate first round" and its verdict choice is justified on that basis — but the state it actually fires on is broader, and the extra states are ones where the check *could not run*, which the module's own contract says must resolve to `UNKNOWN`.

`context.iteration` is already threaded into `screen_no_prior_round` and is sufficient to disambiguate: `iteration <= 1` is the legitimate first round (PASS); `iteration > 1` with a missing prior result is an evidence gap (UNKNOWN). Right now the iteration only appears in the log message, where nothing acts on it.

### [CONCERN] The fresh review leg reads run-wide `step_outputs`, which is never cleared between iterations

`step_outputs[inner_result.step_name] = inner_verdict_result` writes loop-body results into the run-wide dict, and nothing removes them. `FindingsAddressedPolicy.evaluate` reads its *fresh* review via `context.step_outputs.get(review_from)` (`policy.py:46`).

If the review step fails in round N, `step_outputs[review_from]` still holds round N-1's result, and the gate silently treats stale evidence as this round's review — comparing round N-1's findings against themselves. The policy has no way to detect this: there is no round stamp on the result it reads. The `prior_iteration_step_outputs` field was carefully scoped per-iteration to avoid exactly this class of leak (`models.py:65-71` documents the reasoning); the fresh side did not get the same treatment.

Two secondary effects of the same write: inner-step names now persist in the run-wide namespace after the loop exits, so a later top-level gate can resolve `review_from: <inner-step-name>` and silently get the final iteration's value; and an inner step sharing a name with a top-level step overwrites it with no diagnostic.

Reading the fresh leg from `iteration_step_outputs` (which is already built, per-iteration, one line above) would close the staleness hole without changing the resolution mechanism.

### [CONCERN] Gate evidence frontmatter emits unescaped arbitrary strings

`_yaml_scalar` returns `str(value)` with no quoting or escaping, and `render_gate_evidence` interpolates `note` values directly into frontmatter (`evidence.py:125`).

Note strings embed finding locations — `f"re-found at {record.location} ({record.category})"` (`screens.py:263`) and `f"claimed {ADDRESSED} over untouched {location}"` (`verification.py:105`). Locations are *not* sanitized: `review/parsers.py:235` documents that any non-placeholder value is "returned stripped, unchanged", i.e. arbitrary model text. A model writing `location: src/foo.py: line 45` yields:

```yaml
    note: re-found at src/foo.py: line 45 (correctness)
```

which is a YAML mapping-value error inside the frontmatter block. A colon-space, a leading `#`, a leading `-`, or an embedded newline in any interpolated value corrupts the artifact. Since the whole point of this file is to be a machine-readable audit record with a `docType`, producing structurally invalid YAML defeats it. Quote and escape scalars (or serialize the frontmatter mapping with `yaml.safe_dump`, which is already a project dependency — `loader.py` imports it).

### [CONCERN] Consumed-name exclusion opens an ordering hole for `most-severe` gates in loop bodies

`_validate_verdict_count` now skips any inner step named by a gate's contract fields. Its docstring justifies this with "`_last_with_verdict` lands on the gate by construction, since a gate must follow the steps it names."

That construction is only enforced for `findings-addressed` gates — `_validate_findings_addressed_gates` filters `gate_positions` on `policy == GatePolicy.FINDINGS_ADDRESSED` (`loop.py:222-227`). The loader's `_validate_gate_references` walks top-level steps only and returns early for anything in a body. So a body ordered `[gate(most-severe, review_from: r), review r]` now passes validation with `verdict_count == 1`, while at runtime `_last_with_verdict` (`executor.py:414`) walks the action results in body order and lands on `review`, not the gate. `until:` then gates on the un-reduced review verdict, bypassing the gate entirely.

Before this change that config was rejected as ambiguous. The ordering check in `_validate_findings_addressed_gates` (the `earlier_names` loop, `loop.py:243-262`) is policy-agnostic in substance — applying it to every gate in the body, not just findings-addressed ones, would restore the invariant the docstring already assumes.

### [NOTE] Status-line regex is last-wins and one-match-per-line

`_STATUS_LINE.search(line)` takes only the first match on a line, and `statuses[match.group("id")] = ...` lets a later line overwrite an earlier one. A judge emitting several statuses on one line loses all but the first; prose mentioning a finding id after its status line (`"F001: I could not confirm this"` → status token `I`) overwrites a good status with `DISPUTED`.

Both failure directions are fail-closed, and the module docstring explicitly prefers lenient anchoring, so this is not a defect so much as a documented tradeoff. Worth noting that `finditer` over the whole output plus first-wins accumulation would tighten both without giving up leniency.

### [NOTE] `_location_path` is duplicated from `review/parsers.py`

`verification._location_path` splits on `:` then `#` — the same job as `review/parsers._location_path` (`parsers.py:238`), with different semantics for the unverified sentinel (parsers returns `None`, this returns the string). `screens._match_key` then does its own third variant of location interpretation.

Three places now encode "how to read a finding location", and they will drift. The parsers version is private, but promoting it is cheaper than maintaining the divergence — location semantics are a review-domain concept, not a gate-policy one.

### [NOTE] Project lint/type config omits the rule sets that would enforce this guide

Pre-existing rather than introduced here, but this slice is the first to hit it. `[tool.ruff.lint] select = ["E", "F", "I", "UP"]` is missing `W`, `B`, `ASYNC`, and — most relevantly — `BLE`, which is the rule the project's own Python guide names as the mechanical enforcement for the exception-handling policy. This slice adds `except Exception:` at `judge.py:135`; it is a defensible transport boundary with `logger.exception` and a justifying comment, but `BLE` is what makes that a deliberate `# noqa` rather than an unreviewed default.

`[tool.pyright] include = ["src"]` also excludes `tests`, contrary to the guide's rationale that "bugs in tests can mask bugs in code" — which is close to what happened with the severity fixtures above.

### [PASS] Layering, fail-closed derivation, and contract-driven validation

The architecture is sound and the reasoning is unusually well documented at the point of decision rather than in a separate design note.

- `derive_addressed_verdict` (`verification.py:114`) computes the verdict from per-finding statuses and never reads a model-stated conclusion, with `UNKNOWN` evaluated before `FAIL` so a check that could not run is never reported as a check that failed. `verify_outcomes` downgrading unsupportable `MOVED`/`ADDRESSED` claims before that derivation is the right ordering.
- `GatePolicyContract` (`gate.py`) gives `steps/gate.py`, `loader.py`, and `steps/loop.py` one source of truth for the per-policy config surface, and each consumer genuinely reads from it instead of restating field names — the `expand()` comment about `cfg["judge_from"]` KeyError-ing on a valid findings-addressed step shows the failure mode was actually traced.
- The registry dispatch replaces the old string-compare-and-fall-back, and an unregistered-but-valid policy returns `success=False` with `UNKNOWN` rather than silently substituting another policy's answer (`gate.py`).
- `run_git` extracted to `review/git_utils.py` deduplicates `commit.py`'s helper, and the docstring's insistence that callers distinguish `None` (git not invocable) from non-zero returncode is respected by `_git_output` (`screens.py:57`).
- `screen_exact_match` refusing fuzzy matching, and `_match_key` routing `unverified` locations to the judge rather than letting them collide on category, both correctly identify which direction of error is fail-open.
