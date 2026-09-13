---
docType: review
layer: project
reviewType: tasks
slice: review-artifact-integrity
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/917-tasks.review-artifact-integrity-1.md
aiModel: z-ai/glm-5.3
status: complete
dateCreated: 20260912
dateUpdated: 20260912
reviewedSha: 251217ba5d8a168f5d62054505a0cb29e6fcd6f2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 30
findings:
  - id: F001
    severity: concern
    category: process
    summary: "Task 2.4's expected corpus result is wrong: a third invalid-verdict artifact exists in the corpus"
    location: "project-documents/user/tasks/917-tasks.review-artifact-integrity-1.md:179-182"
  - id: F002
    severity: pass
    category: coverage
    summary: "Success criteria coverage is complete across both task files"
    location: "project-documents/user/slices/917-slice.review-artifact-integrity.md"
  - id: F003
    severity: pass
    category: sequencing
    summary: "Sequencing, test-with pattern, and commit distribution are correct"
    location: "project-documents/user/tasks/917-tasks.review-artifact-integrity-1.md"
  - id: F004
    severity: pass
    category: scope
    summary: "No scope creep; out-of-code deliverables trace to design obligations"
    location: "project-documents/user/tasks/917-tasks.review-artifact-integrity-1.md"
  - id: F005
    severity: pass
    category: design-quality
    summary: "Task sizing and junior-completability are appropriate"
    location: "project-documents/user/tasks/917-tasks.review-artifact-integrity-1.md"
  - id: F006
    severity: pass
    category: nfr-coverage
    summary: "No NFR restated; no load-test or CI-wiring obligation applies"
    location: "project-documents/user/slices/917-slice.review-artifact-integrity.md"
  - id: F007
    severity: note
    category: design-quality
    summary: "Task 3.4's success criterion is ambiguous as written"
    location: "project-documents/user/tasks/917-tasks.review-artifact-integrity-1.md:252-267"
  - id: F008
    severity: note
    category: coverage
    summary: "The #92 digest clause is covered only compositionally"
    location: "project-documents/user/tasks/917-tasks.review-artifact-integrity-2.md"
  - id: F009
    severity: note
    category: process
    summary: "Code anchors are not re-verifiable from this working directory"
    location: "unverified"
---

# Review: tasks — slice 917

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3

## Findings

### [CONCERN] Task 2.4's expected corpus result is wrong: a third invalid-verdict artifact exists in the corpus

Task 2.4 instructs the implementer to run the gate over `project-documents/user/reviews/**/*.md` with "Expected: exactly two violations," naming `reviews/343-review.tasks.sq-skills-uninstall-and-sq-doctor-integration.md` and `reviews/archive/266-review.tasks.tool-use-configuration-and-limits.md` (both `verdict: RESOLVED`). I grepped every `^verdict:` line in the corpus, including `reviews/archive/`: the two named files are confirmed `RESOLVED` at line 7 of each, **but** `project-documents/user/reviews/305-review.tasks.findings-addressed-gate.part-1.md:7` carries `verdict: CONCERN` — the singular form, not the plural `CONCERNS` used by every other artifact in the corpus (its sibling `305-...part-2.md:7` correctly says `CONCERNS`), and not one of the four `Verdict` members the design names. The same artifact's body reads "**Verdict:** FAIL," contradicting its own frontmatter, which confirms corruption rather than a valid value.

Consequences: (1) a junior implementer hits a third violation where the task promised exactly two, undermining the dry run's purpose as a known-state check before enabling a repo-wide default-on commit gate; (2) the design's Part 2 done-when ("the gate passes against the existing review corpus before it is enabled") is unsatisfiable as written; (3) the task's escape hatch ("fix the artifact only if this slice produced it") leaves the 305 artifact permanently tripping the gate on any future commit that stages it, with no recorded disposition. Recommended fix in the task file: correct the expected count to three (or two known-plus-one), and add an explicit disposition for the 305 artifact — its body already says FAIL, so correcting the frontmatter to `verdict: FAIL` is a two-character fix, or record it as a permanent, DEVLOG-documented exception.

### [PASS] Success criteria coverage is complete across both task files

Every "Done when" clause in all six parts traces to at least one task. Part 1: rename (1.1), emitted-key test (1.2), `fallback_used`/`to_dict` untouched (1.1 constraint + 1.2 assertion). Part 2: BANANA/RESOLVED rejected with value and enum-derived allowed set, each member passes, no-verdict rejected, non-review ignored, enum-pinned assertion, corpus pass, EVENTS.md/140/CHANGELOG (2.1, 2.3, 2.4, 2.5). Part 3: fenced text yields nothing, out-of-section text yields nothing when the heading exists, the two slice-267 headingless fixtures parse to 6 findings with `findings_section_located=False` and no degraded render, five shapes still parse, heading variants, six templates plus `builders/code.py` fenced/delimited, synthetic echo yields only real findings, existing tests examined individually (3.5, 3.6, 3.7). Part 4: both paths write an artifact with `finish_reason`/`reasoning_chars`, `## Provider Failure` distinguishes it, gate passes it, telemetry distinguishes no-tools, prior artifact archived, exit 1 / `success=False` unchanged, #92 boundary (4.2–4.7). Part 5: every tri-state case including directory, unreadable, over-cap, `../`-never-opened (5.2–5.4). Part 6: digest on a PASS artifact, counts differ on the echo fixture, present regardless of verbosity, counts originate in the parser (6.1, 6.2). File 1 alone covers Parts 1–3; the split is explicit and cross-referenced in both directions, so partial coverage in file 1 is correct, not a gap.

