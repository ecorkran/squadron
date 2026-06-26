---
docType: slice-design
parent: 340-slices.skill-pack-infrastructure.md
initiative: 340
index: 340
project: squadron
dateCreated: 20260625
dateUpdated: 20260625
status: complete
---

# Slice Design: Command Surface Spike — Dispatch vs. Prefix

## Overview

This is a time-boxed spike, not a feature delivery. The open architectural question is: can `/sq:analysis <skill>` (a single dispatcher markdown file) serve as a reliable command surface for skill packs, or must each skill get its own prefix (`/analysis:tech-debt`)?

The answer is empirical. Claude Code receives slash command arguments via `$ARGUMENTS` — the question is whether a dispatcher markdown file can read the first token, route to the right skill's logic, and execute it without losing context, mangling arguments, or producing degraded behavior relative to a direct invocation.

This slice builds the minimal prototype, runs it against two representative skills, documents the observed behavior, and records a decision. The decision updates the arch doc and unblocks slice 341 (manifest + installer).

## Design

### What to Build

**A minimal dispatcher file** at `commands/sq/analysis.md` (temporarily, for testing — not the final location):

```markdown
Route to an analysis skill based on the first argument in $ARGUMENTS.

Parse $ARGUMENTS: the first word is <skill>, the remainder is <skill-args>.

If <skill> is empty, list available skills and stop:
  - tech-debt: analyze technical debt in a project
  - understand: build a deep understanding of a codebase

If <skill> is "tech-debt", execute the tech-debt-analyze skill with <skill-args>.
If <skill> is "understand", execute the understand-anything skill with <skill-args>.
Otherwise, print: Unknown skill "<skill>". Available: tech-debt, understand.
```

**Two stub skill files** to dispatch to — minimal content sufficient to confirm routing worked and arguments arrived intact:
- `commands/sq/analysis-tech-debt.md` — prints "tech-debt invoked with args: $ARGUMENTS"
- `commands/sq/analysis-understand.md` — prints "understand invoked with args: $ARGUMENTS"

These stubs are for spike validation only and are deleted after the decision is recorded.

### What to Observe

Run at minimum:
1. `/sq:analysis tech-debt src/` — verify routing to tech-debt stub, args `src/` intact
2. `/sq:analysis understand src/squadron/` — verify routing to understand stub, args intact
3. `/sq:analysis` (no args) — verify skill listing behavior
4. `/sq:analysis unknown-skill` — verify unknown-skill error message

Record for each invocation:
- Did routing fire correctly?
- Did `<skill-args>` arrive at the stub with correct content?
- Did the dispatcher add any unwanted preamble, intermediate output, or confusion?
- Was the experience meaningfully worse than invoking a direct command?

### Decision Criteria

**Dispatch is reliable (adopt dispatch model)** if:
- Arguments pass through intact in all four test cases
- No context loss or preamble confusion observed
- The user experience is equivalent to a direct invocation

**Dispatch is unreliable (adopt prefix model)** if:
- Arguments are mangled or lost in any case
- Dispatcher produces confusing intermediate output that degrades UX
- Routing fails silently (wrong skill invoked without error)

A marginal result (mostly works, one edge case fails) should be treated as **unreliable** — the dispatch model only has value if it is unconditionally reliable. A single failure mode makes it a footgun.

## Decision Record

Document findings in a one-page decision record appended to this slice design under `## Spike Results` (added after the spike runs). Include:
- The four test cases with observed outcomes
- The verdict: dispatch reliable / unreliable
- Any notable edge cases or caveats

## Arch Doc Update

After the decision is recorded, update `340-arch.skill-pack-infrastructure.md`:
- If **dispatch reliable**: revise the "open dispatch question" principle to state dispatch is adopted; note that the manifest format will support a `dispatch_file` option alongside `prefix`.
- If **dispatch unreliable**: revise to confirm prefix-per-pack; close the open question note.

## Component Interactions

```
~/.claude/commands/sq/analysis.md   (dispatcher — temp location for spike)
~/.claude/commands/sq/analysis-tech-debt.md   (stub skill — spike only)
~/.claude/commands/sq/analysis-understand.md  (stub skill — spike only)
     │
     ▼
Claude Code slash command invocation
     │
     ▼
340-arch.skill-pack-infrastructure.md  (updated with decision)
     │
     ▼
341 slice design  (manifest format inherits the decision)
```

## Success Criteria

1. Dispatcher file and two stub skills are installed and invocable in a Claude Code session.
2. All four test invocations are run and outcomes recorded.
3. A clear dispatch-reliable / dispatch-unreliable verdict is recorded with evidence.
4. Arch doc is updated to reflect the closed decision.
5. Spike files (stubs) are removed from the repo after the decision is recorded.

## Verification Walkthrough

1. Copy `commands/sq/analysis.md` and the two stubs to `~/.claude/commands/sq/` (or run `sq install-commands` after placing them in the repo).
2. Open a Claude Code session in any project.
3. Run `/sq:analysis tech-debt src/` — confirm output mentions "tech-debt invoked with args: src/".
4. Run `/sq:analysis understand src/squadron/` — confirm output mentions "understand invoked with args: src/squadron/".
5. Run `/sq:analysis` — confirm skill listing appears.
6. Run `/sq:analysis bogus` — confirm unknown-skill error.
7. Record all four outcomes in `## Spike Results` below.
8. Update `340-arch.skill-pack-infrastructure.md` with the decision.
9. Remove stub files from `commands/sq/`; confirm `sq install-commands` no longer installs them.

## Dependencies

- [100] — install-commands file-copy pattern (reference implementation)
- Unblocks: [341] (manifest format commits to prefix or dispatch based on this outcome)

## Effort

1/5 — time-boxed spike; no persistent code deliverable.

---

## Spike Results

**Verdict: dispatch reliable**

All four test cases passed. Arguments arrived intact in all routing cases.

| Test | Invocation | Expected | Observed | Pass? |
|------|-----------|----------|----------|-------|
| 1 | `/sq:analysis tech-debt android/` | routes to tech-debt stub; args `android/` intact | "tech-debt skill invoked with args: android/" | ✓ |
| 2 | `/sq:analysis understand android/src` | routes to understand stub; args `android/src` intact | "understand skill invoked with args: android/src" | ✓ |
| 3 | `/sq:analysis` (no args) | skill listing appears | listing rendered correctly (tech-debt, understand) | ✓ |
| 4 | `/sq:analysis fake` | unknown-skill error | "Unknown skill \"fake\". Available: tech-debt, understand." | ✓ |

**Observations:**
- Routing fired correctly in all cases with no intermediate preamble or confusion.
- `<skill-args>` passed through without modification in both routed cases.
- Empty-args listing was clean and unambiguous.
- Unknown-skill error message was clear and actionable.
- User experience is equivalent to a direct invocation.

**Decision:** Adopt the dispatch model. The manifest format (slice 341) will support a `dispatch_file` option alongside `prefix`.
