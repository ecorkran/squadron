---
docType: analysis
project: squadron
topic: tech-debt-audit
dateCreated: 20260727
dateUpdated: 20260727
status: not_started
model: claude-sonnet-4-6
---

# Squadron Tech Debt Audit

Independent run. Commit `ad1706f` on `main`. This run does not read or diff against any prior audit file (940, 941) — it is a fresh, uncorrelated sample.

## Executive Summary

- **No auth on the local agent daemon** (`server/daemon.py`, `server/app.py`): both the Unix socket and the `127.0.0.1` HTTP transport accept `spawn`/`task`/`shutdown` calls from any local process with no token or credential check, and `api_key` is transmitted in a plaintext request body (INF-003).
- **Float-typed config keys are broken at the config layer**: `_coerce_value` in `config/manager.py` only handles `int`/`str`, so the three `metrology.*_rate` keys (declared `type_=float`) raise `ValueError` the moment a user runs `sq config set` on them (INF-013).
- **`OpenAICompatibleProvider.validate_credentials` checks only `OPENAI_API_KEY`**, so `sq doctor`/`auth status` reports missing credentials for every profile that authenticates via `OPENROUTER_API_KEY`, `GEMINI_API_KEY`, etc. — a real, user-visible correctness bug (REV-003).
- **Exception handling is the single most common defect class found**, spanning every module: broad `except Exception` clauses that log at WARNING (or not at all) without including the exception object, violating this project's own explicit exception-handling rule (PIPE-006/007, MET-011/013, CLI-019/020, INF-016/021 and others).
- **`executor.py` (1,576 LOC) and `commands/run.py` (1,116 LOC) are god files** doing 4-5 unrelated jobs each; `commands/review.py` is both large (765 LOC) and the single highest-churn file in the repository (40 changes in 6 months) — churn concentration is exactly where this audit's own methodology predicts debt hides, and it does (PIPE-001, CLI-001).
- **The project's own "never scatter comparison values" rule is violated in the newest code**: `metrology/report.py` repeats the `Literal["admissible", "stale-judge-result"]` string pair across 13 sites instead of a shared enum (MET-006), and SDK message-type strings (`"tool_use"`/`"tool_result"`) are duplicated across 4+ consumer files with no shared constant (REV-005).
- **An ephemeral-agent leak exists in the daemon's one-shot task route**: if `send_message` raises after `spawn_agent` succeeds, `shutdown_agent` is never called, leaking a live agent process (INF-004). The corresponding CLI-level `client.request_shutdown()` method calls a server route (`/shutdown`) that doesn't exist and is dead code (INF-008).
- **Two full stub packages exist as dead surface**: `providers/anthropic/` (3-line files, unregistered, untested) and `src/squadron/adk/`, `src/squadron/mcp/` (docstring-only placeholders referencing slices 11/12) ship in the wheel but do nothing (REV-001, INF-019).
- **Test debt concentrates on exactly the code that's changing fastest**: `sq review code` (the CLI's most complex command) has zero CLI-level tests; the daemon's `run_task` HTTP route has zero server-level tests; Codex's rate-limit/timeout path has none of the regression coverage the SDK path recently earned from three consecutive bug-fix commits (CLI-014, INF-009, REV-008).
- **`git.integration_branch`, a config key this project's own CLAUDE.md documents as a first-class workflow concept, is not honored by the diff-resolution code that finds slice merge commits** — `review/git_utils.py` hardcodes `"main"` as the base branch (REV-015).

## Architectural Mental Model

Squadron is a Typer CLI (`sq`/`squadron`) built around three cooperating subsystems. **Pipelines** (`pipeline/`) are YAML-defined multi-step workflows (`executor.py` interprets step graphs — sequential, `each`, `fan_out`, `loop`, `gate`) that dispatch work to LLM **providers** (`providers/`: a `base.py` protocol implemented by an Anthropic-SDK-backed provider, an OpenAI-compatible HTTP provider, and an experimental Codex provider) via **actions** (`pipeline/actions/`: dispatch, review, compact, summary, gate, cf_op). **Reviews** (`review/`) are the original product surface — structured PASS/CONCERNS/FAIL verdicts parsed from LLM output against YAML-defined templates, invoked directly (`sq review slice/tasks/code`) or as a pipeline action. **Metrology** (`metrology/`) is the newest and most actively developed subsystem: it captures review/judge verdicts blind (no effect on production output), computes agreement/dispersion/trend statistics across samples, and — as of the last ~100 commits — runs a self-referential "tech-debt-audit" harness (the very protocol this document follows) with a noise-floor baseline system for calibrating how much its own findings vary run-to-run. A local daemon (`server/`, `client/`) provides persistent named agents (`spawn`/`task`/`list`/`shutdown`) over a Unix socket + localhost HTTP dual transport.

This matches the README's description closely. One divergence worth flagging as a finding rather than assumption: the daemon exposes a `POST /agents/{name}/task` one-shot spawn+message+shutdown route that no documented CLI command actually calls — `sq task` instead calls the persistent-agent `/message` endpoint (INF-020). The architecture is coherent and the module boundaries (pipeline vs. review vs. providers vs. metrology) are real and mostly respected; the debt found here is concentrated in file-level cohesion (a few outsized files doing several jobs) and in error-handling discipline, not in structural layering.

## Findings Table

