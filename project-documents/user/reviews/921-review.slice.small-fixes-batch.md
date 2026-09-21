---
docType: review
layer: project
reviewType: slice
slice: small-fixes-batch
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/921-slice.small-fixes-batch.md
aiModel: z-ai/glm-5.3
status: complete
dateCreated: 20260917
dateUpdated: 20260917
reviewedSha: 6c1ed6eae5eee80b9b715724f5708a43b27c72d6
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 37
findings:
  - id: F001
    severity: concern
    category: under-specification
    summary: "Fix 2's excluded-summary `--key` escape hatch is under-specified and in tension with the `_summary_key` predicate requirement"
    location: "project-documents/user/slices/921-slice.small-fixes-batch.md#fix-2-103-restore-matches-sibling-projects-by-prefix"
  - id: F002
    severity: concern
    category: error-handling
    summary: "New parent-directory enumeration in Fix 2 has no enumerated failure modes or handling strategy"
    location: "project-documents/user/slices/921-slice.small-fixes-batch.md#fix-2-103-restore-matches-sibling-projects-by-prefix"
  - id: F003
    severity: note
    category: behavior-change
    summary: "Fix 1's guard also rejects valid literal model IDs given with no profile signal — not recorded as a collateral effect"
    location: "project-documents/user/slices/921-slice.small-fixes-batch.md#fix-1-67-unknown-model-alias-dispatches-silently"
  - id: F004
    severity: pass
    category: scope
    summary: "Scope and bundle align with the maintenance architecture and slice plan"
    location: "project-documents/user/slices/921-slice.small-fixes-batch.md"
  - id: F005
    severity: pass
    category: factual-accuracy
    summary: "All load-bearing code claims and both review corrections verify against current source"
    location: "project-documents/user/slices/921-slice.small-fixes-batch.md"
  - id: F006
    severity: pass
    category: integration
    summary: "Writer/reader project-identity seam is consistent; no new cross-layer dependencies"
    location: "project-documents/user/slices/921-slice.small-fixes-batch.md#fix-2-103-restore-matches-sibling-projects-by-prefix"
---

# Review: slice — slice 921

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3

## Findings

### [CONCERN] Fix 2's excluded-summary `--key` escape hatch is under-specified and in tension with the `_summary_key` predicate requirement

The "Fix." paragraph requires filtering `matches` (computed at `summary_instructions.py:110-114`) and applying "the identical predicate inside `_summary_key` so the picker listing (line 126) and key-matching (line 146) can't disagree with default-selection." The "Disambiguation policy" paragraph simultaneously requires that an excluded file still be restorable: "require the caller to pass `--key <the literal stem-derived key>` to restore it explicitly rather than ever selecting it as the silent default." These do not compose as written. If the excluded file is removed from `matches`, `_select_summary` (`summary_instructions.py:134-154`, key match at line 146) can never select it under any `--key`. If it is retained, "the identical predicate inside `_summary_key`" leaves unstated what key an excluded stem yields — today `_summary_key` (lines 82-88) returns the stem minus `{project}-`, i.e. `pr-p5a` for `squadron-pr-p5a` with project `squadron`, which is precisely the ambiguous value. "The literal stem-derived key" is ambiguous between the stripped remainder (`pr-p5a`) and the full stem (`squadron-pr-p5a`). The task breakdown cannot determine what the user must type to restore the excluded file, or whether it is reachable at all. Before task breakdown, pin down: (1) whether excluded files remain in the key-matching set, and (2) the exact key value `_summary_key` returns for an excluded stem.

### [CONCERN] New parent-directory enumeration in Fix 2 has no enumerated failure modes or handling strategy

