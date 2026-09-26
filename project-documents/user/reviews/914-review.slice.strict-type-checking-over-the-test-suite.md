---
docType: review
layer: project
reviewType: slice
slice: strict-type-checking-over-the-test-suite
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/914-slice.strict-type-checking-over-the-test-suite.md
aiModel: z-ai/glm-5.3-flash
status: complete
dateCreated: 20260926
dateUpdated: 20260926
reviewedSha: bb65ac95984783534403afc4776df1388d2876dd
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 35
findings:
  - id: F001
    severity: pass
    category: alignment
    summary: "Scope, rule posture, and goals align with the parent architecture and the guide"
    location: "project-documents/user/slices/914-slice.strict-type-checking-over-the-test-suite.md#overview"
  - id: F002
    severity: pass
    category: design-quality
    summary: "All three plan questions are answered by measurement, two against the plan's assumptions"
    location: "project-documents/user/slices/914-slice.strict-type-checking-over-the-test-suite.md#measured-baseline-measured-20260817"
  - id: F003
    severity: pass
    category: alignment
    summary: "D3's production-touch correction is honest, judged, and mirrored in the plan"
    location: "project-documents/user/slices/914-slice.strict-type-checking-over-the-test-suite.md#d3--reportprivateusage-is-fixed-by-renaming-the-symbol-public"
  - id: F004
    severity: pass
    category: integration-points
    summary: "The consumer/integration surface is correctly identified and verified"
    location: "project-documents/user/slices/914-slice.strict-type-checking-over-the-test-suite.md#migration-plan"
  - id: F005
    severity: concern
    category: dependencies
    summary: "The design omits the parent plan's 923 sequencing dependency"
    location: "project-documents/user/slices/914-slice.strict-type-checking-over-the-test-suite.md:6"
  - id: F006
    severity: concern
    category: under-specification
    summary: "The walkthrough makes pre-existing `# type: ignore` comments a closeout gate, but the design never counts or dispositions them"
    location: "project-documents/user/slices/914-slice.strict-type-checking-over-the-test-suite.md:415-416"
  - id: F007
    severity: concern
    category: design-mechanism
    summary: "D2's per-commit-green mechanism rests on unverified pyright `exclude` semantics"
    location: "project-documents/user/slices/914-slice.strict-type-checking-over-the-test-suite.md:129-173"
  - id: F008
    severity: concern
    category: design-mechanism
    summary: "Directory-level `exclude` entries shadow Part B's file-level entries, so Part B's own gate cannot verify its files"
    location: "project-documents/user/slices/914-slice.strict-type-checking-over-the-test-suite.md:129-173"
  - id: F009
    severity: note
    category: staleness
    summary: "The 3021-passed / 2-skipped pytest floor is already stale for the tree the slice will run on"
    location: "project-documents/user/slices/914-slice.strict-type-checking-over-the-test-suite.md:301-303"
  - id: F010
    severity: note
    category: scope
    summary: "Slice size sits at the edge of the initiative's \"small and focused\" guideline"
    location: "project-documents/user/slices/914-slice.strict-type-checking-over-the-test-suite.md#effort"
---

# Review: slice — slice 914

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3-flash

## Findings

### [PASS] Scope, rule posture, and goals align with the parent architecture and the guide

The slice delivers exactly the guide's mandated configuration — `include = ["src", "tests"]`, `typeCheckingMode = "strict"`, zero errors as a merge blocker (`.claude/rules/python.md:65-76`) — and deletes the deferral comment currently present in `pyproject.toml`'s `[tool.pyright]` block. Tooling conformance is explicitly in 900-arch's scope ("Tooling and CI"; "Tech debt"). The out-of-scope list (no behavior change, no `typeCheckingMode` change, no rule relaxation) matches the guide's intent, and D1's no-relaxation decision is enforced by success criteria 2–3.

### [PASS] All three plan questions are answered by measurement, two against the plan's assumptions

D1 overturns the MagicMock premise with the 2-of-362 measurement; D2's per-directory choice is driven by the concentration table (top-10 files = 45%); D5 derives exactly two helpers from the error data rather than taste. Spot-checks confirm the evidence: `tests/cli/commands/test_dispatch_run.py:17` declares `def _invoke(*args: str) -> object:` exactly as quoted; the typed-`Result` idiom already exists at `tests/cli/test_pr_create_failures.py:63`; the `ModelAlias` optional keys (`private`, `cost_tier`, `notes`, `pricing`, `tool_use`) match `src/squadron/models/aliases.py`; and the parts table sums to exactly 905. This is evidence-first design of the kind the project's own reviews demand.

