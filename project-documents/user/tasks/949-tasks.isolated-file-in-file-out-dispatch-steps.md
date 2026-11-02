---
docType: tasks
slice: isolated-file-in-file-out-dispatch-steps
project: squadron
lld: user/slices/949-slice.isolated-file-in-file-out-dispatch-steps.md
dependencies: []
projectState: v0.24.13 released. Target is main (git.integration_branch unset). Slice
  949 design passed review.
dateCreated: 20261102
dateUpdated: 20261102
status: in_progress
turns: 25
promptTokens: 1367293
cachedTokens: 1284939
cacheWriteTokens: 82316
completionTokens: 20642
durationSeconds: 144.8
costUsd: 0.664577
usageRounds: 2
pricedRounds: 2
usageByModel:
  claude-sonnet-5-5:
    rounds: 2
    costUsd: 0.6645774000000002
    completionTokens: 20642
revision_number: 1
---

## Context Summary
- Working on slice 949: fixes [issue #284](https://github.com/ecorkran/squadron/issues/284). Adds five keys to the `dispatch` step (`prompt_files`, `reply_from`, `reply_format`, `reply_file`, `delivered_prompt_file`), a hard no-tools guard for `allowed_tools: []`, per-step-type `known_keys`, and `sq run <pipeline> --validate --strict`.
- Read the slice design first (D1–D9, API Contracts failure table, Success Criteria, Verification Walkthrough). Tasks cite decisions by number rather than repeating them.
- Existing code this slice builds on:
  - `pipeline/steps/dispatch.py` (`DispatchStepType`, `ARTIFACT_KEY`), `pipeline/steps/protocol.py` (`StepType`), `pipeline/steps/__init__.py` (`StepTypeName`, registry), and the step modules `branch`, `collection` (each), `compact`, `devlog`, `fan_out`, `gate`, `loop`, `phase`, `review`, `summary`.
  - `pipeline/loader.py`: `validate_pipeline`, `_validate_gate_references` (the pattern for `_validate_reply_references`).
  - `pipeline/actions/dispatch.py` (~1000 lines): `DispatchAction._dispatch`, `_dispatch_via_session`, `_dispatch_via_agent`, `_kept_outputs`.
  - `pipeline/actions/tool_support.py` (`resolve_allowed_tools`), `pipeline/failure_kind.py` (`FailureKind`), `pipeline/models.py` (`prior_output_key`), `pipeline/prompt_renderer.py` (`_render_dispatch`), `core/file_write.py` (`write_new_file`), `providers/base.py` (`ProviderCapabilities.can_read_files`).
  - CLI: `cli/commands/run.py` (`--validate` at the `validate_only` branch, `--strict` option).
  - Existing tests to extend or imitate: `tests/pipeline/steps/test_dispatch_step.py`, `tests/pipeline/steps/test_inner_steps.py`, `tests/pipeline/actions/test_dispatch*.py` and `dispatch_helpers.py`, `tests/pipeline/test_loader.py`, `tests/pipeline/test_builtin_pipelines.py`, `tests/pipeline/test_prompt_renderer.py`.
- Decisions made in this breakdown (the design left them to it):
  - **Order follows the design's Development Approach**: strict validation first (gives Amoeba a working probe), then the guard, then `dispatch_io`, then prompt-only, docs, CHANGELOG.
  - **`_dispatch` restructure** (design Special Considerations): resolving the prompt once and earlier means a session `set_model` failure now records the prompt identity. T15 notes this in a code comment; no other handling.
  - **Test files are new** (one per area) unless an existing file above is named; shared stub-provider helpers come from `tests/pipeline/actions/dispatch_helpers.py`.
- Next planned work: slice 949 code review (Phase 7 integration follows it).

## Tasks

### Part A: known keys and `--validate --strict`

- [x] **T1: Create the slice branch; add `known_keys` to the protocol and every step type** (Effort 3)
  - [x] Run `cf config get git.integration_branch` (target is its value, or `main` when empty); create `949-slice.isolated-file-in-file-out-dispatch-steps` from the target, or switch to it if it exists
  - [x] Add required `known_keys: frozenset[str]` to `StepType` in `steps/protocol.py` (D7)
  - [x] In `steps/dispatch.py`, add `DISPATCH_FORWARDED_KEYS` (today's five forwarded keys: `prompt`, `model`, `pre_emption_fragment`, `allowed_tools`, `feedback`) as the single list: `expand` iterates it, and `known_keys = DISPATCH_FORWARDED_KEYS | {ARTIFACT_KEY}`. Do not add the new keys yet
  - [x] Define `EXECUTOR_STEP_KEYS = frozenset({"loop", "step_model"})` once (put it in `steps/utils.py` or `steps/protocol.py`; cite `executor.py` as the reader) and confirm in `executor.py` that these are the only keys it reads on any step
  - [x] For each remaining step type, one sub-item: define a module constant beside its validate/expand code and expose it as `known_keys`, deriving the set by reading that module's `validate` and `expand`, not from memory. Container types include their inner-step source keys. Grep `register_step_type` first to confirm this list is complete (design, tasks and implement may share `PhaseStepType`):
    - [x] `branch.py`
    - [x] `collection.py` (each)
    - [x] `compact.py`
    - [x] `devlog.py`
    - [x] `fan_out.py`
    - [x] `gate.py`
    - [x] `loop.py`
    - [x] `phase.py`
    - [x] `review.py`
    - [x] `summary.py`
  - [x] SC: `ruff format`, `ruff check`, `pyright` clean (pyright proves no step type lacks `known_keys`)

- [x] **T2: `unknown_key_errors` and `validate_pipeline(strict=)`** (Effort 3)
  - [x] In `loader.py`, add `unknown_key_errors(steps)`: for each step, report one `ValidationError` per key not in `known_keys | EXECUTOR_STEP_KEYS`, `field=steps[<name>].<key>`; recurse via `inner_steps(config)` using the same `getattr` test `classification.py` uses; an unknown step type is already an error and is not recursed into (D8)
  - [x] `validate_pipeline(definition, *, strict: bool = False)`: unchanged when false; when true, append `unknown_key_errors(definition.steps)`
  - [x] SC: `ruff format`, `ruff check`, `pyright` clean

- [x] **T3: Test strict validation and built-in pipelines** (Effort 2)
  - [x] Create `tests/pipeline/test_known_keys.py`:
    1. one parametrized case per step type: a valid minimal config for that type passes strict; the same config plus `colour: red` yields exactly one error with `field=steps[<name>].colour`
    2. nested unknown key inside a `loop` body and an `each` body is reported with the nested step's name
    3. non-strict `validate_pipeline` on the same bad config returns no unknown-key error
  - [x] In `tests/pipeline/test_builtin_pipelines.py` (or the file that already loads every built-in), assert every YAML in `src/squadron/data/pipelines/` returns no errors with `strict=True` (Success Criterion 8). If one fails, a `known_keys` set is incomplete: fix the set, not the test
  - [x] SC: tests pass

  Note: strict validation found a dead `slice:` key on the `close-out` dispatch step in P6, P56, P456, implement and implement-plan (nothing reads it; dispatch `expand` never forwarded it). Removed it from those YAMLs rather than add `slice` to dispatch known_keys.

- [x] **T4: `--validate --strict` CLI** (Effort 2)
  - [x] In `cli/commands/run.py`, make the `validate_only` branch pass `strict=strict` to `validate_pipeline`; print errors and exit 1 as it does today
  - [x] Change the `--strict` help text to state both meanings (eager session construction; with `--validate`, also rejects unknown step keys)
  - [x] Tests (next to the existing `--validate` CLI tests; find with `grep -rn "\-\-validate" tests/`): a pipeline with an unknown key exits 1 under `--validate --strict` and prints `steps[<name>].<key>`; the same file exits 0 under plain `--validate`
  - [x] SC: `ruff format`, `ruff check`, `pyright` clean, touched tests pass

**Commit**: `feat: add known_keys per step type and sq run --validate --strict`

### Part B: no-tools guard

- [x] **T5: `FailureKind.TOOL_ISOLATION` and the guard helpers** (Effort 3)
  - [x] Add `TOOL_ISOLATION = "tool_isolation"` to `FailureKind` with a one-line comment; confirm it is not in `_PAUSING_KINDS` (the run fails, not pauses)
  - [x] In `tool_support.py`, add `declares_no_tools(context)` (`allowed_tools` present and equal to `[]`; absent key false) and `tool_isolation_error(...)` per D6: error when the route is the SDK session path, or the agent path whose provider has `capabilities.can_read_files`; returns `None` otherwise. The message names the step, the model and the provider and says to use a model whose provider runs no tools of its own (an `openrouter` alias)
  - [x] Extract `_agent_profile_name` in `actions/dispatch.py` from `_dispatch_via_agent` and call it from both the guard and `_dispatch_via_agent` (D6: they cannot disagree about the provider). No behavior change in `_dispatch_via_agent`
  - [x] SC: `ruff format`, `ruff check`, `pyright` clean; existing `tests/pipeline/actions/test_dispatch*.py` still pass

- [x] **T6: Test the guard helpers** (Effort 2)
  - [x] Create `tests/pipeline/actions/test_tool_isolation.py`:
    1. `declares_no_tools`: `[]` true; `["read"]`, absent and `None` false
    2. `tool_isolation_error`: session route errors; agent route errors when `can_read_files` is true (SDK one-shot, Codex `openai-oauth`) and returns `None` when false (`openai`); the test varies the capability value, never provider identity
    3. error text contains the step name, model and provider
  - [x] SC: tests pass

- [x] **T7: Wire the guard into `_dispatch`** (Effort 2)
  - [x] In `_dispatch`, after routing and before any prompt work: if `declares_no_tools(context)` and `tool_isolation_error(...)` returns a message, return a failed `ActionResult` with `metadata[FAILURE_KIND_KEY] = FailureKind.TOOL_ISOLATION` and log at WARNING (D6). Keep the existing truthiness guard for non-empty lists
  - [x] Check `src/squadron/data/` for `allowed_tools: []` (design says none) and say so in the commit body if confirmed
  - [x] Tests in `tests/pipeline/actions/test_tool_isolation.py` using the stub-provider helpers: SDK session, SDK one-shot and Codex routes fail before any model call (assert the stub is never called) with `failure_kind == "tool_isolation"` and a WARNING in `caplog`; an `openai`-provider route with `allowed_tools: []` runs and offers no tools; `allowed_tools` absent is unchanged; a `review` step with `allowed_tools: []` is unchanged (Excluded in the design)
  - [x] SC: `ruff format`, `ruff check`, `pyright` clean, tests pass

**Commit**: `feat: fail dispatch steps that declare allowed_tools [] on a tool-running provider`

### Part C: new keys, validation and reply lookup

- [x] **T8: New dispatch keys: constants and shape validation** (Effort 3)
  - [x] Create `pipeline/dispatch_keys.py`, a module with no imports from `steps/` or `actions/`, holding the five key-name constants, `ReplyFormat(StrEnum)` (`text`, `json`) and the shared path check (below). `steps/dispatch.py` and `actions/dispatch_io.py` both import from it. This departs from the design's component table, which puts `ReplyFormat` in `dispatch_io.py`: `steps/dispatch.py` already imports `actions/dispatch.py` at module level, so `steps/dispatch.py` → `dispatch_io.py` → `steps/dispatch.py` would be an import cycle (review F005)
  - [x] Create `pipeline/actions/dispatch_io.py` (module docstring citing slice 949 D2–D5); it imports the constants and `ReplyFormat` from `dispatch_keys.py`
  - [x] In `steps/dispatch.py`, add the five names to `DISPATCH_FORWARDED_KEYS` so `expand` forwards them and `known_keys` includes them. No literal key strings anywhere else (Patterns and Conventions)
  - [x] `validate` per D1: `prompt_files` is a non-empty list of strings (a bare string errors and says to use a list); `reply_format` is a `ReplyFormat` value; `reply_from` is a string; `reply_file` and `delivered_prompt_file` are strings and must differ; `feedback` with `prompt_files` or `reply_from` is an error
  - [x] Path check, one shared function in `dispatch_keys.py`: relative, no `..` part. Values containing a `{param}` placeholder skip it at load time (gate-reference convention) and the same function runs at run time (T14)
  - [x] SC: `ruff format`, `ruff check`, `pyright` clean

- [x] **T9: Test key validation** (Effort 2)
  - [x] Extend `tests/pipeline/steps/test_dispatch_step.py`: one case per rule in T8 (bare-string `prompt_files`, empty list, bad `reply_format`, absolute path, `..` path, placeholder path skipped, equal output paths, `feedback` combinations), plus `expand` forwards all five keys
  - [x] SC: tests pass

- [x] **T10: `results_for_step` and `_validate_reply_references`** (Effort 3)
  - [x] In `models.py` beside `prior_output_key`, add `results_for_step(prior_outputs, step_name)` returning that step's results in order; the key format stays defined in this one module (D3)
  - [x] In `loader.py`, add `_validate_reply_references` (called from `validate_pipeline`, like `_validate_gate_references`): `reply_from` must name an earlier top-level `dispatch` step; recurse into container bodies through `inner_steps` and reject any nested `reply_from` with "reply_from is supported on top-level steps only"
  - [x] SC: `ruff format`, `ruff check`, `pyright` clean

  Note: the design says to recurse through `inner_steps`, but fan_out's `inner_steps` returns a synthetic step, not its branch step. Added `body_steps` to loop, each and fan_out and used it for both the nested `reply_from` check and `unknown_key_errors`.

- [x] **T11: Test reply lookup and reference validation** (Effort 2)
  - [x] `tests/pipeline/test_models.py`: `results_for_step` returns results in order and nothing for an unknown step
  - [x] `tests/pipeline/test_reply_references.py`: valid earlier dispatch passes; later step, non-dispatch step, missing step, and `reply_from` inside `loop`, `each` and `fan_out` bodies each fail with the expected message (Success Criterion 6, load-time half)
  - [x] SC: tests pass

**Commit**: `feat: add dispatch file and reply keys with load-time validation`

### Part D: `dispatch_io` and the dispatch restructure

- [x] **T12: `extract_json_object`** (Effort 2)
  - [x] Add to `dispatch_io.py` `extract_json_object(text) -> str | None` exactly per D4: scan each `{` in order with `json.JSONDecoder(parse_constant=_reject).raw_decode`, return the original substring of the first success, reject `NaN`/`Infinity`/`-Infinity`, no re-serialization
  - [x] Tests in `tests/pipeline/actions/test_dispatch_io.py` (parametrized): bare object, fenced object, prose before and after, nested object returns the outer, malformed outer with valid inner returns the inner, `NaN`-only candidate returns `None`, no object returns `None`; returned text is byte-identical to the input span
  - [x] SC: tests pass; `ruff format`, `ruff check`, `pyright` clean

- [x] **T13: `assemble_prompt` and `DispatchInputError`** (Effort 3)
  - [x] Add `DispatchInputError` and `assemble_prompt(...)` to `dispatch_io.py` per D2: parts in order `prompt`, each file, the reply, joined by `"\n\n"`; a prompt-only step is returned unchanged; no placeholder substitution inside file content; each path must satisfy the T8 path check, then `Path.is_file()` before opening; read UTF-8; `OSError` (incl. `PermissionError`) and `UnicodeDecodeError` become `DispatchInputError` naming the path
  - [x] Tests (`test_dispatch_io.py`): order and separator; `{slice}` inside a file arrives unchanged; prompt-only unchanged; missing file, directory, FIFO (`os.mkfifo`; assert it does not block), permission denied (`chmod 000`; skip when running as root), invalid UTF-8, absolute and `..` run-time paths each raise `DispatchInputError` naming the path
  - [x] SC: tests pass; `ruff format`, `ruff check`, `pyright` clean

- [x] **T14: `step_reply` and `write_step_files`** (Effort 3)
  - [x] `step_reply(prior_outputs, step_name)` per D3: take the last `dispatch` result from `results_for_step`; return `outputs["reply_json"]` when present, else `outputs["response"]`; raise `DispatchInputError` naming the step when there is no dispatch result, it failed, or it has no `response`; an empty reply is never passed on
  - [x] `write_step_files(...)` per D5: record the prompt file's current bytes (or absence); write `delivered_prompt_file` first, then `reply_file` last, each with `write_new_file(path, content, force=True)`, UTF-8, nothing appended; any `OSError` from a write is wrapped in `OutputWriteError` (defined in `dispatch_io.py`, message names the path); on an `OSError` from the `reply_file` write, first restore the prompt file (or remove it if it was new), then raise `OutputWriteError`; if the restore itself fails, log at ERROR naming the prompt file and say a changed file remains
  - [x] Tests (`test_dispatch_io.py`): `step_reply` for response, `reply_json`, failed step, skipped step (no `response`), missing step; `write_step_files` writes exact bytes with no trailing newline; a failure injected on the `reply_file` write restores a pre-existing prompt file byte-identically and removes a new one; a failure injected on the restore logs ERROR (`caplog`) naming the prompt file; both targets unchanged after the failure
  - [x] SC: tests pass; `ruff format`, `ruff check`, `pyright` clean; `dispatch_io.py` stays under ~300 lines

**Commit**: `feat: add dispatch_io for prompt assembly, reply hand-off and output files`

- [x] **T15a: Resolve the prompt once in `_dispatch`** (Effort 3)
  - [x] Order inside `_dispatch` per the Data Flow: `_kept_outputs`, route, T7 guard, then resolve the prompt once via `asyncio.to_thread(assemble_prompt, ...)`, then the existing session or agent path receiving the resolved prompt (remove the prompt resolution now duplicated inside each path; do not change their other internals). `PromptSource` stays `EXPLICIT`
  - [x] `execute` catches `DispatchInputError`, logs WARNING, and returns a failed `ActionResult` before any model call
  - [x] Add a code comment at the new prompt-resolution call: a session `set_model` failure now records the prompt identity (design Special Considerations)
  - [x] Tests (`tests/pipeline/actions/test_dispatch_input.py`, stub provider): a missing prompt file fails the step before the stub is called, with a WARNING naming the path; `prompt_files` content reaches the stub in order
  - [x] SC: all existing `tests/pipeline/actions/test_dispatch*.py` pass unchanged; `ruff format`, `ruff check`, `pyright` clean

  Note: the paths keep their signatures (the routing tests assert `_dispatch_via_session(ctx, session)` and `_dispatch_via_agent(ctx)`), so each path resolves the prompt itself via `asyncio.to_thread(self._resolve_prompt, ...)`, once per dispatch. The session path now resolves before `set_model`, so an unreadable prompt file fails the step before the model switch. A `set_model` failure still records no prompt identity, so the code comment the task called for is not needed.

- [x] **T15b: Apply the reply contract after a successful dispatch** (Effort 3)
  - [x] Add `apply_reply_contract(...)` to `dispatch_io.py` so the logic lives there and `dispatch.py` gains only a call site (run via `asyncio.to_thread`): for `reply_format: json`, `extract_json_object` returning `None` yields a failed step with "reply contains no JSON object", keeps `outputs["response"]`, writes no files; on success it sets `outputs["reply_json"]` to the extracted substring while `outputs["response"]` keeps the full reply (State Management)
  - [x] It then calls `write_step_files`: `reply_file` receives `reply_json` for a JSON step, else `response`; `delivered_prompt_file` receives the final delivered text (after override and pre-emption prefixes are added)
  - [x] `OutputWriteError` is caught at the call site in `_dispatch`: log WARNING naming the path and return a failed `ActionResult` with that error (restore already happened in `write_step_files`)
  - [x] Tests (`test_dispatch_io.py` for the contract, `test_dispatch_input.py` for the call site): JSON step sets `reply_json` and writes it; text step writes `response`; no-JSON reply fails with the message and writes nothing; an injected write failure gives a failed `ActionResult` and a WARNING (`caplog`)
  - [x] SC: existing dispatch tests pass unchanged; `dispatch.py` gains call sites only; `ruff format`, `ruff check`, `pyright` clean

- [x] **T16: End-to-end test of the two-step pipeline** (Effort 2)
  - [x] Create `tests/pipeline/test_dispatch_file_io.py` with a stub provider and `tmp_path`, running Amoeba's two-step shape from the design (`allowed_tools: []` on a non-file-reading stub route). Unit tests already cover each rule; this file covers only the integrated criteria:
    1. happy path: `extract.prompt.md` holds prompt then `question.md` verbatim; `claims.json` is exactly the extracted object; `answer.prompt.md` ends with the `claims.json` bytes and does not contain `extract`'s prompt (Criteria 1, 2, 4)
    2. a non-JSON `extract` reply fails that step, and a pre-existing `claims.json` is byte-identical afterwards (Criterion 3)
    3. `reply_from` naming a step whose result failed or has no `response` fails the reading step with an error naming it (Criterion 6)
    4. resume: run the pipeline until `extract` succeeds and persist state, then resume from `answer`; `answer` receives the restored `claims.json` bytes (via `_seed_resume_outputs`). A second resume case whose persisted `extract` result is failed fails `answer` with an error naming `extract` (Criterion 6, "including on resume")
  - [x] SC: tests pass; `ruff format`, `ruff check`, `pyright` clean


  Note: case 3 is covered in two places. The failed-result variant runs through the executor as the second resume case (4); a failed step stops a live run, so it cannot be read in one. The no-response variant is `test_a_reply_from_an_unusable_result_fails_the_reader_naming_the_step` in `tests/pipeline/actions/test_dispatch_input.py`, which runs `DispatchAction` itself.
**Commit**: `feat: dispatch steps read files and earlier replies and write reply files`

### Part E: prompt-only, docs, final verification

- [ ] **T17: Reject the new keys in prompt-only mode** (Effort 2)
  - [ ] In `prompt_renderer.py`, `_render_dispatch` raises the renderer's existing error type when the step config has any of the five new keys; the message names the key and says to run with `sq run` (D9). `allowed_tools: []` behavior is unchanged
  - [ ] Tests in `tests/pipeline/test_prompt_renderer.py` (and `test_dispatch_render.py` if it covers `_render_dispatch`): one case per key raises and names it; a dispatch step without them renders as before; `allowed_tools: []` still renders (Success Criterion 9)
  - [ ] SC: tests pass; `ruff format`, `ruff check`, `pyright` clean

**Commit**: `feat: reject dispatch file keys in prompt-only mode`

- [ ] **T18: Docs and CHANGELOG** (Effort 2)
  - [ ] `docs/PIPELINES.md` dispatch section documents: the five keys with the Amoeba example; the JSON extraction rule; the file-write guarantee (whole-file replace, written only on success, both files unchanged on failure); the no-tools guard being dispatch-only and enforced only by `sq run` (not `--prompt-only`); `reply_from` top-level only; `--validate --strict`
  - [ ] CHANGELOG: short user-facing bullets for the new keys, `--validate --strict`, and the behavior change that `allowed_tools: []` on an SDK or Codex dispatch step now fails. Technical detail goes in DEVLOG, not CHANGELOG
  - [ ] SC: no code changes; links and key names match the implementation (grep each documented key in `src/`)

**Commit**: `docs: document dispatch file keys, tool guard and validate --strict`

- [ ] **T19: Full verification against the design** (Effort 2)
  - [ ] Run the full suite once (`pytest`), `ruff format`, `ruff check`, `pyright`; zero pyright errors
  - [ ] Walk the design's Verification Walkthrough steps 1–3 and 7 (validate, strict, prompt-only) in `/tmp/sq949`, using the real `sq`. Steps 4–6 call live models; run them only if a configured `deepseek4-flash` route is available, otherwise report them as not run
  - [ ] Confirm Success Criteria 1–9 each map to a passing test or a walkthrough step; list any unmapped criterion
  - [ ] Confirm new modules stay under ~300 lines (`wc -l` on `dispatch_io.py` and other new files)
  - [ ] SC: all checks clean; any gap is stated plainly. This task changes no files, so it has no commit marker
