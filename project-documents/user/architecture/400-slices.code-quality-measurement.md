---
docType: slice-plan
parent: 400-arch.code-quality-measurement.md
project: squadron
dateCreated: 20261020
dateUpdated: 20261020
status: not_started
---

# Slice Plan: Code Quality Measurement

## Parent Document
`400-arch.code-quality-measurement.md`: Architecture: Code Quality Measurement

## Planning Context
Architecture-level. The parent went through one design review (CONCERNS, all ten findings accepted and folded in), so the load-bearing decisions are settled: coarse records in 320's store, a closed metric enum with full measurement identity, absent-with-reason, commit export for non-HEAD commits, durable slice-range records, code-review-only normalization, and no pipeline hook.

The plan keeps the architecture's five slices with one boundary moved. Commit export (measuring a commit other than a clean HEAD) moves out of the keystone and into the reports slice, which is its first real consumer: reports take missing fork and merge snapshots on demand. The keystone measures a clean HEAD only, which is enough to prove the record, the metric identity and two adapters.

Ordering:
- The keystone (400) comes first and alone. Slices 401, 403 and 404 read its record.
- Code-review normalization (402) depends only on 320, so it can run in parallel with 400 or 401.
- Reports (403) need snapshots (400) and review records (402).
- The baseline command (404) needs only the snapshot and 323's audit harness. It comes last because it's a thin composition, and 440 is its only external consumer.

---

## Foundation Work

1. [x] **(400) Snapshot Record and First Adapters (keystone)**: The snapshot record type in 320's store, the closed metric enum, the adapter contract, and two adapters: Python, plus one non-Python language. Metrics are file and function length, lint counts and type counts. The second language covers length and lint only, which is enough to prove the contract isn't Python-shaped before it hardens. A snapshot is taken of a clean HEAD, read-only; a dirty tree is refused.
   - **Value:** Architectural enablement. Every later slice reads this record, and squadron's own size limits get checked for the first time.
   - **Success Criteria:**
     - `sq` takes a snapshot of a clean HEAD and writes one record per commit to the metrology store, keyed on `ProjectId` and commit SHA. A dirty tree is refused with an explicit error.
     - Every measurement carries metric (enum member), language, tool, tool version and, for lint and type counts, the rule set. Snapshots on the same commit with the same tools and environment give identical values.
     - File and function length are checked against limits read from project config. With no limits declared, the record holds distributions and says no limits were set. Per-function rows exist only for functions over the limit.
     - A metric that can't be measured is recorded as absent with a reason: no adapter, tool missing, or environment not resolved. Type counts are absent unless the project's environment is resolved, and the record carries the lockfile hash when it is.
     - One effective exclusion set is recorded per snapshot. Squadron's vendored `commands/analysis/` is excluded on its own repo.
     - The measured repository is unchanged after a snapshot, and the existing metrology record types still load (no schema migration).
   - **Dependencies:** [100, 320]
   - **Interfaces:** Provides the snapshot record type, the metric enum, and the adapter contract that 401 extends. Consumes 320's store, envelope and `ProjectId`.
   - **Risk Level:** High. The metric identity, adapter contract and record shape are decided here, and every later slice inherits them.
   - **Relative Effort:** 4/5

---

## Feature Slices (in implementation order)

2. [ ] **(401) Complexity, Duplication and Coverage**: The remaining static metrics, added to both 400 adapters through the existing contract. Coverage is read from a report the project already produces. The snapshot doesn't install dependencies or run tests itself.
   - **Value:** Developer value. Complete static snapshots, which 420 needs for scoring.
   - **Success Criteria:**
     - Complexity and duplication are measured for both languages, and each adapter states how it counts.
     - Coverage is recorded when the project's coverage report exists and matches the commit; otherwise it's absent with a reason.
     - Adding these metrics needs no change to the record envelope or adapter contract beyond new enum members.
   - **Dependencies:** [400]
   - **Interfaces:** Extends 400's adapters and metric enum.
   - **Risk Level:** Medium. Tool definitions of complexity and duplication differ, and that difference has to land in the tool identity.
   - **Relative Effort:** 3/5

