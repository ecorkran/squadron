---
docType: review
layer: project
reviewType: code
slice: review-artifact-integrity
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/917-slice.review-artifact-integrity.md
aiModel: z-ai/glm-5.3
status: complete
dateCreated: 20260912
dateUpdated: 20260912
reviewedSha: 20653392ce8c47084c0571ea30e6ada454f671ab
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 32
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "`summary_section_located` is False for well-formed reviews that contain findings"
    location: "src/squadron/review/parsers.py#_locate_section"
  - id: F002
    severity: concern
    category: telemetry
    summary: "`toolCallsMade: 0` asserts \"offered, used none\" when the raiser offered no count"
    location: "src/squadron/providers/openai/agent.py#_run_agentic_loop"
  - id: F003
    severity: concern
    category: async
    summary: "Blocking subprocess and file I/O added inside the async pipeline review action"
    location: "src/squadron/pipeline/actions/review.py#ReviewAction._review"
  - id: F004
    severity: concern
    category: performance
    summary: "Line-bounds check repeats the full path resolution already done by path-existence"
    location: "src/squadron/review/parsers.py#_check_line_bounds"
  - id: F005
    severity: concern
    category: error-handling
    summary: "Verdict gate fails closed on staged-but-absent paths, and its stated justification is inaccurate"
    location: "src/squadron/events/builtin/review_verdict_gate.py#ReviewVerdictGateAction._check"
  - id: F006
    severity: note
    category: design
    summary: "Transient provider errors now overwrite the live review slot"
    location: "src/squadron/cli/commands/review.py#_run_review_command"
  - id: F007
    severity: note
    category: correctness
    summary: "Multi-part tasks failure artifact lands in the unsuffixed slot"
    location: "src/squadron/review/persistence.py#save_provider_failure"
  - id: F008
    severity: note
    category: consistency
    summary: "Failure and success artifacts can resolve against different roots"
    location: "src/squadron/review/persistence.py#save_review_result"
  - id: F009
    severity: note
    category: parsing
    summary: "Fence regex requires an exactly-equal-length closing fence"
    location: "src/squadron/review/parsers.py#_mask_fences"
  - id: F010
    severity: pass
    category: design
    summary: "Provider-failure artifact design is fail-closed, archive-preserving, and verified end-to-end"
    location: "src/squadron/review/persistence.py#save_provider_failure"
  - id: F011
    severity: pass
    category: testing
    summary: "Bounded-scan tests use real fixtures and pin mechanisms, not just outcomes"
    location: "tests/review/test_templates.py"
---

# Review: code — slice 917

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3

## Findings

### [CONCERN] `summary_section_located` is False for well-formed reviews that contain findings