### [PASS] D3's production-touch correction is honest, judged, and mirrored in the plan

The design identifies its own violation of the plan's "test-only" basis, explicitly rejects the circular "de-facto public" justification, and substitutes a judged criterion with named keep-private candidates. Spot-check supports the candidate list: `_REGISTRY` is a module-level mutable registry (`src/squadron/events/__init__.py:34`) whose promotion to public would be a genuine API cost, and `_write_atomic` / `_run_pipeline_sdk` exist as private internals as claimed. Blast radius is quantified (261 `src` lines), the exception path is reported-not-predicted, and the plan entry was updated to match (`900-slices.maintenance-and-refactoring.md:192`, "Risk: Low-Medium (signature-only production edits per D3)").

### [PASS] The consumer/integration surface is correctly identified and verified

"the only consumers of the pyright config are CI and the local gate; both invoke `uv run pyright` with no path arguments" — verified: `.github/workflows/ci.yml:36` runs `uv run pyright` path-less, and no git hook references pyright. "No CI workflow edit is required" is correct, and the design still requires confirming it in Part A rather than assuming it. No new I/O paths or message types are introduced, so no failure-mode enumeration is owed; the two behavior-capable edits (D3 renames, D4 deletions) are enumerated with a per-part gate as their handling strategy.

### [CONCERN] The design omits the parent plan's 923 sequencing dependency

Frontmatter declares `dependencies: [913]`, but the parent plan entry for this same slice declares `[913 — sequencing only; 923 — sequencing only, so the conftest fixtures it adds and moves are typed once]` (`900-slices.maintenance-and-refactoring.md:192`), and entry 22 states 923 is "Sequenced **before 914**: Part A adds and moves conftest fixtures, and 914 then types them once instead of typing fixtures this slice would rewrite" (line 412). The design document — read in full — never mentions 923. Its Part A adds shared typed helpers and its parts type fixtures across `tests/cli`, `tests/pipeline`, and `tests/review`; 923's Part A adds an autouse root fixture in `tests/conftest.py` and moves fixtures out of `tests/review/conftest.py` — the same files this slice annotates. Running 914 first performs exactly the type-once-type-twice waste the plan entry warns against, and Part A's re-measurement step covers only the 905/104 numbers, not the fixture overlap. State the sequencing explicitly (after 923, or justify the inversion on evidence) and align the frontmatter.

### [CONCERN] The walkthrough makes pre-existing `# type: ignore` comments a closeout gate, but the design never counts or dispositions them

