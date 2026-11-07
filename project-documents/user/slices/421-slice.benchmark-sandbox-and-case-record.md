---
docType: slice-design
slice: benchmark-sandbox-and-case-record
project: squadron
parent: user/architecture/420-slices.model-benchmark.md
dependencies: [420, 177, 320]
interfaces: [422, 424, 425, 426, 427]
dateCreated: 20261104
dateUpdated: 20261106
status: complete
---

# Slice Design: Benchmark Sandbox and Case Record

## Overview

The shared base that fix cases, slice cases, replay and grading all run on. It adds four things:

1. **Case and case-set records** in the 320 metrology store. A case's id is a hash of its content. A case set is a named, versioned list of case ids.
2. **Sandbox environment resolution.** On top of 177's history-free sandbox, the project's dependencies are installed at the start commit from its lockfile, and an environment identity is recorded.
3. **The scrubbed producer environment.** A process environment built from an allowlist: a redirected `HOME`, no GitHub credentials, and a `PATH` that puts the sandbox's environment first and leaves out the user's tool installs. An **auth check** tells, for each agent provider, whether auth still works inside it.
4. **The benchmark language-adapter seam** and its Python implementation of the **suite runner**. The runner reports pass, fail or error per pytest node id and classifies each failure.

Nothing in this slice dispatches a producer, builds a case from history, or grades anything. Those are 422 to 425.

## Value

Architectural enablement. Every later slice in the initiative uses this one's records, sandbox, environment and suite runner, and none of them has to decide again how to install a historical commit or what the producer may see.

It also answers the riskiest open question before anything is built on it: whether agent auth survives the redirected config directory. If the answer is no for a provider, `sq benchmark auth-check` says so here, and the PM decides what to do before 422 starts.

## Technical Scope

**Included**

- `BenchmarkCase` and `CaseSet` record types, plus their write and read paths in the metrology store.
- A `HistoryFreeSandbox` extracted from `ReplaySandbox`. `ReplaySandbox` keeps its behavior by composing it.
- `BenchmarkSandbox`: a history-free sandbox, plus environment resolution through the adapter, plus a scrubbed home beside it.
- `ScrubbedEnvironment`: builds the producer's environment variables, home directory and `PATH`.
- Per-profile auth carryover and the auth check.
- The `BenchmarkAdapter` protocol, its registry, and `PythonBenchmarkAdapter` (uv environment resolution and the pytest suite runner).
- CLI: `sq benchmark auth-check` and `sq benchmark sandbox`. Both are verification tools. The `/sq:benchmark` slash command arrives with 422's first user-facing command.
- Config keys for the install, suite and auth-probe timeouts.

**Excluded**

