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
dateUpdated: 20260930
status: in_progress
---

> Part 2 of 2. Parts C and B (Tasks 1–15) are in `931-tasks.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage-1.md`. Task numbers continue across files; Tasks 11 and 15 (baseline and batched-read runs) are referenced below.

# Part A — Effort (#154)

## Task 16 — `Effort` enum and `AgentConfig.effort` (D1)

- [x] `core/models.py`: `Effort(StrEnum)` with `none`, `low`, `medium`, `high`, `xhigh`;
      `AgentConfig.effort: Effort | None = None` beside `max_output_tokens`
- [x] Test in `tests/test_models.py`: values, construction from string, invalid value raises
  - [x] Success: passes
- [x] Format, lint, typecheck, commit: `feat: add Effort vocabulary and AgentConfig.effort`

---

## Task 17 — Alias field and reader (D1, D2)

- [x] `models/aliases.py`: `ModelAlias.effort`; `_extract_metadata` validates it against
      `Effort` following the `max_output_tokens` block (line ~73)
  - [x] Invalid values, including a bool and a non-string, log a WARNING naming the alias
        and file, and the field is skipped
  - [x] New reader `model_effort(name) -> Effort | None`, mirroring `model_max_output_tokens`
        (unknown/None alias → None)
- [x] `data/models.toml`: header comment documents `effort`; no built-in alias sets it
- [x] Tests in `tests/models/test_aliases.py`: parametrized valid / invalid / bool / absent;
      WARNING content via `caplog`; `model_effort` for known, unknown, and None alias
  - [x] Success: all pass
- [x] Format, lint, typecheck, commit: `feat: add optional effort to model aliases`

---

## Task 18 — `ResolvedModel.effort` and pipeline call sites (D11)

- [x] `pipeline/resolver.py`: `ResolvedModel.effort`, filled by `model_effort(alias)` (line ~73)
- [x] Carry `resolved.effort` to where each pipeline path builds its `AgentConfig` — one
      sub-task each:
  - [x] `pipeline/actions/review.py` (near line 390): pass `effort=settings.resolved.effort`
        to `run_review_with_profile` beside `max_output_tokens`; the `AgentConfig` itself is
        built in `review_client` (Task 19)
  - [x] `pipeline/actions/dispatch.py`: set `effort` on the `AgentConfig` at line ~157
  - [x] Summary path: `pipeline/actions/summary.py` builds no `AgentConfig`. Add an
        `effort: Effort | None = None` keyword to `capture_summary_via_profile_with_telemetry`
        and `capture_summary_via_profile` in `pipeline/summary_oneshot.py`, set it on the
        `AgentConfig` at line ~102, and pass `resolved.effort` from the call at
        `actions/summary.py` line ~274. Check `cli/commands/summary_run.py` (line ~61) and
        pass the alias effort there too, so CLI and pipeline summaries match
- [x] Tests: `ResolvedModel.effort` round-trip in `tests/pipeline/test_resolver.py`; each
      path gets the effort into its config (extend `test_review_action.py`, `test_dispatch.py`,
      `test_summary.py`, and the `summary_oneshot` tests: the built `AgentConfig.effort`
      matches the alias)
  - [x] Success: all pass
- [x] Format, lint, typecheck, commit: `feat: carry alias effort through pipeline resolution`
  - summary_run receives a resolved model id, not the alias, so the prompt renderer now emits a hidden --effort on sq _summary-run when the alias sets one.

---

## Task 19 — CLI and `review_client` recording (D4, D10)

- [x] `cli/commands/review.py`: read `model_effort(alias_name)` next to
      `model_max_output_tokens` (line ~703) and pass it through the same path (lines ~721, ~784)
- [x] `providers/base.py`: `ProviderCapabilities.applies_effort: bool = False`
- [x] `review/review_client.py`: accept `effort`, put it on `AgentConfig`, record
      `sent_effort = effort if provider.capabilities.applies_effort else None` on
      `ReviewResult.effort` (mirror lines ~257–277)
- [x] `review/models.py`: add `ReviewResult.effort` (rendering follows in Task 19B)
- [x] Tests
  - [x] `test_review_client.py`: recorded only when `applies_effort` is True
  - [x] `test_cli_review.py`: alias effort reaches the client; CLI and pipeline produce the
        same effort field for the same alias (interface parity)
  - [x] Success: all pass
- [x] Format, lint, typecheck, commit: `feat: carry alias effort to the review client and result`

---

## Task 19B — Render effort (D10)

- [x] `review/persistence.py`, `review/models.py`: frontmatter `effort` only when sent;
      digest `Effort: <level>` or `backend default`; `to_dict()` `effort` always present,
      null when unset
- [x] Tests in `test_persistence.py` / `test_models.py`: frontmatter, digest, JSON agree;
      absent key when unset
  - [x] Success: all pass; artifact snapshot unchanged when no effort is set
- [x] Format, lint, typecheck, commit: `feat: record the effort a review actually ran with`
  - Per D10 the digest's Effort line always renders ('backend default' when unset), so pinned digest fixtures gained that line; the task's 'snapshot unchanged' expectation conflicted with D10 and D10 was followed.

---

## Task 20 — OpenAI provider applies effort (D3, D4)

- [x] `providers/openai/provider.py`: `applies_effort=True`; pass `config.effort` to the agent
      (mirror line ~80); DEBUG log of the sent level in `create_agent` (D11)
- [x] `providers/openai/agent.py`: send `reasoning_effort=<value>` explicitly in
      `_stream_turn` on every turn when set; omit when unset