Verification step 5 declares "A `# type: ignore` anywhere in `tests/` is a finding — this project uses pyright, and a mypy-style blanket ignore is not the agreed suppression form." The tree currently carries well over a hundred such comments across roughly twenty test files: ~50 `# type: ignore[attr-defined]` sites in `tests/cli/test_install_commands.py` alone, plus `tests/cli/conftest.py:76,117,142,250`, `tests/cli/test_history.py:14`, `tests/pipeline/test_compact_integration.py:136-137`, `tests/events/test_registry.py:104-138`, and others. Pyright honors these comments, so the 905-error baseline excludes whatever they suppress, and no D-decision, baseline table, effort figure, or completion-summary slot accounts for converting, justifying, or deleting them. Several are the same class D5 fixes — the `_invoke` helpers annotated `# type: ignore[no-untyped-def]` in `tests/cli/test_history.py:14` et al. are `CliRunner` wrappers that Helper 1 would retype, making the ignore removable. Either scope the conversion as an explicit decision and work item (or declare the existing inventory in scope for criterion 8's audit), or the final gate trips on a population the design measured around.

### [CONCERN] D2's per-commit-green mechanism rests on unverified pyright `exclude` semantics

The mechanism assumes excluding a directory removes its errors from the report. Pyright does not treat `exclude` that way: excluded paths are skipped from the initial scan but are still checked when referenced (imported) by an included file, and their diagnostics are then reported. The test tree has a real cross-test import graph — `tests/cli/conftest.py` is imported by five test modules, `tests/codehost/fake_runner.py` by four, and `tests/cli/pr_create_support.py` imports `tests.codehost.fake_runner` — so once Part A widens the include and seeds `exclude` with erroring directories, any included file that imports a still-erroring excluded file pulls that file's errors back in, breaking the "pyright passes at *every* commit" property D2 exists to provide. Part A already commits to re-measuring before seeding `exclude`; that step must also assert the seeded exclude actually yields 0 errors on the first commit, and the design should state the constraint (newly included files must not import still-excluded files) so per-part ordering respects the import graph.

### [CONCERN] Directory-level `exclude` entries shadow Part B's file-level entries, so Part B's own gate cannot verify its files

D2 seeds `exclude` with "every test directory that still has errors," then gives the ten heaviest files their own part via file-path entries. The ten files live inside erroring directories (`tests/cli`, `tests/pipeline`, `tests/server`, `tests/providers/openai`, …), and pyright's exclude is additive with no negation — a directory entry necessarily covers those files regardless of any file-path entry. So when Part B deletes its file-path lines, the directory entries seeded in Part A still exclude those files: pyright never actually checks them until the enclosing directory's entry falls in Parts C/D/E. The "pyright passes at every commit" property survives (the build stays green throughout), but Part B's gate verifies nothing about Part B's files, and "Part B clears 45% of all errors in the first working commit" is unobservable at that commit. Either seed `exclude` at file granularity (104 entries — uglier but honest), or restructure so each part is directory-complete, and say which; as written, an implementer following D2 literally would mark Part B done with pyright never having seen its output.

### [NOTE] The 3021-passed / 2-skipped pytest floor is already stale for the tree the slice will run on

D7 hardcodes "the 3021-passed / 2-skipped baseline established at `03cdd73`" (repeated as criterion 6, line 344). Since that measurement, slices 920–926 have landed and the suite is in the 4400s with a different skip count (DEVLOG 20260926: "4461 passed, pyright clean"), and 923 — sequenced before this slice — will move it again. The `≥3021 passed` floor still functions as a no-regression check, but "2 skipped" as literally written cannot match the tree, and the design's Baseline-drift risk mandates re-measurement only for the 905/104 figures. Restate the floor as "no drop from the Part A re-measured baseline" rather than a fixed number.

### [NOTE] Slice size sits at the edge of the initiative's "small and focused" guideline

900-arch's guidelines prefer "many small slices over few large ones." At 4/5 with five parts, 104 files, ~922 lines of blast radius including production renames, this is the largest slice this initiative has carried (913 was 2/5). It remains acceptable — it is one coherent unit (make the widened gate green) and D2's per-part structure keeps each commit independently green — but the size is what makes the two D2 mechanism gaps above matter; worth flagging rather than restructuring.

## Response (20260926)

Four of six non-pass findings accepted; F007 rejected on evidence. The slice design has been revised.

- **F005: accepted.** Frontmatter now `dependencies: [913, 923]`; the Overview states the sequencing and why. 923 has no slice design yet, so 914 waits on it.
- **F006: accepted, and larger than stated.** Measured at `bb65ac9`: 257 `# type: ignore` comments across 67 test files, hiding 442 errors (1208 → 1650 with `enableTypeIgnoreComments = false`). New D8 puts every one in scope — fixed or converted to a justified `# pyright: ignore[rule]` — with a matching Scope line and a criterion-8 grep. `enableTypeIgnoreComments` stays default because disabling it surfaces 147 out-of-scope `src` errors.
- **F007: rejected.** Probed directly: an excluded module with a planted error, imported by an included module, reports 0 errors; the same module un-excluded reports 1. Pyright does not report diagnostics for excluded files pulled in by import, so the cross-test import graph cannot break per-commit green. The verification is recorded in D2.
- **F008: accepted.** D2 now seeds `exclude` one entry per erroring file, with no directory entries, and states why: globs have no negation, so a surviving directory entry would make a part's gate vacuous. The first commit must report 0 errors with the seeded list.
- **F009: accepted.** D7, criterion 6, and Risks now use Part A's recorded passed/skipped counts as the floor instead of 3021/2. The walkthrough's stale `filesAnalyzed` figure (~444) is also replaced with the current 575 vs 244 `src`-only.
- **F010: noted.** No restructure. The 1208/1650 re-measurement makes the slice larger than the 4/5 effort assumed; effort rating left for the PM.

### Run Digest

- Response length: 11112 chars
- Response is newline-free: no
- Tool calls made: 35
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 90116
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