`_locate_section` ends with a Findings-specific fallback: `if _count_finding_matches(text[start:end]) == 0 < _count_finding_matches(text): return None` — added so a `### Findings` heading (which closes before its own same-level findings) falls back to the whole-response scan. But `parse_review_output` reuses the same function for `"summary"`: `summary_section_located = _locate_section(_mask_fences(raw_output), "summary") is not None`. A summary section is *supposed* to contain zero finding-shaped text, so for any review with both a `## Summary` heading and at least one finding — the canonical healthy shape, e.g. `WELL_FORMED_CONCERNS` in tests/review/test_parsers.py — the fallback condition is true, `_locate_section` returns `None`, and `summary_section_located` becomes `False`. `_run_digest_lines` (persistence.py) then persists `` `## Summary` located: no `` into the artifact for a document that plainly opens with `## Summary` — precisely the misinformation the digest (#93) was built to eliminate. The only test asserting `True` (`test_summary_section_located_is_recorded`) uses a document with no findings, the one shape where the heuristic doesn't fire, so the bug is untested. Fix: locate the summary heading without the findings-specific fallback (e.g. gate the fallback on the section name, or use a plain heading-exists check for "summary").

### [CONCERN] `toolCallsMade: 0` asserts "offered, used none" when the raiser offered no count

`ProviderError.__init__` documents `tool_calls_made=None` as "the raiser had no count to offer", but several raise sites in `agent.py` omit the count even though it is known — most notably the final `raise ProviderError(f"Agentic loop exceeded agent.max_tool_iterations ...")`, where the live `tool_calls_made` local is in scope and by definition nonzero (the model spent its whole budget calling tools). The same is true of the no-id tool-call raise and of the `ProviderAuthError`/`ProviderAPIError`/`ProviderTimeoutError` wrappers in `handle_message` (a timeout after N tool calls also carries `None`). `_review_frontmatter_lines` (src/squadron/review/persistence.py) renders this as `toolCallsMade: {tool_calls_made or 0}` → `0`, which the same PR's design comments define as "offered, used none". The failure artifact then asserts the opposite of what happened. Either pass the count at the two loop raise sites (trivial) or render an explicit unknown rather than a confident 0 — the PR itself builds `_render_tristate` for exactly this distinction and does not apply it here. `tests/review/test_persistence.py::test_missing_count_renders_as_zero_not_absent` pins the 0-render, so this is deliberate, but it contradicts the D5 semantics the rest of the change establishes.

### [CONCERN] Blocking subprocess and file I/O added inside the async pipeline review action

The new `except ProviderError` handler in `async def _review` calls `save_provider_failure(...)`, which invokes `resolve_reviewed_sha(cwd)` → `run_git` → `subprocess.run(..., timeout=GIT_COMMAND_TIMEOUT_SECONDS)` — a blocking subprocess bounded at 30 seconds — plus `archive_existing_review`/`write_text`, all synchronously on the event loop. The project rule is explicit (any sync code inside an `async def` must be <1 ms worst case), and the sibling `frontmatter_gate.py` docstring states the convention directly ("never a blocking subprocess call inside an async function"), using `asyncio.create_subprocess_exec` accordingly. The success path already violates this (`resolve_reviewed_sha` inside the `format_review_markdown(...)` call and inside `save_review_result`), so this change extends a pre-existing pattern rather than introducing it — but the new failure path is fresh code and should move the save off-loop (e.g. `asyncio.to_thread`). Relatedly, `ReviewVerdictGateAction.execute` does sync `read_text` + `yaml.safe_load` per staged file inside an async method; small files and an otherwise-idle commit-hook loop make this low risk, but it is the same rule.

### [CONCERN] Line-bounds check repeats the full path resolution already done by path-existence

`_check_line_bounds` calls `_resolve_under(cwd, path)` for every line-cited finding, immediately after `_check_path_existence` resolved the *same* citation through `_path_exists_under` → `_resolve_under`. For bare filenames and hallucinated names — exactly the citations these checks target — `_resolve_under` falls back to `root.rglob(path)`, a full tree walk that runs to the match or to exhaustion. Each phantom citation therefore costs two complete walks of the review root (which `_resolve_review_cwd` anchors at the git root), plus up to 4 MB of synchronous reads per resolved file (`_MAX_LINE_CHECK_BYTES`), all inside `parse_review_output`, which the pipeline action awaits. With the #91-shaped response (dozens of phantom findings), this is seconds of event-loop blockage. Resolve once per finding and share the result between the two checks, or fold both checks into a single pass.

### [CONCERN] Verdict gate fails closed on staged-but-absent paths, and its stated justification is inaccurate

The comment claims "Deleted-but-staged paths do not reach here: git stages the deletion, and the reader is only asked for paths still present." That is not the mechanism: git lists deleted paths in `git diff --cached --name-only` just fine — what keeps them out is `.githooks/pre-commit`'s `--diff-filter=ACMR`. That filter includes `R`, and with `-z --name-only` a staged rename emits *both* the old and new path; after `git mv old.md new.md` the old path no longer exists in the worktree, so `_check` receives an `OSError` and blocks a legitimate rename with the misleading "could not read frontmatter to check its verdict" message. I could not verify whether `cf validate frontmatter` (which receives the same path list via the frontmatter gate) already fails identically on the missing old path — if it does, this is consistent-with-existing rather than new breakage. At minimum the comment should state the real mechanism (the hook's diff filter, which the gate cannot itself rely on); ideally the gate would distinguish "path absent from the worktree" (skip, or say so plainly) from "present but unreadable" (fail closed).

