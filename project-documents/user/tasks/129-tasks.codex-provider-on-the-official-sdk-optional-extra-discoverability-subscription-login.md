---
docType: tasks
slice: codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login
project: squadron
lld: user/slices/129-slice.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md
dependencies: [128, 931]
projectState: >
  Slice design complete (2026-10-01), not implemented. The openai-oauth provider still imports
  codex_app_server and resolves the binary with shutil.which("codex"); `sq auth login` only
  validates. Slices 128 (provider registry, AuthStrategy dispatch) and 931 (Effort, TokenUsage)
  are on main. Release 0.17.0 is current.
dateCreated: 20261001
dateUpdated: 20261001
status: not_started
---

## Context Summary

- Working on slice 129: port the `openai-oauth` provider from `codex_app_server` (GitHub-only)
  to the PyPI package `openai-codex` (module `openai_codex`), shipped as the optional extra
  `squadron-ai[codex]`, then make install → check → log in → review reachable from `sq`.
- Parts: **A** port + packaging + effort + usage, **B** discoverability (error text, `sq doctor`
  row, `sq models list` marker, README), **C** `sq auth login/logout/status` via a new
  `InteractiveLogin` Protocol.
- Design references below as "D1…D9" and "Failure Modes table" are in the slice design (`lld`).
- Prerequisites on main: slice 128 registry/`AUTH_STRATEGIES`; slice 931 `Effort`,
  `AgentConfig.effort`, `core/usage.py` (`TokenUsage`, `RunTelemetry`).
- Test convention: the SDK is faked at the `openai_codex` import boundary
  (`patch.dict("sys.modules", {...})`, as `tests/providers/codex/test_agent.py` does today).
  The default install has no `openai_codex`; the whole suite must pass that way.
- Every commit task means: `ruff format`, `ruff check`, `pyright` (zero errors) first, then
  commit with the stated message. Commit from the repo root. Slice branch:
  `129-slice.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login`
  from the target in `cf config get git.integration_branch` (or `main` if empty).
- Next planned slice: none consumes this slice's interfaces.

Effort scale: 1 (trivial) – 5 (largest).

---

# Part 0 — Precondition

## Task 1 — Verify the `OPENAI_API_KEY` fallback against the real runtime (Effort 2)

Design: Special Considerations. Must complete before any port work. Needs a real
`openai-codex` install, an `OPENAI_API_KEY`, and a machine state with no `~/.codex/auth.json`.
If any of those cannot be arranged by the agent, stop and ask the Project Manager to run the
check or supply the outcome — do not pick an outcome.

- [ ] Create the slice branch (see Context Summary)
- [ ] Install `openai-codex` into a throwaway venv (not the project env)
- [ ] With no `auth.json` (throwaway `CODEX_HOME`-style location only if the runtime supports
      one) and `OPENAI_API_KEY` set, run one real turn via the SDK
- [ ] Record the outcome in this task, one of:
  - [ ] **works** — key honored without `login_api_key`
  - [ ] **fails** — record the runtime's error text verbatim
  - [ ] Outcome: _(fill in)_
  - [ ] Success: outcome recorded with the evidence (error text or response) — not inferred

## Task 2 — Apply the Task 1 outcome to `OAuthFileStrategy` (Effort 2)

File: `src/squadron/providers/codex/auth.py`; tests: `tests/providers/codex/test_auth.py`.

- [ ] **If works:** keep the key fallback; add a test pinning `active_source == "OPENAI_API_KEY"`
      for a key-only environment (existing source label is already `OPENAI_API_KEY`)
- [ ] **If fails:** remove the key fallback from `is_valid`, `active_source`, `get_credentials`,
      and `setup_hint`; `setup_hint` points to `sq auth login openai-oauth` or the `openai` profile
  - [ ] Update existing tests that assert key-only is valid; add a test that a key-only
        environment is not valid and `get_credentials` raises `ProviderAuthError`
- [ ] Success: tests for the chosen outcome pass; the other outcome's behavior is absent
- [ ] Commit: `fix: resolve OPENAI_API_KEY fallback in OAuthFileStrategy against real runtime`

---

# Part A — Port, Packaging, Effort, Usage

## Task 3 — `codex` optional extra (D1) (Effort 1)

File: `pyproject.toml`.

- [ ] Replace the stale GitHub-install comment in `[project.optional-dependencies]` with
      `codex = ["openai-codex>=0.159.3,<1"]`
