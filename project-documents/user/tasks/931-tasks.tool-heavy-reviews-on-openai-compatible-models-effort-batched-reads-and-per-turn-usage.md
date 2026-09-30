---
docType: tasks
slice: tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage
project: squadron
lld: user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md
dependencies: [924]
projectState: >
  Slice design written (2026-09-28), not yet implemented. OpenAI-compatible reviews send no
  effort, `read_file` takes one path, and `_stream_turn` never reads usage. Release 0.16.0
  is current on main; no integration branch is configured.
dateCreated: 20260929
dateUpdated: 20260929
status: not_started
---

## Context Summary

- Working on **931 tool-heavy reviews on OpenAI-compatible models**: fixes issues #154
  (effort), #157 (batched reads), #158 (per-turn usage). Order is **C → B → A**: usage first
  so B and A are measured, not guessed.
- Each part lands as its own commits, each green on the full suite and revertible alone.
  B and A share no code. B can move to its own slice with no design change (D5–D7).
- Design decisions D1–D12 live in the slice design. Tasks cite them by number and do not
  restate them. The D12 failure table and D10 frontmatter table are the contracts.
- Touches `core/usage.py` (new), `core/models.py`, `models/aliases.py`, `pipeline/resolver.py`,
  `providers/{base,profiles,errors}.py`, `providers/openai/{usage(new),provider,agent}.py`,
  `providers/sdk/provider.py`, `providers/codex/agent.py`, `review/{turn_capture,review_client,models,persistence}.py`,
  `tools/{limits,guidance}.py`, `tools/builtin/file_tools.py`, `data/models.toml`.
- Out of scope: Codex effort, SDK usage, `--effort` flag, per-step `effort:`, #155/#156/#159,
  read timeouts (design: Out of scope).
- Tests use stubbed `AsyncStream`s in the style of slice 927's `chunk.model` tests
  (`tests/providers/openai/`). No live calls run in the suite.
- Every code task ends with `ruff format`, `ruff check`, `pyright` (zero errors) and its
  tests before its commit. Commit messages follow the repo's semantic prefixes.
- Effort: 4/5. Next planned slice: per `cf next` after 931 closes.

---

# Part C — Per-turn usage (#158)

## Task 1 — Create the slice branch

- [ ] Confirm `cf config get git.integration_branch` is empty (target = `main`) and
      `git status` is clean
- [ ] `git checkout -b 931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage main`
  - [ ] Success: `git branch --show-current` prints the new branch name

---

## Task 2 — `core/usage.py`: neutral types and `add_optional` (D8)

- [ ] Run `pytest tests/review/test_turn_capture.py` once first; note it passes (the guard
      for this move)
- [ ] Create `src/squadron/core/usage.py`, standard-library imports only
  - [ ] Frozen dataclass `TokenUsage`: `prompt`, `cached`, `completion`, `reasoning`, each
        `int | None = None`; a method returning the field-wise `add_optional` sum of two
  - [ ] Mutable dataclass `RunTelemetry`: `turns: int = 0`, `reasoning_chars: int = 0`,
        `usage: TokenUsage`; a method that folds one turn in; a method returning a snapshot copy
  - [ ] `add_optional(total, value)`: moved from `turn_capture._add`, body unchanged
- [ ] Replace `_add` in `review/turn_capture.py` with an import of `add_optional`; update all
      call sites (lines ~103–151)
- [ ] Create `tests/core/test_usage.py`
  - [ ] `add_optional`: None+None → None, None+n → n, n+None → n, n+m → sum
  - [ ] `TokenUsage` sum keeps None only when both sides are None, per field
  - [ ] `RunTelemetry` fold-in accumulates turns, reasoning chars, and usage; a snapshot is
        independent of later folds
  - [ ] Success: `tests/review/test_turn_capture.py` passes unedited
- [ ] Format, lint, typecheck, commit: `refactor: move None-preserving sum to core/usage`

---

## Task 3 — `providers/openai/usage.py`: chunk usage reader (D8, D12 malformed row)