### [PASS] Sequencing, test-with pattern, and commit distribution are correct

Within every part, each implementation task is immediately followed by its test task (1.1→1.2, 2.1/2.2→2.3, 3.2–3.4→3.5, 3.6→3.7, 4.1/4.2→4.3, 4.4→4.5, 4.6→4.7, 5.1–5.3→5.4, 6.1→6.2), and each part ends with its own verify-and-commit checkpoint (1.3, 2.6, 3.8, 4.8, 5.5, 6.3) — six distributed commits, not batched at the end, and 6.3 correctly holds the merge. Cross-part dependencies hold: Part 3's `FindingScanCounts`/`findings_section_located` fields (3.1, 3.4) exist before Part 5 reasons over findings and Part 6 renders them; Part 2's gate exists before Task 4.3 asserts the failure artifact passes it; Task 4.1's `ProviderError.tool_calls_made` exists before 4.2's writer reads it; Task 5.2's `_resolve_under` refactor precedes 5.3's use. No circular dependencies. One trivial inaccuracy: file 2's preamble says only "Parts 5 and 6 consume the fields" Part 3 adds, but Task 4.7's #92 boundary test also asserts on `findings_section_located` — harmless, since Part 4 is already sequenced after Part 3.

### [PASS] No scope creep; out-of-code deliverables trace to design obligations

Every task traces to a done-when or an explicit design obligation. Task 2.5's EVENTS.md row, 140-arch listing line, and CHANGELOG bullet are the F008-accepted deliverables the design names verbatim. Task 4.1's `ProviderError.tool_calls_made` is the design's "whatever tool telemetry exists" requirement (slice 265's D5, cited correctly here — the design's own "266 D5" mis-citation was not propagated). Task 4.8's and 6.3's CHANGELOG entries are consistent with the project's discipline of flagging user-visible behavior changes. The standing constraints are correctly operationalized as task-level guards: "no new `Verdict` member" (the gate computes its allowed set from the enum; the failure artifact uses existing `UNKNOWN`), `location_path()` untouched (5.1), `to_dict` unchanged (3.1), and the byte-for-byte snapshot check in 4.2 pins the frontmatter extraction refactor.

### [PASS] Task sizing and junior-completability are appropriate

No task needs splitting: the largest (2.1, 3.2, 3.4, 4.2, 4.4) are effort 2 with exact signatures, precise behavioral specs, and grep-checkable success criteria; none bundles more than one independently verifiable change. Nothing is so granular that tasks should merge — the verify-and-commit tasks are lightweight by design and serve as the required commit checkpoints. Test tasks enumerate concrete cases rather than exhortations (e.g. 2.3 lists nine cases including the two-file one-bad assertion; 5.4 lists the full tri-state matrix with the `../`-never-opened monkeypatch). Assertions follow the standing constraint (enum values, `ActionResult.success`, field values — e.g. 2.3's "iterate the enum in the assertion; do not spell the four values").

### [PASS] No NFR restated; no load-test or CI-wiring obligation applies

The design restates no performance, throughput, or latency NFR — its risks are commit-gate misfires, parse-behavior changes on real artifacts, and a write-only model field, all functional concerns covered by the unit/integration tests in Tasks 2.3, 3.5, 4.3–4.7, 5.4, and 6.2. No `tests/load/` task is warranted and none is missing; correspondingly, no CI-gating task is required.

### [NOTE] Task 3.4's success criterion is ambiguous as written

Task 3.4's success bullet — "`_FINDING_RE.finditer` appears in exactly one place (`_count_finding_matches`) plus the bounded scan" — says "exactly one place" and then adds a second place in the same sentence. The intent (two occurrences total: one in the counting helper, one in the bounded scan) is recoverable, but a junior implementer verifying with grep could read it either way. Reword to "appears in exactly two places: `_count_finding_matches` and the bounded scan."

### [NOTE] The #92 digest clause is covered only compositionally

Part 4's done-when says the #92 shape "renders as degraded through the existing UNKNOWN path and its digest shows no `## Findings`." Task 4.7 tests the facts on the #92 parse (`verdict=UNKNOWN`, 0 findings, `findings_section_located False`, `### Raw Response` via the existing degraded path), and Tasks 6.1/6.2 test digest rendering generically — but no single test renders the #92 shape through the completed digest. The composite claim holds by construction, so this is informational; if cheap, extend the 6.2 end-to-end case to the #92 fixture so the design's sentence is asserted once, end to end.

### [NOTE] Code anchors are not re-verifiable from this working directory

The task file's anchor table cites `src/squadron/review/parsers.py`, `models.py`, `persistence.py`, `events/builtin/`, the six template `*.yaml` files, and `tests/review/fixtures/` — none of which exist under this document tree, so the line-level anchors (traced at `e6e7a86` per the file's header) could not be independently confirmed here. I verified every claim that lives in the documents corpus: the two named `RESOLVED` artifacts, the third `CONCERN` violation above, and the two slice-267 archived artifacts' six-findings shape. This mirrors the NOTE the 267 tasks review itself recorded under the same constraint.
