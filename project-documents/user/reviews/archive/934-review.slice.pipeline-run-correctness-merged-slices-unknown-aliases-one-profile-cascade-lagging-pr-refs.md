---
docType: review
layer: project
reviewType: slice
slice: pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/934-slice.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md
aiModel: deepseek/deepseek-v4.1-flash
status: complete
dateCreated: 20261006
dateUpdated: 20261006
reviewedSha: 82bbb7ce0584999c46cfd62c26284ca87c5c7aec
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 48
turns: 20
promptTokens: 2350333
cachedTokens: 1993600
completionTokens: 118741
reasoningTokens: 113169
durationSeconds: 861.9
runId: run-20261007-p4-ced11784
squadronVersion: 0.20.1
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "The #186 ancestry test is specified against a commit the local clone typically will not have"
    location: "project-documents/user/slices/934-slice.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md:107-124"
  - id: F002
    severity: concern
    category: under-specification
    summary: "\"Counts as closed for dependency flagging\" is not pinned to the set the code actually flags on"
    location: "project-documents/user/slices/934-slice.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md:88"
  - id: F003
    severity: concern
    category: hidden dependency
    summary: "The code-host log handler mutates a process-global logger with `propagate = False` and has no teardown"
    location: "project-documents/user/slices/934-slice.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md:233"
  - id: F004
    severity: concern
    category: integration-mismatch
    summary: "The verbosity argument has no source at most call sites the design names"
    location: "project-documents/user/slices/934-slice.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md:235"
  - id: F005
    severity: note
    category: scope
    summary: "Four independently deliverable fixes bundled into one 4/5 slice"
    location: "project-documents/user/slices/934-slice.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md:45-51"
  - id: F006
    severity: note
    category: dependency-direction
    summary: "Frontmatter dependencies list only 197 while two decisions rest on 196"
    location: "project-documents/user/slices/934-slice.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md:55-57"
  - id: F007
    severity: pass
    category: boundaries
    summary: "New module placement and the host-neutral refspec seam respect the existing layer directions"
    location: "project-documents/user/slices/934-slice.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md:66-84"
---

# Review: slice — slice 934

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [CONCERN] The #186 ancestry test is specified against a commit the local clone typically will not have

The fetch flow decides "PR ref lags" by asking whether the fetched `refs/pull/N/head` sha is an ancestor of the API head sha, and only *then* fetches the API head by sha. In the reported case (GHE PR ref 30+ minutes behind) the API head commit is precisely the object the local checkout does not have — that is why the by-sha fetch fallback exists. `git merge-base --is-ancestor <unknown-sha> <fetched>` exits non-zero with "Not a valid object name", and `refs._is_ancestor` (`src/squadron/codehost/refs.py:168-183`) returns `False` for any exit code other than 0 while logging a WARNING. The design's D6 table therefore collapses git's third answer — "cannot answer" — into the `unrelated → force-push or rewrite → RefMovedSinceResolutionError` row, which is the misdiagnosis #186 was filed for ("sends the reader looking for a race"). D10's #186 table enumerates hang, non-zero exit and partial fetch, but has no row for "ancestry unanswerable because the object is absent". Either the fallback must run before the ancestry classification (fetch the sha, then classify), or the probe must require the sha locally and treat absence as a distinct, named state. This should be decided in D6 before implementation, not discovered in the test fixture.

### [CONCERN] "Counts as closed for dependency flagging" is not pinned to the set the code actually flags on

The Data Flow says a merged slice "is skipped as an item and counts as closed for dependency flagging", and the Success Criteria require that A's dependents are not flagged. But the flagging rule in `cf.slices_ready_to_implement` is `dependency in open_in_plan and dependency not in returned` (`src/squadron/pipeline/sources.py:268-281`), where `returned` is every item that made it into the list. A slice that is *dropped* from the item list while cf still reports it `not_started` is therefore still in `open_in_plan` and still not in `returned` — i.e. exactly the "dependency A not designed" flag the slice exists to remove. The design needs to state the mechanism (exclude merged slices from `open_in_plan`, or add them to the set the inner test consults) rather than the outcome, because the current condition is the trap. Item resume's `_open_dependencies` (`item_resume.py:327-337`) has the same shape (`status[d] != CfSliceStatus.COMPLETE`) and the design does say "either answer says so" there, which is clear; the selection path is the one that is not.

### [CONCERN] The code-host log handler mutates a process-global logger with `propagate = False` and has no teardown

