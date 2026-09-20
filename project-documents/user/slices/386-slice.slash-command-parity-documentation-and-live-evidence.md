---
docType: slice-design
slice: slash-command-parity-documentation-and-live-evidence
project: squadron
parent: user/architecture/380-slices.pull-request-workflow.md
dependencies: [381, 382, 383, 384, 385]
interfaces: []
dateCreated: 20260919
dateUpdated: 20260920
status: complete
---

# Slice Design: Slash-Command Parity, Documentation, and Live Evidence

## Overview

381 through 385 built three capabilities and proved each against the fake runner, with one live
run apiece. None of them is reachable from a slash command, none appears in the README, the
quickstart, or the command reference, and no single run has exercised all three together on one
pull request. This slice closes those three gaps and adds no capability.

It is the initiative's integration slice, and its weight is in three places.

The first is **what parity means for a transport that is a prompt** (D1, D2). A squadron slash
command is a markdown file telling a Claude Code session which `sq` command to run. It has no
code path of its own, so "produces the same artifact" cannot be tested by running it under
pytest. The design makes parity structural — the transport adds nothing to the command line —
and then tests the one thing that can drift: the command file's description of the CLI surface.

The second is **an agent transport in front of a host write** (D3). `--post` and `sq pr create`
are the initiative's two writes. A CLI refuses and prints a remediation; an agent reading that
output may carry the remediation out. The architecture's "never surprise the operator" has to be
restated for a transport that can act.

The third is **the live run** (D6), which needs the integration branch on the host in its
current state — a precondition, since `squadron-pr` is 80 commits ahead of `origin/squadron-pr`.

## Value

**User value.** The PR capabilities become discoverable: a reader of the README learns that
squadron reviews, comments on, and opens pull requests, including in a repository squadron never
planned. An operator inside Claude Code reaches all of it without leaving the session.

**Evidence.** One recorded run — create, review, post, post again — on a real pull request of
this initiative's own branch. Every earlier live run exercised one capability; this one shows
they compose.

**Developer value.** A drift test between the CLI's registered options and the command files.
Today nothing fails when a flag is added to `sq review code` and `commands/sq/review.md` is not
updated; after this slice, something does, for the PR surface.

## Technical Scope

### Included

- `commands/sq/review.md`: a `pr` subcommand section, and `pr` added to the valid-subcommand
  list and usage block.
- `commands/sq/pr.md`: new file, `/sq:pr` with `show` and `create`.
- `tests/cli/test_install_commands.py`: the bundle count and `EXPECTED_COMMANDS` gain `pr.md`.
- A new test module asserting command-file / CLI surface agreement for the three PR commands
  (D2), and a documentation-example parse test (D5).
- `README.md`: a "Pull requests" section — review, post, create, the unplanned-repository path.
- `docs/QUICKSTART.md`: the `gh` doctor rows explained; the command count in the example
  output corrected.
- `docs/COMMANDS.md`: `review pr`, a new `pr` section (`pr show`, `pr create`), and
  `review.external_reviews_dir` under `config`.
- `CHANGELOG.md`: one user-facing bullet for the slash-command transports (the capabilities
  themselves already have theirs).
- The live end-to-end run and its record in `DEVLOG.md`.
- Closing out initiative 380: slice plan entry 6 checked, plan and architecture `status`
  updated.

### Excluded

- **Any change to `sq review pr`, `sq pr show`, or `sq pr create`.** If the live run or the
  documentation pass finds a defect, it is fixed as a defect with its own commit and named in
  the DEVLOG — the slice does not plan for one.
- **An MCP transport.** `src/squadron/mcp/` is an empty package; squadron exposes no review
  tool over MCP today, so there is nothing to bring to parity. The standing parity rule applies
  when one exists.
- **A pipeline PR input.** Future Work item 2 in the slice plan.
- **Merging `squadron-pr` into `main`.** PM-only, after this slice and further testing.
- **Retrofitting the drift test to the pre-existing subcommands** (`code`, `slice`, `tasks`,
  `arch`, `resolve`). The test is written so that adding them is a list entry (D2), but their
  command-file sections were not authored against it and bringing them into agreement is
  separate work. Logged as a GitHub issue at task time.

## Dependencies

### Prerequisites

- **381 through 385** merged into `squadron-pr` — all five are. 382, 384, and 385 are the plan
  entry's stated dependencies; 381 (`sq pr show --json`, doctor checks) and 383 (`--reviews-dir`,
  `review.external_reviews_dir`) are consumed directly and listed for that reason.
