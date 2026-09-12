---
docType: review
layer: project
reviewType: arch
slice: pull-request-workflow
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/architecture/380-arch.pull-request-workflow.md
aiModel: minimax/minimax-m3
status: complete
dateCreated: 20260912
dateUpdated: 20260912
reviewedSha: f81fd1dedfdc08f507996e5984f6dd3afec5ea71
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 24
findings:
  - id: F001
    severity: concern
    category: consistency
    summary: "Persistence \"generic target\" claim contradicts current code"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#Design-Goals"
  - id: F002
    severity: concern
    category: consistency
    summary: "Minimal-SliceInfo pattern contradiction"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#Architectural-Principles"
  - id: F003
    severity: concern
    category: completeness
    summary: "PR metadata injection path unspecified"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#Envisioned-State"
  - id: F004
    severity: concern
    category: completeness
    summary: "PR review frontmatter / filename shape unspecified"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#Envisioned-State"
  - id: F005
    severity: concern
    category: feasibility
    summary: "Worktree lifecycle deferred to slice-level but is architectural"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#Technical-Considerations"
  - id: F006
    severity: concern
    category: antipattern
    summary: "Adapter protocol with one planned implementation"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#Design-Goals"
  - id: F007
    severity: concern
    category: completeness
    summary: "`sq pr create` model call through \"existing provider-profile machinery\" is undefined for non-reviews"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#Technical-Considerations"
  - id: F008
    severity: concern
    category: consistency
    summary: "PR description body omits tasks despite promising to gather them"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#Envisioned-State"
  - id: F009
    severity: concern
    category: completeness
    summary: "Default PR base for unplanned repos unspecified"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#Technical-Considerations"
  - id: F010
    severity: concern
    category: technology
    summary: "Untrusted-PR-metadata framing specified, delimiter unspecified"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#Technical-Considerations"
  - id: F011
    severity: concern
    category: feasibility
    summary: "Per-failure tests for `gh` subprocess states are asserted without a strategy"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#Architectural-Principles"
  - id: F012
    severity: note
    category: completeness
    summary: "Default fallback chain for rules outside a planned project contradicts \"explicit degradation\""
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#Technical-Considerations"
---

# Review: arch — slice 380

**Verdict:** CONCERNS
**Model:** minimax/minimax-m3

## Findings

### [CONCERN] Persistence "generic target" claim contradicts current code

The document states "the save path already accepts a generic save target in the CLI; the PR review makes that generic on the persistence side too." The current `save_review_result` and `save_review_file` in `src/squadron/review/persistence.py` are hardwired to a `SliceInfo` TypedDict with `slice_info['index']` and `slice_info['slice_name']` driving the filename `{slice_index}-review.{review_type}.{slice_name}.{ext}`, and `format_review_markdown` writes `slice:` and `slice_index` fields into frontmatter. The CLI's `_resolve_save_outcome` does take a generic `SaveTargetT`, but the callee (`_save_and_report` / `save_review_result`) is not generic — it constructs a `SliceInfo` for arch reviews via a "minimal `SliceInfo`" pattern (see `review_arch` in `src/squadron/cli/commands/review.py`). The persistence rewrite that the principle requires is anticipated work, not present state. As written, the principle reads as a description of what is being built, not what is being extended.

### [CONCERN] Minimal-SliceInfo pattern contradiction

The document says "The existing pattern of fabricating a minimal SliceInfo so a non-slice review can be saved is not extended to PRs." But `review_arch` in `src/squadron/cli/commands/review.py` already does exactly that for arch reviews (initiative index → minimal SliceInfo). The architecture does not say whether `review_arch` should be retrofitted to the new generic target or whether its current pattern should remain. Leaving it untouched means the same architecture has two persistence shapes for "this is not a slice" — a contradiction of the "one review engine" principle.

### [CONCERN] PR metadata injection path unspecified

The document says PR metadata (title, body, linked issues, unresolved threads) is "available to the prompt as additional inputs" so the reviewer knows what the PR claims. The code template (`src/squadron/data/templates/code.yaml`) declares a fixed `diff` input and no PR-metadata slot. The review engine's `inputs` dict is templated with a closed set of names. The document does not specify whether the PR review extends the code template, augments `inputs` outside the template, or wraps the template body in a sentinel block. This is load-bearing for security (the doc itself flags PR metadata as untrusted) and for whether the "one review engine" principle actually holds.

### [CONCERN] PR review frontmatter / filename shape unspecified

The architectural principle asserts "PR-keyed persistence" satisfies the review frontmatter contract without a slice index, but the current `format_review_markdown` emits `slice: {slice_name}`, `slice_index`, `project`, and a filename prefix `{slice_index}-`. The document does not specify the PR-equivalent values for any of these, nor whether metrology (which keys on `slice:` in `src/squadron/metrology/capture.py` and `discovery.py`) needs a parallel update. Sequencing after 916/917 is mentioned, but the interface is not pinned.

### [CONCERN] Worktree lifecycle deferred to slice-level but is architectural

