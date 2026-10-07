---
docType: review
layer: project
reviewType: slice
slice: pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs
project: squadron
verdict: CONCERNS
verdictSource: derived
sourceDocument: project-documents/user/slices/934-slice.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md
aiModel: deepseek/deepseek-v4.1-flash
status: complete
dateCreated: 20261006
dateUpdated: 20261006
reviewedSha: 3cd6ad940a90427fb01fbdbb65dd6764a655d063
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 45
turns: 20
promptTokens: 1427154
cachedTokens: 1203200
completionTokens: 85238
reasoningTokens: 78745
durationSeconds: 621.4
runId: run-20261007-p4-ced11784
squadronVersion: 0.20.1
findings:
  - id: F001
    severity: pass
    category: architecture-boundary
    summary: "New fetch fallback keeps host conventions out of the host-neutral ref module"
    location: "project-documents/user/slices/934-slice.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md#technical-decisions"
  - id: F002
    severity: pass
    category: refactoring
    summary: "One profile cascade replaces two, which is what the parent architecture asks for"
    location: "project-documents/user/slices/934-slice.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md#technical-requirements"
  - id: F003
    severity: concern
    category: error-handling
    summary: "No failure-mode enumeration for the new git and network I/O paths"
    location: "project-documents/user/slices/934-slice.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md#technical-decisions"
  - id: F004
    severity: concern
    category: error-handling
    summary: "D8 suppresses `squadron.codehost` diagnostics wholesale at the verbosity operators actually use"
    location: "project-documents/user/slices/934-slice.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md:188"
  - id: F005
    severity: concern
    category: error-handling
    summary: "D4's \"no new failure path is added\" premise does not hold for an unknown review template"
    location: "project-documents/user/slices/934-slice.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md#technical-decisions"
  - id: F006
    severity: concern
    category: error-handling
    summary: "D5 under-specifies the dry-run classification and omits the pool backend"
    location: "project-documents/user/slices/934-slice.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md:159"
  - id: F007
    severity: concern
    category: error-handling
    summary: "The #188 predicate reads git in the process cwd, which is a second source of \"the repository\""
    location: "project-documents/user/slices/934-slice.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md:131"
  - id: F008
    severity: note
    category: scope
    summary: "The bundle grew past the plan entry's four items without a restated risk or effort"
    location: "project-documents/user/slices/934-slice.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md#technical-scope"
---

# Review: slice — slice 934

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [PASS] New fetch fallback keeps host conventions out of the host-neutral ref module

`refs.py` states its own boundary in its docstring — "the caller supplies the refspec sources, because a refspec is the *host's* convention, and nothing here names a host" — and `github_cli.py` already supplies `refs/pull/N/head` and `refs/heads/<base>`. D6's decision to pass the two fallback refspecs in as `head_fallback_sources: tuple[str, ...]` rather than constructing them in `refs.py` preserves that direction rather than inverting it, and no new module is created just to hold two strings. This is the correct shape for the change.

### [PASS] One profile cascade replaces two, which is what the parent architecture asks for

`review/profile_resolution.py` owning `ReviewProfileSource`, `ReviewProfileChoice`, `resolve_review_profile`, and `review_profile_source` directly serves 900's stated scope ("consolidating duplicated logic", "improving module boundaries"), and the design makes the consolidation testable rather than aspirational: `_resolve_profile` and the inline cascade are deleted, `"sdk"` as a review-profile literal is gone, and parity across every `ReviewProfileSource` is a success criterion. The single private reader for `default_review_profile` (D3) is the right response to the drift 196 D13 documented by hand.

### [CONCERN] No failure-mode enumeration for the new git and network I/O paths

The parent 900 architecture has no NFRs of its own, so nothing is owed on that axis — but the project's Failure-Mode Enumeration rule (`review-code.md`: for each new I/O path, what if it hangs, times out, or the peer disconnects mid-send, explicitly and observably) is owed, and this slice violates it in both directions while citing it in passing (`:188` reads "The adapter keeps logging every failure at WARNING (Failure-Mode Enumeration)" as though a section existed).

Specific gaps I can verify against the code:

