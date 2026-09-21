---
docType: review
layer: project
reviewType: slice
slice: create-a-pr-with-a-good-message
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/385-slice.create-a-pr-with-a-good-message.md
aiModel: z-ai/glm-5.2
status: complete
responseStatus: addressed
dateCreated: 20260917
dateUpdated: 20260917
reviewedSha: 2c138d421574d964b8615b2b9df23c06de897ba3
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 29
findings:
  - id: F001
    severity: pass
    category: uncategorized
    summary: "Base selection faithfully implements the architecture's three-term chain with refusal"
    location: "project-documents/user/slices/385-slice.create-a-pr-with-a-good-message.md:207-250"
  - id: F002
    severity: pass
    category: uncategorized
    summary: "Section contract and presence-and-filled check match the architecture's five-section rule"
    location: "project-documents/user/slices/385-slice.create-a-pr-with-a-good-message.md:319-372"
  - id: F003
    severity: pass
    category: uncategorized
    summary: "One-shot path correction is well-justified and explicitly invited by the architecture"
    location: "project-documents/user/slices/385-slice.create-a-pr-with-a-good-message.md:277-317"
  - id: F004
    severity: pass
    category: uncategorized
    summary: "Import-boundary placement is correct and extends the existing test"
    location: "project-documents/user/slices/385-slice.create-a-pr-with-a-good-message.md:374-405"
  - id: F005
    severity: pass
    category: uncategorized
    summary: "Review-scoping scan correctly implements the architecture's range-membership rule"
    location: "project-documents/user/slices/385-slice.create-a-pr-with-a-good-message.md:407-429"
  - id: F006
    severity: pass
    category: uncategorized
    summary: "Host-call failure modes are thoroughly enumerated with explicit handling"
    location: "project-documents/user/slices/385-slice.create-a-pr-with-a-good-message.md:425-455"
  - id: F007
    severity: concern
    category: nfr-compliance
    summary: "`git ls-remote` timeout constant should be `GIT_QUERY_TIMEOUT_SECONDS`, not `HOST_COMMAND_TIMEOUT_SECONDS`"
    location: "project-documents/user/slices/385-slice.create-a-pr-with-a-good-message.md:427-431"
  - id: F008
    severity: concern
    category: error-handling
    summary: "Model-call failure mode is not explicitly enumerated"
    location: "project-documents/user/slices/385-slice.create-a-pr-with-a-good-message.md:253-275"
  - id: F009
    severity: concern
    category: under-specification
    summary: "Title generation mechanism is under-specified"
    location: "project-documents/user/slices/385-slice.create-a-pr-with-a-good-message.md:58-65"
---

# Review: slice — slice 0

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.2

## Findings

### [PASS] Base selection faithfully implements the architecture's three-term chain with refusal

D1 implements exactly what the architecture specifies: `--base`, then the configured integration branch when the adapter confirms it exists on the host, else the host default, with refusal rather than fall-through when the integration branch is configured but absent. The four-outcome decision table correctly captures the architecture's "if it does not, creation fails and says so rather than falling through to `main`." The design also correctly distinguishes `cf` unavailability (treat the term as absent, proceed to host default) from an explicit empty config, and the rationale for not confirming `--base` against the host (the 422 from `open_pull_request` is loud) is sound and consistent with the architecture's "reads before writes" principle.

### [PASS] Section contract and presence-and-filled check match the architecture's five-section rule

The five headings (what changed, why, how it was verified, known gaps, review provenance), their input mappings, their no-input lines, and the rule that "a body that fails that check is an error, not a degraded PR" all match the architecture's "Description composition" section verbatim in intent. The design's distinction between squadron-written headings/facts and model-written prose correctly implements the architecture's "The section structure is not left to the model: squadron writes the headings and asks the model only for the prose." The "filled" definition (structural, not semantic) is a practical and well-scoped interpretation of the architecture's requirement.

### [PASS] One-shot path correction is well-justified and explicitly invited by the architecture

D3 performs the verification the architecture and plan entry both requested ("correct whichever of the docstring or the routing is wrong") and reaches a defensible conclusion: `summary_oneshot` does not refuse `sdk` (its caller gates on SDK-session reuse), so the composer performs the one-shot sequence directly rather than bending either `summary_oneshot` or `run_review_with_profile` to a third purpose. The docstring correction is the right scope — the routing is correct, the docstring described the caller's policy. The slice plan entry has been updated to acknowledge this resolution. This is a model scope correction.

### [PASS] Import-boundary placement is correct and extends the existing test

