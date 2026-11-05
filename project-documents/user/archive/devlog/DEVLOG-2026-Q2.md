---
docType: devlog
project: squadron
dateCreated: 20261105
dateUpdated: 20261105
---

# Development Log Archive: 2026 Q2

Archived from DEVLOG.md (see context-forge#141). Newest entries first.

## 20260628

### Slice 344: Add `understand-anything` to Analysis Pack — Task Breakdown Complete

**Phase 5 complete.** Created `project-documents/user/tasks/344-tasks.add-understand-anything-to-analysis-pack.md` (147 lines, 18 tasks).

**Task structure:** Pre-work (branch + fork) → skill file (extract, adapt, verify, commit) → dispatcher update (3 targeted edits, verify, commit) → verification gate (test suite, live install/routing, required user real-repo run) → cleanup. Test-with pattern applied: install verification (T8) immediately follows skill file addition (T7); dispatcher verification (T13) immediately follows each dispatcher change.

**Key gate:** T17 (user runs skill on real repo) is a required merge gate — slice is not done until knowledge-graph build and incremental update are both confirmed live.

---

### Slice 344: Add `understand-anything` to Analysis Pack — Slice Design Complete

**Phase 4 complete.** Created `project-documents/user/slices/344-slice.add-understand-anything-to-analysis-pack.md`.

**Design summary:** Content-only slice (effort 1/5, no Python code changes). Forks `github:Egonex-AI/Understand-Anything` (MIT) to `ecorkran/understand-anything`, extracts `understand-anything-plugin/skills/understand/SKILL.md`, prepends attribution, audits and patches instructional `/understand` self-references → `/analysis:understand-anything`, adds as `commands/analysis/understand-anything.md`, and updates the `sq:analysis` dispatcher. The existing installer's `_install_prefix()` glob picks up the new file automatically. Verification requires a user-run knowledge-graph build on a real repo before merge.

---

### Slice 343: `sq skills uninstall` and `sq doctor` Integration — Implementation Complete

**Completed:** Phase 6 implementation of slice 343. All 17 tasks done; slice marked complete.

**What shipped:**
- `InstallReceipt` model + `SurfaceType` StrEnum in `skills/models.py`
- `skills/receipts.py` — `write_receipt` / `read_receipt` (TOML via `tomli-w`, already a dependency; manual-TOML fallback not needed). Malformed/invalid receipts raise `ValueError` with path context; absent receipt returns `None`.
- `installer.install_pack()` — new `receipts_dir` param; writes a receipt after every successful install. Receipt-write failure logs WARNING, never fails the install.
- `sq skills uninstall <pack>` — reads receipt, removes exactly the files install wrote, drops the prefix dir only when empty, deletes the receipt. Graceful exit-1 with message when no receipt. Added `--receipts-dir` to `install` too.
- `doctor_checks.check_skill_packs()` + `SECTION_SKILLS`; wired into `doctor.py` `_SECTION_ORDER` and `run_all_checks()`. Uninstalled packs → WARN with `sq skills install <name>` fix hint. Present in `--json`.

**Tests:** receipts round-trip, installer receipt-writing (incl. failure-does-not-fail-install), uninstall CLI round-trip / unrelated-file-preserved / not-installed / idempotent, `check_skill_packs` installed/not-installed/no-manifest, doctor section + JSON. Full suite: 2036 passed, 2 skipped. `pyright --strict` clean, `ruff` clean.

**Verification walkthrough:** all 8 steps executed against a live dev install; output recorded in the slice design. One caveat: `tomli-w` writes `files_written` as a multi-line TOML array (cosmetic; `read_receipt` parses both forms).

**Baseline fixes (pre-existing slice-342 debt surfaced by the strict gate):**
- `tests/cli/test_install_commands.py` — expected `analysis.md` (9 sq dispatch files, was 8).
- `tests/skills/test_manifest.py` — annotated `_manifest` packs param for strict pyright.
- `tests/skills/test_cli_skills.py` — `TestInstallLocalPack` now passes `--receipts-dir` so install tests don't write a real receipt into `~/.config/squadron/receipts/`.

**State:** Slice 343 complete. Next: slice 344 (add `understand-anything` to analysis pack), no dependency on 343.

---

## 20260626

### Slice 343: `sq skills uninstall` and `sq doctor` Integration — Task Breakdown Complete

**Completed:** Phase 5 task breakdown for slice 343.

**Artifact created:**
- `user/tasks/343-tasks.sq-skills-uninstall-and-sq-doctor-integration.md` — 17 tasks, 154 lines

**Task structure summary (test-with pattern):**
- T1: Branch + prereqs
- T2–T3: `InstallReceipt` model + tests
- T4–T5: `receipts.py` helpers (`write_receipt` / `read_receipt`) + tests
- T6–T7: Extend `installer.py` to write receipt + tests
- T8: Commit checkpoint — receipt infrastructure
- T9–T10: `uninstall` subcommand in `skills.py` + tests (round-trip, unrelated-file-preserved, graceful-failure cases)
- T11: Commit checkpoint — uninstall command
- T12–T13: `check_skill_packs()` + `SECTION_SKILLS` in `doctor_checks.py` + tests
- T14–T15: Wire into `doctor.py` + tests for output
- T16: Full validation pass + CLI smoke test (verification walkthrough)
- T17: Final commit + slice status updates

**State:** Ready for Phase 6 (implementation). No open questions.

---

### Slice 343: `sq skills uninstall` and `sq doctor` Integration — Design Complete

**Completed:** Phase 4 slice design for slice 343.

**Artifact created:**
- `user/slices/343-slice.sq-skills-uninstall-and-sq-doctor-integration.md`

**Key design decisions:**
- **Install receipt** — `installer.py` writes `~/.config/squadron/receipts/<pack>.toml` after each successful install. Contains `pack_name`, `surface`, `destination`, `files_written`. Uninstall reads this rather than re-resolving the source, making uninstall correct for all source types (including `github:`) and independent of source availability.
- **No orphan detection** — `sq doctor` reports only packs declared in the effective manifest; it does not scan for installed files absent from the manifest. Deferred indefinitely.
- **WARN (not MISSING) for uninstalled packs** — skill packs are optional; absence is notable but not blocking. Matches the pattern for `check_slash_commands`.
- **Injected `receipts_dir`** — both `install_pack` and `uninstall` accept `receipts_dir` as an optional parameter for testability; defaults to the standard path.

**New/modified files at implementation time:**
- `src/squadron/skills/models.py` — add `InstallReceipt` model
- `src/squadron/skills/installer.py` — write receipt after successful install
- `src/squadron/cli/commands/skills.py` — add `uninstall` subcommand
- `src/squadron/cli/commands/doctor_checks.py` — add `SECTION_SKILLS`, `check_skill_packs()`
- `src/squadron/cli/commands/doctor.py` — add `SECTION_SKILLS` to `_SECTION_ORDER`
- New tests in `tests/skills/` and `tests/cli/`

**State:** Slice 343 is ready for Phase 5 (task breakdown) and Phase 6 (implementation). No open design questions.

---

### Initiative 340 — Slice 342 (Analysis Pack Bundled): Complete

**Completed:** Phase 6 implementation of slice 342. Analysis pack is now shipped with squadron and installable in one command with no network access.

**Key changes:**
- `src/squadron/data/skills.toml` — shipped default manifest; declares the `analysis` pack with `source="bundled"`
- `src/squadron/skills/manifest.py` — `load_effective()` now loads the shipped default as a base layer (lowest priority); `SHIPPED_DEFAULT_ORIGIN = "default"` constant added; `_load_shipped_default()` helper added
- `src/squadron/skills/resolver.py` — `_resolve_bundled()` gains a dev-mode fallback: walks up from `src/squadron/` to find the project-root `commands/` directory, enabling `sq skills install analysis` in editable installs (wheel installs use `importlib.resources` directly)
- `commands/analysis/tech-debt-audit.md` — analysis skill file (previously created on planning branch)
- `commands/sq/analysis.md` — dispatcher: `/sq:analysis tech-debt-audit` routes to the tech-debt-audit skill
- Tests: `TestLoadEffectiveWithDefault` in `test_manifest.py`, `TestBundledAnalysisPack` in `test_installer.py`, updated `TestListNoManifest` in `test_cli_skills.py` (44 skills tests, all passing)

**Notable implementation decision:** The `force-include` rule maps `commands/` into the wheel as `squadron/commands/`, but editable installs expose `src/squadron/` with no `commands/` subdirectory. Added a dev fallback in `_resolve_bundled()` to resolve via the project root. This is correct behavior: the fallback only fires when `importlib.resources` doesn't find `squadron/commands/<pack>`, which only happens in editable installs.

**Artifacts updated:**
- `user/slices/342-slice.analysis-pack-bundled.md` — Verification Walkthrough updated with actual output and dev-mode caveat; status: complete
- `user/tasks/342-tasks.analysis-pack-bundled.md` — all tasks checked, status: complete
- `user/architecture/340-slices.skill-pack-infrastructure.md` — slice 342 entry checked `[x]`
- `CHANGELOG.md` — added analysis pack, `/sq:analysis` dispatcher, and shipped default manifest entries

**State:** Branch `342-slice.analysis-pack-bundled` is 3 commits ahead of `340-planning.skill-pack-infrastructure`. Ready for merge.

**Next step:** Merge `342-slice.analysis-pack-bundled` to main; then begin slice 343 (`sq skills uninstall` and `sq doctor` integration).

---

## 20260625

### Slice 342: Analysis Pack (Bundled) — Task Breakdown Complete

Authored `342-tasks.analysis-pack-bundled.md` (12 tasks, 122 lines).

Task sequence: branch/prereq check → data package + skills.toml → extend `load_effective()` → tests → commands/analysis/ + commands/sq/analysis.md → commit checkpoint → two CLI smoke tests → integration test → full validation → final commit.

**Pending unblock:** `tech-debt-analyze.md` skill content needed from Project Manager (T5); placeholder acceptable to unblock T6–T12.

---

### Slice 342: Analysis Pack (Bundled) — Design Complete

Authored `342-slice.analysis-pack-bundled.md`.

**Key decisions:**
- Shipped default `skills.toml` at `src/squadron/data/skills.toml` acts as base layer in `load_effective()` — users see the `analysis` pack in `sq skills list` with no manual manifest setup.
- `commands/analysis/` covered automatically by the existing `force-include` wheel rule; no `pyproject.toml` changes needed for commands.
- `src/squadron/data/` package added via `__init__.py` for `importlib.resources` resolution.
- `commands/sq/analysis.md` dispatcher wired into the existing `sq install-commands` path (not `sq skills install`) for `/sq:analysis <skill>` dispatch.
- `tech-debt-analyze.md` content is an external input (existing forked skill); placeholder acceptable to unblock packaging.

**Only code change:** `manifest.py`'s `load_effective()` gains a base-layer step to load the shipped default. Everything else is new files.

**Pending:** Project Manager to supply or confirm `tech-debt-analyze.md` skill content before implementation begins.

---

### Slice 341: Manifest Format and `sq skills install/list` — Implementation Complete

All 14 tasks implemented on branch `341-slice.manifest-format-and-sq-skills-install-list`.

**What was built:**
- `squadron/skills/models.py` — `PackEntry` (Pydantic, validates exactly-one-surface), `InstallResult` (dataclass), `SkillSourceError`
- `squadron/skills/manifest.py` — `load()`, `merge()`, `load_effective()`; `ValidationError` from malformed pack entries is caught and re-raised as `ValueError` with path context
- `squadron/skills/resolver.py` — `resolve_source()`: bundled (importlib.resources), absolute/relative path, `github:` (shallow clone via subprocess+git)
- `squadron/skills/installer.py` — `install_pack()`: copies `.md` files to `commands_dir/<prefix>/` or `commands_dir/sq/<dispatch_file>.md`
- `cli/commands/skills.py` — `skills_app` Typer sub-app with `install` and `list` commands; Rich table for list; catches `SkillSourceError` and `ValueError` at CLI boundary
- `app.py` — wired `skills_app` via `add_typer`

**Tests:** 35 tests in `tests/skills/` (models, manifest, resolver, installer, CLI). All pass. 1 network-gated test (GitHub clone) skipped by default.

**One design correction during implementation:** `_USER_MANIFEST` and `_PROJECT_MANIFEST_NAME` renamed to public `USER_MANIFEST` / `PROJECT_MANIFEST_NAME` (pyright strict rejects cross-module use of private names).

**Commits:** `cdeb3a1` (subpackage foundation) + `b60ecd5` (installer, CLI, wiring).

---

### Slice 341: Manifest Format and `sq skills install/list` — Task Breakdown Complete

Authored `341-tasks.manifest-format-and-sq-skills-install-list.md` (14 tasks, 130 lines).

**Task sequence summary:**
- T1–T2: `skills/models.py` (`PackEntry`, `InstallResult`, `SkillSourceError`) + tests
- T3–T4: `skills/manifest.py` (`load`, `merge`, `load_effective`) + tests
- T5–T6: `skills/resolver.py` (bundled / local / github source resolution) + tests
- T7: Commit checkpoint — subpackage foundation
- T8–T9: `skills/installer.py` (file-copy install for prefix and dispatch_file) + tests
- T10–T11: `cli/commands/skills.py` (Typer `install`/`list` sub-app) + wire into `app.py`
- T12: CLI integration tests via Typer CliRunner
- T13–T14: Full validation pass + final commit

**Pending:** PM approval, then Phase 6 implementation.

### Slice 341: Manifest Format and `sq skills install/list` — Design Complete

Authored `341-slice.manifest-format-and-sq-skills-install-list.md`. Slice plan entry updated with materialized index and doc link.

**Design decisions committed:**

- **Manifest location:** User-level at `~/.config/squadron/skills.toml`; project-level at `<cwd>/.squadron/skills.toml`. Merge rule: additive union — project-level entries extend user-level; same-named pack in project-level wins.
- **Schema:** Each pack entry has `source` (one of `"bundled"`, absolute/relative path, `"github:<org>/<repo>"`) and exactly one of `prefix` or `dispatch_file`. Both or neither is a validation error at load time.
- **Source resolution:** `"bundled"` → `importlib.resources` (same pattern as `_get_commands_source()`); local path → direct; `github:` → shallow `git clone --depth=1` to temp dir, copy `.md` files, discard. No version pinning in v1.
- **Install semantics:** Additive within a pack's prefix directory (no deletion of pre-existing files not from the pack — that is `uninstall`'s job). Idempotent: second install overwrites files, reports success, no error.
- **No manifest auto-creation:** Missing `skills.toml` produces an actionable message; we do not silently create a default file.
- **Component structure:** New `squadron/skills/` subpackage (`manifest.py`, `resolver.py`, `installer.py`, `models.py`) with thin Typer layer at `cli/commands/skills.py`. `skills_app` added to `app.py` via `add_typer`.
- **Pydantic for manifest model**; `tomllib` (stdlib) for parsing; `subprocess` + `git` for GitHub fetch; no new third-party dependencies.

**Pending:** Phase 5 task breakdown, then Phase 6 implementation.

---

### Initiative 340 — Slice 340 (Command Surface Spike): Complete

**Completed:** Phase 6 implementation of the command surface spike.

**Decision:** Dispatch model is reliable. All four test cases passed — routing fired correctly, `<skill-args>` arrived intact, listing rendered cleanly, unknown-skill error was clear. Verdict: dispatch reliable.

**Artifacts updated:**
- `user/slices/340-slice.command-surface-spike-dispatch-vs-prefix.md` — Spike Results filled, status: complete
- `user/architecture/340-arch.skill-pack-infrastructure.md` — "Open dispatch question" principle and technical consideration updated to reflect adopted dispatch model
- `user/architecture/340-slices.skill-pack-infrastructure.md` — Slice 340 checked off

**Next step:** Slice 341 slice design — manifest format + `sq skills install/list` (supports both `dispatch_file` and `prefix` options per the spike outcome).

---

### Initiative 340 — Slice 340 (Command Surface Spike): Phase 5 Task Breakdown Complete

**Completed:** Task breakdown for the spike slice.

**Shipped:** `user/tasks/340-tasks.command-surface-spike-dispatch-vs-prefix.md` — 8 tasks, 105 lines.

**Task summary:** T1–T2 create the dispatcher and two stub files; T3 installs them; T4 runs the four prescribed test invocations; T5 records the decision in the slice design; T6 updates the arch doc; T7 removes spike files and re-syncs; T8 marks complete and commits.

**Next step:** Phase 6 implementation — run the spike (T1–T8 above).

---

### Initiative 340 — Slice 340 (Command Surface Spike): Phase 4 Slice Design Complete

**Completed:** Slice design written for the command surface spike.

**Shipped:** `user/slices/340-slice.command-surface-spike-dispatch-vs-prefix.md`

**Design summary:** A time-boxed spike. Builds a minimal dispatcher markdown file (`analysis.md`) and two stub skill files, installs them via the existing `sq install-commands` path, and runs four test invocations to determine whether Claude Code reliably passes arguments through a dispatch file. Records findings in a `## Spike Results` section appended to the slice design doc. Updates `340-arch` with the closed decision. Stub files are removed after the decision is recorded. The spike has no persistent code deliverable — its output is a decision and an arch doc update that unblocks slice 341.

**Next step:** Run the spike (Phase 6 implementation is just running four commands and recording observations), then move to slice 341 slice design.

---

### Initiative 340 — Skill Pack Infrastructure: Slice Plan Complete

**Completed:** Slice plan written at `user/architecture/340-slices.skill-pack-infrastructure.md`. Four slices across Foundation, Feature, and Integration sections.

**Slice summary:**
- **(340) Command Surface Spike** — Closes the dispatch-vs-prefix open question empirically. Time-boxed; outcome updates the arch doc. Effort 1/5.
- **(341) Manifest Format + `sq skills install/list`** — Core mechanism: `skills.toml` schema, source resolution (bundled/local/git), file-copy installer. Effort 3/5.
- **(342) Analysis Pack (Bundled)** — Ships `tech-debt-analyze` (and others) as `commands/analysis/` in the wheel; one-command install via `sq skills install analysis`. Effort 2/5.
- **(343) `sq skills uninstall` + `sq doctor` integration** — Completes the CLI surface; `sq doctor` gains a Skill Packs section. Effort 1/5.

**Next step:** Spike slice 340 when ready to begin implementation.

---

### Initiative 340 — Skill Pack Infrastructure: Architecture Complete

**Completed:** Initiative 340 added to the initiative plan and architecture document written.

**Context:** Squadron's growing use for analysis of existing codebases surfaced a gap — useful external skills (tech-debt-analyze, understand-anything, etc.) have no principled install path alongside first-party commands. This initiative adds a thin, opt-in skill pack mechanism: a TOML manifest + `sq skills install/list` that copies external skill markdown files into `~/.claude/commands/<prefix>/`, exactly mirroring the existing `install-commands` pattern.

**Key decisions captured in arch:**
- Prefix-per-pack model (`/analysis:tech-debt`) keeps `/sq:*` clean; open question is whether a dispatch router (`/sq:analysis <skill>`) is a viable UX alternative — resolved by a planned spike slice.
- File copy is the delivery primitive; no runtime indirection, no loader, no daemon involvement.
- Analysis pack ships bundled in the wheel (parallel to `commands/sq/`); external sources (local path, git ref) supported by manifest format.
- Squadron owns the analysis pack; third-party packs are supported by format but not hosted.

**Shipped:** `user/architecture/340-arch.skill-pack-infrastructure.md`, initiative entry in `001-initiative-plan.squadron.md` (index 340, cross-dep entry added).

**Next step:** Slice plan (`340-slices.skill-pack-infrastructure.md`) with spike slice as first entry.

---

## 20260617

### Slice 301: Judge Enforcement Layer — Design Complete

Authored `301-slice.judge-enforcement-layer.md`. No commits (design-only phase).

**Design decisions committed:**
- Judge templates identified by presence of a `judge:` YAML block (not naming convention — project rule forbids string dispatch). Block carries default `pass_floor`/`concerns_floor` thresholds.
- `ReviewTemplate.judge: dict[str, object] | None` + `is_judge` property; `JudgeThresholds` and enforcement logic live in a new `pipeline/actions/judge.py`, keeping the template model a thin data carrier.
- `enforce_judge()` is a pure function (logger injected); independently testable without action context.
- Provenance set for ALL results from this slice forward: `"judge"` for judge templates, `"review"` for standard templates — completing the self-describing guarantee from 300.
- Exception path (provider down, missing inputs) for judge templates returns `verdict="UNKNOWN"` rather than `verdict=None`, so checkpoints fire correctly.
- Conservative defaults: `pass_floor=75`, `concerns_floor=50` (constants in `judge.py`).
- Step-level override via `judge: {pass_floor: N}` in pipeline YAML; passed through from `ReviewStepType.expand()` to action params.

**Pending:** PM review of design before task breakdown (Phase 5).

---

### Initiative 300 — Slice 300 (Numeric Scoring Foundation): Phase 6 Implementation Complete

**Completed:** Phase 6 implementation of the keystone slice 300. All 13 tasks (T1→T13) implemented, tested, and committed one-per-task on branch `300-slice.numeric-scoring-foundation`. The slice is the additive, judging-free foundation every later 300 slice composes on.

**Shipped (six source modules, additive only):**
- `review/models.py` — `ReviewResult.score` / `.criteria` / `.provenance` (all `float|dict|str | None`, default `None`); `to_dict()` emits the three keys.
- `pipeline/models.py` — `ActionResult.score` / `.criteria` / `.provenance`, mirroring `verdict`; picked up automatically by `dataclasses.asdict`.
- `review/parsers.py` — new `_extract_score` / `_extract_criteria` helpers + a shared `_parse_finite_float`; wired into `parse_review_output`. Lenient and judging-unaware: absent/malformed → `None`, never raises, never range-checks, first `score:` wins, `inf`/`nan` rejected as non-finite. Criteria parsed from the indented YAML-map block, whole-map-to-`None` on any malformed entry.
- `pipeline/actions/review.py` — threads `result.score` / `.criteria` into the returned `ActionResult` (`provenance` left `None`).
- `review/persistence.py` — `format_review_markdown` emits a top-level `score:` line and a `criteria:` block when present; score-less output is byte-for-byte unchanged.
- `pipeline/state.py` — `StepState.score` + a score hoist in `_append_step` mirroring the verdict hoist.