- **The two fallback fetches (D6, `:168-180`).** `refs._fetch` bounds one `git fetch` at `GIT_FETCH_TIMEOUT_SECONDS = 300` and raises `RefNotFetchableError` when a destination ref is absent afterward. The design adds up to two more fetches through that path but never states the per-fetch bound, the worst-case wall clock (two additional 300s fetches plus verification, on top of the original), or what the operator sees when a fallback fetch times out versus when the remote refuses versus when the connection drops mid-send. `_fetch`'s "both refs present despite a non-zero exit" branch also becomes load-bearing once the same local ref is a fallback destination.
- **The #188 predicate's reads (`:131`).** `for-each-ref` plus one `rev-list --first-parent <target>` plus one `--is-ancestor` per candidate. The design states only "A git failure is logged and raises `GitStateUnknownError`." That does not distinguish a non-zero exit from a timeout from git not running at all, and `rev-list --first-parent` on a long-lived target emits the entire first-parent history — unbounded output on a large repository is not addressed, nor is the per-call timeout.
- **The `-vv` routing decision (D8) is stated but the record that no longer surfaces by default is not enumerated**, which is the same finding as below from the other side.

The neighbouring slices in this initiative (916, 917, 919, 930, 931) each carry an explicit enumeration section; this one should too, and the graph in D6 could then say what the operator sees at each terminal node rather than only which exception type is raised.

### [CONCERN] D8 suppresses `squadron.codehost` diagnostics wholesale at the verbosity operators actually use

The diagnosis is correct and I verified it: `setup_logging()` is called from no production entry point (confirmed by `cli/app.py` having no call and by analysis 941 F015/F016), so Python's `logging.lastResort` is indeed what echoes the adapter's WARNING bare to stderr, and the duplicate is real.

The remedy is over-broad, though. D8 attaches a `NullHandler` to the whole `squadron.codehost` logger below `-vv`. Many WARNING records in that package never accompany a raised `CodeHostError` that `render_code_host_error` will print, so nothing replaces them: `worktree.py`'s orphan-sweep, `prune`-timeout, metadata-lock, and worktree-removal warnings (`:255`, `:264`, `:273`, `:289`, `:292`, `:314`, `:456`, `:460`, `:468`), `metadata_lock.py`'s unlock/close failures, and `github_cli.py`'s "gh is not on path" / "nonexistent cwd" / "gh exceeded Ns" records on paths that are handled rather than raised. Under D8 every one of those becomes invisible at default and `-v`. The rule this project enforces mechanically (`review-code.md`) requires each failure mode to be *observable* — log at WARNING+ — and this change removes observability from a whole package at the default setting.

The design is aware of the coupling but only compensates for one case: D9 exists specifically because "without this the #131 note would disappear at default verbosity." That makes `RefAdjustment`/`FetchedRange.adjustments` a workaround for the handler policy rather than an independent decision, and it says nothing about the worktree and metadata-path records D9 does not cover. Either scope the suppression to the records that genuinely duplicate an error about to be rendered (for example suppress only while `render_code_host_error` is on the stack), or state explicitly that the package's WARNING stream moves to `-vv` and that D9's adjustments cover only the ref path — and note the systemic gap against 941 F016 rather than adding a third ad-hoc handler convention.

### [CONCERN] D4's "no new failure path is added" premise does not hold for an unknown review template

D4 has classification load the template named in the action config "after placeholder resolution" and call `review_profile_source` on it, justified by "An unknown template is already a classification error, so no new failure path is added." I could not confirm that premise; the code says otherwise. `classification._review_template_model_fallback` loads the template and returns `template.model if template is not None else None` — it does not raise. `classify_pipeline` raises `ClassificationError` only when the *candidate* is `None`, i.e. when the action has no model at any cascade level. So a review action with `template: typo` plus a model supplied anywhere else (pipeline model, step model, CLI override) classifies cleanly today, and the new code then reaches `review_profile_source(explicit_present, template)` with no template. What it returns — and whether it disagrees with the runtime review action, which does fail on an unresolvable template — is undefined, and it is exactly the CLI-versus-pipeline divergence this slice exists to remove.

