---
docType: slice-design
slice: claude-agent-sdk-upgrade-and-rate-limit-parser-shim-retirement
project: squadron
parent: 900-slices.maintenance-and-refactoring.md
dependencies: []
interfaces: []
dateCreated: 20260915
dateUpdated: 20260915
status: not_started
---

# Slice Design: Claude Agent SDK Upgrade — 0.1.38 → 0.2.x and Retiring the Rate-Limit Parser Shim

## Overview

Fixes [issue #30](https://github.com/ecorkran/squadron/issues/30). The pin is
`claude-agent-sdk>=0.1.38`; the current release is **0.2.152**. The bundled CLI
ships with the package and has moved ahead of the pinned parser, so the CLI emits
message types the parser treats as fatal — the observed symptom was a real
`sq metrology audit run` dying mid-stream after ~30 tool calls with
`ProviderError: Unknown message type: rate_limit_event`.

The compatibility surface was probed rather than assumed (see
[Probe Findings](#probe-findings)). The public API squadron depends on held
across the bump. **The entire risk of this slice is concentrated in one
mechanism**: throttle detection is currently keyed off a *parse failure*, and
after the upgrade that failure no longer occurs.

That makes this slice's real subject narrower and sharper than "upgrade a
dependency." Today the chain is:

```
CLI emits rate_limit_event
  → SDK parser raises MessageParseError            (0.1.38: unknown type)
  → shim absorbs informational, re-raises rejected
  → _skip_unparseable re-raises it
  → SDK generator is already dead; stream ends
  → ClaudeSDKError surfaces, str(exc) contains "rate_limit"
  → RATE_LIMIT_MARKER substring match → backoff
```

After the upgrade, step 2 never happens. The event parses cleanly into a typed
`RateLimitEvent`, flows to `translate_sdk_message`, which returns `[]` for
unrecognized types — and the throttle **disappears silently**. Nothing raises,
nothing logs, no backoff fires. Squadron keeps issuing requests into a limiter
that is rejecting them.

This is the failure direction that matters. A missing backoff is not a crash;
it is degraded behavior under load, visible only as throughput collapse in a
long run — precisely the condition (~30 tool calls into an audit) where the
original bug was found. The upgrade is a few lines. **Re-keying the detection
correctly, and proving it fires, is the slice.**

## Value

Operator-facing and reliability-facing.

- The audit/review paths stop dying on CLI message types newer than the parser.
- Squadron continues to back off under genuine throttling — via a typed,
  documented event rather than a substring match on an exception's text.
- Roughly 50 lines of parser monkey-patching against SDK private modules
  (`_internal.message_parser`, `_internal.client`, `_errors`) leave the codebase.
  That patching is the most version-fragile code squadron owns.
- Rate-limit classification gains a real contract. Today a `rejected` status is
  inferred from `"rate_limit" in str(exc)`; afterward it is read from
  `RateLimitInfo.status`, a `Literal['allowed', 'allowed_warning', 'rejected']`.

## Probe Findings

Established by installing `claude-agent-sdk==0.2.152` in a throwaway venv and
exercising it against squadron's actual usage. These are verified facts, not
assumptions — the design below depends on them.

**Compatible, no action needed:**

- All **14 public names** squadron imports are present: `AssistantMessage`,
  `ClaudeSDKClient`, `ClaudeAgentOptions`, `ResultMessage`, `SystemMessage`,
  `TextBlock`, `ToolUseBlock`, `ToolResultBlock`, `query`, and the five error
  types (`ClaudeSDKError`, `CLIConnectionError`, `CLIJSONDecodeError`,
  `CLINotFoundError`, `ProcessError`).
- All **9 `ClaudeAgentOptions` fields** squadron sets survive (`cwd`,
  `permission_mode`, `system_prompt`, `model`, `tools`, `allowed_tools`,
  `setting_sources`, `hooks`, `max_turns`). Both option shapes squadron
  constructs build without error. The dataclass now has 48 fields — additions only.
- All **three private modules** the shim reaches into still exist with the same
  shape, including the module-scope `parse_message` binding on `_internal.client`.
  (Relevant only to the decision to stop depending on them.)

**The change that drives this slice:**

- `rate_limit_event` **parses natively** into a new `RateLimitEvent`, present in
  `query()`'s return union alongside `StreamEvent` and `ConversationResetMessage`.
- `RateLimitEvent` fields: `rate_limit_info: RateLimitInfo`, `uuid: str`,
  `session_id: str`.
- `RateLimitInfo` fields: `status`, `resets_at`, `rate_limit_type`,
  `utilization`, `overage_status`, `overage_resets_at`,
  `overage_disabled_reason`, `raw`.
- `RateLimitStatus = Literal['allowed', 'allowed_warning', 'rejected']` — the
  same three values `rate_limit_event_blocks` already classifies.
- `RateLimitInfo.raw` preserves the original camelCase payload dict, so the
  existing dict-shaped classifier remains usable against it.
- Verified parse of both a `rejected` and an `allowed_warning` payload returns
  `RateLimitEvent`; **neither raises**.

**Two structural facts that shape the design:**

1. **Query mode yields every parsed message unfiltered** (`_internal/client.py`),
   so `RateLimitEvent` reaches `_skip_unparseable` → `translate_sdk_message`,
   where unrecognized types return `[]`. That `return []` is the silent drop.
2. **`parse_message` may now return `None`**, and `receive_messages` skips
   `None` results. Client mode imports `parse_message` *inside* the method;
   query mode holds it at module scope. (This asymmetry is why the shim patches
   two bindings — and one more reason to stop.)

## Technical Scope

### In scope

| Area | File(s) | Change |
| --- | --- | --- |
| Dependency pin | `pyproject.toml` | Raise floor to tested version |
| Shim retirement | `providers/sdk/rate_limit.py` | Remove `install_rate_limit_parser_shim`; add typed classification |
| Shim call sites | `providers/sdk/provider.py:43`, `pipeline/sdk_session.py:100` | Remove install calls |
| Throttle detection | `providers/sdk/agent.py`, `pipeline/sdk_session.py` | Re-key off typed event |
| Message dispatch | `providers/sdk/translation.py` | Recognize `RateLimitEvent` |
| Tests | 5 files (below) | Replace fabricated-exception simulation with typed events |

### Explicitly out of scope

- `ClaudeSDKClient` methods gained in 0.2.x (`get_context_usage`, `stop_task`,
  `rewind_files`, MCP controls). **Correction to the slice plan entry:**
  `set_model` is *already in use* at [sdk_session.py:125](src/squadron/pipeline/sdk_session.py#L125)
  and is called routinely by pipelines, so the entry's note about the pipeline
  "working around its absence" is stale.

  Out of scope, and worth stating precisely because squadron selects models by
  two different mechanisms:

  - **By construction (agent path).** `_dispatch_via_agent` bakes the resolved
    model into `AgentConfig(model=model_id)` and spawns a one-shot agent per
    step ([dispatch.py:129](src/squadron/pipeline/actions/dispatch.py#L129)).
    Nothing is switched — each step gets an agent built for its own model. This
    is the common case and the one where per-step models vary most freely.
  - **By mutation (session path).** `_dispatch_via_session` holds one long-lived
    `ClaudeSDKClient`, so a per-step model change must mutate the live session —
    hence `set_model`, with a no-op skip when the model already matches
    ([sdk_session.py:122](src/squadron/pipeline/sdk_session.py#L122)). Reached
    only when the resolved profile is an SDK profile, so its range is narrower.

  `set_model` therefore belongs to the session path alone, and the IDE-extension
  / Claude Code limitation applies to that path for the "no Claude in Claude"
  reason: `ClaudeSDKClient` spawns a Claude Code subprocess, which is blocked
  inside an existing Claude session. Non-SDK agent-path steps spawn no such
  subprocess and select models normally in any environment. Nothing in this
  slice changes any of it.
- `StreamEvent` / `ConversationResetMessage` handling. Both are new to the
  return union, but neither is presently symptomatic. `_skip_unparseable` and
  translation's `return []` handle them non-fatally.
- Optional-dependency restructuring (Future Slice 907).

## Architecture

### Decision D1 — delete the shim outright; do not keep a version-guarded no-op

*Resolves the open question the slice plan entry deferred to design.*

**Delete it.** The floor pin (D2) makes a guarded variant unreachable by
construction; retaining it would mean carrying code that cannot be exercised,
cannot be tested honestly, and monkey-patches two SDK private bindings to do
nothing. The hedge it offers — a user with a stale lockfile below the floor —
is not real: a resolver honoring the floor cannot produce that state, and one
ignoring the floor has already opted out of every compatibility guarantee the
project makes.

The shim's own docstring specifies this outcome: *"Remove once the pin moves
past a parser with native support."* This slice is that moment.

Deleted: `install_rate_limit_parser_shim` and its two call sites.
**Retained:** `rate_limit_event_blocks`, `RATE_LIMIT_EVENT_TYPE`,
`RATE_LIMIT_MARKER`, `rate_limit_backoff_s`, the backoff constants, and
`RateLimitStats`. Only the parser patching goes. `is_rate_limit_event` loses its
only production caller and is removed with the shim.

### Decision D2 — pin a floor, not a ceiling: `>=0.2.152`

Keep the `>=` form. A ceiling would recreate the defect this slice fixes: the
CLI ships *inside* the package, so pinning the SDK back pins the CLI back, and
a stale parser against a moving CLI is the original bug. The floor is the tested
version, `0.2.152`.

This is a deliberate acceptance: a future SDK may again emit a type squadron has
not seen. That is why `_skip_unparseable` is retained (D5) — it is the standing
defense against exactly that, and it is independent of version.

### Decision D3 — classify from the typed event, keeping one classifier

`rate_limit_event_blocks(data: dict)` already encodes the correct policy:
`rejected` means back off; `allowed`/`allowed_warning` are usage-meter updates;
a malformed payload is treated as informational. The policy is right and stays.
Only its input changes.

`RateLimitInfo.raw` carries the original dict, so a typed entry point can
delegate rather than duplicate:

```python
def rate_limit_event_blocks(data: dict[str, object] | None) -> bool:
    ...  # unchanged

def event_blocks(event: RateLimitEvent) -> bool:
    """True when a typed SDK rate-limit event says requests are rejected."""
    return event.rate_limit_info.status == _STATUS_REJECTED
```

Two entry points, one policy constant (`_STATUS_REJECTED`). The typed form reads
the parsed field rather than `raw`, so a future camelCase change in the CLI
payload cannot silently break classification; the dict form is retained for the
`ClaudeSDKError`-text path that still exists for genuine 429s surfaced as plain
errors (D4).

**Constraint:** `_STATUS_REJECTED` stays the single definition of the string.
Do not reintroduce the literal at comparison sites.

### Decision D4 — raise a typed signal at dispatch, not a new control path

The backoff loops in `agent.py` (two) and `sdk_session.py` (one) are already
correct: exponential delay, budget, `progressed` reset, `RateLimitStats`. None
of that changes. What changes is **what reaches them**.

Introduce a dedicated exception in `rate_limit.py`:

```python
class RateLimitRejected(ClaudeSDKError):
    """A typed rate-limit event reporting `rejected` — a genuine throttle."""
```

Subclassing `ClaudeSDKError` is load-bearing: all three loops already catch
`ClaudeSDKError`, so the existing `except` clauses need no restructuring and the
outer `ProviderError` conversions continue to work.

**The `RATE_LIMIT_MARKER` substring test must not be the gate.** Change each of
the three sites from

```python
if RATE_LIMIT_MARKER in str(exc) and retries < budget:
```

to

```python
if is_throttle(exc) and retries < budget:
```

where `is_throttle` returns `True` for `RateLimitRejected` **or** for a plain
`ClaudeSDKError` whose text contains `RATE_LIMIT_MARKER`. The substring path is
retained deliberately: a genuine HTTP 429 can still surface as a plain
`ClaudeSDKError`, and that path is unrelated to `rate_limit_event` parsing. It
is no longer the *only* signal.

Where the raise happens, per mode:

- **Query mode** and **agent client mode** — in `_skip_unparseable`, which both
  already wrap. It becomes the single inspection point: on a `RateLimitEvent`
  whose status is `rejected`, raise `RateLimitRejected` — the event itself is
  intercepted here and never yielded onward. Otherwise (informational), log at
  DEBUG and **yield the event through as normal** so it reaches translation
  (D6) rather than being silently dropped; it must not terminate the stream.
- **Pipeline `dispatch`** — [sdk_session.py:151](src/squadron/pipeline/sdk_session.py#L151)
  iterates `self.client.receive_response()` **directly, with no
  `_skip_unparseable` wrapper**. It needs its own inspection inside the loop,
  beside the existing `ResultMessage.is_error` check. This asymmetry is easy to
  miss and is the most likely place for the slice to half-land.

**Behavioral improvement, stated explicitly:** today a rejected event kills the
SDK generator (the parse exception terminates it permanently), so the query-mode
loop must restart the *entire query* and the client-mode loop must restart
`receive_response()`. With native parsing the stream is alive when the event
arrives. The retry loops still work unchanged, because restarting a healthy
stream is safe. Optimizing to an in-stream pause is **explicitly deferred** — it
would change stream-lifecycle behavior beyond what this slice can verify.

### Decision D5 — retain `_skip_unparseable`, and prove it no longer swallows throttles

Keep it. It defends against *the next* unknown type, which D2 accepts as a
standing possibility. Its docstring and comments, however, become actively
misleading — they explain the behavior in terms of a shim that no longer exists
and a `MessageParseError` that no longer arrives.

Rewrite them to describe two now-distinct concerns:

1. An unparseable message (WARNING, skip) — the stream is dead; the skip ends
   iteration cleanly.
2. A typed `RateLimitEvent` (inspect, and raise on `rejected`) — the stream is
   alive.

The `except MessageParseError` branch is retained (a future unknown type still
raises it), but its `is_rate_limit_event(exc.data)` special case is removed:
after this slice `rate_limit_event` parses natively, so a `MessageParseError`
carrying one cannot occur at the pinned floor.

### Decision D6 — translation recognizes `RateLimitEvent` explicitly

`translate_sdk_message` returns `[]` for unrecognized types. That default is
correct for `StreamEvent`/`ThinkingBlock`, but it is what would make a throttle
vanish. Add an explicit branch returning a `MessageType.system` message with
`sdk_type: "rate_limit_event"` and the status in metadata.

Two reasons this is not redundant with D4: dispatch inspection happens *before*
translation, so translation would never see a `rejected` event — but an
informational one becomes observable rather than dropped, and the explicit
branch documents at the dispatch site that this type was considered rather than
forgotten.

**Consumer check required.** `sdk_session.dispatch` filters translated messages
by `sdk_type` when accumulating `response_parts`, excluding `SDK_RESULT_TYPE`,
`tool_use`, `tool_result`. A new system message type **must** be added to that
exclusion set, or rate-limit notices concatenate into the returned prose —
issue #23's exact defect class. Do not leave this to be noticed later.

## Data Flow

**After (query mode and agent client mode):**

```
CLI emits rate_limit_event
  → SDK parses natively → RateLimitEvent
  → _skip_unparseable inspects:
      status == 'rejected'  → raise RateLimitRejected  ──┐
      otherwise             → DEBUG log, skip            │
  → (informational path continues to translation)        │
                                                         ▼
                              existing except ClaudeSDKError
                              → is_throttle(exc) → backoff, stats, retry
```

**After (pipeline `dispatch`):** identical, except inspection is inline in the
`receive_response()` loop rather than in `_skip_unparseable`.

**Unchanged:** backoff schedule, retry budgets, `progressed` reset semantics,
`RateLimitStats` accumulation, `ProviderRateLimitError` on exhaustion,
`AuditRunFailure.RATE_LIMITED` reporting.

## Implementation Parts

**Part A — Upgrade and shim retirement.**
Raise the pin to `>=0.2.152`; refresh the lockfile. Delete
`install_rate_limit_parser_shim` and `is_rate_limit_event`; remove both install
call sites. Add `RateLimitRejected` and `event_blocks`. Update
`rate_limit.py`'s module docstring, which currently narrates the shim's history.

**Part B — Re-key throttle detection.** *The load-bearing part.*
Add `is_throttle`; replace the three `RATE_LIMIT_MARKER in str(exc)` gates.
Inspect `RateLimitEvent` in `_skip_unparseable` and inline in
`sdk_session.dispatch`. Add translation's branch and extend `dispatch`'s
`sdk_type` exclusion set. Rewrite the stale docstrings/comments in
`_skip_unparseable` and both `dispatch` methods.

**Part C — Verification.** Per [Success Criteria](#success-criteria) and
[Verification Walkthrough](#verification-walkthrough) below.

## Success Criteria

**Functional**

1. `pyproject.toml` floors `claude-agent-sdk>=0.2.152`; the lockfile resolves to
   ≥ that version.
2. No symbol named `install_rate_limit_parser_shim` remains in `src/` or `tests/`;
   no module under `src/` imports `claude_agent_sdk._internal` or
   `claude_agent_sdk._errors.MessageParseError` for patching purposes.
   (`MessageParseError` remains imported in `agent.py` for its `except` branch.)
3. A `RateLimitEvent` with `status='rejected'` reaching any of the three dispatch
   paths triggers backoff: `RateLimitStats.throttles` increments and a WARNING is
   logged naming the attempt number.
4. A `RateLimitEvent` with `status='allowed'` or `'allowed_warning'` triggers **no**
   backoff, **no** stream restart, and does not appear in `dispatch`'s returned
   text.
5. Retry budget, exponential schedule, cap, and `progressed` reset are unchanged —
   asserted against the same expectations as the pre-slice tests.
6. Exhausting the budget still raises `ProviderRateLimitError` (agent) and still
   reports `AuditRunFailure.RATE_LIMITED` (audit).
7. A genuine 429 surfaced as a plain `ClaudeSDKError` containing `rate_limit`
   still triggers backoff — the substring path is retained, not replaced.
8. An unknown, non-rate-limit message type is still skipped with a WARNING and
   does not kill the run.

**Test integrity** — this criterion exists because the current tests would pass
against a completely broken implementation.

9. Every test that today simulates throttling by constructing a
   `MessageParseError` or a `ClaudeSDKError("rate_limit_event: ...")` is rewritten
   to yield a **real `RateLimitEvent`** into the stream. Fabricating the exception
   the SDK no longer raises tests a dead path.
10. At least one test asserts the informational case is **not** treated as a
    throttle (`throttles == 0` after an `allowed_warning` event) — the regression
    that would re-break issue #23's stream-restart behavior.
11. `pyright` reports zero errors; `ruff format` and `ruff check` are clean.

**Affected test files — requiring the criterion-9 rewrite:**
`tests/providers/sdk/test_agent.py` (primary — fabricates both
`MessageParseError` with a `rate_limit_event` payload and
`ClaudeSDKError("rate_limit_event: ...")`), `tests/pipeline/test_sdk_session.py`
(fabricates `ClaudeSDKError("rate_limit_event")`),
`tests/providers/sdk/test_provider.py` and `tests/metrology/test_audit_cli.py`
(shim install and rate-limit config plumbing).

**Not affected:** `tests/providers/openai/test_agent.py` is *not* in scope for
criterion 9. Its only rate-limit test constructs `openai.RateLimitError`
([test_agent.py:167](tests/providers/openai/test_agent.py#L167)) — the OpenAI
SDK's own exception on an independent provider path — and the file never imports
`claude_agent_sdk`. It is covered as a must-not-break regression by the
`pytest tests/providers` run in walkthrough step 2, and must not be modified by
this slice.

## Verification Walkthrough

Unit tests cannot close this slice. The original defect appeared only ~30 tool
calls into a live audit, and the dangerous failure mode — *no backoff under real
throttling* — produces no error to assert on. Steps 3 and 4 are mandatory.

**1. Upgrade landed and the shim is gone**

```bash
cd /Users/manta/source/repos/manta/squadron
grep -n "claude-agent-sdk" pyproject.toml          # expect >=0.2.152
python -c "import importlib.metadata as m; print(m.version('claude-agent-sdk'))"
grep -rn "install_rate_limit_parser_shim" src tests   # expect no matches
grep -rn "claude_agent_sdk._internal" src              # expect no matches
```

**2. Suites pass**

```bash
uv run pytest tests/providers/sdk tests/pipeline/test_sdk_session.py -q
uv run pytest tests/providers tests/metrology -q
uv run ruff format --check . && uv run ruff check . && uv run pyright
```

**3. Real end-to-end review** — exercises query/client dispatch and translation
against the live CLI at the new floor:

```bash
uv run sq review code --diff HEAD~1 -v
```

Confirm: the review completes, writes an artifact with a parsed verdict, and the
run logs no `Unknown message type` warning. A `rate_limit_event` arriving during
this run must not appear in the artifact's prose.

**4. Real metrology audit** — the workload that exposed the original bug; the
subagent fan-out makes a live `rate_limit_event` likely:

```bash
uv run sq metrology audit run -v
```

Confirm: the audit runs to completion rather than dying mid-stream. If
throttling occurs, the run reports a rate-limit summary
(`N rate-limit pauses, Ns spent waiting`) and resumes rather than aborting. If
no throttling occurs, the audit simply completes — a clean run is a pass for
this step, not a missing observation.

**Run this from a straight CLI, not from an IDE-extension or Claude Code
session.** The SDK-backed paths this slice touches depend on spawning a Claude
Code subprocess, which is blocked inside an existing Claude session — so an
audit driven from one does not exercise the paths under test here at all.

**5. Forced-throttle observation** — closes the gap step 4 leaves when no live
throttle occurs. Inject a `rejected` `RateLimitEvent` into a dispatch path
(temporary local patch or a test double at the `receive_response` seam) and
confirm the WARNING fires, `RateLimitStats.throttles` increments, and the run
continues. Revert before commit.

## Risk Assessment

**Silent loss of backoff (High impact, Medium likelihood).** The whole reason
this is not a routine bump. A `rejected` event that reaches translation instead
of the throttle check is dropped with no error. *Mitigations:* the substring
path is retained as a second signal (D4); criteria 9–10 force tests onto the
real event; walkthrough step 5 forces direct observation.

**The pipeline path is missed (High impact, Medium likelihood).**
`sdk_session.dispatch` does not use `_skip_unparseable`, so a fix applied only
there leaves the pipeline silently unprotected — and its tests, which fabricate
exceptions, would stay green. *Mitigation:* called out in D4 and Part B;
verification step 2 runs `test_sdk_session.py` explicitly.

**Tests pass against a dead path (Medium impact, High likelihood if unaddressed).**
The existing tests construct the exceptions themselves and never touch the SDK
parser, so they cannot detect that the mechanism they describe no longer exists.
*Mitigation:* success criterion 9 is non-negotiable.

**A new unknown type at the new floor (Low impact, Low likelihood).** Accepted
by D2 and handled by `_skip_unparseable` (D5).

## Open Questions

None. The shim disposition (D1) and pin form (D2) are decided.

## Slice Review Disposition

`user/reviews/920-review.slice.claude-agent-sdk-upgrade-and-rate-limit-parser-shim-retirement.md`
(z-ai/glm-5.2, **PASS**, 20260915, reviewed sha `5380878e`) — six PASS findings
and one CONCERN, accepted and fixed.

**F007 (scope accuracy) — accepted.** `tests/providers/openai/test_agent.py` was
listed among affected test files, but it has no SDK rate-limit dependency: its
only rate-limit test constructs `openai.RateLimitError` on an independent
provider path, and the file never imports `claude_agent_sdk`. It was swept in by
a broad `rate_limit` grep over `tests/` during scoping. Listing it risks an
implementer modifying an unrelated provider's tests in the name of criterion 9.
The affected-files list is now split into files requiring the criterion-9
rewrite (with the specific fabrication each one carries) and an explicit
not-affected entry for the OpenAI file, covered instead as a must-not-break
regression by walkthrough step 2.

No design decisions changed. D1–D6 stand as written; the four PASS findings on
scope, layering, integration points, and failure-mode enumeration confirmed the
dispatch asymmetry (D4) and the `sdk_type` exclusion-set requirement (D6)
against source.

## Effort

**3/5.** Small diff, concentrated risk. The cost is in test rewriting and live
verification, not in the production change.
