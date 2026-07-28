---
docType: analysis
project: squadron
topic: tech-debt-audit
model: claude-sonnet-5
dateCreated: 20260727
dateUpdated: 20260727
status: complete
---

# Tech Debt Audit: Squadron

Independent run. Static analysis (`ruff check .`, `pyright` strict) and `pip-audit` all pass clean; the full non-network test suite (2545 passed, 2 skipped) passes. This audit's findings therefore concentrate on architecture, observability, and consistency issues that tooling cannot catch — not lint or type errors.

## Executive Summary

- Two files carry god functions with 6-7 mixed responsibilities each, and both are simultaneously the largest and among the most-churned files in the repo: `execute_pipeline()` (`src/squadron/pipeline/executor.py:600-907`, 307 lines) and `run()` (`src/squadron/cli/commands/run.py:753-1116`, 363 lines). (F001, F002)
- The structured JSON logging subsystem (`src/squadron/logging.py`) is effectively dead code: `setup_logging()` is never called from any entry point. A parallel, mostly-unused Pydantic `Settings` config class exists solely to type that unreachable function. Most application loggers fall back to Python's default `lastResort` handler with no level control and no JSON formatting. (F015, F016)
- The daemon's HTTP API (`src/squadron/server/routes/agents.py`) has no auth guard on any route, including agent shutdown — mitigated only by binding to `127.0.0.1`, with no defense in depth if that assumption ever changes. (F008)
- `pyproject.toml` declares `google-adk` and `mcp` as hard runtime dependencies; both map to 3-line stub packages (`src/squadron/adk/`, `src/squadron/mcp/`) with zero imports anywhere in the codebase. (F006, F007)
- Git-subprocess invocation is reimplemented independently in four files (`review/git_utils.py`, `metrology/audit.py`, `review/review_client.py`, `skills/resolver.py`) with no shared helper, and TOML-loading-with-error-handling is independently reimplemented in five files despite a canonical loader existing in `config/manager.py`. (F003, F004)
- `pipeline/prompt_renderer.py` silently swallows model-resolution failures at three near-identical call sites with a bare `except Exception`, falling back to an unvalidated raw string with no log line. (F005)
- `pipeline/executor.py:769` compares a step type against the raw string `"each"` while the two adjacent branches correctly compare against `StepTypeName` enum members — the enum member (`StepTypeName.EACH`) already exists and is simply not used. (F014)
- Test suite is broadly healthy, but `tests/cli/commands/test_run_pipeline_sdk.py` averages ~6.6 `unittest.mock.patch()` calls per test, correlating with a `RuntimeWarning: coroutine ... was never awaited` observed during the actual test run. (F009)
- No hardcoded secrets, no CVEs (`pip-audit`), no circular imports, no `eval`/`pickle`/`shell=True` usage, and pyright `--strict` passes with zero errors — the codebase's static-analysis and dependency hygiene is genuinely good.

## Architectural Mental Model

Squadron is a Python 3.12+ CLI (`sq`) that runs LLM-backed "reviews" and multi-step "pipelines" against a codebase, primarily through the Claude Agent SDK plus OpenAI/OpenRouter/Codex as alternate providers. The core layering is clean and matches the README's description: `core/` and `models/` hold provider-agnostic domain types; `providers/` wraps each backend (`sdk`, `openai`, `codex`, a stub `anthropic`) behind a common `Agent`/`AuthStrategy` protocol; `pipeline/` is the largest and most actively developed module (51 files) — it loads YAML pipeline definitions, resolves placeholders, and executes a step graph (`design`/`tasks`/`review`/`dispatch`/`each`/`fan_out`/`loop`) via `executor.py`; `review/` builds review prompts and parses structured verdicts; `metrology/` (new, per recent commits) captures and reduces audit/judge calibration data; `cli/commands/` is the Typer-based front door; `server/` is an optional local daemon (FastAPI, `127.0.0.1`-only) for long-lived agent processes, largely separate from the CLI/pipeline path. Config is meant to flow through one canonical TOML-backed manager (`config/manager.py`), though in practice several subsystems (model aliases, provider profiles, model pools, skill packs) parse their own TOML files independently rather than routing through it.

Git history confirms the mental model: `src/orchestration` was renamed to `src/squadron` (`71c5970`), and the last several months of commits concentrate almost entirely in `pipeline/`, `cli/commands/review.py` and `run.py`, and the new `metrology/` module — exactly where the god functions and highest churn live. There is no contradiction with the README; the one gap between stated design and reality is observability (structured logging is documented and implemented but never wired up).

