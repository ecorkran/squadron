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
reviewedSha: 6804e05e0e427fa966ecb0484024d2c45d4dba78
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 6
turns: 7
promptTokens: 399631
cachedTokens: 306939
cacheWriteTokens: 92682
completionTokens: 11330
durationSeconds: 61.6
costUsd: 0.028002
costBasis: provider
runId: run-20261020-p4-c1b44230
squadronVersion: 0.23.3
findings:
  - id: F001
    severity: concern
    category: scope
    summary: "README defers `/sq:overview` to #247, contradicting the 365 design and the slice plan"
    location: "project-documents/user/slices/366-slice.dispatcher-routing-and-documentation.md:70 (Excluded) and :147-157 (D4)"
  - id: F002
    severity: concern
    category: consistency
    summary: "Architecture amendments are incomplete and one reference is wrong"
    location: "project-documents/user/slices/366-slice.dispatcher-routing-and-documentation.md:142-146"
  - id: F003
    severity: concern
    category: integration
    summary: "Plugin-detection ownership is assigned to a probe the parent architecture never defines"
    location: "project-documents/user/slices/366-slice.dispatcher-routing-and-documentation.md:142-146"
  - id: F004
    severity: concern
    category: consistency
    summary: "Codex dispatcher edit exceeds the architecture's stated delivery"
    location: "project-documents/user/slices/366-slice.dispatcher-routing-and-documentation.md:52-55"
  - id: F005
    severity: concern
    category: proportionality
    summary: "Proportionality: duplicated install commands plus a three-place sync test"
    location: "project-documents/user/slices/366-slice.dispatcher-routing-and-documentation.md:159-175"
  - id: F006
    severity: note
    category: security
    summary: "Install instruction pulls an unpinned branch"
    location: "project-documents/user/slices/366-slice.dispatcher-routing-and-documentation.md:131-133"
  - id: F007
    severity: pass
    category: integration
    summary: "Probe contract entry strings route as written"
    location: "project-documents/user/slices/366-slice.dispatcher-routing-and-documentation.md:236-237"
  - id: F008
    severity: pass
    category: dependencies
    summary: "Dependency direction and scope match the parent"
    location: "project-documents/user/slices/366-slice.dispatcher-routing-and-documentation.md:74-88"
---

# Review: slice — slice 366

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] README defers `/sq:overview` to #247, contradicting the 365 design and the slice plan

The slice plan's 366 entry says "Document both capabilities in the README" and makes only the `/sq:overview` mention conditional on 365 existing. The slice's Excluded list and D4 remove the `/sq:overview` README text and move it to #247. The 365 design (`project-documents/user/slices/365-slice.overview-command.md`, lines 363 and 372) says the opposite: "slice 366 owns the README pass for both capabilities." The plan also dropped the 365 dependency for 366 so that 366 could land first. That is a reason to ship the README text without waiting for 365, not a reason to leave it out. Either the README text stays in 366, or the 365 design and the plan entry are amended to name #247 as the owner. Today the two slice documents disagree about who owns it.

### [CONCERN] Architecture amendments are incomplete and one reference is wrong

D3 says it amends `360-arch` "(Technical Scope item 8)". The architecture has no Technical Scope section. The number refers to the slice's own Included item 8, which reads like an architecture reference. The amendment also misses a conflicting statement. Architectural Principles (`360-arch.document-intelligence.md:56-58`) says: "If the plugin is absent or the graph is missing, squadron reports what to run and stops." D3 deliberately lets a run continue when the graph exists and the plugin is absent, which contradicts that principle. The amendment list covers Flow step 1 (line 127) and Non-Goals (line 423), but not the principle. Name the real architecture locations in D3 and add the principle to the amendment list, so the parent stays a true statement after this slice lands.

### [CONCERN] Plugin-detection ownership is assigned to a probe the parent architecture never defines

The amended Non-Goal reads "plugin detection belongs to the capability probe." The parent architecture does not mention a capability probe, and its Dependencies section (lines 432-441) does not list initiative 440, which is only in this slice's `interfaces`. The probe contract (`capability-probe-contract.md`) also reports `understand_plugin_installed` for `claude-code`. D3 calls the only signal for that, `~/.claude/plugins/installed_plugins.json`, an undocumented internal file that breaks when Claude Code changes it. The fragility therefore moves to 440 and is not recorded there. Add 440 to the architecture's Dependencies, or state in the amendment that the probe owns the detection method and that the method is fragile.

### [CONCERN] Codex dispatcher edit exceeds the architecture's stated delivery

The architecture's Delivery section (`360-arch.document-intelligence.md:397-399`) says capability (a) is "routed by the existing dispatcher" and that adding it takes "three edits to `commands/sq/analysis.md`." D1 adds a Codex dispatcher edit. The slice does say this goes beyond the stated delivery, and the change is small and consistent with the probe's `codex.entry`. The architecture's Delivery text still becomes false after this slice, so either amend it in the same way D3 does, or record the Codex edit as a deliberate expansion in the architecture.

### [CONCERN] Proportionality: duplicated install commands plus a three-place sync test

The install commands are written into the skill file (both copies), the README (D4), and the test module as constants (D5). A test then asserts each string appears in all three places. The slice's own D4 already links the README to the skill file for flows, so the same approach works for install commands. Cut the README copy of the commands and link to the skill file, and keep the sync test only if the commands are still duplicated. Either removal drops one mechanism. The drift test for dispatchers (D5, first paragraph) is the part that guards a real silent failure and should stay.

### [NOTE] Install instruction pulls an unpinned branch

The Codex command pipes a `main` branch script into `bash`, and the Claude command installs whatever `main` currently contains. The architecture pins the plugin at v2.8.1 (`360-arch.document-intelligence.md:70-71`). The output contract is already treated as something that may change, so this is not blocking. Still, the slice should say whether the instruction is intentionally unpinned, or pin a version or commit.

### [PASS] Probe contract entry strings route as written

`/sq:analysis understand` and `/sq:analysis understand concept` match the `claude-code` entry and concept values in `capability-probe-contract.md` (lines 34 and 88-89). D1 keeps `codex.entry` as `analysis-understand`, which also matches the contract.

### [PASS] Dependency direction and scope match the parent

The slice depends on 361 and on the 340 dispatcher and installer conventions, which match the architecture's Dependencies (`[340]`). It adds no pipeline, installer, manifest, or CLI change, and it does not install or fork the plugin, as the architecture's Non-Goals require.

### Run Digest

- Response length: 6362 chars
- Response is newline-free: no
- Tool calls made: 6
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 7
- Tokens — prompt / cached / cache write / completion / reasoning: 399631 / 306939 / 92682 / 11330 / not computed
- Duration: 61.6 s
- Cost: $0.03 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
