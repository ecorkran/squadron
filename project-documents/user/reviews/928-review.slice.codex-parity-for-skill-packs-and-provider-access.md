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
aiModel: z-ai/glm-5.3-flash
status: complete
dateCreated: 20260927
dateUpdated: 20260927
reviewedSha: 16194f3e130855cdf673d88c4d65af2ef3f1bb44
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 43
squadronVersion: 0.14.0
findings:
  - id: F001
    severity: concern
    category: under-specification
    summary: "D7's removal extraction states two incompatible properties about destination removal"
    location: "project-documents/user/slices/928-slice.codex-parity-for-skill-packs-and-provider-access.md:75"
  - id: F002
    severity: concern
    category: error-handling
    summary: "D8's \"pack ships no Codex content\" requires source resolution the pure check layer cannot do, with unenumerated failure modes"
    location: "project-documents/user/slices/928-slice.codex-parity-for-skill-packs-and-provider-access.md:140"
  - id: F003
    severity: concern
    category: verification
    summary: "Walkthrough step 7 expects WARN rows on bare `sq doctor`, repeating the exact error slice 925 already corrected"
    location: "project-documents/user/slices/928-slice.codex-parity-for-skill-packs-and-provider-access.md:278-279"
  - id: F004
    severity: concern
    category: alignment
    summary: "Slice invalidates 340-arch's stated skill-pack delivery model but plans no amendment line"
    location: "project-documents/user/slices/928-slice.codex-parity-for-skill-packs-and-provider-access.md:180-190"
  - id: F005
    severity: note
    category: verification
    summary: "`sq model list` fix is described as \"one line each\" but occurs three times per file"
    location: "project-documents/user/slices/928-slice.codex-parity-for-skill-packs-and-provider-access.md:24"
  - id: F006
    severity: note
    category: under-specification
    summary: "D12 hint placement and scope interact with the #126 waiting-rule equality test and the pending daemon probe"
    location: "project-documents/user/slices/928-slice.codex-parity-for-skill-packs-and-provider-access.md:170"
  - id: F007
    severity: pass
    category: alignment
    summary: "Dependency slice 925's interface claims are all verified present in shipped code"
    location: "project-documents/user/slices/928-slice.codex-parity-for-skill-packs-and-provider-access.md:58"
  - id: F008
    severity: pass
    category: alignment
    summary: "D5's receipt-name generalization verifiably preserves every existing name and receipt"
    location: "project-documents/user/slices/928-slice.codex-parity-for-skill-packs-and-provider-access.md:134"
  - id: F009
    severity: pass
    category: alignment
    summary: "Scope, effort, and exclusions align with plan entry 26, including the recorded divergences"
    location: "project-documents/user/slices/928-slice.codex-parity-for-skill-packs-and-provider-access.md:35"
  - id: F010
    severity: pass
    category: error-handling
    summary: "D9/D10 security posture and evidence discipline are handled correctly"
    location: "project-documents/user/slices/928-slice.codex-parity-for-skill-packs-and-provider-access.md:142"
---

# Review: slice — slice 928

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3-flash

## Findings

### [CONCERN] D7's removal extraction states two incompatible properties about destination removal

The component table (line 75) specifies `remove_receipt_files(receipt)` as "never removes the destination itself," but the Data Flow (line 102) says "for a Claude prefix pack the now-empty prefix directory is still removed, as today." These cannot both hold: for a skill-pack prefix install, the receipt's `destination` **is** the prefix directory (installer.py records `commands_dir / prefix` as `InstallReceipt.destination`), and today's `sq skills uninstall` removes exactly that destination when empty (skills.py:120-122, gated on `SurfaceType.PREFIX`). The extraction source (`uninstall_commands`, install.py) never removes its destination because its destination is the commands *root*. The design must state which surface performs the prefix-dir removal — the shared routine keyed on `surface`, or the caller — and how the dispatch_file case (where `sq/` is shared and must *not* be removed) is distinguished. As written, the implementer must guess, and the two guesses produce visibly different `~/.claude/commands/` end states.

### [CONCERN] D8's "pack ships no Codex content" requires source resolution the pure check layer cannot do, with unenumerated failure modes

D8 has `check_skill_packs` report `WARN — pack ships no Codex content` for packs without an `agents/` directory, distinguishing that state from "not installed." Determining "no agents content" requires resolving the pack's *source* — but `installed_path(entry, root)` inspects only the destination. For `github:` sources, resolution means `clone_github` (subprocess + network), and `check_skill_packs`' contract and docstring say "Pure: reads the manifest and the filesystem only. no subprocess, no network" (doctor_checks.py:428, and the module docstring at line 1). For unreachable local sources, `resolve_source` raises `SkillSourceError`, but the design's error convention ("SkillSourceError → exit 1") does not apply inside a doctor check, which must return a WARN row, not exit. The design enumerates none of this: does a github-source pack get probed (new network I/O path with hang/timeout failure modes in a pure layer), silently reported as "not installed," or reported some third way? The distinction D8 promises is exactly the one it does not specify a mechanism for.

### [CONCERN] Walkthrough step 7 expects WARN rows on bare `sq doctor`, repeating the exact error slice 925 already corrected

