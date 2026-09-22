---
docType: review
layer: project
reviewType: tasks
slice: command-install-target-parity-codex-via-the-agents-skill-layout
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/925-tasks.command-install-target-parity-codex-via-the-agents-skill-layout.md
aiModel: z-ai/glm-5.3
status: complete
dateCreated: 20260922
dateUpdated: 20260922
reviewedSha: 15f3bafdd12ed3480e57d4b9c41ff8172f6ccac4
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 52
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Task 6 breaks the import chain and its own success criteria before Task 7 repairs them"
    location: "project-documents/user/tasks/925-tasks.command-install-target-parity-codex-via-the-agents-skill-layout.md:200-227"
  - id: F002
    severity: concern
    category: architecture
    summary: "`DELIVERIES` in `skills/targets.py` holding layout writers defined in `cli/commands/install.py` creates an import cycle and inverts the layering"
    location: "project-documents/user/tasks/925-tasks.command-install-target-parity-codex-via-the-agents-skill-layout.md:47-48"
  - id: F003
    severity: concern
    category: consistency
    summary: "Task 1's `receipt_name` rule contradicts the design's enumerated four receipt names"
    location: "project-documents/user/tasks/925-tasks.command-install-target-parity-codex-via-the-agents-skill-layout.md:53-54"
  - id: F004
    severity: concern
    category: coverage-gap
    summary: "No task covers the 340-arch / 360-arch amendment lines (explicit success criterion)"
    location: "project-documents/user/tasks/925-tasks.command-install-target-parity-codex-via-the-agents-skill-layout.md:257-278"
  - id: F005
    severity: concern
    category: conventions
    summary: "No commit checkpoints anywhere in the file"
    location: "project-documents/user/tasks/925-tasks.command-install-target-parity-codex-via-the-agents-skill-layout.md"
  - id: F006
    severity: concern
    category: test-design
    summary: "Task 7's name-keying guard test cannot pass today — the pre-existing `anthropic` DOCS_ANCHOR key never appears in `run_all_checks` output"
    location: "project-documents/user/tasks/925-tasks.command-install-target-parity-codex-via-the-agents-skill-layout.md:250"
  - id: F007
    severity: concern
    category: coverage-gap
    summary: "Missing task item: extend `test_no_test_touches_the_real_receipts_directory` to the new `~/.agents/skills` root"
    location: "project-documents/user/tasks/925-tasks.command-install-target-parity-codex-via-the-agents-skill-layout.md:150-178"
  - id: F008
    severity: concern
    category: task-size
    summary: "Task 3 is too large — it is the slice's effort center and should be split"
    location: "project-documents/user/tasks/925-tasks.command-install-target-parity-codex-via-the-agents-skill-layout.md:107-148"
  - id: F009
    severity: pass
    category: coverage
    summary: "Success-criteria coverage is otherwise complete, and no load-test/CI-gating task is required"
    location: "project-documents/user/tasks/925-tasks.command-install-target-parity-codex-via-the-agents-skill-layout.md"
  - id: F010
    severity: pass
    category: sequencing
    summary: "Sequencing correctly closes the D8 hazard before it exists"
    location: "project-documents/user/tasks/925-tasks.command-install-target-parity-codex-via-the-agents-skill-layout.md:73-107"
  - id: F011
    severity: pass
    category: test-structure
    summary: "Test-with pattern and #47 isolation discipline are consistently applied"
    location: "project-documents/user/tasks/925-tasks.command-install-target-parity-codex-via-the-agents-skill-layout.md"
  - id: F012
    severity: pass
    category: scope
    summary: "No scope creep — every task item traces to a design decision"
    location: "project-documents/user/tasks/925-tasks.command-install-target-parity-codex-via-the-agents-skill-layout.md"
  - id: F013
    severity: note
    category: conventions
    summary: "D7's documentation-lookup sub-item handles the hallucination-trap pattern correctly"
    location: "project-documents/user/tasks/925-tasks.command-install-target-parity-codex-via-the-agents-skill-layout.md:107-113"
---

# Review: tasks — slice 0

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3

## Findings

### [CONCERN] Task 6 breaks the import chain and its own success criteria before Task 7 repairs them

