---
docType: review
layer: project
reviewType: slice
slice: pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/934-slice.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md
aiModel: deepseek/deepseek-v4.1-flash
status: complete
dateCreated: 20261006
dateUpdated: 20261006
reviewedSha: ed711138f6047d7a995257c46dfb62e3e3b27524
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 44
turns: 17
promptTokens: 1716745
cachedTokens: 1543424
completionTokens: 84038
reasoningTokens: 78926
durationSeconds: 578.2
runId: run-20261007-p4-ced11784
squadronVersion: 0.20.1
findings:
  - id: F001
    severity: concern
    category: architecture-scope
    summary: "Four independent fixes bundled in one 4/5 slice against an architecture that asks for small, independently deliverable slices"
    location: "project-documents/user/slices/934-slice.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md:51-57"
  - id: F002
    severity: concern
    category: error-handling
    summary: "D4's new unknown-template error is raised from a helper the executor calls for log labelling, so the design's stated runtime coverage is inaccurate"
    location: "project-documents/user/slices/934-slice.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md:184-191"
  - id: F003
    severity: note
    category: integration
    summary: "\"Provides to Other Slices\" claims an interface commitment to slice 935 that 935's own scope does not support, while `interfaces:` is empty"
    location: "project-documents/user/slices/934-slice.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md:308"
  - id: F004
    severity: note
    category: verification
    summary: "`--dry-run --strict` is inert, so that success criterion cannot be observed"
    location: "project-documents/user/slices/934-slice.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md:211"
  - id: F005
    severity: pass
    category: error-handling
    summary: "Failure modes for the new I/O paths are enumerated with bounds and observable signals"
    location: "project-documents/user/slices/934-slice.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md:266-303"
---

# Review: slice — slice 934

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [CONCERN] Four independent fixes bundled in one 4/5 slice against an architecture that asks for small, independently deliverable slices

The parent architecture states that slices in this initiative "should be small and focused — prefer many small slices over few large ones", that "Each slice should be independently deliverable", and that the standard process is to be used "lighter-weight given the maintenance nature". This slice carries four distinct, root-caused bugs across four unrelated subsystems (`pipeline/git_ops`+`sources`+`item_resume`; `review/` profile resolution + `classification`; `cli/commands/run`; `codehost/refs`+`cli/commands/pr*`), touches roughly a dozen existing modules plus one new one, and lands at the highest effort tier in the plan (4/5, matching only 914 and 916). The design concedes the point in its own words: only #175 and #184 share a change, while "The other two pieces share nothing with them or each other", and the split decision is deferred ("If the PM prefers separate slices, the split falls along exactly these lines and the decisions carry over unchanged"). Bundling is defensible on the plan entry's authority, but the deferral means the architectural granularity question is left unanswered by the document that is supposed to answer it. Independent deliverability is also genuinely reduced: a regression in the #188 predicate or the #186 fallback now blocks progress on the unrelated #175/#184 fixes; the design's own ordering note (do #184/#175 first because they make later live tests safe from typos) is evidence that the groups are not independent.

### [CONCERN] D4's new unknown-template error is raised from a helper the executor calls for log labelling, so the design's stated runtime coverage is inaccurate

D4 introduces `_review_template(action_type, resolved_cfg)` and states that "One template lookup in classification … serves both the model fallback and `review_profile_source`", raising `UnknownReviewTemplateError`. `_review_template_model_fallback` is not only a classification helper: it is reached through `action_model_candidate` (`classification.py:281,298`), which is also reached through `action_model_label` (`classification.py:302-314`), which the executor calls from `_summarize_action_config` for every model-dispatching action, eagerly, inside `_execute_step_once` (`executor.py:101-117`, called in the action loop before `action_impl.execute`). Replace the "return `None` for an unknown name" behaviour with a raise and a step's verbose log label can raise before the review action is ever entered. D4 asserts the opposite for exactly this case — "A name that still holds an unresolved placeholder after merging params … is skipped before the run, as alias candidates already are. At run time the review action's existing `KeyError` path and the resolver backstop cover it" — but the placeholder that survives to runtime would be resolved to a literal `{template}` string, which the new lookup treats as an unknown name and raises on in the labelling path, not in `ReviewAction._review`'s catch list (`pipeline/actions/review.py`, whose `execute` catches `ModelResolutionError`, `ModelPoolNotImplemented`, `UnknownModelAliasError`, `KeyError`, `DiffRange*`, `EmptyScopeError`). Two things are consequently unspecified: the new error's base type (nothing in D4 or D10 says which handlers catch it — `UnknownModelAliasError` is a `ValueError` precisely so the CLI paths catch it, and `sq run --resume` on a PROMPT_ONLY run wraps `_run_pipeline` in `except KeyboardInterrupt` only), and whether the shared lookup should raise at all on the labelling path. The predicate/branch side of this slice has a D10 row for every git call; this new failure path has none.

