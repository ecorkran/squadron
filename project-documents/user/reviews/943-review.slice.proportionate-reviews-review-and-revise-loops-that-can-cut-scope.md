---
docType: review
layer: project
reviewType: slice
slice: proportionate-reviews-review-and-revise-loops-that-can-cut-scope
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/943-slice.proportionate-reviews-review-and-revise-loops-that-can-cut-scope.md
aiModel: deepseek/deepseek-v4.1-flash
aiProfile: openrouter
status: complete
dateCreated: 20261011
dateUpdated: 20261011
reviewedSha: d88ac8050ef8bb27e7faaff62428cca7356ddbb1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 33
turns: 19
promptTokens: 1262449
cachedTokens: 1108736
completionTokens: 61069
reasoningTokens: 62846
durationSeconds: 568.7
squadronVersion: 0.21.4
findings:
  - id: F001
    severity: pass
    category: failure-modes
    summary: "No new I/O path or message type, so the failure-mode enumeration criterion is not triggered"
    location: "project-documents/user/slices/943-slice.proportionate-reviews-review-and-revise-loops-that-can-cut-scope.md:78-84"
  - id: F002
    severity: pass
    category: integration-points
    summary: "The claimed pipeline blast radius is accurate"
    location: "project-documents/user/slices/943-slice.proportionate-reviews-review-and-revise-loops-that-can-cut-scope.md:117-119"
  - id: F003
    severity: concern
    category: integration-points
    summary: "Editing the judge template prompts re-keys calibration identity and lapses existing graduations — \"no migration is needed\" is not correct"
    location: "project-documents/user/slices/943-slice.proportionate-reviews-review-and-revise-loops-that-can-cut-scope.md:121-123"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Item 4 loosens the accept direction of a deliberately fail-closed gate, and nothing in the slice verifies it"
    location: "project-documents/user/slices/943-slice.proportionate-reviews-review-and-revise-loops-that-can-cut-scope.md:45"
  - id: F005
    severity: concern
    category: under-specification
    summary: "The relaxation of the omission criteria is measured only on the weight side"
    location: "project-documents/user/slices/943-slice.proportionate-reviews-review-and-revise-loops-that-can-cut-scope.md:43"
  - id: F006
    severity: note
    category: consistency
    summary: "Technical Scope and the Implementation Approach list six YAML files; the Architecture section says four"
    location: "project-documents/user/slices/943-slice.proportionate-reviews-review-and-revise-loops-that-can-cut-scope.md:78"
  - id: F007
    severity: note
    category: scope-boundary
    summary: "Ownership boundary for judge machinery should be recorded"
    location: "project-documents/user/slices/943-slice.proportionate-reviews-review-and-revise-loops-that-can-cut-scope.md:45-46"
  - id: F008
    severity: note
    category: integration-points
    summary: "The revise paragraph also reaches the non-`feedback:` revise path, which the reach list omits"
    location: "project-documents/user/slices/943-slice.proportionate-reviews-review-and-revise-loops-that-can-cut-scope.md:117-119"
---

# Review: slice — slice 943

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [PASS] No new I/O path or message type, so the failure-mode enumeration criterion is not triggered

The design's Component Structure and Data Flow sections are correct that nothing new is introduced: the change is prompt text in existing review templates plus one appended paragraph in `_findings_block`, and a proportionality finding rides the existing `review → ActionResult.findings → _findings_block → revise` path. There is no new boundary, no new wire/message type, and no new subprocess or network call, so there is no new hang/timeout/peer-disconnect surface to enumerate. Verified: the only non-template edit is a string appended in `_findings_block` (dispatch.py:550-580), and the no-findings branch is left untouched as stated.

### [PASS] The claimed pipeline blast radius is accurate

Every pipeline named carries a `feedback: review` revise step — P4, P5, P45, P456, P56, P6, implement, implement-plan, slices-plan, tasks-plan, findings-addressed-cycle, judge-cycle — with no config change required, as claimed. Combined with the design's explicit choice to put the instruction in the shared `_findings_block` rather than a new per-template `revise_guidance` field, this is the right call for "one sentence true for every review type," and the design names the extension point if guidance ever needs to diverge.

### [CONCERN] Editing the judge template prompts re-keys calibration identity and lapses existing graduations — "no migration is needed" is not correct

The slice's only statement about 320 is: "Judge scores recorded before this change are not comparable on the proportionality criterion. The criterion is new, so old scores simply lack it and no migration is needed." That conflates an additive criterion with an identity change. `template_content_hash` hashes the template's `name`, `description`, `system_prompt`, `model`, and `prompt_template` (metrology/identity.py), i.e. the prompt text *is* the instrument identity — and graduation matching requires exact hash equality, deliberately, so that "a graduation earned by one prompt" cannot "silently transfer to a rewritten one" (metrology/graduation.py `_identity_matches`). Changing `slice.yaml`/`tasks.yaml`/`arch.yaml` is mostly benign (plain reviews are not discovered as judge results), but items 1 and 5 change `judge-slice-vs-arch.yaml` and `judge-tasks-vs-slice.yaml` system prompts, which re-keys `JudgeConfigId` for both judge configs: every existing graduation for those identities stops matching, residual offer selection returns zero for them, and accumulated calibration evidence reads as a lapsed instrument rather than as prior evidence on the same instrument. This is the exact churn risk 320-arch names ("frequent template edits re-key accumulated evidence, which can perpetually reset n"), with the inherit-vs-re-earn question left open for 322. The persisted `criteria:` map also changes shape for all future judge results (a new criterion appears), which 321 reports per criterion. This needs to be stated as the real comparability boundary — and the 322 coordination named — rather than disposed of as "no migration needed."

