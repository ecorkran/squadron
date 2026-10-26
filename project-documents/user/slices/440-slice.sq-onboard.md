---
docType: slice-design
slice: sq-onboard
project: squadron
parent: project-documents/user/architecture/440-slices.brownfield-adoption.md
dependencies:
- 366
interfaces: []
dateCreated: 20261025
dateUpdated: 20261026
status: not_started
turns: 70
promptTokens: 5993502
cachedTokens: 5846388
cacheWriteTokens: 146998
completionTokens: 44319
durationSeconds: 423.1
costUsd: 3.232452
usageRounds: 3
pricedRounds: 3
usageByModel:
  claude-opus-5-5:
    rounds: 3
    costUsd: 3.232451599999999
    completionTokens: 44319
revision_number: 2
---

# Slice Design: sq-onboard

## Overview

`sq onboard` adopts an existing repo end to end. It is a read-only report that names the next step of the adoption, three subcommands that make the cf calls, and an agent loop (`/sq:onboard` and the Codex skill `sq-onboard`) that asks for the next step, does it, and asks again until cf reports the project as planned.

The slice also gives `ContextForgeClient` a working directory and a reader for cf's JSON error envelope, folds `sq probe`'s graph and plugin checks into onboard and deletes the probe command, and stops the pipeline from running a phase on a retroactive slice-plan entry.

## Value

- **Users with an existing codebase:** one command takes the repo from nothing to a slice plan cf can navigate. They answer the PM questions and don't need to know the order of the steps or the name of cf's prompt.
- **Resumable:** every call computes the step from what is on disk. A user who stops after the concept and returns later picks up at the adoption prompt.
- **One state for every surface:** the CLI, the Claude command and the Codex skill read the same Python report, so they can't disagree about where an adoption stands.
- **Maintainers:** the deprecated probe contract and its cf-only fields are gone, and squadron's pipeline can't plan or implement recorded history.

## Technical Scope

**Included**
- `sq onboard [--path DIR] [--json]`: the read-only report and the step decision.
- `sq onboard register|decline|prompt [--path DIR]`: the three cf calls.
- `integrations/cf_adoption.py`: a typed client for `cf detect --json`, `cf init --json`, `cf config set adoption.state declined`, `cf prompt get brownfield-adoption`, and `cf project list --json`.
- `ContextForgeClient`: `cwd` and timeout parameters (timeout from the new `cf.cli_timeout_s` key) and a report-call variant that reads cf's error envelope from stdout.
- `commands/sq/onboard.md` and `commands/agents/sq-onboard/SKILL.md`.
- Moving the graph and plugin/skill detection from `squadron/probe/` to `squadron/onboard/`, and deleting the probe package, `sq probe`, its tests and its cf-only fields.
- Marking `capability-probe-contract.md` superseded by this slice. Updating `docs/COMMANDS.md`, `README.md` and `CHANGELOG.md`.
- `SliceEntry.retroactive`, and a refusal in the pipeline's `set_slice` operation for a retroactive entry.

**Excluded**
- Building the graph. The agent runs the understand-anything plugin's own command (360 non-goal).
- The comprehension (362) and concept (363) flows. They are used as they are.
- Writing cf's formats: the derived architecture, the existing-state slice plan and the retroactive marker. The agent writes them from cf's prompt.
- Adoption from a git worktree of a registered project (D5).
- The adoption baseline (404) and initiative candidates (364).

## Dependencies

### Prerequisites
- **366 (complete):** the `sq:analysis understand` routing (`comprehension`, `concept`) and the probe code this slice moves.
- **context-forge 271:** design final at context-forge `93ee3511`, not built. This slice is built against that design with recorded JSON. The live run needs 271 released.
- **context-forge 272 and ai-project-guide #47:** the reworked `brownfield-adoption` prompt that reads the Adoption Inputs section. Needed for the live run only.
- **cf with `retroactive` in `cf list slices --json`** (cf slice 263). The installed cf 0.19.19 emits it on every entry.