### [NOTE] "Provides to Other Slices" claims an interface commitment to slice 935 that 935's own scope does not support, while `interfaces:` is empty

The design promises `review/profile_resolution.py` as "the single review-profile cascade. Slice 935 (rules injection) and any new review entry point resolve profiles through it." Slice 935 in the plan (`900-slices.maintenance-and-refactoring.md`, entry 33) is scoped to conventions/rules sourcing and relevance selection for dispatch and review — it does not add a review entry point and its text never mentions profile resolution. The commitment is forward-looking and unverifiable at this point, and the frontmatter records `interfaces: []` (line 7), which is inconsistent with naming a consumer even though sibling slices use that field for exactly this (`145-slice…: interfaces: [146, 147, 149]`). Either drop the 935 sentence or name 935 in `interfaces:`; as written, a future slice author reading the interface field sees no dependency at all.

### [NOTE] `--dry-run --strict` is inert, so that success criterion cannot be observed

D5 has `--dry-run` "use[] it with the params from `_assemble_params` and `_extract_model_override(model, param)`" and adds "the `--strict` handling the other two paths already have", and the Success Criteria then require that "`--dry-run --strict` applies the strict policy". But dry-run discards the returned classification after the error check ("On success it renders as today"), and `strict` only feeds `PoolClassificationPolicy`, which affects `needs_persistent_session`/`shape` — neither of which dry-run renders. The flag therefore has no observable effect on the preview, and the criterion as written cannot be demonstrated by output. Either the criterion should be phrased as "does not error and produces the same step list", or dry-run should surface the policy/shape it classified under.

### [PASS] Failure modes for the new I/O paths are enumerated with bounds and observable signals

D10 gives a row per new call for both the #188 predicate (local git) and the #186 head fallback (network), each with the hang/timeout outcome, the git-refuses or peer-disconnect outcome, the observable signal, and the resulting state — including the two distinctions that most often get flattened: `cat-file -e` exiting non-zero is "absent, a normal answer" rather than a failure, and a partial/refused fallback fetch is caught and recorded as that attempt's reason rather than aborting. It correctly orders fetch before classification because `refs._is_ancestor` answers "no" for an absent commit, and it names the publisher of each bound against the real constants (`GIT_COMMAND_TIMEOUT_SECONDS` for `run_git`, `GIT_FETCH_TIMEOUT_SECONDS`/`GIT_QUERY_TIMEOUT_SECONDS` in `codehost/refs.py`, all verified present). It also closes a pre-existing traceback hole on the same path (the primary `_fetch` timeout escaping `sq review pr`) rather than leaving it implicit. The parent architecture states no NFRs (latency, throughput) for any path this slice touches, so there is no NFR target to restate; the bounds above are what carries that role here.

## Response (20261007)

- **Bundling — no change.** The PM chose to bundle these four issues into one slice so it can run in its own worktree alongside 199.
- **D4 raise on the labelling path — fixed.** `_review_template` never raises, so the executor's labelling path behaves as today. A separate `_require_review_template`, called only from `classify_pipeline`, raises `UnknownReviewTemplateError(ValueError)`, which is collected into `ClassificationError`. Runtime unknowns still go through the review action's `KeyError` path, and a test covers that with verbose labelling on.
- **935 interface claim — fixed.** The sentence is dropped.
- **`--dry-run --strict` criterion — fixed.** Rephrased so it can be observed: the same classification errors as a strict run, and the same step list as `--dry-run`.
- Final finding: pass.

### Run Digest

- Response length: 8944 chars
- Response is newline-free: no
- Tool calls made: 44
- Tool calls failed: 2
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 329227
- Effort: backend default
- Turns: 17
- Tokens — prompt / cached / completion / reasoning: 1716745 / 1543424 / 84038 / 78926
- Duration: 578.2 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5
