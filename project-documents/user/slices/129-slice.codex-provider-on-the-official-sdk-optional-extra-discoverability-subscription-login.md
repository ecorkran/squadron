---
docType: slice-design
slice: codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login
project: squadron
parent: project-documents/user/architecture/100-slices.orchestration-v2.md
dependencies: [review-transport-unification-provider-decoupling, tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage]
interfaces: []
dateCreated: 20261001
dateUpdated: 20261001
status: not_started
---

# Slice Design: Codex Provider on the Official SDK — Optional Extra, Discoverability, Subscription Login

## Overview

The `openai-oauth` provider (`src/squadron/providers/codex/`) imports `codex_app_server`, a GitHub-only package, and needs `npm i -g @openai/codex` for the binary. A ChatGPT-subscription user must find two manual installs, and `sq auth login openai-oauth` cannot log them in — it only reports whether `~/.codex/auth.json` exists.

OpenAI now publishes the SDK on PyPI as `openai-codex` (module `openai_codex`), which depends on `openai-codex-cli-bin` (the bundled binary). This slice ports the provider to it and makes the whole path — install, check, log in, review — reachable from squadron commands.

Three parts: **A** port + packaging, **B** discoverability, **C** `sq auth login/logout/status` for profiles whose strategy supports interactive login.

## Value

