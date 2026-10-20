---
docType: tasks
slice: dispatcher-routing-and-documentation
project: squadron
lld: project-documents/user/slices/366-slice.dispatcher-routing-and-documentation.md
parent: project-documents/user/architecture/360-slices.document-intelligence.md
dependencies:
- 361
projectState: 361–363 complete, 364 in progress. 366 design committed (4b3afa91) with
  the capability probe folded in (PM-approved 20261020). Architecture amendment, contract
  Shipping Order, slice plan and initiative plan updates already done with the design.
  Integration branch is squadron-brownfield.
dateCreated: 20261020
dateUpdated: 20261020
status: not_started
turns: 28
promptTokens: 1926039
cachedTokens: 1824556
cacheWriteTokens: 101433
completionTokens: 32118
durationSeconds: 278.5
costUsd: 1.819242
usageRounds: 2
pricedRounds: 2
revision_number: 1
---

# Tasks: Dispatcher Routing and Documentation

## Context Summary

- Working on slice **366**: route the `understand` skill through both analysis dispatchers
  (`/sq:analysis`, `$sq-analysis`), give install guidance when the graph is missing, document the
  capability, and ship `sq probe [--json]` built to
  `project-documents/user/reference/capability-probe-contract.md`.
- Two halves. Markdown: dispatchers, skill copies, README, COMMANDS, CHANGELOG. Python: the
  `dispatcher_skills()` parser, the `squadron.probe` package, the `probe` CLI command, and tests.
- **The contract's field names are frozen at `probe_version` 1.** Never rename, add, or drop a
  field. If a field looks wrong, write `BLOCKED:` under the task and stop; a rename goes to CF first.
- The dispatchers pass the flow argument through unchanged and never list flows (D2). The skill's
  Flow selection section is the only list of flows.
- The skill does not detect the plugin (D3). Only the probe does (D8).
- Already done with the design, no task here: scope item 8 (architecture amendment in
  `360-arch.document-intelligence.md`) and scope item 10 (Shipping Order, slice plan, initiative
  plan).
- **Command reference location.** The design's "CLI reference" is `docs/COMMANDS.md` (README links
  it as "every command and flag"); the README has no CLI reference section. `sq probe` gets an entry
  in `docs/COMMANDS.md` and a one-line pointer in the README.
- **Both skill copies carry both surfaces' commands.** The absent-graph message gives the Claude Code
  and Codex build/install commands in one paragraph, so each install command appears in the README
  and in both skill copies (D3, D5).
