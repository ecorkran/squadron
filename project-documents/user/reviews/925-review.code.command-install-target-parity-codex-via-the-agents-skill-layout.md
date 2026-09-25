---
docType: review
layer: project
reviewType: code
slice: command-install-target-parity-codex-via-the-agents-skill-layout
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/925-slice.command-install-target-parity-codex-via-the-agents-skill-layout.md
aiModel: moonshotai/kimi-k2.7-code
status: complete
dateCreated: 20260925
dateUpdated: 20260925
reviewedSha: 3f23bc51cd786d5b312d42b88631fab083ca49b3
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 0
findings:
  - id: F001
    severity: pass
    category: design
    summary: "Clean target-delivery abstraction"
    location: "src/squadron/skills/targets.py"
  - id: F002
    severity: pass
    category: testing
    summary: "Drift guards keep Claude and agents trees in sync"
    location: "tests/cli/test_install_commands.py:440-620"
  - id: F003
    severity: pass
    category: error-handling
    summary: "`typer.Exit` is caught and converted to an outcome"
    location: "src/squadron/cli/commands/setup_install.py:167-190"
  - id: F004
    severity: concern
    category: portability
    summary: "Agent-layout receipt paths use OS-native separators"
    location: "src/squadron/skills/targets.py:113"
  - id: F005
    severity: pass
    category: correctness
    summary: "Machine/local receipt scopes do not collide"
    location: "src/squadron/skills/targets.py:188"
---

# Review: code — slice 925

**Verdict:** CONCERNS
**Model:** moonshotai/kimi-k2.7-code

## Findings

### [PASS] Clean target-delivery abstraction

The new `CommandTarget` enum, `TargetDelivery` dataclass, and `DELIVERIES` table centralize every per-runtime difference (roots, layouts, receipt names, check names). This is a strong application of OCP: adding a new target later requires only a new enum member and a delivery entry, not scattered conditionals in the installer or doctor check.

### [PASS] Drift guards keep Claude and agents trees in sync

The bijection tests (`test_every_claude_command_has_an_agents_twin`, `test_every_agents_skill_has_a_claude_twin`) plus frontmatter, naming, and policy checks make silently divergent command sets fail loudly. These tests directly address the risk that separately-authored trees drift.

### [PASS] `typer.Exit` is caught and converted to an outcome

The installer now catches `typer.Exit` explicitly (it subclasses `RuntimeError`, not `SystemExit`) while still handling genuine `SystemExit`. This preserves the module's documented contract that a failed install returns an `InstallOutcome` instead of escaping.

### [CONCERN] Agent-layout receipt paths use OS-native separators

`write_skill_dirs` serializes receipt entries with `str(Path(skill_dir.name) / original.relative_to(skill_dir))`, which produces backslashes on Windows. Receipts written on Windows would contain `sq-review\SKILL.md`; the same receipt read on Unix would treat that as a single filename, and tests like `test_agents_install_lists_what_it_wrote` would fail on Windows. The Claude layout already uses forward-slash literals (`f"{source.name}/{md_file.name}"`); the agents layout should use `.as_posix()` for the same portability.

### [PASS] Machine/local receipt scopes do not collide

`receipt_name` produces four distinct keys for the two targets times two scopes, preventing a local install from overwriting a machine receipt and vice versa. The test `test_claude_machine_receipt_name_is_unchanged` also guards backward compatibility with receipts written since issue #65.

### Run Digest

- Response length: 2381 chars
- Response is newline-free: no
- Tool calls made: 0
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 58033
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5
