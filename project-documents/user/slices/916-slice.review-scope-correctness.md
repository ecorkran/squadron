---
docType: slice-design
slice: review-scope-correctness
project: squadron
parent: 900-slices.maintenance-and-refactoring.md
dependencies: []
interfaces: [917]
dateCreated: 20260910
dateUpdated: 20260910
status: not_started
---

# Slice Design: Review Scope Correctness — Diff Resolution, Empty-Scope Verdicts, and Tool Jail Roots

## Overview

Five defects on the `sq review` entry path, all answering one question: **did the review examine the change set the operator meant, and was it equipped to read it?** Each is small; together they are the difference between a review a reviewer can act on and one they must independently re-verify.

They are bundled because they share a surface — `cli/commands/review.py`, `review/git_utils.py`, and the four review templates — and because two of them (A and B) were observed on the *same* live PR review. The wrong subject and the empty subject are two halves of one credibility failure.

Motivating context: squadron reviews are moving toward PR-centric use against enterprise repositories, where a branch is routinely several merges behind its base. Every defect here fires under exactly those conditions, and three of them fail *silently* — a confident artifact with no signal that anything went wrong.

## Value

Developer-facing, and specifically **trust-facing**. A review tool whose verdict is sometimes about the wrong diff is worse than no review tool: it consumes attention and spends credibility. Part A produced a top-line FAIL asserting a PR reverted security fixes it never touched; Part B produced a PASS that cleared a gate having examined zero lines. Both look authoritative. Neither is.

After this slice:

- `--diff <ref>` reviews the branch's own changes, matching what GitHub shows for the same PR.
- A review that examined nothing says so and fails, rather than passing.
- A review that could not be persisted exits non-zero, in every subcommand.
- Tool-enabled `slice`/`arch`/`tasks` reviews can open their own input documents.
- An SDK reviewer's tool set matches what its template declares.

## Technical Scope

**Included** — five parts, sequenced D → A → C → B → E:

| Part | Issue | Surface |
|---|---|---|
| D | #86 | `review_slice`/`review_arch`/`review_tasks` jail root |
| A | #89 | `--diff` merge-base normalization |
| C | #70 | save gating in all four subcommands |
| B | #62 | empty-filtered-scope outcome |
| E | #69 | SDK tool availability |

