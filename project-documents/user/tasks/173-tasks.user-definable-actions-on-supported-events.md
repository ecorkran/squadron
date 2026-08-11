---
docType: tasks
slice: user-definable-actions-on-supported-events
project: squadron
lld: user/slices/173-slice.user-definable-actions-on-supported-events.md
dependencies: [142, 149, 172, 909, 911]
projectState: >
  Slice 172 complete (20260809): the pre-commit gate calls cf validate
  frontmatter directly and sq setup installs it via _install_git_hook. The
  executor still carries the hardcoded 909/911 post-action block at
  executor.py:1136-1154. No events package exists. This slice builds
  squadron/events/, migrates 909/911 onto it, refactors the 172 gate into a
  COMMIT-bound built-in, and closes prompt-only --step-done parity.
dateCreated: 20260811
dateUpdated: 20260811
status: not_started
---

## Context Summary

- Working on slice 173: user-definable actions on supported events. Design:
  `user/slices/173-slice.user-definable-actions-on-supported-events.md`
  (decisions D1–D9 referenced below). Supersedes deferred slice 171.
- A user action is an in-process Python callable satisfying `EventAction`,
  registered under a dotted namespaced name, bound to a **closed**
  `EventType` (`COMMIT`, `POST_ACTION`) via an `events.yaml` manifest.
- Event actions get event-typed contexts (D1) — the pipeline `Action`
  protocol, `ActionContext`, and pipeline action registry are **untouched**.
  `ActionResult` and `ValidationError` are reused as-is.
- Acceptance test (carried from 171): the hardcoded 909/911 executor checks
  migrate onto the mechanism with **zero assertion changes** in their
  existing tests — only patch targets move.
- Delivery order: Part A mechanism → Part B migration (acceptance) → Part C
  gate/CLI/hook → Part D prompt-only parity → Part E docs and closeout.
- Next planned slice: squadron#28 (review verdict UNKNOWN parse mismatch) or
  next 180-band work per Project Manager.

## Part A — Events Package Foundation

- [ ] **T1. Create `events/` package: `EventType`, contexts, protocol.**
  - [ ] `src/squadron/events/__init__.py`: `EventType(StrEnum)` with exactly
    `COMMIT = "commit"` and `POST_ACTION = "post-action"`. Module docstring
    states the set is closed — adding an event is a squadron change (D2).
  - [ ] `src/squadron/events/contexts.py`: frozen dataclasses per D1 —
    `EventContext(event, cwd, params)`; `CommitContext(EventContext)` adding
    `staged_paths: tuple[str, ...]`; `PostActionContext(EventContext)` adding
    `action_type`, `result: ActionResult`, `run_id`, `run_started_at`,
    `run_state_error`, `step_name`, `step_type`,
    `expected_artifact_kind: ArtifactKind | None`, `iteration`,
    `cf_client: CfClientProtocol`. Field list is exactly the design's — do
    not add optional carriers.
  - [ ] `src/squadron/events/protocol.py`: `EventAction` protocol per D2
    (`name`, `events: frozenset[EventType]`, `validate`, `async execute`).
    Reuse `ActionResult` / `ValidationError` from `pipeline/models.py`.
  - [ ] Success: package imports cleanly; pyright strict clean.

- [ ] **T2. Registry with namespacing guards (D3).**
  - [ ] In `events/__init__.py`: `_REGISTRY: dict[str, EventAction]`,
    `register_event_action(action)`, `get_event_action(name)`,
    `list_event_actions()`, plus `bootstrap_event_actions()` importing the
    builtin modules (idempotent, mirroring `steps/bootstrap_step_types`).
  - [ ] `register_event_action` raises `ValueError` on: name without a dot;
    duplicate name; `squadron.` prefix when the registering module is not
    under `squadron.events.builtin` (inspect the caller's `__module__` /
    stack module — accident prevention, not security).
  - [ ] `get_event_action` raises `KeyError` listing registered names
    (same shape as `pipeline/actions/get_action`).
- [ ] **T3. Tests: enum, contexts, registry guards.**
  - [ ] `tests/events/test_registry.py`: registering a well-formed fake
    action succeeds and is listed; undotted name raises; duplicate raises;
    `squadron.`-prefixed registration from the test module raises; unknown
    lookup raises KeyError naming available actions.
  - [ ] Context dataclasses are frozen (assignment raises) and
    `PostActionContext` carries the full design field list.
  - [ ] Success: `uv run pytest tests/events/ -q` passes.

