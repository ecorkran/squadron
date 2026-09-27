---
docType: review
layer: project
reviewType: tasks
slice: test-suite-machine-state-isolation
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/923-tasks.test-suite-machine-state-isolation.md
aiModel: z-ai/glm-5.3-flash
status: complete
dateCreated: 20260926
dateUpdated: 20260926
reviewedSha: 41ffc49036a7689def2e3f498839a07c47a5289d
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 27
findings:
  - id: F001
    severity: pass
    category: traceability
    summary: "All success criteria trace to tasks; walkthrough steps are owned"
    location: "project-documents/user/tasks/923-tasks.test-suite-machine-state-isolation.md:69-455"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing, commit distribution, and CI gating are sound"
    location: "project-documents/user/tasks/923-tasks.test-suite-machine-state-isolation.md:392-429"
  - id: F003
    severity: concern
    category: test-coverage
    summary: "Task D.7's consolidation list misses the duplicated fixtures in `tests/cli/conftest.py`"
    location: "tests/cli/conftest.py:24-56"
  - id: F004
    severity: concern
    category: sequencing
    summary: "Task B.3's \"drop the patch\" branch cannot hold its green checkpoint before Part C exists"
    location: "project-documents/user/tasks/923-tasks.test-suite-machine-state-isolation.md:178-193"
  - id: F005
    severity: concern
    category: ci-gating
    summary: "Task E.3's verification step cannot produce evidence under the CI file's current triggers"
    location: ".github/workflows/ci.yml:3-9"
  - id: F006
    severity: note
    category: test-coverage
    summary: "The design's walkthrough step 3 import-cleanliness check has no owning checklist item"
    location: "project-documents/user/tasks/923-tasks.test-suite-machine-state-isolation.md:195-210"
  - id: F007
    severity: note
    category: process
    summary: "Four tasks lack an explicit commit bullet"
    location: "project-documents/user/tasks/923-tasks.test-suite-machine-state-isolation.md:283-295"
  - id: F008
    severity: note
    category: granularity
    summary: "Task C.2 is very granular and could merge into C.3"
    location: "project-documents/user/tasks/923-tasks.test-suite-machine-state-isolation.md:233-238"
---

# Review: tasks — slice 923

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3-flash

## Findings

### [PASS] All success criteria trace to tasks; walkthrough steps are owned

FR1→E.2, FR2→B.1/B.2/B.4, FR3→C.1–C.4, FR4→B.2/C.5/F.1, FR5→E.1, FR6→A.2/A.3, FR7→E.3, TR1→C.1, TR2→C.2/D.5, TR3→A.1/D.4/F.1, IR1→D.7 (fixture names and return types preserved). Walkthrough steps 1–8 all have owning tasks, and no task exists that lacks a design anchor (no scope creep). The D1 site list in Task B.1 matches the code exactly — I confirmed all 19 module-level `Path.home()` sites at the cited lines (e.g. `src/squadron/pipeline/state.py:162`, `src/squadron/review/templates/__init__.py:189`), and the "do not touch" sites (`worktree.py:102`, `reviews_dir.py:73`, `models_toml_path()`) are indeed already call-time returns. Task B.2's line reference (`src/squadron/cli/app.py:41`) and the existing `@app.callback` it targets are both real, and all four `host_cf` candidate files in D.5 exist (`tests/documents/test_schema_drift.py`, `tests/documents/test_pr_review_frontmatter.py`, `tests/tools/test_cf_contract_live.py`, `tests/review/test_cli_review.py`).

### [PASS] Sequencing, commit distribution, and CI gating are sound

Parts A→F respect dependencies with no cycles: the negative control (A.3) precedes any fix; B.1→B.2→B.3→B.4 build on each other; D.7 requires B.1+C.3 and is ordered after both; E.1 requires all of D. Commits are distributed (A.3, B.3, B.4, C.4, D.4, D.7, E.3), not batched at the end, and B.3's explicit "land as one buildable checkpoint" note correctly ties `src/` renames to their test updates. The new `hermetic` CI job is explicitly wired and gated in E.3 rather than left implicit. This slice states no performance NFR, so no `tests/load/` task is required (that directory already exists with two tests).

### [CONCERN] Task D.7's consolidation list misses the duplicated fixtures in `tests/cli/conftest.py`

The design's D7 and Task D.7 delete `_isolated_user_config`, `_isolated_model_registry`, and `_isolated_user_templates` from `tests/review/conftest.py` — but `tests/cli/conftest.py` carries its own autouse copies of two of them: `_isolated_model_registry` (`tests/cli/conftest.py:24`, patches `squadron.models.aliases.models_toml_path`) and `_isolated_user_templates` (`tests/cli/conftest.py:41`, patches `squadron.review.templates.USER_TEMPLATES_DIR`). Two consequences: (1) after B.1 renames `USER_TEMPLATES_DIR`, the cli fixture's patch target vanishes and every autouse-fixture test under `tests/cli/` errors — Task D.7's rationale ("the per-test home from Task C.3 now covers all three") applies equally to these copies but they are absent from its deletion list; (2) if Task B.3 happens to sweep them instead, they are updated to point at a rename that D.7 should have deleted. Either way the consolidation is partial and one of B.3/D.7 must own `tests/cli/conftest.py` explicitly. The same task should also state whether `isolate_reviews_dir` in that file stays (it patches the repo-relative `REVIEWS_DIR`, which the per-test home does *not* cover, so it should stay — but the task is silent).

