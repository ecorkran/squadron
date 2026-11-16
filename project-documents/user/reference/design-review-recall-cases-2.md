---
docType: reference
project: squadron
dateCreated: 20261116
dateUpdated: 20261116
status: draft
---

# Design and task review recall: candidate cases, batch 1 (mining pass, 2026-11-16)

Read-only pass over `/Users/manta/source/repos/manta/squadron`. 13 candidates examined (all of `batch1.json`; the stop rule did not trigger, because 3 of the first 8 produced a valid case). Nothing was checked out, no model was called. All 13 `reviewedSha` values exist and contain the document (`git cat-file -e`).

Validity rule applied (same as `design-review-recall-cases.md`): a flaw counts only if, at the reviewed commit, the document contradicted itself, its parent, or code in the repo at that commit, left out something its own success criteria required, or held a task that could not be completed as written, and a later commit proves it. It does not count if the correction follows a later decision or scope change, adds a capability or gate, fills in an unspecified detail, or records facts that only existed after other work was built. Borderline items are marked INVALID and tagged `borderline`.

Labels on evidence: **read** = I read the diff and the reviewed text or code named; **inferred** = judged without checking the code.

## Totals

- Candidates examined: 13
- Cases with at least one valid flaw: 8 (129, 174-tasks, 362, 401, 403, 920, 927, 928)
- Valid flaws: 9 (4 need only the document, 5 need code at the reviewed commit; 1 of the 5 is an uncompletable task, 920)
- Invalid or unproven: 47 (12 tagged borderline)
- No valid flaw: 174-design, 178, 366, 402, 945. In each, the correcting commit is a review response, scope trim or PM decision.

## Caveats that affect how to use these

1. **Several correcting commits are mixed.** 129 (`aa8fb7a7`) is mostly a packaging decision with one real fix inside. 366 (`bbd4182d`) folds in the whole probe feature. 403 (`f0c537df`) and 928 (`4849ae2c`) span 6 to 7 days and absorb implementation findings. Only the lines named under each case count.
2. **The proof for 362 and 927 sits in an intermediate commit.** `da970179` (362) and `c88e2587` (927) are review-response commits between the reviewed and the listed correcting commit. The diff `reviewedSha..correcting` includes them. The `-` lines are still the reviewed text.
3. **403 has an odd history.** `git log 90725f6d..f0c537df -- <doc>` lists `c61cccb9` "add slice 403 design", which means history was rewritten or collapsed. The `-` lines of the diff are still the text at `90725f6d`.
4. **Several valid flaws were already found by the original reviewer** (129, 362, 401, 927 walkthrough, 928, 403 partly). They are controls: a model that finds them is doing what the original did. Not found by the original review: 174-tasks, 920, 927 D6. Marked per case.

---

## 1. squadron-129-design

- repo squadron; `project-documents/user/slices/129-slice.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md`; kind design
- reviewed-at: `c5ebaf6f`. Review `reviews/129-review.slice.codex-provider-...md`, deepseek/deepseek-v4.1-flash.
- correcting commit: `aa8fb7a7` "docs: revise slice 129 design and docs for the core codex dependency" (read; doc diff only)
- flaws:
  - The design names the command `sq model list` (summary, D9, Interfaces, Success Criteria, Walkthrough). The CLI registers the group as `models` (`cli/app.py:55` `add_typer(models_app, name="models")` at `c5ebaf6f`), and the README uses `sq models list`. **VALID** (minor): contradicts code. Needs: code. The original review raised it (F "CLI command name ... does not match the shipped surface").
  - Optional extra changed to a core dependency, D9 `ExtraRequirement` removed, `resolve_codex_runtime()` and PATH fallback removed. INVALID: packaging decision made after implementation.
  - `pip install 'squadron-ai[codex]'` lands outside a `uv tool` environment, while the README's primary install is `uv tool install squadron-ai` (README line 41 at `c5ebaf6f`). INVALID (borderline): the design says "or the equivalent", and the walkthrough uses a fresh venv; the decisive fact (uv upgrade drops the extra) was verified after implementation (uv 0.11.2).
  - `sq auth logout` spawns the runtime but no timeout or failure row covers it; correction adds a logout row and widens `account_timeout_s`. INVALID (borderline): an added failure mode. The original review raised it.
  - `login(timeout: float)` renamed `timeout_s` because ruff ASYNC109 rejects it. INVALID: implementation fact.

