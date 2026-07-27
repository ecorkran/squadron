<!-- Forked from github:ecorkran/tech-debt-audit (MIT). Original: github:ksimback/tech-debt-skill -->
---
name: tech-debt-audit
description: Thorough, user-invoked tech debt and architecture audit of the current codebase. Produces audit file as specified with file-cited findings, severity, effort estimates, and a required "looks bad but is actually fine" section. Use when the user asks for a debt audit, codebase health check, architecture review, or code quality assessment of an entire repo. Does not auto-invoke.
disable-model-invocation: true
---

# Tech Debt Audit

A Claude Code skill that conducts a deliberate, opinionated audit of an entire codebase and produces the audit file with cited findings.

When invoked via `/tech-debt-audit`, follow the protocol below. Everything from here through the `---` divider is the protocol Claude executes. The section after the divider is documentation for humans installing or maintaining this skill.

---

## Operating principles

Find what's actually wrong. Not diplomatic. Not surface-only. Don't pattern-match to generic best practices without grounding in this specific repo. No sycophancy. No "overall the codebase is well-structured" filler.

Cite `file:line` for every concrete finding. Vague claims like "the code generally..." don't count. Read code before judging it — a pattern that looks wrong in isolation may be load-bearing.

## Phase 1: Orient

Do not skip this. Forming opinions before understanding the system produces bad audits.

1. Read the README, package manifest (`package.json` / `pyproject.toml` / `Cargo.toml` / `go.mod`), and any architecture and project documents in `project-documents/user/architecture/`.

2. Map the directory structure and identify the major modules / layers.
3. Run `git log --oneline -200` and `git log --stat --since="6 months ago"` to see what's actually changing and where churn concentrates.
4. Identify entry points, hot paths, and cold corners.
5. List the top 20 largest files by line count, and the 20 files most frequently modified in the last 6 months. The intersection is where debt usually hides.
6. Use `TodoWrite` to publish a plan so the user can see progress through the phases.

Write a 1–2 paragraph mental model of the architecture before proceeding. If your model contradicts the README, flag it — that itself is a finding.

## Phase 2: Audit across these dimensions

Use `rg`, `ast-grep`, and language-native tooling to find concrete examples. Cite `path/to/file.ext:LINE` for every finding.

1. **Architectural decay** — circular deps, layering violations, god files (>500 LOC) and god functions, duplicated logic across 3+ sites where an abstraction should exist, abstractions that exist but nobody uses, dead code (unused exports, unreachable branches, stale commented-out blocks).

2. **Consistency rot** — multiple ways of doing the same thing (HTTP clients, error handling, logging, config loading, validation, date handling). Naming drift. Folder structure that no longer reflects what the code actually does.

3. **Type & contract debt** — `any` / `unknown` / `as any` / `# type: ignore` / loose dicts. Untyped API boundaries. Missing schema validation at trust boundaries.

4. **Test debt** — run coverage if available; identify gaps on critical paths. Tests that assert implementation rather than behavior. Skipped or flaky tests. High-churn files with no tests.

5. **Dependency & config debt** — `pnpm audit` / `pip-audit` / `cargo audit` for CVEs. Unused deps. Duplicate deps doing the same job. Env var sprawl (referenced but not documented; defaults inconsistent across envs).

6. **Performance & resource hygiene** — N+1 queries, sync work in async paths, blocking I/O on hot paths, uncleaned listeners or handles, unnecessary serialization.

7. **Error handling & observability** — swallowed exceptions, blanket catches, errors logged but not handled, inconsistent error shapes across modules, missing structured logs on critical paths.

8. **Security hygiene** — hardcoded secrets, string-concat SQL, missing input validation at trust boundaries, permissive auth or CORS, weak crypto.

9. **Documentation drift** — README claims that don't match reality, comments that contradict adjacent code, public APIs without docstrings.

### Category vocabulary

Every finding's `Category` — in the findings table and in the machine-readable block — must be one of these ten kebab-case values, and nothing else:

