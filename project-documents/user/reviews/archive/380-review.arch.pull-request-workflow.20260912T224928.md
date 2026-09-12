---
docType: review
layer: project
reviewType: arch
slice: pull-request-workflow
project: squadron
verdict: FAIL
sourceDocument: project-documents/user/architecture/380-arch.pull-request-workflow.md
aiModel: minimax/minimax-m3
status: complete
dateCreated: 20260912
dateUpdated: 20260912
reviewedSha: bd306bc808e9f85f4045ae4ca790bbd98ba685c8
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 37
findings:
  - id: F001
    severity: fail
    category: consistency
    summary: "PR-base selection contradicts the documented integration-branch hard rule"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#technical-considerations"
  - id: F002
    severity: fail
    category: completeness
    summary: "Save-target contract surface is load-bearing but undefined"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#architectural-principles"
  - id: F003
    severity: concern
    category: abstraction
    summary: "Adapter protocol operations carry GitHub vocabulary despite the stated design rule"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#architectural-principles"
  - id: F004
    severity: concern
    category: completeness
    summary: "Base ref for merge-base computation is missing from the fetching invariants"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#technical-considerations"
  - id: F005
    severity: concern
    category: completeness
    summary: "Idempotency mechanism for posted comments is unspecified; \"must not stack\" but no contract on races"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#technical-considerations"
  - id: F006
    severity: concern
    category: feasibility
    summary: "Direct GitHub API implementation is \"designed for, not scheduled\" but is what justifies the adapter protocol"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#design-goals"
  - id: F007
    severity: concern
    category: completeness
    summary: "Scratch-worktree orphan sweep is asserted but \"alive\" is undefined"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#technical-considerations"
  - id: F008
    severity: concern
    category: feasibility
    summary: "PR description section structure is delegated to the model but enforcement is asserted, not specified"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#technical-considerations"
  - id: F009
    severity: note
    category: extension-points
    summary: "Frontmatter gains two new fields without coordination note with initiative 360"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#technical-considerations"
  - id: F010
    severity: note
    category: completeness
    summary: "Identity refusal policy stated without a mechanism"
    location: "project-documents/user/architecture/380-arch.pull-request-workflow.md#architectural-principles"
---

# Review: arch — slice 380

**Verdict:** FAIL
**Model:** minimax/minimax-m3

## Findings

### [FAIL] PR-base selection contradicts the documented integration-branch hard rule

The "PR base selection" paragraph names "the configured integration branch when `cf` reports one" as the second-preference PR target, falling through to "the host's default branch." This contradicts `CLAUDE.md`'s git rules, which define `git.integration_branch` as the local ref slice branches **fork from and merge into**, and state the hard rule: "never merge to `main` when `integration_branch` is set." `project-documents/user/analysis/942-analysis.tech-debt-audit.md:26` and `:89` (F052) already document `git_utils.py:71,149` as hardcoding `"main"` because `git.integration_branch` is a *local* concept that doesn't belong in reviewed-branch resolution. Repurposing it as a PR base (a) reverses its semantic direction — what you PR *against* vs. what you merge *into* — and (b) silently re-purposes an existing config key for a user who already set it for slice workflow. The document must either name a different key (e.g., a new `pr.base` setting) or drop this preference. As written, a user who configured `git.integration_branch=dev/erik` would have their `sq pr create` target `dev/erik` on the host, which is the opposite of how the rule is documented and the opposite of what most operators want.

### [FAIL] Save-target contract surface is load-bearing but undefined

The Architectural Principles section states the contract "is small: a target yields the filename stem, the target-specific frontmatter fields, and the reviews directory" — but does not enumerate the contract surface. Anticipated slice 3 ("PR-keyed review persistence") is explicitly tasked with *introducing* this contract, and the document says the same slice migrates the existing arch review (which today fabricates a minimal `SliceInfo` at `src/squadron/cli/commands/review.py:556-577`) onto it. Without enumerating the contract's required methods (filename stem? frontmatter extras dict? persistence directory callable? reviewers directory? integration with archiving/digest/integrity from the 900-band?), slice 3 cannot be sized, and the "migrate arch review onto it in the same slice" claim is unprovable. Additionally, the document says PR reviews persist into "the project's reviews directory when one exists or into a configured squadron-owned location when the repository has none," without naming where that configured location comes from (CLI flag? `cf` config key? home-dir default? `XDG_DATA_HOME`-style resolution?). This is precisely the kind of decision `CLAUDE.md` flags under "Never use silent fallback values." Slice 3 is not plannable from this document.

### [CONCERN] Adapter protocol operations carry GitHub vocabulary despite the stated design rule

The Host-Adapter Boundary principle states operations are "named by what squadron needs, not by any host's feature vocabulary," then the very next sentence lists "list unresolved review discussions" — GitHub's term. GitLab calls these "unresolved threads"; Gerrit has "open patch sets" / "draft comments." If the protocol is genuinely host-neutral, the operations should be named by intent (`list_unresolved_review_threads`, `post_review`, `open_pull_request`, `current_operator_identity`). As written, the principle and the example list disagree, and a second host implementation will either rename everything or carry the GitHub-isms forward. This is a load-bearing abstraction choice — pick names that describe intent and write them down.