- [ ] Confirm the distribution name in `[project] name` (`squadron-ai`) matches the install
      hint in Task 5
- [ ] Do not add `openai-codex` to core dependencies or `dev`
- [ ] Success: `pip install -e '.[codex]'` resolves in a throwaway venv; `pip install -e .`
      does not pull `openai-codex`

## Task 4 — Timeout config keys (D7) (Effort 1)

File: `src/squadron/config/keys.py` (beside `cf.mcp_timeout_s`, same `ConfigKey` shape).

- [ ] Add `codex.turn_timeout_s` (int, default 1800), `codex.login_timeout_s` (int, default 300),
      `codex.account_timeout_s` (int, default 30), each with a description naming what it bounds
      (see D7 table)
- [ ] Test (alongside existing config-key tests under `tests/config/`): each key is registered,
      typed `int`, has the stated default, and is readable through the config layer
  - [ ] Success: tests pass
- [ ] Commit: `feat: add codex timeout config keys`

## Task 5 — `runtime.py` resolver (D2, D9 hint source) (Effort 3)

New file: `src/squadron/providers/codex/runtime.py`. No SDK types; `openai_codex` /
`codex_cli_bin` are probed with `importlib.util.find_spec` or a function-local import only.

- [ ] Define the install-hint constant once here (`pip install 'squadron-ai[codex]'` form) and
      the message text for "package missing" and "no binary anywhere" (names both remedies)
- [ ] `CodexRuntime` frozen dataclass: `source` (enum: `bundled` | `path`), `path: str | None`
      (`None` for bundled), `package_version: str | None`
- [ ] `resolve_codex_runtime()`: `openai_codex` not importable → `ProviderError` with the hint;
      `codex_cli_bin` importable → bundled; else `shutil.which("codex")` → path; else
      `ProviderError` naming both remedies
- [ ] Module imports cleanly with `openai_codex` absent (no top-level SDK import)
- [ ] Tests `tests/providers/codex/test_runtime.py`: bundled, PATH fallback, neither, package
      missing (message contains the exact hint), bundled preferred when both exist
  - [ ] Success: tests pass with `openai_codex` absent from the environment
- [ ] Commit: `feat: add Codex runtime resolver`

## Task 6 — Port `CodexAgent` client lifecycle to `openai_codex` (D2, D4) (Effort 4)

File: `src/squadron/providers/codex/agent.py`. Imports of `openai_codex` stay inside functions.

- [ ] Remove `resolve_codex_binary`, `_SDK_INSTALL_URL`, `_CLI_INSTALL_CMD`, the GitHub-install
      error text, and the `codex_app_server` / `AppServerConfig` imports
- [ ] Obtain the runtime via `resolve_codex_runtime()` (raises `ProviderError` with the hint);
      build `CodexConfig(codex_bin=runtime.path)` lazily on first message; update the class
      docstring to describe the extra and bundled binary
- [ ] Sandbox: define the default once as `Sandbox.read_only`; validate
      `credentials["sandbox"]` through `Sandbox(value)`; invalid value → `ProviderError`
      listing valid values (D4)
- [ ] `thread_start(model, sandbox=Sandbox(...), cwd, approval_mode=ApprovalMode.deny_all,
      base_instructions)`; keep the `model is None` guard and lazy single-client reuse
- [ ] Log client startup duration at DEBUG
- [ ] Keep `except ProviderError: raise` / wrap-others shape; keep `shutdown()` teardown
      behavior (logged with `logger.exception`, not re-raised)
- [ ] Update `tests/providers/codex/test_agent.py` fakes to the new module name and symbols
  - [ ] Tests: lazy start once and reuse across messages; `codex_bin=None` for bundled and path
        for PATH runtime; sandbox default; sandbox invalid value; `deny_all` passed;
        `base_instructions` only when set; package-missing error contains the hint
  - [ ] Success: tests pass
- [ ] Commit: `refactor: port CodexAgent to openai_codex client and runtime resolver`

## Task 7 — Turn result checks, timeout, SDK error wrapping (D8, D7, Failure Modes) (Effort 4)

File: `agent.py`. One test per Failure Modes row that applies to a turn; each asserts the raised
`ProviderError` or the WARNING+ log.

- [ ] Wrap `thread.run` in `asyncio.timeout(codex.turn_timeout_s)` (read via the config layer,
      no module default); on expiry interrupt the turn, raise
      `ProviderError("Codex turn timed out after N s")`; `shutdown()` still runs in `finally`
