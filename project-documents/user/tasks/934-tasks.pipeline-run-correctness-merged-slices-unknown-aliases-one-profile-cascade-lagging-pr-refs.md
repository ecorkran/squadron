---
docType: tasks
slice: pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs
project: squadron
lld: user/slices/934-slice.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md
dependencies: [196, 197]
projectState: >
  Slice design complete (20261006) and through two review rounds (both CONCERNS, all findings
  addressed). No code written. 196 and 197 are complete. `git.integration_branch` is set
  (`squadron-issues`), so the slice branch forks from it.
dateCreated: 20261007
dateUpdated: 20261007
status: in_progress
---

## Context Summary

- Working on **934 pipeline-run-correctness**: four bugs where a run does the wrong thing
  instead of failing or finishing cleanly. #184 (one review-profile cascade) and #175 (unknown
  aliases, `--dry-run`), #188 (merged slice reads as open), #186 (lagging PR ref).
- Tasks reference the slice design by decision number (D1–D10). Its D-sections, the D10
  failure-mode tables, Success Criteria and Verification Walkthrough are the contract.
- Order follows the design's Development Approach: Part A (#184 + #175), Part B (#188),
  Part C (#186), Part D (docs, walkthrough, close-out). Each part is independent of the others.
- Every git test runs in a temporary repo the test creates, never the project checkout. Every
  D10 row has a test asserting both the outcome and the log record (level and message).
- Every task that changes code ends with `ruff format`, `ruff check`, `pyright` (zero errors),
  its tests, and a commit on the slice branch. Locate existing tests with `grep` before adding
  new files. Commit messages use the repo's semantic prefixes.
- Out of scope: `implement-plan` checking boxes or editing frontmatter (D1), changing cf's
  status derivation, the #131 base fast-forward rule (it only moves onto `adjustments`), GitLab
  and other hosts.
- Effort: 4/5. Closes #175, #184, #186, #188.

---

## Task 1 — Create the slice branch

- [x] Run `cf config get git.integration_branch`; call its value the target. Confirm `git status` is clean and the current branch is the target
- [x] `git checkout -b 934-slice.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs {target}`
  - [x] Success: `git branch --show-current` prints the new branch name

---

## Part A — #184 / #175: one review-profile cascade, per-action profile source, dry-run check

## Task 2 — `review/profile_resolution.py` (D3)

- [x] Create the module with `ReviewProfileSource` (StrEnum: `explicit`, `alias`, `template`, `config`, `default`) and `ReviewProfileChoice(name, source)`
- [x] `resolve_review_profile(explicit, alias_profile, template)` returns the choice in this order: explicit → alias profile → `template.profile` → `default_review_profile` → `ProfileName.SDK`
  - [x] The sdk fallback is `ProfileName.SDK`, never a `"sdk"` literal
- [x] `review_profile_source(explicit_present, template) -> bool` is True when explicit, `template.profile`, or `default_review_profile` is set; never for the alias profile or the sdk default
- [x] Both functions read `default_review_profile` through one private reader (find how `cli/commands/review.py:_resolve_profile` reads it today and move that read here)
- [x] Tests (`tests/review/`): one case per `ReviewProfileSource`, order precedence (explicit beats all, alias beats template, and so on), template `None`, and `review_profile_source` agreeing with `resolve_review_profile` (source is never `alias`/`default` when it returns True; True exactly when the source is `explicit`, `template` or `config`)
  - [x] Success: tests pass
- [x] Commit: `feat: add shared review profile resolution module`

## Task 3 — `sq review` delegates to the module

- [x] In `cli/commands/review.py`, delete `_resolve_profile` and make its call site use `resolve_review_profile`
- [x] `_reject_unknown_alias` computes its profile-source test with `review_profile_source`; no second copy of the "is a profile set" logic remains in the file
- [x] Tests: existing `tests/cli/test_review_profile.py` and `test_review_resolve.py` pass unchanged; add one case where `default_review_profile` makes a literal id acceptable
  - [x] Success: tests pass; `grep -n "_resolve_profile" src/` finds no definition
- [x] Commit: `refactor: route sq review profile cascade through shared module`

## Task 4 — `ModelResolver.resolve_full(profile_source=)` (D4)

- [x] In `pipeline/resolver.py`, add keyword `profile_source: bool | None = None` to `resolve_full`; `None` uses the run's value; `resolve()` unchanged. The run-level `profile_source` still drives dispatch, summary and compact
- [x] The backstop in `ModelResolver._resolved` uses the per-call value
- [x] Tests (`tests/pipeline/test_resolver.py`): override True accepts a literal id the run-level False would reject; override False rejects one the run-level True would accept; `None` falls back to the run-level value; `resolve()` unaffected
  - [x] Success: tests pass
- [x] Commit: `feat: per-call profile source on resolve_full`

## Task 5 — Pipeline review action uses the shared helper (D3, D4)

- [x] In `pipeline/actions/review.py`, replace the inline cascade with `resolve_review_profile(param, alias_profile, template)`, and pass `review_profile_source(param is not None, template)` to `resolver.resolve_full(..., profile_source=...)`
- [x] No `"sdk"` review-profile literal remains in the file
- [x] Tests (find the action's existing test file by grep): no `profile` param on a template declaring `profile:` runs on that profile; neither set and `default_review_profile` set runs on it; neither set and no config runs on sdk; explicit param still wins
  - [x] Success: tests pass; `grep -rn '"sdk"' src/squadron/pipeline/actions/review.py src/squadron/cli/commands/review.py` finds nothing used as a profile default
- [x] Commit: `fix: pipeline review step resolves profile like sq review (#184)`

## Task 6 — Parity test across both paths

- [x] Add one parametrized test, over every `ReviewProfileSource`, that sets up the same template, model and config and asserts `sq review` and the pipeline review action select the same profile name
  - [x] Success: test passes for all five sources
- [x] Commit: `test: assert review profile parity between sq review and pipeline`

## Task 7 — One template lookup in classification (D4)

- [x] In `pipeline/classification.py` add `_review_template(action_type, resolved_cfg) -> ReviewTemplate | None`. It **never raises**; an unknown name returns `None`
- [x] `_review_template_model_fallback` uses it, so the labelling path (`action_model_candidate` → `action_model_label` → `_summarize_action_config`) behaves exactly as before
- [x] Tests (`tests/pipeline/test_classification.py`): known template returned; unknown name returns `None` without raising; model fallback unchanged for known and unknown names
  - [x] Success: tests pass; existing classification tests unchanged
- [x] Commit: `refactor: single review template lookup in classification`

## Task 8 — Unknown review template fails before the run (D4)

- [x] Add `UnknownReviewTemplateError(name, close_matches)` as a `ValueError` subclass (next to `UnknownModelAliasError`). Message: `unknown review template 'cod'; did you mean: code?`
- [x] Add `_require_review_template(action_type, resolved_cfg) -> ReviewTemplate | None`: calls `_review_template`, raises the error when a fully resolved name returns `None`; skips a name still holding an unresolved placeholder
- [x] `classify_pipeline` catches the error and collects it with the alias errors into the single `ClassificationError`; it never escapes classification
- [x] Tests: unknown literal template fails before step 1; unknown template plus unknown alias reported in one message; placeholder name skipped; a review step whose template resolves only at run time to an unknown name fails through the review action's `KeyError` path with verbose labelling on, not from `action_model_label`; every built-in pipeline in `src/squadron/data/pipelines` classifies cleanly
  - [x] Success: tests pass
- [x] Commit: `feat: reject unknown review templates before the run`

## Task 9 — Review profile source in the alias check (D4, #175)

- [x] `_collect_unknown_alias` takes `profile_source: bool` from its caller. For each `review` action the caller loads the template via `_require_review_template` and passes `review_profile_source(...)`; other action types keep `has_profile_param`
- [x] Tests: a literal non-alias id with `default_review_profile` set passes classification for a review step; the same id with no profile source fails with the same message and close matches `sq review` gives; a template-declared `profile:` makes a literal id acceptable; non-review actions unchanged
  - [x] Success: tests pass
- [x] Commit: `fix: alias check uses the review step's real profile source (#175, #184)`

## Task 10 — `_classify_for_run` in `cli/commands/run.py` (D5)

- [x] Add `_classify_for_run(definition, *, model_override, params, strict) -> PipelineClassification` owning policy (YAML `auth_policy` < `--strict`), `DefaultPoolBackend()`, the `ModelResolver(... profile_source=has_profile_param(params))`, and the `classify_pipeline` call; it raises `ClassificationError`
- [x] `_run_pipeline_sdk` uses it in place of its inline block (its own pool backend for the authoritative resolver is unchanged); `--explain` uses it with `explain_params`; the second inline copy is deleted
  - [x] Success: existing run and explain tests pass unchanged
- [x] Commit: `refactor: share one classification helper between run and explain`

## Task 11 — `--dry-run` classifies (D5, #175)

- [x] `--dry-run` calls `_classify_for_run` with params from `_assemble_params` and `_extract_model_override(model, param)`, and accepts `--strict` like the other paths
- [x] On `ClassificationError` print the run path's message (`Error: Pipeline classification failed — …`) and exit 1 before rendering any step; on success render as today
- [x] Tests: `review 931 --model glm-flash-low. --dry-run` exits 1 with `unknown model alias 'glm-flash-low.'; did you mean: glm-flash-low?`; a valid model renders the same step list as before; `--dry-run --strict` is accepted, raises the same errors as a strict run, otherwise renders the same step list; a real run with the bad alias fails before step 1 and the slot's existing review artifact is byte-identical afterwards (fixture file, compare bytes)
  - [x] Success: tests pass
- [x] Commit: `fix: sq run --dry-run runs the pre-run alias check (#175)`

## Task 12 — Part A validation

- [x] Run the full test suite once, plus `ruff format`, `ruff check`, `pyright`
  - [x] Success: all pass; zero pyright errors
- [x] Commit any formatter changes: `style: format part A`  (skip if none)

---

## Part B — #188: git is the record of a merged slice

## Task 13 — `merged_slice_branches` predicate (D1, D10)

- [x] In `pipeline/git_ops.py` add `merged_slice_branches(entries, target, cwd) -> set[int]`. Branch names come from the same helper the enter step uses (locate with grep; do not re-derive)
  - [x] One `for-each-ref refs/heads` call for tips, one `rev-list --first-parent {target}` call, one `merge-base --is-ancestor` call per candidate
  - [x] A slice is merged only when its tip is an ancestor of the target **and** not on the target's first-parent chain
  - [x] A missing branch reads as not merged, with no log
  - [x] Any timeout (`run_git` returns `None`) or unexpected exit (for `--is-ancestor`: not 0 or 1) logs ERROR via `_logger.error(message)` (as `git_ops.py` does before its other `GitStateUnknownError` raises; there is no active exception, so not `logger.exception`) naming the command and stderr, and raises `GitStateUnknownError`. Never returns an empty set on failure
- [x] Docstring cites the `--no-ff` assertion at `tests/pipeline/test_branch_merge.py:88`
- [x] Tests in `tests/pipeline/test_git_ops.py` (real temp repos): `--no-ff` merged → in the set; fast-forward merged → not; branch entered with no commits → not; missing branch → not; mixed set returns only merged. D10 rows with the fake/patched `run_git`: each of the three calls timing out and exiting non-zero raises `GitStateUnknownError` with the asserted ERROR record (target missing for `rev-list`)
  - [x] Success: tests pass
- [x] Commit: `feat: add merged_slice_branches predicate`

## Task 14 — Sources take `cwd` (D1)

- [x] `SourceFn` gains keyword `cwd: str`; all four registered sources accept it (only `slices_ready_to_implement` uses it)
- [x] `evaluate_each_source(source, params, cf_client, *, cwd)` passes it on
- [x] Callers pass the cwd they already hold: executor `effective_cwd`, item resume `cwd`, the dry-run renderer (`run_dry_run.py`, from `run()`)
- [x] Tests: each caller hands the source its cwd (fake source records it); existing source and executor tests updated for the new keyword
  - [x] Success: tests pass; pyright clean
- [x] Commit: `refactor: pass the run cwd to each-sources`

## Task 15 — `slices_ready_to_implement` treats merged slices as closed (D1)

- [x] Call `merged_slice_branches(entries, target, cwd)` once. Target comes from `read_integration_target`
- [x] Item loop skips `entry.index in merged`; `open_in_plan` excludes merged indexes; `in_plan` unchanged
- [x] One WARNING per merged slice: `slice N: branch B is merged into T but cf reports S; treating it as complete. Check off its tasks to close it in cf.`
- [x] A `GitStateUnknownError` from the predicate propagates, so the `each` step fails before any item runs, logged and reported as a cf failure in a source is today
- [x] Tests (`tests/pipeline/test_sources.py`, temp repo + fake cf): merged unchecked slice A absent from items; dependent B carries no `flag_reason`; WARNING record asserted; open-per-cf, unmerged dependency still flagged exactly as before; source run with a `cwd` different from the process cwd gets that repo's answer; predicate failure fails the step before any item
  - [x] Success: tests pass
- [x] Commit: `fix: batch selection treats merged slices as complete (#188)`

## Task 16 — Item resume uses the predicate (D1)

- [x] `_open_dependencies` counts a dependency complete if cf says so or the predicate reports it merged
- [x] `_select_item` reconcile path: an item no longer selected reconciles to PASSED when the predicate reports it merged, whatever cf's status
- [x] A predicate failure surfaces as the resume's error and changes no report record
- [x] Tests (`tests/pipeline/test_item_resume_*.py`): resume of B runs with no `dependency A not complete`; resume of merged A reconciles to PASSED; unmerged open dependency still blocks; predicate failure leaves `report.json` unchanged
  - [x] Success: tests pass
- [x] Commit: `fix: item resume trusts git for merged slices (#188)`

## Task 17 — Part B validation

- [x] Run the full test suite once, plus `ruff format`, `ruff check`, `pyright`
  - [x] Success: all pass; zero pyright errors
- [x] Commit any formatter changes: `style: format part B`  (skip if none)

---

## Part C — #186: lagging PR ref

## Task 18 — Models and errors (D7, D8, D9)

- [x] `codehost/models.py`: add `RefAdjustment(role, reported_sha, used_sha, source, reason)` and `FetchedRange.adjustments: tuple[RefAdjustment, ...]` (default empty)
- [x] `codehost/errors.py`: add `RENDERED_BY_CALLER` (the `extra` key constant) and `PullRequestHeadUnavailableError` (a `CodeHostError`, role HEAD) with the D7 message and hint
- [x] `RefMovedSinceResolutionError` gains required keyword-only `expected_source` and `actual_source` (no defaults, so no silent label), the D7 message, and hint `Rerun to resolve the pull request again.`
  - [x] Update its one existing call site, `refs._verify` (it serves both base and head): `expected_source="host API"`, `actual_source` the ref that was read (e.g. `refs/pull/49/head`, or the base ref). The `_verify` WARNING is tagged `extra={RENDERED_BY_CALLER: True}`
  - [x] Update the existing constructions and message assertions in `tests/codehost/test_refs.py` (grep `RefMovedSinceResolutionError`) to the new signature and message
- [x] Tests (`tests/codehost/`): message text names each source and sha; hints present; `adjustments` defaults to `()`; a base-side move through `_verify` names its sources
  - [x] Success: tests pass; existing `test_refs.py` cases updated, none deleted
- [x] Commit: `feat: add RefAdjustment and source-naming code host errors`

## Task 19 — Base fast-forward onto `adjustments` (D9)

- [x] The #131 base fast-forward in `refs.py` records a `RefAdjustment` (role BASE) instead of a log-only note. Its WARNING stays untagged here: Task 25a tags it in the same commit that prints the adjustment line, so no run ever has the tag without the line
- [x] Tests: existing #131 tests pass; the fast-forward case returns one adjustment with the reported and used shas
  - [x] Success: tests pass
- [x] Commit: `refactor: record base fast-forward as a ref adjustment`

## Task 20 — Primary fetch timeout (D10)

- [x] In `refs.py`, convert `ProcessTimedOutError` on the primary `_fetch` into `HostCommandTimeoutError`, as `github_cli.py` does for `gh` calls, logging a WARNING tagged `extra={RENDERED_BY_CALLER: True}` first (the command renders the error)
- [x] Tests (fake `ProcessRunner`): primary fetch timeout raises `HostCommandTimeoutError`, not a traceback
  - [x] Success: tests pass
- [x] Commit: `fix: render primary PR fetch timeout as a code host error`

## Task 21 — Obtain the API head locally (D6 step 1)

- [x] In `refs.py` add a helper that, given the API head sha, makes it present locally. `cat-file -e <sha>^{commit}` first; if absent, try in order, each into `<api_local>` (a sibling of `head_local` in the per-PR namespace): (1) `fetch <remote> +<sha>:<api_local>`; (2) for each entry of the new argument `head_fallback_sources: tuple[str, ...]`, `fetch <remote> +<entry>:<api_local>`. The helper itself names no host refspec
- [x] After each attempt `rev-parse <api_local>` must equal the API head sha; a mismatch rejects that attempt
- [x] A `cat-file` timeout (`ProcessTimedOutError`) raises `HostCommandTimeoutError` with a tagged WARNING; a non-zero `cat-file` exit means absent (DEBUG) and goes to the fetch attempts
- [x] A fallback attempt catches `ProcessTimedOutError` and records `timed out after Ns`; non-zero exit records stderr. Each attempt logs DEBUG
- [x] No attempt yields the sha: raise `PullRequestHeadUnavailableError` naming every source with its sha or reason (WARNING tagged `RENDERED_BY_CALLER`)
- [x] Tests (fake runner; the API head sha **absent** locally before the fetch): sha already present → no fetch; `cat-file` timeout → `HostCommandTimeoutError`; `cat-file` non-zero → proceeds to fetch; fetch-by-sha succeeds; sha fetch `not our ref` then a fallback source succeeds; fallback returns a different sha → rejected; timeout on a fallback recorded as the reason; all fail → error naming each source
  - [x] Success: tests pass
  - [x] The helper has no caller until Task 22a wires it; that is expected
- [x] Commit: `feat: fetch the API head by sha or fallback source when the PR ref lags`

## Task 22a — Classify the PR-ref sha against the API head (D6 step 2)

- [x] In `fetch_and_range`, when the PR-ref sha differs from the API head: call Task 21's helper first, then test whether the PR-ref sha is an ancestor of the API head (`merge-base --is-ancestor`). Express the answer as a private `HeadRelation` StrEnum (`LAGS`, `MOVED`, `UNRELATED`). `MOVED` and `UNRELATED` raise `RefMovedSinceResolutionError` naming both sources, hint rerun. `LAGS` keeps today's behavior in this task: it raises the same `RefMovedSinceResolutionError`. Task 22b replaces that one branch
- [x] Tests (lagging fixture from the issue, API sha absent locally until a fallback fetch): pushed after resolution → `RefMovedSinceResolutionError`; unrelated → same; ancestry timeout and non-0/1 exit answer "no" with the existing WARNING, giving the same error; `LAGS` currently raises (the test is rewritten in 22b)
  - [x] Success: tests pass
- [x] Commit: `feat: classify lagging, moved and rewritten PR refs`

## Task 22b — Use the API head on a lagging ref (D6, D9, D10)

- [x] Replace 22a's `LAGS` raise: `update-ref head_local <api-sha>`, record a head `RefAdjustment` (its WARNING stays untagged; Task 25a tags it), build the range on the API head. Only the exact API head sha is ever reviewed
- [x] `update-ref` failure renders `RefNotFetchableError`; timeout renders `HostCommandTimeoutError`; both log a tagged WARNING
- [x] Tests: lag → range built on the API head with one adjustment; `update-ref` non-zero and timeout; 22a's `LAGS`-raises test is replaced by the lag-success test. `uv run pytest tests/codehost -k lagging -v` selects the lag cases (name them accordingly)
  - [x] Success: tests pass
- [x] Commit: `fix: review the API head when refs/pull/N/head lags (#186)`

## Task 23 — GitHub adapter passes the head refspec (D6)

- [x] `fetch_pull_request_refs` passes `("refs/heads/<head_ref>",)` as `head_fallback_sources` to `fetch_and_range`; `refs.py` stays host-neutral (`test_import_boundaries.py` passes)
- [x] Tests (`tests/codehost/test_github_cli.py`): the adapter passes the expected sources; a fork PR whose same-named base branch returns another sha is rejected by the sha check
  - [x] Success: tests pass
- [x] Commit: `feat: github adapter supplies head branch fallback refspec`

## Task 24a — `code_host_logging` context manager (D8)

- [ ] Add `code_host_logging(verbosity: int)` next to `render_code_host_error`. On entry: record the `squadron.codehost` logger level, add one stderr handler (format `%(levelname)s %(name)s: %(message)s`) with the tag filter, set level WARNING/INFO/DEBUG for verbosity 0/1/2+. On exit (`finally`): remove exactly that handler, restore the level. `propagate` untouched
- [ ] Filter drops records carrying `RENDERED_BY_CALLER` below verbosity 2 and keeps them at 2+
- [ ] Nested entry is a no-op on entry and exit
- [ ] Tests (log records emitted directly in the test, with and without the tag): tagged absent at verbosity 0 and 1, present at 2 with prefix; untagged reaches stderr at every verbosity; entering twice shows one handler inside and zero after, level restored; a raised `typer.Exit` inside still cleans up; records still reach `caplog`
  - [ ] Success: tests pass
- [ ] Commit: `feat: code host logging scope that prints each failure once`

## Task 24b — Tag the remaining pre-raise WARNINGs (D8)

- [ ] Tasks 18, 20, 21 and 22b tagged their own records; the adjustment WARNINGs are tagged in 25a. Tag exactly these remaining sites with `extra={RENDERED_BY_CALLER: True}`, each of which logs and then raises a `CodeHostError`:
  - [ ] `codehost/refs.py`: the `_fetch` failure WARNING per endpoint, the `git fetch exited` WARNING, the `ref … is missing after fetch` WARNING in `_verify`, and the `no merge base` WARNING
  - [ ] `codehost/github_cli.py`: `_log_and_raise`, the `gh is not on PATH` WARNING, and the `gh exceeded …s` WARNING
- [ ] Leave untagged: the nonexistent-cwd WARNING (re-raises a non-`CodeHostError`), the review-thread page-limit WARNING, the ancestry-answered-no WARNING, and every WARNING in `remotes`, `worktree`, `metadata_lock`
- [ ] Tests: for each tagged site, drive the failure through the fake runner or fake `gh` and assert the record carries the tag; assert the untagged sites listed above do not
  - [ ] Success: tests pass
- [ ] Commit: `fix: tag code host warnings the command prints itself`

## Task 25a — Print adjustments and record the reviewed head (D9)

- [ ] Print each `RefAdjustment` once, dim, on stderr: `head: refs/pull/49/head lags; reviewed ae1cbf2… fetched by sha`; `sq review pr` and `sq pr show` share the fetch path, so both print it. The PR review artifact's provenance records the head sha actually reviewed
- [ ] Tag the adjustment WARNINGs (Tasks 19 and 22b) with `extra={RENDERED_BY_CALLER: True}` in this task, now that the line they duplicate exists. The tag stays inert until Tasks 25b/25c install the handler
- [ ] Tests: lag success prints exactly one adjustment line and the artifact carries the API head sha; a base fast-forward adjustment prints once; both adjustment records carry the tag
  - [ ] Success: tests pass
- [ ] Commit: `feat: print ref adjustments and record the reviewed head sha`

## Task 25b — Wire `sq review pr` (D8)

- [ ] Wrap the body after `_resolve_verbosity(verbose)` in `with code_host_logging(verbosity):`
- [ ] Tests (`tests/cli/test_review_pr.py`): a `CodeHostError` appears on stderr exactly once at default and `-v`; at `-vv` the tagged WARNING also appears; an untagged codehost WARNING shows at default verbosity; at default verbosity a lag success shows the adjustment line once and no duplicate WARNING; a fetch timeout never produces a traceback
  - [ ] Success: tests pass
- [ ] Commit: `fix: print code host failures once in sq review pr (#186)`

## Task 25c — Wire `sq pr show` and `sq pr create` (D8)

- [ ] Both call `code_host_logging(0)`; no new flags
- [ ] Tests: `tests/cli/test_pr_show.py` and `tests/cli/test_pr_create_failures.py` each assert a `CodeHostError` appears on stderr exactly once and an untagged codehost WARNING still shows
  - [ ] Success: tests pass
- [ ] Commit: `fix: print code host failures once in sq pr show and create`

## Task 26 — Part C validation

- [ ] Run the full test suite once, plus `ruff format`, `ruff check`, `pyright`
  - [ ] Success: all pass; zero pyright errors
- [ ] Commit any formatter changes: `style: format part C`  (skip if none)

---

## Part D — Docs and verification

## Task 27 — Documentation

- [ ] `docs/PIPELINES.md`: merged slices count as complete in `implement-plan` and item resume (git is the record); review profile cascade shared with `sq review`; unknown review template and alias rejected pre-run, including `--dry-run`
- [ ] `CHANGELOG.md`: short user-facing bullets for the four fixes; technical detail stays in DEVLOG
  - [ ] Success: docs match behavior
- [ ] Commit: `docs: document pipeline run correctness fixes`

## Task 28 — Live walkthrough

- [ ] Run Verification Walkthrough steps 1, 3 and 4 from the slice design (step 4: the unit fixture via `uv run pytest tests/codehost -k lagging -v`) with `CLAUDECODE` unset and `uv run`; always pass `--model`
- [ ] Step 2: needs a non-SDK profile with credentials already configured. With one, run both commands and show `profile=…` in both headers; restore the config key afterwards. Without one, run only the unset half (both fail with the same message) and say so in the DEVLOG
- [ ] Record each step's command and key output line in the DEVLOG entry
  - [ ] Success: each step matches the design; any divergence is fixed (with a test) or filed as a GitHub issue linked from the DEVLOG
- [ ] Commit: `docs: add slice 934 implementation DEVLOG entry`

## Task 29 — Close out

- [ ] Set this file's `status: complete`; slice design `status: complete`; check off 934 in `900-slices.maintenance-and-refactoring.md`
- [ ] Commit: `docs: mark slice 934 complete`
  - [ ] Success: commit on the slice branch; tree clean

---

## Notes

- No merge task is listed: Phase 7 merges the slice branch into the target after the code review. The merge or a closing comment linking the slice closes #175, #184, #186, #188.
- Tasks 22, 24 and 25 were split into lettered sub-tasks (22a–b, 24a–b, 25a–c) after the tasks review; other numbers are unchanged.
