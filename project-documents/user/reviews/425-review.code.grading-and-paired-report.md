---
docType: review
layer: project
reviewType: code
slice: grading-and-paired-report
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: squadron
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/slices/425-slice.grading-and-paired-report.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261115
dateUpdated: 20261115
reviewedSha: 0dd899b940c0abca288d06ce775d05dc714f37a4
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 28
diffTruncated: false
effort: xhigh
turns: 29
promptTokens: 2444454
cachedTokens: 2076790
cacheWriteTokens: 367650
completionTokens: 79988
durationSeconds: 367.1
costUsd: 0.80468
costBasis: provider
runId: run-20261114-p6-27f2e9a4
squadronVersion: 0.24.28
categoriesNormalized: true
findings:
  - id: F001
    severity: fail
    category: correctness
    summary: "Snapshot config is read from the producer-editable sandbox tree"
    location: "src/squadron/benchmark/grade_snapshot.py:25"
  - id: F002
    severity: concern
    category: correctness
    summary: "The grading review inherits the `code` template's diff exclusions"
    location: "src/squadron/benchmark/grade_review.py#review_tree_diff"
  - id: F003
    severity: concern
    category: correctness
    summary: "The reference diff loses CR characters through text-mode git output"
    location: "src/squadron/benchmark/grade_prepare.py:51-66"
  - id: F004
    severity: concern
    category: correctness
    summary: "Hidden-fixture injection copies only the imports a fixture uses"
    location: "src/squadron/benchmark/python_injection.py:175-179"
  - id: F005
    severity: concern
    category: consistency-rot
    summary: "The `target_pass_rate_difference` rule is written twice"
    location: "src/squadron/benchmark/grading_config.py:36"
  - id: F006
    severity: note
    category: architectural-decay
    summary: "Three files are over the ~300-line guideline"
    location: "src/squadron/metrology/grade_models.py"
  - id: F007
    severity: note
    category: performance-resource
    summary: "Grade-store queries scan every record"
    location: "src/squadron/metrology/grade_store.py#GradeRecordStore"
  - id: F008
    severity: note
    category: type-contract-debt
    summary: "The report's `TableSection.data` is untyped"
    location: "src/squadron/benchmark/report_models.py#TableSection"
  - id: F009
    severity: note
    category: other
    summary: "The review-pair statistic may not match the floor it is compared to"
    location: "src/squadron/benchmark/bench_report.py#_review_pairs"
  - id: F010
    severity: note
    category: test-debt
    summary: "The load test's latency bound is too loose to catch regressions"
    location: "tests/load/test_benchmark_grading_volume.py"
  - id: F011
    severity: note
    category: error-handling-observability
    summary: "Broad exception handlers turn any snapshot or review failure into an absence"
    location: "src/squadron/benchmark/grade_checks.py#measure_and_store"
---

# Review: code — slice 425

**Verdict:** FAIL
**Model:** claude-haiku-5-5
**Evidence:** 28 successful tool call(s) of 28 made; 594602 of 594602 diff characters reached the model

## Findings

### [FAIL] Snapshot config is read from the producer-editable sandbox tree

`make_snapshot_measurer` calls `read_snapshot_config(tree)`, with the sandbox tree as the root. `read_snapshot_config` reads each setting through `get_config(key, cwd=repo_root)`. `load_config` merges in the project file at `project_config_path(cwd)`, which is `<tree>/.squadron.toml` (src/squadron/config/manager.py:42, :96). The producer's diff can edit that file.

`restore_config` does not restore it. `TOOL_CONFIG_FILES` in src/squadron/benchmark/python_grading.py:51 lists only ruff, pyright, mypy, pytest, coverage, setup.cfg, and tox.ini. The `[tool.*]` restoration covers only `pyproject.toml`. So `.squadron.toml` is neither restored nor deleted when the producer adds it.

The producer can therefore set the snapshot exclusion key (`_read_exclusions`, src/squadron/metrology/snapshot/preflight.py:117). Those patterns become `project_exclusions`, which `resolve_files` applies, so files drop out of the lint and type measurements. `_check_total` then reports smaller `lint_total` and `type_total` values, and the "checks vs baseline" deltas shift. The length limits and the tool timeout are producer-controlled in the same way.

Fix: read the snapshot config from the start commit (through the `TreeReader`), or add `.squadron.toml` to the restored set with delete-if-added. Add a test in which the producer adds `.squadron.toml` with an exclusion and asserts that the lint total does not change.

### [CONCERN] The grading review inherits the `code` template's diff exclusions

`review_tree_diff` calls the review without overriding exclusions. `run_review_with_profile` takes `exclude_patterns = template.diff_exclude_patterns` (src/squadron/review/review_client.py:189) and applies them to both the injected diff (:645-648) and the file list (:190-193). `code.yaml:102-115` excludes `*.md`, `*.yaml`, `*.yml`, `*.toml`, `*.json`, `*.txt`, `*.lock`, `*.csv`, and images.