## 2. squadron-174-design

- `project-documents/user/slices/174-slice.run-liveness-stall-bounds-pruning-and-readable-listings.md`; design
- reviewed-at: `3a628691` (round-2 design). Review round 2 is `aeb87e30`; correction `be0a499b` is 26 minutes later.
- correcting commits: `be0a499b` (read), `86307d74` (read; adds only a spike result)
- flaws (all INVALID):
  - Pre-174 `running` runs with no owner (`UNOWNED`) could never be pruned; correction adds an `unowned` category and `--status unowned`. INVALID (borderline): a new selection capability filling a gap. The reviewed text protects `UNOWNED` runs consistently; the 34 of 188 leftover runs motivated the addition.
  - `process_alive` for a non-positive PID: `os.kill(0, 0)` signals the process group and reads as alive; correction returns `None` (unknown). INVALID (borderline): an edge case against OS semantics, not against the document or repo code.
  - `client.interrupt()` has no timeout in D7. INVALID: an added failure mode.
  - Spike result for `interrupt()` (`86307d74`). INVALID: a fact that only existed after Task 2 ran.

## 3. squadron-174-tasks

- `project-documents/user/tasks/174-tasks.run-liveness-stall-bounds-pruning-and-readable-listings.md`; tasks
- reviewed-at: `44765b28`. Review `174-review.tasks.run-liveness-...md`, PASS, deepseek-v4.1-flash (6 findings: 1 pass-level traceability, notes). Correction `d4229f1b` is 4 minutes later.
- correcting commits: `d4229f1b` (read); `86307d74` (read; only checkbox state, no flaw)
- flaws:
  - Task 22a asserts wall-clock `MAX_LISTING_S = 1.0` for `list_run_summaries`, while the parent design says "The I/O-bounds test enforces the counts, and walkthrough step 8 measures wall-clock time. There is still no assertion on time in tests" (design Special Considerations at `44765b28`). The correction deletes Task 22a and routes the timing to the hand-run walkthrough (Task 42). **VALID**: the task file contradicts its parent design. Needs: document alone (design plus tasks). Not found by the original review (it passed the file and praised criterion traceability).
  - Two tasks say "stop and ask the Project Manager" (D7 fallback, D5 lock). INVALID (borderline): the project rule that PM-gated steps are invalid is a repo policy, not a contradiction in the documents; the steps were completable with a PM present.
  - `with an empty HOME` and the "3 schema-drift failures" note removed. INVALID: wording.

## 4. squadron-178-design

- `project-documents/user/slices/178-slice.artifact-usage-stamping.md`; design
- reviewed-at: `280ebf99`. Review `178-review.slice.artifact-usage-stamping.md`, claude-sonnet-5-5.
- correcting commits: `1c2682e6` is a task-round commit; the design edit is `ea34d9ee` "trim slice 178 design after review" (read). Both fall inside `280ebf99..1c2682e6`.
- flaws (all INVALID):
  - Cut `sq stats artifacts`, split-task-breakdown handling, atomic `update_frontmatter`; moved the usage model from `pipeline/` to `review/`. INVALID: scope trim and structure choice ("Cut ... scope totals to uninterrupted runs").
  - `PostActionContext` field list omits `iteration` (the code has it, `events/contexts.py` at `280ebf99`), which D2 uses. INVALID (borderline): an incomplete list, not a contradiction of behavior.
  - Totals can overcount on re-dispatch or resume. INVALID: a risk statement added; the reviewed text did not claim exactness for those cases.
  - Process killed mid-write row and `#233` deferral. INVALID: a consequence of the cut.

## 5. squadron-362-design