## Findings Table

| ID | Category | File:Line | Severity | Effort | Description | Recommendation |
|----|----------|-----------|----------|--------|--------------|-----------------|
| F001 | architectural-decay | src/squadron/pipeline/executor.py:600-907 | High | L | `execute_pipeline()` is 307 lines handling parameter merging, step-type dispatch, retry-loop orchestration, checkpoint/resume, lazy SDK session lifecycle, and state persistence in one function. | Extract step dispatch (`each`/`fan_out`/`loop`/action) into a router function, and pull checkpoint/resume handling into a separate helper that `execute_pipeline` calls. |
| F002 | architectural-decay | src/squadron/cli/commands/run.py:753-1116 | High | L | `run()` is 363 lines: 22+ mutual-exclusivity CLI validations, logging setup, seven distinct execution modes (`--list`/`--status`/`--validate`/`--dry-run`/`--explain`/`--resume`/`--prompt-only`), and result display all live in one function. | Extract each `--mode` branch into a `_handle_*` function (the file already has this pattern for `_handle_explain`, `_handle_prompt_only_init` etc. — the remaining inline branches should follow it). |
| F003 | architectural-decay | src/squadron/review/git_utils.py:21,45,87,108,148; src/squadron/metrology/audit.py:248-256; src/squadron/review/review_client.py:326,361; src/squadron/skills/resolver.py:59 | Medium | M | Nine call sites across four files independently call `subprocess.run(["git", ...], capture_output=True, text=True, cwd=cwd, check=False)`; only `metrology/audit.py` factors this into a helper (`_run_git`), and even that helper is private to its own module. | Add one shared `run_git(args, cwd) -> CompletedProcess` in a common location (e.g. `core/git.py`) and have all four modules call it. |
| F004 | consistency-rot | src/squadron/models/aliases.py:110-111; src/squadron/providers/profiles.py:100; src/squadron/pipeline/intelligence/pools/loader.py:60,83,111,148; src/squadron/skills/manifest.py:31,55 | Medium | M | Five modules each independently `tomllib.load(s)` a config file and hand-roll `except tomllib.TOMLDecodeError` handling, duplicating logic that `config/manager.py:51` already implements once for the canonical config path. | Extract a shared `load_toml_file(path) -> dict` helper (read + decode-error handling) in `config/`, used by both the canonical config loader and these four domain-specific loaders. |
| F005 | error-handling-observability | src/squadron/pipeline/prompt_renderer.py:156-160,209-212,308-311 | Medium | S | Three near-identical `try: model_id, profile = resolver.resolve(alias) / except Exception: model_id = alias; profile = None` blocks silently swallow any resolution failure (typo'd alias, malformed pool config, resolver bug) with no logging, so a broken alias silently degrades to using the raw string as a model ID. | Catch the specific exception `resolver.resolve()` raises for "unknown alias" and log at WARNING for anything else; consider factoring the three sites into one `_resolve_or_fallback(alias, resolver)` helper. |
| F006 | dependency-config-debt | pyproject.toml:28; src/squadron/adk/__init__.py:1-3 | Medium | S | `google-adk>=0.1.0` is a hard runtime dependency. `src/squadron/adk/__init__.py` is a 3-line stub docstring ("Populated in slice 11.") with zero imports of `google.adk` anywhere in `src/` or `tests/`. | Remove `google-adk` from `pyproject.toml` until the ADK bridge is actually implemented, or move it to `optional-dependencies` if it's genuinely planned near-term. |
| F007 | dependency-config-debt | pyproject.toml:29; src/squadron/mcp/__init__.py:1-3 | Medium | S | `mcp>=1.0.0` is a hard runtime dependency. `src/squadron/mcp/__init__.py` is a 3-line stub ("Populated in slice 12.") with zero imports anywhere in the codebase. | Same as F006 — remove or make optional until the MCP server exists. |
| F008 | security-hygiene | src/squadron/server/routes/agents.py:44-213 (all 8 route handlers) | Medium | M | No FastAPI dependency/auth guard on any daemon route. `DELETE /agents/` (shutdown all) and `DELETE /agents/{name}` are reachable by any local process with no credential check. Mitigated only by `host="127.0.0.1"` in `server/daemon.py:57`. | Add a minimal shared-secret or Unix-socket-permission-based auth dependency on the router, even if trivial — don't rely solely on the bind address as the only control. |
| F009 | test-debt | tests/cli/commands/test_run_pipeline_sdk.py (93 `patch()` calls across 14 tests) | Low | M | Heavy mocking (~6.6 patches/test) of `_run_pipeline`/`_run_pipeline_sdk` correlates with an observed `RuntimeWarning: coroutine '_run_pipeline_sdk' was never awaited` and `coroutine '_run_pipeline' was never awaited` during the actual pytest run (see test session output for `tests/cli/commands/test_run.py::TestPromptOnly::test_prompt_only_next`, `tests/cli/commands/test_run_pipeline.py::TestResumeDispatch::test_explicit_resume_prompt_only_calls_run_pipeline`, `tests/cli/commands/test_run_pipeline_sdk.py::TestClassificationGate::*`). | Replace `MagicMock` with `AsyncMock` (or `new_callable=AsyncMock`) wherever the patched target is awaited, and confirm the warning disappears — a coroutine created but never awaited means that code path isn't actually being exercised the way the test believes. |
| F010 | other | CLAUDE.md.bak:1-335 | Low | S | A 335-line backup file is tracked in git at the repo root (`git log -1` shows it committed 2026-02-26, still present). | Delete it or add `*.bak` to `.gitignore`; git history already preserves prior versions of `CLAUDE.md`. |
| F011 | test-debt | tests/pipeline/test_compact_compose_integration.py:44,181 | Low | M | Two tests are skipped with `reason="fixture pipeline step count mismatch; tracked for fix in slice 248"`. No `248-*` slice/task document exists under `project-documents/user/` — the tracking reference appears stale or the slice was renumbered. | Either fix the fixture mismatch, or update the skip reason to point at the actual tracking artifact if one exists under a different number. |
| F012 | type-contract-debt | src/squadron/pipeline/executor.py:295-308,827,1099,1287,1399,1489,1493 | Low | M | Eight `# type: ignore` directives sit inside the same god function flagged in F001, mostly around dict/placeholder unpacking. Individually each is a reasonable boundary escape (pyright strict passes overall), but their concentration inside one 307-line function makes it harder to tell which are load-bearing. | Address as part of the F001 extraction — narrowing the dict-shaped intermediate values with a `TypedDict` or small dataclass in the extracted helpers would let several of these `type: ignore`s be removed rather than carried forward. |
| F013 | consistency-rot | src/squadron/cli/commands/doctor_checks.py:17; setup_steps.py:28; setup.py:21; core/agent_registry.py:23; review/parsers.py:20; server/daemon.py:23; server/engine.py:19; skills/installer.py:17 (vs. `_logger` in 29 other files, e.g. pipeline/executor.py:41) | Low | S | Module-level logger variables are named `logger` in 8 files and `_logger` in 29 files — no functional effect, but it's exactly the kind of naming drift that erodes grep-ability and consistency over time. | Standardize on one name (`_logger` is the majority convention) via a search-and-replace pass; no behavior change. |
| F014 | architectural-decay | src/squadron/pipeline/executor.py:769 (vs. 787, 805); src/squadron/pipeline/steps/__init__.py:24-32 | Medium | S | `if step.step_type == "each":` uses a raw string literal, while the two adjacent `elif` branches correctly compare against `StepTypeName.FAN_OUT` and `StepTypeName.LOOP`. `StepTypeName.EACH = "each"` already exists in the same enum. This is the exact "user-accessible label as logical structure" / "scattered comparison value" pattern the project's own CLAUDE.md prohibits. | Change line 769 to `step.step_type == StepTypeName.EACH`. One-line fix. |
| F015 | architectural-decay | src/squadron/config/__init__.py:8-37; src/squadron/logging.py:11,29 | High | M | `Settings` (Pydantic `BaseSettings`, `ORCH_`-prefixed env vars — a leftover from the pre-rename `orchestration` package name) duplicates fields already owned by the canonical `config/manager.py` TOML system (`default_provider`, `default_model`, `host`, `port`, `anthropic_api_key`) but is consumed by exactly one thing: a `TYPE_CHECKING`-only import in `logging.py:11` for a function (`setup_logging`, line 29) that is never called anywhere in `src/squadron` (see F016). | Delete `Settings` and the `TYPE_CHECKING` import once `setup_logging()`'s call site is fixed (F016) or, if logging setup is abandoned in favor of the ad-hoc per-command approach, delete both together. |
| F016 | error-handling-observability | src/squadron/logging.py:29-49; src/squadron/cli/commands/run.py:860-867 | High | M | `setup_logging()` — the only function that installs a root log handler and applies the JSON formatter / configurable level — is never invoked from any CLI or server entry point (verified via repo-wide grep for `setup_logging(` and `basicConfig`/`addHandler`). The only handler ever installed is an ad-hoc one in `run.py:860-867`, scoped solely to the `"squadron.pipeline"` logger and only when `-v`/`--verbose` is passed. Every other logger (`metrology.*`, `providers.*`, `server.*`, `core.*`, most of `cli.*`) relies on Python's `logging.lastResort` fallback — WARNING+ only, unformatted, no level control — for every `.warning()`/`.exception()` call verified elsewhere in this audit as "properly logged." | Call `setup_logging()` once at the top of `cli/app.py`'s Typer callback (and the server daemon's startup) so the JSON formatter and level actually apply everywhere, then remove the narrower ad-hoc handler in `run.py` (or keep it only for the `-v` level bump, layered on top of a handler that's already installed). |
| F017 | consistency-rot | src/squadron/providers/codex/auth.py:45,56,62,74 (vs. src/squadron/providers/auth.py:66) | Low | S | `codex/auth.py`'s `OAuthFileStrategy` hardcodes the literal `"OPENAI_API_KEY"` four times as its fallback env var. `providers/auth.py:66` already defines this as a parameterized default (`fallback_env_var: str = "OPENAI_API_KEY"`) on the shared `ApiKeyStrategy`. The Codex strategy is legitimately a different `AuthStrategy` implementation (OAuth-file-first, so reuse isn't a drop-in fix), but the literal itself is duplicated rather than imported from one place. | Define `DEFAULT_OPENAI_API_KEY_ENV = "OPENAI_API_KEY"` once in `providers/auth.py` (or a shared constants module) and import it into `codex/auth.py` instead of re-typing the string four times. |

