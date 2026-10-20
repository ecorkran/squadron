---
docType: review
layer: project
reviewType: arch
slice: code-quality-measurement
targetKind: arch
rulesSource: project
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/architecture/400-arch.code-quality-measurement.md
aiModel: claude-opus-5-5
aiProfile: sdk
status: complete
dateCreated: 20261020
dateUpdated: 20261020
reviewedSha: 0c6c4898e54931b788f58c5f9e15d4c2c1986161
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 8
turns: 9
promptTokens: 381592
cachedTokens: 305909
cacheWriteTokens: 75671
completionTokens: 5101
durationSeconds: 56.7
costUsd: 0.769349
costBasis: provider
squadronVersion: 0.23.5
findings:
  - id: F001
    severity: concern
    category: feasibility
    summary: "Slice attribution contradicts how squadron resolves slice ranges today, and the fork point it relies on only exists in a local reflog"
    location: "project-documents/user/architecture/400-arch.code-quality-measurement.md#technical-considerations"
  - id: F002
    severity: concern
    category: feasibility
    summary: "The store's scan-everything read path is not checked against the new record volume"
    location: "project-documents/user/architecture/400-arch.code-quality-measurement.md#architectural-principles"
  - id: F003
    severity: concern
    category: antipattern
    summary: "The keystone slice is overloaded, and the \"designed for\" extension ships unexercised"
    location: "project-documents/user/architecture/400-arch.code-quality-measurement.md#anticipated-slices"
  - id: F004
    severity: concern
    category: completeness
    summary: "Adapter contract and metric definitions are left as \"the hard part\" with no shape"
    location: "project-documents/user/architecture/400-arch.code-quality-measurement.md#technical-considerations"
  - id: F005
    severity: concern
    category: completeness
    summary: "Snapshot isolation from the working tree is asserted but not designed"
    location: "project-documents/user/architecture/400-arch.code-quality-measurement.md#envisioned-state"
  - id: F006
    severity: concern
    category: feasibility
    summary: "Type-error counts have the same environment dependence as coverage, but only coverage is flagged"
    location: "project-documents/user/architecture/400-arch.code-quality-measurement.md#technical-considerations"
  - id: F007
    severity: concern
    category: abstraction
    summary: "Write-time categorization stretches the \"no change to the audit skill\" non-goal and puts a third copy of the vocabulary in templates"
    location: "project-documents/user/architecture/400-arch.code-quality-measurement.md#non-goals"
  - id: F008
    severity: concern
    category: completeness
    summary: "The \"measure, never gate\" pipeline hook has no owner or failure contract"
    location: "project-documents/user/architecture/400-arch.code-quality-measurement.md#technical-considerations"
  - id: F009
    severity: note
    category: dependencies
    summary: "Baseline command depends on 440's probe, which comes later"
    location: "project-documents/user/architecture/400-arch.code-quality-measurement.md#envisioned-state"
  - id: F010
    severity: note
    category: completeness
    summary: "Baseline cost preview has no defined source"
    location: "project-documents/user/architecture/400-arch.code-quality-measurement.md#technical-considerations"
---

# Review: arch — initiative 400

**Verdict:** CONCERNS
**Model:** claude-opus-5-5

## Findings

### [CONCERN] Slice attribution contradicts how squadron resolves slice ranges today, and the fork point it relies on only exists in a local reflog

"Attributing measurements to slices" says slice branches give "fork point to merge commit" and that "Guessing a slice from commit messages is not acceptable." The existing range resolver in `src/squadron/review/git_utils.py` works differently:
- It finds the merge commit by grepping commit messages (`_search_merge_commit`, lines 221–243, pattern `slice[^0-9]{n}…`).
- It finds the fork point from the reflog entry `branch: Created from` (lines 197–217).

Git does not clone reflogs, and they expire. On a fresh clone, a CI runner, or a brownfield repo, there is no fork-point record. The Envisioned State depends on this ("A slice's before and after is the snapshot at its fork point against the snapshot at its merge"), and so does 420's replay scoring. The document has to do one of two things:
- Reuse `git_utils` and drop or soften the "no commit-message guessing" rule, since the existing resolver already does that.
- Name a durable source for the range, such as the commit SHAs recorded at slice start and merge, and say which component writes it.

Leaving this as "a slice decision" defers the one input the per-slice rollup can't work without.

### [CONCERN] The store's scan-everything read path is not checked against the new record volume

