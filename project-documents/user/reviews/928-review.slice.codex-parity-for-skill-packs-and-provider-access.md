---
docType: review
layer: project
reviewType: slice
slice: codex-parity-for-skill-packs-and-provider-access
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/928-slice.codex-parity-for-skill-packs-and-provider-access.md
aiModel: claude-opus-5-5
status: complete
dateCreated: 20260927
dateUpdated: 20260927
reviewedSha: 44dbc267e62e4827bb7d036233673be8297bfd12
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 7
squadronVersion: 0.14.0
findings:
  - id: F001
    severity: pass
    category: scope
    summary: "Belongs in the maintenance initiative"
    location: "project-documents/user/slices/928-slice.codex-parity-for-skill-packs-and-provider-access.md#overview"
  - id: F002
    severity: note
    category: scope
    summary: "Bigger than 900's \"small and focused\" guideline"
    location: "project-documents/user/slices/928-slice.codex-parity-for-skill-packs-and-provider-access.md:310"
  - id: F003
    severity: pass
    category: architecture
    summary: "Dependencies point the right way; no string dispatch"
    location: "project-documents/user/slices/928-slice.codex-parity-for-skill-packs-and-provider-access.md#component-structure"
  - id: F004
    severity: concern
    category: hidden-dependency
    summary: "D8 needs source content that doctor can't read for GitHub packs"
    location: "project-documents/user/slices/928-slice.codex-parity-for-skill-packs-and-provider-access.md:140"
  - id: F005
    severity: concern
    category: integration
    summary: "D5 suffixes let two packs share a receipt file, and `write_receipt` isn't in the component table"
    location: "project-documents/user/slices/928-slice.codex-parity-for-skill-packs-and-provider-access.md:134"
  - id: F006
    severity: concern
    category: error-handling
    summary: "Agents install can overwrite skill directories it doesn't own"
    location: "project-documents/user/slices/928-slice.codex-parity-for-skill-packs-and-provider-access.md:123-130"
  - id: F007
    severity: concern
    category: security
    summary: "The allow rule may approve `sq skills install` with no prompt"
    location: "project-documents/user/slices/928-slice.codex-parity-for-skill-packs-and-provider-access.md:162"
  - id: F008
    severity: note
    category: under-specification
    summary: "Rule contents are decided at implementation time"
    location: "project-documents/user/slices/928-slice.codex-parity-for-skill-packs-and-provider-access.md:155-166"
  - id: F009
    severity: pass
    category: error-handling
    summary: "Failure modes for the new install path are explicit"
    location: "project-documents/user/slices/928-slice.codex-parity-for-skill-packs-and-provider-access.md:93-97"
  - id: F010
    severity: pass
    category: nfr
    summary: "No NFRs to restate"
    location: "project-documents/user/architecture/900-arch.maintenance-and-refactoring.md"
---

# Review: slice — slice 928

**Verdict:** CONCERNS
**Model:** claude-opus-5-5

## Findings

### [PASS] Belongs in the maintenance initiative

This is parity and bug-fix work that 925 left behind. The typo fix (`sq model list` → `sq models list`) is the kind of cleanup 900's scope explicitly covers. The exclusions are explicit and each has a reason: no auto-conversion (D2), no doctor check for the rule (D11), and #126, copilot and cursor stay out.

### [NOTE] Bigger than 900's "small and focused" guideline

The slice raised its own effort to 3/5 and has two parts. Part A (install layout) and Part B (docs, rule, hints) share no code, and each could ship on its own. The slice plan bundled them deliberately, so this doesn't block anything. If implementation stalls, Part B is the obvious split point.

### [PASS] Dependencies point the right way; no string dispatch

- `pack_layouts.py` lives in `skills/`. The CLI and doctor read from it, and nothing in `skills/` imports CLI code.
- `PACK_LAYOUTS` is keyed by `CommandTarget` and checked exhaustively at import, the same way `DELIVERIES` is.
- D6 removes the install-path logic that `skills.py:156-164` and `doctor_checks.py:453-459` each compute separately today.
- D7 moves the containment-checked removal loop into one place and drops the flat `unlink` loop at `skills.py:112-116`, which leaves empty directories behind.

### [CONCERN] D8 needs source content that doctor can't read for GitHub packs

