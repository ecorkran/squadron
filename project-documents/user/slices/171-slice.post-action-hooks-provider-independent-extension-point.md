---
docType: slice-design
slice: post-action-hooks-provider-independent-extension-point
project: squadron
parent: project-documents/user/architecture/140-slices.pipeline-foundation.md
dependencies: [142, 149, 909, 911]
interfaces: []
dateCreated: 20260803
dateUpdated: 20260806
status: deprecated
---

# Slice Design: Post-Action Hooks — Provider-Independent Extension Point

> **Superseded 20260806 by slice 173 (User-Definable Actions on Supported
> Events).** Do not implement this slice. 173 reaches the same mechanism through
> a more general trigger: 171 fires only *after a pipeline action*, while 173
> binds actions to a closed `EventType` enum in which post-action is one event
> and `COMMIT` — external, fired by git, with no pipeline running — is another.
> The consumer that revives the mechanism turned out to be external to the
> pipeline, which is precisely the case this design could not serve.
>
> **What carries forward into 173, intact:** the single action-execution choke
> point (`executor.py:1124`); the hardcoded slice-909 dispatch post-condition
> below it as the acceptance test for the generalized mechanism; contract (b)
> on what a hook may do (observe / fail the action / mutate the result);
> contract (e) failure-mode enumeration; contract (f) ordering and veto; and the
> position that a hook is a typed in-process Python callable and **not**
> arbitrary shell.
>
> **What 173 corrects.** This design assumed ownership of schema concerns that
> belong to Context Forge — its motivating consumer was a frontmatter `status:`
> validator holding squadron's own copy of the canonical values. Per D10 of
> slice 172, cf maintains the schema and squadron uses it; a frontmatter rule
> bound to `COMMIT` calls `cf validate frontmatter` rather than revalidating.
> The two reworks recorded below (the authoring flow, and the run-level
> watermark) are resolved in 173 by the binding manifest and by event scoping.

## Deferral (20260803)

**Deferred immediately after design review, before any implementation. The
design below stands as written and is not the reason for the deferral.**

The slice rests on one load-bearing argument: the executor has accreted two
hardcoded post-action checks (909's dispatch artifact post-condition, 911's
`revision_number` stamp), and a third means editing the executor again. That
argument is worth 3/5 effort only if a credible third consumer exists. **There
is not one.**

The nominal first consumer — a frontmatter `status:` validator — turns out to
be poorly served by a hook:

- A `sq validate docs` command catches strictly more (every document, not only
  those touched during a pipeline run), can go in CI where it actually blocks,
  and is a fraction of the work.
- It arguably is not squadron's job at all. `cf check` exists, and Context
  Forge owns `file-naming-conventions.md`, which defines the canonical status
  set. Squadron's `DocumentStatus` enum would mirror another project's spec —
  the "accepted drift risk" noted under Technical Decisions is itself the tell.

Refactoring two checks that work onto a mechanism whose only new consumer is
better served elsewhere is speculative generality, which the project's own
rules ban. The two hardcoded checks stay where they are; a third one is
cheaper to add in place than this mechanism is to build.

### What would un-defer this

A consumer that must run **inside** a pipeline and **block** it — something
that cannot wait for CI or a manual command. Name that consumer and the
open/closed argument becomes real rather than theoretical.

### Known rework if it is revived

Two items surfaced in discussion after the design review and are **not**
incorporated below:

1. **Authoring flow.** As designed, adding a hook means editing squadron:
   a module under `hooks/builtin/` plus a line in
   `bootstrap_post_action_hooks()`. There is no project-level hook file. A
   feature that is a pain to use will not get used. Likely shape: a
   `.squadron/hooks/*.py` convention imported at bootstrap, registering
   through the already-public `register_post_action_hook` — the `conftest.py`
   pattern, in-repo, typed, and no shell door opened.

