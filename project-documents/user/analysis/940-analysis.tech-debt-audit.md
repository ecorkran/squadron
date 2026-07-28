---
docType: analysis
project: squadron
topic: tech-debt-audit
dateCreated: 20260727
dateUpdated: 20260727
status: complete
model: claude-sonnet-4-6
---

# Tech Debt Audit — Squadron

Independent run. This audit does not read or reference any prior audit file; findings are not tagged RESOLVED/NEW.

## Executive Summary

- Baseline hygiene is genuinely strong: `ruff check` is clean, `pyright --strict` reports 0 errors, 2545/2547 tests pass (2 skipped, network-gated), and `pip-audit` finds no known CVEs. This is not a codebase in crisis.
- Two live bugs verified by direct reproduction: `sq config set` crashes on any float-typed config key (`_coerce_value` has no float branch — F043), and `DaemonClient.request_shutdown()` always 404s because no `/shutdown` route exists server-side (F020).
- One command-injection-shaped bug: the commit-message renderer skips `shlex.quote()` that its sibling renderers in the same file use, so a commit message prefix containing a single quote breaks out of the emitted shell command (F078).
- `run.py`'s pre-`load_pipeline` `.lower()` call breaks path-based pipeline invocation with any uppercase path segment on case-sensitive filesystems (Linux/CI) — verified by reading `load_pipeline`'s own is-a-file-vs-name branch order (F013).
- The five highest-churn files in the last 6 months (`review.py` 40 commits, `executor.py` 26, `run.py` 25, `review_client.py` 20, `prompt_renderer.py` 20) are also five of the six largest/most duplicated-logic files found — churn and size compound where debt actually lives.
- Two direct violations of this project's own written rules were found in the code it governs: a raw string-literal compared against an `ExecutionStatus` enum (`fan_in/reducers.py:59`, forbidden by CLAUDE.md's "never use labels as logical structure") and a bare `except Exception: pass` with zero comment or logging in `codex/agent.py:80-83` (forbidden by the exception-handling rule in CLAUDE.md).
- `.env.example` only documents the unused `ORCH_*` settings scheme; the credentials actually read at runtime (`OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `GEMINI_API_KEY`) are undocumented there.
- `google-adk` and `mcp` are direct dependencies with zero imports anywhere in `src/` — dead weight for stub packages awaiting future slices.
- `Settings(BaseSettings)` and its entire `ORCH_*` env-var surface (`config/__init__.py`) is never instantiated in production code; `setup_logging()` is called only from tests. An entire configuration subsystem is currently inert.
- Duplication clusters around three shapes: git-diff-with-excludes subprocess logic (3 near-identical copies across review_client.py/rules.py), daemon-client try/except/finally boilerplate (6 copies across 5 CLI commands), and step-execution parameter lists (5 near-identical ~16-parameter function signatures in executor.py).

## Architectural Mental Model

Squadron is a CLI (`sq`/`squadron`, Typer-based) that wraps LLM-driven code/design review and multi-step "pipelines" on top of the Claude Agent SDK (plus OpenAI, OpenRouter, and an experimental Codex provider). The core execution model is: a YAML pipeline definition (`pipeline/loader.py`, `pipeline/schema.py`) is resolved into a sequence of typed steps (`pipeline/steps/`), each dispatched to an "action" (`pipeline/actions/`) by a central `executor.py`, which threads a persistent SDK session, resumable run state (`pipeline/state.py`), and a parallel classification system that decides which steps can share a session vs. need pooled/fresh agents (`pipeline/classification.py`, `pipeline/intelligence/`). Reviews (`review/`) render prompt templates against project artifacts and parse LLM verdicts back into structured findings. `metrology/` is a separate, more recently added subsystem that captures review outcomes as auditable samples and computes agreement/dispersion/graduation statistics against calibrated judge configurations — its own architecture doc (320-arch) is honored well by the implementation, the one clear positive counter-example to the drift found elsewhere. A `server/` daemon (FastAPI over a Unix socket, optionally HTTP) manages long-lived agent processes for the `sq spawn`/`sq task` workflow, fronted by a thin `client/http.py`.

The architecture is coherent in its major seams (provider abstraction, action/step separation, pipeline vs. review vs. metrology as distinct concerns) but the busiest module — `pipeline/executor.py`, the thing every pipeline run passes through — has grown past a size where its five step-execution code paths stay in sync by discipline rather than by structure. The CLI layer mirrors this: `run.py`, `metrology.py`, and `review.py` are Typer commands that have absorbed orchestration logic that arguably belongs one layer down, in `pipeline`/`metrology`/`review` respectively. Two subsystems — the `ORCH_`-prefixed `Settings` class and the `anthropic`/`mcp`/`adk` provider stubs — appear to be residue from an earlier or future-facing design (the project's own `.env.example` and `google-adk`/`mcp` dependencies still reflect a name/scope, "orchestration", that the rest of the codebase has moved on from) that never got wired up or cleaned out.

## Findings Table

| ID | Category | File:Line | Severity | Effort | Description | Recommendation |
|----|----------|-----------|----------|--------|-------------|-----------------|
| F001 | architectural-decay | src/squadron/pipeline/executor.py:1-1576 | Critical | L | 1576-LOC file (5x the project's ~300-line guideline) mixing param resolution, loop grammar, session lifecycle, and 5 separate step-execution paths; also the 2nd-highest-churn file in 6 months | Split into execution_context.py, loop_runner.py, fan_out_runner.py, and a slim orchestrator |
| F002 | architectural-decay | src/squadron/pipeline/executor.py:979,1163,1251,1363,1455 | High | M | `_execute_step_once`/`_execute_loop_step`/`_execute_loop_body`/`_execute_each_step`/`_execute_fan_out_step` each repeat the same ~16-parameter signature | Bundle shared state into one `ExecutionContext` dataclass passed by reference |
| F003 | architectural-decay | src/squadron/pipeline/classification.py:239-249,278-291,297-309,347-360 | High | M | 4 near-identical blocks manually reconstruct a `StepClassification` field-by-field to change only `container_path`/`pool_name` | Replace with `dataclasses.replace(result, ...)` |
| F004 | architectural-decay | src/squadron/pipeline/classification.py:265,433; executor.py:25-28 | Medium | M | Circular dependency: executor.py imports classification.py at module level; classification.py imports back from executor.py via deferred local imports | Move shared low-level types into models.py so both depend downward on a common layer |
| F005 | architectural-decay | src/squadron/pipeline/loader.py:224-243,246-278 | Medium | S | `_validate_model_alias`/`_validate_review_template` accept an injected callable parameter that is never actually called — dead parameter | Use the injected callable or drop the parameter |
| F006 | architectural-decay | src/squadron/pipeline/actions/cf_op.py:91,94,109,113 | Medium | S | `CfOpAction` reaches into `ContextForgeClient._run`/`_run_json` (private members) via `pyright: ignore[reportPrivateUsage]` at 4 sites | Add public methods to `ContextForgeClient` for these operations |
| F007 | architectural-decay | src/squadron/cli/commands/run.py:753-1117 | Critical | L | 1116-LOC file whose `run()` function is itself ~365 lines handling 15+ mutually exclusive flag combinations; highest CLI churn (25 commits/6mo) | Split into per-mode dispatch functions; keep `run()` as pure routing |
| F008 | architectural-decay | src/squadron/cli/commands/metrology.py:1-1013 | High | L | 1013-LOC file combining CLI parsing, campaign-loop orchestration (audit_run/audit_variance), and report rendering | Move campaign-loop logic into squadron.metrology.audit; leave CLI as thin dispatch |
| F009 | architectural-decay | src/squadron/cli/commands/review.py:1-765 | Medium | L | 765-LOC file mixes template resolution, git-diff plumbing, rules loading, and rendering; highest CLI churn overall (40 commits/6mo) | Extract rules/diff resolution into a helper module shared with the pipeline review action |
| F010 | architectural-decay | src/squadron/cli/commands/message.py:23-35 (+ task.py:26-38, history.py:22-31, list.py:33-44, shutdown.py:32-61) | High | M | Identical "create DaemonClient → try → except DaemonNotRunningError → finally close()" boilerplate duplicated across 5 files | Extract an async context manager / decorator centralizing this pattern |
| F011 | architectural-decay | src/squadron/cli/commands/run.py:987-1041,1057-1093,1094-1116 | Medium | M | Resume, implicit-resume, and fresh-run branches each repeat the same match/KeyboardInterrupt/display/`typer.Exit(0)` block | Extract a shared `_execute_and_display(...)` helper |
| F012 | architectural-decay | src/squadron/cli/commands/doctor_checks.py; setup_steps.py:53-63,76-84,87-117,154-165 | Medium | M | `CheckResult.name` is a free-text string used as a matching key across 4 separate dicts with no shared enum — a rename silently orphans dependent entries; violates project's own "define once" rule | Introduce a `CheckId` enum shared by both files |
| F013 | architectural-decay | src/squadron/cli/commands/run.py:898,937,957,963,1045; pipeline/loader.py:65,69 | High | M | `.lower()` applied to the pipeline argument before calling `load_pipeline`, but `load_pipeline` checks `is_file()` on the *original* string before its own internal lowering — path-based invocation with any uppercase segment breaks on case-sensitive filesystems (verified) | Only lowercase when treating the argument as a name; let `load_pipeline` handle the path-vs-name branch |
| F014 | architectural-decay | src/squadron/metrology/audit.py:1-789 | Medium | L | 789-LOC file mixing preflight, git orchestration, prompt-building, progress tracking, execution, and persistence | Split into audit_preflight.py / audit_prompt.py / audit_run.py, mirroring existing audit_parse/audit_variance separation |
| F015 | architectural-decay | src/squadron/metrology/audit.py:41 | Medium | S | Imports private `_resolve_bundled` from squadron.skills.resolver via `pyright: ignore[reportPrivateUsage]` | Add a public `resolve_bundled_pack()` wrapper |
| F016 | architectural-decay | src/squadron/metrology/graduation.py:131,145-163 | Low | S | Uses `id(config)` as a dict key because `GraduatedConfig` isn't hashable — an object-identity workaround | Key on the existing `(template_name, model, template_content_hash, artifact_level)` tuple instead |
| F017 | architectural-decay | src/squadron/providers/anthropic/agent.py:1-3, provider.py:1-3, __init__.py:1-3 | Medium | S | Entire package is a 3-line "Populated in slice 6" stub, never registered in loader.py/registry.py | Delete the dead package, or wire it in — do not leave it unregistered |
| F018 | architectural-decay | src/squadron/review/review_client.py:326-358; src/squadron/review/rules.py:191-218 | High | M | Same git-diff-with-exclude-patterns subprocess invocation duplicated 3 times (review_client.py x2, rules.py x1) | Consolidate into git_utils.py as the single diff-file-list resolver |
| F019 | architectural-decay | src/squadron/providers/codex/provider.py:37-39 vs openai/provider.py:44-45 vs codex/agent.py:107-111 | Medium | S | Codex defers model validation to first message; OpenAI validates at `create_agent` time — inconsistent lifecycle point across providers | Move Codex's model check into `create_agent` to match OpenAI |
| F020 | architectural-decay | src/squadron/client/http.py:139-141; src/squadron/server/app.py:20-21 | High | S | `request_shutdown()` POSTs to `/shutdown`, but no such route is registered anywhere (only `/agents`-prefixed routes exist; shutdown is `DELETE /agents`) — verified, this call always 404s | Add the missing route, or delete the dead client method |
| F021 | architectural-decay | src/squadron/config/__init__.py:8-37 | Medium | S | `Settings(BaseSettings)` is never instantiated anywhere in src/ — all `ORCH_*` env vars it defines are dead | Wire `Settings()` into an actual startup path, or remove the class |
| F022 | architectural-decay | src/squadron/logging.py:29 | Medium | S | `setup_logging()` is called only from tests — log_level/log_format config never takes effect in production | Call `setup_logging(Settings())` at CLI/daemon startup, or remove it |
| F023 | architectural-decay | src/squadron/server/routes/agents.py:123 | Low | S | Route handler reaches into `engine.registry._configs` (private attr of private attr), acknowledged via `pyright: ignore` | Add a public `AgentRegistry.get_provider(name)` |
| F024 | consistency-rot | src/squadron/pipeline/intelligence/fan_in/reducers.py:59 | Medium | S | `if result.status != "completed":` compares an `ExecutionStatus`-typed field against a raw string literal — the exact "labels as logical structure" pattern the project guidelines forbid | Use `ExecutionStatus.COMPLETED` instead of the literal |
| F025 | consistency-rot | src/squadron/pipeline/actions/checkpoint.py:86-92 | Medium | S | Validation failure sets `outputs={"error": ...}` instead of `ActionResult.error`, so `_log_action_result` never surfaces this failure's message | Set `error=` on the `ActionResult`, not a same-named key in `outputs` |
| F026 | consistency-rot | src/squadron/pipeline/prompt_renderer.py:158,211,309 | Medium | S | 3 near-identical `try: resolver.resolve(...) except Exception: <fallback>` blocks, none logging | Extract one shared `_resolve_or_fallback(...)` helper |
| F027 | consistency-rot | src/squadron/cli/commands/*.py (repo-wide) | Medium | M | Two coexisting `typer.Exit` call conventions (`code=1` vs positional `1`) split along file boundaries, not by rule | Standardize on one form; enforce via lint rule |
| F028 | consistency-rot | src/squadron/cli/commands/config.py:30 vs review.py:156-163, metrology.py:92-102 | Medium | S | `--cwd` resolved two different ways: baked-in default vs `Optional` + private `_resolve_cwd` helper | Standardize `--cwd` resolution through one shared helper |
| F029 | consistency-rot | src/squadron/metrology/identity.py:34,46-50 vs capture.py:155, discovery.py:24+53, graduation.py:101, report.py:105 | Medium | S | The `"reviewType"` frontmatter key is centralized as `_FM_TEMPLATE` but never exported; 4 other modules re-hardcode the literal — violates "define once" rule | Export `REVIEW_TYPE_KEY = _FM_TEMPLATE` and reference it at all 5 sites |
| F030 | consistency-rot | src/squadron/providers/codex/agent.py:66 vs openai/translation.py:18,31; sdk/translation.py:45,55,72,85,96 | Low | S | Codex yields `Message(recipients=[])` while every other provider uses `recipients=["all"]` | Standardize on `"all"` (or a shared constant) |
| F031 | consistency-rot | src/squadron/core/models.py:60 | Medium | M | `AgentConfig.credentials: dict[str, Any]` is a grab-bag for unrelated concerns (auth vs. runtime behavior — mode, hooks, sandbox, retry), read via magic strings at 6+ sites | Split into a typed `credentials` dict (auth only) and a typed `agent_options` for runtime knobs |
| F032 | consistency-rot | src/squadron/review/models.py:38 vs parsers.py:104 | Medium | S | `category` is a free-form string parsed by regex from LLM prose — no enum, unlike `Severity`/`Verdict` which are proper `StrEnum`s | Define a `Category` enum or a documented, normalized open set |
| F033 | consistency-rot | src/squadron/server/routes/agents.py:44-88 vs 174-203 | Medium | M | `spawn_agent` translates 4 error types to HTTP codes; near-identical `run_task` only translates 2 — a duplicate-name task request produces an unhandled 500 | Extract a shared "spawn + translate errors" helper for both routes |
| F034 | consistency-rot | src/squadron/config/__init__.py:36-37 vs server/pid.py:18 | Low | S | Two different "default port" values (8000 in dead `Settings`, 7862 in the actually-used `DaemonConfig`) for the same concept | Remove the dead `Settings` fields |
| F035 | type-contract-debt | src/squadron/pipeline/executor.py:909,981,990,991,1137,1165,1175,1176,1253,1262,1263,1365,1374,1375,1457,1466,1467 | Medium | M | 17 occurrences of `step: Any`/`resolver: Any`/`cf_client: Any` in the busiest file in the subsystem | Give these real types or a `Protocol` for callback injection |
| F036 | type-contract-debt | src/squadron/pipeline/state.py (log_pool_selection) | Medium | S | `selection: object` parameter dodges a circular import, accessed via 6 separate `# type: ignore[union-attr]` suppressions | Define a `PoolSelectionLike` Protocol instead of `object` + blanket ignores |
| F037 | type-contract-debt | src/squadron/cli/commands/run.py:508 | Medium | S | `_display_run_status(state: object)` silently no-ops if state isn't a `RunState` — a silent fallback masking caller bugs, contradicting the project's "never use silent fallback values" rule | Type the parameter as `RunState`; raise `TypeError` if a defensive check is truly needed |
| F038 | type-contract-debt | src/squadron/cli/commands/models.py:160,168,175 | Medium | S | `response.json()` consumed as untyped `Any`; a malformed API response raises a raw KeyError/TypeError instead of a clear CLI error | Validate the expected shape before iterating |
| F039 | type-contract-debt | src/squadron/cli/commands/list.py:56-61, message.py:40-41, history.py:40-42, task.py:44-55, shutdown.py:51-56 | Medium | M | Daemon HTTP responses consumed as raw `dict[str, Any]` at 5+ sites — no shared response model | Define a shared TypedDict/dataclass for agent/message payloads |
| F040 | type-contract-debt | src/squadron/metrology/audit.py:508,536-555 | Medium | S | `agent` parameter typed as bare `object`, accessed via `.handle_message()`/`.rate_limit_stats` behind 3 pyright-ignores | Define a minimal `AuditAgent` Protocol |
| F041 | type-contract-debt | src/squadron/review/parsers.py:79-98 | Medium | M | `_FINDING_RE` is a single ~20-line alternation regex encoding 3 heading formats; a wrong branch silently drops findings rather than erroring | Split into per-format regexes tried in sequence with a logged fallback when nothing matches |
| F042 | type-contract-debt | src/squadron/config/manager.py:54-61; config/keys.py:162,171,180 | High | S | `_coerce_value` only handles `int`/`str`; 3 `CONFIG_KEYS` are declared `type_=float`. Verified: `sq config set metrology.graduate_match_rate 0.95` raises `ValueError: Unsupported config type` | Add a `float` branch to `_coerce_value` |
| F043 | test-debt | src/squadron/pipeline/executor.py (fan-out gather path, ~1494,1546) | Medium | S | No test asserts a fan-out branch exception is logged (only that a FAILED result is returned) | Add a `caplog`-based test for the ERROR log on fan-out failure |
| F044 | test-debt | src/squadron/metrology/audit.py:673-687 | Medium | S | No test exercises the `RATE_LIMITED` branch of `run_audit`, though every sibling failure branch has one | Add a test with a mock agent raising `ProviderRateLimitError` |
| F045 | test-debt | src/squadron/review/review_client.py:326-358 | High | M | `_run_git_diff_filenames` (the diff-membership hallucination check) has zero test coverage | Add unit tests for success, non-zero-exit, and `FileNotFoundError` paths |
| F046 | test-debt | src/squadron/providers/codex/agent.py:80-83 | High | S | No test exercises `shutdown()`'s exception-swallowing path | Add a test where `_codex.__aexit__` raises, asserting graceful termination |
| F047 | test-debt | src/squadron/config/manager.py (float keys) | Medium | S | No test calls set/get against any float-typed config key — how F042 shipped unnoticed | Parametrize a set/get round-trip test over every `CONFIG_KEYS` type |
| F048 | test-debt | src/squadron/client/http.py:139-141 | Medium | S | `request_shutdown` has zero test coverage — how F020 shipped unnoticed | Add a round-trip test against the real app fixture (would fail today) |
| F049 | test-debt | src/squadron/server/routes/agents.py (run_task) | Medium | S | `POST /agents/{name}/task` has zero test coverage of any kind | Add success + duplicate-name + provider-error tests |
| F050 | test-debt | src/squadron/cli/commands/run.py:754 | Low | S | Help text says pipeline may be "a path to YAML definition," but no test exercises path invocation with an uppercase segment (the case F013 breaks) | Add a test for path-based invocation with mixed case |
| F051 | dependency-config-debt | .env.example (whole file); providers/profiles.py:40,47,65; providers/auth.py:66,91,107-109,138-139; codex/auth.py:45,74; openai/provider.py:70 | High | S | `.env.example` documents only `ORCH_`-prefixed vars; the credentials actually required at runtime (`OPENAI_API_KEY`, `OPENROUTER_API_KEY`, `GEMINI_API_KEY`, and the hardcoded `OPENAI_API_KEY` fallback) are unprefixed and entirely undocumented | Add an "unprefixed provider credentials" section to `.env.example` sourced from `profiles.py` |
| F052 | dependency-config-debt | pyproject.toml:26 (`google-adk>=0.1.0`) | Medium | S | Direct dependency, never imported anywhere in src/ (verified); `squadron/adk/__init__.py` is a 3-line stub | Move to an optional extra, or drop until the owning slice lands |
| F053 | dependency-config-debt | pyproject.toml:27 (`mcp>=1.0.0`) | Medium | S | Same as F052 — verified unused; `squadron/mcp/__init__.py` is a 3-line stub | Same as F052 |
| F054 | performance-resource | src/squadron/pipeline/intelligence/pools/loader.py:230-270; backend.py:64-71 | Medium | M | Every pool selection re-reads and re-parses TOML files from disk with no caching, repeating on every loop/fan_out/each iteration | Cache the merged pool table (mtime-invalidated or per-run) |
| F055 | performance-resource | src/squadron/metrology/audit.py:248-256,341,348,366 | Medium | S | `_run_git` (preflight) has no timeout, unlike identity.py's bounded git calls — a hung/lock-stuck git blocks preflight indefinitely | Add the same bounded timeout + `TimeoutExpired` handling identity.py already uses |
| F056 | performance-resource | src/squadron/metrology/store.py:188-345 | Low | M | Every `list_*` query globs+validates every JSON file in the store directory with no index — cost grows with total lifetime records, not just the queried project | Note for future growth; add a per-project subdirectory or index if volume grows |
| F057 | performance-resource | src/squadron/integrations/context_forge.py:78-83 | Medium | S | `subprocess.run(["cf", ...])` has no timeout — a hung `cf` process blocks the caller indefinitely with no observable signal, against the project's own failure-mode-enumeration rule | Add `timeout=`, translate `TimeoutExpired` into `ContextForgeError` |
| F058 | performance-resource | src/squadron/skills/resolver.py:59-62 | Medium | S | `subprocess.run(["git","clone","--depth=1",...])` has no timeout — a stalled clone blocks `install_pack` forever | Add a timeout and handle `TimeoutExpired` explicitly |
| F059 | error-handling-observability | src/squadron/pipeline/executor.py:1494,1546 | High | M | Fan-out branch build/gather `except Exception` returns a FAILED result with zero logging | Add `_logger.exception(...)` before returning the failure result |
| F060 | error-handling-observability | src/squadron/pipeline/actions/summary.py:254-260 | High | S | Summary-capture `except Exception` returns failure with zero logging, inconsistent with the restore path 100 lines above in the same file, which does log | Add `_logger.exception(...)` before returning |
| F061 | error-handling-observability | src/squadron/pipeline/emit.py:157-158 | Medium | S | `_emit_rotate` swallows any exception from `sdk_session.compact()` with no log call, though a rotate failure halts the whole action | Log at ERROR/`.exception` before converting to `EmitResult(ok=False)` |
| F062 | error-handling-observability | src/squadron/pipeline/loader.py:140-142 | Medium | S | `discover_pipelines` catches bare `except Exception` around YAML+schema validation, logs only WARNING, silently skips the file | Narrow to `(yaml.YAMLError, pydantic.ValidationError, OSError)`; log unexpected types at ERROR and re-raise |
| F063 | error-handling-observability | src/squadron/pipeline/actions/cf_op.py:107-108 | Medium | S | `except Exception: pass` (with a comment) around model resolution catches unexpected bugs too, not just the two documented resolver exceptions | Narrow to `(ModelResolutionError, ModelPoolNotImplemented)` |
| F064 | error-handling-observability | src/squadron/pipeline/actions/compact.py:127-130 | High | M | Prompt-only compact re-raises `TimeoutError` instead of returning `ActionResult(success=False)` like every other failure path in the file; executor.py has no surrounding try/except at the call site, so this crashes the whole run | Catch `TimeoutError` and return a FAILED `ActionResult` like the sibling branch |
| F065 | error-handling-observability | src/squadron/cli/commands/review.py:278-279 | Medium | S | `except KeyError: pass` with no justifying comment (project convention requires one) | Add a one-line comment explaining why the miss is expected |
| F066 | error-handling-observability | src/squadron/cli/commands/spawn.py:101-103 | Medium | S | `except Exception as exc` prints the message but never calls `logger.exception`, and re-raises `typer.Exit` without `from exc` | Add `logger.exception("spawn failed")`; chain with `from exc` |
| F067 | error-handling-observability | src/squadron/cli/commands/dispatch_run.py:63,79; summary_run.py:67 | High | S | Harness-invoked commands catch `Exception` and print to stderr only, no `logger.exception` — since these run non-interactively, this is the sole diagnostic surface and it's silent | Add `logger.exception` before the stderr message |
| F068 | error-handling-observability | src/squadron/cli/commands/review.py:361-363 | Medium | S | Blanket `except Exception` around `_execute_review` converts every failure into a generic message with no `logger.exception` call | Log at ERROR before exiting |
| F069 | error-handling-observability | src/squadron/providers/codex/agent.py:80-83 | Critical | S | `except Exception: pass` in `shutdown()` — no comment, no logging — a direct violation of the project's exception-handling rule | Add `logger.exception`, or at minimum a justifying comment |
| F070 | error-handling-observability | src/squadron/providers/sdk/agent.py:245-248 | Medium | S | `except Exception: pass  # Best-effort cleanup` catches the broadest type; comment present but type not narrowed | Narrow to the SDK's own disconnect exception type and/or log at WARNING |
| F071 | error-handling-observability | src/squadron/metrology/audit.py:688-704 | Medium | M | Bare `except Exception` reclassifies every stream failure as `STREAM_ERROR`, which would also silently reclassify a genuine bug in this function as a provider problem | Narrow the catch, or explicitly re-raise programmer-error exception classes first |
| F072 | error-handling-observability | src/squadron/core/agent_registry.py:117-126 | Medium | S | `except Exception:` (no `as exc`) logs `str(agent)` (the agent's repr) instead of the actual exception text — the warning never surfaces why shutdown failed | Bind `as exc`, log `str(exc)` |
| F073 | error-handling-observability | src/squadron/core/agent_registry.py:143-149; server/engine.py:125-133; server/daemon.py:87 | Medium | M | `shutdown_all` collects per-agent failure reasons but only logs aggregate counts; `daemon.py` discards the `ShutdownReport` return value entirely — a failed shutdown is completely silent end-to-end | Log each `report.failed[name]` at WARNING at the engine layer |
| F074 | error-handling-observability | src/squadron/review/templates/__init__.py:129-146 | Medium | M | `load_template` wraps some validation in `TemplateValidationError` but lets required-field access (`data["name"]`, etc.) raise raw, contextless `KeyError` for any other missing field | Wrap required-field access in the same `TemplateValidationError` pattern, with file path |
| F075 | security-hygiene | src/squadron/pipeline/prompt_renderer.py:281 | High | S | `_render_commit` builds `f"git add -A && git commit -m '{message}'"` with raw single-quote wrapping and no `shlex.quote()`, while sibling renderers in the same file do use it — a message containing a single quote breaks the quoting in the shell command shown to the executing agent | Use `shlex.quote(message)` consistently, matching the other renderers |
| F076 | security-hygiene | src/squadron/metrology/capture.py:178-181 | Low | S | `build_capture_payload` resolves `artifact_path` via `Path(cwd) / artifact_path` with no containment check; an absolute or `..`-containing path would silently escape `cwd` | Assert the resolved path is relative to `cwd`, raising otherwise |
| F077 | security-hygiene | src/squadron/review/review_client.py:339-358,372-391 | Low | S | Exclude-pattern/ref values interpolated into git pathspecs (`f":!{p}"`) without validating they don't start with `-` (argv-list form prevents shell injection; this is a git flag-injection risk only) | Validate exclude_patterns don't start with `-` |
| F078 | security-hygiene | src/squadron/providers/codex/auth.py:16 | Low | S | Hardcoded `~/.codex/auth.json` path read with no check that permissions aren't world-readable | Warn if file permissions are broader than 0600 |
| F079 | documentation-drift | src/squadron/pipeline/intelligence/fan_in/reducers.py:4; src/squadron/metrology/audit_models.py:1; src/squadron/cli/commands/run.py:754 | Low | S | Three stale/inaccurate docstring or help-text claims: a `merge_findings` reducer that doesn't exist, an "one import site" claim its own consumer bypasses, and path-argument help text whose accuracy depends on the F013 bug being fixed | Correct each docstring/help string to match current behavior |

## Top 5 — If You Fix Nothing Else, Fix These

**1. F042 — `sq config set` crashes on float config keys.** Verified live bug.
```python
# src/squadron/config/manager.py
def _coerce_value(key: str, raw_value: str) -> object:
    key_def = CONFIG_KEYS[key]
    if key_def.type_ is int:
        return int(raw_value)
    if key_def.type_ is str:
        return raw_value
+   if key_def.type_ is float:
+       return float(raw_value)
    raise ValueError(f"Unsupported config type: {key_def.type_}")
```

**2. F020 — `request_shutdown()` always 404s.** No `/shutdown` route exists; only `DELETE /agents` performs shutdown. Either add the route the client expects, or delete the dead client method and route callers to the existing `DELETE /agents` endpoint. This is a broken feature currently masked by zero test coverage (F048).

**3. F069 — silent shutdown-exception swallow in the Codex provider.** Direct violation of the project's own exception-handling rule.
```python
# src/squadron/providers/codex/agent.py
async def shutdown(self) -> None:
    try:
        await self._codex.__aexit__(None, None, None)
-   except Exception:
-       pass
+   except Exception:
+       logger.exception("codex agent shutdown failed")
```

**4. F075 — commit-message renderer skips `shlex.quote()`.** A commit-message prefix containing a single quote breaks out of the emitted shell command shown to (and executed by) the agent — the classic quoting-based injection shape, in a file whose sibling renderers already use `shlex.quote()` correctly.
```python
# src/squadron/pipeline/prompt_renderer.py — _render_commit
-return f"git add -A && git commit -m '{message}'"
+return f"git add -A && git commit -m {shlex.quote(message)}"
```

**5. F001/F002/F007 — `executor.py` and `run.py` are both god files at the center of the highest-churn area of the codebase.** These aren't isolated one-line fixes but the highest-leverage structural investment: `executor.py`'s 5 near-duplicate step-execution signatures (F002) and `run.py`'s 365-line `run()` function (F007) are where every future pipeline feature will have to fight the file's size to land safely. Start with `ExecutionContext` extraction in executor.py — it directly resolves F002, F035, and shrinks F001 in one pass.

## Quick Wins

- [ ] F042 — add `float` branch to `_coerce_value` (config/manager.py:54-61)
- [ ] F069 — log or comment the swallowed shutdown exception in codex/agent.py:80-83
- [ ] F075 — use `shlex.quote()` in `_render_commit` (prompt_renderer.py:281)
- [ ] F020 — delete the dead `request_shutdown()` client method or add the matching route
- [ ] F024 — replace the `"completed"` string literal with `ExecutionStatus.COMPLETED` (fan_in/reducers.py:59)
- [ ] F029 — export `REVIEW_TYPE_KEY` from identity.py and use it at the 4 hardcoded sites
- [ ] F037 — raise instead of silently no-op in `_display_run_status` (run.py:508)
- [ ] F060 — add `_logger.exception(...)` to the summary-capture failure path (actions/summary.py:254-260)
- [ ] F067 — add `logger.exception` to dispatch_run.py/summary_run.py's harness error paths
- [ ] F072 — bind `as exc` and log the real exception text in agent_registry.py:117-126
- [ ] F052/F053 — drop or extras-ify the unused `google-adk`/`mcp` dependencies
- [ ] F065 — add a justifying comment to the uncommented `except KeyError: pass` (review.py:278-279)
- [ ] F017 — delete the dead `anthropic/` provider stub package, or register it

## Things That Look Bad But Are Actually Fine

- `sdk_session.py`'s `disconnect()` swallowing all exceptions at DEBUG level has an explicit "best-effort, ignores errors" docstring for a teardown path where a dead client failing to disconnect is inconsequential — satisfies the project's suppression-justification rule in spirit.
- `gate.py`'s `VALID_GATE_POLICIES` set has only one member, which looks like a stub registry — but the code comment explicitly explains this is deliberate (validated for auditability, not dispatched on) per the project's own rule against building a registry before a second real caller exists.
- `doctor_checks.py` is the cleanest exception-handling file found in the audit: every catch site logs via `logger.exception` before degrading to a WARN row. Held up as the pattern other CLI files should match, not flagged as debt.
- `review.py`'s `--fan` flag prints a "reserved for future fan-out support" warning and does nothing else — this is honest, self-documenting placeholder code, not dead/silent code.
- `metrology/audit.py` at 789 lines is large but cleanly sectioned (preflight / prompt-build / execution / persist), each with its own dataclass and docstring — flagged as a future-split candidate (F014), not active decay.
- `metrology/store.py`'s full-directory-scan query pattern looks like a scaling problem, but the 320-arch document explicitly chose "no database dependency, per-record JSON" for a stated small-n regime — not urgent debt today (noted forward-looking in F056).
- `sdk/rate_limit.py`'s `install_rate_limit_parser_shim` monkeypatches two module bindings, which looks fragile — but the docstring explains precisely why both bindings need patching (an upstream SDK limitation, verified rather than assumed) and it is well-commented, deliberate defensive code.
- `git_utils.py` hardcoding `"main"` looks like it ignores this project's own `git.integration_branch` config concept — but that key belongs to the external `cf` tool's workflow, not to the *reviewed* project's branch, which is what this file resolves diffs against. Orthogonal concerns.
- The server daemon has no CORS middleware or auth layer — but it's hardcoded to bind `127.0.0.1` and its primary transport is a Unix domain socket, filesystem-permission-gated. Reasonable trust model for a local-only daemon.
- `skills/` (installer.py, manifest.py, resolver.py, receipts.py) has consistently exemplary exception handling — every catch is narrowly typed, logs before re-raising, or carries an explicit justification comment. A model for the rest of the codebase, not a debt site.

## Open Questions for the Maintainer

- Is the `anthropic/` provider package (F017) intentionally-deferred scaffolding for a not-yet-landed slice, or should it be deleted now that it predates the current provider registration pattern?
- Are `google-adk` and `mcp` (F052/F053) intentionally installed ahead of the slices that will use them, or should they be removed from `pyproject.toml` until those slices land?
- Is the `Settings`/`ORCH_*` env-var scheme (F021/F022) meant to be wired into the CLI/daemon startup path in a future slice, or is it dead code left from the project's earlier "orchestration" name — and should `.env.example` be rewritten around the credentials actually in use today (F051) regardless of that answer?
- Is `AgentConfig.credentials: dict[str, Any]` (F031) intentionally left untyped given real per-provider variance, or is a typed split already planned for a later slice?

<!-- squadron:findings:begin v1 -->
```yaml
findings:
  - id: F001
    category: architectural-decay
    location: src/squadron/pipeline/executor.py:1-1576
    severity: Critical
    effort: L
    summary: 1576-LOC file mixing param resolution, loop grammar, session lifecycle, and 5 separate step-execution paths, also the 2nd-highest-churn file in 6 months
  - id: F002
    category: architectural-decay
    location: src/squadron/pipeline/executor.py:979,1163,1251,1363,1455
    severity: High
    effort: M
    summary: Five step-execution functions repeat the same roughly 16-parameter signature
  - id: F003
    category: architectural-decay
    location: src/squadron/pipeline/classification.py:239-249,278-291,297-309,347-360
    severity: High
    effort: M
    summary: Four near-identical blocks manually reconstruct a StepClassification field-by-field instead of using dataclasses.replace
  - id: F004
    category: architectural-decay
    location: src/squadron/pipeline/classification.py:265,433
    severity: Medium
    effort: M
    summary: Circular dependency between classification.py and executor.py via module-level and deferred imports
  - id: F005
    category: architectural-decay
    location: src/squadron/pipeline/loader.py:224-243,246-278
    severity: Medium
    effort: S
    summary: Injected callable parameters for model-alias and template validation are accepted but never actually called
  - id: F006
    category: architectural-decay
    location: src/squadron/pipeline/actions/cf_op.py:91,94,109,113
    severity: Medium
    effort: S
    summary: CfOpAction reaches into private ContextForgeClient members via pyright-ignore at four call sites
  - id: F007
    category: architectural-decay
    location: src/squadron/cli/commands/run.py:753-1117
    severity: Critical
    effort: L
    summary: 1116-LOC file whose run() function is itself about 365 lines handling 15+ mutually exclusive flag combinations
  - id: F008
    category: architectural-decay
    location: src/squadron/cli/commands/metrology.py:1-1013
    severity: High
    effort: L
    summary: 1013-LOC file combines CLI parsing, campaign-loop orchestration, and report rendering
  - id: F009
    category: architectural-decay
    location: src/squadron/cli/commands/review.py:1-765
    severity: Medium
    effort: L
    summary: 765-LOC file mixes template resolution, git-diff plumbing, rules loading, and rendering, the highest-churn CLI file
  - id: F010
    category: architectural-decay
    location: src/squadron/cli/commands/message.py:23-35
    severity: High
    effort: M
    summary: Identical DaemonClient create-try-except-finally boilerplate duplicated across five CLI command files
  - id: F011
    category: architectural-decay
    location: src/squadron/cli/commands/run.py:987-1041,1057-1093,1094-1116
    severity: Medium
    effort: M
    summary: Resume, implicit-resume, and fresh-run branches each repeat the same match and display block
  - id: F012
    category: architectural-decay
    location: src/squadron/cli/commands/doctor_checks.py
    severity: Medium
    effort: M
    summary: CheckResult.name is a free-text string used as a matching key across four separate dicts with no shared enum
  - id: F013
    category: architectural-decay
    location: src/squadron/cli/commands/run.py:898,937,957,963,1045
    severity: High
    effort: M
    summary: Lowercasing the pipeline argument before calling load_pipeline breaks path-based invocation with uppercase segments on case-sensitive filesystems, verified against load_pipeline's own branch order
  - id: F014
    category: architectural-decay
    location: src/squadron/metrology/audit.py:1-789
    severity: Medium
    effort: L
    summary: 789-LOC file mixes preflight, git orchestration, prompt-building, progress tracking, execution, and persistence
  - id: F015
    category: architectural-decay
    location: src/squadron/metrology/audit.py:41
    severity: Medium
    effort: S
    summary: Imports a private function from squadron.skills.resolver via pyright-ignore instead of a public wrapper
  - id: F016
    category: architectural-decay
    location: src/squadron/metrology/graduation.py:131,145-163
    severity: Low
    effort: S
    summary: Uses Python object identity as a dict key because GraduatedConfig is not hashable
  - id: F017
    category: architectural-decay
    location: src/squadron/providers/anthropic/agent.py:1-3
    severity: Medium
    effort: S
    summary: Entire anthropic provider package is a three-line stub never registered in the provider loader or registry
  - id: F018
    category: architectural-decay
    location: src/squadron/review/review_client.py:326-358
    severity: High
    effort: M
    summary: The same git-diff-with-exclude-patterns subprocess invocation is duplicated three times across review_client.py and rules.py
  - id: F019
    category: architectural-decay
    location: src/squadron/providers/codex/provider.py:37-39
    severity: Medium
    effort: S
    summary: Codex defers model validation to the first message while OpenAI validates at agent-creation time, an inconsistent lifecycle point across providers
  - id: F020
    category: architectural-decay
    location: src/squadron/client/http.py:139-141
    severity: High
    effort: S
    summary: request_shutdown posts to a slash-shutdown route that is never registered anywhere in the server, verified to always return 404
  - id: F021
    category: architectural-decay
    location: src/squadron/config/__init__.py:8-37
    severity: Medium
    effort: S
    summary: The Settings class and its ORCH-prefixed env vars are never instantiated anywhere in production code
  - id: F022
    category: architectural-decay
    location: src/squadron/logging.py:29
    severity: Medium
    effort: S
    summary: setup_logging is only called from tests, so log level and format configuration never takes effect in production
  - id: F023
    category: architectural-decay
    location: src/squadron/server/routes/agents.py:123
    severity: Low
    effort: S
    summary: Route handler reaches into a private attribute of a private attribute on the engine's registry
  - id: F024
    category: consistency-rot
    location: src/squadron/pipeline/intelligence/fan_in/reducers.py:59
    severity: Medium
    effort: S
    summary: Compares an ExecutionStatus-typed field against a raw string literal instead of the enum member, violating the project's own rule against labels as logical structure
  - id: F025
    category: consistency-rot
    location: src/squadron/pipeline/actions/checkpoint.py:86-92
    severity: Medium
    effort: S
    summary: Validation failure sets an error key inside outputs instead of the ActionResult error field that logging reads from
  - id: F026
    category: consistency-rot
    location: src/squadron/pipeline/prompt_renderer.py:158,211,309
    severity: Medium
    effort: S
    summary: Three near-identical try-except-fallback blocks for resolver.resolve exist with no shared helper and no logging
  - id: F027
    category: consistency-rot
    location: src/squadron/cli/commands
    severity: Medium
    effort: M
    summary: Two coexisting typer.Exit call conventions are split along file boundaries rather than by any semantic rule
  - id: F028
    category: consistency-rot
    location: src/squadron/cli/commands/config.py:30
    severity: Medium
    effort: S
    summary: The cwd option is resolved two different ways across CLI commands, a baked-in default versus an optional value plus helper
  - id: F029
    category: consistency-rot
    location: src/squadron/metrology/identity.py:34,46-50
    severity: Medium
    effort: S
    summary: The reviewType frontmatter key is centralized internally but never exported, so four other modules re-hardcode the literal
  - id: F030
    category: consistency-rot
    location: src/squadron/providers/codex/agent.py:66
    severity: Low
    effort: S
    summary: Codex yields an empty recipients list while every other provider translation path uses a shared all-recipients convention
  - id: F031
    category: consistency-rot
    location: src/squadron/core/models.py:60
    severity: Medium
    effort: M
    summary: AgentConfig.credentials is an untyped grab-bag mixing authentication and unrelated runtime-behavior configuration
  - id: F032
    category: consistency-rot
    location: src/squadron/review/models.py:38
    severity: Medium
    effort: S
    summary: Review finding category is a free-form string parsed by regex with no enum, unlike the project's other verdict and severity types
  - id: F033
    category: consistency-rot
    location: src/squadron/server/routes/agents.py:44-88
    severity: Medium
    effort: M
    summary: spawn_agent translates four error types to HTTP codes while the near-identical run_task route only translates two
  - id: F034
    category: consistency-rot
    location: src/squadron/config/__init__.py:36-37
    severity: Low
    effort: S
    summary: Two different default port values exist for the same daemon-port concept in dead versus live configuration classes
  - id: F035
    category: type-contract-debt
    location: src/squadron/pipeline/executor.py:909,981,990,991,1137,1165,1175,1176,1253,1262,1263,1365,1374,1375,1457,1466,1467
    severity: Medium
    effort: M
    summary: Seventeen occurrences of parameters typed Any in the busiest execution file in the pipeline subsystem
  - id: F036
    category: type-contract-debt
    location: src/squadron/pipeline/state.py
    severity: Medium
    effort: S
    summary: A selection parameter typed as object to dodge a circular import requires six separate type-ignore suppressions instead of a Protocol
  - id: F037
    category: type-contract-debt
    location: src/squadron/cli/commands/run.py:508
    severity: Medium
    effort: S
    summary: A display function silently no-ops on an unexpected input type instead of raising, contradicting the project's rule against silent fallback values
  - id: F038
    category: type-contract-debt
    location: src/squadron/cli/commands/models.py:160,168,175
    severity: Medium
    effort: S
    summary: An HTTP JSON response is consumed as untyped Any so a malformed response raises a raw unhandled error instead of a clear CLI error
  - id: F039
    category: type-contract-debt
    location: src/squadron/cli/commands/list.py:56-61
    severity: Medium
    effort: M
    summary: Daemon HTTP responses are consumed as raw untyped dicts at five or more call sites with no shared response model
  - id: F040
    category: type-contract-debt
    location: src/squadron/metrology/audit.py:508,536-555
    severity: Medium
    effort: S
    summary: An agent parameter is typed as bare object and accessed through three separate type-ignore suppressions
  - id: F041
    category: type-contract-debt
    location: src/squadron/review/parsers.py:79-98
    severity: Medium
    effort: M
    summary: A single large alternation regex encodes three heading formats and silently drops findings rather than erroring on an unmatched branch
  - id: F042
    category: type-contract-debt
    location: src/squadron/config/manager.py:54-61
    severity: High
    effort: S
    summary: Config value coercion has no float branch though three config keys are declared as float type, verified to crash on set
  - id: F043
    category: test-debt
    location: src/squadron/pipeline/executor.py:1494,1546
    severity: Medium
    effort: S
    summary: No test asserts that a fan-out branch exception is logged, only that a failed result is returned
  - id: F044
    category: test-debt
    location: src/squadron/metrology/audit.py:673-687
    severity: Medium
    effort: S
    summary: No test exercises the rate-limited failure branch of run_audit though every sibling failure branch has one
  - id: F045
    category: test-debt
    location: src/squadron/review/review_client.py:326-358
    severity: High
    effort: M
    summary: The diff-membership hallucination-check helper function has zero test coverage
  - id: F046
    category: test-debt
    location: src/squadron/providers/codex/agent.py:80-83
    severity: High
    effort: S
    summary: No test exercises the shutdown exception-swallowing path in the Codex provider
  - id: F047
    category: test-debt
    location: src/squadron/config/manager.py
    severity: Medium
    effort: S
    summary: No test calls set or get against any float-typed config key, which is how the coercion bug shipped unnoticed
  - id: F048
    category: test-debt
    location: src/squadron/client/http.py:139-141
    severity: Medium
    effort: S
    summary: The request_shutdown client method has zero test coverage, which is how the always-404 bug shipped unnoticed
  - id: F049
    category: test-debt
    location: src/squadron/server/routes/agents.py
    severity: Medium
    effort: S
    summary: The run_task HTTP route has zero test coverage of any kind
  - id: F050
    category: test-debt
    location: src/squadron/cli/commands/run.py:754
    severity: Low
    effort: S
    summary: No test exercises path-based pipeline invocation with an uppercase path segment
  - id: F051
    category: dependency-config-debt
    location: .env.example
    severity: High
    effort: S
    summary: The example env file documents only the unused ORCH-prefixed settings scheme while the credentials actually read at runtime are unprefixed and undocumented
  - id: F052
    category: dependency-config-debt
    location: pyproject.toml:26
    severity: Medium
    effort: S
    summary: google-adk is a direct dependency never imported anywhere in the source tree
  - id: F053
    category: dependency-config-debt
    location: pyproject.toml:27
    severity: Medium
    effort: S
    summary: mcp is a direct dependency never imported anywhere in the source tree
  - id: F054
    category: performance-resource
    location: src/squadron/pipeline/intelligence/pools/loader.py:230-270
    severity: Medium
    effort: M
    summary: Every pool selection re-reads and re-parses TOML files from disk with no caching, repeating on every loop iteration
  - id: F055
    category: performance-resource
    location: src/squadron/metrology/audit.py:248-256,341,348,366
    severity: Medium
    effort: S
    summary: Preflight git calls have no timeout unlike other bounded git calls elsewhere in the same subsystem
  - id: F056
    category: performance-resource
    location: src/squadron/metrology/store.py:188-345
    severity: Low
    effort: M
    summary: Every store query globs and validates every JSON file in the directory with no index, a cost that grows with total lifetime records
  - id: F057
    category: performance-resource
    location: src/squadron/integrations/context_forge.py:78-83
    severity: Medium
    effort: S
    summary: The context-forge CLI subprocess call has no timeout, so a hung process blocks the caller indefinitely with no observable signal
  - id: F058
    category: performance-resource
    location: src/squadron/skills/resolver.py:59-62
    severity: Medium
    effort: S
    summary: The git clone subprocess call for skill packs has no timeout, so a stalled network clone blocks installation forever
  - id: F059
    category: error-handling-observability
    location: src/squadron/pipeline/executor.py:1494,1546
    severity: High
    effort: M
    summary: The fan-out branch build and gather exception handler returns a failed result with zero logging
  - id: F060
    category: error-handling-observability
    location: src/squadron/pipeline/actions/summary.py:254-260
    severity: High
    effort: S
    summary: The summary-capture exception handler returns failure with zero logging, inconsistent with the sibling restore path in the same file
  - id: F061
    category: error-handling-observability
    location: src/squadron/pipeline/emit.py:157-158
    severity: Medium
    effort: S
    summary: A rotate operation swallows a compact-session exception with no log call though the failure halts the whole action
  - id: F062
    category: error-handling-observability
    location: src/squadron/pipeline/loader.py:140-142
    severity: Medium
    effort: S
    summary: Pipeline discovery catches a bare broad exception around parsing and validation, logging only at warning level and silently skipping the file
  - id: F063
    category: error-handling-observability
    location: src/squadron/pipeline/actions/cf_op.py:107-108
    severity: Medium
    effort: S
    summary: A commented broad exception catch around model resolution also catches unexpected bugs beyond the two documented resolver exceptions
  - id: F064
    category: error-handling-observability
    location: src/squadron/pipeline/actions/compact.py:127-130
    severity: High
    effort: M
    summary: A timeout error is re-raised instead of returned as a failed action result, crashing the whole pipeline run instead of producing an observable failure
  - id: F065
    category: error-handling-observability
    location: src/squadron/cli/commands/review.py:278-279
    severity: Medium
    effort: S
    summary: A bare except KeyError pass has no justifying comment as the project's exception-handling convention requires
  - id: F066
    category: error-handling-observability
    location: src/squadron/cli/commands/spawn.py:101-103
    severity: Medium
    effort: S
    summary: A broad exception handler prints a message but never logs the exception and re-raises without chaining the original error
  - id: F067
    category: error-handling-observability
    location: src/squadron/cli/commands/dispatch_run.py:63,79
    severity: High
    effort: S
    summary: Harness-invoked commands catch broad exceptions and print to stderr only, with no exception logging as the sole diagnostic surface for non-interactive failures
  - id: F068
    category: error-handling-observability
    location: src/squadron/cli/commands/review.py:361-363
    severity: Medium
    effort: S
    summary: A blanket exception handler converts every review failure into a generic message with no exception logging
  - id: F069
    category: error-handling-observability
    location: src/squadron/providers/codex/agent.py:80-83
    severity: Critical
    effort: S
    summary: Shutdown swallows every exception with no comment and no logging, a direct violation of the project's exception-handling rule
  - id: F070
    category: error-handling-observability
    location: src/squadron/providers/sdk/agent.py:245-248
    severity: Medium
    effort: S
    summary: Shutdown swallows the broadest exception type for best-effort cleanup with a comment present but the exception type not narrowed
  - id: F071
    category: error-handling-observability
    location: src/squadron/metrology/audit.py:688-704
    severity: Medium
    effort: M
    summary: A bare broad exception handler reclassifies every stream failure the same way, which would also mask a genuine bug in the same function as a provider problem
  - id: F072
    category: error-handling-observability
    location: src/squadron/core/agent_registry.py:117-126
    severity: Medium
    effort: S
    summary: A broad exception handler logs the agent's own representation instead of the actual exception text, so the warning never explains the failure
  - id: F073
    category: error-handling-observability
    location: src/squadron/core/agent_registry.py:143-149
    severity: Medium
    effort: M
    summary: Shutdown-all collects per-agent failure reasons but only logs aggregate counts, and the daemon discards the shutdown report entirely
  - id: F074
    category: error-handling-observability
    location: src/squadron/review/templates/__init__.py:129-146
    severity: Medium
    effort: M
    summary: Template loading wraps some validation in a custom error type but lets other required-field access raise a raw contextless key error
  - id: F075
    category: security-hygiene
    location: src/squadron/pipeline/prompt_renderer.py:281
    severity: High
    effort: S
    summary: The commit-message renderer omits the shell-quoting helper its sibling renderers use, so a message containing a single quote breaks out of the emitted shell command
  - id: F076
    category: security-hygiene
    location: src/squadron/metrology/capture.py:178-181
    severity: Low
    effort: S
    summary: An artifact path is joined onto a base directory with no containment check, letting an absolute or parent-relative path escape the intended directory
  - id: F077
    category: security-hygiene
    location: src/squadron/review/review_client.py:339-358,372-391
    severity: Low
    effort: S
    summary: Exclude-pattern and ref values are interpolated into git pathspecs without validating they cannot be parsed as flags
  - id: F078
    category: security-hygiene
    location: src/squadron/providers/codex/auth.py:16
    severity: Low
    effort: S
    summary: A hardcoded auth-token file path is read with no check that its permissions are not overly permissive
  - id: F079
    category: documentation-drift
    location: src/squadron/pipeline/intelligence/fan_in/reducers.py:4
    severity: Low
    effort: S
    summary: Multiple stale docstring and help-text claims describe behavior that does not match the current implementation
```
<!-- squadron:findings:end -->
