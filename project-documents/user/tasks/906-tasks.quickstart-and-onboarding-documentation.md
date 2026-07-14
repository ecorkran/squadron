---
docType: tasks
slice: quickstart-and-onboarding-documentation
project: squadron
lld: user/slices/906-slice.quickstart-and-onboarding-documentation.md
dependencies: [905, 908]
projectState: main @ 7763e76, squadron 0.6.2. Slice 909 merged. This slice's design has been rebuilt twice against live state — see design's Overview for what changed and why. Docs-only slice; no code changes.
dateCreated: 20260711
dateUpdated: 20260712
status: complete
---

## Context Summary

- New `docs/QUICKSTART.md`, plus a minimal additive pointer in `README.md`. No code changes.
- README's existing Install (`curl | sh`, pipx/uv) and Quickstart (SDK auth, review-a-design, review-tasks-then-code, Codex, model aliases) sections are current and accurate as of 20260711 — **do not rewrite or remove them**. Confirm this is still true at task-execution time; if README has changed since, re-derive the diff rather than trusting this note.
- The actual gap: no doc covers `sq doctor`, `sq setup`, the full provider matrix (README's Quickstart only documents SDK auth), or `sq run` (pipeline execution — not mentioned anywhere in README today).
- Provider profiles (verify live against `src/squadron/providers/profiles.py` `BUILT_IN_PROFILES` before writing — do not copy the table below without re-checking): `openai`, `openrouter`, `local`, `gemini`, `sdk`, `openai-oauth`. No "Anthropic API" profile exists.
- `sq doctor --help` and `sq setup --help` are the authoritative source for flags/behavior — read live output, don't restate from slice 905/908's own design docs (those may have drifted during their own Phase 6 implementation).
- Effort: 1/5. Risk: Low.

---

## Tasks

### Phase A — Verify current state before writing anything

- [x] **T1. Re-verify README's current structure and content**
  - Read the full current `README.md` top to bottom.
  - Confirm: Install section still has the `curl | sh` one-liner and pipx/uv blocks; Quickstart section still covers SDK auth + review-a-design + review-tasks-then-code; Codex and model-alias sections still present.
  - If any of this has changed since 20260711, note the actual current state — the slice design's "Explicitly Excluded" list assumes this content is stable; if it is not, stop and flag to the Project Manager before proceeding, since the design's scope boundary depends on it.
  - Success: a short written note (can be a scratch file, not committed) confirming README's current section list matches what the slice design assumes, or documenting what's different.

- [x] **T2. Capture live command output for `sq doctor` and `sq setup`**
  - Run `sq doctor --help`, `sq doctor -v`, `sq setup --help`, `sq setup --check-only` (or `--non-interactive` in a scratch/throwaway env if a full fresh-machine simulation is wanted) and record actual output.
  - Run `sq run --help` to confirm current flags (`--model`, `--param`, `--from`, `--resume`, `--dry-run`, `--validate`, `--list`, `--status`, etc.) and available pipelines (`sq run --list`).
  - Success: have real, current CLI output in hand to write QUICKSTART from — not reconstructed from memory or from slice 905/908's design docs.

- [x] **T3. Verify provider profile table**
  - Read `src/squadron/providers/profiles.py` `BUILT_IN_PROFILES` directly.
  - Confirm the six profiles (`openai`, `openrouter`, `local`, `gemini`, `sdk`, `openai-oauth`) and their `api_key_env`/`auth_type` fields match the design's table.
  - Success: table in hand, confirmed against source, ready to drop into QUICKSTART without further verification needed.

### Phase B — Write `docs/QUICKSTART.md`

- [x] **T4. Create `docs/QUICKSTART.md` — Prerequisites and Install sections**
  - New file. Prerequisites: Python 3.12+, `git`, a supported OS (note Windows limitation from install.sh scope).
  - Install section: link to README's Install section as source of truth rather than re-authoring the `curl | sh` / pipx / uv blocks verbatim (avoids future drift between two copies of the same instructions). A single fenced example of the one-liner is fine for scannability; the authoritative version lives in README.
  - Success: section reads correctly, links resolve, no verbatim duplication of README's install commands beyond one illustrative example.

- [x] **T5. Write "Verify your install" section (`sq doctor` / `sq setup --check-only`)**
  - Explain what `sq doctor` checks (Install / Integrations / Providers / Configuration sections, per T2's live output) and what OK/MISSING/WARN mean.
  - Explain `sq setup --check-only` as the equivalent view rendered through setup's step model, and when to reach for `sq setup` (interactive) vs `sq doctor` (quick check).
  - Use real output captured in T2, not fabricated example output.
  - Success: a reader can run either command and correctly interpret every row they see, including what to do about a MISSING/WARN row.

- [x] **T6. Write "Configure a provider" section with provider matrix table**
  - Use the table verified in T3. Six rows: OpenAI, OpenRouter, Local, Gemini, Claude Code SDK, OpenAI Codex (openai-oauth).
  - One short subsection per provider: what env var (if any) to set, or what command to run (`codex auth login`), or confirmation that no setup is needed (`sdk`, `local`).
  - Include the Agent SDK credit note from the design (reworded to reflect that the June 15, 2026 cutover has already passed — do not use future-tense "before June 15" framing).
  - Success: every one of the six profiles has an actionable auth subsection; table matches T3's verified source data exactly.

- [x] **T7. Write "Your first review" section**
  - Brief — one or two commands, linking to README's existing Quickstart section for the full walkthrough rather than restating it. This section's job is continuity ("you've verified your install — now try a review") not duplication.
  - Success: section is a bridge, not a copy; no more than a few lines plus a link.

- [x] **T8. Write "Your first pipeline run" section (bridge, not net-new — corrected 20260712)**
  - T1 re-verification found README already has a `## Pipelines (\`sq run\`)` section (line ~338) covering `sq run slice N`, `--list`, `--prompt-only`, and a link to `docs/PIPELINES.md`. The design's claim that `sq run` is undocumented was wrong.
  - Write this as a short bridge/pointer, matching T7's treatment of "Your first review": one or two lines plus a link to README's Pipelines section and `docs/PIPELINES.md`, not a full walkthrough.
  - Success: a reader who has never run `sq run` can complete one pipeline execution (or at minimum a `--dry-run`) by following this section alone.

- [x] **T9. Write "Troubleshooting" and "Windows" sections**
  - Troubleshooting: pointer to `sq doctor`, `sq setup --check-only`, `sq auth status` — no new content, just a triage pointer.
  - Windows: note that `install.sh` is macOS/Linux-only (per slice 908's explicit scope) and that Windows users should follow the manual/global-install path from README's Install section.
  - Success: both sections present, short, no unverified claims about Windows behavior beyond what 908's design already states.

### Phase C — README pointer and full-document pass

- [x] **T10. Add a single additive pointer in `README.md` to `docs/QUICKSTART.md`**
  - Exact placement and wording decided against the live file (from T1's re-verification) — a natural spot is near the top of Install or Quickstart, one sentence plus a link.
  - Do not remove, reorder, or reword any existing README content. This is a pure addition.
  - Success: `git diff README.md` shows only an added line/block, nothing removed or restructured.

- [x] **T11. Full top-to-bottom read of `docs/QUICKSTART.md`**
  - Read the completed file as a new user would, section by section, confirming each step is complete, actionable, and internally consistent (no forward references to sections that don't exist, no commands that don't match T2/T3's verified output).
  - Success: no gaps, no stale claims, no unverified command output.

### Phase D — Final gate

- [x] **T12. Run the verification walkthrough from the slice design**
  - Follow "Your first pipeline run" against a real `sq run` invocation and confirm it works as described.
  - Diff `README.md` against its pre-slice version — confirm additive-only.
  - Success: walkthrough passes; README diff is additive-only.

- [x] **T13. Run full validation gate**
  - `uv run ruff check && uv run ruff format --check && uv run pyright` — zero errors (docs-only change, but confirms no incidental Python touch).
  - `uv run pytest -q` — full suite green, no regressions.
  - Success: all three commands clean.

- [x] **T14. Mark slice complete and write DEVLOG entry**
  - Update this task file's frontmatter `status: complete`.
  - Update slice design frontmatter `status: complete`, `dateUpdated` to completion date.
  - Update the slice-plan entry for 906 in `user/architecture/900-slices.maintenance-and-refactoring.md` (checkbox + status line), per the pattern used for 905/908/909.
  - Write a DEVLOG entry per `prompt.ai-project.system.md`'s Session State Summary guidance.
  - Success: all three documents reflect completion; DEVLOG entry present.

## Notes for the implementer

- This design has already been corrected twice for drift between what was assumed and what's actually true (see the slice design's Overview). Do not treat any command output, table, or README-structure claim in the design or in this task file as ground truth — re-verify against live `--help` output, live source, and the live README before writing prose that depends on it. Phase A above exists specifically to force this re-verification before content is written, not after.
- `codeReview`/`review` is set to `none` in the slice design frontmatter (via `cf check --set-review-none 906`) — this is a no-code, docs-only slice intentionally exempted from the code-review gate. Do not re-add a review step at Phase 6 close-out.
