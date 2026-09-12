---
docType: review
layer: project
reviewType: arch
slice: pull-request-workflow
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/architecture/380-arch.pull-request-workflow.md
aiModel: moonshotai/kimi-k2.7-code
status: complete
dateCreated: 20260912
dateUpdated: 20260912
reviewedSha: b2da5532ca2731051ca04403caf9f7a546eb6009
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 22
findings:
  - id: F001
    severity: concern
    category: completeness
    summary: "Save-target contract is undefined"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#architectural-principles"
  - id: F002
    severity: concern
    category: consistency
    summary: "PR base selection conflates local integration branch with host PR target"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#technical-considerations"
  - id: F003
    severity: concern
    category: feasibility
    summary: "PR description fixed-section contract relies on unvalidated model output"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#technical-considerations"
  - id: F004
    severity: concern
    category: abstraction
    summary: "Adapter protocol operation names still carry host vocabulary"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#architectural-principles"
  - id: F005
    severity: concern
    category: completeness
    summary: "Doctor check for host adapter is not detailed"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#envisioned-state"
  - id: F006
    severity: concern
    category: completeness
    summary: "Unplanned-repository persistence location is unspecified"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#technical-considerations"
  - id: F007
    severity: concern
    category: consistency
    summary: "Reviewed SHA semantics for PR reviews are unclear"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#technical-considerations"
  - id: F008
    severity: concern
    category: feasibility
    summary: "PR metadata injection into code template is unspecified"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#technical-considerations"
  - id: F009
    severity: note
    category: extension-points
    summary: "No slice allocated for direct GitHub API implementation"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#anticipated-slices"
---

# Review: arch — slice 380

**Verdict:** CONCERNS
**Model:** moonshotai/kimi-k2.7-code

## Findings

### [CONCERN] Save-target contract is undefined

The document states "This initiative introduces a save-target contract on the persistence side that a slice target and a PR target both satisfy" but never enumerates the contract's methods, attributes, or filename-stem rules. Current `save_review_result` in `src/squadron/review/persistence.py:454` requires a concrete `SliceInfo` and builds filenames from `slice_info['index']` and `slice_info['slice_name']`. The `_resolve_save_outcome` helper in `src/squadron/cli/commands/review.py:316` is generic but only as `Callable[[SaveTargetT], bool]`, with no protocol. The PR-keyed persistence slice cannot be planned or sized without defining what a target must provide.

### [CONCERN] PR base selection conflates local integration branch with host PR target

The document says `sq pr create` targets "an explicit `--base`, the configured integration branch when `cf` reports one (never `main` in that case), else the host's default branch." But `git.integration_branch` is documented in `CLAUDE.md` and `src/squadron/review/git_utils.py:17` as the *local* ref that slice branches fork from and merge into. Using it as the host-side PR base changes the meaning of an existing config key for operators who already set it for slice reviews, and it contradicts the integration-branch rule's intent. The document does not acknowledge this semantic shift or explain why the same key should now name a PR target.

### [CONCERN] PR description fixed-section contract relies on unvalidated model output

The body section structure is produced by a one-shot model call through `capture_summary_via_profile` (`src/squadron/pipeline/summary_oneshot.py`). The document says "squadron writes the headings and asks the model only for the prose under each, then checks that every required section is present," but does not specify how the model is constrained to emit only prose under fixed headings or how squadron recovers when the model emits different headings, drops a section, or emits unstructured text. The prior review in `project-documents/user/reviews/archive/380-review.arch.pull-request-workflow.md` raised the same issue; the current text still does not choose between template-based enforcement and a structured intermediate.

### [CONCERN] Adapter protocol operation names still carry host vocabulary

The document states operations are "named by intent, not by any host's feature vocabulary," but lists "read its open review comments, post a comment, create a PR, identify the operator." "Open review comments" is GitHub-specific terminology (GitLab uses "unresolved threads," etc.). A protocol cannot be host-neutral if its operation names embed one host's feature names.

### [CONCERN] Doctor check for host adapter is not detailed

The document states "`sq doctor` gains checks for the host adapter (`gh` present, authenticated, host reachable)" but `src/squadron/cli/commands/doctor_checks.py` currently has no such check, and the document does not specify the check function, section, or how "host reachable" is determined without violating the `doctor_checks.py` module docstring ("no network, no subprocesses"). This is load-bearing functionality described as if designed but left to implementation.

### [CONCERN] Unplanned-repository persistence location is unspecified

The document says when the repository has no `project-documents/`, reviews save to "a configured squadron data directory keyed by host, owner, and repository." It does not name the config key, environment variable, or default path, nor how the operator discovers or overrides it. `CLAUDE.md` explicitly forbids silent fallback values and magic defaults, so this gap is a concrete design risk.

### [CONCERN] Reviewed SHA semantics for PR reviews are unclear

The document says "the reviewed head sha is recorded as it is for slice reviews." For slice reviews, `resolve_reviewed_sha` in `src/squadron/review/persistence.py:115` resolves local `HEAD`. For PR reviews, the relevant SHA is the PR head fetched into a namespaced ref, not the operator's local HEAD. The document does not state whether `resolve_reviewed_sha` is adapted, replaced, or supplied by the adapter, risking a mismatch between the recorded SHA and the actual reviewed tree.

### [CONCERN] PR metadata injection into code template is unspecified

The document says PR metadata (title, body, linked issues, open review comments) reaches the model through the code template "as one additional optional input rendered by the code prompt builder." But `src/squadron/review/builders/code.py:6` only handles `cwd`, `diff`, `files`, and `diff_exclude_patterns`. The document does not describe the new input key, how the builder truncates the metadata, or how it is labeled so the reviewer treats it as untrusted data. The "same size discipline file injection uses" is mentioned, but no size limit or key name is given.

### [NOTE] No slice allocated for direct GitHub API implementation

The document says the protocol is shaped for a direct-API GitHub implementation "designed for, not scheduled," and the Anticipated Slices list does not allocate a slice for it. This is acceptable if the protocol is pressure-tested by unit tests with a fake runner, but the document's claim that the protocol stays host-neutral depends on that future work actually being done.
