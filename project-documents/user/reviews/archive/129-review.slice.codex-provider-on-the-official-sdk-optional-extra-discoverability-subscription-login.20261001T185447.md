---
docType: review
layer: project
reviewType: slice
slice: codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/129-slice.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md
aiModel: deepseek/deepseek-v4.1-flash
status: complete
dateCreated: 20261001
dateUpdated: 20261001
reviewedSha: b7ea576939f75f75caae3e51adc96702ffd16eae
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 8
turns: 8
promptTokens: 279468
cachedTokens: 222976
completionTokens: 12246
reasoningTokens: 10603
durationSeconds: 46.6
runId: run-20261001-p4-da7c47ac
squadronVersion: 0.17.0
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Failure modes for the Codex review/task turn are not enumerated"
    location: "project-documents/user/slices/129-slice.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md:99"
  - id: F002
    severity: concern
    category: error-handling
    summary: "Empty/failed `final_response` maps to a silent empty Message"
    location: "project-documents/user/slices/129-slice.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md:78"
  - id: F003
    severity: note
    category: documentation
    summary: "Frontmatter `dependencies` omits slice 931"
    location: "project-documents/user/slices/129-slice.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md:8"
  - id: F004
    severity: note
    category: documentation
    summary: "Component-structure comment contradicts the lazy-import note"
    location: "project-documents/user/slices/129-slice.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md:66"
---

# Review: slice — slice 129

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [CONCERN] Failure modes for the Codex review/task turn are not enumerated

The only failure-mode statement is a single bullet: "missing package, missing binary, login timeout, login `success=False` (surface `error`), `account()` failure in status (log WARNING, still show validity)." The login side is covered, but the review/task turn — a new SDK I/O path crossing a subprocess boundary (`AsyncCodex.__aenter__` → `thread_start` → `AsyncThread.run` → `TurnResult`) — has no enumerated failure modes at all. Specifically unaddressed: the SDK subprocess disconnecting/exiting mid-turn, `run` hanging with no time bound, and an SDK error raised outside the `CodexError` hierarchy. The design only offers the generic "wrap-other-exceptions shape," which is exactly the "implicit, not explicit" handling the criteria reject. Slice 931's D12 table is the in-repo precedent for what "explicit and observable" looks like for each new I/O path (failure → behavior → signal → test). Recommend a comparable table for the Codex turn path.

### [CONCERN] Empty/failed `final_response` maps to a silent empty Message

The data flow states `TurnResult.final_response → Message` with no handling for the case where `final_response` is absent or empty. The current implementation returns `result.final_response or ""`, and this design does not specify a replacement behavior for the new SDK surface. That is a silent fallback (violating the project's "Never use silent fallback values" rule) and it reproduces the exact failure class slice 924 was written to fix ("a review the model reasoned out but never emitted"). The design should state what happens when the turn completes with no response content — an explicit error (as `EmptyFinalTurnError` does for the OpenAI path), not an empty message that flows into a review artifact.

### [NOTE] Frontmatter `dependencies` omits slice 931

Frontmatter declares `dependencies: [review-transport-unification-provider-decoupling]` (slice 128), but the "Prerequisites" section lists slice 931 as a prerequisite (`AgentConfig.effort`, `applies_effort` capability, `core/usage.py`). Slice 931 is a hard dependency (D5/D6 consume its effort and usage plumbing), so the two lists disagree. Align the frontmatter with the stated prerequisites.

### [NOTE] Component-structure comment contradicts the lazy-import note

The component table says `login.py` is the "only module besides agent that imports `openai_codex`", but the paragraph two lines later states that `runtime.py` and `login.py` both import `openai_codex` lazily. `runtime.py` is a third importer. Correct the parenthetical so the invariant (which modules touch `openai_codex`, and that all do so lazily) is stated once and accurately — it is the stated basis for the package-absent import behavior.

### Run Digest

- Response length: 4002 chars
- Response is newline-free: no
- Tool calls made: 8
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 46502
- Effort: backend default
- Turns: 8
- Tokens — prompt / cached / completion / reasoning: 279468 / 222976 / 12246 / 10603
- Duration: 46.6 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 4
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 4
- Finding-shaped matches — surviving validation: 4