| Value | Dimension |
|---|---|
| `architectural-decay` | 1. Architectural decay |
| `consistency-rot` | 2. Consistency rot |
| `type-contract-debt` | 3. Type & contract debt |
| `test-debt` | 4. Test debt |
| `dependency-config-debt` | 5. Dependency & config debt |
| `performance-resource` | 6. Performance & resource hygiene |
| `error-handling-observability` | 7. Error handling & observability |
| `security-hygiene` | 8. Security hygiene |
| `documentation-drift` | 9. Documentation drift |
| `other` | none of the above |

`other` exists for findings that are genuinely real but fit none of the nine dimensions. Using it is **not** a failure — a good finding in the wrong-shaped taxonomy is still a good finding, and a rising `other` share is useful evidence that the dimensions need revisiting. What *is* a failure is inventing a category outside this list: downstream tooling cannot compare across audits when the vocabulary drifts, so an invented value is silently unusable data rather than a visible error.

## Phase 3: Deliverable

### File Naming and Location

- Create markdown file `analysis/nnn-analysis.{project-name}{.subproject?}.md` where nnn starts at 940 (analysis range).  This file is known as the audit file.
- Use existing file naming conventions *and required YAML frontmatter* from `file-naming-conventions.md`.
- Add a `model:` field to the frontmatter naming the model that produced the
  audit. Report your own model identifier as precisely as you know it. If you
  cannot determine it, write `model: unknown` — do not guess a plausible name.
  Audits from different models are not comparable: finding counts differ
  systematically between them, so an audit that cannot say what produced it
  cannot be compared to any other.

### File Contents
- **Executive summary** — max 10 bullets, ranked by impact.
- **Architectural mental model** — your understanding of the system as it actually is.
- **Findings table** — columns: `ID | Category | File:Line | Severity (Critical/High/Medium/Low) | Effort (S/M/L) | Description | Recommendation`. Aim for 30–80 findings; padding past that is noise.
- **Top 5 "if you fix nothing else, fix these"** — with concrete diff sketches or refactor outlines, not vague advice.
- **Quick wins** — Low effort × Medium+ severity, as a checklist.
- **Things that look bad but are actually fine** — calls you considered flagging and chose not to, with reasoning. **This section is required.** If it's empty, you didn't look hard enough.
- **Open questions for the maintainer** — things you couldn't tell were debt vs. intentional.
- **Machine-readable findings block** — at the very end of the audit file, after every other section, emit the block described below. This is **in addition to** the findings table, not a replacement: the same findings are serialized twice, because humans read the table and tools read the block. Every finding in the table appears in the block and vice versa.

### Machine-readable findings block

Emit this as the last thing in the audit file, delimited exactly as shown:

<!-- squadron:findings:begin v1 -->
```yaml
findings:
  - id: F001
    category: architectural-decay
    location: src/payments/processor.ts:1240
    severity: Critical
    effort: L
    summary: 1400-line god class handling routing, validation, retry, and reconciliation
```
<!-- squadron:findings:end -->

Rules for the block:

