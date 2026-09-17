---
docType: review
layer: project
reviewType: slice
slice: small-fixes-batch
project: squadron
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/slices/921-slice.small-fixes-batch.md
aiModel: z-ai/glm-5.3
status: complete
dateCreated: 20260917
dateUpdated: 20260917
reviewedSha: c7bdfdafeae5810b33b9cadb91314ecb7cc50b85
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 33
findings:
  - id: F001
    severity: fail
    category: correctness
    summary: "Fix 2's filter, as specified, does not reject the design's own motivating example"
    location: "project-documents/user/slices/921-slice.small-fixes-batch.md:74-78"
  - id: F002
    severity: fail
    category: integration-points
    summary: "Fix 2's \"known project names\" source does not exist; the summary prefix is the cwd basename, not a CF project name"
    location: "project-documents/user/slices/921-slice.small-fixes-batch.md:78-80"
  - id: F003
    severity: concern
    category: design-consistency
    summary: "Fix 1's guard condition and its stated rationale are not equivalent; the design must say which to key on"
    location: "project-documents/user/slices/921-slice.small-fixes-batch.md:47-55"
  - id: F004
    severity: concern
    category: scope
    summary: "Fix 1 leaves the identical silent-passthrough on the judge path unaddressed and unrecorded"
    location: "project-documents/user/slices/921-slice.small-fixes-batch.md:84-91"
  - id: F005
    severity: pass
    category: alignment
    summary: "Scope, verification discipline, and code citations are accurate and aligned with the parent architecture"
    location: "project-documents/user/slices/921-slice.small-fixes-batch.md"
---

# Review: slice — slice 921

**Verdict:** FAIL
**Model:** z-ai/glm-5.3

## Findings

### [FAIL] Fix 2's filter, as specified, does not reject the design's own motivating example