| ID | Category | File:Line | Severity | Effort | Description | Recommendation |
|---|---|---|---|---|---|---|
| F001 | architectural-decay | `src/squadron/pipeline/executor.py:1-1576` | High | L | God file: mixes placeholder resolution, the source registry, three distinct step-dispatch paths (each/fan_out/loop), and dispatch post-condition checks with no single reason to change. | Extract `resolve_placeholders` + regex helpers, the source registry/parser, and the loop/fan-out executors into separate modules under `pipeline/`; leave `executor.py` as the single-dispatch orchestrator. |
| F002 | architectural-decay | `src/squadron/pipeline/classification.py:265,433` | High | S | `classification.py` imports `resolve_placeholders` from `executor.py` via a local-import guard to dodge a circular dependency — the classifier depends on the executor instead of both depending on a shared utility. | Extract `resolve_placeholders` into `pipeline/placeholder.py`; have both `executor.py` and `classification.py` import from there. |
| F003 | error-handling-observability | `src/squadron/pipeline/loader.py:140` | High | S | `discover_pipelines()` catches `except Exception:` and logs a warning that omits `str(exc)` — a Pydantic validation error's actual cause is discarded, leaving only the filename. | Log `"Skipping invalid pipeline file: %s — %s", yaml_path, exc`. |
| F004 | error-handling-observability | `src/squadron/pipeline/state.py:428-433` | High | S | `load_prior_outputs()` swallows any exception (including `TypeError`) reconstructing an `ActionResult`, silently dropping the result from the returned dict — downstream dispatch steps see "no prior output" with no diagnostic. | Narrow to `except (TypeError, KeyError) as exc` and log the exception, not just the field name. |
| F005 | architectural-decay | `src/squadron/pipeline/executor.py:1509` | Medium | S | `_execute_fan_out_step` raises a bare `ValueError` on an invalid inner step instead of returning a `StepResult(status=FAILED)` like every other failure path in the file — the only path that can crash `execute_pipeline`'s caller unhandled. | Return a `FAILED` `StepResult` matching the pattern at lines 1494-1501/1546-1553. |
| F006 | test-debt | `src/squadron/pipeline/executor.py:908-976` (`_step_needs_sdk`, `_connect_lazy_session`) | High | M | The mid-run lazy-SDK-session hook is only exercised via a CLI-layer test (`tests/cli/commands/test_run_pipeline_lazy.py`); it has no unit test in `tests/pipeline/`. | Add `tests/pipeline/test_executor.py` coverage for `_step_needs_sdk` branch conditions and the lazy-hook injection path. |
| F007 | consistency-rot | `src/squadron/pipeline/actions/dispatch.py:186-188,306-308,312-314`, `actions/review.py:124-125`, `actions/cf_op.py:99-101` | Medium | S | The `model`/`step_model` extraction idiom (`str(context.params["x"]) if "x" in context.params else None`) is duplicated verbatim five times across three files; `dispatch.py`'s own `_resolve_model` helper exists but two of its three call sites re-inline the logic instead of calling it. | Extract one helper (e.g. in `actions/protocol.py`) and use it at all five sites, including `dispatch.py`'s own duplicated inlines. |
| F008 | type-contract-debt | `src/squadron/pipeline/schema.py:49` vs `models.py:80` | Medium | S | `PipelineSchema.params` is typed `dict[str, str]`; `PipelineDefinition.params` is `dict[str, object]`. `to_definition()` widens silently, so non-string params validate at the model layer but are rejected by the schema layer with no explanation of the mismatch. | Pick one contract (YAML params are always strings) and align both types; document the decision. |
| F009 | architectural-decay | `src/squadron/pipeline/executor.py:652-673` | Medium | S | Action-module registration happens via inline `import … as _a_X` statements inside `execute_pipeline()`'s body — adding a new action module requires editing this function directly, unlike the symmetric `bootstrap_step_types()` pattern already used for step types. | Add a matching `bootstrap_actions()` in `actions/__init__.py`, called once from `execute_pipeline()`. |
| F010 | test-debt | `src/squadron/pipeline/tests/test_compact_compose_integration.py:44,181` | Medium | S | Two integration tests covering the summarize→compact→restore compose pattern are skipped with `"fixture pipeline step count mismatch; tracked for fix in slice 248"` — an apparently stale reference on a critical, complex state-management path. | Verify slice 248's status; either fix the fixture and un-skip, or replace the skip comment with a tracked issue reference. |
| F011 | performance-resource | `src/squadron/pipeline/state.py:266,328,343,360` | Medium | M | `StateManager` does a full load→mutate→atomic-write round-trip on every single step callback, compact-summary record, and pool-selection log — a 20-step pipeline with 5 pool selections performs 25+ full JSON parse/serialize cycles on the same file with no in-memory caching. | Hold an in-memory `RunState` slot keyed by `run_id`, flushing to disk on each mutation instead of re-reading. |
| F012 | performance-resource | `src/squadron/pipeline/actions/review.py:111` | Medium | S | `load_all_templates()` is called unconditionally inside `_review()`, i.e. on every review-action execution rather than once at session startup — a 5-review-step loop calls it 5+ times. | Call once in `execute_pipeline()` alongside `bootstrap_step_types()`, or guard with a module-level loaded flag. |
| F013 | architectural-decay | `src/squadron/pipeline/prompt_renderer.py:380-416` | Medium | S | `ActionType.GATE` is a registered action type but has no entry in the `_BUILDERS` map used for prompt-only rendering — a `gate` step in prompt-only mode falls back to a generic `"Execute gate action"` placeholder with no rendering of its `judge_from`/`review_from` parameters. | Add a `_render_gate()` builder, or add a comment explaining why gate is intentionally excluded from prompt-only rendering. |
| F014 | type-contract-debt | `src/squadron/pipeline/loader.py:249` | Low | S | `_validate_review_template()` accepts a `get_template_fn` parameter but never uses it (confirmed independently by `vulture --min-confidence 80`); the function calls `get_template` directly instead. | Remove the dead parameter from the signature and all three call sites. |
| F015 | type-contract-debt | `src/squadron/pipeline/actions/summary.py:234,242` | Low | S | Two `assert` statements are used for type narrowing in production code (`assert context.sdk_session is not None`); assertions are elided under `python -O`, silently removing the invariant check in optimized mode. | Replace with explicit `if x is None: raise RuntimeError(...)` guards. |
| F016 | documentation-drift | `src/squadron/pipeline/state.py:102-108` | Low | S | `CompactSummary.key` docstring says "Slice 159 will extend this key with a branch suffix" — a stale forward reference to a slice that has either shipped or been dropped. | Update the docstring to reflect current behavior, or replace with a tracked `TODO(slice-NNN)` if still pending. |
| F017 | architectural-decay | `src/squadron/cli/commands/run.py:753-1116` | High | L | The `run()` Typer handler is 364 lines covering 8 distinct execution branches (list/status/validate/explain/dry-run/prompt-only/resume/fresh-run), each independently loading and validating the pipeline. | Extract each branch into a named `_handle_*` function (matching the existing `_handle_explain` pattern); reduce `run()` to a ~50-line dispatcher. |
| F018 | error-handling-observability | `src/squadron/cli/commands/review.py:358-363` | High | S | `_run_review_command`'s blanket `except Exception as exc` around `asyncio.run(_execute_review(...))` re-raises as `typer.Exit(1)` with only `str(exc)` — no `logger.exception()` call, so stack traces are silently discarded for the CLI's core command. | Log at ERROR with the exception before re-raising as `Exit(1)`; exclude `KeyboardInterrupt`/`SystemExit` from the catch. |
| F019 | test-debt | `src/squadron/cli/commands/review.py` (`review code`) | High | M | Zero CLI-level tests exist for `sq review code` — the most complex review subcommand (git-root detection, dual rules-loading paths, `--files`/`--diff`/slice-number resolution, language auto-detection). | Add `tests/cli/test_review_code.py` covering the diff path, files path, `--no-rules`, missing-slice error, and FAIL→exit-2. |
| F020 | test-debt | `src/squadron/cli/commands/review.py:647-655` (`--fan`) | High | S | `--fan` is a documented-as-"reserved, not yet functional" option with no test asserting the warning fires and the flag is otherwise a no-op — a latent trap if a future refactor accidentally activates it. | Add a test invoking `--fan` and asserting the warning appears with no behavioral change; or remove/hide the option until implemented. |
| F021 | architectural-decay | `src/squadron/cli/commands/run.py:679-683` vs `run.py:1009` | High | S | Resume model-resolution logic is duplicated with subtly different semantics between `_handle_prompt_only_next` and the `--resume` branch — one unconditionally calls `str()` on `state.params.get("model")` even when `model_override` is set, risking a literal `"None"` string. | Extract `_resolve_resume_model(model_override, state_params)` and use it in both branches; guard against `None`. |
| F022 | consistency-rot | `src/squadron/cli/commands/review.py:156-163` vs `metrology.py:92-102` | Medium | S | Two functions both named `_resolve_cwd()` have different semantics — `review.py`'s falls back to `get_config("cwd")`, `metrology.py`'s intentionally does not. Identical names inviting a future copy-paste bug. | Rename one (e.g. `_resolve_repo_root`) to make the semantic difference visible at the call site. |
| F023 | consistency-rot | `src/squadron/cli/commands/review.py:454,529,622,750` | Medium | S | `Verdict.UNKNOWN` has no explicit exit-code branch in any review subcommand and falls through to exit 0 — indistinguishable from PASS at the shell level, contradicting the documented PASS/CONCERNS/FAIL exit-code contract. | Add an explicit `UNKNOWN` branch in each review command; decide and document its exit code. |
| F024 | type-contract-debt | `src/squadron/cli/commands/run.py:90-122` (`_assemble_params`) | Medium | S | `--param key=` (empty value after `=`) passes through as a valid empty-string param with no validation, likely not the user's intent. | Validate that the value portion is non-empty, or explicitly document that empty values are permitted. |
| F025 | error-handling-observability | `src/squadron/cli/commands/spawn.py:101-103` | Medium | S | `except Exception as exc: rprint(...); raise typer.Exit(1)` swallows all daemon-connection errors with no `logger.exception()` call — a JSON decode error or connection timeout becomes a single red line with no trace. | Log at ERROR before re-raising as `Exit(1)`. |
| F026 | error-handling-observability | `src/squadron/cli/commands/run.py:228-238` | Medium | S | `except BaseException:` in `_run_pipeline()` catches `KeyboardInterrupt`/`SystemExit`/`GeneratorExit` to run `state_mgr.finalize()` before re-raising — correctly re-raises, but the breadth of `BaseException` is broader than the stated intent needs. | Narrow to `except (Exception, KeyboardInterrupt):` with a comment explaining why `KeyboardInterrupt` is included. |
| F027 | documentation-drift | `docs/COMMANDS.md:14` | Medium | S | Documents `sq review arch <FILE> --against <ARCH_DOC>`, but `review_arch` (`review.py:458`) takes no `--against` parameter — the arch template reviews a document standalone. | Correct COMMANDS.md; remove the `--against` example from the arch section. |
| F028 | security-hygiene | `src/squadron/cli/app.py:33` | Low | S | `load_dotenv(dotenv_path=Path.cwd() / ".env")` runs unconditionally at module import time, mutating `os.environ` as a side effect of merely importing `squadron`, not just running `sq`. | Guard with a `__main__`/callback check so `.env` loading only fires on actual CLI invocation. |
| F029 | security-hygiene | `src/squadron/cli/commands/doctor_checks.py:103`, `providers/auth.py:31,54` | Low | S | `AuthStrategy.active_source` is printed directly in `doctor`/`auth status` output with no type contract preventing an implementation from setting it to a credential value rather than a source descriptor. | Document (and optionally assert) that `active_source` must never hold the credential itself. |
| F030 | performance-resource | `src/squadron/cli/commands/metrology.py:801-833` (`audit_run`) | Medium | M | Sequential `asyncio.run()` per project in a multi-project audit campaign creates/destroys an event loop per project and only checks the rate-limit early-exit condition after each full run completes. | Acceptable at current scale; note as a candidate for a single-event-loop sequential-await refactor if campaign sizes grow. |
| F031 | architectural-decay | `src/squadron/metrology/audit.py:1-789` | High | M | Single file owns five distinct concerns: error classes, git preflight, skill/prompt resolution, config resolution, and the async execution harness — above the project's ~300-line file guideline despite each piece being individually coherent. | Extract `preflight_project` + git helpers into `audit_preflight.py`; extract skill/prompt construction into `audit_skill.py`. |
| F032 | consistency-rot | `src/squadron/metrology/report.py:61,101,136,152,168,177,223,225,230,276,278,281,286` | High | S | The `admissible: Literal["admissible", "stale-judge-result"]` field's two values appear as bare string literals in 13 places in one file — a direct violation of this project's own CLAUDE.md rule against scattering comparison values across code. | Replace with a two-value `StrEnum` (e.g. `AdmissibilityStatus`) referenced everywhere instead of the bare literals. |
| F033 | consistency-rot | `src/squadron/review/review_client.py:152`, `pipeline/sdk_session.py:168`, `pipeline/summary_oneshot.py:82`, `metrology/audit.py:538-543` | Medium | M | The SDK message-type strings `"tool_use"`/`"tool_result"` are scattered across 4+ consumer files as inline literals with no shared constant (unlike `SDK_RESULT_TYPE`, which is centralized in `core/models.py`). | Define `SDK_TOOL_USE_TYPE`/`SDK_TOOL_RESULT_TYPE` alongside `SDK_RESULT_TYPE` in `core/models.py`; use everywhere. |
| F034 | error-handling-observability | `src/squadron/metrology/audit.py:688-704` | Medium | S | The generic `except Exception as exc:` branch for stream failures logs at WARNING, not ERROR, despite this project's explicit rule that an unclassified broad catch must re-raise-after-ERROR-log or carry a specific-exception justification comment — the existing comment justifies the catch but not the log level. | Change the log level to ERROR for the unclassified-exception branch (the rate-limit/timeout branches above it are correctly WARNING). |
| F035 | type-contract-debt | `src/squadron/metrology/audit_report.py:85-93,137` | Medium | S | `baseline_report` builds a `BaselineExclusionSummary` Pydantic model then imperatively mutates it (`excluded.groups_without_floor += 1`, then `excluded.total_excluded = excluded.groups_without_floor` far away at line 137) instead of computing all fields before construction. | Accumulate as local counters during the loop; construct the model once with all values known. |
| F036 | architectural-decay | `src/squadron/metrology/audit.py:91-107` vs `errors.py`, `audit_variance.py` | Medium | S | Audit-related exception classes are scattered across three modules (`audit.py`, `errors.py`, `audit_variance.py`) with no consistent placement rule — callers must know which module to import from per exception type. | Consolidate `AuditSkillError`, `AuditPreflightError`, `AuditVarianceError` into `errors.py`. |
| F037 | architectural-decay | `src/squadron/metrology/audit.py:41` | Medium | S | `audit.py` and `tests/metrology/test_audit_skill_sync.py` both import the private `_resolve_bundled` function directly from `skills/resolver.py` — two callers depending on an explicitly private API. | Expose a public `resolve_bundled(pack_name)` in `skills/resolver.py`; update both call sites. |
| F038 | test-debt | `src/squadron/metrology/report.py:344-378` (`trend_report`, `_bucket_label`) | Medium | M | No test asserts a sample with a known, timezone-aware `captured_at` lands in exactly the expected time bucket — `_bucket_label` uses `strftime`/`isocalendar()` with no explicit timezone handling, so a timezone bug would silently misbucket samples. | Add a test with a timezone-aware datetime asserting the correct bucket label, including a case that would differ under naive local-time bucketing. |
| F039 | test-debt | `src/squadron/metrology/capture.py` / `tests/metrology/test_capture.py` | Medium | M | No test exercises `record_sample` exactly at the sample-budget ceiling to confirm the second call at the boundary correctly refuses and writes nothing — budget enforcement is a correctness property, not just an optimization. | Add a boundary test: call `record_sample` at the exact budget limit, then again, asserting the second call reports `budget_reached=True` and persists nothing. |
| F040 | performance-resource | `src/squadron/metrology/store.py:195,259,284,328,348` | Medium | M | Every `list_*` query method (and `count_samples`, which calls `list_samples` then takes `len()`) performs a full glob-and-deserialize scan of the store on every call, including on every `record_sample` invocation. | Implement `count_samples` as a direct filename-prefix glob count, avoiding full deserialization just to count; document the O(n) scan's acceptable-scale assumption. |
| F041 | error-handling-observability | `src/squadron/metrology/store.py:197,263,288,331` | Low | S | The four `list_*` methods collapse `OSError`/`ValueError`/`SchemaVersionError` into one WARNING that logs only the file path, not which exception type occurred — a schema-version mismatch is indistinguishable from a corrupt file in the log. | Include `type(exc).__name__` and the message in the warning. |
| F042 | consistency-rot | `src/squadron/metrology/discovery.py:24` vs `identity.py:34` | Low | S | The frontmatter key `"reviewType"` is defined independently as `_FM_REVIEW_TYPE` in `discovery.py` and `_FM_TEMPLATE` in `identity.py` — the same on-disk field name defined twice in one package. | Export one public constant from `identity.py`; import it in `discovery.py`. |
| F043 | type-contract-debt | `src/squadron/metrology/report.py:201` | Low | S | `assert isinstance(value, int)` used as a runtime type-narrowing crutch after a value already typed `int` by `get_typed_config`'s signature — elided under `python -O`. | Remove the assert; fix `get_typed_config`'s type annotation if it's actually wrong. |
| F044 | architectural-decay | `src/squadron/providers/anthropic/provider.py:1-3`, `agent.py:1-3` | High | S | Stub-only provider directory (docstring only, no implementation), unregistered in `providers/loader.py`, untested — creates false confidence that a third native provider exists. | Delete if not planned, or document as an explicit placeholder for a named future slice. |
| F045 | type-contract-debt | `src/squadron/providers/openai/provider.py:64-70` | High | S | `validate_credentials` hardcodes `os.environ.get("OPENAI_API_KEY")` instead of using the profile's configured auth strategy — every non-`OPENAI_API_KEY` profile (OpenRouter, Gemini, OAuth) reports "invalid credentials" even when correctly configured. Confirmed by direct read. | Replace with `ApiKeyStrategy.from_config(...).is_valid()`, matching `resolve_auth_strategy_for_profile`'s pattern. |
| F046 | test-debt | `src/squadron/providers/codex/agent.py` / `tests/providers/codex/` | High | M | Zero tests cover rate-limiting or timeout behavior in `CodexAgent`, despite three consecutive recent bug-fix commits ("absorb rate-limit events", "reset the rate-limit budget", "stop treating usage-status events as throttling") — all fixes landed on the SDK path only; Codex has none of that regression coverage. | Add tests for `handle_message`'s exception-wrapping behavior and post-error agent state, mirroring the SDK path's coverage. |
| F047 | consistency-rot | `src/squadron/providers/openai/provider.py:39` | Medium | S | `create_agent` calls `resolve_auth_strategy(config, profile=None)` even though the caller already encoded profile info into `config.credentials` — a working but undocumented indirection (profile → credentials dict → strategy) that's easy to break by a future contributor who "fixes" the apparent bug. | Add an inline comment documenting the indirection, or make it explicit by adding a `profile` parameter to the `create_agent` protocol. |
| F048 | error-handling-observability | `src/squadron/providers/loader.py:23-24` | Medium | S | `ensure_provider_loaded` swallows `ImportError` broadly with a comment deferring to `get_provider`'s `KeyError` — this conflates "optional dependency missing" (expected) with "syntax error in the provider module" (a real bug that would be silently hidden). | Catch `ModuleNotFoundError` specifically; let other `ImportError` subclasses propagate. |
| F049 | error-handling-observability | `src/squadron/providers/codex/agent.py:72-73,82-83` | Medium | S | `handle_message`'s broad catch wraps everything (including timeouts) into one `ProviderError`, losing type fidelity; `shutdown()`'s bare `except Exception: pass` has no justification comment (the equivalent SDK-agent handler does). | Map known exception types before the broad catch in `handle_message`; add a justification comment to `shutdown()` matching the SDK agent's. |
| F050 | dependency-config-debt | `pyproject.toml:85` | Medium | S | `src/squadron/providers/codex/agent.py` is excluded from pyright strict mode with no inline comment explaining why, risking the exclusion silently widening to mask unrelated type errors over time. | Add a comment naming the specific cause (untyped `codex_app_server` SDK) next to the exclusion. |
| F051 | architectural-decay | `src/squadron/providers/base.py:13-19` | Medium | S | `ProviderType` has no `CODEX` value — `CodexProvider.provider_type` returns `ProviderType.OPENAI_OAUTH`, conflating a provider identity with a profile name; any future code branching on `provider_type` can't distinguish Codex from a hypothetical different OAuth provider. | Add `CODEX = "codex"` to the enum; return it from `CodexProvider`. |
| F052 | error-handling-observability | `src/squadron/review/git_utils.py:71,149` | Medium | S | `_find_merge_commit`/`_find_slice_branch` hardcode `"main"` as the base branch, ignoring this project's own `git.integration_branch` config key — a project configured with an integration branch gets an incorrect diff range for merged slices. | Accept a `base_branch` parameter sourced from `cf config get git.integration_branch` at the call site. |
| F053 | security-hygiene | `src/squadron/providers/codex/auth.py:47-48` | Low | S | `OAuthFileStrategy.is_valid()` only checks that `~/.codex/auth.json` exists as a file — no content validation (non-empty, valid JSON) — so a corrupt file surfaces as an opaque SDK-level error instead of a clear auth error. | Attempt a `json.loads` read in `get_credentials()`; raise `ProviderAuthError` with a clear message on failure. |
| F054 | type-contract-debt | `src/squadron/providers/profiles.py:116` | Low | S | `load_user_profiles` casts `auth_type` to `str` without validating it against `AuthType`'s known values — an invalid value fails much later, at `resolve_auth_strategy` call time, not at config-load time. | Validate `auth_type` against `{a.value for a in AuthType}` at load time with a clear error. |
| F055 | security-hygiene | `src/squadron/server/daemon.py` + `server/app.py` | High | S | Both daemon transports (Unix socket and `127.0.0.1` HTTP) accept `spawn`/`task`/`shutdown` requests with **no authentication token or credential check** (confirmed: no auth middleware in `app.py`, no token check anywhere in the route handlers), and `api_key` values are carried in plaintext request bodies over the HTTP transport. | Add a shared-secret bearer token generated at daemon start (e.g. stored at `~/.squadron/daemon.token`) required on the HTTP transport; document that the Unix socket relies on OS-level filesystem permissions as its access control. |
| F056 | error-handling-observability | `src/squadron/server/routes/agents.py:174-203` | High | S | `run_task` (spawn→send_message→shutdown) doesn't catch `AgentAlreadyExistsError` (500 instead of 409) and, if `send_message` raises after a successful spawn, never calls `shutdown_agent` — the ephemeral agent process leaks. | Wrap the sequence so any post-spawn exception triggers `shutdown_agent` in a `finally`; add the missing exception→status-code mappings already present on the sibling `spawn_agent` route. |
| F057 | type-contract-debt | `src/squadron/config/manager.py:54-61` (`_coerce_value`) | High | S | `_coerce_value` only handles `int` and `str`, raising `ValueError("Unsupported config type")` for `float` — but three real config keys (`metrology.graduate_match_rate`, `metrology.tighten_match_rate`, `metrology.residual_sample_rate`) are declared `type_=float`, so `sq config set` on any of them fails. Confirmed by direct read. | Add a `float` branch to `_coerce_value`; add a round-trip test for a float key. |
| F058 | architectural-decay | `src/squadron/server/engine.py:24-28` vs `providers/loader.py:11-15` | Medium | S | `_PROVIDER_MODULES` (the provider-alias → module-name map) is duplicated verbatim between `engine.py` and `providers/loader.py` — a new alias added to one silently diverges from the other. | Delete the local copy in `engine.py`; call `providers.loader.ensure_provider_loaded` instead. |
| F059 | architectural-decay | `src/squadron/server/routes/agents.py:123` | Medium | S | The `GET /agents/{name}` route reads `engine.registry._configs` directly — a private attribute reach-through, acknowledged by an inline comment as awkward. | Add `SquadronEngine.get_agent_info(name)` returning a complete public `AgentInfo` without exposing internal storage. |
| F060 | type-contract-debt | `src/squadron/server/routes/agents.py:94` | Medium | S | `GET /agents/?state=bogus` passes the raw query string to `AgentState("bogus")`, which raises `ValueError` uncaught — FastAPI returns a 500 instead of a 422 for a client input error. | Type the `state` query parameter as `AgentState \| None` directly so FastAPI validates it, or catch `ValueError` and return a 422. |
| F061 | architectural-decay | `src/squadron/client/http.py:139-141` | Medium | S | `DaemonClient.request_shutdown()` POSTs to `/shutdown`, a route that does not exist on the server (confirmed against `server/routes/`) — the method is unreachable dead code; the real `sq serve --stop` path uses `SIGTERM` directly and never calls this method. | Either implement a `/shutdown` route that sets `should_exit` on both uvicorn servers, or delete `request_shutdown` from the client. |
| F062 | documentation-drift | `src/squadron/config/keys.py:89-96` (`compact.instructions`) | Medium | S | `compact.instructions` is registered with a description saying it "overrides `compact.template`", but `summary_instructions.py` only ever reads `compact.template` — the override is never implemented, so setting this key silently does nothing. | Implement the override check in `summary_instructions.py`, or remove the key and its misleading description. |
| F063 | documentation-drift | `src/squadron/server/routes/agents.py` vs `cli/commands/task.py` | Medium | S | The `POST /agents/{name}/task` server route (one-shot spawn+message+shutdown) is never called by any documented CLI command — `sq task` instead calls the persistent-agent `/message` endpoint. The route is either unfinished or accidentally unwired. | Clarify intent with the maintainer; either wire a CLI command to it or remove the unreachable route. |
| F064 | performance-resource | `src/squadron/server/daemon.py:56-76` (`write_pid_file`) | Medium | M | `write_pid_file()` runs before the uvicorn `TaskGroup` starts; if the socket bind fails before the `TaskGroup` context is entered, the surrounding `finally` (which calls `remove_pid_file`) may not execute, leaving a stale PID file. | Write the PID file only after both servers have successfully bound, or wrap the write itself in its own try/finally. |
| F065 | security-hygiene | `src/squadron/skills/resolver.py:58-66` (`clone_github`) | Medium | M | `subprocess.run(["git", "clone", ..., url, ...])` builds `url` from a user-provided `repo_spec` string with no format validation before use. | Validate `repo_spec` against `^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$` before constructing the clone URL; reject non-matching input. |
| F066 | test-debt | `src/squadron/server/routes/agents.py` (`run_task`) / `tests/server/` | Medium | S | No server-level test exists for `POST /agents/{name}/task` — none of its error paths (auth failure, name collision, mid-flight leak per F056) are exercised at the HTTP boundary. | Add route-level tests for the happy path and each documented error path, including a post-call assertion that no agent remains after an exception. |
| F067 | security-hygiene | `src/squadron/server/app.py:18` | Low | S | `FastAPI(title=...)` uses default settings, which serve Swagger UI (`/docs`) and OpenAPI schema on the daemon's HTTP transport — unnecessary local attack surface for a machine-local daemon. | Pass `docs_url=None, redoc_url=None, openapi_url=None` to the `FastAPI()` constructor. |
| F068 | architectural-decay | `src/squadron/adk/`, `src/squadron/mcp/` | Low | S | Both packages contain only placeholder docstrings referencing slices 11/12, are imported nowhere in the codebase, and ship in the built wheel. | Remove if the referenced slices were abandoned; otherwise track as explicit open work. |
| F069 | performance-resource | `src/squadron/models/aliases.py:160-166,195` | Low | S | `resolve_model_alias` and `estimate_cost` both call `get_all_aliases()` on every invocation, which reads two TOML files from disk each time — a hot path on every model resolution. | Cache `get_all_aliases()`'s result at module level, invalidated on `models.toml` path change, or document the repeated I/O as an accepted cost. |
| F070 | consistency-rot | `src/squadron/config/keys.py:49-68` (`default_model_*`) | Low | S | Four `default_model_{template}` config keys are only ever accessed via the dynamically-constructed string `f"default_model_{template_name}"` (`review.py:275`), bypassing the key registry's static validation; an unexpected `template_name` raises `KeyError`, silently swallowed at the call site. | Enumerate valid per-template keys explicitly and validate `template_name` against that set before construction. |
| F071 | error-handling-observability | `src/squadron/core/agent_registry.py:119` | Low | S | `shutdown_agent`'s exception log uses `str(agent)` (a generic object repr) rather than the agent's name, which is already in scope, making the WARNING log less useful for identifying which agent failed. | Log `name` instead of `str(agent)`. |

