---
docType: review
layer: project
reviewType: tasks
slice: pr-keyed-review-persistence
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/tasks/383-tasks.pr-keyed-review-persistence.md
aiModel: z-ai/glm-5.2
status: complete
dateCreated: 20260915
dateUpdated: 20260915
reviewedSha: 08fb295f3124c842d897459c9f8e3aabab8e6acc
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 8
findings:
  - id: F001
    severity: fail
    category: uncategorized
    summary: "Task 3.6 adds `rulesSource` to every review, contradicting Task 3.8's byte-identity assertion"
    location: "project-documents/user/tasks/383-tasks.pr-keyed-review-persistence.md"
  - id: F002
    severity: concern
    category: uncategorized
    summary: "No end-to-end test asserts written `rulesSource` matches the loader's actual source"
    location: "project-documents/user/tasks/383-tasks.pr-keyed-review-persistence.md"
  - id: F003
    severity: note
    category: uncategorized
    summary: "All success criteria trace to tasks; no scope creep detected"
    location: "project-documents/user/tasks/383-tasks.pr-keyed-review-persistence.md"
  - id: F004
    severity: note
    category: uncategorized
    summary: "Test-with pattern consistently applied; task sequencing respects dependencies"
    location: "project-documents/user/tasks/383-tasks.pr-keyed-review-persistence.md"
  - id: F005
    severity: concern
    category: uncategorized
    summary: "Task 3 is large — nine subtasks spanning protocol definition through byte-identity verification"
    location: "project-documents/user/tasks/383-tasks.pr-keyed-review-persistence.md"
---

# Review: tasks — slice 383

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.2

## Findings

### [FAIL] Task 3.6 adds `rulesSource` to every review, contradicting Task 3.8's byte-identity assertion

Task 3.6 instructs: "Add `rulesSource` as an optional key on **every** review, not only PR reviews (D6)." This changes the byte output of slice, arch, and step reviews by adding a new frontmatter key.

Task 3.8 then instructs: "Run `tests/review/test_persistence_migration.py` — slice and arch artifacts must match their Task 2 fixtures byte-for-byte. **Any diff is a regression, not an improvement. Do not update a fixture to match new output.**"

