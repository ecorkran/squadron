# Events Guide

Events let a project bind its own Python callables to squadron's execution
lifecycle — enforcing a project-specific rule at commit time, or observing
every pipeline action after it runs — without forking squadron or shelling
out to a second tool.

```bash
sq events list                        # show every binding, by event
sq events fire commit [PATHS...]      # run all COMMIT bindings (what the git hook calls)
```

---

## What an event action is

An event action is a Python object satisfying the `EventAction` protocol,
registered under a namespaced name, bound to one or more **supported
events** via a manifest. The set of events is closed:

| Event | Fired by | Meaning |
|---|---|---|
| `commit` | `.githooks/pre-commit` (external, via `sq events fire commit`) | Staged markdown is about to be committed |
| `post-action` | The pipeline executor, once per action | A pipeline action just finished executing |

You bind actions to these two events — you do not invent new ones. Adding a
third event is a squadron change, not a project-level configuration change.

### The `EventAction` contract

```python
from squadron.events import EventType, register_event_action
from squadron.events.contexts import CommitContext, EventContext
from squadron.pipeline.models import ActionResult

class RuleCheck:
    name = "trading.rule-check"                       # namespaced: "{namespace}.{name}"
    events = frozenset({EventType.COMMIT})             # which events this may bind to

    def validate(self, config: dict) -> list:
        return []                                       # binding-param validation

    async def execute(self, context: EventContext) -> ActionResult:
        assert isinstance(context, CommitContext)
        bad = [p for p in context.staged_paths if _violates_rules(p)]
        return ActionResult(
            success=not bad, action_type=self.name, outputs={},
            error=f"rule violations: {bad}" if bad else None,
        )

register_event_action(RuleCheck())
```

- **Names are namespaced**: every action name is `{namespace}.{name}` (a dot
  is required). The `squadron.` prefix is reserved for squadron's own
  built-ins — registering a `squadron.`-prefixed name from outside
  `squadron.events.builtin` raises.
- **`execute` is `async`** so `asyncio.wait_for` can enforce a timeout
  (`events.timeout_seconds`, default 30). An action doing subprocess work
  must use `asyncio.create_subprocess_exec` — never a blocking subprocess
  call inside an `async def`.
- **An action narrows its own context.** `events` also lets the dispatcher
  refuse an invalid binding at manifest-load time, before anything runs.

### Event-typed contexts

A `commit` event and a `post-action` event carry genuinely different data —
a commit has no pipeline run, a post-action has no staged files — so each
event gets its own context rather than one contrived catch-all:

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
    result: ActionResult            # outputs is {} in prompt-only mode — see below
    run_id: str
    run_started_at: datetime | None
    run_state_error: str | None
    step_name: str
    step_type: str
    expected_artifact_kind: ArtifactKind | None
    iteration: int
    cf_client: CfClientProtocol
