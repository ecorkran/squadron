---
docType: review
layer: project
reviewType: tasks
slice: strict-type-checking-over-the-test-suite
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: derived
sourceDocument: project-documents/user/tasks/914-tasks.strict-type-checking-over-the-test-suite-2.md
aiModel: z-ai/glm-5.3-flash
status: complete
dateCreated: 20260928
dateUpdated: 20260928
reviewedSha: 71bd75d55c483b99321610b7e16a1e4e8991e28f
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 13
squadronVersion: 0.14.0
findings:
  - id: F001
    severity: concern
    category: coverage
    summary: "`tests/pipeline/intelligence/fan_in/` is in Part C's territory but named by no task, and carries `# type: ignore` comments criterion 8 requires dispositioned"
    location: "project-documents/user/tasks/914-tasks.strict-type-checking-over-the-test-suite-2.md:172-181"
  - id: F002
    severity: concern
    category: documentation
    summary: "Context Summary states the quoted error counts are post-Part-1, while the tasks quoting them say they are pre-Part-1"
    location: "project-documents/user/tasks/914-tasks.strict-type-checking-over-the-test-suite-2.md:25-27"
  - id: F003
    severity: note
    category: documentation
    summary: "Standing-rules cross-reference points Part C's commit at the wrong task number"
    location: "project-documents/user/tasks/914-tasks.strict-type-checking-over-the-test-suite-2.md:54-55"
  - id: F004
    severity: note
    category: traceability
    summary: "D6's \"record it\" names no destination inside this file"
    location: "project-documents/user/tasks/914-tasks.strict-type-checking-over-the-test-suite-2.md:40-43"
  - id: F005
    severity: note
    category: task-granularity
    summary: "Task 3.9 is the widest task in the file (~24 files), but the breakdown's own structure forces it"
    location: "project-documents/user/tasks/914-tasks.strict-type-checking-over-the-test-suite-2.md:246-260"
  - id: F006
    severity: pass
    category: traceability
    summary: "All 11 slice success criteria trace to tasks, with no orphaned criterion and no scope creep"
    location: "project-documents/user/tasks/914-tasks.strict-type-checking-over-the-test-suite-2.md:158-165"
  - id: F007
    severity: pass
    category: sequencing
    summary: "Commit cadence and CI gating are explicit rather than implicit"
    location: "project-documents/user/tasks/914-tasks.strict-type-checking-over-the-test-suite-2.md:158-165"
---

# Review: tasks — slice 914

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3-flash

## Findings

### [CONCERN] `tests/pipeline/intelligence/fan_in/` is in Part C's territory but named by no task, and carries `# type: ignore` comments criterion 8 requires dispositioned

Part C is titled "`tests/pipeline` Remainder (excl. Part B's 4 pipeline files)" — i.e. it claims everything under `tests/pipeline` not in Part B — but its table enumerates only `actions/` (7 files), `intelligence/pools/` (2), `steps/` (3), and top-level (33), summing to the stated 45 files with no row for `intelligence/fan_in/`. That subdirectory exists (verified: `tests/pipeline/intelligence/fan_in/test_reducers.py`) and carries 8 `# type: ignore` comments at lines 53, 54, 99, and 105–109. File 3's Part E ("Everything Else") lists no pipeline entry either, so no task heading in any of the three files names this file. Whether it surfaces baseline errors is unverified (I cannot run pyright from this review), which leaves two paths: if it surfaces errors, only Task 3.9's directory-global success criterion ("0 errors remaining anywhere under `tests/pipeline/`") catches it implicitly, since the file appears in no task's scope statement; if its errors are fully hidden behind those 8 ignores, it never enters file 1's exclude seed, is never touched by any fixing task, and is dispositioned only when file 3's Task 6.2 audit grep fails — late, with no module-scoped success criterion, no exclude-entry step, and no per-part gate after the fix. The root cause is D8's standing rule being conditioned on "any `# type: ignore` in a file you touch": a file whose only pyright signal is hidden ignores is never touched. Recommend giving `intelligence/fan_in/` an explicit home (Task 3.2's or Task 3.9's scope, or its own task), and/or rewording the D8 standing rule to also claim files carrying `# type: ignore` that report zero surfaced errors.

### [CONCERN] Context Summary states the quoted error counts are post-Part-1, while the tasks quoting them say they are pre-Part-1

