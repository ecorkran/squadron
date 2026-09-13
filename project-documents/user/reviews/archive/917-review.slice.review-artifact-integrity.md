---
docType: review
layer: project
reviewType: slice
slice: review-artifact-integrity
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/917-slice.review-artifact-integrity.md
aiModel: z-ai/glm-5.3
status: complete
dateCreated: 20260912
dateUpdated: 20260912
reviewedSha: 44b128d0563259d92a0d92d6260a7fced37c763d
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 27
findings:
  - id: F001
    severity: pass
    category: scope
    summary: "Scope and plan alignment with the 900 maintenance container"
    location: "slices/917-slice.review-artifact-integrity.md:21-43"
  - id: F002
    severity: pass
    category: integration
    summary: "Part 2 lands on the 173 events mechanism rather than inventing a fourth enforcement path"
    location: "slices/917-slice.review-artifact-integrity.md:71-78"
  - id: F003
    severity: pass
    category: error-handling
    summary: "Part 4's overwrite decision is the fail-closed posture slice 901 established"
    location: "slices/917-slice.review-artifact-integrity.md:109-113"
  - id: F004
    severity: pass
    category: dependencies
    summary: "Consumed contracts preserved: `location_path`, the frontmatter seam, and the write-only precedent"
    location: "slices/917-slice.review-artifact-integrity.md:125-147"
  - id: F005
    severity: concern
    category: integration
    summary: "Part 4's failure artifact has no specified frontmatter, and both Part 2's gate and the pipeline gates depend on it"
    location: "slices/917-slice.review-artifact-integrity.md:109-117"
  - id: F006
    severity: concern
    category: error-handling
    summary: "Part 5 adds a new per-finding file read with no failure-mode enumeration"
    location: "slices/917-slice.review-artifact-integrity.md:129-133"
  - id: F007
    severity: concern
    category: design-quality
    summary: "\"Mark the parse degraded\" names no field or consumer, adding a third meaning to a word Part 1 exists to disambiguate"
    location: "slices/917-slice.review-artifact-integrity.md:91-96"
  - id: F008
    severity: concern
    category: process
    summary: "A default-on commit gate ships without the documentation, CHANGELOG, and architecture-update obligations 173 set for this surface"
    location: "slices/917-slice.review-artifact-integrity.md:71-78"
  - id: F009
    severity: note
    category: documentation
    summary: "\"slice 266 D5\" is a mis-citation; the requirement is slice 265's D5"
    location: "slices/917-slice.review-artifact-integrity.md:109"
  - id: F010
    severity: note
    category: scope
    summary: "XML delimiters for substituted content ride along under #25"
    location: "slices/917-slice.review-artifact-integrity.md:92"
---

# Review: slice — slice 917

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3

## Findings

### [PASS] Scope and plan alignment with the 900 maintenance container

