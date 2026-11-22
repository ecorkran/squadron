---
docType: slice-plan
parent: 420-arch.model-benchmark.md
project: squadron
dateCreated: 20261104
dateUpdated: 20261121
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

1. [x] **(420) Effort Audit Across Dispatch Paths** — Every dispatch path (SDK pipeline session, one-shot runners, OpenAI-compatible, review) sends the alias's effort when the alias has one, or records that it could not. Every usage record carries the effort actually sent, or a recorded "not sent". It never carries the alias's configured value as a stand-in.
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

2. [x] **(421) Benchmark Sandbox and Case Record** — The shared base for cases, replay and grading:
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

3. [x] **(422) Fix Case Qualification and Yield Report (keystone)** — Candidate discovery from commits that close an issue and add tests. Each candidate gets:
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

4. [x] **(423) Fix Pipeline** — `sq run fix <issue>` as a production pipeline that follows the guide's fix rule: a failing test, the change, the gates, a commit to the target. It can run in a sandbox with frozen issue text passed in instead of fetched, needs no GitHub access there, and commits to the sandbox's branch.
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

5. [x] **(424) Producer-Only Replay Runner** — A new `sq run` producer-only mode that runs only a pipeline's producer step (`implement` from `P6`, the `fix` pipeline's step) with its embedded review stripped: same prompt, same dispatch, same commit, no review action and no verdict, then stop. On top of that, the benchmark runner takes a case set × configs × sample count and, for each run:
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

6. [x] **(425) Grading and Paired Report** — The grader runs after the producer finishes, in a fresh sandbox rebuilt from the start commit plus the producer's diff, with its own commands. It:
   - injects the hidden set without removing producer tests, renaming on a clash and recording it;
   - runs the start commit's suite minus the superseded set and the exclusion list;
   - runs the producer's new tests as a separate signal;
   - restores tool config by section from the start commit, and reinstalls (recording that it did) if dependencies or the lockfile changed;
   - counts edits to existing tests or config and added `# noqa` / `# type: ignore`;
   - runs lint and type checks, takes a 400 snapshot, and runs one fixed code-review config whose findings are normalized the way 400 ingests them.

   Harness-caused absences (environment, grader timeout, leak) drop the case from every config. The report gives the per-case pass fraction, paired per-case differences with a paired bootstrap interval ("not distinguishable" when it spans zero), then review findings against 320's noise floor, then cost, turns and time, all with n. Review-finding columns are flagged as coming from an unmeasured reviewer until 427 has data for the grading config. A small first run measures how many samples and cases it takes to separate two configs. Grading is its own command with its own cap and printed bound (D9), and a benchmark's total spend is the run's cap plus each grade invocation's cap.
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

7. [x] **(426) Slice Cases** — Cases from 400 slice-range records: the fork commit is the start, the design and task file at the fork are the task, and the slice branch tip (`tip_sha`) is the reference, so a merge landing does not bring in unrelated work. They have no hidden set. The superseded set comes from the reference diff. They are qualified with the same environment-keyed records. Slice cases are graded on regressions, check and snapshot deltas and review findings. Before judging, diffs are normalized (DEVLOG, CHANGELOG, task files, review files and slice documents dropped). The 177 pairwise judge then compares replay diffs within a case, Bradley-Terry ranks configs, and the reference appears as a reference line, not a ranked config. Diffs too large for the judge's context follow a stated rule, never silent truncation.
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

8. [x] **(427) Reviewer Recall** — ⏪ Dropped 20261115, superseded by 430. It planted mutations in real commits and proved each with a test, which measures synthetic defects in a no-tools review and needed a mutation engine. The hand-run real-bug benchmark answered the same question at cents per review. Never implemented; its design and task file are archived.

9. [x] **(428) Design Review Recall** — ⏪ Dropped 20261115, superseded by 432. Planted flaws are replaced by flaws that were really corrected later.

10. [x] **(429) Task Breakdown Review Recall** — ⏪ Dropped 20261115, superseded by 432.

## Measurement Slices (re-plan 20261115)

PM decision after 426. The replay stack (421–426) stays as built and gets no further work: each data point costs dollars and hours, and few cases qualify. These slices measure with what is cheap and already recorded. Two rules apply to all of them. No task runs against squadron's own history or needs hours; live checks use small fixture projects. Every measured run prints its cost bound first and stops at a cap.

