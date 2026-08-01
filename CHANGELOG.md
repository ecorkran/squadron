---
docType: changelog
scope: project-wide
---

# Changelog

All notable changes to Squadron will be documented in this file.  This file should contain concise entries from user point of view and should answer the following questions:
* What can I do now that I couldn't do before?
* What specific bugs, if any, are fixed?
* Were any features removed?

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **A `loop:` step can now commit every iteration.** Set `commit_each_iteration: true` and squadron commits after each round, with a message naming the iteration (`chore: loop-{name} (iteration N)`) — useful for dispatch-then-review loops that previously left zero commit history. A phase-shaped loop, which already commits automatically, rejects the option at validation time rather than committing twice.
- **Artifacts and review files a loop iteration produces now carry a `revision_number:`.** The design/tasks file a round writes, and the review file squadron authors for it, are stamped with a monotonic revision count so you can tell which round you're looking at. Absent means never stamped by squadron — it is not round 1.

### Fixed
- **`loop:` steps now actually converge.** A dispatch-then-review loop was re-sending the exact same prompt on every retry instead of feeding back what the prior review found — so a loop could run its full `max` iterations without ever seeing what needed fixing. Retries now include the previous iteration's findings.
- **A loop body with two reviews could silently report success while one of them failed.** `sq run --validate`/`--dry-run` now rejects a `loop:` body containing more than one review or gate when `until:` is set, with a message naming the conflicting steps and suggesting the fix (split into sequential loops).
- **A loop iteration that changed nothing left no trace.** Committing inside a loop now logs a warning when the working tree is clean after an iteration — previously this was silent, indistinguishable from a real improvement.

### Changed
- **`sq run --dry-run` now shows what's inside a `loop:` step** — its `max`, `until`, `on_exhaust`, `commit_each_iteration` when set, and each step in its body — instead of a single opaque `loop-N (loop)` line.

## [0.8.2] - 20260729

### Changed
- **`sq models list` now groups aliases by profile** instead of sorting them flat A–Z, so related models sit together — all the Claude entries in one block, the Gemini variants adjacent, and `codex`/`codex-agent`/`codex-spark` no longer split apart by their differing profiles. Order is `sdk`, `openai`, `openai-oauth`, `gemini`, `openrouter`, then anything else. Pass `--sort alias` for the previous flat ordering.

## [0.8.1] - 20260728

### Fixed
- **The install instructions pointed at a package that doesn't exist.** `sq doctor`, `sq setup`, and `scripts/install.sh` all told you to run `npm i -g @manta-digital/context-forge`, which 404s. The correct package is **`@context-forge/cli`**. If you hit this, that's why.
- **`sq doctor` hid the fix.** A warning-level row printed the problem but suppressed its `fix:` line unless you passed `--verbose` — and a missing Context Forge was exactly such a row, so the one check most likely to fail was the one whose remedy you couldn't see.
- **Every "learn more" link in `sq setup` was broken.** All seven pointed at `docs/QUICKSTART.md` headings that never existed. They now resolve, and a test keeps them honest.

### Changed
- **`sq setup` now installs things instead of just describing them.** Press Enter and it runs the install: Squadron's `/sq:` slash commands, Context Forge itself via npm, and Context Forge's `/cf:` slash commands. Failures are specific — a missing `npm` says so by name, and npm's own error is passed through rather than swallowed. `--non-interactive` still only prints the commands, so scripts are unaffected.
- **Context Forge is now reported as required, not optional.** Squadron builds every dispatch prompt through `cf`, so an install without it is broken rather than merely reduced. `sq doctor` marks it missing (not a warning) and exits accordingly.
- **`scripts/install.sh` also installs the `/cf:` commands** — installing the `cf` binary alone left you without them.
- Install docs in README and QUICKSTART now say plainly that `pipx`/`uv` install Squadron *only*, that `sq setup` finishes the job, and that `cf init` is the per-project step that follows.

## [0.8.0] - 20260728

