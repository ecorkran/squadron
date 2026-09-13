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

# Tasks: Review Grounding (2 of 2)

Parts 2 and 3 of three. Context summary, verified code anchors, branch,
and sequencing are in `918-tasks.review-grounding-1.md`.

## Part 2 — Stop-reason evidence on every review (#92)

> **D7 is binding: instrumentation lands first and unconditionally. Do not apply
> a speculative mechanism fix.** T2.8 reads the evidence; T2.9 implements only
> the branch the evidence selects.

### T2.1 — Count failed tool calls in the agent

- [ ] Widen `_execute_tool_call` ([agent.py:355](src/squadron/providers/openai/agent.py#L355))
      to return the error-ness alongside the content — it currently returns
      `str`, discarding `ToolResult.is_error` at the return.
- [ ] **Do not** match on an `"Error: "` prefix downstream. String-dispatch on
      content is forbidden by project rules and would break the moment a tool's
      message wording changes.
- [ ] Count the executor-raised path ([agent.py:367](src/squadron/providers/openai/agent.py#L367))
      and the unknown-tool path ([agent.py:362](src/squadron/providers/openai/agent.py#L362))
      as failures too — the number must mean "tool calls that failed", not
      "tool calls whose executor returned `is_error`".
- [ ] Add the counter beside `tool_calls_made` ([agent.py:457](src/squadron/providers/openai/agent.py#L457)).

**Success:** a run in which every tool errors reports made == failed, non-zero.
Effort: 2.

### T2.2 — Stamp the three facts on final-`Message.metadata`

- [ ] At the existing stamp site ([agent.py:522-526](src/squadron/providers/openai/agent.py#L522-L526)),
      add the stop reason, the reasoning character count, and the failed-call
      count — the same channel tool telemetry already uses (D8).
- [ ] Take the stop reason and reasoning count from the final `TurnResult`.
      **Do not widen `TurnResult`'s caller-facing role** — it is documented as
      internal plumbing ([agent.py:91-93](src/squadron/providers/openai/agent.py#L91-L93))
      and must stay that way.
- [ ] Stamp unconditionally, on success and on degradation alike. The failure
      today is precisely that `_require_final_content`
      ([agent.py:67](src/squadron/providers/openai/agent.py#L67)) returns early
      unless the turn `is_empty()`, so the one case where the stop reason *is*
      the diagnosis records neither.
- [ ] Do **not** stamp anything on the SDK provider path (D12). `finish_reason`
      is an OpenAI/OpenRouter streaming concept; an absent key reads as `None`
      and renders as not-computed. Do not fabricate a value.

**Success:** a passing review's final message carries all three keys. Effort: 2.

### T2.3 — Test the agent stamping

- [ ] With a fake stream: a normal completion stamps a stop reason and a
      reasoning count.
- [ ] A run whose executors all return `is_error` stamps made == failed,
      non-zero — the kimi27 shape.
- [ ] A run with no failed calls stamps `0`, not absent. The distinction matters
      downstream (T2.6).
- [ ] An SDK-path review stamps none of the three.

**Success:** all pass. Effort: 1.

### T2.4 — Read the facts back in `review_client`

- [ ] Read the three keys where the existing telemetry is read
      ([review_client.py:234-238](src/squadron/review/review_client.py#L234-L238)),
      following the same shape.
- [ ] Carry them onto `ReviewResult` (T2.5). `None` where the provider stamped
      nothing.

**Success:** the values reach `ReviewResult` on both the openrouter and SDK
paths, `None` on the latter. Effort: 1.

### T2.5 — Add the `ReviewResult` fields

- [ ] Add three optional fields alongside `tools_given` / `tool_calls_made`
      ([models.py:105-110](src/squadron/review/models.py#L105-L110)): stop reason
      (`str | None`), reasoning characters (`int | None`), failed tool calls
      (`int | None`).
- [ ] `None` means **not reported**, exactly as the existing tri-state fields use
      it. Document that at each field.
- [ ] **Not serialized into frontmatter** (D10) — frontmatter is a consumed
      contract the verdict gate checks; these are diagnostic. Confirm they are
      absent from `to_dict` and any frontmatter builder.

**Success:** fields present, frontmatter unchanged. Effort: 1.

### T2.6 — Render the facts in the Run Digest

- [ ] Add four lines to `_run_digest_lines`
      ([persistence.py:175](src/squadron/review/persistence.py#L175)): stop
      reason, reasoning characters, failed tool calls, and the newline-free
      indicator (T2.7).
- [ ] Put `Tool calls failed` **immediately after** the existing
      `Tool calls made` line — the pair `made: 2` / `failed: 2` names the kimi27
      shape at a glance.
- [ ] Render an absent value with the existing `_NOT_COMPUTED` treatment. **A
      failed-call count of `0` is a real answer and must not render as
      not-computed** — this is the trap in the existing
      `str(result.tool_calls_made or 0)` idiom at
      [persistence.py:183](src/squadron/review/persistence.py#L183); do not copy
      the `or 0`.
- [ ] Nothing gates on these. They are evidence for a human or a future issue.

**Success:** every artifact's digest carries all four. Effort: 1.

### T2.7 — Report a newline-free response (D10a)

- [ ] Add a line count, or a boolean for "response contains no line breaks",
      beside the existing response-length line.
- [ ] This does **not** fix [#96](https://github.com/ecorkran/squadron/issues/96)
      — the parser fix is out of scope. It makes the artifact say *which* of the
      three known shapes occurred: never-emitted output (#92), all-tools-failed
      (kimi27), or emitted-but-unparseable (#96).
- [ ] Leave a comment for whoever fixes #96: the same leniency must not reopen
      [#91](https://github.com/ecorkran/squadron/issues/91) — 917 Part F's fence
      masking and section bounding both assume line structure, so they need
      review together.

**Success:** a multi-kilobyte response with zero newlines is named as such.
Effort: 1.

### T2.8 — Test the digest, then re-run the reproduction

- [ ] Test: a review whose response parses to zero findings shows a **non-empty**
      response length *and* a stop reason in the same digest — the #92 signature,
      readable from the artifact with no `-vv` and no live terminal.
- [ ] Test: a review whose tool executors all error shows made and failed equal
      and non-zero.
- [ ] Test: a run with no failed calls reports `0`, not not-computed.
- [ ] Test: a known newline-free response (the 3076-character `918-review.slice`
      body is a real specimen) is reported as newline-free.
- [ ] Test: an SDK-path review renders stop reason and reasoning count as
      not-computed, not as fabricated values.
- [ ] Then re-run the reproduction: `uv run sq review slice 916 -v --model kimi3`.
      Read the stop reason out of the artifact's digest and **record it in the
      DEVLOG** before writing any fix.
- [ ] If it does not reproduce, say so plainly in the DEVLOG. The instrumentation
      still lands; do not claim the underlying cause is fixed.

**Success:** tests pass and the DEVLOG records an observed stop reason (or a
documented non-reproduction). Effort: 2.

### T2.9 — Implement the branch the evidence selects

> Specify this task's body only after T2.8. Three candidates, three different
> fixes; the design's "Step 2, contingent" section names them.

- [ ] **`finish_reason == "length"`** → the output budget was consumed. Verified:
      `max_tokens` is set on **no** request anywhere under `providers/openai/`.
      Size it against reasoning models; this also closes
      [#84](https://github.com/ecorkran/squadron/issues/84)'s open follow-up.
      Most likely given the symptom.
- [ ] **Clean `stop` with a non-empty turn that parsed to nothing** → the model
      ended its turn believing more were available and the loop treated it as
      final. A turn-boundary bug in the agentic loop.
- [ ] **Neither** → prompt adherence: the model narrated its plan instead of
      emitting the format. Check whether 917 Part F's fenced specimens changed
      adherence. If this is the branch, consider filing a follow-up rather than
      expanding this slice — that call is the Project Manager's.
- [ ] Add a test for whichever branch is implemented, and verify against the
      same command that produced the evidence.

**Success:** the selected fix is implemented, tested, and verified against
`sq review slice 916 -v --model kimi3`; the DEVLOG names which branch and why.
Effort: 2 (bounded; revisit if the evidence points at prompt adherence).

---

## Part 3 — Receipt-based command install (#65 finding 1)

### T3.1 — Write an install receipt

- [ ] Reuse the `sq skills` receipt mechanism rather than inventing a second one
      (D13): `write_receipt` / `read_receipt` at
      [skills/receipts.py:19](src/squadron/skills/receipts.py#L19) and
      [:37](src/squadron/skills/receipts.py#L37), `DEFAULT_RECEIPTS_DIR` at
      [:16](src/squadron/skills/receipts.py#L16), `InstallReceipt` at
      [skills/models.py:42](src/squadron/skills/models.py#L42).
- [ ] Decide whether `InstallReceipt` fits as-is or needs a sibling. It carries
      `pack_name`, `surface`, `destination`, `files_written` — `files_written`
      must hold the `<subdir>/<name>.md` paths `install_commands` already builds
      ([install.py:56](src/squadron/cli/commands/install.py#L56)). If the
      `surface` field does not apply, prefer a sibling model over a misused enum
      value; do not overload a field to mean something it does not.
- [ ] Write the receipt after a successful install, recording every file written.

**Success:** `sq install-commands` leaves a receipt naming exactly what it wrote.
Effort: 2.

### T3.2 — Remove only what the receipt records

- [ ] Replace the unlink loop ([install.py:57-60](src/squadron/cli/commands/install.py#L57-L60)):
      a stale file is removed only if the **previous** receipt names it and the
      current bundle does not.
- [ ] A file present but absent from the receipt is **left alone** (D15).
      Deleting unknown files is the bug being fixed.
- [ ] A receipt entry naming a file the user already deleted is **not an error** —
      tolerate it silently.
- [ ] Keep reporting removals in the existing output, so a legitimate stale
      removal is still visible.

**Success:** `~/.claude/commands/analysis/mine.md` survives. Effort: 2.

### T3.3 — Make uninstall symmetric

- [ ] `uninstall_commands` ([install.py:75](src/squadron/cli/commands/install.py#L75))
      currently removes only `sq/` by `rmtree`. Change it to remove every file the
      receipt records, across every subdirectory (D14).
- [ ] Do not `rmtree` a shared subdirectory — remove the recorded files, then the
      directory only if it is empty.
- [ ] Delete the receipt after a successful uninstall, mirroring
      [skills.py:118](src/squadron/cli/commands/skills.py#L118).
- [ ] With no receipt (a pre-receipt installation), remove nothing and say so.

**Success:** squadron's files go from every subdirectory; user files stay.
Effort: 2.

### T3.4 — Test the install/uninstall lifecycle

- [ ] `tests/cli/test_install_commands.py` does not cover the non-`sq` subdir
      path today. Add coverage for it — that gap is why #65 shipped.
- [ ] A user file in a shared subdirectory survives `sq install-commands`.
- [ ] Squadron's own bundled files are installed and refreshed on re-run.
- [ ] Two consecutive installs are idempotent, and the second reports no
      deletions.
- [ ] An install over a pre-receipt installation (files present, no receipt)
      deletes nothing.
- [ ] `sq uninstall-commands` removes every subdirectory squadron installed and
      leaves user files.
- [ ] Use `--target` / `--receipts-dir` pointed at `tmp_path`. **No test touches
      the real `~/.claude/commands` or `~/.config/squadron/receipts`.**

**Success:** all pass. Effort: 2.

### T3.5 — Verify against a real install

- [ ] Run the design's Part 3 walkthrough: create
      `~/.claude/commands/analysis/zz-scratch.md`, run `sq install-commands`,
      confirm `SURVIVED`.
- [ ] Run it a second time and confirm no deletions.
- [ ] Run `sq uninstall-commands` and confirm squadron's files go and
      `zz-scratch.md` stays.
- [ ] Remove the scratch file afterward.

**Success:** all three confirmed. Effort: 1.

---

## Closeout

- [ ] `ruff format`, `ruff check`, and `pyright` are clean — zero pyright errors
      is a merge blocker.
- [ ] Full test suite passes.
- [ ] DEVLOG entry per `prompt.ai-project.system.md` § Session State Summary,
      recording: the Part 2 stop-reason evidence and which branch it selected,
      and the Part 1 reproduction outcome.
- [ ] Refine the design's "Verification walkthrough" section from draft to what
      was actually run.
- [ ] Mark the slice complete in `918-slice.review-grounding.md` and in entry 16
      of `900-slices.maintenance-and-refactoring.md`.
- [ ] Close [#94](https://github.com/ecorkran/squadron/issues/94),
      [#92](https://github.com/ecorkran/squadron/issues/92), and the
      install-commands finding of
      [#65](https://github.com/ecorkran/squadron/issues/65), each naming the
      implementing commit. #65's dependency findings stay open — they belong to
      the 907 Optional Dependency Split entry.
- [ ] Merge the branch to the target (`cf config get git.integration_branch`, or
      `main` if empty).
