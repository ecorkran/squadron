---
docType: architecture
archIndex: 400
component: code-quality-measurement
initiative: code-quality-measurement
project: squadron
parent: ../project-guides/001-initiative-plan.squadron.md
dependencies: [100, 320]
dateCreated: 20261020
dateUpdated: 20261020
status: not_started
---

# Architecture: Code Quality Measurement

## Overview

Squadron can tell whether a judge agrees with a human (320) and whether a tech-debt audit found fewer issues after an intervention (323, 324). It cannot tell whether the code itself got more complex, more duplicated, or longer than the project's own limits, because nothing deterministic is measured. Every quality signal today is an LLM opinion: audit finding counts, and code-review findings whose categories are free-form strings that are never rolled up. CI reports pass or fail and nothing else. The project's own size rules (~300-line files, ~50-line functions) are checked by nothing.

This component adds the deterministic half of code-quality measurement and joins it to the LLM half that already exists. It has four capabilities:

- **Static snapshot.** A per-commit record of deterministic metrics: cyclomatic complexity, duplication, file and function length against the project's limits, lint and type-error counts, and coverage where tests run.
- **Review-finding normalization.** Code-review findings carry a category from the audit's closed vocabulary, so review output and audit output count in the same buckets.
- **Rollup and trend.** Per-slice, per-project and over-time reports across static metrics, audit counts and review findings, shown as a breakdown.
- **Adoption baseline.** One command that captures a static snapshot plus an audit baseline with its noise floor, so every later slice on that project is a measured before and after.

**Scope.** New metrology record types for snapshots, normalized code-review findings and slice ranges, the measurement adapters that produce snapshots, the category contract for code-review output, the reports over all three sources, and the baseline command. The store, record envelope, project identity, audit harness and noise-floor method are 320's and are reused as they are.

**Motivation.** Initiative 420 (Model Benchmark) needs objective, comparable scores for implementation output, and 440 (Brownfield Adoption) needs a baseline to offer when an existing project is adopted. Both consume this component. Squadron's own work also needs it: "the code got better" is currently a claim nobody can check.

## Design Goals

- **Deterministic numbers next to the LLM ones.** Every snapshot metric gives the same value on the same commit with the same tool versions and environment. LLM-derived signals (audit, review) stay separate and carry their own noise floor.

- **One category vocabulary.** Audit findings and code-review findings count in the same categories, so a report can say "error-handling-observability findings: 4 from review, 2 from audit" without a translation step.

- **Comparable over time and across projects.** A snapshot identifies the project, commit, language, tool versions, rule set, environment and exclusions it was taken under, so two snapshots can be compared or explicitly flagged as not comparable.

- **Works on code squadron didn't write.** Brownfield projects are not Python. Metrics are defined independently of language, and each language is a pluggable adapter.

- **Cheap to start measuring.** An existing project gets a full baseline from one command, without editing the project's config files or code.

## Architectural Principles

- **Measure, never gate.** Snapshot, rollup and baseline data never decides a pipeline outcome. Gates stay with review and the 300 judges. No pipeline step reads this data to pass or fail.

- **Extend the 320 store, don't fork it.** Snapshots, normalized review findings and slice ranges are new `record_type` values in the existing metrology store, added as optional sibling payloads on `MetrologyRecord` the way 322, 323 and 177 did. No new store, no schema migration. Records key on 320's `ProjectId`, never on a filesystem path.

- **Coarse records.** The store reads every record file on every query, so record count is the cost that matters. One snapshot record per measured commit holds every language and metric for that commit. One review record per review file holds its findings inline, following the `AuditRun` precedent. Snapshots store per-file values plus summary distributions; per-function rows are kept only for functions over the project's limit. Snapshots are taken on demand and at slice boundaries, not on every commit.

- **A snapshot measures a commit.** The record keys on project and commit SHA. HEAD of a clean tree is measured in place, read-only. Any other commit is measured from a `git archive` export into a temporary directory, which writes nothing into the measured repository's `.git`. A dirty tree is refused, never silently attributed to HEAD.

- **Absent is not zero.** When a metric cannot be measured (no adapter for the language, tool not installed, environment not resolved, tests failed, coverage not configured), the record says so with a reason. A missing measurement is never written as 0 or omitted silently, because a rollup would read it as perfect.

- **Limits come from the project.** File and function length are checked against limits the project declares in its own config. When none are declared, the snapshot reports length distributions and records that no limits were set. It does not count violations against a squadron default.

- **Metrics are a closed set.** Every measurement is identified by a member of a closed metric enum (the same pattern as `AuditCategory`), plus the language, tool, tool version and, where it applies, the rule set that produced it. Reports compare measurements only when that whole identity matches, and flag the rest instead of diffing them. This is the same reasoning 320 applied to judge template versions.

