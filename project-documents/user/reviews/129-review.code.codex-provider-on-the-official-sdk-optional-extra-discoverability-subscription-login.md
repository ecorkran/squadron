---
docType: review
layer: project
reviewType: code
slice: codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/129-slice.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md
aiModel: deepseek/deepseek-v4.1-flash
status: complete
dateCreated: 20261002
dateUpdated: 20261002
reviewedSha: aa8fb7a7b275b7636d527eec71c8fe84686a7ac7
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 35
diffTruncated: false
turns: 20
promptTokens: 1603328
cachedTokens: 1235712
completionTokens: 129028
reasoningTokens: 124618
durationSeconds: 863.5
squadronVersion: 0.17.0
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Setup renders the Codex prose setup hint as a runnable `$` command"
    location: "src/squadron/cli/commands/setup_steps.py:266"
  - id: F002
    severity: concern
    category: test-quality
    summary: "The new setup-step test asserts on a `fix_hint` production never produces"
    location: "tests/cli/test_setup_steps.py:224"
  - id: F003
    severity: concern
    category: error-handling
    summary: "`login()` lets a runtime-start failure escape as a traceback"
    location: "src/squadron/providers/codex/login.py#login"
  - id: F004
    severity: concern
    category: error-handling
    summary: "`_interrupt` failure modes are narrower than the SDK's own documented behavior"
    location: "src/squadron/providers/codex/agent.py#_interrupt"
  - id: F005
    severity: note
    category: error-handling
    summary: "`_report_validity` (non-interactive path) does not escape, unlike its interactive sibling"
    location: "src/squadron/cli/commands/auth.py:102-108"
  - id: F006
    severity: note
    category: error-handling
    summary: "`check_codex_provider` reads distribution metadata without the guard its sibling uses"
    location: "src/squadron/cli/commands/doctor_checks.py#check_codex_provider"
  - id: F007
    severity: pass
    category: tests
    summary: "SDK boundary is faked rather than mocked into internals"
    location: "tests/providers/codex/fake_sdk.py"
  - id: F008
    severity: pass
    category: design
    summary: "Config keys are centralized and tested rather than sprinkled"
    location: "src/squadron/config/keys.py:365-391"
  - id: F009
    severity: pass
    category: tests
    summary: "Failure-mode tests assert observable signals, not just return values"
    location: "tests/providers/codex/test_login.py"
---

# Review: code — slice 129

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [CONCERN] Setup renders the Codex prose setup hint as a runnable `$` command

`build_steps` maps `command=result.fix_hint` unconditionally, and the new `check_codex_provider` populates `fix_hint` from `OAuthFileStrategy.setup_hint`, which is prose:

```
                                                                                                          
```

`sq setup` will therefore print, in a block whose other commands are copy-pasteable shell lines (`_render_step_block`, `src/squadron/cli/commands/setup.py:74`):

```
                                                                                                          
```

Compare every other entry in `_INSTALLERS`/fix hints (`CONTEXT_FORGE_INSTALL_CMD`, `"sq install-commands --ide codex"`, `GIT_HOOKS_PATH`), which are actual commands. The doctor table tolerates prose (`fix: …`), but the setup step's `command` field does not — it is presented as the thing to type. The new production `setup_steps` test does not catch this because it fabricates a `fix_hint` the real check never returns (see next finding).

### [CONCERN] The new setup-step test asserts on a `fix_hint` production never produces

`test_codex_provider_warn_yields_optional_sign_in_step` constructs `CheckResult(..., fix_hint="sq auth login openai-oauth", ...)` and then asserts `step.command == "sq auth login openai-oauth"`. `check_codex_provider` never emits that string — it emits `OAuthFileStrategy.setup_hint` (the full sentence above). The test passes while the shipped output is wrong, which is precisely the false-confidence pattern CLAUDE.md calls out: "the test fixture must include the actual format that parser will consume in production." Driving the step from a real `check_codex_provider()` result (or the real `setup_hint`) would have surfaced the previous finding.

### [CONCERN] `login()` lets a runtime-start failure escape as a traceback

`_codex_session()` yields `await codex.__aenter__()`; a start failure raises there and propagates out of the `async with` in `login()`. Only `logout()` and `account_summary()` catch `(CodexError, OSError, RuntimeError)`. `CodexAgent._start_thread` explicitly treats `OSError` ("the binary cannot run") and `RuntimeError` as expected start failures, so the same two are expected here — yet `sq auth login` reaches only `except ProviderError` / `except KeyboardInterrupt` in `src/squadron/cli/commands/auth.py:58-61` and will surface a raw traceback for a missing/unrunnable bundled runtime. Failure-Mode Enumeration calls for that path to be an explicit `ProviderError` with a test.

### [CONCERN] `_interrupt` failure modes are narrower than the SDK's own documented behavior

