---
docType: devlog
scope: project-wide
description: Internal session log for development work and project context
---

# Development Log

Internal work log for squadron project development.

---

## 20260731

### Slice 910: Loop Convergence Correctness — Slice Design Complete

**Phase 4 complete.** Created `project-documents/user/slices/910-slice.loop-convergence-correctness.md` on branch `main` (planning work, no slice branch), from the slice-plan entry in `900-slices.maintenance-and-refactoring.md`. Three defects on the `loop:` execution path bundled into one slice because Parts A and B share `_execute_loop_body` and one test file: Part A findings-feedback gap (#42, High), Part B ambiguous multi-review `until:` gating (#43, High), Part C `--dry-run` loop-body expansion (#45, Low).

**Grounded every anchor against on-disk code, extending the scoping already done in the slice-plan entry:**
- **Part A:** re-confirmed `_execute_loop_body` (`executor.py:1298-1321`) passes the outer `prior_outputs` unchanged into every iteration, and that `DispatchAction._resolve_prompt_from_prior_review` (`dispatch.py:258-291`) is a complete, already-shipped consumer waiting on real data. Added a design-time decision the plan entry left open: keep the existing `{action_type}-{action_index}` key scheme for the accumulated `prior_outputs` (letting a later iteration's same-key write overwrite the earlier one) rather than folding the iteration number into the key, since the consumer only ever wants the *most recent* review, not a full history — full history is 911's job.
- **Part B:** traced which step types can actually produce a verdict-bearing action, since the fix counts them at validation time. Confirmed it's not just `StepTypeName.REVIEW` — `PhaseStepType.expand()` (`phase.py:156-169`) appends a `review` action from an inline `review:` sub-field, and `gate` (`actions/gate.py`) also produces a `verdict`. A loop body with two `phase:` steps each carrying inline `review:` is ambiguous under #43 even though neither inner step is literally type `review` — the validation check must expand inner steps and count actions, not pattern-match step-type names. Placed the check inside `LoopStepType.validate()` (`loop.py:30-115`) alongside the existing nested-loop ban, reusing the already-imported `unpack_inner_steps` helper. Flagged a fallback (raw-config inspection instead of calling `expand()`) in case any inner step type's `expand()` isn't side-effect-free.
- **Part C:** confirmed the exact one-line render site (`run.py:983`) and scoped the fix to a single `if step.step_type == "loop"` branch reusing `unpack_inner_steps` for the indented inner-step listing — no new rendering abstraction, matching Parts A/B's no-new-machinery bar.

**Also recorded, not fixed:** the `on_exhaust: skip` fall-through gap the plan entry already flagged as deferred (verified present at `executor.py:873/881`, `SKIPPED` absent from the run loop's early-return checks) is carried into the slice design as an explicit Known Issue, out of scope for all three parts, unchanged from the plan-entry framing.

**Sequencing:** Part B before Part A (establishes the one-verdict-per-body invariant Part A's tests assert against); Part C independent, any order.

**Next:** Phase 5 (Task Breakdown) for slice 910, not yet started.

### Slice 910: Loop Convergence Correctness — Review Resolution

**Review verdict PASS with one CONCERN (F001)**, raised against the three items the design deferred to implementation: Part A's `prior_outputs` key scheme, Part A's `step_outputs` interaction, and Part B's reliance on `expand()` purity. Traced all three against the actual code instead of leaving them open:

- **Key naming:** the plain `{action_type}-{action_index}` scheme (no iteration number folded in, same-key overwrite across iterations) is safe by construction, not just convenient — `action_type` carries no inner-step identity, so a same-key collision within one iteration can only happen if two inner steps produce the same action type, which is exactly the shape Part B's validation bans. Once Part B lands first, the collision case cannot occur.
- **`step_outputs`:** confirmed it's a disjoint mechanism from `prior_outputs` — created once per run, threaded by reference (never copied), written exactly once per top-level step after that step fully returns. Part A's fix never touches it.
- **`expand()` purity:** read every `expand()` implementation reachable inside a loop body (`compact`, `devlog`, `dispatch`, `gate`, `phase`, `review`, `summary`) — each is a pure dict transform with no I/O. Confirmed safe to call at validation time.

Updated the slice design in place (Part A and Part B sections rewritten from "confirm during implementation" to "resolved, not deferred" / "resolved, purity confirmed"), removed the Risk Assessment section since no open risk remained, and appended a Resolution block to the review file (F001 ACCEPTED, F002 ACKNOWLEDGED, F003/F004 no action) following the same pattern slice 909's review used.

### Slice 910: Loop Convergence Correctness — Task Breakdown Complete

**Phase 5 complete.** Created `project-documents/user/tasks/910-tasks.loop-convergence-correctness.md` (13 tasks, 269 lines) from the reviewed slice design. Order: Part B (T1-T4) → Part A (T5-T8) → Part C (T9-T12) → final validation (T13), matching the design's sequencing rationale.

**Found and resolved a design-document defect before writing tasks, not silently:** the slice design's Success Criteria and Verification Walkthrough for Parts B and C repeatedly cite `p45b.yaml` as an existing shipped pipeline demonstrating the two-loop-sequence pattern (design→review, then tasks→review). A full repo search found no such file — `src/squadron/data/pipelines/` contains only `judge-cycle.yaml` and `test-loop.yaml`, both single-loop, neither matching the two-loop shape the design describes. Rather than substitute a different pipeline or silently drop the walkthrough steps, raised this to the PM (AskUserQuestion) per the "stop and request clarifying information" rule in the Phase 5 guide and the project's "don't guess, ask" instruction. **Resolved:** `p45b.yaml` is real, provided directly by the PM, and confirmed present at `~/.config/squadron/pipelines/p45b.yaml` — squadron's user pipeline directory (`_USER_DIR`, `loader.py:23`), which `load_pipeline`/`sq run` already discover automatically. No task creates or moves it; Part B's T3 and Part C's T11 reference it by bare name exactly as the design's walkthrough specifies, and its actual two-sequential-single-review-loop shape is the precedent Part B's validation check is designed to keep valid.

**Test-with applied throughout:** T1 (validation check) → T2 (unit tests in `test_loop.py` + `test_loop_validation.py`) → T3 (manual confirm against real `p45b.yaml`); T5 (accumulate `prior_outputs`) → T6 (loop-body integration test) → T7 (end-to-end prompt-content assertion, closing the gap between "data is threaded" and "the consumer actually uses it"); T9 (`--dry-run` expansion) → T10 (CLI test) → T11 (manual confirm against real `p45b.yaml`). Each part's implementation task is immediately followed by its test task, per the guide.

**Next:** Phase 6 (Implementation) for slice 910, not yet started.

---

## 20260727

### Slice 323: Phase 6 Implementation and First Noise Floor

**T1-T21 complete; T22 complete for two projects, two deferred.** Three measurable results.

**The dispersion is a property of the instrument, not a model.**

| Instrument | Runs | Mean | Spread | % of mean |
|---|---|---|---|---|
| Opus, hash `d17ac6bf` | 22, 25, 27, 30 | 26.0 | 8 | 31% |
| Sonnet 5, hash `a5bc5b31` | 19, 22, 27 | 22.7 | 8 | 35% |

Two models, two sessions, two prompt hashes, the same absolute spread of 8 findings — a claim neither series could support alone.

**It widens with codebase size, worse than proportionally.**

| Project | LOC | Runs | Mean | Spread | % of mean |
|---|---|---|---|---|---|
| migratory-viewer | 3.2k | 19, 22, 27 | 22.7 | 8 | 35% |
| migratory | 44.4k | 49, 60, 82 | 63.7 | 33 | **52%** |
| squadron | large | 17, 79, 71 | 55.7 | 62 | **111%** |

On squadron the spread **exceeds its own mean** — 17 findings on one run, 79 on another, same unchanged commit. `migratory` clears the fan-out condition (44,359 LOC, 9 top-level dirs — the condition is >50k LOC *or* >5 modules) and run 1 made **360 tool calls** against 60-80 for a viewer run. This confirms the design's stated risk that fan-out is itself a variance source and can vary *within* a series, since the threshold is a prompt instruction rather than enforced code. It is also the concrete justification for the per-project floor decision: a single global threshold would understate large repos badly.

Two cautions on reading these numbers. Squadron's mean (55.7) is *lower* than the smaller `migratory` (63.7) only because one run drew 17 — with n=3, a single low draw moves the mean more than the codebases differ. And the floors themselves are correspondingly imprecise: three runs demonstrate that dispersion is large and size-dependent, but do not pin any one project's floor tightly. `metrology.audit_variance_runs` exists to raise that where a tighter floor is worth the cost.

**Per-category dispersion is where the usable signal is.** `architectural-decay` was the most stable category on both projects — 7-7 (sd 0) on viewer, 8-11 on a 14x larger codebase with fan-out — while `type-contract-debt` tripled (1-3 → 4-12). Some categories are plausibly gate-worthy today; totals are not. That distinction is what 324 needs and could not have been guessed from the totals.

The category vocabulary held across both: `other` was 0/22 and 2/49 (~4%).

**Deliberate deviation from the task text.** `AuditCategory`/`AuditSeverity`/`AuditEffort`/`AuditFinding`/`FloorStat`/`AuditRun`/`AuditNoiseFloor` all live in `metrology/models.py`, not `audit_models.py`. `AuditRun.findings` and `AuditNoiseFloor.per_category` embed them, so defining them separately would reintroduce the circular import the 322 layering correction removed. `audit_models.py` re-exports the full set.

#### Defects found by running it, not by testing it

Nine defects surfaced in T22 that fixture tests could not have caught. In rough order of how much they cost:

1. **`rate_limit_event` is not a throttle.** The CLI's own schema describes it as "emitted when rate limit info changes" — a usage-meter status event whose `rate_limit_info.status` is `allowed | allowed_warning | rejected` — and the CLI's own SDK adapter ignores the type outright (`[sdkMessageAdapter] Ignoring rate_limit_event message`). Squadron substring-matched `"rate_limit"` and slept. On a heavily-used account these fire constantly, so every audit paused and restarted its stream on each usage tick. Every "Rate limited (attempt N/10)" line before `72bbcb3` was a meter update; the account was never throttled. Measured payloads confirmed it: 12 events in a healthy 471s run, all `status: allowed`.
2. **A parse failure kills the stream permanently, so the old skip never worked.** The SDK calls `parse_message` *inside* the `async for` driving its message generator (`_internal/client.py:141`), so a raised `MessageParseError` terminates that generator — every later `__anext__` raises `StopAsyncIteration`. `_skip_unparseable` caught and `continue`d on a corpse. Short runs ended quietly with partial output, which is why this went unnoticed until an audit long enough to span a meter update. Fixed by absorbing informational events in the parser itself (`install_rate_limit_parser_shim`) so nothing raises. Two SDK call sites needed patching — client mode imports at call time, query mode binds at module scope — verified rather than assumed after patching one left the other broken.
3. **The whole skill file was being sent as the prompt.** `build_audit_prompt` sent all 17KB including YAML frontmatter (`disable-model-invocation: true`) and 6.5KB of human installation docs. The model read it as a document and returned ~2KB of acknowledgement. `extract_audit_protocol` now strips both halves: 17430 → 10975 bytes.
4. **The findings were being read from the response stream.** The design's own recorded ground truth said the skill writes a file and does not return findings; the harness parsed the stream anyway. `find_audit_file` now locates the file, mtime-restricted so a stale audit cannot persist under a new run id.
5. **Wrong artifact path, twice.** Output goes to `project-documents/user/analysis/`, not `analysis/`, because the skill cites `file-naming-conventions`. Also git collapses a wholly-untracked tree to its *shallowest* ancestor (`?? project-documents/`), so every prefix of both locations must match the dirty-worktree exemption.
6. **The variance series refused its own output file** — would have produced zero floors campaign-wide (`5340c0f`).
7. **No `Write`/`Edit` in the allowed-tools list** while the audit's entire product is a file. It did not fail loudly: the model routed around it via Bash heredocs.
8. **Zero-delay retry loops.** Both carried a comment claiming "the CLI handles the backoff delay" and slept for nothing — measured at 11 attempts in 0.1ms. Also present on the pipeline path (`sdk_session.py`), so it affected review and dispatch equally, not just audits.
9. **The retry budget never reset.** Initialised outside the loop, so it bounded throttles-per-run rather than consecutive failures; a long run exhausted it while still making progress.

#### Instrument provenance was unpinned in three ways

All three were invisible in the stored record, and all three can drift:

- **Model.** Squadron sent no `--model`, so the CLI chose its own — measured as `claude-opus-4-6[1m]`, the most expensive option available. The record stored the literal `"sdk"` and so could not say what ran. Fixed by `metrology.audit_model` (`aee96b2`), which also writes the resolved model onto the record.
- **Effort and thinking.** Squadron sends neither `--effort` nor `--thinking`; `AgentConfig` has no fields for them, so they are structurally unreachable rather than merely unset. The CLI's default for these is *undocumented and unreported*. Filed as #33.
- **The skill's own output.** Now required to carry a `model:` frontmatter field (canonical fork `bf94c72`, vendored in sync). This moved `audit_prompt_hash` `d17ac6bf` → `a5bc5b31`, closing the Opus generation — accepted deliberately rather than reverted.

#### Open, filed, not fixed

- **#34: squadron draws ~3x the session budget of the same skill run interactively.** Same model, same repo, same commit: ~1% manual vs ~3% squadron. Model is eliminated as a cause. Tool-call counts (60-80) against a raw-CLI baseline of 63 do not obviously explain it either.
- **#30: the SDK pin is now blocking, not hygiene.** Squadron runs the SDK's *bundled* CLI 2.1.47 (July 8) while interactive sessions run 2.1.220 — ~170 versions apart. This invalidated every squadron-vs-manual comparison attempted during the session until it was found, and it is why the parser lacks a `rate_limit_event` case at all.
- **#33/#36: token and cost capture.** `ResultMessage` carries full usage accounting; `translate_sdk_message` discards all of it. One measured audit: 2.17M cache-read, 137k cache-creation, 15k output, $2.37. Note for whoever implements it — **do not sum per-message `usage`**, it repeats a snapshot within a turn (7.08M summed vs 2.17M authoritative, while understating output 2,174 vs 15,231).
- **#35: alternative providers.** Cross-model agreement is a stronger quality signal than one model's repeat rate, and unreachable while the harness is Anthropic-only.
- **#38: SDK teardown leaks an unretrieved task exception.** A successful squadron run printed a raw `ProcessError: exit code -15` traceback mid-campaign. Exit -15 is SIGTERM from the SDK's own `close()`; the run had already completed and persisted. `shutdown()` catches `disconnect()` errors but this one is raised in the SDK's background reader task, which nothing awaits. Cosmetic for data, but it cost real diagnostic time — it was initially mistaken for a truncated run — and a *genuine* teardown failure would look identical.
- **#37: the skill emits inline YAML scalars for prose.** `migratory` run 1 needed `_quote_prose_scalars` repair before parsing (`mapping values are not allowed here`). The retry recovered a complete 82-finding audit rather than discarding it, so the fallback works — but block scalars at the source would remove the failure mode. Deliberately not fixed during the campaign: it changes the skill and therefore `audit_prompt_hash`.

#### Process note

The branch convention slipped: 34 implementation commits went to `main` instead of a `323-slice.*` branch. Caught late, and by then 24 were already pushed. Left as-is at the PM's call. The check belongs at the *first* implementation commit, not partway through.

---

## 20260726 (2)

### Task Breakdown 323: Tech-Debt-Audit Baseline Harness — Phase 5 Complete

**Phase 5 complete.** Created `user/tasks/323-tasks.tech-debt-audit-baseline-harness.md` — 22 tasks, 370 lines (under the 450 target, no split). Test tasks sit immediately after their implementation task throughout, per the test-with pattern.

**Ordering is driven by one constraint: the instrument must be stable before anything measures with it.** So the fork edits come first (T1-T3: findings block → category vocabulary + independent-run mode → vendor into squadron), with the CI sync guard at T4. Everything downstream hashes the vendored copy, so an unstable instrument early would poison every later comparison.

Sequence: fork + vendor + sync test (T1-T4) → models + store extension (T5-T8) → parser (T9-T10) → harness with failure handling (T11-T14) → variance reduction (T15-T16) → baseline report (T17-T18) → config keys (T19) → CLI (T20-T21) → end-to-end + the real campaign (T22).

**Deliberate cost shaping.** T22 is the *only* task that spends real tokens at scale (the 12-audit campaign). T1-T21 are all testable on fixtures with a stubbed agent at zero token cost, and the task file says so explicitly so an implementer does not casually burn a campaign mid-development. T14's pre-flight test asserts the agent stub was *never constructed* on a misconfigured project — proving zero spend, not just correct behavior.

**Tasks that encode a correctness trap rather than a feature:**
- **T15 per-category zero-fill** — a category absent from one run counts as 0 for that run, not as missing. Otherwise the spread is computed over the wrong denominator and the floor is silently wrong.
- **T13/T14 persist-nothing-on-failure** — the design's Decision 9 restated as an assertion: each simulated failure persists *zero* records. A partial record would let a hung run masquerade as a low-finding sample and bias the floor downward, the same direction the repeat-run hazard threatened.
- **T9 distinct absent-vs-malformed errors** — not stylistic; T13 logs them differently, and conflating them would hide a model that stopped emitting the block at all behind "parse noise."
- **T8 vocabulary-isolation test** — asserts no `AuditSeverity` value equals any review `Severity` value, so a future edit cannot quietly merge two deliberately disjoint vocabularies.
- **T20/T21 honest campaign summary** — a campaign with failed runs must not exit 0 as though all succeeded.

**Open item carried into implementation:** the `other`-category share per project is a real output of T22, not just a metric — a high share means the 9 dimensions do not fit that codebase, which is information for 324 rather than something to suppress.

**Task review resolved (same day, z-ai/glm-5.2 — a new reviewer model for this project).** Verdict CONCERNS with one **FAIL**, and the FAIL was a real defect I introduced: config-key registration was sequenced *after* the task that reads `metrology.audit_timeout_s`, while that task's own text said "this must precede any code that reads them." A self-contradiction that would have failed at implementation, since `get_config` raises `KeyError` for an unregistered key. Config keys moved to T11 ahead of all `audit.py` work; old T11-T18 renumbered to T12-T19; six internal cross-references updated; an explicit ordering note added so a future edit cannot silently re-break it.

- **F002** — T4 asserted the independent-run *marker* was present but never that T2's rewording of the repeat-run clause landed, leaving the design's success criterion unverified. Assertion added. Higher-stakes than a normal coverage gap: an unconditional repeat-run clause would silently correlate variance runs and bias the floor toward zero.
- **F003 (T14 sizing)** — acknowledged, no change, using the reviewer's own reasoning: splitting would create an artificial seam, because Decision 9 makes failure handling *part of* the execution contract rather than a wrapper. A basic-execution task that persisted before failure handling landed would be a partial-record path — exactly what the design forbids.
- **F004** — explicit push-to-remote step added to T3. Vendoring from an unpushed local fork would satisfy squadron while leaving every other fork consumer on the pre-contract instrument.

Worth noting across the three reviews this slice has now had (kimi-k2.7-code and claude-sonnet-5 on the design, glm-5.2 on the tasks): each model found something the others did not, and glm-5.2 was the only one to catch a hard sequencing error — the kind of defect that is invisible when reading a document for sense and obvious when tracing execution order.

---

## 20260726 (1)

### Slice Design 323: Tech-Debt-Audit Baseline Harness — Phase 4 Complete

**Phase 4 complete.** Created `user/slices/323-slice.tech-debt-audit-baseline-harness.md`; marked the 320 slice-plan entry as designed. First slice of the **audit oracle** — reuses the 320 spine (persistence + trend) but at the project/issue-class grain, with no agreement dimension.

**Reconnaissance changed the design's shape.** Three properties of the `tech-debt-audit` skill were verified against the file rather than assumed:
- It writes to a **model-chosen path** (`analysis/nnn-analysis.*.md`, `:62`) — capturing response text gets narration, not the audit.
- **Repeat-run mode** (`:103`) makes run 2 of a variance series read run 1 and emit a diff. This biases a measured noise floor *toward zero* — the worst direction, since it makes every later 324 delta look significant. The unmodified skill is therefore incompatible with the measurement this slice exists to take.
- **Category is free text** (the 9 dimensions at `:40-56` are prose headings), so cross-project comparison at the issue-class grain is impossible without a closed vocabulary.

**Key decision — fix the fork, do not wrap it.** The initial approach was composing a prompt in Python (strip the Deliverable/repeat-run sections, append a squadron-authored output contract). PM noted the "shipped" skill *is* our fork (`github:ecorkran/tech-debt-audit`), already adapted for cf/squadron. That removes the only reason to wrap: with the contract in the skill file, `/analysis:tech-debt-audit` and the harness consume one artifact, so **no drift is possible between what users run and what the baseline measures**. Strictly less machinery. Makes `[340]` a real coupling — 323 modifies a shipped 340-band artifact — recorded as a decision rather than a discovery.

**Other decisions of consequence:**
- **Findings block is fenced YAML**, not a markdown pipe table — reuses the known-good frontmatter reader (`identity.py:162`); no table parser exists in the repo. Emitted *in addition to* the human table, mirroring the review system's serialize-twice precedent (`persistence.py:130-186`).
- **Severity vocabularies stay disjoint.** Audit `Critical/High/Medium/Low` is *not* mapped onto review `PASS/NOTE/CONCERN/FAIL` — different things on different artifacts; a mapping would manufacture equivalence.
- **Locations recorded, not resolved** — deliberately unlike the review parser's `_check_path_existence`. The count and class are the measurement; a fabricated location does not corrupt a count, and re-verifying across N×M runs is I/O the measurement does not need.
- **Floor is per-project at a pinned commit**, 3 runs (`metrology.audit_variance_runs`). A project without a measured floor is marked "no floor measured" and never borrows another's. Dirty worktree or mismatched SHAs across a series is *refused, not averaged* — otherwise "unchanged code" is an assumption rather than a verified precondition.
- **One run = one persisted unit**; series reduction is a separate pure pass. At 12-audit scale, a failure on run 3 must not discard runs 1-2, and the reduction stays unit-testable at zero token cost.
- **`audit_prompt_hash` on every record** — same discipline 322 canonized for judge templates. Since this slice edits the skill, baselines across that edit are not comparable and are grouped, not pooled.

**Variance set chosen for contrast, sized from the actual repos** (not assumed): squadron (py, ~64k LOC), migratory (py+GPU, ~44k), context-forge (TS, ~61k — isolates language from size), migratory-viewer (TS/UI, ~6.2k — order-of-magnitude smaller). All resolve identity from a git remote, so no `metrology.project_id` prerequisite. `trading-data` recorded as a **stretch case in Future Work**, not the committed set — it is the most likely to expose whether the 9 dimensions fit a database-heavy codebase, which is a question about the instrument rather than a gate on this slice. Note squadron/context-forge both exceed the skill's 50k-LOC subagent threshold (`:97`), making fan-out a plausible variance source — measured, not mitigated, which is why the small repo is in the set.

**Cost is stated, not hidden:** 4 projects × 3 runs = 12 full-repo LLM audits, plus one baseline run each. Dominant cost of the slice and the reason the harness is resumable by design.

**Fork sync made explicit scope (PM decision).** The skill has three homes — the standalone fork, squadron's bundled `commands/analysis/` copy, and installed `~/.claude/commands/` copies. **The fork is canonical**; squadron vendors it. Chosen over squadron-canonical because the skill is distributable beyond squadron: if squadron led, other consumers would run the pre-contract instrument, and since `audit_prompt_hash` correctly refuses to pool audits from differing prompts, the symptom would be a **silent measurement gap** (audits that never compare) rather than a loud error. Sync is enforced by the category-match test rather than remembered, and the hash is computed from the vendored copy actually used so divergence is recorded in the data even if it escapes CI.

**Slice-design review resolved (same day).** Two independent reviews ran against the design — kimi-k2.7-code (filed to `user/analysis/` for reference) and claude-sonnet-5 (`user/reviews/`). Both returned CONCERNS and both independently found the failure-mode gap, which is why it was treated as confirmed without further verification. The Sonnet review was materially more thorough (6 findings vs 3) specifically because it cross-referenced the architecture, slice plan, and *sibling slice frontmatter* rather than reviewing the document against itself — which is what surfaced the two structural findings kimi missed.

- **F001 failure modes** — real gap, now fixed. Verifying the premise made it stronger than the finding stated: `run_review_with_profile` has **no** handling to inherit (`review_client.py:134-156` is a bare `async for` with only `finally: shutdown()` — no timeout, no exception handling around the stream; every try/except in that module guards file/git I/O). Tolerable for an interactive review, not for an unattended 12-run campaign against an external cwd with subagent fan-out. Added an eight-mode table with detection/response/signal, anchored on Decision 9: **a run persists a complete `AuditRun` or nothing** — so a hung or truncated run can never masquerade as a low-finding sample and bias the floor downward (the same direction Fact 2 warns about). Plus pre-flight checks before token spend, series-degrade-not-abort, and `metrology.audit_timeout_s` (default 3600).
- **F002 `interfaces: []`** — a genuine bug in my frontmatter, diagnosed exactly right by the reviewer as copy-paste from 322. Verified against siblings (320 → `[321,322,323,324]`, 321 → `[322]`): the field lists *downstream consumers*, 322 is `[]` correctly because it is terminal, but 324 consumes 323's baseline and floor. Corrected to `interfaces: [324]`.
- **F003 340 boundary** — recorded in the parent architecture's Related Work, which had described 340 as read-only ("ships the analysis pack... this component's code-quality oracle runs"). It now states 323 makes it read-write, names the MIT fork as canonical, notes edits reach every consumer of that fork, and records PM approval. The reviewer graded this NOTE and credited the disclosure, correctly — but the sign-off lived only in conversation and the DEVLOG, not where a future reader of the architecture would find it.

**Fan-out on the large repos is expected and deliberately not suppressed.** `:97` dispatches Task subagents above 50k LOC / 5 top-level modules — squadron and context-forge clear it. It is a prompt instruction, not enforced code, so it may vary *within* a series and widen that project's floor. That is correct: it is noise a real user of the skill experiences, so it belongs inside the measured floor rather than engineered out of it.

**One plan-level open question resolved:** finding-normalization schema + repeated-run count (both recorded in the 320 plan Notes). Four Future Work items opened: human-table fallback parser, `trading-data` stretch run, periodic re-audit cadence, project registry.

---

## 20260725

### Slice Design 322: Calibration-to-Threshold Feedback — Phase 4 Complete

**Phase 4 complete.** Created `user/slices/322-slice.calibration-to-threshold-feedback.md`; materialized `(322)` in the 320 slice plan and marked its entry as designed. Terminal slice of the human-oracle chain (320 → 321 → 322), so `interfaces: []` — 323/324 are the audit oracle and share the 320 *spine*, not this path.

**Three plan-level open questions resolved, all against the actual code rather than the prose:**

1. **Version identity → the content-hash-at-capture fallback ships.** 320's `derive_judge_config_id` already computes `template_content_hash` and 321 already enforces non-blending on it, so no 300 write-path change is taken. The initiative's own *read-side over 300's write path* principle points here. 320-plan Future Work #1 (the 300 version field) and 321 Future Work #2 (judge-verdict persistence, which would ride with it) both stay **open**.

2. **The comparability hash must exclude the `judge:` block — a correctness fix, not a preference.** `identity.py:298` currently hashes `{name, description, system_prompt, model, prompt_template, **judge**}`, and `judge` *is* `pass_floor`/`concerns_floor`. So acting on a graduation recommendation changes the hash → new `JudgeConfigId` → accumulated n resets to 0 → the cell drops below the floor → no further recommendation possible. **The calibration loop would destroy its own evidence every time it worked.** The plan flagged template *editing* as the churn risk; the loop's own success is in fact the dominant source. Fix: narrow the hash to the judged behavior, excluding thresholds — thresholds are the calibration's *output*, not part of the instrument. A judge that scores identically but bands differently is the same instrument with a different readout. Rejected the plan's third framing (a similarity/inherit policy) as more machinery than the actual failure needs. Costs a one-time re-key of historical records, accepted deliberately and documented.

3. **Residual sampling → policy + offer-selection core, CLI-drained.** `capture.py`'s `sample_budget` is a ceiling on *writes*, not offers, and 320 explicitly deferred offer/selection — so the architecture's "continued forced random sampling" commitment needed a selection surface, which 322 adds. Offers are pull-based and non-blocking (nothing in a pipeline/gate/dispatch waits); "forced rate" means offers are *generated* at that rate. Doc-only was rejected: the architecture demands this be *asserted by a test* ("a graduated judge still produces sampled data"), which a documented policy cannot satisfy.

**Other decisions of substance:**
- **Direction bands are asymmetric.** Loosening is floor-gated; **tightening is not** — requiring a large sample before *warning* about a judge that disagrees with the human would suppress the signal most worth having early. Honest reading of the architecture's "refuses to recommend *loosening* below a floor."
- **Recommendations are directions + evidence, never a computed `pass_floor`.** Deriving a specific numeric threshold would imply precision small-n data cannot support and would edge toward the forbidden self-tuning loop. Output shows *currently configured* thresholds (read via `resolve_thresholds`) so the operator sees the delta and picks the magnitude.
- **The (template,model) ↔ (template,step) mismatch is per-recommendation output**, not a footnote — every recommendation carries the note, including the runtime-drawn-model (180 pool) case where the threshold cannot track the drawn model. Making it output is what stops it being ignored at the moment of action.

**Verified against code, not assumed:** two threshold surfaces exist and neither has a model dimension (`judge.py:41-57` merges step override → template default → module constant `75.0`/`50.0`; template blocks live in the judge YAMLs at `pass_floor: 78`/`82`). `GraduatedConfig` persists behind 320's reserved `record_type` discriminator — no store migration.

**Pending.** Frontmatter `status: not-started`. Next: Phase 5 (task breakdown) for 322. Effort 3/5.

### 322 Slice Review — Addressed (F002 valid, F003 declined)

Slice review (`322-review.slice...`, kimi-k2.7-code): 1 PASS, 1 CONCERN, 1 NOTE.

- **F002 (CONCERN, `GraduatedConfig` omits judge-configuration identity) — correct, and the same bug class as the hash-scope issue: an identity missing its version key.** I keyed graduation on `(template_name, model, artifact_level)`, which is **invariant across a prompt edit** — so a graduation earned under one prompt would silently transfer to a rewritten judge, and `select_residual_offers` would keep drawing spot-checks against it. Version-blending at the one point in the initiative where a *trust* decision is recorded rather than a measurement, with residual sampling then verifying an instrument nobody calibrated. Fixed: `GraduatedConfig` carries the full `JudgeConfigId`; offers match that exact identity; added the *Graduation is version-scoped* decision, a lapsed-graduation failure-mode row (empty offers **with** an explanatory line — an operator who edits a prompt learns the graduation lapsed rather than discovering sampling quietly stopped), a success criterion, walkthrough step 7, and test coverage.

  Worth recording how this composes with the hash narrowing: because the hash **excludes** the threshold block, graduation survives the operator acting on it; because it **includes** prompt and model, graduation expires on genuine drift. The two decisions are what make each other safe — either alone is wrong.

- **F003 (NOTE, low-level I/O failure modes) — declined with rationale.** Asked for rows on store lock contention and read timeouts. Checked the code: these paths are local-filesystem with no lock and no timeout-bearing transport; `store.py:177` already skips unreadable siblings on `(OSError, ValueError, SchemaVersionError)` with a WARNING and reports over what loaded, and writes are atomic write-then-rename. Adding rows for mechanisms that don't exist would document fiction. Recorded the actual inherited behavior instead, and noted that an off-filesystem store (280 convergence) would bring its own transport failure modes and its own rows.

### cf config hygiene

`custom.recentEvents` (rendered as "Current Project State" in `/cf:build` output) still pointed at the orchestration-v2 initiative (`100-arch`/`100-slices`) while the authoritative `Architecture:`/`Slice Plan:` fields correctly read 320. Updated to the 320 artifacts so the loaded context stops contradicting itself.

### Slice 322: Calibration-to-Threshold Feedback — Phase 5 Task Breakdown Complete

Created `user/tasks/322-tasks.calibration-to-threshold-feedback.md` — 17 tasks, test-with pattern throughout, following the design's suggested implementation order.

**Sequencing follows the design's own reasoning, not just its task list:** the `identity._template_content_hash` narrowing (T1/T2) comes first because everything downstream — the recommendation core, the graduated-config registry — accumulates evidence under the corrected key; doing it later would mean re-deriving fixtures once the hash changed underneath them. Config keys (`metrology.graduate_match_rate`, `metrology.tighten_match_rate`, `metrology.residual_sample_rate`) land (T5/T6) before the calibration-core tasks that read them (T7-T10), same lesson 321 already applied (its F004) to avoid a task hard-coding a temporary default.

**Direction classification (T7/T8) calls out a precedence subtlety explicitly:** the floor gates *loosening* only. A below-floor cell with a low match rate must still resolve to `TIGHTEN`, not fall through to `INSUFFICIENT_EVIDENCE` — implementing the bands as a naive top-to-bottom if-chain gated uniformly by the floor would silently swallow the "flag a bad judge early" case the design calls out as the asymmetry's whole point. Wrote the task to spell out the precedence order and require a test for exactly this boundary (below-floor + low-match-rate → `TIGHTEN`).

**Graduation registry (T11-T14) carries the slice-review's F002 fix as a first-class regression test, not an afterthought:** T12 requires two `JudgeConfigId`s sharing `template_name`+`model` but differing `template_content_hash` to *not* cross-match in `find_graduation` — the version-blending bug the review caught, now pinned by a test before implementation is written against it.

**One task (T13, offer selection) carries a deliberate escape hatch:** selecting unsampled judge results matching a graduated config's exact identity may need a result-discovery surface 320 doesn't currently expose (list_samples finds *captured* samples, not all persisted judge results). The task instructs against inventing a new file-walk and to flag the gap to the Project Manager if 320's surface doesn't already support it, rather than guessing at an implementation.

**Not re-litigated:** all three plan-level open questions the design resolved (content-hash version identity, the hash-scope correctness fix, residual-sampling-as-policy) are carried into the task file's context summary as settled facts, per the task-breakdown guide's "don't re-guess at task time" instruction — none reopened here.

Task file is 288 lines, well within the ~450-line guideline. Frontmatter `status: not_started`; slice design frontmatter remains `status: not-started` (Phase 6 implementation not yet started). Coverage-checked against the design's Failure Modes table and Success Criteria — all rows traced to a task.

### 322 Task Review — Addressed (F001 fixed, F002/F003 fixed)

Task review (`322-review.tasks...`, kimi-k2.7-code): 1 PASS, 1 CONCERN, 2 NOTEs.

- **F001 (CONCERN, T7 precedence contradicts its own "tightening is not floor-gated" claim) — correct, and a real bug in the task, not just prose.** T7's original numbered precedence checked `n < floor` first, unconditionally, then claimed a few lines later that `TIGHTEN` was "reachable even if `n < floor`." A literal top-to-bottom if-elif of that ordering makes `TIGHTEN` unreachable below the floor — the numbering itself contradicted the design's Direction Bands table it was supposed to encode. Fixed: reordered so unversioned is checked first, then `TIGHTEN` (before the floor applies), then the floor gates only what's left (`GRADUATE`/`HOLD`). The floor now only ever blocks loosening, matching the design exactly.
- **F002 (NOTE, T8 claimed a malformed-judge-block test that wasn't actually listed) — correct.** The Coverage Check asserted this was "exercised in T8" but T8's bullets only covered registered-vs-unregistered templates. Added an explicit T8 bullet: a template with a non-numeric `pass_floor` must not fabricate a threshold, delegating to `resolve_thresholds`' inherited WARNING instead.
- **F003 (NOTE, T13's residual-offer selection leaned on an unverified 320 surface) — correct, and worth resolving rather than deferring further.** Checked `capture.py` directly: `resolve_target` only resolves *one* target given an already-known slice index (`reviews_dir.glob(f"{index}-review.*")`) — there is no whole-project "list every judge review file" surface for residual sampling to diff against. Rather than leave this as a runtime judgment call for whoever implements T13 (my original escape-hatch phrasing), split out a new **T13 (judge-result discovery surface) + T13b (its tests)** ahead of the renumbered offer-selection task (T14), so the gap is resolved at task-breakdown time. Renumbered T13-T17 to T14-T18 throughout, including all cross-references and the Coverage Check.

---

## 20260718

### 320 Keystone Task Review — Addressed (F001 budget, F008 traceability)

Task review (`320-review.tasks...`, kimi-k2.7-code) returned 6 PASS, 1 CONCERN, 1 NOTE — both actionable, both fixed:
- **F001 (CONCERN, sample budget registered but never enforced/tested):** correct gap — I added `metrology.sample_budget` to config but no task read it. Added budget enforcement to T10's `record_sample` (count prior captures for the `project_id` via `list_samples`; at/over budget → refuse the write, no error, a normal "ceiling reached" outcome), T11 asserts the (N+1)th write refuses per-project, T14 reports budget-exhausted and exits 0, T15 asserts it. **Scope correction made explicit in the task:** this slice enforces a ceiling on *captures written*, not on *offering* — the offer/selection policy is deferred to 321, so there is no offer queue here to gate; the write-ceiling is the enforceable slice of the design's "respects the configured budget" criterion.
- **F008 (NOTE, failure-mode traceability):** Coverage Check mapped all Failure Modes rows to T15, but git-remote-absent is asserted in T3 and malformed-target in T5. Corrected the cross-reference to show T3 + T5 + T15 jointly cover the table.

Task file now 252 lines (within 450). Verdict was CONCERNS; both items resolved in-place.

### Task Breakdown 320: Metrology Keystone — Phase 5 Complete

**Phase 5 complete.** Created `user/tasks/320-tasks.metrology-data-layer-sample-capture-keystone.md` (247 lines, within the 450 target — no split). 16 tasks (T1–T16), sequentially ordered following the LLD's Development Approach (identity → models/store → capture → CLI/config → e2e), test-with pairing throughout (each impl task immediately followed by its test task), per-task semantic commit lines.

**Ordering rationale:** identity first (T2–T5) because it's the hardest new territory and everything keys on it — the content-addressed result ref and project-id derivation are the two things squadron lacks today. Store (T8/T9) modeled on `StateManager` with the cross-project-query test called out explicitly. Blindness (T10/T11) has its own load-bearing test asserting the capture payload excludes judge output (data-layer enforcement, not UI). All Failure Modes table rows collapse into T15's CLI failure-mode coverage (one assertion per row). T16 is the judging-path regression gate + walkthrough smoke + slice-completion marking.

**Coverage check appended** mapping every design element to tasks and confirming the correct absences (321 reporting, 322 version-keying resolution, 323 audit records, MCP tool, 300 write-path change — all deferred by design, none in this task file).

**Pending.** Frontmatter `status: not_started`. Next: PM approval, then Phase 6 (implementation) on branch `320-slice.metrology-data-layer-sample-capture-keystone` (integration branch unset → forks from and merges to `main`).

### 320 Keystone Slice Review — Addressed (F001, F005)

Slice review (`320-review.slice...`, kimi-k2.7-code) returned 3 PASS on the load-bearing dimensions (scope deferral, architectural commitments, version-keying deferral), 1 CONCERN, 1 NOTE — both actionable, both fixed in the design:
- **F001 (CONCERN, failure-mode enumeration):** design stated "typed errors/actionable messages" without enumerating modes — a direct hit on the project's Failure-Mode Enumeration rule. Added a **Failure Modes** table under Implementation Details covering all new I/O boundaries (git-remote subprocess w/ timeout, project-identity absence, review-file missing/malformed, target zero/multi-match, atomic store-write failure, non-TTY/SIGINT/invalid-input capture), each with an explicit handling decision, an observable signal (typed error at ERROR / clean skip at INFO / no partial record — never silent), and a required test. Introduced three typed exceptions (`MetrologyIdentityError`, `MetrologyTargetError`, `MetrologyStoreError`) so "bad input" is distinguishable from "store broken." Absent git remote is deliberately *not* an error (normal case, defined fallback) but still surfaces loudly if the fallback also yields nothing.
- **F005 (NOTE, CLI consistency):** walkthrough used `--type` but API Contracts didn't document it. Documented the full `sq metrology sample <target> [--type] [--verdict] [--note] [--skip]` signature and clarified target forms (path alone, or bare index + `--type`, required when the index is ambiguous). Walkthrough now consistent.

Added a Technical Requirement that every Failure Modes row has a test asserting its observable signal.

### Slice Design 320: Metrology Data Layer & Sample Capture (keystone) — Phase 4 Complete

**Phase 4 complete for the keystone.** Created `user/slices/320-slice.metrology-data-layer-sample-capture-keystone.md`. Index already materialized as `(320)` in the slice plan (first slice shares the initiative base). Designed against the actual codebase, not assumptions — mapped 300's persistence and squadron infra first.

**Load-bearing reality that shaped the design:** 300 review results are **id-less flat files** (`review/persistence.py` writes `project-documents/user/reviews/{index}-review.{type}.{slice}.{ext}`, overwritten on re-run — no run-id, no DB, no query surface over scores). So the keystone must *introduce* two things that don't exist in squadron today:
- **Stable project identity** — git-remote-URL-derived (normalized), fallback to a recorded `.squadron.toml` `metrology.project_id`; **fails explicitly** if neither exists (never a path fallback, per arch + no-silent-fallback rule). No project identity exists in the codebase today (confirmed).
- **Stable judge-result reference** — content-addressed `(project_id, relative_review_path, content_hash)` over the canonical judge fields, because there is no id to key against and re-runs overwrite the file.

**Store follows the `StateManager` precedent exactly** (`pipeline/state.py`): user-level `~/.config/squadron/metrology/`, Pydantic records at the file boundary, `_SCHEMA_VERSION` + `SchemaVersionError`, atomic write-then-rename, one JSON file per record, glob-and-filter query surface. **No new DB dependency** — matches established squadron convention (config TOML, JSON run state). A `record_type` envelope discriminator (`"sample"` now, `"audit_finding"` reserved) lets 323 add audit records without migration.

**Blindness enforced at the data layer, not the UI:** the capture core builds the presented payload from artifact + ground truth only and never places judge output in it — assertable by a test on the payload, not a fragile render-order convention. Human-load constraints from the prior session's arch amendment are carried through as success criteria (blindness scoped to designated samples; non-blocking; skip records nothing; budget respected as an offered-sample ceiling).

**Parity by shared core:** new `squadron.metrology` package (identity/models/store/capture) is surface-agnostic; `cli/commands/metrology.py` is a thin Typer sub-app delegating to it (the `config.py` pattern). No MCP tool ships (MCP surface is still a stub) — parity is structural, guaranteed when the MCP slice later wraps the same core.

**Command surface:** `sq metrology sample <target>` (blind capture) + `sq metrology list` (inspection aid, not the 321 reporting surface). Config keys added to `CONFIG_KEYS`: `metrology.store_dir`, `metrology.sample_budget`, `metrology.project_id`.

**Deferrals honored:** no agreement/dispersion math (321), no version-keying *resolution* or minimum-evidence floor (322) — this slice records both a template-content hash and the judge-config identity as candidate keys but decides neither; no audit records (323); no judging-path change.

**Pending.** Frontmatter `status: not_started`. Next: Phase 5 (task breakdown) for 320, or design the remaining slices (321–324). Effort 4/5.

### 320 Human-Load Constraints: Blind-Capture Scoping & Sampling Budget

**Concern raised by PM:** the blind-capture design read as "operator must always evaluate before judge output is visible" — an efficiency regression, and incompatible with the Amoeba direction (Amoeba takes over much running of squadron; human only at critical points; concept-stage, but 320's calibrated judges are its prerequisite — uncalibrated judges would make Amoeba's decisions unacceptably unpredictable).

**Evaluation outcome:** architecture direction confirmed correct (calibration is the *exit* from the resident-human loop, not more of it), but the docs left one door open: "which results are offered for sampling" was fully deferred to slice design, and escalation-triggered offering — the tempting cheapest-n choice — would blind every escalated review, strip the judge's assistive value, and bias the sample. Closed that door plus two adjacent ones. Amended 320-arch and 320-slices:

- **Blindness scoped:** attaches only to designated calibration samples, never the escalated-gate review flow. Reviewer-at-gate and calibration-sampler are distinct roles; an escalated verdict (formed after seeing judge output) is anchored and inadmissible as blind agreement data. Escalation may *enqueue* a sample; it is never itself blinded.
- **New arch principle — sampling is pull-based, budgeted, never blocking:** samples queue for the operator to drain at convenience; no pipeline/gate/dispatch waits on a sample verdict; skip is free; human load is a configured budget (rate/ceiling), not emergent from pipeline volume. Slow evidence → slower graduation + honest floor refusal, never more interruptions.
- **Division of labor named:** dispersion + trend (321) and the audit oracle are the human-free *continuous* monitors maintaining graduated judges' standing between samples; rising dispersion flags where the scarce human budget is spent.
- **Template-churn caveat:** version-keying means frequent template edits can perpetually reset n and starve graduation; minor-revision inheritance vs. full re-calibration flagged as a 322 slice-design question.
- Slice 320 gains matching success criteria (blindness scoping, non-blocking capture, budget respected); open questions gain budget representation and churn items.

### Slice Plan 320: Judge Calibration & Quality Metrology — Phase 3 Complete

**Phase 3 complete.** Created `user/architecture/320-slices.judge-calibration-quality-metrology.md` from the reviewed 320-arch. `cf` Slice Plan field already registered as `320-slices.judge-calibration-quality-metrology`.

**Structure: five slices, keystone-first, two oracles on one spine.** Kept the architecture's anticipated-slice count and boundaries — the load-bearing decisions were already resolved in arch, so no slice reopens them.
- **(320) Metrology Data Layer & Sample Capture (keystone, High, 4/5)** — the queryable/joinable user-level store keyed on stable explicit project identity (not a path, no 280 dependency) plus the blind inline human-sample capture surface (judge output withheld until the human commits). Done alone, no reporting, per the architecture.
- **(321) Agreement & Dispersion Reporting (Medium, 3/5)** — human-oracle headline: judge-vs-human agreement + judge-vs-judge dispersion, per artifact level / judge configuration, every figure carrying its n; dispersion sourced from 300's multi-sample (no 180 `fan_out` dependency); refuses to pool across incompatible judge configs.
- **(322) Calibration-to-Threshold Feedback (Medium, 3/5)** — evidence-floored path to 300's threshold config; graduation-is-not-a-one-way-door forced residual sampling; the (template,model)↔(template,step) mismatch inherited as a config-time model+threshold pairing; resolves the version-keying tension (coordinated 300 write-path field vs. content-hash fallback).
- **(323) Tech-Debt-Audit Baseline Harness (Medium, 3/5)** — cross-project audit baseline, normalized findings, and the audit's own run-to-run noise floor measured first (variance-before-baseline).
- **(324) Pre-Emption Prompt & Delta Measurement (Medium, 3/5)** — dispatch-side generated static prompt fragment flowing down-only into dispatch config (dispatch never queries the store at runtime); before/after delta reported against the noise floor as a directional signal, not causal proof; ships only after 323.

**Two ordering constraints honored explicitly.** *Variance, then baseline, then intervention* forces the audit oracle into two slices (323 measures the floor, 324 intervenes after). The keystone is done alone — reporting is a separate slice so storage/join/ergonomics de-risk in isolation. The version-keying tension is resolved in 322 (where the calibration recommendation depends on it), not the keystone; 321 already enforces non-blending on whatever key is present.

**Future Work seeded:** 300 judge-result version/hash field (if 322 takes the preferred path), 280-store convergence (not a dependency), general 180 `fan_out` for dispersion (boundary made explicit, not assumed).

**Pending.** Phase 4 (slice design) not started. Frontmatter `status: not_started`.

### Housekeeping: reconcile `tech-debt-analyze` → `tech-debt-audit` skill-name drift

Surfaced by 320 arch review F011. The shipped analysis-pack skill is `tech-debt-audit` everywhere load-bearing (frontmatter `name:`, file `commands/analysis/tech-debt-audit.md`, live dispatch `/analysis:tech-debt-audit`), but the 340-band planning docs called it `tech-debt-analyze` — a name that never matched what shipped. Blast radius was documentation-only (zero occurrences in `src/` or `commands/`). Fixed all live docs to the canonical name: `340-arch` (4 spots, was also self-inconsistent with its own line 81), `340-slices` (3 spots), `001-initiative-plan` (2 spots in the 340 entry), `340-slice.command-surface-spike` (1 spot, the spike's stub-dispatcher example — skill name only; left the illustrative `tech-debt` dispatch token as prototyped). Historical review artifacts (342/320 reviews) left as-is — they are point-in-time records. Trimmed 320-arch's Related Work note now that 340-arch is correct. No code change.

### Architecture 320: Judge Calibration & Quality Metrology — Design Complete

**Phase 2 complete.** Created `user/architecture/320-arch.judge-calibration-quality-metrology.md` from the initiative-plan entry 10 charter; `cf` arch field already registered as 320. Commit: `39b5f9d` (docs: add 320-arch judge calibration and quality metrology).

**What the component is.** The measurement layer 300 explicitly deferred: judge-vs-human agreement and judge-vs-judge dispersion measured against a **sampled human oracle** (no curated dataset), computed **per artifact level**, feeding 300's escalate-vs-auto-gate threshold config. Second oracle with the same metrology shape: a cross-project **tech-debt-audit code-quality baseline** (skill shipped in 340's analysis pack), with the dispatch-side pre-emption prompt as its first measurable customer.

**Key design decisions recorded in the doc:**
- Principles: human sampled-not-resident (capture ergonomics are first-class), read-side over 300's write path (no judging-path changes), per-artifact-level calibration only (no blended global accuracy number), baseline-before-intervention ordering, honest small-n statistics (every report carries its sample size; minimum-evidence floor before recommending threshold loosening).
- Metrology records are keyed by judge configuration (template identity/version, model) so template/model changes don't silently blend incompatible measurements.
- Cross-project aggregation is a new persistence requirement (300's persistence is per-run/per-project); relation to the not-started 280 shared artifact store flagged as a leading slice-design decision, not assumed.
- Non-goals: no curated dataset, no changes to the judging path, no automatic threshold mutation (calibration informs, operator decides), no general observability platform.
- Anticipated slices (exploratory): metrology data layer & sample capture (keystone), agreement/dispersion reporting, calibration-to-threshold feedback, tech-debt-audit baseline harness, pre-emption prompt & delta measurement.

**Pending.** Phase 3 (slice planning, `320-slices.*`) not started. Frontmatter `status: not_started` matches initiative-plan entry status.

**Arch review response (same day).** Review `320-review.arch.judge-calibration-quality-metrology.md` (claude-fable-5, verdict CONCERNS) returned 8 concerns + 3 notes; all 11 addressed in the arch doc. Every factual claim verified against source first. Substantive additions: two new principles — *Graduation is not a one-way door* (forced residual sampling of auto-gated results survives graduation, F002) and *Blind capture, not anchored* (judge output withheld until the human commits an independent verdict, F003); principle *Baseline before intervention* rewritten to *Variance, then baseline, then intervention* (measure the audit's run-to-run noise floor before any delta, F008); new consideration committing pre-emption data to flow **down** as a generated static prompt fragment — dispatch never queries the metrology store at runtime (F007, avoids a 140→320 dependency inversion); the metrology-store consideration now fixes three load-bearing commitments — stable explicit project identity, user-level/central locality, no hard 280 dependency (F006); the template-version consideration now names the read-side/no-version-field unsatisfiability and resolves it (coordinated 300 write-path field preferred, capture-time content-hash fallback, F001). Corrections: `fan_out` re-attributed from 140 to 180 and dispersion scoped to 300's multi-sample only, preserving the plan's "Independent of 180" (F004); `340` added to frontmatter `dependencies` (F005). Notes F009 (per-model calibration resolves to operator config-time choice) and F010 (shared "spine" not "one report path") folded in. **F011 verified inverted:** the shipped skill is genuinely `tech-debt-audit` (frontmatter name, file, live `/analysis:tech-debt-audit` dispatch); `tech-debt-analyze` is 340-arch's stale drift — kept the correct name, flagged 340-arch for reconciliation rather than adopting the wrong identifier. Response recorded in the review file. Dependencies `[100, 140, 300, 340]` all complete.

### Slice 304: Gate Composition — Implementation Complete

**Phase 6 complete.** Branch `304-slice.gate-composition` created from `main` (integration branch unset). All 13 tasks (T1–T13, including T2c/T4c/T7b/T8c) implemented, tested, and verified in dependency order across four bisectable commits. Initiative 300 (eval-actions-llm-as-judge-scoring) is now fully closed — slices 300–304 are all complete.

**T1–T2c: pure reduction core.** `src/squadron/pipeline/actions/gate.py` defines the severity ranking once as an `IntEnum` (`PASS < CONCERNS < FAIL < UNKNOWN`, `UNKNOWN` highest/most-severe) and a pure `reduce_verdicts(a, b) -> str` that normalizes `None → "UNKNOWN"` before ranking and returns `max(severity_a, severity_b).name`. `Provenance.COMPOSED` added to the existing `Provenance` `StrEnum` in `actions/judge.py`. 27 tests cover the full 4×4 cross-product (all 16 pairs incl. the 4 diagonal ties) plus all `None`-leg cases.

**T3–T4c: the 140-adjacent executor touch, confirmed pure and signed off.** Added `ActionContext.step_outputs: dict[str, ActionResult]` (`models.py`) — a step-name-keyed view populated in `execute_pipeline`'s top-level loop (`executor.py`), mirroring exactly how `prior_outputs` itself is accumulated, using the existing `_last_with_verdict` helper to pick each step's most recent verdict-bearing result. Required threading the new field through all 5 nested step-execution paths (`_execute_step_once`, `_execute_loop_step`, `_execute_loop_body`, `_execute_each_step`, `_execute_fan_out_step`) and their 9 call sites — more mechanical surface area than the design's grounding notes implied (they named one `ActionContext` construction site; the executor's loop/each/fan_out helpers each pass `prior_outputs` through independently). **140 sign-off obtained from the Project Manager before implementing**, per the STOP-gate: confirmed as a pure additive read view, no change to `prior_outputs` semantics, no checkpoint code touched. Verified: the full pre-existing pipeline suite (999 tests) passed unmodified both before and after the change, and a dedicated regression test (`TestStepOutputsRegression`) pins that the `review-0` key-collision behavior in `prior_outputs` is byte-for-byte unchanged. The sign-off is recorded in the T4c commit body per the task's requirement.

**T5–T8c: `gate` action + step + loader validation.** `GateAction` resolves `judge_from`/`review_from` (step names) against `context.step_outputs`, reduces via `reduce_verdicts`, and returns `provenance=COMPOSED` with both raw verdicts (and scores/criteria, unreduced) on `metadata`. An unresolved source step or a source with `verdict=None` logs WARNING+ and normalizes to `UNKNOWN` — no silent path. `GateStepType` expands to `[gate]` or `[gate, checkpoint]` (mirroring `ReviewStepType`), with its own `validate()` checking only presence/type of its own config, per the `StepType.validate(config)` protocol's own-config-only scope. **F005 (loader cross-step check):** added `_validate_gate_references` in `loader.py`'s `validate_pipeline`, tracking `prior_step_names` across the existing step loop and requiring `judge_from`/`review_from` to each name a step that appears *earlier* — a misspelled or forward-referencing name now fails at load time, distinct from the action's execute-time `UNKNOWN` fallback. 28 additional tests (action + step type + loader validation, incl. nonexistent-step, later-step, and param-placeholder-skip cases).

**T9–T11: example pipeline, end-to-end checkpoint-driving tests, and the escalation boundary.** `compose-gate-example.yaml` composes a `judge.slice-vs-arch` leg and a `slice`-template review leg into one `gate` step with `checkpoint: on-concerns` — validates clean via `sq run compose-gate-example --validate`. `TestDrivesCheckpoint` proves the *reduced* verdict, not either raw leg, fires the checkpoint: (PASS, CONCERNS) fires, (PASS, PASS) doesn't, (UNKNOWN, PASS) fires (no-silent-pass), and — closing the F003 tasks-review gap — a `None`-leg case runs the full normalize→reduce→checkpoint-fires→WARNING-logged path end-to-end, not just at the action level. `test_boundary_requires_140` encodes escalation condition (3) directly: two gate results with identical reduced verdicts (`FAIL`) but opposite raw legs (judge-FAIL-review-PASS vs. judge-PASS-review-FAIL) prove the checkpoint's read path (`_find_review_verdict`, which reads only `.verdict`) cannot distinguish *which* leg failed — that requires extending the checkpoint itself (option b), which this slice does not do.

**T12: authoring guide.** Added "Composing a judge and a review at one gate" to `docs/PIPELINES.md` as a sibling to 303's "Judge-Gated Cycles" section (cross-linked both ways), plus a `### gate` step-type entry (fields table) and Action Type Catalog row. Documents the composition shape, the most-severe-wins rule with `UNKNOWN`-most-severe and `None → UNKNOWN` rationale, the same-step checkpoint requirement, the 140 boundary (with the "which leg failed" example), and the gate-vs-fan-in distinction so authors don't reach for a gate where a fan-in reducer belongs.

**T13: full-suite gate.** `uv run pytest` (2198 passed, 2 pre-existing/unrelated skips), `uv run pyright` (0 errors, strict), `uv run ruff check` (clean) — all green. Verification Walkthrough re-run against actual output and corrected in the slice design: two of the design's draft `-k` filter strings (`drives_checkpoint`, `unknown_dominates`) didn't match the actual test names/classes written in Phase 6 (`TestDrivesCheckpoint`, `test_judge_unknown_review_pass_fires`) — corrected in place with a caveat note, all 7 walkthrough steps now reproducible verbatim.

**Code review (`moonshotai/kimi-k2.7-code`, CONCERNS) addressed.** 2 concerns, 3 passes, 1 note. **F001:** `GateStepType` validated and forwarded a `policy` field that `GateAction.execute` silently ignored — fixed by having the action read `context.params["policy"]`, fall back to the default with a WARNING+ log on an unrecognized value, and record the resolved policy on the result's `metadata` for auditability. The valid-policy set is now centralized once in `actions/gate.py` (`VALID_GATE_POLICIES`/`DEFAULT_GATE_POLICY`, public rather than private so `steps/gate.py` can import it under pyright strict) instead of duplicated across both files. **F002:** the ~720-line `tests/pipeline/test_gate.py` (over the project's ~300-line guideline) was split into four focused files by concern — `test_gate_reduce.py` (pure reduction core), `test_gate_action.py` (GateAction, now including 3 new policy tests), `test_gate_step.py` (GateStepType + loader cross-step validation), `test_gate_executor.py` (step_outputs read surface, end-to-end checkpoint-driving, escalation boundary). **F006** (note, addressed): added an inline comment on `GateAction.execute`'s `success=True` explaining it reports execution health, not verdict outcome, mirroring `CheckpointAction`. F003–F005 were PASS (fail-closed ranking, additive `step_outputs`, load-time cross-step validation) — no change needed. Full suite re-verified green after the split (2201 passed, up from 2198 net of the 3 new tests).

**Housekeeping:** removed a pre-existing stray line of unrelated content (referencing a different slice, "162") that had contaminated the top of `304-slice.gate-composition.md` since its Phase-4 creation commit, ahead of the frontmatter delimiter — confirmed with the PM before removing, out of caution since it predated this session. Slice design and task file frontmatter both updated to `status: complete`, `dateUpdated: 20260717`; slice-plan checkbox (#5, gate composition) in `300-slices.eval-actions-llm-as-judge-scoring.md` checked off, and the plan's own frontmatter status moved `in_progress` → `complete` (confirmed with PM — all 5 core slices done, remaining items are the separate, explicitly-deferred Future Work section). Future Work item 3 (checkpoint multi-verdict support, 140) remains legitimately unscheduled — the escalation boundary never fired, so option (a) shipped as sufficient and (b) stays future work, not superseded. A `workflow_check --fix` pass also corrected unrelated pre-existing drift project-wide (confirmed with PM before keeping): slice 344's checkbox/frontmatter, and architecture status fields for 140, 300, and 900 — none touch slice 304's own scope.

**Initiative 300 status:** all five slices (300 scoring foundation, 301 threshold enforcement, 302 judge templates, 303 judge-gated cycles, 304 gate composition) are complete; the slice plan's frontmatter now reflects `status: complete`. The one deferred coordination — Future Work 3, checkpoint multi-verdict support — remains a 140 dependency to be picked up only if a future required case needs it.

---

## 20260716 (2)

### Slice 304: Gate Composition — Task Breakdown Complete

**Phase 5 complete.** Created `project-documents/user/tasks/304-tasks.gate-composition.md` (312 lines, within target) from the review-addressed design. 13 tasks in dependency order, each impl task followed immediately by its test (test-with pattern): reduction core (T1–T2) → executor read surface (T3–T4) → gate action (T5–T6) → gate step (T7–T8) → example pipeline + drives-checkpoint + boundary tests (T9–T11) → authoring guide (T12) → commit (T13).

**Grounded every code anchor against on-disk source before writing tasks, so the junior AI does not re-derive them.** Verified and carried into the task file's grounding notes: the `Action`/`StepType` protocol method sets (`actions/protocol.py`, `steps/protocol.py` — both confirmed present); `register_action`/`register_step_type` signatures; the `ActionType`/`StepTypeName`/`Provenance` `StrEnum`s that each need a new `GATE`/`COMPOSED` member; and — the load-bearing one — that `StepResult` (`executor.py:244`) carries `step_name` + `action_results` and the executor already accumulates a `step_results` list, but `ActionContext` (`models.py:54`) exposes **only** the lossy action-keyed `prior_outputs`, no step-keyed view. That gap is exactly what T3 fills.

**T3 (the F002-flagged executor touch) is written as a STOP-gated task, not a normal one.** It carries an explicit stop-gate: the step-keyed read surface must be a *pure additive* field on `ActionContext` populated from the already-accumulated `step_results`, changing no `prior_outputs` semantics and touching no checkpoint code, and it needs up-front 140 sign-off because `prior_outputs` is 140-owned. If a pure addition proves impossible, the task says STOP and escalate to option (b) per the design's escalation boundary — the task cannot silently absorb a checkpoint change. This mirrors the F002 resolution: the executor touch is 140-adjacent, not in-scope-by-default.

**F001 (None-verdict) is pinned across three tasks:** `reduce_verdicts` normalizes `None → UNKNOWN` before ranking (T1), the 4×4 cross-product plus all `None` cases are required tests (T2), and the gate action's WARNING+ log on a `None`/unresolved leg is asserted via `caplog` (T6). The escalation-to-140 boundary test (T11) is a first-class required task encoding boundary condition (3) — a policy needing the checkpoint to see both raw verdicts distinctly is asserted *not* expressible via the single reduced gate and documented as a 140 concern.

**Real-path corrections while grounding:** the authoring-guide target is `docs/PIPELINES.md` (slice 152's guide, where 303's `Judge-Gated Cycles` section already lives) — T12 names it and cross-links, rather than pointing at a vague "same doc as 303." Verification section maps each task back to the slice's FR1–FR4 and F001/F002 so the coverage is auditable.

**Task-breakdown review (`moonshotai/kimi-k2.6`, CONCERNS) addressed — 2 PASS (test-with pattern, F002 STOP-gate scoping), 3 concerns resolved.** **F003 (no end-to-end `None`→checkpoint test):** added a `None`-leg case to T10 — normalizes to `UNKNOWN`, reduces to `UNKNOWN`, fires the same-step checkpoint, WARNING+ logged on that path; closes the T6 (action-level) ↔ T10 (checkpoint firing) gap. **F004 (commits batched at end):** distributed commits across the four deliverables — T2c (reduction), T4c (read surface, with mandatory 140-sign-off note in the body), T8c (gate action+step+loader validation), T13 (example+docs+full-suite gate); branch now reads as four bisectable commits. **F005 (gate step omits prior-step existence check):** the fix was right but its locus was not — `StepType.validate(config)` sees only its own config (verified `steps/protocol.py`), so it *cannot* check sibling steps; the cross-reference belongs in the loader's `validate_pipeline` (`loader.py:147`), which iterates all steps and already validates review-template refs the same way (`loader.py:210`). Added T7b (loader validates `judge_from`/`review_from` name real *prior* steps, fail-fast at load) and clarified T7's own `validate` as own-config-only; T8 asserts the load-time failure distinct from T5's execute-time `UNKNOWN` defense-in-depth. Task file 314 → 398 lines (within target). Review dispositioned per-finding; `reviewsAddressed` added to task frontmatter.

**Next:** Phase 6 (implementation) for slice 304 — create branch `304-slice.gate-composition` from the target (integration branch unset → `main`), start T1. Design and tasks are both review-addressed; the one open coordination is the T3 140 sign-off, to be obtained at implementation (T4c holds the commit until it lands).

---

## 20260716

### Slice 304: Gate Composition — Slice Design Complete

**Phase 4 complete.** Created `project-documents/user/slices/304-slice.gate-composition.md` from the slice-plan entry (#5) in `300-slices.eval-actions-llm-as-judge-scoring.md`. This is the initiative's integration slice: resolve how a judge result and a standard review result compose into a single checkpoint gate. The architecture prescribed the *decision procedure* (prefer option a, upstream reduction, additive; escalate option b, checkpoint multi-verdict, as a 140 dependency if a is insufficient) but not the answer. The design **commits to option (a)** and proves it sufficient, grounded against the real machinery rather than the architecture's prose.

**The decisive constraint was verified in code, not assumed.** The checkpoint is single-verdict-per-step for a *mechanical* reason: (1) the executor accumulates results as `prior_outputs[f"{action_type}-{idx}"]` with `idx` resetting per step (`executor.py:880-883`), and a `review` step expands to exactly one review action (`steps/review.py:69-76`) — so *every* standalone review step, judge or standard, writes the same key `review-0` and later steps **overwrite** earlier ones in the global map; (2) `_find_review_verdict` returns the *first* non-`None` verdict in reverse insertion order (`checkpoint.py:28-37`). Both a judge result (threshold-derived verdict) and a standard review (model verdict) carry a non-`None` verdict, so the checkpoint picks exactly one — whichever ran last — and structurally cannot combine two separately-stepped results. This is precisely why combining two *separate* steps' verdicts is option (b)/140 territory: it requires the checkpoint to look past a single key. Option (a) sidesteps it by reducing to one verdict *upstream*, in the same step as the checkpoint.

**Design: a `gate` reduce action + `gate` step (both additive registrations).** The gate step names its two source steps (`judge_from` / `review_from`), the gate action reduces their verdicts by a documented **most-severe-wins** rule (`UNKNOWN > FAIL > CONCERNS > PASS`, `UNKNOWN` ranked most severe deliberately to preserve the no-silent-pass NFR — a broken judge leg must dominate a passing review leg), and the gate step expands to `[gate, checkpoint?]` so the reduced verdict and the checkpoint land in the **same step** — the one place a checkpoint can read the gate's output via the unchanged `_find_review_verdict`. New `Provenance.COMPOSED` value; both raw verdicts preserved on the gate result's metadata for auditability. `_find_review_verdict` and the checkpoint are **not modified** — that is the whole point of option (a), and any need to modify them is the escalation signal.

**The escalation boundary (a → b) is a stated, checkable rule, not a mid-Phase-6 judgment call.** Option (a) is declared insufficient and (b) escalated to 140 iff, in implementation: (1) exposing per-step results to the gate action can't be done as a pure additive read surface without altering the checkpoint's single-verdict contract; (2) a required case needs the checkpoint itself (not an upstream action) to weigh two verdicts; or (3) the reduction can't be a pure function of the two verdicts because a policy needs the checkpoint to branch on *which* leg produced the severity. None holding → (a) stands, 140 untouched (the default, shipped outcome). The required **escalation-to-140 boundary test** encodes condition (3): it asserts a policy needing both raw verdicts seen distinctly is *not* expressible via the single reduced gate and is documented as a 140 concern — so the slice recognizes its own edge rather than silently overreaching.

**The one additive executor touch is named as the risk.** The gate needs source results keyed by *step*, which the lossy action-keyed `prior_outputs` does not preserve (both legs clobbered `review-0`). Adding a step-keyed read view is the single place the slice reaches into the executor; if it can't be a pure read-surface addition, the escalation boundary fires. This is the architecture's anticipated edge, handled by the prescribed escalation.

**Verification Walkthrough is a Phase-4 draft** (marked as such) — the 4×4 reduction cross-product, drives-checkpoint, unknown-dominates, boundary-requires-140, and non-composed-unchanged tests are specified; actual commands/output to be confirmed in Phase 6.

**Two refinements after PM review.** (1) **Tie behavior made explicit:** two same-severity legs (e.g. `CONCERNS`+`CONCERNS`) reduce to that shared value — most-severe-wins is idempotent on equal ranks, so there is no tie-break to decide (the reduction returns a *rank*, not a chosen *leg*); the 4×4 cross-product's four diagonal ties are now called out as required test cases, and the stale "scores for tie-context" phrasing was removed (ties need no score context). Raw per-leg verdicts stay on `metadata`, so a same-rank tie remains auditable. (2) **Fan-out/fan-in relationship pinned as a distinct-but-co-evolving concern.** The codebase already has a `FanInReducer` protocol + registry (`intelligence/fan_in/reducers.py`, slice 182; `collect`/`first_pass`, with `merge_findings`/`unanimous` planned in 189). The gate reduces **2 heterogeneous** judgments of one artifact (judge verdict *and* review verdict); fan-in converges **N homogeneous** samples (same review across many models). Orthogonal today — multi-sample judging (300 FW1) is explicitly a *fan-in* job, not a gate one, so the gate grows no sample count. But both are "reduce a set of results to one verdict," and the gate's most-severe rule is arguably a special case of a `FanInReducer`; a comparison table and an evolution note are now in the design flagging a likely future unification (gate-as-reducer) as *unscheduled direction*, so a later slice unifies them knowingly rather than by accident. Not attempted now — no caller, and forcing the gate through the fan-out branch model would add complexity nothing needs (project rule).

**Slice-design review (`z-ai/glm-5.2`, CONCERNS) addressed — both concerns dispositioned in the design.** **F001 (missing `None`-verdict failure mode):** the reduction now normalizes a `None` source verdict to `UNKNOWN` *before* ranking — fail-closed, deliberately diverging from `_find_review_verdict`'s skip-`None` behavior, because a gate must not let a verdict-less source vanish and silently advance the other leg. Added the rule, a failure-mode-table row, a required WARNING+-logged unit test, and prose distinguishing it from the *authoring-time* missing-source-name case (which stays fail-fast validation). **F002 (executor read-surface boundary ambiguity):** re-framed the per-step read-surface touch from "in-scope unless downstream escalation fires" to **140-adjacent, requiring up-front 140 sign-off regardless** (`prior_outputs` is 140-owned) — two explicit outcomes (confirmed pure addition → proceed with sign-off, expected default; can't stay pure → escalate to (b), condition 1), with the slice explicitly disclaiming unilateral authority to modify executor result accumulation under 300's additive banner. F003 was a PASS (architectural alignment), no change. Review file updated with per-finding `resolution:` and a Resolution section; `reviewsAddressed` added to the design frontmatter. Verdict left `CONCERNS` as the historical record; a Phase-6 re-review should confirm the commitments hold in code.

**Slice status:** design is `not-started` (Phase 4 artifact exists, review-addressed; implementation not begun). This slice completes the 300 initiative's gating story once implemented — 300/301/302/303 are all `complete`.

**Next:** Phase 5 (task breakdown) for slice 304, or PM direction. No branch created (planning work commits to the current target per the git rules).

---

## 20260710

### Slice 909: Pipeline Phase-Step Correctness — Implementation Complete

**Phase 6 complete.** All 18 tasks implemented across three commits, C → B → A: `85f2e03` (Part C, review-code scope guard, #17), `ac01838` (Part B, review frontmatter project name, #16), `49b8522` (Part A, dispatch artifact post-condition, #15). Full suite passes (2101 passed, 2 skipped), ruff clean, pyright clean.

**Part A surfaced a real pre-existing bug while wiring T12/T13, not a design flaw.** `PhaseStepType.expand()` (`steps/phase.py`) hardcoded a bare `"{slice}"` placeholder into the `cf-op(set_slice)` and `review` action tuples. That's correct for ordinary single-slice pipelines, but for `each`-loop pipelines (`design-batch.yaml`, `app.yaml`) the loop's `as: slice` binding puts the *whole slice record* into that variable — so `"{slice}"` resolved to a stringified Python dict instead of the numeric index. This silently corrupted `cf-op(set_slice)` (caught downstream as a `ContextForgeError`) and crashed the `review` action's `int(str(slice_param))` call outright — the identical crash my new post-condition hit immediately, since it reads `slice` on every dispatch rather than only when a review happens to run. Traced this live with the PM (three rounds of investigate-then-report, no guessing) before fixing: root cause was `expand()` receiving the step's *unresolved* config and never reading its own `slice:` key (both `design-batch.yaml` and `app.yaml` already wrote `slice: "{slice.index}"`, correctly anticipating this — it just was never consulted). Fix: `expand()` now uses `cfg.get("slice", "{slice}")` so a step-level override flows into every action tuple that references a slice, resolved later via the pre-existing (and already-correct) dotted-placeholder mechanism. Zero regression for the common case (no `slice` key in step config → identical `"{slice}"` fallback as before).

**Also fixed while chasing test fallout: `execute_pipeline()` never accepted a `runs_dir` parameter.** Any internal `StateManager()` call (the pre-existing SDK-resume-seed code, and my new post-condition) silently read from the *default* runs directory regardless of what the caller configured — a second latent bug, invisible before because the SDK-resume path is rarely hit in tests and never combined with an artifact check. Threaded `runs_dir` through `execute_pipeline` and its loop/each/fan-out helpers; updated the CLI (`run.py`) and 12 pre-existing integration tests across 4 files that broke as a direct, expected consequence of the new post-condition (their mocked dispatch actions never wrote real files, and their `cf_client` mocks couldn't resolve real slices — both now genuinely required).

**A real `sq review code 909 -v` run (not fabricated — this is the fixed Part C path) found four legitimate issues, addressed before closing the slice:** an unhandled `ValueError` in the post-condition's `int()` conversion (now caught, tested with a new case simulating an unresolved `"{slice.index}"` placeholder reaching the check); a swallowed exception in `review_arch`'s project-name resolution with no logging (now logged at WARNING per the exception-handling convention); a DRY violation — `_phase_artifact_cf_client`/`_artifact_writing_action` duplicated verbatim across 4 test files (extracted to `tests/pipeline/conftest.py`); and a scattered `"project-documents/user/tasks/"` magic-string prefix across 3 source files (extracted to a new `TASKS_DIR` constant in `squadron.review.persistence`). One flagged finding (a supposedly misleading error message in `review_code`'s scope guard) was investigated and determined to be a false positive — the code path it described is unreachable, since `_resolve_slice_number` already exits earlier with its own correct "no slice with index N" message.

**Verification Walkthrough updated in the slice design** with actual commands run and real output (not the placeholder command text from Phase 4) — see `909-slice.pipeline-phase-step-correctness.md`. Part A's live-agent repro was not re-run interactively (would require a real dispatch); the automated `TestDispatchArtifactPostCondition` suite (9 cases) exercises the identical code path with mocked dispatch actions standing in, which is documented as the verification tier used, with an explicit note on what a fully-live re-verification would look like.

**Next:** merge slice 909 to main; close issues #15, #16, #17. Then resume slice 303 Phase 5 past its original failure point — the fix that unblocks it (Part A's post-condition) is now in place.

---

## 20260709 (2)

### Slice 909: Pipeline Phase-Step Correctness — Task Breakdown Complete

**Phase 5 complete.** Created `project-documents/user/tasks/909-tasks.pipeline-phase-step-correctness.md` (18 tasks after task review, 274 lines) from the review-addressed design. Tasks ordered C → B → A per the design's cheapest-first sequencing, with test-with pairing throughout and a commit task closing each part.

**Grounding a trace before writing Part A tasks changed Part A's mechanics — and the design.** Before authoring tasks I traced the executor to answer "where does the artifact post-condition actually fire?" The design said "the phase step verifies after dispatch completes." The trace proved that's not mechanically possible: `PhaseStepType.expand()` (`steps/phase.py:96`) returns a flat action list and is **never consulted again** — the phase step has no post-expansion runtime hook. The only seam that runs right after a phase step's `dispatch` action is the per-action tail of `_execute_step_once` (`executor.py` ~898-943). So the honest split is: `expected_artifact_kind` is a **property on `PhaseStepType`** (declaration of what the phase owns — legitimately phase-step knowledge), but the **check runs in the executor**, keyed on `action_type == "dispatch"`, reading that property. Reconciled the design accordingly (Approach, chosen-home decision, Part A files list now name `executor.py` as a modified file, not just `phase.py`) so the two documents don't contradict.

**Two more grounded facts the tasks now carry (no guessing left for the junior AI):**
- **Run-start timestamp** for the stale-artifact mtime check is NOT on `ActionContext`; it lives in `RunState.started_at` (`state.py:126`), loadable via `StateManager().load(run_id).started_at` (precedent: `executor.py:603-606`). T12 makes this an explicit task.
- **Expected-path resolution** reuses `resolve_slice_info(context.cf_client, int(slice)).task_files` / `.design_file` — the exact call the review action already makes at `review.py:264`; `ActionContext` exposes `cwd`, `params["slice"]`, and `cf_client` (a `CfClientProtocol` with the three methods `resolve_slice_info` needs).

**Test-with coverage of the failure-mode table:** T14 enumerates all six Part A cases (present+fresh → pass, absent → fail, stale-mtime → fail, unresolvable-path → fail+WARNING, OSError → fail+log, `implement`/kind-`None` → skipped) plus a "generic dispatch unaffected" assertion. Part B's T5/T8 use real-shaped `cf get --json` fixtures (must include `name`) per the fixture-realism rule; Part C's T2 asserts the review client is **not called** for missing/malformed scope — proving the fabricated-review path is closed.

**Next:** Phase 6 (Implementation) for slice 909, not yet started. Then resume slice 303 Phase 5 past its original failure point.

---

## 20260709 (1)

### Slice 909: Pipeline Phase-Step Correctness — Slice Design Complete

**Phase 4 complete.** Created `project-documents/user/slices/909-slice.pipeline-phase-step-correctness.md` on branch `909-slice.pipeline-phase-step-correctness`, from the slice-plan entry in `900-slices.maintenance-and-refactoring.md`. Three independent bugs bundled into one maintenance slice (all surfaced during slice 303 planning; all share a silent-success failure signature): Part A dispatch artifact post-condition (#15, Medium), Part B review-frontmatter project literal (#16, Low), Part C review-code scope guard (#17, Medium).

**Grounded every anchor against on-disk code before designing, not the issue text alone:**
- **Part A:** confirmed `PhaseStepType.expand()` (`steps/phase.py:96`) emits a bare `("dispatch", {"model": model})` with **no** expected-output attached — so the memory-carried claim "the phase step knows the expected artifact" is *aspirational*: the phase→artifact mapping is conceptually known but materialized nowhere. Confirmed both dispatch success paths (`dispatch.py:198`, `:284`) return `success=True` with only a `_check_cli_error` text scan — no artifact post-condition. Design decision recorded: the post-condition belongs on `PhaseStepType` (which *does* know its phase produces an artifact), NOT in generic `DispatchAction` (must stay usable for bare dispatch steps that write nothing) — rejecting the generic-dispatch home on SRP grounds.
- **Part B:** verified live that `cf get --json` actually returns `"name": "squadron"` — so the fix has a real source, not a hallucinated one. Confirmed `ProjectInfo` (`context_forge.py:52`) has no `name` field, and that `resolve_slice_info` (`persistence.py:66`) *already* calls `get_project()` and merely discards everything but `arch_file`. Confirmed both review write paths (pipeline `save_review_result` → `actions/review.py:193`; CLI `persistence.py:268`) converge on `format_review_markdown`, so a single-point fix there satisfies interface-parity by construction. The `"project: squadron"` literal (`persistence.py:119`) sits directly beside `slice_name`/`slice_index`, which *are* already data-driven with an `"unknown"` fallback — the literal is the lone inconsistency.
- **Part C:** confirmed the guard at `review.py:641` is `if slice_number is not None and slice_number.isdigit()`, so a **malformed non-digit** argument falls through identically to a missing one — the fix must cover both, not just the missing case. Confirmed `review_slice`/`review_tasks` already hard-guard (`if not against: raise typer.Exit(code=1)` at `review.py:408-410`, `551-553`); Part C mirrors that exact pattern. Confirmed `--model glm51` → `z-ai/glm-5.1` resolves correctly and is NOT part of the bug.

**Cross-check carried from prior 303 work:** re-confirmed `StepTypeName` has no `COMMIT` member (design/tasks/implement/dispatch/compact/summary/review/each/fan_out/loop/devlog) — `commit` is an action, not a step type, consistent with the 303 loop-body finding.

**Suggested implementation order (in the design):** Part C (isolated CLI guard, mirrors existing pattern) → Part B (small data-threading through a verified source) → Part A (the genuine design work: post-condition home + unattended-question routing) last, so the two easy wins land regardless of Part A's depth.

**Next:** Phase 5 (Task Breakdown) for slice 909, not yet started. Then resume slice 303 Phase 5 past its original failure point.

---

## 20260705 (3)

### Slice 302: Design-Phase Judge Templates — Task Breakdown Complete

**Phase 5 complete.** Created `project-documents/user/tasks/302-tasks.design-phase-judge-templates.md` (11 tasks, 318 lines) from the reviewed slice design.

**Found and fixed a defect in the reviewed slice design before writing tasks:** the LLD's Success Criteria #3 and Verification Walkthrough step 3 assumed `sq review <judge-template-name>` was invokable from the CLI. Checked the actual CLI (`src/squadron/cli/commands/review.py`): `sq review` exposes exactly four Typer subcommands (`slice`/`arch`/`tasks`/`code`), each hardcoded to its own template name — there is no generic template-name argument. Judge templates are reachable today only via the pipeline `review` step (arbitrary `template:` config) or by calling `run_review_with_profile()` directly. Raised this to the PM (AskUserQuestion) rather than silently patching it; PM chose to drop the CLI claim from scope and correct the walkthrough to invoke the review client directly instead of a nonexistent CLI form. Both fixes committed to the slice design (`00d14ed`) before task breakdown began.

**Task structure:** author `judge-tasks-vs-slice.yaml` (T1) → test (T2) → author `judge-slice-vs-arch.yaml` (T3) → test (T4) → `TEMPLATE_INPUTS` registry entries for both (T5) → test, including updating the existing exact-keyset regression test (T6) → two tests for the failure modes newly introduced by this slice: rogue model-emitted verdict discarded (T7) and `TEMPLATE_INPUTS` resolution failure → `UNKNOWN` (T8), both confirming slice 301's existing enforcement/exception paths cover these cases with no new code → live-provider verification runs for each template (T9, T10), per the Risk Assessment's flagged prompt-quality-is-unverifiable-by-unit-test-alone risk → full validation gate (T11).

**Key discipline carried from the LLD:** judge templates reuse their standard counterpart's evaluation criteria verbatim — only the output contract changes (score+rationale+findings, no verdict). Default thresholds are deliberately different per template (`tasks-vs-slice`: 78/55; `slice-vs-arch`: 82/60, harder to auto-pass — weaker/more interpretive ground truth). `is_judge` and the `TEMPLATE_INPUTS` dict remain the only dispatch signals; the `judge.` name prefix is human-readable only (T11 greps the diff to confirm no naming-convention dispatch leaked in).

**Next:** Phase 6 (Implementation) for slice 302, not yet started.

---

## 20260705 (2)

### Slice 302: Design-Phase Judge Templates — Slice Design Complete

**Phase 4 complete.** Created `project-documents/user/slices/302-slice.design-phase-judge-templates.md` on planning branch `300-planning.design-phase-judge-templates`, following the slice plan entry in `300-slices.eval-actions-llm-as-judge-scoring.md`.

**Grounded in real code, not the plan's sketch alone:** read `templates/__init__.py` (YAML loader, `judge:`/`is_judge` from 301), `data/templates/{slice,tasks}.yaml` (the two standard templates being adapted), `template_inputs.py` (`TEMPLATE_INPUTS` registry — keyed by exact template name, so judge templates need their own entries), `parsers.py` (`_extract_score`/`_extract_criteria` — confirmed these are lenient markdown-line regexes, not a JSON/schema mechanism; `_extract_criteria`'s docstring explicitly flags "the structured-output/JSON variant is slice 302" — but no schema-enforcement mechanism exists in the engine, so the architecture's "structured-output constraint" is realized at the prompt level only), and `review_client.py` (500KB injection cap, unaffected by single-artifact judging).

**Design:** two new built-in template YAML files (`judge-slice-vs-arch.yaml`, `judge-tasks-vs-slice.yaml`) reusing each standard template's evaluation criteria verbatim, swapping the output contract to score+rationale+findings (via the existing `criteria:` block, no new parser target) and explicitly forbidding a verdict summary. Plus two new `TEMPLATE_INPUTS` entries reusing the existing `_design_file`/`_arch_file`/`_tasks_input` source functions unchanged. No engine, parser, or action changes — matches the architecture's "no new engine changes" commitment for this slice.

**Key decisions:** `judge.` name prefix is human-readable only, never a dispatch signal (`is_judge`/`judge:` block presence remains the only signal, per 301's precedent and the project's no-label-as-structure rule); differentiated default thresholds per ground-truth strength (`tasks-vs-slice`: pass_floor=78/concerns_floor=55, stronger ground truth; `slice-vs-arch`: pass_floor=82/concerns_floor=60, more interpretive, escalates more readily), consistent with the architecture's "bubble up the hard calls" principle; rejected a judge→standard template-name-stripping fallback in `TEMPLATE_INPUTS` as reintroducing naming-convention dispatch.

**Flagged risk:** prompt quality (does the model actually skip the verdict, does score-with-rationale reduce anchoring) is unverifiable by unit test alone — walkthrough step 3 and the Risk Assessment call for at least one live-provider run per template during implementation, not just mocked tests.

**Next:** Phase 5 (Task Breakdown) for slice 302, not yet started.

---

## 20260705 (1)

### Slice 301: Judge Enforcement Layer — Implementation Complete

**Phase 6 complete.** Implemented all 13 tasks from `301-tasks.judge-enforcement-layer.md` on branch `301-slice.judge-enforcement-layer` (created from `main` after merging the planning branch).

**What shipped:** `ReviewTemplate.judge: dict | None` + `is_judge` property (identified by `judge:` YAML block presence, not naming convention); new `pipeline/actions/judge.py` — `Provenance` StrEnum (`judge`/`review`), `JudgeThresholds` dataclass with `derive_verdict()`, `resolve_thresholds()` (per-key merge: step override → template default → module constant, conservative defaults `pass_floor=75.0`/`concerns_floor=50.0`), and `enforce_judge()` (pure function — logger passed in, never reads `result.verdict`, returns `UNKNOWN` + WARNING log for absent/out-of-range score); `judge:` step-level override passthrough in `ReviewStepType.expand()`; enforcement wired into `ReviewAction._review()` for the success path and into both of `execute()`'s exception handlers (via a best-effort template re-lookup so a judge-template failure still surfaces as `verdict="UNKNOWN", provenance="judge"` rather than silently passing).

**Caveat found during T11/T12:** existing `MagicMock(spec=ReviewTemplate)` test helpers in `test_review_action.py`/`test_review_action_integration.py` auto-mocked `is_judge` (a real `@property` on the spec) as a truthy `Mock`, silently turning every pre-existing review-action test into a "judge" test. Fixed by explicitly setting `mock.judge = None; mock.is_judge = False` on the shared helper. One pre-301 assertion (`provenance is None`) was updated to `"review"`, since this slice makes provenance non-`None` universally, not just for judges.

**Validation:** full suite 2066 passed/2 skipped, `pyright` 0 errors, `ruff check`/`format --check` clean, all 5 LLD walkthrough commands verified against real output, checkpoint `_TRIGGER_THRESHOLDS` confirmed to already include `UNKNOWN` in both `ON_CONCERNS`/`ON_FAIL` (no change needed), grep for naming-convention dispatch leaks found none.

**Slice 301 marked `complete`** in both its own slice-design frontmatter and the initiative slice-plan checklist. CHANGELOG entry added under `[Unreleased]`.

**Next:** slice 302 (Design-Phase Judge Templates) — first real judge YAML templates against this enforcement contract; no engine changes expected.

---

## 20260704 (1)

### Slice 301: Judge Enforcement Layer — Task Breakdown Complete

**Phase 5 complete.** Created `project-documents/user/tasks/301-tasks.judge-enforcement-layer.md` (225 lines, 13 tasks) from `301-slice.judge-enforcement-layer.md`.

**Task structure:** `ReviewTemplate.judge`/`is_judge` (T1–T2) → new `pipeline/actions/judge.py` module built incrementally — `Provenance`/`JudgeThresholds` (T3–T4), `resolve_thresholds` (T5–T6), `enforce_judge` (T7–T8) — each paired immediately with its test task → step-level `judge:` passthrough in `ReviewStepType.expand()` (T9–T10) → enforcement wired into `ReviewAction._review()` including the judge-exception path (T11–T12) → full validation gate (T13). Test-with pattern applied throughout; `judge.py`'s three functions are each independently tested before `ReviewAction` integration.

**Key discipline carried from the LLD:** `enforce_judge()` must stay a pure function (logger passed in, no global state); it never reads `result.verdict` — T8 explicitly tests a mismatched-verdict `ReviewResult` to prove score wins. `is_judge` is the only judge-detection signal (T13 greps the diff for naming-convention dispatch). Threshold resolution is per-key (step → template → module constant), not all-or-nothing.

**Branch:** `300-planning.judge-enforcement-layer` (Phase 5 planning work under initiative 300, per branch-naming rules).

**State:** Task breakdown ready for Project Manager approval. Next: Phase 6 implementation of slice 301 on branch `301-slice.judge-enforcement-layer`.

---

## 20260628 (3)

### Slice 344: Add `understand-anything` to Analysis Pack — Task Breakdown Complete

**Phase 5 complete.** Created `project-documents/user/tasks/344-tasks.add-understand-anything-to-analysis-pack.md` (147 lines, 18 tasks).

**Task structure:** Pre-work (branch + fork) → skill file (extract, adapt, verify, commit) → dispatcher update (3 targeted edits, verify, commit) → verification gate (test suite, live install/routing, required user real-repo run) → cleanup. Test-with pattern applied: install verification (T8) immediately follows skill file addition (T7); dispatcher verification (T13) immediately follows each dispatcher change.

**Key gate:** T17 (user runs skill on real repo) is a required merge gate — slice is not done until knowledge-graph build and incremental update are both confirmed live.

---

## 20260628 (2)

### Slice 344: Add `understand-anything` to Analysis Pack — Slice Design Complete

**Phase 4 complete.** Created `project-documents/user/slices/344-slice.add-understand-anything-to-analysis-pack.md`.

**Design summary:** Content-only slice (effort 1/5, no Python code changes). Forks `github:Egonex-AI/Understand-Anything` (MIT) to `ecorkran/understand-anything`, extracts `understand-anything-plugin/skills/understand/SKILL.md`, prepends attribution, audits and patches instructional `/understand` self-references → `/analysis:understand-anything`, adds as `commands/analysis/understand-anything.md`, and updates the `sq:analysis` dispatcher. The existing installer's `_install_prefix()` glob picks up the new file automatically. Verification requires a user-run knowledge-graph build on a real repo before merge.

---

## 20260628 (1)

### Slice 343: `sq skills uninstall` and `sq doctor` Integration — Implementation Complete

**Completed:** Phase 6 implementation of slice 343. All 17 tasks done; slice marked complete.

**What shipped:**
- `InstallReceipt` model + `SurfaceType` StrEnum in `skills/models.py`
- `skills/receipts.py` — `write_receipt` / `read_receipt` (TOML via `tomli-w`, already a dependency; manual-TOML fallback not needed). Malformed/invalid receipts raise `ValueError` with path context; absent receipt returns `None`.
- `installer.install_pack()` — new `receipts_dir` param; writes a receipt after every successful install. Receipt-write failure logs WARNING, never fails the install.
- `sq skills uninstall <pack>` — reads receipt, removes exactly the files install wrote, drops the prefix dir only when empty, deletes the receipt. Graceful exit-1 with message when no receipt. Added `--receipts-dir` to `install` too.
- `doctor_checks.check_skill_packs()` + `SECTION_SKILLS`; wired into `doctor.py` `_SECTION_ORDER` and `run_all_checks()`. Uninstalled packs → WARN with `sq skills install <name>` fix hint. Present in `--json`.

**Tests:** receipts round-trip, installer receipt-writing (incl. failure-does-not-fail-install), uninstall CLI round-trip / unrelated-file-preserved / not-installed / idempotent, `check_skill_packs` installed/not-installed/no-manifest, doctor section + JSON. Full suite: 2036 passed, 2 skipped. `pyright --strict` clean, `ruff` clean.

**Verification walkthrough:** all 8 steps executed against a live dev install; output recorded in the slice design. One caveat: `tomli-w` writes `files_written` as a multi-line TOML array (cosmetic; `read_receipt` parses both forms).

**Baseline fixes (pre-existing slice-342 debt surfaced by the strict gate):**
- `tests/cli/test_install_commands.py` — expected `analysis.md` (9 sq dispatch files, was 8).
- `tests/skills/test_manifest.py` — annotated `_manifest` packs param for strict pyright.
- `tests/skills/test_cli_skills.py` — `TestInstallLocalPack` now passes `--receipts-dir` so install tests don't write a real receipt into `~/.config/squadron/receipts/`.

**State:** Slice 343 complete. Next: slice 344 (add `understand-anything` to analysis pack), no dependency on 343.

---

## 20260626 (3)

### Slice 343: `sq skills uninstall` and `sq doctor` Integration — Task Breakdown Complete

**Completed:** Phase 5 task breakdown for slice 343.

**Artifact created:**
- `user/tasks/343-tasks.sq-skills-uninstall-and-sq-doctor-integration.md` — 17 tasks, 154 lines

**Task structure summary (test-with pattern):**
- T1: Branch + prereqs
- T2–T3: `InstallReceipt` model + tests
- T4–T5: `receipts.py` helpers (`write_receipt` / `read_receipt`) + tests
- T6–T7: Extend `installer.py` to write receipt + tests
- T8: Commit checkpoint — receipt infrastructure
- T9–T10: `uninstall` subcommand in `skills.py` + tests (round-trip, unrelated-file-preserved, graceful-failure cases)
- T11: Commit checkpoint — uninstall command
- T12–T13: `check_skill_packs()` + `SECTION_SKILLS` in `doctor_checks.py` + tests
- T14–T15: Wire into `doctor.py` + tests for output
- T16: Full validation pass + CLI smoke test (verification walkthrough)
- T17: Final commit + slice status updates

**State:** Ready for Phase 6 (implementation). No open questions.

---

## 20260626 (2)

### Slice 343: `sq skills uninstall` and `sq doctor` Integration — Design Complete

**Completed:** Phase 4 slice design for slice 343.

**Artifact created:**
- `user/slices/343-slice.sq-skills-uninstall-and-sq-doctor-integration.md`

**Key design decisions:**
- **Install receipt** — `installer.py` writes `~/.config/squadron/receipts/<pack>.toml` after each successful install. Contains `pack_name`, `surface`, `destination`, `files_written`. Uninstall reads this rather than re-resolving the source, making uninstall correct for all source types (including `github:`) and independent of source availability.
- **No orphan detection** — `sq doctor` reports only packs declared in the effective manifest; it does not scan for installed files absent from the manifest. Deferred indefinitely.
- **WARN (not MISSING) for uninstalled packs** — skill packs are optional; absence is notable but not blocking. Matches the pattern for `check_slash_commands`.
- **Injected `receipts_dir`** — both `install_pack` and `uninstall` accept `receipts_dir` as an optional parameter for testability; defaults to the standard path.

**New/modified files at implementation time:**
- `src/squadron/skills/models.py` — add `InstallReceipt` model
- `src/squadron/skills/installer.py` — write receipt after successful install
- `src/squadron/cli/commands/skills.py` — add `uninstall` subcommand
- `src/squadron/cli/commands/doctor_checks.py` — add `SECTION_SKILLS`, `check_skill_packs()`
- `src/squadron/cli/commands/doctor.py` — add `SECTION_SKILLS` to `_SECTION_ORDER`
- New tests in `tests/skills/` and `tests/cli/`

**State:** Slice 343 is ready for Phase 5 (task breakdown) and Phase 6 (implementation). No open design questions.

---

## 20260626 (1)

### Initiative 340 — Slice 342 (Analysis Pack Bundled): Complete

**Completed:** Phase 6 implementation of slice 342. Analysis pack is now shipped with squadron and installable in one command with no network access.

**Key changes:**
- `src/squadron/data/skills.toml` — shipped default manifest; declares the `analysis` pack with `source="bundled"`
- `src/squadron/skills/manifest.py` — `load_effective()` now loads the shipped default as a base layer (lowest priority); `SHIPPED_DEFAULT_ORIGIN = "default"` constant added; `_load_shipped_default()` helper added
- `src/squadron/skills/resolver.py` — `_resolve_bundled()` gains a dev-mode fallback: walks up from `src/squadron/` to find the project-root `commands/` directory, enabling `sq skills install analysis` in editable installs (wheel installs use `importlib.resources` directly)
- `commands/analysis/tech-debt-audit.md` — analysis skill file (previously created on planning branch)
- `commands/sq/analysis.md` — dispatcher: `/sq:analysis tech-debt-audit` routes to the tech-debt-audit skill
- Tests: `TestLoadEffectiveWithDefault` in `test_manifest.py`, `TestBundledAnalysisPack` in `test_installer.py`, updated `TestListNoManifest` in `test_cli_skills.py` (44 skills tests, all passing)

**Notable implementation decision:** The `force-include` rule maps `commands/` into the wheel as `squadron/commands/`, but editable installs expose `src/squadron/` with no `commands/` subdirectory. Added a dev fallback in `_resolve_bundled()` to resolve via the project root. This is correct behavior: the fallback only fires when `importlib.resources` doesn't find `squadron/commands/<pack>`, which only happens in editable installs.

**Artifacts updated:**
- `user/slices/342-slice.analysis-pack-bundled.md` — Verification Walkthrough updated with actual output and dev-mode caveat; status: complete
- `user/tasks/342-tasks.analysis-pack-bundled.md` — all tasks checked, status: complete
- `user/architecture/340-slices.skill-pack-infrastructure.md` — slice 342 entry checked `[x]`
- `CHANGELOG.md` — added analysis pack, `/sq:analysis` dispatcher, and shipped default manifest entries

**State:** Branch `342-slice.analysis-pack-bundled` is 3 commits ahead of `340-planning.skill-pack-infrastructure`. Ready for merge.

**Next step:** Merge `342-slice.analysis-pack-bundled` to main; then begin slice 343 (`sq skills uninstall` and `sq doctor` integration).

---

## 20260625 (5)

### Initiative 340 — Slice 340 (Command Surface Spike): Complete

**Completed:** Phase 6 implementation of the command surface spike.

**Decision:** Dispatch model is reliable. All four test cases passed — routing fired correctly, `<skill-args>` arrived intact, listing rendered cleanly, unknown-skill error was clear. Verdict: dispatch reliable.

**Artifacts updated:**
- `user/slices/340-slice.command-surface-spike-dispatch-vs-prefix.md` — Spike Results filled, status: complete
- `user/architecture/340-arch.skill-pack-infrastructure.md` — "Open dispatch question" principle and technical consideration updated to reflect adopted dispatch model
- `user/architecture/340-slices.skill-pack-infrastructure.md` — Slice 340 checked off

**Next step:** Slice 341 slice design — manifest format + `sq skills install/list` (supports both `dispatch_file` and `prefix` options per the spike outcome).

---

## 20260625 (4)

### Initiative 340 — Slice 340 (Command Surface Spike): Phase 5 Task Breakdown Complete

**Completed:** Task breakdown for the spike slice.

**Shipped:** `user/tasks/340-tasks.command-surface-spike-dispatch-vs-prefix.md` — 8 tasks, 105 lines.

**Task summary:** T1–T2 create the dispatcher and two stub files; T3 installs them; T4 runs the four prescribed test invocations; T5 records the decision in the slice design; T6 updates the arch doc; T7 removes spike files and re-syncs; T8 marks complete and commits.

**Next step:** Phase 6 implementation — run the spike (T1–T8 above).

---

## 20260625 (3)

### Initiative 340 — Slice 340 (Command Surface Spike): Phase 4 Slice Design Complete

**Completed:** Slice design written for the command surface spike.

**Shipped:** `user/slices/340-slice.command-surface-spike-dispatch-vs-prefix.md`

**Design summary:** A time-boxed spike. Builds a minimal dispatcher markdown file (`analysis.md`) and two stub skill files, installs them via the existing `sq install-commands` path, and runs four test invocations to determine whether Claude Code reliably passes arguments through a dispatch file. Records findings in a `## Spike Results` section appended to the slice design doc. Updates `340-arch` with the closed decision. Stub files are removed after the decision is recorded. The spike has no persistent code deliverable — its output is a decision and an arch doc update that unblocks slice 341.

**Next step:** Run the spike (Phase 6 implementation is just running four commands and recording observations), then move to slice 341 slice design.

---

## 20260625 (2)

### Initiative 340 — Skill Pack Infrastructure: Slice Plan Complete

**Completed:** Slice plan written at `user/architecture/340-slices.skill-pack-infrastructure.md`. Four slices across Foundation, Feature, and Integration sections.

**Slice summary:**
- **(340) Command Surface Spike** — Closes the dispatch-vs-prefix open question empirically. Time-boxed; outcome updates the arch doc. Effort 1/5.
- **(341) Manifest Format + `sq skills install/list`** — Core mechanism: `skills.toml` schema, source resolution (bundled/local/git), file-copy installer. Effort 3/5.
- **(342) Analysis Pack (Bundled)** — Ships `tech-debt-analyze` (and others) as `commands/analysis/` in the wheel; one-command install via `sq skills install analysis`. Effort 2/5.
- **(343) `sq skills uninstall` + `sq doctor` integration** — Completes the CLI surface; `sq doctor` gains a Skill Packs section. Effort 1/5.

**Next step:** Spike slice 340 when ready to begin implementation.

---

## 20260625

### Initiative 340 — Skill Pack Infrastructure: Architecture Complete

**Completed:** Initiative 340 added to the initiative plan and architecture document written.

**Context:** Squadron's growing use for analysis of existing codebases surfaced a gap — useful external skills (tech-debt-analyze, understand-anything, etc.) have no principled install path alongside first-party commands. This initiative adds a thin, opt-in skill pack mechanism: a TOML manifest + `sq skills install/list` that copies external skill markdown files into `~/.claude/commands/<prefix>/`, exactly mirroring the existing `install-commands` pattern.

**Key decisions captured in arch:**
- Prefix-per-pack model (`/analysis:tech-debt`) keeps `/sq:*` clean; open question is whether a dispatch router (`/sq:analysis <skill>`) is a viable UX alternative — resolved by a planned spike slice.
- File copy is the delivery primitive; no runtime indirection, no loader, no daemon involvement.
- Analysis pack ships bundled in the wheel (parallel to `commands/sq/`); external sources (local path, git ref) supported by manifest format.
- Squadron owns the analysis pack; third-party packs are supported by format but not hosted.

**Shipped:** `user/architecture/340-arch.skill-pack-infrastructure.md`, initiative entry in `001-initiative-plan.squadron.md` (index 340, cross-dep entry added).

**Next step:** Slice plan (`340-slices.skill-pack-infrastructure.md`) with spike slice as first entry.

---

## 20260617

### Initiative 300 — Slice 300 (Numeric Scoring Foundation): Phase 6 Implementation Complete

**Completed:** Phase 6 implementation of the keystone slice 300. All 13 tasks (T1→T13) implemented, tested, and committed one-per-task on branch `300-slice.numeric-scoring-foundation`. The slice is the additive, judging-free foundation every later 300 slice composes on.

**Shipped (six source modules, additive only):**
- `review/models.py` — `ReviewResult.score` / `.criteria` / `.provenance` (all `float|dict|str | None`, default `None`); `to_dict()` emits the three keys.
- `pipeline/models.py` — `ActionResult.score` / `.criteria` / `.provenance`, mirroring `verdict`; picked up automatically by `dataclasses.asdict`.
- `review/parsers.py` — new `_extract_score` / `_extract_criteria` helpers + a shared `_parse_finite_float`; wired into `parse_review_output`. Lenient and judging-unaware: absent/malformed → `None`, never raises, never range-checks, first `score:` wins, `inf`/`nan` rejected as non-finite. Criteria parsed from the indented YAML-map block, whole-map-to-`None` on any malformed entry.
- `pipeline/actions/review.py` — threads `result.score` / `.criteria` into the returned `ActionResult` (`provenance` left `None`).
- `review/persistence.py` — `format_review_markdown` emits a top-level `score:` line and a `criteria:` block when present; score-less output is byte-for-byte unchanged.
- `pipeline/state.py` — `StepState.score` + a score hoist in `_append_step` mirroring the verdict hoist.

**Tests:** new coverage in `tests/review/test_models.py`, `tests/review/test_parsers.py` (incl. the full failure-mode table + real score-less / score-bearing / criteria-bearing fixtures), `tests/review/test_persistence.py`, `tests/pipeline/test_models.py`, `tests/pipeline/test_state.py` (incl. backward-compat: old run-state JSON without `score` loads), `tests/pipeline/actions/test_review_action.py`. Full suite: **1969 passed, 2 skipped**; `pyright` 0 errors; `ruff check` + `ruff format --check` clean.

**Notable during implementation:**
- One real bug found and fixed in `_extract_criteria`: the `$`-in-MULTILINE label match left the slice starting at the trailing newline, so `splitlines()[0]` was empty and the block ended immediately — fixed by lstripping the leading newline. Caught by an inline probe before the test task.
- No-judging-logic-leak gate (T13): grepped the slice diff — `provenance` appears only as field declarations, comments, and the `to_dict()` serialization key; zero range checks, zero verdict-from-score derivation. Confirmed clean.
- Verification Walkthrough updated with actual commands/output; interactive steps 4–5 replaced with equivalent non-interactive probes (plus a caveat) so an external agent can run them verbatim.

**Process:** `cf:check` (workflow_check) slice 300 — clean after auto-fixing the slice-plan checkbox; slice design + task frontmatter set to `status: complete` / `dateUpdated: 20260617`; CHANGELOG `[Unreleased]` updated.

**Next step:** Phase 4 design for slice 301 (Judge Enforcement Layer) — populates `provenance`, validates the score, derives the verdict by thresholding. No model re-open needed (the shape is settled here).

---

## 20260607

### Initiative 300 — Slice 300 (Numeric Scoring Foundation): Phase 5 Task Breakdown Complete

**Completed:** Phase 5 task breakdown for the keystone slice 300. Task file created from the (review-revised) slice design.

**Shipped:** `project-documents/user/tasks/300-tasks.numeric-scoring-foundation.md` — 13 tasks, ~225 lines (well under the 450 cap, single file). Test-with ordering: each implementation task (T1/T3/T5/T7/T9/T11) is immediately followed by its test task (T2/T4/T6/T8/T10/T12); T13 is the full-suite + static-analysis + no-judging-logic-leaked validation pass. One commit per task. Closes with a coverage table mapping every LLD change to its task(s).

**Decisions/notes:**
- Tasks made authoritative on the **full three-field set** (`score`/`criteria`/`provenance`) on both `ReviewResult` and `ActionResult` — the LLD's component-summary table lagged on `provenance` in two rows, but the LLD body is explicit, so tasks follow the body. Provenance is field-only (T1/T3 add it; T13 verifies nothing populates/reads it).
- Verified all referenced test-file paths against the real tree; corrected `test_review.py` → `tests/pipeline/actions/test_review_action.py` (the others — review test_models/test_parsers/test_persistence, pipeline test_models/test_state — all exist).
- Parser failure-mode table (non-numeric/inf/nan/multi-line/malformed-criteria → `None`, no raise) is its own dedicated test task (T6).
- `cf:check` for slice 300: clean (the prior "design but no task file" info is resolved).

**Task review (glm-5.1, verdict PASS):** coverage/sequencing/test-with/sizing/commits/failure-mode-coverage all PASS. One CONCERN (F003): `_extract_criteria`'s recognized text format was underspecified — `score:` was pinned but `criteria:` was not, leaving T5/T6 without a positive-fixture anchor. **Fixed** in both LLD and task file: pinned `criteria` to the minimal YAML-map shape (top-level `criteria:` + indented `key: <number>` lines — the same idiom T9 emits), whole-map-to-`None` on any malformed value; added a criteria-bearing fixture to T6. Also fixed the LLD component-table + data-flow-diagram lag on `provenance` (body was already explicit).

**Next step:** Phase 6 implementation of slice 300, following T1→T13. After 300 lands, Phase 4 design for slice 301 (Judge Enforcement Layer).

---

## 20260605

### Initiative 300 — Slice 300 (Numeric Scoring Foundation): Phase 4 Slice Design Complete

**Completed:** Phase 4 low-level design for the keystone slice 300, the numeric-scoring foundation. Design grounded in the actual code (read `review/models.py`, `pipeline/models.py`, `review/parsers.py`, `pipeline/actions/review.py`, `review/persistence.py`, `pipeline/state.py`).

**Shipped:** `project-documents/user/slices/300-slice.numeric-scoring-foundation.md` — additive `score: float | None` + reserved `criteria: dict[str,float] | None` on `ReviewResult` and `ActionResult`; lenient, judging-unaware optional extraction in `parse_review_output`; threading through the review action's `ReviewResult → ActionResult` map; persistence on two surfaces.

**Key design decisions:**
- **"Queryable, first-class, not opaque" resolved against real code:** squadron has no SQL DB. The two queryable surfaces are (a) review-file YAML frontmatter — `score:` as a top-level key beside `verdict:`; and (b) run-state JSON — a new top-level `StepState.score` hoisted in `_append_step` from the last non-`None` action score, exactly mirroring the existing `verdict` hoist (state.py:267–286). Resolves the open question "storage representation for the queryable score."
- **Field type `float | None`** (not int, not a sentinel): float holds integer scores and future multi-sample medians; `None` is the only "absent" representation — no `0`/`-1` fallback (project no-silent-fallback rule, and a correctness prerequisite for 301's required-ness check).
- **Parser stays lenient and judging-unaware:** extracts when present, silent on absence, **no validation/range-check/thresholding.** Out-of-range values (e.g. `150`) are extracted as-is; validation → `UNKNOWN` is 301's job at the judge use. This is the parser side of the architecture's two-layer split.
- **Real-fixture tests on both paths** (score-less regression fixture + score-bearing fixture in the judge-template shape) per the project "test the parser on real input" rule.

**Scope boundary held:** no judging *logic* in this slice — required-ness, validation, thresholding, and verdict derivation are all 301.

**Design review (glm-5.1, verdict CONCERNS) — both concerns addressed:**
- **F001 (provenance):** the architecture commits the provenance field to the *result model*, and 300 is the keystone "settle the model shape once" slice — so deferring provenance entirely to 301 would force 301 to re-open the models. **Fix:** add `provenance: str | None = None` as a *latent reserved field* in 300 (mirrors how `criteria` is reserved), unpopulated/unread here; 301 supplies only its meaning and use. No model re-open downstream.
- **F002 (parser failure modes):** added an explicit failure-mode enumeration table for the new score/criteria extraction path (non-numeric value → `None`; `inf`/`nan` → `None`; multiple score lines → first wins; malformed criteria → whole map `None`) — never raises, never fabricates a number. Observable-WARNING-on-required-absence stays 301's job (firing it in the parser would trigger on every ordinary score-less review). Satisfies the project Failure-Mode Enumeration rule.
- F003 (note): structured-output parser shape correctly deferred to 302 — no change.

**Next step:** Phase 5 task breakdown for slice 300, then Phase 6 implementation. After 300 lands, Phase 4 design for slice 301 (Judge Enforcement Layer).

---

## 20260604

### Initiative 300 (Intrinsic LLM Judging & Scoring): Phase 3 Slice Planning Complete

**Completed:** Phase 3 slice planning for initiative 300. Slice plan created from the reviewed architecture document; architecture marked `complete`.

**Shipped:**
- `project-documents/user/architecture/300-slices.eval-actions-llm-as-judge-scoring.md`: five slices in dependency/implementation order — (300) Numeric Scoring Foundation [keystone, foundation, done alone], (301) Judge Enforcement Layer, (302) Design-Phase Judge Templates, (303) Judge-Gated Cycle Conventions, (304) Gate Composition [integration]. Plus a Future Work backlog: multi-sample judging, on-demand ground-truth fetching, checkpoint multi-verdict support (140).
- `300-arch.eval-actions-llm-as-judge-scoring.md`: status `reviewed` → `complete`, dateUpdated 20260604.

**Key planning decisions:**
- Keystone (300) ordered first and done alone, per the architecture — the only Medium-risk cross-cutting model/parser/persistence change; everything composes on it.
- Refined the architecture's four anticipated slices into five by splitting the judge **enforcement layer** (301: required-ness, 0–100 validation, score→verdict thresholding, provenance) from the judge **templates** (302). The two-layer parser/action split is an explicit architectural commitment, the enforcement is independently testable, and no template is gateable until it exists.
- Every slice is additive and leaves the system in a working state; existing verdict-gating pipelines unchanged throughout.
- Gate composition (304) carries the architecture's explicit boundary: prefer upstream reduction (additive, in-scope 300); if insufficient, escalate checkpoint multi-verdict support as a coordinated 140 dependency, not a silent absorption.

**Open questions deferred to slice design (Phase 4):** provenance field name/enum, threshold band values + config keys, queryable-score storage representation, which design-phase judge templates to author first.

**Next step:** Phase 4 slice design for slice 300 (numeric scoring foundation), the keystone.

---

## 20260520

### Slice 908: `sq setup` — Phase 6 Implementation Complete

**Completed:** Phase 6 implementation for slice 908. Slice is complete.

**Shipped:**
- `src/squadron/cli/commands/setup_steps.py` (~220 lines): pure conversion layer (`CheckResult → SetupStep`). `StepKind` StrEnum, `SetupStep` frozen dataclass, `_RECHECK_MAP`, `_classify`, `build_steps` with profile filtering, `_DOCS_ANCHOR`, `_EXPLANATION`, synthesised per-profile recheck lambdas.
- `src/squadron/cli/commands/setup.py` (~120 lines): Typer command with `--non-interactive`, `--check-only`, `--profile`, `--verbose` flags. Rendering functions `_render_check_only`, `_render_non_interactive`, `_run_interactive` (re-prompt cap=5, `q` exits 2).
- `src/squadron/cli/app.py`: `app.command("setup")(setup)` registration.
- `scripts/install.sh` (~100 lines): bash bootstrap with `set -euo pipefail`, interactive prompts, `uv`/`pipx` detection, `npm` detection, `--yes`/`--help` flags, `exec sq setup` handoff.
- `tests/cli/test_setup_steps.py`: 20 tests covering T3, T6, T10, T11, T12.
- `tests/cli/test_setup.py`: 10 tests covering T18a, T18b, T19, T20, T21, T22, T23, T24.
- `tests/scripts/test_install_sh.sh` + `test_install_sh.py`: idempotency smoke test (T26).
- README: "Fresh install (one liner)" section added (T27).
- CHANGELOG: `sq setup` and `scripts/install.sh` entries added.

**Deviations from design:** None. All design decisions implemented as specified.
- T28 (QUICKSTART callout) skipped — `docs/QUICKSTART.md` does not exist yet (slice 906 not merged). DEVLOG follow-up noted.
- Aggregate "at least one provider OK" suppression optimisation deferred per design decision (initial release shows all profile rows).

**Test results (final gate):**
- `pytest tests/cli/test_setup.py tests/cli/test_setup_steps.py tests/scripts/test_install_sh.py -q`: **31 passed**
- `pytest -q` (full suite): **1936 passed, 2 skipped**
- `ruff check && ruff format --check && pyright`: **all clean**

**Exit codes verified:** 0 (all OK), 1 (MISSING present), 2 (user quit), 3 (internal error), 64 (unknown profile).

**Follow-up:** When slice 906 merges and `docs/QUICKSTART.md` exists, add the `sq setup` callout under Step 5 / Troubleshooting (T28).

**Branch:** `908-sq-setup-one-call-install-orchestrator`.

---

## 20260519

### Slice 908: `sq setup` One-Call Install Orchestrator — Phase 4 Slice Design Complete

**Completed:** Phase 4 low-level design for slice 908.

**Document created:**
- `project-documents/user/slices/908-slice.sq-setup-one-call-install-orchestrator.md` — full slice design (status: `not_started`)

**Slice plan updated:** `900-slices.maintenance-and-refactoring.md` entry 7 now references the materialized design path.

**Design highlights:**
- `sq setup` is a *renderer* over slice 905's `run_all_checks()` — no new check logic. Conversion layer maps each `CheckResult` to a `SetupStep` with kind `ALREADY_DONE` / `INSTALL` / `CONFIGURE` / `OPTIONAL`.
- Three modes: interactive (default, one prompt per missing step with `enter/s/q`), `--non-interactive` (emit all steps without prompts; pipe-to-file friendly), `--check-only` (one-liner per step, exits with `sq doctor`'s code).
- `--profile <name>` filters Provider-section steps to a single profile.
- Per-step re-check via a local "check-name → function" map inside `setup_steps.py`. Degrades to "press enter when done" if 905 adds checks we haven't mapped.
- Companion `scripts/install.sh` (bash) handles only the pre-Squadron bootstrap (pipx/uv → `pipx install squadron-ai` → `npm i -g @manta-digital/context-forge` → handoff to `sq setup`). No automatic shell execution from Python.
- Distribution via GitHub raw URL: `curl -sSL <raw URL> | sh`. Pinning to a tag is a follow-up.
- Idempotency contract: setup is re-runnable, install.sh is re-runnable; both detect existing state and skip done steps.

**Cross-slice contract:**
- Strict consumer of slice 905's `CheckResult`, `CheckStatus`, `run_all_checks()`. No API changes requested upstream.
- References slice 906 (QUICKSTART) anchors for `docs_anchor`. If 906 ships later, anchors degrade gracefully to plain section names.

**Branch:** `908-sq-setup-one-call-install-orchestrator` (created from `main`).

**Next:** Phase 5 task breakdown — `task-checker`-friendly checklist derived from this design.

---

### Slice 908: `sq setup` — Phase 5 Task Breakdown Complete

**Completed:** Phase 5 task breakdown for slice 908.

**Document created:**
- `project-documents/user/tasks/908-tasks.sq-setup-one-call-install-orchestrator.md` — 32 tasks (T1–T32) across seven phases (status: `not_started`).

**Phase shape (test-with-pattern preserved throughout):**
- **A. Setup and data model** — branch confirmation, skeleton files, `StepKind` / `SetupStep` dataclass, baseline tests.
- **B. `build_steps` conversion layer (pure)** — recheck-function map, `_classify`, `build_steps`, docs-anchor map, explanation strings; each implementation immediately followed by its tests.
- **C. `setup.py` Typer command and rendering** — command skeleton with all flags, `--check-only` / `--non-interactive` / interactive renderers, registration in `cli/app.py`.
- **D. Tests for `setup.py`** — `CliRunner`-based coverage of every flag combination, profile filter, `q`-quit, recheck loop, and the internal-error fallback.
- **E. `install.sh` bootstrap** — bash script with `set -euo pipefail`, explicit prompts before each install, plus a `pytest`-wrapped idempotency smoke test using PATH-shimmed stubs.
- **F. Documentation** — README one-liner pointer; optional QUICKSTART callout gated on slice 906 merge order.
- **G. Final gate** — full `pytest` / `ruff` / `pyright` gate, verification walkthrough recording into the slice design, slice-plan checkbox flip, DEVLOG closeout.

**Notable design constraints carried into tasks:**
- No automatic shell execution from Python beyond `install_commands()` with explicit consent.
- Per-step re-check cap = 5 (prevents infinite loops in scripted stdin).
- `q` exits 2 (user-aborted), distinct from 1 (`sq doctor` reports missing) and 3 (internal error).
- `_DOCS_ANCHOR` and `_EXPLANATION` maps are local to `setup_steps.py` — no upstream API changes to slice 905.

**Review note:** Phase 4 review flagged 908 as "new feature under maintenance arch" (F001). PM decision was to leave categorisation alone — 905/906/908 form a cohesive onboarding trio that has historically lived under the 900 maintenance architecture. No design changes resulted.

**Task file size:** 259 lines (well under 450-line target; no split needed).

**Branch:** `908-sq-setup-one-call-install-orchestrator`.

**Next:** Phase 6 implementation following T1–T32 in order.

---

## 20260510

### Slice 250: Container Step Classification — Implementation Complete

**Completed:** Phase 6 implementation. Slice 250 is complete.

**Summary of changes (commit 91f8ccd):**
- New `src/squadron/pipeline/steps/utils.py` — `unpack_inner_steps` extracted from `executor.py` to eliminate circular import
- `executor.py` — replaced local `_unpack_inner_steps` with imported utility
- `EachStepType.inner_steps()`, `LoopStepType.inner_steps()` — parse `steps:` list, return `StepConfig` objects
- `FanOutStepType.inner_steps()` — returns one synthetic `_fan_out_aggregate` sentinel carrying the `models:` value
- `classification.py` — added `_classify_alias_set` (shared alias-set aggregator), `_classify_container_inner` (classifies a single inner step / handles `_fan_out_aggregate` sentinel), extended main step loop to descend into containers when `expand()` returns `[]`; added `container_path: str | None = None` field to `StepClassification`
- `run.py` — `_render_explain` emits dim container header rows and `↳ {inner_name}` indented inner-step rows
- 27 new tests across `test_inner_steps.py`, `test_classification.py`, `test_run.py`
- Full suite: 1869 passed, 2 pre-existing failures (compact compose integration)

**Notable implementation decisions:**
- Used `getattr(step_impl, "inner_steps", None)` instead of a lambda to avoid pyright `Unknown` errors
- Rich wraps cell content in narrow test terminals — `↳` assertions check for the symbol presence rather than `"↳ name"` substring
- `_classify_pool_step` refactored to a thin wrapper over `_classify_alias_set` preserving `pool_name`

---

### Slice 250: Container Step Classification — Task Breakdown Complete

**Completed:** Phase 5 task breakdown.

**Documents created:**
- `project-documents/user/tasks/250-tasks.container-step-classification-each-loop-fan-out.md` — 12 tasks, 321 lines

**Task structure:**
- T1: Branch setup
- T2: Extract `_unpack_inner_steps` → `steps/utils.py` (removes circular import); update executor call sites
- T3: `EachStepType.inner_steps()` + tests
- T4: `LoopStepType.inner_steps()` + tests
- T5: `FanOutStepType.inner_steps()` returning sentinel `_fan_out_aggregate` + tests
- T6: Extract `_classify_alias_set` from `_classify_pool_step`; regression test
- T7: Add `container_path: str | None = None` to `StepClassification`; regression test
- T8: Core classifier extension — `_classify_container_inner` helper + modified step loop; 9 new classification tests
- T9: `_render_explain` container rendering (header row + `↳` indent) + 3 rendering tests
- T10: ruff format/check, pyright, full pytest gate
- T11: Implementation commit
- T12: Slice closeout (status, slice plan, CHANGELOG, DEVLOG, docs commit)

**Key task notes:**
- T2 is the prerequisite for T3/T4 (circular import blocker). T5 is independent of T3/T4.
- T6 must precede T8 (T8 calls `_classify_alias_set`).
- T7 must precede T8 and T9 (both use `container_path`).
- T8's `_classify_container_inner` asserts `inner.step_type != "_fan_out_aggregate"` before `get_step_type()`, enforcing the sentinel invariant.

**Status:** Ready for Phase 6 (Implementation).

---

### Slice 250: Container Step Classification — Design Complete

**Completed:** Phase 4 slice design.

**Documents created/updated:**
- `project-documents/user/slices/250-slice.container-step-classification-each-loop-fan-out.md` — full LLD
- `project-documents/user/architecture/240-slices.pipeline-auth-boundary-flexibility.md` — slice 250 entry updated with design link and today's date

**Key design decisions:**
- `inner_steps(config)` added as an optional extension method on step types (detected via `hasattr`, not a required protocol method) — avoids touching all existing step type files.
- `_unpack_inner_steps` extracted from `executor.py` to a shared location so `EachStepType` and `LoopStepType` can reuse it in `inner_steps()` without a circular import.
- `fan_out` returns one synthetic sentinel `StepConfig` (`step_type="_fan_out_aggregate"`) encoding the `models:` field. The classifier detects the sentinel and routes to pool-classify or alias-list-classify accordingly.
- `_classify_alias_set` extracted from `_classify_pool_step` as a shared helper — both the pool path and the fan_out literal-list path call the same aggregation rule.
- `StepClassification` gains `container_path: str | None = None` (backward-compatible, defaults to `None`).
- `--explain` rendering uses `  ↳` indent in the Step column rather than a new column — keeps table width manageable.
- Parent step attribution: inner-step `StepClassification` rows carry the container's `step_name` and `step_index`, not the inner step's own name (which goes in `container_path`).
- No executor changes in scope.

**Status:** Ready for Phase 5 (Task Breakdown).

---

## 20260504

### Slice 245: Pool-Resolution Classification Policy and Mid-Run Session Construction — Task Breakdown Complete

**Completed:** Phase 5 task breakdown.

**Documents created:**
- `project-documents/user/tasks/245-tasks.pool-resolution-classification-policy-and-mid-run-session-construction.md` — 19 tasks across: enum addition, `PipelineClassification` policy field, `classify_pipeline` default change, `auth_policy` YAML field (`PipelineSchema` + `PipelineDefinition`), `execute_pipeline` mid-run hook + helpers, connect-failure UX, `--strict` CLI flag, policy resolution, existing test audit, build/format, and closeout.

**Key task notes:**
- T7: `PipelineSchema` has `extra="forbid"` — `auth_policy` must be added as a declared field; validator rejects anything other than `None`/`"lazy"`/`"strict"`.
- T9: `_step_needs_sdk` ignores pool candidates (returns `False`) — hook fires only on statically confirmed SDK steps.
- T11: connect failure → run state `failed` + re-raise → `_run_pipeline_sdk` catches and prints red message.
- T15: existing pool-uncertain tests relied on the old conservative default; they need `policy=STRICT` annotations or assertion updates.

**Pending:** Phase 6 (implementation). No open questions.

---

### Slice 245: Pool-Resolution Classification Policy and Mid-Run Session Construction — Design Complete

**Completed:** Phase 4 slice design.

**Documents created/updated:**
- `project-documents/user/slices/245-slice.pool-resolution-classification-policy-and-mid-run-session-construction.md` — slice design
- `project-documents/user/architecture/240-slices.pipeline-auth-boundary-flexibility.md` — slice plan entry 5 updated with design link and revised policy framing

**Design summary:**
- **Lazy is the default.** Session not constructed at startup for pool-uncertain pipelines. `--strict` CLI flag (and `auth_policy: strict` pipeline config key) opts into eager upfront connection.
- `PoolClassificationPolicy` enum (`lazy` / `strict`) in `pipeline/classification.py`; default is `LAZY`.
- `classify_pipeline` gains optional `policy` parameter (default `LAZY`); `PipelineClassification` stores the policy used.
- `needs_persistent_session`: under `LAZY`, `POOL_UNCERTAIN` does not force session construction; only statically-confirmed `SDK_REQUIRED` steps do.
- Mid-run hook in `execute_pipeline` (arch §5a): fires on first confirmed-SDK step when `sdk_session is None`; all subsequent steps reuse the same session. Hook is policy-agnostic (dead path under strict mode since session is pre-constructed).
- Auth-failure UX: connect failure mid-run → `failed` run state + clear message; runtime pool selects SDK with no session → `FAILED` step result with `--strict` remediation hint.
- 12 new tests planned across `test_run_pipeline_lazy.py` and `test_classification.py`. Existing pool-uncertain tests need policy annotation update.

**Pending:** Phase 5 (task breakdown) and Phase 6 (implementation). No open questions; design is self-contained.

---

### Slice 244: Conditional Persistent Session Construction — Implementation Complete

**Completed:** Phase 6 implementation (commit c939fb2, branch `244-slice.conditional-persistent-session-construction`)

**Files changed:**
- `src/squadron/cli/commands/run.py` — Added `pool_backend: PoolBackend | None = None` param to `_run_pipeline`; added guard replacing unconditional `DefaultPoolBackend()`. In `_run_pipeline_sdk`: lifted `DefaultPoolBackend()` construction, added `_classify_resolver` (no `on_pool_selection`), added `classify_pipeline` call with `ClassificationError` handler, added INFO/DEBUG logging of classification shape, added session gate (`if classification.needs_persistent_session`). Added `_logger = logging.getLogger(__name__)`.
- `tests/cli/commands/test_run_pipeline_sdk.py` — New test file: 11 tests covering T3 (fallback), T6 (classification gate: all 6 scenarios), T7 (resume path: 2 scenarios).
- `tests/pipeline/test_sdk_wiring.py` — Updated 2 tests to mock `classify_pipeline`/`DefaultPoolBackend`/`ModelResolver` for `needs_persistent_session=True` (tests verify connect/disconnect lifecycle; mock classification is correct because those tests are about lifecycle, not classification).

**Design decisions confirmed during implementation:**
- `on_pool_selection` callback needs `state_mgr`/`_run_id` (initialized inside `_run_pipeline`), so the classification resolver `_classify_resolver` is built without a callback — classification is side-effect-free and never calls `pool_backend.select()`.
- `typer.Exit` raises `click.exceptions.Exit`, not `SystemExit` — tests use `pytest.raises(typer.Exit)` with `exc_info.value.exit_code == 1`.
- Tests run inside Claude Code session (`CLAUDECODE` env var set), so all `_run_pipeline_sdk` tests patch `_resolve_execution_mode` to bypass the session guard.
- Pre-existing failures: `tests/pipeline/test_compact_compose_integration.py` (2 tests) were already failing on main before this slice; not introduced here.

**Audit (T9):** `sdk_session=None` guards confirmed present in `compact.py:62`, `summary.py:149`, `summary.py:218`. No changes needed.

**Test results:** 1806 passing, 2 pre-existing failures (compact compose, unrelated), 0 new failures.

---

### Slice 244: Conditional Persistent Session Construction — Task Breakdown Complete

**Completed:**
- Created `user/tasks/244-tasks.conditional-persistent-session-construction.md` (11 tasks, 192 lines)

**Task structure:**
- T1: Branch setup
- T2: Add optional `resolver`/`pool_backend` params to `_run_pipeline` (backward-compatible)
- T3: Test fallback path (no params supplied)
- T4: Lift `pool_backend`/`resolver` construction into `_run_pipeline_sdk`; wire `on_pool_selection`
- T5: Add `classify_pipeline` call and session gate in `_run_pipeline_sdk`
- T6: Tests for classification gate (T1–T5, T8 from design — non-SDK, SDK, pool-uncertain, ClassificationError, connect failure)
- T7: Tests for resume path (T6, T7 from design)
- T8: Intermediate commit (ruff + pyright + pytest gate)
- T9: Audit `sdk_session=None` correctness for summary/compact (belt-and-suspenders verification)
- T10: Final validation and commit
- T11: Documentation and slice closeout

**Key design note in tasks:** `on_pool_selection` callback depends on `state_mgr`/`_run_id`, which are initialized inside `_run_pipeline`. T4 explicitly flags that the callback must be attached after `state_mgr` is known — implementer must set `resolver._on_pool_selection` inside `_run_pipeline` when `resolver is not None`, or add a setter. Classification never fires pool selection (side-effect-free), so the callback is safe to attach late.

**Status:**
- Task breakdown complete and ready for Phase 6 (Implementation).

---

### Slice 244: Conditional Persistent Session Construction — Design Complete

**Completed:**
- Created `user/slices/244-slice.conditional-persistent-session-construction.md`
- Updated slice plan entry 244 in `240-slices.pipeline-auth-boundary-flexibility.md` with design link

**Key design decisions:**
- Classification runs inside `_run_pipeline_sdk` after `definition` is loaded and `resolver` is constructed — before any session work.
- `pool_backend` and `resolver` are constructed in `_run_pipeline_sdk` and threaded into `_run_pipeline` as optional params; `_run_pipeline`'s internal fallback construction is preserved for callers that don't supply them.
- `POOL_UNCERTAIN` steps take the conservative-pessimistic path (session constructed); lazy opt-in is slice 245.
- `ClassificationError` → `typer.Exit(1)` with a clear message; not an unhandled exception.
- Resume re-classifies from current YAML + alias state; seeding path unchanged (runs only when `sdk_session is not None`).
- Three observable shapes fully established: `claude_required_persistent`, `claude_required_one_shot`, `claude_free`.

**Status:**
- Design ready for Phase 5 (Task Breakdown).

---

## 20260518

### Slice 907: Optional Dependency Split — Task Breakdown Complete

**Completed:** Phase 5 task breakdown. Task file created at `user/tasks/907-tasks.optional-dependency-split-serve-and-codex-extras.md` (173 lines, 8 task groups, 31 checklist items).

**Task structure:**
- T1: Branch setup
- T2: `pyproject.toml` — remove fastapi/uvicorn from deps, add `[serve]` and `[codex]` extras
- T3: Extract `src/squadron/server/pid.py` (DaemonConfig + PID helpers); update `daemon.py` to import from it; update `tests/server/test_daemon.py`
- T4: Update `serve.py` — top-level imports switch to `pid.py`; `start_server`/`SquadronEngine` deferred into `_start_daemon()` after import guard
- T5: Codex binary guard in `provider.py` — `create_agent()` raises `ProviderError` (not `ProviderAuthError`) when binary absent
- T6: Full test suite + static analysis (ruff, pyright, pytest)
- T7: Clean-venv verification walkthrough
- T8: Commit

**Status:** Ready for Phase 6 (Implementation).

---

## 20260514

### Slice 907: Optional Dependency Split — Design Complete

**Completed:**
- Created `user/slices/907-slice.optional-dependency-split-serve-and-codex-extras.md`

**Key Design Decisions:**
- `fastapi` and `uvicorn` move from `[project.dependencies]` to a new `[serve]` optional extra.
- `[codex]` extra is declared empty (PyPI rejects direct URL refs); a comment block carries the GitHub install command.
- `sq serve` start guard lives inside `_start_daemon()` — `--status` and `--stop` remain usable without `[serve]`.
- `start_server` and `SquadronEngine` imports deferred into `_start_daemon` after the guard; `DaemonConfig`/PID helpers stay top-level (verify they don't transitively pull fastapi; extract to `server/pid.py` if they do).
- `CodexProvider.create_agent()` gains an early binary check (`resolve_codex_binary is None` → `ProviderAuthError` with `npm i -g @openai/codex`). SDK import guard already present in `_run_prompt`; no change needed there.

**Status:**
- Design ready for Phase 5 (Task Breakdown).

---

## 20260424

### Slice 167: Per-Action Model Override Convention — Design Complete

**Completed:**
- Created `user/slices/167-slice.per-action-model-override-convention.md`
- Enhanced existing stub with full design: data flow, cascade position, code
  change, YAML/params interaction (no loader change required), test list,
  verification walkthrough, and documentation target
- Key technical decision: `params["review_model"]` is a separate params channel
  from `params["model"]`; step-level `review.model: X` wires into `params["model"]`
  (unchanged), while `--param review_model=Y` writes to the new key — no conflict
- `docs/PIPELINES.md` Model Resolution section is the documentation target
- First adopter: `ReviewAction` only; future actions adopt independently

**Design decisions recorded:**
- `review_model` (underscore) is the canonical convention key matching Python dict
  and `--param` syntax; existing `review-model` (hyphen) YAML param continues to
  work via step-level wiring unchanged
- No loader change needed — the two channels are naturally separate by how params
  merge in the executor

**Status:**
- Phase 4 complete. Ready for Phase 5 (task breakdown).

---

### Slice 154: Prompt-Only Loops — Design Complete

**Completed:**
- Verified `user/slices/154-slice.prompt-only-loops.md` against current codebase — all technical assumptions confirmed accurate
- Codebase verification: all 5 executor functions to be reused (`_parse_source`, `_SOURCE_REGISTRY`, `resolve_placeholders`, `_unpack_inner_steps`, `_resolve_str`) exist and are module-level; all 3 CLI handlers exist; `ExecutionMode` enum, `EachStepType`, `StepTypeName.EACH` in place
- Schema v4 confirmed current; design's v4→v5 bump plan is correct
- Implementation targets confirmed absent (as expected): `LoopContext` model, `loop_context` field on `RunState` and `StepInstructions`
- Updated frontmatter status from `not_started` to `in_progress`
- Note: Phase 5 task file (`154-tasks.prompt-only-loops.md`) was created in a prior session (20260410) but reverted (`39c575d`) — Phase 5 needs to be re-executed

**Status:**
- Phase 4 complete. Design verified and current. Ready for Phase 5 (task breakdown).

---

### Slice 154: Prompt-Only Loops — Phase 4 Design Refreshed

**Completed:**
- Refreshed `user/slices/154-slice.prompt-only-loops.md` against current codebase state (post slices 153–169)
- Updated data models to use Pydantic `BaseModel` (matching `RunState` pattern, was dataclass)
- Schema version bump: v4 → v5 (was v1 → v2 in original design; actual codebase is now at v4)
- Clarified `StateManager` interaction: `first_unfinished_step` remains loop-unaware; loop logic lives in CLI handlers (`_handle_prompt_only_init`, `_handle_prompt_only_next`, `_handle_step_done`)
- Added `LoopContext` model with cached `items` list for deterministic resume
- Documented reuse of executor internals: `_SOURCE_REGISTRY`, `_parse_source`, `resolve_placeholders`, `_unpack_inner_steps`
- Updated out-of-scope references to reflect completed slices (160 checkpoints, 169 compact dispatch)
- Updated slice plan entry from "Design preserved" to "Design Complete"

**Design decisions (unchanged from original, validated against current code):**
- Loop iterations flattened into instruction stream — callers are loop-unaware
- Step names follow `{inner_step_name}-each-{item_index}` pattern
- Flattened step names go into `completed_steps`; parent `each` step recorded on loop completion
- Source items cached in LoopContext for deterministic resume

**Status:**
- Phase 4 complete. Ready for Phase 5 (task breakdown).

---

## 20260412

### Slice 191: Dispatch Summary Context Injection — Phase 5 Task Breakdown Complete

**Completed:**
- Created `user/tasks/191-tasks.dispatch-summary-context-injection.md` (171 lines, 7 tasks)
- Tasks cover: new `summary_context.py` module (T1), unit tests for assembler (T2),
  integration into `_execute_summary()` (T3), integration tests (T4), full verification
  and commit (T5), end-to-end verification (T6), slice completion (T7)
- Implementation note captured: `ActionType` has no `COMPACT` entry; compact steps
  expand to `"summary"` action type — the `match/case` only needs `ActionType.SUMMARY`

**Status:**
- Phase 5 complete. Ready for Phase 6 (implementation).

---

### Slice 191: Dispatch Summary Context Injection — Phase 4 Design Complete

**Completed:**
- Created `user/slices/191-slice.dispatch-summary-context-injection.md`
- New module `pipeline/summary_context.py` with `assemble_dispatch_context()` — pure function that extracts content from `prior_outputs` by action type (dispatch responses, review findings, build_context text, prior summaries) and assembles a delimited context block
- Integration point: `_execute_summary()` prepends context block to instructions for non-SDK profiles only; SDK path unchanged
- Dependencies: slices 161 (summary step) and 164 (profile-aware routing), both complete

**Design decisions:**
- Context prepended to instructions (not a separate system message) — keeps `capture_summary_via_profile` interface unchanged across providers
- Full artifact contents injected, not metadata summaries — the summary model's job is to summarize
- No YAML configuration — context injection is unconditional for non-SDK profiles
- `match/case` on `ActionType` enum for extraction dispatch, not string labels

**Status:**
- Phase 4 complete. Ready for Phase 5 (task breakdown).

---

## 20260410

### Slice 163: Pipeline Run Summary Persistence and Restore — Phase 5 Task Breakdown Complete

**Completed:**
- Created `user/tasks/163-tasks.pipeline-run-summary-persistence-and-restore.md` (158 lines, 14 tasks)
- Tasks cover: source verification (T1), emit.py changes (T2–T4), _project threading (T5–T6), commit (T7), summary_instructions --restore (T8–T9), summary.md --restore branch (T10), run.md alignment (T11), commit (T12), verification (T13), slice completion (T14)
- Test-with pattern: T4 follows T3, T6 follows T5, T9 follows T8
- Review: PASS (minimax). One NOTE addressed: T11 updated to remove stale `_precompact-hook` reference (removed in slice 162); uses `cf status` for project name resolution instead

**Status:**
- Phase 5 complete. Ready for Phase 6 (implementation).

---

### Slice 163: Pipeline Run Summary Persistence and Restore — Phase 4 Design Complete

**Completed:**
- Created slice design at `user/slices/163-slice.pipeline-run-summary-persistence-and-restore.md`
- Added slice overview to `140-slices.pipeline-foundation.md` as entry 23 (index 163)
- Fixed `run.md` clipboard bug: summary action handler now uses `pbcopy`/`xclip`/`wl-copy` via Bash instead of telling the user to copy manually

**Design decisions:**
- Default `emit: [file]` path: `~/.config/squadron/runs/summaries/{project}-{pipeline}.md` (latest-only overwrite)
- Restore via `/sq:summary --restore` — reads most recent summary for current project, no run-id needed
- Project name resolved from CF via `gather_cf_params()` (existing helper)
- Prompt-only `run.md` handler writes to same conventional path via Bash
- `_project` threaded as internal param through `ActionContext` during pipeline init

**Status:**
- Phase 4 complete. Ready for review, then Phase 5 (task breakdown).

---

### Slice 152: Pipeline Documentation and Authoring Guide — Phase 5 Task Breakdown Complete

**Completed:**
- Created `user/tasks/152-tasks.pipeline-documentation-and-authoring-guide.md` (172 lines, 14 tasks)
- Tasks cover: source artifact verification, `docs/PIPELINES.md` creation (Quick Start, YAML Grammar, Step Type Catalog, Action Type Catalog, Model Resolution, Configuration Surface, Built-in Pipelines, Custom Pipeline, Prompt-Only Mode), README.md update, final verification walkthrough, and DEVLOG
- Verification tasks follow each major section (T1 verifies source before writing; T12 runs the full design walkthrough; T13 verifies README)
- No code changes in this slice — documentation only

**Key notes:**
- T1 (source verification) must be completed before writing documentation — particularly to confirm ActionType enum, registered step types, and built-in pipeline file list match the slice design
- The YAML quoting footgun for parameter placeholders must be prominent in the grammar section
- `test-pipeline.yaml` and `app.yaml` in pipelines/ are not for user documentation; exclude from the built-in pipelines table

**Status:**
- Phase 5 complete. Ready for Phase 6 (Slice Execution).

---

### Slice 154: Prompt-Only Loops — Phase 5 Task Breakdown Complete

**Completed:**
- Created `user/tasks/154-tasks.prompt-only-loops.md` (260 lines, 19 tasks)
- Tasks follow test-with pattern: each implementation task is immediately followed by its tests before the next implementation task
- Commit checkpoints placed after coherent logical units (state model, state manager methods, render function, each CLI handler, integration test, closeout)
- No schema version bump needed — `LoopContext` additive with `None` default on `RunState`
- Key implementation sequence: `LoopContext` model → `StateManager` loop methods → `LoopInstructionContext` + `render_each_step_instructions()` → `executor.py` rename → `_handle_prompt_only_init` → `_handle_prompt_only_next` → `_handle_step_done` → integration test → verification walkthrough

**Status:**
- Phase 5 complete. Ready for Phase 6 (Slice Execution).

---

### Slice 154: Prompt-Only Loops — Design Complete (Refreshed)

**Completed:**
- Recreated slice design document at `user/slices/154-slice.prompt-only-loops.md` (previous version was deleted from working tree)
- Design refreshed to reflect current codebase state: schema v3 (no version bump needed — `LoopContext` is additive with `None` default), existing `CompactSummary` pattern, `ExecutionMode` enum
- Core design unchanged from original: flatten `each` loop iterations into prompt-only instruction stream via `LoopContext` state tracking
- Key implementation points: `LoopContext` Pydantic model on `RunState`, `render_each_step_instructions()` in prompt renderer, loop-aware `--step-done` advancement, cached collection items in state for deterministic resume
- Slice plan entry at `140-slices.pipeline-foundation.md` already has materialized index (154) and design-complete link

**Status:**
- Design complete. Ready for Phase 5 (Task Breakdown).

---

## 20260407

### Slice 157: PreCompact Hook for Interactive Claude Code — Phase 6 Implementation Complete

**Completed:**
- All 15 tasks (T1–T15) in `user/tasks/157-tasks.precompact-hook-for-interactive-claude-code.md` implemented and marked complete.
- New shared module `src/squadron/pipeline/compact_render.py` with `LenientDict` + `render_with_params`, extracted from `actions/compact.py`. Both the compact action and the PreCompact hook consume it.
- New hidden Typer subcommand `sq _precompact-hook` (registered on the top-level app with `hidden=True`). Not listed in `sq --help`; direct invocation still works. Emits the Claude Code `PreCompact` payload on stdout, always exits 0.
- New module `src/squadron/cli/commands/install_settings.py` with `settings_json_path`, `_load_settings`, `_save_settings`, `write_precompact_hook`, `remove_precompact_hook`, and `_is_squadron_entry`. Squadron owns its entry in `.claude/settings.json` via a `_managed_by: "squadron"` marker; third-party hooks are preserved on both install and uninstall.
- `sq install-commands` / `sq uninstall-commands` extended with `--hook-target` option (default `./.claude/settings.json`). Installation is idempotent; uninstall tidies `hooks.PreCompact` and `hooks` keys when they become empty.
- Two new config keys: `compact.template` (default `"minimal"`) and `compact.instructions` (default `None`). Literal wins at resolve time.
- `_gather_params` uses best-effort `ContextForgeClient()` with `os.chdir` context management (the CF client has no `cwd` kwarg — task file's pseudocode was updated in practice to match the real API). Catches `ContextForgeError`, `ContextForgeNotAvailable`, `FileNotFoundError`, `OSError`.
- Empty CF values (e.g. `slice=""` as the current squadron project reports) are **omitted** from params so `{slice}` renders as a literal placeholder rather than empty text — discovered during smoke testing and fixed in T14.
- README updated with "Interactive `/compact` for Claude Code" section.
- Full test suite: 1315 passed, 0 failures. Pyright: 0 errors. Ruff: clean.

**Commits on `157-slice.precompact-hook-for-interactive-claude-code` branch:**
- `feat: add compact.template and compact.instructions config keys`
- `refactor: extract LenientDict and render_with_params to compact_render module`
- `feat: add hidden _precompact-hook subcommand for interactive Claude Code`
- `feat: add settings.json merge helpers for PreCompact hook install`
- `feat: install PreCompact hook entry during sq install-commands`
- `docs: document PreCompact hook and compact config keys`
- `chore: rename hook helpers to public names to satisfy pyright`
- `fix: omit empty CF params so PreCompact hook preserves placeholders`
- `docs: mark slice 157 PreCompact hook for interactive Claude Code complete` (pending)

**Deviations from task file:**
- Renamed module-public helpers from `_write_precompact_hook` / `_remove_precompact_hook` / `_settings_json_path` to non-underscored names because pyright's `reportPrivateUsage` flagged cross-module usage with leading underscores. Functionally identical; names reflect convention more accurately.
- Tests for T3/T4/T5 and the module file itself were combined into one commit because all three helpers live in the same file; splitting would have been artificial.
- Test T14 revealed the CF empty-string behavior, which was fixed in `_gather_params` with a tiny non-destructive change: only populate `slice` and `phase` when truthy.
- Also moved the `patch_config_paths` fixture from `tests/config/conftest.py` up to `tests/conftest.py` so CLI command tests can reuse it.

**Smoke tested (automatable parts):**
- `sq install-commands` writes the expected `.claude/settings.json` shape.
- `sq _precompact-hook` emits valid JSON with `hookEventName == "PreCompact"`.
- `{slice}` placeholder preserved when CF reports empty slice.
- Literal `compact.instructions` override wins over template.
- `sq --help` hides the command; `sq _precompact-hook --help` still works.
- `sq uninstall-commands` cleanly removes the entry.

**Not verified (requires human in the loop):**
- Step 6 of the verification walkthrough: real `/compact` in an interactive VS Code Claude Code session or `claude` CLI. Flagged in the slice design for follow-up. The hook payload schema (`hookSpecificOutput.additionalContext`) is based on Claude Code docs; if it turns out to differ, the fix is a single line in `precompact_hook.py` plus one test update.

**Status:**
- Slice 157 complete. Slice plan `140-slices.pipeline-foundation.md` slot 157 checked off.
- Branch: `157-slice.precompact-hook-for-interactive-claude-code` — ready for merge to `main` pending the human-driven `/compact` smoke test.

---

## 20260405

### Slice 154: Prompt-Only Loops — Design Complete

**Completed:**
- Created comprehensive slice design document at `user/slices/154-slice.prompt-only-loops.md`
- Detailed design for extending prompt-only executor (slice 153) with collection loop support
- State schema extension: `RunState` with `LoopContext` field for tracking loop progress across `--next` calls
- Loop iteration tracking: Inner steps within `each` blocks named with iteration index (e.g., `design-each-0`, `tasks-each-1`)
- Successive iteration as instruction stream: Caller doesn't need loop awareness, just calls `--next` repeatedly
- Step instruction output format extended: JSON includes `loop_context` with current item data and loop position
- State persistence for loop resume: Saved loop state allows resuming mid-iteration without re-querying collection
- Verification walkthrough with concrete examples: 6-step scenario (3 items × 2 inner steps)
- Integration: Slash command (`/sq:run`) automatically compatible with loops (no changes needed)

**Status:**
- Design complete and ready for Phase 5 (Task Breakdown)
- Slice plan entry updated: `140-slices.pipeline-foundation.md` now marks slice 154 complete with link to design

**Key Design Decisions:**
- **Loop iterations flattened into instruction stream:** Progressive `--next` calls return successive iteration steps as if sequential. Caller logic unchanged.
- **LoopContext in RunState:** Tracks current item, item index, completed items, total items. Allows mid-loop resume without re-execution or re-querying.
- **Step naming with iteration index:** `{step_name}-each-{item_index}` ensures uniqueness and traceability across iterations.
- **Prompt-only loop output includes item data:** JSON `loop_context` field contains the bound item's resolved fields (e.g., `slice.index: "151"`).
- **No convergence strategies in prompt-only mode:** Falls back to basic max-iteration (inherited from slice 149). Convergence is SDK executor (slice 155) scope.
- **Variables resolved at instruction-generation time:** Bound item fields like `{slice.index}` are replaced in instruction JSON, not left as placeholders.
- **Collection items persisted in state:** Avoids re-querying CF mid-loop. Enables fast resume and deterministic iteration order.

**Dependencies:**
- Slice 153 (Prompt-Only Pipeline Executor) — prerequisite, extends `render_step_instructions()` and state model
- Slice 149 (Pipeline Executor and Loops) — loop execution logic reference; prompt-only mirrors this behavior
- Slice 150 (Pipeline State and Resume) — extended `RunState` schema with loop context
- Slice 126 (CF Integration) — collection sources (`cf.unfinished_slices()`)

**Architecture Overview:**
- No new modules; extends existing `prompt_renderer.py` with loop awareness
- `LoopContext` dataclass added to `models.py` for state tracking
- `StepInstructions` output extended with `loop_context` field (JSON-serializable)
- `StateManager.record_step_done()` enhanced to detect iteration-pattern step names and update `loop_context.completed_items`
- State file schema versioned; v1 (pre-loop) files backward compatible with `loop_context: null`

**Implementation Notes:**
- Effort: 2/5 (low complexity; leverages existing slice 153 patterns and slice 149 loop logic)
- Test strategy: Mock CF queries, verify iteration progression, validate step naming, test state serialization
- No changes needed to `/sq:run` slash command (works transparently with loop iterations)
- Convergence loop strategies generate warning and fall back to max-iteration (same as executor in 149)

