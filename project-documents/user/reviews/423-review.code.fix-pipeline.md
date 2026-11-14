---
docType: review
layer: project
reviewType: code
slice: fix-pipeline
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/423-slice.fix-pipeline.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261113
dateUpdated: 20261113
reviewedSha: f07627546545da08f5df226a430f5fc9fe2054fb
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 47
diffTruncated: false
effort: xhigh
turns: 48
promptTokens: 2724564
cachedTokens: 2526898
cacheWriteTokens: 197634
completionTokens: 75354
durationSeconds: 329.2
costUsd: 0.521106
costBasis: provider
runId: run-20261114-p6-1708bfe1
squadronVersion: 0.24.28
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "A `fix` step without `model:` dispatches with the alias \"None\""
    location: "src/squadron/pipeline/steps/fix.py:97"
  - id: F002
    severity: concern
    category: correctness
    summary: "The fix commit assumes the run's cwd is the repository root"
    location: "src/squadron/pipeline/actions/commit.py:174"
  - id: F003
    severity: concern
    category: consistency-rot
    summary: "The build-context prompt contract is duplicated as literals and widened to any action"
    location: "src/squadron/pipeline/actions/fix_context.py:48"
  - id: F004
    severity: note
    category: consistency-rot
    summary: "`commit-to` is validated in three places with three wordings"
    location: "src/squadron/pipeline/actions/fix_context.py:82"
  - id: F005
    severity: note
    category: consistency-rot
    summary: "`PullRequestTarget` is used for issue references"
    location: "src/squadron/pipeline/fix_issue.py:83"
  - id: F006
    severity: note
    category: correctness
    summary: "`check_fix_flags` treats an explicit `--slice 0` as not given"
    location: "src/squadron/cli/commands/commit_run_fix.py:68"
  - id: F007
    severity: note
    category: type-contract-debt
    summary: "`fix_prior_outputs` relies on an `assert` for its precondition"
    location: "src/squadron/cli/commands/commit_run_fix.py:93"
  - id: F008
    severity: note
    category: security-hygiene
    summary: "Issue text is an unreviewed prompt input"
    location: "src/squadron/pipeline/fix_issue.py:81"
  - id: F009
    severity: note
    category: correctness
    summary: "Verified: the `_project` gating change does not drop emit's project key"
    location: "src/squadron/pipeline/executor.py:587"
  - id: F010
    severity: note
    category: architectural-decay
    summary: "`commit.py` has grown to 352 lines"
    location: "src/squadron/pipeline/actions/commit.py:132"
---

# Review: code — slice 423

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 47 successful tool call(s) of 47 made; 178715 of 178715 diff characters reached the model

## Findings

### [CONCERN] A `fix` step without `model:` dispatches with the alias "None"

`FixStepType.expand` always emits `{MODEL_KEY: cfg.get(MODEL_KEY)}`, so the key is present with `None` when the step omits `model`. `DispatchAction` tests `"model" in context.params` (src/squadron/pipeline/actions/dispatch.py:690, :1019, :1025) and then calls `str(...)`, which turns `None` into the string `"None"`. `resolve_full` (src/squadron/pipeline/resolver.py:199-205) takes the first non-`None` candidate, so `"None"` takes precedence over the run's `-m`, the pipeline model and the config default. The step then runs on whatever `"None"` resolves to, or fails with a misleading error.

`validate` does not require `model`, so this config is accepted. The built-in `fix.yaml` always sets `model: sonnet`, so the shipped path is unaffected. Custom fix steps are affected.

The tests miss it. `test_expand_order_and_configs` always passes a model, and every pipeline test replaces the dispatch action with `_FakeAgent` (tests/pipeline/test_fix_pipeline.py), so the real `DispatchAction` never sees a fix step's params. The fix is to omit the key when `model` is absent, and to add a test that runs a model-less fix step through the real dispatch's model resolution.

### [CONCERN] The fix commit assumes the run's cwd is the repository root

`changed_paths` runs `git status --porcelain=v1` (src/squadron/pipeline/guarded_commit.py:30). Porcelain paths are always relative to the repository root. `_stage_and_commit` then runs `git add -- <paths>` and `git commit -- <paths>` with `cwd` set to the process's directory (commit.py:174-187). `sq run` and `sq _commit` both pass `os.getcwd()`.

