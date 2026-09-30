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

> Part 2 of 2. Parts C and B (Tasks 1–15) are in `931-tasks.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage-1.md`. Task numbers continue across files; Tasks 11 and 15 (baseline and batched-read runs) are referenced below.

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
- [ ] `review/models.py`: add `ReviewResult.effort` (rendering follows in Task 19B)
- [ ] Tests
  - [ ] `test_review_client.py`: recorded only when `applies_effort` is True
  - [ ] `test_cli_review.py`: alias effort reaches the client; CLI and pipeline produce the
        same effort field for the same alias (interface parity)
  - [ ] Success: all pass
- [ ] Format, lint, typecheck, commit: `feat: carry alias effort to the review client and result`

---

## Task 19B — Render effort (D10)

- [ ] `review/persistence.py`, `review/models.py`: frontmatter `effort` only when sent;
      digest `Effort: <level>` or `backend default`; `to_dict()` `effort` always present,
      null when unset
- [ ] Tests in `test_persistence.py` / `test_models.py`: frontmatter, digest, JSON agree;
      absent key when unset
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
  - [ ] D12 "backend rejects `reasoning_effort`" row: a stubbed 400 on a request carrying
        `reasoning_effort` surfaces as `ProviderAPIError` (extend the existing 4xx test
        from Task 7 if it fits)
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
- [ ] Walkthrough step 1 first, since steps 3, 5, 6, 8–10 depend on it: confirm
      `~/.config/squadron/models.toml` defines `glm-flash-low` (profile `openrouter`, same
      model id as built-in `glm-flash`, `effort = "low"`), and that `sq models list` shows it.
      If the file lacks it, add it there; this is the user's own config, so tell the Project
      Manager you did.
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
