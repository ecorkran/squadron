---
docType: slice-design
slice: dispatcher-routing-and-documentation
project: squadron
parent: 360-slices.document-intelligence.md
dependencies:
- 361
interfaces:
- 440
- context-forge-260
dateCreated: 20261020
dateUpdated: 20261020
status: not_started
turns: 48
promptTokens: 2389114
cachedTokens: 2299442
cacheWriteTokens: 89604
completionTokens: 24057
durationSeconds: 231.1
costUsd: 1.658481
usageRounds: 3
pricedRounds: 3
revision_number: 2
---

# Slice Design: Dispatcher Routing and Documentation

## Overview

The understand skill (`commands/analysis/understand.md`, built by 361–364) is installed today but
reachable only as `/analysis:understand` on Claude Code and `$analysis-understand` on Codex. The
`/sq:analysis` dispatcher, the surface users already know, still lists `tech-debt-audit` as its only
skill. This slice routes `understand` through both dispatchers, makes the missing-graph stop tell the
user how to get the `understand-anything` plugin, and documents the capability and its prerequisite
in the README.

It also ships `sq probe --json`, the capability probe that Context Forge 260 runs during brownfield
onboarding, built to `project-documents/user/reference/capability-probe-contract.md` (D6–D11). The
probe was folded into this slice on 20261020 (PM-approved). Shipping both together satisfies the
contract's Shipping Order: the probe never reports an entry that does not route.

The skill file itself already exists in `commands/analysis/`, and the installer already copies it.
The slice plan's "add the skill file" step is therefore done; this slice adds a test that pins it.

## Value

- Capability (a) becomes reachable from `/sq:analysis`, where users look for analysis skills.
- Context Forge 260's handoff slice reads the probe and starts squadron's path through the entries it
  reports. The `claude-code` entry is `/sq:analysis understand`, which routes once this slice lands.
- CF reads one JSON document instead of squadron's install paths, so squadron can move its install
  layout without breaking CF.
- A user with no graph and no plugin gets install instructions instead of a dead end.

## Technical Scope

**Included:**

1. Claude dispatcher `commands/sq/analysis.md`: add `understand` to the valid-skills line, the usage
   block, and a new `## Skill: understand` section.
2. Codex dispatcher `commands/agents/sq-analysis/SKILL.md`: the same three edits, in Codex
   invocation syntax (`$sq-analysis understand`, delegating to `$analysis-understand`).
3. Understand skill, both copies (`commands/analysis/understand.md`,
   `commands/analysis/agents/analysis-understand/SKILL.md`): replace the "Absent" validation
   paragraph that defers plugin reporting to this slice with the install guidance in D3.
4. Claude copy line 16: "When invoked via `/understand`" names the upstream plugin's command, not
   this skill. Change it to `/analysis:understand` (or `/sq:analysis understand`).
5. README: a "Codebase understanding" subsection under "Skill packs (`sq skills`)" (D4), plus one
   line for `sq probe` in the CLI reference.
6. Tests (D5): installer installs `understand.md`; both dispatchers' valid-skills lines match the
   pack's skill files.
7. CHANGELOG bullets for routing and for `sq probe`.
8. Amend `360-arch.document-intelligence.md` as named in D3 (done with this design, 20261020).
9. `sq probe [--json]`: the `squadron.probe` package and the `probe` CLI command (D6–D11), with the
   contract test (D11).
10. Record that the probe ships with this slice in the contract's Shipping Order, the slice plan
    entry, and the initiative plan (done with this design, 20261020).

**Excluded:**

- Plugin detection inside the understand skill (D3). Only the probe detects the plugin (D8).
- README text for `/sq:overview`, deferred to #247 (D4).
- Any installer or manifest change. None is needed.
- Changes to flow behavior inside the understand skill.
- `baseline.available` reporting anything but `false`. Initiative 400 changes it when it ships.

## Dependencies

### Prerequisites

- 361 (complete): the understand skill and its graph contract exist.
- 362, 363 (complete) and 364 (in progress) add flows. The dispatcher passes the flow argument
  through unchanged, so 366 does not wait on 364.
- The probe contract, agreed with CF on 20261020. Field names are frozen at `probe_version` 1.

### Interfaces Required

- 340's dispatcher convention: the first word of `$ARGUMENTS` is the skill name and the rest passes
  through.