- Case discovery, frozen issue text, the fairness rule, qualification and the yield report (422).
- Hidden-test injection (425), the leak scan and the producer-only run mode (424), cf registration of benchmark sandboxes (426).
- The grader, tool-config restoration and the paired report (425).
- Adapters for languages other than Python (Future Work 1).
- Any OS-level containment (#213).

## Dependencies

### Prerequisites

- **420 (effort audit):** must land first. Slices after 421 compare configs by effort sent. 421 itself reads nothing from 420.
- **177:** `ReplaySandbox`, the process lock and the orphan sweep (`src/squadron/replay/sandbox.py`).
- **320:** `MetrologyStore`, `MetrologyRecord`, `ProjectId` (`src/squadron/metrology/`).
- **External:** `uv` and `git` on the harness's `PATH`. Network access for the install step.

### Interfaces Required

- `ProcessRunner` (`core/process_runner.py`). Its `env` parameter merges over `os.environ`, so callers pass `replace_env=True` (added in Task 3) for a child to get exactly the scrubbed environment.
- `ProviderProfile.api_key_env` and `ProfileName` (`providers/profiles.py`, `providers/base.py`). The scrubbed environment uses them to decide which credential variable passes through.
- Model alias resolution (`models.toml`), for the auth check.
- `SourceLanguage` (`metrology/snapshot_models.py`), so the benchmark registry is keyed the same way as 400's.

## Architecture

### Component Structure

```
src/squadron/
  metrology/
    benchmark_models.py     BenchmarkCase, CaseSet, CaseKind, GraderCommand, ConftestFixture
    benchmark_store.py      BenchmarkRecordStore (composes MetrologyStore)
    store.py                + write_record(), iter_records() public primitives
  replay/
    history_free_sandbox.py HistoryFreeSandbox, SandboxError, shared sandbox helpers
    sandbox.py              ReplaySandbox composes HistoryFreeSandbox; sweep_orphans gains
                            sweep_cf_projects and sibling_suffixes
  benchmark/
    adapter.py              BenchmarkAdapter protocol, SuiteSelection,
                            SuiteRun, NodeResult, FailureKind, EnvironmentIdentity
    registry.py             adapter_for(language): the only importer of concrete adapters
    python_adapter.py       PythonBenchmarkAdapter: resolve_environment, run_suite
    python_suite.py         pytest run and fold of the reporter's JSONL into a SuiteRun
    python_failure.py       record contract, classify and fold_records (FailureKind)
    pytest_reporter/        reporter plugin source (stdlib + pytest only), shipped as package data
    sandbox.py              BenchmarkSandbox, benchmark_root, sweep_benchmark_orphans
    scrubbed_env.py         ScrubbedEnvironment, CredentialGrant, SCRUB_SPEC_VERSION
    auth_carryover.py       per-profile carryover table
    auth_check.py           probe orchestration, AuthCheckResult, UnresolvedProfileError,
                            ProbeStartError
  cli/commands/
    benchmark.py            `sq benchmark auth-check`, hidden `sq benchmark _auth-probe`
    benchmark_sandbox.py    `sq benchmark sandbox`
```

`benchmark/` depends on `metrology/` and `replay/sandbox.py`. Neither of those depends on `benchmark/`. CLI code reaches concrete adapters only through `registry.py`.

### Data Flow

**Sandbox with environment** (`BenchmarkSandbox.__enter__`):

1. `HistoryFreeSandbox` writes the lock, then builds `<root>/<id>/` as a one-commit repository at `start_sha` (177's existing steps).
2. The caller passes the adapter, from `adapter_for(SourceLanguage.PYTHON)`. Python is the only language, so there is no detection step. A tree that is not a uv project fails in step 4 with `no_lockfile`.
3. `ScrubbedEnvironment` creates `<root>/<id>.home/`: seeded squadron config, a git config, and credential carryover only if a grant asks for it.
4. `adapter.resolve_environment(ctx)` installs dependencies into the tree (for Python: `uv sync --locked` under the harness environment). It returns an `EnvironmentIdentity` or raises `EnvironmentResolutionError` with a `reason`.
5. The adapter returns its `PATH` entries (Python: `<tree>/.venv/bin`). `ScrubbedEnvironment` puts these first.

**Suite run** (`adapter.run_suite(ctx, selection)`): the runner starts pytest under the scrubbed environment (no credential grant), with the reporter plugin on `PYTHONPATH` from a directory outside the tree. Pytest writes JSONL to `<root>/<id>.out/`. The runner reads the JSONL and returns a `SuiteRun`.

**Auth check**: for each distinct profile among the given aliases, build a throwaway scrubbed home with that profile's grant. Run the installed `sq` by absolute path, under that environment, as `sq benchmark _auth-probe --model <alias>`. Exit 0 with a response means yes. Anything else, including a timeout, means no, and the result carries the probe's stderr.

**Case records**: the caller builds a `BenchmarkCase`. `case_id` is computed from its identity fields. `BenchmarkRecordStore.write_case` writes it once, and an identical case written again returns the same id.

### State Management

- **Store records** (persistent): `benchmark_case` and `case_set` envelopes in `~/.config/squadron/metrology/`. They are optional sibling payloads on `MetrologyRecord`, `schema_version` does not change, and no migration is needed.
- **Sandbox directories** (transient): `~/.config/squadron/benchmark/` holds `<id>/` (tree), `<id>.home/` (scrubbed home), `<id>.out/` (runner output) and `<id>.lock`. All four are removed on exit unless `keep()` was called. The existing orphan sweep, given this root, removes them when their owner is gone.
- **Environment identity**: a value returned to the caller. 421 does not persist it. 422's qualification records and 424's replay records carry it.

## Technical Decisions

### D1 — Case content identity and id
Status: decided
- The identity fields are `project_id`, `kind` (`fix` | `slice`), `start_sha`, `reference_sha`, `task_text`, `hidden_tests` (node ids), `hidden_fixtures` (conftest path and fixture name), `superseded_tests`, `excluded_tests` and `grader_commands`. Lists are sorted before hashing. `case_id` is `case-` followed by the first 16 hex digits of the sha256 of the canonical JSON (sorted keys, no whitespace) of those fields.
- `reference_sha` is in the identity even though the architecture's list leaves it out. The hidden tests' source is read from the reference at grading time, so a different reference means different hidden content. Provenance (issue number, `created_at`, the tool that built the case) is stored but is not part of the identity.
- `BenchmarkCase` is frozen. A `model_validator` recomputes the id and rejects a record whose stored `case_id` does not match, so a hand-edited file fails on read instead of becoming a second case under the old id. `get_case` raises `MetrologyStoreError` for such a file, so it never looks like a missing case. List paths skip it with the store's existing WARNING.
- Rejected: a random id plus content dedup. It needs a lookup on every write and can drift.

### D2 — Case sets are versioned by content
Status: decided
- A `CaseSet` has `name` (lowercase slug, validated), `version` (int ≥ 1), `case_ids` (sorted, unique) and `created_at`. The record id is `caseset-<sha256(name)[:12]>-v<version>`.
- `write_case_set(name, case_ids)` compares the list to the latest version. If they are equal, it returns the existing version. If they differ, it writes version latest + 1. A version is never rewritten. Every case id must already exist in the store, or the write raises `MetrologyStoreError` naming the missing ids.
- A set is keyed by name, not by `ProjectId`, because 422 may pool cases from several projects. Each case still carries its own `project_id`.

### D3 — Benchmark record I/O in its own module
Status: decided
- `store.py` is already 606 lines. Benchmark records will grow over the initiative (cases, sets, qualifications, replays, grades, recall), so their I/O goes in `metrology/benchmark_store.py` as `BenchmarkRecordStore(store: MetrologyStore)`. `MetrologyStore` gains two public primitives: `write_record(record_id, record)`, which wraps the existing atomic write, and `iter_records()`, which exposes the existing tolerant iteration. Each existing record type keeps its own methods. Nothing moves.
- `MetrologyRecord` gains `benchmark_case: BenchmarkCase | None` and `case_set: CaseSet | None`, with `RECORD_TYPE_BENCHMARK_CASE` and `RECORD_TYPE_CASE_SET` constants in `models.py`.
- `task_text` stays inline. Slice-case task text (design plus task file) runs to tens of KB, which is acceptable for coarse records. Diffs (424) are the only sidecars.

### D4 — Extract `HistoryFreeSandbox` from `ReplaySandbox`
Status: decided
- `ReplaySandbox` combines a one-commit repository with cf registration for a slice's initiative. Fix cases have no slice, and environment resolution needs no cf project. The lock, the shallow fetch, the submodule refusal, `keep()` and cleanup become `HistoryFreeSandbox(start_sha, sandbox_id, repo_root, runner, root)`. `ReplaySandbox` composes it and adds `_register_with_cf` and `cf_project`, keeping its public surface (`path`, `branch`, `cf_project`, `keep`, context manager) and its tests unchanged.
- `sweep_orphans` takes a root and a flag for whether to sweep `replay-` cf projects. `sq replay` calls it as it does now. The benchmark sweep handles directories only and also removes the `.home` and `.out` siblings.
- Benchmark sandboxes live under `~/.config/squadron/benchmark/`, a sibling of `replays/`, so the two sweeps never see each other's directories. The store next door is a known leak path, and 424's scan covers it.
- Rejected: an optional `slice_index` on `ReplaySandbox` that skips registration when it is `None`. That turns one class into two behind a flag.

### D5 — Environment resolution for Python: uv lockfile only
Status: decided
- `PythonBenchmarkAdapter.resolve_environment` requires `uv.lock`. It runs `uv sync --locked --all-extras --dev` with `cwd=tree` under the harness environment, bounded by `benchmark.install_timeout_s`.
- `--locked`: a lock that is out of date with `pyproject.toml`, a package that no longer downloads, and a Python version that cannot be obtained all fail. The error carries uv's stderr and a `reason` from `EnvironmentFailureReason` (`no_lockfile`, `lockfile_unsupported`, `lock_stale_or_unresolvable`, `install_timeout`, `installer_missing`). Nothing retries without the lock.
- **Projects without a lockfile** (open question from the slice plan): no lockfile means `no_lockfile`, and other lockfiles (`poetry.lock`, `requirements*.txt`) mean `lockfile_unsupported` naming the file. An unpinned install has no environment identity to key qualification on, so it is not an option. 400's type check supports only `uv.lock` for the same reason.
- `.venv` stays inside the tree so that 400's adapters, which expect `environment_root/.venv` and `environment_root/uv.lock`, can measure the sandbox as it is (425's snapshot). `.venv/` is added to the sandbox's `.git/info/exclude`, so it never shows in a diff, even in a project that does not ignore it.
- Install runs under the harness environment (the user's uv cache, network). Installation is harness work, not producer work. The producer never sees that environment.

### D6 — Environment identity
Status: decided
- `EnvironmentIdentity` holds `language`, `lockfile_path`, `lockfile_sha256`, `interpreter_version` (from `.venv/bin/python --version`), `installer_version` (`uv --version`), `platform` (`sys.platform` and machine), `scrub_spec_version`, and `identity_digest` (sha256 of the rest).
- `scrub_spec_version` is an integer constant in `scrubbed_env.py`. It is incremented whenever the scrub rules change, because tests can depend on `HOME`, `TZ` or git config, so results under one spec should not count as qualified under another.
- This is a new model, not 400's `EnvironmentIdentity`. 400's model describes what a type count depended on. This one is a grader identity with more fields. Both keep `lockfile_sha256` under the same name.

### D7 — Scrubbed producer environment: allowlist, redirected HOME
Status: decided
- The environment is built from an allowlist, never by deleting entries from `os.environ`. That way `GH_TOKEN`, `GITHUB_TOKEN`, `SSH_AUTH_SOCK`, `CLAUDE_CONFIG_DIR`, `CODEX_HOME`, `VIRTUAL_ENV` and any variable added in future are absent unless named.
  - Passed through from the harness: `LANG`, `LC_ALL`, `LC_CTYPE`, `TERM`, `USER`, `LOGNAME`, `SHELL`, `TMPDIR`.
  - Set: `HOME=<id>.home`, `TZ=UTC`, `GIT_CONFIG_GLOBAL=<id>.home/.gitconfig`, `GIT_CONFIG_NOSYSTEM=1` (on macOS the system git config supplies the `osxkeychain` credential helper), `GIT_TERMINAL_PROMPT=0`, `PATH`.
  - `PATH` is the adapter's entries, then `<id>.home/bin`, then `/usr/bin:/bin:/usr/sbin:/sbin`. `<id>.home/bin` holds symlinks to `git` and `uv` as resolved on the harness's `PATH` (`HARNESS_TOOL_ALLOWLIST`). `uv` is included because projects' own instruction files tell agents to `uv run`. `~/.local/bin`, Homebrew, pipx and uv tool installs are not on `PATH`, so in a squadron sandbox `sq` resolves to the start commit's `.venv/bin/sq`.
- `HOME` is redirected rather than setting per-tool variables, because squadron's config directory comes from `Path.home()` and has no override variable. One redirect covers `~/.config/squadron`, `~/.claude`, `~/.claude.json`, `~/.codex`, `~/.gitconfig`, `~/.ssh` and `~/.netrc`.
- The scrubbed home is seeded with:
  - `.config/squadron/` copies of whichever of `SQUADRON_CONFIG_SEED = ("config.toml", "models.toml", "providers.toml")` exist. Aliases and `pipeline.max_cost_usd` must resolve. `metrology/`, `runs/`, `replays/`, `reviews/` and logs are left out, so there is no store and no memory.
  - `.gitconfig` with `user.name`/`user.email` set to a fixed benchmark identity and `init.defaultBranch=main`.
- `CredentialGrant` says what auth enters: `CredentialGrant.none()` for suite runs, or `CredentialGrant.for_profiles(profiles)` for producer runs. The grant adds each profile's `api_key_env` variable, read from the profile definition and never hard-coded, plus that profile's carryover files (D8).
- Every child process the harness starts in a sandbox (pytest, the probe, and later `sq run`) receives `ScrubbedEnvironment.variables()` through `ProcessRunner.run(env=..., replace_env=True)`; `env=` alone merges over `os.environ` and would not apply the scrub. The SDK merges `os.environ` with its options env, so agent CLIs started by a scrubbed `sq run` inherit the scrub.

### D8 — Auth carryover and the auth check
Status: decided
- `auth_carryover.py` holds one table from `ProfileName` to the home-relative files that grant auth. Carried files are **symlinked**, not copied, so a token refresh writes back to the user's one real file instead of rotating a copy that is then thrown away. Initial entries:
  - `openai-oauth` → `.codex/auth.json` (the file `OAuthFileStrategy` reads).
  - `sdk` → `.claude/.credentials.json` when it exists. On macOS Claude Code keeps its credentials in the login Keychain, and this table cannot carry that.
  - API-key profiles (`openai`, `openrouter`, `gemini`, `local`) → no files. Their variable passes through via D7.
- **The auth check is empirical.** Whether the Keychain lookup works under a redirected `HOME` is unknown, and the check exists to find out. `sq benchmark auth-check --model <alias> [--model …]` runs one probe per distinct profile. A probe is the installed `sq`, run by absolute path under a scrubbed environment granted that profile, executing hidden `sq benchmark _auth-probe --model <alias>`. The hidden command resolves the alias and sends one fixed minimal prompt through the same agent-creation path a dispatch uses.
  - Yes: exit 0 and a non-empty response.
  - No: anything else. A probe that outlives `benchmark.auth_probe_timeout_s` is a no with reason `timed out`, since a missing login can hang on a prompt. The result carries the exit code and stderr. It is reported in a table, and the command exits 1. No fallback to the unscrubbed environment, no added variables.
  - After each probe, the check verifies that every carried symlink is still a symlink. A runtime that replaced it with a regular file (write-by-rename) is reported as `yes, but carryover replaced`, because the user's real token may now be stale.
- If a provider answers no, the remedy is a PM decision (for example, a declared token variable for `sdk`). It is never a silent workaround in code.
- Deferred (squadron#301): carried credentials are symlinks to the real files, so a tool that opens one for writing can modify the real login. Symlinks are what lets the check detect a replaced file; whether to copy instead is a separate decision.
- Rejected: checking auth by reading files. The question is whether the runtime authenticates, not whether a file exists.

### D9 — A separate benchmark adapter seam
Status: decided
- `BenchmarkAdapter` is its own protocol, not an extension of 400's `LanguageAdapter`. The two have different clients: snapshot measurement versus case execution. Merging them would make every snapshot adapter stub execution methods. `adapter_for` is keyed by `SourceLanguage`, as 400's registry is, with one entry. Detecting a tree's language waits for a second adapter (Future Work 1).
- Shape beyond Python (open question from the slice plan): the protocol has only what a language must supply to run a case. 422 adds fairness-rule methods and 425 adds hidden-test injection, each in its own slice.

```python
class BenchmarkAdapter(Protocol):
    language: SourceLanguage
    def resolve_environment(self, ctx: SandboxContext) -> EnvironmentIdentity: ...
    def path_entries(self, ctx: SandboxContext) -> tuple[Path, ...]: ...
    def run_suite(self, ctx: SandboxContext, selection: SuiteSelection) -> SuiteRun: ...
```

`SandboxContext` holds `tree`, `output_dir`, `env: ScrubbedEnvironment`, `runner: ProcessRunner` and the install and suite timeouts. `SuiteSelection` is either `all_tests()` or `nodes(ids)`, either one with `deselect` (node ids, for the exclusion and superseded lists).

### D10 — Suite runner: an injected pytest reporter plugin
Status: decided
- The runner runs `<tree>/.venv/bin/python -m pytest -p squadron_benchmark_reporter -p no:cacheprovider` with the selection's node ids or `--deselect` arguments. `cwd=tree`, the scrubbed environment, `PYTHONPATH=<id>.out/plugin`, a JSONL path from an environment variable, and a bound of `benchmark.suite_timeout_s`. `no:cacheprovider` keeps `.pytest_cache` out of the tree. The plugin directory and its output sit outside the tree, so the producer's diff and the project's files are untouched.
- The plugin implements `pytest_collectreport` and a `pytest_runtest_makereport` hookwrapper. It writes one line per collection failure and per test phase: node id, phase, outcome, exception type's qualified name and module, and for `AttributeError`/`ImportError` the `name`/`obj` module file. For an `AttributeError` raised inside `unittest/mock.py`, `obj` is unset, so the plugin reads the `_patch` object (`self` in the innermost frame) and records its `target` module's file. It also writes the file and line of the innermost traceback frame. It imports only the standard library and `pytest`.
- Rejected: `--junitxml`. Node ids come back as a classname and name, which loses parametrized ids and exact paths, and exception types are reduced to text.
- A run that times out returns `SuiteRun(timed_out=True)` with whatever lines were written, and every requested node without a result is `not_run`. A missing or unparseable JSONL file with a non-zero pytest exit raises `SuiteRunError` carrying pytest's stderr. It never comes back as an empty pass.

### D11 — Failure classification
Status: decided
- `FailureKind` values, assigned in this order:
  1. `collection_error`: the node's file failed collection, or the requested node id was not collected.
  2. `missing_symbol`: `ImportError` or `ModuleNotFoundError` naming a project module, or `AttributeError` whose `obj` is a project module, or a `mock.patch` target that is not found in a project module (detected through the recorded patch target, D10). Checked on Python 3.13: mock's `AttributeError` has no `name` or `obj`.
  3. `assertion_failure`: `AssertionError`, or pytest's `Failed` (`pytest.fail`).
  4. `project_exception`: any other exception whose innermost frame is in project source.
  5. `other_exception`: any other exception (raised in test code, a fixture or a dependency).
- `other_exception` is a fifth kind beyond the slice plan's three. A `TypeError` raised at the call site in a test is often a changed signature, which is neither the crash a fix cures nor a clean assertion. Naming it lets 422 exclude it as undecidable instead of guessing.
- Project source is a file under the tree, not under `.venv`, and not a test module (`test_*.py`, `*_test.py`, `conftest.py`). A project module is a module whose `__file__` is project source.
- `NodeResult` holds `node_id`, `outcome` (`passed`, `failed`, `error`, `skipped`, `xfailed`, `xpassed`, `not_run`), `failure_kind` (set only for `failed` and `error`), `phase`, `exception_type`.

### D12 — Timeouts are config keys
Status: decided
- `benchmark.install_timeout_s` (default 900), `benchmark.suite_timeout_s` (default 1800) and `benchmark.auth_probe_timeout_s` (default 120) are declared in `config/keys.py` with their defaults, like `cf.cli_timeout_s`. No timeout is written inline.
- Every bounded call goes through `ProcessRunner`, which already starts each child in its own process group and kills the whole group on timeout. Nothing new is needed for orphans.

### Technology Choices

- `uv` for installs. It is already squadron's toolchain, and 400 depends on `uv.lock`.
- pytest plugin hooks, rather than parsing output, for per-node results.
- No new dependencies.

### Patterns and Conventions

- The store follows 400's pattern: deterministic record ids, an optional sibling payload, Pydantic at the file boundary.
- Errors: `SandboxError` (repository), `EnvironmentResolutionError(reason, detail)`, `SuiteRunError`, `MetrologyStoreError`, `MissingCredentialError` (a granted variable is unset), `MissingHarnessToolError`, `UnresolvedProfileError` (alias unknown or without a profile), `ProbeStartError` (`sq` cannot start in the scrubbed environment; not an auth answer). Each is logged at ERROR where it is raised, carries the failing command's stderr, and never resolves to a default.
- `sweep_benchmark_orphans` (in `benchmark/sandbox.py`) is `sweep_orphans` with no cf sweep and the `.home`/`.out` sibling suffixes; `sq benchmark sandbox` calls it first.
- The dependency install runs under the scrubbed environment (`replace_env=True`) with uv's real cache and Python directories (`UV_CACHE_DIR`, `UV_PYTHON_INSTALL_DIR`, from `uv cache dir` and `uv python dir`); proxy and index settings are not carried over.
- `MetrologyStore.create_record` fails with `FileExistsError` if the record exists; `write_case_set` re-reads and retries so concurrent writers never overwrite a version.
- `run_suite` passes `--continue-on-collection-errors`, so one broken module does not hide every other node.
- Reason and kind values are `StrEnum`s defined once (`EnvironmentFailureReason`, `FailureKind`, `NodeOutcome`, `CaseKind`, `GraderCommandKind`).

## Implementation Details

### API Contracts

**`sq benchmark auth-check --model ALIAS [--model ALIAS …]`**

```
profile        alias     result
sdk            opus      yes
openai-oauth   sol       no    exit 1: <probe stderr, first line>
```

Exit 0 when every profile answers yes. Exit 1 when any answers no. At least one `--model` is required, so there is no implicit "all aliases".

**`sq benchmark sandbox REV [--suite] [--node ID …] [--keep]`**

Builds a sandbox at `REV` in the current project, resolves the environment, and prints the environment identity. With `--suite`, it runs the whole suite. With `--node`, it runs only the given node ids. Either way it prints counts per outcome and failure kind, plus each failing node with its kind. `--keep` leaves the directories in place and prints their paths. A resolution failure prints the reason and uv's stderr and exits 1.

**`sq benchmark _auth-probe --model ALIAS`** (hidden): used only by the auth check.

### Database / Storage Schema

```python
class BenchmarkCase(BaseModel, frozen=True):
    case_id: str                       # derived, validated (D1)
    project_id: ProjectId
    kind: CaseKind
    start_sha: str
    reference_sha: str
    task_text: str
    hidden_tests: tuple[str, ...]
    hidden_fixtures: tuple[ConftestFixture, ...]
    superseded_tests: tuple[str, ...]
    excluded_tests: tuple[str, ...]
    grader_commands: tuple[GraderCommand, ...]   # kind (suite|lint|typecheck) + argv
    provenance: CaseProvenance                   # not identity: source ref, created_at, built_by

class CaseSet(BaseModel, frozen=True):
    name: str
    version: int
    case_ids: tuple[str, ...]
    created_at: datetime
```

`BenchmarkRecordStore`: `write_case(case) -> str`, `get_case(case_id) -> BenchmarkCase | None`, `list_cases(project_id) -> list[BenchmarkCase]`, `write_case_set(name, case_ids) -> CaseSet`, `get_case_set(name, version=None) -> CaseSet | None` (latest when `None`), `list_case_sets() -> list[CaseSet]`.

## Integration Points

### Provides to Other Slices

- **422:** `BenchmarkCase`, `CaseSet` and `BenchmarkRecordStore`; `BenchmarkSandbox` and `EnvironmentIdentity` to key qualification; `run_suite` with `FailureKind`, which the test-first check reads; the adapter seam for the fairness-rule methods.
- **424:** `BenchmarkSandbox`, `ScrubbedEnvironment` with `CredentialGrant.for_profiles`, and the auth check's answer. `HistoryFreeSandbox` for the cf registration 426 adds.
- **425:** `run_suite` with `deselect` for regressions; the in-tree `.venv` that 400's snapshot adapters can measure; `EnvironmentIdentity` as part of the grader identity.
- **426, 427:** case records with `kind=slice`, the sandbox and the suite runner.

### Consumes from Other Slices

- **177:** sandbox internals, extracted (D4) without changing `sq replay` behavior.
- **320:** store primitives and `ProjectId`. Two public methods are added. Existing records still read as before.
- **Providers:** profile definitions and alias resolution, read only.

## Success Criteria

### Functional Requirements

- A `BenchmarkCase` writes to the store and reads back equal. Changing any one identity field (each tested separately) gives a different `case_id`. Changing provenance alone does not. For a record whose stored id does not match its content, `get_case` raises `MetrologyStoreError` and `list_cases` logs a WARNING and skips it.
- Writing an identical case twice leaves one record. `write_case_set` creates v1, returns v1 again for the same list, creates v2 for a changed list, and rejects unknown case ids.
- `sq benchmark sandbox <historical squadron commit>` installs that commit's own dependencies and prints an environment identity whose lockfile hash matches `git show <commit>:uv.lock | shasum -a 256`.
- A commit without `uv.lock` fails with `no_lockfile`. A lock that is out of date with its `pyproject.toml` fails with `lock_stale_or_unresolvable` and uv's message. Neither installs anything.
- Inside the scrubbed environment: `GH_TOKEN`, `GITHUB_TOKEN` and `SSH_AUTH_SOCK` are unset; `git config --get credential.helper` prints nothing; `HOME` is the scrubbed home; every `PATH` entry under the user's home belongs to the sandbox (`<tree>/.venv/bin`, `<id>.home/bin`); and in a squadron sandbox `command -v sq` is `<tree>/.venv/bin/sq` and `sq --version` reports the start commit's version.
- `sq benchmark auth-check` gives a yes or no for `sdk` and `openai-oauth` on the PM's machine, and the answer is recorded in the DEVLOG. A no exits 1 and shows the probe's error. A test with a probe that hangs gets a `timed out` no.
- The suite runner returns a `NodeResult` for every requested node. Fixture tests cover each `FailureKind`: an assertion, a project-code crash, a missing import of a project name, a project-module `AttributeError`, a `mock.patch` of a missing target, a collection error, an exception raised in test code, a not-collected node id, and a timeout.

### Technical Requirements

- `ruff format`, `ruff check` and `pyright` (zero errors) are clean. The existing `tests/replay/` suite passes unchanged after the D4 extraction.
- Every failure path (install failure, timeout, missing JSONL, missing `uv`) has a test that asserts its error and reason.
- Scrubbed-environment tests assert the allowlist from the built variable map, and one integration test asserts it from inside a real child process in a real sandbox: `env` output, `command -v sq`, `sq --version` and `git config --get credential.helper`.
- Suite-runner tests run real pytest against small fixture projects under `tests/benchmark/fixtures/`. Classification is not tested only against synthetic JSONL.

### Integration Requirements

- 422 can build a sandbox at any commit of a uv project, run a chosen node id at the parent, and read its `FailureKind` with no further harness work.
- `sq replay run` behaves as before (its tests and one manual run).

### Verification Walkthrough

Run from the squadron checkout with this branch's `sq` first on `PATH`: `uv sync && export PATH="$PWD/.venv/bin:$PATH"` (an older installed `sq` lacks the probe). Verified on macOS, 2026-11-06.

1. **Auth under the scrubbed environment:**
   ```bash
   sq benchmark auth-check --model sonnet --model luna
   ```
   Prints `probing with: <path to .venv/bin/sq>` then one row per profile: `openai-oauth luna yes`; `sdk sonnet no (… Not logged in …)`. Exit 1 while any row is not `yes`. On this machine `sdk` is a `no`: the Claude Code login is in the macOS Keychain and `~/.claude/.credentials.json` does not exist, so nothing is carried over. Recorded in the DEVLOG for the PM.

2. **A historical sandbox with its own environment.** (In zsh write `${REV}:uv.lock`; `$REV:u` is read as a modifier.)
   ```bash
   REV=$(git log --format=%h -n1 v0.20.0)
   sq benchmark sandbox $REV --keep
   git show ${REV}:uv.lock | shasum -a 256
   ```
   Prints `language`, `lockfile_path`, `lockfile_sha256`, `interpreter_version`, `installer_version`, `platform`, `scrub_spec_version`, `identity_digest`, then the `tree:`, `home:` and `out:` paths, which exist. `lockfile_sha256` equals the shasum (`3e75a85f…` for `69550e3e`).

3. **The installed `sq` is out of reach.** `uv run pytest tests/benchmark/test_scrubbed_env.py -v` passes (9 tests, about 10 s with a warm uv cache). Its integration test installs the repository's own HEAD and checks `env`, `command -v sq`, `sq --version` and `credential.helper` from inside the sandbox.

4. **Suite run with classification:**
   ```bash
   sq benchmark sandbox $REV --suite
   sq benchmark sandbox $REV --node <node-id>
   ```
   `--suite` at `69550e3e` took about 10 minutes and printed `outcomes: failed=6, passed=5748, skipped=8` and `failure kinds: assertion_failure=6`, with one `failed <node id> (assertion_failure)` line per failure (cf-schema and PR-fixture tests that need `cf`, absent from the scrubbed `PATH`). `--node` with one of those ids prints `outcomes: failed=1` and that node. `--suite` with `--node` exits 2.

5. **A lockfile that does not resolve:** `uv run pytest tests/benchmark/test_python_environment.py::test_stale_lock_fails tests/benchmark/test_python_environment.py::test_no_lockfile_runs_nothing -v` passes: reasons `lock_stale_or_unresolvable` (uv's message kept) and `no_lockfile`, no `.venv` left. `sq benchmark sandbox` on such a commit prints `environment resolution failed: <reason>` and uv's stderr, and exits 1.

6. **Case records:** `uv run pytest tests/metrology/test_benchmark_store.py -v` passes (12 tests).

7. **Cleanup:** after a plain `sq benchmark sandbox $REV`, `ls ~/.config/squadron/benchmark/` is empty. Start a run and kill it about a second in (`sq benchmark sandbox $REV & pid=$!; sleep 1; kill -9 $pid`): a `sandbox-…` directory and `.lock` remain. The next run prints `removing orphaned replay sandbox <path>` as a WARNING and leaves nothing behind. A `--keep` sandbox is swept the same way by the next run.

## Risk Assessment

### Technical Risks

- **Claude auth on macOS under a redirected `HOME`.** The credentials are in the Keychain, and whether Claude Code finds them with a different `HOME` is unknown.
- **Token refresh through a carried-over auth file.** If a runtime rewrites its auth file by rename, the symlink is replaced. The user's real file then holds a refresh token that may already have been rotated.
- **Historical locks that no longer resolve** (yanked packages, Python versions uv can no longer download). This lowers case yield, and 422's report counts it per reason.

### Mitigation Strategies

- The auth check is implementation step 1, before any other code, so a no reaches the PM before the rest of the slice is built.
- The check reports a replaced symlink explicitly (D8). If it happens for a provider, its carryover changes to a PM-chosen mechanism before any producer runs.
- A failed lock resolution is a recorded reason, never retried unpinned (D5).

## Implementation Notes

### Development Approach

1. **Auth spike.** A minimal `ScrubbedEnvironment` and the hidden probe. Run the check for `sdk` and `openai-oauth`, record the answers in the DEVLOG, and bring any no to the PM.
2. Extract `HistoryFreeSandbox`, with the replay tests green before and after.
3. Records and `BenchmarkRecordStore`, plus the two store primitives.
4. `BenchmarkAdapter`, `adapter_for` and Python environment resolution.
5. The reporter plugin, the suite runner and classification, against fixture projects.
6. `BenchmarkSandbox` and the CLI. Run the verification walkthrough.

Effort: 3/5.

### Special Considerations

- **Limits of the scrub.** The network stays open, so a producer could install the published, later version of the project (`uvx squadron`, `pip install squadron`) and reach the answer that way. A redirected `HOME` cannot prevent that. It is recorded here as an input to 424's leak scan, which should flag installs of the project's own package.
- The reporter plugin runs under the start commit's pytest. It must stay within hooks pytest has had since 7.0. A pytest without them fails with `SuiteRunError`, never a silent empty result.
- Seeding copies `config.toml`, which may hold user preferences that affect a run. That is intended: the producer runs under the same pipeline settings the PM uses. 424 records which seed files were present.