## Top 5 — Fix These First

**1. No auth on the local daemon (F055).** Any local process — including a compromised dependency in an unrelated project running on the same machine — can spawn agents, read conversation history, or drive arbitrary prompts through a squadron daemon with zero credential check.
```python
# server/daemon.py — start_server()
DAEMON_TOKEN = _load_or_create_token()  # ~/.squadron/daemon.token, 0600

# server/app.py — create_app()
app.add_middleware(BearerTokenMiddleware, token=DAEMON_TOKEN)  # HTTP transport only

# client/http.py — DaemonClient
headers = {"Authorization": f"Bearer {_read_token()}"}
```

**2. Float config keys are broken (F057).** This isn't a style nit — `sq config set metrology.graduate_match_rate 0.85` raises today. Any documented float config key is unusable.
```python
def _coerce_value(key: str, raw_value: str) -> object:
    key_def = CONFIG_KEYS[key]
    if key_def.type_ is int:
        return int(raw_value)
    if key_def.type_ is float:
        return float(raw_value)
    if key_def.type_ is str:
        return raw_value
    raise ValueError(f"Unsupported config type: {key_def.type_}")
```

**3. `validate_credentials` reports false negatives for non-OpenAI-key profiles (F045).** `sq doctor` and `auth status` are the tools users run to debug exactly this class of problem, and they lie for every profile except the OpenAI default.
```python
async def validate_credentials(self) -> bool:
    try:
        __import__("openai")
    except ImportError:
        return False
    strategy = resolve_auth_strategy_for_profile(self._profile)
    return strategy.is_valid()
```

