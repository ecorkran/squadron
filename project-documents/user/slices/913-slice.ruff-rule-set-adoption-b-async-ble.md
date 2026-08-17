---
docType: slice-design
slice: ruff-rule-set-adoption-b-async-ble
project: squadron
parent: project-documents/user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: []
interfaces: []
dateCreated: 20260815
dateUpdated: 20260817
status: complete
---

# Slice Design: Ruff Rule-Set Adoption — `B`, `ASYNC`, `BLE`

## Overview

Closes the first three steps of
[issue #50](https://github.com/ecorkran/squadron/issues/50). The Python guide
(`.claude/rules/python.md`) requires
`select = ["E", "F", "W", "I", "UP", "BLE", "ASYNC", "B"]`; the project selects
`["E", "F", "W", "I", "UP"]` ([pyproject.toml:80](pyproject.toml#L80)). This
slice adds the three missing sets and fixes what they report.

The point is not lint hygiene. `BLE` and `ASYNC` are named in the guide as the
**mechanical enforcement** for two rules the project otherwise states only in
prose — the exception-handling policy and event-loop discipline. Unenforced,
those rules are aspirational, which is how
[issue #49](https://github.com/ecorkran/squadron/issues/49) landed: a bare
`except` in `cf_op` silently dropping `--embed` for non-SDK models. The return
on this slice is the `BLE` sites that turn out to be #49 again, not the count
going to zero.

Sequence A → B → C. A is noise reduction that makes C's diff readable.
Deliberately excludes pyright-over-tests (slice 914), a sweep of a different
character that should not interleave with these.

## Value

Converts two prose-only rules into merge-blocking CI checks. `ruff check` runs
unqualified in CI ([.github/workflows/ci.yml:28](.github/workflows/ci.yml#L28)),
so once a set is selected, a new violation cannot land. The one-time cost is
this slice; the recurring benefit is that #49's failure shape stops being
introducible.

## Measured Baseline (re-measured 20260815)

Issue #50 and the slice plan carry counts taken when the issue was filed. They
have drifted. **These are the current numbers, and they supersede the plan's**:

| Rule | Plan / issue | Actual | Where |
|---|---|---|---|
| `B904` | 54 | **54** | 53 in `cli/commands/`, 1 in `pipeline/emit.py` |
| `B008` | 13 | **14** | all 14 in `cli/commands/` (7 files) |
| `B007`/`B017`/`B905` | 3 | **3** | `B905` in `src`, other two in `tests` |
| **`B` total** | 70 | **71** | |
| `ASYNC240` | 2 | **2** | `client/http.py:42` (prod), `tests/pipeline/test_executor.py:966` |
| `ASYNC221` | 4 | **4** | all in `tests` |
| `BLE001` | 23, all `src` | **28 total — 23 in `src`, 5 in `project-documents/`** | see D3 |

Two of these drifts change the design rather than just the arithmetic:

**B904 is a CLI-shaped problem, not a whole-codebase one.** 53 of 54 sites are
in `src/squadron/cli/commands/`, 25 of them in `run.py` alone. The plan
describes Part A as a codebase-wide mechanical pass; it is in practice a
single-directory pass plus one straggler in `pipeline/emit.py`. That makes the
diff far more reviewable than the raw count suggests, and it means A and the
`B008` ignore touch the same directory.

**`BLE` is 28, not 23.** The extra 5 are in
`project-documents/user/reference/codebase-probe.py` — a tracked file that CI
lints today, because `ruff check` runs with no path argument. The plan says "23
violations, all in `src`", which is true of `src` and silently omits that
enabling `BLE` also breaks the build on a document-directory script. D3 decides
this.

## Technical Decisions

### D1 — `B008` gets a `per-file-ignores` entry, not 14 rewrites

`typer.Option(...)`/`typer.Argument(...)` in a signature default **is** the
Typer idiom; the framework reads those objects to build the CLI. Rewriting them
to module-level singletons to satisfy `B008` would make the CLI worse to read
in exchange for nothing. Add:

```toml
[tool.ruff.lint.per-file-ignores]
"src/squadron/cli/commands/*.py" = ["B008"]
```

Scoped to the CLI command modules only, so a genuine `B008` elsewhere — a
mutable default, the bug the rule actually exists to catch — still fails.
Directory-scoped rather than per-file so a new command module does not
reintroduce the noise.

### D2 — `B904` fixes use `from` deliberately, not blanket `from None`

Every site is `raise typer.Exit(1)` (or similar) inside an `except`. Ruff
accepts either `from exc` or `from None`, and the mechanical temptation is to
apply whichever is uniform. They mean different things and this slice picks per
site:

- **`from exc`** — the default. Preserves the cause chain.
- **`from None`** — only where the CLI has *already* rendered the error for the
  user and the chained traceback would be noise on a deliberate,
  fully-reported exit.

This is what makes Part A "mechanical but not automatic": `ruff --fix` does not
fix `B904` (confirmed: `--fix` reports no fixes available for it), so each of
the 54 is touched by hand anyway. The cost of choosing correctly is therefore
zero over choosing uniformly.

### D3 — the documents tree is exempted from `BLE` only, not from lint

`project-documents/user/reference/codebase-probe.py` is a tracked
one-off analysis script under the *documents* tree, not shipped code —
it is not in `src/`, not packaged
([pyproject.toml:65](pyproject.toml#L65) packages `src/squadron` only), and not
imported by anything. Its 5 `BLE001` sites are the appropriate shape for a
best-effort probe that must not die on one unreadable file.

Applying the production exception policy to it would be enforcing a rule
against code the rule is not for. Exempt the documents tree from that rule
alone:

```toml
[tool.ruff.lint.per-file-ignores]
"project-documents/**/*.py" = ["BLE001"]
```

Directory-scoped rather than naming the one file, because the reason is
"documents are not source", which applies to any future script that lands
there. **This is a scope decision the plan did not record** — flagged here
because it is the only part of this slice that narrows what CI enforces rather
than widening it.

**Alternative considered and rejected:** `extend-exclude =
["project-documents/"]` under `[tool.ruff]`, which drops the tree from ruff
entirely. Simpler to write, but it also discards `E`/`F`/`W`/`I`/`UP` on a file
that passes them today, and on anything that lands there later — a real
coverage reduction well beyond the problem being solved. The `per-file-ignores`
form gives up only the rule that does not fit a best-effort probe and keeps
every other rule live. Raised as F009 in the slice design review
(`913-review.slice.ruff-rule-set-adoption-b-async-ble.md`) and narrowed here in
response.

### D4 — `ASYNC240` in `http.py` is fixed, not annotated

[client/http.py:42](src/squadron/client/http.py#L42) calls
`Path(self._socket_path).exists()` inside `async def _get_client`. This is a
blocking `stat(2)` on the event loop, on the daemon-client I/O path, and the
guide's async rule ("any `async def` that calls synchronous code must guarantee
it runs in <1ms worst case") is exactly what `ASYNC240` mechanizes.

Fix by moving the call off the loop with `asyncio.to_thread`, preserving
behavior:

```python
if await asyncio.to_thread(Path(self._socket_path).exists):
```

Not `anyio.Path`/`trio.Path` as the rule's message suggests — the project is
asyncio-native and does not depend on anyio directly; adding a dependency to
satisfy a lint message would be the wrong trade. `to_thread` is stdlib and
sufficient.

A local `stat` on a Unix socket path is fast in the common case, so this is a
small real-world win. It is fixed rather than `# noqa`'d because the worst
case — a hung or slow filesystem — is not bounded, and "usually fast" is not
the guarantee the rule asks for.

### D5 — `ASYNC221` in tests is fixed the same way, not blanket-ignored

The 4 `ASYNC221` sites are `subprocess.run` (git commands) inside `async def`
tests. Blocking the loop in a test does not corrupt production, and a
`per-file-ignores` for `tests/` would be defensible. Rejected: these tests are
also the pattern other tests get copied from, and a `tests/` exemption for
`ASYNC` would silently license the next `ASYNC240` in a test that *is*
exercising loop behavior. Wrap in `asyncio.to_thread`, consistent with D4.

### D6 — `BLE001` resolution is per site, with a forced choice

Each of the 23 `src` sites gets exactly one of three outcomes, and "leave it
broad without comment" is not among them:

1. **Narrow** the caught type to what can actually be raised. Preferred.
2. **Keep broad, add `logger.exception` + `# noqa: BLE001`** with a comment
   naming why the boundary must not let anything escape. Legitimate at process
   boundaries and plugin/subprocess seams.
3. **Fix a real bug** where the catch is swallowing something that should
   propagate — the #49 shape.

Sites already reviewed during this design that look like outcome 3 or a
near-miss:

- [pipeline/prompt_renderer.py:158](src/squadron/pipeline/prompt_renderer.py#L158)
  — `except Exception` around `resolver.resolve(action_model)`, falling back to
  `model_id = action_model, profile = None`. A resolver failure is silently
  reinterpreted as "the alias is a literal model id with no profile", which
  then feeds `is_sdk_profile(profile)`. This is structurally #49: an
  unresolvable model degrades into a wrong-but-plausible dispatch instead of an
  error. Needs a real answer, not a `noqa`.
- [pipeline/executor.py:1603](src/squadron/pipeline/executor.py#L1603) — broad
  catch around branch-model resolution that converts *any* exception, including
  a `KeyError` in the surrounding dict handling, into a `FAILED` StepResult
  carrying `str(exc)`. Probably outcome 2 (it is a step boundary) but currently
  has no `logger.exception`, so a programming error inside the `try` is
  reported to the user as a step failure with a bare message and no traceback.

**If a site turns out to be a genuine bug of more than trivial size, it is
filed as an issue and fixed in its own slice — not absorbed here.** This slice's
contract is enabling the rule set; it is not a license to make behavior changes
of arbitrary size under a lint banner. A `# noqa` with a comment pointing at the
filed issue is the correct interim state for such a site.

### D7 — Rule sets are enabled one part at a time

`select` gains `B` at the end of Part A, `ASYNC` at the end of Part B, `BLE` at
the end of Part C — each in the same commit that zeroes it. No part leaves the
build red, and `git bisect` stays meaningful. The explanatory comment at
[pyproject.toml:74-79](pyproject.toml#L74-L79) is deleted in Part C, when it
stops being true.

## Scope

**In scope:** the three rule sets, their violations, the `per-file-ignores` and
`extend-exclude` config, and the `pyproject.toml` comment removal.

**Out of scope:** pyright over `tests` (slice 914); any other ruff set (`N`,
`SIM`, `RUF`, …); reformatting; `line-length` (the project uses 104, the guide
says 88 — a separate argument, not this slice's); behavior changes larger than
a `BLE` site's local fix (see D6).

## Migration Plan

No source/destination move and no consumer updates — this is an in-place
lint-conformance change. Behavior verification is the concern:

- **Parts A and B are behavior-preserving by construction.** `from exc` changes
  traceback chaining, not control flow; `to_thread` changes scheduling, not
  results. The existing suite (3016 tests) is the verification.
- **Part C can change behavior.** Narrowing a caught type means something that
  was swallowed now propagates. That is the *intent* of the rule, and it is the
  one place regressions can hide. Each narrowing site must be able to answer
  "what now escapes that did not before, and where does it land?" A site whose
  answer is "an unhandled traceback to the user" is not done — it needs either
  a handler or outcome 2.

## Success Criteria

- [ ] `select = ["E", "F", "W", "I", "UP", "BLE", "ASYNC", "B"]` in
      `pyproject.toml`, matching the guide's baseline exactly.
- [ ] `uv run ruff check` exits 0 with no path argument (CI's invocation).
- [ ] `uv run ruff format --check`, `uv run pyright` (0 errors), and
      `uv run pytest` all pass — no regressions from a 3016-passing baseline.
- [ ] The only ruff suppressions added are: the D1 `B008` `per-file-ignores`
      entry, the D3 `BLE001` `per-file-ignores` entry for the documents tree,
      and per-site `# noqa: BLE001` comments each carrying a justification.
- [ ] No `extend-exclude` is added — the documents tree keeps
      `E`/`F`/`W`/`I`/`UP` coverage (D3).
- [ ] No blanket `per-file-ignores` for `BLE` or `ASYNC` anywhere in `src/` or
      `tests/`.
- [ ] Every retained broad catch has both a justifying comment and a
      `logger.exception` (or a documented reason it must be silent).
- [ ] Any `BLE` site deferred under D6 has a filed issue, referenced in its
      `noqa` comment.
- [ ] The stale `pyproject.toml` comment describing the deferral is removed.
- [ ] `client/http.py:42` no longer blocks the event loop.

## Verification Walkthrough

Each part is independently verifiable; run at the end of each. Commands and
output below are as actually run during implementation (20260817), on top of
each part's own commit — not merely predicted.

**Per-part gate (all three):**

```bash
uv run ruff check              # exits 0, no path arg — same as CI
uv run ruff format --check
uv run pyright                 # 0 errors
uv run pytest -q               # 3016 passed, 2 skipped baseline (Part A/B);
                                # 3018 after Part B's 2 new client tests;
                                # 3021 after Part C's 3 new tests (Tasks 3.3, 3.4)
```

**After Part A** — confirm `B` is live and the ignore is scoped, not blanket:

```bash
uv run ruff check --select B --output-format=concise    # "All checks passed!"
grep -A3 'per-file-ignores' pyproject.toml              # B008, CLI dir only
```

Prove the ignore did not disable `B` for the CLI — a genuine `B006` (mutable
default) in a command module must still fail:

```bash
# temporarily add `def _probe(x: list[str] = []) -> None: ...`
# to any src/squadron/cli/commands/*.py, then:
uv run ruff check --select B006,B008 src/squadron/cli/commands/
# B006 fires on the probe; B008 stays silent. Caveat: `--select B` alone also
# surfaces pre-existing B904 noise before Task 1.3 lands — select the two
# rules directly to isolate the signal.
# revert the probe
```

**After Part B** — confirm the event loop is clean and the daemon client still
works:

```bash
uv run ruff check --select ASYNC --output-format=concise   # "All checks passed!"
uv run pytest tests/client -q                               # 9 passed
sq doctor                       # exercises the http client path end-to-end;
                                 # "0 missing" confirms the socket-detection
                                 # branch selection is unchanged
```

**After Part C** — the substantive gate:

```bash
uv run ruff check --select BLE --output-format=concise     # "All checks passed!"
grep -rn 'noqa: BLE001' src/ | wc -l                       # 13, across 12 files
grep -rn -B3 'noqa: BLE001' src/                           # every one has a comment
```

Read that last output site by site. A `noqa` without a justifying comment
naming the boundary, or without a `logger.exception`/`logger.warning(...,
exc_info=True)` nearby, is a failed criterion — not a passing one with a note.
All 13 retained sites were read individually and confirmed to carry both.

Confirm the D3 exemption is rule-scoped and did not cost the documents tree its
other coverage:

```bash
grep -n 'extend-exclude' pyproject.toml                    # no match
uv run ruff check --select E,F,W,I,UP project-documents/   # still enforced
uv run ruff check --select BLE project-documents/          # clean via ignore
```

**Whole-slice confirmation** — the guide's baseline is met verbatim:

```bash
grep -n 'select = ' pyproject.toml
# select = ["E", "F", "W", "I", "UP", "BLE", "ASYNC", "B"]
```

Then confirm the rules are actually load-bearing by reintroducing #49's shape:

```bash
# add `try: pass\nexcept Exception: pass` to any src/squadron/pipeline/*.py
uv run ruff check    # must fail with BLE001 — confirmed
# revert; `git status` clean
```

That last step is the real acceptance test for this slice: the failure mode
that produced #49 is now caught by CI rather than by review. Two sites turned
out to match #49's shape exactly during implementation and were fixed as real
bugs rather than narrowed or logged — see D6's outcome-3 note and the DEVLOG
entry for this slice.

## Effort

| Part | Scope | Effort |
|---|---|---|
| A — `B` | `per-file-ignores` + 54 `B904` (53 in one dir) + 3 stragglers | 1/5 |
| B — `ASYNC` | 6 sites, one production | 1/5 |
| C — `BLE` | 23 `src` sites, one decision each + D3 ignore entry | 2/5 |

Total 2/5, consistent with the plan. Part C carries essentially all of the risk
and all of the value.

## Risks

**Narrowing an exception type changes what propagates (Part C, Medium).** The
only real risk here. Mitigated by D6's forced choice and by the migration
plan's "what now escapes, and where does it land?" question per site — plus a
full test run at each part boundary.

**A `BLE` site turns out to hide a substantial bug (Part C, Low/expected).**
Not a risk to manage so much as the expected return. D6 caps the blast radius:
file it, `noqa` with the reference, fix it in its own slice.