"Extend the 320 store, don't fork it" reuses `MetrologyStore` unchanged. That store writes one JSON file per record, and every query globs and validates every file (`store.py:176-189`).

320's record types are low-volume: samples, audit runs, floors. 400 adds two high-volume types:
- A snapshot per commit per project, carrying per-file and per-function length distributions.
- A normalized finding per review finding, across every review file in every project, including the historical backfill.

Trend reports read all of these on every invocation. The document doesn't say whether a review finding is one record per finding or one per review file (the `AuditRun` precedent is findings inline, one record per run). It also doesn't say whether distributions are stored raw or summarized. Both choices decide whether "no new store" holds up, so the document should fix them. One record per review file, holding findings inline as `AuditRun` does, is the obvious one.

### [CONCERN] The keystone slice is overloaded, and the "designed for" extension ships unexercised

The keystone slice carries all of these:
- The record type and the adapter contract.
- Tool and rule-set identity.
- Absent-with-reason, exclusions, and project-declared limits.
- A Python adapter covering complexity, duplication, length, lint counts, type counts and coverage.

The non-Python adapter comes later. So the contract is designed with one implementation, which is the exact risk the document names ("proving the contract wasn't Python-shaped").

Two changes would fix this:
- Cut the keystone to length, lint and type counts on Python. These can be computed with no extra tooling: AST line spans, `ruff --statistics`, and pyright's `--outputjson`.
- Put complexity, duplication and coverage in later slices.

Also consider proving the contract with a second language inside the keystone, using only the language-agnostic metrics (line counts, duplication). That checks the contract's shape before it hardens.

### [CONCERN] Adapter contract and metric definitions are left as "the hard part" with no shape

The document says "The adapter contract has to define each metric well enough that adapters agree," but it never gives the contract. It doesn't say:
- What an adapter returns (per-file, per-function, or aggregate).
- How a metric is identified: an enum, or a string paired with tool and version.
- How "function" is defined across languages (lambdas, nested functions, methods, generated accessors).
- How the snapshot is assembled when a repo has several languages ("selects a language adapter for each language present"). Does each adapter get its own record, or do they merge into one record per commit, and how are the exclusions merged?

"Breakdown, not a score" and "refuse to diff across a tool change" both depend on this identity scheme. Without it, the extension point for new languages is a name, not a design. The project rule against scattered comparison values also suggests a closed `MetricKind` enum, by analogy with `AuditCategory`. The document should commit to that.

### [CONCERN] Snapshot isolation from the working tree is asserted but not designed

Three statements pull against each other:
- "A project can be measured at any commit."
- "Taking a snapshot doesn't modify the measured repository."
- A dirty tree is "refused or recorded with an explicit dirty marker."

Measuring an arbitrary non-HEAD commit, which the per-slice before/after needs for fork points that have already passed, means checking out somewhere else: a temporary `git worktree` or `git archive` into a temp directory. That changes three things the document doesn't address:
- Tools that read config (`pyproject.toml`, `.ruff.toml`) see that commit's config, so the rule set changes per commit. This interacts with "name the rule set each count came from".
- Type checkers need the project's installed dependencies to give stable counts. Pyright's error count on an environment without them is mostly import errors.
- `git worktree add` registers metadata in the measured repo's `.git`, which arguably modifies it.

This conflicts with this repo's `cf worktree` conventions too. The document should pick the mechanism.

### [CONCERN] Type-error counts have the same environment dependence as coverage, but only coverage is flagged

"Coverage requires running tests" is treated as the environment-sensitive metric. Type-error counts from pyright or mypy (or `tsc` for TypeScript) depend just as much on the project's dependencies being installed and resolvable. Without them, the counts are dominated by `reportMissingImports` and vary with whatever happens to be in the ambient environment.

That breaks the first design goal: "same value on the same commit with the same tool versions." The snapshot's identity also needs to cover the environment state (dependencies resolved or not, lockfile hash). Otherwise type counts need the same absent-with-reason handling as coverage.

### [CONCERN] Write-time categorization stretches the "no change to the audit skill" non-goal and puts a third copy of the vocabulary in templates

The non-goal says the audit vocabulary is "reused as it stands." But `AuditCategory` (`models.py:136-145`) is a tech-debt taxonomy (`architectural-decay`, `consistency-rot`, `documentation-drift`…). Code-review templates find things such as correctness bugs, spec mismatches, and the review-arch categories (`feasibility`, `extension-points`, `antipattern`) that this very review uses.

