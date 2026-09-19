---
docType: review
layer: project
reviewType: code
slice: create-a-pr-with-a-good-message
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/385-slice.create-a-pr-with-a-good-message.md
aiModel: z-ai/glm-5.3
status: complete
dateCreated: 20260919
dateUpdated: 20260919
responseStatus: addressed
reviewedSha: 35d2cde8d2ceeac449679face773a362ddc3064d
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 7
findings:
  - id: F001
    severity: concern
    category: uncategorized
    summary: "Title-length bound is scattered across prompt text and constant"
    location: "src/squadron/pr/body.py:55-117"
  - id: F002
    severity: concern
    category: uncategorized
    summary: "test_body.py mutates the provider registry without teardown"
    location: "tests/pr/test_body.py:108-113"
  - id: F003
    severity: concern
    category: uncategorized
    summary: "body.py exceeds the ~300-line file-size guideline"
    location: "src/squadron/pr/body.py"
  - id: F004
    severity: note
    category: uncategorized
    summary: "`select_base`'s `cwd` parameter is unused and misleading"
    location: "src/squadron/pr/base.py:44-66"
  - id: F005
    severity: note
    category: uncategorized
    summary: "`create` local-sha read does not check the return code"
    location: "src/squadron/cli/commands/pr.py:216-219"
  - id: F006
    severity: note
    category: uncategorized
    summary: "Design file is read up to three times per compose"
    location: "src/squadron/pr/body.py:206-257"
  - id: F007
    severity: note
    category: uncategorized
    summary: "`create` is ~75 non-whitespace lines, above the ~50-line function guideline"
    location: "src/squadron/cli/commands/pr.py:196-261"
  - id: F008
    severity: pass
    category: uncategorized
    summary: "Failure modes are enumerated, observable, and tested"
    location: "src/squadron/pr/preconditions.py:47-75"
---

# Review: code — slice 0

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3

## Findings

### [CONCERN] Title-length bound is scattered across prompt text and constant

`_TITLE_MAX_CHARS = 72` is defined as the single source of truth, but `_compose_title`'s prompt hardcodes a second copy: `"Write one pull-request title, under 72 characters..."` (body.py:117). CLAUDE.md's "never scatter comparison values" rule says a value used in conditionals/lookups must be defined once. If the constant is ever changed, the prompt tells the model a different bound than the code enforces, and the model's "valid" responses start silently falling back to the commit subject. Build the prompt from the constant (`f"...under {_TITLE_MAX_CHARS - 1} characters..."` or similar).

### [CONCERN] test_body.py mutates the provider registry without teardown

Most tests in `test_body.py` insert fakes with a bare `registry_mod._REGISTRY[_FAKE_PROVIDER_TYPE] = provider` (and the `sdk` test at ~line 165 uses manual try/finally restore). Unlike `tests/cli/conftest.py`'s `fake_composer`, which correctly uses `monkeypatch.setitem`, several of these assignments leak a fake provider into the process-global registry for the remainder of the test session. The manual try/finally in the `sdk` test works but is fragile (an assertion failure between insert and restore would still be caught by finally, but the pattern invites copy-paste without it). Use `monkeypatch.setitem(registry_mod._REGISTRY, ...)` throughout for automatic restoration.

### [CONCERN] body.py exceeds the ~300-line file-size guideline

The file is 465 lines, well past the project's "~300 lines where practical" guideline, and it bundles three distinct responsibilities: the one-shot composer (`compose_one_shot`), title resolution (D4a), and the section contract plus presence check (D4/D5). Each has its own tests and its own reason to change — splitting into `composer.py`, `title.py`, and `body.py` (sections + check) would honor both the size rule and SRP. Not blocking, but the next section added will push it further.

### [NOTE] `select_base`'s `cwd` parameter is unused and misleading

`_read_integration_branch(cwd, ...)` accepts `cwd` and never uses it; `select_base` threads it through solely to forward it. Unlike `resolve_diff_base` (which presumably uses `cwd`), this function reads config, not the working tree. An unused parameter invites a future caller to believe `cwd` affects the result. Drop it or document why it's kept.

### [NOTE] `create` local-sha read does not check the return code

