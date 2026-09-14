---
docType: review
layer: project
reviewType: tasks
slice: verification-that-verified-nothing
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/919-tasks.verification-that-verified-nothing-2.md
aiModel: deepseek/deepseek-v4-flash-0731
status: complete
dateCreated: 20260914
dateUpdated: 20260914
reviewedSha: 5b66a10e5feb3c0f61a48eb466bb51d494cfc3c0
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 12
findings:
  - id: F001
    severity: concern
    category: coverage
    summary: "Part 3 criterion 2 (default checkout unchanged) has no assigned test, and existing gate tests will break under D11"
    location: "tests/events/builtin/test_frontmatter_gate.py"
  - id: F002
    severity: concern
    category: test-coverage
    summary: "The stated-vs-derived mismatch branch is unpinned, leaving the \"compute from fallback_used\" option a silent-wrong-answer trap"
    location: "src/squadron/review/parsers.py#parse_review_output"
  - id: F003
    severity: note
    category: ambiguity
    summary: "T2.5's \"surfaces agree\" test wording is ambiguous about whether `to_dict()` emits the key"
    location: "project-documents/user/tasks/919-tasks.verification-that-verified-nothing-2.md"
  - id: F004
    severity: note
    category: sequencing
    summary: "Tests for T3.2/T3.3 are deferred three tasks to T3.7"
    location: "project-documents/user/tasks/919-tasks.verification-that-verified-nothing-2.md"
  - id: F005
    severity: note
    category: process
    summary: "Commit checkpoints within each part are implicit"
    location: "project-documents/user/tasks/919-tasks.verification-that-verified-nothing-2.md"
  - id: F006
    severity: pass
    category: nfr
    summary: "No load-test or CI-wiring requirement applies"
    location: "project-documents/user/slices/919-slice.verification-that-verified-nothing.md"
  - id: F007
    severity: pass
    category: traceability
    summary: "Part 2 success criteria 1–7 and Part 3 criteria 1, 3–7 all trace to concrete tasks"
    location: "project-documents/user/tasks/919-tasks.verification-that-verified-nothing-2.md"
---

# Review: tasks — slice 919

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4-flash-0731

## Findings

### [CONCERN] Part 3 criterion 2 (default checkout unchanged) has no assigned test, and existing gate tests will break under D11

Description: T3.7's success line claims "design success criteria 1-4 hold as executable tests," but the enumerated tests cover only criterion 1 (T3.2 zero-checked-against-nonempty fails), criterion 4 (T3.3 unparseable count fails), and criterion 3 (T3.4 empty staged list passes). No test pins criterion 2 — "in the default checkout, behavior is unchanged: valid frontmatter passes, invalid fails with cf's own findings" — i.e., `filesChecked >= 1` with exit 0 → success, and `filesChecked >= 1` with exit 1 → failure carrying cf's finding text. At the same time, the existing `TestExitMapping` tests feed fake stdout without a `filesChecked` key (e.g. `test_exit_0_succeeds` returns `b'{"totalFindings":0}'` with exit 0). Once T3.2/T3.3 land, D11's fail-closed rule makes an absent `filesChecked` a failure, so `test_exit_0_succeeds` (and likely `test_exit_1...`/`test_exit_2...` depending on message precedence) will go red. The task file neither predicts this mandatory update nor assigns the criterion-2 positive test, so a junior implementer discovers it only at T3.11's full run and must improvise the message-precedence decision (D11 message vs. exit-code message for nonzero exits) without design guidance. This should be stated explicitly: update the existing fake-process tests to include `filesChecked`, and add the criterion-2 pair (checked>0 + exit 0 passes; checked>0 + exit 1 fails with findings) to T3.7.

### [CONCERN] The stated-vs-derived mismatch branch is unpinned, leaving the "compute from fallback_used" option a silent-wrong-answer trap

