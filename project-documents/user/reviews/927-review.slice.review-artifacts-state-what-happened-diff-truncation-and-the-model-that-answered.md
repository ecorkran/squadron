---
docType: review
layer: project
reviewType: slice
slice: review-artifacts-state-what-happened-diff-truncation-and-the-model-that-answered
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/927-slice.review-artifacts-state-what-happened-diff-truncation-and-the-model-that-answered.md
aiModel: claude-opus-5-5
status: complete
dateCreated: 20260926
dateUpdated: 20260926
reviewedSha: 4748b63cb65fb640ceebb1de1c925d215f66886c
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 11
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "Part B lets any successful tool call cancel the cap, but no tool can recover the missing diff"
    location: "project-documents/user/slices/927-slice.review-artifacts-state-what-happened-diff-truncation-and-the-model-that-answered.md:131-135"
  - id: F002
    severity: note
    category: specification
    summary: "What gets recorded for an empty diff isn't specified"
    location: "project-documents/user/slices/927-slice.review-artifacts-state-what-happened-diff-truncation-and-the-model-that-answered.md:117-119"
  - id: F003
    severity: note
    category: consistency
    summary: "The `VerdictSource` docstring needs updating along with the enum"
    location: "project-documents/user/slices/927-slice.review-artifacts-state-what-happened-diff-truncation-and-the-model-that-answered.md#d5--verdictsourceimposed"
  - id: F004
    severity: note
    category: specification
    summary: "Walkthrough step 6 says \"one run per profile\" but hardcodes `--model sonnet`"
    location: "project-documents/user/slices/927-slice.review-artifacts-state-what-happened-diff-truncation-and-the-model-that-answered.md:348-353"
  - id: F005
    severity: note
    category: scope
    summary: "Three parts in one slice is on the heavy side for this initiative"
    location: "project-documents/user/slices/927-slice.review-artifacts-state-what-happened-diff-truncation-and-the-model-that-answered.md:375"
  - id: F006
    severity: pass
    category: integration
    summary: "CLI/pipeline parity comes from the structure, not from duplicated code"
    location: "project-documents/user/slices/927-slice.review-artifacts-state-what-happened-diff-truncation-and-the-model-that-answered.md:101"
  - id: F007
    severity: pass
    category: error-handling
    summary: "Failure modes are enumerated for every new signal"
    location: "project-documents/user/slices/927-slice.review-artifacts-state-what-happened-diff-truncation-and-the-model-that-answered.md#d11--not-reported-keep-the-requested-id-say-so-in-the-artifact"
  - id: F008
    severity: pass
    category: integration
    summary: "Changing what `aiModel` means is called out, including the one-time metrology identity shift"
    location: "project-documents/user/slices/927-slice.review-artifacts-state-what-happened-diff-truncation-and-the-model-that-answered.md:196"
---

# Review: slice — slice 927

**Verdict:** CONCERNS
**Model:** claude-opus-5-5

## Findings

### [CONCERN] Part B lets any successful tool call cancel the cap, but no tool can recover the missing diff

D4 skips the cap whenever `tool_calls_made - failed_tool_calls > 0`. That counts any call at all: a `Glob`, a `Grep` for a symbol, a `Read` of `CLAUDE.md`. The plan's wording is narrower: "a truncated diff where the model *did read files*" (`900-slices…md:442`). The code also says outright that the diff "is not a file body, and no read-only tool can reconstruct it (issue #81)" (`src/squadron/review/review_client.py:390-391`). So one unrelated `Glob` puts us back in the #135 failure: a PASS on a diff the model never fully saw, with only `diffTruncated: true` to show for it.

That makes the Value claim at line 27 ("a PASS means the model either saw the whole diff or read files with its tools") stronger than the rule delivers. Two ways out:

- Keep the rule, soften the line 27 claim, and add a Run Digest line whenever a truncated diff kept its PASS because of tool calls. That way a human sees the exemption was used.
- Narrow the rule to reads of files in `diff_files`. This needs per-call tool names in telemetry, which today only records counts (`models.py:133-158`).

The first is the cheap one and fits the slice. Either way, the rule is currently wider than the plan's wording, so name the choice explicitly.

