---
docType: slice-design
project: squadron
slice: 263-slice.dispatch-action-wiring-and-pipeline-yaml-surface
parent: 260-slices.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md
dependencies: [262]
interfaces: [264, 265]
dateCreated: 20260831
dateUpdated: 20260831
status: not_started
---

# Slice Design: Dispatch Action Wiring and Pipeline YAML Surface

## Parent Documents

- Architecture: `260-arch.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md`
- Slice Plan: `260-slices.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md`, entry 3

## Overview

Slice 262 made `OpenAICompatibleAgent` use tools **when given them**. Nothing gives them: no
pipeline YAML can declare tools, and the one-shot dispatch path constructs its `AgentConfig`
with a hardcoded `allowed_tools` omission and `cwd=None`. This slice opens that surface —
`allowed_tools` in step YAML, validated at load time, threaded through the dispatch action
into `AgentConfig` — and proves the end-to-end flow with a non-SDK model actually writing a
file.

Two facts from the shipped 262 code shape the whole slice and were not visible when the slice
plan was written:

1. **`cwd` must be threaded alongside `allowed_tools`, not after it.** The agent constructor
   raises `ProviderError` when `allowed_tools` is non-empty and `cwd is None`
   (`providers/openai/agent.py:115-119`). `one_shot_dispatch` currently passes `cwd=None`
   unconditionally (`pipeline/actions/dispatch.py:65`). Wiring tools without also wiring
   `cwd` is not an incomplete feature — it is a guaranteed 100% failure rate on any step that
   declares a tool. `ActionContext.cwd` already carries the executor's resolved working
   directory (`pipeline/executor.py:586`, `effective_cwd = cwd or os.getcwd()`) and is the
   correct source.

2. **Unknown tool names are silently dropped at runtime.** The agent logs a WARNING and
   continues with the remaining tools (`agent.py:127-133`) — deliberate, because decision D1
   leaves shipped review templates carrying Claude-vocabulary names until slice 265. That
   tolerance is correct for templates and wrong for pipeline YAML: a typo in
   `allowed_tools: [read_fil]` would run a full pipeline step with no tools, and the model
   would produce a plausible-sounding response describing a file it never wrote. Load-time
   validation is what makes the YAML surface safe; it is the substance of this slice, not
   decoration on it.

## Value

A pipeline author can write `allowed_tools: [read_file, write_file]` on a step and have a
non-SDK model actually write the artifact. Today `sq run test-p4` against `kimi27` produces
prose describing a slice design; after this slice it produces the slice design file. That is
the initiative's headline capability, and this slice is where it becomes reachable without
writing Python.

The load-time validation is the second half of the value: a misspelled tool name fails the
run before a token is spent, rather than silently degrading to a no-tool run whose output
looks superficially correct. This is the same class of failure as `project_dispatch_noop_bug`
(dispatch reporting success when the agent writes no artifact) and must not be reintroduced
through a new surface.

## Technical Scope

### In scope

- `allowed_tools: list[str] | None` accepted in step config for the `dispatch` step type and
  the three phase step types (`design`, `tasks`, `implement`).
- Per-step validation of tool names against the slice-261 registry, surfaced as squadron
  `ValidationError` through the existing `validate_pipeline` path.
- `DispatchAction._dispatch_via_agent` reads `allowed_tools` from `context.params` and passes
  it, together with `context.cwd`, into `one_shot_dispatch` → `AgentConfig`.
