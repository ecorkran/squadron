---
docType: tasks
slice: project-rules-for-every-provider-agents-md-and-relevance-selected-rules
project: squadron
lld: user/slices/935-slice.project-rules-for-every-provider-agents-md-and-relevance-selected-rules.md
dependencies: [260, 267]
projectState: >
  Slice design 935 complete after one review round (20261012); `requires` (#204) and `@` import
  resolution (#205) were cut. No code written. Release 0.21.5 is on PyPI; fix 3a98f584 (#195, #59)
  is on main, unreleased.
dateCreated: 20261012
dateUpdated: 20261012
status: complete
---

## Context Summary

- Working on **935 project rules for every provider** (fixes #181, #182). Today only SDK dispatches see project rules (natively, via the Claude CLI). Non-SDK dispatches (OpenAI-compatible, codex) get none, and reviews inject only `CLAUDE.md`/`.claude/CLAUDE.md`, never `AGENTS.md`.
- Delivers a `squadron.project_rules` package. It picks one conventions file (`AGENTS.md` first, D2), selects rule files by a new `steps` frontmatter key (D3), and applies a size budget (D6). The package is used by non-SDK dispatch and by reviews, and both record what they injected (D7).
- The design is the reference. Tasks cite its decisions (D1–D7), the failure-mode table under "Patterns and Conventions", and the Verification Walkthrough. They do not repeat them.
- `project_rules` imports nothing from `review` or `pipeline` (D1). Pipeline-side glue goes in a new `pipeline/actions/dispatch_rules.py`. Do not grow `dispatch.py`, which is already over 700 lines.
- Every comparison value is an enum (`ConventionsSource`, `RuleStep`). There are no bare string literals in conditionals.
- Every code task ends with `ruff format`, `ruff check`, `pyright` (zero errors), the touched tests, and a commit on the slice branch.
- Effort: 3/5. Next work after this slice: 941.

## Tasks

- [x] **Task 1: Branch**
  - [x] Read the target: `cf config get git.integration_branch` (empty means `main`)
  - [x] Create `935-slice.project-rules-for-every-provider-agents-md-and-relevance-selected-rules` from the target
  - **Success:** on the slice branch, working tree clean

### Package and frontmatter

- [x] **Task 2: Move frontmatter and glob helpers (no behavior change)**
  - [x] Create `src/squadron/project_rules/__init__.py` and `frontmatter.py`
  - [x] Move the items listed under "Migration Plan → Moved" from `review/rules.py` to `frontmatter.py`, unchanged
  - [x] `review/rules.py` imports them from `project_rules.frontmatter`. `RulesSource`, `resolve_rules_dir`, `load_rules_content`, `get_template_rules`, `extract_diff_paths` and `load_review_rules` stay in `review/rules.py`
  - [x] Update the import paths in `tests/review/test_rules_module.py` (and any other test importing a moved name). Change no assertions.
  - [x] Confirm `project_rules` has no import from `squadron.review` or `squadron.pipeline` (grep)
  - [x] Run `pytest tests/review tests/cli -q`, then ruff and pyright
  - [x] Commit: `refactor: extract rule frontmatter helpers into project_rules`
  - **Success:** all existing review tests pass with only import-path edits

- [x] **Task 3: `RuleStep` enum and `steps` parsing**
  - [x] Add `RuleStep(StrEnum)` in `project_rules` with values `design`, `tasks`, `implement`, `review`, `dispatch`
  - [x] Add a frozen `RuleFrontmatter` dataclass (`paths: list[str] | None`, `steps: frozenset[RuleStep] | None`)
  - [x] Parse `steps` in both inline (`[a, b]`) and block (`- a`) list forms, with the same leniency as `paths` (varying indent, trailing whitespace)
  - [x] An unknown `steps` value raises `ValueError`, and the message names the rule file and the value (D3)
  - [x] `load_rules_frontmatter` returns `dict[str, RuleFrontmatter]`. Update its consumers in `review/rules.py` to read `.paths`.
  - **Success:** review language-rule selection is unchanged for files without `steps`

- [x] **Task 4: Test frontmatter parsing**
  - [x] Tests in `tests/project_rules/test_frontmatter.py`: inline `steps`; block `steps`; `steps` with `paths`; no frontmatter; `paths` only (the `steps` field is `None`)
  - [x] Unknown value → `ValueError` naming the file and the value
  - [x] One test parses every file in squadron's real `.claude/rules/` without error (real-format fixture)
  - [x] Run `pytest tests/project_rules tests/review -q`, then ruff and pyright
  - [x] Commit: `feat: parse steps key in rule frontmatter`
  - **Success:** tests pass, zero pyright errors

### Conventions file

- [x] **Task 5: `conventions.py`**
  - [x] `ConventionsSource(StrEnum)` with the five values in D7 (`AGENTS.md`, `CLAUDE.md`, `.claude/CLAUDE.md`, `sdk-native`, `none`). The values are an artifact contract, so document that in the docstring as `RulesSource` does.
  - [x] Candidate order is one tuple constant: `AGENTS.md`, `CLAUDE.md`, `.claude/CLAUDE.md` (D2)
  - [x] `find_conventions(root: Path)` returns the chosen file (source, path, content) or `None`, plus the list of other candidates that exist (`skipped`)
  - [x] A candidate that exists (`Path.exists()` or `Path.is_symlink()`) but can't be read raises an error naming the path. It never falls through to the next candidate (D2, "Unreadable file").
  - [x] Content is returned as written; `@path` lines are not resolved (#205)
  - **Success:** one function answers "which conventions file" for both consumers

- [x] **Task 6: Test `find_conventions`**
  - [x] Parametrized over `tmp_path` layouts: AGENTS only, CLAUDE only, `.claude/CLAUDE.md` only, AGENTS + CLAUDE, all three, none. Assert the chosen source and `skipped`.
  - [x] Unreadable chosen file (a `chmod 000` file, or a broken symlink) → error naming the path; the next candidate is not used
  - [x] Run the tests, ruff, pyright
  - [x] Commit: `feat: add conventions file discovery with AGENTS.md first`
  - **Success:** tests pass

- [x] **Task 7: Switch the review probe to `find_conventions`**
  - [x] In `review_client._inject_file_contents`, replace the `("CLAUDE.md", ".claude/CLAUDE.md")` loop with `find_conventions(convention_root or cwd)`. Keep heading demotion, placement, and the `review.max_total_injection_bytes` accounting.
  - [x] The injection label names the chosen file (for example `AGENTS.md (project conventions)`), derived from the enum value
  - [x] The read error now propagates instead of logging a warning (D2)
  - [x] No conventions file: log at INFO (D7)
  - [x] Return the chosen `ConventionsSource` (`none` when absent) to the caller with the injected prompt. Extend `InjectedPrompt` rather than adding a second call.
  - [x] In `review/builders/code.py`, change "Apply the project conventions from CLAUDE.md" so it names no file
  - **Success:** an AGENTS.md-only project gets its conventions in review prompts

- [x] **Task 8: Record `conventionsSource` in review frontmatter**
  - [x] Thread the `ConventionsSource` from the review run to the save targets the same way `rules_source` is threaded today
  - [x] Write `conventionsSource` next to `rulesSource` in all three frontmatter builders in `review/save_target.py` and in `cli/commands/review_pr.py`
  - **Success:** every review artifact carries `conventionsSource`

- [x] **Task 9: Test the review conventions switch**
  - [x] `tests/review/test_content_injection.py`: AGENTS-only injects AGENTS; both present injects AGENTS once and not CLAUDE; none injects nothing; `convention_root` is honored; an unreadable file raises
  - [x] `tests/review/test_save_target.py`: `conventionsSource` is present for each target kind
  - [x] Update any exact-match prompt expectations that changed with the label or the builder line
  - [x] Run `pytest tests/review tests/cli tests/pipeline/actions/test_review_action.py -q`, then ruff and pyright
  - [x] Commit: `feat: inject AGENTS.md in reviews and record conventionsSource`
  - **Success:** tests pass

### Selection, render, budget

- [x] **Task 10: Budget config key**
  - [x] Add `project_rules.max_chars` to `config/keys.py`: int, default `48000`, with an About line naming D6 behavior (drop rules, fail on conventions over budget)
  - **Success:** `sq config get project_rules.max_chars` prints 48000

- [x] **Task 11: `selection.py`**
  - [x] `RuleContext` frozen dataclass exactly as in the design's Component Structure (`step_kind`, `file_paths`, `root`, `rules_dir`, `native`, `max_chars`)
  - [x] `ProjectRules` frozen dataclass: chosen conventions (or none), `native: bool`, `skipped`, selected rule paths, dropped rule names, `chars`. `to_record()` returns the D7 dict shape.
  - [x] `select_project_rules(ctx) -> ProjectRules`:
    1. Conventions via `find_conventions(ctx.root)`. If the chosen source equals `ctx.native`, skip its content and set `native=True` (D5).
    2. Rules from `ctx.rules_dir` (`None` → no rules), applying the D3 selection steps in order: skip `review.md`/`review-*.md`, then the step check with defaults, then the path check only when `file_paths` is not `None`. Use the moved `match_rules_files` glob logic.
    3. Budget (D6): conventions first, then rules in filename order. A rule that doesn't fit → WARNING naming it plus an entry in `dropped`. Conventions alone over `max_chars` → error naming the file, its size, and `project_rules.max_chars`.
    4. An unreadable rule file → WARNING plus an entry in `dropped`
  - **Success:** selection is a pure function of `RuleContext` plus file contents

- [x] **Task 12: `render.py`**
  - [x] `render_project_rules(ProjectRules) -> str`: a `## Project Rules` section with the conventions content (unless native) and then each rule, headings demoted like the review injection. Return an empty string when there's nothing to inject.
  - [x] Reuse the existing heading-demotion helper. If it lives in `review/`, move it into `project_rules` and import it back in review (D1 direction).
  - **Success:** the rendered section holds the conventions (unless native) and every selected rule, in order. `ProjectRules.chars` counts raw file content only (what the budget is checked against), not the rendered heading, separators or demotion.

- [x] **Task 13: Test selection and render**
  - [x] One test per D3 selection rule: review template files skipped; `steps` explicit; `steps` defaulted without `paths` (all kinds); defaulted with `paths` (implement and review only); path check skipped when `file_paths` is `None`; path-scoped rule with no matching file excluded
  - [x] D2/D5 cases: native match sets `native` and omits the content but keeps the rules; no native match injects the content
  - [x] Failure-mode rows: a rule over budget is dropped with a WARNING (`caplog`); conventions over budget raises naming the key; an unreadable rule produces a WARNING and lands in `dropped`
  - [x] `to_record()` matches the D7 shape. Render output contains the heading and each selected rule in order. `chars` equals the summed raw length of the injected conventions and rule files.
  - [x] Real-files test: run selection against squadron's own root and `.claude/rules/` and assert the per-kind results in D3 (implement: `bug-fixes`, `python`, `testing`, `shell`, with the tracked file list; design and tasks: `bug-fixes`). Conventions source is `AGENTS.md`, and `skipped` contains `CLAUDE.md`.
  - [x] Run the tests, ruff, pyright
  - [x] Commit: `feat: select project rules by step kind with a size budget`
  - **Success:** tests pass

### Dispatch wiring

- [x] **Task 14: `pipeline/actions/dispatch_rules.py`**
  - [x] `StepTypeName` → `RuleStep` table for `design`, `tasks`, `implement`, `dispatch`. A missing entry raises naming the step type (D3).
  - [x] `ProviderType` → native `ConventionsSource | None` table: `SDK` → `CLAUDE.md`, `OPENAI_OAUTH` → `AGENTS.md`, `OPENAI` → `None`. A missing provider type raises (D5).
  - [x] `build_rule_context(step_type, provider, cwd)`: maps the step; resolves `rules_dir` via `resolve_rules_dir(cwd, None, None)`; reads `project_rules.max_chars`; for implement, gets `file_paths` from `git ls-files` through `run_git`. `run_git` never raises: it returns `None` (git missing or timed out) or a process with a non-zero `returncode` (git refused). Both raise here, naming the git error; neither becomes an empty list.
  - **Success:** all pipeline-to-package translation lives in this module

- [x] **Task 15: Test `dispatch_rules`**
  - [x] Each table entry; a missing step type raises; a missing provider type raises
  - [x] Implement gets tracked files; design gets `None`
  - [x] Monkeypatch `run_git` to return `None`, then a process with a non-zero `returncode`: each raises, naming the git error
  - [x] Run the tests, ruff, pyright
  - [x] Commit: `feat: add pipeline glue for project rule selection`
  - **Success:** tests pass

- [x] **Task 16: Pass the step kind from phase steps**
  - [x] Add `RULES_STEP_PARAM` next to the other param constants in `pipeline/steps/phase.py`, and set it in `dispatch_config` to the phase's `StepTypeName`
  - [x] A bare `dispatch` step sets nothing; the action treats a missing param as `StepTypeName.DISPATCH`
  - **Success:** the phase step's dispatch params carry its kind

- [x] **Task 17: Inject in non-SDK one-shot dispatch**
  - [x] Add a keyword parameter `rule_step: StepTypeName | None = None` to `one_shot_dispatch_with_telemetry`. `None` means no rules and no record, which keeps the summary caller at line ~81 unchanged.
  - [x] When `rule_step` is set and the provider is not SDK: `build_rule_context` → `select_project_rules` → `render_project_rules`, appended to `instructions` after the step `system_prompt`, and `telemetry["project_rules"] = to_record()`. The build-and-select call does git and file I/O, so run it through `asyncio.to_thread` (same pattern as `_kept_outputs` in `dispatch.py`); render is pure and stays inline.
  - [x] When `rule_step` is set and the provider is SDK: no injection; `telemetry["project_rules"] = {"conventions": "sdk-native"}`, built from the enum
  - [x] Non-SDK with conventions `none` and no rules selected: WARNING naming the root and the step (D7)
  - [x] `_dispatch_via_agent` reads `RULES_STEP_PARAM` (default `DISPATCH`) and passes it as `rule_step`
  - [x] `_dispatch_via_session` adds the `sdk-native` record to its `ActionResult.metadata`
  - **Success:** `project_rules` lands in `ActionResult.metadata` on every dispatch path that writes artifacts

- [x] **Task 18: Test dispatch injection**
  - [x] Non-SDK fake provider (follow the existing pattern in `tests/pipeline/actions/test_dispatch.py`): the system prompt given to the agent contains `## Project Rules` and the selected rule text, and the metadata holds the record
  - [x] SDK one-shot: instructions unchanged, and the record is `sdk-native`. Session path (`test_dispatch_session.py`): the record is `sdk-native`.
  - [x] Codex provider type with AGENTS.md present: `native` is true, the content is absent, and the rules are present
  - [x] The none/none WARNING is emitted (`caplog`). Conventions over budget fails the action, and the error names the key.
  - [x] Phase step test: implement's dispatch params carry `RULES_STEP_PARAM`
  - [x] Run `pytest tests/pipeline -q`, then ruff and pyright
  - [x] Commit: `feat: inject project rules into non-SDK dispatches`
  - **Success:** tests pass

### Review rule filtering

- [x] **Task 19: Filter review language rules by `steps`, record `projectRules`**
  - [x] In `load_review_rules`, language-rule matching also applies the D3 step check with `RuleStep.REVIEW`. Template rules and manual rules are unchanged.
  - [x] Return the selected language-rule filenames along with the content (a small result dataclass), and update the three callers (`cli/commands/review.py`, `cli/commands/review_pr.py`, `pipeline/actions/review.py`)
  - [x] Replace the silent `except OSError: continue` in `load_rules_content` and the `except OSError: pass` in `get_template_rules` with a WARNING naming the file. Unreadable language rules are left out of the returned filenames (the failure-mode row's `dropped` case).
  - [x] Write `projectRules: [...]` next to `conventionsSource` in the same frontmatter builders as Task 8
  - **Success:** a rule with `steps: [implement]` never reaches a review

- [x] **Task 20: Test review filtering**
  - [x] `tests/review/test_rules.py`: a language rule with `steps: [implement]` is excluded; with `steps: [review]` it is included; with no `steps` the behavior is as before
  - [x] An unreadable language rule and an unreadable template rule each log a WARNING naming the file (`caplog`); the language rule is absent from the returned filenames
  - [x] `test_save_target.py`: `projectRules` lists the selected rules
  - [x] Run `pytest tests/review tests/cli tests/pipeline -q`, then ruff and pyright
  - [x] Commit: `feat: filter review rules by steps and record projectRules`
  - **Success:** tests pass

### Docs and verification

- [x] **Task 21: Docs and CHANGELOG**
  - [x] `docs/PIPELINES.md`: a "Project rules" section covering the conventions file order, the `steps` key with its defaults table (D3), `project_rules.max_chars`, the `project_rules` record, and SDK `sdk-native`
  - [x] Mention `conventionsSource`/`projectRules` where the review frontmatter keys are documented (find it with grep for `rulesSource` in `docs/`). If no such place exists, add them to the PIPELINES section.
  - [x] CHANGELOG `[Unreleased]`: short user-facing bullets (non-SDK models now get project rules; reviews read `AGENTS.md`; the `steps` rule key)
  - [x] Commit: `docs: document project rules selection and steps key`
  - **Success:** a user can learn the `steps` key and the budget from the docs alone

- [x] **Task 22: Verification walkthrough**
  - [x] Run the design's Verification Walkthrough steps 1–8 in a scratch copy. For `<non-sdk-alias>`, pick an alias whose profile is not `sdk` from `sq model list`. Step 8 needs a codex-profile alias. If none is configured, record step 8 as not run and say why.
  - [x] Record each step's observed result (frontmatter value or `jq` output) in the DEVLOG entry for this phase
  - [x] If a step fails, stop and report the failing step with its output. Do not change code to force a pass.
  - **Success:** every step matches its expected result, or the failure is reported

- [x] **Task 23: Final validation**
  - [x] Full `pytest -q`, `ruff format`, `ruff check`, `pyright` (zero errors)
  - [x] Mark the slice design `status: complete` and update its `dateUpdated`
  - [x] DEVLOG entry: "Slice 935: implementation complete (Phase 6)"
  - [x] Commit: `docs: complete slice 935 implementation`
  - **Success:** the suite is green and all work is committed on the slice branch