### Interfaces Required
From cf (271 design):
- `cf detect --path <root> --json` → D3 report (`reportVersion` 1) or D5 error envelope, exit 1.
- `cf init --json` run in `<root>` → D8 report (`reportVersion` 1, its own constant) with `ok`, or the D5 envelope (`worktree-of-registered-project` and others), exit 1.
- `cf prompt get brownfield-adoption --path <root> --comprehension <path>` → prompt text with an `## Adoption Inputs` section.
- `cf config set adoption.state declined --project <root>` (existing).
- `cf project list --json` (existing): a list of `{ id, name, projectPath?, … }`.

From squadron:
- `probe/graph.py`'s `probe_graph` and `GraphReport`, and `probe/surfaces.py`'s detectors, moved by this slice.
- The comprehension doc convention in `commands/analysis/understand.md`: `project-documents/user/analysis/{index}-analysis.codebase-comprehension.md`, a new index ≥ 940 per run.

## Architecture

### Component Structure

```
src/squadron/integrations/
  context_forge.py      + cwd param, + run_report(), SliceEntry.retroactive   (changed)
  cf_adoption.py        CfAdoptionClient, report dataclasses, AdoptionOutcome,
                        version constants, ADOPTION_PROMPT_KEY               (new)
src/squadron/onboard/
  __init__.py           build_onboard_report(root, cf) → OnboardReport       (new)
  steps.py              OnboardStep, Handoff, decide_step(...) (pure)         (new)
  graph.py              moved from probe/graph.py, minus project_root()       (moved)
  surfaces.py           moved from probe/surfaces.py, minus contract strings  (moved)
  comprehension.py      newest_comprehension(root)                            (new)
src/squadron/probe/                                                           (deleted)
src/squadron/cli/commands/
  onboard.py            typer sub-app: report callback + register/decline/prompt (new)
  probe.py                                                                    (deleted)
src/squadron/pipeline/actions/cf_op.py   SET_SLICE refuses a retroactive entry (changed)
commands/sq/onboard.md                   /sq:onboard agent loop               (new)
commands/agents/sq-onboard/SKILL.md      Codex twin of the loop               (new)
```

`decide_step` is the only place a step is chosen. The CLI report, `/sq:onboard` and the Codex skill all reach it through `sq onboard --json`.

### Data Flow

```
/sq:onboard (agent loop)
   │  1. sq onboard --path <root> --json
   ▼
build_onboard_report(root, cf)
   ├─ cf.detect(root)              → DetectionReport (outcome, artifacts, notices)
   ├─ cf.is_registered(root)       → bool   (cf project list --json)
   ├─ probe_graph(root)            → GraphReport
   ├─ newest_comprehension(root)   → Path | None
   ├─ surface detectors(root)      → per-surface skill/plugin installed
   └─ decide_step(...)             → NextStep(step, reason, handoff)
   ▼
JSON on stdout ─► agent reads next.step and does it:
   ask-adopt     → asks PM → sq onboard register | sq onboard decline
   build-graph   → asks PM → plugin's /understand
   comprehension → /sq:analysis understand comprehension
   concept       → /sq:analysis understand concept
   adopt         → sq onboard prompt → follows the printed prompt
   handoff       → prints the handoff and stops
   │
   └─ back to 1.
```

### State Management

None stored. Each call recomputes the step from cf's detection report, cf's project list, the graph files and squadron's comprehension docs. There is no adoption state file.

## Technical Decisions

### D1 — The step decision
Status: decided
- `OnboardStep` is a `StrEnum`: `handoff`, `ask-adopt`, `build-graph`, `comprehension`, `concept`, `adopt`. `Handoff` is a `StrEnum`: `cf-onboard` (`/cf:onboard`), `cf-next` (`cf next`).
- `decide_step(outcome, registered, graph, comprehension, concept)` checks in this order; the first match wins:

  | # | Condition | Step |
  |---|---|---|
  | 1 | outcome `greenfield` or `opted-out` | `handoff` → `cf-onboard` |
  | 2 | outcome `already-planned` | `handoff` → `cf-next` |
  | 3 | outcome `brownfield` or `adoption-incomplete`, not registered | `ask-adopt` |
  | 4 | no comprehension doc, and graph absent, behind HEAD, or of unknown staleness | `build-graph` |
  | 5 | no comprehension doc | `comprehension` |
  | 6 | cf's `artifacts.concept` is null | `concept` |
  | 7 | otherwise | `adopt` |

