---
docType: review
layer: project
reviewType: slice
slice: command-install-target-parity-codex-via-the-agents-skill-layout
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/925-slice.command-install-target-parity-codex-via-the-agents-skill-layout.md
aiModel: z-ai/glm-5.3
status: complete
dateCreated: 20260921
dateUpdated: 20260921
reviewedSha: 63115e007ff31c09a679a6c6dea7cc47ce48b0ce
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 36
findings:
  - id: F001
    severity: concern
    category: integration-points
    summary: "Bundle move breaks the skills resolver and the metrology audit harness; the Migration Plan's consumer list is incomplete"
    location: "project-documents/user/slices/925-slice.command-install-target-parity-codex-via-the-agents-skill-layout.md:125-127"
  - id: F002
    severity: concern
    category: under-specification
    summary: "`sq setup --ide` threading is under-specified; the component list omits `setup_steps.py`, where the check contract is consumed"
    location: "project-documents/user/slices/925-slice.command-install-target-parity-codex-via-the-agents-skill-layout.md:63-77"
  - id: F003
    severity: note
    category: api-contract
    summary: "`--target` has asymmetric install/uninstall semantics, and D6 leaves the failed check's disposition unstated"
    location: "project-documents/user/slices/925-slice.command-install-target-parity-codex-via-the-agents-skill-layout.md:129-135"
  - id: F004
    severity: note
    category: documentation
    summary: "Sibling architecture documents state the contracts this slice changes, with no amendment recorded"
    location: "project-documents/user/slices/925-slice.command-install-target-parity-codex-via-the-agents-skill-layout.md:123-127"
  - id: F005
    severity: pass
    category: state-management
    summary: "Per-target receipt naming preserves back-compat without a schema change (D5)"
    location: "project-documents/user/slices/925-slice.command-install-target-parity-codex-via-the-agents-skill-layout.md:107"
  - id: F006
    severity: pass
    category: integration-points
    summary: "The `check_slash_commands` return-type change is compatible with doctor's dispatcher"
    location: "project-documents/user/slices/925-slice.command-install-target-parity-codex-via-the-agents-skill-layout.md:68"
  - id: F007
    severity: pass
    category: architecture-alignment
    summary: "D2's divergence from the plan's Part B root is justified and recorded on both sides"
    location: "project-documents/user/slices/925-slice.command-install-target-parity-codex-via-the-agents-skill-layout.md:101"
  - id: F008
    severity: pass
    category: testing
    summary: "Checkable premises hold against the tree, and the verification plan is appropriately hostile"
    location: "project-documents/user/slices/925-slice.command-install-target-parity-codex-via-the-agents-skill-layout.md:179-183"
---

# Review: slice — slice 0

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3

## Findings

### [CONCERN] Bundle move breaks the skills resolver and the metrology audit harness; the Migration Plan's consumer list is incomplete

The Migration Plan names `tests/cli/test_install_commands.py` as the consumers needing path updates and asserts "`_get_commands_source()` unchanged; callers append `delivery.bundle_subdir`." But `_get_commands_source()` is not the only resolver of the commands tree. Verified consumers of the moved `commands/analysis/` directory:

- `src/squadron/skills/resolver.py:73` — `_resolve_bundled(pack_name)` resolves `importlib.resources.files("squadron") / "commands" / pack_name`. The shipped default manifest (`src/squadron/data/skills.toml`) declares `[packs.analysis] source = "bundled"`, so `sq skills install analysis` resolves `squadron/commands/analysis/`, which no longer exists after the move. Both the wheel path and the editable fallback (resolver.py:86) miss, raising `SkillSourceError`.
- `src/squadron/metrology/audit.py:122` — `resolve_audit_skill()` calls `_resolve_bundled(_AUDIT_PACK)` with `_AUDIT_PACK = "analysis"` (line 53). `sq metrology audit run` (initiative 320/323) fails with `AuditSkillError`.
- `tests/metrology/test_audit_skill_sync.py:41` and `tests/skills/test_installer.py` (`TestBundledAnalysisPack`) — the CI fork-sync guard and the bundled-pack install tests both resolve the real pack.

