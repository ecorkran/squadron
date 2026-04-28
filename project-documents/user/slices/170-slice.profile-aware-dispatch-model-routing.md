---
docType: slice-design
slice: profile-aware-dispatch-model-routing
project: squadron
parent: 140-slices.pipeline-foundation.md
dependencies:
  - 145-dispatch-action
  - 164-profile-aware-summary-model-routing
  - 119-review-provider-and-model-selection
interfaces: []
dateCreated: 20260427
dateUpdated: 20260428
status: design
---

# Slice Design: Profile-Aware Dispatch Model Routing

## Overview

Slice 164 fixed profile-aware routing for the **summary** action: when the
resolved model alias has a non-SDK profile (e.g. `minimax` → `openrouter`),
prompt-only rendering emits a `command` field invoking `sq _summary-run …`,
and the SDK action branches off `set_model()` to a one-shot provider
dispatch. The **dispatch** action still has the slice-164 bug: regardless
of the resolved profile, prompt-only `_render_dispatch` emits
"Execute the work using the assembled context" with at most a
`model_switch` directive (`/model …`). When the harness consuming the
JSON is Claude Code (the IDE session running `/sq:run`), `model_switch`
is informational only — the IDE session itself performs the dispatch
and silently ignores the user's chosen non-SDK model. The user types
`/sq:run P4 183 --param model=minimax` expecting minimax to do the
design work; instead, the calling Claude Code session does it.

This slice mirrors slice 164's fix on the dispatch axis, plus closes a
related bug in the SDK dispatch path: API errors surfaced as
SDK assistant messages with `is_error=True` are absorbed as normal
response text (the existing `_check_cli_error` only catches the literal
`"API Error:"` text-prefix shape) and written into design files as if
the model produced them.

## Problem Statement

Three concrete defects:

1. **Prompt-only dispatch ignores resolved profile.**
   `src/squadron/pipeline/prompt_renderer.py:_render_dispatch` (lines
   123–145) returns the same `ActionInstruction` regardless of profile.
   Non-SDK profiles need a `command` the slash handler can run; SDK
   profiles need the current "in-session" path.

2. **No invocation target for one-shot dispatch.** The slash handler
   needs a Bash-runnable entry point that performs a one-shot agent
   dispatch — analogous to slice 164's hidden `sq _summary-run` for
   the summary axis. Today no such target exists for dispatch.

3. **SDK dispatch silently swallows API errors.**
   `src/squadron/pipeline/actions/dispatch.py:_dispatch_via_session`
   relies on `_check_cli_error` matching a literal `"API Error:"`
   prefix on the response text. The Agent SDK can surface an API
   error as an assistant message whose metadata flags `is_error=True`
   without a recognisable text prefix; the existing check misses
   it and `success=True` is returned with the error JSON as the
   "response", which downstream actions (cf-op artifacts, review
   inputs) write to design files.

## Goals

- `/sq:run P4 X --param model=minimax` (from inside Claude Code IDE)
  routes the dispatch to minimax via OpenRouter, not to the calling
  Claude Code session.
- `sq run P4 X --param model=minimax` from a real terminal routes the
  same way through the agent path (already works in SDK action via
  `_dispatch_via_agent`; this slice ensures the prompt-only renderer
  it produces also surfaces the right thing if a prompt-only flag is
  later added — but the canonical path is `_dispatch_via_agent`).
- `sq run P4 X` with the default (Claude/SDK) model continues to use
  the SDK session (`_dispatch_via_session`) as today.
- SDK dispatch fails the action explicitly when the SDK reports an
  API error, instead of writing the error JSON into the design output.

## Non-Goals

- No changes to `CLAUDECODE` env detection or any other interactive-vs-
  scripted heuristic.
- No changes to checkpoint guard semantics.
- No transport-protocol abstraction or `ReviewTransport`-style
  refactor (those belong to the in-flight review-decoupling work,
  not this slice).
- No retry / backoff redesign for SDK API errors. This slice surfaces
  the failure; recovery policy stays where it lives today.

## Design

### 1. Prompt-only dispatch renderer

Update `_render_dispatch` in `src/squadron/pipeline/prompt_renderer.py`
to mirror the structure of `_render_summary` (lines 240–306):

- Accept a `ModelResolver` (already passed via `_BUILDERS` dispatch
  for `ActionType.DISPATCH`).