Task 6 says "Replace `check_slash_commands` with `check_commands_installed(target, root=None)`" (line 202), but `check_slash_commands` is imported by `src/squadron/cli/commands/setup_steps.py:24` and bound in `_RECHECK_MAP` at `setup_steps.py:56`, and imported by `tests/cli/test_doctor_checks.py:37` (called with a `Path` argument at lines 88-105). The task that repoints the setup tables is Task 7 (line 237). A literal Task 6 therefore leaves `squadron.cli.commands.setup_steps` — and via `setup.py` → `cli/app.py`, the whole `sq` surface — failing to import, and `test_doctor_checks.py` un-collectable, until Task 7 runs. Meanwhile Task 6's own success criteria (line 225: "existing doctor tests pass unchanged") cannot be met: `test_doctor_checks.py` imports the removed symbol at collection time. Task 6 is not independently completable as scoped. Fix: either instruct Task 6 to keep `check_slash_commands` importable until Task 7 repoints the tables (removal lands in Task 7), or fold the `setup_steps.py` repointing into Task 6, and scope "existing tests pass unchanged" to `tests/cli/test_doctor.py` — which I verified drives the Typer app and never imports the symbol, so it genuinely does pass unchanged.

### [CONCERN] `DELIVERIES` in `skills/targets.py` holding layout writers defined in `cli/commands/install.py` creates an import cycle and inverts the layering

Task 1 puts the `DELIVERIES` table (with field `layout: Callable[[Path, Path], list[str]]`) in `src/squadron/skills/targets.py`; Task 2 (line 77) defines the two writers `_write_flat_markdown` / `_write_skill_dirs` in `src/squadron/cli/commands/install.py`. For the table entries to hold those callables, `skills/targets.py` must import from `cli.commands.install`, while Task 2/4 require `install.py` to import `CommandTarget`/`DELIVERIES`/`receipt_name` from `skills.targets` — a module cycle. Today `src/squadron/skills/` imports nothing from `cli/` (verified by grep), and `install.py` already imports downward (`squadron.skills.receipts`, `squadron.skills.models`); `doctor_checks.py:52` even defines `_DEFAULT_COMMANDS_DIR` locally "to keep the pure check layer free of CLI coupling", so this codebase demonstrably guards that direction. Neither task specifies import placement, so a junior implementer either hits `ImportError` (both top-level) or silently inverts the layering (stumbling into a lazy import). Fix with one sentence: define the two writers in `targets.py` (they are copy helpers, not CLI), or make `layout` a key the CLI resolves to a writer, or state explicitly that `install.py` imports `targets` function-locally.

### [CONCERN] Task 1's `receipt_name` rule contradicts the design's enumerated four receipt names

Task 1 specifies `receipt_name(target, local)` "appends `-local` for project-local scope, giving the four names in the design's State Management section", with Claude `receipt_base: squadron-commands` (line 50, correct per D5) and agents `receipt_base: squadron-commands-agents` (line 52). Appending `-local` to those bases yields `squadron-commands-local` and `squadron-commands-agents-local` — but the design (slice design, State Management, line 93) enumerates the four receipts as `squadron-commands`, **`squadron-commands-claude-local`**, `squadron-commands-agents`, `squadron-commands-agents-local`. No single suffix rule on the two given bases reproduces the design's set (appending `-{target}-local` would produce `squadron-commands-agents-agents-local`). Task 1's own test bullet ("`receipt_name` returns the four expected names") is therefore ambiguous about which four, and the receipt filename is load-bearing across install, uninstall, walkthrough step 5, and Task 4's receipt-isolation tests. The breakdown should pick one rule explicitly (e.g., a per-entry `local_receipt_name`, or amending the design's enumeration).

### [CONCERN] No task covers the 340-arch / 360-arch amendment lines (explicit success criterion)

The design's Integration Requirements state "340-arch and 360-arch carry their amendment lines" (slice design line 193), the Migration Plan (line 129) specifies dated amendment lines in `340-arch.skill-pack-infrastructure.md` and `360-arch.document-intelligence.md`, and the Development Approach step 6 lists "arch amendment lines" — but Task 8 covers only QUICKSTART, README, CHANGELOG, the two follow-up issues, and the validation pass. Grep confirms no task in the file mentions 340, 360, or "amendment". A junior implementer following the task file will never add these lines and the slice will fail an explicit integration criterion. Add one sub-item to Task 8 (both arch docs exist at `project-documents/user/architecture/340-arch.skill-pack-infrastructure.md` and `360-arch.document-intelligence.md` — verified present).

### [CONCERN] No commit checkpoints anywhere in the file

CLAUDE.md requires "Git add and commit from project root at least once per task" with semantic prefixes, and every sibling task file I checked (105, 106, 111, 112, 113, 114, 116, 121) carries explicit per-task `Commit:` checklist items (verified by grep). This file contains zero commit or `git add` items in any of its nine tasks — checkpoints are neither distributed nor batched; they are absent. Add a semantic commit sub-item per task (e.g., Task 1: `feat: add command target vocabulary and delivery table`).

