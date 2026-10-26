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
reviewedSha: 1550e5d80c0ad4407c40a33430914cb0496c11d1
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 98591
cachedTokens: 11266
cacheWriteTokens: 87321
completionTokens: 5362
durationSeconds: 46.7
costUsd: 0.404768
costBasis: provider
runId: run-20261026-p4-35b5511c
squadronVersion: 0.24.5
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Partial or timed-out registration is unrecoverable by the resume loop"
    location: "project-documents/user/slices/440-slice.sq-onboard.md:180-184"
  - id: F002
    severity: concern
    category: error-handling
    summary: "The agent loop has no stop condition when a step makes no progress"
    location: "project-documents/user/slices/440-slice.sq-onboard.md:215-221"
  - id: F003
    severity: note
    category: scope
    summary: "Retroactive guard covers P4 as well as P5 and P6"
    location: "project-documents/user/slices/440-slice.sq-onboard.md:228"
  - id: F004
    severity: note
    category: integration
    summary: "A missing `retroactive` key is a hard error for every `list_slices` caller"
    location: "project-documents/user/slices/440-slice.sq-onboard.md:226"
  - id: F005
    severity: note
    category: proportionality
    summary: "The new `cf.cli_timeout_s` key and the single 300s timeout are slightly heavier than needed"
    location: "project-documents/user/slices/440-slice.sq-onboard.md:194"
  - id: F006
    severity: pass
    category: architecture-alignment
    summary: "Alignment with the architecture"
    location: "project-documents/user/slices/440-slice.sq-onboard.md#Technical Decisions"
---

# Review: slice — slice 440

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Partial or timed-out registration is unrecoverable by the resume loop

D5 rejects `cf init` as the registration check because it re-runs installs. That makes "registered" mean "present in `cf project list`", and a project can be in that list after `cf init` only partly finished. D8 says `register` lists failed steps and exits 1 when the report has `ok: false`. D7 says a timeout makes `sq onboard` exit 1. After either, the next `sq onboard` call sees `registered: true` and skips `ask-adopt`, so the loop never offers `register` again. The failed guide or command install is not retried. The step then surfaces later as the concept flow's own precondition message ("guide installed"), which doesn't point back to `register`. D10's instruction block for `ask-adopt` doesn't say what the agent does when `register` fails.

State the recovery explicitly:
- On `register` failure or timeout, the agent reports the failed steps and tells the user to re-run `sq onboard register` (it is idempotent per the architecture). It then stops instead of looping.
- Add a test or criterion for the resumed run after a failed `register`.

### [CONCERN] The agent loop has no stop condition when a step makes no progress

D10 defines the loop as "run `sq onboard --json`, do the step, repeat". Python holds no state, so nothing detects a step that was done but didn't change the outcome. Examples:
- The agent follows the adoption prompt but cf still reports `adoption-incomplete`, so `adopt` is returned again.
- The PM declines the concept inside 363's flow, so `concept` is returned again.
- The comprehension flow fails to write a doc, so `comprehension` is returned again.

Each case can loop on LLM spend indefinitely. The Python-decides design is right, but the command files need one rule. If `next.step` is the same after the agent has just completed it, the agent reports what it did and stops for the PM. Add it to the D10 instruction blocks. A test that the command files contain this rule would cover it, like the D3 path assertion.

### [NOTE] Retroactive guard covers P4 as well as P5 and P6

The architecture says the pipeline "must not start P5 or P6" on a retroactive entry. D11 guards every phase step through `set_slice`. D11 gives the reason: `cf check` already rejects a design on a retroactive entry. The widening is small, consistent with cf, and deliberate, so I'm not raising it as a finding.

### [NOTE] A missing `retroactive` key is a hard error for every `list_slices` caller

This follows the no-silent-fallback rule, and the prerequisites name cf slice 263. The blast radius is larger than onboard: any pipeline run against an older cf fails at `list_slices`, not just retroactive handling. The architecture treats the field as stable since 263, so I accept it. The CHANGELOG entry should state the minimum cf version.

### [NOTE] The new `cf.cli_timeout_s` key and the single 300s timeout are slightly heavier than needed

The timeout is justified by the hang failure mode, and keeping the default in `config/keys.py` follows the centralized-defaults rule. Two points:
- One constant would meet the requirement. A user-tunable key isn't needed unless slow guide downloads are expected.
- The 300s applies equally to `cf detect` and `cf project list`, which are quick. A hang in either stalls the read-only report for five minutes. Use a shorter bound for the report calls, or accept the cost.

Neither point blocks the design.

### [PASS] Alignment with the architecture

- The D1 step table matches the architecture's step table, including `adoption-incomplete` being resolved by the normal rows. It adds only the unknown-staleness case.
- The direction rule holds: squadron calls cf, passes paths, never writes cf's formats, and takes the concept only from `cf detect` (D3, Technical Requirements).
- "Python decides, the agent does" is enforced through `decide_step` as the single decision point. The state is the files (State Management), with no state file.
- The root is the given directory with no git-toplevel widening (D4), and the version and outcome checks refuse unknown values (D7).
- D2 reconciles "a stale graph never forces a rebuild" with having no stored state in a way the architecture can accept.
- The scope matches the architecture's single anticipated slice, including the live end-to-end criterion gated on cf 271 and 272.
- Dependencies point the right way (squadron → cf; the `integrations` client below `onboard` and `cli`). The recorded-fixture risk is stated with a mitigation.

### Run Digest

- Response length: 5480 chars
- Response is newline-free: no
- Tool calls made: 3
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 4
- Tokens — prompt / cached / cache write / completion / reasoning: 98591 / 11266 / 87321 / 5362 / not computed
- Duration: 46.7 s
- Cost: $0.40 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