- Resolve the alias: `model_id, profile = resolver.resolve(alias)`.
- If `is_sdk_profile(profile)` (or no model specified): emit the
  current `instruction` + `model_switch` shape, no `command`.
- Otherwise: emit a runnable `sq _dispatch-run` command and **omit**
  `model_switch`. The `instruction` text changes to
  `"Run the `command` field via Bash. Capture stdout as the dispatch
  response."` so the slash handler can dispatch it the same way it
  dispatches review.

The non-SDK command shape:

```
sq _dispatch-run \
  --prompt-file <path> \
  --model <resolved-id> \
  --profile <profile> \
  --param key=value …
```

`--prompt-file` is preferred over `--prompt` because the assembled
context (output of `cf build`) is multi-kilobyte and Bash arg-length
limits make inline passing fragile. The slash handler writes the
prompt text to a temp file before invoking the command. Equivalent
to how the existing review command writes review inputs to a temp
file before passing them in.

The renderer signature changes from `(config, params)` to
`(config, params, resolver)`, matching `_render_summary`. Update
`_BUILDERS` dispatch in `_build_action_instruction` to pass the
resolver to `DISPATCH` (it already does this for `DISPATCH` and
`SUMMARY` together, so this is a one-line check).

### 2. Hidden `sq _dispatch-run` subcommand

New file `src/squadron/cli/commands/dispatch_run.py` registering a
**hidden** Typer subcommand `sq _dispatch-run` (leading underscore,
`hidden=True` — not shown in `--help`). This mirrors slice 164's
`sq _summary-run` and slice 157's PreCompact hook target: an
internal invocation surface for slash-handler use only, not a
public CLI primitive.

Hidden because (a) the public pipeline orchestrator surface is
`sq run` and its flags; (b) the slash handler is the only intended
caller; (c) keeping it hidden avoids the breaking-change surface
of a documented `sq _dispatch-run` (review F001) and matches the
established convention for slash-handler invocation targets.

Argument shape:

| Arg / flag           | Type         | Description |
| -------------------- | ------------ | ----------- |
| `--prompt-file`      | `Path`       | Path to file containing prompt. Required. |
| `--model`            | `str`        | Resolved model id or alias. Required. |
| `--profile`          | `str | None` | Provider profile. If absent, resolved from alias via `ModelResolver`. |
| `--param key=value`  | `list[str]`  | Repeated; collected into a dict (forwarded to `AgentConfig`-relevant fields where applicable). |
| `--system-prompt`    | `str | None` | Optional system prompt. |

Inline `--prompt` is intentionally omitted — the slash handler
always stages a temp file because assembled context is multi-KB.
Keeping the surface minimal also keeps the breaking-change risk
small even though it's hidden.

Behaviour:

1. Read prompt text from `--prompt-file`.
2. Resolve model + profile via `ModelResolver` if `--profile` was
   not given.
3. Call shared `_one_shot_dispatch` helper (see below).
4. Print the response on stdout. Errors print to stderr with
   non-zero exit.

Factor a private helper `_one_shot_dispatch(prompt, model_id,
profile_name, system_prompt)` into
`src/squadron/pipeline/actions/dispatch.py` that
`DispatchAction._dispatch_via_agent` and the new hidden command
both call. The helper owns the existing
spawn-agent → send-message → collect → shutdown sequence currently
inlined in `_dispatch_via_agent`. The hidden command becomes
~30 lines: parse args, read file, call helper, print result.

Register in `src/squadron/cli/app.py` next to other hidden
subcommands (`_summary-run`, etc.).

### 3. `/sq:run` slash command update

In `~/.claude/commands/sq/run.md` (or its source under
`src/squadron/data/commands/`), the `### dispatch` section
becomes branched on the presence of the `command` field:

```
### dispatch
If the `command` field is present:
  Run it via Bash. Capture stdout as the dispatch response.
  Write the response to the appropriate artifact path (next cf-op
  or review action will use it).
Else:
  This is in-session work — you perform the task described in
  `instruction`. If `model_switch` is present, note the recommended
  model for the user.
```

This mirrors the review and summary sections, which already branch
on `command` vs other fields.

The slash handler is responsible for writing the assembled-context
prompt to a temp file before running the dispatch command — the
prompt-only renderer cannot stage files because it produces JSON
only. The renderer emits `command` with a `--prompt-file
{tmp_path}` placeholder; the slash handler replaces `{tmp_path}`
after writing the file. (Alternative: emit a `prompt_text` field
alongside `command` and let the handler write the file. Decision
in tasks; both are mechanically simple.)

