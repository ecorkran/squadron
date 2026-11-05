---
docType: slice-plan
parent: 420-arch.model-benchmark.md
project: squadron
dateCreated: 20261104
dateUpdated: 20261104
status: not_started
---

# Slice Plan: Model Benchmark

## Parent Document
`420-arch.model-benchmark.md` — Architecture: Model Benchmark

## Planning Context
Architecture-level. The architecture went through two review rounds and lists six anticipated slices. This plan keeps their order and splits two of them, each of which had more concerns than one slice should carry:

- **Fix cases and qualification** becomes a sandbox-and-case-record foundation (421) and fix-case qualification ending at the yield report (422). The sandbox environment, the scrubbed producer environment and the test-level suite runner are shared by fix cases, slice cases, replay and grading. Building them first lets the agent-auth check report its answer before anything depends on it.
- **Implementation replay and grading** becomes a producer-only replay runner (424) and the grader with the paired report (425). After 424, replays produce records and diffs. After 425, those records have grades.

The fix-case path stays the keystone (421 → 422 → 423 → 424 → 425). It is the cheapest objective unit and the first to exercise the sandbox, environment and grader end to end.

---

## Foundation Work

1. [ ] **(420) Effort Audit Across Dispatch Paths** — Every dispatch path (SDK pipeline session, one-shot runners, OpenAI-compatible, review) sends the alias's effort when the alias has one, or records that it could not. Every usage record carries the effort actually sent, or a recorded "not sent". It never carries the alias's configured value as a stand-in.
   - **Value:** Without this, effort rows in any benchmark report mean nothing. It also fixes whatever the audit turns up.
   - **Success Criteria:**
     - There is an inventory of every dispatch path, showing whether each sends effort and records it.
     - Every path that can send effort sends it, and a test per path checks this.
     - A path that cannot send effort records "not sent", and a test checks that too.
     - Usage records and config identity carry the effort sent, so two runs that differ only in the alias's effort label but sent the same effort count as one config.
   - **Dependencies:** none in this initiative (#216 fixed in 0.24.19).
   - **Interfaces:** Provides effort-sent on usage records and in config identity. All later slices read it.
   - **Risk Level:** Low
   - **Relative Effort:** 2/5

2. [ ] **(421) Benchmark Sandbox and Case Record** — The shared base for cases, replay and grading:
   - The case and case-set record types in the 320 store. A case is identified by its content: start commit, task text, hidden and superseded test sets, exclusion list and grader commands. A case set is a named, versioned list of case ids. These are optional sibling payloads, keyed on `ProjectId`, with no migration.
   - Sandbox environment resolution on top of 177's history-free sandbox: install the project at the start commit and record an environment identity (lockfile hash, tool versions).
   - The scrubbed producer environment: no GitHub credentials, squadron and agent config directories redirected, `PATH` with the sandbox environment first and no user tool installs. This includes the check that agent auth still works with the config directory redirected.
   - The Python adapter's test-level suite runner, which reports pass, fail or error per pytest node id and tells a collection or import error apart from an assertion failure.
   - **Value:** Developer and architectural enablement. Every later slice runs on it. If agent auth fails under the redirected config, that shows up here.
   - **Success Criteria:**
     - Case and case-set records write to the store and read back. Changing any part of a case's content identity produces a new case id.
     - A sandbox at a historical squadron commit installs its own dependencies and records its environment identity. A lockfile that no longer resolves fails with that reason instead of falling back.
     - A producer process started in the scrubbed environment has no GitHub credentials, and its `PATH` excludes the user's tool installs. The installed `sq` cannot be reached from inside a squadron sandbox.
     - The auth check gives a definite yes or no for each agent provider used by the benchmark. A no is reported, not worked around.
     - The suite runner returns per-node-id results and classifies failures into assertion failure, project-code exception, and collection/import/missing-symbol error.
   - **Dependencies:** [420]; 177 sandbox, 320 store.
   - **Interfaces:** Provides the case and case-set records, the sandbox environment with its environment identity, the scrubbed producer environment, and the language-adapter seam with its Python implementation of the suite runner. Consumes 177's sandbox and 320's store.
   - **Risk Level:** High (installing dependencies in a sandbox from code in history, and auth under redirected config, are both first decided here)
   - **Relative Effort:** 3/5

---

## Feature Slices (in implementation order)

3. [ ] **(422) Fix Case Qualification and Yield Report (keystone)** — Candidate discovery from commits that close an issue and add tests. Each candidate gets:
   - Frozen issue text, captured when the case is created.
   - Per-test hidden and superseded sets, taken from the reference diff.
   - The Python fairness rule: test-first at the parent, reaches project code only through what packaging declared at the parent, and does not patch project code. A check that cannot decide excludes the case.
   - Qualification run several times: the reference grade and the parent's test-first check. Tests that disagree across runs go on the case's exclusion list.

   Qualification records are keyed on environment identity, and a case whose environment differs is re-qualified. The slice ends at a yield report: qualified count per project and excluded count per reason, plus whether that count can separate two configs under the paired statistic. That answer decides whether fix cases are pooled across cf projects or slice cases (426) move ahead.
   - **Value:** Developer value. The first measured answer to "can this project be benchmarked on fixes, and how many cases does it give?"
   - **Success Criteria:**
     - Discovery runs on any cf project's history with no per-project configuration and produces fix-case candidates.
     - Each candidate's issue text is frozen into the case, so a later issue comment does not change the case.
     - Hidden and superseded sets list individual node ids, including `conftest.py` fixtures the fix added.
     - Each of the three fairness checks has tests with qualifying and disqualifying examples taken from squadron's real fix commits, including a crash fix that qualifies and a patched-internal test that does not.
     - Every rejected candidate has a recorded reason. No candidate is silently dropped.
     - Repeated qualification puts flaky tests on the case's exclusion list, and that list is part of the case's content identity.
     - The yield report runs on squadron and on at least one other cf project and states the separability answer.
   - **Dependencies:** [421]
   - **Interfaces:** Provides fix cases, versioned fix-case sets, qualification records and the yield report. Consumes 421's records, sandbox and suite runner.
   - **Risk Level:** High (the fairness rule's boundary trace, and yield that may be low)
   - **Relative Effort:** 4/5

4. [ ] **(423) Fix Pipeline** — `sq run fix <issue>` as a production pipeline that follows the guide's fix rule: a failing test, the change, the gates, a commit to the target. It can run in a sandbox with frozen issue text passed in instead of fetched, needs no GitHub access there, and commits to the sandbox's branch.
   - **Value:** User value on its own, since fixes are done interactively today. It is also what fix cases replay.
   - **Success Criteria:**
     - `sq run fix <issue>` on a real issue produces a failing test, a change that makes it pass, passing gates and one commit on the target.
     - Given frozen issue text, the pipeline runs with no GitHub access and commits to the current branch.
     - The pipeline runs under `pipeline.max_cost_usd` and `--max-cost` like any other pipeline.
     - CLI and slash command give identical results.
   - **Dependencies:** [422] (`CodeHost.get_issue` and the issue renderer, for fetched issue text only; file mode needs nothing from 422).
   - **Interfaces:** Provides the `fix` pipeline and its issue-text input. Consumes the existing executor and cost cap.
   - **Risk Level:** Medium
   - **Relative Effort:** 3/5

5. [ ] **(424) Producer-Only Replay Runner** — A new `sq run` producer-only mode that runs only a pipeline's producer step (`implement` from `P6`, the `fix` pipeline's step) with its embedded review stripped: same prompt, same dispatch, same commit, no review action and no verdict, then stop. On top of that, the benchmark runner takes a case set × configs × sample count and, for each run:
   - opens a sandbox at the start commit;
   - runs the producer in the scrubbed environment;
   - scans the transcript for leak paths and for `git`/`gh` calls against other repos;
   - writes one replay record with the diff in a content-addressed sidecar file.

   The run refuses to start without both a per-pipeline cap and a run-level cap, states its dollar bound before any dispatch (including one-pipeline overshoot), and stops at the run-level cap, marking the run partial. A rerun skips (case, config, sample) runs that already have records, detects orphaned sandboxes, and marks an interrupted run as interrupted. Producer-caused absences (crash, cap, no commit) and leak-caused absences are recorded with their kind.
   - **Value:** Developer value. Configs produce comparable implementations on identical work, under a stated spend limit.
   - **Success Criteria:**
     - Producer-only mode on `P6` runs the `implement` step's prompt and dispatch, commits, and stops with no review, close-out, DEVLOG or merge. No pipeline YAML or prompt is copied to do this.
     - A benchmark run with either cap missing refuses to start and names the missing cap.
     - The stated bound appears before the first dispatch. Hitting the run-level cap stops dispatching, keeps every record written, and marks the run partial.
     - A planted read of a known leak path in a test transcript marks the run leaked and ungraded. A clean run is recorded as "no leak detected".
     - Diffs are stored as sidecar files referenced by hash, and records stay small.
     - Rerunning an interrupted benchmark skips completed runs and reports orphaned sandboxes.
   - **Dependencies:** [421, 422, 423]
   - **Interfaces:** Provides producer-only mode on `sq run`, the benchmark run command, replay records and diff sidecars. Consumes cases (422), the fix pipeline (423), `P6`, the sandbox and scrubbed environment (421), and 947's cap.
   - **Risk Level:** High (stripping the embedded review without forking the step, and leak detection)
   - **Relative Effort:** 4/5

6. [ ] **(425) Grading and Paired Report** — The grader runs after the producer finishes, in a fresh sandbox rebuilt from the start commit plus the producer's diff, with its own commands. It:
   - injects the hidden set without removing producer tests, renaming on a clash and recording it;
   - runs the start commit's suite minus the superseded set and the exclusion list;
   - runs the producer's new tests as a separate signal;
   - restores tool config by section from the start commit, and reinstalls (recording that it did) if dependencies or the lockfile changed;
   - counts edits to existing tests or config and added `# noqa` / `# type: ignore`;
   - runs lint and type checks, takes a 400 snapshot, and runs one fixed code-review config whose findings are normalized the way 400 ingests them.

   Harness-caused absences (environment, grader timeout, leak) drop the case from every config. The report gives the per-case pass fraction, paired per-case differences with a paired bootstrap interval ("not distinguishable" when it spans zero), then review findings against 320's noise floor, then cost, turns and time, all with n. Review-finding columns are flagged as coming from an unmeasured reviewer until 427 has data for the grading config. A small first run measures how many samples and cases it takes to separate two configs.
   - **Value:** Developer value. The first objective answer to "does config X implement fixes as well as config Z, and at what cost?"
   - **Success Criteria:**
     - The reference fix, graded like a replay, passes. A replay that edits a test, adds a suppression or changes `[tool.*]` config is counted, and the edit does not change the grade.
     - Superseded tests are not counted as regressions. Hidden tests are injected with clashes renamed and recorded.
     - Config-caused absences count as fails for that config. Harness-caused absences drop the case from every config. The report counts both kinds.
     - Two configs on the same cases get a paired interval, and a pair whose interval spans zero is shown as not distinguishable, not ranked.
     - No composite score is computed anywhere.
     - The sample-count measurement from a small run is recorded and shown in the report.
   - **Dependencies:** [424]; 400 snapshots and finding normalization, 320 noise floor.
   - **Interfaces:** Provides grade records, the grader identity and the benchmark report. Consumes replay records (424), the suite runner (421), 400 snapshot and normalization, 300's code-review template.
   - **Risk Level:** Medium
   - **Relative Effort:** 4/5

7. [ ] **(426) Slice Cases** — Cases from 400 slice-range records: the fork commit is the start, the design and task file at the fork are the task, and the slice branch tip (`tip_sha`) is the reference, so a merge landing does not bring in unrelated work. They have no hidden set. The superseded set comes from the reference diff. They are qualified with the same environment-keyed records. Slice cases are graded on regressions, check and snapshot deltas and review findings. Before judging, diffs are normalized (DEVLOG, CHANGELOG, task files, review files and slice documents dropped). The 177 pairwise judge then compares replay diffs within a case, Bradley-Terry ranks configs, and the reference appears as a reference line, not a ranked config. Diffs too large for the judge's context follow a stated rule, never silent truncation.
   - **Value:** Developer value. Benchmarks the full-slice implementation work where most P6 spend goes.
   - **Success Criteria:**
     - Slice cases build from squadron's 400 slice ranges with recorded exclusion reasons.
     - Replays of slice cases run through producer-only `P6`, and grading reports them in a table separate from fix cases.
     - The judge sees only normalized diffs. The reference is shown as a reference line.
     - Over-size diffs are handled by the stated rule and counted in the report.
   - **Dependencies:** [425]; 400 slice-range records, 177 judge.
   - **Interfaces:** Provides slice cases, slice-case sets and pairwise results over diffs. Consumes 421–425 and 177's judge and aggregation.
   - **Risk Level:** Medium
   - **Relative Effort:** 3/5

8. [ ] **(427) Reviewer Recall** — Planted-defect cases: real diffs with known defects injected. Each defect has ground truth: location, category in 402's vocabulary, and a failing test that shows it breaks something. Each reviewer config reviews each case several times. Findings are matched to planted defects by a stated rule, giving recall per config plus the count of findings that matched nothing. When recall data exists for 425's grading config, 425's report drops its unmeasured-reviewer flag.
   - **Value:** Developer value. Code-review model choice gets a measured basis, and the grader's reviewer gets a measured recall.
   - **Success Criteria:**
     - Each planted defect has location, category and a test that fails with the defect and passes without it.
     - The matching rule is defined and tested on findings that match and findings that don't.
     - The report gives recall and unmatched-finding counts per reviewer config, with n.
     - 425's report reads recall for its grading config and flags the review columns only when that recall is missing.
   - **Dependencies:** [421, 425]; 400 normalized findings, 300 review template. It imports 425's `ReviewerRef`, review call and bootstrap, and does not depend on 424 or 426.
   - **Interfaces:** Provides planted-defect cases, recall records and the recall report. Consumes 421's records and sandbox, and 400's normalization.
   - **Risk Level:** Medium (how defects are planted and how loose the matcher is decide whether the number means anything)
   - **Relative Effort:** 3/5

---

## Notes

**Key decisions made during planning:**
- **The keystone and the replay slice are each split in two.** As written in the architecture, each carried more than six concerns. The splits are at a data boundary (sandbox and records vs. fix-case qualification) and at a process boundary (producing a diff vs. grading it). Each half leaves a working, inspectable result.
- **The auth check lives in 421**, which builds the scrubbed environment, so a no stops the plan before 422 depends on it.
- **The fix pipeline (423) depends on 422 only for fetching issue text.** It comes right after 422 in the keystone order.
- **Reviewer recall (427) needs 421 and 425.** It reuses 425's grading review and statistics instead of defining its own.

**Ordering decided by measurement:**
- 422's yield report decides what comes after 423. If qualified fix cases can separate two configs, the order stands. If not, either discovery is pooled across cf projects (422 already runs on any project) or 426's case-building part moves ahead of 424, and 424 and 425 are built against slice cases first.

**Open for slice design:**
- The producer-only mode's flag name and how it reports the stop (424).
- How the language-adapter seam is shaped beyond Python (421; only Python is implemented).
- How sandbox environment resolution handles projects without a lockfile (421).
- The diff-size rule for the judge (426).
- How defects are planted, and the finding-to-defect matching rule (427).
- The sample count, measured in 425 before any large run.

---

## Future Work
1. [ ] **(1) Additional Language Adapters** — Fairness rule and suite runner for TypeScript (package.json `bin`/`exports`/`main`) and other languages, so non-Python cf projects yield fix cases. Dependencies: [422]. Effort: 3/5.
2. [ ] **(2) OS-Sandboxed Replays** — Run replays under #213's OS sandbox once it lands. Dependencies: [424], #213. Effort: 2/5.
3. [ ] **(3) Concurrent Replays** — Run configs and samples in parallel (#146). Dependencies: [424], #146. Effort: 3/5.