### [NOTE] Transient provider errors now overwrite the live review slot

Through the agent, rate limits and timeouts are wrapped into `ProviderAPIError`/`ProviderTimeoutError` — subclasses of `ProviderError` — so they take the new failure-artifact branch, not the pre-existing `except RateLimitError` branch (which only catches a raw, unwrapped openai error that escapes the agent). A transient failure therefore archives the prior review and installs `verdict: UNKNOWN` in the live slot. This matches the documented fail-closed intent (a stale PASS must not wave the next gate through) and the prior content survives in `archive/`, but a rate-limited run now costs the live slot; distinguishing transient from terminal provider errors would avoid that trade-off.

### [NOTE] Multi-part tasks failure artifact lands in the unsuffixed slot

`save_provider_failure` has no `name_suffix` parameter. In `review_tasks` (src/squadron/cli/commands/review.py), every part passes the same `failure_target=slice_info`, so a provider failure in part N of a split tasks review writes `{index}-review.tasks.{slice_name}.md` — a slot no success path ever writes (parts write `.part-N.md`) — and repeated failures across parts overwrite one another in that single slot (each archived on the way). The failure is still recorded and the command exits 1, but the artifact cannot be tied to the failing part.

### [NOTE] Failure and success artifacts can resolve against different roots

The failure path saves via `save_review_file(..., cwd=inputs.get("cwd"))`, where `inputs["cwd"]` is `review_cwd` — the git root, per `_resolve_review_cwd` (issue #86). The success path saves via `save_review_result`, which resolves `REVIEWS_DIR` against the process working directory and accepts no `cwd`. When `sq review` is invoked from a subdirectory of the repository, the two paths write into different `project-documents/user/reviews` trees. The failure path's anchoring is the more correct of the two; the success-path behavior is pre-existing.

### [NOTE] Fence regex requires an exactly-equal-length closing fence

`_FENCE_RE` closes a fence with a backreference (`(?P=fence)`), so the closing fence must be exactly as long as the opener. CommonMark permits a closing fence *at least* as long as the opening one, so a ``` block closed with ```` is valid markdown this regex treats as unclosed — masking everything to end of document and silently dropping every finding after it. The run digest's "inside fences" count makes the anomaly observable (which is why this is a note), but per the project's own lenient-parsing rule ("a regex that silently fails on valid input is a bug"), an at-least-as-long closer would be safer given the failure mode is dropping real findings.

### [PASS] Provider-failure artifact design is fail-closed, archive-preserving, and verified end-to-end

`UNKNOWN` is a real `Verdict` member, so the new commit gate accepts the failure artifact rather than rejecting the record of the failure itself; the prior artifact is archived (with the single-slot/timestamped-generation protections) rather than destroyed; a slice-less run refuses to fabricate `slice 0`, names the file from the step, and warns instead of silently writing nothing. `tests/review/test_persistence.py::TestProviderFailureArtifact::test_saved_failure_passes_the_verdict_gate` closes the loop between writer and gate end-to-end, and the extracted `_review_frontmatter_lines` removes what would otherwise be a second, drifting copy of the frontmatter block. (Subject to the `toolCallsMade` concern above.)

### [PASS] Bounded-scan tests use real fixtures and pin mechanisms, not just outcomes

`test_specimen_is_inside_a_fence` substitutes a real severity into each template's specimen before asserting the fence holds — pinning the mechanism rather than the outcome, since the unfenced specimen's `[PASS|CONCERN|FAIL]` alternation happens not to match the finding regex and the outcome-only test would pass unfenced. `TestHeadinglessRealReviews` (tests/review/test_parsers.py) uses two real 267 responses as fixtures, which is exactly the project's "test fixture must include the actual format the parser will consume" rule, and it guards the whole-response fallback that keeps headingless reviews parsing — the right posture of never dropping real findings to exclude phantoms.

### Run Digest

- Response length: 12478 chars
- Tool calls made: 32
- `## Summary` located: no
- `## Findings` located: yes
- Finding-shaped matches — whole response: 11
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 11
- Finding-shaped matches — surviving validation: 11