The sentence "Each file's error count below is what remained *after* Part 1's global fixes, so it may already be lower than the design's original figures" contradicts the tasks that carry those figures. Task 2.5 says "34 errors **before** Part 1; 10 were `reportPrivateUsage` (already resolved by Task 1.8–1.10) and 7 `reportUnknownLambdaType` (already resolved by Task 1.6)" — a post-fix count could not contain those shares. Task 2.9 likewise: "28 errors before Part 1, 16 of them `reportUnknownLambdaType` (already resolved by Task 1.6)". The counts are the pre-fix figures from file 1's 1270-error baseline (file 1's Top-10 table, measured at `caedf4e5` before Tasks 1.5–1.10 ran), annotated per task with the shares Part 1 already cleared. The "may already be lower than the design's original figures" clause is also directionally wrong for the mechanism it names: `test_provider.py` is 168 vs the design's 96 and `test_review_profile.py` is 66 vs 41 — those moves came from suite drift between 20260817 and 20260927, not from Part 1's fixes. Practical impact is contained — Tasks 2.3 and 2.5–2.10 each instruct re-measuring fresh, and Tasks 2.1/2.2 quote only rules Part 1's global passes don't touch (`reportArgumentType`; `reportUnknown/MissingParameterType`) — but this document's entire epistemology is "which baseline do you trust," and a junior AI comparing its fresh measurement against "the count below" deserves a correct framing. Reword to: pre-Part-1 figures from file 1's baseline, annotated with the shares Part 1's global passes already cleared.

### [NOTE] Standing-rules cross-reference points Part C's commit at the wrong task number

"do **not** commit until this file's gate tasks (2.11, **3.9** in file 3's numbering...)" — Part C's gate is Task 3.10; Task 3.9 is the straggler-fixing task that must precede the commit. The trailing "see each Part's own gate task" and Task 3.10's explicit "Commit Part C as one commit" make the correct checkpoint recoverable, so this is cosmetic, but the parenthetical should read 3.10.

### [NOTE] D6's "record it" names no destination inside this file

The standing rule says a wrong production signature must be "recorded — do not quietly change the test" and that "zero found is a valid, recorded outcome," but not where. The destination is two hops away: design D6 says "the slice's completion notes," and file 3's Task 6.3 fills that table. Since Task 2.1 concentrates the D6 work (168 `reportArgumentType` sites, called "the most likely to be real findings") and file 3's audit may run in a later session, add one clause naming the destination (e.g. "record it in the slice design's Completion Summary section") to the standing rule so findings survive the session boundary.

### [NOTE] Task 3.9 is the widest task in the file (~24 files), but the breakdown's own structure forces it

~24 top-level files at ≤5 errors each with effort 3/5, an explicit "re-derive the exact current list from a fresh `uv run pyright --outputjson`" instruction, and a directory-global success criterion. Its size is a consequence of D2's per-part commit unit — everything left in the directory must land before Task 3.10's gate — not of sloppy splitting, and its named files all exist (verified against `tests/pipeline/`). Flagged only so the executor knows this is the one task where standing-rule application must be batched across many files; the named list includes `type: ignore`-heavy files (`test_compact_integration.py`, `test_dispatch.py`) where the D8 disposition dominates the annotation work.

### [PASS] All 11 slice success criteria trace to tasks, with no orphaned criterion and no scope creep

Criterion 1/2 → per-file exclude-removal standing rule, Task 2.11's "all 10 files' entries gone / no directory-level entry left," Task 3.10's `grep -n "tests/pipeline"`, and file 3 Task 5.9 (exactly one entry, `agent.py`); 3 → D1 standing rule plus file 3 Task 6.2's `executionEnvironments` grep; 4 → file 3 Task 6.1's walkthrough eyeball; 5 → file 1 Task 1.14; 6 → file 1 Task 1.4's recorded floor (4781 passed / 4 skipped) enforced at every gate; 7 → every gate task; 8 → D8 standing rule plus file 3 Task 6.2; 9 → file 1 Tasks 1.8–1.10, with file 2's fallback note routing any missed `reportPrivateUsage` back through Task 1.8's rule and into file 3's summary; 10 → D6 standing rule plus file 3 Task 6.3 (zero recorded if zero); 11 → file 3 Task 6.3. Repo state checked: `pyproject.toml:94-95` still has `include = ["src"]` and the deferral comment, so file 2's per-file exclude-removal rule correctly presumes the seed file 1 Task 1.14 creates. Every file and count file 2 names was verified to exist. No task reaches beyond annotation, dead-code deletion, exclude bookkeeping, or the D6/D4/D8 dispositions the design mandates.

### [PASS] Commit cadence and CI gating are explicit rather than implicit