### 4. SDK synthetic-error fix

`_check_cli_error` in `dispatch.py` extends to also detect SDK
API-error messages. Two complementary checks:

- Keep the literal-prefix check (`"API Error:"`) for backwards
  compatibility with the Claude CLI's text-prefix error format.
- Add a metadata-driven check: have `SDKExecutionSession.dispatch`
  propagate a per-message `is_error` flag (sourced from the SDK
  message structure — `APIErrorMessage` / `is_error=True` in the
  agent SDK's translated assistant message). When any message in
  the response has `is_error=True`, raise `ProviderAPIError` from
  `dispatch()` rather than returning the joined text.

The action layer's existing `try/except ProviderAPIError` (via the
generic `Exception` handler at the top of `execute`) already turns
this into `ActionResult(success=False, error=…)`. Pipeline executor
flow control then halts.

This is the only change to `_dispatch_via_session`. The text-prefix
check in `_check_cli_error` stays as a defence-in-depth backstop.

### Data flow

```
/sq:run P4 183 --param model=minimax
  └─ slash handler calls: sq run --prompt-only --next ...
       └─ executor → _render_dispatch(config, params, resolver)
            ├─ resolver.resolve("minimax") → ("minimax-…", "openrouter")
            ├─ is_sdk_profile("openrouter") → False
            └─ ActionInstruction(
                  action_type="dispatch",
                  command="sq _dispatch-run --prompt-file {tmp} --model minimax-… --profile openrouter …",
                  instruction="Run the command field via Bash …",
               )
       └─ slash handler stages prompt file, runs command
            └─ sq _dispatch-run → _one_shot_dispatch → registry → minimax response
       └─ slash handler captures stdout → next action (review / cf-op)
```

SDK profile path is unchanged: `model_switch` only, no `command`,
slash handler does the work in-session.

### Failure Modes

Each new I/O path with its observable signal and handling strategy:

**`sq _dispatch-run` subprocess invocation by slash handler.**

- *Subprocess hang.* No timeout enforced inside `sq _dispatch-run`
  itself — the underlying agent's `handle_message` loop owns the
  network timeout (provider-level, already bounded). The slash
  handler's Bash invocation inherits the harness's overall turn
  timeout; no additional wrapper-level timeout is added.
  Observable: provider error logged at ERROR via the existing
  `_logger.exception` path in `_dispatch_via_agent`.
- *Subprocess crash mid-output.* Bash returns non-zero; slash
  handler treats non-zero exit as a dispatch failure (same shape
  as a failed `sq review`). Pipeline halts with the standard
  failed-action handling.
- *Non-zero exit code without stderr.* `_dispatch-run` always
  writes a one-line error to stderr before exiting non-zero;
  silent failure is a bug.

**Temp-file staging by slash handler.**

