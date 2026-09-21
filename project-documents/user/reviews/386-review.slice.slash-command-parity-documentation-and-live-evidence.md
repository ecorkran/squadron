---
docType: review
layer: project
reviewType: slice
slice: slash-command-parity-documentation-and-live-evidence
targetKind: slice
rulesSource: project
project: squadron
verdict: PASS
sourceDocument: project-documents/user/slices/386-slice.slash-command-parity-documentation-and-live-evidence.md
aiModel: deepseek/deepseek-v4-pro
status: complete
responseStatus: addressed
dateCreated: 20260919
dateUpdated: 20260919
reviewedSha: 13bd126913b9f7c002b4235964a300e77eaaef1c
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
findings:
  - id: F001
    severity: pass
    category: uncategorized
    summary: "D1 verbatim pass-through enforces the \"CLI is the contract\" parity principle"
    location: "project-documents/user/slices/386-slice.slash-command-parity-documentation-and-live-evidence.md#technical-decisions"
  - id: F002
    severity: pass
    category: uncategorized
    summary: "D3 restates \"never surprise the operator\" for an agent transport that can act"
    location: "project-documents/user/slices/386-slice.slash-command-parity-documentation-and-live-evidence.md#d3--host-writes-through-an-agent-transport-run-once-never-remediate"
  - id: F003
    severity: pass
    category: uncategorized
    summary: "D2 parity-testing strategy is appropriate for a prompt-based transport"
    location: "project-documents/user/slices/386-slice.slash-command-parity-documentation-and-live-evidence.md#d2--parity-is-tested-as-surface-agreement-plus-one-deterministic-live-comparison"
  - id: F004
    severity: pass
    category: uncategorized
    summary: "Live-run write sequencing respects the architecture's \"reads before writes, writes are explicit\" principle"
    location: "project-documents/user/slices/386-slice.slash-command-parity-documentation-and-live-evidence.md#d6--the-live-run-is-on-this-slices-own-branch-and-lands-the-way-its-predecessors-did"
  - id: F005
    severity: note
    category: uncategorized
    summary: "Dependencies frontmatter lists 382/384/385; \"Consumes\" section also references 381 and 383"
    location: "project-documents/user/slices/386-slice.slash-command-parity-documentation-and-live-evidence.md:29-36"
  - id: F006
    severity: note
    category: uncategorized
    summary: "D4 profile-inside-session handling is documented-from-observation rather than designed"
    location: "project-documents/user/slices/386-slice.slash-command-parity-documentation-and-live-evidence.md#d4--provider-profile-inside-a-session-is-documented-from-observation-not-decided-here"
---

# Review: slice — slice 0

**Verdict:** PASS
**Model:** deepseek/deepseek-v4-pro

## Findings

### [PASS] D1 verbatim pass-through enforces the "CLI is the contract" parity principle

The architecture states: *"Whatever `sq review pr` accepts, the `/sq:review` slash command … accept identically, producing the same artifact. The CLI is the contract; the others are transports."* D1 encodes this directly: the delegation line carries the remainder placeholder with nothing appended, no injected flags, and no number shorthand that rewrites the argument string. Parity holds by construction for every flag, including future ones, rather than requiring a manual update checklist. The section also correctly calls out why the existing `-v` shorthand is deliberately omitted for `pr` (the bare number is already a valid PR target) — preventing a latent drift hazard.

### [PASS] D3 restates "never surprise the operator" for an agent transport that can act

The architecture's rule is: *"Squadron never writes to a PR unless asked on that invocation."* Through a slash command a second actor (the session) could ask. D3 closes that gap with four explicit prompt instructions — `--post` only when the operator typed it, a write command runs once, printed remediation is shown and not executed, and `--dry-run` is never substituted. The design is honest that prompt instructions aren't enforceable like code paths, accepts that the CLI's own refusals still hold, and positions the instructions as closing the gap between "the CLI refused" and "the session worked around it." This directly implements the architectural principle for the agent-transport context.

### [PASS] D2 parity-testing strategy is appropriate for a prompt-based transport

