---
docType: review
layer: project
reviewType: code
slice: squash-planning-commit-sets-command-and-pipeline-action
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/948-slice.squash-planning-commit-sets-command-and-pipeline-action.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261025
dateUpdated: 20261025
reviewedSha: 68276e577ec4902fffbb4da27794dfc530ef50bc
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 1
diffTruncated: false
turns: 2
promptTokens: 170813
cachedTokens: 17053
cacheWriteTokens: 153756
completionTokens: 4896
durationSeconds: 41.6
costUsd: 0.66996
costBasis: provider
squadronVersion: 0.24.1
findings:
  - id: F001
    severity: concern
    category: design
    summary: "Action and renderer import constants from the step module, inverting the dependency direction"
    location: "src/squadron/pipeline/actions/squash.py:16"
  - id: F002
    severity: concern
    category: dry
    summary: "Short-SHA length constant is duplicated"
    location: "src/squadron/cli/commands/squash_run.py:25"
  - id: F003
    severity: concern
    category: error-handling
    summary: "CLI handler's \"logged where they happen\" comment is not true for every caught exception"
    location: "src/squadron/cli/commands/squash_run.py:51-55"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Action lets `ContextForgeError` and plain `ValueError` from planning escape unhandled"
    location: "src/squadron/pipeline/actions/squash.py:50-60"
  - id: F005
    severity: concern
    category: failure-mode
    summary: "`apply_squash` does not re-check cleanliness or HEAD before `reset --hard` on failure"
    location: "src/squadron/pipeline/squash.py:apply_squash, _restore"
  - id: F006
    severity: concern
    category: testing
    summary: "Failure-mode tests are missing for timeouts and for a failed restore"
    location: "tests/pipeline/test_squash_apply.py"
  - id: F007
    severity: note
    category: design
    summary: "`SubjectPaths` exposes the private `_Candidate` type in a public dataclass"
    location: "src/squadron/pipeline/commit_plan.py:136-155"
  - id: F008
    severity: note
    category: performance
    summary: "`_find_run` spawns one `git diff-tree` per commit"
    location: "src/squadron/pipeline/squash.py:_find_run"
  - id: F009
    severity: note
    category: compatibility
    summary: "Error-message wording changed in the shared resolver"
    location: "src/squadron/review/persistence.py:_resolve_initiative_file"
  - id: F010
    severity: pass
    category: design
    summary: "Refusal checks, backup tag and tree verification"
    location: "src/squadron/pipeline/squash.py:_check_refusals"
---

# Review: code — slice 948

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Action and renderer import constants from the step module, inverting the dependency direction

`actions/squash.py` and `prompt_renderer.py` import `INDEX_PARAM`, `KIND_PARAM` and `DEFAULT_SLICE_REF` from `pipeline/steps/squash.py`. The step type sits above the action (it expands to the action), so the action now depends on the step layer and the shared contract has no neutral home. `steps/squash.py` also imports `SquashKind` from `pipeline/squash.py`. Define these parameter names once in `pipeline/squash.py` or a small constants module that the step, the action and the renderer all import. This keeps the "define once" rule without coupling the action to the step.

### [CONCERN] Short-SHA length constant is duplicated

`_SHORT = 8` repeats `_SHORT_SHA_LENGTH = 8` in `pipeline/squash.py`. The two are coupled, because the CLI prints SHAs that must match the 8-character suffix of the backup tag (`test_dry_run_prints_the_run_and_rewrites_nothing` relies on that). Export one constant and import it.

### [CONCERN] CLI handler's "logged where they happen" comment is not true for every caught exception

The first `except` clause catches `ValueError`, `FileNotFoundError` and `SquashRewriteError`, and the comment says all of them are logged where they happen. `SquashRefusedError` (via `_refuse`) and `SquashRewriteError` (via `_restore`) are logged. The plain `ValueError` from an unknown slice or initiative and the `FileNotFoundError` from a missing slice plan or architecture file are not, as far as the diff shows. Those paths are therefore swallowed with only a stderr print. Either log them at WARNING/ERROR, or narrow the comment and the tuple. The `try` also wraps the whole function body, which is broader than the "narrowly around the line that might fail" rule.

### [CONCERN] Action lets `ContextForgeError` and plain `ValueError` from planning escape unhandled

`plan_squash` documents `ValueError` ("cf does not know the slice") as a possible failure. The action's second `try` catches `SquashRefusedError`, `SquashRewriteError`, `CommitTargetError`, `SliceNotInPlanError` and `FileNotFoundError`. A bare `ValueError` that is not one of those subclasses, or a `ContextForgeError` from `read_integration_target`, will propagate and end the whole pipeline. The CLI treats the same errors as exit 1. If propagating is intended, say so in the comment. Otherwise, make the action and the CLI agree on which failures fail the step and which end the run.