### [CONCERN] Base ref for merge-base computation is missing from the fetching invariants

The document states the reviewed range is "merge-base to head" and that "the adapter fetches into a namespaced local ref" — but `git merge-base` requires *both* refs to exist locally. The invariants list describes fetching the head and namespacing it; they do not name the base ref's fetch (e.g., `refs/pull/N/base` on GitHub, or the host's `refs/heads/<base-branch>`). A shallow clone, a freshly-cloned repo with no `origin/main` fetch, or a PR whose base branch was never fetched locally will produce an `EmptyScopeError` (per slice 916) that the operator reads as "wrong base" rather than "fetch failed." The fix is small (fetch the base under the same namespacing discipline, or document the failure mode as a distinct error) but the document doesn't list it.

### [CONCERN] Idempotency mechanism for posted comments is unspecified; "must not stack" but no contract on races

The document says the comment "is marked so squadron can find and update its own prior comment" but does not choose between the two viable mechanisms: (a) hidden marker in the comment body discoverable via the host on every post, or (b) a local index mapping `(host, owner, repo, PR)` to the comment id. The trade-offs differ — (a) survives machine moves and CI but the marker format must not leak through the protocol and must survive body edits; (b) is faster but breaks when `sq review pr --post` is run from a fresh checkout or CI runner. The document also asserts "must not stack" but acknowledges a race between lookup and post without saying whether concurrent posts are out of contract (then "best effort" should replace "must not") or whether they are serialized somewhere. This is a load-bearing decision deferred to slice design without a clear resolution path.

### [CONCERN] Direct GitHub API implementation is "designed for, not scheduled" but is what justifies the adapter protocol

The Design Goals state the protocol is shaped "so that GitHub over its API directly ... is a second implementation with no protocol change; that implementation is designed for, not scheduled." This second implementation is the *only* thing that justifies "host behind a protocol" rather than "gh wrapper" — it is what pressure-tests the boundary and forces host-neutral naming. Without a scheduled slice, `gh`-specific shapes will inevitably leak into the protocol because nothing else exercises it. Either allocate a slice (even if deferred) in Anticipated Slices, or drop the claim and re-frame the architecture as "gh-first, with the protocol boundary maintained as a soft constraint." The auth source for this second impl is also unaddressed (`GITHUB_TOKEN` env var? `gh auth token`? app installation token? PAT?) — directly flagged by `CLAUDE.md` as the kind of decision that must be made, not hand-waved.

### [CONCERN] Scratch-worktree orphan sweep is asserted but "alive" is undefined

The invariants list cleanup on success, failure, and timeout, and add that "each invocation also sweeps: it prunes squadron-owned worktrees whose run is no longer alive before creating its own." The definition of "alive" is missing. PID file? Process group? PID namespace? `os.kill(pid, 0)`? A `SIGKILL`ed process leaves no cleanup hook; an OOM kill or machine reboot leaves no cleanup at all. The per-run id avoids *collisions* (because it is fresh per invocation), but not *accumulation* — orphans from crashed invocations sit under squadron's data directory with `git worktree` still tracking them. The document mentions no startup prune ("on `sq doctor`, list orphans") and no age-based retention. For a heavy PR-review workload, this leaks worktrees silently. Specify how "alive" is determined and add at least one startup-time sweep (e.g., prune orphans older than N days or older than the last `sq doctor` run).

### [CONCERN] PR description section structure is delegated to the model but enforcement is asserted, not specified

The document says "squadron writes the headings and asks the model only for the prose under each, then checks that every required section is present and non-empty before creating the PR." The wording is right, but the mechanism is not specified: how is the prompt structured so the model fills *under* each heading rather than rewriting the body? The section structure is also called a contract that `sq review pr` itself will parse — but the doc does not name who checks it on the read side, what schema the parser expects, or what happens when the parser sees a section it doesn't recognize. If the structure is a contract for both human and AI readers, both ends need to be specified; "ask the model" plus "check that every required section is present" is the enforcement story only at a coarse level.

### [NOTE] Frontmatter gains two new fields without coordination note with initiative 360

The Technical Considerations section adds (a) a `pr` field carrying the typed PR record, replacing slice fields, and (b) a "rules-source" provenance field for PR reviews. Initiative 360 (Document Intelligence) appears to own review-frontmatter schema (`project-documents/user/architecture/360-arch.document-intelligence.md`). The document says "The field is added in the persistence slice; existing artifacts are unaffected" — which is true for the new field — but does not record a coordination task in Anticipated Slices dependencies. Worth a coordination entry in slice 3's deps, not a blocker.

### [NOTE] Identity refusal policy stated without a mechanism

The "reads before writes, and writes are explicit" principle says "a write operation that cannot confirm the operator's identity refuses rather than posting anonymously." This is correct policy, but the *confirmation mechanism* is not named. For `gh`, the obvious answer is `gh auth status` — but the architecture should specify it (and what fields it inspects: `gh auth status` returns active account, protocol, scopes; `gh api user` is another probe). As-is, the policy is firm but the implementation is left for slice 4 to discover.