`_interrupt` swallows only `(TimeoutError, CodexError)`. The code itself documents two lines later that "the SDK reports a failed turn (and a missing completion event) as a bare `RuntimeError`" (`_run_turn`). If `turn.interrupt()` raises that same `RuntimeError`, it escapes the `except TimeoutError` arm of `_run_turn`, replacing the intended `ProviderError("Codex turn timed out after N s")` with an error that `_run_turn_translating_errors` does not map (it catches only `TransportClosedError`, `ServerBusyError`, `CodexRpcError`), so it surfaces via `handle_message`'s generic `except Exception` as `"Codex agent error: …"`. `TransportClosedError` from a dead runtime after a timeout is equally plausible and equally uncaught. The consequence is a misleading message and a lost WARNING for a failure mode the design enumerated; the timeout path's test only exercises a *successful* interrupt.

### [NOTE] `_report_validity` (non-interactive path) does not escape, unlike its interactive sibling

The slice's stated theme is that provider text can carry brackets that are not Rich tags, and `auth_login`, `_fail`, `_print_notice`, and `auth_status` all apply `rich.markup.escape`. `_report_validity` interpolates `strategy.active_source` and `strategy.setup_hint` raw into `rprint` (lines 105 and 108), so a user-defined profile whose hint contains `[extra]` renders inconsistently with the login path it sits beside. `_profile_or_exit` duplicates `_fail`'s `[red]Error:[/red] {escape(...)}` form rather than calling it (lines 88 and 93) — the same message should have one definition.

### [NOTE] `check_codex_provider` reads distribution metadata without the guard its sibling uses

`importlib.metadata.version("openai-codex")` is unguarded, unlike `check_squadron_install`, which wraps the same call in `except PackageNotFoundError`. `openai-codex` is a pinned dependency, so this normally resolves, but in a dev/editable install it raises; `run_all_checks._run` then degrades it to a `WARN` row whose detail is `"check failed: PackageNotFoundError"` — a non-actionable message for exactly the "packaging is broken" case this row exists to report. It also makes `test_run_all_checks_includes_codex_provider_row` (which asserts `"check failed" not in row.detail`) an ambient-environment test rather than a hermetic one.

### [PASS] SDK boundary is faked rather than mocked into internals

`installed_fake_sdk()` substitutes `openai_codex` in `sys.modules` and exposes the handles a test configures (`FakeSdk.turn`, `.thread`, `.client`), so `CodexAgent` is exercised through its real code path with no monkeypatched internals. `tests/providers/codex/test_sdk_surface.py` pins the same names against the real package, which is the right drift alarm for the loose `>=0.159.3,<1` pin.

### [PASS] Config keys are centralized and tested rather than sprinkled

`codex.turn_timeout_s`, `codex.login_timeout_s`, and `codex.account_timeout_s` are declared once with defaults and read via `get_typed_config` at each use, with `LOGIN_TIMEOUT_KEY` re-exported so the CLI's `--timeout` help text cannot drift from the provider. `tests/config/test_keys.py` asserts registration, type, default, and readability — satisfying CLAUDE.md's "no magic defaults" and "one value, one source."

### [PASS] Failure-mode tests assert observable signals, not just return values

`test_url_and_code_never_logged` asserts the auth URL, device URL, and user code never reach the log at DEBUG; `test_sdk_error_returns_none_and_warns` and `test_timeout_returns_none_and_warns` assert the WARNING that makes the swallowed account-lookup failure observable; `test_teardown_error_logged_not_raised` asserts the teardown log and `AgentState.terminated`. Each swallowed exception in `login.py` and `agent.py` is matched by a test that the failure produces a signal — the standard the review rules ask for.

## Response (20261002)

All six findings were checked against the code and are valid. All six are fixed in `6a809ef2`.

- **F001: accepted.** `providers/codex/auth.py` defines `LOGIN_COMMAND` once. `setup_hint` builds its sentence from it, and `check_codex_provider` uses it as `fix_hint`, so `sq setup` shows a runnable `$ sq auth login openai-oauth`.
- **F002: accepted.** `test_codex_provider_warn_yields_optional_sign_in_step` now builds its step from a real `check_codex_provider()` result in the isolated HOME, so it asserts what production emits. The doctor test now asserts the exact command.
- **F003: accepted.** `login()` maps `CodexError`/`OSError`/`RuntimeError` to `ProviderError("Codex login failed: …")`, the same set `logout()` uses. New test: `test_runtime_start_failure_raises_provider_error`.
- **F004: accepted in part.** `TransportClosedError` subclasses `CodexError` and was already caught. The real gap was a bare `RuntimeError`, which `_interrupt` now also swallows with its WARNING. New test: `test_timeout_still_reported_when_interrupt_raises_runtime_error`.
- **F005: accepted.** `_report_validity` escapes the profile name, source and hint, and `_profile_or_exit` calls `_fail`.
- **F006: accepted.** A missing `openai-codex` distribution gives a WARN row saying to reinstall squadron-ai, not `check failed: PackageNotFoundError`. New test: `test_codex_provider_missing_distribution_warns_actionably`.

The empty fenced blocks under F001 were a squadron parser bug: finding bodies were sliced from fence-masked text. It is fixed in `1960da73`.

### Run Digest

- Response length: 7542 chars
- Response is newline-free: no
- Tool calls made: 35
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 488650
- Effort: backend default
- Turns: 20
- Tokens — prompt / cached / completion / reasoning: 1603328 / 1235712 / 129028 / 124618
- Duration: 863.5 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
