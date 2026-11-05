---
docType: review
layer: project
reviewType: tasks
slice: effort-audit-across-dispatch-paths
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/tasks/420-tasks.effort-audit-across-dispatch-paths.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261105
dateUpdated: 20261105
reviewedSha: 3f945e25a3686d9d714bd05f4f7f97b74cb82039
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 34
effort: xhigh
turns: 35
promptTokens: 1680089
cachedTokens: 1496478
cacheWriteTokens: 183583
completionTokens: 78448
durationSeconds: 446.3
costUsd: 0.323966
costBasis: provider
runId: run-20261105-p5-03049c49
squadronVersion: 0.24.22
findings:
  - id: F001
    severity: fail
    category: correctness
    summary: "Task 21 records `None` for an absent `tool_use`, which the alias readers treat as allowed"
    location: "project-documents/user/tasks/420-tasks.effort-audit-across-dispatch-paths.md:183"
  - id: F002
    severity: concern
    category: completeness
    summary: "Task 4 cannot stamp the failure paths as written"
    location: "src/squadron/pipeline/actions/dispatch.py:671"
  - id: F003
    severity: concern
    category: correctness
    summary: "Task 2's \"the one reader\" sits beside an existing reader that silently returns `None`"
    location: "src/squadron/pipeline/usage_capture.py:66"
  - id: F004
    severity: concern
    category: scope
    summary: "The success criterion names three identity fields; D6 and Tasks 21–23 use five"
    location: "project-documents/user/slices/420-slice.effort-audit-across-dispatch-paths.md:177"
  - id: F005
    severity: concern
    category: coverage
    summary: "Task 21's success condition has no test"
    location: "project-documents/user/tasks/420-tasks.effort-audit-across-dispatch-paths.md:184"
  - id: F006
    severity: concern
    category: proportionality
    summary: "27 tasks and 12 commits for a slice the design rates 2/5"
    location: "project-documents/user/tasks/420-tasks.effort-audit-across-dispatch-paths.md:212"
  - id: F007
    severity: concern
    category: proportionality
    summary: "Task 22 says \"if it would exceed ~300 lines,\" but `report.py` is already 311"
    location: "src/squadron/replay/report.py"
  - id: F008
    severity: note
    category: coverage
    summary: "Task 25's path-coverage claims are partly wrong, and it misses existing tests"
    location: "project-documents/user/tasks/420-tasks.effort-audit-across-dispatch-paths.md:214"
  - id: F009
    severity: note
    category: verification
    summary: "Walkthrough step 2 claims coverage of paths 1–12 with an incomplete file list"
    location: "project-documents/user/slices/420-slice.effort-audit-across-dispatch-paths.md:203"
  - id: F010
    severity: note
    category: completeness
    summary: "No load test, and the rule that would require one is not addressed"
    location: "project-documents/user/slices/420-slice.effort-audit-across-dispatch-paths.md"
  - id: F011
    severity: note
    category: process
    summary: "Task 1 does not address the working tree's pre-existing state"
    location: "project-documents/user/tasks/420-tasks.effort-audit-across-dispatch-paths.md:41"
  - id: F012
    severity: note
    category: correctness
    summary: "Task 24's enumeration must match `ast.Call`, not text"
    location: "src/squadron/core/models.py:59"
  - id: F013
    severity: pass
    category: coverage
    summary: "Enumeration list matches the code"
    location: "src/squadron/pipeline/actions/dispatch.py:249"
  - id: F014
    severity: pass
    category: coverage
    summary: "Every functional criterion maps to a task, and sequencing is sound"
    location: "project-documents/user/tasks/420-tasks.effort-audit-across-dispatch-paths.md:62"
---

# Review: tasks — slice 420

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] Task 21 records `None` for an absent `tool_use`, which the alias readers treat as allowed