## Top 5 — If You Fix Nothing Else, Fix These

**1. Wire up `setup_logging()` (F016) — currently a no-op subsystem.**
This is the single highest-leverage fix: every other "properly logged" finding in this audit (the OK-rated exception handlers in `state.py`, `loader.py`, `agent_registry.py`, etc.) is only as good as whatever handler is actually installed, and right now that's Python's bare `lastResort` for most of the app.
```python
# src/squadron/cli/app.py — in the Typer app's top-level callback
from squadron.config import Settings
from squadron.logging import setup_logging

@app.callback()
def main(...):
    setup_logging(Settings())
    ...
```
Then delete the narrower ad-hoc handler in `run.py:860-867` or reduce it to just a level bump on top of the now-installed root handler.

**2. Fix the magic-string step dispatch (F014) — one line, directly matches the project's own written rule.**
```python
# src/squadron/pipeline/executor.py:769
- if step.step_type == "each":
+ if step.step_type == StepTypeName.EACH:
```

**3. Extract `execute_pipeline()` (F001) into a dispatch table.**
```python
_STEP_HANDLERS: dict[StepTypeName, Callable[..., Awaitable[StepResult]]] = {
    StepTypeName.EACH: _execute_each_step,
    StepTypeName.FAN_OUT: _execute_fan_out_step,
    StepTypeName.LOOP: _execute_loop_body,
}
# execute_pipeline() then does:
handler = _STEP_HANDLERS.get(step.step_type, _execute_step_once)
step_result = await handler(step=step, resolved_config=resolved_config, ...)
```
This alone removes the string/enum inconsistency (F014) as a side effect, since every branch now keys off the same enum.