- **`squadron-pr` pushed to `origin`** before the live run (D6). This is an outward-facing
  action awaiting PM direction; it is a precondition of the live-run tasks, not one of them.
- `gh` authenticated for `github.com` on the operator machine.

### Interfaces Required

- The Typer command objects for `review pr`, `pr show`, `pr create`, reachable from the `sq`
  app for option introspection.
- `sq pr show --json` (`_render_json`), the deterministic output 381 shaped for this slice.
- `sq review pr --post --dry-run`, which prints `compose_comment`'s body without a host write.
- `_get_commands_source()` from `cli/commands/install.py`, for locating the bundled files.

## Architecture

### Component Structure

```
commands/sq/
  review.md        + "## Subcommand: pr"        → sq review pr {remainder}
  pr.md            new: show | create           → sq pr show|create {remainder}

tests/cli/
  test_install_commands.py     count 9 → 10, EXPECTED_COMMANDS + pr.md
  test_command_surface.py      new: D2 drift test
tests/docs/
  test_pr_doc_examples.py      new: D5 example-parse test

README.md, docs/QUICKSTART.md, docs/COMMANDS.md, CHANGELOG.md, DEVLOG.md
```

No file under `src/squadron/` changes. Installation needs no change either:
`install_commands` copies every `*.md` under each bundle subdirectory and records it in the
receipt, so `pr.md` installs and uninstalls with the rest.

### Data Flow: a slash-command invocation

```
  operator: /sq:review pr 116 --model glm-5.3 --post
      │
      ├─ Claude Code loads commands/sq/review.md, $ARGUMENTS = "pr 116 --model glm-5.3 --post"
      ├─ first word "pr" selects the section; remainder = "116 --model glm-5.3 --post"
      ├─ session runs, once:   sq review pr 116 --model glm-5.3 --post
      │        └─ the CLI does everything: resolve, fetch, review, save, post
      └─ session shows the CLI's output; on FAIL/CONCERNS highlights findings
```

The artifact is written by the CLI process. The transport's whole contribution is the argument
string, which is why D1 constrains it to be the operator's own.

## Technical Decisions

### D1 — The PR transports pass the remainder through verbatim and inject nothing

The existing `/sq:review` sections have a number shorthand that appends `-v`. The `pr` section
does not get one, for two reasons.

The PR target grammar already makes a bare number meaningful to the CLI (`sq review pr 116`),
so there is no shorthand to expand — the number *is* the full invocation.

And an injected flag is a difference between the transports. `-v` happens to be harmless —
prompt capture into the artifact begins at verbosity 2 (`review_client.py`) — but "harmless
today" is exactly the kind of fact that stops being true without anyone editing the command
file. The rule is simpler and stronger: `/sq:review pr X` runs `sq review pr X`, and
`/sq:pr show|create X` runs `sq pr show|create X`. Parity then holds by construction for every
flag, including ones added later.

An absent remainder is valid and passes through as absent: `sq review pr` with no target
reviews the current branch's PR.

### D2 — Parity is tested as surface agreement, plus one deterministic live comparison

A command file cannot be executed by pytest, so the test suite cannot compare artifacts across
transports. What it can pin is the two ways the transport goes wrong:

1. **The delegation line drifts.** The test asserts each PR section contains its delegation
   command with the remainder placeholder and nothing appended.
2. **The described surface drifts from the real one.** The test introspects the Typer/Click
   command for `review pr`, `pr show`, and `pr create`, collects every registered long option,
   and asserts set equality with the `--flag` tokens found in that command's section of the
   command file. A flag in the CLI but not the file is an undocumented capability; a flag in
   the file but not the CLI is an instruction to pass something the CLI will reject.

Section extraction is by heading (`## Subcommand: pr` to the next `## ` or end of file) and flag
extraction is a lenient token scan (`--[a-z][a-z-]*` anywhere in the section, inside or outside
backticks), per the project's parsing rules. The fixture is the real bundled file, located
through `_get_commands_source()`, not a synthetic one. The commands under test are one list of
(command path, file, section heading) entries, so extending coverage to `code` or `resolve`
later is an added entry, not a new test.

`--help` is excluded from the comparison by name, once, in the test module's constants.

**The live comparison** is where "identical artifacts" is demonstrated, and it has to be honest
about what can be identical. Two reviews of one PR by one model are two completions; their
prose differs, as 385's walkthrough already established for dry-run versus real creation. So
the live check has two tiers:

- **Byte-identical, no model:** `sq pr show 116 --json` run from a terminal and
  `/sq:pr show 116 --json` run in a session produce the same JSON. This is what `_render_json`
  was shaped for.