11. [x] **(430) Real-Bug Review Recall** — The hand-run code-review benchmark (`user/reference/review-recall-runbook.md`, results in `user/reference/review-recall-results/`) as a command. A case is a real merged diff (repo, base, head) with the bugs a later fix commit or issue proved real. A reviewer config is a recipe: one or more reviewers run in parallel (fan-out), an optional pool to pick from at random, and zero or more comb stages that mark each finding KEEP or DROP. Each stage's output is stored once per case and run, and a recipe is scored from stored outputs wherever no new call is needed (a union for fan-out, the member mean for a pool, stored comb decisions). Reviewers run as they are used, with tools, in 421's history-free sandbox at `head`, so the later fix cannot be read. The report gives known-bug recall, finding counts, graded-real share and cost per recipe, with the number of cases and runs.
   - **Value:** User-facing. Answers "which code review setup, and is a replacement better or worse" with a repeatable command. The recipe that wins becomes the pipeline review step's configuration.
   - **Success Criteria:**
     - The existing cases and their known bugs load as stored cases. A new case is added as a record, not as code.
     - The existing hand-run results import as stored stage outputs, and the report reproduces the hand-run recall table for haiku-xhigh, sol, sonnet-high and sonnet from them with no new calls.
     - A recipe of two reviewers plus a comb is scored from stored single-review and comb records.
     - `run` prints its cost bound before the first call, stops at its cap with exit 2, and resumes.
     - The rule for when a finding hits a known bug is stated and tested. Findings it cannot decide are listed for a person and not counted.
     - The first recipe is committed and ready, and the PM runs it after the slice (it takes over an hour serially, so no task runs it): haiku-xhigh and sol in parallel, then a luna comb, then an opus-high comb (RESULTS.md section 5: opus-high combing haiku-xhigh kept all 6 of its known bugs at 86% real, and combing sol kept all 5 at 92%). The comb prompt is a first draft and is versioned with its records.
   - **Dependencies:** [420, 421, 424, 425] (effort sent, sandbox and scrubbed environment, leak scan, record store, cap and bound code); 402 normalized findings.
   - **Interfaces:** Provides stored real-bug cases, per-stage review and comb records, recipe scoring and the recall report. Consumed by 432.
   - **Follow-up outside this slice (#369):** shipped code-review defaults (P6, implement, implement-plan) are haiku-xhigh alone, because a pipeline review step takes one model. Once the first recipe's live run holds up, #369 lets the step name a recipe (haiku-xhigh + sol, opus-high comb) and makes it the default.
   - **Risk Level:** Medium (the hit rule; the graded-real share is agent-graded and needs a human-checked sample)
   - **Relative Effort:** 3/5

12. [ ] **(431) Implementation Report from Run Records** — A report over pipeline runs already recorded: per producer model and step (design, tasks, implement), the first-review verdict and finding counts by severity, revise rounds, pauses by kind, cost and turns, split by the slice's effort rating. No replay and no model calls. It is not controlled, since slice difficulty differs between runs, so each row shows its run count and no row is ranked below a stated floor.
   - **Value:** User-facing. Answers "which implementation model" from work already done. Alternating models across real slices turns it into a comparison at no extra cost.
   - **Success Criteria:**
     - Rows per step, model and effort sent, with the run count, from the run records and review files of every project with recorded runs.
     - Runs with no review, and runs whose records cannot be read, are counted and named, never dropped silently.
     - Finding categories are right for current reviews (needs #338 fixed).
   - **Dependencies:** 199 run listings, 175 usage records, review frontmatter; #338. [434] for recipe reviews: its `recipe_review` metrology records, read by `run_id` and `step_name`, and `aiRecipe` in review frontmatter.
   - **Interfaces:** Provides the implementation rows for `review-recall-results/SUMMARY.md` and `ANSWERS.yaml`.
   - **Risk Level:** Low
   - **Relative Effort:** 2/5

13. [ ] **(432) Document Review Recall from Real Corrections** — 430's method on documents: architecture documents, slice designs and task files. A case is a document as its review passed it, plus the flaws corrected later (a "correct the design" commit, a task rewrite after a blocked run). The spike is done (amended 20261119): the hand-run mining found 82 valid flaws in 43 cases from squadron, context-forge and migratory (19 arch, 32 slice, 31 tasks), far past the stop line of five, and the hand-run grids answered the first question (`review-recall-results/RESULTS.md` sections 16-20). What remains is making that repeatable, so a new model is measured on documents with one command instead of a hand-run grid and its grading agents.
   - **Value:** Shows which model reviews architecture documents, designs and task breakdowns, the checks that run before code is written, and re-measures cheaply when a new model arrives.
   - **Success Criteria:**
     - Document case kinds (arch, slice, tasks) load as 430 cases, reviewed with the matching template in 430's sandbox, and scored by 430's report.
     - Two cases are checked in: amoeba slice 260's task file with the #383 key, and one slice design. Every flaw has a later correcting commit.
     - One agent matcher labels hits under a cost bound taken from observed costs, so no person reads findings to score a run (#383).
     - Reduced 20261121 (PM): the import of the 43 mined cases, the section 16 reproduction, the added architecture cases (#373) and the question of flaws with no later commit moved to [#387](https://github.com/ecorkran/squadron/issues/387).
   - **Dependencies:** [430].
   - **Interfaces:** Consumes 430's case records, recipes and report.
   - **Risk Level:** Medium (document flaws are matched by agent grading, not by file location)
   - **Relative Effort:** 3/5

14. [x] **(433) Model Answers Report** — ⏪ Dropped 20261119. `review-recall-results/SUMMARY.md` and `ANSWERS.yaml` already give the per-category answer with its evidence and confidence, updated by hand when data changes. Real-work recipe rows come from `sq benchmark recall report --real-work` (434).

15. [x] **(434) Recipe Reviews in Pipelines** — A pipeline review step takes a 430 recipe by name in place of one model (`review-model: haiku-solr-luna-opus`). Its reviewers run on the real work, its combs filter their findings, and the kept findings (plus the uncombed NOTE and PASS findings) become the review the step acts on: one verdict, one review file, the same revise loop. Each stage's output, cost and kept/dropped decisions are recorded in the metrology store, keyed by run id, so every real P6 run that uses a recipe also leaves a record of it. Stages run one after another (#372). Can be built alongside 431.
   - **Value:** User-facing. Real slices get a review whose comb cuts the noise the reviser has to chase (430's live run, 20261118: no recipe found more bugs than haiku-xhigh alone, but haiku-solr-luna-opus halved the findings and cut those matching no known bug from 229 to 95). Recipe cost, revise rounds and finding counts then come from real work with no hand-run benchmark.
   - **Success Criteria:**
     - A pipeline's `review-model`, a step's `review.model` and `sq review --model` accept a recipe name; a single model alias works as before. A name that is neither fails before the run starts. A pool recipe is refused: its random pick could change the verdict between revise rounds (amended 20261118).
     - The review step's findings are the recipe's kept findings, and its verdict comes from them by the existing verdict rule. A revise round reruns the whole recipe.
     - A reviewer or comb stage that fails is reported in the review and the run record, never silently dropped from the merge.
     - Per-stage findings, kept/dropped decisions and cost are stored in the metrology store, keyed by run id, and readable by 430's report and 431.
     - The same recipe gives the same result shape from the CLI and slash commands. (Squadron has no MCP review tool; amended 20261118.)
   - **Dependencies:** [430, 425] (425 for content sidecars); review step dispatch.
   - **Interfaces:** Consumes 430's recipes and comb stage. Provides per-stage review records on pipeline runs that 431 reads.
   - **Risk Level:** Med (the merged verdict and how a failed stage affects it)
   - **Relative Effort:** 3/5

16. [ ] **(435) Repeated Reviewers and Finding Dedupe** — A recipe can run the same reviewer several times on one case run (`repeat: 3`) and merge the outputs, and duplicate findings across reviewers or repeats are merged into one issue before combing or counting. A vote filter keeps only issues raised by at least N of the repeats, as a comb that costs no model call beyond the dedupe. Added 20261118 from 430's live data: one haiku-xhigh run finds 35% of the real-bugs-nonsquadron bugs, but the union of its 3 runs finds 11 of 18 (61%), more than any measured recipe, at triple the findings.
   - **Value:** User-facing. Tests the cheapest known lever on recall (repeat a cheap reviewer) and whether agreement across repeats filters noise as well as an opus-high comb (haiku-opus: 1.4 findings/run, 36 matched nothing, but 15 of haiku's 19 bug hits).
   - **Success Criteria:**
     - A recipe declares a repeat count per reviewer. Stored single-review outputs are reused where the store already holds enough samples, and `run` prints the bound for only the missing ones.
     - Fan-out and repeat outputs pass through a dedupe stage that groups findings naming the same issue; the report gives findings/run both before and after dedupe, and a duplicate never counts twice after it.
     - The dedupe method is chosen by measurement, not assumed. 430's stored labels are the test set: findings labeled HIT for the same bug should merge, and findings labeled HIT for different bugs of one case must not. Candidates: file location alone; location plus sentence embeddings with a similarity threshold (graph or agglomerative clustering, as in the PM's [embedding-cluster](https://github.com/ecorkran/embedding-cluster), all-MiniLM-L6-v2 with a threshold sweep); location plus a cheap model grouping the findings. Embedding candidates cost no model call, so the sweep runs over every stored output.
     - A vote filter (`min_votes: N`) keeps an issue only when N or more repeats raised it, and is scored like a comb (kept/dropped per finding, recall lower and upper bounds).
     - The report compares, on real-bugs-nonsquadron: haiku-xhigh ×1, ×3 union, ×3 vote-2, ×3 + opus-high comb, against haiku-opus and haiku-solr-luna-opus.
     - 434 recipes in pipelines accept repeat and dedupe, so a production review can use them; a vote filter's verdict is deterministic for a fixed set of stage outputs.
   - **Dependencies:** [430]; [434] for production use.
   - **Interfaces:** Extends 430's recipe file, stage identities, scoring and report. Provides deduped finding groups that 436's sequential reviewer can read.
   - **Risk Level:** Med (dedupe quality: two findings in different words about one bug must merge, two bugs in one file must not)
   - **Relative Effort:** 3/5

17. [ ] **(436) Focused and Sequential Reviewers** — Two new reviewer shapes in a recipe. **Focused:** a reviewer entry names a focus (a rules file such as correctness, concurrency, error handling, security, tests), sent with the review the way `sq review --rules` sends one, so several cheap reviewers each look at one thing. **Sequential:** a reviewer stage reads the findings of the stages before it and is asked only what they missed; its findings join the merge. Neither shape has been measured: 430's design-review "second pass" was two independent reviews unioned, and the only sequential stages so far are two combs in a row.
   - **Value:** User-facing. Answers whether a narrow brief lifts cheap models (haiku, mimo, glm-flash) more than repetition does, and whether "find what they missed" beats an independent second reviewer.
   - **Success Criteria:**
     - A reviewer entry may carry a focus; the focus file's content is part of the stage identity, so a changed focus never reuses an old output.
     - A sequential stage names the stages it reads; its prompt carries their deduped findings (435), and it is stored and scored like any reviewer.
     - The report compares, on real-bugs-nonsquadron: haiku-xhigh with 3–4 focuses against haiku-xhigh ×3 (435), and haiku-xhigh → sequential mimo or sol-r against the same pair in parallel, each with and without the opus-high comb.
     - 434 recipes in pipelines accept both shapes.
   - **Dependencies:** [430, 435]. Scope is set by 435's results (amended 20261119): design starts only after 435's report exists. If repeat-and-vote clearly beats the measured recipes, the design cuts the shapes that report leaves little room for, and says which and why.
   - **Interfaces:** Extends 430's recipe file, stage runner and stage identities; reads 435's finding groups.
   - **Risk Level:** Med (a sequential reviewer that repeats or argues with earlier findings instead of finding new ones)
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

**Re-plan 20261115 (PM decision):**
- Slices 427–429 are dropped and 430–433 added (section "Measurement Slices"). The design and task writer comparison stays with 177's `sq replay`; it needs no new slice.
- The live runs on squadron in 426 were deleted and replaced by end-to-end tests on a fixture project.

**Relevance review 20261119 (PM decision):**
- 433 dropped: the hand-maintained SUMMARY.md and ANSWERS.yaml do its job.
- 432's spike is done (82 flaws in 43 cases); the slice now makes document recall repeatable and covers architecture documents (#373).
- 436's scope waits on 435's results.

**Open for slice design:**
- The producer-only mode's flag name and how it reports the stop (424).
- How the language-adapter seam is shaped beyond Python (421; only Python is implemented).
- How sandbox environment resolution handles projects without a lockfile (421).
- The diff-size rule for the judge (426).
- The rule for when a finding hits a known bug, and how recipes are stored and scored (430).
- The sample count, measured in 425 before any large run.

---

## Future Work
1. [ ] **(1) Additional Language Adapters** — Fairness rule and suite runner for TypeScript (package.json `bin`/`exports`/`main`) and other languages, so non-Python cf projects yield fix cases. Dependencies: [422]. Effort: 3/5.
2. [ ] **(2) OS-Sandboxed Replays** — Run replays under #213's OS sandbox once it lands. Dependencies: [424], #213. Effort: 2/5.
3. [ ] **(3) Concurrent Replays** — Run configs and samples in parallel (#146). Dependencies: [424], #146. Effort: 3/5.
