---
docType: review
layer: project
reviewType: slice
slice: codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login
project: squadron
verdict: CONCERNS
verdictSource: derived
sourceDocument: project-documents/user/slices/129-slice.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md
aiModel: deepseek/deepseek-v4.1-flash
status: complete
dateCreated: 20261001
dateUpdated: 20261001
reviewedSha: 06cc719867832dce778ffe4f33f6835dda81cd92
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 13
turns: 9
promptTokens: 297218
cachedTokens: 248448
completionTokens: 18369
reasoningTokens: 15964
durationSeconds: 68.8
runId: run-20261001-p4-da7c47ac
squadronVersion: 0.17.0
findings:
  - id: F001
    severity: concern
    category: nfr-coverage
    summary: "New subprocess-spawning runtime path introduces no startup/latency consideration or target"
    location: "project-documents/user/slices/129-slice.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md#data-flow"
  - id: F002
    severity: note
    category: hidden-dependency
    summary: "`sq doctor` Codex row reaches the runtime resolver directly, bypassing the abstraction the slice just introduces"
    location: "project-documents/user/slices/129-slice.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md#sub-part-b-surfaces"
  - id: F003
    severity: note
    category: scope
    summary: "Interactive-login capability is net-new relative to the architecture's auth model"
    location: "project-documents/user/slices/129-slice.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md#architecture"
  - id: F004
    severity: note
    category: error-handling
    summary: "Deferred `OPENAI_API_KEY` fallback remains an unverified silent-fallback path"
    location: "project-documents/user/slices/129-slice.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md#special-considerations"
  - id: F005
    severity: pass
    category: architectural-alignment
    summary: "Provider/protocol alignment and credential containment match the architecture"
    location: "project-documents/user/slices/129-slice.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md#integration-points"
---

# Review: slice — slice 129

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [CONCERN] New subprocess-spawning runtime path introduces no startup/latency consideration or target

Description: The parent architecture states an explicit initialization-cost constraint for the agent-execution layer — "each `ClaudeSDKClient` instance spawns a CLI subprocess with 20-30s initialization time; design for warm pool / instance reuse rather than per-message creation" and, under "SDK Agent Design Considerations," repeats the ~20-30s startup cost and warm-pool guidance. This slice adds a new subprocess-spawning runtime on the agent-creation path: `create_agent` → `resolve_codex_runtime()` → `CodexAgent` builds `CodexConfig(codex_bin=runtime.path)` → `AsyncCodex.__aenter__` (a Codex runtime process) → `thread_start`/`thread.run`. The doc treats that startup as opaque and states no startup/latency expectation or reuse/one-shot tradeoff for the new runtime, and never references the parent architecture's initialization-cost guidance. Per the review criterion ("If the slice touches a path with an NFR stated in the parent architecture document, the NFR is restated in this slice doc with the specific target"), the design should either restate the budget the parent sets (or explicitly note that the parent's warm-pool consideration does not apply to the once-per-agent Codex runtime) rather than leave it implicit. Note the slice's own `codex.turn_timeout_s`/`login_timeout_s`/`account_timeout_s` cover hang bounds only, not startup cost.

### [NOTE] `sq doctor` Codex row reaches the runtime resolver directly, bypassing the abstraction the slice just introduces

Description: D9 introduces `ExtraRequirement` (in `providers/base.py`, `missing_extra_hint()`) specifically so callers can ask "is the optional dependency missing, and what is the install command" without knowing provider identity, and `sq model list` is wired through `isinstance(provider, ExtraRequirement)`. The `sq doctor` `codex provider` row, by contrast, is stated to "call the Codex runtime resolver directly, since that row is Codex-specific by design." That leaves two mechanisms producing the same information and gives the CLI a concrete `providers.codex.runtime` import. This is defensible (the row is intentionally Codex-specific and `doctor` already has a `codex CLI` row), but it is worth naming explicitly as an accepted exception so future optional-dependency rows don't copy the direct-import pattern and erode the `ExtraRequirement` abstraction.

### [NOTE] Interactive-login capability is net-new relative to the architecture's auth model

