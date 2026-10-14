---
docType: slice-design
slice: dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success
project: squadron
parent: project-documents/user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: [942, 944]
interfaces: []
dateCreated: 20261014
dateUpdated: 20261014
status: not_started
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
3. **Tool-outcome rules in dispatch** (D3). Copy `failed_tool_calls` and `tool_errors` into step metadata. Log WARNING and fail per the D3 table.
4. **SDK failed-call count fix** (D4). `_translate_and_track` looks for `ToolResultBlock` as a top-level stream message, so the count never increments. Count it inside `UserMessage.content`.
5. **#202:** `ContextForgeError` from the slice lookup in the dispatch-artifact post-condition, and from dispatch's `existing: keep` lookup, becomes a one-line step failure with no traceback (D5).
6. **#212 item 2:** a merge refused for unfinished task items ends the step, and therefore the run, `paused` instead of `failed` (D6).

**Excluded**
- Bare `dispatch` steps with no `allowed_tools`. These are legitimate text-only steps, and squadron cannot tell intent from prose. On a read-only Codex sandbox they log a WARNING (D2) but are not failed. The fake tool-call markup case (#211, deepseek with no tools) is in this class.
- Honoring squadron tools inside Codex (for example by exposing them as an MCP server). Codex writes through its own tools when its sandbox allows it.
- Tool telemetry on the persistent SDK session path. It reports none today, and adding it is a separate change.
- #212 items 1 and 3 (merge with unchecked tasks; `concerns_or_better` merging CONCERNS). One related finding is recorded for item 1 under Special Considerations.
- Parsing model prose for refusals.

## Dependencies

### Prerequisites
- Slice 942 (complete): the checkbox merge gate (`_require_checked_tasks`), the close-out step, and failed-dispatch handling in loops.
- Slice 944, #200 (complete): a failed dispatch in a multi-step loop body ends the loop with the loop's `on_exhaust` status (`executor.py` `_execute_loop_body`, `_failed_dispatch_error`). Steps failed by this slice use that path unchanged.

### Interfaces Required
- `AgentConfig` (`core/models.py`): gains `requires_writes: bool = False`.
- `ToolDescriptor` (`tools/models.py`): gains `writes: bool = False`. It is set on `write_file` and `bash`.
- Provider response metadata: the existing keys `tools_given`, `tool_calls_made`, and `failed_tool_calls`, plus the new `tool_errors: list[str]`.

## Architecture

### Component Structure

| Component | File | Change |
|---|---|---|
| Write-required predicate | `pipeline/actions/dispatch.py` | `dispatch_requires_writes(params)`: true for a phase-step rules param or `feedback` set |
| One-shot dispatch | `pipeline/actions/dispatch.py` `one_shot_dispatch_with_telemetry` | Pass `requires_writes`; copy `failed_tool_calls` and `tool_errors` |
| Outcome rules | new `pipeline/actions/dispatch_outcome.py` | `assess_tool_outcome(declared, requires_writes, telemetry) -> ToolOutcome` (D3) |
| Codex agent | `providers/codex/agent.py` | Spawn-time refusals; stamp `sandbox` in metadata |
| OpenAI-compatible agent | `providers/openai/agent.py` | Write-tool refusal; keep the first `_TOOL_ERROR_LIMIT` error texts as `tool_errors` |
| SDK agent | `providers/sdk/agent.py` | Count `ToolResultBlock.is_error` inside `UserMessage.content` |
| Tool registry | `tools/models.py`, `tools/builtin/*` | `ToolDescriptor.writes`; a lookup for write-capable names |
| Dispatch-artifact post-condition | `events/builtin/dispatch_artifact.py` | Catch `ContextForgeError` and return a one-line failed outcome |
| Branch merge | `pipeline/branch_ops.py`, `actions/branch.py` | `BranchFailure.UNFINISHED_TASKS`; the action marks the result as needing a decision |
| Executor | `pipeline/executor.py` | A failed action carrying `NEEDS_DECISION_OUTPUT` gives `PAUSED`, not `FAILED` |

### Data Flow

```
phase/revise step ──params──▶ DispatchAction._dispatch_via_agent
   requires_writes = dispatch_requires_writes(params)
   AgentConfig(allowed_tools, requires_writes, …) ──▶ registry.spawn
        Codex:  allowed_tools → ProviderError ; requires_writes ∧ read-only → ProviderError
        OpenAI: requires_writes ∧ no write tool given → ProviderError
   (ProviderError → one-line failed step, existing #200 path)
   handle_message ──▶ final metadata {tools_given, tool_calls_made, failed_tool_calls, tool_errors}
   assess_tool_outcome(...) ──▶ ToolOutcome(fail_reason | None, warnings)
        warnings → logger.warning + metadata["tool_warnings"]
        fail_reason → ActionResult(success=False, error=fail_reason, metadata=…)
```

### State Management
Nothing new is persisted. The new metadata keys reach `StepState.action_results` through the existing `asdict` serialization. A paused merge step writes the existing `CheckpointState` through `StateManager._append_step`, so `sq run --resume` re-runs the merge once the PM has finished or checked off the items.

## Technical Decisions

### D1 — Write-required is derived, not declared
No new pipeline key is added. Phase steps and revise dispatches exist to change files. Bare dispatch keeps its meaning: text-only unless it declares `allowed_tools`. The predicate lives in one function, and its inputs are the existing constants `RULES_STEP_PARAM` and the `feedback` param. Rejected: a per-step `writes: true` key. It adds config surface, and the cases it would cover beyond D1 are bare dispatches like P6's `close-out`, which runs on the SDK by default.

### D2 — Providers refuse at spawn; dispatch keeps a backstop
Provider-specific knowledge stays in the provider. The sandbox, for example, is a Codex credential that dispatch must not read. Refusing at spawn costs nothing, because no model call is made. The refusal messages name the fix:
- Codex with `allowed_tools`: "Codex does not run squadron tools; remove `allowed_tools` (Codex uses its own tools when its sandbox allows writes) or use a profile that supports them."
- Codex, read-only, write-required: "profile `<name>` runs Codex with a read-only sandbox; this step must write files. Set `sandbox = "workspace-write"` in the profile credentials."
- OpenAI-compatible, write-required, no write tool: "step must write files but has no write-capable tool; add `write_file` (or `bash`) to `allowed_tools`."
- Codex, read-only, not write-required (bare dispatch): no refusal. Log a WARNING and stamp `sandbox: read-only` in metadata.

Dispatch keeps a provider-agnostic backstop (D3 row 1) for any provider that ignores `allowed_tools` without raising.

### D3 — Which signals fail a step and which warn

| # | Signal (from final response metadata) | Outcome |
|---|---|---|
| 1 | `allowed_tools` non-empty after the capability gate, but no `tools_given` in the response | **Fail**: "declared tools were not given to the model" |
| 2 | Write-required, tools given, `tool_calls_made == 0` | **Fail**: "step must write files but made no tool calls" |
| 3 | `tool_calls_made > 0` and `failed_tool_calls == tool_calls_made` | **Fail**: "every tool call failed", with the first `tool_errors` entry |
| 4 | `failed_tool_calls > 0`, some calls succeeded | **Warn**. Models recover from a bad grep or path |
| 5 | Tools suppressed by the capability gate (`tools_suppressed_reason`) on a write-required step | **Fail** (it reduces to row 2's situation with no tools at all) |

Every row records its counts in metadata. Fail rows also log at WARNING with the step name. `tools_suppressed_reason` is copied into metadata today only as a log line; it is now copied as a key. Rows 2 and 5 do not apply where no tool telemetry exists: SDK phase steps use native tools and stamp telemetry only when `allowed_tools` is declared. These steps are covered by the #15 post-condition (`design`, `tasks`) and by the merge gate (`implement`).

**#15 check (from the plan entry).** The no-artifact post-condition applies only to `design` and `tasks` (`steps/phase.py` `_EXPECTED_ARTIFACT_KIND`; `implement` maps to `None`). It does not apply to bare dispatch or revise dispatches. It catches a no-op design/tasks step on any provider, but only after the model has run. This slice adds earlier refusal (D2) and covers `implement` and revise dispatches (rows 2–3). The #15 post-condition is unchanged.

### D4 — SDK failed-tool count
The claude-agent-sdk delivers `ToolResultBlock` inside `UserMessage.content`. The current `elif isinstance(sdk_msg, ToolResultBlock)` never matches, so `failed_tool_calls` is always 0 on the SDK path. Row 3 needs a real count, so the fix is in scope. A unit test with a `UserMessage` carrying an error `ToolResultBlock` asserts the count.

### D5 — cf errors in post-conditions are one line
In `dispatch_artifact._resolve_paths`, catch `ContextForgeError` next to `(ValueError, TypeError, FileNotFoundError)`. Return a failed `EventOutcome` whose error is the cf message, which already names the fix (for example "No slice plan configured. Set one with: cf set slicePlan <path>"). Use `error_kind` NONE so the executor does not rewrite it to `<action>: raised`. Dispatch's `_kept_artifact_paths` gets the same treatment: `ContextForgeError` becomes `ActionResult(success=False, error=…)` without reaching the generic `_logger.exception` handler. Both paths log the message at ERROR without `exc_info`. This is the same one-line form #200 gave `ProviderError`.

### D6 — Unfinished tasks at merge pause the run
A task-file hard gate is a task that requires an explicit PM confirmation before work proceeds (for example trading-data slice 128, "Hard Gate A — PM-confirmed backup"). The implementing agent stops there by design. Squadron's only deterministic evidence is the unchecked items the merge gate already finds, and the gate currently returns `FAILED`. The work is not wrong; it is waiting for a decision. So:
- Add `BranchFailure.UNFINISHED_TASKS` and raise it from `_require_checked_tasks` when unchecked items remain. An unreadable task file stays `OTHER`, which still fails.
- The branch action sets `outputs[NEEDS_DECISION_OUTPUT] = True` on that failure. `NEEDS_DECISION_OUTPUT` is defined once in `pipeline/models.py`.
- The executor's action-failure branch returns `ExecutionStatus.PAUSED` when a failed action carries that output. The run ends `paused`, exits 0 (existing PAUSED handling), and is resumable.
- Fan-out/batch flag classification (slice 197) maps `UNFINISHED_TASKS` the way it maps `OTHER` today. Batch items have no per-item pause.

**Open item for the PM:** the #212 run (trading-ui, 0.21.7) ended `completed`, and its run state is not on this machine. A `completed` end means the merge gate passed, so either close-out checked off the gated item or cf listed no task files (see Special Considerations). D6 makes the honest-close-out case pause. Phase 6 should confirm the actual path against that run's state file if it can be supplied.

## Integration Points

### Provides to Other Slices
- `AgentConfig.requires_writes` and the D2 contract. Future providers must refuse a write-required config they cannot serve.
- `ToolDescriptor.writes`, for any later tool policy.
- `NEEDS_DECISION_OUTPUT`, a generic way for an action to end its step `paused`.

### Consumes from Other Slices
- 944/#200: a failed dispatch inside a multi-step loop body ends the loop with `on_exhaust`. A revise dispatch failed by D3 in P6's `revise-code` therefore ends at `checkpoint`, which is `paused`. In P4/P5 loops it ends with their configured `on_exhaust`. The single-step loop shape (`_execute_loop_step`) still treats an action failure as transient. No built-in pipeline uses that shape for a dispatch, so it stays as is.
- 942: the merge gate and close-out step, unchanged except for the failure kind.

## Success Criteria

### Functional Requirements
1. A Codex-profile dispatch that declares `allowed_tools` fails before any model call, with the D2 message. Run status is `failed`.
2. A Codex-profile phase step on a read-only sandbox fails before any model call, with the D2 message naming the `sandbox` credential.
3. A bare Codex dispatch on a read-only sandbox still runs, logs a WARNING, and records `sandbox: read-only` in step metadata.
4. An OpenRouter dispatch whose only `write_file` call is rejected by the jail fails. The step error contains the jail message, and the run state records `failed_tool_calls` and `tool_errors`.
5. An OpenRouter `implement` step with no write-capable tool in `allowed_tools` fails at spawn.
6. A dispatch with some failed and some successful tool calls completes, with a WARNING and the counts in metadata.
7. `sq run P4 <slice>` with no cf slice plan prints one line with the cf message and no traceback. The step fails.
8. A P6 run whose task file still has unchecked items at merge ends `paused`, exit 0, and `sq run --resume <run-id>` re-attempts the merge.
9. SDK one-shot dispatches record a non-zero `failed_tool_calls` when a tool errors.

### Technical Requirements
- Unit tests for `assess_tool_outcome` cover each D3 row and the no-telemetry case.
- Provider tests cover each D2 refusal and the bare-dispatch WARNING. The SDK test covers the D4 count.
- Executor test: a failed action with `NEEDS_DECISION_OUTPUT` gives `PAUSED`, without it `FAILED`. Branch test: unchecked items give `UNFINISHED_TASKS`, an unreadable file gives `OTHER`.
- Every new failure mode logs at WARNING or ERROR, and at least one test asserts the log record.
- `ruff format`, `ruff check`, and `pyright` with zero errors. The full test suite passes.
- CHANGELOG bullets for the user-visible changes (refusals, failed steps, the paused merge, one-line cf error).

### Integration Requirements
- P4/P5/P6 run unchanged on the default SDK profiles.
- The #200 loop path ends a loop on a D3-failed revise dispatch.

### Verification Walkthrough

Run inside a scratch clone registered with cf. Probe pipelines are one-step YAML files, as in #211. Paths and aliases below are the ones used in the #211 probes; adjust to the local `models.toml`.

1. **Codex refuses declared tools** (criterion 1):
   ```bash
   sq run probe-luna-tools.yaml      # dispatch, model: luna, allowed_tools: [write_file]
   ```
   Expect: exit 1, one line `… Codex does not run squadron tools; remove allowed_tools …`, and no model call in `-v` output.
2. **Codex read-only phase step** (criterion 2): run a `design` step with `model: luna` on a profile without `sandbox`. Expect a failed step naming `sandbox = "workspace-write"`. Set that credential and rerun; the design file is written.
3. **Bare Codex dispatch** (criterion 3): `probe-luna-notools.yaml` completes. stderr shows a WARNING about the read-only sandbox, and `sq run --status latest` / the run JSON shows `sandbox: read-only` in the step metadata.
4. **Jail-rejected write** (criterion 4): `probe-ds-tools.yaml` (deepseek4-flash, `write_file`, path outside the cwd). Expect exit 1 and step error `every tool call failed: Error: path '…' resolves outside the working directory …`. The run JSON shows `failed_tool_calls: 1` and `tool_errors`.
5. **Control** (no regression): `probe-ds-inrepo.yaml` and an SDK haiku probe both complete and write the file.
6. **#202** (criterion 7): in a cf project with no `slicePlan` set, run `sq run P4 <index>`. Expect one line ending with `cf set slicePlan <path>` and no traceback.
7. **#212 paused merge** (criterion 8): on a scratch slice, leave one task item unchecked with the text "Hard Gate: PM confirms X" and run P6. Expect the run to end `paused`, exit 0, and the merge message naming the unchecked item. Check the item and run `sq run --resume <run-id>`; the merge completes.

## Risk Assessment

### Technical Risks
- **False failures on row 2.** A legitimate revise dispatch could conclude that no change is needed and make zero tool calls. It now fails, and in P6 that ends the loop at `checkpoint`, which is `paused`. That is the correct human-decision outcome, not a lost run.
- **Codex users with the default read-only profile** will see phase steps refused where they previously "completed" while doing nothing. This is intended. The message names the one-line fix, and the CHANGELOG states it.

## Implementation Notes

### Development Approach
1. Add `ToolDescriptor.writes` and `AgentConfig.requires_writes`, and the `dispatch_requires_writes` predicate.
2. D4: fix the SDK count first, since rows 3 and 4 depend on accurate counts.
3. OpenAI-compatible agent: `tool_errors` capture and the write-tool refusal.
4. Codex agent: spawn refusals, the bare-dispatch WARNING, and the `sandbox` metadata.
5. `dispatch_outcome.py` and its wiring in `_dispatch_via_agent`, including the new metadata keys.
6. D5: cf one-line errors in the post-condition and the keep path.
7. D6: `UNFINISHED_TASKS`, `NEEDS_DECISION_OUTPUT`, the executor mapping, and the batch flag mapping.
8. CHANGELOG, then the walkthrough.

Unit tests for each step mock the provider stream or registry. Walkthrough steps 1–4 use real providers; they are the only proof that the refusals fire on real configs.

### Special Considerations
- **Finding for #212 item 1 (not fixed here):** `_require_checked_tasks` passes when `resolve_slice_info` returns no `task_files`. A slice whose task file cf does not list therefore merges with unchecked work. Record this on #212 as a lead for item 1.
- `tool_errors` stores tool result text, which can include file paths from the working directory. It holds the first `_TOOL_ERROR_LIMIT` (3) entries, each truncated, and is defined once in the OpenAI agent module.
