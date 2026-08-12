---
docType: review
layer: project
reviewType: code
slice: user-definable-actions-on-supported-events
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/173-slice.user-definable-actions-on-supported-events.md
aiModel: moonshotai/kimi-k2.7-code
status: complete
dateCreated: 20260811
dateUpdated: 20260811
reviewedSha: a1600cf8a530c2e4e04bdd8913a58a5a11aeba8e
findings:
  - id: F001
    severity: concern
    category: linting/static-analysis
    summary: "Unused top-level import of `bootstrap_event_actions`"
    location: src/squadron/cli/commands/run.py
  - id: F002
    severity: concern
    category: typing
    summary: "`paths` Typer argument type is incompatible with `None` default"
    location: src/squadron/cli/commands/events.py#events_fire
  - id: F003
    severity: concern
    category: error-handling
    summary: "Broad `except Exception` swallows plugin bugs in dispatcher"
    location: src/squadron/events/dispatcher.py#_run_binding
  - id: F004
    severity: concern
    category: design
    summary: "Private artifact-path helper is imported across builtin actions"
    location: src/squadron/events/builtin/revision_stamp.py
  - id: F005
    severity: concern
    category: validation
    summary: "events.yaml is parsed and validated manually instead of via Pydantic"
    location: src/squadron/events/manifest.py#load_manifest
  - id: F006
    severity: concern
    category: validation
    summary: "Manifest loader does not validate action/event compatibility"
    location: src/squadron/events/manifest.py#resolve_bindings
  - id: F007
    severity: concern
    category: async/testing
    summary: "Real `cf` integration tests block the async event loop"
    location: tests/events/builtin/test_frontmatter_gate.py#TestRealCfIntegration
  - id: F008
    severity: concern
    category: documentation/ux
    summary: "Pre-commit hook exit-2 message is stale after moving to `sq events fire`"
    location: .githooks/pre-commit
  - id: F009
    severity: note
    category: typing
    summary: "EventAction protocol declares `name`/`events` as properties while implementations use class attributes"
    location: src/squadron/events/protocol.py#EventAction
  - id: F010
    severity: pass
    category: design
    summary: "Event contexts use frozen dataclasses with clear per-event field separation"
    location: src/squadron/events/contexts.py
  - id: F011
    severity: pass
    category: error-handling
    summary: "Plugin discovery restores `sys.path` and fails closed on import errors"
    location: src/squadron/events/discovery.py#discover_plugins
  - id: F012
    severity: pass
    category: testing
    summary: "Dispatcher tests cover commit vs post-action semantics, timeouts, and raises"
    location: tests/events/test_dispatcher.py
---

# Review: code — slice 173

**Verdict:** CONCERNS
**Model:** moonshotai/kimi-k2.7-code

## Findings

### [CONCERN] Unused top-level import of `bootstrap_event_actions`

`run.py` imports `bootstrap_event_actions` at module level alongside `EventType`, then re-imports `bootstrap_event_actions` inside `_run_post_action_bindings_for_step_done`. The module-level import is unused and will be flagged by ruff (`F401`) and pyright strict (`reportUnusedImport`), which are merge blockers per project rules. Remove the duplicate top-level import.

### [CONCERN] `paths` Typer argument type is incompatible with `None` default

`paths: list[str] = typer.Argument(default=None, ...)` declares a non-optional `list[str]` with a `None` default. Under strict type checking this is a mismatch. Use `paths: list[str] = typer.Argument(default_factory=list)` or annotate `paths: list[str] | None`.

### [CONCERN] Broad `except Exception` swallows plugin bugs in dispatcher

`_run_binding` catches `Exception` around `action.execute`. While D4 wants every action raise to be treated as a failure, the project Python rules require specific exception types, re-raising after logging, or a documented top-level process boundary. The current catch also captures `ValueError`, `TypeError`, `AssertionError`, etc. from action implementation bugs rather than expected action failures. Narrow the exception contract or make the boundary explicit with a clarifying inline comment.

### [CONCERN] Private artifact-path helper is imported across builtin actions

`revision_stamp.py` imports `_expected_artifact_paths` from `dispatch_artifact.py` and has to suppress `reportPrivateUsage`. Sharing a private helper across modules violates encapsulation and couples the two builtin actions. Extract the path-resolution logic into a public shared helper (e.g., `squadron.events.artifact_utils`) that both actions import.

### [CONCERN] events.yaml is parsed and validated manually instead of via Pydantic

The project Python rules require Pydantic for all external-boundary parsing. `load_manifest` performs hand-rolled YAML casting and validation. Replace it with Pydantic models (`EventManifestModel`, `BindingModel`) to reduce parsing bugs, improve error messages, and make extension safer.

### [CONCERN] Manifest loader does not validate action/event compatibility

`resolve_bindings` only checks that an action name is registered; it does not verify that the action supports the event it is bound to. A user could write `post-action: squadron.frontmatter-gate`, which loads cleanly but then triggers a runtime `AssertionError` when the action narrows the context. Validate `event in action.events` during load and raise `ManifestError` for incompatible bindings.

### [CONCERN] Real `cf` integration tests block the async event loop

`TestRealCfIntegration` uses synchronous `subprocess.run(["cf", ...], ...)` inside `async def` test methods. Per the project async rule, synchronous code that takes more than ~1 ms must not run directly inside an `async def`; it blocks the event loop. Convert these calls to `asyncio.create_subprocess_exec` or run them in a thread via `asyncio.to_thread`.

### [CONCERN] Pre-commit hook exit-2 message is stale after moving to `sq events fire`

The exit-code-2 branch still tells the user “if this repo is not a registered cf project, run 'cf init' once.” With the new command, exit code 2 comes from `sq events fire commit` for usage errors, manifest errors, or plugin-load failures—not from `cf validate frontmatter`. Update both `.githooks/pre-commit` and the identical `PRE_COMMIT_HOOK` string in `src/squadron/cli/commands/setup_install.py` to mention `events.yaml`/plugin/manifest errors.

### [NOTE] EventAction protocol declares `name`/`events` as properties while implementations use class attributes

`EventAction` declares `name` and `events` as `@property`, but built-in implementations define them as class attributes (`name = "squadron..."`). Runtime-checkable protocols accept this, but the static contract is weaker and can mislead readers. Consider aligning the protocol with the implementations (plain attributes or abstract properties).

### [PASS] Event contexts use frozen dataclasses with clear per-event field separation

`EventContext`, `CommitContext`, and `PostActionContext` are immutable dataclasses and carry only the fields each event type honestly provides. This cleanly separates commit-time and executor-time events per design D1.

### [PASS] Plugin discovery restores `sys.path` and fails closed on import errors

`discover_plugins` prepends the working directory to `sys.path`, imports declared plugin modules, and removes the entry in a `finally` block. Import failures are logged at ERROR and raised as attributed `PluginLoadError`, satisfying the rule that a gate whose plugin did not load must not pass.

### [PASS] Dispatcher tests cover commit vs post-action semantics, timeouts, and raises

The new dispatcher tests assert D4 (COMMIT runs all bindings), D5 (POST_ACTION stops at first failure), and the timeout/raise failure modes with log assertions. This is a solid test-with pattern for the new subsystem.