- `adoption-incomplete` has no step of its own: rows 3–7 resolve it like any other run. Row 3 includes it because the concept flow and the prompt need a registration, and an unregistered half-adoption is still the PM's choice to adopt.
- A finished adoption is `already-planned` (row 2). Squadron never reads the slice plan to tell an adopted project from any other planned one.

### D2 — The graph gates only until a comprehension doc exists
Status: decided
- The architecture says a stale graph never forces a rebuild; the PM decides. With no stored state, a PM's "keep the stale graph" can't be remembered, so the graph is checked only while there is no comprehension doc (row 4). Once one exists the graph is reported, never gating.
- On `build-graph` the agent tells the PM whether the graph is absent or how many commits behind it is (or that staleness is unknown):
  - Graph absent: on yes, run the plugin's build command. On no, stop: the comprehension flow needs a graph.
  - Graph stale or unknown: on yes, rebuild. On no, go straight to the `comprehension` step without asking `sq onboard` again.
- Unknown staleness (`commits_behind` null on a present graph, for example a commit not on HEAD's history) counts as stale, so the PM is asked rather than the doc being built on a graph nobody checked. The moved `probe_graph` already logs a WARNING naming the cause, and its existing tests assert it.
- If the current surface's understand plugin is not installed, the agent shows how to install it and stops. Squadron never installs the plugin.
- A comprehension doc older than the graph (doc mtime earlier than `knowledge-graph.json` mtime) is reported as `comprehension_older_than_graph: true` and kept. The doc's own provenance block names the graph commit it came from; squadron does not parse it.

### D3 — The comprehension doc is found by squadron's own name
Status: decided
- `newest_comprehension(root)` globs `project-documents/user/analysis/*-analysis.codebase-comprehension.md` and returns the file with the highest leading integer index. Each run takes a new, higher index (understand.md, Index selection), so the highest index is the newest. Files without a leading integer are skipped with a WARNING naming them.
- The analysis directory and the file suffix are module constants in `onboard/comprehension.py`, built on `DOCS_ROOT` from `context_forge.py`. The skill markdown that writes the file is the other place the name appears; markdown can't import a Python constant, so a test reads `commands/analysis/understand.md` and asserts it contains the constant's path.
- The concept is never looked for by squadron. It comes from cf's `artifacts.concept`.

### D4 — The project root is the given directory
Status: decided
- `--path` defaults to `Path.cwd()`, is resolved to an absolute path, and is the root for every cf call, the graph and the comprehension lookup. It is never widened to the git toplevel. `probe/graph.py`'s `project_root()` is deleted with the probe.
- A `--path` that is not an existing directory is an error before any cf call.
- cf calls that act on "the current project" are given the root explicitly, never left to cwd resolution: `cf detect --path`, `cf prompt get --path`, `cf config set --project <root>` (D6), and `cf init` run with `cwd=root`.

### D5 — "Registered" comes from `cf project list --json`
Status: decided
- `is_registered(root)` is true when some entry's `projectPath`, resolved, equals the resolved root. Entries without `projectPath` are skipped. This is cf's own listing; squadron does not read cf's store files.
- Rejected: `cf init --json` as the check. It re-runs guide and command installs on every resumed call. Rejected: `cf get` with `cwd=root`. cf's cwd resolution prefix-matches, so a monorepo subdirectory resolves to its parent project (cf `findProjectByCwd`).
- A git worktree registered with `cf worktree init` is not in the project list, so it reads as unregistered, and `register` gets cf's `worktree-of-registered-project` error. Adoption is run in the primary checkout; the `register` error says so (D8). Adoption in a worktree is excluded from this slice.

### D6 — `decline` passes the root as `--project`
Status: decided
- `cf config set adoption.state declined --project <root>`, run with `cwd=root`. The directory is unregistered when the PM declines, and cf's config command resolves a `--project` value that matches no registered project as a literal directory (cf `resolveConfigProjectPath`). Without the flag, cwd resolution would write to a registered parent project's `.context-forge.toml` in a monorepo.
- The key, `adoption.state`, and the value, `declined`, are constants in `cf_adoption.py`.

### D7 — One report call and one error reader
Status: decided
- `ContextForgeClient.__init__(cwd: Path | None = None, timeout_s: int | None = None)` passes `cwd` and `timeout` to `subprocess.run`. Existing callers pass neither and behave as today.
- **Timeout.** `CfAdoptionClient` builds its client with `timeout_s` from a new config key, `cf.cli_timeout_s` (int, default 300 in `config/keys.py`, its only definition). The default covers `cf init`'s guide download. It applies to every adoption call: `detect`, `project list`, `init`, `config set` and `prompt get`. `subprocess.TimeoutExpired` raises `ContextForgeError` naming the cf command and the timeout, so `sq onboard` exits 1 with that line on stderr instead of stalling the agent loop. One bound for every call is accepted: a hung `cf detect` waits the full bound too, but a hang is the fault being bounded, not the normal case. One test runs a fake `cf` that sleeps past a 1-second timeout and asserts the error and exit 1.
- `ContextForgeClient.run_report(args) -> dict[str, object]` is the JSON-report variant. It does not use `check=True`. On exit 0 or 1 it parses stdout as a JSON object; anything else (other exit codes, non-JSON stdout, a non-object) raises `ContextForgeError` with stderr. `_run` and `_run_json` are unchanged, so no other caller sees a difference.
- `CfAdoptionClient` reads every report through one function, `_checked_report(data, expected_version, command)`:
  1. `reportVersion` must equal `expected_version` (`DETECT_REPORT_VERSION = 1` or `INIT_REPORT_VERSION = 1`). Anything else, including missing, raises `ContextForgeError` naming the command and the value. The version is checked before the envelope, since an unknown version may have a different envelope.
  2. An `error` object raises `ContextForgeReportError(code, message)`, a `ContextForgeError` subclass. The CLI shows `cf <command>: <code>: <message>`.
  3. Otherwise the report is returned for parsing.
- `outcome` is parsed into `AdoptionOutcome` (`StrEnum` of cf's five values). An unknown value raises `ContextForgeError` naming it. Nothing falls back to guessing a step.
- `cf init` failing a step is not an error: the D8 report has `ok: false` and exit 1, and `register` lists the failed steps (D8).

### D8 — Subcommand behavior
Status: decided
- **`register [--path] [--ide TARGET]`** runs `cf init --json` with `cwd=root`, plus `--ide TARGET` when given. The Codex skill passes `--ide agents` so cf configures Codex rather than its default, Claude. The value is passed to cf unvalidated; squadron holds no target list, and cf rejects an unknown one. Output: project name, `created` or `existing`, then one line per step with its status and message. `ok: false` → the failed steps are listed and the exit is 1. `register` never checks registration first; it always runs `cf init`, which is safe on a registered project (`registration: existing`). So re-running it is how a failed or timed-out registration is retried. The report can't offer it again, because the project is already in `cf project list` (D5). The `worktree-of-registered-project` error prints cf's message and the line "Run `cf worktree init` in this directory, or run `sq onboard` in the primary checkout." and exits 1.
- **`decline [--path]`**: D6. Prints one line confirming the opt-out and that `/cf:onboard` treats the project as new.
- **`prompt [--path]`**: finds the newest comprehension doc (D3). None → exit 1 with "No comprehension doc; run the comprehension step first", and cf is not called. Otherwise runs `cf prompt get brownfield-adoption --path <root> --comprehension <doc>` with the doc's absolute path and prints cf's stdout unchanged. The prompt key is `ADOPTION_PROMPT_KEY` in `cf_adoption.py`, its only occurrence in source. A missing prompt or a profile without `fileComprehension` is cf's error, shown as is; there is no fallback prompt.
- All subcommands, and the report, exit 1 with a one-line message when `cf` is not installed (`ContextForgeNotAvailable`).

### D9 — `sq onboard` output
Status: decided
- `--json` prints one JSON object (API Contracts). It has no version field: its only consumers are squadron's own command files, shipped in the same package.
- Without `--json`, it prints the outcome, what exists (registered, graph and staleness, comprehension doc, concept), cf's notices, then `Next: <step>` and its reason. Exit 0 whenever a report is produced, whatever the step.

### D10 — The agent surfaces carry the step instructions; Python carries the state
Status: decided
- `commands/sq/onboard.md` and `commands/agents/sq-onboard/SKILL.md` hold one instruction block per `OnboardStep` and nothing that decides a step. The loop is: run `sq onboard --path <dir> --json`, do the step named in `next.step`, repeat. Each surface names its own commands (`/sq:analysis understand comprehension` vs `analysis-understand comprehension`, `/understand` vs `understand`), and reads its own key under `surfaces` for skill and plugin install state.
- If `register` exits 1, including on a timeout, the agent shows its output, tells the user to fix the cause and re-run `sq onboard register --path <dir>`, and stops.
- **No-progress stop.** If `next.step` is the step the agent has just done, or the agent has just done `comprehension` and `next.step` is `build-graph` (the PM kept a stale graph and no doc was written), the agent reports what it did and what `sq onboard` reported, and stops for the PM instead of repeating the step. This covers an `adopt` that leaves cf at `adoption-incomplete`, a concept the PM declined, and a comprehension run that wrote no doc. A test asserts that both command files contain this rule.
- If the surface's analysis skill is not installed when the step is `comprehension` or `concept`, the agent tells the user to install the analysis pack (`sq skills install analysis`) and stops.
- `ask-adopt` and the graph question are the only PM questions the loop adds. The concept flow asks its own (363), and never overwrites a concept without the PM.
- On `handoff`, the agent prints cf's notices as given and the handoff command, and stops. The instructions contain no example notice text (hallucination trap).
- The command files are delivered by the existing bundles (`sq` and `agents` subdirectories); no installer change.
- `SurfaceSpec` keeps `key` and its two detectors, and drops `entry`, `concept` and `graph_build`. Those strings were contract fields for cf; the command files now hold them.

### D11 — Retroactive entries are refused at `set_slice`
Status: decided
- `SliceEntry` gains `retroactive: bool`, read from each `cf list slices --json` entry. A missing key raises `ContextForgeError` naming the entry and the required cf (slice 263): the installed cf always emits it, and a silent `False` would let the pipeline plan recorded history on an old cf.
- The strict key check applies to every `list_slices` caller, not only the guard. That is deliberate: cf 0.19.18 is the stated minimum, and an older cf fails loudly instead of letting any caller treat recorded history as open work.
- `CfOpAction`'s `SET_SLICE` looks the slice up in `cf_client.list_slices()` before `cf set slice`. This call fails the way every other pipeline cf call does: a non-zero exit or non-JSON output raises `ContextForgeError` and fails the action with that message. It gets no timeout, matching the pipeline's other cf calls; `cf.cli_timeout_s` is scoped to the adoption client. A retroactive entry fails the action with "slice N is a retroactive entry (recorded history, not planned work); phase steps do not run on it". An index not in the list is left to `cf set slice`, as today.
- Every phase step on a slice goes through `set_slice`, so the guard covers P4 as well as P5 and P6. That is broader than the slice plan's "P5 or P6" on purpose: `cf check` already errors on a retroactive entry with a slice design or task file, so a design on one is equally wrong.
- Batch sources need no change. cf derives a checked retroactive entry's status as `complete`, which `_EXCLUDED_STATUSES` already skips. The guard catches an explicitly named slice.
- Prompt-only runs render `cf set slice` as an instruction and call no cf, so they carry no guard. `cf check` remains the check there.

## Implementation Details

### Migration Plan

- **Moved:** `probe/graph.py` with `GraphReport` (from `probe/report.py`) → `onboard/graph.py`, minus `project_root()` (D4); `probe/surfaces.py` → `onboard/surfaces.py`, minus the contract strings (D10); `tests/probe/test_graph.py` and `test_surfaces.py` → `tests/onboard/`.
- **Deleted:** the rest of `squadron/probe/` (`build_probe`, `PROBE_VERSION`, `ProbeReport`, `SurfaceReport`, `BaselineReport`), `cli/commands/probe.py` and its `app.py` registration, `tests/probe/test_contract.py`, `tests/cli/test_probe.py`.
- **Text updated:** `docs/COMMANDS.md` (`probe` section becomes `onboard`), `README.md` line 404, `skills/dispatcher.py`'s docstring, `capability-probe-contract.md` (marked superseded by slice 440), CHANGELOG. The CHANGELOG entry states that cf 0.19.18 or later is now required, because every `list_slices` caller fails without the `retroactive` field (D11).

Nothing outside the probe package imports it. The moved tests show the detectors return the same values for the same root.

### API Contracts

**`sq onboard [--path DIR] [--json]`**

```json
{
  "root": "/abs/path",
  "outcome": "brownfield",
  "registered": true,
  "graph": { "present": true, "path": ".understand-anything/knowledge-graph.json", "commit": "…", "commits_behind": 3 },
  "comprehension": "project-documents/user/analysis/940-analysis.codebase-comprehension.md",
  "comprehension_older_than_graph": false,
  "concept": null,
  "surfaces": {
    "claude-code": { "analysis_skill_installed": true, "understand_plugin_installed": true },
    "codex": { "analysis_skill_installed": false, "understand_plugin_installed": null }
  },
  "notices": [],
  "next": { "step": "concept", "reason": "cf reports no concept", "handoff": null }
}
```

- Paths other than `root` are relative to the root, as cf's are. `comprehension_older_than_graph` is null when either file is absent. `handoff` is a `Handoff` value only when `step` is `handoff`. `reason` strings are constants beside `decide_step`.
- Errors: exit 1, one line on stderr: a cf error envelope (`cf detect: <code>: <message>`), an unknown `reportVersion` or `outcome` naming the value, cf not installed, or `--path` not a directory.

**`sq onboard register [--path DIR] [--ide TARGET]`**, **`decline [--path DIR]`**, **`prompt [--path DIR]`**: D8.

**`CfAdoptionClient`** (constructed with a `ContextForgeClient`):

| Method | cf call | Returns |
|---|---|---|
| `detect(root)` | `cf detect --path <root> --json` | `DetectionReport(outcome, artifacts, notices)` |
| `is_registered(root)` | `cf project list --json` | `bool` |
| `init_project(root, ide)` | `cf init --json [--ide]`, `cwd=root` | `InitReport(project_name, registration, steps, notices, ok)` |
| `decline(root)` | `cf config set adoption.state declined --project <root>`, `cwd=root` | `None` |
| `adoption_prompt(root, comprehension)` | `cf prompt get brownfield-adoption --path <root> --comprehension <path>` | `str` |

`build_onboard_report` takes the client as a parameter (a `Protocol` with these methods), so tests pass a fake that returns recorded cf JSON.

## Integration Points

### Provides to Other Slices
- `sq onboard`, `/sq:onboard` and `sq-onboard`: the brownfield entry point cf points at (271 D6).
- `CfAdoptionClient` and `ContextForgeClient(cwd=…)` / `run_report` for any later cf report call.
- `SliceEntry.retroactive` for any pipeline code that needs it.
- 404, if revived, would be offered after `handoff` → `cf-next` on a project onboard adopted.

### Consumes from Other Slices
- **cf 271:** the three reports. Recorded JSON fixtures in `tests/fixtures/cf_adoption/` are copied from the 271 design's D3, D5 and D8 shapes. If cf ships a different shape under the same `reportVersion`, the live run fails and the fixtures are updated from real output. A different `reportVersion` is refused (D7).
- **362, 363:** run by the agent as they are. Their own preconditions (guide installed, cf registration, never overwriting a concept) stop the loop with their own messages.
- **understand-anything plugin:** detected, never run by squadron.

## Success Criteria

### Functional Requirements
Each item is one test (or one parametrized set) on recorded cf JSON:
- No writes: tree (paths, sizes, mtimes), `.context-forge.toml` and `cf project list --json` match before and after `sq onboard` on an unregistered directory.
- Every row of the D1 table, including each of cf's five outcomes, and a resumed run with a comprehension doc and a concept going to `adopt`.
- D7: unknown `reportVersion` (detect, init), unknown `outcome`, the error envelope from each command, and the timeout.
- D8: `register` on `ok: false` and on `worktree-of-registered-project`; a second `register` after an `ok: false` run calls `cf init` again; `decline`'s cf arguments and `cwd`; `prompt` with the highest-index doc, and with none.
- D4: a monorepo subdirectory is the root for every cf call and the comprehension lookup.
- D11: a retroactive slice fails at `set_slice`; a missing `retroactive` key is an error.
- `sq probe` no longer exists.

### Technical Requirements
- `ruff format`, `ruff check`, `pyright` (zero errors) and the full test suite pass.
- `decide_step` is the only step decision. `ADOPTION_PROMPT_KEY`, the `adoption.state` key and value, and the report versions each appear once in source.
- No squadron code reads cf's project store or names cf's artifact files; the concept comes only from `cf detect`.
- New source files stay under ~300 lines.

### Integration Requirements
- Live, once cf 271 and 272 and ai-project-guide #47 are released: on a real brownfield repo, `/sq:onboard` runs from detect to `already-planned`, and `cf next` then points at the first unbuilt slice. Until then this criterion is open and the slice is not complete.
- The recorded fixtures match the JSON the released cf prints for the same cases.

### Verification Walkthrough

The test suite covers the individual behaviors. These two checks need cf 271 installed; step 2 also needs cf 272 and guide #47 released.

1. **No writes on an unregistered brownfield repo.** Copy a local repo that has code and no `project-documents/`:
   ```bash
   git clone -q <path-to-a-local-brownfield-repo> /tmp/sq440-bf
   (cd /tmp/sq440-bf && git status --short; ls -a) > /tmp/before.txt; cf project list --json > /tmp/proj-before.json
   sq onboard --path /tmp/sq440-bf
   (cd /tmp/sq440-bf && git status --short; ls -a) > /tmp/after.txt; cf project list --json > /tmp/proj-after.json
   diff /tmp/before.txt /tmp/after.txt && diff /tmp/proj-before.json /tmp/proj-after.json && echo unchanged
   ```
   Expect outcome `brownfield`, `Next: ask-adopt`, and `unchanged`.

2. **Live end to end.** In a Claude Code session in `/tmp/sq440-bf`, run `/sq:onboard`. Answer yes to adopt and to the graph build. Expect the loop to run the plugin's `/understand`, write `940-analysis.codebase-comprehension.md`, run the concept flow (confirm the concept), fetch the adoption prompt and write the derived architecture and existing-state plan, then report `already-planned` and hand off. Then `cf next` names the first unbuilt slice. Stop the session after the concept, start a new one, run `/sq:onboard` again, and expect it to resume at `adopt`.

## Risk Assessment

### Technical Risks
- **Contract drift.** The recorded fixtures follow the 271 design; cf 271 is not built. A shape change under the same `reportVersion` passes the tests and fails live.

### Mitigation Strategies
- Version checks refuse a bumped report outright (D7). When 271 ships, regenerate the fixtures from real `cf detect --json` / `cf init --json` output before the live run, and diff them against the recorded ones.

## Implementation Notes

### Development Approach
1. `ContextForgeClient`: `cwd`, `timeout_s` with `cf.cli_timeout_s`, and `run_report`, with tests that exit 1 with an envelope on stdout, with garbage, and that time out.
2. `SliceEntry.retroactive` and the `SET_SLICE` guard (D11).
3. `cf_adoption.py`: dataclasses, `AdoptionOutcome`, `_checked_report`, the five methods; tests on recorded fixtures for every outcome and error code.
4. Move graph and surface code to `onboard/`, delete the probe package and command, move the tests.
5. `comprehension.py`, `steps.py` (`decide_step` table tests), `build_onboard_report`.
6. `cli/commands/onboard.py`: report and subcommands, including the no-writes and monorepo tests.
7. `commands/sq/onboard.md` and `commands/agents/sq-onboard/SKILL.md`.
8. Docs: COMMANDS.md, README, CHANGELOG, the contract doc's superseded marker.
9. Walkthrough step 1 once cf 271 is installed; step 2 once 272 and guide #47 ship.

Effort: 3/5.

### Special Considerations
- **Interim guide.** Until cf 272, the installed `brownfield-adoption` prompt expects the old Adoption Facts section and stops without it. The `adopt` step can't complete live before then; everything up to it can.
- **Recorded JSON is not cf.** Tests use a fake `CfAdoptionClient` or a fake `cf` that returns fixtures, never the user's real cf store, so a test can't register or opt out a real project.