Because a command file cannot be executed by pytest, the design correctly identifies the two ways a prompt transport drifts — delegation-line mutation and described-surface drift — and tests both mechanically (set-equality of registered Click options vs. `--flag` tokens in the section; delegation command with remainder placeholder and nothing appended). The live byte-identical comparison targets `sq pr show --json` (deterministic via `_render_json`, shaped for this in 381), and the structural comparison for model output is honest about what can be identical (frontmatter keys, deterministic fields) vs. what cannot (prose, verdict). The test is written so extending coverage to pre-existing subcommands is a list entry, not a rewrite. This satisfies the architecture's "Interface parity" principle within the constraints of the transport.

### [PASS] Live-run write sequencing respects the architecture's "reads before writes, writes are explicit" principle

The D6 sequence runs every write (create, post) through `--dry-run` first, as the architecture requires: *"each with a dry-run form that prints what would be sent."* The landing strategy — local `--no-ff` merge into `squadron-pr`, with the live PR as evidence rather than the merge route — matches every predecessor slice's pattern. The architecture's "Never surprise the operator" is respected: each step is an explicit operator command, preceded by its dry-run. The post-PR-merge state (marking the PR merged) is correctly noted as the natural final state.

### [NOTE] Dependencies frontmatter lists 382/384/385; "Consumes" section also references 381 and 383

The frontmatter `dependencies: [382, 384, 385]` and the Prerequisites section ("382, 384, 385 merged into `squadron-pr`") list three slices, while "Consumes from Other Slices" correctly enumerates all five (381–385). This is functionally correct — 381 and 383 are consumed but were likely merged earlier and aren't blocking prerequisites — but readers tracing the dependency graph from frontmatter alone may miss that 381's `sq pr show --json` and 383's `--reviews-dir`/`review.external_reviews_dir` are required interfaces. No architectural violation; a documentation-consistency note.

### [NOTE] D4 profile-inside-session handling is documented-from-observation rather than designed

The architecture says *"The protocol must not leak `gh`-specific shapes"* and the adapter boundary is git/host, not provider profiles, so the profile issue sits outside the architecture's direct scope. D4 correctly refuses to inject a profile flag (consistent with D1's verbatim rule) and instead commits to observing what happens with the default profile inside a session and documenting the result. If the default fails with an unhelpful message, the design says that is a CLI defect, logged as an issue — not patched over in the command file. This is a defensible position, but the slice's success criterion ("The observed behavior of the default profile inside a session is documented") creates a documentation dependency on a runtime observation whose outcome is unknown at design time. The fallback plan (log as CLI defect) is adequate.

## Response

PASS, four pass findings and two notes. One note changed the design; one did not.

### [NOTE] F005 — dependencies frontmatter omitted 381 and 383

Fixed. `dependencies` is now `[381, 382, 383, 384, 385]`, and Prerequisites says why the two
additions are there: 381's `sq pr show --json` and doctor checks, and 383's `--reviews-dir` and
`review.external_reviews_dir`, are consumed directly. The slice plan entry's own dependency list
(382, 384, 385) is unchanged — it names what gates the slice, and both additions landed before
those did.

### [NOTE] F006 — D4 documents from observation rather than deciding

No change. The finding calls the position defensible and the fallback adequate, and it is the
only honest option at design time: whether the default `sdk` profile runs inside a session is a
fact about the runtime, not a choice the design can make. D4 orders the observation before the
documentation work (Implementation Notes step 3) so nothing is written against an unknown.

### Run Digest

- Response length: 6511 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 16480
- `## Summary` located: no
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6

### Raw Response

## Summary

The slice design for **386 — Slash-Command Parity, Documentation, and Live Evidence** is well-aligned with architecture **380 — Pull Request Workflow**. Every technical decision (D1–D6) directly addresses an architectural principle: D1 maps to "Interface parity," D3 maps to "Never surprise the operator," D2 provides appropriate parity testing for a prompt-based transport incapable of pytest execution. The scope matches the architecture's anticipated slice exactly — command files, documentation, and a recorded live run, with no capability addition. I found no architectural boundary violations, no dependency-direction errors, and no scope creep. Two minor documentation-consistency notes follow.

## Findings

### [PASS] D1 verbatim pass-through enforces the "CLI is the contract" parity principle
location: project-documents/user/slices/386-slice.slash-command-parity-documentation-and-live-evidence.md#technical-decisions

The architecture states: *"Whatever `sq review pr` accepts, the `/sq:review` slash command … accept identically, producing the same artifact. The CLI is the contract; the others are transports."* D1 encodes this directly: the delegation line carries the remainder placeholder with nothing appended, no injected flags, and no number shorthand that rewrites the argument string. Parity holds by construction for every flag, including future ones, rather than requiring a manual update checklist. The section also correctly calls out why the existing `-v` shorthand is deliberately omitted for `pr` (the bare number is already a valid PR target) — preventing a latent drift hazard.

