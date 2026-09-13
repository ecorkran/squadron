---
docType: review
layer: project
reviewType: tasks
slice: review-artifact-integrity
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/917-tasks.review-artifact-integrity-2.md
aiModel: z-ai/glm-5.3
status: complete
dateCreated: 20260912
dateUpdated: 20260912
reviewedSha: 251217ba5d8a168f5d62054505a0cb29e6fcd6f2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 33
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "`_count_lines`' specified signature cannot produce the WARNING the design and standing constraints require"
    location: "tasks/917-tasks.review-artifact-integrity-2.md:167"
  - id: F002
    severity: concern
    category: design-quality
    summary: "Task 4.6's `slice_info`-absent pipeline branch does not compose with the writer Task 4.2 specifies"
    location: "tasks/917-tasks.review-artifact-integrity-2.md:108-118"
  - id: F003
    severity: note
    category: coverage
    summary: "The #92 digest clause is still covered only compositionally"
    location: "tasks/917-tasks.review-artifact-integrity-2.md:230-240"
  - id: F004
    severity: note
    category: integration
    summary: "The shared frontmatter helper and failure writer do not thread slice 266's suppression reason"
    location: "tasks/917-tasks.review-artifact-integrity-2.md:51-58"
  - id: F005
    severity: note
    category: documentation
    summary: "File 2's preamble understates Part 3's consumers"
    location: "tasks/917-tasks.review-artifact-integrity-2.md:21"
  - id: F006
    severity: note
    category: process
    summary: "Code anchors are not re-verifiable from this working directory"
    location: "unverified"
  - id: F007
    severity: pass
    category: coverage
    summary: "Every \"Done when\" clause of Parts 4–6 traces to at least one task"
    location: "tasks/917-tasks.review-artifact-integrity-2.md"
  - id: F008
    severity: pass
    category: sequencing
    summary: "Sequencing, test-with pattern, and commit distribution are correct"
    location: "tasks/917-tasks.review-artifact-integrity-2.md"
  - id: F009
    severity: pass
    category: scope
    summary: "No scope creep; every task traces to a design obligation"
    location: "tasks/917-tasks.review-artifact-integrity-2.md"
  - id: F010
    severity: pass
    category: design-quality
    summary: "Task sizing and junior-completability are appropriate"
    location: "tasks/917-tasks.review-artifact-integrity-2.md"
  - id: F011
    severity: pass
    category: nfr-coverage
    summary: "No NFR is restated; no load-test or CI-wiring obligation applies"
    location: "slices/917-slice.review-artifact-integrity.md"
---

# Review: tasks — slice 917

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3

## Findings

### [CONCERN] `_count_lines`' specified signature cannot produce the WARNING the design and standing constraints require

The design's F006-accepted failure-mode list (slices/917-slice.review-artifact-integrity.md:134) says every could-not-run case "yields `None` with a WARNING naming the finding and the reason," and file 1's standing constraint (tasks/917-tasks.review-artifact-integrity-1.md:81) repeats it: "`None` on `location_verified` is always accompanied by a WARNING naming the finding and the reason." Task 5.2 specifies `_count_lines(root, resolved) -> int | None` — a signature with no finding identifier — and Task 5.3 then delegates the directory/over-cap/`OSError`/outside-root cases to it with "(WARNING already logged there)," precluding a second, finding-naming WARNING at the `_check_line_bounds` call site. As written, a junior AI must either violate the specified signature (thread the finding summary/location into `_count_lines`) or log a WARNING that cannot name the finding — and Task 5.4's caplog assertions only check a WARNING exists, not its content, so the violation would not be caught. Fix is small: add a `finding` parameter to `_count_lines`, or move the None-case logging into `_check_line_bounds` (which iterates findings and has the name in hand).

### [CONCERN] Task 4.6's `slice_info`-absent pipeline branch does not compose with the writer Task 4.2 specifies