- [ ] Create `src/squadron/providers/openai/usage.py` with
      `read_chunk_usage(chunk) -> TokenUsage | None`
  - [ ] Returns `None` when `chunk.usage` is absent
  - [ ] `prompt`/`completion` from `prompt_tokens`/`completion_tokens`; `cached` from
        `prompt_tokens_details.cached_tokens`; `reasoning` from
        `completion_tokens_details.reasoning_tokens`; each field `None` when not reported
  - [ ] A non-int count or a wrong-typed details object makes that field `None`, leaves the
        siblings intact, and logs a WARNING naming the field and `%.200r` of the raw value.
        Never raises.
  - [ ] Signature is `read_chunk_usage(chunk, warned: set[str])`. The reader logs each
        malformed field only if its name is not yet in `warned`, then adds it. The agent
        owns the set and clears it at the top of `handle_message` (Task 6), which gives
        "once per call" without agent state in the reader.
- [ ] Create `tests/providers/openai/test_usage.py`
  - [ ] OpenAI/Ollama shape (empty `choices`), OpenRouter shape (one choice, empty delta)
  - [ ] Ollama: `cached_tokens` present, no `completion_tokens_details` → `reasoning` None
  - [ ] Parametrized malformed shapes: field None, siblings intact, WARNING via `caplog`
  - [ ] Passing the same `warned` set on a second malformed chunk logs no second WARNING
  - [ ] NFR (design: Special Considerations, event loop): a test times 1,000 calls to
        `read_chunk_usage` on a full usage chunk and asserts the mean is under 1 ms per call
        (a generous bound that catches accidental I/O or regex work, not a benchmark)
  - [ ] Success: all pass; no `openai` package types are imported by `core/usage.py`

- [ ] Format, lint, typecheck, commit: `feat: read token usage from OpenAI-shaped stream chunks`

---

## Task 4 — `sends_stream_usage` flag and `profile_credentials` (Technical Requirements)

- [ ] `providers/profiles.py`: add `ProviderProfile.sends_stream_usage: bool = True`
  - [ ] Read it from a user profile table like the other profile fields; reject a non-bool
        with the same explicit error style the file already uses
  - [ ] Set it `False` on the gemini entry of `BUILT_IN_PROFILES`
  - [ ] Add `profile_credentials(profile) -> dict` returning `api_key_env`,
        `default_headers`, `sends_stream_usage`
- [ ] `tests/providers/test_profiles.py`: user-table parsing (true, false, absent, non-bool),
      gemini built-in is False, every other built-in is True, `profile_credentials` keys
- [ ] Format, lint, typecheck, commit: `feat: add sends_stream_usage profile flag and profile_credentials`

---

## Task 4B — Switch the six credential call sites (Technical Requirements)

- [ ] Switch each of the six call sites from hand-copied fields to `**profile_credentials(profile)`
      — one sub-task each, keeping each diff reviewable:
  - [ ] `review/review_client.py`
  - [ ] `pipeline/actions/dispatch.py`
  - [ ] `pipeline/summary_oneshot.py`
  - [ ] `metrology/audit.py`
  - [ ] `pr/composer.py`
  - [ ] `cli/commands/spawn.py`
  - [ ] `providers/auth.py` is NOT one of the six; leave it unchanged
- [ ] Add a parametrized test asserting each site's built `credentials` equals
      `profile_credentials(profile)` for the same profile (use each site's existing test
      seam; add the smallest seam if one is missing)
  - [ ] Success: existing tests for all six sites still pass
- [ ] Format, lint, typecheck, commit: `refactor: build agent credentials from one profile_credentials helper`

---

## Task 5 — `_stream_turn` reads usage and sends `stream_options` (D8, D12)

- [ ] `providers/openai/agent.py`: in `_stream_turn`
  - [ ] Pass `stream_options={"include_usage": True}` explicitly (not via `**kwargs`) unless
        `credentials.get("sends_stream_usage")` is `False`; an absent key sends it
  - [ ] Call `read_chunk_usage` on every chunk **before** the `if not chunk.choices: continue`
        guard, next to the existing `chunk.model` read; last non-None value in a turn wins.
        Pass the agent's `warned` set (a new per-call attribute, cleared at the top of
        `handle_message`, beside `_answering_models`)
  - [ ] Return it on `TurnResult.usage`
