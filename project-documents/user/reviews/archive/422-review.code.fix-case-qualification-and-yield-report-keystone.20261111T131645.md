---
docType: review
layer: project
reviewType: code
slice: fix-case-qualification-and-yield-report-keystone
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/422-slice.fix-case-qualification-and-yield-report-keystone.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261111
dateUpdated: 20261111
reviewedSha: 29011817e2f81485fa886b4270ed6413a50f59fb
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 21
diffTruncated: false
effort: xhigh
turns: 22
promptTokens: 1758487
cachedTokens: 1451299
cacheWriteTokens: 307176
completionTokens: 57096
durationSeconds: 252.2
costUsd: 0.63578
costBasis: provider
runId: run-20261111-p6-62b55a9e
squadronVersion: 0.24.26
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "Git-quoted path decoding replaces escapes in the wrong order"
    location: "src/squadron/benchmark/diff_classify.py:72-73"
  - id: F002
    severity: concern
    category: correctness
    summary: "Cutoff boundary is inconsistent between body edits and title renames"
    location: "src/squadron/benchmark/issue_freeze.py:58-64"
  - id: F003
    severity: concern
    category: type-contract-debt
    summary: "Parser turns missing title and body into empty strings"
    location: "src/squadron/codehost/github_parse.py:187-188"
  - id: F004
    severity: concern
    category: performance-resource
    summary: "Reused candidates still pay for the environment"
    location: "src/squadron/benchmark/qualify_sandbox.py:114"
  - id: F005
    severity: concern
    category: correctness
    summary: "Installer failures become candidate rejections"
    location: "src/squadron/benchmark/qualify_sandbox.py:69-78"
  - id: F006
    severity: concern
    category: architectural-decay
    summary: "The reuse predicate is implemented twice"
    location: "src/squadron/benchmark/qualify.py:24"
  - id: F007
    severity: concern
    category: architectural-decay
    summary: "Language-specific rules are in the language-neutral stage, and one constant is duplicated"
    location: "src/squadron/benchmark/qualify_stages.py:45"
  - id: F008
    severity: note
    category: consistency-rot
    summary: "Git query timeouts are defined a fourth and fifth time"
    location: "src/squadron/cli/commands/benchmark_common.py:9"
  - id: F009
    severity: note
    category: architectural-decay
    summary: "Two places build the same `FixQualification` fields"
    location: "src/squadron/benchmark/qualify_types.py:119"
  - id: F010
    severity: note
    category: error-handling-observability
    summary: "Stale plugin output can satisfy the \"plugin loaded\" check"
    location: "src/squadron/benchmark/python_fairness.py:218-222"
  - id: F011
    severity: note
    category: test-debt
    summary: "A test assertion accepts either of two values"
    location: "tests/benchmark/test_fix_cases_cli.py:163"
  - id: F012
    severity: note
    category: type-contract-debt
    summary: "New test doubles suppress strict-typing errors instead of typing the fakes"
    location: "tests/benchmark/test_python_boundary.py#_Runner.run"
---

# Review: code — slice 422

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 21 successful tool call(s) of 21 made; 489434 of 489434 diff characters reached the model

## Findings

### [CONCERN] Git-quoted path decoding replaces escapes in the wrong order

`_unquote` applies `_SIMPLE_ESCAPES` with sequential `str.replace` calls, and the escaped-backslash entry (`\\`) runs first (line 64). For a file named with a literal backslash followed by `n`, git quotes it as `"x\\n"`. The first replacement turns that into `x\n`, and the `\n` replacement then produces a newline. The decoded path is wrong, so `_read_at` reads a nonexistent path and the candidate fails with a misleading error or classification. A single-pass decoder (one regex with alternation, or a character loop) fixes it. Add a parametrized case with a backslash before `n` and `t`.

### [CONCERN] Cutoff boundary is inconsistent between body edits and title renames

The body and comment-edit check (`_edited_after`, line 58) uses `> cutoff`, so a body edited exactly at the fix's committer time is accepted. The title-rename check (line 64) uses `>= cutoff`, so a rename at that same instant is rejected. Comment creation (line 38) uses `< cutoff`, which omits a comment created at the cutoff. Three checks answer "changed at the cutoff?" three ways. The test suite pins the title case (`test_a_title_rename_after_the_cutoff_rejects_and_one_before_does_not`) but no test covers a body edit at the cutoff. Pick one boundary and test it for all three.

### [CONCERN] Parser turns missing title and body into empty strings

`to_issue_snapshot` reads `title` and `body` with `str(... or "")`, and `to_issue_comment` does the same for comment bodies (line 170). `require_str` (line 60) already exists and is used for `number` in the same function. The GitHub schema types these fields as non-null strings, so a null is response drift. The current code silently produces an empty heading or body, and that becomes the frozen task text with no error. Use `require_str`, and reserve the `or ""` default for the deleted-author case the comment at line 168 describes.