The concrete predicate â "filter out any path whose stem, with the `{project}-` prefix stripped, still starts with `{other_project}-` for some other known project name" â fails on the exact case the design cites one paragraph earlier ("for `project == "squadron"`, it also matches `squadron-pr-*.md`"). For stem `squadron-pr-p5a` and project `squadron`: the stripped remainder is `pr-p5a`, and `pr-p5a` does not start with `squadron-pr-` (the sibling project's prefix), so the match is not filtered. The over-match class the bare glob creates is precisely nested-prefix siblings (`squadron-pr` vs `squadron`), so the literal predicate is a no-op on the entire defect class. The first sentence ("whose remainder â¦ is itself a real sibling project name followed by `-`") fails the same example: remainder `pr-p5a` is not `squadron-pr` followed by `-`. The working form is to test the unstripped stem against `{other_project}-` prefixes. The design must also acknowledge a residual ambiguity any prefix filter leaves: `squadron-pr-p5a.md` may equally be the *current* project's `pr-p5a` pipeline summary, so a corrected filter silently makes a legitimate own-project key unrestorable â the design should state a disambiguation policy (warn/attribute rather than silently drop, or require `--key` in the colliding case) rather than leave that consequence implicit.

### [FAIL] Fix 2's "known project names" source does not exist; the summary prefix is the cwd basename, not a CF project name

The design asserts: "Known project names come from the same CF source `gather_cf_params`/project listing already uses elsewhere in this file â no new dependency." Verified against the code, no such source exists. `gather_cf_params` (src/squadron/pipeline/summary_render.py:66) returns `{project, slice, phase}` for the current checkout only, and `project` is set to `Path(cwd).resolve().name` â the directory basename â not a value read from Context Forge (`get_project()` is consulted only for `slice`/`phase`). `ContextForgeClient` (src/squadron/integrations/context_forge.py) exposes `is_available`, `list_slices`, `list_tasks`, `get_project`, `get_config` â no project-listing operation â and `summary_instructions.py` imports only `gather_cf_params`. The writer side keys on the same value (`emit.py`'s `_emit_file` names files from `ctx.params["_project"]`, seeded by the executor from `gather_cf_params`), so "sibling project names" in this scheme are sibling checkout directory basenames, for which squadron holds no registry. The design's Current-behavior account ("resolves the current project name via CF") repeats `_handle_restore`'s docstring rather than its implementation. If an unwrapped `cf` project-listing command is intended, that is a new integration surface needing its own specification and failure-mode enumeration (cf absent â which `gather_cf_params` already swallows to `{}` â empty/malformed output), i.e. a new dependency, contradicting the claim; and CF-registered names would still not reliably match basename-derived filenames. The design must specify where the sibling-name set comes from (the summaries directory itself is the one machine-global candidate, and its circularity should be weighed explicitly) before implementation. Secondary under-specification at the same location: "apply the same predicate inside `_summary_key`" leaves `_summary_key`'s return value for rejected paths unspecified. The parent plan's Risk: Low / Effort: 1/5 premise rests on the "no new dependency" claim and does not survive it.

### [CONCERN] Fix 1's guard condition and its stated rationale are not equivalent; the design must say which to key on

The design specifies the trigger as "no explicit `--profile` was given (i.e. resolution is about to fall back to the `"sdk"` default)". In the code, `_resolve_profile` (review.py:490) resolves flag â `template.profile` â config `default_review_profile` â `"sdk"`, so the two conditions diverge whenever a template sets a profile or config sets `default_review_profile`: a literal model id with a resolvable non-flag profile is rejected under the flag-keyed condition even though, by the design's own rationale ("the ambiguity only exists when profile is unresolved"), it should not be. The design should pick one condition explicitly â keying on `profile_flag is None` is the simpler, fail-closed choice, but the parenthetical justification must then be corrected. It should also acknowledge two collateral behavior changes it currently does not: `raw_model` also arrives from config (`default_model`, `default_model_{template}` via the `_resolve_model` cascade just above the call site), so a stale config value will now fail every review with the alias error â consistent with the fail-explicit convention, but wider than "unknown `--model` alias" suggests â and literal-passthrough users with a template/config profile set must now pass `--profile` explicitly where they previously did not.

### [CONCERN] Fix 1 leaves the identical silent-passthrough on the judge path unaddressed and unrecorded

`_resolve_judge_model` (review.py:1169-1176) has the same shape the design fixes: `resolve_model_alias(raw_model)` returning `(name, None)` flows into `_resolve_profile(profile_flag or alias_profile, template)` and the unresolved name is dispatched, so `sq review resolve <index> --model <typo>` reproduces #67 on a sibling path in the same file, driven by the same `--model` flag. The design pins the guard to `_run_review_command` (review.py:597-608) only, and neither the Fix section nor Non-goals mentions the judge path, despite the Overview's stated goal being "unknown model alias dispatches silently instead of failing fast." Either extend the fix (the guard is the same few lines; a shared helper would serve both sites) or record the judge path as an explicit non-goal with a rationale. The pipeline `--model` runtime passthrough (`ModelResolver.resolve` â passthrough) is reasonably left to the existing #60 non-goal, and the loader's `_validate_model_alias` (loader.py:229-248) already fail-closes unresolved pipeline/step-level aliases when validation runs.

### [PASS] Scope, verification discipline, and code citations are accurate and aligned with the parent architecture

The slice sits squarely in the architecture's defined scope ("Bug fixes: non-trivial bugs that don't belong to an active feature slice") and matches the parent plan's entry 19 exactly (two bugs, no dependencies). It honors the "small and focused / independently deliverable" guideline with well-reasoned non-goals (#67's workspace-trust preflight, #60). The Overview's disposition of #78 and #65-finding-1 â verified already fixed on `main` (`0aae0c8c`, `9c0d7a37`) by reading current code rather than trusting issue text, then closed rather than re-designed â is exactly the discipline this initiative's maintenance slices should show. I verified the design's citations against the code and they are accurate: `resolve_model_alias` at aliases.py:179-190 returns `(name, None)` for unknown names as described; the alias-resolution block at review.py:597-608 matches the described fallback; `_handle_restore` at summary_instructions.py:91-131 with the glob at line 111, `_summary_key` at 82-88, `_select_summary` at 134-154, the picker listing at 126, and key matching at 146 all behave as the Current-behavior accounts state. Frontmatter (`dependencies: []`, `interfaces: []`) is consistent with a localized bug-fix slice. The parent architecture states no NFRs, so none needed restating, and Fix 1 introduces no new I/O path.

### Run Digest

- Response length: 9020 chars
- Response is newline-free: no
- Tool calls made: 33
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 131584
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5

---

## Response (20260917)

All 5 findings verified against source before acting; both FAILs were confirmed as real logic bugs, not just imprecision.

- **F001** (Fix 2's filter is a no-op on its own example) — confirmed by direct computation: for stem `squadron-pr-p5a` and project `squadron`, `removeprefix("squadron-")` yields `pr-p5a`, which cannot start with `squadron-pr-` — stripping the first prefix already consumes part of the second project's name. Fixed: the predicate now tests the **unstripped stem** against `{other_project}-` for every sibling project name, not the stripped remainder.
- **F002** ("known project names" source doesn't exist) — confirmed: `gather_cf_params` (summary_render.py:73) sets `project_name = resolved_cwd.name`, a directory basename, never CF-sourced; `ContextForgeClient` has no project-listing method. The design now names the actual source: sibling checkout directories under the current checkout's parent (`resolved_cwd.parent.iterdir()`), consistent with how `gather_cf_params` derives the current project's own name. Documented as a heuristic (catches sibling-worktree collisions, the reported case; won't catch same-prefix projects checked out elsewhere) rather than a complete solution, and added the disambiguation policy the finding required: a filtered-out match is never silently dropped from consideration — it's listed as excluded, and restoring it requires an explicit `--key`.
- **F003** (guard condition vs. rationale mismatch) — confirmed: `_resolve_profile` falls back through `template.profile` → config `default_review_profile` → `"sdk"`, not just the flag. Fixed: the guard now checks the same three-step chain `_resolve_profile` performs before treating profile as "unresolved," matching the stated rationale instead of a narrower flag-only check. Added the collateral-effects note (a stale `default_model` config value with no profile anywhere will now fail closed, which is wider than the issue's `--model`-flag framing but consistent with the project's fail-explicit convention).
- **F004** (judge path unaddressed) — confirmed: `_resolve_judge_model` (review.py:1160-1176) has the identical unguarded shape. Fixed: the design now applies the same guard to both call sites via a shared helper rather than leaving the judge path as a silent gap.
- **F005** (pass) — no change needed.

Design doc updated: `project-documents/user/slices/921-slice.small-fixes-batch.md` (dateUpdated 20260917).
