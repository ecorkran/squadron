---
docType: review
layer: project
reviewType: tasks
slice: fix-case-qualification-and-yield-report-keystone
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261106
dateUpdated: 20261106
reviewedSha: 8875b059fdd325957f6122328a27beea2416897e
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 16
effort: xhigh
turns: 17
promptTokens: 795741
cachedTokens: 574148
cacheWriteTokens: 221581
completionTokens: 100838
durationSeconds: 430.5
costUsd: 0.490182
costBasis: provider
runId: run-20261106-tasks-plan-711d0fe6
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Tasks 12 and 13 each need the other's tests to pass"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:163-176"
  - id: F002
    severity: concern
    category: error-handling
    summary: "Stage 7 suite failures and the case-set write have no harness-failure path or test"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:255-273"
  - id: F003
    severity: concern
    category: error-handling
    summary: "A resolver bug and a package import failure both become a case rejection"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:218-219"
  - id: F004
    severity: concern
    category: spec-consistency
    summary: "A missing pyproject.toml and a failed git show look the same to the implementer"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:242-244"
  - id: F005
    severity: concern
    category: coverage
    summary: "No test covers a project-owned delattr, setitem or delitem"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:211-213"
  - id: F006
    severity: concern
    category: completability
    summary: "Task 18 needs two fixture projects that no task creates"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:220"
  - id: F007
    severity: concern
    category: spec-consistency
    summary: "The conftest rule has two readings"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:130"
  - id: F008
    severity: concern
    category: coverage
    summary: "A title edit after the cutoff is not checked"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:98-100"
  - id: F009
    severity: concern
    category: spec-consistency
    summary: "The design correction list omits the qualification_for signature change"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:333-334"
  - id: F010
    severity: concern
    category: ci-gating
    summary: "Task 27's (a)–(d) pins cannot run in CI as written"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:315-316"
  - id: F011
    severity: concern
    category: granularity
    summary: "Task 7 bundles too many deliverables"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:109-122"
  - id: F012
    severity: concern
    category: granularity
    summary: "Task 11 bundles the config, digest, conftest and packaging work"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:149-158"
  - id: F013
    severity: concern
    category: commits
    summary: "Task 9's source is committed under Task 10's `test:` marker"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:137-147"
  - id: F014
    severity: concern
    category: coverage
    summary: "Real-commit test-first pins miss the assertion example"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:315-316"
  - id: F015
    severity: note
    category: completability
    summary: "Task 5's edited-comment fixture may not exist, and there is no fallback"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:84"
  - id: F016
    severity: note
    category: spec-consistency
    summary: "Crossing module naming is not pinned"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:201"
  - id: F017
    severity: note
    category: completability
    summary: "Trace-mode node ids are not in the pinned config"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:40"
  - id: F018
    severity: note
    category: completability
    summary: "The FileStates switch operation is not named"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:172-179"
  - id: F019
    severity: note
    category: commits
    summary: "DEVLOG.md already has uncommitted changes"
    location: "DEVLOG.md"
  - id: F020
    severity: pass
    category: sequencing
    summary: "The 421 gate and branch name are correct"
    location: "project-documents/user/tasks/422-tasks.fix-case-qualification-and-yield-report-keystone.md:49-53"
  - id: F021
    severity: pass
    category: coverage
    summary: "Success-criteria coverage holds, apart from the partial gaps above"
    location: "project-documents/user/slices/422-slice.fix-case-qualification-and-yield-report-keystone.md:368-395"
---

# Review: tasks — slice 422

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Tasks 12 and 13 each need the other's tests to pass

Task 12's test (line 164) collects "at the reference commit of sort_sets" and checks a reference-state `collection_broken` failure (line 165). The only defined way to reach the reference state is `FileStates` in Task 13. Task 13's test (line 176) checks that `collect` after a switch lists the diff-added test, which needs Task 12's `collect`. Fix: have Task 12 build a second sandbox from a checkout of the fix commit and say so in the step, or move the reference-state assertions into Task 13.

### [CONCERN] Stage 7 suite failures and the case-set write have no harness-failure path or test

