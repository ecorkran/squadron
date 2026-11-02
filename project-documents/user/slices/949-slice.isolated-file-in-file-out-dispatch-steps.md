---
docType: slice-design
slice: isolated-file-in-file-out-dispatch-steps
project: squadron
parent: project-documents/user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: []
interfaces: []
dateCreated: 20261102
dateUpdated: 20261102
status: complete
turns: 79
promptTokens: 6620822
cachedTokens: 6458405
cacheWriteTokens: 162297
completionTokens: 47293
durationSeconds: 498.7
costUsd: 3.536754
usageRounds: 3
pricedRounds: 3
usageByModel:
  claude-opus-5-5:
    rounds: 3
    costUsd: 3.5367545999999996
    completionTokens: 47293
revision_number: 2
---

# Slice Design: isolated-file-in-file-out-dispatch-steps

## Overview

Fixes [issue #284](https://github.com/ecorkran/squadron/issues/284). Amoeba (a separate project that supervises Squadron pipelines) needs a two-step answering pipeline. Each step sees only the files and replies it is given and writes its result to a named file. The installed `sq` cannot run that pipeline today. The dispatch step forwards only `prompt`, `model`, `pre_emption_fragment`, `allowed_tools` and `feedback`. `allowed_tools: []` does not stop an SDK model from reading files. `--validate` accepts any key, so a probe cannot tell whether the installed `sq` supports the pipeline.

This slice adds five things to the `dispatch` step: file content in the prompt, an earlier step's reply in the prompt, reply and delivered-prompt files, a hard no-tools guarantee, and opt-in strict key validation.

## Value

- **Amoeba:** can run its answering pipeline on stock `sq`, and its start-up probe (`sq run <pipeline> --validate --strict`) proves the installed `sq` knows every key the pipeline uses.
- **Pipeline authors:** a dispatch step can be used as a pure function. It takes named files in and writes named files out, and the delivered prompt is on disk to inspect. On a dispatch step, `allowed_tools: []` is now enforced: a model that would have tools or file access fails before it is called.
- **Maintainers:** every step type declares the keys it accepts in one place, so a misspelled or retired key can be found mechanically.

## Technical Scope

**Included**

1. Five new dispatch-step keys: `prompt_files`, `reply_from`, `reply_format`, `reply_file`, `delivered_prompt_file` (D1).
2. Prompt assembly from `prompt`, the listed files and the earlier reply, with no placeholder replacement inside file content (D2).
3. The reply hand-off: `reply_from` names an earlier top-level dispatch step and receives its reply (D3). With `reply_format: json`, only the extracted JSON object is passed on (D4).
4. Reply and delivered-prompt files, written only when the step succeeds (D5).
5. The no-tools guard for dispatch steps declaring `allowed_tools: []` (D6).
6. A `known_keys` set on every step type, and `sq run <pipeline> --validate --strict` (D7, D8).
7. Prompt-only mode rejects dispatch steps that use the new keys (D9).
8. `docs/PIPELINES.md` dispatch section, `--strict` help text and a CHANGELOG bullet.

**Excluded**

- The no-tools guard on `review` and `summary` steps. Both accept `allowed_tools`, but plan entry item (4) is scoped to dispatch. On those steps `allowed_tools: []` keeps today's behavior, and docs and CHANGELOG say the guarantee is for dispatch steps only.
- Warnings for unknown keys under plain `--validate` or `sq run`. The plan entry keeps both unchanged.
- `reply_from` inside `loop`, `each` or `fan_out` bodies (D3). It is rejected at load time.
- System-prompt content. Project rules configured for `dispatch` steps (slice 935) are still appended to the system prompt. That is project configuration, not step input, and an author who wants none configures none.
- Changing what `response` means for multi-turn tool runs (D3, note).

## Dependencies

### Prerequisites

None, matching the plan entry. The provider capability declarations this slice reads (`can_read_files`, and slice 945's `runs_squadron_tools`) are already in the code; slice 945 is complete.

### Interfaces Required

- `squadron.core.file_write.write_new_file(path, content, force=True)`: the existing whole-file replace, used unchanged for each output file (D5).
- `ProviderCapabilities.can_read_files` (`providers/base.py`): `True` for the `sdk` and `openai-oauth` (Codex) providers, `False` for the `openai` provider. This is the capability the no-tools guard tests. It never tests provider identity.
- `prior_output_key()` (`pipeline/models.py`): top-level steps' results are keyed `{step}:{action_type}-{index}` in `prior_outputs`, both in a live run and after `_seed_resume_outputs` restores them on resume.
- The `inner_steps(config)` method that `LoopStepType`, `EachStepType` and `FanOutStepType` already implement.
- Run state persists `ActionResult.outputs` (`state.py`), so a resumed run gets the earlier step's reply back.

## Architecture

### Component Structure

| Component | Change |
|---|---|
| `pipeline/steps/dispatch.py` | `DISPATCH_FORWARDED_KEYS`, the single key list that `expand` iterates and that `known_keys` builds from. Validation of the new keys' shapes, and the path check (relative, no `..`; placeholder values skipped at load time). |
| `pipeline/steps/protocol.py` | `StepType.known_keys: frozenset[str]` (required). |
| every step type module | Declares its `known_keys` constant. |
| `pipeline/loader.py` | `validate_pipeline(definition, *, strict: bool = False)`. Adds `_validate_reply_references` (top-level references, like `_validate_gate_references`, and rejection of `reply_from` in container bodies) and `unknown_key_errors` (strict only). |
| `pipeline/actions/dispatch_io.py` (new) | `assemble_prompt`, `extract_json_object`, `step_reply`, `write_step_files`, `DispatchInputError`, `ReplyFormat`. Holds the file and reply logic so `actions/dispatch.py` (already ~1000 lines) gains only the call sites. |
| `pipeline/actions/tool_support.py` | `declares_no_tools(context)` and `tool_isolation_error(...)`. |
| `pipeline/actions/dispatch.py` | `_dispatch` resolves the route and the prompt once, runs the guard, calls the path, then applies the reply contract. |
| `pipeline/failure_kind.py` | `FailureKind.TOOL_ISOLATION`. |
| `pipeline/prompt_renderer.py` | `_render_dispatch` raises for the new keys (D9). |
| `cli/commands/run.py` | `--validate` passes `strict`. `--strict` help covers both meanings. |

### Data Flow

Run time, one dispatch step:

```
_kept_outputs (unchanged)
  → route: session | agent(profile → provider capabilities)
  → if allowed_tools == []: tool_isolation_error(route) ─fail→ FailureKind.TOOL_ISOLATION
  → resolve prompt (to_thread):
        prompt text
        + each prompt_files entry, read as UTF-8 from cwd, verbatim
        + step_reply(named step's result)                    ─fail→ DispatchInputError
        joined by "\n\n"; then override / pre-emption prefixes as today
  → dispatch via session or agent (unchanged internals; receives the ResolvedPrompt)
  → on success (to_thread):
        reply_format json: extract_json_object(response)     ─none→ failed step
        write delivered_prompt_file, then reply_file         ─OSError→ restore prompt file, failed step
  → ActionResult(outputs={"response": …, ["reply_json": …]})
```

A later step reads `prior_outputs` for `{named}:dispatch-*`. Its reply is `outputs["reply_json"]` when present, else `outputs["response"]`.

### State Management

The only addition to persisted state is `outputs["reply_json"]` on a successful `reply_format: json` dispatch: the exact substring passed on and written to `reply_file`. `outputs["response"]` still holds the full reply. The new `tool_isolation` value is recorded in `metadata["failure_kind"]` the same way as existing ones, and it does not pause a run. Written file paths are not recorded, because the pipeline author already named them.

## Technical Decisions

### D1 — Key names and shapes
Status: decided
- `prompt_files: [path, …]`: a non-empty list of strings. A bare string is a validation error that says to use a list. One form keeps both the parser and the docs single.
- `reply_from: <step name>`
- `reply_format: text | json`, a `ReplyFormat` StrEnum. Absent means `text`, which is today's behavior (no extraction).
- `reply_file: path`, `delivered_prompt_file: path`
- Paths are resolved against the run's `cwd` and must be relative with no `..` part. That check runs at load time. A value containing a `{param}` placeholder skips the load-time check (the gate-reference convention) and gets the same check at run time. Symlinks are not resolved: pipelines are trusted author content, and this check only catches mistakes. `reply_file` and `delivered_prompt_file` must differ.
- `feedback` combined with `prompt_files` or `reply_from` is a validation error, because the feedback prompt is built from review findings and the two prompt sources would conflict.
- Rejected: the singular `prompt_file` from the issue's probe, which cannot express "in the order listed". Also rejected: allowing both a string and a list.

### D2 — Prompt assembly
Status: decided
- When `prompt`, `prompt_files` or `reply_from` is present, the prompt is built from those keys and nothing else, in this order: `prompt`, then each file, then the reply. Parts are joined by one blank line (`"\n\n"`). A step with only `prompt` is unchanged.
- File content is read in `DispatchAction` after `resolve_placeholders` has already run on the step config, so `{…}` text inside a file is never substituted. Placeholders in the *path values* are resolved, as for any config value.
- Override instructions and the pre-emption fragment are prepended afterwards, as today. The delivered-prompt file records the final text, so whatever was added is visible.
- `PromptSource` stays `EXPLICIT`. The identity hash covers the full delivered text.
- Each entry must be a regular file. `Path.is_file()` is checked before opening, which rejects missing paths, directories, FIFOs and devices, so a read cannot block on a pipe. The read catches `OSError` (including `PermissionError`) and `UnicodeDecodeError`. Each of these raises `DispatchInputError` naming the path. `execute` catches it, logs at WARNING and fails the step before any model call.
- No size limit. An oversized prompt is refused by the provider and surfaces as today's `provider_error`.

### D3 — Reply hand-off scope and lookup
Status: decided
- `reply_from` is supported only on a **top-level** step, and must name an **earlier top-level `dispatch` step**. `_validate_reply_references` checks both at load time. It recurses into container bodies through `inner_steps` and rejects any nested `reply_from` with "reply_from is supported on top-level steps only". The plan entry records this narrowing. Restricting to top level avoids the three different key schemes used inside loop, each and fan-out bodies. Amoeba's pipeline is two top-level steps.
- Lookup: `results_for_step(prior_outputs, step_name)` in `models.py`, next to `prior_output_key`, so the key format is defined in one module. It returns the step's results in order. `step_reply` takes the last `dispatch` result.
- The reading step fails with `DispatchInputError` naming the step when the named step has no dispatch result in scope, its result is a failure, or its result has no `response` (for example, a step that kept an existing artifact and skipped the call). An empty reply is never passed on.
- On resume, the named step's result comes from `_seed_resume_outputs`. The rules above apply unchanged.
- Note: the reply is the step's recorded `response`. For a step with tools on a multi-turn provider, that is the joined text of its turns. For a step under the no-tools guard (D6), it is the single final reply. Changing `response` is out of scope.

### D4 — JSON extraction rule
Status: decided
- `extract_json_object(text) -> str | None`: for each `{` in `text`, in order, call `json.JSONDecoder(parse_constant=_reject).raw_decode(text, i)`. The first call that succeeds returns `text[i:end]`, the original substring, never re-serialized. A span that starts at `{` and decodes is always an object. Code fences are not special-cased: the scan sees through them.
- `parse_constant` rejects `NaN`, `Infinity` and `-Infinity`, so the object is valid strict JSON for any consumer.
- No match: the step that **declares** `reply_format: json` fails with the error "reply contains no JSON object" (no new `FailureKind`). `outputs["response"]` is kept for diagnosis, and no files are written.
- Rejected: taking the first fenced block, or the last object. The issue fixes the rule.

### D5 — Output files
Status: decided
- Written only after a successful dispatch and a successful extraction. `reply_file` gets `reply_json` for a JSON step and `response` otherwise. `delivered_prompt_file` gets the delivered prompt text. Both are UTF-8 and nothing is appended (no trailing newline).
- Each file is written with the existing `write_new_file(..., force=True)` (temp sibling, then replace), so each target is replaced whole and partial reply text is never written. `delivered_prompt_file` is written first and `reply_file` last.
- Before writing, the step reads the prompt file's current bytes, or notes that it is absent. If the `reply_file` write fails, the prompt file is restored to those bytes, or removed if it did not exist. A failed step therefore leaves both files as they were.
- Any `OSError` fails the step with an error naming the path. If the restore itself fails, that is logged at ERROR naming the prompt file. This is the one case where a failed step leaves a changed file, and the log says so.
- Extraction and writes run in `asyncio.to_thread`. Prompt-file reads do too. The scan in D4 is quadratic in the worst case and must stay off the event loop.

### D6 — No-tools guard
Status: decided
- `declares_no_tools(context)`: `allowed_tools` is present and equals `[]`. An absent key keeps today's behavior.
- `tool_isolation_error(route)` returns an error when the step would run on the SDK session path (a persistent session with a fixed tool set), or on the agent path whose provider has `capabilities.can_read_files`. The agent path's profile comes from one helper, `_agent_profile_name`, shared with `_dispatch_via_agent`, so the guard and the call cannot disagree about the provider.
- The guard runs in `_dispatch` after routing and before prompt assembly. The failed result carries `FailureKind.TOOL_ISOLATION`. The error names the step, the model and the provider, and says to use a model whose provider runs no tools of its own (for example an `openrouter` alias).
- The existing session-path guard (`if resolve_allowed_tools(...)`) keeps its truthiness test for non-empty lists. The new check covers `[]`.
- Behavior change: an existing `allowed_tools: []` on an SDK or Codex dispatch step now fails. No built-in pipeline or template uses it (checked `src/squadron/data/`).

### D7 — Known keys per step type
Status: decided
- `StepType.known_keys` is required on the protocol, so a step type without it fails pyright. Each module defines the set as a module constant beside its validate and expand code.
- Dispatch: `known_keys = DISPATCH_FORWARDED_KEYS | {ARTIFACT_KEY}`. `expand` forwards exactly `DISPATCH_FORWARDED_KEYS`. This is the "one list shared by validate and expand" the plan asks for.
- Keys the executor reads on any step, `loop` and `step_model` (`executor.py`), are one constant, `EXECUTOR_STEP_KEYS`. `unknown_key_errors` adds it to every step type's set, so it is not repeated in each set.
- Rejected: a central table of keys per type in the loader, which would drift away from the modules that read the keys.

### D8 — `--validate --strict`
Status: decided
- `validate_pipeline(definition, strict=False)` is unchanged when `strict` is false. When true, it adds `unknown_key_errors(definition.steps)`: one error per unknown key, `field=steps[<name>].<key>`. It recurses into `inner_steps(config)` for step types that have it, using the same `getattr` test `classification.py` uses. An unknown step type is already an error and is not recursed into.
- `sq run <pipeline> --validate --strict` prints the errors and exits 1. Plain `--validate` and `sq run` do not call the check. The existing `--strict` flag (eager session construction) is reused because the issue names this exact command. Its help text states both meanings.

### D9 — Prompt-only mode
Status: decided
- In `--prompt-only` and the slash-command path, the harness runs the dispatch itself, so Squadron cannot read the files, pass the reply, write outputs or enforce isolation. `_render_dispatch` raises a rendering error when the step config has `prompt_files`, `reply_from`, `reply_format`, `reply_file` or `delivered_prompt_file`. The message names the key and says to run with `sq run`. Failing explicitly keeps the two modes from giving different results without saying so.
- `allowed_tools: []` keeps today's prompt-only behavior, so existing pipelines are not broken. `docs/PIPELINES.md` states that only `sq run` enforces the no-tools guard.

### Patterns and Conventions

- Key names are constants in `steps/dispatch.py`, and the action reads them from there. No literal key strings are repeated across modules.
- Input failures before any model call go through `DispatchInputError` (WARNING, failed step). Classified failures use `FailureKind`. Unexpected exceptions still reach `execute`'s `logger.exception`.

## Implementation Details

### API Contracts

Pipeline YAML for Amoeba's shape:

```yaml
steps:
  - dispatch:
      name: extract
      model: deepseek4-flash
      allowed_tools: []
      prompt: "Extract the claims below as a JSON object."
      prompt_files: [question.md, source.md]
      reply_format: json
      reply_file: claims.json
      delivered_prompt_file: extract.prompt.md
  - dispatch:
      name: answer
      model: deepseek4-flash
      allowed_tools: []
      prompt_files: [answer-instructions.md]
      reply_from: extract
      reply_file: answer.md
      delivered_prompt_file: answer.prompt.md
```

Failure surface:

| Condition | When | Result |
|---|---|---|
| Bad key shape, absolute or `..` path, `reply_from` not naming an earlier top-level dispatch, `reply_from` inside a container body, `feedback` with the new prompt keys | `--validate`, `sq run` load | validation error |
| Unknown key | `--validate --strict` only | validation error |
| `allowed_tools: []` on a session-path or file-reading provider | before dispatch | failed, `failure_kind: tool_isolation` |
| Prompt file not a regular file, unreadable (`OSError`) or invalid UTF-8; no usable reply from the named step | before dispatch | failed, WARNING log, error names the path or step |
| No JSON object in a `reply_format: json` reply | after dispatch | failed, error names the step, no files written |
| Output file write error | after dispatch | failed, error names the path, prompt file restored, both targets unchanged |
| Prompt-file restore fails after a reply write error | after dispatch | failed, ERROR log naming the prompt file (D5) |

## Integration Points

### Provides to Other Slices

- Amoeba's answering pipeline and its `--validate --strict` start-up probe. This is an external consumer, so `interfaces` is empty.

### Consumes from Other Slices

- Provider capability declarations (slice 945 `runs_squadron_tools`, `can_read_files`). A new provider that sets `can_read_files` correctly is covered by the guard without any change here.

## Success Criteria

### Functional Requirements

1. A dispatch step with `prompt` and `prompt_files: [a.md, b.md]` delivers `prompt`, `a.md` and `b.md` in that order, joined by a blank line. `{slice}` text inside `a.md` arrives unchanged.
2. A step with `reply_from: extract` receives `extract`'s reply and not its prompt. When `extract` declares `reply_format: json` and replies with prose around a fenced object, only the object substring is received, byte for byte.
3. A `reply_format: json` step whose reply contains no JSON object (including one whose only candidate uses `NaN`) fails with "reply contains no JSON object" and writes no files.
4. On success, `reply_file` and `delivered_prompt_file` hold exactly the received reply (or the extracted object) and the delivered prompt. A failed step leaves both files, if they already existed, byte-identical to before, and creates neither. This includes a step whose `reply_file` write fails after the prompt file was written.
5. `allowed_tools: []` on a dispatch step that routes to the SDK session, an SDK one-shot or a Codex (`openai-oauth`) model fails before any model call with `failure_kind: tool_isolation`. On an `openai`-provider model it runs with no tools offered.
6. `reply_from` naming a later step, a non-dispatch step or a missing step, or set on a step inside a loop, each or fan-out body, fails validation. A named step with a failed or skipped result fails the reading step with an error naming it, including on resume.
7. `sq run p --validate --strict` exits 1 and lists each unknown key with its step, including keys on nested steps. `sq run p --validate` on the same file exits 0 as today.
8. Every built-in pipeline in `src/squadron/data/pipelines/` passes `--validate --strict`. This is the check that each step type's `known_keys` is complete.
9. `--prompt-only` on a pipeline using any new key fails with a message naming the key.

### Technical Requirements

- Unit tests: `extract_json_object` (parametrized: bare, fenced, prose before and after, nested, malformed outer with valid inner, `NaN`, none), `assemble_prompt`, path checks (absolute, `..`, placeholder), prompt-file read failures (missing, directory, FIFO, permission denied, invalid UTF-8), output writes with a failure injected on the `reply_file` write (prompt file restored, and removed when it was new) and on the restore (ERROR logged), `tool_isolation_error` across capabilities, and `unknown_key_errors` with nested steps.
- Observable-signal tests: each failure row in the API Contracts table asserts its signal, using `caplog` for the WARNING or ERROR record and `metadata["failure_kind"]` for `tool_isolation`.
- Executor-level tests with a stub provider: the two-step pipeline above, end to end, files on disk; resume from the second step reads the restored reply.
- `ruff format`, `ruff check` and `pyright` with zero errors. New modules stay under ~300 lines.

### Integration Requirements

- Amoeba's probe pipeline from the issue (`allowed_tools: []`, the file keys) validates under `--validate --strict` once its keys use this slice's names.
- `docs/PIPELINES.md` documents the five keys, the JSON rule, the file-write guarantee, the dispatch-only and `sq run`-only scope of the no-tools guard, `reply_from` being top-level only, and `--validate --strict`.
- CHANGELOG notes the new keys and the behavior change: `allowed_tools: []` on an SDK or Codex dispatch step now fails.

### Verification Walkthrough

Run from the root of a project registered with Context Forge: `sq run` checks `cf` before it starts, and it refuses to run in an unregistered directory. Paths in the pipeline are relative to that root, so the files live in a scratch subdirectory, `.sq949/`, which you delete at the end. `glm-flash` is an `openrouter` alias (the `openai` provider, `can_read_files: false`). Any fast openrouter alias works. `haiku` is `sdk`; `luna` is `openai-oauth` (Codex).

1. Create inputs:
   ```bash
   mkdir -p .sq949
   printf 'Question: what is 2+2? Literal braces: {slice}\n' > .sq949/question.md
   printf 'Answer in one sentence using the JSON you are given.\n' > .sq949/answer-instructions.md
   ```
2. Save the API Contracts YAML as `.sq949/answer.yaml`, with `source.md` removed from `prompt_files`, every path prefixed `.sq949/`, `model: glm-flash`, and a header the API Contracts block omits:
   ```yaml
   name: answer
   description: Two isolated steps that answer a question from a file
   ```
   Validate:
   ```bash
   sq run ./.sq949/answer.yaml --validate --strict
   ```
   Expected: `Pipeline 'answer' is valid.`, exit 0. (Verified.)
3. Add `colour: red` to the `extract` step (a line under `name: extract`) and repeat. Expected: exit 1, printing `steps[extract].colour: unknown key 'colour'; dispatch accepts [...]` followed by the accepted keys, which include the five new ones. Then run `sq run ./.sq949/answer.yaml --validate`. Expected: `Pipeline 'answer' is valid.`, exit 0, unchanged behavior. Remove the key and confirm `--validate --strict` is valid again. (Verified.)
4. Run it:
   ```bash
   sq run ./.sq949/answer.yaml
   cat .sq949/extract.prompt.md   # prompt text, a blank line, then question.md verbatim, "{slice}" intact
   cat .sq949/claims.json         # one JSON object, nothing else
   cat .sq949/answer.prompt.md    # answer-instructions.md, then the claims.json bytes
   cat .sq949/answer.md
   ```
   Expected: both steps `completed`, and `cmp <(tail -c "$(wc -c < .sq949/claims.json)" .sq949/answer.prompt.md) .sq949/claims.json` reports no difference. `answer.prompt.md` does not contain `extract`'s prompt. A prompt file's own trailing newline plus the blank-line separator shows as two blank lines before the reply. (Verified with `glm-flash`.)
5. Isolation: change `extract`'s model to `haiku` and run it. Expected: the step fails before any model call, with an error naming the model (`claude-haiku-5-5`), the provider (`sdk`) and the route, and the run state records `"failure_kind": "tool_isolation"`. The printed text does not contain the word `tool_isolation`. `shasum .sq949/claims.json` is unchanged from step 4. Repeat with `luna` (Codex): same result, provider `openai-oauth`. (Verified.)
6. JSON failure: set `extract`'s prompt to "Reply with the word no." and run it. Expected: the step fails with `reply contains no JSON object`, and `claims.json` is unchanged. (Verified.)
7. Prompt-only: run `sq run ./.sq949/answer.yaml --prompt-only`. Expected: exit 1 and a one-paragraph error, with no traceback: `Error: step 'extract': dispatch step uses prompt_files, reply_format, reply_file, delivered_prompt_file, which prompt-only mode cannot honor; run the pipeline with `sq run``. (Verified.)
8. Clean up: `rm -r .sq949`.

## Risk Assessment

### Technical Risks

- Changing what `allowed_tools: []` means can break a user pipeline that set it on an SDK or Codex dispatch step and relied on it being ignored.
- Incomplete `known_keys` sets would make `--validate --strict` reject valid pipelines.

### Mitigation Strategies

- The guard's error says what to change. The CHANGELOG states the behavior change. Review and summary steps are untouched.
- Criterion 8 runs every built-in pipeline under `--strict`. Strict mode is opt-in, so a missed key cannot affect `sq run`.

## Implementation Notes

### Development Approach

1. `known_keys`, `--validate --strict`, and built-ins passing (D7, D8). This is independent and gives Amoeba a working probe first.
2. The no-tools guard and `FailureKind.TOOL_ISOLATION` (D6).
3. `dispatch_io`: assembly, files, reply lookup, extraction, writes (D1–D5), and the `_dispatch` restructure that resolves the prompt once.
4. Prompt-only rejection (D9), docs, CHANGELOG.

Effort: 3/5.

### Special Considerations

- As built: each path still resolves the prompt itself, through `asyncio.to_thread(self._resolve_prompt, context)`, because the routing tests pin the paths' signatures. The session path now resolves it before `set_model`, so an unreadable prompt file fails the step before the model switch. A `set_model` failure still records no prompt identity.
- As built: the key names, `ReplyFormat` and the shared path check live in `pipeline/dispatch_keys.py`, not `dispatch_io.py` (an import cycle otherwise). `LoopStepType`, `EachStepType` and `FanOutStepType` gained `body_steps`, because fan_out's `inner_steps` is a synthetic classification step; the nested-`reply_from` check and `unknown_key_errors` walk `body_steps`.
- As built: the built-in `P6`, `P56`, `P456`, `implement` and `implement-plan` close-out steps carried an ignored `slice:` key. Strict validation found it, and it was removed.