**4. Delete the unused `google-adk` and `mcp` dependencies (F006, F007).**
Two one-line removals from `pyproject.toml`'s `dependencies` list; re-add under `optional-dependencies` if there's a near-term plan to populate `src/squadron/adk/` and `src/squadron/mcp/`.

**5. Add an auth guard to the daemon API (F008).**
```python
# src/squadron/server/routes/agents.py
async def _require_token(request: Request) -> None:
    expected = request.app.state.daemon_token
    if request.headers.get("X-Squadron-Token") != expected:
        raise HTTPException(status_code=403)

agents_router = APIRouter(prefix="/agents", dependencies=[Depends(_require_token)])
```
A token generated at daemon startup and written to a user-only-readable file is enough — the goal is defense in depth against the `127.0.0.1`-only assumption, not a full auth system.

## Quick Wins

- [ ] F014 — `pipeline/executor.py:769`: replace `"each"` with `StepTypeName.EACH`
- [ ] F006 — remove unused `google-adk` dependency from `pyproject.toml:28`
- [ ] F007 — remove unused `mcp` dependency from `pyproject.toml:29`
- [ ] F010 — delete `CLAUDE.md.bak` and add `*.bak` to `.gitignore`
- [ ] F017 — define `DEFAULT_OPENAI_API_KEY_ENV` once and import it into `codex/auth.py` instead of re-typing the literal 4x
- [ ] F013 — rename `logger` → `_logger` in the 8 outlier files for consistency

