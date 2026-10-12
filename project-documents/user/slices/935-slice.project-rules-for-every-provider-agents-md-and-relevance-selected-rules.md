---
docType: slice-design
slice: project-rules-for-every-provider-agents-md-and-relevance-selected-rules
project: squadron
parent: project-documents/user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: [260, 267]
interfaces: []
dateCreated: 20261012
dateUpdated: 20261012
status: not_started
---

# Slice Design: Project Rules for Every Provider — AGENTS.md and Relevance-Selected Rules

## Overview

Fixes [#181](https://github.com/ecorkran/squadron/issues/181) and [#182](https://github.com/ecorkran/squadron/issues/182).

Today only SDK dispatches see project rules, and they get them from the Claude CLI (`setting_sources=("project",)`), which loads `CLAUDE.md` and `.claude/rules/*.md`. Non-SDK dispatches (OpenRouter, OpenAI-compatible, codex) get nothing: `setting_sources=None`, and the cf prompt doesn't point at the files. Reviews inject `CLAUDE.md` or `.claude/CLAUDE.md` by probing `review_client._inject_file_contents`, never `AGENTS.md`, and the artifact records only `rulesSource`, which describes the rules directory, not the conventions file.

This slice makes squadron read the rules itself. It picks one conventions file (`AGENTS.md`, `CLAUDE.md` or `.claude/CLAUDE.md`), selects rule files from frontmatter by step kind, injects the result into every non-SDK dispatch and every review, and records what it injected, including "none".

## Value

- Non-SDK design, tasks and implement agents follow the project's code-structure, exception, parsing, commit and document rules. Since 260 and 197 they write real code, so this is the gap between "a cheap model implemented it" and "a cheap model implemented it the way the project requires".
- Projects that keep their conventions only in `AGENTS.md` (codex-style) get them in reviews.
- A reviewer or run that saw no conventions says so in its artifact and run state, instead of looking identical to one that did.

## Technical Scope

**Included**
- A shared `squadron.project_rules` package: conventions-file discovery, rule selection by frontmatter, a size budget, and a record of what was injected.
- Injection into non-SDK one-shot dispatch (`_dispatch_via_agent` → `one_shot_dispatch_with_telemetry`).
- Reviews (CLI `sq review`, pipeline `review` action, PR review) use the same conventions discovery and the same `steps` filtering for language rules.
- One new optional rule-frontmatter key, `steps`.
- Recording: `project_rules` in dispatch step metadata (persisted in run state), `conventionsSource` and `projectRules` in review frontmatter.
- One config key, `project_rules.max_chars`.
- Docs: rule frontmatter keys and selection behavior in the user docs.

**Excluded**
- SDK dispatches keep native loading (D4). Only their record changes.
- Splitting `CLAUDE.md` or `AGENTS.md` into parts. Either file is one always-apply unit (D2).
- Per-model budgets (an alias field). The global key covers it until a real small-context model needs less; tracked as an issue at implementation time.
- Changing the content of squadron's own `CLAUDE.md`/`AGENTS.md` (cf generates both). Compiling the rules once to `AGENTS.md`, with `CLAUDE.md` importing it, is [context-forge#116](https://github.com/ecorkran/context-forge/issues/116).
- Summary and compact dispatches. They don't produce project artifacts.
- A `requires` key (rule selection by agent capability): [#204](https://github.com/ecorkran/squadron/issues/204). No existing rule needs it, and it needs a capability model per provider and reviewer.
- Resolving `@path` imports in an injected `CLAUDE.md`: [#205](https://github.com/ecorkran/squadron/issues/205). With `AGENTS.md` chosen first, a `CLAUDE.md` that only imports `AGENTS.md` is never the chosen file.

## Dependencies

### Prerequisites
- **260** (non-SDK tool use) and **197** (implement batch): the non-SDK implement path this slice feeds. Complete.
- **267** (tool-use guidance): non-SDK system prompt composition (`instructions` plus the guidance block added in the agent). Complete.
- **382 D1**: `convention_root` for PR reviews, honored by the new discovery. Complete.

### Interfaces Required
- `review.rules.resolve_rules_dir` for rules-directory resolution (unchanged priority order). The caller resolves the directory and passes it in `RuleContext.rules_dir`; `project_rules` never imports from `review` (D1).
- `review.rules` frontmatter and glob helpers (`load_rules_frontmatter`, `match_rules_files`, `_glob_to_regex`), moved into the new package (Migration Plan).
- `ProviderType` for the native-loading table (D5).
- `StepTypeName` for step kinds, mapped to `RuleStep` on the pipeline side (D3).

## Architecture

### Component Structure

```
src/squadron/project_rules/
  conventions.py   ConventionsSource enum, find_conventions(root) -> ConventionsFile | None
  frontmatter.py   moved from review/rules.py; parses paths, steps
  selection.py     RuleContext, select_project_rules(...) -> ProjectRules
  render.py        render_project_rules(ProjectRules) -> str (headings demoted)

src/squadron/pipeline/actions/dispatch_rules.py
  StepTypeName -> RuleStep map, native-loading table, build_rule_context(...)
```

`dispatch_rules.py` is the pipeline-side glue. It keeps `dispatch.py` (already over 700 lines) from growing, and it is where pipeline concepts (`StepTypeName`, `ProviderType`, `resolve_rules_dir`) meet the package.

`ProjectRules` is a frozen dataclass holding the chosen conventions file (or none), whether it was skipped as native, the skipped candidates, the selected rule files, the dropped rule files, the rendered character count, and `to_record() -> dict[str, object]` for metadata and frontmatter.

`RuleContext` is what selection needs and nothing else: `step_kind: RuleStep`, `file_paths: list[str] | None`, `root: Path`, `rules_dir: Path | None`, `native: ConventionsSource | None` (the file the provider loads itself, D5), `max_chars: int`.

### Data Flow

**Non-SDK dispatch**

1. Phase steps (design, tasks, implement) already pass params into their dispatch action. They add `RULES_STEP_PARAM` with their `StepTypeName`. A bare `dispatch` step has no param and gets kind `dispatch`.
2. `_dispatch_via_agent` calls `build_rule_context`, which maps the step kind, resolves the rules directory with `resolve_rules_dir(cwd, None, None)`, looks up the provider's native file, and reads `project_rules.max_chars`.
3. For implement, `file_paths` is the project's tracked files (`git ls-files`, through `run_git`). Design, tasks and dispatch pass `None`.
4. `select_project_rules` → `render_project_rules` → appended to `instructions` under a `## Project Rules` heading, after any step `system_prompt`. The agent then adds the 267 guidance block as today.
5. `ProjectRules.to_record()` goes into the returned telemetry dict under `project_rules`, which lands in `ActionResult.metadata` and so in `StepState.action_results` in the run state file.

**Review**

1. `_inject_file_contents` replaces its `CLAUDE.md` probe with `find_conventions(convention_root or cwd)`. Placement doesn't change: the conventions file is still injected into the user prompt, demoted, and counts against `review.max_total_injection_bytes`. The code-review builder's "Apply the project conventions from CLAUDE.md" line stops naming a file.
2. `load_review_rules` keeps its order (template rules, manual rules, language rules). Language rules now pass through the same `steps` filter with kind `review`, matched against the diff or target paths as today.
3. The save target writes `conventionsSource` and `projectRules` next to `rulesSource`.

**SDK dispatch and SDK session**

No injection. The record is `{"conventions": "sdk-native"}`, so every step's state says where its rules came from.

### State Management

No new state. The record rides in existing persisted structures: dispatch `ActionResult.metadata` (serialized into `StepState.action_results`) and review frontmatter.

## Technical Decisions

### D1 — One package, two consumers
Discovery and selection live in `squadron.project_rules`, not in `review/` or `pipeline/`. Dispatch and review both import it, so "which file, which rules" has one answer. The frontmatter and glob helpers move out of `review/rules.py`; review keeps its rules-directory resolution and its template-rule loading, which are review concepts.

Import direction: `project_rules` imports nothing from `review` or `pipeline`. It takes the rules directory, the native file and the budget as inputs. `review` and `pipeline` import `project_rules`, never the reverse. Moving `resolve_rules_dir` was rejected: it reads config and `review.templates`, so moving it would drag those dependencies along.

### D2 — Conventions file: one, AGENTS.md first, never concatenated
Candidates in order: `AGENTS.md`, `CLAUDE.md`, `.claude/CLAUDE.md`. The first one present is used. Any others present are recorded as `skipped`, not injected.

Why not concatenate: in cf-managed projects both files come from the same source. In squadron they differ only in the title line, the bug-fixes pointer and `AGENTS.md`'s rules index. Concatenating doubles about 13K characters for nothing.

Why `AGENTS.md` first: squadron injects only for models that aren't Claude (D4), and `AGENTS.md` is the file every agent tool reads (codex, Copilot, Cursor). `CLAUDE.md` is becoming the Claude-only layer on top: `@AGENTS.md` plus notes for Claude, which Claude Code loads natively. A non-Claude model should get the neutral rules, not instructions written for Claude. For projects with both files, reviews switch from `CLAUDE.md` to `AGENTS.md`; in cf-managed projects the content is nearly identical.

**Imports.** The chosen file is injected as written; `@path` lines are not resolved ([#205](https://github.com/ecorkran/squadron/issues/205)). With `AGENTS.md` first, the cf#116 layout (`CLAUDE.md` = `@AGENTS.md` plus notes) always picks `AGENTS.md`, so the pointer line never reaches a prompt.

**Unreadable file.** A candidate that exists but can't be read (`OSError`: permissions, a broken symlink) raises an error naming the path, in dispatch and in review. It is never skipped in favor of the next candidate, because that would silently swap one project's rules for another file.

The file is injected whole. It is the project's always-apply layer (`AGENTS.md` says as much: "The rules above always apply"), and the only way to split it would be by its headings, which this project forbids as structure. A project that wants git rules kept away from reviewers moves them into a rule file with `steps: [implement]`.

### D3 — How a rule declares relevance: frontmatter
Rule files already carry `description` and `paths` frontmatter (Claude Code's format). One optional key is added. Squadron reads it and Claude Code ignores it.

| Key | Values | Absent means |
|---|---|---|
| `steps` | any of `design`, `tasks`, `implement`, `review`, `dispatch` | no `paths`: all kinds. With `paths`: `implement`, `review` |

Selection for one rule file:
1. `review.md` and `review-*.md` are skipped for dispatch. They keep their existing role as review template rules (`get_template_rules`).
2. The step kind must be in `steps`, explicit or defaulted.
3. If the rule has `paths` and the step has `file_paths` (implement, review), at least one path must match. Design, tasks and dispatch have no file set, so they skip the path check. A path-scoped rule reaches them only when `steps` lists them explicitly.

The defaults match Claude Code where they overlap (a rule with no `paths` always loads), so a project's existing rules behave as they do under the SDK. Applied to squadron's `.claude/rules` with no edits: implement gets `bug-fixes`, `python`, `testing`, `shell`; design and tasks get `bug-fixes`; review gets what `load_review_rules` gives it today.

`RuleStep` is a `StrEnum` in `project_rules`. Frontmatter values are parsed into it, and an unknown value raises at parse time with the file name. It is never ignored. This is fail-fast on purpose: one typo'd `steps` value fails every dispatch and review that loads that rules directory, and the error names the file to fix. Skipping the rule would hide it from every step with no signal.

`StepTypeName` → `RuleStep` is one table in `dispatch_rules.py`: `design`, `tasks`, `implement`, `dispatch` map by name. Review sites pass `RuleStep.REVIEW` directly. A step type outside the table raises, so a new phase step can't silently get no rules.

### D4 — SDK dispatches keep native loading
Rejected: moving SDK to squadron's selection with `setting_sources=[]`. Two reasons. Dropping `project` also drops the project's `settings.json` (permissions, hooks), which squadron can't replicate. And the persistent SDK session fixes its system prompt at connect time (#155 guard), so per-step selection is impossible on that path. SDK parity is in the record (`sdk-native`), not in the mechanism.

### D5 — Codex loads AGENTS.md itself; squadron injects only what it doesn't
Verified 20261012 with a probe through the same `openai_codex` SDK squadron uses (thread at `cwd`, read-only sandbox, no tool calls made). In a repo with both files, codex answered with the codeword from `AGENTS.md` and knew nothing of the one in `CLAUDE.md`. So codex loads `AGENTS.md` natively and ignores `CLAUDE.md`.

Each provider type therefore declares which conventions file it loads natively: `ProviderType.SDK` → `CLAUDE.md` (plus rules, D4), `ProviderType.OPENAI_OAUTH` (codex) → `AGENTS.md`, `ProviderType.OPENAI` → none. It's one table in `dispatch_rules.py`, and a provider type missing from it raises. When the chosen conventions file (D2) is the one the provider loads natively, squadron skips the conventions file and records it as `native`. Selected rules are still injected, because codex has no rules mechanism. Codex with only `CLAUDE.md` present gets `CLAUDE.md` injected.

### D6 — Size budget: one config key, drop rules, never truncate
New key `project_rules.max_chars`, default `48000`, defined in `config/keys.py` like every other default. The conventions file goes in first, then rules in filename order. A rule that would exceed the budget is dropped: one WARNING naming it, plus an entry in `dropped`. If the conventions file alone exceeds the budget, the dispatch fails with an error naming the file, its size and the key. Rules are never truncated mid-file, because a half rule reads as the whole rule.

Reviews keep their existing `review.max_*` budgets, which already cover the conventions injection there.

### D7 — Recording and "none found"
`ConventionsSource(StrEnum)`: `CLAUDE.md`, `.claude/CLAUDE.md`, `AGENTS.md`, `sdk-native`, `none`. These values are an artifact contract, the same as `RulesSource`.

Dispatch metadata `project_rules`:
```json
{"conventions": "AGENTS.md", "native": false, "skipped": ["CLAUDE.md"],
 "rules": ["bug-fixes.md", "python.md"], "dropped": [], "chars": 23140}
```
Review frontmatter: `conventionsSource: AGENTS.md` and `projectRules: [python.md]`.

When the conventions source is `none` and no rule was selected for a non-SDK dispatch, log a WARNING naming the root and the step: an agent writing project artifacts with zero rules is worth seeing. A review with no conventions file logs at INFO; its frontmatter already says `none`.

### Patterns and Conventions
- Comparison values are enums (`ConventionsSource`, `RuleStep`), never bare strings.
- Frontmatter parsing stays lenient about layout (inline and block lists, varying indent, as today) and strict about values (unknown enum value → error).
- Unreadable rule file (`OSError`): WARNING and recorded in `dropped`. Today `load_rules_content` skips it silently; that `continue` is replaced.

**Failure modes and their signals** (each gets a test asserting the signal):

| Failure | Signal |
|---|---|
| Conventions file exists but can't be read | error naming the path (D2) |
| Unknown `steps` value | error naming the file and value (D3) |
| Rule file can't be read | WARNING, entry in `dropped` |
| Rule doesn't fit the budget | WARNING, entry in `dropped` (D6) |
| Conventions file alone over budget | dispatch fails naming file, size, `project_rules.max_chars` (D6) |
| `git ls-files` fails or times out | dispatch fails with the git error (Special Considerations) |
| No conventions and no rules, non-SDK dispatch | WARNING naming root and step (D7) |
| Step type or provider type missing from a `dispatch_rules.py` table | error naming it |

## Implementation Details

### Migration Plan
- **Moved:** `_FRONTMATTER_RE`, `_PATHS_RE`, `_PATHS_LIST_RE`, `_parse_frontmatter_paths`, `_filename_to_glob`, `load_rules_frontmatter`, `_glob_to_regex`, shell-shebang detection, `match_rules_files`, from `review/rules.py` to `project_rules/frontmatter.py`. `load_rules_frontmatter` returns a `RuleFrontmatter` dataclass (`paths`, `steps`) per file instead of only the path list.
- **Consumers:** `review/rules.py` (`load_review_rules`) imports from the new module. `cli/commands/review_pr.py` and `pipeline/actions/review.py` keep importing `resolve_rules_dir`/`load_review_rules` from `review.rules`, unchanged.
- **Behavior preserved:** the existing `tests/review/test_rules*.py` pass unchanged after import-path updates. For rule files without `steps`, review language-rule selection is identical to today's.

## Integration Points

### Provides to Other Slices
- `select_project_rules(RuleContext) -> ProjectRules` for any future dispatch site, such as an orchestration layer or MCP-driven runs.
- The `project_rules` metadata record and the `conventionsSource` frontmatter key for consumers like cf/Amoeba gating or the run visualizer.

### Consumes from Other Slices
- 267's guidance composition: project rules sit in `instructions`, and the guidance block is still appended after them by the agent.
- 382's `convention_root`: PR reviews read conventions from the trusted checkout, never the scratch worktree.

## Success Criteria

### Functional Requirements
- A non-SDK design, tasks or implement dispatch includes the chosen conventions file and the selected rules in its system prompt. The step's state holds the `project_rules` record.
- With `CLAUDE.md` only, `AGENTS.md` only, both, or neither, the chosen source follows D2, `skipped` lists the unused candidates, and neither file content appears twice.
- A rule with `steps: [implement]` reaches implement dispatches and never design, tasks or review.
- A path-scoped rule reaches implement only when a tracked file matches its `paths`.
- Reviews from an `AGENTS.md`-only project inject `AGENTS.md`. Review frontmatter carries `conventionsSource` and `projectRules`.
- SDK dispatch and SDK session steps record `conventions: sdk-native`, and their prompts are unchanged.
- Over budget: rules are dropped with a WARNING and recorded. A conventions file over budget fails the dispatch with an error naming `project_rules.max_chars`.
- No conventions file and no rules: a non-SDK dispatch logs a WARNING and records `none`.

### Technical Requirements
- Unit tests for selection covering each D3 rule, each D2 case, and the budget paths in D6.
- One test runs selection against squadron's real `.claude/rules/` and real `CLAUDE.md`/`AGENTS.md` and asserts the per-kind result listed in D3 (real-format fixture requirement).
- Frontmatter parser tests: inline and block `steps`, unknown value → error naming the file.
- One test per row of the failure-mode table (Patterns and Conventions), asserting its signal.
- `ruff format`, `ruff check`, and `pyright` with zero errors.

### Integration Requirements
- The dispatch integration test (non-SDK fake provider) asserts the system prompt contains the rules block and the metadata record.
- The review save-target test asserts the new frontmatter keys.

### Verification Walkthrough

Run from a scratch copy so the project's files stay untouched.

1. **Review picks AGENTS.md over CLAUDE.md.**
   ```bash
   cp -R ~/source/repos/manta/squadron /tmp/sq935 && cd /tmp/sq935
   sq review slice 935 --model <non-sdk-alias>
   ```
   The new review file under `project-documents/user/reviews/` has `conventionsSource: AGENTS.md` in its frontmatter.

2. **CLAUDE.md only.** `git rm AGENTS.md` and commit. Rerun step 1. Frontmatter shows `conventionsSource: CLAUDE.md`.

3. **Neither file.** Remove both files, commit, rerun step 1. Frontmatter shows `conventionsSource: none`.

4. **Non-SDK implement dispatch records its rules.** Restore both files (`git reset --hard HEAD~2`). Run an implement pipeline on a non-SDK alias (`sq run implement <slice> --model <non-sdk-alias>`), then:
   ```bash
   jq '.completed_steps[] | select(.step_type=="implement") | .action_results[].metadata.project_rules' \
     ~/.config/squadron/runs/<run-id>.json
   ```
   Expect `conventions: "AGENTS.md"`, `skipped: ["CLAUDE.md"]`, and `rules` containing `python.md` and `testing.md`.

5. **Step relevance.** Add `steps: [implement]` to `.claude/rules/bug-fixes.md` frontmatter. Rerun `sq review slice 935 --model <non-sdk-alias>`. `projectRules` doesn't list `bug-fixes.md`. A design dispatch's record doesn't list it either.

6. **SDK unchanged.** Run any phase step on an SDK alias. Its record is `conventions: "sdk-native"`.

7. **Budget.** `sq config set project_rules.max_chars 5000`, rerun step 4. The run fails, and the error names `AGENTS.md`, its size, and `project_rules.max_chars`. Unset the key afterward.

8. **Codex native loading (D5).** With `AGENTS.md` present, run a codex-profile dispatch. The record shows `AGENTS.md` as `native` with the selected rules injected. Hide `AGENTS.md`, rerun, and the record shows `CLAUDE.md` injected.

## Risk Assessment

### Technical Risks
- **Prompt growth on non-SDK implement:** about 30K characters for squadron (CLAUDE.md plus four rules). This is the point of the slice, and the budget caps it. A small-context model that can't take it fails explicitly instead of losing rules silently.

### Mitigation Strategies
- The D6 budget and explicit failure. A per-alias budget is filed as an issue if a real model needs it.

## Implementation Notes

### Development Approach
1. Move the frontmatter and glob helpers into `project_rules/frontmatter.py`. The review tests should pass with no behavior change. Commit.
2. Add `steps` parsing and the `RuleStep` enum, with parser tests.
3. Add `conventions.py` and switch the review probe to it. Add the frontmatter keys to the save targets.
4. Add `selection.py`, `render.py`, the budget key, and the real-files test.
5. Add `dispatch_rules.py` and wire into `one_shot_dispatch_with_telemetry`: phase steps pass `RULES_STEP_PARAM`; SDK paths record `sdk-native`.
6. Filter review language rules by `steps`.
7. Docs: the rule frontmatter keys and selection table in the rules or pipelines docs, and a CHANGELOG bullet.

### Special Considerations
- Effort: 3/5.
- `git ls-files` for implement runs once per dispatch through `run_git` (bounded timeout). A git failure raises; it never selects zero path rules silently.
- Rule content is project-authored text placed in a system prompt. It comes from the same trust level as the cf prompt, so it needs no sanitizing. PR reviews still read it only from the trusted checkout (382).