### [CONCERN] Reused candidates still pay for the environment

`_qualify_in` checks for a reusable record only after `deps.sandbox_factory` has entered the sandbox. `BenchmarkSandbox.__enter__` calls `self._environment.prepare()` and `resolve_environment` (sandbox.py:113-115) before returning, and the reuse key includes the environment digest, which exists only after that point. Re-running `fix-cases build` therefore prepares an environment for every candidate even when it reuses the record. The reuse test checks that no suite runs, not that no environment is prepared. Either key reuse on an identity computed before the sandbox (for example, lockfile hash plus interpreter), or document the cost and test for it.

### [CONCERN] Installer failures become candidate rejections

Every `EnvironmentResolutionError` becomes a REJECTED `environment_unresolved` verdict. Its reasons include `INSTALLER_MISSING` and `INSTALL_TIMEOUT` (adapter.py:25-26). The design (slice 422 line 301) does map all of 421's resolution errors to `environment_unresolved`, so this follows the design. It conflicts with this module's docstring (lines 6-7): "a harness failure is a `harness_error` record, never a verdict on the candidate." If `uv` is missing from `PATH`, every candidate is rejected, and the yield report then reports that as candidate quality. Map `INSTALLER_MISSING` (and probably `INSTALL_TIMEOUT`) to `HARNESS_ERROR`, or amend the design and the docstring together.

### [CONCERN] The reuse predicate is implemented twice

`qualification_for` and `_reusable` (qualify_sandbox.py:85-101) implement the same match: project, commit, environment digest, rule version, and not `harness_error`. Only `_reusable` runs in this branch. `qualification_for` is called only from `tests/benchmark/test_qualify_repeats.py`, and the design says 424 will consume it. The two differ in one way: `_reusable` converts store errors to `BuildHalted`, and `qualification_for` lets them propagate. The docstring also says the caller re-runs `qualify_candidate` "with the sandbox it already holds," which is not how `_qualify_in` works. Make `_reusable` delegate to one shared function, and correct the docstring.

### [CONCERN] Language-specific rules are in the language-neutral stage, and one constant is duplicated

`PYPROJECT_NAME` is defined here (line 45) and again in `python_tree_files.py:21`. The pre-sandbox stage, which is meant to be language-neutral, also encodes the Python rule "no `pyproject.toml` at the parent means no fix-case adapter" (lines 118-121). `case_build.py:134` and `:137` hard-code `SourceLanguage.PYTHON` in the orchestrator. Move the adapter-presence check behind the adapter (or the registry), and import the file-name constant from one place.

### [NOTE] Git query timeouts are defined a fourth and fifth time

This branch adds `GIT_TIMEOUT_S = 60` here and `GIT_QUERY_TIMEOUT_S = 60` in `python_fairness.py:48`. The codebase already defines `GIT_QUERY_TIMEOUT_SECONDS = 30` in `codehost/git_refs.py:24` and `codehost/remotes.py:29`. The two new constants disagree with the existing value. Reuse the existing constant, and pass the timeout into the adapter rather than defining it there.

### [NOTE] Two places build the same `FixQualification` fields

`record_outcome` (line 98) builds the record with `model_validate` on a dict, and `record_discovery_rejection` (line 121) calls the constructor. Both set the same project, commit, parent, issue reference, rule version, repeats, and timestamp. One helper removes the duplication and keeps `FAIRNESS_RULE_VERSION` in one place.

### [NOTE] Stale plugin output can satisfy the "plugin loaded" check

`_run_plugin` never deletes the output file before a run. The plugin's own design says a file that exists proves it loaded, but a file left by an earlier run in the same `output_dir` also satisfies that check. Practical impact is small: if the plugin fails to load, pytest exits with a usage error that the exit-code check (line 223) catches. Still, delete the output path before each run so the invariant holds.

### [NOTE] A test assertion accepts either of two values

The assertion `repo_root == Path(repo).resolve() or repo_root == repo` passes for either value, so it would not catch a wrong root. Pick the one the code produces and assert it.

### [NOTE] New test doubles suppress strict-typing errors instead of typing the fakes

The project requires strict pyright with tests included. The new tests add `# type: ignore[no-untyped-def]` and `# type: ignore[arg-type]` to fakes, for example `_Runner.run` here, `no_sandbox` and `FailingCaseSets.write_case_set` in `tests/benchmark/test_case_build.py`. Type the fakes, or use a `Protocol`. I have not run pyright, so I cannot say whether these suppressions hide errors.

### Run Digest

- Response length: 9900 chars
- Response is newline-free: no
- Tool calls made: 21
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 22
- Tokens — prompt / cached / cache write / completion / reasoning: 1758487 / 1451299 / 307176 / 57096 / not computed
- Duration: 252.2 s
- Cost: $0.64 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 12
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 12
- Finding-shaped matches — surviving validation: 12