- **Structurally identical, with a model:** one `sq review pr` and one `/sq:review pr` on the
  same PR and model, each with its own `--reviews-dir`. The two artifacts have the same
  filename, the same frontmatter keys, and equal values for every deterministic field (`pr`
  record, `reviewedSha`, `sourceDocument`, `reviewType`, `aiModel`, rules source). Verdict and
  findings are model output and are recorded, not compared.

### D3 — Host writes through an agent transport: run once, never remediate

The architecture's rule is that squadron never writes to a PR unless asked on that invocation.
Through a slash command there is a second actor who could do the asking: the session. The
command files therefore carry four instructions, stated in the file and not left to inference:

- **`--post` is passed only when the operator typed it.** The `pr` section never suggests
  adding it after a review, and never re-runs a finished review with it.
- **A write command runs once.** On a non-zero exit from `sq review pr --post` or
  `sq pr create`, the session shows the output and stops. No retry — 385 D8 gives the reason:
  a create that failed after landing opens a second PR when retried.
- **Printed remediation is shown, not executed.** `sq pr create` refuses an unpushed branch by
  printing the `git push` to run. That line exists because squadron does not push. A session
  that runs it has made squadron push by proxy, so `pr.md` says: show the command, do not run
  it. Likewise for a refused integration branch — the session does not pass `--base` on the
  operator's behalf.
- **`--dry-run` is offered, not substituted.** The file documents it; the session does not
  convert a create into a dry run or the reverse.

These are prompt instructions, so they are not enforceable the way a code path is. The design
accepts that: the CLI is still the only thing that writes, its own refusals still hold, and the
instructions close the gap between "the CLI refused" and "the session worked around it."

### D4 — Provider profile inside a session is documented from observation, not decided here

385's walkthrough recorded that the `sdk` profile could not be exercised from inside the Claude
Code session running it, and used `--profile openrouter` instead. A slash command always runs
inside a session, and `sq review pr` and `sq pr create` both default to `sdk`.

The transport does not pick a profile — that would be an injected flag (D1). What this slice
owes is the fact: one task runs `sq review pr` with the default profile from inside a session,
records what happens (success, or the exact error text), and the command files and README state
that observed behavior and the working invocation. If the default fails inside a session with
an unhelpful message, that is a CLI defect, logged as an issue and linked from the DEVLOG — not
patched over in the command file.

### D5 — Documentation placement, and how "examples run as written" is held

| Document | Gains |
|---|---|
| `README.md` | "Pull requests" section after "Reviews in depth": review a PR (target forms), `--post` with `--dry-run`, `sq pr create` with `--dry-run`, base selection in one sentence, the five body sections named, and the unplanned-repository path — where the artifact goes, `--reviews-dir`, `review.external_reviews_dir`, and that the chosen location and its source are printed. States the two host writes and that squadron never pushes. |
| `docs/COMMANDS.md` | `### review pr` under `review` with the full option table; a new `## pr` with `### pr show` and `### pr create`; `review.external_reviews_dir` under `config` with its default tree. |
| `docs/QUICKSTART.md` | The `gh CLI` and `gh hosts file` rows: what each checks, that doctor makes no subprocess or network call so an OK row means *present*, not *authenticated*, and the fix hints. Command count in the sample output corrected for the tenth file. |
| `CHANGELOG.md` | One bullet: `/sq:review pr` and `/sq:pr`. 381–385 already wrote the bullets for show, review, persistence, post, and create. |

Doctor's sample output in QUICKSTART is pasted from a real `sq doctor -v` run, not typed.

"Examples run as written" is held two ways. **Mechanically:** a test collects every line
beginning `sq review pr` or `sq pr` from fenced code blocks in the three documents, splits it
with `shlex`, and parses it against the real Click command without invoking it, so an example
naming a flag that does not exist, or omitting a required value, fails the suite. Extraction is
lenient about a leading `$ ` prompt and trailing comments. **Live:** every example in the README
section is one of the commands the D6 run executes, so the examples and the evidence are the
same invocations.

Examples use placeholder targets only where the grammar requires showing a form
(`owner/repo#n`); none hardcodes a value the reader is meant to look up.

### D6 — The live run is on this slice's own branch, and lands the way its predecessors did

The plan entry asks for a run "on a real PR of this initiative's own branch (review, post, and
a PR created by `sq pr create`)". PR #116 (slice 385) was created by `sq pr create` and is
still open, but its branch is merged locally, and it will show as merged the moment
`squadron-pr` is pushed. The 386 slice branch is the natural subject: it will exist, be pushed,
and have a small, reviewable diff of command files and documentation.