### [CONCERN] Task 7's name-keying guard test cannot pass today — the pre-existing `anthropic` DOCS_ANCHOR key never appears in `run_all_checks` output

Task 7's test spec says "Every check name the tables key on exists in some `run_all_checks` output". But `DOCS_ANCHOR` in `src/squadron/cli/commands/setup_steps.py:112` has an `"anthropic"` key, and `BUILT_IN_PROFILES` in `src/squadron/providers/profiles.py:35-76` contains only `openai`, `openrouter`, `local`, `gemini`, `sdk`, `openai-oauth` — `check_provider_profiles` emits rows named by profile, so `"anthropic"` (a user-defined-profile convenience key) never appears on a clean test machine. Every other key in `_RECHECK_MAP`, `DOCS_ANCHOR`, `_EXPLANATION`, and `_TITLE_MAP` does appear (verified against `run_all_checks` in `doctor_checks.py:534-571`). A junior implementing this guard literally will hit a pre-existing failure unrelated to this slice and must choose between silent scope creep (deleting the `anthropic` entry) and an unfixable criterion. Scope the assertion to the two command check names (`slash commands`, `codex skills`), or explicitly instruct removing the stale `anthropic` key as part of the task.

### [CONCERN] Missing task item: extend `test_no_test_touches_the_real_receipts_directory` to the new `~/.agents/skills` root