- [ ] After `run`: `TurnStatus.failed` → `ProviderError` carrying `TurnResult.error.message`;
      `interrupted` → `ProviderError("Codex turn interrupted")`; `completed` with `None`/blank
      `final_response` → `ProviderError("Codex turn completed with no response text")`;
      remove `final_response or ""`
- [ ] Wrap SDK `CodexError` subclasses into `ProviderError` with the original chained:
  - [ ] startup/`initialize` failure
  - [ ] `TransportClosedError` — also clear `_codex` and `_thread` so the next message does not
        reuse the dead client
  - [ ] `ServerBusyError` / `RetryLimitExceededError` — SDK message, no retry
  - [ ] `CodexRpcError` (not logged in / rejected) — text includes `sq auth login openai-oauth`
- [ ] Tests (one each): timeout, failed, interrupted, empty response, blank response,
      startup failure, transport closed (state reset, then a later message starts a new
      client), server busy, rpc error (hint text), teardown error still logged-not-raised
  - [ ] Success: tests pass; no test relies on a real subprocess
- [ ] Commit: `feat: check Codex turn results and bound turns with a timeout`

## Task 8 — Effort (D5, closes #171) (Effort 2)

Files: `agent.py`, `provider.py`.

- [ ] Remove the slice-931 "cannot apply effort" WARNING in `CodexAgent.__init__`
- [ ] Pass `effort=ReasoningEffort(config.effort.value)` to `thread.run` when
      `config.effort` is set; omit when `None`
- [ ] `CodexProvider.capabilities`: `applies_effort=True`
- [ ] Update the existing capabilities test that expects `applies_effort=False` for
      `openai-oauth` (`tests/providers/test_capabilities.py` / codex provider tests)
- [ ] Tests: each squadron `Effort` value reaches `thread.run` as the same-named
      `ReasoningEffort`; `None` passes no effort; no effort WARNING emitted
  - [ ] Success: tests pass
- [ ] Commit: `feat: apply effort on Codex turns`

## Task 9 — Token usage (D6) (Effort 3)

File: `agent.py`. Reuse `TokenUsage` / `RunTelemetry` from `core/usage.py`.

- [ ] Map `TurnResult.usage.last` (`input_tokens`, `cached_input_tokens`, `output_tokens`,
      `reasoning_output_tokens`) → `TokenUsage(prompt, cached, completion, reasoning)`
- [ ] `usage is None` → usage left unreported (never 0) and a DEBUG log
- [ ] Stamp the response `Message` with the same metadata keys the OpenAI agent uses
      (`metadata["usage"]`, `metadata["turns"]`; see `providers/openai/agent.py` stamping),
      so review artifacts need no change
- [ ] Tests: full mapping; a field the SDK omits stays `None`; `usage=None` → `not reported`
      plus DEBUG log; metadata keys present on the yielded Message
  - [ ] Success: tests pass
- [ ] Commit: `feat: record Codex per-turn token usage`

## Task 10 — Port `CodexProvider` to the runtime resolver (D2) (Effort 2)

File: `src/squadron/providers/codex/provider.py`.

- [ ] `create_agent`: keep the credentials check; call `resolve_codex_runtime()` (raises with the
      hint) instead of `resolve_codex_binary()`; no subprocess spawn
- [ ] `validate_credentials`: `True` only when `resolve_codex_runtime()` succeeds and
      `OAuthFileStrategy().is_valid()`; a `ProviderError` from the resolver → `False`
      (specific exception, with a comment why swallowing is correct)
- [ ] Provider still registers when `openai_codex` is absent so `get_provider("openai-oauth")`
      raises the install hint, not "unknown provider"
- [ ] Update `tests/providers/codex/test_provider.py` and `test_registration.py` (they patch
      `resolve_codex_binary` and `codex_app_server` today)
  - [ ] Tests: create_agent without package → hint; no binary → both remedies; no credentials →
        `ProviderAuthError`; `validate_credentials` true/false matrix; registration works with
        the package absent
  - [ ] Success: tests pass
- [ ] Commit: `refactor: port CodexProvider to the runtime resolver`

## Task 11 — Remove stale references (Effort 1)

- [ ] `grep -rn "codex_app_server\|AppServerConfig\|resolve_codex_binary" src tests README.md docs`
      returns nothing
- [ ] Success: zero matches (Technical Requirements)
- [ ] Commit only if the grep required edits: `chore: remove codex_app_server references`

