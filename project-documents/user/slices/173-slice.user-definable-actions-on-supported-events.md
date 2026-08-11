---
docType: slice-design
slice: user-definable-actions-on-supported-events
project: squadron
parent: project-documents/user/architecture/140-slices.pipeline-foundation.md
dependencies: [142, 149, 172, 909, 911]
interfaces: []
dateCreated: 20260809
dateUpdated: 20260811
status: complete
---

# Slice Design: User-Definable Actions on Supported Events

> Supersedes slice 171 (post-action hooks, deferred 20260803, issue #52). 171's
> deferral test — "name a consumer that must run inside the mechanism and block"
> — is now met twice over: the frontmatter gate that slice 172 shipped as a
> bespoke installer, and external projects (e.g. a trading repo) adding
> domain-specific rule checks. 171's contracts on authority, failure modes, and
> ordering carry forward intact and are cited where they apply.

## Overview

An advanced user writes a Python callable conforming to a published contract,
registers it against a **supported event**, and squadron runs it. Events are a
closed set — users bind to events; they do not invent them. `COMMIT` (external,
fired by git, no pipeline running) and `POST_ACTION` (fired at the executor's
single action-execution site) are the initial two.

The framing that shapes everything: `{action}` that runs on `{event}` —
not "a thing that runs on commit."

Most of the machinery exists. `pipeline/actions/__init__.py` has the
Protocol-plus-registry pattern; `gate.py:118-138` repeats it for gate policies;
`ActionResult` already carries `success`, `error`, `verdict`, `findings` — the
shape a rules check returns. **The actual gap is discovery**: registration
happens as an import side effect, and nothing imports a user module today, so a
user action can never register. This slice builds events, namespacing, binding,
and discovery — and migrates the two hardcoded post-action checks (909, 911)
onto the mechanism as its acceptance test.

## Value

**User-facing.** A project consuming squadron can enforce its own rules at
commit time (e.g. `trading.rule-check`) by writing one Python module and one
manifest entry — no fork, no subprocess, no second executable.

**Architectural.** The executor's growing `if action_type == ...` post-action
chain (909's post-condition, 911's revision stamp — a third means editing the
executor again) becomes registrations on one mechanism. Slice 172's bespoke
gate installer becomes a `COMMIT`-bound built-in, closing the loop the slice
plan records: 172 landed first, 173 refactors its T30 step into the registry.

## Technical Scope

### In scope

- `EventType(StrEnum)` — `COMMIT`, `POST_ACTION`. Closed: adding an event is a
  squadron change, never a user change.
- `squadron/events/` package: event contexts, `EventAction` protocol,
  namespaced registry, binding manifest loader, plugin discovery, dispatcher.
- Built-in event actions: `squadron.frontmatter-gate` (COMMIT — calls
  `cf validate frontmatter`), `squadron.dispatch-artifact` (POST_ACTION —
  migrated 909 post-condition), `squadron.revision-stamp` (POST_ACTION —
  migrated 911 stamp).
- `sq events fire {event}` — the synchronous process entry point git needs.
- `.githooks/pre-commit` repointed from calling `cf validate frontmatter`
  directly to `sq events fire commit`; 172's `_install_git_hook` content
  updated accordingly (installer mechanics unchanged).
- Prompt-only parity at `--step-done`, per 171's decision (see D9).

### Explicitly excluded

- **Arbitrary shell / subprocess plugins.** A user action is an in-process
  Python callable. Shell can be added later and cannot be removed later.
- **Pre-action events** that rewrite an action's input. No consumer.
- **New event types beyond the two.** The enum exists precisely so additions
  are deliberate squadron changes.
- **Sandboxing / security hardening of plugin import.** Out of the threat
  model per the Project Manager: the plugin author is the project owner.
- **Python < 3.12.** Squadron already requires ≥3.12; a plugin author is in
  the target user group or is not writing plugins.

## Dependencies

### Prerequisites

- **142** — `ActionResult` / `ValidationError` (reused as-is) and the registry
  idiom being copied.
- **149** — the executor and its single action-execution site
  (`executor.py:1125`, `result = await action_impl.execute(ctx)`).
- **172** — the frontmatter gate being refactored onto the mechanism; `cf
  validate frontmatter` (context-forge ≥ 0.12.0) as the gate's engine.
- **909 / 911** — the hardcoded post-condition and revision stamp being
  migrated. Both complete; their tests are the acceptance criterion.

### Interfaces Required

- `ArtifactKind` / `PhaseStepType` (`steps/phase.py`) — the migrated
  dispatch-artifact action needs `expected_artifact_kind`.
- `StateManager.load(run_id).started_at` — the watermark 909 uses, passed in.
- `CfClientProtocol` (`review/persistence.py`) — the migrated actions resolve
  document paths through it.
- `get_config` (`config/manager.py`) — `events.timeout_seconds`.
- Loader search-path convention (`pipeline/loader.py:_search_dirs`) — the
  manifest resolves the same way: project → user.

## Architecture

### Component Structure

```
src/squadron/events/
  __init__.py       EventType, registry (register/get/list), bootstrap
  contexts.py       EventContext base + CommitContext, PostActionContext
  protocol.py       EventAction protocol
  manifest.py       binding manifest load/resolve (project → user)
  discovery.py      plugin import with per-plugin attribution
  dispatcher.py     fire() — the one execution path for both events
  builtin/
    frontmatter_gate.py    new (wraps cf validate frontmatter)
    dispatch_artifact.py   migrated from executor.py
    revision_stamp.py      migrated from executor.py
src/squadron/cli/commands/events.py   sq events fire / sq events list
```

This is deliberately the **third** instance of the Protocol-plus-registry
pattern (actions, gate policies, now events), not an extension of the first:
see D1 for why event actions do not enter the pipeline action registry.

### Data Flow

**COMMIT** (external — git is the caller):

```
git commit
  └─ .githooks/pre-commit (staged *.md → args)
       └─ sq events fire commit [paths...]        (process boundary)
            ├─ load manifest (project → user, first found)
            ├─ discover: import each declared plugin, attributed hard-fail
            ├─ build CommitContext(cwd, staged_paths, params)
            └─ for each binding on COMMIT, in manifest order:
                 result = asyncio.wait_for(action.execute(ctx), timeout)
                 → all bindings run; failures collected, not short-circuited
            exit 0 all succeeded / 1 any failed / 2 could not run
```

**POST_ACTION** (internal — the executor is the caller):

```
executor: result = await action_impl.execute(ctx)     # executor.py:1125
  └─ await fire(PostActionContext(..., result=result))
       └─ for each binding on POST_ACTION, in registration-then-manifest order:
            outcome applied to result (observe / fail / mutate per D4)
            failure stops the chain (expresses 909-before-911 ordering)
```

COMMIT runs **all** bindings and reports every failure — a commit gate that
stops at the first finding hides the second, and the developer fixes findings
one commit attempt at a time. POST_ACTION **stops on failure** — that is the
existing `if artifact_error is not None: ... elif` structure of 909/911,
expressed as ordering, and carried from 171 contract (f) unchanged.

## Technical Decisions

### D1 — Event-scoped contexts; the pipeline `Action`/`ActionContext` are untouched

The one place the two bindings genuinely rub, resolved as follows.
`ActionContext` requires `pipeline_name`, `run_id`, `step_index`,
`prior_outputs`, `resolver`, `cf_client` — all pipeline concepts. A commit has
none of them, and lacks the one thing a commit event *does* carry: staged
paths. Reusing `ActionContext` would mean synthesizing placeholder resolvers
and empty run ids — silent fallback values, banned outright — and every
optional carrier added for one event is a field the other event's authors read
by accident.

So event actions take an **event-typed context**:

```python
@dataclass(frozen=True)
class EventContext:                 # common base
    event: EventType
    cwd: str
    params: dict[str, object]       # from the binding's manifest entry

@dataclass(frozen=True)
class CommitContext(EventContext):
    staged_paths: tuple[str, ...]

@dataclass(frozen=True)
class PostActionContext(EventContext):
    action_type: str
    result: ActionResult            # outputs is {} in prompt-only mode (D9)
    run_id: str
    run_started_at: datetime | None
    run_state_error: str | None
    step_name: str
    step_type: str
    expected_artifact_kind: ArtifactKind | None
    iteration: int
    cf_client: CfClientProtocol
```

`PostActionContext` is 171's `HookContext`, renamed. "A user-defined callable
is an Action" holds where it matters — same `ActionResult`, same
`ValidationError`, same registry idiom, same bootstrap idiom — but the
*context* is honest about what the event actually carries. The pipeline
`Action` protocol, `ActionContext`, and the pipeline action registry do not
change in this slice.

### D2 — The `EventAction` protocol

```python
@runtime_checkable
class EventAction(Protocol):
    @property
    def name(self) -> str: ...                       # namespaced: "trading.rule-check"
    @property
    def events(self) -> frozenset[EventType]: ...    # which events it may bind to
    def validate(self, config: dict[str, object]) -> list[ValidationError]: ...
    async def execute(self, context: EventContext) -> ActionResult: ...
```

`execute` is `async` for the same single reason as 171: `asyncio.wait_for` is
the timeout mechanism. The process entry point wraps dispatch in
`asyncio.run()` — a git hook is a process that exits with a status, which is
the "synchronous entry point" the slice plan requires. An action doing
subprocess work (the frontmatter gate shells to `cf`) must use
`asyncio.create_subprocess_exec`, per the project's event-loop rule.

An action narrows the context itself (`isinstance(context, CommitContext)`)
and returns a failed `ActionResult` naming the mismatch if bound to an event
it does not support — and `events` lets the dispatcher refuse the binding at
manifest-validation time, before anything runs.

### D3 — Namespacing: every event action name is `{namespace}.{name}`

All event actions — built-ins included — carry a dotted namespace:
`squadron.frontmatter-gate`, `trading.rule-check`. `register_event_action`
raises on: a name without a dot, a duplicate name (collision — first
registration wins nothing; it is an error, not a shadow), and a `squadron.`
prefix registered from outside `squadron.events.builtin` (checked by module of
the caller at registration; cheap, not security — security is out of scope,
this catches accidents). Built-in dispatch never consults this registry by
free string: the dispatcher iterates *bindings*, and binding validation
resolves names once at manifest load. The no-string-dispatch rule holds
because no squadron code branches on an action's name.

The pipeline `ActionType` enum and pipeline registry are unaffected; the
slice-plan language about guarding `register_action` lands here, on the new
registry, where third-party names actually arrive.

### D4 — Authority: what a bound action may do (carried from 171 contract b)

Three things, no more:

- **Observe** — return `success=True`; findings/verdict recorded, nothing
  altered.
- **Fail** — return `success=False` with `error`. On COMMIT this fails the
  commit (exit 1). On POST_ACTION the dispatcher sets `result.success =
  False`, `result.error = ...` on the *pipeline* action's result and stops the
  chain.
- **Mutate** — an action may write files (the revision stamp does). It may
  **not** otherwise mutate the pipeline `ActionResult` it observes, and may
  not read `result.outputs` (empty in prompt-only mode — an action depending
  on it works in one mode and silently no-ops in the other; both migrated
  consumers read the filesystem, so the restriction costs nothing).

There is no severity axis in this design. 171 needed `WARN`-clamping because
`revision-stamp` must never fail an action; here that is expressed directly:
the migrated `squadron.revision-stamp` returns `success=True` always and logs
its own failures at WARNING, which is its existing 911 contract, enforced by
its own tests rather than by a runner clamp. If a future consumer needs
declared severity, it is added then — designing it now is the speculative
generality that deferred 171.

### D5 — Failure modes: coarse, attributed, never silent (carried from 171 contract e)

Per the Project Manager: "you make a python callable and it breaks, it's your
fault — crash the process with message."

- **Plugin import raises** (discovery): `logger.exception` naming the plugin
  module and manifest source file, then hard-fail — COMMIT exits 2, a
  POST_ACTION dispatch fails the pipeline action. Never skip-and-continue: a
  gate whose plugin didn't load must not pass.
- **Action raises during execute**: caught at the dispatch boundary (process
  boundary handler), `logger.exception` with the action name, treated as
  **Fail** with the exception text in the message. The one deliberate
  `except Exception` in this slice, at the boundary, logged — per the
  exception-handling rule's clause (c).
- **Timeout**: `events.timeout_seconds` config key (`int`, default 30);
  exceeding it is identical to a raise, naming the action.
- **Unknown action name in a binding**: manifest validation error at load,
  naming the manifest file and the name; lists registered actions (same shape
  as `get_action`'s KeyError).
- Logging: success at DEBUG with duration, failure at WARNING or above, always
  prefixed with the action name. No silent path.

### D6 — Binding manifest: `events.yaml`, resolved project → user, first found wins

Locations, mirroring `pipeline/loader.py:_search_dirs` exactly minus built-in
(built-in bindings live in code, see below):

1. `{cwd}/project-documents/user/events.yaml` (project)
2. `~/.config/squadron/events.yaml` (user)

First file found is **the** manifest — no merging, matching `load_pipeline`
semantics. Format:

```yaml
plugins:
  - trading_rules.checks          # importable module path (see D7)
bindings:
  commit:
    - action: trading.rule-check
      params: {ruleset: strict}
disable:
  - squadron.frontmatter-gate     # opt out of a built-in binding
```

Built-in bindings (`squadron.frontmatter-gate` on COMMIT;
`squadron.dispatch-artifact` then `squadron.revision-stamp` on POST_ACTION)
are defined in code as `DEFAULT_BINDINGS` and always active unless named in
`disable` — the migrated 909/911 checks must keep working with zero config,
and a default expressed as an installed file would be a default nobody can
tell from user intent. No manifest at all means: defaults only, which is
exactly today's behavior. Execution order: built-ins in their declared order,
then manifest bindings in file order.

### D7 — Discovery: declared imports, not scanning

`plugins:` entries are importable module paths, imported with
`importlib.import_module` at dispatch entry (once per process). Registration
happens as an import side effect via `register_event_action(...)` at module
foot — the same idiom as every action module and gate policy. No `pkgutil`
walking, no directory scanning, no entry points: a scan finds things nobody
declared, and this feature's contract is explicit declaration.

The module must be importable from the process's environment — for a project
whose plugin lives in-repo, that means the project root on `sys.path` or the
plugin installed into the venv. The dispatcher prepends `cwd` to `sys.path`
for the import step (and removes it after), so `plugins: [tools.squadron_rules]`
resolves against a `tools/squadron_rules.py` in the repo without packaging
ceremony. That is the whole accommodation; anything fancier is the plugin
author's packaging problem.

### D8 — Process entry point: `sq events fire`

```
sq events fire commit [PATHS...]     # paths: the staged files, from the hook
sq events fire commit                # no paths: action decides its own scope
sq events list                       # bindings by event, with source (built-in/manifest)
```

Exit codes (matching the 172 gate's semantics): `0` all bound actions
succeeded, `1` at least one failed (findings printed per action, attributed),
`2` could not run (plugin import failure, manifest error, unknown action).
`POST_ACTION` cannot be fired from the CLI — it has no meaning outside a run;
`sq events fire post-action` is a usage error naming the reason.

`.githooks/pre-commit` (and `PRE_COMMIT_HOOK` in `setup_install.py` — the
byte-identity test carries over) changes its invocation line to
`uv run --quiet sq events fire commit -- "${staged_files[@]}"` with the same
missing-tool hard-fail contract, now checking `uv` (as the pre-172 hook did).
`squadron.frontmatter-gate` invokes `cf validate frontmatter <paths>` and maps
its exit codes through — cf missing or exit 2 is a **Fail** with the
actionable message, preserving 172's D6 (a gate that cannot run must not
pass).

### D9 — Prompt-only parity at `--step-done` (carried from 171, unchanged)

The 909 post-condition runs only in the in-process executor; prompt-only mode
(`/sq:run`'s mode) has no post-action moment, so a P4 run whose dispatch wrote
nothing advances anyway. 171 decided to close this at `_handle_step_done`, and
that decision carries: expand the step, synthesize
`ActionResult(success=True, outputs={})` per expanded action (the honest
reading of what `--step-done` asserts), build `PostActionContext`, run the
same dispatcher. Any failure: print attributed message to stderr, do **not**
`record_step_done`, exit non-zero. This changes the exit-code contract of a
scripted command — CHANGELOG-flagged as a break, `disable:` is the escape
hatch. Hooks fire once per expanded action at step end rather than
interleaved; for filesystem-inspecting actions this is indistinguishable, and
it is recorded here so nobody later reads it as a bug.

## Implementation Details

### Migration plan (the acceptance test)

Order matters; each step leaves the tree working.

| # | Move | From | To |
|---|---|---|---|
| 1 | Package: enum, contexts, protocol, registry, dispatcher, manifest, discovery | — | `events/` |
| 2 | `_check_dispatch_artifact_written`, `_dispatch_artifact_post_condition_error`, `_expected_artifact_paths` | `executor.py` (~110–214) | `events/builtin/dispatch_artifact.py` |
| 3 | `_stamp_revision_number` | `executor.py` (~217) | `events/builtin/revision_stamp.py` |
| 4 | Delete the `if action_type == "dispatch" ...` block | `executor.py:1136-1154` | one `await fire(PostActionContext(...))` call |
| 5 | New built-in | — | `events/builtin/frontmatter_gate.py` |
| 6 | CLI | — | `cli/commands/events.py` |
| 7 | Hook + installer repoint | `.githooks/pre-commit`, `setup_install.py:PRE_COMMIT_HOOK` | `sq events fire commit` |
| 8 | Prompt-only call site | — | `_handle_step_done` |

`_expected_artifact_paths` is shared by 2 and 3: it lands in
`dispatch_artifact.py`, `revision_stamp.py` imports it. Do not duplicate it.

**Binding constraint, carried verbatim from 171: no assertion in an existing
909/911 test changes.** Only `monkeypatch`/`mock.patch` target paths move
(`squadron.pipeline.executor._*` → `squadron.events.builtin.*`). The
`"dispatch post-condition"` log prefix is part of the asserted behavior and
survives the move. `test_not_stamped_when_post_condition_failed`
(tests/pipeline/test_executor.py, 911 suite) becomes the proof of
fail-stops-the-chain. If a test needs its assertion text changed, the
mechanism is the wrong shape and the design is what gets revised.

### What a plugin looks like (contract illustration, not shipped code)

```python
# tools/squadron_rules.py — in the consuming repo
from squadron.events import EventType, register_event_action
from squadron.events.contexts import CommitContext, EventContext
from squadron.pipeline.models import ActionResult

class RuleCheck:
    name = "trading.rule-check"
    events = frozenset({EventType.COMMIT})
    def validate(self, config): return []
    async def execute(self, context: EventContext) -> ActionResult:
        assert isinstance(context, CommitContext)
        bad = [p for p in context.staged_paths if _violates_rules(p)]
        return ActionResult(
            success=not bad, action_type=self.name, outputs={},
            error=f"rule violations: {bad}" if bad else None,
        )

register_event_action(RuleCheck())
```

Two files total for the consumer: this module, and an `events.yaml` declaring
`plugins: [tools.squadron_rules]` and one binding.

## Integration Points

### Provides to Other Slices

- The `COMMIT` mechanism 172's T30 gate refactors onto (this slice performs
  that refactor; `_install_git_hook` and its tests survive with only the hook
  body changing).
- The `POST_ACTION` extension point initiative-180 convergence strategies can
  register against without executor edits.
- The parent architecture doc (`140-arch.pipeline-foundation.md`) gains the
  events registry in Component Architecture / Package Structure and the
  authority model (observe / fail / mutate, no-outputs rule) — updated in this
  slice rather than left to drift, as 171 specified.

### Consumes from Other Slices

- `cf validate frontmatter` (172 / context-forge ≥ 0.12.0). If `cf` is absent
  the frontmatter gate **fails** with the install hint — same posture as the
  current hook, now enforced one layer down.

## Success Criteria

### Functional

1. `EventType` has exactly `COMMIT` and `POST_ACTION`; binding to anything
   else is a manifest validation error.
2. `register_event_action` raises on: undotted name, duplicate name,
   `squadron.` prefix from outside `events/builtin`.
3. A plugin module declared in `events.yaml` is imported at dispatch entry;
   its registration is visible to `sq events list`.
4. A plugin that raises on import produces an ERROR log naming module and
   manifest file, and the event run fails (COMMIT exit 2) — never skips.
5. An action that raises or exceeds `events.timeout_seconds` during execute is
   logged at ERROR with attribution and treated as Fail.
6. COMMIT runs all bindings and reports every failure; exit 0/1/2 per D8.
7. POST_ACTION stops at the first failure; the failing action's error lands on
   the pipeline `ActionResult` (`success=False`, `error` set).
8. `squadron.frontmatter-gate` maps `cf validate frontmatter` exits through:
   0 → success, 1 → fail with findings, 2/missing-cf → fail with actionable
   message.
9. Manifest resolution: project file wins over user file, first found, no
   merge; `disable:` suppresses a built-in binding; no manifest → defaults
   only.
10. `sq events fire post-action` is a usage error; `sq events list` shows
    every binding with its source.
11. Prompt-only: `sq run --step-done` runs POST_ACTION bindings; a failure
    prints to stderr, does not record the step done, exits non-zero.

### Technical

12. No `if action_type == ...` post-action branch remains in `executor.py`.
13. Every existing 909/911 test passes with assertion text unchanged; only
    patch targets move.
14. `.githooks/pre-commit` and `PRE_COMMIT_HOOK` remain byte-identical
    (existing test), now invoking `sq events fire commit`.
15. `ruff`, `pyright` strict clean; modules ≤ ~300 lines; failure-mode
    coverage: one test per raise / timeout / import-failure / unknown-name /
    disable / chain-stop / run-all.

### Documentation

16. `docs/PIPELINES.md` (or a new `docs/EVENTS.md`): what an event action is,
    the contract, the manifest format, the authority model, the no-outputs
    rule with its reason.
17. CHANGELOG: the `--step-done` behavior change flagged as a break; the hook
    invocation change (commit gating now requires `uv`/squadron on PATH, not
    only `cf`).

## Verification Walkthrough

Executed against the real implementation at end of Phase 6 (20260811).
Commands and output below are as observed, not illustrative.

### 1. The migration changed nothing

```bash
uv run pytest tests/pipeline/test_executor.py -k "post_condition or revision" -q
git diff main -- tests/pipeline/test_executor.py | grep "^[+-]" | grep -v "patch\|monkeypatch\|import\|^[+-][+-]"
grep -n 'action_type == "dispatch"' src/squadron/pipeline/executor.py
```

Observed: 18 passed; the filtered diff is empty (this file has zero diff
from `main` — the existing 909/911 tests already exercised the public
`execute_pipeline` entry point, never the private helpers by dotted path,
so no patch-target strings needed to move at all); the grep exits 1 (no
match).

### 2. A third-party rules check runs on commit

In a scratch repo (`git init`, no cf project yet):

```bash
mkdir -p tools project-documents/user
cat > tools/demo_rules.py    # RuleCheck class from the contract illustration,
                              # named "demo.rule-check", rejecting paths containing "forbidden"
cat > project-documents/user/events.yaml <<'EOF'
plugins:
  - tools.demo_rules
bindings:
  commit:
    - action: demo.rule-check
disable:
  - squadron.frontmatter-gate   # no cf project registered in this scratch repo
EOF
sq events list
```

Observed:
```
commit
  demo.rule-check  (project-documents/user/events.yaml)
post-action
  squadron.dispatch-artifact  (built-in)
  squadron.revision-stamp  (built-in)
disabled
  squadron.frontmatter-gate  (disabled)
```

```bash
echo content > forbidden-file.md
sq events fire commit -- forbidden-file.md; echo $?
```
Observed: `demo.rule-check: failed (0.00s): rule violations: ['forbidden-file.md']`,
exit 1. Renamed to a clean path: `demo.rule-check: ok`, exit 0. With a
syntax error appended to `tools/demo_rules.py`:
`Error: failed to import plugin 'tools.demo_rules' declared in project-documents/user/events.yaml`,
exit 2 — a full traceback is also logged naming the file and line — never a
silent pass.

### 3. The frontmatter gate still gates, one layer down

In this repo (a registered cf project), with a doc carrying
`status: not-a-real-status`:

```bash
git add project-documents/user/reviews/zz-smoke.md
git commit -m test
```
Observed: commit refused; `frontmatter-gate: Frontmatter Validation ... ⚠
Invalid value 'not-a-real-status' for field 'status' ...`; hook prints
`pre-commit: sq events fire commit failed (exit 1).`; exit 1.

```bash
echo 'disable: [squadron.frontmatter-gate]' >> project-documents/user/events.yaml
sq events fire commit -- <that file>; echo $?
```
Observed: exit 0 — no bindings ran, so no findings printed (the disable
is silently effective at manifest resolution; `manifest.py` logs the
suppression at DEBUG, verified via `caplog` in `tests/events/test_manifest.py::test_disable_removes_a_default_binding`).

### 4. Prompt-only parity

```bash
sq run P4 200 --prompt-only        # -> run_id=run-...
sq run --step-done <run_id>        # without writing the design artifact
echo $?
```

Observed (scratch repo, slice 200 not in any registered slice plan):
`squadron.dispatch-artifact: raised during execute` with a full traceback
(`cf list slices --json` fails closed because no slice plan is configured),
`Error: squadron.dispatch-artifact: raised`, exit 1 — the attributed-raise
path (D5), not the artifact-post-condition path, since slice resolution
itself failed here. `record_step_done` is never called in either failure
mode (unit-tested directly in
`tests/cli/commands/test_run.py::TestStepDonePostActionParity`, which
mocks `run_event` to also exercise the artifact-missing/-present and
implement-phase-unaffected paths without requiring a live cf slice plan).

**Bug found and fixed during this walkthrough**: the first implementation
passed `PhaseStepType.expand(step)`'s action config straight through as
`PostActionContext.params`, so the `slice` param stayed the literal
unresolved string `"{slice}"` instead of the run's actual slice number —
`_run_post_action_bindings_for_step_done` now calls
`resolve_placeholders(action_config, state.params)` first, mirroring the
in-process executor's own resolution step. Covered by
`test_slice_placeholder_resolves_against_run_params`, which asserts against
`{slice}` leaking through if the fix regresses.

## Risk Assessment

**Importing foreign code is the risk; the mechanism is not.** Mitigations are
scoping, not sandboxing (per the PM, security is out of the threat model):
imports happen only for modules the project's own manifest declares; every
failure is attributed to a named module/action; and the dispatcher is the only
place plugin code runs, so the blast radius of a misbehaving plugin is the
event run, observably.

**The hook regains a squadron dependency at commit time.** 172 reduced the
hook's dependency to `cf` alone; routing through `sq events fire` re-adds
`uv`/squadron. This is the price of user-definable gates and matches the
pre-172 posture; the hook's missing-tool contract stays a hard fail either
way. If a repo wants the cf-only gate, `disable:` plus a hand-edited hook
remains possible — not squadron's default.

**`--step-done` exit-code change** — same break 171 accepted; CHANGELOG entry
and `disable:` escape hatch.

## Implementation Notes

Suggested order (each lands green):
**A** — `events/` package with a test-only fake action: registry guards,
manifest resolution, discovery attribution, dispatcher run-all vs. stop-on-fail,
timeout, raise handling. **B** — migrate `dispatch-artifact` and
`revision-stamp`, delete the executor block (the acceptance test).
**C** — `frontmatter-gate`, CLI, hook + installer repoint. **D** — prompt-only
`--step-done` call site. The new consumer surface (C) comes after the migrated
consumers prove the mechanism's shape, mirroring 171's reasoning: until the
909/911 assertions pass untouched, the mechanism has not earned a third
consumer.

Effort: 3/5. Risk: Medium (per slice plan).