- **Normalize categories, not severities.** Review severities (`PASS/NOTE/CONCERN/FAIL`) and audit severities (`critical/high/medium/low`) grade different things on different artifacts. 323 made them deliberately disjoint, and a test enforces it. This component maps code-review *categories* onto the audit vocabulary and reports severity on each source's own scale. It never maps one scale onto the other.

- **Breakdown, not a score.** Reports show each metric and category separately with its source and sample size. No weighted composite is computed anywhere, including as an intermediate value.

## Current State

- **Metrology store (320).** User-level JSON store at `~/.config/squadron/metrology/`, one file per record, keyed by a stable `ProjectId` (git remote or recorded id). Every query scans and validates every file. Record types today are human samples, graduated configs, audit runs, audit noise floors, producer replays and pairwise judgments. No pipeline action writes to it. Records arrive through `sq metrology` commands.
- **Audit (323, 324).** The tech-debt-audit skill emits findings in the closed `AuditCategory` vocabulary (nine dimensions plus a load-bearing `other`). A 3-run noise floor is measured per category, and before/after deltas are reported against it. A sync test keeps the skill file and the Python enum identical.
- **Code review.** `sq review code` writes review files under `project-documents/user/reviews/` with structured findings in frontmatter. The model chooses `category` freely. A finding with no category is written as the sentinel string `uncategorized`. Arch, slice and tasks review templates have their own category vocabularies (`feasibility`, `antipattern` and so on). No review finding is ingested or counted anywhere.
- **Slice ranges.** `review/git_utils.py` resolves a slice's commit range for `sq review code`. It reads the fork point from the branch's reflog entry, which a fresh clone doesn't have and `git gc` expires, and it finds the merge commit by matching the slice number in merge commit messages.
- **Static metrics.** None. Ruff and pyright run in CI as pass/fail gates. Their counts are not recorded, and they cover only Python.
- **Size limits.** Stated in prose in CLAUDE.md and the review rules. No tool reads or checks them.

## Envisioned State

A project can be measured at any commit. The snapshot command resolves the project's identity, exports the commit if it isn't a clean HEAD, selects a language adapter for each language present, runs the deterministic tools, and writes one snapshot record. The record identifies everything that would make two snapshots incomparable, including a single effective exclusion set for the whole commit.

Code-review output arrives already categorized. The `code` review template emits categories from the audit vocabulary plus one review-only value, `correctness`, for behavioral defects that a tech-debt taxonomy has no slot for. The model's raw string is kept beside it, and `other` stays the honest fallback. An ingest step reads code-review files into the store as one record per review file, tied to project, commit and slice where known. Arch, slice and tasks reviews keep their own vocabularies and are not ingested.

Slice attribution is durable. The first time a slice's range resolves (from git topology, or from the existing `git_utils` resolver while its reflog entry still exists), the range is written to the store as a slice-range record. After that the reflog no longer matters. Slices whose range never resolved roll up at project level only.

