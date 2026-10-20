---
docType: review
layer: project
reviewType: slice
slice: dispatcher-routing-and-documentation
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/366-slice.dispatcher-routing-and-documentation.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261020
dateUpdated: 20261020
reviewedSha: 278372f7a4656aeb567be566631fee690173ef27
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
turns: 6
promptTokens: 267856
cachedTokens: 166889
cacheWriteTokens: 100959
completionTokens: 9201
durationSeconds: 47.9
costUsd: 0.027193
costBasis: provider
runId: run-20261020-p4-c1b44230
squadronVersion: 0.23.3
findings:
  - id: F001
    severity: concern
    category: architecture-alignment
    summary: "D3 overrides the architecture's plugin-presence rule without recording an amendment"
    location: "project-documents/user/slices/366-slice.dispatcher-routing-and-documentation.md#D3 — Missing-graph guidance is conditional wording, not plugin detection"
  - id: F002
    severity: concern
    category: dependencies
    summary: "Usage block advertises the `candidates` flow before its slice has landed"
    location: "project-documents/user/slices/366-slice.dispatcher-routing-and-documentation.md:70-76"
  - id: F003
    severity: concern
    category: design-consistency
    summary: "D2 rejects a second flow list, then adds one in the dispatcher usage"
    location: "project-documents/user/slices/366-slice.dispatcher-routing-and-documentation.md#D2 — Pass the flow argument through without interpreting it"
  - id: F004
    severity: note
    category: architecture-alignment
    summary: "Codex dispatcher edit is broader than the architecture's stated delivery"
    location: "project-documents/user/slices/366-slice.dispatcher-routing-and-documentation.md#D1 — Route Codex as well as Claude"
  - id: F005
    severity: note
    category: proportionality
    summary: "README subsection restates skill content that will drift"
    location: "project-documents/user/slices/366-slice.dispatcher-routing-and-documentation.md#D4 — README documents capability (a) only"
  - id: F006
    severity: pass
    category: architecture-alignment
    summary: "Routing, scope, and integration match the parent and the probe contract"
    location: "project-documents/user/slices/366-slice.dispatcher-routing-and-documentation.md#Integration Points"
---

# Review: slice — slice 366

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] D3 overrides the architecture's plugin-presence rule without recording an amendment

The parent architecture states the plugin-presence rule three ways. Principle "Graph is an input, not a dependency" says "If the plugin is absent or the graph is missing, squadron reports what to run and stops." Flow step 1 says "Verify the plugin is installed and `knowledge-graph.json` exists." Non-Goals says "The skill detects absence and instructs." D3 instead states that "a missing plugin with a graph present is not an error" and that the skill will not detect plugin installation. The reasoning is sound: `installed_plugins.json` is an undocumented internal file, and the probe contract already owns `understand_plugin_installed`. But the parent is still the contract this slice is reviewed against, and it says the opposite. Either the architecture's Preconditions and principle should be amended to match D3 (the graph is the true input, and the plugin is needed only to build it), or D3 should be reworked. As written, the slice and its parent disagree and nothing records which one governs.

### [CONCERN] Usage block advertises the `candidates` flow before its slice has landed

The Dependencies section lists only 361 in frontmatter and says 366 "does not wait on 364". But 364 (Initiative Candidates) is in progress, and the slice adds `candidates` to the usage line and the `Valid skills` line (lines 174–177). Until 364 lands, `/sq:analysis understand candidates` routes to a flow the skill does not implement, so the skill's own "unrecognized" message will fire on a flow the dispatcher advertised. Success Criteria at line 205–206 also requires `candidates` to reach its flow. The "does not wait" reasoning holds for routing, since arguments pass through, but not for the advertised surface or the success criteria. The design should either gate the `candidates` entry on 364 or state which flows are advertised at merge time, and list 364 as a soft dependency in frontmatter.

### [CONCERN] D2 rejects a second flow list, then adds one in the dispatcher usage

D2 rejects validating flows in the dispatcher because it "would add a second list to keep in sync with the skill." The same design then lists the flows in the dispatcher's usage line and `Valid skills` block (`[comprehension|concept|candidates]`, line 177), and the dispatcher text itself says it "lists the flows for discoverability." That is the same second list D2 rejects, and it is the drift risk the Concern above describes. Either drop the flow names from the dispatcher and point to the skill, or accept the list and say explicitly that the D5 drift test does not cover it, so the parity claim in D2 is not overstated.

### [NOTE] Codex dispatcher edit is broader than the architecture's stated delivery

The parent's Delivery section says capability (a) needs "three edits to `commands/sq/analysis.md`" and nothing else. D1 adds three more edits to `commands/agents/sq-analysis/SKILL.md`. That is consistent with the Codex twin convention from the 925 amendment, and the probe contract's `codex.entry` is unchanged, so this is not a conflict. The architecture's Delivery paragraph is now inaccurate, though. Update it to mention the Codex twin so the next reader does not expect a Claude-only change.

### [NOTE] README subsection restates skill content that will drift

D4 asks the README to list the three flows, the `jq` requirement, and the Codex form. The flow list and prerequisite are already defined in the understand skill and in the probe contract. The README can point to the skill and state only the plugin prerequisite and install commands, which the architecture requires. This keeps the README to the content that must be stable for users and removes one copy that would need updating every time a flow changes.

### [PASS] Routing, scope, and integration match the parent and the probe contract

The `/sq:analysis understand` and `/sq:analysis understand concept` routes match `claude-code.entry` and `claude-code.concept` in `capability-probe-contract.md`, and the Shipping Order (366 before the probe) is respected. The slice keeps the direct entries and the existing installer unchanged. It also respects the architecture's boundary that squadron never installs or drives the marketplace plugin, and it keeps the missing-graph stop with the `/understand` command as the architecture requires.

### Run Digest

- Response length: 5728 chars
- Response is newline-free: no
- Tool calls made: 5
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 6
- Tokens — prompt / cached / cache write / completion / reasoning: 267856 / 166889 / 100959 / 9201 / not computed
- Duration: 47.9 s
- Cost: $0.03 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
