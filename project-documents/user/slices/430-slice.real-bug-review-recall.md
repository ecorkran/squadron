---
docType: slice-design
slice: real-bug-review-recall
project: squadron
parent: user/architecture/420-slices.model-benchmark.md
dependencies: [420, 421, 424, 425, 402]
interfaces: [432, 433]
dateCreated: 20261115
dateUpdated: 20261118
status: complete
---

# Slice Design: real-bug-review-recall

## Overview

The hand-run code-review benchmark (`user/reference/review-recall-runbook.md`, results in `user/reference/review-recall-results/`) becomes a command group, `sq benchmark recall`. A case is a real merged diff (repo, base, head) with the bugs that a later fix commit or issue proved real. A reviewer config is a **recipe**: one or more reviewers (fan-out) or a pool of reviewers, then zero or more comb stages that mark each finding KEEP or DROP. Every stage output is stored once per case and run. A recipe is scored from stored outputs wherever no new call is needed, so one reviewer run serves every recipe that includes it.

The hand-run data holds:
- 17 cases and 21 known bugs.
- 696 distinct review outputs, with 3,619 findings between them. `find <dir> -maxdepth 1 -name '*.json'` over `20261112-grid1/` (27), `20261112-grid2/` (210) and `20261113-grid3/` (486) gives 723 files, but all 27 grid1 files are byte-identical copies of same-named grid2 files, so the import skips them (D10). The `judge/` and `precision/` subfolders are not review outputs.
- 480 comb outputs.
- Four agent grading passes.

It is imported as records, and the report reproduces the hand-run tables from those records with no new calls. Later measurements add records rather than new scripts.

## Value

- **User-facing.** The command answers "which code review setup, and is a replacement better or worse" on the same cases each time, with an interval that says when a difference is noise. Today that means rerunning `comb.py`, `score.py` and `report.py` by hand, and they disagree on folders and ids.
- **Cheap comparison.** Stage outputs are reused across recipes. Adding a comb to a recipe costs one comb call per stored review, not a new review grid.
- **Downstream.** The winning recipe becomes the pipeline review step's configuration (a PM decision informed by the report, not something the code reads). 432 reuses the case, recipe and report machinery for documents, and 433 reads the report.

## Technical Scope

Included:
- Case records for real-bug cases (kind `code`), with a committed case-file format, plus versioned case sets. A case-kind seam for 432 (D14).
- Recipe files.
- Run records: one per case and run, holding every reviewer's review and combs.
- Label records: known-bug hit labels and finding grades, from the imported grading passes and from people. One record per case and labeler.
- The hit rule: a mechanical location gate plus stored labels (D3).
- `sq benchmark recall` subcommands: `cases add`, `cases list`, `import`, `run`, `label`, `report`, plus a hidden `_stage` command that the runner launches.
- A built-in `comb` review template with `output: decisions`, plus a lenient decisions parser.
- Stage calls run as subprocesses under 421's scrubbed environment, after 421's auth check, and each is checked with 424's transcript leak scan (D6).
- The import of the hand-run results (grids 1–3, comb outputs, the four grading passes).
- The recipe file and walkthrough step for the first live recipe (D11).

