---
docType: review
layer: project
reviewType: tasks
slice: code-host-adapter-and-pr-target-resolution
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/381-tasks.code-host-adapter-and-pr-target-resolution-1.md
aiModel: z-ai/glm-5.3-flash
status: complete
dateCreated: 20260913
dateUpdated: 20260913
reviewedSha: cb2ce1224a8838eb9b2b3cac77e7b5d82cbdcedb
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 22
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Every success criterion traces to at least one task; no gaps in functional or technical coverage"
    location: "slices/381-slice.code-host-adapter-and-pr-target-resolution.md:444-477"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing is dependency-correct with test tasks following their implementations; commit checkpoints are distributed, not batched"
    location: "tasks/381-tasks.code-host-adapter-and-pr-target-resolution-1.md:98"
  - id: F003
    severity: pass
    category: nfr-coverage
    summary: "No NFR restated in the slice design, so no `tests/load/` task or CI gating task is required"
    location: "slices/381-slice.code-host-adapter-and-pr-target-resolution.md:444-477"
  - id: F004
    severity: concern
    category: documentation
    summary: "B.2 says \"All sixteen\" but enumerates nineteen error classes"
    location: "tasks/381-tasks.code-host-adapter-and-pr-target-resolution-1.md:240-246"
  - id: F005
    severity: concern
    category: sequencing
    summary: "H.2 asserts `write_calls()` stays empty \"across a full `sq pr show` run\" one task before `sq pr show` exists"
    location: "tasks/381-tasks.code-host-adapter-and-pr-target-resolution-2.md:250-251"
  - id: F006
    severity: concern
    category: task-sizing
    summary: "H.4 packs four independent test deliverables, absorbing the design's separately-named `test_errors_observable.py`"
    location: "tasks/381-tasks.code-host-adapter-and-pr-target-resolution-2.md:280-296"
  - id: F007
    severity: concern
    category: scope-creep
    summary: "A.5's documented deviation contradicts the slice design's Excluded and Coordination sections, which were not updated"
    location: "slices/381-slice.code-host-adapter-and-pr-target-resolution.md:62"
  - id: F008
    severity: concern
    category: coverage
    summary: "The design's `__init__.py` re-export requirement has no corresponding task bullet"
    location: "tasks/381-tasks.code-host-adapter-and-pr-target-resolution-1.md:217"
  - id: F009
    severity: note
    category: sequencing
    summary: "The doctor-subprocess invariant test is written in G.3, two parts after the doctor checks it guards"
    location: "tasks/381-tasks.code-host-adapter-and-pr-target-resolution-2.md:206-209"
  - id: F010
    severity: note
    category: task-sizing
    summary: "Per-part commit tasks (B.4, C.3, D.4, E.4, F.6, G.4) are uniformly effort-1 but are the required distributed checkpoints, not granularity creep"
    location: "tasks/381-tasks.code-host-adapter-and-pr-target-resolution-1.md:267"
---

# Review: tasks — slice 381

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3-flash

## Findings

### [PASS] Every success criterion traces to at least one task; no gaps in functional or technical coverage

All seven functional criteria and four technical criteria have corresponding tasks: six-form/enterprise parity → H.4 (file 2:283-285); fork layout and non-GitHub mirror → D.3 (file 1:368-372); foreign repository → D.3 (file 1:376); fetch invariants and no-mutation argv → G.3 (file 2:194-196) plus live check I.1 (file 2:338-343); error table type/log/exit-1 → H.4 (file 2:288-290) with the timeout-bound assertion in F.5 (file 2:132-133); closed/merged and cross-repo fetch → F.5 and G.3 (file 2:208); doctor rows → E.2/E.3 with the subprocess invariant corrected to "write" in G.3 (file 2:206-209). Technical criteria: lint/pyright per commit task; import-graph test → H.4 (file 2:292-293); argv pinning → F.5; real-captured fixtures → F.1; the 300-line/query-split rule → F.4's final bullet (file 2:109-110). The design's Verification Walkthrough maps step-for-step onto I.1, and its Implementation Notes order maps onto Parts A–I with no missing step. No scope creep found: every task traces to a design statement, including the A.5 extraction (see the contradiction finding below — traceable, but the design text disagrees).