- [x] Tests in `tests/providers/openai/`: `reasoning_effort` on every turn of a tool loop and
      on the recovery turn; absent when unset; `none` is sent as `"none"`; capability flag
      true in `test_capabilities.py`
  - [x] D12 "backend rejects `reasoning_effort`" row: a stubbed 400 on a request carrying
        `reasoning_effort` surfaces as `ProviderAPIError` (extend the existing 4xx test
        from Task 7 if it fits)
  - [x] Success: all pass
- [x] Format, lint, typecheck, commit: `feat: send reasoning_effort from the OpenAI-compatible agent`

---

## Task 21 — SDK provider applies effort (D1, D4)

- [x] `providers/sdk/provider.py`: `applies_effort=True`; map `Effort` → `ClaudeAgentOptions.effort`;
      `none` → `thinking={"type": "disabled"}` with no `effort`
  - [x] Confirm `ClaudeAgentOptions.effort` accepts `low|medium|high|xhigh` in the installed
        `claude-agent-sdk` (0.2.162) before writing the mapping; if `xhigh` differs, stop and
        ask the Project Manager
- [x] Tests in `tests/providers/sdk/test_provider.py`: each level maps; `none` yields
      `thinking` and no `effort`; unset yields neither; capability flag true
  - [x] Success: all pass
- [x] Format, lint, typecheck, commit: `feat: apply alias effort in the SDK provider`
  - claude-agent-sdk 0.2.162 EffortLevel is low|medium|high|xhigh|max; xhigh maps as-is.

---

## Task 22 — Codex warns (D4)

- [x] `providers/codex/agent.py`: WARNING `Codex agent cannot apply effort=%s; the backend
      default applies` when `config.effort` is set, beside the `max_output_tokens` warning
      (line ~45); `applies_effort` stays False
- [x] Test in `tests/providers/codex/test_agent.py`: WARNING with `caplog`; and a
      `review_client` test that the artifact has no `effort` key for this provider
  - [x] Success: all pass
- [x] Format, lint, typecheck, commit: `feat: warn when Codex cannot apply effort`

---

# Wrap-up

## Task 23 — Full verification and live walkthrough

- [x] Full `pytest`, `ruff format --check`, `ruff check`, `pyright`: all clean; both import
      greps from Task 11 re-run clean
- [x] `cf validate frontmatter` passes on a saved review that carries the new keys
- [x] Walkthrough step 1 first, since steps 3, 5, 6, 8–10 depend on it: confirm
      `~/.config/squadron/models.toml` defines `glm-flash-low` (profile `openrouter`, same
      model id as built-in `glm-flash`, `effort = "low"`), and that `sq models list` shows it.
      If the file lacks it, add it there; this is the user's own config, so tell the Project
      Manager you did.
  - glm-flash-low added to ~/.config/squadron/models.toml (inline [aliases] form); PM told.
- [ ] Live walkthrough steps 3, 5, 6, 10 (OpenRouter key; else stop and tell the Project
      Manager): low-effort alias review, JSON parity, pipeline parity, invalid value
  - [ ] `effort: low` in frontmatter; JSON matches frontmatter; `sq run review 931
        --model glm-flash-low` records the same fields as the CLI; invalid value logs the
        skip WARNING naming alias and file
  - [x] After step 10, set `glm-flash-low` back to `effort = "low"` and confirm
        `sq models list` loads it with no WARNING
    - Step 10 run (skip WARNING logged, then restored). Steps 3, 5, 6 not run: no OpenRouter key.
- [ ] Walkthrough steps 7–9 need Ollama, OpenAI, Gemini, and Codex access. Run whichever
      the environment has; list the rest by name in the DEVLOG entry as not run
  - [ ] Step 8 (mid-loop failure on `local`): failure artifact has `providerFailure: true`,
        `turns` ≥ 1, `durationSeconds`
    - local (Ollama llama3.2) run for step 7; openai, gemini, step 8, step 9 not run — listed in DEVLOG
  - [x] Step 8 sub-item (if broken out separately, check it)
- [x] Commit any fixups: `fix: <what>` (skip if none)

---

## Task 24 — Follow-up issues and #154 comment (Implementation Notes step 4)

- [x] File three GitHub issues with `gh issue create`, then link each number from the
      decision that defers it (D4, Out of scope, Risk Assessment)
  - [x] Codex effort (needs `codex_app_server` to verify `thread_start`'s reasoning parameter)
  - [x] SDK usage from `ResultMessage.usage` onto `core.usage.TokenUsage`
  - [x] Enable `sends_stream_usage` on gemini once a probe succeeds; include the probe
        command from Risk Assessment
- [x] Comment the D2 decision (aliases, not flags) on #154
- [x] Commit the design-doc links: `docs: link follow-up issues from slice 931 design`
  - Issues #171 (Codex effort), #172 (SDK usage), #173 (gemini probe); #154 comment posted; design links committed. Also filed #174 (pre-existing grep empty-pattern handling).

---

## Task 25 — Close out

- [x] Add a CHANGELOG entry (short user-facing bullets: alias `effort`, `read_file` `paths`,
      usage and duration in review artifacts)
- [x] Write the DEVLOG entry per `prompt.ai-project.system.md`, Session State Summary,
      including the baseline-versus-low-effort comparison and the `cachedTokens` answer
- [ ] Mark every task above `[x]` (dropped items too), set this file's `status: complete`,
      and set the slice design and slice plan entry to complete
- [ ] Merge into the target: re-read `cf config get git.integration_branch`,
      `git checkout <target>`, `git merge 931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage`;
      if either command fails, stop and ask the Project Manager
- [ ] Commit: `docs: close out slice 931`
  - Held: live OpenRouter runs (Tasks 11, 15, 23) are pending with the Project Manager; slice not marked complete or merged.
