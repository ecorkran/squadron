---
docType: tasks
slice: sq-onboard
project: squadron
lld: user/slices/440-slice.sq-onboard.md
dependencies:
- 366
projectState: v0.24.5 released; slice 440 design complete (rev 2). cf 271 designed
  (context-forge 93ee3511) but not built. Target is main (git.integration_branch unset).
dateCreated: 20261026
dateUpdated: 20261026
status: in_progress
turns: 34
promptTokens: 2487857
cachedTokens: 2384832
cacheWriteTokens: 102965
completionTokens: 37077
durationSeconds: 378.6
costUsd: 2.042766
usageRounds: 3
pricedRounds: 3
usageByModel:
  claude-opus-5-5:
    rounds: 3
    costUsd: 2.0427668
    completionTokens: 37077
revision_number: 2
---

## Context Summary
- Working on slice 440: `sq onboard`, a read-only adoption report plus `register`, `decline` and `prompt` subcommands, driven by the agent loops `/sq:onboard` and the Codex skill `sq-onboard`. The slice also adds `cwd`, a timeout and `run_report` to `ContextForgeClient`, moves the probe's graph and surface code into `onboard/` and deletes `sq probe`, and refuses retroactive slice-plan entries at the pipeline's `set_slice`.
- Read the slice design (D1–D11, API Contracts, Migration Plan) before starting. Tasks cite decisions by number instead of repeating them.
- Existing code this slice builds on:
  - `src/squadron/integrations/context_forge.py`: `ContextForgeClient` (`_run`, `_run_json`, `list_slices`), `SliceEntry`, `ContextForgeError`, `ContextForgeNotAvailable`, `DOCS_ROOT`. Its tests (`tests/integrations/test_context_forge.py`) patch `subprocess.run`.
  - `src/squadron/config/keys.py`: the `cf.*` keys (`cf.mcp_timeout_s` is the pattern for the new key).
  - `src/squadron/pipeline/actions/cf_op.py`: `CfOperation.SET_SLICE`; tests in `tests/pipeline/actions/test_cf_op.py`.
  - `src/squadron/probe/` (`graph.py`, `report.py`, `surfaces.py`), `cli/commands/probe.py` (registered in `cli/app.py`), `tests/probe/` (with `fixtures/installed_plugins.json`), `tests/cli/test_probe.py`.
  - `commands/analysis/understand.md`: names the comprehension doc `project-documents/user/analysis/{index}-analysis.codebase-comprehension.md`.
  - Command bundles `commands/sq/` and `commands/agents/`; `tests/cli/test_install_commands.py` checks bundle files.
- cf report shapes for the recorded fixtures: the sibling context-forge checkout, `../context-forge/project-documents/user/slices/271-slice.adoption-primitives-for-sq-onboard.md` (read it with `git -C ../context-forge show 93ee3511:project-documents/user/slices/271-slice.adoption-primitives-for-sq-onboard.md` if the working copy has moved on), sections D3 (detect report), D5 (error envelope and codes) and D8 (init report).
- **Slice precondition, not a task:** the design's Integration Requirements and Verification Walkthrough need cf 271 installed (walkthrough step 1) and cf 272 plus ai-project-guide #47 released (step 2), then the fixtures regenerated from real cf output. These are outside what this task list can produce. The task list ends with the work committed on the slice branch; the slice is not complete until the live run passes. Tracked as #273.
- No test may call the real `cf` or touch the user's cf store (design, Special Considerations). Tests use a fake `CfAdoptionClient`, a patched `subprocess.run`, or a fake `cf` script on `PATH` in `tmp_path`.
- Next planned work: per the 440 slice plan.

## Tasks

### Setup