The effect is that the reviewer never sees producer edits to `pyproject.toml` or `uv.lock`. Fixture `producer_c` is an example: its entire change is in those files, so the reviewer would see an empty diff, which D7 treats as a valid zero-findings outcome. Nothing in the review outcome records that files were excluded.

Decide in the design whether grading reviews should see these files. Either pass an empty exclusion set for grading, or record the exclusion set and the excluded-file count on the outcome. Add a test with a producer diff that edits only `pyproject.toml`.

### [CONCERN] The reference diff loses CR characters through text-mode git output

`subject_diff` gets a REFERENCE's diff from `run_git`, which goes through `SubprocessRunner` (src/squadron/core/process_runner.py:133-139). That call uses `text=True` and `TEXT_DECODING` (src/squadron/core/subprocess_text.py:25: utf-8 with `errors="replace"`). CPython's text-mode `communicate()` normalizes `\r\n` and lone `\r` to `\n`.

`apply_subject` then pipes that text to `git apply` (:70-79). For a CRLF source file, the context and `+` lines no longer match, so the apply fails with DIFF_APPLY_FAILED, which blames the reference. For a newly added CRLF file, the apply can succeed and write LF content silently, so the hidden tests run against a file that differs from the reference commit. `errors="replace"` also corrupts non-UTF-8 bytes in `--binary` output.

Replay diffs are not affected, because they come from stored bytes. Fix: write the reference diff to a file inside the sandbox (`git diff --binary --output=...`) and read bytes, or add a bytes-returning path to the runner. Add a test with a CRLF file in the reference commit. The grading fixtures in the diff are all LF, so no current test covers this. `GitTreeReader` has the same root cause, which tree_reader.py documents as #334. The diff path is not documented.

### [CONCERN] Hidden-fixture injection copies only the imports a fixture uses

`build_module` takes the function body of each hidden fixture, plus only the imports whose bound names that body uses (lines 175-178), and appends the function source (line 179). A fixture that reads a module-level constant or helper defined in the reference conftest, rather than an import, will raise NameError when the injected module is collected. The fixture also silently uses the producer's conftest for any other fixture it requests by name.

The failure is loud: hidden nodes error, and the reference then fails with REFERENCE_FAILED_GRADE and its case is dropped. The record does not show the missing name, so the cause is hard to find. Fix: copy the module-level names the fixture uses, or reject such fixtures with a named error at injection time. Add a test with a fixture that reads a module constant. Confidence is medium, since I read this code rather than executed it.

### [CONCERN] The `target_pass_rate_difference` rule is written twice

`check_target_difference` reimplements the `0 < value < 1` rule with its own message. The existing reader, `get_open_unit_interval_config` (src/squadron/config/manager.py:153-158), enforces the same rule, and the keys.py comment names it as the reader for this key. The rule now lives in two places, so the two messages can drift. Fix: extract a `check_open_unit_interval(key, value)` helper that both the typed reader and the grade seam call.

### [NOTE] Three files are over the ~300-line guideline

From the diff headers, `grade_models.py` and `benchmark_grade.py` are 312 lines each, and `python_injection.py` is 302. Not blocking, but worth splitting when the next change lands in them.

### [NOTE] Grade-store queries scan every record

`grades_for`, `largest_review_cost`, and `latest_estimate` each iterate `iter_records()` over the whole store. The yield command calls `latest_estimate` once per case set. This is fine at current scale but will grow with the store.

### [NOTE] The report's `TableSection.data` is untyped

`data: dict[str, Any]` is the one loosely typed boundary in the report models. Tests re-validate it into `FixTableData`. A typed union or a generic over the table's data model would keep the contract checked.

### [NOTE] The review-pair statistic may not match the floor it is compared to

`_review_pairs` compares the difference between two configs' per-case means of findings, each averaged over k replays, against `is_within_floor`. That floor is the spread of three single reviews of one reference diff. A difference of k-sample means has a different variance, so "beyond floor" may not mean what the report says. Confirm the statistic with the design owner.

### [NOTE] The load test's latency bound is too loose to catch regressions

The bound is 10 seconds per subject, and the run uses doubled suites and a doubled reviewer, so it does not exercise a realistic sandbox or suite. It still asserts that no sandbox is left behind. Tighten the bound against a measured baseline, or add a variant with a real suite run.

### [NOTE] Broad exception handlers turn any snapshot or review failure into an absence

`measure_and_store` catches `Exception`, logs with `logger.exception`, and raises `GradeAbsent`. `review_tree_diff` does the same. Both are logged and recorded, so nothing is silent. But a programming error in the measurer becomes a per-subject absence, and the run continues. Narrow the catch to the tool and I/O errors the measurer is expected to raise, and let other errors stop the run.

### Run Digest

- Response length: 10559 chars
- Response is newline-free: no
- Tool calls made: 28
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 29
- Tokens — prompt / cached / cache write / completion / reasoning: 2444454 / 2076790 / 367650 / 79988 / not computed
- Duration: 367.1 s
- Cost: $0.80 (provider)
- `## Summary` located: yes
- `## Findings` located: no
- Finding-shaped matches — whole response: 11
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 11
- Finding-shaped matches — surviving validation: 11
