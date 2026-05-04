---
docType: tasks
slice: conditional-persistent-session-construction
project: squadron
lld: user/slices/244-slice.conditional-persistent-session-construction.md
dependencies: [242, 243]
projectState: Slice 243 complete on main (e838898). classification.py and PipelineClassification are available. _run_pipeline_sdk in run.py still constructs SDKExecutionSession unconditionally.
dateCreated: 20260504
dateUpdated: 20260504
reviewResponse: 20260504
status: not_started
---

## Context Summary

- Slice 244: gate `SDKExecutionSession` construction on `PipelineClassification.needs_persistent_session`
- `classify_pipeline` (slice 243) is already merged; this slice wires it into `_run_pipeline_sdk`
- Primary change site: `src/squadron/cli/commands/run.py` (`_run_pipeline_sdk` and `_run_pipeline`)
- `_run_pipeline` must accept optional `resolver` and `pool_backend` params so `_run_pipeline_sdk` can share them with the classifier (Option A from design)
- No changes to step handlers (compact, summary, dispatch) — they already handle `sdk_session=None`
- All tests must pass; pyright and ruff must be clean
- Next slice: 245 — Pool-Resolution Classification Policy (lazy mode)

---

## Tasks

### T1 — Branch setup

- [ ] Verify current branch is `main` and working tree is clean
  - [ ] `git status` shows no uncommitted changes
  - [ ] `git log --oneline -1` shows `b02006c` (slice 243 merge)
- [ ] Create branch `244-slice.conditional-persistent-session-construction` from `main`
  - [ ] `git checkout -b 244-slice.conditional-persistent-session-construction`

---

### T2 — Add optional `resolver` and `pool_backend` params to `_run_pipeline`

File: `src/squadron/cli/commands/run.py`