Sequence, after implementation is otherwise complete:

1. `squadron-pr` is on `origin` at its current head (precondition, PM-authorized).
2. Push `386-slice.slash-command-parity-documentation-and-live-evidence`.
3. `sq pr create --dry-run`, then `sq pr create` → the PR. Base is `squadron-pr` from
   `git.integration_branch`, confirmed on the host — the success branch of 385 D1's middle term.
4. `sq pr show <n> --json` from a terminal and via `/sq:pr show`; compare (D2 tier one).
5. `sq review pr <n> --post --dry-run`, then `--post` → one squadron comment.
6. `/sq:review pr <n> --post` from a session → still one comment, updated (384's idempotency,
   now exercised across transports); artifacts compared (D2 tier two).
7. The four target forms through `sq pr show` — number, URL, `owner/repo#n`, branch — closing
   the success-path gap 381's tasks deferred to this slice for want of an open PR.
8. `gh pr view <n> --json body,comments` recorded: five sections, one squadron comment.

Each step's command, exit code, and the identifying output (PR URL, comment URL, artifact
paths, shas) go into the DEVLOG entry. The two review artifacts are kept under
`project-documents/user/reviews/` as 385's was.

**Landing.** Every slice of this initiative landed as a local `--no-ff` merge into
`squadron-pr`, with its live PR as evidence rather than as the merge route. 386 does the same.
After the merge is pushed, the host marks the PR merged, which is the correct final state for
it and is noted in the DEVLOG.

## Integration Points

### Provides

Nothing new to other slices. The drift test's command list is the extension point for the
pre-existing subcommands.

### Consumes from Other Slices

- **381**: `sq pr show --json`; the target grammar the documentation describes; doctor's `gh`
  checks.
- **382**: `sq review pr` and its option set — the surface the `pr` section must equal.
- **383**: `--reviews-dir`, `review.external_reviews_dir`, the printed location and source, and
  the PR-keyed artifact name the documentation shows.
- **384**: `--post`, `--dry-run`, the one-comment-per-login behavior the live run demonstrates.
- **385**: `sq pr create`, its refusals (whose remediation D3 tells the session not to execute),
  and the five-section body.

## Success Criteria

### Functional

- `/sq:review pr <target> [flags]` runs `sq review pr <target> [flags]` with nothing added or
  removed; `/sq:pr show` and `/sq:pr create` likewise.
- `/sq:review` with `pr` is no longer reported as an unrecognized subcommand; `/sq:pr` with a
  missing or unknown subcommand shows usage and stops.
- `sq install-commands` installs ten files under `sq/`, `pr.md` among them, recorded in the
  receipt; uninstall removes it.
- `pr.md` and the `pr` section state the D3 rules: no unrequested `--post`, no retry of a
  write, printed remediation shown and not run.
- README, QUICKSTART, and COMMANDS cover review, post, and create, the unplanned-repository
  path, `--reviews-dir`, `review.external_reviews_dir`, and the `gh` doctor rows.
- `sq pr show <n> --json` output is byte-identical across the two transports for one PR.
- CLI and slash-command review artifacts for one PR and model share filename, frontmatter keys,
  and every deterministic field value.
- The recorded run shows a PR created by `sq pr create` whose body has all five sections, and
  exactly one squadron comment on it after two posts, one from each transport.
- The observed behavior of the default profile inside a session is documented (D4).

### Technical

- The surface test fails when an option is added to or removed from any of the three commands
  without the command file changing, demonstrated by a test that runs the comparison against a
  deliberately incomplete section string.
- The documentation-example test parses every `sq review pr` / `sq pr` example in the three
  documents against the real commands and fails on an unknown flag.
- Both tests read the real bundled and repository files, not fixtures.
- No file under `src/squadron/` changes; `sq review code`, slice persistence, and the pipeline
  action pass their existing tests unchanged.
- `ruff format`, `ruff check`, and `pyright` clean.

### Verification Walkthrough

