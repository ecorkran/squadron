---
docType: tasks
slice: summary-step-with-emit-destinations
project: squadron
parent: 161-slice.summary-step-with-emit-destinations.md
dependencies: [158-sdk-session-management-and-compaction]
projectState: Slice 158 complete — SDK session-rotate compaction via SDKExecutionSession.compact() working end-to-end. compact action populates RunState.compact_summaries. claude_code system prompt preset wired in run.py. Response-text duplication bug fixed. PreCompact hook no longer installed by default. Test pipeline extended with tasks+post-compact-dispatch for smoke tests.
dateCreated: 20260408
dateUpdated: 20260408
status: not_started
---

# Tasks: Summary Step with Emit Destinations (Part 1 of 2)

> **Part 1** covers dependency + core mechanism: pyperclip, the
> `SDKExecutionSession` capture/rotate split, the emit registry and
> its built-in destinations, the emit parser, and the new summary
> action implementation. Tasks T1–T9.
>
> **Part 2** (`161-tasks.summary-step-with-emit-destinations-2.md`)
> covers the compact alias refactor, summary step type, loader
> validation, end-to-end integration tests, smoke pipeline update,
> lint/type-check, and closeout. Tasks T10–T17.

## Context Summary

- Working on slice 161 (Summary Step with Emit Destinations).
- Goal: add a `summary` pipeline step type that generates a
  conversation summary and emits it to one or more destinations
  (stdout, file, clipboard, rotate). Decouples summary generation
  from "what to do with the summary."
- `compact` step/action remains backward compatible as a thin alias
  that hardcodes `emit: [rotate]` — existing pipelines do not
  change.
- Key refactor: split slice 158's `SDKExecutionSession.compact()`
  into two operations — `capture_summary()` (no rotation) and the
  existing `compact()` gains an optional `summary=` parameter so it
  can skip the capture phase when called from the summary action's
  rotate emit. This avoids running the summarizer twice when
  `emit: [..., rotate]` is combined with other destinations.
- New dependency: `pyperclip` for clipboard emit (small pure-Python
  lib, platform-aware, import-clean on headless systems).
- Failure isolation: non-rotate emit failures log a warning, record
  `ok: False`, and let the remaining emits continue. Rotate failure
  halts the action.
- No schema changes. No new state fields. `compact_summaries`
  persistence stays compact-only; summary-step persistence deferred
  to a follow-up.

**Files to change:**
- `pyproject.toml` — add `pyperclip` runtime dependency
- `src/squadron/pipeline/sdk_session.py` — add `capture_summary()`;
  extend `compact()` with optional `summary=` kwarg
- `src/squadron/pipeline/emit.py` — NEW: registry, types, four
  built-in destinations
- `src/squadron/pipeline/actions/__init__.py` — add
  `ActionType.SUMMARY`
- `src/squadron/pipeline/actions/summary.py` — NEW: `SummaryAction`
  class and the shared `_execute_summary()` helper
- `src/squadron/pipeline/actions/compact.py` — refactor SDK path to
  delegate into `_execute_summary()` with `emit=[rotate]` baked in
- `src/squadron/pipeline/steps/__init__.py` — add
  `StepTypeName.SUMMARY`
- `src/squadron/pipeline/steps/summary.py` — NEW: `SummaryStepType`
  with validate/expand, checkpoint shorthand
- `src/squadron/pipeline/executor.py` — import-side-effect
  registration for new action + step modules
- `src/squadron/data/pipelines/test-pipeline.yaml` — add summary
  smoke step (or sibling fixture)

**Next planned slice:** 159 (Pipeline Fan-Out / Fan-In Step Type)

---

## Tasks

### T1 — Add `pyperclip` runtime dependency

- [ ] In `pyproject.toml`, add `pyperclip` to `[project] dependencies`
  with a minimum version constraint matching the current stable
  release (`pyperclip>=1.8.2`).