Step 7 runs bare `sq doctor` and expects "analysis, analysis (codex), demo, demo (codex) — all four rows present," then a bare `sq doctor` showing the `demo (codex)` WARN row. All four rows are WARN-level at that point (nothing is installed for the walkthrough's targets), and `doctor.py:64` hides every WARN row unless `-v` is passed. Slice 925's walkthrough hit this precise mistake, corrected it in place, and recorded the lesson ("the design assumed output rather than running the command"); 925's D9-based rows (installed commands) are OK-level and visible, but skill-pack rows here are all WARN. The walkthrough as written will fail at step 7 for the implementer through no defect in the design's actual behavior — it needs `sq doctor -v`, and the success criterion containing this expectation should be corrected before implementation.

### [CONCERN] Slice invalidates 340-arch's stated skill-pack delivery model but plans no amendment line

The Migration Plan records the moved files, receipt compatibility, and behavior preservation — but no architecture amendments. After this slice, `340-arch.skill-pack-infrastructure.md`'s stated model is partially wrong on two points: "File copy is the delivery primitive — `sq skills install` writes markdown files to `~/.claude/commands/<prefix>/`" (the codex target now writes skill directories to `~/.agents/skills/`), and the pack-source layout section (README's documented format gains a required-for-codex `agents/` tree with validation rules that 340-arch does not describe). Slice 925 set the governing precedent: its integration requirements mandated dated amendment lines to 340-arch and 360-arch when this exact sentence was invalidated. This slice changes the same sentence's subject matter and should carry the same obligation; the skill-pack architecture document is the parent lineage of the surface this slice redefines.

### [NOTE] `sq model list` fix is described as "one line each" but occurs three times per file

The Overview says the typo is "fixed here, one line each"; the string `sq model list` appears at three places in each file (commands/sq/review.md:60,112,158 and commands/agents/sq-review/SKILL.md:82,134,180) — six sites, not two. Trivial as an edit, but the design's own walkthrough and the drift guard both depend on accurate tree descriptions, and the undercount could leave stale occurrences behind if the implementer fixes "one line" per file. The target command `sq models list` was verified to exist (models.py:194, registered at app.py:55).

### [NOTE] D12 hint placement and scope interact with the #126 waiting-rule equality test and the pending daemon probe

Two small unstated constraints. First, the new sandbox-rejection section goes into `sq-review`, `sq-run`, and `sq-pr` SKILL.md — three of the four skills whose `## Waiting on the command` sections must remain byte-identical to each other (the #126 drift test extracts everything from that heading to the next `\n---\n`). The design doesn't pin where the hint section is inserted relative to the waiting rule; an insertion inside that span breaks the equality test loudly (recoverable, but the placement should be specified). Second, `sq-task` is a daemon-client command sitting in the same long-command set, and D10's daemon rows are unprobed — if the probe finds daemon commands need the rule, `sq-task` can hit the same sandbox rejection the hint exists to explain, yet the hint trio excludes it. Worth one sentence either way.

### [PASS] Dependency slice 925's interface claims are all verified present in shipped code

Every prerequisite named in Dependencies exists with the stated semantics: `CommandTarget`/`normalize_target`/`DELIVERIES`/`receipt_name`/`write_skill_dirs`/`bundled_skill_names` in skills/targets.py, and doctor's `_command_targets_to_check` with the Claude-always/agents-only-if-Codex semantics the design assumes (doctor_checks.py:577). The consumption direction is correct — this slice builds on a completed prerequisite and provides `PACK_LAYOUTS`/`remove_receipt_files` forward without inventing upward dependencies.

### [PASS] D5's receipt-name generalization verifiably preserves every existing name and receipt

Checked against the current implementation: `receipt_base` values are `"squadron-commands"` and `"squadron-commands-agents"` (targets.py:167,179), so `base + suffix(""/"-agents") + ("-local")` reproduces today's four `squadron-commands*` names exactly; a pack name as base yields `<pack>.toml` for Claude machine scope, matching what `write_receipt` writes today. The old-receipt-read requirement (criterion 6) is satisfiable with no schema change, as claimed. The blast radius is correctly scoped: callers are install.py:128,233 and the receipt-name tests the design's test list already covers.

### [PASS] Scope, effort, and exclusions align with plan entry 26, including the recorded divergences

The design covers exactly the plan's Part A (target threading through `sq skills`) and Part B (approval rule documentation + command enumeration), answers the plan's designated design question about a doctor check for the rule (D11, with the reasoning the plan asked for), and its D9 divergence from the plan's `default.rules` wording (own `squadron.rules` file) is recorded in the plan entry itself. Effort revision to 3/5 appears in both documents. Exclusions carry forward the plan's (#126, copilot/cursor) and correctly keep `sq setup`'s prints-don't-edit principle for the rule file, consistent with slice 908's constraint.

### [PASS] D9/D10 security posture and evidence discipline are handled correctly

The rule grants unsandboxed execution (network *and* filesystem), and the design mandates stating that in the same paragraph as the snippet, documents the `decision = "prompt"` alternative, and names the non-matching command shapes (redirection, env-var prefixes, globs). D10's subcommand enumeration is probe-based rather than code-read, with an honest table distinguishing confirmed rows from "confirm by probe" rows and recording where results land (DEVLOG) — the design does not present unverified evidence as verified, and the README consequence for daemon commands is handled conditionally in the same decision.

### Run Digest

- Response length: 11041 chars
- Response is newline-free: no
- Tool calls made: 43
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 128000 tokens
- Reasoning characters: 40077
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
