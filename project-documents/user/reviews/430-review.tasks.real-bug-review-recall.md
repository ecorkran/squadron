---
docType: review
layer: project
reviewType: tasks
slice: real-bug-review-recall
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/430-tasks.real-bug-review-recall.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261116
dateUpdated: 20261116
reviewedSha: 37c1b6fcff325a4536616367650551b154c50eab
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 15
effort: xhigh
turns: 16
promptTokens: 787374
cachedTokens: 656714
cacheWriteTokens: 130644
completionTokens: 79394
durationSeconds: 368.3
costUsd: 0.188127
costBasis: provider
squadronVersion: 0.24.31
findings:
  - id: F001
    severity: fail
    category: correctness
    summary: "Two-stage comb composition and finding-id mapping are unspecified"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md"
  - id: F002
    severity: concern
    category: traceability
    summary: "Task 1 cites design-gap bullets the Context Summary does not contain"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md"
  - id: F003
    severity: concern
    category: scope
    summary: "Person-vs-person precedence is a new rule with no design basis"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:212"
  - id: F004
    severity: concern
    category: correctness
    summary: "The D11 recipe's `luna` comb does not match the measured comb"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:186"
  - id: F005
    severity: concern
    category: coverage
    summary: "No command-level test for the D11 \"run prints its bound\" criterion"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md"
  - id: F006
    severity: concern
    category: sizing
    summary: "Task 8 is too large for one commit"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md"
  - id: F007
    severity: concern
    category: sequencing
    summary: "Task 8 defers part of its output to a Task 15 commit that does not exist"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md"
  - id: F008
    severity: concern
    category: sizing
    summary: "Task 13 bundles four grading formats, an overrides file and precedence rules"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md"
  - id: F009
    severity: note
    category: traceability
    summary: "The set-list markdown is not in the design and has no consumer"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md"
  - id: F010
    severity: note
    category: traceability
    summary: "Several modules are missing from the design's component table"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:92-107"
  - id: F011
    severity: note
    category: coverage
    summary: "Task 20's uncombed baseline of 14 is unverified"
    location: "project-documents/user/reference/review-recall-results/RESULTS.md:108"
  - id: F012
    severity: note
    category: commit-cadence
    summary: "One commit marker covers six tasks"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md:203"
  - id: F013
    severity: note
    category: sizing
    summary: "Tasks 2a–2c are granular"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md"
  - id: F014
    severity: pass
    category: coverage
    summary: "Coverage of criteria and failure modes"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md"
  - id: F015
    severity: pass
    category: traceability
    summary: "Named code and data references resolve"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md"
  - id: F016
    severity: pass
    category: coverage
    summary: "No load-test tier required"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md"
---

# Review: tasks — slice 430

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] Two-stage comb composition and finding-id mapping are unspecified

Task 12 imports the `luna-r+opus-high` chain from "decisions from the stored output via Task 9's parser; missing ids UNDECIDED". Task 16 says stage-one `UNDECIDED` is not sent to stage two. Task 21 renders `F1..Fn` in "the comb.py render format". The hand-run data does not behave that way:
- Stage two receives only the refs stage one kept (`comb.py:83-86`).
- Findings are renumbered by position (`comb.py:50-57`, `:100`). The F-ids map back to refs only through the stored `refs` object (`:123`).
- Stage-one drops are written as `P{n}` DROP entries in the `decisions` dict (`:117-119`, `:124`), not in `raw_output`.

Consequences: (a) stage-two F-ids must be mapped to original finding ids through `refs`, or decisions attach to the wrong findings; (b) a stage-one drop is absent from stage two's output, so the "missing → UNDECIDED" rule would wrongly make it UNDECIDED; it must be DROP in the chain. The design's "imports directly" (D2, line 188) and "passes findings through by id" (D3, line 211) are not true of the hand-run files without this mapping. The Task 12 test that checks "chain key has two parts" does not catch it.

Fix: state a chain-composition rule in Tasks 12, 16 and 23a (stage-one DROP → DROP, UNDECIDED → UNDECIDED, KEEP → stage-two verdict via id map). Have Task 12 map through the stored `refs`. Have Task 21 label findings by their `finding_id`, not by position. Add a test: stage one keeps two findings, and stage-two decisions land on those ids while the rest stay DROP.

### [CONCERN] Task 1 cites design-gap bullets the Context Summary does not contain

Task 1 says to write "each design-gap bullet in the Context Summary" and lists D1, API Contracts, the D3 person-labeler rule, and a Non-functional line. The Context Summary has bullets for payload homes, the combs key, scoring modules, lock name, timeout refusal, pair seed, entry selection, overrides path, slash-command parity and stale text. It has none for D1, API Contracts, the person rule, or the Non-functional line. An executor cannot write the D1 or API Contracts gap from the text given. Add those bullets with their content, or remove the items from Task 1.

### [CONCERN] Person-vs-person precedence is a new rule with no design basis

D3 says only "Precedence: person over import passes." Task 13 adds "among person labelers the newest `updated` wins", with a test, and Task 1 would write it into D3. No success criterion needs it, and it settles a question the design left open. Take it to the PM as a decision, or drop it and list a person-vs-person disagreement as a conflict, as imports already do.

### [CONCERN] The D11 recipe's `luna` comb does not match the measured comb

D2's example and the D11 recipe (`haiku-sol-luna-opus`, Task 10) use comb `luna`. In RESULTS.md the measured comb is `luna-r` (14/14 known kept, line 117; two-stage `luna-r+opus-high`, line 127). Plain `luna` is a Codex reviewer alias (line 32). The first live recipe would then run a different alias from the one measured, and imported `luna-r` entries would never match it. Name the comb `luna-r` in D2, D11 and Task 10, after confirming `luna-r` is a registered alias. I did not check the alias registry.