- The two HTML comment delimiters must appear exactly as written, once each, wrapping a single fenced ```yaml block.
- Each entry carries exactly six fields: `id`, `category`, `location`, `severity`, `effort`, `summary`.
- `category` must be drawn from the closed vocabulary in Phase 2 — never invent a value outside it.
- `severity` is one of `Critical`, `High`, `Medium`, `Low`; `effort` is one of `S`, `M`, `L`.
- `summary` is the finding's Description, as prose, on one line.
- `recommendation` is deliberately **not** in the block. It is advice for a human reader, it is the longest field, and no tool consumes it. It stays in the findings table only.

## Rules

- Cite `file:line` for every concrete finding.
- If unsure whether something is debt or intentional, ask in the open questions section — don't assert.
- Don't recommend rewrites. Recommend specific, scoped changes.
- Don't pad. If a category has nothing material, write "Nothing material" and move on.
- No sycophancy. Tell the user what's broken.

## Stack-specific tooling

Detect the stack from the manifest and run the relevant tools. Run them in parallel when possible.

- **TypeScript / JavaScript** — `npm audit`, `npx knip` (dead exports), `npx madge --circular` (circular deps), `npx depcheck` (unused deps), `tsc --noEmit` for type drift.
- **Python** — `pip-audit`, `ruff check`, `vulture` (dead code), `pydeps --show-cycles`, `mypy --strict` for type drift.
- **Rust** — `cargo audit`, `cargo udeps`, `cargo machete`, `cargo clippy -- -W clippy::pedantic`.
- **Go** — `govulncheck`, `go vet`, `staticcheck`, `golangci-lint run`.
- **Dart** — `dart pub outdated` (dependency drift), `dart analyze` (static analysis/type drift), `dart format --set-exit-if-changed .` (format drift), `dart run dependency_validator` (unused/missing deps), `dart run pana .` (package health).
- **Flutter** — `flutter pub outdated` (dependency drift), `flutter analyze` (static analysis/type drift), `dart format --set-exit-if-changed .` (format drift), `dart run dependency_validator` (unused/missing deps), `flutter test` (widget/unit test drift).

If a tool isn't installed, note it in the audit and move on rather than blocking. Do not install dev tools globally without permission.

## Large repos: spawn subagents

If the repo is >50k LOC or has >5 top-level modules, dispatch subagents (Task tool) in parallel — one per module — and synthesize their reports. Serial reading on a large repo eats the context window before findings can be written.

Each subagent gets: scope (one module), the dimensions list above, the citation requirement, and a 200-finding cap. The main agent merges, dedupes, and ranks.

## Repeat-run mode

**Unless this invocation requests an independent run** (see below), repeat-run mode applies: if audit file already as specified here exists in the repo, read it first. Mark resolved findings as `RESOLVED`, update stale ones, and tag new findings with `NEW`. This turns the audit into a living document tracked over time.

## Independent-run mode

If the invocation is prefixed with the line:

```
INDEPENDENT RUN: do not read or update any existing audit file
```

then repeat-run mode above does **not** apply. Do not read any existing audit file, do not diff against one, and do not tag findings `RESOLVED` or `NEW`. Audit the codebase as if for the first time and write a fresh audit file.

Why: repeated audits of unchanged code are used to measure the audit's own run-to-run variance. A run that reads the previous run's output is not an independent sample of that variance — it is anchored to it, which makes the measured spread look smaller than it really is.

Interactive users are unaffected. Absent that line, the living-document behavior above is unchanged.

---

# Project documentation

Everything below is for humans installing, using, or contributing to this skill. It is not part of the audit protocol.  Note that these instructions are updated to install the fork, which updates the output file name to `nnn-analysis.{project-name}{.subproject?}.md` to fit the existing analysis file naming convention. An earlier decision to rename the skill was reverted.

## Installation

Personal install (available across all your projects):

```bash
mkdir -p ~/.claude/skills/tech-debt-audit
```

```bash
curl -o ~/.claude/skills/tech-debt-audit/SKILL.md https://raw.githubusercontent.com/ecorkran/tech-debt-audit/main/SKILL.md
```

Or for a project-only install (just this repo):

```bash
mkdir -p .claude/skills/tech-debt-audit && cp /path/to/SKILL.md .claude/skills/tech-debt-audit/SKILL.md
```

Verify it loaded:

```bash
echo "/skills" | claude
```

## Usage

In Claude Code, in the repo you want audited:

```
/tech-debt-audit
```

That's it. Output goes to audit file as specified. First run takes 5–20 minutes depending on repo size; subsequent runs in repeat-run mode are faster.

## Philosophy

Most "code review" prompts produce a bulleted list of generic best-practice violations dressed up as findings. This skill is built to avoid that failure mode. Three design choices do most of the work:

**Forced orientation before judgment.** Phase 1 isn't optional decoration. Without a real mental model of the architecture, every Phase 2 finding is just pattern-matching against generic heuristics. Reading `git log` for churn data is what surfaces the files that *actually* have debt versus the files that just look messy.

**File:line citations on every finding.** This is the single biggest quality lever. A finding without a citation is a vibe. Vibes don't get fixed.

**The "looks bad but is actually fine" section is required.** This is the one most people remove when adapting the prompt. Don't. Forcing the model to surface the calls it considered making and chose not to is what separates a real audit from a checklist regurgitation. If that section is empty, the audit is shallow.

The skill also explicitly forbids recommending rewrites and forbids padding categories. Both are common LLM failure modes — rewriting is easier than diagnosing, and padding makes outputs feel thorough when they aren't.

## What you get

Audit file looks like this in shape:

```
# Tech Debt Audit — <repo name>
Generated: 2026-04-25

