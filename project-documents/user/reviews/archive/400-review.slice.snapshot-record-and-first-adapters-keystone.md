---
docType: review
layer: project
reviewType: slice
slice: snapshot-record-and-first-adapters-keystone
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/400-slice.snapshot-record-and-first-adapters-keystone.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261022
dateUpdated: 20261022
reviewedSha: 642b55e09da46e1292dbac779c0e426d13bb6f20
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 179829
cachedTokens: 90531
cacheWriteTokens: 89292
completionTokens: 3099
durationSeconds: 29.2
costUsd: 0.397953
costBasis: provider
runId: run-20261022-p4-4bf38a18
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Alignment with architecture principles and boundaries"
    location: "project-documents/user/slices/400-slice.snapshot-record-and-first-adapters-keystone.md#Architecture"
  - id: F002
    severity: concern
    category: proportionality
    summary: "Overweight design: mechanisms that nothing in this slice needs yet"
    location: "project-documents/user/slices/400-slice.snapshot-record-and-first-adapters-keystone.md#Technical Decisions"
  - id: F003
    severity: concern
    category: scope-creep
    summary: "Environment identity for ESLint goes beyond what the arch and slice plan define"
    location: "project-documents/user/slices/400-slice.snapshot-record-and-first-adapters-keystone.md#D5 / #D2"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Failure modes for new I/O paths are mostly enumerated, but some lack an observable signal or a test"
    location: "project-documents/user/slices/400-slice.snapshot-record-and-first-adapters-keystone.md#Data Flow"
  - id: F005
    severity: concern
    category: configuration
    summary: "Hard-coded default for tool timeout versus project rule"
    location: "project-documents/user/slices/400-slice.snapshot-record-and-first-adapters-keystone.md#D10"
  - id: F006
    severity: note
    category: determinism
    summary: "Exclusion tag and `-` usage: untracked `.squadron.toml` exemption weakens the clean-tree guarantee"
    location: "project-documents/user/slices/400-slice.snapshot-record-and-first-adapters-keystone.md#D9"
  - id: F007
    severity: note
    category: integration
    summary: "Cross-slice contract surfaces look right"
    location: "project-documents/user/slices/400-slice.snapshot-record-and-first-adapters-keystone.md#Integration Points"
---

# Review: slice — slice 400

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Alignment with architecture principles and boundaries

- The record is a sibling payload on `MetrologyRecord`, with `schema_version` unchanged and no migration. It follows the 322/323/177 precedent and the arch's "extend the 320 store" rule.
- One coarse record per commit, and per-function rows only for functions over the limit.
- Absent-with-reason, with `absent_detail` required.
- Closed `SnapshotMetric` enum, plus full tool, rule-set and environment identity.
- Limits come from project config, and the record says so when none are declared.
- Clean-HEAD-only matches the slice plan, which moved commit export to 403.
- `take.py` depends only on the contract, so dependencies point toward the abstraction.
- The slice contains no gating, no composite score and no pipeline hook.

### [CONCERN] Overweight design: mechanisms that nothing in this slice needs yet

The design is heavy for what the slice plan assigns, though the plan does rate this slice 4/5. Items that can be cut or deferred:
- **Overwrite settings-diff (D3).** `write_snapshot` compares limits, exclusions and every measurement's tool, rule set and environment against the existing record. It then logs a WARNING and prints a CLI line naming the changed fields. The arch already makes each record carry its own identity, and 403 flags mismatches from that. A plain overwrite, or a single "settings differ" WARNING, meets the requirement.
- **Unique tmp names in `_write_atomic`.** This changes a shared 320 code path for every record type, for a race between two snapshots of the same commit that the slice doesn't need to support. Cut it, or move it to a fix.
- **Integrity check via `git status --porcelain --ignored` before and after (D9).** The design admits it can't see writes inside existing ignored directories, which is where tool caches would land. It only partly checks a property that the design says is already guaranteed by read-only flags. The slice plan does require "repository unchanged", so keep a cheaper check (tracked files plus untracked) rather than a full `--ignored` comparison. Alternatively, state that prevention is the guarantee and drop the check.
- **Dual-form `snapshot_exclude`.** It accepts either a TOML array or a comma-separated string. This is defensible because `sq config set` writes strings, but it is a second parse path.
- **Pyproject-table canonical-JSON hashing (D8).** This is justified by release version bumps. It is still a lot of mechanism for a keystone.
- **Module count.** Ten new modules and nine decisions make a large surface. That is acceptable only if the heavier items above are trimmed.

### [CONCERN] Environment identity for ESLint goes beyond what the arch and slice plan define

