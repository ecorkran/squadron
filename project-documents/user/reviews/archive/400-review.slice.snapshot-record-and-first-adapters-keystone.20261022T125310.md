---
docType: review
layer: project
reviewType: slice
slice: snapshot-record-and-first-adapters-keystone
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/400-slice.snapshot-record-and-first-adapters-keystone.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261022
dateUpdated: 20261022
reviewedSha: 7e1fad9f73adb5a32dec9541079754bd9b9f52b5
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 97029
cachedTokens: 8865
cacheWriteTokens: 88160
completionTokens: 6091
durationSeconds: 53.9
costUsd: 0.415175
costBasis: provider
runId: run-20261022-p4-4bf38a18
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Alignment with architecture principles and keystone scope"
    location: "project-documents/user/slices/400-slice.snapshot-record-and-first-adapters-keystone.md#Technical Scope"
  - id: F002
    severity: concern
    category: error-handling
    summary: "Read-only integrity check cannot detect writes inside existing ignored directories"
    location: "project-documents/user/slices/400-slice.snapshot-record-and-first-adapters-keystone.md#D9 — Read-only guarantee is checked, not assumed"
  - id: F003
    severity: concern
    category: integration
    summary: "Project limits live in a file that dirties the tree, which conflicts with brownfield \"no config edits\""
    location: "project-documents/user/slices/400-slice.snapshot-record-and-first-adapters-keystone.md#D10 — Config keys"
  - id: F004
    severity: concern
    category: data-integrity
    summary: "Same-commit overwrite can silently replace a snapshot taken under different settings"
    location: "project-documents/user/slices/400-slice.snapshot-record-and-first-adapters-keystone.md#D3 — Same commit re-snapshot overwrites in place"
  - id: F005
    severity: concern
    category: comparability
    summary: "ESLint results have no environment identity"
    location: "project-documents/user/slices/400-slice.snapshot-record-and-first-adapters-keystone.md#D2 — Metric identity is enforced by the model, not by convention"
  - id: F006
    severity: concern
    category: error-handling
    summary: "Failure modes for the store write and the uv environment check are not enumerated"
    location: "project-documents/user/slices/400-slice.snapshot-record-and-first-adapters-keystone.md#Data Flow"
  - id: F007
    severity: concern
    category: proportionality
    summary: "Design is heavier than the keystone requires in a few places"
    location: "project-documents/user/slices/400-slice.snapshot-record-and-first-adapters-keystone.md#D8 — Tool resolution, version and rule-set sources"
  - id: F008
    severity: note
    category: integration
    summary: "`take_snapshot` signature versus HEAD-only scope"
    location: "project-documents/user/slices/400-slice.snapshot-record-and-first-adapters-keystone.md#Provides to Other Slices"
---

# Review: slice — slice 400

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Alignment with architecture principles and keystone scope

The slice covers the keystone entry in the architecture's anticipated slices: record, metric enum, adapter contract, tool/rule-set/environment identity, absent-with-reason, exclusions, project limits, and a TypeScript adapter with length and lint only. Commit export, complexity, duplication, coverage and reports are correctly deferred to later slices. `take.py` depends on the contract and registry, not on concrete adapters, so dependency direction is sound. Determinism is restated as criterion 4 with a walkthrough check.

### [CONCERN] Read-only integrity check cannot detect writes inside existing ignored directories

D9 and criterion 8 rely on `git status --porcelain --ignored` before and after. Git reports an ignored directory such as `.venv/`, `node_modules/` or `.pytest_cache/` as a single entry. A tool that writes a file inside one of those directories that already exists produces no diff. Criterion 8 ("a tool that writes into the repo causes `SnapshotIntegrityError`") therefore holds only for new top-level paths and tracked files. Either narrow the claim to what the check detects, or add a stronger check, such as listing ignored files individually with `--ignored=matching` plus untracked-all, or comparing mtimes of the tool outputs. The slice should also say whether benign tool-created paths, like a fresh `__pycache__`, are expected to fail the snapshot.

### [CONCERN] Project limits live in a file that dirties the tree, which conflicts with brownfield "no config edits"

The architecture's goal is that an existing project gets a baseline "without editing the project's config files or code". Limits and exclusions can only be declared in the measured project's `.squadron.toml`. D9 refuses any untracked file. Squadron works only because its `.squadron.toml` is gitignored (Special Considerations). A brownfield project that declares limits, or exclusions for vendored code, would either fail the clean-tree preflight or have to commit a squadron file. The slice also doesn't say whether `get_config` resolves project config from `--cwd` or from the process cwd. Walkthrough step 8 assumes `--cwd`. State the resolution rule. Then either exempt `.squadron.toml` from the dirty check or say how a project declares limits without breaking preflight. 404 inherits this behavior.

### [CONCERN] Same-commit overwrite can silently replace a snapshot taken under different settings