All failures are loud (explicit errors, not silent degradation), but two production commands regress and CI fails, and the Out of scope framing ("`sq skills install` targets … it consumes `CommandTarget` but is its own change") conflates *target selection* — correctly deferred — with *source resolution*, which this slice breaks today. The design must either thread the delivery subdir through `_resolve_bundled`/the `bundled` source or keep the analysis pack's resolution stable, and amend the consumer list, before task breakdown.

### [CONCERN] `sq setup --ide` threading is under-specified; the component list omits `setup_steps.py`, where the check contract is consumed

The component structure lists `setup.py MOD --ide, forwarded` and `setup_install.py MOD _install_sq_commands(target)`, but the check→step conversion layer is unmentioned and is where the change actually lands:

- `setup_steps.py` wires `_RECHECK_MAP["slash commands"] = check_slash_commands` under the type `Callable[[], CheckResult]` (`SetupStep.recheck`). The design's `check_slash_commands -> list[CheckResult]` (slice line 68) breaks that contract — `setup.py`'s interactive loop reads `result.status` off the recheck result. Either the recheck stays single-result (the existing precedent being `check_skill_packs`, which returns a list and is simply absent from the map) or the step machinery changes; the design says neither.
- The new check name `codex skills` has no entries in the five name-keyed dictionaries (`_RECHECK_MAP`, `DOCS_ANCHOR`, `_EXPLANATION`, `_TITLE_MAP`, `_INSTALLERS`) — acceptable if deliberate, but that should be stated.
- `run_all_checks(git_hooks_path=...)` takes no target parameter. Without one, `sq setup --ide codex` still emits the Claude `slash commands` row, classifies it INSTALL, and offers it for in-process install via `_INSTALLERS["slash commands"]` — installing Claude commands on a run whose own success criterion (line 176) says it "installs the agents commands in place of the Claude ones." The final `run_all_checks` summary inside `_run_interactive` is likewise unscoped.

One sentence naming where `--ide` lands (a `run_all_checks` parameter, or a post-filter in `build_steps`) and what happens to the Claude row under a non-Claude `--ide` closes this.

### [NOTE] `--target` has asymmetric install/uninstall semantics, and D6 leaves the failed check's disposition unstated

Scope item 3 and the API Contracts block present `--target DIR` uniformly as the override that beats both, while D6 (line 109) redefines it on uninstall as "a check ('receipt says X, you said Y') rather than a source of paths." The design never says what a failed check does — hard error, warning, or proceed-from-receipt. Under the project's no-silent-fallback rule that disposition should be stated explicitly, since "a check that silently proceeds" is exactly the shape the conventions reject. The D6 direction itself (receipt destination is the truth about where files went) is correct and the walkthrough step 5 exercises it.

### [NOTE] Sibling architecture documents state the contracts this slice changes, with no amendment recorded

`340-arch.skill-pack-infrastructure.md` states "`sq install-commands` copies `commands/sq/*.md` from the wheel into `~/.claude/commands/sq/`. This is the only install path" and "the analysis pack ships as `commands/analysis/` in the wheel, parallel to `commands/sq/`"; `360-arch.document-intelligence.md` cites the same wholesale-copy behavior. Both become false after the restructure. The house pattern (e.g. 320-arch's boundary correction recorded from slice 323's design) is to record such amendments in the affected architecture doc. The design already files two cross-repo issues as integration requirements; an in-repo amendment note for 340 belongs alongside them.

### [PASS] Per-target receipt naming preserves back-compat without a schema change (D5)

Verified against `src/squadron/skills/receipts.py`: the receipt file is keyed solely by `pack_name` (`read_receipt`/`write_receipt` address `receipts_dir / f"{pack_name}.toml"`), and `InstallReceipt` carries no target or scope field — so suffixing the name expresses exactly the dimension the filename already can, and keeping `squadron-commands` for the Claude machine install means every receipt written since #65 still reads and still governs stale removal. The rejected alternative (new fields) would indeed force a read-compat path for old receipts. The four-name scheme in State Management is consistent with this and with receipt-destination isolation per scope.