### [CONCERN] Task B.3's "drop the patch" branch cannot hold its green checkpoint before Part C exists

B.3 instructs: for each of the ~44 patch references, "if the per-test home (added in Part A/C below) will already cover it, drop the patch entirely; otherwise, switch the patch target to the new function name" — and then requires `pytest` green "same or better than Task A.1's baseline" before moving on. At B.3's checkpoint the per-test home does not exist yet, so a dropped patch (e.g. `tests/skills/test_manifest.py:84` redirecting `USER_MANIFEST` to `tmp_path / "no-such.toml"`) sends the test at the developer's real `~/.config/squadron/` — passing by luck on a clean machine, failing on one with a real `skills.toml`, which is exactly the machine-dependence this slice exists to remove. Additionally, no task after C.3 owns the "drop now-redundant patches" step: Part D fixes *failures*, and D.7 only consolidates conftest fixtures, so per-test monkeypatches would linger. Resolve by splitting B.3: rename-target updates in Part B (green-safe), and an explicit patch-drop pass after C.3 in Part C or D.

### [CONCERN] Task E.3's verification step cannot produce evidence under the CI file's current triggers

E.3's checklist ends: "Push the slice branch and confirm the `hermetic` job goes green." The workflow triggers only on `push: branches: [main]`, tags, and `pull_request: branches: [main]` — a push of a slice branch fires nothing, and if the project uses an integration branch (per the git rules the slice branch merges into the configured target, which may not be `main`), even the merge won't trigger CI. FR7 ("green on the slice branch push") inherits the same impossibility. The task must specify the actual evidence path: open a PR against `main` (which runs both jobs), or reword FR7/E.3 to "green on the PR run" / "green after merge to the trigger branch." As written, a junior AI cannot complete the checklist item honestly.

### [NOTE] The design's walkthrough step 3 import-cleanliness check has no owning checklist item

Walkthrough step 3 includes `python -c "import squadron.cli.app, os; print('OPENROUTER_API_KEY' in os.environ)"` (import must not load `.env`), but no task's checklist runs it: B.4's AST guard only flags literal module-level `Path.home()`/`load_dotenv` calls, so a top-level `_load_env_file()` invocation would pass the guard while still loading `.env` at import; B.2 only verifies the positive runtime behavior and F.1 covers walkthrough step 4. Adding one checklist line to B.2 or B.4 closes it.

### [NOTE] Four tasks lack an explicit commit bullet

Tasks C.5, D.5, D.6, and E.1 have no "Commit" line. The project convention ("commit at least once per task") covers this in practice, and C.5's file would ride with D.1–D.4's checkpoint, but each task should either carry its own commit bullet or state which checkpoint it joins, so the checkpoint boundaries are unambiguous.

### [NOTE] Task C.2 is very granular and could merge into C.3

Registering one marker in `pyproject.toml` (1/5 effort) is consumed only by C.3's fixture and D.5's marking pass; folding it into C.3 would lose nothing and remove a task boundary. It is independently completable as written, so this is optional.

## Response (20260926)

Three concerns accepted and fixed, two notes accepted and fixed, one note skipped.

- **F003: accepted.** Confirmed `tests/cli/conftest.py:24` and `:41` duplicate `_isolated_model_registry` and `_isolated_user_templates` from `tests/review/conftest.py`. Task D.7 now deletes both from `tests/cli/conftest.py` too, and states explicitly that `isolate_reviews_dir` stays (it patches the repo-relative `REVIEWS_DIR`, not a home-derived path).
- **F004: accepted.** Confirmed the sequencing hole: B.3's "drop the patch" branch ran before the per-test home exists. Split it — Task B.3 now only retargets patches to the renamed functions (no drops), and Task D.7 gained the drop pass after Task C.3's per-test home is in place.
- **F005: accepted.** Confirmed via `cf config get git.integration_branch` — this project's integration branch is `squadron-9143`, not `main`, and `ci.yml` only triggers on `push`/`pull_request` to `main`. Task E.3 now specifies opening a PR against `main` as the actual evidence path, and the slice design's FR7 wording is corrected to match.
- **F006: accepted.** Task B.4 gained the walkthrough step 3 check directly (`import squadron.cli.app` then assert `OPENROUTER_API_KEY` absent from `os.environ`), since the AST guard can't detect a top-level call to the new `_load_env_file()` function.
- **F007: accepted.** Added explicit commit bullets to C.5, D.5, D.6, and E.1 stating which checkpoint each joins.
- **F008: skipped.** Granularity preference, not a correctness or coverage gap; C.2 stays a separate task.

### Run Digest

- Response length: 7742 chars
- Response is newline-free: no
- Tool calls made: 27
- Tool calls failed: 1
- Stop reason: stop
- Reasoning characters: 55475
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