## Task 12 — Real-types SDK drift test (Technical Requirements) (Effort 2)

New test in `tests/providers/codex/` (e.g. `test_sdk_surface.py`).

- [ ] `pytest.importorskip("openai_codex")`; assert the names the code imports exist and are
      constructible/usable: `AsyncCodex`, `CodexConfig(codex_bin=…)`, `Sandbox.read_only`,
      `ApprovalMode.deny_all`, every `ReasoningEffort` member matching each squadron `Effort`
      value, `TurnStatus.completed`; and that `AsyncCodex` exposes `login_chatgpt`,
      `login_chatgpt_device_code`, `account`, `logout` (used in Part C)
- [ ] Success: passes with the extra installed in a throwaway venv; reports skipped (not failed)
      without it

## Task 13 — Part A gate: default-install suite (Effort 1)

- [ ] Run the full test suite in an environment **without** `openai_codex`; all pass
- [ ] `tests/test_import_purity.py` passes (no import-time home/.env reads in new modules)
- [ ] `ruff format`, `ruff check`, `pyright` clean. If `pyright` reports missing-import errors in
      `runtime.py` (function-local imports only; expected none), fix there rather than widening
      the exclude list
- [ ] Commit any fixes: `chore: part A validation fixes`

---

# Part B — Discoverability

## Task 14 — `ExtraRequirement` Protocol and `CodexProvider` implementation (D9) (Effort 2)

Files: `src/squadron/providers/base.py`, `providers/codex/provider.py`.

- [ ] Add `ExtraRequirement` (`@runtime_checkable`) with `missing_extra_hint() -> str | None`
      beside `AgentProvider`
- [ ] `CodexProvider.missing_extra_hint()`: `None` when `resolve_codex_runtime()` succeeds,
      otherwise the hint from `runtime.py` (the one definition; no new string)
- [ ] Providers without optional dependencies do not implement it
- [ ] Tests: `isinstance(CodexProvider(), ExtraRequirement)`; hint returned when package missing,
      `None` when present; a provider without the method is not an `ExtraRequirement`
  - [ ] Success: tests pass
- [ ] Commit: `feat: add ExtraRequirement protocol and Codex implementation`

## Task 15 — Missing-package error text audit (Effort 1)

- [ ] Confirm agent, provider, and (later) doctor / model list all take the hint from
      `runtime.py`; no duplicated install string anywhere in `src`
- [ ] Test: grep-style assertion or targeted test that the literal install command appears in
      exactly one source module
  - [ ] Success: one definition site

## Task 16 — `sq doctor` `codex provider` row (D9, Sub-part B) (Effort 3)

File: `src/squadron/cli/commands/doctor_checks.py`. No import probing or `shutil.which` in the
doctor module itself (the existing `codex CLI` row stays unchanged).

- [ ] `check_codex_provider()`: non-required row in the integrations section
- [ ] Missing-extra determination and hint from the registered provider's
      `ExtraRequirement.missing_extra_hint()` (via `ensure_provider_loaded` + `get_provider`)
- [ ] Detail (package version, `runtime: bundled` | `runtime: PATH: <path>`) from
      `resolve_codex_runtime()`; login state from `auth.json` presence only (no subprocess)
- [ ] States: extra missing → WARN with the install command as `fix_hint`; installed + logged in
      → OK; installed + not logged in → WARN pointing to `sq auth login openai-oauth`
- [ ] Register in `run_all_checks` beside `codex CLI` via `_run`
- [ ] Tests in `tests/cli/test_doctor_checks.py` (match existing style): the three states plus
      bundled vs PATH detail; `sq doctor` end-to-end runs cleanly with and without the extra
  - [ ] Success: tests pass
- [ ] Commit: `feat: add codex provider row to sq doctor`

## Task 17 — `sq models list` marker (D9) (Effort 2)

File: `src/squadron/cli/commands/models.py`.

- [ ] For each alias, resolve its profile's provider through `ensure_provider_loaded` +
      `get_provider`; if `isinstance(provider, ExtraRequirement)` and `missing_extra_hint()` is
      not `None`, add `(needs [codex] extra)` to the Notes/Profile cell. No profile-name check;
      the marker text derives from the hint
- [ ] Shown in default and verbose output; absent when the extra is installed
- [ ] A profile whose provider cannot be resolved must not break the listing (specific
      exception, WARNING log, no marker)