Reports read snapshots, audit runs and review records and present them as a breakdown per slice, per project and over time. A slice's before and after is the snapshot of the target just before it landed against the snapshot just after: the merge commit's first parent against the merge commit, or the fork against the tip for a fast-forward (refined in slice 403, D3, so other work merged after the fork isn't counted). Because any commit can be measured after the fact, a report takes missing boundary snapshots on demand; nothing has to run at fork time. LLM-sourced numbers are shown against their noise floor. Deterministic numbers need none.

For an existing project, one standalone baseline command takes the first snapshot and runs the audit baseline with its noise floor. Every later slice is measured against it.

Downstream, 420 reads snapshots and normalized review findings to score implementation replays, and 440 offers the baseline command at adoption. Neither writes these record types. This component is the only writer.

## Technical Considerations

- **Language coverage and tool choice.** Complexity, duplication and function-length tools differ per language, and their definitions of the same metric differ too: cyclomatic complexity is computed differently by different analyzers, and "function" can include or exclude lambdas, nested functions and generated accessors. The metric enum fixes what is measured; each adapter must state how it counts, and a definition difference between adapters is part of the tool identity, not hidden by it. Cross-language comparisons in a report are labelled as such.

- **Which rule set lint and type counts use.** The project's own configured rules make trends meaningful for that project. A fixed reference rule set makes projects comparable to each other. These are different numbers. A snapshot may record either or both, but it must name the rule set each count came from. Measuring an exported commit reads that commit's config, so a config change between two commits shows up as a rule-set change, and the counts are flagged rather than diffed.

- **Type counts and coverage need the project's environment.** Without installed dependencies, a type checker's count is mostly unresolved imports and varies with whatever is installed. Coverage needs the tests to run, which also needs the environment and can fail. Both metrics are measured only when the project's environment is resolved, and the snapshot records the environment's identity (lockfile hash). For an exported commit, the current environment is used only when that commit's lockfile matches it; otherwise both metrics are absent with that reason. Whether the snapshot ever installs dependencies itself is a slice decision with real security and environment cost; reading a coverage report the project already produces is the cheaper starting point.

- **Exclusions.** Vendored, generated and third-party code has to be excluded or it swamps the numbers. Squadron itself vendors the audit skill under `commands/analysis/`. Exclusions come from project config plus each language's usual conventions, and the effective exclusion set is recorded on the snapshot, because changing it changes every metric.

- **Code-review categorization at write time.** Prompting the `code` review template with the closed vocabulary changes that template and its output parsing. Mapping free-form strings afterwards would need a lookup table that misses or an LLM call that adds noise. Write-time is the direction; the audit skill itself doesn't change. Historical code reviews can only be mapped read-side, and reports mark those findings as read-side mapped. Ingest treats `uncategorized` as missing, never as a category. The vocabulary then has a third copy (enum, audit skill, `code` template), and 323's sync test extends to cover it. If `other` dominates review findings even with `correctness` added, that's reported as evidence the vocabulary doesn't fit; changing the shared vocabulary is a decision across 320 and 400, not something this component does on its own.

- **Durable slice ranges.** Git topology gives a durable range when the slice was merged with a real merge commit: the merge's second parent is the branch tip, and the merge base of its two parents is the fork. A fast-forward merge leaves no such record, which is why the existing resolver reads the reflog. Matching a slice number in merge commit messages is the project's established merge convention and acceptable as the resolver does it today. Inferring attribution from ordinary commit messages is not. Persisting the range on first resolution is what makes it survive a fresh clone or reflog expiry.

- **Baseline scope report.** The audit noise floor is three audit runs plus the baseline run, all LLM calls on a possibly large codebase. Before spending, the baseline command reports the file count and byte count after exclusions and the number of audit runs it will make. This is informational, not a gate. It uses 320's existing audit profile and model config rather than choosing its own.

## Anticipated Slices

Exploratory. The snapshot record and first two adapters are the keystone.

- **Snapshot record, Python adapter and one non-Python adapter (keystone).** The record type, metric enum, adapter contract, tool, rule-set and environment identity, the absent-with-reason rule, exclusions and project-declared limits, on a clean HEAD. Metrics are file and function length, lint counts and type counts. A second language with length and lint only proves the contract isn't Python-shaped before it hardens.
- **Complexity, duplication and coverage.** The remaining metrics, added to both adapters.
- **Code-review normalization and ingest.** Closed-vocabulary categories in the `code` review template, the extended sync test, and ingest of review files into the store, including read-side mapping for historical reviews.
- **Slice ranges, rollup and trend reports.** Durable slice-range records, commit export for non-HEAD commits, per-slice, per-project and over-time breakdowns across all three sources, on-demand boundary snapshots, and noise-floor display for LLM sources.
- **Adoption baseline command.** Snapshot plus audit baseline with noise floor in one standalone step.

## Non-Goals

- **No composite quality score.** Not as output, and not as an internal ranking signal.
- **No quality-based merge gates.** Gates stay with review and the 300 judges.
- **No change to the tech-debt-audit skill.** Its vocabulary is reused as it stands.
- **No pipeline snapshot hook.** Nothing runs at slice fork or merge. Boundary snapshots are taken on demand by reports, because any commit can be measured after the fact.
- **No normalization of arch, slice or tasks reviews.** They grade documents, not code, and keep their own vocabularies.
- **No new store.** Everything lands in 320's metrology store.
- **No hosted dashboards or telemetry.** Reports are CLI output over the local store.

## Related Work

- **Initiative 320 (Judge Calibration & Quality Metrology)**: the store, record envelope, `ProjectId`, audit harness, noise floor and before/after delta this component builds on. See [320-arch.judge-calibration-quality-metrology.md](320-arch.judge-calibration-quality-metrology.md) and [323-slice.tech-debt-audit-baseline-harness.md](../slices/323-slice.tech-debt-audit-baseline-harness.md) for the closed category vocabulary and the disjoint-severity rule.
- **Initiative 300 (LLM-as-Judge Scoring)**: owns gating. This component stays out of the gate path. See [300-arch.eval-actions-llm-as-judge-scoring.md](300-arch.eval-actions-llm-as-judge-scoring.md).
- **Initiative 100 (Orchestration v2)**: CLI command registration for the snapshot, ingest, report and baseline commands. See [100-arch.orchestration-v2.md](100-arch.orchestration-v2.md).
- **Slice range resolution**: `src/squadron/review/git_utils.py`, the existing resolver this component reuses and makes durable.
- **Initiative 420 (Model Benchmark)**: consumes snapshots and normalized review findings to score implementation replays.
- **Initiative 440 (Brownfield Adoption)** and **context-forge initiative 260**: offer the baseline command at adoption. The probe contract that advertises it is 440's.
- **Initiative plan**: [001-initiative-plan.squadron.md](../project-guides/001-initiative-plan.squadron.md), entry 14.