- `one_shot_dispatch` gains `allowed_tools` and `cwd` keyword parameters (both optional,
  defaulting to today's behavior).
- `test-p4.yaml` declares `allowed_tools` on its design step.
- Tests: schema/validation, expansion, threading, and an integration test against a mocked
  OpenAI-compatible endpoint that returns a tool call.

### Out of scope

- **Review and summary actions.** Slice 265 owns the review path, including its read-only
  tool subset and injection-skip decision. This slice establishes the pattern 265 follows.
- **SDK path changes.** The SDK dispatch path (`_dispatch_via_session`) is untouched. It has
  no per-step tool surface today and gains none here; SDK tool vocabulary remains a 265
  concern (decision D1).
- **Tool-use capability gating** (`models.toml tool_use`, `--no-tools`) — slice 266.
- **Other step types.** `loop`, `fan_out`, `gate`, `compact`, `devlog`, `commit`,
  `checkpoint`, `cf-op` do not dispatch to a model with a per-step tool surface. `loop` and
  `fan_out` contain inner steps whose own configs carry the field; no separate wiring is
  needed for the container.

## Architecture

### Data flow

```
step YAML
  allowed_tools: [read_file, write_file]
        │
        ▼
PipelineSchema._unpack_steps                     (schema.py — pass-through)
  StepSchema.config: dict[str, object]
        │
        ▼
validate_pipeline → step_impl.validate(step)     (loader.py:203)
  DispatchStepType.validate / PhaseStepType.validate
    → type check (list of str)
    → registry membership check  ← NEW, fails the run here
        │
        ▼
step_impl.expand(step)
  action_config["allowed_tools"] = [...]         ← NEW, conditional
        │
        ▼
ActionContext.params["allowed_tools"]
        │
        ▼
DispatchAction._dispatch_via_agent
  one_shot_dispatch(allowed_tools=..., cwd=context.cwd)   ← NEW
        │
        ▼
AgentConfig(allowed_tools=..., cwd=...)
        │
        ▼
OpenAICompatibleProvider.create_agent → OpenAICompatibleAgent
  tools.materialize(names, cwd)                  (262, unchanged)
```

Nothing new is invented in this flow: every hop is an existing hop that currently drops the
field. The design is deliberately a threading exercise plus one new validation.

### Where validation lives

`PipelineSchema` is not the right home, despite the slice plan's reference to the slice-245
`auth_policy` pattern. `auth_policy` is a **pipeline-level** typed field on `PipelineSchema`;
step configs are an untyped `dict[str, object]` (`schema.py:29-33`) precisely so step types
own their own config contracts. Adding a typed per-step field would require either a typed
model per step type in the schema layer or a special-case field on `StepSchema` that most
step types ignore — the first is a large refactor outside this slice, the second is an ISP
violation.

The established mechanism is `StepTypeName`'s own `validate(config) -> list[ValidationError]`,
which `validate_pipeline` already calls for every step (`loader.py:203`) and which every CLI
entry point already surfaces (`cli/commands/run.py`, six call sites). Tool validation goes
there. This also gives the correct error type: squadron's `ValidationError` with
`field`/`message`/`action_type`, rendered by the existing error path — not
`pydantic.ValidationError`, which the slice plan anticipated but which would bypass the
pipeline's own error rendering.

### Registry bootstrap at validation time

`validate_pipeline` already performs lazy registry bootstrap through local imports:
`bootstrap_step_types()` for step types and `load_all_templates()` for review templates
(`loader.py:163-179`). Tool registration follows the identical pattern — importing
`squadron.tools` registers the built-ins as an import side effect (documented in
`tools/__init__.py`). Today `squadron.tools` is imported only by the openai provider, which is
lazily loaded via `ensure_provider_loaded`, so validation cannot assume the registry is
populated. The validating step type imports `squadron.tools` locally at the top of its check.

### Shared validation helper

`DispatchStepType` and `PhaseStepType` need identical checking, and `PhaseStepType` is
instantiated three times. Duplicating the check four ways violates DRY and guarantees the
copies drift. The check goes in `pipeline/steps/utils.py` (which already exists and holds
shared step-type helpers) as a single function returning `list[ValidationError]`, called by
both step types.

```python
def validate_allowed_tools(
    config: StepConfig, action_type: str
) -> list[ValidationError]:
    """Validate a step's optional allowed_tools field.

    Checks the field is a list of strings and that every name is registered in
    the slice-261 tool registry. Returns [] when the field is absent.
    """
```

Two failure modes, two distinct messages:

- **Type failure** — not a list, or a list containing a non-string. Message names the field
  and the expected shape.
- **Unknown name** — passes type check, absent from `tools.list_tools()`. Message names the
  offending tool and lists the registered ones, matching the shape of the existing
  `ToolNotRegisteredError` message and the unknown-step-type error.

Each offending name produces its own `ValidationError` so a YAML with two typos reports both
in one run rather than one per fix cycle.

### Expansion

Both step types extend `expand()` conditionally, matching the established convention that an
absent key leaves the expanded dict byte-identical to its previous shape — the reason
`pre_emption_fragment` is conditional in both step types today
(`steps/phase.py:145-148`, `steps/dispatch.py:63-64`) and the reason the existing
exact-equality `expand()` tests keep passing.

### Dispatch action and cwd

`one_shot_dispatch` gains two keyword parameters:

```python
async def one_shot_dispatch(
    *,
    prompt: str,
    model_id: str,
    profile_name: str,
    system_prompt: str = "",
    step_name: str = "dispatch",
    run_id: str = "cli",
    branch_idx: object = None,
    allowed_tools: list[str] | None = None,   # NEW
    cwd: str | None = None,                   # NEW
) -> str:
```

Both default to `None`, so the existing callers (`cli` paths that call `one_shot_dispatch`
directly) keep today's behavior exactly. `AgentConfig` receives both. The `cwd=None` literal
at `dispatch.py:65` becomes the parameter.

`_dispatch_via_agent` reads the field from `context.params` — the same source it already uses
for `model`, `profile`, `system_prompt`, and `pre_emption_fragment` — and passes
`context.cwd` through unconditionally. Passing `cwd` even when no tools are declared is
correct and is not a behavior change worth gating: `AgentConfig.cwd` is inert for the non-SDK
agent unless tools are configured (the constructor only reads it inside the
`if requested_tools:` branch), and threading it unconditionally means the tool path cannot
later be reached with `cwd` accidentally unset.

A defensive type coercion is required at the params boundary. `context.params` is
`dict[str, object]`, and placeholder resolution runs over it. The action reads the value and
narrows to `list[str]`; a value that is not a list of strings at this point is a defect that
validation should have caught, so it raises rather than silently dropping tools — consistent
with the project rule against silent fallbacks. It is not re-validated against the registry
here: that check belongs at load time, and duplicating it would put the "unknown tool" message
in two places.

## Implementation Details

### Files changed

| File | Change |
| --- | --- |
| `pipeline/steps/utils.py` | Add `validate_allowed_tools` helper |
| `pipeline/steps/dispatch.py` | Call helper in `validate`; conditional pass-through in `expand` |
| `pipeline/steps/phase.py` | Same two changes |
| `pipeline/actions/dispatch.py` | `one_shot_dispatch` params; `_dispatch_via_agent` threading; replace `cwd=None` literal |
| `data/pipelines/test-p4.yaml` | `allowed_tools` on the design step |

No changes to `schema.py`, `loader.py`, `executor.py`, `models.py`, `AgentConfig`, the agent,
or the provider. The absence of loader changes is a deliberate signal that the design uses the
existing extension point rather than adding one.

### test-p4.yaml

```yaml
  - design:
      phase: 4
      model: "{model}"
      allowed_tools: [read_file, write_file]
      review:
        template: slice
        model: "{review-model}"
```

`bash` is deliberately excluded. The design phase writes one artifact; `bash` is unrestricted
beyond CWD scoping (documented 261 scope) and adding it to a shipped pipeline would widen the
blast radius of the demo without adding demonstrated capability. `read_file` is included
because the design phase legitimately reads the slice plan and architecture documents.

## Integration Points

- **Slice 262 (upstream, complete):** consumes `AgentConfig.allowed_tools` and `cwd`. This
  slice is purely additive to it — no agent or provider change.
- **Slice 261 (upstream, complete):** `tools.list_tools()` is the validation authority. If 261
  later registers more tools, this slice's validation widens automatically with no edit.
- **Slice 265 (downstream):** applies this same threading pattern to the pipeline `review` and
  `summary` actions, and owns the read-only tool subset. `validate_allowed_tools` is written to
  be reused by those step types unchanged — 265 calls it and adds its own subset restriction on
  top.
- **Slice 264 (downstream):** CF MCP tools register through the same registry, so they become
  declarable in YAML with no change to this slice's validation.
- **Slice 245 / initiative 240 (auth boundary):** unaffected. Tool wiring happens strictly
  inside `_dispatch_via_agent`, downstream of the profile-aware routing decision that 240 owns.

## Success Criteria

1. A step declaring `allowed_tools: [read_file, write_file]` loads, validates, and reaches
   `AgentConfig.allowed_tools` with those exact names.
2. A step declaring an unregistered tool name fails `validate_pipeline` with a
   `ValidationError` naming the offending tool and listing registered tools; the run does not
   start. Two bad names produce two errors in one pass.
3. A step declaring `allowed_tools` as a non-list, or a list containing a non-string, fails
   validation with a distinct type-shape message.
4. A step with no `allowed_tools` key produces an expanded action dict byte-identical to its
   pre-slice shape, and `AgentConfig.allowed_tools` is `None` — all existing pipelines behave
   exactly as before.
5. `_dispatch_via_agent` passes `context.cwd` into `AgentConfig.cwd` on every dispatch, so a
   tool-declaring step never trips the agent's `cwd is None` `ProviderError`.
6. Against a mocked OpenAI-compatible endpoint that returns a `write_file` tool call, running a
   pipeline step results in the file existing on disk with the expected content, and the
   dispatch `ActionResult` carries the model's final-turn text.
7. `sq run test-p4 <slice>` with a non-SDK model writes the slice-design file (manual
   verification — see walkthrough).
8. Full suite green, `uv run pyright` 0 errors, `ruff check` and `ruff format --check` clean.

## Design Decisions

**D1 — Validation lives in step-type `validate()`, not `PipelineSchema`.** Step configs are
intentionally untyped at the schema layer so step types own their contracts. Adding a typed
per-step field would mean either a per-step-type schema model (a refactor outside this slice)
or a `StepSchema` field most step types ignore (ISP violation). The step-type validate hook is
the existing, already-surfaced extension point and yields squadron's own `ValidationError`
type. This supersedes the slice plan's reference to the `auth_policy` pattern, which is
pipeline-level and not applicable to a per-step field.

**D2 — `cwd` is threaded unconditionally, not only when tools are declared.** Conditional
threading would create a second code path whose only difference is a field the agent ignores
when no tools are configured, and would leave a latent `ProviderError` reachable if a future
caller sets tools without tripping the condition. Unconditional threading is simpler and
removes the failure mode entirely.

**D3 — The dispatch action does not re-validate names against the registry.** Load-time
validation is the single authority; a second check would duplicate the "unknown tool" message
in two places and invite the two copies to diverge. The action does narrow the type and raises
on a malformed value, because a wrong type at that boundary is a defect, not user input.

**D4 — `bash` is excluded from the shipped `test-p4.yaml`.** The demo proves file writing;
`bash` adds unrestricted process execution to a shipped pipeline without adding demonstrated
capability. Authors can still declare it explicitly.

**D5 — Unknown names remain a WARNING at the agent layer.** The agent's drop-with-warning
behavior (262, decision D1) is not changed to a raise. It exists so shipped review templates
carrying Claude-vocabulary names keep working until slice 265 migrates them; making it fatal
here would break the review path. Pipeline YAML is protected by the load-time check instead,
so the two surfaces get the strictness each needs.

## Risks

**Placeholder resolution over a list value.** Step configs pass through param placeholder
resolution, which is exercised on scalars throughout the codebase; `allowed_tools` is the
first list-valued field to travel this path from the phase/dispatch step types. If resolution
stringifies or otherwise mangles a list, the action's type narrowing (D3) raises rather than
silently dropping tools. A test asserts the list arrives intact at `AgentConfig`. Mitigation is
cheap; the failure is loud either way.

## Verification Walkthrough

### 1. Validation rejects a bad tool name before spending a token

Create a scratch pipeline with a typo:

```yaml
name: tool-validation-check
params:
  slice: required
steps:
  - dispatch:
      prompt: "hello"
      allowed_tools: [read_file, write_fil]
```

```bash
uv run sq run tool-validation-check --slice 263 --dry-run
```

Expect a non-zero exit and an error naming `write_fil` and listing the registered tools
(`read_file`, `write_file`, `bash`). No model call is made.

### 2. Absent field changes nothing

```bash
uv run pytest tests/pipeline/ -q
```

The existing exact-equality `expand()` tests for `dispatch` and the phase step types pass
unmodified — that is the regression gate proving criterion 4.

### 3. Tool call actually writes a file (mocked endpoint)

```bash
uv run pytest tests/pipeline/test_dispatch_tools.py -v
```

The integration test stands up a mocked OpenAI-compatible endpoint returning a `write_file`
tool call followed by a final text turn, runs a one-step pipeline in a `tmp_path` cwd, and
asserts the file exists with the expected content and the `ActionResult` carries the final
turn's text.

### 4. End-to-end with a real non-SDK model

```bash
uv run sq run test-p4 --slice <some-unstarted-slice> -v
```

Expect: the design step dispatches to `kimi27` with `tools` in the request; the model issues a
`write_file` call; the slice-design file exists at
`project-documents/user/slices/<nnn>-slice.<name>.md` after the step; the subsequent review
step finds it as input rather than reporting a missing artifact.

Compare against `git stash`-ing the `allowed_tools` line from `test-p4.yaml` and re-running:
the model produces prose describing the design and no file appears. That contrast is the
slice's whole point.

### 5. Quality gates

```bash
uv run ruff format . && uv run ruff check . && uv run pyright && uv run pytest -q
```

Note: the full suite takes ~7 minutes and includes metrology tests that perform real
`time.sleep` — this is expected, not a hang.