The arch and slice plan tie environment identity to **type counts** only ("Type counts and coverage need the project's environment"). The slice plan's criterion is "type counts are absent unless the project's environment is resolved, and the record carries the lockfile hash".

D2 and D5 extend this to lint. ESLint lint is absent with `environment_unresolved` when there is no package lockfile. That adds a `uses_project_environment` flag, a lockfile search order across pnpm, npm and yarn, and a `node --version` probe.

The reasoning is sound, since ESLint results depend on plugins in `node_modules`. But it is an addition to the arch's stated rule and it costs a probe plus a new absence path. Either cite it as a deliberate arch extension, or defer it and record ESLint lint with the tool version and rule set only.

### [CONCERN] Failure modes for new I/O paths are mostly enumerated, but some lack an observable signal or a test

Tool failures (D7, D8) and store failures are well covered. These gaps remain:
- **Git calls.** `run_git` returning `None` is a preflight failure. But the failure table has no entry for `git ls-files` or the `git status` before/after calls failing or timing out mid-run. The integrity check needs a defined behavior here: either raise `SnapshotIntegrityError` or fail the preflight, never treat it as "unchanged".
- **`node --version` and `uv`/tool `--version` probes.** A hang, non-zero exit or unparseable output on a version probe has no mapped absent reason. D8 covers a tool binary that fails or times out, but not its version probe.
- **In-process parse failures.** `unparsed_files` is logged at WARNING per file, but the Technical Requirements say tests cover only "timeout, missing tool, bad JSON, non-zero exit". Add the parse failure and `RecursionError` path to the tests that assert the signal.
- **Timeout.** The criteria need a stated per-tool timeout and a single bound on total runtime. `snapshot_tool_timeout_s` defaults to 600, and the slice doesn't say whether that is per call or per tool.

### [CONCERN] Hard-coded default for tool timeout versus project rule

`metrology.snapshot_tool_timeout_s` has default 600, but the other three keys default to `None`. CLAUDE.md says magic defaults must be centralized at the config level. Registering the default in `CONFIG_KEYS` satisfies this, so say explicitly that it lives there and is not repeated in the adapter or runner code. Also state whether `ToolRunner` fails when a caller passes no timeout.

### [NOTE] Exclusion tag and `-` usage: untracked `.squadron.toml` exemption weakens the clean-tree guarantee

The arch says "a dirty tree is refused, never silently attributed to HEAD". D9 exempts an untracked `.squadron.toml`. The rationale holds, since it is recorded on the snapshot and no measured tool reads it. But it is a deliberate departure from the arch wording. The consequence is that two checkouts of one commit can produce different records, which D3's overwrite warning partly covers. Keep it, and name it as an arch deviation in the doc.

### [NOTE] Cross-slice contract surfaces look right

- 401 can add enum members without touching the envelope or the contract, and the "every member appears for every language" test enforces that.
- 403 gets `list_snapshots` and full identities.
- 404 gets `take_snapshot` and the post-exclusion file set.
- The rule that the orchestrator raises on mismatch between declared and returned metrics protects the contract.
- The slice does not restate the arch's absence of NFRs, and none are required: the arch states no latency or throughput targets for this path.

### Run Digest

- Response length: 7543 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 179829 / 90531 / 89292 / 3099 / not computed
- Duration: 29.2 s
- Cost: $0.40 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7

## Response

- **F001** no change.
- **F002** accepted in part:
  - Overwrite: a single WARNING when the replaced record differs, with no per-field diff (D3).
  - Unique tmp names in `_write_atomic`: cut. Two snapshots of one commit at once are stated as unsupported.
  - Integrity check: reduced to rerunning the preflight's `git status --porcelain`, so ignored paths rely on prevention (D9).
  - `snapshot_exclude`: comma-separated string only.
  - Kept: the pyproject table hashing. Hashing the whole file would turn every release's version bump into a rule-set change.
  - Kept: the module count. The cuts above take the weight off.
- **F003** accepted, deferred: ESLint lint carries a tool version and rule set only. The environment validator reverts to the arch's rule (type counts only). ESLint lockfile identity is #250.
- **F004** accepted: failure-mode rows added for git calls returning `None` or non-zero (`SnapshotIntegrityError`, never treated as unchanged) and for version-probe failures (`tool_failed`, tool not run). The timeout is stated as per subprocess call, with no total bound. Parse, `RecursionError` and git paths are added to the signal tests.
- **F005** accepted: the timeout default lives only in `CONFIG_KEYS` and is read with `get_positive_int_config`. `ToolRunner.run` requires `timeout_s`.
- **F006** accepted: the `.squadron.toml` exemption is named in D9 as a deliberate arch deviation, with its consequence.
- **F007** no change.