### [CONCERN] Item 4 loosens the accept direction of a deliberately fail-closed gate, and nothing in the slice verifies it

`judge-findings-addressed.yaml` defines `addressed` as "the diff contains a change that substantively resolves it," offers `disputed` for uncertainty, and states plainly that "a wrong `addressed` ends the loop on work that was never done" — the gate's whole posture is asymmetric in the direction the new wording relaxes. Two problems. First, the new text ("a removal or deferral of the scope a finding was about") may not be decidable from what the judge is actually given: the conservative subset is the prior findings, the set of changed paths, and the fresh findings; a *deferral* is frequently a rewrite or a note, not something visible as a removal in that evidence, so the instruction invites the guess-to-`addressed` that `disputed` exists to prevent. Second, there is no verification: the walkthrough reruns P4, and P4 has no `findings-addressed` gate step, so Success Criterion 5 ("counts removal or deferral ... as `addressed`") is not exercised by anything in the plan, and the design's own statement that "tests do not check the template wording itself" leaves SC5 with no evidence path at all. Narrow the wording to what the evidence can show, or state explicitly that a deferral must be observable in the diff, and either add a gate-level check or record SC5 as unverified.

### [CONCERN] The relaxation of the omission criteria is measured only on the weight side

The gap qualifier ("raise a missing-item finding only when you can name the requirement the gap leaves unmet") trades review coverage for weight, and the design is honest that it qualifies the omission criteria that are "the main source of added weight." But the verification walkthrough measures only per-round word counts plus "at least one finding should ask for a cut, or the review should PASS outright." Nothing observes the other side of the trade: whether a genuine omission — an unenumerated failure mode on a new I/O path, an unrestated NFR target — still earns a finding. The failure-diagnosis paragraph the slice offers ("Either the reviewer did not raise proportionality ... or revise ignored the instruction") enumerates two causes and omits this third, which is the one the change newly creates. The single-model rerun also cannot separate "the reviewer stayed quiet because the gap was not real" from "the reviewer stayed quiet because it no longer has to justify silence." Add an explicit check after the rerun: the genuine gaps the baseline flagged on 127 must still be raised, or the reason each was dropped must be stated.

### [NOTE] Technical Scope and the Implementation Approach list six YAML files; the Architecture section says four

"No new components. Four YAML prompt edits and one string change in `_findings_block`" contradicts the five template-level items in Technical Scope and the five steps in the Development Approach: `slice.yaml`, `tasks.yaml`, `arch.yaml`, `judge-slice-vs-arch.yaml`, `judge-tasks-vs-slice.yaml`, and `judge-findings-addressed.yaml` is six. Low risk because Success Criterion 5 names the findings-addressed file explicitly, but the Component Structure section is the one an implementer would use to bound the diff, and it understates it.

### [NOTE] Ownership boundary for judge machinery should be recorded

Items 4 and 5 change judge-owned artifacts: the `findings-addressed` gate policy's accept semantics and the two calibration judge templates. The 900 slice plan moved entry 912 to slice 305 under initiative 300 on the reasoning that "the seam and the judge machinery live" there, and 320 owns judge comparability. Prompt-text-only edits to shared review templates are plainly maintenance (901/904/916–919 set that precedent), and changing what the gate accepts is closer to changing a capability's behavior. Record the coordination with 300/305/320 — or state explicitly why this belongs in 900 as prompt text while 912's move did not. This is a PM call, not a defect.

### [NOTE] The revise paragraph also reaches the non-`feedback:` revise path, which the reach list omits

`_findings_block` is reached from two call sites, not one: the `feedback: review` path (`_resolve_feedback_prompt`) and the fallback fix-from-prior-review path when no explicit prompt or `build_context` output exists (`_resolve_prompt_from_prior_review`). The design's rationale for the shared location is right — it is precisely this sharing that makes one string sufficient — but the "Provides to Other Slices" enumeration describes only `feedback: review` pipelines, so the stated blast radius is narrower than the actual one.

### Run Digest

- Response length: 9804 chars
- Response is newline-free: no
- Tool calls made: 33
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 248748
- Effort: backend default
- Turns: 19
- Tokens — prompt / cached / completion / reasoning: 1262449 / 1108736 / 61069 / 62846
- Duration: 568.7 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8

## Response

Resolved by cutting scope where possible, per the slice's own rule.

- **F003 (judge calibration re-key):** cut. Judge templates are no longer edited, so 320 calibration identities are untouched.
- **F004 (findings-addressed loosening):** cut. The existing definition ("a change that substantively resolves it") already covers a cut; no wording change.
- **F005 (coverage side unmeasured):** accepted. Walkthrough step 4 checks the rerun still covers 127's plan entry and the approved cut, and that real-gap CONCERNs still appear; the failure diagnosis names the qualifier as a third cause. The slice criterion now also grades cutting plan-assigned scope as CONCERN, and revise must log each deferral as a GitHub issue.
- **F006 (file count):** moot after the cuts; now three YAML edits.
- **F007 (judge ownership):** moot; no judge machinery changes.
- **F008 (second revise path):** accepted; Integration Points names `_resolve_prompt_from_prior_review`.