The store is user-level, and the record id depends only on project and commit. Limits and exclusions come from a per-checkout, gitignored file. Two checkouts of the same project, or two runs under different local settings, overwrite each other. 403 and 404 would then compare a boundary snapshot against one taken under different exclusions or tool versions, with no trace of the earlier record. The architecture's goal is that incomparable snapshots are "explicitly flagged". The Special Considerations section claims this is satisfied, but overwrite destroys the evidence. Either include a hash of the effective settings in the id, or refuse or log at WARNING when the overwritten record's identity differs from the new one.

### [CONCERN] ESLint results have no environment identity

`environment` is required only for type measurements. ESLint counts depend on installed plugins and parsers (for example typescript-eslint versions) in `node_modules`, and none of that appears in the rule-set hash (config content only, `extend` not followed) or the tool version. Two snapshots with the same config hash can differ after a dependency bump and would be reported as comparable. This undercuts the architecture's comparability goal. Record a lockfile identity (`package-lock.json` or equivalent hash) as the environment for ESLint, or state explicitly that lint comparability across dependency changes is out of scope.

### [CONCERN] Failure modes for the store write and the uv environment check are not enumerated

Tool failures and git `None` results are covered well. Several paths are not:
- `store.write_snapshot` failing (disk full, permissions) or two concurrent snapshots of the same commit racing on the deterministic id. The slice doesn't say whether the write is atomic or what the user sees.
- The `uv sync --check` step (D7 condition 3). A missing `uv`, a timeout, and a non-zero exit for reasons other than drift could each map to `tool_missing`, `tool_failed` or `environment_unresolved`. D7 says only that failing the check gives `environment_unresolved`.
- A pathological file that makes `ast` or tree-sitter run unbounded. Only external tools get the timeout.

Each needs a stated handling and an observable signal (WARNING log), in line with the project's failure-mode rule.

### [CONCERN] Design is heavier than the keystone requires in a few places

The two adapters and the identity model are assigned by the architecture. These pieces can be cut or deferred:
- Legacy `.eslintrc*` support and the `eslint.config.{ts,mts,cts}` variants in D8. The walkthrough target is `eslint.config.mjs`. Add other config forms when a real project needs them.
- Canonical-JSON hashing of pyproject TOML tables. Hashing the extracted table's `repr` after a sorted dump is equivalent, but the point is that this is bespoke rule-set normalization for ruff and pyright that nothing downstream consumes yet. Hash the whole config file now and note the pyproject churn as a known limitation.
- `per_rule` totals on lint and type measurements. Nothing in 401, 403 or 404 as described reads them.
- The "fake third adapter" mitigation is useful, but the registry-enumeration test in Integration Requirements already proves the same property.

Eleven modules for this scope is also on the high side. `contract.py`, `registry.py` and `runner.py` could merge without losing the separation the slice wants.

### [NOTE] `take_snapshot` signature versus HEAD-only scope

The text says `take_snapshot(repo_root, ...)` takes a directory and commit sha so 403's export can reuse it. The slice itself only measures HEAD and puts the clean-tree policy in the CLI. This is consistent with the architecture's deferral of export to a later slice. When 403 exports a commit, the environment-reuse rule (lockfile must match the current environment) will need a hook that this contract doesn't yet show.

### Run Digest

- Response length: 8092 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 3
- Tokens — prompt / cached / cache write / completion / reasoning: 97029 / 8865 / 88160 / 6091 / not computed
- Duration: 53.9 s
- Cost: $0.42 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8

## Response

- **F001** no change.
- **F002** accepted: D9 now says read-only is prevented by construction and only partly checked. The `--ignored` diff catches modified tracked files and any new untracked or ignored path, including a fresh `__pycache__/`, which fails the snapshot. It doesn't catch writes inside an existing ignored directory. Criterion 8 is narrowed to match.
- **F003** accepted: config resolves from the measured repo root (`--cwd`), not from the process cwd. An untracked `.squadron.toml` is the single exemption from the dirty-tree check (D9, D10), so a brownfield project declares limits without committing anything.
- **F004** accepted: the overwrite stays. When the replaced record's settings (limits, exclusions, tool, rule set, environment) differ, a WARNING names the changed fields (D3, criterion 9).
- **F005** accepted: `ToolIdentity.uses_project_environment` drives the validator. ESLint records the package lockfile hash and the node version. With no lockfile, lint is absent `environment_unresolved`.
- **F006** accepted: a failure-mode table covers the store write, concurrent writes (unique tmp name in `_write_atomic`) and in-process parse failures. D7 maps uv exit codes (checked with uv 0.11.2): 1 gives `environment_unresolved`; 2 or other gives `tool_failed`; not found gives `tool_missing`; a timeout gives `tool_failed`.
- **F007** partly accepted:
  - Cut: legacy `.eslintrc*` and the `.ts/.mts/.cts` config variants, `per_rule`, and the fake-adapter mitigation. `registry.py` is merged into `contract.py`.
  - Kept: the pyproject table hashing. Hashing the whole file would flag every release's version bump as a rule-set change.
- **F008** accepted: the claim that `take_snapshot` takes a commit sha is removed. 400 measures HEAD only, and 403 extends it with export and the environment-reuse rule.