Description: `fallback_used` is set True at two sites: the derivation branch (parsers.py:802) and the CONCERNS/FAIL-with-zero-findings mismatch branch (the block after parsers.py:816). In the mismatch branch the verdict was genuinely *stated* by the model (it came from `_extract_verdict`), so per D7's semantics it must be `STATED`. T2.2 invites deciding "whether `fallback_used` alone is sufficient" — it is not, and the task's own follow-on instruction ("every other branch that produces a real verdict sets STATED") is correct. But T2.3 enumerates only four cases (derived #96 shape, stated normal, stated normalized, nothing-parsed), none of which is the mismatch branch — the one place where `fallback_used == True` and `VerdictSource == STATED` diverge. A field-based implementation could regress there, and the "compute from fallback_used" alternative would silently mark a stated CONCERNS as `derived` (fail-safe direction, but wrong provenance and it breaks the design's stated-vs-derived orthogonality). Add the mismatch case to T2.3's list and pin `STATED`.

### [NOTE] T2.5's "surfaces agree" test wording is ambiguous about whether `to_dict()` emits the key

Description: Design criterion 6 requires the `to_dict()` JSON contract and frontmatter to agree. T2.4 assigns emission only to frontmatter (`_review_frontmatter_lines`, both call sites); T2.5's third test says "assert both surfaces report the same value for the same input." If JSON never emits `verdictSource` (it currently carries only `fallback_used`), "report the same value" cannot literally hold unless the test compares frontmatter's `verdictSource` against a JSON-derived expectation from `fallback_used`. Worth one sentence in T2.5 (or T2.2) deciding whether `to_dict()` also carries the key, since criterion 6's executable form depends on it.

### [NOTE] Tests for T3.2/T3.3 are deferred three tasks to T3.7

Description: The test-with pattern holds for T3.5→T3.6, but T3.2's and T3.3's own success criteria are phrased as behaviors ("a fake `cf` process returning exit 0 with `{"filesChecked": 0}` now fails") that are only verified in T3.7, after T3.4 and T3.5 — both further implementation. The batching is defensible (the three failure messages must be asserted pairwise in one place), but a junior implementer cannot confirm T3.2/T3.3 independently complete. Acceptable given T3.11's full-file gate; flagging so the delay is deliberate, not accidental.

### [NOTE] Commit checkpoints within each part are implicit

Description: Within Part 2 and Part 3 the only explicit commit tasks are T2.7 and T3.11 at each part's end; distribution relies entirely on CLAUDE.md's blanket "git add and commit from project root at least once per task." If the implementing agent treats each part as one unit and commits only at T2.7/T3.11, 18 tasks collapse into 2 commits — contrary to the distributed-checkpoint expectation. The reliance works, but one explicit line ("commit after each task per CLAUDE.md; the named message is the part's semantic closeout") would remove the ambiguity.

### [PASS] No load-test or CI-wiring requirement applies

Description: The slice design restates no NFR. D14's timeout is a hang bound (a Failure-Mode Enumeration requirement with its own observable-signal tests in T3.6/T3.7), not a throughput/latency load requirement, so the absence of a `tests/load/` task is correct, and consequently no CI wiring task is needed either.

### [PASS] Part 2 success criteria 1–7 and Part 3 criteria 1, 3–7 all trace to concrete tasks

Description: Criterion 1→T2.4/T2.5, 2→T2.1, 3→T2.5 (absence-asserted test), 4→T2.3/T2.5, 5→T2.2/T2.3, 6→T2.5, 7→T2.6; Part 3: 1→T3.2/T3.7, 3→T3.4/T3.7, 4→T3.3/T3.7, 5→T3.5/T3.6, 6→T3.8, 7→T3.6/T3.7, plus D13's CHANGELOG (T3.10) and the worktree reproduction (T3.9) — no scope creep was found, and no task fails to trace to a design decision or walkthrough requirement.

### Run Digest

- Response length: 7583 chars
- Response is newline-free: no
- Tool calls made: 12
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 70828
- `## Summary` located: no
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