3. [ ] **(402) Code-Review Normalization and Ingest**: The `code` review template emits categories from the audit vocabulary plus the review-only `correctness`, keeping the model's raw string beside it. An ingest command reads code-review files into the store, one record per review file with findings inline. Historical reviews are mapped read-side and marked as mapped. Arch, slice and tasks reviews are untouched.
   - **Value:** Developer value. Review findings become countable next to audit findings for the first time.
   - **Success Criteria:**
     - New `code` reviews carry a category from the closed set, with the raw string kept. Out-of-vocabulary categories normalize to `other`.
     - 323's sync test covers the third copy of the vocabulary (enum, audit skill, `code` template), and drift fails CI.
     - Ingest writes one record per review file, tied to project and commit and, when it resolves, to the slice. `uncategorized` is treated as missing. Read-side mapped findings are marked as such.
     - Review and audit severities stay separate, and the existing disjoint-severity test still passes.
     - Arch, slice and tasks review output is unchanged.
   - **Dependencies:** [320]. Independent of 400.
   - **Interfaces:** Provides the review-finding record type and the review-side category set (`AuditCategory` plus `correctness`). Consumes review files and 320's store.
   - **Risk Level:** Medium. Changing the review template's output parsing touches a heavily used path.
   - **Relative Effort:** 3/5

4. [ ] **(403) Slice Ranges and Rollup Reports**: Durable slice-range records, commit export for measuring non-HEAD commits, and the reports. A slice's range is resolved from git topology or the existing `git_utils` resolver and written to the store the first time it resolves. Reports take missing fork and merge snapshots on demand through commit export, then show per-slice, per-project and over-time breakdowns across snapshots, audit runs and review records.
   - **Value:** Developer value. "Did this slice make the code better?" gets a measured answer, and trends become visible.
   - **Success Criteria:**
     - A slice merged with a real merge commit resolves from topology alone, with no reflog. A fast-forward merge resolves through the existing resolver while its reflog lasts. Either way the range is persisted, and it still resolves after reflog expiry or in a fresh clone.
     - A non-HEAD commit is measured from a `git archive` export without writing to the measured repo's `.git`. Type counts at an exported commit are absent unless its lockfile matches the current environment.
     - Reports compare measurements only on full identity match, and flag the rest (tool change, rule-set change, environment change) instead of diffing them.
     - LLM-sourced numbers are shown against their noise floor, and every figure carries its sample size. No composite score appears anywhere.
     - Slices whose range never resolved appear at project level only, never under a guessed slice.
   - **Dependencies:** [400, 402]
   - **Interfaces:** Provides the slice-range record type, commit export, and report commands. Consumes snapshot, review, audit and noise-floor records, and `review/git_utils.py`.
   - **Risk Level:** Medium. Range resolution across fast-forward merges and fresh clones has known gaps, so the persistence has to be right the first time.
   - **Relative Effort:** 4/5

5. [ ] **(404) Adoption Baseline Command**: One standalone command that takes a snapshot of the project and runs 323's audit baseline with its noise floor. Before spending, it reports the file count and byte count after exclusions and the number of audit runs. It uses 320's configured audit profile and model.
   - **Value:** User value. An existing project gets a measured starting point in one step. 440 offers this at adoption.
   - **Success Criteria:**
     - One command produces a snapshot record, an audit run and an audit noise floor for the project.
     - The scope report (files, bytes, audit runs) prints before any LLM call. It's informational and doesn't wait for confirmation.
     - The audit profile and model come from 320's config, and a missing config fails explicitly.
     - The command runs on a project with no squadron or cf setup beyond a git repository.
   - **Dependencies:** [400], plus 323's audit harness.
   - **Interfaces:** Provides the baseline command that 440's probe advertises. Consumes 400's snapshot and 323's audit and noise-floor commands.
   - **Risk Level:** Low
   - **Relative Effort:** 2/5

---

## Integration Work

None planned. Each slice ships its own CLI surface and docs.

---

## Future Work

- **Fixed reference rule set.** Lint and type counts under a fixed rule set, so projects can be compared to each other. The keystone records only the project's own rules.
- **Dependency installation for type counts and coverage.** Resolve a project's environment for an exported commit instead of recording those metrics as absent. This has real security and environment cost.

---

## Notes

Slice indices 400–404 are tentative and sit in the initiative's 400 band.