One commit per part (Tasks 2.11 and 3.10), following file 1's two commits and preceding file 3's — no end-batching, with per-file `git add` and an explicit "do not commit until this file's gate tasks" rule keeping pyright green at every landed commit per D2. CI enforcement of criteria 1–2 is concrete, not assumed: `.github/workflows/ci.yml:36` runs `uv run pyright` with no path argument (verified), so the widened include is gated from file 1's Task 1.14 onward with no workflow edit, and file 1 Task 1.1 verifies that fact instead of trusting the design's Migration Plan.

### Run Digest

- Response length: 9267 chars
- Response is newline-free: no
- Tool calls made: 13
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 128000 tokens
- Reasoning characters: 67285
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7

### Raw Response

## Summary
[overall assessment: CONCERNS]

Cross-referencing all 11 success criteria in the slice design against the three task files (this is part 2 of 3, so file 1 and file 3 were read to determine where each criterion lands): every criterion traces to at least one task, task ordering respects D2's heaviest-first/per-directory discipline with no circular dependencies, per-task success criteria are concrete enough for a junior AI (0 errors + `exclude` entry removed + named pytest command), commit checkpoints land at each part boundary rather than batched, and there is no scope creep — no task adds tests, builds a fixture-factory framework, or relaxes a rule, matching the design's out-of-scope list. Two CONCERNS remain: a subdirectory of `tests/pipeline` is claimed by Part C's title but named by no task anywhere in the breakdown, and the file's Context Summary misdescribes its own baseline figures as post-Part-1 when the tasks they annotate quote pre-Part-1 counts.

## Findings

### [CONCERN] `tests/pipeline/intelligence/fan_in/` is in Part C's territory but named by no task, and carries `# type: ignore` comments criterion 8 requires dispositioned
location: project-documents/user/tasks/914-tasks.strict-type-checking-over-the-test-suite-2.md:172-181
category: coverage

Part C is titled "`tests/pipeline` Remainder (excl. Part B's 4 pipeline files)" — i.e. it claims everything under `tests/pipeline` not in Part B — but its table enumerates only `actions/` (7 files), `intelligence/pools/` (2), `steps/` (3), and top-level (33), summing to the stated 45 files with no row for `intelligence/fan_in/`. That subdirectory exists (verified: `tests/pipeline/intelligence/fan_in/test_reducers.py`) and carries 8 `# type: ignore` comments at lines 53, 54, 99, and 105–109. File 3's Part E ("Everything Else") lists no pipeline entry either, so no task heading in any of the three files names this file. Whether it surfaces baseline errors is unverified (I cannot run pyright from this review), which leaves two paths: if it surfaces errors, only Task 3.9's directory-global success criterion ("0 errors remaining anywhere under `tests/pipeline/`") catches it implicitly, since the file appears in no task's scope statement; if its errors are fully hidden behind those 8 ignores, it never enters file 1's exclude seed, is never touched by any fixing task, and is dispositioned only when file 3's Task 6.2 audit grep fails — late, with no module-scoped success criterion, no exclude-entry step, and no per-part gate after the fix. The root cause is D8's standing rule being conditioned on "any `# type: ignore` in a file you touch": a file whose only pyright signal is hidden ignores is never touched. Recommend giving `intelligence/fan_in/` an explicit home (Task 3.2's or Task 3.9's scope, or its own task), and/or rewording the D8 standing rule to also claim files carrying `# type: ignore` that report zero surfaced errors.

### [CONCERN] Context Summary states the quoted error counts are post-Part-1, while the tasks quoting them say they are pre-Part-1
location: project-documents/user/tasks/914-tasks.strict-type-checking-over-the-test-suite-2.md:25-27
category: documentation

The sentence "Each file's error count below is what remained *after* Part 1's global fixes, so it may already be lower than the design's original figures" contradicts the tasks that carry those figures. Task 2.5 says "34 errors **before** Part 1; 10 were `reportPrivateUsage` (already resolved by Task 1.8–1.10) and 7 `reportUnknownLambdaType` (already resolved by Task 1.6)" — a post-fix count could not contain those shares. Task 2.9 likewise: "28 errors before Part 1, 16 of them `reportUnknownLambdaType` (already resolved by Task 1.6)". The counts are the pre-fix figures from file 1's 1270-error baseline (file 1's Top-10 table, measured at `caedf4e5` before Tasks 1.5–1.10 ran), annotated per task with the shares Part 1 already cleared. The "may already be lower than the design's original figures" clause is also directionally wrong for the mechanism it names: `test_provider.py` is 168 vs the design's 96 and `test_review_profile.py` is 66 vs 41 — those moves came from suite drift between 20260817 and 20260927, not from Part 1's fixes. Practical impact is contained — Tasks 2.3 and 2.5–2.10 each instruct re-measuring fresh, and Tasks 2.1/2.2 quote only rules Part 1's global passes don't touch (`reportArgumentType`; `reportUnknown/MissingParameterType`) — but this document's entire epistemology is "which baseline do you trust," and a junior AI comparing its fresh measurement against "the count below" deserves a correct framing. Reword to: pre-Part-1 figures from file 1's baseline, annotated with the shares Part 1's global passes already cleared.