```

These are **not** the pipeline's own `Action` / `ActionContext` — that
protocol is unchanged by this feature and still governs pipeline steps.
Event actions are a separate, third instance of the same
protocol-plus-registry idiom (after pipeline actions and gate policies).

---

## Authority model

A bound action may do exactly three things:

- **Observe** — return `success=True`; nothing is altered.
- **Fail** — return `success=False` with `error`. On `commit` this fails the
  commit. On `post-action` the dispatcher marks the pipeline action's result
  failed and stops the chain (see Ordering, below).
- **Mutate** — an action may write files (squadron's own `revision-stamp`
  built-in does). It may **not** otherwise reach into and change the
  pipeline `ActionResult` it observes, and it may **not** read
  `result.outputs` — outputs is always `{}` in prompt-only mode
  (`--step-done` synthesizes a result with no real outputs to inspect), so
  an action depending on it would work in one execution mode and silently
  no-op in the other.

There is no severity axis (no WARN/CONCERNS tier). An action that must
never fail the run — like the revision stamp — expresses that by always
returning `success=True` and logging its own failures at WARNING; that is
the action's own tested contract, not something the runner clamps for it.

## Failure philosophy: coarse, attributed, never silent

If your callable breaks, that's on you — squadron crashes the process with
an attributed message rather than skipping past a broken action:

- **A declared plugin module fails to import** → logged at ERROR naming the
  module and the manifest file it was declared in, then hard-fails. `commit`
  exits 2. Never skipped: a gate whose plugin didn't load must not pass.
- **An action raises during `execute`**, or exceeds
  `events.timeout_seconds` → treated as **Fail**, logged with the action's
  name attributed. This is the one deliberate `except Exception` in the
  events package, at the dispatch boundary.
- **A binding names an action that isn't registered** → a manifest
  validation error at load time, naming the manifest file and the unknown
  name — never discovered at fire time.

## Ordering

- **`commit` runs every binding and reports every failure.** A gate that
  stops at the first finding hides the second, so a developer would fix
  violations one commit attempt at a time.
- **`post-action` stops at the first failure**, in registration-then-manifest
  order. Squadron's own built-ins run first: `squadron.dispatch-artifact`
  (does the phase step's dispatch action actually write the artifact it
  claimed to?) before `squadron.revision-stamp` (stamp a monotonic
  `revision_number` onto that artifact) — the stamp only runs once the
  post-condition has already passed.

---

## `events.yaml`

Resolved project → user, **first file found wins, no merging** (the same
search order `pipeline/loader.py` uses for pipelines):

1. `{project-root}/project-documents/user/events.yaml`
2. `~/.config/squadron/events.yaml`

No file present at all means: squadron's built-in bindings only — exactly
today's behavior with zero configuration.

```yaml
plugins:
  - tools.squadron_rules          # importable module path (see Discovery, below)

bindings:
  commit:
    - action: trading.rule-check
      params:
        ruleset: strict

disable:
  - squadron.frontmatter-gate     # opt out of a built-in binding
```

- **`plugins`** — module paths imported once, at dispatch entry, via
  `importlib.import_module`. Each module registers its action(s) as an
  import side effect (`register_event_action(...)` at the module foot — the
  same idiom as every squadron action module). The project's own root
  directory is temporarily added to `sys.path` for the import, so
  `plugins: [tools.squadron_rules]` resolves a `tools/squadron_rules.py` in
  the repo without any packaging.
- **`bindings`** — event name → list of `{action, params}`. `params`
  reaches the action as `context.params`.
- **`disable`** — action names to remove from squadron's default bindings.
  This is the escape hatch if a built-in doesn't fit — for example, a repo
  that wants the pre-172 cf-only gate can `disable: [squadron.frontmatter-gate]`
  and hand-edit its own hook.

**Effective binding order**: squadron's built-ins (minus anything in
`disable`), then this file's `bindings`, in the order they appear.

### Built-in bindings (always active unless disabled)

| Event | Action | What it does |
|---|---|---|
| `commit` | `squadron.frontmatter-gate` | Runs `cf validate frontmatter` against staged paths |
| `post-action` | `squadron.dispatch-artifact` | Fails a phase-step dispatch that didn't write its expected artifact |
| `post-action` | `squadron.revision-stamp` | Stamps a monotonic `revision_number` after a loop-iteration dispatch |

---

## Discovery

Declared imports only — squadron never scans a directory for plugins. A
scan finds things nobody declared; this feature's contract is explicit
declaration in `events.yaml`. If your plugin needs packaging (a real
installed dependency, not an in-repo module), install it into the same
environment `sq` runs in and reference its dotted module path directly —
no further accommodation is provided.

---

## Prompt-only parity

The in-process executor fires `post-action` bindings after every pipeline
action. A prompt-only run (`sq run --prompt-only`, as used by `/sq:run`) has
no in-process moment to fire from, so `sq run --step-done <run-id>` performs
the same dispatch itself: it expands the current step into its actions,
synthesizes an honest `ActionResult(success=True, outputs={})` per action,
and runs the same `post-action` bindings before marking the step done.

A failing binding prints its attributed message to stderr, does **not**
record the step as done, and exits non-zero — where previously a dispatch
that silently wrote nothing would advance anyway. This is a behavior
change to a scripted command's exit code; see the CHANGELOG.

---

## See also

- [Pipeline Authoring Guide](PIPELINES.md) — the pipeline mechanism whose
  action-execution site fires `post-action`.
- [Command Reference](COMMANDS.md#events) — `sq events fire` / `sq events list`.