Task 21 maps `HarnessFailure` and `ProcessTimedOutError` to `harness_error` for stages 3–6 only (line 255). Stage 7, the full-suite repeats at the reference (line 265), has no mapping, and Task 22's tests (lines 268–273) do not cover it. A suite timeout there is the case the design's Technical Requirements name (design line 389). Task 24 also writes the case set (line 286) with no failure test, although the Context Summary says every record write has one (line 44). Extend the mapping to stage 7 with a test, and add a `write_case_set` failure test (BuildHalted, ERROR log) in Task 24.

### [CONCERN] A resolver bug and a package import failure both become a case rejection

Task 18 raises `BoundaryUndecidable` on any non-zero exit, and Task 21 records that as the case-blaming `boundary_undecidable` (line 252). An import failure exits non-zero, but so does any uncaught exception in the resolver's own code. The design treats import failures as rejections (design line 185) and resolver crashes as harness failures (design line 389). Fix: the resolver catches the import error itself and exits with a dedicated code. Any other non-zero exit raises `HarnessFailure`. Add a test for each.

### [CONCERN] A missing pyproject.toml and a failed git show look the same to the implementer

Line 242 reads `pyproject.toml` with `git show` and maps absence to `no_fix_case_adapter`. Line 244 maps a non-zero `git show` to `harness_error`. `git show <sha>:<missing path>` exits non-zero, so the two rules collide. Fix: test presence first with `git cat-file -e <sha>:pyproject.toml`, and treat only other failures as `harness_error`.

### [CONCERN] No test covers a project-owned delattr, setitem or delitem

The design requires coverage of "each patch API" (design line 388). Task 17 wraps `delattr`, `setitem` and `delitem` (line 211), but no test in its list (line 212) has one of them target a project module, class or dict. Add one test for each to `fixfair_project`.

### [CONCERN] Task 18 needs two fixture projects that no task creates

Task 18 tests "a project without `__all__` or scripts" and "a package that fails to import". Task 10 creates only `fixfair_project`, which has both `__all__` and a script. A junior agent would have to invent two projects with uv locks. Add both to Task 10's fixtures.

### [CONCERN] The conftest rule has two readings

The first sentence rejects a conftest only when a parent top-level definition is changed or removed. The second says only added `pytest.fixture` functions and added imports pass. Under the first reading, an added plain helper function passes. The design (line 156) says anything other than added fixtures and imports is `modifies_test_support`. State the second reading in the task and add a test where a conftest adds a plain helper and is rejected.

### [CONCERN] A title edit after the cutoff is not checked

The frozen text includes the title, but the checks cover only the body and included comments (Task 6 line 100, design line 141). The design criterion says an issue "edited after the fix" is rejected (design line 374). The snapshot has no title edit time, so a title-only edit would pass. Either confirm from the Task 5 fixture that `lastEditedAt` moves on title edits, add a title timestamp to `IssueSnapshot`, or narrow the criterion to body and comments as a design change.

### [CONCERN] The design correction list omits the qualification_for signature change

Task 22 gives `qualification_for` a `store` argument (line 267). The design's contract is `qualification_for(case, environment)` (design line 242), and 424 consumes it (design line 394). Task 29's correction list does not include the change. Add it.

### [CONCERN] Task 27's (a)–(d) pins cannot run in CI as written

Task 27 pins cases chosen from a manual `fix-cases build` run, read through `fix-cases show`. That data lives in the local store and needs `gh` access. CI runs plain `uv run pytest` (`.github/workflows/ci.yml:38`), and no workflow sets `GH_TOKEN` or any secret, so the pins would fail there. The task also says there is "no skip". Fix: have each pin name its commit sha and call `qualify_in_sandbox` directly with a hand-built candidate, as the three commits in bullet 2 already do, so no `gh` call or store read is needed. Or state the CI credential requirement as its own wiring task.

### [CONCERN] Task 7 bundles too many deliverables

