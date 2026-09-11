---
docType: review
layer: project
reviewType: slice
slice: review-scope-correctness
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/916-slice.review-scope-correctness.md
aiModel: z-ai/glm-5.3
status: complete
dateCreated: 20260911
dateUpdated: 20260911
reviewedSha: cacd0fe813c8cdc0372c52ab795cfbb10201207a
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 33
findings:
  - id: F001
    severity: concern
    category: integration-points
    summary: "Part B's empty-scope refusal is pinned to the CLI path; the pipeline review action — the path that trips gates — has no named detection point"
    location: "project-documents/user/slices/916-slice.review-scope-correctness.md:152"
  - id: F002
    severity: concern
    category: error-handling
    summary: "New `normalize_diff_spec` git invocation lacks enumerated low-level failure modes (hang, timeout, non-repo cwd)"
    location: "project-documents/user/slices/916-slice.review-scope-correctness.md:97-109"
  - id: F003
    severity: concern
    category: integration-points
    summary: "Part C deliberately breaks shipped `--diff`-without-slice invocations; the Risk Assessment omits it and no doc-update work is scoped"
    location: "project-documents/user/slices/916-slice.review-scope-correctness.md:113-129"
  - id: F004
    severity: note
    category: scope
    summary: "Five-part bundle at 4/5 effort sits at the edge of 900's \"prefer many small slices\" guideline"
    location: "project-documents/user/slices/916-slice.review-scope-correctness.md#technical-scope"
  - id: F005
    severity: pass
    category: architecture-alignment
    summary: "Part B's verdict-consumer enumeration prevents a cross-repo contract break and keeps the slice inside 900's scope"
    location: "project-documents/user/slices/916-slice.review-scope-correctness.md#part-b--empty-filtered-scope-62"
  - id: F006
    severity: pass
    category: boundary-analysis
    summary: "Hidden-dependency and containment implications are identified and discharged rather than left implicit"
    location: "project-documents/user/slices/916-slice.review-scope-correctness.md"
---

# Review: slice — slice 916

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3

## Findings

### [CONCERN] Part B's empty-scope refusal is pinned to the CLI path; the pipeline review action — the path that trips gates — has no named detection point

B1 places detection at `extract_diff_paths` "already runs at review.py:893" — the CLI subcommand layer. But per slices 146 and 901, the pipeline `review` action calls `run_review_with_profile` directly and resolves its diff through the template-input registry (`resolve_slice_diff_range`), not through the CLI site the design names. Part B's stated goal is gate integrity ("no artifact clears no gate, in either repo"), and the Risk Assessment asserts that pipelines relying on an all-excluded review "will begin failing" — yet the design never identifies where the pipeline path detects an empty post-exclusion scope. If the pipeline path does not run the same pre-flight check, the exact harm B exists to fix (an empty-scope PASS artifact clearing a gate) remains reachable via `sq run`, and the mitigation ("remove the `review:` key") rests on a failure the design does not guarantee will occur. I could not verify the pipeline path's current behavior against source (not present in this documents workspace). The design should either name the pipeline-side call site / move the check into shared code below both entry points, or explicitly scope B to the CLI and record the pipeline gap as follow-up rather than implying the whole surface is closed.

### [CONCERN] New `normalize_diff_spec` git invocation lacks enumerated low-level failure modes (hang, timeout, non-repo cwd)

