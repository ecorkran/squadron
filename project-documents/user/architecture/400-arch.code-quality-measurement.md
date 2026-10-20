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

**Scope.** New metrology record types for snapshots and normalized review findings, the measurement adapters that produce snapshots, the category contract for review output, the reports over all three sources, and the baseline command. The store, record envelope, project identity, audit harness and noise-floor method are 320's and are reused as they are.

**Motivation.** Initiative 420 (Model Benchmark) needs objective, comparable scores for implementation output, and 440 (Brownfield Adoption) needs a baseline to offer when an existing project is adopted. Both consume this component. Squadron's own work also needs it: "the code got better" is currently a claim nobody can check.

## Design Goals

- **Deterministic numbers next to the LLM ones.** Every snapshot metric gives the same value on the same commit with the same tool versions. LLM-derived signals (audit, review) stay separate and carry their own noise floor.

- **One category vocabulary.** Audit findings and code-review findings count in the same ten categories, so a report can say "error-handling findings: 4 from review, 2 from audit" without a translation step.

- **Comparable over time and across projects.** A snapshot identifies the project, commit, language, tool versions, rule set and exclusions it was taken under, so two snapshots can be compared or explicitly flagged as not comparable.

- **Works on code squadron didn't write.** Brownfield projects are not Python. Metrics are defined independently of language, and each language is a pluggable adapter.

- **Cheap to start measuring.** An existing project gets a full baseline from one command, without editing the project's config files or code.

## Architectural Principles

- **Measure, never gate.** Snapshot, rollup and baseline data never decides a pipeline outcome. Gates stay with review and the 300 judges. A pipeline step may *write* a snapshot; no step reads one to pass or fail.

- **Extend the 320 store, don't fork it.** Snapshots and normalized review findings are new `record_type` values in the existing metrology store, added as optional sibling payloads on `MetrologyRecord` the way 322, 323 and 177 did. No new store, no schema migration. Records key on 320's `ProjectId`, never on a filesystem path.

- **A snapshot measures a commit.** The record keys on project and commit SHA. A dirty working tree is either refused or recorded with an explicit dirty marker, never silently attributed to the HEAD commit.

- **Absent is not zero.** When a metric cannot be measured (no adapter for the language, tool not installed, tests failed, coverage not configured), the record says so with a reason. A missing measurement is never written as 0 or omitted silently, because a rollup would read it as perfect.

- **Limits come from the project.** File and function length are checked against limits the project declares in its own config. When none are declared, the snapshot reports length distributions and records that no limits were set. It does not count violations against a squadron default.

- **Normalize categories, not severities.** Review severities (`PASS/NOTE/CONCERN/FAIL`) and audit severities (`critical/high/medium/low`) grade different things on different artifacts. 323 made them deliberately disjoint, and a test enforces it. This component maps review *categories* onto `AuditCategory` and reports severity on each source's own scale. It never maps one scale onto the other.

- **Breakdown, not a score.** Reports show each metric and category separately with its source and sample size. No weighted composite is computed anywhere, including as an intermediate value.

- **Tool identity is part of the measurement.** A complexity number from tool A version 1 and one from tool B version 2 are different measurements. Snapshots record the tool and version per metric, and reports refuse to diff across a tool change without flagging it. This is the same reasoning 320 applied to judge template versions.

## Current State

- **Metrology store (320).** User-level JSON store at `~/.config/squadron/metrology/`, keyed by a stable `ProjectId` (git remote or recorded id). Record types today are human samples, graduated configs, audit runs, audit noise floors, producer replays and pairwise judgments. No pipeline action writes to it. Records arrive through `sq metrology` commands.
- **Audit (323, 324).** The tech-debt-audit skill emits findings in the closed `AuditCategory` vocabulary (nine dimensions plus a load-bearing `other`). A 3-run noise floor is measured per category, and before/after deltas are reported against it. A sync test keeps the skill file and the Python enum identical.
- **Code review.** `sq review code` writes review files under `project-documents/user/reviews/` with structured findings in frontmatter. `category` is a free string the model chooses, and is `None` on many findings. Findings are never ingested or counted anywhere.
- **Static metrics.** None. Ruff and pyright run in CI as pass/fail gates. Their counts are not recorded, and they cover only Python.
- **Size limits.** Stated in prose in CLAUDE.md and the review rules. No tool reads or checks them.

## Envisioned State

A project can be measured at any commit. The snapshot command resolves the project's identity, selects a language adapter for each language present, runs the deterministic tools, and writes one snapshot record per commit into the metrology store. The record identifies everything that would make two snapshots incomparable. Taking a snapshot doesn't modify the measured repository.

Code review output arrives already categorized. Review templates emit categories from the same closed vocabulary the audit uses, with the model's raw string kept beside it and `other` as the honest fallback. An ingest step reads review files into the store as normalized finding records tied to project, commit and slice where known.

Reports read all three sources (snapshots, audit runs, review findings) and present them as a breakdown per slice, per project and over time. A slice's before and after is the snapshot at its fork point against the snapshot at its merge. LLM-sourced numbers are shown against their noise floor; deterministic numbers need none.

For an existing project, one baseline command takes the first snapshot and runs the audit baseline with its noise floor. CF offers this at handoff through 440's capability probe. Every later slice is measured against it.

Downstream, 420 reads snapshots and normalized review findings to score implementation replays, and 440 reads the baseline. Neither writes these record types. This component is the only writer.