### [PASS] The `check_slash_commands` return-type change is compatible with doctor's dispatcher

`run_all_checks`'s `_run` helper already extends Sequence outputs (`isinstance(output, collections.abc.Sequence) and not isinstance(output, CheckResult)`), so a list return needs no dispatcher change on the doctor side — `check_skill_packs` is the existing list-returning precedent. Gating the agents row on `check_codex_cli()` also stays within the pure-check layer's constraints (`shutil.which` is a PATH scan, not a subprocess, and `check_codex_cli` already lives there). The setup-side consumer of the same function is a separate matter, covered by the concern above.

### [PASS] D2's divergence from the plan's Part B root is justified and recorded on both sides

The plan's entry 23 Part B specified `~/.codex/skills`; the design corrects it to `~/.agents/skills`, citing Codex's own source marking the former deprecated, and the plan's closing note was updated to record the design's resolution. Filing a `cf` issue is an explicit integration requirement. The divergence also does not silently strand existing installs: the design's risk section names the deprecated/current dual-root situation and its consequence for users who ran `cf install-commands --ide codex`.

### [PASS] Checkable premises hold against the tree, and the verification plan is appropriately hostile

Verified: exactly the two `commands/analysis/` files carry `disable-model-invocation: true` (D7's mapping scope is stated correctly); no file under `commands/` uses `` !`cmd` `` output injection (D3's "no passthrough rewrite needed" premise); the moved file count is 10 `sq/` + 2 `analysis/` = 12, matching the walkthrough's "Installed 12 command(s)". The unchanged-Claude-default test (pre/post-slice install into `tmp_path`, identical file sets and receipt contents), the extension of `test_no_test_touches_the_real_receipts_directory` to the new root, and stubbed `shutil.which` per #47 all align with the machine-state isolation work in slice 923 — the slice anticipates the isolation discipline rather than contradicting it.

## Response (20260922)

All four findings verified against the tree and accepted. Design revised in place (`dateUpdated` 20260922); `validate-slice-design` PASS.

- **F001 — accepted, resolved by dropping the move.** `_resolve_bundled` (`skills/resolver.py:73`) and `metrology/audit.py:122` do resolve `commands/analysis/` by pack name; the shipped `skills.toml` declares `source = "bundled"`. New **D8**: `commands/sq/` and `commands/analysis/` stay put, `commands/agents/` is a sibling, and each `TargetDelivery` names its bundle subdirectories explicitly (Claude: `("sq", "analysis")`) so the Claude install stops walking every directory under `commands/`. Migration Plan rewritten; consumer list is now the one behavioral change in `install.py`. Walkthrough step 9 exercises `sq skills install analysis` and the skills/metrology suites.
- **F002 — accepted.** New **D9**: `check_commands_installed(target) -> CheckResult` (single result, name from the delivery); `run_all_checks(ide: CommandTarget | None)` — `None` for doctor (Claude row always, agents row when `check_codex_cli()` is OK), a target for setup (that row only, so `--ide codex` never offers the Claude install). Both setup passes take the flag. The five name-keyed tables in `setup_steps.py` gain `codex skills` entries; `setup_steps.py` added to the component list. The tables keying on user-visible names is noted as a pre-existing smell, not changed here.
- **F003 — accepted.** D6 now states the disposition: `--target` on uninstall that differs from `receipt.destination` exits 1 with both paths and removes nothing; without `--target` the receipt's destination is used. API Contracts updated.
- **F004 — accepted.** With D8, every `commands/sq/` / `commands/analysis/` statement in 340 and 360 stays true. The two that do not — 340 "only install path" and 360 "adding a file is its registration" — carry dated amendment lines as of this response.

Observation, not a finding: this review's heading reads "slice 0". That is the bug fixed in `11894797` (unreleased); the review ran under the installed 0.13.0.

### Run Digest

- Response length: 10740 chars
- Response is newline-free: no
- Tool calls made: 36
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 73832
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