- 340's installer: `_install_prefix()` copies every `*.md` in `commands/analysis/`, and the Codex
  target copies every `commands/analysis/agents/*/SKILL.md`.
- `squadron.skills.targets`: `CommandTarget` and `DELIVERIES` (install roots per target).
- `squadron.review.git_utils.run_git`: bounded git calls that distinguish "git could not answer"
  (`None`) from "git refused" (non-zero exit).
- The understand skill's flow selection: no argument or `comprehension`, `concept`, `candidates`.
- The understand skill's graph root and staleness rules (`understand.md`, "Graph location" and
  "Staleness"), which the probe reproduces in Python (D9).

## Architecture

### Component Structure

```
/sq:analysis understand [flow]         $sq-analysis understand [flow]
        │  commands/sq/analysis.md             │  commands/agents/sq-analysis/SKILL.md
        ▼                                      ▼
/analysis:understand [flow]            $analysis-understand [flow]
        │  commands/analysis/understand.md     │  commands/analysis/agents/analysis-understand/SKILL.md
        ▼                                      ▼
   Preflight (graph contract) → Flow selection → Flow

sq probe --json  (src/squadron/cli/commands/probe.py)
        │
        ▼
squadron.probe.build_probe(cwd) ──► surfaces: one SurfaceSpec per CommandTarget (D7, D8)
                               ──► graph: root, meta.json, staleness via run_git (D9)
                               ──► baseline: constant false
```

The direct entries keep working. Only arguments flow through (D2), and nothing holds state. The
probe only reads: it writes nothing and runs only read-only git commands.

## Technical Decisions

### D1 — Route Codex as well as Claude
Status: decided
- Add `understand` to `$sq-analysis` along with `/sq:analysis`. Commands should behave the same on
  every surface, and the edit is three lines.
- The probe contract's `codex.entry` stays `analysis-understand` (direct). Changing it is a contract
  change this slice does not need.
- This goes beyond the delivery stated in the architecture and slice plan, which name only
  `/sq:analysis understand`. The Codex dispatcher already exists and routes `tech-debt-audit`, so
  leaving `understand` out would make Codex the one surface where the dispatcher cannot reach it.

### D2 — Pass the flow argument through without interpreting it
Status: decided
- The dispatcher section says: invoke the skill with the rest of `$ARGUMENTS`. It neither names nor
  validates flows. Usage shows `[flow]` and points to the skill's Flow selection section, the only
  list of flows. Unrecognized flows are rejected there.
- Rejected: listing or validating flows in the dispatcher. Either one is a second list to keep in
  sync with the skill.

### D3 — Missing-graph guidance is conditional wording, not plugin detection
Status: decided
- When the graph is absent, the skill already stops. The message now also says: build the graph with
  the plugin's `/understand` (Codex: the `understand` skill); if the plugin is not installed, install
  it with `/plugin marketplace add Egonex-AI/Understand-Anything` then
  `/plugin install understand-anything`. On Codex, install it with upstream's documented command,
  `curl -fsSL https://raw.githubusercontent.com/Egonex-AI/Understand-Anything/main/install.sh | bash -s codex`.
  Both commands install upstream's current release, matching how the marketplace install behaves;
  the architecture's v2.8.1 is the version the graph contract was verified against, not a pin.
- The skill does not try to work out whether the plugin is installed. A markdown skill reading
  `~/.claude/plugins/installed_plugins.json`, an undocumented Claude Code internal file, breaks
  silently whenever Claude Code changes that file. The probe does read it, in tested Python that
  reports `null` when the file's shape is not what it expects (D8). Giving both instructions works
  whether or not the plugin is installed.
- The plugin is only needed when there is no graph. A missing plugin with a graph present is not an
  error, so this message is the only place the guidance belongs.
- The existing "Do not speculate…" sentence is replaced. The wording above states a condition and
  does not guess whether the plugin is installed.
- **Architecture amendment** (scope item 8), recorded as a dated `*Amendment (20261020, slice
  366)*` note in `360-arch.document-intelligence.md`:
  - Architectural Principles, "Graph is an input, not a dependency": the graph is the input; the
    plugin is needed only to build it. A missing graph stops the run; a missing plugin alone does
    not.
  - Flow step 1 (Preconditions): "Verify the plugin is installed and" is removed.
  - Non-Goals: "The skill detects absence and instructs" becomes "The skill instructs when the graph
    is absent; plugin detection belongs to the capability probe (`sq probe`, slice 366)."
  - Delivery: the Codex dispatcher is edited as well (D1).