- `project-documents/user/slices/362-slice.comprehension-analysis-and-graph-extraction.md`; design
- reviewed-at: `f434a1a6` (the commit that added the design). Review `362-review.slice.comprehension-analysis-...md`, deepseek-v4-flash-0731, 7 findings. Response commit `da970179`.
- correcting commit: `7b9e8b96` (read). The text that proves the flaw is in `da970179`, which says in terms: "This resolves a contradiction present in the first draft of this design".
- flaws:
  - Dependency section: "Function- and class-level edge endpoints are resolved to their owning file's layer rather than dropped", while Success Criterion 9 says "no function- or class-level node is read". Resolving an endpoint to a layer reads the node. The fix derives the owning file from the node id string, which makes both hold. **VALID**: self-contradiction. Needs: document alone. Found by the original review (F001 "Function/class edge-endpoint resolution conflicts with the architecture's 'not read' rule"), so a control.
  - No failure path for an unresolvable edge endpoint (added `[GAP: ...]`, drift report, criterion 11, walkthrough 5b). INVALID: an added failure mode. The review raised it (F002).
  - Design writes seven sections while the architecture names four (line 163); the correction adds a "Section count vs the architecture" table. INVALID (borderline): the architecture's own text sanctions the coverage slot and 361 shipped reading order; the fix adds justification, not content.
  - Correction 3 (`fingerprints.json` churn note, verified against upstream plugin source). INVALID: scope addition from outside research.

## 6. squadron-366-design

- `project-documents/user/slices/366-slice.dispatcher-routing-and-documentation.md`; design
- reviewed-at: `6804e05e`. Review `366-review.slice.dispatcher-routing-and-documentation.md`, claude-haiku-5-5. Correction `bbd4182d` is a task-revision commit.
- correcting commits: `bbd4182d` (read); the design diff also includes `4b3afa91` "fold capability probe into slice 366 design" and `25730005`.
- flaws (all INVALID):
  - Probe (D6 to D11, `sq probe --json`) folded into the slice. INVALID: PM-approved scope change.
  - Design says "365's design assigns [README text for `/sq:overview`] to 366". I read 365's design at `6804e05e` (lines 360 and 363: "slice 366 owns the README pass for both capabilities"). INVALID: the claim was true; no contradiction. The amendment only names #247 in 365.
  - `resolve_root(local=True)` reads process cwd; the CLI reference is `docs/COMMANDS.md`, not the README. INVALID: amendments to the new probe text, which did not exist at the reviewed commit.

## 7. squadron-401-tasks

- `project-documents/user/tasks/401-tasks.complexity-duplication-and-coverage.md`; tasks
- reviewed-at: `ac3afee7`. Review `401-review.tasks.complexity-duplication-and-coverage.md`, claude-sonnet-5-5, 5 findings. Correction `89a32f65` is 11 minutes later.
- correcting commit: `89a32f65` (read)
- flaws:
  - Design Success Criterion 10 says that when `DUPLICATION_MAX_TOKENS` is passed, `duplicated_lines` is `tool_failed` "and its other metrics are unchanged". The task at the reviewed commit (line 138) asserts only `tool_failed` plus the WARNING. The correction adds the "other metrics still present" assertion. **VALID** (minor): the task leaves out something its parent's success criterion requires. Needs: document alone (design plus tasks). Found by the original review (F004), so a control.
  - Task 28 has no `Success:` line (F005); Tasks 29 and 30 merged. INVALID (borderline): a format convention, no content gap.

## 8. squadron-402-tasks

- `project-documents/user/tasks/402-tasks.code-review-normalization-and-ingest.md`; tasks
- reviewed-at: `a8639308`. Review `402-review.tasks.code-review-normalization-and-ingest.md`, claude-sonnet-5-5 (round 1 PASS). Correction `fa2fac55` is 3 minutes later.
- correcting commit: `fa2fac55` (read)
- flaws (all INVALID):
  - Task 5 adds "definitions contain no backticked tokens other than the category value" (Task 6 compares every backticked token). INVALID (borderline): I read the audit skill's vocabulary table at `a8639308`; the definitions it supplies contain no backticks, so the reviewed task was completable. The guard is a hazard note.
  - Walkthrough says the arch review "is `not-code-review`" while the result dataclass counts it in `skipped_not_code`. INVALID (borderline): a label-versus-counter wording mismatch, the design itself uses the label for summary lines.

## 9. squadron-403-design