The parent architecture (`architecture/900-arch.maintenance-and-refactoring.md#Scope`) admits "Bug fixes: Non-trivial bugs that don't belong to an active feature slice" and "Operational: Logging, error handling, configuration improvements." All six parts are that: parser correctness, commit-time enforcement of an existing enum, failure-path persistence, and debug-field disambiguation. Notably, the design moves *against* scope creep: it drops plan Part B (#28) and narrows Part C (#84) on verified evidence against `main` (`ca40196`), both of which the plan entry's own 20260912 correction block sanctions ("the slice design supersedes this entry on both"). The resequenced parts table (1–6 = E→A→F→C→D→G) matches the plan entry's corrected sequence exactly, and the effort correction 5/5→4/5 is carried through. The non-goals section (lines 45–51) explicitly fences off verdict manipulation, semantic hallucination detection, `max_tokens`, #27, and #92 — the same discipline that got slice 305 renumbered out of this initiative is applied here.

### [PASS] Part 2 lands on the 173 events mechanism rather than inventing a fourth enforcement path

The decision places `squadron.review-verdict-gate` in `src/squadron/events/builtin/`, "following the shape of `FrontmatterGateAction`," which is exactly what `architecture/140-arch.pipeline-foundation.md` prescribes for commit-bound enforcement (the events registry is the home for COMMIT bindings; the frontmatter gate is the named precedent for a built-in). It respects 173's contracts: namespaced name (`squadron.` prefix from inside `events/builtin`, permitted by D3), `events = {COMMIT}` narrowing, default binding with `disable:` opt-out (D6), and — most importantly — the fail-closed posture ("a gate that cannot determine validity must not pass") that 173's D5 and 172's D6 both mandate. Reading `Verdict` from `review/models.py` keeps a single source of truth with no parallel literal list and no cross-repo coupling, which is also consistent with 172's settled principle that "what squadron keeps is enforcement, not schema": `Verdict` is a squadron-native enum producing the value, not a duplication of Context Forge's document schema. The `docType: review` keying claim checks out against a real artifact (`reviews/916-review.slice.review-scope-correctness.md` carries both `docType: review` and `verdict: PASS` as top-level keys).

### [PASS] Part 4's overwrite decision is the fail-closed posture slice 901 established

The design explicitly reverses the plan entry's instinct ("the prior FAIL artifact was overwritten") and justifies it against the right precedent: leaving a stale verdict in the live slot is the silent pass-through that 901's UNKNOWN-fails-closed exists to prevent, so fail-closed requires the slot to hold the failure. The prior content is preserved by `archive_existing_review` (#73) with a test pinning that the failure path routes through it — so the change is "what is recorded," not "whether the run fails," with exit codes unchanged. Keeping the existing catch-alls as process-boundary handlers and adding an explicit `ProviderError` handler on each path also matches the exception-handling discipline slice 913 encoded (`BLE001` sites must be deliberate boundary handlers, logged).

### [PASS] Consumed contracts preserved: `location_path`, the frontmatter seam, and the write-only precedent

Part 5 keeps `location_path()`'s contract intact for the slice-305 findings-addressed gate (line 127), keeps diff membership out of `location_verified` (line 130), and follows the exact `ReviewResult.provenance` precedent from slice 300 — field added, written, never read, with the gate policy owned by whoever builds the gate (line 131). Part 6 puts the digest in the artifact body rather than frontmatter, naming the reason (frontmatter is the consumed cross-tool contract that Context Forge scans and Part 2 now gates; line 141), which is the same seam-awareness 911 Part C recorded. Part 6 also correctly sources the counts from the parser via `ReviewResult` rather than having the formatter re-parse (line 145), and Part 1 keeps `ReviewResult.fallback_used` and its `to_dict` key untouched (line 63), preserving the serialized consumers.

### [CONCERN] Part 4's failure artifact has no specified frontmatter, and both Part 2's gate and the pipeline gates depend on it

The design never states what `verdict:` (or `docType:`) the failure artifact carries, yet two consumers in the same slice hinge on that value. First, Part 2's own gate rejects `docType: review` with no `verdict:` key and any non-`Verdict` value (line 74) — so a failure artifact that omits the verdict or uses a sentinel like `ERROR` will be rejected at commit time in this repo, where `reviews/` is tracked. Second, the design's entire justification for overwriting the live slot is that "a pipeline gate reads a stale verdict from a previous run" (line 111) — which means the failure artifact *is* read by gates, and its verdict determines whether the fail-closed outcome actually fires (`CheckpointTrigger.ON_CONCERNS` includes UNKNOWN, per line 69). The done-when only requires the artifact be "distinguishable from a clean UNKNOWN and from a no-tools run" (line 117) without saying by what field. The design should state the frontmatter shape: the `verdict` value, whether it carries `docType: review`, and the distinguishing marker — before implementation, since Parts 2 and 4 will otherwise be reconciled by whoever writes the code.

### [CONCERN] Part 5 adds a new per-finding file read with no failure-mode enumeration

Bounds-checking a cited line requires opening and counting the cited file — new file I/O on the parse path, driven by a model-supplied path, executed once per finding. The design specifies the path-resolution story (`_path_exists_under`'s resolution, line 129) but no failure modes for the read itself: an unreadable file (permissions, IO error), a non-UTF-8 or binary file, an unbounded read against a very large cited file (the existing existence check is a cheap `Path.exists()`; this is not), or a path that resolves *outside* `cwd` (does that yield `None` "not checked" or `False` "checked and failed"?). The tri-state has no fourth state for "checked, and the check itself errored," so `False` would silently mean "hallucinated" for a real citation whose file merely could not be read — the exact conflation line 125 argues against. Slices 265/266 established the project discipline that every model-supplied path reaching a read is bounded and that no failure is silent; the done-when (line 133) covers only the happy and out-of-bounds paths. This is the one new I/O path in the slice that needs an explicit enumeration (read error → which state; size bound or line-wise count; containment).

### [CONCERN] "Mark the parse degraded" names no field or consumer, adding a third meaning to a word Part 1 exists to disambiguate

Part 1 spends its whole section separating two meanings: the debug-log field (`degraded`, renamed) means "some degraded parse happened," while `ReviewResult.fallback_used` means "findings were un-derivable from a known verdict" (lines 57–63). Part 3 then says a headingless parse is to be "mark[ed] degraded so the artifact says the format was not followed" (line 91) and "flagged degraded" (line 96), without naming what carries that mark. It cannot be `fallback_used` (findings *are* derivable in the two slice-267 cases — that would recreate the conflation Part 1 removes), and the degraded treatment in `format_review_markdown` is today *computed* from `verdict == UNKNOWN or fallback_used` (the `degraded` computation at `persistence.py:198`, cited in the 916 plan entry) — so making a good headingless review render as degraded requires either a new `ReviewResult` field plus an extension of that computation, or keying off Part 6's "whether `## Findings` was located" digest bit. The design should say which. The unstated consequence is also real: roughly 2 of ~13 real responses are headingless, so ~15% of good reviews would newly embed their full raw response.

### [CONCERN] A default-on commit gate ships without the documentation, CHANGELOG, and architecture-update obligations 173 set for this surface

Slice 173 established the obligations that come with a new built-in binding: `docs/EVENTS.md` documents the bindings and manifest format (173 success criterion 16), commit-gating behavior changes are CHANGELOG-flagged (173 flagged a strictly smaller change — the hook's PATH dependency — as CHANGELOG-worthy), and the parent architecture's `events/builtin/` listing is updated "rather than left to drift" (173's Integration Points section). `architecture/140-arch.pipeline-foundation.md` currently lists exactly three built-ins (`frontmatter_gate.py`, `dispatch_artifact.py`, `revision_stamp.py`); a fourth appears nowhere in this design's deliverables. A gate that is enabled by default and "blocks commits repo-wide" (line 153) is undiscoverable by users except via `sq events list` if it is not documented. Relatedly, the frontmatter declares `interfaces: []` (line 7) despite introducing a namespaced, disableable public identifier. Adding these as explicit deliverables is cheap now and expensive to retrofit.

### [NOTE] "slice 266 D5" is a mis-citation; the requirement is slice 265's D5

The design attributes the "'given tools, said nothing' is distinguishable from 'ran without tools'" requirement to "slice 266 D5." Slice 266's D5 is a landing-order decision ("Item (a) lands first within the slice. It is the only security item."). The requirement quoted is slice **265's** D5 — "`tools_given` is present with `tool_calls_made: 0` when tools were offered and unused. Emitting nothing in that case would collapse it with 'no tools offered'" — with 266's SC4 covering the suppression variant. The error is inherited verbatim from plan entry 15's Part C ("the state slice 266's D5 requires be distinguishable"). The work is justified either way; only the citation is wrong, and it is worth correcting since this slice's whole method is citing verified precedent.

### [NOTE] XML delimiters for substituted content ride along under #25

Change 3's primary move — fencing the specimen in the four templates — is squarely within the #25 fold-in the plan entry authorizes ("fold it in as the complementary prompt-side change once the parser is bounded"). The trailing clause "Delimit substituted document content with XML tags while there" is a second, distinct prompt-structure change to all four templates beyond fencing the specimen. It is covered by a done-when ("templates carry the fenced specimen and the #25 delimiters"), so it is specified rather than implicit, and it serves the same goal (keeping finding-shaped substituted content out of the parsed region). Worth confirming it is actually within #25's filed scope rather than a drive-by, but it does not warrant re-scoping.
