---
docType: review
layer: project
reviewType: slice
slice: producer-replay-and-pairwise-judging
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/177-slice.producer-replay-and-pairwise-judging.md
aiModel: xiaomi/mimo-v2.6-pro
aiProfile: openrouter
status: complete
dateCreated: 20261016
dateUpdated: 20261016
reviewedSha: 5601c3c4b2c92b7c589719ba446f0dc8b798fde6
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 19
turns: 13
promptTokens: 853734
cachedTokens: 749696
completionTokens: 26134
reasoningTokens: 23140
durationSeconds: 775.8
costUsd: 0.070992
costBasis: alias_pricing
squadronVersion: 0.22.0
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Judge call has no hang/timeout failure mode"
    location: "project-documents/user/slices/177-slice.producer-replay-and-pairwise-judging.md:302-303"
  - id: F002
    severity: concern
    category: integration
    summary: "`--run-id` seam claim mismatches `_run_pipeline`'s resume semantics"
    location: "project-documents/user/slices/177-slice.producer-replay-and-pairwise-judging.md:69"
  - id: F003
    severity: concern
    category: under-specification
    summary: "Orphan sweep's \"live lock file\" is referenced but never defined"
    location: "project-documents/user/slices/177-slice.producer-replay-and-pairwise-judging.md:156"
  - id: F004
    severity: note
    category: documentation
    summary: "Plan entry 33 is stale on mechanism and effort"
    location: "project-documents/user/architecture/140-slices.pipeline-foundation.md:120"
  - id: F005
    severity: note
    category: provenance
    summary: "Prompt identity semantics under-specified in two places"
    location: "project-documents/user/slices/177-slice.producer-replay-and-pairwise-judging.md:242-244"
  - id: F006
    severity: pass
    category: structural
    summary: "Seam citations, dependency direction, and plan coverage verified"
    location: "project-documents/user/slices/177-slice.producer-replay-and-pairwise-judging.md"
---

# Review: slice — slice 177

**Verdict:** CONCERNS
**Model:** xiaomi/mimo-v2.6-pro

## Findings

### [CONCERN] Judge call has no hang/timeout failure mode

D10 enumerates "Judge dispatch raises" and "no verdict line" but not a judge call that **hangs**. The judge is this slice's most expensive new message type — `one_shot_dispatch_with_telemetry` calls growing with k² (D5, line 191) — and I verified the seam carries no wall-clock bound; the project itself documents the absence as an open gap (`300-slices.eval-actions-llm-as-judge-scoring.md` Future Work 4: "Per-Call Provider Timeout (140) … so an unattended judge cycle whose provider *hangs* … instead of stalling indefinitely"). The `sq run` hang row (line 301) leans on 174's stall bounds, which cover SDK session turns inside the subprocess — not this path. `sq replay judge --yes` (D10's "Not interactive" row implies unattended `--yes` use) would therefore stall indefinitely on a hung provider. Also unspecified: a pair whose first call succeeds and whose swapped call raises — "that pair not recorded" means the spent call's cost is lost and both calls repeat on re-run; say so explicitly. Add a D10 row with a per-call bound (or an explicit reliance on Ctrl-C + the confirmation prompt as the accepted strategy) and name the half-pair behavior.

### [CONCERN] `--run-id` seam claim mismatches `_run_pipeline`'s resume semantics

"`_run_pipeline(..., run_id=...)` already takes a run id. Only the CLI option is new" is inaccurate. I verified in `src/squadron/cli/commands/run.py:284-308` that a provided `run_id` is the **resume** path: the docstring states "`init_run` is skipped so no new state file is created", `resuming = run_id is not None`, and `RunHeartbeat(…, claim=resuming)` claims a state file that must already exist. Implemented as literally specified, a fresh replay run creates no run state, the observer writes fail-soft with warnings, `finalize` raises `FileNotFoundError`, and the runner's read-back lands in D10's own `no_run_state` row — for every config. The caller-chosen-id creation path exists one level down (`StateManager.init_run(…, run_id=…)` at `src/squadron/pipeline/state.py:332-336`) but `_run_pipeline` never routes there when an id is supplied, and no collision check exists today ("fails rather than overwriting it" is new behavior). D4 (line 168) should state the real change: thread the chosen id into `init_run`, add the fail-on-existing check, and keep `--run-id` semantics distinct from `--resume` — not "only the CLI option is new".

### [CONCERN] Orphan sweep's "live lock file" is referenced but never defined

D3's sweep removes "sandbox directories with no live lock file", but nothing in the design says `ReplaySandbox` writes a lock file, where it lives, what it contains, or what makes it "live" (pid + hostname? heartbeat?). This unnamed signal is load-bearing for the cleanup guarantees (Success Criteria 2; D10's "next run's sweep retries") and is the only thing preventing `sq replay run`'s startup sweep from deleting a sandbox belonging to a concurrent or just-starting invocation — the "Concurrent replays" exclusion (line 55) covers configs within one set, not two overlapping `sq replay` processes. There is an in-repo precedent with exactly this shape — `src/squadron/codehost/worktree.py` (`WorktreeLock`, `_is_orphan`, `sweep_orphans`, which "never raises") — that the design does not reference. Name the lock format and liveness rule, or state that the codehost lock/sweep pattern is borrowed.

