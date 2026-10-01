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
reviewedSha: e2c5cb6a014788a86a91337a46067cc5186b69d3
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 16
turns: 8
promptTokens: 254939
cachedTokens: 207744
completionTokens: 14745
reasoningTokens: 12548
durationSeconds: 56.4
runId: run-20261001-p4-da7c47ac
squadronVersion: 0.17.0
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "`account()` is a new I/O path with failure handling but no hang/timeout handling"
    location: "project-documents/user/slices/129-slice.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md#failure-modes--codex-turn"
  - id: F002
    severity: concern
    category: integration
    summary: "No interface is defined for the \"provider reports the extra missing\" signal used by `sq model list` and `sq doctor`"
    location: "project-documents/user/slices/129-slice.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md#sub-part-b-surfaces"
  - id: F003
    severity: note
    category: under-specification
    summary: "Turn-level timeout constant/default is referenced but not pinned"
    location: "project-documents/user/slices/129-slice.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md#failure-modes--codex-turn"
  - id: F004
    severity: note
    category: documentation
    summary: "Frontmatter `interfaces:` is empty while the doc declares provided interfaces"
    location: "project-documents/user/slices/129-slice.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md:7"
  - id: F005
    severity: pass
    category: architecture-alignment
    summary: "Provider stays within the Agent Provider Layer and keeps credentials self-contained"
    location: "project-documents/user/slices/129-slice.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md#architecture"
---

# Review: slice — slice 129

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [CONCERN] `account()` is a new I/O path with failure handling but no hang/timeout handling

Description: The design adds `AsyncCodex.account()` as a call in two new places — the login flow ("re-read `account()` and print email + plan") and `sq auth status` ("if the strategy is `InteractiveLogin` and valid, append account email + plan"). In both cases the runtime spawns/uses the Codex subprocess. The design enumerates `account()` *failure* ("account() failure in status (log WARNING, still show validity)") but never enumerates *hang* (peer open, no response), *timeout*, or *peer disconnect mid-call* for this path. The slice's own failure-mode rule and the review criteria require each new I/O path to state an explicit handling strategy for hang/timeout/disconnect. `sq auth status` runs per profile and has no stated deadline, so a non-responsive runtime can hang the status command indefinitely. The login flow's D7 timeout covers `handle.wait()` during login, but not the post-login `account()` re-read, and not the status-time call at all. Recommend adding `account()` rows (hang/timeout/disconnect) to the failure-mode table with an explicit bound (e.g. a single timeout constant shared with D7) or an explicit statement that `account()` is best-effort and time-bounded.

### [CONCERN] No interface is defined for the "provider reports the extra missing" signal used by `sq model list` and `sq doctor`

Description: The design requires `sq model list` to mark aliases "whose profile's provider reports the extra missing" and insists this be "Determined through the provider/strategy, not a hard-coded `"openai-oauth"` string." But no contract is specified for how a provider reports this. The `AgentProvider` Protocol exposes only `capabilities` and `validate_credentials()`, and `validate_credentials()` conflates package, binary, and login state (it returns `False` if any is absent), so it cannot distinguish "extra not installed" from "not logged in". Without a defined method/property (e.g. an `extra_available()`/`missing_extra_hint()` on the provider, or a capabilities flag), `models.py` has no non-string-driven way to obtain the marker, and the doctor row's "package importable + version" may duplicate rather than reuse the same source. Recommend naming the provider-side signal (method or capability) that both `model list` and `doctor` consume, so the interface is fixed at design time.

### [NOTE] Turn-level timeout constant/default is referenced but not pinned

Description: The turn-timeout row says "Turn-level timeout (one constant, `--timeout`-style config, defined once) wrapping `thread.run`." The `--timeout` CLI surface defined in API Contracts applies only to `sq auth login`, so it is unclear whether the turn timeout is user-configurable at all, where the constant lives, and what its default is. This is a new I/O path whose bound should be concrete. Not blocking, but the design should state the owning module and default value.

### [NOTE] Frontmatter `interfaces:` is empty while the doc declares provided interfaces

Description: `interfaces: []` in the frontmatter, yet the "Provides to Other Slices" section declares `InteractiveLogin` (a reusable Pattern future OAuth providers implement) and `CodexRuntime` (a reusable resolver). These are genuinely provided interfaces to downstream work; listing them would keep the slice's frontmatter consistent with its body.

### [PASS] Provider stays within the Agent Provider Layer and keeps credentials self-contained

Description: The design keeps the port inside `providers/codex/`, has the provider register even when `openai_codex` is absent so `get_provider` can surface the install hint, defers all SDK imports into functions so the module graph imports without the extra, and stores no credentials of its own (`~/.codex/auth.json` remains the only store). This matches the HLD's "each provider's credential resolution is self-contained" and "adding a new LLM provider should require only implementing the Protocol and registering the provider — no core engine changes." The capability-based dispatch (`isinstance(strategy, InteractiveLogin)`, `applies_effort=True`) and explicit rejection of profile-name/auth-type string comparison also conform to the architecture's multi-provider constraint and slice 128's precedent.

### Run Digest

- Response length: 6040 chars
- Response is newline-free: no
- Tool calls made: 16
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 56849
- Effort: backend default
- Turns: 8
- Tokens — prompt / cached / completion / reasoning: 254939 / 207744 / 14745 / 12548
- Duration: 56.4 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5
