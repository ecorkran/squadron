---
docType: review
layer: project
reviewType: tasks
slice: review-scope-correctness
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/916-tasks.review-scope-correctness.md
aiModel: z-ai/glm-5.3
status: complete
dateCreated: 20260911
dateUpdated: 20260911
reviewedSha: c5fc4e19861cdad2ffc8f9befc1de5f33aa60fe8
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 24
findings:
  - id: F001
    severity: pass
    category: traceability
    summary: "All eleven functional and every technical success criterion map to concrete tasks"
    location: "project-documents/user/tasks/916-tasks.review-scope-correctness.md"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing honors the design's load-bearing DâAâCâBâE order with no circular dependencies"
    location: "project-documents/user/tasks/916-tasks.review-scope-correctness.md"
  - id: F003
    severity: pass
    category: task-structure
    summary: "Test-with pattern applied consistently with five distributed commit checkpoints"
    location: "project-documents/user/tasks/916-tasks.review-scope-correctness.md"
  - id: F004
    severity: pass
    category: nfr-load-testing
    summary: "No NFR restated; no `tests/load/` or CI-wiring task required"
    location: "project-documents/user/slices/916-slice.review-scope-correctness.md"
  - id: F005
    severity: concern
    category: factual-accuracy
    summary: "Task D.3 names `tests/review/test_config_cwd.py` as \"the existing home for cwd behavior\" â uncorroborated by any other project document"
    location: "project-documents/user/tasks/916-tasks.review-scope-correctness.md:105"
  - id: F006
    severity: concern
    category: test-coverage
    summary: "Part B's new failure paths are the only ones with no WARNING+ log-record assertion"
    location: "project-documents/user/tasks/916-tasks.review-scope-correctness.md:380-393"
  - id: F007
    severity: note
    category: documentation
    summary: "Task A.6 misreferences \"A6's rewrite\" where it means A.3's"
    location: "project-documents/user/tasks/916-tasks.review-scope-correctness.md:204"
  - id: F008
    severity: note
    category: verification
    summary: "Criterion 1's `gh pr view --json files` oracle is silently replaced by `git diff --name-only` in A.7 and Z.1"
    location: "project-documents/user/tasks/916-tasks.review-scope-correctness.md:222"
  - id: F009
    severity: note
    category: task-sizing
    summary: "Task C.4 is a single-checkbox task whose scope C.2 already enumerates"
    location: "project-documents/user/tasks/916-tasks.review-scope-correctness.md:281-285"
---

# Review: tasks — slice 916

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3

## Findings

### [PASS] All eleven functional and every technical success criterion map to concrete tasks

Full mapping, criterion by criterion:

| Criterion | Covering tasks |
|---|---|
| SC1 merge-base file list | A.3, A.5, A.6, A.7 |
| SC2 `a..b`/`a...b` pass through | A.3 shape table; A.6 (both pass-throughs + explicit three-dot case) |
| SC3 nonexistent ref, no model call | A.4, A.5, A.6 (CLI test asserting the review client was never called) |
| SC4 all-excluded, no artifact | B.1, B.2, B.3, B.4 (asserts reviews dir unchanged), B.7 |
| SC5 no-changed-files, distinct case | B.2, B.4 (different structured case) |
| SC6 holds via `sq run` and rules-absent | B.3 (unconditional, both entry points), B.4 (pipeline test + rules-absent test â correctly called out as the most important test in the part), B.7 |
| SC7 `--diff`-only exits on verdict + WARNING + 10 examples | C.3, C.5 (exit 0 **and** WARNING record), C.6 (pinned forms + doc-line read-through) |
| SC8 failed save exits 1 | C.2, C.3, C.5 (forced `OSError`), C.7 (read-only path) |
| SC9 `--no-save` quiet | C.3, C.5, C.7 |
| SC10 git-root jail | D.1, D.2 (grep-count success criterion), D.3, D.4 |
| SC11 `tools` set, `Bash` unavailable | E.2, E.3, E.4 (live verification per design E4) |

Technical criteria: no-new-`Verdict` (standing constraint, B.3, Z.1); one shared helper not five copies (D.1/D.2 with a mechanical `grep -c` check); the five named tests exist (A.6, B.4, C.5, D.3, E.3); no-message-text-assertion is stated as a standing constraint and restated inside A.6, B.4, and C.5. No gaps and no scope creep â A.1 (`run_git` timeout), B.5 (escape-hatch verification), B.6 (pre-landing behavior-change check), and C.6 (documented-invocation regression guard) all look like additions but each is explicitly required by design A5, B3, the Risk Assessment, and C3/F003 respectively. The "Verified code anchors" table traced to a specific commit materially helps junior-AI completability.

### [PASS] Sequencing honors the design's load-bearing DâAâCâBâE order with no circular dependencies

The task file reproduces the design's Implementation Notes order exactly and restates the rationale (D consolidates the function bodies A/B/C then edit; C before B so B builds on the corrected outcome model). Intra-part dependencies are respected: D.1 (helper) precedes D.2 (routing); A.1âA.2 and A.3/A.4/A.5âA.6; C.1âC.2âC.3/C.4; B.1âB.2âB.3âB.4; and E.1 explicitly gates E.2 ("This task gates E.2. Do not implement before it resolves"), which is the correct handling of design E5's scope-boundary condition. B.8 is correctly placed after B.7's commit since it is post-landing verification.