- [ ] Tests in `tests/cli/test_model_list.py`: marker present for `codex-agent` and
      `codex-spark` when missing, in default and verbose; absent when installed; other
      aliases never marked
  - [ ] Success: tests pass
- [ ] Commit: `feat: mark Codex aliases that need the extra in sq models list`

## Task 18 — README (Effort 1)

File: `README.md`, section "Using Codex (experimental)".

- [ ] Replace the npm + GitHub SDK instructions with: install the extra →
      `sq auth login openai-oauth` → example `sq review … --model codex-agent`; note
      `--device-code` for SSH/headless
- [ ] Success: no mention of `npm i -g @openai/codex` as a requirement for this path (the
      separate `codex CLI` skills note stays); install command matches the single definition
- [ ] Commit: `docs: document Codex extra install and login in README`

---

# Part C — Interactive Login

## Task 19 — `InteractiveLogin` Protocol (D3) (Effort 1)

File: `src/squadron/providers/auth.py`. `AuthStrategy` is not changed.

- [ ] Add `InteractiveLogin` (`@runtime_checkable`): `async login(*, device_code: bool,
      timeout: float, notify: Callable[[str], None]) -> None`, `async logout() -> None`,
      `async account_summary() -> str | None`
- [ ] Tests in `tests/providers/test_auth.py`: a stub implementing all three is an
      `InteractiveLogin`; `ApiKeyStrategy`-style strategies are not
  - [ ] Success: tests pass
- [ ] Commit: `feat: add InteractiveLogin protocol`

## Task 20 — `login.py`: login flows (D7, Login data flow) (Effort 4)

New file: `src/squadron/providers/codex/login.py`. `openai_codex` imported inside functions.
Calls `resolve_codex_runtime()` before touching the SDK.

- [ ] `login(*, device_code, timeout, notify)`: build `AsyncCodex(CodexConfig(codex_bin=…))`;
      browser mode → `login_chatgpt()`, `notify(auth_url)`, attempt `webbrowser.open`;
      device-code mode → `login_chatgpt_device_code()`, `notify` the `verification_url` and
      `user_code`; `await handle.wait()` under `asyncio.timeout(timeout)`
- [ ] Notification `success=False` → raise with its `error`; timeout or Ctrl-C /
      `CancelledError` → `handle.cancel()` (releases the callback listener), then raise a
      timeout/cancel error; runtime always shut down in `finally`
- [ ] Auth URLs and device codes are only passed to `notify`, never logged
- [ ] Tests (SDK faked): browser success; device-code success (URL + code reach `notify`);
      `success=False` surfaces `error`; timeout cancels the handle; cancellation cancels the
      handle; `webbrowser.open` failure does not fail the login; extra absent → install hint,
      no `ImportError`
  - [ ] Success: tests pass; no URL/code appears in captured logs
- [ ] Commit: `feat: add Codex login flows`

## Task 21 — `login.py`: logout and account summary (D7, Failure Modes) (Effort 3)

File: `login.py`.

- [ ] `account_summary()`: runtime start + `account()` under
      `asyncio.timeout(codex.account_timeout_s)`; returns `"<email>, <plan_type>"`; on timeout or
      SDK error log WARNING and return `None` (never raise)
- [ ] `logout()`: runtime start + `logout()` under the same timeout; timeout or SDK error
      propagates as an error (command exits non-zero in Task 24)
- [ ] Only email/plan are read; `auth.json` contents are never read or logged
- [ ] Tests: summary format; `account()` raising → `None` + WARNING; `account()` timeout →
      `None` + WARNING; logout success; logout timeout raises; logout SDK error raises;
      extra absent → install hint
  - [ ] Success: tests pass
- [ ] Commit: `feat: add Codex logout and account summary`

## Task 22 — `OAuthFileStrategy` implements `InteractiveLogin` (D3) (Effort 2)

File: `src/squadron/providers/codex/auth.py`.

- [ ] Add `login`, `logout`, `account_summary` delegating to `login.py`; no change to the
      `AuthStrategy` surface
- [ ] `account_summary()` returns `None` when the strategy is not valid (no spawn for an
      unauthenticated profile); when the extra is absent it returns `None` without spawning
      (status shows the install command; see Task 25)
- [ ] Tests in `tests/providers/codex/test_auth.py`: `isinstance(OAuthFileStrategy(),
      InteractiveLogin)`; delegation to `login.py`; invalid strategy skips the runtime
  - [ ] Success: tests pass
