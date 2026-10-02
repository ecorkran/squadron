---
docType: slice-design
slice: codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login
project: squadron
parent: project-documents/user/architecture/100-slices.orchestration-v2.md
dependencies: [review-transport-unification-provider-decoupling, tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage]
interfaces: []  # none: InteractiveLogin is provided but no planned slice consumes it
dateCreated: 20261001
dateUpdated: 20261002
status: in_progress
---

# Slice Design: Codex Provider on the Official SDK — Optional Extra, Discoverability, Subscription Login

## Overview

The `openai-oauth` provider (`src/squadron/providers/codex/`) imports `codex_app_server`, a GitHub-only package, and needs `npm i -g @openai/codex` for the binary. A ChatGPT-subscription user must find two manual installs, and `sq auth login openai-oauth` cannot log them in — it only reports whether `~/.codex/auth.json` exists.

OpenAI now publishes the SDK on PyPI as `openai-codex` (module `openai_codex`), which depends on `openai-codex-cli-bin` (the bundled binary). This slice ports the provider to it and makes the whole path — install, check, log in, review — reachable from squadron commands.

Three parts: **A** port + packaging, **B** discoverability, **C** `sq auth login/logout/status` for profiles whose strategy supports interactive login.

> **Revised 20261002 (D1, D10):** the SDK was first shipped as an optional `codex` extra. Review found that the usual upgrade command, `uv tool install --upgrade squadron-ai`, silently uninstalls an extra, so `openai-codex` is now a core dependency and every missing-extra surface was removed. The slice name still says "Optional Extra"; the content below describes the shipped design.

## Value