When the run starts in a subdirectory, the pathspecs resolve against the wrong directory. The add or commit fails only after `fix-context` has passed and the dispatch has already changed the tree. Nothing checks the top-level directory at `fix-context`, so the agent's work is spent before the failure. The scoped commit path avoids this through the `root` handling in `commit_plan`. Every fix test runs from the repository root, so this case is untested. The fix is to refuse early at `fix-context` when cwd is not the top level, or to run the git commands against the top level. Add a test that runs from a subdirectory.

### [CONCERN] The build-context prompt contract is duplicated as literals and widened to any action

`OPERATION_KEY = "operation"` and `PROMPT_KEY = "stdout"` are private copies of the cf-op output keys. `cf_op.py:177` writes `"stdout"` and `"operation"` as literals, and `dispatch.py:846-847` reads the same two literals. The dispatch fallback used to require `action_type == CF_OP`. It now accepts any result whose `operation` is `build_context` and that has a `stdout` (dispatch.py:843-848). Any action can therefore become the dispatch prompt source by writing those two keys, and the contract is spread across three modules with no shared constant. The fix is to define the key names once, next to `CfOperation`, and reference them from all three. The alternative is to restore an identity check on the producing action. `test_dispatch_prompt_identity.py` asserts the widened behaviour, so it would need updating too.

### [NOTE] `commit-to` is validated in three places with three wordings

The check is repeated in `steps/fix.py:60-62` ("is not one of"), `fix_context.py:82-85` ("must be one of"), and `commit_run_fix.py#_check_fix_values`. Each uses `COMMIT_TO_VALUES`, so the values are not scattered, but the parse-and-check logic is duplicated. A single `parse_commit_to(raw) -> CommitTo` in `fix_keys` would remove the drift.

### [NOTE] `PullRequestTarget` is used for issue references

`IssueTextLoader._fetch` builds a `PullRequestTarget(form=TargetForm.NUMBER, ...)` to choose a repository for an issue number. The codehost target type is shared between pull requests and issues, so the name misleads anyone reading this path. This is a naming issue only and has no behavioural effect.

### [NOTE] `check_fix_flags` treats an explicit `--slice 0` as not given

`value not in (None, [], 0)` ignores explicit zero values as well as defaults. `--slice 0` on a fix commit is therefore silently dropped instead of refused, which is the case this check exists to catch. Use `None` as the sentinel for each flag. The impact is small if slice 0 is never valid.

### [NOTE] `fix_prior_outputs` relies on an `assert` for its precondition

`assert flags.issue is not None and flags.report_file is not None` is the only guard on a public function's inputs. It disappears under `python -O`, and it depends on the caller having run `check_fix_flags` first. Passing narrowed values, or raising explicitly, would make the precondition hold on its own.

### [NOTE] Issue text is an unreviewed prompt input

`_fetch` puts the full issue text and every comment, from any commenter, into the agent prompt. Per design D3 there is no cutoff. The agent has write access to the working tree, and the pipeline commits every changed path. The commit is local and nothing is pushed, and `fix.md` marks the issue text as data, so the exposure is bounded. The trust boundary should still be recorded in the design, and the resulting commit should not be treated as reviewed.

### [NOTE] Verified: the `_project` gating change does not drop emit's project key

The executor now injects `_project` only when a step needs cf. Its readers, `emit.py:117` and `actions/devlog.py:63`, fall back to `"unknown"`. The only steps that emit to the default summaries path or write devlog entries are `summary` and `devlog`, and both return `True` from `needs_context_forge` (steps/summary.py:81-83, steps/devlog.py:49-51). No existing pipeline loses its project key. The real dispatch on the fix path also never reaches cf: `_kept_outputs` and `_finish_implementation` are gated on implement-only params. The `needs_context_forge=False` declaration for `fix` is therefore sound.

### [NOTE] `commit.py` has grown to 352 lines

The fix branch adds `_fix_commit`, and the `literal_paths` flag threads through `_stage_and_commit`. That puts the file above the ~300-line guidance and gives one action two commit paths. `fix_commit.py` already holds the fix plan, so the fix dispatch and its helpers could move there.

### Run Digest

- Response length: 12329 chars
- Response is newline-free: no
- Tool calls made: 47
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 48
- Tokens — prompt / cached / cache write / completion / reasoning: 2724564 / 2526898 / 197634 / 75354 / not computed
- Duration: 329.2 s
- Cost: $0.52 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
