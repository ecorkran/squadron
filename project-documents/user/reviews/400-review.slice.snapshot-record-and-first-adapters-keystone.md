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
reviewedSha: 76ac8066401fe69dbbcaa528e418c9cba4794a94
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 98851
cachedTokens: 11266
cacheWriteTokens: 87581
completionTokens: 5293
durationSeconds: 53.0
costUsd: 0.405119
costBasis: provider
runId: run-20261022-p4-4bf38a18
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Record shape, store extension and boundaries follow the architecture"
    location: "project-documents/user/slices/400-slice.snapshot-record-and-first-adapters-keystone.md#Database / Storage Schema"
  - id: F002
    severity: pass
    category: architecture-alignment
    summary: "Keystone requirement of a non-Python adapter is met, and the dependency direction is sound"
    location: "project-documents/user/slices/400-slice.snapshot-record-and-first-adapters-keystone.md#Component Structure"
  - id: F003
    severity: concern
    category: proportionality
    summary: "Overweight for a keystone: several mechanisms serve cases this slice does not have"
    location: "project-documents/user/slices/400-slice.snapshot-record-and-first-adapters-keystone.md#D3, #D9, #Data Flow"
  - id: F004
    severity: concern
    category: design-consistency
    summary: "The \"one file set for every metric\" guarantee does not hold for ESLint"
    location: "project-documents/user/slices/400-slice.snapshot-record-and-first-adapters-keystone.md#D4"
  - id: F005
    severity: concern
    category: hidden-dependency
    summary: "Adapter registry location and registration site are unspecified"
    location: "project-documents/user/slices/400-slice.snapshot-record-and-first-adapters-keystone.md#Component Structure"
  - id: F006
    severity: note
    category: architecture-alignment
    summary: "Deliberate departure from \"a dirty tree is refused\" is documented, with an overwrite consequence"
    location: "project-documents/user/slices/400-slice.snapshot-record-and-first-adapters-keystone.md#D9"
  - id: F007
    severity: note
    category: integration
    summary: "`take_snapshot` signature for 403/404 is only partly defined"
    location: "project-documents/user/slices/400-slice.snapshot-record-and-first-adapters-keystone.md#Integration Points"
---

# Review: slice — slice 400

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Record shape, store extension and boundaries follow the architecture

- **Store and envelope:** `code_snapshot` is an optional sibling payload on `MetrologyRecord`, with no schema bump and no new store. That matches "extend the 320 store, don't fork it".
- **Coarse records:** The slice writes one record per (project, commit), with per-file values plus distributions. Per-function rows appear only for functions over the limit. That matches "coarse records".
- **Absent is not zero:** The slice enforces this in a model validator and with a closed `AbsenceReason` enum.
- **Metric identity:** The slice enforces the arch's identity rules through model validation: tool and version, rule set on lint and type, environment with lockfile hash on type.
- **Limits and exclusions:** Limits come from project config, and no squadron default is applied. One effective exclusion set is recorded on the snapshot.
- **Measure, never gate:** Nothing in the slice feeds a pipeline gate.

### [PASS] Keystone requirement of a non-Python adapter is met, and the dependency direction is sound

Python measures all four metrics. TypeScript measures length and lint only, with type errors recorded as `metric_unsupported`. That is the arch's "second language with length and lint only". `take.py` depends only on the contract. The `every SnapshotMetric member appears for every language` test makes 401's extension a non-breaking change. Failure modes for every new I/O path are enumerated with an observable signal and a test requirement. These paths are the tool runner, the uv check, parsers, git calls and the store write.

### [CONCERN] Overweight for a keystone: several mechanisms serve cases this slice does not have

The slice has ten new modules, two new runtime dependencies, and a long list of decision records. These items can be cut or deferred without losing a requirement:
- **D3 "replaced record differs" WARNING.** It needs a field-by-field comparison on write (everything except `measured_at` and `snapshot_id`), plus its own test. The arch needs only one record per commit and visible identity. Log an unconditional INFO or WARNING on overwrite, or defer the diff to 403, which already flags mismatches from the stored identities.
- **Per-language, per-step INFO progress lines.** They exist only to trace a stall in an unbounded in-process parse. The slice itself says the parse is linear in file size. Drop them, or emit a single line per language.
- **`ExclusionPattern.source` tagging, and the ESLint-only fallback to "no `eslint.config.{js,mjs,cjs}` found".** Nothing in 401, 403 or 404 reads the tag. It is cheap, but it is a field in a contract that every later slice inherits.
- **The `uv sync --check` exit-code table.** It has five rows. Collapsing it to "resolved or `environment_unresolved` with detail, with any uv error as `tool_failed`" meets criterion 6 with less machinery.

Because the contract is inherited by 401, 403 and 404, the cost of an unused field is higher than usual.

### [CONCERN] The "one file set for every metric" guarantee does not hold for ESLint

D4 rejects tool-level excludes because they would "measure four different file sets under one snapshot". D1 also defines the measured file set as the file-length key set. D4 passes explicit files to ruff, pyright and ESLint, and says tool-level include/exclude are not applied. That is accurate for ruff and pyright. For ESLint, the project's flat-config `ignores` entries still apply to explicitly passed files. ESLint reports those files as "ignored" warnings, or skips them, and the design neither detects this nor handles it. The result is TypeScript lint counts over a different file set than TypeScript length counts. That is exactly the divergence D4 says it prevents. The design should either state that ESLint-ignored files are excluded from the lint file set and recorded, or pass a flag that disables config ignores. It should also say how ignored-file messages are kept out of the count.

### [CONCERN] Adapter registry location and registration site are unspecified

The table places the adapter registry in `snapshot/contract.py`. The text says `take.py` "depends only on the contract module, never on a concrete adapter". It also says adding a language means "registering it". The contract module cannot import the concrete adapters without turning the contract into a dependency on them. The design never says where registration happens (CLI module, an `adapters/__init__`, or an injected parameter to `take_snapshot`). The unanswered questions are:
- who populates the registry;
- whether 404 calling `take_snapshot` gets the default adapters;
- whether tests can inject a fake registry.

Passing the registry as a `take_snapshot` argument, with the CLI building the default one, would resolve all three.

### [NOTE] Deliberate departure from "a dirty tree is refused" is documented, with an overwrite consequence

The untracked `.squadron.toml` exemption contradicts the arch's "dirty tree is refused" wording. D9 states this openly, and the limits and exclusions are recorded on the snapshot, so the departure is traceable. Two consequences are worth carrying forward to 403.
- Squadron's own `.squadron.toml` is gitignored, so its 300/50 limits are checkout-local. Two checkouts of one commit overwrite each other's record (last writer wins).
- The arch goal "same value on same commit" holds only when the recorded settings match.

403 must therefore compare `limits` and `exclusions`, not just tool identity, before it diffs. The slice's own Integration Points should say so.

### [NOTE] `take_snapshot` signature for 403/404 is only partly defined

The slice says `take_snapshot(repo_root)` measures a clean HEAD, and that 403 "extends it" for exported commits. The preflight, the integrity check and the write are all fused into `take_snapshot`. 404 wants the post-exclusion file set for its scope report, so 404 must either take a full snapshot (all tools run) or get a separate file-resolution entry point. Exposing `files.py` resolution as part of the provided interface would let 404 run its scope report without a full snapshot.

### Run Digest

- Response length: 7335 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 98851 / 11266 / 87581 / 5293 / not computed
- Duration: 53.0 s
- Cost: $0.41 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