**4. `executor.py` and `run.py` god files (F001, F017).** Both are the largest files in their respective layers, both mix orchestration with dispatch-branch logic, and both are actively changing — every future step-type or subcommand addition compounds the cohesion problem. Extract along the seams already identified: placeholder resolution / source registry / loop-executor / fan-out-executor out of `executor.py`; one `_handle_*` function per `run()` branch.

**5. Ephemeral-agent leak + dead shutdown route (F056, F061).** These are two ends of the same gap: the daemon's one-shot task route can leak a spawned agent on error, and the client method meant to gracefully shut the daemon down calls a route that was never implemented. Both point at the daemon lifecycle surface having less test/design attention than the CLI or pipeline layers — unsurprising, since `server/` is by far the least-churned major module in the last 6 months, but it's also the module with the most privilege (spawning processes, holding credentials in memory) and the least test coverage (F066).

## Quick Wins

- [ ] F057 — Add `float` branch to `config/manager.py:_coerce_value` (S, fixes a currently-broken documented feature)
- [ ] F045 — Fix `validate_credentials` to check the profile's actual auth strategy, not a hardcoded env var (S, fixes false-negative `sq doctor` output)
- [ ] F014 — Remove dead `get_template_fn` parameter in `pipeline/loader.py:249` (S, vulture-confirmed)
- [ ] F061 — Delete `DaemonClient.request_shutdown()` or implement the `/shutdown` route it calls (S)
- [ ] F062 — Implement or remove the unused `compact.instructions` config override (S)
- [ ] F003/F004 — Include `exc` in the two silently-swallowed pipeline loader/state warnings (S each)
- [ ] F023 — Add an explicit `Verdict.UNKNOWN` exit-code branch to the four review commands (S)
- [ ] F067 — Disable Swagger/OpenAPI docs endpoints on the production daemon (S)
- [ ] F032 — Replace the 13-site `Literal["admissible", "stale-judge-result"]` string pair with an enum (S)
- [ ] F044 — Delete (or explicitly document) the unregistered, untested `providers/anthropic/` stub (S)
- [ ] F068 — Delete the unused `adk/`/`mcp/` placeholder packages, or open tracked issues for them (S)

