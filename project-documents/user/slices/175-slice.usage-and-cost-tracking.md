---
docType: slice-design
slice: usage-and-cost-tracking
project: squadron
parent: project-documents/user/architecture/140-slices.pipeline-foundation.md
dependencies: [174]
interfaces: []
dateCreated: 20261014
dateUpdated: 20261014
status: not_started
---

# Slice Design: Usage and Cost Tracking

## Overview

Squadron records what each run step, review, and audit spends (tokens by class, turns, wall time, effort sent, and cost when one is known), keeps the record in run state and review artifacts, and reports it with a new `sq stats` command.

Slice 931 built part of this. It added the neutral `TokenUsage` / `RunTelemetry` types in `core/usage.py`, OpenAI-compatible per-turn usage, Codex usage, alias `effort`, and review frontmatter keys. Only reviews consume that data. The Claude SDK paths, which carry most of the volume, throw usage away at `providers/sdk/translation.py:102-127`. Dispatch, summary, and compact record nothing on any provider. Alias pricing exists, but `estimate_cost` (`models/aliases.py:322`) has no callers. This slice closes those gaps and adds the reporting surface.

The two payoff reports, #214 (planned vs actual effort per slice) and #210 (producer model effectiveness per phase), are split into a follow-on slice (D12).

## Value