- Post-merge (Phase 7, not a task here): tell `cf` and `ai-project-guide-70` that `sq probe` exists.
- Next planned slice: none in 360 after 366; 365 was dropped (#247 owns `/sq:overview` README text).

### Verified anchors (traced 20261020 on `squadron-brownfield` at `4b3afa91`)

| Anchor | Fact |
|---|---|
| Claude dispatcher | `commands/sq/analysis.md`; `Valid skills: \`tech-debt-audit\`` |
| Codex dispatcher | `commands/agents/sq-analysis/SKILL.md`; same line, `$sq-analysis` syntax |
| Skill, Claude copy | `commands/analysis/understand.md`; line 16 says "When invoked via `/understand`"; "**1. Absent**" paragraph at lines 104–111 |
| Skill, Codex copy | `commands/analysis/agents/analysis-understand/SKILL.md`; "**1. Absent**" at lines 107–114; line 15 already correct |
| Targets | `src/squadron/skills/targets.py`: `CommandTarget` (`CLAUDE`, `AGENTS`), `DELIVERIES`, `TargetDelivery.resolve_root(local=)`; roots `.claude/commands` and `.agents/skills` |
| Git helper | `squadron.review.git_utils.run_git(args, *, cwd: str)` returns `CompletedProcess` or `None` |
| Version | `squadron.__version__` |
| CLI registration | `src/squadron/cli/app.py`, `app.command("<name>")(fn)` pattern |
| Installer test | `tests/skills/test_installer.py:104`, `class TestBundledAnalysisPack` |
| Hermetic HOME | `tests/conftest.py` autouse fixture already points `HOME` at a temp dir per test |
| README | "## Skill packs (`sq skills`)" at line 373; line 375 says "Squadron ships one, `analysis`." |
| Probe package | `src/squadron/probe/` and `tests/probe/` do not exist yet |

## Tasks

### Setup

- [ ] **Task 0: Create the slice branch** (Effort: 1/5)
  - [ ] Confirm this worktree is registered: `cf worktree list --json` has an entry whose
    `worktreePath` equals `git rev-parse --show-toplevel`. If not, write `BLOCKED:` under this task
    and stop; the target `cf` returns belongs to the primary checkout.
  - [ ] Read `cf config get git.integration_branch`; its value (or `main` if empty) is the target.
  - [ ] `git checkout -b 366-slice.dispatcher-routing-and-documentation {target}`, or switch to it
    if it exists.
  - [ ] **Success:** `git branch --show-current` prints
    `366-slice.dispatcher-routing-and-documentation`.

### Dispatcher parser and routing

- [ ] **Task 1: Implement and test `dispatcher_skills()`** (Effort: 1/5)
  - [ ] Create `src/squadron/skills/dispatcher.py` with
    `dispatcher_skills(text: str) -> set[str] | None` (D5).
  - [ ] Find the first line whose stripped, case-folded text starts with `valid skills:`. Return every
    backtick-quoted token on that line as a set; separators (commas, `and`, spaces) are ignored.
    Return `None` when no such line exists.
  - [ ] Module docstring says it reads a dispatcher's `Valid skills:` line and that both the drift
    test and the probe use it.
  - [ ] Create `tests/skills/test_dispatcher.py`. Cases: one skill; two skills comma-separated;
    leading whitespace; lowercase `valid skills:`; `and` as separator; no line → `None`; line with
    no backticks → empty set.
  - [ ] One case reads the real `commands/sq/analysis.md` and asserts `tech-debt-audit` is in the
    result (real-world input, per the parsing rules).
  - [ ] **Success:** `pytest tests/skills/test_dispatcher.py` passes; pyright clean.
  - [ ] Commit: `feat: add dispatcher valid-skills parser`

- [ ] **Task 2: Drift test and dispatcher routing** (Effort: 2/5)
  - [ ] Create `tests/skills/test_dispatcher_drift.py` (D5). Locate files relative to the
    repository root the same way existing `tests/skills/` tests locate `commands/` (read one first).
    1. Claude: expected set is the file stems of `commands/analysis/*.md`; actual is
       `dispatcher_skills()` of `commands/sq/analysis.md`. Assert set equality.
    2. Codex: expected set is the names of `commands/analysis/agents/*/` directories containing a
       `SKILL.md`, with the `analysis-` prefix stripped; actual is `dispatcher_skills()` of
       `commands/agents/sq-analysis/SKILL.md`. Assert set equality.
    3. Assert `dispatcher_skills()` did not return `None` before comparing, with a message naming
       the file.
  - [ ] Run it: both tests fail, each because `understand` is missing from the dispatcher.
  - [ ] Edit `commands/sq/analysis.md`:
    1. Valid skills line: `` `tech-debt-audit`, `understand` ``.
    2. Usage block: add `/sq:analysis understand [flow]` below the existing line.
    3. Add `## Skill: understand` after the tech-debt-audit section, separated by `---`, in the
       same shape: invoke `/analysis:understand` passing the remainder of `$ARGUMENTS`; one
       paragraph saying the skill reads an existing `understand-anything` knowledge graph and
       writes squadron planning documents; `[flow]` is optional and the skill's "Flow selection"
       section defines the valid flows and rejects others; the same not-installed message as
       tech-debt-audit.
    4. Change the Input parsing sentence so the remainder is described as the skill's arguments,
       not only `[target]`.
  - [ ] Edit `commands/agents/sq-analysis/SKILL.md` with the same edits in Codex syntax: usage
    `$sq-analysis understand [flow]`; the section delegates to `$analysis-understand`, passing along
    whatever the user typed after the skill name (D1). Extend the frontmatter `description`, which
    names only the tech debt audit, to cover codebase understanding from a knowledge graph.
  - [ ] Neither dispatcher names or validates any flow (D2).
  - [ ] **Success:** `pytest tests/skills/test_dispatcher_drift.py` passes.
  - [ ] Commit: `feat: route understand through the analysis dispatchers`

- [ ] **Task 3: Pin the installed understand skill** (Effort: 1/5)
  - [ ] In `tests/skills/test_installer.py`, `TestBundledAnalysisPack`, add a test that installing
    the bundled `analysis` pack creates `analysis/understand.md` and lists `understand.md` in
    `result.files_written`. Follow the existing tech-debt-audit test's shape.
  - [ ] **Success:** `pytest tests/skills/test_installer.py` passes.
  - [ ] Commit: `test: assert analysis pack installs understand`

### Missing-graph guidance

- [ ] **Task 4: Install guidance in both skill copies** (Effort: 2/5)
  - [ ] In `commands/analysis/understand.md`, line 16: change "When invoked via `/understand`" to
    "When invoked via `/analysis:understand` or `/sq:analysis understand`".
  - [ ] In the Claude copy, replace the second paragraph of "**1. Absent**" (from "State only that
    the graph is missing" through "wrong as often as right.") with the D3 guidance. Keep the first
    paragraph (report the checked path, the graph comes from the plugin's `/understand`). The new
    paragraph holds both surfaces' commands, states them as a condition, and does not guess whether
    the plugin is installed:
    1. Build the graph with the plugin's `/understand` (on Codex, the `understand` skill).
    2. If the plugin is not installed, on Claude Code run
       `/plugin marketplace add Egonex-AI/Understand-Anything` then
       `/plugin install understand-anything`.
    3. If the plugin is not installed, on Codex run
       `curl -fsSL https://raw.githubusercontent.com/Egonex-AI/Understand-Anything/main/install.sh | bash -s codex`.
    4. The stop message the agent prints includes the build and install commands for the surface it
       is running on; the file itself always keeps both.
  - [ ] Each command appears verbatim, in backticks, on one line. Remove the reference to
    "slice 366's scope"; no slice numbers in the protocol text.
  - [ ] Apply the same replacement to `commands/analysis/agents/analysis-understand/SKILL.md`,
    wording identical except where the copy already uses Codex invocation syntax. Its line 15 needs
    no change.
  - [ ] Create `tests/skills/test_understand_install_guidance.py`. Define the three install commands
    once as module constants. Parametrize over both skill copies and assert each constant appears in
    each file. Task 10 adds `README.md`.
  - [ ] **Success:** the test passes; `grep -n "slice 366"` on both copies prints nothing; the
    absent stop still says to report the checked path.
  - [ ] Commit: `feat: give understand-anything install guidance when the graph is absent`

### Probe package

- [ ] **Task 5: Report types and graph detection** (Effort: 2/5)
  - [ ] Create `src/squadron/probe/report.py` with `TypedDict`s mirroring the contract shape (D10):
    `SurfaceReport` (`analysis_skill_installed: bool | None`, `entry: str`, `concept: str`,
    `understand_plugin_installed: bool | None`, `graph_build: str`), `GraphReport` (`present: bool`,
    `path: str | None`, `commit: str | None`, `commits_behind: int | None`), `BaselineReport`
    (`available: bool`), `ProbeReport` (`probe_version: int`, `sq_version: str`,
    `surfaces: dict[str, SurfaceReport]`, `graph: GraphReport`, `baseline: BaselineReport`).
    Docstring names the contract document as the source of truth.
  - [ ] Create `src/squadron/probe/graph.py` (D9) with two functions:
    1. `project_root(cwd: Path) -> Path`: `run_git(["rev-parse", "--show-toplevel"], cwd=str(cwd))`;
       on `None` or non-zero exit, return `cwd`. This is the only place the root rule lives; Task 8
       reuses it.
    2. `probe_graph(root: Path) -> GraphReport`, given the root from `project_root`.
  - [ ] `present`: `<root>/.understand-anything/knowledge-graph.json` is a file. `path`: its absolute
    path as a string when present, else `None`.
  - [ ] `commit`: `gitCommitHash` from `meta.json` beside the graph. `None` with its own WARNING log
    line for each of: `meta.json` absent, not valid JSON, no string `gitCommitHash`.
  - [ ] `commits_behind`: `None` when `commit` is `None`. Else `rev-parse HEAD` equal to `commit` → 0;
    else `merge-base --is-ancestor <commit> HEAD` exit 0 → `rev-list --count <commit>..HEAD` as int;
    anything else (`None` result, non-zero exit, unparseable count) → `None` with a WARNING naming
    which.
  - [ ] Module logger (`logging.getLogger(__name__)`). Write nothing; run only these read-only git
    commands. Do not read the graph's contents.
  - [ ] Create `tests/probe/__init__.py` and `tests/probe/test_graph.py`. Build temporary git repos
    with real `git init` and commits (hermetic git config is already applied by `tests/conftest.py`).
    Cases: graph at HEAD → `commits_behind` 0; graph two commits behind → 2; `gitCommitHash` not an
    ancestor (a fabricated 40-hex string) → `None`; non-repository directory with a graph → root is
    `cwd`, `present` true, `commits_behind` `None`; no graph → `present` false, `path` `None`;
    `meta.json` absent, without `gitCommitHash`, and not JSON → `commit` `None` each.
  - [ ] Each `None` case asserts a WARNING record via `caplog`. One case calls `project_root` from a
    subdirectory and asserts the repository root.
  - [ ] **Success:** `pytest tests/probe/test_graph.py` passes; pyright clean.
  - [ ] Commit: `feat: add probe graph and staleness detection`

- [ ] **Task 6: Surface specs and skill detection** (Effort: 3/5)
  - [ ] Create `src/squadron/probe/surfaces.py` (D7). A frozen dataclass `SurfaceSpec` with the
    contract key, `entry`, `concept`, `graph_build`, and two callables:
    `analysis_skill_installed(project_root: Path) -> bool | None` and
    `understand_plugin_installed(project_root: Path) -> bool | None` (the latter filled in Task 7).
  - [ ] `SURFACES: dict[CommandTarget, SurfaceSpec]` with an import-time
    `assert set(SURFACES) == set(CommandTarget)`, matching the `DELIVERIES` pattern. The contract
    strings are copied exactly from the contract's Shape block and defined only here.
  - [ ] Skill detection checks the machine root `DELIVERIES[target].resolve_root(local=False)` and
    the project root joined with `DELIVERIES[target].local_root`. Deviation from D7's wording:
    `resolve_root(local=True)` reads `Path.cwd()`, which is wrong when `sq probe` runs from a
    subdirectory; say so in a comment. Combine: any scope `True` → `True`; else any `None` → `None`;
    else `False`.
    1. `claude-code`, per scope: `analysis/understand.md` exists and `sq/analysis.md` exists and
       `"understand" in dispatcher_skills(...)`. A dispatcher for which `dispatcher_skills` returns
       `None` → `None` with a WARNING naming the file.
    2. `codex`, per scope: `analysis-understand/SKILL.md` exists.
  - [ ] Create `tests/probe/test_surfaces.py`. Populate the temp `HOME` and a temp project root.
    1. Claude: nothing installed → `False`; skill file and post-366 dispatcher at machine scope →
       `True`; same at project scope only → `True`; pre-366 dispatcher (only `tech-debt-audit`)
       plus skill file → `False`; dispatcher with no `Valid skills:` line → `None` with a WARNING;
       skill file without dispatcher → `False`.
    2. Codex: absent → `False`; machine scope → `True`; project scope → `True`.
    3. Every `CommandTarget` has a `SURFACES` entry; the contract keys are `{"claude-code", "codex"}`.
  - [ ] **Success:** `pytest tests/probe/test_surfaces.py` passes; pyright clean.
  - [ ] Commit: `feat: add probe surface specs and skill detection`

- [ ] **Task 7: Plugin detection** (Effort: 2/5)
  - [ ] In `surfaces.py`, add the two `understand_plugin_installed` callables (D8), resolving `HOME`
    at call time.
  - [ ] `codex`: `True` when `~/.agents/skills/understand/SKILL.md` exists, else `False`.
  - [ ] `claude-code`: read `~/.claude/plugins/installed_plugins.json`.
    1. File absent → `False`.
    2. Unreadable, not JSON, or no `plugins` object whose values are lists → `None` with a WARNING
       naming what was unexpected.
    3. Installed when a key whose part before `@` is `understand-anything` has an entry with
       `scope` `user`, or any other scope whose `projectPath` resolves to the project root.
       Otherwise `False`.
  - [ ] Catch only `OSError` and `json.JSONDecodeError`, each with a comment saying why it becomes
    `None`.
  - [ ] Add `tests/probe/fixtures/installed_plugins.json` in the real file's format, observed
    20261020: top-level `version` (int) and `plugins`, an object keyed `name@marketplace` whose
    values are lists of entries with `scope`, `installPath`, `version`, `installedAt`,
    `lastUpdated`, `gitCommitSha`, and `projectPath` on non-user scopes. Copy the structure from
    `~/.claude/plugins/installed_plugins.json`; replace paths and hashes with obvious placeholders.
    Include a user-scope `understand-anything@understand-anything` entry and a project-scope entry
    for another plugin.
  - [ ] Tests in `tests/probe/test_surfaces.py`:
    1. The fixture copied into the temp `HOME` → `True`.
    2. Synthetic variants: file absent → `False`; project-scope entry for this project → `True`;
       project-scope entry for another path → `False`; other plugins only → `False`; not JSON,
       `plugins` missing, `plugins` value not a list → `None` + WARNING each.
    3. Codex: `understand/SKILL.md` present → `True`; absent → `False`.
  - [ ] **Success:** `pytest tests/probe/test_surfaces.py` passes; pyright clean.
  - [ ] Commit: `feat: add probe plugin detection`

- [ ] **Task 8: `build_probe` and the contract test** (Effort: 2/5)
  - [ ] Create `src/squadron/probe/__init__.py` exporting `PROBE_VERSION = 1` and
    `build_probe(cwd: Path) -> ProbeReport` (D6, D10). It calls `project_root(cwd)` once, builds
    `surfaces` from `SURFACES` keyed by each spec's contract key, `graph` from `probe_graph(root)`,
    `baseline` as `{"available": False}`, and `sq_version` from `squadron.__version__`.
  - [ ] Create `tests/probe/test_contract.py` (D11). Read
    `project-documents/user/reference/capability-probe-contract.md`, extract the ```` ```json ````
    block under "## Shape", parse it.
  - [ ] Parse the field table: rows whose Type column contains `or null` name the nullable fields.
    Fail the test if no such rows are found (a silent empty set would pass everything).
  - [ ] Assert `build_probe(tmp_path)` output has exactly the example's keys at every level, and each
    value's JSON type matches the example's, allowing `null` for nullable fields. Treat example
    values of `"string or null"` as type string.
  - [ ] Assert `probe_version == PROBE_VERSION == 1` and the `entry`, `concept`, `graph_build`
    values equal the example's exactly.
  - [ ] **Success:** passes; renaming a key in the contract's example (try once by hand, then
    restore) makes it fail.
  - [ ] Commit: `feat: add build_probe and contract test`

- [ ] **Task 9: The `sq probe` command** (Effort: 1/5)
  - [ ] Create `src/squadron/cli/commands/probe.py` with a `probe` Typer command and a `--json` flag
    (D6). Register it in `src/squadron/cli/app.py` as `app.command("probe")(probe)`.
  - [ ] `--json`: `json.dumps(report, separators=(",", ":"))` on one line. Without: `indent=2`.
  - [ ] This is a process boundary: wrap `build_probe` so any exception prints the error to stderr
    and exits 1 with nothing on stdout. Exit 0 otherwise. WARNING log lines go to stderr, never
    stdout.
  - [ ] Create `tests/cli/test_probe.py` using `CliRunner` (see `tests/cli/conftest.py`). Cases:
    `--json` stdout is one line that parses as JSON and exits 0; without `--json` output is
    multi-line and parses to the same object; `build_probe` patched to raise → exit 1, stdout empty,
    error on stderr; a run that logs a WARNING keeps stdout pure JSON.
  - [ ] **Success:** `pytest tests/cli/test_probe.py` passes; `.venv/bin/sq probe --json | jq .`
    parses; `sq --help` lists `probe`.
  - [ ] Commit: `feat: add sq probe command`

### Documentation

- [ ] **Task 10: README, COMMANDS, CHANGELOG** (Effort: 2/5)
  - [ ] README line 375: replace "Squadron ships one, `analysis`." with a sentence saying it ships
    `analysis`, containing `tech-debt-audit` and `understand`.
  - [ ] Add `### Codebase understanding` under "Skill packs" (D4): reads an existing
    `understand-anything` graph and writes planning documents; run `/sq:analysis understand`
    (Codex: `$sq-analysis understand`); prerequisite plugin with the three install commands from
    Task 4 verbatim; build the graph first with `/understand`; link to
    `commands/analysis/understand.md` for flows and other requirements. Do not list flows. No
    `/sq:overview` text (#247).
  - [ ] In that subsection, one line: `sq probe --json` reports what is installed and the graph's
    state, with a link to `docs/COMMANDS.md#probe`.
  - [ ] `docs/COMMANDS.md`: add `## probe` matching neighbouring entries' format: the `--json`
    flag, exit codes (0 when it can report, 1 when the probe fails), and a link to the contract
    document for fields.
  - [ ] Extend Task 4's test so `README.md` is a third parametrized file.
  - [ ] CHANGELOG, under `## [Unreleased]`, `### Added`: one bullet for `/sq:analysis understand`
    and `$sq-analysis understand`, plus install guidance when no graph exists; one bullet for
    `sq probe --json`. Short and user-facing.
  - [ ] **Success:** `pytest tests/skills/test_understand_install_guidance.py` passes with three
    files.
  - [ ] Commit: `docs: document codebase understanding and sq probe`

### Verification

- [ ] **Task 11: Run the verification walkthrough** (Effort: 2/5)
  - [ ] Follow the slice design's Verification Walkthrough steps 1–8 from the worktree venv.
  - [ ] Steps 2–5 run in Claude Code. Cancel at the skill's write confirmation in step 3; nothing
    is written.
  - [ ] Step 5 uses a scratch git repo under `/tmp`, never this checkout.
  - [ ] Step 6: if Codex is not available, record "skipped: Codex unavailable" under this task.
  - [ ] Step 7: if `/plugin` cannot be run from the agent, record that and compare
    `understand_plugin_installed` against the `understand-anything` key in
    `~/.claude/plugins/installed_plugins.json` read by hand.
  - [ ] Record each step's outcome as a one-line sub-bullet under this task.
  - [ ] **Success:** every non-skipped step matches the design's expected result; every
    `sq probe` run exits 0.
  - [ ] Commit: `docs: record slice 366 walkthrough results`

- [ ] **Task 12: Final validation** (Effort: 1/5)
  - [ ] `ruff format`, `ruff check`, `pyright` (zero errors).
  - [ ] `.venv/bin/pytest tests/skills tests/probe tests/cli/test_install_commands.py tests/cli/test_probe.py -q`
    passes, then the full suite.
  - [ ] Every file in `src/squadron/probe/` is under ~300 lines.
  - [ ] Commit any formatting changes: `style: format slice 366 changes`. The slice ends at a
    commit on the slice branch.
