---
docType: review
reviewType: arch
slice: review-provider-model-selection
project: squadron
verdict: PASS
dateCreated: 20260321
dateUpdated: 20260321
---

# Review: arch — slice 119

**Verdict:** PASS
**Model:** opus

## Findings

### [PASS] — Correct use of existing provider infrastructure

The slice reuses `ProviderProfile`, `get_profile()`, `resolve_auth_strategy()`, and `AsyncOpenAI` from completed slices 111–114 rather than building parallel provider abstractions. This follows the architecture's multi-provider design where providers implement shared Protocols and the core engine remains provider-agnostic. The non-SDK path creates an `AsyncOpenAI` client from profile credentials — exactly the pattern `OpenAICompatibleProvider` already uses.

### [PASS] — SDK path preservation

The design wraps rather than replaces `run_review()`, delegating to the existing SDK path when `profile="sdk"`. This respects the architecture's position that SDK agents are the primary execution path and avoids regression risk on the most used flow.

### [PASS] — Clean dependency direction

Dependencies flow correctly: CLI → `review_client.py` → provider infrastructure (profiles, auth) → external SDKs. No reverse dependencies introduced. The slice consumes slices 105, 113, 114, 118 — all marked complete in the slice plan.

### [PASS] — Scope is well-bounded

Excluded items (Anthropic API provider, Ensemble Review, MCP exposure, tool use for non-SDK providers) are all correctly identified as belonging to other slices (122, 130, 127 respectively). The relationship to ADP (140-arch) is explicitly documented and clearly distinguished.

### [CONCERN] — Bypasses Agent Protocol for non-SDK reviews

The architecture document defines a unified `Agent` Protocol and states: **"the core engine never depends on provider internals."** The non-SDK review path in this slice directly creates an `AsyncOpenAI` client and calls `chat.completions.create()` — bypassing the `Agent` Protocol, `AgentProvider`, agent registry, and message bus entirely. 

This is pragmatic (reviews are one-shot request/response, not agent lifecycle), and the design explicitly justifies it: *"Avoids the Agent Protocol overhead — reviews don't need agent lifecycle, registry, message bus."* However, when Ensemble Review (130) arrives and needs to fan-out reviews to multiple providers via the message bus, this non-Protocol path may need to be retrofitted. The slice acknowledges this by listing 130 as a consumer, but doesn't specify whether 130 will use `run_review_with_profile()` directly or route through agents.

**Recommendation:** Acceptable for now. Document in the slice that Ensemble Review (130) may need to decide whether to wrap `run_review_with_profile()` in a temporary agent or use it as a direct function call outside the agent topology.

### [CONCERN] — CLI/Slash-Command/MCP parity partially addressed

The slice plan entry (line 67 of 100-slices) states: *"CLI/slash-command/MCP parity applies."* The slice design covers CLI (`--profile` flag) and slash commands (documentation updates), but explicitly excludes MCP-exposed review execution (slice 127). The memory file `feedback_interface_parity.md` reinforces that CLI, slash commands, and MCP must produce identical results and artifacts.

While MCP review exposure is correctly deferred to slice 127, the slice should note that when 127 ships, it must support the `profile` parameter to maintain parity. The current design doesn't mention this interface contract.

**Recommendation:** Add a brief note in the "Excluded" section or "Known Limitations" clarifying that MCP parity for `--profile` is a requirement for slice 127.

### [CONCERN] — Config key naming inconsistency with slice plan

The slice plan (100-slices, line 67) references `default_review_provider` and `default_review_model` as config keys. The slice design defines `default_review_profile` instead — a single key replacing two. This is arguably cleaner, but the naming divergence between the slice plan and the slice design could cause confusion.

**Recommendation:** Update the slice plan entry to reflect the actual config key name (`default_review_profile`) or document in the slice why the single key supersedes the two originally planned.

### [PASS] — User-customizable templates are well-designed

The two-directory template loading (built-in + `~/.config/squadron/templates/`) with name-based override is a clean extension mechanism. It doesn't conflict with any architectural boundary — templates are a feature of the review subsystem, not the core engine or provider layer.

### [PASS] — Testing strategy is appropriate

The testing approach (unit tests for profile resolution and model inference, mocked non-SDK execution, tmp_path-based template loading, SDK regression via existing tests) is proportional to the change scope and covers the key integration points.