- **Cost visibility.** An API-key user can see what a run, step, or review cost before the bill arrives. A subscription user sees token volume, which is what draws down the session pool.
- **A baseline for reduction.** Reviews are the most frequent SDK path. A regression in prompt size or turn count shows up in `sq stats` instead of going unnoticed (#36).
- **Diagnosis of #34.** Per-run cache read and cache write tokens and turn counts let us measure the 3x session-draw gap instead of inferring it from a session meter that reports whole percentages.
- **Data for 214/210.** Every normal run from now on records effort, tokens, cost, and step duration. The follow-on reports have history to read on the day they ship.

## Technical Scope

**Included:**

1. **Neutral record.** `TokenUsage` gains `cache_write`. New `UsageRecord` (model, alias, profile, effort sent, turns, duration, tokens, cost, cost basis) in `core/usage.py`.
2. **SDK capture (#172, #33, #36).** `ClaudeSDKAgent` and `SDKExecutionSession` read `ResultMessage.usage`, `num_turns`, and `total_cost_usd`.
3. **Action capture.** dispatch (one-shot and session), summary (one-shot and session), compact (SDK session), and review stamp a `UsageRecord` into `ActionResult.metadata`, so it persists in run state through the existing `asdict` path.
4. **Step duration.** `StepState.duration_seconds`, an additive field with no schema bump.
5. **Cost.** One pricing function replaces `estimate_cost`. A cost the provider reports takes precedence over a cost computed from alias pricing.
6. **Review artifacts.** `RunCost` adds `cacheWriteTokens`, `costUsd`, and `costBasis`. SDK reviews now populate every token key.
7. **Metrology audit (#33).** `AuditRun` gains an optional `usage` field.
8. **#151.** dispatch and summary pass the alias `max_output_tokens`.
9. **#158 closure.** 931 implemented #158's ask: per-turn usage summed across the loop, and reasoning totalled. The issue was not closed. This slice adds `cache_write` to the OpenAI reader's output (always `None` there; see D2) and closes #158.
10. **#154 closure.** Effort sent is now recorded on dispatch and summary steps, not only reviews (931 D11 left those as a DEBUG log).
11. **`sq stats`.** `run`, `runs`, and `reviews` subcommands with `--json`. Core logic is Typer-free. The slash command and agents skill wrap the CLI.
12. **#173.** A probe of Gemini's endpoint, gated on a precondition (D11).

**Excluded:**

- **MCP tool.** Squadron has no MCP server (`tools/mcp_bridge.py` is a client to context-forge). The core is shaped so a tool can wrap it, following the metrology precedent. A server is its own feature; it is logged as an issue when this design is approved.
- **Fixing #34.** This slice measures it (D10). A fix depends on what the measurement shows.
- **Applying effort on the SDK session path.** `open_pipeline_session` builds options without the alias effort, and `set_model` changes only the model. This slice records the gap truthfully (D7) but does not apply effort there ([#216](https://github.com/ecorkran/squadron/issues/216)).
- **#214 and #210 reports** (D12).
- **The PR composer** (`pr/composer.py`) and the addressed-findings judge. Neither has a run or artifact to attach a record to. The judge's review already passes through `review_client`.
- **Budgets or limits** ("stop when cost exceeds X").

## Dependencies

### Prerequisites

- **174** (complete): run-state v5, `SDKExecutionSession` stall interrupts and drains. Results drained during an interrupt must be counted (D4).
- **931** (complete): `core/usage.py`, `RunCost`, `Effort`, and the OpenAI and Codex usage readers.
- **claude-agent-sdk ≥ 0.2.162** (current pin). `ResultMessage` has `usage: dict | None`, `num_turns`, `duration_ms`, `total_cost_usd: float | None`, and `model_usage: dict[str, ModelUsage] | None` (`types.py:1340-1356`). `ModelUsage` has `inputTokens`, `outputTokens`, `cacheReadInputTokens`, `cacheCreationInputTokens`, and `costUSD`.

### Interfaces Required

- `ActionResult.metadata: dict[str, object]` (`pipeline/models.py:28-44`), already persisted through `dataclasses.asdict` in `_append_step` (`pipeline/state.py:482-536`).
- `ResolvedModel` (`pipeline/resolver.py:61-85`): alias name, profile, `effort`, `max_output_tokens`.
- `read_frontmatter` for review artifacts, used by `sq stats reviews`.
- `StateManager` listing (`pipeline/run_listing.list_run_summaries`) for `sq stats runs`.

## Architecture

### Component Structure

| Component | Location | Change |
|---|---|---|
| `TokenUsage`, `RunTelemetry`, `UsageRecord`, `CostBasis` | `core/usage.py` | extend / new (stdlib only, stays a leaf module) |
| Metadata key constants | `providers/base.py` | `USAGE_KEY`, `TURNS_KEY`, `COST_USD_KEY` replace the bare `"usage"`/`"turns"` strings |
| SDK result reader | `providers/sdk/usage.py` (new) | `read_result_usage(ResultMessage) -> (TokenUsage, turns, cost_usd)` |
| `ClaudeSDKAgent` | `providers/sdk/agent.py` | stamps usage keys in `_translate_and_track` |
| `SDKExecutionSession` | `pipeline/sdk_session.py`, `pipeline/sdk_turns.py` | `DispatchTurns` carries a `RunTelemetry` folded from every `ResultMessage` |
| Pricing | `models/aliases.py` | `price_usage(alias, usage)` replaces `estimate_cost` |
| Action capture helper | `pipeline/usage_capture.py` (new) | builds a `UsageRecord` from agent metadata or session telemetry plus `ResolvedModel` |
| Actions | `pipeline/actions/{dispatch,summary,compact,review}.py`, `pipeline/summary_oneshot.py` | stamp `metadata[USAGE_KEY]`. dispatch and summary also pass `max_output_tokens` |
| Step timing | `pipeline/executor.py`, `pipeline/state.py` | `StepState.duration_seconds` |
| Review rendering | `review/run_cost.py`, `review/models.py` | cache write, cost, cost basis |
| Audit | `metrology/audit.py`, `metrology/models.py` | `AuditRun.usage: dict | None` |
| Stats core | `stats/usage_report.py` (new package, no Typer) | read run state and review artifacts, aggregate |
| Stats CLI | `cli/commands/stats.py` | `sq stats run|runs|reviews` |
| Slash / skill | `commands/sq/stats.md`, `commands/agents/sq-stats/SKILL.md` | wrap the CLI |

### Data Flow

```
provider seam                     action                         persistence            report
-------------                     ------                         -----------            ------
OpenAI _stream_turn  ─┐
Codex _turn_usage    ─┼─ Message.metadata[USAGE/TURNS/COST] ─┐
SDK agent ResultMsg  ─┘                                      ├─ usage_capture ─► ActionResult.metadata["usage"]
SDKExecutionSession ResultMsgs ─► DispatchTurns.telemetry ───┘   + ResolvedModel   ─► StepState.action_results ─► sq stats run/runs
                                                                  + price_usage       (~/.config/squadron/runs)
review_client ─► ReviewResult.usage/cost ─► RunCost ─► review artifact frontmatter ─────────────────────────► sq stats reviews
metrology audit ─► AuditRun.usage ─► metrology store
```

Totals for a step, a run, or a set of runs are computed at read time and never stored. That leaves one source of truth per action.

### State Management

- **Run state.** No schema version bump. `metadata["usage"]` lives inside the existing `action_results` dicts. `StepState.duration_seconds: float | None = None` follows the slice 940 precedent: pydantic ignores fields it does not know, so older builds still read new files. Files written before this slice have no usage, and reports show them as "not recorded" (D9).
- **Review artifacts.** New keys appear only when they have a value (931 D10 convention). cf does not reject unknown keys.
- **Metrology store.** `AuditRun.usage` is optional and defaults to `None`, so record schema 1 is unchanged. #33's reason for deferring this was the 323 noise-floor campaign, and slice 323 is complete.

## Technical Decisions

### D1 — `prompt` counts every input token; cache classes are subsets

The providers disagree on what "input" means. OpenAI-style `prompt_tokens` and Codex `input_tokens` include cached tokens. Anthropic's `input_tokens` excludes both cache reads and cache writes. One meaning is fixed for every provider:

- `prompt`: all input tokens billed or read, including cached and cache-written.
- `cached`: the subset read from cache.
- `cache_write`: the subset written to cache. This answers #172's open question. It is billed input, so it is counted in `prompt` and also kept as its own field, because it is priced differently and is the first thing #34 needs.
- `completion`: output tokens, including reasoning.
- `reasoning`: the subset of completion that is reasoning, when reported. The SDK does not report it, so it stays `None` there.

SDK mapping: `prompt = input_tokens + cache_read_input_tokens + cache_creation_input_tokens`, `cached = cache_read_input_tokens`, `cache_write = cache_creation_input_tokens`, `completion = output_tokens`. A missing key stays `None`. It is never 0. `prompt` is `None` only if `input_tokens` is missing. A missing cache key adds nothing, and that cache field stays `None`.

### D2 — Read only `ResultMessage`; never sum per-message usage

Per-message `usage` repeats a snapshot within a turn. Summing it gave 7.08M cache-read tokens where the authoritative figure was 2.17M (#33). Only `ResultMessage` is read. Within one `handle_message` or one session `dispatch()`, each `ResultMessage` covers one query or turn, and those are summed with `add_optional`. In `SDKExecutionSession`, that covers the own result, injected follow-up turns (`sdk_session.py:270-282`), and results drained during an interrupt (`387-407`). Each is real spend.

`model_usage` is not stored per model. The answering model is already recorded (`answering_models`). The top-level `usage` is the total, and a per-model split has no consumer yet. When a result has no top-level `usage` but has `model_usage`, the per-model entries are summed as the fallback. That is the only use of `model_usage`.

The OpenAI-compatible reader never sees a cache-write count (OpenAI does not report one), so `cache_write` stays `None` there. Codex likewise.

### D3 — Cost: provider-reported, else alias pricing, else none

`UsageRecord.cost_usd: float | None` and `cost_basis: CostBasis | None`, where `CostBasis` is a `StrEnum` with `provider` and `alias_pricing`.

1. If the provider reported a cost (SDK `total_cost_usd`), use it with basis `provider`. On a subscription account this is the API-rate equivalent, not money spent. `sq stats` prints `api-rate equiv.` when the profile's `cost_tier` is `subscription`, and that label is read from the alias, not inferred.
2. Otherwise, if the alias has pricing, `price_usage` computes it with basis `alias_pricing`. Uncached input is `prompt − cached − cache_write`, each class at its own price.
3. Otherwise, cost is `None`.

`price_usage` returns `None` (and logs a WARNING once per alias per process, naming the alias and the missing price key) when a token class with a nonzero count has no price, or when the counts are inconsistent (`cached + cache_write > prompt`). A partial price is never shown as a total. `estimate_cost` has no callers and is deleted. `price_usage` replaces it.

The pricing table is the only source of prices. No prices are hard-coded in Python.

### D4 — Capture at the provider seam, attribute at the action

Providers report what they measured (tokens, turns, cost) on the final `Message.metadata` under the `providers/base.py` constants, the way OpenAI and Codex already do. A provider does not know the alias or step, so it builds no `UsageRecord`.

`pipeline/usage_capture.py` is the one place a `UsageRecord` is built. It takes the provider telemetry plus the `ResolvedModel` (alias, profile, effort, budget) and the measured duration, and calls `price_usage`. Every action calls it. Review builds its record from `ReviewResult`, which already holds the same fields, so no logic is duplicated: `RunCost` and `UsageRecord` both read `ReviewResult`.

`SDKExecutionSession` is not an `Agent`, so it returns its `RunTelemetry` on `DispatchTurns` (and from `capture_summary` / `compact`) rather than through message metadata. Both paths end in the same helper.

### D5 — Failed actions record what they spent

A failed dispatch still spent tokens. Where a `ProviderError` carries `telemetry` (OpenAI today; SDK after this slice, set in the agent's existing failure path), the failed `ActionResult` gets a `UsageRecord` too. A stalled SDK session turn (174) folds the results drained during the interrupt, so the record covers them. Run totals include failed attempts. The cost of a loop is the whole loop (#210).

### D6 — Step duration in run state, action duration in the record

`StepState.duration_seconds` is measured with `time.monotonic()` in the executor around one step's actions. It includes non-LLM actions (cf ops, commits) and answers #210's "wall time per step". `UsageRecord.duration_seconds` is the LLM call's own time (the review path already measures it, 931 D9). Both are kept because they answer different questions: where the time goes inside a step.

### D7 — Effort recorded is effort sent

`UsageRecord.effort` is the value actually sent: `ResolvedModel.effort` when the provider's `applies_effort` is true and the path applies it, otherwise `None` ("backend default"). The SDK session path does not apply alias effort. When the alias sets one there, the record says `None`, and one WARNING per step says `"SDK session does not apply alias effort=%s for %s; the backend default applies"`. A record never claims a level that was not sent (931 D4 rule).

### D8 — `sq stats` reads; it never writes

Subcommands:

- `sq stats run <run_id>`: one row per step and action, plus a total.
- `sq stats runs [--pipeline NAME] [--slice INDEX] [--since YYYYMMDD] [--status S]`: one row per run, plus a grand total.
- `sq stats reviews [--slice INDEX] [--since YYYYMMDD] [--dir PATH]`: one row per review artifact, plus a total. It covers standalone `sq review` runs. Pipeline reviews appear here and also under their run, so the two views are never summed together.

All subcommands take `--json`. `--slice` matches `RunState.params[SLICE_PARAM]` for runs (the constant from `pipeline/commit_plan.py`), and the frontmatter `slice` key for reviews.

The core (`stats/usage_report.py`) returns typed summaries. `cli/commands/stats.py` renders them as tables or JSON. The slash command and skill run `sq stats $ARGUMENTS`, which is how every existing slash command reaches parity. An MCP tool, when a server exists, calls the core functions.

The name is `stats`, not `usage`, because #214 asked for `sq stats slice`. The follow-on slice adds that subcommand to the same group.

### D9 — Honest totals

- Token totals use `add_optional`. A class no action reported stays `not reported`.
- A cost total prints how many actions it covers: `$1.84 (7 of 9 actions priced)`. Actions with no cost are never counted as $0.
- Actions recorded before this slice, or non-LLM actions, have no record. Each report states the number of LLM actions with no usage recorded. Non-LLM action types (cf op, commit, gate, checkpoint) are identified by `ActionType` enum membership, not by string matching.
- A malformed `metadata["usage"]` in a state file is skipped. The row shows `unreadable`, and a WARNING names the run and step.

### D10 — #34: measure, don't fix

The slice makes the measurement possible and runs it once as a walkthrough step: the same audit through `sq metrology audit run` and through raw `claude -p --output-format json`, comparing `cache_write`, `cached`, and turns. The numbers are posted on #34. #34 stays open, and the fix gets its own design once the cause is known. The operator needs a Max account and the same repo and commit as #34's measurements, so this is a walkthrough step and not a task gate.

### D11 — #173 is a precondition-gated probe

Flipping `sends_stream_usage` on gemini needs a live probe that succeeds. When `GEMINI_API_KEY` is set and the probe streams a `usage` chunk, the one-line flip and its test flip are made, and #173 is closed. If the probe returns 503/429, or no key is available, #173 stays open with the result posted. The slice does not wait on it.

### D12 — #214 and #210 split into a follow-on slice

The capture layer and `sq stats` are enough for one release. #214 also needs git commit attribution per task and a task-kind tag that depends on context-forge. #210 needs a replay runner and scorers under the 320 store. Neither changes the capture schema here. #210's own "item 1 first" is exactly this slice. Both issues stay open and are referenced by the follow-on slice plan entry.

## Implementation Details

### API Contracts

**Neutral types (`core/usage.py`)**

```python
@dataclass(frozen=True)
class TokenUsage:
    prompt: int | None = None       # all input, incl. cached and cache_write (D1)
    cached: int | None = None
    cache_write: int | None = None
    completion: int | None = None
    reasoning: int | None = None

class CostBasis(StrEnum):
    PROVIDER = "provider"
    ALIAS_PRICING = "alias_pricing"

@dataclass(frozen=True)
class UsageRecord:
    model: str | None          # answering model when known, else requested
    alias: str | None
    profile: str | None
    effort: str | None         # sent, else None (D7)
    turns: int | None
    duration_seconds: float | None
    usage: TokenUsage
    cost_usd: float | None
    cost_basis: CostBasis | None
    def to_dict(self) -> dict[str, object]: ...
    @classmethod
    def from_dict(cls, raw: Mapping[str, object]) -> UsageRecord: ...  # raises ValueError on a malformed record
```

`RunTelemetry` gains `cost_usd: float | None`, summed by a float version of `add_optional`.

**Pricing:** `price_usage(alias_name: str | None, usage: TokenUsage) -> float | None` in `models/aliases.py`.

**Persisted shape** (inside `StepState.action_results[i].metadata`):

```json
"usage": {"model": "...", "alias": "...", "profile": "sdk", "effort": null,
          "turns": 12, "duration_seconds": 84.2,
          "tokens": {"prompt": 412803, "cached": 380112, "cache_write": 21011,
                     "completion": 9214, "reasoning": null},
          "cost_usd": 0.41, "cost_basis": "provider"}
```

**Review frontmatter**, added to the 931 D10 table. Each key is present only when it has a value: `cacheWriteTokens`, `costUsd`, `costBasis`. The digest token line becomes `prompt / cached / cache write / completion / reasoning`. A new line reads `Cost: $0.41 (provider) | not reported`. `to_dict()` gains `cache_write_tokens`, `cost_usd`, and `cost_basis`, always present and null when not reported.

### UI Specifications

`sq stats run` (illustrative layout; values are not real):

```
Run run-20261014-ab12cd34  P456  slice=175  completed  38m 12s

Step         Action    Model / effort       Turns   Prompt    Cached  Cache wr  Compl.   Cost         Time
design       dispatch  opus / high             41   3.12M     2.98M    96.1k    18.4k   $2.07 prov   9m 40s
design-rev   review    glm-flash / low          9   412.8k   380.1k        —     9.2k   $0.03 alias  3m 34s
tasks        dispatch  opus / default          22   1.40M     1.31M    40.2k    11.0k   $0.96 prov   6m 02s
...
Total                                          96   6.01M     5.62M   151.3k    44.9k   $3.21 (7 of 9 priced)
2 LLM actions have no usage recorded.
```

`sq stats runs` uses one row per run with the same token and cost columns, plus pipeline, target, status, and start date. Width handling reuses 174's `cli/columns.py` (`fit_widths`). `sq stats reviews` uses one row per artifact: date, slice, review type, model, verdict, then the token and cost columns.

## Integration Points

### Provides to Other Slices

- `UsageRecord` in run state for every LLM action. This is the data source for the #214/#210 follow-on, and for 174-style stall tuning from real step durations.
- `stats/usage_report.py` functions, ready to wrap as MCP tools.
- `price_usage`, available for pool strategies that rank by expected cost (`pipeline/intelligence/pools/strategies.py` ranks by input price today).
- Review frontmatter cost keys, for amoeba and cf consumers comparing runs.

### Consumes from Other Slices

- 931's `RunCost`/`ReviewResult` usage path, extended rather than replaced.
- 174's interrupt and drain behavior in `SDKExecutionSession`. If a drain yields no `ResultMessage`, the record has the turns that completed and tokens stay as reported. That is not a failure.

## Success Criteria

### Functional Requirements

1. An SDK review artifact carries `turns`, `promptTokens`, `cachedTokens`, `cacheWriteTokens`, `completionTokens`, `costUsd`, and `costBasis: provider`. The digest shows them (#172, #36).
2. Every dispatch, summary, compact (SDK session), and review action in a pipeline run has `metadata.usage` in the run state file, on every provider that reports usage (SDK agent, SDK session, OpenAI-compatible, Codex). This includes failed actions whose error carries telemetry.
3. SDK session totals include injected follow-up turns and interrupt drains.
4. `StepState.duration_seconds` is set for every completed step.
5. Cost follows D3 precedence. A partial price yields `None` and a WARNING. Nothing is ever reported as $0 by default.
6. Dispatch and summary agents receive the alias `max_output_tokens` (#151).
7. `effort` on dispatch and summary records equals the level sent. The SDK session path records `None` and warns when the alias sets one.
8. `sq stats run`, `runs`, and `reviews` print the layouts in UI Specifications. `--json` emits the same data. Filters work as specified in D8.
9. Run files from before this slice load and report "no usage recorded" without error.
10. `sq metrology audit run` stores usage on `AuditRun`, and old audit records still load.
11. `/sq:stats` and the `sq-stats` skill produce output identical to the CLI.

### Technical Requirements

- `core/usage.py` stays stdlib-only.
- No bare `"usage"`/`"turns"` metadata strings. All use the `providers/base.py` constants.
- Every failure mode in the table below has a test that asserts its signal:

| Failure | Behavior | Signal |
|---|---|---|
| `ResultMessage.usage` is `None` and `model_usage` is absent | tokens `None` | WARNING once per `handle_message` / `dispatch()` (mirrors 931's OpenAI warning) |
| A usage value is a non-int | that field `None`, siblings read | WARNING naming the field and value, `%.200r` |
| `total_cost_usd` is absent | falls back to alias pricing (D3) | none (expected on non-SDK) |
| Partial alias pricing, or inconsistent counts | cost `None` | WARNING once per alias |
| Malformed `metadata.usage` in a state file | row `unreadable` | WARNING naming run and step |
| Unknown alias (bare model id) | alias `None`, provider cost only | none |
| SDK session with alias effort | effort `None` | WARNING per step (D7) |

- ruff format, ruff check, pyright with zero errors. Full suite green.
- Stubbed `ResultMessage` fixtures use the real field shape from `claude-agent-sdk` 0.2.162 (`usage` dict keys as the CLI emits them), including one captured from a real run.
- CHANGELOG bullets (user-facing). README: a `sq stats` section and the cost-basis meaning.

### Integration Requirements

- The follow-on #214/#210 slice can compute cost per accepted artifact from run state alone (dispatch records plus review verdicts per round).
- Existing review artifacts and `clean_pass_artifact.md` stay valid. The fixture is regenerated once, for the digest token-line change.

### Verification Walkthrough

Run in a scratch project registered with cf (as in 945), unless noted.

1. **SDK review records usage.**
   `sq review slice 175 --model sonnet -v`
   Open the artifact. Frontmatter has `promptTokens`, `cachedTokens`, `cacheWriteTokens`, `completionTokens`, `turns`, `costUsd`, and `costBasis: provider`. The digest has the `Tokens —` and `Cost:` lines with values, not `not reported`.
2. **OpenAI-compatible review prices from the alias.**
   `sq review slice 175 --model <an openrouter alias with pricing>`. Frontmatter has `costBasis: alias_pricing` and no `cacheWriteTokens`.
3. **A pipeline run records every LLM action.**
   `sq run P4 <slice>`, then `sq stats run <run_id>`. Each dispatch and review row has tokens, a model/effort column, and time. The total line shows "N of M priced". Open `~/.config/squadron/runs/<run_id>.json` and confirm `metadata.usage` on each LLM action and `duration_seconds` on each step.
4. **Budget reaches dispatch (#151).** Run a dispatch step with an alias that sets `max_output_tokens`, using `-vv`. The OpenAI provider's DEBUG line shows `max_completion_tokens` sent.
5. **Old runs degrade honestly.** `sq stats runs --since 20261001` lists pre-slice runs with `—` token cells and the "no usage recorded" line, and no traceback.
6. **Filters and JSON.** `sq stats runs --slice 175 --json | python -m json.tool` returns the same rows as the table. `sq stats reviews --slice 175` lists the steps 1–2 artifacts.
7. **Slash parity.** In Claude Code, `/sq:stats runs --slice 175` prints the same table as step 6.
8. **#34 measurement (operator, Max account; D10).** On migratory-viewer @5788a99a, run `sq metrology audit run` and the raw-CLI equivalent with `--output-format json`. Compare `cache_write`, `cached`, and turns from the audit record (`sq metrology list`) against the raw result. Post the table on #34.
9. **#173 probe (precondition: `GEMINI_API_KEY`; D11).** Run the curl from #173. If the last chunk before `[DONE]` carries `usage`, flip the gemini profile and its test, then rerun step 2 with a gemini alias. Otherwise post the response on #173.

## Risk Assessment

### Technical Risks

- **SDK `usage` dict shape.** The keys are passed through from the CLI, not typed by the SDK. A CLI version could rename or drop keys.
- **Notional cost on subscriptions.** `total_cost_usd` on a Max account could be read as money spent.

### Mitigation Strategies

- The reader takes the keys from a real captured `ResultMessage` fixture, and missing keys degrade to `None` with a WARNING (failure table). The fixture is checked in, so an SDK upgrade that changes the shape fails the test.
- The `api-rate equiv.` label (D3), and a README note on cost basis.

## Implementation Notes

### Development Approach

1. `core/usage.py`: `cache_write`, `UsageRecord`, `CostBasis`, the float `add_optional`. Metadata key constants, replacing the bare strings.
2. `price_usage`, delete `estimate_cost`, tests for each D3 branch.
3. SDK reader and `ClaudeSDKAgent` stamping, including failure telemetry. Gives SDK reviews (#172) through the existing `review_client` path.
4. `RunCost` / `ReviewResult` additions, fixture regeneration.
5. `SDKExecutionSession` telemetry on `DispatchTurns`, `capture_summary`, `compact`, including drains.
6. `usage_capture.py`. Wire dispatch (both paths), summary (both), compact, review. #151 budget. D7 effort rule.
7. `StepState.duration_seconds` in the executor.
8. `AuditRun.usage`.
9. `stats/usage_report.py`, then `cli/commands/stats.py`, then slash command and skill. Run `sq install-commands`.
10. CHANGELOG, README. Close #172, #36, #33, #158, #154, #151 with a line naming what landed. Walkthrough steps 8–9 update #34 and #173.

Testing: unit tests per reader with stubbed messages, `usage_capture` across providers, `price_usage` table tests, state round-trip with old fixture files (no usage, schema v3/v4/v5), and CLI snapshot tests for the three `stats` tables and JSON.

### Special Considerations

- **Release.** The slice plan calls this a minor-release feature. The new `sq stats` command group qualifies under the versioning rule (a new user-facing feature).
- **Privacy.** Records hold counts, model ids, and costs only, with no prompt or response content.
- **Open item for the Project Manager.** The #214/#210 follow-on needs a slice plan entry (D12).