Task 21 says `config_ref` fills `tool_use` and `max_output_tokens` "from the alias entry" and sets `None` "where the alias schema allows it." Absence of `tool_use` means allow: `src/squadron/models/aliases.py:41–43` documents it, and the single reader `model_allows_tools` returns `alias.get("tool_use", True)` (aliases.py:277–291). Read literally, an alias with no `tool_use` key records `None`, while an alias with `tool_use = true` records `True`. Both send the same request, so they land in different rows. That contradicts D6's rule that identity is what went on the wire (slice design:142) and the success criterion at slice design:177. `max_output_tokens` is fine, since `None` means no budget is sent (aliases.py:294–306).

Also, `replay_common.py:50` reads `entry["model"]` directly, which bypasses the alias readers.

Fix before implementing: have `config_ref` call `model_allows_tools` and `model_max_output_tokens` rather than reading the raw entry. The design also needs to say how old records (`None` by default) relate to the new canonical value, because `None` currently means "not recorded."

### [CONCERN] Task 4 cannot stamp the failure paths as written

- The `except Exception` branch at dispatch.py:467 is in `execute()`, outside `_dispatch`, where the resolved effort lives. Task 4 says to stamp there "only when resolution already ran" but does not say how the branch learns that or what value to use.
- `_provider_failure` (dispatch.py:476) is the one failure constructor. It has four call sites (438, 671, 691, 976), and none is named in Task 4. It takes no effort parameter.
- The `set_model` failure (668–671) comes after `resolve_full` (660) but before `effort_for_session` (673). No effort value exists yet on that path, which Task 4's "same value passed to the usage capture" does not cover.

Fix: compute `effort_sent` before `set_model` (the session is already open), pass it into `_provider_failure`, and state the mechanism for the generic `except` branch as an explicit choice.

### [CONCERN] Task 2's "the one reader" sits beside an existing reader that silently returns `None`

`read_effort_sent` returns `value if isinstance(value, Effort) else None` (usage_capture.py:69). A JSON-round-tripped `"high"` is a `str`, so it reads as `None`. This is the silent failure D5 rejects. Task 12 calls `read_effort_sent` for the judge. Task 2 does not say to replace or delegate it, so two readers with different strictness would exist.

The existing string parser `_parse_effort` (`src/squadron/models/aliases.py:123`) returns `None` for an unrecognized value, and its caller logs and skips it. Reusing it would reproduce the silent `None` that Task 2 forbids.

Fix: make `action_effort_sent` the only reader, route or remove `read_effort_sent`, point Task 12 at the single reader, and use a strict parser.

### [CONCERN] The success criterion names three identity fields; D6 and Tasks 21–23 use five

The criterion reads "same model, profile and effort fall into one report row." D6 (slice design:142–147) adds `tool_use` and `max_output_tokens`. Under D6, two replays with the same model, profile and effort but different `tool_use` become two rows, which the criterion as written does not allow. D6 says it "narrows" the architecture to what the criterion requires, but the tuple is wider than the criterion.

The task breakdown implements D6, so the criterion and the tasks disagree. The PM should decide whether the criterion or D6 is right, and the other document should be updated to match.

### [CONCERN] Task 21's success condition has no test

Task 21's success line says "`config_ref` output carries both fields." Task 23 tests grouping on hand-built records and old-record loading. No listed test calls `config_ref`, so a regression that drops the fields would pass the whole suite.

Fix: add a Task 23 bullet that calls `config_ref` for an alias with `tool_use = false` and a token budget, and for an alias with neither. This would also catch the FAIL above.

### [CONCERN] 27 tasks and 12 commits for a slice the design rates 2/5

Twelve of 27 tasks are test-only. Specific merges:
- Task 25 is a mapping step in the same new file as Task 24, with the same commit. It duplicates Task 24's classification table, which already names the proving test. Fold it into Task 24, and have the test check that each named test exists. The current "add a missing test" wording is open-ended.
- Tasks 6 and 8 each add one-line stamps to one file. Merge 6–9 into one stamp task with one commit, or keep them split, but choose one.
- Task 1 is a checkout step. Fold it into the Context Summary.