## Things That Look Bad But Are Actually Fine

- **`src/squadron/client/http.py:74`** (`except Exception: detail = resp.text or f"HTTP {status}"`) — looks like a silent swallow at first glance, but the request has already failed (status ≥ 400) and `raise httpx.HTTPStatusError(...)` fires unconditionally two lines later; this `except` only decides how to *word* the error message when the body isn't JSON. No error is actually being hidden.
- **`src/squadron/cli/commands/doctor_checks.py:58`** (`except Exception: source_path = "(unknown path)"`) — this is inside `sq doctor`'s version-display helper, used purely for "paste this into a bug report" ergonomics. A failure here has zero effect on program correctness.
- **`src/squadron/pipeline/sdk_session.py:108`, `providers/sdk/agent.py:247`, `providers/codex/agent.py:82-83`, `pipeline/actions/cf_op.py:107-108`** — all four are `except Exception: pass` with an explicit comment explaining the teardown/best-effort rationale, exactly matching the project's own exception-handling rule (option (b): documented reason for swallowing).
- **`src/squadron/config/keys.py` (254 lines, ~25 `ConfigKey` entries)** — at a glance this reads like a wall of magic numbers, but it is in fact the single canonical registry the project's own CLAUDE.md asks for: every default is defined exactly once, with a description, and `get_default()`/`get_typed_config()` are the only paths that read them. This is the *positive* counter-example to F004, not more of the same problem.
- **`src/squadron/providers/codex/auth.py`'s `OAuthFileStrategy` vs. `providers/auth.py`'s `ApiKeyStrategy`** — two different classes implementing the same `AuthStrategy` Protocol looked like duplication on first pass, but it's the Strategy pattern working correctly (DIP/ISP): OAuth-file-first with API-key fallback is a genuinely different resolution order than pure API-key, and both are dispatched polymorphically via `resolve_auth_strategy_for_profile()`. Only the literal env-var-name string is duplicated (F017), not the logic.
- **Subprocess usage throughout (`commit.py`, `audit.py`, `git_utils.py`, `review_client.py`, `skills/resolver.py`)** — all calls use list-argument `subprocess.run([...])`, never `shell=True`, so there's no shell-injection surface despite the volume of git shellouts (F003 is about duplication, not safety).
- **`time.sleep(cooldown_s)` in `cli/commands/metrology.py:884`** — reads like blocking-I/O in an async context, but `audit_variance()` is a synchronous Typer command that calls `asyncio.run()` per iteration; there is no live event loop for the sleep to block.
- **README's `sq models` alias table** — spot-checked against `src/squadron/data/models.toml` (the shipped defaults); every alias/model-ID pair in the README matches the packaged TOML exactly. No documentation drift found here.

## Open Questions for the Maintainer