`git rev-parse HEAD`'s result is stripped and used without checking `returncode`; on failure `local_sha` becomes `""`, and the failure surfaces later as a confusing `HeadBranchBehindError` ("host is at X, but local is at ''"). Contrast with `_current_branch`, which does check. Checking the return code and raising a specific error here would keep the detached/dead-repo failure modes distinct.

### [NOTE] Design file is read up to three times per compose

`_read_design_h1` (title path), `_what_changed_prompt`, and `_why_prompt` each independently `Path(...).read_text()` the same design document (the latter two truncate at 6000 chars). Correct but wasteful and a mild DRY smell; passing the excerpt (or the facts plus a cached read) through `PrFacts`/composition state would read it once.

### [NOTE] `create` is ~75 non-whitespace lines, above the ~50-line function guideline

The command body threads five sequential phases (resolution, preconditions, base, inputs, composition, write). The ordering is deliberate and well-commented, so restructuring is optional, but extracting the input-gathering try block or the composition block would bring it under the guideline.

### [PASS] Failure modes are enumerated, observable, and tested

Missing vs. behind vs. timed-out vs. git-unavailable are each distinct errors with distinct fix hints, each observable, and each covered by a test (`tests/pr/test_preconditions.py`, `tests/cli/test_pr_create_failures.py`). Degradations (unreadable design, unresolvable slice, missing task file, malformed review frontmatter) all log at WARNING and are asserted with `caplog` — no silent failure paths found. The empty-range/unresolvable-range distinction in `commits_in_range` is likewise tested with real-world-style input.

## Response

All seven findings accepted and fixed. Verified after the changes: `ruff format` clean,
`ruff check` clean, `pyright` 0 errors, full suite **3 failed / 4206 passed / 6
skipped**. The three failures are `tests/documents/test_schema_drift.py`, the known
context-forge #88 symptom this worktree already carried, failing identically before
these changes.

### [CONCERN] F001 — title-length bound scattered across prompt and constant

Fixed. `_compose_title`'s prompt is built from `_TITLE_MAX_CHARS`
(`src/squadron/pr/title.py`); the bound has one definition.

### [CONCERN] F002 — `test_body.py` mutated the provider registry without teardown

Fixed. Every registry insertion in the composer tests (now `tests/pr/test_composer.py`)
goes through `monkeypatch.setitem`, including the `sdk` test, whose manual
try/finally restore is gone.

### [CONCERN] F003 — `body.py` exceeded the file-size guideline

Fixed by the split the finding proposed: `pr/composer.py` (`compose_one_shot`,
`CompositionError`, `Composer`), `pr/title.py` (D4a), and `pr/body.py` (section
contract + presence check, now 271 lines). Tests split to match:
`test_composer.py`, `test_title.py`, `test_body.py`. The tool-gate's sanctioned-site
list (`tests/tools/test_effective_tools.py`) names `pr/composer.py`.

### [NOTE] F004 — `select_base`'s `cwd` parameter was unused

Fixed. Dropped from `select_base` and `_read_integration_branch`, and from the call
sites.

### [NOTE] F005 — `create` did not check `git rev-parse HEAD`'s return code

Fixed. `_local_head_sha` raises `TargetUnresolvableError` on a non-zero exit or empty
output, so the failure no longer reaches the pushed-branch check as `""`. Test:
`test_unreadable_local_head_is_its_own_refusal`.

### [NOTE] F006 — design file read up to three times per compose

Fixed, and the fix closed a latent defect the finding did not name: all three reads
used `Path(design_file)` relative to the *process* working directory, not `--cwd`, so
`sq pr create --cwd <repo>` run from elsewhere would have lost the design silently.
Input gathering now reads the design once, relative to `cwd`
(`inputs._read_design_text`, WARNING on failure), and carries it as
`SliceInputs.design_text` / `PrFacts.slice_design_text`; the title and both prompts
consume that text. Tests: `test_slice_branch_with_design_and_tasks` asserts the text
is read under `cwd`; `test_unreadable_design_degrades_to_absent_text_with_a_warning`
replaces the title-path warning test.

### [NOTE] F007 — `create` was above the function-size guideline

Fixed. Input gathering with its two range refusals moved to `_gather_facts`, and the
HEAD read to `_local_head_sha`; `create` keeps only the D8 phase ordering.

### Run Digest

- Response length: 5054 chars
- Response is newline-free: no
- Tool calls made: 7
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 4062
- `## Summary` located: no
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