- *Temp directory not writable.* Slash handler uses `mktemp` (or
  the harness's standard temp path); failure is a Bash error
  before invocation, surfaces as a dispatch failure to the user.
- *Orphan temp files.* Slash handler removes the temp file in a
  trailing cleanup step regardless of dispatch outcome (Bash
  `trap` or equivalent in the slash command body). Prompts are
  not secret in this pipeline — leakage risk is low — but
  cleanup is still mandatory to avoid `/tmp` accumulation across
  many runs.
- *Encoding.* Prompt is written as UTF-8 bytes; `_dispatch-run`
  reads with explicit `encoding="utf-8"`. Multi-KB content is
  the expected case (cf-built context is typically 5–50 KB).

**`_one_shot_dispatch` helper via agent registry.**

- *Agent spawn failure.* `registry.spawn` raises; the helper
  re-raises (caller wraps in `try/except` at the action /
  CLI boundary). Observable via `_logger.exception` and
  non-zero exit from `sq _dispatch-run`.
- *Profile not registered.* `ensure_provider_loaded(profile.provider)`
  raises a clear error; same handling as spawn failure.
- *Partial response on agent crash.* Existing behaviour: response
  parts collected so far are joined and returned. The
  `_check_cli_error` text-prefix check and the new `is_error`
  metadata check (see SDK synthetic-error fix) catch the
  in-band error case. For an out-of-band crash (the agent's
  async iterator raises), the exception propagates and the
  action fails — partial output is discarded, not written to
  artifacts.
- *No response.* Empty string returned; `DispatchAction` writes
  it to outputs as today. Downstream review/cf-op detect empty
  artifacts via their own validation (out of scope here).

**SDK API error in `_dispatch_via_session`.**

- *`is_error=True` message in stream.* Surface as
  `ProviderAPIError` from `SDKExecutionSession.dispatch`; existing
  `try/except` in `DispatchAction.execute` returns
  `ActionResult(success=False, error=…)`. Pipeline halts.
- *Literal `"API Error:"` prefix in response text.* Existing
  `_check_cli_error` path retained as backstop. Same outcome.
- *Both signals missing but response is malformed JSON written
  by the model.* Out of scope — this is a model-quality issue,
  not an I/O failure mode. Review/cf-op consumers handle their
  own validation.

### Performance Notes

The non-SDK dispatch path itself is not new — `_dispatch_via_agent`
already spawns a one-shot agent for non-SDK profiles when called
directly from the SDK pipeline executor. This slice adds **one
extra subprocess hop** in the prompt-only / slash-handler path:
slash handler → `sq _dispatch-run` (Python+Typer cold start) →
existing `_one_shot_dispatch` → existing agent code.

Cold-start overhead for `sq _dispatch-run` is the same as any
other `sq …` invocation — Python interpreter + Typer init,
roughly 200–400 ms on a warm filesystem. For a dispatch whose
model latency is 5–60 s, the added overhead is in the noise
(<10 % at the floor, <1 % typical) and matches the cost
already paid by every `sq review` invocation in the same
pipeline. No NFR target exists in
`140-arch.pipeline-foundation.md` for dispatch latency; none is
introduced here. If pipeline-wide cold-start cost ever becomes
material, the architectural answer is the deferred SDK Client
Warm Pool (slice 139) and its analogues, not per-action
optimisation.

## Cross-Slice Dependencies

- **Slice 145 (Dispatch Action)**: extends the existing dispatch
  action; reuses `_dispatch_via_agent` machinery via factored helper.
- **Slice 164 (Profile-Aware Summary Model Routing)**: this slice
  is the dispatch-axis mirror of 164. The shape of the prompt-only
  renderer change is identical; reuse `is_sdk_profile()` predicate
  from `summary_oneshot.py`.
- **Slice 119 (Review Provider & Model Selection)**:
  `run_review_with_profile()` is the precedent pattern for the
  one-shot helper that `sq _dispatch-run` wraps.
- **Slice 164 / 157 conventions**: `sq _dispatch-run` follows the
  hidden-subcommand pattern established by `sq _summary-run` (164)
  and the PreCompact hook target (157). No public CLI surface
  added.

No interface contracts change for other actions or step types.
The `ActionInstruction` dataclass already carries `command` —
this slice just populates it for dispatch.

## Success Criteria

1. `/sq:run P4 183 --param model=minimax` from inside Claude Code IDE
   produces a step JSON whose dispatch action has a `command` field
   invoking `sq _dispatch-run … --profile openrouter …` and **no**
   `model_switch`. `sq _dispatch-run` is hidden from `sq --help`.
2. The slash handler runs that command via Bash and captures stdout
   as the dispatch response — no in-session dispatch by Claude Code.
3. `sq _dispatch-run --prompt-file <f> --model minimax --profile openrouter`
   from a real terminal returns minimax's response on stdout.
4. `/sq:run P4 183` (no `--param model`) from inside Claude Code IDE
   continues to emit the in-session "you perform the task" instruction
   with no `command` field.
5. From a real terminal, `sq run P4 183` with default model continues
   to use the SDK session path (`_dispatch_via_session`).
6. When the SDK session surfaces an API error message
   (`is_error=True`), the dispatch action returns
   `ActionResult(success=False, error=…)` and the pipeline halts;
   no error JSON appears in any artifact file.

## Test Plan

Unit tests (`tests/pipeline/test_prompt_renderer.py`):

- `test_render_dispatch_sdk_profile_emits_in_session_instruction` —
  resolver returns `("claude-…", "sdk")` → instruction has
  `model_switch`, no `command`.
- `test_render_dispatch_non_sdk_profile_emits_command` — resolver
  returns `("minimax-…", "openrouter")` → instruction has `command`
  starting with `sq _dispatch-run`, no `model_switch`.
- `test_render_dispatch_no_model_param` — no model alias →
  in-session instruction (default behaviour preserved).

Unit tests (`tests/cli/test_dispatch_run_command.py`):

- `test_dispatch_run_with_prompt_file` — given a temp prompt file
  and a fake provider, returns response on stdout.
- `test_dispatch_run_resolves_profile_from_alias` — `--profile`
  omitted, alias resolves to non-SDK profile, agent config carries
  correct profile.
- `test_dispatch_run_errors_when_prompt_file_missing` — non-existent
  `--prompt-file` → exit code != 0, stderr message.
- `test_dispatch_run_hidden_from_help` — `sq --help` output does
  not contain `_dispatch-run`.

Integration test
(`tests/pipeline/test_dispatch_synthetic_error.py`):

- `test_sdk_session_api_error_fails_action` — fake
  `SDKExecutionSession` whose `dispatch` raises `ProviderAPIError`;
  `DispatchAction.execute` returns `success=False` with the error
  text.
- `test_sdk_session_is_error_message_fails_action` — fake session
  yields a message with `is_error=True` metadata; dispatch raises
  `ProviderAPIError` and action returns `success=False`.

End-to-end manual (in verification walkthrough below).

## Risks

- **`sq _dispatch-run` is the slash handler's contract.** Even
  though hidden from `--help`, the arg shape is a contract between
  the prompt-only renderer and the slash handler — changing it
  requires coordinated updates to both. Mitigation: keep the
  surface minimal (the table above) and treat it the same way
  `sq _summary-run` is treated — internal but stable across
  patch releases, version-bumped on breaking change.
- **SDK error-detection heuristic.** The Agent SDK's `is_error`
  marker is the documented signal, but the propagation path through
  `SDKExecutionSession.dispatch` adds one place where new SDK
  versions could change shape. Mitigation: keep the text-prefix
  check as a backstop, and assert the `is_error` path in the
  integration test using a fake session (no live SDK dependency).

## Verification Walkthrough

This is the demo script the user will run after implementation.
It assumes a squadron project at the current working directory with
CF initialized and at least one design slice (e.g. 183).

**Step 1 — In-IDE non-SDK model routes through agent path.**

Inside Claude Code (IDE session, model = whatever):

```
/sq:run P4 183 --param model=minimax
```

Expected:
- Slash handler runs `sq run --prompt-only --next …` for each step.
- For the dispatch action, the JSON contains a `command` field
  starting with `sq _dispatch-run … --profile openrouter …`.
- The slash handler runs the command via Bash; the IDE Claude
  session does **not** generate the design output.
- `~/.config/squadron/runs/<run-id>/state.json` shows the dispatch
  step's `metadata.profile == "openrouter"` (or equivalent for the
  resolver's chosen profile).
- The design file produced under `project-documents/user/slices/`
  is the work of minimax, not the IDE session.

**Step 2 — Real-terminal non-SDK model routes through agent path.**

In a real terminal:

```
sq run P4 183 --param model=minimax
```

Expected:
- Same routing as Step 1. `_dispatch_via_agent` runs (it already
  handles non-SDK profiles correctly).
- Same design file content as Step 1 (modulo model nondeterminism).

**Step 3 — Real-terminal default model uses SDK session as today.**

In a real terminal:

```
sq run P4 183
```

Expected:
- `_dispatch_via_session` path runs (default profile is SDK).
- Behaviour identical to current main; nothing in this slice
  affects the default path.

**Step 4 — SDK API error halts the pipeline cleanly.**

(Reproducer is artificial — a fake `SDKExecutionSession` that
raises `ProviderAPIError` from `dispatch`. The integration test
exercises this; manual verification is optional but useful when
the SDK actually emits an error in production.)

Expected:
- Pipeline state shows the dispatch step with `status=failed`
  and `error` populated.
- No design file is written for the failed step.
- `sq run --status` shows the run as halted at the dispatch step.

**Step 5 — `sq _dispatch-run` standalone (debug-only).**

```
echo "Write a haiku about pipelines." > /tmp/p.txt
sq _dispatch-run --prompt-file /tmp/p.txt --model minimax
```

Expected:
- Resolves `minimax` → `(model_id, openrouter)` via the registry.
- Spawns one-shot agent, prints the haiku on stdout.
- Exit code 0 on success.

Note: `sq _dispatch-run` does **not** appear in `sq --help`. It
is an internal invocation target for the slash handler, exposed
only because the slash command runs it via Bash. Direct invocation
is supported as a debugging affordance, not a user-facing surface.
