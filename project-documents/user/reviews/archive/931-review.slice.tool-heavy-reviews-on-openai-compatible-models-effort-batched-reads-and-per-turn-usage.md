---
docType: review
layer: project
reviewType: slice
slice: tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage
targetKind: slice
rulesSource: project
project: squadron
verdict: PASS
verdictSource: stated
sourceDocument: project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md
aiModel: z-ai/glm-5.3-flash
status: complete
dateCreated: 20260930
dateUpdated: 20260930
reviewedSha: 8920f79b40247fff4fd908bbd418b7c6612a98c1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 50
turns: 20
promptTokens: 2343136
cachedTokens: 1537024
completionTokens: 83523
reasoningTokens: 79466
durationSeconds: 1273.3
squadronVersion: 0.16.0
findings:
  - id: F001
    severity: pass
    category: scope
    summary: "Scope alignment with the architecture's initiative boundary is honest and well-argued"
    location: "project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md#initiative-fit"
  - id: F002
    severity: pass
    category: architecture-boundary
    summary: "Dependency directions are correct and the claims verify against the real import graph"
    location: "project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md#dependency-direction"
  - id: F003
    severity: pass
    category: error-handling
    summary: "D12 enumerates failure modes for every new I/O path with explicit signals and tests — no TBDs"
    location: "project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md#d12-failure-modes-and-their-signals"
  - id: F004
    severity: pass
    category: integration
    summary: "Integration points match what the consuming and providing slices expect"
    location: "project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md#component-structure"
  - id: F005
    severity: pass
    category: nfr
    summary: "NFR handling is correct: the parent architecture states none, and the one applicable rule is restated with specifics"
    location: "project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md#special-considerations"
  - id: F006
    severity: note
    category: scope
    summary: "The bundle rationale slightly overstates part B's shared code"
    location: "project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md#why-one-slice"
  - id: F007
    severity: note
    category: nfr
    summary: "The project guide's load-test tier for network paths is not addressed"
    location: "project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md#special-considerations"
  - id: F008
    severity: note
    category: documentation
    summary: "SDK version citation is stale relative to the resolved lock"
    location: "project-documents/user/slices/931-slice.tool-heavy-reviews-on-openai-compatible-models-effort-batched-reads-and-per-turn-usage.md#prerequisites"
---

# Review: slice — slice 931

**Verdict:** PASS
**Model:** z-ai/glm-5.3-flash

## Findings

### [PASS] Scope alignment with the architecture's initiative boundary is honest and well-argued

Each part maps to a 900-arch scope line ("Operational: configuration improvements that span subsystems", "Tech debt: restructured for performance", "Bug fixes"), and the design explicitly argues against the excluded "new features or capabilities" reading rather than ignoring it. Part A (effort) is flagged as the weakest mapping and defended in detail ("the fix" vs. "the control"), following the 924 precedent. Out-of-scope items (CLI flag, per-step key, Codex effort, SDK usage, other AgentConfig sites) are enumerated, matching the slice plan's entry.

### [PASS] Dependency directions are correct and the claims verify against the real import graph

The design's stated graph matches reality: `review/` imports only provider shared modules and no concrete provider package; the new edges (`providers/errors.py` → `core.usage`, `providers/openai` → `core.usage`) exist and cannot cycle because `core/usage.py` imports only the standard library. The design also reports the pre-existing package-level `core` ↔ `providers` coupling honestly rather than claiming a clean layering, and enforces both invariants as acceptance-criteria greps.

### [PASS] D12 enumerates failure modes for every new I/O path with explicit signals and tests — no TBDs

Connect failure, mid-stream disconnect (including the verified SDK gap that raw `httpx` errors escape unconverted), stream stall (bounded by the verified SDK default `Timeout(connect=5, read=600)`), missing usage chunk, malformed usage fields, 400 rejections, batch-budget cutoff, all-fail batches, hung reads, and non-appliable effort each have a behavior, a log signal, and a named test. "None new / unchanged behavior" appears only where it is justified (the hung-read row), not as a dodge. No silent fallbacks anywhere: unreported fields stay `None`/absent, never 0, and malformed accounting degrades to `None` with a WARNING rather than failing the review.

### [PASS] Integration points match what the consuming and providing slices expect

All six credential call sites listed for the `profile_credentials` switch exist and were switched; the profile-less daemon path (`server/routes/agents.py`, credentials from request bodies) behaves as the design states; 195's `format_provider_failure_markdown` exists and reads off `ProviderError`, so the new telemetry rides the existing channel; 924's `applies_output_budget`/`max_output_tokens` pattern is followed exactly; the cross-tool frontmatter addition is mitigated (cf tolerates unknown keys) and validated in walkthrough step 11. Gemini's open `stream_options` fact is decoupled from the merge via `sends_stream_usage = False`, so no integration point waits on an unverified external fact.

### [PASS] NFR handling is correct: the parent architecture states none, and the one applicable rule is restated with specifics

The 900 architecture defines no NFRs, and the design says so explicitly rather than inventing targets. The one NFR the slice touches — the project rule that synchronous work inside `async def` must complete in under 1 ms — is restated with the specific mechanism: per-chunk usage reading is attribute access, and batched reads run entirely inside the one existing `asyncio.to_thread` call, so a hung read blocks a worker thread, not the event loop.

### [NOTE] The bundle rationale slightly overstates part B's shared code

The justification says "All three edit `_stream_turn`/`_run_agentic_loop` and the same `ReviewResult` rendering," but the component table for B lists only `file_tools.py`, `limits.py`, and `guidance.py` — none of those functions — and the same document states "B and A share no code" and "B shares no code with A or C." The design self-corrects elsewhere (B is the cuttable part whose inclusion rests on the PM decision and shared fixture work), so the cut-out path is sound, but the "shared work" sentence should not be read as a code-level justification for B.

### [NOTE] The project guide's load-test tier for network paths is not addressed

`python.md`'s testing tier states that code on network/concurrency paths requires at least one load test, CI-gated. This slice modifies per-chunk processing inside a network streaming loop. The added work is trivial (attribute access per chunk, argued under the 1 ms rule), and I could not verify whether prior network-path slices (e.g., 262, 924, 927) carried load tests or whether the rule is enforced for this path in practice — so this is informational, not a blocking concern, but a sentence stating why the tier does or does not apply would close the gap.

### [NOTE] SDK version citation is stale relative to the resolved lock

The design cites `claude-agent-sdk` 0.2.160, but the resolved lock and the pyproject floor are 0.2.162. Every capability the design attributes to the SDK (`effort` with `low|medium|high|xhigh|max`, `thinking={"type": "disabled"}`) is present in the resolved version, so this is harmless drift; `openai` 2.24.0 matches exactly.

### Run Digest

- Response length: 7634 chars
- Response is newline-free: no
- Tool calls made: 50
- Tool calls failed: 1
- Stop reason: stop
- Output budget: 128000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 344056
- Effort: backend default
- Turns: 20
- Tokens — prompt / cached / completion / reasoning: 2343136 / 1537024 / 83523 / 79466
- Duration: 1273.3 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