### D4 — README documents capability (a) and the probe
Status: decided
- Under "Skill packs", add a short subsection covering what the skill does (it reads an existing
  graph and writes planning documents), the `understand-anything` prerequisite with its install
  commands (D3), and the Codex form. For flows and the skill's other requirements, it links to the
  skill file instead of restating them.
- One line in the CLI reference for `sq probe --json`, pointing to the contract document for fields.
  *Amendment (20261020, task breakdown):* the CLI reference is `docs/COMMANDS.md` (`## probe`);
  the README has no such section and gets a one-line pointer.
- `/sq:overview` README text is deferred to #247 because 365 has not shipped. The slice plan
  requires it only "once 365 exists". The 365 design is amended to name #247 as the owner.
- Also correct "Squadron ships one, `analysis`" so it says what the pack contains:
  `tech-debt-audit` and `understand`.

### D5 — A drift test instead of a routing test
Status: decided
- Routing is markdown that an agent interprets, so no unit test can exercise it. The verification
  walkthrough covers it by hand.
- What can break silently is a skill shipped in the pack but missing from a dispatcher. A test in
  `tests/skills/` reads the `Valid skills:` line of each dispatcher and compares it with the pack's
  skill names, using set equality so the test fails in both directions. Claude's expected set is
  the file stems of `commands/analysis/*.md`. Codex's expected set is the names of the
  `commands/analysis/agents/*/` directories that contain a `SKILL.md`, with the pack prefix
  `analysis-` stripped.
- The `Valid skills:` parser lives in `src/squadron/skills/dispatcher.py` as
  `dispatcher_skills(text) -> set[str] | None`, because the probe uses it too (D7). Parsing is
  lenient: find the line starting with `Valid skills:` (any case, any leading whitespace), take every
  backtick-quoted token on it, ignore separators. `None` means no such line.
- The install commands appear in the README and both skill copies. The test module defines them once
  as constants and asserts each appears in all three.
- `TestBundledAnalysisPack` gains an assertion that `understand.md` is installed and appears in
  `files_written`, which is what the receipt records.

### D6 — Command shape and exit codes
Status: decided
- `sq probe --json` prints the contract object as one compact JSON line on stdout. Without `--json`
  it prints the same object indented, for a human. One builder, two `json.dumps` settings.
- Exit 0 whenever the object is built, however many fields are `null` or `false`. A field the probe
  cannot determine is `null`, and the reason goes to stderr as one WARNING log line, so stdout stays
  pure JSON.
- Any exception that escapes `build_probe` is a probe failure: the CLI command is the process
  boundary, prints the error to stderr, and exits 1. No partial object is printed.
- `PROBE_VERSION = 1` is a module constant. `sq_version` comes from `squadron.__version__`.

### D7 — Surfaces come from `CommandTarget`
Status: decided
- `squadron.probe.surfaces` holds `SURFACES: dict[CommandTarget, SurfaceSpec]`, the same pattern as
  `DELIVERIES`, with an import-time assert that every `CommandTarget` has a surface. `SurfaceSpec`
  carries the contract key (`claude-code`, `codex`), the `entry`, `concept`, and `graph_build`
  strings, and the two detection callables. The contract's strings are defined here once.
- `analysis_skill_installed` checks both the machine root and the project-local root from
  `DELIVERIES[target].resolve_root`, since both runtimes read both. It is true when either scope
  has what the surface's `entry` needs:
  - `claude-code`: `analysis/understand.md` exists, and `sq/analysis.md` exists with
    `understand` in `dispatcher_skills()`. An installed dispatcher from before this slice does not
    route `understand`, so the skill file alone is not enough. A dispatcher with no `Valid skills:`
    line makes the field `null` with a warning, since its shape is not one squadron wrote.
  - `codex`: `analysis-understand/SKILL.md` exists. The Codex entry is the skill itself, so no
    dispatcher is involved.
- *Amendment (20261020, task breakdown):* the project-local root is the project root joined with
  `DELIVERIES[target].local_root`, not `resolve_root(local=True)`, which reads the process cwd and
  is wrong when `sq probe` runs from a subdirectory.

