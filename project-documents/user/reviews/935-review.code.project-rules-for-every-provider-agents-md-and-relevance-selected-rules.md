---
docType: review
layer: project
reviewType: code
slice: project-rules-for-every-provider-agents-md-and-relevance-selected-rules
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/935-slice.project-rules-for-every-provider-agents-md-and-relevance-selected-rules.md
aiModel: claude-opus-5-5
aiProfile: sdk
status: complete
dateCreated: 20261012
dateUpdated: 20261012
reviewedSha: ee553ac2cd9bed646235aaa363e33e6f417bbb96
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
diffTruncated: false
durationSeconds: 48.9
squadronVersion: 0.21.5
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Expected project-rules failures are logged as \"unexpected error\" with a full traceback"
    location: "src/squadron/pipeline/actions/dispatch.py:383-390"
  - id: F002
    severity: concern
    category: testing
    summary: "Test module imports private helpers from another test module"
    location: "tests/pipeline/actions/test_dispatch_project_rules.py:19-26"
  - id: F003
    severity: concern
    category: error-handling
    summary: "Unknown `steps` value raises outside the CLI review error handler"
    location: "src/squadron/cli/commands/review.py:1245-1253"
  - id: F004
    severity: note
    category: correctness
    summary: "`projectRules` frontmatter is written as an unquoted flow list"
    location: "src/squadron/review/persistence.py:433-434"
  - id: F005
    severity: note
    category: parsing
    summary: "Lenient parsing misses a multi-line inline list"
    location: "src/squadron/project_rules/frontmatter.py:47-72"
  - id: F006
    severity: note
    category: dry
    summary: "Rule-file separator constant is defined twice"
    location: "src/squadron/project_rules/render.py:28"
  - id: F007
    severity: note
    category: design
    summary: "`_candidate_rules` reports drops through a mutated argument"
    location: "src/squadron/project_rules/selection.py:89-110"
  - id: F008
    severity: note
    category: testing
    summary: "Real-repo selection test asserts an exact rule list"
    location: "tests/project_rules/test_selection.py:202-207"
  - id: F009
    severity: note
    category: testing
    summary: "`os.geteuid` skip guard is not Windows-safe"
    location: "tests/review/test_rules.py:247"
  - id: F010
    severity: pass
    category: async
    summary: "Selection I/O is kept off the event loop and fails loudly"
    location: "src/squadron/pipeline/actions/dispatch_rules.py:104-121"
  - id: F011
    severity: pass
    category: design
    summary: "Package layering and shared frontmatter extraction"
    location: "src/squadron/project_rules/__init__.py"
  - id: F012
    severity: pass
    category: testing
    summary: "Conventions discovery and provenance are well tested"
    location: "tests/project_rules/test_conventions.py"
---

# Review: code — slice 935

**Verdict:** CONCERNS
**Model:** claude-opus-5-5

## Findings

### [CONCERN] Expected project-rules failures are logged as "unexpected error" with a full traceback

The design intends four named failures here: a conventions file over budget (`ProjectRulesBudgetError`), an unreadable conventions file (`ConventionsReadError`), an unknown `steps` value (`ValueError`), and a git or mapping failure (`ProjectRulesContextError`). `DispatchAction.execute` catches none of them by name, so they all land in the catch-all `except Exception`, which calls `_logger.exception("dispatch: unexpected error ...")`. The step does fail correctly, and `test_conventions_over_budget_fails_the_action` confirms that. The problem is how it is reported: a user whose AGENTS.md exceeds `project_rules.max_chars` gets a stack trace labelled "unexpected". The handler already treats `DispatchStalledError` and `ProviderError` as named failures with a single log line and no traceback. Add one shared base, or a tuple of these exception types, and handle it the same way. A test should then assert that the log is a single WARNING/ERROR line with no traceback.

### [CONCERN] Test module imports private helpers from another test module

The test imports `_P`, `_make_agent_mock`, `_make_context`, `_make_registry`, `_openrouter_profile` and `_sdk_profile` from `tests.pipeline.actions.test_dispatch`, and each import needs a `reportPrivateUsage` suppression. That ties the two test files together, and pytest can end up collecting `test_dispatch` twice. The project rule is to put shared fixtures in `conftest.py`. Move these helpers into `tests/pipeline/actions/conftest.py`, or into a non-test helper module.

### [CONCERN] Unknown `steps` value raises outside the CLI review error handler

`load_review_rules` now raises `ValueError` from `parse_rule_frontmatter` when a rule file has a typo such as `steps: [implemnt]`. In `review_code`, and in `_resolve_pr_rules_content` in `review_pr.py`, that call runs before the guarded block at lines 727-766, so a typo in one rule file crashes `sq review code` with a raw traceback. Failing on the typo is correct; the traceback is not. Catch the error at this boundary and print the same `Error: ...` line as the other failures, then exit with code 1, or give it a named exception type.

### [NOTE] `projectRules` frontmatter is written as an unquoted flow list