- [ ] Commit: `feat: OAuthFileStrategy supports interactive login`

## Task 23 — `sq auth login` (Effort 3)

File: `src/squadron/cli/commands/auth.py`; tests `tests/cli/test_auth.py`.

- [ ] Add `--device-code` and `--timeout SECONDS` options; `--timeout` defaults to
      `codex.login_timeout_s` read through the config layer (no literal in the command)
- [ ] Strategy is `InteractiveLogin` → `strategy.login(...)` with `notify` printing via Rich;
      on success re-read `account_summary()` and print
      `✓ <profile>: authenticated (<email>, <plan>)`; failure/timeout → red error, exit 1
- [ ] Not `InteractiveLogin` and `--device-code` given → error that the profile does not support
      interactive login, exit non-zero
- [ ] Not `InteractiveLogin`, no flag → today's validate path, output byte-for-byte unchanged
- [ ] Extra absent → exit non-zero with the install command, no traceback
- [ ] Tests: interactive success line; device-code mode passed through; `--timeout` override;
      failure and timeout exit non-zero; `sdk --device-code` error; unchanged output for a
      non-interactive profile (compare to existing test expectation); extra absent
  - [ ] Success: tests pass
- [ ] Commit: `feat: sq auth login performs interactive login for supporting profiles`

## Task 24 — `sq auth logout` (Effort 2)

File: `cli/commands/auth.py`.

- [ ] New command `logout <profile>`: `InteractiveLogin` → `strategy.logout()`, print
      confirmation; non-interactive profile → same "does not support interactive login" error
      (nothing squadron can clear), exit non-zero; unknown profile → existing error style
- [ ] SDK error or `codex.account_timeout_s` timeout → exit non-zero with the error text
- [ ] Extra absent → exit non-zero with the install command, no traceback
- [ ] Tests: success; non-interactive profile; unknown profile; logout timeout; SDK error;
      extra absent
  - [ ] Success: tests pass
- [ ] Commit: `feat: add sq auth logout`

## Task 25 — `sq auth status` account details (Effort 2)

File: `cli/commands/auth.py`.

- [ ] For each valid profile whose strategy is `InteractiveLogin`, append
      `(<email>, <plan>)` from `account_summary()` to the Source cell
      (`~/.codex/auth.json (you@example.com, plus)`)
- [ ] `account_summary()` returns `None` (failure/timeout) → row shows validity and source only;
      other profiles' rows still render; the command never fails because of it
- [ ] Extra absent → Source cell shows the install command in place of account details; the
      runtime is not spawned
- [ ] Non-interactive and invalid profiles unchanged
- [ ] Tests: row with account; `account_summary` → `None`; a failing profile does not block
      later rows; extra absent; non-interactive rows unchanged
  - [ ] Success: tests pass
- [ ] Commit: `feat: show Codex account in sq auth status`

---

# Closeout

## Task 26 — Full validation (Effort 1)

- [ ] Full test suite in an environment without `openai_codex`: all pass
- [ ] Full test suite with the extra installed (throwaway venv): all pass, real-types test runs
- [ ] `ruff format --check`, `ruff check`, `pyright`: zero errors
- [ ] No string dispatch added: no profile-name or auth-type comparison in the diff
      (`git diff` review of `cli/commands/*.py`, `providers/codex/*.py`)
- [ ] Technical Requirements grep from Task 11 still clean
- [ ] Commit any fixes: `chore: slice 129 validation fixes`

## Task 27 — Slice closeout (Effort 1)

- [ ] `CHANGELOG.md`: short user-facing bullets (extra install, `sq auth login/logout`,
      doctor row, models marker, effort/usage on Codex; closes #171)
- [ ] Mark every task above `[x]` (including dropped/skipped items) before closing; delegate
      to `task-checker`
- [ ] Set slice design `status` and the slice-plan entry to complete
- [ ] DEVLOG entry per `prompt.ai-project.system.md` Session State Summary
- [ ] Merge the slice branch into the target (re-read `cf config get git.integration_branch`
      first); stop and ask the Project Manager if checkout or merge fails
- [ ] Commit: `docs: complete slice 129`

## Manual verification (Project Manager, not a checklist item)

The browser login, device-code login on a headless box, and the real-account review smoke test
(Verification Walkthrough steps 3, 4, 6 and 8 in the slice design) need a real ChatGPT account
and a browser, and cannot be run by an agent. Steps 1, 2, 5 and 7 are covered by tests above.