### Added
- **`sq metrology preempt generate` and `sq metrology audit delta`** — turn a measured audit baseline into guidance, and check whether anything actually changed. `preempt generate` writes a short **pre-emption fragment** naming the issue classes your project's audit keeps finding; a pipeline opts into prepending it to a dispatch prompt with `pre_emption_fragment: <path>` on a `dispatch`, `design`, `tasks`, or `implement` step. Pipelines that don't set it are completely unaffected. `--check` reports whether the written fragment still matches the current baseline (exit 1 when stale or absent, so CI can gate on it) — regeneration is always something you ask for, never automatic. `audit delta` runs one fresh audit and compares it to the baseline **relative to the measured noise floor**: a change smaller than the floor's observed spread is reported as indistinguishable from noise rather than as an improvement, and a category with no measured floor is reported as **"no floor — delta not interpretable"** instead of being treated as significant. Every delta report carries a fixed observational disclaimer: it never claims a cause.
- **`metrology.preemption_fragment_dir`** — where `preempt generate` writes fragment files (default `~/.config/squadron/metrology/preemption`).
- **`sq metrology audit run|variance` and `sq metrology report baseline`** — measure how much a tech-debt audit's findings vary when nothing about the code has changed. `audit run` audits a project once and persists the findings; `audit variance` runs the same audit N times at one pinned commit and reduces them to a **noise floor** — the range and spread you should expect from the instrument itself. `report baseline` shows per-project, per-category counts with that floor attached, and says **"no floor measured"** rather than borrowing another project's number. Audits taken under a different prompt or model are never pooled: they are reported as separate instruments.
- **`metrology.audit_model`** — pin the model used for audits. Left unset, the CLI picks its own (measured as a 1M-context Opus — the most expensive option available, chosen silently and liable to change when the CLI updates). Pinning matters for cost and for comparability: different models return systematically different finding counts, so an unpinned model means a floor measured today may not be comparable to one measured later. All metrology config keys are now documented in `docs/COMMANDS.md`.
- **`sq metrology recommend|graduate|offers`** — turns your captured calibration evidence into an advisory recommendation for a judge's pass/concerns thresholds. `recommend` shows, per artifact level and judge configuration, whether the evidence supports graduating the judge toward auto-gate, tightening it, holding, or needs more evidence — always stating the sample count and the floor applied, never a blank. Nothing is ever mutated automatically: threshold changes are yours to make by hand. Once you've edited a threshold based on a `GRADUATE` recommendation, `sq metrology graduate` records that decision (refusing if the evidence doesn't actually support it), and `sq metrology offers` keeps listing spot-check targets afterward so a graduated judge doesn't stop accumulating evidence.
- **`sq metrology report agreement|dispersion|trend`** — the headline analysis over your captured calibration samples. `agreement` shows how often the judge's verdict matched your blind human verdict, broken out per artifact level and judge configuration (never a single blended number), each figure carrying its sample size and a low-evidence flag. `dispersion` shows how much distinct judge configurations disagree when grading the same artifact. `trend` buckets both over time (`--bucket day|week|month`). All three are read-only and support `--json` for scripting.
- **`sq metrology sample` / `sq metrology list`** — capture a blind human calibration verdict against a persisted judge result and inspect the stored samples. `sample <target>` shows the reviewed artifact and its ground truth (never the judge's score/verdict/findings) before you commit a verdict, then records it against that specific result. Samples live in a user-level store (`~/.config/squadron/metrology/`) that aggregates across every project you run — `list` returns samples from all of them. Skipping is free and never blocks; a per-project budget caps how many samples are recorded.
- **`judge-cycle`** — a new built-in reference pipeline for the judge-gated review→fix→re-review cycle: a bounded `loop` that fixes an artifact, re-judges it, auto-advances once the judge's score clears its threshold, and escalates to a human (`PAUSED`, with the last score and findings visible) if it never does. See the new "Judge-Gated Cycles" section in `docs/PIPELINES.md` for the convention, including the advisory-only (always-escalate) mode for weak-ground-truth judges.
- **`gate` step** — compose a judge verdict and a standard review verdict into a single checkpoint gate. Reduces both by most-severe-wins (a broken or `UNKNOWN` leg always dominates a passing one — never a silent pass) and gates on the combined result, with both raw verdicts preserved for auditing. See the new "Composing a judge and a review at one gate" section in `docs/PIPELINES.md`, and the `compose-gate-example` built-in pipeline for the reference shape.
- **New model aliases** — Claude Fable 5, Opus 5, Sonnet 5, Kimi K2.7, GLM 5.2, MiniMax M3, and Trinity Large Thinking, plus refreshed pricing across the existing OpenRouter and Gemini entries. Run `sq models list` to see what's available. Note that `opus` and `sonnet` now point at Opus 5 and Sonnet 5; the previous generation is still reachable as `opus4` and `sonnet4`.
- **Long-running audits now report liveness.** `sq metrology audit run|variance` prints progress while a run is in flight, so a 5-20 minute audit no longer looks like a hang.

### Fixed
- **Rate limits are now absorbed rather than hammered through.** A throttled provider triggers exponential backoff (capped by `metrology.audit_rate_limit_cap_s`, retried up to `metrology.audit_rate_limit_retries` times) instead of retrying immediately, and a campaign that hits a hard limit stops cleanly with completed runs persisted rather than burning through every remaining project on identical failures. Runs also report what throttling they absorbed, so a run that finished after ten pauses is distinguishable from one that finished clean. Usage-status notices are no longer misread as throttling, and the retry budget resets once work starts flowing again.
- SDK-based agents no longer crash on message types the installed SDK version cannot parse — unknown messages are skipped with a warning instead of aborting the run.
- `sq _summary-instructions` (used by `/sq:summary`) no longer leaves `{keep_section}`/`{summarize_section}` as literal unresolved text in rendered output.
- `sq review code <slice>` no longer silently guesses a diff range from a commit-message text search when no local branch or merge commit can be found for the slice — a wrong guess could pull an unrelated, already-merged prior slice's code into the review. It now fails with a clear error and asks you to pass `--diff` explicitly.
- `sq metrology sample|recommend|graduate|offers` now correctly resolve judge templates. Previously every judge result looked "unversioned" to these commands (templates were never loaded), which silently made a judge's calibration ineligible for graduation no matter how much matching evidence you'd captured.
- `sq metrology graduate` no longer risks graduating stale evidence when a judge template has been edited since some of its samples were captured — it now always acts on the template as currently configured, refusing with a clear message if no evidence exists yet for the current version.
- Reviews now fail immediately with a clear error when the `input` or `against` document doesn't exist on disk (stale path, typo, or an artifact a prior step never wrote), instead of silently proceeding without that document and letting the model produce a fabricated verdict. Applies to `sq review slice|tasks|arch` and pipeline review steps; a warning is also logged if a missing document is ever skipped at the prompt-injection layer. Closes [#18](https://github.com/ecorkran/squadron/issues/18).
- A pipeline `review` step with no model set anywhere now falls back to the review template's own default model instead of failing outright — matching how `sq review` already behaves.
- A judge review's saved file now shows its real PASS/CONCERNS/FAIL verdict (derived from the score) instead of always showing `UNKNOWN` — judge templates intentionally don't state a verdict in their own output, so the file previously looked unresolved even when the score clearly passed or failed.
- Review file-injection size limits (per-file and total) are now configurable via `review.max_file_size_bytes` and `review.max_total_injection_bytes` (`sq config set ...`), instead of fixed at 100KB/500KB regardless of the model's actual context window. Closes [#19](https://github.com/ecorkran/squadron/issues/19).
- A review whose model response doesn't follow the required `### [SEVERITY] Title` finding format no longer fabricates findings out of the model's own prose narration. Previously, a verdict of CONCERNS/FAIL with no parseable findings would grab arbitrary sentence fragments and present them as structured findings with invented severities — plausible-looking but meaningless. The findings list is now left empty and a warning is logged instead; the model's raw response remains visible in the saved review file either way. Closes [#20](https://github.com/ecorkran/squadron/issues/20).
- SDK-based reviews and one-shot summaries no longer mix tool-call narration ("Using tool: Bash", command output) into their saved text with no separator between messages. Previously, a review or summary that read files or ran commands mid-turn could end up with its actual prose mashed together with tool-use markers into one unreadable, unparseable run-on line — which could also corrupt the very `### [SEVERITY]` structure a review's findings are parsed from. Tool-call messages are now excluded entirely, and remaining content is joined with newlines. Closes [#22](https://github.com/ecorkran/squadron/issues/22).
- The `judge-cycle` pipeline's fix step now actually sees what the prior judge review flagged, instead of repeating the same generic instruction every iteration — it was converging by luck (or not at all) rather than by acting on feedback.
- A pipeline `review` step relying solely on a review template's own default model (no CLI/action/step/pipeline/config override) no longer fails with a false "no model at any cascade level" error before the pipeline even starts.
- A malformed judge threshold override (e.g. a non-numeric `pass_floor`) no longer discards an already-completed review with no file written at all — it now degrades to an `UNKNOWN` verdict (logged as a warning) and the review is still saved.
- A judge review persisted as JSON (`as_json=True`) now shows its real threshold-derived verdict instead of always showing `UNKNOWN`, matching the markdown output for the same run.
- `sq review code` no longer sends its template-specific rules (`.claude/rules/review-code.md`) to the model twice in the system prompt — it was inflating prompt size on every run with a configured rules directory. Closes [#24](https://github.com/ecorkran/squadron/issues/24).
- Pipeline dispatch steps (design/tasks/implement, via `SDKExecutionSession`) no longer mix tool-call narration ("Using tool: Bash", command output) into the response text passed to later pipeline steps, with no separator between messages — the same class of corruption fixed for reviews and summaries in #22. Closes [#23](https://github.com/ecorkran/squadron/issues/23).

## [0.7.0] - 20260714

### Added
- **`docs/QUICKSTART.md`** — new guide covering how to verify your install (`sq doctor`, `sq setup --check-only`), the full six-profile provider matrix, and where to go for your first review or pipeline run. Linked from the README.
- Review templates can now be marked as **judges** via a `judge:` block (with optional `pass_floor`/`concerns_floor`). For judge templates, the verdict is always derived from the numeric score by threshold — never the model's own stated verdict — and every result now carries a `provenance` field (`"judge"` or `"review"`) so consumers can tell how a verdict was produced. A score that's missing or out of range yields `UNKNOWN` (never a silent pass), each logged as a warning. Thresholds can be overridden per pipeline step via a `judge:` key.
- **`judge.tasks-vs-slice`** and **`judge.slice-vs-arch`** — the first two judge templates, scoring a task breakdown against its parent slice design and a slice design against its parent architecture, respectively. Each produces a numeric score with a per-criterion rationale and findings instead of a verdict. Usable via a pipeline `review` step (`template: judge.tasks-vs-slice`) or directly through the review API; not yet exposed as an `sq review` CLI subcommand.

### Fixed
- A pipeline's `design`/`tasks` phase step no longer reports success when the dispatched agent ends its turn without writing the expected design or task file. The step now fails immediately at the dispatch point (not one step later at review, with a misleading error), so an unattended run stops observably instead of silently limping forward.
- `sq review code` run without a slice number, `--diff`, or `--files` (or with a non-numeric slice argument) now errors out instead of silently running an unscoped review — which could produce a confident, fully-fabricated result citing files that don't exist in your project.
- Saved review files now record the actual project name in their `project:` frontmatter field, instead of always writing `squadron` regardless of which project the review ran in.

## [0.6.2] - 20260628

### Added
- **`sq skills uninstall <pack>`** — remove a pack's installed files using an install receipt written at install time. Removes only the files `install` wrote; unrelated files you added to the pack directory are left untouched. Reports a clear error (no traceback) if the pack is not installed.
- **`sq doctor` Skill Packs section** — `sq doctor` now lists every pack in the manifest with installed / not-installed status, and shows `fix: sq skills install <pack>` for any pack not yet installed. Included in `sq doctor --json` output.
- **`sq skills install <pack>`** — install a skill pack from a `skills.toml` manifest. Supports local paths, bundled packs, and GitHub sources (`github:<org>/<repo>`). Copies `.md` files to `~/.claude/commands/<prefix>/` or the dispatch file location. Idempotent.
- **`sq skills list`** — show all packs in the active manifest with their source, surface type, and install status (Installed / Not installed). The `analysis` pack is now visible out of the box (no `skills.toml` required).
- **`skills.toml` manifest format** — declare skill packs at `~/.config/squadron/skills.toml` (user-level) and/or `<project>/.squadron/skills.toml` (project-level). Project-level entries win on name collision.
- **`analysis` skill pack** — bundled with squadron. Run `sq skills install analysis` to install the `tech-debt-audit` skill to `~/.claude/commands/analysis/`. Works offline with no GitHub token.
- **`/sq:analysis` dispatcher** — routes `/sq:analysis tech-debt-audit` to the installed tech-debt-audit skill. Install via `sq install-commands`.
- **Shipped default manifest** — squadron now ships a built-in `skills.toml` that pre-declares the `analysis` pack, so `sq skills list` shows available packs even before the user creates their own manifest.
- Review results can now carry an optional numeric **score** (0–100) and a per-criterion **criteria** breakdown alongside the existing PASS/CONCERNS/FAIL verdict. When a review response includes a top-level `score:` line, the score is parsed and surfaced as a first-class field: written to the review file's frontmatter as a top-level `score:` (greppable without reading the body), included in JSON output, and recorded on the run state. Score-less reviews are unchanged. (Foundation for upcoming LLM-as-judge scoring; no review template emits a score yet.)

## [0.6.1] - 20260604

### Added
- `sq setup`: new command that walks a fresh user through the full Squadron install sequence in one invocation. Interactive by default (pauses at each step); use `--non-interactive` / `-y` to emit all steps without prompting, or `--check-only` for a fast one-line summary. Supports `--profile <name>` to scope provider steps to a single profile.
- `scripts/install.sh`: bootstrap script for new users with no Squadron installed. Detects `uv`/`pipx` and `npm`, installs `squadron-ai` and `@manta-digital/context-forge`, then hands off to `sq setup`. Fetch with `curl -sSL https://raw.githubusercontent.com/ecorkran/squadron/main/scripts/install.sh | sh`.
- `sq doctor`: new command that inspects the runtime environment and reports configured providers, integrations, and config files. Exits 1 when a required item is missing. Use `--json` for machine-readable output and `-v` to show optional items.

### Fixed
- `sq setup` / `sq doctor`: the Claude Code check now reports whether the Claude Code CLI is installed (the dependency the `sdk` provider authenticates through) instead of whether you happen to be running inside a Claude Code session. Installing from a normal terminal no longer shows a misleading warning or pauses on a re-detect prompt; the step is informational and never blocks.

## [0.6.0] - 20260512

### Added
- **Container step classification**: `sq run --explain` now reports classification for `each`, `loop`, and `fan_out` steps by descending into their inner steps. Container steps appear as a dim header row with inner-step rows indented with `↳`. `fan_out` pipelines (pool-ref or literal alias list) produce correct `sdk_required` / `non_sdk` / `pool_uncertain` results in `--explain` output and for session-construction decisions.
- **`sq run --explain <pipeline>`**: Print a per-step classification table and pipeline shape summary without executing. Shows each step's resolved alias, model ID, profile, classification (`sdk_required` / `non_sdk` / `pool_uncertain`), and rationale. Accepts `--model`, `--param`, and `--strict` to show what classification a real run would use with those overrides.
- **Lazy pool-auth default**: `sq run` no longer connects a Claude session at startup for pool-uncertain pipelines. The session is connected on-demand the first time a step actually resolves to an SDK model. Claude auth is skipped entirely for runs where pool selection never picks a Claude model.
- **`--strict` flag** (`sq run --strict`): Opt in to the pre-245 eager-connect behaviour for pool-uncertain pipelines. Also configurable per-pipeline via `auth_policy: strict` in the pipeline YAML.
- **`auth_policy` YAML field**: Pipelines can set `auth_policy: lazy` (explicit default) or `auth_policy: strict` in their YAML header. CLI `--strict` overrides the YAML setting.
- Pipeline classification gates SDK session construction — non-Claude pipelines no longer require Claude auth. `sq run my-non-claude-pipeline` completes without spawning a Claude CLI process.
- Pipeline classification pre-scan: Squadron now classifies each model-dispatching step (`dispatch`, `review`, `summary`, `compact`) as SDK-required, non-SDK, or pool-uncertain before the pipeline runs.
- Non-SDK models (e.g. `minimax`, `gemini-flash`) now work correctly in prompt-only/IDE mode (`/sq:run`). The dispatch renderer emits a `sq _dispatch-run` command for non-SDK profiles; the IDE harness runs it via Bash instead of silently using the calling session.
- New hidden subcommand `sq _dispatch-run` for pipeline-internal use: accepts `--prompt-file`, `--model`, `--profile`, `--param` flags and invokes a one-shot non-SDK dispatch.

### Fixed
- `sq run … --param model=<non-sdk>` (pure-CLI mode) now correctly dispatches to the non-SDK provider instead of silently routing the prompt through the persistent Claude session. Mixed pipelines (some steps Claude, some non-SDK) route per-step correctly; `metadata.profile` in run state now accurately reflects which path executed.
- SDK synthetic errors (`ResultMessage.is_error=True`) are now caught and surfaced as `ProviderAPIError` before any response text is returned, preventing silent writes of error text into design artifacts.

## [0.5.1] - 20260427

### Added
- Multi-step loop bodies: `loop:` can now wrap a `steps:` sequence (e.g. `dispatch:` then `review:`) and re-run the whole block per iteration, with the same `until` / `on_exhaust` / `max` semantics as the single-step form.
- Loop iteration count is now reported on completed step state in run JSON (you can see how many times the loop actually ran).
- Every review finding (PASS included) now carries a `location:` field, so review output is consistent and findings can be deduplicated cleanly across multiple reviewers.

### Changed
- Pipeline reviews are silent by default. Pass `-v` or `-vv` to `sq run` (or `/sq:run`) to opt in to verbose review output; previously `-v` was hard-coded.
- `review.yaml` no longer takes a `template` param — the pipeline is purpose-built for code reviews. **Breaking** for callers that passed `--param template=...`.

### Fixed
- Top-level `loop:` steps now actually run instead of failing validation with `Unknown step type loop`.
- `loop`, `each`, and `fan_out` step types now load correctly in prompt-only mode (previously raised `KeyError`).
- Checkpoint pause now shows the review's findings instead of "No structured findings". Closes [#12](https://github.com/ecorkran/squadron/issues/12).
- Pipeline code reviews no longer silently produce `UNKNOWN` with no findings; the diff is now assembled and injected automatically when the review step has a `slice:` set.
- Checkpoints now stop on `UNKNOWN` verdicts (treated like `FAIL` / `CONCERNS`); a missing review still passes through unchanged.
- Review findings missing or with placeholder locations (`-`, `global`, `n/a`, `none`, empty) are normalized to the explicit `unverified` token, and a WARNING is logged. Resolves [#10](https://github.com/ecorkran/squadron/issues/10).
- Review parser warns on suspect finding locations: a WARNING fires when a cited path isn't in the diff (code reviews) or doesn't exist on disk (any template). Both are observational; findings are never modified.

## [0.5.0] - 20260424

### Added
- `compact:` step now works in all execution environments. In `sq run` (true CLI), the existing session-rotate flow is preserved. In IDE/Claude Code CLI (prompt-only), `/compact` is dispatched automatically via `claude_agent_sdk.query()` and the pipeline awaits `compact_boundary` before continuing.
- `summary: restore: true` mode: re-inject a previously captured summary into the current session. Use after `compact:` to preserve a summary artifact across context reduction.
- `CompactAction` registered in the action registry as `ActionType.COMPACT`.

### Changed
- `compact:` step no longer implicitly captures a summary artifact. Pipelines that relied on `compact:` producing a summary must add an explicit `summary: emit: [file]` step before `compact:`. See PIPELINES.md for the recommended compose pattern.
- `compact:` YAML fields: `template`, `keep`, and `summarize` are no longer meaningful (silently ignored). Use `model` and `instructions` instead.

## [0.4.2] - 20260417

### Added
- `fan_out` step type: run the same inner step concurrently against N models and reduce results via a configurable `fan_in` reducer (`collect` or `first_pass`).
- Pool-based fan-out: set `models: pool:<name>` with `n: N` to draw N models from a named pool and run them in parallel.
- `FanInReducer` protocol for registering custom reducers at import time (used by slice 189 for ensemble review).

### Fixed
- `fan_out` steps now execute correctly in SDK pipeline runs (the session guard was over-broad; branches always run without a session).
- OpenRouter and other non-SDK models in `fan_out` now route to the correct provider; previously the resolved profile was dropped on a second alias lookup, causing all branches to fall back to the Claude SDK provider.
- Concurrent `fan_out` branches with the same inner step name no longer collide in the agent registry; each branch gets a unique agent name suffixed with its branch index.
- `sdk_query` (one-shot agent dispatch) now retries on `rate_limit_event` instead of failing; mirrors the existing retry logic in client/session mode.

## [0.4.1] - 20260415

### Added
- `sq review code <N>` now resolves the correct diff for slices merged directly to main (no surviving branch) by grepping commit messages for the slice number.
- `sq review code --fan N` flag accepted as a placeholder for future fan-out support (slice 182); currently warns and proceeds normally.

### Fixed
- `sq review code` was running `git diff` from the config `cwd` (e.g. `project-documents/user`) instead of the git root, causing empty diffs and UNKNOWN verdicts.
- Language-specific rules files (e.g. `python.md`) were not injected because quoted paths in block-list YAML frontmatter (`"**/*.py"`) were not stripped of quotes during parsing.
- `CLAUDE.md` is now injected into review prompts for API-only providers (e.g. OpenRouter) that cannot read files directly; headings are demoted to match the rules hierarchy.

## [0.4.0] - 20260414

### Added
- **Pool-based model selection.** `pool:` is now a first-class model specifier at every
  cascade level (`--model pool:<name>`, pipeline YAML, action config). Squadron transparently
  rotates through pool members per the pool's strategy; every selection is recorded in the
  run state file.
- **`sq pools` CLI command group.** Inspect and manage model pools:
  - `sq pools list` — Rich table of all configured pools (Name, Strategy, Members, Source)
  - `sq pools list <name>` — detail view: pool metadata, members table, last 10 selections
  - `sq pools reset <name>` — clear round-robin position for a named pool
- **Built-in model pools.** Three pools ship out of the box in the alias registry:
  `review` (round-robin, mid-tier), `high` (random, strongest), `cheap` (cheapest).
  User overrides in `~/.config/squadron/pools.toml` layer on top.
- **Four selection strategies:** `random`, `round-robin`, `cheapest`, `weighted-random`.
  Round-robin position persists across runs in `~/.config/squadron/pool-state.toml`.

## [0.3.14] - 20260412

### Fixed
- Non-SDK summary models (e.g. minimax via openrouter) no longer produce empty
  or hallucinated summaries. Prior pipeline step results (dispatch responses,
  review findings, build_context output) are now assembled into a context block
  and prepended to the instructions sent to one-shot summary models. SDK-session
  summary paths are unaffected.

### Added
- `dispatch` is now a valid pipeline step type in YAML. Accepts optional `prompt`
  and `model` fields. Enables direct dispatch steps without wrapping in a phase
  step (design/tasks/implement).

## [0.3.13] - 20260411

### Fixed
- `/sq:summary --restore` no longer reports wrong filename when restoring in a
  project with a single summary file. The CLI now always emits the selected
  filename on stderr, and the slash command parses it explicitly instead of
  relying on a nearby example value.

### Added
- "Hallucination traps in prompts" rule added to CLAUDE.md — prevents placing
  hardcoded example values near fill-in slots in model instructions.

## [0.3.12] - 20260411

### Fixed
- `compact:` pipeline steps now work correctly in prompt-only mode. Previously,
  every pipeline using `compact:` (P6, slice, tasks, app, example) would stall
  because the prompt-only renderer emitted a literal `/compact [...]` string
  that Claude Code never interpreted as a slash command. `compact:` now routes
  through the same `summary` action as SDK mode, producing a proper summary
  action with `emit: [rotate]`.

### Changed
- `compact:` in pipeline YAML is now a pure step-type alias. The runtime
  `CompactAction`, `ActionType.COMPACT`, and `_render_compact` have been removed.
  All summary/compaction logic is now unified under `SummaryAction`. Existing
  pipeline YAML files using `compact:` require no changes.

## [0.3.11] - 20260411

### Added
- `/sq:summary` now writes the summary to disk (`{project}-interactive.md`) so
  `/sq:summary --restore` can restore it in a new session, exactly like pipeline
  summaries.

## [0.3.10] - 20260411

### Added
- Checkpoints now show an interactive menu instead of always exiting. When a
  review checkpoint fires during an SDK pipeline run, you can choose:
  - **[a] Accept** — use the review findings as instructions for the next step and
    keep going without restarting.
  - **[o] Override** — type custom instructions and continue in-place.
  - **[e] Exit** — save state and exit (previous behavior, unchanged).
- The resume command (`sq run --resume <run-id>`) is shown in the menu so you
  always know how to pick up where you left off after an Exit.
- Non-interactive environments (piped stdin, `SQUADRON_NO_INTERACTIVE=1`) default
  to Exit silently so CI pipelines never hang.
- Prompt-only checkpoint instructions now describe all three choices so a human
  operator knows exactly what to do at each checkpoint.

## [0.3.9] - 20260411

### Added
- Summary and compact pipeline steps now accept any configured model alias,
  not just Claude models. You can use openrouter, gemini, or local models
  as your summary model by setting `model:` on the step.
- Using `emit: [rotate]` with a non-SDK summary model now fails immediately
  with a clear error instead of silently misbehaving.

## [0.3.8] - 20260411

### Added
- Phase pipelines (P1, P2, P4, P5, P6) now write summaries to disk automatically.
  After any phase pipeline run, `/sq:summary --restore` will find the summary
  without needing a run-id.

### Fixed
- CI pyright failure introduced in 0.3.5; `main` is green again.

## [0.3.5] - 20260410

### Added
- `emit: [file]` in a pipeline summary step now writes to a standard path
  (`~/.config/squadron/runs/summaries/{project}-{pipeline}.md`) when no
  explicit path is given. The file is overwritten each run (latest-only).
- `/sq:summary --restore` — seeds the current conversation with the most
  recent pipeline summary for this project. No run-id needed; works after
  both SDK and prompt-only runs.

## [0.3.4] - 20260409

### Added
- `/sq:summary [template]` slash command — generates a structured summary of
  the current conversation and copies it to the clipboard. Intended for the
  `/sq:summary` → `/clear` → paste workflow. Uses your configured
  `compact.template` by default.

### Removed
- PreCompact hook subcommand removed; it was dead code since 0.3.3.

## [0.3.3] - 20260408

### Added
- `summary` pipeline step type — captures a session summary and sends it to
  one or more destinations: `stdout`, `file`, `clipboard`, or `rotate`
  (compact the session in place). `compact:` remains a supported alias.
  Add `checkpoint: true` to pause after the summary emits.
- `minimal-sdk` compaction template ships with Squadron for clean
  third-person summaries suitable for seeding a fresh session.

### Changed
- `sq install-commands` no longer installs a PreCompact hook — the hook API
  doesn't reliably override compaction instructions in practice.

### Fixed
- API errors returned as assistant text (e.g. `API Error: 500 …`) are now
  treated as dispatch failures. Previously the pipeline continued to the next
  step as if dispatch had succeeded.

## [0.3.2] - 20260407

### Fixed
- `sq run` was broken for all SDK pipelines — the Claude Agent SDK stopped
  accepting runtime permission-mode changes. Permissions are now set at
  session start.
- PreCompact hook payload was malformed, producing a "Hook JSON output
  validation failed" error in Claude Code sessions.
- `.squadron.toml` is now gitignored so per-developer config isn't
  accidentally committed.

## [0.3.1] - 20260407

### Added
- `/compact` in Claude Code now uses your Squadron compaction template
  automatically. Configure with `compact.template` (template name) or
  `compact.instructions` (literal text override) in your Squadron config.
  Install via `sq install-commands`.
- `sq run --status` now shows whether a run used SDK or prompt-only mode.
- Pipeline names are now case-insensitive on all platforms.

### Fixed
- `sq run` now validates the pipeline before starting — bad checkpoint
  triggers and other config errors are reported upfront instead of crashing
  mid-run.
- `sq run --resume` on SDK runs no longer falls through to a missing CF
  command.
- Implicit resume now works regardless of pipeline name casing.

## [0.3.0] - 20260407

### Added
- `sq run <pipeline> <target>` — execute a named pipeline end-to-end. SDK
  mode runs autonomously; `--prompt-only` mode emits step-by-step
  instructions for manual execution inside Claude Code.
- `sq run --list` — show all available pipelines.
- `sq run --validate <pipeline>` — check pipeline config for errors without
  running.
- `sq run --dry-run <pipeline> <target>` — preview the execution plan.
- `sq run --status [latest|<run-id>]` — inspect a run's current state.
- `sq run --resume <run-id>` — continue a paused run from its checkpoint.
- `sq run --from <step>` — start execution from a named step (adoption).
- `--param key=value` — pass additional parameters to a pipeline at runtime.
- `--model` — override the model for the entire run.
- Pipelines pause automatically at checkpoints and can be resumed; keyboard
  interrupt also pauses with resume instructions.
- Built-in pipelines: `slice-lifecycle`, `review-only`,
  `implementation-only`, `design-batch`.
- Pipeline steps iterate over CF collections with `each:` — e.g. run a
  review loop over every unfinished slice.
- `/sq:run` slash command updated to drive prompt-only pipeline execution.

### Fixed
- Review files are now saved even on FAIL verdict (previously only saved on
  CONCERNS or better).
- Review terminal output no longer has excess indentation on headings.
- SDK reviews (Claude/Anthropic) no longer duplicate findings in output.

## [0.2.12] - 20260328

### Added
- Set `SQUADRON_APP_NAME` to tag your requests in OpenRouter traces and
  Langfuse dashboards.

## [0.2.11] - 20260328

### Added
- `sq review arch <index>` — review an architecture document on its own
  merits (no `--against` required). Accepts a bare initiative number as
  shorthand.
- Per-review-type default model config: `default_model_arch`,
  `default_model_slice`, `default_model_tasks`, `default_model_code`.
- `sq config unset <key>` — remove a config key, reverting to the default.

## [0.2.7]

### Added
- **[Experimental]** Codex provider — use OpenAI Codex as a review or
  dispatch provider. Requires the separate Codex SDK.
- `sq review code` now auto-detects language rules and injects them into the
  review prompt. Use `--rules-dir` to point at a custom rules directory or
  `--no-rules` to disable.
- `sq review code` diff is now scoped to the current slice branch
  automatically via merge-base detection.
- `-vvv` prints the full system prompt, user prompt, and injected rules to
  stderr, and saves a prompt log to `~/.config/squadron/logs/`.

## [0.2.6] - 20260325

### Fixed
- `default_model` in config now goes through alias resolution. Previously
  only `--model` on the CLI was resolved, causing UNKNOWN verdict when using
  a config default.

## [0.2.5] - 20260323

### Fixed
- `.env` file loading now looks in the current working directory only,
  instead of walking up the directory tree from the package install location.

## [0.2.4] - 20260323

### Added
- API keys are now loaded from a `.env` file in the current directory at
  startup.

## [0.2.3] - 20260323

### Added
- `sq models --verbose` displays cost tier, privacy, and notes alongside
  each model alias.

## [0.2.2] - 20260322

### Changed
- `sq model` and `sq models` merged into a single `sq models` command.

## [0.2.1] - 20260321

### Added
- README updates: model aliases, slice reviews, version info.

## [0.2.0] - 20260321

### Added
- Model alias registry — define short names like `haiku` or `minimax` in
  `~/.config/squadron/models.toml` and use them everywhere.
- `sq models` command to list available aliases.
- `--profile` flag on all `sq review` commands to choose the provider
  (sdk, openrouter, openai, gemini, local).
- User-customizable review templates from `~/.config/squadron/templates/`.
- File content and git diff injected into prompts for non-SDK reviews.

### Changed
- `review arch` renamed to `review slice`.

## [0.1.1] - 20260321

### Added
- `/sq:run-slice` slash command — runs the full slice lifecycle
  (design → tasks → implement → review) in one command.
- Bare number shorthand for review commands: `sq review slice 118`,
  `sq review tasks 118`. Review files are saved automatically when using
  the shorthand.

## [0.1.0] - 20260217

### Added
- Initial release published to PyPI as `squadron-ai`.
- `sq` CLI with agent management commands: `spawn`, `list`, `task`,
  `shutdown`.
- Review workflows: slice, tasks, and code reviews with built-in templates.
- Verbosity levels, persistent config, text colors, `--rules` flag.
- Providers: Claude SDK, OpenAI-compatible, OpenRouter, local models,
  Gemini-via-compatible.
- `sq auth login` / `sq auth status` for API key management.
- `sq install-commands` for Claude Code slash command setup.
- GitHub Actions CI and PyPI publishing on tag.