- **F015/F016**: Was `setup_logging()` intentionally left unwired (e.g., because the CLI is meant to rely on Rich's `rprint` for user-facing output and structured logging was scoped only for the never-built daemon/server path), or is this a genuine gap that should be closed? If intentional, `Settings` and `logging.py`'s JSON formatter should probably be deleted rather than fixed.
- **F011**: Does "slice 248" refer to a real, still-planned unit of work under a different numbering, or was it abandoned? The skip reason can't be resolved from the repo alone.
- **F008**: Is the daemon (`sq serve`) ever expected to run somewhere other than a trusted local machine (e.g., inside a container reachable from other containers)? If it's strictly single-user-localhost by design, the current no-auth posture may be an acceptable, deliberate simplification rather than debt — but it's worth having that be a documented decision rather than an implicit one.
- **F006/F007**: Are `google-adk` and `mcp` integrations (slices 11/12 per the stub docstrings) still on the roadmap? If they're near-term, "optional dependency" is a better home than removal.

<!-- squadron:findings:begin v1 -->
```yaml
findings:
  - id: F001
    category: architectural-decay
    location: src/squadron/pipeline/executor.py:600-907
    severity: High
    effort: L
    summary: execute_pipeline() is a 307-line function handling parameter merging, step-type dispatch, retry-loop orchestration, checkpoint/resume, lazy SDK session lifecycle, and state persistence together
  - id: F002
    category: architectural-decay
    location: src/squadron/cli/commands/run.py:753-1116
    severity: High
    effort: L
    summary: run() is a 363-line function combining 22+ mutual-exclusivity CLI validations, logging setup, seven execution modes, and result display
  - id: F003
    category: architectural-decay
    location: src/squadron/review/git_utils.py:21
    severity: Medium
    effort: M
    summary: Nine call sites across four files (git_utils.py, metrology/audit.py, review_client.py, skills/resolver.py) independently invoke subprocess.run for git with no shared helper
  - id: F004
    category: consistency-rot
    location: src/squadron/models/aliases.py:110-111
    severity: Medium
    effort: M
    summary: Five modules independently parse TOML with hand-rolled TOMLDecodeError handling instead of routing through the canonical config/manager.py loader
  - id: F005
    category: error-handling-observability
    location: src/squadron/pipeline/prompt_renderer.py:156-160
    severity: Medium
    effort: S
    summary: Three near-identical bare except-Exception blocks around resolver.resolve() silently fall back to the raw alias string with no logging on model-resolution failure
  - id: F006
    category: dependency-config-debt
    location: pyproject.toml:28
    severity: Medium
    effort: S
    summary: google-adk is declared as a hard runtime dependency but its corresponding module is an unpopulated 3-line stub with zero imports anywhere in the codebase
  - id: F007
    category: dependency-config-debt
    location: pyproject.toml:29
    severity: Medium
    effort: S
    summary: mcp is declared as a hard runtime dependency but its corresponding module is an unpopulated 3-line stub with zero imports anywhere in the codebase
  - id: F008
    category: security-hygiene
    location: src/squadron/server/routes/agents.py:44-213
    severity: Medium
    effort: M
    summary: No auth guard exists on any daemon route including agent shutdown, relying solely on 127.0.0.1 binding for protection
  - id: F009
    category: test-debt
    location: tests/cli/commands/test_run_pipeline_sdk.py:1-950
    severity: Low
    effort: M
    summary: Heavy mocking averaging 6.6 patch() calls per test correlates with an observed RuntimeWarning that a pipeline coroutine was never awaited during the real test run
  - id: F010
    category: other
    location: CLAUDE.md.bak:1-335
    severity: Low
    effort: S
    summary: A 335-line backup file is tracked in git at the repository root instead of being gitignored
  - id: F011
    category: test-debt
    location: tests/pipeline/test_compact_compose_integration.py:44
    severity: Low
    effort: M
    summary: Two tests are skipped citing a fix tracked in slice 248, but no such slice artifact exists in the project documents
  - id: F012
    category: type-contract-debt
    location: src/squadron/pipeline/executor.py:295-308
    severity: Low
    effort: M
    summary: Eight type-ignore directives concentrate inside the same god function as F001, making it unclear which are load-bearing boundary escapes
  - id: F013
    category: consistency-rot
    location: src/squadron/cli/commands/doctor_checks.py:17
    severity: Low
    effort: S
    summary: Module-level logger variables are named logger in 8 files and _logger in 29 files with no functional difference
  - id: F014
    category: architectural-decay
    location: src/squadron/pipeline/executor.py:769
    severity: Medium
    effort: S
    summary: Step-type dispatch compares against the raw string literal "each" while adjacent branches correctly use StepTypeName enum members, even though StepTypeName.EACH already exists
  - id: F015
    category: architectural-decay
    location: src/squadron/config/__init__.py:8-37
    severity: High
    effort: M
    summary: A parallel Pydantic Settings config class with a stale ORCH_ env prefix duplicates fields already owned by the canonical TOML config system and is only reachable via a type-checking-only import
  - id: F016
    category: error-handling-observability
    location: src/squadron/logging.py:29-49
    severity: High
    effort: M
    summary: setup_logging() is never invoked from any CLI or server entry point, so most application loggers rely on Python's unformatted lastResort fallback instead of the intended JSON formatter and configurable level
  - id: F017
    category: consistency-rot
    location: src/squadron/providers/codex/auth.py:45
    severity: Low
    effort: S
    summary: The Codex auth strategy hardcodes the OPENAI_API_KEY literal four times instead of reusing the parameterized default already defined on the shared ApiKeyStrategy
```
<!-- squadron:findings:end -->
