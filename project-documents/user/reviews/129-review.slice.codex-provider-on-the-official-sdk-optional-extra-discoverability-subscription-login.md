---
docType: review
layer: project
reviewType: slice
slice: codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/129-slice.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md
aiModel: deepseek/deepseek-v4.1-flash
status: complete
dateCreated: 20261001
dateUpdated: 20261001
reviewedSha: c5ebaf6f296bb95f29d7d28482ded93080688761
revision_number: 3
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 18
turns: 12
promptTokens: 472261
cachedTokens: 418176
completionTokens: 20700
reasoningTokens: 18156
durationSeconds: 76.9
runId: run-20261001-p4-da7c47ac
squadronVersion: 0.17.0
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "`sq auth logout` spawns the runtime with no timeout and no failure-mode row"
    location: "project-documents/user/slices/129-slice.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md:107-109"
  - id: F002
    severity: concern
    category: error-handling
    summary: "Missing-extra failure not enumerated for the login and status spawn paths"
    location: "project-documents/user/slices/129-slice.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md:120-137"
  - id: F003
    severity: concern
    category: specification
    summary: "Version upper bound is both pinned and declared undecided"
    location: "project-documents/user/slices/129-slice.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md:97"
  - id: F004
    severity: note
    category: architecture-alignment
    summary: "Architecture's Authentication Patterns section is not amended for a net-new cross-provider capability"
    location: "project-documents/user/slices/129-slice.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md:89"
  - id: F005
    severity: note
    category: consistency
    summary: "CLI command name in the design (`sq model list`) does not match the shipped surface (`sq models list`)"
    location: "project-documents/user/slices/129-slice.codex-provider-on-the-official-sdk-optional-extra-discoverability-subscription-login.md:173"
---

# Review: slice — slice 129

**Verdict:** CONCERNS
**Model:** deepseek/deepseek-v4.1-flash

## Findings

### [CONCERN] `sq auth logout` spawns the runtime with no timeout and no failure-mode row

The Data Flow section states spawning is confined to "a Codex turn, `sq auth login/logout`, and `sq auth status`", and `logout()` is part of the `InteractiveLogin` Protocol. D7 defines exactly three wall-clock caps — `codex.turn_timeout_s` (turn.run), `codex.login_timeout_s` (the login `handle.wait()`), and `codex.account_timeout_s` (status/post-login). There is no key bounding `logout()`, and the "Failure Modes — Codex Turn" table has no row for a hung or failed logout despite it being an enumerated new I/O path that starts the app-server subprocess. As written, a runtime that never returns from `logout()` hangs the CLI indefinitely. Add a `logout` timeout (or explicitly fold it under an existing bound) and a failure row, consistent with how the login and status paths are bounded.

### [CONCERN] Missing-extra failure not enumerated for the login and status spawn paths

The failure table covers `openai_codex` not being installed only "at `create_agent`". But the design deliberately spawns/imports the SDK in two other places: `sq auth login` (Part C calls `login.login(mode)` → `AsyncCodex(config)` → `AsyncCodex.login_chatgpt()`), and `sq auth status` for a profile that is "already valid" (which `OAuthFileStrategy` reports on `~/.codex/auth.json` presence alone, independent of the package). With the extra absent but `~/.codex/auth.json` present, neither path's failure is specified: the missing-import raises `ImportError` rather than the SDK error the `account()` row anticipates, and the login path has no missing-package entry at all. Enumerate "extra absent" for the login and status spawn paths (same install-hint text as `create_agent`), or state explicitly that these paths are unreachable without the extra and why.

### [CONCERN] Version upper bound is both pinned and declared undecided

D1 writes the delivered constraint as `codex = ["openai-codex>=0.159.3,<1"]` while Special Considerations states "Version upper bound for `openai-codex` is not decided here … PM to say whether to cap." The design cannot both commit `,<1` and leave the cap open; whichever is intended, the other should be reconciled so the pyproject edit has one unambiguous target. (Related: the duplicate/numbering gap — D9 precedes D8 in the Technical Decisions list — makes the decision set harder to read as a contract.)

### [NOTE] Architecture's Authentication Patterns section is not amended for a net-new cross-provider capability

The slice reasons that `InteractiveLogin` (a `runtime_checkable` Protocol in `providers/auth.py`, with a shared `isinstance` dispatch in `cli/commands/auth.py`) does not contradict the architecture's "squadron does not unify authentication." The reasoning is sound — it delegates to the runtime and stores no credentials — but it is a new cross-provider capability that any future OAuth-backed provider can adopt without CLI changes, which is exactly the kind of seam the section documents. Deferring the one-sentence amendment to "when a second provider adopts it" risks a window where the architecture text no longer describes the code. Either add the sentence now or record an explicit follow-up trigger; the current text relies on a reader finding this slice's justification.

### [NOTE] CLI command name in the design (`sq model list`) does not match the shipped surface (`sq models list`)

The slice specifies the discoverability marker for "`sq model list`" (also used in the Value and Data Flow sections). The registered command is `sq models` with a `list` subcommand (`app.add_typer(models_app, name="models")`; `@models_app.command("list")`). This is a doc/surface mismatch rather than an architectural violation, but the acceptance criteria and verification walkthrough should name the real command so the marker's presence can be checked as written.

### Run Digest

- Response length: 5400 chars
- Response is newline-free: no
- Tool calls made: 18
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 384000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 79639
- Effort: backend default
- Turns: 12
- Tokens — prompt / cached / completion / reasoning: 472261 / 418176 / 20700 / 18156
- Duration: 76.9 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5
