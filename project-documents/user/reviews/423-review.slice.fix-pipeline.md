---
docType: review
layer: project
reviewType: slice
slice: fix-pipeline
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/423-slice.fix-pipeline.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261104
dateUpdated: 20261104
reviewedSha: ef6d51a92bef416c09d60faee087b218920b0079
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 10
effort: high
turns: 11
promptTokens: 515165
cachedTokens: 413972
cacheWriteTokens: 101181
completionTokens: 8218
durationSeconds: 68.0
costUsd: 0.57535
costBasis: provider
squadronVersion: 0.24.22
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Architecture alignment on the producer step and sandbox mode"
    location: "project-documents/user/slices/423-slice.fix-pipeline.md#Overview"
  - id: F002
    severity: concern
    category: dependencies
    summary: "Hidden dependency on 422 conflicts with `dependencies: []` and with 422's interface"
    location: "project-documents/user/slices/423-slice.fix-pipeline.md:6, 50-52"
  - id: F003
    severity: concern
    category: failure-modes
    summary: "Resume after a block or refusal conflicts with the clean-tree precondition"
    location: "project-documents/user/slices/423-slice.fix-pipeline.md:158, 157, 167"
  - id: F004
    severity: concern
    category: integration
    summary: "Prompt-only `start_head` capture point is ambiguous, so the HEAD-moved guard may be vacuous"
    location: "project-documents/user/slices/423-slice.fix-pipeline.md:106-107, 198"
  - id: F005
    severity: concern
    category: scope
    summary: "Parity scope drops \"MCP\" from the slice plan's success criterion"
    location: "project-documents/user/slices/423-slice.fix-pipeline.md:44, 199"
  - id: F006
    severity: concern
    category: proportionality
    summary: "D7 changes the shared `sq run` gate for one param, which is heavier than needed"
    location: "project-documents/user/slices/423-slice.fix-pipeline.md:177-181"
  - id: F007
    severity: concern
    category: failure-modes
    summary: "Fetch path I/O failure modes are incomplete"
    location: "project-documents/user/slices/423-slice.fix-pipeline.md:139, 204"
  - id: F008
    severity: note
    category: integration
    summary: "Staging \"everything\" in a sandbox can sweep in untracked artifacts"
    location: "project-documents/user/slices/423-slice.fix-pipeline.md:167-169"
  - id: F009
    severity: note
    category: proportionality
    summary: "Effort growth and size are justified, but the plan entry should be updated"
    location: "project-documents/user/slices/423-slice.fix-pipeline.md:349"
---

# Review: slice — slice 423

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Architecture alignment on the producer step and sandbox mode

The slice does what the architecture's "Envisioned State" and "The fix pipeline in a sandbox" sections ask for.
- It is a production `fix` pipeline with one producer step and no embedded review to strip.
- It takes frozen issue text from a file, with no GitHub or cf calls (D2, D5, D7).
- It commits to the current branch in a sandbox.
- It reuses the existing executor, `DispatchAction` and cost cap, with no forked copies.
- It rejects using `implement` for fixes, as the architecture does.
- Dependency directions are sound: 424 and 425 consume this slice, and it consumes the executor and `CodeHost`.
- The cost-cap NFR is restated with a target (`failure_kind: cost_cap`, walkthrough step 5).

### [CONCERN] Hidden dependency on 422 conflicts with `dependencies: []` and with 422's interface

The frontmatter says `dependencies: []`. The Prerequisites section then relies on three things from 422:
- `CodeHost.get_issue`
- bare-`#n` repository resolution
- the `issue_freeze` renderer, with a cutoff parameter that "must accept `None`"

422's D2 describes `issue_freeze` as "IssueSnapshot + fix timestamp -> frozen task text or rejection". It specifies no optional cutoff. This slice therefore imposes an interface change on 422 that 422 does not record.

The "if built first, this slice adds both exactly as 422 D2 specifies" clause creates two possible owners of the same code. Neither owner is pinned in the plan. The architecture's slice plan says 423 has no dependencies in this initiative.

Pick one owner and record it in both docs:
- 422 exports the renderer with an optional cutoff, and 423's frontmatter lists the dependency.
- Or 423 owns a small title/body/comments renderer and 422 wraps it with the cutoff and rejection.

Delete the "built first" branch either way.

### [CONCERN] Resume after a block or refusal conflicts with the clean-tree precondition

Three paths deliberately leave the agent's changes in the tree:
- `blocked` pauses with `awaits_human`.
- A `fix_report` refusal "leaves the agent's changes in the tree".
- A `cost_cap` stop after the dispatch also leaves the tree dirty.

D4 says `sq run --resume` "re-runs the step". D5 says `fix-context` refuses a dirty tree and recomputes `start_head`.

If resume re-enters at `fix-context`, every resume from these states fails on its own precondition. The user then has to discard the agent's work, which is the opposite of the point of pausing. If resume re-enters at `dispatch` or `commit`, then `start_head` must come from the saved run state rather than being recomputed.

The doc must state:
- which action a resume re-enters;
- how the clean-tree check treats changes this run produced;
- that `start_head` is persisted and reused.

Add a test for resume after `blocked`. This is a failure mode of the new step's pause path and is currently implicit.

### [CONCERN] Prompt-only `start_head` capture point is ambiguous, so the HEAD-moved guard may be vacuous

