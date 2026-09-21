---
docType: review
layer: project
reviewType: slice
slice: small-fixes-batch-2
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/922-slice.small-fixes-batch-2.md
aiModel: moonshotai/kimi-k3
status: complete
dateCreated: 20260919
dateUpdated: 20260919
reviewedSha: 700662730dea4ad0299ee0200c9620a828907bcf
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 13
findings:
  - id: F001
    severity: concern
    category: accuracy
    summary: "Fix 6 cites the wrong slice and wrong decision for the exclusion precedent"
    location: "project-documents/user/slices/922-slice.small-fixes-batch-2.md:122"
  - id: F002
    severity: concern
    category: under-specification
    summary: "Frontmatter `interfaces: []` is inconsistent with the body's own interface declarations"
    location: "project-documents/user/slices/922-slice.small-fixes-batch-2.md:7"
  - id: F003
    severity: note
    category: integration
    summary: "New exception is exported contract; other ProcessRunner implementations are not addressed"
    location: "project-documents/user/slices/922-slice.small-fixes-batch-2.md:196-202"
  - id: F004
    severity: note
    category: nfr
    summary: "No NFRs to restate; failure-mode enumeration standard is substantially met"
    location: "project-documents/user/slices/922-slice.small-fixes-batch-2.md"
  - id: F005
    severity: pass
    category: architecture-alignment
    summary: "Scope, dependency direction, and integration with consuming slices all align"
    location: "project-documents/user/slices/922-slice.small-fixes-batch-2.md"
---

# Review: slice — slice 922

**Verdict:** CONCERNS
**Model:** moonshotai/kimi-k3

## Findings

### [CONCERN] Fix 6 cites the wrong slice and wrong decision for the exclusion precedent

The doc attributes the exclusion mechanism to "slice 917 D6" both here (Fix 6 scoping) and at line 241 ("an exclusion is slice 917's policy working as designed"). Verified against the slice corpus: the excluded-subtree jail policy is **slice 918** (review-grounding, Part A), whose **D3 — "Silent to the model, WARNING to the operator"** (918-slice.review-grounding.md:144-147) is the logging posture Fix 6 revises; 918's D6 is about exclusion patterns resolving as paths by containment. Slice 917 is review-artifact-integrity and contains no exclusion policy. This matters beyond a stale cross-reference: Fix 6 is deliberately amending 918's D3 posture (WARNING per refusal) for the policy-exclusion subclass, and Implementation Notes line 363 compounds it by saying "Fix 6 changes what slice 917's tests assert" — the tests pinned to WARNING-for-exclusions belong to 918's work. The document's own claim that "The docstrings that state 'both are logged at WARNING' are corrected" (D6) is the right instinct applied to the wrong citation. The fix itself is sound and consistent with 918's structure (escape vs. exclusion are distinct conditions); only the attribution is wrong.

### [CONCERN] Frontmatter `interfaces: []` is inconsistent with the body's own interface declarations

The frontmatter declares no interfaces, but the body declares them in both directions: "Interfaces Required" (lines 132-135) names the `cf validate frontmatter --json` contract and an extension to the `ProcessRunner` protocol, and "Provides to Other Slices" (lines 249-252) names `ProcessCwdNotFoundError` and `TOOL_USE_TYPE`/`TOOL_RESULT_TYPE` as new shared symbols. An automated consumer keying on frontmatter (this project builds frontmatter gates and document tooling) would conclude this slice touches no contracts, when in fact it extends one protocol with a new exception and adds two new canonical constants that future consumers are expected to reference. Predecessor 921 also used `interfaces: []`, but it genuinely added no new contract surface; this slice does. Either populate the field or record why the convention leaves it empty for maintenance slices.

### [NOTE] New exception is exported contract; other ProcessRunner implementations are not addressed