### [PASS] Sequencing is dependency-correct with test tasks following their implementations; commit checkpoints are distributed, not batched

The A→I order stated at file 1:60-62 is honored by the task layout: the process-runner seam (A) precedes everything tested through it; E.1's `github_config.py` precedes F.2's hosts construction; G.1/G.2 precede H.3's CLI; I follows all. Every implementation task has its test task immediately after within the same part (A.4, C.2, D.3, E.3, F.5, G.3, H.2, H.4). Each of the eight parts ends in a commit task (A.6 through H.5, file 1:198-207 and file 2:139-146, 213-219, 298-306), each running the accumulated suite plus ruff/pyright — the checkpoints are distributed exactly as required. Part B has no test task, but that is a stated deviation ("Pure declarations. No behavior… Parts C onward exercise every field", file 1:210-213) matching the design's own Implementation Notes, and B's outputs are exercised by C.2, D.3, F.5, G.3, and H.4.

### [PASS] No NFR restated in the slice design, so no `tests/load/` task or CI gating task is required

The success criteria are correctness criteria (target resolution, ref invariants, error observability, import boundaries) with no latency, throughput, or load requirement anywhere in the design; a grep of both task files for `tests/load`, CI, latency, throughput, and benchmark returns nothing. The quality gate the design does restate — ruff/pyright clean with zero pyright errors as a merge blocker — is enforced per-commit in every commit task and re-swept in I.2 (file 2:358-370).

### [CONCERN] B.2 says "All sixteen" but enumerates nineteen error classes