### [NOTE] Standing-rules cross-reference points Part C's commit at the wrong task number
location: project-documents/user/tasks/914-tasks.strict-type-checking-over-the-test-suite-2.md:54-55
category: documentation

"do **not** commit until this file's gate tasks (2.11, **3.9** in file 3's numbering...)" — Part C's gate is Task 3.10; Task 3.9 is the straggler-fixing task that must precede the commit. The trailing "see each Part's own gate task" and Task 3.10's explicit "Commit Part C as one commit" make the correct checkpoint recoverable, so this is cosmetic, but the parenthetical should read 3.10.

### [NOTE] D6's "record it" names no destination inside this file
location: project-documents/user/tasks/914-tasks.strict-type-checking-over-the-test-suite-2.md:40-43
category: traceability

The standing rule says a wrong production signature must be "recorded — do not quietly change the test" and that "zero found is a valid, recorded outcome," but not where. The destination is two hops away: design D6 says "the slice's completion notes," and file 3's Task 6.3 fills that table. Since Task 2.1 concentrates the D6 work (168 `reportArgumentType` sites, called "the most likely to be real findings") and file 3's audit may run in a later session, add one clause naming the destination (e.g. "record it in the slice design's Completion Summary section") to the standing rule so findings survive the session boundary.

### [NOTE] Task 3.9 is the widest task in the file (~24 files), but the breakdown's own structure forces it
location: project-documents/user/tasks/914-tasks.strict-type-checking-over-the-test-suite-2.md:246-260
category: task-granularity

~24 top-level files at ≤5 errors each with effort 3/5, an explicit "re-derive the exact current list from a fresh `uv run pyright --outputjson`" instruction, and a directory-global success criterion. Its size is a consequence of D2's per-part commit unit — everything left in the directory must land before Task 3.10's gate — not of sloppy splitting, and its named files all exist (verified against `tests/pipeline/`). Flagged only so the executor knows this is the one task where standing-rule application must be batched across many files; the named list includes `type: ignore`-heavy files (`test_compact_integration.py`, `test_dispatch.py`) where the D8 disposition dominates the annotation work.

### [PASS] All 11 slice success criteria trace to tasks, with no orphaned criterion and no scope creep
location: project-documents/user/tasks/914-tasks.strict-type-checking-over-the-test-suite-2.md:158-165
category: traceability

Criterion 1/2 → per-file exclude-removal standing rule, Task 2.11's "all 10 files' entries gone / no directory-level entry left," Task 3.10's `grep -n "tests/pipeline"`, and file 3 Task 5.9 (exactly one entry, `agent.py`); 3 → D1 standing rule plus file 3 Task 6.2's `executionEnvironments` grep; 4 → file 3 Task 6.1's walkthrough eyeball; 5 → file 1 Task 1.14; 6 → file 1 Task 1.4's recorded floor (4781 passed / 4 skipped) enforced at every gate; 7 → every gate task; 8 → D8 standing rule plus file 3 Task 6.2; 9 → file 1 Tasks 1.8–1.10, with file 2's fallback note routing any missed `reportPrivateUsage` back through Task 1.8's rule and into file 3's summary; 10 → D6 standing rule plus file 3 Task 6.3 (zero recorded if zero); 11 → file 3 Task 6.3. Repo state checked: `pyproject.toml:94-95` still has `include = ["src"]` and the deferral comment, so file 2's per-file exclude-removal rule correctly presumes the seed file 1 Task 1.14 creates. Every file and count file 2 names was verified to exist. No task reaches beyond annotation, dead-code deletion, exclude bookkeeping, or the D6/D4/D8 dispositions the design mandates.

### [PASS] Commit cadence and CI gating are explicit rather than implicit
location: project-documents/user/tasks/914-tasks.strict-type-checking-over-the-test-suite-2.md:158-165
category: sequencing

One commit per part (Tasks 2.11 and 3.10), following file 1's two commits and preceding file 3's — no end-batching, with per-file `git add` and an explicit "do not commit until this file's gate tasks" rule keeping pyright green at every landed commit per D2. CI enforcement of criteria 1–2 is concrete, not assumed: `.github/workflows/ci.yml:36` runs `uv run pyright` with no path argument (verified), so the widened include is gated from file 1's Task 1.14 onward with no workflow edit, and file 1 Task 1.1 verifies that fact instead of trusting the design's Migration Plan.