2. **The watermark is wrong, and duplicate suppression is the symptom.**
   `frontmatter-status` scopes to documents with mtime `>= run_started_at`,
   which is a *run*-level watermark — a document written in step 1 keeps
   matching after every later action, which is the only reason the design
   needs a dedup component. The correct shape: the **runner** computes the
   changed-document set once per action (delta since the *previous* action)
   and passes it in `HookContext`. A hook with nothing to do then receives an
   empty set and returns `PASS` immediately, each document is validated once
   at the moment it is written, the scan is shared across hooks instead of
   repeated per hook, and duplicate suppression disappears entirely. Gate the
   scan on whether any registered hook consumes it.

   Rejected alternative: having actions self-report what they wrote.
   `dispatch` cannot know — an agent writes files out of band, which is the
   entire premise of the 909 bug.

Also unresolved: hook records land in `ActionResult.metadata`, which persists
via `dataclasses.asdict` at [state.py:291](src/squadron/pipeline/state.py#L291)
— but only at **step** completion, and in prompt-only mode
`record_step_done` builds an `action_results` list only when `--verdict` is
passed ([state.py:387-396](src/squadron/pipeline/state.py#L387-L396)), so
there is nowhere to hang them. That signature needs to change. And as
designed, only non-`PASS` outcomes are recorded, which makes "ran and passed"
indistinguishable from "never fired" — the design's own "no silent path" rule
applied to failures but not to the silence that actually bites.

The architecture document carries the mechanism as **designed, not built**.

---

## Overview

Claude Code's `PreToolUse`/`PostToolUse` hooks are valuable and available to
exactly one of the seven provider profiles squadron runs. Anything built on
them silently does nothing for `openai`, `openai-oauth`, `openrouter`,
`gemini`, `local`, or `codex`. Issue
[#52](https://github.com/ecorkran/squadron/issues/52).

This slice adds the equivalent at the layer squadron owns — after an action —
and it is a **generalization of a mechanism already in the tree**, not a new
concept. Two facts make it small:

1. There is exactly one action-execution site:
   [executor.py:1124](src/squadron/pipeline/executor.py#L1124),
   `result = await action_impl.execute(ctx)`.
2. Squadron already has a post-action hook, hardcoded. Directly below that
   line sits the dispatch artifact post-condition from slice 909
   ([executor.py:1135-1153](src/squadron/pipeline/executor.py#L1135-L1153)) —
   an `if action_type == "dispatch" and result.success and expected_kind is
   not None` block that inspects the result, touches the filesystem, and can
   turn a reported success into a failure. Immediately after it, the slice 911
   `revision_number` stamp does the same thing again with the opposite
   severity contract.

Adding a third such check means editing the executor again, which is the
open/closed violation `.claude/rules/review-code.md` names explicitly. Giving
the mechanism a registration surface and migrating both existing cases onto
it is the whole slice. **If they do not fit, the mechanism is the wrong
shape** — that is the acceptance test, per the issue.

## Value

**Architectural.** One extension point replaces a growing `if action_type ==
...` chain in the executor's hot path, and it works for every provider profile
because it lives above the provider layer entirely.

**Developer-facing.** A post-action check becomes a ~40-line module with a
declared trigger and severity, plus a registration line — not an executor
edit and not a new executor test fixture.

**User-facing, immediately.** Agents repeatedly write `status: draft` into
document frontmatter. The canonical set (`not_started | in_progress |
complete | deferred | deprecated`) is defined in prose in
`ai-project-guide/file-naming-conventions.md` and mechanically enforced
nowhere. One contributing prompt error was found and fixed and did not account
for all of it. This slice ships the validator.

## Technical Scope

### In scope

- `PostActionHook` protocol, `HookTrigger`, `HookContext`, `HookOutcome`,
  `HookSeverity` — in a new `squadron/pipeline/hooks/` package.
- A hook registry mirroring the existing action registry, with a
  `bootstrap_post_action_hooks()` entry point mirroring
  `bootstrap_step_types()`.
- A single runner that executes matching hooks after one action, applies
  outcomes, enforces a timeout, and records results.
- Two call sites: the in-process executor, and the prompt-only
  `--step-done` handler (parity — see below).
- Three built-in hooks: `dispatch-artifact` (migrated), `revision-stamp`
  (migrated), `frontmatter-status` (new).
- Activation surface: one config key + one pipeline-YAML block.
- `DocumentStatus` enum — squadron's first mechanical definition of the
  canonical status set.

### Explicitly excluded

- **Pre-action hooks** that rewrite an action's input. Much larger blast
  radius, no current consumer.
- **Arbitrary shell hooks.** This is what makes Claude's hooks a security
  surface and is the least portable across CI / MCP / IDE / bare CLI. Shell
  can be added later; it cannot be removed later.
- **User-authored hook discovery** (entry points, plugin scan, project hook
  files). The registry function is public so an in-process consumer can
  register, but there is no file-based discovery this slice.
- **Per-step activation.** No consumer wants it.
- Replacing Claude Code's hooks where they are better positioned. They see
  individual tool calls; squadron sees actions. The two are complementary.

### Parent architecture

This slice introduces architecture-level surface — a third registry, a new
pipeline-YAML block, two config keys — so the parent
[140-arch.pipeline-foundation.md](../architecture/140-arch.pipeline-foundation.md)
is updated as part of this slice rather than left to drift: the hooks registry
appears in the Component Architecture diagram and Package Structure, the
`hooks:` block in the Grammar, and the authority model (trigger, severity,
clamp, chain-stop, the `result.outputs` bar) in a new "Post-Action Hooks"
section under Action Extensibility. Initiative 180's convergence strategies
and any future custom step type need to know this extension point exists and
what authority it carries.

## Dependencies

### Prerequisites

- **142** — `ActionResult` / `ActionContext` models and the `Action` protocol,
  whose registry shape this slice copies.
- **149** — the executor and its single action-execution site.
- **909** — the hardcoded dispatch artifact post-condition being generalized;
  **911** — the `revision_number` stamp layered on it. Both complete.

### Interfaces Required

- `ArtifactKind` / `PhaseStepType` ([steps/phase.py](src/squadron/pipeline/steps/phase.py)) —
  the dispatch-artifact hook needs the step's `expected_artifact_kind`.
- `StateManager.load(run_id).started_at` — the mtime watermark both
  filesystem-inspecting hooks use.
- `read_frontmatter` / `update_frontmatter`
  ([documents/frontmatter.py](src/squadron/documents/frontmatter.py)).
- `get_config` ([config/manager.py](src/squadron/config/manager.py)).

## Architecture

### Component Structure

```
src/squadron/pipeline/hooks/
  __init__.py          protocol, models, registry, bootstrap
  runner.py            run_post_action_hooks() — the one execution path
  builtin/
    dispatch_artifact.py   migrated from executor.py:125-214
    revision_stamp.py      migrated from executor.py:217-~280
    frontmatter_status.py  new
```

`squadron/documents/paths.py` — new, holding `USER_DOCS_ROOT =
Path("project-documents/user")`. `REVIEWS_DIR` and `TASKS_DIR` in
[review/persistence.py](src/squadron/review/persistence.py#L21) are rewritten
to derive from it; their names and values do not change, so no consumer moves.

`squadron/documents/status.py` — new, holding `DocumentStatus(StrEnum)`.

### The four contracts

**(a) What a hook is.** A registered Python object satisfying a
`runtime_checkable` Protocol — typed, testable, in-process. Same shape as
`Action`, same registry pattern, same bootstrap idiom.

```python
class HookSeverity(StrEnum):
    WARN = "warn"    # may observe and warn; may never fail an action
    FAIL = "fail"    # may turn a successful action into a failed one

class HookStatus(StrEnum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"

@dataclass(frozen=True)
class HookTrigger:
    # None = every action type. Never a pipeline-structure predicate.
    action_types: frozenset[str] | None
    on_success_only: bool = True

@dataclass(frozen=True)
class HookOutcome:
    status: HookStatus
    message: str | None = None

@runtime_checkable
class PostActionHook(Protocol):
    @property
    def hook_name(self) -> str: ...
    @property
    def trigger(self) -> HookTrigger: ...
    @property
    def severity(self) -> HookSeverity: ...
    async def check(self, context: HookContext) -> HookOutcome: ...
```

`check` is `async` for one reason that matters: it makes
`asyncio.wait_for` the timeout mechanism rather than a thread. Hooks doing
subprocess work (CF resolution shells out) must not block the loop, and the
project's Python rules forbid >1ms synchronous work inside an `await`-able.
Hooks that are purely `Path.stat()` may be trivially `async`.

**(b) What a hook may do.** Three things, and no more:

- Return `PASS` — nothing to say.
- Return `WARN` — observable, non-fatal.
- Return `FAIL` — the runner sets `result.success = False` and
  `result.error = message`.

A hook may write files (the `revision_number` stamp does). A hook may **not**
otherwise mutate `ActionResult`, and may **not** read `result.outputs` — see
the prompt-only parity section for why that restriction is load-bearing
rather than stylistic.

Severity is one declared axis, and it governs both the outcome and the
breakage case. The runner **clamps**: a `WARN`-severity hook returning `FAIL`
is a programming error — clamped to `WARN`, logged at ERROR naming the hook.
This is what keeps `revision-stamp` from ever failing a converging loop, which
909/911 states as a hard requirement.

**(c) Trigger granularity.** `HookTrigger` declares action types and
success-only. It deliberately cannot express "on phase steps with an expected
artifact" — that is pipeline structure, and the issue requires hooks not know
it. Instead the **runner** puts step-derived facts into `HookContext` and the
hook self-selects:

```python
@dataclass(frozen=True)
class HookContext:
    action_type: str
    result: ActionResult          # outputs is {} in prompt-only mode
    params: dict[str, object]
    cwd: str
    run_id: str
    run_started_at: datetime | None
    run_state_error: str | None
    step_name: str
    step_type: str
    expected_artifact_kind: ArtifactKind | None
    iteration: int
    cf_client: CfClientProtocol
```

`expected_artifact_kind` is already computed once per step at
[executor.py:1078](src/squadron/pipeline/executor.py#L1078); it moves into the
context unchanged. `dispatch-artifact` returns `PASS` when it is `None` —
which is precisely today's `expected_kind is not None` guard, relocated from
the executor into the hook that cares.

`run_started_at` / `run_state_error` likewise move as-is. Their present
"fails closed if state is unreadable" doctrine belongs to the dispatch hook,
not to the runner, and travels with it.

**(d) Activation.** Built-ins register at bootstrap and are **enabled by
default** — the migrated post-condition must keep working with zero config.
Two disable surfaces, unioned:

| Surface | Form | Reach |
|---|---|---|
| `hooks.disabled` config key | comma-separated hook names, default `""` | user + project config |
| Pipeline YAML `hooks: {disable: [...]}` | list of hook names | one pipeline |

A hook is skipped if named in **either**. There is no re-enable override, so
there is no precedence puzzle. Both surfaces are read by the same code below
the CLI, so CLI / slash command / MCP behave identically — the standing
interface-parity rule.

Note on the config type system: `_coerce_value`
([config/manager.py:54-61](src/squadron/config/manager.py#L54-L61)) supports
only `int` and `str`. `hooks.disabled` is therefore `str` (comma-separated),
not `list[str]`, so `sq config set hooks.disabled a,b` works without widening
the config type system in this slice. YAML is where a list is natural, and
that is where the list form lives. Second key: `hooks.timeout_seconds`
(`int`, default `30`).

This does leave two encodings of one concept, and it is a workaround, not a
preference. **Trigger condition for fixing it properly: a third list-valued
config key.** At that point `_coerce_value` gains a `list[str]` branch and
`hooks.disabled` migrates to it — two keys do not justify widening a shared
type system; three do. Recorded so the decision is made on a count rather
than on whoever next finds the comma-splitting annoying.

### Data Flow

```
executor: result = await action_impl.execute(ctx)
              |
              v
   run_post_action_hooks(HookContext, disabled: frozenset[str])
              |
     for each registered hook, in registration order:
              |
       trigger matches? --no--> skip
              | yes
       named in disabled? --yes--> skip (log DEBUG)
              | no
       await asyncio.wait_for(hook.check(ctx), timeout)
              |
       +------+------------------------------+
       |                                     |
   raised / timed out                    HookOutcome
       |                                     |
   severity FAIL -> outcome FAIL         clamp to severity
   severity WARN -> outcome WARN             |
       |                                     |
       +------------------+------------------+
                          v
        record in result.metadata["hooks"] (append)
                          |
              status is FAIL? --yes--> result.success = False
                          |             result.error = message
                          |             STOP — remaining hooks skipped
                          v
                    next hook
```

`FAIL` stops the chain. This is what expresses the one real ordering
dependency in the tree today: `revision-stamp` registers **after**
`dispatch-artifact` and therefore does not run when the post-condition failed
— which is exactly the current `if artifact_error is not None: ... elif
ctx.iteration >= 1: _stamp_revision_number(...)` structure, expressed as
ordering instead of an `elif`.

Registration order is deterministic and stated in one place
(`bootstrap_post_action_hooks()`), mirroring `bootstrap_step_types()`.

### State and observability

Every hook invocation that is not `PASS` appends to
`result.metadata["hooks"]`:

```python
{"hook": "dispatch-artifact", "status": "fail", "message": "..."}
```

`metadata` already flows into persisted run state, so hook activity is
inspectable after the fact and in `sq run --status`. Values are `str` only —
JSON-serializable by construction.

Logging: `PASS` at DEBUG (with duration), `WARN` at WARNING, `FAIL` at
WARNING, hook raise at ERROR via `logger.exception`. Every message is prefixed
with the hook name. **There is no silent path** — this is the
failure-mode-enumeration rule, and a silent hook is worse than no hook.

## Technical Decisions

### Prompt-only parity — the decision that shapes the slice

Today the dispatch artifact post-condition runs **only** in the in-process
executor. Prompt-only mode (`sq run --prompt-only` /
[run.py:606](src/squadron/cli/commands/run.py#L606), then
`--step-done`) never executes an action in-process, so it has no post-action
moment and no post-condition. **That is a pre-existing parity gap**, not one
this slice introduces — but this slice either inherits it or closes it, and
inheriting it would mean shipping an extension point that does nothing in the
execution mode `/sq:run` uses.

**Decision: close it, at `--step-done`.**
`_handle_step_done` ([run.py:709](src/squadron/cli/commands/run.py#L709)) is
prompt-only's post-action moment — the point where the out-of-process agent
asserts the step is complete. Changes:

1. Expand the step (`step_type_impl.expand(step)`) to get its action types —
   the CLI already has the `StepConfig` and the definition.
2. For each expanded action, build a `HookContext` with a **synthesized**
   `ActionResult(success=True, action_type=..., outputs={})`. Success is the
   honest reading of what `--step-done` asserts.
3. Run the same hooks through the same runner.
4. If any hook returns `FAIL`: print the message to stderr, **do not** call
   `record_step_done`, and exit non-zero.

Step 4 is the substantive win: today, a prompt-only P4 run whose dispatch
wrote no design document advances anyway. After this slice it does not — the
909 bug is fixed in the mode where it is most likely to bite.

**This is why hooks may not read `result.outputs`.** In prompt-only mode there
are none. A hook that depended on them would work in one mode and silently
no-op in the other, which is the exact failure this slice exists to remove.
Both known consumers read the filesystem and the context, so the restriction
costs nothing today; it is stated as a contract so it keeps costing nothing.

Not addressed: prompt-only has no per-action granularity (the agent does the
whole step out of process), so hooks fire once per expanded action at
step end rather than interleaved. For filesystem-inspecting hooks this is
indistinguishable. It is recorded here so nobody later reads the difference
as a bug.

### Frontmatter status validator: WARN, not FAIL

`frontmatter-status` is `HookSeverity.WARN`.

An invalid `status:` is a metadata defect, not a broken artifact. Failing the
action — and therefore the step, and therefore possibly a review loop — over
a bad enum value would be disproportionate, and would block work on a
pre-existing bad file the current run did not create. It is escalatable to
`FAIL` later, once the real warning rate is known. Escalating is a one-line
change; de-escalating after it has blocked someone's pipeline is a bug report.

Scope: files under `USER_DOCS_ROOT` with mtime `>= run_started_at`, i.e. the
documents this run may have written. If `run_started_at` is unavailable, the
hook returns `PASS` and logs at WARNING naming the reason — a validator that
cannot scope itself must not scan the entire tree on every action.

Trigger: `action_types=None, on_success_only=True`. Squadron cannot know which
actions write documents, and guessing a set would be exactly the fragile
label-as-logic pattern the project rules ban.

**Duplicate suppression.** A 12-step pipeline would otherwise emit the same
warning 40 times, and a noisy hook is an ignored hook. The runner keeps an
in-memory set keyed `(hook_name, message)` and logs each distinct outcome
once; suppressed repeats are logged at DEBUG. The `metadata["hooks"]` record
is still written every time — the log is deduped, the evidence is not.

The set's lifetime is **the process**, not the run, and the two coincide only
in the in-process executor. In prompt-only mode each `sq run --step-done` is a
fresh process, so a recurring warning surfaces once per `--step-done`
invocation rather than once per run. That is the correct behavior for a mode
whose steps are separated by human turns — a warning suppressed in a process
the user is no longer looking at would be a warning lost — but it means
"once per run" is only true of the executor. Success criterion #10 is stated
in those terms so it is testable as written.

### The canonical status set lives in squadron code

`DocumentStatus(StrEnum)` in `squadron/documents/status.py`:
`not_started | in_progress | complete | deferred | deprecated`, plus the
documented `completed` → `complete` alias
([file-naming-conventions.md:61](project-documents/ai-project-guide/file-naming-conventions.md#L61)).

The upstream prose lives in `ai-project-guide/`, which squadron vendors and
does not own, so it cannot be the runtime source of truth. The enum carries a
comment naming that file as the upstream definition. **Drift risk is real and
is accepted for this slice**; if `cf` ever exposes the valid set
programmatically, the enum should read from there instead. Recorded as a
follow-up, not built speculatively.

## Migration Plan

The migration is the acceptance test. Order matters — each step leaves the
tree working.

| # | Move | From | To |
|---|---|---|---|
| 1 | Add package, protocol, registry, runner | — | `pipeline/hooks/` |
| 2 | `_check_dispatch_artifact_written`, `_dispatch_artifact_post_condition_error`, `_expected_artifact_paths` | [executor.py:110-214](src/squadron/pipeline/executor.py#L110-L214) | `hooks/builtin/dispatch_artifact.py` |
| 3 | `_stamp_revision_number` | [executor.py:217](src/squadron/pipeline/executor.py#L217) | `hooks/builtin/revision_stamp.py` |
| 4 | Delete the `if action_type == "dispatch" ...` block | [executor.py:1129-1153](src/squadron/pipeline/executor.py#L1129-L1153) | replaced by one `run_post_action_hooks(...)` call |
| 5 | New hook | — | `hooks/builtin/frontmatter_status.py` |
| 6 | Prompt-only call site | — | `_handle_step_done` |

`_expected_artifact_paths` is shared by steps 2 and 3; it lands in
`dispatch_artifact.py` and `revision_stamp.py` imports it, or it moves to a
small shared module if a third consumer appears. Do not duplicate it.

### Verification that behavior is preserved

**The binding constraint: no assertion in an existing 909/911 test may
change.** Only `monkeypatch`/`mock.patch` target paths move, and only because
the functions moved modules. This is the same discipline slice 306 applied
when relocating `run_git` — seven patch targets moved, zero assertions
changed.

Existing coverage that must pass unmodified-except-for-targets:

- [test_executor.py:646](tests/pipeline/test_executor.py#L646) onward — the
  Part A post-condition suite, including the WARNING-log assertion at
  [line 857](tests/pipeline/test_executor.py#L857) (`"dispatch post-condition"`
  must remain the log prefix) and `test_implement_phase_skips_post_condition`
  at [line 860](tests/pipeline/test_executor.py#L860).
- [test_executor.py:994](tests/pipeline/test_executor.py#L994) onward — the
  911 `revision_number` stamp suite, including
  `test_not_stamped_when_post_condition_failed` at
  [line 1159](tests/pipeline/test_executor.py#L1159), which after migration is
  proving the runner's FAIL-stops-the-chain rule rather than an `elif`.
- [test_executor_integration.py:62](tests/pipeline/test_executor_integration.py#L62)
  and the `conftest.py` fixture note at
  [line 26](tests/pipeline/conftest.py#L26).

If any of these needs its assertion text changed, the mechanism is the wrong
shape and the design is what gets revised — not the test.

## Success Criteria

### Functional

1. `PostActionHook` protocol, `HookTrigger`, `HookContext`, `HookOutcome`,
   `HookSeverity`, `HookStatus`, and a registry with
   `register_post_action_hook` / `get_post_action_hook` /
   `list_post_action_hooks` / `bootstrap_post_action_hooks`.
2. `run_post_action_hooks()` is the only place a hook is invoked, from both
   the executor and `_handle_step_done`.
3. Trigger matching: `action_types=None` matches every action;
   a non-`None` set matches only those; `on_success_only=True` skips failed
   actions.
4. Outcome application: `FAIL` sets `success=False` and `error`; `WARN` and
   `PASS` leave the result's success untouched.
5. Severity clamp: a `WARN`-severity hook returning `FAIL` is clamped to
   `WARN` and logged at ERROR.
6. `FAIL` stops the remaining hooks for that action.
7. A hook that raises is logged at ERROR with a traceback and produces its
   declared severity's outcome — `FAIL`-severity fails the action,
   `WARN`-severity does not.
8. A hook that exceeds `hooks.timeout_seconds` is cancelled and treated
   identically to a raise.
9. Every non-`PASS` outcome appends to `result.metadata["hooks"]` and is
   logged at WARNING or above, prefixed with the hook name.
10. Duplicate `(hook_name, message)` outcomes are logged once per **process**
    — once per run under the executor, once per `--step-done` invocation in
    prompt-only mode. Metadata records every occurrence.
11. `hooks.disabled` and pipeline `hooks: {disable: [...]}` each skip a named
    hook; the effective set is their union.
12. `dispatch-artifact` reproduces the 909 post-condition exactly, including
    every fail-closed branch and the `"dispatch post-condition"` log prefix.
13. `revision-stamp` reproduces the 911 stamp exactly, including its
    `iteration >= 1` gate and its never-fail-the-action contract.
14. `frontmatter-status` warns on any document under `USER_DOCS_ROOT` modified
    at-or-after `run_started_at` whose `status:` is outside `DocumentStatus`
    (accepting `completed` as an alias), naming file and offending value.
15. In prompt-only mode, `sq run --step-done` runs the same hooks; a `FAIL`
    outcome prints to stderr, does **not** record the step done, and exits
    non-zero.

### Technical

16. No `if action_type == ...` post-action branch remains in `executor.py`.
17. Every existing 909/911 test passes with assertion text unchanged; only
    patch targets move.
18. `ruff check`, `ruff format --check`, and `pyright` (strict) clean.
19. Each new module under ~300 lines; the runner's main function under ~50.
20. Failure-mode coverage: at least one test asserting the observable signal
    for each of raise, timeout, disabled, clamp, and chain-stop.

### Documentation

21. `docs/PIPELINES.md` gains a "Post-action hooks" section: what a hook is,
    the two contracts an author must declare, the activation surfaces, and
    the "may not read `result.outputs`" restriction with its reason.
22. `docs/COMMANDS.md` records the `--step-done` non-zero exit and the two
    new config keys.
23. CHANGELOG entry noting the prompt-only `--step-done` behavior change —
    a step that previously advanced can now block. This is a real break for
    anyone scripting `--step-done`.
24. `140-arch.pipeline-foundation.md` carries the hooks registry in its
    Component Architecture and Package Structure, the `hooks:` block in its
    Grammar, and the authority model under Action Extensibility.

## Verification Walkthrough

Draft. Refined against observed output at the end of Phase 6.

### 1. The migration changed nothing (the acceptance test)

```bash
uv run pytest tests/pipeline/test_executor.py -k "post_condition or revision" -q
git diff --stat main -- tests/pipeline/test_executor.py
```

Expect: all pass. The diff shows only `monkeypatch.setattr` /
`mock.patch` target strings changing from
`squadron.pipeline.executor._*` to `squadron.pipeline.hooks.builtin.*`. **No
assertion line appears in the diff.**

```bash
grep -n 'action_type == "dispatch"' src/squadron/pipeline/executor.py
```

Expect: no output.

### 2. The frontmatter validator catches what motivated the slice

In a scratch project with a document written during a run:

```bash
sq run p4 171 --verbose
```

While it runs, set `status: draft` in the design document it is writing.
Expect on stderr, once:

```
WARNING  frontmatter-status: project-documents/user/slices/171-slice.….md
         has status: 'draft' — not one of not_started, in_progress, complete,
         deferred, deprecated
```

Expect the run to **continue** — `WARN` severity does not fail the action.
Expect the warning **once**, not once per subsequent action.

### 3. The dispatch post-condition still fails closed

```bash
sq run p4 <index-with-no-writable-design-path> --verbose
```

Expect the step to fail with the same message text as before this slice, and
`sq run --status latest` to show the hook record:

```
hooks: dispatch-artifact = fail
```

### 4. Prompt-only parity — the new behavior

```bash
sq run p4 171 --prompt-only            # note the run_id on stderr
sq run --step-done <run_id>            # without having written the design
echo "exit=$?"
```

Expect a non-zero exit, the post-condition message on stderr, and:

```bash
sq run --status <run_id>
```

showing the step **not** marked complete. Then write the design document and
re-run `--step-done`; expect exit 0 and the step recorded.

Before this slice, the first `--step-done` succeeded silently and the
pipeline advanced.

### 5. Disabling

```bash
sq config set hooks.disabled frontmatter-status
sq run p4 171 --verbose
```

Expect no `frontmatter-status` lines and a DEBUG line naming it as disabled.
Same result via a pipeline's `hooks: {disable: [frontmatter-status]}` block.

### 6. A misbehaving hook is observable, not silent

Covered by test rather than by hand, since it needs a deliberately broken
hook: register a hook that sleeps past `hooks.timeout_seconds` and one that
raises. Expect an ERROR log naming each, the `FAIL`-severity one failing its
action, and the `WARN`-severity one not.

## Risk Assessment

**Deciding what a hook may do to a running pipeline is the risk; the
mechanism is not.** The mitigation is that severity is a single declared axis
with a runner-enforced clamp, so a hook cannot exceed its declared authority
even by returning the wrong thing. The two migrated consumers sit at opposite
ends of that axis (`FAIL` and `WARN`), so both ends are exercised on day one
rather than designed for hypothetically.

**Prompt-only `--step-done` is a behavior break.** A step that previously
advanced can now block. This is the intended fix for the 909 bug in
prompt-only mode, but it changes the exit-code contract of a command users
script against. Mitigation: CHANGELOG entry flagged as a break, the failure
message names the hook and the reason, and `hooks.disabled` is the documented
escape hatch.

**Scan cost of an every-action hook.** `frontmatter-status` triggers on every
action. Mitigation is the mtime watermark — it only stats files under one
directory tree and only parses frontmatter for those modified during the run,
which in practice is one to three files. If this proves slow, the trigger
narrows; it does not need a redesign.

## Implementation Notes

Suggested order: registry and runner with a test-only fake hook first (proves
trigger matching, clamping, chain-stop, timeout, and raise handling in
isolation) → migrate `dispatch-artifact` → migrate `revision-stamp` → delete
the executor block → prompt-only call site → `frontmatter-status` last.

Putting the new hook last is deliberate. Until the two migrated hooks pass
their untouched 909/911 assertions, the mechanism has not earned a third
consumer.