- [ ] Add `resolver: ModelResolver | None = None` and `pool_backend: PoolBackend | None = None` to `_run_pipeline`'s signature
  - [ ] Import `ModelResolver` at the top of `run.py` (already used in `_run_pipeline_sdk` area; confirm it's present or add it)
  - [ ] Import `PoolBackend` type (TYPE_CHECKING block if needed to avoid circular imports)
- [ ] Inside `_run_pipeline`, wrap the existing `DefaultPoolBackend()` + `ModelResolver(...)` construction in a guard: only construct when the caller did not supply them
  - [ ] `if pool_backend is None: pool_backend = DefaultPoolBackend()`
  - [ ] `if resolver is None: resolver = ModelResolver(cli_override=model_override, pipeline_model=definition.model, pool_backend=pool_backend, on_pool_selection=...)`
  - [ ] The existing `on_pool_selection` lambda referencing `state_mgr` and `_run_id` is unchanged; it stays inside the `if resolver is None` branch
- [ ] Success criteria:
  - [ ] `_run_pipeline` signature accepts both new params as keyword-only with default `None`
  - [ ] When called without the params, behavior is identical to before (fallback constructs internally)
  - [ ] `pyright` reports zero errors on `run.py`

---

### T3 — Test: `_run_pipeline` backward-compatible fallback

File: `tests/cli/test_run_pipeline_sdk.py` (new file, or extend nearest integration test)

- [ ] Write a test calling `_run_pipeline` without `resolver` or `pool_backend` args
  - [ ] Use an existing mock pipeline fixture (or a minimal inline `PipelineDefinition`)
  - [ ] Assert the call succeeds and `execute_pipeline` is invoked (mock `execute_pipeline`)
  - [ ] Assert no `AttributeError` or `TypeError` from the internal construction path
- [ ] Run `uv run pytest tests/cli/test_run_pipeline_sdk.py -v` — all pass
- [ ] Success criteria: fallback construction path exercised and green

---

### T4 — Lift `pool_backend` + `resolver` construction into `_run_pipeline_sdk`

File: `src/squadron/cli/commands/run.py`

- [ ] In `_run_pipeline_sdk`, before the `import claude_agent_sdk` block, construct:
  - [ ] `pool_backend = DefaultPoolBackend()`
  - [ ] `resolver = ModelResolver(cli_override=model_override, pipeline_model=definition.model, pool_backend=pool_backend)` — no `on_pool_selection` here; classification never fires pool selection (side-effect-free), so the callback is not needed yet
- [ ] Pass `resolver=resolver, pool_backend=pool_backend` to the `_run_pipeline(...)` call in `_run_pipeline_sdk`
- [ ] Inside `_run_pipeline`, in the `if resolver is None:` branch (added in T2), construct resolver as before with the `on_pool_selection` callback. In the `else:` path (pre-built resolver supplied), attach the callback directly: `resolver._on_pool_selection = lambda sel: state_mgr.log_pool_selection(_run_id, sel)` — this line goes immediately after `state_mgr` and `_run_id` are known. `_on_pool_selection` is a plain instance attribute on `ModelResolver` (confirmed: `resolver.py` line 59); direct assignment is the prescribed approach. Do not add a new public setter method.
- [ ] Run `uv run pytest tests/cli/ -q` after this task to confirm no regressions before T5
- [ ] Success criteria:
  - [ ] `_run_pipeline_sdk` constructs `pool_backend` and `resolver` before the classification call
  - [ ] The same instances are passed to `_run_pipeline`
  - [ ] `on_pool_selection` callback is set on the pre-built resolver inside `_run_pipeline` before `execute_pipeline` runs
  - [ ] Existing test suite (`tests/cli/`) passes after T4 — no regressions from the refactor
  - [ ] `pyright` clean on `run.py`

---

### T5 — Add `classify_pipeline` call and session gate in `_run_pipeline_sdk`

File: `src/squadron/cli/commands/run.py`

- [ ] Import `classify_pipeline` and `ClassificationError` from `squadron.pipeline.classification`
- [ ] After constructing `resolver` and `pool_backend`, add classification:
  ```
  try:
      classification = classify_pipeline(definition, resolver, pool_backend)
  except ClassificationError as exc:
      rprint(f"[red]Error: Pipeline classification failed — {exc}[/red]")
      raise typer.Exit(1)
  ```
- [ ] Log classification result at INFO:
  - [ ] `_logger.info("pipeline '%s' shape: %s (%d classified steps)", pipeline_name, classification.shape, len(classification.steps))`
- [ ] Log each step's classification at DEBUG:
  - [ ] Iterate `classification.steps`; for each, log step name, action type, classification value, and rationale
- [ ] Gate session construction:
  - [ ] `if classification.needs_persistent_session:` — construct `options`, `client`, `session`, call `await session.connect()`
  - [ ] `else: session = None`
  - [ ] The `try/finally` block wrapping `_run_pipeline(...)` and `session.disconnect()` begins **after** `session` is assigned (connect failure does not enter the finally block — intentional, per design §Conditional connect() failure modes)
- [ ] Success criteria:
  - [ ] `classify_pipeline` is called with `(definition, resolver, pool_backend)` before session construction
  - [ ] `ClassificationError` produces `typer.Exit(1)` with a red error message, no traceback
  - [ ] `needs_persistent_session=True` → session constructed and connected
  - [ ] `needs_persistent_session=False` → `session = None`, no `SDKExecutionSession` created
  - [ ] INFO log line is emitted before session construction decision
  - [ ] `pyright` clean

---

### T6 — Tests: classification gate in `_run_pipeline_sdk` (T1–T5, T8 from design)

File: `tests/cli/test_run_pipeline_sdk.py`

- [ ] **T1** — All steps non-SDK (dispatch only): mock `classify_pipeline` returning `needs_persistent_session=False, shape=claude_free`; assert `SDKExecutionSession` is never constructed
- [ ] **T2** — Non-SDK pipeline with summary + compact steps: mock classification as `claude_free`; call step handlers with `sdk_session=None`; assert no crash and no session constructed
- [ ] **T3** — At least one SDK dispatch step: mock `needs_persistent_session=True, shape=claude_required_persistent`; assert `SDKExecutionSession` constructed and `connect()` called
- [ ] **T3b** — `claude_required_one_shot` shape: mock `classify_pipeline` returning `needs_persistent_session=False, needs_one_shot_claude=True, shape=claude_required_one_shot` (e.g., a review-only pipeline with SDK-profile reviews); assert no persistent session constructed — `sdk_session=None` is passed to `execute_pipeline`; this satisfies Success Criterion 8
- [ ] **T4** — Pool-uncertain step: mock classification with `POOL_UNCERTAIN` step (still `needs_persistent_session=True`); assert session constructed
- [ ] **T5** — `ClassificationError`: mock `classify_pipeline` to raise `ClassificationError("bad cascade")`; assert `typer.Exit(1)` raised and no session created
- [ ] **T8** — `connect()` failure: mock `needs_persistent_session=True`, mock `session.connect()` to raise `CLINotFoundError`; assert exception propagates, `disconnect()` not called
- [ ] Run `uv run pytest tests/cli/test_run_pipeline_sdk.py -v` — all pass
- [ ] Success criteria: T1–T5, T3b, and T8 green; test file uses mocked `classify_pipeline` (no alias config needed)

---

### T7 — Tests: resume path (T6, T7 from design)

File: `tests/cli/test_run_pipeline_sdk.py` (extend same file)

- [ ] **T6** — Resume, non-SDK: set up a mock `RunState` with `execution_mode=SDK`; mock classification as `claude_free`; call the resume branch of the `run` command; assert no session constructed
- [ ] **T7** — Resume, SDK: mock classification as `claude_required_persistent`; assert session constructed and `seed_context` called (session seeded from prior compact summary)
- [ ] Run full test file — all pass
- [ ] Success criteria: resume path correctly re-classifies and gates session on each call

---

### T8 — Intermediate commit

- [ ] `ruff format src/ tests/`
- [ ] `ruff check src/ tests/` — clean
- [ ] `uv run pyright` — zero errors
- [ ] `uv run pytest --tb=short -q` — no regressions (1795+ passing)
- [ ] `git add src/squadron/cli/commands/run.py tests/cli/test_run_pipeline_sdk.py`
- [ ] `git commit -m "feat: gate SDKExecutionSession construction on pipeline classification"`

---

### T9 — Verify `sdk_session=None` correctness for summary and compact (T2 extended)

This task is a targeted audit, not a code change. Confirm the design assertions hold.

- [ ] Read `src/squadron/pipeline/actions/compact.py` lines 58–64: confirm branch on `context.sdk_session is not None`
- [ ] Read `src/squadron/pipeline/actions/summary.py` lines 218–224: confirm SDK-profile guard returns `ActionResult(success=False, ...)`
- [ ] Read `src/squadron/pipeline/actions/summary.py` lines 149–170: confirm restore variant checks `sdk_session is not None` before seeding
- [ ] If any of the three guards are absent or broken, fix them in the respective action file and add a regression test
- [ ] Success criteria: all three guards confirmed present; no code changes required (or changes committed if guards were missing)

---

### T10 — Final validation and commit

- [ ] `ruff format src/ tests/`
- [ ] `ruff check src/ tests/` — clean
- [ ] `uv run pyright` — zero errors
- [ ] `uv run pytest --tb=short -q` — full suite passes, new tests included
- [ ] Confirm INFO log shape line appears by running with `--log-level DEBUG` against a test pipeline (manual spot-check or log capture in test)
- [ ] `git add -p` (stage any remaining changes)
- [ ] `git commit -m "test: add conditional session gate tests (T1–T8)"`

---

### T11 — Documentation and slice closeout

- [ ] Update `project-documents/user/slices/244-slice.conditional-persistent-session-construction.md`:
  - [ ] Set `status: complete`
  - [ ] Add `completedCommit: <hash>` (use final implementation commit hash)
  - [ ] Update Verification Walkthrough with actual log output observed
- [ ] Update `project-documents/user/architecture/240-slices.pipeline-auth-boundary-flexibility.md`:
  - [ ] Mark slice 244 entry `[x]`
  - [ ] Set `dateUpdated: 20260504`
- [ ] Update `CHANGELOG.md` under `[Unreleased]`:
  - [ ] One-line user-facing entry: `Pipeline classification gates SDK session construction — non-Claude pipelines no longer require Claude auth`
- [ ] Write DEVLOG entry in `project-documents/DEVLOG.md` (Phase 6 implementation summary)
- [ ] `git add` doc files and `git commit -m "docs: mark slice 244 complete; DEVLOG, CHANGELOG, and slice-plan closeout"`