Description: The parent architecture's authentication section scopes auth as per-provider and self-contained ("Squadron does not attempt to unify authentication. Each provider's credential resolution is self-contained") and lists OpenAI as API-key only; it does not describe CLI-driven interactive login. Part C adds a shared `InteractiveLogin` Protocol in `providers/auth.py` plus `login`/`logout`/`status` CLI flows and a device-code path. This is authorized by the slice plan (parent), and D3's ISP reasoning (a separate capability protocol rather than new `AuthStrategy` methods) keeps it from forcing API-key strategies to stub methods — so it does not violate the "no unified auth" boundary. Flagging it only because the capability is not traceable to the architecture document under review; the design would be stronger if it briefly reconciled Part C with the architecture's per-provider auth statement.

### [NOTE] Deferred `OPENAI_API_KEY` fallback remains an unverified silent-fallback path

Description: Special Considerations notes a pre-existing `OPENAI_API_KEY` fallback in `OAuthFileStrategy` whose behavior "has not been verified," and defers the question (verify during smoke test; file an issue if it does not work). This is an existing concern rather than something this slice introduces, and the project rule against silent fallbacks makes it worth a concrete disposition rather than an out-of-band issue: the slice's success criteria already run with the key unset, but no criterion covers "key set but account not logged in" to prove the fallback is not a silent alternative auth path. A one-line acceptance criterion or an explicit "documented, intended fallback" statement would close it.

### [PASS] Provider/protocol alignment and credential containment match the architecture

Description: The port keeps the Codex provider behind the shared Protocols, registers it so `get_provider("openai-oauth")` resolves, maps `TurnResult.final_response` to squadron `Message` objects, applies effort/usage via the slice-128/931 capability plumbing, and explicitly keeps Squadron free of any token store (`~/.codex/auth.json` owned by the Codex runtime). These match the architecture's provider-implementation requirements ("Implement AgentProvider Protocol… Produce agents that implement Agent Protocol… Handle its own credential resolution… Map its native response format to squadron Message objects") and its "core engine never depends on provider internals" invariant. `InteractiveLogin`/`ExtraRequirement` are additive protocols in `providers/base.py` and `providers/auth.py`, not core-engine changes, consistent with "Adding a new provider should require only implementing the Protocol and registering the provider."

### Run Digest

- Response length: 6817 chars
- Response is newline-free: no
- Tool calls made: 13
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 71664
- Effort: backend default
- Turns: 9
- Tokens — prompt / cached / completion / reasoning: 297218 / 248448 / 18369 / 15964
- Duration: 68.8 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5

### Raw Response

## Summary

The slice is well-aligned with the multi-provider architecture in the broad strokes: it ports the Codex provider to an official SDK while keeping it behind the `AgentProvider`/`Agent` Protocols, keeps credential resolution self-contained (no squadron token store), preserves lazy-import so the provider still registers and fails with an actionable hint, and enumerates failure modes for the new turn/login I/O paths. I did not find a boundary violation in the core-engine/provider split or an incorrect dependency direction. I do flag one restated-goal/NFR gap and a few smaller consistency observations.

## Findings

### [CONCERN] New subprocess-spawning runtime path introduces no startup/latency consideration or target
category: nfr-coverage
location: project-documents/user/slices/129-slice.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md#data-flow
Description: The parent architecture states an explicit initialization-cost constraint for the agent-execution layer — "each `ClaudeSDKClient` instance spawns a CLI subprocess with 20-30s initialization time; design for warm pool / instance reuse rather than per-message creation" and, under "SDK Agent Design Considerations," repeats the ~20-30s startup cost and warm-pool guidance. This slice adds a new subprocess-spawning runtime on the agent-creation path: `create_agent` → `resolve_codex_runtime()` → `CodexAgent` builds `CodexConfig(codex_bin=runtime.path)` → `AsyncCodex.__aenter__` (a Codex runtime process) → `thread_start`/`thread.run`. The doc treats that startup as opaque and states no startup/latency expectation or reuse/one-shot tradeoff for the new runtime, and never references the parent architecture's initialization-cost guidance. Per the review criterion ("If the slice touches a path with an NFR stated in the parent architecture document, the NFR is restated in this slice doc with the specific target"), the design should either restate the budget the parent sets (or explicitly note that the parent's warm-pool consideration does not apply to the once-per-agent Codex runtime) rather than leave it implicit. Note the slice's own `codex.turn_timeout_s`/`login_timeout_s`/`account_timeout_s` cover hang bounds only, not startup cost.

