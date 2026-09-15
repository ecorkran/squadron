---
docType: notes
layer: project
reviewType: code
slice: review-a-pr
project: squadron
respondsTo: project-documents/user/reviews/382-review.code.review-a-pr.md
reviewedSha: f72420b0e5a24039a2f3495094cdb4ea90229605
status: complete
dateCreated: 20260915
dateUpdated: 20260915
resolution:
  - id: F001
    disposition: fixed
  - id: F002
    disposition: fixed
  - id: F003
    disposition: rejected
  - id: F004
    disposition: fixed
  - id: F005
    disposition: deferred
    issue: 104
---

# Review response: code — slice 382

Four of five findings accepted; F003 rejected on the design record. Verified against the
code at each cited location before deciding — the reviewer's line references were accurate
throughout.

## F001 — `assemble_pr_metadata` network call outside the `CodeHostError` handler — FIXED

Confirmed real. `HostResponseMalformedError` subclasses `CodeHostError`
(`codehost/errors.py:149`), and `list_unresolved_discussions` raises it on a malformed
GraphQL payload (`codehost/github_cli.py:399`). The call sat immediately after the `try`
block, so an adapter failure during discussion fetch produced a traceback where every other
adapter failure renders through `render_code_host_error` and exits 1.

Fixed by moving the call inside the existing handler rather than adding a second one — one
handler, one rendering path. Regression test:
`test_discussion_fetch_failure_renders_as_an_adapter_error_not_a_traceback`.

## F002 — sweep/creation race — FIXED, and the design decision amended

Confirmed real, and slightly wider than the review states. `sweep_orphans` runs at the *top*
of `__enter__`, before `mkdir` — so the exposure is not only the gap between `git worktree
add` and the lock write, but any concurrent run's sweep overlapping another's setup. The load
test could not have caught it: it asserts only non-colliding paths and no exceptions, and a
swept-mid-setup worktree may produce neither.

The obvious fix — write the lock before creating the worktree — is not available: `git
worktree add` **refuses a pre-existing target directory** (`fatal: '<path>' already
exists`), verified directly against git rather than assumed. So the claim cannot live inside
the directory it protects.

**Implemented:** a sibling claim file, `<root>/<name>.claim`, written before `git worktree
add` and unlinked once the real lock lands — and on every creation failure path. It carries
the same pid and start time payload as the lock, so `_read_lock`/`_is_orphan` interpret both
under one set of rules: a claim whose writer has died is swept exactly like a dead lock, and
only a *live* claim protects an unlocked directory. `sweep_orphans` skips the claim files
themselves for free, since that loop already ignores non-directories.

This narrows design decision D3's "a worktree whose lock is absent entirely is also an
orphan," which was correct for a crashed run but deleted live ones. The slice design carries
an explicit amendment recording the change and why the claim sits outside the worktree.

Four regression tests: live claim protects, dead claim does not, claim removed on success,
claim removed on creation failure.

## F003 — `--no-tools` disables project settings against a trusted checkout — REJECTED

This contradicts design decision D8, which was made deliberately and for a reason the finding
does not engage.

D8's rationale is that `setting_sources: ["project"]` resolves settings from the agent's own
`cwd`, that project settings may define `PreToolUse` hooks, and — decisively — that **neither
`permission_mode` nor `allowed_tools` constrains hook execution**. `--no-tools` governs the
tool allowlist. It does not disable hooks. Restoring `setting_sources=["project"]` on the
`--no-tools` path would therefore reopen exactly the execution path D8 closed, in the one
command whose entire purpose is reviewing code from untrusted contributors.

The finding's premise — that `--no-tools` means "single root, the trusted checkout, so
nothing untrusted is involved" — holds for the *cwd*, but project scope also loads skills,
commands, subagents and `CLAUDE.md`, several of which search parent directories. And D8
records that nothing of value is lost: D1 already supplies rules and `CLAUDE.md` from the
trusted checkout through squadron's own injection, so the conventions arrive by the safe path
regardless.

The design states the conclusion directly: the safe value depends on what is being reviewed,
so it belongs to the invocation rather than the template. No change.

## F004 — zero-width space as an invisible literal — FIXED

Confirmed by byte inspection: `od` showed `342 200 213` (UTF-8 U+200B) in the source at
`review/builders/code.py:14`. Replaced with the explicit escape `"​"`. The rendered value
is identical; the source is now readable.

## F005 — private imports from `review.py` — DEFERRED to issue #104

Agreed in substance: four `# pyright: ignore[reportPrivateUsage]` suppressions remove the only
automated signal that a rename or signature change in `review.py` breaks `review_pr.py`.

Not fixed here. These names are already imported directly by six test modules, and
`tests/cli/test_review_pr.py` monkeypatches `squadron.cli.commands.review_pr._run_review_command`
by string path — promoting them touches ~25 call sites across files this slice did not
otherwise change, on top of an already-merged slice. Filed as issue #104 with the suggested
shape (a shared `review_common.py`), to fold into 383's work on this module.

## Verification

- `ruff format` — 533 files unchanged; `ruff check` — all checks passed; `pyright` — 0 errors.
- Full suite: **3974 passed, 4 skipped**.
- The 3 failures in `tests/documents/test_schema_drift.py` are cf issue #88 — pre-existing,
  unrelated to this slice, and failing before any work in this response.
