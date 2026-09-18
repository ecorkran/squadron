---
docType: review
layer: project
reviewType: slice
slice: review-a-pr
project: squadron
verdict: FAIL
sourceDocument: project-documents/user/slices/382-slice.review-a-pr.md
aiModel: claude-sonnet-5
status: complete
dateCreated: 20260913
dateUpdated: 20260913
reviewedSha: fdb46f40e90eb0c9c918851fb125565a6ccff7c1
findings:
  - id: F001
    severity: fail
    category: security
    summary: "SDK `setting_sources: [project]` leaves the two-root isolation boundary open to PR-controlled code execution"
    location: "project-documents/user/slices/382-slice.review-a-pr.md:310-315"
  - id: F002
    severity: concern
    category: failure-mode-enumeration
    summary: "Lock-file corruption is not enumerated as a failure mode for the sweep path"
    location: "project-documents/user/slices/382-slice.review-a-pr.md:174-178"
  - id: F003
    severity: concern
    category: under-specification
    summary: "Data Flow diagram and D4 disagree on which layer renders the PR metadata block"
    location: "project-documents/user/slices/382-slice.review-a-pr.md:117"
  - id: F004
    severity: pass
    category: alignment
    summary: "Two-root split correctly implements the architecture's convention/code isolation rule"
    location: "project-documents/user/slices/382-slice.review-a-pr.md:133-151"
  - id: F005
    severity: pass
    category: alignment
    summary: "Scope stays within the slice plan's boundary, with corrections tracked transparently"
    location: "project-documents/user/slices/382-slice.review-a-pr.md:53-70"
---

# Review: slice — slice 382

**Verdict:** FAIL
**Model:** claude-sonnet-5

## Findings

### [FAIL] SDK `setting_sources: [project]` leaves the two-root isolation boundary open to PR-controlled code execution

The whole point of D1's `convention_root` split is that "how this project works" (rules, `CLAUDE.md`) must come from the trusted checkout while only reviewed code comes from the untrusted worktree (architecture: "Which tree rules load from," "a PR that edits the rules directory cannot review itself against its own edits"). The Risk Assessment section itself identifies that this guarantee is incomplete: the SDK provider's `setting_sources: [project]` resolves `.claude/settings.json` from its own `cwd`, which on the tools path is the scratch worktree — i.e., attacker-controlled PR content. Claude Code settings can define hooks that execute arbitrary shell commands on tool-call events, so an adversarial PR could plant a `.claude/settings.json` in its own worktree and get code executed on the operator's machine during an automated review — the exact "surprise the operator" scenario the architecture's two-root principle exists to prevent. The document's resolution is "determine during implementation whether the code template should drop `setting_sources` on the PR path, and record the answer" — a design-time TBD on a security-critical trust boundary, with no test in the Testing section asserting the settings-isolation behavior either way. Per this project's failure-mode enumeration standard ("explicitly, not implicitly," "silent failure paths are bugs in waiting"), a known-open path for untrusted code influence on the reviewer process should be closed (e.g., a firm decision to drop `setting_sources` on the PR path, or an explicit sandboxing argument) before this slice is implemented, not deferred.

### [CONCERN] Lock-file corruption is not enumerated as a failure mode for the sweep path

D3 introduces `lock.json` (pid + start time) as a new on-disk I/O artifact that `sweep_orphans` reads on every invocation before creating a new worktree. The doc specifies liveness semantics (pid absent, or present with a different start time ⇒ orphan) but does not say what happens when the lock file is truncated or unparsable — the exact state a process crash mid-write would leave behind, which is precisely the abnormal-exit scenario D3 is designed around. If an unhandled parse exception propagates out of `sweep_orphans`, it would fail *every* subsequent `sq review pr` invocation until the directory is cleaned by hand, which is a worse outcome than the orphan-accumulation problem D3 solves. The Testing section (`test_worktree.py`) lists "sweep (live and dead owner)" but not a corrupt/partial lock file case. Per the project's Failure-Mode Enumeration rule, this new I/O path needs an explicit answer ("what if the lock file is malformed") with an observable signal (WARNING + treat-as-orphan, most likely) and a matching test.

### [CONCERN] Data Flow diagram and D4 disagree on which layer renders the PR metadata block

The `Data Flow: sq review pr <target>` diagram shows the CLI assembling `inputs = {..., pr: <rendered block>, ...}` before calling `run_review_with_profile` — implying the fenced/label-neutralized block already exists when the CLI builds inputs. D4 states the opposite: the block is "Rendered by `code_review_prompt`" (the builder inside `review/builders/code.py`, invoked during template rendering) specifically "because the architecture fixes fence policy in one place." Component Structure and Implementation Notes (`_pr_block()` in `builders/code.py`, built before `review.py` in the implementation order) support D4's version, so the diagram's `<rendered block>` label appears to be a documentation slip rather than the intended contract — but as written it leaves ambiguous whether `review.py` passes raw PR metadata (title/body/issues/discussions) or a pre-rendered string into `inputs["pr"]`. Since this input is called out under "Provides" as a reusable integration point, the ambiguity should be resolved before implementation so the CLI and builder aren't written against different assumptions.

### [PASS] Two-root split correctly implements the architecture's convention/code isolation rule

D1 adds `convention_root` alongside `cwd` rather than repointing `cwd` at the worktree, matches the architecture's explicit rejection of "pointing `cwd` at the worktree and copying the rules into it," defaults to `None` (`cwd`) preserving every existing caller's behavior, and is backed by a byte-identical-prompt pin test. This is a faithful, non-overreaching translation of the "Which tree rules load from" architectural principle into a concrete, minimally-invasive contract change.

### [PASS] Scope stays within the slice plan's boundary, with corrections tracked transparently

The Excluded list (persistence, posting, creation, slash parity, pipeline surface) matches the 380 slice plan's sequencing exactly, and the "Scope corrections against the plan entry" table documents three places where design-time investigation (not assumption) overturned the plan's wording — each with a named decision (D1, D4, D7) rather than a silent deviation. This matches both the architecture's "explicit degradation, not silent" ethos and the project's "do not guess or assume" rule.