Run for real at the end of Phase 6 against **PR #119**
(https://github.com/ecorkran/squadron/pull/119), created from this slice's own branch. `<n>` is
`119` throughout. One caveat found along the way: `sq pr create` with the default `sdk` profile
fails inside a Claude Code session (nested-session guard on the one-shot composer's subprocess
launch) — every `sq pr create` invocation below uses `--profile openrouter --model
openai/gpt-4o-mini`, the same fallback 385's walkthrough used. `sq review pr` is unaffected; its
default profile works inside a session (see DEVLOG, "Slice 386 implementation and live run").

**1. Transports installed.**

```bash
sq install-commands
ls ~/.claude/commands/sq/pr.md
```

Ten commands reported, `sq/pr.md` listed.

**2. Create the PR from this slice's branch.**

```bash
git checkout 386-slice.slash-command-parity-documentation-and-live-evidence
git push -u origin 386-slice.slash-command-parity-documentation-and-live-evidence
sq pr create --dry-run --profile openrouter --model openai/gpt-4o-mini
sq pr create --profile openrouter --model openai/gpt-4o-mini
```

stderr named `base: squadron-pr (source: integration-branch)`; stdout ended with
`https://github.com/ecorkran/squadron/pull/119`. Confirmed independently via
`gh pr view 119 --json baseRefName` → `squadron-pr`.

**3. Deterministic parity.**

```bash
sq pr show 119 --json > /tmp/cli-show.json
```

In a Claude Code session: `/sq:pr show 119 --json`, output saved to `/tmp/slash-show.json`.
`diff /tmp/cli-show.json /tmp/slash-show.json` printed nothing — byte-identical.

**4. Review and post, CLI.**

```bash
sq review pr 119 --profile openrouter --model openai/gpt-4o-mini \
  --reviews-dir /tmp/parity-cli --post --dry-run
sq review pr 119 --profile openrouter --model openai/gpt-4o-mini \
  --reviews-dir /tmp/parity-cli --post
```

The dry run printed the comment and wrote nothing to the host. The second call posted
[issuecomment-5751705564](https://github.com/ecorkran/squadron/pull/119#issuecomment-5751705564).

**5. Review and post, slash command.** In a session:

```
/sq:review pr 119 --profile openrouter --model openai/gpt-4o-mini --reviews-dir /tmp/parity-slash --post
```

The session ran that exact `sq review pr` command once, and posted to the **same** comment
(`#issuecomment-5751705564`) rather than a new one — 384's idempotency held across transports.
Then:

```bash
gh pr view 119 --json comments --jq '[.comments[] | select(.body | contains("squadron"))] | length'
ls /tmp/parity-cli /tmp/parity-slash
```

Output: `1`. Same artifact filename (`github.com-ecorkran-squadron-119-review.code.md`) in both
directories; frontmatter compared field by field — `pr`, `reviewedSha`, `sourceDocument`,
`reviewType`, `aiModel`, `rulesSource` all equal; `toolCallsMade` and `findings` differed, as
expected for two calls to a non-deterministic model (recorded, not compared).

All four target forms resolved PR 119 identically via `sq pr show`: `119`, the full PR URL,
`ecorkran/squadron#119`, and the branch name.

**6. Refusal is shown, not worked around.** On a scratch branch with an unpushed commit, in a
session: `/sq:pr create --dry-run`. The session showed the refusal and the printed remediation
(`git push -u origin scratch-386-refusal-test`) and ran nothing further; `git ls-remote origin
scratch-386-refusal-test` confirmed the branch never reached the host. Scratch branch deleted
afterward.

```bash
gh pr view 119 --json body,comments
```

All five body sections present (`## What changed`, `## Why`, `## How it was verified`,
`## Known gaps`, `## Review provenance`); exactly one squadron comment.

**7. Documentation.**

```bash
pytest tests/docs/test_pr_doc_examples.py tests/cli/test_command_surface.py -q
sq doctor -v
```

Both test modules pass (6 passed); doctor's `gh CLI` and `gh hosts file` rows match the
QUICKSTART text, and the install count reads `10 command(s)`.

## Implementation Notes

### Order

1. `commands/sq/pr.md` and the `pr` section of `review.md`; install-test count and map.
2. `test_command_surface.py` — written against the files from step 1, so the first run proves
   the files agree with the CLI or names what is missing.
3. D4's observation, since its result is documentation input.
4. README, COMMANDS, QUICKSTART, CHANGELOG; then `test_pr_doc_examples.py`.
5. Precondition check: `squadron-pr` on `origin`. Then the live run (D6) and its DEVLOG record.
6. Close-out: walkthrough refined, slice plan entry 6 checked, initiative status updated.

Steps 1–4 need no host access and no PM action; only step 5 waits on the push.

### Special Considerations

- The live run performs the initiative's two host writes on a public repository. Each is run
  by the operator's explicit command, preceded by its `--dry-run`.
- Relative effort: 2/5, as planned. The command files and documentation are the bulk; the two
  tests are small; the live run is sequencing, not building.