**Tests:** new coverage in `tests/review/test_models.py`, `tests/review/test_parsers.py` (incl. the full failure-mode table + real score-less / score-bearing / criteria-bearing fixtures), `tests/review/test_persistence.py`, `tests/pipeline/test_models.py`, `tests/pipeline/test_state.py` (incl. backward-compat: old run-state JSON without `score` loads), `tests/pipeline/actions/test_review_action.py`. Full suite: **1969 passed, 2 skipped**; `pyright` 0 errors; `ruff check` + `ruff format --check` clean.

**Notable during implementation:**
- One real bug found and fixed in `_extract_criteria`: the `$`-in-MULTILINE label match left the slice starting at the trailing newline, so `splitlines()[0]` was empty and the block ended immediately — fixed by lstripping the leading newline. Caught by an inline probe before the test task.
- No-judging-logic-leak gate (T13): grepped the slice diff — `provenance` appears only as field declarations, comments, and the `to_dict()` serialization key; zero range checks, zero verdict-from-score derivation. Confirmed clean.
- Verification Walkthrough updated with actual commands/output; interactive steps 4–5 replaced with equivalent non-interactive probes (plus a caveat) so an external agent can run them verbatim.

**Process:** `cf:check` (workflow_check) slice 300 — clean after auto-fixing the slice-plan checkbox; slice design + task frontmatter set to `status: complete` / `dateUpdated: 20260617`; CHANGELOG `[Unreleased]` updated.

**Next step:** Phase 4 design for slice 301 (Judge Enforcement Layer) — populates `provenance`, validates the score, derives the verdict by thresholding. No model re-open needed (the shape is settled here).

---

## 20260607

### Initiative 300 — Slice 300 (Numeric Scoring Foundation): Phase 5 Task Breakdown Complete

**Completed:** Phase 5 task breakdown for the keystone slice 300. Task file created from the (review-revised) slice design.

**Shipped:** `project-documents/user/tasks/300-tasks.numeric-scoring-foundation.md` — 13 tasks, ~225 lines (well under the 450 cap, single file). Test-with ordering: each implementation task (T1/T3/T5/T7/T9/T11) is immediately followed by its test task (T2/T4/T6/T8/T10/T12); T13 is the full-suite + static-analysis + no-judging-logic-leaked validation pass. One commit per task. Closes with a coverage table mapping every LLD change to its task(s).

**Decisions/notes:**
- Tasks made authoritative on the **full three-field set** (`score`/`criteria`/`provenance`) on both `ReviewResult` and `ActionResult` — the LLD's component-summary table lagged on `provenance` in two rows, but the LLD body is explicit, so tasks follow the body. Provenance is field-only (T1/T3 add it; T13 verifies nothing populates/reads it).
- Verified all referenced test-file paths against the real tree; corrected `test_review.py` → `tests/pipeline/actions/test_review_action.py` (the others — review test_models/test_parsers/test_persistence, pipeline test_models/test_state — all exist).
- Parser failure-mode table (non-numeric/inf/nan/multi-line/malformed-criteria → `None`, no raise) is its own dedicated test task (T6).
- `cf:check` for slice 300: clean (the prior "design but no task file" info is resolved).

**Task review (glm-5.1, verdict PASS):** coverage/sequencing/test-with/sizing/commits/failure-mode-coverage all PASS. One CONCERN (F003): `_extract_criteria`'s recognized text format was underspecified — `score:` was pinned but `criteria:` was not, leaving T5/T6 without a positive-fixture anchor. **Fixed** in both LLD and task file: pinned `criteria` to the minimal YAML-map shape (top-level `criteria:` + indented `key: <number>` lines — the same idiom T9 emits), whole-map-to-`None` on any malformed value; added a criteria-bearing fixture to T6. Also fixed the LLD component-table + data-flow-diagram lag on `provenance` (body was already explicit).

**Next step:** Phase 6 implementation of slice 300, following T1→T13. After 300 lands, Phase 4 design for slice 301 (Judge Enforcement Layer).

---

## 20260605

### Initiative 300 — Slice 300 (Numeric Scoring Foundation): Phase 4 Slice Design Complete

**Completed:** Phase 4 low-level design for the keystone slice 300, the numeric-scoring foundation. Design grounded in the actual code (read `review/models.py`, `pipeline/models.py`, `review/parsers.py`, `pipeline/actions/review.py`, `review/persistence.py`, `pipeline/state.py`).

**Shipped:** `project-documents/user/slices/300-slice.numeric-scoring-foundation.md` — additive `score: float | None` + reserved `criteria: dict[str,float] | None` on `ReviewResult` and `ActionResult`; lenient, judging-unaware optional extraction in `parse_review_output`; threading through the review action's `ReviewResult → ActionResult` map; persistence on two surfaces.