- [ ] **T4. Binding manifest loader (D6).**
  - [ ] `src/squadron/events/manifest.py`: resolve
    `{cwd}/project-documents/user/events.yaml` → `~/.config/squadron/events.yaml`,
    **first found wins, no merge** (match `pipeline/loader._search_dirs`
    idiom; accept injected paths for tests). No file → defaults only.
  - [ ] Parse `plugins:` (list of module paths), `bindings:` (event name →
    list of `{action, params}`), `disable:` (list of action names). Lenient
    on YAML layout variations per project parsing rules; strict on content:
    unknown event name or non-`EventType` key is a validation error naming
    the file and the offending value.
  - [ ] `DEFAULT_BINDINGS` constant: `squadron.frontmatter-gate` on COMMIT;
    `squadron.dispatch-artifact` then `squadron.revision-stamp` on
    POST_ACTION (order is the 909-before-911 contract). Effective bindings =
    defaults (minus `disable:`) then manifest bindings in file order.
  - [ ] Binding resolution errors (action name not in registry) raise at
    load, naming manifest file, name, and registered actions — never at
    fire time.
- [ ] **T5. Tests: manifest.**
  - [ ] `tests/events/test_manifest.py` with **real YAML fixture files**
    (tmp_path), including the exact format the design documents — per the
    project rule that parser fixtures must match production format.
  - [ ] Cases: project file wins over user file; user file used when project
    absent; no file → defaults only; `disable:` removes a default binding;
    unknown event key errors naming file; unknown action name errors naming
    both; bindings preserve file order after defaults.
  - [ ] Success: suite passes.

- [ ] **T6. Plugin discovery (D7) and dispatcher (D4/D5).**
  - [ ] `src/squadron/events/discovery.py`: import each declared plugin via
    `importlib.import_module`, with `cwd` prepended to `sys.path` for the
    import step and removed after (try/finally). A plugin that raises:
    `logger.exception` naming module and manifest file, then re-raise as
    `PluginLoadError(module, manifest_path)` — hard fail, never skip.
  - [ ] `src/squadron/events/dispatcher.py`: `async fire(context) ->
    list[EventOutcome]` (small dataclass: action name, `ActionResult`,
    error kind). Per binding: validate the action's `events` includes the
    context's event (else load-time error from T4 resolution);
    `asyncio.wait_for(action.execute(ctx), timeout)` with
    `events.timeout_seconds` config key (`int`, default 30) added to
    `config/keys.py`.
  - [ ] Semantics per D4: COMMIT — run **all** bindings, collect failures;
    POST_ACTION — **stop at first failure**. Action raise or timeout →
    treated as Fail with attribution (`logger.exception` / ERROR naming the
    action; the one boundary `except Exception` per D5).
  - [ ] Logging: success DEBUG with duration; failure WARNING+; all lines
    prefixed with action name. No silent path.
- [ ] **T7. Tests: discovery and dispatcher.**
  - [ ] `tests/events/test_discovery.py`: a real tmp plugin module imports
    and registers; a raising plugin produces `PluginLoadError` naming it and
    an ERROR log; sys.path is restored either way.
  - [ ] `tests/events/test_dispatcher.py` with fake actions: run-all on
    COMMIT (second action runs after first fails; both failures reported);
    stop-on-fail on POST_ACTION (second action not called); timeout treated
    as fail naming the action; raise treated as fail with ERROR log;
    disabled binding skipped with DEBUG log; duration DEBUG on success.
  - [ ] Success: suite passes; failure-mode coverage per design criterion 15.
- [ ] **T8. Commit checkpoint: Part A.**
  - [ ] `ruff format`, full `pytest`, `pyright` clean; commit
    (`feat: add events package - types, registry, manifest, dispatcher`).

## Part B — Migrate 909/911 (the acceptance test)

