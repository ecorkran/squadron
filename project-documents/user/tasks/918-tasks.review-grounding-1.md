---
docType: tasks
slice: review-grounding
project: squadron
lldReference: project-documents/user/slices/918-slice.review-grounding.md
parent: project-documents/user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: [917]
interfaces: []
status: not_started
dateCreated: 20260913
dateUpdated: 20260913
---

# Tasks: Review Grounding (1 of 2)

## Context Summary

Part 1 of three; Parts 2 and 3 are in `918-tasks.review-grounding-2.md`.

Three changes that stop a review from grading text other than the document in
front of it, and make the artifact say why output was lost when it is.

- **Part 1 (#94)** — a document review can read the archived and live reviews of
  the very document it is grading, because they sit inside the tool jail under
  the document's own name prefix. It quotes phrases deleted two revisions ago
  and recycles dispositioned findings; the third consecutive run escalated to
  FAIL. Fixed by a per-review-type tool-jail exclusion, threaded through tool
  binding alongside `cwd`.
- **Part 2 (#92)** — a complete, substantive model response that parses to zero
  findings records neither the stop reason nor the reasoning volume, the only
  two facts that discriminate the cause. Instrumentation lands first and
  unconditionally; the mechanism fix is chosen by what the instrumentation
  reports.
- **Part 3 (#65 finding 1)** — `sq install-commands` unlinks any `*.md` in a
  shared subdirectory it did not install, and `sq setup` runs it as step 2 of
  17. Fixed with the receipt mechanism `sq skills` already uses.

Issues [#94](https://github.com/ecorkran/squadron/issues/94),
[#92](https://github.com/ecorkran/squadron/issues/92),
[#65](https://github.com/ecorkran/squadron/issues/65). Related, not fixed here:
[#96](https://github.com/ecorkran/squadron/issues/96),
[#97](https://github.com/ecorkran/squadron/issues/97).

Sequenced **1 → 2 → 3** per the design. Part 1 changes a shared contract
(`ToolFactory`, `materialize`) that Parts 2 and 3 do not touch; Part 2 touches
`providers/openai/` and the digest; Part 3 touches neither and may land in any
order. Each part is independently committable.

Branch: `918-slice.review-grounding`. Read `cf config get git.integration_branch`
first — fork from and merge to its value, or `main` if empty.

### Verified code anchors (traced on `42bd0e05`, 20260913)

| Anchor | Location |
|---|---|
| `ToolFactory = Callable[[Path], ToolExecutor]` | [tools/models.py:37](src/squadron/tools/models.py#L37) |
| `ToolResult.is_error` | [tools/models.py:23](src/squadron/tools/models.py#L23) |
| `materialize(names, cwd)` — resolves `cwd` once | [tools/registry.py:42-62](src/squadron/tools/registry.py#L42-L62) |
| `resolve_in_jail(cwd, path)` | [_shared.py:26](src/squadron/tools/builtin/_shared.py#L26) |
| `contained_in_jail(cwd, entry, *, tool)` — D6 silence precedent | [_shared.py:43](src/squadron/tools/builtin/_shared.py#L43) |
| `jail_violation` — the refusal result both predicates feed | [_shared.py:120](src/squadron/tools/builtin/_shared.py#L120) |
| Five factories, all `(cwd: Path)` | [file_tools.py:48](src/squadron/tools/builtin/file_tools.py#L48), [:102](src/squadron/tools/builtin/file_tools.py#L102), [:171](src/squadron/tools/builtin/file_tools.py#L171), [search_tools.py:101](src/squadron/tools/builtin/search_tools.py#L101), [bash_tool.py:45](src/squadron/tools/builtin/bash_tool.py#L45) |
| `ReviewTemplate.diff_exclude_patterns` — the field to mirror | [templates/__init__.py:40](src/squadron/review/templates/__init__.py#L40) |
| Its loader handling | [templates/__init__.py:140-144](src/squadron/review/templates/__init__.py#L140-L144) |
| `REVIEWS_DIR = Path("project-documents/user/reviews")` — D4's named seam | [persistence.py:24](src/squadron/review/persistence.py#L24) |
| `archive_existing_review` — writes predecessors into the jail | [persistence.py:439](src/squadron/review/persistence.py#L439) |
| `materialize`'s single caller | [agent.py:190](src/squadron/providers/openai/agent.py#L190) |
| `TurnResult` (`finish_reason`, `reasoning_chars`) | [agent.py:91-105](src/squadron/providers/openai/agent.py#L91-L105) |
| `_require_final_content` — returns early unless `is_empty()` | [agent.py:67](src/squadron/providers/openai/agent.py#L67) |
| `_execute_tool_call` — branches on `is_error`, returns `str` | [agent.py:355-381](src/squadron/providers/openai/agent.py#L355-L381) |
| Executor-raised path (also an error the model sees) | [agent.py:367](src/squadron/providers/openai/agent.py#L367) |
| `tool_calls_made += 1` — counts without regard to outcome | [agent.py:457](src/squadron/providers/openai/agent.py#L457) |
| Metadata stamp site (D8's channel) | [agent.py:522-526](src/squadron/providers/openai/agent.py#L522-L526) |
| Metadata read-back in `review_client` | [review_client.py:234-238](src/squadron/review/review_client.py#L234-L238) |
| `_run_digest_lines` and `_NOT_COMPUTED` / `_render_tristate` | [persistence.py:175-200](src/squadron/review/persistence.py#L175-L200) |
| `ReviewResult` (`tools_given`, `tool_calls_made` precedent) | [models.py:86-110](src/squadron/review/models.py#L86-L110) |
| `install_commands` — the unlink loop | [install.py:57-60](src/squadron/cli/commands/install.py#L57-L60) |
| `uninstall_commands` — asymmetric, `sq/` only | [install.py:75-91](src/squadron/cli/commands/install.py#L75-L91) |
| `write_receipt` / `read_receipt`, `DEFAULT_RECEIPTS_DIR` | [skills/receipts.py:19](src/squadron/skills/receipts.py#L19), [:37](src/squadron/skills/receipts.py#L37), [:16](src/squadron/skills/receipts.py#L16) |
| `InstallReceipt` — the model to reuse or mirror | [skills/models.py:42-48](src/squadron/skills/models.py#L42-L48) |

### Two design questions answered during breakdown

**The `bash` gap is not a gap.** The design flags that a path deny-list cannot
constrain `bash`, and directs implementation to determine whether document
reviews grant it. Checked: **no template grants `bash`.** All seven
(`arch`, `slice`, `tasks`, `code`, and the three judges) declare
`allowed_tools: [read_file, list_files, grep]`. The exclusion is therefore
complete for every review that exists today, and T1.9 pins that with a test so
adding `bash` to a document template cannot silently reopen the hole. No
withholding logic is needed.

**`review.external_reviews_dir` has not landed on `main`.** D4 anticipated this
and prescribed the fallback: resolve against the current default and leave a
single named seam. `REVIEWS_DIR` ([persistence.py:24](src/squadron/review/persistence.py#L24))
is that seam and already exists — the templates declare the pattern as a string,
and the default value is that constant. When 383 lands, one constant changes.

---

## Part 1 — Jail exclusions for document reviews (#94)

### T1.1 — Introduce the jail specification value object

- [ ] Add a frozen dataclass to `src/squadron/tools/models.py` carrying the
      resolved jail root and the resolved exclusion paths (e.g. `JailSpec` with
      `root: Path` and `excluded: tuple[Path, ...]`).
- [ ] Document in its docstring that both fields are **already resolved** —
      resolution happens once at bind time, never inside a predicate, matching
      the existing contract that `ToolFactory` receives a resolved `cwd`.
- [ ] Change `ToolFactory` to `Callable[[JailSpec], ToolExecutor]` and update the
      comment above it ([tools/models.py:35-37](src/squadron/tools/models.py#L35-L37)).
- [ ] Update the `ToolDescriptor.factory` docstring ([tools/models.py:50-51](src/squadron/tools/models.py#L50-L51))
      so "already-resolved `cwd`" becomes the spec.
- [ ] Provide a convenience constructor or default so a spec with no exclusions
      is as cheap to build as passing a `Path` was — every non-review caller
      builds one of these.

**Success:** `ToolFactory` takes one opaque value object. Nothing in
`tools/models.py` mentions reviews, templates, or exclusion *policy* — only
resolved paths. Effort: 1.

### T1.2 — Teach the two predicates about exclusions

- [ ] Change `resolve_in_jail` ([_shared.py:26](src/squadron/tools/builtin/_shared.py#L26))
      to take the spec and return `None` for a candidate inside an excluded path,
      by the **same return** as a containment failure.
- [ ] Change `contained_in_jail` ([_shared.py:43](src/squadron/tools/builtin/_shared.py#L43))
      the same way, returning `False`.
- [ ] Match by `is_relative_to` against the resolved candidate — **never**
      string-prefix comparison. The reasoning is already documented at
      [_shared.py:34-35](src/squadron/tools/builtin/_shared.py#L34-L35)
      (`/tmp/jail_evil` starts with `/tmp/jail`); the same trap applies here.
- [ ] An excluded path logs exactly one WARNING per refusal, wording it as an
      exclusion rather than a jail escape so the two are distinguishable in a log.
- [ ] Extend both docstrings: the D6 silence rationale at
      [_shared.py:51-53](src/squadron/tools/builtin/_shared.py#L51-L53) now
      covers exclusions too.

**Why the same return path:** every existing caller handles `None`/`False`
already. Reusing it means no tool contract, error message, or model-visible
behavior changes — an excluded path is indistinguishable from a nonexistent one.
Effort: 2.

### T1.3 — Test the predicates directly

- [ ] Add to `tests/tools/test_jail.py` (or a sibling): a path inside an excluded
      directory returns `None` from `resolve_in_jail` and `False` from
      `contained_in_jail`.
- [ ] A path inside the jail but outside every exclusion still resolves.
- [ ] An empty exclusion set behaves **identically** to today for both
      predicates — the default-path regression guard named in the design's Risks.
- [ ] A sibling directory whose name shares a prefix with an excluded one
      (`reviews-archive` vs `reviews`) is **not** excluded. This is the
      `is_relative_to` assertion; a string-prefix implementation fails it.
- [ ] A refusal emits exactly one WARNING (use `caplog`).

**Success:** all pass; the prefix test fails if T1.2 is implemented with
`str.startswith`. Effort: 1.

### T1.4 — Thread the spec through the five factories

- [ ] Update all five factory signatures from `(cwd: Path)` to the spec:
      `_read_file_factory` ([file_tools.py:48](src/squadron/tools/builtin/file_tools.py#L48)),
      `_write_file_factory` ([:102](src/squadron/tools/builtin/file_tools.py#L102)),
      `_list_files_factory` ([:171](src/squadron/tools/builtin/file_tools.py#L171)),
      `_grep_factory` ([search_tools.py:101](src/squadron/tools/builtin/search_tools.py#L101)),
      `_bash_factory` ([bash_tool.py:45](src/squadron/tools/builtin/bash_tool.py#L45)).
- [ ] Where a factory needs the bare root (e.g. `bash`'s subprocess `cwd`,
      `format_entry`'s relative rendering), read it off the spec rather than
      changing the downstream call.
- [ ] Do **not** add exclusion logic to any individual tool — the predicates own
      it. A tool that reaches around them is the defect this task avoids.

**Success:** `pyright` clean; every tool's behavior with an empty exclusion set
is byte-identical to before. Effort: 2.

### T1.5 — Resolve root and exclusions together in `materialize`

- [ ] Change `materialize(names, cwd)` ([registry.py:42](src/squadron/tools/registry.py#L42))
      to accept the exclusion patterns alongside `cwd`, resolve both exactly
      once, build the spec, and hand it to every `descriptor.factory(...)`.
- [ ] Resolve each pattern against the jail root. A pattern that resolves
      **outside** the jail is discarded at bind time with a WARNING naming the
      pattern (D6) — it can never match, and silently keeping it invites a false
      sense of coverage.
- [ ] Keep the exclusion argument optional with an empty default, so every
      non-review caller is unchanged at its call site.
- [ ] Update the docstring: it currently states `cwd` is "resolved exactly once
      here" — say the same of the exclusions.

**Success:** one resolution point for both. A caller passing no exclusions gets
today's behavior. Effort: 2.

### T1.6 — Test `materialize`'s binding

- [ ] In `tests/tools/test_registry.py`: patterns resolve against the jail root
      and reach every materialized executor.
- [ ] A pattern resolving outside the jail is dropped, with one WARNING.
- [ ] **Concurrency/isolation:** materialize two executor sets with *different*
      exclusions and assert each honors only its own — the anti-global-state
      criterion from the design. This test fails if the implementation uses a
      module-level set.

**Success:** all pass. Effort: 1.

### T1.7 — Add the template field and its loader

- [ ] Add `tool_exclude_patterns: list[str] | None = None` to `ReviewTemplate`,
      declared as a sibling of `diff_exclude_patterns`
      ([templates/__init__.py:40](src/squadron/review/templates/__init__.py#L40)).
- [ ] Name it for the tool jail, not the diff — the two are independent and a
      reader must not conflate them. Comment the distinction at the field.
- [ ] Mirror the loader handling exactly
      ([templates/__init__.py:140-144](src/squadron/review/templates/__init__.py#L140-L144)):
      optional, list-of-strings, `None` when absent.

**Success:** a template YAML without the key loads to `None`; one with it loads
to a list of strings. Effort: 1.

### T1.8 — Declare the exclusion on the document templates

- [ ] Add `tool_exclude_patterns` to `arch.yaml`, `slice.yaml`, and `tasks.yaml`,
      excluding the reviews directory — the value of `REVIEWS_DIR`
      ([persistence.py:24](src/squadron/review/persistence.py#L24)), which is the
      single named seam D4 requires. Do **not** scatter the literal string.
- [ ] Add it to `judge-slice-vs-arch.yaml` and `judge-tasks-vs-slice.yaml` — both
      are document reviews and both run with tools
      (`allowed_tools: [read_file, list_files, grep]`, verified).
- [ ] **`judge-findings-addressed.yaml`: leave it alone and comment why.** It is
      305's deliberate prior-findings injection path — the design's non-goal. It
      receives findings as an input, not by discovery, so the exclusion neither
      helps nor harms it; a future reader must not "fix" the omission.
- [ ] **`code.yaml`: do not add the field.** Code reviews read the tree broadly
      by design (D2).

**Success:** five templates declare it, two deliberately do not, and the reason
is written down next to each omission. Effort: 1.

### T1.9 — Pin the `bash` boundary

- [ ] Add a test asserting no template whose `tool_exclude_patterns` is non-empty
      also declares `bash` in `allowed_tools`.
- [ ] Comment the test with the reason: a path deny-list does not constrain a
      subprocess, so a document-review template granting `bash` would silently
      defeat the exclusion. No template grants it today (verified on `42bd0e05`);
      this test is what keeps that true.

**Success:** passes today; fails immediately if someone adds `bash` to a
document-review template. Effort: 1.

### T1.10 — Pass template exclusions to the agent

- [ ] In `review_client.py`, pass the template's `tool_exclude_patterns` to the
      agent alongside `cwd`, on the same path `allowed_tools` already takes.
- [ ] In the agent, thread them into the `materialize` call
      ([agent.py:190](src/squadron/providers/openai/agent.py#L190)) as **opaque
      data**. The agent is a generic provider and must not learn what a review
      type is — no template lookup, no review-specific branch (D5).
- [ ] A template declaring no exclusions passes an empty set, not `None`-handling
      at the agent.

**Success:** `grep -n "template\|review" src/squadron/providers/openai/agent.py`
shows no new review-awareness. Effort: 2.

### T1.11 — Integration test: a document review cannot read reviews

- [ ] Build a fixture tree with a document under review and a populated reviews
      directory (live plus `archive/`), materialize an arch review's tools, and
      assert **all three** of `read_file`, `list_files`, and `grep` refuse every
      path under the reviews directory.
- [ ] `list_files` must not *enumerate* the excluded directory — a refusal that
      still lists names leaks the filenames, which are the document's own name
      prefixed. Assert on the returned content, not just on an error flag.
- [ ] `grep` must return no match from an excluded file even when the pattern
      matches its contents.
- [ ] The refusals are invisible in tool output (the model cannot distinguish
      them from a nonexistent path) and produce WARNINGs in the log.
- [ ] **Code reviews unaffected:** materialize a `code` review's tools against
      the same tree and assert it *can* read a file under the reviews directory.
      Also assert `code.yaml` declares no `tool_exclude_patterns`.

**Success:** all pass. This is the test that would have caught #94. Effort: 2.

### T1.12 — Verify the reported reproduction

- [ ] Follow the design's Part 1 walkthrough in the `squadron-pr` worktree, where
      the 380 document and its five archived reviews live. Confirm the
      predecessors exist, then run three consecutive `sq review arch 380 -v`
      passes with a revision between each.
- [ ] Confirm no finding quotes a phrase absent from the current
      `380-arch.pull-request-workflow.md`, and that findings dispositioned in an
      earlier round do not reappear.
- [ ] Confirm the exclusion **fired** rather than the model simply not looking:
      `sq review arch 380 -vv ... 2>&1 | grep -i 'refus'` shows WARNINGs, and
      nothing in the model-visible transcript names a denial.
- [ ] Run from the repo root with `uv run sq` — the released `sq` predates
      `_resolve_review_cwd` (issue #86) and will not exercise this path correctly.
- [ ] Record the outcome in the DEVLOG. If the exclusion does not fire, stop and
      diagnose before proceeding — do not tune the patterns speculatively.

**Success:** three convergent runs, WARNINGs present, transcript clean. Effort: 1.