### D8 — Plugin detection
Status: decided
- `codex`: `understand_plugin_installed` is true when `~/.agents/skills/understand/SKILL.md` exists,
  false otherwise. That path is where upstream's `install.sh codex` writes.
- `claude-code`: read `~/.claude/plugins/installed_plugins.json`. The record is installed when a key
  whose name before `@` is `understand-anything` has an entry with `scope` `user`, or any other
  scope with a `projectPath` that resolves to the project root.
  - File absent: `false`. Claude Code writes the file on the first plugin install.
  - File unreadable, not JSON, or missing a `plugins` object of lists: `null` with a warning naming
    what was unexpected. This is where Claude Code changing its internal format shows up, as
    "unknown" and never as a wrong `false`.
- Installed is not enabled. The contract field says installed, and a user who disabled the plugin
  sees the build command fail with Claude Code's own message.

### D9 — Graph and staleness
Status: decided
- The root is `git rev-parse --show-toplevel` from the working directory, falling back to the
  working directory when git cannot answer, the same rule as the understand skill.
- `present`: `<root>/.understand-anything/knowledge-graph.json` is a file. `path`: its absolute path
  when present, `null` when absent.
- `commit`: `gitCommitHash` from `meta.json` beside it, or `null` when `meta.json` is absent,
  unparseable, or has no string `gitCommitHash`. Each reason logs its own warning.
- `commits_behind`, through `run_git`:
  - `commit` equals `git rev-parse HEAD`: 0.
  - `git merge-base --is-ancestor <commit> HEAD` succeeds: `git rev-list --count <commit>..HEAD`.
  - Anything else (not a repository, git unavailable, hash unknown or not an ancestor): `null`.
- The probe does not validate the graph's contents. The skill's Preflight does that when it runs.

### D10 — Package layout
Status: decided
- `src/squadron/probe/__init__.py` exports `build_probe(cwd: Path) -> ProbeReport` and
  `PROBE_VERSION`.
- `src/squadron/probe/report.py`: `TypedDict`s mirroring the contract shape, so pyright checks every
  key.