- [ ] Extend `tests/providers/openai/test_agentic_loop.py` (or a new sibling file) with
      stubbed streams
  - [ ] Both chunk shapes yield the turn's usage and the turn's text and tool calls intact
  - [ ] A stream with no usage chunk completes with `usage=None`
  - [ ] gemini-profile agent omits `stream_options`; openrouter-profile agent sends it; an
        agent built with no profile (server-route shape) sends it
  - [ ] A request with no effort set is otherwise identical to today's
  - [ ] Success: all pass
- [ ] Format, lint, typecheck, commit: `feat: request and read per-turn usage in the OpenAI agent`

---

## Task 6 — Loop accumulation and stamping (D8)

- [ ] `providers/openai/agent.py`
  - [ ] Add per-call `RunTelemetry`, reset at the top of `handle_message` beside
        `_answering_models`; fold each `_stream_turn` result in; `turns` counts
        `_stream_turn` calls
  - [ ] `_stamp_tool_telemetry` stamps `turns`, `usage`, and `RunTelemetry.reasoning_chars`
        (run total) onto the final Message metadata
  - [ ] Keep the `handle_message` change to a few lines. The file is already over 300
        lines; do not split it in this task (design: Special Considerations)
- [ ] Tests in `tests/providers/openai/test_agentic_loop.py`
  - [ ] Three-turn loop: metadata `turns == 3`, usage summed per field, reasoning chars is
        the run total (not the final turn's)
  - [ ] A backend reporting only some fields keeps the others `None`, never 0
  - [ ] Two consecutive `handle_message` calls do not leak telemetry into each other
  - [ ] Success: existing `reasoning_chars` assertions updated only where the run total
        differs from the final turn, each with a comment
- [ ] Format, lint, typecheck, commit: `feat: accumulate turns, usage, and reasoning chars per run`

---

## Task 6B — Usage WARNINGs and the exit signal (D12)

- [ ] `providers/openai/agent.py`
  - [ ] Set a `completed` flag on the normal return; the existing `finally` logs the exit
        WARNING when unset (text in D12 last row)
  - [ ] Log the once-per-call "backend reported no token usage" WARNING when no turn
        reported usage (D12)
  - [ ] Confirm malformed-usage WARNINGs are once per call via the `warned` set from Task 5
- [ ] Tests in `tests/providers/openai/test_agentic_loop.py`
  - [ ] No-usage stream: exactly one WARNING per call across three turns; fields `None`
  - [ ] Malformed usage on two turns: one WARNING per field per call
  - [ ] Exit WARNING fires when the loop ends without a final response (iteration guard)
        and carries the turn and token counts; does not fire on a normal return
  - [ ] Success: all pass
- [ ] Format, lint, typecheck, commit: `feat: warn on missing usage and non-normal agent exits`

---

## Task 7 — `ProviderError.telemetry` and stream failure conversions (D12)

- [ ] `providers/errors.py`: add keyword-only `telemetry: RunTelemetry | None = None` and
      `duration_seconds: float | None = None` to `ProviderError`; existing raisers unchanged;
      `EmptyFinalTurnError` uses the inherited `telemetry`
  - [ ] In the agent, `EmptyFinalTurnError` keeps final-turn `reasoning_chars` for its message
        and attribute, and its `telemetry` carries the run total
- [ ] `providers/openai/agent.py`
  - [ ] Add `httpx.TimeoutException` → `ProviderTimeoutError` and `httpx.TransportError` →
        `ProviderError` conversions next to the existing ones
  - [ ] An outer `except ProviderError` attaches a snapshot of the run's `RunTelemetry` and
        re-raises (covers the iteration-guard error too); it swallows nothing
  - [ ] Any other exception propagates unconverted; the `finally` WARNING still fires
- [ ] Tests (each asserts its signal with `caplog`, per D12 table)
  - [ ] Stubbed stream raises on turn 3: error `telemetry.turns == 2` with summed usage
  - [ ] Stubbed streams raise `httpx.ReadTimeout` and `httpx.RemoteProtocolError`
        mid-iteration: converted type, attached telemetry, exit WARNING
  - [ ] `RuntimeError` on turn 2 propagates unchanged; exit WARNING carries `turns=1`
  - [ ] Iteration-guard `ProviderError` carries telemetry
  - [ ] Success: the exit WARNING text matches D12 and all pass
- [ ] Format, lint, typecheck, commit: `feat: attach run telemetry to provider errors and convert mid-stream transport failures`

---

## Task 8 — `TurnCapture` sums turns and usage (D8)

- [ ] `review/turn_capture.py`: `TurnCapture` gains `turns` and `usage`, summed with
      `add_optional` across `collect_turn` calls, including the recovery turn
  - [ ] `fold_empty_turn` reads the total from `ProviderError.telemetry`, not from the
        error's final-turn `reasoning_chars`
  - [ ] `review/` must not import `providers/openai`; it may import `core.usage` and
        `providers.errors`
- [ ] Extend `tests/review/test_turn_capture.py`
  - [ ] Two-call sum plus a recovery turn after `EmptyFinalTurnError`: turns and usage sum;
        reasoning chars is the run total
  - [ ] An error with `telemetry=None` folds as before (no crash, no fabricated zeros)
  - [ ] Success: all pass, prior tests unchanged
- [ ] Format, lint, typecheck, commit: `feat: sum turns and usage across review turn captures`

---

## Task 9 — `review_client` timing and failure stamping (D9)

- [ ] `review/review_client.py`
  - [ ] Read `time.monotonic()` before `provider.create_agent`; after `_collect_review` on
        success (recovery turn included); copy `turns`, `usage`, `duration_seconds` onto
        `ReviewResult`
  - [ ] Narrow `except ProviderError` sets `exc.duration_seconds` and re-raises
- [ ] `review/models.py`: `ReviewResult` gains `turns: int | None`, `usage: TokenUsage`
      (from `core.usage`; not four loose fields), and `duration_seconds: float | None = None`
- [ ] Tests in `tests/review/test_review_client.py`
  - [ ] Duration is stamped on success (fake clock) for an SDK-shaped and a Codex-shaped
        provider stub, not only openai
  - [ ] A `ProviderError` leaves with `duration_seconds` set and is the same exception object
  - [ ] Success: all pass
- [ ] Format, lint, typecheck, commit: `feat: time reviews and carry usage onto ReviewResult`

---

## Task 10 — Render usage: frontmatter, digest, JSON, failure artifact (D10)

- [ ] `review/persistence.py`, `review/models.py`
  - [ ] Frontmatter keys `turns`, `promptTokens`, `cachedTokens`, `completionTokens`,
        `reasoningTokens`, `durationSeconds`, each emitted only when it has a value (D10 table)
  - [ ] Run Digest lines `Turns`, `Tokens — prompt / cached / completion / reasoning`,
        `Duration` (one decimal), always rendered, `not reported` via `_render_optional`
  - [ ] `to_dict()` adds `turns`, `prompt_tokens`, `cached_tokens`, `completion_tokens`,
        `reasoning_tokens`, `duration_seconds`, always present, null when unreported
  - [ ] `format_provider_failure_markdown` reads `telemetry` and `duration_seconds` off the
        error, like `exc.tool_calls_made`; CLI and pipeline call sites unchanged
- [ ] Tests in `tests/review/test_persistence.py` and `tests/review/test_models.py`
  - [ ] Frontmatter, digest, and JSON agree from one `ReviewResult`, and from one failed
        `ProviderError`
  - [ ] Unreported fields: key absent, `not reported`, null; never 0
  - [ ] Existing artifact still parses under the existing frontmatter parsers
- [ ] Regenerate `clean_pass_artifact.md` snapshot **once** (D10): run the snapshot test on
      the new code, review the diff to confirm only the new keys/lines changed, then commit
      the fixture
  - [ ] Success: full `pytest` passes
- [ ] Format, lint, typecheck, commit: `feat: record turns, token usage, and duration in review artifacts`

---

## Task 11 — Part C verification

- [ ] Grep gates, run once each
  - [ ] `grep -rn "providers.openai" src/squadron/review/` returns nothing
  - [ ] `grep -n "squadron" src/squadron/core/usage.py` returns nothing
- [ ] Full `pytest`, `ruff format --check`, `ruff check`, `pyright`: all clean
- [ ] Live baseline (needs an OpenRouter key; if unavailable, stop and tell the Project
      Manager): `sq review slice 931 --model glm-flash -v`
  - [ ] Saved review has `turns`, four token keys, `durationSeconds`, no `effort` key, and
        the new digest lines (walkthrough step 2)
  - [ ] Record `cachedTokens` (answers whether OpenRouter caches the resent history) in the
        DEVLOG entry, not in code
- [ ] Commit any fixups: `fix: <what>` (skip if none)

---

# Part B — Batched reads (#157)

## Task 12 — Extract the single-file read helper (D5)

- [ ] Add a byte-for-byte characterization test **before any source change**, in a new
      `tests/tools/test_read_file.py` (or the existing file-tools test)
  - [ ] Cover: normal file, truncation at `MAX_READ_BYTES`, jail escape, missing file,
        line-reference fallback, special-file rejection; assert exact `ToolResult` content
  - [ ] Success: passes on unmodified code
- [ ] `tools/builtin/file_tools.py`: extract the existing single-file body (jail check,
      line-ref fallback, special-file rejection, truncation) into a helper; `read_file`
      calls it for `path`
  - [ ] Success: characterization test passes unedited
- [ ] Format, lint, typecheck, commit: `refactor: extract single-file read helper from read_file`

---

## Task 13 — `paths` and the batch budget (D5, D6, D12)

- [ ] `tools/limits.py`: add `MAX_READ_BATCH_BYTES = MAX_READ_BYTES` with a comment tying it
      to `min_tool_result_chars()`
- [ ] `tools/builtin/file_tools.py`
  - [ ] Schema per the design's API Contracts: `path` and `paths`, `required: []`
  - [ ] Executor: both or neither → error naming the rule; empty `paths` → error
  - [ ] `path` alone → unchanged result, no header
  - [ ] `paths` (even one entry) → `==> {requested path} <==` header per file, request order,
        each through the Task 12 helper; per-file failures render inline
  - [ ] `is_error` True only when every file failed
  - [ ] Budget: append files until the next would exceed `MAX_READ_BATCH_BYTES`; each
        remaining path gets `[not read: batch budget of N bytes reached; request it in another call]`;
        a first file over budget is still read with normal truncation
  - [ ] WARNING `read_file: batch budget of %d bytes reached; %d path(s) not read`
- [ ] Tests in `tests/tools/test_read_file.py`
  - [ ] Batch: order, headers, single-entry `paths`
  - [ ] Mixed failure inline with `is_error` False; all-fail `is_error` True
  - [ ] Budget cutoff with marker lines and WARNING (`caplog`); oversize first file
  - [ ] Both / neither / empty `paths` errors
  - [ ] Invariant: `MAX_READ_BATCH_BYTES` plus header overhead for a full batch is below
        `min_tool_result_chars()`
  - [ ] The registered tool schema contains both properties
  - [ ] NFR (event loop): a five-path batch calls `asyncio.to_thread` exactly once (patch it
        with a counting wrapper), so no blocking read runs on the event loop
  - [ ] Success: all pass, Task 12 characterization test still unedited
- [ ] Format, lint, typecheck, commit: `feat: let read_file take several paths under a batch byte budget`

---

## Task 14 — Guidance paragraph (D7)

- [ ] `tools/guidance.py`: add the D7 paragraph verbatim from the design; keep the
      docstring's rule that prose names no specific tool
  - [ ] Keep the existing "Do not read files a claim does not depend on" sentence
- [ ] `tests/tools/test_guidance.py`: block contains the paragraph; contains no tool name
      (`read_file`, `grep`, etc.), consistent with existing assertions
  - [ ] Success: all pass; update any snapshot of the block once, reviewing the diff
- [ ] Format, lint, typecheck, commit: `feat: tell models to batch independent reads`

---

## Task 15 — Part B verification

- [ ] Full `pytest`, `ruff format --check`, `ruff check`, `pyright`: all clean
- [ ] Live run (OpenRouter key; else stop and tell the Project Manager):
      `sq review slice 931 --model glm-flash -vv`
  - [ ] At least one `read_file` call carries `paths` with >1 entry and output shows
        `==> path <==` headers (walkthrough step 4)
  - [ ] Record `Tool calls made` and `Turns` versus the Task 11 baseline in the DEVLOG entry

---

# Part A — Effort (#154)

## Task 16 — `Effort` enum and `AgentConfig.effort` (D1)

- [ ] `core/models.py`: `Effort(StrEnum)` with `none`, `low`, `medium`, `high`, `xhigh`;
      `AgentConfig.effort: Effort | None = None` beside `max_output_tokens`
- [ ] Test in `tests/test_models.py`: values, construction from string, invalid value raises
  - [ ] Success: passes
- [ ] Format, lint, typecheck, commit: `feat: add Effort vocabulary and AgentConfig.effort`

---

## Task 17 — Alias field and reader (D1, D2)

- [ ] `models/aliases.py`: `ModelAlias.effort`; `_extract_metadata` validates it against
      `Effort` following the `max_output_tokens` block (line ~73)
  - [ ] Invalid values, including a bool and a non-string, log a WARNING naming the alias
        and file, and the field is skipped
  - [ ] New reader `model_effort(name) -> Effort | None`, mirroring `model_max_output_tokens`
        (unknown/None alias → None)
- [ ] `data/models.toml`: header comment documents `effort`; no built-in alias sets it
- [ ] Tests in `tests/models/test_aliases.py`: parametrized valid / invalid / bool / absent;
      WARNING content via `caplog`; `model_effort` for known, unknown, and None alias
  - [ ] Success: all pass
- [ ] Format, lint, typecheck, commit: `feat: add optional effort to model aliases`

---

## Task 18 — `ResolvedModel.effort` and pipeline call sites (D11)

- [ ] `pipeline/resolver.py`: `ResolvedModel.effort`, filled by `model_effort(alias)` (line ~73)
- [ ] Pass `resolved.effort` into the `AgentConfig` each site builds — one sub-task each:
  - [ ] `pipeline/actions/review.py` (near line 390)
  - [ ] `pipeline/actions/dispatch.py`
  - [ ] `pipeline/summary.py`
- [ ] Tests: `ResolvedModel.effort` round-trip in `tests/pipeline/test_resolver.py`; each
      action passes it into its config (extend `test_review_action.py`, `test_dispatch.py`,
      `test_summary.py`)
  - [ ] Success: all pass
- [ ] Format, lint, typecheck, commit: `feat: carry alias effort through pipeline resolution`

---

## Task 19 — CLI and `review_client` recording (D4, D10)

- [ ] `cli/commands/review.py`: read `model_effort(alias_name)` next to
      `model_max_output_tokens` (line ~703) and pass it through the same path (lines ~721, ~784)
- [ ] `providers/base.py`: `ProviderCapabilities.applies_effort: bool = False`
- [ ] `review/review_client.py`: accept `effort`, put it on `AgentConfig`, record
      `sent_effort = effort if provider.capabilities.applies_effort else None` on
      `ReviewResult.effort` (mirror lines ~257–277)
- [ ] `review/models.py`, `review/persistence.py`: `ReviewResult.effort`; frontmatter `effort`
      only when sent; digest `Effort: <level>` or `backend default`; `to_dict()` `effort`
      always present, null when unset
- [ ] Tests
  - [ ] `test_review_client.py`: recorded only when `applies_effort` is True
  - [ ] `test_persistence.py` / `test_models.py`: frontmatter, digest, JSON agree; absent
        key when unset
  - [ ] `test_cli_review.py`: alias effort reaches the client; CLI and pipeline produce the
        same effort field for the same alias (interface parity)
  - [ ] Success: all pass; artifact snapshot unchanged when no effort is set
- [ ] Format, lint, typecheck, commit: `feat: record the effort a review actually ran with`

---

## Task 20 — OpenAI provider applies effort (D3, D4)

- [ ] `providers/openai/provider.py`: `applies_effort=True`; pass `config.effort` to the agent
      (mirror line ~80); DEBUG log of the sent level in `create_agent` (D11)
- [ ] `providers/openai/agent.py`: send `reasoning_effort=<value>` explicitly in
      `_stream_turn` on every turn when set; omit when unset
- [ ] Tests in `tests/providers/openai/`: `reasoning_effort` on every turn of a tool loop and
      on the recovery turn; absent when unset; `none` is sent as `"none"`; capability flag
      true in `test_capabilities.py`
  - [ ] Success: all pass
- [ ] Format, lint, typecheck, commit: `feat: send reasoning_effort from the OpenAI-compatible agent`

---

## Task 21 — SDK provider applies effort (D1, D4)

- [ ] `providers/sdk/provider.py`: `applies_effort=True`; map `Effort` → `ClaudeAgentOptions.effort`;
      `none` → `thinking={"type": "disabled"}` with no `effort`
  - [ ] Confirm `ClaudeAgentOptions.effort` accepts `low|medium|high|xhigh` in the installed
        `claude-agent-sdk` (0.2.162) before writing the mapping; if `xhigh` differs, stop and
        ask the Project Manager
- [ ] Tests in `tests/providers/sdk/test_provider.py`: each level maps; `none` yields
      `thinking` and no `effort`; unset yields neither; capability flag true
  - [ ] Success: all pass
- [ ] Format, lint, typecheck, commit: `feat: apply alias effort in the SDK provider`

---

## Task 22 — Codex warns (D4)

- [ ] `providers/codex/agent.py`: WARNING `Codex agent cannot apply effort=%s; the backend
      default applies` when `config.effort` is set, beside the `max_output_tokens` warning
      (line ~45); `applies_effort` stays False
- [ ] Test in `tests/providers/codex/test_agent.py`: WARNING with `caplog`; and a
      `review_client` test that the artifact has no `effort` key for this provider
  - [ ] Success: all pass
- [ ] Format, lint, typecheck, commit: `feat: warn when Codex cannot apply effort`

---

# Wrap-up

## Task 23 — Full verification and live walkthrough

- [ ] Full `pytest`, `ruff format --check`, `ruff check`, `pyright`: all clean; both import
      greps from Task 11 re-run clean
- [ ] `cf validate frontmatter` passes on a saved review that carries the new keys
- [ ] Live walkthrough steps 3, 5, 6, 10 (OpenRouter key; else stop and tell the Project
      Manager): low-effort alias review, JSON parity, pipeline parity, invalid value
  - [ ] `effort: low` in frontmatter; JSON matches frontmatter; `sq run review 931
        --model glm-flash-low` records the same fields as the CLI; invalid value logs the
        skip WARNING naming alias and file
- [ ] Walkthrough steps 7–9 need Ollama, OpenAI, Gemini, and Codex access. Run whichever
      the environment has; list the rest by name in the DEVLOG entry as not run
  - [ ] Step 8 (mid-loop failure on `local`): failure artifact has `providerFailure: true`,
        `turns` ≥ 1, `durationSeconds`
- [ ] Commit any fixups: `fix: <what>` (skip if none)

---

## Task 24 — Follow-up issues and #154 comment (Implementation Notes step 4)

- [ ] File three GitHub issues with `gh issue create`, then link each number from the
      decision that defers it (D4, Out of scope, Risk Assessment)
  - [ ] Codex effort (needs `codex_app_server` to verify `thread_start`'s reasoning parameter)
  - [ ] SDK usage from `ResultMessage.usage` onto `core.usage.TokenUsage`
  - [ ] Enable `sends_stream_usage` on gemini once a probe succeeds; include the probe
        command from Risk Assessment
- [ ] Comment the D2 decision (aliases, not flags) on #154
- [ ] Commit the design-doc links: `docs: link follow-up issues from slice 931 design`

---

## Task 25 — Close out

- [ ] Add a CHANGELOG entry (short user-facing bullets: alias `effort`, `read_file` `paths`,
      usage and duration in review artifacts)
- [ ] Write the DEVLOG entry per `prompt.ai-project.system.md`, Session State Summary,
      including the baseline-versus-low-effort comparison and the `cachedTokens` answer
- [ ] Mark every task above `[x]` (dropped items too), set this file's `status: complete`,
      and set the slice design and slice plan entry to complete
- [ ] Merge into the target: re-read `cf config get git.integration_branch`,
      `git checkout <target>`, `git merge 931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage`;
      if either command fails, stop and ask the Project Manager
- [ ] Commit: `docs: close out slice 931`