- [ ] Run `uv lock` (or `uv sync`) to refresh the lockfile.
- [ ] Confirm `uv run python -c "import pyperclip"` succeeds.
- [ ] Confirm `uv run ruff check src/ tests/` still passes after
  the dependency update.

**Test T1** — manual only

- [ ] On the developer machine (macOS), confirm
  `uv run python -c "import pyperclip; pyperclip.copy('hi'); print(pyperclip.paste())"`
  prints `hi`. This is a smoke check of the dependency, not an
  automated test.

**Commit:** `chore: add pyperclip dependency for summary clipboard emit`

---

### T2 — Add `SDKExecutionSession.capture_summary()` method

- [ ] In `src/squadron/pipeline/sdk_session.py`, add a new async
  method alongside the existing `compact()`:
  ```python
  async def capture_summary(
      self,
      instructions: str,
      summary_model: str | None = None,
      restore_model: str | None = None,
  ) -> str:
      """Generate a summary of the live session without rotating.

      Switches to summary_model if provided, dispatches instructions,
      captures the response as the summary, optionally restores the
      prior model, and returns the summary text. Does NOT disconnect
      the client or create a new session.
      """
  ```
- [ ] Implementation:
  1. If `summary_model` provided and differs from `current_model`,
     `await self.set_model(summary_model)`.
  2. Log DEBUG: `"SDKExecutionSession.capture_summary: dispatching instructions"`.
  3. `summary = await self.dispatch(instructions)`.
  4. If `restore_model` provided and differs from `current_model`
     after the dispatch, `await self.set_model(restore_model)`.
  5. Return `summary`.
- [ ] Allow exceptions to propagate; callers handle them.

**Test T2** — `tests/pipeline/test_sdk_session.py`

- [ ] Add test class `TestCaptureSummary`.
- [ ] Test: `capture_summary("instr")` with no model args dispatches
  once and returns the response text.
- [ ] Test: `capture_summary("instr", summary_model="haiku-id")`
  calls `set_model("haiku-id")` before dispatching.
- [ ] Test: `capture_summary("instr", restore_model="sonnet-id")`
  calls `set_model("sonnet-id")` after dispatching.
- [ ] Test: `capture_summary` does NOT call `disconnect()` and does
  NOT replace `self.client`.
- [ ] Test: exception from `dispatch()` propagates unchanged.

**Commit:** `feat: add SDKExecutionSession.capture_summary() method`

---

### T3 — Extend `SDKExecutionSession.compact()` with optional `summary` parameter

- [ ] In `sdk_session.py`, modify `compact()` signature:
  ```python
  async def compact(
      self,
      instructions: str,
      summary_model: str | None = None,
      restore_model: str | None = None,
      summary: str | None = None,
  ) -> str:
  ```
- [ ] Behavior change:
  - If `summary is None` (current slice 158 behavior): call
    `self.capture_summary(instructions, summary_model, restore_model=None)`
    to generate the summary, then proceed to disconnect/reconnect/seed.
    (Refactor: the first half of compact now reuses `capture_summary`.)
  - If `summary is not None`: SKIP the capture phase entirely.
    Proceed directly to disconnect → create new client → connect →
    seed with `frame_summary_for_seed(summary)` → restore_model if
    provided. Return the passed-in `summary` unchanged.
- [ ] Ensure the existing compact action's path (called with no
  `summary=` kwarg) is byte-identical to slice 158 behavior.
- [ ] Update the method's docstring to document the new parameter.

**Test T3** — `tests/pipeline/test_sdk_session.py`

- [ ] Update existing `TestCompactSessionRotate` tests to account
  for the refactor (should be no behavior change — these must all
  still pass unchanged after T3).
- [ ] Add test: `compact(instructions="x", summary="pre-made")`
  does NOT call `client.query("x")` on the old client (capture is
  skipped), but DOES call `client.query(frame_summary_for_seed("pre-made"))`
  on the new client.
- [ ] Add test: `compact(instructions="x", summary="pre-made",
  restore_model="sonnet-id")` calls `set_model("sonnet-id")` on the
  new client after seeding.