- `project-documents/user/slices/403-slice.slice-ranges-and-rollup-reports.md`; design
- reviewed-at: `90725f6d` (see caveat 3). Review `403-review.slice.slice-ranges-and-rollup-reports.md`, claude-sonnet-5-5, 8 findings.
- correcting commit: `f0c537df` "docs: align 403 design git_utils wording with task breakdown" (read; the diff covers the whole reviewed-to-final span)
- flaws:
  - D1 requires every landing of a slice (a slice can land twice; slices 172, 305 and 940 each have two merges on first-parent history), but D2 resolves them by reusing `_search_merge_commit` with a `first_parent` flag. At `90725f6d` that helper runs `git log --merges ... -1` and returns only the newest merge, as `str | None` (`review/git_utils.py:221-243`). It cannot return multiple landings. The correction stops reusing it and has the resolver run `git log --first-parent` itself, sharing only the pattern and parse functions. **VALID**: contradicts code. Needs: code (read the helper at `90725f6d`). Not found by the original review.
  - Failure table treats a `None` from the merge search or reflog as "this path can't answer, try the next"; the correction returns `GIT_ERROR` and never falls through, and raises the log level to WARNING. INVALID (borderline): partly a consequence of the same helper; the reviewed text did say a failure is never an empty range, so the distinction is a strengthening. The review flagged it (F "Git failures ... at INFO").
  - 401 changed from "not a prerequisite" to "a prerequisite". INVALID: sequencing decision.
  - Concurrent `slice_ranges` writes now detected and merged. INVALID: added failure handling (original review F raised it).
  - `limits_changed`/`exclusions_changed` merged into `settings_changed`; `report history` stops showing audits and reviews; `ensure_snapshot` moved to `slice_report.py`; review table columns. INVALID: refinements and scope cuts.

## 10. squadron-920-tasks