The Task 2 fixtures are captured *before* Task 3.6 runs (Task 2 explicitly states "before any persistence change"). Since `rulesSource` is a new key not present in those fixtures, adding it in 3.6 guarantees a byte diff, which 3.8 forbids. An implementer cannot satisfy both simultaneously: either they skip `rulesSource` on existing paths (violating 3.6 and D6's "on every review" requirement), or they update the fixtures (explicitly forbidden by 3.8).

Notably, Task 8.1 handles this same tension correctly for `targetKind`: it says "byte-identity fixtures updated only if `targetKind` addition is intended to change them — if so, confirm with the Project Manager first." Task 3.6 has no equivalent acknowledgment or escape hatch. The resolution is likely one of: (a) add `rulesSource` only for PR reviews and defer the "every review" goal to a later slice, (b) update fixtures with PM confirmation as 8.1 does, or (c) sequence `rulesSource` addition after the byte-identity migration completes. This must be resolved before implementation.

### [CONCERN] No end-to-end test asserts written `rulesSource` matches the loader's actual source

The success criterion states: "`rulesSource` reads `project`, `user`, or `template` and **matches the directory the loader actually used**, asserted for each branch." Task 1.3 tests that `resolve_rules_dir` *returns* the correct `RulesSource` for each branch, and Task 3.6 writes `rulesSource` to frontmatter. However, no task contains a test that writes a review artifact, reads the `rulesSource` field back, and asserts it matches the directory the loader actually selected. The connection between "resolve returns source X" (Task 1.3) and "artifact frontmatter contains source X" (Task 3.6) is never tested end-to-end. A junior AI implementing this plan could wire the source to the frontmatter incorrectly (e.g., hardcode a value, or fail to thread the `RulesSource` through to `frontmatter_fields()`) without any test catching it.

### [NOTE] All success criteria trace to tasks; no scope creep detected

Cross-referencing every functional and technical success criterion against the task list:

| Success Criterion | Covering Task(s) |
|---|---|
| PR review saves with PR-keyed name, `reviewedSha` = record head sha | 7.1, 7.2, 7.3 |
| Unplanned repo: saves externally, nothing written inside, `git status --porcelain` empty | 6.2, 7.3 |
| Full precedence chain table-tested | 6.4 |
| Each enumerated write-path failure mode asserted | 6.4 |
| `sq review resolve 42` / metrology select slice review with PR 42 present | 8.2 |
| Byte-identical to pre-migration fixtures on all three paths | 2.1, 2.2, 3.8, 4.2 |
| Step review refused on unarchivable target, action returns result | 4.2 |
| Archiving, digest, 917 integrity run on PR artifact unchanged | 8.3 |
| `rulesSource` matches loader source, each branch; artifact without key still parses | 1.3, 3.6 (partial — see CONCERN above) |
| PR-shaped artifact validates under `cf validate frontmatter`, `filesChecked` +1 | 9.2 |
| `ruff`/`pyright` clean | 9.4 + every commit task |
| No `review/` module imports `codehost` | 7.1, 9.4 |
| `SliceInfo` retains shape and consumers | 3.2 |
| Three `test_schema_drift.py` failures unchanged | 9.3 |

No task traces outside the slice design's scope. Every commit checkpoint (1.4, 2.3, 3.9, 4.3, 5.3, 6.5, 7.4, 8.4, 9.9) follows its implementation block — commits are distributed throughout, not batched at end.

### [NOTE] Test-with pattern consistently applied; task sequencing respects dependencies

Every implementation task block is immediately followed by its test task:
- 1.1–1.2 → 1.3; 2.1 → 2.2; 3.1–3.4 → 3.5; 3.6–3.7 → 3.8; 4.1 → 4.2; 5.1 → 5.2; 6.1–6.3 → 6.4; 7.1–7.2 → 7.3; 8.1 → 8.2.

Dependency chain is sound: Task 1 (rules source) → Task 2 (fixtures) → Task 3 (contract + migration) → Task 4 (step path) → Task 5 (path_key) → Task 6 (precedence) → Task 7 (PrTarget) → Task 8 (targetKind) → Task 9 (closeout). No circular dependencies. Task 5 (path_key) correctly precedes Task 7 (PrTarget needs it for the stem). Task 2 (fixtures) correctly precedes Task 3 (migration), and the task explicitly calls out that fixtures must be captured before any persistence change.

### [CONCERN] Task 3 is large — nine subtasks spanning protocol definition through byte-identity verification

Task 3 covers: protocol definition (3.1), three target implementations (3.2–3.4), implementation tests (3.5), frontmatter restructuring (3.6), two function migrations (3.7), byte-identity verification (3.8), and commit (3.9). Subtasks 3.6 and 3.7 are both effort 3 (the slice's highest), and 3.6 touches rendering that 917's artifact-integrity work depends on. While each subtask has clear success criteria, the aggregate scope is significant for a single task boundary. Consider splitting at 3.5/3.6 into "define and implement targets" (3.1–3.5, commit) and "migrate persistence and verify byte-identity" (3.6–3.8, commit) — this would also give a clean checkpoint between the additive (new protocol + implementations) and subtractive (replacing `SliceInfo` in `save_review_result`) halves of the migration.

## Response — 20260915

Reviewed sha `08fb295f`. Design and task file both corrected; re-review waived by the Project Manager.

### F001 — `rulesSource` contradicts byte-identity — ACCEPTED, fixed (option c)

Correct, and the defect was **the design's**, not only the task file's. The reviewer found one instance; there were two. D6 (line 328) writes `rulesSource` on every review, D4 (line 260) writes `targetKind` by every target, and D2 plus the success criterion at line 409 assert slice/arch/step artifacts are byte-identical. Three statements, mutually unsatisfiable. The task file inherited the contradiction faithfully — which is the one thing it did right. Task 8.1's "confirm with the PM" hedge papered over the `targetKind` half rather than resolving it.

Of the three resolutions offered, **(c) — sequence the keys after byte-identity verification** — is the only one that preserves every decision as written:

- **(a) PR-only keys** would gut D6's stated rationale ("equally true for a slice review and costs nothing") and D4's "written by every target through the contract."
- **(b) update fixtures with PM confirmation** makes byte-identity mean "identical except what we chose to add." A fixture updatable on intent cannot distinguish an intended key from unintended drift, which is the only condition the check exists to detect. It would leave the check nominally passing and substantively dead.
- **(c)** costs a resequencing and nothing else. Neither key's scope narrows.

Design changes: D2 gains the sequencing rule and its rationale; D4 and D6 each cross-reference it; the Excluded scope note, the line-409 success criterion, the risk mitigation, and the implementation order are all corrected. A new success criterion requires the regenerated fixtures to differ by **exactly those two keys and nothing else** — a third difference is drift the migration check would otherwise have hidden.

Task changes: Task 1 is retitled "signature only" with a scope note; Task 3.6 is prohibited from adding any new key; Task 8 is rebuilt as the combined both-keys step (8.1 write, 8.2 regenerate-and-pin-the-diff), with the former 8.2/8.3/8.4 renumbered to 8.4/8.5/8.6.

### F002 — no end-to-end `rulesSource` test — ACCEPTED, fixed

Correct. Task 1.3 tested that the resolver *returns* the right source; Task 3.6 wrote the field; nothing read it back off a written artifact. Both halves could be individually correct with a hardcoded value or a source never threaded to `frontmatter_fields()`, and every test would pass. The success criterion at design line 420 ("matches the directory the loader actually used") is an end-to-end claim that no task tested.

New **Task 8.3** writes an artifact, reads `rulesSource` back from the file, and asserts it matches the branch the loader took, for each of `project`, `user`, and `template` — with the explicit criterion that a deliberately hardcoded value must fail it. Added `tests/review/test_rules_source_artifact.py` to the design's test inventory so the two documents do not diverge.

### F005 — Task 3 is large — REJECTED, with reasoning

The observation is fair; the remedy is already delivered by the F001 fix. The reviewer proposes splitting at 3.5/3.6, between the additive and subtractive halves. That is where option (c) cuts anyway: 3.6 no longer carries the frontmatter key, so Task 3 is now protocol definition, three implementations, their tests, the rendering split, the function migration, and byte-identity verification — a single coherent migration with one checkpoint at 3.9.

Splitting on size alone, without the F001 fix, would have produced two tasks that still contradicted 3.8. Splitting now would add a commit boundary in the middle of a migration whose entire value is that it is verified as one unit against untouched fixtures. Nine subtasks at effort 1–3 each, with a commit at the end, is not over-scoped for that.

### F003, F004 — noted, no action

Both passes. The traceability table and the test-with/dependency audit are accurate and were useful confirmation; no change required.

### Run Digest

- Response length: 6521 chars
- Response is newline-free: no
- Tool calls made: 8
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 34527
- `## Summary` located: no
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5
