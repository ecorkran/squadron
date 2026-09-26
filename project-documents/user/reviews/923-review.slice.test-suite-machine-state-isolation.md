---
docType: review
layer: project
reviewType: slice
slice: test-suite-machine-state-isolation
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/923-slice.test-suite-machine-state-isolation.md
aiModel: claude-sonnet-5
status: complete
dateCreated: 20260926
dateUpdated: 20260926
reviewedSha: b279155ac6f6ed3aaa332f2dcbc0bf30c3816e77
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 9
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Scope fits the maintenance-and-refactoring container"
    location: "project-documents/user/architecture/900-arch.maintenance-and-refactoring.md#Scope"
  - id: F002
    severity: pass
    category: dependency-direction
    summary: "Integration point with 914 is consistent across documents"
    location: "project-documents/user/slices/923-slice.test-suite-machine-state-isolation.md#Integration-Points"
  - id: F003
    severity: concern
    category: scope
    summary: "Slice bundles three sequenced parts against an architecture that asks for small, focused slices"
    location: "project-documents/user/slices/923-slice.test-suite-machine-state-isolation.md#Technical-Scope"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Hostile-environment script's I/O failure modes are only partly enumerated"
    location: "project-documents/user/slices/923-slice.test-suite-machine-state-isolation.md:214-232"
  - id: F005
    severity: pass
    category: nfr
    summary: "No NFR restatement gap"
    location: "project-documents/user/architecture/900-arch.maintenance-and-refactoring.md"
---

# Review: slice — slice 923

**Verdict:** CONCERNS
**Model:** claude-sonnet-5

## Findings

### [PASS] Scope fits the maintenance-and-refactoring container

The slice is a test-infrastructure fix (leaked host state causing false-positive green runs) plus the `src/` refactors it depends on (import-time `Path.home()`, `.env` load timing). That's squarely "Tooling and CI" and "Bug fixes: non-trivial bugs that don't belong to an active feature slice" per the architecture's scope list, and it introduces no new product feature.

### [PASS] Integration point with 914 is consistent across documents

923 claims it provides a stable root conftest and `tests/_hermetic.py` for 914 to type, and that 914 shouldn't need to move/rename fixtures after this merges. Cross-checked against 914's own doc (`dependencies: [913, 923]`, "923's Part A adds an autouse root fixture... running 914 first would type those fixtures and then have 923 rewrite them") and the slice plan's entry for both — all three agree on direction and rationale. No inverted or contradicted dependency.

### [CONCERN] Slice bundles three sequenced parts against an architecture that asks for small, focused slices

The architecture doc states explicitly: "Slices in this initiative should be small and focused — prefer many small slices over few large ones." This slice is Parts A/B/C in one document: two `src/` refactors across 19 files, a new autouse conftest fixture, a new opt-out marker with a sweep, a new bash hostile-environment script, and a new CI job (Effort 4/5 per the slice plan). The doc's own justification — "eight instances of one class are the case for fixing the class" — is a reasonable engineering argument for treating this as one coherent unit rather than three separately-landable slices, and the bundling decision was already made at the slice-plan level (900-slices doc), not invented here. Still, it's a real tension with the architecture's stated preference worth surfacing rather than silently accepting.

### [CONCERN] Hostile-environment script's I/O failure modes are only partly enumerated

D9 introduces a new script with several I/O steps (network `git clone --no-local`, `uv sync --frozen`, a `pytest` subprocess run). Only two steps get explicit, observable failure handling: step 4 ("`command -v cf` must fail... stop with an error") and step 5 (the hostile-config probe, "stop with an error"). Steps 1 (clone) and 6 (cache resolution / `uv sync`) have no stated behavior if the clone fails, times out, or the network drops mid-transfer, and step 7 only checks the final pytest exit code. Nothing in the doc states whether the script runs under `set -e` or otherwise guarantees a clone/sync failure surfaces as a loud, non-zero exit rather than silently continuing into a run against a partially-populated checkout. Given this script is also gated into CI (D10), an unhandled hang or partial-clone failure there would either hang the job or produce a misleading result. Worth a one-line note on error propagation (`set -euo pipefail` or equivalent) and what "clone failed" looks like to whoever reads the CI log.

### [PASS] No NFR restatement gap

The parent architecture document states no NFRs (latency, throughput, or otherwise) for any path this slice touches, so there's nothing for the slice to restate. Not applicable, not a gap.

## Response (20260926)

One of two concerns was accepted, and the slice design has been revised.

- **F003: rejected.** The bundle was decided at the slice-plan level, and the finding itself acknowledges that. The three parts are not independently landable:
  - Part C's negative control and CI job exist to prove Part A.
  - Part B's sweep is driven by Part C's hostile run (D8).
  - Landing A without C would repeat the unverified "isolated" claim that #47 is filed against.

  The slice stays whole.
- **F004: accepted, with one correction.** D9 now requires `set -euo pipefail`. Every setup step fails with a labeled `hostile-env: <step> failed` line on stderr, so a setup failure never reaches pytest and is distinguishable from a test failure in the CI log. D10 now bounds the job with `timeout-minutes`. The correction: `git clone --no-local` is a local disk copy, not a network operation; only `uv sync` can reach the network, and only on a cache miss.

### Run Digest

- Response length: 3883 chars
- Response is newline-free: no
- Tool calls made: 9
- Tool calls failed: 0
- Stop reason: end_turn
- Reasoning characters: 0
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5