Task 4.6 instructs: "call `save_provider_failure` using `slice_info` when present, else the step-name/index naming the existing save branch uses." But Task 4.2's writer signature (tasks/917-tasks.review-artifact-integrity-2.md:51-58) takes `slice_info` positionally and its body template is hardcoded as `# Review: {review_type} — slice {index}`. For the `slice_info`-absent branch: (1) passing "the step-name/index" where `slice_info` is expected is a type mismatch under the file's own zero-errors pyright gate, unless the signature is widened — a decision the task leaves to the implementer; (2) the rendering of a slice-less failure artifact (which frontmatter slice fields, what the `— slice {index}` body line becomes) is unspecified; (3) Task 4.7 tests only the `slice_info`-present shape, so the absent branch ships untested. If the pipeline review action in practice always has `slice_info`, the task should say so and drop the "else"; if the branch is reachable, `format_provider_failure_markdown` needs a slice-less rendering spec and 4.7 needs a case for it. Either way the two tasks should be reconciled before a junior AI picks up Part 4.

### [NOTE] The #92 digest clause is still covered only compositionally

The part-1 review's F008 recorded that Part 4's done-when ("its digest shows no `## Findings`") is asserted only compositionally — Task 4.7 pins the #92 parse and degraded render, Tasks 6.1/6.2 pin digest rendering generically — and suggested, if cheap, extending 6.2's end-to-end case to the #92 fixture. The task file was not revised: 6.2's end-to-end case still uses only the echo-then-real response from Task 3.5. The composite claim holds by construction, so this remains informational, but the suggestion was available and not taken.

### [NOTE] The shared frontmatter helper and failure writer do not thread slice 266's suppression reason