`f"projectRules: [{', '.join(project_rules)}]"` writes filenames without quotes. That works for names like `python.md`, but a rule filename containing `,`, `:`, `#` or `[` would produce YAML that reads back wrong. Either quote each item, or check that the frontmatter reader treats these as opaque strings.

### [NOTE] Lenient parsing misses a multi-line inline list

The inline-list regex `\[(.*?)\]` cannot span lines. A value written as `paths: [\n "a",\n "b"\n]` therefore falls through to the scalar branch and is parsed as `["["]`, with no error. The project's parsing rule asks for common layout variations to be handled. Add DOTALL to the inline match, or reject a lone `[` explicitly.

### [NOTE] Rule-file separator constant is defined twice

`_SEPARATOR` in `render.py` and `_RULES_SEPARATOR` in `review/rules.py` are both `"\n\n---\n\n"`, and both are used to join rule files. Since `project_rules` is now the shared home for this logic, export the constant from there and reference it in both places.

### [NOTE] `_candidate_rules` reports drops through a mutated argument

`dropped` is passed in and appended to as an out-parameter. Returning `(selected, dropped)` would make the data flow explicit. The function also reads and parses rule files itself, while `frontmatter.load_rules_frontmatter` does the same job with different handling for unreadable files (it skips them; this function drops and records them). The difference looks intentional, but it is worth a comment.

### [NOTE] Real-repo selection test asserts an exact rule list

`test_implement_with_tracked_files` hard-codes `["bug-fixes.md", "python.md", "shell.md", "sql.md", "testing.md"]`. Testing against the real files satisfies the "real-world input" rule, but adding any rule under `.claude/rules` will break this test. Asserting membership of the key files would be less brittle, if that fits the intent.

### [NOTE] `os.geteuid` skip guard is not Windows-safe

`test_unreadable_template_rule_warns` evaluates `os.geteuid()` without a `sys.platform` check, so on Windows it raises `AttributeError` at collection time. `tests/project_rules/test_conventions.py:77` already guards against this correctly.

### [PASS] Selection I/O is kept off the event loop and fails loudly

`project_rules_for_dispatch` runs the git, config and file I/O in `asyncio.to_thread` and keeps rendering pure. `tracked_files` treats both git-missing and a non-zero exit as errors rather than "no files", and tests cover both cases. The no-rules case logs a WARNING, and a test asserts it.

### [PASS] Package layering and shared frontmatter extraction

`squadron.project_rules` imports nothing from `review` or `pipeline`, and the pipeline-specific glue is isolated in `dispatch_rules.py`. The glob and frontmatter logic moved out of `review/rules.py` without being duplicated. Unreadable rule files now log a WARNING where they used to be silently skipped. Lookup tables for step kinds and native conventions raise named errors on unmapped keys.

### [PASS] Conventions discovery and provenance are well tested

The tests cover candidate order, the skipped list, broken symlinks (which raise rather than falling through to the next candidate), unreadable files, `convention_root` honoring, and the `conventionsSource`/`projectRules` frontmatter for every save-target kind.

### Run Digest

- Response length: 6572 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 48.9 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 12
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 12
- Finding-shaped matches — surviving validation: 12

## Response (20261012)

- **F001 — fixed.** New `project_rules.errors.ProjectRulesError`, the base of `ConventionsReadError`, `ProjectRulesBudgetError`, `UnknownRuleStepError` (was `ValueError`) and `ProjectRulesContextError`. `DispatchAction.execute` catches it by name: one ERROR line, no traceback, step fails. The over-budget dispatch test asserts exactly one ERROR record with no `exc_info`.
- **F002 — fixed.** Shared builders moved to `tests/pipeline/actions/dispatch_helpers.py`; `test_dispatch.py`, `test_dispatch_project_rules.py` and `test_dispatch_session.py` import from it. No test imports another test module.
- **F003 — fixed.** `load_review_rules_or_exit` in `cli/commands/review.py` prints `Error: …` and exits 1 on `ProjectRulesError`; used by `_run_review_command`, `review_code` and the PR path. CLI test with `steps: [implemnt]` asserts exit 1, the message, and no review run.
- **F004 — no change.** `projectRules` holds rule filenames from the rules directory, and D7 fixes the unquoted `[python.md]` shape. A filename with `,`, `:`, `#` or `[` isn't a real rule file.
- **F005 — fixed.** The inline-list match is DOTALL, so `paths: [\n "a",\n "b"\n]` parses; test added.
- **F006 — fixed.** `RULES_SEPARATOR` is defined once in `project_rules.render` and imported by `review.rules`.
- **F007 — fixed.** `_candidate_rules` returns `(selected, dropped)`; its docstring says why it reads files itself (it needs content and records unreadable rules in `dropped`).
- **F008 — no change.** The exact list is the D3 contract for squadron's own rules, as the design's real-files requirement asks. A new rule file should fail this test so the expected per-kind result is updated on purpose.
- **F009 — fixed.** The skip guard checks `sys.platform` before `os.geteuid()`.
