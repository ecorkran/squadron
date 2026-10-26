---
docType: review
layer: project
reviewType: slice
slice: sq-onboard
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/440-slice.sq-onboard.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261025
dateUpdated: 20261025
reviewedSha: 92bdcfc5a699e450f77ca1adfafc31751ad61c1b
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 98897
cachedTokens: 11266
cacheWriteTokens: 87627
completionTokens: 5502
durationSeconds: 48.1
costUsd: 0.407392
costBasis: provider
runId: run-20261026-p4-35b5511c
squadronVersion: 0.24.5
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "D11 adds an unenumerated cf call to every set_slice and widens the guard beyond the architecture"
    location: "project-documents/user/slices/440-slice.sq-onboard.md:226-232"
  - id: F002
    severity: note
    category: error-handling
    summary: "The no-progress stop doesn't cover \"comprehension wrote no doc\" after a declined stale-graph rebuild"
    location: "project-documents/user/slices/440-slice.sq-onboard.md:164-165,219"
  - id: F003
    severity: note
    category: scope
    summary: "Scope is large but matches the architecture's single-slice decision"
    location: "project-documents/user/slices/440-slice.sq-onboard.md:44-61"
  - id: F004
    severity: pass
    category: architecture-alignment
    summary: "Direction rule and file ownership are preserved"
    location: "project-documents/user/slices/440-slice.sq-onboard.md#D3 — The comprehension doc is found by squadron's own name"
  - id: F005
    severity: pass
    category: architecture-alignment
    summary: "Step table, error reader and version refusal match the architecture"
    location: "project-documents/user/slices/440-slice.sq-onboard.md#D1 — The step decision"
  - id: F006
    severity: pass
    category: architecture-alignment
    summary: "Resumability and the PM-gated graph build are handled coherently"
    location: "project-documents/user/slices/440-slice.sq-onboard.md#D2 — The graph gates only until a comprehension doc exists"
---

# Review: slice — slice 440

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] D11 adds an unenumerated cf call to every set_slice and widens the guard beyond the architecture

The architecture (Technical Considerations, retroactive entries) says the pipeline must not start P5 or P6 on a retroactive entry. It also says `retroactive` is read unversioned because it has been stable since cf 263. D11 differs from that in three ways:

- **New I/O call.** `SET_SLICE` now calls `list_slices()` before every `cf set slice`. D7 gives the adoption client a timeout, a version check and an error reader. D11 states no failure handling for this call. It doesn't say what happens if `cf list slices` hangs, times out, returns non-JSON, or returns an entry without `retroactive`. The existing pipeline client has no timeout, since the timeout is wired only into `CfAdoptionClient`. The failure result is implicit.
- **Wider blast radius.** A missing `retroactive` key raises for every `list_slices` caller, not only for `SET_SLICE`. D11 and the Migration Plan accept this, with a CHANGELOG line requiring cf 0.19.18 or later. The architecture did not call for hard-failing unrelated pipeline paths on older cf. State the intended blast radius explicitly, or confine the strict check to the guard.
- **Wider guard.** The slice covers P4 as well as P5 and P6. The slice records the reason, which is that `cf check` already errors on a retroactive entry that has a slice design. The architecture says "P5 or P6", so call this out as a deliberate deviation from it.

Required: add one line each for `list_slices` timeout, bad output, and the missing key. Say whether each fails the action with a logged WARNING+ or ERROR. Add a test for at least one of them.

### [NOTE] The no-progress stop doesn't cover "comprehension wrote no doc" after a declined stale-graph rebuild

The no-progress rule fires when `next.step` equals the step the agent just did. Suppose the PM declined to rebuild a stale graph and the comprehension run then wrote no doc. The report returns `build-graph`, not `comprehension`, so the rule doesn't fire. The agent asks the PM the graph question again. Each loop still needs a PM answer, so it is bounded and not a hang. Still, D10 claims the rule covers "a comprehension run that wrote no doc", and that claim holds only when the graph is fresh. Either narrow the claim or let the rule also fire when the agent has just done `comprehension` and the next step is `build-graph`.

### [NOTE] Scope is large but matches the architecture's single-slice decision

The slice bundles the report, three subcommands, the cf client changes, two agent surfaces, the probe retirement, the retroactive guard and doc updates. The architecture states that these belong in one slice. Nothing in it is unused. The `cf.cli_timeout_s` key and the `--ide` option each serve a named consumer: the timeout bound, and the Codex skill. The "heaviest option" test doesn't apply, because the slice rejects the heavier alternatives for registration (D5) and state storage. No cuts are required. If effort 3/5 proves tight, the retroactive guard (D11) is the most separable piece. It touches the pipeline, not onboard.

### [PASS] Direction rule and file ownership are preserved

- Squadron calls cf and passes the comprehension path in. It never names cf's files.
- The concept comes only from `cf detect`'s `artifacts.concept`.
- Squadron never writes cf's formats.
- D5 settles the registered-check question the architecture left open. It uses `cf project list --json` and does not read cf's store, which meets "must come from cf".

### [PASS] Step table, error reader and version refusal match the architecture

- The D1 table reproduces the architecture's closed step set, with `adoption-incomplete` resolving through the normal rows.
- `already-planned` hands off to `cf next`, with no `done` step.
- D7 implements the one error reader and the per-command `reportVersion` refusal. An unknown `outcome` is also refused, and nothing guesses a step.
- D7 enumerates timeout, non-JSON output, a non-object, other exit codes and cf not installed. Each exits 1 with a one-line stderr message, and tests are named for them.
- The `cwd` and stdout-envelope changes are kept separate from `_run` and `_run_json`, so other callers don't change.

### [PASS] Resumability and the PM-gated graph build are handled coherently

D2 resolves the tension between "a stale graph never forces a rebuild" and "no stored state". It checks the graph only while no comprehension doc exists. The PM's choice is carried by the agent loop within a session, and the next run recomputes from disk. The 'comprehension older than graph' case is reported and kept, as the architecture specifies. The dependency directions are correct: `onboard/` and `pipeline/` depend on `integrations/`, and nothing depends back on the deleted `probe/` package.

### Run Digest

- Response length: 5852 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 3
- Tokens — prompt / cached / cache write / completion / reasoning: 98897 / 11266 / 87627 / 5502 / not computed
- Duration: 48.1 s
- Cost: $0.41 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