The sibling-projects derivation (`Path(cwd).resolve().parent.iterdir()`) is a new filesystem I/O path introduced by this slice. The design enumerates the heuristic's *logical* limitation (it misses same-prefix projects checked out elsewhere, and correctly requires this in a code comment) but not the *operational* failure modes of the enumeration itself: an unreadable or unlistable parent (permissions, parent removed between resolution and listing, cwd at a filesystem root) raises `OSError` from `iterdir()`, which `_handle_restore` does not catch. Today's command I/O (`glob`, `stat`, `read_text`) is likewise unguarded, so the new call is consistent with local precedent — but consistency of an implicit strategy is exactly what the review criteria exclude, and this project's own precedent is explicit: 916's slice review (F002) added hang/timeout/no-repo enumeration for its new git call. State the handling in the task breakdown — e.g., unlistable parent → WARNING and treat as no siblings (degrades to today's behavior), or fail explicitly per the fail-explicit convention.

### [NOTE] Fix 1's guard also rejects valid literal model IDs given with no profile signal — not recorded as a collateral effect

The guard fires whenever `resolve_model_alias` returns `(name, None)` and all three profile sources are absent. Verified against source: no shipped template declares `profile:` (grep of `src/squadron/data/templates` finds only `model:` keys), so an invocation like `sq review code --model <valid-claude-model-id>` — which today dispatches via the `"sdk"` default profile (`review.py:490-506`) — will after this fix fail with the unknown-alias error; the remedy is to also pass `--profile`. The design states the rule explicitly ("When any of the three supplies a profile, the name passes through as a literal model ID exactly as today") and enumerates the config-cascade collateral under "Collateral effects to record," but the flag-literal population is absent from that list, and the "not just the `--model` flag case the issue title names" phrasing frames the flag case as the typo case only. Since this is a currently-working invocation that will start failing, add it to the collateral effects the task's acceptance criteria must record.

### [PASS] Scope and bundle align with the maintenance architecture and slice plan

Both fixes are bug fixes within 900-arch's declared scope, the bundle matches slice-plan entry 19 exactly, and the reduction from four issues to two is corroborated on this branch: `install.py:59-90` now reads a prior receipt and unlinks only previously-written files no longer in the bundle, confirming #65 finding 1 is already fixed as the design claims. Extending the guard to `_resolve_judge_model` is the same defect on a sibling call site of the same mechanism (`resolve_model_alias` has exactly two CLI call sites, `review.py:605` and `review.py:1174`), not scope creep. The pipeline-path exclusion is verified sound: `_validate_model_alias` (`loader.py:229-248`) already fail-closes unresolved pipeline/step-level aliases at validation time. The architecture states no NFRs, so there is nothing to restate, and the frontmatter `parent` correctly targets the slice plan.

### [PASS] All load-bearing code claims and both review corrections verify against current source

Verified: `resolve_model_alias` pass-through semantics (`aliases.py:179-191`); the alias/profile flow at `review.py:597-608` and `_resolve_profile`'s exact three-level chain at `review.py:490-506` — the proposed guard correctly mirrors that chain, and the doc's own correction (the flag-only draft would wrongly reject a literal ID with a template/config-supplied profile) is accurate; the identical shape at `_resolve_judge_model` (`review.py:1160-1176`); `gather_cf_params` deriving `project` from `resolved_cwd.name` with CF consulted only for `slice`/`phase` (`summary_render.py:72-90`); the prefix-glob flaw across `_handle_restore` (91-131), `_summary_key` (82-88), and `_select_summary` (134-154, `matches[0]` at 142); and `ContextForgeClient` exposing no project-listing operation (`is_available`/`list_slices`/`list_tasks`/`get_project`/`get_config` only), so the design's second correction is accurate and the unstripped-stem predicate is indeed required for the motivating case.

### [PASS] Writer/reader project-identity seam is consistent; no new cross-layer dependencies

The sibling heuristic reuses the same cwd-basename project identity both sides of the summary seam already use: the writer (`pipeline/emit.py` `_emit_file`, keyed on the executor-injected `_project` from `gather_cf_params`, `executor.py:609-613`) and the reader (`_handle_restore` via `gather_cf_params`) both key on `resolved_cwd.name`, so deriving siblings from the checkout layout extends the existing convention rather than inventing a second identity source — the design's consistency claim holds. Fix 1's shared `_reject_unknown_alias` helper stays inside the review CLI module, and all dependency directions (CLI → `models/aliases`, CLI → config) are unchanged.

### Run Digest

- Response length: 8772 chars
- Response is newline-free: no
- Tool calls made: 37
- Tool calls failed: 1
- Stop reason: stop
- Reasoning characters: 78119
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6

---

## Response (20260917)

All 3 findings verified against source before acting.

- **F001** (excluded-summary `--key` escape hatch under-specified/self-contradicting) — confirmed: requiring both "identical predicate inside `_summary_key`" and "excluded files remain restorable via `--key`" cannot compose, since removing a match from the matchable set makes it unselectable under any key. Resolved: the sibling-prefix filter now applies only to the **default** (no-`--key`) selection, partitioning matches into `clean`/`excluded`; `_summary_key` is unchanged for every stem, so an excluded file's key is exactly what it always was and remains reachable via explicit `--key`. The stderr listing now marks excluded entries with the reason and the key to use.
- **F002** (no enumerated failure modes for the new `iterdir()` call) — confirmed: no existing try/except in `_handle_restore` covers filesystem errors, and this project's own 916 precedent requires enumerating a new I/O path's failure modes explicitly. Added: unreadable/removed parent or root-cwd cases all surface as `OSError`; handling is catch-and-WARNING, degrading to an empty sibling set (today's unfiltered behavior) rather than crashing the command.
- **F003** (guard also rejects valid literal model IDs with no profile signal) — confirmed by grep: no shipped template declares `profile:`, so `template.profile` is always `None` in practice and the guard's real trigger condition is wider than the design's framing suggested. Added as an explicit second collateral effect (distinct from the config-cascade one already recorded), since this is a currently-working, non-typo invocation shape that starts failing.

Design doc updated: `project-documents/user/slices/921-slice.small-fixes-batch.md` (dateUpdated 20260917).
