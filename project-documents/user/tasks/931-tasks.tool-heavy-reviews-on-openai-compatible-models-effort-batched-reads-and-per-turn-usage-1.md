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
        owns the set and clears it at the top of `handle_message` (Task 5), which gives
        "once per call" without agent state in the reader.
- [ ] Create `tests/providers/openai/test_usage.py`
  - [ ] OpenAI/Ollama shape (empty `choices`), OpenRouter shape (one choice, empty delta)
  - [ ] Ollama: `cached_tokens` present, no `completion_tokens_details` → `reasoning` None
  - [ ] Parametrized malformed shapes: field None, siblings intact, WARNING via `caplog`
  - [ ] Passing the same `warned` set on a second malformed chunk logs no second WARNING
  - [ ] The event-loop NFR check for this reader lives in the load-test tier (Task 11), not here
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
- [ ] Add a parametrized test per site asserting the built `credentials` **contains every
      item of** `profile_credentials(profile)` for the same profile, and that the site's
      extra keys are unchanged (`review_client.py` also carries `hooks` and `mode`; check
      each other site's current extras before writing its assertion). Equality would fail
      wherever a site adds keys of its own. Use each site's existing test seam; add the
      smallest seam if one is missing.
  - [ ] Success: existing tests for all six sites still pass
- [ ] Format, lint, typecheck, commit: `refactor: build agent credentials from one profile_credentials helper`

---

## Task 5 — `_stream_turn` reads usage and sends `stream_options` (D8, D12)

- [ ] Wire the flag to the agent: `OpenAICompatibleAgent` has no `credentials` member today
      (`provider.create_agent` passes named arguments only)
  - [ ] Add a constructor argument `sends_stream_usage: bool = True` on the agent
  - [ ] `providers/openai/provider.py` `create_agent` passes
        `sends_stream_usage=config.credentials.get("sends_stream_usage", True)`; an absent
        key (no profile involved, e.g. `server/routes/agents.py`) sends it, per the design
- [ ] `providers/openai/agent.py`: in `_stream_turn`
  - [ ] Pass `stream_options={"include_usage": True}` explicitly (not via `**kwargs`) unless
        the agent's `sends_stream_usage` is `False`
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
        (run total) onto the final Message metadata. Place them beside `stop_reason`, before
        the `if not self._tools_given:` early return, and unconditionally, so a run with no
        tools still records them (the same rule slice 918 set for `stop_reason`). Replace
        the existing `turn.reasoning_chars` stamp; do not add a second key.
  - [ ] Test a no-tools run: `turns` and `usage` are present on the final Message
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
- [ ] Tests in `tests/review/test_persistence.py` and `tests/review/test_models.py`
  - [ ] Frontmatter, digest, and JSON agree from one `ReviewResult`
  - [ ] Unreported fields: key absent, `not reported`, null; never 0
  - [ ] Existing artifact still parses under the existing frontmatter parsers
- [ ] Format, lint, typecheck; commit the code and tests **without** the snapshot fixture:
      `feat: render turns, token usage, and duration for successful reviews`
  - [ ] Expected: the `clean_pass_artifact.md` snapshot test fails until Task 10B

---

## Task 10B — Failure artifact and snapshot regeneration (D10, D12)

- [ ] `review/persistence.py`: `format_provider_failure_markdown` reads `telemetry` and
      `duration_seconds` off the error, like `exc.tool_calls_made`; CLI and pipeline call
      sites unchanged
- [ ] Tests in `tests/review/test_persistence.py`
  - [ ] Frontmatter, digest, and JSON agree from one failed `ProviderError`
  - [ ] An error with `telemetry=None` renders no fabricated zeros
- [ ] Regenerate `clean_pass_artifact.md` snapshot **once** (D10): run the snapshot test on
      the new code, review the diff to confirm only the new keys/lines changed, then commit
      the fixture
  - [ ] Success: full `pytest` passes
- [ ] Format, lint, typecheck, commit: `feat: record usage in provider-failure artifacts and refresh snapshot`

---

## Task 11 — Part C verification

- [ ] Grep gates, run once each
  - [ ] `grep -rn "providers.openai" src/squadron/review/` returns nothing
  - [ ] `grep -n "squadron" src/squadron/core/usage.py` returns nothing
- [ ] Load test for the event-loop NFR (`.claude/rules/python.md`, load-test tier). Create
      `tests/load/test_usage_reader_loop.py`, styled after `tests/load/test_grep_timeout.py`
      (module docstring naming the rule and design NFR; generous bounds)
  - [ ] Feed a stubbed 5,000-chunk stream (usage on the last chunk, plus a few malformed
        ones) through `_stream_turn` while a concurrent `asyncio` ticker task records its
        scheduling gaps; assert the largest gap stays under a generous bound (for example
        50 ms), so per-chunk usage reading does not starve the loop
  - [ ] Assert mean `read_chunk_usage` cost under 1 ms per call over 1,000 calls
  - [ ] No CI wiring task is needed: `ci.yml` runs `uv run pytest` over `testpaths =
        ["tests"]`, which already includes `tests/load/`. Confirm by running
        `pytest tests/load/test_usage_reader_loop.py` once.
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
  - [ ] The event-loop NFR check for batches lives in the load-test tier (Task 15), not here
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

- [ ] Load test for the event-loop NFR: create `tests/load/test_read_file_batch_loop.py`,
      styled after `tests/load/test_grep_timeout.py`
  - [ ] Real files on disk (a batch of several files near the byte budget) read through the
        registered `read_file` executor while an `asyncio` ticker task records scheduling
        gaps; assert the largest gap stays under a generous bound, so a batch does not
        block the loop
  - [ ] Patch `asyncio.to_thread` with a counting wrapper: a five-path batch calls it
        exactly once
  - [ ] Runs under the existing `uv run pytest` in CI; no wiring task needed (see Task 11)
- [ ] Full `pytest`, `ruff format --check`, `ruff check`, `pyright`: all clean
- [ ] Live run (OpenRouter key; else stop and tell the Project Manager):
      `sq review slice 931 --model glm-flash -vv`
  - [ ] At least one `read_file` call carries `paths` with >1 entry and output shows
        `==> path <==` headers (walkthrough step 4)
  - [ ] Record `Tool calls made` and `Turns` versus the Task 11 baseline in the DEVLOG entry