The document says "Concurrency with the operator's own worktrees, disk use, and cleanup on failure are the slice-level questions." These are not slice questions — they decide whether a tool-enabled PR review can run in parallel with another review, whether an interrupted review leaks disk space, and whether the design's `GIT_COMMAND_TIMEOUT_SECONDS` discipline (in `src/squadron/review/git_utils.py`) applies to the worktree teardown. Two parallel reviews with `--diff` already share git working-tree state via `review_cwd`; adding worktrees multiplies that surface. The architecture needs at least a stated invariant (e.g. one scratch worktree per review, named, cleaned up on success and on timeout) before slices can implement it.

### [CONCERN] Adapter protocol with one planned implementation

The protocol's stated value is "A second host is a new implementation, not an edit." The roadmap names GitHub via `gh` as the first implementation and lists no second host. The protocol has at least five operations (resolve, fetch head, read threads, post comment, create PR, identify operator) — each with `gh`-shaped quirks that will need to be abstracted out (e.g. "unresolved review threads" is GitHub-specific terminology; "linked issues" semantics differ across hosts). This is over-engineering for hypothetical extension and risks either a leaky abstraction (gh-specific shapes in the protocol) or a protocol so generic it cannot express host features the design implicitly relies on.

### [CONCERN] `sq pr create` model call through "existing provider-profile machinery" is undefined for non-reviews

The document says description composition "is a one-shot model call through the existing provider-profile machinery, with the same model and profile flags reviews use." The only documented model caller is `run_review_with_profile` in `src/squadron/review/review_client.py`, which is structured around `ReviewTemplate`, `ReviewResult`, and the review's required inputs. Composition is not a review. The document does not specify whether composition goes through `run_review_with_profile` with a stub template, gets its own engine function, or reuses `providers/profiles.py` directly. This is a load-bearing detail because the doc promises "deterministic parts are assembled without a model so they are exact" — which implies a non-review model path exists or will exist, and the architecture is silent on which.

### [CONCERN] PR description body omits tasks despite promising to gather them

The envisioned state says `sq pr create` "gathers the branch's commits against the target, the slice design and tasks when the branch name and `cf` identify a slice, and the latest saved review" — then names fixed body sections: "what changed, why, how it was verified, known gaps, review provenance." Tasks are not in those sections. The document does not say whether tasks are summarized into "what changed," included as a hidden block, or dropped silently. If dropped, the "gathers tasks" claim is false; if summarized, the section contract that the doc promises "an AI reviewer can parse for intent and claimed verification" widens without being named.

### [CONCERN] Default PR base for unplanned repos unspecified

The document says "`sq pr create` must respect the project's integration-branch rule: the PR targets the configured integration branch when one is set, and never `main` in that case." The very motivation paragraph is "repositories... that were often never planned in squadron at all" — meaning the typical PR-create target has no `cf`, no `project-documents/`, no integration-branch config. The architecture does not say what `sq pr create` does in that case: fail (forcing a `--base` flag), fall back to the host's default branch (which `gh pr create` would otherwise derive), or some other behavior. This is a default-behavior decision that needs to be architectural, not slice-level, because it changes how `sq pr create` is invoked in its primary use case.

### [CONCERN] Untrusted-PR-metadata framing specified, delimiter unspecified

The document says PR metadata "are injected as clearly delimited data, sized with the same truncation discipline as file injection, and never as instructions." The intent is correct (and the project rules in CLAUDE.md call out prompt-injection traps). The architecture does not specify the delimiter format (sentinel prefix? fenced block with a hostile-input label?), the truncation policy (chars vs tokens vs both, and how the truncation interacts with the "data, not instructions" framing), or which template variable carries it. Without that, the same wording could land in five different slices with five different injection shapes — defeating the security claim.

### [CONCERN] Per-failure tests for `gh` subprocess states are asserted without a strategy

The principle requires "each is a named error... and each has a test asserting that signal" for cases including `gh` missing, unauthenticated, and host unreachable. The project currently has no live integration tests against external CLIs other than `cf`, and `gh` failures are environmental (auth state, network reachability, binary presence). The architecture does not say whether these tests are unit-level (mocks the subprocess), fixture-level (a stub `gh` script), or live (CI against a sandboxed repo). The doc later in the slice list says "a live run against a real PR recorded as evidence" — which is a single end-to-end test, not per-failure coverage. The principle as written is stronger than the planned test strategy supports.

### [NOTE] Default fallback chain for rules outside a planned project contradicts "explicit degradation"

`resolve_rules_dir` in `src/squadron/review/rules.py` falls back to `~/.config/squadron/rules/` when no in-repo rules are found. The document says rules loading "degrade[s] explicitly, not silently" — but a global fallback rules directory is picked up silently by the existing function. A PR review in an unplanned repo with a global `~/.config/squadron/rules/python.md` would inject those rules without saying so. The architecture needs to either specify that this fallback is suppressed in unplanned repos or rename the degradation path (it is not "explicit" today).