## Executive summary
- 3 Critical findings, 12 High, 31 Medium, 18 Low
- Largest debt concentration: src/payments/* (god module, 4 of 3 Critical findings)
- ...

## Architectural mental model
The system is a [...]

## Findings
| ID | Category | File:Line | Severity | Effort | Description | Recommendation |
|----|----------|-----------|----------|--------|-------------|----------------|
| F001 | Architectural decay | src/payments/processor.ts:1240 | Critical | L | 1,400-line god class handling routing, validation, retry, and reconciliation | Extract retry and reconciliation into separate services |
| ... |

## Top 5
1. **F001 — Decompose payments/processor.ts** ...

## Quick wins
- [ ] F042: Remove unused dep `lodash.merge` (replaced by native ...)
- [ ] ...

## Things that look bad but are actually fine
- The deeply nested callback pattern in `src/legacy/webhooks.ts` looks like a refactor target, but it preserves ordering guarantees that the queue-based replacement would break. Leave it.
- ...

## Open questions
- Is `src/experiments/` intentionally untested, or did it fall through?
- ...
```

## Adaptation notes

**Project-level overrides.** A `.claude/skills/tech-debt-audit/SKILL.md` in a specific repo overrides the global one. Useful when a project needs custom dimensions — e.g., an agent codebase might add "prompt injection surface area" or "tool-call cost per turn" as audit categories.

**Mid-audit course correction.** After Phase 1 completes, you can interrupt with: *"Before Phase 2, tell me what surprised you in Phase 1 and what you want to investigate that isn't in the dimensions list."* The best findings often come from things the prompt didn't anticipate. Worth doing on first run for any new codebase.

**Tuning severity calibration.** If the model is over- or under-flagging, edit the Phase 2 dimensions list to add explicit thresholds. Example: change "god files (>500 LOC)" to ">800 LOC" if your codebase has a higher baseline.

**Adding categories.** The 9 dimensions in Phase 2 are a starting point. Add domain-specific ones for your stack — accessibility for frontend, IaC drift for infra, model evals for ML, prompt versioning for LLM apps.

**Splitting into supporting files.** As this SKILL.md grows, you can extract sections into sibling files (`severity-rubric.md`, `stack-tooling.md`) and reference them from the protocol. Claude Code lazy-loads them only when needed.

## Limitations

This is a static audit, not a security audit. It catches obvious security hygiene issues (hardcoded secrets, SQL injection patterns) but won't replace a real pen test or threat model.

It won't catch business-logic bugs. Those require domain knowledge the model doesn't have.

It can't tell intentional simplicity from accidental simplicity. The "open questions" section exists for exactly this reason — when in doubt, the skill asks rather than assuming.

For very large repos (>200k LOC), even subagent dispatch can produce shallow results. Consider scoping to a module: `/tech-debt-audit src/payments`.

## Contributing
PRs welcome. Before submitting:

1. Test against at least two real codebases of different stacks.
2. If you're adding a dimension, include a justification for why it isn't covered by the existing 9.
3. If you're tightening a rule, show a before/after audit excerpt demonstrating the improvement.

The single design constraint: this skill must produce findings that engineers act on. Anything that pushes toward "feels comprehensive but nothing changes" is a regression.

## License
MIT. Use it, fork it, ship it. Attribution appreciated but not required.

## Credits
Built on the Claude Code Agent Skills standard. Inspired by the experience of working with Claude Code on codebases that got really messy over time.