[Issue #71](https://github.com/ecorkran/squadron/issues/71) (merged-slice empty review, unreproduced) is carried for verification after B rather than given its own part — see Part B.

**Excluded:**

- The `Verdict` enum gains no member (Part B decision).
- No change to how findings are parsed, scored, or persisted — that is slice 917.
- No re-include mechanism for excluded file types; #62's scope note declines it and this slice honors that.
- No SDK version upgrade ([issue #30](https://github.com/ecorkran/squadron/issues/30)) — Part E works on the pinned `claude-agent-sdk>=0.1.38`, verified below.
- `max_tokens` sizing, empty-turn telemetry, verdict frontmatter validation — all 917.

## Dependencies

### Prerequisites

None. All five parts are independently landable against current `main`.

### Interfaces Required

- `resolve_diff_base()` / `find_git_root()` (`review/git_utils.py`) — exist and are used by `review_code` today; Parts A and D extend their reach rather than adding machinery.
- `claude_agent_sdk.ClaudeAgentOptions.tools` — **verified present on the pinned 0.1.38**, and `subprocess_cli` emits it as `--tools` (a list joins comma-separated; an empty list emits `--tools ""`). Part E does not depend on #30.

## Architecture

### Part D — Tool jail root (#86)

`review_slice`/`review_arch`/`review_tasks` pass `_resolve_cwd(cwd)` straight through as `inputs["cwd"]`, which becomes `AgentConfig.cwd` — the `read_file`/`list_files`/`grep` jail root ([review.py:597](src/squadron/cli/commands/review.py#L597), [:655](src/squadron/cli/commands/review.py#L655), [:756](src/squadron/cli/commands/review.py#L756)). Meanwhile the prompt presents repo-root-relative document paths resolved via Context Forge. With a subdirectory `cwd` config (`cwd = "./project-documents/user"`) the segment doubles and the model cannot open its own inputs.

`review_code` already resolves this at [review.py:874](src/squadron/cli/commands/review.py#L874) and `review_resolve` at [:1035](src/squadron/cli/commands/review.py#L1035):

```python
review_cwd = find_git_root(resolved_cwd) or resolved_cwd
```

**Design:** apply the identical resolution at the three remaining sites, and pass `review_cwd` to `resolve_rules_dir` there as `review_code` does at [:890](src/squadron/cli/commands/review.py#L890).

**D1 — extract, do not copy a fourth time.** Five call sites doing the same two-line dance is the duplication the project rule forbids. Introduce one private helper in `review.py` returning the pair `(review_cwd, resolved_rules_dir)` from `(cwd, rules_dir_flag)`, and route all five subcommands through it. This is why D leads the sequence: it is the smallest change, it touches the same function bodies the later parts edit, and doing it first means A/B/C edit already-consolidated code.

*Not a traversal defect.* `resolve_in_jail` behaves correctly; it is being handed inconsistent inputs. Nothing about the jail's containment weakens here — the root moves outward from a subdirectory to the repo root, which is the root the prompt's paths were always relative to.

### Part A — `--diff` merge-base normalization (#89)

[Issue #32](https://github.com/ecorkran/squadron/issues/32)'s fix added merge-base resolution to `resolve_slice_diff_range`, which [review.py:849-852](src/squadron/cli/commands/review.py#L849-L852) calls **only when `--diff` is absent**. An explicit `--diff origin/main` reaches:

1. `extract_diff_paths` ([rules.py:202](src/squadron/review/rules.py#L202)) — a literal `git diff --name-only <ref>`, and
2. the prompt builder ([builders/code.py:32](src/squadron/review/builders/code.py#L32)) — interpolated verbatim into a `Run \`git diff {diff}\`` instruction the model executes.

Both then compare against the *current tip* of the ref, so anything the base gained since the fork point is reported as this branch deleting it.

**A1 — normalize the value once, at the CLI edge, before either consumer sees it.** The two consumers must never disagree about what is under review. Normalization happens immediately after the `--diff` value is read, and the normalized string is what flows onward.

**A2 — normalization is by *shape*, not by guessing intent.** A new `normalize_diff_spec(spec, cwd)` in `review/git_utils.py`:

| Input shape | Treatment | Rationale |
|---|---|---|
| contains `...` | pass through unchanged | already merge-base semantics; the caller was explicit |
| contains `..` | pass through unchanged | an explicit two-dot range is an explicit request |
| bare ref (no range operator) | rewrite to `<ref>...HEAD` | **the bug**: this is the "review my branch against this base" case |

Only the third row changes behavior. `--diff origin/main` becomes `origin/main...HEAD`, which is what GitHub computes for a PR against `origin/main` and what `resolve_slice_diff_range` already produces on the slice-number path. Note the fix is *not* calling `resolve_slice_diff_range` — that function is slice-number-shaped and returns `merge_base...branch`; A needs the same **semantics** applied to a user-supplied ref.

**A3 — three dots, not a resolved SHA.** `<ref>...HEAD` is handed to git rather than pre-resolving the merge-base ourselves. Git computes the same answer, the string stays legible in the prompt and in `reviewedSha` provenance, and there is one less resolution path to keep correct. `resolve_slice_diff_range` pre-resolves because it must detect the fully-merged case; A has no such requirement.

**A4 — a bare ref that does not resolve fails loudly.** Guard with `_resolve_rev(ref, cwd)` before rewriting. `git diff` against a nonexistent ref currently yields an empty path list ([rules.py:218-220](src/squadron/review/rules.py#L218-L220) swallows the failure and returns `[]`) — which under Part B would present as "nothing in scope" rather than "you typed a ref that does not exist." Distinguish the two: a `--diff` value naming an unresolvable ref exits non-zero with the offending value, before any model call.

**A5 — the two-dot form stays reachable, unchanged, and undocumented as a feature.** Someone who writes `--diff a..b` gets exactly that. No new flag is added: the shape already expresses the distinction, and a flag would be a second way to say something the argument already says.

### Part C — Save gating (#70)

All four subcommands initialize `saved = True` and overwrite it only inside a branch gated on an identifier that `--diff`/`--files`-only runs never supply ([:616](src/squadron/cli/commands/review.py#L616), [:673](src/squadron/cli/commands/review.py#L673), [:760](src/squadron/cli/commands/review.py#L760), [:930](src/squadron/cli/commands/review.py#L930)). The review runs, prints, writes nothing, exits 0. This is precisely what `_save_and_report`'s docstring ([:190-193](src/squadron/cli/commands/review.py#L190-L193)) says must not happen — the guard lives inside the function this path never calls.

**C1 — the initializer is the bug; invert the default.** `saved` starts `False` and becomes `True` only on a real write or a real `--no-save`. Optimism about an unperformed write is the whole defect.

**C2 — distinguish "chose not to save" from "could not save."** `--no-save` is a deliberate instruction and must keep exiting 0. Model the three outcomes explicitly rather than through one boolean's history:

- **saved** — artifact written; exit on verdict.
- **suppressed** — `--no-save` given; exit on verdict.
- **unsaved** — a save was expected and did not happen; exit 1 regardless of verdict, per `_exit_on`'s existing precedence ([:273-285](src/squadron/cli/commands/review.py#L273-L285)).

A small enum, per the project rule against user-visible labels and scattered comparison values.

**C3 — a `--diff`-only run is "unsaved," not "suppressed."** This is the decision that fixes the issue. Today no artifact path can be derived without a slice identifier, so the run genuinely cannot persist. Rather than inventing a naming scheme for slice-less reviews (out of scope, and a naming decision that deserves its own thought), the run **fails with an actionable message**: it names why no artifact could be written and what to supply. This is Part B's shape and #17's shape — an input problem reported as an input problem.

**C4 — all four subcommands, one mechanism.** #70 was filed against `code`; the reading above confirms all four carry it. Interface parity is a standing project rule.

### Part B — Empty filtered scope (#62)

When `diff_exclude_patterns` ([code.yaml:72-85](src/squadron/data/templates/code.yaml#L72-L85)) filters every changed file out of the range, the reviewer correctly reports that nothing was in scope — at severity `note`, leaving `verdict: PASS`. Observed clearing a review gate on slice 362 with zero lines examined.

**Decision (recorded in the plan entry, 20260910): refuse to persist and exit non-zero. No new `Verdict` member.**

Rejected alternative — a `NOT_APPLICABLE` / `NO_SCOPE` verdict — on two grounds:

1. **It models the event wrongly.** A verdict says "a review happened and this was its answer." Nothing was reviewed. That is an input error of the same kind as Part C and [#17](https://github.com/ecorkran/squadron/issues/17), and earns the same treatment.
2. **The gates are allowlists, not exhaustive switches**, so a new member is silently mishandled in three directions rather than caught:

| Consumer | Shape | A new member would |
|---|---|---|
| `CheckpointTrigger.ON_CONCERNS` ([checkpoint.py:22](src/squadron/pipeline/actions/checkpoint.py#L22)) | `{CONCERNS, FAIL, UNKNOWN}` | not trip — waved through |
| `LoopCondition.REVIEW_CONCERNS_OR_BETTER` ([executor.py:249-252](src/squadron/pipeline/executor.py#L249-L252)) | `{PASS, CONCERNS}` | never satisfy — loop never converges |
| `_aggregate_verdicts` rank ([review.py:333](src/squadron/cli/commands/review.py#L333)) | bare dict subscript | raise `KeyError` |

Two further consumers assume the closed set: `_LEG_VERDICT_TO_RESOLUTION` ([resolution.py:70-72](src/squadron/review/resolution.py#L70-L72)) and the `degraded` computation at [persistence.py:198](src/squadron/review/persistence.py#L198). And `workflow.review_threshold` has **no consumer in squadron** — review gating lives in Context Forge, so a new member is additionally a cross-repo contract change.

Refusing to persist fixes the reported harm directly: no artifact clears no gate, in either repo, with no coordination.

**B1 — detect before the model call, not after.** `extract_diff_paths` already runs at [review.py:893](src/squadron/cli/commands/review.py#L893), before any provider work. An empty result there is the signal. Detecting pre-flight also avoids spending a model call to be told what git already said, and means the failure message can name the exclusion patterns responsible.

**B2 — distinguish empty-after-filtering from empty-before-filtering.** Two different operator errors deserving two different messages:

- Range resolved, had changed files, **all excluded** → name the matched patterns and the excluded file count. The operator likely wants the review omitted, or a different range.
- Range resolved to **no changed files at all** → the range itself is the problem (wrong base, already-merged branch, typo).

Both exit non-zero; both must be distinguishable in the message. Conflating them is how #71 stayed unexplained for weeks.

**B3 — accepted consequence, and the escape hatch is verified to exist.** A pipeline whose slice is genuinely all-docs now fails rather than passing. That is true and visible, and it makes an existing convention load-bearing: per #62's scope note, a slice whose substantive change is documentation or a skill prompt is covered by design and task reviews with the code review omitted.

The plan entry required confirming that omission is expressible today. **It is:** `PhaseStepType.expand` emits the review action only when the `review:` key is present ([phase.py:76](src/squadron/pipeline/steps/phase.py#L76), `if review is not None`; [:163](src/squadron/pipeline/steps/phase.py#L163) for the action list). There is no `none` literal and none is needed — omitting the key suppresses both the review and its checkpoint. No pipeline-surface work is required by this part; the design records the mechanism so task breakdown does not go looking for a feature that does not need building.

**B4 — #71 verification, not a fix.** #71's own analysis rules out the merge-subject grep and names the exclusion filter as the leading candidate — which is exactly this part. After B lands, re-run #71's reproduction script in the reporting repo. If B's new message explains it, close #71. If not, re-file with the new evidence. No code in this slice is written *for* #71.

### Part E — SDK tool availability (#69)

Squadron sets only `AgentConfig.allowed_tools` → `ClaudeAgentOptions.allowed_tools` → `--allowedTools` ([providers/sdk/provider.py:64-66](src/squadron/providers/sdk/provider.py#L64-L66)). That flag is a **permission allowlist** — it pre-approves tools that would otherwise prompt. Availability is governed by a separate `tools` → `--tools` field squadron never sets, so with it unset the CLI supplies its full default tool set, including unrestricted `Bash`.

Compounding it, all four templates set `permission_mode: bypassPermissions`, which approves everything regardless — so `--allowedTools` is inert there anyway.

So `allowed_tools` means a **capability gate** on the non-SDK path (the name materializes an executor from the registry; omitting `bash` means no shell exists) and **nothing** on the SDK path. All four templates already declare exactly `[read_file, list_files, grep]`, so 265's D6 has landed and only the SDK path fails to honor it.

**E1 — set `tools` from the same declared list, at the same edge.** In `provider.py`'s kwargs build, alongside the existing `allowed_tools` translation:

```python
kwargs["tools"] = translate_tool_names(config.allowed_tools)
```

Chosen over `disallowed_tools` (the complement) because a denylist must be re-audited every time the CLI's default tool set grows — the declaration would silently stop being a gate. An allowlist cannot drift that way. `translate_tool_names` ([tool_names.py:26](src/squadron/providers/sdk/tool_names.py#L26)) already raises `ProviderError` on unmapped names, so a typo in a template fails loudly rather than silently widening the set.

**E2 — `tools` and `allowed_tools` are both set, deliberately.** They answer different questions (what exists vs. what is pre-approved) and setting both is coherent: the reviewer has exactly three tools and needs no prompt for any of them.

**E3 — `bypassPermissions` stays, and E1 is what makes that safe.** #69 asks whether review templates still want it. They do: a review is unattended, and a permission prompt would hang it. The reason it was alarming is that it approved *everything* — with `tools` set, "everything" is three read-only tools. Removing `bypassPermissions` without E1 would trade a silent over-permission for a silent hang; E1 without removing it addresses the actual exposure. **This decision must be re-examined if a future template declares a mutating tool** — recorded here so that change is a deliberate one.

**E4 — behavior-changing; verify against a live SDK review.** This is the one part that alters what a working reviewer can do, and the reason 265 scoped it out. A unit test asserting the emitted kwargs is necessary but not sufficient — a live SDK code review must still produce a usable review with only three tools. Sequenced last for this reason.

**E5 — scope boundary.** `AgentConfig.allowed_tools` is consumed by other dispatch paths, not only reviews. E1 changes the SDK provider edge for *any* config declaring `allowed_tools`, so the verification must confirm no non-review SDK dispatch relied on receiving the default tool set while declaring a narrower list. Check `allowed_tools` producers before implementing; if a non-review producer depends on the current behavior, E narrows to the review client's config construction instead of the provider edge.

## Data Flow

The `--diff` value's journey, after Part A:

```
--diff origin/main
   │
   ├─ normalize_diff_spec()          A2: bare ref → "origin/main...HEAD"
   │     └─ _resolve_rev() guard     A4: unresolvable → exit non-zero
   │
   ├─ extract_diff_paths(spec, review_cwd, exclude_patterns)
   │     └─ empty? ─────────────────► B1/B2: exit non-zero, no artifact
   │                                   (distinguishing all-excluded from no-changes)
   │
   └─ inputs["diff"] = spec ────────► builders/code.py → the model's `git diff` instruction
```

Both consumers receive the *same normalized string* — A1's requirement, and what makes the model's own `git diff` agree with the file list it was given.

## Success Criteria

### Functional

1. **A** — `sq review code --diff <base>` on a branch behind `<base>` reviews only the branch's own changes; the file list matches `gh pr view --json files` for the same PR.
2. **A** — `--diff a..b` and `--diff a...b` pass through unchanged.
3. **A** — `--diff <nonexistent>` exits non-zero naming the ref, with no model call.
4. **B** — an all-excluded range writes no artifact and exits non-zero, naming the matched exclusion patterns.
5. **B** — a range with no changed files at all exits non-zero with a *different*, range-focused message.
6. **C** — a `--diff`-only run in any of the four subcommands exits non-zero rather than 0.
7. **C** — `--no-save` still exits on verdict alone.
8. **D** — with `cwd = "./project-documents/user"` configured, a tool-enabled `slice`/`arch`/`tasks` review opens its input documents; the `AgentConfig.cwd` the client receives is the git root.
9. **E** — an SDK review agent is constructed with `tools` set to the template's declared list; `Bash` is not available.

### Technical

- No new `Verdict` member; no change to the five verdict consumers enumerated in Part B.
- Part D leaves one shared helper, not five copies (D1).
- Every new failure path exits non-zero **and** logs at WARNING or above, per the Failure-Mode Enumeration rule — no silent path is replaced by another silent path.
- Tests: normalization shape table (A2) including pass-through cases; both empty-scope messages distinctly (B2); save-outcome enum across all four subcommands (C4); a `slice` review under a subdirectory `cwd` asserting the client's `cwd` is the git root (D, the test #86 asks for); emitted SDK kwargs for `tools` (E1).
- No test may assert on user-facing message *text* as logical structure — assert on exit codes and the outcome enum.

### Verification Walkthrough

**A — the reported bug, reproduced and fixed.** In any repo with a branch behind its base:

```bash
git checkout -b probe origin/main~3
echo x >> README.md && git commit -am "probe change"

# Before: names files the branch never touched.
# After: names only README.md.
uv run sq review code --diff origin/main -v

# Cross-check against git's own merge-base answer:
git diff --name-only origin/main...HEAD
```

The two file lists must agree. On a real PR, both must agree with `gh pr view <n> --json files --jq '.files[].path'`.

**B — empty scope.** On a branch whose only changes are markdown:

```bash
uv run sq review code --diff origin/main -v; echo "exit=$?"
```

Expect non-zero, a message naming the `*.md` exclusion, and **no new file** under `project-documents/user/reviews/`. Confirm with `git status --short project-documents/user/reviews/`.

Then confirm the escape hatch: a pipeline phase with no `review:` key emits neither review nor checkpoint —

```bash
uv run sq run <pipeline> <slice> --dry-run
```

**C — silent no-save.** Against a range that does contain code:

```bash
uv run sq review code --diff origin/main -v; echo "exit=$?"
```

Expect non-zero with a message saying why no artifact could be written. Repeat for `sq review slice`/`arch`/`tasks` with `--diff`/`--files`-only invocations. Then confirm `--no-save` still exits 0 on a PASS.

**D — jail root.** With `cwd = "./project-documents/user"` in `~/.config/squadron/config.toml`:

```bash
uv run sq review slice 267 -v --model kimi3
```

Expect no `read_file: file not found` lines with a doubled `project-documents/user/project-documents/user/` prefix — the exact symptom in #86.

**E — tool availability.** Run an SDK-profile code review at `-vv` and confirm from the per-tool-call DEBUG records that only `read_file`/`list_files`/`grep` are used, and that the review is still usable. Then confirm `--tools` reaches the CLI as declared.

**#71 follow-up (not a deliverable).** After B, re-run #71's reproduction script in the reporting repo and close or re-file per B4.

## Risk Assessment

**Part B changes a passing outcome to a failing one.** Any pipeline currently relying on an all-excluded review passing will begin failing. That is the intended correction, but it is a live behavior change: before landing, check whether any repo's active pipeline has a docs-shaped phase with a `review:` key, and remove the key there per B3.

**Part E changes what a working reviewer can do.** Mitigated by sequencing it last, by E5's scope check on non-review `allowed_tools` producers, and by requiring a live SDK review in verification rather than only a kwargs assertion.

**Part A's rewrite rule is shape-based and could surprise.** A bare ref is the only shape that changes, and it changes toward what GitHub shows — but anyone scripting `--diff <ref>` expecting two-dot semantics gets different output. Acceptable: that expectation is the bug, and A5 keeps the explicit form available.

## Implementation Notes

Sequence **D → A → C → B → E**, and the order is load-bearing:

- **D** first: smallest change, and its helper extraction consolidates the function bodies A/B/C then edit.
- **A** next: contained, independently verifiable against `git diff --name-only`.
- **C** before **B**: B's new failure path should be built on C's corrected save-outcome model, not retrofitted into the `saved = True` optimism.
- **B** after both: carries the widest behavior change and depends on C's outcome enum.
- **E** last: the only part that alters a working reviewer's capability, and the only one whose verification needs a live model call.

Each part is independently committable and leaves the CLI working.