`configure_code_host_logging` attaches a handler to the `squadron.codehost` logger and sets `propagate = False`. Two consequences the design does not address. First, `propagate = False` stops those records reaching any other handler — including the root handler `setup_logging` installs, whose wiring is the open recommendation in the tech-debt audits (`project-documents/user/analysis/941-analysis.tech-debt-audit.md` F016). The design's "Nothing that is visible today disappears" is true only while no root handler exists; the moment F016 is closed, every codehost diagnostic becomes invisible to it. Second, this repeats the exact shape of `_configure_agent_logging` in `cli/commands/review.py:452`, which is what issue #78 ("review CLI verbosity leaking global logger state across tests") was filed against. "Idempotent" is not the same as leak-free: Typer's `CliRunner` runs commands in-process, so the handler and the level persist after the command returns. The design should either specify teardown, or attach the handler from the entry point rather than from each command, and say how existing `caplog`-based codehost tests (`tests/codehost/test_github_cli.py`, `tests/cli/test_pr_show.py`) keep capturing records once the CLI path has run once in the same process.

### [CONCERN] The verbosity argument has no source at most call sites the design names

D8 specifies levels ("WARNING by default, INFO at `-v`, DEBUG at `-vv`") and says "Every command that renders `CodeHostError` (`sq pr show`, `sq review pr`, and the other `sq pr` subcommands) calls it once, before its first host call." `sq pr show` takes only `target`, `--cwd` and `--json` (`src/squadron/cli/commands/pr.py:100-113`), so there is no `-v` to pass. Either those subcommands gain a verbosity option (a user-facing CLI change the design does not scope or test) or the helper needs a defined default and a stated rule for which commands can vary it. Read together with "pr prints it twice" in the Overview — which the issue reports in a command that has no verbosity flag — the design should say plainly what `sq pr` commands do at their only verbosity level.

### [NOTE] Four independently deliverable fixes bundled into one 4/5 slice

900-arch Guidelines ask for "many small slices over few large ones" and "Each slice should be independently deliverable," and the plan's own entry (900-slices, item 32) frames 934 as four root-caused bugs bundled together. The four parts touch disjoint code (`git_ops`/`sources`/`item_resume`; `review.profile_resolution`/`classification`/`run.py`; `codehost.refs`/`pr.py`; each with its own tests) and the design already orders them 184+175 → 188 → 186. Nothing here is invalid under 900's scope, and bundling has in-initiative precedent (909, 916, 917); flagging only because in this case each part is independently landable and the Effort moved 3/5 → 4/5, which is the direction 900's guideline pushes against.

### [NOTE] Frontmatter dependencies list only 197 while two decisions rest on 196

D4 and D5 extend 196's machinery — `require_known_model`, `has_profile_param`, the pre-run classification check, `_collect_unknown_alias` — and the Prerequisites section names 196 (complete) alongside 197, which is correct. The `dependencies:` frontmatter carries only `[197]`. Low impact since both are complete, but the two lists should agree.

### [PASS] New module placement and the host-neutral refspec seam respect the existing layer directions

`review/profile_resolution.py` is placed in the `review` package that both `cli/commands/review.py` and `pipeline/actions/review.py` already import (the `pipeline → review` edge exists today), and it reads `default_review_profile` through the same `squadron.config.manager` the review package already imports, so the "one private reader" claim does not open a new edge. `refs.py` receives the GitHub refspec strings as `head_fallback_sources` instead of naming a host, which preserves the direction asserted by `tests/codehost/test_import_boundaries.py` ("`cli -> codehost -> core`", no `review → codehost` beyond `models`), and the new `RefAdjustment`/`FetchedRange.adjustments` types land in `codehost/models.py`, which that test already permits. The parent architecture states no NFR with a numeric target for any path this slice touches, so there is nothing to restate; the design does restate the existing `GIT_COMMAND_TIMEOUT_SECONDS` / `GIT_FETCH_TIMEOUT_SECONDS` / `GIT_QUERY_TIMEOUT_SECONDS` bounds in D10 and gives each new call an observable signal and a test.

### Run Digest

- Response length: 9121 chars
- Response is newline-free: no
- Tool calls made: 48
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 477425
- Effort: backend default
- Turns: 20
- Tokens — prompt / cached / completion / reasoning: 2350333 / 1993600 / 118741 / 113169
- Duration: 861.9 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