Either establish that the template lookup in the new path cannot miss (and restate what happens if it does), or handle the miss explicitly with a defined result. Worth noting the runtime half also differs by path today: the pipeline action surfaces it as an action failure, and `template_inputs` treats an unknown name as "one unchanged dict" (slice 930's task), so this is not one behavior to inherit but three.

### [CONCERN] D5 under-specifies the dry-run classification and omits the pool backend

D5 promises `--dry-run` reports `UnknownModelAliasError` "the same way a run does (exit 1, same message, same close matches)." `classify_pipeline` raises `ClassificationError` for at least two other causes, and one of them is reachable purely because dry-run has no backend to give it:

- A `pool:` candidate with no pool backend raises `ClassificationError("... resolves to pool 'x' but no pool backend is configured")`. Verified: the current dry-run branch in `cli/commands/run.py` assembles params and calls `render_steps(...)` with no resolver and no backend, whereas both `_run_pipeline_sdk` and `_handle_explain` construct `DefaultPoolBackend()`. Wiring classification into dry-run without doing the same makes `sq run --dry-run` exit 1 on any pipeline containing a pool reference that a real run accepts — the preview refusing what the run performs.
- An action with no model at any cascade level raises a different `ClassificationError`.

Neither the design nor the success criteria say which failures count as "the same message," or that the other `ClassificationError` causes must be treated as preview failures too. The functional criterion is also stated as a prediction rather than a verified fact ("A real run fails before step 1"), while the corresponding success criterion for #188 pins the exact WARNING text — the same precision is warranted here.

### [CONCERN] The #188 predicate reads git in the process cwd, which is a second source of "the repository"

D1 grants the predicate `os.getcwd()` "at the call site," reasoning that `sources.py` makes every `cf` call in the process cwd and "The executor's `effective_cwd` already defaults to it." The default is not the contract: `executor.py:473` is `effective_cwd = cwd or os.getcwd()` — `execute_pipeline` accepts an explicit `cwd`, and `evaluate_each_source` does not receive it. So the predicate would answer about one repository while the executor runs in another, silently, whenever a caller passes `cwd=`.

There is a sharper version of the same problem. The target comes from `read_integration_target(cf_client)`, i.e. cf's registered project identity; the branch tips would come from the process directory. Two roots for one answer, agreeing while the CLI is the only caller — which is precisely the hidden dependency the design's own "reads git each time and caches nothing" stance is meant to avoid. Threading the executor's `effective_cwd` into the source call (or reading it from the cf client) removes the second source; if the process cwd is genuinely the intended one, that is a decision worth recording as one, since `evaluate_each_source` is also invoked by `sq run --dry-run` and by item resume (`item_resume.py:151`, which passes its own `cwd`).

### [NOTE] The bundle grew past the plan entry's four items without a restated risk or effort

900's guidance is "Slices in this initiative should be small and focused — prefer many small slices over few large ones" and "Each slice should be independently deliverable," and the plan entry itself bundled the four issues (so the bundling is not the finding). What the design adds beyond the entry is: `RefAdjustment` plus `FetchedRange.adjustments` as new provenance covering #131 (D9), and a package-wide logging policy applied to "every such command" (D8). Neither is mentioned in the plan entry's summary, which rated the work "Risk: Low · Effort: 3/5." The design should say why these ride along rather than shipping as their own maintenance slice, and whether the plan's figures still hold — particularly since D8/D9 introduce a coupling (one exists because the other hides a record) that the plan entry does not reflect.

### Run Digest

- Response length: 13252 chars
- Response is newline-free: no
- Tool calls made: 45
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 333268
- Effort: backend default
- Turns: 20
- Tokens — prompt / cached / completion / reasoning: 1427154 / 1203200 / 85238 / 78745
- Duration: 621.4 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8

### Raw Response

## Summary
[CONCERNS]

The slice is well-aimed at the parent architecture: every change lands in the 900 initiative's declared scope (refactoring, consolidating duplicated logic, bug fixes, operational logging/error handling), and the design respects the two boundaries I could verify — `codehost` staying host-neutral, and one review-profile cascade instead of two. Several concrete gaps should be closed before implementation: the new git/network I/O paths have no enumerated failure modes, D8 removes observability from a whole package at the default verbosity, D4's "no new failure path" premise does not hold against the classifier's actual behavior, D5 does not account for the other `ClassificationError` causes or for supplying a pool backend, and the #188 predicate's `cwd` is taken from a second source that only coincides with the executor's by convention.

## Findings

### [PASS] New fetch fallback keeps host conventions out of the host-neutral ref module
category: architecture-boundary
location: project-documents/user/slices/934-slice.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md#technical-decisions
`refs.py` states its own boundary in its docstring — "the caller supplies the refspec sources, because a refspec is the *host's* convention, and nothing here names a host" — and `github_cli.py` already supplies `refs/pull/N/head` and `refs/heads/<base>`. D6's decision to pass the two fallback refspecs in as `head_fallback_sources: tuple[str, ...]` rather than constructing them in `refs.py` preserves that direction rather than inverting it, and no new module is created just to hold two strings. This is the correct shape for the change.

### [PASS] One profile cascade replaces two, which is what the parent architecture asks for
category: refactoring
location: project-documents/user/slices/934-slice.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md#technical-requirements
`review/profile_resolution.py` owning `ReviewProfileSource`, `ReviewProfileChoice`, `resolve_review_profile`, and `review_profile_source` directly serves 900's stated scope ("consolidating duplicated logic", "improving module boundaries"), and the design makes the consolidation testable rather than aspirational: `_resolve_profile` and the inline cascade are deleted, `"sdk"` as a review-profile literal is gone, and parity across every `ReviewProfileSource` is a success criterion. The single private reader for `default_review_profile` (D3) is the right response to the drift 196 D13 documented by hand.

### [CONCERN] No failure-mode enumeration for the new git and network I/O paths
category: error-handling
location: project-documents/user/slices/934-slice.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md#technical-decisions
The parent 900 architecture has no NFRs of its own, so nothing is owed on that axis — but the project's Failure-Mode Enumeration rule (`review-code.md`: for each new I/O path, what if it hangs, times out, or the peer disconnects mid-send, explicitly and observably) is owed, and this slice violates it in both directions while citing it in passing (`:188` reads "The adapter keeps logging every failure at WARNING (Failure-Mode Enumeration)" as though a section existed).

Specific gaps I can verify against the code:

- **The two fallback fetches (D6, `:168-180`).** `refs._fetch` bounds one `git fetch` at `GIT_FETCH_TIMEOUT_SECONDS = 300` and raises `RefNotFetchableError` when a destination ref is absent afterward. The design adds up to two more fetches through that path but never states the per-fetch bound, the worst-case wall clock (two additional 300s fetches plus verification, on top of the original), or what the operator sees when a fallback fetch times out versus when the remote refuses versus when the connection drops mid-send. `_fetch`'s "both refs present despite a non-zero exit" branch also becomes load-bearing once the same local ref is a fallback destination.
- **The #188 predicate's reads (`:131`).** `for-each-ref` plus one `rev-list --first-parent <target>` plus one `--is-ancestor` per candidate. The design states only "A git failure is logged and raises `GitStateUnknownError`." That does not distinguish a non-zero exit from a timeout from git not running at all, and `rev-list --first-parent` on a long-lived target emits the entire first-parent history — unbounded output on a large repository is not addressed, nor is the per-call timeout.
- **The `-vv` routing decision (D8) is stated but the record that no longer surfaces by default is not enumerated**, which is the same finding as below from the other side.

The neighbouring slices in this initiative (916, 917, 919, 930, 931) each carry an explicit enumeration section; this one should too, and the graph in D6 could then say what the operator sees at each terminal node rather than only which exception type is raised.

### [CONCERN] D8 suppresses `squadron.codehost` diagnostics wholesale at the verbosity operators actually use
category: error-handling
location: project-documents/user/slices/934-slice.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md:188
The diagnosis is correct and I verified it: `setup_logging()` is called from no production entry point (confirmed by `cli/app.py` having no call and by analysis 941 F015/F016), so Python's `logging.lastResort` is indeed what echoes the adapter's WARNING bare to stderr, and the duplicate is real.

The remedy is over-broad, though. D8 attaches a `NullHandler` to the whole `squadron.codehost` logger below `-vv`. Many WARNING records in that package never accompany a raised `CodeHostError` that `render_code_host_error` will print, so nothing replaces them: `worktree.py`'s orphan-sweep, `prune`-timeout, metadata-lock, and worktree-removal warnings (`:255`, `:264`, `:273`, `:289`, `:292`, `:314`, `:456`, `:460`, `:468`), `metadata_lock.py`'s unlock/close failures, and `github_cli.py`'s "gh is not on path" / "nonexistent cwd" / "gh exceeded Ns" records on paths that are handled rather than raised. Under D8 every one of those becomes invisible at default and `-v`. The rule this project enforces mechanically (`review-code.md`) requires each failure mode to be *observable* — log at WARNING+ — and this change removes observability from a whole package at the default setting.

The design is aware of the coupling but only compensates for one case: D9 exists specifically because "without this the #131 note would disappear at default verbosity." That makes `RefAdjustment`/`FetchedRange.adjustments` a workaround for the handler policy rather than an independent decision, and it says nothing about the worktree and metadata-path records D9 does not cover. Either scope the suppression to the records that genuinely duplicate an error about to be rendered (for example suppress only while `render_code_host_error` is on the stack), or state explicitly that the package's WARNING stream moves to `-vv` and that D9's adjustments cover only the ref path — and note the systemic gap against 941 F016 rather than adding a third ad-hoc handler convention.

### [CONCERN] D4's "no new failure path is added" premise does not hold for an unknown review template
category: error-handling
location: project-documents/user/slices/934-slice.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md#technical-decisions
D4 has classification load the template named in the action config "after placeholder resolution" and call `review_profile_source` on it, justified by "An unknown template is already a classification error, so no new failure path is added." I could not confirm that premise; the code says otherwise. `classification._review_template_model_fallback` loads the template and returns `template.model if template is not None else None` — it does not raise. `classify_pipeline` raises `ClassificationError` only when the *candidate* is `None`, i.e. when the action has no model at any cascade level. So a review action with `template: typo` plus a model supplied anywhere else (pipeline model, step model, CLI override) classifies cleanly today, and the new code then reaches `review_profile_source(explicit_present, template)` with no template. What it returns — and whether it disagrees with the runtime review action, which does fail on an unresolvable template — is undefined, and it is exactly the CLI-versus-pipeline divergence this slice exists to remove.

Either establish that the template lookup in the new path cannot miss (and restate what happens if it does), or handle the miss explicitly with a defined result. Worth noting the runtime half also differs by path today: the pipeline action surfaces it as an action failure, and `template_inputs` treats an unknown name as "one unchanged dict" (slice 930's task), so this is not one behavior to inherit but three.

### [CONCERN] D5 under-specifies the dry-run classification and omits the pool backend
category: error-handling
location: project-documents/user/slices/934-slice.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md:159
D5 promises `--dry-run` reports `UnknownModelAliasError` "the same way a run does (exit 1, same message, same close matches)." `classify_pipeline` raises `ClassificationError` for at least two other causes, and one of them is reachable purely because dry-run has no backend to give it:

- A `pool:` candidate with no pool backend raises `ClassificationError("... resolves to pool 'x' but no pool backend is configured")`. Verified: the current dry-run branch in `cli/commands/run.py` assembles params and calls `render_steps(...)` with no resolver and no backend, whereas both `_run_pipeline_sdk` and `_handle_explain` construct `DefaultPoolBackend()`. Wiring classification into dry-run without doing the same makes `sq run --dry-run` exit 1 on any pipeline containing a pool reference that a real run accepts — the preview refusing what the run performs.
- An action with no model at any cascade level raises a different `ClassificationError`.

Neither the design nor the success criteria say which failures count as "the same message," or that the other `ClassificationError` causes must be treated as preview failures too. The functional criterion is also stated as a prediction rather than a verified fact ("A real run fails before step 1"), while the corresponding success criterion for #188 pins the exact WARNING text — the same precision is warranted here.

### [CONCERN] The #188 predicate reads git in the process cwd, which is a second source of "the repository"
category: error-handling
location: project-documents/user/slices/934-slice.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md:131
D1 grants the predicate `os.getcwd()` "at the call site," reasoning that `sources.py` makes every `cf` call in the process cwd and "The executor's `effective_cwd` already defaults to it." The default is not the contract: `executor.py:473` is `effective_cwd = cwd or os.getcwd()` — `execute_pipeline` accepts an explicit `cwd`, and `evaluate_each_source` does not receive it. So the predicate would answer about one repository while the executor runs in another, silently, whenever a caller passes `cwd=`.

There is a sharper version of the same problem. The target comes from `read_integration_target(cf_client)`, i.e. cf's registered project identity; the branch tips would come from the process directory. Two roots for one answer, agreeing while the CLI is the only caller — which is precisely the hidden dependency the design's own "reads git each time and caches nothing" stance is meant to avoid. Threading the executor's `effective_cwd` into the source call (or reading it from the cf client) removes the second source; if the process cwd is genuinely the intended one, that is a decision worth recording as one, since `evaluate_each_source` is also invoked by `sq run --dry-run` and by item resume (`item_resume.py:151`, which passes its own `cwd`).

### [NOTE] The bundle grew past the plan entry's four items without a restated risk or effort
category: scope
location: project-documents/user/slices/934-slice.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md#technical-scope
900's guidance is "Slices in this initiative should be small and focused — prefer many small slices over few large ones" and "Each slice should be independently deliverable," and the plan entry itself bundled the four issues (so the bundling is not the finding). What the design adds beyond the entry is: `RefAdjustment` plus `FetchedRange.adjustments` as new provenance covering #131 (D9), and a package-wide logging policy applied to "every such command" (D8). Neither is mentioned in the plan entry's summary, which rated the work "Risk: Low · Effort: 3/5." The design should say why these ride along rather than shipping as their own maintenance slice, and whether the plan's figures still hold — particularly since D8/D9 introduce a coupling (one exists because the other hides a record) that the plan entry does not reflect.
