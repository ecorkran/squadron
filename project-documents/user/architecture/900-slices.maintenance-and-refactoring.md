---
docType: slice-plan
parent: 900-arch.maintenance-and-refactoring.md
project: squadron
dateCreated: 20260325
dateUpdated: 20260731
status: in-progress
---

# Slice Plan: Maintenance and Refactoring

## Parent Document
`900-arch.maintenance-and-refactoring.md` — Architecture: Maintenance and Refactoring

## Guidelines
- Slices are added as maintenance needs are identified
- No strict implementation order — pick up based on priority
- Each slice should be small, focused, and independently deliverable

---

## Maintenance Slices

1. [x] **(901) Pipeline Code-Review Diff Injection and UNKNOWN-Fails-Closed**
Fixes [issue #11](https://github.com/ecorkran/squadron/issues/11): pipeline
code reviews silently produce UNKNOWN/no-findings because the diff is never
injected into the review prompt. Three coordinated changes:

1. Forward `slice` explicitly from phase / review step `expand()` into the
   review action config (deterministic key, not merged-params side channel).
2. Replace per-template `match` in `_resolve_slice_inputs` with a declarative
   template-input registry, so any template that declares it consumes a
   diff gets one resolved automatically.
3. Treat verdict `UNKNOWN` as `FAIL` for `on-fail` checkpoint triggers (fail
   closed) so dead reviewers and parser misses can't silently wave through.

**Status:** complete · **Risk:** Low · **Effort:** 2/5 · **Dependencies:** [149]

2. [x] **(902) Pipeline Verbosity Passthrough (`-v`/`-vv`) + Step-Type Registration Bootstrap**
Fixes [issue #9](https://github.com/ecorkran/squadron/issues/9): pipeline review
commands hard-code `-v`, and `/sq:run` swallows trailing flags into the target
string. Two coordinated changes:

1. Thread the existing `sq run -v/-vv` count into `PromptRenderer` and replace
   the hard-coded `cmd_parts.append("-v")` in `_render_review`
   ([prompt_renderer.py:174](src/squadron/pipeline/prompt_renderer.py#L174))
   with conditional emission based on runtime verbosity. Default 0 (no flag);
   `-v` and `-vv` opt in. This is a deliberate behavior change — current runs
   always emit `-v` to sub-reviews; new default is silent.
2. Update `/sq:run` slash command to peel trailing `-v`/`-vv`/`--verbose`
   tokens off `$ARGUMENTS` before splitting pipeline/target, and pass them
   through to `sq run`.

**Slice design:** `user/slices/902-slice.pipeline-verbosity-passthrough-v-vv.md`
Branch: `902-pipeline-verbosity-passthrough`, close issue on merge.

**Status:** complete · **Risk:** Low · **Effort:** 1/5 · **Dependencies:** none

**Follow-up (20260427):** extract `bootstrap_step_types()` into
[steps/__init__.py](src/squadron/pipeline/steps/__init__.py) to eliminate
triple-registration across executor / loader / prompt_renderer, and close the
prompt_renderer gap (missing `loop`/`collection`/`fan_out`) as a one-line
consequence. Tracked as T14–T17 in the 902 task file.

3. [x] **(904) Review-Finding Location Required**
Fixes [issue #10](https://github.com/ecorkran/squadron/issues/10): review
findings inconsistently cite a code location, and PASS findings almost never
do. Load-bearing for ensemble review (slices 182, 189) where merged-finding
deduplication keys on location. Four coordinated changes:

1. Update all four review-template prompts ([code.yaml](src/squadron/data/templates/code.yaml),
   [slice.yaml](src/squadron/data/templates/slice.yaml),
   [arch.yaml](src/squadron/data/templates/arch.yaml),
   [tasks.yaml](src/squadron/data/templates/tasks.yaml)) to require
   `location:` on every finding (PASS included), with `unverified` as
   the explicit "I don't know" token.
2. Soft-fail in [parsers.py](src/squadron/review/parsers.py): missing
   `location:` becomes `unverified` with a WARNING log; existing `-`,
   `global`, and empty values are normalized to `unverified`.
3. Diff-membership WARNING for code reviews (cited path must appear in
   the diff); WARNING-only.
4. Path-existence WARNING for all template types (cheap `Path.exists()`
   per finding); primary defense against hallucinated filenames in
   non-code reviews.

`task_ref:` field deferred to future slice (likely under 189 ensemble
review).

**Slice design:** `user/slices/904-slice.review-finding-location-required.md`
Branch: `904-review-finding-location-required`, close issue on merge.

**Status:** complete (20260427) · **Risk:** Low–Medium · **Effort:** 2.5/5 · **Dependencies:** none

4. [x] **(905) `sq doctor` Environment Diagnostic Command** — New `sq doctor` subcommand that inspects and reports on the runtime environment a user has assembled: which providers are usable (auth file present, API key set, profile reachable), which integrations are wired (Context Forge CLI on PATH, Claude Code session detected, Codex CLI binary present), and which configuration files are loaded. Output is a human-readable checklist with `OK` / `MISSING` / `WARN` per item and "fix it with: X" hints for each `MISSING` (install command, env var name, login command). Exit code 0 when nothing is broken, non-zero when at least one required item is missing for the user's apparent intent. Primary motivation: lower onboarding friction — new users assemble Squadron + Context Forge + per-provider auth from three package managers, and a single diagnostic command tells them what's wrong without digging through README sections. Secondary motivation: promotion-readiness — a discoverable "is everything OK?" command is table stakes for tools that span multiple installation paths. Scope: read-only inspection; does not write config, does not install anything. Out of scope: auto-remediation, interactive setup wizard. Risk: Low. Effort: 2/5. Dependencies: none.

5. [x] **(906) Quickstart and Onboarding Documentation** — New `docs/QUICKSTART.md` bridging "installed" to "verified and running": how to read `sq doctor`/`sq setup --check-only` output, the full six-profile provider matrix (`sdk`, `openai`, `openrouter`, `gemini`, `local`, `openai-oauth`), and pointers to README's existing review/pipeline walkthroughs rather than duplicating them. README gained two additive links to QUICKSTART; nothing existing was removed or reworded. Scope is docs-only; no code changes.

**Slice design:** `user/slices/906-slice.quickstart-and-onboarding-documentation.md` (rebuilt twice against live state during Phases 4–6 — see design's Overview and Verification Walkthrough for corrections found, including that `sq run` was already documented in README contrary to the original design's premise)

**Status:** complete (20260712) · **Risk:** Low · **Effort:** 1/5 · **Dependencies:** [905, 908]

6. [x] **(908) `sq setup` — One-Call Install Orchestrator** — Slice design: `user/slices/908-slice.sq-setup-one-call-install-orchestrator.md`. New `sq setup` command (and optional shell installer script) that walks a fresh user through the full install sequence in one invocation: checks for `cf` on PATH and prints the npm install command if missing, runs `sq install-commands`, prompts for provider choice and prints the relevant `export VAR=...` line, then runs `sq doctor` to confirm. Interactive by default; `--non-interactive` flag for scripted use (prints steps without prompting). No automatic execution of npm or system commands — prints and guides, does not run arbitrary installs. A companion `install.sh` (hosted alongside the PyPI package or in the repo) wraps `pipx install squadron-ai` + `npm i -g @manta-digital/context-forge` + `sq setup` into a single `curl | sh` for new users. Risk: Low. Effort: 2/5. Dependencies: [905 (sq doctor), 906 (QUICKSTART for links)].

**Status:** complete (20260520) · **Risk:** Low · **Effort:** 2/5 · **Dependencies:** [905, 906]

7. [x] **(909) Pipeline Phase-Step Correctness — Dispatch Post-Condition + Review Frontmatter Project + Review-Code Scope Guard**
Fixes [issue #15](https://github.com/ecorkran/squadron/issues/15), [issue #16](https://github.com/ecorkran/squadron/issues/16), and [issue #17](https://github.com/ecorkran/squadron/issues/17). Three independent pipeline/CLI correctness bugs, all surfaced during slice 303 planning, bundled into one maintenance slice because each is small and all three sit on the phase-step / review command correctness path.

**Part A — Dispatch artifact post-condition (#15, Medium).** A phase-step `dispatch` expected to *write an artifact* (design doc, task file) returns `success=True` whenever the agent's turn completes, with no check that the file was created. An agent that stops mid-task to ask a question — or never writes the file — is indistinguishable from success; the failure surfaces one step later at the review action with a misleading "prior step may not have created the expected file" message. Two coupled sub-problems: (1) dispatch has no artifact post-condition — the phase step knows the expected output (a `tasks` phase expects a task file) so the check likely belongs there, not in generic dispatch; (2) an unattended agent that ends its turn with a question has no answer path — it should route to a checkpoint/escalation rather than complete silently. Repro: `sq run p5a 303` (`run-20260707-p5a-73bbffc0.json`). (Ruled out CF review gates — squadron reads no `review_gate` setting.)

**Part B — Review frontmatter hardcodes `project: squadron` (#16, Low).** `format_review_markdown` (`persistence.py:119`) emits `project: squadron` as a string literal on every review file, in every project — a review run in context-forge is mislabeled `squadron`. `ProjectInfo` (`context_forge.py:52`) does not currently carry the project name; the fix adds it (from the `cf get --json` response already parsed in `get_project`), threads it via `SliceInfo`/`resolve_slice_info` (which already calls `get_project()`), and replaces the literal — falling back to a non-silent `unknown`, never `squadron`. Verify both write paths (pipeline `actions/review.py:201`, CLI `persistence.py:268`) per interface-parity.

**Part C — `sq review code` silently runs unscoped review when slice index missing/malformed (#17, Medium).** `review_code()` (`cli/commands/review.py:604-607`) declares `slice_number` as a fully optional Typer argument with no fallback validation; when it's omitted (or consumed by a misparsed flag), execution falls through with no `diff`/`files`/`slice_info` and no error. `_run_review_command`'s required-inputs check (`review.py:302-308`) is a no-op because the `code` template declares `required_inputs: []`. `code_review_prompt()` (`review/builders/code.py:40-44`) then substitutes an unconstrained "survey the project structure" instruction, and that prompt is sent to a real LLM, producing a confident, fully-formed review citing plausible-but-nonexistent files — a silent hallucinated-output failure, not a crash. Fix: require at least one of `slice_number` / `--diff` / `--files` before proceeding, mirroring the existing hard guards in `review_slice`/`review_tasks` (`review.py:408-410`, `551-553`). Repro: `sq review code -v --model glm51` run from context-forge with no slice index — produced a CONCERNS verdict citing files (`src/document-resolver.ts`, `src/git.ts`, etc.) that don't exist in that repo.

**Slice design:** `user/slices/909-slice.pipeline-phase-step-correctness.md`
**Task file:** `user/tasks/909-tasks.pipeline-phase-step-correctness.md`
**Status:** complete (20260710) · **Risk:** Medium (Part A) / Low (Part B) / Medium (Part C) · **Effort:** 4/5 · **Dependencies:** [149]

8. [ ] **(910) Loop Convergence Correctness — Findings Feedback + Multi-Review Gate + Iteration History + Dry-Run Expansion**
Fixes [issue #42](https://github.com/ecorkran/squadron/issues/42), [issue #43](https://github.com/ecorkran/squadron/issues/43), [issue #44](https://github.com/ecorkran/squadron/issues/44), and [issue #45](https://github.com/ecorkran/squadron/issues/45). Four defects on the multi-step `loop:` path, bundled because all four sit on the same construct and the first three share a single 60-line function (`_execute_loop_body`) and one test file. Together #42 and #43 make "the loop fixes the findings and re-reviews" false for the demo pipeline; #43 is why `p45b.yaml` currently uses two loops rather than one. Each part is small because the machinery already exists — this is wiring, not new architecture.

**Part A — Loop retries do not feed findings back into the re-run (#42, High).** `_execute_loop_body` (`pipeline/executor.py:1298-1321`) passes the *outer* `prior_outputs` into every `_execute_step_once` call (line 1308) and never updates it; `iteration_action_results` is reset at the top of each round (line 1299) and discarded. Iteration N+1 therefore re-runs a prompt identical to iteration N's — the loop re-rolls the same dice rather than converging. The consumer is already built and correct: `DispatchAction._resolve_prompt_from_prior_review` (`actions/dispatch.py:258`) walks `context.prior_outputs` in reverse for a `REVIEW` result, formats findings into a fix prompt, and already handles the empty-findings case — it is simply never fed. Fix: accumulate each inner step's results into a per-iteration `prior_outputs` copy and pass that down, mirroring the `dict(prior_outputs)` snapshot pattern `_execute_step_once` already uses (`executor.py:1030`). Effort 1/5 for the edit. **Verify during design:** how `step_outputs` interacts with `prior_outputs` inside `_execute_step_once` — the fix touches exactly that boundary and it is the one place a hidden complication could raise the estimate.

**Part B — `until:` reads only the last review in a multi-review body (#43, High).** `_last_with_verdict` (`executor.py:356-360`) returns the first verdict found walking backward, so in a body containing several reviews only the final one gates `until:`. A design review that FAILs while a tasks review PASSes exits the loop successfully. The code change is trivial; the *semantics* are the real work and need an explicit decision before implementation: all-verdicts-must-pass is the obvious reading, but `evaluate_condition` (`executor.py:334`) is shared with the single-step loop path where current behavior is correct, and any change alters behavior for existing multi-review pipelines. Sequence this part first — it determines the loop shape that Part A's tests assert against. Effort 1/5 to implement, 3/5 to decide.

**Part C — Iterations overwrite artifacts with no commit (#44, Medium).** Each iteration overwrites the previous iteration's artifact with no commit between rounds, so a converging loop leaves no way to diff round 2 against round 1 and no way to recover a better earlier attempt. Diagnostically coupled to Part A: with no per-round history there is no evidence available to *prove* the findings actually landed, and a byte-identical output — an empty commit — is precisely the Part A symptom. Land with Part A for that reason. A `commit` step type already exists, so the machinery is present; open questions to resolve in design are whether the loop inserts a commit automatically or it belongs in the body as an explicit step, commit-every-round vs. only-on-change, message format, and whether this is opt-in (`commit_each_iteration: true`) so existing loops do not begin writing history unexpectedly. This is the only part whose scope could grow. Effort 2/5.

**Part D — `sq run --dry-run` does not expand loop bodies (#45, Low).** A `loop:` step prints as a single opaque line (`loop-0 (loop)`), omitting the body's steps and the `max` / `until` / `on_exhaust` configuration — so the construct with the most surprising execution shape and the highest cost when wrong is the one `--dry-run` describes least. Parsing is already correct (`--validate` reports the pipeline valid), making this a display gap only. Independent of Parts A–C: shares no code, can land in any order. Effort 1/5.

**Status:** not started · **Risk:** Medium (Parts A/B) / Low (Parts C/D) · **Effort:** 3/5 · **Dependencies:** none

---

## Future Slices

Deferred work — not scheduled, kept for reference. Promote back into
Maintenance Slices when picked up.

1. [ ] **(907) Optional Dependency Split — `serve` and `codex` Extras** — Move `fastapi` and `uvicorn` out of mandatory dependencies into an optional `[serve]` extra (`pip install squadron-ai[serve]`), since they are only needed for `sq serve` (the daemon). Add a runtime check in `sq serve` that fails fast with an actionable install hint if the extras are absent. Similarly, define a `[codex]` extra noting the manual GitHub install requirement for the Codex SDK, and add a runtime check in codex-profile dispatch that produces a clear "run this to install" error rather than a raw `ImportError`. Scope: `pyproject.toml` restructure + two runtime guards. No behavior change for users who have the full install. Risk: Low. Effort: 1/5. Dependencies: none.

**Note (20260711) — premise needs re-verification before implementation.** Confirmed via `grep` that `fastapi`/`uvicorn` usage is genuinely confined to `src/squadron/server/` (no surprise indirect callers), and the codex SDK is already imported lazily/function-locally everywhere (`providers/auth.py:167`) — so codex already behaves the way this slice wants. But `serve` does not: [cli/app.py](src/squadron/cli/app.py) imports `squadron.cli.commands.serve` at module top level unconditionally (line ~24, `from squadron.cli.commands.serve import serve`), and [cli/commands/serve.py:12-14](src/squadron/cli/commands/serve.py#L12-L14) imports `squadron.server.daemon`/`.engine`/`.pid` at module scope — which themselves import `fastapi`/`uvicorn` at module scope. That means **every** `sq` invocation (`sq --help`, `sq run`, anything) currently imports fastapi/uvicorn into the process regardless of whether `serve` is ever used. Splitting the pyproject dependency alone, as scoped above, would make `sq` itself uninstallable/broken for any user without the `[serve]` extra — the import would need to become lazy (deferred inside the `serve` command function or behind a local import in `cli/app.py`'s registration) as a prerequisite, which is more than "two runtime guards." Re-scope and re-verify the actual blast radius (does this affect startup latency today? is lazy-loading `serve`'s registration in `cli/app.py` itself safe with Typer's command registration model?) before treating this as Effort 1/5.

**Slice design:** `user/slices/907-slice.optional-dependency-split-serve-and-codex-extras.md`
**Task file:** `user/tasks/907-tasks.optional-dependency-split-serve-and-codex-extras.md`
**Status:** deferred (20260712) · **Risk:** Low · **Effort:** 1/5 · **Dependencies:** none