## Things That Look Bad But Are Actually Fine

- **`sdk_session.py`'s bare `except Exception: pass` in `disconnect()`.** The docstring explicitly says "best-effort — ignores errors" for a teardown-only network-channel close. This satisfies the project's rule (b): specific justification for swallowing.
- **`agent_registry.py`'s broad catches in `shutdown_agent`/`shutdown_all`.** One re-raises after logging (rule a); the other is a best-effort teardown loop that collects failures into a report rather than aborting mid-shutdown — correct behavior for a "stop everything, report what didn't stop cleanly" operation.
- **The five-format `_FINDING_RE` regex alternation in `review/parsers.py`.** Looks like a parsing arms race at first glance, but each alternate format corresponds to an observed real model-output style, and the test suite backs each with real fixtures — not speculative generality.
- **`providers/openai/agent.py`'s `async def handle_message` implementing a `def ... -> AsyncIterator[Message]` protocol.** A structural type mismatch on paper, but an `async def` containing `yield` is an async generator, a legitimate subtype of `AsyncIterator` — the code is correct, only the Protocol's literal signature is stylistically inconsistent with its implementations.
- **`review_client.py`'s `sdk_type` filtering, which reads like a provider-specific branch in supposedly provider-agnostic code.** It's actually a Message-metadata key check that's a no-op for any provider that doesn't set it — genuinely provider-agnostic, just non-obviously so without reading the comment above it.
- **`pid.py`'s `except (ValueError, OSError): return None` in `read_pid_file`.** `None` is the documented contract for "no daemon running" (stale/corrupt PID file), and the sole consumer (`is_daemon_running`) handles it correctly. Not a silent swallow — it's the intended interface.
- **No CORS middleware on the FastAPI daemon app.** Correct: the daemon is `127.0.0.1`-only and meant for local CLI/test callers, not browser clients. Absence of CORS handling is the right call here (independent of the missing-auth finding, F055, which is a separate concern).
- **`ruff check` and `pyright --strict` both report zero issues repo-wide.** Given `strict` mode and a 24.7k-line codebase, this is a genuinely clean baseline — not a case of the tools being under-configured; the `[tool.pyright]` config in `pyproject.toml` sets `typeCheckingMode = "strict"` with only one narrow, commented-adjacent exclusion (`providers/codex/agent.py`, see F050).