The bullet reads "One subclass per row of the design's error table. All sixteen:" and then lists `GitHubCliMissingError`, `HostUnauthenticatedError`, `HostUnreachableError`, `HostCommandTimeoutError`, `PullRequestNotFoundError`, `NoOpenPullRequestForBranchError`, `AmbiguousBranchPullRequestsError`, `ForeignRepositoryError`, `NoHostRemoteError`, `AmbiguousHostRemoteError`, `TargetSyntaxError`, `TargetUnresolvableError`, `RefNotFetchableError`, `RefMovedSinceResolutionError`, `NoMergeBaseError`, `HostRequestRejectedError`, `PullRequestCreationRejectedError`, `HostResponseMalformedError`, `OperatorUnidentifiedError` — nineteen names. The design's table has fourteen rows covering those nineteen classes, so "sixteen" matches neither grouping. The list itself is complete and matches the design exactly, but a junior implementer who treats the count as the check could stop at sixteen and silently drop three classes — and H.4's error-observability table is keyed off "B.2's table" (file 2:288), propagating the discrepancy. Fix the count (and note that H.4's "B.2's table" refers to the design's error table, since B.2 is a list, not a table).

### [CONCERN] H.2 asserts `write_calls()` stays empty "across a full `sq pr show` run" one task before `sq pr show` exists

H.2's third bullet requires an empty-`write_calls()` assertion over "a full `sq pr show` run — that empty assertion is 381's proof the slice is read-only". H.2 is the test task for H.1 (write operations); `pr.py` and the `sq pr show` command are created in H.3 (file 2:257-278) and registered against the live CLI only in H.5. As written, the bullet cannot be completed in sequence. It also is not re-homed anywhere later: H.4's bullets (file 2:280-296) cover the six-form test, the error table, `--json`, and the import boundary, but not the read-only proof, and I.1 checks refs/status via git rather than `write_calls()`. If the bullet is simply dropped during execution, the slice loses its only in-suite read-only assertion — the very mechanism 384 is documented to reuse. Move that assertion to H.4 (where the CLI exists), or scope H.2's emptiness check to a scripted full adapter pipeline (parse → select → resolve → fetch) with the CLI-level variant added in H.4.

### [CONCERN] H.4 packs four independent test deliverables, absorbing the design's separately-named `test_errors_observable.py`

H.4 combines: (1) the slice's headline six-form parametrized parity test over two hosts, (2) the full table-driven error-observability suite — the design's `test_errors_observable.py` (slices/381-slice.code-host-adapter-and-pr-target-resolution.md:574-575), which at nineteen error classes × type/log/exit-1 assertions is the densest single test in the slice, (3) the `--json` three-key shape test, and (4) the `tests/codehost/test_import_boundaries.py` import-graph walk across two packages. That is two test files in two directories and four unrelated deliverables under one effort-3 task — the highest-risk test (the error table) is the one most likely to be partially completed when buried in a four-part task. The design's Testing section names `test_errors_observable.py` as its own file; consolidating exit-code observability into `tests/cli/test_pr_show.py` is defensible (exit codes are only observable through the CLI) but should be stated in the task. Split H.4 into a CLI-behavior task (six-form, `--json`) and an observability/boundary task (error table, import graph), and note the file-placement deviation from the design's Testing layout.

### [CONCERN] A.5's documented deviation contradicts the slice design's Excluded and Coordination sections, which were not updated

The design states "Any change under `src/squadron/review/`" is excluded (line 62) and "Nothing under `src/squadron/review/` changes", with "the one edit to `cli/app.py`" as the sole coordinated edit (lines 90-91). The task file's A.5 makes a second, behavior-preserving edit to `review.py` under a PM decision dated 20260913, and documents it carefully — a Corrections table entry (file 1:46-53), an expanded Coordination note naming both `sq-base` notifications (file 1:64-76), and an early standalone commit. The deviation itself is justified and well-governed; the problem is that the slice design — the document the task file's own `lldReference` points to, and the contract slices 382/384/385 read — still asserts the opposite. A junior AI working from the design alone would refuse or mis-scope A.5, and I.3's closeout (file 2:372-388) updates status in the design and plan without reconciling this text. Amend the design's Excluded/Coordination sections (or append a scope-corrections row mirroring the task file's table) so the two governing documents agree. Minor related point: A.5 leaves an open implementation choice ("Either re-export it or accept the `cli → review` import here and record which", file 1:192-195) — bounded and completable either way, but the choice should be made in the task text if possible.

### [CONCERN] The design's `__init__.py` re-export requirement has no corresponding task bullet

The design's component structure specifies `__init__.py` "re-exports the public types below" (slices/381-slice.code-host-adapter-and-pr-target-resolution.md:101), and its Integration Points → Provides section (slices/381-slice.code-host-adapter-and-pr-target-resolution.md:478-486) declares the package-root surface (`codehost.CodeHost`, `GitHubCli`, `PullRequestRecord`, `parse_target`, `list_remotes`, `select_remote`, `build_github_host`, …) as the contract consumed by 382, 384, and 385. B.1's only instruction is "Create `src/squadron/codehost/` with `__init__.py`" — no bullet says what goes in it. A junior AI can satisfy every B.1 checkbox with an empty `__init__.py`, and nothing in C–I or I.2's criteria sweep (file 2:354-370) checks the re-exports, so the divergence would surface only at 382 integration as deep-path imports — precisely the cross-slice interface surprise this slice exists to prevent. Add a bullet to B.1 (re-export the Provides list from the package root, verified once in I.2). Every other Provides entry traces to a task: models/errors/protocol (B.1–B.3), `parse_target` (C.1), `list_remotes`/`select_remote` (D.1/D.2), `build_github_host` and `serves_host` (F.2), `ProcessRunner`/`SubprocessRunner` (A.1), `FakeProcessRunner.write_calls()` (A.3), `pr_app` (H.3).

### [NOTE] The doctor-subprocess invariant test is written in G.3, two parts after the doctor checks it guards

The design's correction ("existing test extended" → the test does not exist and must be written) is assigned to G.3, so Part E's doctor checks land without the invariant until Part G. The placement is deliberate (documented in file 1's corrections table) and G.4's test command (`tests/codehost tests/cli`) picks it up, but E.3 — which already extends `tests/cli/test_doctor_checks.py` — is its natural home. The claim that no such test exists today is the task file's own statement and could not be verified here (the code tree is absent from this workspace); the placement finding does not depend on it. Consider moving the invariant test to E.3.

### [NOTE] Per-part commit tasks (B.4, C.3, D.4, E.4, F.6, G.4) are uniformly effort-1 but are the required distributed checkpoints, not granularity creep

Each commit task bundles the accumulated test run with lint/type gates and a named commit message, which is process hygiene the review rubric asks for; merging them into implementation tasks would weaken the checkpoint cadence. The smallest implementation tasks (A.2, effort 1; B.3, effort 1) are each a single coherent unit; A.1+A.2 could merge but the split matches the design's own Order step 1 and costs nothing. No task is too granular.