- `project-documents/user/tasks/920-tasks.claude-agent-sdk-upgrade-and-rate-limit-parser-shim-retirement.md`; tasks
- reviewed-at: `b5939ca4` (the commit that added the task breakdown). Review `920-review.tasks.claude-agent-sdk-upgrade-and-rate-limit-parser-shim-retirement.md`, z-ai/glm-5.2 (6 findings; none is this one).
- correcting commit: `20e08882` "docs: resolve slice 920 task 13's uncompletable checklist items" (read; the implementer's BLOCKED text is the proof). The task is numbered 15 at the reviewed commit and 13 after renumbering.
- flaws:
  - Task 15 (live `sq metrology audit run -v`; "Confirm: the audit runs to completion") could not be completed as written. At `b5939ca4`, `metrology/audit.py:160` defines `_AUDIT_ALLOWED_TOOLS` with Claude-native names (`Read`, `Glob`, `Grep`, `Bash`, `Task`, `TodoWrite`, `Write`, `Edit`); `providers/sdk/provider.py:66` runs `translate_tool_names` on `allowed_tools`; `providers/sdk/tool_names.py` raises `ProviderError` for any name not in the five canonical keys. The commit that added the translator (`4a6db5c0`) is an ancestor of `b5939ca4`. So the audit fails before any dispatch. Slice closed with the item recorded as blocked and filed as #107. **VALID**: held a task that could not be completed as written. Needs: code (the audit constant, the translator, and `git merge-base` for ordering). Not found by the original review. Note the walkthrough step in the parent design (step 4) has the same dependency.
  - Rest of the diff is implementation check-offs and renumbering. INVALID.

## 11. squadron-927-design

- `project-documents/user/slices/927-slice.review-artifacts-state-what-happened-diff-truncation-and-the-model-that-answered.md`; design
- reviewed-at: `4748b63c` (the commit that added the design). Review `927-review.slice.review-artifacts-...md`, claude-opus-5-5, 8 findings. Response commit `c88e2587`.
- correcting commit: `04061e85` "drop slice 927 D6 render change; the cap never meets unparsed findings" (read; diff covers `c88e2587` too)
- flaws:
  - D6 and Success Criterion 7 assume a stated PASS with `fallback_used=True` (verdict read, findings not parsed) can reach the PASS-to-CONCERNS cap, and prescribe rendering the "Findings Not Parsed" notice whenever `fallback_used` is set, in the artifact and the terminal. In `review/parsers.py` at `4748b63c`, `fallback_used` is set only in two branches: a derived verdict (computed from findings that did parse) and the mismatch branch (verdict CONCERNS or FAIL with no findings, never PASS). The premise is false, and the prescribed change would stamp "Findings Not Parsed" on every derived-verdict review. **VALID**: contradicts code. Needs: code (`parsers.py` lines 963-1030). Not found by the original review.
  - Walkthrough step 6 says "one run per configured profile" but the command pins `--model sonnet`, which exercises one profile only. The correction uses each profile's default model and `--profile <profile>`. **VALID** (minor): self-contradiction. Needs: document alone. Found by the original review (F "Walkthrough step 6 ... hardcodes `--model sonnet`"), so a control.
  - Overview says a PASS means the model "saw the whole diff or read files with its tools", while D4 exempts on any successful tool call, including a `Glob`. INVALID (borderline): wording of the same rule the review treated as a design choice (F001).
  - Empty diff records `DiffInjection(0, 0)` and writes `diffTruncated: false`. INVALID: an unspecified detail filled in.
  - "Commit each part separately". INVALID: process.

## 12. squadron-928-design

- `project-documents/user/slices/928-slice.codex-parity-for-skill-packs-and-provider-access.md`; design
- reviewed-at: `16194f3e`. Review `928-review.slice.codex-parity-for-skill-packs-and-provider-access.md`, z-ai/glm-5.3-flash, 11 findings.
- correcting commit: `4849ae2c` "docs: amend slice 928 design for the Codex rules writer and probe results" (read; diff covers `5f226f39`)
- flaws:
  - Walkthrough step 7 runs bare `sq doctor` and expects "all four rows present" and `demo (codex): WARN`. `cli/commands/doctor.py:64` at `16194f3e` skips WARN rows unless `-v`. The correction adds `-v` and notes "bare `sq doctor` hides WARN rows (F003)". **VALID**: contradicts code. Needs: code. Found by the original review (F "Walkthrough step 7 expects WARN rows on bare `sq doctor`, repeating the exact error slice 925 already corrected"), so a control.
  - Out of scope "writing the rule file for the user" reversed (D9 rules writer, `~/.codex/rules/squadron.rules`). INVALID: decision made during implementation.
  - Probe results table, README sentence no longer existing, hint remedy. INVALID: facts that only existed after the probe and implementation.
  - Walkthrough output lines filled in with verified results and disposable-home variables. INVALID: later facts and unspecified detail.

## 13. squadron-945-design

- `project-documents/user/slices/945-slice.dispatch-outcomes-match-what-happened-codex-tool-contract-and-silent-success.md`; design
- reviewed-at: `03f77032`. Review `945-review.slice.dispatch-outcomes-...md`, claude-sonnet-5-5. Correction `98fe4397` is a task-revision commit; the design edit is `81931240` "revise slice 945 design per review response".
- correcting commits: `98fe4397`, `81931240` (read via the span diff)
- flaws (all INVALID):
  - `tool_errors: list[str]` simplified to `first_tool_error`; dropped the Codex `sandbox` stamp. INVALID: simplification and scope.
  - Executor read `UNFINISHED_TASKS` from the `failure` output; replaced by an `ActionResult.awaits_human` flag. INVALID: a design refinement, not a contradiction.
  - `dispatch_requires_writes` moved to `dispatch_rules.py`. INVALID: file-size structure.
  - "Open item for the PM" replaced by a PM decision (unchecked items pause the run). INVALID: PM decision.
  - SDK `ToolResultBlock` behavior verified against 0.2.162. INVALID: a fact added after checking; the reviewed text already stated the behavior.
  - CHANGELOG naming covered providers. INVALID: wording.

---

## Notes for building the benchmark from these

- 9 valid flaws is a small set. 5 need code at the reviewed commit; a reviewer without tools can reach at most the 4 document-only ones (174-tasks Task 22a, 362 id-versus-not-read, 401 Task criterion 10, 927 walkthrough step 6).
- The four whose original review did not find them are the most useful as misses: 174-tasks (doc only), 403 (code), 920 (code), 927 D6 (code).
- 174-tasks needs the parent design at the same commit as input; 401 needs its parent design too.
- 920 is an uncompletable-task case whose proof needs the SDK tool-name translator, which a document-only reviewer cannot see.