D8 has doctor print `WARN — pack ships no Codex content` for packs with no `agents/` directory. The only way to know that is to look at the pack's source. `check_skill_packs` is documented as "Pure: reads the manifest and the filesystem only", and for a `github:` source the content is only reachable through `clone_github`, which does a network `git clone`.

The design doesn't say which of these doctor does for a GitHub pack:
- clone it (network I/O inside doctor, plus hang and timeout handling),
- skip the check,
- or report "unknown".

Walkthrough step 7 only uses a local `/tmp` source, so it never hits this case. Fix: resolve only bundled and local sources. For a GitHub pack with no install, report plain "not installed (codex)" with no content claim, and say so in D8.

### [CONCERN] D5 suffixes let two packs share a receipt file, and `write_receipt` isn't in the component table

Receipt names are built as `base + "-agents" + "-local"`, so two different pack/target combinations can produce the same name. A Claude install of a pack named `foo-agents` gets `foo-agents.toml`, and so does a Codex install of pack `foo`. Installing one overwrites the other's receipt. Uninstalling then deletes files listed by the wrong pack. The "Excluded" section only rules out collisions with squadron's own names; this pack-vs-pack collision is new in this slice.

The component table also leaves out a signature change the design depends on. `receipts.py:write_receipt` and `read_receipt` build the file name from `pack_name` (`receipts_dir/<pack_name>.toml`). D5 needs that name to come from `receipt_name(...)`. Either those two functions take the receipt name as a parameter, or `InstallReceipt.pack_name` quietly starts holding `mypack-agents`. The second contradicts "Schema unchanged" at line 113.

Fix, pick one:
- reject pack names ending in `-agents` or `-local` at manifest load, or
- on read, check the receipt's recorded pack name and target against the request, and fail if they don't match.

Then add the `write_receipt`/`read_receipt` change to the component table.

### [CONCERN] Agents install can overwrite skill directories it doesn't own

D3 says `~/.agents/skills` is shared with every other skill source. But D3 only validates the source tree. `write_skill_dirs` copies with `copytree(..., dirs_exist_ok=True)`, which merges into an existing directory and silently overwrites a same-named `SKILL.md` that belongs to another tool or to the user. The receipt then lists that file, and `skills uninstall` deletes it. That is the #65 ownership failure again, which the "Patterns" section says receipts are there to prevent.

A second case exists inside squadron itself. With D4, `install-commands --ide codex` and `skills install analysis --ide codex` write the same `analysis-*` directories under two different receipts. Uninstalling either one removes files the other still claims.

Fix: before writing, check that no destination skill directory exists unless it is already listed in this pack's own receipt. If one does, exit 1 with its path, the same way D3 does. At minimum, acknowledge the two-receipts case in the Excluded section, because D4 makes it structural rather than accidental.

### [CONCERN] The allow rule may approve `sq skills install` with no prompt

The D10 table marks `sq skills install` (GitHub source) as "yes — confirm by probe", which puts it in the `allow` rule if the probe agrees. That lets the Codex model clone any repo and write skills into `~/.agents/skills`, which Codex loads on its next start, all outside the sandbox and without asking. That is different in kind from "call a model provider": it lets the model install new instructions for itself. D9's justification text ("commands that call a model provider or GitHub") hides this.

Fix: keep `sq skills` out of the `allow` alternatives. Either document a separate `decision = "prompt"` rule for it or leave it to per-call approval, and state that choice in D10.

### [NOTE] Rule contents are decided at implementation time

Several D10 rows are still "probe", so the exact rule text doesn't exist yet. The design does pin down the method (run under `codex sandbox` from a real terminal, with `sq serve` running for the daemon commands), where results get recorded (DEVLOG), and a check to verify the result (criterion 8). That's acceptable for a docs deliverable.

### [PASS] Failure modes for the new install path are explicit

A missing `agents/` directory, bad skill names, and bad frontmatter are all collected and reported together, and nothing is written unless every check passes. Exit codes and messages are specified, and the walkthrough exercises each case. For `uninstall`, a `--commands-dir` that doesn't match the receipt fails with nothing removed (line 194). The GitHub clone path is unchanged from today.

### [PASS] No NFRs to restate

The 900 architecture document states no latency or throughput targets, so there is nothing this slice needed to carry over.

### Run Digest

- Response length: 8314 chars
- Response is newline-free: no
- Tool calls made: 7
- Tool calls failed: 0
- Stop reason: end_turn
- Reasoning characters: 0
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