- [ ] **T9. Migrate the dispatch-artifact post-condition (909).**
  - [ ] Move `_check_dispatch_artifact_written`,
    `_dispatch_artifact_post_condition_error`, `_expected_artifact_paths`
    from `executor.py` (~110–214) to
    `events/builtin/dispatch_artifact.py`, unchanged in behavior — the
    `"dispatch post-condition"` log prefix is asserted by tests and must
    survive.
  - [ ] Wrap as `EventAction` named `squadron.dispatch-artifact`,
    `events = {POST_ACTION}`; `execute` narrows to `PostActionContext`,
    returns `PASS`-equivalent success when `action_type != "dispatch"`,
    result unsuccessful, or `expected_artifact_kind is None` (today's guard
    relocated); registers at module foot.
- [ ] **T10. Migrate the revision stamp (911).**
  - [ ] Move `_stamp_revision_number` (executor.py ~217) to
    `events/builtin/revision_stamp.py`; import
    `_expected_artifact_paths` from `dispatch_artifact.py` — do not
    duplicate it.
  - [ ] Wrap as `squadron.revision-stamp` on POST_ACTION; gate on
    `iteration >= 1` as today; **always returns success** — its failures log
    at WARNING (911's never-fail contract, now the action's own tested
    behavior per D4).
- [ ] **T11. Replace the executor block with one dispatch call.**
  - [ ] Delete the `if action_type == "dispatch" ...` block
    (`executor.py:1136-1154`); in its place build `PostActionContext` (the
    `run_started_at` / `run_state_error` / `expected_kind` computation above
    it stays) and `await fire(...)`; apply outcomes: a failure sets
    `result.success = False` / `result.error` (the dispatcher's stop-on-fail
    ordering now expresses the old `elif`).
  - [ ] `bootstrap_event_actions()` called where `bootstrap_step_types()` is
    (executor entry), so built-ins are registered with zero config.
  - [ ] Success: `grep 'action_type == "dispatch"' src/squadron/pipeline/executor.py`
    is empty.
- [ ] **T12. Migrate the 909/911 tests — patch targets only.**
  - [ ] Update `monkeypatch`/`mock.patch` targets in
    `tests/pipeline/test_executor.py` (909 suite ~646+, 911 suite ~994+) and
    `test_executor_integration.py` from `squadron.pipeline.executor._*` to
    `squadron.events.builtin.*`. **No assertion text changes.** If an
    assertion must change, STOP — the mechanism is the wrong shape; raise
    with the Project Manager (design gets revised, not the test).
  - [ ] Verify:
    `git diff main -- tests/pipeline/test_executor.py` shows only
    target-string/import lines; the 909/911 suites pass;
    `test_not_stamped_when_post_condition_failed` passes (now proving
    stop-on-fail ordering).
- [ ] **T13. Commit checkpoint: Part B.**
  - [ ] Full `pytest` + `pyright` + `ruff` clean; commit
    (`refactor: migrate 909/911 post-action checks onto events dispatcher`).

## Part C — Frontmatter Gate, CLI, Hook

- [ ] **T14. Built-in `squadron.frontmatter-gate` (D8).**
  - [ ] `events/builtin/frontmatter_gate.py`: `events = {COMMIT}`; narrows
    to `CommitContext`; runs `cf validate frontmatter <staged_paths>`
    (no paths → no-path invocation, cf walks the root) via
    `asyncio.create_subprocess_exec` — never blocking subprocess in async
    (project async rule).
  - [ ] Exit mapping: 0 → success; 1 → fail, cf's findings passed through in
    `error`; 2 or `cf` missing (FileNotFoundError) → fail with the
    actionable message (install hint / `cf init` hint) — a gate that cannot
    run must not pass (172 D6 carried).
- [ ] **T15. Tests: frontmatter gate.**
  - [ ] Mock the subprocess boundary; assert all three exit mappings and the
    missing-`cf` path, each with its message content.
  - [ ] One real-cf integration test in this repo (cf ≥ 0.12.0 present):
    a tmp in-root doc with bad frontmatter → fail with finding text; clean
    doc → success. Fail (not skip) if `cf` absent, matching
    `test_schema_drift.py`'s posture.
- [ ] **T16. CLI: `sq events fire` / `sq events list` (D8).**
  - [ ] `cli/commands/events.py` (Typer sub-app wired in `cli/app.py`):
    `fire {event} [PATHS...]` — loads manifest, discovers plugins, builds
    `CommitContext`, `asyncio.run(fire(...))`; prints per-action outcomes
    attributed; exit 0 all success / 1 any fail / 2 could-not-run
    (PluginLoadError, manifest error). `fire post-action` → usage error
    naming the reason (no meaning outside a run).
  - [ ] `list`: bindings grouped by event with source (`built-in` /
    manifest path) and disabled built-ins shown as disabled.