Task 4.2's `_review_frontmatter_lines` parameter list (verdict, model, review_type, slice fields, source_doc, today, reviewed_sha, revision_number, tools_given, tool_calls_made) and the failure writer's `tools_given` input carry no suppression reason. Slice 266 established that a tools-suppressed run is distinguished in persisted frontmatter by `toolsSuppressedReason` (slices/266-slice.tool-use-configuration-and-limits.md:433), and archived 266 artifacts carry it. I could not verify from this working directory whether the live frontmatter block emits that key directly (in which case 4.2's extraction parameter list is incomplete — though the byte-for-byte snapshot at test_persistence.py:824 would catch that for the normal path) or whether it is stamped post-hoc like `revision_number`. Either way, a failure artifact from a tools-suppressed run collapses "suppressed" with "never offered," and Task 4.3 tests only `tools_given=["read_file"]` and `tools_given=None`. The design's done-when only requires 265 D5's distinction, so this is within scope as designed — recording it as a fidelity note for the implementer.

### [NOTE] File 2's preamble understates Part 3's consumers

The preamble says "Parts 5 and 6 consume the fields [Part 3] adds to `ReviewResult`," but Task 4.7's #92 boundary test also asserts on `findings_section_located` (line ~125). Harmless — Part 4 is already sequenced after Part 3 — and already recorded as a trivial inaccuracy by the part-1 review; noting it here only because it lives in this file.

### [NOTE] Code anchors are not re-verifiable from this working directory

As with the part-1 review (its F009), this document tree contains only project documents — `src/squadron/...`, the six template YAMLs, and `tests/` are absent — so the anchor table's line-level citations (`review.py:548/627/800`, `actions/review.py:238/283-300`, `agent.py:67/222/432`, `persistence.py:210-238`, `test_persistence.py:824`) were taken on trust from the file's "traced on `e6e7a86`" header. Document-internal claims were verified where possible: `resolve_reviewed_sha` exists as a shared helper (slice 306), `revision_number` is an optional `format_review_markdown` input (slice 911), and `tools_given`/`tool_calls_made` have been `ReviewResult` fields since slice 265 — which also confirms Task 6.1's `_run_digest_lines(result)` can read both telemetry values from the result alone.

### [PASS] Every "Done when" clause of Parts 4–6 traces to at least one task

Part 4: both paths produce an artifact with `finish_reason`/`reasoning_chars` (4.4–4.7); `## Provider Failure` marker and Part 2 gate pass (4.2, 4.3); distinguishable from clean UNKNOWN by the section and from a no-tools run by telemetry keys present/absent (4.2, 4.3); prior artifact archived (4.3, 4.5, 4.7); CLI exit 1 / pipeline `success=False` unchanged (4.4, 4.5, 4.6, 4.7); #92 renders degraded through the existing UNKNOWN path (4.7). Part 5: the full tri-state matrix — no `cwd` → `None`, `:999999` → `False`, in-bounds → `True`, whole-file and `UNVERIFIED_LOCATION` → `None`, range form parses (5.1 `:42-50` → 50; 5.4 `file.py:3-10` → `True`), `location_path()` untouched (5.1), #91 phantom → `False` (5.4), directory/unreadable/over-cap/`../` each `None` with the last never opened (5.2, 5.4). Part 6: digest on a PASS artifact, counts differ on the echo fixture (6.2 end-to-end), present regardless of verbosity, raw-response behavior unchanged, counts originate in the parser not a re-parse (6.1, 6.2). No success criterion is unowned.

### [PASS] Sequencing, test-with pattern, and commit distribution are correct

Implementation is immediately followed by its tests in every case: 4.2→4.3, 4.4→4.5, 4.6→4.7, 5.1–5.3→5.4, 6.1→6.2; Tasks 4.1 and 5.1 embed a single-assertion test as a bullet inside the effort-1 task, which is the right granularity rather than a violation. Commit checkpoints are distributed — 4.8, 5.5, 6.3 here plus 1.3, 2.6, 3.8 in file 1 — six commits, with the merge and status flips correctly held in 6.3 rather than batched. Cross-part dependencies hold and are explicitly guarded: the preamble requires Part 3 complete and committed first; 4.1's `ProviderError.tool_calls_made` precedes 4.2's writer reading it; Part 2's gate precedes 4.3's gate assertion; 5.2's `_resolve_under` refactor precedes 5.3's use; Part 6's digest reads only fields Part 3 added. No circular dependencies.

### [PASS] No scope creep; every task traces to a design obligation

Task 4.1's `ProviderError.tool_calls_made` is the design's "whatever tool telemetry exists" (265 D5, cited correctly here — the design's "266 D5" mis-citation was not propagated). Task 4.2's frontmatter extraction is the design's "extracted into a shared helper, not duplicated," and its byte-for-byte snapshot pin is the right guard. Task 4.7's #92 boundary test is the design's "A test here confirms that." Task 5.4's synthetic #91 phantom is Part 5's done-when. Task 6.1's `finding_scan is None` → "not computed" handling and fixture update are required by the design's "always-on digest" and are the one flagged intended snapshot change. 4.8/6.3's CHANGELOG and DEVLOG entries are close-out obligations, consistent with project discipline. The `no_save`, `--no-save`, and `Optional` failure-target typing correctly respect 916's save-gating decisions rather than reopening them.

### [PASS] Task sizing and junior-completability are appropriate

Efforts are 1–2 with exact signatures (`format_provider_failure_markdown`'s full keyword-only contract, `location_line`'s five-case table, `_count_lines`'s enumerated None conditions), enumerated test cases rather than exhortations (4.5's three CLI scenarios, 5.4's full tri-state matrix including the `../outside.py` never-opened monkeypatch and the root-skip guard), and grep- or command-checkable success criteria. Nothing needs splitting; nothing is so granular it should merge. The one loose signature — `save_provider_failure(...)` given as an ellipsis — is inferable from 4.4/4.6's call descriptions (it takes the formatter's context plus the write target), so it does not impede a junior implementer; the two CONCERNs above are the only places where the spec forces an unguided decision.

### [PASS] No NFR is restated; no load-test or CI-wiring obligation applies

The slice design restates no performance, throughput, latency, or availability NFR — its risks are commit-gate misfires, parse-behavior changes on real artifacts, and a write-only model field, all functional concerns covered by the unit/integration tests in 4.3–4.7, 5.4, and 6.2. No `tests/load/` task is warranted and none is missing; correspondingly, no CI-gating task is required. This matches the part-1 review's F006.