## Open Questions for the Maintainer

1. **`providers/anthropic/` (F044):** Reserved for a specific planned slice, or safe to delete outright?
2. **Slice 248 (F010):** Are the two skipped compact/rotate integration tests still blocked, or did the underlying fixture mismatch get fixed elsewhere and the skip just never got removed?
3. **`loop.strategy` (pipeline):** `LoopConfig.strategy` is parsed and validated but ignored at runtime with a `"not implemented"` warning at two call sites in `executor.py`. Is there a tracking slice for this, and should the warning be louder (or the field rejected at validation time) until it's implemented?
4. **`git.integration_branch` (F052):** Is this config key actually set to a non-default value in any current usage of this repo? If yes, `review/git_utils.py`'s hardcoded `"main"` is producing wrong diff ranges today, not just hypothetically.
5. **`POST /agents/{name}/task` (F063):** Intentionally unwired for future use, or a slip where `sq task` should have called it instead of `/message`?
6. **`prior_outputs` key collision (pipeline/state.py):** Two steps of the same action type both write to `f"{action_type}-{idx}"`, with the second overwriting the first — acknowledged in a nearby comment as "lossy." `step_outputs` was added as a workaround for the gate use case specifically. Is the plan to migrate all consumers off `prior_outputs`, or fix the underlying key scheme?