Excluded:
- Live agent grading of new findings (`grade`, a `recall-grade` template, agent label records). It is deferred to [#340](https://github.com/ecorkran/squadron/issues/340). Graded-real share comes from the imported passes, and live entries show as ungraded.
- Document cases (design and task reviews). Those are 432's; this slice only provides the kind seam.
- Outside tools (Greptile and similar). Pushing a PR anywhere is a PM-approved outward action; the runbook's manual method stands.
- Automatic matching of findings to bugs by a model. The runbook rule is that no model grades hits.
- Issue clustering (grouping findings across runs into distinct issues). Finding counts are raw sums.
- Controls (findings the case's own saved review reported that are not case bugs). They stay in the markdown and are not scored.
- Concurrent stage calls. Calls run one after another, as the architecture's non-goal requires; concurrency is [#146](https://github.com/ecorkran/squadron/issues/146).
- Batch-API dispatch.
- Any change to the replay stack (421–426), and any change to `sq review code`.

## Dependencies

### Prerequisites
- **420 (complete):** `effort_sent` on usage records.
- **421 (complete):**
  - `HistoryFreeSandbox` (`replay/history_free_sandbox.py`), used unchanged.
  - `ScrubbedEnvironment` and `CredentialGrant` (`benchmark/scrubbed_env.py`).
  - `run_auth_check` (`benchmark/auth_check.py`).
  - `resolve_sq_path()` (`benchmark/production_deps.py`).
  - `BenchmarkRecordStore`, with its `MetrologyRecord` sibling-payload pattern and `ContentSidecars` (the `REVIEWS` kind).
- **424 (complete):**
  - `leak_scan.scan`, `transcript_source_for(profile)` and `build_leak_rules`.
  - The `leak_rule_source` helpers `installed_package_location` and `uv_cache_dir`.
  - The benchmark process lock (`BenchmarkLock`), which takes over a lock whose owner is gone.
- **425 (complete):** `ReviewBudget` (`benchmark/grade_budget.py`), the `render_bound` pattern (`grade_plan.py`), `EXIT_CAP_REACHED = 2` (`cli/commands/benchmark_grade.py`), `ReviewerRef` (`metrology/grade_models.py`), resume by deterministic record id, and `paired_stats` (`compare_pair`, `pair_seed`).
- **402 (complete):** normalized finding categories (`map_historical_category`) and the `CodeReviewFinding` vocabulary.
- The source repos named by each case must be readable at the recorded path. A missing repo is a harness failure (D8), not an error that stops the run.

### Interfaces Required
- `sq review code --diff <base> --model <alias> --no-save --output file --output-path <file>`, the production command, run unchanged.
- `run_review_with_profile` (`review/review_client.py`), which `_stage` calls for the comb template.
- `TemplateOutput.DECISIONS` (`review/templates/__init__.py`), which already disables the review recovery turn.
- `template_content_hash` (`metrology/identity.py`) for the prompt identity of live stages.
- Config keys:
  - `benchmark.review_timeout_s` (existing, unset by default; `run` refuses without it, as 425 does)
  - `benchmark.auth_probe_timeout_s` (existing)
  - `benchmark.recall_fetch_timeout_s` (new, with its default in the config defaults table)

## Architecture

### Component Structure

New package `src/squadron/benchmark/recall/`, kept apart from the replay modules:

| Module | Responsibility |
|---|---|
| `case_models.py` | The case-file loader and validator (`load_case_file`, `derive_locations`). The case payloads live in `metrology/recall_case_models.py` |
| `kinds.py` | The `RecallKind` protocol and registry (D14); `CodeKind`, the only implementation here |
| `recipe.py` | `Recipe` model, recipe-file loader, expanding a recipe into the stage keys it needs |
| `stage_identity.py` | Live stage identity from the alias registry (`live_stage_config`) and `LiveStageResolver`, the live `StageIdentityResolver` |
| `recall_store.py` | Read and write for the four record types, deterministic ids |
| `review_sandbox.py` | Wraps `HistoryFreeSandbox` and fetches the ancestry back to `base` (D7) |
| `stage_runner.py` | One stage call: scrubbed subprocess in the sandbox, giving a `StageEntry` (D6) |
| `leak_check.py` | The `LeakChecker` used by `stage_runner`: transcript leak scan or `confined` (D6) |
| `run_loop.py` | Serial dispatch of pending stages: sandboxes, caps, resume, orphan ingest, retry (D8, D9) |
| `hit_rule.py` | Location gate and label resolution (D3) |
| `decisions.py` | Lenient parser for `<finding-id>: <WORD> — reason` lines |
| `run_plan.py` | Missing stages for (recipe, case set, runs), auth preflight, bound and refusal checks |
| `scoring_select.py` | Entry selection: the `StageIdentityResolver` protocol, `ImportOnlyResolver`, matching reviews and comb chains. Pure |
| `scoring.py` | Recipe outputs per (case, run): comb chains, fan-out and pool composition, rows per stage identity. Pure: no I/O |
| `scoring_pair.py` | One (case, run) scored: bug hits in both bounds, matched nothing, grades. Pure |
| `scoring_metrics.py` | Per-row metrics, recall bounds, real share. Pure |
| `scoring_paired.py` | Paired intervals per recipe pair (D12). Pure |
| `report_build.py` | Reads the store and assembles the report data |
| `report_render.py` | Text rendering |
| `report_json.py` | The `--json` document (the schema 433 reads) |
| `label_precedence.py` | One effective label and grade per finding (D3 precedence) |
| `hand_run_import.py` | Reads the hand-run folders and writes run and label records |

Record payloads live beside the other metrology payloads, because `MetrologyRecord` (`metrology/models.py`) imports every payload from `metrology/*_models.py` and never imports `benchmark/`:
- `metrology/recall_case_models.py`: `RealBugCase`, `KnownBug`, `BugLocation`, `RecallCaseSet`
- `metrology/recall_run_models.py`: `RecallRun`, `StageEntry`, `RecallFinding`, `StageConfig`, `CombDecision`, `StageUsage`, and the enums `StageKind`, `CombVerdict`, `StageOutcome`, `RecallLeakVerdict`
- `metrology/recall_label_models.py`: `RecallLabels`, `HitVerdict`, `FindingGrade`, `LabelerKind`

CLI: `cli/commands/benchmark_recall.py` (a Typer subgroup registered on `sq benchmark`), split further if it passes about 300 lines. Every collaborator (store, sandbox factory, process runner, clock) is injected through a services factory, as in `benchmark_grade.py`.

Template: `data/templates/comb.yaml` (the hand-run `comb.yaml` prompt, unchanged, with `output: decisions`).

### Data Flow

```
case files (YAML) ──cases add──▶ RealBugCase + RecallCaseSet records
hand-run folders ──import──▶ RecallRun (reviews + combs) + RecallLabels (one per grading pass)

recipe file + case set + runs
   └─run─▶ run_plan: expand recipe → stage keys → drop keys already stored
            → auth check per profile → print bound → per missing stage, one at a time:
               review_sandbox(head, ancestry to base) ─▶ stage_runner
                 scrubbed subprocess, cwd = sandbox, `sq` from resolve_sq_path():
                   review: kind's review command (code: <sq> review code --diff base --model alias)
                   comb:   <sq> benchmark recall _stage (comb template, upstream findings)
                 → leak scan of the subprocess's transcript ─▶ StageEntry in the case run's RecallRun
            → ReviewBudget and plan-call checks between calls → exit 0 / 2

label ─▶ lists undecided hit candidates
        → person records HIT / ADJACENT / MISS → person RecallLabels for the case

report ─▶ scoring(recipes, runs, labels, set version) → tables + recall bounds + paired intervals
```

### State Management

All state lives in the metrology store as four record types, plus raw output in the `REVIEWS` sidecar. Nothing is held between commands. Resume works because every run record id and stage key is deterministic: a rerun computes the same keys and skips the stage entries that exist. Sandboxes, scrubbed homes and stage output files live under 421's benchmark root and are swept by `sweep_benchmark_orphans`.

## Technical Decisions

### D1 — Cases are committed YAML files, loaded into records
Status: decided
- Each case is one YAML file under `user/reference/review-recall-cases/` (for example `trading-data-921.yaml`). `cases add <file|dir> --set <name>` validates the files and writes `RealBugCase` records, then writes a new version of the named case set. The 17 cases in `review-recall-cases.md` are written as YAML once, during this slice. The markdown stays as the narrative record, and the YAML is the input.
- **Bug locations come from history.** At `cases add`, each bug's locations are every file its proof commit(s) changed (`git show --name-only` in the source repo), with no filtering. A file the fix did not change but a finding may rightly cite goes in `extra_locations`, each with a `reason`. For example, 307 B1's graded hits cite `cutover_304_first_purchase.py`; whether that file is in the fix commit is read, not assumed. The resolved list is frozen into the record. This keeps the ground truth tied to the fix commit, as the architecture requires, and every hand addition is visible with its reason. Reading squadron's own commits for this is D13.
- **Case id** is content-derived: `rbcase-<sha12>` of canonical JSON of (kind, repo name, base, head, host repo, bugs with their resolved locations). Any change gives a new case id, and the old case stays readable. `name` (for example `trading-data-921`) is for display and lookup only.
- **Which bugs count.** These follow the case file's own totals and RESULTS.md (14 known bugs in the original 10 cases, 7 in batch 2), so 21 bugs in all.
  - A bug the case's saved review reported is still a scored bug, as the case file's batch 2 rule says. Its `original_review: reported` lets the report split recall by it.
  - The three controls in the original 10 cases are not bugs in the record.
  - The second bug fixed by `9006d54c` (`cf9006d5-N1`) was found in grading and is not in the totals. It stays in that case's `notes` and is not a case bug.
- **`distribution` and `host_repo` are written in the file**, so `cases add` reads nothing else from the repo or its remotes. All six source repos have an `origin` remote; context-forge also has a second one (`pro`), which is one reason the host repo is stated, not selected.
- Rejected: parsing the existing markdown, which is prose with variable layout. A parser for it would be fragile and would fail silently on new cases.

Case file:

```yaml
name: trading-data-921
kind: code                      # 432 adds `document` (D14)
repo: ~/source/repos/manta/trading-data   # local path; `~` expanded at run time
host_repo: <owner>/<repo>       # code-host repository, for the leak rules (D6)
distribution: <package name>    # pyproject [project].name or package.json name at head (D6)
base: eaf1ab4e5913465369ad916785cce5974eaab08c
head: 9b54f27bdc6b62bca9890bc5006bbac73f2ea6bc
status: checked                 # verified | checked
hand_run_id: "921"              # id used in the hand-run folders; import only
bugs:
  - id: B1
    description: "..."
    proof: [dc391881]           # fix commits or issue refs (#n)
    original_review: missed     # missed | reported
    extra_locations:            # optional; files beyond those the proof commits changed
      - file: <path>
        symbol: <name>          # optional hint for `label`
        reason: "..."
notes: "..."
```

A bug whose proof is an issue rather than a commit must have `extra_locations`, and validation refuses it otherwise.

### D2 — A recipe is fan-out or a pool, then ordered combs; combs run per reviewer output
Status: decided
- Recipe file (YAML; passed to `run` and `report` with `--recipe`, repeatable):
  ```yaml
  name: haiku-sol-luna-opus
  reviewers: [haiku-xhigh, sol]   # one entry = single reviewer
  pool: false                      # true = a random pick from the members, scored as its expected value
  combs: [luna-r, opus-high]       # applied in order; [] = no comb
  ```
- **Combs run on each reviewer's output separately, never on a union.** A comb decides each finding on its own. Combing each output keeps every comb reusable: the luna-r comb of haiku-xhigh run 1 on a case serves every recipe that contains haiku-xhigh and a luna-r first comb. A two-stage comb (luna-r, then opus-high) runs opus-high on what luna-r kept (this is `comb.py --after`). This is also how the hand-run comb data was produced, so it imports directly.
- **Fan-out score** for run k on a case is the union of each reviewer's final kept findings for run k. A known bug is hit if any reviewer's kept finding hits it. The finding count is the sum, with duplicates across reviewers counted, and the report says so.
- **Pool score.** The plan's pool picks one member at random per case run. The report scores that pick by its expected value, the mean of the members' per-case metrics, which is exact and adds no sampling noise. Computing it needs every member's stored output. **Cost consequence:** `run` on a pool of N members makes N review calls per case run (plus their combs), not one. When the members are already stored, a pool costs nothing. Pool and fan-out are not combined in one recipe, and the loader refuses `pool: true` with one reviewer.
- **Report rows** are keyed by recipe name plus the identities of the stages they use (D4). A recipe file whose stages resolve to different identities on different cases is reported as separate rows and flagged, never merged.

### D3 — Hit rule: a mechanical location gate, then a stored label; no model
Status: decided
- **Gate.** For each kept finding and each known bug of its case:
  1. Collect the file paths the finding cites: path-like tokens with an extension, taken from `location` and the description. The parse is lenient: `path:12-30`, `path#symbol`, `path (some text)` and bare basenames all work.
  2. A cited path matches a bug file when one ends with the other at a `/` boundary (`minute.py` matches `src/.../minute.py`).
  3. A finding that cites no path at all is a **candidate** for every bug of the case, since the gate cannot decide it.
  4. A finding that cites paths, none of which match a bug's files, is a **decided miss** for that bug. It is not listed and needs no person.
  5. Otherwise it is a **candidate** for that bug.
- **Label.** A candidate counts as a hit only if the case's labels hold `HIT` for (finding content key, bug). `ADJACENT` and `MISS` labels are decided non-hits, and `ADJACENT` is counted separately, as the runbook asks. A candidate with no label is **undecided**.
- **Undecided is not a miss.** This covers both undecided hit candidates and `UNDECIDED` comb decisions.
  - The report gives recall as a lower and an upper bound:
    - The **lower bound** treats an undecided candidate as a miss and an `UNDECIDED` comb decision as DROP.
    - The **upper bound** treats an undecided candidate as a hit and an `UNDECIDED` comb decision as KEEP.
    - When nothing is undecided, the two are equal and print as one number.
  - **Two-stage combs.** A stage-two comb sees only the findings stage one kept. A finding stage one left `UNDECIDED` is not sent to stage two. It stays undecided in the chain's output, so it is dropped in the lower bound and kept in the upper bound.
  - **Paired intervals** (D12) use only cases with nothing undecided in either recipe, and print how many cases were left out for that reason.
  - `label` lists every undecided hit candidate.
- **Scored findings (found while implementing, 20261118).** Only CONCERN and FAIL findings are scored and sent to a comb (`SCORED_SEVERITIES` in `scoring.py`). That is the set the hand-run comb (`comb.py`), the grading passes (`prep.py`) and the RESULTS.md tables used: the report example's 7.8 findings/run for haiku-xhigh is its CONCERN/FAIL count (all findings would be 14.7). NOTE and PASS findings are stored but not scored.
- **Matched nothing.** A kept finding matched nothing when it is decided for every bug of its case (by the gate or by a label) and none of those decisions is `HIT` or `ADJACENT`. A finding that is undecided for any bug is counted only as undecided. It uses the lower-bound kept set.
- **Content key** is sha256 of the normalized (location, title, description), with whitespace collapsed. A label attaches to finding content, not to a stage, so a comb (which passes findings through by id) inherits the label, and an identical finding in a repeat run needs no second label.
- **Precedence:** person over import passes. Among `person` labelers, the record with the newest `updated` wins (PM-approved 20261116); there is no disagreement listing.
- **Why this rule.** The gate is deliberately loose (file level), so it never decides a real hit away. The person decides what the gate cannot. A test checks the gate against every imported hit label (Success Criteria). If an imported hit fails the gate, the case needs an `extra_locations` entry with its reason. The gate itself is not loosened.
- Rejected: a model matcher, which the runbook forbids for hits. Also rejected: symbol or line-range matching as a decider. The hand-run hits cite neighbouring lines, effect blocks and callers, so a strict span test would deflate recall. The symbol is shown in the `label` listing as a hint only.

### D4 — One run record per case run, holding every reviewer's review and combs
Status: decided
- **`RecallRun`**, one record per (case, run index), as the architecture's coarse-record rule asks:
  - `reviews: dict[entry_key, StageEntry]`, one per reviewer config.
  - `combs: dict[str, StageEntry]`, keyed by the string `"<entry_key>|<chain_key>"` (a tuple cannot be a JSON object key). Here `chain_key` is the ordered comb entry keys joined with `>`. A two-stage comb's input is the entry whose chain is one shorter.
  - `superseded: list[StageEntry]`: entries a retry replaced (D8).
- **`StageEntry`**:
  - `config`: `StageConfig` (below)
  - `effort_configured`, `effort_sent`. `effort_sent` comes from the call's usage record, and is `null` when it was not recorded (every imported entry).
  - `findings: list[RecallFinding]` (review only)
  - `decisions: dict[finding_id, CombDecision]` (comb only; `KEEP` | `DROP` | `UNDECIDED`, with the reason)
  - `usage` (cost_usd, cost_basis, duration_s, turns, tool_calls)
  - `outcome` (D8)
  - `leak`: `no_leak_detected` | `confined` | `leaked` | `scan_unavailable` | `not_scanned` (D6)
  - `source` (`live` | `import:<folder>`)
  - `case_set`: the set name and version the entry was produced under (`run`'s `--set`; `import` records the set named in its `--set`)
  - `raw_ref` (sha256 in the `REVIEWS` sidecar)
  - `alias`, for display only
  - `created`
- **`StageConfig`** follows the architecture's identity list, with the alias for display only: model, profile, template_hash, `tool_use`, `max_output_tokens`. `config_key` is sha256 of those five.
  - **Difference from 425's `reviewer_key`:** `reviewer_key` hashes model, profile, configured effort and template hash. `config_key` leaves out configured effort and adds `tool_use` and `max_output_tokens`. Effort enters identity only as effort sent. 425's `ReviewerRef` is not changed.
  - Imported entries follow D10, with explicit unknown markers.
- **Stage identity in reports** is (`config_key`, `effort_sent`). Two aliases that resolve to the same model and settings and send the same effort are one row. An `effort_sent` of `null` is shown as "not recorded", never as the alias's effort.
- **Entry selection.** `report` matches a recipe stage to stored entries by stage identity (`config_key`, `effort_sent`). Live identities come from an injected `StageIdentityResolver` (protocol in `scoring.py`; live implementation `LiveStageResolver` in `stage_identity.py`). An entry whose `source` is `import:*` matches when its `alias` equals the recipe's alias. Each distinct stage identity found becomes its own row; a recipe with both live and imported matches gives separate, flagged rows. `entry_key` is used only by `run`, to decide whether a stage is already stored, and only live `entry_key` matches count as stored.
- **`entry_key`** is sha256 of (`config_key`, `effort_configured`). Configured effort is in this key only so that two calls that could send different efforts, and so are distinct pending calls, are not taken for each other before they run. It is not identity: report rows use `effort_sent`.
- `RecallFinding`: finding_id, content_key, severity, category (402 vocabulary through `map_historical_category`), raw_category, location, title, description. This extends `CodeReviewFinding` with the full text, which combing and labelling need. Findings are stored in full.
- **Record id:** `rbrun-<sha12>` of (case_id, run_index).
- **Writes.** A run record is rewritten with the store's `write_record` when an entry is added or replaced. The store lock (D9) means only one writer at a time.
- **Size and count.** The import writes 51 run records, one per (case, run) in the hand-run data. Each holds every review's findings and every comb's decisions for that case run. Raw output, 5.8 MB in all, stays in the sidecar.
- **Set version.** Each entry records the set it was produced under. The report takes case membership from the set version named on its command line (`--set`, newest version unless `name@version` is given). It prints that version in the header, plus the number of entries used that were produced under a different set or version.

### D5 — Graded-real share comes from the imported grading passes
Status: decided
- **Graded-real share** = REAL / graded findings, over a recipe's final kept findings (lower-bound set). The grades come from the imported passes (D10) and the person overrides.
- The report names every grading pass whose grades the share uses, and shows the graded count. It also shows the number of grades a person has checked (findings with both an override and a pass grade), and agreement on that checked set.
- Findings with no grade are counted as ungraded and are left out of the share. Live entries are ungraded until live grading exists ([#340](https://github.com/ecorkran/squadron/issues/340)).
- Combs never use grades. Only the report does.

### D6 — Every stage call is a scrubbed subprocess, and its transcript is scanned for leaks
Status: decided
- The source checkout named by each case holds the later fix. Review tools under the `sdk` and Codex profiles are not confined to the working directory, so the sandbox alone does not keep the fix out of reach. Squadron's own `read_file`, `list_files` and `grep` (used by OpenAI-compatible profiles) already refuse paths outside the working directory (`tools/builtin/_shared.py`).
- **Auth preflight.** Before the bound prints, `run` calls `run_auth_check` for the distinct profiles behind the recipe's aliases, with `benchmark.auth_probe_timeout_s` and the `resolve_sq_path()` path. A profile that does not answer `yes` refuses the run (exit 1), naming the profile. No stage is recorded.
- **Each call runs as a subprocess** with cwd = the sandbox and the environment of a 421 `ScrubbedEnvironment`: a redirected home, the alias profile's credentials only, and no user config, store or memory. The scrubbed `PATH` does not hold `sq`, so every command uses the absolute path from `resolve_sq_path()`, resolved once per command, as 421's auth check and slice runner do.
  - Review: the case kind's review command (D14). For `code` it is `<sq> review code --diff <base> --model <alias> --no-save --output file --output-path <out> --cwd .`. This is the production command, unchanged, so the benchmark measures what users run. `--cwd .` (added 20261118, walkthrough step 5) keeps a `cwd` key in the seeded user config from pointing the review outside the sandbox.
  - Comb: the hidden `<sq> benchmark recall _stage --template comb --input <file> --output <file>` (in the same style as `_auth-probe`). It calls `run_review_with_profile` with the template, `allowed_tools: [read_file, list_files, grep]`, and the findings rendered as `F1..Fn` (the `comb.py render` format).
  - `_stage` also takes `--model <alias>` and `--diff <base>` (found while implementing, 20261118): the call needs the alias, and the prompt's changed-file list is `git diff --name-only <base> HEAD` in the sandbox, as `comb.py` built it. The input file holds only the parent's kept CONCERN/FAIL findings (D3 scored findings).
  - `<out>` is a deterministic path under the benchmark root, `recall-out/<record id>/<stage key>.json` (D8).
  - **Effort sent for live entries** (found while implementing, 20261118). `sq review code` and `_stage` write `ReviewResult.to_dict()`, whose `effort` field is the effort actually sent: `review_client` writes it only when the provider applies effort (slice 931 D4). Neither writes an `effort_sent` key, so a live entry's `effort_sent` is read from `effort`. The live resolver predicts the same value with `effort_sent_by_profile(profile, configured effort)` (`pipeline/usage_capture.py`), so stored live entries match their recipe stage. Imported entries keep `effort_sent: null` (D10).
- **Leak rules** come from 424's `build_leak_rules`, unchanged, with these inputs:
  - `tree`, `home`, `output_dir`: the sandbox tree, the call's scrubbed home and its output directory. These are the only roots a call may use.
  - `real_home`: the user's home. It covers the store and the user's config and memory.
  - `repo_root`: the case's source checkout, which holds the fix.
  - `install_location`: `installed_package_location()`, the installed squadron package, which may be a later `sq`.
  - `uv_cache`: `uv_cache_dir()`, the package manager's cache.
  - `distribution_name`: the case's `distribution` (D1), so reads of an installed copy of the case project in site-packages or the cache are hits.
  - `host_owner`, `host_repo`: the case's `host_repo` (D1). The git and `gh` rule then covers calls that could read the fix from the host.
- **Leak verdicts.** After the call, `transcript_source_for(profile)` is looked up:
  - **A source exists:** `leak_scan.scan(source, <scrubbed home>, rules)` runs, and its verdict goes in the entry's `leak` field.
    - `leaked` or `scan_unavailable`: the entry is stored and dropped from every recipe's comparison, like a harness failure (D8), and counted by verdict. This is the architecture's "a run that reaches for it is not graded".
    - `no_leak_detected`: scored.
  - **No source**, and the profile's tools are squadron's jailed builtins: the scan is not called, and the verdict is `confined`. Scored. A profile with neither is refused at plan time (exit 1). The scan is never handed an absent source.
  - **`not_scanned`:** imported entries. They ran in worktrees of the real repo, before this rule existed. They are scored, so the hand-run tables can be reproduced, and the report prints how many scored entries are `not_scanned` on every row that uses them.
- `review_tree_diff` in 425 stays as it is (no-tools grading in its own sandbox).

### D7 — The sandbox holds head with its ancestry back to base, and nothing later
Status: decided
- **Needs an architecture amendment.** The architecture says recall runs "in a history-free sandbox at the diff's head", and describes that sandbox as "one commit, no refs to later history". Recall's sandbox holds `head` and its ancestry back to `base`.
  - It needs that ancestry because `sq review code --diff <base>` rewrites a bare ref to the merge-base form `<base>...HEAD`, which needs a path from `head` back to `base`.
  - The smaller alternative, fetching only `base` and `head` at depth 1, leaves no merge base, so the production command fails.
  - The property the architecture protects still holds: fetching a commit brings its ancestors only, so no commit later than `head`, and so no fix, can be present.
  - **Proposed amendment** (a line under the architecture's 20261115 amendment): "Reviewer recall's sandbox holds the diff's head and its ancestry back to base, and nothing later; 'one commit' describes the replay sandbox."
- **Mechanism.**
  - `recall/review_sandbox.py` wraps `HistoryFreeSandbox` without changing it, and enters `HistoryFreeSandbox(start_sha=head)`. That one-commit build runs under the sandbox's own fixed 120-second bound per command.
  - The wrapper then runs three commands of its own through the injected `ProcessRunner`, not the sandbox's helper, each with timeout `benchmark.recall_fetch_timeout_s`:
    - `git rev-list --count base..head` in the source repo
    - `git -C <tree> fetch --depth <count + 1> <repo> <head>`
    - `git -C <tree> rev-parse --verify base^{commit}`
  - If the last command fails, the sandbox fails with that reason. No refs are created.
- No language adapter and no environment install: reviews read code and run nothing.
- One sandbox per case per command invocation, reused for every stage of that case and then removed. Each stage call gets its own scrubbed home, so each transcript scan covers one call.

### D8 — Failure modes and how each is observed
Status: decided
Every mode below is logged at the level shown, with case, run and stage where they apply. It is written into the entry's `outcome` or the command summary, and covered by a test that asserts both the outcome and the log record.

**Classification rule.** A failure the model or its output caused is `config_failure`, a miss for that config. A failure of setup is `harness_failure`, dropped from every recipe. Setup means credentials, the `sq` path, the sandbox, the repo, the fetch, or a subprocess that exits without writing its output file. Credentials are proven by the auth preflight (D6) before any call. The output file is the signal: `sq review code` and `_stage` write it once a model call has run, so no file means the call never reached the model.

Stage calls:

| Mode | Level | Outcome | Effect on scoring |
|---|---|---|---|
| Profile fails the auth preflight | ERROR | Run refused, exit 1, nothing recorded | — |
| Subprocess cannot start, or exits without writing its output file (credentials rejected mid-run, plan quota exhausted, `sq` path gone) | WARNING | `harness_failure` + exit code and stderr tail | (case, run) dropped from every recipe, counted by reason |
| Review call exceeds `benchmark.review_timeout_s`, or its output file holds no parseable result | WARNING | `config_failure` + reason | A run with no findings: a miss for that config |
| Comb call (`_stage`) exceeds `benchmark.review_timeout_s`, or its output holds no parseable decision line | WARNING | `config_failure` + reason | The comb has no output. Recipes using it count that (case, run) as zero kept findings, a miss |
| Comb returns decisions for some findings only | WARNING | `ok`; missing ones are `UNDECIDED` | Range per D3; count printed per recipe |
| Repo missing, sandbox build fails, a D7 command exceeds `benchmark.recall_fetch_timeout_s`, connection drops mid-fetch, or `base` not reachable | WARNING | `harness_failure` + reason | (case, run) dropped from every recipe, counted by reason |
| Leak scan `leaked` or `scan_unavailable` (D6) | WARNING | `ok` with that `leak` verdict | Dropped from every recipe, counted by verdict |
| Crash after a call's output file is written but before its entry is stored | WARNING on resume | On resume, an output file in `recall-out/` with no entry is ingested, and its leak scan runs if its scrubbed home is still present. Otherwise the call is repeated, and the WARNING says the earlier call's cost was spent without a record | As for the ingested or repeated call |
| Recipe lacks a stage for some (case, run) | — | — | Scored only over complete pairs. n cases and runs printed, and left-out pairs listed |

Other I/O paths:

| Mode | Level | Outcome |
|---|---|---|
| `cases add`: any file fails validation (schema, missing proof commit, issue proof without `extra_locations`) | ERROR | All files are validated before anything is written. One failure refuses the whole command (exit 1), listing every failing file and reason. No case and no set version is written |
| `cases add`: `git show --name-only` fails or times out for a proof commit | ERROR | Refused as above, naming the commit |
| `import`: a hand-run file is unreadable or not valid JSON, or lacks a field the import needs | WARNING | That file is skipped and listed in the summary with the reason. The import continues, and exits 1 at the end if anything was skipped |
| `import`: a grade ref names a config, run or finding index with no imported finding | WARNING | That ref is skipped and listed. The other refs of the pass are imported |
| Store lock held by a live process | ERROR | Refused, exit 1, naming the owner pid |
| Store lock whose owner is gone | WARNING | Taken over (424's `BenchmarkLock` behavior) |
| `write_record` fails | ERROR | The command stops with exit 1. Records already written stay, and the output file stays in `recall-out/` for the next run to ingest |

- **Retry deletes nothing.** `run --retry-harness` runs harness-failure and dropped-leak entries again. The new entry replaces the old one in the run record, and the old one moves to `superseded`, so the report always uses the current entry. Config failures are results and are not retried.
- The hand-run `comb.py` change that defaulted missing decisions to DROP is not carried over.

### D9 — Cost bound, cap and resume follow 425; calls run serially
Status: decided
- `run` refuses to start without `--max-cost`, or without `benchmark.review_timeout_s` set (exit 1; the timeout through `check_review_timeout` in `benchmark/grading_config.py`, as `benchmark_grade.py` does).
- **Per-call figure** for each stage config is the largest observed `cost_usd` for that `config_key` in recall run records. With none observed, `--call-cost` is required, and the command refuses without it.
- **Stated bound** = the sum of the per-call figures for every missing priced call, plus the largest per-call figure once. That last term is the overshoot: the cap is checked before each call, so one call can cross it. The line says "estimate" when any figure comes from observed costs, because a later call can cost more than any earlier one. It says "from --call-cost" otherwise.
- **Plan-billed calls.** Calls with `cost_basis` `plan` (Codex) count as $0 toward the dollar cap. When the plan holds any, `--max-plan-calls N` is required, and `run` stops before the (N+1)th plan-billed call with exit 2. The bound line shows the plan-billed call count against that cap.
- **The bound prints before the first call**, after the lock is taken and the auth preflight passes. It lists missing stages by kind and config, the dollar bound with its label, the plan-billed count, and "capped at $X". The wording follows `grade_plan.render_bound`.
- `ReviewBudget` is reused as it is: `before_review()` before each dispatch, `after_review(cost)` after. On `GradeCapReached`, or at the plan-call cap, the command stops dispatching, keeps every record written, prints what is left, and exits 2.
- **Calls run one at a time**, following the architecture's non-goal. Concurrency is [#146](https://github.com/ecorkran/squadron/issues/146).
- The store lock is 424's `BenchmarkLock.acquire(root, benchmark_id, runner)` with lock id `recall`. It stops two recall commands from running at once.

### D10 — Import maps the hand-run files and names the source of every field
Status: decided
- `import <results-dir> --set <name>` reads:
  - review outputs: the `*.json` files directly under `20261112-grid1/`, `20261112-grid2/` and `20261113-grid3/` (`<case>-<config>-<run>.json`). A file whose content (sha256 of the bytes) matches a file already read is skipped and listed as a duplicate. This drops all 27 grid1 files, which are copies of grid2 files, leaving 696 (PM decision 20261118).
  - comb outputs: `20261113-comb/out/<comb>/<case>-<reviewer>-<run>.json`. The two-stage `luna-r+opus-high` folder becomes the chain luna-r then opus-high.
  - grading passes: `*/precision/*-graded*.json`
- **Case mapping** is by each case file's `hand_run_id`. A file whose case id has no case record is reported and skipped, never guessed.
- **Imported review config.** Each field has one source, and nothing is filled in:

  | Field | Source |
  |---|---|
  | alias (display) | the `<config>` part of the file name |
  | model, profile, max_output_tokens | the output's `model`, `profile` and `max_output_tokens` fields |
  | effort configured | the output's `effort` field |
  | template_hash | `unknown:<template_name>@<squadron_version>`, from the output's two fields. The outputs record no hash, and `template_content_hash` hashes today's template, so it is not used |
  | tool_use | the output's `tools_given`: non-empty is `true`, empty is `false`. It records what the call was actually offered, which is the fact identity needs. It also separates `sonnet` from `sonnet_notools` (tools suppressed for the run), which otherwise share every field (PM decision 20261118) |
  | effort_sent | `null`: the outputs' `effort` is the alias's value, which the 420 slice forbids as a stand-in |

- **Imported comb config.**

  | Field | Source |
  |---|---|
  | alias (display) | the `out/<comb>/` folder name |
  | effort configured | the output's `effort` field |
  | model, profile, max_output_tokens, tool_use | `unknown`: comb outputs record none of them. Combs that differ only in the folder name therefore share a `config_key`, so the import adds the folder name to the comb's template marker (`comb.yaml@9bc108a6#<folder>`) to keep them apart |
  | template_hash | `comb.yaml@9bc108a6#<folder>`. The prompt is as committed in that commit. The runs used the review recovery turn (`recovery_turn_used: true`), which the live `decisions` template does not |
  | effort_sent | `null` |

- **Unknown is a value, not a gap.** `unknown` values are part of `config_key`. Imported and live entries therefore never share a `config_key`, and the report shows imported rows as their own rows. The import summary counts entries per unknown field.
- **Grading passes.** Each pass gets its own labeler, `import:<brief>`, with one label record per case it graded:

  | Pass | Grade files | Format |
  |---|---|---|
  | `import:grid2/BRIEF.md` | `20261112-grid2/precision/{case}-graded.json` | `issues` with `members`, `grade` and `known` |
  | `import:grid3/BRIEF.md` | `20261113-grid3/precision/{case}-graded.json` | `matched` and `new_issues` |
  | `import:grid3/BRIEF-B2.md` | `20261113-grid3/precision/{case}-graded-b2.json` | `matched` (finding ref to an issue id) and `new_issues` |
  | `import:grid3/BRIEF-SOL.md` | `20261113-grid3/precision/{case}-graded-sol.json` | `matched` and `new_issues` |

  - A finding ref (`<config>/<run>/<index>`) maps to the imported review entry of that case, config and run, and to its finding at that index. That finding's content key is the label key.
  - A `matched` ref takes the grade and `known` of the issue it names, whichever pass defined that issue. Issue ids are unique across a case's passes; this was checked on the committed files.
  - **Merge rule:** if two passes grade the same content key, the later pass in the table's order wins, and the import summary counts and lists the conflicts.
- **Hit labels**, in the same pass records:
  - A member (or matched ref) of an issue whose `known` is `Bn` gets `HIT` for bug Bn.
  - Members of other issues in the same case get `MISS` for every bug of that case. The grader had sorted them as distinct issues.
  - The cf5e840c partial hit is imported as `HIT`, as RESULTS.md section 13 records the PM decision.
- **Overrides.** The section 12 adjudications that overrode grades in the data (921-I9 REAL, 197-I14 MINOR) are applied as person labels from a small committed overrides file, `user/reference/review-recall-overrides.yaml` (outside the cases folder, so `cases add <dir>` never reads it), so the decision is recorded, not hidden. Each entry is `{case, issue, grade, reason}` and is written as one `RecallLabels` per case with labeler `person:results-section-12`.
- **Found while implementing the import (20261118):**
  - Codex outputs record `tools_given: null` (squadron does not list Codex's own tools). That is not recorded, so `tool_use` is the `unknown` marker, not `false`.
  - A two-stage comb file whose stage one kept nothing holds no `F` refs and no call was made. It imports as `ok` with no decisions (4 files), not as a config failure.
  - Members of an issue whose `known` is `Bn` get `HIT` for Bn and `MISS` for the case's other bugs: the grader sorted them into Bn's issue.
  - Imported entries take `created` (and pass labels `updated`) from the folder's date, and the override record takes the newest pass date of its case, so a second import builds identical records.
  - `raw_ref` is the sha256 of the whole output file, which is what goes in the sidecar.
  - The committed passes have no grade or hit conflicts; the conflict path is tested on a synthetic pass.
- Every imported entry has `leak: not_scanned` (D6).
- Not imported: `20261112-311/` (markdown experiments on one case) and `20261115-design/` (432's).
- The import is idempotent. Run record and label record ids are deterministic, and a second import changes nothing.

### D11 — The first live recipe is a PM-run walkthrough step on the non-squadron cases
Status: decided
- The first recipe is haiku-xhigh and sol in parallel, then a luna-r comb, then an opus-high comb, one run. The comb alias is `luna-r`, the OpenRouter alias RESULTS.md section 5 measured; plain `luna` is the Codex alias, which was not measured as a comb. Its recipe file is committed with this slice, and it runs on case set `real-bugs-nonsquadron`. That set is the 14 cases outside squadron's own repo, following the measurement-slices rule that no task runs against squadron's own history.
- Run serially (D9), it takes the sum of its calls. That is about 10 minutes per case at the hand-run median times, so over an hour for 14 cases. The measurement rule says no task needs hours. So this design makes the run walkthrough step 7, run by the PM after the slice, not an implementation task. Its report is appended to RESULTS.md as a new section, with the date.
- The plan's criterion becomes "The first recipe is committed and ready; the PM runs it after the slice" (PM decision 20261116).
- The comb prompt is the hand-run first draft. Its template hash is in every comb entry, so a later revision shows as a separate row.

### D12 — Recipe comparisons carry paired intervals
Status: decided
- For every pair of recipes in a report, scoring takes the cases both have complete and that have nothing undecided in either recipe (D3). Per case, it reduces each recipe to one value: recall (bug-hits / (bugs × runs)), and separately findings per run. `paired_stats.compare_pair` then gives the mean difference and its bootstrap interval, over cases, with the seed from `pair_seed(benchmark_id, key_a, key_b)`, where `benchmark_id` is `<set name>@v<version>` and the keys are the two row keys.
- A pair whose interval spans zero is printed as "not distinguishable", not ranked. Fewer than 8 usable shared cases (the runbook's floor) prints "too few cases" instead of an interval. The line also gives the number of cases left out for undecided items.
- Graded-real share gets no interval. It is agent-graded, and the report already marks it as first-pass.

### D13 — `cases add` reads squadron's own commits for three cases
Status: decided
- D1 derives bug locations from each proof commit's file list. For the three squadron cases (932, 175, 197), that is `git show --name-only` on four squadron commits (`5e384226`, `0a850c0a`, `af50b937`, `366250ba`). It runs no review, build or test against squadron's history, and takes seconds.
- Reading commit metadata for case records is outside the measurement-slices rule (PM decision 20261116).

### D14 — The case kind is a seam
Status: decided
- `kinds.py` defines the `RecallKind` protocol, with a registry keyed by the case's `kind`:
  - `validate(case_file) -> RealBugCase`: kind-specific fields and checks.
  - `open_sandbox(case, runner) -> ContextManager[Path]`: the tree a review reads.
  - `review_argv(case, alias, sq_path, out_path) -> list[str]`: the review command.
- `CodeKind` is the only implementation here. It wraps D1's fields, D7's sandbox and D6's `sq review code` command.
- `cases add`, `stage_runner` and the import look up the kind and never branch on it. The recipe model, combs, labels, the hit rule and `scoring` take no kind input. 432 adds `DocumentKind` and a registry entry, without changing them.

### Technology Choices
- **Non-functional.** Recall runs serially under D9 as a PM-run benchmark, so it has no load-test tier.
- PyYAML for case and recipe files (already a dependency, used for templates). Pydantic models for records, as in every other metrology payload.
- No new dependencies.

### Patterns and Conventions
- Enums for every compared value: `StageKind`, `HitVerdict` (`HIT`, `ADJACENT`, `MISS`), `FindingGrade`, `CombVerdict` (`KEEP`, `DROP`, `UNDECIDED`), `StageOutcome`, `LeakVerdict` (424's, plus `confined` and `not_scanned` in recall's own enum), `LabelerKind`. The decisions parser maps words to enum members in one table. The `unknown` marker is one constant.
- **Decisions parser:** lenient. It accepts `F3: KEEP — reason`, `F3 - KEEP: reason`, `**F3**: keep`, a hyphen, en dash or em dash, any case, and surrounding markdown. The first verdict per id wins, and later repeats are counted in a `duplicate_decisions` field. Unknown ids are counted, not dropped silently. The fixtures are real hand-run comb `raw_output` strings.
- Record id prefixes: `rbcase-`, `rbset-`, `rbrun-`, `rblabels-`.

## Implementation Details

### API Contracts

CLI (`sq benchmark recall ...`). Exit codes: 0 complete, 1 refused or error, 2 cap reached (work remains).

| Command | Purpose | Key options |
|---|---|---|
| `cases add <path>...` | Validate case files, write cases and a new set version | `--set NAME` (required) |
| `cases list` | Cases and sets with versions, bug counts and source status | `--set` |
| `import <results-dir>` | Import hand-run outputs and grading passes | `--set NAME` (required), `--dry-run` |
| `run` | Run the missing stages for recipes over a case set | `--recipe FILE` (repeatable), `--set NAME[@VERSION]`, `--runs N` (run indexes 1..N), `--max-cost`, `--call-cost`, `--max-plan-calls`, `--retry-harness`, `--case NAME` |
| `label` | List undecided hit candidates; record a person's hit label | `--recipe`, `--set`, `--case`; `--hit FINDING_KEY BUG HIT\|ADJACENT\|MISS`, `--by NAME` |
| `report` | Recall report per recipe, with paired comparisons | `--recipe` (repeatable), `--set NAME[@VERSION]`, `--runs`, `--json` |
| `_stage` (hidden) | One comb call; launched by the runner | `--template`, `--input`, `--output` |

`report` text output, one row per recipe and stage identity:

```
Case set real-bugs-original v1: 10 cases, 14 known bugs, runs 1..3
Hit rule: location gate + labels; recall is shown as low–high when anything is undecided.

| Recipe | Cases | Runs | Bug-hits | Recall | Bugs found | Runs with a hit | Adjacent | Undecided | Findings/run | Matched nothing | Real share (passes; graded, checked) | Cost/run (basis) | Leak scan |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| haiku-xhigh | 10 | 3 | 16/42 | 38% | 6/14 | 14/30 | 0 | 0 | 7.8 | ... | 24% (import:grid2; 235, 0) | $0.62 sub | 30 not scanned |
...
Paired (recall, 10 usable cases, 0 left out as undecided): haiku-xhigh − sol  +0.10 [-0.05, +0.25]  not distinguishable
Dropped (harness): 0.  Dropped (leak): 0.  Left out (incomplete stages): none.  Entries from another set version: 0.
```

`label` prints each undecided candidate with: case, bug id and description, the bug's files and symbols, the finding's content key, severity, location, title and description, and which recipes and runs it affects.

### Database / Storage Schema

Four sibling payloads on `MetrologyRecord` (`schema_version` stays 1, no migration), each with a `RECORD_TYPE_*` constant. Payloads carry `project_id: ProjectId` (the squadron project running the benchmark, as for 421's records).

| Record type | Payload | Id | Count |
|---|---|---|---|
| `recall_case` | `RealBugCase` (D1) | `rbcase-<sha12 of content>` | one per case (17) |
| `recall_case_set` | `RecallCaseSet(name, version, case_ids, created)` | `rbset-<name>-v<version>` | one per set version |
| `recall_run` | `RecallRun` (D4) | `rbrun-<sha12 of (case_id, run_index)>` | one per case run (51 from the import) |
| `recall_labels` | `RecallLabels(case_id, labeler, hits: {content_key: {bug_id: HitVerdict}}, grades: {content_key: FindingGrade}, updated, notes)` | `rblabels-<case_id>-<labeler, path-safe>-<sha8 of labeler>` | one per case and labeler: each import pass that graded the case, and the person |

- Per-finding label files are rejected. The import alone covers 3,619 findings, and hit labels are per finding and bug, which would mean thousands of files read on every store query.
- Case, case-set and import label records are written once. Run records and person label records are rewritten in place with `write_record` when they change. The newest write wins, and nothing is deleted.
- Raw review and comb output goes in the `REVIEWS` sidecar, referenced by sha256.

## Integration Points

### Provides to Other Slices
- **432:** the `RecallKind` seam (D14), case records with `kind`, recipes, run records, the hit rule, labels, and `scoring`/`report`. 432 adds `DocumentKind` and reuses everything else.
- **433:** `report --json`, which emits per-row data with case set name and version, n cases, n runs, the recall bounds, matched nothing, real share, cost, paired comparisons and the date of the newest entry, for the code-review category.
- **Pipeline configuration:** the report is evidence for the PM's choice of review step aliases. Nothing reads it at run time.

### Consumes from Other Slices
- `HistoryFreeSandbox` (unchanged, wrapped by D7), 421's scrubbed environment, auth check and `resolve_sq_path()`, and the record store. A change to the sandbox's fetch would surface as harness failures, which are counted, never as wrong recall.
- 424's leak scan, rule builder, transcript sources and process lock. A profile whose transcript format changes gives `scan_unavailable`, which drops entries visibly rather than scoring them.
- 425's `ReviewBudget`, bound wording, exit-code convention and paired statistics.
- 402's category mapping, so imported and live findings share one category vocabulary.

## Success Criteria

### Functional Requirements
- The 17 cases (21 bugs) in `review-recall-cases.md` exist as case files.
  - `cases add` derives each bug's locations from its proof commits, subject to D13. It loads the files as four sets:
    - `real-bugs`: all 17
    - `real-bugs-original`: the first 10, 14 bugs
    - `real-bugs-original-no-u103`: 9 cases, 13 bugs
    - `real-bugs-nonsquadron`: 14 cases
  - Every `extra_locations` entry has a reason.
  - A failing file refuses the whole command, and nothing is written.
  - Adding an 18th case is a new YAML file and one command, with no code change.
- `import` loads the 696 distinct review outputs (27 duplicate grid1 files skipped), the 480 comb outputs and the four grading passes into 51 run records, with no new calls. A second import changes nothing. The import summary lists unknown-field counts, grade conflicts between passes and any skipped files or refs.
- On the imported records, `report` for single-reviewer recipes haiku-xhigh, sol, sonnet-high and sonnet over `real-bugs-original`, runs 1..3, reproduces RESULTS.md section 1:
  - bug-hits 16, 12, 7 and 4 of 42 (13, 9, 4 and 1 of 39 over `real-bugs-original-no-u103`)
  - runs with a hit 14, 12, 7 and 4 of 30

  (Checked against the grade files while writing this design.)
- On imported comb entries, the "known kept" count reproduces RESULTS.md section 5: opus-high 14/14, luna-r 14/14, sol 10/14 and sonnet-high 8/14, over the four run-1 reviewers.
- A recipe of two reviewers plus a comb is scored from stored review and comb entries with no new calls. A fan-out of haiku-xhigh and sol with an opus-high comb, on run 1 of the original cases, is reported from imported records alone.
- A pool recipe of {haiku-xhigh, sol} reports the mean of the two single-reviewer rows.
- With undecided candidates or `UNDECIDED` comb decisions present, recall prints as a low–high range, and the paired line counts the cases left out. The report has a matched-nothing column that excludes undecided findings, and paired intervals per recipe pair, with "not distinguishable" and "too few cases" shown where they apply.
- Imported entries carry the D10 unknown markers and `effort_sent` null, shown as "not recorded". A live entry is always a separate, flagged row from an imported one. Two live aliases with the same model, settings and effort sent are one row.
- `run`:
  - refuses without `--max-cost` or `benchmark.review_timeout_s`, and refuses when a profile fails the auth preflight
  - prints its bound, with the overshoot term and its label, before the first call
  - requires `--max-plan-calls` when plan-billed calls are pending
  - runs calls one at a time, and stops at either cap with exit 2
  - resumes on a rerun without repeating stored entries, and ingests an orphan output file
  - with `--retry-harness`, moves the replaced entry to `superseded` and deletes no record
- Every live stage call runs in a scrubbed subprocess through the `resolve_sq_path()` path and is leak-scanned with the D6 inputs, or marked `confined` with no scan. A fixture call that reads the case's source repo by absolute path is recorded `leaked` and dropped from the report, with the drop counted.
- The hit rule is stated (D3) and tested. Every imported `HIT` label passes the location gate. A finding citing no path is a candidate. A path mismatch is a decided miss. An unlabeled candidate is listed by `label`.
- The report shows real share from the imported passes, naming each pass, with the graded and person-checked counts. Live entries count as ungraded.
- The D11 recipe file is committed, and `run` with it on `real-bugs-nonsquadron` prints its bound.

### Technical Requirements
- `ruff format`, `ruff check` and `pyright` (zero errors) pass, and the `tests/benchmark/recall/` tests pass.
- Tests run no model and no git outside fixtures. The process runner, sandbox factory and clock are injected.
- Every D8 mode, in both tables, has a test asserting its outcome and its log record.
- The decisions parser has fixtures taken from real hand-run comb `raw_output` (at least one Claude, one Codex and one OpenRouter output).
- The import is tested against the real committed hand-run files (they are in the repo), not only synthetic fixtures.
- `HistoryFreeSandbox`, `ReviewerRef`, `build_leak_rules` and `sq review code` are unchanged (no diff in their files).
- The runbook's "Running a reviewer" and "Scoring" sections point to the command, and the hand-run method stays documented as the fallback for outside tools.

### Integration Requirements
- 432 can add a case kind by implementing `RecallKind` and registering it, without changing `scoring.py`, the recipe model or `stage_runner`. A test registers a stub kind and runs a stage through it.
- `report --json` output has a test that fixes its schema for 433.

### Verification Walkthrough

Run from the squadron checkout. Verified 20261118 on the real store (steps 1–6; step 7 is the PM's).

**Caveats found while verifying:**
- Until a release carries `sq benchmark recall`, run every command as `uv run sq ...` from the checkout. The installed tool (`~/.local/bin/sq`, 0.24.33) has no `recall` group. Inside `uv run`, `resolve_sq_path()` finds the checkout's `.venv/bin/sq`, so the scrubbed subprocesses run this code too.
- Recipe files are `project-documents/user/reference/review-recall-recipes/<name>.yaml` (below, `$P`).
- Every command also prints `Skipping unreadable metrology record: .../snapshot-*.json` for three existing snapshot records in the store. They are not recall's.
- In zsh, expand a space-separated file list with `${=files}`; a plain `$files` is one argument.

```bash
P=project-documents/user/reference/review-recall-recipes
```

1. **Load cases.**
   ```bash
   uv run sq benchmark recall cases add project-documents/user/reference/review-recall-cases/ --set real-bugs
   uv run sq benchmark recall cases list --set real-bugs
   ```
   Output: `17 cases (17 new); set real-bugs v1 with 17 cases`, then `Cases: 17, bugs: 21`, each bug's derived file list, and `repo=present` per case. A second `cases add` prints `17 cases (0 new); set real-bugs v1 with 17 cases`. Add the other three sets from `review-recall-sets.md`:
   ```bash
   for set in real-bugs-original real-bugs-original-no-u103 real-bugs-nonsquadron; do
     files=$(uv run python -c "from tests.benchmark.recall.committed import parse_sets, SETS_FILE, CASES_DIR; print(' '.join(str(CASES_DIR/m) for m in parse_sets(SETS_FILE.read_text())['$set']))")
     uv run sq benchmark recall cases add ${=files} --set $set
   done
   ```
   Output: `10 cases (0 new); set real-bugs-original v1 with 10 cases`, then 9 and 14. `cases list` shows the four sets at v1.

2. **Import the hand-run results.**
   ```bash
   uv run sq benchmark recall import project-documents/user/reference/review-recall-results/ --set real-bugs --dry-run
   uv run sq benchmark recall import project-documents/user/reference/review-recall-results/ --set real-bugs
   ```
   Output: `Review entries: 696`, `Comb entries: 480`, `Run records: 51`, `Label records: 56`, `Unknown fields: max_output_tokens 480, model 480, profile 480, template_hash 696, tool_use 633`, `Duplicates skipped: 27` (each grid1 file listed), `Label conflicts (later pass wins): 0`, `Skipped files and refs: 0`. The real run ends `Written: 51 run records, 56 label records`; a second import prints `No changes.` Exit 0.

3. **Reproduce the hand-run tables.**
   ```bash
   uv run sq benchmark recall report --set real-bugs-original --runs 3 \
     --recipe $P/haiku-xhigh.yaml --recipe $P/sol.yaml --recipe $P/sonnet-high.yaml --recipe $P/sonnet.yaml
   uv run sq benchmark recall report --set real-bugs-original-no-u103 --runs 3 --recipe $P/haiku-xhigh.yaml
   ```
   Rows (Bug-hits, Recall, Runs with a hit): haiku-xhigh `16/42 | 38%` … `14/30`, sol `12/42` … `12/30`, sonnet-high `7/42` … `7/30`, sonnet `4/42` … `4/30`, each `30 not scanned`; without u103 haiku-xhigh `13/39`. These match RESULTS.md section 1. haiku-xhigh's row also matches the report example (7.8 findings/run, real share 24% over 235 graded, $0.62). Paired lines: haiku-xhigh − sol `not distinguishable`; haiku-xhigh ahead of sonnet-high and sonnet. The footer counts `Entries from another set version: 120`, because the import recorded its entries under `real-bugs@v1`, and this report is over `real-bugs-original`.

4. **Score a compound recipe with no calls.**
   ```bash
   uv run sq benchmark recall report --set real-bugs-original --runs 1 \
     --recipe $P/haiku-sol-opus.yaml --recipe $P/haiku-sol-pool.yaml
   ```
   Output: haiku-sol-opus `8/14 | 57% | 8/14` with cost `$1.33` (the sum of its stored review and comb costs), haiku-sol-pool `5.5/14` (the mean of the haiku-xhigh and sol rows; its cost is also the members' mean, the expected cost of one pick), and `Left out (incomplete stages): none.`

5. **Preflight, bound, cap, resume and leak scan on a fixture.**
   ```bash
   uv run python tests/benchmark/recall/fixtures/bug_repo/build.py
   uv run sq benchmark recall cases add tests/benchmark/recall/fixtures/bug_repo/case.yaml --set fixture
   uv run sq benchmark recall run --set fixture --recipe $P/luna.yaml --runs 2 --max-cost 0.05 --call-cost 0.01 --max-plan-calls 2
   ```
   Correction: `luna` is a Codex alias, so its calls are plan-billed (D9) and `run` refuses without `--max-plan-calls` (`Error: 2 plan-billed calls are pending: set --max-plan-calls`). Output: `auth openai-oauth (luna): yes`, `2 stages to run`, `review luna (openai-oauth): 2 calls plan-billed`, `bound: no priced calls, capped at $0.05`, `plan-billed calls: 2, cap 2`, `stored 2 entries; complete`, exit 0. Both entries are `ok` with leak `no_leak_detected` (Codex transcript scanned).
   - Rerun with the same options: `0 stages to run`, exit 0.
   - Cap: plan-billed calls count $0 toward `--max-cost`, so the plan-call cap is the one that stops `luna`. `run ... --runs 4 --max-cost 0.000001 --max-plan-calls 1` prints the bound, makes one call, then `recall plan-call cap reached: 1 of 1`, `cap reached: plan-billed call cap 1 reached; 1 stages left`, `left: fixture-bug-repo run 4 review luna`, exit 2.
   - The overshoot term needs a priced call. A one-line recipe `reviewers: [luna-r]` (OpenRouter) with `--runs 1 --max-cost 0.05 --call-cost 0.01` prints `bound: 1 priced calls $0.01 + one call of overshoot $0.01 → at most $0.02 (from --call-cost), capped at $0.05`. Its entry's leak verdict is `confined` (jailed builtins, no scan).
   - `~/.config/squadron/benchmark/recall-sandboxes/` and `recall-homes/` are empty after each run.
   - Found here and fixed: `sq review code` resolved its cwd from the user's `config.toml` `cwd` key, which the scrubbed home is seeded with, and failed with `git could not be run in './project-documents/user'` (two `harness_failure` entries). The code kind's review command now passes `--cwd .` (the call's cwd is the sandbox). `run ... --retry-harness` reran both and moved the failures to `superseded`.

6. **Label.**
   ```bash
   uv run sq benchmark recall label --set fixture
   uv run sq benchmark recall label --set fixture --recipe $P/luna.yaml --runs 2
   uv run sq benchmark recall label --set fixture --hit <content-key> B1 HIT --by <name>
   uv run sq benchmark recall report --set fixture --recipe $P/luna.yaml --runs 2
   ```
   The first command lists the undecided candidates (`4 undecided candidates`: every stored live finding cites `src/bug_repo/clamp.py:5`), each with the bug, its files, the content key, severity, location, title, description and `affects:`. With `--recipe` it lists the two in luna runs 1–2. Before labelling, the report row is `| luna | 1 | 2 | 0–2/2 | 0–100% | ... | 2 | ...`. After `--hit ... B1 HIT` for both keys (`recorded HIT for <key> B1 as person:<name>`) it is `| luna | 1 | 2 | 2/2 | 100% | 1/1 | 2/2 | 0 | 0 | 1.0 | 0 | ungraded | $0.00 alias_pricing | 2 no leak detected |`. Real share shows the live entries as ungraded.

7. **First live recipe (D11), run by the PM after the slice.**
   ```bash
   uv run sq benchmark recall run --set real-bugs-nonsquadron --runs 1 \
     --recipe $P/haiku-sol-luna-opus.yaml --max-cost 25 --max-plan-calls 14 --call-cost <USD per call>
   uv run sq benchmark recall label --set real-bugs-nonsquadron --recipe $P/haiku-sol-luna-opus.yaml
   uv run sq benchmark recall report --set real-bugs-nonsquadron --recipe $P/haiku-sol-luna-opus.yaml \
     --recipe $P/haiku-xhigh.yaml --recipe $P/sol.yaml
   ```
   Correction: `--call-cost` is required. Per-call figures come only from live entries, and imported entries never share a live `config_key`, so nothing is observed yet. The bound covers 84 stages: 28 reviews and 56 combs. The 14 sol reviews are plan-billed, so `plan-billed calls: 14, cap 14` (checked by `tests/cli/test_benchmark_recall_run.py`). Imported haiku-xhigh and sol reviews have a different stage identity from live ones (unknown fields, `effort_sent` not recorded, not scanned), so the recipe runs its reviews live. The run takes over an hour serially. A person labels the undecided candidates, and the report section is appended to RESULTS.md.

## Risk Assessment

### Technical Risks
- **Labeling load.** Every new reviewer config produces candidates a person must decide. The hand-run grids suggest a few candidates per case with the file-level gate. If the load turns out heavy, that is a reason to tighten the gate with symbol hints, which is a measured change, not a guess.
- **Agent-graded real share.** It is a first-pass signal (RESULTS.md section 8). The report always prints the person-checked count beside it.

### Mitigation Strategies
- The gate-versus-import test catches incomplete bug locations before they deflate recall.
- Real share is never the ranking column. Recall from fix-commit-proven bugs is printed first, as a range when anything is undecided.

## Implementation Notes

### Development Approach
1. Case model, `RecallKind` seam with `CodeKind`, case files for the 17 cases, `cases add/list` with location derivation, and case sets.
2. Run and label models, `recall_store`, and the decisions parser with real fixtures.
3. Hand-run import (the four passes and the field sources in D10), with tests on the committed files.
4. Hit rule, `scoring` (recall bounds, paired intervals) and `report`, then the reproduction tests for sections 1 and 5. This is the first point where the slice gives the PM a result.
5. `review_sandbox`, `stage_runner` (auth preflight, scrubbed subprocess through `resolve_sq_path()`, leak rules, leak scan, `_stage`), and `run` with bound, both caps, orphan ingest and resume, plus the `comb` template. End-to-end on the fixture repo with a scripted model command, including a leaking call and each D8 mode.
6. `label`.
7. Runbook update and the D11 recipe file. The live run itself is walkthrough step 7.

Testing: unit tests per module. Scoring tests use small hand-built run and label sets that cover these cases:
- fan-out, pool and a two-stage comb, including an `UNDECIDED` stage-one decision
- undecided candidates and the recall range, and matched nothing
- harness and leak drops, superseded entries, and incomplete coverage

Import and parser tests use the real hand-run files.

### Special Considerations
- Provider keys for OpenRouter aliases come from the environment, as for `sq review` (the runbook loads `.env` in the shell). The scrubbed environment passes only the alias profile's credentials. Nothing reads `.env` itself.
- The case files hold local repo paths. They are the PM's machine paths, as the hand-run records already are. Nothing is pushed anywhere.
