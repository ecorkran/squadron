---
docType: slice-design
slice: isolated-file-in-file-out-dispatch-steps
project: squadron
parent: user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: []
interfaces: []
dateCreated: 20261102
dateUpdated: 20261102
status: not_started
turns: 41
promptTokens: 3224738
cachedTokens: 3112296
cacheWriteTokens: 112364
completionTokens: 29580
durationSeconds: 314.9
costUsd: 2.11591
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-opus-5-5:
    rounds: 1
    costUsd: 2.1159101999999996
    completionTokens: 29580
---

# Slice Design: isolated-file-in-file-out-dispatch-steps

## Overview

Amoeba needs a two-step answering pipeline whose steps see only the files and replies they are given ([issue #284](https://github.com/ecorkran/squadron/issues/284)). The installed `sq` cannot run it. This slice adds five things:

1. A dispatch step can add file contents to its prompt.
2. A dispatch step can add an earlier step's reply to its prompt, with a documented JSON extraction rule.
3. A dispatch step can write its reply and its delivered prompt to files.
4. `allowed_tools: []` becomes a hard guarantee that the step runs with no tools.
5. `sq run --validate --strict` rejects any step key the step type does not know.

## Value

- **Amoeba:** can run its answering pipeline on stock `sq`. Its start-up probe (`--validate --strict`) proves the installed `sq` knows every key the pipeline uses, so an older `sq` fails at probe time and not halfway through a run.
- **Pipeline authors:** a misspelled or retired step key is caught by `--validate --strict`, and plain `--validate` lists it as a warning. Today it is silently ignored.
- **Safety:** `allowed_tools: []` means what it says. Today a step that declares it can still read files through the SDK session (confirmed on 0.24.12 with a haiku step).

## Technical Scope

**Included**
- New dispatch step keys: `prompt_files`, `reply_from`, `reply_format`, `reply_file`, `delivered_prompt_file`.
- A JSON reply extractor (the one documented rule) and a step-reply reader.
- A tool-isolation guard in `DispatchAction`, applied before any model call.
- A required `known_keys` property on every step type, plus an optional `ContainsSteps` protocol so strict validation can reach inner steps.
- `validate_pipeline(..., strict=...)`. `sq run --validate --strict` fails on unknown keys, and plain `--validate` lists them as warnings.
- `docs/PIPELINES.md` (new dispatch keys, strict validation) and a CHANGELOG bullet.

**Excluded**
- The tool-isolation guard on review and summary steps. Both take `allowed_tools`, but the issue and the plan entry cover dispatch steps only.
- Unknown-key checks in plain `sq run`. Its behavior is unchanged.
- Stopping project rules from being added to an isolated step's system prompt. Rules are chosen by the project's own rule `steps:` filter, which can already exclude `dispatch`.
- A list of steps for `reply_from`. It takes one step name.

## Dependencies

### Prerequisites
None. Everything this slice extends is already on `main`: the dispatch step and action, `ProviderCapabilities.can_read_files`, `FailureKind`, `prior_outputs` keyed by step name (#170), resume restoring `prior_outputs` (#219), and the existing `--strict` flag on `sq run`.

### Interfaces Required
- `ProviderCapabilities.can_read_files` (`providers/base.py`). SDK and Codex declare `True`, OpenAI-compatible declares `False`.
- `prior_output_key(step_name, action_type, index)` (`pipeline/models.py`) for finding an earlier step's dispatch result.
- `ActionContext.cwd`, the run's working directory. All new file paths resolve against it.

## Architecture

### Component Structure

| Component | Location | Change |
|---|---|---|
| `DispatchStepType` | `pipeline/steps/dispatch.py` | Validates the new keys. `expand` forwards every key in `FORWARDED_KEYS`. `known_keys` is built from that same tuple. |
| `reply_io` (new) | `pipeline/actions/reply_io.py` | `ReplyFormat` enum, `extract_json_object(text)`, `step_reply(result)`, `read_prompt_files(paths, cwd)`, `write_step_files(...)`, path containment check. |
| `DispatchAction` | `pipeline/actions/dispatch.py` | Builds the isolated prompt body, runs the isolation guard, extracts JSON replies, writes the output files on success. |
| Isolation guard | `pipeline/actions/tool_support.py` | `tool_isolation_error(context, provider_capabilities) -> str \| None`, next to `resolve_allowed_tools`. |
| `StepType` protocol | `pipeline/steps/protocol.py` | Adds the required `known_keys: frozenset[str]` property and the optional `ContainsSteps` protocol. |
| Step types (all 11 modules) | `pipeline/steps/*.py` | Each declares `known_keys`. `loop`, `each` and `fan_out` implement `ContainsSteps.inner_steps`. |
| Strict key walker | `pipeline/steps/known_keys.py` (new) | `COMMON_STEP_KEYS` and `unknown_key_errors(steps)`, which recurses through `ContainsSteps`. |
| `validate_pipeline` | `pipeline/loader.py` | Takes `strict: bool` and adds unknown-key errors when it is set (see D9). Checks that `reply_from` names an earlier dispatch step. |
| `sq run` | `cli/commands/run.py` | Passes `--strict` to `validate_pipeline` when `--validate` is set. Prints warnings. |
| `FailureKind` | `pipeline/failure_kind.py` | Adds `TOOL_ISOLATION`, `REPLY_NOT_JSON` and `STEP_IO`. |

### Data Flow

Answering pipeline, step A (`draft`) then step B (`answer`):

```
draft:  prompt + read(prompt_files...) ──► model (no tools) ──► raw reply
          │                                                     │ reply_format: json
          │                                                     ▼
          │                                        extract_json_object(raw)
          │                                          none? ─► FAIL (REPLY_NOT_JSON), write nothing
          ▼                                                     ▼
   delivered_prompt_file ◄── on success only ──► reply_file  (extracted span, byte for byte)
                                                   outputs["reply"] = extracted span
answer: prompt + read(prompt_files...) + step_reply(draft) ──► model ──► reply ──► files
```

**Delivered prompt layout.** These parts, in this order, are joined with one blank line (`"\n\n"`). Missing parts are left out, and no part is stripped or decorated:
1. the step's `prompt` text (after the usual `{param}` substitution of step config)
2. each file in `prompt_files`, in the order listed, read as UTF-8 and used verbatim (`{...}` inside a file is never substituted)
3. the reply of the step named by `reply_from`

The existing checkpoint override and `pre_emption_fragment` prefixes are then added as they are today. The pre-emption fragment is only added when the step declares it. The override is a human decision made at a checkpoint.

**Isolated body.** When a step sets `prompt_files` or `reply_from`, its prompt body is the layout above and nothing else. It never falls back to a `build_context` output or prior review findings. That is the point of isolation.

**File contents are never substituted.** `resolve_placeholders` runs on step config, which holds file *names*. File *contents* are read inside the action, after substitution has already run, so they never pass through it.

### State Management

- `ActionResult.outputs["response"]` is unchanged: it is the raw text reply.
- New `outputs["reply"]`, set only when `reply_format: json`, holds the extracted object span. `step_reply(result)` returns `outputs["reply"]` if present and `outputs["response"]` otherwise. It is the only reader.
- Both keys are in run state, so on a resumed run `_seed_resume_outputs` restores what a later `reply_from` step reads. No state-format change.
- The files written to the working directory belong to the run's caller. Squadron does not record them in state beyond `metadata["written_files"]`, which lists the paths.

## Technical Decisions

### D1 — Key names
Status: decided
- `prompt_files` (list of paths; a single string is accepted as a one-item list), `reply_from` (step name), `reply_format` (`text` | `json`, default `text`), `reply_file` (path), `delivered_prompt_file` (path).
- `reply_from` follows the existing `judge_from` / `review_from` naming. `delivered_prompt_file` uses the requirement's own wording; `prompt_file` was rejected because it reads as an input.
- `ReplyFormat` is a `StrEnum`. Code compares against it, never against the bare string.

### D2 — JSON extraction rule
Status: decided
- Scan the raw reply for each `{` in order. At each one, call `json.JSONDecoder().raw_decode(text, idx)`. The first call that succeeds gives the object, and the extracted value is the substring `text[idx:end]`, byte for byte. It is never re-serialized.
- Code fences are not treated specially: scanning the raw text covers fenced and unfenced replies alike.
- A `{` can only open an object, so a successful decode is always a JSON object.
- No match means the step fails with `FailureKind.REPLY_NOT_JSON`. The error message names the step and the rule.
- This rule is documented once in `docs/PIPELINES.md` and once in the extractor's docstring.

### D3 — What "the earlier step's reply" is
Status: decided
- It is the earlier step's latest dispatch result in `prior_outputs` (keys prefixed `{step}:dispatch-`), read through `step_reply`. It never includes the prompt, tool calls or tool output.
- For a tool-less step, which Amoeba's steps are, this is the model's single final turn. For a step with tools it is the assistant text the step already records as `response`. Inventing a separate "last turn only" capture would add a second meaning of "reply" for no requested use.
- At load time, `validate_pipeline` checks that `reply_from` names a step earlier in the same list whose type is `dispatch`, as it does for gate references. At run time, a missing result fails the step with a message naming the reference. It never sends an empty reply.

### D4 — Output files are written only on success, atomically
Status: decided
- `reply_file` and `delivered_prompt_file` are written after the dispatch succeeded and, for JSON steps, after extraction succeeded. Each file is written to a temporary file in the same directory and then `os.replace`d into place, so a reader never sees partial text.
- A failed step does not touch either file, so an existing file is left as it was.
- A write error fails the step with `FailureKind.STEP_IO`. If the delivered prompt write succeeds and the reply write then fails, the prompt file stays (the requirement allows "leaves one already written"). The reply file is either untouched or complete.
- The write order is delivered prompt first, then reply. A reply file that exists always comes from a run whose prompt was recorded.
- The atomic write reuses `batch_report._write_atomic`, moved to a shared helper in `reply_io` that `batch_report` imports. One implementation.

### D5 — Paths are relative and contained in the working directory
Status: decided
- Every path in the new keys is resolved against `ActionContext.cwd`. An absolute path, or a path that resolves outside cwd (`..`, a symlink escape), is rejected.
- Literal values are checked at load time. Values that contain `{param}` are checked at run time after substitution (the loader's existing convention for param-valued fields).
- A missing or unreadable `prompt_files` entry fails the step before dispatch with `FailureKind.STEP_IO`. The message names the file. No model call is made.

### D6 — The tool-isolation rule: tool-less means a provider that cannot read files
Status: decided
- A step is *tool-less* when `allowed_tools` is present and equal to `[]`. `None` (key absent) keeps today's meaning.
- Before any model call, `DispatchAction._dispatch` resolves the step's profile the way `_dispatch_via_agent` does (`params["profile"]`, else the alias profile, else `ProfileName.SDK`) and looks up the provider's capabilities. If the step is tool-less and `capabilities.can_read_files` is `True`, the step fails with `FailureKind.TOOL_ISOLATION`. The error text starts `tool isolation:` and names the step, model and provider.
- This one test covers every case the issue names. The SDK session path is always the SDK provider (`can_read_files=True`). The SDK one-shot path has the CLI's file access and settings. Codex reads files natively in its sandbox. OpenAI-compatible providers declare `False`, and with `[]` they are offered no tools (`resolve_effective_tools([])` returns `[]`, and the default write-step tools apply only when `allowed_tools is None`).
- The guard runs before the routing split, so the session path's truthiness check is no longer the only gate. That check stays for non-empty lists, where its message is still correct.
- Rejected: letting the SDK one-shot path pass `tools=[]`. That turns off built-in tools, but MCP servers and settings loaded from `setting_sources` remain. The issue explicitly lists "a provider that reads files natively" as a failure case, and `can_read_files` is the capability that already says so.
- This changes run-time behavior for any existing pipeline that has `allowed_tools: []` on an SDK or Codex dispatch step. That is the plan entry's stated Medium risk, and it is the requested fix. CHANGELOG states it.

### D7 — Content keys and isolation are independent
Status: decided
- `prompt_files`, `reply_from` and the output files work on any provider, tool-less or not. Isolation is requirement 4's job, chosen by declaring `allowed_tools: []`. A step that uses the content keys on the SDK session path still sees that session's conversation. `docs/PIPELINES.md` says so next to the keys.
- Combining `feedback` with `prompt_files` or `reply_from` is a validation error. `feedback: review` adds review findings to the prompt, which contradicts an isolated body.
- Combining `reply_format: json` with `artifact` is not restricted. They are unrelated.

### D8 — One known-keys list per step type, shared by validate and expand
Status: decided
- `StepType` gains the required property `known_keys: frozenset[str]`. Every registered type declares it. A type that forgets fails pyright and the registry test, not a user's run.
- Dispatch defines `FORWARDED_KEYS` (the keys `expand` copies into the action config). `expand` iterates over it in place of the current five `if` statements, and `known_keys = frozenset(FORWARDED_KEYS) | {ARTIFACT_KEY}`. The list `expand` uses and the list strict validation checks are the same object.
- Branch's existing `_ALLOWED_KEYS` becomes its `known_keys`. Its always-on unknown-key error stays as it is.
- `COMMON_STEP_KEYS = {"step_model"}` holds keys the executor and classifier read from any step's config. `name` is removed by the schema before a step type sees its config, so it is not a key.
- Inner steps: the optional `ContainsSteps` protocol (`inner_steps(config) -> list[StepConfig]`) is implemented by `loop` and `each` (their `steps` list, through `unpack_inner_steps`) and by `fan_out` (its single `inner`). The walker checks for the protocol, not for concrete classes, as the executor does for `RunPreflight`.
- Each type's list is built from the keys its `validate` and `expand` read, and from what its action reads out of params (for example `checkpoint`). A test running every built-in pipeline under strict validation catches a missing key.

### D9 — `--strict` with `--validate`; warnings without it
Status: decided
- `sq run` already has `--strict` (eager session construction), and `--validate` ignores it today. When combined with `--validate`, `--strict` means strict key validation. The issue asks for exactly `--validate --strict`, and Amoeba's probe depends on it. The flag's help text gains one clause describing this.
- `unknown_key_errors(steps)` (in `known_keys.py`) returns one `ValidationError` per unknown key. `validate_pipeline(definition, strict=False)` keeps its return type and appends those errors only when `strict` is set. Its six existing callers in `run.py` pass nothing and are unchanged.
- The `--validate` branch calls `unknown_key_errors` itself when `--strict` is absent and prints the results as yellow warnings, keeping its exit code. `--validate --strict` exits 1 and lists each key with its step name and the step type's known keys.

### Technology Choices
- Standard library only: `json.JSONDecoder.raw_decode`, `os.replace`, `pathlib`. No new dependencies.

### Patterns and Conventions
- Failures are `ActionResult(success=False)` with a `FailureKind` stamped where the failure is decided (slice 177 D4), one log line at WARNING or above, and no traceback. They are never silent.
- Values that are compared (`ReplyFormat`, `FailureKind`, key names) are defined once and referenced everywhere.
- `reply_io.py` stays well under 300 lines. `dispatch.py` is already 994 lines, so the new logic goes into `reply_io` and `tool_support`, and the action only calls them.

## Implementation Details

### API Contracts

Dispatch step keys added by this slice:

| Key | Type | Default | Meaning |
|---|---|---|---|
| `prompt_files` | list[str] \| str | absent | Files in cwd whose content is added after `prompt`, in order, verbatim. |
| `reply_from` | str | absent | Name of an earlier dispatch step. Its reply is added after the files. |
| `reply_format` | `text` \| `json` | `text` | `json`: extract one object (D2). No object fails the step. |
| `reply_file` | str | absent | Path in cwd. Holds the reply (the extracted object for `json`). Written on success only. |
| `delivered_prompt_file` | str | absent | Path in cwd. Holds the exact prompt sent. Written on success only. |

Example pipeline (the shape Amoeba runs):

```yaml
steps:
  - dispatch:
      name: draft
      model: "{model}"
      allowed_tools: []
      prompt: "Answer the question below. Reply with one JSON object."
      prompt_files: [question.md, context.md]
      reply_format: json
      reply_file: draft.json
      delivered_prompt_file: draft.prompt.md
  - dispatch:
      name: answer
      model: "{model}"
      allowed_tools: []
      prompt: "Check this draft against the question and return the final answer."
      prompt_files: [question.md]
      reply_from: draft
      reply_file: answer.md
```

New `FailureKind` values: `tool_isolation`, `reply_not_json`, `step_io`. None of them pauses a run.

CLI:

```
sq run <pipeline> --validate            # unchanged exit; unknown keys printed as warnings
sq run <pipeline> --validate --strict   # exit 1 on any unknown step key
```

## Integration Points

### Provides to Other Slices
- `--validate --strict` as a capability probe for any supervisor (Amoeba first).
- `known_keys` on every step type, and the `ContainsSteps` walker, available to future tooling (for example a pipeline linter or editor schema).
- `step_reply` / `extract_json_object` for any future step that consumes another step's reply.

### Consumes from Other Slices
- Provider capability declarations. A new provider that can read files must set `can_read_files=True`, or tool-less steps would run on it. This is the capability's existing contract, not a new one.

## Success Criteria

### Functional Requirements
- [ ] A dispatch step with `prompt` and `prompt_files: [a.md, b.md]` delivers `prompt + "\n\n" + a + "\n\n" + b`. A `{x}` inside `a.md` arrives unchanged even when the pipeline declares a param `x`.
- [ ] A step with `prompt_files` or `reply_from` never uses a `build_context` output or review findings as its prompt.
- [ ] A missing `prompt_files` entry fails the step before any model call, with `failure_kind: step_io` and the file named.
- [ ] `reply_from: draft` adds draft's reply text and nothing from draft's prompt. On a resumed run started after `draft`, the restored reply is used.
- [ ] With `reply_format: json`, a reply ```` "Sure:\n```json\n{\"a\": 1}\n```" ```` gives exactly `{"a": 1}`. A reply `"x {not json} {\"b\": [1]} tail"` gives `{"b": [1]}`. A reply with no object fails the step with `failure_kind: reply_not_json`.
- [ ] `reply_file` for a JSON step holds the bytes a later `reply_from` step receives. `delivered_prompt_file` holds the exact delivered prompt.
- [ ] A failed step (provider error, isolation refusal, no JSON object) leaves existing `reply_file` / `delivered_prompt_file` contents unchanged and creates neither when they are absent.
- [ ] An absolute path or `..` escape in any new path key is a validation error (literal) or a step failure (param-valued).
- [ ] `allowed_tools: []` on a step that resolves to an SDK model (session or one-shot) or a Codex model fails before dispatch with `failure_kind: tool_isolation`. On an OpenAI-compatible model it runs with no tools offered.
- [ ] `reply_from` naming a later step, an unknown step, or a non-dispatch step is a validation error.
- [ ] `feedback` combined with `prompt_files` or `reply_from` is a validation error.
- [ ] `sq run p --validate --strict` exits 1 on an unknown key anywhere, including inside `loop`/`each` bodies and `fan_out.inner`, and names the step and key. Plain `--validate` exits 0 for the same pipeline and prints the key as a warning. Plain `sq run` is unchanged.

### Technical Requirements
- [ ] Every registered step type declares `known_keys`. Dispatch's `expand` and `known_keys` both come from `FORWARDED_KEYS`.
- [ ] Every built-in pipeline in `src/squadron/data/pipelines/` passes `--validate --strict` (test).
- [ ] Unit tests for `extract_json_object` (fenced, unfenced, leading invalid `{`, nested braces in strings, no object, top-level array ignored in favor of an object inside it), path containment, and atomic write behavior on failure.
- [ ] Each new failure kind has a test asserting the stamped `failure_kind` and a WARNING-or-higher log line.
- [ ] `ruff format`, `ruff check`, `pyright` (zero errors), and the pipeline test suite pass.
- [ ] `docs/PIPELINES.md` documents the five keys, the prompt layout, the JSON rule, the isolation rule, and `--validate --strict`. The CHANGELOG has one bullet for the new keys and strict validation, and one for the `allowed_tools: []` behavior change.

### Integration Requirements
- [ ] The example pipeline from API Contracts runs end-to-end on an OpenAI-compatible model and produces `draft.json`, `draft.prompt.md` and `answer.md`, with `answer`'s delivered prompt containing draft's extracted JSON.

### Verification Walkthrough

Run in a scratch directory with an OpenAI-compatible alias configured. This walkthrough uses `{model}`, a pipeline param: pass `-p model=<alias>`, where `<alias>` is one listed by `sq models` whose profile is not `sdk` and not Codex.

1. Set up the inputs:
   ```bash
   mkdir /tmp/sq949 && cd /tmp/sq949
   printf 'What is 2+2? Literal braces stay: {model}\n' > question.md
   printf 'Context: arithmetic.\n' > context.md
   ```
   Save the API Contracts example as `answering.yaml`, with a top-level `params: {model: null}`.

2. Strict validation passes:
   ```bash
   sq run ./answering.yaml --validate --strict
   ```
   Expect `Pipeline 'answering' is valid.` and exit 0.

3. Strict validation catches a typo. Change `reply_file` to `reply_fiel` in step `answer`, then:
   ```bash
   sq run ./answering.yaml --validate            # exit 0, yellow warning naming reply_fiel
   sq run ./answering.yaml --validate --strict   # exit 1, names step 'answer', key 'reply_fiel', known keys
   ```
   Undo the typo.

4. Run it:
   ```bash
   sq run ./answering.yaml -p model=<alias>
   cat draft.prompt.md   # prompt, blank line, question.md (with literal {model}), blank line, context.md
   cat draft.json        # one JSON object only, no fence
   cat answer.md
   ```
   Confirm that `draft.prompt.md` contains the literal `{model}`, and that `answer`'s delivered prompt (visible with `-vv`) ends with the exact contents of `draft.json`.

5. Failure leaves files alone. Note `cat draft.json`. Edit `draft`'s prompt to "Reply in plain prose, no JSON." and rerun. Expect the run to fail at `draft` with `reply_not_json` (`sq run --status latest`), and `draft.json` to be unchanged.

6. Isolation guard. Set both steps' `model` to an SDK alias (for example the pipeline default when no model is given) and rerun. Expect failure at `draft` before any model call, error text starting `tool isolation:`, and `failure_kind: tool_isolation` in `sq run --status latest -v`. The run reports no spend for the step.

## Risk Assessment

### Technical Risks
- **Behavior change for `allowed_tools: []` on SDK/Codex steps** (D6). An existing pipeline that has it, and relied on the SDK ignoring it, will now fail.

### Mitigation Strategies
- The failure is immediate, named, and spends nothing. The message says to use a model whose provider cannot read files, or to remove `allowed_tools: []`. The CHANGELOG states the change. No built-in pipeline or template uses `allowed_tools: []` (checked: the only declarations in `src/squadron/data` are non-empty lists).

## Implementation Notes

### Development Approach
1. `known_keys` on the protocol and all step types, `ContainsSteps`, the walker, `validate_pipeline(strict)`, and the CLI wiring. Test: built-in pipelines pass strict. This is self-contained and gives Amoeba its probe first.
2. Tool-isolation guard and `FailureKind.TOOL_ISOLATION`, with tests on SDK session, SDK one-shot, Codex and OpenAI-compatible routes (mocked providers).
3. `reply_io`: extractor, containment, prompt-file reading, atomic write (move `_write_atomic`). Pure unit tests.
4. Dispatch step keys (validation and `FORWARDED_KEYS`), the isolated body in `_resolve_prompt`, JSON extraction and file writes in the action, the loader check for `reply_from`, and the `feedback` conflict check.
5. Executor-level test running the two-step example with a fake provider: prompt layout, reply handoff, files, failure leaving files alone, and resume after `draft`.
6. Docs and CHANGELOG.

### Special Considerations
- **Security:** path containment (D5) stops a pipeline param from making a step read or write outside the run's working directory.
- **Ordering in `_dispatch`:** the isolation guard runs after the `existing: keep` short-circuit (which makes no model call) and before routing, so it covers both the session path and the agent path from one place.