### [CONCERN] No command-level test for the D11 "run prints its bound" criterion

The design criterion (slice design line 519) says `run` with the D11 recipe on `real-bugs-nonsquadron` prints its bound. Task 24 tests the plan function on that set. Task 27 tests bound printing with other fixtures. Task 30 skips walkthrough step 7 because it spends money. No task invokes `run` with the committed recipe and set. Add a Task 27 test that calls `run` with fake services, the committed `haiku-sol-luna-opus.yaml` and the nonsquadron set. It should assert the bound line prints before the first call and that no call is made. No model call is involved.

### [CONCERN] Task 8 is too large for one commit

Task 8 hand-writes 17 case files, reads each repo's `origin` remote and head manifest, captures `proof_files.json` for every proof, writes four set lists, and adds a parser test. Those reads depend on repos on the PM's machine, and one failure blocks the whole commit. Split it: 8a the 10 original cases, 8b the 7 batch-2 cases, 8c the set lists and their test. Each part gets its own check.

### [CONCERN] Task 8 defers part of its output to a Task 15 commit that does not exist

Task 8's success line says gate-found locations "are added in Task 15's commit". Task 15 has no `**Commit**:` marker; its code lands in the commit after Task 20. Task 8's `extra_locations` are also known incomplete until Task 15's gate test runs. Give Task 15 its own marker after its gate test passes, and make the Task 8 wording say the extras are finalized there.

### [CONCERN] Task 13 bundles four grading formats, an overrides file and precedence rules

Task 13 covers four pass formats with different schemas (`issues`/`members`, `matched`/`new_issues`, and `matched` refs to issue ids), the merge rule and conflict listing, hit labels, a new overrides file with its own schema, two precedence rules and five tests. Split it into 13a (the four passes, labels, merge, conflicts) and 13b (overrides file and person precedence).

### [NOTE] The set-list markdown is not in the design and has no consumer

Task 8 creates `user/reference/review-recall-sets.md`, which only a test parses. The design has `cases add` take file lists (walkthrough step 1: "repeat with the file lists"), and D1 rejects markdown parsing for cases. Either add the sets file to the design and have the walkthrough use it, or keep the lists in the test only.

### [NOTE] Several modules are missing from the design's component table

Tasks 22, 23b and 25 add `stage_identity.py`, `leak_check.py` and `run_loop.py`. None appears in the table. Task 16's `scoring_metrics.py` and `scoring_paired.py` are covered by the Context Summary but not the table. Task 1 should add them.

### [NOTE] Task 20's uncombed baseline of 14 is unverified

Task 20 asserts "against 14 for the same fan-out uncombed" (task file line 200). The design gives only the four comb figures. A text search of RESULTS.md for "uncombed", "without a comb" and "no comb" found nothing. Confirm the figure from the data, or drop the assertion.

### [NOTE] One commit marker covers six tasks

The marker after Task 20 covers the hit rule, scoring, metrics, paired intervals and report. Each part is tested, so this is allowed. A marker after Task 18 would give a reviewable commit point for the scoring work.

### [NOTE] Tasks 2a–2c are granular

Each of the three record-model tasks is one module with one test file, under a shared convention. Merging them into one task would cut three headers and three commit-cadence decisions. Optional.

### [PASS] Coverage of criteria and failure modes

Every design success criterion has a task and test, except the D11 command-level bound (above). The "18th case is one YAML file" criterion is covered only implicitly by Task 7's happy path. Every D8 row in both tables has a task that asserts its outcome and log. Tests follow their implementation in the same task. The dependency order has no cycles. Task 22 deliberately comes after Task 20, with Task 20's report switched to the live resolver later.

### [PASS] Named code and data references resolve

I confirmed by search: `read_effort_sent`, `check_review_timeout`, `pair_seed`, `compare_pair`, `MIN_PAIRED_CASES` (5, as the Context Summary says), `BenchmarkLock.acquire`, `resolve_alias_profile`, `run_auth_check`, `build_leak_rules`, `uv_cache_dir`, `installed_package_location`, `map_historical_category`, `template_content_hash` (returns `str | None`, which Task 22 handles), `get_all_aliases`, `resolve_sq_path`, `ReviewBudget`, `GradeCapReached`, `EXIT_CAP_REACHED`, the `LeakVerdict` members, `TemplateOutput.DECISIONS`, `HistoryFreeSandbox`, `ScrubbedEnvironment`, `CredentialGrant`, `ReviewerRef`. Files confirmed: `cli/commands/review.py`, `config/keys.py`, `commands/sq/benchmark.md`, `CHANGELOG.md`, `tests/benchmark/slice_repos.py`, `tests/benchmark/test_config_keys.py`, `comb.py`, `comb.yaml`. The Task 30 `git diff --stat` checks are therefore not vacuous.

### [PASS] No load-test tier required

The design restates no latency, throughput or resource NFR. Recall runs serially by design (D9), so no `tests/load/` task or CI gate is needed.

### Run Digest

- Response length: 11427 chars
- Response is newline-free: no
- Tool calls made: 15
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 16
- Tokens — prompt / cached / cache write / completion / reasoning: 787374 / 656714 / 130644 / 79394 / not computed
- Duration: 368.3 s
- Cost: $0.19 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 16
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 16
- Finding-shaped matches — surviving validation: 16
