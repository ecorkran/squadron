---
docType: slice-design
slice: dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success
project: squadron
parent: project-documents/user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: []
interfaces: []
dateCreated: 20261014
dateUpdated: 20261014
status: complete
---

# Slice Design: Dispatch Outcomes Match What Happened — Codex Tool Contract and Silent Success

## Overview

A dispatch step can report `completed`, `success: True` when the model did nothing. Issue #211 recorded four cases: Codex ignoring `allowed_tools` on a read-only sandbox, an OpenRouter write rejected by the working-directory guard, and a model emitting fake tool-call markup as text. Squadron already holds most of the evidence (tool counts, failed-call counts, whether tools were given) and drops it before the step result. This slice fixes three things:

- Providers refuse configurations they cannot honor before the model runs.
- Dispatch records the tool signals and fails steps that cannot have done their job.
- Two related outcome bugs: a raw traceback when cf has no slice plan (#202), and a hard-gate stop ending `completed` instead of `paused` (#212 item 2).

## Value

- A pipeline run's status matches what happened. A step that wrote nothing on a step that must write fails or pauses, and the run does not go on to merge.
- Run state records why: failed tool calls, their error text, and refused tool sets. Today the guard message only reaches stderr (#211 §3).
- A cf configuration problem prints one line that names its fix.

## Technical Scope

**Included**
1. **Write-required dispatch.** A dispatch is write-required when it comes from a phase step (`design`, `tasks`, `implement`) or has `feedback` set (a revise dispatch). `AgentConfig.requires_writes` carries this to the provider.
2. **Provider contract: refuse what you cannot honor** (D1, D2). Codex raises `ProviderError` at spawn in two cases: `allowed_tools` is declared, or `requires_writes` is set on a read-only sandbox. The OpenAI-compatible agent raises when `requires_writes` is set and no write-capable tool was given.
3. **Tool-outcome rules in dispatch** (D3). Copy `failed_tool_calls` and `first_tool_error` into step metadata. Log WARNING and fail per the D3 table.
4. **SDK failed-call count fix** (D4). `_translate_and_track` looks for `ToolResultBlock` as a top-level stream message, so the count never increments. Count it inside `UserMessage.content`.
5. **#202:** `ContextForgeError` from the slice lookup in the dispatch-artifact post-condition, and from dispatch's `existing: keep` lookup, becomes a one-line step failure with no traceback (D5).
6. **#212 item 2:** a hard-gate stop can no longer pass the merge gate when cf lists no task files, and a merge refused for unfinished task items ends the run `paused` instead of `failed` (D6).

Items 5 and 6 are assigned to this slice by the plan entry. They share no code with items 1–4, so they are implemented and committed separately.

**Excluded**
- Failing bare `dispatch` steps that declare no tools (see Plan Reconciliation).
- Honoring squadron tools inside Codex (for example by exposing them as an MCP server). Codex writes through its own tools when its sandbox allows it.
- Tool telemetry on the persistent SDK session path. It reports none today, and adding it is a separate change.
- #212 items 1 and 3 (merge with unchecked tasks; `concerns_or_better` merging CONCERNS). Item 1 stays tracked in #212.
- Parsing model prose for refusals.

### Plan Reconciliation
How each case the plan entry names is handled:

| Plan case | Handling |
|---|---|
| Codex ignores `allowed_tools` | D2 refusal (criterion 1) |
| A dispatch that must write on a read-only Codex sandbox | D2 refusal for write-required dispatches (D1, criterion 2) |
| A tool call that returned an error (#211 deepseek jail probe) | D3 row 2 fails it (criterion 4); row 3 warns otherwise |
| `allowed_tools` declared, no tools given | D2: Codex, the only provider that dropped them, now refuses |
| Zero tool calls on a step that needs them | D3 row 1; "needs them" means write-required (D1) |
| #211 luna probe, bare dispatch, no tools | Not failed. WARNING (criterion 3) |
| #211 deepseek probe, bare dispatch, no tools, fake tool-call markup | Not failed |

The plan fails a step "where the step cannot have done its job". A bare dispatch that declares no tools has declared no job beyond its text reply, so squadron cannot tell a refusal from an answer without parsing prose, which is excluded. The same two models on a phase or revise step fail: Codex by D2, deepseek by the OpenAI-compatible refusal (D2).

## Dependencies

### Prerequisites
None. The plan entry lists no dependencies. This slice builds on completed work:
- Slice 942 (complete): the checkbox merge gate (`_require_checked_tasks`), the close-out step, and failed-dispatch handling in loops.
- Slice 944, #200 (complete): a failed dispatch in a multi-step loop body ends the loop with the loop's `on_exhaust` status (`executor.py` `_execute_loop_body`, `_failed_dispatch_error`). Steps failed by this slice use that path unchanged.

### Interfaces Required
- `AgentConfig` (`core/models.py`): gains `requires_writes: bool = False`.
- `WRITE_TOOL_NAMES` (`tools/builtin/_shared.py`, re-exported from `tools/builtin`): a frozenset of the existing `WRITE_FILE_NAME` and `BASH_NAME`.
- Provider response metadata: the existing keys `tools_given`, `tool_calls_made`, and `failed_tool_calls`, plus the new `first_tool_error: str | None`.

## Architecture

### Component Structure

| Component | File | Change |
|---|---|---|
| Write-required predicate | `pipeline/actions/dispatch_rules.py` | `dispatch_requires_writes(params)`: true for a phase-step rules param or `feedback` set |
| One-shot dispatch | `pipeline/actions/dispatch.py` `one_shot_dispatch_with_telemetry` | Pass `requires_writes`; copy `failed_tool_calls` and `first_tool_error` |
| Outcome rules | new `pipeline/actions/dispatch_outcome.py` | `assess_tool_outcome(declared, requires_writes, telemetry) -> ToolOutcome` (D3) |
| Codex agent | `providers/codex/agent.py` | Spawn-time refusals |
| OpenAI-compatible agent | `providers/openai/agent.py` | Write-tool refusal; keep the first failed call's error text as `first_tool_error` |
| SDK agent | `providers/sdk/agent.py` | Count `ToolResultBlock.is_error` inside `UserMessage.content` |
| Write-capable tools | `tools/builtin/_shared.py` | `WRITE_TOOL_NAMES` constant |
| Dispatch-artifact post-condition | `events/builtin/dispatch_artifact.py` | Catch `ContextForgeError` and return a one-line failed outcome |
| Action result | `pipeline/models.py` `ActionResult` | `awaits_human: bool = False`: a failed action that is waiting on a person, not broken |
| Branch merge | `pipeline/branch_ops.py`, branch action | `BranchFailure.UNFINISHED_TASKS`; the branch action sets `awaits_human` for it |
| Executor | `pipeline/executor.py` | A failed action with `awaits_human` gives `PAUSED`, not `FAILED`. The executor reads no action-specific values |

### Data Flow

```
phase/revise step ──params──▶ DispatchAction._dispatch_via_agent
   requires_writes = dispatch_requires_writes(params)
   AgentConfig(allowed_tools, requires_writes, …) ──▶ registry.spawn
        Codex:  allowed_tools → ProviderError ; requires_writes ∧ read-only → ProviderError
        OpenAI: requires_writes ∧ no write tool given → ProviderError
   (ProviderError → one-line failed step, existing #200 path)
   handle_message ──▶ final metadata {tools_given, tool_calls_made, failed_tool_calls, first_tool_error}
   assess_tool_outcome(...) ──▶ ToolOutcome(fail_reason | None, warnings)
        warnings → logger.warning
        fail_reason → ActionResult(success=False, error=fail_reason, metadata=…)
```

### State Management
Nothing new is persisted. The new metadata keys reach `StepState.action_results` through the existing `asdict` serialization. A paused merge step writes the existing `CheckpointState` through `StateManager._append_step`, so `sq run --resume` re-runs the merge once the PM has finished or checked off the items.

## Technical Decisions

### D1 — Write-required is derived, not declared
No new pipeline key is added. Phase steps and revise dispatches exist to change files. Bare dispatch keeps its meaning: text-only unless it declares `allowed_tools`. The predicate lives in one function, and its inputs are the existing constants `RULES_STEP_PARAM` and the `feedback` param. Rejected: a per-step `writes: true` key. It adds config surface, and the cases it would cover beyond D1 are bare dispatches like P6's `close-out`, which runs on the SDK by default.

### D2 — Providers refuse at spawn
Provider-specific knowledge stays in the provider. The sandbox, for example, is a Codex credential that dispatch must not read. Refusing at spawn costs nothing, because no model call is made. The refusal messages name the fix:
- Codex with `allowed_tools`: "Codex does not run squadron tools; remove `allowed_tools` (Codex uses its own tools when its sandbox allows writes) or use a profile that supports them."
- Codex, read-only, write-required: "profile `<name>` runs Codex with a read-only sandbox; this step must write files. Set `sandbox = "workspace-write"` in the profile credentials."
- OpenAI-compatible, write-required, no write tool: "step must write files but has no write-capable tool; add `write_file` (or `bash`) to `allowed_tools`."
- Codex, read-only, not write-required (bare dispatch): no refusal. Log a WARNING.

The fix those messages name needed a way to set it: before this slice no profile could carry a `sandbox` value. `ProviderProfile.sandbox` (read from `providers.toml`, passed in `profile_credentials` only when set) is added here. The Codex message names the provider id where `<name>` stands, because `AgentConfig` does not carry the profile name.

### D3 — Which signals fail a step and which warn

| # | Signal (from final response metadata) | Outcome |
|---|---|---|
| 1 | Write-required, tools given, `tool_calls_made == 0` | **Fail**: "step must write files but made no tool calls" |
| 2 | `tool_calls_made > 0`, `failed_tool_calls == tool_calls_made`, and the step is write-required or its tools include one in `WRITE_TOOL_NAMES` | **Fail**: "every tool call failed", with `first_tool_error` |
| 3 | Any other `failed_tool_calls > 0` | **Warn**. A read-only step can still answer after a failed read or grep |

`failed_tool_calls` and `first_tool_error` are copied into step metadata so run state records why a step failed (#211 §3). Every row logs at WARNING with the step name. A write-required step whose tools the capability gate suppressed is already refused at spawn (D2), so it needs no row. The rows apply only where tool telemetry exists: OpenAI-compatible dispatches, and SDK one-shot dispatches that declare `allowed_tools`. SDK phase and revise steps on native tools, and the SDK session path, report no telemetry. Those are covered by the #15 post-condition (`design`, `tasks`) and by the merge gate (`implement`).

**#15 check (from the plan entry).** The no-artifact post-condition applies only to `design` and `tasks` (`steps/phase.py` `_EXPECTED_ARTIFACT_KIND`; `implement` maps to `None`). It does not apply to bare dispatch or revise dispatches. It catches a no-op design/tasks step on any provider, but only after the model has run. This slice adds earlier refusal (D2). It covers `implement` and revise dispatches on Codex (D2) and on OpenAI-compatible providers (rows 1–2), but not on the default SDK path, which has no telemetry. The #15 post-condition is unchanged.

### D4 — SDK failed-tool count
The claude-agent-sdk delivers `ToolResultBlock` inside `UserMessage.content`. The current `elif isinstance(sdk_msg, ToolResultBlock)` never matches, so `failed_tool_calls` is always 0 on the SDK path. Verified 20261014 against claude-agent-sdk 0.2.162: its message parser builds `ToolResultBlock` only inside the `"user"` case's `UserMessage`. Row 2 needs a real count, so the fix is in scope. A unit test with a `UserMessage` carrying an error `ToolResultBlock` asserts the count.

### D5 — cf errors in post-conditions are one line
In `dispatch_artifact._resolve_paths`, catch `ContextForgeError` next to `(ValueError, TypeError, FileNotFoundError)`. Return a failed `EventOutcome` whose error is the cf message, which already names the fix (for example "No slice plan configured. Set one with: cf set slicePlan <path>"). Use `error_kind` NONE so the executor does not rewrite it to `<action>: raised`. Dispatch's `_kept_artifact_paths` gets the same treatment: `ContextForgeError` becomes `ActionResult(success=False, error=…)` without reaching the generic `_logger.exception` handler. Both paths log the message at ERROR without `exc_info`. This is the same one-line form #200 gave `ProviderError`.

### D6 — Unfinished tasks at merge pause the run
A task-file hard gate is a task that requires an explicit PM confirmation before work proceeds (for example trading-data slice 128, "Hard Gate A — PM-confirmed backup"). The implementing agent stops there by design. Squadron's only deterministic evidence is the unchecked items the merge gate already finds, and the gate currently returns `FAILED`. The work is not wrong; it is waiting for a decision.

A run that ended `completed`, as #212 reports, means the merge gate passed. Reading `_require_checked_tasks` shows two ways that happens after a hard-gate stop:
- cf lists no task files for the slice. The gate loops over an empty list and passes. This slice closes that path.
- Close-out checked off the gated item. This is #212 item 1 (merge with unchecked work) and is not fixed here.

So:
- When `resolve_slice_info` returns no `task_files`, refuse the merge with `UNFINISHED_TASKS`: "slice N not merged: cf lists no task files for this slice, so its work cannot be verified."
- Add `BranchFailure.UNFINISHED_TASKS` and raise it from `_require_checked_tasks` when unchecked items remain. An unreadable task file stays `OTHER`, which still fails.
- The branch action returns `ActionResult(success=False, awaits_human=True)` for `UNFINISHED_TASKS`. The executor's action-failure branch returns `ExecutionStatus.PAUSED` for any failed action with `awaits_human`, and imports nothing from `branch_ops`. A later "pause instead of fail" outcome sets the same flag; the executor does not change. The run ends `paused`, exits 0 (existing PAUSED handling), and is resumable.
- Fan-out/batch flag classification (slice 197) maps `UNFINISHED_TASKS` the way it maps `OTHER` today. Batch items have no per-item pause.

**PM decision (20261014):** unchecked items at merge end the run `paused`, not `failed`. This changes slice 942's merge-gate status on purpose: unchecked work is waiting on a person, not broken.

**Partial fix of #212 item 2.** The #212 run (trading-ui, 0.21.7) has no run id yet, so which of the two paths above it took is unknown. This slice closes the empty-task-list path and pauses the honest-close-out case. If the run turns out to be the close-out path, it belongs to #212 item 1 and stays open there.

## Integration Points

### Provides to Other Slices
- `AgentConfig.requires_writes` and the D2 contract. Future providers must refuse a write-required config they cannot serve.

### Consumes from Other Slices
- 944/#200: a failed dispatch inside a multi-step loop body ends the loop with `on_exhaust`. A revise dispatch failed by D3 in P6's `revise-code` therefore ends at `checkpoint`, which is `paused`. In P4/P5 loops it ends with their configured `on_exhaust`. The single-step loop shape (`_execute_loop_step`) still treats an action failure as transient. No built-in pipeline uses that shape for a dispatch, so it stays as is.
- 942: the merge gate and close-out step, unchanged except for the failure kind.

## Success Criteria

### Functional Requirements
1. A Codex-profile dispatch that declares `allowed_tools` fails before any model call, with the D2 message. Run status is `failed`.
2. A Codex-profile phase step on a read-only sandbox fails before any model call, with the D2 message naming the `sandbox` credential.
3. A bare Codex dispatch on a read-only sandbox still runs and logs a WARNING.
4. An OpenRouter dispatch whose only `write_file` call is rejected by the jail fails. The step error contains the jail message, and the run state records `failed_tool_calls` and `first_tool_error`.
5. An OpenRouter `implement` step with no write-capable tool in `allowed_tools` fails at spawn.
6. A dispatch with some failed and some successful tool calls completes, with a WARNING and the counts in metadata.
7. `sq run P4 <slice>` with no cf slice plan prints one line with the cf message and no traceback. The step fails.
8. A P6 run whose task file still has unchecked items at merge, or whose slice has no task files listed by cf, ends `paused`, exit 0, and `sq run --resume <run-id>` re-attempts the merge.
9. SDK one-shot dispatches record a non-zero `failed_tool_calls` when a tool errors.

### Technical Requirements
- Unit tests for `assess_tool_outcome` cover each D3 row and the no-telemetry case.
- Provider tests cover each D2 refusal and the bare-dispatch WARNING. The SDK test covers the D4 count.
- Executor test: a failed action with `awaits_human` gives `PAUSED`, without it gives `FAILED`. Branch action test: `UNFINISHED_TASKS` sets `awaits_human`, `OTHER` does not. Branch test: unchecked items or an empty task-file list give `UNFINISHED_TASKS`, an unreadable file gives `OTHER`.
- Every new failure mode logs at WARNING or ERROR, and at least one test asserts the log record.
- `ruff format`, `ruff check`, and `pyright` with zero errors. The full test suite passes.
- CHANGELOG bullets for the user-visible changes (refusals, failed steps, the paused merge, one-line cf error). They name the providers the outcome rules cover (OpenAI-compatible, Codex refusals, SDK one-shot with `allowed_tools`) and do not claim coverage of the default SDK path.

### Integration Requirements
- P4/P5/P6 run unchanged on the default SDK profiles.
- The #200 loop path ends a loop on a D3-failed revise dispatch.

### Verification Walkthrough

Verified 20261014 on `squadron` 945 branch (`.venv/bin/sq`, 0.21.7 plus this slice) in a scratch git repo registered with cf (`cf init --name scratch-945 --lite`, then `cf guides install`). Probe pipelines are one-step YAML files of this shape (aliases `luna`, `deepseek4-flash`, `haiku` come from the packaged `models.toml`):

```yaml
name: probe-luna-tools
params: {}
steps:
  - dispatch: { name: probe, model: luna, allowed_tools: [write_file], prompt: "Write the text hi to a file named out.txt." }
```

OpenRouter steps need `OPENROUTER_API_KEY` in the environment of that command. Each step below ran as `sq run <file> -v`; "exit" is the process exit code.

1. **Codex refuses declared tools** (criterion 1): `probe-luna-tools.yaml`. Exit 1. Output: `dispatch: step probe failed: Codex does not run squadron tools; remove `allowed_tools` (Codex uses its own tools when its sandbox allows writes) or use a profile that supports them.` No Codex runtime started.
2. **Codex read-only phase step** (criterion 2):
   - `sq run P4 105 -m luna` on the default profile. Exit 1, `profile `openai-oauth` runs Codex with a read-only sandbox; this step must write files. Set `sandbox = "workspace-write"` in the profile credentials.`
   - Set the credential in `~/.config/squadron/providers.toml` (new in this slice; the key is `sandbox`, valid for a Codex profile):
     ```toml
     [profiles.openai-oauth]
     provider = "openai-oauth"
     auth_type = "oauth"
     sandbox = "workspace-write"
     ```
     Rerun: the refusal is gone and the dispatch runs (`-> ok (model=gpt-6-luna)`).
   - File-write check with a bare probe (`probe-luna-write.yaml`, prompt "Create a file named out-luna.txt containing the text hi."): read-only completes with the sandbox WARNING and writes nothing; `workspace-write` writes `out-luna.txt`.
   - Caveat: on the stub slice the P4 design agent declined to write ("waiting for the slice scope"), so a P4 design file was not produced; that is model behavior on an empty slice, not a squadron fault.
3. **Bare Codex dispatch** (criterion 3): `probe-luna-notools.yaml`. Exit 0, `completed`, and a WARNING: `Codex profile `openai-oauth` runs with a read-only sandbox; set `sandbox = "workspace-write"` in the profile credentials if this dispatch should write files`. Note a bare dispatch is not failed even though it cannot write (design, Excluded).
4. **Jail-rejected write** (criterion 4): `probe-ds-tools.yaml` (`deepseek4-flash`, `write_file`, prompt names `/tmp/outside-945.txt`). Exit 1, `every tool call failed: Error: path '/tmp/outside-945.txt' resolves outside the working directory and was rejected.` The run JSON (`~/.config/squadron/runs/run-*-probe-ds-tools-*.json`) holds `tools_given: ['write_file']`, `tool_calls_made: 1`, `failed_tool_calls: 1` and `first_tool_error`. The file was not created.
5. **Controls** (no regression): `probe-ds-inrepo.yaml` and an SDK `haiku` probe (no `allowed_tools`; an SDK step on the session path may not declare them) both exit 0 and write `out-ds.txt` / `out-haiku.txt`. `sq run P4 105 -m deepseek4-flash` is refused with `step must write files but has no write-capable tool; add `write_file` (or `bash`) to `allowed_tools`.` (criterion 5): the built-in phase steps give an OpenAI-compatible model no tools, so they could never write; they previously reported `completed`.
6. **#202** (criterion 7): in a cf project with no slice plan but a slice file `105-slice.stub.md`, `sq run P4 105 -m haiku`. Exit 1, no `Traceback` in the output (0 matches). The step error contains `No slice plan configured. Set one with: cf set slicePlan <path>`. The agent's final text is appended after it (design 909 D7), so the line does not end at the cf text. Without a slice file the run stops earlier at `cf set slice`; that error is cf's own.
7. **#212 paused merge** (criterion 8): a minimal pipeline `probe-merge.yaml` (`branch enter` then `branch merge`, slice 105) with a task file holding one unchecked item `**Task 2: Hard Gate: PM confirms X**` (cf set up with `cf set arch 100`, a slice plan listing slice 105). Exit 0, `Pipeline 'probe-merge' — paused`, step `branch-1: paused`, error `slice 105 not merged: 1 unchecked task item(s), first: **Task 2: Hard Gate: PM confirms X**. Finish or check them off, then rerun the merge.` Check the item, commit it on the slice branch, `sq run --resume <run-id>`: exit 0, `completed`, HEAD `merge: slice 105 — Stub` on `main`. P6 itself was not run; the merge step is the part D6 changes.

## Risk Assessment

### Technical Risks
- **False failures on row 1.** A legitimate revise dispatch could conclude that no change is needed and make zero tool calls. It now fails, and in P6 that ends the loop at `checkpoint`, which is `paused`. That is the correct human-decision outcome, not a lost run.
- **Codex users with the default read-only profile** will see phase steps refused where they previously "completed" while doing nothing. This is intended. The message names the one-line fix, and the CHANGELOG states it.

## Implementation Notes

### Development Approach
1. Add `WRITE_TOOL_NAMES` and `AgentConfig.requires_writes`, and the `dispatch_requires_writes` predicate.
2. D4: fix the SDK count first, since rows 2 and 3 depend on accurate counts.
3. OpenAI-compatible agent: `first_tool_error` capture and the write-tool refusal.
4. Codex agent: spawn refusals and the bare-dispatch WARNING.
5. `dispatch_outcome.py` and its wiring in `_dispatch_via_agent`, including the new metadata keys.
6. D5: cf one-line errors in the post-condition and the keep path.
7. D6: `UNFINISHED_TASKS` (including the empty task list), the executor mapping, and the batch flag mapping.
8. CHANGELOG, then the walkthrough.

Unit tests for each step mock the provider stream or registry. Walkthrough steps 1–4 use real providers; they are the only proof that the refusals fire on real configs.

### Special Considerations
- `first_tool_error` stores tool result text, which can include file paths from the working directory. It is truncated to a length defined once in the OpenAI agent module.
