---
docType: slice-design
slice: review-scope-correctness
project: squadron
parent: 900-slices.maintenance-and-refactoring.md
dependencies: []
interfaces: [917]
dateCreated: 20260910
dateUpdated: 20260911
status: complete
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

**A5 — low-level failure modes for the new git call (added after slice review, F002).** `normalize_diff_spec` shells out, so the hang/timeout/no-repo family needs an explicit answer rather than the blanket assurance in Technical criteria:

- **Hang or timeout.** The new call goes through `run_git` ([git_utils.py:21](src/squadron/review/git_utils.py#L21)) rather than calling `subprocess` directly — the same helper the six inline git calls were consolidated into for #63. **Checked: `run_git` passes no `timeout`**, so `subprocess.run` blocks indefinitely. Adding a bounded timeout there is in scope for this part. It is a shared helper, so this hardens all seven existing callers too — a `git rev-parse` or `merge-base` against an unreachable remote-tracking ref currently hangs the CLI before any review begins, with no output explaining why. On timeout, `run_git` returns None, which every caller already treats as "git could not be invoked" — no call-site changes needed.
- **`cwd` outside a git work tree.** `run_git` returns None and `_resolve_rev` yields None, which A4 already routes to the loud non-zero exit. The message must distinguish "not a git repository" from "ref not found" — they are different operator errors and the fix differs.
- **Asymmetry, stated deliberately.** A4's guard covers the bare-ref shape only. An unresolvable ref inside an explicit `a..b`/`a...b` range still reaches the swallow at [rules.py:218-220](src/squadron/review/rules.py#L218-L220) and surfaces as B2's no-changed-files message. That is handled (non-zero, not silent) but less precise. Validating both endpoints of an explicit range is deliberately **not** done here: the shapes A2 passes through are the ones where the caller was explicit, and B2's guard already catches the outcome. Recorded so the gap is a decision rather than an oversight.

**A6 — the two-dot form stays reachable, unchanged, and undocumented as a feature.** Someone who writes `--diff a..b` gets exactly that. No new flag is added: the shape already expresses the distinction, and a flag would be a second way to say something the argument already says.

### Part C — Save gating (#70)

All four subcommands initialize `saved = True` and overwrite it only inside a branch gated on an identifier that `--diff`/`--files`-only runs never supply ([:616](src/squadron/cli/commands/review.py#L616), [:673](src/squadron/cli/commands/review.py#L673), [:760](src/squadron/cli/commands/review.py#L760), [:930](src/squadron/cli/commands/review.py#L930)). The review runs, prints, writes nothing, exits 0. This is precisely what `_save_and_report`'s docstring ([:190-193](src/squadron/cli/commands/review.py#L190-L193)) says must not happen — the guard lives inside the function this path never calls.

**C1 — the initializer is the bug; invert the default.** `saved` starts `False` and becomes `True` only on a real write or a real `--no-save`. Optimism about an unperformed write is the whole defect.

**C2 — distinguish "chose not to save" from "could not save."** `--no-save` is a deliberate instruction and must keep exiting 0. Model the three outcomes explicitly rather than through one boolean's history:

- **saved** — artifact written; exit on verdict.
- **suppressed** — `--no-save` given; exit on verdict.
- **unsaved** — a save was expected and did not happen; exit 1 regardless of verdict, per `_exit_on`'s existing precedence ([:273-285](src/squadron/cli/commands/review.py#L273-L285)).

A small enum, per the project rule against user-visible labels and scattered comparison values.

**C3 — a `--diff`-only run warns and exits 0; only an *attempted and failed* save exits non-zero.** Revised after the slice review (F003). The original C3 made a slice-less `--diff` run exit 1. That is wrong, and the review caught it.

The evidence: `sq review code --diff main` with no slice number is not an edge case, it is **the primary documented workflow**. It appears in 10 shipped examples — [README.md:154](README.md#L154), [:176](README.md#L176), [:286](README.md#L286), [:292](README.md#L292), [:322](README.md#L322), [:341](README.md#L341), [:344](README.md#L344), [:347](README.md#L347) and [docs/COMMANDS.md:90](docs/COMMANDS.md#L90), [:96](docs/COMMANDS.md#L96) — including the `--output json` examples whose entire purpose is terminal/piped output with no artifact. Slice 118's `/sq:review-code` carries an explicit compatibility guarantee for the same form. Failing it would break the tool's most-advertised invocation to fix a bug about *silent* failure, and would turn every one of those examples into an instruction to run a failing command.

The correction: #70's defect is that the run reports success for a save it never attempted and never mentions it. The fix for that is **saying so**, not failing. Terminal output is a legitimate destination — `--output json` proves it was designed to be.

So the outcome model from C2 resolves as:

| Invocation | Outcome | Exit |
|---|---|---|
| slice identifier present, write succeeds | saved | on verdict |
| `--no-save` given | suppressed | on verdict |
| no slice identifier (`--diff`/`--files` only) | **not-persistable** | on verdict, **plus a WARNING** naming that no artifact was written and how to get one |
| save attempted and failed (I/O, permissions) | unsaved | **1**, per `_exit_on` |

The fourth row needs no new machinery: `_save_and_report` already returns `False` on `OSError` from `save_review_result` ([review.py:266-268](src/squadron/cli/commands/review.py#L266-L268)), and `save_review_result` already refuses to overwrite a review whose prior content it could not archive (slice 306 Part D). Attempted-and-failed is therefore *already* distinguishable from not-attempted — C1's inverted initializer is what lets the caller see the difference. The fourth row is what `_exit_on`'s existing contract ([review.py:190-193](src/squadron/cli/commands/review.py#L190-L193)) is actually about — "an unwritten review is a review Context Forge cannot see" applies to a review that was *supposed* to be written. The third row was never supposed to be written, and the bug is only that it stayed quiet about it.

This still closes #70's reported harm: the trading-data operator lost 7 findings because nothing said the run had not persisted and a stale artifact remained in place. A WARNING naming the absent artifact prevents exactly that, without breaking the documented surface.

**C4 — the warning must name the remedy, not just the fact.** It states that no artifact was written, and that supplying a slice number (or `--output file --output-path`) will produce one. A warning that only reports absence leaves the operator where they started.

*Deliberately not done:* inventing an artifact naming scheme for slice-less reviews. That is a real gap — there is no way to persist a `--diff`-only review under `project-documents/user/reviews/` — but naming is a design decision of its own and #70 does not require it. Filed as [issue #90](https://github.com/ecorkran/squadron/issues/90) rather than settled here.

**C5 — all four subcommands, one mechanism.** #70 was filed against `code`; the reading above confirms all four carry it. Interface parity is a standing project rule.

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

**B1 — detect in shared code below both entry points, pre-flight.** Revised after the slice review (F001), which was right that B was pinned to the CLI, and right that the pipeline is the path that trips gates.

The original B1 proposed reusing the `extract_diff_paths` call at [review.py:893](src/squadron/cli/commands/review.py#L893). Checking the source shows that would have been wrong twice over:

1. **There are two independent call sites, not one.** The pipeline review action has its own at [actions/review.py:195](src/squadron/pipeline/actions/review.py#L195). Building B on the CLI's site leaves `sq run` — the path that clears review gates — exactly as broken as it is today, which is the harm B exists to fix.
2. **Neither call site is a scope check.** Both are nested inside `if rules_dir is not None:` ([review.py:891](src/squadron/cli/commands/review.py#L891), [actions/review.py:187](src/squadron/pipeline/actions/review.py#L187)) and exist to feed language auto-detection into `load_review_rules`; `file_paths` is discarded afterward. A check hung off them would **silently not run** whenever no rules directory resolves — a configuration-dependent gap in a guard whose whole purpose is to be unconditional.

**Design:** a single `assert_reviewable_scope(diff, cwd, exclude_patterns)` in `review/git_utils.py`, called unconditionally by both entry points before any provider work and independent of rules resolution. It computes the filtered and unfiltered path lists itself and raises a typed error carrying which of B2's two cases occurred plus the matched patterns. The existing rules-loading calls are left alone — they are doing a different job, and folding scope detection into them is what created this trap.

Placing it in `git_utils` rather than in either caller is the same interface-parity rule that makes C5 cover all four subcommands: a gate that holds on one entry point and not the other is not a gate. Pre-flight placement also avoids spending a model call to be told what git already knew, and lets the message name the responsible patterns.

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
6. **B** — criteria 4 and 5 hold identically via `sq run` (the pipeline review action), not only via the CLI, and hold when **no rules directory resolves** — the guard is unconditional (B1).
7. **C** — a `--diff`-only run still exits on verdict (0 on PASS) and emits a WARNING naming the absent artifact and how to obtain one. The 10 documented `--diff`-without-slice examples in README/COMMANDS.md continue to work.
8. **C** — a save that is attempted and *fails* exits 1.
9. **C** — `--no-save` still exits on verdict alone, with no warning.
10. **D** — with `cwd = "./project-documents/user"` configured, a tool-enabled `slice`/`arch`/`tasks` review opens its input documents; the `AgentConfig.cwd` the client receives is the git root.
11. **E** — an SDK review agent is constructed with `tools` set to the template's declared list; `Bash` is not available.

### Technical

- No new `Verdict` member; no change to the five verdict consumers enumerated in Part B.
- Part D leaves one shared helper, not five copies (D1).
- Every new failure path exits non-zero **and** logs at WARNING or above, per the Failure-Mode Enumeration rule — no silent path is replaced by another silent path.
- Tests: normalization shape table (A2) including pass-through cases; both empty-scope messages distinctly (B2); save-outcome enum across all four subcommands (C5); a `slice` review under a subdirectory `cwd` asserting the client's `cwd` is the git root (D, the test #86 asks for); emitted SDK kwargs for `tools` (E1).
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

**Verified on implementation** with a constructed probe repo (a branch behind a base that moved
on): the old bare-ref form reported `app.py` *and* `other.py` — the latter a change only the
base had — while the fix reports `['app.py']`, matching `git diff --name-only main...HEAD`
exactly. `gh` is not required; the git form is the authoritative oracle.

**B — empty scope.** On a branch whose only changes are markdown:

```bash
uv run sq review code --diff origin/main -v; echo "exit=$?"
```

Expect non-zero, a message naming the `*.md` exclusion, and **no new file** under `project-documents/user/reviews/`. Confirm with `git status --short project-documents/user/reviews/`.

**Verified on implementation** against a markdown-only branch: CLI exits 1, CLI with
`resolve_rules_dir` returning None exits 1, and the pipeline action returns `success=False` —
all three with a WARNING naming the `*.md` exclusion and the excluded count, no model call, and
no artifact written.

Then the same range through the pipeline, which is the path that trips gates (B1) — this must fail identically, not pass:

```bash
uv run sq run <pipeline> <docs-only-slice>; echo "exit=$?"
```

And confirm the guard is unconditional: re-run the CLI case with `--rules-dir` pointing somewhere with no rules, so `resolve_rules_dir` returns None. The empty-scope refusal must still fire — this is the regression the original B1 would have shipped.

Then confirm the escape hatch: a pipeline phase with no `review:` key emits neither review nor checkpoint —

```bash
uv run sq run <pipeline> <slice> --dry-run
```

**C — silent no-save.** Against a range that does contain code:

```bash
uv run sq review code --diff origin/main -v; echo "exit=$?"
```

Expect **exit 0 on a PASS**, findings on the terminal, and a WARNING naming that no artifact was written and how to get one. Confirm no file appeared: `git status --short project-documents/user/reviews/`.

Then confirm the documented surface still works — every one of these must behave as its documentation says:

```bash
uv run sq review code --diff main --output json | jq .verdict   # README:344
uv run sq review code --diff main --files "src/**/*.py"          # README:292
```

Repeat the bare form for `sq review slice`/`arch`/`tasks`. Then confirm `--no-save` exits 0 with **no** warning, and that a save which genuinely fails (point the reviews directory at a read-only path) exits 1.

**Caveat discovered on implementation:** the not-persistable warning must go to **stderr**, not
stdout. `COMMANDS.md:96` documents `sq review code --diff main --output json > review.json`, and
a warning on stdout corrupts that JSON. The `--output json` check above is only meaningful if it
parses *stdout alone* — piping through `jq` does test this; asserting on combined output does
not.

**Verified on implementation:** not-persistable exits 0 with a stderr warning and no artifact,
`--no-save` exits 0 silently, and a save raising `OSError` exits 1 — each across all four
subcommands. All ten documented invocations continue to work, so **no documentation changes were
needed**, which is what C3's reversal was for.

**D — jail root.** With `cwd = "./project-documents/user"` in `~/.config/squadron/config.toml`:

```bash
uv run sq review slice 267 -v --model kimi3
```

Expect no `read_file: file not found` lines with a doubled `project-documents/user/project-documents/user/` prefix — the exact symptom in #86.

**Verified on implementation** without spending a model call, by resolving the pair directly:

```bash
uv run python -c "
from unittest.mock import patch
from squadron.cli.commands.review import _resolve_review_cwd
with patch('squadron.cli.commands.review.get_config',
           side_effect=lambda k, cwd='.': './project-documents/user' if k == 'cwd' else None):
    print(_resolve_review_cwd(None, None))
"
```

Observed: the repository root and `<root>/.claude/rules` — so no repo-relative path in the
prompt can produce the doubled prefix.

**E — tool availability.** Run an SDK-profile code review at `-vv` and confirm the review is
still usable. **Correction (implementation):** the per-tool-call DEBUG records this step asks
for are *not obtainable on the SDK path*. That logging exists only on the OpenAI agentic-loop
path (`providers/openai/agent.py`); the SDK delegates tool execution to the Claude Code CLI,
which does not report individual calls back through squadron's loggers. This is a pre-existing
observability gap, not one Part E introduced. Verify the restriction at the options boundary
the SDK actually enforces instead:

```bash
uv run python -c "
import asyncio
from unittest.mock import MagicMock, patch
from squadron.core.models import AgentConfig
from squadron.providers.sdk.provider import ClaudeSDKProvider
from squadron.review.templates import get_template, load_all_templates
load_all_templates(); t = get_template('code')
cfg = AgentConfig(name='review-code', agent_type='sdk', provider='sdk',
                  allowed_tools=t.allowed_tools, permission_mode=t.permission_mode,
                  setting_sources=t.setting_sources)
with patch('squadron.providers.sdk.agent.ClaudeSDKAgent', create=True) as m:
    m.return_value = MagicMock()
    asyncio.run(ClaudeSDKProvider().create_agent(cfg))
    o = m.call_args.kwargs['options']
print(list(o.tools), list(o.allowed_tools), o.permission_mode)
"
```

Observed: `['Read', 'Glob', 'Grep'] ['Read', 'Glob', 'Grep'] bypassPermissions` — `Bash` absent,
`allowed_tools` still set (both, per E2), permission mode unchanged (E3).

For the usability half, a live run is required. **Caveat:** `sq review` cannot launch the SDK
provider from inside a Claude Code session; prefix with `env -u CLAUDECODE
-u CLAUDE_CODE_ENTRYPOINT`, and pass `--model` explicitly, since the `sdk` profile's configured
default may not be a Claude model:

```bash
env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT \
  uv run sq review code --diff main --profile sdk --model sonnet -vv --no-save
```

Observed on implementation: exit 0, verdict CONCERNS, grounded file-level findings — a
three-tool reviewer is **not** degraded. This run also surfaced four real defects in the slice's
own work (see DEVLOG 20260911), all fixed before landing.

**#71 follow-up (not a deliverable).** **Result: #71 stays open.** Ran the issue's own
diagnostic against the reporting repo. Resolution is correct — `resolve_slice_diff_range(267)`
returns `bd0b169^1..bd0b169^2`, the same range the reporter got a real review from — and
**candidate 3 (all-excluded scope) is ruled out**: 45 files survive the code template's
`diff_exclude_patterns`, so the scope was never empty and Part B's guard does not fire on it.
Part B's message therefore does not explain #71; the cause lies elsewhere. Re-file with this
evidence rather than closing.

## Risk Assessment

**Part B changes a passing outcome to a failing one.** Any pipeline currently relying on an all-excluded review passing will begin failing. That is the intended correction, but it is a live behavior change: before landing, check whether any repo's active pipeline has a docs-shaped phase with a `review:` key, and remove the key there per B3.

**Part E changes what a working reviewer can do.** Mitigated by sequencing it last, by E5's scope check on non-review `allowed_tools` producers, and by requiring a live SDK review in verification rather than only a kwargs assertion.

**Part C touches the most-documented invocation on the tool.** Surfaced by the slice review (F003). The revised C3 keeps `sq review code --diff main` exiting 0, so the 10 README/COMMANDS.md examples and slice 118's `/sq:review-code` compatibility guarantee all continue to hold — the change is an added WARNING, not a failure. **No documentation updates are required, and that is the point of the revision**; the original C3 would have required rewriting every one of those examples. If implementation finds a case where exiting 0 is untenable, the doc updates come back into scope and must be scoped explicitly rather than absorbed.

**Part A's rewrite rule is shape-based and could surprise.** A bare ref is the only shape that changes, and it changes toward what GitHub shows — but anyone scripting `--diff <ref>` expecting two-dot semantics gets different output. Acceptable: that expectation is the bug, and A6 keeps the explicit form available.

## Slice Review Disposition

Slice review (`916-review.slice.review-scope-correctness.md`, glm-5.3, CONCERNS, 20260911). All three concerns accepted; two changed the design materially.

- **F001 (concern) — accepted, design changed.** B was pinned to the CLI path. Verification against source found it worse than the finding could confirm: there are **two** independent `extract_diff_paths` call sites (CLI [review.py:893](src/squadron/cli/commands/review.py#L893), pipeline [actions/review.py:195](src/squadron/pipeline/actions/review.py#L195)), and *neither is a scope check* — both are nested under `if rules_dir is not None:` and feed language detection, discarding `file_paths` afterward. B1 now specifies a shared unconditional guard in `git_utils` called by both entry points. Criteria 6 and the walkthrough test the rules-absent case explicitly, since that is the regression the original B1 would have shipped.
- **F002 (concern) — accepted, A5 added.** The hang/timeout/no-repo family is now answered: the new call goes through `run_git` rather than raw `subprocess`, adding a timeout there if absent; "not a git repository" is distinguished from "ref not found"; and the unvalidated-endpoint asymmetry in explicit ranges is recorded as a decision with its rationale rather than left as a gap.
- **F003 (concern) — accepted, design reversed.** The strongest finding. The original C3 would have made `sq review code --diff main` exit non-zero — the tool's most-documented invocation, appearing in 10 README/COMMANDS.md examples plus slice 118's compatibility guarantee, including `--output json` examples whose purpose is terminal output with no artifact. C3 now warns and exits on verdict; only an *attempted and failed* save exits 1. This still closes #70's reported harm (the operator lost findings because nothing said the run had not persisted) without breaking the documented surface, and it removes the doc-update work the finding correctly noted was unscoped.
- **F004 (note) — acknowledged, no change.** Five parts at 4/5 sits at the edge of 900's "prefer many small slices." The finding requests no change and notes the bundle is plan-authorized with a load-bearing part sequence, each part independently committable.
- **F005, F006 (pass)** — no action.

Follow-up filed as [issue #90](https://github.com/ecorkran/squadron/issues/90): there is no artifact naming scheme for slice-less reviews, so a `--diff`-only review cannot be persisted at all. Real gap, but a naming decision of its own and not required by #70.

## Implementation Notes

Sequence **D → A → C → B → E**, and the order is load-bearing:

- **D** first: smallest change, and its helper extraction consolidates the function bodies A/B/C then edit.
- **A** next: contained, independently verifiable against `git diff --name-only`.
- **C** before **B**: B's new failure path should be built on C's corrected save-outcome model, not retrofitted into the `saved = True` optimism.
- **B** after both: carries the widest behavior change and depends on C's outcome enum.
- **E** last: the only part that alters a working reviewer's capability, and the only one whose verification needs a live model call.

Each part is independently committable and leaves the CLI working.
