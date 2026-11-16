---
docType: reference
project: squadron
dateCreated: 20261116
dateUpdated: 20261116
status: draft
---

# Design, architecture and task review recall: candidate cases, batch 2 (self-verified, 2026-11-16)

Read-only pass over `/Users/manta/source/repos/manta/squadron` using `git show`, `git diff`, `git log`, `git grep` at the reviewed commit. Nothing was checked out, no model was called, no `sq` command was run. 15 candidates examined (all of `batch2.json`). The stop rule did not trigger: 7 of the first 8 produced a valid case.

Validity rule applied (same as `design-review-recall-cases.md`): a flaw counts only if, in the text the reviewer saw (`<commit>^:<doc>`), the document contradicted itself, its parent, or code in the repo at that commit, left out something its own success criteria required, or held a task that could not be completed as written. It does not count if the correction follows a later decision, scope change, new gate or capability, filled-in unspecified detail, a style or size opinion, or facts that only existed after other slices were built. Borderline items are INVALID and tagged `borderline`.

What differs from batch 1: no later independent commit proves the flaws. The saved review's findings and the response diff were leads only. Every valid flaw below was checked by me against the pre-response document and, where named, the code or sibling documents at `<commit>^`. A reviewer claim I could not verify is INVALID (unproven). Each valid flaw says whether the original review raised it; the original reviewer's model is the control.

Labels on evidence: **read** = I read the reviewed text, the response diff and the code or sibling document named. Every item below is **read**; none is **inferred**.

Flaw types: **doc** = needs only the reviewed document (or its parent design / sibling documents, no source code); **code** = needs source code at the reviewed commit. Tag `coverage` marks a valid flaw of the form "the task file's tests omit a branch its parent design's success criterion names". These are the softest valid flaws; drop them if only strong flaws are wanted.

## Totals

- Candidates examined: 15
- Cases with at least one valid flaw: 11 (320-arch, 360-arch, 380-arch, 400-arch, 197-tasks, 264-tasks, 306-tasks, 322-tasks, 363-tasks, 385-tasks, 917-tasks)
- Cases with no valid flaw: 4 (155-tasks, 381-tasks, 913-tasks, 922-tasks)
- Valid flaws: 19 (15 need only documents, 4 need code at the reviewed commit). 6 of the 15 document-only flaws are `coverage` (264 x1, 306 x1, 363 x4); without them: 13 strong flaws, 9 doc and 4 code.
- Original review raised: 19 of 19. I found no verifiable flaw that the original review missed. Every valid flaw is a control for the original reviewer's model.
- Invalid or unproven: about 75 findings and response-diff items (24 tagged borderline; the rest are unspecified detail filled in, scope or decision changes, style, or reviewer claims I could not verify).
- Original reviewer models: claude-fable-5 (320), minimax/minimax-m3 (360, 380, 306, 913), claude-opus-5-5 (400, 197), z-ai/glm-5 (155), moonshotai/kimi-k3 (264, 385), moonshotai/kimi-k2.7-code (322), qwen/qwen3.8-2.4t-a95b (363), z-ai/glm-5.3-flash (381), z-ai/glm-5.3 (917), deepseek/deepseek-v4-pro (922).

## Caveats

1. **380 pairing differs from `batch2.json`.** The review file now in the tree is a later glm-5.3 round (`reviewedSha b49cca4e`, after this response). The file added by commit `76bd0251` is a minimax/minimax-m3 review with `reviewedSha f81fd1de`, which is `76bd0251^`. I used the minimax-m3 review (`git show 76bd0251:<review>`). The glm-5.3 findings in the working tree refer to text that did not exist at `76bd0251^`.
2. **197 model differs from `batch2.json`.** The review frontmatter says `aiModel: claude-opus-5-5`, not sonnet-5-5.
3. **155's commit is a closeout, not a review response.** The only doc change is check-offs, and code for the whole slice already exists at `3a8d7326^`. The task file reviewed was written before implementation but sits next to the finished code.
4. **Review files committed with the response can carry a Resolution section** (306, 385, 917 and others). The reviewer did not see it.
5. **Shell note:** with zsh, write `git show "${C}:path"` when `C` ends in `^`; `"$C:path"` is read as a modifier.

---

## 1. squadron-320-arch

