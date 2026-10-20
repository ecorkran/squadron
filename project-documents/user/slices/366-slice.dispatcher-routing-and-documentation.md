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
turns: 31
promptTokens: 1531878
cachedTokens: 1456722
cacheWriteTokens: 75106
completionTokens: 17803
durationSeconds: 169.5
costUsd: 1.248801
usageRounds: 2
pricedRounds: 2
revision_number: 1
---

# Slice Design: Dispatcher Routing and Documentation

## Overview

The understand skill (`commands/analysis/understand.md`, built by 361–364) is installed today but
reachable only as `/analysis:understand` on Claude Code and `$analysis-understand` on Codex. The
`/sq:analysis` dispatcher, the surface users already know, still lists `tech-debt-audit` as its only
skill. This slice routes `understand` through both dispatchers, makes the missing-graph stop tell the
user how to get the `understand-anything` plugin, and documents the capability and its prerequisite
in the README.

The skill file itself already exists in `commands/analysis/`, and the installer already copies it.
The slice plan's "add the skill file" step is therefore done; this slice adds a test that pins it.

## Value

- Capability (a) becomes reachable from `/sq:analysis`, where users look for analysis skills.
- Context Forge 260's handoff slice and the capability probe (`capability-probe-contract.md`)
  advertise `/sq:analysis understand` as the `claude-code` entry. The contract's Shipping Order
  requires this slice to land first so the probe never reports an entry that does not route.
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
5. README: a "Codebase understanding" subsection under "Skill packs (`sq skills`)" (D4).
6. Tests (D5): installer installs `understand.md`; both dispatchers' valid-skills lines match the
   pack's skill files.
7. CHANGELOG bullet.
8. Amend the two `360-arch` sentences named in D3.

**Excluded:**

- Detecting whether the plugin is installed (D3). The capability probe owns detection.
- README text for `/sq:overview`, deferred to #247 (D4).
- Any installer, manifest, or CLI change. None is needed.
- Changes to flow behavior inside the understand skill.

## Dependencies

### Prerequisites

- 361 (complete): the understand skill and its graph contract exist.
- 362, 363 (complete) and 364 (in progress) add flows. The dispatcher passes the flow argument
  through unchanged, so 366 does not wait on 364.

### Interfaces Required

- 340's dispatcher convention: the first word of `$ARGUMENTS` is the skill name and the rest passes
  through.
- 340's installer: `_install_prefix()` copies every `*.md` in `commands/analysis/`, and the Codex
  target copies every `commands/analysis/agents/*/SKILL.md`.
- The understand skill's flow selection: no argument or `comprehension`, `concept`, `candidates`.

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
```

The direct entries keep working. Only arguments flow through (D2), and nothing holds state.

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
  sync with the skill. A list would also advertise flows before their slice lands, as with
  `candidates` while 364 is in progress.

### D3 — Missing-graph guidance is conditional wording, not plugin detection
Status: decided
- When the graph is absent, the skill already stops. The message now also says: build the graph with
  the plugin's `/understand` (Codex: the `understand` skill); if the plugin is not installed, install
  it with `/plugin marketplace add Egonex-AI/Understand-Anything` then
  `/plugin install understand-anything`. On Codex, install it with upstream's documented command,
  `curl -fsSL https://raw.githubusercontent.com/Egonex-AI/Understand-Anything/main/install.sh | bash -s codex`.
- The skill does not try to work out whether the plugin is installed. The only signal on Claude Code
  is `~/.claude/plugins/installed_plugins.json`, an undocumented Claude Code internal file. A skill
  that reads it breaks whenever Claude Code changes that file. Giving both instructions works whether
  or not the plugin is installed.
- The plugin is only needed when there is no graph. A missing plugin with a graph present is not an
  error, so this message is the only place the guidance belongs.
- The existing "Do not speculate…" sentence is replaced. The wording above states a condition and
  does not guess whether the plugin is installed.
- **Architecture amendment.** This slice amends `360-arch.document-intelligence.md` (Technical
  Scope item 8). In Flow step 1, "Verify the plugin is installed and" is removed. In Non-Goals,
  "The skill detects absence and instructs" becomes "The skill instructs when the graph is absent;
  plugin detection belongs to the capability probe."

### D4 — README documents capability (a) only
Status: decided
- Under "Skill packs", add a short subsection covering what the skill does (it reads an existing
  graph and writes planning documents), the `understand-anything` prerequisite with its install
  commands (D3), and the Codex form. For flows and the skill's other requirements, it links to the
  skill file instead of restating them, so the README cannot drift from the skill.
- `/sq:overview` README text is deferred to #247 because 365 has not shipped. The slice plan
  requires it only "once 365 exists", and 365's design assigns it to 366, so the issue keeps it
  owned.
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
  `analysis-` stripped. Parsing is lenient: take every backtick-quoted token on that line and
  ignore separators and whitespace.
- Sync check for the duplicated text. The same test module defines the two install commands from
  D3 once, as constants. It asserts that each one appears in both understand skill copies and in
  the README.
- `TestBundledAnalysisPack` gains an assertion that `understand.md` is installed and appears in
  `files_written`, which is what the receipt records.

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

## Integration Points

### Provides to Other Slices

- `/sq:analysis understand` and `/sq:analysis understand concept` route. These are the
  `claude-code.entry` and `claude-code.concept` values in the probe contract, and the entry point
  that Context Forge 260's handoff slice uses.
- Unblocks the capability probe (initiative 440), which ships after 366 under the contract's
  Shipping Order.

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

### Technical Requirements

- The drift test (D5) passes for both dispatchers and fails if either dispatcher's valid-skills line
  is missing a pack skill.
- Existing `tests/skills/` and `tests/cli/test_install_commands.py` stay green.
- `ruff format`, `ruff check`, and `pyright` report zero errors.
- README subsection and CHANGELOG bullet are present. The CHANGELOG bullet is user-facing: the
  skill is now reachable as `/sq:analysis understand`, and the missing-graph message explains how to
  install the plugin.

### Integration Requirements

- The `claude-code.entry` and `claude-code.concept` strings in `capability-probe-contract.md` both
  route as written.

### Verification Walkthrough

Run from a squadron checkout with the worktree's venv.

1. Install and confirm the files:
   ```bash
   uv run sq skills install analysis
   ls ~/.claude/commands/analysis/        # tech-debt-audit.md  understand.md
   uv run sq skills install analysis --ide codex
   ls ~/.agents/skills/ | grep analysis   # analysis-tech-debt-audit  analysis-understand
   uv run sq install-commands             # refreshes /sq:analysis dispatcher
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
7. Tests:
   ```bash
   uv run pytest tests/skills tests/cli/test_install_commands.py -q
   ```

## Implementation Notes

### Development Approach

1. Drift test first. It fails against the current dispatchers.
2. Edit the Claude and Codex dispatchers. The test passes.
3. Installer assertion for `understand.md`.
4. Update the skill's absent-graph paragraph in both copies, and fix line 16 in the Claude copy.
5. Add the README subsection and CHANGELOG bullet.
6. Run the walkthrough.

### Special Considerations

- Relative Effort: 1/5.