- [ ] Add test: `compact(instructions="x", summary="pre-made")`
  returns `"pre-made"` (unchanged).

**Commit:** `feat: add summary= overload to SDKExecutionSession.compact()`

---

### T4 — Create emit registry module and types

- [ ] Create `src/squadron/pipeline/emit.py`.
- [ ] Define `EmitKind` as a `StrEnum` with members `STDOUT`,
  `FILE`, `CLIPBOARD`, `ROTATE` (values: `"stdout"`, `"file"`,
  `"clipboard"`, `"rotate"`).
- [ ] Define `EmitDestination` as a frozen dataclass:
  ```python
  @dataclass(frozen=True)
  class EmitDestination:
      kind: EmitKind
      arg: str | None = None  # path for FILE; unused otherwise

      def display(self) -> str:
          """Human-readable form: 'stdout', 'file:/tmp/x.md', etc."""
          if self.kind is EmitKind.FILE:
              return f"file:{self.arg}"
          return self.kind.value
  ```
- [ ] Define `EmitResult` as a frozen dataclass:
  ```python
  @dataclass(frozen=True)
  class EmitResult:
      destination: str  # human-readable, from EmitDestination.display()
      ok: bool
      detail: str
  ```
- [ ] Define the registry:
  ```python
  EmitFn = Callable[
      [str, EmitDestination, "ActionContext"],
      Awaitable[EmitResult],
  ]
  _REGISTRY: dict[EmitKind, EmitFn] = {}

  def register_emit(kind: EmitKind, fn: EmitFn) -> None: ...
  def get_emit(kind: EmitKind) -> EmitFn: ...
  ```
- [ ] Add `__all__` exporting `EmitKind`, `EmitDestination`,
  `EmitResult`, `EmitFn`, `register_emit`, `get_emit`,
  `parse_emit_entry`, `parse_emit_list`.
- [ ] Do NOT register destination functions yet — those land in
  T5. The registry exists but is empty until then.

**Test T4** — `tests/pipeline/test_emit.py` (new file)

- [ ] Test: `EmitKind` enum values are lowercase strings matching
  the YAML grammar.
- [ ] Test: `EmitDestination(kind=EmitKind.FILE, arg="/tmp/x").display()`
  returns `"file:/tmp/x"`.
- [ ] Test: `EmitDestination(kind=EmitKind.STDOUT).display()`
  returns `"stdout"`.
- [ ] Test: `register_emit(EmitKind.STDOUT, fake_fn)` then
  `get_emit(EmitKind.STDOUT)` returns `fake_fn`.
- [ ] Test: `get_emit(EmitKind.CLIPBOARD)` on an empty registry
  raises `KeyError`.

**Commit:** `feat: add emit destination registry and types`

---

### T5 — Implement built-in emit destinations

- [ ] In `src/squadron/pipeline/emit.py`, implement the four
  built-in emit functions and register them at module import time:
  - `_emit_stdout(text, dest, ctx)` — prints the text via
    `print()` (not logger — must survive `--quiet`), returns
    `EmitResult(destination="stdout", ok=True, detail="")`.
  - `_emit_file(text, dest, ctx)` — resolves `dest.arg` relative
    to `ctx.cwd` if not absolute, creates parent directories
    (`mkdir(parents=True, exist_ok=True)`), writes text with
    UTF-8 encoding. On success returns
    `EmitResult(ok=True, detail=f"wrote {len(text.encode('utf-8'))} bytes")`.
    On `OSError`/`PermissionError`, logs a warning and returns
    `EmitResult(ok=False, detail=str(exc))`.
  - `_emit_clipboard(text, dest, ctx)` — calls
    `await asyncio.to_thread(pyperclip.copy, text)`. On
    `pyperclip.PyperclipException`, returns `ok=False` with the
    error message. On success returns `ok=True, detail=""`.
  - `_emit_rotate(text, dest, ctx)` — requires
    `ctx.sdk_session is not None`; returns
    `EmitResult(ok=False, detail="rotate emit requires SDK execution mode")`
    if not. Otherwise calls
    `await ctx.sdk_session.compact(instructions="", summary=text,
    restore_model=ctx.sdk_session.current_model)` and returns
    `EmitResult(ok=True, detail="session rotated")`. Exceptions
    from `compact()` produce `EmitResult(ok=False, detail=str(exc))`.