- A normal `uv tool install squadron-ai`, then `sq auth login openai-oauth`, then `sq review … --model codex-agent` works on a ChatGPT login with no API key, no npm, and no extra install step. Upgrades use whatever command the user already uses.
- Effort on Codex reviews is applied rather than dropped (closes #171), and per-turn token usage is recorded when the SDK reports it.
- A missing login is named at the point of failure with the exact command to fix it.

## Technical Scope

**Included**
- Port `providers/codex/agent.py` and `provider.py` to `openai_codex`.
- `openai-codex` as a core dependency in `pyproject.toml`; the SDK locates its bundled runtime binary itself.
- Effort mapping, `applies_effort=True`, token-usage recording.
- `sq doctor` Codex provider row, `sq setup` sign-in step, README section.
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
  agent.py     EDIT  openai_codex port; effort; usage
  provider.py  EDIT  credential check only; applies_effort=True
  auth.py      EDIT  OAuthFileStrategy implements InteractiveLogin
  login.py     NEW   async login/logout/account flows over AsyncCodex (with agent.py, one of two modules using SDK types)
providers/auth.py    EDIT  add InteractiveLogin Protocol (runtime_checkable)
config/keys.py       EDIT  codex.turn_timeout_s, codex.login_timeout_s, codex.account_timeout_s
cli/commands/auth.py EDIT  login/logout/status use InteractiveLogin
cli/commands/doctor_checks.py  EDIT  check_codex_provider row
cli/commands/setup_steps.py    EDIT  Codex sign-in step
```

`agent.py` and `login.py` are the only modules that use SDK types. They import `openai_codex` inside functions (types under `TYPE_CHECKING`), so tests can substitute a fake SDK at the import boundary and no runtime is spawned in unit tests. Both are type-checked by pyright against the real SDK.

### Data Flow

**Review/task turn.** `create_agent` (checks `auth.json` presence) → `CodexAgent` lazily builds `CodexConfig()` (the SDK resolves its bundled binary) → `AsyncCodex.__aenter__` → `thread_start(model, sandbox=Sandbox(…), cwd, approval_mode=ApprovalMode.deny_all, base_instructions)` → `thread.run(prompt, effort=ReasoningEffort(effort.value))` → `TurnResult.final_response` → Message; `TurnResult.usage.last` mapped to `TokenUsage` and stamped on the message.

**Runtime startup cost.** Each `AsyncCodex.__aenter__` spawns the Codex app-server subprocess and performs `initialize`. Squadron pays this once per `CodexAgent` (the existing lazy client, reused for every later message in that agent), never per message. No latency target is set: the cost is dominated by the agentic turn itself, and the hang case is already bounded by `codex.turn_timeout_s`. Spawning is confined to three places — a Codex turn, `sq auth login/logout`, and `sq auth status` for a profile that is already valid (bounded by `codex.account_timeout_s`). `create_agent`, `validate_credentials`, `sq doctor`, and `sq models list` never spawn the runtime; they check file presence only. Startup duration is logged at DEBUG so a slow start is diagnosable without a benchmark task.

**Login.** `sq auth login <profile>` → resolve strategy → `isinstance(strategy, InteractiveLogin)`? yes → `login.login(mode)` → `AsyncCodex(config)` → `login_chatgpt()` (print `auth_url`, attempt `webbrowser.open`) or `login_chatgpt_device_code()` (print `verification_url` + `user_code`) → `handle.wait()` under a timeout → success/error → re-read `account()` and print email + plan. No → today's validate path, unchanged.

**Status.** For each profile: existing validity/source; if the strategy is `InteractiveLogin` and valid, append account email + plan from `account()`.

### Relationship to the architecture's auth model
`100-arch.orchestration-v2.md` (Authentication Patterns) states that squadron does not unify authentication and each provider's credential resolution is self-contained. `InteractiveLogin` is net-new relative to that document — no provider so far has had a login action — but it does not unify anything: it is an optional capability that only the Codex strategy implements, it delegates entirely to the Codex runtime, and squadron stores no credentials. The architecture text stays accurate; this slice adds a capability, not a shared auth layer. If a second provider adopts `InteractiveLogin`, the architecture's Authentication Patterns section should gain a sentence then; it is not edited here.

### State Management
No squadron state added. Credentials live in `~/.codex/auth.json`, written and refreshed by the Codex runtime. `CodexAgent` keeps its existing lazy client + thread lifecycle.

## Technical Decisions

### Technology Choices
- **D1 — `openai-codex` as a core dependency**, `"openai-codex>=0.159.3,<1"` in `[project] dependencies`. The floor is the version this design was inspected against. The cap stays at `<1` rather than a minor version: the SDK releases faster than weekly, so a tighter cap would break installs on every release, and API drift is caught by the real-types test (Technical Requirements) instead. Replaces the stale pyproject comment about GitHub installs. Cost, measured: the bundled runtime is 302 MB (the core Claude SDK already bundles 223 MB); `openai-codex-cli-bin` publishes wheels for macOS, Linux glibc/musl and Windows on x86 and ARM, wider than the Claude SDK's; pydantic's floor rises to 2.12 through the SDK. *Revised 20261002:* first shipped as an optional `codex` extra to avoid that cost. Rejected after implementation because an extra is easy to lose (see D10), and every surface that existed only to explain a missing extra went with it.
- **D2 — The SDK's bundled binary is the only runtime.** `CodexConfig()` leaves `codex_bin` as `None`, and the SDK resolves the binary from `openai-codex-cli-bin`, which `openai-codex` pins exactly. Replaces `resolve_codex_binary()` and its three callers. *Revised 20261002:* the first implementation had a `resolve_codex_runtime()` helper with a `codex`-on-PATH fallback; with the SDK a core dependency the bundled binary is always present, so the helper and the fallback were removed.
- **D3 — Interactive login is a separate Protocol, not a new `AuthStrategy` method.** `InteractiveLogin` (`async login(...)`, `async logout()`, `async account_summary()`) is `runtime_checkable`; `OAuthFileStrategy` implements it; the CLI tests `isinstance(strategy, InteractiveLogin)`. Adding methods to `AuthStrategy` would force every API-key strategy to stub them (ISP), and a profile-name or auth-type check is the string dispatch banned by slice 128.
- **D4 — Sandbox and approval via enums.** `credentials["sandbox"]` (today a free string defaulting to `"read-only"`) is validated through `Sandbox(value)`; an invalid value raises `ProviderError` listing the valid ones. The default is defined once as `Sandbox.read_only`. Today's `approval_policy="never"` becomes `ApprovalMode.deny_all` (the SDK maps it to `AskForApproval.never`).
- **D5 — Effort:** `ReasoningEffort(config.effort.value)`. Every squadron `Effort` value (`none, low, medium, high, xhigh`) exists in `ReasoningEffort`, so no mapping table. Passed on `thread.run(effort=…)`. Drops the slice-931 WARNING; sets `applies_effort=True`.
- **D6 — Token usage:** map `TurnResult.usage.last` (`input_tokens`, `cached_input_tokens`, `output_tokens`, `reasoning_output_tokens`) to `TokenUsage(prompt, cached, completion, reasoning)`; `None` when `usage` is `None` (never 0). Stamp via the same metadata keys the OpenAI agent uses so review artifacts need no change.
- **D7 — Timeouts are config keys, not constants,** registered in `config/keys.py` beside `cf.mcp_timeout_s` and read through the config layer (no module-level defaults). Each is a wall-clock cap in seconds:

  | Key | Default | Bounds |
  |---|---|---|
  | `codex.turn_timeout_s` | 1800 | one `thread.run` (agentic reviews are legitimately slow; this bounds a hung runtime, it does not pace work) |
  | `codex.login_timeout_s` | 300 | `handle.wait()` for browser or device-code login; `sq auth login --timeout` overrides it |
  | `codex.account_timeout_s` | 30 | runtime start + `account()` in `sq auth status` and post-login confirmation; runtime start + `logout()` in `sq auth logout`; also bounds `turn.interrupt()` after a turn timeout and `handle.cancel()` after a login timeout, so a hung runtime cannot defeat those timeouts |

  On login timeout or Ctrl-C the handle is cancelled (`handle.cancel()`) so the local callback listener is released.
- **D8 — Turn result is checked, not trusted.** After `thread.run`, `TurnResult.status` must be `TurnStatus.completed`; `failed` raises `ProviderError` carrying `TurnResult.error.message`, `interrupted` raises `ProviderError("Codex turn interrupted")`. A `completed` turn whose `final_response` is `None` or blank raises `ProviderError("Codex turn completed with no response text")`. The current `result.final_response or ""` is removed: an empty review must never reach the parser as a valid, empty Message (the dispatch no-op class of bug, issue #15).

- **D9 — Removed 20261002.** Was an `ExtraRequirement` protocol so `sq models list`, `sq doctor` and `sq auth status` could report a missing extra without naming it. With no extra (D1) there is nothing to report, so the protocol, `loader.missing_extra_hint()`, the models-list marker and the auth-status hint were deleted.

- **D10 — No install step: an optional extra was the wrong packaging (20261002).** The README's primary install is `uv tool install squadron-ai`. The first design told users to `pip install 'squadron-ai[codex]'`, which lands outside a `uv tool` environment, so `sq` never sees the SDK. Correcting it to `uv tool install 'squadron-ai[codex]'` showed a worse problem: uv saves the spec given to `uv tool install`, so the usual upgrade command `uv tool install --upgrade squadron-ai` replaces it and uninstalls the extra, while only `uv tool upgrade squadron-ai` keeps it (both verified, uv 0.11.2). Documentation cannot fix that habit, so D1 makes the SDK a core dependency and no install step exists.

### Failure Modes — Codex Turn

Each row is logged at WARNING or above (or raised as `ProviderError`, which callers log) and has a test asserting the signal.

| Failure | Behavior |
|---|---|
| Runtime subprocess fails to start / `initialize` fails | `ProviderError` wrapping the SDK error; client closed (the SDK closes on init failure) |
| Hang: no response from the runtime | `asyncio.timeout(codex.turn_timeout_s)` (D7) around `thread.run`; on expiry cancel the turn, raise `ProviderError("Codex turn timed out after N s")` |
| Hang or failure in `account()` / runtime start during `sq auth status` or post-login confirmation | `asyncio.timeout(codex.account_timeout_s)` (D7); on timeout or SDK error log WARNING, show validity and source without account details, never fail the command or block the other profiles' rows |
| Hang or failure in `logout()` / runtime start during `sq auth logout` | `asyncio.timeout(codex.account_timeout_s)` (D7); on timeout or SDK error the command exits non-zero with the error, and `sq auth status` remains the way to check whether the login is gone |
| Login `wait()` never completes | `codex.login_timeout_s` (D7); handle cancelled, command exits non-zero with a timeout message |
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
    async def login(self, *, device_code: bool, timeout_s: float, notify: Callable[[str], None]) -> None: ...
    async def logout(self) -> None: ...
    async def account_summary(self) -> str | None: ...
```

`notify` is how the strategy hands the URL / user code to the CLI without importing Rich.

*Implemented as `timeout_s` (ruff ASYNC109 rejects an async parameter named `timeout`); it bounds only `handle.wait()`, so the handle can be cancelled on expiry.*

### Sub-part B surfaces
- **`sq doctor`:** new row `codex provider` in the integrations section, non-required: SDK version and login state from `auth.json` presence (no subprocess in doctor). The existing `codex CLI` row stays — it gates the `codex skills` row and is unrelated to the SDK.
- **`sq setup`:** the `codex provider` row becomes an optional "Sign in to Codex" step whose command is the login hint.
- **README:** replace the Codex install instructions with `sq auth login openai-oauth` → example review; note `--device-code` for SSH.

## Integration Points

### Provides to Other Slices
- `InteractiveLogin` — a pattern future OAuth-backed providers can implement without CLI changes.

### Consumes from Other Slices
- Slice 128 registry and capability declarations; slice 931 effort and usage plumbing.

## Success Criteria

### Functional Requirements
- On a default install with a ChatGPT login, `sq review code <slice> --model codex-agent` completes with `OPENAI_API_KEY` unset and no `codex` on PATH.
- `sq auth login openai-oauth` completes browser login; `--device-code` prints URL and user code and completes without a local browser; either leaves `~/.codex/auth.json` populated.
- `sq auth status` shows email and plan for a logged-in `openai-oauth`; `sq auth logout openai-oauth` removes the login.
- Other profiles' `sq auth login` behavior is byte-for-byte unchanged.
- An alias with `effort = "high"` on `codex-agent` reaches the SDK as `ReasoningEffort.high`; the review artifact records effort and usage.

### Technical Requirements
- No remaining reference to `codex_app_server`, `AppServerConfig`, or `resolve_codex_binary`.
- No profile-name or auth-type string comparison added; capability via `isinstance(…, InteractiveLogin)` and the provider's own report.
- Tests (SDK faked at the `openai_codex` import boundary, as existing codex tests do): one test per row of the Failure Modes — Codex Turn table asserting the raised `ProviderError`/log signal (including failed, interrupted, empty-response, timeout, transport-closed), sandbox validation, effort mapping, usage mapping incl. `None`, login success / `success=False` / timeout-cancels-handle, device-code path, status with and without `account()` failure, logout, logout timeout, `--device-code` on a non-interactive profile, doctor row states, setup step.
- At least one test imports against the real `openai_codex` types so a drifted SDK surface fails loudly.
- `ruff format`, `ruff check`, `pyright` clean.

### Integration Requirements
- `sq doctor` and `sq models list` run cleanly logged in and logged out.

### Verification Walkthrough

Verified 20261001 on macOS, `openai-codex` 0.160.0; steps 1 and 4 re-verified 20261002 after the core-dependency revision. Steps 1, 4 and 6 were run by the implementing agent; steps 2, 3, 5 and 7 need a real ChatGPT account, a browser, or would log the account out, and are Project Manager checks. Each automated step is also covered by tests (named below).

1. `sq doctor -v` on a default install → `✓ codex provider    openai-codex 0.160.0; logged in`. With no `~/.codex/auth.json` the row is WARN `…; not logged in` with fix `Run 'sq auth login openai-oauth' to sign in with ChatGPT, or use the 'openai' profile for API-key access` (`test_codex_provider_not_logged_in_points_to_login`).
2. *(PM)* `sq auth login openai-oauth` → `Sign in at: <url>` printed, browser opens; after sign-in → `✓ openai-oauth: authenticated (<email>, <plan>)`. If the browser cannot open, a WARNING is logged and the printed URL still works.
3. *(PM)* Headless/SSH: `sq auth login openai-oauth --device-code` → `Open <verification_url> and enter code: <code>`; enter it on another device → same success line. `--timeout N` overrides `codex.login_timeout_s` (default 300).
4. `sq auth status` → `openai-oauth │ oauth │ ✓ authenticated │ ~/.codex/auth.json (<email>, <plan>)` (verified live: account and plan shown). Other profiles unchanged.
5. *(PM)* `env -u OPENAI_API_KEY sq review code 128 --model codex-agent -v` → review completes; the artifact lists the model, `effort` (if the alias sets one) and token usage. The artifact path is covered end to end with a faked SDK in `tests/review/test_codex_review_artifact.py`. Restore the slice 128 review afterwards if it is committed.
6. `sq auth login sdk --device-code` → `Error: profile 'sdk' does not support interactive login`, exit 1 (verified).
7. *(PM)* `sq auth logout openai-oauth` → `✓ openai-oauth: logged out`; `sq auth status` → `✗ not authenticated`. Logout and status are bounded by `codex.account_timeout_s` (default 30).

## Implementation Notes

### Development Approach
0. Verify the `OPENAI_API_KEY` fallback against the real runtime and apply the matching outcome (see Special Considerations) before porting anything.
1. Part A: agent/provider port, dependency in `pyproject.toml`, effort + usage — tests against a faked SDK; then one real-types test.
2. Part B: doctor row, setup step, README.
3. Part C: `InteractiveLogin` Protocol, `login.py`, `OAuthFileStrategy` implementation, CLI commands.
4. Smoke test (step 5 above) on a real ChatGPT login; the browser flow cannot be automated and is manual.

### Special Considerations
- **`OPENAI_API_KEY` fallback in `OAuthFileStrategy` is resolved in this slice, not deferred.** The strategy reports a key-only environment as valid, but whether the Codex app-server honors that key from the environment without `login_api_key` is unverified; if it does not, `sq auth status` says "authenticated" and the first turn fails — a silent-fallback path in a file this slice already edits. The first implementation task is a real check: unset `~/.codex/auth.json` (use a throwaway `CODEX_HOME`-style location only if the runtime supports one; otherwise a machine without a login), set `OPENAI_API_KEY`, run one turn. Outcomes: **works** → keep the fallback, label the source `OPENAI_API_KEY` in status, add a test pinning it; **fails** → remove the key fallback from `OAuthFileStrategy` (`is_valid`, `active_source`, `get_credentials`, `setup_hint`) so a key-only environment reports not authenticated and the hint points to `sq auth login openai-oauth` or the `openai` profile. Either outcome is recorded in the task file; neither is left unverified.
- **Security:** squadron never reads or logs `auth.json` contents; only existence and the `account()` email/plan. Auth URLs and device codes are printed to the user's terminal only, not written to logs.