### [NOTE] Plan entry 33 is stale on mechanism and effort

The entry prescribes "throwaway worktrees" and Effort 3/5. The design correctly rejects worktrees for a history-free sandbox (D3 — a worktree shares refs, so a tool-using producer could read the answer from `main`) and itself estimates the scope at 4/5 (line 439). Both deviations are sound, but the plan entry should be updated so it stops advertising a mechanism the design disproved and a budget the design exceeds.

### [NOTE] Prompt identity semantics under-specified in two places

(a) The sha256's input is unstated. `_resolve_prompt` returns the prompt *after* checkpoint-override and pre-emption-fragment composition (`_apply_override` / `_apply_pre_emption_fragment` in `pipeline/actions/dispatch.py`); if the hash covers only the branch-resolved text, two dispatches that told the model different things hash identically. Say "hash the delivered prompt". (b) "Template revision is identified by `(cf_version, guide_version)`" misses squadron-side prompt-composition changes (revise guidance, rules blocks, prompt template edits) — `squadron_version` is recorded on `ProducerReplay` but not in `metadata["prompt"]`, so a squadron release that changes prompts pools silently again, which is exactly the defect the plan entry ("prompt-template identity per dispatch, which 176 pools") assigns this slice to fix.

### [PASS] Seam citations, dependency direction, and plan coverage verified

Every code seam named in Dependencies/Interfaces Required exists at (or within a few lines of) its cited location, including `GitHistory`/`first_added`/`show`, `ProducerKey`/`extract_units`, the `RECORD_TYPE_*` + `MetrologyRecord` + `write_*`/`list_*` pattern at `metrology/models.py:28-31,278-294`, `metrology.min_evidence_n`, and `_resolve_prompt`'s four prompt sources matching D8's `source` enum. The subprocess decision is justified against the architecture's cwd-based CF and SDK session model, the new record types follow 320's no-migration convention with `_SCHEMA_VERSION` unchanged, and the additive run-state metadata matches the "defaults load unchanged" precedent from 176. Proportionality holds: each mechanism (sandbox + sweep, order-swap judge, BT fit, confirmation prompts with dispatch bounds) traces to a plan-entry commitment or a named risk, and the Excluded list plus the explicit non-adoption of an eval tool hold the slice to entry 33's scope.

## Response (20261016)

I checked all five findings against the code and accepted each one. They are fixed in `da0749f4`.

- **F001: accepted.** `one_shot_dispatch_with_telemetry` has no bound. D5 now wraps each judge call in `asyncio.wait_for`, bounded by a new key `metrology.judge_timeout_s`. It copies `metrology.audit_timeout_s` (`metrology/audit.py:610,682`), and its default lives only in `config/keys.py`. D5 also defines half-recorded pairs: no record is written, the spent call's cost is logged at WARNING, and both calls repeat on the next run. D10 gains a row for each case.
- **F002: accepted.** Confirmed at `cli/commands/run.py:284-308`: a `run_id` there is the resume path. D4 now adds a `new_run_id` parameter that goes to `init_run(..., run_id=...)`. Passing both ids is a `ValueError`, and `init_run` raises `FileExistsError` on an existing id. No `src/` caller passes an id today.
- **F003: accepted.** D3 now borrows the `codehost/worktree.py` lock pattern: a pid plus start time, live only while that process exists with that start time. The sweep never raises and leaves sandboxes with a live lock alone. If the helpers are tied to `PullRequestRecord`, they are extracted into a shared module rather than copied.
- **F004: accepted.** Plan entry 33 now describes the history-free sandbox, and its effort is raised to 4/5.
- **F005: accepted.** (a) The hash covers the delivered prompt, taken after `_apply_override` and `_apply_pre_emption_fragment` (`dispatch.py:671`). (b) `squadron_version` is added to `metadata["prompt"]`, and template revision is now `(squadron_version, cf_version, guide_version)`.

### Run Digest

- Response length: 7802 chars
- Response is newline-free: no
- Tool calls made: 19
- Tool calls failed: 1
- Stop reason: stop
- Output budget: 131072 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 95669
- Effort: backend default
- Turns: 13
- Tokens — prompt / cached / cache write / completion / reasoning: 853734 / 749696 / not computed / 26134 / 23140
- Duration: 775.8 s
- Cost: $0.07 (alias_pricing)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