### [NOTE] `sq doctor` Codex row reaches the runtime resolver directly, bypassing the abstraction the slice just introduces
category: hidden-dependency
location: project-documents/user/slices/129-slice.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md#sub-part-b-surfaces
Description: D9 introduces `ExtraRequirement` (in `providers/base.py`, `missing_extra_hint()`) specifically so callers can ask "is the optional dependency missing, and what is the install command" without knowing provider identity, and `sq model list` is wired through `isinstance(provider, ExtraRequirement)`. The `sq doctor` `codex provider` row, by contrast, is stated to "call the Codex runtime resolver directly, since that row is Codex-specific by design." That leaves two mechanisms producing the same information and gives the CLI a concrete `providers.codex.runtime` import. This is defensible (the row is intentionally Codex-specific and `doctor` already has a `codex CLI` row), but it is worth naming explicitly as an accepted exception so future optional-dependency rows don't copy the direct-import pattern and erode the `ExtraRequirement` abstraction.

### [NOTE] Interactive-login capability is net-new relative to the architecture's auth model
category: scope
location: project-documents/user/slices/129-slice.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md#architecture
Description: The parent architecture's authentication section scopes auth as per-provider and self-contained ("Squadron does not attempt to unify authentication. Each provider's credential resolution is self-contained") and lists OpenAI as API-key only; it does not describe CLI-driven interactive login. Part C adds a shared `InteractiveLogin` Protocol in `providers/auth.py` plus `login`/`logout`/`status` CLI flows and a device-code path. This is authorized by the slice plan (parent), and D3's ISP reasoning (a separate capability protocol rather than new `AuthStrategy` methods) keeps it from forcing API-key strategies to stub methods — so it does not violate the "no unified auth" boundary. Flagging it only because the capability is not traceable to the architecture document under review; the design would be stronger if it briefly reconciled Part C with the architecture's per-provider auth statement.

### [NOTE] Deferred `OPENAI_API_KEY` fallback remains an unverified silent-fallback path
category: error-handling
location: project-documents/user/slices/129-slice.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md#special-considerations
Description: Special Considerations notes a pre-existing `OPENAI_API_KEY` fallback in `OAuthFileStrategy` whose behavior "has not been verified," and defers the question (verify during smoke test; file an issue if it does not work). This is an existing concern rather than something this slice introduces, and the project rule against silent fallbacks makes it worth a concrete disposition rather than an out-of-band issue: the slice's success criteria already run with the key unset, but no criterion covers "key set but account not logged in" to prove the fallback is not a silent alternative auth path. A one-line acceptance criterion or an explicit "documented, intended fallback" statement would close it.

### [PASS] Provider/protocol alignment and credential containment match the architecture
category: architectural-alignment
location: project-documents/user/slices/129-slice.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md#integration-points
Description: The port keeps the Codex provider behind the shared Protocols, registers it so `get_provider("openai-oauth")` resolves, maps `TurnResult.final_response` to squadron `Message` objects, applies effort/usage via the slice-128/931 capability plumbing, and explicitly keeps Squadron free of any token store (`~/.codex/auth.json` owned by the Codex runtime). These match the architecture's provider-implementation requirements ("Implement AgentProvider Protocol… Produce agents that implement Agent Protocol… Handle its own credential resolution… Map its native response format to squadron Message objects") and its "core engine never depends on provider internals" invariant. `InteractiveLogin`/`ExtraRequirement` are additive protocols in `providers/base.py` and `providers/auth.py`, not core-engine changes, consistent with "Adding a new provider should require only implementing the Protocol and registering the provider."