**Response:** Accepted, option 1. D4 now states that the exemption is deliberately wider than "read the missing files" and explains why narrowing it needs per-call telemetry. A kept PASS on a truncated diff adds a `Diff coverage:` Run Digest line. The Value claim is reworded to match, and SC5 covers the digest line.

### [NOTE] What gets recorded for an empty diff isn't specified

D2 keys on whether `inputs` has a `diff` key. But `_inject_file_contents` only injects when `_run_git_diff` returns something (`review_client.py:423`, `if diff_content:`). When the key is present and the diff is empty (wrong ref, or nothing changed), the design doesn't say whether `diff_injection` is `None` (key absent) or `DiffInjection(0, 0)` (`diffTruncated: false`). Pick one and add it to the SC3 test. `false` is the honest answer: the model did see all zero characters.

**Response:** Accepted. D2 specifies that an empty diff records `DiffInjection(0, 0)` and writes `diffTruncated: false`. SC3 covers it.

### [NOTE] The `VerdictSource` docstring needs updating along with the enum

`models.py:29-39` describes `VerdictSource` as "a closed two-value vocabulary" that answers "did the model say this?". D5's reasoning is sound: the vocabulary stays closed and the original objection was to open-ended reason strings. But `IMPOSED` changes what the field answers. Add the docstring rewrite to the Component Structure row for `review/models.py`.

**Response:** Accepted. The `review/models.py` row now includes the docstring rewrite: the field answers "where did this verdict come from?", and the vocabulary stays closed.

### [NOTE] Walkthrough step 6 says "one run per profile" but hardcodes `--model sonnet`

The step is supposed to capture real answering-model ids for sdk, openai, openrouter, and local, but the command pins `--model sonnet`. Unless `sonnet` resolves on every profile, the openai and local runs will fail or capture ids nobody configured. Use each profile's default alias (or `--profile X` without `--model`), since those are the ids D9 has to handle correctly.

**Response:** Accepted. Step 6 now runs `sq review slice 927 --profile <profile> -v` with no `--model`, so each run uses that profile's default.

### [NOTE] Three parts in one slice is on the heavy side for this initiative

The 900 guidelines prefer many small, independently deliverable slices. Parts A and C are independent (line 375) and touch different layers: injection versus providers. The plan bundled them on purpose under one principle, and both land on the same artifact fields, so this isn't a blocker. Just keep the commits per part so either half can be reverted on its own.

**Response:** Accepted as written. The slice stays whole, and Development Approach now requires a separate commit per part.

### [PASS] CLI/pipeline parity comes from the structure, not from duplicated code

Both paths call `run_review_with_profile` (verified at `pipeline/actions/review.py:274`) and render through `format_review_markdown`. Every new fact rides on `ReviewResult`, so there's no second code path that can drift. This meets the interface-parity requirement from plan line 441.

### [PASS] Failure modes are enumerated for every new signal

The slice adds no new I/O. It reads fields from streams that already exist. Each degraded case has explicit handling that shows up in the artifact or logs:

- Provider reports nothing: D11, digest line, no made-up id.
- Several models answer: D12, WARNING plus digest.
- `<synthetic>` placeholders and subagent messages: D8.
- Diff skipped by the total limit: D3.
- A degraded parse hidden behind the synthetic finding: D6.
- Cap ordering relative to the recovery turn: line 380, which matches `review_client.py:271-278`.

The architecture doc sets no performance targets, so there's nothing to restate there.

### [PASS] Changing what `aiModel` means is called out, including the one-time metrology identity shift

`aiModel` changes meaning, and D10 says so. It also names the knock-on effect: OpenAI dated snapshots shift metrology identity once. The context-forge reader check behind `verdictSource` is dated (D5). The artifacts for provider failures are deliberately left alone (D13) so that `requestedModel` keeps meaning exactly one thing: the model was substituted. Every downstream contract is either additive or explicitly acknowledged.

### Run Digest

- Response length: 6932 chars
- Response is newline-free: no
- Tool calls made: 11
- Tool calls failed: 0
- Stop reason: end_turn
- Reasoning characters: 0
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