**Key design decisions:**
- **"Queryable, first-class, not opaque" resolved against real code:** squadron has no SQL DB. The two queryable surfaces are (a) review-file YAML frontmatter — `score:` as a top-level key beside `verdict:`; and (b) run-state JSON — a new top-level `StepState.score` hoisted in `_append_step` from the last non-`None` action score, exactly mirroring the existing `verdict` hoist (state.py:267–286). Resolves the open question "storage representation for the queryable score."
- **Field type `float | None`** (not int, not a sentinel): float holds integer scores and future multi-sample medians; `None` is the only "absent" representation — no `0`/`-1` fallback (project no-silent-fallback rule, and a correctness prerequisite for 301's required-ness check).
- **Parser stays lenient and judging-unaware:** extracts when present, silent on absence, **no validation/range-check/thresholding.** Out-of-range values (e.g. `150`) are extracted as-is; validation → `UNKNOWN` is 301's job at the judge use. This is the parser side of the architecture's two-layer split.
- **Real-fixture tests on both paths** (score-less regression fixture + score-bearing fixture in the judge-template shape) per the project "test the parser on real input" rule.

**Scope boundary held:** no judging *logic* in this slice — required-ness, validation, thresholding, and verdict derivation are all 301.

**Design review (glm-5.1, verdict CONCERNS) — both concerns addressed:**
- **F001 (provenance):** the architecture commits the provenance field to the *result model*, and 300 is the keystone "settle the model shape once" slice — so deferring provenance entirely to 301 would force 301 to re-open the models. **Fix:** add `provenance: str | None = None` as a *latent reserved field* in 300 (mirrors how `criteria` is reserved), unpopulated/unread here; 301 supplies only its meaning and use. No model re-open downstream.
- **F002 (parser failure modes):** added an explicit failure-mode enumeration table for the new score/criteria extraction path (non-numeric value → `None`; `inf`/`nan` → `None`; multiple score lines → first wins; malformed criteria → whole map `None`) — never raises, never fabricates a number. Observable-WARNING-on-required-absence stays 301's job (firing it in the parser would trigger on every ordinary score-less review). Satisfies the project Failure-Mode Enumeration rule.
- F003 (note): structured-output parser shape correctly deferred to 302 — no change.

**Next step:** Phase 5 task breakdown for slice 300, then Phase 6 implementation. After 300 lands, Phase 4 design for slice 301 (Judge Enforcement Layer).

---

## 20260604

### Initiative 300 (Intrinsic LLM Judging & Scoring): Phase 3 Slice Planning Complete

**Completed:** Phase 3 slice planning for initiative 300. Slice plan created from the reviewed architecture document; architecture marked `complete`.

**Shipped:**
- `project-documents/user/architecture/300-slices.eval-actions-llm-as-judge-scoring.md`: five slices in dependency/implementation order — (300) Numeric Scoring Foundation [keystone, foundation, done alone], (301) Judge Enforcement Layer, (302) Design-Phase Judge Templates, (303) Judge-Gated Cycle Conventions, (304) Gate Composition [integration]. Plus a Future Work backlog: multi-sample judging, on-demand ground-truth fetching, checkpoint multi-verdict support (140).
- `300-arch.eval-actions-llm-as-judge-scoring.md`: status `reviewed` → `complete`, dateUpdated 20260604.

**Key planning decisions:**
- Keystone (300) ordered first and done alone, per the architecture — the only Medium-risk cross-cutting model/parser/persistence change; everything composes on it.
- Refined the architecture's four anticipated slices into five by splitting the judge **enforcement layer** (301: required-ness, 0–100 validation, score→verdict thresholding, provenance) from the judge **templates** (302). The two-layer parser/action split is an explicit architectural commitment, the enforcement is independently testable, and no template is gateable until it exists.
- Every slice is additive and leaves the system in a working state; existing verdict-gating pipelines unchanged throughout.
- Gate composition (304) carries the architecture's explicit boundary: prefer upstream reduction (additive, in-scope 300); if insufficient, escalate checkpoint multi-verdict support as a coordinated 140 dependency, not a silent absorption.

**Open questions deferred to slice design (Phase 4):** provenance field name/enum, threshold band values + config keys, queryable-score storage representation, which design-phase judge templates to author first.

**Next step:** Phase 4 slice design for slice 300 (numeric scoring foundation), the keystone.

---

## 20260531

### Initiative 300 scope reduction + Initiative 320 + orchestrator Future Work — Design

Major rethink after a review (GLM-5.1, CONCERNS) and an extended PM/architect design conversation. The 300 arch doc had spiraled toward over-engineering; pulled it back to what's actually needed, and split the rest into a sibling initiative and a far-future Future Work entry.

**The "why" (captured for future context — this is the motivation behind 300/320 and the orchestrator):**
Squadron is an excellent *deterministic workflow engine* running a *non-deterministic process*. High accuracy, decent-but-variable code quality, and an external quality standard now exists to measure against (a forked MIT `tech-debt-audit` Claude skill, adapted for squadron projects, which surfaces plenty of issues). In return for high accuracy it demands human-in-loop at too many gates — rarely at code, sometimes extensively at *design* — heavy enough that simple projects aren't worth the overhead. The automation breaks precisely at the **decision points**, because those are non-deterministic. LLM judgment at those points is the missing piece. (Origin: the CCA training + two interviews surfaced the eval gap; adding it makes squadron feel "complete"/legit — a workflow engine without eval is a car without a speedometer.)

**Determinism/leverage ladder (the framing that resolved where agentic loops belong):**
1. Now — high-accuracy, high-effort workflow engine (human at every gate).
2. 300/320 — judge-at-decision-points; trade some accuracy for far less effort; variability accepted but kept minimal.
3. Future — an orchestrator agent driving CF+squadron, human consulted only on hard calls; another leverage jump.
Organism metaphor: CF structures = stable skeleton; LLM judges/orchestrator = nervous system (joints absorbing variability, making local decisions); human = consulted only where it matters. **Agentic loops belong ONLY at rung 3, above the engine — never inside a pipeline action.** The doc kept spiraling because it tried to put a rung-3 turn-loop inside a rung-2 action (the read-file capability). Removing that dissolved the circularity.

**Initiative 300 — reduced and renamed → "Intrinsic LLM Judging & Scoring".**
Now two reuse-first capabilities only: (1) an optional 0–100 numeric **score** added additively to result models/parser/persistence (keystone slice, done first), verdict *derived from* score by threshold (score = source of truth, verdict = its projection for `--step-done --verdict`), optional `criteria` map reserved from the start; (2) an **intrinsic judge** = the *existing* `review` action with a judge system-prompt emitting score+findings, composing with *existing* `each`/`loop`/`commit` for unattended review→fix→re-review. Ground truth is **in-repo** (parent doc, rules, code, phase criteria) — no external answer key. Prioritize design-phase gates (slice-vs-arch, tasks-vs-slice). **Dropped from 300:** the `eval:judge` action (duplicative of `review`), reference datasets, per-case dataset loop, read-file/turn-loop, fan-in aggregation. Arch doc fully rewritten; `status: not_started` (needs fresh review against reduced scope). Second-review findings re-dispositioned: F001/F002/F006/F007 fixed & carried forward, F003/F004/F005 removed from scope, F008 retained as a slice-design caveat.

**Reference datasets — ruled out (not deferred scope, a different product).** Curated input/expected pairs to grade a model in the abstract. Poor fit here: prompts are complex, outputs non-deterministic (valid solutions vary), and ground-truth strength is a *gradient* — strong for tasks-vs-slice, minimal for arch-concept-vs-initiative-blurb. Squadron's judging needs none of it; its ground truth is the project's own documents.

**Initiative 320 (new) — "Judge Calibration & Quality Metrology".** Answers "how good are the judges themselves?" Ground truth = **the human, sampled**: operator spot-checks a sample of judge verdicts; system reports judge-vs-human agreement + judge-vs-judge dispersion ("does model X overreach while Y rubber-stamps?"). Trust is per-artifact-level (scales with in-repo ground-truth strength) and feeds 300's escalate-vs-auto-gate decision. Includes the **tech-debt-audit code-quality baseline** + a dispatch-side **prompt-chaining pre-emption** prompt (chained because the current one is already complex) as the first measurable customer (audit-findings-per-project should drop). Two oracles, same metrology shape: tech-debt-audit (code), human-sampled agreement (design). Depends on [100, 140, 300]. Overview/rough-concept captured in the initiative-plan entry; full design in coming weeks.

**Orchestrator — Future Work entry.** The rung-3 organism; named to keep its agentic loop from being smuggled back into 300-band components. Promote to a full initiative when pursued.

**Index spacing:** initiatives now spaced by 20 (300, 320). 310 intentionally skipped.

**Delivered:** rewrote `300-arch.eval-actions-llm-as-judge-scoring.md`; updated `001-initiative-plan.squadron.md` (300 entry slimmed, 320 added, Future Work section added, cross-deps + dateUpdated); re-dispositioned `300-review.arch...md`.

**Pending:** fresh review of slimmed 300; `/cf:prompt get add-initiative-overview` already applied to capture 320 as a plan entry — a standalone 320 concept doc was not created (project has no concept-doc convention; the plan entry + this DEVLOG are the durable capture). All planning edits remain uncommitted on branch `908-sq-setup-one-call-install-orchestrator`.

---

## 20260530

### Initiative 300: Eval Actions (LLM-as-Judge & Scoring) — Design Complete

Stood up a new initiative and authored its architecture document. Adds an `eval` action family that gives squadron's deterministic executor a judgment-and-measurement layer.

**Delivered:**
- Initiative 300 entry added to `001-initiative-plan.squadron.md` (index 300, after 280; dependencies [100, 140]); cross-initiative dependency entry and `dateUpdated` refreshed.
- `300-arch.eval-actions-llm-as-judge-scoring.md` created and registered (`cf set arch 300`).

**Component shape.** `eval:judge` is LLM-as-judge: reuses the existing provider-agnostic review engine (`run_review_with_profile`) with a judge system-prompt and reference-dataset inputs, emitting a **0–100 scalar score + verdict + findings**. The verdict drops into the existing `sq run --step-done --verdict` checkpoint machinery with no new plumbing.

**Key decisions:**
- **Initiative, not a single slice** — because numeric scoring is a cross-cutting change to result models every pipeline depends on, reference-dataset eval is new infrastructure, and eval/review gate composition is an open arch question.
- **Keystone slice first:** numeric scoring foundation (add `score` *alongside* verdict, additive/backward-compatible, verdict stays authoritative at summary level). Isolated and done first to de-risk the model migration.
- **Scalar summarizes a latent criterion vector** — scalar consumed now, vector recorded but not surfaced.
- **Read-file-on-request tool** for non-SDK judges is owned by this initiative (the canonical minimal one), but is a **secondary, later slice** — explicitly *not* dependent on 260's full agentic loop (260 may consume it later).

**Grounding (verified against source this session):** action registry is open (`register_action`); `ActionResult` already carries `verdict`/`findings`; verdict enum `PASS|CONCERNS|FAIL|UNKNOWN` is exactly what `--step-done --verdict` consumes; provider/model support comes from the profile registry; the 500KB injection cap is the binding constraint on non-file-reading judge models.

**Pending / open (for slice design):** dataset format & location convention; scalar score range vs. per-criterion schema detail; eval/review gate-composition policy (combined / separate / per-review-type).

**Note:** these are planning-doc edits made on branch `908-sq-setup-one-call-install-orchestrator`; not yet committed.

---

## 20260520

### Slice 908: `sq setup` — Phase 6 Implementation Complete

**Completed:** Phase 6 implementation for slice 908. Slice is complete.

**Shipped:**
- `src/squadron/cli/commands/setup_steps.py` (~220 lines): pure conversion layer (`CheckResult → SetupStep`). `StepKind` StrEnum, `SetupStep` frozen dataclass, `_RECHECK_MAP`, `_classify`, `build_steps` with profile filtering, `_DOCS_ANCHOR`, `_EXPLANATION`, synthesised per-profile recheck lambdas.
- `src/squadron/cli/commands/setup.py` (~120 lines): Typer command with `--non-interactive`, `--check-only`, `--profile`, `--verbose` flags. Rendering functions `_render_check_only`, `_render_non_interactive`, `_run_interactive` (re-prompt cap=5, `q` exits 2).
- `src/squadron/cli/app.py`: `app.command("setup")(setup)` registration.
- `scripts/install.sh` (~100 lines): bash bootstrap with `set -euo pipefail`, interactive prompts, `uv`/`pipx` detection, `npm` detection, `--yes`/`--help` flags, `exec sq setup` handoff.
- `tests/cli/test_setup_steps.py`: 20 tests covering T3, T6, T10, T11, T12.
- `tests/cli/test_setup.py`: 10 tests covering T18a, T18b, T19, T20, T21, T22, T23, T24.
- `tests/scripts/test_install_sh.sh` + `test_install_sh.py`: idempotency smoke test (T26).
- README: "Fresh install (one liner)" section added (T27).
- CHANGELOG: `sq setup` and `scripts/install.sh` entries added.

**Deviations from design:** None. All design decisions implemented as specified.
- T28 (QUICKSTART callout) skipped — `docs/QUICKSTART.md` does not exist yet (slice 906 not merged). DEVLOG follow-up noted.
- Aggregate "at least one provider OK" suppression optimisation deferred per design decision (initial release shows all profile rows).

**Test results (final gate):**
- `pytest tests/cli/test_setup.py tests/cli/test_setup_steps.py tests/scripts/test_install_sh.py -q`: **31 passed**
- `pytest -q` (full suite): **1936 passed, 2 skipped**
- `ruff check && ruff format --check && pyright`: **all clean**

**Exit codes verified:** 0 (all OK), 1 (MISSING present), 2 (user quit), 3 (internal error), 64 (unknown profile).

**Follow-up:** When slice 906 merges and `docs/QUICKSTART.md` exists, add the `sq setup` callout under Step 5 / Troubleshooting (T28).

**Branch:** `908-sq-setup-one-call-install-orchestrator`.

---

## 20260519

### Slice 908: `sq setup` One-Call Install Orchestrator — Phase 4 Slice Design Complete

**Completed:** Phase 4 low-level design for slice 908.

**Document created:**
- `project-documents/user/slices/908-slice.sq-setup-one-call-install-orchestrator.md` — full slice design (status: `not_started`)

**Slice plan updated:** `900-slices.maintenance-and-refactoring.md` entry 7 now references the materialized design path.

**Design highlights:**
- `sq setup` is a *renderer* over slice 905's `run_all_checks()` — no new check logic. Conversion layer maps each `CheckResult` to a `SetupStep` with kind `ALREADY_DONE` / `INSTALL` / `CONFIGURE` / `OPTIONAL`.
- Three modes: interactive (default, one prompt per missing step with `enter/s/q`), `--non-interactive` (emit all steps without prompts; pipe-to-file friendly), `--check-only` (one-liner per step, exits with `sq doctor`'s code).
- `--profile <name>` filters Provider-section steps to a single profile.
- Per-step re-check via a local "check-name → function" map inside `setup_steps.py`. Degrades to "press enter when done" if 905 adds checks we haven't mapped.
- Companion `scripts/install.sh` (bash) handles only the pre-Squadron bootstrap (pipx/uv → `pipx install squadron-ai` → `npm i -g @manta-digital/context-forge` → handoff to `sq setup`). No automatic shell execution from Python.
- Distribution via GitHub raw URL: `curl -sSL <raw URL> | sh`. Pinning to a tag is a follow-up.
- Idempotency contract: setup is re-runnable, install.sh is re-runnable; both detect existing state and skip done steps.

**Cross-slice contract:**
- Strict consumer of slice 905's `CheckResult`, `CheckStatus`, `run_all_checks()`. No API changes requested upstream.
- References slice 906 (QUICKSTART) anchors for `docs_anchor`. If 906 ships later, anchors degrade gracefully to plain section names.

**Branch:** `908-sq-setup-one-call-install-orchestrator` (created from `main`).

**Next:** Phase 5 task breakdown — `task-checker`-friendly checklist derived from this design.

---

### Slice 908: `sq setup` — Phase 5 Task Breakdown Complete

**Completed:** Phase 5 task breakdown for slice 908.

**Document created:**
- `project-documents/user/tasks/908-tasks.sq-setup-one-call-install-orchestrator.md` — 32 tasks (T1–T32) across seven phases (status: `not_started`).

**Phase shape (test-with-pattern preserved throughout):**
- **A. Setup and data model** — branch confirmation, skeleton files, `StepKind` / `SetupStep` dataclass, baseline tests.
- **B. `build_steps` conversion layer (pure)** — recheck-function map, `_classify`, `build_steps`, docs-anchor map, explanation strings; each implementation immediately followed by its tests.
- **C. `setup.py` Typer command and rendering** — command skeleton with all flags, `--check-only` / `--non-interactive` / interactive renderers, registration in `cli/app.py`.
- **D. Tests for `setup.py`** — `CliRunner`-based coverage of every flag combination, profile filter, `q`-quit, recheck loop, and the internal-error fallback.
- **E. `install.sh` bootstrap** — bash script with `set -euo pipefail`, explicit prompts before each install, plus a `pytest`-wrapped idempotency smoke test using PATH-shimmed stubs.
- **F. Documentation** — README one-liner pointer; optional QUICKSTART callout gated on slice 906 merge order.
- **G. Final gate** — full `pytest` / `ruff` / `pyright` gate, verification walkthrough recording into the slice design, slice-plan checkbox flip, DEVLOG closeout.

**Notable design constraints carried into tasks:**
- No automatic shell execution from Python beyond `install_commands()` with explicit consent.
- Per-step re-check cap = 5 (prevents infinite loops in scripted stdin).
- `q` exits 2 (user-aborted), distinct from 1 (`sq doctor` reports missing) and 3 (internal error).
- `_DOCS_ANCHOR` and `_EXPLANATION` maps are local to `setup_steps.py` — no upstream API changes to slice 905.

**Review note:** Phase 4 review flagged 908 as "new feature under maintenance arch" (F001). PM decision was to leave categorisation alone — 905/906/908 form a cohesive onboarding trio that has historically lived under the 900 maintenance architecture. No design changes resulted.

**Task file size:** 259 lines (well under 450-line target; no split needed).

**Branch:** `908-sq-setup-one-call-install-orchestrator`.

**Next:** Phase 6 implementation following T1–T32 in order.

---

## 20260518

### Slice 907: Optional Dependency Split — Task Breakdown Complete

**Completed:** Phase 5 task breakdown. Task file created at `user/tasks/907-tasks.optional-dependency-split-serve-and-codex-extras.md` (173 lines, 8 task groups, 31 checklist items).

**Task structure:**
- T1: Branch setup
- T2: `pyproject.toml` — remove fastapi/uvicorn from deps, add `[serve]` and `[codex]` extras
- T3: Extract `src/squadron/server/pid.py` (DaemonConfig + PID helpers); update `daemon.py` to import from it; update `tests/server/test_daemon.py`
- T4: Update `serve.py` — top-level imports switch to `pid.py`; `start_server`/`SquadronEngine` deferred into `_start_daemon()` after import guard
- T5: Codex binary guard in `provider.py` — `create_agent()` raises `ProviderError` (not `ProviderAuthError`) when binary absent
- T6: Full test suite + static analysis (ruff, pyright, pytest)
- T7: Clean-venv verification walkthrough
- T8: Commit

**Status:** Ready for Phase 6 (Implementation).

---

## 20260514

### Initiative 200: Multi-Agent Communication — Architecture Rewrite

Rewrote `200-arch.multi-agent-communication.md` and `200-slices.multi-agent-communication.md` to reflect a fundamentally different model from the original pub/sub message bus design.

**Why:** IDE plugins (Claude Code, Codex) and interactive sessions are reactive — they cannot receive async push. The original bus model assumed agents could be woken up; they can't. The new model is pull-based: a shared SQLite task store owned by the daemon, agents poll for work, claim atomically, complete via daemon socket.

**New model summary:**
- Daemon (`sq serve`) owns `workspace.db` (SQLite, WAL mode), listens on Unix socket
- `sq run` posts tasks via socket, polls DB read-only for results — no more SDK session spawning from CLI
- Claude Code IDE participates via `/sq:work` slash command + MCP tools
- Codex IDE plugin: same poll/claim/complete loop, capability-routed
- Hermes (remote machine): connects to local daemon via SSH tunnel, same socket protocol
- Project isolation via `project_path` column — one daemon, one DB, multiple projects

**Dropped from original 200-series:** Supervisor (OTP restart patterns), Message Bus Core, Multi-Agent Message Routing, Human-in-the-Loop as bus participant, Communication Topologies, ADK Integration, REST+WebSocket, Subprocess Agent Support.

**Retained/adapted:** 203 (Anthropic API Provider, standalone, unchanged), 208→224 (MCP tools, repurposed for poll/claim), 210 (Ensemble Review, unchanged), 212→228 (E2E testing, rescoped).

**New slices:** 221 (Task Store schema), 222 (Daemon Socket Server), 223 (Pipeline Executor Integration), 224 (MCP Tools), 225 (/sq:work slash command), 226 (Capability Routing), 227 (sq work Hermes worker CLI).

**June 15 relevance noted:** Slices 203 + 223 together eliminate the Agent SDK credit dependency for `sq run` pipeline steps. Prioritized in implementation order notes.

### Slice 907: Optional Dependency Split — Design Complete

**Completed:**
- Created `user/slices/907-slice.optional-dependency-split-serve-and-codex-extras.md`

**Key Design Decisions:**
- `fastapi` and `uvicorn` move from `[project.dependencies]` to a new `[serve]` optional extra.
- `[codex]` extra is declared empty (PyPI rejects direct URL refs); a comment block carries the GitHub install command.
- `sq serve` start guard lives inside `_start_daemon()` — `--status` and `--stop` remain usable without `[serve]`.
- `start_server` and `SquadronEngine` imports deferred into `_start_daemon` after the guard; `DaemonConfig`/PID helpers stay top-level (verify they don't transitively pull fastapi; extract to `server/pid.py` if they do).
- `CodexProvider.create_agent()` gains an early binary check (`resolve_codex_binary is None` → `ProviderAuthError` with `npm i -g @openai/codex`). SDK import guard already present in `_run_prompt`; no change needed there.

**Status:**
- Design ready for Phase 5 (Task Breakdown).

---

## 20260513

### Slice 906: Quickstart and Onboarding Documentation — Phase 4 Slice Design

Authored `user/slices/906-slice.quickstart-and-onboarding-documentation.md`.

Scope: docs-only. Two deliverables — new `docs/QUICKSTART.md` (step-by-step from
zero to working `sq run`) and targeted README edits (Quickstart → pointer, Install →
keep global-install block only).

Key design decisions:
- QUICKSTART is structured as numbered install steps matching the `sq doctor` fix-hint
  contract: every hint emitted by doctor maps to a named QUICKSTART section. This
  mapping is documented in the slice design as a stable interface.
- Provider matrix table derived from `BUILT_IN_PROFILES` — covers sdk, openai,
  openrouter, gemini, local, openai-oauth (experimental), and Anthropic API (planned,
  slice 203).
- README Quickstart section replaced with ~3 lines + link; dev-install block moves
  to QUICKSTART under a contributing subsection.
- No code changes. Effort 1/5.

### Slice 905: `sq doctor` — Phase 6 Implementation Complete

Completed full implementation of `sq doctor` in a single session across 35 tasks.

Two new files: `src/squadron/cli/commands/doctor_checks.py` (~280 lines, pure check
functions + `run_all_checks()`) and `src/squadron/cli/commands/doctor.py` (~120 lines,
Typer command + Rich/JSON rendering). One edit to `cli/app.py` to register the command.

Key implementation decisions:
- Module-level imports for `get_all_profiles`, `providers_toml_path`, `models_toml_path`
  (not lazy inside functions) — required for test patching to work correctly.
- `Console(soft_wrap=True)` for path-heavy detail strings that exceed terminal width.
- `_API_KEY_ONLY_PROFILES` fixture in integration tests because `sdk`, `local`,
  `openai-oauth` profiles return `is_valid()=True` unconditionally — a fresh-system
  env var wipe doesn't actually leave zero valid providers. The fixture simulates
  a minimal env with only API-key-based profiles for the "fresh-system → exit 1" scenario.
- Scenario 3 (broken providers.toml) produces two error signals: `get_all_profiles()` 
  raises before per-profile checks run (process-boundary handler emits WARN), then 
  `check_providers_toml()` independently emits the MISSING row. Both correct; both informative.

Tests: 35 doctor tests added; full suite 1904 passing, 2 skipped (pre-existing). Ruff/pyright clean.

Branch: `905-sq-doctor-environment-diagnostic-command`. Not yet merged.

### Slice 905: `sq doctor` — Phase 5 Task Breakdown

Authored `user/tasks/905-tasks.sq-doctor-environment-diagnostic-command.md`
(35 tasks across four phases: setup/data-model, individual checks,
orchestration/rendering, final integration).

Test-with pattern applied throughout — every implementation task is
immediately followed by its test task (T4→T5, T6→T7, T8→T9, etc.), no
batched test phase. Each check function gets its own implementation +
test pair so failures surface against a small surface area.

Phase A (T1–T3) bootstraps the branch, skeleton files, and the
`CheckResult`/`CheckStatus` data model. Phase B (T4–T23) implements the
10 individual check functions. Phase C (T24–T30) wires orchestration,
Rich + JSON rendering, the Typer command, and 6 CliRunner integration
tests. Phase D (T31–T35) is the gate (pytest/ruff/pyright), manual
scenario verification mirroring 904's recorded-outcomes pattern,
CHANGELOG, commit, and slice closure.

Notable choices:

- Provider profile tests use real `monkeypatch.setenv` against the real
  auth registry — not mocked `resolve_auth_strategy_for_profile`. We're
  testing integration with the actual auth strategies, not a fake.
- TOML config checks distinguish absent (informational OK) from
  malformed (MISSING). Repairing the file is the fix hint.
- Process-boundary catch in `run_all_checks()` wraps each check call;
  one broken check emits a synthetic WARN row instead of aborting.
- Top-level command body raises `typer.Exit(exit_code)`. Exit 1 iff any
  MISSING row exists; WARN never affects exit code.

Status: not_started · 35 tasks · 219 lines.

---

### Slice 905: `sq doctor` Environment Diagnostic — Phase 4 Slice Design

Authored `user/slices/905-slice.sq-doctor-environment-diagnostic-command.md`.
Design covers a read-only `sq doctor` subcommand that orchestrates pure
check functions over existing inspection targets — `get_all_profiles()`,
`resolve_auth_strategy_for_profile()`, `providers_toml_path()`,
`models_toml_path()`, `shutil.which("cf"|"codex")`, Claude Code env-var
presence — and renders a Rich table (default) or JSON (`--json`).

Key decisions:

- Two new files: `cli/commands/doctor.py` (Typer command + rendering) and
  `cli/commands/doctor_checks.py` (pure synchronous check functions
  returning a `CheckResult` dataclass). Separation keeps checks unit-
  testable without Typer.
- "Apparent intent" inference is deferred. Required checks are only those
  that block all Squadron use (the package itself, at-least-one provider
  authenticated, parseability of any user-supplied `providers.toml` /
  `models.toml`). Provider-specific and integration-specific rows are
  WARN. Exit 1 iff any MISSING row.
- WARN rows are hidden by default; surface via `-v`. JSON output always
  includes all rows.
- No network calls. Auth correctness against the wire remains
  `sq auth login`'s job. Doctor reports "authenticated locally" — not
  "will work."
- Failure-mode enumeration is explicit for every I/O point (malformed
  TOML, missing HOME, stale `which` results, unexpected profile shape,
  `PackageNotFoundError` for dev installs). Every catch logs at WARNING
  per project rules.

Pairs with slice 906 (Quickstart docs) — `fix_hint` strings are the
contract 906 will reference verbatim.

Status: not_started · Effort: 2/5 · Risk: Low · Dependencies: none.

---

## 20260510

### Slice 250: Container Step Classification — Implementation Complete

**Completed:** Phase 6 implementation. Slice 250 is complete.

**Summary of changes (commit 91f8ccd):**
- New `src/squadron/pipeline/steps/utils.py` — `unpack_inner_steps` extracted from `executor.py` to eliminate circular import
- `executor.py` — replaced local `_unpack_inner_steps` with imported utility
- `EachStepType.inner_steps()`, `LoopStepType.inner_steps()` — parse `steps:` list, return `StepConfig` objects
- `FanOutStepType.inner_steps()` — returns one synthetic `_fan_out_aggregate` sentinel carrying the `models:` value
- `classification.py` — added `_classify_alias_set` (shared alias-set aggregator), `_classify_container_inner` (classifies a single inner step / handles `_fan_out_aggregate` sentinel), extended main step loop to descend into containers when `expand()` returns `[]`; added `container_path: str | None = None` field to `StepClassification`
- `run.py` — `_render_explain` emits dim container header rows and `↳ {inner_name}` indented inner-step rows
- 27 new tests across `test_inner_steps.py`, `test_classification.py`, `test_run.py`
- Full suite: 1869 passed, 2 pre-existing failures (compact compose integration)

**Notable implementation decisions:**
- Used `getattr(step_impl, "inner_steps", None)` instead of a lambda to avoid pyright `Unknown` errors
- Rich wraps cell content in narrow test terminals — `↳` assertions check for the symbol presence rather than `"↳ name"` substring
- `_classify_pool_step` refactored to a thin wrapper over `_classify_alias_set` preserving `pool_name`

---

### Slice 250: Container Step Classification — Task Breakdown Complete

**Completed:** Phase 5 task breakdown.

**Documents created:**
- `project-documents/user/tasks/250-tasks.container-step-classification-each-loop-fan-out.md` — 12 tasks, 321 lines

**Task structure:**
- T1: Branch setup
- T2: Extract `_unpack_inner_steps` → `steps/utils.py` (removes circular import); update executor call sites
- T3: `EachStepType.inner_steps()` + tests
- T4: `LoopStepType.inner_steps()` + tests
- T5: `FanOutStepType.inner_steps()` returning sentinel `_fan_out_aggregate` + tests
- T6: Extract `_classify_alias_set` from `_classify_pool_step`; regression test
- T7: Add `container_path: str | None = None` to `StepClassification`; regression test
- T8: Core classifier extension — `_classify_container_inner` helper + modified step loop; 9 new classification tests
- T9: `_render_explain` container rendering (header row + `↳` indent) + 3 rendering tests
- T10: ruff format/check, pyright, full pytest gate
- T11: Implementation commit
- T12: Slice closeout (status, slice plan, CHANGELOG, DEVLOG, docs commit)

**Key task notes:**
- T2 is the prerequisite for T3/T4 (circular import blocker). T5 is independent of T3/T4.
- T6 must precede T8 (T8 calls `_classify_alias_set`).
- T7 must precede T8 and T9 (both use `container_path`).
- T8's `_classify_container_inner` asserts `inner.step_type != "_fan_out_aggregate"` before `get_step_type()`, enforcing the sentinel invariant.

**Status:** Ready for Phase 6 (Implementation).

---

### Slice 250: Container Step Classification — Design Complete

**Completed:** Phase 4 slice design.

**Documents created/updated:**
- `project-documents/user/slices/250-slice.container-step-classification-each-loop-fan-out.md` — full LLD
- `project-documents/user/architecture/240-slices.pipeline-auth-boundary-flexibility.md` — slice 250 entry updated with design link and today's date

**Key design decisions:**
- `inner_steps(config)` added as an optional extension method on step types (detected via `hasattr`, not a required protocol method) — avoids touching all existing step type files.
- `_unpack_inner_steps` extracted from `executor.py` to a shared location so `EachStepType` and `LoopStepType` can reuse it in `inner_steps()` without a circular import.
- `fan_out` returns one synthetic sentinel `StepConfig` (`step_type="_fan_out_aggregate"`) encoding the `models:` field. The classifier detects the sentinel and routes to pool-classify or alias-list-classify accordingly.
- `_classify_alias_set` extracted from `_classify_pool_step` as a shared helper — both the pool path and the fan_out literal-list path call the same aggregation rule.
- `StepClassification` gains `container_path: str | None = None` (backward-compatible, defaults to `None`).
- `--explain` rendering uses `  ↳` indent in the Step column rather than a new column — keeps table width manageable.
- Parent step attribution: inner-step `StepClassification` rows carry the container's `step_name` and `step_index`, not the inner step's own name (which goes in `container_path`).
- No executor changes in scope.

**Status:** Ready for Phase 5 (Task Breakdown).

---

## 20260507

### Slice 243 follow-up: classify_pipeline missed phase-step dispatches (commit aef3b41)

Discovered while testing slice 246's `--explain` against P4: the classifier
returned a single non-SDK row (the summary step), reporting P4 as
Claude-free even though P4's `design` step dispatches with the default
`model: sonnet` (SDK).

**Root cause:** `_MODEL_DISPATCHING_STEP_TYPES` in `classification.py`
gated on raw step-type names (`dispatch`/`review`/`summary`/`compact`).
Phase step types (`design`/`tasks`/`implement`) expand into those
actions via `StepType.expand()` but their step-type name doesn't match,
so the classifier silently skipped them. The same gap also affected the
embedded review block under a phase step.

**Fix:** Classifier now walks `StepType.expand()` and classifies each
emitted model-dispatching action. Action configs run through
`resolve_placeholders` against pipeline-default params so `{model}`-style
templates resolve to their concrete alias before cascade lookup. Two test
fixtures for standalone review steps were updated to include the required
`template` field.

**Known limitation (out of scope here):** `each`, `loop`, and `fan_out`
step types return `[]` from `expand()` — their inner model dispatches are
still uncovered by classification. These are handled directly by the
executor; a future slice should either teach those step types to surface
their inner dispatches, or extend the classifier to introspect them.

---

## 20260506

### Slice 246: Auth-Classification Diagnostics CLI — Complete (commit ec72fab)

All 9 tasks implemented in a single pass on branch `246-slice.auth-classification-diagnostics-cli`.

**Changes:**
- `src/squadron/cli/commands/run.py` — Added `--explain` flag, `_render_explain`, `_handle_explain`, `_extract_model_override`, `_SHAPE_LABELS` constant, `_STEP_CLASS_COLORS` constant, mutual-exclusivity guards (5 incompatible options), and dispatch branch. All confined to this file; no new modules.
- `tests/cli/commands/test_run.py` — Added `TestExplainMutualExclusivity` (5 tests) and `TestExplainCommand` (8 tests). Total test count: 1863 passing.

**Verification findings:**
- `uv run sq run p6 --explain` and `uv run sq run implement --explain` work correctly.
- `test-compact-compose` has a misconfigured `summary-2` step with no model at any cascade level — `--explain` correctly raises `ClassificationError` for it. Verification walkthrough updated to use `p6` and `implement` instead.
- Pre-existing integration test failures (2 in `test_compact_compose_integration.py`) are unrelated and present on `main` before this branch.

**Quality gates:** ruff format ✓, ruff check ✓, pyright ✓ (3 pre-existing errors), pytest 1863 passed.

---

### Slice 246: Auth-Classification Diagnostics CLI — Task Breakdown Complete

No commits (planning-only phase).

Created `project-documents/user/tasks/246-tasks.auth-classification-diagnostics-cli.md` (173 lines, 9 tasks).

**Task sequence:** Flag declaration (T1) → mutual-exclusivity guard (T2) → guard tests (T3) → `_render_explain` renderer (T4) → `_handle_explain` handler (T5) → wire dispatch branch (T6) → happy-path tests (T7) → error-path tests (T8) → quality gates + commit (T9).

All changes confined to `src/squadron/cli/commands/run.py` and `tests/cli/commands/test_run.py`. No new modules. Dependencies (classify_pipeline, PipelineClassification, all related enums) fully stable.

**Ready for Phase 6 (Implementation).**

---

## 20260505

### Slice 246: Auth-Classification Diagnostics CLI — Design Complete

No commits (design-only phase).

Created `project-documents/user/slices/246-slice.auth-classification-diagnostics-cli.md`. Updated slice plan entry (240-slices) to reference the design document and pin the flag name as `--explain`.

**Decisions:**
- Flag name `--explain` (over `--classify`, `--auth-check`) — most natural for the "explain to me why this needs Claude auth" user intent.
- No new module; all changes land in `cli/commands/run.py`: new `--explain` flag, `_handle_explain`, and `_render_explain`.
- `--explain` accepts `--model`, `--param`, `--strict`, and `--verbose`; rejected alongside execution options (`--resume`, `--dry-run`, `--from`, `--prompt-only`, `--validate`).
- Resolver construction duplicates `_run_pipeline_sdk`'s `_classify_resolver` block intentionally — deferred to a `_build_classification_resolver` helper only when a third call site appears.
- No `--json` output in this slice; trivial to add as a maintenance task later.
- Rich table for per-step output (matches existing CLI conventions); summary panel below.

**Ready for Phase 5 (Task Breakdown) and implementation.**

---

### Initiative 260: Non-SDK Agent Tool Use — Architecture and Slice Plan Complete

Commits `0d94d7b` (arch + slice plan), `0c19515` (arch review).

**Context:** Triggered by observing that `test-p4.yaml` with `model: kimi25` fails silently — the model emits raw tool-call XML into the response stream because `OpenAICompatibleAgent` never passes `tools` to the API and has no execution loop. Confirmed via code audit that `allowed_tools`, `permission_mode`, and all tool-related `AgentConfig` fields are silently ignored by non-SDK providers.

**Architecture (`260-arch.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md`):** Agentic loop inside `OpenAICompatibleAgent._run_agentic_loop` (structured for future lift-out). Tool descriptor protocol: name, description, JSON Schema parameters, `cwd`-injecting factory, async executor returning `ToolResult(content, is_error)`. Process-level tool registry (`register`/`lookup`/`materialize`). Core tools: `read_file`, `write_file` (CWD-scoped), `bash` (CWD working directory; network/env/fork unrestricted at this stage — documented scope). Reuses existing `AgentConfig.allowed_tools` field with non-SDK semantics; empty by default, opt-in per pipeline step. Max-iterations guard + character-count token-budget threshold. Streaming contract: intermediate turns DEBUG-logged only; final turn streams normally. Arch review (GLM-5.1, CONCERNS) addressed in same session: F001 false "no network" claim fixed; F002–F008 covered by new Technical Considerations subsections (descriptor protocol, cwd injection, async-first interface, token budget, streaming contract, content+tool_calls co-occurrence).

**Slice plan (`260-slices.non-sdk-agent-tool-use-openai-compatible-agentic-loop.md`):** 5 slices. Critical path: 261 (tool registry + core tools, Effort 2/5) → 262 (agentic loop, Effort 3/5) → 263 (dispatch wiring + YAML surface, Effort 2/5). Deferred: 264 (CF MCP bridge), 265 (review/summary coverage).

**Decision:** Initiative 260 shelved pending completion of initiative 240 (4 slices remaining: 246–249). Will resume 260 after 240 is closed.

## 20260504

### Slice 245: Pool-Resolution Classification Policy and Mid-Run Session Construction — Complete

Commit `be0138c`. 10 files changed, 947 insertions.

**Delivered:**
- `PoolClassificationPolicy` enum (`LAZY`/`STRICT`) in `classification.py`; `PipelineClassification` stores policy; `needs_persistent_session` evaluates `POOL_UNCERTAIN` against policy — LAZY skips it, STRICT counts it.
- `classify_pipeline()` gains optional `policy=PoolClassificationPolicy.LAZY` param.
- `PipelineDefinition.auth_policy: str | None` and `PipelineSchema.auth_policy` with validator (accepts `"lazy"`, `"strict"`, or `None`).
- `execute_pipeline()` gains `pool_policy` param; mid-run lazy hook connects `SDKExecutionSession` just before the first step whose candidate statically resolves to an SDK alias. `_step_needs_sdk()` and `_connect_lazy_session()` are private helpers.
- `LazySessionConnectError` exception carries step name; caught in `_run_pipeline_sdk` which prints a user-facing red message with `--strict` guidance and raises `typer.Exit(1)`.
- `DispatchAction._dispatch` guard: when `sdk_session is None` and the resolved alias has an explicit `'sdk'` profile (pool selected an SDK alias at runtime), returns FAILED with `--strict` hint. `None` alias_profile (no explicit profile) still routes through the one-shot agent safely.
- `sq run --strict` flag; YAML `auth_policy: strict` support; policy resolution precedence: LAZY → YAML strict → CLI `--strict`.
- `PERSISTENT_SESSION_STEP_TYPES` renamed public (was `_PERSISTENT_SESSION_STEP_TYPES`) to avoid pyright `reportPrivateUsage`.

**Tests:** `tests/cli/commands/test_run_pipeline_lazy.py` (new, 18 tests); expanded `test_classification.py` (+12 tests); `test_schema.py` (+4 tests); `test_dispatch.py` (1 updated). 1836 total passing, 0 new failures. ruff/pyright clean (3 pre-existing pyright errors from slice 244 unchanged).

**Key design decision (implementation):** Dispatch guard uses `alias_profile == ProfileName.SDK` (not `is_sdk_profile(alias_profile)`) because `is_sdk_profile(None)` returns True but `None` profile means "one-shot agent, safe without session". Only an explicit `'sdk'` profile signals that a pool selected a true SDK alias requiring a persistent session.

### Slice 243: Resolution Pre-Scan — Phase 6 Implementation Complete

Commit `e838898`. Changed files: `src/squadron/pipeline/classification.py` (new, 235 lines), `src/squadron/pipeline/resolver.py` (added `cascade_candidates()`; refactored `resolve()` to consume it), `tests/pipeline/test_classification.py` (new, 28 tests).

**`ModelResolver.cascade_candidates(action_model, step_model) -> tuple[str | None, ...]`** — returns the ordered cascade inputs (cli_override, action_model, step_model, pipeline_model, config_default) with no alias resolution and no pool selection. `resolve()` now iterates `cascade_candidates()` internally, making cascade ordering single-source. Existing 11 resolver tests pass unchanged.

**`classification.py`** — `classify_pipeline(definition, resolver, pool_backend) -> PipelineClassification`. Walks `definition.steps`; for each model-dispatching step (`dispatch`, `review`, `summary`, `compact`), calls `resolver.cascade_candidates()`, picks first non-None, then dispatches: non-pool candidate → `resolve_model_alias()` + `is_sdk_profile()` → `SDK_REQUIRED` or `NON_SDK`; pool candidate → walks `pool.models` statically → all-SDK collapses to `SDK_REQUIRED`, all-non-SDK to `NON_SDK`, mixed → `POOL_UNCERTAIN`. Non-model steps skipped; `step_index` preserves original pipeline position. Two failure modes raise `ClassificationError` explicitly: empty cascade and pool candidate without backend. `PipelineClassification` derives `needs_persistent_session` (dispatch/summary/compact SDK or pool-uncertain), `needs_one_shot_claude` (review SDK or pool-uncertain), and `shape` (`claude_required_persistent`, `claude_required_one_shot`, `claude_free`).

**Test coverage (28 tests):** spy-backend verification (T1), cascade ordering and resolve-consumes-candidates patch guard (T3), all 7 property isolation tests (T5), 9 non-pool path tests including step-index and F002 regression guards (T7), 5 pool path tests with zero-select assertions (T9), idempotency/side-effect-freeness regression (T10). ruff/pyright clean; full suite +28 new passing tests.

No executor changes. Pre-existing 2 failures in `test_compact_compose_integration` are unrelated and pre-date this slice.

### Slice 243: Resolution Pre-Scan — Phase 5 Task Breakdown Complete

Created [243-tasks.resolution-pre-scan.md](project-documents/user/tasks/243-tasks.resolution-pre-scan.md) (267 lines, 12 tasks). Task sequence: T1 creates test infrastructure (`SpyPoolBackend`, definition/resolver builders) before any implementation. T2 adds `ModelResolver.cascade_candidates()` and refactors `resolve()` to consume it (single-source cascade, resolves review F001). T3 tests `cascade_candidates` and the resolver refactor. T4 defines the dataclasses (`StepClass`, `PipelineShape`, `ClassificationError`, `StepClassification`, `PipelineClassification`) with the three `@property` methods. T5 tests the properties in isolation — includes direct F002 regression guard (`test_needs_one_shot_claude_false_for_sdk_dispatch_only`). T6–T7 implement and test the non-pool path. T8–T9 implement and test the pool path (pool-collapsing logic + `SpyPoolBackend` zero-select assertions). T10 adds the idempotency/side-effect-freeness regression test. T11 is the quality-gate and commit task. T12 closes the slice. No open questions; design is unambiguous.

### Slice 243: Resolution Pre-Scan — Phase 4 Slice Design Revision (review CONCERNS addressed)

Slice review at [243-review.slice.resolution-pre-scan.md](project-documents/user/reviews/243-review.slice.resolution-pre-scan.md) returned `CONCERNS` with two findings; both addressed in-place in the slice design (frontmatter `reviewIteration: 2`, `dateUpdated: 20260504`). **F001 (cascade duplication):** earlier draft proposed three read-only properties (`cli_override`, `pipeline_model`, `config_default`) on `ModelResolver` and reproduced the cascade ordering inside the classifier — leaving cascade logic in two places with a known divergence risk. Replaced with a single `ModelResolver.cascade_candidates(action_model, step_model) -> tuple[str | None, ...]` method returning the ordered cascade *inputs* (no alias resolution, no pool selection). `resolve()` is refactored in the same change to consume the new method internally so the two paths cannot drift; added `test_cascade_candidates_returns_ordered_inputs` and `test_resolve_consumes_cascade_candidates` regression guards. The "Resolver attribute coupling" risk is dropped (resolved by design). Non-goal updated: "no new *selection-performing* resolver entrypoint" (the side-effect-free accessor is permitted; selection is the prohibition). **F002 (`needs_one_shot_claude` semantics drift):** earlier draft defined the predicate as "any SDK-resolved or pool-uncertain step" — broader than arch §Envisioned State point 2, which scopes it to steps that route through the provider registry's one-shot ClaudeSDKAgent path. Tightened to: SDK-resolved review steps ∪ SDK-resolved dispatch-via-agent steps (the second set is empty in practice post-slice-242, included for arch-correctness). Added two new tests — `test_one_shot_excludes_persistent_session_steps` (dispatch+summary all Claude → `needs_one_shot_claude=False`, the direct F002 regression guard) and `test_one_shot_excludes_non_sdk_review`. Success criterion #4 expanded with explicit mixed-pipeline rows. Test count moved from ~14 to ~16. Five PASS findings (side-effect contract documentation, conservative pool default, failure-mode enumeration, scope discipline, 180-band boundary) acknowledged; no design changes for those.

### Slice 245: Pool-Resolution Classification Policy and Mid-Run Session Construction — Task Breakdown Complete

**Completed:** Phase 5 task breakdown.

**Documents created:**
- `project-documents/user/tasks/245-tasks.pool-resolution-classification-policy-and-mid-run-session-construction.md` — 19 tasks across: enum addition, `PipelineClassification` policy field, `classify_pipeline` default change, `auth_policy` YAML field (`PipelineSchema` + `PipelineDefinition`), `execute_pipeline` mid-run hook + helpers, connect-failure UX, `--strict` CLI flag, policy resolution, existing test audit, build/format, and closeout.

**Key task notes:**
- T7: `PipelineSchema` has `extra="forbid"` — `auth_policy` must be added as a declared field; validator rejects anything other than `None`/`"lazy"`/`"strict"`.
- T9: `_step_needs_sdk` ignores pool candidates (returns `False`) — hook fires only on statically confirmed SDK steps.
- T11: connect failure → run state `failed` + re-raise → `_run_pipeline_sdk` catches and prints red message.
- T15: existing pool-uncertain tests relied on the old conservative default; they need `policy=STRICT` annotations or assertion updates.

**Pending:** Phase 6 (implementation). No open questions.

---

### Slice 245: Pool-Resolution Classification Policy and Mid-Run Session Construction — Design Complete

**Completed:** Phase 4 slice design.

**Documents created/updated:**
- `project-documents/user/slices/245-slice.pool-resolution-classification-policy-and-mid-run-session-construction.md` — slice design
- `project-documents/user/architecture/240-slices.pipeline-auth-boundary-flexibility.md` — slice plan entry 5 updated with design link and revised policy framing

**Design summary:**
- **Lazy is the default.** Session not constructed at startup for pool-uncertain pipelines. `--strict` CLI flag (and `auth_policy: strict` pipeline config key) opts into eager upfront connection.
- `PoolClassificationPolicy` enum (`lazy` / `strict`) in `pipeline/classification.py`; default is `LAZY`.
- `classify_pipeline` gains optional `policy` parameter (default `LAZY`); `PipelineClassification` stores the policy used.
- `needs_persistent_session`: under `LAZY`, `POOL_UNCERTAIN` does not force session construction; only statically-confirmed `SDK_REQUIRED` steps do.
- Mid-run hook in `execute_pipeline` (arch §5a): fires on first confirmed-SDK step when `sdk_session is None`; all subsequent steps reuse the same session. Hook is policy-agnostic (dead path under strict mode since session is pre-constructed).
- Auth-failure UX: connect failure mid-run → `failed` run state + clear message; runtime pool selects SDK with no session → `FAILED` step result with `--strict` remediation hint.
- 12 new tests planned across `test_run_pipeline_lazy.py` and `test_classification.py`. Existing pool-uncertain tests need policy annotation update.

**Pending:** Phase 5 (task breakdown) and Phase 6 (implementation). No open questions; design is self-contained.

---

### Slice 244: Conditional Persistent Session Construction — Implementation Complete

**Completed:** Phase 6 implementation (commit c939fb2, branch `244-slice.conditional-persistent-session-construction`)

**Files changed:**
- `src/squadron/cli/commands/run.py` — Added `pool_backend: PoolBackend | None = None` param to `_run_pipeline`; added guard replacing unconditional `DefaultPoolBackend()`. In `_run_pipeline_sdk`: lifted `DefaultPoolBackend()` construction, added `_classify_resolver` (no `on_pool_selection`), added `classify_pipeline` call with `ClassificationError` handler, added INFO/DEBUG logging of classification shape, added session gate (`if classification.needs_persistent_session`). Added `_logger = logging.getLogger(__name__)`.
- `tests/cli/commands/test_run_pipeline_sdk.py` — New test file: 11 tests covering T3 (fallback), T6 (classification gate: all 6 scenarios), T7 (resume path: 2 scenarios).
- `tests/pipeline/test_sdk_wiring.py` — Updated 2 tests to mock `classify_pipeline`/`DefaultPoolBackend`/`ModelResolver` for `needs_persistent_session=True` (tests verify connect/disconnect lifecycle; mock classification is correct because those tests are about lifecycle, not classification).

**Design decisions confirmed during implementation:**
- `on_pool_selection` callback needs `state_mgr`/`_run_id` (initialized inside `_run_pipeline`), so the classification resolver `_classify_resolver` is built without a callback — classification is side-effect-free and never calls `pool_backend.select()`.
- `typer.Exit` raises `click.exceptions.Exit`, not `SystemExit` — tests use `pytest.raises(typer.Exit)` with `exc_info.value.exit_code == 1`.
- Tests run inside Claude Code session (`CLAUDECODE` env var set), so all `_run_pipeline_sdk` tests patch `_resolve_execution_mode` to bypass the session guard.
- Pre-existing failures: `tests/pipeline/test_compact_compose_integration.py` (2 tests) were already failing on main before this slice; not introduced here.

**Audit (T9):** `sdk_session=None` guards confirmed present in `compact.py:62`, `summary.py:149`, `summary.py:218`. No changes needed.

**Test results:** 1806 passing, 2 pre-existing failures (compact compose, unrelated), 0 new failures.

---

### Slice 244: Conditional Persistent Session Construction — Task Breakdown Complete

**Completed:**
- Created `user/tasks/244-tasks.conditional-persistent-session-construction.md` (11 tasks, 192 lines)

**Task structure:**
- T1: Branch setup
- T2: Add optional `resolver`/`pool_backend` params to `_run_pipeline` (backward-compatible)
- T3: Test fallback path (no params supplied)
- T4: Lift `pool_backend`/`resolver` construction into `_run_pipeline_sdk`; wire `on_pool_selection`
- T5: Add `classify_pipeline` call and session gate in `_run_pipeline_sdk`
- T6: Tests for classification gate (T1–T5, T8 from design — non-SDK, SDK, pool-uncertain, ClassificationError, connect failure)
- T7: Tests for resume path (T6, T7 from design)
- T8: Intermediate commit (ruff + pyright + pytest gate)
- T9: Audit `sdk_session=None` correctness for summary/compact (belt-and-suspenders verification)
- T10: Final validation and commit
- T11: Documentation and slice closeout

**Key design note in tasks:** `on_pool_selection` callback depends on `state_mgr`/`_run_id`, which are initialized inside `_run_pipeline`. T4 explicitly flags that the callback must be attached after `state_mgr` is known — implementer must set `resolver._on_pool_selection` inside `_run_pipeline` when `resolver is not None`, or add a setter. Classification never fires pool selection (side-effect-free), so the callback is safe to attach late.

**Status:**
- Task breakdown complete and ready for Phase 6 (Implementation).

---

### Slice 244: Conditional Persistent Session Construction — Design Complete

**Completed:**
- Created `user/slices/244-slice.conditional-persistent-session-construction.md`
- Updated slice plan entry 244 in `240-slices.pipeline-auth-boundary-flexibility.md` with design link

**Key design decisions:**
- Classification runs inside `_run_pipeline_sdk` after `definition` is loaded and `resolver` is constructed — before any session work.
- `pool_backend` and `resolver` are constructed in `_run_pipeline_sdk` and threaded into `_run_pipeline` as optional params; `_run_pipeline`'s internal fallback construction is preserved for callers that don't supply them.
- `POOL_UNCERTAIN` steps take the conservative-pessimistic path (session constructed); lazy opt-in is slice 245.
- `ClassificationError` → `typer.Exit(1)` with a clear message; not an unhandled exception.
- Resume re-classifies from current YAML + alias state; seeding path unchanged (runs only when `sdk_session is not None`).
- Three observable shapes fully established: `claude_required_persistent`, `claude_required_one_shot`, `claude_free`.

**Status:**
- Design ready for Phase 5 (Task Breakdown).

---

## 20260503

### Slice 243: Resolution Pre-Scan — Phase 4 Slice Design Complete

Authored design at [243-slice.resolution-pre-scan.md](project-documents/user/slices/243-slice.resolution-pre-scan.md). Slice introduces a new `src/squadron/pipeline/classification.py` module exposing `classify_pipeline(definition, resolver, pool_backend) -> PipelineClassification`. The classifier walks `PipelineDefinition.steps`, reproduces the resolver's five-tier cascade in read-only form (so it can inspect candidates *before* selection commits), and emits a `StepClassification` per model-dispatching step (`dispatch`, `review`, `summary`, `compact`). Non-pool candidates resolve via `resolve_model_alias` (pure dict lookup); pool candidates classify structurally by walking `ModelPool.models` and applying `is_sdk_profile` to each — never invokes `pool_backend.select()`, never advances 180-band selection state. Two pipeline-level booleans derived per arch §Envisioned State point 2: `needs_persistent_session` (union over `dispatch`/`summary`/`compact` SDK-resolved steps, *excluding* reviews — they route through one-shot ClaudeSDKAgent), and `needs_one_shot_claude` (informational, any-step union). Three pipeline shapes surface: claude_required_persistent, claude_required_one_shot, claude_free. Conservative pool-uncertain default hard-coded for this slice; lazy policy is slice 245's job. Adds three read-only properties on `ModelResolver` (`cli_override`, `pipeline_model`, `config_default`) so the classifier reads via clean public surface, not name-mangled attrs. Failure modes: misconfigured step (cascade yields no candidate) raises `ClassificationError` at planning time; pool candidate without backend likewise. Side-effect-freeness contract documented and asserted by a spy-backend test (zero `select()` calls for double classification). Slice ships the classifier and 14 unit tests only — no executor wiring; slice 244 will gate `SDKExecutionSession` construction on `classification.needs_persistent_session`. Slice-plan entry now carries the design pointer; slice plan `status` advanced to `in_progress`. Risk: Low; Effort: 2/5.

### Slice 242: Profile-Aware Dispatch Router (pure CLI) — Phase 6 Implementation Complete

Commit `0dbe41a`. Changed files: `src/squadron/pipeline/actions/dispatch.py`, `tests/pipeline/actions/test_dispatch_routing.py`, `tests/pipeline/actions/test_dispatch_session.py`.

**What changed:**
- `dispatch.py`: Added `is_sdk_profile` import from `squadron.providers.profiles`. Added `_resolve_model(context)` helper that extracts the `action_model / step_model / resolver.resolve(...)` cascade. Rewrote `_dispatch` with three-branch profile-aware routing: no session → agent path; session + non-SDK profile → agent path; session + SDK or None profile → session path. `_dispatch_via_session` and `_dispatch_via_agent` retain their own inline resolve cascade unchanged.
- `test_dispatch_routing.py` (new): Five routing tests (T5a–T5e): session+non-SDK→agent, session+None→session, session+sdk→session, no-session→agent, mixed-pipeline-per-step. All pass.
- `test_dispatch_session.py`: Updated one assertion from `assert_called_once_with` to `assert_any_call` to reflect the documented double-resolve (routing call in `_dispatch`, then branch call in `_dispatch_via_session`).

**T10 verification walkthrough:** Unit tests T5a–T5e verify routing logic in isolation. Live end-to-end steps (Step 1 minimax via pure-CLI, Step 2 default Claude regression, Step 3 mixed pipeline) require a configured minimax alias and Claude auth; these are environment-dependent and were not executed in this session. Steps should be run manually before tagging a release. Step 4 (IDE axis unchanged) is covered by existing slice-170 tests.

**Quality gates:** ruff format clean, ruff check clean, pyright 0 errors. Full suite: 1769 passed (baseline 1764 + 5 new).

### Slice 242: Profile-Aware Dispatch Router (pure CLI) — Phase 5 Task Breakdown Complete

Created [242-tasks.profile-aware-dispatch-router-pure-cli.md](project-documents/user/tasks/242-tasks.profile-aware-dispatch-router-pure-cli.md) (222 lines, 10 tasks). Three implementation tasks: T1 adds the `is_sdk_profile` import, T2 extracts the `_resolve_model` helper, T3 rewrites `_dispatch` with the profile-aware three-branch routing. T4 verifies existing tests stay green. T5 creates a new dedicated `tests/pipeline/actions/test_dispatch_routing.py` with five routing cases (session+non-SDK→agent, session+None-profile→session, session+explicit-sdk→session, no-session→agent, mixed-pipeline per-step); `test_dispatch.py` at 412 lines would be too large for 5 additional tests. T6–T8 are quality gates (targeted test run, ruff+pyright, full suite expecting 1769+ passed). T9 commits; T10 closes out the slice. No open questions; design is unambiguous.

### Slice 242: Profile-Aware Dispatch Router (pure CLI) — Phase 4 Slice Design Complete

Authored design at [242-slice.profile-aware-dispatch-router-pure-cli.md](project-documents/user/slices/242-slice.profile-aware-dispatch-router-pure-cli.md). The slice closes the pure-CLI mirror of slice 170: when `sq run … --param model=<non-sdk>` runs through `_run_pipeline_sdk`, today's `DispatchAction._dispatch` routes purely on `context.sdk_session is not None` and silently misroutes non-SDK aliases to `session.set_model(...)` on a Claude session — the prompt is dispatched to Claude under the non-SDK model id. Design extracts a small `_resolve_model(context)` helper, branches on `is_sdk_profile(alias_profile)` (now imported from `squadron.providers.profiles` per slice 241), and routes non-SDK profiles to `_dispatch_via_agent` even when a persistent session exists. Default Claude path (profile `None` per the slice-241 `None → True` contract) and explicit `sdk` profiles continue through `_dispatch_via_session` unchanged. No session-construction changes — the persistent session still connects at startup; conditional construction is slice 244. Test plan covers five routing cases (session+non-SDK → agent, session+default-None → session, session+explicit-sdk → session, no-session → agent, mixed-pipeline per-step). Risk: Low; Effort: 2/5. Slice-plan entry materialized with the (242) index and design pointer; frontmatter dateUpdated bumped.

### Slice 241: is_sdk_profile Predicate Re-Homing — Phase 6 Implementation Complete

Mechanical refactor landed in commit 393af52: `is_sdk_profile()` now lives in `src/squadron/providers/profiles.py` (alongside `get_profile()`), with `__all__` updated to export it. Two production callers (`pipeline/prompt_renderer.py:23`, `pipeline/actions/summary.py:11`) and one test (`tests/providers/test_profiles.py`) import from the new home; the old definition and its predicate-test are deleted from `pipeline/summary_oneshot.py` and `tests/pipeline/test_summary_oneshot.py`. The 9-case parametric test (None, "sdk", 5 registered non-SDK profiles, "unknown-profile", "") covers the documented contract; `None` → `True` semantics preserved per arch iteration 3 (renderer/summary call sites depend on this; pre-scan layer in slice 243 will operate only on resolved profiles and never pass `None`). All 4 grep sentinels green: zero hits for the old import path, zero residual references in `summary_oneshot.py`, expected hits at the new home. Quality gates: ruff format clean, ruff check clean, pyright zero errors, full suite 1764 passed (one net-new test). Verification walkthrough re-run end-to-end against the landed commit; observed output matches documented expectations across steps 1–5 and 7. Foundation in place for slices 242–248. Note: the slice-plan summary line at `240-slices.pipeline-auth-boundary-flexibility.md:35` still narrates the original `None` → `False` contract; appended a pointer to the arch iteration-3 contract rather than rewriting the plan body.

---

## 20260502

### Slice 241: is_sdk_profile Predicate Re-Homing — Phase 5 Task Breakdown

Task file created at `user/tasks/241-tasks.is-sdk-profile-predicate-re-homing.md` (10 tasks, 158 lines). Sequenced as: T1 add predicate to `providers/profiles.py` → T2 add parametric test at new home → T3 update `prompt_renderer.py` import → T4 update `actions/summary.py` import → T5 remove predicate from `test_summary_oneshot.py` → T6 delete old definition from `summary_oneshot.py` → T7 grep sentinel verification → T8 quality gates → T9 commit → T10 slice closeout. Investigation confirmed `tests/providers/test_profiles.py` already exists (no `is_sdk_profile` tests yet) and `tests/providers/` directory is present — no `__init__.py` creation needed.

---

## 20260501

### Slice 241: is_sdk_profile Predicate Re-Homing — Phase 4 Slice Design

Drafted slice design at [241-slice.is-sdk-profile-predicate-re-homing.md](project-documents/user/slices/241-slice.is-sdk-profile-predicate-re-homing.md). Foundation slice for the 240-band initiative: promotes `is_sdk_profile()` from [pipeline/summary_oneshot.py:19-24](src/squadron/pipeline/summary_oneshot.py#L19-L24) to [providers/profiles.py](src/squadron/providers/profiles.py) with an explicit contract (returns `True` for `None` or `"sdk"`, `False` for every other registered profile and unknown strings; no I/O, no auth probe, pure read of the profile-name enum). Investigation found only **2 production importers** (not 3 as the slice plan estimated) — slice 170 added the predicate to the dispatch *renderer* but not the dispatch *router* (router branch is slice 242's work). 6-file mechanical refactor: new definition + new test file + 2 caller import updates + old definition removal + old test removal. No re-export shim — all callers update in the same PR. Slice plan entry updated with design-complete pointer.

### Initiative 240: Pipeline Auth-Boundary Flexibility — Phase 3 Slice Plan

Drafted slice plan at [240-slices.pipeline-auth-boundary-flexibility.md](project-documents/user/architecture/240-slices.pipeline-auth-boundary-flexibility.md). 8 slices in two groups: 1 foundation (241 predicate re-homing) + 7 features (242 dispatch router pure-CLI fix, 243 resolution pre-scan, 244 conditional persistent session construction, 245 pool-resolution policy + mid-run construction, 246 `sq run --explain` diagnostics CLI, 247 documentation, 248 adversarial test matrix). Each slice maps directly to addressed-CONCERN territory from the iteration-2 arch review: 241 → F006 ownership, 243 → F003/F004/F005 pre-scan correctness, 244 → F001 split classification + F007 resume policy, 245 → F002 mid-run mechanism. Conservative shipping order: 241 → 242 → 243 → 244 → 245 → 246 → 248 → 247. Aggressive parallel order with {242, 243} and {244, 246} as parallelizable groups also documented.

### Slice 170: Profile-Aware Dispatch Model Routing — Phase 6 Implementation Complete

All 15 tasks (T1–T15) implemented and committed. 1763 tests passing, zero ruff/pyright errors.

**What changed:**

- **`_render_dispatch` branches on resolved profile** (`prompt_renderer.py`): SDK/None profiles keep the current in-session path (`model_switch`, no command). Non-SDK profiles emit a `sq _dispatch-run` command with `--prompt-file {tmp_path}`, `--model`, `--profile`, and any non-internal params forwarded as `--param` flags. `model_switch` and `command` are mutually exclusive.
- **`one_shot_dispatch` helper extracted** (`dispatch.py`): Factored the agent-spawn sequence out of `_dispatch_via_agent` into a public module-level async function. `_dispatch_via_agent` becomes a thin caller. Token metadata was not consumed downstream and was dropped in the refactor.
- **`sq _dispatch-run` hidden subcommand added** (`cli/commands/dispatch_run.py`, `app.py`): Reads prompt from `--prompt-file`, resolves profile via `ModelResolver` if `--profile` omitted, calls `one_shot_dispatch`, prints to stdout. Errors always go to stderr before exit 1. Hidden from `sq --help`.
- **`commands/sq/run.md` dispatch section updated**: Branched on `command` field presence — non-SDK path writes temp file, replaces `{tmp_path}`, runs via Bash, cleans up. SDK/in-session path is the else branch (unchanged wording).
- **SDK synthetic-error fix** (`sdk_session.py`): In `SDKExecutionSession.dispatch`, after `translate_sdk_message`, checks `isinstance(sdk_msg, ResultMessage) and sdk_msg.is_error` before appending content. Raises `ProviderAPIError("SDK reported is_error=True: ...")` on the error path. Existing `_CLI_ERROR_PREFIX` text check in `_check_cli_error` preserved as backstop.

**Key decision:** `_one_shot_dispatch` renamed to `one_shot_dispatch` (no leading underscore) because pyright strict mode treats leading-underscore module-level names as private and the function is intentionally cross-module.

**Commits:** `9942161` refactor, `6000c42` feat renderer, `062191e` feat subcommand, `7545a7e` feat run.md, `32bc7f6` fix sdk error

**Issues logged:** None.

**Next:** Initiative 240 slice plan (pipeline auth-boundary flexibility), or Phase 6 on any pending slice.
Format: `## YYYYMMDD` followed by brief notes (1-3 lines per session).  This file differs from
CHANGELOG.md, in that this file is written from implementor perspective where CHANGELOG.md is
written from user perspective.

---

### Slice 170: Profile-Aware Dispatch Model Routing — Phase 5 Task Breakdown

Task file created at `user/tasks/170-tasks.profile-aware-dispatch-model-routing.md` (15 tasks, 360 lines).
Tasks cover: `_one_shot_dispatch` extraction from `_dispatch_via_agent`, `_render_dispatch` profile
branch fix, new hidden `sq _dispatch-run` subcommand, `commands/sq/run.md` dispatch-section update,
SDK `is_error` synthetic-error detection fix, full suite + type-check, verification walkthrough, and
slice closeout. Inline `--prompt` intentionally omitted from `_dispatch-run`; file-only via
`--prompt-file` matching the established convention for multi-KB assembled context.

---

## 20260428

### Initiative 240: Pipeline Auth-Boundary Flexibility — Phase 2 Architecture (review iteration 2)

Reviewed via slice-style review at [240-review.arch.pipeline-auth-boundary-flexibility.md](project-documents/user/reviews/240-review.arch.pipeline-auth-boundary-flexibility.md) (verdict CONCERNS, 6 concerns + 1 note). All addressed in arch doc revision: classification split into two distinct properties (`needs_persistent_session` vs `needs_one_shot_claude`) so review-only-with-SDK-reviews pipelines no longer pay persistent-session connect cost (F001); mid-run lazy-connect mechanism sketched in Envisioned State step 5a after verifying `ActionContext` is constructed per-action in `pipeline/executor.py:785` (F002); pre-scan pool handling clarified as static structural query against pool's alias list with no 180 API dependency (F003); pre-scan resolver instance must match runtime cascade including `--param` overrides (F004); resolver side-effect-freedom verified by inspection of `models/aliases.py:resolve_model_alias` and stated as documented contract (F005); `is_sdk_profile()` ownership promoted to `providers/profiles.py` with explicit contract (F006); resume policy under changed pipeline definitions stated explicitly — current resolution wins (F007).

### Initiative 240: Pipeline Auth-Boundary Flexibility — Phase 2 Architecture

Drafted [240-arch.pipeline-auth-boundary-flexibility.md](project-documents/user/architecture/240-arch.pipeline-auth-boundary-flexibility.md). Promoted from in-flight slice-170 work after recognising the actual scope: today's pipeline executor unconditionally constructs a `ClaudeSDKClient` at startup regardless of pipeline content, and the dispatch router has no profile branch — together these mean (a) any `sq run` from pure CLI requires Claude auth, (b) `sq run … --param model=<non-sdk>` for a dispatch step silently fails. Architecture names two distinct SDK-touching paths (persistent `SDKExecutionSession` vs. registry-spawned one-shot `ClaudeSDKAgent`) and treats them as separate auth surfaces, both intentional. Initiative owns: per-step auth classification via resolution pre-scan, conditional persistent-session construction, profile-aware dispatch routing in pure-CLI mode, pool-resolution classification policy (conservative-vs-lazy), and diagnostic CLI surface. Explicit non-goals: until-loop convergence, fan-out/fan-in aggregation, intra-loop compaction policy, conversation-vs-override-instruction routing for findings — all 180-band. One-shot Claude subprocess pooling documented as known cost, not optimised. Anticipated 6–10 slices. Initiative entry added to [001-initiative-plan.squadron.md](project-documents/user/project-guides/001-initiative-plan.squadron.md) at index 240; cross-initiative dependency line added.

## 20260427

### Slice 170: Profile-Aware Dispatch Model Routing — Phase 4 Design

Drafted slice design at [170-slice.profile-aware-dispatch-model-routing.md](project-documents/user/slices/170-slice.profile-aware-dispatch-model-routing.md). Mirrors slice 164's profile-aware fix on the dispatch axis: `_render_dispatch` will branch on resolved profile and emit a runnable `sq dispatch …` command for non-SDK profiles (currently emits "in-session work" regardless of profile, so `/sq:run … --param model=minimax` from inside Claude Code silently runs the dispatch in the IDE session instead of routing to minimax). New `sq dispatch` CLI surface factored from `_dispatch_via_agent`. Independent in-scope fix: `_dispatch_via_session` will surface SDK `is_error=True` messages as `ProviderAPIError` instead of returning the error JSON as response text. Slice plan entry added to [140-slices.pipeline-foundation.md](project-documents/user/architecture/140-slices.pipeline-foundation.md) at index 170 (Feature Slices, after 166); plan `dateUpdated` bumped.

### Slice 904: Review-Finding Location Required — Complete

Resolves [issue #10](https://github.com/ecorkran/squadron/issues/10): review findings inconsistently cite a `location:` field, especially on PASS findings. The field is the dedup key for upcoming ensemble review (slices 182, 189), so it has to land first.

**Four coordinated changes:**

1. **Template prompts** (`src/squadron/data/templates/{code,slice,arch,tasks}.yaml`). All four review templates now require `location:` on every finding (PASS included), with a per-template precedence ladder (e.g. code: `path:line` → `path:start-end` → `path#symbol` → `path` → `unverified`). The explicit `unverified` token is the "I don't know" escape hatch — the prompt tells the model that hallucinated paths are worse than `unverified`. Commit `88bf32e`.

2. **Soft-fail parser normalization** (`src/squadron/review/parsers.py`). New `_normalize_location()` helper: missing locations and placeholder values (`-`, `global`, `n/a`, `none`, empty) become `"unverified"` with a WARNING that names the finding ID, title, template, and verdict. Tightened `_CATEGORY_RE` and `_LOCATION_RE` to `[ \t]*` (was `\s*`) so an empty value tag cannot bleed onto the next body line. Threaded `verdict` and `template_name` through `_extract_findings`, `_lenient_extract_findings`, and the synthesized fallback for consistent triage signals. Commit `059818a`.

3. **Diff-membership check** (code reviews only). `_check_diff_membership()` runs after extraction; for each finding citing a path, WARN if the path is not in the diff under review. Skips `UNVERIFIED_LOCATION` findings. Wired up in `review_client.py` via a new `_run_git_diff_filenames()` helper that calls `git diff --name-only` with the same exclude-pattern handling as `_run_git_diff()`. Commit `846a8a1`.

4. **Path-existence check** (all template types). `_check_path_existence()` runs after extraction; for each finding citing a path and a `cwd`, WARN if `(cwd / path).exists()` is false. Cheap defense against hallucinated filenames in arch/slice/tasks reviews where there's no diff. Same commit as (3).

**Hallucination defense, three layers, all WARNING-only:** prompt-side `unverified` token (self-documenting in rendered review); path-existence (catches made-up filenames everywhere); diff-membership (stricter check where we have an authoritative file set). Hard-rejection deferred until real-world false-positive data is available.

**Tests:** 11 new soft-fail tests (`TestLocationSoftFail`) + 6 diff/path tests (`TestLocationDiffMembershipAndPathExistence`). One existing test (`test_no_location_returns_none`) renamed/updated — the old `None` behavior is now `"unverified"` by design. Full review suite: 315 passing. Full project: 1742 passing.

**T11/T12 manual verification with `minimax/minimax-m2.7`:**
- T11 code review against the slice 902 diff (commit `a4679b6`): 8 PASS findings, 8/8 had `location:` populated with real `path:line-range` values. Zero `unverified`, zero hallucinations, zero parser WARNINGs. Saved to [902-review.code.pipeline-verbosity-passthrough-v-vv.md](project-documents/user/reviews/902-review.code.pipeline-verbosity-passthrough-v-vv.md).
- T12 arch review against `900-arch.maintenance-and-refactoring.md`: 5 findings (3 CONCERN, 2 NOTE), 5/5 had `location:` populated. **All 5 fired path-existence WARNINGs** because the model emitted bare filenames (`900-arch.maintenance-and-refactoring.md`) without the `project-documents/user/architecture/` prefix. The check did exactly its job — the cited paths really don't exist relative to `cwd`. The arch prompt could be tightened later to require project-relative paths; for slice 904 the WARNING is the correct surfacing.

**Caveat captured:** the code prompt does not require `category:` (only arch.yaml does), so code-review findings still fall back to `category: uncategorized` in structured output. Pre-existing, not a 904 regression. If/when ensemble review needs category-based dedup, that's a follow-up.

## 20260426

**slice: devlog-9**
- cf-op-0: PASS
- cf-op-1: PASS
- cf-op-2: PASS
- dispatch-3: PASS
- review-4: PASS (verdict: PASS)
- checkpoint-5: PASS
- commit-6: PASS
- summary-0: PASS
- compact-0: PASS

### Slice 902: Pipeline Verbosity Passthrough — Complete
- Commits: `69aefbf` fix(pipeline): thread verbosity through render_step_instructions; `4c1c011` fix(sq:run): peel -v/-vv flags from arguments, pass to sq run.
- `_render_review` now accepts `verbosity: int = 0` (keyword-only). Hard-coded `-v` replaced with conditional: nothing at 0, `-v` at 1, `-vv` at ≥2.
- `_build_action_instruction` and `render_step_instructions` forward `verbosity`. Both `_handle_prompt_only_init` and `_handle_prompt_only_next` in `run.py` pass `verbose` count from typer option.
- `/sq:run` slash command updated: three-step peel (scan → capture → remove) for `-v`/`-vv`/`--verbose`; Step 0 template includes `<verbose_flags>`.
- Tests: existing assertion updated (no `-v` at default); 3 new parametrized verbosity tests added. Full gate: 1723 passed, ruff+pyright clean.
- Verification walkthrough updated with actual output and `command: null` gotcha (use `a.get('command') or ''`).

### Slice 902: Pipeline Verbosity Passthrough — Task Breakdown Complete
- Created `902-tasks.pipeline-verbosity-passthrough-v-vv.md` (12 tasks, 105 lines).
- Tasks cover: `_render_review` verbosity param + conditional emit, test update + new parametrized tests, `_build_action_instruction` forwarding, `render_step_instructions` param, two `run.py` call sites, slash command peel in `run.md`, two commits, final gate.

### Slice 902: Pipeline Verbosity Passthrough — Design Complete
- Created slice design for issue #9: pipeline review commands hard-code `-v`, `/sq:run` swallows trailing flags.
- Two changes: thread `verbosity` param through `render_step_instructions` → `_render_review` (replacing hard-coded `-v`), and update `/sq:run` slash command to peel `-v`/`-vv` from `$ARGUMENTS`.
- Default changes from implicit `-v` to silent (0); `-v`/`-vv` opt in explicitly.

## 20260425

### Slice 901: Pipeline Code-Review Diff Injection — Implementation Complete

Shipped three coordinated fixes for issue #11 (pipeline code reviews silently UNKNOWN).

**UNKNOWN fails closed** (`checkpoint.py`): Added `"UNKNOWN"` to `ON_FAIL` and `ON_CONCERNS`
threshold sets. `verdict is None` (no prior review) is unchanged — only the
parsed-but-unparseable case fails closed. 8 new unit tests in `test_checkpoint.py`.

**`slice` forwarded through `expand()`** (`phase.py`, `review.py`): `PhaseStepType.expand()` and
`ReviewStepType.expand()` now include `"slice"` in the emitted review action dict. Phase steps
use `"{slice}"` placeholder; review steps forward `cfg.get("slice")`. 4 new tests.

**Declarative template-input registry** (`src/squadron/review/template_inputs.py`): New module
with `TemplateInputSpec` dataclass and `TEMPLATE_INPUTS` dict covering `slice`, `tasks`, `arch`,
and `code` templates. `code` entry calls `resolve_slice_diff_range` to inject `inputs["diff"]`.
`_resolve_slice_inputs` in `pipeline/actions/review.py` rewritten to delegate entirely to
`resolve_template_inputs`. 9 registry tests + 6 `_resolve_slice_inputs` regression tests + 2
end-to-end integration tests.

Gates: 1719 tests pass, ruff clean, pyright 0 errors.

### Slice 901: Pipeline Code-Review Diff Injection — Task Breakdown Complete

Task file created at `user/tasks/901-tasks.pipeline-code-review-diff-injection.md`
(13 tasks, test-with pattern, 4 commits). Covers three coordinated fixes for
issue #11: UNKNOWN fails closed in checkpoint thresholds; `slice` forwarded
explicitly through `PhaseStepType.expand()` and `ReviewStepType.expand()`; and
the per-template `match` in `_resolve_slice_inputs` replaced by a declarative
`TEMPLATE_INPUTS` registry that auto-injects `inputs["diff"]` for the `code`
template via `resolve_slice_diff_range`.

**P6: devlog-2**
- cf-op-0: PASS
- cf-op-1: PASS
- cf-op-2: PASS
- dispatch-3: PASS
- review-4: PASS (verdict: UNKNOWN)
- checkpoint-5: PASS
- commit-6: PASS
- compact-0: PASS

### Slice 194: Loop Step Type for Multi-Step Bodies — Implementation Complete

Shipped `LoopStepType` in `src/squadron/pipeline/steps/loop.py` with full `validate()` (7 rules, nested-loop ban on both sub-field and step-type forms) and `expand()` returning `[]`. Added `_execute_loop_body` to `executor.py` and wired it as the `StepTypeName.LOOP` dispatch branch (ahead of the existing `loop:` sub-field else branch). Reused all slice-149 machinery unchanged: `_parse_loop_config`, `LoopCondition`, `ExhaustBehavior`, `evaluate_condition`, `_unpack_inner_steps`, `_execute_step_once`. Strategy field parsed but stubbed with same warning as the single-step path — slice 184 will implement convergence strategies for both forms simultaneously. Added 25 new tests across three test files; fixed 11 pre-existing integration-test failures caused by `slice.yaml` having grown from 6 to 10 steps in a prior commit. All 1690 tests pass, pyright zero errors.

## 20260424

### Slice 194: Loop Step Type for Multi-Step Bodies — Phase 4 Slice Design Complete

Added new slice 194 to `180-slices.pipeline-intelligence.md` (Feature Slices) and authored slice design at `project-documents/user/slices/194-slice.loop-step-type-for-multi-step-bodies.md`. Top-level `loop:` step type with a `steps:` body, symmetric with `each:`. Reuses existing `LoopConfig` / `LoopCondition` / `evaluate_condition` / `ExhaustBehavior` from slice 149's executor — no new loop semantics. v1 bans both nested-loop forms (sub-field on inner step, and inner `loop:` step type) at validation time. Existing single-step `loop:` sub-field unchanged; inline `review:` sub-field on phase steps stays as phase-only sugar. Prerequisite for slice 184 to drive realistic dispatch-then-review convergence rather than re-asking the same review against an unchanged artifact. Effort 2/5. Status: not-started, ready for Phase 5 (task design).

### Slice 194: Loop Step Type for Multi-Step Bodies — Phase 5 Task Breakdown Complete

Authored `project-documents/user/tasks/194-tasks.loop-step-type-for-multi-step-bodies.md` (275 lines, 21 tasks). Tasks follow the test-with pattern — each implementation task is paired with its test task before moving on. Sequence: enum addition → test stub → `LoopStepType` (validate + expand) → validation tests → expand/registration tests → `_execute_loop_body` executor branch → dispatch wiring → registration import → six integration tests covering pass-on-iteration-1, retry-to-PASS-on-N, three exhaustion modes, transient inner failure, checkpoint short-circuit, nested-loop ban (both forms) → regression check on existing single-step loop suite → authoring example in `example.yaml` → schema/loader smoke test → final lint/types/test gate → slice completion + DEVLOG entry. Slice review (verdict FAIL from kimi-k2.6) addressed: F001 rejected on slice-182 precedent (same registry-mediated step-type addition pattern, shipped in same 180 plan); F002 accepted via new "Deferred Interactions with 184/185/188" section that punts multi-step convergence/escalation/persistence cross-product to those downstream slices. Status: in-review, ready for Phase 6 implementation.

### Slice 167: Per-Action Model Override Convention — Design Complete

**Completed:**
- Created `user/slices/167-slice.per-action-model-override-convention.md`
- Enhanced existing stub with full design: data flow, cascade position, code
  change, YAML/params interaction (no loader change required), test list,
  verification walkthrough, and documentation target
- Key technical decision: `params["review_model"]` is a separate params channel
  from `params["model"]`; step-level `review.model: X` wires into `params["model"]`
  (unchanged), while `--param review_model=Y` writes to the new key — no conflict
- `docs/PIPELINES.md` Model Resolution section is the documentation target
- First adopter: `ReviewAction` only; future actions adopt independently

**Design decisions recorded:**
- `review_model` (underscore) is the canonical convention key matching Python dict
  and `--param` syntax; existing `review-model` (hyphen) YAML param continues to
  work via step-level wiring unchanged
- No loader change needed — the two channels are naturally separate by how params
  merge in the executor

**Status:**
- Phase 4 complete. Ready for Phase 5 (task breakdown).

---

### Slice 154: Prompt-Only Loops — Design Complete

**Completed:**
- Verified `user/slices/154-slice.prompt-only-loops.md` against current codebase — all technical assumptions confirmed accurate
- Codebase verification: all 5 executor functions to be reused (`_parse_source`, `_SOURCE_REGISTRY`, `resolve_placeholders`, `_unpack_inner_steps`, `_resolve_str`) exist and are module-level; all 3 CLI handlers exist; `ExecutionMode` enum, `EachStepType`, `StepTypeName.EACH` in place
- Schema v4 confirmed current; design's v4→v5 bump plan is correct
- Implementation targets confirmed absent (as expected): `LoopContext` model, `loop_context` field on `RunState` and `StepInstructions`
- Updated frontmatter status from `not_started` to `in_progress`
- Note: Phase 5 task file (`154-tasks.prompt-only-loops.md`) was created in a prior session (20260410) but reverted (`39c575d`) — Phase 5 needs to be re-executed

**Status:**
- Phase 4 complete. Design verified and current. Ready for Phase 5 (task breakdown).

---

### Slice 154: Prompt-Only Loops — Phase 4 Design Refreshed

**Completed:**
- Refreshed `user/slices/154-slice.prompt-only-loops.md` against current codebase state (post slices 153–169)
- Updated data models to use Pydantic `BaseModel` (matching `RunState` pattern, was dataclass)
- Schema version bump: v4 → v5 (was v1 → v2 in original design; actual codebase is now at v4)
- Clarified `StateManager` interaction: `first_unfinished_step` remains loop-unaware; loop logic lives in CLI handlers (`_handle_prompt_only_init`, `_handle_prompt_only_next`, `_handle_step_done`)
- Added `LoopContext` model with cached `items` list for deterministic resume
- Documented reuse of executor internals: `_SOURCE_REGISTRY`, `_parse_source`, `resolve_placeholders`, `_unpack_inner_steps`
- Updated out-of-scope references to reflect completed slices (160 checkpoints, 169 compact dispatch)
- Updated slice plan entry from "Design preserved" to "Design Complete"

**Design decisions (unchanged from original, validated against current code):**
- Loop iterations flattened into instruction stream — callers are loop-unaware
- Step names follow `{inner_step_name}-each-{item_index}` pattern
- Flattened step names go into `completed_steps`; parent `each` step recorded on loop completion
- Source items cached in LoopContext for deterministic resume

**Status:**
- Phase 4 complete. Ready for Phase 5 (task breakdown).

---

## 20260422

### Slice 169: Compact Action — SDK Capability Dispatch — Implementation Complete

Implemented `CompactAction` end-to-end as a dedicated pipeline action (separate from `SummaryAction`).
`CompactStepType.expand()` now emits `("compact", ...)` instead of `("summary", emit=[rotate])`.
Two execution branches: when `context.sdk_session is not None`, delegates to existing
`SDKExecutionSession.compact()` rotate flow (unchanged); when None, dispatches `/compact` via
`claude_agent_sdk.query()` and awaits `SystemMessage(subtype="compact_boundary")`, logging
`pre_tokens`/`trigger`/`compacted_at` to `ActionResult.outputs`. Default 120s timeout.
`SummaryAction` gained `restore: true` mode — reads most recent prior `summary` result from
`prior_outputs` and seeds it into the SDK session via `seed_context()`.

**Design simplification during implementation:** T2 (SessionCapabilities), T3 (capability probe),
and T4 (/model investigation) were dropped after PM discussion. The original design called for
reading `slash_commands` from the SDK init message and branching on capability presence. Simplified
to: assume `/compact` is available (SDK v0.0.20+ guarantees it); branch on `sdk_session` presence
instead. `SessionCapabilities` dataclass and `ActionContext.capabilities` field were not added.

**Added:** `src/squadron/pipeline/actions/compact.py` (CompactAction, ~165 lines);
`src/squadron/data/pipelines/test-compact-compose.yaml`; `_render_compact` builder in
`prompt_renderer.py` (emits `trigger: "/compact"` for prompt-only). **Modified:**
`CompactStepType` (new config surface: `model`, `instructions`); `SummaryAction._execute_restore`;
`ActionType` enum (added `COMPACT`); executor imports `actions.compact` to trigger registration;
existing integration test registries gained `"compact": action` entries.

**Tests:** 16 new in `test_compact.py` (action unit); 12 rewritten in `steps/test_compact.py`
(StepType); 3 new in `test_compact_compose_integration.py` (prompt-only + true-CLI compose,
dead-slash-text regression); 6 new restore-mode tests in `test_summary.py`; 1 new registry
integration assertion. **Total: 1665 passing, pyright clean, ruff clean.**

**Docs:** `docs/PIPELINES.md` — compact step section rewritten with environment matrix and
compose pattern; summary section documents `restore: true`; actions table updated.
`CHANGELOG.md` — `[Unreleased]` section describes added capability, restore mode, and
migration note for pipelines that relied on compact's implicit summary. No existing pipeline
YAMLs required migration (audit in T9 found all `compact:` uses were pure context-reduction,
not summary-capture dependencies).

**Commits:** `126a0bf` (CompactAction + step wiring), `e988261` (summary restore mode),
`b5ac797` (compose integration tests + pipeline YAML), `6293ff0` (docs).

---

## 20260415

### Slice 182: Fan-Out / Fan-In Step Type — Implementation Complete

Implemented `fan_out` step type end-to-end. New files: `src/squadron/pipeline/steps/fan_out.py`,
`src/squadron/pipeline/intelligence/fan_in/{__init__,protocol,reducers}.py`. Executor changes:
`_execute_fan_out_step` added to `executor.py`, dispatch branch wired after `each` in
`execute_pipeline`, import triggers added for `fan_out` module and `fan_in.reducers`.
29 new tests (15 step/integration + 14 reducer); 1635 total passing. Pyright and ruff clean.
SDK-session guard wording matches user-facing contract exactly. Slice 189 can register
`merge_findings` reducer at import time with no fan-out infra changes.

**Commits:** `1e138a7` (reducers), `25fff72` (FanOutStepType), `fc60e7b` (executor), `812f2a2` (cleanup)

---

### Slice 182: Fan-Out / Fan-In Step Type — Design + Tasks Complete

Created slice design `user/slices/182-slice.fan-out-fan-in-step-type.md` and task file
`user/tasks/182-tasks.fan-out-fan-in-step-type.md` (14 tasks, 202 lines). Design covers
`FanOutStepType`, `_execute_fan_out_step` in executor, `FanInReducer` protocol, and
`collect`/`first_pass` built-in reducers. Key decisions: reuse `resolver.resolve()` N times
for pool multi-select (no new `PoolBackend` method needed), explicit SDK-session guard (raise
error rather than silently interleave), failure fast-fail before reducer. Unblocks slice 189
(Ensemble Review). Ready for Phase 6 (Implementation).

---

### Slice 168: `sq review code` — Slice Implementation Review — Complete

Added commit-message grep as step 3 in `resolve_slice_diff_range` (`src/squadron/review/git_utils.py`). `sq review code <N>` now resolves a useful diff range for slices merged directly to main with no surviving branch. Single-commit edge case handled via `{sha}^!` syntax. `--fan N` flag added to `sq review code` as a placeholder for slice 182 fan-out; warns and proceeds. 12 new tests (1598 total). All passing, pyright clean.

**Commit:** `b5df568` feat: resolve slice impl diff via commit grep

---

## 20260414

### Slice 181: Pool Resolver Integration and CLI — Implementation Complete

Wired the slice 180 pool infrastructure into the resolver, state, and CLI. Key implementation
decisions: `PoolBackend` protocol and `DefaultPoolBackend` added to new `backend.py` (slice 180
shipped only module-level functions); resolver construction sites are in `run.py` (not
`executor.py`, which accepts a pre-built resolver as a param); `state.py` `_load_raw` uses a
`_SUPPORTED_SCHEMA_VERSIONS = {3, 4}` set to accept both v3 (back-compat) and v4 (new). At
SDK-mode call site, resolver must be built after `init_run` so `run_id` is in scope for the
`on_pool_selection` closure. Pre-existing schema v1 run files produce harmless
"Skipping unreadable state file" log warnings from `list_runs()` — expected, not a bug.
1589 tests passing; 5 commits.

Refactor: consolidated `sq pools show <name>` into `sq pools list [name]` — optional name arg
produces detail view (members + recent selections). Pattern matches `sq models list`. 949 tests
passing; 6 commits. Bump to 0.4.0 — start of significant new functionality (pool-based model
selection).

---

## 20260413

### Slice 180: Model Pool Infrastructure and Strategies — Implementation Complete

Implemented full pool infrastructure in `src/squadron/pipeline/intelligence/pools/`:
5 source files (`models.py`, `protocol.py`, `strategies.py`, `loader.py`, `__init__.py`),
`src/squadron/data/pools.toml` (3 built-in pools), 5 test files (71 new tests, all green).
One bug found during implementation: `tomli_w.dumps()` returns `str` not `bytes` — fixed
with `write_text()` instead of `write_bytes()`. No regressions in the 1478 existing tests.
Patch order for `get_all_aliases` in tests: must patch `squadron.models.aliases.get_all_aliases`
(the source) since loader imports it lazily inside functions.

### Slice 180: Model Pool Infrastructure and Strategies — Design Complete (Phase 5)

Task breakdown complete at `project-documents/user/tasks/180-tasks.model-pool-infrastructure-and-strategies.md`
(28 tasks, 420 lines). Covers: package scaffolding, test infrastructure, data models (`ModelPool`,
`SelectionContext`, `PoolState`), `PoolStrategy` protocol, four built-in strategies (`random`,
`round-robin`, `cheapest`, `weighted-random`), strategy registry, round-robin state persistence,
built-in `pools.toml`, pool loader with alias validation, `select_from_pool` wrapper, and public
API surface. Test-with pattern applied throughout; 5 intermediate commits defined.
Implementation is slice 181's blocker for pool resolver integration.

---

## 20260412

### Slice 191: Dispatch Summary Context Injection — Complete (Phase 6)

Fixed the root cause of empty/hallucinated non-SDK summary output: one-shot
models received only the compaction template instructions with zero pipeline
context. Added `src/squadron/pipeline/summary_context.py` — a pure function
`assemble_dispatch_context` that iterates `prior_outputs` and assembles prior
dispatch responses, review verdicts/findings, and `build_context` stdout into
a delimited context block prepended to non-SDK summary instructions. SDK path
(has session history) is completely unmodified. 13 unit tests, 2 integration
tests, all 623 pipeline tests green, ruff clean. Verified with a live minimax
run: model correctly summarized the dispatch response and accurately reported
it had no slice 191 content (the test pipeline used an unrelated prompt).

Also added `dispatch` as a first-class YAML step type (previously only an
internal `ActionType`). Accepts optional `prompt` and `model`; expands to a
single dispatch action. Required to make Verification Walkthrough scenarios
runnable directly. 8 new tests.

Fixed a `/sq:summary --restore` hallucination bug (v0.3.13): CLI only emitted
the selected filename to stderr in the multi-match case; single-match was
silent, causing the model to use the nearby example value verbatim. Always emit
`Using: {name}` to stderr; slash command now parses it explicitly and errors if
absent. Added "Hallucination traps in prompts" rule to CLAUDE.md.

---

### Slice 191: Dispatch Summary Context Injection — Phase 5 Task Breakdown Complete

**Completed:**
- Created `user/tasks/191-tasks.dispatch-summary-context-injection.md` (171 lines, 7 tasks)
- Tasks cover: new `summary_context.py` module (T1), unit tests for assembler (T2),
  integration into `_execute_summary()` (T3), integration tests (T4), full verification
  and commit (T5), end-to-end verification (T6), slice completion (T7)
- Implementation note captured: `ActionType` has no `COMPACT` entry; compact steps
  expand to `"summary"` action type — the `match/case` only needs `ActionType.SUMMARY`

**Status:**
- Phase 5 complete. Ready for Phase 6 (implementation).

---

### Slice 191: Dispatch Summary Context Injection — Phase 4 Design Complete

**Completed:**
- Created `user/slices/191-slice.dispatch-summary-context-injection.md`
- New module `pipeline/summary_context.py` with `assemble_dispatch_context()` — pure function that extracts content from `prior_outputs` by action type (dispatch responses, review findings, build_context text, prior summaries) and assembles a delimited context block
- Integration point: `_execute_summary()` prepends context block to instructions for non-SDK profiles only; SDK path unchanged
- Dependencies: slices 161 (summary step) and 164 (profile-aware routing), both complete

**Design decisions:**
- Context prepended to instructions (not a separate system message) — keeps `capture_summary_via_profile` interface unchanged across providers
- Full artifact contents injected, not metadata summaries — the summary model's job is to summarize
- No YAML configuration — context injection is unconditional for non-SDK profiles
- `match/case` on `ActionType` enum for extraction dispatch, not string labels

**Status:**
- Phase 4 complete. Ready for Phase 5 (task breakdown).

---

## 20260411

### Slice 166: Compact and Summary Unification — Complete (Phase 6)

Completed the runtime unification of `compact` and `summary`. Deleted
`CompactAction`, `ActionType.COMPACT`, `_render_compact`, and both
compact action test files (~780 lines net deleted). Moved template
helpers (`CompactionTemplate`, `load_compaction_template`,
`render_instructions`, `_parse_template`) from `actions/compact.py`
into a new `src/squadron/pipeline/compaction_templates.py` module;
updated all five consumers to import from the new home.

Rewrote `CompactStepType.expand()` to return `("summary", {...,
"emit": ["rotate"]})` instead of `("compact", ...)`. Rewrote
`StateManager._maybe_record_compact_summaries` gate to fire on
`action_type="summary"` with a successful rotate emit entry in
`emit_results` — the one real risk in the slice. Removed the
`### compact` section from `commands/sq/run.md` and refreshed the
installed copy.

Prompt-only smoke test confirmed: `compact-1` step in P6 now renders
as `action_type="summary"`, `emit=["rotate"]`, no `/compact [` in
any command field. All 1455 tests green, pyright clean, ruff clean.

No surprises. Pipeline YAML files (P6, slice, tasks, app, example)
all validate cleanly — `compact:` keyword still parses.

### Slice 166: Compact and Summary Unification — Task Breakdown Complete (Phase 5)

Broke slice 166 into a single task file at
`project-documents/user/tasks/166-tasks.compact-and-summary-unification.md`
(26 tasks, 6 commit checkpoints, ~510 lines). Kept it as one file after
weighing against the 450-line guideline — splitting added more friction
than it solved for this size.

Task groups follow the migration order from the slice doc's
Implementation Notes: (1) survey call sites, (2) extract template
helpers into a new `compaction_templates.py` module and update every
import before touching runtime code, (3) rewrite
`CompactStepType.expand()` and the `_maybe_record_compact_summaries`
gate with paired tests, (4) delete `_render_compact` and add a
prompt-only renderer smoke test, (5) delete `CompactAction`,
`ActionType.COMPACT`, and compact-specific tests, (6) clean up
`commands/sq/run.md`, (7) pipeline validation + E2E smoke tests in
both prompt-only and SDK modes + grep verification + full quality
gate, (8) arch doc verification and slice/DEVLOG wrapup.

Test-with pairing honored throughout: each rewrite (step expand,
state gate, `_render_compact` removal) has its tests as the immediate
successor task. The state gate test specifically covers the slice's
one real risk — summary action with rotate emit must still populate
`RunState.compact_summaries` for resume-with-reinjection.

Next: Phase 6 implementation.

### Slice 166: Compact and Summary Unification — Review PASS (1 concern addressed)

Review verdict PASS (glm5). Eight findings: seven pass, one note, one concern.

Concern F004 (documentation-sync): `140-arch.pipeline-foundation.md` lists
compact as a distinct action type in two places flagged by the reviewer, plus
two additional locations I found when auditing: action registry table (line
106), detailed compact-action subsection (lines ~246-251), action type diagram
(line 514), and `actions/compact.py` package entry (line ~549). Addressed by
adding a new §"Architecture Document Updates" section to the slice design with
a concrete change checklist and explicit out-of-scope list (compaction as
concept, `compact:` YAML examples, and step-type-layer references all stay).
Arch doc updates land during Phase 6 implementation alongside the code changes,
keeping doc and code in sync rather than drifting during the implementation
window. New success criterion #11 verifies the arch doc is updated.

Review: `project-documents/user/reviews/166-review.slice.compact-and-summary-unification.md`.

### Slice 166: Compact and Summary Unification — Design Complete

Added slice 166 to `140-slices.pipeline-foundation.md` and designed it at
`project-documents/user/slices/166-slice.compact-and-summary-unification.md`.

Finishes the abandoned refactor from slice 161. Today compact and summary are
two half-merged code paths: SDK mode already delegates compact to summary
internally, but prompt-only mode still renders a broken `/compact [...]` slash
command string. This breaks P6 and every pipeline using `compact:`.

Design: rewrite `CompactStepType.expand()` to emit a summary action with
`emit=[rotate]` instead of a compact action. Delete `CompactAction`,
`ActionType.COMPACT`, `_render_compact`, the compact test class, and the compact
section of `commands/sq/run.md`. `compact:` YAML continues to parse — it becomes
a pure two-word alias with no unique code below the step-expansion layer.

One real risk: `state.py::_maybe_record_compact_summaries` is gated on
`ar.action_type == "compact"`. After the refactor no action is compact-typed, so
the gate must switch to "summary action whose emit includes rotate" to preserve
resume-with-reinjection. Called out explicitly in the design with its own
targeted integration test. No schema version bump — field names and shapes
unchanged.

Template helper functions (`load_compaction_template`, `render_instructions`)
must be moved out of `actions/compact.py` before the file can be deleted, since
the summary action imports them.

Priority: implement before continuing 180-band work — P6 is currently broken in
prompt-only mode.

Marked slice plan 140 frontmatter `status: in_progress` (was `complete`). Slice
plan entry numbering updated: 166 added as item 23, Integration Work item 152
bumped from 23 to 24.

---

### Slice 181: Pool Resolver Integration and CLI — Design Complete

Created `project-documents/user/slices/181-slice.pool-resolver-integration-and-cli.md`.

Design extends `ModelResolver` with `pool_backend` and `on_pool_selection` callback params.
`_resolve_pool()` delegates to `PoolBackend.select()` (slice 180), then resolves the returned
alias through the existing alias registry — transparent to all action handlers. `RunState` gains
`pool_selections: list[dict]` with schema version bump to 4 (backwards-compatible). New
`sq pools` CLI (list / show / reset) follows the `sq models` pattern. Executor wires up
`PoolLoader.load()` and the logging callback when building `ModelResolver`.

---

### Slice 160: Interactive Checkpoint Resolution — Implementation Complete

Phase 6 complete. Three files changed:

- `executor.py`: Added `CheckpointResolution(StrEnum)`, `CheckpointDecision` dataclass,
  `_is_interactive()`, `_prompt_checkpoint_interactive()`. Modified `_execute_step_once`
  checkpoint detection block to call the handler; EXIT path returns PAUSED (unchanged),
  Accept/Override inject `override_instructions` into `merged_params` and continue.
- `actions/dispatch.py`: `_resolve_prompt` now reads `override_instructions` from
  `context.params` and prepends a delimited block when present.
- `prompt_renderer.py`: `_render_checkpoint` now describes all three options per trigger
  type. `run_id` injected into `render_params` so the resume command is correct.

All 1477 tests pass. `pyright` clean. No `RunState` schema change (stays v3).

---

### Slice 160: Interactive Checkpoint Resolution — Design Complete

Created `project-documents/user/slices/160-slice.interactive-checkpoint-resolution.md`.

Design confines the change to three files: `executor.py` (interactive handler +
`CheckpointResolution`/`CheckpointDecision` types), `actions/dispatch.py` (pick up
`override_instructions` from params), and `prompt_renderer.py` (enhanced checkpoint
instruction text). The Accept/Override path injects instructions into `merged_params` and
continues in-place; the Exit path is unchanged. No `RunState` schema bump required.
Updated slice plan entry 18 with Design Complete pointer.

---

### CHANGELOG rewrite — user perspective

Rewrote all CHANGELOG entries to answer "what can I do / what bug is fixed"
rather than listing internal class names, module paths, and slice refs.
Net: 338 lines removed, changelog is now readable without source context.

---

### Slice 164 implementation complete: profile-aware summary model routing

**Slice 164 — Phase 6 complete.**

- **What changed:**
  - New module `src/squadron/pipeline/summary_oneshot.py`:
    `is_sdk_profile()` predicate and `capture_summary_via_profile()` —
    near-copy of the ~40 relevant lines from `run_review_with_profile()`,
    review-specific paths stripped.
  - `_execute_summary()` now branches on resolved profile: SDK path
    (profile `None` or `"sdk"`) keeps `sdk_session.capture_summary()`;
    non-SDK path dispatches through the provider registry via
    `capture_summary_via_profile()`.
  - Rotation emit + non-SDK profile fails fast with a descriptive error
    at execution time (resolver not available at schema-validation time).
  - `_render_summary()` in `prompt_renderer.py` emits `model_switch` for
    SDK profiles and `command` (runnable `sq _summary-run …`) for
    non-SDK profiles.
  - New hidden CLI subcommand `sq _summary-run` (registered alongside
    `sq _summary-instructions`) as the CLI surface for prompt-only
    non-SDK summary execution.
  - `CompactAction` inherits the fix for free via the shared
    `_execute_summary()` helper.
  - 1452 tests pass; pyright and ruff clean.

- **OQ1 resolved:** Option A — new hidden `sq _summary-run` subcommand,
  matching the `_summary-instructions` naming convention. The subcommand
  name uses leading underscore (`_summary-run`) per project convention.

- **Surprises:**
  - `compact.py` imports `_execute_summary` inside the method body
    (deferred import), so tests must patch
    `squadron.pipeline.actions.summary._execute_summary`, not
    `squadron.pipeline.actions.compact._execute_summary`.
  - `--validate` in `sq run` only calls schema-level `validate()` — the
    rotate+non-SDK profile check fires at execution time, not validation
    time (resolver is execution-time only). Slice doc updated with
    caveat.

- **Pipelines unblocked:** Any pipeline summary step can now use cheap
  external models (minimax, gemini-flash, local) via their respective
  profiles. The only restriction is `emit: [rotate]`, which remains
  SDK-only.

---

### Slice 164 design + tasks; CI fix; phase pipelines now write summary files

**v0.3.8 release.**

- **Slice 164 (Profile-Aware Summary Model Routing)** — Phase 4 design
  and Phase 5 task breakdown complete via `/sq:run P4 164` and
  `/sq:run P5 164`. Both phases reviewed PASS by minimax-m2.7. Slice
  routes the summary action through the provider registry for non-SDK
  profiles, mirroring `run_review_with_profile()`. New module
  `summary_oneshot.py` houses `capture_summary_via_profile()` and the
  `is_sdk_profile()` predicate. 17 implementation tasks in
  `164-tasks.profile-aware-summary-model-routing.md`. Implementation
  deferred (Phase 6 not yet started).
- **CI fix** — `prompt_renderer.py:270` had a `dict[str, object]`
  narrow that pyright couldn't infer through; added
  `cast(list[object], emit_raw)` after the `isinstance(list)` check.
  Seven consecutive `main` builds had been red on this same error.
- **Phase pipelines now write summary files** — after re-running
  `sq install-commands` to refresh stale `summary.md` and `run.md`
  skills, discovered that all five phase pipelines (P1, P2, P4, P5, P6)
  emit only `[stdout, clipboard]` and never `[file]` — so slice 163's
  default-file-path branch had nothing to write to. Added `file` to
  every P*.yaml emit list. `/sq:summary --restore` now works
  end-to-end after any phase pipeline run.

**Commits:**
- `5d7ab9d` docs: add slice 164 profile-aware summary model routing design
- `32fc9e7` fix: cast emit list to satisfy pyright in _render_summary
- `f8c887a` docs: add slice 164 task breakdown
- (this commit) feat: emit pipeline summaries to file + bump to v0.3.8

## 20260410

### Slice 163: Pipeline Run Summary Persistence and Restore — Complete

**Phase 6 (implementation) complete.**

- Closes the "run pipeline in CLI terminal, restore context in VS Code" workflow gap
- Three implementation sites: `emit.py` (default file path), `executor.py` (_project injection), `summary_instructions.py` (--restore), `commands/sq/summary.md` (--restore branch), `commands/sq/run.md` (file-write step)
- Key decision: bare `"file"` in `emit:` YAML list now produces `EmitDestination(kind=FILE, arg=None)` rather than raising; default path is `~/.config/squadron/runs/summaries/{project}-{pipeline}.md`
- `_project` threaded into `ActionContext.params` via `gather_cf_params()` at pipeline init in `executor.py`; falls back to `"unknown"` when CF unavailable; caller-supplied `_project` not overwritten
- 31 new tests added (28 in test_emit.py, 3 in test_executor.py, 5 in test_summary_instructions.py)

**Commits:**
- `51a3342` feat: add default summaries path to emit and thread _project into ActionContext
- `1d6281f` feat: add --restore to /sq:summary and write summary to conventional path in run.md


**tasks: devlog-4**
- cf-op-0: PASS
- cf-op-1: PASS
- cf-op-2: PASS
- dispatch-3: PASS
- review-4: PASS (verdict: UNKNOWN)
- checkpoint-5: PASS
- commit-6: PASS
- compact-0: PASS

### Slice 152: Pipeline Documentation and Authoring Guide — Complete

**Deliverables created:**
- `docs/PIPELINES.md` — authoritative pipeline authoring guide (Quick Start, YAML Grammar, Step Type Catalog, Action Type Catalog, Model Resolution, Configuration Surface, Built-in Pipelines, Custom Pipeline Walkthrough, Prompt-Only Mode)
- `README.md` — added `## Pipelines (sq run)` section with quick-start and link to guide

**Discrepancies found during T1 verification (documented, not propagated from slice design):**
- `slice` pipeline has 2 params (`slice`, `review-model`); slice design table listed only `slice`
- `tasks`, `P5`, `P6` each have 3 params including `model`; design table showed 2
- `example.yaml` inline comment shows stale project path (`.squadron/pipelines/`); loader uses `project-documents/user/pipelines/` — guide uses loader path
- `app.yaml` is a WIP pipeline (same description as design-batch, has TODO comment) — excluded from docs

**Commits:**
- `4056c7b` docs: add pipeline authoring guide
- `5460177` docs: add sq run section to README

### Slice 163: Pipeline Run Summary Persistence and Restore — Phase 5 Task Breakdown Complete

**Completed:**
- Created `user/tasks/163-tasks.pipeline-run-summary-persistence-and-restore.md` (158 lines, 14 tasks)
- Tasks cover: source verification (T1), emit.py changes (T2–T4), _project threading (T5–T6), commit (T7), summary_instructions --restore (T8–T9), summary.md --restore branch (T10), run.md alignment (T11), commit (T12), verification (T13), slice completion (T14)
- Test-with pattern: T4 follows T3, T6 follows T5, T9 follows T8
- Review: PASS (minimax). One NOTE addressed: T11 updated to remove stale `_precompact-hook` reference (removed in slice 162); uses `cf status` for project name resolution instead

**Status:**
- Phase 5 complete. Ready for Phase 6 (implementation).

---

### Slice 163: Pipeline Run Summary Persistence and Restore — Phase 4 Design Complete

**Completed:**
- Created slice design at `user/slices/163-slice.pipeline-run-summary-persistence-and-restore.md`
- Added slice overview to `140-slices.pipeline-foundation.md` as entry 23 (index 163)
- Fixed `run.md` clipboard bug: summary action handler now uses `pbcopy`/`xclip`/`wl-copy` via Bash instead of telling the user to copy manually

**Design decisions:**
- Default `emit: [file]` path: `~/.config/squadron/runs/summaries/{project}-{pipeline}.md` (latest-only overwrite)
- Restore via `/sq:summary --restore` — reads most recent summary for current project, no run-id needed
- Project name resolved from CF via `gather_cf_params()` (existing helper)
- Prompt-only `run.md` handler writes to same conventional path via Bash
- `_project` threaded as internal param through `ActionContext` during pipeline init

**Status:**
- Phase 4 complete. Ready for review, then Phase 5 (task breakdown).

---

### Slice 152: Pipeline Documentation and Authoring Guide — Phase 5 Task Breakdown Complete

**Completed:**
- Created `user/tasks/152-tasks.pipeline-documentation-and-authoring-guide.md` (172 lines, 14 tasks)
- Tasks cover: source artifact verification, `docs/PIPELINES.md` creation (Quick Start, YAML Grammar, Step Type Catalog, Action Type Catalog, Model Resolution, Configuration Surface, Built-in Pipelines, Custom Pipeline, Prompt-Only Mode), README.md update, final verification walkthrough, and DEVLOG
- Verification tasks follow each major section (T1 verifies source before writing; T12 runs the full design walkthrough; T13 verifies README)
- No code changes in this slice — documentation only

**Key notes:**
- T1 (source verification) must be completed before writing documentation — particularly to confirm ActionType enum, registered step types, and built-in pipeline file list match the slice design
- The YAML quoting footgun for parameter placeholders must be prominent in the grammar section
- `test-pipeline.yaml` and `app.yaml` in pipelines/ are not for user documentation; exclude from the built-in pipelines table

**Status:**
- Phase 5 complete. Ready for Phase 6 (Slice Execution).

---

### Slice 154: Prompt-Only Loops — Phase 5 Task Breakdown Complete

**Completed:**
- Created `user/tasks/154-tasks.prompt-only-loops.md` (260 lines, 19 tasks)
- Tasks follow test-with pattern: each implementation task is immediately followed by its tests before the next implementation task
- Commit checkpoints placed after coherent logical units (state model, state manager methods, render function, each CLI handler, integration test, closeout)
- No schema version bump needed — `LoopContext` additive with `None` default on `RunState`
- Key implementation sequence: `LoopContext` model → `StateManager` loop methods → `LoopInstructionContext` + `render_each_step_instructions()` → `executor.py` rename → `_handle_prompt_only_init` → `_handle_prompt_only_next` → `_handle_step_done` → integration test → verification walkthrough

**Status:**
- Phase 5 complete. Ready for Phase 6 (Slice Execution).

---

### Slice 154: Prompt-Only Loops — Design Complete (Refreshed)

**Completed:**
- Recreated slice design document at `user/slices/154-slice.prompt-only-loops.md` (previous version was deleted from working tree)
- Design refreshed to reflect current codebase state: schema v3 (no version bump needed — `LoopContext` is additive with `None` default), existing `CompactSummary` pattern, `ExecutionMode` enum
- Core design unchanged from original: flatten `each` loop iterations into prompt-only instruction stream via `LoopContext` state tracking
- Key implementation points: `LoopContext` Pydantic model on `RunState`, `render_each_step_instructions()` in prompt renderer, loop-aware `--step-done` advancement, cached collection items in state for deterministic resume
- Slice plan entry at `140-slices.pipeline-foundation.md` already has materialized index (154) and design-complete link

**Status:**
- Design complete. Ready for Phase 5 (Task Breakdown).

---

## 20260409

### Slice 162: /sq:summary — Clipboard Summary for Manual Context Reset

**Phase 4 (design) + Phase 5 (task breakdown) + Phase 6 (implementation) complete.**

- Motivated by unreliable `/compact [with instructions]` — user wants deterministic "clear with custom summary" using templates already built for pipeline compaction (slices 157/158)
- Design: slash command `/sq:summary [template]` + hidden `sq _summary-instructions` CLI. Current CC session generates the summary inline; squadron supplies template instructions + clipboard sink.
- Created `pipeline/summary_render.py` with `resolve_template_instructions()` and `gather_cf_params()` — logic salvaged from dead `precompact_hook.py`
- Removed `precompact_hook.py`, `install_settings.py`, and all PreCompact hook install/uninstall logic (dead code since 0.3.3)
- Reuses `compact.template` config key — no new config surface
- Clipboard via shell chain: `pbcopy` → `xclip` → `wl-copy` (Windows deferred)
- All 1400 tests pass, ruff clean, pyright clean
- Post-implementation: removed misleading "do not print to chat" instruction from summary.md — summary appearing in chat is correct and lets user verify before `/clear`; bumped to v0.3.4

## 20260408

**v0.3.3 release — merge, tag, PyPI publish**

- Caught that dispatch fix landed on `test-161-pipeline` instead of `161`; cherry-picked `07881d5` → `210950d`
- Bumped version 0.3.2 → 0.3.3, merged `161-slice.summary-step-with-emit-destinations` → main, tagged `v0.3.3`
- CI: both push and tag runs triggered; `publish` job succeeded; `squadron-ai==0.3.3` live on PyPI
- Verified full pipeline smoke test end-to-end (design → tasks → summary:rotate → design again) on separate branch; discarded test branch
- CHANGELOG restructured: collapsed duplicate `[Unreleased]` sections into proper versioned entries; fixed orphaned `## [Unreleased]` mid-file (was 0.2.7-era content); made entries more concise for human readers
- **Latent bug fixed:** `DispatchAction` — Claude CLI surfaces API errors (e.g. 500) as assistant text with `"API Error:"` prefix; dispatch was returning `success=True`, allowing review/checkpoint to run against a non-existent output file. Added `_check_cli_error()` detection in both session and agent paths.

### Slice 161: Summary Step with Emit Destinations — Complete

**Commits (8 slice commits):**
- `877f1e6` chore: add pyperclip dependency for summary clipboard emit
- `2bbbcb7` feat: add SDKExecutionSession.capture_summary() method
- `1a953ae` feat: add summary= overload to SDKExecutionSession.compact()
- `6f78e1e` feat: add emit destination registry and types
- `76b0e65` feat: add SummaryAction with config validation
- `9b043a7` feat: implement _execute_summary shared helper
- `c613422` feat: wire SummaryAction.execute to shared helper
- `7293394` feat: add SummaryStepType, register summary action+step, validate emit, update test-pipeline

**Delivered:**
- `SDKExecutionSession.capture_summary()` — captures summary without rotating session
- `SDKExecutionSession.compact(summary=...)` — `summary=` overload skips capture phase for reuse
- `emit.py` — `EmitKind` registry with stdout, file, clipboard (pyperclip), rotate destinations
- `actions/summary.py` — `SummaryAction` + `_execute_summary()` shared helper; single capture, multi-destination dispatch; rotate failures fail the action, others log warning
- `CompactAction` SDK path refactored to delegate into `_execute_summary()` with `emit=[rotate]`; `action_type` kept as `"compact"` — state persistence unaffected
- `SummaryStepType` with `emit` validation and `checkpoint:` shorthand (expands to summary + checkpoint action pair)
- `test-pipeline.yaml` updated to use `summary:emit:[rotate]` in place of `compact:`
- 1429 tests passing; pyright clean; ruff clean

**Pending / deferred:**
- T15 manual smoke test (`sq run test-pipeline 154 -vv`) deferred — requires live Claude SDK session; no blockers
- `clear` follow-up (rotate without seeding) not yet filed as a slice; design open question from 161 slice doc

---

## 20260407

**Slices 158, 159: Pipeline plan additions**
Added two new feature slices to `140-slices.pipeline-foundation.md`. Slice 158 (Pipeline Fan-Out / Fan-In Step Type) — general parallel branch infrastructure with pluggable fan-in reducer; ships with identity reducer, consensus reducer is a stub for 160; demonstrates with N>1 reviews against multiple models; foundational for consensus review infrastructure. Slice 159 (Interactive Checkpoint Resolution) — replace pause-and-exit with interactive prompt offering accept/override/exit options; first two avoid the full resume cycle. Both slices need design (Phase 4) before implementation.

**Slice 157: SDK Session Management and Compaction — Design Updated (Phase 4 revision)**
Revised `157-slice.sdk-session-management-and-compaction.md` to address two review concerns: (1) checkpoint resume after compact loses the summary because the previous process's session is gone — fixed by persisting compact summaries in a new keyed `compact_summaries` dict on `RunState` (schema bump v2 → v3); (2) executor-owned re-injection on resume via a new `seed_context()` session method. Keying scheme `{step_index}:{step_name}` is forward-compatible with slice 158 fan-out branches (will extend with `#branch{n}` suffix). Added `CompactSummary` dataclass, `record_compact_summary` state manager method, and `active_compact_summary_for_resume` helper. Re-reviewed task breakdown follows in same session.

**Slice 157: SDK Session Management and Compaction — Task Breakdown Updated (Phase 5 revision)**
Expanded `157-tasks.sdk-session-management-and-compaction.md` from 11 tasks to 18 to cover the design revision: T2/T3 add `CompactSummary` dataclass, schema v3 bump, state manager persistence and lookup helpers; T7 adds `seed_context()` method; T11 wires the compact summary persistence via the executor's `on_step_complete` callback (action stays free of state-manager coupling); T12 implements executor resume injection; T14 adds an automated integration test for the full session rotate flow; T15 adds an automated test specifically for resume-after-compact. T13 (PreCompact hook) retains its investigation-first note. Test-with pattern throughout; 452 lines.

### Slice 157: PreCompact Hook for Interactive Claude Code — Phase 6 Implementation Complete

**Completed:**
- All 15 tasks (T1–T15) in `user/tasks/157-tasks.precompact-hook-for-interactive-claude-code.md` implemented and marked complete.
- New shared module `src/squadron/pipeline/compact_render.py` with `LenientDict` + `render_with_params`, extracted from `actions/compact.py`. Both the compact action and the PreCompact hook consume it.
- New hidden Typer subcommand `sq _precompact-hook` (registered on the top-level app with `hidden=True`). Not listed in `sq --help`; direct invocation still works. Emits the Claude Code `PreCompact` payload on stdout, always exits 0.
- New module `src/squadron/cli/commands/install_settings.py` with `settings_json_path`, `_load_settings`, `_save_settings`, `write_precompact_hook`, `remove_precompact_hook`, and `_is_squadron_entry`. Squadron owns its entry in `.claude/settings.json` via a `_managed_by: "squadron"` marker; third-party hooks are preserved on both install and uninstall.
- `sq install-commands` / `sq uninstall-commands` extended with `--hook-target` option (default `./.claude/settings.json`). Installation is idempotent; uninstall tidies `hooks.PreCompact` and `hooks` keys when they become empty.
- Two new config keys: `compact.template` (default `"minimal"`) and `compact.instructions` (default `None`). Literal wins at resolve time.
- `_gather_params` uses best-effort `ContextForgeClient()` with `os.chdir` context management (the CF client has no `cwd` kwarg — task file's pseudocode was updated in practice to match the real API). Catches `ContextForgeError`, `ContextForgeNotAvailable`, `FileNotFoundError`, `OSError`.
- Empty CF values (e.g. `slice=""` as the current squadron project reports) are **omitted** from params so `{slice}` renders as a literal placeholder rather than empty text — discovered during smoke testing and fixed in T14.
- README updated with "Interactive `/compact` for Claude Code" section.
- Full test suite: 1315 passed, 0 failures. Pyright: 0 errors. Ruff: clean.

**Commits on `157-slice.precompact-hook-for-interactive-claude-code` branch:**
- `feat: add compact.template and compact.instructions config keys`
- `refactor: extract LenientDict and render_with_params to compact_render module`
- `feat: add hidden _precompact-hook subcommand for interactive Claude Code`
- `feat: add settings.json merge helpers for PreCompact hook install`
- `feat: install PreCompact hook entry during sq install-commands`
- `docs: document PreCompact hook and compact config keys`
- `chore: rename hook helpers to public names to satisfy pyright`
- `fix: omit empty CF params so PreCompact hook preserves placeholders`
- `docs: mark slice 157 PreCompact hook for interactive Claude Code complete` (pending)

**Deviations from task file:**
- Renamed module-public helpers from `_write_precompact_hook` / `_remove_precompact_hook` / `_settings_json_path` to non-underscored names because pyright's `reportPrivateUsage` flagged cross-module usage with leading underscores. Functionally identical; names reflect convention more accurately.
- Tests for T3/T4/T5 and the module file itself were combined into one commit because all three helpers live in the same file; splitting would have been artificial.
- Test T14 revealed the CF empty-string behavior, which was fixed in `_gather_params` with a tiny non-destructive change: only populate `slice` and `phase` when truthy.
- Also moved the `patch_config_paths` fixture from `tests/config/conftest.py` up to `tests/conftest.py` so CLI command tests can reuse it.

**Smoke tested (automatable parts):**
- `sq install-commands` writes the expected `.claude/settings.json` shape.
- `sq _precompact-hook` emits valid JSON with `hookEventName == "PreCompact"`.
- `{slice}` placeholder preserved when CF reports empty slice.
- Literal `compact.instructions` override wins over template.
- `sq --help` hides the command; `sq _precompact-hook --help` still works.
- `sq uninstall-commands` cleanly removes the entry.

**Not verified (requires human in the loop):**
- Step 6 of the verification walkthrough: real `/compact` in an interactive VS Code Claude Code session or `claude` CLI. Flagged in the slice design for follow-up. The hook payload schema (`hookSpecificOutput.additionalContext`) is based on Claude Code docs; if it turns out to differ, the fix is a single line in `precompact_hook.py` plus one test update.

**Status:**
- Slice 157 complete. Slice plan `140-slices.pipeline-foundation.md` slot 157 checked off.
- Branch: `157-slice.precompact-hook-for-interactive-claude-code` — ready for merge to `main` pending the human-driven `/compact` smoke test.

---

## 20260406

**Slice 157: SDK Session Management and Compaction — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/157-tasks.sdk-session-management-and-compaction.md`. 11 tasks (T1–T11): capture `session_id` from `ResultMessage` in translation (T1); add `session_id` and `options` fields to `SDKExecutionSession` (T2); pass options into session from `_run_pipeline_sdk` (T3); implement `compact()` session rotate method (T4); remove `configure_compaction()` stub (T5); add `model` field to compact step YAML (T6); wire compact action to call `session.compact()` (T7); register `PreCompact` hook for interactive instruction injection (T8); end-to-end smoke test via test-pipeline (T9); lint/type-check/full suite (T10); closeout (T11). Test-with pattern throughout; commits after each implementation+test pair. Note: T8 includes verification-before-implement note for the `PreCompact` hook return format as that API detail needs confirmation.

**Slice 157: SDK Session Management and Compaction — Design Complete (Phase 4)**
Created `project-documents/user/slices/157-slice.sdk-session-management-and-compaction.md`. Core approach: session rotate compaction at pipeline step boundaries. When compact step executes, switch model to cheap summarizer (e.g. haiku) in the *current* session, query with compact template instructions, capture summary, disconnect, start fresh session seeded with summary. Key insight: summarize in the live session (model has full context) rather than resuming in a new process (loads entire context just to read it). Also wires `PreCompact` hook for interactive `/compact` instruction injection. Adds optional `model` field to compact YAML. Removes unconnected `configure_compaction()` stub from slice 155. Agent SDK investigation confirmed: no `context_management`, no `compaction_control`, no threshold control — session rotate is the only deterministic compaction path. Dependencies: [155, 156]. Effort: 3/5.

## 20260405

**Fix: validate pipeline before execution, not just `--validate`**
`_run_pipeline` now calls `validate_pipeline()` before `execute_pipeline()`, so invalid action parameters (e.g. `checkpoint: concerns` instead of `on-concerns`) are caught with a clear error before execution begins. Previously validation only ran for `--validate` and `--dry-run`. Also added defense-in-depth in `CheckpointAction.execute()` — invalid trigger values now return `ActionResult(success=False)` instead of an unhandled `ValueError`. 1253 tests pass.

**Slice 154: Prompt-Only Loops — Design Complete (Phase 4)**
Created `project-documents/user/slices/154-slice.prompt-only-loops.md`. Slice extends slice 153's prompt-only mode to transparently support `each`/collection loops. Core design: `EachLoopState` dataclass tracks iteration context (current item index, inner step name, cached source query results) persisted in `RunState`; `render_each_step_instructions()` resolves CF source queries on first entry; placeholder resolution enhanced to support `{param.field}` dot-path syntax for item binding; `StateManager` methods `first_unfinished_step()` and `advance_iteration()` handle navigation within/across iterations. To the caller, loops are transparent — each `--next` returns the next instruction in flattened execution order, whether it's a new step or next iteration. Model switching is informational only (slash command handles manually). Technical decisions documented: transparent iteration, params-based item binding, single-depth loops (nesting deferred to 160), convergence strategies stubbed (160 scope). Data flows, state persistence format, and integration points detailed. Ready for Phase 5 (task breakdown) and Phase 6 (implementation). Effort: 2/5, risk: low.

**Slice 156: Pipeline Executor Hardening — Implementation Complete (Phase 6)**
Implemented all 14 tasks. `ExecutionMode` StrEnum added to `state.py`; `RunState` schema bumped to v2 with `execution_mode` field (default `SDK` for forward-compat with v1 files); `init_run` gains `execution_mode` param and `pipeline_name.lower()` normalisation. `_run_pipeline` gains `run_id` param (skips `init_run` when provided); `_run_pipeline_sdk` gains `run_id` param and forwards with `execution_mode=SDK`. Both `--resume` and implicit resume paths rewritten to dispatch via `match state.execution_mode:` — no string literals. `_handle_prompt_only_init` records `PROMPT_ONLY`. `load_pipeline` and `discover_pipelines` normalise names to lowercase; CLI `run()` normalises at `--validate`, `--dry-run`, `--prompt-only`, and standard execution entry points. `--status` output includes `Mode:` line. 1251 tests pass; pyright zero errors; ruff clean. Branch: `156-slice.pipeline-executor-hardening`.

### Slice 154: Prompt-Only Loops — Design Complete

**Completed:**
- Created comprehensive slice design document at `user/slices/154-slice.prompt-only-loops.md`
- Detailed design for extending prompt-only executor (slice 153) with collection loop support
- State schema extension: `RunState` with `LoopContext` field for tracking loop progress across `--next` calls
- Loop iteration tracking: Inner steps within `each` blocks named with iteration index (e.g., `design-each-0`, `tasks-each-1`)
- Successive iteration as instruction stream: Caller doesn't need loop awareness, just calls `--next` repeatedly
- Step instruction output format extended: JSON includes `loop_context` with current item data and loop position
- State persistence for loop resume: Saved loop state allows resuming mid-iteration without re-querying collection
- Verification walkthrough with concrete examples: 6-step scenario (3 items × 2 inner steps)
- Integration: Slash command (`/sq:run`) automatically compatible with loops (no changes needed)

**Status:**
- Design complete and ready for Phase 5 (Task Breakdown)
- Slice plan entry updated: `140-slices.pipeline-foundation.md` now marks slice 154 complete with link to design

**Key Design Decisions:**
- **Loop iterations flattened into instruction stream:** Progressive `--next` calls return successive iteration steps as if sequential. Caller logic unchanged.
- **LoopContext in RunState:** Tracks current item, item index, completed items, total items. Allows mid-loop resume without re-execution or re-querying.
- **Step naming with iteration index:** `{step_name}-each-{item_index}` ensures uniqueness and traceability across iterations.
- **Prompt-only loop output includes item data:** JSON `loop_context` field contains the bound item's resolved fields (e.g., `slice.index: "151"`).
- **No convergence strategies in prompt-only mode:** Falls back to basic max-iteration (inherited from slice 149). Convergence is SDK executor (slice 155) scope.
- **Variables resolved at instruction-generation time:** Bound item fields like `{slice.index}` are replaced in instruction JSON, not left as placeholders.
- **Collection items persisted in state:** Avoids re-querying CF mid-loop. Enables fast resume and deterministic iteration order.

**Dependencies:**
- Slice 153 (Prompt-Only Pipeline Executor) — prerequisite, extends `render_step_instructions()` and state model
- Slice 149 (Pipeline Executor and Loops) — loop execution logic reference; prompt-only mirrors this behavior
- Slice 150 (Pipeline State and Resume) — extended `RunState` schema with loop context
- Slice 126 (CF Integration) — collection sources (`cf.unfinished_slices()`)

**Architecture Overview:**
- No new modules; extends existing `prompt_renderer.py` with loop awareness
- `LoopContext` dataclass added to `models.py` for state tracking
- `StepInstructions` output extended with `loop_context` field (JSON-serializable)
- `StateManager.record_step_done()` enhanced to detect iteration-pattern step names and update `loop_context.completed_items`
- State file schema versioned; v1 (pre-loop) files backward compatible with `loop_context: null`

**Implementation Notes:**
- Effort: 2/5 (low complexity; leverages existing slice 153 patterns and slice 149 loop logic)
- Test strategy: Mock CF queries, verify iteration progression, validate step naming, test state serialization
- No changes needed to `/sq:run` slash command (works transparently with loop iterations)
- Convergence loop strategies generate warning and fall back to max-iteration (same as executor in 149)

## 20260404

**Slice 156: Pipeline Executor Hardening — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/156-tasks.pipeline-executor-hardening.md`. 14 tasks (T1–T14): `ExecutionMode` StrEnum in state.py (T1); schema v2 with `execution_mode` field on `RunState` (T2); `init_run` gains `execution_mode` param and lowercase normalisation (T3); `_run_pipeline` gains `run_id` and `execution_mode` params (T4); `_run_pipeline_sdk` gains `run_id` param (T5); fix `--resume` dispatch via `match state.execution_mode` (T6); fix implicit resume dispatch (T7); `_handle_prompt_only_init` records `PROMPT_ONLY` (T8); lowercase normalisation in `load_pipeline` (T9) and `discover_pipelines` (T10); CLI input normalisation (T11); display `execution_mode` in `--status` (T12); lint/type-check/full suite (T13); closeout (T14). Test-with pattern throughout; 6 commit checkpoints.

**Slice 156: Pipeline Executor Hardening — Design Complete (Phase 4)**
Diagnosed resume failure: both `--resume` and implicit resume paths bypass `_run_pipeline_sdk`, so `sdk_session` is `None` on resume; compact action falls through to `cf compact --instructions ...` which does not exist. Fix scope: (1) `ExecutionMode` StrEnum added to `state.py`; (2) `RunState.execution_mode` field (schema v2); (3) both resume paths dispatch by enum match to the correct runner; (4) `_run_pipeline_sdk` accepts `run_id` for resume-in-place; (5) pipeline name normalised to lowercase at load and CLI input boundary. Design created at `project-documents/user/slices/156-slice.pipeline-executor-hardening.md`.

**Slice 154: Prompt-Only Loops — Design Complete (Phase 4)**
Created `project-documents/user/slices/154-slice.prompt-only-loops.md` and `project-documents/user/tasks/154-tasks.prompt-only-loops.md`. Slice extends prompt-only mode to transparently support `each`/collection loops — executor expands loops internally, returns successive iteration instructions via `--next` calls. To the caller, a loop appears as a sequence of steps. Enables design-batch pipelines (multi-slice batch operations) in interactive prompt-only mode. Architecture: loop state tracking (iteration count, bound item) in StateManager; placeholder resolution (`{slice.index}` → actual value from item); query source executor for CF `cf.unfinished_slices(plan)` integration; loop expansion in executor's `next_step()` / advancement in `step_done()`. Convergence loop syntax acknowledged in YAML but stubbed (strategies are 155/160 scope). 20 implementation tasks; test-with pattern throughout. No design blockers; ready for implementation.

**Slice 155: SDK Pipeline Executor — Implementation Complete (Phase 6)**
Implemented all 20 tasks (T1–T20). Created `src/squadron/pipeline/sdk_session.py`: `SDKExecutionSession` dataclass wrapping `ClaudeSDKClient` with `set_model()` (skips if unchanged), `dispatch()` (rate-limit retry, error translation), `configure_compaction()` (stores config), `connect()`/`disconnect()` lifecycle. Extended `ActionContext` with `sdk_session: SDKExecutionSession | None = None`. Dispatch action gains `_dispatch_via_session()` path; routing checks `context.sdk_session`. Compact action gains SDK path that calls `session.configure_compaction()` instead of CF. Environment detection via `_resolve_execution_mode()` raises `typer.Exit(1)` for `CLAUDECODE` env var. CLI wiring: `_run_pipeline_sdk()` async helper creates session, connects, calls `_run_pipeline()`, disconnects in `finally`. Executor propagates `sdk_session` through all `_execute_step_once()`/loop/each call chains. 38 new tests across 5 test files. Full suite: 1228 tests pass, zero regressions. Slice 155 marked complete.

**Slice 155: SDK Pipeline Executor — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/155-tasks.sdk-pipeline-executor.md`. 20 tasks (T1–T20): SDKExecutionSession module with persistent client lifecycle and set_model()/dispatch()/configure_compaction() methods (T1-T3), ActionContext extension with sdk_session field (T4), dispatch action session path with model switching (T5-T7), compact action SDK compaction path via context_management API (T8-T10), environment detection for CLAUDECODE rejection (T11-T13), CLI wiring and executor propagation (T14-T17), integration test with full pipeline cycle (T18-T19), lint/verify/closeout (T20). Test-with pattern throughout; 7 commit checkpoints.

**Slice 155: SDK Pipeline Executor — Design Complete (Phase 4)**
Created `project-documents/user/slices/155-slice.sdk-pipeline-executor.md`. Full pipeline automation via `ClaudeSDKClient` with persistent session, per-step model switching via `set_model()`, and server-side compaction via `context_management` API (`compact_20260112` beta). Slice review (glm-5) raised FAIL on persistent session violating 140's "stateless steps" principle. Resolved by updating `140-arch.pipeline-foundation.md` to distinguish SDK session persistence (runtime optimization, 140 scope) from conversation persistence (semantic dependency, 160 scope). Architecture updated: "Interaction with Conversations" section clarified, dependency notes updated.

**Slice 153: Verification and Pipeline Testing**
Ran prompt-only pipeline end-to-end in IDE extension, Claude Code CLI, and straight CLI. Findings: (1) reviews blocked inside Claude Code sessions ("no nested Claude Code") regardless of model — review dispatch goes through SDK subprocess; (2) `/model` and `/compact` slash commands cannot be automated — only user can issue slash commands; (3) checkpoint `always` trigger required stronger prompt language to enforce. Fixed: review command now uses model alias (not resolved ID) to preserve profile resolution; removed invalid `--template` flag; strengthened checkpoint/compact instructions in `/sq:run`. Added `test-pipeline.yaml` for low-cost pipeline testing. Added slice 155 to slice plan, updated slice 154 scope (loops only, model switching informational).

**Slice 153: Prompt-Only Pipeline Executor — Implementation Complete (Phase 6)**
Implemented all 17 tasks (T1–T17). Created `src/squadron/pipeline/prompt_renderer.py`: `StepInstructions`, `ActionInstruction`, `CompletionResult` dataclasses, per-action-type builders (cf-op, dispatch, review, checkpoint, commit, compact, devlog), `render_step_instructions()` entry point. Added `StateManager.record_step_done()` public method. CLI: `--prompt-only`, `--next`, `--step-done`, `--verdict` flags on `sq run`. `/sq:run` slash command rewritten to consume prompt-only output. 30 unit tests, 4 integration tests, 12 CLI tests. Full verification walkthrough passed: all 6 slice pipeline steps cycle correctly, model aliases resolve, compact params resolve `{slice}` → target. 1193 total tests pass, zero regressions. Slice 153 complete.

## 20260403

**Slice 153: Prompt-Only Pipeline Executor — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/153-tasks.prompt-only-pipeline-executor.md`. 17 tasks (T1–T17): data models (`StepInstructions`, `ActionInstruction`, `CompletionResult`), per-action-type instruction builders (cf-op, dispatch, review, checkpoint, commit, compact, devlog), `render_step_instructions()` entry point, `StateManager.record_step_done()` public method, CLI flags (`--prompt-only`, `--next`, `--step-done`), integration test (full prompt-only cycle), `/sq:run` slash command rewrite to consume executor output, lint/verify, closeout. Test-with pattern throughout; 7 commit checkpoints. No blockers.

**Slice 153: Prompt-Only Pipeline Executor — Design Complete (Phase 4)**
Created `project-documents/user/slices/153-slice.prompt-only-pipeline-executor.md`. Adds `--prompt-only --next` mode to `sq run` that outputs one step's structured instructions (JSON) at a time without dispatching to LLMs. Each call advances state via existing `StateManager`. `--step-done <run-id> [--verdict V]` feeds back completion/verdict for checkpoint evaluation. New `prompt_renderer.py` module: pure function that expands step types via existing `expand()`, resolves models via `ModelResolver`, renders compact templates with pipeline params — produces `StepInstructions` dataclass. `/sq:run` slash command rewritten to consume executor output instead of hardcoding workflow. Added slice overview to `140-slices.pipeline-foundation.md` (item 13). Added future work item for external model dispatch to non-Claude-Code LLMs. Dependencies: [151].

**Slice 151: CLI Integration and End-to-End Validation — Implementation Complete (Phase 6)**
Implemented all tasks T1–T21. Created `src/squadron/cli/commands/run.py` (~300 lines): `run()` Typer command with positional `pipeline`/`target` args, `--model`, `--param key=value`, `--from`, `--resume`, `--dry-run`, `--validate`, `--list`, `--status`. `_resolve_target()` maps positional target to pipeline's first required param at runtime. `_assemble_params()` combines target, `--param`, and model. `_check_cf()` pre-flight verifies CF availability. `_run_pipeline()` async helper: load → validate → init_run → execute → finalize. `--resume` loads state, finds next step, re-executes. Implicit resume detection via `find_matching_run()` + `typer.confirm()`. Keyboard interrupt handling saves state and prints resume instructions. Rich output: Table for `--list`, Panel for `--status`, colored summary for execution results. Registered in `app.py`. 38 unit tests (`tests/cli/commands/test_run.py`), 5 integration tests (`tests/pipeline/test_cli_integration.py`). pyright 0 errors; ruff clean. Slice 151 marked complete — completes Pipeline Foundation initiative (140).

**Slice 151: CLI Integration and End-to-End Validation — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/151-tasks.cli-integration-and-end-to-end-validation.md`. 21 tasks (T1–T21): command skeleton + registration, Typer argument signatures, mutual exclusivity validation, `--list`, `--validate`, `--status` (with `"latest"` sentinel), `--dry-run`, parameter assembly helper, CF pre-flight check, core execution flow (`_run_pipeline` async helper + `asyncio.run` bridge), `--resume` flow, implicit resume detection (`find_matching_run` + `typer.confirm`), `--from` mid-process adoption, keyboard interrupt handling, 4 integration tests (full run, resume, from-step, dry-run no state file), exports/lint/pyright, verification and closeout. Test-with pattern throughout; 5 commit checkpoints. No blockers.

**Slice 151: CLI Integration and End-to-End Validation — Design Complete (Phase 4)**
Created `project-documents/user/slices/151-slice.cli-integration-and-end-to-end-validation.md`. Typer `sq run` command surface wiring executor, state manager, and pipeline loader into the CLI presentation layer. Options: `--slice`, `--model`, `--from`, `--resume`, `--dry-run`, `--validate`, `--list`, `--status`. Implicit resume detection when paused run matches pipeline+params. Rich terminal output for all display modes. Integration tests with mock action registries. Async executor bridged via `asyncio.run()`. Pre-flight CF check to avoid orphan state files. Dependencies: [148, 149, 150]. Completes the Pipeline Foundation initiative (140).

**Slice 150: Pipeline State and Resume — Implementation Complete (Phase 6)**
Implemented all tasks T1–T26. Created `src/squadron/pipeline/state.py` (~280 lines): Pydantic models (`RunState`, `StepState`, `CheckpointState`), `SchemaVersionError`, and `StateManager` with full public interface (10 methods). Atomic write via `.tmp` sibling + rename; `init_run` generates `run-{YYYYMMDD}-{slug}-{hash8}` IDs and auto-prunes; `make_step_callback` returns executor-ready closure; `_append_step` extracts verdict (last non-None) and outputs (last action); paused steps set `status="paused"` + `checkpoint` field; `finalize` writes terminal status; `load` validates schema version; `load_prior_outputs` reconstructs `dict[str, ActionResult]` defensively; `first_unfinished_step` scans definition in order; `list_runs` globs+filters+sorts; `find_matching_run` exact params match; `prune` skips paused runs. 43 unit tests + 2 integration tests (full run + resume) all pass. pyright 0 errors; ruff clean. Slice 150 marked complete.

**Slice 150: Pipeline State and Resume — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/150-tasks.pipeline-state-and-resume.md`. 26 tasks (T1–T26): test infrastructure (conftest fixtures), Pydantic models (`RunState`/`StepState`/`CheckpointState`/`SchemaVersionError`), `StateManager.__init__` + atomic write helper, `init_run`, `make_step_callback` + `_append_step`, `finalize`, `load` + `SchemaVersionError` check, `load_prior_outputs`, `first_unfinished_step`, `list_runs`, `find_matching_run`, `prune`, integration tests (full run + resume), exports/lint, closeout. Test-with pattern throughout; 3 commit checkpoints. No blockers.

**Slice 150: Pipeline State and Resume — Design Complete (Phase 4)**
Created `project-documents/user/slices/150-slice.pipeline-state-and-resume.md`. `StateManager` persists `RunState` JSON to `~/.config/squadron/runs/` after every completed step via `on_step_complete` callback. Pydantic models: `RunState`, `StepState`, `CheckpointState`. Atomic write pattern for corruption safety. `load_prior_outputs` reconstructs `dict[str, ActionResult]` from stored `action_results`. `find_matching_run` enables implicit resume detection. `prune(keep=10)` per-pipeline auto-prune on `init_run`. `SchemaVersionError` for forward-compatibility. Provides `StateManager` interface to slice 151 (CLI). Dependencies: [149]. Status: not_started.

**Slice 149: Pipeline Executor and Loops — Implementation Complete (Phase 6)**
Implemented all tasks T1–T10. Created `src/squadron/pipeline/executor.py` (~570 lines): `ExecutionStatus`/`StepResult`/`PipelineResult` result types; `resolve_placeholders` with dotted-path traversal; `LoopCondition`/`evaluate_condition` with closed 3-value enum; `ExhaustBehavior`/`LoopConfig`; `_cf_unfinished_slices` source fn + `_SOURCE_REGISTRY`; `_parse_source` with regex validation; `execute_pipeline` async core with sequential steps, `start_from` skip, checkpoint and failure propagation, `each` branch via `_execute_each_step`, and loop wrapping via `_execute_loop_step`. Replaced `steps/collection.py` stub with `EachStepType` (structural validation, empty `expand()`). Added `collection` import to `validate_pipeline` in `loader.py`. 52 unit tests in `test_executor.py`, 6 integration tests in `test_executor_integration.py`. 296 total pipeline tests pass; pyright 0 errors; ruff clean. Slice 149 marked complete.

**Slice 149: Pipeline Executor and Loops — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/149-tasks.pipeline-executor-and-loops.md`. 10 tasks (T1–T10): test infrastructure, result types (`ExecutionStatus`, `StepResult`, `PipelineResult`), placeholder resolution, loop condition grammar (`LoopCondition` enum + `evaluate_condition`), core sequential executor with checkpoint/failure handling, retry loop execution (`LoopConfig`, `ExhaustBehavior`), `EachStepType` implementation, source registry + `each` execution branch, integration tests, verification and closeout. Test-with pattern throughout; 3 commit checkpoints. No blockers.

**Slice 149: Pipeline Executor and Loops — Design Complete (Phase 4)**
Created `project-documents/user/slices/149-slice.pipeline-executor-and-loops.md`. Async executor engine takes validated `PipelineDefinition`, expands step types into action sequences, resolves `{param}` placeholders, and executes actions sequentially. Retry loops (`loop: {max, until, on_exhaust}`) with closed condition grammar (`review.pass`, `review.concerns_or_better`, `action.success`). `each` collection loop step type with source query dispatch (`cf.unfinished_slices`) and dot-path item binding (`{slice.index}`). Convergence loop strategy field acknowledged but stubbed (160 scope). Checkpoint pausing and action failure propagation. `on_step_complete` callback for state manager/CLI integration. Dependencies: [147, 148]. Unblocks slices 150 (State/Resume) and 151 (CLI).

## 20260402

**Slice 148: Pipeline Definitions and Loader — Implementation Complete (Phase 6)**
Implemented all 13 tasks (T1–T13). Created `schema.py` with `PipelineSchema` and `StepSchema` Pydantic v2 models — `@model_validator(mode="before")` unpacks YAML step grammar, scalar shorthand expansion (`devlog: auto` → `{"mode": "auto"}`), `to_definition()` converts to existing dataclasses. Created `loader.py` with `load_pipeline()` (path or name with project→user→built-in search), `discover_pipelines()` (scan+merge with source attribution), and `validate_pipeline()` (step type registry, model alias resolution, review template existence, param placeholder declaration checks). Four built-in pipeline YAMLs: slice-lifecycle (5 steps), review-only (1), implementation-only (2), design-batch (1 `each`). 43 new tests (12 schema + 11 loader + 9 validation + 11 integration), 995 total pass, pyright 0 errors, ruff clean. Slice 148 marked complete.

**Slice 148: Pipeline Definitions and Loader — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/148-tasks.pipeline-definitions-and-loader.md`. 13 tasks (T1–T13): Pydantic schema models + tests, four built-in pipeline YAML files, pipeline loader with 3-source discovery + tests, `discover_pipelines` + tests, semantic validation (`validate_pipeline`) + tests, integration tests for all built-ins, two commit checkpoints, closeout. Test-with pattern throughout. No blockers.

**Slice 148: Pipeline Definitions and Loader — Design Complete (Phase 4)**
Created `project-documents/user/slices/148-slice.pipeline-definitions-and-loader.md`. YAML pipeline grammar with Pydantic v2 schema validation (`schema.py`), loader with 3-source discovery (built-in → user → project), four built-in pipelines (slice-lifecycle, review-only, implementation-only, design-batch), and semantic validation (step types, model aliases, review templates, param references). Pydantic validates at boundary, converts to existing `PipelineDefinition`/`StepConfig` dataclasses. Dependencies: [147]. Unblocks slice 149 (Executor) and 151 (CLI).

**Slice 147: Compact Action and Step Types — Implementation Complete (Phase 6)**
Implemented all 13 tasks (T1–T13). Created compaction instruction template (`data/compaction/default.yaml`) with loader supporting user overrides from `~/.config/squadron/compaction/`. Implemented `CompactAction` with template-based CF instructions, `keep`/`summarize` params, and optional CF summarize call. Implemented four step types: `PhaseStepType` (3 registrations, 6-action expansion with optional review/checkpoint), `CompactStepType` (single compact action passthrough), `ReviewStepType` (review + optional checkpoint), `DevlogStepType` (single devlog with auto/explicit mode). 76 new tests (17 compact action + 17 phase + 7 compact step + 8 review step + 9 devlog step + 17 registry integration + 1 init), 952 total pass, pyright 0 errors, ruff clean. Slice 147 marked complete.

**Slice 147: Compact Action and Step Types — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/147-tasks.compact-action-and-step-types.md`. 13 tasks (T1–T13): compaction instruction template + loader, CompactAction implementation + tests, PhaseStepType (3-phase registration) + tests, CompactStepType + tests, ReviewStepType + tests, DevlogStepType + tests, registry integration tests, verification and closeout. Test-with pattern throughout. No blockers.

**Slice 147: Compact Action and Step Types — Design Complete (Phase 4)**
Created `project-documents/user/slices/147-slice.compact-action-and-step-types.md`. Compact action issues parameterized compaction instructions to CF with configurable `keep`/`summarize` params. Four step types: phase (cf-op→dispatch→review→checkpoint→commit), compact (single compact action), review (review + optional checkpoint), devlog (single devlog action). Step types are pure data transformers — `expand()` returns `(action_type, action_config)` tuples for the executor. Dependencies: [144, 145, 146]. Unblocks slice 148 (Pipeline Definitions) and 149 (Executor).

**Slice 146: Review and Checkpoint Actions — Implementation Complete (Phase 6)**
Implemented all 8 tasks (T1–T8). Extracted review persistence to shared `review/persistence.py` (`format_review_markdown`, `save_review_file`, `yaml_escape`, `SliceInfo`). Implemented `CheckpointAction` with `CheckpointTrigger` enum and trigger×verdict evaluation matrix. Implemented `ReviewAction` delegating to `run_review_with_profile()` with model/profile resolution, template input passthrough, review file persistence (non-fatal), and verdict/findings mapping. 57 new tests (13 persistence + 21 checkpoint + 21 review + 2 registry), 884 total pass, pyright 0 errors, ruff clean. Slice 146 marked complete.

---