D9 says `SHA` is read "when the renderer builds the step's instructions, which is the moment the step starts". The `commit` action is the third action of the step, and its instructions are what carry `--start-head`.

If the renderer builds each action's instructions only when that action is reached, the SHA is read after the dispatch. An agent commit during the dispatch would then go undetected. That defeats the HEAD-unchanged check (D5) in `/sq:run`, which the parity criterion promises behaves the same as the SDK path.

State that the renderer reads HEAD once, before the first action's instructions. Alternatively, have `sq _fix-prompt` print the start HEAD for the session to pass on. Then add a parity test in which the "agent" commits mid-step.

### [CONCERN] Parity scope drops "MCP" from the slice plan's success criterion

The slice plan's 423 entry has the criterion "CLI, slash command and MCP give identical results". The design excludes MCP. Its reason is that squadron has no MCP server for pipelines, so adding the first one would be a separate feature.

The reasoning is sound and consistent with the architecture. But the design drops plan-assigned scope without the plan being amended. Update the 420 slice plan's 423 criterion to "CLI and slash command", or cite where the plan's MCP wording was resolved. Otherwise 423 will be read as incomplete against its own plan entry.

### [CONCERN] D7 changes the shared `sq run` gate for one param, which is heavier than needed

D7 changes the gate in `run.py` (`any_step_needs_context_forge(definition.steps)`) for every pipeline, to resolve placeholders before the check. It adds a before/after test over all built-in pipelines and is listed as a risk of its own.

The only consumer is `fix` with `commit-to=current`. A lighter option meets the requirement: `FixStepType.needs_context_forge` returns false, and `fix-context` fails explicitly when `commit-to: target` and the cf call (`read_integration_target`) is unavailable. That keeps the shared path untouched and still gives a cf-free sandbox run.

If the friendlier `_check_cf` message in target mode matters, say so and keep D7. Otherwise cut it. Note that D7 raises effort from the plan's 2/5 to 3/5 on its own.

### [CONCERN] Fetch path I/O failure modes are incomplete

D2 covers `CodeHostError` for not-found, auth and transport failures, with no retry and no file fallback. It does not say what happens if the `gh` call hangs. It does not state a bound or point to one that the existing `CodeHost` subprocess call already has.

State the timeout, or name the existing one. State that a timeout fails `fix-context` before any dispatch with a WARNING log.

The Technical Requirements list a unit test for each source. Add a test for the timeout/hang case so the failure mode produces an observable signal.

### [NOTE] Staging "everything" in a sandbox can sweep in untracked artifacts

The commit stages every untracked, non-ignored path. In a 424 sandbox, a project whose `.gitignore` at the start commit omits its venv or test caches would have those files committed into the fix diff. This pollutes the diff that 425 grades and 426 judges.

Squadron probably ignores them, so this may only matter for other cf projects. Consider noting in 424 or 425 how the environment directory is excluded. Nothing is needed in this slice beyond awareness.

### [NOTE] Effort growth and size are justified, but the plan entry should be updated

The design raises effort from 2/5 to 3/5 and says why. Sync the slice plan's effort for 423 so downstream planning (424's estimates) reads the same number. If the D7 cut above is taken, 2/5 to 3/5 may no longer be needed.

### Run Digest

- Response length: 7741 chars
- Response is newline-free: no
- Tool calls made: 10
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: high
- Turns: 11
- Tokens — prompt / cached / cache write / completion / reasoning: 515165 / 413972 / 101181 / 8218 / not computed
- Duration: 68.0 s
- Cost: $0.58 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9

## Responses

- **F002 (fixed):** Valid. 422 now owns `get_issue` and an issue renderer with an optional cutoff, the frontmatter lists `dependencies: [422]`, and the "built first" branch is gone. Bare-`#n` resolution already exists in `codehost/remotes.py` (`select_remote`), so it is no longer attributed to 422.
- **F003 (fixed):** Valid; a resumed step re-runs from `fix-context`, which would refuse the agent's own changes. Cut the pause: `blocked` now fails like any report refusal, leaves the tree, and the user re-runs after resolving it, so there is no resume path to define.
- **F004 (fixed):** `render_step_instructions` builds all of a step's actions at once, so the SHA is read before `fix-context` runs; D9 now says so. The parity test also covers a commit made between rendering and `sq _commit`.
- **F005 (noted):** The design's MCP exclusion stands. The 420 slice plan's 423 criterion should read "CLI and slash command give identical results"; that change is out of this slice's file.
- **F006 (fixed):** Took the cut. `FixStepType.needs_context_forge` returns false and the shared gate is untouched; target mode fails in `fix-context` through `read_integration_target`, which already raises when cf is unavailable.
- **F007 (fixed):** Named the existing bound: `GitHubCli`'s 30-second `HOST_COMMAND_TIMEOUT_SECONDS`, raising `HostCommandTimeoutError` (a `CodeHostError`), which fails `fix-context` before dispatch. Added a timeout case to the issue-source unit test.
- **F008 (noted):** Belongs to 424/425 sandbox setup; nothing changes in this slice.
- **F009 (noted):** Effort stays 3/5, since the stated reason is prompt-only parity and the report contract, not D7. The slice plan's 423 effort should be updated to 3/5.