<!-- squadron:findings:begin v1 -->
```yaml
findings:
  - id: F001
    category: architectural-decay
    location: src/squadron/pipeline/executor.py:1
    severity: High
    effort: L
    summary: executor.py is 1576 lines mixing placeholder resolution, the source registry, three distinct step-dispatch paths, and dispatch post-condition checks with no single reason to change
  - id: F002
    category: architectural-decay
    location: src/squadron/pipeline/classification.py:265
    severity: High
    effort: S
    summary: classification.py imports resolve_placeholders from executor.py via a local-import guard to avoid a circular dependency, a layering violation
  - id: F003
    category: error-handling-observability
    location: src/squadron/pipeline/loader.py:140
    severity: High
    effort: S
    summary: discover_pipelines catches broad Exception and logs a warning that omits the exception detail, hiding the real parse failure cause
  - id: F004
    category: error-handling-observability
    location: src/squadron/pipeline/state.py:428
    severity: High
    effort: S
    summary: load_prior_outputs swallows exceptions reconstructing ActionResult silently dropping the result with no diagnostic
  - id: F005
    category: architectural-decay
    location: src/squadron/pipeline/executor.py:1509
    severity: Medium
    effort: S
    summary: _execute_fan_out_step raises a bare ValueError on invalid inner step instead of returning a FAILED StepResult like every other failure path
  - id: F006
    category: test-debt
    location: src/squadron/pipeline/executor.py:908
    severity: High
    effort: M
    summary: the mid-run lazy-SDK-session hook has no pipeline-layer unit test, only an indirect CLI-layer test
  - id: F007
    category: consistency-rot
    location: src/squadron/pipeline/actions/dispatch.py:186
    severity: Medium
    effort: S
    summary: model and step_model extraction idiom duplicated verbatim five times across three action files instead of using the existing helper
  - id: F008
    category: type-contract-debt
    location: src/squadron/pipeline/schema.py:49
    severity: Medium
    effort: S
    summary: PipelineSchema.params is typed dict[str, str] while PipelineDefinition.params is dict[str, object], a silent widening mismatch between schema and model layers
  - id: F009
    category: architectural-decay
    location: src/squadron/pipeline/executor.py:652
    severity: Medium
    effort: S
    summary: action-module registration happens via inline imports inside execute_pipeline's body instead of a symmetric bootstrap function like step types use
  - id: F010
    category: test-debt
    location: tests/pipeline/test_compact_compose_integration.py:44
    severity: Medium
    effort: S
    summary: two integration tests for the compact/rotate compose pattern are skipped citing a stale slice reference for an unresolved fixture mismatch
  - id: F011
    category: performance-resource
    location: src/squadron/pipeline/state.py:266
    severity: Medium
    effort: M
    summary: StateManager performs a full load-mutate-atomic-write round trip on every step callback and pool selection with no in-memory caching
  - id: F012
    category: performance-resource
    location: src/squadron/pipeline/actions/review.py:111
    severity: Medium
    effort: S
    summary: load_all_templates is called unconditionally on every review action execution rather than once at session startup
  - id: F013
    category: architectural-decay
    location: src/squadron/pipeline/prompt_renderer.py:380
    severity: Medium
    effort: S
    summary: ActionType.GATE has no entry in the prompt-only rendering builder map, falling back to a generic unhelpful placeholder
  - id: F014
    category: type-contract-debt
    location: src/squadron/pipeline/loader.py:249
    severity: Low
    effort: S
    summary: _validate_review_template accepts an unused get_template_fn parameter, confirmed dead by vulture
  - id: F015
    category: type-contract-debt
    location: src/squadron/pipeline/actions/summary.py:234
    severity: Low
    effort: S
    summary: assert statements used for type narrowing in production code are elided under python -O, silently removing the invariant check
  - id: F016
    category: documentation-drift
    location: src/squadron/pipeline/state.py:102
    severity: Low
    effort: S
    summary: CompactSummary.key docstring references a stale forward-looking slice number that has since shipped or been dropped
  - id: F017
    category: architectural-decay
    location: src/squadron/cli/commands/run.py:753
    severity: High
    effort: L
    summary: the run() Typer handler is 364 lines covering eight distinct execution branches each independently loading and validating the pipeline
  - id: F018
    category: error-handling-observability
    location: src/squadron/cli/commands/review.py:358
    severity: High
    effort: S
    summary: blanket except Exception around the core review execution re-raises as typer.Exit with no logger.exception call, discarding the stack trace
  - id: F019
    category: test-debt
    location: src/squadron/cli/commands/review.py:1
    severity: High
    effort: M
    summary: zero CLI-level tests exist for sq review code, the most complex review subcommand with git-root detection and multi-source resolution
  - id: F020
    category: test-debt
    location: src/squadron/cli/commands/review.py:647
    severity: High
    effort: S
    summary: the documented-reserved --fan option has no test asserting its warning fires and it remains a no-op
  - id: F021
    category: architectural-decay
    location: src/squadron/cli/commands/run.py:679
    severity: High
    effort: S
    summary: resume model-resolution logic is duplicated with subtly different semantics between two branches, risking a literal None string value
  - id: F022
    category: consistency-rot
    location: src/squadron/cli/commands/review.py:156
    severity: Medium
    effort: S
    summary: two functions named identically _resolve_cwd have different fallback semantics across review.py and metrology.py
  - id: F023
    category: consistency-rot
    location: src/squadron/cli/commands/review.py:454
    severity: Medium
    effort: S
    summary: Verdict.UNKNOWN has no explicit exit-code branch and falls through to exit 0, indistinguishable from PASS at the shell level
  - id: F024
    category: type-contract-debt
    location: src/squadron/cli/commands/run.py:90
    severity: Medium
    effort: S
    summary: --param key= with an empty value passes through unvalidated as a valid empty-string parameter
  - id: F025
    category: error-handling-observability
    location: src/squadron/cli/commands/spawn.py:101
    severity: Medium
    effort: S
    summary: spawn command swallows all daemon-connection exceptions with no logger.exception call before exiting
  - id: F026
    category: error-handling-observability
    location: src/squadron/cli/commands/run.py:228
    severity: Medium
    effort: S
    summary: except BaseException in _run_pipeline is broader than the stated finalize-before-propagate intent requires
  - id: F027
    category: documentation-drift
    location: docs/COMMANDS.md:14
    severity: Medium
    effort: S
    summary: COMMANDS.md documents a --against flag for review arch that the actual command does not accept
  - id: F028
    category: security-hygiene
    location: src/squadron/cli/app.py:33
    severity: Low
    effort: S
    summary: load_dotenv runs unconditionally at module import time, mutating process environment as a side effect of importing squadron
  - id: F029
    category: security-hygiene
    location: src/squadron/cli/commands/doctor_checks.py:103
    severity: Low
    effort: S
    summary: AuthStrategy.active_source is printed directly in doctor output with no contract preventing it from holding a credential value
  - id: F030
    category: performance-resource
    location: src/squadron/cli/commands/metrology.py:801
    severity: Medium
    effort: M
    summary: multi-project audit campaign creates and destroys an event loop per project via sequential asyncio.run calls
  - id: F031
    category: architectural-decay
    location: src/squadron/metrology/audit.py:1
    severity: High
    effort: M
    summary: audit.py is 789 lines owning five distinct concerns including preflight, prompt construction, config resolution, and the execution harness
  - id: F032
    category: consistency-rot
    location: src/squadron/metrology/report.py:61
    severity: High
    effort: S
    summary: a two-value Literal string pair is repeated as bare literals across 13 sites in one file, violating the project's own rule against scattering comparison values
  - id: F033
    category: consistency-rot
    location: src/squadron/review/review_client.py:152
    severity: Medium
    effort: M
    summary: SDK message type strings tool_use and tool_result are scattered as inline literals across four consumer files with no shared constant
  - id: F034
    category: error-handling-observability
    location: src/squadron/metrology/audit.py:688
    severity: Medium
    effort: S
    summary: the generic stream-failure exception branch logs at WARNING rather than ERROR despite the project's rule requiring ERROR for unclassified broad catches
  - id: F035
    category: type-contract-debt
    location: src/squadron/metrology/audit_report.py:85
    severity: Medium
    effort: S
    summary: baseline_report imperatively mutates a Pydantic model across a distant loop and assignment instead of computing all fields before construction
  - id: F036
    category: architectural-decay
    location: src/squadron/metrology/audit.py:91
    severity: Medium
    effort: S
    summary: audit-related exception classes are scattered across three separate modules with no consistent placement rule
  - id: F037
    category: architectural-decay
    location: src/squadron/metrology/audit.py:41
    severity: Medium
    effort: S
    summary: two callers depend directly on a private function imported from the skills resolver module instead of a public API
  - id: F038
    category: test-debt
    location: src/squadron/metrology/report.py:344
    severity: Medium
    effort: M
    summary: no test asserts a timezone-aware sample lands in the expected trend bucket, leaving a timezone bucketing bug undetectable
  - id: F039
    category: test-debt
    location: src/squadron/metrology/capture.py:1
    severity: Medium
    effort: M
    summary: no test exercises record_sample exactly at the sample budget ceiling to confirm boundary refusal behavior
  - id: F040
    category: performance-resource
    location: src/squadron/metrology/store.py:195
    severity: Medium
    effort: M
    summary: every list query method performs a full glob-and-deserialize scan including count_samples which deserializes every record just to count them
  - id: F041
    category: error-handling-observability
    location: src/squadron/metrology/store.py:197
    severity: Low
    effort: S
    summary: store list methods collapse three distinct exception types into one warning that logs only the file path, not the exception type
  - id: F042
    category: consistency-rot
    location: src/squadron/metrology/discovery.py:24
    severity: Low
    effort: S
    summary: the same frontmatter key name is defined independently as two different private constants in two modules of the same package
  - id: F043
    category: type-contract-debt
    location: src/squadron/metrology/report.py:201
    severity: Low
    effort: S
    summary: assert isinstance used as a runtime type-narrowing crutch on an already-typed value, elided under python -O
  - id: F044
    category: architectural-decay
    location: src/squadron/providers/anthropic/provider.py:1
    severity: High
    effort: S
    summary: stub-only unregistered untested provider directory creates false confidence that a third native provider implementation exists
  - id: F045
    category: type-contract-debt
    location: src/squadron/providers/openai/provider.py:64
    severity: High
    effort: S
    summary: validate_credentials hardcodes a check against OPENAI_API_KEY instead of the profile's configured auth strategy, producing false negatives for every other profile
  - id: F046
    category: test-debt
    location: src/squadron/providers/codex/agent.py:1
    severity: High
    effort: M
    summary: zero tests cover rate-limiting or timeout behavior in the Codex provider despite three recent fixes to the equivalent SDK-path behavior
  - id: F047
    category: consistency-rot
    location: src/squadron/providers/openai/provider.py:39
    severity: Medium
    effort: S
    summary: create_agent resolves auth strategy with an undocumented profile-to-credentials-dict indirection that is easy to accidentally break
  - id: F048
    category: error-handling-observability
    location: src/squadron/providers/loader.py:23
    severity: Medium
    effort: S
    summary: ensure_provider_loaded swallows all ImportError broadly, conflating an expected missing optional dependency with a real bug in the provider module
  - id: F049
    category: error-handling-observability
    location: src/squadron/providers/codex/agent.py:72
    severity: Medium
    effort: S
    summary: handle_message wraps all exceptions into one ProviderError losing type fidelity, and shutdown's broad catch lacks a justification comment
  - id: F050
    category: dependency-config-debt
    location: pyproject.toml:85
    severity: Medium
    effort: S
    summary: the codex agent module is excluded from pyright strict mode with no inline comment explaining the specific cause
  - id: F051
    category: architectural-decay
    location: src/squadron/providers/base.py:13
    severity: Medium
    effort: S
    summary: ProviderType enum has no CODEX value, so the Codex provider reports itself as the OPENAI_OAUTH profile type, conflating identity with profile
  - id: F052
    category: error-handling-observability
    location: src/squadron/review/git_utils.py:71
    severity: Medium
    effort: S
    summary: merge-commit and slice-branch resolution hardcode main as the base branch, ignoring the project's own configurable integration branch setting
  - id: F053
    category: security-hygiene
    location: src/squadron/providers/codex/auth.py:47
    severity: Low
    effort: S
    summary: OAuth file validity check only tests file existence, not content, surfacing corrupt auth files as opaque downstream SDK errors
  - id: F054
    category: type-contract-debt
    location: src/squadron/providers/profiles.py:116
    severity: Low
    effort: S
    summary: auth_type is not validated against known values at profile-load time, deferring the error to a much later call site
  - id: F055
    category: security-hygiene
    location: src/squadron/server/daemon.py:42
    severity: High
    effort: S
    summary: neither the Unix socket nor the localhost HTTP transport requires any authentication token, and api_key values transit the HTTP transport in plaintext request bodies
  - id: F056
    category: error-handling-observability
    location: src/squadron/server/routes/agents.py:174
    severity: High
    effort: S
    summary: the one-shot task route leaks a spawned agent process if send_message raises after spawn succeeds, and does not map a name-collision error to its own status code
  - id: F057
    category: type-contract-debt
    location: src/squadron/config/manager.py:54
    severity: High
    effort: S
    summary: config value coercion has no float branch, so three documented float-typed config keys fail with an unsupported-type error when set
  - id: F058
    category: architectural-decay
    location: src/squadron/server/engine.py:24
    severity: Medium
    effort: S
    summary: the provider-alias to module-name mapping is duplicated verbatim between the server engine and the providers loader
  - id: F059
    category: architectural-decay
    location: src/squadron/server/routes/agents.py:123
    severity: Medium
    effort: S
    summary: a route handler reaches into a private registry attribute to fetch provider info instead of using a public accessor
  - id: F060
    category: type-contract-debt
    location: src/squadron/server/routes/agents.py:94
    severity: Medium
    effort: S
    summary: an invalid state query parameter raises an uncaught ValueError producing a 500 instead of a 422 client error
  - id: F061
    category: architectural-decay
    location: src/squadron/client/http.py:139
    severity: Medium
    effort: S
    summary: the daemon client's shutdown-request method calls a server route that does not exist, making the method unreachable dead code
  - id: F062
    category: documentation-drift
    location: src/squadron/config/keys.py:89
    severity: Medium
    effort: S
    summary: a registered config key's description claims it overrides another key but the override logic was never implemented
  - id: F063
    category: documentation-drift
    location: src/squadron/server/routes/agents.py:1
    severity: Medium
    effort: S
    summary: a server route for one-shot agent tasks exists but no documented CLI command calls it, leaving its intended usage unclear
  - id: F064
    category: performance-resource
    location: src/squadron/server/daemon.py:56
    severity: Medium
    effort: M
    summary: the PID file is written before server binding completes, risking a stale PID file if the bind fails before the cleanup finally block is reached
  - id: F065
    category: security-hygiene
    location: src/squadron/skills/resolver.py:58
    severity: Medium
    effort: M
    summary: a user-provided repo spec string is passed unvalidated into a git clone subprocess command
  - id: F066
    category: test-debt
    location: src/squadron/server/routes/agents.py:174
    severity: Medium
    effort: S
    summary: no server-level test exercises the one-shot task route's happy path or any of its error paths
  - id: F067
    category: security-hygiene
    location: src/squadron/server/app.py:18
    severity: Low
    effort: S
    summary: the daemon's FastAPI app uses default settings which serve Swagger UI and OpenAPI schema, unnecessary local attack surface
  - id: F068
    category: architectural-decay
    location: src/squadron/adk/__init__.py:1
    severity: Low
    effort: S
    summary: two placeholder packages referencing old slice numbers contain no implementation and are imported nowhere in the codebase
  - id: F069
    category: performance-resource
    location: src/squadron/models/aliases.py:160
    severity: Low
    effort: S
    summary: model alias resolution reads two TOML files from disk on every call with no caching
  - id: F070
    category: consistency-rot
    location: src/squadron/config/keys.py:49
    severity: Low
    effort: S
    summary: per-template default-model config keys are only accessed via dynamic string construction, bypassing static key registry validation
  - id: F071
    category: error-handling-observability
    location: src/squadron/core/agent_registry.py:119
    severity: Low
    effort: S
    summary: an exception log uses a generic object repr instead of the already-in-scope agent name, reducing log usefulness
```
<!-- squadron:findings:end -->