- [ ] Register all four via `register_emit(EmitKind.X, _emit_x)`
  at module scope (executed on import).
- [ ] Import `pyperclip` lazily inside `_emit_clipboard` so module
  import does not fail if pyperclip's platform probe fails.
  (Wrap `import pyperclip` in the function body, not at module top.)

**Test T5** — `tests/pipeline/test_emit.py`

- [ ] Test: `_emit_stdout("hello", ...)` prints "hello" to stdout
  (use pytest's `capsys` fixture) and returns `ok=True`.
- [ ] Test: `_emit_file("payload", EmitDestination(FILE, "/tmp/a/b.md"), ctx)`
  with `tmp_path` (override `ctx.cwd`) writes the file, creates
  parent dirs, returns `ok=True` with a byte count in detail.
- [ ] Test: `_emit_file` with a relative path resolves relative to
  `ctx.cwd`.
- [ ] Test: `_emit_file` on a read-only directory returns
  `ok=False` with an error message (use `tmp_path` with
  `chmod(0o555)`; skip on Windows if needed).
- [ ] Test: `_emit_clipboard("x", ...)` with `pyperclip.copy`
  monkeypatched to succeed returns `ok=True`.
- [ ] Test: `_emit_clipboard` with `pyperclip.copy` monkeypatched
  to raise `pyperclip.PyperclipException` returns `ok=False`.
- [ ] Test: `_emit_rotate("summary text", ...)` with
  `ctx.sdk_session = None` returns `ok=False` and does NOT raise.
- [ ] Test: `_emit_rotate` with a mocked session calls
  `session.compact(instructions="", summary="summary text",
  restore_model=...)` once and returns `ok=True`.
- [ ] Test: `_emit_rotate` propagates the captured summary to
  `compact()` without modification (verify via the mock's
  `call_args.kwargs["summary"]`).

**Commit:** `feat: implement stdout/file/clipboard/rotate emit destinations`

---

### T6 — Add `parse_emit_entry()` and `parse_emit_list()` helpers

- [ ] In `emit.py`, add:
  ```python
  def parse_emit_entry(entry: object) -> EmitDestination:
      """Parse a single YAML emit entry into an EmitDestination.

      Accepted forms:
        - "stdout" / "clipboard" / "rotate" -> bare strings
        - {"file": "<path>"} -> one-key dict with a non-empty string path
      Raises ValueError on any other shape.
      """

  def parse_emit_list(
      raw: object,
  ) -> list[EmitDestination]:
      """Parse a YAML emit value into a list of EmitDestination.

      - None or missing -> [EmitDestination(EmitKind.STDOUT)]
      - list[...] -> each entry parsed via parse_emit_entry
      - anything else -> ValueError
      """
  ```
- [ ] Default (None/missing) returns `[EmitDestination(kind=EmitKind.STDOUT)]`.
- [ ] Empty list is an error: `ValueError("emit list cannot be empty")`.
- [ ] Unknown kind is an error: `ValueError(f"unknown emit destination: {name!r}")`.
- [ ] `file:` with missing/empty `arg` is an error.

**Test T6** — `tests/pipeline/test_emit.py`

- [ ] Test: `parse_emit_list(None)` returns
  `[EmitDestination(EmitKind.STDOUT)]`.
- [ ] Test: `parse_emit_list(["stdout", "clipboard"])` returns
  two EmitDestinations with matching kinds.
- [ ] Test: `parse_emit_list([{"file": "/tmp/x.md"}])` returns one
  EmitDestination with kind=FILE and arg="/tmp/x.md".
- [ ] Test: `parse_emit_list(["rotate", {"file": "/tmp/y"}])`
  returns two in declared order.
- [ ] Test: `parse_emit_list([])` raises ValueError.
- [ ] Test: `parse_emit_list(["banana"])` raises ValueError with
  `"unknown emit destination"` in the message.
- [ ] Test: `parse_emit_list([{"file": ""}])` raises ValueError.
- [ ] Test: `parse_emit_list([{"file": 42}])` raises ValueError.
- [ ] Test: `parse_emit_list("stdout")` (not a list) raises
  ValueError.

**Commit:** `feat: add emit list parser`

---

### T7 — Add `ActionType.SUMMARY` and create summary action module

- [ ] In `src/squadron/pipeline/actions/__init__.py`, add
  `SUMMARY = "summary"` to the `ActionType` StrEnum.
- [ ] Create `src/squadron/pipeline/actions/summary.py`.
- [ ] Define `SummaryAction` implementing the action protocol with:
  - `action_type` property returning `ActionType.SUMMARY`.
  - `validate(config)` that checks:
    - `template` optional (string; default handled at execute time)
    - `model` optional (string)
    - `emit` optional (delegated to `parse_emit_list` — catch
      `ValueError` and produce `ValidationError(field="emit", ...)`)
  - `execute(context)` that delegates to the shared
    `_execute_summary()` helper (added in T8).
- [ ] Register via `register_action(ActionType.SUMMARY, SummaryAction())`
  at module bottom.

**Test T7** — `tests/pipeline/actions/test_summary.py` (new file)

- [ ] Test: `SummaryAction().action_type == "summary"`.
- [ ] Test: `validate({"template": "minimal-sdk"})` returns no errors.
- [ ] Test: `validate({"template": 42})` returns one error on field
  `"template"`.
- [ ] Test: `validate({"model": 42})` returns one error on field
  `"model"`.
- [ ] Test: `validate({"emit": ["banana"]})` returns one error on
  field `"emit"` with a useful message.
- [ ] Test: `validate({"emit": [{"file": "/tmp/x"}]})` returns no
  errors.

**Commit:** `feat: add SummaryAction with config validation`

---

### T8 — Implement `_execute_summary()` shared helper

- [ ] In `src/squadron/pipeline/actions/summary.py`, implement the
  shared helper:
  ```python
  async def _execute_summary(
      *,
      context: ActionContext,
      instructions: str,
      summary_model_alias: str | None,
      emit_destinations: list[EmitDestination],
      action_type: str,
  ) -> ActionResult:
      ...
  ```
- [ ] Flow:
  1. If `context.sdk_session is None`, return
     `ActionResult(success=False, action_type=action_type,
     outputs={}, error="summary action requires SDK execution mode")`.
  2. Resolve summary_model via `context.resolver.resolve(
     action_model=summary_model_alias, step_model=None)` if alias
     provided; else `model_id = None`.
  3. Capture `restore_model = context.sdk_session.current_model`.
  4. Call `summary = await context.sdk_session.capture_summary(
     instructions=instructions, summary_model=model_id,
     restore_model=restore_model)`.
  5. Iterate `emit_destinations` in order, calling each via
     `get_emit(dest.kind)(summary, dest, context)`. Collect
     `EmitResult`s into a list.
  6. If any emit whose `dest.kind == EmitKind.ROTATE` returned
     `ok=False`, return
     `ActionResult(success=False, action_type=action_type,
     outputs={...partial...}, error=<rotate detail>)`.
  7. Otherwise return
     `ActionResult(success=True, action_type=action_type, outputs={
       "summary": summary,
       "instructions": instructions,
       "emit_results": [{"destination": r.destination, "ok": r.ok,
                         "detail": r.detail} for r in results],
       "source_step_index": context.step_index,
       "source_step_name": context.step_name,
       "summary_model": model_id,
     }, metadata={"summary_model": model_id or ""})`.
- [ ] On exception from `capture_summary()`, return
  `ActionResult(success=False, action_type=action_type, outputs={},
  error=str(exc))`.
- [ ] Non-rotate emit failures log a WARNING via the module logger
  but do NOT affect the action's success status.

**Test T8** — `tests/pipeline/actions/test_summary.py`

- [ ] Test: execute with `emit=[stdout]` calls `capture_summary`
  once, then `_emit_stdout`, returns success with `emit_results`
  list of length 1 and `ok=True`.
- [ ] Test: execute with `emit=[stdout, file, clipboard]` calls
  three emits in order and the returned `emit_results` preserves
  order.
- [ ] Test: execute with `ctx.sdk_session=None` returns
  `success=False` with a clear error message and does NOT call
  any emit.
- [ ] Test: execute when `capture_summary` raises returns
  `success=False` with the exception message.
- [ ] Test: execute with a non-rotate emit that returns
  `ok=False` (mock the emit fn) still returns `success=True`;
  the failing emit is recorded in `emit_results` with `ok=False`.
- [ ] Test: execute with `emit=[rotate]` whose rotate emit returns
  `ok=False` returns `success=False` with the rotate error as the
  action's error.
- [ ] Test: execute with `emit=[stdout, rotate]` captures summary
  ONCE (verify `capture_summary` mock called exactly once, and
  verify `session.compact` is called by the rotate emit with the
  same summary text — not a fresh dispatch).
- [ ] Test: `summary_model_alias="haiku"` causes
  `resolver.resolve(action_model="haiku", step_model=None)` to be
  called and the resolved model ID is passed into `capture_summary`.
- [ ] Test: outputs include `source_step_index`, `source_step_name`,
  and `summary_model` matching the context and resolved model.

**Commit:** `feat: implement _execute_summary shared helper`

---

### T9 — Wire `SummaryAction.execute()` to `_execute_summary()`

- [ ] In `SummaryAction.execute()`:
  1. Extract `template_name = str(context.params.get("template", "default"))`.
  2. Try to load the template via `load_compaction_template(template_name)`;
     on `FileNotFoundError` return
     `ActionResult(success=False, action_type=self.action_type,
     outputs={}, error=str(exc))`.
  3. Render instructions via `render_instructions(template,
     keep=None, summarize=False, pipeline_params=context.params)`.
     (Summary step does not use `keep` / `summarize` fields —
     keep is a compact-era concept.)
  4. Parse `emit` from `context.params.get("emit")` via
     `parse_emit_list`; on `ValueError` return
     `ActionResult(success=False, ..., error=<msg>)`.
  5. Call `await _execute_summary(context=context,
     instructions=instructions,
     summary_model_alias=context.params.get("model"),
     emit_destinations=emit_destinations,
     action_type=self.action_type)`.

**Test T9** — `tests/pipeline/actions/test_summary.py`

- [ ] Test: execute with `params={"template": "minimal-sdk"}`
  loads the real `minimal-sdk.yaml` template from
  `src/squadron/data/compaction/`, renders instructions, and
  passes them through to `capture_summary`. (Use a real template,
  mock the SDK session.)
- [ ] Test: execute with `params={"template": "does-not-exist"}`
  returns `success=False` with a file-not-found error.
- [ ] Test: execute with no `emit` in params uses the default
  `[stdout]` and emits once.
- [ ] Test: execute with `params={"emit": ["banana"]}` returns
  `success=False` with a parse error (not `ValidationError` — the
  parse happens at execute time for dynamic emits).

**Commit:** `feat: wire SummaryAction.execute to shared helper`

---

> **End of Part 1.** Continue with
> [`161-tasks.summary-step-with-emit-destinations-2.md`](161-tasks.summary-step-with-emit-destinations-2.md)
> for tasks T10–T17 (compact alias refactor, summary step type,
> loader validation, integration tests, smoke pipeline, lint, and
> slice closeout).

