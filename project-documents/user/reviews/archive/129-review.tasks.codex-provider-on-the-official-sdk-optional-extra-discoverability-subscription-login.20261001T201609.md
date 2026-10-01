---
docType: review
layer: project
reviewType: tasks
slice: codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/129-tasks.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md
aiModel: deepseek/deepseek-v4.1-flash
status: complete
dateCreated: 20261001
dateUpdated: 20261001
reviewedSha: 97b6c9f507f344d81eb7a9a2f3735f8195468db8
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 12
turns: 8
promptTokens: 271277
cachedTokens: 227200
completionTokens: 20185
reasoningTokens: 18211
durationSeconds: 63.3
runId: run-20261001-p5-9c2f4175
squadronVersion: 0.17.0
findings:
  - id: F001
    severity: pass
    category: traceability
    summary: "Success criteria and failure modes are broadly covered"
    location: "project-documents/user/tasks/129-tasks.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md"
  - id: F002
    severity: concern
    category: error-handling
    summary: "Post-login account-summary failure is unspecified in `sq auth login`"
    location: "src/squadron/cli/commands/auth.py"
  - id: F003
    severity: note
    category: process
    summary: "`Task 1` precondition may not be completable by the agent"
    location: "project-documents/user/tasks/129-tasks.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md"
  - id: F004
    severity: note
    category: process
    summary: "`Task 12` has no commit checkpoint"
    location: "project-documents/user/tasks/129-tasks.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md"
  - id: F005
    severity: note
    category: dry-principle
    summary: "Models-list marker hardcodes the extra name, escaping the single-source audit"
    location: "src/squadron/cli/commands/models.py"
---

# Review: tasks — slice 129

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [PASS] Success criteria and failure modes are broadly covered

Every Functional, Technical, and Integration success criterion maps to a task: runtime resolver and port (Tasks 5/6/10), extra packaging (Task 3), effort/usage incl. the `effort = "high"` artifact test (Tasks 8/9), discoverability error text / doctor row / models marker / README (Tasks 14–17), interactive login/logout/status (Tasks 20–25), stale-reference grep (Task 11), real-types drift test (Task 12), and default-install gates (Tasks 13/26). Each row of the slice design's Failure Modes table has a producing task and a test. Sequencing respects dependencies (config keys before their consumers, `ExtraRequirement` before doctor/models, `InteractiveLogin` before the CLI commands), with no circular dependencies. No slice NFR is restated that would require a `tests/load/` task, and the design explicitly sets no latency target.

### [CONCERN] Post-login account-summary failure is unspecified in `sq auth login`

The slice design's Failure Modes row for "Hang or failure in `account()` / runtime start during `sq auth status` **or post-login confirmation**" requires that on timeout or SDK error the command "never fail the command", showing validity and source without account details. Task 23 only specifies the success path — "on success re-read `account_summary()` and print `✓ <profile>: authenticated (<email>, <plan>)`" — and its test list omits the `account_summary() -> None` case after a successful `login()`. Since Task 21/22 make `account_summary()` return `None` on timeout/SDK error (and `None` for an invalid strategy), a junior implementer following Task 23 literally would print a success line with empty/`None` account fields, or crash, rather than degrading gracefully as the design mandates. Task 23 should state the `None` branch (print success with validity/source only, no failure) and add a test for it.

### [NOTE] `Task 1` precondition may not be completable by the agent

Task 1 is a blocker for the whole slice ("Must complete before any port work") and requires a real `openai-codex` install, an `OPENAI_API_KEY`, and a machine with no `~/.codex/auth.json` plus a real SDK turn. The task correctly instructs the agent to stop and ask the PM if it cannot arrange this, so the outcome is not fabricated — but reviewers should be aware the slice's first gate is not agent-completable in a typical sandbox. No change strictly required.

### [NOTE] `Task 12` has no commit checkpoint

Every other implementation task ends with a `Commit:` line (per CLAUDE.md "Git add and commit from project root at least once per task"), but Task 12 adds a new test file (`test_sdk_surface.py`) with no commit instruction; its work would only be captured by Task 13's conditional `chore: part A validation fixes`. Add an explicit commit to Task 12 for consistency.

### [NOTE] Models-list marker hardcodes the extra name, escaping the single-source audit

Task 16 specifies the marker literal `(needs [codex] extra)` and simultaneously says "the marker text derives from the hint", while Task 18's single-source test only asserts "the literal install command appears in exactly one `src` module". The extra name `[codex]` therefore ends up encoded both in `runtime.py`'s hint and in `models.py`'s marker, and the audit in Task 18 would not catch the divergence. Either derive the marker entirely from `missing_extra_hint()` (no `[codex]` literal), or extend the Task 18 audit to cover the extra name.

### Run Digest

- Response length: 4498 chars
- Response is newline-free: no
- Tool calls made: 12
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 73248
- Effort: backend default
- Turns: 8
- Tokens — prompt / cached / completion / reasoning: 271277 / 227200 / 20185 / 18211
- Duration: 63.3 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5