- `pip install 'squadron-ai[codex]'` (or the equivalent for the project's published name) then `sq auth login openai-oauth` then `sq review … --model codex-agent` works on a ChatGPT login with no API key and no npm.
- Users who do not want Codex install nothing extra.
- Effort on Codex reviews is applied rather than dropped (closes #171), and per-turn token usage is recorded when the SDK reports it.
- A missing piece is named at the point of failure with the exact command to fix it.

## Technical Scope

**Included**
- Port `providers/codex/agent.py` and `provider.py` to `openai_codex`.
- A single runtime resolver (bundled binary, else `codex` on PATH) shared by agent, provider, doctor.
- `codex` optional extra in `pyproject.toml`.
- Effort mapping, `applies_effort=True`, token-usage recording.
- Missing-package error, `sq doctor` Codex provider row, `sq model list` marker, README section.
- Interactive-login capability on the auth layer; `sq auth login` browser and `--device-code` flows; `sq auth logout`; account email/plan in `sq auth status`.

**Excluded**
- Any squadron-side token store — `~/.codex/auth.json` stays the only store, owned by the Codex runtime.
- `login_api_key` — API-key users keep the `openai` profile.
- Streaming, tool plumbing, or approval handling beyond today's `deny_all` behavior.
- Changing the `AuthStrategy` Protocol itself (see D3).

## Dependencies

### Prerequisites
- Slice 128: provider registry, `ProviderCapabilities`, `AuthStrategy` dispatch via `AUTH_STRATEGIES`, `"oauth"` auth type.
- Slice 931: `AgentConfig.effort`, `applies_effort` capability, `core/usage.py` (`TokenUsage`, `RunTelemetry`).
- External: `openai-codex` on PyPI. Version inspected for this design: 0.159.3 (requires Python >=3.10, `pydantic>=2.12`, pins `openai-codex-cli-bin==0.159.3`). Squadron requires >=3.12, so no conflict.

### Interfaces Required
- `openai_codex`: `AsyncCodex`, `CodexConfig(codex_bin=…)`, `Sandbox`, `ApprovalMode`, `ReasoningEffort`, `AsyncCodex.login_chatgpt()` → handle with `auth_url`, `login_chatgpt_device_code()` → handle with `verification_url`/`user_code`, handle `.wait()` → notification with `success`/`error`, `.cancel()`, `AsyncCodex.account()` → `GetAccountResponse` (`account.root` is `ChatgptAccount` with `email`, `plan_type`), `AsyncCodex.logout()`, `AsyncThread.run(..., effort=…)` → `TurnResult` with `usage: ThreadTokenUsage | None` (`last` = this turn).
- `squadron.core.usage.TokenUsage`/`RunTelemetry`, and the message-metadata stamping the OpenAI agent already uses (`metadata["usage"]`, `["turns"]`).

## Architecture

### Component Structure

```
providers/codex/
  runtime.py   NEW   resolve_codex_runtime() → CodexRuntime(source, path|None); probes importability only, no SDK types
  agent.py     EDIT  openai_codex port; effort; usage
  provider.py  EDIT  uses runtime.py; applies_effort=True
  auth.py      EDIT  OAuthFileStrategy implements InteractiveLogin
  login.py     NEW   async login/logout/account flows over AsyncCodex (with agent.py, one of two modules using SDK types)
providers/auth.py    EDIT  add InteractiveLogin Protocol (runtime_checkable)
cli/commands/auth.py EDIT  login/logout/status use InteractiveLogin
cli/commands/doctor_checks.py  EDIT  check_codex_provider row
cli/commands/models.py         EDIT  marker for aliases needing the extra
```

`openai_codex` is imported only inside functions, never at module top level, in `runtime.py`, `login.py`, and `agent.py`. The module graph therefore imports cleanly without the extra, and the provider still registers so `get_provider("openai-oauth")` can raise the install hint rather than "unknown provider". `agent.py` and `login.py` are the only modules that use SDK types; `runtime.py` only probes importability.

### Data Flow

**Review/task turn.** `create_agent` → `resolve_codex_runtime()` (raises `ProviderError` naming the extra if `openai_codex` is not importable; names the PATH fallback if neither binary exists) → `CodexAgent` lazily builds `CodexConfig(codex_bin=runtime.path)` (`None` = SDK's bundled binary) → `AsyncCodex.__aenter__` → `thread_start(model, sandbox=Sandbox(…), cwd, approval_mode=ApprovalMode.deny_all, base_instructions)` → `thread.run(prompt, effort=ReasoningEffort(effort.value))` → `TurnResult.final_response` → Message; `TurnResult.usage.last` mapped to `TokenUsage` and stamped on the message.

**Login.** `sq auth login <profile>` → resolve strategy → `isinstance(strategy, InteractiveLogin)`? yes → `login.login(mode)` → `AsyncCodex(config)` → `login_chatgpt()` (print `auth_url`, attempt `webbrowser.open`) or `login_chatgpt_device_code()` (print `verification_url` + `user_code`) → `handle.wait()` under a timeout → success/error → re-read `account()` and print email + plan. No → today's validate path, unchanged.

**Status.** For each profile: existing validity/source; if the strategy is `InteractiveLogin` and valid, append account email + plan from `account()`.

### State Management
No squadron state added. Credentials live in `~/.codex/auth.json`, written and refreshed by the Codex runtime. `CodexAgent` keeps its existing lazy client + thread lifecycle.

## Technical Decisions

### Technology Choices
- **D1 — `openai-codex` as an optional extra**, `codex = ["openai-codex>=0.159.3,<1"]` (floor is the version this design was inspected against; the upper bound is a PM call — see Special Considerations). Replaces the stale pyproject comment about GitHub installs. Alternative rejected: core dependency — adds a pydantic floor and a bundled native binary for every user.
- **D2 — Runtime resolution order: bundled binary first, `codex` on PATH second.** The SDK resolves the bundled binary itself when `codex_bin` is `None`; `resolve_codex_runtime()` checks `codex_cli_bin` importability, else `shutil.which("codex")`, else raises. Returns a typed `CodexRuntime` so agent, provider, and doctor share one definition (replaces `resolve_codex_binary()` and its three callers).
- **D3 — Interactive login is a separate Protocol, not a new `AuthStrategy` method.** `InteractiveLogin` (`async login(...)`, `async logout()`, `async account_summary()`) is `runtime_checkable`; `OAuthFileStrategy` implements it; the CLI tests `isinstance(strategy, InteractiveLogin)`. Adding methods to `AuthStrategy` would force every API-key strategy to stub them (ISP), and a profile-name or auth-type check is the string dispatch banned by slice 128.
- **D4 — Sandbox and approval via enums.** `credentials["sandbox"]` (today a free string defaulting to `"read-only"`) is validated through `Sandbox(value)`; an invalid value raises `ProviderError` listing the valid ones. The default is defined once as `Sandbox.read_only`. Today's `approval_policy="never"` becomes `ApprovalMode.deny_all` (the SDK maps it to `AskForApproval.never`).
- **D5 — Effort:** `ReasoningEffort(config.effort.value)`. Every squadron `Effort` value (`none, low, medium, high, xhigh`) exists in `ReasoningEffort`, so no mapping table. Passed on `thread.run(effort=…)`. Drops the slice-931 WARNING; sets `applies_effort=True`.
- **D6 — Token usage:** map `TurnResult.usage.last` (`input_tokens`, `cached_input_tokens`, `output_tokens`, `reasoning_output_tokens`) to `TokenUsage(prompt, cached, completion, reasoning)`; `None` when `usage` is `None` (never 0). Stamp via the same metadata keys the OpenAI agent uses so review artifacts need no change.
- **D7 — Login timeout** is one module-level constant in `login.py`, overridable by `--timeout`. On timeout or Ctrl-C the handle is cancelled (`handle.cancel()`) so the local callback listener is released.

- **D8 — Turn result is checked, not trusted.** After `thread.run`, `TurnResult.status` must be `TurnStatus.completed`; `failed` raises `ProviderError` carrying `TurnResult.error.message`, `interrupted` raises `ProviderError("Codex turn interrupted")`. A `completed` turn whose `final_response` is `None` or blank raises `ProviderError("Codex turn completed with no response text")`. The current `result.final_response or ""` is removed: an empty review must never reach the parser as a valid, empty Message (the dispatch no-op class of bug, issue #15).

### Failure Modes — Codex Turn

Each row is logged at WARNING or above (or raised as `ProviderError`, which callers log) and has a test asserting the signal.

| Failure | Behavior |
|---|---|
| `openai_codex` not installed | `ProviderError` with the install command, at `create_agent` |
| No bundled binary and none on PATH | `ProviderError` naming both remedies, at `create_agent` |
| Runtime subprocess fails to start / `initialize` fails | `ProviderError` wrapping the SDK error; client closed (the SDK closes on init failure) |
| Hang: no response from the runtime | Turn-level timeout (one constant, `--timeout`-style config, defined once) wrapping `thread.run`; on expiry cancel the turn, raise `ProviderError("Codex turn timed out after N s")` |
| Timeout or cancellation mid-turn | Turn handle interrupted and `shutdown()` still runs in `finally`, so no orphaned runtime process |
| Runtime exits / transport closes mid-turn (`TransportClosedError`) | `ProviderError` chained from the SDK error; agent state reset so a later message does not reuse the dead client (`_codex`/`_thread` cleared) |
| Server busy / rate-limited (`ServerBusyError`, `RetryLimitExceededError`) | `ProviderError` with the SDK message; no squadron-side retry |
| Not logged in / token rejected | Surfaces as `CodexRpcError` from the runtime → `ProviderError` whose text includes `sq auth login openai-oauth` |
| Turn `failed` or `interrupted` | `ProviderError` per D8 |
| Completed with empty `final_response` | `ProviderError` per D8 |
| `usage` absent | `TokenUsage` left `None` and a DEBUG log; not an error |
| Teardown error in `shutdown()` | Existing behavior: logged with `logger.exception`, not re-raised (process-boundary teardown) |

### Patterns and Conventions
- Failure modes are explicit and observable: the turn table above, plus login timeout, login `success=False` (surface `error`), and `account()` failure in `status` (log WARNING, still show validity). No silent fallbacks.
- The install hint string (`pip install 'squadron-ai[codex]'` form) is defined once in `runtime.py` and referenced by agent, provider, doctor, and `model list`.
- `CodexAgent` keeps its `except ProviderError: raise` / wrap-other-exceptions shape; SDK `CodexError` subclasses are wrapped into `ProviderError` with the original chained.

## Implementation Details

### API Contracts

CLI surface:

```
sq auth login <profile> [--device-code] [--timeout SECONDS]
sq auth logout <profile>
sq auth status
```

- `--device-code` on a profile whose strategy is not `InteractiveLogin` → error stating the profile does not support interactive login (not silently ignored).
- `sq auth logout` on a non-interactive profile → same error; there is nothing squadron can clear.
- `sq auth status` row for `openai-oauth`: `✓ authenticated | ~/.codex/auth.json (you@example.com, plus)`.

`InteractiveLogin` Protocol (shape only):

```python
@runtime_checkable
class InteractiveLogin(Protocol):
    async def login(self, *, device_code: bool, timeout: float, notify: Callable[[str], None]) -> None: ...
    async def logout(self) -> None: ...
    async def account_summary(self) -> str | None: ...
```

`notify` is how the strategy hands the URL / user code to the CLI without importing Rich.

### Sub-part B surfaces
- **Missing-package error:** `Codex support needs the optional extra: pip install 'squadron-ai[codex]'` (final distribution name confirmed against `pyproject.toml` `name` during implementation).
- **`sq doctor`:** new row `codex provider` in the integrations section, non-required: package importable + version, runtime source (`bundled` | `PATH: <path>`), login state from `auth.json` presence (no subprocess in doctor). The existing `codex CLI` row stays — it gates the `codex skills` row and is unrelated to the SDK.
- **`sq model list`:** for aliases whose profile's provider reports the extra missing, add `(needs [codex] extra)` to the Notes/Profile cell. Determined through the provider/strategy, not a hard-coded `"openai-oauth"` string. Shown in default and verbose output; absent when the extra is installed.
- **README:** replace the Codex install instructions with extra install → `sq auth login openai-oauth` → example review; note `--device-code` for SSH.

## Integration Points

### Provides to Other Slices
- `InteractiveLogin` — a pattern future OAuth-backed providers can implement without CLI changes.
- `CodexRuntime` resolver — reusable by any later Codex-adjacent feature.

### Consumes from Other Slices
- Slice 128 registry and capability declarations; slice 931 effort and usage plumbing. If `openai_codex` is absent the provider still registers and fails with the install hint — the rest of squadron is unaffected.

## Success Criteria

### Functional Requirements
- With the extra installed and a ChatGPT login, `sq review code <slice> --model codex-agent` completes with `OPENAI_API_KEY` unset and no `codex` on PATH.
- Without the extra, any `openai-oauth` use exits with an error containing the exact install command.
- `sq auth login openai-oauth` completes browser login; `--device-code` prints URL and user code and completes without a local browser; either leaves `~/.codex/auth.json` populated.
- `sq auth status` shows email and plan for a logged-in `openai-oauth`; `sq auth logout openai-oauth` removes the login.
- Other profiles' `sq auth login` behavior is byte-for-byte unchanged.
- An alias with `effort = "high"` on `codex-agent` reaches the SDK as `ReasoningEffort.high`; the review artifact records effort and usage.

### Technical Requirements
- No remaining reference to `codex_app_server`, `AppServerConfig`, or `resolve_codex_binary`.
- No profile-name or auth-type string comparison added; capability via `isinstance(…, InteractiveLogin)` and the provider's own report.
- Tests (SDK faked at the `openai_codex` import boundary, as existing codex tests do): runtime resolution (bundled / PATH / neither / package missing), one test per row of the Failure Modes — Codex Turn table asserting the raised `ProviderError`/log signal (including failed, interrupted, empty-response, timeout, transport-closed), sandbox validation, effort mapping, usage mapping incl. `None`, login success / `success=False` / timeout-cancels-handle, device-code path, status with and without `account()` failure, logout, `--device-code` on a non-interactive profile, doctor row states, model-list marker present/absent.
- At least one test imports against the real `openai_codex` types (skipped when the extra is absent) so a drifted SDK surface fails loudly.
- `ruff format`, `ruff check`, `pyright` clean.

### Integration Requirements
- Default install (no extra) passes the full existing test suite with `openai_codex` absent.
- `sq doctor` and `sq model list` run cleanly with and without the extra.

### Verification Walkthrough

1. Without the extra (fresh venv, `pip install squadron-ai`):
   `sq review code 128 --model codex-agent` → fails with the `pip install 'squadron-ai[codex]'` message.
   `sq model list` → `codex-agent` and `codex-spark` marked as needing the extra.
   `sq doctor` → `codex provider` row WARN with the same command.
2. `pip install 'squadron-ai[codex]'`; `sq doctor` → row shows package version, `runtime: bundled`, login: not logged in.
3. `sq auth login openai-oauth` → URL printed, browser opens, complete sign-in → `✓ openai-oauth: authenticated (you@example.com, <plan>)`.
4. On a headless/SSH box: `sq auth login openai-oauth --device-code` → URL + code printed; enter code on another device → same success line.
5. `sq auth status` → `openai-oauth` row shows source and account. Other profiles unchanged.
6. `env -u OPENAI_API_KEY sq review code 128 --model codex-agent -v` → review completes; saved artifact lists model, effort (if the alias sets one), and token usage.
7. `sq auth login sdk --device-code` → error: profile does not support interactive login.
8. `sq auth logout openai-oauth`; `sq auth status` → `✗ not authenticated`.

## Implementation Notes

### Development Approach
1. Part A first: `runtime.py`, agent/provider port, extra in `pyproject.toml`, effort + usage — tests against a faked SDK; then one real-types test.
2. Part B: error text, doctor row, model-list marker, README.
3. Part C: `InteractiveLogin` Protocol, `login.py`, `OAuthFileStrategy` implementation, CLI commands.
4. Smoke test (step 6 above) on a real ChatGPT login; the browser flow cannot be automated and is manual.

### Special Considerations
- **Version upper bound** for `openai-codex` is not decided here: the SDK is at 0.x and its generated surface moves. Floor is 0.159.3; PM to say whether to cap.
- **`OPENAI_API_KEY` fallback in `OAuthFileStrategy`** predates this slice. Whether the Codex app-server honors that key from the environment without `login_api_key` has not been verified; the smoke test runs with the key unset, and implementation must check this case and file an issue if the fallback does not actually work, rather than extend scope here.
- **Security:** squadron never reads or logs `auth.json` contents; only existence and the `account()` email/plan. Auth URLs and device codes are printed to the user's terminal only, not written to logs.