### [PASS] D3 restates "never surprise the operator" for an agent transport that can act
location: project-documents/user/slices/386-slice.slash-command-parity-documentation-and-live-evidence.md#d3--host-writes-through-an-agent-transport-run-once-never-remediate

The architecture's rule is: *"Squadron never writes to a PR unless asked on that invocation."* Through a slash command a second actor (the session) could ask. D3 closes that gap with four explicit prompt instructions — `--post` only when the operator typed it, a write command runs once, printed remediation is shown and not executed, and `--dry-run` is never substituted. The design is honest that prompt instructions aren't enforceable like code paths, accepts that the CLI's own refusals still hold, and positions the instructions as closing the gap between "the CLI refused" and "the session worked around it." This directly implements the architectural principle for the agent-transport context.

### [PASS] D2 parity-testing strategy is appropriate for a prompt-based transport
location: project-documents/user/slices/386-slice.slash-command-parity-documentation-and-live-evidence.md#d2--parity-is-tested-as-surface-agreement-plus-one-deterministic-live-comparison

Because a command file cannot be executed by pytest, the design correctly identifies the two ways a prompt transport drifts — delegation-line mutation and described-surface drift — and tests both mechanically (set-equality of registered Click options vs. `--flag` tokens in the section; delegation command with remainder placeholder and nothing appended). The live byte-identical comparison targets `sq pr show --json` (deterministic via `_render_json`, shaped for this in 381), and the structural comparison for model output is honest about what can be identical (frontmatter keys, deterministic fields) vs. what cannot (prose, verdict). The test is written so extending coverage to pre-existing subcommands is a list entry, not a rewrite. This satisfies the architecture's "Interface parity" principle within the constraints of the transport.

### [PASS] Live-run write sequencing respects the architecture's "reads before writes, writes are explicit" principle
location: project-documents/user/slices/386-slice.slash-command-parity-documentation-and-live-evidence.md#d6--the-live-run-is-on-this-slices-own-branch-and-lands-the-way-its-predecessors-did

The D6 sequence runs every write (create, post) through `--dry-run` first, as the architecture requires: *"each with a dry-run form that prints what would be sent."* The landing strategy — local `--no-ff` merge into `squadron-pr`, with the live PR as evidence rather than the merge route — matches every predecessor slice's pattern. The architecture's "Never surprise the operator" is respected: each step is an explicit operator command, preceded by its dry-run. The post-PR-merge state (marking the PR merged) is correctly noted as the natural final state.

### [NOTE] Dependencies frontmatter lists 382/384/385; "Consumes" section also references 381 and 383
location: project-documents/user/slices/386-slice.slash-command-parity-documentation-and-live-evidence.md:29-36

The frontmatter `dependencies: [382, 384, 385]` and the Prerequisites section ("382, 384, 385 merged into `squadron-pr`") list three slices, while "Consumes from Other Slices" correctly enumerates all five (381–385). This is functionally correct — 381 and 383 are consumed but were likely merged earlier and aren't blocking prerequisites — but readers tracing the dependency graph from frontmatter alone may miss that 381's `sq pr show --json` and 383's `--reviews-dir`/`review.external_reviews_dir` are required interfaces. No architectural violation; a documentation-consistency note.

### [NOTE] D4 profile-inside-session handling is documented-from-observation rather than designed
location: project-documents/user/slices/386-slice.slash-command-parity-documentation-and-live-evidence.md#d4--provider-profile-inside-a-session-is-documented-from-observation-not-decided-here

The architecture says *"The protocol must not leak `gh`-specific shapes"* and the adapter boundary is git/host, not provider profiles, so the profile issue sits outside the architecture's direct scope. D4 correctly refuses to inject a profile flag (consistent with D1's verbatim rule) and instead commits to observing what happens with the default profile inside a session and documenting the result. If the default fails with an unhelpful message, the design says that is a CLI defect, logged as an issue — not patched over in the command file. This is a defensible position, but the slice's success criterion ("The observed behavior of the default profile inside a session is documented") creates a documentation dependency on a runtime observation whose outcome is unknown at design time. The fallback plan (log as CLI defect) is adequate.