Two problems follow:
- A large share of review findings will land in `other`. The document treats that as "a finding to report," but it also kills the headline report example, which uses "error-handling", a value that doesn't exist (the enum value is `error-handling-observability`).
- Review templates other than `code` (arch, slice, tasks) already have their own category vocabularies. Changing them all would break existing reviews. The document doesn't scope which templates change.

The document should either restrict normalization to `review code` explicitly or admit that the vocabulary may need a review-specific extension. Also, `review/models.py:401` already coerces `None` to the string `"uncategorized"` when it builds `StructuredFinding`. So "category is `None` on many findings" (Current State) is not what the frontmatter that ingest reads actually contains. Ingest has to handle that sentinel explicitly.

### [CONCERN] The "measure, never gate" pipeline hook has no owner or failure contract

"When snapshots are taken" floats a pipeline action at fork and merge, and says a failure "must never fail the pipeline step… but must be visible." Several things are left open:
- Whether this action is in scope for 400 at all. It's absent from Anticipated Slices.
- Which pipeline step it attaches to. Slice fork and merge happen in agent-driven git workflow (Phase 6/7), not in a squadron pipeline step.
- How "recorded as absent" works for a snapshot that never produced a record.

If the action is deferred, say so in Non-Goals and accept that per-slice before/after needs a manual `snapshot` at fork. Otherwise the per-slice rollup has no data for most slices.

### [NOTE] Baseline command depends on 440's probe, which comes later

"CF offers this at handoff through 440's capability probe" puts a dependency on a later initiative (440) and an external repo (context-forge 260) into the Envisioned State. The frontmatter `dependencies: [100, 320]` doesn't list it. The baseline command should be specified as standalone, with the probe contract owned by 440. That way the 400 slice isn't blocked on, or shaped by, a design that doesn't exist yet.

### [NOTE] Baseline cost preview has no defined source

"The baseline command must report its expected scope before spending." Scope in what units: files, tokens, runs? From what estimator? 323's harness exposes no size estimate. Either define the reported quantity (for example, file count and byte count after exclusions, multiplied by four runs) or drop the requirement. Spend is pre-authorized under project rules, so this is informational, not a gate.

### Run Digest

- Response length: 10968 chars
- Response is newline-free: no
- Tool calls made: 8
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 9
- Tokens — prompt / cached / cache write / completion / reasoning: 381592 / 305909 / 75671 / 5101 / not computed
- Duration: 56.7 s
- Cost: $0.77 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10

## Response

- **F001** accepted: slice ranges get a durable record, written to the store the first time a range resolves (from git topology for real merge commits, or from the existing `git_utils` resolver while the reflog lasts). Matching the slice number in merge commit messages is allowed as the established convention; inferring from ordinary commit messages is not. Unresolved slices roll up at project level only.
- **F002** accepted: a new "Coarse records" principle. One snapshot record per measured commit, one review record per review file with findings inline (the `AuditRun` precedent), per-function rows only for over-limit functions, and snapshots on demand rather than per commit.
- **F003** accepted: the keystone covers length, lint and type counts with Python plus one non-Python adapter (length and lint). Complexity, duplication and coverage move to the second slice.
- **F004** accepted: a closed metric enum. Every measurement carries metric, language, tool, tool version and rule set, and reports compare only on a full identity match. One record per commit for all languages, with a single effective exclusion set. Each adapter states how it counts things like "function"; the exact definitions are left to slice design.
- **F005** accepted: a clean HEAD is measured in place; any other commit is measured from a `git archive` export, which writes nothing to `.git`. A dirty tree is refused. Reading the exported commit's own config is intended and shows up as a rule-set change.
- **F006** accepted: type counts are treated like coverage. Both are measured only with a resolved environment, the snapshot records the lockfile hash, and an exported commit whose lockfile differs gets both metrics as absent, with the reason recorded.
- **F007** accepted: normalization is limited to `review code`. Arch, slice and tasks reviews keep their own vocabularies (a new non-goal). The review side adds one value, `correctness`. The example now uses `error-handling-observability`, Current State describes the `uncategorized` sentinel, and ingest treats that sentinel as missing.
- **F008** accepted, resolved by removal: no pipeline hook (a new non-goal). Because any commit can be measured after the fact, reports take missing boundary snapshots on demand.
- **F009** accepted: the baseline command is standalone. 440 offers it, and the probe contract is 440's.
- **F010** accepted: the scope report gives the file count and byte count after exclusions, plus the number of audit runs. It's informational, not a gate.