A2 adds a new function to `review/git_utils.py` that rewrites a user-supplied `--diff` string and (per A4) shells out via `_resolve_rev(ref, cwd)` before any model call. The enumerated failure modes are semantic: unresolvable bare ref → non-zero exit (A4), and the two empty-range shapes (B2). The Technical criteria carry a blanket "every new failure path exits non-zero and logs at WARNING+, per the Failure-Mode Enumeration rule" — but that rule also requires the hang/timeout family answered explicitly, and neither A2 nor A4 addresses subprocess hang or timeout on the new resolution call, or a `cwd` outside any git work tree (Part D states the inherited `find_git_root(...) or resolved_cwd` fallback for D's sites, but A does not say what `normalize_diff_spec` does when there is no repo). Note also an asymmetry the design leaves implicit: A4's loud guard covers only the bare-ref shape, so an unresolvable ref embedded in an explicit `a..b`/`a...b` range still reaches the swallow at `rules.py:218-220` and surfaces only as B2's generic "no changed files" message — handled (non-zero, not silent), but worth stating. State the timeout/hang strategy for the new call, or state that it inherits the existing `git_utils` subprocess policy, per the project rule this slice itself cites.

### [CONCERN] Part C deliberately breaks shipped `--diff`-without-slice invocations; the Risk Assessment omits it and no doc-update work is scoped

C3 makes a `--diff`/`--files`-only run (no slice identifier) exit 1 with "no artifact could be written." That is a well-argued correction of #70 — the design is explicit that this is the point. But it changes a documented, working user surface: slice 118 ships `/sq:review-code` with the explicit guarantee "existing invocation still works: `/sq:review-code --diff main --files "src/**/*.py"`", and the README/PyPI examples (slices 106, 117) show `sq review code --diff main -v` with no slice number. After C, every one of those exits non-zero. The Risk Assessment covers B's passing→failing change, E's capability change, and A's shape surprise — but not C's, and the Excluded list scopes no work to update the `/sq` command docs or README examples that will now instruct users into a failing command. Add C's blast radius to the Risk Assessment and scope the consuming-surface updates (or record them as an explicit follow-up), so the interfaces slices 118/117/106 define do not silently contradict the CLI.

### [NOTE] Five-part bundle at 4/5 effort sits at the edge of 900's "prefer many small slices" guideline

The 900 architecture asks for "small and focused" slices and prefers many small over few large. 916 bundles five defects spanning the CLI review path and the SDK provider edge, at the series' top effort band (4/5, per the plan entry). The bundle is pre-authorized by the slice plan, justified by a shared surface and two defects observed on the same live PR, and mitigated by a load-bearing part sequence in which each part is independently committable — which satisfies "independently deliverable" at part granularity. Informational only; no change requested.

### [PASS] Part B's verdict-consumer enumeration prevents a cross-repo contract break and keeps the slice inside 900's scope

Refusing to persist rather than adding a `NOT_APPLICABLE`/`NO_SCOPE` verdict is backed by a concrete enumeration of five in-repo consumers (`CheckpointTrigger.ON_CONCERNS` allowlist, `LoopCondition.REVIEW_CONCERNS_OR_BETTER`, the verdict-rank dict subscript, `_LEG_VERDICT_TO_RESOLUTION`, the `degraded` computation) plus the cross-repo `workflow.review_threshold` seam, with the specific mishandling direction named for each (waved through / never converges / `KeyError`). This is exactly the boundary analysis 900's scope exclusion ("no new features or capabilities") demands: the rejected alternative would have been a cross-repo contract change smuggled in as a bug fix, and the chosen fix closes the reported harm with no coordination. B3's verification that omitting the `review:` key already expresses "no code review" (`phase.py:76`) is recorded so task breakdown does not go build an unneeded feature — good interface discipline against the consuming pipeline surface.

### [PASS] Hidden-dependency and containment implications are identified and discharged rather than left implicit

Two places where this slice touches a boundary are handled explicitly. Part D argues — rather than assumes — that moving the `read_file`/`list_files`/`grep` jail root from a configured subdirectory to the git root is consistency with the prompt's existing repo-root-relative path vocabulary, not a containment weakening, and routes all five call sites through one helper instead of a fourth copy (D1), honoring the project's duplication rule. E5 recognizes that E1 changes the SDK provider edge for *any* config declaring `allowed_tools`, requires a producer check before implementation, and pre-commits the narrowing fallback (review-client config construction) if a non-review producer depends on current behavior. Both are the kind of hidden-dependency pre-emption the review criteria ask for.