### [CONCERN] `apply_squash` does not re-check cleanliness or HEAD before `reset --hard` on failure

Cleanliness, branch and remote checks happen in `plan_squash`. `apply_squash` then runs `reset --soft`, `commit` and, on any failure, `reset --hard <tag>`. Nothing verifies that HEAD still equals the planned head, or that the tree is still clean, between planning and applying. In SDK mode an agent step or concurrent process can change state in that window, and the restore would silently discard those changes. A cheap guard at the start of `apply_squash` would fail fast: compare `rev-parse HEAD` with the tag target or with a head recorded in `SquashPlan`.

### [CONCERN] Failure-mode tests are missing for timeouts and for a failed restore

The code handles `run_git` returning `None` (timeout or could not run) in several places. It also has a distinct branch where `reset --hard` itself fails ("restoring failed ... recover with"). None of the new tests exercise these branches, and the rules ask for at least one test asserting each failure mode's observable signal. Add tests that patch `run_git` to return `None` or a nonzero result for the restore call, and for `rev-parse --verify` in `_check_refusals`, which raises `GitEnvironmentError`.

### [NOTE] `SubjectPaths` exposes the private `_Candidate` type in a public dataclass

`SubjectPaths.candidates` is typed `tuple[_Candidate, ...]`. It works within the module and under strict pyright, but it leaks a private type through a public API. Consumers outside the module only use `contains` and `is_artifact`, so making `candidates` private would remove the leak.

### [NOTE] `_find_run` spawns one `git diff-tree` per commit

The scan stops at the first foreign or merge commit, so cost is bounded by the length of the run plus one. That is fine for planning loops. If a long planning history ever sits on top of a long run, a single `git log --name-only -z` pass would replace the per-commit subprocesses.

### [NOTE] Error-message wording changed in the shared resolver

`resolve_arch_file`'s error changed from "No architecture document matching" to "No arch document matching", and the multiple-match warning changed likewise. A repo-wide grep found no other references to the old text, so nothing visible breaks. Callers outside this repo that match on the message would still be affected.

### [PASS] Refusal checks, backup tag and tree verification

Refusals touch nothing and each logs at WARNING through `_refuse`. The backup tag is reused only when it points at HEAD. The new tree is compared to the planned tree before success is reported. Refusals and the main rewrite paths are covered by tests on real repositories, with history-unchanged assertions.

### Run Digest

- Response length: 6369 chars
- Response is newline-free: no
- Tool calls made: 1
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 2
- Tokens — prompt / cached / cache write / completion / reasoning: 170813 / 17053 / 153756 / 4896 / not computed
- Duration: 41.6 s
- Cost: $0.67 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10

## Response (20261025)

I checked each finding against the code. Six are fixed in `61426764`, F004 is answered with a comment, and three are left as they are.

- **F001: declined.** The action and renderer read param names from the step module the same way `actions/branch.py` and `_render_branch` read `OP_PARAM`/`WHEN_PARAM` from `steps/branch.py`. Moving squash alone would split the convention. If it changes, it should change for every step at once.
- **F002: accepted.** `pipeline/squash.py` exports `SHORT_SHA_LENGTH`, and the CLI prints with it, so printed shas and tag suffixes cannot drift apart.
- **F003: accepted.** The CLI now catches refusals and rewrite errors in their own clause, since those are already logged. An unknown slice or a missing architecture or slice plan file is logged at WARNING in a second clause before exit 1.
- **F004: accepted in part.** Plain `ValueError` from cf reaches the action as `SliceNotInPlanError` or `CommitTargetError`, which are caught. A cf failure while reading the target arrives as `GitEnvironmentError`. That one and a raw `ContextForgeError` end the run on purpose, the same as branch and commit. The comment now says so.
- **F005: accepted.** `SquashPlan` records `head`. `apply_squash` refuses before touching anything (no tag, no reset) if HEAD has moved or the tree is dirty. New tests: `test_head_moved_since_plan_refuses_and_touches_nothing` and `test_tree_dirtied_since_plan_refuses`.
- **F006: accepted.** `test_failed_restore_prints_the_recovery_command` covers a failing `reset --hard` after a failed commit and asserts the `recover with:` text and the ERROR record. `test_git_that_cannot_answer_raises_environment_error` covers `run_git` returning `None` in the tag lookup.
- **F007: declined.** Only `commit_plan.py` reads `candidates`, and `build_commit_plan` needs it. Callers outside the module use `contains` and `is_artifact`.
- **F008: declined.** The walk stops at the first commit outside the run, so the cost is the run's length plus one. That is what the review says too.
- **F009: accepted.** `_resolve_initiative_file` takes a label, so the errors read "No architecture document matching …" again, plus "No slice plan document matching …" for the new resolver.