Keep the per-path test tasks, since each maps to a success criterion.

### [CONCERN] Task 22 says "if it would exceed ~300 lines," but `report.py` is already 311

The conditional in Task 22 (line 191) is already true before any change. Instruct the sibling-module split now, not as a fallback.

### [NOTE] Task 25's path-coverage claims are partly wrong, and it misses existing tests

Task 25 says "Paths 4–6 … use `capture_config`." `capture_config` is used only in `tests/pipeline/test_effort_plumbing.py` and its helper. Existing coverage the task does not name:
- Path 2 and path 10 summary CLI: `test_effort_plumbing.py:50`, `:83`
- Path 4 and path 5: `test_effort_plumbing.py:23`, `:37`
- Path 9: `tests/cli/test_review_profile.py:622` (`test_alias_effort_reaches_the_review`)
- Path 10 renderer: `tests/pipeline/test_prompt_renderer.py:749–779`
- Path 6: `tests/review/test_review_client.py` and `tests/pipeline/actions/test_review_action.py` both mention effort. I did not check which assertion they make.

Task 25 should map each path to these named tests and add only real gaps. It should also say the assertion must target the wire value (`config.effort`), not only the stamp.

### [NOTE] Walkthrough step 2 claims coverage of paths 1–12 with an incomplete file list

Step 2 lists four test files and says "All pass, covering paths 1–12." The list omits the dispatch, summary and review action tests, the findings judge test, `_dispatch-run`, the outcome and producer tests, the report tests, and the inventory test. Task 27 runs these steps and records the result. Either list the files or drop the coverage claim and name the full suite as the gate.

### [NOTE] No load test, and the rule that would require one is not addressed

The slice restates no NFR, so the load-test check does not trigger. `python.md` requires a `tests/load/` test for code on "network" paths, and this slice edits provider-call code in dispatch, summary, review, the replay judge and the findings judge. The change is parameter plumbing with no concurrency or throughput change, so I think no load test is warranted. The task file should say so explicitly.

### [NOTE] Task 1 does not address the working tree's pre-existing state

At start, `git status` showed `M DEVLOG.md` (not part of this slice) and the task file untracked. Task 1 should say to commit the planning documents to the target before branching, and never to stage `DEVLOG.md` in slice commits. Commits should use explicit paths, not `git add -A`.

### [NOTE] Task 24's enumeration must match `ast.Call`, not text

A text search for `AgentConfig(` matches the class definition at `core/models.py:59`. The guard must match call nodes, or the definition gets flagged as an unclassified site.

### [PASS] Enumeration list matches the code

Grep finds eight `AgentConfig(` construction sites: `summary_oneshot.py:117`, `pr/composer.py:74`, `providers/auth.py:263`, `review/review_client.py:266`, `pipeline/actions/dispatch.py:249`, `metrology/audit.py:634`, `server/routes/agents.py:49` and `:179`. Task 24 lists all eight. `open_pipeline_session` callers (`executor.py:930`, `run_session.py:75`) also match.

### [PASS] Every functional criterion maps to a task, and sequencing is sound

Each functional criterion maps to a task: inventory guard (24), compaction (10–11), replay judge (12–13), findings judge at both entry points (14–15), `_dispatch-run` and renderer (16–18), failure attribution (4–5, 19–20), identity grouping (21–23), capability gate (3), CHANGELOG (26) and validation (27). Excluded items appear only as `NO_ALIAS` classifications. Each implementation task precedes its tests, and the 12 commit markers each sit after a tested unit. Readers (19) follow the stamps they read (4–10), and identity fields (21) precede grouping (22). I found no circular dependencies.

### Run Digest

- Response length: 13647 chars
- Response is newline-free: no
- Tool calls made: 34
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 35
- Tokens — prompt / cached / cache write / completion / reasoning: 1680089 / 1496478 / 183583 / 78448 / not computed
- Duration: 446.3 s
- Cost: $0.32 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 14
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 14
- Finding-shaped matches — surviving validation: 14