D3 adds `ProcessCwdNotFoundError` to the `ProcessRunner` protocol's documented exception set and lists it under "Provides to Other Slices — available to any future `ProcessRunner` caller." The doc names exactly one `ProcessNotFoundError` catcher (`codehost/github_cli.py:490`) and notes the git call sites in `codehost/remotes.py`/`codehost/refs.py` do not catch it — but it does not address whether any `ProcessRunner` implementation other than `SubprocessRunner` exists, or what the new exception means for one (must it raise it? must callers of the protocol now handle it?). If `SubprocessRunner` is the only implementation this is a documentation nicety; if a mock or alternate runner exists, criterion 7's "raises `ProcessCwdNotFoundError`" needs a counterpart statement for that implementation. Worth one sentence in D3 rather than a task-time surprise.

### [NOTE] No NFRs to restate; failure-mode enumeration standard is substantially met

The parent architecture (900-arch.maintenance-and-refactoring.md) states no latency/throughput/availability NFRs, so there is nothing to restate — the criterion is vacuously satisfied. On failure modes: the slice introduces no new external I/O paths. The one touched I/O path (Fix 2's `cf validate` invocation) inherits 919's D14 timeout/hang/reap handling, and criterion 6 (line 269) explicitly pins unchanged behavior on timeout, missing `cf`, and unreadable count. Fix 3's check-then-use reasoning (classify inside the existing handler to avoid a pre-check race) is the correct failure-mode discipline for a subprocess spawn. No hang/timeout/disconnect enumeration is owed and none is missing.

### [PASS] Scope, dependency direction, and integration with consuming slices all align

Every fix maps to an architecture-sanctioned work category (dependency management: Fix 1; bug fixes: Fixes 2, 3, 5, 6; refactoring: Fix 4), none is a new feature, and the plan entry (900-slices.maintenance-and-refactoring.md entry 20) scopes exactly these six issues with "Dependencies: none." Fix 1's stale-premise corrections (keeping `mcp`, which #65 listed as unimported but is now imported in two files; noting #108's `dispatch.py:174` citation no longer holds) follow the project's own verified-against-main convention. Fix 2's D2 confines a squadron-side scope predicate to the zero-of-N branch with the rejected alternative recorded, preserving cf as validation authority and 919's fail-closed postures — criterion 5 pins the D10 worktree message intact. Fix 4's constants land in `core/models.py` beside the existing `SDK_RESULT_TYPE`/`RATE_LIMIT_EVENT_TYPE`, so all five consumers depend inward on core. Each fix carries verification commands, and the two unverified command shapes (`run` kwargs, `sq setup --check`) are flagged "to be confirmed during implementation" rather than asserted — the right handling under the project's no-speculative-fix rule.

### Run Digest

- Response length: 6690 chars
- Response is newline-free: no
- Tool calls made: 13
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 0
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5

## Response (20260919)

All findings verified against source before acting.

- **F001** (wrong slice/decision cited for the exclusion precedent) — confirmed: the excluded-subtree policy and its logging posture are slice 918 D3 ("Silent to the model, WARNING to the operator", `918-slice.review-grounding.md:144`). The "917" attribution was carried over from issue #100's text without checking it. All five citations corrected, D6 now states outright that it amends 918 D3 for the policy-exclusion case only, and the design notes that #100's attribution is wrong.
- **F002** (`interfaces: []` inconsistent with the body) — not changed. The slice-design template defines the field as `interfaces: [list-of-slices-that-depend-on-this]`: it lists *slices*, not symbols. No slice depends on 922, so `[]` is the correct value; the new symbols are recorded where the template puts them, under Integration Points. Listing symbols in a field typed as slice references would break any consumer that reads it as such.
- **F003** (other `ProcessRunner` implementations not addressed) — confirmed one exists: `tests/codehost/fake_runner.py::FakeProcessRunner`. It raises whatever `Exception` a test scripts, so it needs no change. D3 now says so, names `SubprocessRunner` as the only production implementation, and states that the protocol obliges no caller to handle the new exception.
- **F004**, **F005** — no action required.

Design doc updated: `project-documents/user/slices/922-slice.small-fixes-batch-2.md` (dateUpdated 20260919).