One task covers `build_errors.py`, the git-log parser, the closing regex and rejection precedence, `resolve_locator`, the `closing_commit_repo` fixture, a captured real-history fixture and four test groups. Split it after `discover` and its rejections, and make `resolve_locator` and `no_issue_host` the second task, each with its own marker.

### [CONCERN] Task 11 bundles the config, digest, conftest and packaging work

Task 11 covers the plugin's config and output, per-item closure digests (fixtures, `co_names` recursion through nested code objects, parametrize ids), conftest fixture reporting, collection-error capture and the wheel check. Split it into node ids and digests first, then conftest reporting, collection errors and packaging, each ending at a tested point.

### [CONCERN] Task 9's source is committed under Task 10's `test:` marker

Task 9 adds `src/squadron/benchmark/test_sets.py` but has no `**Commit**:` marker. The next marker (line 147) is `test: add fixfair fixture project and history helper`, so the feature code lands in a `test:` commit. Add a marker after Task 9, for example `feat: sort tests into hidden and superseded sets`.

### [CONCERN] Real-commit test-first pins miss the assertion example

Design line 377 names two test-first examples: an AttributeError on an added symbol, and a failure by assertion. Task 27 pins the symbol case (b). Its holds case (a) is `project_exception`, not an assertion. Add a pin for an `assertion_failure` hold. If squadron's history has none, write `BLOCKED:` with the evidence.

### [NOTE] Task 5's edited-comment fixture may not exist, and there is no fallback

Task 5 requires an issue with an edited comment, captured from real GitHub data. If no such issue exists, the task has no path forward. Name a fallback, such as any issue whose comment carries `lastEditedAt`, or a `BLOCKED:` line.

### [NOTE] Crossing module naming is not pinned

Crossings are recorded as `(module, co_qualname, kind)`, while the resolver's allowed set uses `obj.__module__` (line 218). If the plugin derives the module from a file path, the two will not match and every crossing gets rejected. Pin the crossing module to the callee frame's `f_globals["__name__"]`.

### [NOTE] Trace-mode node ids are not in the pinned config

The pinned config has no node list, but trace mode traces "each requested test" (line 196). Say that node ids are pytest's positional arguments, as the suite runner passes them.

### [NOTE] The FileStates switch operation is not named

Tasks 13, 14 and 21 each "switch the sandbox" with `FileStates`, but only `overlay` is defined. Name the operation, for example `FileStates.apply(ctx, state)`, so that Tasks 14 and 21 call the same thing.

### [NOTE] DEVLOG.md already has uncommitted changes

`git status` at session start shows `M DEVLOG.md`. Task 29 writes the DEVLOG and then commits. Stage only the slice's files, or the unrelated change goes into the `feat:` commit.

### [PASS] The 421 gate and branch name are correct

`src/squadron/benchmark/` does not exist yet, and 421's task file defines `registry.py` at its line 245, so the gate is correct. The branch name follows the `{index}-slice.{name}` rule.

### [PASS] Success-criteria coverage holds, apart from the partial gaps above

Each functional, technical and integration criterion maps to at least one task. The partial ones are the patch-API, title-edit, test-first and stage-7 items above. Test tasks follow their implementation tasks, no task contains a merge or push, and the design restates no load NFR, so no load-test task is needed.

### Run Digest

- Response length: 12471 chars
- Response is newline-free: no
- Tool calls made: 16
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 17
- Tokens — prompt / cached / cache write / completion / reasoning: 795741 / 574148 / 221581 / 100838 / not computed
- Duration: 430.5 s
- Cost: $0.49 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 21
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 21
- Finding-shaped matches — surviving validation: 21

## Resolution

Task numbers below are the revised file's. Splitting Tasks 7 and 11 renumbered the file to 31 tasks.