### [PASS] Test-with pattern applied consistently with five distributed commit checkpoints

Every implementation task is immediately followed by its test task before the part's commit: D.1/D.2âD.3âD.4; A.1âA.2 and A.3/A.4/A.5âA.6âA.7; C.1-C.4âC.5/C.6âC.7; B.1-B.3âB.4âB.7; E.2âE.3/E.4âE.5. Tests therefore land in the same commit as the code they verify. Commits exist at D.4, A.7, C.7, B.7, and E.5 â one per part, distributed throughout, not batched at the end. Z.1/Z.2 are closure tasks, not a deferred commit.

### [PASS] No NFR restated; no `tests/load/` or CI-wiring task required

Neither the slice design's Success Criteria nor the parent plan's entry 14 restates a latency, throughput, or scalability NFR â all criteria are functional correctness. The one performance-adjacent item, Task A.1's bounded timeout on `run_git`, is a hang/safety bound, not a latency SLA, and is correctly verified by A.2's unit test with a raised `subprocess.TimeoutExpired`. This matches the precedent this repo's own task reviews established for exactly this class of work (reviews 261, 266, 910, 911 all concluded timeout/bounds constants are correctness properties verified by monkeypatched unit tests, not load-test material). The 265 `tests/load/` case is distinguishable: that timeout guarded catastrophic regex backtracking running `asyncio.to_thread`'d on the event loop â concurrency-path work. No load test task is missing, and consequently no CI-gating task is left implicit.

### [CONCERN] Task D.3 names `tests/review/test_config_cwd.py` as "the existing home for cwd behavior" â uncorroborated by any other project document

The other three test homes this task file asserts are all multiply-attested elsewhere in the repo: `tests/review/test_git_utils.py` (tasks/127, notes/000-process-journal, slices/168, reviews/168), `tests/cli/test_review_save.py` (tasks/118, reviews/146, analysis/303), and `tests/review/test_template_sdk_regression.py` (slices/265). `tests/review/test_config_cwd.py` appears in exactly one place in the entire documents tree â this task file's own claim that it is an existing home. I cannot inspect the `tests/` tree directly (it is outside my working directory), so this is unverified rather than disproven, but the attestation asymmetry against three corroborated siblings is a strong signal the path is misremembered. The concrete cwd-related tests I could find referenced elsewhere live in `tests/cli/test_review_profile.py`, `tests/review/test_rules.py`, and `tests/providers/openai/test_provider.py`. If the file does not exist, a junior AI will create it and the test still lands; the real risk is that if a genuine existing home for cwd behavior exists, D.3's test fragments into a fresh file instead of joining it. Recommend the task say "create if absent" (the phrasing other task files in this repo use, e.g. tasks/122) or name the verified home.

### [CONCERN] Part B's new failure paths are the only ones with no WARNING+ log-record assertion

The file's own standing constraint requires that "Every new failure path exits non-zero **and** logs at WARNING or above (Failure-Mode Enumeration rule). No silent path may be replaced by another silent path." Parts A and C enforce this in their test tasks: A.2 asserts a "WARNING-level record" on timeout, A.5 specifies "logging at ERROR," and C.5 asserts "a WARNING-level record was emitted." Part B â whose entire purpose is converting a silent PASS into a loud failure â specifies exit codes and structured error fields in B.1/B.2/B.3 but never names a log level, and B.4's tests assert exit codes, structured cases, and artifact absence without asserting any log record. A typed exception raised pre-flight may or may not surface at WARNING+ depending on how each entry point's error handler catches it, which is precisely the drift the constraint exists to prevent. One line in B.4 ("assert a WARNING-level record is emitted for both cases, at both entry points") closes it.

### [NOTE] Task A.6 misreferences "A6's rewrite" where it means A.3's

"...the pass-throughs are what protect `--diff a..b` from A6's rewrite" â A.6 is the test task; the rewrite rule lives in A.3 (design A2). Context makes the intent recoverable, so this will not block a junior AI, but it is worth correcting since the file leans heavily on precise part references for navigation.

### [NOTE] Criterion 1's `gh pr view --json files` oracle is silently replaced by `git diff --name-only` in A.7 and Z.1

Success criterion 1 states the file list "matches `gh pr view --json files` for the same PR," and the design's walkthrough adds "On a real PR, both must agree with `gh pr view <n> --json files`." Task A.7's walkthrough and Z.1's restatement both use only `git diff --name-only origin/main...HEAD`. The substitution is defensible â git is the authoritative merge-base computation and `gh` is not always available â but the task file does not acknowledge it has narrowed the design's oracle. Worth a one-line note in A.7 that the `gh` cross-check is design-optional and omitted deliberately.

### [NOTE] Task C.4 is a single-checkbox task whose scope C.2 already enumerates

C.2's first bullet already lists all four `saved = True` initializer sites ([:616], [:673], [:760], [:930] â one per subcommand), so C.4's "all four subcommands get the same mechanism" adds no mechanical work. It is retained as an explicit interface-parity reminder tracing to design C5, which is a defensible reason to keep it, but it is the one task in the file a reviewer could argue for merging into C.2. Compare the 910 task review's F002, which reached the same conclusion for an equivalently granular separation. Not blocking; no other task is too large (the largest are Effort 3 â A.6, C.2, C.5, B.1, B.3, B.4 â each a single cohesive unit) and the Effort-1 verify/commit tasks follow this project's established per-part cadence.