D6 correctly identifies that `pr/` needs both `codehost` types and `review` helpers, which is the combination the import-boundary test forbids inside `review/` and permits in the CLI tier. Placing the logic in a new `src/squadron/pr/` package (imported only by `cli/`, importing `codehost` and `review` freely) is the right architectural decision, and the explicit assertion that `review/` still does not import `pr/` extends the boundary test correctly. The `resolve_locator` extraction avoids duplicating the first three steps of `resolve_and_fetch_pull_request` without pulling in the existing-PR resolution that `create` does not need.

### [PASS] Review-scoping scan correctly implements the architecture's range-membership rule

D7 implements exactly the architecture's rule: "the most recent review artifact whose reviewed sha lies in the base-to-head range, so a review of an earlier merged branch that is an ancestor of this one never qualifies." The use of `git rev-list <base>..<head>` for range membership (not ancestry of head) is the correct mechanism to exclude merged-ancestor reviews. The design's note that `locate_review` is not reusable (index-keyed, raises on ambiguity) is accurate, and the decision to write a new scan is justified. The skip-with-WARNING behavior for malformed artifacts is observable and non-fatal, matching the architecture's principle.

### [PASS] Host-call failure modes are thoroughly enumerated with explicit handling

D8 enumerates each host call (`identify_operator`, `branch_exists`, `default_branch`, `git ls-remote`, `open_pull_request`), classifies the first four as reads preceding the model call and the fifth as the sole write, and specifies the error-handling pattern (`except CodeHostError → render_code_host_error → exit 1`). The specific handling of `PullRequestCreationRejectedError` (422, no retry, name the reason) is explicit and matches the architecture's "creation rejected" failure mode. The no-retry rationale (a retried create after a network error that actually landed would open two PRs) is sound.

### [CONCERN] `git ls-remote` timeout constant should be `GIT_QUERY_TIMEOUT_SECONDS`, not `HOST_COMMAND_TIMEOUT_SECONDS`

D8 lists five "host calls on this path" and states they are all "bounded by `HOST_COMMAND_TIMEOUT_SECONDS`." However, `git ls-remote` is a git operation, not a `gh`/host call. The established codebase pattern (verified in `src/squadron/codehost/refs.py:28` and `src/squadron/codehost/remotes.py:29`) uses `GIT_QUERY_TIMEOUT_SECONDS` (30s) for git queries (rev-parse, merge-base, diff, remote enumeration) and `HOST_COMMAND_TIMEOUT_SECONDS` (30s, in `github_cli.py:68`) exclusively for `gh` invocations. Both constants happen to be 30 seconds, so the practical bound is identical, but the design explicitly names the wrong constant for a git call. The success criteria at line 505 ("Every host call on the path carries `HOST_COMMAND_TIMEOUT_SECONDS`") compounds this by classifying the `git ls-remote` call as a "host call." The design should reference `GIT_QUERY_TIMEOUT_SECONDS` for the `git ls-remote` call, consistent with how 381 and 382 bound their git operations.

### [CONCERN] Model-call failure mode is not explicitly enumerated

The architecture requires that "Failure modes are enumerated and observable" for each new I/O path or message type. The one-shot model call in `pr/body.py` is a new I/O path (a new composer performing the `get_profile → get_provider → create_agent → handle_message` sequence directly, not through an existing function). D8 thoroughly enumerates host-call failures and states "A transport failure or timeout at any read refuses before the model runs," but the design does not explicitly state what happens when the model call itself fails — provider unreachable, connection timeout mid-stream, or the agent raising an exception during `handle_message`. D5 covers structural model-output failure (missing section, bare heading) but not provider/transport failure during the call. The architecture's failure list includes "host call exceeded its timeout" but the model call is not a host call; its failure mode needs its own explicit handling strategy (e.g., "a provider error during composition logs at ERROR, exits non-zero, and creates nothing"). The design implies this through the data-flow ordering (compose → check → write) but does not state it, which leaves the implementer to infer the exception-handling pattern.

### [CONCERN] Title generation mechanism is under-specified

The technical scope lists `--title` as a flag, and the data-flow diagram and `open_pull_request` call both reference `title` as a parameter. However, the design's composition step (D3, D4) describes only body composition — the five headings, the model prose, and the presence check. The design never specifies how the title is generated when `--title` is not provided: is it derived from the first commit's subject line, composed by the model as part of the one-shot call, or constructed deterministically from the slice name? The architecture says "produces a title and a body" but does not elaborate on the title mechanism, so the slice design needs to fill this gap. Without this specification, the implementer must invent the title strategy, and the dry-run/real equality success criterion (line 488) cannot be fully validated without knowing what the title is.

### Run Digest

- Response length: 9450 chars
- Response is newline-free: no
- Tool calls made: 29
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 16820
- `## Summary` located: no
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