- F001 (Tasks 12/13 depend on each other): Task 14's tests now build a second `BenchmarkSandbox` at the fix sha and collect there, so they need no state switch. The switch stays in Task 15.
- F002 (stage 7 and case-set write): Task 24 maps a `HarnessFailure`, `ProcessTimedOutError` or `SuiteRunError` from a stage 7 run to `harness_error`, with a timeout test and a `SuiteRunError` test. Task 26 raises `BuildHalted` on a `write_case_set` failure, with a test.
- F003 (resolver bug vs import failure): Task 20's resolver catches the import failure itself and exits with `IMPORT_FAILURE_EXIT`. Only that code raises `BoundaryUndecidable`. Any other non-zero exit, a timeout, or unparseable output raises `HarnessFailure`. Tests cover each.
- F004 (missing `pyproject.toml` vs failed `git show`): Task 22 tests presence with `git ls-tree --name-only <parent> -- pyproject.toml` instead of the suggested `git cat-file -e`. I ran both here: `cat-file -e` exits 128 for a missing path and for a bad revision alike, so it cannot tell them apart. `ls-tree` exits 0 with empty output for a missing path. Absent gives `no_fix_case_adapter`; a failing `ls-tree` gives `harness_error`. Both are tested.
- F005 (`delattr`, `setitem`, `delitem`): Task 19 adds a project-owned `monkeypatch.delattr`, `setitem` and `delitem` test to `fixfair_project`.
- F006 (two missing fixture projects): Task 11 now creates `fixfair_no_boundary` and `fixfair_bad_import`, each with a `uv.lock`, and Task 20's tests name them.
- F007 (conftest rule): Task 9 states one reading, matching D3. A changed or deleted `conftest.py` is rejected unless every difference is an added `pytest.fixture` function or an added import. A test where a conftest adds a plain helper is rejected is added.
- F008 (title edit after cutoff): Task 5 adds title rename events to the query (`timelineItems`, `RENAMED_TITLE_EVENT`) and a `title_renamed_at` field on `IssueSnapshot`, plus a captured rename fixture. Task 6 rejects a rename at or after the cutoff and tests both sides. I did not rely on `lastEditedAt` moving on title edits, because nothing in the repo confirms it.
- F009 (`qualification_for` signature): Task 31's design correction list and its success line now include the `store` argument.
- F010 (Task 27 pins in CI): now Task 29. Selecting (a)–(e) stays a one-time manual step that needs `gh`. Each pin names its sha and calls `qualify_in_sandbox` with a hand-built candidate and a temporary store, so no `gh` call or local store read is needed and the pins run under CI's plain `uv run pytest`.
- F011 (Task 7 too large): split. Task 7 is discovery, rejections, `BuildHalted` and the fixtures. Task 8 is `resolve_locator` and `no_issue_host`. Each has its own marker.
- F012 (Task 11 too large): split. Task 12 covers node ids and closure digests, filling the other output keys as empty lists. Task 13 covers conftest fixtures, collection errors and the wheel check. Each has its own marker.
- F013 (Task 9 under a `test:` marker): Task 10 (test sets) now has its own marker, `feat: sort tests into hidden and superseded sets`.
- F014 (assertion example for test-first): Task 29 adds (e), the most recent qualified case whose parent-run detail records `assertion_failure`, with a `BLOCKED:` line if none exists. It is pinned with (a)–(d).
- F015 (Task 5 edited-comment fixture fallback): Task 5 accepts any public issue whose comment has a non-null `lastEditedAt` (same for the rename fixture), and writes `BLOCKED:` with the search tried if none is found.
- F016 (crossing module naming): pinned to the callee frame's `f_globals["__name__"]`, the same form as the resolver's `obj.__module__`, in the Context Summary and Task 18.
- F017 (trace-mode node ids): the Context Summary says they are pytest's positional arguments, and Task 21's `trace` passes them that way.
- F018 (`FileStates` switch operation): Task 15 names it. `FileState` is a `StrEnum`, and `FileStates.switch_to(ctx, adapter, state)` is the one operation that Tasks 15 and 23 use.
- F019 (DEVLOG uncommitted changes): `git status` was clean when I checked, but Task 31 now has a step: run `git status`, stage by path, and use `git add -p` for `DEVLOG.md` if it holds changes this slice did not make.
- F020 (421 gate and branch name, pass): no change.
- F021 (success-criteria coverage, pass): no change. The partial gaps it names are covered by F005, F008, F014 and F002.