- `src/squadron/probe/surfaces.py`: D7 and D8. `src/squadron/probe/graph.py`: D9.
- `src/squadron/cli/commands/probe.py`: the Typer command, registered in `app.py`.
- Home and project paths are always resolved at call time, never at import, so tests point `HOME` at
  a temporary directory (#47).

### D11 — Contract test reads the contract
Status: decided
- `tests/probe/test_contract.py` extracts the JSON example from `capability-probe-contract.md` and
  asserts that the real probe output has exactly the same keys at every level and the same JSON
  types, allowing `null` where the contract's table says "or null". A field renamed in code or in the
  document fails the test.
- Unit tests cover each detection rule with a temporary `HOME` and a temporary git repository: the
  three staleness outcomes, a non-repository directory, `meta.json` absent and without a hash, each
  plugin-record case in D8, the pre-366 dispatcher, and a broken builder exiting 1 with nothing on
  stdout.

## Implementation Details

### API Contracts

Dispatcher section to add to `commands/sq/analysis.md`, in the same shape as `tech-debt-audit`:

```
Valid skills: `tech-debt-audit`, `understand`

/sq:analysis understand [flow]

## Skill: understand
Invoke `/analysis:understand` passing the remainder of `$ARGUMENTS` …
(one-paragraph description; flows are defined by the skill's Flow selection; not-installed message)
```

The Codex dispatcher mirrors this with `$sq-analysis` / `$analysis-understand`.

The probe's output is the contract's shape, unchanged. The contract document is the API.

## Integration Points

### Provides to Other Slices

- `/sq:analysis understand` and `/sq:analysis understand concept` route. These are the
  `claude-code.entry` and `claude-code.concept` values in the probe contract, and the entry point
  that Context Forge 260's handoff slice uses.
- `sq probe --json` for Context Forge 260 and the ai-project-guide brownfield prompt. When this
  slice merges, tell `cf` and `ai-project-guide-70`.
- `baseline.available` is the field initiative 400 flips when its baseline ships.

### Consumes from Other Slices

- The understand skill's flow-selection contract (361–364). A new flow added by 364 or later needs
  no dispatcher change (D2).

## Success Criteria

### Functional Requirements

- `/sq:analysis understand` runs the comprehension flow, and `/sq:analysis understand concept`
  reaches the concept flow with the argument intact.
- `$sq-analysis understand [flow]` behaves the same on Codex.
- `/sq:analysis bogus` and `/sq:analysis` with no argument still print the usage block, which now
  lists both skills.
- `/sq:analysis understand bogus` stops with the skill's own "unrecognized" message.
- With no graph present, the skill's stop message names the path it checked, the build command, and
  the plugin install commands for the current surface.
- `sq skills install analysis` writes `tech-debt-audit.md` and `understand.md`, and the receipt
  lists both.
- `sq probe --json` prints one contract-shaped JSON object and exits 0, in a repository with a
  graph, in one without, and outside any repository.
- With the pre-366 dispatcher installed, `surfaces.claude-code.analysis_skill_installed` is false.

### Technical Requirements

- The drift test (D5) passes for both dispatchers and fails if either dispatcher's valid-skills line
  is missing a pack skill.
- The contract test (D11) passes, and fails if a field is renamed on either side.
- Existing `tests/skills/` and `tests/cli/test_install_commands.py` stay green.
- `ruff format`, `ruff check`, and `pyright` report zero errors.
- README subsection, `sq probe` line, and CHANGELOG bullets are present.

### Integration Requirements

- The `claude-code.entry` and `claude-code.concept` strings in `capability-probe-contract.md` both
  route as written.
- Every field name in the probe's output matches the contract. No field is renamed without CF.

### Verification Walkthrough

Run from the worktree with its venv.

1. Install and confirm the files:
   ```bash
   .venv/bin/sq skills install analysis
   ls ~/.claude/commands/analysis/        # tech-debt-audit.md  understand.md
   .venv/bin/sq skills install analysis --ide codex
   ls ~/.agents/skills/ | grep analysis   # analysis-tech-debt-audit  analysis-understand
   .venv/bin/sq install-commands          # refreshes /sq:analysis dispatcher
   ```
2. Usage path. In Claude Code, run `/sq:analysis`, then `/sq:analysis nope`. Both print usage
   listing `tech-debt-audit` and `understand`.
3. Routing. In a repo with a graph (squadron has one in `.understand-anything/`), run
   `/sq:analysis understand`. The skill runs Preflight and starts Flow: Comprehension Analysis.
   Cancel at the write confirmation. Repeat with `concept` and confirm it reaches Flow: Concept
   Generation.
4. Bad flow. Run `/sq:analysis understand nope`. The skill reports the argument is unrecognized.
5. Missing graph. In a scratch git repo with no `.understand-anything/`, run
   `/sq:analysis understand`. The stop message names the checked path, says to run `/understand`,
   and gives the two `/plugin` install commands.
6. Codex. Run `$sq-analysis understand` in Codex and check that it delegates to
   `$analysis-understand`. If Codex is unavailable, record that this step was skipped. The probe
   contract already marks Codex as "not yet run end to end".
7. Probe. In the squadron checkout, run `.venv/bin/sq probe --json | jq .`. Check `graph.commit`
   against `jq -r .gitCommitHash .understand-anything/meta.json` and `graph.commits_behind` against
   `git rev-list --count <that hash>..HEAD`. Check `claude-code.understand_plugin_installed` against
   `/plugin` in Claude Code. Run it again in the scratch repo from step 5 (`graph.present` false,
   `path` null) and in `/tmp` (`commits_behind` null). Each run exits 0.
8. Tests:
   ```bash
   .venv/bin/pytest tests/skills tests/probe tests/cli/test_install_commands.py -q
   ```

## Implementation Notes

### Development Approach

1. Drift test first. It fails against the current dispatchers.
2. Extract `dispatcher_skills()`, edit the Claude and Codex dispatchers. The test passes.
3. Installer assertion for `understand.md`.
4. Update the skill's absent-graph paragraph in both copies, and fix line 16 in the Claude copy.
5. Contract test, then the probe package and CLI command until it passes; then the unit tests.
6. README and CHANGELOG.
7. Run the walkthrough.

### Special Considerations

- Relative Effort: 3/5 (raised from 2/5 when the probe was folded in).
- The probe's field names are a cross-repo contract. Any rename goes to CF before code.