- [ ] **T17. Tests: CLI.**
  - [ ] `tests/cli/test_events.py` via Typer runner: exit codes 0/1/2 paths;
    `fire post-action` usage error; `list` output includes a manifest
    binding and marks a disabled built-in.
- [ ] **T18. Repoint the hook and installer.**
  - [ ] `.githooks/pre-commit`: invocation becomes
    `uv run --quiet sq events fire commit -- "${staged_files[@]}"`; the
    missing-tool hard-fail now checks `uv` (pre-172 posture); keep
    `--diff-filter=ACMR` staged collection and the exit-2 message branch
    (cf's project hint now surfaces through the gate action's output).
  - [ ] Update `PRE_COMMIT_HOOK` in `setup_install.py` identically — the
    byte-identity test (`test_gate_hook_matches_tracked_copy`) must keep
    passing unmodified.
  - [ ] Manual verification in this repo: stage a bad-frontmatter doc →
    commit refused with cf findings; clean doc commits; both recorded in
    the task notes.
- [ ] **T19. Commit checkpoint: Part C.**
  - [ ] Full suite + pyright + ruff clean; commit
    (`feat: frontmatter gate as COMMIT event action, sq events CLI, hook repoint`).

## Part D — Prompt-Only Parity (D9)

- [ ] **T20. `--step-done` runs POST_ACTION bindings.**
  - [ ] In `_handle_step_done` (`cli/commands/run.py` ~709): expand the step,
    synthesize `ActionResult(success=True, action_type=..., outputs={})` per
    expanded action, build `PostActionContext` per action,
    run the dispatcher. Any failure: print attributed message to stderr, do
    **not** call `record_step_done`, exit non-zero.
  - [ ] Success criterion: a prompt-only phase step whose dispatch wrote no
    artifact no longer advances (the 909 bug fixed in `/sq:run`'s mode).
- [ ] **T21. Tests: `--step-done` parity.**
  - [ ] Failing post-condition → non-zero exit, stderr names
    `squadron.dispatch-artifact`, step not recorded; artifact present →
    exit 0, step recorded; implement-phase (no expected artifact) →
    unaffected.
- [ ] **T22. Commit checkpoint: Part D.**
  - [ ] Full suite + pyright + ruff clean; commit
    (`feat: run post-action event bindings at --step-done`).

## Part E — Documentation and Closeout

- [ ] **T23. Documentation.**
  - [ ] `docs/EVENTS.md` (new): what an event action is, the `EventAction`
    contract, event-typed contexts, `events.yaml` format, `disable:`,
    authority model (observe / fail / mutate; may not read
    `result.outputs`, with the prompt-only reason), failure philosophy
    (attributed hard-fail). Link from `docs/PIPELINES.md`.
  - [ ] `docs/COMMANDS.md`: `sq events fire` / `sq events list`, exit codes,
    the `--step-done` non-zero exit, `events.timeout_seconds`.
  - [ ] CHANGELOG (user-facing, concise): user-definable commit checks; two
    flagged breaks — `--step-done` can now exit non-zero, and the pre-commit
    hook now requires `uv`/squadron on PATH (not only `cf`).
  - [ ] `140-arch.pipeline-foundation.md`: events registry in Component
    Architecture and Package Structure; authority model noted under Action
    Extensibility; remove/supersede any remaining 171 "designed, not built"
    hooks language.
- [ ] **T24. Verification walkthrough and slice closeout.**
  - [ ] Execute design Verification Walkthrough steps 1–4; refine the
    design's walkthrough section against observed output (per Phase 4/6
    convention).
  - [ ] Full validation: `pytest`, `pyright`, `ruff check`,
    `ruff format --check`, `cf validate frontmatter` all clean.
  - [ ] Mark slice complete: design frontmatter `status: complete`;
    slice-plan entry 28 checked with completion note; this file's
    frontmatter; DEVLOG entry.
  - [ ] Final commit and merge of the slice branch into the target per Git
    Rules (`173-slice.user-definable-actions-on-supported-events`).

Effort: 3/5 overall. Part B carries the binding constraint; treat any
assertion-text pressure there as a design defect, not a test chore.