## Technical Considerations

- **Language coverage and tool choice.** Complexity, duplication and function-length tools differ per language, and their definitions of the same metric differ too: cyclomatic complexity is computed differently by different analyzers. The adapter contract has to define each metric well enough that adapters agree on what they report, and cross-language comparisons in a report have to be labelled as such. Language-agnostic tools exist for some metrics (duplication, line counts) and not others (type errors). Which languages ship first is a slice decision. Python is required for squadron's own use, and at least one non-Python language is required before 440 relies on this.

- **Which rule set lint and type counts use.** The project's own configured rules make trends meaningful for that project. A fixed reference rule set makes projects comparable to each other. These are different numbers. A snapshot may record either or both, but it must name the rule set each count came from. A count with no named rule set can't be compared to anything.

- **Coverage requires running tests.** That's slow, can fail, needs the project's environment, and can't be done on every brownfield repo out of the box. Coverage is therefore optional per snapshot and recorded as absent with a reason when not taken. Whether the snapshot ever installs or runs project dependencies, or only reads a coverage report the project already produces, is a slice decision with real security and environment cost.

- **Exclusions.** Vendored, generated and third-party code has to be excluded or it swamps the numbers. Squadron itself vendors the audit skill under `commands/analysis/`. Exclusions come from project config plus each language's usual conventions, and the effective exclusion set is recorded on the snapshot, because changing it changes every metric.

- **Where review categorization happens.** Two options. Prompting review templates to emit the closed vocabulary is a write-path change to review templates and output parsing, but it's deterministic at ingest. Mapping free-form strings after the fact needs either a lookup table that will miss or an LLM call that adds noise. The preferred direction is write-time categorization, following 323's precedent for the audit skill. Historical reviews can only be mapped read-side, and reports must mark those findings as read-side mapped rather than pool them silently. The vocabulary then has a third copy (enum, audit skill, review templates), and 323's sync test extends to cover it.

- **Attributing measurements to slices.** Per-slice rollup needs a commit range per slice. Slice branches give one (fork point to merge commit), but fix commits land directly on the target, and brownfield history has no slices at all. Unattributed commits roll up at project level only. The mapping source (git topology, cf slice records, or both) is a slice decision. Guessing a slice from commit messages is not acceptable.

- **When snapshots are taken.** On demand from the CLI is the baseline. Capturing at slice boundaries automatically, through a pipeline action at fork and merge, makes per-slice before/after free, but it adds work and a failure mode to every pipeline run. A failed snapshot must never fail the pipeline step it's attached to, but it must be visible as a failure (logged and recorded as absent), not swallowed.

- **Baseline cost.** The audit noise floor is three audit runs plus the baseline run, all LLM calls on a possibly large codebase. The baseline command must report its expected scope before spending, and accept 320's existing audit profile and model config rather than pick its own.

## Anticipated Slices

Exploratory. The snapshot record and first adapter is the keystone.

- **Snapshot record and Python adapter (keystone).** The record type, adapter contract, tool and rule-set identity, the absent-with-reason rule, exclusions, and project-declared limits, proven on Python against squadron itself.
- **Additional language adapters.** At least one non-Python language, chosen for brownfield adoption, proving the contract wasn't Python-shaped.
- **Review-finding normalization and ingest.** Closed-vocabulary categories in review templates, the extended sync test, and ingest of review files into the store, including read-side mapping for historical reviews.
- **Rollup and trend reports.** Per-slice, per-project and over-time breakdowns across all three sources, with slice attribution and noise-floor display for LLM sources.
- **Adoption baseline command.** Snapshot plus audit baseline with noise floor in one step, consumable by 440's capability probe.

## Non-Goals

- **No composite quality score.** Not as output, and not as an internal ranking signal.
- **No quality-based merge gates.** Gates stay with review and the 300 judges.
- **No change to the tech-debt-audit skill.** Its vocabulary is reused as it stands. If the vocabulary turns out not to fit review findings, that's a finding to report, not a reason to edit the skill from here.
- **No new store.** Everything lands in 320's metrology store.
- **No hosted dashboards or telemetry.** Reports are CLI output over the local store.

## Related Work

- **Initiative 320 (Judge Calibration & Quality Metrology)**: the store, record envelope, `ProjectId`, audit harness, noise floor and before/after delta this component builds on. See [320-arch.judge-calibration-quality-metrology.md](320-arch.judge-calibration-quality-metrology.md) and [323-slice.tech-debt-audit-baseline-harness.md](../slices/323-slice.tech-debt-audit-baseline-harness.md) for the closed category vocabulary and the disjoint-severity rule.
- **Initiative 300 (LLM-as-Judge Scoring)**: owns gating. This component stays out of the gate path. See [300-arch.eval-actions-llm-as-judge-scoring.md](300-arch.eval-actions-llm-as-judge-scoring.md).
- **Initiative 100 (Orchestration v2)**: CLI command registration for the snapshot, ingest, report and baseline commands. See [100-arch.orchestration-v2.md](100-arch.orchestration-v2.md).
- **Initiative 420 (Model Benchmark)**: consumes snapshots and normalized review findings to score implementation replays.
- **Initiative 440 (Brownfield Adoption)** and **context-forge initiative 260**: consume the adoption baseline, offered at CF's handoff through 440's capability probe.
- **Initiative plan**: [001-initiative-plan.squadron.md](../project-guides/001-initiative-plan.squadron.md), entry 14.