- repo squadron; `project-documents/user/architecture/320-arch.judge-calibration-quality-metrology.md`; kind arch
- reviewed-at: `e46daac3^` (no `reviewedSha`). Review `reviews/320-review.arch.judge-calibration-quality-metrology.md`, CONCERNS, **claude-fable-5**, 11 findings.
- response commit: `e46daac3` "review: address 320 arch review concerns (F001-F011)" (read)
- flaws:
  - Technical Considerations and Related Work say "140's `fan_out`" (lines 81, 110), but 140's own slice plan says fan-out was relocated to initiative 180 (`140-slices.pipeline-foundation.md:158`, "Slice 159 (Fan-Out / Fan-In) relocated to initiative 180"; `180-slices.pipeline-intelligence.md:39` slice 182 `fan_out`), while the parent initiative plan says 320 is "Independent of 180" (`001-initiative-plan.squadron.md:44`). **VALID**: contradicts the parent plan and 140's documents. Needs: doc (sibling documents). Raised by the original review (F004).
  - F001 (judge-configuration identity keyed by template version, but `ReviewResult` has `template_name` and `model` and no version; read-side principle forbids changing it). INVALID (borderline): I confirmed `ReviewResult` has no version field (`review/models.py` at `e46daac3^`), but the identity is for 320's own new metrology records, which can hash template content at capture time, as the review itself concedes; the doc defers granularity to slice design.
  - F005 (frontmatter `dependencies: [100, 140, 300]` omits 340). INVALID (borderline): the list matches the parent plan's line 44 ("320 depends on 100, 140, 300"); the plan only calls 320 a consumer of 340.
  - F011 (skill named `tech-debt-audit` versus 340-arch's `tech-debt-analyze`). INVALID: the premise is inverted. The shipped file is `commands/analysis/tech-debt-audit.md` at the reviewed commit, so 320 matches the code.
  - F002 (graduation ends sampling), F003 (human anchoring), F006 (store constraints deferred), F007 (pre-emption data path), F008 (oracle noise floor), F009, F010 ("built once" wording). INVALID: new principles, filled-in unspecified detail or opinion; none contradicts the text, a parent or code.

## 2. squadron-360-arch

- `project-documents/user/architecture/360-arch.document-intelligence.md`; arch
- reviewed-at: `d69d9ee8^` = `e7300471` (equals the review's `reviewedSha`). Review `reviews/360-review.arch.document-intelligence.md`, PASS, **minimax/minimax-m3**, 12 findings.
- response commit: `d69d9ee8` "docs: address arch review findings for initiative 360" (read)
- flaws:
  - Output Conventions: "Both capabilities write to the existing `project-documents/user/analysis/` directory" (line 243) and the settled list (lines 332-333), while Capability 1 Outputs writes the concept to `project-documents/user/project-guides/000-concept.{project}.md` (line 148). **VALID**: self-contradiction. Needs: doc alone. Raised by the original review (F001; the response calls it "a factual error").
  - F002 (provenance undefined), F003 (initiative-candidate heuristic), F004 ("structural" undefined), F005 (status for a generated document), F006 (`.gitignore` write owner and failure), F007 (no shape check on the graph), F008 ("sacred" section dependency), F009 (command registration), F010 (translation principles unenforced), F011 (git precondition), F012 (graph reading strategy). INVALID: each is unspecified detail filled in or an added failure mode. The status enum named in the doc matches `documents/schema.py` at the reviewed commit.

## 3. squadron-380-arch

- `project-documents/user/architecture/380-arch.pull-request-workflow.md`; arch
- reviewed-at: `76bd0251^` = `f81fd1de` (the review's `reviewedSha`; see caveat 1). Review as committed in `76bd0251`, CONCERNS, **minimax/minimax-m3**, 12 findings.
- response commit: `76bd0251` "review: address initiative 380 architecture review findings" (read)
- flaws:
  - "Rules outside a planned project": "In an unplanned repository the review runs with the template's rules and language auto-detection only, and says so" (line 175). `review/rules.py:resolve_rules_dir` at `76bd0251^` resolves CLI flag, config, `{cwd}/rules/`, `{cwd}/.claude/rules/`, then `~/.config/squadron/rules/`, so a review in an unplanned repository can load rules from the repo or the user directory, silently. **VALID** (minor): contradicts code. Needs: code. Raised by the original review (F012). The response changed the doc to "reported, not suppressed".
  - F001 (persistence "generic target" contradicts code). INVALID: the doc says only the CLI helper is generic and persistence will be made generic; I confirmed `_resolve_save_outcome[SaveTargetT]` is generic and the callee is not, which is the doc's claim.
  - F002 (minimal-`SliceInfo` pattern leaves two persistence shapes). INVALID: scope addition (migrating `review_arch`).
  - F004 (metrology keys on `slice:` in `capture.py` and `discovery.py`). INVALID (unproven): at `76bd0251^` both only glob `{index}-review.*` and `*-review.*`; there is no `slice:` key. The response DEVLOG says the same.
  - F003 (metadata injection path), F005 (worktree invariants), F006 (adapter with one implementation), F007 (composition model path), F008 (tasks versus body sections), F009 (default PR base), F010 (delimiter), F011 (`gh` failure test strategy). INVALID: unspecified detail filled in, opinion, or a tests-strategy choice. F008 is borderline: tasks are an input, not a promised section.

## 4. squadron-400-arch

- `project-documents/user/architecture/400-arch.code-quality-measurement.md`; arch
- reviewed-at: `2b3bc66f^` = `0c6c4898` (the review's `reviewedSha`). Review `reviews/400-review.arch.code-quality-measurement.md`, CONCERNS, **claude-opus-5-5**, 10 findings.
- response commit: `2b3bc66f` "docs: revise 400 architecture for design review findings" (read)
- flaws:
  - Design Goals: the headline report example "error-handling findings: 4 from review, 2 from audit". `AuditCategory` at `0c6c4898` (`metrology/models.py:135-144`) has `ERROR_HANDLING_OBSERVABILITY = "error-handling-observability"` and no `error-handling`. **VALID** (minor): contradicts code. Needs: code. Raised by the original review (F007).
  - Current State: "`category` is a free string the model chooses, and is `None` on many findings", read by ingest from review frontmatter. `ReviewResult.structured_findings` (`review/models.py:~401`) writes `category=f.category or "uncategorized"`, so the frontmatter never holds `None`. **VALID**: contradicts code, and ingest would have to handle a sentinel string instead. Needs: code. Raised by the original review (F007).
  - F001 (slice attribution versus `git_utils`; reflog-only fork point). INVALID (borderline): the doc's "no guessing from commit messages" is about attributing ordinary commits; the response itself keeps merge-message matching. Topology (merge parents) does give a fork point without a reflog, so the claim was not false.
  - F006 (type-error counts depend on the environment, but only coverage is flagged; Design Goal 1 says same value on the same commit with the same tool versions). INVALID (borderline): the premise is tool behavior, not the doc, a parent or repo code; the fix adds a new identity dimension.
  - F007 part 3 ("Review templates emit categories from the closed vocabulary" would break arch, slice and tasks vocabularies). INVALID (borderline): the doc states a plan; its Design Goals say "code-review findings".
  - F002 (store scans every file), F003 (keystone overloaded), F004 (adapter contract shape), F005 (snapshot isolation mechanism), F008 (pipeline hook owner), F009 (440 probe dependency), F010 (cost preview source). INVALID: unspecified detail, opinion, or scope cuts (the hook is dropped, durable slice-range records are new scope).

---

## 5. squadron-155-tasks

- `project-documents/user/tasks/155-tasks.sdk-pipeline-executor.md`; tasks
- reviewed-at: `3a8d7326^` (no `reviewedSha`; see caveat 3). Review `reviews/155-review.tasks.sdk-pipeline-executor.md`, FAIL, **z-ai/glm-5**, 6 findings.
- commit `3a8d7326` "chore: lint and verify SDK pipeline executor": the task-file diff is check-offs only (268 lines, all `[ ]` to `[x]` and `status: complete`). There is no response edit.
- flaws (all INVALID):
  - F001 FAIL: "no tasks implement checkpoint triggers, state persistence, exit code, `--resume`". INVALID (unproven, misread): T14 has an explicit checkpoint-handling item ("existing checkpoint logic from slice 151 handles the rest ... only new behavior is `session.disconnect()`"), and `run.py` at `3a8d7326^` already has `--resume`, `ExecutionStatus.PAUSED` and state persistence.
  - F002: "no task verifies review actions stay subprocess-based". INVALID: T18 has the bullet "Test review actions still use subprocess dispatch path (not SDK session) ...".
  - F003: T1 stores `_compaction_config` but no task applies it on dispatch (SC3 "compact steps trigger server-side compaction"). INVALID (borderline): true that no task applies it, and the implemented `sdk_session.py` stores it and never reads it, but the Implementation Notes section names the `context_management` unknowns and says to evaluate them "early in implementation (T1/T8)" with a fallback.

## 6. squadron-197-tasks

- `project-documents/user/tasks/197-tasks.implementation-batch-pipeline-implement-plan.md`; tasks
- reviewed-at: `e87b2474^` = `4f2af384` (the review's `reviewedSha`). Review `reviews/197-review.tasks.implementation-batch-pipeline-implement-plan.md`, CONCERNS, **claude-opus-5-5** (see caveat 2), 8 findings.
- response commit: `e87b2474` "docs: address slice 197 tasks review findings" (read)
- flaws:
  - Design D12 (slice 197 design at `e87b2474^`, lines 413-418 and 398) says: a lock-time `rev-parse --git-dir` failure raises `GitEnvironmentError` and exits 2 (nothing ran); any other lock `OSError` exits 2 for both item resume and `sq run`; a report temp write or rename `OSError` ends item resume with exit 3. The tasks: Task 24 only says "held lock -> exit 2"; Task 26 only says "held -> REJECTED"; Task 28 maps every `GitEnvironmentError`/`GitStateUnknownError` to HALTED and never maps the report-write `OSError` to HALTED. A lock-time `GitEnvironmentError` would exit 3 (halted), contradicting D12. **VALID**: the tasks contradict the parent design. Needs: doc (design plus tasks). Raised by the original review (F001).
  - Task 3 requires a test that a failed `set_arch` reports `outputs["failure"] = other` from the branch action, but `set_arch` is a separate `cf-op` step that `branch: { plan: }` inserts before the branch action, and that step is not added until Task 7 (Task 7 itself says "expansion emits `cf-op(set_arch, plan)` before the branch action"). The branch action's outputs cannot carry that failure, and Task 3 precedes Task 7. **VALID**: self-contradiction and a test that cannot be written as ordered. Needs: doc alone. Raised by the original review (F002).
  - F003 (no tests listed for criteria 12 and 3, `slices-plan` item resume, the empty-diff row). INVALID: the Context Summary says every D12 row has a test, and Task 31 maps each criterion and D12 row to a test and adds missing ones.
  - F004 (Task 2 names no module), F005 (run lock may break existing `sq run` tests). INVALID: unspecified detail; the second is speculation I did not verify.

## 7. squadron-264-tasks

- `project-documents/user/tasks/264-tasks.context-forge-mcp-tool-bridge.md`; tasks
- reviewed-at: `fa69cb2f^` = `af1f3c97` (the review's `reviewedSha`). Review `reviews/264-review.tasks.context-forge-mcp-tool-bridge.md`, CONCERNS, **moonshotai/kimi-k3**, 5 findings.
- response commit: `fa69cb2f` "review: slice 264 task review CONCERNS; all findings addressed" (read)
- flaws:
  - Slice design Result mapping: "Non-text blocks are noted by type in the content, not dropped silently" (design line 138), part of SC2 "maps results per the Result mapping rules". Task 4.2 implements it, but the Task 3 fixture has only `echo`/`fail`/`sleep`/`empty`, Task 5 never produces a non-text block, and Task 7 mocks the bridge. No task tests the rule, although the zero-text-blocks rule next to it has a fixture tool and a test. **VALID** (minor, `coverage`): the tasks leave out verification of a rule SC2 names. Needs: doc (design plus tasks). Raised by the original review (F001).
  - F002 (protocol-error row's WARNING assertion implicit). INVALID (borderline): Task 5.4 says "each failure-mode test above also asserts its WARNING", which covers `test_unknown_tool_name` in 5.1.
  - F003 (PID capture needs fixture support). INVALID: Task 5.2 offers a fallback (scan for the command line) that works without it.
  - F004 (SC6 live demo deferred while the slice is complete). INVALID: the design states the same caveat.

## 8. squadron-306-tasks

- `project-documents/user/tasks/306-tasks.review-resolution-recording-that-findings-were-addressed-1.md`; tasks (file 1 of 2)
- reviewed-at: `41cb878e^` = `e8382dbb` (no `reviewedSha`; the review file was added by the response commit). Review `reviews/306-review.tasks.review-resolution-recording-that-findings-were-addressed.part-1.md`, CONCERNS, **minimax/minimax-m3**, 9 findings; its Resolution section is the author's, not the reviewer's.
- response commit: `41cb878e` "review: resolve slice 306 task-breakdown review (part 1)" (read)
- flaws:
  - Design SC (line 372-373): "A failed **or unverifiable** archive copy aborts the overwrite: the original review file is byte-identical afterward". T12 specifies both modes (copy cannot be created; read-back verification fails), but T13's tests cover only the unwritable-directory mode; no test exercises a copy that succeeds and then fails verification. **VALID** (minor, `coverage`): the tests leave out one branch the success criterion names. Needs: doc (design plus tasks). Raised by the original review (F001, as its first CONCERN).
  - F002 (T14 cf-scanning checkpoint is numbered after the T12 it gates). INVALID (borderline): the file says "do not mark T12 done until T14's outcome is known", so the work is completable by doing T14 first; the fix is a reorder.
  - F003 (T2/T4/T6 run focused subsets; full suite only at T8). INVALID: clarifying note.
  - F004 (no findings round-trip test in T11). INVALID: a new test guarding a hazard; no criterion requires it.

## 9. squadron-322-tasks

- `project-documents/user/tasks/322-tasks.calibration-to-threshold-feedback.md`; tasks
- reviewed-at: `f5c586f6^` = `9360d61c` (no `reviewedSha`). Review `reviews/322-review.tasks.calibration-to-threshold-feedback.md`, CONCERNS, **moonshotai/kimi-k2.7-code**, 4 findings.
- response commit: `f5c586f6` "review: address task-review findings for slice 322" (read)
- flaws:
  - T7 lists `classify_direction` precedence as 1 `n < floor` -> `INSUFFICIENT_EVIDENCE`, 2 unversioned -> same, 3 graduate, 4 `match_rate <= tighten_rate` -> `TIGHTEN`, 5 `HOLD`, and says case 4 is "reachable even if `n < floor`". Taken as a precedence list, case 1 returns first for every below-floor cell, so `TIGHTEN` is unreachable there. That contradicts the same task, T8's test ("a below-floor cell with a low match rate returns `TIGHTEN`") and the design (`322-slice` line 37 "tightening is not floor-gated"; Direction Bands table line 183). **VALID**: self-contradiction. Needs: doc alone. Raised by the original review (F001).
  - The Coverage Check says the malformed `judge:` block row is "exercised in T8", but T8's tests list only registered and unregistered templates. **VALID** (minor): self-contradiction between the Coverage Check and T8. Needs: doc alone. Raised by the original review (F002).
  - T13 says to "reuse 320's existing result-discovery surface" to find unsampled judge results, falling back to "store-recorded samples only". At `9360d61c`, `metrology/capture.py` has only `resolve_target` (a glob scoped to one `{index}`), and no module enumerates judge results across the project. Unsampled results are by definition absent from the store, so the fallback cannot meet T13's own success criterion (3 unsampled results at `rate=1.0` yield 3 `OfferTarget`s). **VALID**: the task cannot be completed as written, and it names code that does not exist. Needs: code. Raised by the original review (F003, as a note).

## 10. squadron-363-tasks

- `project-documents/user/tasks/363-tasks.concept-generation.md`; tasks
- reviewed-at: `e4e1f8c1^` = `3ae461ce` (the review's `reviewedSha`). Review `reviews/363-review.tasks.concept-generation.md`, CONCERNS, **qwen/qwen3.8-2.4t-a95b**, 8 findings.
- response commit: `e4e1f8c1` "review: address CONCERNS in slice 363 task breakdown" (read)
- All four valid flaws are `coverage` omissions against the slice design's Success Criteria (design at `3ae461ce:...363-slice.concept-generation.md`, lines 346-374). The design's own walkthrough steps (3, 5, 6) are as thin as the tasks, so a reviewer who reads only the tasks needs the design's SC list to see them.
- flaws:
  - SC4: dropped topics (why-now, audience evolution, methodology preference) "appear nowhere in the document, neither as content nor as gap markers". Task 4.1 authors the rule and 5.1 stops extra questions, but no task inspects the generated `000-concept.squadron.md` for them. **VALID** (`coverage`). Needs: doc (design plus tasks). Raised (F001).
  - SC7: with the guide "absent, unreadable, or missing the expected section title" the flow stops loudly (and names the setup step when the guide tree is absent). Task 6.1 authors all three; Task 8.3 exercises only the renamed section. **VALID** (`coverage`). Needs: doc. Raised (F002).
  - SC8: "mechanical refillability for augment". Task 6.2 authors it; Task 8.4 checks default stop, the dated subheading and byte identity of populated sections, not that an empty or `[GAP: ...]` section is refilled and real content left alone. **VALID** (`coverage`). Needs: doc. Raised (F003, first half).
  - SC10: "every `[INFERRED]` sentence satisfies the checkable rule". Task 8.1 checks only that the provenance inferred-claims line exists; no task audits the sentences. **VALID** (`coverage`). Needs: doc. Raised (F004).
  - F003 second half (8.4 ambiguous about the re-run interview and whether augment mutates the real document), F005 (8.3 "point the check at it" has no mechanism), F006 (8.6 scope check precedes close-out edits), F007 (hygiene checks not traceable to a criterion). INVALID: unspecified detail filled in, or labeling; the 8.6 check says "shows only" and a later DEVLOG does not violate it.

## 11. squadron-381-tasks

- `project-documents/user/tasks/381-tasks.code-host-adapter-and-pr-target-resolution-2.md`; tasks (file 2 of 2)
- reviewed-at: `b9c1b4bf^` = `ea0fca58` (the review's `reviewedSha`). Review `reviews/381-review.tasks.code-host-adapter-and-pr-target-resolution.part-2.md`, CONCERNS, **z-ai/glm-5.3-flash**, 8 findings.
- response commit: `b9c1b4bf` "review: address glm-5.3-flash slice 381 task review part 2" (read)
- flaws (all INVALID):
  - F008: the design's seventh functional criterion says `run_all_checks` makes no subprocess call "(existing test extended)" and its Testing section puts `test_errors_observable.py` under `tests/codehost/`, while tasks write the test new and place it in `tests/cli/`. I confirmed no test with `subprocess` exists in `tests/cli/test_doctor_checks.py` at `ea0fca58`, so the design line is false. INVALID (borderline): the false line sits in the parent design, outside the reviewed document, and file 1 of the tasks already records the correction in its Corrections table; the reviewed task file carries no flaw.
  - F007 (no named seam for CLI-level test doubles), F006 (fetch path has no enterprise-hostname leg). INVALID: the first is unspecified detail; the second is a requirement the review itself calls vacuous (the fetch names the remote, never the host); the response records why.
  - F005 (F.5 dense), F001-F004 (pass or notes). INVALID.

## 12. squadron-385-tasks

- `project-documents/user/tasks/385-tasks.create-a-pr-with-a-good-message.md`; tasks
- reviewed-at: `5861257d^` = `da018715` (the review's `reviewedSha`). Review `reviews/385-review.tasks.create-a-pr-with-a-good-message.md`, PASS, **moonshotai/kimi-k3**, 6 findings.
- response commit: `5861257d` "review: address 385 tasks review, PASS" (read)
- flaws:
  - Task 1's header says `parse_slice_branch` is "needed by Task 9". The only task that calls it is Task 7.1 ("`parse_slice_branch(head)` from Task 1"); Task 9 (`assemble_facts`) takes already-gathered inputs and never references it. **VALID** (minor): a cross-reference that contradicts the rest of the file. Needs: doc alone. Raised by the original review (F004).
  - F005 (commit checkpoints implicit). INVALID: process opinion; the project rule covers it.

## 13. squadron-913-tasks

- `project-documents/user/tasks/913-tasks.ruff-rule-set-adoption-b-async-ble.md`; tasks
- reviewed-at: `352789fa^` = `71745244` (the review's `reviewedSha`). Review `reviews/913-review.tasks.ruff-rule-set-adoption-b-async-ble.md`, CONCERNS, **minimax/minimax-m3**, 13 findings.
- response commit: `352789fa` "review: add slice 913 task review and address F007/F008/F011" (read)
- flaws (all INVALID):
  - F007 (no per-site test review for Part C narrowings). INVALID: the design's migration plan requires the "what now escapes, and where does it land?" answer per narrowing and the Part C introduction in the tasks already says "For every narrowing, answer explicitly ..."; the response only turns it into a recorded audit in 3.6.
  - F008 (Task 3.2 scope-guard trigger judgmental). INVALID: unspecified detail filled in.
  - F011 (Task 1.3 could be committed early). INVALID: the tasks already say "Commit Part A alone ... select change and the fixes together" at 1.5; the response adds a "do not commit here" reminder.
  - F009, F010, F012, F013. INVALID: no action or opinion.

## 14. squadron-917-tasks

- `project-documents/user/tasks/917-tasks.review-artifact-integrity-2.md`; tasks (file 2 of 2)
- reviewed-at: `a73698ab^` = `251217ba` (the review's `reviewedSha`). Review `reviews/917-review.tasks.review-artifact-integrity.part-2.md`, CONCERNS, **z-ai/glm-5.3**, 11 findings.
- response commit: `a73698ab` "docs: address slice 917 task review findings" (read)
- flaws:
  - Task 5.2 specifies `_count_lines(root, resolved) -> int | None` that "return[s] `None` with a WARNING" for the outside-root, directory, over-cap and `OSError` cases, and Task 5.3 relies on it ("WARNING already logged there"). The design (917 slice, line 134) and file 1's standing constraint (line 81) require every `None` on `location_verified` to be "accompanied by a WARNING naming the finding and the reason". `_count_lines` receives no finding identifier, so it cannot name one. **VALID**: the task contradicts the standing constraint and the design. Needs: doc (design, file 1, file 2). Raised by the original review (F001).
  - Task 4.6 says call `save_provider_failure` "using `slice_info` when present, else the step-name/index", but Task 4.2's writer takes `slice_info` as a plain parameter (no `| None`) and hardcodes the body title `# Review: {review_type} — slice {index}`; the slice-less branch has no signature or rendering, and Task 4.7 tests only the `slice_info`-present shape. **VALID**: tasks 4.2 and 4.6 do not compose; the branch cannot be implemented as written under the zero-error pyright gate. Needs: doc alone. (At `251217ba`, `format_review_markdown` already accepts `slice_info: SliceInfo | None = None`, which is the resolution the response picks.) Raised by the original review (F002).
  - F003 (the #92 digest case covered only compositionally), F004 (suppression reason not threaded), F005 (preamble understates Part 3 consumers), F006 (anchors unverifiable). INVALID: the first three are extra tests, a design-scoped limitation and an incomplete rationale sentence; the last is a reviewer-environment note. F005 is borderline: the sentence says Parts 5 and 6 consume the fields and does not deny Part 4.

## 15. squadron-922-tasks

- `project-documents/user/tasks/922-tasks.small-fixes-batch-2-2.md`; tasks (file 2 of 2)
- reviewed-at: `445cde2c^` = `91810414` (the review's `reviewedSha`). Review `reviews/922-review.tasks.small-fixes-batch-2.part-2.md`, PASS, **deepseek/deepseek-v4-pro**, 3 notes.
- response commit: `445cde2c` "review: address slice 922 task review findings" (read)
- flaws (all INVALID): F001 (F5 test location unspecified: unspecified detail), F002 (G2 does not list the 11 criteria: style), F003 (F4 manual check before F5 test: ordering preference; the reviewer says it is "not broken"). The response diff adds only these three edits.

---

## Notes for building the benchmark from these

- 19 valid flaws, 15 document-only. Of those, 13 are strong (contradictions between a document and itself, its parent, or a sibling document) and 6 are `coverage` omissions that tasks inherited from thin design walkthroughs (264, 306, 363). 4 need code at the reviewed commit: 380 rules fallback, 400 category example and `None` versus `"uncategorized"`, 322 missing discovery surface.
- Every valid flaw was raised by the original reviewer, across 11 distinct models; that makes this batch a control set (a model that finds them is matching a reviewer that already found them), not a set of misses. Original reviews that found them include all of: fable-5 (1), minimax-m3 (3 cases), opus-5-5 (2 cases), kimi-k3 (2), kimi-k2.7-code (1), qwen (1), glm-5.3 (1).
- Tasks cases need the parent design at the same commit as input: 197 (design D12), 264 (Result mapping, SC2), 306 (SC at line 372), 322 (Direction Bands), 363 (SC4, 7, 8, 10), 917 (design line 134, file 1 line 81). 320's flaw needs `140-slices.pipeline-foundation.md` and `001-initiative-plan.squadron.md`.
- The strongest single cases: 197 (both), 322 (all three), 917 (both), 400 (both, but code), 380 (code), 320 (sibling documents).
- Reviewer false positives worth keeping as negative controls: 155 F001 and F002 (the task file already has the item), 320 F011 (premise inverted), 380 F004 (metrology key claim unsupported), 913 F007 and F011 (the requirement is already in the tasks).
- 380 and 197 have model-recording mismatches with `batch2.json` (caveats 1 and 2); use the values here.