- [x] **T1: Create the slice branch and record the cf fixtures** (Effort 2)
  - [x] Run `cf config get git.integration_branch` (target is its value, or `main` when empty); create `440-slice.sq-onboard` from the target, or switch to it if it exists
  - [x] Create `tests/fixtures/cf_adoption/` with JSON files copied from the cf 271 design shapes (D3, D5, D8), one case per file:
    1. `detect-{outcome}.json` for each of the five outcomes: `greenfield`, `brownfield`, `adoption-incomplete`, `already-planned`, `opted-out`; `adoption-incomplete` has a non-null `artifacts.concept`, the others as D3 shows
    2. `detect-error-path-not-found.json`: the D5 envelope with code `path-not-found`
    3. `init-ok.json` (`registration: created`, all steps `ok` or `skipped`, `ok: true`), `init-existing.json` (`registration: existing`), `init-failed-step.json` (one `guides` step `failed` with a message, `ok: false`), `init-error-worktree.json` (D5 envelope, code `worktree-of-registered-project`)
    4. `project-list.json`: three entries, one with a `projectPath`, one with a different `projectPath`, one without `projectPath`
  - [x] Add a small loader helper (for example `tests/fixtures/cf_adoption/__init__.py` or a function in the tests' `conftest.py`) that reads a fixture by name; tests in later tasks use it
  - [x] SC: every fixture parses as JSON; each detect and init fixture has `reportVersion: 1`
  - [x] SC: commit `test: add recorded cf adoption report fixtures`

### Part A: cf client

- [x] **T2: Add `cf.cli_timeout_s` and `cwd`/`timeout_s` to `ContextForgeClient`** (Effort 2)
  - [x] In `config/keys.py`, add `cf.cli_timeout_s` (int, default 300) beside `cf.mcp_timeout_s`; the description says it bounds each cf CLI call made by `sq onboard`. This is its only definition (D7)
  - [x] `ContextForgeClient.__init__(cwd: Path | None = None, timeout_s: int | None = None)`; `_run` passes both to `subprocess.run` (D7). Callers that pass neither behave exactly as today
  - [x] Catch `subprocess.TimeoutExpired` in `_run` and raise `ContextForgeError` naming the cf command and the timeout in seconds
  - [x] SC: no existing caller changes; `pyright` clean

- [x] **T3: Test `cwd` and the timeout** (Effort 2)
  - [x] In `tests/integrations/test_context_forge.py`:
    1. the default client passes `cwd=None` and `timeout=None` to `subprocess.run` (patched)
    2. a client with `cwd` and `timeout_s` passes both through
    3. a fake `cf` script on `PATH` (in `tmp_path`) that sleeps past a 1-second timeout raises `ContextForgeError` whose message names the command and `1`
  - [x] Add a test in `tests/config/test_keys.py` that `cf.cli_timeout_s` exists with type int and default 300
  - [x] SC: `pytest tests/integrations tests/config` passes
  - [x] SC: `ruff format`, `ruff check`, `pyright` clean; commit `feat: add cwd and timeout to ContextForgeClient`

- [x] **T4: Add and test `ContextForgeClient.run_report`** (Effort 2)
  - [x] `run_report(args) -> dict[str, object]` per D7: runs without `check=True`; on exit 0 or 1 parses stdout as a JSON object and returns it; any other exit code, non-JSON stdout, or a JSON value that is not an object raises `ContextForgeError` including stderr
  - [x] It shares `_run`'s `cwd`, timeout and `ContextForgeNotAvailable` handling (no duplicated subprocess setup); `_run` and `_run_json` keep their current behavior
  - [x] Tests with patched `subprocess.run`:
    1. exit 0 with a JSON object returns it
    2. exit 1 with the D5 envelope on stdout (fixture `detect-error-path-not-found.json`) returns the envelope, not an exception
    3. exit 1 with garbage stdout raises `ContextForgeError` containing stderr
    4. exit 2 with valid JSON raises `ContextForgeError`
    5. a JSON array raises `ContextForgeError`
    6. `cf` missing raises `ContextForgeNotAvailable`
  - [x] SC: `pytest tests/integrations/test_context_forge.py` passes
  - [x] SC: lint and type checks clean; commit `feat: add run_report for cf JSON reports with error envelopes`

- [x] **T5: Add and test `SliceEntry.retroactive`** (Effort 2)
  - [x] `SliceEntry` gains `retroactive: bool`, read in `list_slices` from each entry (D11)
  - [x] A missing `retroactive` key raises `ContextForgeError` naming the entry and that cf with slice 263 (0.19.18 or later) is required. No default value
  - [x] Update every place that constructs `SliceEntry` (source and test helpers) to pass `retroactive`
  - [x] Tests: `true` and `false` are read; a missing key raises `ContextForgeError` whose message names the entry index and the cf requirement
  - [x] The strict check also hits every test that mocks cf `list slices` output. Find them all with `grep -rln "list_slices\|SliceEntry" src tests` (outside `tests/integrations` and `tests/pipeline` this includes `tests/cli`, `tests/events`, `tests/pr`, `tests/review`) and add `retroactive` to each mock
  - [x] SC: the full `pytest` suite passes
  - [x] SC: lint and type checks clean; commit `feat: read the retroactive flag from cf list slices`

- [x] **T6: Refuse a retroactive entry at `SET_SLICE`** (Effort 2)
  - [x] In `cf_op.py`, before `cf set slice`, look the slice index up in `cf_client.list_slices()` (D11). A retroactive entry fails the action with "slice N is a retroactive entry (recorded history, not planned work); phase steps do not run on it"
  - [x] An index not in the list proceeds to `cf set slice` as today. A `ContextForgeError` from `list_slices` fails the action with its message, the way other cf calls in the action fail
  - [x] Define the refusal message once (module constant or format function)
  - [x] SC: no change to other operations; `pyright` clean

- [x] **T7: Test the `SET_SLICE` guard** (Effort 2)
  - [x] Tests in `tests/pipeline/actions/test_cf_op.py`:
    1. a retroactive entry fails the action with the message and `set slice` is not called
    2. a non-retroactive entry calls `set slice` as before
    3. an index absent from the list calls `set slice`
    4. `list_slices` raising `ContextForgeError` fails the action with that message
  - [x] SC: `pytest tests/pipeline` passes
  - [x] SC: lint and type checks clean; commit `feat: refuse phase steps on retroactive slice entries`

### Part B: adoption client

- [x] **T8: Types and the report checker in `cf_adoption.py`** (Effort 3)
  - [x] Create `src/squadron/integrations/cf_adoption.py` with a module docstring citing slice 440 D5–D8 and cf 271 D3/D5/D8
  - [x] Define once, in this module: `DETECT_REPORT_VERSION = 1`, `INIT_REPORT_VERSION = 1`, `ADOPTION_PROMPT_KEY` (`brownfield-adoption`), the `adoption.state` key and the `declined` value
  - [x] `AdoptionOutcome` (`StrEnum` of cf's five outcome values)
  - [x] `ContextForgeReportError(ContextForgeError)` carrying `command`, `code` and `message`; its string is `cf <command>: <code>: <message>` (D7)
  - [x] Frozen dataclasses: `DetectionArtifacts` (`concept`, `derived_architectures`, `existing_state_plan`), `DetectionReport` (`outcome`, `artifacts`, `notices`), `InitStep` (`step`, `status`, `message`), `InitReport` (`project_name`, `registration`, `steps`, `notices`, `ok`)
  - [x] `_checked_report(data, expected_version, command)` implementing D7 steps 1–3 in that order (version before envelope); a missing or different `reportVersion` raises `ContextForgeError` naming the command and the value
  - [x] Parsers from checked dicts to `DetectionReport` and `InitReport`; an unknown `outcome` raises `ContextForgeError` naming the value; a missing required field raises `ContextForgeError` naming it
  - [x] SC: file under ~300 lines; `pyright` clean

- [x] **T9: Test the report checker and parsers** (Effort 2)
  - [x] Create `tests/integrations/test_cf_adoption.py`:
    1. each `detect-{outcome}.json` parses to the matching `AdoptionOutcome`, with artifacts and notices read
    2. `detect-error-path-not-found.json` and `init-error-worktree.json` each raise `ContextForgeReportError` with the fixture's code and message, and its string has the `cf <command>: <code>: <message>` form
    3. `reportVersion` 2, and a missing `reportVersion`, raise `ContextForgeError` naming the value, for both detect and init, including on a payload that also has an `error` object
    4. an unknown `outcome` raises naming it
    5. `init-ok`, `init-existing` and `init-failed-step` parse, with `ok` and step statuses as recorded
  - [x] SC: `pytest tests/integrations/test_cf_adoption.py` passes
  - [x] SC: lint and type checks clean; commit `feat: add cf adoption report types and checker`

- [x] **T10: `CfAdoptionClient` methods** (Effort 3)
  - [x] `CfAdoptionClient` takes the timeout from `cf.cli_timeout_s` and builds a `ContextForgeClient` per call root (`cwd` where D4/D6/D8 require it); construction takes what it needs to be tested without the real config (for example a client factory or the timeout as a parameter)
  - [x] The five methods per the API Contracts table:
    1. `detect(root)`: `cf detect --path <root> --json` through `run_report`, checked with `DETECT_REPORT_VERSION`
    2. `is_registered(root)`: `cf project list --json`; true when an entry's `projectPath`, resolved, equals the resolved root; entries without `projectPath` skipped (D5)
    3. `init_project(root, ide)`: `cf init --json`, plus `--ide <ide>` when given, `cwd=root`, checked with `INIT_REPORT_VERSION`; returns `InitReport` for `ok: false` too
    4. `decline(root)`: `cf config set adoption.state declined --project <root>`, `cwd=root` (D6)
    5. `adoption_prompt(root, comprehension)`: `cf prompt get <ADOPTION_PROMPT_KEY> --path <root> --comprehension <absolute path>`; returns stdout unchanged
  - [x] Define the `Protocol` with these five methods that `build_onboard_report` and the CLI depend on, in `cf_adoption.py` (its one definition; `onboard/` imports it)
  - [x] SC: file under ~300 lines; `pyright` clean

- [x] **T11: Test `CfAdoptionClient`** (Effort 2)
  - [x] Tests with patched `subprocess.run` returning fixtures, asserting exact argv, `cwd` and `timeout` for each method:
    1. `detect` passes `--path <root> --json` and returns the parsed report
    2. `is_registered`: true for the matching `projectPath` (including a non-resolved form of the same path), false for another path, entries without `projectPath` ignored
    3. `init_project` with and without `ide`; `cwd` is the root; `init-failed-step` returns `ok: false` without raising; `init-error-worktree` raises `ContextForgeReportError`
    4. `decline` argv and `cwd`
    5. `adoption_prompt` argv uses the absolute doc path and returns stdout verbatim
    6. the timeout passed to `subprocess.run` is the `cf.cli_timeout_s` value
  - [x] SC: `pytest tests/integrations` passes
  - [x] SC: lint and type checks clean; commit `feat: add CfAdoptionClient for cf detect, init, decline and prompt`

### Part C: move the probe code

- [x] **T12: Move graph and surface code to `onboard/` and delete `sq probe`** (Effort 3)
  - [x] Create `src/squadron/onboard/` with `graph.py` (from `probe/graph.py`, with `GraphReport` from `probe/report.py`, minus `project_root()`, D4) and `surfaces.py` (from `probe/surfaces.py`; `SurfaceSpec` keeps `key` and the two detectors, drops `entry`, `concept`, `graph_build`, D10). `__init__.py` stays minimal until T16
  - [x] Move `tests/probe/test_graph.py`, `tests/probe/test_surfaces.py` and `tests/probe/fixtures/` to `tests/onboard/`; update imports; drop assertions on the removed fields only
  - [x] Delete the rest of `src/squadron/probe/`, `cli/commands/probe.py` and its import and registration in `cli/app.py`, `tests/probe/` (including `test_contract.py`) and `tests/cli/test_probe.py` (Migration Plan)
  - [x] Update `skills/dispatcher.py`'s module docstring to stop naming the probe
  - [x] Add a test that `sq probe` is not a registered command (check the Click/Typer registration, not `--help` text)
  - [x] SC: `grep -rn "squadron.probe\|probe import" src tests` returns nothing
  - [x] SC: moved tests pass unchanged apart from imports and dropped fields, showing the detectors return the same values for the same root; existing `probe_graph` WARNING tests still pass
  - [x] SC: full `pytest` passes; lint and type checks clean; commit `refactor: move graph and surface detection into onboard and delete sq probe`

### Part D: onboard core

- [x] **T13: Add and test `onboard/comprehension.py`** (Effort 2)
  - [x] Module constants for the analysis directory and the file suffix, built on `DOCS_ROOT` (D3)
  - [x] `newest_comprehension(root) -> Path | None`: glob `*-analysis.codebase-comprehension.md` in the analysis directory, return the file with the highest leading integer index; files without a leading integer are skipped with a WARNING naming them
  - [x] Create `tests/onboard/test_comprehension.py`:
    1. none present returns `None`; missing analysis directory returns `None`
    2. `940-…` and `1002-…` present returns `1002` (integer, not lexical, ordering)
    3. a file without a leading integer is skipped and a WARNING naming it is logged (`caplog`)
    4. `commands/analysis/understand.md` contains the constant-built path (D3)
  - [x] SC: `pytest tests/onboard` passes; lint and type checks clean; commit `feat: find the newest comprehension doc for onboard`

- [x] **T14: `onboard/steps.py`** (Effort 2)
  - [x] `OnboardStep` and `Handoff` `StrEnum`s with the D1 values; `NextStep` (`step`, `reason`, `handoff`)
  - [x] `decide_step(outcome, registered, graph, comprehension, concept) -> NextStep`, pure, rows 1–7 of D1 in order; row 4 treats an absent graph, `commits_behind > 0` and `commits_behind` null on a present graph as gating (D2)
  - [x] One reason constant per row beside `decide_step`; `handoff` is set only for `OnboardStep.HANDOFF`
  - [x] SC: `pyright` clean

- [x] **T15: Test `decide_step`** (Effort 2)
  - [x] Create `tests/onboard/test_steps.py` with one parametrized table covering every D1 row, including:
    1. `greenfield` and `opted-out` → `handoff`/`cf-onboard`; `already-planned` → `handoff`/`cf-next`
    2. `brownfield` and `adoption-incomplete` unregistered → `ask-adopt`
    3. no doc with graph absent, behind, and of unknown staleness → `build-graph`; no doc with a current graph → `comprehension`
    4. a doc with a stale graph → not `build-graph` (D2)
    5. doc present, concept null → `concept`; doc and concept present → `adopt` (the resumed run)
    6. `handoff` is null for every non-handoff step
  - [x] SC: `pytest tests/onboard` passes; lint and type checks clean; commit `feat: add the onboard step decision`

- [x] **T16: `build_onboard_report`** (Effort 3)
  - [x] In `onboard/__init__.py`: `OnboardReport` and `build_onboard_report(root, cf) -> OnboardReport`, where `cf` is the T10 `Protocol`. Calls `detect`, `is_registered`, `probe_graph`, `newest_comprehension`, the surface detectors, then `decide_step` (Data Flow)
  - [x] A `to_json` (or equivalent) producing exactly the API Contracts shape: paths other than `root` relative to the root; `comprehension_older_than_graph` true/false from doc vs `knowledge-graph.json` mtime, null when either is absent; `surfaces` keyed by `SurfaceSpec.key`; `notices` from cf
  - [x] It never calls `init_project`, `decline` or `adoption_prompt`
  - [x] SC: file under ~300 lines; `pyright` clean

- [x] **T17: Test `build_onboard_report`** (Effort 2)
  - [x] Create `tests/onboard/test_report.py` with a fake client returning fixture-backed reports and a `tmp_path` root:
    1. the JSON keys and types match API Contracts for a `brownfield` registered root with a graph and a doc
    2. `comprehension_older_than_graph` true, false, and null (doc absent; graph absent)
    3. the fake records that only `detect` and `is_registered` were called
    4. `next` comes from `decide_step` (one resumed-run case: doc and concept → `adopt`)
  - [x] SC: `pytest tests/onboard` passes; lint and type checks clean; commit `feat: build the onboard report`

### Part E: CLI

- [x] **T18: `sq onboard` report command** (Effort 3)
  - [x] Create `src/squadron/cli/commands/onboard.py` as a Typer sub-app whose callback is the report (`invoke_without_command=True`) with `--path` (default `Path.cwd()`, resolved) and `--json`; register it in `cli/app.py`
  - [x] Client seam: the callback sets `ctx.obj` to a `CfAdoptionClient` only when `ctx.obj` is unset, and the report and every subcommand (T20) read the client from `ctx.obj`, typed as the T10 `Protocol`. Tests inject a fake with `CliRunner.invoke(app, args, obj=fake)`; nothing is monkeypatched
  - [x] A `--path` that is not an existing directory exits 1 before any cf call (D4)
  - [x] `--json` prints the T16 JSON; otherwise prints the D9 text (outcome, what exists, notices, `Next: <step>` and reason). Exit 0 whenever a report is produced
  - [x] `ContextForgeError` (including `ContextForgeReportError` and the timeout) and `ContextForgeNotAvailable` exit 1 with one line on stderr (API Contracts, Errors)
  - [x] SC: `pyright` clean

- [x] **T19: Test the report command** (Effort 3)
  - [x] Create `tests/cli/test_onboard.py` using `CliRunner` with a fake adoption client passed as `obj` (T18), never the real cf:
    1. `--json` output parses and matches API Contracts; text output contains `Next: ` and the step
    2. errors: an envelope (`cf detect: <code>: <message>`), unknown `reportVersion`, unknown `outcome`, cf not installed, timeout, `--path` not a directory; each exits 1 with one stderr line
    3. **no writes:** on an unregistered `tmp_path` directory, the tree (paths, sizes, mtimes) and `.context-forge.toml` (absent) are identical before and after, and the fake records no `init_project` or `decline` call
    4. **monorepo (D4):** `--path` set to a subdirectory of a directory that holds a `.context-forge.toml`; every client call receives the subdirectory as its root, and the comprehension lookup uses the subdirectory
  - [x] SC: `pytest tests/cli/test_onboard.py` passes; lint and type checks clean; commit `feat: add the sq onboard report command`

- [x] **T20: `register`, `decline` and `prompt` subcommands** (Effort 3)
  - [x] `register [--path] [--ide TARGET]` per D8: always runs `init_project`; prints project name, `created`/`existing`, one line per step with status and message; `ok: false` lists failed steps and exits 1; `worktree-of-registered-project` prints cf's message and the D8 guidance line and exits 1. `--ide` is passed unvalidated
  - [x] `decline [--path]`: calls `decline`; prints one line confirming the opt-out and that `/cf:onboard` treats the project as new
  - [x] `prompt [--path]`: no comprehension doc → exit 1 with "No comprehension doc; run the comprehension step first", cf not called; otherwise prints `adoption_prompt` output unchanged
  - [x] All three get the client from `ctx.obj` (T18) and share the `--path` validation and error handling with the report (no duplicated handling)
  - [x] SC: `onboard.py` under ~300 lines; `pyright` clean

- [x] **T21: Test the subcommands** (Effort 2)
  - [x] In `tests/cli/test_onboard.py`:
    1. `register` on `init-ok` exits 0 and prints the steps; on `init-failed-step` exits 1 and names the failed step; on `init-error-worktree` exits 1 with the guidance line
    2. a second `register` after an `ok: false` run calls `init_project` again
    3. `register --ide agents` passes `agents` to `init_project`
    4. `decline` passes the root to `decline`
    5. `prompt` uses the highest-index doc's absolute path and prints the client's output verbatim; with no doc, exits 1 and makes no client call
    6. each subcommand exits 1 with one line when cf is not installed
  - [x] SC: `pytest tests/cli/test_onboard.py` passes; lint and type checks clean; commit `feat: add sq onboard register, decline and prompt`

### Part F: agent surfaces

- [x] **T22: `commands/sq/onboard.md`** (Effort 3)
  - [x] Frontmatter matching the other `commands/sq/*.md` files
  - [x] The loop (D10): run `sq onboard --path <dir> --json`, do `next.step`, repeat. One instruction block per `OnboardStep`, each under a `### Step: <value>` heading with the exact `OnboardStep` value, using the Claude Code command names (`/sq:analysis understand comprehension`, `/sq:analysis understand concept`, the plugin's `/understand`) and the `claude-code` key under `surfaces`
  - [x] Include, per D2/D8/D10: the two PM questions (adopt; graph build with absent/behind/unknown wording); plugin not installed → show install and stop; analysis skill not installed → `sq skills install analysis` and stop; `register` exit 1 → show output, say to fix and re-run `sq onboard register --path <dir>`, stop; the no-progress stop rule under a `## No-progress stop` heading; on `handoff`, print cf's notices as given and the handoff command, then stop
  - [x] No step-deciding logic and no example notice text (hallucination trap)
  - [x] SC: the step headings and the no-progress heading are present (checked by T24)

- [x] **T23: `commands/agents/sq-onboard/SKILL.md`** (Effort 2)
  - [x] Frontmatter matching the other `commands/agents/*/SKILL.md` files
  - [x] The same loop, `### Step: <value>` blocks and `## No-progress stop` section as T22, with Codex names (`analysis-understand comprehension`, `analysis-understand concept`, the plugin's `understand`), the `codex` key under `surfaces`, and `sq onboard register --ide agents`
  - [x] SC: the step headings and the no-progress heading are present (checked by T24)

- [x] **T24: Test the agent surfaces** (Effort 2)
  - [x] Tests (in `tests/cli/` beside the other command-file tests) that read both files and assert:
    1. the set of `### Step: <value>` headings in each file equals the set of `OnboardStep` values exactly (no missing, extra or duplicate step)
    2. each file has a `## No-progress stop` heading with a non-empty section under it (D10)
    3. the Codex skill contains `--ide agents`
  - [x] Update `tests/cli/test_install_commands.py` if it lists bundle files, so the new files are covered by the existing install tests
  - [x] SC: `pytest tests/cli` passes; commit `feat: add the /sq:onboard loop and sq-onboard Codex skill`

### Part G: docs and final checks

- [x] **T25: Update docs** (Effort 2)
  - [x] `docs/COMMANDS.md`: replace the `probe` section with `onboard` (report, subcommands, `--json` shape reference, `cf.cli_timeout_s`); fix any links to `#probe`
  - [x] `README.md`: replace the sentence that begins "`sq probe --json` reports what is installed" with one about `sq onboard`
  - [x] `project-documents/user/reference/capability-probe-contract.md`: mark superseded by slice 440 (frontmatter status and a one-line note at the top)
  - [x] `CHANGELOG.md` under Unreleased: short user-facing bullets for `sq onboard` and `/sq:onboard`, removal of `sq probe`, and that cf 0.19.18 or later is now required
  - [x] SC: `grep -rn "sq probe" docs README.md commands` returns nothing; commit `docs: document sq onboard and retire sq probe`

- [x] **T26: Single-definition and no-cf-names checks** (Effort 1)
  - [x] `grep` shows `decide_step` is the only step decision, and `ADOPTION_PROMPT_KEY`'s value, the `adoption.state` key and value, `DETECT_REPORT_VERSION` and `INIT_REPORT_VERSION` each appear once in `src`
  - [x] `grep` of `src/squadron/onboard` and `cf_adoption.py` shows no code reading cf's project store or naming cf's artifact files
  - [x] SC: both checks pass; commit any fixes as `refactor: …` on the slice branch
  - [x] SC: `ruff format`, `ruff check`, `pyright` (zero errors) and the full `pytest` suite pass