The design's Special Considerations (slice design line 251) requires: "No test may touch the real `~/.agents/skills` or `~/.config/squadron/receipts` — extend `test_no_test_touches_the_real_receipts_directory` to the new root." That guard exists at `tests/cli/test_install_commands.py:375`, and grep confirms the task file never mentions extending it. The omission is acute exactly where Task 4's new tests run: an agents install invoked with `--ide codex` and no `--target` resolves `~/.agents/skills` from the real `HOME`, which is the precise hazard the guard mechanizes (the same #47/923 discipline the file invokes elsewhere). The tmp_path conventions in the test bullets are good, but the design asked for mechanical enforcement. Add the extension to Task 4's test block.

### [CONCERN] Task 3 is too large — it is the slice's effort center and should be split

Task 3 bundles four distinct deliverables: confirming the `openai.yaml` key, authoring ten `sq-*` skills, authoring two `analysis-*` skills, and writing the full drift-test suite. The authoring surface is large and I verified the sources: `commands/analysis/understand.md` is 1,262+ lines (grep shows a `---` at line 1262), `commands/analysis/tech-debt-audit.md` is ~170, `commands/sq/review.md` ~277, `commands/sq/run.md` ~161 — each requiring per-step argument-prose rewriting per D3, which the design itself calls "the effort center, not the Python." A junior AI in one context will struggle to re-author a 1,262-line file plus eleven others plus a test suite with fidelity. Split into: (3a) the ten `sq-*` skills, (3b) the two `analysis-*` skills + `openai.yaml` pair, with the drift/bijection test landing after 3b (the bijection asserts both directions and can only hold once both halves exist). The per-file sub-items and success criteria are otherwise well specified.

### [PASS] Success-criteria coverage is otherwise complete, and no load-test/CI-gating task is required

Cross-referencing every criterion: all seven functional requirements map to tasks (FR1/FR4 → Task 4; FR2 → Tasks 4+5; FR3 → Tasks 2+4; FR5 → Task 6; FR6 → Task 7; FR7 → Task 9); all technical-requirement tests map (normalization → Task 1; per-target install/receipt isolation/unchanged default → Tasks 2+4; D6 → Task 5; drift bijection → Task 3; stubbed `shutil.which` → Task 6); the two follow-up issues and docs map to Task 8; and all nine verification-walkthrough steps appear in Task 9 (steps 1-5, 8-9 CLI-level; 6 live; 7 fresh-`HOME` setup). The design restates no performance NFR (its technical requirements are pyright/ruff/tests/docs, and the parent 900-slices entry for 925 states none — the only "latency" mention in that document concerns a different slice's fastapi imports), so no `tests/load/` task is needed and the CI-gating criterion is satisfied vacuously. The only uncovered criteria are the two flagged above (arch amendments, receipts-guard extension).

### [PASS] Sequencing correctly closes the D8 hazard before it exists

The one ordering that would break the slice — `commands/agents/` existing while `install_commands` still walks every subdirectory of `commands/` (current behavior at `src/squadron/cli/commands/install.py:73`) — is handled correctly: Task 2 lands the explicit `bundle_subdirs` iteration (plus the `test_agents_tree_is_not_installed_for_claude` guard) *before* Task 3 creates the real `commands/agents/` tree. Task dependencies 1→2→3→4→5→6→7→8→9 are all respected, Task 5 correctly defers D6 until Task 4 mirrors the uninstall flags, and there are no circular *task* dependencies. Task 3 being sequenced before Task 4 (the reverse of the design's Development Approach order) is safe and arguably better: the asset tree exists before the flag that installs it.

### [PASS] Test-with pattern and #47 isolation discipline are consistently applied

Every implementation task (1-7) carries its test block inline immediately after the implementation items, each with concrete, runnable success criteria (`pytest` file targets, `pyright` clean, expected exit codes and messages). The tmp_path/monkeypatched-`HOME` discipline appears in Tasks 1, 4, 5, 6, and 7, including "**Stub it** — never read the host `PATH` (#47)" for the codex detection. Task 3's drift-test verification via "a tmp copy of the tree, not by editing the real bundle" and Task 1's "`~` is expanded at use, not at import" both show real care for the machine-state-isolation problem the project is actively fixing.

### [PASS] No scope creep — every task item traces to a design decision

Each task item maps to a numbered design decision (D1-D9), an API contract clause, a walkthrough step, or an integration requirement. The design's out-of-scope list is respected: `sq skills install --ide` and the `cf` `~/.codex/skills` defect are correctly deferred as the two follow-up issues in Task 8; `copilot`/`cursor` are excluded from the enum per D1; the deprecated flat-prompt format is untouched. Nothing in the file introduces work the design did not ask for.

### [NOTE] D7's documentation-lookup sub-item handles the hallucination-trap pattern correctly

CLAUDE.md warns against placing a hardcoded plausible value next to an instruction to retrieve a value from a possibly-empty source; Task 3's first sub-item does place the design's recorded guess (`policy.allow_implicit_invocation: false`) adjacent to "Check the current Codex skills documentation for the exact key path". However, the same sub-item closes the trap with an explicit stop rule — "if it cannot be confirmed, the task stops and asks the Project Manager rather than guessing" — which is the correct mitigation and mirrors the design's D7 wording. No action required; noting it because the project has a specific rule about this pattern.

## Response (20260922)

All eight concerns verified against the tree and accepted; task file revised (`dateUpdated` 20260922, now 375 lines, ten tasks).

- **F001 — accepted.** Confirmed `check_slash_commands` is imported by `setup_steps.py:24`/`:56` and `tests/cli/test_doctor_checks.py:37`. Task 6 now repoints every importer in the same task and asserts `python -c "import squadron.cli.app"` succeeds before it closes; its "tests pass unchanged" criterion is scoped to `test_doctor.py`, which drives the Typer app and never imports the symbol.
- **F002 — accepted.** Confirmed `src/squadron/skills/` imports nothing from `cli/`. The two layout writers move into `targets.py` (Task 1) where `DELIVERIES` can reference them; Task 2 states the import direction explicitly as CLI → skills.
- **F003 — accepted, resolved in the design.** The irregular name was the design's, not the rule's: `receipt_name` is `receipt_base` + `-local`, and the design's State Management enumeration was corrected from `squadron-commands-claude-local` to `squadron-commands-local`. Task 1 now lists the four names literally.
- **F004 — accepted.** Task 8 gains an item verifying both amendment lines. Note they were already written during the design-review response (commit `2f52d4e2`), so the item is a check-and-correct rather than an authoring job — but the review is right that a junior following only the task file would never have looked.
- **F005 — accepted.** All ten tasks now carry a semantic `Commit:` item.
- **F006 — accepted.** Confirmed `DOCS_ANCHOR` has an `anthropic` key (`setup_steps.py:112`) absent from `BUILT_IN_PROFILES`. The guard is scoped to the two command check names, with the `anthropic` key explicitly left alone as out of scope.
- **F007 — accepted.** Extending `test_no_test_touches_the_real_receipts_directory` to `~/.agents/skills` added to Task 4's test block.
- **F008 — accepted.** Task 3 split into 3a (ten `sq-*` skills) and 3b (two `analysis-*` skills + `openai.yaml` + drift guard), with the bijection test after 3b since it asserts both directions. `commands/analysis/understand.md` at ~1,260 lines is called out as a context session of its own.

F013's note on the hallucination trap: the D7 lookup item no longer restates the candidate key inline — it says the documentation is the authority, with the stop rule retained.

Observation: this review's heading also reads "slice 0" — squadron#28 fixed in `11894797`, unreleased; the review ran on installed 0.13.0.

### Run Digest

- Response length: 15233 chars
- Response is newline-free: no
- Tool calls made: 52
- Tool calls failed: 1
- Stop reason: stop
- Reasoning characters: 105189
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 13
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 13
- Finding-shaped matches — surviving validation: 13
